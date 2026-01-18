#!/usr/bin/env python3
"""
Check spatial completeness for each 12-day period

If Java needs 7 tracks for full coverage, periods with <7 tracks have gaps
"""

import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import sys

# Add period_utils to path
sys.path.insert(0, str(Path(__file__).parent))
from period_utils import get_period_from_date

def extract_metadata(filename):
    """Extract date and orbit from filename"""
    match = re.search(r'S1([AB])_IW_GRDH.*?_(\d{8})T\d{6}.*?_(\d{6})', filename)

    if not match:
        return None

    date_str = match.group(2)
    orbit = int(match.group(3))

    date = datetime.strptime(date_str, '%Y%m%d')
    rel_orbit = orbit % 175 if orbit % 175 != 0 else 175

    return {
        'date': date,
        'period': get_period_from_date(date),
        'rel_orbit': rel_orbit
    }

def main():
    preprocessed_dir = Path('workspace/preprocessed_50m')

    if not preprocessed_dir.exists():
        print(f"Directory not found: {preprocessed_dir}")
        return

    scene_files = list(preprocessed_dir.glob('*_VH_*.tif'))

    if not scene_files:
        print("No files found")
        return

    print(f"Analyzing {len(scene_files)} scenes for spatial completeness...\n")

    # Group by period and track
    period_tracks = defaultdict(set)
    period_scenes = defaultdict(int)
    all_tracks = set()

    for scene_file in scene_files:
        meta = extract_metadata(scene_file.name)

        if meta:
            period = meta['period']
            track = meta['rel_orbit']

            period_tracks[period].add(track)
            period_scenes[period] += 1
            all_tracks.add(track)

    total_tracks = len(all_tracks)

    print("="*70)
    print("SPATIAL COMPLETENESS ANALYSIS")
    print("="*70)
    print(f"\nTotal unique tracks in dataset: {total_tracks}")
    print(f"Tracks: {sorted(all_tracks)}")
    print(f"\nFor complete Java coverage, each period should have all {total_tracks} tracks\n")

    # Analyze completeness
    complete_periods = []
    incomplete_periods = []

    print("-"*70)
    print(f"{'Period':<8} {'Tracks':<10} {'Scenes':<8} {'Status':<20} {'Missing Tracks'}")
    print("-"*70)

    for period in sorted(period_tracks.keys()):
        tracks = period_tracks[period]
        n_tracks = len(tracks)
        n_scenes = period_scenes[period]
        missing = all_tracks - tracks

        if n_tracks == total_tracks:
            status = "✓ COMPLETE"
            complete_periods.append(period)
            missing_str = "-"
        else:
            status = f"⚠ INCOMPLETE ({n_tracks}/{total_tracks})"
            incomplete_periods.append(period)
            missing_str = f"{sorted(missing)}"

        print(f"{period:<8} {n_tracks:>2}/{total_tracks:<5} {n_scenes:<8} {status:<20} {missing_str}")

    print("-"*70)

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"\nComplete periods (all {total_tracks} tracks): {len(complete_periods)}/31")
    print(f"Incomplete periods: {len(incomplete_periods)}/31")

    if incomplete_periods:
        print(f"\nIncomplete periods: {incomplete_periods}")
        print("\n⚠️  THESE PERIODS WILL HAVE SPATIAL GAPS (nodata areas)")

        # Estimate coverage
        avg_completeness = sum(len(period_tracks[p]) for p in period_tracks) / len(period_tracks)
        coverage_pct = (avg_completeness / total_tracks) * 100

        print(f"\nAverage spatial coverage: {coverage_pct:.1f}%")
        print(f"Average tracks per period: {avg_completeness:.1f}/{total_tracks}")
    else:
        print("\n✓ ALL PERIODS HAVE COMPLETE COVERAGE!")

    # Recommendations
    print("\n" + "="*70)
    print("IMPACT & RECOMMENDATIONS")
    print("="*70)

    if len(incomplete_periods) == 0:
        print("\n✓ Perfect! All periods have all tracks.")
        print("  → No spatial gaps in any period")
        print("  → Ready for Java-wide mapping")

    elif len(incomplete_periods) <= 5:
        print(f"\n⚠️  {len(incomplete_periods)} periods have incomplete coverage")
        print("\nOptions:")
        print("  1. Accept gaps (nodata) in those periods")
        print("  2. Use temporal interpolation to fill gaps")
        print("  3. Acquire/process missing scenes if available")

        print(f"\n  → {len(complete_periods)} complete periods still usable for training!")

    elif len(incomplete_periods) <= 15:
        print(f"\n⚠️  {len(incomplete_periods)} periods have incomplete coverage")
        print("\nRecommendations:")
        print("  1. Use temporal interpolation (recommended)")
        print("  2. Train on complete periods only")
        print("  3. Use longer compositing windows (e.g., 24-day)")

        print(f"\n  → Consider {len(complete_periods)} complete periods sufficient")

    else:
        print(f"\n⚠️⚠️  {len(incomplete_periods)} periods incomplete - SERIOUS GAPS")
        print("\nThis suggests:")
        print("  • Sentinel-1 acquisition gaps")
        print("  • Download/preprocessing issues")
        print("  • Need to acquire more data")

        print(f"\n  → Only {len(complete_periods)} complete periods available")

    # Per-track analysis
    print("\n" + "="*70)
    print("PER-TRACK TEMPORAL COVERAGE")
    print("="*70)

    track_period_count = defaultdict(int)
    for period, tracks in period_tracks.items():
        for track in tracks:
            track_period_count[track] += 1

    print(f"\n{'Track':<10} {'Periods':<15} {'Coverage'}")
    print("-"*70)
    for track in sorted(all_tracks):
        n_periods = track_period_count[track]
        coverage = (n_periods / 31) * 100
        bar = "█" * int(coverage / 5) + "░" * (20 - int(coverage / 5))
        print(f"R{track:>3}      {n_periods:>2}/31          {bar} {coverage:>5.1f}%")

    # Identify problematic tracks
    print("\n" + "="*70)
    print("TEMPORAL GAPS BY TRACK")
    print("="*70)

    for track in sorted(all_tracks):
        missing_periods = []
        for period in range(1, 32):
            if track not in period_tracks[period]:
                missing_periods.append(period)

        if missing_periods:
            print(f"\nTrack R{track:03d}: Missing {len(missing_periods)} periods")
            # Group consecutive periods
            if len(missing_periods) <= 10:
                print(f"  Missing: {missing_periods}")
            else:
                print(f"  Missing: {missing_periods[:5]} ... {missing_periods[-5:]}")

    print("\n" + "="*70)

if __name__ == '__main__':
    main()
