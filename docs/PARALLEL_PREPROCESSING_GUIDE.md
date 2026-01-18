# Parallel Sentinel-1 Preprocessing Guide

Complete guide for parallel processing of Sentinel-1 SAR data using SNAP GPT with optimized memory management and multi-core utilization.

## Table of Contents

- [Overview](#overview)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage Examples](#usage-examples)
- [Performance Optimization](#performance-optimization)
- [Monitoring Progress](#monitoring-progress)
- [Troubleshooting](#troubleshooting)
- [Advanced Configuration](#advanced-configuration)

---

## Overview

The parallel preprocessing system processes multiple Sentinel-1 GRD scenes simultaneously using Python's multiprocessing, dramatically reducing total processing time from weeks to days.

### Key Features

✅ **Parallel Processing** - Process 4-10 scenes simultaneously
✅ **Automatic Memory Management** - Allocates RAM per worker
✅ **Resume Capability** - Automatically skips processed files
✅ **Progress Tracking** - JSON status file for monitoring
✅ **Error Handling** - Robust retry logic and logging
✅ **Automatic Cleanup** - Removes temporary BEAM-DIMAP files
✅ **VH Band Extraction** - Outputs ready-to-use VH GeoTIFFs

### Processing Chain

For each Sentinel-1 scene, the pipeline applies:

1. **Apply Orbit File** - Precise orbit information
2. **Thermal Noise Removal** - Remove sensor noise
3. **Calibration** - Convert to Beta0 backscatter
4. **Terrain Flattening** - Normalize for terrain effects
5. **Terrain Correction** - Orthorectification (Range Doppler)
6. **Speckle Filtering** - Gamma MAP 5×5 filter
7. **Linear to dB** - Convert to decibel scale
8. **VH Band Extraction** - Extract VH polarization to GeoTIFF

---

## System Requirements

### Minimum Requirements

- **RAM:** 32GB (for 1 worker)
- **CPU:** 4 cores
- **Disk Space:** 10-15GB per scene output
- **OS:** Linux, macOS, or Windows
- **SNAP:** ESA SNAP 11.0 or later

### Recommended for Parallel Processing

- **RAM:** 512GB - 2TB (for 4-10 workers)
- **CPU:** 64-128 cores
- **Disk:** SSD with 2-3TB free space
- **Network:** Fast connection for orbit files

### Software Dependencies

```bash
# Python packages
pip install gdal

# System requirements
- ESA SNAP installed and configured
- Python 3.8+
- GDAL/OGR libraries
```

---

## Installation

### 1. Install ESA SNAP

Download and install SNAP from:
https://step.esa.int/main/download/snap-download/

### 2. Configure SNAP for High Memory

Edit `$SNAP_HOME/bin/gpt.vmoptions`:

```bash
# Recommended for 2TB RAM system
-Xmx800G                    # Maximum heap size
-Xms64G                     # Initial heap size
-XX:+UseG1GC                # G1 Garbage Collector
-XX:MaxGCPauseMillis=200    # Max GC pause time
-XX:ParallelGCThreads=32    # Parallel GC threads
-XX:ConcGCThreads=8         # Concurrent GC threads
```

### 3. Configure Environment

Add to your `~/.bashrc`:

```bash
# ESA SNAP configuration
export SNAP_HOME=/path/to/esa-snap
export PATH=$SNAP_HOME/bin:$PATH
export SNAP_GPT_MEMORY=800G
```

Apply changes:
```bash
source ~/.bashrc
```

### 4. Verify SNAP Installation

```bash
gpt --diag
```

Expected output:
```
SNAP Release version 11.0.0
Max memory: 800.0 GB
Processors: 128
```

---

## Quick Start

### Basic Usage

```bash
python s1_preprocess_parallel.py \
    --input-dir workspace/downloads \
    --output-dir workspace/preprocessed \
    --workers 4
```

### With Custom Memory Settings

```bash
python s1_preprocess_parallel.py \
    --input-dir workspace/downloads \
    --output-dir workspace/preprocessed \
    --workers 4 \
    --memory 200G \
    --cache 150G
```

### Run in Background (Recommended)

```bash
# Using screen
screen -S snap_preprocess
python s1_preprocess_parallel.py --input-dir workspace/downloads --output-dir workspace/preprocessed --workers 4
# Press Ctrl+A then D to detach
# Reattach: screen -r snap_preprocess

# Using tmux
tmux new -s snap_preprocess
python s1_preprocess_parallel.py --input-dir workspace/downloads --output-dir workspace/preprocessed --workers 4
# Press Ctrl+B then D to detach
# Reattach: tmux attach -t snap_preprocess

# Using nohup
nohup python s1_preprocess_parallel.py --input-dir workspace/downloads --output-dir workspace/preprocessed --workers 4 > preprocess.log 2>&1 &
```

---

## Usage Examples

### Example 1: Conservative Processing (Recommended)

**Best for initial testing and stability**

```bash
python s1_preprocess_parallel.py \
    --input-dir workspace/downloads \
    --output-dir workspace/preprocessed \
    --workers 4 \
    --memory 200G \
    --cache 150G
```

**Configuration:**
- Workers: 4
- RAM per worker: 200GB
- Total RAM: ~800GB
- Expected time: ~4 days (211 scenes)

---

### Example 2: Aggressive Processing

**For faster processing on high-memory systems**

```bash
python s1_preprocess_parallel.py \
    --input-dir workspace/downloads \
    --output-dir workspace/preprocessed \
    --workers 8 \
    --memory 100G \
    --cache 80G
```

**Configuration:**
- Workers: 8
- RAM per worker: 100GB
- Total RAM: ~800GB
- Expected time: ~2 days (211 scenes)

---

### Example 3: Maximum Speed

**Use with caution - monitor system closely**

```bash
python s1_preprocess_parallel.py \
    --input-dir workspace/downloads \
    --output-dir workspace/preprocessed \
    --workers 10 \
    --memory 80G \
    --cache 60G
```

**Configuration:**
- Workers: 10
- RAM per worker: 80GB
- Total RAM: ~800GB
- Expected time: ~1.5 days (211 scenes)

---

### Example 4: Resume Interrupted Processing

**Automatically skips completed files**

```bash
# Just run the same command again
python s1_preprocess_parallel.py \
    --input-dir workspace/downloads \
    --output-dir workspace/preprocessed \
    --workers 4
```

The script will:
- Load `processing_status.json`
- Skip files marked as `completed` or `skipped`
- Continue processing remaining files

---

### Example 5: Custom Graph XML

**Use a different preprocessing workflow**

```bash
python s1_preprocess_parallel.py \
    --input-dir workspace/downloads \
    --output-dir workspace/preprocessed \
    --graph custom_preprocessing.xml \
    --workers 4
```

---

### Example 6: Specific File Pattern

**Process only specific scenes**

```bash
python s1_preprocess_parallel.py \
    --input-dir workspace/downloads \
    --output-dir workspace/preprocessed \
    --pattern "S1A_IW_GRDH_*_202406*.zip" \
    --workers 4
```

---

## Performance Optimization

### Choosing Number of Workers

**Formula:**
```
workers = min(
    available_RAM / 200GB,
    cpu_cores / 16,
    10  # maximum recommended
)
```

**Examples:**

| RAM | CPU Cores | Recommended Workers | RAM Usage |
|-----|-----------|---------------------|-----------|
| 512GB | 64 | 2 | ~400GB |
| 1TB | 128 | 4 | ~800GB |
| 2TB | 128 | 8 | ~800GB |
| 4TB | 256 | 10 | ~1TB |

### Memory Settings

**Per-worker memory formula:**
```
memory_per_worker = available_RAM / workers / 1.2
```

The factor of 1.2 provides 20% buffer for system overhead.

**Examples:**

| Total RAM | Workers | Memory/Worker | Cache/Worker |
|-----------|---------|---------------|--------------|
| 512GB | 2 | 200G | 150G |
| 1TB | 4 | 200G | 150G |
| 2TB | 8 | 100G | 80G |
| 4TB | 10 | 300G | 250G |

### Cache Size Settings

**Recommended:**
```
cache_per_worker = memory_per_worker * 0.75
```

Example:
- Memory: 200GB → Cache: 150GB
- Memory: 100GB → Cache: 75GB

### Performance Comparison

**Processing 211 scenes (typical year of data):**

| Configuration | Workers | Time | Speedup |
|---------------|---------|------|---------|
| Serial (baseline) | 1 | 15 days | 1× |
| Conservative | 4 | 4 days | 4× |
| Aggressive | 8 | 2 days | 8× |
| Maximum | 10 | 1.5 days | 10× |

### Disk I/O Optimization

**Best practices:**

1. **Use SSD** for output directory
2. **Separate disks** for input and output if possible
3. **RAID 0** can improve throughput
4. **NVMe SSD** for maximum performance

**Expected disk usage:**
- Input (compressed): ~1GB per scene
- Temporary files: ~5GB per scene
- Output GeoTIFF: ~2-3GB per scene
- Total: ~200GB input + ~600GB output

---

## Monitoring Progress

### Check Processing Status

**Count completed files:**
```bash
grep -c "completed" workspace/preprocessed/processing_status.json
```

**Count failed files:**
```bash
grep -c "failed" workspace/preprocessed/processing_status.json
```

**Count files in progress:**
```bash
grep -c "processing" workspace/preprocessed/processing_status.json
```

**View detailed status:**
```bash
cat workspace/preprocessed/processing_status.json | jq
```

### Monitor Output Files

**Count processed GeoTIFFs:**
```bash
ls workspace/preprocessed/*.tif | wc -l
```

**Check latest processed file:**
```bash
ls -lt workspace/preprocessed/*.tif | head -1
```

**Calculate progress percentage:**
```bash
total_files=$(ls workspace/downloads/*.zip | wc -l)
processed_files=$(ls workspace/preprocessed/*.tif | wc -l)
echo "Progress: $processed_files / $total_files ($(($processed_files * 100 / $total_files))%)"
```

### Monitor System Resources

**RAM usage:**
```bash
free -h
watch -n 5 free -h  # Update every 5 seconds
```

**CPU usage:**
```bash
top -u $USER
htop  # Better visualization
```

**Disk usage:**
```bash
df -h workspace/preprocessed/
watch -n 60 df -h workspace/preprocessed/  # Monitor disk space
```

**Process monitoring:**
```bash
# Count running SNAP GPT processes
ps aux | grep gpt | grep -v grep | wc -l

# View SNAP processes
ps aux | grep gpt | grep -v grep
```

### Log Monitoring

**View real-time logs (if using screen):**
```bash
screen -r snap_preprocess
```

**View logs (if using nohup):**
```bash
tail -f preprocess.log
```

**Search for errors:**
```bash
grep -i error preprocess.log
grep -i failed preprocess.log
```

---

## Troubleshooting

### Problem: Out of Memory Errors

**Symptoms:**
```
java.lang.OutOfMemoryError: Java heap space
```

**Solutions:**

1. **Reduce number of workers:**
   ```bash
   # From 8 workers to 4
   python s1_preprocess_parallel.py --input-dir ... --workers 4
   ```

2. **Increase memory per worker in SNAP:**
   Edit `$SNAP_HOME/bin/gpt.vmoptions`:
   ```bash
   -Xmx1000G  # Increase if you have available RAM
   ```

3. **Reduce cache size:**
   ```bash
   python s1_preprocess_parallel.py --cache 100G  # Lower cache
   ```

---

### Problem: Processing Timeouts

**Symptoms:**
```
TIMEOUT: S1A_IW_GRDH_...
```

**Solutions:**

1. **Increase timeout in script:**
   Edit `s1_preprocess_parallel.py` line 160:
   ```python
   timeout=10800  # 3 hours instead of 2
   ```

2. **Check if specific scenes are problematic:**
   ```bash
   grep "TIMEOUT" workspace/preprocessed/processing_status.json
   ```

3. **Process problematic scenes individually:**
   ```bash
   python s1_preprocess_snap.py --input problem_scene.zip --output output.tif
   ```

---

### Problem: No Output Files Created

**Symptoms:**
- Script runs but no `.tif` files created
- Status shows "failed"

**Solutions:**

1. **Check graph XML exists:**
   ```bash
   ls sen1_preprocessing-gpt.xml
   ```

2. **Verify SNAP can find orbit files:**
   Check internet connection (SNAP downloads orbit files)

3. **Check disk space:**
   ```bash
   df -h workspace/preprocessed/
   ```

4. **Check permissions:**
   ```bash
   ls -ld workspace/preprocessed/
   chmod 755 workspace/preprocessed/
   ```

---

### Problem: GDAL Import Error

**Symptoms:**
```
ModuleNotFoundError: No module named 'osgeo'
```

**Solution:**
```bash
# Install GDAL
conda install -c conda-forge gdal

# Or using pip
pip install gdal
```

---

### Problem: GPT Not Found

**Symptoms:**
```
FileNotFoundError: SNAP GPT not found
```

**Solutions:**

1. **Verify GPT in PATH:**
   ```bash
   which gpt
   ```

2. **Manually specify GPT path:**
   ```bash
   python s1_preprocess_parallel.py \
       --gpt-path /home/user/esa-snap/bin/gpt \
       --input-dir workspace/downloads \
       --output-dir workspace/preprocessed
   ```

3. **Update PATH:**
   ```bash
   export PATH=/path/to/esa-snap/bin:$PATH
   ```

---

### Problem: Slow Processing Speed

**Symptoms:**
- Processing slower than expected
- High CPU wait time

**Solutions:**

1. **Check disk I/O:**
   ```bash
   iostat -x 5  # Check if disk is bottleneck
   ```

2. **Use faster storage:**
   - Move to SSD if on HDD
   - Use local disk instead of network storage

3. **Reduce parallelism if I/O bound:**
   ```bash
   # Fewer workers can be faster if disk is bottleneck
   python s1_preprocess_parallel.py --workers 2
   ```

4. **Check network (orbit file downloads):**
   Ensure good internet connection for orbit file retrieval

---

## Advanced Configuration

### Custom SNAP Graph XML

Create custom preprocessing workflow by modifying `sen1_preprocessing-gpt.xml`:

```xml
<graph id="S1_Preprocessing">
  <version>1.0</version>

  <!-- Read -->
  <node id="Read">
    <operator>Read</operator>
    <sources/>
    <parameters>
      <file>${myFilename}</file>
    </parameters>
  </node>

  <!-- Apply Orbit File -->
  <node id="Apply-Orbit-File">
    <operator>Apply-Orbit-File</operator>
    <sources>
      <sourceProduct refid="Read"/>
    </sources>
    <parameters>
      <orbitType>Sentinel Precise (Auto Download)</orbitType>
      <polyDegree>3</polyDegree>
    </parameters>
  </node>

  <!-- Add more operators as needed -->

</graph>
```

### Processing Specific Date Ranges

```bash
# Process only June 2024 scenes
python s1_preprocess_parallel.py \
    --input-dir workspace/downloads \
    --output-dir workspace/preprocessed \
    --pattern "*202406*.zip" \
    --workers 4
```

### Custom Status File Location

Edit `s1_preprocess_parallel.py` line 329:

```python
status_file: str = 'processing_status_custom.json'
```

### Adjust Timeout Per Scene

Edit `s1_preprocess_parallel.py` line 160:

```python
timeout=7200  # 2 hours (default)
timeout=10800  # 3 hours (for large scenes)
timeout=14400  # 4 hours (for very large scenes)
```

### Disable Automatic Cleanup

If you want to keep BEAM-DIMAP files, comment out line 147:

```python
# self._cleanup_temp_files(temp_output)
```

---

## Output Format

### Output Directory Structure

```
workspace/preprocessed/
├── S1A_IW_GRDH_1SDV_20240101T111508_..._VH.tif
├── S1A_IW_GRDH_1SDV_20240103T111508_..._VH.tif
├── S1A_IW_GRDH_1SDV_20240105T111508_..._VH.tif
├── ...
└── processing_status.json
```

### Output File Naming

Format: `{original_scene_name}_VH.tif`

Example:
```
Input:  S1A_IW_GRDH_1SDV_20240528T111509_20240528T111538_054070_069315_642B.zip
Output: S1A_IW_GRDH_1SDV_20240528T111509_20240528T111538_054070_069315_642B_VH.tif
```

### GeoTIFF Properties

- **Bands:** 1 (VH polarization only)
- **Data type:** Float32
- **Values:** Backscatter in dB (typically -25 to -5 dB)
- **Compression:** LZW
- **Tiling:** Yes (for efficient access)
- **NoData:** -9999 or NaN
- **Projection:** UTM (from terrain correction)

### Status File Format

`processing_status.json`:

```json
{
  "workspace/downloads/scene1.zip": "completed",
  "workspace/downloads/scene2.zip": "completed",
  "workspace/downloads/scene3.zip": "failed",
  "workspace/downloads/scene4.zip": "processing",
  "workspace/downloads/scene5.zip": "timeout"
}
```

**Status values:**
- `completed` - Successfully processed
- `skipped` - Already exists (resume mode)
- `processing` - Currently being processed
- `failed` - Processing failed
- `timeout` - Processing exceeded timeout
- `error` - Unexpected error occurred

---

## Next Steps After Preprocessing

Once all scenes are preprocessed:

### 1. Create 31-Band Annual Stack

```bash
python s1_composite_12day.py \
    --year 2024 \
    --input-dir workspace/preprocessed \
    --output workspace/stacked/s1_vh_stack_2024_31bands.tif \
    --method median
```

### 2. Generate Period Lookup Table

```bash
python s1_composite_12day.py \
    --year 2024 \
    --generate-lookup \
    --input-dir workspace/preprocessed \
    --output dummy.tif
```

### 3. Train Model

```bash
python balanced_train_lstm.py --augment --use-class-weights
```

### 4. Make Predictions

```bash
python predict_optimized.py --period 15 --skip-test
```

See `CLAUDE.md` for complete workflow documentation.

---

## Performance Tips

### Maximum Efficiency Checklist

- ✅ Use SSD for output directory
- ✅ Ensure good internet connection (orbit files)
- ✅ Run in screen/tmux session
- ✅ Monitor first few scenes before leaving unattended
- ✅ Set workers based on available RAM
- ✅ Use 75% of RAM maximum (leave buffer)
- ✅ Keep eye on disk space (grows quickly)
- ✅ Process during off-peak hours if on shared system

### Expected Processing Times

**Single scene (reference):**
- Fast system (SSD, 64GB RAM): 1-1.5 hours
- Standard system (HDD, 32GB RAM): 2-3 hours

**Full dataset (211 scenes):**

| Workers | Time (days) | RAM (GB) |
|---------|-------------|----------|
| 1 | 15 | 200 |
| 2 | 7.5 | 400 |
| 4 | 4 | 800 |
| 8 | 2 | 800 |
| 10 | 1.5 | 800 |

---

## Support and Contact

**Documentation:**
- Main workflow: `CLAUDE.md`
- 12-day period system: `12DAY_PERIOD_SYSTEM.md`
- Optimization guide: `OPTIMIZATION_RECOMMENDATIONS.md`

**SNAP Resources:**
- SNAP Forum: https://forum.step.esa.int/
- SNAP Documentation: https://step.esa.int/main/doc/

**Sentinel-1 Data:**
- ASF Data Search: https://search.asf.alaska.edu/
- Copernicus Browser: https://browser.dataspace.copernicus.eu/

---

## Version History

**v1.0 (2025-10-19)**
- Initial release
- Support for parallel processing (2-10 workers)
- Automatic VH band extraction
- Resume capability
- Status tracking

---

## License

This preprocessing pipeline is part of the Rice Growth Stage Mapping System.
See main repository for license information.
