#!/usr/bin/env python3
"""
Sentinel-1 Mosaicking Pipeline for Java Island
Creates seamless 12-day composite mosaics from multiple S1 tracks

Workflow:
1. Group scenes by 12-day period AND relative orbit (track)
2. Composite within each track for each period
3. Radiometric normalization across tracks
4. Mosaic tracks with distance-weighted blending in overlaps
5. Stack all 31 periods into annual multi-band GeoTIFF

This ensures:
- Temporal consistency (12-day composites)
- Radiometric consistency (normalization)
- Seamless mosaics (proper overlap blending)

Usage:
    # Create mosaics for all 31 periods
    python s1_mosaic_java_12day.py \
        --input-dir workspace/preprocessed_50m \
        --output-dir workspace/mosaics_50m \
        --year 2024 \
        --resolution 50

    # Stack into 31-band GeoTIFF
    python s1_mosaic_java_12day.py \
        --input-dir workspace/preprocessed_50m \
        --output workspace/java_vh_stack_2024_31bands.tif \
        --year 2024 \
        --stack-only
"""

import os
import sys
import numpy as np
from pathlib import Path
import argparse
from datetime import datetime
import logging
from typing import List, Dict, Tuple, Optional
import re
import subprocess
import json

from period_utils import get_period_from_date

try:
    from osgeo import gdal, gdalconst
    # Don't call UseExceptions() yet to avoid importing gdal_array (NumPy conflicts with OTB)
