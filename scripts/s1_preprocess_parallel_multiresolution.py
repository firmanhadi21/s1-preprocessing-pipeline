#!/usr/bin/env python3
"""
Multi-Resolution Parallel Sentinel-1 Preprocessing with SNAP GPT

Processes multiple Sentinel-1 scenes in parallel with configurable spatial resolution
Optimized for operational-scale processing (province/national level)

NEW FEATURES:
- Support for multiple resolutions: 10m, 20m, 50m, 100m
- Automatic graph XML selection based on resolution
- Optimized memory settings per resolution
- Processing time estimation
- Storage requirement estimation

Resolution Guide:
- 10m: High-detail mapping, small fields (>0.1 ha), processing time: 2h/scene
- 20m: Detailed mapping, medium fields (>0.25 ha), processing time: 30min/scene
- 50m: Operational mapping, large fields (>0.5 ha), processing time: 6-8min/scene
- 100m: Rapid monitoring, very large areas, processing time: 2-3min/scene

Usage:
  # Indonesia-wide processing (50m for 2-week target)
  python s1_preprocess_parallel_multiresolution.py \\
    --input-dir downloads \\
    --output-dir preprocessed_50m \\
    --resolution 50 \\
    --workers 8

  # Provincial processing (10m for detailed mapping)
  python s1_preprocess_parallel_multiresolution.py \\
    --input-dir downloads \\
    --output-dir preprocessed_10m \\
    --resolution 10 \\
    --workers 4
"""

import os
import sys
import subprocess
from pathlib import Path
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
from multiprocessing import Pool, cpu_count, Manager
import json
import argparse
from functools import partial

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(processName)s] %(message)s'
)
logger = logging.getLogger(__name__)


