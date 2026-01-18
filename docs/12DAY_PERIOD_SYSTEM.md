# 12-Day Period System for Rice Growth Stage Mapping

## Overview

The rice growth stage mapping system uses a **12-day period system** that divides each year into **31 periods** of 12 days each. This temporal compositing strategy provides consistent time intervals for monitoring rice phenology throughout the growing season.

---

## Period Structure

### Annual Division

- **Total periods per year**: 31
- **Days per period**: 12 (except Period 31)
- **Period numbering**: 1 to 31
- **Band numbering**: Period number = Band number

### Period Calendar for 2025

```
Period   Start Date   End Date     Days   Band
──────────────────────────────────────────────
1        2025-01-01   2025-01-12   12     1
2        2025-01-13   2025-01-24   12     2
3        2025-01-25   2025-02-05   12     3
4        2025-02-06   2025-02-17   12     4
5        2025-02-18   2025-03-01   12     5
6        2025-03-02   2025-03-13   12     6
7        2025-03-14   2025-03-25   12     7
8        2025-03-26   2025-04-06   12     8
9        2025-04-07   2025-04-18   12     9
10       2025-04-19   2025-04-30   12     10
...
30       2025-12-15   2025-12-26   12     30
31       2025-12-27   2025-12-31   5      31
```

**Note**: Period 31 has only 5 days (6 in leap years) to complete the year.

---

## Backward-Looking Time Series

### Temporal Window

The prediction model uses a **backward-looking approach** with:
- **Current period** (t0)
- **6 previous periods** (t1, t2, t3, t4, t5, t6)
- **Total temporal depth**: 7 periods

### Valid Prediction Periods

| Criteria | Value |
|----------|-------|
| **Minimum period** | Period 7 |
| **Maximum period** | Period 31 |
| **Total valid periods** | 25 periods |

**Why period 7 minimum?**
- To predict Period 7, you need:
  - Current: Period 7 (Band 7)
  - Previous: Periods 6, 5, 4, 3, 2, 1 (Bands 6-1)
  - Total: 7 bands

### Band Indexing Examples

```python
# Period 7 prediction uses:
band_indices = [6, 5, 4, 3, 2, 1, 0]  # Bands 7, 6, 5, 4, 3, 2, 1

# Period 15 prediction uses:
band_indices = [14, 13, 12, 11, 10, 9, 8]  # Bands 15, 14, 13, 12, 11, 10, 9

# Period 31 prediction uses:
band_indices = [30, 29, 28, 27, 26, 25, 24]  # Bands 31, 30, 29, 28, 27, 26, 25
```

---

## Data Products

### Annual Stack Format

**File naming**: `s1_vh_stack_<year>_31bands.tif`

**Specifications**:
- **Bands**: 31 (one per period)
- **Band order**: Sequential (Band 1 = Period 1, Band 2 = Period 2, etc.)
- **Data type**: Float32
- **Units**: VH backscatter in dB
- **NoData**: -32768
- **Compression**: LZW
- **Tiling**: Yes (for efficient access)

**Band descriptions**: `Period_<N>_<start_date>_<end_date>`

Example:
```
Band 1: Period_1_20250101_20250112
Band 2: Period_2_20250113_20250124
...
Band 31: Period_31_20251227_20251231
```

---

## Compositing Strategy

### Sentinel-1 Acquisition Density

Sentinel-1 constellation (S1A + S1B) provides:
- **Revisit time**: ~6 days
- **Expected acquisitions per period**: 2-3 scenes
- **Temporal coverage**: Excellent for 12-day compositing

### Compositing Methods

The system supports multiple compositing methods:

| Method | Description | Use Case |
|--------|-------------|----------|
| **median** | Median of all scenes in period | **Recommended** - robust to outliers |
| **mean** | Mean of all scenes in period | Smoother results |
| **first** | First scene in period | Preserve temporal detail |
| **last** | Last scene in period | Latest observation |

**Default**: `median` (best noise reduction)

### Gap Filling

When a period has no Sentinel-1 acquisitions, the system can:
1. **Interpolate** from neighboring periods (if both neighbors exist)
2. **Copy** from previous period (if only previous exists)
3. **Copy** from next period (if only next exists)
4. **Leave as NoData** (if disabled or no neighbors)

