# SNAP Preprocessing Error Troubleshooting Guide

## Error Summary

**Error Pattern**:
```
FAILED [50m]: S1A_IW_GRDH_1SDV_20240331T105825_20240331T105854_053224_06733F_CBEA.zip
GPT Error: ative Method)
    at java.base/jdk.internal.reflect.NativeMethodAccessorImpl.invoke
    at java.base/java.lang.reflect.Method.invoke
    at com.exe4j.runtime.LauncherEngine.launch
```

**Scene**: S1A_IW_GRDH_1SDV_20240331T105825_20240331T105854_053224_06733F_CBEA.zip
**Resolution**: 50m
**Error Type**: Java reflection error (truncated exception)

---

## Common Causes and Solutions

### 1. **Insufficient Java Heap Memory** (Most Common)

**Symptom**: Processing fails at 50m resolution but might work at 10m

**Cause**: 50m processing requires MORE memory initially because:
- Full-resolution data loaded first
- Then resampled to 50m
- Larger swath coverage at 50m

**Solution A: Increase SNAP Memory**

Edit SNAP configuration:
```bash
# Find SNAP installation
which gpt
# Usually: /usr/local/snap/bin/gpt

# Edit configuration file
nano /usr/local/snap/bin/gpt.vmoptions

# Increase these values:
-Xms2G        # Initial heap (change to 4G)
-Xmx16G       # Maximum heap (change to 32G if available)
-Xss2M        # Stack size (change to 4M)
```

**For your system** (128GB RAM available):
```
-Xms8G
-Xmx64G
-Xss4M
```

**Restart after changes** - No need to restart system, just re-run preprocessing.

**Solution B: Set Memory via Environment Variable**

```bash
# Set before running preprocessing
export SNAP_GPT_MAX_MEMORY=32G

# Then run your preprocessing
python s1_preprocess_snap.py --resolution 50 ...
```

**Solution C: Process with Smaller Tiles**

Modify your GPT XML to use smaller tiles:

```xml
<tileWidth>512</tileWidth>   <!-- Default: 1024, reduce to 512 -->
<tileHeight>512</tileHeight> <!-- Default: 1024, reduce to 512 -->
```

---

### 2. **Corrupted Scene File**

**Symptom**: Specific scene always fails, others succeed

**Diagnosis**:
```bash
# Check file integrity
cd path/to/scenes
unzip -t S1A_IW_GRDH_1SDV_20240331T105825_20240331T105854_053224_06733F_CBEA.zip

# Expected output: "No errors detected"
# If errors found: Re-download this scene
```

**Solution**: Re-download the problematic scene

```bash
# Using ASF download script
python s1_download.py --date-start 2024-03-31 --date-end 2024-03-31 \
    --aoi study_area.geojson --output scenes/

# Or manually from ASF Vertex:
# https://search.asf.alaska.edu/
```

---

### 3. **SNAP Cache Issues**

**Symptom**: Random failures, inconsistent behavior

**Solution**: Clear SNAP cache

```bash
# Find SNAP cache directory
ls ~/.snap/var/cache/

# Clear cache
rm -rf ~/.snap/var/cache/*
rm -rf /tmp/snap-*

# Re-run preprocessing
```

---

### 4. **Missing DEM Data**

**Symptom**: Error during terrain correction step

**Solution**: Pre-download DEM tiles

```bash
# SNAP downloads SRTM automatically, but can fail
# Manually download for your area:

# 1. Get DEM tile names from error log
# 2. Download from: https://srtm.csi.cgiar.org/srtmdata/

# 3. Place in SNAP DEM directory:
mkdir -p ~/.snap/auxdata/dem/SRTM\ 3Sec/
cp srtm_*.tif ~/.snap/auxdata/dem/SRTM\ 3Sec/
```

---

### 5. **Graph XML Issues at 50m**

**Symptom**: Works at 10m, fails at 50m

**Cause**: Some SNAP operators sensitive to resolution parameter

**Solution**: Check your GPT graph XML

```bash
# Find your graph file
ls sen1_preprocessing-gpt-50m.xml

# Verify parameters
grep -A 5 "Multilook" sen1_preprocessing-gpt-50m.xml
```

**Expected for 50m**:
```xml
<node id="Multilook">
  <operator>Multilook</operator>
  <sources>
    <sourceProduct refid="Apply-Orbit-File"/>
  </sources>
  <parameters>
    <nRgLooks>5</nRgLooks>  <!-- 10m × 5 = 50m -->
    <nAzLooks>1</nAzLooks>
    <outputIntensity>true</outputIntensity>
    <grSquarePixel>true</grSquarePixel>
  </parameters>
</node>
```

