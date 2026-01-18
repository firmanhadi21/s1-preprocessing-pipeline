#!/usr/bin/env python3
"""
Multi-Scene Sentinel-1 Pipeline with Mosaicking

This script handles:
1. Downloading multiple Sentinel-1 scenes from ASF
2. Preprocessing each scene with SNAP GPT
3. Converting to GeoTIFF (Gamma0 VH in dB)
4. Mosaicking scenes from the same date with histogram matching

Usage:
    python s1_multiscene_pipeline.py --config pipeline_config_semarang_demak.yaml --run-all
    python s1_multiscene_pipeline.py --config pipeline_config_semarang_demak.yaml --download-only
    python s1_multiscene_pipeline.py --config pipeline_config_semarang_demak.yaml --preprocess-only
    python s1_multiscene_pipeline.py --config pipeline_config_semarang_demak.yaml --mosaic-only
"""

import os
import sys
from pathlib import Path
import yaml
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import argparse
from collections import defaultdict
import subprocess
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MultiScenePipeline:
    """
    Pipeline for processing multiple Sentinel-1 scenes with mosaicking
    """

    def __init__(self, config_file: str):
        """Initialize pipeline from config file"""
        self.config = self._load_config(config_file)
        self.work_dir = Path(self.config['directories']['work_dir'])
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # Setup directories
        self.dirs = {
            'downloads': self.work_dir / 'downloads',
            'preprocessed': self.work_dir / 'preprocessed',
            'geotiff': self.work_dir / 'geotiff',
            'mosaic': self.work_dir / 'mosaic'
        }

        for dir_path in self.dirs.values():
            dir_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Pipeline workspace: {self.work_dir}")

    def _load_config(self, config_file: str) -> Dict:
        """Load configuration from YAML file"""
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        logger.info(f"Loaded configuration from: {config_file}")
        return config

    def step1_download(self) -> Dict[str, List[Path]]:
        """
        Download Sentinel-1 scenes from ASF

        Returns:
            Dictionary mapping dates to list of downloaded file paths
        """
        logger.info("\n" + "=" * 60)
        logger.info("STEP 1: DOWNLOAD SENTINEL-1 DATA FROM ASF")
        logger.info("=" * 60)

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
        logger.info(f"Period: {cfg['start_date']} to {cfg['end_date']}")

        # Search for products
        logger.info("\nSearching ASF...")
        results = asf.search(
            platform=asf.PLATFORM.SENTINEL1,
            processingLevel='GRD_HD',
            start=cfg['start_date'],
            end=cfg['end_date'],
            intersectsWith=aoi_wkt,
            maxResults=100
        )

        logger.info(f"Found {len(results)} products")

        if len(results) == 0:
            logger.warning("No products found")
            return {}

        # Group by date
        by_date = defaultdict(list)
        for r in results:
            date = r.properties['startTime'][:10]
            by_date[date].append(r)

        logger.info("\nProducts by date:")
        for date in sorted(by_date.keys()):
            products = by_date[date]
            size_gb = sum(p.properties.get('bytes', 0) for p in products) / 1e9
            logger.info(f"  {date}: {len(products)} scene(s), {size_gb:.1f} GB")

        # Download all products
        downloaded = defaultdict(list)
        total = sum(len(v) for v in by_date.values())
        current = 0

        for date in sorted(by_date.keys()):
            for result in by_date[date]:
                current += 1
                filename = result.properties['fileID'] + '.zip'
                filepath = self.dirs['downloads'] / filename

                if filepath.exists():
                    logger.info(f"[{current}/{total}] Already exists: {filename}")
                    downloaded[date].append(filepath)
                    continue

                logger.info(f"[{current}/{total}] Downloading: {filename}")
                try:
                    result.download(path=str(self.dirs['downloads']))
                    downloaded[date].append(filepath)
                    logger.info(f"  ✓ Downloaded: {filepath.name}")
                except Exception as e:
                    logger.error(f"  ✗ Download failed: {e}")

        logger.info(f"\n✓ Downloaded {sum(len(v) for v in downloaded.values())} files")
        return downloaded

    def step2_preprocess(self, downloaded: Optional[Dict[str, List[Path]]] = None) -> Dict[str, List[Path]]:
        """
        Preprocess all scenes with SNAP GPT

        Args:
            downloaded: Dictionary mapping dates to downloaded files

        Returns:
            Dictionary mapping dates to preprocessed .dim files
        """
        logger.info("\n" + "=" * 60)
        logger.info("STEP 2: PREPROCESS WITH SNAP GPT")
        logger.info("=" * 60)

        # Find downloaded files if not provided
        if downloaded is None:
            downloaded = defaultdict(list)
            for f in sorted(self.dirs['downloads'].glob('*.zip')):
                # Extract date from filename (S1A_IW_GRDH_1SDV_YYYYMMDD...)
                parts = f.stem.split('_')
                if len(parts) >= 5:
                    date_str = parts[4][:8]
                    date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                    downloaded[date].append(f)

        if not downloaded:
            logger.warning("No downloaded files found")
            return {}

        cfg = self.config['preprocessing']
        gpt_path = cfg.get('snap_gpt_path', '/home/unika_sianturi/work/idmai/esa-snap/bin/gpt')
        graph_xml = cfg.get('graph_xml', 'sen1_preprocessing-gpt.xml')
        cache_size = cfg.get('cache_size', '8G')

        preprocessed = defaultdict(list)
        total = sum(len(v) for v in downloaded.values())
        current = 0

        for date in sorted(downloaded.keys()):
            for input_file in downloaded[date]:
                current += 1
                output_name = input_file.stem + '_processed'
                output_file = self.dirs['preprocessed'] / output_name

                # Check if already processed
                if (output_file.with_suffix('.dim')).exists():
                    logger.info(f"[{current}/{total}] Already processed: {output_name}")
                    preprocessed[date].append(output_file.with_suffix('.dim'))
                    continue

                logger.info(f"[{current}/{total}] Processing: {input_file.name}")

                # Build GPT command
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
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=3600  # 1 hour timeout
                    )

                    if result.returncode == 0 and output_file.with_suffix('.dim').exists():
                        logger.info(f"  ✓ Processed: {output_name}")
                        preprocessed[date].append(output_file.with_suffix('.dim'))
                    else:
                        logger.error(f"  ✗ Processing failed")
                        if result.stderr:
                            logger.error(f"  Error: {result.stderr[-500:]}")

                except subprocess.TimeoutExpired:
                    logger.error(f"  ✗ Processing timeout")
                except Exception as e:
                    logger.error(f"  ✗ Error: {e}")

        logger.info(f"\n✓ Preprocessed {sum(len(v) for v in preprocessed.values())} files")
        return preprocessed

    def step3_convert_to_geotiff(self, preprocessed: Optional[Dict[str, List[Path]]] = None) -> Dict[str, List[Path]]:
        """
        Convert preprocessed .dim files to GeoTIFF

        Args:
            preprocessed: Dictionary mapping dates to .dim files

        Returns:
            Dictionary mapping dates to GeoTIFF files
        """
        logger.info("\n" + "=" * 60)
        logger.info("STEP 3: CONVERT TO GEOTIFF")
        logger.info("=" * 60)

        import rasterio
        from rasterio.crs import CRS

        # Find preprocessed files if not provided
        if preprocessed is None:
            preprocessed = defaultdict(list)
            for f in sorted(self.dirs['preprocessed'].glob('*.dim')):
                # Extract date from filename
                parts = f.stem.split('_')
                if len(parts) >= 5:
                    date_str = parts[4][:8]
                    date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                    preprocessed[date].append(f)

        if not preprocessed:
            logger.warning("No preprocessed files found")
            return {}

        geotiffs = defaultdict(list)
        total = sum(len(v) for v in preprocessed.values())
        current = 0

        for date in sorted(preprocessed.keys()):
            for dim_file in preprocessed[date]:
                current += 1

                # Find the VH data file
                data_dir = dim_file.with_suffix('.data')
                vh_file = data_dir / 'Gamma0_VH_db.img'

                if not vh_file.exists():
                    logger.warning(f"[{current}/{total}] VH file not found: {vh_file}")
                    continue

                output_tif = self.dirs['geotiff'] / f"{dim_file.stem}_VH.tif"

                if output_tif.exists():
                    logger.info(f"[{current}/{total}] Already converted: {output_tif.name}")
                    geotiffs[date].append(output_tif)
                    continue

                logger.info(f"[{current}/{total}] Converting: {dim_file.name}")

                try:
                    with rasterio.open(vh_file) as src:
                        data = src.read(1)
                        profile = src.profile.copy()

                        # Update profile for GeoTIFF
                        profile.update(
                            driver='GTiff',
                            compress='lzw'
                        )
                        profile.pop('tiled', None)
                        profile.pop('blockxsize', None)
                        profile.pop('blockysize', None)

                        with rasterio.open(output_tif, 'w', **profile) as dst:
                            dst.write(data, 1)

                    logger.info(f"  ✓ Created: {output_tif.name}")
                    geotiffs[date].append(output_tif)

                except Exception as e:
                    logger.error(f"  ✗ Conversion failed: {e}")

        logger.info(f"\n✓ Converted {sum(len(v) for v in geotiffs.values())} files")
        return geotiffs

    def step4_mosaic_with_histogram_matching(self, geotiffs: Optional[Dict[str, List[Path]]] = None) -> List[Path]:
        """
        Mosaic scenes from the same date with histogram matching

        Args:
            geotiffs: Dictionary mapping dates to GeoTIFF files

        Returns:
            List of mosaic output files
        """
        logger.info("\n" + "=" * 60)
        logger.info("STEP 4: MOSAIC WITH HISTOGRAM MATCHING")
        logger.info("=" * 60)

        import rasterio
        from rasterio.merge import merge
        from rasterio.warp import calculate_default_transform, reproject, Resampling
        from rasterio.crs import CRS

        # Find GeoTIFF files if not provided
        if geotiffs is None:
            geotiffs = defaultdict(list)
            for f in sorted(self.dirs['geotiff'].glob('*_VH.tif')):
                # Extract date from filename
                parts = f.stem.split('_')
                if len(parts) >= 5:
                    date_str = parts[4][:8]
                    date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                    geotiffs[date].append(f)

        if not geotiffs:
            logger.warning("No GeoTIFF files found")
            return []

        mosaic_cfg = self.config.get('mosaicking', {})
        do_histogram_matching = mosaic_cfg.get('histogram_matching', True)
        reference_method = mosaic_cfg.get('reference_scene', 'center')

        mosaics = []

        for date in sorted(geotiffs.keys()):
            files = geotiffs[date]
            output_mosaic = self.dirs['mosaic'] / f"S1_mosaic_{date.replace('-', '')}_VH.tif"

            if output_mosaic.exists():
                logger.info(f"Already mosaicked: {date}")
                mosaics.append(output_mosaic)
                continue

            if len(files) == 1:
                # Single scene, just copy
                logger.info(f"Single scene for {date}, copying...")
                import shutil
                shutil.copy(files[0], output_mosaic)
                mosaics.append(output_mosaic)
                continue

            logger.info(f"\nMosaicking {len(files)} scenes for {date}")

            try:
                # Read all scenes
                datasets = []
                for f in files:
                    src = rasterio.open(f)
                    datasets.append(src)
                    logger.info(f"  Input: {f.name}, shape: {src.shape}")

                if do_histogram_matching and len(datasets) > 1:
                    logger.info("  Applying histogram matching...")

                    # Select reference scene
                    if reference_method == 'center':
                        # Use scene with center closest to AOI center
                        ref_idx = len(datasets) // 2
                    elif reference_method == 'largest':
                        # Use largest scene
                        ref_idx = max(range(len(datasets)),
                                     key=lambda i: datasets[i].width * datasets[i].height)
                    else:
                        ref_idx = 0

                    ref_data = datasets[ref_idx].read(1)
                    ref_valid = ~np.isnan(ref_data) & (ref_data > -100) & (ref_data < 50)
                    ref_mean = np.mean(ref_data[ref_valid])
                    ref_std = np.std(ref_data[ref_valid])

                    logger.info(f"  Reference scene [{ref_idx}]: mean={ref_mean:.2f}, std={ref_std:.2f}")

                    # Apply histogram matching to other scenes
                    matched_files = []
                    for i, (f, ds) in enumerate(zip(files, datasets)):
                        if i == ref_idx:
                            matched_files.append(f)
                            continue

                        data = ds.read(1)
                        valid = ~np.isnan(data) & (data > -100) & (data < 50)

                        if np.sum(valid) == 0:
                            matched_files.append(f)
                            continue

                        src_mean = np.mean(data[valid])
                        src_std = np.std(data[valid])

                        # Linear histogram matching
                        if src_std > 0:
                            matched_data = (data - src_mean) * (ref_std / src_std) + ref_mean
                        else:
                            matched_data = data - src_mean + ref_mean

                        logger.info(f"  Scene [{i}]: shifted by {ref_mean - src_mean:.2f} dB")

                        # Save matched data to temp file
                        matched_file = self.dirs['geotiff'] / f"{f.stem}_matched.tif"
                        profile = ds.profile.copy()
                        profile.update(driver='GTiff', compress='lzw')
                        profile.pop('tiled', None)
                        profile.pop('blockxsize', None)
                        profile.pop('blockysize', None)

                        with rasterio.open(matched_file, 'w', **profile) as dst:
                            dst.write(matched_data.astype(profile['dtype']), 1)

                        matched_files.append(matched_file)

                    # Close original datasets and open matched ones
                    for ds in datasets:
                        ds.close()

                    datasets = [rasterio.open(f) for f in matched_files]

                # Merge all scenes
                logger.info("  Merging scenes...")
                mosaic_data, mosaic_transform = merge(datasets)

                # Write output
                profile = datasets[0].profile.copy()
                profile.update(
                    driver='GTiff',
                    height=mosaic_data.shape[1],
                    width=mosaic_data.shape[2],
                    transform=mosaic_transform,
                    compress='lzw'
                )
                profile.pop('tiled', None)
                profile.pop('blockxsize', None)
                profile.pop('blockysize', None)

                with rasterio.open(output_mosaic, 'w', **profile) as dst:
                    dst.write(mosaic_data)

                logger.info(f"  ✓ Mosaic created: {output_mosaic.name}")
                logger.info(f"    Shape: {mosaic_data.shape[1]} x {mosaic_data.shape[2]}")
                mosaics.append(output_mosaic)

                # Close datasets
                for ds in datasets:
                    ds.close()

                # Clean up matched temp files
                if do_histogram_matching:
                    for f in self.dirs['geotiff'].glob('*_matched.tif'):
                        f.unlink()

            except Exception as e:
                logger.error(f"  ✗ Mosaic failed: {e}")
                import traceback
                traceback.print_exc()

        logger.info(f"\n✓ Created {len(mosaics)} mosaics")
        return mosaics

    def run_full_pipeline(self, skip_download: bool = False, skip_preprocess: bool = False,
                          skip_convert: bool = False):
        """Run complete pipeline"""
        logger.info("\n" + "=" * 70)
        logger.info("MULTI-SCENE SENTINEL-1 PIPELINE")
        logger.info("=" * 70)
        logger.info(f"Start time: {datetime.now()}")
        logger.info(f"Workspace: {self.work_dir}")

        start_time = datetime.now()

        # Step 1: Download
        if not skip_download:
            downloaded = self.step1_download()
        else:
            logger.info("\nSkipping download (using existing files)")
            downloaded = None

        # Step 2: Preprocess
        if not skip_preprocess:
            preprocessed = self.step2_preprocess(downloaded)
        else:
            logger.info("\nSkipping preprocessing (using existing files)")
            preprocessed = None

        # Step 3: Convert to GeoTIFF
        if not skip_convert:
            geotiffs = self.step3_convert_to_geotiff(preprocessed)
        else:
            logger.info("\nSkipping conversion (using existing files)")
            geotiffs = None

        # Step 4: Mosaic
        mosaics = self.step4_mosaic_with_histogram_matching(geotiffs)

        # Summary
        elapsed = datetime.now() - start_time
        logger.info("\n" + "=" * 70)
        logger.info("PIPELINE COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Total time: {elapsed}")
        logger.info(f"\nOutput mosaics in: {self.dirs['mosaic']}")
        for m in mosaics:
            logger.info(f"  {m.name}")

        return mosaics


