# Contributing to Sentinel-1 Preprocessing Pipeline

Thank you for your interest in contributing! This document provides guidelines for contributing to this project.

## How Can I Contribute?

### Reporting Bugs

Before submitting a bug report:
1. Check existing [issues](https://github.com/firmanhadi21/s1-preprocessing-pipeline/issues) to avoid duplicates
2. Ensure you're using the latest version
3. Verify your SNAP and GDAL installations are working correctly

When submitting a bug report, include:
- Your operating system and version
- Python version (`python --version`)
- SNAP version (`gpt --version`)
- GDAL version (`gdalinfo --version`)
- Complete error message and stack trace
- Steps to reproduce the issue
- Sample data information (scene ID, date, region)

### Suggesting Features

Feature requests are welcome! Please:
1. Check if the feature has already been requested
2. Clearly describe the use case and benefits
3. Provide examples if possible

### Submitting Code Changes

#### Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/s1-preprocessing-pipeline.git
   cd s1-preprocessing-pipeline
   ```
3. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

#### Development Setup

1. Install dependencies:
   ```bash
   pip install rasterio numpy matplotlib asf-search shapely
   ```

2. Ensure SNAP and GDAL are installed and configured (see README.md)

3. Test your changes with sample data

#### Code Style

- Follow PEP 8 style guidelines
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Keep functions focused and modular
- Add comments for complex logic

#### Commit Messages

Write clear, descriptive commit messages:

```
Add support for VV polarization processing

- Add VV band extraction in step2_convert_to_geotiff()
- Update SNAP graph to include VV output
- Add --polarization argument to CLI
```

Format:
- First line: Short summary (50 chars or less)
- Blank line
- Body: Detailed description (wrap at 72 chars)

#### Pull Request Process

1. Update documentation if needed
2. Test your changes thoroughly
3. Ensure no new warnings or errors
4. Submit PR with clear description of changes

### Testing

Before submitting:
1. Test with at least one Sentinel-1 scene
2. Verify output GeoTIFF is valid
3. Check mosaic quality if multiple scenes
4. Test on your target platform (Linux/macOS/Windows)

#### Test Checklist

- [ ] `python s1_process_period_dir.py --help` works
- [ ] `--preprocess` step completes without errors
- [ ] `--convert` step produces valid GeoTIFFs
- [ ] `--mosaic` step creates seamless mosaic
- [ ] `--preview` step generates PNG image
- [ ] `--run-all` completes full workflow

## Areas for Contribution

### High Priority

- [ ] **Testing on macOS/Windows** - Most development done on Linux
- [ ] **Error handling improvements** - Better error messages and recovery
- [ ] **VV polarization support** - Currently VH only
- [ ] **Dual-pol processing** - VH+VV combined outputs

### Medium Priority

- [ ] **Progress indicators** - Show processing progress
- [ ] **Logging improvements** - Better log file management
- [ ] **Configuration file support** - YAML/JSON config instead of CLI args
- [ ] **Docker container** - Containerized processing environment

### Documentation

- [ ] **Video tutorials** - Installation and usage guides
- [ ] **More examples** - Different regions and use cases
- [ ] **Translations** - Documentation in other languages

## Code of Conduct

### Our Standards

- Be respectful and inclusive
- Accept constructive criticism gracefully
- Focus on what's best for the community
- Show empathy towards others

### Unacceptable Behavior

- Harassment or discriminatory language
- Personal attacks
- Publishing others' private information
- Other unprofessional conduct

## Questions?

- Open an [issue](https://github.com/firmanhadi21/s1-preprocessing-pipeline/issues) with the "question" label
- Check existing documentation in README.md

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing!
