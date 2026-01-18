#!/usr/bin/env python3
"""
Create Dual-Polarization 12-Day Composites from Sentinel-1 Time Series

Creates TWO separate 31-band stacks:
1. VH polarization stack (31 bands, one per 12-day period)
2. VV polarization stack (31 bands, one per 12-day period)

These stacks are used together for dual-polarization land cover classification.

Processing:
1. Group S1 scenes by 12-day period
2. For each period, extract VH and VV bands separately
3. Create composite (mean/median) for each period
4. Stack all periods into two multi-band GeoTIFFs

Usage:
    # Create both VH and VV stacks
    python s1_composite_dualpol.py --year 2024 --input-dir preprocessed/ \\
        --output-vh stack_2024_vh.tif --output-vv stack_2024_vv.tif

    # Print period calendar
    python s1_composite_dualpol.py --year 2024 --print-calendar \\
        --input-dir . --output-vh dummy.tif --output-vv dummy.tif
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
    print_period_calendar,
    generate_period_lookup_csv
)

try:
    from osgeo import gdal
    import rasterio
    from rasterio.transform import from_bounds
    from rasterio.warp import calculate_default_transform, reproject, Resampling
except ImportError:
    print("Error: GDAL/rasterio not available")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DualPolCompositor:
    """
    Create dual-polarization 12-day period composites from Sentinel-1 scenes
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

        logger.info(f"Dual-Pol Sentinel-1 12-Day Compositor for {year}")
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
            scene_files: List of preprocessed scene file paths

        Returns:
            Dictionary mapping period number (1-31) to list of scene files
        """
        period_scenes = {i: [] for i in range(1, 32)}

        for scene_file in scene_files:
            date = self.extract_date_from_filename(scene_file.name)
            if date is None:
                continue

            # Check if date is in target year
            if date.year != self.year:
                continue

            # Get period number
            period = get_period_from_date(date, self.year)
            if period is not None:
                period_scenes[period].append(scene_file)

        # Log statistics
        filled_periods = sum(1 for scenes in period_scenes.values() if scenes)
        logger.info(f"Found scenes for {filled_periods}/31 periods")

        for period, scenes in period_scenes.items():
            if scenes:
                logger.info(f"  Period {period:2d}: {len(scenes)} scenes")

        return period_scenes

    def create_period_composite_dualpol(self, scene_files: List[Path],
                                       method: str = 'median') -> Tuple[np.ndarray, np.ndarray, dict]:
        """
        Create composite for VH and VV from multiple scenes

        Args:
            scene_files: List of scene file paths for this period
            method: Compositing method ('mean', 'median', 'first', 'last')

        Returns:
            Tuple of (vh_composite, vv_composite, metadata)
        """
        if not scene_files:
            return None, None, None

        # Read all scenes
        vh_arrays = []
        vv_arrays = []
        profile = None

        for scene_file in scene_files:
            try:
                with rasterio.open(scene_file) as src:
                    if profile is None:
                        profile = src.profile.copy()
                        profile['count'] = 1  # Single band output

                    # Read bands
                    # Assuming band 1 = VH, band 2 = VV (adjust if different)
                    if src.count >= 2:
                        vh_band = src.read(1)
                        vv_band = src.read(2)
                    elif src.count == 1:
                        # If single band, check filename for polarization
                        if 'VH' in scene_file.name.upper():
                            vh_band = src.read(1)
                            vv_band = None
                        elif 'VV' in scene_file.name.upper():
                            vh_band = None
                            vv_band = src.read(1)
                        else:
                            logger.warning(f"Cannot determine polarization for {scene_file.name}")
                            continue
                    else:
                        logger.warning(f"Unexpected band count: {src.count}")
                        continue

                    if vh_band is not None:
                        vh_arrays.append(vh_band)
                    if vv_band is not None:
                        vv_arrays.append(vv_band)

            except Exception as e:
                logger.error(f"Error reading {scene_file}: {str(e)}")
                continue

        if not vh_arrays and not vv_arrays:
            return None, None, None

        # Create composites
        vh_composite = None
        vv_composite = None

        if vh_arrays:
            vh_stack = np.stack(vh_arrays, axis=0)
            if method == 'median':
                vh_composite = np.median(vh_stack, axis=0)
            elif method == 'mean':
                vh_composite = np.mean(vh_stack, axis=0)
            elif method == 'first':
                vh_composite = vh_stack[0]
            elif method == 'last':
                vh_composite = vh_stack[-1]
            else:
                raise ValueError(f"Unknown method: {method}")

        if vv_arrays:
            vv_stack = np.stack(vv_arrays, axis=0)
            if method == 'median':
                vv_composite = np.median(vv_stack, axis=0)
            elif method == 'mean':
                vv_composite = np.mean(vv_stack, axis=0)
            elif method == 'first':
                vv_composite = vv_stack[0]
            elif method == 'last':
                vv_composite = vv_stack[-1]
            else:
                raise ValueError(f"Unknown method: {method}")

        return vh_composite, vv_composite, profile

    def create_annual_stack_dualpol(self, input_dir: Path, output_vh: Path,
                                   output_vv: Path, method: str = 'median'):
        """
        Create dual-polarization annual stacks (31 bands each)

        Args:
            input_dir: Directory with preprocessed scenes
            output_vh: Output path for VH stack
            output_vv: Output path for VV stack
            method: Compositing method
        """
        logger.info(f"Creating dual-pol annual stacks for {self.year}")
        logger.info(f"Input directory: {input_dir}")
        logger.info(f"Output VH: {output_vh}")
        logger.info(f"Output VV: {output_vv}")
        logger.info(f"Compositing method: {method}")

        # Find all preprocessed scenes
        scene_files = list(input_dir.glob('*.tif')) + list(input_dir.glob('*.TIF'))
        logger.info(f"Found {len(scene_files)} scene files")

        if not scene_files:
            raise ValueError(f"No .tif files found in {input_dir}")

        # Group by period
        period_scenes = self.group_scenes_by_period(scene_files)

        # Create composites for each period
        vh_bands = []
        vv_bands = []
        profile = None

        for period in range(1, 32):
            logger.info(f"\nProcessing period {period}/31...")

            scenes = period_scenes[period]
            if not scenes:
                logger.warning(f"No scenes for period {period}, creating empty band")
                # Create empty band if we have profile
                if profile is not None:
                    empty_band = np.full((profile['height'], profile['width']),
                                        profile.get('nodata', -32768), dtype=np.float32)
                    vh_bands.append(empty_band)
                    vv_bands.append(empty_band)
                continue

            # Create composite
            vh_comp, vv_comp, comp_profile = self.create_period_composite_dualpol(
                scenes, method=method
            )

            if comp_profile is not None and profile is None:
                profile = comp_profile

            if vh_comp is not None:
                vh_bands.append(vh_comp)
            else:
                if profile is not None:
                    empty_band = np.full((profile['height'], profile['width']),
                                        profile.get('nodata', -32768), dtype=np.float32)
                    vh_bands.append(empty_band)

            if vv_comp is not None:
                vv_bands.append(vv_comp)
            else:
                if profile is not None:
                    empty_band = np.full((profile['height'], profile['width']),
                                        profile.get('nodata', -32768), dtype=np.float32)
                    vv_bands.append(empty_band)

            logger.info(f"Period {period} complete (VH: {'Yes' if vh_comp is not None else 'No'}, "
                       f"VV: {'Yes' if vv_comp is not None else 'No'})")

        # Stack bands and write outputs
        if not vh_bands or not vv_bands:
            raise ValueError("No valid composites created")

        # Write VH stack
        logger.info(f"\nWriting VH stack to {output_vh}...")
        vh_stack = np.stack(vh_bands, axis=0)
        profile.update(count=31, dtype=np.float32)

        with rasterio.open(output_vh, 'w', **profile) as dst:
            for i, band in enumerate(vh_bands, 1):
                dst.write(band.astype(np.float32), i)
                dst.set_band_description(i, f'Period_{i:02d}')

        logger.info(f"VH stack written: {vh_stack.shape}")

        # Write VV stack
        logger.info(f"\nWriting VV stack to {output_vv}...")
        vv_stack = np.stack(vv_bands, axis=0)

        with rasterio.open(output_vv, 'w', **profile) as dst:
            for i, band in enumerate(vv_bands, 1):
                dst.write(band.astype(np.float32), i)
                dst.set_band_description(i, f'Period_{i:02d}')

        logger.info(f"VV stack written: {vv_stack.shape}")
        logger.info("\nDual-pol annual stacks created successfully!")


def main():
    parser = argparse.ArgumentParser(
        description='Create dual-polarization 12-day composites from Sentinel-1 time series'
    )
    parser.add_argument('--year', type=int, required=True,
                       help='Year to process')
    parser.add_argument('--input-dir', type=Path, required=True,
                       help='Directory with preprocessed S1 scenes')
    parser.add_argument('--output-vh', type=Path, required=True,
                       help='Output path for VH stack (.tif)')
    parser.add_argument('--output-vv', type=Path, required=True,
                       help='Output path for VV stack (.tif)')
    parser.add_argument('--method', type=str, default='median',
                       choices=['median', 'mean', 'first', 'last'],
                       help='Compositing method (default: median)')
    parser.add_argument('--print-calendar', action='store_true',
                       help='Print 12-day period calendar and exit')
    parser.add_argument('--generate-lookup', action='store_true',
                       help='Generate period lookup CSV and exit')

    args = parser.parse_args()

    # Print calendar if requested
    if args.print_calendar:
        print_period_calendar(args.year)
        sys.exit(0)

    # Generate lookup if requested
    if args.generate_lookup:
        output_csv = Path(f'period_lookup_{args.year}.csv')
        generate_period_lookup_csv(args.year, output_csv)
        print(f"Generated period lookup: {output_csv}")
        sys.exit(0)

    # Validate inputs
    if not args.input_dir.exists():
        logger.error(f"Input directory not found: {args.input_dir}")
        sys.exit(1)

    # Create compositor
    compositor = DualPolCompositor(year=args.year)

    # Create annual stacks
    try:
        compositor.create_annual_stack_dualpol(
            input_dir=args.input_dir,
            output_vh=args.output_vh,
            output_vv=args.output_vv,
            method=args.method
        )
    except Exception as e:
        logger.error(f"Error creating stacks: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
