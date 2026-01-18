# Batch Processing Guide

## Overview

The batch processing scripts automate preprocessing of Sentinel-1 data across multiple periods (1-56), covering both 2024 and 2025. This eliminates the need to manually run preprocessing for each period individually.

## Available Scripts

### 1. `batch_preprocess_periods.py` ⭐ **RECOMMENDED**

The most flexible option with full control over which periods to process.

**Features:**
- ✅ Process all periods or specific ranges
- ✅ Flexible period selection (e.g., "1-10", "1-5,10,15-20")
- ✅ Custom resolution and worker settings
- ✅ Progress tracking and timing
- ✅ Summary statistics
- ✅ Continue on error option
- ✅ Checks for missing data
- ✅ Automatic directory creation

**Basic Usage:**
```bash
# Process all periods (1-56)
python batch_preprocess_periods.py

# Process specific periods
python batch_preprocess_periods.py --periods 1-10

# Process 2024 only
python batch_preprocess_periods.py --periods 1-31

# Process 2025 only
python batch_preprocess_periods.py --periods 32-56
```

**Advanced Usage:**
```bash
# Custom resolution and workers
python batch_preprocess_periods.py \
  --periods 1-56 \
  --resolution 10 \
  --workers 16

# Custom paths
python batch_preprocess_periods.py \
  --periods 1-31 \
  --download-base data/downloads \
  --output-base data/preprocessed_20m

# Continue even if some periods fail
python batch_preprocess_periods.py \
  --periods 1-56 \
  --continue-on-error
```

**All Options:**
```bash
python batch_preprocess_periods.py --help
```

### 2. `batch_preprocess_all_periods.py`

Simple Python script that processes all periods 1-56 with default settings.

**Usage:**
```bash
python batch_preprocess_all_periods.py
```

**When to use:**
- Quick processing of all periods
- Don't need customization
- Want simple, no-configuration approach

### 3. `batch_preprocess_all_periods.sh`

Bash script version for shell scripting integration.

**Usage:**
```bash
./batch_preprocess_all_periods.sh
```

**When to use:**
- Integration with existing bash scripts
- Cron jobs or scheduled tasks
- Shell-based workflows

## Period Organization

### Period-to-Year Mapping

- **Periods 1-31**: 2024 (12-day periods)
- **Periods 32-56**: 2025 (12-day periods)

### Directory Structure

The batch scripts expect and create this structure:

```
workspace/
├── downloads/
│   ├── downloads_p1/      # Period 1 raw data
│   ├── downloads_p2/      # Period 2 raw data
│   ├── ...
│   └── downloads_p56/     # Period 56 raw data
└── preprocessed_20m/
    ├── p1/                # Period 1 processed
    ├── p2/                # Period 2 processed
    ├── ...
    └── p56/               # Period 56 processed
```

## Common Workflows

### Workflow 1: Process All Periods for First Time

```bash
# Process all periods at 20m resolution
python batch_preprocess_periods.py \
  --periods 1-56 \
  --resolution 20 \
  --workers 8 \
  --continue-on-error
```

**Expected output:**
```
====================================================================
BATCH PREPROCESSING CONFIGURATION
====================================================================
Script:         s1_preprocess_parallel_multiresolution.py
Download base:  workspace/downloads
Output base:    workspace/preprocessed_20m
Resolution:     20m
Workers:        8
Periods:        1-56 (56 total)
Continue on error: True
====================================================================

[1/56] Period 1
======================================================================
Processing Period 1 (Year: 2024)
Input:  workspace/downloads/downloads_p1
Output: workspace/preprocessed_20m/p1
Resolution: 20m | Workers: 8
======================================================================
Found 15 files to process
✓ Period 1 completed successfully in 450.2s

[2/56] Period 2
...

====================================================================
BATCH PROCESSING COMPLETE
====================================================================
Total time:     54321.5s (905.4 minutes)
Total periods:  56
Successful:     54
Skipped:        2
Failed:         0

Failed periods: 
====================================================================
```

### Workflow 2: Process by Year

```bash
# Process 2024 data first
python batch_preprocess_periods.py \
  --periods 1-31 \
  --resolution 20 \
  --workers 8

# Then process 2025 data
python batch_preprocess_periods.py \
  --periods 32-56 \
  --resolution 20 \
  --workers 8
```

### Workflow 3: Reprocess Failed Periods

```bash
# After initial run, reprocess only failed periods
python batch_preprocess_periods.py \
  --periods 15,23,45 \
  --resolution 20 \
  --workers 8
```

### Workflow 4: Process Specific Season

```bash
# Process only dry season periods (example: periods 1-5, 20-31)
python batch_preprocess_periods.py \
  --periods 1-5,20-31 \
  --resolution 20 \
  --workers 8
```

### Workflow 5: High-Resolution Processing

```bash
# Process all periods at 10m for detailed analysis
python batch_preprocess_periods.py \
  --periods 1-56 \
  --resolution 10 \
  --workers 4 \
  --continue-on-error

# This will take much longer (days to weeks)
```

## Resource Planning

### Processing Time Estimates

| Resolution | Workers | Time per Period | Total Time (56 periods) |
|------------|---------|-----------------|-------------------------|
| 10m | 4 | 2-3 hours | 112-168 hours (5-7 days) |
| 20m | 8 | 30-45 min | 28-42 hours (1-2 days) |
| 50m | 8 | 7-10 min | 6-9 hours |
| 100m | 8 | 2-3 min | 2-3 hours |

*Assumes ~15-30 scenes per period

### Storage Requirements

| Resolution | Per Period | Total (56 periods) |
|------------|-----------|-------------------|
| 10m | 750 GB | 42 TB |
| 20m | 180 GB | 10 TB |
| 50m | 30 GB | 1.7 TB |
| 100m | 7.5 GB | 420 GB |

