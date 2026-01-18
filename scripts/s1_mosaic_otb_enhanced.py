#!/usr/bin/env python3
"""
Enhanced OTB mosaicking with multiple strategies

Tries different OTB mosaic parameters for better overlap handling

Usage:
    python s1_mosaic_otb_enhanced.py \
        --input-dir workspace/preprocessed_20m/p6 \
        --output workspace/mosaics_20m/period_06_mosaic.tif \
        --strategy seamless
"""

import os
import sys
import argparse
import subprocess
import logging
from pathlib import Path
from typing import List

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class EnhancedOTBMosaicker:
    """Enhanced OTB mosaicking with multiple strategies"""

    STRATEGIES = {
        'seamless': {
            'desc': 'Maximum feathering and harmonization (best for visible seams)',
            'feather': 'large',
            'harmo_method': 'band',
            'harmo_cost': 'rmse'
        },
        'histogram': {
            'desc': 'Histogram-based harmonization (good for radiometric differences)',
            'feather': 'large',
            'harmo_method': 'band',
            'harmo_cost': 'musig'  # Mean/sigma matching
        },
        'interpolation': {
            'desc': 'Bicubic interpolation with feathering',
            'feather': 'large',
            'harmo_method': 'band',
            'harmo_cost': 'rmse',
            'interpolator': 'bco'
        },
        'simple': {
            'desc': 'Feathering only, no harmonization (fast)',
            'feather': 'large',
            'harmo_method': 'none'
        }
    }

    def __init__(self, strategy: str = 'seamless'):
        if strategy not in self.STRATEGIES:
            logger.error(f"Invalid strategy: {strategy}")
            logger.error(f"Available: {', '.join(self.STRATEGIES.keys())}")
            sys.exit(1)

        self.strategy = strategy
        self.params = self.STRATEGIES[strategy]
        logger.info(f"OTB Mosaic Strategy: {strategy}")
        logger.info(f"  {self.params['desc']}")

    def mosaic_scenes(self, scene_files: List[Path], output_file: Path) -> bool:
        """
        Mosaic scenes using OTB with selected strategy

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

        logger.info(f"Mosaicking {len(scene_files)} scenes with OTB...")

        # Build OTB command
        cmd = [
            'otbcli_Mosaic',
            '-il'
        ] + [str(f) for f in scene_files] + [
            '-out', str(output_file), 'float',
            '-comp.feather', self.params['feather'],
            '-nodata', '-32768'
        ]

        # Add harmonization parameters
        if self.params.get('harmo_method') != 'none':
            cmd.extend([
                '-harmo.method', self.params['harmo_method'],
                '-harmo.cost', self.params['harmo_cost']
            ])

        # Add interpolator if specified
        if 'interpolator' in self.params:
            cmd.extend(['-interpolator', self.params['interpolator']])

        # Add temp directory
        tmp_dir = output_file.parent / 'tmp'
        tmp_dir.mkdir(parents=True, exist_ok=True)
        cmd.extend(['-tmpdir', str(tmp_dir)])

        try:
            logger.info(f"Running OTB Mosaic...")
            logger.info(f"Command: {' '.join(cmd)}")

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

            result = subprocess.run(cmd, env=otb_env, check=True,
                                  capture_output=True, text=True)

            logger.info(f"✓ Mosaic created: {output_file}")

            # Clean up
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"OTB Mosaicking failed: {e.stderr}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description='Enhanced OTB mosaicking',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--input-dir', required=True,
                       help='Directory with preprocessed scenes')
    parser.add_argument('--output', required=True,
                       help='Output mosaic file (.tif)')
    parser.add_argument('--strategy', default='seamless',
                       choices=list(EnhancedOTBMosaicker.STRATEGIES.keys()),
                       help='Mosaicking strategy (default: seamless)')

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

    # Show available strategies
    logger.info("\nAvailable strategies:")
    for name, params in EnhancedOTBMosaicker.STRATEGIES.items():
        marker = "→" if name == args.strategy else " "
        logger.info(f"  {marker} {name}: {params['desc']}")

    # Create mosaicker
    mosaicker = EnhancedOTBMosaicker(strategy=args.strategy)

    # Mosaic
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"\n{'='*70}")
    logger.info(f"CREATING MOSAIC")
    logger.info(f"{'='*70}")

    success = mosaicker.mosaic_scenes(scene_files, output_path)

    if success:
        from osgeo import gdal
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
