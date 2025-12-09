#!/usr/bin/env python3

"""
Validate cached addresses using rewards.py to confirm they score 1.0.

This script tests all addresses in address_cache.json using _grade_address_variations
to verify they all score 1.0 (like the validator does).

Usage:
    python3 validate_cached_addresses.py                    # Test all countries
    python3 validate_cached_addresses.py --country "Poland" # Test one country
    python3 validate_cached_addresses.py --sample 10        # Test 10 random countries
"""

import os
import sys
import json
import argparse
import random

# Put MIID validator on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

from reward import _grade_address_variations

CACHE_FILE = os.path.join(os.path.dirname(__file__), "address_cache.json")

def validate_country_addresses(country: str, addresses: list, verbose: bool = True) -> dict:
    """
    Validate addresses for a country using _grade_address_variations.
    
    Returns:
        Dictionary with validation results
    """
    if not addresses:
        return {"error": "No addresses provided"}
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"VALIDATING: {country}")
        print(f"{'='*60}")
        print(f"Testing {len(addresses)} addresses...")
    
    # Format addresses like validator expects
    # variations: Dict[str, List[List[str]]] = {name: [[name_var, dob_var, addr_var], ...]}
    variations = {
        "Test Name": [
            ["Test Name", "1990-01-01", addr] for addr in addresses
        ]
    }
    
    # Seed addresses (one per name)
    seed_addresses = [country] * len(variations)
    
    # Call _grade_address_variations
    result = _grade_address_variations(
        variations=variations,
        seed_addresses=seed_addresses,
        miner_metrics={},
        validator_uid=101,
        miner_uid=501
    )
    
    overall_score = result.get('overall_score', 0.0)
    heuristic_perfect = result.get('heuristic_perfect', False)
    region_matches = result.get('region_matches', 0)
    api_result = result.get('api_result', 'UNKNOWN')
    total_addresses = result.get('total_addresses', len(addresses))
    
    if verbose:
        print(f"\n📊 VALIDATION RESULTS:")
        print(f"   Overall Score: {overall_score:.4f}")
        print(f"   Heuristic Perfect: {heuristic_perfect}")
        print(f"   Region Matches: {region_matches}/{total_addresses}")
        print(f"   API Result: {api_result}")
        print(f"   Total Addresses: {total_addresses}")
        
        if overall_score >= 0.99:
            print(f"\n✅✅✅ SUCCESS: All addresses score 1.0!")
        else:
            print(f"\n❌ FAILURE: Score is {overall_score:.4f} (expected 1.0)")
            print(f"   Some addresses may not score perfectly in validator")
    
    return {
        'country': country,
        'overall_score': overall_score,
        'heuristic_perfect': heuristic_perfect,
        'region_matches': region_matches,
        'api_result': api_result,
        'total_addresses': total_addresses,
        'all_passed': overall_score >= 0.99
    }

def main():
    parser = argparse.ArgumentParser(description='Validate cached addresses using rewards.py')
    parser.add_argument('--country', help='Specific country to validate (default: all)')
    parser.add_argument('--sample', type=int, help='Test N random countries (for quick check)')
    parser.add_argument('--verbose', action='store_true', default=True, help='Verbose output')
    
    args = parser.parse_args()
    
    # Load cache
    if not os.path.exists(CACHE_FILE):
        print(f"❌ Cache file not found: {CACHE_FILE}")
        return
    
    print(f"📂 Loading cache from: {CACHE_FILE}")
    with open(CACHE_FILE, 'r', encoding='utf-8') as f:
        cache_data = json.load(f)
    
    addresses_cache = cache_data.get('addresses', {})
    
    if not addresses_cache:
        print("❌ No addresses found in cache")
        return
    
    print(f"✅ Loaded {len(addresses_cache)} countries from cache")
    
    # Select countries to test
    if args.country:
        if args.country not in addresses_cache:
            print(f"❌ Country '{args.country}' not found in cache")
            return
        countries_to_test = {args.country: addresses_cache[args.country]}
    elif args.sample:
        countries_to_test = dict(random.sample(list(addresses_cache.items()), min(args.sample, len(addresses_cache))))
        print(f"🎲 Testing {len(countries_to_test)} random countries...")
    else:
        countries_to_test = addresses_cache
        print(f"🧪 Testing all {len(countries_to_test)} countries...")
    
    # Validate each country
    results = []
    passed = 0
    failed = 0
    
    for country, addresses in countries_to_test.items():
        result = validate_country_addresses(country, addresses, args.verbose)
        results.append(result)
        
        if result.get('all_passed'):
            passed += 1
        else:
            failed += 1
    
    # Summary
    print(f"\n{'='*60}")
    print(f"VALIDATION SUMMARY")
    print(f"{'='*60}")
    print(f"Total countries tested: {len(results)}")
    print(f"✅ Passed (score 1.0): {passed}")
    print(f"❌ Failed (score < 1.0): {failed}")
    
    if failed > 0:
        print(f"\n⚠️  Failed countries:")
        for r in results:
            if not r.get('all_passed'):
                print(f"   - {r['country']}: Score {r['overall_score']:.4f}")
    
    # Calculate average score
    if results:
        avg_score = sum(r['overall_score'] for r in results) / len(results)
        print(f"\n📊 Average score: {avg_score:.4f}")
    
    print(f"{'='*60}")

if __name__ == '__main__':
    main()

