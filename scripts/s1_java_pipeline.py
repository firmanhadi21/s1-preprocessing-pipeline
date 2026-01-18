#!/usr/bin/env python3
"""
Java Island Sentinel-1 Pipeline with Sequential Mosaicking

This script handles large-area mosaicking with step-by-step histogram matching:
1. Download multiple Sentinel-1 scenes from ASF
2. Preprocess each scene with SNAP GPT (Gamma0 in dB)
3. Convert to GeoTIFF
4. Sequential mosaicking from west to east (or east to west) with histogram matching

The sequential approach ensures consistent radiometry across the entire mosaic
by matching each new scene to the growing mosaic.

Usage:
    python s1_java_pipeline.py --config pipeline_config_java.yaml --run-all
    python s1_java_pipeline.py --config pipeline_config_java.yaml --download-only
    python s1_java_pipeline.py --config pipeline_config_java.yaml --mosaic-only --direction west_to_east
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
import tempfile
import shutil

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class JavaIslandPipeline:
    """
    Pipeline for processing Java Island Sentinel-1 data with sequential mosaicking
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
            'mosaic': self.work_dir / 'mosaic',
            'temp': self.work_dir / 'temp'
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

    def step1_download(self) -> List[Path]:
        """Download Sentinel-1 scenes from ASF"""
        logger.info("\n" + "=" * 60)
        logger.info("STEP 1: DOWNLOAD SENTINEL-1 DATA FROM ASF")
        logger.info("=" * 60)

        try:
            import asf_search as asf
            from shapely.geometry import shape
        except ImportError:
            logger.error("Required packages not installed. Run: pip install asf-search shapely")
            return []

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
            maxResults=200
        )

        logger.info(f"Found {len(results)} products")

        if len(results) == 0:
            logger.warning("No products found")
            return []

        # Download all products
        downloaded = []
        total = len(results)

        for i, result in enumerate(results, 1):
            filename = result.properties['fileID'] + '.zip'
            filepath = self.dirs['downloads'] / filename

            if filepath.exists():
                logger.info(f"[{i}/{total}] Already exists: {filename}")
                downloaded.append(filepath)
                continue

            logger.info(f"[{i}/{total}] Downloading: {filename}")
            try:
                result.download(path=str(self.dirs['downloads']))
                downloaded.append(filepath)
                logger.info(f"  ✓ Downloaded")
            except Exception as e:
                logger.error(f"  ✗ Download failed: {e}")

        logger.info(f"\n✓ Downloaded {len(downloaded)} files")
        return downloaded

    def step2_preprocess(self, downloaded: Optional[List[Path]] = None) -> List[Path]:
        """Preprocess all scenes with SNAP GPT"""
        logger.info("\n" + "=" * 60)
        logger.info("STEP 2: PREPROCESS WITH SNAP GPT")
        logger.info("=" * 60)

        # Find downloaded files if not provided
        if downloaded is None:
            downloaded = sorted(self.dirs['downloads'].glob('*.zip'))

        if not downloaded:
            logger.warning("No downloaded files found")
            return []

        cfg = self.config['preprocessing']
        gpt_path = cfg.get('snap_gpt_path', '/home/unika_sianturi/work/idmai/esa-snap/bin/gpt')
        graph_xml = cfg.get('graph_xml', 'sen1_preprocessing-gpt.xml')
        cache_size = cfg.get('cache_size', '8G')

        preprocessed = []
        total = len(downloaded)

        for i, input_file in enumerate(downloaded, 1):
            output_name = input_file.stem + '_processed'
            output_file = self.dirs['preprocessed'] / output_name

            # Check if already processed
            if (output_file.with_suffix('.dim')).exists():
                logger.info(f"[{i}/{total}] Already processed: {output_name}")
                preprocessed.append(output_file.with_suffix('.dim'))
                continue

            logger.info(f"[{i}/{total}] Processing: {input_file.name}")

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

            except subprocess.TimeoutExpired:
                logger.error(f"  ✗ Processing timeout")
            except Exception as e:
                logger.error(f"  ✗ Error: {e}")

        logger.info(f"\n✓ Preprocessed {len(preprocessed)} files")
        return preprocessed

    def step3_convert_to_geotiff(self, preprocessed: Optional[List[Path]] = None) -> List[Path]:
        """Convert preprocessed .dim files to GeoTIFF"""
        logger.info("\n" + "=" * 60)
        logger.info("STEP 3: CONVERT TO GEOTIFF")
        logger.info("=" * 60)

        import rasterio

        # Find preprocessed files if not provided
        if preprocessed is None:
            preprocessed = sorted(self.dirs['preprocessed'].glob('*.dim'))

        if not preprocessed:
            logger.warning("No preprocessed files found")
            return []

        geotiffs = []
        total = len(preprocessed)

        for i, dim_file in enumerate(preprocessed, 1):
            # Find the VH data file
            data_dir = dim_file.with_suffix('.data')
            vh_file = data_dir / 'Gamma0_VH_db.img'

            if not vh_file.exists():
                logger.warning(f"[{i}/{total}] VH file not found: {vh_file}")
                continue

            output_tif = self.dirs['geotiff'] / f"{dim_file.stem}_VH.tif"

            if output_tif.exists():
                logger.info(f"[{i}/{total}] Already converted: {output_tif.name}")
                geotiffs.append(output_tif)
                continue

            logger.info(f"[{i}/{total}] Converting: {dim_file.name}")

            try:
                with rasterio.open(vh_file) as src:
                    data = src.read(1)
                    profile = src.profile.copy()

                    profile.update(driver='GTiff', compress='lzw')
                    profile.pop('tiled', None)
                    profile.pop('blockxsize', None)
                    profile.pop('blockysize', None)

                    with rasterio.open(output_tif, 'w', **profile) as dst:
                        dst.write(data, 1)

                logger.info(f"  ✓ Created: {output_tif.name}")
                geotiffs.append(output_tif)

            except Exception as e:
                logger.error(f"  ✗ Conversion failed: {e}")

        logger.info(f"\n✓ Converted {len(geotiffs)} files")
        return geotiffs

    def _get_scene_center_lon(self, tif_file: Path) -> float:
        """Get the center longitude of a GeoTIFF file"""
        import rasterio
        with rasterio.open(tif_file) as src:
            bounds = src.bounds
            return (bounds.left + bounds.right) / 2

    def _histogram_match_to_reference(self, src_data: np.ndarray, ref_data: np.ndarray,
                                       nodata_value: float = -999) -> np.ndarray:
        """
        Apply histogram matching to match source to reference

        Uses linear matching based on mean and std in overlap region
        """
        # Create valid masks
        src_valid = ~np.isnan(src_data) & (src_data > -100) & (src_data < 50)
        ref_valid = ~np.isnan(ref_data) & (ref_data > -100) & (ref_data < 50)

        # Find overlap region (both valid)
        overlap = src_valid & ref_valid

        if np.sum(overlap) < 1000:
            logger.warning("  Insufficient overlap for histogram matching")
            return src_data

        # Calculate statistics in overlap region
        src_mean = np.mean(src_data[overlap])
        src_std = np.std(src_data[overlap])
        ref_mean = np.mean(ref_data[overlap])
        ref_std = np.std(ref_data[overlap])

        logger.info(f"    Overlap pixels: {np.sum(overlap):,}")
        logger.info(f"    Source: mean={src_mean:.2f}, std={src_std:.2f}")
        logger.info(f"    Reference: mean={ref_mean:.2f}, std={ref_std:.2f}")

        # Apply linear transformation
        if src_std > 0.1:
            matched = (src_data - src_mean) * (ref_std / src_std) + ref_mean
        else:
            matched = src_data - src_mean + ref_mean

        shift = ref_mean - src_mean
        logger.info(f"    Applied shift: {shift:.2f} dB")

        return matched

    def step4_sequential_mosaic(self, geotiffs: Optional[List[Path]] = None,
                                 direction: str = 'west_to_east') -> Path:
        """
        Create sequential mosaic with histogram matching

        Args:
            geotiffs: List of GeoTIFF files to mosaic
            direction: 'west_to_east' or 'east_to_west'

        Returns:
            Path to final mosaic
        """
        logger.info("\n" + "=" * 60)
        logger.info("STEP 4: SEQUENTIAL MOSAIC WITH HISTOGRAM MATCHING")
        logger.info("=" * 60)

        import rasterio
        from rasterio.merge import merge
        from rasterio.warp import calculate_default_transform, reproject, Resampling
        from rasterio import Affine

        # Find GeoTIFF files if not provided
        if geotiffs is None:
            geotiffs = sorted(self.dirs['geotiff'].glob('*_VH.tif'))

        if not geotiffs:
            logger.warning("No GeoTIFF files found")
            return None

        # Filter out invalid files (all zeros)
        valid_geotiffs = []
        for f in geotiffs:
            with rasterio.open(f) as src:
                data = src.read(1, masked=True)
                valid = ~np.isnan(data) & (data > -100) & (data < 50)
                if np.sum(valid) > 10000:
                    valid_geotiffs.append(f)
                else:
                    logger.warning(f"Skipping invalid file: {f.name}")

        geotiffs = valid_geotiffs
        logger.info(f"Valid scenes for mosaicking: {len(geotiffs)}")

        # Sort by center longitude
        geotiffs_with_lon = [(f, self._get_scene_center_lon(f)) for f in geotiffs]

        if direction == 'west_to_east':
            geotiffs_with_lon.sort(key=lambda x: x[1])  # Sort by lon ascending
            logger.info("Direction: West to East")
        else:
            geotiffs_with_lon.sort(key=lambda x: x[1], reverse=True)  # Sort by lon descending
            logger.info("Direction: East to West")

        logger.info("\nScene order:")
        for i, (f, lon) in enumerate(geotiffs_with_lon, 1):
            logger.info(f"  {i}. {f.name} (lon={lon:.2f})")

        # Start with the first scene
        current_mosaic = geotiffs_with_lon[0][0]
        logger.info(f"\nStarting with: {current_mosaic.name}")

        # Process remaining scenes one by one
        for i, (next_scene, next_lon) in enumerate(geotiffs_with_lon[1:], 2):
            logger.info(f"\n[{i}/{len(geotiffs_with_lon)}] Adding: {next_scene.name} (lon={next_lon:.2f})")

            # Create temporary output for this step
            temp_output = self.dirs['temp'] / f"mosaic_step_{i:02d}.tif"

            try:
                # Open current mosaic and next scene
                with rasterio.open(current_mosaic) as mosaic_src:
                    mosaic_data = mosaic_src.read(1)
                    mosaic_profile = mosaic_src.profile.copy()
                    mosaic_bounds = mosaic_src.bounds
                    mosaic_transform = mosaic_src.transform
                    mosaic_crs = mosaic_src.crs

                with rasterio.open(next_scene) as scene_src:
                    scene_data = scene_src.read(1)
                    scene_profile = scene_src.profile.copy()
                    scene_bounds = scene_src.bounds
                    scene_transform = scene_src.transform

                # Check for overlap
                overlap_left = max(mosaic_bounds.left, scene_bounds.left)
                overlap_right = min(mosaic_bounds.right, scene_bounds.right)

                has_overlap = overlap_right > overlap_left

                if has_overlap:
                    logger.info(f"  Overlap region: {overlap_left:.3f} to {overlap_right:.3f} E")

                    # Create overlap arrays for histogram matching
                    # Resample scene to mosaic grid in overlap region
                    overlap_width = int((overlap_right - overlap_left) / abs(mosaic_transform.a))

                    if overlap_width > 100:
                        logger.info("  Applying histogram matching...")

                        # Get overlap data from both images
                        # For mosaic
                        mosaic_col_start = int((overlap_left - mosaic_bounds.left) / abs(mosaic_transform.a))
                        mosaic_col_end = int((overlap_right - mosaic_bounds.left) / abs(mosaic_transform.a))
                        mosaic_overlap = mosaic_data[:, mosaic_col_start:mosaic_col_end]

                        # For scene
                        scene_col_start = int((overlap_left - scene_bounds.left) / abs(scene_transform.a))
                        scene_col_end = int((overlap_right - scene_bounds.left) / abs(scene_transform.a))
                        scene_overlap = scene_data[:, scene_col_start:scene_col_end]

                        # Match histograms
                        # Calculate adjustment based on overlap statistics
                        mosaic_valid = ~np.isnan(mosaic_overlap) & (mosaic_overlap > -100) & (mosaic_overlap < 50)
                        scene_valid = ~np.isnan(scene_overlap) & (scene_overlap > -100) & (scene_overlap < 50)

                        if np.sum(mosaic_valid) > 1000 and np.sum(scene_valid) > 1000:
                            mosaic_mean = np.mean(mosaic_overlap[mosaic_valid])
                            scene_mean = np.mean(scene_overlap[scene_valid])

                            shift = mosaic_mean - scene_mean
                            logger.info(f"    Mosaic mean: {mosaic_mean:.2f} dB")
                            logger.info(f"    Scene mean: {scene_mean:.2f} dB")
                            logger.info(f"    Applied shift: {shift:.2f} dB")

                            # Apply shift to entire scene
                            scene_data = scene_data + shift
                else:
                    logger.info("  No overlap detected, merging without histogram matching")

                # Save adjusted scene to temp file
                adjusted_scene = self.dirs['temp'] / f"adjusted_{next_scene.name}"
                scene_profile.update(
                    driver='GTiff',
                    compress='lzw',
                    BIGTIFF='IF_SAFER',
                    tiled=True,
                    blockxsize=512,
                    blockysize=512
                )

                with rasterio.open(adjusted_scene, 'w', **scene_profile) as dst:
                    dst.write(scene_data, 1)

                # Merge current mosaic with adjusted scene
                logger.info("  Merging...")
                datasets = [rasterio.open(current_mosaic), rasterio.open(adjusted_scene)]

                merged_data, merged_transform = merge(datasets)

                for ds in datasets:
                    ds.close()

                # Write merged result
                merged_profile = mosaic_profile.copy()
                merged_profile.update(
                    height=merged_data.shape[1],
                    width=merged_data.shape[2],
                    transform=merged_transform,
                    driver='GTiff',
                    compress='lzw',
                    BIGTIFF='YES',
                    tiled=True,
                    blockxsize=512,
                    blockysize=512
                )

                with rasterio.open(temp_output, 'w', **merged_profile) as dst:
                    dst.write(merged_data)

                logger.info(f"  ✓ Mosaic shape: {merged_data.shape[1]} x {merged_data.shape[2]}")

                # Update current mosaic for next iteration
                current_mosaic = temp_output

                # Clean up adjusted scene
                if adjusted_scene.exists():
                    adjusted_scene.unlink()

            except Exception as e:
                logger.error(f"  ✗ Error: {e}")
                import traceback
                traceback.print_exc()
                continue

        # Copy final mosaic to output directory
        final_output = self.dirs['mosaic'] / f"S1_Java_mosaic_{direction}.tif"
        shutil.copy(current_mosaic, final_output)

        # Clean up temp files
        for f in self.dirs['temp'].glob('mosaic_step_*.tif'):
            f.unlink()

        logger.info(f"\n✓ Final mosaic created: {final_output}")

        # Print summary
        with rasterio.open(final_output) as src:
            logger.info(f"  Size: {final_output.stat().st_size / 1e9:.2f} GB")
            logger.info(f"  Shape: {src.height} x {src.width}")
            logger.info(f"  Bounds: {src.bounds.left:.3f} to {src.bounds.right:.3f} E")
            logger.info(f"          {src.bounds.bottom:.3f} to {src.bounds.top:.3f} S")

        return final_output

    def run_full_pipeline(self, skip_download: bool = False, skip_preprocess: bool = False,
                          skip_convert: bool = False, direction: str = 'west_to_east'):
        """Run complete pipeline"""
        logger.info("\n" + "=" * 70)
        logger.info("JAVA ISLAND SENTINEL-1 PIPELINE")
        logger.info("=" * 70)
        logger.info(f"Start time: {datetime.now()}")
        logger.info(f"Workspace: {self.work_dir}")

        start_time = datetime.now()

        # Step 1: Download
        if not skip_download:
            downloaded = self.step1_download()
        else:
            logger.info("\nSkipping download")
            downloaded = None

        # Step 2: Preprocess
        if not skip_preprocess:
            preprocessed = self.step2_preprocess(downloaded)
        else:
            logger.info("\nSkipping preprocessing")
            preprocessed = None

        # Step 3: Convert to GeoTIFF
        if not skip_convert:
            geotiffs = self.step3_convert_to_geotiff(preprocessed)
        else:
            logger.info("\nSkipping conversion")
            geotiffs = None

        # Step 4: Sequential Mosaic
        final_mosaic = self.step4_sequential_mosaic(geotiffs, direction=direction)

        # Summary
        elapsed = datetime.now() - start_time
        logger.info("\n" + "=" * 70)
        logger.info("PIPELINE COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Total time: {elapsed}")
        logger.info(f"Final mosaic: {final_mosaic}")

        return final_mosaic


