#!/usr/bin/env python3
"""
Setup Folder Structure for Manual Period Workflow

Creates the folder structure needed for manual period-based processing:
- downloads_p1/ through downloads_p31/
- Creates README files with period date ranges

Usage:
    python setup_manual_period_folders.py
    python setup_manual_period_folders.py --work-dir /path/to/workspace
    python setup_manual_period_folders.py --year 2024
"""

import argparse
from pathlib import Path
import logging

# Import period utilities
try:
    from period_utils import get_period_dates
except ImportError:
    print("Warning: period_utils.py not found. Using simple date calculation.")
    get_period_dates = None

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def create_period_folders(work_dir: Path, year: int = 2024):
    """
    Create download folders for all 31 periods

    Args:
        work_dir: Working directory
        year: Year for period date calculations
    """
    logger.info("="*70)
    logger.info("SETUP MANUAL PERIOD WORKFLOW FOLDERS")
    logger.info("="*70)
    logger.info(f"Working directory: {work_dir}")
    logger.info(f"Year: {year}")
    logger.info("")

    # Create main directories
    work_dir.mkdir(parents=True, exist_ok=True)

    mosaics_dir = work_dir / 'mosaics'
    mosaics_dir.mkdir(exist_ok=True)

    final_stack_dir = work_dir / 'final_stack'
    final_stack_dir.mkdir(exist_ok=True)

    logger.info("Creating download folders for 31 periods...")
    logger.info("")

    # Period date ranges (simplified)
    period_dates = []
    if get_period_dates:
        # Use period_utils if available
        for period in range(1, 32):
            start_date, end_date = get_period_dates(year, period)
            period_dates.append((period, start_date, end_date))
    else:
        # Simple calculation
        import datetime
        for period in range(1, 32):
            start_doy = (period - 1) * 12 + 1
            end_doy = min(period * 12, 365 if year % 4 != 0 else 366)
            start_date = datetime.datetime(year, 1, 1) + datetime.timedelta(days=start_doy - 1)
            end_date = datetime.datetime(year, 1, 1) + datetime.timedelta(days=end_doy - 1)
            period_dates.append((period, start_date, end_date))

    # Create folders and README files
    for period, start_date, end_date in period_dates:
        folder_name = f"downloads_p{period}"
        folder_path = work_dir / folder_name

        # Create folder
        folder_path.mkdir(exist_ok=True)

        # Create README
        readme_path = folder_path / 'README.txt'
        with open(readme_path, 'w') as f:
            f.write(f"Period {period} Downloads\n")
            f.write("="*50 + "\n\n")
            f.write(f"Date Range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}\n")
            f.write(f"Period: {period}\n")
            f.write(f"Year: {year}\n\n")
            f.write("Download Instructions:\n")
            f.write("-"*50 + "\n")
            f.write("1. Go to https://search.asf.alaska.edu/\n")
            f.write(f"2. Set date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}\n")
            f.write("3. Draw your area of interest (AOI)\n")
            f.write("4. Select Sentinel-1 GRD\n")
            f.write("5. Search and download matching scenes\n")
            f.write("6. Place downloaded ZIP files in this folder\n\n")
            f.write("Expected files:\n")
            f.write("-"*50 + "\n")
            f.write("- S1A_IW_GRDH_*.zip (Sentinel-1A)\n")
            f.write("- S1B_IW_GRDH_*.zip (Sentinel-1B)\n\n")
            f.write("Processing:\n")
            f.write("-"*50 + "\n")
            f.write(f"python s1_manual_period_workflow.py --period {period} --run-all\n")

        logger.info(f"✓ Created: {folder_name:20s}  ({start_date.strftime('%b %d')} - {end_date.strftime('%b %d')})")

    logger.info("")
    logger.info("="*70)
    logger.info("FOLDER STRUCTURE READY")
    logger.info("="*70)
    logger.info("")
    logger.info("Next steps:")
    logger.info("  1. Download Sentinel-1 GRD files from ASF")
    logger.info("  2. Place files in corresponding downloads_pX/ folders")
    logger.info("  3. Run: python s1_manual_period_workflow.py --run-all")
    logger.info("")
    logger.info("Quick reference:")
    logger.info(f"  Period 1:  {period_dates[0][1].strftime('%b %d')} - {period_dates[0][2].strftime('%b %d')}")
    logger.info(f"  Period 15: {period_dates[14][1].strftime('%b %d')} - {period_dates[14][2].strftime('%b %d')}")
    logger.info(f"  Period 31: {period_dates[30][1].strftime('%b %d')} - {period_dates[30][2].strftime('%b %d')}")
    logger.info("")

    # Create main README
    main_readme = work_dir / 'README_MANUAL_WORKFLOW.txt'
    with open(main_readme, 'w') as f:
        f.write("Manual Period Workflow\n")
        f.write("="*70 + "\n\n")
        f.write("This folder contains the manual period-based workflow for\n")
        f.write("Sentinel-1 rice growth stage mapping.\n\n")
        f.write("Folder Structure:\n")
        f.write("-"*70 + "\n")
        f.write("  downloads_p1/...downloads_p31/   Manual downloads (31 periods)\n")
        f.write("  preprocessed_p1/...p31/           SNAP preprocessed files (auto)\n")
        f.write("  mosaics/                          Period mosaics (auto)\n")
        f.write("  final_stack/                      Final 31-band stack (auto)\n\n")
        f.write("Workflow:\n")
        f.write("-"*70 + "\n")
        f.write("1. Download Sentinel-1 files from ASF for each period\n")
        f.write("2. Place in downloads_pX/ folders (see README.txt in each)\n")
        f.write("3. Run: python s1_manual_period_workflow.py --run-all\n\n")
        f.write("Commands:\n")
        f.write("-"*70 + "\n")
        f.write("  # Process single period\n")
        f.write("  python s1_manual_period_workflow.py --period 1 --run-all\n\n")
        f.write("  # Process all periods\n")
        f.write("  python s1_manual_period_workflow.py --run-all\n\n")
        f.write("  # Just preprocess all\n")
        f.write("  python s1_manual_period_workflow.py --preprocess-all\n\n")
        f.write("  # Just mosaic all\n")
        f.write("  python s1_manual_period_workflow.py --mosaic-all\n\n")
        f.write("  # Stack all mosaics\n")
        f.write(f"  python s1_manual_period_workflow.py --stack --year {year}\n\n")
        f.write("Documentation:\n")
        f.write("-"*70 + "\n")
        f.write("  See: MANUAL_PERIOD_WORKFLOW_GUIDE.md\n")

    logger.info(f"Created main README: {main_readme.name}")
    logger.info("")


def main():
    parser = argparse.ArgumentParser(
        description='Setup folder structure for manual period workflow'
    )
    parser.add_argument('--work-dir', default='.',
                        help='Working directory (default: current directory)')
    parser.add_argument('--year', type=int, default=2024,
                        help='Year for period calculations (default: 2024)')

    args = parser.parse_args()

    work_dir = Path(args.work_dir).resolve()
    create_period_folders(work_dir, args.year)


if __name__ == '__main__':
    main()
