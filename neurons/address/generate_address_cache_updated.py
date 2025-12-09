#!/usr/bin/env python3

"""
Max-quality address cache generator (Updated Version)

Requirements:
- requests
- geonamescache
- your project: MIID/validator/reward.py with:
    looks_like_address, extract_city_country, validate_address_region,
    compute_bounding_box_areas_meters

What it does:
- For each country from GeonamesCache (excluding territories) it fetches candidate
  nodes via Overpass and validates them. Validates each using your exact functions 
  and caches results incrementally to validated_address_cache_fresh_start.json.

Changes:
- Accepts addresses with score >= 0.9 (not just 1.0)
- Stores address, score, and normalized_address for each entry
- Uses only top 20 cities (no progressive expansion)
- 4-level validation: looks_like_address, validate_address_region, API validation (>=0.9), duplicate check
- Fresh cache location: validated_address_cache_fresh_start.json

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

# Configuration
OVERPASS_URL = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
NOMINATIM_URL = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org/reverse")
# Proper User-Agent with contact info (REQUIRED by Nominatim to avoid 403 errors)
USER_AGENT = os.getenv("USER_AGENT", "MIIDSubnet/1.0 (contact: prasadpsd2001@gmail.com)")
# New cache location - starting completely fresh
CACHE_FILE = os.path.join(os.path.dirname(__file__), "validated_address_cache_fresh_psd.json")

# Proxy configuration for IP rotation (optional)
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
    """Get proxy configuration for requests."""
    if for_overpass:
        return None
    
    if for_nominatim:
        if _free_proxy_enabled:
            try:
                free_proxy_url = get_free_proxy()
                if free_proxy_url:
                    return {"http": free_proxy_url, "https": free_proxy_url}
            except Exception as e:
                print(f"⚠️  Free proxy error: {e}")
        
        if PROXY_URL:
            return {"http": PROXY_URL, "https": PROXY_URL}
        return None
    
    if PROXY_URL:
        return {"http": PROXY_URL, "https": PROXY_URL}
    return None

# Safety/timeouts
NOMINATIM_SLEEP = 1.0   # seconds between Nominatim calls
OVERPASS_SLEEP = 1.0    # polite pause between Overpass calls
MAX_OVERPASS_TIMEOUT = 180
MAX_OVERPASS_NODES = 2000
MAX_REVERSE_ATTEMPTS_PER_NODE = 1
MAX_ATTEMPTS_PER_COUNTRY = 0  # Disabled: random sampling is disabled

# Global error tracking
_nominatim_403_count = 0
_nominatim_403_threshold = 10
_nominatim_403_cooldown_threshold = 5

# Countries where reverse geocoding is disabled
_LEGACY_DISABLE_LIST = {
    "Afghanistan", "Somalia", "South Sudan", "Yemen", "Libya",
    "Brunei", "Burkina Faso", "Central African Republic", "Chad",
    "Bonaire, Saint Eustatius and Saba", "British Virgin Islands",
    "Cayman Islands", "Bermuda", "Seychelles", "Maldives",
    "Falkland Islands", "Turks and Caicos Islands", "Cook Islands",
    "Samoa", "Tonga", "Vanuatu", "Saint Helena",
    "Anguilla", "Montserrat", "Saint Kitts and Nevis",
    "Antigua and Barbuda", "Dominica", "Saint Lucia",
    "Saint Vincent and the Grenadines", "Grenada", "Barbados",
    "Aruba", "Curaçao", "Sint Maarten",
    "Palau", "Nauru", "Tuvalu", "Kiribati", "Marshall Islands",
    "Micronesia", "Niue",
    "Gibraltar", "Monaco", "San Marino", "Liechtenstein",
    "Andorra", "Vatican", "Malta"
}

USE_LOCAL_NODES_ONLY = True  # Disable reverse geocoding for all countries
DISABLE_REVERSE_COUNTRIES = _LEGACY_DISABLE_LIST

# Bounding boxes for high-density areas
DENSE_CITY_BBOXES = {
    "Afghanistan": [(34.5220, 69.1600, 34.5360, 69.1860)],  # Kabul center
}

# Country name mappings
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
    """Compare country names with normalization for known mismatches."""
    if not extracted_country or not expected_country:
        return False
    
    extracted_lower = extracted_country.strip().lower()
    expected_lower = expected_country.strip().lower()
    
    if extracted_lower == expected_lower:
        return True
    
    if expected_country in COUNTRY_NAME_MAPPINGS:
        valid_names = [name.lower() for name in COUNTRY_NAME_MAPPINGS[expected_country]]
        if extracted_lower in valid_names:
            return True
    
    for key, values in COUNTRY_NAME_MAPPINGS.items():
        if key.lower() == expected_lower:
            valid_names = [name.lower() for name in values]
            if extracted_lower in valid_names:
                return True
    
    if extracted_lower in expected_lower or expected_lower in extracted_lower:
        if len(extracted_lower) > 5 and len(expected_lower) > 5:
            return True
    
    return False

def country_to_code(name: str) -> str:
    """Convert country name -> ISO code (geonamescache)."""
    gc = geonamescache.GeonamesCache()
    for code, info in gc.get_countries().items():
        if info.get("name", "").strip().lower() == name.strip().lower():
            return code
    return ""

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

def fetch_nodes_from_overpass_bbox(bbox: Tuple[float, float, float, float], timeout: int = MAX_OVERPASS_TIMEOUT, verbose: bool = True) -> List[dict]:
    """Premium multi-step Overpass query with progressive fallback."""
    min_lat, min_lon, max_lat, max_lon = bbox
    if verbose:
        print(f"     🔍 Querying Overpass API (multi-step fallback) for bbox ({min_lat:.4f}, {min_lon:.4f}, {max_lat:.4f}, {max_lon:.4f})...")
    
    q = f"""
    [out:json][timeout:{timeout}];
    (
      nwr["addr:housenumber"]["addr:street"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["addr:street"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["addr:place"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["addr:block"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["addr:neighbourhood"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["addr:suburb"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["addr:district"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["addr:city"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["addr:housenumber"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["building"~"^(house|residential|apartments|detached|semi|terrace|bungalow|villa|yes)$"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["building"~"^(house|residential|apartments|detached|semi|terrace|bungalow|villa|yes)$"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["name"]["building"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["name"]["amenity"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["name"]["shop"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["name"]["office"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["name"]["tourism"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["name"]["healthcare"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["name"]["historic"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["name"]["leisure"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["name"]["sport"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["highway"]["name"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["highway"~"^(residential|unclassified|tertiary|secondary|primary)$"]["name"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["entrance"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["entrance"]["addr:housenumber"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["addr:postcode"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["building"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["amenity"]["name"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["shop"]["name"]({min_lat},{min_lon},{max_lat},{max_lon});
      nwr["tourism"]["name"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out center {MAX_OVERPASS_NODES};
    """
    
    start_time = time.time()
    try:
        proxies = get_proxies(for_overpass=True)
        r = requests.post(OVERPASS_URL, data={"data": q}, timeout=timeout + 10, proxies=proxies, verify=True)
        r.raise_for_status()
        data = r.json()
        elems = data.get("elements", [])[:MAX_OVERPASS_NODES]
        elapsed = time.time() - start_time
        
        nodes_count = sum(1 for e in elems if e.get("type") == "node")
        ways_count = sum(1 for e in elems if e.get("type") == "way")
        relations_count = sum(1 for e in elems if e.get("type") == "relation")
        
        if verbose:
            print(f"     ⏱️  Overpass query completed in {elapsed:.2f}s, received {len(elems)} elements (limited to {MAX_OVERPASS_NODES})")
            print(f"        📊 Breakdown: {nodes_count} nodes, {ways_count} ways, {relations_count} relations")
        
        time.sleep(OVERPASS_SLEEP)
        return elems
    except requests.exceptions.Timeout as e:
        if verbose:
            print(f"     ⚠️  Overpass timeout error after {timeout}s: {e}")
        return []
    except requests.exceptions.RequestException as e:
        if verbose:
            print(f"     ⚠️  Overpass request error: {e}")
        return []
    except Exception as e:
        if verbose:
            print(f"     ⚠️  Overpass error: {type(e).__name__}: {e}")
        return []

def reverse_geocode(lat: float, lon: float, zoom: int = 19, verbose: bool = False, max_retries: int = 3) -> dict:
    """Reverse-geocode lat/lon with Nominatim (zoom=19)."""
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
            proxies = get_proxies(for_overpass=False, for_nominatim=True)
            verify_ssl = proxies is None or (PROXY_URL and proxies.get("https") == PROXY_URL)
            r = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=15, proxies=proxies, verify=verify_ssl)
            
            if r.status_code == 403:
                global _nominatim_403_count, _nominatim_403_cooldown_threshold
                _nominatim_403_count += 1
                retry_after = 5 * (2 ** attempt)
                if verbose:
                    print(f"        ⚠️  Nominatim HTTP 403 (rate limited/blocked) for ({lat:.4f}, {lon:.4f})")
                    if attempt < max_retries - 1:
                        print(f"        ⏳ Retrying after {retry_after}s (attempt {attempt + 1}/{max_retries})...")
                
                if _nominatim_403_count > _nominatim_403_cooldown_threshold:
                    cooldown_time = 60
                    print(f"\n        🚨 COOLDOWN: {_nominatim_403_count} Nominatim 403 errors detected!")
                    print(f"        ⏸️  Waiting {cooldown_time}s to prevent IP ban...")
                    time.sleep(cooldown_time)
                
                if _nominatim_403_count >= _nominatim_403_threshold and _nominatim_403_count == _nominatim_403_threshold:
                    print(f"\n        🚨 WARNING: {_nominatim_403_count} Nominatim 403 errors detected!")
                
                if attempt < max_retries - 1:
                    time.sleep(retry_after)
                    continue
                time.sleep(5)
                return {}
            
            if r.status_code != 200:
                if verbose:
                    status_msg = {
                        429: "Too Many Requests (rate limited)",
                        503: "Service Unavailable",
                        504: "Gateway Timeout"
                    }.get(r.status_code, f"HTTP {r.status_code}")
                    print(f"        ⚠️  Nominatim {status_msg} for ({lat:.4f}, {lon:.4f})")
                time.sleep(5)
                return {}
            
            data = r.json()
            if verbose and data.get("display_name"):
                print(f"        📍 Reverse geocoded ({lat:.4f}, {lon:.4f}): {data.get('display_name', '')[:60]}...")
            
            time.sleep(NOMINATIM_SLEEP)
            return data
            
        except requests.exceptions.ProxyError as e:
            if _free_proxy_enabled and proxies:
                try:
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
                time.sleep(2 ** attempt)
                continue
            time.sleep(5)
            return {}
        except requests.exceptions.RequestException as e:
            if verbose:
                print(f"        ⚠️  Nominatim request error for ({lat:.4f}, {lon:.4f}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            time.sleep(5)
            return {}
        except Exception as e:
            if verbose:
                print(f"        ⚠️  Nominatim error for ({lat:.4f}, {lon:.4f}): {type(e).__name__}: {e}")
            return {}
    
    return {}

def prioritize_nodes(nodes: List[dict]) -> List[dict]:
    """Sort nodes to prioritize those with addr:housenumber."""
    def node_priority(node: dict) -> int:
        tags = node.get("tags", {}) or {}
        priority = 0
        if "addr:housenumber" in tags:
            priority += 1000
        if "addr:street" in tags:
            priority += 500
        if "name" in tags:
            priority += 100
        if tags.get("building"):
            priority += 50
        return priority
    
    sorted_nodes = sorted(nodes, key=lambda n: (-node_priority(n), n.get("id", 0)))
    return sorted_nodes

def node_tags_to_display_name(node_tags: dict, country: str) -> str:
    """Build display-like string from Overpass node tags."""
    parts = []
    if not node_tags:
        return None
    
    housen = (node_tags.get("addr:housenumber") or 
              node_tags.get("housenumber") or
              node_tags.get("addr:house"))
    
    street = (node_tags.get("addr:street") or 
              node_tags.get("street") or 
              node_tags.get("addr:place") or
              node_tags.get("addr:block") or
              node_tags.get("addr:neighbourhood") or
              node_tags.get("addr:suburb") or
              node_tags.get("addr:district"))
    
    if housen and street:
        parts.append(f"{housen}")
        parts.append(street)
    elif housen:
        parts.append(f"{housen}")
        road_name = (node_tags.get("name") or
                     node_tags.get("addr:road") or
                     node_tags.get("highway"))
        if road_name:
            parts.append(road_name)
    elif street:
        parts.append(street)
    elif node_tags.get("name"):
        name = node_tags.get("name")
        if name and name[0].isdigit():
            parts.append(name)
        else:
            parts.append(name)
    
    city_found = False
    for k in ("addr:city", "city", "town", "village", "suburb", 
              "addr:district", "addr:suburb", "addr:neighbourhood",
              "addr:block", "addr:place", "place", "municipality"):
        if node_tags.get(k):
            parts.append(node_tags.get(k))
            city_found = True
            break
    
    postcode = (node_tags.get("addr:postcode") or
                node_tags.get("postcode") or
                node_tags.get("postal_code") or
                node_tags.get("addr:postal_code"))
    if postcode:
        parts.append(postcode)
    
    parts.append(country)
    display = ", ".join([p for p in parts if p])
    return display if display else None

def validate_nominatim_result(nom_res: dict, country: str, verbose: bool = False) -> bool:
    """Validate a Nominatim result using exact validators."""
    if not nom_res or "display_name" not in nom_res:
        if verbose:
            print(f"        ❌ Validation failed: No display_name in result")
        return False
    display = nom_res["display_name"]
    
    if not validate_address_region(display, country):
        if verbose:
            print(f"        ❌ Validation failed: Region validation failed")
        return False
    
    if not looks_like_address(display):
        if verbose:
            print(f"        ❌ Validation failed: Failed 'looks_like_address' heuristic")
        return False
    
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
    """Validate address using check_with_nominatim from rewards.py. Accepts score >= 0.9."""
    if verbose:
        print(f"        🔍 API validation: Checking with Nominatim (must score >= 0.9)...")
    
    original_proxy_url = os.getenv("PROXY_URL", None)
    free_proxy_used = None
    
    if _free_proxy_enabled:
        try:
            free_proxy_url = get_free_proxy()
            if free_proxy_url:
                os.environ["PROXY_URL"] = free_proxy_url
                free_proxy_used = free_proxy_url
                if verbose:
                    print(f"        🔄 Using free proxy: {free_proxy_url[:50]}...")
        except Exception as e:
            if verbose:
                print(f"        ⚠️  Free proxy error: {e}")
    
    try:
        api_result = check_with_nominatim(
            address=address,
            validator_uid=101,
            miner_uid=501,
            seed_address=country,
            seed_name="Test"
        )
    finally:
        if free_proxy_used:
            if original_proxy_url:
                os.environ["PROXY_URL"] = original_proxy_url
            else:
                os.environ.pop("PROXY_URL", None)
            if isinstance(api_result, (int, float)) and api_result == 0.0:
                try:
                    mark_proxy_failed(free_proxy_used)
                    if verbose:
                        print(f"        ⚠️  Marked proxy as failed (validation returned 0.0)")
                except:
                    pass
    
    time.sleep(NOMINATIM_SLEEP)
    
    if api_result == "TIMEOUT":
        if verbose:
            print(f"        ⚠️  API timeout")
        time.sleep(5)
        return False, 0.0
    
    if api_result == 0.0:
        if verbose:
            print(f"        ❌ API check failed (no results)")
        return False, 0.0
    
    if isinstance(api_result, dict):
        api_score = api_result.get('score', 0.0)
        area = api_result.get('min_area')
        
        if api_score >= 0.9:  # CHANGED: Accept score >= 0.9 (not just 1.0)
            if verbose:
                print(f"        ✅✅✅ API check passed (score: {api_score:.4f}, area: {area:.2f} m²)")
            return True, api_score
        else:
            if verbose:
                print(f"        ❌ API check failed (score: {api_score:.4f} < 0.9, area: {area:.2f} m²)")
            return False, api_score
    else:
        if api_result >= 0.9:  # CHANGED: Accept score >= 0.9
            if verbose:
                print(f"        ✅✅✅ API check passed (score: {api_result:.4f})")
            return True, api_result
        else:
            if verbose:
                print(f"        ❌ API check failed (score: {api_result:.4f} < 0.9)")
            return False, api_result

def validate_address_complete(address: str, country: str, verbose: bool = False) -> Tuple[bool, dict]:
    """
    Validate address with all 3 checks:
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
    
    # Normalize address for duplicate detection
    normalized = normalize_address(address)
    address_dict = {
        "address": address,
        "score": score,
        "normalized_address": normalized
    }
    
    return True, address_dict

def generate_addresses_for_country(country: str, per_country: int = 15, verbose: bool = True, existing_cache: dict = None) -> List[dict]:
    """High-level per-country generator. Returns list of address dicts with address, score, normalized_address."""
    if verbose:
        print(f"\n  🚀 Starting address generation for {country}...")
        sys.stdout.flush()
    
    gc = geonamescache.GeonamesCache()
    
    country_code = country_to_code(country)
    if verbose:
        print(f"  📍 Country code: {country_code}")
        print(f"  🔄 Loading all cities (this may take a few seconds)...")
        sys.stdout.flush()
    
    cities = [c for c in gc.get_cities().values() if c.get("countrycode", "").upper() == (country_code or "").upper()]
    if verbose:
        print(f"  ✅ Found {len(cities)} cities for {country}")
        sys.stdout.flush()
    
    # CHANGED: Use only top 20 cities (no progressive expansion)
    if cities:
        cities_sorted = sorted(cities, key=lambda x: x.get("population", 0) or 0, reverse=True)
        center_cities = cities_sorted[:20]  # Only 20 cities
    else:
        center_cities = []

    if verbose:
        print(f"  📍 Using {len(center_cities)} cities as center points (top 20 cities only)")
        if USE_LOCAL_NODES_ONLY or country in DISABLE_REVERSE_COUNTRIES:
            print(f"  🚫 Reverse geocoding DISABLED for {country}")
        sys.stdout.flush()

    results = []
    tried_nodes = set()
    normalized_addresses_seen = set()  # Track normalized addresses for duplicate detection (4th level)
    
    # Load normalized addresses from existing cache for this country (if resuming)
    if existing_cache and country in existing_cache:
        for cached_addr in existing_cache[country]:
            if isinstance(cached_addr, dict) and "normalized_address" in cached_addr:
                normalized_addresses_seen.add(cached_addr["normalized_address"])
            elif isinstance(cached_addr, str):
                # If cache has old format (just strings), normalize them
                normalized_addresses_seen.add(normalize_address(cached_addr))
    
    stats = {
        "overpass_queries": 0,
        "nodes_fetched": 0,
        "local_validations": 0,
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
        
        nodes = prioritize_nodes(nodes)
        
        if verbose:
            print(f"     🔄 Processing {len(nodes)} nodes from Overpass (prioritized by addr:housenumber)...")
        
        processed = 0
        for n in nodes:
            if len(results) >= per_country:
                break
            
            element_id = n.get("id")
            if element_id in tried_nodes:
                stats["duplicates_skipped"] += 1
                if verbose and processed % 50 == 0:
                    print(f"     ⚠️  Duplicate element {element_id} (already tried)")
            else:
                tried_nodes.add(element_id)
            
            processed += 1
            
            if USE_LOCAL_NODES_ONLY or country in DISABLE_REVERSE_COUNTRIES:
                tags = n.get("tags", {}) or {}
                display = node_tags_to_display_name(tags, country)
                if not display:
                    stats["validation_failed"] += 1
                    continue
                
                # Validate with all 3 checks first
                is_valid, address_dict = validate_address_complete(display, country, verbose=verbose and processed % 5 == 0)
                
                if is_valid:
                    # Check duplicate AFTER validation (4th level - normalized address check)
                    # Use normalized_address from address_dict (already normalized in validate_address_complete)
                    normalized = address_dict.get("normalized_address", "")
                    if normalized in normalized_addresses_seen:
                        stats["duplicates_skipped"] += 1
                        if verbose and processed % 10 == 0:
                            print(f"     ⚠️  SKIPPING (normalized address already seen): {display[:60]}...")
                        continue
                    
                    # Add to results and track normalized address
                    normalized_addresses_seen.add(normalized)
                    results.append(address_dict)
                    stats["validation_passed"] += 1
                    stats["local_validations"] += 1
                    if verbose:
                        print(f"     ✅✅✅ ACCEPTED (all 4 checks passed, score: {address_dict['score']:.4f}, {len(results)}/{per_country}): {display[:80]}...")
                    time.sleep(NOMINATIM_SLEEP)
                    continue
                else:
                    stats["validation_failed"] += 1
                    if verbose and processed % 10 == 0:
                        print(f"     ❌ REJECTED (failed one or more validation checks): {display[:60]}...")
                    continue
        
        if verbose:
            print(f"     📊 Bbox {bbox_idx} summary: {processed} processed, {len(results)}/{per_country} accepted so far")

    # 2) Try Overpass around center cities (only 20 cities)
    if len(results) < per_country and center_cities:
        if verbose:
            print(f"  🏙️  Tier 2: Trying Overpass around {len(center_cities)} major cities...")
    
    for city_idx, city in enumerate(center_cities, 1):
        if len(results) >= per_country:
            break
        city_name = city.get("name", "Unknown")
        lat = float(city.get("latitude"))
        lon = float(city.get("longitude"))
        lat_delta = 0.09
        lon_delta = 0.09 / max(0.1, abs((math.cos(math.radians(lat)))))
        bbox = (lat - lat_delta, lon - lon_delta, lat + lat_delta, lon + lon_delta)
        if verbose:
            print(f"  📍 City {city_idx}/{len(center_cities)}: {city_name} ({lat:.4f}, {lon:.4f})")
        nodes = fetch_nodes_from_overpass_bbox(bbox, verbose=verbose)
        stats["overpass_queries"] += 1
        stats["nodes_fetched"] += len(nodes)
        
        nodes = prioritize_nodes(nodes)
        
        if verbose:
            print(f"     🔄 Processing {len(nodes)} nodes from {city_name} (prioritized by addr:housenumber)...")
        
        processed = 0
        for n in nodes:
            if len(results) >= per_country:
                break
            
            element_id = n.get("id")
            if element_id in tried_nodes:
                stats["duplicates_skipped"] += 1
                if verbose and processed % 50 == 0:
                    print(f"     ⚠️  Duplicate element {element_id} (already tried)")
            else:
                tried_nodes.add(element_id)
            
            processed += 1
            
            if USE_LOCAL_NODES_ONLY or country in DISABLE_REVERSE_COUNTRIES:
                tags = n.get("tags", {}) or {}
                display = node_tags_to_display_name(tags, country)
                if not display:
                    stats["validation_failed"] += 1
                    continue
                
                # Validate with all 3 checks first
                is_valid, address_dict = validate_address_complete(display, country, verbose=verbose and processed % 5 == 0)
                
                if is_valid:
                    # Check duplicate AFTER validation (4th level - normalized address check)
                    # Use normalized_address from address_dict (already normalized in validate_address_complete)
                    normalized = address_dict.get("normalized_address", "")
                    if normalized in normalized_addresses_seen:
                        stats["duplicates_skipped"] += 1
                        if verbose and processed % 10 == 0:
                            print(f"     ⚠️  SKIPPING (normalized address already seen): {display[:60]}...")
                        continue
                    
                    # Add to results and track normalized address
                    normalized_addresses_seen.add(normalized)
                    results.append(address_dict)
                    stats["validation_passed"] += 1
                    stats["local_validations"] += 1
                    if verbose:
                        print(f"     ✅✅✅ ACCEPTED (all 4 checks passed, score: {address_dict['score']:.4f}, {len(results)}/{per_country}): {display[:80]}...")
                    time.sleep(NOMINATIM_SLEEP)
                    continue
                else:
                    stats["validation_failed"] += 1
                    if verbose and processed % 10 == 0:
                        print(f"     ❌ REJECTED (failed one or more validation checks): {display[:60]}...")
                    continue
        
        if verbose:
            print(f"     📊 {city_name} summary: {processed} processed, {len(results)}/{per_country} accepted so far")

    # Print final statistics
    if verbose:
        print(f"\n  📊 FINAL STATISTICS for {country}:")
        print(f"     ✅ Accepted: {len(results)}/{per_country} addresses")
        print(f"     📡 Overpass queries: {stats['overpass_queries']}")
        print(f"     📦 Nodes fetched: {stats['nodes_fetched']}")
        print(f"     🏠 Local validations: {stats['local_validations']}")
        print(f"     ✅ Validation passed: {stats['validation_passed']}")
        print(f"     ❌ Validation failed: {stats['validation_failed']}")
        print(f"     🔁 Duplicates skipped: {stats['duplicates_skipped']}")
        print()

    return results

# Global variables for signal handling
_cache_save_lock = False
_current_address_cache = None
_current_failed_countries = None
_current_cache_file = None

def save_cache_safely(address_cache: dict, failed_countries: list, cache_file: str, total_countries: int, force: bool = False):
    """Safely save cache to disk with error handling and backup."""
    global _cache_save_lock
    if _cache_save_lock and not force:
        return False
    
    _cache_save_lock = True
    try:
        if os.path.exists(cache_file):
            backup_file = cache_file + ".backup"
            try:
                shutil.copy2(cache_file, backup_file)
            except Exception:
                pass
        
        cache_data = {
            "addresses": address_cache,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_countries": total_countries,
            "cached_countries": len(address_cache),
            "failed_countries": failed_countries
        }
        
        temp_file = cache_file + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
        
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
    global _current_address_cache, _current_failed_countries, _current_cache_file
    print("\n\n  ⚠️  Interrupt signal received (Ctrl+C)")
    if _current_address_cache is not None:
        print("  💾 Saving cache before exit...")
        total_countries = len(_current_address_cache) + 50
        if _current_cache_file and os.path.exists(_current_cache_file):
            try:
                with open(_current_cache_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                    total_countries = existing.get("total_countries", total_countries)
            except Exception:
                pass
        
        save_cache_safely(_current_address_cache, _current_failed_countries or [], 
                         _current_cache_file or CACHE_FILE, total_countries, force=True)
        print(f"  ✅ Cache saved: {len(_current_address_cache)} countries")
    print("  👋 Exiting gracefully...")
    sys.exit(0)

def generate_address_cache(force_reprocess: bool = False):
    """Main orchestrator function."""
    global _current_address_cache, _current_failed_countries, _current_cache_file
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    gc = geonamescache.GeonamesCache()

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

    address_cache = {}
    failed_countries = []
    cache_file_path = os.path.abspath(CACHE_FILE)
    print(f"📂 Cache file path: {cache_file_path}")
    print(f"🆕 Starting completely fresh - new cache location: validated_address_cache_fresh_psd.json")
    
    if os.path.exists(CACHE_FILE):
        try:
            file_size = os.path.getsize(CACHE_FILE)
            print(f"📦 Cache file exists ({file_size:,} bytes)")
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
                address_cache = existing.get("addresses", {}) or {}
                failed_countries = existing.get("failed_countries", []) or []
                complete = len([c for c in address_cache.keys() if len(address_cache[c]) >= 15])
                partial = len(address_cache) - complete
                print(f"🔁 Resuming from existing cache: {len(address_cache)} countries cached ({complete} complete, {partial} partial)")
                if len(address_cache) > 0:
                    sample_countries = list(address_cache.keys())[:5]
                    print(f"   📋 Sample cached countries: {', '.join(sample_countries)}")
        except json.JSONDecodeError as e:
            print(f"⚠️ Cache file is corrupted (invalid JSON): {e}")
            backup_file = CACHE_FILE + ".backup"
            if os.path.exists(backup_file):
                try:
                    print(f"   🔄 Attempting to load from backup: {backup_file}")
                    with open(backup_file, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                        address_cache = existing.get("addresses", {}) or {}
                        failed_countries = existing.get("failed_countries", []) or []
                        print(f"   ✅ Loaded {len(address_cache)} countries from backup")
                except Exception as e2:
                    print(f"   ⚠️ Could not load backup either: {e2}")
        except Exception as e:
            print(f"⚠️ Could not load existing cache: {e}")
            import traceback
            print(f"   Traceback: {traceback.format_exc()}")
    else:
        print(f"📝 No existing cache file found - starting fresh")
    
    _current_address_cache = address_cache
    _current_failed_countries = failed_countries
    _current_cache_file = CACHE_FILE

    total_countries = len(valid_countries)
    complete_countries = [c for c in address_cache.keys() if len(address_cache[c]) >= 15]
    partial_countries = [c for c in address_cache.keys() if len(address_cache[c]) < 15]
    remaining_countries = [c for c in valid_countries 
                           if c not in address_cache or len(address_cache.get(c, [])) < 15]
    start_time = time.time()
    
    failed_countries_set = set(failed_countries)
    
    print("\n" + "="*80)
    print("ADDRESS CACHE GENERATION STARTED")
    print("="*80)
    print(f"Total countries: {total_countries}")
    print(f"Already cached (complete): {len(complete_countries)} countries with 15+ addresses")
    print(f"Already cached (partial): {len(partial_countries)} countries with < 15 addresses")
    print(f"Remaining to process: {len(remaining_countries)}")
    if failed_countries_set:
        print(f"Countries to skip (failed previously): {len(failed_countries_set)} countries")
        print(f"   {', '.join(sorted(failed_countries_set))}")
    print(f"Cache file: {CACHE_FILE}")
    print("="*80 + "\n")

    for idx, country in enumerate(valid_countries, 1):
        if country in failed_countries_set:
            print(f"[{idx}/{total_countries}] ⏭️  SKIP (failed previously): {country}")
            continue
        
        if not force_reprocess and country in address_cache and len(address_cache[country]) >= 15:
            print(f"[{idx}/{total_countries}] ⏭️  SKIP (cached): {country} ({len(address_cache[country])}/15 addresses)")
            continue
        elif force_reprocess and country in address_cache and len(address_cache[country]) >= 15:
            print(f"[{idx}/{total_countries}] 🔄 RE-PROCESSING (--force): {country} (existing: {len(address_cache[country])}/15 addresses)")
        
        country_start_time = time.time()
        print("\n" + "="*80)
        print(f"[{idx}/{total_countries}] 🏳️  PROCESSING COUNTRY: {country}")
        print(f"Started at: {time.strftime('%H:%M:%S')}")
        print("="*80)

        try:
            addresses = generate_addresses_for_country(country, per_country=15, verbose=True, existing_cache=address_cache)
        except KeyboardInterrupt:
            print(f"\n  ⚠️  Interrupted by user")
            print("  💾 Saving cache before exit...")
            _current_address_cache = address_cache
            _current_failed_countries = failed_countries
            if save_cache_safely(address_cache, failed_countries, CACHE_FILE, total_countries, force=True):
                print(f"  ✅ Cache saved: {len(address_cache)} countries")
            raise
        except Exception as e:
            import traceback
            print(f"  ❌ Error generating for {country}: {type(e).__name__}: {e}")
            print(f"  Traceback: {traceback.format_exc()}")
            addresses = []

        country_elapsed = time.time() - country_start_time
        if len(addresses) >= 15:
            address_cache[country] = addresses[:15]
            print(f"\n  ✅ COUNTRY COMPLETED: {country} ({len(addresses[:15])}/15 addresses in {country_elapsed:.1f}s)")
        else:
            failed_countries.append(country)
            address_cache[country] = addresses
            print(f"\n  ❌ COUNTRY FAILED: {country} ({len(addresses)}/15 addresses in {country_elapsed:.1f}s)")

        _current_address_cache = address_cache
        _current_failed_countries = failed_countries
        
        if save_cache_safely(address_cache, failed_countries, CACHE_FILE, total_countries):
            print(f"   💾 Cache saved incrementally ({len(address_cache)}/{total_countries} countries)")
        else:
            print(f"   ⚠️ Failed to save cache (check permissions)")

        elapsed_total = time.time() - start_time
        remaining = len([c for c in valid_countries[idx:] 
                        if c not in address_cache or len(address_cache.get(c, [])) < 15])
        avg_time_per_country = elapsed_total / idx if idx > 0 else 0
        estimated_remaining = avg_time_per_country * remaining if remaining > 0 else 0
        
        print(f"   ⏱️  Progress: {idx}/{total_countries} countries | "
              f"Elapsed: {elapsed_total/60:.1f}m | "
              f"Avg: {avg_time_per_country:.1f}s/country | "
              f"Est. remaining: {estimated_remaining/60:.1f}m")

        time.sleep(0.5)

    overall_elapsed = time.time() - start_time
    
    total_addresses = sum(len(addrs) for addrs in address_cache.values())
    complete_countries = len([c for c in address_cache.keys() if len(address_cache[c]) >= 15])
    partial_countries = len(address_cache) - complete_countries
    
    print("\n" + "="*80)
    print("🎉 ALL DONE - FINAL SUMMARY")
    print("="*80)
    print(f"⏱️  Total time elapsed: {overall_elapsed/60:.1f} minutes ({overall_elapsed:.0f} seconds)")
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
    if failed_countries:
        print(f"\n⚠️  Failed countries ({len(failed_countries)}):")
        for fc in failed_countries[:10]:
            print(f"   - {fc} ({len(address_cache.get(fc, []))} addresses)")
        if len(failed_countries) > 10:
            print(f"   ... and {len(failed_countries) - 10} more")
    print("="*80)

    return CACHE_FILE

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate validated address cache for all countries")
    parser.add_argument("--force", action="store_true", 
                       help="Force re-processing of countries that already have 15+ addresses")
    args = parser.parse_args()
    generate_address_cache(force_reprocess=args.force)

