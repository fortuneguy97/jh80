#!/usr/bin/env python3

"""
Validated Address Cache Generator

This script generates addresses and validates each one using rewards.py functions
to ensure they score exactly 1.0. Only addresses that pass all checks and score
1.0 are accepted.

After generating 15 addresses for a country, it tests them all together using
_grade_address_variations to confirm they all score 1.0.

Usage:
    python3 generate_validated_address_cache.py --country "Poland"
    python3 generate_validated_address_cache.py --country "Russia"
    python3 generate_validated_address_cache.py  # Process all countries
"""

import os
import sys
import json
import time
import random
import requests
import geonamescache
import math
import signal
import shutil
import argparse
from typing import List, Tuple, Dict

# Force unbuffered output for real-time logging
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

# Put MIID validator on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

from reward import (
    looks_like_address,
    extract_city_country,
    validate_address_region,
    compute_bounding_box_areas_meters,
    check_with_nominatim,
    _grade_address_variations
)

# Configuration
OVERPASS_URL = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
NOMINATIM_URL = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org/reverse")
USER_AGENT = os.getenv("USER_AGENT", "MIID-Address-Gen/1.0 (contact@example.com)")
CACHE_FILE = os.path.join(os.path.dirname(__file__), "validated_address_cache.json")  # Different location

# Safety/timeouts
NOMINATIM_SLEEP = 1.0
OVERPASS_SLEEP = 1.0
MAX_OVERPASS_TIMEOUT = 180
MAX_OVERPASS_NODES = 2000
MAX_ATTEMPTS_PER_COUNTRY = 2000

# Global error tracking
_nominatim_403_count = 0
_nominatim_403_threshold = 10

# Import helper functions from original script
# (We'll copy the essential ones here)

def node_tags_to_display_name(node_tags: dict, country: str) -> str:
    """Build display_name from node tags."""
    parts = []
    if not node_tags:
        return None
    
    housen = node_tags.get("addr:housenumber")
    street = node_tags.get("addr:street") or node_tags.get("street") or node_tags.get("addr:place")
    
    if housen and street:
        parts.append(f"{housen}")
        parts.append(street)
    elif housen:
        parts.append(f"{housen}")
        if node_tags.get("name"):
            parts.append(node_tags.get("name"))
    elif street:
        parts.append(street)
    elif node_tags.get("name"):
        parts.append(node_tags.get("name"))
    
    # Add city/location
    for k in ("addr:city", "city", "town", "village", "suburb", "addr:district", "addr:suburb"):
        if node_tags.get(k):
            parts.append(node_tags.get(k))
            break
    
    # Add postcode if available
    if node_tags.get("addr:postcode"):
        parts.append(node_tags.get("addr:postcode"))
    
    # Add country
    parts.append(country)
    display = ", ".join([p for p in parts if p])
    return display if display else None

def validate_address_locally(address: str, seed_address: str, verbose: bool = False) -> bool:
    """
    Fast local validation (no API calls).
    Returns True if address passes heuristic and region checks.
    """
    # Step 1: Heuristic check
    if verbose:
        print(f"        🔍 Checking heuristic (30+ chars, 20+ letters, 2+ commas)...")
    
    if not looks_like_address(address):
        if verbose:
            char_count = len(address)
            letter_count = sum(c.isalpha() for c in address)
            comma_count = address.count(',')
            print(f"        ❌ Heuristic FAILED: chars={char_count}, letters={letter_count}, commas={comma_count}")
        return False
    
    if verbose:
        print(f"        ✅ Heuristic passed")
    
    # Step 2: Region validation
    if verbose:
        print(f"        🔍 Checking region validation (must match '{seed_address}')...")
    
    if not validate_address_region(address, seed_address):
        if verbose:
            gen_city, gen_country = extract_city_country(address, two_parts=(',' in seed_address))
            print(f"        ❌ Region FAILED: extracted city='{gen_city}', country='{gen_country}', seed='{seed_address}'")
        return False
    
    if verbose:
        print(f"        ✅ Region validation passed")
    
    return True

