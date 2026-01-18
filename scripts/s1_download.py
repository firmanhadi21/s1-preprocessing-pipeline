#!/usr/bin/env python3
"""
Sentinel-1 Data Download Module

Automatically downloads Sentinel-1 GRD data from:
1. Copernicus Data Space Ecosystem (CDSE) - NEW ESA platform (replaces SciHub)
2. Alaska Satellite Facility (ASF) - Free, no registration required (RECOMMENDED)

Requirements:
    pip install asf-search
    pip install cdsetool  # For Copernicus Data Space

Note: ESA SciHub is deprecated. Use CDSE or ASF instead.
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import json
from typing import List, Dict, Tuple
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Sentinel1Downloader:
    """
    Download Sentinel-1 GRD data for specified area and time period
    """

    def __init__(self, download_dir='downloads/sentinel1',
                 username=None, password=None):
        """
        Initialize downloader

        Args:
            download_dir: Directory to save downloaded files
            username: Copernicus Data Space username (register at https://dataspace.copernicus.eu/)
            password: Copernicus Data Space password

        Note: ESA SciHub is deprecated. For CDSE, register at:
              https://dataspace.copernicus.eu/
        """
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

        self.username = username
        self.password = password

        logger.info(f"Download directory: {self.download_dir}")


    def download_cdse(self, aoi_wkt: str, start_date: str, end_date: str,
                      product_type='GRD', polarisation='VH',
                      orbit_direction='ASCENDING') -> List[str]:
        """
        Download from Copernicus Data Space Ecosystem (CDSE)
        This replaces the deprecated SciHub API

        Args:
            aoi_wkt: Area of Interest in WKT format
                     Example: 'POLYGON((106 -8, 115 -8, 115 -5, 106 -5, 106 -8))'
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            product_type: Product type ('GRD' or 'SLC')
            polarisation: Polarisation mode ('VH', 'VV', or 'VH VV')
            orbit_direction: Orbit direction ('ASCENDING' or 'DESCENDING')

        Returns:
            List of downloaded file paths
        """
        logger.warning("IMPORTANT: ESA SciHub is deprecated!")
        logger.warning("Use ASF (recommended) or Copernicus Data Space Ecosystem")
        logger.warning("For CDSE, register at: https://dataspace.copernicus.eu/")

        if not self.username or not self.password:
            logger.error("CDSE credentials not provided!")
            logger.info("Register at: https://dataspace.copernicus.eu/")
            logger.info("RECOMMENDATION: Use ASF instead (no registration required)")
            return []

        logger.info("="*60)
        logger.info("DOWNLOADING FROM COPERNICUS DATA SPACE ECOSYSTEM (CDSE)")
        logger.info("="*60)
        logger.info(f"Area: {aoi_wkt}")
        logger.info(f"Period: {start_date} to {end_date}")
        logger.info(f"Product: Sentinel-1 {product_type}")
        logger.info(f"Polarisation: {polarisation}")
        logger.info(f"Orbit: {orbit_direction}")

        # For CDSE implementation, use cdsetool or OData API
        # Placeholder - implement using CDSE API when available
        logger.error("CDSE download not yet implemented in this version")
        logger.info("Please use ASF download instead (recommended):")
        logger.info("  python s1_download.py --source asf ...")
        return []

        # Search for products
        products = api.query(
            area=aoi_wkt,
            date=(start_date, end_date),
            platformname='Sentinel-1',
            producttype=product_type,
            orbitdirection=orbit_direction,
            polarisationmode=polarisation
        )

        logger.info(f"Found {len(products)} products")

        if len(products) == 0:
            logger.warning("No products found for the specified criteria")
            return []

        # Convert to DataFrame for easier handling
        products_df = api.to_dataframe(products)

        # Sort by acquisition date
        products_df = products_df.sort_values('beginposition', ascending=True)

        logger.info("\nProducts to download:")
        for idx, row in products_df.iterrows():
            logger.info(f"  {row['title']}")
            logger.info(f"    Date: {row['beginposition']}")
            logger.info(f"    Size: {row['size']}")

        # Download products
        downloaded_files = []

        for idx, row in products_df.iterrows():
            try:
                logger.info(f"\nDownloading: {row['title']}")

                # Download
                api.download(idx, directory_path=str(self.download_dir))

                # Get downloaded file path
                product_path = self.download_dir / f"{row['title']}.zip"

                if product_path.exists():
                    downloaded_files.append(str(product_path))
                    logger.info(f"✓ Downloaded: {product_path}")
                else:
                    logger.warning(f"✗ File not found: {product_path}")

            except Exception as e:
                logger.error(f"Error downloading {row['title']}: {str(e)}")
                continue

        logger.info(f"\n✓ Downloaded {len(downloaded_files)} files")
        return downloaded_files


    def download_asf(self, aoi_geojson: Dict, start_date: str, end_date: str,
                     processing_level='GRD_HD', max_results=100) -> List[str]:
        """
        Download from Alaska Satellite Facility (ASF)
        Free, no authentication required for most data

        Args:
            aoi_geojson: Area of Interest as GeoJSON dict
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            processing_level: Processing level (GRD_HD, GRD_MS, SLC, etc.)
            max_results: Maximum number of results to return

        Returns:
            List of downloaded file paths
        """
        try:
            import asf_search as asf
            from shapely.geometry import shape
        except ImportError:
            logger.error("Required packages not installed. Install with: pip install asf-search shapely")
            return []

        logger.info("="*60)
        logger.info("DOWNLOADING FROM ALASKA SATELLITE FACILITY (ASF)")
        logger.info("="*60)
        logger.info(f"Period: {start_date} to {end_date}")
        logger.info(f"Processing level: {processing_level}")

        # Convert GeoJSON to WKT format (ASF expects WKT, not GeoJSON)
        geom = shape(aoi_geojson)
        aoi_wkt = geom.wkt
        logger.info(f"AOI (WKT): {aoi_wkt}")

        # Search for products
        results = asf.search(
            platform=asf.PLATFORM.SENTINEL1,
            processingLevel=processing_level,
            start=start_date,
            end=end_date,
            intersectsWith=aoi_wkt,
            maxResults=max_results
        )

        logger.info(f"Found {len(results)} products")

        if len(results) == 0:
            logger.warning("No products found")
            return []

        # Display found products
        logger.info("\nProducts to download:")
        for result in results[:10]:  # Show first 10
            logger.info(f"  {result.properties['fileID']}")
            logger.info(f"    Date: {result.properties['startTime']}")
            logger.info(f"    Size: {result.properties.get('bytes', 'Unknown')}")

        if len(results) > 10:
            logger.info(f"  ... and {len(results) - 10} more")

        # Download
        downloaded_files = []

        for result in results:
            try:
                logger.info(f"\nDownloading: {result.properties['fileID']}")

                # Download (requires authentication for some products)
                # For free download, use:
                result.download(path=str(self.download_dir))

                # Get downloaded file path
                filename = result.properties['fileID'] + '.zip'
                product_path = self.download_dir / filename

                if product_path.exists():
                    downloaded_files.append(str(product_path))
                    logger.info(f"✓ Downloaded: {product_path}")

            except Exception as e:
                logger.error(f"Error downloading: {str(e)}")
                continue

        logger.info(f"\n✓ Downloaded {len(downloaded_files)} files")
        return downloaded_files


    def download_by_tile_date(self, tile_id: str, dates: List[str]) -> List[str]:
        """
        Download specific tiles by ID and date
        Useful when you know exact tiles needed

        Args:
            tile_id: Tile identifier (e.g., 'S1A_IW_GRDH_1SDV')
            dates: List of dates in YYYY-MM-DD format

        Returns:
            List of downloaded file paths
        """
        # Implementation depends on which service you're using
        # This is a placeholder for custom tile-based downloading
        pass


    def create_download_list(self, aoi_wkt: str, start_date: str, end_date: str,
                            interval_days: int = 6) -> List[Tuple[str, str]]:
        """
        Create list of date ranges for periodic downloads

        Args:
            aoi_wkt: Area of Interest in WKT
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            interval_days: Interval between acquisitions (default: 6 for S1 repeat cycle)

        Returns:
            List of (start, end) date tuples
        """
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')

        date_ranges = []
        current = start

        while current <= end:
            period_start = current.strftime('%Y-%m-%d')
            period_end = (current + timedelta(days=interval_days)).strftime('%Y-%m-%d')
            date_ranges.append((period_start, period_end))
            current += timedelta(days=interval_days)

        logger.info(f"Created {len(date_ranges)} date ranges with {interval_days}-day intervals")
        return date_ranges


def create_aoi_from_bbox(min_lon: float, min_lat: float,
                         max_lon: float, max_lat: float) -> str:
    """
    Create WKT polygon from bounding box coordinates

    Args:
        min_lon: Minimum longitude
        min_lat: Minimum latitude
        max_lon: Maximum longitude
        max_lat: Maximum latitude

    Returns:
        WKT polygon string
    """
    wkt = f"POLYGON(({min_lon} {min_lat}, {max_lon} {min_lat}, " \
          f"{max_lon} {max_lat}, {min_lon} {max_lat}, {min_lon} {min_lat}))"
    return wkt


def create_aoi_geojson(min_lon: float, min_lat: float,
                       max_lon: float, max_lat: float) -> Dict:
    """
    Create GeoJSON polygon from bounding box

    Args:
        min_lon: Minimum longitude
        min_lat: Minimum latitude
        max_lon: Maximum longitude
        max_lat: Maximum latitude

    Returns:
        GeoJSON dict
    """
    geojson = {
        "type": "Polygon",
        "coordinates": [[
            [min_lon, min_lat],
            [max_lon, min_lat],
            [max_lon, max_lat],
            [min_lon, max_lat],
            [min_lon, min_lat]
        ]]
    }
    return geojson


def main():
    """Example usage"""
    import argparse

    parser = argparse.ArgumentParser(description='Download Sentinel-1 data')
    parser.add_argument('--start-date', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--bbox', nargs=4, type=float, required=True,
                       metavar=('MIN_LON', 'MIN_LAT', 'MAX_LON', 'MAX_LAT'),
                       help='Bounding box coordinates')
    parser.add_argument('--username', help='ESA SciHub username')
    parser.add_argument('--password', help='ESA SciHub password')
    parser.add_argument('--download-dir', default='downloads/sentinel1',
                       help='Download directory')
    parser.add_argument('--source', choices=['cdse', 'asf'], default='asf',
                       help='Download source (default: asf - recommended, no registration)')

    args = parser.parse_args()

    # Create AOI
    min_lon, min_lat, max_lon, max_lat = args.bbox
    aoi_wkt = create_aoi_from_bbox(min_lon, min_lat, max_lon, max_lat)
    aoi_geojson = create_aoi_geojson(min_lon, min_lat, max_lon, max_lat)

    # Initialize downloader
    downloader = Sentinel1Downloader(
        download_dir=args.download_dir,
        username=args.username,
        password=args.password
    )

    # Download
    if args.source == 'scihub':
        files = downloader.download_scihub(
            aoi_wkt=aoi_wkt,
            start_date=args.start_date,
            end_date=args.end_date
        )
    else:  # ASF
        files = downloader.download_asf(
            aoi_geojson=aoi_geojson,
            start_date=args.start_date,
            end_date=args.end_date
        )

    logger.info(f"\n{'='*60}")
    logger.info(f"DOWNLOAD COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Downloaded {len(files)} files to: {args.download_dir}")

    for f in files:
        logger.info(f"  {f}")


if __name__ == '__main__':
    main()
