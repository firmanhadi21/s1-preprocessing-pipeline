#!/usr/bin/env python3
"""
Manual Period-Based Sentinel-1 Workflow

This script processes manually downloaded Sentinel-1 data organized by period:

Folder Structure:
    downloads_p1/       # Period 1 downloads (Jan 1-12)
    downloads_p2/       # Period 2 downloads (Jan 13-24)
    ...
    downloads_p31/      # Period 31 downloads (Dec 27-31)

Processing Steps:
    1. Preprocess each period's downloads with SNAP GPT
       → preprocessed_p1/, preprocessed_p2/, etc.

    2. Mosaic each period's preprocessed files into single seamless GeoTIFF
       → mosaics/mosaic_p1.tif, mosaic_p2.tif, etc.
       (Seamless, ignoring NULL values)

    3. Stack all period mosaics into final 31-band GeoTIFF
       → final_stack/S1_VH_stack_YYYY_31bands.tif

Usage:
    # Process single period
    python s1_manual_period_workflow.py --period 1 --preprocess
    python s1_manual_period_workflow.py --period 1 --mosaic

    # Process all periods at once
    python s1_manual_period_workflow.py --preprocess-all
    python s1_manual_period_workflow.py --mosaic-all

    # Stack all mosaics
    python s1_manual_period_workflow.py --stack

    # Full workflow for single period
    python s1_manual_period_workflow.py --period 15 --run-all

    # Full workflow for all periods
    python s1_manual_period_workflow.py --run-all
"""

