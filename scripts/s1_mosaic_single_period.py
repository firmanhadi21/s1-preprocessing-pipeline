#!/usr/bin/env python3
"""
Mosaic a single 12-day period from preprocessed scenes

Simpler version of full mosaicking - processes one period at a time

Usage:
    python s1_mosaic_single_period.py \
        --input-dir workspace/preprocessed_15 \
        --output workspace/mosaics/period_15_mosaic.tif \
        --period 15 \
        --year 2024
"""

import os
import sys
import argparse
import subprocess
import logging
from pathlib import Path
from typing import List
from collections import defaultdict
import re
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import GDAL - but avoid gdal_array to prevent NumPy conflicts with OTB
try:
    from osgeo import gdal
    # Don't call UseExceptions() yet to avoid importing gdal_array
except ImportError:
    logger.error("GDAL not found. Install with: conda install gdal")
    sys.exit(1)


class SinglePeriodMosaicker:
    """Mosaic single period from multiple tracks"""

    # Java Island default extent (WGS84)
    JAVA_EXTENT = (105.0, -9.0, 116.0, -5.0)  # (minx, miny, maxx, maxy)

    def __init__(self, period: int, year: int = 2024, resolution: int = 50,
                 target_extent: tuple = None):
        self.period = period
        self.year = year
        self.resolution = resolution
        self.target_extent = target_extent or self.JAVA_EXTENT

        logger.info(f"Single Period Mosaicker - Period {period}, {year}")
        logger.info(f"Resolution: {resolution}m")
        logger.info(f"Target extent: {self.target_extent}")

    def mosaic_scenes(self, scene_files: List[Path], output_file: Path) -> bool:
        """
        Mosaic all scenes using Orfeo Toolbox (OTB)

        OTB provides better overlap handling with feathering and harmonization

        Args:
            scene_files: List of preprocessed GeoTIFF files
            output_file: Output mosaic file

        Returns:
            Success status
        """
        if not scene_files:
            logger.error("No input scenes provided")
            return False

        if len(scene_files) == 1:
            # Single scene - just copy
            logger.info("Single scene - copying directly")
            import shutil
            shutil.copy(scene_files[0], output_file)
            return True

        logger.info(f"Mosaicking {len(scene_files)} scenes with Orfeo Toolbox...")

        # Build OTB Mosaic command
        # Using large feathering for seamless blending in overlaps
        cmd = [
            'otbcli_Mosaic',
            '-il'
        ] + [str(f) for f in scene_files] + [
            '-out', str(output_file), 'float',
            '-comp.feather', 'large',           # Large feathering for smooth blending
            '-nodata', '-32768',                # Nodata value
            '-harmo.method', 'band',            # Band-wise harmonization
            '-harmo.cost', 'rmse',              # RMSE cost function
            '-tmpdir', str(output_file.parent / 'tmp')
        ]

        # Create temp directory
        tmp_dir = output_file.parent / 'tmp'
        tmp_dir.mkdir(parents=True, exist_ok=True)

        try:
            logger.info(f"Running OTB Mosaic with large feathering...")
            logger.info(f"  - Feathering: large (seamless blending)")
            logger.info(f"  - Harmonization: band-wise RMSE")

            # Set up OTB environment for this subprocess only
            otb_env = os.environ.copy()
            otb_profile = Path.home() / 'work' / 'OTB' / 'otbenv.profile'

            if otb_profile.exists():
                # Source OTB profile and get environment variables
                source_cmd = f'source {otb_profile} && env'
                env_result = subprocess.run(source_cmd, shell=True, executable='/bin/bash',
                                          capture_output=True, text=True)

                # Parse environment variables from sourced profile
                for line in env_result.stdout.split('\n'):
                    if '=' in line:
                        key, _, value = line.partition('=')
                        otb_env[key] = value

            result = subprocess.run(cmd, env=otb_env, check=True, capture_output=True, text=True)
            logger.info(f"✓ Mosaic created: {output_file}")

            # Clean up temp directory
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"OTB Mosaicking failed: {e.stderr}")
            logger.error(f"Make sure Orfeo Toolbox is installed: conda install -c conda-forge otb")
            return False


def main():
    parser = argparse.ArgumentParser(
        description='Mosaic single 12-day period',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--input-dir', required=True,
                       help='Directory with preprocessed scenes for this period')
    parser.add_argument('--output', required=True,
                       help='Output mosaic file (.tif)')
    parser.add_argument('--period', type=int, required=True,
                       help='Period number (1-31)')
    parser.add_argument('--year', type=int, default=2024,
                       help='Year (default: 2024)')
    parser.add_argument('--resolution', type=int, default=50,
                       help='Resolution in meters (default: 50)')
    parser.add_argument('--extent', nargs=4, type=float,
                       metavar=('MINX', 'MINY', 'MAXX', 'MAXY'),
                       help='Target extent in WGS84 (default: Java Island)')

    args = parser.parse_args()

    # Validate period
    if not 1 <= args.period <= 31:
        logger.error(f"Period must be 1-31, got {args.period}")
        sys.exit(1)

    # Initialize mosaicker
    mosaicker = SinglePeriodMosaicker(
        period=args.period,
        year=args.year,
        resolution=args.resolution,
        target_extent=tuple(args.extent) if args.extent else None
    )

    # Find input scenes
    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        logger.error(f"Input directory not found: {input_dir}")
        sys.exit(1)

    scene_files = sorted(input_dir.glob('*_VH_*.tif'))

    if not scene_files:
        logger.error(f"No preprocessed scenes found in {input_dir}")
        logger.info("Expected files: *_VH_50m.tif or similar")
        sys.exit(1)

    logger.info(f"Found {len(scene_files)} preprocessed scenes")

    # Create output directory
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Mosaic
    logger.info(f"\n{'='*70}")
    logger.info(f"MOSAICKING PERIOD {args.period}")
    logger.info(f"{'='*70}")

    success = mosaicker.mosaic_scenes(scene_files, output_path)

    if success:
        # Get mosaic info
        ds = gdal.Open(str(output_path))
        if ds:
            logger.info(f"\n{'='*70}")
            logger.info("MOSAIC INFO")
            logger.info(f"{'='*70}")
            logger.info(f"File: {output_path}")
            logger.info(f"Size: {ds.RasterXSize} x {ds.RasterYSize}")
            logger.info(f"Bands: {ds.RasterCount}")
            logger.info(f"File size: {output_path.stat().st_size / (1024**3):.2f} GB")

            # Get actual extent
            gt = ds.GetGeoTransform()
            minx = gt[0]
            maxy = gt[3]
            maxx = minx + gt[1] * ds.RasterXSize
            miny = maxy + gt[5] * ds.RasterYSize
            logger.info(f"Extent: ({minx:.2f}, {miny:.2f}, {maxx:.2f}, {maxy:.2f})")

            ds = None
            logger.info(f"{'='*70}")
            logger.info(f"✓ Period {args.period} mosaic complete!")
            logger.info(f"{'='*70}\n")

        sys.exit(0)
    else:
        logger.error(f"\n✗ Failed to create mosaic for period {args.period}")
        sys.exit(1)


if __name__ == '__main__':
    main()
