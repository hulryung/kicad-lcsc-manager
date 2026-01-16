#!/usr/bin/env python3
"""
Test script to extract detailed component information from EasyEDA API
"""
import requests
import json

def test_components_endpoint(lcsc_id):
    """Test the /components endpoint which provides complete data"""
    print(f"\n{'='*60}")
    print(f"Testing LCSC ID: {lcsc_id}")
    print(f"{'='*60}")

    url = f"https://easyeda.com/api/products/{lcsc_id}/components?version=6.4.19.5"
    response = requests.get(url)

    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        return None

    data = response.json()

    if not data.get('success'):
        print("API returned success=False")
        return None

    result = data.get('result', {})

    # Extract basic info
    print(f"\n=== Basic Info ===")
    print(f"UUID: {result.get('uuid')}")
    print(f"Title: {result.get('title')}")
    print(f"Description: {result.get('description')}")
    print(f"Type: {result.get('type')}")
    print(f"SMT: {result.get('SMT')}")

    # Extract LCSC info
    if 'lcsc' in result:
        lcsc_info = result['lcsc']
        print(f"\n=== LCSC Info ===")
        print(f"LCSC ID: {lcsc_info.get('number')}")
        print(f"LCSC Internal ID: {lcsc_info.get('id')}")

    # Extract symbol data
    if 'dataStr' in result and 'head' in result['dataStr']:
        head = result['dataStr']['head']
        if 'c_para' in head:
            c_para = head['c_para']
            print(f"\n=== Component Parameters (c_para) ===")
            print(f"Name: {c_para.get('name', 'N/A')}")
            print(f"Package: {c_para.get('package', 'N/A')}")
            print(f"Prefix: {c_para.get('pre', 'N/A')}")
            print(f"Contributor: {c_para.get('Contributor', 'N/A')}")
            print(f"Supplier: {c_para.get('Supplier', 'N/A')}")
            print(f"Supplier Part: {c_para.get('Supplier Part', 'N/A')}")
            print(f"Manufacturer: {c_para.get('Manufacturer', 'N/A')}")
            print(f"Manufacturer Part: {c_para.get('Manufacturer Part', 'N/A')}")
            print(f"JLCPCB Part Class: {c_para.get('JLCPCB Part Class', 'N/A')}")

            # Check for other possible fields
            other_keys = [k for k in c_para.keys() if k not in [
                'name', 'package', 'pre', 'Contributor', 'Supplier',
                'Supplier Part', 'Manufacturer', 'Manufacturer Part',
                'JLCPCB Part Class'
            ]]
            if other_keys:
                print(f"\n=== Other c_para fields ===")
                for key in other_keys:
                    print(f"{key}: {c_para[key]}")

    # Extract footprint data
    if 'packageDetail' in result:
        pkg = result['packageDetail']
        print(f"\n=== Package Detail ===")
        print(f"Title: {pkg.get('title')}")
        print(f"UUID: {pkg.get('uuid')}")

        if 'dataStr' in pkg and 'head' in pkg['dataStr']:
            pkg_head = pkg['dataStr']['head']
            if 'c_para' in pkg_head:
                pkg_c_para = pkg_head['c_para']
                print(f"\nPackage c_para:")
                print(f"  Package: {pkg_c_para.get('package', 'N/A')}")
                print(f"  3D Model: {pkg_c_para.get('3DModel', 'N/A')}")

    return result

if __name__ == "__main__":
    # Test multiple components
    test_cases = [
        ("C2040", "Expected: RP2040, Raspberry Pi, LQFN-56_L7.0-W7.0-P0.4-EP"),
        ("C1", "Expected: 10uF capacitor"),
        ("C2", "Expected: 100nF capacitor"),
    ]

    for lcsc_id, description in test_cases:
        print(f"\n{description}")
        result = test_components_endpoint(lcsc_id)

        if result:
            print(f"\n✓ Successfully retrieved data for {lcsc_id}")
        else:
            print(f"\n✗ Failed to retrieve data for {lcsc_id}")

        print(f"\n{'-'*60}\n")
