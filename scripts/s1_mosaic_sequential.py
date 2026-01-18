#!/usr/bin/env python3
"""
Sequential west-to-east mosaicking with OTB

Mosaics scenes sequentially from west to east:
- Scene1 + Scene2 → Mosaic1
- Mosaic1 + Scene3 → Mosaic2
- Mosaic2 + Scene4 → Mosaic3
- ... until all scenes combined

This gives much better harmonization than mosaicking all at once.

Usage:
    python s1_mosaic_sequential.py \
        --input-dir workspace/preprocessed_20m/p6 \
        --output workspace/mosaics_20m/period_06_mosaic.tif \
        --strategy histogram
"""

import os
import sys
import argparse
import subprocess
import logging
from pathlib import Path
from typing import List, Tuple
from osgeo import gdal
import tempfile
import shutil

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

gdal.UseExceptions()


class SequentialMosaicker:
    """Sequential west-to-east mosaicking with OTB"""

    OTB_STRATEGIES = {
        'histogram': {
            'desc': 'Histogram-based harmonization (best for radiometric differences)',
            'feather': 'large',
            'harmo_method': 'band',
            'harmo_cost': 'musig'
        },
        'seamless': {
            'desc': 'Maximum feathering and RMSE harmonization',
            'feather': 'large',
            'harmo_method': 'band',
            'harmo_cost': 'rmse'
        },
        'simple': {
            'desc': 'Feathering only, no harmonization (fast)',
            'feather': 'large',
            'harmo_method': 'none'
        }
    }

    def __init__(self, strategy: str = 'histogram', keep_intermediate: bool = False):
        """
        Args:
            strategy: OTB mosaicking strategy
            keep_intermediate: Keep intermediate mosaic files for debugging
        """
        if strategy not in self.OTB_STRATEGIES:
            logger.error(f"Invalid strategy: {strategy}")
            sys.exit(1)

        self.strategy = strategy
        self.params = self.OTB_STRATEGIES[strategy]
        self.keep_intermediate = keep_intermediate

        logger.info(f"Sequential Mosaicker (OTB)")
        logger.info(f"  Strategy: {strategy} - {self.params['desc']}")
        logger.info(f"  Keep intermediates: {keep_intermediate}")

    def get_scene_bounds(self, scene_file: Path) -> Tuple[float, float, float, float]:
        """
        Get scene bounding box (minx, miny, maxx, maxy)
        """
        ds = gdal.Open(str(scene_file))
        if not ds:
            raise RuntimeError(f"Cannot open {scene_file}")

        gt = ds.GetGeoTransform()
        width = ds.RasterXSize
        height = ds.RasterYSize

        minx = gt[0]
        maxy = gt[3]
        maxx = minx + gt[1] * width
        miny = maxy + gt[5] * height

        ds = None

        return minx, miny, maxx, maxy

    def sort_scenes_west_to_east(self, scene_files: List[Path]) -> List[Path]:
        """
        Sort scenes by western-most longitude (left to right)
        """
        logger.info("Sorting scenes west to east...")

        scene_bounds = []
        for scene_file in scene_files:
            try:
                minx, miny, maxx, maxy = self.get_scene_bounds(scene_file)
                scene_bounds.append((scene_file, minx, maxy))  # file, west lon, north lat
                logger.info(f"  {scene_file.name}: west={minx:.3f}, north={maxy:.3f}")
            except Exception as e:
                logger.warning(f"Could not get bounds for {scene_file}: {e}")

        # Sort by western longitude (minx), then by northern latitude (maxy) for ties
        scene_bounds.sort(key=lambda x: (x[1], -x[2]))

        sorted_files = [sb[0] for sb in scene_bounds]

        logger.info("\nMosaicking order (west to east):")
        for i, scene_file in enumerate(sorted_files, 1):
            logger.info(f"  {i}. {scene_file.name}")

        return sorted_files

    def mosaic_two_files(self, file1: Path, file2: Path, output_file: Path) -> bool:
        """
        Mosaic two files using OTB

        Args:
            file1: First input file (usually western or existing mosaic)
            file2: Second input file (usually eastern scene to add)
            output_file: Output mosaic file

        Returns:
            Success status
        """
        logger.info(f"  Mosaicking:")
        logger.info(f"    Base: {file1.name}")
        logger.info(f"    Add:  {file2.name}")

        # Build OTB command
        cmd = [
            'otbcli_Mosaic',
            '-il', str(file1), str(file2),
            '-out', str(output_file), 'float',
            '-comp.feather', self.params['feather'],
            '-nodata', '-32768'
        ]

        # Add harmonization if not 'none'
        if self.params.get('harmo_method') != 'none':
            cmd.extend([
                '-harmo.method', self.params['harmo_method'],
                '-harmo.cost', self.params['harmo_cost']
            ])

        # Create temp directory
        tmp_dir = output_file.parent / 'tmp'
        tmp_dir.mkdir(parents=True, exist_ok=True)
        cmd.extend(['-tmpdir', str(tmp_dir)])

        try:
            # Set up OTB environment
            otb_env = os.environ.copy()
            otb_profile = Path.home() / 'work' / 'OTB' / 'otbenv.profile'

            if otb_profile.exists():
                source_cmd = f'source {otb_profile} && env'
                env_result = subprocess.run(source_cmd, shell=True, executable='/bin/bash',
                                          capture_output=True, text=True)

                for line in env_result.stdout.split('\n'):
                    if '=' in line:
                        key, _, value = line.partition('=')
                        otb_env[key] = value

            # Run OTB
            result = subprocess.run(cmd, env=otb_env, check=True,
                                  capture_output=True, text=True)

            # Clean up temp
            shutil.rmtree(tmp_dir, ignore_errors=True)

            # Get output info
            ds = gdal.Open(str(output_file))
            if ds:
                size_mb = output_file.stat().st_size / (1024**2)
                logger.info(f"    → {ds.RasterXSize}x{ds.RasterYSize} pixels, {size_mb:.1f} MB")
                ds = None

            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"OTB failed: {e.stderr}")
            return False

    def mosaic_sequential(self, scene_files: List[Path], output_file: Path) -> bool:
        """
        Perform sequential mosaicking west to east

        Args:
            scene_files: List of scene files (will be sorted west to east)
            output_file: Final output mosaic file

        Returns:
            Success status
        """
        if not scene_files:
            logger.error("No scene files provided")
            return False

        if len(scene_files) == 1:
            logger.info("Single scene - copying directly")
            shutil.copy(scene_files[0], output_file)
            return True

        # Sort scenes west to east
        sorted_scenes = self.sort_scenes_west_to_east(scene_files)

        # Create temp directory for intermediate mosaics
        if self.keep_intermediate:
            temp_dir = output_file.parent / 'intermediate'
            temp_dir.mkdir(parents=True, exist_ok=True)
        else:
            temp_dir = Path(tempfile.mkdtemp(prefix='mosaic_'))

        logger.info(f"\n{'='*70}")
        logger.info(f"SEQUENTIAL MOSAICKING ({len(sorted_scenes)} scenes)")
        logger.info(f"{'='*70}\n")

        # Start with first scene
        current_mosaic = sorted_scenes[0]
        logger.info(f"Step 0: Starting with {current_mosaic.name}")

        # Sequentially add each scene
        for i, next_scene in enumerate(sorted_scenes[1:], start=1):
            logger.info(f"\nStep {i}/{len(sorted_scenes)-1}:")

            # Determine output file name
            if i == len(sorted_scenes) - 1:
                # Last iteration - use final output file
                step_output = output_file
            else:
                # Intermediate iteration
                if self.keep_intermediate:
                    step_output = temp_dir / f"mosaic_step{i:02d}.tif"
                else:
                    step_output = temp_dir / f"mosaic{i}.tif"

            # Mosaic current with next
            success = self.mosaic_two_files(current_mosaic, next_scene, step_output)

            if not success:
                logger.error(f"Failed at step {i}")
                if not self.keep_intermediate:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                return False

            # Update current mosaic for next iteration
            # Don't delete the first scene file
            if i > 1 and current_mosaic != sorted_scenes[0] and not self.keep_intermediate:
                current_mosaic.unlink()  # Delete previous intermediate

            current_mosaic = step_output

        # Clean up temp directory if not keeping intermediates
        if not self.keep_intermediate:
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"\nCleaned up temporary files")
        else:
            logger.info(f"\nIntermediate mosaics saved in: {temp_dir}")

        return True


