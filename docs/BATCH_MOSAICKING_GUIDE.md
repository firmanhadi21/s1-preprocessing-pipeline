# Batch Mosaicking Guide

## Overview

The batch mosaicking scripts automate the process of mosaicking multiple Sentinel-1 scenes for each period (1-56) using OTB Mosaic with feathering and harmonization. This creates seamless, radiometrically balanced mosaics for each period.

## Why Mosaic?

SAR data from overlapping swaths often have:
- **Visible seams** at overlap boundaries
- **Radiometric differences** between adjacent tracks
- **Different acquisition geometries**

OTB Mosaic solves these issues by:
- ✅ **Feathering**: Smooth blending at overlaps
- ✅ **Harmonization**: Radiometric balancing using RMSE
- ✅ **Seamless output**: Single consistent image per period

## Available Scripts

### 1. `batch_mosaic_periods.py` ⭐ **RECOMMENDED**

Flexible Python script with full control over mosaicking parameters.

**Features:**
- ✅ Process all periods or specific ranges
- ✅ Configurable OTB parameters
- ✅ Different spacing for different resolutions
- ✅ Progress tracking and timing
- ✅ Overwrite protection
- ✅ Continue on error option

**Basic Usage:**
```bash
# Mosaic all periods (1-56) at 20m resolution
python batch_mosaic_periods.py

# Mosaic specific periods
python batch_mosaic_periods.py --periods 1-10

# Mosaic 2024 only
python batch_mosaic_periods.py --periods 1-31

# Mosaic 2025 only
python batch_mosaic_periods.py --periods 32-56
```

**Advanced Usage:**
```bash
# 50m resolution mosaics (different spacing)
python batch_mosaic_periods.py \
  --periods 1-56 \
  --input-base workspace/preprocessed_50m \
  --output-dir workspace/mosaics_50m \
  --spacing-x 0.00044915764206 \
  --spacing-y 0.00044915764206

# 10m resolution mosaics
python batch_mosaic_periods.py \
  --periods 1-31 \
  --input-base workspace/preprocessed_10m \
  --output-dir workspace/mosaics_10m \
  --spacing-x 0.000089831528412 \
  --spacing-y 0.000089831528412

# Overwrite existing mosaics
python batch_mosaic_periods.py --periods 1-56 --overwrite

# Continue even if some fail
python batch_mosaic_periods.py --periods 1-56 --continue-on-error
```

**All Options:**
```bash
python batch_mosaic_periods.py --help
```

### 2. `batch_mosaic_all_periods.sh`

Simple bash script for mosaicking all periods with default settings.

**Usage:**
```bash
./batch_mosaic_all_periods.sh
```

**When to use:**
- Quick mosaicking of all periods
- Default 20m resolution
- No customization needed

## Pixel Spacing by Resolution

The pixel spacing must match your preprocessing resolution:

| Resolution | Spacing (degrees) | Approximate meters at equator |
|------------|-------------------|-------------------------------|
| 10m | 0.000089831528412 | ~10m |
| 20m | 0.000179663056824 | ~20m |
| 50m | 0.00044915764206 | ~50m |
| 100m | 0.00089831528412 | ~100m |

**Important:** Always use the correct spacing for your resolution!

## Directory Structure

### Input Structure (from preprocessing)
```
workspace/preprocessed_20m/
├── p1/
│   ├── S1A_..._VH_20m.tif
│   ├── S1A_..._VH_20m.tif
│   └── ...
├── p2/
│   ├── S1A_..._VH_20m.tif
│   └── ...
└── p56/
    └── ...
```

### Output Structure (mosaics)
```
workspace/mosaics_20m/
├── period_01_mosaic.tif
├── period_02_mosaic.tif
├── period_03_mosaic.tif
├── ...
└── period_56_mosaic.tif
```

**Note:** Output filenames use zero-padded period numbers (01, 02, ..., 56).

## OTB Mosaic Parameters

The scripts use these default OTB Mosaic parameters:

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `-comp.feather` | `large` | Strong feathering for smooth blending |
| `-harmo.method` | `band` | Band-wise harmonization |
| `-harmo.cost` | `rmse` | RMSE-based cost function |
| `-interpolator` | `nn` | Nearest neighbor (preserves SAR values) |
| `-distancemap.sr` | `10` | Distance map sampling ratio |
| `-nodata` | `0` | No-data value |
| `-output.spacingx/y` | resolution-dependent | Pixel size in degrees |

You can customize these with the Python script's options.

## Common Workflows

### Workflow 1: Mosaic After Preprocessing

```bash
# Step 1: Batch preprocessing (if not done)
python batch_preprocess_periods.py --periods 1-56 --resolution 20

# Step 2: Batch mosaicking
python batch_mosaic_periods.py --periods 1-56
```

### Workflow 2: Mosaic by Year

