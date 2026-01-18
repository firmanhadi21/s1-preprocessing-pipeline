#!/usr/bin/env python3
"""
GDAL-based mosaicking with averaging in overlaps

This uses gdal_merge.py which averages overlapping areas, providing
seamless blending without harmonization artifacts.

Usage:
    python s1_mosaic_gdal.py \
        --input-dir workspace/preprocessed_20m/p6 \
        --output workspace/mosaics_20m/period_06_mosaic_gdal.tif
"""

import os
import sys
import argparse
import subprocess
import logging
from pathlib import Path
from typing import List
from osgeo import gdal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

gdal.UseExceptions()


class GDALMosaicker:
    """GDAL-based mosaicking with averaging"""

    def __init__(self, nodata: float = -32768):
        self.nodata = nodata
        logger.info("GDAL Mosaicker")
        logger.info("  Method: Average in overlaps")
        logger.info(f"  NoData: {nodata}")

    def mosaic_with_gdal_merge(self, scene_files: List[Path], output_file: Path) -> bool:
        """
        Mosaic using gdal_merge.py with averaging

        Args:
            scene_files: List of input scene files
            output_file: Output mosaic file

        Returns:
            Success status
        """
        if not scene_files:
            logger.error("No scene files provided")
            return False

        if len(scene_files) == 1:
            logger.info("Single scene - copying")
            import shutil
            shutil.copy(scene_files[0], output_file)
            return True

        logger.info(f"Mosaicking {len(scene_files)} scenes with gdal_merge.py...")
        logger.info("  Overlaps will be averaged (seamless blending)")

        # Build gdal_merge.py command
        cmd = [
            'gdal_merge.py',
            '-o', str(output_file),
            '-of', 'GTiff',
            '-co', 'COMPRESS=LZW',
            '-co', 'TILED=YES',
            '-co', 'BIGTIFF=YES',
            '-co', 'NUM_THREADS=ALL_CPUS',
            '-a_nodata', str(self.nodata),
            '-n', str(self.nodata),  # Input nodata
            '-init', str(self.nodata),  # Initialize with nodata
            '-ot', 'Float32'
        ]

        # Add all input files
        cmd.extend([str(f) for f in scene_files])

        try:
            logger.info("Running gdal_merge.py...")
            logger.info(f"  This may take 5-10 minutes for {len(scene_files)} scenes...")

            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )

            logger.info("✓ Mosaic created successfully")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"gdal_merge.py failed: {e.stderr}")
            return False

    def mosaic_with_vrt(self, scene_files: List[Path], output_file: Path) -> bool:
        """
        Create mosaic using VRT (Virtual Raster)

        This is very fast but doesn't average overlaps - first scene wins.
        Good for quick preview.

        Args:
            scene_files: List of input scene files
            output_file: Output VRT file (will be converted to GeoTIFF)

        Returns:
            Success status
        """
        if not scene_files:
            logger.error("No scene files")
            return False

        logger.info(f"Creating VRT mosaic for {len(scene_files)} scenes...")

        # Create VRT
        vrt_file = output_file.with_suffix('.vrt')

        vrt_options = gdal.BuildVRTOptions(
            resolution='average',
            addAlpha=False,
            srcNodata=self.nodata,
            VRTNodata=self.nodata
        )

        vrt_ds = gdal.BuildVRT(
            str(vrt_file),
            [str(f) for f in scene_files],
            options=vrt_options
        )

        if not vrt_ds:
            logger.error("Failed to create VRT")
            return False

        vrt_ds = None

        logger.info(f"✓ VRT created: {vrt_file}")

        # Convert VRT to GeoTIFF if output is .tif
        if output_file.suffix.lower() in ['.tif', '.tiff']:
            logger.info("Converting VRT to GeoTIFF...")

            translate_options = gdal.TranslateOptions(
                format='GTiff',
                creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES', 'NUM_THREADS=ALL_CPUS']
            )

            ds = gdal.Translate(
                str(output_file),
                str(vrt_file),
                options=translate_options
            )

            if ds:
                ds = None
                logger.info(f"✓ GeoTIFF created: {output_file}")
                # Remove VRT
                vrt_file.unlink()
                return True
            else:
                logger.error("Failed to convert VRT to GeoTIFF")
                return False
        else:
            return True


def main():
    parser = argparse.ArgumentParser(
        description='GDAL-based mosaicking',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Standard mosaic with averaging (recommended)
  python s1_mosaic_gdal.py \\
      --input-dir workspace/preprocessed_20m/p6 \\
      --output workspace/mosaics_20m/period_06_mosaic_gdal.tif

  # Quick VRT mosaic (no averaging, fast preview)
  python s1_mosaic_gdal.py \\
      --input-dir workspace/preprocessed_20m/p6 \\
      --output workspace/mosaics_20m/period_06_mosaic.vrt \\
      --method vrt
        """
    )

    parser.add_argument('--input-dir', required=True,
                       help='Directory with preprocessed scenes')
    parser.add_argument('--output', required=True,
                       help='Output mosaic file (.tif or .vrt)')
    parser.add_argument('--method', default='merge',
                       choices=['merge', 'vrt'],
                       help='Mosaicking method (default: merge with averaging)')
    parser.add_argument('--nodata', type=float, default=-32768,
                       help='NoData value (default: -32768)')

    args = parser.parse_args()

    # Find input scenes
    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        logger.error(f"Input directory not found: {input_dir}")
        sys.exit(1)

    scene_files = sorted(input_dir.glob('*_VH_*.tif'))

    if not scene_files:
        logger.error(f"No scenes found in {input_dir}")
        sys.exit(1)

    logger.info(f"Found {len(scene_files)} scenes")

    # Create mosaicker
    mosaicker = GDALMosaicker(nodata=args.nodata)

    # Create output directory
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Mosaic
    logger.info(f"\n{'='*70}")
    logger.info("CREATING MOSAIC")
    logger.info(f"{'='*70}\n")

    if args.method == 'merge':
        success = mosaicker.mosaic_with_gdal_merge(scene_files, output_path)
    else:
        success = mosaicker.mosaic_with_vrt(scene_files, output_path)

    if success:
        logger.info(f"\n{'='*70}")
        logger.info("MOSAIC INFO")
        logger.info(f"{'='*70}")

        ds = gdal.Open(str(output_path))
        if ds:
            logger.info(f"File: {output_path}")
            logger.info(f"Size: {ds.RasterXSize} x {ds.RasterYSize}")

            if output_path.suffix.lower() in ['.tif', '.tiff']:
                file_size_gb = output_path.stat().st_size / (1024**3)
                logger.info(f"File size: {file_size_gb:.2f} GB")

            band = ds.GetRasterBand(1)
            stats = band.ComputeStatistics(False)
            logger.info(f"Value range: {stats[0]:.2f} to {stats[1]:.2f} dB")
            logger.info(f"Mean: {stats[2]:.2f} dB")

            ds = None

        logger.info(f"{'='*70}")
        logger.info("✓ Mosaic complete!")
        logger.info(f"{'='*70}\n")

        sys.exit(0)
    else:
        logger.error("\n✗ Mosaicking failed")
        sys.exit(1)


if __name__ == '__main__':
    main()
