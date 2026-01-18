#!/bin/bash

# Batch mosaicking script for all periods (1-56)
# Uses OTB Mosaic with feathering and harmonization

# Configuration
INPUT_BASE="workspace/preprocessed_20m"
OUTPUT_DIR="workspace/mosaics_20m"
SPACING_X=0.000179663056824
SPACING_Y=0.000179663056824
FEATHER="large"
HARMO_METHOD="band"
HARMO_COST="rmse"
INTERPOLATOR="nn"
DISTANCE_SR=10
NODATA=0

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Function to mosaic a single period
mosaic_period() {
    local period=$1
    local input_dir="${INPUT_BASE}/p${period}"
    local output_file="${OUTPUT_DIR}/period_$(printf '%02d' $period)_mosaic.tif"
    
    echo "========================================"
    echo "Mosaicking Period $period"
    echo "Input:  $input_dir"
    echo "Output: $output_file"
    echo "========================================"
    
    # Check if input directory exists
    if [ ! -d "$input_dir" ]; then
        echo "WARNING: Input directory $input_dir does not exist. Skipping..."
        return 1
    fi
    
    # Check if there are any .tif files
    if [ -z "$(ls -A $input_dir/*.tif 2>/dev/null)" ]; then
        echo "WARNING: No .tif files found in $input_dir. Skipping..."
        return 1
    fi
    
    # Count files
    file_count=$(ls -1 $input_dir/*.tif 2>/dev/null | wc -l)
    echo "Found $file_count files to mosaic"
    
    # Run OTB Mosaic
    otbcli_Mosaic \
        -il $(ls $input_dir/*.tif | tr '\n' ' ') \
        -comp.feather $FEATHER \
        -harmo.method $HARMO_METHOD \
        -harmo.cost $HARMO_COST \
        -interpolator $INTERPOLATOR \
        -output.spacingx $SPACING_X \
        -output.spacingy $SPACING_Y \
        -distancemap.sr $DISTANCE_SR \
        -nodata $NODATA \
        -out $output_file
    
    if [ $? -eq 0 ]; then
        echo "✓ Period $period completed successfully"
        return 0
    else
        echo "✗ Period $period failed"
        return 2
    fi
}

# Main processing loop
echo "Starting batch mosaicking for periods 1-56"
echo "Input base:  $INPUT_BASE"
echo "Output dir:  $OUTPUT_DIR"
echo "Spacing:     $SPACING_X × $SPACING_Y degrees"
echo ""

# Track statistics
total_periods=56
successful=0
failed=0
skipped=0

# Process periods 1-56
for period in {1..56}; do
    if [ $period -le 31 ]; then
        year=2024
    else
        year=2025
    fi
    
    echo ""
    echo "----------------------------------------"
    echo "Period $period (Year: $year)"
    echo "----------------------------------------"
    
    mosaic_period $period
    result=$?
    
    if [ $result -eq 0 ]; then
        ((successful++))
    elif [ $result -eq 1 ]; then
        ((skipped++))
    else
        ((failed++))
    fi
done

# Print summary
echo ""
echo "========================================"
echo "BATCH MOSAICKING COMPLETE"
echo "========================================"
echo "Total periods:  $total_periods"
echo "Successful:     $successful"
echo "Skipped:        $skipped"
echo "Failed:         $failed"
echo "Mosaics saved to: $OUTPUT_DIR/"
echo "========================================"
