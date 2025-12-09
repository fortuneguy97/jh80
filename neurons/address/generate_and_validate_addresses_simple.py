#!/usr/bin/env python3
"""
Simple address generator: Pull addresses directly from Nominatim and validate each one with rewards.py.
Only keep addresses that pass all validation checks.
"""

import sys
import os
import time
import json
import requests
from typing import List, Dict, Any

# Add MIID to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID'))

from validator.reward import (
    _grade_address_variations,
    looks_like_address,
    validate_address_region,
    check_with_nominatim,
    compute_bounding_box_areas_meters
)

# Configuration
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_SLEEP = 1.0  # 1 request per second
USER_AGENT = os.getenv("USER_AGENT", "MIID-Address-Generator/1.0 (contact@example.com)")

class MockValidator:
    def __init__(self):
        self.uid = 0

class MockMiner:
    def __init__(self):
        self.uid = 0

def reverse_geocode_address(lat: float, lon: float, max_retries: int = 3) -> Dict[str, Any]:
    """
    Reverse geocode coordinates to get an address from Nominatim.
    Returns Nominatim result dict or None.
    """
    params = {
        "lat": str(lat),
        "lon": str(lon),
        "format": "json",
        "addressdetails": "1",
        "extratags": "1",
        "namedetails": "1",
        "accept-language": "en",
        "zoom": "18"  # Building level
    }
    headers = {"User-Agent": USER_AGENT}
    
    for attempt in range(max_retries):
        try:
            r = requests.get("https://nominatim.openstreetmap.org/reverse", params=params, headers=headers, timeout=15)
            r.raise_for_status()
            result = r.json()
            time.sleep(NOMINATIM_SLEEP)
            return result
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep((attempt + 1) * 2)
                continue
            return None
    return None

def search_nominatim_for_addresses(country: str, query: str = None, limit: int = 50, max_retries: int = 3) -> List[Dict[str, Any]]:
    """
    Search Nominatim for addresses in a country/city.
    Returns list of Nominatim results.
    """
    # Build query string
    if query:
        search_query = f"{query}, {country}"
    else:
        search_query = country
    
    params = {
        "q": search_query,
        "format": "json",
        "limit": limit,
        "addressdetails": "1",
        "extratags": "1",
        "namedetails": "1",
        "accept-language": "en"
    }
    headers = {"User-Agent": USER_AGENT}
    
    for attempt in range(max_retries):
        try:
            print(f"  🔍 Searching Nominatim: '{search_query}' (attempt {attempt + 1}/{max_retries})...")
            sys.stdout.flush()
            
            r = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=15)
            r.raise_for_status()
            
            results = r.json()
            print(f"  ✅ Found {len(results)} results from Nominatim")
            sys.stdout.flush()
            
            time.sleep(NOMINATIM_SLEEP)
            return results
        except requests.exceptions.ConnectionError as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2
                print(f"  ⚠️  Connection error, retrying in {wait_time}s...")
                sys.stdout.flush()
                time.sleep(wait_time)
                continue
            else:
                print(f"  ❌ Nominatim connection error after {max_retries} attempts: {e}")
                sys.stdout.flush()
                return []
        except requests.exceptions.Timeout as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2
                print(f"  ⚠️  Timeout, retrying in {wait_time}s...")
                sys.stdout.flush()
                time.sleep(wait_time)
                continue
            else:
                print(f"  ❌ Nominatim timeout after {max_retries} attempts: {e}")
                sys.stdout.flush()
                return []
        except Exception as e:
            print(f"  ❌ Nominatim search error: {e}")
            sys.stdout.flush()
            return []
    
    return []

def validate_address_with_rewards(address: str, country: str, validator: MockValidator, miner: MockMiner, verbose: bool = True) -> Dict[str, Any]:
    """
    Validate a single address using rewards.py functions.
    Returns validation results.
    """
    result = {
        "address": address,
        "looks_like_address": False,
        "region_match": False,
        "api_score": 0.0,
        "api_area": 0.0,
        "passed": False
    }
    
    # Step 1: Heuristic check
    if not looks_like_address(address):
        if verbose:
            print(f"    ❌ Failed: looks_like_address heuristic")
        return result
    
    result["looks_like_address"] = True
    
    # Step 2: Region validation
    if not validate_address_region(address, country):
        if verbose:
            print(f"    ❌ Failed: region validation")
        return result
    
    result["region_match"] = True
    
    # Step 3: API validation
    api_result = check_with_nominatim(address, validator.uid, miner.uid, country, "Test")
    
    if isinstance(api_result, dict):
        result["api_score"] = api_result.get("score", 0.0)
        result["api_area"] = api_result.get("min_area", 0.0)
    elif isinstance(api_result, (int, float)):
        result["api_score"] = float(api_result)
    
    # Address passes if all checks pass
    result["passed"] = (
        result["looks_like_address"] and
        result["region_match"] and
        result["api_score"] >= 0.9  # Require at least 0.9 API score
    )
    
    if verbose:
        status = "✅ PASSED" if result["passed"] else "❌ FAILED"
        print(f"    {status} | Looks: {result['looks_like_address']} | Region: {result['region_match']} | API: {result['api_score']:.4f} (area: {result['api_area']:.2f} m²)")
    
    return result

