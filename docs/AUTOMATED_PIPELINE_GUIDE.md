# Automated Data Acquisition & Processing Pipeline

## 📋 Overview

This automated pipeline replaces manual GEE processing with automatic downloading and preprocessing of Sentinel-1 data using ESA SNAP.

**Complete Workflow**:
1. **Download** Sentinel-1 GRD data from ASF or ESA SciHub
2. **Preprocess** with SNAP GPT (orbit, calibration, terrain correction, speckle filter)
3. **Stack** temporal data into multi-band GeoTIFF
4. **Train** growth stage mapping model
5. **Predict** rice growth stages

---

## 🎯 New vs Old Workflow

### Old Workflow (Manual GEE)
```
Google Earth Engine (Web Interface)
  ↓ Manual export
GeoTIFF file
  ↓ Manual download
Local training/prediction
```

### New Workflow (Automated)
```bash
# One command does everything!
python s1_pipeline_auto.py --config pipeline_config.yaml --run-all
```

---

## 🚀 Quick Start

### Step 1: Install Dependencies

```bash
# Python packages
pip install sentinelsat asf-search pyyaml

# Or using conda
conda install -c conda-forge sentinelsat pyyaml
pip install asf-search

# SNAP (ESA Sentinel Application Platform)
# Download from: https://step.esa.int/main/download/snap-download/
# Install and ensure 'gpt' is in your PATH
```

### Step 2: Configure Pipeline

```bash
# Copy and edit configuration
cp pipeline_config.yaml my_pipeline.yaml
nano my_pipeline.yaml

# Edit these key parameters:
# - aoi_bbox: Your area of interest coordinates
# - start_date / end_date: Time period
# - snap_gpt_path: Path to SNAP GPT (if not in PATH)
```

### Step 3: Run Automated Pipeline

```bash
# Complete automated workflow
python s1_pipeline_auto.py --config my_pipeline.yaml --run-all

# This will:
# 1. Download Sentinel-1 data for your AOI and time period
# 2. Preprocess each scene with SNAP
# 3. Stack into multi-band GeoTIFF
# 4. Provide instructions for training/prediction
```

---

## 📁 File Structure

### New Pipeline Files

| File | Purpose |
|------|---------|
| **s1_download.py** | Download Sentinel-1 data from ASF or ESA SciHub |
| **s1_preprocess_snap.py** | Preprocess with SNAP GPT |
| **s1_pipeline_auto.py** | Complete automated pipeline orchestrator |
| **pipeline_config.yaml** | Configuration file |
| **sen1_preprocessing-gpt.xml** | SNAP preprocessing workflow (already provided) |

### Pipeline Output Structure

```
pipeline_workspace/
├── downloads/                    # Downloaded .zip files
│   ├── S1A_IW_GRDH_*.zip
│   └── S1B_IW_GRDH_*.zip
├── extracted/                    # Extracted .SAFE directories
├── preprocessed/                 # Preprocessed GeoTIFFs (one per date)
│   ├── S1A_*_processed.tif
│   └── S1B_*_processed.tif
├── stacked/                      # Multi-band temporal stack
│   └── s1_vh_stack_24bands.tif  # Ready for training/prediction!
├── models/                       # Trained models
└── predictions/                  # Prediction outputs
```

---

## 🔧 Detailed Setup

### 1. Install SNAP

**Linux:**
```bash
# Download SNAP installer
wget https://download.esa.int/step/snap/9.0/installers/esa-snap_sentinel_unix_9_0_0.sh

# Make executable
chmod +x esa-snap_sentinel_unix_9_0_0.sh

# Install
./esa-snap_sentinel_unix_9_0_0.sh

# Add to PATH
echo 'export PATH=/usr/local/snap/bin:$PATH' >> ~/.bashrc
source ~/.bashrc

# Verify installation
gpt -h
```

**Windows:**
- Download installer from https://step.esa.int/main/download/snap-download/
- Run installer (esa-snap_sentinel_windows-x64_9_0_0.exe)
- Add `C:\Program Files\snap\bin` to system PATH

**macOS:**
```bash
# Download .dmg from SNAP website
# Install app
# Add to PATH:
echo 'export PATH=/Applications/snap/bin:$PATH' >> ~/.zshrc
source ~/.zshrc
```

### 2. Register for Data Access

**Option A: ASF (Recommended - No Registration Required)**
- Alaska Satellite Facility provides free Sentinel-1 access
- No account needed for most data
- Faster downloads
- **This is the default option**

**Option B: ESA SciHub (Requires Registration)**
```bash
# 1. Register at: https://scihub.copernicus.eu/dhus/#/self-registration
# 2. Confirm email
# 3. Add credentials to pipeline_config.yaml:

data_acquisition:
  download_source: scihub
  scihub_username: your_username
  scihub_password: your_password
```

### 3. Configure Your Area of Interest

Edit `pipeline_config.yaml`:

