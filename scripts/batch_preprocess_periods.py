#!/usr/bin/env python3
"""
Flexible batch preprocessing script for Sentinel-1 data
Supports processing specific periods or ranges
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

def preprocess_period(period, config):
    """Preprocess a single period"""
    input_dir = f"{config['download_base']}/downloads_p{period}"
    output_dir = f"{config['output_base']}/p{period}"
    
    year = 2024 if period <= 31 else 2025
    
    print("=" * 70)
    print(f"Processing Period {period} (Year: {year})")
    print(f"Input:  {input_dir}")
    print(f"Output: {output_dir}")
    print(f"Resolution: {config['resolution']}m | Workers: {config['workers']}")
    print("=" * 70)
    
    # Check if input directory exists
    if not os.path.exists(input_dir):
        print(f"WARNING: Input directory {input_dir} does not exist. Skipping...")
        return "skipped"
    
    # Check if input directory is empty
    files = list(Path(input_dir).glob("*.zip")) + list(Path(input_dir).glob("*.SAFE"))
    if len(files) == 0:
        print(f"WARNING: No Sentinel-1 data found in {input_dir}. Skipping...")
        return "skipped"
    
    print(f"Found {len(files)} files to process")
    
    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Build command
    cmd = [
        "python", config['script'],
        "--input-dir", input_dir,
        "--output-dir", output_dir,
        "--resolution", str(config['resolution']),
        "--workers", str(config['workers'])
    ]
    
    # Run preprocessing
    start_time = datetime.now()
    try:
        result = subprocess.run(cmd, check=True)
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"✓ Period {period} completed successfully in {elapsed:.1f}s")
        return "success"
    except subprocess.CalledProcessError as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"✗ Period {period} failed after {elapsed:.1f}s with error code {e.returncode}")
        return "failed"
    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"✗ Period {period} failed after {elapsed:.1f}s with exception: {e}")
        return "failed"

def parse_period_range(period_str):
    """Parse period range string (e.g., '1-5,10,15-20')"""
    periods = set()
    for part in period_str.split(','):
        if '-' in part:
            start, end = map(int, part.split('-'))
            periods.update(range(start, end + 1))
        else:
            periods.add(int(part))
    return sorted(periods)

def main():
    parser = argparse.ArgumentParser(
        description='Batch preprocessing for Sentinel-1 data across multiple periods',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Process all periods (1-56)
  python %(prog)s
  
  # Process specific periods
  python %(prog)s --periods 1-10
  
  # Process multiple ranges
  python %(prog)s --periods 1-5,10,15-20
  
  # Process with custom resolution and workers
  python %(prog)s --periods 1-31 --resolution 10 --workers 16
  
  # Use custom paths
  python %(prog)s --download-base data/downloads --output-base data/output
        '''
    )
    
    parser.add_argument(
        '--periods',
        type=str,
        default='1-56',
        help='Periods to process (e.g., "1-10", "1-5,10,15-20"). Default: 1-56'
    )
    parser.add_argument(
        '--script',
        type=str,
        default='s1_preprocess_parallel_multiresolution.py',
        help='Preprocessing script to use'
    )
    parser.add_argument(
        '--download-base',
        type=str,
        default='workspace/downloads',
        help='Base directory for downloads'
    )
    parser.add_argument(
        '--output-base',
        type=str,
        default='workspace/preprocessed_20m',
        help='Base directory for outputs'
    )
    parser.add_argument(
        '--resolution',
        type=int,
        default=20,
        help='Output resolution in meters'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=8,
        help='Number of parallel workers'
    )
    parser.add_argument(
        '--continue-on-error',
        action='store_true',
        help='Continue processing even if a period fails'
    )
    
    args = parser.parse_args()
    
    # Parse periods
    try:
        periods = parse_period_range(args.periods)
    except Exception as e:
        print(f"ERROR: Invalid period range '{args.periods}': {e}")
        sys.exit(1)
    
    # Check if script exists
    if not os.path.exists(args.script):
        print(f"ERROR: Script {args.script} not found!")
        sys.exit(1)
    
    # Configuration
    config = {
        'script': args.script,
        'download_base': args.download_base,
        'output_base': args.output_base,
        'resolution': args.resolution,
        'workers': args.workers
    }
    
    # Print configuration
    print("=" * 70)
    print("BATCH PREPROCESSING CONFIGURATION")
    print("=" * 70)
    print(f"Script:         {config['script']}")
    print(f"Download base:  {config['download_base']}")
    print(f"Output base:    {config['output_base']}")
    print(f"Resolution:     {config['resolution']}m")
    print(f"Workers:        {config['workers']}")
    print(f"Periods:        {min(periods)}-{max(periods)} ({len(periods)} total)")
    print(f"Continue on error: {args.continue_on_error}")
    print("=" * 70)
    print()
    
    # Track statistics
    stats = {"success": 0, "failed": 0, "skipped": 0}
    failed_periods = []
    
    overall_start = datetime.now()
    
    # Process periods
    for i, period in enumerate(periods, 1):
        print()
        print(f"[{i}/{len(periods)}] Period {period}")
        print("-" * 70)
        
        result = preprocess_period(period, config)
        stats[result] += 1
        
        if result == "failed":
            failed_periods.append(period)
            if not args.continue_on_error:
                print(f"\nERROR: Period {period} failed. Stopping batch processing.")
                print("Use --continue-on-error to continue despite failures.")
                break
    
    overall_elapsed = (datetime.now() - overall_start).total_seconds()
    
    # Print summary
    print()
    print("=" * 70)
    print("BATCH PROCESSING COMPLETE")
    print("=" * 70)
    print(f"Total time:     {overall_elapsed:.1f}s ({overall_elapsed/60:.1f} minutes)")
    print(f"Total periods:  {len(periods)}")
    print(f"Successful:     {stats['success']}")
    print(f"Skipped:        {stats['skipped']}")
    print(f"Failed:         {stats['failed']}")
    
    if failed_periods:
        print(f"\nFailed periods: {', '.join(map(str, failed_periods))}")
    
    print("=" * 70)
    
    # Exit with error code if any failed
    if stats['failed'] > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
