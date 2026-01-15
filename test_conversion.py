#!/usr/bin/env python3
"""
Test symbol and footprint conversion
"""
import sys
from pathlib import Path

# Add plugins to path
sys.path.insert(0, str(Path(__file__).parent / "plugins"))

from lcsc_manager.api.lcsc_api import LCSCAPIClient
from lcsc_manager.converters.symbol_converter import SymbolConverter
from lcsc_manager.converters.footprint_converter import FootprintConverter

def test_conversion():
    """Test conversion with C2040"""
    print("="*60)
    print("Testing Symbol and Footprint Conversion")
    print("="*60)

    # Get component data
    client = LCSCAPIClient()
    component = client.search_component("C2040")

    if not component:
        print("✗ Failed to fetch component")
        return False

    easyeda_data = component.get('easyeda_data')
    if not easyeda_data:
        print("✗ No easyeda_data in component")
        return False

    print(f"\n✓ Component fetched: {component['name']}")
    print(f"  Manufacturer: {component['manufacturer']}")
    print(f"  Package: {component['package']}")

    # Test symbol conversion
    print(f"\n{'='*60}")
    print("SYMBOL CONVERSION")
    print(f"{'='*60}")

    symbol_converter = SymbolConverter()
    try:
        symbol_content = symbol_converter.convert(easyeda_data, component)

        # Check if it's a placeholder or real
        if 'shape' in str(symbol_content):
            print("✗ Symbol appears to be placeholder (contains generic 'shape')")
            is_real_symbol = False
        elif 'pin' in symbol_content.lower() and len(symbol_content) > 2000:
            print("✓ Symbol appears to be real (contains pins, size > 2KB)")
            is_real_symbol = True
            print(f"  Symbol size: {len(symbol_content)} bytes")

            # Count pins
            pin_count = symbol_content.count('(pin ')
            print(f"  Pin count: {pin_count}")
        else:
            print("? Symbol conversion completed but unclear if real or placeholder")
            print(f"  Symbol size: {len(symbol_content)} bytes")
            is_real_symbol = False

    except Exception as e:
        print(f"✗ Symbol conversion failed: {e}")
        is_real_symbol = False

    # Test footprint conversion
    print(f"\n{'='*60}")
    print("FOOTPRINT CONVERSION")
    print(f"{'='*60}")

    footprint_converter = FootprintConverter()
    try:
        footprint_content = footprint_converter.convert(easyeda_data, component)

        # Check if it's a placeholder or real
        if '(pad "1" smd rect (at -1 0) (size 0.8 1.2)' in footprint_content:
            print("✗ Footprint is placeholder (generic 2-pad)")
            is_real_footprint = False
        elif '(pad' in footprint_content and len(footprint_content) > 3000:
            print("✓ Footprint appears to be real (contains pads, size > 3KB)")
            is_real_footprint = True
            print(f"  Footprint size: {len(footprint_content)} bytes")

            # Count pads
            pad_count = footprint_content.count('(pad ')
            print(f"  Pad count: {pad_count}")
        else:
            print("? Footprint conversion completed but unclear if real or placeholder")
            print(f"  Footprint size: {len(footprint_content)} bytes")
            is_real_footprint = False

    except Exception as e:
        print(f"✗ Footprint conversion failed: {e}")
        is_real_footprint = False

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    if is_real_symbol and is_real_footprint:
        print("✓✓ SUCCESS: Both symbol and footprint conversions working!")
        return True
    elif is_real_symbol or is_real_footprint:
        print("⚠ PARTIAL: One conversion working, one failed")
        if is_real_symbol:
            print("  ✓ Symbol: OK")
        else:
            print("  ✗ Symbol: Failed or placeholder")

        if is_real_footprint:
            print("  ✓ Footprint: OK")
        else:
            print("  ✗ Footprint: Failed or placeholder")
        return False
    else:
        print("✗✗ FAILED: Both conversions using placeholders")
        return False

if __name__ == "__main__":
    try:
        success = test_conversion()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
