#!/usr/bin/env python3
"""
Period Calculation Utilities for 12-Day Periods

Year is divided into 31 periods of 12 days each:
- Period 1: Jan 1-12
- Period 2: Jan 13-24
- Period 3: Jan 25-Feb 5
- ...
- Period 31: Dec 25-31 (last period may have fewer days)

Usage:
    from period_utils import get_period_dates, get_period_from_date, generate_period_lookup
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Tuple, List, Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_period_dates(year: int, period: int) -> Tuple[datetime, datetime]:
    """
    Get start and end dates for a given period in a year

    Args:
        year: Year (e.g., 2024)
        period: Period number (1-31)

    Returns:
        Tuple of (start_date, end_date)

    Example:
        >>> start, end = get_period_dates(2024, 1)
        >>> print(start, end)
        2024-01-01 2024-01-12
    """
    if not 1 <= period <= 31:
        raise ValueError(f"Period must be between 1 and 31, got {period}")

    # Calculate start date
    days_offset = (period - 1) * 12
    start_date = datetime(year, 1, 1) + timedelta(days=days_offset)

    # Calculate end date (12 days later, but not beyond year end)
    end_date = start_date + timedelta(days=11)  # 12 days total (inclusive)

    # Ensure we don't go beyond the year
    year_end = datetime(year, 12, 31)
    if end_date > year_end:
        end_date = year_end

    return start_date, end_date


def get_period_from_date(date: datetime) -> int:
    """
    Get period number from a date

    Args:
        date: Date to convert

    Returns:
        Period number (1-31)

    Example:
        >>> period = get_period_from_date(datetime(2024, 1, 15))
        >>> print(period)
        2
    """
    # Get day of year (1-366)
    day_of_year = date.timetuple().tm_yday

    # Calculate period (12 days per period)
    period = ((day_of_year - 1) // 12) + 1

    # Ensure it's within valid range
    period = min(period, 31)

    return period


def generate_period_lookup_csv(year: int, output_file: str = 'perioda.csv'):
    """
    Generate period lookup CSV file for a given year

    Creates CSV with columns: Periode, Start Date, End Date

    Args:
        year: Year to generate lookup for
        output_file: Output CSV filename

    Example:
        >>> generate_period_lookup_csv(2024, 'perioda_2024.csv')
    """
    logger.info(f"Generating period lookup for year {year}")

    periods_data = []

    for period in range(1, 32):  # 31 periods
        start_date, end_date = get_period_dates(year, period)

        periods_data.append({
            'Periode': period,
            'Start Date': start_date.strftime('%Y-%m-%d'),
            'End Date': end_date.strftime('%Y-%m-%d')
        })

        logger.info(f"  Period {period:2d}: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

    # Create DataFrame
    df = pd.DataFrame(periods_data)

    # Save to CSV
    df.to_csv(output_file, index=False)

    logger.info(f"✓ Period lookup saved to: {output_file}")
    logger.info(f"  Total periods: {len(df)}")

    return df


def get_sentinel1_dates_for_period(year: int, period: int,
                                   revisit_days: int = 6) -> List[datetime]:
    """
    Get expected Sentinel-1 acquisition dates within a period

    Sentinel-1 has ~6 day revisit time (combination of S1A and S1B)

    Args:
        year: Year
        period: Period number (1-31)
        revisit_days: Sentinel-1 revisit interval (default: 6)

    Returns:
        List of expected acquisition dates

    Example:
        >>> dates = get_sentinel1_dates_for_period(2024, 1)
        >>> print(dates)
        [datetime(2024, 1, 1), datetime(2024, 1, 7)]
    """
    start_date, end_date = get_period_dates(year, period)

    acquisition_dates = []
    current_date = start_date

    while current_date <= end_date:
        acquisition_dates.append(current_date)
        current_date += timedelta(days=revisit_days)

    return acquisition_dates


def calculate_composite_period(year: int, period: int,
                               available_dates: List[datetime]) -> datetime:
    """
    Select best date for period composite from available acquisitions

    Args:
        year: Year
        period: Period number
        available_dates: List of available acquisition dates

    Returns:
        Best date for this period (closest to period middle)

    Example:
        >>> available = [datetime(2024, 1, 3), datetime(2024, 1, 9)]
        >>> best = calculate_composite_period(2024, 1, available)
        >>> print(best)
        2024-01-09
    """
    start_date, end_date = get_period_dates(year, period)

    # Calculate period middle
    period_middle = start_date + (end_date - start_date) / 2

    # Filter dates within period
    dates_in_period = [d for d in available_dates if start_date <= d <= end_date]

    if not dates_in_period:
        logger.warning(f"No acquisitions found for period {period}")
        return None

    # Find date closest to period middle
    best_date = min(dates_in_period, key=lambda d: abs((d - period_middle).total_seconds()))

    return best_date


def print_period_calendar(year: int):
    """
    Print calendar showing all 31 periods

    Args:
        year: Year to display
    """
    print("\n" + "="*70)
    print(f"12-DAY PERIOD CALENDAR FOR {year}")
    print("="*70)
    print(f"{'Period':<8} {'Start Date':<12} {'End Date':<12} {'Days':<6} {'Band':<6}")
    print("-"*70)

    for period in range(1, 32):
        start_date, end_date = get_period_dates(year, period)
        num_days = (end_date - start_date).days + 1
        band = period  # Band number = Period number

        print(f"{period:<8} {start_date.strftime('%Y-%m-%d'):<12} "
              f"{end_date.strftime('%Y-%m-%d'):<12} {num_days:<6} {band:<6}")

    print("="*70)
    print(f"Total periods: 31")
    print(f"Total bands in annual stack: 31")
    print("="*70 + "\n")


def validate_period_data(geotiff_bands: int, year: int = None):
    """
    Validate that GeoTIFF has correct number of bands for 12-day periods

    Args:
        geotiff_bands: Number of bands in GeoTIFF
        year: Year (optional, for validation message)

    Returns:
        bool: True if valid

    Raises:
        ValueError: If band count doesn't match expected periods
    """
    expected_periods = 31

    if geotiff_bands < expected_periods:
        raise ValueError(
            f"GeoTIFF has {geotiff_bands} bands, but expected {expected_periods} "
            f"for 12-day periods in a year"
        )

    if geotiff_bands > expected_periods:
        logger.warning(
            f"GeoTIFF has {geotiff_bands} bands, more than {expected_periods} expected. "
            f"May contain multiple years or different period division."
        )

    logger.info(f"✓ Band count validation passed: {geotiff_bands} bands")
    return True


def get_valid_prediction_periods(total_bands: int, n_previous: int = 6) -> List[int]:
    """
    Get list of valid periods for prediction

    For backward-looking model, need current period + n_previous periods

    Args:
        total_bands: Total number of bands in GeoTIFF
        n_previous: Number of previous periods needed (default: 6)

    Returns:
        List of valid period numbers

    Example:
        >>> valid_periods = get_valid_prediction_periods(31, 6)
        >>> print(valid_periods)
        [7, 8, 9, ..., 31]  # Can predict from period 7 onwards
    """
    min_period = n_previous + 1  # Need 7 periods total (current + 6 back)
    max_period = total_bands

    valid_periods = list(range(min_period, max_period + 1))

    logger.info(f"Valid prediction periods: {min_period} to {max_period}")
    logger.info(f"  (Need {n_previous + 1} periods: current + {n_previous} previous)")

    return valid_periods


def create_download_schedule(year: int, output_file: str = 'download_schedule.csv'):
    """
    Create download schedule showing which Sentinel-1 dates to acquire

    Args:
        year: Year
        output_file: Output CSV filename

    Returns:
        DataFrame with download schedule
    """
    logger.info(f"Creating Sentinel-1 download schedule for {year}")

    schedule = []

    for period in range(1, 32):
        start_date, end_date = get_period_dates(year, period)

        # Get expected S1 dates (every 6 days)
        expected_dates = get_sentinel1_dates_for_period(year, period)

        schedule.append({
            'Period': period,
            'Band': period,
            'Start_Date': start_date.strftime('%Y-%m-%d'),
            'End_Date': end_date.strftime('%Y-%m-%d'),
            'Expected_Acquisitions': len(expected_dates),
            'S1_Dates': ', '.join([d.strftime('%Y-%m-%d') for d in expected_dates])
        })

    df = pd.DataFrame(schedule)
    df.to_csv(output_file, index=False)

    logger.info(f"✓ Download schedule saved to: {output_file}")

    return df


def main():
    """Example usage and testing"""
    print("\n" + "="*70)
    print("12-DAY PERIOD UTILITIES - EXAMPLES")
    print("="*70)

    year = 2024

    # Example 1: Print period calendar
    print("\nExample 1: Period Calendar")
    print("-"*70)
    print_period_calendar(year)

    # Example 2: Get specific period dates
    print("\nExample 2: Get Period Dates")
    print("-"*70)
    for period in [1, 15, 31]:
        start, end = get_period_dates(year, period)
        print(f"Period {period:2d}: {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}")

    # Example 3: Get period from date
    print("\nExample 3: Date to Period Conversion")
    print("-"*70)
    test_dates = [
        datetime(2024, 1, 5),   # Should be period 1
        datetime(2024, 1, 15),  # Should be period 2
        datetime(2024, 6, 15),  # Mid-year
        datetime(2024, 12, 30)  # End of year
    ]

    for date in test_dates:
        period = get_period_from_date(date)
        print(f"{date.strftime('%Y-%m-%d')} → Period {period}")

    # Example 4: Generate period lookup CSV
    print("\nExample 4: Generate Period Lookup CSV")
    print("-"*70)
    df = generate_period_lookup_csv(year, 'perioda_example.csv')
    print(df.head())
    print(f"... {len(df)} total periods")

    # Example 5: Valid prediction periods
    print("\nExample 5: Valid Prediction Periods")
    print("-"*70)
    valid = get_valid_prediction_periods(total_bands=31, n_previous=6)
    print(f"With 31 bands and backward window of 7:")
    print(f"  Valid periods: {valid[0]} to {valid[-1]}")
    print(f"  Total valid predictions: {len(valid)}")

    # Example 6: Download schedule
    print("\nExample 6: Sentinel-1 Download Schedule")
    print("-"*70)
    schedule = create_download_schedule(year, 'download_schedule_example.csv')
    print(schedule.head(3))
    print(f"... {len(schedule)} total periods")

    print("\n" + "="*70)
    print("Examples complete!")
    print("="*70 + "\n")


if __name__ == '__main__':
    main()
