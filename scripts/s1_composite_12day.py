#!/usr/bin/env python3
"""
Create 12-Day Composites from Sentinel-1 Time Series

Composites Sentinel-1 acquisitions into 12-day periods (31 per year).
Each period becomes one band in the output stack.

Processing:
1. Group S1 scenes by 12-day period
2. For each period, select best scene or create composite
3. Stack all periods into multi-band GeoTIFF

Usage:
    python s1_composite_12day.py --year 2024 --input-dir preprocessed/ --output stack_2024.tif
"""

import os
import sys
import numpy as np
from pathlib import Path
import argparse
from datetime import datetime
import logging
from typing import List, Dict, Tuple
import re

# Import period utilities
from period_utils import (
    get_period_dates,
    get_period_from_date,
    calculate_composite_period,
    print_period_calendar,
    generate_period_lookup_csv
)

try:
    from osgeo import gdal
    import rasterio
except ImportError:
    print("Error: GDAL/rasterio not available")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Sentinel1Compositor:
    """
    Create 12-day period composites from Sentinel-1 scenes
    """

    def __init__(self, year: int, output_dir: str = 'composites'):
        """
        Initialize compositor

        Args:
            year: Year to process
            output_dir: Output directory for composites
        """
        self.year = year
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Sentinel-1 12-Day Compositor for {year}")
        logger.info(f"Output directory: {self.output_dir}")


    def extract_date_from_filename(self, filename: str) -> datetime:
        """
        Extract acquisition date from Sentinel-1 filename

        Supports formats:
        - S1A_IW_GRDH_1SDV_20240115T...
        - S1A_*_20240115_processed.tif
        - Custom format with YYYYMMDD

        Args:
            filename: Sentinel-1 filename

        Returns:
            datetime object
        """
        # Try standard S1 format: YYYYMMDDTHHMMSS
        match = re.search(r'(\d{8})T\d{6}', filename)
        if match:
            date_str = match.group(1)
            return datetime.strptime(date_str, '%Y%m%d')

        # Try simple YYYYMMDD
        match = re.search(r'(\d{8})', filename)
        if match:
            date_str = match.group(1)
            return datetime.strptime(date_str, '%Y%m%d')

        logger.warning(f"Could not extract date from: {filename}")
        return None


    def group_scenes_by_period(self, scene_files: List[Path]) -> Dict[int, List[Path]]:
        """
        Group scene files by 12-day period

        Args:
            scene_files: List of preprocessed scene files

        Returns:
            Dictionary mapping period number to list of scene files
        """
        logger.info(f"Grouping {len(scene_files)} scenes by 12-day period...")

        period_groups = {i: [] for i in range(1, 32)}  # 31 periods

        for scene_file in scene_files:
            # Extract date from filename
            date = self.extract_date_from_filename(scene_file.name)

            if date is None:
                logger.warning(f"Skipping file with unknown date: {scene_file.name}")
                continue

            # Check if date is in target year
            if date.year != self.year:
                logger.debug(f"Skipping {scene_file.name} (year {date.year} != {self.year})")
                continue

            # Get period number
            period = get_period_from_date(date)

            period_groups[period].append(scene_file)

        # Log grouping results
        for period, files in period_groups.items():
            if files:
                logger.info(f"  Period {period:2d}: {len(files)} scenes")

        return period_groups


    def create_period_composite(self, scene_files: List[Path],
                               method: str = 'median') -> np.ndarray:
        """
        Create composite from multiple scenes

        Args:
            scene_files: List of scene files for this period
            method: Compositing method ('median', 'mean', 'first', 'last')

        Returns:
            Composite array
        """
        if len(scene_files) == 0:
            return None

        if len(scene_files) == 1:
            # Single scene - just read it
            with rasterio.open(scene_files[0]) as src:
                return src.read(1)

        # Multiple scenes - create composite
        logger.info(f"Creating {method} composite from {len(scene_files)} scenes")

        # Read all scenes
        arrays = []
        for scene_file in scene_files:
            try:
                with rasterio.open(scene_file) as src:
                    data = src.read(1)
                    arrays.append(data)
            except Exception as e:
                logger.warning(f"Error reading {scene_file}: {e}")
                continue

        if not arrays:
            return None

        # Stack arrays
        stacked = np.stack(arrays, axis=0)

        # Handle nodata
        nodata_value = -32768
        valid_mask = stacked != nodata_value

        # Create composite based on method
        if method == 'median':
            # Masked median
            composite = np.ma.median(np.ma.masked_array(stacked, ~valid_mask), axis=0)
            composite = composite.filled(nodata_value)

        elif method == 'mean':
            # Masked mean
            composite = np.ma.mean(np.ma.masked_array(stacked, ~valid_mask), axis=0)
            composite = composite.filled(nodata_value)

        elif method == 'first':
            composite = arrays[0]

        elif method == 'last':
            composite = arrays[-1]

        else:
            raise ValueError(f"Unknown method: {method}")

        return composite.astype(np.float32)


    def create_annual_stack(self, input_dir: str, output_file: str,
                           composite_method: str = 'median',
                           fill_missing: bool = True) -> str:
        """
        Create annual stack with 31 bands (one per 12-day period)

        Args:
            input_dir: Directory containing preprocessed scenes
            output_file: Output GeoTIFF file
            composite_method: Method for combining multiple scenes ('median', 'mean', 'first')
            fill_missing: Whether to interpolate missing periods

        Returns:
            Path to output file
        """
        logger.info("="*70)
        logger.info(f"CREATING ANNUAL STACK FOR {self.year}")
        logger.info("="*70)

        # Find all preprocessed scenes
        input_path = Path(input_dir)
        scene_files = list(input_path.glob('*.tif'))

        logger.info(f"Found {len(scene_files)} preprocessed scenes")

        if len(scene_files) == 0:
            raise FileNotFoundError(f"No .tif files found in {input_dir}")

        # Group by period
        period_groups = self.group_scenes_by_period(scene_files)

        # Get reference geometry from first available scene
        ref_file = scene_files[0]
        with rasterio.open(ref_file) as src:
            profile = src.profile.copy()
            height = src.height
            width = src.width
            transform = src.transform
            crs = src.crs
            nodata = src.nodata or -32768

        logger.info(f"\nOutput stack:")
        logger.info(f"  Dimensions: {width} x {height}")
        logger.info(f"  Bands: 31 (one per 12-day period)")
        logger.info(f"  NoData: {nodata}")

        # Create output array
        stack = np.full((31, height, width), nodata, dtype=np.float32)

        # Process each period
        logger.info(f"\nProcessing periods...")

        for period in range(1, 32):
            files = period_groups[period]

            if len(files) > 0:
                # Create composite
                composite = self.create_period_composite(files, method=composite_method)

                if composite is not None:
                    stack[period - 1] = composite
                    logger.info(f"  Period {period:2d} (Band {period:2d}): ✓ Composite from {len(files)} scene(s)")
                else:
                    logger.warning(f"  Period {period:2d} (Band {period:2d}): ✗ Failed to create composite")
            else:
                logger.warning(f"  Period {period:2d} (Band {period:2d}): ✗ No data")

        # Fill missing periods if requested
        if fill_missing:
            stack = self._fill_missing_periods(stack, nodata)

        # Update profile for multi-band output
        profile.update(
            count=31,
            dtype=rasterio.float32,
            compress='lzw',
            tiled=True,
            bigtiff='yes',
            nodata=nodata
        )

        # Write output
        logger.info(f"\nWriting output to: {output_file}")

        with rasterio.open(output_file, 'w', **profile) as dst:
            for band in range(31):
                dst.write(stack[band], band + 1)

                # Set band description
                start_date, end_date = get_period_dates(self.year, band + 1)
                description = f"Period_{band+1}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
                dst.set_band_description(band + 1, description)

        logger.info(f"✓ Annual stack created: {output_file}")

        # Generate statistics
        self._print_stack_statistics(stack, nodata)

        return output_file


    def _fill_missing_periods(self, stack: np.ndarray, nodata: float) -> np.ndarray:
        """
        Fill missing periods using temporal interpolation

        Args:
            stack: Stack array (31, height, width)
            nodata: NoData value

        Returns:
            Filled stack
        """
        logger.info("\nFilling missing periods using interpolation...")

        filled = stack.copy()
        n_filled = 0

        for period in range(31):
            band_data = stack[period]

            # Check if period is entirely missing
            if np.all(band_data == nodata):
                # Find nearest valid periods
                prev_period = period - 1
                next_period = period + 1

                # Look backward for valid data
                while prev_period >= 0 and np.all(stack[prev_period] == nodata):
                    prev_period -= 1

                # Look forward for valid data
                while next_period < 31 and np.all(stack[next_period] == nodata):
                    next_period += 1

                # Interpolate if we have both neighbors
                if prev_period >= 0 and next_period < 31:
                    filled[period] = (stack[prev_period] + stack[next_period]) / 2
                    n_filled += 1
                    logger.info(f"  Filled period {period + 1} (interpolated from {prev_period + 1} and {next_period + 1})")

                # Use previous if only that's available
                elif prev_period >= 0:
                    filled[period] = stack[prev_period]
                    n_filled += 1
                    logger.info(f"  Filled period {period + 1} (copied from {prev_period + 1})")

                # Use next if only that's available
                elif next_period < 31:
                    filled[period] = stack[next_period]
                    n_filled += 1
                    logger.info(f"  Filled period {period + 1} (copied from {next_period + 1})")

        logger.info(f"✓ Filled {n_filled} missing periods")

        return filled


    def _print_stack_statistics(self, stack: np.ndarray, nodata: float):
        """Print statistics about the stack"""

        logger.info("\n" + "="*70)
        logger.info("STACK STATISTICS")
        logger.info("="*70)

        valid_periods = 0
        partial_periods = 0
        missing_periods = 0

        for period in range(31):
            band_data = stack[period]
            valid_pixels = np.sum(band_data != nodata)
            total_pixels = band_data.size

            coverage = (valid_pixels / total_pixels) * 100

            if coverage > 99:
                valid_periods += 1
            elif coverage > 0:
                partial_periods += 1
            else:
                missing_periods += 1

        logger.info(f"Complete periods (>99% coverage): {valid_periods}/31")
        logger.info(f"Partial periods (1-99% coverage): {partial_periods}/31")
        logger.info(f"Missing periods (0% coverage):     {missing_periods}/31")
        logger.info("="*70)


