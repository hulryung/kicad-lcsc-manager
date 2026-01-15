#!/usr/bin/env python3
"""
Test EasyEDA API response structure
"""
import sys
from pathlib import Path

# Add plugins to path
sys.path.insert(0, str(Path(__file__).parent / "plugins"))

from lcsc_manager.api.lcsc_api import LCSCAPIClient

def test_structure():
    """Test EasyEDA response structure"""
    client = LCSCAPIClient()

    lcsc_id = "C2040"
    print(f"Testing structure for: {lcsc_id}\n")

    component = client.search_component(lcsc_id)

    if component and 'easyeda_data' in component:
        easyeda_data = component['easyeda_data']

        print("Top-level keys in easyeda_data:")
        print(f"  {list(easyeda_data.keys())}\n")

        # Check for dataStr
        if 'dataStr' in easyeda_data:
            print("✓ dataStr found")
            dataStr = easyeda_data['dataStr']
            print(f"  dataStr keys: {list(dataStr.keys())}")

            if 'shape' in dataStr:
                print(f"  ✓ shape found: {len(dataStr['shape'])} elements")
            else:
                print("  ✗ shape NOT found")
        else:
            print("✗ dataStr NOT found")

        print()

        # Check for packageDetail
        if 'packageDetail' in easyeda_data:
            print("✓ packageDetail found")
            pkg = easyeda_data['packageDetail']
            print(f"  packageDetail keys: {list(pkg.keys())}")

            if 'dataStr' in pkg:
                pkg_dataStr = pkg['dataStr']
                print(f"  packageDetail.dataStr keys: {list(pkg_dataStr.keys())}")

                if 'shape' in pkg_dataStr:
                    print(f"  ✓ packageDetail.shape found: {len(pkg_dataStr['shape'])} elements")
                else:
                    print("  ✗ packageDetail.shape NOT found")
            else:
                print("  ✗ packageDetail.dataStr NOT found")
        else:
            print("✗ packageDetail NOT found")

        print("\n" + "="*60)
        print("CONCLUSION:")
        print("="*60)

        has_symbol = 'dataStr' in easyeda_data and 'shape' in easyeda_data.get('dataStr', {})
        has_footprint = 'packageDetail' in easyeda_data and 'dataStr' in easyeda_data.get('packageDetail', {}) and 'shape' in easyeda_data['packageDetail'].get('dataStr', {})

        if has_symbol:
            print("✓ Symbol data is available for conversion")
        else:
            print("✗ Symbol data is MISSING - will use placeholder")

        if has_footprint:
            print("✓ Footprint data is available for conversion")
        else:
            print("✗ Footprint data is MISSING - will use placeholder")
    else:
        print("✗ Failed to get component or easyeda_data")

if __name__ == "__main__":
    test_structure()
