#!/usr/bin/env python3
"""
Improved S1 mosaicking with better overlap handling

Uses median compositing instead of simple mosaicking for better handling
of radiometric differences between overlapping scenes.

Usage:
    python s1_mosaic_improved.py \
        --input-dir workspace/preprocessed_20m/p6 \
        --output workspace/mosaics_20m/period_06_mosaic.tif \
        --method median
"""

import os
import sys
import argparse
import logging
from pathlib import Path
import numpy as np
from osgeo import gdal, osr
from typing import List, Tuple
import gc

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

gdal.UseExceptions()


class ImprovedMosaicker:
    """Mosaic with median/mean compositing for better overlap handling"""

    def __init__(self, method: str = 'median', nodata: float = -32768):
        """
        Args:
            method: 'median', 'mean', or 'min' compositing in overlaps
            nodata: NoData value
        """
        self.method = method
        self.nodata = nodata
        logger.info(f"Improved Mosaicker - Method: {method}")

    def get_common_extent(self, scene_files: List[Path]) -> Tuple[float, float, float, float, int, int, Tuple]:
        """Get common extent and optimal resolution for all scenes"""

        logger.info("Computing common extent...")

        minx = miny = float('inf')
        maxx = maxy = float('-inf')
        pixel_sizes = []
        first_srs = None

        for scene_file in scene_files:
            ds = gdal.Open(str(scene_file))
            if not ds:
                logger.warning(f"Could not open {scene_file}")
                continue

            # Get extent
            gt = ds.GetGeoTransform()
            xmin = gt[0]
            ymax = gt[3]
            xmax = xmin + gt[1] * ds.RasterXSize
            ymin = ymax + gt[5] * ds.RasterYSize

            minx = min(minx, xmin)
            maxx = max(maxx, xmax)
            miny = min(miny, ymin)
            maxy = max(maxy, ymax)

            pixel_sizes.append(abs(gt[1]))

            if first_srs is None:
                first_srs = ds.GetProjection()

            ds = None

        # Use median pixel size
        pixel_size = np.median(pixel_sizes)

        # Calculate dimensions
        width = int((maxx - minx) / pixel_size)
        height = int((maxy - miny) / pixel_size)

        logger.info(f"  Extent: ({minx:.2f}, {miny:.2f}, {maxx:.2f}, {maxy:.2f})")
        logger.info(f"  Pixel size: {pixel_size:.2f} m")
        logger.info(f"  Dimensions: {width} x {height}")

        geotransform = (minx, pixel_size, 0, maxy, 0, -pixel_size)

        return minx, miny, maxx, maxy, width, height, geotransform, first_srs

    def mosaic_with_compositing(self, scene_files: List[Path], output_file: Path) -> bool:
        """
        Mosaic scenes using median/mean compositing in overlaps

        This approach:
        1. Creates output raster covering all scenes
        2. For each pixel position, collects values from all overlapping scenes
        3. Uses median/mean to blend overlaps (reduces radiometric differences)

        Args:
            scene_files: List of input GeoTIFF files
            output_file: Output mosaic file

        Returns:
            Success status
        """
        if not scene_files:
            logger.error("No input scenes provided")
            return False

        if len(scene_files) == 1:
            logger.info("Single scene - copying directly")
            import shutil
            shutil.copy(scene_files[0], output_file)
            return True

        logger.info(f"Mosaicking {len(scene_files)} scenes with {self.method} compositing...")

        # Get common extent
        minx, miny, maxx, maxy, width, height, geotransform, projection = \
            self.get_common_extent(scene_files)

        # Create output arrays
        logger.info("Initializing output arrays...")
        output_data = np.full((height, width), self.nodata, dtype=np.float32)
        count_data = np.zeros((height, width), dtype=np.uint8)  # Count of valid values

        # For median, we need to store all values
        if self.method == 'median':
            # Pre-allocate array for all values (max len(scene_files) values per pixel)
            value_stack = np.full((len(scene_files), height, width), self.nodata, dtype=np.float32)

        # Process each scene
        for idx, scene_file in enumerate(scene_files):
            logger.info(f"Processing scene {idx+1}/{len(scene_files)}: {scene_file.name}")

            ds = gdal.Open(str(scene_file))
            if not ds:
                logger.warning(f"Could not open {scene_file}")
                continue

            # Read data
            band = ds.GetRasterBand(1)
            scene_data = band.ReadAsArray()
            scene_gt = ds.GetGeoTransform()

            # Calculate pixel offset in output grid
            x_offset = int((scene_gt[0] - geotransform[0]) / geotransform[1])
            y_offset = int((scene_gt[3] - geotransform[3]) / geotransform[5])

            # Get overlap region
            x_start = max(0, x_offset)
            y_start = max(0, y_offset)
            x_end = min(width, x_offset + ds.RasterXSize)
            y_end = min(height, y_offset + ds.RasterYSize)

            # Get corresponding region in scene
            scene_x_start = x_start - x_offset
            scene_y_start = y_start - y_offset
            scene_x_end = scene_x_start + (x_end - x_start)
            scene_y_end = scene_y_start + (y_end - y_start)

            # Extract overlap region
            overlap_data = scene_data[scene_y_start:scene_y_end, scene_x_start:scene_x_end]

            # Create valid data mask (not nodata, not NaN, not Inf)
            valid_mask = (overlap_data != self.nodata) & \
                        ~np.isnan(overlap_data) & \
                        ~np.isinf(overlap_data)

            if self.method == 'median':
                # Store values for median calculation
                value_stack[count_data[y_start:y_end, x_start:x_end], y_start:y_end, x_start:x_end] = \
                    np.where(valid_mask, overlap_data, self.nodata)
                count_data[y_start:y_end, x_start:x_end] += valid_mask.astype(np.uint8)

            elif self.method == 'mean':
                # Accumulate sum for mean
                output_data[y_start:y_end, x_start:x_end] = np.where(
                    valid_mask,
                    np.where(count_data[y_start:y_end, x_start:x_end] == 0,
                            overlap_data,
                            output_data[y_start:y_end, x_start:x_end] + overlap_data),
                    output_data[y_start:y_end, x_start:x_end]
                )
                count_data[y_start:y_end, x_start:x_end] += valid_mask.astype(np.uint8)

            elif self.method == 'min':
                # Take minimum value (useful for SAR to reduce bright artifacts)
                output_data[y_start:y_end, x_start:x_end] = np.where(
                    valid_mask,
                    np.where(count_data[y_start:y_end, x_start:x_end] == 0,
                            overlap_data,
                            np.minimum(output_data[y_start:y_end, x_start:x_end], overlap_data)),
                    output_data[y_start:y_end, x_start:x_end]
                )
                count_data[y_start:y_end, x_start:x_end] += valid_mask.astype(np.uint8)

            ds = None
            gc.collect()

        # Finalize output
        logger.info(f"Computing final {self.method} values...")

        if self.method == 'median':
            # Calculate median for each pixel
            for y in range(height):
                if y % 1000 == 0:
                    logger.info(f"  Processing row {y}/{height}")
                for x in range(width):
                    n_values = count_data[y, x]
                    if n_values > 0:
                        # Get valid values for this pixel
                        pixel_values = value_stack[:n_values, y, x]
                        valid_values = pixel_values[pixel_values != self.nodata]
                        if len(valid_values) > 0:
                            output_data[y, x] = np.median(valid_values)

        elif self.method == 'mean':
            # Divide sum by count
            valid_pixels = count_data > 0
            output_data[valid_pixels] /= count_data[valid_pixels]

        # Write output
        logger.info(f"Writing output to {output_file}...")

        output_file.parent.mkdir(parents=True, exist_ok=True)

        driver = gdal.GetDriverByName('GTiff')
        out_ds = driver.Create(
            str(output_file),
            width, height, 1,
            gdal.GDT_Float32,
            options=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES']
        )

        out_ds.SetGeoTransform(geotransform)
        out_ds.SetProjection(projection)

        out_band = out_ds.GetRasterBand(1)
        out_band.WriteArray(output_data)
        out_band.SetNoDataValue(self.nodata)
        out_band.FlushCache()

        out_ds = None

        # Statistics
        valid_pixels = np.sum(count_data > 0)
        overlap_pixels = np.sum(count_data > 1)
        logger.info(f"  Total valid pixels: {valid_pixels:,}")
        logger.info(f"  Overlap pixels: {overlap_pixels:,} ({overlap_pixels/valid_pixels*100:.1f}%)")
        logger.info(f"✓ Mosaic created: {output_file}")

        return True


