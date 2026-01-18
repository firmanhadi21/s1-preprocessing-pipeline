#!/usr/bin/env python3
"""
Check actual pass direction from Sentinel-1 metadata

The orbit number heuristic is unreliable - need to check actual metadata
"""

from pathlib import Path
import subprocess
import re
from collections import defaultdict

def get_pass_direction_from_metadata(tif_file):
    """
    Get actual pass direction from GeoTIFF metadata

    SNAP processing embeds S1 metadata in the GeoTIFF
    """
    try:
        result = subprocess.run(
            ['gdalinfo', str(tif_file)],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            metadata = result.stdout

            # Look for ASCENDING or DESCENDING in metadata
            if 'ASCENDING' in metadata.upper():
                return 'ASCENDING'
            elif 'DESCENDING' in metadata.upper():
                return 'DESCENDING'

            # Check for pass direction metadata field
            match = re.search(r'PASS[_\s]DIRECTION[=:\s]+(\w+)', metadata, re.IGNORECASE)
            if match:
                return match.group(1).upper()

    except:
        pass

    return 'UNKNOWN'

def check_filename_pattern(filename):
    """
    Extract info from filename
    """
    match = re.search(r'S1([AB])_IW_GRDH.*?_(\d{8})T(\d{6}).*?_(\d{6})', filename)

    if match:
        satellite = match.group(1)
        date = match.group(2)
        time = match.group(3)
        orbit = int(match.group(4))

        return {
            'satellite': f'S1{satellite}',
            'date': date,
            'time': time,
            'orbit': orbit,
            'rel_orbit': orbit % 175 if orbit % 175 != 0 else 175
        }

    return None

def main():
    preprocessed_dir = Path('workspace/preprocessed_50m')

    if not preprocessed_dir.exists():
        print(f"Directory not found: {preprocessed_dir}")
        return

    # Check a sample of files
    scene_files = sorted(list(preprocessed_dir.glob('*_VH_*.tif')))[:20]  # Sample first 20

    if not scene_files:
        print("No files found")
        return

    print("Checking pass direction from GeoTIFF metadata...")
    print("(Sampling first 20 files)\n")

    results = defaultdict(list)

    for scene_file in scene_files:
        info = check_filename_pattern(scene_file.name)
        pass_dir = get_pass_direction_from_metadata(scene_file)

        if info:
            results[pass_dir].append({
                'file': scene_file.name[:60],
                'orbit': info['rel_orbit'],
                'time': info['time']
            })

    print("="*70)
    print("PASS DIRECTION ANALYSIS (from actual metadata)")
    print("="*70)

    for pass_dir in ['ASCENDING', 'DESCENDING', 'UNKNOWN']:
        if pass_dir in results:
            files = results[pass_dir]
            print(f"\n{pass_dir}: {len(files)} files")
            print("-"*70)

            for f in files[:5]:  # Show first 5 examples
                print(f"  R{f['orbit']:03d}  {f['time'][:4]}  {f['file']}")

            if len(files) > 5:
                print(f"  ... and {len(files)-5} more")

    print("\n" + "="*70)

    # Summary
    total = len(scene_files)
    ascending = len(results['ASCENDING'])
    descending = len(results['DESCENDING'])
    unknown = len(results['UNKNOWN'])

    print("\nSUMMARY (from 20 samples):")
    print(f"  Ascending:  {ascending:3d} ({ascending/total*100:.0f}%)")
    print(f"  Descending: {descending:3d} ({descending/total*100:.0f}%)")
    print(f"  Unknown:    {unknown:3d} ({unknown/total*100:.0f}%)")

    if unknown > 0:
        print("\n⚠️  Could not determine pass direction from metadata")
        print("   Trying alternative method...")
        print("\n" + "="*70)
        print("ACQUISITION TIME ANALYSIS")
        print("="*70)
        print("\nS1 acquisition times (UTC):")
        print("  Morning (~21:00-23:00 UTC) = Ascending over Indonesia")
        print("  Evening (~09:00-11:00 UTC) = Descending over Indonesia")

        print("\nYour scenes:")

        morning = []
        evening = []
        other = []

        for scene_file in scene_files:
            info = check_filename_pattern(scene_file.name)
            if info:
                hour = int(info['time'][:2])
                if 21 <= hour <= 23:
                    morning.append(info)
                elif 9 <= hour <= 11:
                    evening.append(info)
                else:
                    other.append(info)

        print(f"\n  Morning passes (21:00-23:00 UTC → Ascending):  {len(morning)}")
        if morning:
            print(f"    Example times: {', '.join([m['time'][:4] for m in morning[:5]])}")

        print(f"  Evening passes (09:00-11:00 UTC → Descending): {len(evening)}")
        if evening:
            print(f"    Example times: {', '.join([e['time'][:4] for e in evening[:5]])}")

        print(f"  Other times: {len(other)}")

        if len(morning) > len(evening) * 2:
            print("\n✓ Likely ALL ASCENDING based on acquisition times")
        elif len(evening) > len(morning) * 2:
            print("\n✓ Likely ALL DESCENDING based on acquisition times")
        else:
            print("\n⚠️  Mixed acquisition times - both geometries present")

    print("\n" + "="*70)

if __name__ == '__main__':
    main()
