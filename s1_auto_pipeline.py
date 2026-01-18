#!/usr/bin/env python3
"""
Sentinel-1 Automatic Pipeline (EXPERIMENTAL)

Fully automated workflow: Define AOI + time period -> Download -> Preprocess -> Mosaic

WARNING: This script is EXPERIMENTAL and has not been fully tested.
         For production use, prefer the manual workflow with s1_process_period_dir.py

Requirements:
    pip install asf-search shapely rasterio numpy matplotlib

Usage:
    python s1_auto_pipeline.py \
        --bbox 110.0 -7.5 111.0 -6.5 \
        --start-date 2024-01-01 \
        --end-date 2024-01-12 \
        --output-dir ./output

Author: Firman Hadi
License: MIT
"""

import os
import sys
from pathlib import Path
import argparse
import logging
import subprocess
import shutil
from datetime import datetime
from typing import List, Dict, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_warning():
    """Print experimental warning"""
    warning = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                              ⚠️  WARNING ⚠️                                   ║
║                                                                              ║
║  This automatic pipeline is EXPERIMENTAL and has NOT been fully tested.     ║
║                                                                              ║
║  Known limitations:                                                          ║
║  - ASF download may fail for some regions or time periods                    ║
║  - Large areas may exceed memory limits                                      ║
║  - Network interruptions can cause incomplete downloads                      ║
║  - Some Sentinel-1 scenes may have missing data                              ║
║                                                                              ║
║  For production use, we recommend the MANUAL workflow:                       ║
║  1. Search scenes on ASF Vertex: https://search.asf.alaska.edu/              ║
║  2. Download manually to downloads/ folder                                   ║
║  3. Run: python s1_process_period_dir.py --run-all                           ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """
    print(warning)


def create_aoi_geojson(min_lon: float, min_lat: float,
                       max_lon: float, max_lat: float) -> Dict:
    """Create GeoJSON polygon from bounding box"""
    return {
        "type": "Polygon",
        "coordinates": [[
            [min_lon, min_lat],
            [max_lon, min_lat],
            [max_lon, max_lat],
            [min_lon, max_lat],
            [min_lon, min_lat]
        ]]
    }


def search_and_download_asf(aoi_geojson: Dict, start_date: str, end_date: str,
                            download_dir: Path, max_results: int = 50) -> List[Path]:
    """
    Search and download Sentinel-1 GRD from ASF

    Args:
        aoi_geojson: Area of interest as GeoJSON dict
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        download_dir: Directory to save downloads
        max_results: Maximum number of scenes to download

    Returns:
        List of downloaded file paths
    """
    try:
        import asf_search as asf
        from shapely.geometry import shape
    except ImportError:
        logger.error("Required packages not installed!")
        logger.error("Run: pip install asf-search shapely")
        return []

    logger.info("=" * 60)
    logger.info("STEP 1: SEARCHING ASF ARCHIVE")
    logger.info("=" * 60)

    # Convert GeoJSON to WKT
    geom = shape(aoi_geojson)
    aoi_wkt = geom.wkt

    logger.info(f"AOI: {aoi_wkt[:100]}...")
    logger.info(f"Period: {start_date} to {end_date}")

    # Search ASF
    try:
        results = asf.search(
            platform=asf.PLATFORM.SENTINEL1,
            processingLevel='GRD_HD',
            start=start_date,
            end=end_date,
            intersectsWith=aoi_wkt,
            maxResults=max_results
        )
    except Exception as e:
        logger.error(f"ASF search failed: {e}")
        return []

    logger.info(f"Found {len(results)} scenes")

    if len(results) == 0:
        logger.warning("No scenes found for the specified criteria")
        return []

    # Display found scenes
    for i, result in enumerate(results[:5]):
        logger.info(f"  [{i+1}] {result.properties['fileID']}")
        logger.info(f"      Date: {result.properties['startTime']}")
    if len(results) > 5:
        logger.info(f"  ... and {len(results) - 5} more")

    # Download
    logger.info("")
    logger.info("=" * 60)
    logger.info("STEP 2: DOWNLOADING FROM ASF")
    logger.info("=" * 60)

    download_dir.mkdir(parents=True, exist_ok=True)
    downloaded = []

    for i, result in enumerate(results):
        filename = result.properties['fileID'] + '.zip'
        filepath = download_dir / filename

        if filepath.exists():
            logger.info(f"[{i+1}/{len(results)}] Already exists: {filename}")
            downloaded.append(filepath)
            continue

        logger.info(f"[{i+1}/{len(results)}] Downloading: {filename}")

        try:
            result.download(path=str(download_dir))
            if filepath.exists():
                downloaded.append(filepath)
                logger.info(f"  ✓ Downloaded")
            else:
                logger.warning(f"  ✗ Download failed")
        except Exception as e:
            logger.error(f"  ✗ Error: {e}")

    logger.info(f"\nDownloaded {len(downloaded)}/{len(results)} scenes")
    return downloaded


def run_preprocessing(work_dir: Path, resolution: int = 20,
                      snap_gpt_path: str = 'gpt') -> bool:
    """
    Run preprocessing using s1_process_period_dir.py

    Args:
        work_dir: Working directory with downloads/ folder
        resolution: Output resolution (10, 20, 50, 100)
        snap_gpt_path: Path to SNAP GPT executable

    Returns:
        True if successful
    """
    logger.info("")
    logger.info("=" * 60)
    logger.info("STEP 3: PREPROCESSING WITH SNAP")
    logger.info("=" * 60)

    # Get path to processing script
    script_dir = Path(__file__).parent
    process_script = script_dir / 's1_process_period_dir.py'

    if not process_script.exists():
        logger.error(f"Processing script not found: {process_script}")
        return False

    # Run preprocessing
    cmd = [
        sys.executable,
        str(process_script),
        '--period-dir', str(work_dir),
        '--resolution', str(resolution),
        '--snap-gpt-path', snap_gpt_path,
        '--run-all'
    ]

    logger.info(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        logger.error(f"Preprocessing failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Sentinel-1 Automatic Pipeline (EXPERIMENTAL)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
⚠️  WARNING: This is an EXPERIMENTAL feature. Not fully tested!

Examples:
  # Process a small area for a 12-day period
  python s1_auto_pipeline.py \\
      --bbox 110.0 -7.5 111.0 -6.5 \\
      --start-date 2024-01-01 \\
      --end-date 2024-01-12 \\
      --output-dir ./my_output

  # With custom resolution
  python s1_auto_pipeline.py \\
      --bbox 110.0 -7.5 111.0 -6.5 \\
      --start-date 2024-01-01 \\
      --end-date 2024-01-12 \\
      --resolution 50 \\
      --output-dir ./my_output

For production use, prefer the manual workflow:
  1. Search: https://search.asf.alaska.edu/
  2. Download .zip files to downloads/ folder
  3. Run: python s1_process_period_dir.py --run-all
        """
    )

    parser.add_argument('--bbox', nargs=4, type=float, required=True,
                        metavar=('MIN_LON', 'MIN_LAT', 'MAX_LON', 'MAX_LAT'),
                        help='Bounding box: min_lon min_lat max_lon max_lat')
    parser.add_argument('--start-date', required=True,
                        help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', required=True,
                        help='End date (YYYY-MM-DD)')
    parser.add_argument('--output-dir', required=True,
                        help='Output directory')
    parser.add_argument('--resolution', type=int, default=20,
                        choices=[10, 20, 50, 100],
                        help='Output resolution in meters (default: 20)')
    parser.add_argument('--snap-gpt-path', default='gpt',
                        help='Path to SNAP GPT executable')
    parser.add_argument('--max-scenes', type=int, default=50,
                        help='Maximum number of scenes to download (default: 50)')
    parser.add_argument('--skip-warning', action='store_true',
                        help='Skip the experimental warning')

    args = parser.parse_args()

    # Show warning
    if not args.skip_warning:
        print_warning()
        response = input("Do you want to continue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            logger.info("Aborted by user")
            return

    # Setup directories
    output_dir = Path(args.output_dir).resolve()
    downloads_dir = output_dir / 'downloads'

    logger.info("")
    logger.info("=" * 60)
    logger.info("SENTINEL-1 AUTOMATIC PIPELINE (EXPERIMENTAL)")
    logger.info("=" * 60)
    logger.info(f"AOI: {args.bbox}")
    logger.info(f"Period: {args.start_date} to {args.end_date}")
    logger.info(f"Resolution: {args.resolution}m")
    logger.info(f"Output: {output_dir}")

    # Create AOI
    min_lon, min_lat, max_lon, max_lat = args.bbox
    aoi_geojson = create_aoi_geojson(min_lon, min_lat, max_lon, max_lat)

    # Step 1 & 2: Search and download
    downloaded = search_and_download_asf(
        aoi_geojson=aoi_geojson,
        start_date=args.start_date,
        end_date=args.end_date,
        download_dir=downloads_dir,
        max_results=args.max_scenes
    )

    if not downloaded:
        logger.error("No files downloaded. Exiting.")
        return

    # Step 3: Preprocess
    success = run_preprocessing(
        work_dir=output_dir,
        resolution=args.resolution,
        snap_gpt_path=args.snap_gpt_path
    )

    # Summary
    logger.info("")
    logger.info("=" * 60)
    if success:
        logger.info("✓ PIPELINE COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Output directory: {output_dir}")
        logger.info(f"  - downloads/: {len(downloaded)} raw scenes")
        logger.info(f"  - preprocessed/: SNAP processed files")
        logger.info(f"  - geotiff/: GeoTIFF files")
        logger.info(f"  - mosaic/: Final mosaic and preview")
    else:
        logger.error("✗ PIPELINE FAILED")
        logger.info("=" * 60)
        logger.info("Check the logs above for errors.")
        logger.info("Consider using the manual workflow instead.")


if __name__ == '__main__':
    main()
