#!/usr/bin/env python3
"""
Process Sentinel-1 data in period directory structure

Works with directory structure:
    pX/
    ├── downloads/      # Place .zip files here
    ├── preprocessed/   # SNAP output (.dim files)
    ├── geotiff/        # Converted GeoTIFF files
    └── mosaic/         # Final mosaic output + preview image

Usage:
    cd workspace_java_both_orbits/year_2024/p15
    python /path/to/s1_process_period_dir.py --preprocess
    python /path/to/s1_process_period_dir.py --convert
    python /path/to/s1_process_period_dir.py --mosaic

    # Or all steps at once:
    python /path/to/s1_process_period_dir.py --run-all
"""

import os
import sys
from pathlib import Path
import logging
import argparse
import subprocess
from typing import List

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PeriodDirectoryProcessor:
    """
    Process Sentinel-1 data in a single period directory
    """

    def __init__(self, period_dir: str = '.',
                 snap_gpt_path: str = 'gpt',
                 graph_xml: str = None,
                 resolution: int = 20,
                 cache_size: str = '16G'):
        """
        Initialize processor

        Args:
            period_dir: Period directory (e.g., p15/)
            snap_gpt_path: Path to SNAP GPT executable (default: 'gpt' from PATH)
            graph_xml: SNAP processing graph XML file (auto-selected if None)
            resolution: Output resolution in meters (10, 20, 50, or 100)
            cache_size: SNAP cache size
        """
        self.period_dir = Path(period_dir).resolve()
        self.snap_gpt_path = snap_gpt_path
        self.resolution = resolution
        self.cache_size = cache_size

        # Auto-select graph based on resolution if not specified
        if graph_xml is None:
            script_dir = Path(__file__).parent
            if resolution == 10:
                self.graph_xml = str(script_dir / 'graphs' / 'sen1_preprocessing-gpt.xml')
            elif resolution == 20:
                self.graph_xml = str(script_dir / 'graphs' / 'sen1_preprocessing-gpt-20m.xml')
            elif resolution == 50:
                self.graph_xml = str(script_dir / 'graphs' / 'sen1_preprocessing-gpt-50m.xml')
            elif resolution == 100:
                self.graph_xml = str(script_dir / 'graphs' / 'sen1_preprocessing-gpt-100m.xml')
            else:
                raise ValueError(f"Unsupported resolution: {resolution}. Use 10, 20, 50, or 100.")
        else:
            self.graph_xml = graph_xml

        # Setup directories
        self.downloads_dir = self.period_dir / 'downloads'
        self.preprocessed_dir = self.period_dir / 'preprocessed'
        self.geotiff_dir = self.period_dir / 'geotiff'
        self.mosaic_dir = self.period_dir / 'mosaic'

        # Create directories if they don't exist
        self.preprocessed_dir.mkdir(parents=True, exist_ok=True)
        self.geotiff_dir.mkdir(parents=True, exist_ok=True)
        self.mosaic_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Period Directory Processor")
        logger.info(f"Working directory: {self.period_dir}")

    def step1_preprocess(self) -> bool:
        """
        Preprocess all downloads with SNAP GPT

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"STEP 1: PREPROCESSING")
        logger.info(f"{'='*70}")

        # Check if downloads directory exists
        if not self.downloads_dir.exists():
            logger.error(f"Downloads directory not found: {self.downloads_dir}")
            return False

        # Get all ZIP files
        zip_files = sorted(self.downloads_dir.glob('*.zip'))
        if not zip_files:
            logger.warning(f"No ZIP files found in {self.downloads_dir}")
            return False

        logger.info(f"Found {len(zip_files)} ZIP files")

        # Process each file
        success_count = 0
        for i, zip_file in enumerate(zip_files, 1):
            output_name = zip_file.stem + '_processed'
            output_file = self.preprocessed_dir / output_name

            # Check if already processed
            if (output_file.with_suffix('.dim')).exists():
                logger.info(f"[{i}/{len(zip_files)}] Already processed: {output_name}")
                success_count += 1
                continue

            logger.info(f"[{i}/{len(zip_files)}] Processing: {zip_file.name}")

            # Build GPT command
            cmd = [
                self.snap_gpt_path,
                self.graph_xml,
                f'-PmyFilename={str(zip_file.absolute())}',
                f'-PoutputFile={str(output_file.absolute())}',
                '-c', self.cache_size,
                '-q', '16'
            ]

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=3600  # 1 hour timeout
                )

                if result.returncode == 0 and output_file.with_suffix('.dim').exists():
                    logger.info(f"  ✓ Processed successfully")
                    success_count += 1
                else:
                    logger.error(f"  ✗ Processing failed")
                    if result.stderr:
                        logger.error(f"  Error: {result.stderr[-500:]}")

            except subprocess.TimeoutExpired:
                logger.error(f"  ✗ Processing timeout (>1 hour)")
            except Exception as e:
                logger.error(f"  ✗ Error: {e}")

        logger.info(f"\nProcessed {success_count}/{len(zip_files)} files")
        return success_count > 0

    def step2_convert_to_geotiff(self) -> bool:
        """
        Convert preprocessed .dim files to GeoTIFF

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"STEP 2: CONVERT TO GEOTIFF")
        logger.info(f"{'='*70}")

        try:
            import rasterio
        except ImportError:
            logger.error("rasterio not installed. Run: pip install rasterio")
            return False

        # Get all .dim files
        dim_files = sorted(self.preprocessed_dir.glob('*.dim'))
        if not dim_files:
            logger.warning(f"No preprocessed files found in {self.preprocessed_dir}")
            return False

        logger.info(f"Found {len(dim_files)} preprocessed files")

        success_count = 0
        for i, dim_file in enumerate(dim_files, 1):
            # Find VH data file
            data_dir = dim_file.with_suffix('.data')
            vh_file = data_dir / 'Gamma0_VH_db.img'

            if not vh_file.exists():
                logger.warning(f"[{i}/{len(dim_files)}] VH file not found: {vh_file}")
                continue

            # Output GeoTIFF
            output_tif = self.geotiff_dir / f"{dim_file.stem}_VH.tif"

            if output_tif.exists():
                logger.info(f"[{i}/{len(dim_files)}] Already converted: {output_tif.name}")
                success_count += 1
                continue

            logger.info(f"[{i}/{len(dim_files)}] Converting: {dim_file.name}")

            try:
                with rasterio.open(vh_file) as src:
                    data = src.read(1)
                    profile = src.profile.copy()

                    # Update profile for GeoTIFF
                    profile.update(
                        driver='GTiff',
                        compress='lzw',
                        tiled=True,
                        blockxsize=512,
                        blockysize=512
                    )

                    with rasterio.open(output_tif, 'w', **profile) as dst:
                        dst.write(data, 1)

                logger.info(f"  ✓ Converted")
                success_count += 1

            except Exception as e:
                logger.error(f"  ✗ Conversion failed: {e}")

        logger.info(f"\nConverted {success_count}/{len(dim_files)} files")
        return success_count > 0

    def step3_mosaic(self) -> bool:
        """
        Mosaic all GeoTIFF files using gdal_merge.py

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"STEP 3: MOSAIC WITH GDAL_MERGE.PY")
        logger.info(f"{'='*70}")

        # Get all GeoTIFF files
        geotiff_files = sorted(self.geotiff_dir.glob('*_VH.tif'))

        # Exclude test subdirectory
        geotiff_files = [f for f in geotiff_files if 'test' not in str(f)]

        if not geotiff_files:
            logger.error(f"No GeoTIFF files found in {self.geotiff_dir}")
            return False

        logger.info(f"Found {len(geotiff_files)} GeoTIFF files")

        # Output mosaic file
        period_name = self.period_dir.name
        output_mosaic = self.mosaic_dir / f"{period_name}_mosaic.tif"

        if output_mosaic.exists():
            logger.warning(f"Mosaic already exists: {output_mosaic}")
            response = input("Overwrite? (y/n): ")
            if response.lower() != 'y':
                logger.info("Skipping mosaic creation")
                return True

        # Mosaic with gdal_merge.py
        if len(geotiff_files) == 1:
            # Single file - just copy
            logger.info("Single file, copying...")
            import shutil
            shutil.copy(geotiff_files[0], output_mosaic)
            logger.info(f"  ✓ Copied to: {output_mosaic.name}")
        else:
            # Multiple files - use gdal_merge.py
            logger.info(f"Mosaicking {len(geotiff_files)} files with gdal_merge.py...")
            logger.info("  Overlaps will be averaged (seamless blending)")

            # Build gdal_merge.py command
            # Note: Input files from SNAP have 0 as nodata
            cmd = [
                'gdal_merge.py',
                '-ot', 'Int16',
                '-of', 'GTiff',
                '-co', 'COMPRESS=LZW',
                '-co', 'TILED=YES',
                '-co', 'BIGTIFF=YES',
                '-a_nodata', '-32768',
                '-n', '0',  # Input nodata is 0 from SNAP
                '-init', '-32768',  # Initialize output with nodata
                '-o', str(output_mosaic)
            ]

            # Add all input files
            cmd.extend([str(f) for f in geotiff_files])

            try:
                # Run gdal_merge.py
                result = subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True
                )

                logger.info(f"  ✓ Mosaic created: {output_mosaic.name}")

            except subprocess.CalledProcessError as e:
                logger.error(f"  ✗ gdal_merge.py failed: {e.stderr}")
                return False
            except Exception as e:
                logger.error(f"  ✗ Mosaicking failed: {e}")
                return False

        # Verify mosaic
        try:
            import rasterio
            with rasterio.open(output_mosaic) as src:
                logger.info(f"\nMosaic verification:")
                logger.info(f"  File: {output_mosaic.name}")
                logger.info(f"  Size: {output_mosaic.stat().st_size / 1e9:.2f} GB")
                logger.info(f"  Shape: {src.height} x {src.width}")
                logger.info(f"  CRS: {src.crs}")
                logger.info(f"  Bounds: {src.bounds}")
        except Exception as e:
            logger.warning(f"Could not verify mosaic: {e}")

        return True

    def step4_create_preview(self) -> bool:
        """
        Create a preview image of the mosaic

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"STEP 4: CREATE PREVIEW")
        logger.info(f"{'='*70}")

        try:
            import rasterio
            import numpy as np
            import matplotlib.pyplot as plt
        except ImportError as e:
            logger.error(f"Required packages not installed: {e}")
            return False

        # Find mosaic file
        period_name = self.period_dir.name
        mosaic_file = self.mosaic_dir / f"{period_name}_mosaic.tif"

        if not mosaic_file.exists():
            logger.error(f"Mosaic file not found: {mosaic_file}")
            return False

        logger.info(f"Creating preview for: {mosaic_file.name}")

        try:
            with rasterio.open(mosaic_file) as src:
                # Downsample for preview (factor of 50)
                factor = 50
                out_height = max(1, src.height // factor)
                out_width = max(1, src.width // factor)
                data = src.read(1, out_shape=(out_height, out_width))

                # Get bounds for extent
                bounds = src.bounds

                # Mask nodata
                nodata = src.nodata
                if nodata is not None:
                    data = np.ma.masked_equal(data, nodata)

            # Create preview figure
            fig, ax = plt.subplots(figsize=(14, 8))

            # Plot with geographic extent
            extent = [bounds.left, bounds.right, bounds.bottom, bounds.top]
            im = ax.imshow(data, cmap='gray', extent=extent, vmin=-25, vmax=-5)

            ax.set_xlabel('Longitude')
            ax.set_ylabel('Latitude')
            ax.set_title(f'{period_name.upper()} Mosaic\nSentinel-1 VH Backscatter (dB)')

            # Add colorbar
            cbar = plt.colorbar(im, ax=ax, shrink=0.8)
            cbar.set_label('VH Backscatter (dB)')

            # Save preview
            preview_path = self.mosaic_dir / f"{period_name}_preview.png"
            plt.savefig(preview_path, dpi=150, bbox_inches='tight')
            plt.close()

            logger.info(f"  ✓ Preview saved: {preview_path.name}")
            return True

        except Exception as e:
            logger.error(f"  ✗ Preview creation failed: {e}")
            return False

    def run_all(self):
        """Run all steps"""
        logger.info(f"\n{'='*70}")
        logger.info(f"PROCESSING PERIOD DIRECTORY: {self.period_dir.name}")
        logger.info(f"{'='*70}")

        # Step 1: Preprocess
        if not self.step1_preprocess():
            logger.error("Preprocessing failed or skipped")

        # Step 2: Convert to GeoTIFF
        if not self.step2_convert_to_geotiff():
            logger.error("Conversion failed or skipped")

        # Step 3: Mosaic
        if not self.step3_mosaic():
            logger.error("Mosaicking failed or skipped")

        # Step 4: Create Preview
        if not self.step4_create_preview():
            logger.error("Preview creation failed or skipped")
        else:
            logger.info(f"\n{'='*70}")
            logger.info("✓ PROCESSING COMPLETE")
            logger.info(f"{'='*70}")
            logger.info(f"Mosaic saved to: {self.mosaic_dir}")
            logger.info(f"Preview saved to: {self.mosaic_dir}")


def main():
    parser = argparse.ArgumentParser(
        description='Process Sentinel-1 data in period directory',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process current directory at 20m resolution (default)
  cd workspace/year_2024/p15
  python s1_process_period_dir.py --run-all

  # Process at different resolutions
  python s1_process_period_dir.py --run-all --resolution 10   # 10m (highest detail)
  python s1_process_period_dir.py --run-all --resolution 20   # 20m (recommended)
  python s1_process_period_dir.py --run-all --resolution 50   # 50m (faster)
  python s1_process_period_dir.py --run-all --resolution 100  # 100m (quickest)

  # Individual steps
  python s1_process_period_dir.py --preprocess
  python s1_process_period_dir.py --convert
  python s1_process_period_dir.py --mosaic
  python s1_process_period_dir.py --preview

  # Specify directory
  python s1_process_period_dir.py --period-dir path/to/p15 --run-all
        """
    )

    parser.add_argument('--period-dir', default='.',
                        help='Period directory (default: current directory)')
    parser.add_argument('--resolution', type=int, default=20, choices=[10, 20, 50, 100],
                        help='Output resolution in meters (default: 20)')
    parser.add_argument('--snap-gpt-path', default='gpt',
                        help='Path to SNAP GPT executable (default: gpt from PATH)')
    parser.add_argument('--graph-xml', default=None,
                        help='SNAP processing graph XML file (auto-selected based on resolution)')
    parser.add_argument('--cache-size', default='16G',
                        help='SNAP cache size (default: 16G)')

    # Actions
    parser.add_argument('--preprocess', action='store_true',
                        help='Preprocess downloads')
    parser.add_argument('--convert', action='store_true',
                        help='Convert to GeoTIFF')
    parser.add_argument('--mosaic', action='store_true',
                        help='Create mosaic')
    parser.add_argument('--preview', action='store_true',
                        help='Create preview image of mosaic')
    parser.add_argument('--run-all', action='store_true',
                        help='Run all steps')

    args = parser.parse_args()

    # Initialize processor
    processor = PeriodDirectoryProcessor(
        period_dir=args.period_dir,
        snap_gpt_path=args.snap_gpt_path,
        graph_xml=args.graph_xml,
        resolution=args.resolution,
        cache_size=args.cache_size
    )

    # Execute requested actions
    if args.run_all:
        processor.run_all()
    elif args.preprocess:
        processor.step1_preprocess()
    elif args.convert:
        processor.step2_convert_to_geotiff()
    elif args.mosaic:
        processor.step3_mosaic()
    elif args.preview:
        processor.step4_create_preview()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
