# Period-Based Pipeline Guide

## Overview

The **period-based pipeline** (`s1_period_pipeline.py`) is a complete automated solution for processing Sentinel-1 data organized by **12-day periods** for rice growth stage mapping.

Instead of processing scenes by acquisition date, this pipeline:
1. **Groups data by 12-day period** (31 periods per year)
2. **Downloads scenes for each period** automatically
3. **Mosaics multiple scenes within each period** (with histogram matching)
4. **Stacks all 31 periods into a single multi-band GeoTIFF** ready for training/prediction

## Why Period-Based Processing?

Rice growth stage mapping uses a **backward-looking time series approach** where the model needs **7 consecutive 12-day periods** to make a prediction. The final output must be a **31-band annual stack** where:
- Band 1 = Period 1 (Jan 1-12)
- Band 2 = Period 2 (Jan 13-24)
- ...
- Band 31 = Period 31 (Dec 27-31)

Traditional date-based processing requires manual grouping of scenes into periods. The period-based pipeline **automates this entire workflow**.

## Quick Start

### 1. Install Dependencies

```bash
# Python packages
pip install asf-search shapely pyyaml rasterio numpy

# SNAP (for preprocessing)
# Download from: https://step.esa.int/main/download/snap-download/
```

### 2. Create Configuration

Copy and edit the period configuration:

```bash
cp pipeline_config_period.yaml my_region_config.yaml
nano my_region_config.yaml
```

**Key settings to configure:**
- `aoi_bbox`: Your region of interest [west, south, east, north]
- `work_dir`: Where to store all data
- `snap_gpt_path`: Path to SNAP GPT executable

### 3. Run Full Pipeline for a Year

```bash
# Process all 31 periods for 2024
python s1_period_pipeline.py \
    --config my_region_config.yaml \
    --year 2024 \
    --run-all
```

**Expected output:**
```
workspace_period/year_2024/
├── downloads/              # Raw Sentinel-1 ZIP files
├── preprocessed/           # SNAP processed .dim files
├── geotiff/                # Individual scene GeoTIFFs
├── period_mosaics/         # Mosaics for each period
│   ├── period_01_VH.tif
│   ├── period_02_VH.tif
│   └── ...
└── final_stack/
    └── S1_VH_stack_2024_31bands.tif  ← Final output for training!
```

## Usage Examples

### Process Specific Periods Only

```bash
# Only process periods 1-10
python s1_period_pipeline.py \
    --config my_region_config.yaml \
    --year 2024 \
    --periods "1-10" \
    --run-all

# Process specific periods (e.g., rice growing season)
python s1_period_pipeline.py \
    --config my_region_config.yaml \
    --year 2024 \
    --periods "5-25" \
    --run-all

# Process multiple ranges and individual periods
python s1_period_pipeline.py \
    --config my_region_config.yaml \
    --year 2024 \
    --periods "1-5,10,15-20,30" \
    --run-all
```

### Step-by-Step Execution

For large areas or to monitor progress, run each step separately:

```bash
# Step 1: Download only
python s1_period_pipeline.py \
    --config my_region_config.yaml \
    --year 2024 \
    --download-only

# Step 2: Preprocess downloaded scenes
python s1_period_pipeline.py \
    --config my_region_config.yaml \
    --year 2024 \
    --preprocess-only

# Step 3: Convert to GeoTIFF
python s1_period_pipeline.py \
    --config my_region_config.yaml \
    --year 2024 \
    --convert-only

# Step 4: Mosaic by period
python s1_period_pipeline.py \
    --config my_region_config.yaml \
    --year 2024 \
    --mosaic-only

# Step 5: Stack into final 31-band GeoTIFF
python s1_period_pipeline.py \
    --config my_region_config.yaml \
    --year 2024 \
    --stack-only
```

### Resume Interrupted Pipeline

If the pipeline was interrupted, skip completed steps:

```bash
# Resume from mosaicking (download/preprocess/convert already done)
python s1_period_pipeline.py \
    --config my_region_config.yaml \
    --year 2024 \
    --run-all \
    --skip-download \
    --skip-preprocess \
    --skip-convert
```

## Pipeline Steps Explained

### Step 1: Download by Period

