#!/usr/bin/env python3
"""
Test script to validate cached addresses using the validator from rewards.py
Tests all 15 addresses from a country to see if they score 1.0
"""

import os
import sys
import json
from typing import Dict, List, Any

# Add validator to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

from reward import _grade_address_variations

def load_cached_addresses(cache_file: str = "validated_address_cache_fresh.json") -> Dict[str, List[str]]:
    """Load addresses from cache file."""
    if not os.path.exists(cache_file):
        print(f"❌ Cache file not found: {cache_file}")
        return {}
    
    with open(cache_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get("addresses", {})

def test_addresses_for_country(country: str, addresses: List[str], verbose: bool = True):
    """
    Test addresses for a country using _grade_address_variations.
    
    Args:
        country: Country name (used as seed address)
        addresses: List of addresses to test
        verbose: Print detailed results
    """
    if not addresses:
        print(f"❌ No addresses found for {country}")
        return None
    
    print(f"\n{'='*80}")
    print(f"🧪 TESTING {len(addresses)} ADDRESSES FOR: {country}")
    print(f"{'='*80}\n")
    
    # Create variations structure expected by _grade_address_variations
    # Format: {name: [[name_var, dob_var, address_var], ...]}
    # We'll create one variation per address with dummy name and DOB
    variations = {}
    seed_addresses = []
    
    for idx, address in enumerate(addresses):
        # Create a unique name for each address
        name = f"TestPerson_{idx+1}"
        # Create variation: [name, dob, address]
        # Using dummy name and DOB since we only care about address validation
        variations[name] = [[name, "1990-01-01", address]]
        seed_addresses.append(country)
    
    # Mock miner metrics (required by function)
    miner_metrics = {}
    
    # Test with validator
    validator_uid = 101
    miner_uid = 501
    
    if verbose:
        print(f"📋 Test Configuration:")
        print(f"   Country (seed): {country}")
        print(f"   Addresses to test: {len(addresses)}")
        print(f"   Validator UID: {validator_uid}")
        print(f"   Miner UID: {miner_uid}\n")
        print(f"🔄 Running validation...\n")
    
    try:
        result = _grade_address_variations(
            variations=variations,
            seed_addresses=seed_addresses,
            miner_metrics=miner_metrics,
            validator_uid=validator_uid,
            miner_uid=miner_uid
        )
        
        # Print results
        overall_score = result.get("overall_score", 0.0)
        heuristic_perfect = result.get("heuristic_perfect", False)
        region_matches = result.get("region_matches", 0)
        api_result = result.get("api_result", "UNKNOWN")
        
        print(f"{'='*80}")
        print(f"📊 VALIDATION RESULTS")
        print(f"{'='*80}")
        print(f"✅ Overall Score: {overall_score:.4f}")
        print(f"✅ Heuristic Perfect: {heuristic_perfect}")
        print(f"✅ Region Matches: {region_matches}/{len(addresses)}")
        print(f"✅ API Result: {api_result}")
        
        # Show detailed breakdown if available
        if "validation_results" in result:
            validation_results = result["validation_results"]
            print(f"\n📋 Detailed Breakdown:")
            for name, details in validation_results.items():
                print(f"   {name}:")
                if isinstance(details, dict):
                    for key, value in details.items():
                        print(f"      {key}: {value}")
        
        # Show API validation details
        if "api_validation" in result:
            api_validation = result["api_validation"]
            if api_validation:
                print(f"\n🔍 API Validation Details:")
                for key, value in api_validation.items():
                    if isinstance(value, dict):
                        print(f"   {key}:")
                        for k, v in value.items():
                            print(f"      {k}: {v}")
                    else:
                        print(f"   {key}: {value}")
        
        # Show API attempts
        if "api_attempts" in result:
            api_attempts = result["api_attempts"]
            print(f"\n🌐 API Attempts ({len(api_attempts)} addresses tested):")
            for idx, attempt in enumerate(api_attempts, 1):
                addr = attempt.get("address", "Unknown")[:60]
                api_result = attempt.get("result", "Unknown")
                print(f"   [{idx}] {addr}... → {api_result}")
        
        # Show which addresses were selected for API validation
        if "api_validated_addresses" in result:
            api_addrs = result["api_validated_addresses"]
            print(f"\n🎲 Addresses Selected for API Validation (random 3):")
            for idx, addr_info in enumerate(api_addrs, 1):
                if isinstance(addr_info, (list, tuple)) and len(addr_info) >= 1:
                    addr = addr_info[0] if isinstance(addr_info[0], str) else str(addr_info[0])
                    print(f"   [{idx}] {addr[:70]}...")
                else:
                    print(f"   [{idx}] {addr_info}")
        
        # Check individual addresses
        print(f"\n📝 Individual Address Results:")
        for idx, address in enumerate(addresses):
            name = f"TestPerson_{idx+1}"
            if "validation_results" in result and name in result["validation_results"]:
                addr_result = result["validation_results"][name]
                status = "✅" if addr_result.get("passed", False) else "❌"
                print(f"   {status} [{idx+1}/{len(addresses)}] {address[:60]}...")
            else:
                print(f"   ⚠️  [{idx+1}/{len(addresses)}] {address[:60]}... (no result)")
        
        print(f"\n{'='*80}")
        if overall_score >= 1.0:
            print(f"✅✅✅ SUCCESS: All addresses score 1.0!")
        elif overall_score >= 0.9:
            print(f"⚠️  WARNING: Score is {overall_score:.4f} (close to 1.0 but not perfect)")
        else:
            print(f"❌ FAILED: Score is {overall_score:.4f} (expected 1.0)")
        print(f"{'='*80}\n")
        
        return result
        
    except Exception as e:
        print(f"❌ Error during validation: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Main function to test cached addresses."""
    cache_file = "validated_address_cache_fresh.json"
    
    print("🔍 Loading cached addresses...")
    addresses_by_country = load_cached_addresses(cache_file)
    
    if not addresses_by_country:
        print("❌ No addresses found in cache file")
        return
    
    # Find countries with 15 addresses
    countries_with_15 = {
        country: addrs for country, addrs in addresses_by_country.items() 
        if len(addrs) >= 15
    }
    
    if not countries_with_15:
        print("❌ No countries found with 15+ addresses")
        print(f"Available countries: {list(addresses_by_country.keys())}")
        return
    
    print(f"✅ Found {len(countries_with_15)} countries with 15+ addresses:")
    for country in sorted(countries_with_15.keys()):
        print(f"   - {country}: {len(countries_with_15[country])} addresses")
    
    # Test first country with 15 addresses
    test_country = sorted(countries_with_15.keys())[0]
    test_addresses = countries_with_15[test_country][:15]  # Take first 15
    
    print(f"\n🎯 Testing first country: {test_country}")
    
    result = test_addresses_for_country(test_country, test_addresses, verbose=True)
    
    if result:
        overall_score = result.get("overall_score", 0.0)
        if overall_score >= 1.0:
            print(f"\n✅✅✅ SUCCESS: All {len(test_addresses)} addresses scored 1.0!")
        else:
            print(f"\n⚠️  Score: {overall_score:.4f} (expected 1.0)")

if __name__ == "__main__":
    main()

