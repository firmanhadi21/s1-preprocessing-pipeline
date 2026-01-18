# SNAP GPT Parallel Processing Fix

## Problem
When running parallel SNAP GPT processing, you encountered multiple errors:

### Error 1: Java Cache Conflicts
```
ERROR - FAILED [50m]: S1A_IW_GRDH_1SDV_20240606T105050_20240606T105116_054201_069792_A6BA.zip
ERROR - GPT Error: (Java stack trace)
```

### Error 2: GPT Command Line Parsing
```
Error: Unknown option '-tworkspace/preprocessed_50m/S1A_..._temp_50m'
```

### Error 3: No Output Files Created
```
ERROR - FAILED (no output) [50m]: S1A_IW_GRDH_1SDV_20240124T110648_20240124T110717_052247_06510A_726F.zip
```
GPT runs successfully but `.dim` file is not created.

### Error 4: GeoTIFF Conversion Fails
```
ERROR 1: The selected file is an ENVI header file, but to open ENVI datasets,
the data file should be selected instead of the .hdr file
ERROR - FAILED (GeoTIFF conversion) [50m]: S1A_IW_GRDH_...zip
```
GDAL tries to open `.hdr` header files instead of `.img` data files.

## Root Causes

### 1. **Cache Directory Conflicts**
- All parallel workers were sharing the same SNAP cache directory
- This caused race conditions and Java file locking issues
- Multiple processes trying to write to the same temp/cache files

### 2. **GPT Command Line Parsing Issue**
- GPT flags (`-t`, `-c`) were concatenated with values without spaces
- Example: `-tworkspace/path` instead of `-t workspace/path`
- Relative paths caused GPT option parser to fail
- Required absolute paths or proper flag/value separation

### 3. **Excessive Memory Settings**
- Default settings: 50G per worker for 50m resolution
- With 8 workers: 400G total memory (likely exceeding system capacity)
- SNAP GPT can fail silently when memory is insufficient

### 4. **Hardcoded Output Path in XML**
- XML graph had hardcoded `<file>targets.dim</file>` in Write operator
- The `-t` flag conflicts with hardcoded Write operator paths
- GPT writes to working directory instead of specified output location
- Results in "no output" errors as files are created in wrong location

### 5. **GDAL Opening Wrong File Type**
- BEAM-DIMAP format stores data as ENVI `.img` + `.hdr` pairs
- GDAL was trying to open `.hdr` (header) files instead of `.img` (data) files
- ENVI driver requires opening the binary `.img` file directly
- Opening `.hdr` files causes "wrong file type" error

### 6. **Insufficient Error Logging**
- Only last 500 characters of error were logged
- Made debugging difficult as root cause was truncated

## Fixes Applied

### 1. **Per-Process Cache Directories** ✅
Each worker now gets its own isolated cache directory:
```python
cache_dir = tempfile.mkdtemp(prefix=f"snap_cache_{input_name}_")
env = os.environ.copy()
env['_JAVA_OPTIONS'] = f'-Djava.io.tmpdir={cache_dir}'
```

This eliminates file locking conflicts between parallel processes.

### 2. **Fixed GPT Command Line Syntax** ✅
Proper flag/value separation and absolute paths:

**Before (broken)**:
```python
cmd = [gpt_path, xml, f'-t{temp_output}', f'-c{cache}']
# Results in: gpt ... -tworkspace/path -c6G
```

**After (fixed)**:
```python
temp_output = Path(output_dir).absolute() / f"{name}_temp_{res}m"
cmd = [gpt_path, xml, '-t', str(temp_output), '-c', cache]
# Results in: gpt ... -t /full/absolute/path -c 6G
```

Changes:
- All paths converted to absolute paths
- Flags and values separated into distinct arguments
- Prevents GPT parser errors

### 3. **Parameterized Output Path in XML** ✅
All XML graphs now use a parameter for the output file:

**Before**:
```xml
<file>targets.dim</file>
```

**After**:
```xml
<file>${outputFile}</file>
```

Python script passes output path as parameter:
```python
cmd = [gpt_path, xml,
       f'-PmyFilename={input_file}',
       f'-PoutputFile={temp_output}',  # NEW: Output path parameter
       '-c', cache]
```

This ensures GPT writes to the correct location every time.

### 4. **Reduced Memory Settings** ✅
New conservative defaults:
- **10m**: 16G per worker (was 200G)
- **20m**: 12G per worker (was 100G)
- **50m**: 8G per worker (was 50G)
- **100m**: 6G per worker (was 30G)

With 8 workers at 50m: 64G total (much more reasonable)

### 5. **Direct ENVI File Access** ✅
Fixed GeoTIFF extraction to open correct file type:

**Before (broken)**:
```python
dataset = gdal.Open(dim_file)  # Opens .dim, which points to .hdr files
```

**After (fixed)**:
```python
# Find the actual .img data file
data_dir = Path(dim_file).with_suffix('.data')
vh_img_file = data_dir / 'Gamma0_VH_db.img'  # Not .hdr!
dataset = gdal.Open(str(vh_img_file))  # Open binary data directly
```

BEAM-DIMAP structure:
```
output.dim          # XML metadata
output.data/
  ├── Gamma0_VH_db.img  # Binary data (OPEN THIS)
  ├── Gamma0_VH_db.hdr  # ENVI header (DON'T OPEN)
  ├── Gamma0_VV_db.img
  └── Gamma0_VV_db.hdr
```

