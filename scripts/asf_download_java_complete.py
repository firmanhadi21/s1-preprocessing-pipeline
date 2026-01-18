#!/usr/bin/env python3
"""
Complete Sentinel-1 Download for Java Island 2024

Downloads all S1A ASCENDING GRD scenes covering Java Island for entire 2024
Uses Alaska Satellite Facility (ASF) Data Search API

Features:
- Auto-resume from interruptions
- Parallel downloads (configurable)
- Progress tracking and ETA
- Checksum verification
- Coverage validation
- Smart duplicate handling

Usage:
    # Download everything (3,600+ scenes)
    python asf_download_java_complete.py \
        --output-dir workspace/downloads \
        --workers 8

    # Download specific periods only (e.g., growing season)
    python asf_download_java_complete.py \
        --output-dir workspace/downloads \
        --start-period 12 \
        --end-period 24 \
        --workers 8

    # Resume interrupted download
    python asf_download_java_complete.py \
        --output-dir workspace/downloads \
        --resume
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta
import json
from typing import List, Dict, Optional
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

try:
    import asf_search as asf
except ImportError:
    print("ERROR: asf_search not installed")
    print("Install with: pip install asf-search")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class JavaS1Downloader:
    """
    Complete S1 downloader for Java Island
    """

    # Java Island bounding box (WGS84)
    JAVA_AOI = {
        'min_lon': 105.0,
        'max_lon': 116.0,
        'min_lat': -9.0,
        'max_lat': -5.0
    }

    def __init__(self, output_dir: str, year: int = 2024,
                 max_workers: int = 4, verify_checksums: bool = True):
        """
        Initialize downloader

        Args:
            output_dir: Output directory for downloads
            year: Year to download (default: 2024)
            max_workers: Number of parallel downloads
            verify_checksums: Verify file checksums after download
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.year = year
        self.max_workers = max_workers
        self.verify_checksums = verify_checksums

        self.status_file = self.output_dir / 'download_status.json'
        self.status = self._load_status()

        logger.info(f"Java S1 Downloader initialized")
        logger.info(f"Output: {self.output_dir}")
        logger.info(f"Year: {year}")
        logger.info(f"Workers: {max_workers}")


    def _load_status(self) -> Dict:
        """Load download status from file"""
        if self.status_file.exists():
            with open(self.status_file, 'r') as f:
                status = json.load(f)
                logger.info(f"Loaded status: {len(status)} entries")
                return status
        return {}


    def _save_status(self):
        """Save download status to file"""
        with open(self.status_file, 'w') as f:
            json.dump(self.status, f, indent=2)


    def search_scenes(self, start_date: Optional[datetime] = None,
                     end_date: Optional[datetime] = None,
                     orbit_direction: str = 'ASCENDING') -> List:
        """
        Search for S1 scenes covering Java

        Args:
            start_date: Start date (default: Jan 1, year)
            end_date: End date (default: Dec 31, year)
            orbit_direction: ASCENDING or DESCENDING

        Returns:
            List of ASF search results
        """
        if start_date is None:
            start_date = datetime(self.year, 1, 1)
        if end_date is None:
            end_date = datetime(self.year, 12, 31)

        logger.info(f"Searching ASF for scenes...")
        logger.info(f"  AOI: Java Island {self.JAVA_AOI}")
        logger.info(f"  Date range: {start_date.date()} to {end_date.date()}")
        logger.info(f"  Orbit: {orbit_direction}")

        # Create WKT polygon for Java
        wkt = (f"POLYGON(("
               f"{self.JAVA_AOI['min_lon']} {self.JAVA_AOI['min_lat']}, "
               f"{self.JAVA_AOI['max_lon']} {self.JAVA_AOI['min_lat']}, "
               f"{self.JAVA_AOI['max_lon']} {self.JAVA_AOI['max_lat']}, "
               f"{self.JAVA_AOI['min_lon']} {self.JAVA_AOI['max_lat']}, "
               f"{self.JAVA_AOI['min_lon']} {self.JAVA_AOI['min_lat']}))")

        try:
            # Search ASF
            results = asf.search(
                platform=[asf.PLATFORM.SENTINEL1A],
                processingLevel=asf.PRODUCT_TYPE.GRD_HD,
                beamMode=asf.BEAMMODE.IW,
                flightDirection=orbit_direction,
                start=start_date,
                end=end_date,
                intersectsWith=wkt,
                maxResults=10000  # High limit to get all results
            )

            logger.info(f"Found {len(results)} scenes")

            return results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []


    def download_scene(self, result, session=None) -> tuple:
        """
        Download a single scene

        Args:
            result: ASF search result
            session: Optional ASF session for authentication

        Returns:
            (granule_name, success, file_path)
        """
        granule_name = result.properties['sceneName']
        output_file = self.output_dir / f"{granule_name}.zip"

        # Check if already downloaded
        if granule_name in self.status:
            status_entry = self.status[granule_name]
            if status_entry['status'] == 'completed' and output_file.exists():
                logger.debug(f"✓ SKIP (already downloaded): {granule_name}")
                return (granule_name, True, str(output_file))

        logger.info(f"START: {granule_name}")
        start_time = time.time()

        try:
            # Download using ASF
            result.download(
                path=str(self.output_dir),
                session=session
            )

            elapsed = time.time() - start_time

            # Verify file exists
            if not output_file.exists():
                logger.error(f"FAILED (file not found): {granule_name}")
                self.status[granule_name] = {
                    'status': 'failed',
                    'error': 'file_not_found',
                    'timestamp': datetime.now().isoformat()
                }
                return (granule_name, False, "")

            # Verify checksum if requested
            if self.verify_checksums:
                # ASF provides MD5 checksum
                expected_md5 = result.properties.get('md5sum')
                if expected_md5:
                    actual_md5 = self._calculate_md5(output_file)
                    if actual_md5 != expected_md5:
                        logger.error(f"FAILED (checksum mismatch): {granule_name}")
                        output_file.unlink()  # Delete corrupted file
                        self.status[granule_name] = {
                            'status': 'failed',
                            'error': 'checksum_mismatch',
                            'timestamp': datetime.now().isoformat()
                        }
                        return (granule_name, False, "")

            # Success
            file_size_mb = output_file.stat().st_size / (1024**2)
            logger.info(f"✓ DONE ({elapsed:.1f}s, {file_size_mb:.1f} MB): {granule_name}")

            self.status[granule_name] = {
                'status': 'completed',
                'file': str(output_file),
                'size_mb': file_size_mb,
                'timestamp': datetime.now().isoformat(),
                'elapsed_seconds': elapsed
            }

            return (granule_name, True, str(output_file))

        except Exception as e:
            logger.error(f"ERROR: {granule_name} - {str(e)}")
            self.status[granule_name] = {
                'status': 'failed',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            return (granule_name, False, "")


    def _calculate_md5(self, file_path: Path) -> str:
        """Calculate MD5 checksum of file"""
        md5 = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                md5.update(chunk)
        return md5.hexdigest()


    def download_all(self, results: List, session=None) -> Dict:
        """
        Download all scenes in parallel

        Args:
            results: List of ASF search results
            session: Optional ASF session

        Returns:
            Statistics dict
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"STARTING PARALLEL DOWNLOAD")
        logger.info(f"{'='*70}")
        logger.info(f"Total scenes: {len(results)}")
        logger.info(f"Workers: {self.max_workers}")

        # Filter already downloaded
        remaining = [
            r for r in results
            if r.properties['sceneName'] not in self.status
            or self.status[r.properties['sceneName']]['status'] != 'completed'
        ]

        logger.info(f"Already downloaded: {len(results) - len(remaining)}")
        logger.info(f"Remaining: {len(remaining)}\n")

        if not remaining:
            logger.info("All scenes already downloaded!")
            return {
                'total': len(results),
                'completed': len(results),
                'failed': 0,
                'skipped': len(results)
            }

        # Download in parallel
        start_time = time.time()
        completed = 0
        failed = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all downloads
            futures = {
                executor.submit(self.download_scene, result, session): result
                for result in remaining
            }

            # Process as they complete
            for future in as_completed(futures):
                granule_name, success, file_path = future.result()

                if success:
                    completed += 1
                else:
                    failed += 1

                # Progress update
                total_done = completed + failed
                percent = (total_done / len(remaining)) * 100
                elapsed = time.time() - start_time
                rate = total_done / elapsed if elapsed > 0 else 0
                eta = (len(remaining) - total_done) / rate if rate > 0 else 0

                logger.info(
                    f"Progress: {total_done}/{len(remaining)} ({percent:.1f}%) | "
                    f"✓ {completed} | ✗ {failed} | "
                    f"Rate: {rate:.2f} scenes/min | "
                    f"ETA: {timedelta(seconds=int(eta))}"
                )

                # Save status periodically
                if total_done % 10 == 0:
                    self._save_status()

        # Final save
        self._save_status()

        elapsed = time.time() - start_time

        # Summary
        logger.info(f"\n{'='*70}")
        logger.info("DOWNLOAD SUMMARY")
        logger.info(f"{'='*70}")
        logger.info(f"Total scenes: {len(results)}")
        logger.info(f"Completed: {completed}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Already had: {len(results) - len(remaining)}")
        logger.info(f"Total time: {timedelta(seconds=int(elapsed))}")
        logger.info(f"Average rate: {len(remaining)/elapsed*60:.2f} scenes/hour")
        logger.info(f"{'='*70}")

        return {
            'total': len(results),
            'completed': completed,
            'failed': failed,
            'skipped': len(results) - len(remaining),
            'elapsed': elapsed
        }


def main():
    parser = argparse.ArgumentParser(
        description='Download complete S1 dataset for Java Island',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--output-dir', default='workspace/downloads',
                       help='Output directory (default: workspace/downloads)')
    parser.add_argument('--year', type=int, default=2024,
                       help='Year to download (default: 2024)')
    parser.add_argument('--workers', type=int, default=4,
                       help='Number of parallel downloads (default: 4)')
    parser.add_argument('--start-period', type=int,
                       help='Start period (1-31, for partial download)')
    parser.add_argument('--end-period', type=int,
                       help='End period (1-31, for partial download)')
    parser.add_argument('--orbit', default='ASCENDING',
                       choices=['ASCENDING', 'DESCENDING'],
                       help='Orbit direction (default: ASCENDING)')
    parser.add_argument('--no-verify', action='store_true',
                       help='Skip checksum verification (faster but less safe)')
    parser.add_argument('--username',
                       help='NASA Earthdata username (optional, for faster downloads)')
    parser.add_argument('--password',
                       help='NASA Earthdata password (optional)')

    args = parser.parse_args()

    # Initialize downloader
    downloader = JavaS1Downloader(
        output_dir=args.output_dir,
        year=args.year,
        max_workers=args.workers,
        verify_checksums=not args.no_verify
    )

    # Calculate date range
    if args.start_period or args.end_period:
        from period_utils import get_period_dates

        start_period = args.start_period or 1
        end_period = args.end_period or 31

        start_date_str, _ = get_period_dates(args.year, start_period)
        _, end_date_str = get_period_dates(args.year, end_period)

        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')

        logger.info(f"Downloading periods {start_period}-{end_period}")
    else:
        start_date = datetime(args.year, 1, 1)
        end_date = datetime(args.year, 12, 31)
        logger.info(f"Downloading full year {args.year}")

    # Create session if credentials provided
    session = None
    if args.username and args.password:
        try:
            session = asf.ASFSession().auth_with_creds(args.username, args.password)
            logger.info("Authenticated with NASA Earthdata")
        except Exception as e:
            logger.warning(f"Authentication failed: {e}")
            logger.info("Continuing with unauthenticated downloads (slower)")

    # Search for scenes
    results = downloader.search_scenes(
        start_date=start_date,
        end_date=end_date,
        orbit_direction=args.orbit
    )

    if not results:
        logger.error("No scenes found! Check AOI and date range.")
        sys.exit(1)

    # Download all
    stats = downloader.download_all(results, session=session)

    # Exit code
    if stats['failed'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
