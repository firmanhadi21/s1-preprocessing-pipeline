#!/bin/bash
#
# Reorganize existing downloads into period structure
#
# This script moves files from workspace_java_both_orbits/year_2024/downloads/
# into period-specific folders: workspace_java_both_orbits/year_2024/p15/downloads/
#

WORKSPACE="workspace_java_both_orbits/year_2024"

echo "Reorganizing downloads into period structure..."
echo "Workspace: $WORKSPACE"

# Function to extract date from S1 filename
# Format: S1A_IW_GRDH_1SDV_20240626T...
get_date_from_filename() {
    local filename="$1"
    # Extract YYYYMMDD
    echo "$filename" | grep -oP '20\d{6}' | head -1
}

# Function to calculate period from date (simplified for 2024)
get_period_from_date() {
    local date_str="$1"  # YYYYMMDD
    local year="${date_str:0:4}"
    local month="${date_str:4:2}"
    local day="${date_str:6:2}"

    # Convert to day of year
    local doy=$(date -d "$year-$month-$day" +%j)

    # Calculate period (1-based, 12 days each)
    local period=$(( (doy - 1) / 12 + 1 ))

    # Cap at period 31
    if [ $period -gt 31 ]; then
        period=31
    fi

    echo $period
}

# Process all ZIP files in downloads folder
if [ -d "$WORKSPACE/downloads" ]; then
    echo "Found downloads folder"

    for zipfile in "$WORKSPACE/downloads"/*.zip; do
        if [ -f "$zipfile" ]; then
            filename=$(basename "$zipfile")
            echo "Processing: $filename"

            # Extract date
            date_str=$(get_date_from_filename "$filename")

            if [ -n "$date_str" ]; then
                # Get period
                period=$(get_period_from_date "$date_str")
                echo "  Date: $date_str -> Period: $period"

                # Create period directory
                period_dir="$WORKSPACE/p${period}/downloads"
                mkdir -p "$period_dir"

                # Move file
                echo "  Moving to: $period_dir/"
                mv "$zipfile" "$period_dir/"
            else
                echo "  Warning: Could not extract date from filename"
            fi
        fi
    done

    echo ""
    echo "✓ Reorganization complete!"
    echo ""
    echo "New structure:"
    ls -d "$WORKSPACE"/p*/downloads/ 2>/dev/null | while read dir; do
        count=$(ls "$dir"/*.zip 2>/dev/null | wc -l)
        echo "  $dir: $count files"
    done
else
    echo "Error: $WORKSPACE/downloads not found"
    exit 1
fi
