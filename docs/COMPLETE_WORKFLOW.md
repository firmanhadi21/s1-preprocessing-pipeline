# Complete Sentinel-1 Rice Growth Stage Mapping Workflow

This document provides a complete end-to-end workflow for creating rice growth stage maps from Sentinel-1 SAR data using the 12-day period system.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Workflow Summary](#workflow-summary)
4. [Step 1: Data Search and Download (ASF)](#step-1-data-search-and-download-asf)
5. [Step 2: SNAP Preprocessing](#step-2-snap-preprocessing)
6. [Step 3: OTB Mosaicking](#step-3-otb-mosaicking)
7. [Step 4: Stacking All Periods](#step-4-stacking-all-periods)
8. [Step 5: Model Training](#step-5-model-training)
9. [Step 6: Prediction](#step-6-prediction)
10. [Directory Structure](#directory-structure)
11. [Troubleshooting](#troubleshooting)

---

## Overview

This workflow processes Sentinel-1 GRD (Ground Range Detected) data to create time series analysis for rice growth stage classification. The system:

- Divides the year into **31 periods** of 12 days each
- Downloads Sentinel-1 data from **Alaska Satellite Facility (ASF)**
- Preprocesses with **ESA SNAP** (calibration, terrain correction, speckle filtering)
- Mosaics overlapping tracks using **Orfeo Toolbox (OTB)** for seamless results
- Stacks all periods into a **31-band annual GeoTIFF**
- Trains a **deep learning model** for growth stage classification
- Generates **growth stage maps** for any period

**Study Area**: Java Island, Indonesia
**Temporal Resolution**: 12-day periods
**Spatial Resolution**: 10m or 50m
**Polarization**: VH (cross-polarized)

---

## Prerequisites

### Software Requirements

1. **Python Environment** (conda recommended)
   ```bash
   conda env create -f env.yml
   conda activate myenv  # or geo_ml_env
   ```

2. **ESA SNAP** (for preprocessing)
   - Download: https://step.esa.int/main/download/snap-download/
   - Install and configure `gpt` command
   - See `AUTOMATED_PIPELINE_GUIDE.md` for SNAP setup

3. **Orfeo Toolbox** (for mosaicking)
   - Installation directory: `~/work/OTB/`
   - Profile file: `~/work/OTB/otbenv.profile`
   - **Note**: Keep OTB config in `.bashrc` commented out to avoid GDAL conflicts

4. **ASF Python Tools** (for data download)
   ```bash
   pip install asf-search
   ```

### Required Python Packages

- GDAL (from conda, not OTB)
- TensorFlow/Keras
- NumPy, Pandas, Rasterio, GeoPandas
- scikit-learn, imbalanced-learn

---

## Workflow Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                    SENTINEL-1 PROCESSING WORKFLOW                │
└─────────────────────────────────────────────────────────────────┘

STEP 1: ASF Data Download
  ├─ Search for Sentinel-1 GRD data covering Java Island
  ├─ Filter by period date ranges (12-day windows)
  └─ Download to: downloads/downloads_p{period}/

STEP 2: SNAP Preprocessing (per period)
  ├─ Apply orbit file
  ├─ Radiometric calibration (sigma0)
  ├─ Speckle filtering (Lee Sigma 7x7)
  ├─ Terrain correction (SRTM 1-sec, 10m resolution)
  ├─ Convert to dB
  └─ Output to: preprocessed_10m/p{period}/

STEP 3: OTB Mosaicking (per period)
  ├─ Mosaic overlapping tracks with OTB
  ├─ Large feathering for seamless blending
  ├─ Band-wise harmonization (RMSE)
  └─ Output to: workspace/mosaics_10m/period_{XX}_mosaic.tif

STEP 4: Stack All Periods
  ├─ Combine 31 period mosaics
  └─ Output: workspace/java_vh_stack_2024_31bands.tif

STEP 5: Model Training
  ├─ Load training points (CSV with coordinates + growth stage)
  ├─ Extract 29 temporal features per point
  ├─ Train with 5-fold cross-validation
  └─ Save model artifacts to: model_files/

STEP 6: Generate Predictions
  ├─ Load trained model
  ├─ Predict growth stage for each pixel
  ├─ Apply spatial smoothing
  └─ Output maps to: predictions/period_XX/
```

---

## Step 1: Data Search and Download (ASF)

### 1.1 Search for Data

Use the ASF Search API to find Sentinel-1 GRD scenes covering Java Island for each period.

**Period Date Ranges** (see `12DAY_PERIOD_SYSTEM.md` for complete calendar):
- Period 1: Jan 1-12
- Period 2: Jan 13-24
- Period 3: Jan 25-Feb 5
- ...
- Period 31: Dec 27-31

**Example Python Script for ASF Search:**

```python
import asf_search as asf
from datetime import datetime

# Java Island bounding box (WGS84)
aoi = "POLYGON((105.0 -9.0, 116.0 -9.0, 116.0 -5.0, 105.0 -5.0, 105.0 -9.0))"

# Period 1 example: Jan 1-12, 2024
start_date = datetime(2024, 1, 1)
end_date = datetime(2024, 1, 12)

# Search for Sentinel-1 GRD
results = asf.search(
    platform=asf.PLATFORM.SENTINEL1,
    intersectsWith=aoi,
    start=start_date,
    end=end_date,
    processingLevel='GRD_HD',
    beamMode='IW',
    polarization='VV+VH'  # Dual-pol
)

print(f"Found {len(results)} scenes for Period 1")
```

### 1.2 Download Data

**Using ASF Python Tools:**

```python
import asf_search as asf

# Authenticate (required for download)
session = asf.ASFSession().auth_with_creds('YOUR_USERNAME', 'YOUR_PASSWORD')

# Download all results
results.download(
    path='downloads/downloads_p1',
    session=session,
    processes=4  # Parallel downloads
)
```

**Directory Structure After Download:**

```
downloads/
├── downloads_p1/
│   ├── S1A_IW_GRDH_1SDV_20240101T*.zip
│   ├── S1A_IW_GRDH_1SDV_20240105T*.zip
│   └── ...
├── downloads_p2/
│   └── ...
└── downloads_p31/
    └── ...
```

### 1.3 Repeat for All Periods

Create a loop to download all 31 periods:

```python
from period_utils import get_period_dates

for period in range(1, 32):
    start, end = get_period_dates(period, year=2024)

    # Search
    results = asf.search(
        platform=asf.PLATFORM.SENTINEL1,
        intersectsWith=aoi,
        start=start,
        end=end,
        processingLevel='GRD_HD',
        beamMode='IW',
        polarization='VV+VH'
    )

    # Download
    results.download(
        path=f'downloads/downloads_p{period}',
        session=session
    )

    print(f"✓ Period {period}: {len(results)} scenes downloaded")
```

---

## Step 2: SNAP Preprocessing

Preprocess each period's downloaded scenes using ESA SNAP GPT (Graph Processing Tool).

### 2.1 SNAP Preprocessing Graph

Use the provided XML graph: `sen1_preprocessing-gpt.xml`

This graph performs:
1. **Apply-Orbit-File**: Precise orbit correction
2. **Calibration**: Radiometric calibration to sigma0
3. **Speckle-Filter**: Lee Sigma filter (7x7 window)
4. **Terrain-Correction**: SRTM 1-sec DEM, 10m pixel spacing
5. **LinearToFromdB**: Convert to dB scale
6. **Subset**: Extract VH polarization only
7. **Write**: Output GeoTIFF

### 2.2 Preprocess Single Period

**Using the automated preprocessing script:**

```bash
python s1_preprocess_snap.py \
    --input-dir downloads/downloads_p1 \
    --output-dir preprocessed_10m/p1 \
    --resolution 10 \
    --graph sen1_preprocessing-gpt.xml
```

**What happens:**
- All `.zip` files in `downloads/downloads_p1/` are processed
- SNAP applies the complete preprocessing chain
- VH band GeoTIFFs are saved to `preprocessed_10m/p1/`

**Expected Output:**

```
preprocessed_10m/p1/
├── S1A_IW_GRDH_20240101_VH_10m.tif
├── S1A_IW_GRDH_20240105_VH_10m.tif
└── ...
```

### 2.3 Batch Preprocessing for All Periods

**Option 1: Loop Script**

```bash
for period in {1..31}; do
    echo "Processing Period $period..."
    python s1_preprocess_snap.py \
        --input-dir downloads/downloads_p${period} \
        --output-dir preprocessed_10m/p${period} \
        --resolution 10 \
        --graph sen1_preprocessing-gpt.xml
done
```

**Option 2: Using the Automated Pipeline**

```bash
# Configure pipeline_config.yaml with your AOI and dates
python s1_pipeline_auto.py --config pipeline_config.yaml --preprocess-only
```

### 2.4 Expected Time

- **Per scene**: 5-15 minutes (depends on scene size and CPU cores)
- **Per period**: 1-4 hours (assuming 10-20 scenes per period)
- **All 31 periods**: 1-3 days (can run in parallel if resources allow)

---

## Step 3: OTB Mosaicking

Mosaic overlapping Sentinel-1 tracks for each period using Orfeo Toolbox for seamless results.

### 3.1 Why OTB?

OTB provides superior mosaicking for SAR data compared to GDAL because:
- **Large feathering**: Seamless blending in overlap areas (eliminates visible seams)
- **Radiometric harmonization**: Normalizes brightness differences between tracks
- **Better nodata handling**: Properly masks NULL values
- **RMSE-based cost function**: Optimizes radiometric consistency

### 3.2 Mosaic Single Period

```bash
python s1_mosaic_single_period.py \
    --input-dir workspace/preprocessed_20m/p6 \
    --output workspace/mosaics_20m/period_06_mosaic.tif \
    --period 6 \
    --year 2024 \
    --resolution 20
```

**Parameters:**
- `--input-dir`: Directory with preprocessed VH GeoTIFFs for this period
- `--output`: Output mosaic file
- `--period`: Period number (1-31)
- `--year`: Year (default: 2024)
- `--resolution`: Pixel size in meters (default: 50)

**OTB Settings Used:**
- Feathering: `large` (maximum blending for seamless results)
- Harmonization: `band` method with `rmse` cost function
- Nodata: `-32768`

### 3.3 Batch Mosaic All Periods

**Create a bash script** `mosaic_all_periods.sh`:

```bash
#!/bin/bash

RESOLUTION=10
YEAR=2024

echo "Starting OTB mosaicking for all 31 periods..."

for period in {1..31}; do
    echo ""
    echo "========================================="
    echo "Mosaicking Period $period"
    echo "========================================="

    python s1_mosaic_single_period.py \
        --input-dir preprocessed_${RESOLUTION}m/p${period} \
        --output workspace/mosaics_${RESOLUTION}m/period_$(printf "%02d" $period)_mosaic.tif \
        --period $period \
        --year $YEAR \
        --resolution $RESOLUTION

    if [ $? -eq 0 ]; then
        echo "✓ Period $period mosaic complete"
    else
        echo "✗ Period $period mosaic failed"
        exit 1
    fi
done

echo ""
echo "========================================="
echo "✓ All 31 period mosaics complete!"
echo "========================================="
```

**Run:**

```bash
chmod +x mosaic_all_periods.sh
./mosaic_all_periods.sh
```

### 3.4 Alternative: Full Pipeline Mosaicking

For more advanced users processing multiple tracks:

```bash
python s1_mosaic_java_12day.py \
    --input-dir preprocessed_10m \
    --output-dir workspace/mosaics_10m \
    --year 2024 \
    --resolution 10 \
    --composite-method median
```

This handles:
- Grouping scenes by period AND relative orbit (track)
- Within-track compositing (if multiple scenes per track)
- Cross-track mosaicking with OTB

### 3.5 Expected Output

```
workspace/mosaics_10m/
├── period_01_mosaic.tif
├── period_02_mosaic.tif
├── ...
└── period_31_mosaic.tif
```

Each mosaic:
- Covers Java Island extent
- 10m spatial resolution
- VH backscatter in dB
- Nodata value: -32768
- Seamless (no visible track boundaries)

### 3.6 Verify Mosaics

```bash
# Check mosaic info
gdalinfo workspace/mosaics_10m/period_01_mosaic.tif

# Quick visualization
gdal_translate -of PNG -scale \
    workspace/mosaics_10m/period_01_mosaic.tif \
    period_01_preview.png
```

---

## Step 4: Stacking All Periods

Combine all 31 period mosaics into a single multi-band GeoTIFF for model training and prediction.

### 4.1 Stack Periods

```bash
python stack_period_mosaics.py \
    --mosaic-dir workspace/mosaics_10m \
    --output workspace/java_vh_stack_2024_31bands.tif
```

**What happens:**
1. Finds all `period_XX_mosaic.tif` files in the mosaic directory
2. Creates a VRT (Virtual Raster) with all periods as separate bands
3. Converts VRT to a compressed GeoTIFF

**Output:**
- File: `workspace/java_vh_stack_2024_31bands.tif`
- Bands: 31 (one per period)
- Band 1 = Period 1, Band 2 = Period 2, ..., Band 31 = Period 31

### 4.2 Verify Stack

```bash
gdalinfo workspace/java_vh_stack_2024_31bands.tif

# Check band count
gdalinfo workspace/java_vh_stack_2024_31bands.tif | grep "Band "

# Sample a few pixels to ensure data is valid
gdallocationinfo -valonly workspace/java_vh_stack_2024_31bands.tif 1000 1000
```

### 4.3 Update Configuration

Edit `config.py` to point to your new stack:

```python
# File paths
VH_STACK_2024 = 'workspace/java_vh_stack_2024_31bands.tif'
```

---

## Step 5: Model Training

Train the rice growth stage classification model using your training data.

### 5.1 Prepare Training Data

**Required CSV format** (`training_data.csv`):

| tanggal    | lintang   | bujur     | fase |
|------------|-----------|-----------|------|
| 2024-01-15 | -7.55321  | 108.23456 | 2    |
| 2024-02-20 | -7.60123  | 108.45678 | 4    |
| ...        | ...       | ...       | ...  |

**Columns:**
- `tanggal`: Date of observation (YYYY-MM-DD)
- `lintang`: Latitude (decimal degrees)
- `bujur`: Longitude (decimal degrees)
- `fase`: Growth stage (1-6)

**Growth Stages:**
1. Flooding / Land Preparation
2. Early Vegetative (Seedling)
3. Late Vegetative (Tillering)
4. Early Generative (Flowering)
5. Late Generative (Grain Filling)
6. Post-Harvest / Bare Soil

### 5.2 Update Configuration

Edit `config.py`:

```python
# Training data
TRAINING_CSV = 'training_data.csv'
VH_STACK_2024 = 'workspace/java_vh_stack_2024_31bands.tif'
PERIOD_LOOKUP = 'period_lookup_2024.csv'
```

### 5.3 Train Model

```bash
python train.py
```

**What happens:**
1. Loads training points from CSV
2. Maps dates to 12-day periods using period lookup
3. Extracts 29 temporal features per point:
   - VH time series (7 bands: current + 6 backward)
   - Temporal differences (6 features)
   - Temporal ratios (6 features)
   - Phenology indicators (6 features)
   - Extrema features (4 features)
4. Trains with 5-fold stratified cross-validation
5. Saves model artifacts to `model_files/`

**Output:**

```
model_files/
├── rice_stage_model.keras          # Trained model
├── scaler.joblib                   # Feature scaler
├── label_encoder.joblib            # Label encoder
├── feature_columns.txt             # Feature names
└── training_YYYYMMDD_HHMMSS/       # Training logs
    ├── confusion_matrix.png
    ├── classification_report.txt
    └── training_log.txt
```

### 5.4 Training Options

**For better accuracy**, use enhanced training scripts:

```bash
# CNN model
python train_cnn.py --use-smote

# CNN-LSTM model with class balancing
python balanced_train_lstm.py --augment --use-class-weights

# Standard with balancing
python balanced_train.py --augment
```

See `OPTIMIZATION_RECOMMENDATIONS.md` for details.

### 5.5 Evaluate Model

Check training logs:

```bash
# View classification report
cat model_files/training_*/classification_report.txt

# View confusion matrix
display model_files/training_*/confusion_matrix.png
```

**Expected Accuracy:** 75-90% (depends on training data quality and quantity)

---

## Step 6: Prediction

Generate rice growth stage maps for any period.

### 6.1 Single Period Prediction

```bash
python predict.py --period 15
```

**Valid period range:** 7-31 (period 7 is minimum because it needs 7 bands for backward window)

**What happens:**
1. Loads trained model and artifacts
2. Reads bands 15, 14, 13, 12, 11, 10, 9 from the 31-band stack
3. Extracts 29 features for each pixel
4. Predicts growth stage (1-6) for each pixel
5. Applies spatial smoothing (median filter)
6. Optionally applies temporal filtering (uses previous periods)
7. Saves output to `predictions/period_15/`

**Output:**

```
predictions/period_15/
├── predictions.tif           # Growth stage map (1-6, nodata=-32768)
├── confidence.tif            # Model confidence (0-1)
├── prediction_map.png        # Visualization
└── statistics.txt            # Class distribution
```

### 6.2 Prediction Options

**Skip test prediction** (faster):
```bash
python predict.py --period 15 --skip-test
```

**Use mask file** (limit prediction area):
```bash
python predict.py --period 15 --mask path/to/rice_mask.tif
```

**Disable temporal filtering**:
```bash
python predict.py --period 15 --no-temporal
```

### 6.3 Batch Predictions

**Predict all valid periods:**

```bash
./run_predictions.sh
```

Edit `START_PERIOD` and `END_PERIOD` in the script (valid: 7-31).

**Or create a custom loop:**

```bash
for period in {7..31}; do
    echo "Predicting period $period..."
    python predict.py --period $period --skip-test
done
```

### 6.4 Using Optimized Prediction (Recommended)

For **10-50x faster** predictions:

```bash
python predict_optimized.py --period 15 --skip-test
```

See `OPTIMIZATION_RECOMMENDATIONS.md` for details.

### 6.5 Visualize Results

**View in QGIS:**
1. Load `predictions/period_15/predictions.tif`
2. Set symbology to categorical values (1-6)
3. Assign colors for each growth stage

**Command-line visualization:**

```bash
# Create PNG preview with color scheme
gdal_translate -of PNG -scale 1 6 \
    predictions/period_15/predictions.tif \
    predictions/period_15/preview.png
```

---

## Directory Structure

**Complete directory tree:**

```
work/
├── downloads/                          # Raw Sentinel-1 data from ASF
│   ├── downloads_p1/
│   │   ├── S1A_IW_GRDH_*.zip
│   │   └── ...
│   ├── downloads_p2/
│   └── ...
│
├── preprocessed_10m/                   # SNAP preprocessed VH GeoTIFFs
│   ├── p1/
│   │   ├── S1A_*_VH_10m.tif
│   │   └── ...
│   ├── p2/
│   └── ...
│
├── workspace/
│   ├── mosaics_10m/                   # OTB mosaics per period
│   │   ├── period_01_mosaic.tif
│   │   ├── period_02_mosaic.tif
│   │   └── ...
│   └── java_vh_stack_2024_31bands.tif # Final 31-band stack
│
├── model_files/                        # Trained model artifacts
│   ├── rice_stage_model.keras
│   ├── scaler.joblib
│   ├── label_encoder.joblib
│   ├── feature_columns.txt
│   └── training_YYYYMMDD_HHMMSS/
│
├── predictions/                        # Output predictions
│   ├── period_07/
│   ├── period_08/
│   └── ...
│
└── DL/vh/backup_model_6fase_enhanced_backward/  # Code repository
    ├── train.py
    ├── predict.py
    ├── s1_mosaic_single_period.py
    ├── stack_period_mosaics.py
    ├── config.py
    └── ...
```

---

## Troubleshooting

### Issue: OTB Mosaic Parameter Error

**Error:** `Parameter -comp.feather.large.comp does not exist`

**Solution:** This parameter was removed in recent OTB versions. The scripts have been updated to use only `-comp.feather large`.

---

### Issue: GDAL Not Found in Conda Environment

**Error:** `ModuleNotFoundError: No module named 'osgeo'`

**Solution:**
```bash
conda install -c conda-forge gdal
```

---

### Issue: NumPy Version Conflict

**Error:** `A module that was compiled using NumPy 1.x cannot be run in NumPy 2.0.2`

**Solution:** The scripts have been updated to avoid importing `gdal_array`. If issues persist:
```bash
conda install "numpy<2"
```

---

### Issue: OTB Command Not Found

**Error:** `otbcli_Mosaic: command not found`

**Solution:** The scripts automatically source OTB environment when running `otbcli_Mosaic`. Keep OTB configuration **commented out** in `.bashrc` to avoid GDAL conflicts.

---

### Issue: Missing Periods in Stack

**Error:** `Missing: Period X mosaic`

**Solution:**
1. Check if the mosaic file exists in the mosaic directory
2. If missing, re-run mosaicking for that period
3. Ensure the filename matches `period_XX_mosaic.tif` format (with zero-padding)

---

### Issue: Predictions Have No Valid Data

**Possible causes:**
1. Period number < 7 (not enough bands for backward window)
2. All pixels masked by mask file
3. All pixels have NaN/Inf values in input stack

**Solution:**
- Use periods 7-31 only
- Check mask file: `gdalinfo mask.tif`
- Verify stack has valid data: `gdallocationinfo stack.tif 1000 1000`

---

### Issue: Out of Memory During Prediction

**Error:** `GPU/CPU out of memory`

**Solution:** Reduce chunk size in `predict.py`:
```python
# Line ~200
chunk_size = 10000  # Reduce from 20000
```

Or use a mask file to process fewer pixels.

---

## Next Steps

After completing this workflow:

1. **Validate predictions** against ground truth data
2. **Fine-tune model** with more training samples
3. **Temporal analysis** - track rice field progression over time
4. **Area estimation** - calculate area per growth stage
5. **Export to GIS** - integrate with QGIS/ArcGIS for further analysis

---

## Additional Resources

- **12-Day Period System**: See `12DAY_PERIOD_SYSTEM.md`
- **Automated Pipeline**: See `AUTOMATED_PIPELINE_GUIDE.md`
- **Performance Optimization**: See `OPTIMIZATION_RECOMMENDATIONS.md`
- **Temporal Filtering**: See `HEIKIN_ASHI_FILTERING_GUIDE.md`
- **Project Overview**: See `CLAUDE.md`

---

## Support

For issues or questions:
- Check documentation in this repository
- Review error logs in `model_files/training_*/` or prediction output directories
- Verify SNAP, OTB, and GDAL installations

**Last Updated:** 2025-10-20
