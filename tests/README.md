# Tests

This directory contains test scripts for the KiCad LCSC Manager plugin.

## Test Files

### API Tests

- **test_api_endpoints.py** - Test basic API endpoint connectivity
- **test_api_detailed.py** - Detailed API response structure testing
- **test_updated_api.py** - Test updated API implementation
- **test_jlcpcb_api.py** - Test JLCPCB API for stock/pricing information
- **test_integrated_api.py** - Test integrated EasyEDA + JLCPCB API workflow

### Conversion Tests

- **test_conversion.py** - Test symbol and footprint conversion
  - Validates real conversion generates proper KiCad files
  - Tests pin count, pad count, and file sizes
  - Example component: C2040 (Raspberry Pi RP2040)

- **test_easyeda_structure.py** - Test EasyEDA API response structure
  - Validates API response contains required fields
  - Checks for shape data, packageDetail, etc.

## Running Tests

All tests can be run from the project root:

```bash
# Run specific test
python3 tests/test_conversion.py

# Run API tests
python3 tests/test_integrated_api.py

# Run all tests
for test in tests/test_*.py; do
    echo "Running $test..."
    python3 "$test"
done
```

## Test Requirements

- Tests require the plugin modules to be importable
- Some tests require internet connectivity (API tests)
- Component C2040 is used as the standard test component

## Notes

- Tests are standalone scripts, not using pytest framework
- Each test includes its own validation and output
- Tests output success/failure indicators (✓/✗)
