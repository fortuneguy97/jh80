#!/usr/bin/env python3
"""
Standalone address validation functions from rewards.py
Complete code to evaluate addresses.
"""

import re
import math
import time
import random
import requests
import geonamescache
from typing import Dict, List, Tuple, Union, Any, Optional

# Global country name mapping to handle variations between miner submissions and geonames data
COUNTRY_MAPPING = {
    "korea, south": "south korea",
    "korea, north": "north korea",
    "cote d ivoire": "ivory coast",
    "côte d'ivoire": "ivory coast",
    "cote d'ivoire": "ivory coast",
    "the gambia": "gambia",
    "netherlands": "the netherlands",
    "holland": "the netherlands",
    "congo, democratic republic of the": "democratic republic of the congo",
    "drc": "democratic republic of the congo",
    "congo, republic of the": "republic of the congo",
    "burma": "myanmar",
    'bonaire': 'bonaire, saint eustatius and saba',
    "usa": "united states",
    "us": "united states",
    "united states of america": "united states",
    "uk": "united kingdom",
    "great britain": "united kingdom",
    "britain": "united kingdom",
    "uae": "united arab emirates",
    "u.s.a.": "united states",
    "u.s.": "united states",
    "u.k.": "united kingdom",
}

# Global cache for geonames data
_geonames_cache = None
_cities_data = None
_countries_data = None

def get_geonames_data():
    """Get cached geonames data, loading it only once."""
    global _geonames_cache, _cities_data, _countries_data
    
    if _geonames_cache is None:
        print("Loading geonames data for the first time...")
        start_time = time.time()
        _geonames_cache = geonamescache.GeonamesCache()
        _cities_data = _geonames_cache.get_cities()
        _countries_data = _geonames_cache.get_countries()
        end_time = time.time()
        print(f"Geonames data loaded in {end_time - start_time:.2f} seconds")
    
    return _cities_data, _countries_data

def looks_like_address(address: str) -> bool:
    address = address.strip().lower()

    # Keep all letters (Latin and non-Latin) and numbers
    address_len = re.sub(r'[^\w]', '', address.strip(), flags=re.UNICODE)
    if len(address_len) < 30:
        return False
    if len(address_len) > 300:
        return False

    # Count letters (both Latin and non-Latin)
    letter_count = len(re.findall(r'[^\W\d]', address, flags=re.UNICODE))
    if letter_count < 20:
        return False

    if re.match(r"^[^a-zA-Z]*$", address):
        return False
    if len(set(address)) < 5:
        return False
        
    # Has at least one digit in a comma-separated section
    address_for_number_count = address.replace('-', '').replace(';', '')
    sections = [s.strip() for s in address_for_number_count.split(',')]
    sections_with_numbers = []
    for section in sections:
        number_groups = re.findall(r"[0-9]+", section)
        if len(number_groups) > 0:
            sections_with_numbers.append(section)
    if len(sections_with_numbers) < 1:
        return False

    if address.count(",") < 2:
        return False
    
    # Check for special characters that should not be in addresses
    special_chars = ['`', ':', '%', '$', '@', '*', '^', '[', ']', '{', '}', '_', '«', '»']
    if any(char in address for char in special_chars):
        return False
    
    return True

def compute_bounding_box_areas_meters(nominatim_results):
    """
    Computes bounding box areas in meters instead of degrees.
    """
    if not isinstance(nominatim_results, list):
        return []
    
    areas = []
    for item in nominatim_results:
        if "boundingbox" not in item:
            continue
        
        # Extract and convert bounding box coords to floats
        south, north, west, east = map(float, item["boundingbox"])
        
        # Approx center latitude for longitude scaling
        center_lat = (south + north) / 2.0
        lat_m = 111_000  # meters per degree latitude
        lon_m = 111_000 * math.cos(math.radians(center_lat))  # meters per degree longitude
        height_m = abs(north - south) * lat_m
        width_m = abs(east - west) * lon_m
        area_m2 = width_m * height_m
        
        areas.append({
            "south": south,
            "north": north,
            "west": west,
            "east": east,
            "width_m": width_m,
            "height_m": height_m,
            "area_m2": area_m2,
            "result": item
        })
    
    return areas

