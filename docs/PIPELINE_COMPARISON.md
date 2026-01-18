# Pipeline Comparison Guide

## Which Pipeline Should I Use?

This project includes **4 different pipelines** for processing Sentinel-1 data. Choose based on your use case:

## Quick Recommendation

| Your Goal | Use This Pipeline | Documentation |
|-----------|-------------------|---------------|
| **Full annual stack for rice mapping** | `s1_period_pipeline.py` | `PERIOD_PIPELINE_GUIDE.md` |
| Single date mosaic | `s1_pipeline_auto.py` | `AUTOMATED_PIPELINE_GUIDE.md` |
| Multi-date mosaics (testing) | `s1_multiscene_pipeline.py` | See script header |
| Very large areas (>100km) | `s1_java_pipeline.py` | See script header |

## Detailed Comparison

### 1. Period-Based Pipeline (RECOMMENDED FOR RICE MAPPING)

**Script:** `s1_period_pipeline.py`
**Config:** `pipeline_config_period.yaml`
**Quick Start:** `./run_period_pipeline.sh 2024`

**Purpose:**
- Process all 31 12-day periods for a full year
- Output: Single 31-band GeoTIFF ready for training/prediction

**Use When:**
- ✅ You need a complete annual stack for rice growth stage mapping
- ✅ You want automatic period grouping (no manual date calculations)
- ✅ You're processing for training or systematic prediction

**Features:**
- Downloads scenes for each of 31 periods automatically
- Mosaics multiple scenes within each period
- Histogram matching for seamless mosaics
- Stacks all periods into final 31-band GeoTIFF
- Handles missing periods gracefully

**Example:**
```bash
# Full year processing
python s1_period_pipeline.py --config my_config.yaml --year 2024 --run-all

# Output: S1_VH_stack_2024_31bands.tif (ready for training!)
```

**Pros:**
- ✅ Complete automation for annual processing
- ✅ Perfect alignment with 12-day period system
- ✅ Direct integration with training/prediction
- ✅ Can process specific periods only

**Cons:**
- ⚠️ Requires full year (or accepts gaps)
- ⚠️ Can be time-consuming for large areas (16-48 hours)

---

### 2. Multi-Scene Pipeline

**Script:** `s1_multiscene_pipeline.py`
**Config:** `pipeline_config_semarang_demak.yaml`

**Purpose:**
- Process multiple scenes for a specific date range
- Group scenes by acquisition date
- Create mosaics for each date

**Use When:**
- ✅ Testing mosaicking for a specific region
- ✅ You need mosaics for specific dates (not full year)
- ✅ Validating preprocessing parameters

**Features:**
- Groups scenes by acquisition date
- Histogram matching within each date
- Multiple mosaics (one per date)

**Example:**
```bash
# Process one month
python s1_multiscene_pipeline.py \
    --config pipeline_config_semarang_demak.yaml \
    --run-all
```

**Pros:**
- ✅ Good for testing
- ✅ Date-based organization
- ✅ Flexible date ranges

**Cons:**
- ⚠️ Requires manual period mapping
- ⚠️ Not optimized for annual stacks
- ⚠️ Multiple output files

---

### 3. Java Island Pipeline (Sequential Mosaicking)

**Script:** `s1_java_pipeline.py`
**Config:** `pipeline_config_java.yaml`

**Purpose:**
- Large-area processing with sequential mosaicking
- Optimized for regions requiring many scenes (e.g., Java Island)
- West-to-east or east-to-west mosaicking

**Use When:**
- ✅ Processing very large areas (>100 km extent)
- ✅ Region requires 5+ scenes to cover
- ✅ Need consistent radiometry across large mosaic

**Features:**
- Sequential mosaicking with growing reference
- Direction control (west-to-east or east-to-west)
- Overlap-based histogram matching
- Single large mosaic output

**Example:**
```bash
# Process Java Island
python s1_java_pipeline.py \
    --config pipeline_config_java.yaml \
    --run-all \
    --direction west_to_east
```

**Pros:**
- ✅ Handles very large areas
- ✅ Better radiometric consistency for large mosaics
- ✅ Direction control

**Cons:**
- ⚠️ Single mosaic output (not period-based)
- ⚠️ Slower (sequential processing)
- ⚠️ Requires manual period integration

---

### 4. Automated Pipeline (Single Date Range)

**Script:** `s1_pipeline_auto.py`
**Config:** `pipeline_config.yaml`

**Purpose:**
- General-purpose automated pipeline
- Process a specific date range
- Single mosaic output

**Use When:**
- ✅ Quick processing for specific dates
- ✅ Single-mosaic output needed
- ✅ Testing preprocessing workflow

**Features:**
- Download → Preprocess → Mosaic in one command
- Simple configuration
- Single output mosaic

**Example:**
```bash
# Process specific date range
python s1_pipeline_auto.py --config my_config.yaml --run-all
```

**Pros:**
- ✅ Simple and straightforward
- ✅ Good for single-date processing
- ✅ Minimal configuration

**Cons:**
- ⚠️ Not period-aware
- ⚠️ Requires manual period integration
- ⚠️ Single mosaic only

---

## Feature Matrix

