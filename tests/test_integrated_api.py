#!/usr/bin/env python3
"""
Test the integrated API client with both EasyEDA and JLCPCB
"""
import sys
from pathlib import Path

# Add plugins to path
sys.path.insert(0, str(Path(__file__).parent / "plugins"))

from lcsc_manager.api.lcsc_api import LCSCAPIClient

def test_integrated_search():
    """Test the integrated search_component method"""
    print("Testing Integrated API Client (EasyEDA + JLCPCB)")
    print("=" * 80)

    client = LCSCAPIClient()

    # Test C2040 (Raspberry Pi RP2040)
    lcsc_id = "C2040"
    print(f"\nSearching for: {lcsc_id}")
    print("-" * 80)

    component = client.search_component(lcsc_id)

    if component:
        print(f"✓ Component found!\n")
        print(f"{'='*80}")
        print("BASIC INFORMATION")
        print(f"{'='*80}")
        print(f"LCSC ID: {component.get('lcsc_id')}")
        print(f"Name: {component.get('name')}")
        print(f"Manufacturer: {component.get('manufacturer')}")
        print(f"Manufacturer Part: {component.get('manufacturer_part')}")
        print(f"Package: {component.get('package')}")
        print(f"JLCPCB Class: {component.get('jlcpcb_class')}")
        print(f"Description: {component.get('description')}")

        print(f"\n{'='*80}")
        print("STOCK & AVAILABILITY")
        print(f"{'='*80}")
        stock = component.get('stock', 0)
        print(f"Stock: {stock:,} units")

        print(f"\n{'='*80}")
        print("PRICING")
        print(f"{'='*80}")
        prices = component.get('price', [])
        if prices:
            for i, price_tier in enumerate(prices, 1):
                qty_start = price_tier.get('qty', 0)
                qty_max = price_tier.get('qty_max')
                price = price_tier.get('price', 0)

                if qty_max is None:
                    qty_range = f"{qty_start:,}+"
                else:
                    qty_range = f"{qty_start:,}-{qty_max:,}"

                print(f"  Tier {i}: {qty_range:>15} units @ ${price:.6f}")
        else:
            print("  No pricing information available")

        print(f"\n{'='*80}")
        print("LINKS & RESOURCES")
        print(f"{'='*80}")
        print(f"Datasheet: {component.get('datasheet', 'N/A')}")
        print(f"Product URL: {component.get('url', 'N/A')}")
        print(f"Image: {component.get('image', 'N/A')}")

        print(f"\n{'='*80}")
        print("TECHNICAL DATA")
        print(f"{'='*80}")
        print(f"Symbol UUID: {component.get('symbol_uuid', 'N/A')}")
        print(f"Footprint UUID: {component.get('footprint_uuid', 'N/A')}")
        print(f"SMT: {component.get('smt', False)}")

        # Verify we have easyeda_data
        if 'easyeda_data' in component:
            print(f"\n✓ EasyEDA data is present for converters")
        else:
            print(f"\n✗ EasyEDA data is missing!")

        # Verify expected values
        print(f"\n{'='*80}")
        print("VERIFICATION")
        print(f"{'='*80}")

        checks = [
            ("Name", "RP2040", component.get('name')),
            ("Manufacturer contains 'Raspberry Pi'", True, "Raspberry Pi" in component.get('manufacturer', '')),
            ("Package", "LQFN-56_L7.0-W7.0-P0.4-EP", component.get('package')),
            ("Stock > 0", True, component.get('stock', 0) > 0),
            ("Has pricing", True, len(component.get('price', [])) > 0),
            ("Has datasheet", True, bool(component.get('datasheet'))),
        ]

        all_passed = True
        for check_name, expected, actual in checks:
            if expected == actual or (isinstance(expected, bool) and expected == bool(actual)):
                print(f"  ✓ {check_name}")
            else:
                print(f"  ✗ {check_name}: expected {expected}, got {actual}")
                all_passed = False

        print(f"\n{'='*80}")
        if all_passed:
            print("✓ ALL CHECKS PASSED!")
        else:
            print("✗ SOME CHECKS FAILED")
        print(f"{'='*80}")

        return True
    else:
        print(f"✗ Component not found")
        return False

if __name__ == "__main__":
    try:
        success = test_integrated_search()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