```bash
# Mosaic 2024 periods
python batch_mosaic_periods.py --periods 1-31

# Mosaic 2025 periods
python batch_mosaic_periods.py --periods 32-56
```

### Workflow 3: Mosaic Different Resolutions

```bash
# 20m mosaics
python batch_mosaic_periods.py \
  --periods 1-56 \
  --input-base workspace/preprocessed_20m \
  --output-dir workspace/mosaics_20m \
  --spacing-x 0.000179663056824 \
  --spacing-y 0.000179663056824

# 50m mosaics
python batch_mosaic_periods.py \
  --periods 1-56 \
  --input-base workspace/preprocessed_50m \
  --output-dir workspace/mosaics_50m \
  --spacing-x 0.00044915764206 \
  --spacing-y 0.00044915764206
```

### Workflow 4: Reprocess Failed Mosaics

```bash
# After initial run, reprocess only failed periods
python batch_mosaic_periods.py \
  --periods 15,23,45 \
  --overwrite
```

### Workflow 5: Complete Pipeline (Preprocessing → Mosaicking)

```bash
# 1. Batch preprocessing
python batch_preprocess_periods.py \
  --periods 1-56 \
  --resolution 20 \
  --workers 8

# 2. Batch mosaicking
python batch_mosaic_periods.py \
  --periods 1-56

# 3. Continue with temporal compositing (optional, if needed)
# Note: For period-based analysis, you can use mosaics directly
# For 12-day compositing, use s1_composite_12day.py
```

## Processing Time Estimates

Mosaicking time depends on:
- Number of scenes per period
- Input resolution
- Feathering method
- System performance

### Typical Times per Period

| Scenes/Period | Resolution | Time/Period | Total (56 periods) |
|---------------|------------|-------------|-------------------|
| 5-10 | 20m | 2-5 min | 2-5 hours |
| 10-15 | 20m | 5-10 min | 5-9 hours |
| 15-30 | 20m | 10-20 min | 9-19 hours |
| 5-10 | 50m | 1-2 min | 1-2 hours |
| 10-15 | 50m | 2-5 min | 2-5 hours |

*Times are approximate and vary by system

## Storage Requirements

### Mosaic Size per Period (approximate)

| Resolution | Scenes/Period | Mosaic Size |
|------------|---------------|-------------|
| 10m | 10-15 | 8-12 GB |
| 20m | 10-15 | 2-3 GB |
| 50m | 10-15 | 300-500 MB |
| 100m | 10-15 | 75-125 MB |

### Total Storage (all 56 periods)

| Resolution | Total Storage |
|------------|---------------|
| 10m | ~450-670 GB |
| 20m | ~110-170 GB |
| 50m | ~17-28 GB |
| 100m | ~4-7 GB |

## Error Handling

### Automatic Skipping

The scripts automatically skip periods when:
- Input directory doesn't exist
- No .tif files found in input directory
- Output already exists (unless `--overwrite` is used)

### Continue on Error

Use `--continue-on-error` to process all periods even if some fail:

```bash
python batch_mosaic_periods.py \
  --periods 1-56 \
  --continue-on-error
```

### Failed Period Summary

At the end, you'll see which periods failed:

```
Failed periods: 15, 23, 45
```

Reprocess only failed periods:

```bash
python batch_mosaic_periods.py --periods 15,23,45 --overwrite
```

## Troubleshooting

### Issue: OTB Mosaic not found

**Error:**
```
ERROR: otbcli_Mosaic not found. Please install Orfeo Toolbox (OTB).
```

**Solution:**
Install OTB or ensure it's in your PATH:
```bash
# Check if OTB is installed
which otbcli_Mosaic

# If not in PATH, add it (example for macOS/Linux)
export PATH="/path/to/otb/bin:$PATH"
```

### Issue: "Dimensions are not defined"

**Error:**
```
itk::ERROR: GDALImageIO: Dimensions are not defined.
```

**Cause:** Missing or incorrect pixel spacing, or input images have inconsistent projections.

**Solution:**
1. Check that all input images have the same projection
2. Verify pixel spacing matches your resolution:
   ```bash
   # For 20m
   --spacing-x 0.000179663056824 --spacing-y 0.000179663056824
   ```
3. Use `gdalinfo` to check input image properties

### Issue: "A spacing of 0 is not allowed"

**Error:**
```
itk::ERROR: VectorImage: A spacing of 0 is not allowed
```

**Solution:**
Don't use 0 for spacing. Use the correct value for your resolution (see table above).

### Issue: Visible seams in output

**Symptoms:** Mosaic has visible brightness differences or seams.

**Cause:** Harmonization or feathering not working properly.

**Solutions:**
1. Ensure `-harmo.method band` and `-harmo.cost rmse` are set
2. Try different feathering:
   ```bash
   --feather large  # strongest blending (default)
   --feather slim   # moderate blending
   ```
