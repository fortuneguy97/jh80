#!/usr/bin/env python3
"""
Standalone test script for Afghanistan addresses
Copies all validation methods from rewards.py without modifying it
"""

import os
import sys
import re
import math
import time
import requests
import geonamescache
from typing import Union

# ============================================================================
# COPIED CONSTANTS AND MAPPINGS
# ============================================================================

COUNTRY_MAPPING = {
    # Korea variations
    "korea, south": "south korea",
    "korea, north": "north korea",
    
    # Cote d'Ivoire variations
    "cote d ivoire": "ivory coast",
    "côte d'ivoire": "ivory coast",
    "cote d'ivoire": "ivory coast",
    
    # Gambia variations
    "the gambia": "gambia",
    
    # Netherlands variations
    "netherlands": "the netherlands",
    "holland": "the netherlands",
    
    # Congo variations
    "congo, democratic republic of the": "democratic republic of the congo",
    "drc": "democratic republic of the congo",
    "congo, republic of the": "republic of the congo",
    
    # Burma/Myanmar variations
    "burma": "myanmar",

    # Bonaire variations
    'bonaire': 'bonaire, saint eustatius and saba',
    
    # Additional common variations
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

# ============================================================================
# COPIED VALIDATION FUNCTIONS
# ============================================================================

def looks_like_address(address: str) -> bool:
    """Copied from rewards.py"""
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
    
    # Check for special characters
    special_chars = ['`', ':', '%', '$', '@', '*', '^', '[', ']', '{', '}', '_', '«', '»']
    if any(char in address for char in special_chars):
        return False
    
    return True


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


def city_in_country(city_name: str, country_name: str) -> bool:
    """Copied from rewards.py"""
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
            # Skip cities not in the target country
            if city_data.get("countrycode", "") != country_code:
                continue
                
            city_data_name = city_data.get("name", "").lower()
            
            # Check exact match first
            if city_data_name.strip() == city_name_lower.strip():
                return True
            # Check first word match
            elif len(city_words) >= 2 and city_data_name.startswith(city_words[0]):
                return True
            # Check second word match
            elif len(city_words) >= 2 and city_words[1] in city_data_name:
                return True
        
        return False
        
    except Exception as e:
        print(f"Error checking city '{city_name}' in country '{country_name}': {str(e)}")
        return False


def extract_city_country(address: str, two_parts: bool = False) -> tuple:
    """Copied from rewards.py"""
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
    """Copied from rewards.py"""
    if not generated_address or not seed_address:
        return False
    
    # Special handling for disputed regions
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
    
    city_match = gen_city and seed_address_lower and gen_city == seed_address_lower
    country_match = gen_country and seed_address_lower and gen_country == seed_address_lower
    mapped_match = gen_country and seed_address_mapped and gen_country == seed_address_mapped
    
    if not (city_match or country_match or mapped_match):
        return False
    
    return True


def compute_bounding_box_areas_meters(nominatim_results):
    """Copied from rewards.py"""
    if not isinstance(nominatim_results, list):
        return []
    
    areas = []
    for item in nominatim_results:
        if "boundingbox" not in item:
            continue
        
        south, north, west, east = map(float, item["boundingbox"])
        
        center_lat = (south + north) / 2.0
        lat_m = 111_000
        lon_m = 111_000 * math.cos(math.radians(center_lat))
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


def check_with_nominatim(address: str, validator_uid: int, miner_uid: int, seed_address: str, seed_name: str) -> Union[float, str, dict]:
    """
    Copied from rewards.py but with configurable Nominatim URL
    """
    try:
        # CONFIGURABLE NOMINATIM URL (can be set via environment variable)
        nominatim_base_url = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org")
        url = f"{nominatim_base_url}/search"
        params = {"q": address, "format": "json"}
        
        default_user_agent = "MIIDSubnet/1.0 (contact: prasadpsd2001@gmail.com)"
        user_agent = os.getenv("USER_AGENT", default_user_agent)
        
        proxy_url = os.getenv("PROXY_URL", None)
        proxies = None
        if proxy_url:
            proxies = {
                "http": proxy_url,
                "https": proxy_url
            }
        verify_ssl = proxy_url is None
        response = requests.get(url, params=params, headers={"User-Agent": user_agent}, timeout=5, proxies=proxies, verify=verify_ssl)
        
        if response.status_code != 200:
            if response.status_code == 403:
                print(f"⚠️  Nominatim 403 Forbidden for address '{address}' - rate limited or blocked")
            else:
                print(f"⚠️  Nominatim HTTP {response.status_code} for address '{address}'")
            return 0.0
        
        results = response.json()
        
        if len(results) == 0:
            return 0.0
        
        original_numbers = set(re.findall(r"[0-9]+", address.lower()))
        
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
        
        areas_data = compute_bounding_box_areas_meters(results)
        
        if len(areas_data) == 0:
            return 0.0
        
        areas = [item["area_m2"] for item in areas_data]
        min_area = min(areas)
        
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
        print(f"⚠️  API timeout for address: {address}")
        return "TIMEOUT"
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Request exception for address '{address}': {type(e).__name__}: {str(e)}")
        return 0.0
    except Exception as e:
        print(f"⚠️  Error for address '{address}': {type(e).__name__}: {str(e)}")
        return 0.0


# ============================================================================
# TEST ADDRESSES
# ============================================================================

ADDRESSES_TO_TEST = [
    "12, Darulaman Road, Kabul, 1003, Afghanistan",
    "34, Karte Parwan Street, Kabul, 1005, Afghanistan",
    "7, Chicken Street, Kabul, 1009, Afghanistan",
    "Ariana Hotel, Shahre Now, Kabul, 1006, Afghanistan",
    "45, Wazir Akbar Khan Road, Kabul, 1007, Afghanistan",
    "6, Flower Street, Shar-e-Naw, Kabul, 1006, Afghanistan",
    "Ministry of Education, Pashtunistan Watt, Kabul, 1001, Afghanistan",
    "101, Macrorayan Roundabout, Kabul, 1004, Afghanistan",
    "88, Street 2, Karte Seh, Kabul, 1008, Afghanistan",
    "3, Jalalabad Road, Kabul, 1002, Afghanistan",
    "22, Taimani Street, Kabul, 1009, Afghanistan",
    "17, Bagh-e Bala Road, Kabul, 1003, Afghanistan",
    "French Cultural Center, Shahr-e Naw, Kabul, 1006, Afghanistan",
    "56, Qalai-Fathullah Street, Kabul, 1002, Afghanistan",
    "199, Darulaman Palace Road, Kabul, 1003, Afghanistan",
    "8, Ansari Watt, Kabul, 1007, Afghanistan",
    "27, Kart-e-Char, Kabul, 1008, Afghanistan",
    "5, Karta-e-Now Bridge Road, Kabul, 1006, Afghanistan",
    "Sultani Hospital, District 3, Kabul, 1002, Afghanistan",
    "14, University Road, Kabul, 1004, Afghanistan",
    "9, Tapa-e-Mardan, Herat, 7001, Afghanistan",
    "33, Ahmad Shah Baba Mina, Herat, 7002, Afghanistan",
    "Blue Mosque, Herat Old City, Herat, 7001, Afghanistan",
    "70, Malikzada Street, Herat, 7003, Afghanistan",
    "Central Hospital, Char-Rahi Herat, Herat, 7001, Afghanistan",
    "4, Sultani Watt, Herat, 7002, Afghanistan",
    "165, Road 7, Herat Industrial Area, Herat, 7004, Afghanistan",
    "12, Pul-e-Khushk, Mazar-e-Sharif, 1701, Afghanistan",
    "Blue Mosque Rd, Mazar-e-Sharif, 1701, Afghanistan",
    "55, Balkh Street, Mazar-e-Sharif, 1702, Afghanistan",
    "8, Adina Market Street, Mazar-e-Sharif, 1703, Afghanistan",
    "Balkh University, Sholgara Road, Mazar-e-Sharif, 1701, Afghanistan",
    "21, Taloqan Road, Kunduz, 3501, Afghanistan",
    "Kunduz Regional Hospital, Kunduz City, Kunduz, 3501, Afghanistan",
    "3, City Center Road, Kunduz, 3502, Afghanistan",
    "48, Kandahar Road, Lashkar Gah, Helmand, 3801, Afghanistan",
    "Provincial Hospital, Lashkar Gah, Helmand, 3801, Afghanistan",
    "9, Kandahar Bazaar Road, Kandahar, 3802, Afghanistan",
    "Kandahar University Campus, Kandahar, 3803, Afghanistan",
    "125, Shahid Street, Kandahar, 3802, Afghanistan",
    "16, Jalalabad Main Road, Jalalabad, Nangarhar, 3101, Afghanistan",
    "Nangarhar Provincial Hospital, Jalalabad, Nangarhar, 3101, Afghanistan",
    "7, Torkham Road, Jalalabad, Nangarhar, 3102, Afghanistan",
    "44, Ghazi Road, Ghazni City, Ghazni, 2301, Afghanistan",
    "Ghazni University, Central Ghazni, Ghazni, 2301, Afghanistan",
    "2, Bamiyan Road, Bamiyan, 2101, Afghanistan",
    "Buddhas Viewpoint, Bamiyan Valley, Bamiyan, 2101, Afghanistan",
    "88, Charikar Road, Parwan, Charikar, 1501, Afghanistan",
    "Parwan District Hospital, Charikar, Parwan, 1501, Afghanistan",
    "39, Pul-e-Khumri Street, Baghlan, 2201, Afghanistan",
    "11, Fayzabad Road, Badakhshan, Fayzabad, 3401, Afghanistan",
    "101, Qala-e-Now Road, Herat, 7002, Afghanistan",
    "66, Shah Faisal Street, Kabul, 1007, Afghanistan",
    "50, Cinema Street, Kabul, 1006, Afghanistan",
    "Serai Restaurant, Kart-e-Char, Kabul, 1008, Afghanistan",
    "3, Police HQ Road, Kandahar, 3802, Afghanistan",
    "Green Market, Mazar-e-Sharif, Balkh, 1701, Afghanistan",
    "90, Stadium Road, Kandahar, 3803, Afghanistan",
    "24, Dawoodkhil Lane, Kabul, 1002, Afghanistan",
    "200, Airport Road, Kabul International, Kabul, 1003, Afghanistan",
    "17, Sayed Jamal Road, Herat, 7001, Afghanistan",
    "5, Old Bazaar Lane, Herat, 7001, Afghanistan",
    "60, University Ave, Mazar-e-Sharif, 1702, Afghanistan",
    "2, Police Station Road, Kunduz, 3502, Afghanistan",
    "73, Industrial Road, Kandahar, 3803, Afghanistan",
    "29, Shuhada Street, Jalalabad, Nangarhar, 3102, Afghanistan",
    "8, New Market Street, Herat, 7002, Afghanistan",
    "14, Hospital Road, Mazar-e-Sharif, 1701, Afghanistan",
    "Afghan Bank Branch, Shahre Now, Kabul, 1006, Afghanistan",
    "6, Embassy Quarter Road, Kabul, 1007, Afghanistan",
    "Royal Guest House, Wazir Akbar Khan, Kabul, 1007, Afghanistan",
    "21, Khost Main Road, Khost City, Khost, 2501, Afghanistan",
    "Provincial Governor Office, Khost, 2501, Afghanistan",
    "11, Gardez Road, Paktia, Gardez, 2401, Afghanistan",
    "Paktia District Hospital, Gardez, Paktia, 2401, Afghanistan",
    "5, Lashkari Bazar, Zaranj, Nimruz, 4601, Afghanistan",
    "Zaranj Customs Office, Zaranj, Nimruz, 4601, Afghanistan",
    "19, Sheberghan Rd, Jawzjan, Sheberghan, 1601, Afghanistan",
    "Sheberghan Clinic, Sheberghan, Jawzjan, 1601, Afghanistan",
    "36, Pol-e Khomri Avenue, Baghlan, 2201, Afghanistan",
    "7, Qala-e- Zal Road, Kunduz, 3501, Afghanistan",
    "4, Flower Market Street, Kabul, 1006, Afghanistan",
    "55, Civil Hospital Road, Herat, 7001, Afghanistan",
    "Ariana Cinema, Shahr-e Naw, Kabul, 1006, Afghanistan",
    "102, University Road, Herat, 7002, Afghanistan",
    "14, Market Lane, Mazar-e-Sharif, 1703, Afghanistan",
    "67, Industrial Park Rd, Kandahar, 3803, Afghanistan",
    "8, Riverbank Street, Jalalabad, 3101, Afghanistan",
    "42, Police Crossing, Kabul, 1004, Afghanistan",
    "3, New Kabul-Charikar Highway, Kabul, 1002, Afghanistan",
    "20, Shahid Square, Herat, 7001, Afghanistan",
    "5, University Gate Road, Kabul University, Kabul, 1004, Afghanistan",
    "88, Hotel Avenue, Mazar-e-Sharif, 1702, Afghanistan",
    "9, Central Bazaar Road, Kandahar, 3802, Afghanistan",
    "34, Airport Service Road, Herat, 7003, Afghanistan",
    "12, Old City Lane, Balkh, Mazar-e-Sharif, 1701, Afghanistan",
    "46, Healthcare Rd, Jalalabad, 3102, Afghanistan",
    "77, Police Parade Road, Kandahar, 3802, Afghanistan",
    "1, Presidential Garden Road, Kabul, 1003, Afghanistan",
    "250, National Highway 1 (ring), Kandahar, 3803, Afghanistan",
]


# ============================================================================
# TEST FUNCTION
# ============================================================================

def test_addresses():
    """Test all addresses with validation functions"""
    
    seed_address = "Afghanistan"
    seed_name = "Test"
    validator_uid = 101
    miner_uid = 501
    
    # Check which Nominatim instance is being used
    nominatim_url = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org")
    API_SLEEP = 1.0
    
    print("=" * 80)
    print("TESTING AFGHANISTAN ADDRESSES (STANDALONE)")
    print("=" * 80)
    print(f"Using Nominatim instance: {nominatim_url}")
    print(f"Total addresses to test: {len(ADDRESSES_TO_TEST)}")
    print(f"Sleep between API calls: {API_SLEEP}s")
    print()
    
    results = {
        "total": len(ADDRESSES_TO_TEST),
        "looks_like_address_pass": 0,
        "region_validation_pass": 0,
        "api_validation_pass": 0,
        "all_pass": 0,
        "details": []
    }
    
    for idx, addr in enumerate(ADDRESSES_TO_TEST, 1):
        print(f"[{idx}/{len(ADDRESSES_TO_TEST)}] Testing: {addr[:60]}...")
        
        # Test 1: looks_like_address
        looks_like = looks_like_address(addr)
        if looks_like:
            results["looks_like_address_pass"] += 1
        
        # Test 2: validate_address_region
        region_valid = False
        if looks_like:
            region_valid = validate_address_region(addr, seed_address)
            if region_valid:
                results["region_validation_pass"] += 1
        
        # Test 3: API validation (only if first two pass)
        api_score = None
        api_valid = False
        if looks_like and region_valid:
            try:
                time.sleep(API_SLEEP)
                
                api_result = check_with_nominatim(
                    address=addr,
                    validator_uid=validator_uid,
                    miner_uid=miner_uid,
                    seed_address=seed_address,
                    seed_name=seed_name
                )
                
                if isinstance(api_result, dict):
                    api_score = api_result.get('score', 0.0)
                    api_valid = api_score >= 0.9
                elif isinstance(api_result, (int, float)):
                    api_score = api_result
                    api_valid = api_score >= 0.9
                else:
                    api_score = 0.0
                
                if api_valid:
                    results["api_validation_pass"] += 1
            except Exception as e:
                api_score = f"ERROR: {e}"
        
        # Check if all pass
        all_pass = looks_like and region_valid and api_valid
        
        if all_pass:
            results["all_pass"] += 1
        
        # Store details
        result_detail = {
            "address": addr,
            "looks_like": looks_like,
            "region_valid": region_valid,
            "api_score": api_score,
            "api_valid": api_valid,
            "all_pass": all_pass
        }
        results["details"].append(result_detail)
        
        # Print result
        status = "✅" if all_pass else "❌"
        print(f"  {status} Looks like address: {looks_like}, Region: {region_valid}, API: {api_score if api_score is not None else 'N/A'}")
        print()
    
    # Print summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total addresses: {results['total']}")
    print(f"✅ Looks like address: {results['looks_like_address_pass']}/{results['total']} ({results['looks_like_address_pass']/results['total']*100:.1f}%)")
    print(f"✅ Region validation: {results['region_validation_pass']}/{results['total']} ({results['region_validation_pass']/results['total']*100:.1f}%)")
    print(f"✅ API validation (score >= 0.9): {results['api_validation_pass']}/{results['total']} ({results['api_validation_pass']/results['total']*100:.1f}%)")
    print(f"✅ All validations pass: {results['all_pass']}/{results['total']} ({results['all_pass']/results['total']*100:.1f}%)")
    print()
    
    # Print addresses that pass all validations
    print("=" * 80)
    print("ADDRESSES THAT PASS ALL VALIDATIONS (score >= 0.9)")
    print("=" * 80)
    valid_addresses = [r["address"] for r in results["details"] if r["all_pass"]]
    if valid_addresses:
        for addr in valid_addresses:
            print(f"✅ {addr}")
    else:
        print("❌ No addresses passed all validations")
    print()
    
    return results


if __name__ == "__main__":
    # Allow setting Nominatim URL via environment variable
    # Example: export NOMINATIM_URL="http://localhost:8080"
    # Or uncomment one of these:
    # os.environ["NOMINATIM_URL"] = "https://nominatim.openstreetmap.org"  # Official
    # os.environ["NOMINATIM_URL"] = "http://localhost:8080"  # Self-hosted
    
    results = test_addresses()