def main():
    parser = argparse.ArgumentParser(
        description='Java Island Sentinel-1 Pipeline with Sequential Mosaicking'
    )
    parser.add_argument('--config', default='pipeline_config_java.yaml',
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
                        help='Only create mosaic from existing GeoTIFFs')
    parser.add_argument('--skip-download', action='store_true',
                        help='Skip download step')
    parser.add_argument('--skip-preprocess', action='store_true',
                        help='Skip preprocessing step')
    parser.add_argument('--skip-convert', action='store_true',
                        help='Skip conversion step')
    parser.add_argument('--direction', choices=['west_to_east', 'east_to_west'],
                        default='west_to_east',
                        help='Mosaic direction (default: west_to_east)')

    args = parser.parse_args()

    if not Path(args.config).exists():
        logger.error(f"Configuration file not found: {args.config}")
        sys.exit(1)

    pipeline = JavaIslandPipeline(args.config)

    if args.download_only:
        pipeline.step1_download()
    elif args.preprocess_only:
        pipeline.step2_preprocess()
    elif args.convert_only:
        pipeline.step3_convert_to_geotiff()
    elif args.mosaic_only:
        pipeline.step4_sequential_mosaic(direction=args.direction)
    elif args.run_all:
        pipeline.run_full_pipeline(
            skip_download=args.skip_download,
            skip_preprocess=args.skip_preprocess,
            skip_convert=args.skip_convert,
            direction=args.direction
        )
    else:
        logger.error("Please specify an action: --run-all, --download-only, etc.")
        parser.print_help()


if __name__ == '__main__':
    main()