def main():
    parser = argparse.ArgumentParser(
        description='Create 12-day period composites from Sentinel-1'
    )
    parser.add_argument('--year', type=int, required=True,
                       help='Year to process')
    parser.add_argument('--input-dir', required=True,
                       help='Directory containing preprocessed scenes')
    parser.add_argument('--output', required=True,
                       help='Output stacked GeoTIFF')
    parser.add_argument('--method', choices=['median', 'mean', 'first', 'last'],
                       default='median',
                       help='Compositing method (default: median)')
    parser.add_argument('--no-fill', action='store_true',
                       help='Do not fill missing periods')
    parser.add_argument('--print-calendar', action='store_true',
                       help='Print period calendar and exit')
    parser.add_argument('--generate-lookup', action='store_true',
                       help='Generate period lookup CSV')

    args = parser.parse_args()

    # Print calendar if requested
    if args.print_calendar:
        print_period_calendar(args.year)
        sys.exit(0)

    # Generate lookup if requested
    if args.generate_lookup:
        output_csv = f'perioda_{args.year}.csv'
        generate_period_lookup_csv(args.year, output_csv)
        sys.exit(0)

    # Create compositor
    compositor = Sentinel1Compositor(args.year)

    # Create annual stack
    output_file = compositor.create_annual_stack(
        input_dir=args.input_dir,
        output_file=args.output,
        composite_method=args.method,
        fill_missing=not args.no_fill
    )

    logger.info(f"\n{'='*70}")
    logger.info("COMPOSITING COMPLETE")
    logger.info(f"{'='*70}")
    logger.info(f"Output: {output_file}")
    logger.info(f"Bands: 31 (12-day periods)")
    logger.info(f"Valid prediction periods: 7-31 (need 7 bands for backward window)")
    logger.info(f"{'='*70}\n")


if __name__ == '__main__':
    main()
