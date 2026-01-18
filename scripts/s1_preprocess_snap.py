#!/usr/bin/env python3
"""
Sentinel-1 Preprocessing with ESA SNAP GPT

Processes Sentinel-1 GRD data using the SNAP Graph Processing Tool (GPT)
Based on the workflow defined in sen1_preprocessing-gpt.xml

Processing chain:
1. Read S1 product
2. Apply Orbit File
3. Thermal Noise Removal
4. Calibration (Beta0)
5. Terrain Flattening
6. Terrain Correction (Range Doppler)
7. Speckle Filtering (Gamma MAP 5x5)
8. Linear to dB conversion
9. Export to GeoTIFF

Requirements:
    - ESA SNAP installed (download from https://step.esa.int/main/download/snap-download/)
    - SNAP GPT in system PATH or specify path
    - Sufficient disk space (~5-10GB per scene)
"""

import os
import sys
import subprocess
from pathlib import Path
import logging
from datetime import datetime
from typing import List, Optional, Dict
import xml.etree.ElementTree as ET
import shutil
import zipfile

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SNAPPreprocessor:
    """
    Wrapper for SNAP GPT preprocessing
    """

    def __init__(self, snap_gpt_path=None, cache_size='8G', num_threads=None):
        """
        Initialize SNAP preprocessor

        Args:
            snap_gpt_path: Path to SNAP GPT executable
                          If None, searches in common locations
            cache_size: SNAP cache size (e.g., '8G', '16G')
            num_threads: Number of threads (None = auto)
        """
        self.gpt_path = snap_gpt_path or self._find_gpt()
        self.cache_size = cache_size
        self.num_threads = num_threads or os.cpu_count()

        if not self.gpt_path:
            raise FileNotFoundError(
                "SNAP GPT not found. Please install SNAP from "
                "https://step.esa.int/main/download/snap-download/ "
                "or specify path with snap_gpt_path parameter"
            )

        logger.info(f"SNAP GPT: {self.gpt_path}")
        logger.info(f"Cache size: {self.cache_size}")
        logger.info(f"Threads: {self.num_threads}")


    def _find_gpt(self) -> Optional[str]:
        """Find SNAP GPT executable"""
        # Common GPT locations
        common_paths = [
            '/usr/local/snap/bin/gpt',
            '/opt/snap/bin/gpt',
            '~/snap/bin/gpt',
            'C:\\Program Files\\snap\\bin\\gpt.exe',  # Windows
            '/Applications/snap/bin/gpt',  # macOS
        ]

        # Check in PATH first
        gpt = shutil.which('gpt')
        if gpt:
            return gpt

        # Check common locations
        for path in common_paths:
            expanded = Path(path).expanduser()
            if expanded.exists():
                return str(expanded)

        return None


    def process_scene(self, input_file: str, output_file: str,
                     graph_xml: str = 'sen1_preprocessing-gpt.xml',
                     aoi_wkt: Optional[str] = None,
                     subset: bool = False) -> bool:
        """
        Process single Sentinel-1 scene using SNAP GPT

        Args:
            input_file: Input .zip or .SAFE file
            output_file: Output filename (will create .dim and .data/)
            graph_xml: Path to SNAP graph XML file
            aoi_wkt: Area of Interest in WKT (for subsetting)
            subset: Whether to subset to AOI

        Returns:
            True if successful, False otherwise
        """
        logger.info("="*60)
        logger.info(f"PROCESSING: {Path(input_file).name}")
        logger.info("="*60)

        # Validate inputs
        input_path = Path(input_file)
        if not input_path.exists():
            logger.error(f"Input file not found: {input_file}")
            return False

        graph_path = Path(graph_xml)
        if not graph_path.exists():
            logger.error(f"Graph XML not found: {graph_xml}")
            return False

        # Create output directory
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build GPT command
        # Note: Use -P parameters to pass values to graph XML variables
        # The graph uses ${myFilename} for input and ${outputFile} for output
        cmd = [
            self.gpt_path,
            graph_xml,
            f'-PmyFilename={input_file}',
            f'-PoutputFile={output_file}',
            '-c', self.cache_size,
            '-q', str(self.num_threads)
        ]

        # Add subset if specified
        if subset and aoi_wkt:
            cmd.append(f'-Paoi={aoi_wkt}')

        logger.info(f"Output: {output_file}")
        logger.info(f"Command: {' '.join(cmd)}")

        # Execute GPT
        start_time = datetime.now()

        try:
            # Run GPT with real-time output
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )

            # Print output in real-time
            for line in process.stdout:
                line = line.strip()
                if line:
                    # Filter SNAP's verbose output, keep important messages
                    if any(keyword in line.lower() for keyword in
                           ['processing', 'operator', 'complete', 'error', 'warning']):
                        logger.info(f"  {line}")

            process.wait()

            if process.returncode != 0:
                logger.error(f"GPT failed with return code {process.returncode}")
                return False

            elapsed = datetime.now() - start_time
            logger.info(f"✓ Processing completed in {elapsed}")

            # Verify output
            if output_path.with_suffix('.dim').exists():
                logger.info(f"✓ Output created: {output_file}")
                return True
            else:
                logger.error(f"✗ Output file not created")
                return False

        except Exception as e:
            logger.error(f"Error during processing: {str(e)}")
            return False


    def convert_to_geotiff(self, dim_file: str, output_tif: str,
                          band_name: str = 'Beta0_VH_db') -> bool:
        """
        Convert BEAM-DIMAP (.dim) to GeoTIFF

        Args:
            dim_file: Input .dim file
            output_tif: Output .tif file
            band_name: Name of band to export

        Returns:
            True if successful
        """
        logger.info(f"Converting to GeoTIFF: {Path(dim_file).name} -> {Path(output_tif).name}")

        # Use GDAL to convert
        try:
            from osgeo import gdal
        except ImportError:
            logger.error("GDAL not available. Install with: conda install gdal")
            return False

        try:
            # Open DIM file
            dataset = gdal.Open(dim_file)
            if dataset is None:
                logger.error(f"Failed to open {dim_file}")
                return False

            # Find band by name
            band_idx = None
            for i in range(1, dataset.RasterCount + 1):
                band = dataset.GetRasterBand(i)
                if band.GetDescription() == band_name:
                    band_idx = i
                    break

            if band_idx is None:
                logger.warning(f"Band '{band_name}' not found, using band 1")
                band_idx = 1

            # Create output
            driver = gdal.GetDriverByName('GTiff')
            out_ds = driver.CreateCopy(
                output_tif,
                dataset,
                options=['COMPRESS=LZW', 'TILED=YES']
            )

            out_ds = None
            dataset = None

            logger.info(f"✓ GeoTIFF created: {output_tif}")
            return True

        except Exception as e:
            logger.error(f"Error converting to GeoTIFF: {str(e)}")
            return False


    def batch_process(self, input_files: List[str], output_dir: str,
                     graph_xml: str = 'sen1_preprocessing-gpt.xml',
                     convert_to_tif: bool = True) -> List[str]:
        """
        Process multiple Sentinel-1 scenes

        Args:
            input_files: List of input .zip files
            output_dir: Output directory
            graph_xml: SNAP graph XML file
            convert_to_tif: Whether to convert outputs to GeoTIFF

        Returns:
            List of successfully processed output files
        """
        logger.info("="*60)
        logger.info(f"BATCH PROCESSING {len(input_files)} SCENES")
        logger.info("="*60)

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        processed_files = []
        failed_files = []

        for i, input_file in enumerate(input_files, 1):
            logger.info(f"\n[{i}/{len(input_files)}] Processing: {Path(input_file).name}")

            # Generate output filename
            input_name = Path(input_file).stem
            output_dim = output_dir / f"{input_name}_processed"

            # Process
            success = self.process_scene(
                input_file=input_file,
                output_file=str(output_dim),
                graph_xml=graph_xml
            )

            if success:
                # Convert to GeoTIFF if requested
                if convert_to_tif:
                    output_tif = output_dir / f"{input_name}_processed.tif"
                    tif_success = self.convert_to_geotiff(
                        dim_file=f"{output_dim}.dim",
                        output_tif=str(output_tif)
                    )

                    if tif_success:
                        processed_files.append(str(output_tif))
                    else:
                        processed_files.append(f"{output_dim}.dim")
                else:
                    processed_files.append(f"{output_dim}.dim")
            else:
                failed_files.append(input_file)

        # Summary
        logger.info("\n" + "="*60)
        logger.info("BATCH PROCESSING SUMMARY")
        logger.info("="*60)
        logger.info(f"Total scenes: {len(input_files)}")
        logger.info(f"Successful: {len(processed_files)}")
        logger.info(f"Failed: {len(failed_files)}")

        if failed_files:
            logger.warning("\nFailed files:")
            for f in failed_files:
                logger.warning(f"  {f}")

        return processed_files


    def extract_vh_band(self, processed_file: str, output_vh: str) -> bool:
        """
        Extract VH band from processed file

        Args:
            processed_file: Processed .dim or .tif file
            output_vh: Output VH GeoTIFF

        Returns:
            True if successful
        """
        try:
            from osgeo import gdal
        except ImportError:
            logger.error("GDAL not available")
            return False

        try:
            # Open file
            dataset = gdal.Open(processed_file)
            if dataset is None:
                return False

            # Find VH band (look for Beta0_VH_db or Sigma0_VH_db)
            vh_band_idx = None
            for i in range(1, dataset.RasterCount + 1):
                band = dataset.GetRasterBand(i)
                desc = band.GetDescription()
                if 'VH' in desc and 'db' in desc.lower():
                    vh_band_idx = i
                    logger.info(f"Found VH band: {desc}")
                    break

            if vh_band_idx is None:
                logger.error("VH band not found")
                return False

            # Extract band
            driver = gdal.GetDriverByName('GTiff')
            vh_band = dataset.GetRasterBand(vh_band_idx)

            out_ds = driver.Create(
                output_vh,
                dataset.RasterXSize,
                dataset.RasterYSize,
                1,
                vh_band.DataType,
                options=['COMPRESS=LZW', 'TILED=YES']
            )

            out_ds.SetGeoTransform(dataset.GetGeoTransform())
            out_ds.SetProjection(dataset.GetProjection())
            out_ds.GetRasterBand(1).WriteArray(vh_band.ReadAsArray())
            out_ds.GetRasterBand(1).SetNoDataValue(vh_band.GetNoDataValue())

            out_ds = None
            dataset = None

            logger.info(f"✓ VH band extracted: {output_vh}")
            return True

        except Exception as e:
            logger.error(f"Error extracting VH band: {str(e)}")
            return False