def check_with_nominatim(address: str, validator_uid: int, miner_uid: int, seed_address: str, seed_name: str, proxies: Optional[Dict[str, str]] = None) -> Union[float, str, dict]:
    """
    Validates address using Nominatim API and returns a score based on bounding box areas.
    Returns: dict with 'score' and 'details' for success, "TIMEOUT" for timeout, or 0.0 for failure
    
    Args:
        proxies: Optional dict with 'http' and 'https' proxy URLs (e.g., {'http': 'http://proxy:port', 'https': 'https://proxy:port'})
    """
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": address, "format": "json"}
        
        user_agent = f"YanezCompliance/{validator_uid} (https://yanezcompliance.com; omar@yanezcompliance.com)"
        
        # Use proxies if provided, otherwise check environment variables
        if proxies is None:
            proxies = {}
            import os
            if os.getenv('HTTP_PROXY'):
                proxies['http'] = os.getenv('HTTP_PROXY')
            if os.getenv('HTTPS_PROXY'):
                proxies['https'] = os.getenv('HTTPS_PROXY')
            if not proxies:
                proxies = None
        
        response = requests.get(url, params=params, headers={"User-Agent": user_agent}, timeout=5, proxies=proxies)
        results = response.json()
        
        if len(results) == 0:
            return 0.0
        
        # Extract numbers from the original address for matching
        original_numbers = set(re.findall(r"[0-9]+", address.lower()))
        
        # Filter results based on place_rank, name check, and numbers check
        filtered_results = []
        for result in results:
            place_rank = result.get('place_rank', 0)
            if place_rank < 20:
                continue
            
            name = result.get('name', '')
            if name:
                if name.lower() not in address.lower():
                    continue
            
            display_name = result.get('display_name', '')
            if display_name:
                display_numbers = set(re.findall(r"[0-9]+", display_name.lower()))
                if original_numbers:
                    if display_numbers and not display_numbers.issubset(original_numbers):
                        continue
            
            filtered_results.append(result)
        
        if len(filtered_results) == 0:
            return 0.0
        
        # Calculate bounding box areas for all results
        areas_data = compute_bounding_box_areas_meters(results)
        
        if len(areas_data) == 0:
            return 0.0
        
        # Extract areas
        areas = [item["area_m2"] for item in areas_data]
        
        # Use the smallest area for scoring
        min_area = min(areas)
        
        # Score based on smallest area
        if min_area < 100:
            score = 1.0
        elif min_area < 1000:
            score = 0.9
        elif min_area < 10000:
            score = 0.8
        elif min_area < 100000:
            score = 0.7
        else:
            score = 0.3
        
        score_details = {
            "score": score,
            "areas": areas,
            "min_area": min_area,
            "num_results": len(areas),
            "areas_data": areas_data
        }
        
        return score_details
    except requests.exceptions.Timeout:
        print(f"API timeout for address: {address}")
        return "TIMEOUT"
    except requests.exceptions.RequestException as e:
        print(f"Request exception for address '{address}': {type(e).__name__}: {str(e)}")
        return 0.0
    except ValueError as e:
        error_msg = str(e)
        if "codec" in error_msg.lower() and "encode" in error_msg.lower():
            print(f"Encoding error for address '{address}' (treating as timeout): {error_msg}")
            return "TIMEOUT"
        else:
            print(f"ValueError (likely JSON parsing) for address '{address}': {error_msg}")
            return 0.0
    except Exception as e:
        print(f"Unexpected exception for address '{address}': {type(e).__name__}: {str(e)}")
        return 0.0

def city_in_country(city_name: str, country_name: str) -> bool:
    """
    Check if a city is actually in the specified country using geonamescache.
    """
    if not city_name or not country_name:
        return False
    
    try:
        cities, countries = get_geonames_data()
        
        city_name_lower = city_name.lower()
        country_name_lower = country_name.lower()
        
        # Find country code
        country_code = None
        for code, data in countries.items():
            if data.get('name', '').lower().strip() == country_name_lower.strip():
                country_code = code
                break
        
        if not country_code:
            return False
        
        # Only check cities that are actually in the specified country
        city_words = city_name_lower.split()
        
        for city_id, city_data in cities.items():
            if city_data.get("countrycode", "") != country_code:
                continue
                
            city_data_name = city_data.get("name", "").lower()
            
            if city_data_name.strip() == city_name_lower.strip():
                return True
            elif len(city_words) >= 2 and city_data_name.startswith(city_words[0]):
                return True
            elif len(city_words) >= 2 and city_words[1] in city_data_name:
                return True
        
        return False
        
    except Exception as e:
        print(f"Error checking city '{city_name}' in country '{country_name}': {str(e)}")
        return False

