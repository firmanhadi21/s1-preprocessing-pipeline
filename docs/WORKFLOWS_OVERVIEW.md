# Period-Based Workflows Overview

## Two Approaches for Period-Based Processing

You now have **two complete workflows** for period-based Sentinel-1 processing:

### 1. Automated Period Pipeline ⚡ (Fully Automated)
**Script:** `s1_period_pipeline.py`  
**Guide:** `PERIOD_PIPELINE_GUIDE.md`

✅ **Fully automated** downloads via API  
✅ Zero manual intervention  
✅ Best for: Processing all 31 periods automatically

### 2. Manual Period Workflow 🎯 (Semi-Automated)
**Script:** `s1_manual_period_workflow.py`  
**Guide:** `MANUAL_WORKFLOW_QUICKSTART.md`

✅ **Manual scene selection**  
✅ Full control over downloads  
✅ Best for: Choosing specific scenes per period

---

## Quick Comparison

| Aspect | Automated Pipeline | Manual Workflow |
|--------|-------------------|-----------------|
| **Downloads** | Automatic via API | Manual from ASF |
| **Scene Selection** | Uses all scenes | Choose specific scenes |
| **Setup** | 5 min config | 2-4 hours downloading |
| **Processing** | Fully automatic | Semi-automatic |
| **Control** | Medium | High |
| **Best For** | Full automation | Specific scene selection |

---

## When to Use Each

### Use Automated Pipeline When:
- ✅ You want **zero manual work**
- ✅ You're processing **all 31 periods**
- ✅ You don't need to pick specific scenes
- ✅ You want **fastest setup**

### Use Manual Workflow When:
- ✅ You want to **select specific scenes**
- ✅ You're processing **only certain periods**
- ✅ You **already have downloads**
- ✅ You want **maximum control**

---

## Automated Pipeline Quick Start

```bash
# 1. Configure
cp pipeline_config_period.yaml my_region.yaml
nano my_region.yaml  # Edit AOI

# 2. Run (fully automated)
python s1_period_pipeline.py --config my_region.yaml --year 2024 --run-all

# OR use quick launcher:
./run_period_pipeline.sh 2024

# 3. Output
# workspace_period/year_2024/final_stack/S1_VH_stack_2024_31bands.tif
```

**Time:** 16-48 hours (fully automated, no manual intervention)

---

## Manual Workflow Quick Start

```bash
# 1. Setup folders
python setup_manual_period_folders.py

# 2. Download manually from ASF
#    Place in downloads_p1/, downloads_p2/, etc.

# 3. Process
python s1_manual_period_workflow.py --run-all --year 2024

# 4. Output
# final_stack/S1_VH_stack_2024_31bands.tif
```

**Time:** 2-4 hours downloading + 8-48 hours processing

---

## Both Workflows Produce Same Output

**Final output from both:**
```
S1_VH_stack_2024_31bands.tif
```

**Properties:**
- 31 bands (one per 12-day period)
- Band 1 = Period 1 (Jan 1-12)
- Band 31 = Period 31 (Dec 27-31)
- VH backscatter in dB
- Seamless mosaics (NULL values ignored)
- Ready for training/prediction!

**Integration:**
```python
# In config.py
PREDICTION_GEOTIFF = 'path/to/S1_VH_stack_2024_31bands.tif'
```

```bash
python train.py
python predict.py --period 15
```

---

## Folder Structures

### Automated Pipeline Structure

```
workspace_period/year_2024/
├── downloads/              # Auto-downloaded ZIP files
├── preprocessed/           # SNAP processed files
├── geotiff/                # Individual scene GeoTIFFs
├── period_mosaics/         # One mosaic per period
│   ├── period_01_VH.tif
│   └── ...
└── final_stack/
    └── S1_VH_stack_2024_31bands.tif  ← Final output
```

### Manual Workflow Structure

```
your_workspace/
├── downloads_p1/           # YOUR manual downloads for Period 1
├── downloads_p2/           # YOUR manual downloads for Period 2
├── ...
├── preprocessed_p1/        # Auto-generated
├── preprocessed_p2/
├── ...
├── mosaics/                # Auto-generated
│   ├── mosaic_p1.tif
│   └── ...
└── final_stack/
    └── S1_VH_stack_2024_31bands.tif  ← Final output
```

