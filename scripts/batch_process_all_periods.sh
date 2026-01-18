#!/bin/bash
# Batch process all periods (p2-p31)
# Period 1 already completed

WORK_DIR="/home/unika_sianturi/work/rice-growth-stage-mapping/workspace_java_both_orbits/year_2024"
SCRIPT="/home/unika_sianturi/work/rice-growth-stage-mapping/s1_process_period_dir.py"

# Process periods 2-31
for i in $(seq 2 31); do
    PERIOD_DIR="$WORK_DIR/p$i"

    echo "=============================================="
    echo "Processing Period $i"
    echo "=============================================="

    # Check if downloads exist
    if [ -d "$PERIOD_DIR/downloads" ] && [ "$(ls -A $PERIOD_DIR/downloads/*.zip 2>/dev/null)" ]; then
        cd "$PERIOD_DIR"
        python "$SCRIPT" --run-all

        # Check if mosaic was created
        if [ -f "$PERIOD_DIR/mosaic/p${i}_mosaic.tif" ]; then
            echo "✓ Period $i completed successfully"
        else
            echo "✗ Period $i mosaic not created"
        fi
    else
        echo "⚠ No downloads found for period $i, skipping..."
    fi

    echo ""
done

echo "=============================================="
echo "All periods processed!"
echo "=============================================="

# List all mosaics
echo ""
echo "Mosaics created:"
ls -lh $WORK_DIR/p*/mosaic/*.tif 2>/dev/null || echo "No mosaics found"
