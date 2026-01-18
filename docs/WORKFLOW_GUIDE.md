# Complete Workflow: Training to Prediction

This guide shows the **exact command sequence** from training a model to making predictions.

---

## 📋 Prerequisites Checklist

Before starting, ensure you have:

```bash
# 1. Check data files exist
ls data/HA_JAWA_2024_compressed.tif          # Training/Prediction GeoTIFF
ls data/training_points_0104.csv              # Training points CSV
ls data/perioda.csv                           # Period lookup table

# 2. Check conda environment
conda activate myenv  # or your environment name

# 3. Verify GPU availability (optional but recommended)
python -c "import tensorflow as tf; print('GPUs:', tf.config.list_physical_devices('GPU'))"
```

**If any files are missing**, update paths in `config.py`

---

## 🎯 Option 1: RECOMMENDED (Best Speed + Accuracy)

### Step 1: Train Model with Best Accuracy

```bash
# Train using CNN-LSTM with class balancing and augmentation
python balanced_train_lstm.py --augment --use-class-weights

# Expected output:
# - Creates directory: model_files/training_YYYYMMDD_HHMMSS/
# - Training time: 2-4 hours (depends on data size)
# - Shows validation accuracy per class
# - Saves model artifacts
```

**What this does:**
- Uses CNN-LSTM architecture (best for temporal data)
- Applies SMOTE oversampling for minority classes
- Adds data augmentation with noise injection
- Uses class weighting to handle imbalance
- Expected accuracy: **5-15% better** than basic training

**Output files created:**
```
model_files/
├── rice_stage_model.keras          # Trained model
├── scaler.joblib                   # Feature scaler
├── label_encoder.joblib            # Label encoder
├── feature_columns.txt             # Feature names
└── training_YYYYMMDD_HHMMSS/
    ├── confusion_matrix.png
    ├── model_evaluation.txt
    ├── training_history.png
    ├── feature_importance.csv
    └── performance_metrics.txt
```

### Step 2: Verify Training Results

```bash
# Check model evaluation
cat model_files/training_*/model_evaluation.txt

# Look for:
# - Overall Accuracy: Should be > 85%
# - Per-class accuracy: All classes > 70%
```

### Step 3: Make Predictions (FAST - 10-50x speedup!)

```bash
# Single period prediction using OPTIMIZED script
python predict_optimized.py --period 23 --skip-test

# With mask to limit prediction area
python predict_optimized.py --period 23 --skip-test --mask /path/to/mask.tif

# Without temporal filtering (faster, independent predictions)
python predict_optimized.py --period 23 --skip-test --no-temporal
```

**What this does:**
- Uses vectorized feature extraction (10-50x faster!)
- Loads trained model from `model_files/`
- Processes entire GeoTIFF efficiently
- Saves predictions to `predictions/period_23/`

**Output files created:**
```
predictions/period_23/
├── predictions.tif          # Growth stage map (1-6)
├── confidence.tif           # Prediction confidence (0-1)
├── prediction_map.png       # Visualization
├── statistics.txt           # Class distribution
└── prediction.log           # Processing log
```

### Step 4: Batch Predictions for Multiple Periods

```bash
# Predict periods 8 through 23
for period in {8..23}; do
    echo "Processing period $period..."
    python predict_optimized.py --period $period --skip-test
done

# Or use the provided script (modify START_PERIOD and END_PERIOD first)
# Edit run_predictions.sh to use predict_optimized.py instead of predict.py
# Then run:
./run_predictions.sh
```

---

## 🎯 Option 2: FAST Training (CNN with SMOTE)

### Step 1: Train with CNN

```bash
# Faster training, still good accuracy
python train_cnn.py --use-smote

# Expected output:
# - Training time: 1-2 hours
# - Accuracy: 5-10% better than basic
```

### Step 2-4: Same as Option 1

Follow Steps 2-4 from Option 1 above.

---

## 🎯 Option 3: BASIC (Original Workflow)

### Step 1: Basic Training