**Default**: Gap filling enabled

---

## Implementation

### Creating 12-Day Composites

```bash
# Generate period calendar for reference
python s1_composite_12day.py --year 2025 --print-calendar \
    --input-dir . --output dummy.tif

# Generate period lookup CSV
python s1_composite_12day.py --year 2025 --generate-lookup \
    --input-dir . --output dummy.tif

# Create 31-band annual stack
python s1_composite_12day.py \
    --year 2025 \
    --input-dir preprocessed/ \
    --output s1_vh_stack_2025_31bands.tif \
    --method median
```

### Python API

```python
from s1_composite_12day import Sentinel1Compositor
from period_utils import get_period_dates, get_period_from_date

# Initialize compositor
compositor = Sentinel1Compositor(year=2025, output_dir='composites/')

# Create annual stack
stacked_file = compositor.create_annual_stack(
    input_dir='preprocessed/',
    output_file='s1_vh_stack_2025_31bands.tif',
    composite_method='median',
    fill_missing=True
)

# Get period information
start_date, end_date = get_period_dates(2025, 15)
print(f"Period 15: {start_date} to {end_date}")

# Convert date to period
from datetime import datetime
date = datetime(2025, 6, 15)
period = get_period_from_date(date)
print(f"{date.date()} is in Period {period}")
```

---

## Integration with Pipeline

### Automated Pipeline

The automated pipeline (`s1_pipeline_auto.py`) now uses 12-day compositing:

```bash
# Run complete pipeline with 12-day compositing
python s1_pipeline_auto.py --config pipeline_config.yaml --run-all
```

**Pipeline steps**:
1. **Download**: Sentinel-1 data from ASF or CDSE
2. **Preprocess**: SNAP GPT processing
3. **Composite**: Create 31-band stack using 12-day periods ← NEW
4. **Train**: Train growth stage model
5. **Predict**: Generate predictions for periods 7-31

### Configuration

In `pipeline_config.yaml`:

```yaml
data_acquisition:
  start_date: '2025-01-01'
  end_date: '2025-12-31'  # Full year for 31 periods

prediction:
  # Valid periods: 7-31 (need 7 bands for backward window)
  periods: [7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18,
            19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31]
```

---

## Prediction Workflow

### Command Examples

```bash
# Predict Period 7 (earliest possible)
python predict_optimized.py --period 7 --skip-test

# Predict Period 15 (mid-season)
python predict_optimized.py --period 15 --skip-test

# Predict Period 31 (end of year)
python predict_optimized.py --period 31 --skip-test
```

### What Happens Internally

For **Period 15** prediction:
```
1. Load bands 9-15 from GeoTIFF (7 bands total)
2. Extract VH values: VH_t0 through VH_t6
   - VH_t0 = Band 15 (current period)
   - VH_t1 = Band 14 (1 period back)
   - VH_t2 = Band 13 (2 periods back)
   - ...
   - VH_t6 = Band 9 (6 periods back)
3. Calculate derived features:
   - Differences: dVH_t1 through dVH_t6 (6 features)
   - Ratios: rVH_t1 through rVH_t6 (6 features)
   - Phenology: min, max, range, mean, std, trend (6 features)
   - Extrema: first, last, max_idx, min_idx (4 features)
4. Total features: 7 + 6 + 6 + 6 + 4 = 29 features
5. Scale features using trained scaler
6. Predict using CNN-LSTM model
7. Save results to predictions/period_15/
```

---

## Period Lookup Table

The `perioda_2025.csv` file provides easy lookup:

```csv
Periode,Start Date,End Date
1,2025-01-01,2025-01-12
2,2025-01-13,2025-01-24
3,2025-01-25,2025-02-05
...
31,2025-12-27,2025-12-31
```

**Usage**:
- Planning field campaigns
- Interpreting prediction results
- Matching ground truth observations

---

## Advantages of 12-Day Periods

### 1. **Consistent Temporal Sampling**
- Fixed 12-day intervals (vs. variable 8-day or 16-day)
- Aligns well with Sentinel-1 6-day revisit
- ~2-3 acquisitions per period for robust composites

