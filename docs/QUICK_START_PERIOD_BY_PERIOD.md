# Quick Start: Period-by-Period Approach

## Why This Works Better

✅ **250 GB** minimum storage (vs 3.3 TB bulk)
✅ **Start training** after first 9 periods (vs waiting for all 31)
✅ **Easy management** (one period at a time)
✅ **Flexible** (prioritize growing season)
✅ **Error recovery** (just redo one period)

---

## Complete Example: Period 15 (Growing Season)

### Step 1: Generate ASF Search URLs

```bash
# Generate all search URLs
python generate_asf_search_urls.py --html

# This creates asf_urls_2024.html
# Open in browser - contains clickable links for all 31 periods
```

### Step 2: Download Period 15 from ASF

**A. Via HTML file (easiest):**
1. Open `asf_urls_2024.html` in browser
2. Click "Period 15" link (marked ⭐ PRIORITY)
3. ASF Vertex opens with search results
4. Select all results (~120 scenes)
5. Click "Queue" → "Download"
6. Save all .zip files to `workspace/downloads_15/`

**B. Via ASF Vertex manually:**
1. Go to https://search.asf.alaska.edu/
2. Draw polygon around Java or enter coordinates:
   ```
   Min Lon: 105.0, Max Lon: 116.0
   Min Lat: -9.0, Max Lat: -5.0
   ```
3. Set filters:
   ```
   Dataset: Sentinel-1
   Product Type: GRD_HD
   Beam Mode: IW
   Start Date: 2024-06-17
   End Date: 2024-06-28
   Flight Direction: ASCENDING
   ```
4. Click Search → Select All → Download
5. Save to `workspace/downloads_15/`

**Expected:** ~120 scenes, ~95 GB

### Step 3: Preprocess Period 15

```bash
python s1_preprocess_parallel_multiresolution.py \
    --input-dir workspace/downloads_15 \
    --output-dir workspace/preprocessed_15 \
    --resolution 50 \
    --workers 8
```

**Time:** 2-3 hours
**Output:** ~120 VH GeoTIFFs (~9 GB)

### Step 4: Mosaic Period 15

```bash
python s1_mosaic_single_period.py \
    --input-dir workspace/preprocessed_50m/p1 \
    --output workspace/mosaics_50m/period_15_mosaic.tif \
    --period 1 \
    --year 2024 \
    --resolution 50
```

**Time:** 5-10 minutes
**Output:** `period_15_mosaic.tif` (~3 GB)

### Step 5: Verify

```bash
gdalinfo workspace/mosaics/period_15_mosaic.tif

# Should show:
# Size: ~12000 x 8000 (Java coverage)
# Bands: 1
# Type: Float32
# NoData: -32768
```

### Step 6: Clean Up (Optional - Saves Space!)

```bash
# Delete raw downloads (saves ~95 GB)
rm -rf workspace/downloads_15

# Delete preprocessed (saves ~9 GB)
rm -rf workspace/preprocessed_15

# Keep only the mosaic (3 GB)
```

**Done!** Period 15 complete. Repeat for other periods.

---

## Recommended Order

### Phase 1: Growing Season (START HERE!)

**Periods 12-20** (May-August, rice growing season)

```bash
# Generate URLs
python generate_asf_search_urls.py --html

# For each period 12-20:
# 1. Download from ASF → workspace/downloads_N/
# 2. Preprocess
python s1_preprocess_parallel_multiresolution.py \
    --input-dir workspace/downloads_N \
    --output-dir workspace/preprocessed_N \
    --resolution 50 --workers 8

# 3. Mosaic
python s1_mosaic_single_period.py \
    --input-dir workspace/preprocessed_N \
    --output workspace/mosaics/period_NN_mosaic.tif \
    --period N

# 4. Clean up
rm -rf workspace/downloads_N workspace/preprocessed_N
```

**After 9 periods (12-20):** You can start training!

```bash
# Stack just these 9 periods for initial training
python stack_period_mosaics.py \
    --mosaic-dir workspace/mosaics \
    --output workspace/java_vh_stack_2024_growing_season.tif

# Train model
python train.py  # Update config to point to this stack
```

### Phase 2: Complete the Rest

**Periods 1-11, 21-31** (remaining periods)

Use same workflow. Can do in parallel if you have multiple machines!

### Phase 3: Final Stack

```bash
# Once all 31 periods done
python stack_period_mosaics.py \
    --mosaic-dir workspace/mosaics \
    --output workspace/java_vh_stack_2024_31bands.tif
```

---

## Batch Processing Script

For convenience, here's a bash script to automate one period:

```bash
#!/bin/bash
# process_period.sh

PERIOD=$1
if [ -z "$PERIOD" ]; then
    echo "Usage: ./process_period.sh <period_number>"
    exit 1
fi

echo "Processing Period $PERIOD"
echo "================================"

# Preprocess
echo "Step 1: Preprocessing..."
python s1_preprocess_parallel_multiresolution.py \
    --input-dir workspace/downloads_$PERIOD \
    --output-dir workspace/preprocessed_$PERIOD \
    --resolution 50 \
    --workers 8

if [ $? -ne 0 ]; then
    echo "ERROR: Preprocessing failed"
    exit 1
fi

# Mosaic
echo "Step 2: Mosaicking..."
python s1_mosaic_single_period.py \
    --input-dir workspace/preprocessed_$PERIOD \
    --output workspace/mosaics/period_$(printf "%02d" $PERIOD)_mosaic.tif \
    --period $PERIOD \
    --year 2024 \
    --resolution 50

if [ $? -ne 0 ]; then
    echo "ERROR: Mosaicking failed"
    exit 1
fi

# Clean up
echo "Step 3: Cleaning up..."
echo "Delete downloads_$PERIOD? (y/n)"
read -r response
if [ "$response" = "y" ]; then
    rm -rf workspace/downloads_$PERIOD
    rm -rf workspace/preprocessed_$PERIOD
    echo "✓ Cleaned up intermediate files"
fi

echo "✓ Period $PERIOD complete!"
```

**Usage:**
```bash
chmod +x process_period.sh

# After downloading Period 15 from ASF:
./process_period.sh 15
```

---

## Timeline Estimate

### For 9 Growing Season Periods (12-20)

| Step | Time per Period | Total for 9 Periods |
|------|----------------|---------------------|
| Download (manual) | 30-60 min | 4-9 hours |
| Preprocess | 2-3 hours | 18-27 hours |
| Mosaic | 5-10 min | 45-90 min |
| **Total** | **3-4 hours** | **~1.5-2 days** |

**With parallel work (2 machines):** ~1 day!

### For All 31 Periods

**Sequential:** 4-5 days
**Parallel (2 machines):** 2-3 days
**Parallel (3+ machines):** 1-2 days

---

## Storage Requirements

### Per Period
```
Downloads:      80-120 GB
Preprocessed:   8-12 GB
Mosaic:         3 GB
─────────────────────────
Working space:  ~120 GB
Keep (mosaic):  3 GB
```

### Total (All 31 Periods)
```
If you delete after each period:
  Working space:  120 GB (reused each period)
  Final mosaics:  93 GB (31 × 3 GB)
  ──────────────────────
  Total:          ~220 GB

If you keep everything:
  Downloads:      2.9 TB
  Preprocessed:   290 GB
  Mosaics:        93 GB
  ──────────────────────
  Total:          3.3 TB
```

**Recommended:** Delete after each period, keep only mosaics (~220 GB total)

---

## Troubleshooting

### "No scenes found in downloads_N/"
- Check folder name matches exactly
- Verify .zip files are fully downloaded
- Try: `ls workspace/downloads_15/*.zip | wc -l`

### "Mosaic is empty (all nodata)"
- Check if preprocessed files have data
- Try: `gdalinfo workspace/preprocessed_15/<first_file>.tif`
- May need to adjust extent in mosaic command

### "Preprocessing very slow"
- Reduce workers: `--workers 4`
- Check disk I/O (not CPU bound)
- Consider external SSD for workspace/

---

## Advantages Over Your Current Data

| Metric | Current (369 scenes) | After Phase 1 (9 periods) | After All (31 periods) |
|--------|---------------------|--------------------------|------------------------|
| Scenes | 369 | ~1,080 | ~3,600 |
| Coverage per period | 10% | 100% ✓ | 100% ✓ |
| Complete periods | 0/31 | 9/31 | 31/31 ✓ |
| Can train? | No | Yes! ✓ | Yes! ✓ |
| Java-wide mapping | No | Growing season only | All year ✓ |

---

## Next Steps

1. **Generate URLs:**
   ```bash
   python generate_asf_search_urls.py --html
   ```

2. **Start with Period 15:**
   - Open HTML, click Period 15 link
   - Download to `workspace/downloads_15/`
   - Run preprocessing & mosaicking
   - Verify result

3. **Continue with 12-20:**
   - Same process for each period
   - After 9 periods: stack and train!

4. **Complete the rest (1-11, 21-31):**
   - Can do in parallel
   - Final stack when done

---

**Ready to start?** Generate the URLs and download Period 15! 🚀
