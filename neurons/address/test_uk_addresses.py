#!/usr/bin/env python3
"""
Test script to validate UK addresses using rewards.py
"""

import os
import sys
import time

# Add MIID validator to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

from reward import _grade_address_variations, looks_like_address, validate_address_region, check_with_nominatim

# First set: Manchester addresses
set1_addresses = [
    "1 Hilton Street, Manchester, M1 1JJ, United Kingdom",
    "3 Spear Street, Manchester, M1 1JU, United Kingdom",
    "5 Stevenson Square, Manchester, M1 1FB, United Kingdom",
    "7 Warwick Street, Manchester, M1 3BU, United Kingdom",
    "9 Little Lever Street, Manchester, M1 1HR, United Kingdom",
    "11 Back Piccadilly, Manchester, M1 1HP, United Kingdom",
    "13 Dale Street, Manchester, M1 1NJ, United Kingdom",
    "15 Hilton Street, Manchester, M1 1JN, United Kingdom",
    "17 Lever Street, Manchester, M1 1BY, United Kingdom",
    "19 Spear Street, Manchester, M1 1JN, United Kingdom",
    "21 Tib Street, Manchester, M1 1LW, United Kingdom",
    "23 Faraday Street, Manchester, M1 1BE, United Kingdom",
    "25 Hilton Street, Manchester, M1 1EL, United Kingdom",
    "27 Turner Street, Manchester, M4 1DW, United Kingdom",
    "29 Back Turner Street, Manchester, M4 1FN, United Kingdom"
]

# Second set: Smaller UK towns
set2_addresses = [
    "1 Mill Lane, Stow-on-the-Wold, GL54 1BN, United Kingdom",
    "3 Sheep Street, Stow-on-the-Wold, GL54 1AA, United Kingdom",
    "5 Park Street, Cirencester, GL7 2BX, United Kingdom",
    "7 Silver Street, Tetbury, GL8 8DH, United Kingdom",
    "12 Church Street, Chipping Campden, GL55 6JG, United Kingdom",
    "14 High Street, Moreton-in-Marsh, GL56 0AX, United Kingdom",
    "18 Gloucester Street, Winchcombe, GL54 5LX, United Kingdom",
    "22 West End, Northleach, GL54 3HE, United Kingdom",
    "25 Park Road, Bourton-on-the-Water, GL54 2AR, United Kingdom",
    "28 Station Road, Bourton-on-the-Water, GL54 2EE, United Kingdom",
    "31 The Square, Bibury, GL7 5NW, United Kingdom",
    "34 Church Lane, Naunton, GL54 3AX, United Kingdom",
    "37 High Street, Burford, OX18 4QA, United Kingdom",
    "41 Sheep Street, Burford, OX18 4LS, United Kingdom",
    "45 Park Lane, Woodstock, OX20 1SZ, United Kingdom"
]

def test_address_set(addresses, set_name, seed_address="United Kingdom"):
    """Test a set of addresses using _grade_address_variations"""
    
    print("\n" + "="*80)
    print(f"TESTING {set_name.upper()}")
    print("="*80)
    print(f"\nTesting {len(addresses)} addresses from {seed_address}\n")
    
    # Format addresses for validator
    variations = {
        "Test Name": [
            ["Test Name", "1990-01-01", addr] for addr in addresses
        ]
    }
    
    # Seed address
    seed_addresses = [seed_address] * len(variations)
    
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
    print(f"🌍 Region Matches: {region_matches}/{len(addresses)}")
    print(f"🔍 API Result: {api_result}")
    
    if api_attempts:
        print(f"\n📡 API Validation Details:")
        print(f"   Total API attempts: {len(api_attempts)}")
        
        # Count successful API validations
        successful = sum(1 for attempt in api_attempts 
                        if isinstance(attempt, dict) and attempt.get('score', 0) >= 0.99)
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
    
    passed_heuristic = 0
    passed_region = 0
    passed_api = 0
    
    for i, addr in enumerate(addresses, 1):
        heuristic_ok = looks_like_address(addr)
        region_ok = validate_address_region(addr, seed_address)
        
        if heuristic_ok:
            passed_heuristic += 1
        if region_ok:
            passed_region += 1
        
        # Check API for this address (only if heuristic and region pass)
        api_score = "N/A"
        api_area = "N/A"
        if heuristic_ok and region_ok:
            api_check = check_with_nominatim(
                address=addr,
                validator_uid=validator_uid,
                miner_uid=miner_uid,
                seed_address=seed_address,
                seed_name="Test"
            )
            
            if isinstance(api_check, dict):
                api_score = api_check.get('score', 0.0)
                api_area = api_check.get('min_area', 'N/A')
                if api_score >= 0.99:
                    passed_api += 1
            elif api_check == "TIMEOUT":
                api_score = "TIMEOUT"
            elif isinstance(api_check, (int, float)):
                api_score = api_check
            
            # Rate limit: Wait 1 second between API calls to respect Nominatim's rate limit
            if i < len(addresses):  # Don't sleep after the last address
                time.sleep(1.0)
        
        status = "✅" if (heuristic_ok and region_ok and (isinstance(api_score, (int, float)) and api_score >= 0.99)) else "❌"
        
        print(f"{status} [{i:2d}] {addr}")
        print(f"      Heuristic: {'✅' if heuristic_ok else '❌'}, "
              f"Region: {'✅' if region_ok else '❌'}, "
              f"API: {api_score if isinstance(api_score, str) else f'{api_score:.4f}'} "
              f"{f'(Area: {api_area} m²)' if isinstance(api_area, (int, float)) else ''}")
    
    print("\n" + "-" * 80)
    print(f"Summary: Heuristic: {passed_heuristic}/{len(addresses)}, "
          f"Region: {passed_region}/{len(addresses)}, "
          f"API: {passed_api}/{len(addresses)}")
    print("="*80)
    
    if overall_score >= 0.99:
        print("✅✅✅ SUCCESS: All addresses score 1.0!")
    else:
        print(f"⚠️  WARNING: Overall score is {overall_score:.4f} (expected 1.0)")
    
    print("="*80)
    
    return result

if __name__ == "__main__":
    # Test Set 1: Manchester addresses
    test_address_set(set1_addresses, "MANCHESTER ADDRESSES", "United Kingdom")