def generate_addresses_for_country(country: str, per_country: int = 15, cities: List[str] = None, verbose: bool = True) -> List[str]:
    """
    Generate addresses for a country by:
    1. Searching Nominatim for addresses
    2. Validating each address with rewards.py
    3. Only keeping addresses that pass all checks
    """
    validator = MockValidator()
    miner = MockMiner()
    
    valid_addresses = []
    searched_queries = set()
    
    # Search strategy: Try major cities first, then country-wide
    search_queries = []
    
    if cities:
        for city in cities:
            search_queries.append((city, country))
    
    # Add country-wide search
    search_queries.append((None, country))
    
    # Use reverse geocoding on random points in major cities
    # This gets addresses directly from Nominatim with proper formatting
    import geonamescache
    gc = geonamescache.GeonamesCache()
    
    # Get major cities for the country
    country_code_map = {
        "Poland": "PL",
        "Philippines": "PH",
        "Russia": "RU",
        "Albania": "AL",
        # Add more as needed
    }
    
    country_code = country_code_map.get(country, "")
    if country_code:
        cities = [c for c in gc.get_cities().values() 
                 if c.get("countrycode", "").upper() == country_code.upper()]
        cities_sorted = sorted(cities, key=lambda x: x.get("population", 0) or 0, reverse=True)
        major_cities = cities_sorted[:10]  # Top 10 cities
        
        print(f"  📍 Found {len(major_cities)} major cities for reverse geocoding")
        sys.stdout.flush()
        
        # Add reverse geocoding coordinates
        import random
        for city in major_cities:
            lat = city.get("latitude", 0)
            lon = city.get("longitude", 0)
            if lat and lon:
                # Add 5 random points around each city center
                for _ in range(5):
                    # Random offset within ~1km
                    offset_lat = lat + random.uniform(-0.01, 0.01)
                    offset_lon = lon + random.uniform(-0.01, 0.01)
                    search_queries.append((f"REVERSE:{offset_lat}:{offset_lon}", country))
    
    print(f"\n{'='*80}")
    print(f"GENERATING ADDRESSES FOR: {country.upper()}")
    print(f"{'='*80}")
    print(f"Target: {per_country} valid addresses")
    print(f"Search queries: {len(search_queries)}")
    print(f"{'='*80}\n")
    sys.stdout.flush()
    
    for query_idx, (query, country_name) in enumerate(search_queries, 1):
        if len(valid_addresses) >= per_country:
            break
        
        if query in searched_queries:
            continue
        searched_queries.add(query)
        
        print(f"\n[Query {query_idx}/{len(search_queries)}] Searching: '{query or country_name}'")
        sys.stdout.flush()
        
        # Check if this is a reverse geocoding request
        if query and query.startswith("REVERSE:"):
            # Extract coordinates
            parts = query.split(":")
            if len(parts) == 3:
                lat = float(parts[1])
                lon = float(parts[2])
                result = reverse_geocode_address(lat, lon)
                results = [result] if result else []
            else:
                results = []
        else:
            # Search Nominatim
            results = search_nominatim_for_addresses(country_name, query)
        
        if not results:
            print(f"  ⏭️  No results, skipping...")
            sys.stdout.flush()
            continue
        
        # Validate each result
        print(f"  🔄 Validating {len(results)} addresses...")
        sys.stdout.flush()
        
        for idx, nom_result in enumerate(results, 1):
            if len(valid_addresses) >= per_country:
                break
            
            address = nom_result.get("display_name", "")
            if not address:
                continue
            
            # Check if address starts with a number (like Poland format: "26, Siedlisko...")
            first_part = address.split(",")[0].strip()
            has_number_at_start = first_part and first_part[0].isdigit()
            
            # Prioritize addresses with house numbers at start
            if not has_number_at_start and len(valid_addresses) < per_country * 0.5:
                # Skip addresses without house numbers at start if we're still early in search
                if verbose:
                    print(f"  [{idx}/{len(results)}] ⏭️  Skipping (no house number at start): {address[:70]}...")
                sys.stdout.flush()
                continue
            
            print(f"\n  [{idx}/{len(results)}] Testing: {address[:70]}...")
            if has_number_at_start:
                print(f"         ✅ Has house number at start: '{first_part}'")
            sys.stdout.flush()
            
            # Validate with rewards.py
            validation = validate_address_with_rewards(
                address, country_name, validator, miner, verbose=verbose
            )
            
            if validation["passed"]:
                valid_addresses.append(address)
                print(f"  ✅ ACCEPTED ({len(valid_addresses)}/{per_country}): {address[:70]}...")
                sys.stdout.flush()
            else:
                if verbose:
                    print(f"  ⏭️  Rejected")
                sys.stdout.flush()
            
            # Rate limiting
            time.sleep(NOMINATIM_SLEEP)
        
        print(f"\n  📊 Progress: {len(valid_addresses)}/{per_country} valid addresses found")
        sys.stdout.flush()
    
    print(f"\n{'='*80}")
    print(f"FINAL RESULTS FOR {country.upper()}")
    print(f"{'='*80}")
    print(f"✅ Generated {len(valid_addresses)}/{per_country} valid addresses")
    
    if valid_addresses:
        print(f"\n📋 Valid addresses:")
        for i, addr in enumerate(valid_addresses, 1):
            print(f"  {i}. {addr}")
    else:
        print(f"\n⚠️  No valid addresses found!")
    
    print(f"{'='*80}\n")
    sys.stdout.flush()
    
    return valid_addresses

