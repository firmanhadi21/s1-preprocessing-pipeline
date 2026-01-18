#!/usr/bin/env python3
"""
Period-Based Sentinel-1 Pipeline for Rice Growth Stage Mapping

This pipeline processes Sentinel-1 data for all 31 12-day periods in a year:
1. For each period: Download scenes falling within that 12-day window
2. Preprocess each scene with SNAP GPT
3. Convert to GeoTIFF (Gamma0 VH in dB)
4. Mosaic multiple scenes within each period (with histogram matching)
5. Stack all 31 periods into a single multi-band GeoTIFF ready for training/prediction

The output is a 31-band GeoTIFF where:
- Band 1 = Period 1 (Jan 1-12)
- Band 2 = Period 2 (Jan 13-24)
- ...
- Band 31 = Period 31 (Dec 27-31)

Usage:
    # Full year processing
    python s1_period_pipeline.py --config pipeline_config_java.yaml --year 2024 --run-all

    # Process specific periods only
    python s1_period_pipeline.py --config pipeline_config_java.yaml --year 2024 \\
        --periods 1 2 3 --run-all

    # Download only for specific periods
    python s1_period_pipeline.py --config pipeline_config_java.yaml --year 2024 \\
        --periods 15-20 --download-only

    # Stack existing period mosaics
    python s1_period_pipeline.py --config pipeline_config_java.yaml --year 2024 --stack-only
"""

import os
import sys
from pathlib import Path
import yaml
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import argparse
from collections import defaultdict
import subprocess
import numpy as np