def validate_address_with_api(address: str, seed_address: str, verbose: bool = False) -> Tuple[bool, float, Dict]:
    """
    Validate an address using rewards.py API check (SLOW - makes API call).
    Only call this after local validation passes.
    
    Returns:
        (is_valid, score, details) tuple
        is_valid: True if address scores 1.0
        score: The actual score (0.0 to 1.0)
        details: Detailed validation results
    """
    details = {
        'api': False,
        'api_score': 0.0,
        'area': None
    }
    
    # API check (this is the critical one for score 1.0)
    # Use check_with_nominatim from rewards.py
    api_result = check_with_nominatim(
        address=address,
        validator_uid=101,  # Mock validator UID
        miner_uid=501,      # Mock miner UID
        seed_address=seed_address,
        seed_name="Test"    # Mock seed name
    )
    
    if api_result == "TIMEOUT":
        if verbose:
            print(f"        ⚠️  API timeout")
        return False, 0.0, details
    
    if api_result == 0.0:
        if verbose:
            print(f"        ❌ API check failed (no results)")
        return False, 0.0, details
    
    if isinstance(api_result, dict):
        api_score = api_result.get('score', 0.0)
        details['api_score'] = api_score
        details['area'] = api_result.get('min_area')
        
        if api_score >= 0.99:  # Score 1.0 (with small tolerance)
            details['api'] = True
            if verbose:
                print(f"        ✅ API check passed (score: {api_score:.4f}, area: {details['area']:.2f} m²)")
            return True, api_score, details
        else:
            if verbose:
                print(f"        ❌ API check failed (score: {api_score:.4f} < 1.0)")
            return False, api_score, details
    else:
        # Fallback if api_result is a float
        if api_result >= 0.99:
            details['api'] = True
            details['api_score'] = api_result
            return True, api_result, details
        else:
            return False, api_result, details

def fetch_nodes_from_overpass_bbox(bbox: Tuple[float, float, float, float], timeout: int = 180, verbose: bool = True) -> List[dict]:
    """Fetch nodes from Overpass API for a bounding box."""
    min_lat, min_lon, max_lat, max_lon = bbox
    if verbose:
        print(f"     🔍 Querying Overpass API for bbox ({min_lat:.4f}, {min_lon:.4f}, {max_lat:.4f}, {max_lon:.4f})...")
    
    query = f"""
[out:json][timeout:{timeout}];
(
  node["addr:housenumber"]({min_lat},{min_lon},{max_lat},{max_lon});
  node["entrance"]({min_lat},{min_lon},{max_lat},{max_lon});
  node["amenity"]({min_lat},{min_lon},{max_lat},{max_lon});
  node["shop"]({min_lat},{min_lon},{max_lat},{max_lon});
  node["office"]({min_lat},{min_lon},{max_lat},{max_lon});
  node["building"="residential"]({min_lat},{min_lon},{max_lat},{max_lon});
  node["building"="yes"]({min_lat},{min_lon},{max_lat},{max_lon});
  node["tourism"]({min_lat},{min_lon},{max_lat},{max_lon});
  node["historic"]({min_lat},{min_lon},{max_lat},{max_lon});
  node["building"="commercial"]({min_lat},{min_lon},{max_lat},{max_lon});
  node["building"="retail"]({min_lat},{min_lon},{max_lat},{max_lon});
  node["building"="house"]({min_lat},{min_lon},{max_lat},{max_lon});
  node["building"="apartments"]({min_lat},{min_lon},{max_lat},{max_lon});
  node["healthcare"]({min_lat},{min_lon},{max_lat},{max_lon});
  node["leisure"]({min_lat},{min_lon},{max_lat},{max_lon});
  node["craft"]({min_lat},{min_lon},{max_lat},{max_lon});
  node["industrial"]({min_lat},{min_lon},{max_lat},{max_lon});
  node["public_transport"]({min_lat},{min_lon},{max_lat},{max_lon});
  node["addr:street"]({min_lat},{min_lon},{max_lat},{max_lon});
  node["addr:place"]({min_lat},{min_lon},{max_lat},{max_lon});
);
out body;
"""
    
    try:
        r = requests.post(OVERPASS_URL, data={'data': query}, timeout=timeout + 10, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        data = r.json()
        elements = data.get("elements", [])
        if verbose:
            print(f"     ✅ Overpass returned {len(elements)} nodes")
        time.sleep(OVERPASS_SLEEP)
        return elements
    except Exception as e:
        if verbose:
            print(f"     ❌ Overpass error: {e}")
        return []

def reverse_geocode(lat: float, lon: float, zoom: int = 19, verbose: bool = False, max_retries: int = 3) -> dict:
    """Reverse geocode coordinates to get address."""
    global _nominatim_403_count
    
    params = {
        "format": "json",
        "lat": str(lat),
        "lon": str(lon),
        "zoom": str(zoom),
        "addressdetails": "1",
        "extratags": "1",
        "namedetails": "1",
        "accept-language": "en"
    }
    headers = {"User-Agent": USER_AGENT}
    
    for attempt in range(max_retries):
        try:
            r = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=15)
            
            if r.status_code == 403:
                _nominatim_403_count += 1
                retry_after = 5 * (2 ** attempt)
                if verbose:
                    print(f"        ⚠️  Nominatim HTTP 403 (rate limited)")
                if attempt < max_retries - 1:
                    time.sleep(retry_after)
                    continue
                return {}
            
            if r.status_code != 200:
                return {}
            
            data = r.json()
            time.sleep(NOMINATIM_SLEEP)
            return data
            
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return {}
    
    return {}

