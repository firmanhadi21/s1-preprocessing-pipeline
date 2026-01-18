#!/usr/bin/env python3
"""
Check how many Sentinel-1 tracks (relative orbits) cover your area
"""

import re
from pathlib import Path
from collections import defaultdict
import sys

def extract_orbit_info(filename):
    """Extract satellite and orbit number from S1 filename"""
    match = re.search(r'S1([AB])_IW_GRDH.*?_(\d{8})T\d{6}_(\d{8})T\d{6}_(\d{6})', filename)

    if not match:
        return None

    satellite = match.group(1)
    orbit_number = int(match.group(4))

    # Calculate relative orbit (1-175 for each satellite)
    relative_orbit = orbit_number % 175
    if relative_orbit == 0:
        relative_orbit = 175

    return {
        'satellite': f'S1{satellite}',
        'absolute_orbit': orbit_number,
        'relative_orbit': relative_orbit,
        'track_id': f'S1{satellite}_R{relative_orbit:03d}'
    }

def main():
    # Check preprocessed files
    preprocessed_dir = Path('workspace/preprocessed_50m')

    if not preprocessed_dir.exists():
        print(f"Directory not found: {preprocessed_dir}")
        print("Run from repository root, or adjust path")
        sys.exit(1)

    scene_files = list(preprocessed_dir.glob('*_VH_*.tif'))

    if not scene_files:
        print(f"No preprocessed files found in {preprocessed_dir}")
        print("Preprocessing may still be running")
        sys.exit(0)

    print(f"Analyzing {len(scene_files)} preprocessed scenes...\n")

    # Group by track
    tracks = defaultdict(list)

    for scene_file in scene_files:
        orbit_info = extract_orbit_info(scene_file.name)

        if orbit_info:
            tracks[orbit_info['track_id']].append(scene_file.name)

    # Print summary
    print("="*70)
    print("TRACK COVERAGE ANALYSIS")
    print("="*70)
    print(f"\nTotal scenes: {len(scene_files)}")
    print(f"Unique tracks: {len(tracks)}\n")

    # Sort tracks by number of scenes
    sorted_tracks = sorted(tracks.items(), key=lambda x: len(x[1]), reverse=True)

    print("Track breakdown:")
    print("-" * 70)
    print(f"{'Track ID':<15} {'Satellite':<10} {'Rel. Orbit':<12} {'# Scenes':<10}")
    print("-" * 70)

    for track_id, scenes in sorted_tracks:
        satellite = track_id[:3]
        rel_orbit = int(track_id.split('_R')[1])
        print(f"{track_id:<15} {satellite:<10} {rel_orbit:<12} {len(scenes):<10}")

    print("-" * 70)
    print(f"{'TOTAL':<15} {'':<10} {'':<12} {len(scene_files):<10}")
    print("="*70)

    # Estimate coverage
    print("\n" + "="*70)
    print("COVERAGE ESTIMATION")
    print("="*70)

    s1a_tracks = [t for t in tracks.keys() if t.startswith('S1A')]
    s1b_tracks = [t for t in tracks.keys() if t.startswith('S1B')]

    print(f"\nS1A tracks: {len(s1a_tracks)}")
    print(f"S1B tracks: {len(s1b_tracks)}")

    if len(tracks) <= 2:
        coverage = "Small area (single swath)"
    elif len(tracks) <= 4:
        coverage = "Medium area (2-3 swaths wide)"
    elif len(tracks) <= 7:
        coverage = "Large area (Java-wide or similar)"
    else:
        coverage = "Very large area (multiple islands or regional)"

    print(f"\nEstimated coverage: {coverage}")
    print(f"Each track swath: ~250 km wide")
    print(f"Your area width: ~{len(tracks) * 150} - {len(tracks) * 250} km")

    # Check if ascending/descending
    print("\n" + "="*70)
    print("ORBIT GEOMETRY")
    print("="*70)
    print("\nNote: Sentinel-1 relative orbits 1-175 cover the globe")
    print("- Orbits 1-87: Mostly ascending")
    print("- Orbits 88-175: Mostly descending")

    ascending = [t for t in sorted_tracks if int(t[0].split('_R')[1]) < 88]
    descending = [t for t in sorted_tracks if int(t[0].split('_R')[1]) >= 88]

    print(f"\nYour tracks:")
    print(f"  Ascending: {len(ascending)} tracks")
    print(f"  Descending: {len(descending)} tracks")

    if len(ascending) > 0 and len(descending) > 0:
        print("\n⚠️  You have BOTH ascending and descending tracks!")
        print("   Different geometries may need separate processing")
        print("   Consider filtering to one geometry for consistency")

    print("\n" + "="*70)
    print("RECOMMENDATIONS")
    print("="*70)

    if len(tracks) == 1:
        print("\n✓ Single track - no mosaicking needed!")
        print("  Just stack scenes temporally")
    elif len(tracks) <= 4:
        print(f"\n✓ {len(tracks)} tracks - straightforward mosaicking")
        print("  Track-based compositing + gdalwarp will work great")
    elif len(tracks) <= 8:
        print(f"\n✓ {len(tracks)} tracks - standard multi-track mosaicking")
        print("  Use the s1_mosaic_java_12day.py script as designed")
    else:
        print(f"\n⚠️  {len(tracks)} tracks - complex mosaicking")
        print("  Consider:")
        print("  1. Processing by region (split Java into west/central/east)")
        print("  2. Using only one orbit geometry (ascending OR descending)")
        print("  3. Filtering to most frequent tracks only")

    print("\n" + "="*70)

if __name__ == '__main__':
    main()
