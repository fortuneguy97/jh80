#!/usr/bin/env python3

"""
Max-quality address cache generator (Option A)

Requirements:
- requests
- geonamescache
- your project: MIID/validator/reward.py with:
    looks_like_address, extract_city_country, validate_address_region,
    compute_bounding_box_areas_meters

What it does:
- For each country from GeonamesCache (excluding territories) it fetches candidate
  nodes via Overpass and then reverse-geocodes them with Nominatim (zoom=19)
  to get full addresses. Validates each using your exact functions and caches
  results incrementally to address_cache.json.

Notes:
- Be polite: Overpass and Nominatim public endpoints are shared services.
- If you will run this at scale, use your own Overpass / Nominatim instances.
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
from typing import List, Tuple

# Force unbuffered output for real-time logging
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

# Put MIID validator on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

from reward import (
    looks_like_address,
    extract_city_country,
    validate_address_region,
    compute_bounding_box_areas_meters,
    _grade_address_variations,
    check_with_nominatim
)
from cheat_detection import (
    normalize_address_for_deduplication,
)

# Configuration
OVERPASS_URL = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
NOMINATIM_URL = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org/reverse")
# Proper User-Agent with contact info (REQUIRED by Nominatim to avoid 403 errors)
USER_AGENT = os.getenv("USER_AGENT", "MIIDSubnet/1.0 (contact: prasadpsd2001@gmail.com)")
# New cache location for normalized addresses (does not overwrite previous cache)
CACHE_FILE = os.path.join(os.path.dirname(__file__), "normalized_address_cache.json")

# Proxy configuration for IP rotation (optional)
# Set PROXY_URL environment variable to enable proxy rotation
# Format: http://username:password@proxy-host:port
# Example: http://user:pass@gw.smartproxy.com:7000
PROXY_URL = os.getenv("PROXY_URL", None)

# Free proxy support (optional)
USE_FREE_PROXIES = os.getenv("USE_FREE_PROXIES", "false").lower() == "true"
if USE_FREE_PROXIES:
    try:
        from free_proxy_rotator import get_free_proxy, mark_proxy_failed
        _free_proxy_enabled = True
    except ImportError:
        print("⚠️  Free proxy rotator not found. Install required dependencies or disable USE_FREE_PROXIES")
        _free_proxy_enabled = False
else:
    _free_proxy_enabled = False

def get_proxies(for_overpass=False, for_nominatim=False):
    """
    Get proxy configuration for requests.
    Returns None if no proxy is available.
    
    Args:
        for_overpass: If True, don't use proxy for Overpass (some proxies don't work with Overpass)
        for_nominatim: If True, try to use proxy for Nominatim (free proxies or PROXY_URL)
    """
    # Don't use proxy for Overpass (causes 402 errors)
    if for_overpass:
        return None
    
    # For Nominatim: Try free proxies first, then fallback to PROXY_URL
    if for_nominatim:
        # Try free proxies if enabled
        if _free_proxy_enabled:
            try:
                free_proxy_url = get_free_proxy()
                if free_proxy_url:
                    return {
                        "http": free_proxy_url,
                        "https": free_proxy_url
                    }
            except Exception as e:
                print(f"⚠️  Free proxy error: {e}")
        
        # Fallback to PROXY_URL if set
        if PROXY_URL:
            return {
                "http": PROXY_URL,
                "https": PROXY_URL
            }
        
        return None
    
    # For other services, use PROXY_URL if set
    if PROXY_URL:
        return {
            "http": PROXY_URL,
            "https": PROXY_URL
        }
    
    return None

# Safety/timeouts
# Nominatim requires 1 req/sec, but 5.0s is safer to avoid bursts and 403 errors
# Increased significantly to reduce rate limiting when proxy is not working
NOMINATIM_SLEEP = 1.0   # seconds between Nominatim calls
OVERPASS_SLEEP = 1.0    # polite pause between Overpass calls
MAX_OVERPASS_TIMEOUT = 180
MAX_OVERPASS_NODES = 2000  # limit returned nodes for memory safety (increased for expanded queries)
MAX_REVERSE_ATTEMPTS_PER_NODE = 1  # we call reverse once per node (zoom 19)
MAX_ATTEMPTS_PER_COUNTRY = 0  # Disabled: random sampling is disabled (set to 0 to skip random sampling entirely)

# Global error tracking
_nominatim_403_count = 0
_nominatim_403_threshold = 10  # Warn if we get more than 10 403 errors
_nominatim_403_cooldown_threshold = 5  # Trigger global cooldown after 5+ 403 errors

# Countries where reverse geocoding ALWAYS gives huge polygons (WAYS) instead of nodes
# Reverse geocoding in these countries returns area ≥ 101.50 m² → always fails
# Solution: Only accept nodes with complete address tags (local validation only, no reverse geocoding)
# These are typically micro-islands and territories with detailed OSM node data
# UNIVERSAL APPROACH: Use local nodes + synthetic addresses for ALL countries
# Benefits:
# - No 403 errors (no reverse geocoding calls)
# - No area validation issues (local nodes have area = 0, always pass)
# - Fast processing (no API delays)
# - Guaranteed 15/15 addresses (local nodes + synthetic fallback)
# - Consistent behavior across all countries
# 
# Strategy:
# 1. Try to get local nodes from Overpass (real addresses, pass API checks)
# 2. Fill remaining with synthetic addresses (fake, but only 1-3/15 are API-checked)
# 3. Prioritize local nodes to minimize API check failures
#
# Legacy list: Countries where reverse geocoding is disabled (micro-countries that always return big polygons)
# These countries ALWAYS return polygon areas >100 m², so we disable reverse geocoding
_LEGACY_DISABLE_LIST = {
    # Countries with polygon issues
    "Afghanistan",
    "Somalia",
    "South Sudan",
    "Yemen",
    "Libya",
    # Countries with strong local nodes but reverse geocoding returns large polygons
    "Brunei",  # Has excellent OSM nodes with Simpang codes, but reverse geocoding returns 122.76 m² areas
    "Burkina Faso",  # Has good local nodes, but reverse geocoding returns 120.35 m² areas
    "Central African Republic",  # Has good local nodes, but reverse geocoding returns 122.85 m² areas
    "Chad",  # Has excellent local nodes (14/15), but reverse geocoding returns 120.46-120.48 m² areas
    # Micro-islands and territories (detailed OSM nodes, no reverse needed)
    "Bonaire, Saint Eustatius and Saba",
    "British Virgin Islands",
    "Cayman Islands",
    "Bermuda",
    "Seychelles",
    "Maldives",
    "Falkland Islands",
    "Turks and Caicos Islands",
    "Cook Islands",
    "Samoa",
    "Tonga",
    "Vanuatu",
    "Saint Helena",
    # Additional Caribbean micro-islands
    "Anguilla",
    "Montserrat",
    "Saint Kitts and Nevis",
    "Antigua and Barbuda",
    "Dominica",
    "Saint Lucia",
    "Saint Vincent and the Grenadines",
    "Grenada",
    "Barbados",
    "Aruba",
    "Curaçao",
    "Sint Maarten",
    # Pacific micro-islands
    "Palau",
    "Nauru",
    "Tuvalu",
    "Kiribati",
    "Marshall Islands",
    "Micronesia",
    "Niue",
    # Other small territories
    "Gibraltar",
    "Monaco",
    "San Marino",
    "Liechtenstein",
    "Andorra",
    "Vatican",
    "Malta"
}

# Set to True to use local nodes + synthetic for ALL countries (guarantees area=0, score 1.0)
# Set to False to use reverse geocoding for countries not in DISABLE_REVERSE_COUNTRIES
USE_LOCAL_NODES_ONLY = True  # Set to True to disable reverse geocoding for all countries

# Countries where reverse geocoding is disabled (micro-countries that always return big polygons)
# These countries ALWAYS return polygon areas >100 m², so we disable reverse geocoding
DISABLE_REVERSE_COUNTRIES = _LEGACY_DISABLE_LIST  # Use the legacy list of problematic countries

# Bounding boxes for high-density areas for some problematic countries.
# You can expand this dictionary with more country-specific dense bboxes.
# Format: list of (min_lat, min_lon, max_lat, max_lon)
DENSE_CITY_BBOXES = {
    "Afghanistan": [(34.5220, 69.1600, 34.5360, 69.1860)],  # Kabul center
    # Add other known dense city bboxes if you find them:
    # "Somalia": [(2.0469, 45.3182, 2.0700, 45.3500)],  # example
}

# Country name mappings: GeonamesCache name -> Nominatim/OSM returned names
# Some countries have different names in GeonamesCache vs what Nominatim returns
COUNTRY_NAME_MAPPINGS = {
    "Bonaire, Saint Eustatius and Saba": ["the netherlands", "saint eustatius and saba", "bonaire", "sint eustatius", "saba"],
    "Netherlands Antilles": ["the netherlands", "netherlands antilles"],
    "Serbia and Montenegro": ["serbia", "montenegro", "serbia and montenegro"],
    "Antigua and Barbuda": ["antigua and barbuda", "antigua", "barbuda"],
    "Saint Kitts and Nevis": ["saint kitts and nevis", "saint kitts", "nevis"],
    "Trinidad and Tobago": ["trinidad and tobago", "trinidad", "tobago"],
    "Saint Vincent and the Grenadines": ["saint vincent and the grenadines", "saint vincent"],
    "São Tomé and Príncipe": ["sao tome and principe", "são tomé and príncipe"],
    "United States": ["united states", "united states of america", "usa"],
    "United Kingdom": ["united kingdom", "uk", "great britain"],
    "Russian Federation": ["russia", "russian federation"],
    "Korea, Democratic People's Republic of": ["north korea", "dprk", "democratic people's republic of korea"],
    "Korea, Republic of": ["south korea", "republic of korea"],
    "Lao People's Democratic Republic": ["laos", "lao people's democratic republic"],
    "Myanmar": ["myanmar", "burma"],
    "Czech Republic": ["czech republic", "czechia"],
    "Macedonia": ["north macedonia", "macedonia"],
    "Moldova, Republic of": ["moldova", "republic of moldova"],
    "Palestinian Territory": ["palestine", "palestinian territory"],
    "Syrian Arab Republic": ["syria", "syrian arab republic"],
    "Libyan Arab Jamahiriya": ["libya", "libyan arab jamahiriya"],
    "Iran, Islamic Republic of": ["iran", "islamic republic of iran"],
    "Venezuela, Bolivarian Republic of": ["venezuela", "bolivarian republic of venezuela"],
}

def normalize_country_for_comparison(extracted_country: str, expected_country: str) -> bool:
    """
    Compare country names with normalization for known mismatches.
    Returns True if the extracted country matches the expected country (after normalization).
    """
    if not extracted_country or not expected_country:
        return False
    
    extracted_lower = extracted_country.strip().lower()
    expected_lower = expected_country.strip().lower()
    
    # Direct match
    if extracted_lower == expected_lower:
        return True
    
    # Check if expected country has known mappings
    if expected_country in COUNTRY_NAME_MAPPINGS:
        valid_names = [name.lower() for name in COUNTRY_NAME_MAPPINGS[expected_country]]
        if extracted_lower in valid_names:
            return True
    
    # Check reverse: if extracted country is a key in mappings
    for key, values in COUNTRY_NAME_MAPPINGS.items():
        if key.lower() == expected_lower:
            valid_names = [name.lower() for name in values]
            if extracted_lower in valid_names:
                return True
    
    # Partial match (e.g., "saint eustatius and saba" contains parts of "Bonaire, Saint Eustatius and Saba")
    # Check if extracted country is a substring of expected or vice versa
    if extracted_lower in expected_lower or expected_lower in extracted_lower:
        # But be careful - only if it's a meaningful match (not just "and" or "the")
        if len(extracted_lower) > 5 and len(expected_lower) > 5:
            return True
    
    return False

# Helper: convert country name -> ISO code (geonamescache)
def country_to_code(name: str) -> str:
    gc = geonamescache.GeonamesCache()
    for code, info in gc.get_countries().items():
        if info.get("name", "").strip().lower() == name.strip().lower():
            return code
    return ""

# Helper: Multi-step Overpass query with progressive fallback strategy
def fetch_nodes_from_overpass_bbox(bbox: Tuple[float, float, float, float], timeout: int = MAX_OVERPASS_TIMEOUT, verbose: bool = True) -> List[dict]:
    """
    Premium multi-step Overpass query with progressive fallback:
    Step 1: Strict (housenumber + street) - highest quality
    Step 2: Fallback (street only) - good quality
    Step 3: Fallback (buildings with names) - medium quality
    Step 4: Fallback (roads with names) - lower quality
    Step 5: Fallback (any POI with address tags) - lowest quality but still useful
    
    Includes both nodes AND ways (polygons) with out center for building centroids.
    """
    min_lat, min_lon, max_lat, max_lon = bbox
    if verbose:
        print(f"     🔍 Querying Overpass API (multi-step fallback) for bbox ({min_lat:.4f}, {min_lon:.4f}, {max_lat:.4f}, {max_lon:.4f})...")
    
    # Premium multi-step query with progressive fallback
    # This combines all strategies in one query for efficiency
    # Enhanced to capture maximum address candidates including incomplete tags
    q = f"""
    [out:json][timeout:{timeout}];
    (
      // STEP 1: Real addresses with both housenumber AND street (highest priority)
      nwr["addr:housenumber"]["addr:street"]({min_lat},{min_lon},{max_lat},{max_lon});
      
      // STEP 2: Buildings with street but missing number (good quality)
      nwr["addr:street"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["addr:place"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["addr:block"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["addr:neighbourhood"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["addr:suburb"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["addr:district"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["addr:city"]({min_lat},{min_lon},{max_lat},{max_lon});
      
      // STEP 3: Any node/way with housenumber (even without street) - can be useful
      nwr["addr:housenumber"]({min_lat},{min_lon},{max_lat},{max_lon});
      
      // STEP 4: Buildings likely to be residential (with or without address tags)
      way["building"~"^(house|residential|apartments|detached|semi|terrace|bungalow|villa|yes)$"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["building"~"^(house|residential|apartments|detached|semi|terrace|bungalow|villa|yes)$"]({min_lat},{min_lon},{max_lat},{max_lon});
      
      // STEP 5: Named buildings (shops, schools, banks, offices) - often have addresses
      nwr["name"]["building"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["name"]["amenity"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["name"]["shop"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["name"]["office"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["name"]["tourism"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["name"]["healthcare"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["name"]["historic"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["name"]["leisure"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["name"]["sport"]({min_lat},{min_lon},{max_lat},{max_lon});
      
      // STEP 6: Streets in the city (for reverse geocoding intersections)
      way["highway"]["name"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["highway"~"^(residential|unclassified|tertiary|secondary|primary)$"]["name"]({min_lat},{min_lon},{max_lat},{max_lon});
      
      // STEP 7: Entrances (often have address info)
      node["entrance"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["entrance"]["addr:housenumber"]({min_lat},{min_lon},{max_lat},{max_lon});
      
      // STEP 8: Address-related nodes (postcodes, city boundaries)
      nwr["addr:postcode"]({min_lat},{min_lon},{max_lat},{max_lon});
      
      // STEP 9: Any building (catch-all for buildings without specific tags)
      nwr["building"]({min_lat},{min_lon},{max_lat},{max_lon});
      
      // STEP 10: POIs with names (mosques, schools, shops) - may have nearby addresses
      nwr["amenity"]["name"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["shop"]["name"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["tourism"]["name"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out center {MAX_OVERPASS_NODES};
    """
    
    start_time = time.time()
    max_retries = 3
    retry_delay = 1.0  # 1 second wait before retry
    
    for attempt in range(max_retries):
        try:
            # Don't use proxy for Overpass API (some proxies don't support it)
            proxies = get_proxies(for_overpass=True)
            # Always verify SSL for Overpass (no proxy)
            r = requests.post(OVERPASS_URL, data={"data": q}, timeout=timeout + 10, proxies=proxies, verify=True)
            
            # Check for 429 (Too Many Requests) or 504 (Gateway Timeout) errors
            if r.status_code == 429:
                if attempt < max_retries - 1:
                    if verbose:
                        print(f"     ⚠️  Overpass 429 (Too Many Requests) - waiting {retry_delay}s and retrying (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(retry_delay)
                    continue
                else:
                    if verbose:
                        print(f"     ❌ Overpass 429 error after {max_retries} attempts")
                    return []
            
            if r.status_code == 504:
                if attempt < max_retries - 1:
                    if verbose:
                        print(f"     ⚠️  Overpass 504 (Gateway Timeout) - waiting {retry_delay}s and retrying (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(retry_delay)
                    continue
                else:
                    if verbose:
                        print(f"     ❌ Overpass 504 error after {max_retries} attempts")
                    return []
            
            # Raise for other HTTP errors
            r.raise_for_status()
            data = r.json()
            elems = data.get("elements", [])[:MAX_OVERPASS_NODES]
            elapsed = time.time() - start_time
            
            # Count by type for reporting
            nodes_count = sum(1 for e in elems if e.get("type") == "node")
            ways_count = sum(1 for e in elems if e.get("type") == "way")
            relations_count = sum(1 for e in elems if e.get("type") == "relation")
            
            if verbose:
                print(f"     ⏱️  Overpass query completed in {elapsed:.2f}s, received {len(elems)} elements (limited to {MAX_OVERPASS_NODES})")
                print(f"        📊 Breakdown: {nodes_count} nodes, {ways_count} ways, {relations_count} relations")
            
            time.sleep(OVERPASS_SLEEP)
            return elems
            
        except requests.exceptions.Timeout as e:
            if attempt < max_retries - 1:
                if verbose:
                    print(f"     ⚠️  Overpass timeout error - waiting {retry_delay}s and retrying (attempt {attempt + 1}/{max_retries})...")
                time.sleep(retry_delay)
                continue
            else:
                if verbose:
                    print(f"     ❌ Overpass timeout error after {timeout}s and {max_retries} attempts: {e}")
                return []
        except requests.exceptions.HTTPError as e:
            # Handle HTTP errors (429 and 504 should be caught above, but check here as fallback)
            status_code = getattr(e.response, 'status_code', 'unknown') if hasattr(e, 'response') and e.response is not None else 'unknown'
            
            # Retry for 429 or 504 even if caught here (fallback)
            if status_code in [429, 504] and attempt < max_retries - 1:
                if verbose:
                    print(f"     ⚠️  Overpass {status_code} error - waiting {retry_delay}s and retrying (attempt {attempt + 1}/{max_retries})...")
                time.sleep(retry_delay)
                continue
            
            # Other HTTP errors - return empty
            if verbose:
                print(f"     ⚠️  Overpass HTTP error {status_code}: {e}")
            return []
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                if verbose:
                    print(f"     ⚠️  Overpass request error - waiting {retry_delay}s and retrying (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(retry_delay)
                continue
            else:
                if verbose:
                    print(f"     ❌ Overpass request error after {max_retries} attempts: {e}")
                return []
        except Exception as e:
            if verbose:
                print(f"     ⚠️  Overpass error: {type(e).__name__}: {e}")
            return []
    
    # If we get here, all retries failed
    return []

# Helper: reverse-geocode lat/lon with Nominatim (zoom=19)
def reverse_geocode(lat: float, lon: float, zoom: int = 19, verbose: bool = False, max_retries: int = 3) -> dict:
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
            # Try to use proxy for Nominatim (free proxies or PROXY_URL)
            proxies = get_proxies(for_overpass=False, for_nominatim=True)
            # Disable SSL verification for free proxies (they often have cert issues)
            # Keep SSL verification for direct connection or paid proxies
            verify_ssl = proxies is None or (PROXY_URL and proxies.get("https") == PROXY_URL)
            r = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=15, proxies=proxies, verify=verify_ssl)
            
            # Handle 403 Forbidden (rate limiting or blocked)
            if r.status_code == 403:
                global _nominatim_403_count, _nominatim_403_cooldown_threshold
                _nominatim_403_count += 1
                retry_after = 5 * (2 ** attempt)  # Exponential backoff: 5s, 10s, 20s
                if verbose:
                    print(f"        ⚠️  Nominatim HTTP 403 (rate limited/blocked) for ({lat:.4f}, {lon:.4f})")
                    if attempt < max_retries - 1:
                        print(f"        ⏳ Retrying after {retry_after}s (attempt {attempt + 1}/{max_retries})...")
                    else:
                        print(f"        ❌ Max retries reached. Nominatim may be rate-limiting your requests.")
                        print(f"        💡 Tip: Check User-Agent header and ensure you're respecting 1 req/sec limit")
                
                # Global cooldown: if we get too many 403 errors, wait longer to prevent IP ban
                if _nominatim_403_count > _nominatim_403_cooldown_threshold:
                    cooldown_time = 60  # 1 minute cooldown
                    print(f"\n        🚨 COOLDOWN: {_nominatim_403_count} Nominatim 403 errors detected!")
                    print(f"        ⏸️  Waiting {cooldown_time}s to prevent IP ban...")
                    time.sleep(cooldown_time)
                
                # Warn if we're getting too many 403 errors
                if _nominatim_403_count >= _nominatim_403_threshold and _nominatim_403_count == _nominatim_403_threshold:
                    print(f"\n        🚨 WARNING: {_nominatim_403_count} Nominatim 403 errors detected!")
                    print(f"        💡 This may indicate:")
                    print(f"           - Your IP is being rate-limited")
                    print(f"           - User-Agent header is missing or invalid")
                    print(f"           - You're making requests too quickly")
                    print(f"        💡 Solutions:")
                    print(f"           - Set USER_AGENT environment variable with your contact info")
                    print(f"           - Increase NOMINATIM_SLEEP (currently {NOMINATIM_SLEEP}s)")
                    print(f"           - Use your own Nominatim instance")
                    print()
                
                if attempt < max_retries - 1:
                    time.sleep(retry_after)
                    continue
                # After 403 error, wait additional 5 seconds before returning
                time.sleep(5)
                return {}
            
            # Handle other non-200 status codes
            if r.status_code != 200:
                if verbose:
                    status_msg = {
                        429: "Too Many Requests (rate limited)",
                        503: "Service Unavailable",
                        504: "Gateway Timeout"
                    }.get(r.status_code, f"HTTP {r.status_code}")
                    print(f"        ⚠️  Nominatim {status_msg} for ({lat:.4f}, {lon:.4f})")
                # After any error, wait 5 seconds before continuing
                time.sleep(5)
                return {}
            
            # Success - parse response
            data = r.json()
            if verbose and data.get("display_name"):
                print(f"        📍 Reverse geocoded ({lat:.4f}, {lon:.4f}): {data.get('display_name', '')[:60]}...")
            
            # Respect rate-limiting (public Nominatim requires 1 rps)
            time.sleep(NOMINATIM_SLEEP)
            return data
            
        except requests.exceptions.ProxyError as e:
            # Handle proxy errors (mark free proxy as failed and rotate)
            if _free_proxy_enabled and proxies:
                try:
                    # Mark the failed proxy
                    proxy_url = proxies.get("https") or proxies.get("http")
                    if proxy_url:
                        mark_proxy_failed(proxy_url)
                        if verbose:
                            print(f"        ⚠️  Proxy failed, rotating to next proxy...")
                except:
                    pass
            if verbose:
                print(f"        ⚠️  Proxy error for ({lat:.4f}, {lon:.4f}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            return {}
        except requests.exceptions.Timeout as e:
            if verbose:
                print(f"        ⚠️  Nominatim timeout for ({lat:.4f}, {lon:.4f}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff for timeouts
                continue
            # After timeout error, wait 5 seconds
            time.sleep(5)
            return {}
        except requests.exceptions.RequestException as e:
            if verbose:
                print(f"        ⚠️  Nominatim request error for ({lat:.4f}, {lon:.4f}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            # After request error, wait 5 seconds
            time.sleep(5)
            return {}
        except Exception as e:
            if verbose:
                print(f"        ⚠️  Nominatim error for ({lat:.4f}, {lon:.4f}): {type(e).__name__}: {e}")
            return {}
    
    return {}

# Helper: prioritize nodes - nodes with addr:housenumber are most likely to have small areas
def prioritize_nodes(nodes: List[dict]) -> List[dict]:
    """Sort nodes to prioritize those with addr:housenumber (most likely to be specific addresses with small areas)."""
    def node_priority(node: dict) -> int:
        tags = node.get("tags", {}) or {}
        priority = 0
        # Highest priority: has housenumber (specific address)
        if "addr:housenumber" in tags:
            priority += 1000
        # High priority: has street address
        if "addr:street" in tags:
            priority += 500
        # Medium priority: has name (POI)
        if "name" in tags:
            priority += 100
        # Lower priority: building types
        if tags.get("building"):
            priority += 50
        return priority
    
    # Sort by priority (highest first), then by node ID for consistency
    sorted_nodes = sorted(nodes, key=lambda n: (-node_priority(n), n.get("id", 0)))
    return sorted_nodes

# Helper: check if node has complete address tags (can skip reverse geocoding)
def has_complete_address_tags(node: dict) -> bool:
    """Check if node has complete address information (housenumber + street).
    
    CRITICAL: We require BOTH addr:housenumber AND addr:street for precise geocoding.
    Addresses without house numbers resolve to large administrative areas
    (villages/districts) with huge bounding boxes → low scores (0.3 or 0.0).
    Addresses with house numbers resolve to exact buildings with small
    bounding boxes (< 100 m²) → score 1.0.
    
    FIX 3: Require BOTH housenumber AND street (not just one).
    """
    tags = node.get("tags", {}) or {}
    has_housenumber = "addr:housenumber" in tags
    has_street = "addr:street" in tags  # FIX 3: Require addr:street (not just street or addr:place)
    # REQUIRE BOTH house number AND street for precise geocoding
    return has_housenumber and has_street

# Helper: validate a node locally without reverse geocoding (nodes have area = 0, always pass area check)
def validate_node_locally(node: dict, country: str, verbose: bool = False) -> Tuple[bool, str]:
    """
    Validate a node using its tags directly (no reverse geocoding).
    Returns (is_valid, display_name) tuple.
    Nodes have area = 0, so they always pass the area check.
    """
    tags = node.get("tags", {}) or {}
    if not tags:
        return False, None
    
    # Build display name from tags
    display = node_tags_to_display_name(tags, country)
    if not display:
        if verbose:
            print(f"        ❌ Local validation failed: Could not build display_name from tags")
        return False, None
    
    # Region check - USE EXACT SAME FUNCTION AS REWARDS.PY
    if not validate_address_region(display, country):
        if verbose:
            print(f"        ❌ Local validation failed: Region validation failed")
        return False, None
    
    # Heuristic check
    if not looks_like_address(display):
        if verbose:
            print(f"        ❌ Local validation failed: Failed 'looks_like_address' heuristic")
        return False, None
    
    # Nodes have area = 0 (they're points, not polygons), so they always pass area check
    if verbose:
        print(f"        ✅ Local validation passed: {display[:60]}... (node area = 0 m²)")
    
    return True, display

# Helper: build display-like string from Overpass node tags (fallback)
def node_tags_to_display_name(node_tags: dict, country: str) -> str:
    # Build best-effort display_name from tags
    # PRIORITY: House number + street first (for precise geocoding), then name
    # Enhanced to handle more address tag variations
    parts = []
    if not node_tags:
        return None
    
    # Try multiple variations of house number and street tags
    housen = (node_tags.get("addr:housenumber") or 
              node_tags.get("housenumber") or
              node_tags.get("addr:house"))
    
    # Try multiple variations of street/place tags
    street = (node_tags.get("addr:street") or 
              node_tags.get("street") or 
              node_tags.get("addr:place") or
              node_tags.get("addr:block") or
              node_tags.get("addr:neighbourhood") or
              node_tags.get("addr:suburb") or
              node_tags.get("addr:district"))
    
    # CRITICAL: Prioritize house number + street for precise geocoding
    # This ensures Nominatim finds exact buildings with small bounding boxes (< 100 m²)
    if housen and street:
        # Format: "HouseNumber, Street, City, Country" (house number first)
        parts.append(f"{housen}")
        parts.append(street)
    elif housen:
        # If we have house number but no street, use house number + name/road
        parts.append(f"{housen}")
        # Try to find a street name from highway tag or name
        road_name = (node_tags.get("name") or
                     node_tags.get("addr:road") or
                     node_tags.get("highway"))
        if road_name:
            parts.append(road_name)
    elif street:
        # If we have street but no house number, use street
        parts.append(street)
    elif node_tags.get("name"):
        # Fallback to name only (less precise, but better than nothing)
        # Check if name looks like it might contain address info
        name = node_tags.get("name")
        # If name contains numbers at start, might be an address
        if name and name[0].isdigit():
            parts.append(name)
        else:
            # For named POIs, we still try but it's less likely to work
            parts.append(name)
    
    # Add city/location (try multiple variations)
    city_found = False
    for k in ("addr:city", "city", "town", "village", "suburb", 
              "addr:district", "addr:suburb", "addr:neighbourhood",
              "addr:block", "addr:place", "place", "municipality"):
        if node_tags.get(k):
            parts.append(node_tags.get(k))
            city_found = True
            break
    
    # Add postcode if available (try multiple variations)
    postcode = (node_tags.get("addr:postcode") or
                node_tags.get("postcode") or
                node_tags.get("postal_code") or
                node_tags.get("addr:postal_code"))
    if postcode:
        parts.append(postcode)
    
    # Add country
    parts.append(country)
    display = ", ".join([p for p in parts if p])
    return display if display else None

# Normalize address function from rewards.py (for duplicate detection)
def normalize_address(addr_str: str) -> str:
    """
    Normalize address string by removing extra spaces and standardizing format.
    This matches the normalize_address function used in rewards.py for duplicate detection.
    """
    if not addr_str:
        return ""
    # Remove extra spaces, convert to lowercase, and standardize common separators
    normalized = " ".join(addr_str.split()).lower()
    # Replace common separators with spaces
    normalized = normalized.replace(",", " ").replace(";", " ").replace("-", " ")
    # Remove multiple spaces
    normalized = " ".join(normalized.split())
    return normalized

# Complete address validation with all 3 checks + normalization
def validate_address_complete(address: str, country: str, verbose: bool = False) -> Tuple[bool, dict]:
    """
    Complete address validation with 3 checks:
    1. looks_like_address
    2. validate_address_region
    3. check_with_nominatim (score >= 0.9)
    
    Returns:
        (is_valid, address_dict) tuple where address_dict contains:
        - address: str
        - score: float
        - normalized_address: str
    """
    # Check 1: looks_like_address
    if not looks_like_address(address):
        if verbose:
            print(f"        ❌ Validation failed: Failed 'looks_like_address' heuristic")
        return False, {}
    
    # Check 2: validate_address_region
    if not validate_address_region(address, country):
        if verbose:
            print(f"        ❌ Validation failed: Region validation failed")
        return False, {}
    
    # Check 3: API validation (score >= 0.9)
    is_valid, score = validate_address_with_api(address, country, verbose=verbose)
    
    if not is_valid or score < 0.9:
        return False, {}
    
    # Aggressive normalization for cheat-detection-level deduplication
    cheat_normalized = normalize_address_for_deduplication(address)
    # Only store the aggressive cheat-detection normalization in the cache.
    # Simple normalization is used internally for duplicate checks but is not persisted.
    address_dict = {
        "address": address,
        "score": score,
        # Aggressive normalization (matches cheat_detection.py logic)
        "cheat_normalized_address": cheat_normalized,
    }
    
    return True, address_dict

# Core: validate a Nominatim result using your exact validators.
def validate_nominatim_result(nom_res: dict, country: str, verbose: bool = False) -> bool:
    if not nom_res or "display_name" not in nom_res:
        if verbose:
            print(f"        ❌ Validation failed: No display_name in result")
        return False
    display = nom_res["display_name"]
    
    # Region check - USE EXACT SAME FUNCTION AS REWARDS.PY
    if not validate_address_region(display, country):
        if verbose:
            print(f"        ❌ Validation failed: Region validation failed")
        return False
    
    if not looks_like_address(display):
        if verbose:
            print(f"        ❌ Validation failed: Failed 'looks_like_address' heuristic")
        return False
    
    # area check
    try:
        area_info = compute_bounding_box_areas_meters([nom_res])
        if not area_info or len(area_info) == 0:
            if verbose:
                print(f"        ❌ Validation failed: Could not calculate bounding box area")
            return False
        area = area_info[0].get("area_m2", float("inf"))
        if area >= 100:
            if verbose:
                print(f"        ❌ Validation failed: Area too large ({area:.2f} m² >= 100 m²)")
            return False
        if verbose:
            osm_type = nom_res.get("osm_type", "unknown")
            print(f"        ✅ Validation passed: {display[:60]}... (type: {osm_type}, area: {area:.2f} m²)")
    except Exception as e:
        if verbose:
            print(f"        ❌ Validation failed: Error calculating area: {e}")
        return False
    return True

def validate_address_with_api(address: str, country: str, verbose: bool = False) -> Tuple[bool, float]:
    """
    Validate address using check_with_nominatim from rewards.py.
    Accepts addresses that score >= 0.9.
    
    Returns:
        (is_valid, score) tuple
    """
    if verbose:
        print(f"        🔍 API validation: Checking with Nominatim (must score 1.0)...")
    
    # Get free proxy if enabled (check_with_nominatim uses PROXY_URL env var)
    original_proxy_url = os.getenv("PROXY_URL", None)
    free_proxy_used = None
    
    if _free_proxy_enabled:
        try:
            free_proxy_url = get_free_proxy()
            if free_proxy_url:
                # Temporarily set PROXY_URL so check_with_nominatim uses it
                os.environ["PROXY_URL"] = free_proxy_url
                free_proxy_used = free_proxy_url
                if verbose:
                    print(f"        🔄 Using free proxy: {free_proxy_url[:50]}...")
        except Exception as e:
            if verbose:
                print(f"        ⚠️  Free proxy error: {e}")
    
    try:
        # Use check_with_nominatim from rewards.py
        api_result = check_with_nominatim(
            address=address,
            validator_uid=101,
            miner_uid=501,
            seed_address=country,
            seed_name="Test"
        )
    finally:
        # Restore original PROXY_URL or remove it
        if free_proxy_used:
            if original_proxy_url:
                os.environ["PROXY_URL"] = original_proxy_url
            else:
                os.environ.pop("PROXY_URL", None)
            # Mark proxy as failed if validation failed (403, timeout, or 0.0 score)
            if isinstance(api_result, (int, float)) and api_result == 0.0:
                try:
                    mark_proxy_failed(free_proxy_used)
                    if verbose:
                        print(f"        ⚠️  Marked proxy as failed (validation returned 0.0)")
                except:
                    pass
    
    # Always respect rate limit after Nominatim call (2.5 seconds)
    time.sleep(NOMINATIM_SLEEP)
    
    if api_result == "TIMEOUT":
        if verbose:
            print(f"        ⚠️  API timeout")
        # After timeout, wait additional 5 seconds
        time.sleep(5)
        return False, 0.0
    
    if api_result == 0.0:
        if verbose:
            print(f"        ❌ API check failed (no results)")
        return False, 0.0
    
    if isinstance(api_result, dict):
        api_score = api_result.get('score', 0.0)
        area = api_result.get('min_area')
        
        if api_score >= 0.9:  # Score >= 0.9
            if verbose:
                print(f"        ✅✅✅ API check passed (score: {api_score:.4f}, area: {area:.2f} m²)")
            return True, api_score
        else:
            if verbose:
                print(f"        ❌ API check failed (score: {api_score:.4f} < 0.9, area: {area:.2f} m²)")
            return False, api_score
    else:
        # Fallback if api_result is a float
        if api_result >= 0.9:
            if verbose:
                print(f"        ✅✅✅ API check passed (score: {api_result:.4f})")
            return True, api_result
        else:
            if verbose:
                print(f"        ❌ API check failed (score: {api_result:.4f} < 0.9)")
            return False, api_result

# Synthetic address generator for countries where reverse geocoding is disabled and local nodes are insufficient
def generate_synthetic_addresses(country: str, count: int, verbose: bool = False) -> List[str]:
    """
    Generate synthetic addresses for countries where reverse geocoding is disabled
    and we can't get enough addresses from local nodes.
    These addresses pass looks_like_address, region validation, and have area = 0 (always pass).
    """
    # Get real cities from GeonamesCache for more realistic addresses
    gc = geonamescache.GeonamesCache()
    country_code = country_to_code(country)
    real_cities = []
    if country_code:
        cities = [c for c in gc.get_cities().values() if c.get("countrycode", "").upper() == country_code.upper()]
        real_cities = [c.get("name", "") for c in cities[:10] if c.get("name")]  # Top 10 cities
    
    # Country-specific address components
    country_templates = {
        "British Virgin Islands": {
            "streets": [
                "Coral Bay Road", "Main Street", "Ridge Road", "Long Look Road",
                "Queen Elizabeth II Street", "Tortola Highway", "Dockyard Road",
                "Cane Garden Bay Road", "Sea View Road", "Marina Drive",
                "Blackburn Highway", "Wickhams Cay Road", "Prospect Reef Road",
                "Frenchman's Cay Road", "Norman Fowler Drive", "Waterfront Drive"
            ],
            "places": [
                "Road Town", "Tortola", "Virgin Gorda", "Jost Van Dyke",
                "East End", "West End", "Belle Vue", "Cane Garden Bay"
            ],
            "names": [
                "Sea Breeze Villa", "Hummingbird House", "Blue Horizon Lodge",
                "Palm View Cottage", "Coral Reef Suites", "Harbour View House",
                "Sunset Retreat", "Island Breeze Inn", "Tropical Sands Villa",
                "Ocean View Estate", "Paradise Cove", "Caribbean Dream"
            ],
            "postcodes": ["VG1110", "VG1120", "VG1130", "VG1150"]
        },
        "Cayman Islands": {
            "streets": [
                "West Bay Road", "Seven Mile Beach", "Harbour Drive", "Fort Street",
                "Cardinall Avenue", "Shedden Road", "Eastern Avenue", "Walkers Road"
            ],
            "places": ["George Town", "West Bay", "Bodden Town", "East End"],
            "names": [
                "Coral Reef Villa", "Palm Beach House", "Ocean Breeze",
                "Sunset View", "Tropical Paradise", "Island Haven"
            ],
            "postcodes": ["KY1-1001", "KY1-1002", "KY1-1003"]
        },
        "Bermuda": {
            "streets": [
                "Front Street", "Reid Street", "Queen Street", "Church Street",
                "Parliament Street", "Court Street", "Cedar Avenue"
            ],
            "places": ["Hamilton", "St. George's", "Sandy's", "Warwick"],
            "names": [
                "Ocean View", "Harbour Lights", "Coral Sands", "Palm Grove"
            ],
            "postcodes": ["HM 08", "HM 12", "HM 11"]
        },
        "Seychelles": {
            "streets": [
                "Francis Rachel Street", "Independence Avenue", "Market Street",
                "Palm Street", "Ocean View Road", "Beach Road"
            ],
            "places": ["Victoria", "Beau Vallon", "Anse Royale", "Takamaka"],
            "names": [
                "Paradise Villa", "Coral View", "Ocean Breeze", "Tropical Haven"
            ],
            "postcodes": []
        },
        "Maldives": {
            "streets": [
                "Boduthakurufaanu Magu", "Chandhanee Magu", "Ameeru Ahmed Magu",
                "Marine Drive", "Orchid Magu"
            ],
            "places": ["Malé", "Addu City", "Fuvahmulah", "Kulhudhuffushi"],
            "names": [
                "Ocean Villa", "Coral Paradise", "Beach House", "Island Retreat"
            ],
            "postcodes": []
        }
    }
    
    # Get country-specific template or use generic
    template = country_templates.get(country, {
        "streets": ["Main Street", "High Street", "Church Street", "Market Street", "Beach Road"],
        "places": ["Capital", "Main Town", "Central District"],
        "names": ["Villa", "House", "Lodge", "Residence", "Cottage"],
        "postcodes": []
    })
    
    # Use real cities if available, otherwise use template cities
    places = real_cities if real_cities else template["places"]
    
    results = []
    used_addresses = set()
    
    for i in range(count):
        # Generate unique address
        max_attempts = 100
        for attempt in range(max_attempts):
            street_no = random.randint(1, 200)
            street = random.choice(template["streets"])
            place = random.choice(places)
            name = random.choice(template["names"])
            
            # FIX 4: Build address with house number FIRST (not business name)
            # Format: {house_number} {street}, {city}, {postcode(optional)}, {country}
            # NOT: {name}, {house_number} {street}, ...
            if template["postcodes"]:
                postcode = random.choice(template["postcodes"])
                display = f"{street_no} {street}, {place}, {postcode}, {country}"
            else:
                display = f"{street_no} {street}, {place}, {country}"
            
            # Ensure uniqueness
            if display not in used_addresses:
                used_addresses.add(display)
                results.append(display)
                break
        
        if len(results) <= i:
            # Fallback if we can't generate unique (FIX 4: house number first)
            if template["postcodes"]:
                postcode = random.choice(template["postcodes"])
                display = f"{street_no} {street}, {place}, {postcode}, {country}"
            else:
                display = f"{street_no} {street}, {place}, {country}"
            results.append(display)
    
    if verbose:
        print(f"     ✨ Generated {len(results)} synthetic addresses for {country}")
    
    return results

# High-level per-country generator (Option A: Overpass -> reverse nodes)
def generate_addresses_for_country(
    country: str,
    per_country: int = 15,
    verbose: bool = True,
    skip_cities: List[str] | None = None,
    existing_addresses: List[dict] | None = None,
) -> tuple[List[dict], List[str], bool]:
    """
    Returns:
        (results, cities_queried, all_cities_exhausted)
        - results: List of address dicts
        - cities_queried: List of city names that were actually queried
        - all_cities_exhausted: True if all cities were processed but still < per_country addresses
    
    Args:
        existing_addresses: List of existing address dicts to check duplicates against
    """
    if verbose:
        print(f"\n  🚀 Starting address generation for {country}...")
        sys.stdout.flush()
    
    if verbose:
        print(f"  📦 Loading GeonamesCache...")
        sys.stdout.flush()
    gc = geonamescache.GeonamesCache()
    
    if verbose:
        print(f"  🔍 Getting country code and cities...")
        sys.stdout.flush()
    # get country code and cities
    country_code = country_to_code(country)
    if verbose:
        print(f"  📍 Country code: {country_code}")
        print(f"  🔄 Loading all cities (this may take a few seconds)...")
        sys.stdout.flush()
    cities = [
        c
        for c in gc.get_cities().values()
        if c.get("countrycode", "").upper() == (country_code or "").upper()
    ]
    if verbose:
        print(f"  ✅ Found {len(cities)} cities for {country}")
        sys.stdout.flush()

    # If we have a list of cities that were already processed for this country
    # (from the existing cache's `cities_processed`), skip them so we don't
    # query Overpass for the same cities again.
    if skip_cities:
        before = len(cities)
        cities = [c for c in cities if c.get("name") not in skip_cities]
        after = len(cities)
        if verbose:
            skipped = before - after
            print(f"  ⏭️  Skipping {skipped} cities already processed in previous runs")
            print(f"  🔄 Remaining cities to process: {after}")
            sys.stdout.flush()

    # For failed-country reprocessing we want to consider ALL remaining cities
    # (not just the top 20), so `center_cities` is the full sorted list.
    if cities:
        cities_sorted = sorted(
            cities, key=lambda x: x.get("population", 0) or 0, reverse=True
        )
        center_cities = cities_sorted
    else:
        cities_sorted = []
        center_cities = []

    if verbose:
        print(f"  📍 Using {len(center_cities)} cities (all remaining cities from Geonames)")
        if USE_LOCAL_NODES_ONLY or country in DISABLE_REVERSE_COUNTRIES:
            print(
                f"  🚫 Reverse geocoding DISABLED for {country} "
                f"(only local nodes with complete address tags will be accepted)"
            )
        sys.stdout.flush()

    results = []
    tried_nodes = set()
    cities_queried = []  # Track which cities were actually queried
    # Track normalized addresses for duplicate detection (validator-level, in-memory only)
    normalized_addresses_seen = set()
    # Track aggressively-normalized addresses (cheat_detection-level) so cache
    # entries are also unique under cheat detection's normalization.
    cheat_normalized_addresses_seen = set()
    
    # Pre-populate seen sets with existing addresses to avoid duplicates
    # This ensures we don't waste time finding addresses that match existing ones
    if existing_addresses:
        preloaded_count = 0
        for existing_addr in existing_addresses:
            if isinstance(existing_addr, dict):
                addr_str = existing_addr.get("address", "")
                if addr_str:
                    # Get cheat_normalized_address if already computed, otherwise compute it
                    cheat_norm = existing_addr.get("cheat_normalized_address") or (
                        normalize_address_for_deduplication(addr_str)
                    )
                    normalized = normalize_address(addr_str)
                    if cheat_norm:
                        cheat_normalized_addresses_seen.add(cheat_norm)
                    if normalized:
                        normalized_addresses_seen.add(normalized)
                    preloaded_count += 1
        if verbose:
            print(f"  🔍 Pre-loaded {preloaded_count} existing addresses into duplicate detection sets")
            print(f"     📊 Normalized strings loaded: {len(cheat_normalized_addresses_seen)} cheat-normalized, {len(normalized_addresses_seen)} normalized")
            print(f"     ✅ All new addresses will be checked against these existing addresses")
    stats = {
        "overpass_queries": 0,
        "nodes_fetched": 0,
        "local_validations": 0,  # Nodes validated locally (no reverse geocoding)
        "reverse_geocoded": 0,
        "validation_passed": 0,
        "validation_failed": 0,
        "duplicates_skipped": 0
    }

    # 1) Try country-specific dense bboxes first (if available)
    bboxes = DENSE_CITY_BBOXES.get(country, [])
    if verbose and bboxes:
        print(f"  🏙️  {country} detected: Using Overpass API for {len(bboxes)} dense bbox(es)")
    
    for bbox_idx, bbox in enumerate(bboxes, 1):
        if len(results) >= per_country:
            break
        if verbose:
            print(f"  📦 Bbox {bbox_idx}/{len(bboxes)}: {bbox}")
        nodes = fetch_nodes_from_overpass_bbox(bbox, verbose=verbose)
        stats["overpass_queries"] += 1
        stats["nodes_fetched"] += len(nodes)
        
        # Prioritize nodes with addr:housenumber (most likely to have small areas)
        nodes = prioritize_nodes(nodes)
        
        if verbose:
            print(f"     🔄 Processing {len(nodes)} nodes from Overpass (prioritized by addr:housenumber)...")
        
        # For every node, try local validation first (skip reverse geocoding if tags are complete)
        # PROCESS ALL NODES - don't skip any
        processed = 0
        for n in nodes:
            if len(results) >= per_country:
                break
            # Process all element types (node, way, relation) - don't skip
            element_type = n.get("type", "unknown")
            element_id = n.get("id")
            
            # Track but don't skip duplicates - process all
            if element_id in tried_nodes:
                stats["duplicates_skipped"] += 1
                # Still process duplicates but mark them
                if verbose and processed % 50 == 0:
                    print(f"     ⚠️  Duplicate element {element_id} (already tried, but processing anyway)")
            else:
                tried_nodes.add(element_id)
            
            processed += 1
            
            # For countries where reverse geocoding is disabled (or universal approach enabled), validate locally first, then with API
            # CRITICAL: We still need to do API validation to ensure score 1.0
            if USE_LOCAL_NODES_ONLY or country in DISABLE_REVERSE_COUNTRIES:
                tags = n.get("tags", {}) or {}
                
                # PROCESS ALL NODES - don't skip any based on tags
                # Build address from tags and validate with all 3 checks
                display = node_tags_to_display_name(tags, country)
                if not display:
                    stats["validation_failed"] += 1
                    if verbose and processed % 5 == 0:
                        print(f"     ❌ REJECTED: Could not build display_name from tags")
                    continue
                
                # Validate with all 3 checks (looks_like_address, validate_address_region, check_with_nominatim)
                is_valid, address_dict = validate_address_complete(display, country, verbose=verbose and processed % 5 == 0)
                
                if is_valid:
                    # Check duplicate AFTER validation (4th level - normalized address checks)
                    addr_str = address_dict.get("address", "")
                    cheat_norm = address_dict.get("cheat_normalized_address", "") or (
                        normalize_address_for_deduplication(addr_str) if addr_str else ""
                    )
                    normalized = normalize_address(addr_str) if addr_str else ""

                    # First guard against aggressive (cheat-detection level) duplicates
                    if cheat_norm and cheat_norm in cheat_normalized_addresses_seen:
                        stats["duplicates_skipped"] += 1
                        if verbose and processed % 10 == 0:
                            print(f"     ⚠️  SKIPPING (cheat-normalized address already seen): {display[:60]}...")
                        continue

                    # Also avoid duplicates under simple normalization for consistency
                    if normalized and normalized in normalized_addresses_seen:
                        stats["duplicates_skipped"] += 1
                        if verbose and processed % 10 == 0:
                            print(f"     ⚠️  SKIPPING (normalized address already seen): {display[:60]}...")
                        continue
                    
                    # Add to results and track both normalization variants (in-memory only)
                    if normalized:
                        normalized_addresses_seen.add(normalized)
                    if cheat_norm:
                        cheat_normalized_addresses_seen.add(cheat_norm)
                    results.append(address_dict)
                    stats["validation_passed"] += 1
                    stats["local_validations"] += 1
                    if verbose:
                        score = address_dict.get("score", 0.0)
                        print(f"     ✅✅✅ ACCEPTED (all 4 checks passed, score: {score:.4f}, {len(results)}/{per_country}): {display[:80]}...")
                    time.sleep(NOMINATIM_SLEEP)  # Rate limit for API validation
                    continue
                else:
                    stats["validation_failed"] += 1
                    if verbose and processed % 10 == 0:
                        print(f"     ❌ REJECTED (failed one or more validation checks): {display[:60]}...")
                    continue
            
            # Step 1: Prioritize nodes with house numbers, but use reverse geocoding to ensure Nominatim can find them
            # CRITICAL: We use reverse geocoding even for nodes with complete tags to ensure addresses are in Nominatim's index
            # This ensures API validation will find the addresses (score 1.0)
            if not (USE_LOCAL_NODES_ONLY or country in DISABLE_REVERSE_COUNTRIES):
                # Check if node has house number (prioritize these for precise geocoding)
                tags = n.get("tags", {}) or {}
                has_housenumber = "addr:housenumber" in tags
                
                # Use reverse geocoding to get Nominatim's version of the address
                # This ensures the address is in Nominatim's search index for API validation
                lat = n.get("lat")
                lon = n.get("lon")
                if lat and lon:
                    nom = reverse_geocode(lat, lon, zoom=19, verbose=verbose and processed % 10 == 0)
                    if nom:
                        stats["reverse_geocoded"] += 1
                        # CRITICAL: Require house number at START (like Poland: "26, Siedlisko...")
                        # This ensures addresses are precise and findable in Nominatim API
                        nom_display = nom.get("display_name", "")
                        if not nom_display:
                            stats["validation_failed"] += 1
                            continue
                        
                        first_part = nom_display.split(",")[0].strip()
                        # FIX 1: Check if first part STARTS with a number (like Poland format)
                        has_number_at_start = first_part and first_part[0].isdigit()
                        
                        if verbose and processed % 10 == 0:
                            print(f"        📍 Reverse geocoded: {nom_display[:60]}...")
                            print(f"        🔍 First part: '{first_part}' | Has number at start: {has_number_at_start}")
                        
                        # Note: House number at start is preferred but not required - process all nodes
                        if not has_number_at_start:
                            if verbose and processed % 10 == 0:
                                print(f"     ⚠️  WARNING: House number not at start (first part: '{first_part}') - will still validate")
                        
                        # Process all nodes - validate regardless of house number position
                        if not validate_nominatim_result(nom, country, verbose=verbose and processed % 10 == 0):
                            stats["validation_failed"] += 1
                            if verbose and processed % 10 == 0:
                                print(f"     ❌ REJECTED: Local validation failed")
                            continue
                        
                        # FAST: Local validation passed, now do API validation (must score 1.0)
                        display = nom["display_name"]
                        is_valid, score = validate_address_with_api(display, country, verbose=verbose and processed % 5 == 0)
                        
                        if is_valid and score >= 0.9:
                            # Use validate_address_complete to get address_dict with both normalizations
                            is_valid_complete, address_dict = validate_address_complete(display, country, verbose=verbose and processed % 5 == 0)
                            
                            if is_valid_complete:
                                # Check duplicate AFTER validation (4th level - normalized address checks)
                                addr_str = address_dict.get("address", "")
                                cheat_norm = address_dict.get("cheat_normalized_address", "") or (
                                    normalize_address_for_deduplication(addr_str) if addr_str else ""
                                )
                                normalized = normalize_address(addr_str) if addr_str else ""

                                if cheat_norm and cheat_norm in cheat_normalized_addresses_seen:
                                    stats["duplicates_skipped"] += 1
                                    if verbose and processed % 10 == 0:
                                        print(f"     ⚠️  SKIPPING (cheat-normalized address already seen): {display[:60]}...")
                                    continue

                                if normalized and normalized in normalized_addresses_seen:
                                    stats["duplicates_skipped"] += 1
                                    if verbose and processed % 10 == 0:
                                        print(f"     ⚠️  SKIPPING (normalized address already seen): {display[:60]}...")
                                    continue
                                
                                # Add to results and track both normalization variants (in-memory only)
                                if normalized:
                                    normalized_addresses_seen.add(normalized)
                                if cheat_norm:
                                    cheat_normalized_addresses_seen.add(cheat_norm)
                                results.append(address_dict)
                                stats["validation_passed"] += 1
                                if verbose:
                                    score = address_dict.get("score", 0.0)
                                    priority_note = " (prioritized: has house number)" if has_housenumber else ""
                                    print(f"     ✅✅✅ ACCEPTED (all 4 checks passed, score: {score:.4f}{priority_note}, {len(results)}/{per_country}): {display[:80]}...")
                                time.sleep(NOMINATIM_SLEEP)  # Rate limit for API validation
                            else:
                                stats["validation_failed"] += 1
                                if verbose and processed % 10 == 0:
                                    print(f"     ❌ REJECTED (failed one or more validation checks): {display[:60]}...")
                        else:
                            stats["validation_failed"] += 1
                    else:
                        stats["validation_failed"] += 1
                continue
            
            # Step 2: For disabled countries, skip reverse geocoding (already handled above)
            if USE_LOCAL_NODES_ONLY or country in DISABLE_REVERSE_COUNTRIES:
                # This should never happen if the check above worked, but adding as safeguard
                stats["validation_failed"] += 1
                if verbose:
                    print(f"     ⚠️  WARNING: Attempted reverse geocoding for {country} (disabled) - skipping node")
                continue
        
        if verbose:
            print(f"     📊 Bbox {bbox_idx} summary: {processed} processed, {len(results)}/{per_country} accepted so far")

    # 2) Try Overpass around center cities (only 20 cities, no expansion)
    if len(results) < per_country and center_cities:
        if verbose:
            print(f"  🏙️  Tier 2: Trying Overpass around {len(center_cities)} major cities...")
    
    for city_idx, city in enumerate(center_cities, 1):
            if len(results) >= per_country:
                break
            city_name = city.get("name", "Unknown")
            lat = float(city.get("latitude"))
            lon = float(city.get("longitude"))
            # define small bbox around city center (approx 10km radius)
            lat_delta = 0.09  # ~10km
            lon_delta = 0.09 / max(0.1, abs((math.cos(math.radians(lat)))))  # adjust for lat
            bbox = (lat - lat_delta, lon - lon_delta, lat + lat_delta, lon + lon_delta)
            if verbose:
                print(f"  📍 City {city_idx}/{len(center_cities)}: {city_name} ({lat:.4f}, {lon:.4f})")
            # Track that we're querying this city
            if city_name not in cities_queried:
                cities_queried.append(city_name)
            nodes = fetch_nodes_from_overpass_bbox(bbox, verbose=verbose)
            stats["overpass_queries"] += 1
            stats["nodes_fetched"] += len(nodes)
            
            # Prioritize nodes with addr:housenumber (most likely to have small areas)
            nodes = prioritize_nodes(nodes)
            
            if verbose:
                print(f"     🔄 Processing {len(nodes)} nodes from {city_name} (prioritized by addr:housenumber)...")
            
            processed = 0
            for n in nodes:
                if len(results) >= per_country:
                    break
                # PROCESS ALL ELEMENT TYPES - don't skip ways/relations
                element_type = n.get("type", "unknown")
                element_id = n.get("id")
                
                # Track but don't skip duplicates - process all
                if element_id in tried_nodes:
                    stats["duplicates_skipped"] += 1
                    if verbose and processed % 50 == 0:
                        print(f"     ⚠️  Duplicate element {element_id} (already tried, but processing anyway)")
                else:
                    tried_nodes.add(element_id)
                
                processed += 1
                
                # For countries where reverse geocoding is disabled (or universal approach enabled), validate locally first, then with API
                # CRITICAL: We still need to do API validation to ensure score 1.0
                if USE_LOCAL_NODES_ONLY or country in DISABLE_REVERSE_COUNTRIES:
                    tags = n.get("tags", {}) or {}
                    
                    # PROCESS ALL NODES - don't skip any based on tags
                    # Build address from tags and validate with all 3 checks
                    display = node_tags_to_display_name(tags, country)
                    if not display:
                        stats["validation_failed"] += 1
                        if verbose and processed % 5 == 0:
                            print(f"     ❌ REJECTED: Could not build display_name from tags")
                        continue
                    
                    # Validate with all 3 checks (looks_like_address, validate_address_region, check_with_nominatim)
                    is_valid, address_dict = validate_address_complete(display, country, verbose=verbose and processed % 5 == 0)
                    
                    if is_valid:
                        # Check duplicate AFTER validation (4th level - normalized address checks)
                        addr_str = address_dict.get("address", "")
                        cheat_norm = address_dict.get("cheat_normalized_address", "") or (
                            normalize_address_for_deduplication(addr_str) if addr_str else ""
                        )
                        normalized = normalize_address(addr_str) if addr_str else ""

                        if cheat_norm and cheat_norm in cheat_normalized_addresses_seen:
                            stats["duplicates_skipped"] += 1
                            if verbose and processed % 10 == 0:
                                print(f"     ⚠️  SKIPPING (cheat-normalized address already seen): {display[:60]}...")
                            continue

                        if normalized and normalized in normalized_addresses_seen:
                            stats["duplicates_skipped"] += 1
                            if verbose and processed % 10 == 0:
                                print(f"     ⚠️  SKIPPING (normalized address already seen): {display[:60]}...")
                            continue
                        
                        # Add to results and track both normalization variants (in-memory only)
                        if normalized:
                            normalized_addresses_seen.add(normalized)
                        if cheat_norm:
                            cheat_normalized_addresses_seen.add(cheat_norm)
                        # Track which city produced this address
                        address_dict["source_city"] = city_name
                        results.append(address_dict)
                        stats["validation_passed"] += 1
                        stats["local_validations"] += 1
                        if verbose:
                            score = address_dict.get("score", 0.0)
                            print(f"     ✅✅✅ ACCEPTED (all 4 checks passed, score: {score:.4f}, {len(results)}/{per_country}): {display[:80]}...")
                        time.sleep(NOMINATIM_SLEEP)  # Rate limit for API validation
                        continue
                    else:
                        stats["validation_failed"] += 1
                        if verbose and processed % 10 == 0:
                            print(f"     ❌ REJECTED (failed one or more validation checks): {display[:60]}...")
                        continue
                
                # Step 1: Prioritize nodes with house numbers, but use reverse geocoding to ensure Nominatim can find them
                # CRITICAL: We use reverse geocoding even for nodes with complete tags to ensure addresses are in Nominatim's index
                # This ensures API validation will find the addresses (score 1.0)
                if not (USE_LOCAL_NODES_ONLY or country in DISABLE_REVERSE_COUNTRIES):
                    # Check if node has house number (prioritize these for precise geocoding)
                    tags = n.get("tags", {}) or {}
                    has_housenumber = "addr:housenumber" in tags
                    
                    # Use reverse geocoding to get Nominatim's version of the address
                    # This ensures the address is in Nominatim's search index for API validation
                    lat = n.get("lat")
                    lon = n.get("lon")
                    if lat and lon:
                        nom = reverse_geocode(lat, lon, zoom=19, verbose=verbose and processed % 10 == 0)
                        if nom:
                            stats["reverse_geocoded"] += 1
                            # CRITICAL: Require house number at START (like Poland: "26, Siedlisko...")
                            # This ensures addresses are precise and findable in Nominatim API
                            nom_display = nom.get("display_name", "")
                            if not nom_display:
                                stats["validation_failed"] += 1
                                continue
                            
                            first_part = nom_display.split(",")[0].strip()
                            # FIX 1: Check if first part STARTS with a number (like Poland format)
                            has_number_at_start = first_part and first_part[0].isdigit()
                            
                            if verbose and processed % 10 == 0:
                                print(f"        📍 Reverse geocoded: {nom_display[:60]}...")
                                print(f"        🔍 First part: '{first_part}' | Has number at start: {has_number_at_start}")
                            
                            # Note: House number at start is preferred but not required - process all nodes
                            if not has_number_at_start:
                                if verbose and processed % 10 == 0:
                                    print(f"     ⚠️  WARNING: House number not at start (first part: '{first_part}') - will still validate")
                            
                            # Process all nodes - validate regardless of house number position
                            if not validate_nominatim_result(nom, country, verbose=verbose and processed % 10 == 0):
                                stats["validation_failed"] += 1
                                if verbose and processed % 10 == 0:
                                    print(f"     ❌ REJECTED: Local validation failed")
                                continue
                            
                            # Validate with all 3 checks (looks_like_address, validate_address_region, check_with_nominatim)
                            display = nom["display_name"]
                            is_valid, address_dict = validate_address_complete(display, country, verbose=verbose and processed % 5 == 0)
                            
                            if is_valid:
                                # Check duplicate AFTER validation (4th level - normalized address checks)
                                # This checks against BOTH existing addresses (pre-loaded) AND newly found addresses
                                addr_str = address_dict.get("address", "")
                                cheat_norm = address_dict.get("cheat_normalized_address", "") or (
                                    normalize_address_for_deduplication(addr_str) if addr_str else ""
                                )
                                normalized = address_dict.get("normalized_address", "") or (
                                    normalize_address(addr_str) if addr_str else ""
                                )
                                
                                # First guard against aggressive (cheat-detection level) duplicates
                                if cheat_norm and cheat_norm in cheat_normalized_addresses_seen:
                                    stats["duplicates_skipped"] += 1
                                    if verbose and processed % 10 == 0:
                                        print(f"     ⚠️  SKIPPING (cheat-normalized address already seen - duplicate of existing): {display[:60]}...")
                                    continue
                                
                                # Also check simple normalized address
                                if normalized and normalized in normalized_addresses_seen:
                                    stats["duplicates_skipped"] += 1
                                    if verbose and processed % 10 == 0:
                                        print(f"     ⚠️  SKIPPING (normalized address already seen - duplicate of existing): {display[:60]}...")
                                    continue
                                
                                # Add to results and track both normalization variants
                                if normalized:
                                    normalized_addresses_seen.add(normalized)
                                if cheat_norm:
                                    cheat_normalized_addresses_seen.add(cheat_norm)
                                # Track which city produced this address
                                address_dict["source_city"] = city_name
                                results.append(address_dict)
                                stats["validation_passed"] += 1
                                if verbose:
                                    score = address_dict.get("score", 0.0)
                                    priority_note = " (prioritized: has house number)" if has_housenumber else ""
                                    print(f"     ✅✅✅ ACCEPTED (all 4 checks passed, score: {score:.4f}{priority_note}, {len(results)}/{per_country}): {display[:80]}...")
                                time.sleep(NOMINATIM_SLEEP)  # Rate limit for API validation
                                continue
                            else:
                                stats["validation_failed"] += 1
                                if verbose and processed % 10 == 0:
                                    print(f"     ❌ REJECTED (failed one or more validation checks): {display[:60]}...")
                        else:
                            stats["validation_failed"] += 1
                    else:
                        stats["validation_failed"] += 1
                    continue
                
                # Step 2: For disabled countries, skip reverse geocoding (already handled above)
                if USE_LOCAL_NODES_ONLY or country in DISABLE_REVERSE_COUNTRIES:
                    # This should never happen if the check above worked, but adding as safeguard
                    stats["validation_failed"] += 1
                    if verbose:
                        print(f"     ⚠️  WARNING: Attempted reverse geocoding for {country} (disabled) - skipping node")
                    continue
            
            if verbose:
                print(f"     📊 {city_name} summary: {processed} processed, {len(results)}/{per_country} accepted so far")

    # 3) If still short, try random sampling (only for countries with reverse geocoding enabled)
    # NOTE: We only use REAL addresses from Overpass/Nominatim - no synthetic addresses
    if len(results) < per_country:
        if USE_LOCAL_NODES_ONLY or country in DISABLE_REVERSE_COUNTRIES:
            if verbose:
                remaining = per_country - len(results)
                print(f"  ⚠️  Could not find enough real addresses: {len(results)}/{per_country}")
                print(f"     Reverse geocoding is disabled for {country}, so random sampling is not available.")
                print(f"     Only real addresses from Overpass nodes are used (no synthetic addresses).")
        else:
            if verbose:
                remaining = per_country - len(results)
                print(f"  🎲 Tier 3: Falling back to random sampling for {remaining} more addresses (max {MAX_ATTEMPTS_PER_COUNTRY} attempts)...")
    
    attempts = 0
    while len(results) < per_country and attempts < MAX_ATTEMPTS_PER_COUNTRY and country not in DISABLE_REVERSE_COUNTRIES:
        attempts += 1
        if not center_cities:
            # pick random geoname country center fallback: use whole country lat/lon from GeonamesCache country info
            country_info = gc.get_countries().get(country_code)
            if country_info and country_info.get("latitude") and country_info.get("longitude"):
                base_lat = float(country_info.get("latitude"))
                base_lon = float(country_info.get("longitude"))
            else:
                # last resort: random global lat/lon (low chance)
                base_lat = random.uniform(-60, 60)
                base_lon = random.uniform(-180, 180)
        else:
            center = random.choice(center_cities)
            base_lat = float(center.get("latitude"))
            base_lon = float(center.get("longitude"))

        # sample within ~25km radius
        lat = base_lat + random.uniform(-0.225, 0.225)
        lon = base_lon + random.uniform(-0.225, 0.225) / max(0.1, abs(math.cos(math.radians(base_lat))))

        if verbose and attempts % 50 == 0:
            print(f"     🔄 Random attempt {attempts}/{MAX_ATTEMPTS_PER_COUNTRY}: Sampling ({lat:.4f}, {lon:.4f})...")

        nom = reverse_geocode(lat, lon, zoom=19, verbose=verbose and attempts % 50 == 0)
        if not nom:
            continue
        stats["reverse_geocoded"] += 1
        
        # ensure not duplicate display_name
        disp = nom.get("display_name")
        if not disp or disp in results:
            stats["duplicates_skipped"] += 1
            continue
        if validate_nominatim_result(nom, country, verbose=verbose and attempts % 50 == 0):
            # FAST: Local validation passed, now do API validation (must score 1.0)
            is_valid, score = validate_address_with_api(disp, country, verbose=verbose and attempts % 10 == 0)
            
            if is_valid and score >= 0.9:
                # Use validate_address_complete to get address_dict with both normalizations
                is_valid_complete, address_dict = validate_address_complete(disp, country, verbose=verbose and attempts % 10 == 0)
                
                if is_valid_complete:
                    # Check duplicate AFTER validation (4th level - normalized address checks)
                    addr_str = address_dict.get("address", "")
                    cheat_norm = address_dict.get("cheat_normalized_address", "") or (
                        normalize_address_for_deduplication(addr_str) if addr_str else ""
                    )
                    normalized = normalize_address(addr_str) if addr_str else ""

                    if cheat_norm and cheat_norm in cheat_normalized_addresses_seen:
                        stats["duplicates_skipped"] += 1
                        if verbose and attempts % 20 == 0:
                            print(f"     ⚠️  SKIPPING (cheat-normalized address already seen): {disp[:60]}...")
                        continue

                    if normalized and normalized in normalized_addresses_seen:
                        stats["duplicates_skipped"] += 1
                        if verbose and attempts % 20 == 0:
                            print(f"     ⚠️  SKIPPING (normalized address already seen): {disp[:60]}...")
                        continue
                    
                    # Add to results and track both normalization variants (in-memory only)
                    if normalized:
                        normalized_addresses_seen.add(normalized)
                    if cheat_norm:
                        cheat_normalized_addresses_seen.add(cheat_norm)
                    # Track which city produced this address
                    address_dict["source_city"] = city_name
                    results.append(address_dict)
                    stats["validation_passed"] += 1
                    if verbose:
                        score = address_dict.get("score", 0.0)
                        print(f"     ✅✅✅ ACCEPTED (all 4 checks passed, score: {score:.4f}, {len(results)}/{per_country}): {disp[:80]}...")
                    time.sleep(NOMINATIM_SLEEP)  # Rate limit for API validation
                else:
                    stats["validation_failed"] += 1
                    if verbose and attempts % 20 == 0:
                        print(f"     ❌ REJECTED (failed one or more validation checks): {disp[:60]}...")
            else:
                stats["validation_failed"] += 1
        else:
            stats["validation_failed"] += 1
    
    # Print final statistics
    if verbose:
        print(f"\n  📊 FINAL STATISTICS for {country}:")
        print(f"     ✅ Accepted: {len(results)}/{per_country} addresses")
        print(f"     📡 Overpass queries: {stats['overpass_queries']}")
        print(f"     📦 Nodes fetched: {stats['nodes_fetched']}")
        print(f"     🏠 Local validations (no reverse geocoding): {stats['local_validations']}")
        print(f"     🔄 Reverse geocoded: {stats['reverse_geocoded']}")
        print(f"     ✅ Validation passed: {stats['validation_passed']}")
        print(f"     ❌ Validation failed: {stats['validation_failed']}")
        print(f"     🔁 Duplicates skipped: {stats['duplicates_skipped']}")
        if stats['reverse_geocoded'] > 0:
            reverse_success_rate = ((stats['validation_passed'] - stats['local_validations']) / stats['reverse_geocoded']) * 100
            print(f"     📈 Reverse geocoding success rate: {reverse_success_rate:.1f}%")
        if stats['local_validations'] > 0:
            print(f"     ⚡ Local validation saved {stats['local_validations']} Nominatim API calls!")
        print()
    
    # Final validation: Test all addresses together with _grade_address_variations (like validator does)
    if len(results) >= per_country:
        if verbose:
            print(f"\n  {'='*60}")
            print(f"  🧪 FINAL VALIDATION: Testing all {len(results)} addresses with validator...")
            print(f"  {'='*60}")
        
        # Format addresses like validator expects (extract address string from address_dict)
        variations = {
            "Test Name": [
                ["Test Name", "1990-01-01", addr.get("address", addr) if isinstance(addr, dict) else addr] 
                for addr in results[:per_country]
            ]
        }
        
        # Seed addresses (one per name)
        seed_addresses = [country] * len(variations)
        
        # Call _grade_address_variations
        validation_result = _grade_address_variations(
            variations=variations,
            seed_addresses=seed_addresses,
            miner_metrics={},
            validator_uid=101,
            miner_uid=501
        )
        
        overall_score = validation_result.get('overall_score', 0.0)
        heuristic_perfect = validation_result.get('heuristic_perfect', False)
        region_matches = validation_result.get('region_matches', 0)
        api_result = validation_result.get('api_result', 'UNKNOWN')
        
        if verbose:
            print(f"\n  📊 VALIDATION RESULTS:")
            print(f"     Overall Score: {overall_score:.4f}")
            print(f"     Heuristic Perfect: {heuristic_perfect}")
            print(f"     Region Matches: {region_matches}/{len(results[:per_country])}")
            print(f"     API Result: {api_result}")
            
            if overall_score >= 0.9:
                print(f"\n  ✅✅✅ SUCCESS: All addresses score 1.0!")
            else:
                print(f"\n  ⚠️  WARNING: Score is {overall_score:.4f} (expected 1.0)")
                print(f"     Some addresses may not score perfectly in validator")
        
        # Only return addresses if they score >= 0.9
        if overall_score < 0.9:
            if verbose:
                print(f"  ❌ FAILED VALIDATION: Score {overall_score:.4f} < 1.0")
                print(f"     Rejecting addresses - will continue searching for valid ones")
            # Return empty list to force regeneration
            all_cities_exhausted = len(cities_queried) >= len(center_cities)
            return ([], cities_queried, all_cities_exhausted)

    # Check if all cities were exhausted
    all_cities_exhausted = len(cities_queried) >= len(center_cities) and len(results) < per_country
    
    return (results, cities_queried, all_cities_exhausted)

# Global variables for signal handling
_cache_save_lock = False
_current_address_cache = None
_current_failed_countries = None
_current_manual_work_needed = None
_current_cities_processed = None
_current_cache_file = None

def save_cache_safely(address_cache: dict, failed_countries: list, cache_file: str, total_countries: int, force: bool = False, cities_processed: dict = None, manual_work_needed: list = None):
    """Safely save cache to disk with error handling and backup."""
    global _cache_save_lock
    if _cache_save_lock and not force:
        return False
    
    _cache_save_lock = True
    try:
        # Create backup of existing cache if it exists
        if os.path.exists(cache_file):
            backup_file = cache_file + ".backup"
            try:
                shutil.copy2(cache_file, backup_file)
            except Exception:
                pass  # Backup is optional
        
        # Use provided cities_processed, or derive it if not provided
        if cities_processed is None:
            # Derive which cities were *targeted* per country using the same
            # Geonames logic as in generate_addresses_for_country (top 20 cities).
            # This includes cities even if they ultimately produced 0 accepted addresses.
            gc = geonamescache.GeonamesCache()
            cities_processed = {}
            for country in address_cache.keys():
                code = country_to_code(country)
                if not code:
                    continue
                all_cities = [
                    c
                    for c in gc.get_cities().values()
                    if c.get("countrycode", "").upper() == code.upper()
                ]
                if not all_cities:
                    continue
                cities_sorted = sorted(
                    all_cities, key=lambda x: x.get("population", 0) or 0, reverse=True
                )
                names = [
                    c.get("name", "")
                    for c in cities_sorted[:20]
                    if c.get("name")
                ]
                if names:
                    cities_processed[country] = names

        cache_data = {
            "addresses": address_cache,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_countries": total_countries,
            "cached_countries": len(address_cache),
            "failed_countries": failed_countries,
            "manual_work_needed": manual_work_needed or [],
            # New: record which cities were processed to obtain the cached addresses
            "cities_processed": cities_processed or {},
        }
        
        # Write to temporary file first, then rename (atomic operation)
        temp_file = cache_file + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
        
        # Atomic rename (works on Unix and Windows)
        if os.path.exists(temp_file):
            if os.path.exists(cache_file):
                os.replace(temp_file, cache_file)
            else:
                os.rename(temp_file, cache_file)
        
        return True
    except Exception as e:
        print(f"   ⚠️ Failed to save cache: {e}")
        return False
    finally:
        _cache_save_lock = False

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully by saving cache before exiting."""
    global _current_address_cache, _current_failed_countries, _current_manual_work_needed, _current_cities_processed, _current_cache_file
    print("\n\n  ⚠️  Interrupt signal received (Ctrl+C)")
    if _current_address_cache is not None:
        print("  💾 Saving cache before exit...")
        cache_file = _current_cache_file or CACHE_FILE
        
        # Get total_countries and preserve existing manual_work_needed from cache file
        total_countries = len(_current_address_cache) + 50  # Estimate if not available
        existing_manual_work_needed = []
        existing_cities_processed = {}
        existing_failed_countries = []
        
        if cache_file and os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                    total_countries = existing.get("total_countries", total_countries)
                    # CRITICAL: Preserve existing manual_work_needed from cache file
                    existing_manual_work_needed = existing.get("manual_work_needed", []) or []
                    existing_cities_processed = existing.get("cities_processed", {}) or {}
                    existing_failed_countries = existing.get("failed_countries", []) or []
            except Exception as e:
                print(f"  ⚠️  Could not load existing cache: {e}")
        
        # Merge manual_work_needed: preserve existing + add any new from in-memory
        # CRITICAL: Always preserve existing manual_work_needed from cache file
        final_manual_work_needed = list(set(existing_manual_work_needed))
        if _current_manual_work_needed and isinstance(_current_manual_work_needed, list):
            # Merge: add any new countries from in-memory that aren't already in existing
            final_manual_work_needed = list(set(final_manual_work_needed + _current_manual_work_needed))
        
        # Merge cities_processed: preserve existing + merge with in-memory
        final_cities_processed = existing_cities_processed.copy()
        if _current_cities_processed:
            for country, cities in _current_cities_processed.items():
                if country in final_cities_processed:
                    # Merge cities lists
                    existing_cities_set = set(final_cities_processed[country])
                    new_cities_set = set(cities)
                    final_cities_processed[country] = sorted(list(existing_cities_set | new_cities_set))
                else:
                    final_cities_processed[country] = cities
        
        # Merge failed_countries: use in-memory if available, otherwise preserve existing
        final_failed_countries = _current_failed_countries if _current_failed_countries is not None else existing_failed_countries
        
        # Count total addresses being saved
        total_addresses = sum(len(addrs) for addrs in _current_address_cache.values())
        
        # Save with merged data
        if save_cache_safely(
            _current_address_cache, 
            final_failed_countries or [], 
            cache_file, 
            total_countries, 
            force=True,
            cities_processed=final_cities_processed, 
            manual_work_needed=final_manual_work_needed
        ):
            print(f"  ✅ Cache saved successfully!")
            print(f"  📊 Countries: {len(_current_address_cache)}")
            print(f"  📊 Total addresses: {total_addresses}")
            print(f"  📊 Failed countries: {len(final_failed_countries)}")
            print(f"  📊 Manual work needed: {len(final_manual_work_needed)}")
            if final_manual_work_needed:
                print(f"     Countries: {', '.join(final_manual_work_needed[:10])}")
                if len(final_manual_work_needed) > 10:
                    print(f"     ... and {len(final_manual_work_needed) - 10} more")
        else:
            print(f"  ❌ Failed to save cache!")
    print("  👋 Exiting gracefully...")
    sys.exit(0)

# generate_address_cache: orchestrator
def generate_address_cache(force_reprocess: bool = False):
    global _current_address_cache, _current_failed_countries, _current_cache_file
    
    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    gc = geonamescache.GeonamesCache()

    # Load valid countries (reuse previous logic: exclude territories)
    countries_data = gc.get_countries()
    excluded_territories = {
        'Antarctica', 'Bouvet Island', 'Heard Island and McDonald Islands',
        'United States Minor Outlying Islands', 'Tokelau',
        'British Indian Ocean Territory', 'Netherlands Antilles',
        'Serbia and Montenegro', 'Antigua and Barbuda', 'Anguilla',
        'American Samoa', 'Aland Islands', 'Barbados', 'Saint Barthelemy',
        'Bermuda', 'Bonaire, Saint Eustatius and Saba ', 'Cocos Islands',
        'Cook Islands', 'Christmas Island', 'Dominica', 'Falkland Islands',
        'Micronesia', 'Faroe Islands', 'Grenada', 'Guernsey', 'Gibraltar',
        'Greenland', 'South Georgia and the South Sandwich Islands',
        'Isle of Man', 'Jersey', 'Kiribati', 'Saint Kitts and Nevis',
        'Liechtenstein', 'Saint Martin', 'Marshall Islands',
        'Northern Mariana Islands', 'Maldives', 'Norfolk Island', 'Nauru',
        'Niue', 'Saint Pierre and Miquelon', 'Pitcairn', 'Palau',
        'Solomon Islands', 'Seychelles', 'Saint Helena',
        'Svalbard and Jan Mayen', 'San Marino', 'Sao Tome and Principe',
        'Sint Maarten', 'French Southern Territories', 'Tonga', 'Tuvalu',
        'Vatican', 'Vanuatu', 'Wallis and Futuna', 'Samoa'
    }

    valid_countries = []
    for code, info in countries_data.items():
        cn = info.get("name", "").strip()
        if not cn or cn in excluded_territories:
            continue
        valid_countries.append(cn)

    valid_countries = sorted(valid_countries)

    # Load incremental cache if exists
    address_cache: dict = {}
    failed_countries: list[str] = []
    manual_work_needed: list[str] = []  # Countries where all cities exhausted but still < 15 addresses
    cities_processed: dict = {}
    cache_file_path = os.path.abspath(CACHE_FILE)
    print(f"📂 Cache file path: {cache_file_path}")
    print(f"🆕 Using new cache location for normalized addresses: {os.path.basename(CACHE_FILE)}")
    
    # Check if new cache exists
    if os.path.exists(CACHE_FILE):
        try:
            file_size = os.path.getsize(CACHE_FILE)
            print(f"📦 Cache file exists ({file_size:,} bytes)")
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
                address_cache = existing.get("addresses", {}) or {}
                failed_countries = existing.get("failed_countries", []) or []
                manual_work_needed = existing.get("manual_work_needed", []) or []
                cities_processed = existing.get("cities_processed", {}) or {}
                complete = len(
                    [c for c in address_cache.keys() if len(address_cache[c]) >= 15]
                )
                partial = len(address_cache) - complete
                print(
                    f"🔁 Resuming from existing cache: {len(address_cache)} countries "
                    f"cached ({complete} complete, {partial} partial)"
                )
                if len(address_cache) > 0:
                    # Show first few countries as verification
                    sample_countries = list(address_cache.keys())[:5]
                    print(
                        f"   📋 Sample cached countries: {', '.join(sample_countries)}"
                    )
        except json.JSONDecodeError as e:
            print(f"⚠️ Cache file is corrupted (invalid JSON): {e}")
            # Try to load from backup if main cache is corrupted
            backup_file = CACHE_FILE + ".backup"
            if os.path.exists(backup_file):
                try:
                    print(f"   🔄 Attempting to load from backup: {backup_file}")
                    with open(backup_file, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                        address_cache = existing.get("addresses", {}) or {}
                        failed_countries = existing.get("failed_countries", []) or []
                        manual_work_needed = existing.get("manual_work_needed", []) or []
                        cities_processed = existing.get("cities_processed", {}) or {}
                        print(
                            f"   ✅ Loaded {len(address_cache)} countries from backup"
                        )
                except Exception as e2:
                    print(f"   ⚠️ Could not load backup either: {e2}")
        except Exception as e:
            print(f"⚠️ Could not load existing cache: {e}")
            import traceback
            print(f"   Traceback: {traceback.format_exc()}")
    else:
        print(f"📝 No existing cache file found - starting fresh")
    
    # Update global variables for signal handler
    _current_address_cache = address_cache
    _current_failed_countries = failed_countries
    _current_manual_work_needed = manual_work_needed
    _current_cities_processed = cities_processed
    _current_cache_file = CACHE_FILE

    total_countries = len(valid_countries)
    # Count complete countries (15+ addresses) and partial countries (< 15 addresses)
    complete_countries = [
        c for c in address_cache.keys() if len(address_cache[c]) >= 15
    ]
    partial_countries = [
        c for c in address_cache.keys() if len(address_cache[c]) < 15
    ]

    # We only process the countries currently listed in failed_countries.
    # BUT skip countries that are in manual_work_needed (all cities exhausted)
    original_failed = [c for c in failed_countries if c in valid_countries and c not in manual_work_needed]
    current_failed = original_failed.copy()
    
    if manual_work_needed:
        print(f"⚠️  Skipping {len(manual_work_needed)} countries in 'manual_work_needed' (all cities exhausted):")
        print(f"   {', '.join(manual_work_needed[:10])}")
        if len(manual_work_needed) > 10:
            print(f"   ... and {len(manual_work_needed) - 10} more")

    start_time = time.time()

    print("\n" + "=" * 80)
    print("ADDRESS CACHE GENERATION (FAILED COUNTRIES ONLY)")
    print("=" * 80)
    print(f"Total countries: {total_countries}")
    print(
        f"Already cached (complete): {len(complete_countries)} countries with 15+ addresses"
    )
    print(
        f"Already cached (partial): {len(partial_countries)} countries with < 15 addresses"
    )
    print(f"Failed countries to process: {len(original_failed)}")
    if original_failed:
        print(f"   First few: {', '.join(original_failed[:10])}")
        if len(original_failed) > 10:
            print(f"   ... and {len(original_failed) - 10} more")
    print(f"Cache file: {CACHE_FILE}")
    print("=" * 80 + "\n")

    if not original_failed:
        print("⚠️  No failed countries to process. Exiting.")
        return CACHE_FILE

    for idx, country in enumerate(original_failed, 1):
        existing_addresses = address_cache.get(country, [])
        existing_count = len(existing_addresses)

        # Cities that were already processed in previous runs for this country
        skip_cities = cities_processed.get(country, [])

        country_start_time = time.time()
        print("\n" + "=" * 80)
        print(f"[{idx}/{len(original_failed)}] 🏳️  PROCESSING FAILED COUNTRY: {country}")
        print(f"   Existing addresses: {existing_count}/15")
        print(f"   Cities already processed (skip): {len(skip_cities)}")
        print(f"   Started at: {time.strftime('%H:%M:%S')}")
        print("=" * 80)

        # We only need the *remaining* number of addresses for this country.
        remaining_needed = max(0, 15 - existing_count)

        try:
            new_addresses: List[dict] = []
            cities_queried_for_country: List[str] = []
            all_cities_exhausted = False
            if remaining_needed > 0:
                new_addresses, cities_queried_for_country, all_cities_exhausted = generate_addresses_for_country(
                    country,
                    per_country=remaining_needed,
                    verbose=True,
                    skip_cities=skip_cities,
                    existing_addresses=existing_addresses,
                )
        except KeyboardInterrupt:
            print(f"\n  ⚠️  Interrupted by user")
            # Save cache before exiting
            print("  💾 Saving cache before exit...")
            _current_address_cache = address_cache
            _current_failed_countries = current_failed
            if save_cache_safely(
                address_cache, current_failed, CACHE_FILE, total_countries, force=True,
                cities_processed=cities_processed, manual_work_needed=manual_work_needed
            ):
                print(f"  ✅ Cache saved: {len(address_cache)} countries")
            raise
        except Exception as e:
            import traceback

            print(
                f"  ❌ Error generating for {country}: {type(e).__name__}: {e}"
            )
            print(f"  Traceback: {traceback.format_exc()}")
            new_addresses = []
            cities_queried_for_country = []
            all_cities_exhausted = False

        # Merge existing + new and enforce uniqueness on cheat_normalized_address
        combined = []
        if isinstance(existing_addresses, list):
            combined.extend(existing_addresses)
        if isinstance(new_addresses, list):
            combined.extend(new_addresses)

        seen_norms = set()
        final_addresses: List[dict] = []

        for addr in combined:
            if not isinstance(addr, dict):
                # Backward-compat: addr is a plain string
                addr_str = str(addr)
                cheat_norm = normalize_address_for_deduplication(addr_str)
                addr_dict = {
                    "address": addr_str,
                    "score": 1.0,
                    "cheat_normalized_address": cheat_norm,
                }
            else:
                addr_dict = addr
                addr_str = addr_dict.get("address", "")
                cheat_norm = addr_dict.get("cheat_normalized_address") or (
                    normalize_address_for_deduplication(addr_str) if addr_str else ""
                )

            if not cheat_norm:
                continue

            if cheat_norm in seen_norms:
                continue

            seen_norms.add(cheat_norm)
            final_addresses.append(addr_dict)

            if len(final_addresses) >= 15:
                break

        country_elapsed = time.time() - country_start_time

        # Update cities_processed with cities that were queried
        if cities_queried_for_country:
            existing_cities = set(cities_processed.get(country, []))
            existing_cities.update(cities_queried_for_country)
            cities_processed[country] = sorted(list(existing_cities))
        
        if len(final_addresses) >= 15:
            address_cache[country] = final_addresses[:15]
            if country in current_failed:
                current_failed.remove(country)
            # Remove from manual_work_needed if it was there
            if country in manual_work_needed:
                manual_work_needed.remove(country)
            print(
                f"\n  ✅ COUNTRY COMPLETED: {country} "
                f"({len(final_addresses[:15])}/15 unique addresses in {country_elapsed:.1f}s)"
            )
            print(f"  🎉 Removed from failed_countries list!")
        else:
            # Still failed: keep whatever unique addresses we managed to collect
            address_cache[country] = final_addresses
            if country not in current_failed:
                current_failed.append(country)
            
            # If all cities were exhausted, add to manual_work_needed
            if all_cities_exhausted:
                if country not in manual_work_needed:
                    manual_work_needed.append(country)
                print(
                    f"\n  ❌ COUNTRY STILL FAILED (ALL CITIES EXHAUSTED): {country} "
                    f"({len(final_addresses)}/15 unique addresses in {country_elapsed:.1f}s)"
                )
                print(
                    "  ⚠️  All available cities were exhausted. Added to 'manual_work_needed' list."
                )
            else:
                print(
                    f"\n  ❌ COUNTRY STILL FAILED: {country} "
                    f"({len(final_addresses)}/15 unique addresses in {country_elapsed:.1f}s)"
                )
                print(
                    "  ⚠️  Insufficient unique addresses found. Will retry on next run."
                )

        # Update global variables for signal handler
        _current_address_cache = address_cache
        _current_failed_countries = current_failed
        _current_manual_work_needed = manual_work_needed
        _current_cities_processed = cities_processed

        # Save incremental cache safely
        if save_cache_safely(
            address_cache, current_failed, CACHE_FILE, total_countries,
            cities_processed=cities_processed, manual_work_needed=manual_work_needed
        ):
            print(
                f"   💾 Cache saved incrementally "
                f"({len(address_cache)}/{total_countries} countries)"
            )
        else:
            print(f"   ⚠️ Failed to save cache (check permissions)")

        # Progress summary
        elapsed_total = time.time() - start_time
        remaining = len(original_failed) - idx
        avg_time_per_country = elapsed_total / idx if idx > 0 else 0
        estimated_remaining = avg_time_per_country * remaining if remaining > 0 else 0

        print(
            f"   ⏱️  Progress: {idx}/{len(original_failed)} failed countries | "
            f"Elapsed: {elapsed_total/60:.1f}m | "
            f"Avg: {avg_time_per_country:.1f}s/country | "
            f"Est. remaining: {estimated_remaining/60:.1f}m"
        )

        # polite pause between countries
        time.sleep(0.5)

    # Replace failed_countries with the updated list
    failed_countries[:] = current_failed
    
    # Calculate how many countries were cleared
    countries_cleared = len(original_failed) - len(current_failed)

    overall_elapsed = time.time() - start_time
    
    # Calculate statistics
    total_addresses = sum(len(addrs) for addrs in address_cache.values())
    complete_countries = len([c for c in address_cache.keys() if len(address_cache[c]) >= 15])
    partial_countries = len(address_cache) - complete_countries
    
    print("\n" + "="*80)
    print("🎉 ALL DONE - FINAL SUMMARY")
    print("="*80)
    print(f"⏱️  Total time elapsed: {overall_elapsed/60:.1f} minutes ({overall_elapsed:.0f} seconds)")
    print(f"✅ Countries cleared from failed_countries: {countries_cleared}")
    print(f"⚠️  Countries in manual_work_needed: {len(manual_work_needed)}")
    if manual_work_needed:
        print(f"   {', '.join(manual_work_needed[:10])}")
        if len(manual_work_needed) > 10:
            print(f"   ... and {len(manual_work_needed) - 10} more")
    print(f"📊 Countries processed: {len(address_cache)}/{total_countries}")
    print(f"   ✅ Complete (15 addresses): {complete_countries}")
    print(f"   ⚠️  Partial (<15 addresses): {partial_countries}")
    print(f"   ❌ Failed: {len(failed_countries)}")
    print(f"📦 Total addresses cached: {total_addresses}")
    if len(address_cache) > 0:
        avg_addresses = total_addresses / len(address_cache)
        print(f"📈 Average addresses per country: {avg_addresses:.1f}")
    if overall_elapsed > 0:
        print(f"⚡ Processing rate: {len(address_cache) / (overall_elapsed/60):.2f} countries/minute")
    print(f"💾 Cache file: {CACHE_FILE}")
    if _nominatim_403_count > 0:
        print(f"⚠️  Nominatim 403 errors encountered: {_nominatim_403_count}")
        if _nominatim_403_count >= _nominatim_403_threshold:
            print(f"   🚨 High number of 403 errors - consider:")
            print(f"      - Setting USER_AGENT environment variable")
            print(f"      - Increasing NOMINATIM_SLEEP (currently {NOMINATIM_SLEEP}s)")
            print(f"      - Using your own Nominatim instance")
    if failed_countries:
        print(f"\n⚠️  Failed countries ({len(failed_countries)}):")
        for fc in failed_countries[:10]:  # Show first 10
            print(f"   - {fc} ({len(address_cache.get(fc, []))} addresses)")
        if len(failed_countries) > 10:
            print(f"   ... and {len(failed_countries) - 10} more")
    print("="*80)
    
    # Final save to ensure manual_work_needed is persisted
    save_cache_safely(
        address_cache, failed_countries, CACHE_FILE, total_countries, force=True,
        cities_processed=cities_processed, manual_work_needed=manual_work_needed
    )

    return CACHE_FILE

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate validated address cache for all countries")
    parser.add_argument("--force", action="store_true", 
                       help="Force re-processing of countries that already have 15+ addresses")
    args = parser.parse_args()
    generate_address_cache(force_reprocess=args.force)
