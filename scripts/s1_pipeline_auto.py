#!/usr/bin/env python3
"""
Automated End-to-End Pipeline for Rice Growth Stage Mapping

Complete workflow:
1. Download Sentinel-1 data for specified area and time period
2. Preprocess with SNAP GPT (apply orbit, calibrate, terrain correct, speckle filter)
3. Stack temporal data into multi-band GeoTIFF
4. Train model (if requested)
5. Generate predictions

Usage:
    # Complete automated workflow
    python s1_pipeline_auto.py --config pipeline_config.yaml --run-all

    # Individual steps
    python s1_pipeline_auto.py --config pipeline_config.yaml --download-only
    python s1_pipeline_auto.py --config pipeline_config.yaml --preprocess-only
    python s1_pipeline_auto.py --config pipeline_config.yaml --predict-only
"""

import os
import sys
from pathlib import Path
import yaml
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import argparse

# Import our modules
from s1_download import Sentinel1Downloader, create_aoi_from_bbox, create_aoi_geojson
from s1_preprocess_snap import SNAPPreprocessor, extract_zip_if_needed

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RiceGrowthPipeline:
    """
    Automated pipeline for rice growth stage mapping
    """

    def __init__(self, config_file: str):
        """
        Initialize pipeline from config file

        Args:
            config_file: Path to YAML configuration file
        """
        self.config = self._load_config(config_file)
        self.work_dir = Path(self.config['directories']['work_dir'])
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # Setup directories
        self.dirs = {
            'downloads': self.work_dir / 'downloads',
            'extracted': self.work_dir / 'extracted',
            'preprocessed': self.work_dir / 'preprocessed',
            'stacked': self.work_dir / 'stacked',
            'models': self.work_dir / 'models',
            'predictions': self.work_dir / 'predictions'
        }

        for dir_path in self.dirs.values():
            dir_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Pipeline workspace: {self.work_dir}")


    def _load_config(self, config_file: str) -> Dict:
        """Load configuration from YAML file"""
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)

        logger.info(f"Loaded configuration from: {config_file}")
        return config


    def step1_download_data(self) -> List[str]:
        """
        Step 1: Download Sentinel-1 data

        Returns:
            List of downloaded file paths
        """
        logger.info("\n" + "="*60)
        logger.info("STEP 1: DOWNLOAD SENTINEL-1 DATA")
        logger.info("="*60)

        cfg = self.config['data_acquisition']

        # Create AOI
        bbox = cfg['aoi_bbox']
        aoi_wkt = create_aoi_from_bbox(*bbox)
        aoi_geojson = create_aoi_geojson(*bbox)

        # Initialize downloader
        downloader = Sentinel1Downloader(
            download_dir=str(self.dirs['downloads']),
            username=cfg.get('scihub_username'),
            password=cfg.get('scihub_password')
        )

        # Download based on source
        source = cfg.get('download_source', 'asf')

        if source == 'scihub':
            files = downloader.download_scihub(
                aoi_wkt=aoi_wkt,
                start_date=cfg['start_date'],
                end_date=cfg['end_date'],
                orbit_direction=cfg.get('orbit_direction', 'ASCENDING')
            )
        else:  # ASF
            files = downloader.download_asf(
                aoi_geojson=aoi_geojson,
                start_date=cfg['start_date'],
                end_date=cfg['end_date']
            )

        logger.info(f"\n✓ Downloaded {len(files)} files")
        return files


    def step2_preprocess(self, input_files: Optional[List[str]] = None) -> List[str]:
        """
        Step 2: Preprocess with SNAP GPT

        Args:
            input_files: List of input files (if None, searches download directory)

        Returns:
            List of preprocessed GeoTIFF files
        """
        logger.info("\n" + "="*60)
        logger.info("STEP 2: PREPROCESS WITH SNAP GPT")
        logger.info("="*60)

        # Find input files if not provided
        if input_files is None:
            input_files = list(self.dirs['downloads'].glob('*.zip'))
            logger.info(f"Found {len(input_files)} files to preprocess")

        if len(input_files) == 0:
            logger.warning("No input files found")
            return []

        # Initialize preprocessor
        cfg = self.config['preprocessing']
        preprocessor = SNAPPreprocessor(
            snap_gpt_path=cfg.get('snap_gpt_path'),
            cache_size=cfg.get('cache_size', '8G')
        )

        # Get graph XML path
        graph_xml = Path(cfg.get('graph_xml', 'sen1_preprocessing-gpt.xml'))

        # Process all files
        processed_files = preprocessor.batch_process(
            input_files=[str(f) for f in input_files],
            output_dir=str(self.dirs['preprocessed']),
            graph_xml=str(graph_xml),
            convert_to_tif=True
        )

        logger.info(f"\n✓ Preprocessed {len(processed_files)} files")
        return processed_files


    def step3_stack_temporal(self, preprocessed_files: Optional[List[str]] = None) -> str:
        """
        Step 3: Create 12-day period composites and stack into 31-band GeoTIFF

        Args:
            preprocessed_files: List of preprocessed files (optional)

        Returns:
            Path to stacked 31-band GeoTIFF (one band per 12-day period)
        """
        logger.info("\n" + "="*60)
        logger.info("STEP 3: CREATE 12-DAY PERIOD COMPOSITES")
        logger.info("="*60)

        # Import the 12-day compositor
        try:
            from s1_composite_12day import Sentinel1Compositor
        except ImportError:
            logger.error("s1_composite_12day.py not found")
            return None

        # Determine the year from configuration
        cfg = self.config['data_acquisition']
        start_date_str = cfg['start_date']
        year = int(start_date_str.split('-')[0])

        logger.info(f"Creating 12-day composites for year {year}")
        logger.info("System: 31 periods per year (12 days each)")
        logger.info("Output: 31-band GeoTIFF (Period 1 = Band 1, etc.)")

        # Initialize compositor
        compositor = Sentinel1Compositor(year=year, output_dir=str(self.dirs['stacked']))

        # Output file
        output_file = self.dirs['stacked'] / f's1_vh_stack_{year}_31bands.tif'

        # Create annual stack using 12-day compositor
        try:
            stacked_file = compositor.create_annual_stack(
                input_dir=str(self.dirs['preprocessed']),
                output_file=str(output_file),
                composite_method='median',  # Can be 'median', 'mean', 'first', 'last'
                fill_missing=True  # Interpolate missing periods
            )

            logger.info(f"\n✓ 12-day period stack created: {stacked_file}")
            logger.info(f"  Bands: 31 (12-day periods)")
            logger.info(f"  Valid prediction periods: 7-31 (need 7 bands for backward window)")

            return stacked_file

        except Exception as e:
            logger.error(f"Failed to create 12-day composite stack: {e}")
            import traceback
            traceback.print_exc()
            return None


    def step4_train_model(self, stacked_file: str, training_points_csv: str):
        """
        Step 4: Train growth stage mapping model

        Args:
            stacked_file: Path to stacked multi-band GeoTIFF
            training_points_csv: Path to training points CSV
        """
        logger.info("\n" + "="*60)
        logger.info("STEP 4: TRAIN MODEL")
        logger.info("="*60)

        # Update config.py with new paths
        logger.info("Updating configuration...")

        # Import training script
        try:
            from balanced_train_lstm import main as train_main
        except ImportError:
            logger.error("Training scripts not found")
            return

        # TODO: Update config.py programmatically
        # For now, user needs to update paths manually
        logger.info("Please update config.py with:")
        logger.info(f"  TRAINING_GEOTIFF: {stacked_file}")
        logger.info(f"  TRAINING_CSV: {training_points_csv}")
        logger.info("\nThen run:")
        logger.info("  python balanced_train_lstm.py --augment --use-class-weights")


    def step5_predict(self, stacked_file: str, periods: List[int]):
        """
        Step 5: Generate predictions

        Args:
            stacked_file: Path to stacked multi-band GeoTIFF
            periods: List of period numbers to predict
        """
        logger.info("\n" + "="*60)
        logger.info("STEP 5: GENERATE PREDICTIONS")
        logger.info("="*60)

        logger.info("Please update config.py with:")
        logger.info(f"  PREDICTION_GEOTIFF: {stacked_file}")
        logger.info("\nThen run:")
        for period in periods:
            logger.info(f"  python predict_optimized.py --period {period} --skip-test")


    def run_full_pipeline(self, skip_download: bool = False,
                         skip_preprocess: bool = False):
        """
        Run complete pipeline

        Args:
            skip_download: Skip download step (use existing files)
            skip_preprocess: Skip preprocessing step (use existing files)
        """
        logger.info("\n" + "="*70)
        logger.info("AUTOMATED RICE GROWTH STAGE MAPPING PIPELINE")
        logger.info("="*70)
        logger.info(f"Start time: {datetime.now()}")
        logger.info(f"Workspace: {self.work_dir}")

        start_time = datetime.now()

        # Step 1: Download
        if not skip_download:
            downloaded_files = self.step1_download_data()
        else:
            logger.info("\nSkipping download (using existing files)")
            downloaded_files = list(self.dirs['downloads'].glob('*.zip'))

        # Step 2: Preprocess
        if not skip_preprocess:
            preprocessed_files = self.step2_preprocess(downloaded_files)
        else:
            logger.info("\nSkipping preprocessing (using existing files)")
            preprocessed_files = list(self.dirs['preprocessed'].glob('*.tif'))

        # Step 3: Stack
        stacked_file = self.step3_stack_temporal(preprocessed_files)

        # Step 4 & 5: Instructions for training and prediction
        logger.info("\n" + "="*70)
        logger.info("PIPELINE PREPARATION COMPLETE")
        logger.info("="*70)

        elapsed = datetime.now() - start_time
        logger.info(f"Total time: {elapsed}")

        logger.info("\nNext steps:")
        logger.info("1. Prepare training points CSV with columns:")
        logger.info("   - tanggal (date), lintang (latitude), bujur (longitude), fase (growth stage)")
        logger.info("2. Update config.py with paths:")
        logger.info(f"   - TRAINING_GEOTIFF: {stacked_file}")
        logger.info(f"   - PREDICTION_GEOTIFF: {stacked_file}")
        logger.info(f"   - TRAINING_CSV: <your_training_points.csv>")
        logger.info("3. Train model:")
        logger.info("   python balanced_train_lstm.py --augment --use-class-weights")
        logger.info("4. Generate predictions:")
        logger.info("   python predict_optimized.py --period <period_number> --skip-test")


