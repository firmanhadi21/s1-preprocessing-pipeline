# Consistent Preprocessing: 2024 Training + 2025 Prediction

## ⚠️ Critical Requirement

**You MUST use identical preprocessing for both 2024 (training) and 2025 (prediction) data!**

Different preprocessing = Different backscatter values = Model failure

---

## The Problem

### Current Situation (INCORRECT)

```
2024 Training Data:
├─ Processed with: GEE / Custom workflow / Unknown
├─ Calibration: Unknown
├─ Speckle filter: Unknown
└─ Output: HA_JAWA_2024_compressed.tif

2025 Prediction Data:
├─ Processed with: SNAP GPT (sen1_preprocessing-gpt.xml)
├─ Calibration: Beta0 → Gamma0 (terrain-flattened)
├─ Speckle filter: Gamma Map 5×5
└─ Output: s1_vh_stack_2025_31bands.tif

❌ PROBLEM: Different preprocessing = Different radiometry = Model mismatch!
```

### The Solution (CORRECT)

```
Both 2024 AND 2025:
├─ Processed with: SNAP GPT (sen1_preprocessing-gpt.xml)
├─ Calibration: Beta0 → Gamma0 (terrain-flattened)
├─ Speckle filter: Gamma Map 5×5
└─ Consistent output: Gamma Nought in dB

✅ SOLUTION: Identical preprocessing = Consistent radiometry = Model works!
```

---

## Complete Workflow (UPDATED)

### Phase 1: Reprocess 2024 Data with SNAP

#### Step 1: Download 2024 Sentinel-1 Data

**Option A: Automated Download**

Edit `pipeline_config.yaml` for 2024:
```yaml
data_acquisition:
  download_source: asf
  aoi_bbox: [106.0, -8.0, 115.0, -5.0]  # Your Java Island AOI
  start_date: '2024-01-01'
  end_date: '2024-12-31'
  orbit_direction: ASCENDING
```

Run pipeline:
```bash
# Download 2024 data
python s1_pipeline_auto.py --config pipeline_config.yaml --download-only
```

**Option B: Manual Download**

Use ASF Vertex: https://search.asf.alaska.edu/
- Platform: Sentinel-1A, Sentinel-1B
- Beam Mode: IW
- Polarization: VV+VH or Dual VV+VH
- Date Range: 2024-01-01 to 2024-12-31
- Area: Your AOI (Java Island)
- Download all matching scenes

#### Step 2: Preprocess 2024 Data with SNAP

**Automated:**
```bash
python s1_pipeline_auto.py --config pipeline_config.yaml --preprocess-only
```

**Manual batch processing:**
```bash
python s1_preprocess_snap.py \
    --input downloads_2024/*.zip \
    --output preprocessed_2024/ \
    --graph sen1_preprocessing-gpt.xml \
    --batch
```

**Output**: Preprocessed 2024 scenes in `preprocessed_2024/`
- VH polarization
- Gamma Nought (dB)
- Speckle filtered (Gamma Map 5×5)
- Geocoded (WGS84)

#### Step 3: Create 2024 Annual Stack (12-Day Composites)

```bash
python s1_composite_12day.py \
    --year 2024 \
    --input-dir preprocessed_2024/ \
    --output s1_vh_stack_2024_31bands.tif \
    --method median
```

**Output**: `s1_vh_stack_2024_31bands.tif`
- 31 bands (Period 1-31)
- Gamma Nought (dB)
- Consistent with 2025 preprocessing ✅

#### Step 4: Update config.py for 2024 Stack

```python
FILES = {
    'TRAINING_GEOTIFF': 's1_vh_stack_2024_31bands.tif',  # ← NEW 2024 stack
    'PREDICTION_GEOTIFF': 's1_vh_stack_2024_31bands.tif',  # Use same for validation
    'TRAINING_CSV': 'data/training_points_0104.csv',
    'PERIOD_LOOKUP': 'data/perioda.csv'
}
```

#### Step 5: Verify Training Points Match Periods

Your training CSV has dates. Verify they map correctly to 2024 periods:

```bash
# Generate 2024 period lookup
python s1_composite_12day.py --year 2024 --generate-lookup \
    --input-dir . --output dummy.tif
# Creates perioda_2024.csv

# Check a few training dates
python -c "
from period_utils import get_period_from_date
from datetime import datetime

# Example training dates
dates = [
    datetime(2024, 3, 15),
    datetime(2024, 6, 20),
    datetime(2024, 9, 10)
]

for date in dates:
    period = get_period_from_date(date)
    print(f'{date.date()} → Period {period}')
"
```

#### Step 6: Train Model with Reprocessed 2024 Data

```bash
# Standard training
python train.py

# Recommended: Balanced training with augmentation
python balanced_train_lstm.py --augment --use-class-weights

# With Heikin-Ashi temporal filtering
python train_with_filtering.py --filter-strength 0.5
```