def main():
    parser = argparse.ArgumentParser(
        description='Improved S1 mosaicking with compositing',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--input-dir', required=True,
                       help='Directory with preprocessed scenes')
    parser.add_argument('--output', required=True,
                       help='Output mosaic file (.tif)')
    parser.add_argument('--method', default='median',
                       choices=['median', 'mean', 'min'],
                       help='Compositing method in overlaps (default: median)')
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
        logger.info("Expected files: *_VH_*.tif")
        sys.exit(1)

    logger.info(f"Found {len(scene_files)} scenes")
    for f in scene_files:
        logger.info(f"  - {f.name}")

    # Create mosaicker
    mosaicker = ImprovedMosaicker(method=args.method, nodata=args.nodata)

    # Mosaic
    output_path = Path(args.output)
    logger.info(f"\n{'='*70}")
    logger.info(f"CREATING MOSAIC")
    logger.info(f"{'='*70}")

    success = mosaicker.mosaic_with_compositing(scene_files, output_path)

    if success:
        # Get mosaic info
        ds = gdal.Open(str(output_path))
        if ds:
            logger.info(f"\n{'='*70}")
            logger.info("MOSAIC INFO")
            logger.info(f"{'='*70}")
            logger.info(f"File: {output_path}")
            logger.info(f"Size: {ds.RasterXSize} x {ds.RasterYSize}")
            logger.info(f"File size: {output_path.stat().st_size / (1024**3):.2f} GB")

            band = ds.GetRasterBand(1)
            stats = band.ComputeStatistics(False)
            logger.info(f"Value range: {stats[0]:.2f} to {stats[1]:.2f} dB")
            logger.info(f"Mean: {stats[2]:.2f} dB")

            ds = None
            logger.info(f"{'='*70}")
            logger.info(f"✓ Mosaic complete!")
            logger.info(f"{'='*70}\n")

        sys.exit(0)
    else:
        logger.error(f"\n✗ Failed to create mosaic")
        sys.exit(1)


if __name__ == '__main__':
    main()