def generate_addresses_for_country(country: str, per_country: int = 15, verbose: bool = True) -> List[str]:
    """Generate validated addresses for a country (all must score 1.0)."""
    results = []
    gc = geonamescache.GeonamesCache()
    
    # Get country code from country name
    countries = gc.get_countries()
    country_code = None
    for code, data in countries.items():
        if data.get('name', '').lower() == country.lower():
            country_code = code.upper()
            break
    
    if not country_code:
        if verbose:
            print(f"  ❌ Country '{country}' not found in GeonamesCache")
        return results
    
    # Get cities for the country
    cities = gc.get_cities()
    country_cities = []
    for city_id, city_data in cities.items():
        if city_data.get('countrycode', '').upper() == country_code:
            country_cities.append(city_data)
    
    if not country_cities:
        if verbose:
            print(f"  ⚠️  No cities found for {country}")
        return results
    
    # Sort by population
    country_cities.sort(key=lambda x: x.get('population', 0), reverse=True)
    center_cities = country_cities[:20]  # Top 20 cities
    
    if verbose:
        print(f"  📍 Processing {len(center_cities)} cities...")
    
    attempts = 0
    for city_data in center_cities:
        if len(results) >= per_country:
            break
        
        lat = city_data.get('latitude', 0)
        lon = city_data.get('longitude', 0)
        
        # Create bbox around city
        bbox = (lat - 0.05, lon - 0.05, lat + 0.05, lon + 0.05)
        
        # Fetch nodes
        nodes = fetch_nodes_from_overpass_bbox(bbox, verbose=verbose)
        
        # Prioritize nodes with address tags (more likely to have valid addresses)
        def node_priority(node):
            tags = node.get("tags", {}) or {}
            priority = 0
            if "addr:housenumber" in tags:
                priority += 10
            if "addr:street" in tags:
                priority += 5
            if "addr:city" in tags:
                priority += 2
            return priority
        
        sorted_nodes = sorted(nodes, key=node_priority, reverse=True)
        
        if verbose:
            print(f"     📊 Prioritized {len(sorted_nodes)} nodes (nodes with addr:housenumber first)")
        
        # Process nodes
        for node_idx, node in enumerate(sorted_nodes, 1):
            if len(results) >= per_country:
                if verbose:
                    print(f"\n  ✅ Found {len(results)}/{per_country} addresses! Moving to next city...")
                break
            
            attempts += 1
            if attempts > MAX_ATTEMPTS_PER_COUNTRY:
                if verbose:
                    print(f"\n  ⚠️  Max attempts ({MAX_ATTEMPTS_PER_COUNTRY}) reached for {country}")
                break
            
            if verbose and node_idx % 50 == 0:
                print(f"\n  📊 Progress: Processed {node_idx}/{len(sorted_nodes)} nodes, found {len(results)}/{per_country} addresses so far...")
            
            # Use reverse geocoding to get full address from Nominatim
            lat = node.get("lat")
            lon = node.get("lon")
            if not lat or not lon:
                continue
            
            # Check if node has address tags (prioritize these)
            tags = node.get("tags", {}) or {}
            has_addr_tags = "addr:housenumber" in tags or "addr:street" in tags
            
            # Reverse geocode to get Nominatim's full address
            if verbose:
                addr_note = " (has addr tags)" if has_addr_tags else ""
                print(f"\n  🔄 [{attempts}] Reverse geocoding node at ({lat:.4f}, {lon:.4f}){addr_note}...")
            
            nom_result = reverse_geocode(lat, lon, zoom=19, verbose=verbose)
            if not nom_result or "display_name" not in nom_result:
                if verbose:
                    print(f"     ❌ No result from reverse geocoding")
                continue
            
            display = nom_result["display_name"]
            if verbose:
                print(f"     📍 Got address: {display[:80]}...")
            
            # Check if address starts with house number (like Poland format: "26, Siedlisko...")
            first_part = display.split(",")[0].strip()
            has_number_at_start = first_part and first_part[0].isdigit()
            
            if verbose:
                print(f"\n  🔍 [{attempts}] Processing: {display[:70]}...")
            
            if not has_number_at_start:
                if verbose:
                    print(f"     ❌ SKIPPED: No house number at start (first part: '{first_part}')")
                continue
            
            if verbose:
                print(f"     ✅ Has house number at start: '{first_part}'")
            
            # FAST: Local validation first (no API call)
            if verbose:
                print(f"     🔍 Step 1: Local validation (heuristic + region)...")
            
            if not validate_address_locally(display, country, verbose=verbose):
                if verbose:
                    print(f"     ❌ REJECTED: Failed local validation")
                continue
            
            if verbose:
                print(f"     ✅ Local validation passed")
            
            # SLOW: API validation only for addresses that pass local checks
            if verbose:
                print(f"     🔍 Step 2: API validation (checking with Nominatim, score must be 1.0)...")
            
            is_valid, score, details = validate_address_with_api(display, country, verbose=verbose)
            
            if is_valid and score >= 0.99:
                results.append(display)
                if verbose:
                    print(f"     ✅✅✅ ACCEPTED [{len(results)}/{per_country}] (score: {score:.4f}, area: {details.get('area', 'N/A')} m²)")
                    print(f"     📍 Address: {display}")
            else:
                if verbose:
                    print(f"     ❌ REJECTED: Score {score:.4f} < 1.0 (area: {details.get('area', 'N/A')} m²)")
            
            time.sleep(NOMINATIM_SLEEP)  # Respect rate limit (1 req/sec)
        
        time.sleep(OVERPASS_SLEEP)
    
    return results

