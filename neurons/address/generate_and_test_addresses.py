#!/usr/bin/env python3
"""
Generate addresses using Overpass API (OpenStreetMap) and validate with rewards.py
- Query Overpass for real buildings with address tags
- Assemble addresses from OSM data
- Validate each address and cache perfect ones
- Final batch validation with rewards.py to get score
"""

import os
import sys
import json
import time
import logging
import argparse
import requests
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
import re

# Parse arguments BEFORE importing bittensor
_original_argv = sys.argv.copy()
_saved_argv = sys.argv
sys.argv = [sys.argv[0]]

# Add MIID validator to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
sys.path.insert(0, os.path.join(BASE_DIR, 'MIID', 'validator'))

# Import from rewards.py
from reward import (
    looks_like_address,
    validate_address_region,
    check_with_nominatim,
    _grade_address_variations
)

# Restore argv
sys.argv = _saved_argv

# Overpass API endpoint
OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_TIMEOUT = 30

# Setup logging
def setup_logging():
    """Setup detailed logging"""
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"address_generation_{timestamp}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info("ADDRESS GENERATION AND VALIDATION STARTED (Overpass API)")
    logger.info("=" * 80)
    logger.info(f"Log file: {log_file}")
    logger.info("=" * 80)
    
    return logger

def get_country_area_id(country: str) -> Optional[int]:
    """Get OSM area ID for a country using Nominatim"""
    try:
        # Rate limit before Nominatim call
        time.sleep(1.0)
        
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": country,
            "format": "json",
            "limit": 1,
            "addressdetails": 1
        }
        # Proper User-Agent with contact info (REQUIRED by Nominatim)
        user_agent = os.getenv("USER_AGENT", "AddressGenerator/1.0 (contact: youremail@example.com)")
        headers = {"User-Agent": user_agent}
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        results = response.json()
        
        if results and len(results) > 0:
            # Try to get relation ID (area ID)
            osm_id = results[0].get("osm_id")
            osm_type = results[0].get("osm_type")
            
            if osm_type == "relation":
                return int(osm_id)
            elif osm_type == "way":
                # For ways, we need to find the relation
                # This is a simplified approach - may need refinement
                return None
        return None
    except Exception as e:
        logging.warning(f"Failed to get area ID for {country}: {e}")
        return None

