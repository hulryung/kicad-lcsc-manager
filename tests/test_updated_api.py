#!/usr/bin/env python3
"""
Test the updated LCSC API client
"""
import sys
from pathlib import Path

# Add plugins to path
sys.path.insert(0, str(Path(__file__).parent / "plugins"))

from lcsc_manager.api.lcsc_api import LCSCAPIClient

def test_search():
    """Test the updated search_component method"""
    print("Testing Updated LCSC API Client")
    print("=" * 60)

    client = LCSCAPIClient()

    # Test C2040 (Raspberry Pi RP2040)
    lcsc_id = "C2040"
    print(f"\nSearching for: {lcsc_id}")
    print("-" * 60)

    component = client.search_component(lcsc_id)

    if component:
        print(f"✓ Component found!\n")
        print(f"LCSC ID: {component.get('lcsc_id')}")
        print(f"Name: {component.get('name')}")
        print(f"Manufacturer: {component.get('manufacturer')}")
        print(f"Manufacturer Part: {component.get('manufacturer_part')}")
        print(f"Package: {component.get('package')}")
        print(f"JLCPCB Class: {component.get('jlcpcb_class')}")
        print(f"Symbol UUID: {component.get('symbol_uuid')}")
        print(f"Footprint UUID: {component.get('footprint_uuid')}")
        print(f"SMT: {component.get('smt')}")

        # Verify we have easyeda_data
        if 'easyeda_data' in component:
            print(f"\n✓ EasyEDA data is present")
            easyeda_keys = list(component['easyeda_data'].keys())
            print(f"  Keys: {', '.join(easyeda_keys[:10])}")
        else:
            print(f"\n✗ EasyEDA data is missing!")

        # Verify correct values
        print(f"\n{'='*60}")
        print("VERIFICATION")
        print(f"{'='*60}")

        expected = {
            "name": "RP2040",
            "manufacturer": "Raspberry Pi(树莓派)",
            "package": "LQFN-56_L7.0-W7.0-P0.4-EP",
        }

        all_correct = True
        for key, expected_value in expected.items():
            actual_value = component.get(key)
            matches = actual_value == expected_value
            status = "✓" if matches else "✗"
            print(f"{status} {key}: {actual_value}")
            if not matches:
                print(f"    Expected: {expected_value}")
                all_correct = False

        if all_correct:
            print(f"\n✓ All fields match expected values!")
        else:
            print(f"\n✗ Some fields do not match")

        return True
    else:
        print(f"✗ Component not found")
        return False

if __name__ == "__main__":
    try:
        success = test_search()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
