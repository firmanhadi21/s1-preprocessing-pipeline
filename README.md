# Sentinel-1 SAR Preprocessing Pipeline

Simple, proven workflow for preprocessing Sentinel-1 GRD data using ESA SNAP.

## Workflow

1. **Search** Sentinel-1 scenes on [ASF Vertex](https://search.asf.alaska.edu/)
2. **Download** the .zip files to a `downloads/` folder
3. **Run** the preprocessing script

## Quick Start

```bash
# Create period folder structure
mkdir -p p15/downloads

# Download Sentinel-1 GRD .zip files from ASF into p15/downloads/

# Run preprocessing (from inside the period folder)
cd p15
python /path/to/s1_process_period_dir.py --run-all
```

## Output Structure

```
p15/
├── downloads/      # Input: Place .zip files here
├── preprocessed/   # SNAP output (.dim files)
├── geotiff/        # Converted GeoTIFF files
└── mosaic/         # Final mosaic + preview image
    ├── p15_mosaic.tif
    └── p15_preview.png
```

## Resolution Options

```bash
# 20m resolution (default, recommended)
python s1_process_period_dir.py --run-all

# 10m resolution (highest detail, slower)
python s1_process_period_dir.py --run-all --resolution 10

# 50m resolution (faster processing)
python s1_process_period_dir.py --run-all --resolution 50

# 100m resolution (quickest, for previews)
python s1_process_period_dir.py --run-all --resolution 100
```

## Individual Steps

```bash
# Step 1: Preprocess with SNAP
python s1_process_period_dir.py --preprocess

# Step 2: Convert .dim to GeoTIFF
python s1_process_period_dir.py --convert

# Step 3: Mosaic all scenes
python s1_process_period_dir.py --mosaic

# Step 4: Create preview image
python s1_process_period_dir.py --preview
```

## Processing Chain

The SNAP preprocessing applies:
1. Apply Orbit File (precise orbit correction)
2. Thermal Noise Removal
3. Calibration (Beta0)
4. Terrain Flattening
5. Terrain Correction (Range Doppler)
6. Speckle Filtering (Gamma MAP 5x5)
7. Linear to dB conversion

## Requirements

- **Python 3.8+** with `rasterio`, `numpy`, `matplotlib`
- **ESA SNAP** with `gpt` command in PATH
- **GDAL** with `gdal_merge.py`

### Install Python dependencies

```bash
pip install rasterio numpy matplotlib
```

### Install ESA SNAP

Download from: https://step.esa.int/main/download/snap-download/

Add SNAP bin directory to PATH:
```bash
export PATH=$PATH:/path/to/snap/bin
```

## Files

```
s1-preprocessing-pipeline/
├── s1_process_period_dir.py     # Main processing script
├── graphs/
│   ├── sen1_preprocessing-gpt.xml       # 10m resolution
│   ├── sen1_preprocessing-gpt-20m.xml   # 20m resolution
│   ├── sen1_preprocessing-gpt-50m.xml   # 50m resolution
│   └── sen1_preprocessing-gpt-100m.xml  # 100m resolution
└── README.md
```

## License

MIT License