### 2. **Optimal for Rice Phenology**
- Rice growth stages progress over ~10-15 days
- 12-day periods capture phenological changes
- Sufficient temporal detail for stage transitions

### 3. **Computational Efficiency**
- 31 bands = manageable file size
- Faster than daily or weekly stacks
- Efficient feature extraction and prediction

### 4. **Operational Feasibility**
- Near-real-time monitoring possible
- Updates every 12 days
- Balances timeliness and data volume

---

## Migration from Previous System

If you have existing code using different period systems:

### Old System → New System

| Old | New | Notes |
|-----|-----|-------|
| Periods 8-55 | Periods 7-31 | Reduced to annual calendar |
| Variable bands | 31 bands | Fixed annual structure |
| Custom date ranges | 12-day periods | Standardized intervals |

### Code Updates Required

1. **Change period ranges**:
```python
# OLD
for period in range(8, 56):
    predict(period)

# NEW
for period in range(7, 32):
    predict(period)
```

2. **Update band expectations**:
```python
# OLD
expected_bands = 55  # Multi-year stack

# NEW
expected_bands = 31  # Single year stack
```

3. **Use new utilities**:
```python
# NEW
from period_utils import get_period_dates, get_valid_prediction_periods

valid_periods = get_valid_prediction_periods(total_bands=31, n_previous=6)
# Returns: [7, 8, 9, ..., 31]
```

---

## Validation and Quality Control

### Check Stack Validity

```python
import rasterio
from period_utils import validate_period_data

# Open stack
with rasterio.open('s1_vh_stack_2025_31bands.tif') as src:
    n_bands = src.count

    # Validate
    validate_period_data(n_bands, year=2025)
    # ✓ Band count validation passed: 31 bands
```

### Check Period Coverage

```bash
# List all periods and their coverage
python s1_composite_12day.py --year 2025 --print-calendar \
    --input-dir . --output dummy.tif
```

---

## Troubleshooting

### Issue: "Period X requires bands Y to Z, but only 31 bands available"

**Cause**: Trying to predict period < 7

**Solution**: Use periods 7-31 only
```bash
# ERROR
python predict_optimized.py --period 5

# CORRECT
python predict_optimized.py --period 7
```

### Issue: Missing periods in stack

**Cause**: No Sentinel-1 acquisitions for some periods

**Solution**: Enable gap filling
```python
compositor.create_annual_stack(
    ...,
    fill_missing=True  # ← Enable interpolation
)
```

### Issue: Wrong number of bands

**Cause**: Multi-year stack or incorrect compositing

**Solution**: Create one stack per year
```bash
# Create 2024 stack (31 bands)
python s1_composite_12day.py --year 2024 --input-dir preprocessed_2024/ ...

# Create 2025 stack (31 bands)
python s1_composite_12day.py --year 2025 --input-dir preprocessed_2025/ ...
```

---

## References

### Key Files

- `period_utils.py` - Period calculation utilities
- `s1_composite_12day.py` - 12-day compositor
- `s1_pipeline_auto.py` - Automated pipeline with compositing
- `pipeline_config.yaml` - Pipeline configuration
- `perioda_2025.csv` - Period lookup table

### Related Documentation

- `AUTOMATED_PIPELINE_GUIDE.md` - Complete pipeline workflow
- `WORKFLOW_GUIDE.md` - Manual workflow steps
- `CLAUDE.md` - System architecture and commands

---

## Summary

**12-Day Period System**:
✅ 31 periods per year (12 days each)
✅ Period number = Band number
✅ Valid predictions: Periods 7-31
✅ Backward window: 7 periods (current + 6 previous)
✅ Median compositing with gap filling
✅ Integrated into automated pipeline

**Quick Start**:
```bash
# 1. Create 31-band stack
python s1_composite_12day.py --year 2025 \
    --input-dir preprocessed/ \
    --output s1_vh_stack_2025_31bands.tif

# 2. Predict any period 7-31
python predict_optimized.py --period 15 --skip-test
```

---

*Last Updated: 2025-10-19*
*Version: 1.0 - Initial 12-day period system implementation*
