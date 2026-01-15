#!/usr/bin/env python3
"""
Test JLCPCB API to fetch stock and price information
"""
import requests
import json

def test_jlcpcb_api(part_number):
    """Test JLCPCB API for stock and price info"""
    print(f"\n{'='*60}")
    print(f"Testing JLCPCB API for: {part_number}")
    print(f"{'='*60}")

    url = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"

    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
    }

    data = {
        'keyword': part_number
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code != 200:
        print(f"✗ API error: {response.status_code}")
        return None

    result = response.json()

    if result.get('code') != 200:
        print(f"✗ Response code: {result.get('code')}")
        return None

    # Extract component list
    components = result.get('data', {}).get('componentPageInfo', {}).get('list', [])

    if not components:
        print(f"✗ No components found")
        return None

    # Find exact match
    component = None
    for c in components:
        if c.get('componentCode') == part_number:
            component = c
            break

    if not component:
        print(f"✗ Exact match not found")
        return None

    print(f"\n✓ Component found!")
    print(f"\n=== Basic Info ===")
    print(f"Part Number: {component.get('componentCode')}")
    print(f"Manufacturer: {component.get('componentBrandEn', 'Unknown')}")
    print(f"MPN: {component.get('componentModelEn', '')}")
    print(f"Description: {component.get('describe', '')}")
    print(f"Package: {component.get('componentSpecificationEn', '')}")

    print(f"\n=== Stock Info ===")
    stock = component.get('stockCount', 0)
    print(f"Stock: {stock:,} units")

    print(f"\n=== Price Info ===")
    prices = component.get('componentPrices', [])
    if prices:
        # Sort by quantity
        prices_sorted = sorted(prices, key=lambda p: p.get('startNumber', 0))
        for price_tier in prices_sorted:
            start = price_tier.get('startNumber', 0)
            end = price_tier.get('endNumber', -1)
            price = price_tier.get('productPrice', 0)

            if end == -1:
                qty_range = f"{start:,}+"
            else:
                qty_range = f"{start:,}-{end:,}"

            print(f"  {qty_range} units: ${price:.6f}")
    else:
        print("  No pricing available")

    print(f"\n=== Other Info ===")
    print(f"Datasheet: {component.get('dataManualUrl', 'N/A')}")
    print(f"Image ID: {component.get('minImageAccessId', 'N/A')}")
    print(f"Product URL: {component.get('lcscGoodsUrl', 'N/A')}")

    return component

if __name__ == "__main__":
    # Test with C2040
    test_jlcpcb_api("C2040")

    # Test with another component
    print("\n")
    test_jlcpcb_api("C25804")