import os
import sys
from pathlib import Path
import logging
import argparse
import subprocess
from typing import List, Optional
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ManualPeriodWorkflow:
    """
    Manual workflow for processing Sentinel-1 data by period
    """

    def __init__(self, work_dir: str = '.', year: Optional[int] = None,
                 snap_gpt_path: str = '/home/unika_sianturi/work/idmai/esa-snap/bin/gpt',
                 graph_xml: str = 'sen1_preprocessing-gpt.xml',
                 cache_size: str = '16G'):
        """
        Initialize manual workflow

        Args:
            work_dir: Working directory containing downloads_pX folders
            year: Year for output naming (optional)
            snap_gpt_path: Path to SNAP GPT executable
            graph_xml: SNAP processing graph XML file
            cache_size: SNAP cache size
        """
        self.work_dir = Path(work_dir)
        self.year = year
        self.snap_gpt_path = snap_gpt_path
        self.graph_xml = graph_xml
        self.cache_size = cache_size

        # Create output directories
        self.mosaics_dir = self.work_dir / 'mosaics'
        self.mosaics_dir.mkdir(parents=True, exist_ok=True)

        self.final_stack_dir = self.work_dir / 'final_stack'
        self.final_stack_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Manual Period Workflow")
        logger.info(f"Working directory: {self.work_dir}")
        if year:
            logger.info(f"Year: {year}")

    def _get_period_dirs(self, period: int) -> tuple:
        """Get directory paths for a period"""
        downloads_dir = self.work_dir / f"downloads_p{period}"
        preprocessed_dir = self.work_dir / f"preprocessed_p{period}"
        return downloads_dir, preprocessed_dir

    def preprocess_period(self, period: int) -> bool:
        """
        Preprocess all downloads for a specific period

        Args:
            period: Period number (1-31)

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"PREPROCESSING PERIOD {period}")
        logger.info(f"{'='*70}")

        downloads_dir, preprocessed_dir = self._get_period_dirs(period)

        # Check if downloads directory exists
        if not downloads_dir.exists():
            logger.error(f"Downloads directory not found: {downloads_dir}")
            logger.error(f"Please create {downloads_dir} and add Sentinel-1 ZIP files")
            return False

        # Get all ZIP files
        zip_files = sorted(downloads_dir.glob('*.zip'))
        if not zip_files:
            logger.warning(f"No ZIP files found in {downloads_dir}")
            return False

        logger.info(f"Found {len(zip_files)} ZIP files in {downloads_dir}")

        # Create preprocessed directory
        preprocessed_dir.mkdir(parents=True, exist_ok=True)

        # Process each file
        success_count = 0
        for i, zip_file in enumerate(zip_files, 1):
            output_name = zip_file.stem + '_processed'
            output_file = preprocessed_dir / output_name

            # Check if already processed
            if (output_file.with_suffix('.dim')).exists():
                logger.info(f"[{i}/{len(zip_files)}] Already processed: {output_name}")
                success_count += 1
                continue

            logger.info(f"[{i}/{len(zip_files)}] Processing: {zip_file.name}")

            # Build GPT command
            # Convert Path objects to absolute string paths
            zip_file_str = str(zip_file.absolute())
            output_file_str = str(output_file.absolute())

            cmd = [
                self.snap_gpt_path,
                self.graph_xml,
                f'-PmyFilename={zip_file_str}',
                f'-PoutputFile={output_file_str}',
                '-c', self.cache_size,
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
                    logger.info(f"  ✓ Processed successfully")
                    success_count += 1
                else:
                    logger.error(f"  ✗ Processing failed")
                    if result.stderr:
                        logger.error(f"  Error: {result.stderr[-500:]}")

            except subprocess.TimeoutExpired:
                logger.error(f"  ✗ Processing timeout (>1 hour)")
            except Exception as e:
                logger.error(f"  ✗ Error: {e}")

        logger.info(f"\nPeriod {period}: Processed {success_count}/{len(zip_files)} files")
        return success_count > 0

    def mosaic_period(self, period: int) -> bool:
        """
        Mosaic all preprocessed files for a period into seamless GeoTIFF

        Args:
            period: Period number (1-31)

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"MOSAICKING PERIOD {period}")
        logger.info(f"{'='*70}")

        downloads_dir, preprocessed_dir = self._get_period_dirs(period)

        # Check if preprocessed directory exists
        if not preprocessed_dir.exists():
            logger.error(f"Preprocessed directory not found: {preprocessed_dir}")
            logger.error(f"Run preprocessing first: --period {period} --preprocess")
            return False

        # Get all .dim files
        dim_files = sorted(preprocessed_dir.glob('*.dim'))
        if not dim_files:
            logger.warning(f"No preprocessed files found in {preprocessed_dir}")
            return False

        logger.info(f"Found {len(dim_files)} preprocessed files")

        # Output mosaic file
        output_mosaic = self.mosaics_dir / f"mosaic_p{period}.tif"

        if output_mosaic.exists():
            logger.info(f"Mosaic already exists: {output_mosaic.name}")
            return True

        # Convert .dim files to GeoTIFF first (VH band)
        try:
            import rasterio
        except ImportError:
            logger.error("rasterio not installed. Run: pip install rasterio")
            return False

        logger.info("Converting preprocessed files to GeoTIFF...")

        temp_geotiffs = []
        for i, dim_file in enumerate(dim_files, 1):
            # Find VH data file
            data_dir = dim_file.with_suffix('.data')
            vh_file = data_dir / 'Gamma0_VH_db.img'

            if not vh_file.exists():
                logger.warning(f"[{i}/{len(dim_files)}] VH file not found: {vh_file}")
                continue

            # Create temp GeoTIFF
            temp_tif = preprocessed_dir / f"{dim_file.stem}_VH.tif"

            if not temp_tif.exists():
                logger.info(f"[{i}/{len(dim_files)}] Converting: {dim_file.name}")
                try:
                    with rasterio.open(vh_file) as src:
                        data = src.read(1)
                        profile = src.profile.copy()

                        # Update profile for GeoTIFF
                        profile.update(
                            driver='GTiff',
                            compress='lzw',
                            tiled=True,
                            blockxsize=512,
                            blockysize=512
                        )

                        with rasterio.open(temp_tif, 'w', **profile) as dst:
                            dst.write(data, 1)

                    logger.info(f"  ✓ Converted")
                except Exception as e:
                    logger.error(f"  ✗ Conversion failed: {e}")
                    continue
            else:
                logger.info(f"[{i}/{len(dim_files)}] Already converted: {temp_tif.name}")

            temp_geotiffs.append(temp_tif)

        if not temp_geotiffs:
            logger.error("No GeoTIFF files available for mosaicking")
            return False

        # Mosaic GeoTIFFs using gdal_merge.py
        logger.info(f"\nMosaicking {len(temp_geotiffs)} files using gdal_merge.py...")

        if len(temp_geotiffs) == 1:
            # Single file - just copy
            logger.info("Single file, copying...")
            import shutil
            shutil.copy(temp_geotiffs[0], output_mosaic)
            logger.info(f"  ✓ Copied to: {output_mosaic.name}")
        else:
            # Multiple files - use gdal_merge.py with averaging in overlaps
            try:
                logger.info(f"Merging {len(temp_geotiffs)} files with gdal_merge.py...")
                logger.info("  Overlaps will be averaged (seamless blending)")

                # Build gdal_merge.py command
                cmd = [
                    'gdal_merge.py',
                    '-ot', 'Int16',
                    '-of', 'GTiff',
                    '-co', 'COMPRESS=LZW',
                    '-co', 'TILED=YES',
                    '-co', 'BIGTIFF=YES',
                    '-a_nodata', '-32768',
                    '-n', '-32768',  # Input nodata
                    '-init', '-32768',  # Initialize with nodata
                    '-o', str(output_mosaic)
                ]

                # Add all input files
                cmd.extend([str(f) for f in temp_geotiffs])

                # Run gdal_merge.py
                result = subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True
                )

                logger.info(f"  ✓ Mosaic created: {output_mosaic.name}")

            except subprocess.CalledProcessError as e:
                logger.error(f"  ✗ gdal_merge.py failed: {e.stderr}")
                return False
            except Exception as e:
                logger.error(f"  ✗ Mosaicking failed: {e}")
                import traceback
                traceback.print_exc()
                return False

        # Verify mosaic
        try:
            with rasterio.open(output_mosaic) as src:
                logger.info(f"\nMosaic verification:")
                logger.info(f"  File: {output_mosaic.name}")
                logger.info(f"  Size: {output_mosaic.stat().st_size / 1e6:.1f} MB")
                logger.info(f"  Shape: {src.height} x {src.width}")
                logger.info(f"  CRS: {src.crs}")
                logger.info(f"  Bounds: {src.bounds}")
        except Exception as e:
            logger.error(f"Could not verify mosaic: {e}")

        return True

    def stack_all_mosaics(self) -> Optional[Path]:
        """
        Stack all period mosaics into final 31-band GeoTIFF

        Returns:
            Path to final stack, or None if failed
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"STACKING ALL PERIOD MOSAICS")
        logger.info(f"{'='*70}")

        try:
            import rasterio
            from rasterio.warp import calculate_default_transform, reproject, Resampling
        except ImportError:
            logger.error("rasterio not installed. Run: pip install rasterio")
            return None

        # Find all period mosaics
        mosaic_files = {}
        for period in range(1, 32):
            mosaic_file = self.mosaics_dir / f"mosaic_p{period}.tif"
            if mosaic_file.exists():
                mosaic_files[period] = mosaic_file

        if not mosaic_files:
            logger.error(f"No mosaic files found in {self.mosaics_dir}")
            logger.error("Run mosaicking first: --mosaic-all")
            return None

        logger.info(f"Found {len(mosaic_files)} period mosaics:")
        for period in sorted(mosaic_files.keys()):
            logger.info(f"  Period {period}: {mosaic_files[period].name}")

        # Check for missing periods
        all_periods = set(range(1, 32))
        available_periods = set(mosaic_files.keys())
        missing_periods = all_periods - available_periods

        if missing_periods:
            logger.warning(f"\nMissing periods: {sorted(missing_periods)}")
            logger.warning("These will be filled with nodata values")

        # Get reference grid from first available period
        first_period = min(mosaic_files.keys())
        with rasterio.open(mosaic_files[first_period]) as src:
            profile = src.profile.copy()
            ref_crs = src.crs
            ref_transform = src.transform
            ref_bounds = src.bounds
            ref_shape = (src.height, src.width)
            ref_nodata = src.nodata or -9999

        logger.info(f"\nReference grid from period {first_period}:")
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
            BIGTIFF='YES',
            nodata=ref_nodata
        )

        # Output filename
        year_str = f"_{self.year}" if self.year else ""
        output_stack = self.final_stack_dir / f"S1_VH_stack{year_str}_31bands.tif"

        logger.info(f"\nCreating final stack: {output_stack.name}")

        with rasterio.open(output_stack, 'w', **profile) as dst:
            for period in range(1, 32):
                if period in mosaic_files:
                    logger.info(f"  Band {period}: Period {period}")

                    with rasterio.open(mosaic_files[period]) as src:
                        # Check if reprojection needed
                        if (src.crs != ref_crs or
                            src.transform != ref_transform or
                            src.shape != ref_shape):
                            logger.info(f"    Reprojecting to common grid...")
                            data = np.empty(ref_shape, dtype='float32')
                            reproject(
                                source=rasterio.band(src, 1),
                                destination=data,
                                src_transform=src.transform,
                                src_crs=src.crs,
                                dst_transform=ref_transform,
                                dst_crs=ref_crs,
                                resampling=Resampling.bilinear,
                                src_nodata=src.nodata,
                                dst_nodata=ref_nodata
                            )
                        else:
                            data = src.read(1)

                        dst.write(data.astype('float32'), period)
                else:
                    logger.warning(f"  Band {period}: MISSING - writing nodata")
                    nodata_band = np.full(ref_shape, ref_nodata, dtype='float32')
                    dst.write(nodata_band, period)

        logger.info(f"\n✓ Final stack created: {output_stack}")

        # Print statistics
        file_size_gb = output_stack.stat().st_size / 1e9
        logger.info(f"  Size: {file_size_gb:.2f} GB")
        logger.info(f"  Bands: 31")
        logger.info(f"  Shape: {ref_shape}")
        logger.info(f"  Available periods: {len(mosaic_files)}/31")
        logger.info(f"  Ready for training/prediction!")

        return output_stack


def main():
    parser = argparse.ArgumentParser(
        description='Manual Period-Based Sentinel-1 Workflow',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preprocess single period
  python s1_manual_period_workflow.py --period 1 --preprocess

  # Mosaic single period
  python s1_manual_period_workflow.py --period 1 --mosaic

  # Process single period (preprocess + mosaic)
  python s1_manual_period_workflow.py --period 15 --run-all

  # Preprocess all periods
  python s1_manual_period_workflow.py --preprocess-all

  # Mosaic all periods
  python s1_manual_period_workflow.py --mosaic-all

  # Stack all mosaics
  python s1_manual_period_workflow.py --stack

  # Full workflow (preprocess all + mosaic all + stack)
  python s1_manual_period_workflow.py --run-all
        """
    )

    parser.add_argument('--work-dir', default='.',
                        help='Working directory (default: current directory)')
    parser.add_argument('--year', type=int,
                        help='Year for output naming (optional)')
    parser.add_argument('--snap-gpt-path',
                        default='/home/unika_sianturi/work/idmai/esa-snap/bin/gpt',
                        help='Path to SNAP GPT executable')
    parser.add_argument('--graph-xml', default='sen1_preprocessing-gpt.xml',
                        help='SNAP processing graph XML file')
    parser.add_argument('--cache-size', default='16G',
                        help='SNAP cache size (default: 16G)')

    # Actions
    parser.add_argument('--period', type=int,
                        help='Period number to process (1-31)')
    parser.add_argument('--preprocess', action='store_true',
                        help='Preprocess downloads for specified period')
    parser.add_argument('--mosaic', action='store_true',
                        help='Mosaic preprocessed files for specified period')
    parser.add_argument('--preprocess-all', action='store_true',
                        help='Preprocess all periods (1-31)')
    parser.add_argument('--mosaic-all', action='store_true',
                        help='Mosaic all periods (1-31)')
    parser.add_argument('--stack', action='store_true',
                        help='Stack all period mosaics into 31-band GeoTIFF')
    parser.add_argument('--run-all', action='store_true',
                        help='Run full workflow for period or all periods')

    args = parser.parse_args()

    # Initialize workflow
    workflow = ManualPeriodWorkflow(
        work_dir=args.work_dir,
        year=args.year,
        snap_gpt_path=args.snap_gpt_path,
        graph_xml=args.graph_xml,
        cache_size=args.cache_size
    )

    # Execute requested actions
    if args.period and args.preprocess:
        # Preprocess single period
        workflow.preprocess_period(args.period)

    elif args.period and args.mosaic:
        # Mosaic single period
        workflow.mosaic_period(args.period)

    elif args.period and args.run_all:
        # Full workflow for single period
        logger.info(f"\nRunning full workflow for period {args.period}")
        if workflow.preprocess_period(args.period):
            workflow.mosaic_period(args.period)

    elif args.preprocess_all:
        # Preprocess all periods
        logger.info("\nPreprocessing all periods (1-31)")
        for period in range(1, 32):
            workflow.preprocess_period(period)

    elif args.mosaic_all:
        # Mosaic all periods
        logger.info("\nMosaicking all periods (1-31)")
        for period in range(1, 32):
            workflow.mosaic_period(period)

    elif args.stack:
        # Stack all mosaics
        workflow.stack_all_mosaics()

    elif args.run_all:
        # Full workflow for all periods
        logger.info("\nRunning full workflow for all periods")
        logger.info("Step 1: Preprocessing all periods")
        for period in range(1, 32):
            workflow.preprocess_period(period)

        logger.info("\nStep 2: Mosaicking all periods")
        for period in range(1, 32):
            workflow.mosaic_period(period)

        logger.info("\nStep 3: Stacking all mosaics")
        workflow.stack_all_mosaics()

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