def test_with_rewards(addresses: List[str], country: str) -> Dict[str, Any]:
    """
    Test all addresses with rewards.py _grade_address_variations.
    """
    validator = MockValidator()
    miner = MockMiner()
    
    print(f"\n{'='*80}")
    print(f"TESTING WITH REWARDS.PY")
    print(f"{'='*80}\n")
    sys.stdout.flush()
    
    variations = {
        'John Smith': [
            ['John Smith', '1990-01-01', addr] for addr in addresses
        ]
    }
    
    result = _grade_address_variations(
        variations=variations,
        seed_addresses=[country],
        miner_metrics={},
        validator_uid=validator.uid,
        miner_uid=miner.uid
    )
    
    overall_score = result.get('overall_score', 0.0)
    breakdown = result.get('detailed_breakdown', {})
    validation_results = breakdown.get('validation_results', {}).get('John Smith', [])
    api_validation = breakdown.get('api_validation', {})
    api_attempts = api_validation.get('api_attempts', [])
    
    print(f"📊 FINAL SCORES:")
    print(f"  Overall Score: {overall_score:.4f}")
    
    if validation_results:
        looks_count = sum(1 for r in validation_results if r.get('looks_like_address', False))
        region_count = sum(1 for r in validation_results if r.get('region_match', False))
        passed_count = sum(1 for r in validation_results if r.get('passed_validation', False))
        
        print(f"  Looks Like Address: {looks_count}/{len(addresses)}")
        print(f"  Region Match: {region_count}/{len(addresses)}")
        print(f"  Passed Validation: {passed_count}/{len(addresses)}")
    
    if api_attempts:
        api_scores = []
        for attempt in api_attempts:
            r = attempt.get('result', 0.0)
            if isinstance(r, (int, float)):
                api_scores.append(r)
            elif isinstance(r, dict):
                api_scores.append(r.get('score', 0.0))
        
        if api_scores:
            avg_api = sum(api_scores) / len(api_scores) if api_scores else 0.0
            print(f"  API Scores: {api_scores}")
            print(f"  Average API Score: {avg_api:.4f}")
            print(f"  API Addresses Checked: {len(api_attempts)}")
    
    print(f"\n{'='*80}\n")
    sys.stdout.flush()
    
    return result

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate and validate addresses from Nominatim")
    parser.add_argument("--country", type=str, required=True, help="Country name")
    parser.add_argument("--count", type=int, default=15, help="Number of addresses to generate (default: 15)")
    parser.add_argument("--cities", type=str, nargs="+", help="Optional list of cities to search")
    parser.add_argument("--test", action="store_true", help="Test generated addresses with rewards.py")
    
    args = parser.parse_args()
    
    # Generate addresses
    addresses = generate_addresses_for_country(
        country=args.country,
        per_country=args.count,
        cities=args.cities,
        verbose=True
    )
    
    # Test with rewards.py if requested
    if args.test and addresses:
        test_with_rewards(addresses, args.country)