def query_overpass_for_addresses(country: str, city: Optional[str] = None, limit: int = 500) -> List[Dict[str, Any]]:
    """
    Query Overpass API for buildings with address tags
    
    Returns list of dicts with address components
    """
    logger = logging.getLogger(__name__)
    
    # Build query - restrict to country first, then city within country
    # This ensures we get the correct city (e.g., Oxford UK, not Oxford Ohio)
    if city:
        # Find country area first, then city within country
        # This is the CORRECT way to avoid matching wrong cities
        overpass_query = f"""
        [out:json][timeout:{OVERPASS_TIMEOUT}];
        area["name"="{country}"]["admin_level"="2"]->.country;
        area["name"="{city}"]["place"~"^(city|town)$"](area.country)->.city;
        (
          nwr["addr:housenumber"]["addr:street"](area.city);
        );
        out body;
        >;
        out skel qt;
        """
    else:
        # Search country-wide
        overpass_query = f"""
        [out:json][timeout:{OVERPASS_TIMEOUT}];
        area["name"="{country}"]["admin_level"="2"]->.country;
        (
          nwr["addr:housenumber"]["addr:street"](area.country);
        );
        out body;
        >;
        out skel qt;
        """
    
    logger.info(f"📡 Querying Overpass API for {country}" + (f" (city: {city})" if city else ""))
    logger.debug(f"Overpass query: {overpass_query[:200]}...")
    
    try:
        start_time = time.time()
        response = requests.post(
            OVERPASS_API_URL,
            data=overpass_query,
            headers={"Content-Type": "text/plain"},
            timeout=OVERPASS_TIMEOUT + 10
        )
        elapsed = time.time() - start_time
        
        if response.status_code != 200:
            logger.error(f"❌ Overpass API error: {response.status_code} - {response.text[:200]}")
            return []
        
        data = response.json()
        logger.info(f"✅ Overpass response received in {elapsed:.2f} seconds")
        
        elements = data.get("elements", [])
        logger.info(f"   Found {len(elements)} elements")
        
        # Extract address components
        addresses = []
        for element in elements:
            tags = element.get("tags", {})
            
            # Required tags
            housenumber = tags.get("addr:housenumber")
            street = tags.get("addr:street")
            
            if not housenumber or not street:
                continue
            
            # Get country from tags - filter by country
            country_name = tags.get("addr:country") or country
            
            # Normalize country names for comparison
            country_normalized = country.lower().strip()
            country_name_normalized = country_name.lower().strip() if country_name else ""
            
            # Country name variations mapping
            country_variations = {
                "united kingdom": ["uk", "great britain", "britain", "england", "scotland", "wales", "gb"],
                "usa": ["united states", "united states of america", "us"],
                "russia": ["russian federation", "ru"],
            }
            
            # Check if country matches (with variations)
            country_matches = False
            if not country_name_normalized:
                # If no country tag, assume it matches (area query should have filtered)
                country_matches = True
            elif country_name_normalized == country_normalized:
                country_matches = True
            else:
                # Check variations
                variations = country_variations.get(country_normalized, [])
                if country_name_normalized in variations:
                    country_matches = True
                # Also check reverse
                for key, vals in country_variations.items():
                    if country_normalized in vals and country_name_normalized == key:
                        country_matches = True
                        break
            
            if not country_matches:
                continue
            
            # Optional but preferred tags
            city_name = tags.get("addr:city") or tags.get("addr:place") or tags.get("addr:suburb") or city
            postcode = tags.get("addr:postcode")
            
            # Get coordinates
            lat = element.get("lat")
            lon = element.get("lon")
            
            # For ways/relations, we might need to get centroid
            if lat is None or lon is None:
                if "center" in element:
                    lat = element["center"].get("lat")
                    lon = element["center"].get("lon")
            
            # Additional filtering: if we have coordinates, verify they're in the right country
            # For UK, lat should be ~50-60, lon should be ~-8 to 2
            if lat and lon:
                if country.lower() in ["united kingdom", "uk", "great britain"]:
                    # UK coordinates: lat 49-61, lon -8 to 2
                    if not (49 <= lat <= 61 and -8 <= lon <= 2):
                        continue
                elif country.lower() in ["usa", "united states", "united states of america"]:
                    # USA coordinates: lat 24-50, lon -125 to -66
                    if not (24 <= lat <= 50 and -125 <= lon <= -66):
                        continue
            
            if not city_name:
                continue
            
            address_data = {
                "housenumber": housenumber,
                "street": street,
                "city": city_name,
                "postcode": postcode,
                "country": country_name or country,
                "lat": lat,
                "lon": lon,
                "osm_type": element.get("type"),
                "osm_id": element.get("id")
            }
            
            addresses.append(address_data)
        
        logger.info(f"✅ Extracted {len(addresses)} addresses with required tags")
        return addresses
        
    except requests.exceptions.Timeout:
        logger.error("❌ Overpass API timeout")
        return []
    except Exception as e:
        logger.error(f"❌ Overpass API error: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return []

def assemble_address(address_data: Dict[str, Any]) -> str:
    """Assemble address string from OSM data"""
    parts = []
    
    # House number and street
    if address_data.get("housenumber") and address_data.get("street"):
        parts.append(f"{address_data['housenumber']} {address_data['street']}")
    
    # City
    if address_data.get("city"):
        parts.append(address_data["city"])
    
    # Postcode
    if address_data.get("postcode"):
        parts.append(address_data["postcode"])
    
    # Country
    if address_data.get("country"):
        parts.append(address_data["country"])
    
    return ", ".join(parts)

def validate_single_address(address: str, country: str, logger: logging.Logger) -> Tuple[bool, float, Dict[str, Any]]:
    """
    Validate a single address using rewards.py functions
    Returns: (is_perfect, score, details)
    """
    details = {
        "address": address,
        "heuristic": False,
        "region": False,
        "api_score": 0.0,
        "api_area": None,
        "api_result": None
    }
    
    # Step 1: Heuristic check
    logger.info(f"      Step 1: Heuristic check...")
    heuristic_result = looks_like_address(address)
    details["heuristic"] = heuristic_result
    
    if not heuristic_result:
        logger.info(f"         ❌ FAILED: Address format invalid")
        return False, 0.0, details
    
    logger.info(f"         ✅ PASSED: Address format valid")
    
    # Step 2: Region validation
    logger.info(f"      Step 2: Region validation...")
    region_result = validate_address_region(address, country)
    details["region"] = region_result
    
    if not region_result:
        logger.info(f"         ❌ FAILED: Region mismatch (not in {country})")
        return False, 0.0, details
    
    logger.info(f"         ✅ PASSED: Region matches {country}")
    
    # Step 3: Nominatim API check
    logger.info(f"      Step 3: Nominatim API check...")
    # CRITICAL: Rate limit BEFORE Nominatim call (1 second minimum)
    time.sleep(1.0)
    api_start = time.time()
    api_result = check_with_nominatim(
        address=address,
        validator_uid=101,
        miner_uid=501,
        seed_address=country,
        seed_name="Generator"
    )
    api_elapsed = time.time() - api_start
    
    if isinstance(api_result, dict):
        details["api_result"] = "SUCCESS"
        details["api_score"] = float(api_result.get("score", 0.0))
        details["api_area"] = float(api_result.get("min_area", 0.0)) if api_result.get("min_area") is not None else None
        
        # Get detailed failure reasons
        failure_reason = api_result.get("failure_reason", "Unknown")
        found_building = api_result.get("found_building", False)
        min_area = api_result.get("min_area", None)
        
        is_perfect = details["api_score"] >= 0.99
        
        if is_perfect:
            logger.info(f"         ✅ PASSED: Score={details['api_score']:.4f}, Area={details['api_area']:.2f} m² (took {api_elapsed:.2f}s)")
        else:
            logger.info(f"         ❌ FAILED: Score={details['api_score']:.4f} (took {api_elapsed:.2f}s)")
            logger.info(f"            Reason: {failure_reason}")
            logger.info(f"            Found building: {found_building}")
            if min_area is not None:
                logger.info(f"            Building area: {min_area:.2f} m² (needs < 100 m²)")
            else:
                logger.info(f"            Building area: None (no building found or no polygon)")
        
        return is_perfect, details["api_score"], details
    elif api_result == "TIMEOUT":
        details["api_result"] = "TIMEOUT"
        logger.warning(f"         ⏱️  TIMEOUT: API call timed out (took {api_elapsed:.2f}s)")
        return False, 0.0, details
    else:
        details["api_result"] = "FAILED"
        logger.info(f"         ❌ FAILED: API returned {api_result} (took {api_elapsed:.2f}s)")
        logger.info(f"            ⚠️  REASON: Address not found in OpenStreetMap")
        logger.info(f"            This means:")
        logger.info(f"            - Nominatim search returned 0 results")
        logger.info(f"            - Address doesn't exist in OSM database")
        logger.info(f"            - OR address format doesn't match OSM data")
        logger.info(f"            - OR country has weak OSM coverage")
        return False, 0.0, details

def generate_and_validate_addresses(country: str, target: int, logger: logging.Logger, city: Optional[str] = None) -> List[str]:
    """Query Overpass, assemble addresses, and validate until target reached"""
    
    perfect_addresses = []
    tried_addresses = set()
    attempt = 0
    max_attempts = 5
    query_limit = 500
    
    # Try major cities if no city specified
    cities_to_try = [city] if city else []
    
    # If no city specified, try to query country-wide
    if not cities_to_try:
        cities_to_try = [None]  # None means country-wide
    
    while len(perfect_addresses) < target and attempt < max_attempts:
        attempt += 1
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"ATTEMPT {attempt}/{max_attempts}")
        logger.info("=" * 80)
        logger.info(f"Current progress: {len(perfect_addresses)}/{target} perfect addresses")
        
        # Query Overpass
        current_city = cities_to_try[(attempt - 1) % len(cities_to_try)] if cities_to_try else None
        address_data_list = query_overpass_for_addresses(country, current_city, limit=query_limit)
        
        if not address_data_list:
            logger.warning(f"⚠️  No addresses found from Overpass. Trying next city or increasing limit...")
            query_limit = min(query_limit * 2, 2000)  # Increase limit for next attempt
            time.sleep(5)  # Rate limit
            continue
        
        # Assemble addresses
        candidates = []
        for addr_data in address_data_list:
            assembled = assemble_address(addr_data)
            if assembled and assembled not in tried_addresses:
                tried_addresses.add(assembled)
                candidates.append((assembled, addr_data))
        
        logger.info(f"📋 Testing {len(candidates)} unique candidate addresses...")
        logger.info(f"   Estimated time: ~{len(candidates) * 2 / 60:.1f} minutes (2s per address)")
        
        # Validate each candidate
        for idx, (addr, addr_data) in enumerate(candidates, 1):
            logger.info("")
            logger.info(f"  [{idx}/{len(candidates)}] Validating: {addr[:70]}...")
            
            is_perfect, score, details = validate_single_address(addr, country, logger)
            
            if is_perfect:
                perfect_addresses.append(addr)
                logger.info(f"  ✅ PERFECT ADDRESS FOUND! ({len(perfect_addresses)}/{target})")
                
                if len(perfect_addresses) >= target:
                    logger.info("")
                    logger.info("🎉 TARGET REACHED! Found 15 perfect addresses")
                    return perfect_addresses
            
            # Rate limit AFTER validation (additional delay to ensure 1 req/sec)
            # Note: We already sleep 1s BEFORE the API call, so this ensures spacing
            time.sleep(1.0)  # Total: 1s before + API call time + 1s after = safe spacing
        
        logger.info("")
        logger.info(f"Attempt {attempt} complete: {len(perfect_addresses)}/{target} perfect addresses found")
        
        # Rate limit between Overpass queries
        if len(perfect_addresses) < target:
            logger.info("⏳ Waiting 5 seconds before next Overpass query...")
            time.sleep(5)
    
    return perfect_addresses

