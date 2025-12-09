"""
Test generate_perfect_addresses() to verify:
1. Searches Nominatim for real addresses
2. Filters by bounding box area < 100 m² (guaranteed 1.0 score)
3. Validates heuristic requirements (30+ chars, 20+ letters, 2+ commas)
4. Returns real addresses that will score 1.0
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

from unified_generator import generate_perfect_addresses
from reward import looks_like_address, validate_address_region, check_with_nominatim
import re
from math import cos, radians
import requests

def calculate_bounding_box_area(bbox):
    """Calculate bounding box area in square meters."""
    if len(bbox) != 4:
        return None
    try:
        lat_min, lat_max, lon_min, lon_max = map(float, bbox)
        lat_avg = (lat_min + lat_max) / 2
        lat_diff = lat_max - lat_min
        lon_diff = lon_max - lon_min
        lat_m = lat_diff * 111000
        lon_m = lon_diff * 111000 * cos(radians(lat_avg))
        area_m2 = lat_m * lon_m
        return area_m2
    except:
        return None

def verify_address_heuristic(address: str) -> dict:
    """Verify address passes looks_like_address() heuristic."""
    address_clean = re.sub(r'[^\w]', '', address, flags=re.UNICODE)
    letter_count = len(re.findall(r'[^\W\d]', address, flags=re.UNICODE))
    comma_count = address.count(',')
    has_numbers = any(char.isdigit() for char in address)
    
    return {
        "length_ok": len(address_clean) >= 30,
        "letter_count_ok": letter_count >= 20,
        "comma_count_ok": comma_count >= 2,
        "has_numbers": has_numbers,
        "actual_length": len(address_clean),
        "actual_letters": letter_count,
        "actual_commas": comma_count,
        "passes_heuristic": looks_like_address(address)
    }

def verify_address_in_nominatim(address: str) -> dict:
    """Verify address exists in Nominatim and get bounding box area."""
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json", "limit": 1}
    headers = {"User-Agent": "MIID-Miner-Test/1.0"}
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code != 200:
            return {"exists": False, "error": f"HTTP {response.status_code}"}
        
        results = response.json()
        if len(results) == 0:
            return {"exists": False, "error": "No results"}
        
        result = results[0]
        bbox = result.get('boundingbox', [])
        area_m2 = calculate_bounding_box_area(bbox)
        
        return {
            "exists": True,
            "display_name": result.get('display_name', ''),
            "bbox": bbox,
            "area_m2": area_m2,
            "area_ok": area_m2 is not None and area_m2 < 100,
            "place_rank": result.get('place_rank', 0)
        }
    except Exception as e:
        return {"exists": False, "error": str(e)}

# Test addresses
test_seed_addresses = [
    "New York, USA",
    "London, UK",
    "Paris, France",
]

print("="*100)
print("TESTING generate_perfect_addresses()")
print("="*100)
print()
print("Testing:")
print("1. Searches Nominatim for real addresses")
print("2. Filters by bounding box area < 100 m² (guaranteed 1.0 score)")
print("3. Validates heuristic requirements (30+ chars, 20+ letters, 2+ commas)")
print("4. Returns real addresses that will score 1.0")
print()

for seed_address in test_seed_addresses:
    print("="*100)
    print(f"TESTING: {seed_address}")
    print("="*100)
    print()
    
    # Generate addresses
    print(f"Generating 5 perfect addresses for '{seed_address}'...")
    addresses = generate_perfect_addresses(seed_address, variation_count=5)
    
    print(f"\nGenerated {len(addresses)} addresses")
    print()
    
    # Test each address
    for i, address in enumerate(addresses, 1):
        print(f"Address {i}: {address}")
        print("-" * 100)
        
        # Test 1: Verify heuristic requirements
        heuristic_check = verify_address_heuristic(address)
        print(f"  Heuristic Check:")
        print(f"    Length >= 30: {heuristic_check['length_ok']} (actual: {heuristic_check['actual_length']})")
        print(f"    Letters >= 20: {heuristic_check['letter_count_ok']} (actual: {heuristic_check['actual_letters']})")
        print(f"    Commas >= 2: {heuristic_check['comma_count_ok']} (actual: {heuristic_check['actual_commas']})")
        print(f"    Has numbers: {heuristic_check['has_numbers']}")
        print(f"    Passes looks_like_address(): {heuristic_check['passes_heuristic']}")
        
        if not heuristic_check['passes_heuristic']:
            print(f"    ❌ FAILED: Does not pass looks_like_address() heuristic!")
        else:
            print(f"    ✅ PASSED: Heuristic check")
        print()
        
        # Test 2: Verify region match
        region_match = validate_address_region(address, seed_address)
        print(f"  Region Check:")
        print(f"    validate_address_region(): {region_match}")
        if region_match:
            print(f"    ✅ PASSED: Region matches seed address")
        else:
            print(f"    ❌ FAILED: Region does not match seed address")
        print()
        
        # Test 3: Verify exists in Nominatim and has area < 100 m²
        nominatim_check = verify_address_in_nominatim(address)
        print(f"  Nominatim Check:")
        print(f"    Exists in Nominatim: {nominatim_check.get('exists', False)}")
        if nominatim_check.get('exists'):
            print(f"    Bounding box area: {nominatim_check.get('area_m2', 'N/A'):.2f} m²")
            print(f"    Area < 100 m²: {nominatim_check.get('area_ok', False)}")
            print(f"    Place rank: {nominatim_check.get('place_rank', 'N/A')}")
            if nominatim_check.get('area_ok'):
                print(f"    ✅ PASSED: Area < 100 m² (will score 1.0)")
            else:
                print(f"    ⚠️  WARNING: Area >= 100 m² (will score < 1.0)")
        else:
            print(f"    ❌ FAILED: Address not found in Nominatim")
            print(f"    Error: {nominatim_check.get('error', 'Unknown')}")
        print()
        
        # Test 4: Full validation using validator's check_with_nominatim
        print(f"  Full Validation (using validator's check_with_nominatim):")
        try:
            result = check_with_nominatim(address, validator_uid=1, miner_uid=1, seed_address=seed_address, seed_name="Test")
            if isinstance(result, dict) and "score" in result:
                score = result["score"]
                print(f"    Score: {score:.3f}")
                if score == 1.0:
                    print(f"    ✅ PERFECT: Will score 1.0!")
                elif score >= 0.9:
                    print(f"    ✅ GOOD: Will score {score:.3f} (close to 1.0)")
                else:
                    print(f"    ⚠️  WARNING: Will score {score:.3f} (< 1.0)")
            elif result == "TIMEOUT":
                print(f"    ⚠️  TIMEOUT: API call timed out")
            else:
                print(f"    ❌ FAILED: Score = {result}")
        except Exception as e:
            print(f"    ❌ ERROR: {e}")
        
        print()
        print()
    
    print("="*100)
    print()

print("="*100)
print("TEST SUMMARY")
print("="*100)
print()
print("Expected results for each address:")
print("  ✅ Passes looks_like_address() heuristic")
print("  ✅ Passes validate_address_region()")
print("  ✅ Exists in Nominatim")
print("  ✅ Bounding box area < 100 m²")
print("  ✅ check_with_nominatim() returns score = 1.0")
print()
