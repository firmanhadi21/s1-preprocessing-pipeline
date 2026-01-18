#!/bin/bash

# Batch preprocessing script for all periods (1-56)
# Period 1-31: 2024
# Period 32-56: 2025

# Configuration
SCRIPT="s1_preprocess_parallel_multiresolution.py"
DOWNLOAD_BASE="workspace/downloads"
OUTPUT_BASE="workspace/preprocessed_20m"
RESOLUTION=20
WORKERS=8

# Check if script exists
if [ ! -f "$SCRIPT" ]; then
    echo "ERROR: Script $SCRIPT not found!"
    exit 1
fi

# Function to preprocess a single period
preprocess_period() {
    local period=$1
    local input_dir="${DOWNLOAD_BASE}/downloads_p${period}"
    local output_dir="${OUTPUT_BASE}/p${period}"
    
    echo "========================================"
    echo "Processing Period $period"
    echo "Input:  $input_dir"
    echo "Output: $output_dir"
    echo "========================================"
    
    # Check if input directory exists
    if [ ! -d "$input_dir" ]; then
        echo "WARNING: Input directory $input_dir does not exist. Skipping..."
        return 1
    fi
    
    # Create output directory if it doesn't exist
    mkdir -p "$output_dir"
    
    # Run preprocessing
    python "$SCRIPT" \
        --input-dir "$input_dir" \
        --output-dir "$output_dir" \
        --resolution $RESOLUTION \
        --workers $WORKERS
    
    if [ $? -eq 0 ]; then
        echo "✓ Period $period completed successfully"
        return 0
    else
        echo "✗ Period $period failed"
        return 1
    fi
}

# Main processing loop
echo "Starting batch preprocessing for periods 1-56"
echo "Resolution: ${RESOLUTION}m"
echo "Workers: $WORKERS"
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
    
    preprocess_period $period
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
echo "BATCH PROCESSING COMPLETE"
echo "========================================"
echo "Total periods:  $total_periods"
echo "Successful:     $successful"
echo "Skipped:        $skipped"
echo "Failed:         $failed"
echo "========================================"