def create_example_config(output_file: str = 'pipeline_config.yaml'):
    """Create example configuration file"""
    example_config = {
        'directories': {
            'work_dir': './pipeline_workspace'
        },
        'data_acquisition': {
            'download_source': 'asf',  # or 'scihub'
            'aoi_bbox': [106.0, -8.0, 115.0, -5.0],  # [min_lon, min_lat, max_lon, max_lat]
            'start_date': '2024-01-01',
            'end_date': '2024-06-30',
            'orbit_direction': 'ASCENDING',
            'scihub_username': null,  # Set if using scihub
            'scihub_password': null   # Set if using scihub
        },
        'preprocessing': {
            'snap_gpt_path': null,  # Auto-detect if null
            'graph_xml': 'sen1_preprocessing-gpt.xml',
            'cache_size': '8G'
        },
        'training': {
            'model_type': 'cnn_lstm',  # 'mlp', 'cnn', or 'cnn_lstm'
            'use_augmentation': True,
            'use_class_weights': True,
            'use_smote': True
        },
        'prediction': {
            'periods': list(range(8, 24)),  # Periods to predict
            'use_optimized': True
        }
    }

    with open(output_file, 'w') as f:
        yaml.dump(example_config, f, default_flow_style=False, sort_keys=False)

    logger.info(f"Example configuration created: {output_file}")
    logger.info("Please edit this file with your specific parameters")


