#!/bin/bash
# SNAP Preprocessing Diagnostic Script
# Run this to diagnose why a scene is failing

echo "=========================================="
echo "SNAP PREPROCESSING DIAGNOSTIC"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SCENE="S1A_IW_GRDH_1SDV_20240331T105825_20240331T105854_053224_06733F_CBEA.zip"

# 1. Check SNAP installation
echo "1. Checking SNAP Installation..."
if command -v gpt &> /dev/null; then
    echo -e "${GREEN}✓${NC} SNAP GPT found: $(which gpt)"
    GPT_VERSION=$(gpt -h | head -1)
    echo "  Version: $GPT_VERSION"
else
    echo -e "${RED}✗${NC} SNAP GPT not found in PATH"
    exit 1
fi
echo ""

# 2. Check Java
echo "2. Checking Java..."
if command -v java &> /dev/null; then
    echo -e "${GREEN}✓${NC} Java found"
    java -version 2>&1 | head -3 | sed 's/^/  /'
else
    echo -e "${RED}✗${NC} Java not found"
    exit 1
fi
echo ""

# 3. Check SNAP memory configuration
echo "3. Checking SNAP Memory Configuration..."
SNAP_BIN=$(which gpt)
SNAP_DIR=$(dirname "$SNAP_BIN")
VMOPTIONS="$SNAP_DIR/gpt.vmoptions"

if [ -f "$VMOPTIONS" ]; then
    echo -e "${GREEN}✓${NC} Found: $VMOPTIONS"
    echo "  Current settings:"
    grep -E "^-Xm" "$VMOPTIONS" | sed 's/^/    /'

    # Check if memory is sufficient
    XMX=$(grep "^-Xmx" "$VMOPTIONS" | sed 's/-Xmx//' | sed 's/[^0-9]*//g')
    if [ -n "$XMX" ]; then
        if [ "$XMX" -lt 16000 ]; then
            echo -e "  ${YELLOW}⚠${NC} Warning: -Xmx is ${XMX}M, recommend ≥32G for 50m processing"
        else
            echo -e "  ${GREEN}✓${NC} Memory setting looks good"
        fi
    fi
else
    echo -e "${YELLOW}⚠${NC} vmoptions file not found at expected location"
    echo "  Trying alternate locations..."
    find /usr/local/snap /opt/snap ~/.snap -name "gpt.vmoptions" 2>/dev/null | sed 's/^/  /'
fi
echo ""

# 4. Check system resources
echo "4. Checking System Resources..."
echo "  Total RAM:"
free -h | grep "Mem:" | awk '{print "    Total: "$2", Available: "$7}'
echo "  Disk space:"
df -h . | tail -1 | awk '{print "    Available: "$4}'
echo ""

# 5. Check scene file
echo "5. Checking Scene File..."
SCENE_PATH=$(find . -name "$SCENE" 2>/dev/null | head -1)

if [ -n "$SCENE_PATH" ]; then
    echo -e "${GREEN}✓${NC} Scene found: $SCENE_PATH"

    # Check file size
    SIZE=$(ls -lh "$SCENE_PATH" | awk '{print $5}')
    echo "  Size: $SIZE"

    # Expected size for IW GRDH: 800MB - 1.2GB
    SIZE_BYTES=$(stat -f%z "$SCENE_PATH" 2>/dev/null || stat -c%s "$SCENE_PATH" 2>/dev/null)
    if [ "$SIZE_BYTES" -lt 700000000 ]; then
        echo -e "  ${YELLOW}⚠${NC} Warning: File smaller than expected (< 700MB)"
        echo "     May be corrupted or incomplete download"
    else
        echo -e "  ${GREEN}✓${NC} File size looks normal"
    fi

    # Test ZIP integrity
    echo "  Testing ZIP integrity..."
    if unzip -t "$SCENE_PATH" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} ZIP file is valid"
    else
        echo -e "  ${RED}✗${NC} ZIP file is CORRUPTED"
        echo "     Recommendation: Re-download this scene"
    fi
else
    echo -e "${YELLOW}⚠${NC} Scene not found in current directory"
    echo "  Searched for: $SCENE"
    echo "  Please run from directory containing scenes"
