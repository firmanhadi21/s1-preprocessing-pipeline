#!/usr/bin/env python3
"""
Normalize SAR scenes to common radiometric reference

This adjusts each scene's histogram to match a reference, reducing seams

Usage:
    python normalize_scenes.py \
        --input-dir workspace/preprocessed_20m/p6 \
        --output-dir workspace/preprocessed_20m/p6_normalized
"""

import argparse
import logging
from pathlib import Path
import numpy as np
from osgeo import gdal
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

gdal.UseExceptions()


class SceneNormalizer:
    """Normalize scenes to common radiometric reference"""

    def __init__(self, target_mean: float = None, target_std: float = None):
        """
        Args:
            target_mean: Target mean value (None = use median of all scenes)
            target_std: Target std dev (None = use median of all scenes)
        """
        self.target_mean = target_mean
        self.target_std = target_std

    def get_scene_stats(self, scene_file: Path, sample_rate: float = 0.1):
        """Get statistics from scene"""

        ds = gdal.Open(str(scene_file))
        if not ds:
            return None

        band = ds.GetRasterBand(1)
        nodata = band.GetNoDataValue()

        # Sample data for speed
        width = ds.RasterXSize
        height = ds.RasterYSize

        if sample_rate < 1.0:
            sample_width = int(width * sample_rate)
            sample_height = int(height * sample_rate)
            data = band.ReadAsArray(buf_xsize=sample_width, buf_ysize=sample_height)
        else:
            data = band.ReadAsArray()

        ds = None

        # Get valid data
        if nodata is not None:
            valid_mask = (data != nodata) & ~np.isnan(data) & ~np.isinf(data)
        else:
            valid_mask = ~np.isnan(data) & ~np.isinf(data)

        valid_data = data[valid_mask]

        if len(valid_data) == 0:
            return None

        return {
            'mean': np.mean(valid_data),
            'std': np.std(valid_data),
            'median': np.median(valid_data),
            'p25': np.percentile(valid_data, 25),
            'p75': np.percentile(valid_data, 75)
        }

    def normalize_scene(self, input_file: Path, output_file: Path,
                       target_mean: float, target_std: float) -> bool:
        """
        Normalize scene to target statistics

        Uses: normalized = (value - scene_mean) / scene_std * target_std + target_mean
        """

        logger.info(f"Normalizing: {input_file.name}")

        # Get scene stats
        stats = self.get_scene_stats(input_file, sample_rate=0.2)
        if not stats:
            logger.error(f"Could not get stats for {input_file}")
            return False

        scene_mean = stats['mean']
        scene_std = stats['std']

        logger.info(f"  Scene: mean={scene_mean:.2f}, std={scene_std:.2f}")
        logger.info(f"  Target: mean={target_mean:.2f}, std={target_std:.2f}")

        # Open input
        src_ds = gdal.Open(str(input_file))
        if not src_ds:
            return False

        # Create output
        driver = gdal.GetDriverByName('GTiff')
        dst_ds = driver.CreateCopy(
            str(output_file),
            src_ds,
            options=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=IF_SAFER']
        )

        src_band = src_ds.GetRasterBand(1)
        dst_band = dst_ds.GetRasterBand(1)
        nodata = src_band.GetNoDataValue()

        # Process in chunks
        width = src_ds.RasterXSize
        height = src_ds.RasterYSize
        chunk_size = 2048

        for y in range(0, height, chunk_size):
            y_size = min(chunk_size, height - y)

            for x in range(0, width, chunk_size):
                x_size = min(chunk_size, width - x)

                # Read chunk
                data = src_band.ReadAsArray(x, y, x_size, y_size)

                # Create mask
                if nodata is not None:
                    valid_mask = (data != nodata) & ~np.isnan(data) & ~np.isinf(data)
                else:
                    valid_mask = ~np.isnan(data) & ~np.isinf(data)

                # Normalize valid pixels
                if scene_std > 0:
                    normalized = np.where(
                        valid_mask,
                        (data - scene_mean) / scene_std * target_std + target_mean,
                        data
                    )
                else:
                    normalized = data

                # Write chunk
                dst_band.WriteArray(normalized, x, y)

        # Finalize
        dst_band.FlushCache()
        dst_ds = None
        src_ds = None

        logger.info(f"  ✓ Saved: {output_file}")
        return True


def main():
    parser = argparse.ArgumentParser(description='Normalize SAR scenes')

    parser.add_argument('--input-dir', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--target-mean', type=float,
                       help='Target mean (default: median of all scenes)')
    parser.add_argument('--target-std', type=float,
                       help='Target std dev (default: median of all scenes)')

    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if not input_dir.exists():
        logger.error(f"Input directory not found: {input_dir}")
        sys.exit(1)

    scene_files = sorted(input_dir.glob('*_VH_*.tif'))

    if not scene_files:
        logger.error(f"No scenes found in {input_dir}")
        sys.exit(1)

    logger.info(f"Found {len(scene_files)} scenes")

    # Get target statistics
    normalizer = SceneNormalizer()

    if args.target_mean is None or args.target_std is None:
        logger.info("Computing target statistics from all scenes...")

        all_means = []
        all_stds = []

        for scene_file in scene_files:
            stats = normalizer.get_scene_stats(scene_file)
            if stats:
                all_means.append(stats['mean'])
                all_stds.append(stats['std'])
                logger.info(f"  {scene_file.name}: mean={stats['mean']:.2f}, std={stats['std']:.2f}")

        target_mean = args.target_mean or np.median(all_means)
        target_std = args.target_std or np.median(all_stds)

        logger.info(f"\nTarget statistics:")
        logger.info(f"  Mean: {target_mean:.2f} dB")
        logger.info(f"  Std: {target_std:.2f} dB")
    else:
        target_mean = args.target_mean
        target_std = args.target_std

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Normalize each scene
    logger.info(f"\n{'='*70}")
    logger.info("NORMALIZING SCENES")
    logger.info(f"{'='*70}")

    for i, scene_file in enumerate(scene_files, 1):
        logger.info(f"\nScene {i}/{len(scene_files)}")

        output_file = output_dir / scene_file.name
        success = normalizer.normalize_scene(scene_file, output_file, target_mean, target_std)

        if not success:
            logger.error(f"Failed to normalize {scene_file}")

    logger.info(f"\n{'='*70}")
    logger.info(f"✓ Normalization complete!")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"{'='*70}\n")


if __name__ == '__main__':
    main()
