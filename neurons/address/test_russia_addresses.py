#!/usr/bin/env python3
"""
Test Russia addresses from cache using _grade_address_variations from rewards.py
"""

import os
import sys
import json

# Add MIID validator to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, 'MIID', 'validator'))

from reward import _grade_address_variations, extract_city_country, validate_address_region

# Load Russia addresses from cache
CACHE_FILE = os.path.join(BASE_DIR, "address_cache.json")
with open(CACHE_FILE, 'r', encoding='utf-8') as f:
    cache_data = json.load(f)

russia_addresses = cache_data.get('addresses', {}).get('Russia', [])

if not russia_addresses:
    print("No Russia addresses found in cache")
    sys.exit(1)

print("=" * 80)
print("TESTING RUSSIA ADDRESSES FROM CACHE")
print("=" * 80)
print(f"Total addresses: {len(russia_addresses)}")
print()

# First, check which ones pass region validation
print("Checking region validation for each address:")
print()
passed_region = []
failed_region = []

for i, addr in enumerate(russia_addresses, 1):
    city, country = extract_city_country(addr)
    region_valid = validate_address_region(addr, "Russia")
    
    if region_valid:
        passed_region.append(addr)
        status = "✅"
    else:
        failed_region.append(addr)
        status = "❌"
    
    print(f"{status} [{i}] City: \"{city}\" | Region: {region_valid}")
    print(f"    {addr[:70]}...")
    print()

print("=" * 80)
print(f"Region Validation Summary:")
print(f"  ✅ Passed: {len(passed_region)}/{len(russia_addresses)}")
print(f"  ❌ Failed: {len(failed_region)}/{len(russia_addresses)}")
print()

# Test all addresses with _grade_address_variations
print("=" * 80)
print("TESTING ALL ADDRESSES WITH rewards.py")
print("=" * 80)
print()

variations = {
    'Test': [['Test', '1990-01-01', addr] for addr in russia_addresses]
}

result = _grade_address_variations(
    variations=variations,
    seed_addresses=['Russia'],
    miner_metrics={},
    validator_uid=101,
    miner_uid=501
)

# Display results
print("=" * 80)
print("VALIDATION RESULTS")
print("=" * 80)
print(f"Overall Score: {result.get('overall_score', 0.0):.4f}")
print(f"Heuristic Perfect: {result.get('heuristic_perfect', False)}")
print(f"Region Matches: {result.get('region_matches', 0)}/{len(russia_addresses)}")
print(f"Total Addresses: {result.get('total_addresses', 0)}")
print(f"API Result: {result.get('api_result', 'N/A')}")
print()

# API validation details
breakdown = result.get('detailed_breakdown', {})
api_validation = breakdown.get('api_validation', {})

if api_validation:
    print("API Validation Details:")
    print(f"  Total eligible: {api_validation.get('total_eligible_addresses', 0)}")
    print(f"  API calls made: {api_validation.get('total_calls', 0)}")
    print(f"  Successful: {api_validation.get('total_successful_calls', 0)}")
    print(f"  Failed: {api_validation.get('total_failed_calls', 0)}")
    print()
    
    api_attempts = api_validation.get('api_attempts', [])
    if api_attempts:
        print("Individual API Results:")
        print()
        for i, attempt in enumerate(api_attempts, 1):
            addr = attempt.get('address', 'N/A')
            api_result_val = attempt.get('result', 'N/A')
            score_details = attempt.get('score_details', {}) or {}
            
            if isinstance(api_result_val, (int, float)):
                area = score_details.get('min_area', 'N/A') if score_details else 'N/A'
                status = "✅" if api_result_val >= 0.99 else "❌"
                print(f"  {status} [{i}] {addr[:60]}...")
                print(f"      Score: {api_result_val:.4f}, Area: {area} m²")
            elif api_result_val == "TIMEOUT":
                print(f"  ⏱️  [{i}] {addr[:60]}...")
                print(f"      Status: TIMEOUT")
            else:
                print(f"  ❌ [{i}] {addr[:60]}...")
                print(f"      Status: FAILED")
            print()

# Show failed addresses
if failed_region:
    print("=" * 80)
    print("ADDRESSES FAILING REGION VALIDATION:")
    print("=" * 80)
    for i, addr in enumerate(failed_region[:5], 1):  # Show first 5
        city, country = extract_city_country(addr)
        print(f"{i}. City: \"{city}\" (empty = not found in geonames)")
        print(f"   {addr}")
        print()

print("=" * 80)

# Save results
output_file = "russia_validation_results.json"
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump({
        "addresses": russia_addresses,
        "validation_result": result,
        "count": len(russia_addresses),
        "passed_region": len(passed_region),
        "failed_region": len(failed_region)
    }, f, indent=2, ensure_ascii=False)

print(f"\n💾 Results saved to {output_file}")