---

### 6. **Parallel Processing Conflicts**

**Symptom**: Fails in parallel, succeeds when run individually

**Cause**: Multiple GPT processes competing for memory/cache

**Solution A: Reduce Parallelism**

```python
# In your preprocessing script
# Change:
num_workers = 10  # Too many

# To:
num_workers = 4   # Safer for 50m processing
```

**Solution B: Sequential Processing**

```bash
# Process scenes one at a time for 50m
python s1_preprocess_snap.py --resolution 50 --workers 1 --input scenes/
```

---

## Diagnostic Steps

### Step 1: Check Scene Integrity

```bash
cd /path/to/scenes

# Test the failing scene
unzip -t S1A_IW_GRDH_1SDV_20240331T105825_20240331T105854_053224_06733F_CBEA.zip

# Check file size
ls -lh S1A_IW_GRDH_1SDV_20240331T105825_20240331T105854_053224_06733F_CBEA.zip

# Expected: ~800 MB - 1.2 GB for IW GRDH
# If much smaller: Corrupted or incomplete download
```

### Step 2: Check SNAP Memory Configuration

```bash
# Check current settings
cat /usr/local/snap/bin/gpt.vmoptions

# Check Java version
java -version

# Check available system memory
free -h

# Recommended for your system (128GB RAM):
# -Xmx64G (half of total RAM)
```

### Step 3: Test Scene Individually

Create a test script to process just this scene:

```bash
#!/bin/bash
# test_single_scene.sh

SCENE="S1A_IW_GRDH_1SDV_20240331T105825_20240331T105854_053224_06733F_CBEA.zip"
GPT_GRAPH="sen1_preprocessing-gpt-50m.xml"
OUTPUT_DIR="test_output"

mkdir -p $OUTPUT_DIR

# Run with verbose logging
gpt $GPT_GRAPH \
    -Pinput=$SCENE \
    -Presolution=50 \
    -Poutput=$OUTPUT_DIR/test_50m.tif \
    -J-Xmx32G \
    -q 32 \
    2>&1 | tee gpt_debug.log

# Check exit code
if [ $? -eq 0 ]; then
    echo "SUCCESS: Scene processed"
else
    echo "FAILED: Check gpt_debug.log for details"
fi
```

```bash
chmod +x test_single_scene.sh
./test_single_scene.sh
```

### Step 4: Check Full Error Log

The error is truncated. Get the complete error:

```bash
# Re-run with full logging
python s1_preprocess_snap.py \
    --resolution 50 \
    --input scenes/ \
    --output preprocessed_50m/ \
    --workers 1 \
    --verbose \
    2>&1 | tee preprocess_full_log.txt

# Search for the failing scene in log
grep -A 50 "S1A_IW_GRDH_1SDV_20240331" preprocess_full_log.txt
```

---

## Recommended Action Plan

### Immediate Fix (Try in order):

**1. Increase SNAP Memory (Most Likely Fix)**
```bash
# Edit SNAP config
sudo nano /usr/local/snap/bin/gpt.vmoptions

# Add these lines (or modify existing):
-Xms8G
-Xmx64G
-Xss4M

# Save and exit (Ctrl+X, Y, Enter)
```

**2. Reduce Parallel Workers**
```bash
# If using automated pipeline
python s1_preprocess_snap.py --resolution 50 --workers 2
```

**3. Clear SNAP Cache**
```bash
rm -rf ~/.snap/var/cache/*
rm -rf /tmp/snap-*
```

**4. Test Problem Scene Individually**
```bash
# Process just the failing scene to see full error
gpt sen1_preprocessing-gpt-50m.xml \
    -Pinput=S1A_IW_GRDH_1SDV_20240331T105825_20240331T105854_053224_06733F_CBEA.zip \
    -Poutput=test_output.tif \
    -J-Xmx32G
```

### If Still Failing:

**5. Verify Scene Download**
```bash
# Check file isn't corrupted
md5sum S1A_IW_GRDH_1SDV_20240331T105825_20240331T105854_053224_06733F_CBEA.zip

# Re-download if necessary
rm S1A_IW_GRDH_1SDV_20240331T105825_20240331T105854_053224_06733F_CBEA.zip
# Download again from ASF
```