def extract_city_country(address: str, two_parts: bool = False) -> tuple:
    """
    Extract city and country from an address.
    Country is always the last part.
    City is found by checking each section from right to left (excluding country)
    and validating against geonames data to ensure it's a real city in the country.
    """
    if not address:
        return "", ""

    address = address.lower()
    
    parts = [p.strip() for p in address.split(",")]
    if len(parts) < 2:
        return "", ""

    # Determine country and its normalized form
    last_part = parts[-1]
    single_part_normalized = COUNTRY_MAPPING.get(last_part, last_part)
    
    country_checking_name = ''
    if two_parts and len(parts) >= 2:
        two_part_raw = f"{parts[-2]}, {parts[-1]}"
        two_part_normalized = COUNTRY_MAPPING.get(two_part_raw, two_part_raw)

        if two_part_raw != two_part_normalized:
            country_checking_name = two_part_normalized
            normalized_country = two_part_normalized
            used_two_parts_for_country = True
        else:
            country_checking_name = single_part_normalized
            normalized_country = single_part_normalized
            used_two_parts_for_country = False
    else:
        country_checking_name = single_part_normalized
        normalized_country = single_part_normalized
        used_two_parts_for_country = False

    if not normalized_country:
        return "", ""

    # Check each section from right to left (excluding the country)
    exclude_count = 2 if used_two_parts_for_country else 1
    for i in range(exclude_count + 1, len(parts) + 1):
        candidate_index = -i
        if abs(candidate_index) > len(parts):
            break
        
        candidate_part = parts[candidate_index]
        if not candidate_part:
            continue
            
        words = candidate_part.split()
        
        # Try different combinations of words (1-2 words max)
        for num_words in range(len(words)):
            current_word = words[num_words]

            candidates = [current_word]

            if num_words > 0:
                prev_plus_current = words[num_words - 1] + " " + words[num_words]
                candidates.append(prev_plus_current)

            for city_candidate in candidates:
                if any(char.isdigit() for char in city_candidate):
                    continue

                if city_in_country(city_candidate, country_checking_name):
                    return city_candidate, normalized_country

    return "", normalized_country

def validate_address_region(generated_address: str, seed_address: str) -> bool:
    """
    Validate that generated address has correct region from seed address.
    
    Special handling for disputed regions not in geonames:
    - Luhansk, Crimea, Donetsk, West Sahara
    """
    if not generated_address or not seed_address:
        return False
    
    SPECIAL_REGIONS = ["luhansk", "crimea", "donetsk", "west sahara", 'western sahara']
    
    seed_lower = seed_address.lower()
    if seed_lower in SPECIAL_REGIONS:
        gen_lower = generated_address.lower()
        return seed_lower in gen_lower
    
    # Extract city and country from both addresses
    gen_city, gen_country = extract_city_country(generated_address, two_parts=(',' in seed_address))
    seed_address_lower = seed_address.lower()
    seed_address_mapped = COUNTRY_MAPPING.get(seed_address.lower(), seed_address.lower())
    
    if not gen_city:
        return False
    
    if not gen_country:
        return False
    
    # Check if either city or country matches
    city_match = gen_city and seed_address_lower and gen_city == seed_address_lower
    country_match = gen_country and seed_address_lower and gen_country == seed_address_lower
    mapped_match = gen_country and seed_address_mapped and gen_country == seed_address_mapped
    
    if not (city_match or country_match or mapped_match):
        return False
    
    return True

