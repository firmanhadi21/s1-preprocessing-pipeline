# Sentinel-1 SAR Preprocessing Pipeline

Simple, proven workflow for preprocessing Sentinel-1 GRD data using ESA SNAP.

## Why SNAP Instead of Google Earth Engine?

Many users prefer Google Earth Engine (GEE) for Sentinel-1 processing because it's fast and convenient. However, there are important reasons to use ESA SNAP instead:

### 1. Complete Processing Chain

GEE's Sentinel-1 preprocessing is **incomplete**. The GEE backscatter data lacks critical steps that affect data quality:

| Processing Step | SNAP | GEE |
|-----------------|------|-----|
| Apply Orbit File | Yes | Yes |
| Thermal Noise Removal | Yes | Partial |
| Calibration | Yes | Yes |
| **Terrain Flattening** | Yes | **No** |
| Terrain Correction | Yes | Yes |
| Speckle Filtering | Yes | No (manual) |

**Terrain Flattening** is essential for accurate backscatter analysis in mountainous or hilly areas. Without it, the backscatter values are affected by local incidence angle variations caused by terrain slope.

### 2. Commercial Use & Licensing

GEE has licensing restrictions:
- GEE is **free only for research, education, and non-profit use**
- **Commercial applications require a paid Google Earth Engine license**
- Using GEE-processed data in commercial products may violate terms of service

With SNAP:
- ESA SNAP is **free and open-source** (GPL-3.0)
- Sentinel-1 data is **free and open** under Copernicus license
- **No restrictions** on commercial use of your processed outputs

### 3. Independence & Reproducibility

- **No vendor lock-in**: Your workflow doesn't depend on Google's cloud service
- **Offline processing**: Works without internet after downloading data
- **Full control**: Complete transparency over every processing step
- **Long-term reproducibility**: Not affected by GEE API changes or service availability

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
