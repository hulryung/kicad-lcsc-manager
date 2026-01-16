"""
Test real 3D model downloading from EasyEDA
"""
import sys
sys.path.insert(0, '/Users/dkkang/dev/kicad-lcsc-manager/plugins')

from pathlib import Path
from lcsc_manager.api.lcsc_api import LCSCAPIClient
from lcsc_manager.converters.model_3d_converter import Model3DConverter

# Create test directory
test_dir = Path('/tmp/test_3d_models')
test_dir.mkdir(exist_ok=True)

# Get component with 3D model
client = LCSCAPIClient()
component = client.search_component('C2040')

print(f"Component: {component.get('name')}")
print(f"LCSC ID: {component.get('lcsc_id')}")

# Get EasyEDA data
easyeda_data = component.get('easyeda_data', {})

if not easyeda_data:
    print("ERROR: No EasyEDA data in component")
    sys.exit(1)

print("\nProcessing 3D models...")

# Download and convert 3D models
converter = Model3DConverter()
models = converter.process_component_model(
    easyeda_data=easyeda_data,
    component_info=component,
    output_dir=test_dir
)

print("\nResults:")
for format_type, path in models.items():
    print(f"  {format_type.upper()}: {path}")
    print(f"    Exists: {path.exists()}")
    print(f"    Size: {path.stat().st_size if path.exists() else 0} bytes")

# Cleanup
import shutil
# shutil.rmtree(test_dir)  # Comment out to inspect files
print(f"\nTest files saved to: {test_dir}")