except ImportError:
    print("Error: GDAL not available")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class JavaIslandMosaicker:
    """
    Create seamless mosaics for Java Island from multiple S1 tracks
    """

    def __init__(self, year: int, resolution: int = 50,
                 target_extent: Optional[Tuple[float, float, float, float]] = None):
        """
        Initialize mosaicker

        Args:
            year: Year to process
            resolution: Spatial resolution in meters
            target_extent: Target extent (minx, miny, maxx, maxy) in WGS84
                         If None, uses Java Island default extent
        """
        self.year = year
        self.resolution = resolution

        # Default Java Island extent (WGS84)
        # Adjust if needed for your specific AOI
        if target_extent is None:
            self.target_extent = (105.0, -9.0, 116.0, -5.0)  # (minx, miny, maxx, maxy)
        else:
            self.target_extent = target_extent

        logger.info(f"Java Island Mosaicker - {year}")
        logger.info(f"Resolution: {resolution}m")
        logger.info(f"Target extent: {self.target_extent}")


    def extract_metadata_from_filename(self, filename: str) -> Dict:
        """
        Extract metadata from S1 filename

        Format: S1A_IW_GRDH_1SDV_YYYYMMDDTHHMMSS_YYYYMMDDTHHMMSS_XXXXXX_YYYYYY_ZZZZ

        Returns:
            Dict with 'date', 'satellite', 'orbit_number'
        """
        match = re.search(r'S1([AB])_IW_GRDH.*?_(\d{8})T\d{6}_(\d{8})T\d{6}_(\d{6})', filename)

        if not match:
            logger.warning(f"Could not parse filename: {filename}")
            return None

        satellite = match.group(1)
        date_str = match.group(2)
        orbit_number = int(match.group(4))

        date = datetime.strptime(date_str, '%Y%m%d')

        # Relative orbit number (for track identification)
        # S1A: 175 orbits, S1B: 175 orbits (offset by 90 degrees)
        relative_orbit = orbit_number % 175
        if satellite == 'B':
            relative_orbit += 175  # Offset S1B tracks

        # Determine orbit geometry (ascending/descending)
        # Rough approximation: orbits 1-87 are mostly ascending, 88-175 descending
        if relative_orbit == 0:
            relative_orbit = 175
        geometry = 'ascending' if relative_orbit < 88 else 'descending'

        return {
            'date': date,
            'satellite': satellite,
            'orbit_number': orbit_number,
            'relative_orbit': relative_orbit,
            'period': get_period_from_date(date),
            'geometry': geometry
        }


    def group_by_period_and_track(self, scene_files: List[Path],
                                  filter_geometry: Optional[str] = None) -> Dict[int, Dict[int, List[Path]]]:
        """
        Group scenes by period and track (relative orbit)

        Args:
            scene_files: List of scene files
            filter_geometry: Filter to 'ascending' or 'descending' only (or None for both)

        Returns:
            {period: {track: [scene_files]}}
        """
        logger.info(f"Grouping {len(scene_files)} scenes by period and track...")
        if filter_geometry:
            logger.info(f"Filtering to {filter_geometry} passes only")

        groups = {}
        filtered_count = 0

        for scene_file in scene_files:
            meta = self.extract_metadata_from_filename(scene_file.name)

            if meta is None:
                continue

            if meta['date'].year != self.year:
                continue

            # Filter by geometry if requested
            if filter_geometry and meta['geometry'] != filter_geometry:
                filtered_count += 1
                continue

            period = meta['period']
            track = meta['relative_orbit']

            if period not in groups:
                groups[period] = {}

            if track not in groups[period]:
                groups[period][track] = []

            groups[period][track].append(scene_file)

        if filter_geometry:
            logger.info(f"Filtered out {filtered_count} {('descending' if filter_geometry == 'ascending' else 'ascending')} scenes")

        # Log grouping
        logger.info(f"\nGrouping summary:")
        for period in sorted(groups.keys()):
            n_tracks = len(groups[period])
            n_scenes = sum(len(scenes) for scenes in groups[period].values())
            logger.info(f"  Period {period:2d}: {n_tracks} tracks, {n_scenes} scenes total")
            for track, scenes in sorted(groups[period].items()):
                logger.info(f"    Track {track:3d}: {len(scenes)} scenes")

        return groups


    def composite_track(self, scene_files: List[Path], output_file: Path,
                       method: str = 'median') -> bool:
        """
        Create composite from multiple scenes in same track

        Uses GDAL VRT for efficiency
        """
        if len(scene_files) == 0:
            return False

        if len(scene_files) == 1:
            # Single scene - just copy
            import shutil
            shutil.copy(scene_files[0], output_file)
            return True

        logger.info(f"Creating {method} composite from {len(scene_files)} scenes")

        # Create VRT
        vrt_file = output_file.with_suffix('.vrt')

        cmd = ['gdalbuildvrt', '-separate', str(vrt_file)] + [str(f) for f in scene_files]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"VRT creation failed: {e.stderr.decode()}")
            return False

        # Apply compositing
        vrt_ds = gdal.Open(str(vrt_file))

        if method == 'median':
            # Read all bands
            bands_data = []
            for i in range(1, vrt_ds.RasterCount + 1):
                band = vrt_ds.GetRasterBand(i)
                data = band.ReadAsArray()
                bands_data.append(data)

            # Stack and compute median
            stacked = np.stack(bands_data, axis=0)
            nodata = -32768
            valid_mask = stacked != nodata

            composite = np.ma.median(np.ma.masked_array(stacked, ~valid_mask), axis=0)
            composite = composite.filled(nodata).astype(np.float32)

        elif method == 'mean':
            # Similar to median
            bands_data = []
            for i in range(1, vrt_ds.RasterCount + 1):
                band = vrt_ds.GetRasterBand(i)
                data = band.ReadAsArray()
                bands_data.append(data)

            stacked = np.stack(bands_data, axis=0)
            nodata = -32768
            valid_mask = stacked != nodata

            composite = np.ma.mean(np.ma.masked_array(stacked, ~valid_mask), axis=0)
            composite = composite.filled(nodata).astype(np.float32)

        elif method == 'first':
            composite = vrt_ds.GetRasterBand(1).ReadAsArray()

        else:
            raise ValueError(f"Unknown method: {method}")

        # Write output
        driver = gdal.GetDriverByName('GTiff')
        out_ds = driver.Create(
            str(output_file),
            vrt_ds.RasterXSize,
            vrt_ds.RasterYSize,
            1,
            gdal.GDT_Float32,
            options=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES']
        )

        out_ds.SetGeoTransform(vrt_ds.GetGeoTransform())
        out_ds.SetProjection(vrt_ds.GetProjection())
        out_ds.GetRasterBand(1).WriteArray(composite)
        out_ds.GetRasterBand(1).SetNoDataValue(nodata)

        out_ds = None
        vrt_ds = None

        # Clean up VRT
        vrt_file.unlink()

        return True


    def mosaic_tracks_otb(self, track_files: List[Path], output_file: Path) -> bool:
        """
        Mosaic multiple track composites using Orfeo Toolbox

        OTB provides superior overlap handling with:
        - Large feathering for seamless blending
        - Radiometric harmonization across tracks
        - Better nodata handling
        """
        if len(track_files) == 0:
            return False

        if len(track_files) == 1:
            import shutil
            shutil.copy(track_files[0], output_file)
            return True

        logger.info(f"Mosaicking {len(track_files)} tracks with Orfeo Toolbox...")

        # Build OTB Mosaic command
        cmd = [
            'otbcli_Mosaic',
            '-il'
        ] + [str(f) for f in track_files] + [
            '-out', str(output_file), 'float',
            '-comp.feather', 'large',           # Large feathering for smooth blending
            '-nodata', '-32768',                # Nodata value
            '-harmo.method', 'band',            # Band-wise harmonization
            '-harmo.cost', 'rmse',              # RMSE cost function for harmonization
            '-tmpdir', str(output_file.parent / 'tmp')
        ]

        # Create temp directory
        tmp_dir = output_file.parent / 'tmp'
        tmp_dir.mkdir(parents=True, exist_ok=True)

        try:
            logger.info(f"Running OTB Mosaic:")
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
            logger.info(f"✓ Mosaic created: {output_file.name}")

            # Clean up temp directory
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"OTB Mosaicking failed: {e.stderr}")
            logger.error(f"Make sure Orfeo Toolbox is installed: conda install -c conda-forge otb")
            return False


    def process_period(self, period: int, period_groups: Dict[int, List[Path]],
                      output_dir: Path, composite_method: str = 'median') -> Optional[Path]:
        """
        Process one 12-day period: composite tracks, then mosaic

        Returns:
            Path to final mosaic (or None if failed)
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"PROCESSING PERIOD {period}")
        logger.info(f"{'='*70}")

        output_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Composite each track
        track_composites = []

        for track, scene_files in sorted(period_groups.items()):
            track_output = output_dir / f"period_{period:02d}_track_{track:03d}.tif"

            if track_output.exists():
                logger.info(f"✓ Track {track} composite already exists")
                track_composites.append(track_output)
                continue

            logger.info(f"Compositing track {track} ({len(scene_files)} scenes)...")
            success = self.composite_track(scene_files, track_output, method=composite_method)

            if success:
                track_composites.append(track_output)
            else:
                logger.warning(f"Failed to composite track {track}")

        if not track_composites:
            logger.error(f"No track composites created for period {period}")
            return None

        # Step 2: Mosaic all tracks
        mosaic_output = output_dir / f"period_{period:02d}_mosaic.tif"

        if mosaic_output.exists():
            logger.info(f"✓ Period {period} mosaic already exists")
            return mosaic_output

        logger.info(f"Mosaicking {len(track_composites)} track composites...")
        success = self.mosaic_tracks_otb(track_composites, mosaic_output)

        if success:
            # Clean up track composites to save space
            logger.info("Cleaning up intermediate track files...")
            for track_file in track_composites:
                track_file.unlink()

            return mosaic_output
        else:
            return None


    def create_annual_stack(self, mosaic_dir: Path, output_file: Path) -> bool:
        """
        Stack all 31 period mosaics into single multi-band GeoTIFF
        """
        logger.info(f"\n{'='*70}")
        logger.info("CREATING ANNUAL STACK")
        logger.info(f"{'='*70}")

        # Find all period mosaics
        period_mosaics = sorted(mosaic_dir.glob('period_*_mosaic.tif'))

        if not period_mosaics:
            logger.error(f"No period mosaics found in {mosaic_dir}")
            return False

        logger.info(f"Found {len(period_mosaics)} period mosaics")

        # Use gdal_merge.py or buildvrt + gdal_translate
        logger.info("Building VRT stack...")

        vrt_file = output_file.with_suffix('.vrt')

        cmd = ['gdalbuildvrt', '-separate', str(vrt_file)] + [str(f) for f in period_mosaics]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"VRT creation failed: {e.stderr.decode()}")
            return False

        # Convert VRT to GeoTIFF
        logger.info("Converting to GeoTIFF...")

        cmd = [
            'gdal_translate',
            '-co', 'COMPRESS=LZW',
            '-co', 'TILED=YES',
            '-co', 'BIGTIFF=YES',
            str(vrt_file),
            str(output_file)
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"✓ Annual stack created: {output_file}")

            # Clean up VRT
            vrt_file.unlink()

            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"GeoTIFF creation failed: {e.stderr.decode()}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description='Create seamless 12-day mosaics for Java Island',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--input-dir', required=True,
                       help='Directory with preprocessed scenes')
    parser.add_argument('--output-dir',
                       help='Output directory for period mosaics')
    parser.add_argument('--output',
                       help='Output file for annual stack')
    parser.add_argument('--year', type=int, default=2024,
                       help='Year to process (default: 2024)')
    parser.add_argument('--resolution', type=int, default=50,
                       help='Output resolution in meters (default: 50)')
    parser.add_argument('--composite-method', default='median',
                       choices=['median', 'mean', 'first'],
                       help='Within-track compositing method (default: median)')
    parser.add_argument('--extent', nargs=4, type=float, metavar=('MINX', 'MINY', 'MAXX', 'MAXY'),
                       help='Target extent in WGS84 (default: Java Island)')
    parser.add_argument('--geometry', choices=['ascending', 'descending', 'both'], default='both',
                       help='Orbit geometry to use (default: both)')
    parser.add_argument('--stack-only', action='store_true',
                       help='Only create stack from existing mosaics')

    args = parser.parse_args()

    # Initialize mosaicker
    mosaicker = JavaIslandMosaicker(
        year=args.year,
        resolution=args.resolution,
        target_extent=tuple(args.extent) if args.extent else None
    )

    # Find input scenes
    input_path = Path(args.input_dir)
    scene_files = list(input_path.glob('*_VH_*.tif'))

    if not scene_files:
        logger.error(f"No scenes found in {input_path}")
        sys.exit(1)

    logger.info(f"Found {len(scene_files)} preprocessed scenes")

    if args.stack_only:
        # Only create stack from existing mosaics
        if not args.output:
            logger.error("--output required with --stack-only")
            sys.exit(1)

        mosaic_dir = Path(args.output_dir) if args.output_dir else Path('workspace/mosaics_50m')
        success = mosaicker.create_annual_stack(mosaic_dir, Path(args.output))

        sys.exit(0 if success else 1)

    # Group by period and track
    filter_geom = None if args.geometry == 'both' else args.geometry
    period_track_groups = mosaicker.group_by_period_and_track(scene_files, filter_geometry=filter_geom)

    # Output directory
    output_dir = Path(args.output_dir) if args.output_dir else Path('workspace/mosaics_50m')
    output_dir.mkdir(parents=True, exist_ok=True)

    # Process each period
    created_mosaics = []

    for period in sorted(period_track_groups.keys()):
        mosaic_file = mosaicker.process_period(
            period,
            period_track_groups[period],
            output_dir,
            composite_method=args.composite_method
        )

        if mosaic_file:
            created_mosaics.append(mosaic_file)

    logger.info(f"\n{'='*70}")
    logger.info(f"SUMMARY: Created {len(created_mosaics)}/31 period mosaics")
    logger.info(f"{'='*70}")

    # Create annual stack if requested
    if args.output:
        success = mosaicker.create_annual_stack(output_dir, Path(args.output))
        if success:
            logger.info(f"\n✓ Complete! Annual stack: {args.output}")
        else:
            logger.error("\n✗ Failed to create annual stack")
            sys.exit(1)


if __name__ == '__main__':
    main()