class MultiResolutionSNAPPreprocessor:
    """
    Multi-resolution parallel preprocessing wrapper for SNAP GPT
    """

    # Resolution-specific configurations
    # NOTE: Memory reduced to conservative defaults to avoid SNAP GPT errors
    RESOLUTION_CONFIGS = {
        10: {
            'graph_xml': 'sen1_preprocessing-gpt.xml',
            'memory_per_worker': '16G',
            'cache_per_worker': '12G',
            'avg_time_minutes': 120,  # 2 hours
            'output_size_gb': 50,
            'speckle_filter_size': 5,
            'description': 'High-detail (>0.1 ha fields)'
        },
        20: {
            'graph_xml': 'sen1_preprocessing-gpt-20m.xml',
            'memory_per_worker': '12G',
            'cache_per_worker': '8G',
            'avg_time_minutes': 30,
            'output_size_gb': 12,
            'speckle_filter_size': 5,
            'description': 'Detailed (>0.25 ha fields)'
        },
        50: {
            'graph_xml': 'sen1_preprocessing-gpt-50m.xml',
            'memory_per_worker': '8G',
            'cache_per_worker': '6G',
            'avg_time_minutes': 7,  # 6-8 minutes
            'output_size_gb': 2,
            'speckle_filter_size': 3,
            'description': 'Operational (>0.5 ha fields)'
        },
        100: {
            'graph_xml': 'sen1_preprocessing-gpt-100m.xml',
            'memory_per_worker': '6G',
            'cache_per_worker': '4G',
            'avg_time_minutes': 2.5,
            'output_size_gb': 0.5,
            'speckle_filter_size': 3,
            'description': 'Rapid monitoring (>1 ha fields)'
        }
    }

    def __init__(self, snap_gpt_path=None, num_workers=4,
                 resolution=50, custom_memory=None, custom_cache=None):
        """
        Initialize multi-resolution preprocessor

        Args:
            snap_gpt_path: Path to SNAP GPT executable (None = auto-detect)
            num_workers: Number of parallel workers
            resolution: Spatial resolution in meters (10, 20, 50, or 100)
            custom_memory: Override memory per worker (e.g., '50G')
            custom_cache: Override cache per worker (e.g., '40G')
        """
        if resolution not in self.RESOLUTION_CONFIGS:
            raise ValueError(f"Resolution must be one of {list(self.RESOLUTION_CONFIGS.keys())}")

        self.resolution = resolution
        self.config = self.RESOLUTION_CONFIGS[resolution]
        self.gpt_path = snap_gpt_path or self._find_gpt()
        self.num_workers = num_workers

        # Use custom or default memory settings
        self.memory_per_worker = custom_memory or self.config['memory_per_worker']
        self.cache_per_worker = custom_cache or self.config['cache_per_worker']
        self.graph_xml = self.config['graph_xml']

        if not self.gpt_path:
            raise FileNotFoundError("SNAP GPT not found. Please install SNAP.")

        # Validate graph XML exists
        if not Path(self.graph_xml).exists():
            raise FileNotFoundError(f"Graph XML not found: {self.graph_xml}")

        self._print_configuration()

    def _print_configuration(self):
        """Print configuration summary"""
        logger.info("="*70)
        logger.info("MULTI-RESOLUTION PARALLEL SNAP PREPROCESSOR")
        logger.info("="*70)
        logger.info(f"Resolution: {self.resolution}m ({self.config['description']})")
        logger.info(f"Graph XML: {self.graph_xml}")
        logger.info(f"SNAP GPT: {self.gpt_path}")
        logger.info(f"Number of workers: {self.num_workers}")
        logger.info(f"Memory per worker: {self.memory_per_worker}")
        logger.info(f"Cache per worker: {self.cache_per_worker}")
        logger.info(f"Total memory usage: ~{self._estimate_total_memory()}")
        logger.info(f"Expected time per scene: ~{self.config['avg_time_minutes']} min")
        logger.info(f"Expected output size: ~{self.config['output_size_gb']} GB/scene")
        logger.info("="*70)

    def estimate_processing_time(self, n_scenes: int) -> Dict[str, str]:
        """
        Estimate total processing time

        Args:
            n_scenes: Number of scenes to process

        Returns:
            Dictionary with time estimates
        """
        minutes_per_scene = self.config['avg_time_minutes']

        # Serial processing
        serial_minutes = n_scenes * minutes_per_scene

        # Parallel processing
        parallel_minutes = (n_scenes * minutes_per_scene) / self.num_workers

        # Add 10% buffer for overhead
        parallel_minutes *= 1.1

        serial_time = timedelta(minutes=serial_minutes)
        parallel_time = timedelta(minutes=parallel_minutes)

        # Storage estimate
        total_storage_gb = n_scenes * self.config['output_size_gb']

        return {
            'n_scenes': n_scenes,
            'resolution': f"{self.resolution}m",
            'serial_time': str(serial_time),
            'parallel_time': str(parallel_time),
            'parallel_days': parallel_minutes / (60 * 24),
            'storage_gb': total_storage_gb,
            'storage_tb': total_storage_gb / 1024
        }

    def print_time_estimate(self, n_scenes: int):
        """Print processing time estimate"""
        est = self.estimate_processing_time(n_scenes)

        logger.info("\n" + "="*70)
        logger.info("PROCESSING TIME ESTIMATE")
        logger.info("="*70)
        logger.info(f"Number of scenes: {est['n_scenes']}")
        logger.info(f"Resolution: {est['resolution']}")
        logger.info(f"Serial processing time: {est['serial_time']}")
        logger.info(f"Parallel processing time ({self.num_workers} workers): {est['parallel_time']}")
        logger.info(f"Parallel processing days: {est['parallel_days']:.2f} days")
        logger.info(f"Expected storage: {est['storage_gb']:.1f} GB ({est['storage_tb']:.2f} TB)")
        logger.info("="*70 + "\n")

    def _find_gpt(self) -> Optional[str]:
        """Find SNAP GPT executable in PATH"""
        import shutil
        gpt = shutil.which('gpt')
        if gpt:
            return gpt

        # Try common locations
        common_paths = [
            '/usr/local/snap/bin/gpt',
            '/opt/snap/bin/gpt',
            os.path.expanduser('~/snap/bin/gpt'),
            os.path.expanduser('~/work/idmai/esa-snap/bin/gpt'),
        ]

        for path in common_paths:
            if os.path.exists(path):
                return path

        return None

    def _estimate_total_memory(self) -> str:
        """Estimate total memory usage"""
        try:
            mem_value = int(''.join(filter(str.isdigit, self.memory_per_worker)))
            total = mem_value * self.num_workers
            return f"{total}G"
        except:
            return "Unknown"

    def process_single_scene(self, input_file: str, output_dir: str,
                            status_dict: dict) -> Tuple[str, bool, str]:
        """
        Process a single Sentinel-1 scene

        Args:
            input_file: Input .zip file
            output_dir: Output directory
            status_dict: Shared status dictionary

        Returns:
            (input_file, success, output_file)
        """
        import tempfile
        import shutil

        input_path = Path(input_file)
        input_name = input_path.stem

        # Generate output filename with resolution tag
        output_tif = Path(output_dir) / f"{input_name}_VH_{self.resolution}m.tif"

        # Check if already processed
        if output_tif.exists():
            logger.info(f"✓ SKIP (already exists): {input_path.name}")
            status_dict[input_file] = 'skipped'
            return (input_file, True, str(output_tif))

        logger.info(f"START [{self.resolution}m]: {input_path.name}")
        status_dict[input_file] = 'processing'

        # Create temporary output for BEAM-DIMAP (use absolute path)
        temp_output = Path(output_dir).absolute() / f"{input_name}_temp_{self.resolution}m"

        # Create unique cache directory for this process to avoid conflicts
        cache_dir = tempfile.mkdtemp(prefix=f"snap_cache_{input_name}_")

        # Build GPT command with unique cache directory
        # NOTE: Use -P parameters to pass both input and output paths to the graph
        cmd = [
            self.gpt_path,
            self.graph_xml,
            f'-PmyFilename={Path(input_file).absolute()}',  # Input file parameter
            f'-PoutputFile={temp_output}',  # Output file parameter (no extension)
            '-c', self.cache_per_worker,  # Cache size
        ]

        # Create isolated environment for SNAP to avoid cache conflicts
        env = os.environ.copy()
        env['_JAVA_OPTIONS'] = f'-Djava.io.tmpdir={cache_dir}'

        # Create error log file for detailed debugging (use absolute path)
        error_log = Path(output_dir).absolute() / f"{input_name}_error.log"

        start_time = datetime.now()

        try:
            # Run GPT with timeout based on resolution
            # 50m should be ~10x faster than 10m
            timeout_multiplier = {10: 7200, 20: 3600, 50: 900, 100: 450}
            timeout = timeout_multiplier.get(self.resolution, 3600)

            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                timeout=timeout,
                env=env  # Use isolated environment
            )

            if result.returncode != 0:
                logger.error(f"FAILED [{self.resolution}m]: {input_path.name}")
                # Save full error to file for debugging
                with open(error_log, 'w') as f:
                    f.write(f"Command: {' '.join(cmd)}\n\n")
                    f.write(f"Return code: {result.returncode}\n\n")
                    f.write(f"Full output:\n{result.stdout}\n")
                logger.error(f"Full error saved to: {error_log}")
                logger.error(f"GPT Error (last 500 chars): {result.stdout[-500:]}")
                status_dict[input_file] = 'failed'
                # Clean up cache directory
                shutil.rmtree(cache_dir, ignore_errors=True)
                return (input_file, False, "")

            # Convert to GeoTIFF and extract VH band
            dim_file = f"{temp_output}.dim"
            if Path(dim_file).exists():
                success = self._extract_vh_to_geotiff(dim_file, str(output_tif))

                if success:
                    # Clean up BEAM-DIMAP files and cache directory
                    self._cleanup_temp_files(temp_output)
                    shutil.rmtree(cache_dir, ignore_errors=True)

                    elapsed = datetime.now() - start_time
                    logger.info(f"✓ DONE ({elapsed}) [{self.resolution}m]: {input_path.name}")
                    status_dict[input_file] = 'completed'
                    return (input_file, True, str(output_tif))
                else:
                    logger.error(f"FAILED (GeoTIFF conversion) [{self.resolution}m]: {input_path.name}")
                    status_dict[input_file] = 'failed'
                    shutil.rmtree(cache_dir, ignore_errors=True)
                    return (input_file, False, "")
            else:
                logger.error(f"FAILED (no output) [{self.resolution}m]: {input_path.name}")
                status_dict[input_file] = 'failed'
                shutil.rmtree(cache_dir, ignore_errors=True)
                return (input_file, False, "")

        except subprocess.TimeoutExpired:
            logger.error(f"TIMEOUT [{self.resolution}m]: {input_path.name}")
            status_dict[input_file] = 'timeout'
            shutil.rmtree(cache_dir, ignore_errors=True)
            return (input_file, False, "")
        except Exception as e:
            logger.error(f"ERROR [{self.resolution}m]: {input_path.name} - {str(e)}")
            status_dict[input_file] = 'error'
            shutil.rmtree(cache_dir, ignore_errors=True)
            return (input_file, False, "")

    def _extract_vh_to_geotiff(self, dim_file: str, output_tif: str) -> bool:
        """Extract VH band from BEAM-DIMAP to GeoTIFF"""
        try:
            from osgeo import gdal

            # Don't use exceptions - causes issues with ENVI driver
            gdal.DontUseExceptions()

            # Verify .dim file exists
            if not Path(dim_file).exists():
                logger.error(f"DIM file does not exist: {dim_file}")
                return False

            # BEAM-DIMAP stores data in a .data directory
            # Find the VH .img file (not .hdr!)
            data_dir = Path(dim_file).with_suffix('.data')
            if not data_dir.exists():
                logger.error(f"Data directory does not exist: {data_dir}")
                return False

            # Look for Gamma0_VH_db.img file
            vh_img_file = data_dir / 'Gamma0_VH_db.img'
            if not vh_img_file.exists():
                # Try alternate patterns
                vh_files = list(data_dir.glob('*VH*db.img'))
                if vh_files:
                    vh_img_file = vh_files[0]
                else:
                    logger.error(f"No VH .img file found in {data_dir}")
                    return False

            logger.debug(f"Opening VH file: {vh_img_file}")

            # Open the ENVI .img file directly
            dataset = gdal.Open(str(vh_img_file), gdal.GA_ReadOnly)
            if dataset is None:
                logger.error(f"Failed to open VH file: {vh_img_file}")
                return False

            # Create GeoTIFF
            driver = gdal.GetDriverByName('GTiff')

            # Get the first (and only) band
            vh_band = dataset.GetRasterBand(1)

            out_ds = driver.Create(
                output_tif,
                dataset.RasterXSize,
                dataset.RasterYSize,
                1,
                vh_band.DataType,
                options=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES']
            )

            # Copy geotransform and projection
            out_ds.SetGeoTransform(dataset.GetGeoTransform())
            out_ds.SetProjection(dataset.GetProjection())

            # Copy data
            data = vh_band.ReadAsArray()
            out_ds.GetRasterBand(1).WriteArray(data)

            # Copy nodata value
            nodata = vh_band.GetNoDataValue()
            if nodata is not None:
                out_ds.GetRasterBand(1).SetNoDataValue(nodata)

            # Flush and close
            out_ds.FlushCache()
            out_ds = None
            dataset = None

            logger.debug(f"Successfully created GeoTIFF: {output_tif}")
            return True

        except Exception as e:
            logger.error(f"Error extracting VH band from {dim_file}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _cleanup_temp_files(self, temp_output: Path):
        """Clean up temporary BEAM-DIMAP files"""
        try:
            dim_file = Path(f"{temp_output}.dim")
            data_dir = Path(f"{temp_output}.data")

            if dim_file.exists():
                dim_file.unlink()
            if data_dir.exists():
                import shutil
                shutil.rmtree(data_dir)
        except Exception as e:
            logger.warning(f"Could not clean up temp files: {str(e)}")

    def batch_process_parallel(self, input_files: List[str], output_dir: str,
                               status_file: str = None) -> Dict:
        """
        Process multiple scenes in parallel

        Args:
            input_files: List of input .zip files
            output_dir: Output directory
            status_file: File to save processing status (auto-generated if None)

        Returns:
            Dictionary with processing statistics
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Auto-generate status filename with resolution
        if status_file is None:
            status_file = f'processing_status_{self.resolution}m.json'

        # Load previous status if exists
        status_path = output_path / status_file
        if status_path.exists():
            with open(status_path, 'r') as f:
                previous_status = json.load(f)
            logger.info(f"Loaded previous status: {len(previous_status)} entries")
        else:
            previous_status = {}

        # Filter out already completed files
        remaining_files = [
            f for f in input_files
            if previous_status.get(f, '') not in ['completed', 'skipped']
        ]

        logger.info(f"\nTotal files: {len(input_files)}")
        logger.info(f"Already processed: {len(input_files) - len(remaining_files)}")
        logger.info(f"Remaining to process: {len(remaining_files)}\n")

        if not remaining_files:
            logger.info("All files already processed!")
            return {'total': len(input_files), 'completed': len(input_files), 'failed': 0}

        # Print time estimate
        self.print_time_estimate(len(remaining_files))

        # Create shared status dictionary
        with Manager() as manager:
            status_dict = manager.dict(previous_status)

            # Create partial function with fixed arguments
            process_func = partial(
                self.process_single_scene,
                output_dir=output_dir,
                status_dict=status_dict
            )

            # Process in parallel
            logger.info(f"Starting parallel processing with {self.num_workers} workers...")
            start_time = datetime.now()

            with Pool(processes=self.num_workers) as pool:
                results = pool.map(process_func, remaining_files)

            # Save status
            final_status = dict(status_dict)
            with open(status_path, 'w') as f:
                json.dump(final_status, f, indent=2)

            # Calculate statistics
            completed = sum(1 for _, success, _ in results if success)
            failed = len(results) - completed

            elapsed = datetime.now() - start_time
            avg_time = elapsed / len(results) if results else timedelta(0)

            # Calculate throughput
            scenes_per_hour = (len(results) / (elapsed.total_seconds() / 3600)) if elapsed.total_seconds() > 0 else 0

            # Print summary
            logger.info("\n" + "="*70)
            logger.info("PARALLEL PROCESSING SUMMARY")
            logger.info("="*70)
            logger.info(f"Resolution: {self.resolution}m")
            logger.info(f"Total files processed: {len(results)}")
            logger.info(f"Successful: {completed}")
            logger.info(f"Failed: {failed}")
            logger.info(f"Total time: {elapsed}")
            logger.info(f"Average time per scene: {avg_time}")
            logger.info(f"Throughput: {scenes_per_hour:.2f} scenes/hour")
            logger.info(f"Status saved to: {status_path}")
            logger.info("="*70)

            return {
                'resolution': self.resolution,
                'total': len(results),
                'completed': completed,
                'failed': failed,
                'elapsed': str(elapsed),
                'avg_time_per_scene': str(avg_time),
                'scenes_per_hour': scenes_per_hour
            }


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Multi-Resolution Parallel Sentinel-1 preprocessing with SNAP GPT',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Resolution Guide:
  10m : High-detail mapping, small fields (>0.1 ha), ~2h/scene
  20m : Detailed mapping, medium fields (>0.25 ha), ~30min/scene
  50m : Operational mapping, large fields (>0.5 ha), ~7min/scene [RECOMMENDED FOR INDONESIA]
  100m: Rapid monitoring, very large areas, ~2.5min/scene

Examples:
  # Indonesia-wide operational mapping (50m, 2-week target)
  python s1_preprocess_parallel_multiresolution.py \\
    --input-dir downloads \\
    --output-dir preprocessed_50m \\
    --resolution 50 \\
    --workers 8

  # Provincial detailed mapping (10m)
  python s1_preprocess_parallel_multiresolution.py \\
    --input-dir downloads \\
    --output-dir preprocessed_10m \\
    --resolution 10 \\
    --workers 4

  # Rapid national monitoring (100m)
  python s1_preprocess_parallel_multiresolution.py \\
    --input-dir downloads \\
    --output-dir preprocessed_100m \\
    --resolution 100 \\
    --workers 8

  # Estimate processing time only (dry-run)
  python s1_preprocess_parallel_multiresolution.py \\
    --input-dir downloads \\
    --output-dir preprocessed_50m \\
    --resolution 50 \\
    --workers 8 \\
    --estimate-only
        """
    )

    parser.add_argument('--input-dir', required=True,
                       help='Directory containing .zip files')
    parser.add_argument('--output-dir', required=True,
                       help='Output directory for processed files')
    parser.add_argument('--resolution', type=int, choices=[10, 20, 50, 100], default=50,
                       help='Spatial resolution in meters (default: 50)')
    parser.add_argument('--workers', type=int, default=4,
                       help='Number of parallel workers (default: 4)')
    parser.add_argument('--memory',
                       help='Memory per worker (default: auto based on resolution)')
    parser.add_argument('--cache',
                       help='Cache size per worker (default: auto based on resolution)')
    parser.add_argument('--gpt-path',
                       help='Path to SNAP GPT executable (default: auto-detect)')
    parser.add_argument('--pattern', default='*.zip',
                       help='File pattern to match (default: *.zip)')
    parser.add_argument('--estimate-only', action='store_true',
                       help='Only estimate processing time, do not process')

    args = parser.parse_args()

    # Find input files
    input_dir = Path(args.input_dir)
    input_files = sorted(input_dir.glob(args.pattern))

    if not input_files:
        logger.error(f"No files matching '{args.pattern}' found in {input_dir}")
        sys.exit(1)

    logger.info(f"Found {len(input_files)} files to process")

    # Initialize preprocessor
    try:
        preprocessor = MultiResolutionSNAPPreprocessor(
            snap_gpt_path=args.gpt_path,
            num_workers=args.workers,
            resolution=args.resolution,
            custom_memory=args.memory,
            custom_cache=args.cache
        )
    except (ValueError, FileNotFoundError) as e:
        logger.error(str(e))
        sys.exit(1)

    # Estimate only mode
    if args.estimate_only:
        preprocessor.print_time_estimate(len(input_files))
        logger.info("Estimate-only mode. Exiting without processing.")
        sys.exit(0)

    # Process
    stats = preprocessor.batch_process_parallel(
        input_files=[str(f) for f in input_files],
        output_dir=args.output_dir
    )

    # Exit with error if any failed
    if stats['failed'] > 0:
        logger.warning(f"\n⚠ {stats['failed']} files failed processing")
        logger.info(f"Check processing_status_{args.resolution}m.json for details")
        sys.exit(1)
    else:
        logger.info("\n✓ All files processed successfully!")
        sys.exit(0)


if __name__ == '__main__':
    main()