**Output**: Model artifacts in `model_files/`
- Trained on consistent SNAP-processed data ✅
- Same preprocessing as 2025 predictions ✅

---

### Phase 2: Process 2025 Data (Same Way)

#### Step 1: Download 2025 Sentinel-1 Data

Update `pipeline_config.yaml` for 2025:
```yaml
data_acquisition:
  start_date: '2025-01-01'
  end_date: '2025-12-31'  # Or current date
  # Same AOI, orbit direction as 2024
```

```bash
python s1_pipeline_auto.py --config pipeline_config.yaml --download-only
```

#### Step 2: Preprocess 2025 Data with SNAP

```bash
# Use SAME preprocessing graph as 2024
python s1_pipeline_auto.py --config pipeline_config.yaml --preprocess-only
```

#### Step 3: Create 2025 Annual Stack

```bash
python s1_composite_12day.py \
    --year 2025 \
    --input-dir preprocessed_2025/ \
    --output s1_vh_stack_2025_31bands.tif \
    --method median  # Same method as 2024
```

#### Step 4: Update config.py for Prediction

```python
FILES = {
    'TRAINING_GEOTIFF': 's1_vh_stack_2024_31bands.tif',  # Training data
    'PREDICTION_GEOTIFF': 's1_vh_stack_2025_31bands.tif',  # Prediction data
    'TRAINING_CSV': 'data/training_points_0104.csv',
}
```

#### Step 5: Generate 2025 Predictions

```bash
# Predict all valid periods
for period in {7..31}; do
    python predict_optimized.py --period $period --skip-test
done
```

---

## Why This Matters

### Example: Impact of Different Preprocessing

**Scenario 1: GEE vs SNAP (WRONG)**
```
GEE-processed 2024:
VH = -18.5 dB (Sigma0, different speckle filter)

SNAP-processed 2025:
VH = -16.2 dB (Gamma0, Gamma Map filter)

Difference: 2.3 dB → Model sees different patterns → Poor predictions
```

**Scenario 2: Both SNAP (CORRECT)**
```
SNAP-processed 2024:
VH = -16.2 dB (Gamma0, Gamma Map filter)

SNAP-processed 2025:
VH = -16.2 dB (Gamma0, Gamma Map filter)

Difference: 0.0 dB → Model sees consistent patterns → Good predictions ✅
```

### Radiometric Differences by Calibration Type

| Calibration | Typical VH Range | Use Case |
|-------------|------------------|----------|
| **Sigma Nought (σ0)** | -22 to -8 dB | Flat terrain |
| **Beta Nought (β0)** | -20 to -6 dB | Intermediate |
| **Gamma Nought (γ0)** | -18 to -4 dB | Mountainous terrain ✅ |

Java Island has topography → **Gamma Nought is best** ✅

---

## Directory Structure

Recommended organization:

```
project/
├── downloads_2024/          # Raw S1 ZIP files (2024)
│   ├── S1A_*.zip
│   └── S1B_*.zip
├── downloads_2025/          # Raw S1 ZIP files (2025)
│   ├── S1A_*.zip
│   └── S1B_*.zip
├── preprocessed_2024/       # SNAP-processed (2024)
│   ├── S1A_*_processed.tif
│   └── S1B_*_processed.tif
├── preprocessed_2025/       # SNAP-processed (2025)
│   ├── S1A_*_processed.tif
│   └── S1B_*_processed.tif
├── s1_vh_stack_2024_31bands.tif  # Training stack
├── s1_vh_stack_2025_31bands.tif  # Prediction stack
├── data/
│   ├── training_points_0104.csv  # Training samples
│   ├── perioda_2024.csv          # 2024 period lookup
│   └── perioda_2025.csv          # 2025 period lookup
├── model_files/
│   ├── rice_stage_model.keras    # Trained model
│   ├── scaler.joblib
│   └── label_encoder.joblib
└── predictions/
    ├── period_07/
    ├── period_08/
    └── ...
```

---

## Automated Pipeline (Both Years)

You can use the automated pipeline for both years:

### For 2024 (Training)

```bash
# Create config for 2024
cp pipeline_config.yaml pipeline_config_2024.yaml

# Edit dates
vim pipeline_config_2024.yaml
# Change: start_date: '2024-01-01'
#         end_date: '2024-12-31'

# Run full pipeline
python s1_pipeline_auto.py --config pipeline_config_2024.yaml --run-all
```

**Output**: `pipeline_workspace/stacked/s1_vh_stack_2024_31bands.tif`

### For 2025 (Prediction)

```bash
# Create config for 2025
cp pipeline_config.yaml pipeline_config_2025.yaml

# Edit dates
vim pipeline_config_2025.yaml
# Change: start_date: '2025-01-01'
#         end_date: '2025-12-31'

# Run full pipeline
python s1_pipeline_auto.py --config pipeline_config_2025.yaml --run-all
```