### 6. **Full Error Logging** ✅
Failed processes now save complete error logs:
```
preprocessed_50m/{scene_name}_error.log
```

Contains:
- Full GPT command
- Complete stdout/stderr output
- Return code

### 7. **Automatic Cleanup** ✅
All cache directories are now cleaned up automatically:
- On successful completion
- On failure
- On timeout
- On exceptions

## Testing the Fix

### 1. Resume Your Processing
The script will automatically skip already-processed files:
```bash
python s1_preprocess_parallel_multiresolution.py \
    --input-dir downloads \
    --output-dir preprocessed_50m \
    --resolution 50 \
    --workers 8
```

### 2. Check Error Logs
If any files still fail, check the detailed error logs:
```bash
ls preprocessed_50m/*_error.log
cat preprocessed_50m/S1A_IW_GRDH_*_error.log
```

### 3. Reduce Workers if Needed
If you still encounter memory issues, reduce workers:
```bash
python s1_preprocess_parallel_multiresolution.py \
    --input-dir downloads \
    --output-dir preprocessed_50m \
    --resolution 50 \
    --workers 4  # Reduced from 8
```

### 4. Process Individual Failed Files
For specific problematic files, process sequentially:
```bash
python s1_preprocess_parallel_multiresolution.py \
    --input-dir downloads \
    --output-dir preprocessed_50m \
    --resolution 50 \
    --workers 1 \
    --pattern "S1A_IW_GRDH_1SDV_20240606T105050*.zip"
```

## Expected Behavior

### Before Fix
```
2025-10-19 22:30:03,187 - INFO - START [50m]: scene1.zip
2025-10-19 22:30:03,260 - ERROR - FAILED [50m]: scene1.zip
2025-10-19 22:30:03,260 - ERROR - GPT Error: (truncated)
```

### After Fix
```
2025-10-19 22:30:03,187 - INFO - START [50m]: scene1.zip
2025-10-19 22:35:45,123 - INFO - ✓ DONE (0:05:42) [50m]: scene1.zip
```

Or if it still fails:
```
2025-10-19 22:30:03,187 - INFO - START [50m]: scene1.zip
2025-10-19 22:30:15,260 - ERROR - FAILED [50m]: scene1.zip
2025-10-19 22:30:15,261 - ERROR - Full error saved to: preprocessed_50m/scene1_error.log
2025-10-19 22:30:15,262 - ERROR - GPT Error (last 500 chars): ...
```

## Troubleshooting

### If Files Still Fail

1. **Check the error log**:
   ```bash
   cat preprocessed_50m/{scene_name}_error.log
   ```

2. **Common issues**:
   - **Corrupted download**: Re-download the .zip file
   - **DEM download failure**: Check internet connection, SNAP may need to download SRTM data
   - **Disk space**: Ensure sufficient disk space (2-3GB per scene for 50m)
   - **Memory**: Reduce workers or increase system RAM

3. **Test SNAP GPT manually**:
   ```bash
   gpt sen1_preprocessing-gpt-50m.xml \
       -PmyFilename=/path/to/scene.zip \
       -ttest_output.dim
   ```

### Optimization Tips

**For fastest processing (50m resolution)**:
- Workers = Number of CPU cores (but watch memory)
- With 64GB RAM: 8 workers safe
- With 32GB RAM: 4 workers recommended
- With 16GB RAM: 2 workers max

**Memory per worker formula**:
```
workers × memory_per_worker ≤ 80% of total RAM
```

Example with 64GB RAM:
```
8 workers × 8G = 64G (100% - too tight)
6 workers × 8G = 48G (75% - good)
```

## Changes Summary

**File**: `s1_preprocess_parallel_multiresolution.py`

**Lines modified**:
- Lines 63-101: Reduced memory defaults (8G for 50m vs 50G)
- Lines 267-287: Fixed GPT command construction with absolute paths and proper flag separation
- Lines 234-352: Added per-process cache, environment isolation, full error logging
- Lines 356-435: Fixed GDAL extraction to use `.img` files instead of `.hdr` files

**Key fixes**:
1. Unique temporary cache directory per process
2. Java temp directory isolation via `_JAVA_OPTIONS`
3. Absolute paths for all file operations
4. Proper GPT command flag/value separation (`-t`, `path` vs `-tpath`)
5. Full error logs saved to `{output_dir}/{scene}_error.log`
6. Automatic cache cleanup on all exit paths

**Command changes**:
```bash
# Old (broken):
gpt xml -PmyFilename=/abs/path.zip -trelative/path -c6G

# New (fixed):
gpt xml -PmyFilename=/abs/path.zip -PoutputFile=/absolute/output/path -c 6G
```

**XML changes**: All 4 XML files updated (`sen1_preprocessing-gpt.xml`, `sen1_preprocessing-gpt-20m.xml`, `sen1_preprocessing-gpt-50m.xml`, `sen1_preprocessing-gpt-100m.xml`)

## Performance Impact

- **Speed**: No significant change (cache is per-process but same size)
- **Memory**: Reduced total usage (8G vs 50G per worker at 50m)
- **Reliability**: Significantly improved (no cache conflicts)
- **Debugging**: Much easier (full error logs)

## Next Steps

1. Resume your processing with the fixed script
2. Monitor for any remaining failures
3. Check error logs if failures occur
4. Adjust workers/memory if needed
5. Report any persistent issues with error log contents