def test_batch_with_rewards(addresses: List[str], country: str, logger: logging.Logger) -> Dict[str, Any]:
    """Test all addresses together with _grade_address_variations"""
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("BATCH VALIDATION WITH rewards.py")
    logger.info("=" * 80)
    logger.info(f"Testing {len(addresses)} addresses together...")
    
    variations = {
        'Test': [['Test', '1990-01-01', addr] for addr in addresses]
    }
    
    logger.info("Calling _grade_address_variations from rewards.py...")
    result = _grade_address_variations(
        variations=variations,
        seed_addresses=[country],
        miner_metrics={},
        validator_uid=101,
        miner_uid=501
    )
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("FINAL SCORE FROM rewards.py")
    logger.info("=" * 80)
    logger.info(f"Overall Score: {result.get('overall_score', 0.0):.4f}")
    logger.info(f"Heuristic Perfect: {result.get('heuristic_perfect', False)}")
    logger.info(f"Region Matches: {result.get('region_matches', 0)}/{len(addresses)}")
    logger.info(f"Total Addresses: {result.get('total_addresses', 0)}")
    logger.info(f"API Result: {result.get('api_result', 'N/A')}")
    
    # API details
    breakdown = result.get('detailed_breakdown', {})
    api_validation = breakdown.get('api_validation', {})
    
    if api_validation:
        logger.info("")
        logger.info("API Validation Details:")
        logger.info(f"  Total eligible: {api_validation.get('total_eligible_addresses', 0)}")
        logger.info(f"  API calls made: {api_validation.get('total_calls', 0)}")
        logger.info(f"  Successful: {api_validation.get('total_successful_calls', 0)}")
        logger.info(f"  Failed: {api_validation.get('total_failed_calls', 0)}")
        
        api_attempts = api_validation.get('api_attempts', [])
        if api_attempts:
            logger.info("")
            logger.info("Individual API Results:")
            for i, attempt in enumerate(api_attempts, 1):
                addr = attempt.get('address', 'N/A')
                api_result_val = attempt.get('result', 'N/A')
                score_details = attempt.get('score_details', {}) or {}
                
                if isinstance(api_result_val, (int, float)):
                    area = score_details.get('min_area', 'N/A') if score_details else 'N/A'
                    status = "✅" if api_result_val >= 0.99 else "❌"
                    logger.info(f"  {status} [{i}] {addr[:60]}...")
                    logger.info(f"      Score: {api_result_val:.4f}, Area: {area} m²")
    
    logger.info("=" * 80)
    
    return result

