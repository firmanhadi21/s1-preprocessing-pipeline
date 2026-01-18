#!/usr/bin/env python3
"""
Verify Period-Based Folder Structure

This script checks if the period-based folder structure is correctly set up.
It verifies:
- Period folders (p1, p2, ..., p31) exist
- Required subfolders (downloads, preprocessed, geotiff) exist
- Mosaic naming follows the new convention (mosaic_p*.tif)
- BIGTIFF support in mosaics
- Reports file counts and potential issues

Usage:
    python verify_period_structure.py --workspace workspace_java/year_2024
    python verify_period_structure.py --workspace workspace_java/year_2024 --verbose
"""

import argparse
from pathlib import Path
import sys
from typing import Dict, List, Tuple

try:
    import rasterio
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False
    print("Warning: rasterio not available - BIGTIFF check will be skipped")


class StructureVerifier:
    """Verify period-based folder structure"""

    def __init__(self, workspace: Path, verbose: bool = False):
        self.workspace = workspace
        self.verbose = verbose
        self.issues = []
        self.warnings = []

    def log(self, message: str, level: str = "INFO"):
        """Log message based on verbosity"""
        if level == "ERROR":
            self.issues.append(message)
            print(f"❌ ERROR: {message}")
        elif level == "WARNING":
            self.warnings.append(message)
            print(f"⚠️  WARNING: {message}")
        elif self.verbose or level == "INFO":
            print(f"✓ {message}")

    def check_base_structure(self) -> bool:
        """Check if workspace exists and has required base folders"""
        print("\n" + "="*70)
        print("CHECKING BASE STRUCTURE")
        print("="*70)

        if not self.workspace.exists():
            self.log(f"Workspace not found: {self.workspace}", "ERROR")
            return False

        self.log(f"Workspace found: {self.workspace}")

        # Check for required base folders
        required_folders = ['period_mosaics', 'final_stack', 'temp']
        for folder_name in required_folders:
            folder = self.workspace / folder_name
            if folder.exists():
                self.log(f"Found {folder_name}/")
            else:
                self.log(f"Missing {folder_name}/", "WARNING")

        return True

    def check_period_folders(self) -> Dict[int, Dict[str, bool]]:
        """Check period folders structure"""
        print("\n" + "="*70)
        print("CHECKING PERIOD FOLDERS (p1 - p31)")
        print("="*70)

        period_status = {}

        for period in range(1, 32):
            period_dir = self.workspace / f"p{period}"

            status = {
                'exists': period_dir.exists(),
                'downloads': False,
                'preprocessed': False,
                'geotiff': False,
                'download_count': 0,
                'preprocessed_count': 0,
                'geotiff_count': 0
            }

            if status['exists']:
                # Check subfolders
                downloads_dir = period_dir / 'downloads'
                preprocessed_dir = period_dir / 'preprocessed'
                geotiff_dir = period_dir / 'geotiff'

                status['downloads'] = downloads_dir.exists()
                status['preprocessed'] = preprocessed_dir.exists()
                status['geotiff'] = geotiff_dir.exists()

                # Count files
                if status['downloads']:
                    status['download_count'] = len(list(downloads_dir.glob('*.zip')))
                if status['preprocessed']:
                    status['preprocessed_count'] = len(list(preprocessed_dir.glob('*.dim')))
                if status['geotiff']:
                    status['geotiff_count'] = len(list(geotiff_dir.glob('*_VH.tif')))

                if self.verbose:
                    self.log(f"Period {period:2d}: downloads={status['download_count']}, "
                           f"preprocessed={status['preprocessed_count']}, "
                           f"geotiff={status['geotiff_count']}")
            else:
                if self.verbose:
                    self.log(f"Period {period:2d}: folder not found", "WARNING")

            period_status[period] = status

        # Summary
        existing_periods = [p for p, s in period_status.items() if s['exists']]
        print(f"\nPeriod folders found: {len(existing_periods)}/31")

        if len(existing_periods) < 31:
            missing = [p for p in range(1, 32) if p not in existing_periods]
            self.log(f"Missing period folders: {missing}", "WARNING")

        return period_status

    def check_mosaics(self) -> Dict[int, Path]:
        """Check period mosaics"""
        print("\n" + "="*70)
        print("CHECKING PERIOD MOSAICS")
        print("="*70)

        mosaics_dir = self.workspace / 'period_mosaics'

        if not mosaics_dir.exists():
            self.log("period_mosaics/ folder not found", "ERROR")
            return {}

        # Look for new naming convention: mosaic_p*.tif
        mosaics = {}
        for mosaic_file in sorted(mosaics_dir.glob('mosaic_p*.tif')):
            # Extract period number
            period_str = mosaic_file.stem.replace('mosaic_p', '')
            try:
                period = int(period_str)
                mosaics[period] = mosaic_file

                # Check BIGTIFF if rasterio available
                if RASTERIO_AVAILABLE:
                    try:
                        with rasterio.open(mosaic_file) as src:
                            # Check if BIGTIFF
                            is_bigtiff = src.profile.get('BIGTIFF', 'NO') == 'YES'
                            file_size_mb = mosaic_file.stat().st_size / (1024 * 1024)

                            if self.verbose:
                                bigtiff_status = "✓ BIGTIFF" if is_bigtiff else "✗ Not BIGTIFF"
                                self.log(f"Period {period:2d}: {mosaic_file.name} "
                                       f"({file_size_mb:.1f} MB, {bigtiff_status})")

                            # Warn if large file without BIGTIFF
                            if file_size_mb > 2000 and not is_bigtiff:
                                self.log(f"Period {period}: Large file without BIGTIFF "
                                       f"({file_size_mb:.1f} MB)", "WARNING")
                    except Exception as e:
                        self.log(f"Period {period}: Cannot read mosaic - {e}", "WARNING")
                else:
                    if self.verbose:
                        self.log(f"Period {period:2d}: {mosaic_file.name}")

            except ValueError:
                self.log(f"Invalid mosaic filename: {mosaic_file.name}", "WARNING")

        # Check for old naming convention
        old_mosaics = list(mosaics_dir.glob('period_*_VH.tif'))
        if old_mosaics:
            self.log(f"Found {len(old_mosaics)} files with old naming (period_*_VH.tif)", "WARNING")
            self.log("Consider renaming to new convention (mosaic_p*.tif)", "WARNING")

        print(f"\nMosaics found: {len(mosaics)}/31 (new naming convention)")

        if len(mosaics) < 31:
            missing = [p for p in range(1, 32) if p not in mosaics]
            self.log(f"Missing mosaics for periods: {missing}", "WARNING")

        return mosaics

    def check_final_stack(self) -> bool:
        """Check final stack"""
        print("\n" + "="*70)
        print("CHECKING FINAL STACK")
        print("="*70)

        final_stack_dir = self.workspace / 'final_stack'

        if not final_stack_dir.exists():
            self.log("final_stack/ folder not found", "WARNING")
            return False

        # Look for stack file
        stacks = list(final_stack_dir.glob('S1_VH_stack_*_31bands.tif'))

        if not stacks:
            self.log("No final stack found", "WARNING")
            return False

        for stack in stacks:
            file_size_gb = stack.stat().st_size / (1024**3)
            self.log(f"Found stack: {stack.name} ({file_size_gb:.2f} GB)")

            if RASTERIO_AVAILABLE:
                try:
                    with rasterio.open(stack) as src:
                        self.log(f"  Bands: {src.count}")
                        self.log(f"  Shape: {src.height} x {src.width}")
                        self.log(f"  CRS: {src.crs}")

                        is_bigtiff = src.profile.get('BIGTIFF', 'NO') == 'YES'
                        bigtiff_status = "✓ BIGTIFF enabled" if is_bigtiff else "✗ BIGTIFF not enabled"
                        self.log(f"  {bigtiff_status}")

                        if src.count != 31:
                            self.log(f"Expected 31 bands, found {src.count}", "WARNING")

                except Exception as e:
                    self.log(f"Cannot read stack: {e}", "ERROR")
                    return False

        return True

    def generate_report(self, period_status: Dict, mosaics: Dict) -> None:
        """Generate summary report"""
        print("\n" + "="*70)
        print("SUMMARY REPORT")
        print("="*70)

        # Count statistics
        total_downloads = sum(s['download_count'] for s in period_status.values())
        total_preprocessed = sum(s['preprocessed_count'] for s in period_status.values())
        total_geotiffs = sum(s['geotiff_count'] for s in period_status.values())

        print(f"\nFile Counts:")
        print(f"  Downloads:     {total_downloads}")
        print(f"  Preprocessed:  {total_preprocessed}")
        print(f"  GeoTIFFs:      {total_geotiffs}")
        print(f"  Mosaics:       {len(mosaics)}/31")

        # Find periods with data
        periods_with_downloads = [p for p, s in period_status.items() if s['download_count'] > 0]
        periods_with_mosaics = list(mosaics.keys())

        print(f"\nPeriods with data:")
        print(f"  Downloads: {len(periods_with_downloads)} periods")
        print(f"  Mosaics:   {len(periods_with_mosaics)} periods")

        # Issues and warnings
        if self.issues:
            print(f"\n❌ Errors: {len(self.issues)}")
            for issue in self.issues:
                print(f"   - {issue}")
        else:
            print(f"\n✓ No errors found")

        if self.warnings:
            print(f"\n⚠️  Warnings: {len(self.warnings)}")
            for warning in self.warnings[:10]:  # Show first 10
                print(f"   - {warning}")
            if len(self.warnings) > 10:
                print(f"   ... and {len(self.warnings) - 10} more")
        else:
            print(f"\n✓ No warnings")

        # Recommendations
        print(f"\n" + "="*70)
        print("RECOMMENDATIONS")
        print("="*70)

        if total_downloads == 0:
            print("• Start by downloading data for specific periods")
            print("  python s1_period_pipeline.py --config CONFIG --year YEAR --periods 1-5 --download-only")
        elif total_preprocessed < total_downloads:
            print("• Run preprocessing on downloaded files")
            print("  python s1_period_pipeline.py --config CONFIG --year YEAR --preprocess-only")
        elif total_geotiffs < total_preprocessed:
            print("• Convert preprocessed files to GeoTIFF")
            print("  python s1_period_pipeline.py --config CONFIG --year YEAR --convert-only")
        elif len(mosaics) < len(periods_with_downloads):
            print("• Create mosaics for periods with GeoTIFFs")
            print("  python s1_period_pipeline.py --config CONFIG --year YEAR --mosaic-only")
        elif len(mosaics) == 31:
            print("• All mosaics ready! Create final stack")
            print("  python s1_period_pipeline.py --config CONFIG --year YEAR --stack-only")
        else:
            print("• Continue processing remaining periods")
            print("  python s1_period_pipeline.py --config CONFIG --year YEAR --run-all")


def main():
    parser = argparse.ArgumentParser(
        description='Verify period-based folder structure',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--workspace', required=True,
                      help='Workspace directory (e.g., workspace_java/year_2024)')
    parser.add_argument('--verbose', '-v', action='store_true',
                      help='Show detailed information for each period')

    args = parser.parse_args()

    workspace = Path(args.workspace)
    verifier = StructureVerifier(workspace, verbose=args.verbose)

    # Run checks
    if not verifier.check_base_structure():
        sys.exit(1)

    period_status = verifier.check_period_folders()
    mosaics = verifier.check_mosaics()
    verifier.check_final_stack()

    # Generate report
    verifier.generate_report(period_status, mosaics)

    # Exit code based on errors
    if verifier.issues:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