def extract_zip_if_needed(zip_file: str, extract_dir: str) -> str:
    """
    Extract .zip file if input is zipped

    Args:
        zip_file: Input .zip file
        extract_dir: Directory to extract to

    Returns:
        Path to .SAFE directory
    """
    zip_path = Path(zip_file)

    if zip_path.suffix == '.zip':
        logger.info(f"Extracting: {zip_path.name}")

        extract_path = Path(extract_dir)
        extract_path.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            zip_ref.extractall(extract_path)

        # Find .SAFE directory
        safe_dirs = list(extract_path.glob('*.SAFE'))
        if safe_dirs:
            logger.info(f"✓ Extracted to: {safe_dirs[0]}")
            return str(safe_dirs[0])
        else:
            logger.error("No .SAFE directory found in zip")
            return zip_file
    else:
        return zip_file


def main():
    """Example usage"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Preprocess Sentinel-1 data with SNAP GPT'
    )
    parser.add_argument('--input', required=True, help='Input .zip or .SAFE file')
    parser.add_argument('--output', required=True, help='Output file path')
    parser.add_argument('--graph', default='sen1_preprocessing-gpt.xml',
                       help='SNAP graph XML file')
    parser.add_argument('--gpt-path', help='Path to SNAP GPT executable')
    parser.add_argument('--cache', default='8G', help='SNAP cache size (e.g., 8G)')
    parser.add_argument('--to-tif', action='store_true',
                       help='Convert output to GeoTIFF')
    parser.add_argument('--extract-vh', help='Extract VH band to separate file')

    args = parser.parse_args()

    # Initialize preprocessor
    preprocessor = SNAPPreprocessor(
        snap_gpt_path=args.gpt_path,
        cache_size=args.cache
    )

    # Process
    success = preprocessor.process_scene(
        input_file=args.input,
        output_file=args.output,
        graph_xml=args.graph
    )

    if not success:
        logger.error("Processing failed")
        sys.exit(1)

    # Convert to GeoTIFF
    if args.to_tif:
        tif_output = Path(args.output).with_suffix('.tif')
        preprocessor.convert_to_geotiff(
            dim_file=f"{args.output}.dim",
            output_tif=str(tif_output)
        )

    # Extract VH band
    if args.extract_vh:
        preprocessor.extract_vh_band(
            processed_file=f"{args.output}.dim",
            output_vh=args.extract_vh
        )

    logger.info("\n✓ Processing complete!")


if __name__ == '__main__':
    main()
