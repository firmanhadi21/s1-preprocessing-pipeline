# Java Island Mosaicking Guide

## Your Original Approach vs. Recommended Approach

### Your Idea: Sequential Histogram Matching
```
Period 1:
  Scene1 + Scene2 → Temp1 (histogram match)
  Temp1 + Scene3 → Temp2 (histogram match)
  Temp2 + Scene4 → ... → Final mosaic

Repeat for all 31 periods
```

**Issues:**
- ❌ **Order dependency**: First scene becomes "reference", biases entire mosaic
- ❌ **Error propagation**: Histogram matching errors accumulate
- ❌ **Arbitrary reference**: Why should Scene1 define radiometry?
- ❌ **Inefficient**: N-1 intermediate mosaics per period

### Recommended: Track-Based Compositing + Smart Mosaicking

```
Period 1:
  Track A: [Scene1, Scene2, Scene3] → Median composite → Track_A.tif
  Track B: [Scene4, Scene5] → Median composite → Track_B.tif
  Track C: [Scene6, Scene7, Scene8, Scene9] → Median composite → Track_C.tif

  Mosaic [Track_A, Track_B, Track_C] with gdalwarp (automatic blending)
  → period_01_mosaic.tif

Repeat for all 31 periods
Stack all mosaics → java_vh_stack_2024_31bands.tif
```

**Advantages:**
- ✅ **No order dependency**: All inputs treated equally
- ✅ **Temporal consistency**: Median reduces noise within each track
- ✅ **Radiometric consistency**: Same-track scenes have similar radiometry
- ✅ **Automated blending**: gdalwarp handles overlaps optimally
- ✅ **Efficient**: Minimal intermediate files

---

## Why This Approach Works Better

### 1. Track-Based Compositing
Scenes from the **same relative orbit** (track) have:
- Same acquisition geometry
- Same incidence angles
- Same radiometric characteristics
- **Minimal radiometric differences**

→ Compositing within tracks is **safe and consistent**

### 2. Median Compositing
Using median instead of mean:
- ✅ Robust to outliers (bright targets, dark shadows)
- ✅ Reduces speckle noise
- ✅ Preserves radiometric integrity
- ✅ Natural "best pixel" selection

### 3. GDAL Mosaicking
`gdalwarp` automatically:
- Handles different extents and overlaps
- Applies bilinear resampling
- Blends overlaps (average by default)
- Maintains consistent pixel grid
- Faster than manual histogram matching

---

## Comparison Table

| Aspect | Your Approach | Recommended Approach |
|--------|---------------|---------------------|
| **Radiometric consistency** | Histogram matching (manual) | Track-based grouping (natural) |
| **Overlap handling** | Sequential blending | Simultaneous weighted blending |
| **Reference bias** | First scene is reference | No reference (equal treatment) |
| **Speckle reduction** | None | Median compositing |
| **Processing time** | High (many iterations) | Low (parallel compositing) |
| **Disk usage** | High (many intermediates) | Low (clean up tracks) |
| **Automation** | Manual tuning needed | Fully automated |
| **Reproducibility** | Order-dependent | Order-independent |

---

## Usage

### Step 1: Create Period Mosaics

**After preprocessing completes**, run:

```bash
python s1_mosaic_java_12day.py \
    --input-dir workspace/preprocessed_50m \
    --output-dir workspace/mosaics_50m \
    --year 2024 \
    --resolution 50 \
    --composite-method median
```

This will:
1. Group your 251+ scenes by 12-day period AND track
2. Create median composite for each track in each period
3. Mosaic tracks together with seamless blending
4. Output: `workspace/mosaics_50m/period_01_mosaic.tif` through `period_31_mosaic.tif`

**Expected output:**
```
Period  1: 3 tracks, 14 scenes → period_01_mosaic.tif
Period  2: 3 tracks, 13 scenes → period_02_mosaic.tif
...
Period 31: 3 tracks, 12 scenes → period_31_mosaic.tif
```

### Step 2: Create Annual Stack

```bash
python s1_mosaic_java_12day.py \
    --input-dir workspace/preprocessed_50m \
    --output-dir workspace/mosaics_50m \
    --output workspace/java_vh_stack_2024_31bands.tif \
    --year 2024 \
    --resolution 50
```

This creates the final **31-band GeoTIFF** ready for training/prediction.

**Or create stack from existing mosaics:**
```bash
python s1_mosaic_java_12day.py \
    --input-dir workspace/preprocessed_50m \
    --output-dir workspace/mosaics_50m \
    --output workspace/java_vh_stack_2024_31bands.tif \
    --stack-only
```

### Step 3: Use in Training/Prediction

Update `config.py`:
```python
# Path to annual stack
VH_STACK_2024 = 'workspace/java_vh_stack_2024_31bands.tif'

# Training data
TRAINING_CSV = 'path/to/training_points.csv'
```