```yaml
data_acquisition:
  # Define your area (example: Java Island)
  aoi_bbox: [106.0, -8.0, 115.0, -5.0]  # [min_lon, min_lat, max_lon, max_lat]

  # Define time period
  start_date: '2024-01-01'
  end_date: '2024-06-30'
```

**How to find coordinates:**
- Use https://boundingbox.klokantech.com/
- Draw box around your area
- Copy coordinates in format: `CSV` → `[min_lon, min_lat, max_lon, max_lat]`

---

## 💻 Usage Examples

### Example 1: Complete Automated Workflow

```bash
# Edit configuration
nano pipeline_config.yaml

# Run complete pipeline
python s1_pipeline_auto.py --config pipeline_config.yaml --run-all

# Expected output:
# - Downloads ~10-50 Sentinel-1 scenes (depends on time period)
# - Preprocesses each scene (~30-60 min per scene)
# - Creates stacked multi-band GeoTIFF
# - Total time: 8-24 hours (depends on area size and time period)
```

### Example 2: Step-by-Step Execution

```bash
# Step 1: Download only
python s1_pipeline_auto.py --config pipeline_config.yaml --download-only

# Step 2: Preprocess only (after download)
python s1_pipeline_auto.py --config pipeline_config.yaml --preprocess-only

# Step 3: Stack only (after preprocessing)
python s1_pipeline_auto.py --config pipeline_config.yaml --stack-only
```

### Example 3: Resume After Interruption

```bash
# If download already completed, skip it
python s1_pipeline_auto.py --config pipeline_config.yaml --run-all --skip-download

# If preprocessing already done, skip it too
python s1_pipeline_auto.py --config pipeline_config.yaml --run-all --skip-download --skip-preprocess
```

### Example 4: Process Existing Downloaded Data

```bash
# If you already have .zip files in downloads/ directory
python s1_pipeline_auto.py --config pipeline_config.yaml --run-all --skip-download
```

---

## 📊 Expected Processing Times

| Step | Number of Scenes | Time per Scene | Total Time |
|------|------------------|----------------|------------|
| Download | 24 (6 months) | 10-30 min | 4-12 hours |
| Preprocessing | 24 scenes | 30-60 min | 12-24 hours |
| Stacking | 24 bands | 5-10 min | 5-10 min |

**Total pipeline time: 16-36 hours** (can run overnight/weekend)

**Disk space required**:
- Raw downloads: ~30-50 GB
- Preprocessed: ~20-30 GB
- Stacked output: ~5-10 GB
- **Total: ~60-100 GB**

---

## 🎓 Understanding the SNAP Preprocessing

The `sen1_preprocessing-gpt.xml` workflow applies these steps:

### 1. Apply Orbit File
- Updates orbit metadata with precise orbit information
- Essential for accurate geolocation

### 2. Thermal Noise Removal
- Removes thermal noise from SAR data
- Improves radiometric quality

### 3. Calibration (Beta0)
- Converts digital numbers to backscatter coefficient
- Uses Beta0 (terrain-flattened backscatter)

### 4. Terrain Flattening
- Corrects for local incidence angle variations
- Critical for mountainous/hilly terrain

### 5. Terrain Correction (Range Doppler)
- Orthorectifies SAR data using DEM (SRTM 1-arc second)
- Projects to WGS84 geographic coordinates
- Resamples to 10m pixel spacing

### 6. Speckle Filtering
- Applies Gamma MAP filter (5x5 kernel)
- Reduces speckle noise while preserving edges

### 7. Linear to dB Conversion
- Converts backscatter to decibel scale
- Final output: VH backscatter in dB

**Result**: Calibrated, terrain-corrected, speckle-filtered VH backscatter in dB (×100 for your model)

---

## 🔍 Troubleshooting

### Issue 1: SNAP GPT Not Found

```bash
# Check if SNAP is installed
which gpt
gpt -h

# If not found, add to PATH:
export PATH=/usr/local/snap/bin:$PATH

# Or specify path in config:
preprocessing:
  snap_gpt_path: /path/to/snap/bin/gpt
```

### Issue 2: Download Fails (SciHub)

```bash
# Error: Authentication failed
# Solution: Check credentials in pipeline_config.yaml

# Error: No products found
# Solution: Check your AOI and date range

# Alternative: Use ASF instead
data_acquisition:
  download_source: asf  # No credentials needed!
```

### Issue 3: Out of Memory During Preprocessing

```bash
# Reduce SNAP cache size
preprocessing:
  cache_size: '4G'  # Instead of '8G'

# Or increase available RAM:
# Close other applications before running
```

### Issue 4: Preprocessing Fails for Some Scenes

```bash
# Check SNAP logs in:
# ~/.snap/var/log/

# Common fixes:
# 1. Re-download failed scene
# 2. Check if .zip file is complete
# 3. Ensure SNAP has write permissions
# 4. Update SNAP to latest version
```

### Issue 5: Stack Has Misaligned Bands

