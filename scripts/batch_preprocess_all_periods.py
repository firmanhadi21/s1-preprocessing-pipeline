#!/usr/bin/env python3
"""
Batch preprocessing script for all periods (1-56)
Period 1-31: 2024
Period 32-56: 2025
"""

import os
import sys
import subprocess
from pathlib import Path

# Configuration
SCRIPT = "s1_preprocess_parallel_multiresolution.py"
DOWNLOAD_BASE = "workspace/downloads"
OUTPUT_BASE = "workspace/preprocessed_20m"
RESOLUTION = 20
WORKERS = 8

def preprocess_period(period):
    """Preprocess a single period"""
    input_dir = f"{DOWNLOAD_BASE}/downloads_p{period}"
    output_dir = f"{OUTPUT_BASE}/p{period}"
    
    year = 2024 if period <= 31 else 2025
    
    print("=" * 60)
    print(f"Processing Period {period} (Year: {year})")
    print(f"Input:  {input_dir}")
    print(f"Output: {output_dir}")
    print("=" * 60)
    
    # Check if input directory exists
    if not os.path.exists(input_dir):
        print(f"WARNING: Input directory {input_dir} does not exist. Skipping...")
        return "skipped"
    
    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Build command
    cmd = [
        "python", SCRIPT,
        "--input-dir", input_dir,
        "--output-dir", output_dir,
        "--resolution", str(RESOLUTION),
        "--workers", str(WORKERS)
    ]
    
    # Run preprocessing
    try:
        result = subprocess.run(cmd, check=True)
        print(f"✓ Period {period} completed successfully")
        return "success"
    except subprocess.CalledProcessError as e:
        print(f"✗ Period {period} failed with error code {e.returncode}")
        return "failed"
    except Exception as e:
        print(f"✗ Period {period} failed with exception: {e}")
        return "failed"

def main():
    """Main batch processing function"""
    # Check if script exists
    if not os.path.exists(SCRIPT):
        print(f"ERROR: Script {SCRIPT} not found!")
        sys.exit(1)
    
    print("Starting batch preprocessing for periods 1-56")
    print(f"Resolution: {RESOLUTION}m")
    print(f"Workers: {WORKERS}")
    print()
    
    # Track statistics
    stats = {"success": 0, "failed": 0, "skipped": 0}
    
    # Process periods 1-56
    for period in range(1, 57):
        print()
        print("-" * 60)
        result = preprocess_period(period)
        stats[result] += 1
    
    # Print summary
    print()
    print("=" * 60)
    print("BATCH PROCESSING COMPLETE")
    print("=" * 60)
    print(f"Total periods:  56")
    print(f"Successful:     {stats['success']}")
    print(f"Skipped:        {stats['skipped']}")
    print(f"Failed:         {stats['failed']}")
    print("=" * 60)
    
    # Exit with error code if any failed
    if stats['failed'] > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