def main():
    parser = argparse.ArgumentParser(
        description='Sequential west-to-east mosaicking with OTB',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default (histogram harmonization)
  python s1_mosaic_sequential.py \\
      --input-dir workspace/preprocessed_20m/p6 \\
      --output workspace/mosaics_20m/period_06_mosaic.tif

  # Keep intermediate mosaics for debugging
  python s1_mosaic_sequential.py \\
      --input-dir workspace/preprocessed_20m/p6 \\
      --output workspace/mosaics_20m/period_06_mosaic.tif \\
      --keep-intermediate

  # Try different strategy
  python s1_mosaic_sequential.py \\
      --input-dir workspace/preprocessed_20m/p6 \\
      --output workspace/mosaics_20m/period_06_mosaic.tif \\
      --strategy seamless
        """
    )

    parser.add_argument('--input-dir', required=True,
                       help='Directory with preprocessed scenes')
    parser.add_argument('--output', required=True,
                       help='Output mosaic file (.tif)')
    parser.add_argument('--strategy', default='histogram',
                       choices=list(SequentialMosaicker.OTB_STRATEGIES.keys()),
                       help='OTB mosaicking strategy (default: histogram)')
    parser.add_argument('--keep-intermediate', action='store_true',
                       help='Keep intermediate mosaic files for debugging')

    args = parser.parse_args()

    # Find input scenes
    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        logger.error(f"Input directory not found: {input_dir}")
        sys.exit(1)

    scene_files = list(input_dir.glob('*_VH_*.tif'))

    if not scene_files:
        logger.error(f"No scenes found in {input_dir}")
        logger.info("Expected files: *_VH_*.tif")
        sys.exit(1)

    logger.info(f"Found {len(scene_files)} scenes\n")

    # Create mosaicker
    mosaicker = SequentialMosaicker(
        strategy=args.strategy,
        keep_intermediate=args.keep_intermediate
    )

    # Create output directory
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Mosaic
    success = mosaicker.mosaic_sequential(scene_files, output_path)

    if success:
        logger.info(f"\n{'='*70}")
        logger.info("FINAL MOSAIC INFO")
        logger.info(f"{'='*70}")

        ds = gdal.Open(str(output_path))
        if ds:
            logger.info(f"File: {output_path}")
            logger.info(f"Size: {ds.RasterXSize} x {ds.RasterYSize}")

            file_size_gb = output_path.stat().st_size / (1024**3)
            logger.info(f"File size: {file_size_gb:.2f} GB")

            band = ds.GetRasterBand(1)
            stats = band.ComputeStatistics(False)
            logger.info(f"Value range: {stats[0]:.2f} to {stats[1]:.2f} dB")
            logger.info(f"Mean: {stats[2]:.2f} dB")

            ds = None

        logger.info(f"{'='*70}")
        logger.info(f"✓ Sequential mosaicking complete!")
        logger.info(f"{'='*70}\n")

        sys.exit(0)
    else:
        logger.error(f"\n✗ Sequential mosaicking failed")
        sys.exit(1)


if __name__ == '__main__':
    main()