**Output**: `pipeline_workspace/stacked/s1_vh_stack_2025_31bands.tif`

---

## Verification Checklist

### Before Training

Check 2024 stack:
```bash
# Check it's Gamma Nought
gdalinfo s1_vh_stack_2024_31bands.tif | head -50

# Verify 31 bands
gdalinfo s1_vh_stack_2024_31bands.tif | grep "Band " | wc -l
# Should output: 31

# Check band descriptions
gdalinfo s1_vh_stack_2024_31bands.tif | grep Description
# Should show: Period_1_20240101_20240112, etc.

# Check value range (should be dB)
gdalinfo -stats s1_vh_stack_2024_31bands.tif
# VH typically: -30 to 0 dB
```

### Before Prediction

Compare 2024 and 2025 preprocessing:
```bash
# Check both have same band count
gdalinfo s1_vh_stack_2024_31bands.tif | grep "Size is"
gdalinfo s1_vh_stack_2025_31bands.tif | grep "Size is"
# Don't need same size, but should be similar

# Check both use same NoData
gdalinfo s1_vh_stack_2024_31bands.tif | grep NoData
gdalinfo s1_vh_stack_2025_31bands.tif | grep NoData
# Should both be: -32768

# Check value ranges are similar
gdalinfo -stats s1_vh_stack_2024_31bands.tif | grep "STATISTICS_MEAN"
gdalinfo -stats s1_vh_stack_2025_31bands.tif | grep "STATISTICS_MEAN"
# Should be within 1-2 dB if same area/season
```

---

## Processing Time Estimates

Based on typical Sentinel-1 processing:

| Step | Per Scene | 100 Scenes | 365 Days Coverage |
|------|-----------|------------|-------------------|
| **Download** | 1-5 min | 2-8 hours | 3-12 hours |
| **SNAP GPT** | 3-10 min | 5-16 hours | 18-60 hours |
| **Compositing** | - | - | 1-5 minutes |
| **Total** | - | 7-24 hours | 21-72 hours |

**Recommendation**:
- Use automated pipeline overnight
- Process 2024 and 2025 separately
- Budget 1-3 days per year for full processing

---

## Quick Start Commands

### Complete Workflow (2024 + 2025)

```bash
# ========================================
# YEAR 2024 (Training)
# ========================================

# 1. Download 2024 data
python s1_download.py \
    --start 2024-01-01 \
    --end 2024-12-31 \
    --aoi "POLYGON((106 -8, 115 -8, 115 -5, 106 -5, 106 -8))" \
    --output downloads_2024/

# 2. Preprocess with SNAP
python s1_preprocess_snap.py \
    --input downloads_2024/*.zip \
    --output preprocessed_2024/ \
    --graph sen1_preprocessing-gpt.xml \
    --batch

# 3. Create 31-band stack
python s1_composite_12day.py \
    --year 2024 \
    --input-dir preprocessed_2024/ \
    --output s1_vh_stack_2024_31bands.tif \
    --method median

# 4. Train model
python balanced_train_lstm.py --augment --use-class-weights

# ========================================
# YEAR 2025 (Prediction)
# ========================================

# 1. Download 2025 data
python s1_download.py \
    --start 2025-01-01 \
    --end 2025-12-31 \
    --aoi "POLYGON((106 -8, 115 -8, 115 -5, 106 -5, 106 -8))" \
    --output downloads_2025/

# 2. Preprocess with SNAP (SAME as 2024)
python s1_preprocess_snap.py \
    --input downloads_2025/*.zip \
    --output preprocessed_2025/ \
    --graph sen1_preprocessing-gpt.xml \
    --batch

# 3. Create 31-band stack (SAME method as 2024)
python s1_composite_12day.py \
    --year 2025 \
    --input-dir preprocessed_2025/ \
    --output s1_vh_stack_2025_31bands.tif \
    --method median

# 4. Generate predictions
for period in {7..31}; do
    python predict_optimized.py --period $period --skip-test
done
```

---

## Summary

### ✅ Correct Workflow

1. **Download 2024 S1 data** (same source as 2025)
2. **Preprocess 2024 with SNAP** (same graph as 2025)
3. **Create 2024 stack** (same compositing as 2025)
4. **Train model** on consistent 2024 data
5. **Download 2025 S1 data** (same parameters)
6. **Preprocess 2025 with SNAP** (same graph)
7. **Create 2025 stack** (same compositing)
8. **Predict 2025** using 2024-trained model

### ⚠️ Critical Requirements

- ✅ **Same SNAP graph** for both years
- ✅ **Same calibration** (Gamma Nought)
- ✅ **Same speckle filter** (Gamma Map 5×5)
- ✅ **Same compositing method** (median)
- ✅ **Same period structure** (31 × 12-day periods)

### 🎯 Result

**Consistent preprocessing** → **Reliable predictions** → **Operational system** ✅

---

*This ensures your model generalizes from 2024 training to 2025 predictions!*