For each 12-day period, the pipeline:
- Calculates the period's date range (e.g., Period 15 = May 17-28)
- Searches ASF for Sentinel-1 GRD scenes intersecting your AOI
- Downloads all matching scenes
- Organizes downloads by period

**Example:** Period 15 might have 3 scenes covering different parts of your region.

### Step 2: Preprocess with SNAP GPT

Each downloaded scene is preprocessed using `sen1_preprocessing-gpt.xml`:
- Apply Orbit File
- Thermal Noise Removal
- Radiometric Calibration (Gamma0)
- Terrain Correction
- Speckle Filtering (Gamma MAP 5x5)
- Conversion to dB

**Output:** `.dim` files with VH backscatter in dB

### Step 3: Convert to GeoTIFF

Extracts the `Gamma0_VH_db` band from each `.dim` file and saves as compressed GeoTIFF.

### Step 4: Mosaic by Period

For each period:
- **Single scene:** Simply copies to period mosaic
- **Multiple scenes:**
  - Applies histogram matching for radiometric consistency
  - Merges scenes using rasterio
  - Outputs one mosaic per period

**Histogram matching** ensures seamless transitions between overlapping scenes by adjusting their radiometry to match a reference scene.

### Step 5: Stack All Periods

Creates the final **31-band GeoTIFF**:
- Reprojects all period mosaics to a common grid
- Stacks them in order (Band 1 = Period 1, ..., Band 31 = Period 31)
- Fills missing periods with nodata values
- Compresses with LZW

**Output:** `S1_VH_stack_2024_31bands.tif` - ready for training and prediction!

## Configuration Options

### AOI Definition

```yaml
data_acquisition:
  # Bounding box: [west, south, east, north] in WGS84
  aoi_bbox: [110.0, -7.5, 111.0, -6.5]
```

**Tips:**
- Use small test areas first (~10km × 10km)
- For large areas (100+ km), increase SNAP cache size
- Check coverage at https://search.asf.alaska.edu/

### Histogram Matching

```yaml
mosaicking:
  histogram_matching: true  # Recommended
  reference_scene: center   # Options: first, largest, center
```

**When to use:**
- **Enable** for multi-scene mosaics (reduces seam lines)
- **Disable** for single-scene periods or debugging

### SNAP Processing

```yaml
preprocessing:
  snap_gpt_path: /path/to/snap/bin/gpt
  cache_size: '16G'  # Increase for large scenes
```

**Memory recommendations:**
- Small scenes (<1GB): 8G cache
- Medium scenes (1-3GB): 16G cache
- Large scenes (>3GB): 32G cache

## Integration with Training/Prediction

### After Pipeline Completion

```bash
# Update config.py to use the new stack
nano config.py
```

```python
# In config.py
PREDICTION_GEOTIFF = '/path/to/workspace_period/year_2024/final_stack/S1_VH_stack_2024_31bands.tif'
TRAINING_GEOTIFF = PREDICTION_GEOTIFF  # Same file for training
```

### Train Model

```bash
# Train on the complete annual stack
python train.py

# Or use optimized/balanced training
python balanced_train_lstm.py --augment
```

### Make Predictions

```bash
# Predict for period 15 (uses bands 15, 14, 13, 12, 11, 10, 9)
python predict.py --period 15

# Batch predictions for all valid periods (7-31)
./run_predictions.sh
```

## Multi-Year Processing

Process multiple years and stack them:

```bash
# Year 2023
python s1_period_pipeline.py \
    --config my_region_config.yaml \
    --year 2023 \
    --run-all

# Year 2024
python s1_period_pipeline.py \
    --config my_region_config.yaml \
    --year 2024 \
    --run-all

# Stack years together (if needed)
# Each year gets its own 31-band stack
```

## Troubleshooting

### No scenes found for some periods

**Cause:** Sentinel-1 has a 12-day repeat cycle, but coverage gaps can occur.

**Solution:**
- Check coverage at https://search.asf.alaska.edu/
- Accept that some periods may be missing
- The pipeline will fill missing periods with nodata

### Download failures

**Cause:** Network issues, ASF server busy

**Solution:**
- Re-run with `--download-only` to retry
- The pipeline skips already-downloaded files
- Check ASF status: https://asf.alaska.edu/