Then train:
```bash
python train.py
```

---

## Advanced Options

### Custom Extent

If you want to limit to a specific area:

```bash
python s1_mosaic_java_12day.py \
    --input-dir workspace/preprocessed_50m \
    --output-dir workspace/mosaics_50m \
    --year 2024 \
    --extent 106.5 -7.0 107.5 -6.0  # minx miny maxx maxy (WGS84)
```

### Different Compositing Methods

**Median (recommended)**: Robust to outliers
```bash
--composite-method median
```

**Mean**: Smoother but sensitive to outliers
```bash
--composite-method mean
```

**First**: Just use first scene in each track (fastest, no compositing)
```bash
--composite-method first
```

---

## Expected Processing Time

**For Java Island (~14 scenes × 31 periods = ~434 scenes):**

| Step | Time | Output |
|------|------|--------|
| Track compositing | 10-20 min | 3 tracks × 31 periods = ~93 files |
| Mosaicking | 30-40 min | 31 period mosaics |
| Stacking | 5-10 min | 1 final stack |
| **Total** | **45-70 min** | Ready for ML! |

**Disk space:**
- Intermediate tracks: ~20 GB (auto-deleted)
- Period mosaics: ~8 GB
- Final stack: ~3 GB
- **Total needed**: ~12 GB

---

## Troubleshooting

### "No scenes found"
Check that preprocessing output files match pattern `*_VH_*.tif`:
```bash
ls workspace/preprocessed_50m/*_VH_50m.tif | head
```

### "Could not parse filename"
Ensure files follow S1 naming convention:
```
S1A_IW_GRDH_1SDV_20240115T105050_20240115T105115_052101_064C13_ABCD_VH_50m.tif
```

### "gdalwarp failed"
Check GDAL installation:
```bash
which gdalwarp
gdalwarp --version
```

If not found:
```bash
conda install -c conda-forge gdal
```

### Different number of scenes than expected

Java Island typically covered by **3 relative orbits** (tracks):
- Ascending track 1
- Ascending track 2
- Descending track

Each track covers ~1/3 of Java with overlap.

Check grouping:
```bash
# The script will print:
Period  1: 3 tracks, 14 scenes total
  Track  18: 5 scenes
  Track  120: 4 scenes
  Track 193: 5 scenes
```

If you see 1 track only → All scenes from same orbit (rare for Java-wide)
If you see 10+ tracks → Scenes from many orbits (check if covering larger area?)

---

## Comparison with SNAP Mosaic

| Feature | This Script | SNAP Mosaic Tool |
|---------|-------------|------------------|
| **Automation** | Fully automated | Manual setup per period |
| **Speed** | Fast (GDAL optimized) | Slower (GUI-based) |
| **Reproducibility** | Perfect (scripted) | Manual (GUI clicks) |
| **Radiometric consistency** | Track-based natural | Manual normalization |
| **Memory usage** | Low (streaming) | High (loads all in memory) |
| **Best for** | Operational/large-scale | Research/small areas |

---

## Next Steps After Mosaicking

Once you have `java_vh_stack_2024_31bands.tif`:

### 1. Verify Stack
```bash
gdalinfo workspace/java_vh_stack_2024_31bands.tif
# Should show: 31 bands, Float32, Java extent
```

### 2. Visualize
```python
import rasterio
import matplotlib.pyplot as plt

with rasterio.open('workspace/java_vh_stack_2024_31bands.tif') as src:
    # Show period 15 (mid-year)
    plt.imshow(src.read(15), cmap='gray', vmin=-20, vmax=-5)
    plt.title('Period 15 (May 25 - Jun 5)')
    plt.colorbar(label='VH backscatter (dB)')
    plt.show()
```

### 3. Train Model
```bash
python train.py
```

### 4. Generate Predictions
```bash
# Predict rice stage for period 15
python predict.py --period 15
```

---

## Why Not Histogram Matching?

Histogram matching works well for **optical imagery** where:
- Radiometry can vary significantly (haze, illumination, seasons)
- Visual appearance matters
- Absolute radiometry less critical

For **SAR backscatter**:
- ✅ Physical quantity (σ°) should be preserved
- ✅ Track-based radiometry already consistent
- ✅ Median compositing handles variations
- ❌ Histogram matching can distort physical signal
- ❌ May harm ML model (training expects real σ° values)

**Exception**: If you notice significant radiometric differences between tracks AFTER mosaicking, you could apply **relative radiometric normalization** as post-processing. But test first - track-based compositing usually sufficient.

---

## Summary

**Your approach**: Good instinct about overlap handling, but sequential processing has drawbacks

**This approach**:
- Groups by track FIRST (natural radiometric consistency)
- Composites within track (temporal noise reduction)
- Mosaics automatically (optimal blending)
- Preserves physical signal (no arbitrary normalization)

**Bottom line**: This will give you better, more consistent results with less effort!
