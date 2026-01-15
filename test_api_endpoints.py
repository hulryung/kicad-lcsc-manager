#!/usr/bin/env python3
"""
Test script to compare different EasyEDA API endpoints
"""
import requests
import json

def test_endpoint_1(lcsc_id):
    """Test our current endpoint: /svgs"""
    print(f"\n{'='*60}")
    print(f"Endpoint 1: /api/products/{lcsc_id}/svgs")
    print(f"{'='*60}")

    url = f"https://easyeda.com/api/products/{lcsc_id}/svgs"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        print(f"Success: {data.get('success')}")
        print(f"\nData keys: {list(data.keys())}")

        if data.get('result'):
            print(f"Result length: {len(data['result'])}")
            if data['result']:
                print(f"\nFirst item keys: {list(data['result'][0].keys())}")
                print(f"First item: {json.dumps(data['result'][0], indent=2)}")
    else:
        print(f"Error: {response.status_code}")

    return data if response.status_code == 200 else None

def test_endpoint_2(lcsc_id):
    """Test easyeda2kicad endpoint: /components with version"""
    print(f"\n{'='*60}")
    print(f"Endpoint 2: /api/products/{lcsc_id}/components")
    print(f"{'='*60}")

    url = f"https://easyeda.com/api/products/{lcsc_id}/components?version=6.4.19.5"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        print(f"Success: {data.get('success')}")
        print(f"\nData keys: {list(data.keys())}")

        if data.get('result'):
            result = data['result']
            print(f"\nResult keys: {list(result.keys())}")

            # Check for LCSC info
            if 'lcsc' in result:
                print(f"\nLCSC data found!")
                lcsc_data = result['lcsc']
                print(f"LCSC keys: {list(lcsc_data.keys())}")
                print(f"LCSC data: {json.dumps(lcsc_data, indent=2)}")

            # Check for component info
            if 'dataStr' in result:
                dataStr = result['dataStr']
                if 'head' in dataStr:
                    head = dataStr['head']
                    if 'c_para' in head:
                        c_para = head['c_para']
                        print(f"\nc_para keys: {list(c_para.keys())}")

                        # Extract key info
                        print(f"\nExtracted info:")
                        print(f"  Name: {c_para.get('name', 'N/A')}")
                        print(f"  Package: {c_para.get('package', 'N/A')}")
                        print(f"  Manufacturer: {c_para.get('BOM_Manufacturer', 'N/A')}")
                        print(f"  Datasheet: {c_para.get('link', 'N/A')}")
    else:
        print(f"Error: {response.status_code}")

    return data if response.status_code == 200 else None

def test_component_uuid(uuid):
    """Test fetching component details by UUID"""
    print(f"\n{'='*60}")
    print(f"Endpoint 3: /api/components/{uuid}")
    print(f"{'='*60}")

    url = f"https://easyeda.com/api/components/{uuid}"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        print(f"Success: {data.get('success')}")

        if data.get('result'):
            result = data['result']
            print(f"\nTitle: {result.get('title', 'N/A')}")

            if 'dataStr' in result:
                dataStr = result['dataStr']
                if 'head' in dataStr:
                    head = dataStr['head']
                    if 'c_para' in head:
                        c_para = head['c_para']
                        print(f"Package: {c_para.get('package', 'N/A')}")
                        print(f"Manufacturer: {c_para.get('Manufacturer', 'N/A')}")
    else:
        print(f"Error: {response.status_code}")

    return data if response.status_code == 200 else None

if __name__ == "__main__":
    # Test with C2040 (Raspberry Pi RP2040)
    lcsc_id = "C2040"

    print(f"Testing LCSC ID: {lcsc_id}")
    print(f"Expected: Raspberry Pi RP2040, LQFN-56(7x7), Raspberry Pi")

    # Test both endpoints
    data1 = test_endpoint_1(lcsc_id)
    data2 = test_endpoint_2(lcsc_id)

    # If we got UUIDs from endpoint 1, test those too
    if data1 and data1.get('result'):
        result = data1['result']
        if result and len(result) > 0:
            first_uuid = result[0].get('component_uuid')
            if first_uuid:
                print(f"\nTesting UUID from endpoint 1: {first_uuid}")
                test_component_uuid(first_uuid)

    print(f"\n{'='*60}")
    print("CONCLUSION")
    print(f"{'='*60}")
    print("Endpoint 2 (/components) provides complete product information")
    print("including manufacturer, part name, and datasheet from LCSC.")
    print("This is the endpoint we should use!")
