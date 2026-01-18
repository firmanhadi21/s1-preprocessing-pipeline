# Quick Reference Guide - Sentinel-1 Rice Mapping

One-page cheat sheet for the complete workflow.

## Prerequisites Setup

```bash
# 1. Activate conda environment
conda activate myenv  # or geo_ml_env

# 2. Install GDAL if not present
conda install -c conda-forge gdal

# 3. Install ASF tools
pip install asf-search

# 4. Verify OTB (should be in ~/work/OTB/)
source ~/work/OTB/otbenv.profile
otbcli_Mosaic --help
```

**Important:** Keep OTB config in `.bashrc` **commented out** to avoid GDAL conflicts!

---

## Complete Workflow (One Command Per Step)

### Step 1: Download Data (ASF)

```python
# Download Period 1 data covering Java Island
import asf_search as asf
from datetime import datetime

aoi = "POLYGON((105.0 -9.0, 116.0 -9.0, 116.0 -5.0, 105.0 -5.0, 105.0 -9.0))"
session = asf.ASFSession().auth_with_creds('USERNAME', 'PASSWORD')

results = asf.search(
    platform=asf.PLATFORM.SENTINEL1,
    intersectsWith=aoi,
    start=datetime(2024, 1, 1),
    end=datetime(2024, 1, 12),
    processingLevel='GRD_HD',
    beamMode='IW',
    polarization='VV+VH'
)

results.download(path='downloads/downloads_p1', session=session)
```

Repeat for periods 2-31.

---

### Step 2: Preprocess with SNAP

```bash
# Single period
python s1_preprocess_snap.py \
    --input-dir downloads/downloads_p1 \
    --output-dir preprocessed_10m/p1 \
    --resolution 10 \
    --graph sen1_preprocessing-gpt.xml

# All periods (loop)
for p in {1..31}; do
    python s1_preprocess_snap.py \
        --input-dir downloads/downloads_p${p} \
        --output-dir preprocessed_10m/p${p} \
        --resolution 10 \
        --graph sen1_preprocessing-gpt.xml
done
```

**Output:** `preprocessed_10m/p1/`, `preprocessed_10m/p2/`, etc.

---

### Step 3: Mosaic with OTB

```bash
# Single period
python s1_mosaic_single_period.py \
    --input-dir preprocessed_10m/p1 \
    --output workspace/mosaics_10m/period_01_mosaic.tif \
    --period 1 \
    --year 2024 \
    --resolution 10

# All periods (loop)
for p in {1..31}; do
    python s1_mosaic_single_period.py \
        --input-dir preprocessed_10m/p${p} \
        --output workspace/mosaics_10m/period_$(printf "%02d" $p)_mosaic.tif \
        --period $p \
        --year 2024 \
        --resolution 10
done
```

**Output:** `workspace/mosaics_10m/period_01_mosaic.tif` through `period_31_mosaic.tif`

---

### Step 4: Stack All Periods

```bash
python stack_period_mosaics.py \
    --mosaic-dir workspace/mosaics_10m \
    --output workspace/java_vh_stack_2024_31bands.tif
```

**Output:** 31-band GeoTIFF ready for training/prediction

---

### Step 5: Update Config and Train

```bash
# Edit config.py
# VH_STACK_2024 = 'workspace/java_vh_stack_2024_31bands.tif'
# TRAINING_CSV = 'training_data.csv'

# Train model
python train.py
```

**Output:** `model_files/rice_stage_model.keras` + artifacts

---

### Step 6: Generate Predictions

```bash
# Single period
python predict.py --period 15

# Batch predictions (periods 7-31)
./run_predictions.sh

# Optimized (10-50x faster)
python predict_optimized.py --period 15 --skip-test
```

**Output:** `predictions/period_15/predictions.tif`, `confidence.tif`, etc.

---

## Directory Structure

```
work/
├── downloads/
│   ├── downloads_p1/         # ASF downloaded .zip files
│   ├── downloads_p2/
│   └── ...
├── preprocessed_10m/
│   ├── p1/                   # SNAP preprocessed VH GeoTIFFs
│   ├── p2/
│   └── ...
├── workspace/
│   ├── mosaics_10m/          # OTB mosaics
│   │   ├── period_01_mosaic.tif
│   │   └── ...
│   └── java_vh_stack_2024_31bands.tif  # Final stack
├── model_files/              # Trained model
└── predictions/              # Output maps
    ├── period_07/
    └── ...
```

---

## Common Commands

### Verify Data