def main():
    parser = argparse.ArgumentParser(
        description='Multi-Scene Sentinel-1 Pipeline with Mosaicking'
    )
    parser.add_argument('--config', default='pipeline_config_semarang_demak.yaml',
                        help='Pipeline configuration file')
    parser.add_argument('--run-all', action='store_true',
                        help='Run full pipeline')
    parser.add_argument('--download-only', action='store_true',
                        help='Only download data')
    parser.add_argument('--preprocess-only', action='store_true',
                        help='Only preprocess data')
    parser.add_argument('--convert-only', action='store_true',
                        help='Only convert to GeoTIFF')
    parser.add_argument('--mosaic-only', action='store_true',
                        help='Only mosaic existing GeoTIFFs')
    parser.add_argument('--skip-download', action='store_true',
                        help='Skip download step')
    parser.add_argument('--skip-preprocess', action='store_true',
                        help='Skip preprocessing step')
    parser.add_argument('--skip-convert', action='store_true',
                        help='Skip conversion step')

    args = parser.parse_args()

    # Check config exists
    if not Path(args.config).exists():
        logger.error(f"Configuration file not found: {args.config}")
        sys.exit(1)

    # Initialize pipeline
    pipeline = MultiScenePipeline(args.config)

    # Run requested steps
    if args.download_only:
        pipeline.step1_download()
    elif args.preprocess_only:
        pipeline.step2_preprocess()
    elif args.convert_only:
        pipeline.step3_convert_to_geotiff()
    elif args.mosaic_only:
        pipeline.step4_mosaic_with_histogram_matching()
    elif args.run_all:
        pipeline.run_full_pipeline(
            skip_download=args.skip_download,
            skip_preprocess=args.skip_preprocess,
            skip_convert=args.skip_convert
        )
    else:
        logger.error("Please specify an action: --run-all, --download-only, etc.")
        parser.print_help()


if __name__ == '__main__':
    main()
