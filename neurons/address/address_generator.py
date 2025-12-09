#!/usr/bin/env python3

"""
address_generator.py

Single-file, production-oriented address generator + validator (Option A)
- Uses Overpass API to fetch buildings with addr:* tags
- Uses Nominatim for area lookup and to validate addresses
- Calls your existing rewards.py functions for final validation
- Local JSON cache of Overpass & Nominatim results to avoid rate limits
- Simple retry/backoff and rate-limiting

NOTE: This file was created to be placed in the same repo as your validator code.
If you uploaded a file earlier, you can find it at the local path used in your workspace, e.g.:
  /Users/prasad/cursor/MIID-subnet

How to run:
  export PYTHONPATH="$(pwd)/MIID/validator:$PYTHONPATH"
  python3 address_generator.py --country "United Kingdom" --city "Oxford" --target 15 --output uk_oxford.json

Requirements:
  pip install requests tqdm

Behavior summary:
  - query_overpass_for_addresses() fetches buildings with addr:housenumber & addr:street
  - assemble_address() builds the canonical address string
  - validate_single_address() runs looks_like_address(), validate_address_region(), check_with_nominatim()
  - caching in ./cache/ to speed up repeated runs

The script avoids aggressive concurrency to play nice with Overpass/Nominatim.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Make sure the validator path is available (same approach as your other scripts)
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
VALIDATOR_PATH = os.path.join(BASE_DIR, 'MIID', 'validator')
if VALIDATOR_PATH not in sys.path:
    sys.path.insert(0, VALIDATOR_PATH)

# Parse arguments BEFORE importing bittensor
_original_argv = sys.argv.copy()
_saved_argv = sys.argv
sys.argv = [sys.argv[0]]

# Import rewards helpers (these must exist in MIID/validator/reward.py)
try:
    from reward import (
        looks_like_address,
        validate_address_region,
        compute_bounding_box_areas_meters,  # For calculating areas
        _grade_address_variations,  # Only for batch validation
    )
except Exception as e:
    raise RuntimeError(f"Failed to import reward helpers from {VALIDATOR_PATH}: {e}")

# Restore argv
sys.argv = _saved_argv

import requests
from requests.adapters import HTTPAdapter, Retry
try:
    import socks
    import socket
    TOR_AVAILABLE = True
except ImportError:
    TOR_AVAILABLE = False

try:
    from tqdm import tqdm
except ImportError:
    # Fallback if tqdm not available
    def tqdm(iterable, desc=None):
        return iterable

# -----------------------------
# Configuration
# -----------------------------
OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "AddressGenerator/1.0 (+https://example.com)"
CACHE_DIR = Path(BASE_DIR) / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
OVERPASS_TIMEOUT = 60
RATE_LIMIT_SLEEP = 3.0  # seconds between Nominatim/Overpass sensitive calls (Nominatim allows 1 req/sec, using 3s for safety)
MAX_OVERPASS_RETRIES = 4
MAX_NOMINATIM_RETRIES = 3

# Logging

def setup_logging(logfile: Optional[str] = None) -> logging.Logger:
    log_dir = Path(BASE_DIR) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    if logfile is None:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        logfile = log_dir / f"address_generator_{timestamp}.log"
    else:
        logfile = Path(logfile)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        handlers=[
            logging.FileHandler(logfile, encoding='utf-8'),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# Configure Tor proxy if available
TOR_PROXY_HOST = "127.0.0.1"
TOR_PROXY_PORT = 9050
USE_TOR = os.environ.get("USE_TOR", "false").lower() == "true"

def setup_tor_proxy():
    """Setup Tor SOCKS5 proxy for requests"""
    if not TOR_AVAILABLE:
        logger.warning("⚠️  Tor support not available. Install pysocks: pip install pysocks")
        return False
    
    if not USE_TOR:
        logger.info("ℹ️  Tor not enabled. Set USE_TOR=true to enable.")
        return False
    
    try:
        # Test if Tor is running
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(2)
        result = test_socket.connect_ex((TOR_PROXY_HOST, TOR_PROXY_PORT))
        test_socket.close()
        
        if result != 0:
            logger.warning(f"⚠️  Tor proxy not available at {TOR_PROXY_HOST}:{TOR_PROXY_PORT}")
            logger.warning("   Make sure Tor is running: brew install tor && tor")
            return False
        
        logger.info(f"✅ Tor proxy enabled: {TOR_PROXY_HOST}:{TOR_PROXY_PORT}")
        return True
    except Exception as e:
        logger.warning(f"⚠️  Failed to connect to Tor proxy: {e}")
        return False

TOR_ENABLED = setup_tor_proxy()

# Requests session with retries
session = requests.Session()

# Configure Tor proxy if enabled
if TOR_ENABLED and TOR_AVAILABLE:
    session.proxies = {
        'http': f'socks5h://{TOR_PROXY_HOST}:{TOR_PROXY_PORT}',
        'https': f'socks5h://{TOR_PROXY_HOST}:{TOR_PROXY_PORT}'
    }
    logger.info("✅ Requests will be routed through Tor")

retries = Retry(
    total=5,
    backoff_factor=0.5,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=("GET", "POST"),
)
adapter = HTTPAdapter(max_retries=retries)
session.mount("https://", adapter)
session.headers.update({"User-Agent": USER_AGENT})

# -----------------------------
# Utility: caching
# -----------------------------

def cache_get(key: str) -> Optional[Any]:
    path = CACHE_DIR / f"{re.sub(r'[^A-Za-z0-9._-]', '_', key)}.json"
    if path.exists():
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
    return None


def cache_set(key: str, value: Any) -> None:
    path = CACHE_DIR / f"{re.sub(r'[^A-Za-z0-9._-]', '_', key)}.json"
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Failed to write cache {path}: {e}")

# -----------------------------
# Nominatim helpers
# -----------------------------

def nominatim_get_area_id(country: str) -> Optional[int]:
    """Return OSM relation id if available for a country via Nominatim search.
    The returned osm_id is not directly an "area" id; Overpass expects area:3600xxx for relation
    We return the relation id (osm_id) or None.
    """
    logger.info(f"🔍 Getting area ID for country '{country}' from Nominatim...")
    cache_key = f"nominatim_area_{country}"
    cached = cache_get(cache_key)
    if cached:
        logger.info(f"✅ Found cached area ID: {cached.get('osm_id')}")
        return cached.get('osm_id')

    logger.info(f"📡 Querying Nominatim API for country '{country}'...")
    params = {"q": country, "format": "json", "limit": 1, "addressdetails": 1}
    for attempt in range(1, MAX_NOMINATIM_RETRIES + 1):
        logger.info(f"   Attempt {attempt}/{MAX_NOMINATIM_RETRIES}")
        try:
            start_time = time.time()
            r = session.get(NOMINATIM_SEARCH_URL, params=params, timeout=15)
            elapsed = time.time() - start_time
            logger.info(f"   Response received in {elapsed:.2f}s, status={r.status_code}")
            
            if r.status_code == 200:
                data = r.json()
                if data:
                    osm_id = data[0].get('osm_id')
                    osm_type = data[0].get('osm_type')
                    logger.info(f"   ✅ Found: osm_id={osm_id}, osm_type={osm_type}")
                    result = {'osm_id': osm_id, 'osm_type': osm_type}
                    cache_set(cache_key, result)
                    return osm_id
                else:
                    logger.warning(f"   ⚠️  No results in response")
                return None
            else:
                logger.warning(f"   ❌ Nominatim area search failed {r.status_code}: {r.text[:200]}")
        except requests.exceptions.Timeout as e:
            logger.error(f"   ❌ Nominatim attempt {attempt} TIMEOUT: {e}")
        except Exception as e:
            logger.error(f"   ❌ Nominatim attempt {attempt} failed: {e}")
            import traceback
            logger.debug(traceback.format_exc())
        
        if attempt < MAX_NOMINATIM_RETRIES:
            wait_time = RATE_LIMIT_SLEEP * attempt
            logger.info(f"   Waiting {wait_time}s before retry...")
            time.sleep(wait_time)
    
    logger.warning(f"❌ Failed to get area ID for '{country}' after {MAX_NOMINATIM_RETRIES} attempts")
    return None

# -----------------------------
# Overpass query
# -----------------------------

def build_overpass_query(country: str, city: Optional[str] = None, limit: int = 1000) -> str:
    """Build a focused Overpass QL query to fetch nodes/ways/relations with addr tags.
    If we have a country relation id we will use it. Otherwise a name lookup is used.
    """
    logger.info(f"Building Overpass query for country='{country}', city='{city}', limit={limit}")
    
    # Try to get area id
    logger.info(f"Attempting to get area ID for country '{country}' from Nominatim...")
    area_id = nominatim_get_area_id(country)
    if area_id:
        logger.info(f"Found area ID: {area_id} for country '{country}'")
    else:
        logger.warning(f"No area ID found for country '{country}', will use name-based search")
    
    area_filter = ''
    if area_id:
        # area: relationId + 3600000000 per Overpass area id convention isn't needed in search by name
        area_filter = f"area({area_id});"
    else:
        # Fallback: search by name for admin_level=2
        area_filter = f'area["name"="{country}"]["admin_level"="2"];'

    # If city specified, prefer area by city name
    if city:
        # CRITICAL FIX: Restrict to country first, then city within country
        # This prevents matching wrong cities (e.g., Oxford Ohio instead of Oxford UK)
        logger.info(f"Building city-specific query: country='{country}', city='{city}'")
        # Use relation search to ensure we get the correct city within the country
        # First find country, then find city within that country boundary
        q = f"""[out:json][timeout:{OVERPASS_TIMEOUT}];
        (
          relation["name"="{country}"]["type"="boundary"]["admin_level"="2"];
        );
        map_to_area->.country;
        (
          relation["name"="{city}"]["place"~"^(city|town|village)$"](area.country);
        );
        map_to_area->.city;
        (
          nwr["addr:housenumber"]["addr:street"](area.city);
        );
        out center {limit};"""
        logger.info(f"Overpass query (first 200 chars):\n{q[:200]}...")
        return q

    # Country-wide query (may be large)
    logger.info(f"Building country-wide query (no city specified)")
    q = f"""[out:json][timeout:{OVERPASS_TIMEOUT}];
        {area_filter}
        (
          nwr["addr:housenumber"]["addr:street"](area);
        );
        out center {limit};"""
    logger.debug(f"Overpass query:\n{q}")
    return q


def query_overpass(country: str, city: Optional[str] = None, limit: int = 1000) -> List[Dict[str, Any]]:
    cache_key = f"overpass_{country}_{city or 'country'}_{limit}"
    logger.info(f"Checking cache for key: {cache_key}")
    cached = cache_get(cache_key)
    if cached:
        logger.info(f"✅ Using cached Overpass results for {country}{' / '+city if city else ''} ({len(cached)} elements)")
        return cached
    else:
        logger.info(f"❌ No cache found, will query Overpass API")

    q = build_overpass_query(country, city, limit)
    logger.info(f"📡 Querying Overpass API for {country}{' / '+city if city else ''} (limit={limit})")
    logger.info(f"   URL: {OVERPASS_API_URL}")
    logger.info(f"   Query length: {len(q)} characters")

    for attempt in range(1, MAX_OVERPASS_RETRIES + 1):
        logger.info(f"   Attempt {attempt}/{MAX_OVERPASS_RETRIES}")
        try:
            start_time = time.time()
            r = session.post(OVERPASS_API_URL, data=q.encode('utf-8'), timeout=OVERPASS_TIMEOUT)
            elapsed = time.time() - start_time
            logger.info(f"   Response received in {elapsed:.2f}s, status={r.status_code}")
            
            if r.status_code == 200:
                logger.info("   Parsing JSON response...")
                data = r.json()
                elements = data.get('elements', [])
                logger.info(f"   ✅ Overpass returned {len(elements)} elements")
                
                # Log some details about the elements
                if elements:
                    sample = elements[0]
                    logger.info(f"   Sample element: type={sample.get('type')}, id={sample.get('id')}, tags={list(sample.get('tags', {}).keys())[:5]}")
                
                cache_set(cache_key, elements)
                logger.info(f"   Cached results for future use")
                return elements
            else:
                logger.warning(f"   ❌ Overpass returned {r.status_code}")
                logger.warning(f"   Response text (first 500 chars): {r.text[:500]}")
        except requests.exceptions.Timeout as e:
            logger.error(f"   ❌ Overpass attempt {attempt} TIMEOUT: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"   ❌ Overpass attempt {attempt} REQUEST ERROR: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"   ❌ Overpass attempt {attempt} JSON DECODE ERROR: {e}")
            logger.error(f"   Response text (first 500 chars): {r.text[:500] if 'r' in locals() else 'N/A'}")
        except Exception as e:
            logger.error(f"   ❌ Overpass attempt {attempt} UNEXPECTED ERROR: {e}")
            import traceback
            logger.debug(traceback.format_exc())
        
        if attempt < MAX_OVERPASS_RETRIES:
            wait_time = RATE_LIMIT_SLEEP * attempt
            logger.info(f"   Waiting {wait_time}s before retry...")
            time.sleep(wait_time)
    
    logger.error(f"❌ Overpass query failed after {MAX_OVERPASS_RETRIES} retries")
    return []

# -----------------------------
# Parse Overpass elements into address dicts
# -----------------------------

def extract_addresses_from_elements(elements: List[Dict[str, Any]], country: str) -> List[Dict[str, Any]]:
    logger.info(f"Extracting addresses from {len(elements)} elements for country '{country}'")
    addresses: List[Dict[str, Any]] = []
    skipped_no_tags = 0
    skipped_no_housenumber = 0
    skipped_no_street = 0
    
    for idx, el in enumerate(elements):
        tags = el.get('tags') or {}
        if not tags:
            skipped_no_tags += 1
            continue
            
        housenumber = tags.get('addr:housenumber')
        street = tags.get('addr:street')
        if not housenumber:
            skipped_no_housenumber += 1
            continue
        if not street:
            skipped_no_street += 1
            continue
            
        city = tags.get('addr:city') or tags.get('addr:place') or tags.get('addr:suburb')
        postcode = tags.get('addr:postcode')
        country_tag = tags.get('addr:country') or country
        lat = el.get('lat') or (el.get('center') or {}).get('lat')
        lon = el.get('lon') or (el.get('center') or {}).get('lon')
        
        # Basic country heuristics - keep element if country matches or missing
        if country_tag and country_tag.strip().lower() not in (country.lower(), country.lower()):
            # allow missing country or minor differences
            pass
        
        address = {
            'housenumber': housenumber,
            'street': street,
            'city': city,
            'postcode': postcode,
            'country': country_tag,
            'lat': lat,
            'lon': lon,
            'osm_id': el.get('id'),
            'osm_type': el.get('type')
        }
        addresses.append(address)
        
        # Log first few addresses for debugging
        if idx < 3:
            logger.debug(f"   Sample address {idx+1}: {housenumber} {street}, {city}, {postcode}, {country_tag}")
    
    logger.info(f"✅ Extracted {len(addresses)} addresses")
    logger.info(f"   Skipped: {skipped_no_tags} (no tags), {skipped_no_housenumber} (no housenumber), {skipped_no_street} (no street)")
    return addresses

# -----------------------------
# Assemble canonical address string
# -----------------------------

def assemble_address(addr: Dict[str, Any]) -> Optional[str]:
    parts = []
    if addr.get('housenumber') and addr.get('street'):
        parts.append(f"{addr['housenumber']} {addr['street']}")
    else:
        return None
    if addr.get('city'):
        parts.append(addr['city'])
    if addr.get('postcode'):
        parts.append(addr['postcode'])
    if addr.get('country'):
        parts.append(addr['country'])
    return ", ".join(parts)

# -----------------------------
# Validation pipeline (single address)
# -----------------------------

def validate_single_address(address: str, country_seed: str) -> Tuple[bool, float, Dict[str, Any]]:
    details = {
        'address': address,
        'heuristic': False,
        'region': False,
        'api_score': 0.0,
        'api_area': None,
        'api_result': None,
    }

    # 1. Heuristic
    logger.debug(f"      Step 1: Heuristic check...")
    try:
        looks = looks_like_address(address)
    except Exception as e:
        logger.warning(f"      ❌ looks_like_address failed for '{address}': {e}")
        looks = False
    details['heuristic'] = looks
    if not looks:
        logger.debug(f"      ❌ FAILED: Address format invalid (heuristic check)")
        return False, 0.0, details
    logger.debug(f"      ✅ PASSED: Address format valid")

    # 2. Region
    logger.debug(f"      Step 2: Region validation...")
    try:
        region_ok = validate_address_region(address, country_seed)
    except Exception as e:
        logger.warning(f"      ❌ validate_address_region error for '{address}': {e}")
        region_ok = False
    details['region'] = region_ok
    if not region_ok:
        logger.debug(f"      ❌ FAILED: Region mismatch (not in {country_seed})")
        return False, 0.0, details
    logger.debug(f"      ✅ PASSED: Region matches {country_seed}")

    # 3. Nominatim API check (direct call, not through rewards.py)
    logger.debug(f"      Step 3: Nominatim API check (direct call)...")
    api_start = time.time()
    
    try:
        # Direct Nominatim API call with longer timeout (10 seconds)
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": address, "format": "json"}
        user_agent = "AddressGenerator/1.0 (+https://example.com)"
        
        logger.debug(f"         Calling Nominatim API (timeout=10s)...")
        response = session.get(url, params=params, headers={"User-Agent": user_agent}, timeout=10)
        api_elapsed = time.time() - api_start
        
        if response.status_code != 200:
            logger.warning(f"      ❌ Nominatim returned status {response.status_code}")
            details['api_result'] = 'FAILED'
            return False, 0.0, details
        
        results = response.json()
        
        # Check if we have any results
        if len(results) == 0:
            logger.debug(f"      ❌ FAILED: No results found in Nominatim (took {api_elapsed:.2f}s)")
            details['api_result'] = 'FAILED'
            return False, 0.0, details
        
        # Extract numbers from the original address for matching
        original_numbers = set(re.findall(r"[0-9]+", address.lower()))
        
        # Filter results based on place_rank, name check, and numbers check (same logic as rewards.py)
        filtered_results = []
        for result in results:
            # Check place_rank is 20 or above
            place_rank = result.get('place_rank', 0)
            if place_rank < 20:
                continue
            
            # Check that 'name' field exists and is in the original address
            name = result.get('name', '')
            if name:
                if name.lower() not in address.lower():
                    continue
            
            # Check that numbers in display_name match numbers from the original address
            display_name = result.get('display_name', '')
            if display_name:
                display_numbers = set(re.findall(r"[0-9]+", display_name.lower()))
                if original_numbers:
                    if display_numbers and not display_numbers.issubset(original_numbers):
                        continue
            
            filtered_results.append(result)
        
        # If no results pass the filters, return 0.0
        if len(filtered_results) == 0:
            logger.debug(f"      ❌ FAILED: No results passed filters (took {api_elapsed:.2f}s)")
            details['api_result'] = 'FAILED'
            return False, 0.0, details
        
        # Calculate bounding box areas for all results
        areas_data = compute_bounding_box_areas_meters(results)
        
        if len(areas_data) == 0:
            logger.debug(f"      ❌ FAILED: No bounding box areas calculated (took {api_elapsed:.2f}s)")
            details['api_result'] = 'FAILED'
            return False, 0.0, details
        
        # Extract areas
        areas = [item["area_m2"] for item in areas_data]
        
        # Use the smallest area for scoring
        min_area = min(areas)
        
        # Score based on smallest area (same logic as rewards.py)
        if min_area < 100:
            score = 1.0
        elif min_area < 1000:
            score = 0.9
        elif min_area < 10000:
            score = 0.8
        elif min_area < 100000:
            score = 0.5
        else:
            score = 0.3
        
        details['api_result'] = 'SUCCESS'
        details['api_score'] = score
        details['api_area'] = min_area
        is_perfect = score >= 0.99
        
        if is_perfect:
            logger.info(f"      ✅ PASSED: Score={score:.4f}, Area={min_area:.2f} m² (took {api_elapsed:.2f}s)")
        else:
            logger.debug(f"      ❌ FAILED: Score={score:.4f} (took {api_elapsed:.2f}s)")
            logger.debug(f"         Area: {min_area:.2f} m² (needs < 100 m² for perfect score)")
        
        return is_perfect, score, details
        
    except requests.exceptions.Timeout:
        details['api_result'] = 'TIMEOUT'
        api_elapsed = time.time() - api_start
        logger.warning(f"      ⏱️  TIMEOUT: API call timed out after 10s (took {api_elapsed:.2f}s)")
        return False, 0.0, details
    except Exception as e:
        details['api_result'] = 'ERROR'
        api_elapsed = time.time() - api_start
        logger.warning(f"      ❌ ERROR: Nominatim check failed: {e} (took {api_elapsed:.2f}s)")
        import traceback
        logger.debug(traceback.format_exc())
        return False, 0.0, details

# -----------------------------
# Main generation loop
# -----------------------------

def generate_perfect_addresses(country: str, city: Optional[str], target: int, output: Optional[str]) -> List[str]:
    logger.info("=" * 80)
    logger.info(f"🚀 Starting address generation")
    logger.info(f"   Country: {country}")
    logger.info(f"   City: {city if city else 'None (country-wide)'}")
    logger.info(f"   Target: {target} perfect addresses")
    logger.info("=" * 80)

    # Strategy:
    # 1) Query Overpass for addr:* elements
    # 2) Extract candidate addresses
    # 3) Validate until we find 'target' perfect addresses

    perfect_addresses: List[str] = []
    seen_addresses = set()

    # progressive query limits to increase until we find enough
    query_limits = [500, 1000, 2000]

    for limit_idx, limit in enumerate(query_limits, 1):
        logger.info("")
        logger.info(f"📊 Query limit {limit_idx}/{len(query_limits)}: limit={limit}")
        logger.info("-" * 80)
        
        elements = query_overpass(country, city, limit=limit)
        if not elements:
            logger.warning(f"⚠️  No elements from Overpass with limit={limit}; trying next limit")
            time.sleep(2)
            continue

        logger.info(f"📋 Processing {len(elements)} elements from Overpass...")
        candidates = extract_addresses_from_elements(elements, country)
        logger.info(f"✅ Extracted {len(candidates)} candidate addresses from Overpass (limit={limit})")

        if not candidates:
            logger.warning(f"⚠️  No valid candidate addresses extracted; trying next limit")
            time.sleep(2)
            continue

        # Randomize to avoid picking always the same cluster
        logger.info("🔀 Randomizing candidate order...")
        random.shuffle(candidates)

        logger.info(f"🔍 Starting validation of {len(candidates)} candidates...")
        logger.info(f"   Rate limit: {RATE_LIMIT_SLEEP}s between Nominatim calls")
        logger.info(f"   Estimated time: ~{len(candidates) * RATE_LIMIT_SLEEP / 60:.1f} minutes")
        
        validated_count = 0
        for cand_idx, cand in enumerate(candidates, 1):
            addr_str = assemble_address(cand)
            if not addr_str:
                logger.debug(f"   [{cand_idx}/{len(candidates)}] Skipped: Could not assemble address from {cand}")
                continue
            if addr_str in seen_addresses:
                logger.debug(f"   [{cand_idx}/{len(candidates)}] Skipped: Duplicate address")
                continue
            seen_addresses.add(addr_str)

            logger.info(f"   [{cand_idx}/{len(candidates)}] Validating: {addr_str[:70]}...")
            validated_count += 1
            
            is_perfect, score, details = validate_single_address(addr_str, country)
            
            if is_perfect:
                perfect_addresses.append(addr_str)
                logger.info("")
                logger.info("   " + "="*76)
                logger.info(f"   ✅ PERFECT ADDRESS FOUND!")
                logger.info(f"   " + "="*76)
                logger.info(f"      Address: {addr_str}")
                logger.info(f"      Score: {score:.4f}")
                logger.info(f"      Area: {details.get('api_area', 'N/A')} m²")
                logger.info(f"      Progress: {len(perfect_addresses)}/{target} perfect addresses")
                logger.info("")
                
                if len(perfect_addresses) >= target:
                    logger.info("")
                    logger.info("🎉 TARGET REACHED!")
                    break
            else:
                # Log failure reasons at INFO level so user can see progress
                failure_reasons = []
                if not details.get('heuristic', False):
                    failure_reasons.append("heuristic")
                if not details.get('region', False):
                    failure_reasons.append("region")
                if details.get('api_result') == 'TIMEOUT':
                    failure_reasons.append("timeout")
                elif details.get('api_result') == 'FAILED':
                    failure_reasons.append("not found in OSM")
                elif details.get('api_score', 0) < 0.99:
                    failure_reasons.append(f"score too low ({details.get('api_score', 0):.4f})")
                
                logger.info(f"      ❌ Not perfect: {', '.join(failure_reasons) if failure_reasons else 'unknown reason'}")
                
                # Show progress every 10 addresses
                if validated_count % 10 == 0:
                    logger.info(f"      Progress: {validated_count}/{len(candidates)} validated, {len(perfect_addresses)}/{target} perfect")

            # polite rate-limiting between Nominatim calls (3 seconds = 1 call/sec with safety margin)
            # Nominatim allows 1 request per second, using 3s to avoid 429 errors
            if cand_idx < len(candidates) and len(perfect_addresses) < target:
                time.sleep(RATE_LIMIT_SLEEP)
                
                # If we got a 429 error or timeout, add extra delay
                if details.get('api_result') in ('TIMEOUT', 'ERROR'):
                    logger.warning(f"      Adding extra 2s delay after error to reduce server load...")
                    time.sleep(2.0)

        logger.info("")
        logger.info(f"📊 Progress after limit {limit}:")
        logger.info(f"   Validated: {validated_count} addresses")
        logger.info(f"   Perfect: {len(perfect_addresses)}/{target}")
        
        if len(perfect_addresses) >= target:
            logger.info("✅ Target reached, stopping generation")
            break
        else:
            logger.info(f"⏳ Target not reached, trying next limit...")
            time.sleep(3)

    if output:
        output_data = {
            'country': country,
            'city': city,
            'perfect_addresses': perfect_addresses,
            'count': len(perfect_addresses),
            'timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved results to {output}")

    return perfect_addresses

# -----------------------------
# Batch test with rewards.py
# -----------------------------

def batch_test_with_rewards(addresses: List[str], country: str) -> Dict[str, Any]:
    variations = {'Generator': [["Generator", "1990-01-01", a] for a in addresses]}
    result = _grade_address_variations(
        variations=variations,
        seed_addresses=[country],
        miner_metrics={},
        validator_uid=101,
        miner_uid=501,
    )
    return result

# -----------------------------
# CLI
# -----------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate perfect addresses using Overpass + Nominatim + rewards.py validator")
    p.add_argument('--country', required=True, help='Country name (exact)')
    p.add_argument('--city', default=None, help='Optional city name to narrow search')
    p.add_argument('--target', type=int, default=15, help='Number of perfect addresses to find')
    p.add_argument('--output', default=None, help='Path to output JSON file')
    return p.parse_args()


def main() -> None:
    args = parse_args()
    start = time.time()
    results = generate_perfect_addresses(args.country, args.city, args.target, args.output)
    elapsed = time.time() - start
    logger.info(f"Generation finished in {elapsed:.1f}s; found {len(results)} perfect addresses")

    if results:
        logger.info("Running batch test with rewards.py to compute final validator score")
        score = batch_test_with_rewards(results, args.country)
        logger.info(f"Validator overall_score={score.get('overall_score')}")
    else:
        logger.error("No perfect addresses found; cannot run final validator")


if __name__ == '__main__':
    main()