3. Check that all input images are properly calibrated

### Issue: Out of memory

**Symptoms:** Process killed or system unresponsive.

**Solutions:**
1. Process in smaller batches:
   ```bash
   python batch_mosaic_periods.py --periods 1-10
   python batch_mosaic_periods.py --periods 11-20
   # etc.
   ```
2. Close other applications
3. Use coarser resolution (e.g., 50m instead of 20m)

### Issue: Very slow processing

**Solutions:**
1. Reduce distance map sampling:
   ```bash
   --distance-sr 20  # instead of 10
   ```
2. Use faster interpolation:
   ```bash
   --interpolator nn  # fastest (default)
   ```
3. Process fewer scenes per period (if possible)

## Quality Check

After mosaicking, verify outputs:

### 1. Visual Inspection

Open mosaics in QGIS and check:
- No visible seams between swaths
- Consistent radiometry across the image
- No artifacts at overlap areas
- Proper georeferencing

### 2. File Size Check

```bash
# Check all mosaic sizes
ls -lh workspace/mosaics_20m/*.tif

# Typical sizes for 20m:
# Small areas: 500 MB - 1 GB
# Medium areas: 1 GB - 3 GB
# Large areas: 3 GB - 10 GB
```

### 3. Metadata Check

```bash
# Check mosaic metadata
gdalinfo workspace/mosaics_20m/period_01_mosaic.tif

# Verify:
# - Pixel Size matches expected spacing
# - Coordinate System is correct (EPSG:4326)
# - Data type (usually Float32)
```

## Integration with Full Pipeline

### Complete Workflow (Preprocessing → Mosaic → Analysis)

```bash
# Step 1: Batch preprocessing
python batch_preprocess_periods.py \
  --periods 1-56 \
  --resolution 20 \
  --workers 8

# Step 2: Batch mosaicking
python batch_mosaic_periods.py \
  --periods 1-56

# Step 3: Use mosaics for analysis
# Option A: Direct analysis per period
for period in {1..56}; do
  python predict_optimized_filtered.py \
    --period $period \
    --input workspace/mosaics_20m/period_$(printf '%02d' $period)_mosaic.tif \
    --model-path model_files/rice_stage_model.keras \
    --output-dir predictions/p${period}
done

# Option B: Stack all mosaics into multi-temporal cube
python stack_mosaics.py \
  --input-dir workspace/mosaics_20m \
  --output s1_vh_stack_2024_2025_56periods_20m.tif

# Then train and predict as usual
python train_with_filtering.py \
  --tif-path s1_vh_stack_2024_2025_56periods_20m.tif \
  --csv-path training_points.csv \
  --output-dir model_files
```

## Best Practices

1. **Always mosaic before temporal analysis**
   - Mosaicking creates consistent spatial coverage
   - Eliminates seams and radiometric differences
   - Simplifies downstream processing

2. **Use consistent spacing**
   - Match spacing to preprocessing resolution
   - Don't mix resolutions in same analysis

3. **Keep feathering and harmonization enabled**
   - Essential for seamless mosaics
   - Only disable for debugging

4. **Process by year for better organization**
   ```bash
   python batch_mosaic_periods.py --periods 1-31   # 2024
   python batch_mosaic_periods.py --periods 32-56  # 2025
   ```

5. **Check first few mosaics before processing all**
   ```bash
   # Test with first 3 periods
   python batch_mosaic_periods.py --periods 1-3
   
   # Check quality in QGIS
   # Then process all if satisfied
   python batch_mosaic_periods.py --periods 1-56
   ```

6. **Use `--overwrite` only when necessary**
   - Protects against accidental re-processing
   - Saves time by skipping existing mosaics

7. **Save processing logs**
   ```bash
   python batch_mosaic_periods.py --periods 1-56 2>&1 | tee mosaic_log.txt
   ```

## Quick Reference

### Mosaic All Periods (20m)
```bash
python batch_mosaic_periods.py
```

### Mosaic 2024 Only
```bash
python batch_mosaic_periods.py --periods 1-31
```

### Mosaic 2025 Only
```bash
python batch_mosaic_periods.py --periods 32-56
```

### Mosaic 50m Resolution
```bash
python batch_mosaic_periods.py \
  --input-base workspace/preprocessed_50m \
  --output-dir workspace/mosaics_50m \
  --spacing-x 0.00044915764206 \
  --spacing-y 0.00044915764206
```

### Reprocess Failed Periods
```bash
python batch_mosaic_periods.py --periods 5,12,23 --overwrite
```

### Help
```bash
python batch_mosaic_periods.py --help
```

---

**Version:** 1.0  
**Last Updated:** November 2025  
**See Also:** BATCH_PROCESSING_GUIDE.md, MULTI_RESOLUTION_GUIDE.md
