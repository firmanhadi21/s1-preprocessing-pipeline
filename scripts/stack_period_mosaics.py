#!/usr/bin/env python3
"""
Stack all 31 period mosaics into single multi-band GeoTIFF

Creates final annual stack from completed period mosaics

Usage:
    python stack_period_mosaics.py \
        --mosaic-dir workspace/mosaics \
        --output workspace/java_vh_stack_2024_31bands.tif
"""

import os
import sys
import argparse
import subprocess
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from osgeo import gdal
    gdal.UseExceptions()
except ImportError:
    logger.error("GDAL not found")
    sys.exit(1)


def stack_mosaics(mosaic_dir: Path, output_file: Path) -> bool:
    """
    Stack period mosaics into multi-band GeoTIFF

    Args:
        mosaic_dir: Directory containing period_XX_mosaic.tif files
        output_file: Output stack file

    Returns:
        Success status
    """
    logger.info(f"{'='*70}")
    logger.info("STACKING PERIOD MOSAICS")
    logger.info(f"{'='*70}")

    # Find all period mosaics
    period_mosaics = []
    for period in range(1, 32):
        mosaic_file = mosaic_dir / f"period_{period:02d}_mosaic.tif"
        if mosaic_file.exists():
            period_mosaics.append((period, mosaic_file))
        else:
            logger.warning(f"Missing: Period {period} mosaic ({mosaic_file.name})")

    if not period_mosaics:
        logger.error(f"No period mosaics found in {mosaic_dir}")
        logger.info("Expected files: period_01_mosaic.tif through period_31_mosaic.tif")
        return False

    logger.info(f"Found {len(period_mosaics)}/31 period mosaics")

    if len(period_mosaics) < 31:
        logger.warning(f"⚠️  Only {len(period_mosaics)}/31 periods available")
        logger.info("Missing periods will be skipped in the stack")

    # Sort by period number
    period_mosaics.sort(key=lambda x: x[0])

    # Log found periods
    logger.info("\nFound periods:")
    for period, mosaic_file in period_mosaics:
        file_size_mb = mosaic_file.stat().st_size / (1024**2)
        logger.info(f"  Period {period:2d}: {mosaic_file.name} ({file_size_mb:.1f} MB)")

    # Create output directory
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Build VRT first (faster)
    logger.info(f"\nBuilding VRT stack...")
    vrt_file = output_file.with_suffix('.vrt')

    cmd_vrt = ['gdalbuildvrt', '-separate', str(vrt_file)] + [str(f) for p, f in period_mosaics]

    try:
        subprocess.run(cmd_vrt, check=True, capture_output=True, text=True)
        logger.info(f"✓ VRT created: {vrt_file.name}")
    except subprocess.CalledProcessError as e:
        logger.error(f"VRT creation failed: {e.stderr}")
        return False

    # Convert VRT to GeoTIFF
    logger.info(f"\nConverting to GeoTIFF...")

    cmd_translate = [
        'gdal_translate',
        '-co', 'COMPRESS=LZW',
        '-co', 'TILED=YES',
        '-co', 'BIGTIFF=YES',
        str(vrt_file),
        str(output_file)
    ]

    try:
        subprocess.run(cmd_translate, check=True, capture_output=True, text=True)
        logger.info(f"✓ GeoTIFF created: {output_file.name}")
    except subprocess.CalledProcessError as e:
        logger.error(f"GeoTIFF conversion failed: {e.stderr}")
        return False

    # Clean up VRT
    vrt_file.unlink()

    # Get stack info
    ds = gdal.Open(str(output_file))
    if ds:
        logger.info(f"\n{'='*70}")
        logger.info("FINAL STACK INFO")
        logger.info(f"{'='*70}")
        logger.info(f"File: {output_file}")
        logger.info(f"Size: {ds.RasterXSize} x {ds.RasterYSize}")
        logger.info(f"Bands: {ds.RasterCount} (one per period)")
        logger.info(f"Data type: {gdal.GetDataTypeName(ds.GetRasterBand(1).DataType)}")

        # File size
        file_size_gb = output_file.stat().st_size / (1024**3)
        logger.info(f"File size: {file_size_gb:.2f} GB")

        # Extent
        gt = ds.GetGeoTransform()
        minx = gt[0]
        maxy = gt[3]
        maxx = minx + gt[1] * ds.RasterXSize
        miny = maxy + gt[5] * ds.RasterYSize
        logger.info(f"Extent: ({minx:.2f}, {miny:.2f}, {maxx:.2f}, {maxy:.2f})")

        # Check each band
        logger.info(f"\nBand check:")
        all_ok = True
        for i in range(1, ds.RasterCount + 1):
            band = ds.GetRasterBand(i)
            # Read small sample
            sample = band.ReadAsArray(0, 0, min(100, ds.RasterXSize), min(100, ds.RasterYSize))
            valid_pixels = (sample != -32768).sum()

            if valid_pixels > 0:
                logger.info(f"  Band {i:2d} (Period {i:2d}): ✓ {valid_pixels} valid pixels in sample")
            else:
                logger.warning(f"  Band {i:2d} (Period {i:2d}): ⚠️  No valid data in sample!")
                all_ok = False

        ds = None

        logger.info(f"{'='*70}")

        if all_ok:
            logger.info("✓ All bands have valid data!")
        else:
            logger.warning("⚠️  Some bands may be empty - check source mosaics")

        logger.info(f"\n✓ Annual stack complete: {output_file}")
        logger.info(f"{'='*70}\n")

        return True
    else:
        logger.error("Failed to open output file")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Stack period mosaics into annual multi-band GeoTIFF'
    )

    parser.add_argument('--mosaic-dir', required=True,
                       help='Directory containing period_XX_mosaic.tif files')
    parser.add_argument('--output', required=True,
                       help='Output stack file (.tif)')

    args = parser.parse_args()

    mosaic_dir = Path(args.mosaic_dir)
    if not mosaic_dir.exists():
        logger.error(f"Mosaic directory not found: {mosaic_dir}")
        sys.exit(1)

    output_file = Path(args.output)

    success = stack_mosaics(mosaic_dir, output_file)

    if success:
        logger.info("\n" + "="*70)
        logger.info("NEXT STEPS")
        logger.info("="*70)
        logger.info("\n1. Verify the stack:")
        logger.info(f"   gdalinfo {output_file}")
        logger.info("\n2. Update config.py:")
        logger.info(f"   VH_STACK_2024 = '{output_file}'")
        logger.info("\n3. Train model:")
        logger.info("   python train.py")
        logger.info("\n4. Make predictions:")
        logger.info("   python predict.py --period 15")
        logger.info("="*70 + "\n")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
