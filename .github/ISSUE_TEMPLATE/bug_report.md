---
name: Bug Report
about: Report a bug or unexpected behavior
title: '[BUG] '
labels: bug
assignees: ''
---

## Bug Description

A clear and concise description of what the bug is.

## Environment

- **Operating System**: [e.g., Ubuntu 22.04, macOS 14, Windows 11]
- **Python Version**: [e.g., 3.10.12] (`python --version`)
- **SNAP Version**: [e.g., 10.0] (`gpt --version`)
- **GDAL Version**: [e.g., 3.4.1] (`gdalinfo --version`)

## Steps to Reproduce

1. Download scene '...'
2. Run command '...'
3. See error

## Expected Behavior

What you expected to happen.

## Actual Behavior

What actually happened.

## Error Message

```
Paste the complete error message and stack trace here
```

## Input Data

- **Sentinel-1 Scene ID**: [e.g., S1A_IW_GRDH_1SDV_20240101T...]
- **Region/AOI**: [e.g., Java Island, Indonesia]
- **Number of scenes**: [e.g., 5 scenes]

## Command Used

```bash
# Paste the exact command you ran
python s1_process_period_dir.py --run-all
```

## Screenshots

If applicable, add screenshots to help explain the problem.

## Additional Context

Add any other context about the problem here.

## Checklist

- [ ] I have checked existing issues for duplicates
- [ ] I have verified SNAP is correctly installed (`gpt --version` works)
- [ ] I have verified GDAL is correctly installed (`gdal_merge.py --help` works)
- [ ] I have sufficient disk space for processing
- [ ] I have sufficient RAM (at least 16GB recommended)