def main():
    parser = argparse.ArgumentParser(
        description='Automated Rice Growth Stage Mapping Pipeline'
    )
    parser.add_argument('--config', default='pipeline_config.yaml',
                       help='Pipeline configuration file')
    parser.add_argument('--create-config', action='store_true',
                       help='Create example configuration file')
    parser.add_argument('--run-all', action='store_true',
                       help='Run full pipeline')
    parser.add_argument('--download-only', action='store_true',
                       help='Only download data')
    parser.add_argument('--preprocess-only', action='store_true',
                       help='Only preprocess data')
    parser.add_argument('--stack-only', action='store_true',
                       help='Only stack preprocessed data')
    parser.add_argument('--skip-download', action='store_true',
                       help='Skip download step')
    parser.add_argument('--skip-preprocess', action='store_true',
                       help='Skip preprocessing step')

    args = parser.parse_args()

    # Create example config
    if args.create_config:
        create_example_config(args.config)
        return

    # Check config exists
    if not Path(args.config).exists():
        logger.error(f"Configuration file not found: {args.config}")
        logger.info("Create one with: python s1_pipeline_auto.py --create-config")
        sys.exit(1)

    # Initialize pipeline
    pipeline = RiceGrowthPipeline(args.config)

    # Run requested steps
    if args.download_only:
        pipeline.step1_download_data()
    elif args.preprocess_only:
        pipeline.step2_preprocess()
    elif args.stack_only:
        pipeline.step3_stack_temporal()
    elif args.run_all:
        pipeline.run_full_pipeline(
            skip_download=args.skip_download,
            skip_preprocess=args.skip_preprocess
        )
    else:
        logger.error("Please specify an action: --run-all, --download-only, etc.")
        parser.print_help()


if __name__ == '__main__':
    main()
