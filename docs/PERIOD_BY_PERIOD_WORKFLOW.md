# Period-by-Period Workflow for Java Island

## Your Approach (BETTER than bulk download!)

**Workflow:**
```
Period 1: Search ASF → Download to downloads_1/ → Preprocess → Mosaic → Done!
Period 2: Search ASF → Download to downloads_2/ → Preprocess → Mosaic → Done!
...
Period 31: Search ASF → Download to downloads_31/ → Preprocess → Mosaic → Done!

Final: Stack all 31 mosaics → java_vh_stack_2024_31bands.tif
```

## Advantages ✅

1. **Progressive**: Start with important periods (growing season)
2. **Manageable**: ~100-150 scenes per period vs 3,600 at once
3. **Less storage**: ~100-150 GB working space vs 3.3 TB
4. **Faster results**: Get period 15 working in 1 day!
5. **Error recovery**: Easier to fix issues per period
6. **Prioritization**: Focus on rice growing season first

---

## Step-by-Step Guide

### Step 1: Search & Download via ASF Web (Per Period)

#### For Period 1 (Jan 1-12, 2024)

**1. Go to ASF Vertex:** https://search.asf.alaska.edu/

**2. Draw Java AOI:**
- Click polygon tool
- Draw around Java Island
- Or use coordinates:
  - Min Lon: 105.0
  - Max Lon: 116.0
  - Min Lat: -9.0
  - Max Lat: -5.0

**3. Set Filters:**
```
Dataset: Sentinel-1
Product Type: GRD_HD (High Resolution)
Beam Mode: IW
Start Date: 2024-01-01
End Date: 2024-01-12
Flight Direction: ASCENDING
```

**4. Click Search**
- Should show ~100-150 scenes for Period 1

**5. Download:**
- Select all results
- Click "Queue" (top right)
- Click "Download" (creates download script)
- Or use "Bulk Download" option

**6. Save to period folder:**
```bash
mkdir -p workspace/downloads_1
# Move all .zip files to workspace/downloads_1/
```

#### For Period 2 (Jan 13-24, 2024)

Repeat above with:
```
Start Date: 2024-01-13
End Date: 2024-01-24
```

Save to `workspace/downloads_2/`

**Continue for all 31 periods...**

---

## Period Date Ranges Reference

Use this table for ASF search dates:

| Period | Start Date | End Date | Season |
|--------|-----------|----------|---------|
| 1 | 2024-01-01 | 2024-01-12 | Dry |
| 2 | 2024-01-13 | 2024-01-24 | Dry |
| 3 | 2024-01-25 | 2024-02-05 | Dry |
| 4 | 2024-02-06 | 2024-02-17 | Dry |
| 5 | 2024-02-18 | 2024-02-29 | Dry |
| 6 | 2024-03-01 | 2024-03-12 | Dry |
| 7 | 2024-03-13 | 2024-03-24 | Dry→Wet |
| 8 | 2024-03-25 | 2024-04-05 | Wet |
| 9 | 2024-04-06 | 2024-04-17 | Wet |
| 10 | 2024-04-18 | 2024-04-29 | Wet |
| 11 | 2024-04-30 | 2024-05-11 | Wet |
| **12** | **2024-05-12** | **2024-05-23** | **Growing** ⭐ |
| **13** | **2024-05-24** | **2024-06-04** | **Growing** ⭐ |
| **14** | **2024-06-05** | **2024-06-16** | **Growing** ⭐ |
| **15** | **2024-06-17** | **2024-06-28** | **Growing** ⭐ |
| **16** | **2024-06-29** | **2024-07-10** | **Growing** ⭐ |
| **17** | **2024-07-11** | **2024-07-22** | **Growing** ⭐ |
| **18** | **2024-07-23** | **2024-08-03** | **Growing** ⭐ |
| **19** | **2024-08-04** | **2024-08-15** | **Growing** ⭐ |
| **20** | **2024-08-16** | **2024-08-27** | **Growing** ⭐ |
| 21 | 2024-08-28 | 2024-09-08 | Wet |
| 22 | 2024-09-09 | 2024-09-20 | Wet |
| 23 | 2024-09-21 | 2024-10-02 | Wet |
| 24 | 2024-10-03 | 2024-10-14 | Wet |
| 25 | 2024-10-15 | 2024-10-26 | Wet→Dry |
| 26 | 2024-10-27 | 2024-11-07 | Dry |
| 27 | 2024-11-08 | 2024-11-19 | Dry |
| 28 | 2024-11-20 | 2024-12-01 | Dry |
| 29 | 2024-12-02 | 2024-12-13 | Dry |
| 30 | 2024-12-14 | 2024-12-25 | Dry |
| 31 | 2024-12-26 | 2024-12-31 | Dry |

⭐ **Priority: Start with periods 12-20 (growing season)**

---

## Step 2: Process Each Period

Once you have downloads for a period:

```bash
# Example for Period 15

# 1. Preprocess
python s1_preprocess_parallel_multiresolution.py \
    --input-dir workspace/downloads_15 \
    --output-dir workspace/preprocessed_15 \
    --resolution 50 \
    --workers 8

# 2. Mosaic (single period)
python s1_mosaic_single_period.py \
    --input-dir workspace/preprocessed_15 \
    --output workspace/mosaics/period_15_mosaic.tif \
    --period 15 \
    --year 2024 \
    --resolution 50
```

I'll create the single-period mosaicking script below.

---

## Step 3: Stack All Periods (After All Done)

Once you have all 31 period mosaics:

```bash
# Stack into final 31-band GeoTIFF
python stack_period_mosaics.py \
    --mosaic-dir workspace/mosaics \
    --output workspace/java_vh_stack_2024_31bands.tif
```

---

## Recommended Order (Smart Strategy)

### Phase 1: Growing Season (First!)
**Periods 12-20** (May-Aug, rice growing)
- Most important for rice mapping
- ~900 scenes total
- **Can start training with just these!**

**Time:** 3-5 days
**Storage:** ~800 GB working space

### Phase 2: Wet Season
**Periods 7-11, 21-24** (Mar-Apr, Sep-Oct)
- Planting and harvest periods
- ~600 scenes

**Time:** 2-3 days
**Storage:** ~500 GB

### Phase 3: Dry Season
**Periods 1-6, 25-31** (rest of year)
- Background/baseline
- ~500 scenes

**Time:** 2-3 days
**Storage:** ~400 GB

**Total:** ~1 week with parallel work, but can start training after Phase 1!

---

## Per-Period Storage Requirements

**For each period:**
```
Downloads (raw):     ~100-150 scenes × 800 MB = 80-120 GB
Preprocessed:        ~100-150 scenes × 80 MB = 8-12 GB
Mosaic:             1 file × 3 GB = 3 GB
────────────────────────────────────────────────────
Working space:      ~100-150 GB
Keep after cleanup: ~3 GB (just the mosaic)
```

**Progressive strategy:**
```bash
# Process one period
Download period N → Preprocess → Mosaic → DELETE raw & preprocessed
# Now you only keep the 3 GB mosaic

# Move to next period
Download period N+1 → Preprocess → Mosaic → DELETE raw & preprocessed

# Total space needed at any time: ~150 GB working + ~100 GB for all mosaics
```

**Total minimum:** ~250 GB (vs 3.3 TB for bulk approach!)

---

## Automated Period Date Generator

I'll create a script to generate all ASF search URLs for you:

```bash
python generate_asf_search_urls.py

# Outputs:
Period 1: https://search.asf.alaska.edu/?...&start=2024-01-01&end=2024-01-12
Period 2: https://search.asf.alaska.edu/?...&start=2024-01-13&end=2024-01-24
...
```

Just click each link, search, and download!

---

## Monitoring Progress

Track which periods you've completed:

```bash
python check_period_status.py

# Shows:
Period 1:  ✓ Downloaded ✓ Preprocessed ✓ Mosaicked
Period 2:  ✓ Downloaded ✓ Preprocessed ✗ Not mosaicked
Period 3:  ✓ Downloaded ✗ Not preprocessed
Period 4:  ✗ Not started
...
Period 15: ✓ Downloaded ✓ Preprocessed ✓ Mosaicked
```

---

## Comparison: Your Approach vs Bulk Download

| Aspect | Your Period-by-Period | Bulk Download |
|--------|----------------------|---------------|
| **Storage** | 250 GB minimum | 3.3 TB |
| **Start training** | After first 9 periods (~3 days) | After all done (~1 week) |
| **Error recovery** | Easy (just one period) | Hard (3,600 scenes) |
| **Prioritization** | Yes (growing season first) | No (all or nothing) |
| **Parallel work** | Yes (multiple machines) | Limited |
| **Management** | Simple (one period at a time) | Complex (track 3,600 files) |
| **Flexibility** | High (skip periods if needed) | Low (download all) |

**Winner:** Your approach! 🏆

---

## Example: Complete Workflow for Period 15

```bash
# 1. Search ASF (manual via web)
#    Date: 2024-06-17 to 2024-06-28
#    AOI: Java Island
#    Result: ~120 scenes

# 2. Download to period folder
mkdir workspace/downloads_15
# ... download all .zip files ...

# 3. Preprocess (2-3 hours)
python s1_preprocess_parallel_multiresolution.py \
    --input-dir workspace/downloads_15 \
    --output-dir workspace/preprocessed_15 \
    --resolution 50 \
    --workers 8

# 4. Mosaic (5-10 minutes)
python s1_mosaic_single_period.py \
    --input-dir workspace/preprocessed_15 \
    --output workspace/mosaics/period_15_mosaic.tif \
    --period 15

# 5. Verify
gdalinfo workspace/mosaics/period_15_mosaic.tif

# 6. Cleanup (optional, saves space)
rm -rf workspace/downloads_15
rm -rf workspace/preprocessed_15

# 7. Repeat for next period!
```

---

## Next Steps

I'll create:
1. ✅ Single-period mosaicking script
2. ✅ ASF search URL generator
3. ✅ Period progress tracker
4. ✅ Period stacking script (combine all 31 mosaics)

Ready to proceed?