### Memory Requirements

| Resolution | Workers | Recommended RAM |
|------------|---------|----------------|
| 10m | 4 | 1 TB |
| 20m | 8 | 1 TB |
| 50m | 8 | 512 GB |
| 100m | 8 | 256 GB |

## Error Handling

### Automatic Skipping

The batch scripts automatically skip periods when:
- Input directory doesn't exist
- Input directory is empty (no .zip or .SAFE files)

### Continue on Error

Use `--continue-on-error` to process all periods even if some fail:

```bash
python batch_preprocess_periods.py \
  --periods 1-56 \
  --continue-on-error
```

Without this flag, processing stops on the first failure.

### Failed Period Summary

At the end, you'll see which periods failed:

```
Failed periods: 15, 23, 45
```

You can then reprocess only these:

```bash
python batch_preprocess_periods.py --periods 15,23,45
```

## Monitoring Progress

### Real-time Monitoring

The script shows:
- Current period being processed
- Input/output directories
- Number of files found
- Processing time per period
- Overall progress (e.g., [15/56])

### Log Files

To save logs for later review:

```bash
python batch_preprocess_periods.py \
  --periods 1-56 \
  --continue-on-error \
  2>&1 | tee batch_processing.log
```

## Integration with Full Pipeline

After batch preprocessing, continue with the standard workflow:

### Step 1: Batch Preprocessing ✅

```bash
python batch_preprocess_periods.py --periods 1-56
```

### Step 2: Create Temporal Composites

```bash
# Create composite for each period
for period in {1..56}; do
  python s1_composite_12day.py \
    --period $period \
    --input-dir workspace/preprocessed_20m/p${period} \
    --output workspace/composites/s1_vh_p${period}_20m.tif \
    --method median
done
```

### Step 3: Stack All Periods

```bash
python create_annual_stack.py \
  --input-dir workspace/composites \
  --output s1_vh_stack_2024_2025_56periods_20m.tif
```

### Step 4: Train Model

```bash
python train_with_filtering.py \
  --tif-path s1_vh_stack_2024_2025_56periods_20m.tif \
  --csv-path training_points_all_periods.csv \
  --output-dir model_files_20m
```

### Step 5: Generate Predictions

```bash
for period in {1..56}; do
  python predict_optimized_filtered.py \
    --period $period \
    --tif-path s1_vh_stack_2024_2025_56periods_20m.tif \
    --model-path model_files_20m/rice_stage_model.keras \
    --scaler-path model_files_20m/scaler.joblib \
    --output-dir predictions_20m/p${period}
done
```

## Troubleshooting

### Problem: Script can't find input directories

**Solution:** Check your directory structure matches the expected pattern:
```
workspace/downloads/downloads_p{N}
```

Or use custom paths:
```bash
python batch_preprocess_periods.py \
  --download-base /path/to/your/downloads \
  --output-base /path/to/your/output
```

### Problem: Out of memory errors

**Solutions:**
1. Reduce number of workers:
   ```bash
   --workers 4  # instead of 8
   ```

2. Use coarser resolution:
   ```bash
   --resolution 50  # instead of 20
   ```

3. Process in smaller batches:
   ```bash
   python batch_preprocess_periods.py --periods 1-10
   python batch_preprocess_periods.py --periods 11-20
   # etc.
   ```

### Problem: Processing too slow

**Solutions:**
1. Increase workers (if memory allows):
   ```bash
   --workers 16
   ```

2. Use coarser resolution:
   ```bash
   --resolution 50  # or 100 for very fast
   ```

3. Process in parallel by year:
   ```bash
   # Terminal 1
   python batch_preprocess_periods.py --periods 1-31
   
   # Terminal 2 (simultaneously)
   python batch_preprocess_periods.py --periods 32-56 \
     --output-base workspace/preprocessed_20m_2025
   ```

### Problem: Some periods missing data

**Expected behavior:** Script will automatically skip these and report:
```
WARNING: Input directory workspace/downloads/downloads_p15 does not exist. Skipping...
```

**What to do:**
- Download missing data
- Reprocess only those periods later

## Best Practices

1. **Start with a test run** on a few periods:
   ```bash
   python batch_preprocess_periods.py --periods 1-3
   ```

2. **Use `--continue-on-error`** for large batch jobs to avoid stopping on minor issues

3. **Monitor disk space** before starting - check storage estimates above

4. **Process by year** for better organization and easier troubleshooting

5. **Save logs** for large processing runs:
   ```bash
   python batch_preprocess_periods.py --periods 1-56 2>&1 | tee preprocessing.log
   ```

6. **Check failed periods** and reprocess separately with more resources

7. **Use appropriate resolution** for your use case (see MULTI_RESOLUTION_GUIDE.md)

## Quick Reference

### Process Everything (Default Settings)
```bash
python batch_preprocess_periods.py
```

### Process 2024 Only
```bash
python batch_preprocess_periods.py --periods 1-31
```

### Process 2025 Only
```bash
python batch_preprocess_periods.py --periods 32-56
```

### High-Detail Processing
```bash
python batch_preprocess_periods.py --periods 1-56 --resolution 10 --workers 4
```

### Fast Processing
```bash
python batch_preprocess_periods.py --periods 1-56 --resolution 50 --workers 8
```

### Reprocess Failed Periods
```bash
python batch_preprocess_periods.py --periods 5,12,23
```

### Help
```bash
python batch_preprocess_periods.py --help
```

---

**Version:** 1.0  
**Last Updated:** November 2025  
**See Also:** MULTI_RESOLUTION_GUIDE.md, COMPLETE_WORKFLOW.md
