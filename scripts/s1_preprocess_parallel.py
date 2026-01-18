#!/usr/bin/env python3
"""
Parallel Sentinel-1 Preprocessing with SNAP GPT

Processes multiple Sentinel-1 scenes in parallel using multiprocessing
Optimized for high-memory systems (2TB RAM, 128 cores)

Features:
- Parallel processing of multiple scenes
- Automatic memory allocation per worker
- Progress tracking with status file
- Resume capability (skips already processed files)
- Error handling and retry logic
"""

import os
import sys
import subprocess
from pathlib import Path
import logging
from datetime import datetime
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


class ParallelSNAPPreprocessor:
    """
    Parallel preprocessing wrapper for SNAP GPT
    """

    def __init__(self, snap_gpt_path=None, num_workers=4,
                 memory_per_worker='200G', cache_per_worker='150G'):
        """
        Initialize parallel preprocessor

        Args:
            snap_gpt_path: Path to SNAP GPT executable (None = auto-detect)
            num_workers: Number of parallel workers
            memory_per_worker: Max memory per worker (e.g., '200G')
            cache_per_worker: Cache size per worker (e.g., '150G')
        """
        self.gpt_path = snap_gpt_path or self._find_gpt()
        self.num_workers = num_workers
        self.memory_per_worker = memory_per_worker
        self.cache_per_worker = cache_per_worker

        if not self.gpt_path:
            raise FileNotFoundError("SNAP GPT not found. Please install SNAP.")

        logger.info("="*60)
        logger.info("PARALLEL SNAP PREPROCESSOR INITIALIZED")
        logger.info("="*60)
        logger.info(f"SNAP GPT: {self.gpt_path}")
        logger.info(f"Number of workers: {self.num_workers}")
        logger.info(f"Memory per worker: {self.memory_per_worker}")
        logger.info(f"Cache per worker: {self.cache_per_worker}")
        logger.info(f"Total memory usage: ~{self._estimate_total_memory()}")
        logger.info("="*60)


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
                            graph_xml: str, status_dict: dict) -> Tuple[str, bool, str]:
        """
        Process a single Sentinel-1 scene

        Args:
            input_file: Input .zip file
            output_dir: Output directory
            graph_xml: SNAP graph XML
            status_dict: Shared status dictionary

        Returns:
            (input_file, success, output_file)
        """
        input_path = Path(input_file)
        input_name = input_path.stem

        # Generate output filename
        output_tif = Path(output_dir) / f"{input_name}_VH.tif"

        # Check if already processed
        if output_tif.exists():
            logger.info(f"✓ SKIP (already exists): {input_path.name}")
            status_dict[input_file] = 'skipped'
            return (input_file, True, str(output_tif))

        logger.info(f"START: {input_path.name}")
        status_dict[input_file] = 'processing'

        # Create temporary output for BEAM-DIMAP
        temp_output = Path(output_dir) / f"{input_name}_temp"

        # Build GPT command
        cmd = [
            self.gpt_path,
            graph_xml,
            f'-PmyFilename={input_file}',
            f'-t{temp_output}',
            f'-c{self.cache_per_worker}',
        ]

        start_time = datetime.now()

        try:
            # Run GPT
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                timeout=7200  # 2 hour timeout per scene
            )

            if result.returncode != 0:
                logger.error(f"FAILED: {input_path.name}")
                logger.error(f"GPT Error: {result.stdout[-500:]}")  # Last 500 chars
                status_dict[input_file] = 'failed'
                return (input_file, False, "")

            # Convert to GeoTIFF and extract VH band
            dim_file = f"{temp_output}.dim"
            if Path(dim_file).exists():
                success = self._extract_vh_to_geotiff(dim_file, str(output_tif))

                if success:
                    # Clean up BEAM-DIMAP files
                    self._cleanup_temp_files(temp_output)

                    elapsed = datetime.now() - start_time
                    logger.info(f"✓ DONE ({elapsed}): {input_path.name}")
                    status_dict[input_file] = 'completed'
                    return (input_file, True, str(output_tif))
                else:
                    logger.error(f"FAILED (GeoTIFF conversion): {input_path.name}")
                    status_dict[input_file] = 'failed'
                    return (input_file, False, "")
            else:
                logger.error(f"FAILED (no output): {input_path.name}")
                status_dict[input_file] = 'failed'
                return (input_file, False, "")

        except subprocess.TimeoutExpired:
            logger.error(f"TIMEOUT: {input_path.name}")
            status_dict[input_file] = 'timeout'
            return (input_file, False, "")
        except Exception as e:
            logger.error(f"ERROR: {input_path.name} - {str(e)}")
            status_dict[input_file] = 'error'
            return (input_file, False, "")


    def _extract_vh_to_geotiff(self, dim_file: str, output_tif: str) -> bool:
        """Extract VH band from BEAM-DIMAP to GeoTIFF"""
        try:
            from osgeo import gdal

            # Open DIM file
            dataset = gdal.Open(dim_file)
            if dataset is None:
                return False

            # Find VH band
            vh_band_idx = None
            for i in range(1, dataset.RasterCount + 1):
                band = dataset.GetRasterBand(i)
                desc = band.GetDescription()
                # Look for VH band in dB
                if 'VH' in desc and ('db' in desc.lower() or 'dB' in desc):
                    vh_band_idx = i
                    break

            if vh_band_idx is None:
                logger.warning(f"VH band not found in {dim_file}, using band 1")
                vh_band_idx = 1

            # Create GeoTIFF with VH band only
            driver = gdal.GetDriverByName('GTiff')
            vh_band = dataset.GetRasterBand(vh_band_idx)

            out_ds = driver.Create(
                output_tif,
                dataset.RasterXSize,
                dataset.RasterYSize,
                1,
                vh_band.DataType,
                options=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES']
            )

            out_ds.SetGeoTransform(dataset.GetGeoTransform())
            out_ds.SetProjection(dataset.GetProjection())
            out_ds.GetRasterBand(1).WriteArray(vh_band.ReadAsArray())

            nodata = vh_band.GetNoDataValue()
            if nodata is not None:
                out_ds.GetRasterBand(1).SetNoDataValue(nodata)

            out_ds = None
            dataset = None

            return True

        except Exception as e:
            logger.error(f"Error extracting VH band: {str(e)}")
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
                               graph_xml: str = 'sen1_preprocessing-gpt.xml',
                               status_file: str = 'processing_status.json') -> Dict:
        """
        Process multiple scenes in parallel

        Args:
            input_files: List of input .zip files
            output_dir: Output directory
            graph_xml: SNAP graph XML file
            status_file: File to save processing status

        Returns:
            Dictionary with processing statistics
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

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

        # Create shared status dictionary
        with Manager() as manager:
            status_dict = manager.dict(previous_status)

            # Create partial function with fixed arguments
            process_func = partial(
                self.process_single_scene,
                output_dir=output_dir,
                graph_xml=graph_xml,
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

            # Print summary
            logger.info("\n" + "="*60)
            logger.info("PARALLEL PROCESSING SUMMARY")
            logger.info("="*60)
            logger.info(f"Total files processed: {len(results)}")
            logger.info(f"Successful: {completed}")
            logger.info(f"Failed: {failed}")
            logger.info(f"Total time: {elapsed}")
            logger.info(f"Average time per scene: {elapsed / len(results) if results else 0}")
            logger.info(f"Status saved to: {status_path}")
            logger.info("="*60)

            return {
                'total': len(results),
                'completed': completed,
                'failed': failed,
                'elapsed': str(elapsed)
            }


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Parallel Sentinel-1 preprocessing with SNAP GPT',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process with 4 workers (conservative)
  python s1_preprocess_parallel.py --input-dir downloads --output-dir preprocessed --workers 4

  # Aggressive: 8 workers for faster processing
  python s1_preprocess_parallel.py --input-dir downloads --output-dir preprocessed --workers 8 --memory 100G --cache 80G

  # Resume interrupted processing
  python s1_preprocess_parallel.py --input-dir downloads --output-dir preprocessed --workers 4
        """
    )

    parser.add_argument('--input-dir', required=True,
                       help='Directory containing .zip files')
    parser.add_argument('--output-dir', required=True,
                       help='Output directory for processed files')
    parser.add_argument('--graph', default='sen1_preprocessing-gpt.xml',
                       help='SNAP graph XML file (default: sen1_preprocessing-gpt.xml)')
    parser.add_argument('--workers', type=int, default=4,
                       help='Number of parallel workers (default: 4, recommended: 4-8)')
    parser.add_argument('--memory', default='200G',
                       help='Memory per worker (default: 200G)')
    parser.add_argument('--cache', default='150G',
                       help='Cache size per worker (default: 150G)')
    parser.add_argument('--gpt-path',
                       help='Path to SNAP GPT executable (default: auto-detect)')
    parser.add_argument('--pattern', default='*.zip',
                       help='File pattern to match (default: *.zip)')

    args = parser.parse_args()

    # Find input files
    input_dir = Path(args.input_dir)
    input_files = sorted(input_dir.glob(args.pattern))

    if not input_files:
        logger.error(f"No files matching '{args.pattern}' found in {input_dir}")
        sys.exit(1)

    logger.info(f"Found {len(input_files)} files to process")

    # Validate graph XML
    if not Path(args.graph).exists():
        logger.error(f"Graph XML not found: {args.graph}")
        sys.exit(1)

    # Initialize preprocessor
    preprocessor = ParallelSNAPPreprocessor(
        snap_gpt_path=args.gpt_path,
        num_workers=args.workers,
        memory_per_worker=args.memory,
        cache_per_worker=args.cache
    )

    # Process
    stats = preprocessor.batch_process_parallel(
        input_files=[str(f) for f in input_files],
        output_dir=args.output_dir,
        graph_xml=args.graph
    )

    # Exit with error if any failed
    if stats['failed'] > 0:
        logger.warning(f"\n⚠ {stats['failed']} files failed processing")
        logger.info("Check processing_status.json for details")
        sys.exit(1)
    else:
        logger.info("\n✓ All files processed successfully!")
        sys.exit(0)


if __name__ == '__main__':
    main()