```bash
# Simple MLP training (original)
python train.py

# Expected output:
# - Training time: 1-2 hours
# - Baseline accuracy
# - No class balancing
```

### Step 2: Make Predictions (Original - SLOW)

```bash
# Using original script (10-50x slower than optimized)
python predict.py --period 23 --skip-test

# NOTE: This is much slower! Use predict_optimized.py instead
```

---

## 📊 Benchmark Before Production Use

**IMPORTANT**: Before running large-scale predictions, benchmark the speedup:

```bash
# Test on small sample (takes ~2-5 minutes)
python benchmark_optimization.py --period 23 --samples 10000

# Expected output:
# Original time:      45.23s
# Vectorized time:     1.12s
# SPEEDUP:            40.4x faster
# ✓ Results are numerically identical
```

---

## 🔄 Complete Production Workflow

Here's the **full recommended sequence** for production:

```bash
# ============================================
# STEP 1: INITIAL SETUP (One-time)
# ============================================

# Activate environment
conda activate myenv

# Verify data files
ls -lh data/*.tif data/*.csv

# Verify model directory exists
mkdir -p model_files predictions


# ============================================
# STEP 2: TRAIN MODEL (Do this once or when updating model)
# ============================================

# Train with best accuracy (RECOMMENDED)
python balanced_train_lstm.py --augment --use-class-weights

# Wait for training to complete (2-4 hours)
# Check output directory: model_files/training_YYYYMMDD_HHMMSS/

# Verify training results
cat model_files/training_*/model_evaluation.txt


# ============================================
# STEP 3: BENCHMARK OPTIMIZATION (One-time verification)
# ============================================

# Test speedup on your system
python benchmark_optimization.py --period 23 --samples 10000

# Verify you see 10-50x speedup and valid features


# ============================================
# STEP 4: MAKE PREDICTIONS (Run for each period)
# ============================================

# Single period
python predict_optimized.py --period 23 --skip-test

# Check results
ls -lh predictions/period_23/
gdalinfo predictions/period_23/predictions.tif


# ============================================
# STEP 5: BATCH PREDICTIONS (Optional - multiple periods)
# ============================================

# Sequential predictions with temporal filtering
for period in {8..23}; do
    echo "================================"
    echo "Processing period $period"
    echo "================================"
    python predict_optimized.py --period $period --skip-test

    # Check if successful
    if [ $? -eq 0 ]; then
        echo "✓ Period $period completed successfully"
    else
        echo "✗ Period $period failed!"
        break
    fi
done


# ============================================
# STEP 6: VERIFY OUTPUTS
# ============================================

# Check all predictions were created
ls -lh predictions/period_*/predictions.tif

# View statistics for a period
cat predictions/period_23/statistics.txt

# Optional: Create combined visualization or analysis
```

---

## ⚙️ Configuration Notes

### Modify Config Before Training

If your data paths are different, edit `config.py`:

```python
# config.py - Update these paths
FILES = {
    'TRAINING_GEOTIFF': os.path.join(PATHS['DATA_DIR'], 'YOUR_TRAINING_FILE.tif'),
    'PREDICTION_GEOTIFF': os.path.join(PATHS['DATA_DIR'], 'YOUR_PREDICTION_FILE.tif'),
    'TRAINING_CSV': os.path.join(PATHS['DATA_DIR'], 'YOUR_TRAINING_POINTS.csv'),
    'PERIOD_LOOKUP': os.path.join(PATHS['DATA_DIR'], 'perioda.csv')
}
```

### Modify Prediction Settings

Common modifications in `predict_optimized.py`:

```python
# Line ~370: Adjust batch size if GPU memory issues
batch_size = 25000  # Reduce if out of memory

# Line ~666: Adjust smoothing kernel
smoothed_predictions = apply_spatial_smoothing_optimized(predictions, kernel_size=3)  # Reduce for less smoothing
```

---

## 📝 Command Reference Quick Sheet