---

## Common Commands

### Automated Pipeline

```bash
# Full year
./run_period_pipeline.sh 2024

# Specific periods
python s1_period_pipeline.py \
    --config cfg.yaml \
    --year 2024 \
    --periods "1-10" \
    --run-all

# Resume from mosaicking
python s1_period_pipeline.py \
    --config cfg.yaml \
    --year 2024 \
    --run-all \
    --skip-download \
    --skip-preprocess
```

### Manual Workflow

```bash
# Setup folders
python setup_manual_period_folders.py

# Process single period
python s1_manual_period_workflow.py --period 1 --run-all

# Process all periods
python s1_manual_period_workflow.py --run-all --year 2024

# Just stack existing mosaics
python s1_manual_period_workflow.py --stack --year 2024
```

---

## Seamless Mosaicking (Both Workflows)

Both workflows create **seamless mosaics** by:
- ✅ Extracting VH band from preprocessed files
- ✅ Converting to GeoTIFF
- ✅ Merging with `rasterio.merge()`
- ✅ **Automatically ignoring NULL/nodata values**
- ✅ Using "first valid pixel" for overlaps
- ✅ Output: Compressed, tiled, seamless GeoTIFF

**No manual editing needed - completely automated!**

---

## Documentation Index

### Automated Pipeline
- **Quick Start:** `PERIOD_PROCESSING_README.md`
- **Complete Guide:** `PERIOD_PIPELINE_GUIDE.md`
- **Implementation:** `PERIOD_PROCESSING_SUMMARY.md`

### Manual Workflow
- **Quick Start:** `MANUAL_WORKFLOW_QUICKSTART.md`
- **Complete Guide:** `MANUAL_PERIOD_WORKFLOW_GUIDE.md`

### General
- **Pipeline Comparison:** `PIPELINE_COMPARISON.md`
- **Period System:** `12DAY_PERIOD_SYSTEM.md`
- **Training/Prediction:** `COMPLETE_WORKFLOW.md`

---

## Example Scenarios

### Scenario 1: First Time User, Want Automation

```bash
# Use automated pipeline
cp pipeline_config_period.yaml my_config.yaml
nano my_config.yaml  # Edit AOI
./run_period_pipeline.sh 2024
```

### Scenario 2: Need Specific Scenes Only

```bash
# Use manual workflow
python setup_manual_period_folders.py
# Download specific scenes from ASF
# Place in downloads_pX/ folders
python s1_manual_period_workflow.py --run-all --year 2024
```

### Scenario 3: Already Have Downloads

```bash
# Use manual workflow
# Organize existing downloads into downloads_p1/, downloads_p2/, etc.
python s1_manual_period_workflow.py --run-all --year 2024
```

### Scenario 4: Process Only Growing Season

**Automated:**
```bash
python s1_period_pipeline.py \
    --config cfg.yaml \
    --year 2024 \
    --periods "5-25" \
    --run-all
```

**Manual:**
```bash
# Download only periods 5-25, then:
for p in {5..25}; do
    python s1_manual_period_workflow.py --period $p --run-all
done
python s1_manual_period_workflow.py --stack --year 2024
```

---

## Both Are Production-Ready

✅ **Automated Pipeline** - Best for most users  
✅ **Manual Workflow** - Best for specific needs  
✅ **Both produce identical outputs**  
✅ **Both integrate seamlessly with training/prediction**  
✅ **Both create seamless mosaics**  
✅ **Both are fully documented**  

---

## Getting Started

**Choose your workflow:**

1. **Want full automation?**  
   → Start with `PERIOD_PROCESSING_README.md`  
   → Use `s1_period_pipeline.py`

2. **Want manual control?**  
   → Start with `MANUAL_WORKFLOW_QUICKSTART.md`  
   → Use `s1_manual_period_workflow.py`

3. **Not sure?**  
   → Read `PIPELINE_COMPARISON.md`  
   → Try automated first (easier setup)

---

## Support

Both workflows are tested and production-ready. See documentation for:
- Detailed usage guides
- Troubleshooting tips
- Performance optimization
- Integration with training

Happy mapping! 🌾🛰️
