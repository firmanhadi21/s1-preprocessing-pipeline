# Manual Preprocessing Guide

Complete guide for preprocessing Sentinel-1 data when downloads are performed manually (not using the automated pipeline).

## Table of Contents

- [Overview](#overview)
- [Directory Structure](#directory-structure)
- [Step-by-Step Workflow](#step-by-step-workflow)
- [Multi-Resolution Processing](#multi-resolution-processing)
- [Compositing by Resolution](#compositing-by-resolution)
- [Troubleshooting](#troubleshooting)

---

## Overview

This guide covers preprocessing when you have manually downloaded Sentinel-1 data into period-specific folders like:
- `workspace/downloads/downloads_p1/`
- `workspace/downloads/downloads_p2/`
- etc.

### Processing Workflow

```
Manual Downloads → Preprocessing (by resolution) → Compositing → Training/Prediction
```

### Resolution Options

| Resolution | Output Folder | Use Case | Processing Time/Scene |
|------------|---------------|----------|----------------------|
| 10m | `preprocessed_10m/` | High-detail mapping | ~2 hours |
| 20m | `preprocessed_20m/` | Detailed regional mapping | ~30 min |
| 50m | `preprocessed_50m/` | **Operational national mapping** | ~7 min |
| 100m | `preprocessed_100m/` | Rapid monitoring | ~2.5 min |

---

## Directory Structure

### Before Processing

```
project/
├── workspace/
│   └── downloads/
│       ├── downloads_p1/           # Period 1 scenes (Jan 1-12)
│       │   ├── S1A_...20250101....zip
│       │   ├── S1A_...20250105....zip
│       │   └── S1B_...20250110....zip
│       ├── downloads_p2/           # Period 2 scenes (Jan 13-24)
│       │   └── S1A_...20250115....zip
│       ├── downloads_p7/           # Period 7 scenes
│       │   └── ...
│       └── downloads_p31/          # Period 31 scenes (Dec 27-31)
│           └── ...
├── sen1_preprocessing-gpt.xml      # 10m processing graph
├── sen1_preprocessing-gpt-20m.xml  # 20m processing graph
├── sen1_preprocessing-gpt-50m.xml  # 50m processing graph
└── sen1_preprocessing-gpt-100m.xml # 100m processing graph
```

### After Processing

```
project/
├── workspace/
│   └── downloads/                  # Original downloads (keep for reprocessing)
│       └── downloads_p*/
├── preprocessed_10m/               # 10m processed scenes
│   ├── S1A_...20250101...VH_10m.tif
│   ├── S1A_...20250105...VH_10m.tif
│   └── processing_status_10m.json
├── preprocessed_50m/               # 50m processed scenes (RECOMMENDED)
│   ├── S1A_...20250101...VH_50m.tif
│   └── processing_status_50m.json
├── stacks/                         # Annual stacks by resolution
│   ├── s1_vh_stack_2025_31bands_10m.tif
│   ├── s1_vh_stack_2025_31bands_50m.tif
│   └── s1_vh_stack_2025_31bands_100m.tif
└── model_files_50m/                # Resolution-specific models
    ├── rice_stage_model.keras
    ├── scaler.joblib
    └── label_encoder.joblib
```

---

## Step-by-Step Workflow

### Step 1: Organize Downloads

If your downloads are scattered, organize them by period:

```bash
# Optional: Organize by period if not already done
# Create period directories
for i in {1..31}; do
  mkdir -p workspace/downloads/downloads_p${i}
done

# Move files to appropriate period folders (manual or script-based)
# Example: Move files with date YYYYMMDD to corresponding period
```

### Step 2: Merge All Downloads into Single Directory (RECOMMENDED)

For easier processing, merge all period folders into one:

```bash
# Create a unified download directory
mkdir -p workspace/downloads/all_downloads

# Copy all .zip files from period folders
cp workspace/downloads/downloads_p*/*.zip workspace/downloads/all_downloads/

# Check total count
ls workspace/downloads/all_downloads/*.zip | wc -l
```

### Step 3: Choose Resolution and Preprocess

Choose resolution based on your needs (see [Multi-Resolution Processing](#multi-resolution-processing)).

#### Option A: 50m Resolution (RECOMMENDED for Indonesia)

```bash
# Estimate processing time first
python s1_preprocess_parallel_multiresolution.py \
  --input-dir workspace/downloads/all_downloads \
  --output-dir preprocessed_50m \
  --resolution 50 \
  --workers 8 \
  --estimate-only

# Run preprocessing
python s1_preprocess_parallel_multiresolution.py \
  --input-dir workspace/downloads/all_downloads \
  --output-dir preprocessed_50m \
  --resolution 50 \
  --workers 8
```

**Processing Time:**
- 50 scenes: ~6 hours (with 8 workers)
- 360 scenes (1 year): ~42 hours (1.75 days)
- 1350 scenes (Indonesia full): ~19 hours (<1 day)

#### Option B: 10m High-Detail Resolution

```bash
python s1_preprocess_parallel_multiresolution.py \
  --input-dir workspace/downloads/all_downloads \
  --output-dir preprocessed_10m \
  --resolution 10 \
  --workers 4
```

**Processing Time:**
- 50 scenes: ~25 hours (1 day)
- 360 scenes: ~180 hours (7.5 days)

#### Option C: 20m Balanced Resolution

```bash
python s1_preprocess_parallel_multiresolution.py \
  --input-dir workspace/downloads/all_downloads \
  --output-dir preprocessed_20m \
  --resolution 20 \
  --workers 8
```

**Processing Time:**
- 50 scenes: ~6 hours
- 360 scenes: ~45 hours (2 days)

#### Option D: 100m Rapid Resolution

```bash
python s1_preprocess_parallel_multiresolution.py \
  --input-dir workspace/downloads/all_downloads \
  --output-dir preprocessed_100m \
  --resolution 100 \
  --workers 8
```

**Processing Time:**
- 50 scenes: ~30 min
- 360 scenes: ~4 hours

### Step 4: Monitor Processing Progress

Check processing status:

```bash
# View processing log
tail -f preprocessed_50m/*.log

# Check status file
cat preprocessed_50m/processing_status_50m.json

# Count completed files
ls preprocessed_50m/*_VH_50m.tif | wc -l
```

### Step 5: Create Annual Stack (Compositing)

See [Compositing by Resolution](#compositing-by-resolution) section below.

---

## Multi-Resolution Processing

### Processing Multiple Resolutions Simultaneously

You can process the same data at different resolutions for comparison:

```bash
# Process at 50m (operational)
python s1_preprocess_parallel_multiresolution.py \
  --input-dir workspace/downloads/all_downloads \
  --output-dir preprocessed_50m \
  --resolution 50 \
  --workers 8 &

# Process at 10m (detailed) - use fewer workers to avoid memory issues
python s1_preprocess_parallel_multiresolution.py \
  --input-dir workspace/downloads/all_downloads \
  --output-dir preprocessed_10m \
  --resolution 10 \
  --workers 4 &

# Wait for both to complete
wait
```

**Memory Requirements:**
- 8 workers @ 50m: ~400 GB RAM
- 4 workers @ 10m: ~800 GB RAM
- **Total if running both: ~1.2 TB RAM**

### Sequential Processing (Lower Memory)

If memory is limited, process sequentially:

```bash
# First: 50m for operational use
python s1_preprocess_parallel_multiresolution.py \
  --input-dir workspace/downloads/all_downloads \
  --output-dir preprocessed_50m \
  --resolution 50 \
  --workers 8

# Then: 10m for detailed analysis (selected regions only)
python s1_preprocess_parallel_multiresolution.py \
  --input-dir workspace/downloads/selected_region \
  --output-dir preprocessed_10m \
  --resolution 10 \
  --workers 4
```

### Resume Failed Processing

The script automatically tracks progress and resumes:

```bash
# If processing was interrupted, just rerun the same command
# It will skip already processed files

python s1_preprocess_parallel_multiresolution.py \
  --input-dir workspace/downloads/all_downloads \
  --output-dir preprocessed_50m \
  --resolution 50 \
  --workers 8

# Check what's already done
cat preprocessed_50m/processing_status_50m.json | grep completed | wc -l
```

---

## Compositing by Resolution

After preprocessing, create annual stacks for each resolution.

### Compositing 50m Data (RECOMMENDED)

```bash
# Create 31-band annual stack from 50m preprocessed scenes
python s1_composite_12day.py \
  --year 2025 \
  --input-dir preprocessed_50m \
  --output stacks/s1_vh_stack_2025_31bands_50m.tif \
  --method median

# Print period calendar for reference
python s1_composite_12day.py \
  --year 2025 \
  --print-calendar \
  --input-dir . \
  --output dummy.tif

# Generate period lookup CSV
python s1_composite_12day.py \
  --year 2025 \
  --generate-lookup \
  --input-dir . \
  --output dummy.tif
```

**Output:**
- File: `stacks/s1_vh_stack_2025_31bands_50m.tif`
- Bands: 31 (one per 12-day period)
- Size: ~2-5 GB (depends on area)
- Valid prediction periods: 7-31 (need 7 bands for backward window)

### Compositing 10m Data

```bash
python s1_composite_12day.py \
  --year 2025 \
  --input-dir preprocessed_10m \
  --output stacks/s1_vh_stack_2025_31bands_10m.tif \
  --method median
```

**Output:**
- File: `stacks/s1_vh_stack_2025_31bands_10m.tif`
- Bands: 31
- Size: ~50-100 GB (much larger than 50m)

### Compositing 20m Data

```bash
python s1_composite_12day.py \
  --year 2025 \
  --input-dir preprocessed_20m \
  --output stacks/s1_vh_stack_2025_31bands_20m.tif \
  --method median
```

**Output:**
- File: `stacks/s1_vh_stack_2025_31bands_20m.tif`
- Bands: 31
- Size: ~10-20 GB

### Compositing 100m Data

```bash
python s1_composite_12day.py \
  --year 2025 \
  --input-dir preprocessed_100m \
  --output stacks/s1_vh_stack_2025_31bands_100m.tif \
  --method median
```

**Output:**
- File: `stacks/s1_vh_stack_2025_31bands_100m.tif`
- Bands: 31
- Size: ~500 MB - 1 GB

### Compositing Methods

Choose compositing method based on your needs:

```bash
# Median (DEFAULT - RECOMMENDED)
# - Reduces speckle noise
# - Robust to outliers
python s1_composite_12day.py \
  --year 2025 \
  --input-dir preprocessed_50m \
  --output stacks/s1_vh_stack_2025_median_50m.tif \
  --method median

# Mean (faster but less robust)
python s1_composite_12day.py \
  --year 2025 \
  --input-dir preprocessed_50m \
  --output stacks/s1_vh_stack_2025_mean_50m.tif \
  --method mean

# First (earliest scene in period)
python s1_composite_12day.py \
  --year 2025 \
  --input-dir preprocessed_50m \
  --output stacks/s1_vh_stack_2025_first_50m.tif \
  --method first

# Last (latest scene in period)
python s1_composite_12day.py \
  --year 2025 \
  --input-dir preprocessed_50m \
  --output stacks/s1_vh_stack_2025_last_50m.tif \
  --method last
```

**Recommendation:** Use `median` for production, `mean` for faster testing.

### Handling Missing Periods

If some periods have no data:

```bash
# Automatic gap-filling (DEFAULT)
python s1_composite_12day.py \
  --year 2025 \
  --input-dir preprocessed_50m \
  --output stacks/s1_vh_stack_2025_31bands_50m.tif \
  --method median

# Disable gap-filling (keep missing periods as nodata)
python s1_composite_12day.py \
  --year 2025 \
  --input-dir preprocessed_50m \
  --output stacks/s1_vh_stack_2025_31bands_50m.tif \
  --method median \
  --no-fill
```

The script will:
1. Identify periods with no data
2. Interpolate from neighboring periods
3. Report which periods were filled

---

## Complete Multi-Resolution Workflow Example

### Scenario: Process Java Island with Multiple Resolutions

```bash
# ========================================
# STEP 1: ORGANIZE DOWNLOADS
# ========================================
mkdir -p workspace/downloads/java_2025
# Manually copy all Java island .zip files here

# Check file count
echo "Total scenes: $(ls workspace/downloads/java_2025/*.zip | wc -l)"

# ========================================
# STEP 2: PREPROCESS AT 50M (OPERATIONAL)
# ========================================
python s1_preprocess_parallel_multiresolution.py \
  --input-dir workspace/downloads/java_2025 \
  --output-dir preprocessed_java_50m \
  --resolution 50 \
  --workers 8

# ========================================
# STEP 3: PREPROCESS AT 10M (SELECTED AREAS)
# ========================================
# Create subset for high-detail areas
mkdir -p workspace/downloads/java_priority
cp workspace/downloads/java_2025/*_20250[1-3]*zip workspace/downloads/java_priority/

python s1_preprocess_parallel_multiresolution.py \
  --input-dir workspace/downloads/java_priority \
  --output-dir preprocessed_java_10m \
  --resolution 10 \
  --workers 4

# ========================================
# STEP 4: CREATE ANNUAL STACKS
# ========================================

# 50m stack (full year)
mkdir -p stacks
python s1_composite_12day.py \
  --year 2025 \
  --input-dir preprocessed_java_50m \
  --output stacks/java_2025_50m.tif \
  --method median

# 10m stack (Q1 only for priority areas)
python s1_composite_12day.py \
  --year 2025 \
  --input-dir preprocessed_java_10m \
  --output stacks/java_2025_q1_10m.tif \
  --method median \
  --no-fill

# ========================================
# STEP 5: TRAIN MODELS
# ========================================

# Train 50m model (operational)
python train.py \
  --tif-path stacks/java_2025_50m.tif \
  --csv-path training_points_java_2025.csv \
  --output-dir model_files_java_50m

# Train 10m model (detailed)
python train.py \
  --tif-path stacks/java_2025_q1_10m.tif \
  --csv-path training_points_java_priority.csv \
  --output-dir model_files_java_10m

# ========================================
# STEP 6: GENERATE PREDICTIONS
# ========================================

# 50m predictions (periods 7-31)
for period in {7..31}; do
  python predict.py \
    --period $period \
    --tif-path stacks/java_2025_50m.tif \
    --model-path model_files_java_50m \
    --output-dir predictions_java_50m
done

# 10m predictions (periods 7-9 only - Q1 data)
for period in {7..9}; do
  python predict.py \
    --period $period \
    --tif-path stacks/java_2025_q1_10m.tif \
    --model-path model_files_java_10m \
    --output-dir predictions_java_10m
done

echo "Processing complete!"
echo "50m predictions: predictions_java_50m/"
echo "10m predictions: predictions_java_10m/"
```

---

## Troubleshooting

### Issue 1: Files Not Found in Period Folders

**Problem:** Script cannot find .zip files

**Solution:**
```bash
# Check if files exist
ls workspace/downloads/downloads_p1/*.zip

# If scattered, merge into one directory
mkdir -p workspace/downloads/all_downloads
find workspace/downloads -name "*.zip" -exec cp {} workspace/downloads/all_downloads/ \;

# Rerun preprocessing
python s1_preprocess_parallel_multiresolution.py \
  --input-dir workspace/downloads/all_downloads \
  --output-dir preprocessed_50m \
  --resolution 50 \
  --workers 8
```

### Issue 2: Different Resolutions Have Different Coverage

**Problem:** 10m stack has fewer periods than 50m stack

**Solution:** This is expected if you processed different subsets.

```bash
# Check band counts
gdalinfo stacks/s1_vh_stack_2025_50m.tif | grep "Band 1"
gdalinfo stacks/s1_vh_stack_2025_10m.tif | grep "Band 1"

# Option A: Process same input for both resolutions
python s1_preprocess_parallel_multiresolution.py \
  --input-dir workspace/downloads/all_downloads \
  --output-dir preprocessed_10m \
  --resolution 10 \
  --workers 4

# Option B: Use --no-fill to see actual coverage
python s1_composite_12day.py \
  --year 2025 \
  --input-dir preprocessed_10m \
  --output stacks/s1_vh_stack_2025_10m_nofill.tif \
  --method median \
  --no-fill
```

### Issue 3: Preprocessing Stalled

**Problem:** Some scenes fail to process

**Solution:**
```bash
# Check status file
cat preprocessed_50m/processing_status_50m.json | jq '.[] | select(. == "failed")'

# Check error logs
ls preprocessed_50m/*_error.log

# Rerun with fewer workers
python s1_preprocess_parallel_multiresolution.py \
  --input-dir workspace/downloads/all_downloads \
  --output-dir preprocessed_50m \
  --resolution 50 \
  --workers 4  # Reduced from 8

# Or reduce memory allocation
python s1_preprocess_parallel_multiresolution.py \
  --input-dir workspace/downloads/all_downloads \
  --output-dir preprocessed_50m \
  --resolution 50 \
  --workers 8 \
  --memory 30G \
  --cache 25G
```

### Issue 4: Stack Creation Fails

**Problem:** Compositing script cannot create stack

**Solution:**
```bash
# Check if preprocessed files exist
ls preprocessed_50m/*_VH_50m.tif | head -5

# Check file format
gdalinfo preprocessed_50m/S1A_*_VH_50m.tif

# Verify dates are extracted correctly
python s1_composite_12day.py \
  --year 2025 \
  --input-dir preprocessed_50m \
  --output test_stack.tif \
  --method median

# If dates not recognized, check filename format
# Expected: S1A_..._YYYYMMDD...VH_50m.tif
```

### Issue 5: Out of Memory During Compositing

**Problem:** System runs out of RAM during stack creation

**Solution:**
```bash
# Process in chunks (modify script or use simpler method)
# Use 'first' method instead of 'median' (less memory intensive)
python s1_composite_12day.py \
  --year 2025 \
  --input-dir preprocessed_50m \
  --output stacks/s1_vh_stack_2025_50m.tif \
  --method first  # Less memory than median

# Or use coarser resolution
python s1_composite_12day.py \
  --year 2025 \
  --input-dir preprocessed_100m \
  --output stacks/s1_vh_stack_2025_100m.tif \
  --method median
```

### Issue 6: Disk Space Issues

**Problem:** Running out of disk space

**Solutions:**
```bash
# Check space usage
du -sh preprocessed_*
du -sh workspace/downloads

# Clean up intermediate files after compositing
rm -rf preprocessed_50m/*.dim
rm -rf preprocessed_50m/*.data

# Delete raw downloads after successful processing
# WARNING: Only after verifying preprocessing worked!
# rm -rf workspace/downloads/

# Use symbolic links if data on different disks
ln -s /large_disk/downloads workspace/downloads
ln -s /large_disk/preprocessed_50m preprocessed_50m
```

---

## Resolution Selection Quick Reference

| Your Goal | Resolution | Command |
|-----------|------------|---------|
| **Indonesia-wide operational mapping** | 50m | `--resolution 50 --workers 8` |
| **Provincial detailed mapping** | 10m or 20m | `--resolution 10 --workers 4` |
| **Quick feasibility test** | 100m | `--resolution 100 --workers 8` |
| **Small field detection (<0.5 ha)** | 10m | `--resolution 10 --workers 4` |
| **Medium fields (0.5-1 ha)** | 20m or 50m | `--resolution 20 --workers 8` |
| **Large fields (>1 ha)** | 50m or 100m | `--resolution 50 --workers 8` |

---

## Next Steps

After creating your annual stacks:

1. **Train models** (resolution-specific):
   ```bash
   python train.py --tif-path stacks/s1_vh_stack_2025_50m.tif
   ```

2. **Generate predictions**:
   ```bash
   python predict.py --period 15 --tif-path stacks/s1_vh_stack_2025_50m.tif
   ```

3. **Batch predictions**:
   ```bash
   ./run_predictions.sh
   ```

For detailed training and prediction workflows, see:
- `COMPLETE_WORKFLOW.md` - End-to-end workflow
- `QUICK_REFERENCE.md` - Command cheat sheet
- `MULTI_RESOLUTION_GUIDE.md` - Detailed resolution comparison

---

**Last Updated:** 2025-10-28
