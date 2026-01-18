# Sentinel-1 SAR Preprocessing Pipeline

A comprehensive pipeline for downloading, preprocessing, and mosaicking Sentinel-1 SAR (Synthetic Aperture Radar) data using ESA SNAP and GDAL/OTB tools.

## Features

- **Automated Data Acquisition**: Download Sentinel-1 GRD data from ASF (Alaska Satellite Facility)
- **SNAP GPT Preprocessing**: Calibration, terrain correction, speckle filtering, dB conversion
- **Multi-Resolution Support**: Process at 10m, 20m, 50m, or 100m resolution
- **Seamless Mosaicking**: GDAL and OTB-based mosaicking with histogram matching
- **12-Day Period Compositing**: Create 31-band annual stacks for time series analysis
- **Parallel Processing**: Multi-threaded batch processing for large datasets

## Repository Structure

```
s1-preprocessing-pipeline/
├── scripts/              # All Python and shell scripts
│   ├── s1_preprocess_snap.py           # Main SNAP preprocessing wrapper
│   ├── s1_preprocess_parallel.py       # Parallel preprocessing
│   ├── s1_period_pipeline.py           # Full annual pipeline (RECOMMENDED)
│   ├── s1_process_period_dir.py        # Process single period directory
│   ├── s1_download.py                  # ASF/SciHub download
│   ├── batch_mosaic_periods.py         # Batch mosaicking with OTB
│   ├── stack_period_mosaics.py         # Stack mosaics into annual stack
│   ├── period_utils.py                 # Period calculation utilities
│   └── ...                             # Additional utility scripts
├── graphs/               # SNAP GPT XML processing graphs
│   ├── sen1_preprocessing-gpt.xml      # 10m resolution
│   ├── sen1_preprocessing-gpt-20m.xml  # 20m resolution (recommended)
│   ├── sen1_preprocessing-gpt-50m.xml  # 50m resolution
│   └── sen1_preprocessing-gpt-100m.xml # 100m resolution
├── configs/              # Pipeline configuration files
│   ├── pipeline_config_period.yaml     # Period-based pipeline config
│   ├── pipeline_config_java.yaml       # Java Island example config
│   ├── env.yml                         # Conda environment
│   └── ...                             # Additional configs
└── docs/                 # Documentation
    ├── PERIOD_PIPELINE_GUIDE.md        # Comprehensive pipeline guide
    ├── AUTOMATED_PIPELINE_GUIDE.md     # Automation guide
    ├── 12DAY_PERIOD_SYSTEM.md          # Period system explanation
    └── ...                             # Additional guides
```

## Quick Start

### 1. Install Dependencies

```bash
# Create conda environment
conda env create -f configs/env.yml
conda activate myenv

# Install additional packages
pip install asf-search shapely pyyaml rasterio

# Install ESA SNAP from https://step.esa.int/main/download/snap-download/
# Ensure 'gpt' command is in PATH
```

### 2. Configure Pipeline

```bash
# Copy and edit configuration
cp configs/pipeline_config_period.yaml my_config.yaml
nano my_config.yaml  # Edit AOI (area of interest) and dates
```

### 3. Run Full Annual Pipeline (Recommended)

```bash
# Process entire year with 31 12-day periods
python scripts/s1_period_pipeline.py --config my_config.yaml --year 2024 --run-all
```

This automatically:
- Downloads Sentinel-1 data for all 31 periods
- Preprocesses with SNAP (calibration, terrain correction, speckle filter)
- Mosaics multiple scenes within each period
- Stacks all periods into final 31-band GeoTIFF

### 4. Alternative: Process Single Period

```bash
# Navigate to period directory with downloaded .zip files
cd workspace/year_2024/p15

# Run preprocessing pipeline
python /path/to/scripts/s1_process_period_dir.py --run-all
```

## Processing Chain

The SNAP GPT preprocessing chain includes:

1. **Read** - Load Sentinel-1 GRD product
2. **Apply Orbit File** - Precise orbit correction
3. **Thermal Noise Removal** - Remove thermal noise artifacts
4. **Calibration** - Convert to Beta0 backscatter
5. **Terrain Flattening** - Radiometric terrain correction
6. **Terrain Correction** - Range Doppler geometric correction
7. **Speckle Filtering** - Gamma MAP 5x5 filter
8. **Linear to dB** - Convert to decibel scale
9. **Export** - Output GeoTIFF or BEAM-DIMAP

## 12-Day Period System

The year is divided into 31 periods of 12 days each:

| Period | Date Range | Band Index |
|--------|------------|------------|
| 1 | Jan 1-12 | 0 |
| 2 | Jan 13-24 | 1 |
| ... | ... | ... |
| 31 | Dec 27-31 | 30 |

Generate period calendar:
```bash
python scripts/s1_composite_12day.py --year 2025 --print-calendar \
    --input-dir . --output dummy.tif
```

## Key Scripts

| Script | Purpose |
|--------|---------|
| `s1_period_pipeline.py` | **Full annual pipeline (RECOMMENDED)** |
| `s1_process_period_dir.py` | Process single period directory |
| `s1_preprocess_snap.py` | SNAP GPT preprocessing wrapper |
| `s1_preprocess_parallel.py` | Parallel batch preprocessing |
| `s1_download.py` | Download from ASF or ESA SciHub |
| `batch_mosaic_periods.py` | Batch mosaicking with OTB |
| `stack_period_mosaics.py` | Stack mosaics into multi-band stack |
| `s1_composite_12day.py` | Create 12-day composites |

## Configuration Options

Example `pipeline_config_period.yaml`:

```yaml
aoi:
  # Define area of interest (WKT or bounding box)
  wkt: "POLYGON((105.0 -8.5, 115.0 -8.5, 115.0 -5.5, 105.0 -5.5, 105.0 -8.5))"

processing:
  resolution: 20  # Output resolution in meters
  polarization: VH  # VH, VV, or both

snap:
  gpt_path: /path/to/snap/bin/gpt  # Path to SNAP GPT
  graph: graphs/sen1_preprocessing-gpt-20m.xml

output:
  workspace: ./workspace
  format: GeoTIFF
```

## Requirements

- **Python 3.9+**
- **ESA SNAP** (for preprocessing)
- **GDAL** (for mosaicking and format conversion)
- **OTB** (optional, for advanced mosaicking with histogram matching)
- **asf-search** (for data download)

## Documentation

- [Period Pipeline Guide](docs/PERIOD_PIPELINE_GUIDE.md) - Comprehensive pipeline documentation
- [Automated Pipeline Guide](docs/AUTOMATED_PIPELINE_GUIDE.md) - Full automation guide
- [12-Day Period System](docs/12DAY_PERIOD_SYSTEM.md) - Period calendar and utilities
- [Manual Workflow](docs/MANUAL_WORKFLOW_QUICKSTART.md) - Manual download workflow
- [Batch Processing](docs/BATCH_PROCESSING_GUIDE.md) - Multi-period batch processing
- [Quick Reference](docs/QUICK_REFERENCE.md) - Command cheat sheet

## License

MIT License

## Acknowledgments

- ESA Sentinel-1 Mission
- ESA SNAP Toolbox
- Alaska Satellite Facility (ASF)
- Orfeo ToolBox (OTB)