def test_addresses_with_validator(addresses: List[str], country: str, verbose: bool = True) -> Dict:
    """
    Test all addresses together using _grade_address_variations (like validator does).
    
    Returns:
        Dictionary with test results
    """
    if not addresses:
        return {"error": "No addresses to test"}
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"TESTING {len(addresses)} ADDRESSES WITH VALIDATOR")
        print(f"{'='*60}")
    
    # Format addresses like validator expects
    # variations: Dict[str, List[List[str]]] = {name: [[name_var, dob_var, addr_var], ...]}
    variations = {
        "Test Name": [
            ["Test Name", "1990-01-01", addr] for addr in addresses
        ]
    }
    
    # Seed addresses (one per name, but we only have one name)
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
    
    if verbose:
        print(f"\n📊 VALIDATION RESULTS:")
        print(f"   Overall Score: {overall_score:.4f}")
        print(f"   Heuristic Perfect: {heuristic_perfect}")
        print(f"   Region Matches: {region_matches}/{len(addresses)}")
        print(f"   API Result: {api_result}")
        
        if overall_score >= 0.99:
            print(f"\n✅ SUCCESS: All addresses score 1.0!")
        else:
            print(f"\n❌ FAILURE: Score is {overall_score:.4f} (expected 1.0)")
            print(f"   Details: {result.get('detailed_breakdown', {})}")
    
    return {
        'overall_score': overall_score,
        'heuristic_perfect': heuristic_perfect,
        'region_matches': region_matches,
        'api_result': api_result,
        'total_addresses': len(addresses),
        'all_passed': overall_score >= 0.99
    }

