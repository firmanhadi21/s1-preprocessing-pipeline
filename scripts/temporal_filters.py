#!/usr/bin/env python3
"""
Temporal Filtering for Sentinel-1 Time Series

Implements Heikin-Ashi smoothing technique adapted for SAR backscatter data.
This reduces noise while preserving important temporal trends.

Heikin-Ashi Concept:
- Originally from Japanese candlestick charts
- Smooths data by averaging with previous values
- Reduces false signals and highlights trends
- Adapted here for VH backscatter time series

Usage:
    from temporal_filters import apply_heikin_ashi, HeikinAshiFilter

    # Simple usage
    smoothed_vh = apply_heikin_ashi(vh_timeseries)

    # Advanced usage with custom weights
    filter = HeikinAshiFilter(weight_current=0.5, weight_previous=0.5)
    smoothed = filter.smooth_timeseries(vh_timeseries)
"""

import numpy as np
from typing import Optional, Tuple, Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HeikinAshiFilter:
    """
    Heikin-Ashi temporal smoothing filter for SAR time series

    Adapted from candlestick chart technique to smooth VH backscatter values.
    """

    def __init__(self, weight_current: float = 0.5, weight_previous: float = 0.5):
        """
        Initialize Heikin-Ashi filter

        Args:
            weight_current: Weight for current observation (0-1)
            weight_previous: Weight for previous smoothed value (0-1)

        Note: Weights will be normalized to sum to 1.0
        """
        total = weight_current + weight_previous
        self.w_current = weight_current / total
        self.w_previous = weight_previous / total

        logger.info(f"Heikin-Ashi Filter initialized:")
        logger.info(f"  Current weight: {self.w_current:.3f}")
        logger.info(f"  Previous weight: {self.w_previous:.3f}")


    def smooth_1d(self, timeseries: np.ndarray,
                  initial_value: Optional[float] = None) -> np.ndarray:
        """
        Apply Heikin-Ashi smoothing to 1D time series

        Formula:
            HA[t] = w_current * Value[t] + w_previous * HA[t-1]

        Args:
            timeseries: 1D array of VH values in temporal order (oldest to newest)
            initial_value: Initial smoothed value (if None, uses first observation)

        Returns:
            Smoothed time series (same length as input)
        """
        if len(timeseries) == 0:
            return timeseries

        smoothed = np.zeros_like(timeseries, dtype=np.float32)

        # Initialize with first value or provided initial value
        smoothed[0] = initial_value if initial_value is not None else timeseries[0]

        # Apply Heikin-Ashi formula
        for t in range(1, len(timeseries)):
            smoothed[t] = (self.w_current * timeseries[t] +
                          self.w_previous * smoothed[t-1])

        return smoothed


    def smooth_timeseries(self, timeseries: np.ndarray,
                         axis: int = -1) -> np.ndarray:
        """
        Apply Heikin-Ashi smoothing to multi-dimensional time series

        Args:
            timeseries: Array with time dimension
                       Shape can be (n_times,) or (n_samples, n_times) or (height, width, n_times)
            axis: Axis along which to apply smoothing (default: last axis)

        Returns:
            Smoothed array (same shape as input)
        """
        # Handle 1D case
        if timeseries.ndim == 1:
            return self.smooth_1d(timeseries)

        # For multi-dimensional, apply along specified axis
        return np.apply_along_axis(self.smooth_1d, axis, timeseries)


    def smooth_backward_series(self, vh_values: np.ndarray) -> np.ndarray:
        """
        Smooth backward-looking time series (t0, t1, t2, ..., t6)

        For rice growth stage mapping, where:
        - vh_values[0] = current period (t0)
        - vh_values[1] = 1 period back (t1)
        - vh_values[6] = 6 periods back (t6)

        Args:
            vh_values: Array of shape (n_samples, 7) or (7,)
                      Values in backward order: [t0, t1, t2, t3, t4, t5, t6]

        Returns:
            Smoothed VH values (same shape)
        """
        # Reverse to forward order for smoothing
        if vh_values.ndim == 1:
            forward = vh_values[::-1]  # [t6, t5, t4, t3, t2, t1, t0]
            smoothed_forward = self.smooth_1d(forward)
            smoothed_backward = smoothed_forward[::-1]  # Back to [t0, t1, ..., t6]
            return smoothed_backward
        else:
            # Multiple samples: (n_samples, 7)
            forward = vh_values[:, ::-1]  # Reverse time axis
            smoothed_forward = np.apply_along_axis(self.smooth_1d, 1, forward)
            smoothed_backward = smoothed_forward[:, ::-1]
            return smoothed_backward


    def smooth_spatial_temporal(self, data: np.ndarray) -> np.ndarray:
        """
        Smooth spatial-temporal data (e.g., raster time series)

        Args:
            data: Array of shape (n_bands, height, width)
                 where n_bands = temporal acquisitions

        Returns:
            Smoothed array (same shape)
        """
        n_bands, height, width = data.shape
        smoothed = np.zeros_like(data, dtype=np.float32)

        # Apply smoothing for each pixel's time series
        for i in range(height):
            for j in range(width):
                pixel_timeseries = data[:, i, j]

                # Skip if all NaN or invalid
                if np.all(np.isnan(pixel_timeseries)) or np.all(pixel_timeseries == -32768):
                    smoothed[:, i, j] = pixel_timeseries
                else:
                    smoothed[:, i, j] = self.smooth_1d(pixel_timeseries)

        return smoothed