def _grade_address_variations(variations: Dict[str, List[List[str]]], seed_addresses: List[str], miner_metrics: Dict[str, Any], validator_uid: int, miner_uid: int) -> Dict[str, Any]:
    """Grade address variations - check all with heuristics, one random with API, and region validation."""
    if not seed_addresses or not any(seed_addresses):
        return {"overall_score": 1.0}
    
    # Collect all addresses with their corresponding seed addresses
    all_addresses = []
    address_seed_mapping = []
    for name_idx, name in enumerate(variations.keys()):
        if name in variations and len(variations[name]) >= 1 and name_idx < len(seed_addresses):
            all_variations = variations[name]
            address_variations = [var[2] for var in all_variations if len(var) > 2]
            if address_variations and seed_addresses[name_idx]:
                valid_addrs = [addr for addr in address_variations if addr and addr.strip()]
                all_addresses.extend(valid_addrs)
                seed_addr = seed_addresses[name_idx]
                address_seed_mapping.extend([seed_addr] * len(valid_addrs))
    
    if not all_addresses:
        return {"overall_score": 0.0}
    
    address_breakdown = {
        "seed_addresses": [],
        "variations_by_name": {},
        "validation_results": {},
        "api_validation": {}
    }
    
    # Process each name and validate addresses
    heuristic_perfect = True
    region_matches = 0
    api_validated_addresses = []
    
    for name_idx, name in enumerate(variations.keys()):
        if name not in variations or len(variations[name]) < 1 or name_idx >= len(seed_addresses):
            continue
            
        if not seed_addresses[name_idx]:
            continue
            
        all_variations = variations[name]
        address_variations = [var[2] for var in all_variations if len(var) > 2 and var[2]]
        
        if not address_variations:
            continue
        
        validation_results = []
        seed_addr = seed_addresses[name_idx]
        for i, addr in enumerate(address_variations):
            if not addr or not addr.strip():
                validation_results.append({
                    "address": addr,
                    "seed_address": seed_addr,
                    "looks_like_address": False,
                    "region_match": False,
                    "passed_validation": False,
                    "status": "EMPTY/INVALID"
                })
                heuristic_perfect = False
                continue
                
            looks_like = looks_like_address(addr)
            
            region_match = False
            if looks_like:
                region_match = validate_address_region(addr, seed_addr)
            
            passed_validation = looks_like and region_match
            if not looks_like or not region_match:
                heuristic_perfect = False
            
            if passed_validation:
                api_validated_addresses.append((addr, seed_addr, name))
                region_matches += 1
            
            validation_results.append({
                "address": addr,
                "seed_address": seed_addresses[name_idx],
                "looks_like_address": looks_like,
                "region_match": region_match,
                "passed_validation": passed_validation,
                "status": "PASSED" if passed_validation else "FAILED"
            })
        
        address_breakdown["validation_results"][name] = validation_results
    
    # If first 2 steps fail, return 0 immediately
    if not heuristic_perfect:
        address_breakdown["api_validation"] = {
            "api_result": False,
            "total_eligible_addresses": 0,
            "api_attempts": [],
            "reason": "Heuristic validation failed - no API call made"
        }
        
        return {
            "overall_score": 0.0,
            "heuristic_perfect": False,
            "api_result": False,
            "region_matches": region_matches,
            "total_addresses": len(all_addresses),
            "base_score": 0.0,
            "detailed_breakdown": address_breakdown
        }
    
    # Only call API if all addresses passed first 2 checks
    api_result = False
    api_attempts = []
    nominatim_successful_calls = 0
    nominatim_timeout_calls = 0
    nominatim_failed_calls = 0
    total_calls = 0
    nominatim_scores = []
    
    if api_validated_addresses:
        max_addresses = min(3, len(api_validated_addresses))
        chosen_addresses = random.sample(api_validated_addresses, max_addresses)
        
        nominatim_addresses = chosen_addresses
        
        nominatim_scores = []
        for i, (addr, seed_addr, seed_name) in enumerate(nominatim_addresses):
            result = check_with_nominatim(addr, validator_uid, miner_uid, seed_addr, seed_name)
            
            score = None
            score_details = None
            if isinstance(result, dict) and "score" in result:
                score = result["score"]
                score_details = result
            elif result == "TIMEOUT":
                score = "TIMEOUT"
            else:
                score = result if isinstance(result, (int, float)) else 0.0
            
            api_attempts.append({
                "address": addr,
                "api": "nominatim",
                "result": score,
                "score_details": score_details,
                "attempt": i + 1
            })
            
            if result == "TIMEOUT":
                nominatim_timeout_calls += 1
                time.sleep(1.0)
            elif isinstance(result, dict) and result.get("score", 0) > 0.0:
                nominatim_successful_calls += 1
                nominatim_scores.append(result["score"])
            elif isinstance(result, (int, float)) and result > 0.0:
                nominatim_successful_calls += 1
                nominatim_scores.append(result)
            else:
                nominatim_failed_calls += 1
            
            if i < len(nominatim_addresses) - 1:
                time.sleep(1.0)
        
        total_calls = len(chosen_addresses)
        total_successful = nominatim_successful_calls
        total_timeouts = nominatim_timeout_calls
        total_failed = nominatim_failed_calls
        
        if total_failed > 0:
            api_result = "FAILED"
        elif total_timeouts > 0:
            api_result = "TIMEOUT"
        else:
            api_result = "SUCCESS"
    
    # Scoring based on individual API results
    if nominatim_failed_calls > 0 or len(nominatim_scores) == 0:
        base_score = 0.3
    else:
        base_score = sum(nominatim_scores) / len(nominatim_scores)
    
    address_breakdown["api_validation"] = {
        "api_result": api_result,
        "total_eligible_addresses": len(api_validated_addresses),
        "api_attempts": api_attempts,
        "nominatim_successful_calls": nominatim_successful_calls,
        "nominatim_timeout_calls": nominatim_timeout_calls,
        "nominatim_failed_calls": nominatim_failed_calls,
        "total_calls": total_calls
    }
    
    return {
        "overall_score": base_score,
        "heuristic_perfect": heuristic_perfect,
        "api_result": api_result,
        "region_matches": region_matches,
        "total_addresses": len(all_addresses),
        "base_score": base_score,
        "detailed_breakdown": address_breakdown
    }