# Import period utilities
from period_utils import get_period_dates, get_period_from_date

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PeriodBasedPipeline:
    """
    Complete period-based pipeline for Sentinel-1 rice growth stage mapping
    """

    def __init__(self, config_file: str, year: int):
        """Initialize pipeline from config file"""
        self.config = self._load_config(config_file)
        self.year = year
        self.work_dir = Path(self.config['directories']['work_dir']) / f"year_{year}"
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # Setup base directories
        self.period_mosaics_dir = self.work_dir / 'period_mosaics'
        self.period_mosaics_dir.mkdir(parents=True, exist_ok=True)

        self.final_stack_dir = self.work_dir / 'final_stack'
        self.final_stack_dir.mkdir(parents=True, exist_ok=True)

        self.temp_dir = self.work_dir / 'temp'
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Period-based Pipeline for {year}")
        logger.info(f"Workspace: {self.work_dir}")

    def _get_period_dirs(self, period: int):
        """Get directory paths for a specific period"""
        period_dir = self.work_dir / f"p{period}"
        period_dir.mkdir(parents=True, exist_ok=True)

        dirs = {
            'downloads': period_dir / 'downloads',
            'preprocessed': period_dir / 'preprocessed',
            'geotiff': period_dir / 'geotiff'
        }

        for d in dirs.values():
            d.mkdir(parents=True, exist_ok=True)

        return dirs

    def _load_config(self, config_file: str) -> Dict:
        """Load configuration from YAML file"""
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        logger.info(f"Loaded configuration from: {config_file}")
        return config

    def _parse_period_range(self, period_spec: str) -> List[int]:
        """
        Parse period specification into list of periods

        Examples:
            "1" -> [1]
            "1,2,3" -> [1, 2, 3]
            "1-5" -> [1, 2, 3, 4, 5]
            "1-5,10,15-20" -> [1, 2, 3, 4, 5, 10, 15, 16, 17, 18, 19, 20]
        """
        periods = []
        for part in period_spec.split(','):
            if '-' in part:
                start, end = map(int, part.split('-'))
                periods.extend(range(start, end + 1))
            else:
                periods.append(int(part))
        return sorted(set(periods))

    def step1_download_by_period(self, periods: List[int]) -> Dict[int, List[Path]]:
        """
        Download Sentinel-1 scenes for each period

        Args:
            periods: List of period numbers (1-31)

        Returns:
            Dictionary mapping period number to list of downloaded files
        """
        logger.info("\n" + "=" * 70)
        logger.info("STEP 1: DOWNLOAD SENTINEL-1 DATA BY PERIOD")
        logger.info("=" * 70)

        try:
            import asf_search as asf
            from shapely.geometry import shape
        except ImportError:
            logger.error("Required packages not installed. Run: pip install asf-search shapely")
            return {}

        cfg = self.config['data_acquisition']
        bbox = cfg['aoi_bbox']

        # Create AOI
        aoi_geojson = {
            'type': 'Polygon',
            'coordinates': [[
                [bbox[0], bbox[1]],
                [bbox[2], bbox[1]],
                [bbox[2], bbox[3]],
                [bbox[0], bbox[3]],
                [bbox[0], bbox[1]]
            ]]
        }
        geom = shape(aoi_geojson)
        aoi_wkt = geom.wkt

        logger.info(f"AOI: {bbox}")
        logger.info(f"Year: {self.year}")
        logger.info(f"Periods to process: {periods}")

        # Download for each period
        downloaded_by_period = {}

        for period_num in periods:
            logger.info(f"\n{'='*60}")
            logger.info(f"Period {period_num}")
            logger.info(f"{'='*60}")

            # Get period-specific directories
            period_dirs = self._get_period_dirs(period_num)

            # Get period date range
            start_date, end_date = get_period_dates(self.year, period_num)
            logger.info(f"Date range: {start_date} to {end_date}")

            # Search for products
            logger.info("Searching ASF...")
            results = asf.search(
                platform=asf.PLATFORM.SENTINEL1,
                processingLevel='GRD_HD',
                start=start_date.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d'),
                intersectsWith=aoi_wkt,
                maxResults=100
            )

            logger.info(f"Found {len(results)} products for period {period_num}")

            if len(results) == 0:
                logger.warning(f"No products found for period {period_num}")
                downloaded_by_period[period_num] = []
                continue

            # Download products
            downloaded = []
            for i, result in enumerate(results, 1):
                # ASF download may save with different filename
                # Try to find the actual downloaded file
                expected_filename = result.properties['fileID'] + '.zip'
                expected_filepath = period_dirs['downloads'] / expected_filename

                # Also check for filename without suffix (actual ASF behavior)
                base_filename = result.properties['fileName']  # Original filename from ASF
                if base_filename.endswith('.zip'):
                    actual_filepath = period_dirs['downloads'] / base_filename
                else:
                    actual_filepath = period_dirs['downloads'] / (base_filename + '.zip')

                # Check if already downloaded (either format)
                if expected_filepath.exists():
                    logger.info(f"[{i}/{len(results)}] Already exists: {expected_filename}")
                    downloaded.append(expected_filepath)
                    continue
                elif actual_filepath.exists():
                    logger.info(f"[{i}/{len(results)}] Already exists: {base_filename}")
                    downloaded.append(actual_filepath)
                    continue

                logger.info(f"[{i}/{len(results)}] Downloading: {expected_filename}")
                try:
                    result.download(path=str(period_dirs['downloads']))

                    # Find which file was actually downloaded
                    if actual_filepath.exists():
                        downloaded.append(actual_filepath)
                        logger.info(f"  ✓ Downloaded as: {actual_filepath.name}")
                    elif expected_filepath.exists():
                        downloaded.append(expected_filepath)
                        logger.info(f"  ✓ Downloaded")
                    else:
                        logger.warning(f"  ? Downloaded but file not found in expected locations")
                except Exception as e:
                    logger.error(f"  ✗ Download failed: {e}")

            downloaded_by_period[period_num] = downloaded
            logger.info(f"Period {period_num}: Downloaded {len(downloaded)} files")

        # Summary
        total_downloads = sum(len(v) for v in downloaded_by_period.values())
        logger.info(f"\n✓ Total downloaded: {total_downloads} files across {len(periods)} periods")

        return downloaded_by_period

    def step2_preprocess_all(self, downloaded_by_period: Optional[Dict[int, List[Path]]] = None) -> Dict[int, List[Path]]:
        """
        Preprocess all downloaded scenes with SNAP GPT

        Args:
            downloaded_by_period: Dictionary mapping periods to downloaded files

        Returns:
            Dictionary mapping periods to preprocessed .dim files
        """
        logger.info("\n" + "=" * 70)
        logger.info("STEP 2: PREPROCESS WITH SNAP GPT")
        logger.info("=" * 70)

        # Find all downloaded files if not provided
        if downloaded_by_period is None:
            downloaded_by_period = {}
            # Scan all period folders
            for p in range(1, 32):
                period_dirs = self._get_period_dirs(p)
                zips = list(period_dirs['downloads'].glob('*.zip'))
                if zips:
                    downloaded_by_period[p] = zips

        if not downloaded_by_period:
            logger.warning("No files to preprocess")
            return {}

        cfg = self.config['preprocessing']
        gpt_path = cfg.get('snap_gpt_path', '/home/unika_sianturi/work/idmai/esa-snap/bin/gpt')
        graph_xml = cfg.get('graph_xml', 'sen1_preprocessing-gpt.xml')
        cache_size = cfg.get('cache_size', '8G')

        preprocessed_by_period = {}
        total_files = sum(len(v) for v in downloaded_by_period.values())
        current = 0

        for period_num in sorted(downloaded_by_period.keys()):
            period_dirs = self._get_period_dirs(period_num)
            period_files = downloaded_by_period[period_num]

            logger.info(f"\nPreprocessing Period {period_num}: {len(period_files)} files")

            preprocessed = []
            for input_file in period_files:
                current += 1
                output_name = input_file.stem + '_processed'
                output_file = period_dirs['preprocessed'] / output_name

                # Check if already processed
                if (output_file.with_suffix('.dim')).exists():
                    logger.info(f"[{current}/{total_files}] Already processed: {output_name}")
                    preprocessed.append(output_file.with_suffix('.dim'))
                    continue

                logger.info(f"[{current}/{total_files}] Processing: {input_file.name}")

                # Convert Path objects to absolute string paths
                input_file_str = str(input_file.absolute())
                output_file_str = str(output_file.absolute())

                cmd = [
                    gpt_path,
                    graph_xml,
                    f'-PmyFilename={input_file_str}',
                    f'-PoutputFile={output_file_str}',
                    '-c', cache_size,
                    '-q', '16'
                ]

                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

                    if result.returncode == 0 and output_file.with_suffix('.dim').exists():
                        logger.info(f"  ✓ Processed")
                        preprocessed.append(output_file.with_suffix('.dim'))
                    else:
                        logger.error(f"  ✗ Processing failed")
                        if result.stderr:
                            logger.error(f"  Error: {result.stderr[-500:]}")

                except subprocess.TimeoutExpired:
                    logger.error(f"  ✗ Processing timeout")
                except Exception as e:
                    logger.error(f"  ✗ Error: {e}")

            preprocessed_by_period[period_num] = preprocessed

        logger.info(f"\n✓ Preprocessed {sum(len(v) for v in preprocessed_by_period.values())} files")
        return preprocessed_by_period

    def step3_convert_to_geotiff(self, preprocessed_by_period: Optional[Dict[int, List[Path]]] = None) -> Dict[int, List[Path]]:
        """
        Convert preprocessed .dim files to GeoTIFF

        Args:
            preprocessed_by_period: Dictionary mapping periods to .dim files

        Returns:
            Dictionary mapping periods to GeoTIFF files
        """
        logger.info("\n" + "=" * 70)
        logger.info("STEP 3: CONVERT TO GEOTIFF")
        logger.info("=" * 70)

        import rasterio

        # Find all preprocessed files if not provided
        if preprocessed_by_period is None:
            preprocessed_by_period = {}
            # Scan all period folders
            for p in range(1, 32):
                period_dirs = self._get_period_dirs(p)
                dims = list(period_dirs['preprocessed'].glob('*.dim'))
                if dims:
                    preprocessed_by_period[p] = dims

        if not preprocessed_by_period:
            logger.warning("No files to convert")
            return {}

        geotiffs_by_period = {}
        total_files = sum(len(v) for v in preprocessed_by_period.values())
        current = 0

        for period_num in sorted(preprocessed_by_period.keys()):
            period_dirs = self._get_period_dirs(period_num)
            period_files = preprocessed_by_period[period_num]

            logger.info(f"\nConverting Period {period_num}: {len(period_files)} files")

            geotiffs = []
            for dim_file in period_files:
                current += 1
                # Find the VH data file
                data_dir = dim_file.with_suffix('.data')
                vh_file = data_dir / 'Gamma0_VH_db.img'

                if not vh_file.exists():
                    logger.warning(f"[{current}/{total_files}] VH file not found: {vh_file}")
                    continue

                output_tif = period_dirs['geotiff'] / f"{dim_file.stem}_VH.tif"

                if output_tif.exists():
                    logger.info(f"[{current}/{total_files}] Already converted: {output_tif.name}")
                    geotiffs.append(output_tif)
                    continue

                logger.info(f"[{current}/{total_files}] Converting: {dim_file.name}")

                try:
                    with rasterio.open(vh_file) as src:
                        data = src.read(1)
                        profile = src.profile.copy()

                        # Convert to Int16 by scaling dB values × 100
                        # This improves OTB harmonization stability
                        # Range: -30 dB → -3000, +5 dB → +500
                        # Precision: 0.01 dB
                        data_scaled = np.where(
                            (data == 0) | (data < -50) | (data > 10),
                            -32768,  # NoData for Int16
                            (data * 100).astype(np.int16)
                        )

                        # Update profile for Int16
                        profile.update(
                            driver='GTiff',
                            dtype=rasterio.int16,
                            compress='lzw',
                            nodata=-32768
                        )
                        profile.pop('tiled', None)
                        profile.pop('blockxsize', None)
                        profile.pop('blockysize', None)

                        with rasterio.open(output_tif, 'w', **profile) as dst:
                            dst.write(data_scaled, 1)

                    logger.info(f"  ✓ Created: {output_tif.name} (Int16, scaled ×100)")
                    geotiffs.append(output_tif)

                except Exception as e:
                    logger.error(f"  ✗ Conversion failed: {e}")

            geotiffs_by_period[period_num] = geotiffs

        total_geotiffs = sum(len(v) for v in geotiffs_by_period.values())
        logger.info(f"\n✓ Converted {total_geotiffs} files across {len(geotiffs_by_period)} periods")

        return geotiffs_by_period

    def _group_files_by_period(self, files: List[Path]) -> Dict[int, List[Path]]:
        """Group files by their acquisition period"""
        import re
        from collections import defaultdict

        files_by_period = defaultdict(list)

        for f in files:
            # Extract date from filename (format: S1A_IW_GRDH_1SDV_20240115T...)
            match = re.search(r'(\d{8})T', f.name)
            if match:
                date_str = match.group(1)
                date = datetime.strptime(date_str, '%Y%m%d')
                period_num = get_period_from_date(date)
                files_by_period[period_num].append(f)
            else:
                logger.warning(f"Could not extract date from: {f.name}")

        return dict(files_by_period)

    def step4_mosaic_by_period(self, geotiffs_by_period: Optional[Dict[int, List[Path]]] = None,
                                periods: Optional[List[int]] = None) -> Dict[int, Path]:
        """
        Create mosaics for each period using Sequential OTB Mosaicking (West to East)

        Args:
            geotiffs_by_period: Dictionary mapping periods to GeoTIFF files
            periods: List of periods to process (None = all)

        Returns:
            Dictionary mapping period number to mosaic file path
        """
        logger.info("\n" + "=" * 70)
        logger.info("STEP 4: SEQUENTIAL MOSAIC BY PERIOD (OTB West-to-East)")
        logger.info("=" * 70)

        # Find all GeoTIFFs and group by period if not provided
        if geotiffs_by_period is None:
            geotiffs_by_period = {}
            # Scan all period folders
            for p in range(1, 32):
                period_dirs = self._get_period_dirs(p)
                geotiffs = list(period_dirs['geotiff'].glob('*_VH.tif'))
                if geotiffs:
                    geotiffs_by_period[p] = geotiffs

        if not geotiffs_by_period:
            logger.warning("No GeoTIFF files found")
            return {}

        # Filter by requested periods
        if periods is not None:
            geotiffs_by_period = {p: geotiffs_by_period[p] for p in periods if p in geotiffs_by_period}

        # Get OTB configuration
        mosaic_cfg = self.config.get('mosaicking', {})
        feather = mosaic_cfg.get('feather', 'large')
        harmo_method = mosaic_cfg.get('harmo_method', 'band')
        harmo_cost = mosaic_cfg.get('harmo_cost', 'rmse')
        nodata = mosaic_cfg.get('nodata', -9999)

        logger.info(f"Sequential OTB Mosaic Configuration:")
        logger.info(f"  Feathering: {feather}")
        logger.info(f"  Harmonization method: {harmo_method}")
        logger.info(f"  Harmonization cost: {harmo_cost}")
        logger.info(f"  NoData value: {nodata}")

        # Setup OTB environment
        otb_env = self._setup_otb_environment()

        period_mosaics = {}

        for period_num in sorted(geotiffs_by_period.keys()):
            files = geotiffs_by_period[period_num]

            logger.info(f"\n{'='*60}")
            logger.info(f"Period {period_num}: {len(files)} scene(s)")
            logger.info(f"{'='*60}")

            output_mosaic = self.period_mosaics_dir / f"mosaic_p{period_num}.tif"

            if output_mosaic.exists():
                logger.info(f"Already mosaicked: {output_mosaic.name}")
                period_mosaics[period_num] = output_mosaic
                continue

            if len(files) == 1:
                # Single scene, just copy
                logger.info("Single scene, copying...")
                import shutil
                shutil.copy(files[0], output_mosaic)
                period_mosaics[period_num] = output_mosaic
                logger.info(f"  ✓ Copied: {output_mosaic.name}")
                continue

            # Multiple scenes - use sequential mosaicking
            logger.info(f"Sequential mosaicking {len(files)} scenes (west to east)...")

            try:
                # Sort scenes west to east
                sorted_files = self._sort_scenes_west_to_east(files)

                # Create intermediate directory
                intermediate_dir = self.temp_dir / f'intermediate_p{period_num}'
                intermediate_dir.mkdir(parents=True, exist_ok=True)

                # Sequential mosaicking
                current_mosaic = sorted_files[0]
                logger.info(f"\nStep 0: Starting with {current_mosaic.name}")

                for i, next_scene in enumerate(sorted_files[1:], start=1):
                    logger.info(f"\nStep {i}/{len(sorted_files)-1}:")

                    # Determine output file
                    if i == len(sorted_files) - 1:
                        # Last step - final output
                        step_output = output_mosaic
                    else:
                        # Intermediate step
                        step_output = intermediate_dir / f"mosaic_p{period_num}_{i}.tif"

                    # Mosaic two files
                    success = self._mosaic_two_otb(
                        current_mosaic, next_scene, step_output,
                        feather, harmo_method, harmo_cost, nodata, otb_env
                    )

                    if not success:
                        logger.error(f"  ✗ Failed at step {i}")
                        break

                    # Update current mosaic
                    # Delete previous intermediate (but not original scene)
                    if i > 1 and current_mosaic != sorted_files[0]:
                        current_mosaic.unlink()

                    current_mosaic = step_output

                # Cleanup intermediate directory
                import shutil
                shutil.rmtree(intermediate_dir, ignore_errors=True)

                if output_mosaic.exists():
                    file_size_mb = output_mosaic.stat().st_size / (1024**2)
                    logger.info(f"\n  ✓ Final mosaic: {output_mosaic.name}")
                    logger.info(f"    Size: {file_size_mb:.1f} MB")
                    period_mosaics[period_num] = output_mosaic
                else:
                    logger.error(f"  ✗ Final mosaic not created")

            except Exception as e:
                logger.error(f"  ✗ Mosaic failed: {e}")
                import traceback
                traceback.print_exc()

        logger.info(f"\n✓ Created {len(period_mosaics)} period mosaics")
        return period_mosaics

    def _sort_scenes_west_to_east(self, scene_files: List[Path]) -> List[Path]:
        """Sort scenes by western-most longitude (west to east)"""
        from osgeo import gdal

        logger.info("  Sorting scenes west to east...")

        scene_bounds = []
        for scene_file in scene_files:
            try:
                ds = gdal.Open(str(scene_file))
                gt = ds.GetGeoTransform()
                minx = gt[0]  # Western edge
                maxy = gt[3]  # Northern edge
                ds = None
                scene_bounds.append((scene_file, minx, maxy))
                logger.info(f"    {scene_file.name}: west={minx:.3f}")
            except Exception as e:
                logger.warning(f"    Could not get bounds for {scene_file.name}: {e}")

        # Sort by western longitude (minx), then by northern latitude for ties
        scene_bounds.sort(key=lambda x: (x[1], -x[2]))

        sorted_files = [sb[0] for sb in scene_bounds]

        logger.info("  Mosaicking order:")
        for i, scene_file in enumerate(sorted_files, 1):
            logger.info(f"    {i}. {scene_file.name}")

        return sorted_files

    def _mosaic_two_otb(self, file1: Path, file2: Path, output: Path,
                        feather: str, harmo_method: str, harmo_cost: str,
                        nodata: int, otb_env: dict) -> bool:
        """Mosaic two files using OTB"""
        logger.info(f"    Base: {file1.name}")
        logger.info(f"    Add:  {file2.name}")

        cmd = [
            'otbcli_Mosaic',
            '-il', str(file1), str(file2),
            '-out', str(output), 'float',
            '-comp.feather', feather,
            '-nodata', str(nodata)
        ]

        # Add harmonization if not 'none'
        if harmo_method != 'none':
            cmd.extend([
                '-harmo.method', harmo_method,
                '-harmo.cost', harmo_cost
            ])

        # Temp directory
        tmp_dir = output.parent / 'tmp_otb'
        tmp_dir.mkdir(parents=True, exist_ok=True)
        cmd.extend(['-tmpdir', str(tmp_dir)])

        try:
            result = subprocess.run(
                cmd, env=otb_env,
                capture_output=True, text=True,
                timeout=1800  # 30 min per pair
            )

            # Cleanup
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

            if result.returncode == 0 and output.exists():
                # Post-process: Fix OTB artifacts (zeros and positive values)
                logger.info(f"      Post-processing to fix OTB artifacts...")
                import rasterio

                with rasterio.open(output, 'r+') as ds:
                    data = ds.read(1)

                    # Count issues before fixing
                    is_zero = (data == 0)
                    is_positive = (data > 0)
                    n_zeros = np.sum(is_zero)
                    n_positive = np.sum(is_positive)

                    if n_zeros > 0 or n_positive > 0:
                        logger.info(f"      Fixing: {n_zeros} zeros, {n_positive} positive values")

                        # Replace zeros and positive values with nodata
                        data = np.where((data == 0) | (data > 0), nodata, data)

                        # Write back
                        ds.write(data, 1)

                size_mb = output.stat().st_size / (1024**2)
                logger.info(f"      → {data.shape[1]}x{data.shape[0]} pixels, {size_mb:.1f} MB")
                return True
            else:
                logger.error(f"      ✗ OTB failed")
                if result.stderr:
                    logger.error(f"      {result.stderr[-500:]}")
                return False

        except subprocess.TimeoutExpired:
            logger.error(f"      ✗ Timeout (>30 min)")
            return False
        except Exception as e:
            logger.error(f"      ✗ Error: {e}")
            return False

    def _setup_otb_environment(self):
        """Setup OTB environment variables"""
        otb_env = os.environ.copy()

        # Try to source OTB environment profile
        otb_profile = Path.home() / 'work' / 'OTB' / 'otbenv.profile'

        if otb_profile.exists():
            logger.debug(f"Loading OTB environment from: {otb_profile}")
            source_cmd = f'source {otb_profile} && env'

            try:
                env_result = subprocess.run(
                    source_cmd,
                    shell=True,
                    executable='/bin/bash',
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                for line in env_result.stdout.split('\n'):
                    if '=' in line:
                        key, _, value = line.partition('=')
                        otb_env[key] = value

                logger.debug("  ✓ OTB environment loaded")

            except Exception as e:
                logger.warning(f"Could not load OTB environment: {e}")
                logger.warning("Continuing with system environment...")

        else:
            logger.warning(f"OTB profile not found: {otb_profile}")
            logger.warning("Assuming OTB is in system PATH...")

        return otb_env

    def step5_stack_periods(self, period_mosaics: Optional[Dict[int, Path]] = None) -> Path:
        """
        Stack all period mosaics into final 31-band GeoTIFF

        Args:
            period_mosaics: Dictionary mapping period number to mosaic file

        Returns:
            Path to final stacked GeoTIFF
        """
        logger.info("\n" + "=" * 70)
        logger.info("STEP 5: STACK ALL PERIODS INTO MULTI-BAND GEOTIFF")
        logger.info("=" * 70)

        import rasterio
        from rasterio.warp import calculate_default_transform, reproject, Resampling

        # Find period mosaics if not provided
        if period_mosaics is None:
            period_mosaics = {}
            for f in sorted(self.period_mosaics_dir.glob('mosaic_p*.tif')):
                # Extract period number from filename (format: mosaic_p15.tif)
                import re
                match = re.search(r'mosaic_p(\d+)\.tif', f.name)
                if match:
                    period_num = int(match.group(1))
                    period_mosaics[period_num] = f

        if not period_mosaics:
            logger.error("No period mosaics found")
            return None

        logger.info(f"Periods available: {sorted(period_mosaics.keys())}")

        # Check which periods are missing
        all_periods = set(range(1, 32))
        available_periods = set(period_mosaics.keys())
        missing_periods = all_periods - available_periods

        if missing_periods:
            logger.warning(f"Missing periods: {sorted(missing_periods)}")
            logger.warning("Final stack will have gaps for these periods")

        # Determine common grid from first available period
        first_period = min(period_mosaics.keys())
        with rasterio.open(period_mosaics[first_period]) as src:
            profile = src.profile.copy()
            ref_crs = src.crs
            ref_transform = src.transform
            ref_bounds = src.bounds
            ref_shape = (src.height, src.width)

        logger.info(f"Reference grid from period {first_period}:")
        logger.info(f"  Shape: {ref_shape}")
        logger.info(f"  CRS: {ref_crs}")
        logger.info(f"  Bounds: {ref_bounds}")

        # Create output profile for 31-band stack
        profile.update(
            count=31,
            dtype='float32',
            compress='lzw',
            tiled=True,
            blockxsize=512,
            blockysize=512,
            BIGTIFF='YES'
        )

        output_stack = self.final_stack_dir / f"S1_VH_stack_{self.year}_31bands.tif"

        logger.info(f"\nCreating final stack: {output_stack.name}")

        with rasterio.open(output_stack, 'w', **profile) as dst:
            for period_num in range(1, 32):
                if period_num in period_mosaics:
                    logger.info(f"  Band {period_num}: Period {period_num}")

                    with rasterio.open(period_mosaics[period_num]) as src:
                        # Check if reprojection is needed
                        if src.crs != ref_crs or src.transform != ref_transform or src.shape != ref_shape:
                            logger.info(f"    Reprojecting to common grid...")
                            data = np.empty(ref_shape, dtype='float32')
                            reproject(
                                source=rasterio.band(src, 1),
                                destination=data,
                                src_transform=src.transform,
                                src_crs=src.crs,
                                dst_transform=ref_transform,
                                dst_crs=ref_crs,
                                resampling=Resampling.bilinear
                            )
                        else:
                            data = src.read(1)

                        dst.write(data.astype('float32'), period_num)
                else:
                    logger.warning(f"  Band {period_num}: MISSING - writing nodata")
                    nodata_band = np.full(ref_shape, profile.get('nodata', -9999), dtype='float32')
                    dst.write(nodata_band, period_num)

        logger.info(f"\n✓ Final stack created: {output_stack}")

        # Print statistics
        file_size_gb = output_stack.stat().st_size / 1e9
        logger.info(f"  Size: {file_size_gb:.2f} GB")
        logger.info(f"  Bands: 31")
        logger.info(f"  Shape: {ref_shape}")
        logger.info(f"  Ready for training/prediction!")

        return output_stack

    def run_full_pipeline(self, periods: Optional[List[int]] = None,
                          skip_download: bool = False,
                          skip_preprocess: bool = False,
                          skip_convert: bool = False,
                          skip_mosaic: bool = False) -> Path:
        """
        Run complete period-based pipeline

        Args:
            periods: List of periods to process (None = all 31 periods)
            skip_download: Skip download step
            skip_preprocess: Skip preprocessing step
            skip_convert: Skip conversion step
            skip_mosaic: Skip mosaicking step

        Returns:
            Path to final stacked GeoTIFF
        """
        logger.info("\n" + "=" * 80)
        logger.info("PERIOD-BASED SENTINEL-1 PIPELINE FOR RICE GROWTH STAGE MAPPING")
        logger.info("=" * 80)
        logger.info(f"Year: {self.year}")
        logger.info(f"Start time: {datetime.now()}")
        logger.info(f"Workspace: {self.work_dir}")

        if periods is None:
            periods = list(range(1, 32))
        logger.info(f"Periods to process: {periods}")

        start_time = datetime.now()

        # Step 1: Download by period
        if not skip_download:
            downloaded = self.step1_download_by_period(periods)
        else:
            logger.info("\nSkipping download")
            downloaded = None

        # Step 2: Preprocess
        if not skip_preprocess:
            preprocessed = self.step2_preprocess_all(downloaded)
        else:
            logger.info("\nSkipping preprocessing")
            preprocessed = None

        # Step 3: Convert to GeoTIFF
        if not skip_convert:
            geotiffs = self.step3_convert_to_geotiff(preprocessed)
        else:
            logger.info("\nSkipping conversion")
            geotiffs = None

        # Step 4: Mosaic by period
        if not skip_mosaic:
            period_mosaics = self.step4_mosaic_by_period(geotiffs, periods)
        else:
            logger.info("\nSkipping mosaicking")
            period_mosaics = None

        # Step 5: Stack all periods
        final_stack = self.step5_stack_periods(period_mosaics)

        # Summary
        elapsed = datetime.now() - start_time
        logger.info("\n" + "=" * 80)
        logger.info("PIPELINE COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Total time: {elapsed}")
        logger.info(f"Final output: {final_stack}")
        logger.info("\nNext steps:")
        logger.info("  1. Train model: python train.py")
        logger.info("  2. Make predictions: python predict.py --period 15")

        return final_stack


def main():
    parser = argparse.ArgumentParser(
        description='Period-Based Sentinel-1 Pipeline for Rice Growth Stage Mapping',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--config', required=True,
                        help='Pipeline configuration file (YAML)')
    parser.add_argument('--year', type=int, required=True,
                        help='Year to process (e.g., 2024)')
    parser.add_argument('--periods', type=str,
                        help='Periods to process (e.g., "1-5,10,15-20", default: all 31 periods)')

    # Actions
    parser.add_argument('--run-all', action='store_true',
                        help='Run full pipeline')
    parser.add_argument('--download-only', action='store_true',
                        help='Only download data')
    parser.add_argument('--preprocess-only', action='store_true',
                        help='Only preprocess data')
    parser.add_argument('--convert-only', action='store_true',
                        help='Only convert to GeoTIFF')
    parser.add_argument('--mosaic-only', action='store_true',
                        help='Only mosaic by period')
    parser.add_argument('--stack-only', action='store_true',
                        help='Only stack existing period mosaics')

    # Skip options
    parser.add_argument('--skip-download', action='store_true',
                        help='Skip download step')
    parser.add_argument('--skip-preprocess', action='store_true',
                        help='Skip preprocessing step')
    parser.add_argument('--skip-convert', action='store_true',
                        help='Skip conversion step')
    parser.add_argument('--skip-mosaic', action='store_true',
                        help='Skip mosaicking step')

    args = parser.parse_args()

    if not Path(args.config).exists():
        logger.error(f"Configuration file not found: {args.config}")
        sys.exit(1)

    # Initialize pipeline
    pipeline = PeriodBasedPipeline(args.config, args.year)

    # Parse periods
    periods = None
    if args.periods:
        periods = pipeline._parse_period_range(args.periods)
        logger.info(f"Processing periods: {periods}")

    # Run requested action
    if args.download_only:
        pipeline.step1_download_by_period(periods or list(range(1, 32)))
    elif args.preprocess_only:
        pipeline.step2_preprocess_all()
    elif args.convert_only:
        pipeline.step3_convert_to_geotiff()
    elif args.mosaic_only:
        pipeline.step4_mosaic_by_period(periods=periods)
    elif args.stack_only:
        pipeline.step5_stack_periods()
    elif args.run_all:
        pipeline.run_full_pipeline(
            periods=periods,
            skip_download=args.skip_download,
            skip_preprocess=args.skip_preprocess,
            skip_convert=args.skip_convert,
            skip_mosaic=args.skip_mosaic
        )
    else:
        logger.error("Please specify an action: --run-all, --download-only, etc.")
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