```bash
# Cause: Different scenes have different extents
# Solution: All scenes should use same AOI subset

# Future enhancement: Add automatic alignment
```

---

## 📚 Integration with Existing Workflow

### After Pipeline Completes

```bash
# 1. Update config.py with new data paths
nano config.py

# Update these lines:
FILES = {
    'TRAINING_GEOTIFF': './pipeline_workspace/stacked/s1_vh_stack_24bands.tif',
    'PREDICTION_GEOTIFF': './pipeline_workspace/stacked/s1_vh_stack_24bands.tif',
    'TRAINING_CSV': './data/training_points_0104.csv',  # Your training points
    'PERIOD_LOOKUP': './data/perioda.csv'
}

# 2. Train model (use optimized scripts!)
python balanced_train_lstm.py --augment --use-class-weights

# 3. Generate predictions
python predict_optimized.py --period 23 --skip-test

# 4. Batch predictions
for period in {8..23}; do
    python predict_optimized.py --period $period --skip-test
done
```

---

## 🆚 Comparison: Manual vs Automated

| Aspect | Manual (GEE) | Automated (Pipeline) |
|--------|--------------|----------------------|
| **Setup** | Web interface | One-time install |
| **Data Source** | GEE catalog | Direct from ESA/ASF |
| **Processing** | GEE servers | Local SNAP |
| **Control** | Limited | Full control |
| **Customization** | JavaScript | Python |
| **Reproducibility** | Low (GEE changes) | High (local) |
| **Cost** | Free (GEE limits) | Free (local compute) |
| **Time** | Manual clicks | Fully automated |
| **Integration** | Export → Download | Direct to pipeline |

**Recommendation**: Use automated pipeline for:
- ✅ Reproducible research
- ✅ Custom processing chains
- ✅ Large-scale processing
- ✅ Full control over parameters
- ✅ Integration with ML pipeline

---

## 🔮 Future Enhancements

Potential additions to the pipeline:

1. **Automatic AOI Alignment**
   - Ensure all scenes cover same extent
   - Auto-crop to common area

2. **Cloud Storage Integration**
   - Download directly from Google Cloud Sentinel-1 buckets
   - Faster than ESA SciHub

3. **Parallel Processing**
   - Process multiple scenes simultaneously
   - Reduce total processing time

4. **Quality Checks**
   - Automatic scene quality assessment
   - Skip cloudy/bad quality scenes

5. **Training Point Generation**
   - Interactive tool to create training points
   - Integration with field data

---

## 💡 Tips & Best Practices

### 1. Start Small
```bash
# Test with small area and short time period first
aoi_bbox: [106.0, -7.0, 107.0, -6.0]  # Small test area
start_date: '2024-01-01'
end_date: '2024-01-31'  # One month only
```

### 2. Monitor Disk Space
```bash
# Check available space before starting
df -h

# Clean up after stacking
rm -rf pipeline_workspace/downloads/*.zip  # Remove raw downloads
rm -rf pipeline_workspace/extracted/       # Remove extracted files
```

### 3. Use Screen/tmux for Long Runs
```bash
# Start screen session
screen -S pipeline

# Run pipeline
python s1_pipeline_auto.py --config pipeline_config.yaml --run-all

# Detach: Ctrl+A, D
# Reattach: screen -r pipeline
```

### 4. Backup Configuration
```bash
# Save your working config
cp pipeline_config.yaml pipeline_config_working.yaml

# Add to version control
git add pipeline_config_working.yaml
git commit -m "Working pipeline configuration for Java Island"
```

---

## 📞 Support & Resources

### Documentation
- **SNAP Documentation**: https://step.esa.int/main/doc/
- **Sentinel-1 User Guide**: https://sentinel.esa.int/web/sentinel/user-guides/sentinel-1-sar
- **ASF Data Search**: https://search.asf.alaska.edu/

### Training Materials
- **SNAP Tutorials**: https://step.esa.int/main/doc/tutorials/
- **Sentinel-1 Toolbox**: https://sentinel.esa.int/web/sentinel/toolboxes/sentinel-1

### Community
- **STEP Forum**: https://forum.step.esa.int/
- **Sentinel-1 Mission**: https://sentinel.esa.int/web/sentinel/missions/sentinel-1

---

## ✅ Summary

**You now have**:
- ✅ Automated data download (s1_download.py)
- ✅ SNAP preprocessing wrapper (s1_preprocess_snap.py)
- ✅ Complete pipeline orchestrator (s1_pipeline_auto.py)
- ✅ Configuration template (pipeline_config.yaml)
- ✅ Integration with existing training/prediction workflow

**Next step**: Follow the Quick Start guide above to run your first automated pipeline!

**Time savings**:
- Manual GEE workflow: ~4-8 hours of manual work per dataset
- Automated pipeline: ~5 minutes setup, then fully automatic!

**Total workflow**: Data Download → SNAP Processing → Training → Prediction (all automated!)