def apply_heikin_ashi(timeseries: np.ndarray,
                     weight_current: float = 0.5,
                     weight_previous: float = 0.5,
                     axis: int = -1) -> np.ndarray:
    """
    Convenience function to apply Heikin-Ashi smoothing

    Args:
        timeseries: Time series data
        weight_current: Weight for current value (default: 0.5)
        weight_previous: Weight for previous smoothed value (default: 0.5)
        axis: Axis to smooth along (default: -1)

    Returns:
        Smoothed time series

    Example:
        >>> vh_series = np.array([-1800, -1750, -1900, -1600, -1400, -1300, -1500])
        >>> smoothed = apply_heikin_ashi(vh_series)
        >>> print(smoothed)
    """
    filter = HeikinAshiFilter(weight_current, weight_previous)
    return filter.smooth_timeseries(timeseries, axis=axis)


def compare_filtering_methods(timeseries: np.ndarray) -> Dict[str, np.ndarray]:
    """
    Compare different Heikin-Ashi weight configurations

    Args:
        timeseries: Original time series

    Returns:
        Dictionary with different smoothed versions
    """
    results = {
        'original': timeseries,
        'ha_balanced': apply_heikin_ashi(timeseries, 0.5, 0.5),
        'ha_aggressive': apply_heikin_ashi(timeseries, 0.3, 0.7),
        'ha_conservative': apply_heikin_ashi(timeseries, 0.7, 0.3),
    }

    return results


