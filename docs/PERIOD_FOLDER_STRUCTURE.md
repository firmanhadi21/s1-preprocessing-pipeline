# Period-Based Folder Structure

## Overview

The automated pipeline (`s1_period_pipeline.py`) now uses a **period-specific folder structure** where each period has its own dedicated folders for downloads, preprocessed data, and GeoTIFFs.

## Directory Structure

```
workspace_java/year_2024/
├── p1/                          # Period 1 (Jan 1-12)
│   ├── downloads/               # Raw downloaded .zip files
│   ├── preprocessed/            # SNAP-processed .dim files
│   └── geotiff/                 # Converted GeoTIFF files
├── p2/                          # Period 2 (Jan 13-24)
│   ├── downloads/
│   ├── preprocessed/
│   └── geotiff/
├── ...
├── p31/                         # Period 31 (Dec 27-31)
│   ├── downloads/
│   ├── preprocessed/
│   └── geotiff/
├── period_mosaics/              # Final mosaics (one per period)
│   ├── mosaic_p1.tif
│   ├── mosaic_p2.tif
│   ├── ...
│   └── mosaic_p31.tif
├── final_stack/                 # 31-band annual stack
│   └── S1_VH_stack_2024_31bands.tif
└── temp/                        # Temporary files for processing
```

## Key Changes

### Before (Old Structure)
```
year_2024/
├── downloads/                   # All downloads mixed together
├── preprocessed/                # All preprocessed files mixed
├── geotiff/                     # All GeoTIFFs mixed
├── period_mosaics/
│   └── period_01_VH.tif        # Old naming scheme
```

### After (New Structure)
```
year_2024/
├── p1/
│   ├── downloads/              # Only Period 1 downloads
│   ├── preprocessed/           # Only Period 1 preprocessed
│   └── geotiff/                # Only Period 1 GeoTIFFs
├── period_mosaics/
│   └── mosaic_p1.tif           # New naming scheme
```

## Benefits

1. **Better Organization**: Each period's data is isolated in its own folder
2. **Easier Debugging**: Quickly find files for a specific period
3. **Parallel Processing**: Can process multiple periods independently
4. **Clear Naming**: `mosaic_p15.tif` is clearer than `period_15_VH.tif`
5. **Scalability**: Easy to add/remove periods without affecting others

## File Naming

### Downloads
- Format: `S1A_IW_GRDH_1SDV_YYYYMMDDTHHMMSS_*.zip`
- Location: `year_2024/p{period}/downloads/`
- Example: `year_2024/p15/downloads/S1A_IW_GRDH_1SDV_20240626T221012_*.zip`

### Preprocessed
- Format: `*_processed.dim` (plus corresponding `.data/` folder)
- Location: `year_2024/p{period}/preprocessed/`
- Example: `year_2024/p15/preprocessed/S1A_IW_GRDH_1SDV_20240626T221012_*_processed.dim`

### GeoTIFFs
- Format: `*_processed_VH.tif`
- Location: `year_2024/p{period}/geotiff/`
- Example: `year_2024/p15/geotiff/S1A_IW_GRDH_1SDV_20240626T221012_*_processed_VH.tif`

### Period Mosaics
- Format: `mosaic_p{period}.tif`
- Location: `year_2024/period_mosaics/`
- Example: `year_2024/period_mosaics/mosaic_p15.tif`

### Final Stack
- Format: `S1_VH_stack_{year}_31bands.tif`
- Location: `year_2024/final_stack/`
- Example: `year_2024/final_stack/S1_VH_stack_2024_31bands.tif`

## BIGTIFF Support

All GeoTIFF outputs now include `BIGTIFF='YES'` to handle large files (>4GB):

- **Mosaics**: Automatically use BIGTIFF
- **Final stack**: Automatically uses BIGTIFF
- **Single scene copies**: Rewritten with BIGTIFF support

This prevents the "Maximum TIFF file size exceeded" error.

## Usage Examples

### Process All Periods
```bash
python s1_period_pipeline.py --config pipeline_config_java.yaml --year 2024 --run-all
```

### Process Specific Periods
```bash
# Process periods 15-20
python s1_period_pipeline.py --config pipeline_config_java.yaml --year 2024 \
    --periods 15-20 --run-all

# Process periods 1, 5, 10
python s1_period_pipeline.py --config pipeline_config_java.yaml --year 2024 \
    --periods 1,5,10 --run-all
```

### Download Only for Specific Period
```bash
python s1_period_pipeline.py --config pipeline_config_java.yaml --year 2024 \
    --periods 15 --download-only
```

### Stack Existing Mosaics
```bash
# If you already have mosaic_p1.tif through mosaic_p31.tif
python s1_period_pipeline.py --config pipeline_config_java.yaml --year 2024 --stack-only
```

## Migrating from Old Structure

If you have files in the old structure (flat `downloads/`, `preprocessed/`, etc.), use the reorganization script:

```bash
./reorganize_to_period_structure.sh
```

This script:
1. Reads date from each filename
2. Calculates which period it belongs to
3. Moves files to appropriate `p{period}/downloads/` folder

## Checking Your Structure

To verify your folder structure:

```bash
# Check period folders exist
ls -d year_2024/p*/

# Count files in each period's downloads
for p in year_2024/p*/downloads/; do
    echo "$p: $(ls $p/*.zip 2>/dev/null | wc -l) files"
done

# Check mosaics
ls -lh year_2024/period_mosaics/

# Check final stack
ls -lh year_2024/final_stack/
```

## Troubleshooting

### Problem: "No period mosaics found"
**Solution**: Check that files are named `mosaic_p1.tif`, not `period_01_VH.tif`

### Problem: "BIGTIFF error"
**Solution**: Update to latest pipeline - all outputs now use `BIGTIFF='YES'`

### Problem: "Files in wrong period folder"
**Solution**:
1. Stop the pipeline
2. Run `./reorganize_to_period_structure.sh`
3. Restart the pipeline

### Problem: "Missing preprocessed files for period X"
**Solution**:
```bash
# Rerun preprocessing for specific period
python s1_period_pipeline.py --config pipeline_config_java.yaml --year 2024 \
    --periods X --preprocess-only
```

## Pipeline Steps

The pipeline automatically manages the folder structure:

1. **Step 1 - Download**: Downloads to `p{period}/downloads/`
2. **Step 2 - Preprocess**: Reads from `p{period}/downloads/`, writes to `p{period}/preprocessed/`
3. **Step 3 - Convert**: Reads from `p{period}/preprocessed/`, writes to `p{period}/geotiff/`
4. **Step 4 - Mosaic**: Reads from `p{period}/geotiff/`, writes to `period_mosaics/mosaic_p{period}.tif`
5. **Step 5 - Stack**: Reads from `period_mosaics/mosaic_p*.tif`, writes to `final_stack/S1_VH_stack_{year}_31bands.tif`

## Manual Workflow Comparison

**Automated Pipeline** (`s1_period_pipeline.py`):
- Uses: `p1/`, `p2/`, ..., `p31/` folders
- Mosaics: `period_mosaics/mosaic_p{period}.tif`

**Manual Workflow** (`s1_manual_period_workflow.py`):
- Uses: `downloads_p1/`, `preprocessed_p1/`, ... folders
- Mosaics: `mosaics/mosaic_p{period}.tif`

Choose the workflow that fits your needs - they're designed for different use cases.