| Feature | Period Pipeline | Multi-Scene | Java Island | Automated |
|---------|----------------|-------------|-------------|-----------|
| **Period-based processing** | ✅ Yes | ❌ No | ❌ No | ❌ No |
| **Automatic period grouping** | ✅ Yes | ❌ No | ❌ No | ❌ No |
| **Multi-scene mosaicking** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **Histogram matching** | ✅ Yes | ✅ Yes | ✅ Yes | ⚠️ Limited |
| **31-band stack output** | ✅ Yes | ❌ No | ❌ No | ❌ No |
| **Large area support** | ✅ Yes | ⚠️ Medium | ✅✅ Best | ⚠️ Medium |
| **Sequential mosaicking** | ❌ No | ❌ No | ✅ Yes | ❌ No |
| **Training-ready output** | ✅✅ Best | ⚠️ Manual | ⚠️ Manual | ⚠️ Manual |
| **Processing time** | Slow (16-48h) | Fast (2-6h) | Slow (12-36h) | Fast (1-4h) |
| **Complexity** | Medium | Medium | High | Low |

---

## Common Workflows

### Workflow 1: Annual Rice Mapping (RECOMMENDED)

**Goal:** Create training data and predictions for a full year

```bash
# Use period-based pipeline
python s1_period_pipeline.py \
    --config pipeline_config_period.yaml \
    --year 2024 \
    --run-all

# Output: S1_VH_stack_2024_31bands.tif

# Train model
python train.py

# Predict
python predict.py --period 15
```

---

### Workflow 2: Multi-Year Comparison

**Goal:** Process multiple years for trend analysis

```bash
# Year 2023
python s1_period_pipeline.py --config cfg.yaml --year 2023 --run-all

# Year 2024
python s1_period_pipeline.py --config cfg.yaml --year 2024 --run-all

# Compare annual stacks
# Each year gets its own 31-band stack in separate directories
```

---

### Workflow 3: Quick Test for Specific Region/Date

**Goal:** Test preprocessing for a small area and date range

```bash
# Use automated pipeline for quick test
python s1_pipeline_auto.py --config test_config.yaml --run-all

# Or use multi-scene for specific month
python s1_multiscene_pipeline.py --config test_config.yaml --run-all
```

---

### Workflow 4: Large Island/Province Coverage

**Goal:** Create single large mosaic for very large area

```bash
# Use Java Island pipeline with sequential mosaicking
python s1_java_pipeline.py \
    --config pipeline_config_java.yaml \
    --run-all \
    --direction west_to_east

# Then manually integrate into period system if needed
```

---

## Configuration Files

Each pipeline uses a YAML configuration file:

| Pipeline | Default Config | Purpose |
|----------|---------------|---------|
| Period-based | `pipeline_config_period.yaml` | Full annual processing |
| Multi-scene | `pipeline_config_semarang_demak.yaml` | Regional testing |
| Java Island | `pipeline_config_java.yaml` | Large area processing |
| Automated | `pipeline_config.yaml` | Single date range |
| Test | `pipeline_config_test.yaml` | Small area testing |

**Create your own:**
```bash
# Copy appropriate template
cp pipeline_config_period.yaml my_region.yaml

# Edit AOI and parameters
nano my_region.yaml

# Run pipeline
python s1_period_pipeline.py --config my_region.yaml --year 2024 --run-all
```

---

## Performance Comparison

### Small Area (10km × 10km, ~5 scenes/period)

| Pipeline | Time | Disk Space | Output |
|----------|------|------------|--------|
| Period (31 periods) | 16-24 hours | ~80 GB | 31-band stack (2 GB) |
| Multi-scene (1 month) | 2-4 hours | ~15 GB | Multiple mosaics |
| Automated (1 date) | 1-2 hours | ~5 GB | Single mosaic |

### Large Area (100km × 100km, ~20 scenes/period)

| Pipeline | Time | Disk Space | Output |
|----------|------|------------|--------|
| Period (31 periods) | 36-48 hours | ~350 GB | 31-band stack (10 GB) |
| Java Island | 24-36 hours | ~200 GB | Single large mosaic |
| Multi-scene (1 month) | 4-8 hours | ~60 GB | Multiple mosaics |

---

## Migration Guide

### From Manual GEE Processing → Period Pipeline

**Before (manual):**
1. Export periods 1-31 from GEE
2. Download 31 separate files
3. Stack manually with GDAL

**After (automated):**
```bash
python s1_period_pipeline.py --config cfg.yaml --year 2024 --run-all
# Done! 31-band stack created automatically
```

### From Single Date Pipeline → Period Pipeline

**Before:**
```bash
# Had to run 31 times manually
for period in {1..31}; do
    # Calculate dates
    # Update config
    # Run pipeline
    # Stack outputs
done
```

**After:**
```bash
python s1_period_pipeline.py --config cfg.yaml --year 2024 --run-all
# Automatically processes all 31 periods
```

---

## Summary Recommendations

| You Want To... | Use This |
|----------------|----------|
| **Train rice mapping model** | `s1_period_pipeline.py` ⭐ |
| **Make annual predictions** | `s1_period_pipeline.py` ⭐ |
| **Process specific periods** | `s1_period_pipeline.py --periods "1-10"` |
| **Test small area/date** | `s1_pipeline_auto.py` |
| **Process very large region** | `s1_java_pipeline.py` |
| **Experiment with mosaicking** | `s1_multiscene_pipeline.py` |

**⭐ = Recommended for most users**

---

## Support

For detailed documentation:
- **Period Pipeline**: `PERIOD_PIPELINE_GUIDE.md`
- **Automated Pipeline**: `AUTOMATED_PIPELINE_GUIDE.md`
- **Complete Workflow**: `COMPLETE_WORKFLOW.md`
- **Quick Reference**: `QUICK_REFERENCE.md`
