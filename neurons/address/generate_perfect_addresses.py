#!/usr/bin/env python3
"""
Generate addresses with score 1.0 (area < 100 m²) using Nominatim reverse-engineering.
Searches for high-precision POIs and validates them against all validator checks.
"""

import sys
import os
import csv
import time
import requests
import geonamescache
from typing import List, Dict, Tuple

# Import address validation functions
from evaluate_addresses import (
    looks_like_address,
    check_with_nominatim,
    validate_address_region,
    COUNTRY_MAPPING
)

# Configuration
VALIDATOR_UID = 101
MINER_UID = 501
TARGET_SCORE = 1.0
TARGET_COUNT = 15
NOMINATIM_SLEEP = 1.0  # 1 request per second
USER_AGENT = "YanezCompliance/AddressGenerator (contact@example.com)"

# Search terms for high-precision POIs (these typically have small bounding boxes)
SEARCH_TERMS = [
    "university library",
    "main post office",
    "city hall",
    "national library",
    "central bank",
    "presidential palace",
    "embassy",
    "hospital",
    "train station",
    "airport terminal",
    "shopping mall",
    "stadium",
    "museum",
    "cathedral",
    "mosque",
    "temple",
    "government building",
    "parliament",
    "supreme court",
    "central market"
]

def get_country_names() -> List[str]:
    """Get standardized country list from geonamescache."""
    gc = geonamescache.GeonamesCache()
    
    # Get country names
    country_list = [
        data['name'].lower()
        for data in gc.get_countries().values()
    ]
    
    # Add mapped variations
    for raw, mapped in COUNTRY_MAPPING.items():
        if mapped not in country_list:
            country_list.append(mapped)
    
    # Remove duplicates and sort
    return sorted(list(set(country_list)))