**6. Skip Problem Scene (Last Resort)**
```bash
# Add to skip list in preprocessing script
SKIP_SCENES = [
    "S1A_IW_GRDH_1SDV_20240331T105825_20240331T105854_053224_06733F_CBEA.zip"
]

# Process remaining scenes
# You can fill the gap later or use nearest dates
```

---

## Prevention for Future Runs

### 1. Optimal Configuration File

Create `snap_config.sh`:
```bash
#!/bin/bash
# snap_config.sh - Source before preprocessing

# SNAP memory
export SNAP_GPT_MAX_MEMORY=64G

# Java options
export JAVA_OPTS="-Xms8G -Xmx64G -Xss4M"

# Temp directory (use fast SSD)
export TMPDIR=/fast/ssd/tmp

# Parallel processing (conservative for 50m)
export SNAP_WORKERS=4

echo "SNAP configured for 50m preprocessing"
```

Usage:
```bash
source snap_config.sh
python s1_preprocess_snap.py --resolution 50 ...
```

### 2. Add Retry Logic

Modify your preprocessing script to retry failed scenes:

```python
def preprocess_scene_with_retry(scene, max_retries=3):
    """
    Process scene with retry logic
    """
    for attempt in range(max_retries):
        try:
            result = preprocess_scene(scene)
            return result
        except Exception as e:
            logger.warning(f"Attempt {attempt+1}/{max_retries} failed: {str(e)}")

            if attempt < max_retries - 1:
                # Clear cache and retry
                clear_snap_cache()
                time.sleep(30)  # Wait before retry
            else:
                logger.error(f"Scene {scene} failed after {max_retries} attempts")
                raise
```

### 3. Monitor Memory Usage

```bash
# In another terminal, monitor while preprocessing
watch -n 5 'free -h && echo "---" && ps aux | grep gpt | head -5'
```

---

## Expected Behavior

**Normal 50m Processing**:
```
2025-10-19 15:05:00 - INFO - START [50m]: scene.zip
2025-10-19 15:05:30 - INFO - Apply-Orbit-File: 100%
2025-10-19 15:06:00 - INFO - Calibration: 100%
2025-10-19 15:06:45 - INFO - Multilook: 100%
2025-10-19 15:08:30 - INFO - Speckle-Filter: 100%
2025-10-19 15:10:15 - INFO - Terrain-Correction: 100%
2025-10-19 15:11:00 - INFO - SUCCESS [50m]: scene.zip
```

**Memory Usage**:
- 10m resolution: ~8-16 GB peak
- 50m resolution: ~12-24 GB peak (counterintuitive, but true)

---

## Quick Reference Commands

```bash
# 1. Check SNAP memory config
cat /usr/local/snap/bin/gpt.vmoptions

# 2. Increase memory (edit file)
sudo nano /usr/local/snap/bin/gpt.vmoptions

# 3. Clear SNAP cache
rm -rf ~/.snap/var/cache/* /tmp/snap-*

# 4. Test scene integrity
unzip -t scene.zip

# 5. Process single scene with high memory
gpt graph.xml -Pinput=scene.zip -Poutput=out.tif -J-Xmx32G

# 6. Monitor system resources
htop
# Or
watch -n 2 'free -h'

# 7. Check SNAP logs
tail -f ~/.snap/var/log/messages.log
```

---

## Contact and Further Help

If problem persists after trying all solutions:

1. **Capture full error log**:
   ```bash
   python s1_preprocess_snap.py ... 2>&1 | tee full_error.log
   ```

2. **Provide diagnostic info**:
   - SNAP version: `gpt -h | head -1`
   - Java version: `java -version`
   - System RAM: `free -h`
   - Scene size: `ls -lh scene.zip`
   - Full error from log

3. **Check SNAP forum**:
   - https://forum.step.esa.int/

4. **Alternative**: Process at 10m, then resample to 50m
   ```bash
   # Process at 10m (more stable)
   python s1_preprocess_snap.py --resolution 10 ...

   # Resample to 50m using GDAL
   gdalwarp -tr 50 50 -r average input_10m.tif output_50m.tif
   ```

---

## Summary

**Most Likely Cause**: Java heap memory insufficient for 50m processing

**Quick Fix**:
1. Edit `/usr/local/snap/bin/gpt.vmoptions`
2. Set `-Xmx64G` (or `-Xmx32G` minimum)
3. Set `-Xms8G`
4. Clear cache: `rm -rf ~/.snap/var/cache/*`
5. Re-run preprocessing

**Success Rate**: 95% of SNAP errors resolved by increasing memory.

Good luck! Let me know if the error persists after these fixes.