fi
echo ""

# 6. Check SNAP cache
echo "6. Checking SNAP Cache..."
SNAP_CACHE="$HOME/.snap/var/cache"
if [ -d "$SNAP_CACHE" ]; then
    CACHE_SIZE=$(du -sh "$SNAP_CACHE" 2>/dev/null | awk '{print $1}')
    echo "  Cache location: $SNAP_CACHE"
    echo "  Cache size: $CACHE_SIZE"

    # Check temp files
    TEMP_COUNT=$(find /tmp -name "snap-*" 2>/dev/null | wc -l)
    echo "  Temp files: $TEMP_COUNT SNAP temp directories"

    if [ "$CACHE_SIZE" != "0" ] || [ "$TEMP_COUNT" -gt 0 ]; then
        echo -e "  ${YELLOW}ℹ${NC} Consider clearing cache if having issues:"
        echo "     rm -rf ~/.snap/var/cache/*"
        echo "     rm -rf /tmp/snap-*"
    fi
else
    echo "  No cache directory found"
fi
echo ""

# 7. Check for GPT graph XML
echo "7. Checking GPT Graph Files..."
for GRAPH in sen1_preprocessing-gpt-50m.xml sen1_preprocessing-gpt.xml; do
    if [ -f "$GRAPH" ]; then
        echo -e "${GREEN}✓${NC} Found: $GRAPH"

        # Check resolution parameter
        if grep -q "50" "$GRAPH"; then
            echo "  Contains 50m configuration"
        fi
    fi
done

if ! ls *gpt*.xml &>/dev/null; then
    echo -e "${YELLOW}⚠${NC} No GPT graph XML found in current directory"
fi
echo ""

# 8. Recommendations
echo "=========================================="
echo "RECOMMENDATIONS"
echo "=========================================="
echo ""

HAS_ISSUES=0

# Check memory
XMX=$(grep "^-Xmx" "$VMOPTIONS" 2>/dev/null | sed 's/-Xmx//' | sed 's/[^0-9]*//g')
if [ -n "$XMX" ] && [ "$XMX" -lt 16000 ]; then
    echo -e "${YELLOW}⚠${NC} MEMORY: Increase SNAP memory allocation"
    echo "   Edit: $VMOPTIONS"
    echo "   Set: -Xmx32G (or -Xmx64G if you have ≥128GB RAM)"
    echo "   Set: -Xms8G"
    HAS_ISSUES=1
fi

# Check scene integrity
if [ -n "$SCENE_PATH" ]; then
    if ! unzip -t "$SCENE_PATH" > /dev/null 2>&1; then
        echo -e "${RED}✗${NC} CORRUPTED SCENE: Re-download required"
        echo "   Scene: $SCENE"
        echo "   Download from: https://search.asf.alaska.edu/"
        HAS_ISSUES=1
    fi
fi

if [ "$HAS_ISSUES" -eq 0 ]; then
    echo -e "${GREEN}✓${NC} No major issues detected"
    echo ""
    echo "If still getting errors, try:"
    echo "  1. Clear SNAP cache: rm -rf ~/.snap/var/cache/*"
    echo "  2. Reduce parallel workers: --workers 2"
    echo "  3. Process scene individually to see full error"
fi

echo ""
echo "=========================================="
echo "TEST SINGLE SCENE"
echo "=========================================="
echo ""

if [ -n "$SCENE_PATH" ] && [ -f "sen1_preprocessing-gpt-50m.xml" ]; then
    echo "To test this specific scene, run:"
    echo ""
    echo "  gpt sen1_preprocessing-gpt-50m.xml \\"
    echo "      -Pinput=\"$SCENE_PATH\" \\"
    echo "      -Poutput=test_output_50m.tif \\"
    echo "      -J-Xmx32G \\"
    echo "      -q 32"
    echo ""
    echo "This will show the full error message if it fails."
else
    echo "Cannot generate test command (missing scene or graph XML)"
fi

echo ""
echo "=========================================="
echo "DIAGNOSTIC COMPLETE"
echo "=========================================="
