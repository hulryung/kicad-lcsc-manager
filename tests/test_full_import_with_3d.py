"""
Test full component import with real 3D models
"""
import sys
sys.path.insert(0, '/Users/dkkang/dev/kicad-lcsc-manager/plugins')

from pathlib import Path
from lcsc_manager.api.lcsc_api import LCSCAPIClient
from lcsc_manager.library.library_manager import LibraryManager

# Create test project
test_dir = Path('/tmp/test_full_import_3d')
test_dir.mkdir(exist_ok=True)
test_project = test_dir / 'test.kicad_pcb'
test_project.write_text('')

# Create library directories
lib_dir = test_dir / 'libs' / 'lcsc'
symbol_dir = lib_dir / 'symbols'
footprint_dir = lib_dir / 'footprints.pretty'
model_dir = lib_dir / '3dmodels'
symbol_dir.mkdir(parents=True, exist_ok=True)
footprint_dir.mkdir(parents=True, exist_ok=True)
model_dir.mkdir(parents=True, exist_ok=True)

print("Test Setup Complete")
print(f"Project: {test_project}")
print(f"Library: {lib_dir}")

# Get component
client = LCSCAPIClient()
component = client.search_component('C2040')

print(f"\nComponent: {component.get('name')}")
print(f"LCSC ID: {component.get('lcsc_id')}")

# Import component with all options
lib_manager = LibraryManager(test_project)
print("\nImporting component...")

results = lib_manager.import_component(
    easyeda_data=component['easyeda_data'],
    component_info=component,
    import_symbol=True,
    import_footprint=True,
    import_3d=True
)

print("\n=== Import Results ===")
print(f"Success: {results['success']}")

if results.get('symbol'):
    print(f"\n✓ Symbol: {results['symbol']}")

if results.get('footprint'):
    print(f"✓ Footprint: {results['footprint']}")

if results.get('model_3d'):
    models = results['model_3d']
    print(f"✓ 3D Models:")
    for format_type, path in models.items():
        print(f"    {format_type.upper()}: {path}")
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            print(f"      Size: {size_mb:.2f} MB")

if results.get('errors'):
    print("\nWarnings/Errors:")
    for error in results['errors']:
        print(f"  - {error}")

# Verify files exist
print("\n=== File Verification ===")
symbol_file = symbol_dir / 'lcsc_imported.kicad_sym'
footprint_file = footprint_dir / f"C2040_LQFN-56_L7_0-W7_0-P0_4-EP.kicad_mod"
wrl_file = model_dir / 'C2040.wrl'
step_file = model_dir / 'C2040.step'

print(f"Symbol exists: {symbol_file.exists()}")
print(f"Footprint exists: {footprint_file.exists()}")
print(f"WRL model exists: {wrl_file.exists()}")
print(f"STEP model exists: {step_file.exists()}")

# Check footprint contains model reference
if footprint_file.exists():
    footprint_content = footprint_file.read_text()
    if '${KIPRJMOD}/libs/lcsc/3dmodels/C2040.wrl' in footprint_content:
        print("\n✓ Footprint correctly references 3D model")
    else:
        print("\n✗ Footprint missing 3D model reference")

print(f"\nTest files saved to: {test_dir}")
print("(Directory NOT cleaned up for manual inspection)")