def visualize_filtering(timeseries: np.ndarray,
                       smoothed: np.ndarray,
                       title: str = "Heikin-Ashi Temporal Filtering"):
    """
    Visualize original vs smoothed time series

    Args:
        timeseries: Original time series
        smoothed: Smoothed time series
        title: Plot title
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not available for visualization")
        return

    plt.figure(figsize=(12, 6))

    time_points = np.arange(len(timeseries))

    plt.plot(time_points, timeseries, 'o-', label='Original',
             alpha=0.6, linewidth=2, markersize=8)
    plt.plot(time_points, smoothed, 's-', label='Heikin-Ashi Smoothed',
             linewidth=2, markersize=6)

    plt.xlabel('Time Period', fontsize=12)
    plt.ylabel('VH Backscatter (dB × 100)', fontsize=12)
    plt.title(title, fontsize=14, fontweight='bold')
    plt.legend(fontsize=11)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    return plt


def filter_training_data(feature_df, vh_columns: list = None):
    """
    Apply Heikin-Ashi filtering to training data DataFrame

    Args:
        feature_df: Training DataFrame with VH time series columns
        vh_columns: List of VH column names (default: VH_t0 through VH_t6)

    Returns:
        DataFrame with smoothed VH values
    """
    import pandas as pd

    if vh_columns is None:
        vh_columns = [f'VH_t{i}' for i in range(7)]

    # Check columns exist
    missing = [col for col in vh_columns if col not in feature_df.columns]
    if missing:
        logger.error(f"Missing columns: {missing}")
        return feature_df

    logger.info(f"Applying Heikin-Ashi filtering to {len(feature_df)} samples...")

    # Extract VH time series
    vh_data = feature_df[vh_columns].values  # Shape: (n_samples, 7)

    # Apply filtering (backward order)
    filter = HeikinAshiFilter(weight_current=0.5, weight_previous=0.5)
    vh_smoothed = filter.smooth_backward_series(vh_data)

    # Create new DataFrame with smoothed values
    filtered_df = feature_df.copy()
    filtered_df[vh_columns] = vh_smoothed

    # Recalculate derived features (differences and ratios)
    for i in range(6):
        # Differences
        diff_col = f'VH_diff_t{i}'
        if diff_col in filtered_df.columns:
            filtered_df[diff_col] = vh_smoothed[:, i] - vh_smoothed[:, i+1]

        # Ratios
        ratio_col = f'VH_ratio_t{i}'
        if ratio_col in filtered_df.columns:
            denominator = np.abs(vh_smoothed[:, i+1])
            denominator = np.where(denominator < 1e-10, 1e-10, denominator)
            filtered_df[ratio_col] = vh_smoothed[:, i] / denominator

    logger.info("✓ Filtering complete")

    return filtered_df


def filter_raster_timeseries(input_file: str, output_file: str,
                            weight_current: float = 0.5,
                            weight_previous: float = 0.5):
    """
    Apply Heikin-Ashi filtering to multi-band raster time series

    Args:
        input_file: Input GeoTIFF with temporal bands
        output_file: Output GeoTIFF (smoothed)
        weight_current: Current value weight
        weight_previous: Previous smoothed value weight
    """
    try:
        import rasterio
    except ImportError:
        logger.error("rasterio not available")
        return

    logger.info(f"Filtering raster: {input_file}")

    with rasterio.open(input_file) as src:
        # Read all bands
        data = src.read()  # Shape: (n_bands, height, width)
        profile = src.profile.copy()

        logger.info(f"  Bands: {data.shape[0]}")
        logger.info(f"  Dimensions: {data.shape[1]} x {data.shape[2]}")

        # Apply filtering
        filter = HeikinAshiFilter(weight_current, weight_previous)
        smoothed = filter.smooth_spatial_temporal(data)

        # Write output
        profile.update(compress='lzw', tiled=True)

        with rasterio.open(output_file, 'w', **profile) as dst:
            dst.write(smoothed)

        logger.info(f"✓ Filtered raster saved to: {output_file}")


def main():
    """Example usage and testing"""
    print("="*60)
    print("HEIKIN-ASHI TEMPORAL FILTERING")
    print("="*60)

    # Example 1: Simple time series
    print("\nExample 1: Smoothing a single time series")
    print("-"*60)

    # Simulated VH backscatter values (dB × 100)
    # Represents rice growth from flooding to harvest
    vh_series = np.array([-2000, -1850, -1700, -1500, -1300, -1400, -1600])

    print(f"Original VH values: {vh_series}")

    # Apply Heikin-Ashi smoothing
    smoothed = apply_heikin_ashi(vh_series, weight_current=0.5, weight_previous=0.5)

    print(f"Smoothed VH values: {smoothed.astype(int)}")

    # Calculate noise reduction
    original_variance = np.var(np.diff(vh_series))
    smoothed_variance = np.var(np.diff(smoothed))
    noise_reduction = (1 - smoothed_variance / original_variance) * 100

    print(f"\nNoise reduction: {noise_reduction:.1f}%")

    # Example 2: Multiple time series (batch)
    print("\n\nExample 2: Smoothing multiple time series")
    print("-"*60)

    # 5 samples, each with 7 time points
    vh_batch = np.array([
        [-2000, -1850, -1700, -1500, -1300, -1400, -1600],
        [-1900, -1750, -1600, -1450, -1350, -1450, -1700],
        [-2100, -1900, -1750, -1550, -1400, -1500, -1650],
        [-1950, -1800, -1650, -1500, -1350, -1400, -1600],
        [-2050, -1850, -1700, -1550, -1300, -1350, -1550],
    ])

    print(f"Batch shape: {vh_batch.shape}")

    filter = HeikinAshiFilter(weight_current=0.5, weight_previous=0.5)
    smoothed_batch = filter.smooth_backward_series(vh_batch)

    print(f"Smoothed batch shape: {smoothed_batch.shape}")
    print(f"\nFirst sample original: {vh_batch[0]}")
    print(f"First sample smoothed: {smoothed_batch[0].astype(int)}")

    # Example 3: Compare different weights
    print("\n\nExample 3: Comparing different smoothing strengths")
    print("-"*60)

    comparisons = compare_filtering_methods(vh_series)

    for name, series in comparisons.items():
        print(f"{name:20s}: {series.astype(int)}")

    # Example 4: Visualization
    print("\n\nExample 4: Visualization")
    print("-"*60)

    try:
        plt = visualize_filtering(vh_series, smoothed)
        print("Visualization created (close plot window to continue)")
        plt.show()
    except:
        print("Visualization skipped (matplotlib not available)")

    print("\n" + "="*60)
    print("Examples complete!")
    print("="*60)


if __name__ == '__main__':
    main()