def main():
    parser = argparse.ArgumentParser(description="Generate and validate addresses with Overpass API")
    parser.add_argument("--country", required=True, help="Country name")
    parser.add_argument("--city", default=None, help="City name (optional, for more targeted search)")
    parser.add_argument("--target", type=int, default=15, help="Target perfect addresses")
    parser.add_argument("--output", default=None, help="Output JSON file")
    
    args = parser.parse_args()
    
    logger = setup_logging()
    
    # Generate and validate
    logger.info("")
    logger.info("=" * 80)
    logger.info(f"GENERATING ADDRESSES FOR: {args.country}" + (f" (city: {args.city})" if args.city else ""))
    logger.info("=" * 80)
    logger.info("Using Overpass API to query OpenStreetMap for real addresses")
    logger.info("=" * 80)
    
    start_time = time.time()
    perfect_addresses = generate_and_validate_addresses(args.country, args.target, logger, city=args.city)
    generation_time = time.time() - start_time
    
    if len(perfect_addresses) < args.target:
        logger.warning(f"⚠️  Only found {len(perfect_addresses)}/{args.target} perfect addresses")
    else:
        logger.info(f"✅ Successfully generated {len(perfect_addresses)} perfect addresses in {generation_time:.1f} seconds")
    
    # Test batch with rewards.py
    if perfect_addresses:
        result = test_batch_with_rewards(perfect_addresses, args.country, logger)
        
        # Save results
        if args.output:
            output_data = {
                "country": args.country,
                "city": args.city,
                "perfect_addresses": perfect_addresses,
                "count": len(perfect_addresses),
                "final_score": result.get('overall_score', 0.0),
                "validation_result": result,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
            
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Results saved to {args.output}")
    else:
        logger.error("❌ No perfect addresses found. Cannot test batch validation.")

if __name__ == "__main__":
    main()