### Training Commands
```bash
# Best accuracy (RECOMMENDED)
python balanced_train_lstm.py --augment --use-class-weights

# Good accuracy, faster training
python train_cnn.py --use-smote

# Standard with balancing
python balanced_train.py --augment

# Basic (not recommended)
python train.py
```

### Prediction Commands
```bash
# RECOMMENDED: Optimized (10-50x faster)
python predict_optimized.py --period 23 --skip-test

# With mask
python predict_optimized.py --period 23 --skip-test --mask mask.tif

# Without temporal filtering
python predict_optimized.py --period 23 --skip-test --no-temporal

# Original (slow, not recommended)
python predict.py --period 23 --skip-test
```

### Utility Commands
```bash
# Benchmark speedup
python benchmark_optimization.py --period 23 --samples 10000

# Check available periods (based on bands)
python -c "import rasterio; src=rasterio.open('data/HA_JAWA_2024_compressed.tif'); print(f'Bands: {src.count}, Valid periods: 7 to {src.count-6}')"

# View model info
python -c "import joblib; le=joblib.load('model_files/label_encoder.joblib'); print('Classes:', le.classes_)"
```

---

## 🚨 Common Issues

### Issue 1: "Model files not found"
```bash
# Solution: Train a model first!
python balanced_train_lstm.py --augment --use-class-weights
```

### Issue 2: "Period X requires band Y but only Z bands available"
```bash
# Solution: Check your GeoTIFF band count
gdalinfo data/HA_JAWA_2024_compressed.tif | grep "Band "

# Valid periods: 7 to (number_of_bands - 6)
# Example: 24 bands → valid periods are 7 to 18
```

### Issue 3: "GPU out of memory"
```bash
# Solution 1: Reduce batch size in predict_optimized.py (line ~370)
# Solution 2: Use mask to process smaller area
python predict_optimized.py --period 23 --mask smaller_area.tif
```

### Issue 4: "Predictions are empty"
```bash
# Check period number is valid
# Check input GeoTIFF has valid data
gdalinfo -stats data/HA_JAWA_2024_compressed.tif

# Run without --skip-test to see test results
python predict_optimized.py --period 23
```

---

## 📈 Performance Expectations

### Training Time
| Method | Dataset Size | Time |
|--------|--------------|------|
| balanced_train_lstm.py | ~100k samples | 2-4 hours |
| train_cnn.py | ~100k samples | 1-2 hours |
| train.py | ~100k samples | 1-2 hours |

### Prediction Time (Optimized)
| Area Size | Time |
|-----------|------|
| 1M pixels | 2-3 min |
| 10M pixels | 10-15 min |
| 50M pixels | 30-60 min |

### Prediction Time (Original)
| Area Size | Time |
|-----------|------|
| 1M pixels | 30 min |
| 10M pixels | 4 hours |
| 50M pixels | 24+ hours |

---

## ✅ Success Checklist

After running the complete workflow, you should have:

- [ ] Trained model in `model_files/rice_stage_model.keras`
- [ ] Model artifacts (scaler, label_encoder, feature_columns)
- [ ] Training evaluation results (accuracy > 85%)
- [ ] Benchmark showing 10-50x speedup
- [ ] Predictions for desired periods in `predictions/period_XX/`
- [ ] Prediction GeoTIFFs with growth stages 1-6
- [ ] Confidence maps showing model certainty
- [ ] Visualizations (PNG files)
- [ ] Statistics showing class distributions

---

## 🎓 Summary

**For Best Results:**
1. Train with: `python balanced_train_lstm.py --augment --use-class-weights`
2. Predict with: `python predict_optimized.py --period XX --skip-test`
3. Repeat step 2 for all desired periods

**Expected Performance:**
- Training: 2-4 hours (one time)
- Prediction: 10-15 min per period (10-50x faster than original)
- Accuracy: 5-15% better than baseline

**Next Steps:**
- Read `OPTIMIZATION_QUICKSTART.md` for quick reference
- See `CLAUDE.md` for detailed documentation
- Check `OPTIMIZATION_RECOMMENDATIONS.md` for future improvements