### SNAP preprocessing timeout

**Cause:** Large scenes or insufficient memory

**Solution:**
- Increase `cache_size` in config (e.g., `32G`)
- Increase timeout in code (default: 3600s = 1 hour)
- Process fewer scenes in parallel

### Memory errors during mosaicking

**Cause:** Very large mosaics

**Solution:**
- Process smaller AOI
- Use `BIGTIFF='YES'` (already enabled in code)
- Close other applications

### Misaligned period mosaics

**Cause:** Different projections or resolutions

**Solution:**
- The stacking step (Step 5) automatically reprojects to common grid
- Check reference period mosaic has valid data

## Performance Optimization

### Parallel Processing

The pipeline processes scenes **sequentially** by default. For faster processing:

1. **Download all periods first:**
   ```bash
   python s1_period_pipeline.py --config cfg.yaml --year 2024 --download-only
   ```

2. **Preprocess in parallel manually:**
   ```bash
   # Split scenes into batches and run multiple SNAP instances
   # (Advanced - requires custom scripting)
   ```

### Disk Space Management

Estimate disk space needed:
- **Raw downloads:** ~1 GB per scene
- **Preprocessed:** ~2 GB per scene
- **GeoTIFFs:** ~0.5 GB per scene
- **Period mosaics:** ~0.5-2 GB per period
- **Final stack:** ~1-5 GB (31 bands)

**Total for 100 scenes:** ~350 GB

**Cleanup strategy:**
```bash
# After successful completion, you can delete:
rm -rf downloads/        # Keep preprocessed instead
rm -rf preprocessed/     # Keep GeoTIFFs instead
rm -rf geotiff/          # Keep only period_mosaics and final_stack

# Essential outputs:
# - period_mosaics/     (for verification)
# - final_stack/        (for training/prediction)
```

## Comparison with Other Pipelines

| Pipeline | Use Case | Output |
|----------|----------|--------|
| `s1_pipeline_auto.py` | Single date range | Single mosaic |
| `s1_multiscene_pipeline.py` | Multi-scene, date-based | Mosaics by date |
| `s1_java_pipeline.py` | Large area, sequential | Single large mosaic |
| **`s1_period_pipeline.py`** | **Full year, period-based** | **31-band annual stack** |

**Choose period-based pipeline when:**
- ✅ You need a full annual stack for rice mapping
- ✅ You want automatic period grouping
- ✅ You're processing multiple periods systematically

## Example Workflow

Complete workflow from scratch:

```bash
# 1. Setup
cd /home/unika_sianturi/work/rice-growth-stage-mapping
cp pipeline_config_period.yaml my_config.yaml
nano my_config.yaml  # Edit AOI and paths

# 2. Run period-based pipeline
python s1_period_pipeline.py \
    --config my_config.yaml \
    --year 2024 \
    --run-all

# Expected time: 16-48 hours (depends on area size and # of scenes)

# 3. Verify output
ls -lh workspace_period/year_2024/final_stack/
# Should show: S1_VH_stack_2024_31bands.tif

# 4. Update training config
nano config.py
# Set PREDICTION_GEOTIFF to the stack path

# 5. Train model
python balanced_train_lstm.py --augment

# 6. Make predictions
python predict.py --period 15
```

## Next Steps

After successful pipeline execution:

1. **Quality Check:**
   ```bash
   # Visualize period mosaics
   for i in {1..31}; do
       gdalinfo workspace_period/year_2024/period_mosaics/period_$(printf "%02d" $i)_VH.tif
   done
   ```

2. **Training:**
   - See `COMPLETE_WORKFLOW.md` for training guide
   - Use `balanced_train_lstm.py` for best accuracy

3. **Prediction:**
   - See `QUICK_REFERENCE.md` for prediction commands
   - Use `predict_optimized.py` for faster predictions

4. **Multi-Year Analysis:**
   - Run pipeline for multiple years
   - Compare inter-annual variability
   - Build multi-year training datasets

## Support

For issues or questions:
- Check logs in terminal output
- Review `COMPLETE_WORKFLOW.md` for context
- See `AUTOMATED_PIPELINE_GUIDE.md` for SNAP setup
- Check `12DAY_PERIOD_SYSTEM.md` for period details