def save_cache_safely(cache: dict, filepath: str):
    """Save cache atomically."""
    tmp_file = filepath + ".tmp"
    backup_file = filepath + ".backup"
    
    try:
        # Backup existing file
        if os.path.exists(filepath):
            shutil.copy2(filepath, backup_file)
        
        # Write to temp file
        with open(tmp_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
        
        # Atomic rename
        os.rename(tmp_file, filepath)
    except Exception as e:
        print(f"⚠️  Error saving cache: {e}")

def load_cache(filepath: str) -> dict:
    """Load cache file."""
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            # Try backup
            backup = filepath + ".backup"
            if os.path.exists(backup):
                with open(backup, 'r', encoding='utf-8') as f:
                    return json.load(f)
    return {"addresses": {}, "metadata": {}}

def main():
    parser = argparse.ArgumentParser(description='Generate validated address cache (all addresses score 1.0)')
    parser.add_argument('--country', help='Specific country to process (default: all)')
    parser.add_argument('--count', type=int, default=15, help='Number of addresses per country (default: 15)')
    parser.add_argument('--verbose', action='store_true', default=True, help='Verbose output')
    
    args = parser.parse_args()
    
    # Load existing cache
    cache = load_cache(CACHE_FILE)
    if 'addresses' not in cache:
        cache['addresses'] = {}
    if 'metadata' not in cache:
        cache['metadata'] = {}
    
    # Get countries to process
    gc = geonamescache.GeonamesCache()
    countries = gc.get_countries()
    
    if args.country:
        # Process single country
        country_name = args.country
        print(f"\n{'='*60}")
        print(f"GENERATING VALIDATED ADDRESSES FOR: {country_name}")
        print(f"{'='*60}\n")
        
        addresses = generate_addresses_for_country(country_name, args.count, args.verbose)
        
        if len(addresses) >= args.count:
            # Test all addresses together
            test_result = test_addresses_with_validator(addresses, country_name, args.verbose)
            
            if test_result.get('all_passed'):
                # Save to cache
                cache['addresses'][country_name] = addresses
                cache['metadata'][country_name] = {
                    'count': len(addresses),
                    'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'test_score': test_result['overall_score']
                }
                save_cache_safely(cache, CACHE_FILE)
                print(f"\n✅ Successfully cached {len(addresses)} validated addresses for {country_name}")
            else:
                print(f"\n❌ Validation test failed. Not saving to cache.")
        else:
            print(f"\n⚠️  Only generated {len(addresses)}/{args.count} addresses for {country_name}")
    else:
        # Process all countries
        print(f"\n{'='*60}")
        print(f"GENERATING VALIDATED ADDRESSES FOR ALL COUNTRIES")
        print(f"{'='*60}\n")
        
        for country_code, country_data in countries.items():
            country_name = country_data.get('name', '')
            if not country_name:
                continue
            
            # Skip if already has enough addresses
            if country_name in cache['addresses']:
                existing = len(cache['addresses'][country_name])
                if existing >= args.count:
                    print(f"⏭️  Skipping {country_name} (already has {existing} addresses)")
                    continue
            
            print(f"\n{'='*60}")
            print(f"Processing: {country_name}")
            print(f"{'='*60}")
            
            addresses = generate_addresses_for_country(country_name, args.count, args.verbose)
            
            if len(addresses) >= args.count:
                # Test all addresses together
                test_result = test_addresses_with_validator(addresses, country_name, args.verbose)
                
                if test_result.get('all_passed'):
                    cache['addresses'][country_name] = addresses
                    cache['metadata'][country_name] = {
                        'count': len(addresses),
                        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'test_score': test_result['overall_score']
                    }
                    save_cache_safely(cache, CACHE_FILE)
                    print(f"✅ Cached {len(addresses)} addresses for {country_name}")
                else:
                    print(f"❌ Validation test failed for {country_name}")
            else:
                print(f"⚠️  Only {len(addresses)}/{args.count} addresses for {country_name}")
            
            time.sleep(2)  # Delay between countries

if __name__ == '__main__':
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\n\n⚠️  Interrupted. Saving cache...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    main()