```bash
# Check mosaic
gdalinfo workspace/mosaics_10m/period_01_mosaic.tif

# Check stack
gdalinfo workspace/java_vh_stack_2024_31bands.tif | grep "Band "

# Sample pixel values
gdallocationinfo workspace/java_vh_stack_2024_31bands.tif 1000 1000
```

### Visualize

```bash
# Create PNG preview
gdal_translate -of PNG -scale \
    predictions/period_15/predictions.tif \
    preview.png

# Open in QGIS
qgis predictions/period_15/predictions.tif
```

### Check Model Performance

```bash
# View training results
cat model_files/training_*/classification_report.txt

# View confusion matrix
display model_files/training_*/confusion_matrix.png
```

---

## Key Parameters

| Parameter | Description | Default | Range |
|-----------|-------------|---------|-------|
| Period | 12-day period number | - | 1-31 (predict: 7-31) |
| Resolution | Pixel size in meters | 50 | 10, 20, 50 |
| Year | Processing year | 2024 | Any |
| Chunk size | Pixels per batch | 20000 | 5000-50000 |

---

## 12-Day Period Calendar (2024)

| Period | Date Range | Period | Date Range |
|--------|------------|--------|------------|
| 1 | Jan 1-12 | 17 | Jun 25-Jul 6 |
| 2 | Jan 13-24 | 18 | Jul 7-18 |
| 3 | Jan 25-Feb 5 | 19 | Jul 19-30 |
| 4 | Feb 6-17 | 20 | Jul 31-Aug 11 |
| 5 | Feb 18-29 | 21 | Aug 12-23 |
| 6 | Mar 1-12 | 22 | Aug 24-Sep 4 |
| 7 | Mar 13-24 | 23 | Sep 5-16 |
| 8 | Mar 25-Apr 5 | 24 | Sep 17-28 |
| 9 | Apr 6-17 | 25 | Sep 29-Oct 10 |
| 10 | Apr 18-29 | 26 | Oct 11-22 |
| 11 | Apr 30-May 11 | 27 | Oct 23-Nov 3 |
| 12 | May 12-23 | 28 | Nov 4-15 |
| 13 | May 24-Jun 4 | 29 | Nov 16-27 |
| 14 | Jun 5-16 | 30 | Nov 28-Dec 9 |
| 15 | Jun 17-28 | 31 | Dec 10-21 |
| 16 | Jun 29-Jul 10 | - | - |

See `12DAY_PERIOD_SYSTEM.md` for complete calendar and utilities.

---

## Troubleshooting Quick Fixes

| Issue | Quick Fix |
|-------|-----------|
| `GDAL not found` | `conda install -c conda-forge gdal` |
| `otbcli_Mosaic: command not found` | Keep `.bashrc` OTB config commented out |
| `NumPy version conflict` | `conda install "numpy<2"` |
| `Period < 7 not allowed` | Use periods 7-31 only for prediction |
| `Out of memory` | Reduce chunk_size in predict.py |
| `No valid predictions` | Check mask file and input data |

---

## Performance Tips

1. **Use optimized scripts** for 10-50x speedup:
   - `predict_optimized.py` instead of `predict.py`
   - `utils_optimized.py` for vectorized operations

2. **Parallel processing**:
   - Download: ASF with `processes=4`
   - SNAP: Process multiple periods simultaneously
   - Predictions: Run multiple periods in parallel

3. **Disk space**:
   - Raw downloads: ~500GB for 31 periods
   - Preprocessed: ~200GB
   - Mosaics: ~50GB
   - Stack: ~5-10GB

4. **Memory requirements**:
   - Training: 16GB RAM minimum
   - Prediction: 32GB+ recommended (or use smaller chunks)
   - SNAP: 256GB allocated (adjust SNAP_GPT_MEMORY)

---

## File Formats

- **Raw data**: Sentinel-1 .zip (SAFE format)
- **Preprocessed**: GeoTIFF (.tif), Float32, dB scale, WGS84
- **Mosaics**: GeoTIFF, Float32, Nodata=-32768
- **Stack**: Multi-band GeoTIFF, 31 bands, Nodata=-32768
- **Predictions**: GeoTIFF, Int16, Values 1-6, Nodata=-32768
- **Training**: CSV with columns: tanggal, lintang, bujur, fase

---

## Resources

- Full documentation: `COMPLETE_WORKFLOW.md`
- Period system: `12DAY_PERIOD_SYSTEM.md`
- Automated pipeline: `AUTOMATED_PIPELINE_GUIDE.md`
- Optimization: `OPTIMIZATION_RECOMMENDATIONS.md`
- Project overview: `CLAUDE.md`

---

**Last Updated:** 2025-10-20