def find_precise_addresses(country_name: str, count: int = 30) -> List[Dict]:
    """
    Uses Nominatim to find specific, highly-ranked addresses (place_rank >= 26).
    These typically have small bounding boxes (< 100 m²).
    """
    precise_addresses = []
    seen_addresses = set()
    
    print(f"  🔍 Searching Nominatim for high-precision addresses in {country_name}...")
    sys.stdout.flush()
    
    for term in SEARCH_TERMS:
        if len(precise_addresses) >= count:
            break
        
        q = f"{term}, {country_name}"
        params = {
            "q": q,
            "format": "json",
            "limit": 20,  # Get multiple results per search term
            "addressdetails": 1,
            "extratags": 1,
            "namedetails": 1,
            "accept-language": "en"
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(
                    "https://nominatim.openstreetmap.org/search",
                    params=params,
                    headers={"User-Agent": USER_AGENT},
                    timeout=15
                )
                
                if response.status_code == 429:
                    wait_time = (attempt + 1) * 2
                    print(f"    ⚠️  Rate limited, waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                if response.status_code != 200:
                    print(f"    ⚠️  HTTP {response.status_code} for '{term}'")
                    time.sleep(NOMINATIM_SLEEP)
                    break
                
                results = response.json()
                
                # Filter by place_rank >= 26 (building, house, street level)
                for result in results:
                    place_rank = result.get('place_rank', 0)
                    
                    # Only accept high-precision results (place_rank >= 26)
                    if place_rank >= 26:
                        address_str = result.get('display_name', '')
                        
                        # Skip duplicates
                        if address_str and address_str not in seen_addresses:
                            seen_addresses.add(address_str)
                            precise_addresses.append({
                                'address': address_str,
                                'place_rank': place_rank,
                                'country': country_name,
                                'lat': result.get('lat'),
                                'lon': result.get('lon')
                            })
                            
                            if len(precise_addresses) >= count:
                                break
                
                time.sleep(NOMINATIM_SLEEP)  # Respect rate limits
                break  # Success, exit retry loop
                
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"    ⚠️  Timeout for '{term}', retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"    ⚠️  Timeout for '{term}' after {max_retries} attempts")
                    break
            except requests.exceptions.ConnectionError:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"    ⚠️  Connection error for '{term}', retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"    ❌ Connection error for '{term}' after {max_retries} attempts")
                    break
            except Exception as e:
                print(f"    ❌ Error searching '{term}': {e}")
                break
    
    print(f"  ✅ Found {len(precise_addresses)} candidate addresses")
    sys.stdout.flush()
    
    return precise_addresses

def full_validation_check(address: str, seed_region: str, validator_uid: int, miner_uid: int) -> Tuple[bool, float]:
    """
    Applies all three core checks defined in the validator code.
    Returns (is_valid, score)
    """
    # Check 1: Heuristic Check
    if not looks_like_address(address):
        return False, 0.0
    
    # Check 2: Nominatim Score Check (must be 1.0)
    nominatim_result = check_with_nominatim(address, validator_uid, miner_uid, seed_region, "N/A")
    
    if nominatim_result == "TIMEOUT":
        return False, 0.0
    
    if nominatim_result == 0.0:
        return False, 0.0
    
    # Extract score from result
    if isinstance(nominatim_result, dict):
        nominatim_score = nominatim_result.get('score', 0.0)
    elif isinstance(nominatim_result, (int, float)):
        nominatim_score = float(nominatim_result)
    else:
        return False, 0.0
    
    # Require score of 1.0 (area < 100 m²)
    if nominatim_score < TARGET_SCORE:
        return False, nominatim_score
    
    # Check 3: Region Validation Check
    if not validate_address_region(address, seed_region):
        return False, nominatim_score
    
    # Passed all checks with score 1.0
    return True, nominatim_score

def generate_and_validate_addresses_for_country(country: str, target_count: int = 15) -> List[Tuple[str, str, float]]:
    """
    Generate and validate addresses for a single country.
    Returns list of (country, address, score) tuples.
    """
    print(f"\n{'='*80}")
    print(f"PROCESSING: {country.upper()}")
    print(f"{'='*80}")
    sys.stdout.flush()
    
    # Step 1: Find candidate addresses from Nominatim
    candidates = find_precise_addresses(country, count=target_count * 3)  # Get 3x candidates for filtering
    
    if not candidates:
        print(f"  ⚠️  No candidates found for {country}")
        return []
    
    # Step 2: Validate each candidate
    validated_list = []
    
    print(f"  🔄 Validating {len(candidates)} candidates...")
    sys.stdout.flush()
    
    for idx, candidate in enumerate(candidates, 1):
        address = candidate['address']
        
        print(f"    [{idx}/{len(candidates)}] Testing: {address[:70]}...", end=" ")
        sys.stdout.flush()
        
        is_valid, score = full_validation_check(
            address,
            country,
            VALIDATOR_UID,
            MINER_UID
        )
        
        if is_valid and score == TARGET_SCORE:
            if address not in [v[1] for v in validated_list]:
                validated_list.append((country, address, score))
                print(f"✅ PASSED (Score: {score:.4f})")
            else:
                print(f"⏭️  DUPLICATE")
        else:
            if score > 0:
                print(f"❌ FAILED (Score: {score:.4f})")
            else:
                print(f"❌ FAILED")
        
        sys.stdout.flush()
        
        if len(validated_list) >= target_count:
            break
        
        # Rate limiting between validations
        time.sleep(NOMINATIM_SLEEP)
    
    print(f"\n  📊 Results: {len(validated_list)}/{target_count} addresses validated with score {TARGET_SCORE}")
    sys.stdout.flush()
    
    return validated_list

def test_with_cached_addresses(country: str, count: int = 5):
    """Test validation logic using addresses from address_cache.json."""
    import json
    
    print("="*80)
    print("TESTING WITH CACHED ADDRESSES")
    print("="*80)
    print(f"Country: {country}")
    print(f"Testing validation logic on existing addresses...")
    print("="*80)
    sys.stdout.flush()
    
    # Load cache
    cache_file = "address_cache.json"
    if not os.path.exists(cache_file):
        print(f"❌ {cache_file} not found!")
        return
    
    with open(cache_file, 'r') as f:
        cache = json.load(f)
    
    addresses_dict = cache.get('addresses', {})
    if country not in addresses_dict:
        print(f"❌ Country '{country}' not found in cache")
        return
    
    addresses = addresses_dict[country][:count * 2]  # Test more than needed
    
    print(f"\n📋 Testing {len(addresses)} addresses from cache...")
    sys.stdout.flush()
    
    validated_list = []
    
    for idx, address in enumerate(addresses, 1):
        print(f"  [{idx}/{len(addresses)}] Testing: {address[:70]}...", end=" ")
        sys.stdout.flush()
        
        is_valid, score = full_validation_check(
            address,
            country,
            VALIDATOR_UID,
            MINER_UID
        )
        
        if is_valid and score == TARGET_SCORE:
            if address not in [v[1] for v in validated_list]:
                validated_list.append((country, address, score))
                print(f"✅ PASSED (Score: {score:.4f})")
            else:
                print(f"⏭️  DUPLICATE")
        else:
            if score > 0:
                print(f"❌ FAILED (Score: {score:.4f})")
            else:
                print(f"❌ FAILED")
        
        sys.stdout.flush()
        
        if len(validated_list) >= count:
            break
        
        time.sleep(0.5)  # Shorter delay for cached addresses
    
    print(f"\n📊 Results: {len(validated_list)}/{count} addresses validated with score {TARGET_SCORE}")
    
    if validated_list:
        print("\n✅ Validated addresses:")
        for i, (country, address, score) in enumerate(validated_list, 1):
            print(f"  {i}. {address}")
            print(f"     Score: {score:.4f}")
    else:
        print("\n⚠️  No addresses scored 1.0 from cache")
    
    return validated_list

def main():
    """Main function to generate and validate addresses for a test country."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate addresses with score 1.0")
    parser.add_argument("--country", type=str, required=True, help="Country name to test")
    parser.add_argument("--count", type=int, default=15, help="Number of addresses to generate (default: 15)")
    parser.add_argument("--output", type=str, default="validated_addresses.csv", help="Output CSV file")
    parser.add_argument("--test-cache", action="store_true", help="Test with cached addresses instead of generating new ones")
    
    args = parser.parse_args()
    
    if args.test_cache:
        # Test mode: use cached addresses
        validated_addresses = test_with_cached_addresses(args.country, args.count)
    else:
        # Generate mode: search Nominatim
        print("="*80)
        print("GENERATE PERFECT ADDRESSES (Score 1.0)")
        print("="*80)
        print(f"Target Score: {TARGET_SCORE} (area < 100 m²)")
        print(f"Target Count: {args.count} addresses per country")
        print(f"Test Country: {args.country}")
        print("="*80)
        sys.stdout.flush()
        
        # Generate and validate addresses
        validated_addresses = generate_and_validate_addresses_for_country(args.country, args.count)
    
    if not validated_addresses:
        print(f"\n❌ No valid addresses found for {args.country}")
        sys.exit(1)
    
    # Export to CSV
    print(f"\n💾 Exporting to {args.output}...")
    sys.stdout.flush()
    
    with open(args.output, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Country', 'Address', 'Nominatim_Score'])
        
        for country, address, score in validated_addresses:
            writer.writerow([country, address, score])
    
    print(f"✅ Successfully exported {len(validated_addresses)} addresses to {args.output}")
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Country: {args.country}")
    print(f"Validated Addresses: {len(validated_addresses)}/{args.count}")
    print(f"All addresses have score: {TARGET_SCORE}")
    print("="*80)
    
    # Show first 5 addresses
    print("\n📋 Sample addresses (first 5):")
    for i, (country, address, score) in enumerate(validated_addresses[:5], 1):
        print(f"  {i}. {address}")
        print(f"     Score: {score:.4f}")

if __name__ == "__main__":
    main()

