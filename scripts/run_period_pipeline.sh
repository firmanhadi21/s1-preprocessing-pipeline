#!/bin/bash
#
# Quick launcher for period-based pipeline
# Processes all 31 12-day periods for rice growth stage mapping
#
# Usage:
#   ./run_period_pipeline.sh                    # Process all periods for current year
#   ./run_period_pipeline.sh 2024               # Process all periods for 2024
#   ./run_period_pipeline.sh 2024 "1-10"        # Process specific periods
#   ./run_period_pipeline.sh 2024 "15" test     # Process period 15 with test config
#

# Configuration
CONFIG_FILE="${3:-pipeline_config_period.yaml}"
YEAR="${1:-$(date +%Y)}"
PERIODS="${2:-}"

echo "=========================================="
echo "Period-Based Sentinel-1 Pipeline"
echo "=========================================="
echo "Config: $CONFIG_FILE"
echo "Year: $YEAR"
if [ -n "$PERIODS" ]; then
    echo "Periods: $PERIODS"
else
    echo "Periods: All (1-31)"
fi
echo "=========================================="
echo ""

# Check config exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Config file not found: $CONFIG_FILE"
    echo ""
    echo "Available configs:"
    ls -1 pipeline_config*.yaml 2>/dev/null || echo "  None found"
    echo ""
    echo "Create one with:"
    echo "  cp pipeline_config_period.yaml my_config.yaml"
    exit 1
fi

# Build command
CMD="python s1_period_pipeline.py --config $CONFIG_FILE --year $YEAR --run-all"

if [ -n "$PERIODS" ]; then
    CMD="$CMD --periods $PERIODS"
fi

echo "Running: $CMD"
echo ""

# Execute
$CMD

# Check result
if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "Pipeline completed successfully!"
    echo "=========================================="
    echo ""
    echo "Output stack:"
    STACK_FILE="workspace_period/year_${YEAR}/final_stack/S1_VH_stack_${YEAR}_31bands.tif"
    if [ -f "$STACK_FILE" ]; then
        ls -lh "$STACK_FILE"
        echo ""
        echo "Next steps:"
        echo "  1. Update config.py to use this stack"
        echo "  2. Train model: python train.py"
        echo "  3. Predict: python predict.py --period 15"
    fi
else
    echo ""
    echo "=========================================="
    echo "Pipeline failed!"
    echo "=========================================="
    echo "Check logs above for errors"
    exit 1
fi
