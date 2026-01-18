#!/usr/bin/env python3
"""
Batch mosaicking script for preprocessed Sentinel-1 data
Mosaics all periods (1-56) using OTB Mosaic with feathering and harmonization
"""

import os
import sys
import argparse
import subprocess
import glob
from pathlib import Path
from datetime import datetime

def mosaic_period(period, config):
    """Mosaic a single period using OTB"""
    input_dir = f"{config['input_base']}/p{period}"
    output_file = f"{config['output_dir']}/period_{period:02d}_mosaic.tif"
    
    year = 2024 if period <= 31 else 2025
    
    print("=" * 70)
    print(f"Mosaicking Period {period} (Year: {year})")
    print(f"Input:  {input_dir}")
    print(f"Output: {output_file}")
    print("=" * 70)
    
    # Check if input directory exists
    if not os.path.exists(input_dir):
        print(f"WARNING: Input directory {input_dir} does not exist. Skipping...")
        return "skipped"
    
    # Get list of input files
    input_files = glob.glob(f"{input_dir}/*.tif")
    if len(input_files) == 0:
        print(f"WARNING: No .tif files found in {input_dir}. Skipping...")
        return "skipped"
    
    print(f"Found {len(input_files)} files to mosaic")
    
    # Create output directory
    Path(config['output_dir']).mkdir(parents=True, exist_ok=True)
    
    # Check if output already exists
    if os.path.exists(output_file) and not config['overwrite']:
        print(f"Output file {output_file} already exists. Skipping...")
        print("Use --overwrite to force regeneration")
        return "skipped"
    
    # Build OTB Mosaic command
    input_list = ' '.join(input_files)
    
    cmd = [
        config['otb_cmd'],  # Use the detected OTB path
        '-il', input_list,
        '-comp.feather', config['feather'],
        '-harmo.method', config['harmo_method'],
        '-harmo.cost', config['harmo_cost'],
        '-interpolator', config['interpolator'],
        '-output.spacingx', str(config['spacing_x']),
        '-output.spacingy', str(config['spacing_y']),
        '-distancemap.sr', str(config['distance_sr']),
        '-nodata', str(config['nodata']),
        '-out', output_file
    ]
    
    # Run mosaicking
    start_time = datetime.now()
    try:
        print(f"\nRunning OTB Mosaic...")
        result = subprocess.run(' '.join(cmd), shell=True, check=True, 
                              capture_output=False, text=True)
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # Check output file size
        if os.path.exists(output_file):
            file_size_mb = os.path.getsize(output_file) / (1024 * 1024)
            print(f"✓ Period {period} completed successfully in {elapsed:.1f}s")
            print(f"  Output size: {file_size_mb:.1f} MB")
            return "success"
        else:
            print(f"✗ Period {period} failed - output file not created")
            return "failed"
            
    except subprocess.CalledProcessError as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"✗ Period {period} failed after {elapsed:.1f}s")
        print(f"  Error: {e}")
        return "failed"
    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"✗ Period {period} failed after {elapsed:.1f}s")
        print(f"  Exception: {e}")
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
        description='Batch mosaicking for Sentinel-1 preprocessed data using OTB Mosaic',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Mosaic all periods (1-56)
  python %(prog)s
  
  # Mosaic specific periods
  python %(prog)s --periods 1-10
  
  # Mosaic 2024 only
  python %(prog)s --periods 1-31
  
  # Mosaic 2025 only
  python %(prog)s --periods 32-56
  
  # Custom paths and settings
  python %(prog)s --periods 1-56 \
    --input-base workspace/preprocessed_50m \
    --output-dir workspace/mosaics_50m \
    --spacing 0.00044915764206
  
  # Overwrite existing mosaics
  python %(prog)s --periods 1-56 --overwrite
        '''
    )
    
    parser.add_argument(
        '--periods',
        type=str,
        default='1-56',
        help='Periods to mosaic (e.g., "1-10", "1-5,10,15-20"). Default: 1-56'
    )
    parser.add_argument(
        '--input-base',
        type=str,
        default='workspace/preprocessed_20m',
        help='Base directory for preprocessed data (contains p1, p2, etc.)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='workspace/mosaics_20m',
        help='Output directory for mosaics'
    )
    parser.add_argument(
        '--spacing-x',
        type=float,
        default=0.000179663056824,
        help='Output pixel spacing X in degrees (default: 0.000179663056824 for ~20m)'
    )
    parser.add_argument(
        '--spacing-y',
        type=float,
        default=0.000179663056824,
        help='Output pixel spacing Y in degrees (default: 0.000179663056824 for ~20m)'
    )
    parser.add_argument(
        '--feather',
        type=str,
        default='large',
        choices=['none', 'large', 'slim'],
        help='Feathering method (default: large)'
    )
    parser.add_argument(
        '--harmo-method',
        type=str,
        default='band',
        choices=['none', 'band', 'rgb'],
        help='Harmonization method (default: band)'
    )
    parser.add_argument(
        '--harmo-cost',
        type=str,
        default='rmse',
        choices=['rmse', 'musig', 'mu'],
        help='Harmonization cost function (default: rmse)'
    )
    parser.add_argument(
        '--interpolator',
        type=str,
        default='nn',
        choices=['nn', 'bco', 'linear'],
        help='Interpolation method (default: nn - nearest neighbor)'
    )
    parser.add_argument(
        '--distance-sr',
        type=float,
        default=10,
        help='Distance map sampling ratio (default: 10)'
    )
    parser.add_argument(
        '--nodata',
        type=float,
        default=0,
        help='No-data value (default: 0)'
    )
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite existing mosaic files'
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
    
    # Check if OTB is available (try common paths and system PATH)
    # First check if user provided OTB_PATH environment variable
    otb_cmd = os.environ.get('OTB_PATH')
    
    if otb_cmd:
        # Remove trailing slashes and clean up path
        otb_cmd = otb_cmd.rstrip('/')
        try:
            # Check if path exists and is executable
            if not os.path.isfile(otb_cmd):
                print(f"WARNING: OTB_PATH points to non-existent file: {otb_cmd}")
                otb_cmd = None
            elif not os.access(otb_cmd, os.X_OK):
                print(f"WARNING: OTB_PATH exists but is not executable: {otb_cmd}")
                otb_cmd = None
            else:
                subprocess.run([otb_cmd, '-help'], 
                              capture_output=True, check=True, shell=False)
                print(f"Using OTB from OTB_PATH: {otb_cmd}")
        except (subprocess.CalledProcessError, FileNotFoundError, PermissionError) as e:
            print(f"WARNING: OTB_PATH is set but invalid: {otb_cmd}")
            print(f"  Error: {e}")
            otb_cmd = None
    
    # If not found via environment variable, try common paths
    if otb_cmd is None:
        otb_paths = [
            'otbcli_Mosaic',  # System PATH
            '/home/unika_sianturi/work/OTB/bin/otbcli_Mosaic',  # Your installation
            '/usr/local/bin/otbcli_Mosaic',
            '/opt/OTB/bin/otbcli_Mosaic',
        ]
        
        for otb_path in otb_paths:
            try:
                # Skip if path doesn't exist (for absolute paths)
                if otb_path.startswith('/') and not os.path.isfile(otb_path):
                    continue
                    
                subprocess.run([otb_path, '-help'], 
                              capture_output=True, check=True, shell=False)
                otb_cmd = otb_path
                print(f"Found OTB at: {otb_cmd}")
                break
            except (subprocess.CalledProcessError, FileNotFoundError, PermissionError):
                continue
    
    if otb_cmd is None:
        print("ERROR: otbcli_Mosaic not found in common locations.")
        print("Please specify the full path using OTB_PATH environment variable:")
        print("  export OTB_PATH=/path/to/OTB/bin/otbcli_Mosaic")
        print("  python batch_mosaic_periods.py")
        print("\nOr add OTB to your PATH:")
        print("  export PATH=/path/to/OTB/bin:$PATH")
        sys.exit(1)
    
    # Configuration
    config = {
        'input_base': args.input_base,
        'output_dir': args.output_dir,
        'spacing_x': args.spacing_x,
        'spacing_y': args.spacing_y,
        'feather': args.feather,
        'harmo_method': args.harmo_method,
        'harmo_cost': args.harmo_cost,
        'interpolator': args.interpolator,
        'distance_sr': args.distance_sr,
        'nodata': args.nodata,
        'overwrite': args.overwrite,
        'otb_cmd': otb_cmd  # Add OTB command path
    }
    
    # Print configuration
    print("=" * 70)
    print("BATCH MOSAICKING CONFIGURATION")
    print("=" * 70)
    print(f"Input base:     {config['input_base']}")
    print(f"Output dir:     {config['output_dir']}")
    print(f"Spacing:        {config['spacing_x']} × {config['spacing_y']} degrees")
    print(f"Feathering:     {config['feather']}")
    print(f"Harmonization:  {config['harmo_method']} ({config['harmo_cost']})")
    print(f"Interpolation:  {config['interpolator']}")
    print(f"Periods:        {min(periods)}-{max(periods)} ({len(periods)} total)")
    print(f"Overwrite:      {args.overwrite}")
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
        
        result = mosaic_period(period, config)
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
    print("BATCH MOSAICKING COMPLETE")
    print("=" * 70)
    print(f"Total time:     {overall_elapsed:.1f}s ({overall_elapsed/60:.1f} minutes)")
    print(f"Total periods:  {len(periods)}")
    print(f"Successful:     {stats['success']}")
    print(f"Skipped:        {stats['skipped']}")
    print(f"Failed:         {stats['failed']}")
    
    if failed_periods:
        print(f"\nFailed periods: {', '.join(map(str, failed_periods))}")
    
    print(f"\nMosaics saved to: {config['output_dir']}/")
    print("=" * 70)
    
    # Exit with error code if any failed
    if stats['failed'] > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
