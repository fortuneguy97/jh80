#!/usr/bin/env python3
"""
Test script to validate 15 Polish addresses using rewards.py
"""

import os
import sys

# Add MIID validator to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

from reward import _grade_address_variations

# Original addresses (FAIL - only 1 comma)
original_addresses = [
    "1 Józefa Sarego, Kraków, Poland",
    "2 Kanonicza, Kraków, Poland",
    "7 św. Marka, Kraków, Poland",
    "12 Gołębia, Kraków, Poland",
    "19 św. Jana, Kraków, Poland",
    "21 św. Tomasza, Kraków, Poland",
    "24 Bracka, Kraków, Poland",
    "25 Karmelicka, Kraków, Poland",
    "30 św. Gertrudy, Kraków, Poland",
    "31 Długa, Kraków, Poland",
    "34 Dietla, Kraków, Poland",
    "36 Sławkowska, Kraków, Poland",
    "40 Grodzka, Kraków, Poland",
    "45 Starowiślna, Kraków, Poland",
    "52 Krowoderska, Kraków, Poland"
]

# Corrected addresses (PASS - 2+ commas with postal code)
test_addresses = [
    "1 Józefa Sarego, Kraków, 31-000, Poland",
    "2 Kanonicza, Kraków, 31-000, Poland",
    "7 św. Marka, Kraków, 31-000, Poland",
    "12 Gołębia, Kraków, 31-000, Poland",
    "19 św. Jana, Kraków, 31-000, Poland",
    "21 św. Tomasza, Kraków, 31-000, Poland",
    "24 Bracka, Kraków, 31-000, Poland",
    "25 Karmelicka, Kraków, 31-000, Poland",
    "30 św. Gertrudy, Kraków, 31-000, Poland",
    "31 Długa, Kraków, 31-000, Poland",
    "34 Dietla, Kraków, 31-000, Poland",
    "36 Sławkowska, Kraków, 31-000, Poland",
    "40 Grodzka, Kraków, 31-000, Poland",
    "45 Starowiślna, Kraków, 31-000, Poland",
    "52 Krowoderska, Kraków, 31-000, Poland"
]

def test_poland_addresses():
    """Test the addresses using _grade_address_variations"""
    
    print("="*80)
    print("TESTING 15 POLISH ADDRESSES (CORRECTED - WITH POSTAL CODES)")
    print("="*80)
    print(f"\nTesting {len(test_addresses)} addresses from Kraków, Poland")
    print("All addresses now have 2+ commas (required by validator)\n")
    
    # Format addresses for validator
    # The validator expects: variations = {name: [[name, dob, address], ...]}
    variations = {
        "Test Name": [
            ["Test Name", "1990-01-01", addr] for addr in test_addresses
        ]
    }
    
    # Seed address (country)
    seed_addresses = ["Poland"] * len(variations)
    
    # Mock validator and miner UIDs
    validator_uid = 101
    miner_uid = 501
    
    print("Calling _grade_address_variations...")
    print("-" * 80)
    
    # Call the validator function
    result = _grade_address_variations(
        variations=variations,
        seed_addresses=seed_addresses,
        miner_metrics={},
        validator_uid=validator_uid,
        miner_uid=miner_uid
    )
    
    # Display results
    print("\n" + "="*80)
    print("VALIDATION RESULTS")
    print("="*80)
    
    overall_score = result.get('overall_score', 0.0)
    heuristic_perfect = result.get('heuristic_perfect', False)
    region_matches = result.get('region_matches', 0)
    api_result = result.get('api_result', 'UNKNOWN')
    api_attempts = result.get('api_attempts', [])
    
    print(f"\n📊 Overall Score: {overall_score:.4f}")
    print(f"✅ Heuristic Perfect: {heuristic_perfect}")
    print(f"🌍 Region Matches: {region_matches}/{len(test_addresses)}")
    print(f"🔍 API Result: {api_result}")
    
    if api_attempts:
        print(f"\n📡 API Validation Details:")
        print(f"   Total API attempts: {len(api_attempts)}")
        
        # Count successful API validations
        successful = sum(1 for attempt in api_attempts if isinstance(attempt, dict) and attempt.get('score', 0) >= 0.99)
        print(f"   Successful (score >= 0.99): {successful}/{len(api_attempts)}")
        
        # Show individual API results
        print(f"\n   Individual API Results:")
        for i, attempt in enumerate(api_attempts[:10], 1):  # Show first 10
            if isinstance(attempt, dict):
                score = attempt.get('score', 0.0)
                area = attempt.get('min_area', 'N/A')
                address = attempt.get('address', 'N/A')[:50]
                status = "✅" if score >= 0.99 else "❌"
                print(f"   {status} [{i}] Score: {score:.4f}, Area: {area} m², Address: {address}...")
            elif attempt == "TIMEOUT":
                print(f"   ⏱️  [{i}] TIMEOUT")
            else:
                print(f"   ❌ [{i}] {attempt}")
        
        if len(api_attempts) > 10:
            print(f"   ... and {len(api_attempts) - 10} more")
    
    # Show individual address validation
    print(f"\n📋 Individual Address Validation:")
    print("-" * 80)
    
    # Check each address individually
    from reward import looks_like_address, validate_address_region, check_with_nominatim
    
    for i, addr in enumerate(test_addresses, 1):
        heuristic_ok = looks_like_address(addr)
        region_ok = validate_address_region(addr, "Poland")
        
        # Check API for this address
        api_check = check_with_nominatim(
            address=addr,
            validator_uid=validator_uid,
            miner_uid=miner_uid,
            seed_address="Poland",
            seed_name="Test"
        )
        
        api_score = 0.0
        api_area = "N/A"
        if isinstance(api_check, dict):
            api_score = api_check.get('score', 0.0)
            api_area = api_check.get('min_area', 'N/A')
        elif api_check == "TIMEOUT":
            api_score = "TIMEOUT"
        elif isinstance(api_check, (int, float)):
            api_score = api_check
        
        status = "✅" if (heuristic_ok and region_ok and (isinstance(api_score, (int, float)) and api_score >= 0.99)) else "❌"
        
        print(f"{status} [{i:2d}] {addr}")
        print(f"      Heuristic: {'✅' if heuristic_ok else '❌'}, "
              f"Region: {'✅' if region_ok else '❌'}, "
              f"API: {api_score if isinstance(api_score, str) else f'{api_score:.4f}'} "
              f"{f'(Area: {api_area} m²)' if isinstance(api_area, (int, float)) else ''}")
    
    print("\n" + "="*80)
    
    if overall_score >= 0.99:
        print("✅✅✅ SUCCESS: All addresses score 1.0!")
    else:
        print(f"⚠️  WARNING: Overall score is {overall_score:.4f} (expected 1.0)")
    
    print("="*80)
    
    return result

if __name__ == "__main__":
    test_poland_addresses()

