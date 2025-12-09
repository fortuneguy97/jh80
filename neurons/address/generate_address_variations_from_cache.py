#!/usr/bin/env python3
"""
Generate address variations from countries with < 15 addresses in cache.
Uses Nominatim to extract components and generate unique variations.
"""

import json
import requests
import re
import unicodedata
import time
import sys
import os
import signal
from unidecode import unidecode
from typing import List, Dict, Set

# Add MIID validator to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))
from cheat_detection import normalize_address_for_deduplication
from reward import (
    looks_like_address,
    validate_address_region,
    check_with_nominatim
)

USER_AGENT = "MIIDSubnet/1.0 (contact: prasadpsd2001@gmail.com)"

###############################################################################
# NORMALIZER (exact deduplication logic)
###############################################################################

def remove_disallowed_unicode(text: str) -> str:
    allowed = []
    for c in text:
        code = ord(c)
        if 0x1D00 <= code <= 0x1D7F or 0x1D80 <= code <= 0x1DBF or 0xA720 <= code <= 0xA7FF:
            continue
        cat = unicodedata.category(c)
        if cat.startswith("L") or cat.startswith("M") or c in " 0123456789":
            allowed.append(c)
    return "".join(allowed)

def normalize_address(addr: str) -> str:
    if not addr or not addr.strip():
        return ""
    text = remove_disallowed_unicode(addr)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[-:,.;!?(){}\[\]\"'""''/\\|*_=+<>@#^&]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -:")
    text = unidecode(text)
    cleaned = text.replace(",", " ")
    parts = [p for p in cleaned.split(" ") if p]
    unique_words = set(parts)
    dedup = " ".join(unique_words)
    letters = re.findall(r'[^\W\d]', dedup, flags=re.UNICODE)
    letters = [c.lower() for c in letters if c not in ['\u02BB', '\u02BC']]
    return ''.join(sorted(letters))

###############################################################################
# QUERY NOMINATIM
###############################################################################

def fetch_nominatim(query: str, retries: int = 3) -> List[Dict]:
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "json",
        "addressdetails": 1,
        "limit": 5
    }
    headers = {"User-Agent": USER_AGENT}
    
    for attempt in range(retries):
        # Check for shutdown before each attempt
        if _shutdown_requested:
            return []
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                if _shutdown_requested:
                    return []
                time.sleep(1)
                if _shutdown_requested:
                    return []
                continue
            print(f"  ⚠️  Error fetching Nominatim: {e}")
            return []
    return []

###############################################################################
# EXTRACT COMPONENTS
###############################################################################

def extract_components(nom_json: List[Dict]) -> Dict:
    """Given a Nominatim JSON array, extract all meaningful components."""
    if not nom_json:
        return {}
    
    base = nom_json[0]  # use first result
    addr = base.get("address", {})
    components = {
        "road":          addr.get("road"),
        "suburb":        addr.get("suburb"),
        "residential":   addr.get("residential"),
        "city":          addr.get("city"),
        "county":        addr.get("county"),
        "state":         addr.get("state"),
        "postcode":      addr.get("postcode"),
        "country":       addr.get("country"),
    }
    # Flatten & remove None
    return {k: v for k, v in components.items() if v}

###############################################################################
# GENERATE UNIQUE VARIATIONS
###############################################################################

def transliterate_road(road: str) -> str:
    """Transliterate Persian/Arabic script road names to English using unidecode."""
    if not road:
        return road
    # Check if road contains non-Latin characters
    has_non_latin = any(ord(c) > 127 for c in road)
    if has_non_latin:
        # Use unidecode for transliteration
        transliterated = unidecode(road)
        # Capitalize properly (Title Case)
        words = transliterated.split()
        transliterated = ' '.join(word.capitalize() for word in words)
        return transliterated
    return road

def abbreviate_road(road: str) -> str:
    """Create abbreviation variations of road names."""
    abbreviations = {
        'Road': 'Rd',
        'Street': 'St',
        'Avenue': 'Ave',
        'Boulevard': 'Blvd',
        'Drive': 'Dr',
        'Lane': 'Ln',
        'Place': 'Pl',
    }
    result = road
    for full, abbrev in abbreviations.items():
        if full in result:
            result = result.replace(full, abbrev)
            break  # Only replace one
    return result

def translate_persian_district(persian_text: str, city_name: str = "") -> str:
    """
    Translate Persian district/province names to English.
    Common patterns:
    - "ناحیه سوم" → "3rd District"
    - "کابل ښاروالۍ" → "Kabul District"
    - "ولایت كابل" → "Kabul Province"
    """
    # Use unidecode to transliterate, then clean up
    transliterated = unidecode(persian_text)
    transliterated = transliterated.strip()
    
    # Common translations
    translations = {
        "ناحیه سوم": "3rd District",
        "ناحیه سیزدهم": "13th District",
        "کابل ښاروالۍ": f"{city_name} District" if city_name else "Kabul District",
        "ولایت كابل": f"{city_name} Province" if city_name else "Kabul Province",
    }
    
    # Check exact match first
    if persian_text in translations:
        return translations[persian_text]
    
    # Check if transliterated contains patterns
    transliterated_lower = transliterated.lower()
    
    # Check for "nahia" (district) patterns
    if "nahia" in transliterated_lower or "nw" in transliterated_lower:
        # Extract number if present
        import re
        numbers = re.findall(r'\d+', transliterated)
        if numbers:
            num = int(numbers[0])
            ordinals = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th",
                       6: "6th", 7: "7th", 8: "8th", 9: "9th", 10: "10th",
                       11: "11th", 12: "12th", 13: "13th", 14: "14th", 15: "15th"}
            if num in ordinals:
                return f"{ordinals[num]} District"
        return "District"
    
    # Check for "wilayat" (province) patterns
    if "wilayat" in transliterated_lower or "wlayt" in transliterated_lower:
        if city_name:
            return f"{city_name} Province"
        return "Province"
    
    # Check for "sharwali" (district) patterns
    if "sharwali" in transliterated_lower or "shrwly" in transliterated_lower:
        if city_name:
            return f"{city_name} District"
        return "District"
    
    # Fallback: if city name appears in transliterated, create pattern
    if city_name and city_name.lower() in transliterated_lower:
        if "province" in transliterated_lower or "wlayt" in transliterated_lower:
            return f"{city_name} Province"
        return f"{city_name} District"
    
    return transliterated  # Return transliterated as fallback

def extract_district_province_names(components: Dict, display_name: str, seed_city: str = None) -> List[str]:
    """
    Extract valid district/province names that appear in display_name.
    Translates Persian names to English patterns that work.
    """
    valid_names = []
    city_name = seed_city if seed_city else components.get("city", "")
    # Normalize city name (remove Persian, use English if available)
    if city_name and any(ord(c) > 127 for c in city_name):
        city_name = unidecode(city_name).strip()
    
    # If city_name is still Persian, try to get English version
    if not city_name or any(ord(c) > 127 for c in city_name):
        # Try to extract from display_name or use "Kabul" as default for Afghanistan
        city_name = "Kabul"  # Default for Afghanistan addresses
    
    county = components.get("county", "")
    state = components.get("state", "")
    suburb = components.get("suburb", "")
    
    # Translate and add district/province names
    if suburb and suburb in display_name:
        # Translate Persian suburb (e.g., "ناحیه سوم" → "3rd District")
        translated = translate_persian_district(suburb, city_name)
        if translated and translated not in valid_names:
            valid_names.append(translated)
    
    if county and county in display_name:
        # Translate Persian county (e.g., "کابل ښاروالۍ" → "Kabul District")
        translated = translate_persian_district(county, city_name)
        if translated and translated not in valid_names:
            valid_names.append(translated)
    
    if state and state in display_name:
        # Translate Persian state (e.g., "ولایت كابل" → "Kabul Province")
        translated = translate_persian_district(state, city_name)
        if translated and translated not in valid_names:
            valid_names.append(translated)
    
    # Also add English patterns if city_name is available
    if city_name:
        if f"{city_name} District" not in valid_names:
            valid_names.append(f"{city_name} District")
        if f"{city_name} Province" not in valid_names:
            valid_names.append(f"{city_name} Province")
    
    return list(dict.fromkeys(valid_names))  # Remove duplicates

def generate_variations(base_road: str, components: Dict, nominatim_result: Dict = None, seed_city: str = None, seed_address: str = None) -> List[str]:
    """
    Generate valid variations matching manually generated address patterns.
    
    Patterns from successful addresses:
    1. ROAD, District City, POSTCODE, COUNTRY (no comma between district and city)
    2. ROAD, District, City, POSTCODE, COUNTRY (with comma)
    3. ROAD, City, POSTCODE, COUNTRY (base)
    4. Transliterated roads (Persian → English)
    5. Road abbreviations (Road → Rd)
    """
    if not nominatim_result:
        return []
    
    # Get display_name from Nominatim result (the REAL OSM hierarchy)
    disp = nominatim_result.get("display_name", "")
    
    road = components.get("road")
    # Use seed_city if provided (from original address), otherwise use Nominatim's city
    # This ensures region validation passes
    city = seed_city if seed_city else components.get("city")
    
    # Extract postcode and country from seed_address if provided, otherwise use Nominatim
    postcode = components.get("postcode")
    country = components.get("country")
    
    if seed_address:
        import re
        # Extract postcode from seed (4-5 digit number)
        postcode_match = re.search(r'\b(\d{4,5})\b', seed_address)
        if postcode_match:
            postcode = postcode_match.group(1)
        
        # Extract country from seed (last part)
        parts = [p.strip() for p in seed_address.split(',')]
        if parts:
            seed_country = parts[-1]
            # Normalize country name (use English if available)
            country_mapping = {
                "افغانستان": "Afghanistan",
                "Afghanistan": "Afghanistan",
            }
            # Check if country is Persian or needs normalization
            if any(ord(c) > 127 for c in seed_country):
                # Transliterate Persian country name
                transliterated_country = unidecode(seed_country).strip()
                # Map common transliterations
                if "afghanistan" in transliterated_country.lower():
                    country = "Afghanistan"
                else:
                    country = transliterated_country
            else:
                country = country_mapping.get(seed_country, seed_country)
    
    if not (road and city and country):
        return []
    
    variations = []
    
    # Generate road variations (original, transliterated, abbreviated)
    road_variations = [road]
    
    # Transliterate if road has non-Latin characters
    transliterated_road = transliterate_road(road)
    if transliterated_road != road:
        road_variations.append(transliterated_road)
        # Also create abbreviation of transliterated version
        abbrev_trans = abbreviate_road(transliterated_road)
        if abbrev_trans != transliterated_road:
            road_variations.append(abbrev_trans)
    
    # Create abbreviation of original road
    abbrev_road = abbreviate_road(road)
    if abbrev_road != road:
        road_variations.append(abbrev_road)
    
    # Remove duplicates
    road_variations = list(dict.fromkeys(road_variations))
    
    # Extract valid district/province names from display_name
    district_province_names = extract_district_province_names(components, disp, seed_city=city)
    
    # Generate variations for each road variation
    for road_var in road_variations:
        # Base variation
        if postcode:
            variations.append(f"{road_var}, {city}, {postcode}, {country}")
        else:
            variations.append(f"{road_var}, {city}, {country}")
        
        # Add district/province variations
        for district_province in district_province_names:
            if postcode:
                # Format 1: ROAD, District City, POSTCODE, COUNTRY (no comma - like "3rd District Kabul")
                variations.append(f"{road_var}, {district_province} {city}, {postcode}, {country}")
                # Format 2: ROAD, District, City, POSTCODE, COUNTRY (with comma - like "Kabul District, Kabul")
                variations.append(f"{road_var}, {district_province}, {city}, {postcode}, {country}")
    
    # Remove duplicates preserving order
    return list(dict.fromkeys(variations))

###############################################################################
# MAIN PROCESSING
###############################################################################

def load_existing_addresses() -> Set[str]:
    """Load all normalized addresses from both JSON files."""
    normalized_set = set()
    
    # Load from cache
    try:
        with open('normalized_address_cache.json', 'r') as f:
            cache_data = json.load(f)
        for country, addresses in cache_data.get('addresses', {}).items():
            for addr in addresses:
                norm = addr.get('cheat_normalized_address', '')
                if norm:
                    normalized_set.add(norm)
    except Exception as e:
        print(f"⚠️  Error loading cache: {e}")
    
    # Load from variations
    try:
        with open('new_addresses_variations.json', 'r') as f:
            variations_data = json.load(f)
        for country, addresses in variations_data.get('addresses_by_country', {}).items():
            for addr in addresses:
                norm = addr.get('cheat_normalized_address', '')
                if norm:
                    normalized_set.add(norm)
    except Exception as e:
        print(f"⚠️  Error loading variations: {e}")
    
    return normalized_set

# Global flag for graceful shutdown
_shutdown_requested = False

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    global _shutdown_requested
    import sys
    if not _shutdown_requested:  # First time
        print("\n\n⚠️  Ctrl+C detected. Saving progress and shutting down gracefully...")
        _shutdown_requested = True
    else:  # Second time - force exit immediately
        print("\n\n⚠️  Force exit requested. Exiting immediately...")
        sys.exit(1)

# Fresh cache file for generated addresses
GENERATED_CACHE_FILE = "generated_addresses_cache.json"

def save_progress(variations_data):
    """Save current progress to generated_addresses_cache.json"""
    try:
        with open(GENERATED_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(variations_data, f, indent=2, ensure_ascii=False)
        print(f"✅ Progress saved to {GENERATED_CACHE_FILE}")
    except Exception as e:
        print(f"❌ Error saving progress: {e}")

def process_countries_with_less_than_15():
    """Process countries with < 15 addresses and generate variations."""
    global _shutdown_requested
    
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Load cache (read-only, to find countries that need addresses)
    with open('normalized_address_cache.json', 'r') as f:
        cache_data = json.load(f)
    
    # Load or create fresh cache file (where we'll save new addresses)
    # Start fresh - create new file if it doesn't exist
    if os.path.exists(GENERATED_CACHE_FILE):
        try:
            with open(GENERATED_CACHE_FILE, 'r') as f:
                variations_data = json.load(f)
            print(f"📂 Loading existing {GENERATED_CACHE_FILE}")
        except:
            variations_data = {
                "description": "Generated address variations from cache addresses",
                "created_at": "2024-12-19",
                "source": "Generated from addresses in normalized_address_cache.json",
                "addresses_by_country": {}
            }
    else:
        variations_data = {
            "description": "Generated address variations from cache addresses",
            "created_at": "2024-12-19",
            "source": "Generated from addresses in normalized_address_cache.json",
            "addresses_by_country": {}
        }
        print(f"📂 Creating fresh {GENERATED_CACHE_FILE}")
    
    # Get existing normalized addresses from BOTH files
    existing_normalized = load_existing_addresses()
    print(f"Loaded {len(existing_normalized)} existing normalized addresses")
    print()
    
    # Find countries with < 18 addresses
    TARGET_ADDRESSES = 18
    addresses_by_country = cache_data.get('addresses', {})
    
    # Get already generated addresses from cache
    generated_addresses_by_country = variations_data.get('addresses_by_country', {})
    
    countries_to_process = []
    
    for country, addresses in addresses_by_country.items():
        # Count addresses in original cache
        cache_count = len(addresses)
        
        # Count addresses already generated
        generated_count = len(generated_addresses_by_country.get(country, []))
        
        # Total addresses available
        total_count = cache_count + generated_count
        
        # Only process if total is less than target
        if cache_count > 0 and total_count < TARGET_ADDRESSES:
            needed = TARGET_ADDRESSES - total_count
            countries_to_process.append((country, addresses, needed, generated_count))
        elif generated_count >= TARGET_ADDRESSES:
            # Skip countries that already have enough addresses in generated cache
            print(f"⏭️  Skipping {country}: Already has {generated_count} addresses in generated cache")
    
    print(f"Found {len(countries_to_process)} countries with < {TARGET_ADDRESSES} addresses")
    print(f"Target: {TARGET_ADDRESSES} addresses per country")
    print()
    
    total_generated = 0
    total_added = 0
    
    # Process each country
    for country, addresses, needed_count, already_generated in countries_to_process:  # Process all countries
        if _shutdown_requested:
            print("\n⚠️  Shutdown requested. Saving progress...")
            save_progress(variations_data)
            break
        
        cache_count = len(addresses)
        generated_count = len(variations_data['addresses_by_country'].get(country, []))
        total_count = cache_count + generated_count
        
        print("=" * 80)
        print(f"Processing: {country}")
        print(f"  Addresses in original cache: {cache_count}")
        print(f"  Addresses already generated: {generated_count}")
        print(f"  Total addresses: {total_count}/{TARGET_ADDRESSES}")
        print(f"  Need to generate: {needed_count} more addresses")
        print("=" * 80)
        
        # Initialize country in variations file if not exists
        if country not in variations_data['addresses_by_country']:
            variations_data['addresses_by_country'][country] = []
        
        country_added = 0
        
        # Process each address in the country
        for addr_idx, addr_obj in enumerate(addresses, 1):
            if country_added >= needed_count:
                print(f"\n✅ Reached target! Generated {country_added} addresses for {country}")
                break
            
            address_processed = addr_idx
            original_addr = addr_obj.get('address', '')
            if not original_addr:
                continue
            
            print(f"\n{'='*80}")
            print(f"  📍 Address {address_processed}/{len(addresses)}: {original_addr}")
            print(f"  🎯 Progress: {country_added}/{needed_count} addresses generated so far")
            print(f"{'='*80}")
            
            # Fetch Nominatim data
            print(f"  [1/6] 🔍 Fetching Nominatim components for: {original_addr[:60]}...")
            nom_data = fetch_nominatim(original_addr)
            
            if not nom_data:
                print(f"  ❌ [1/6] FAILED: No Nominatim results found")
                if _shutdown_requested:
                    break
                time.sleep(1)  # Rate limiting
                if _shutdown_requested:
                    break
                continue
            
            print(f"  ✅ [1/6] SUCCESS: Got {len(nom_data)} Nominatim result(s)")
            
            # Extract components
            print(f"  [2/6] 🔧 Extracting address components...")
            components = extract_components(nom_data)
            if not components.get('road') or not components.get('city'):
                print(f"  ❌ [2/6] FAILED: Missing road or city components")
                print(f"     Available components: {list(components.keys())}")
                if _shutdown_requested:
                    break
                time.sleep(1)
                if _shutdown_requested:
                    break
                continue
            
            print(f"  ✅ [2/6] SUCCESS: Extracted {len(components)} components")
            print(f"     Components: {', '.join(components.keys())}")
            print(f"     Road: {components.get('road', 'N/A')}")
            print(f"     City: {components.get('city', 'N/A')}")
            print(f"     Country: {components.get('country', 'N/A')}")
            
            # Generate variations following THE GOLDEN RULES
            # CRITICAL: Must pass Nominatim result to check display_name
            # CRITICAL: Extract city from seed address to ensure region validation passes
            print(f"  [3/6] 🎲 Generating address variations (using OSM display_name hierarchy)...")
            base_road = components.get('road')
            
            # Extract city from original seed address (for region validation)
            # This ensures generated addresses use the same city name as seed
            from reward import extract_city_country
            seed_city, seed_country = extract_city_country(original_addr)
            if not seed_city:
                # Fallback to Nominatim city if extraction fails
                seed_city = components.get('city')
            
            # Pass the first Nominatim result - REQUIRED to check display_name
            nominatim_result = nom_data[0] if nom_data else None
            if nominatim_result:
                display_name = nominatim_result.get("display_name", "")
                print(f"     OSM display_name: {display_name[:80]}...")
                print(f"     Using city from seed: '{seed_city}' (for region validation)")
            variations = generate_variations(base_road, components, nominatim_result, seed_city=seed_city, seed_address=original_address)
            print(f"  ✅ [3/6] SUCCESS: Generated {len(variations)} valid variations (OSM hierarchy verified)")
            if variations:
                print(f"     Variations:")
                for i, var in enumerate(variations[:3], 1):
                    print(f"       {i}. {var[:70]}...")
                if len(variations) > 3:
                    print(f"       ... and {len(variations) - 3} more")
            
            # Filter unique variations and validate with ALL 4 checks
            # 1. looks_like_address
            # 2. validate_address_region
            # 3. check_with_nominatim (score >= 0.9)
            # 4. normalize_address_for_deduplication (uniqueness)
            print(f"  [4/6] ✅ Validating {len(variations)} variations with 4 checks...")
            unique_variations = []
            validation_stats = {
                'looks_like_address_failed': 0,
                'region_validation_failed': 0,
                'nominatim_failed': 0,
                'duplicate': 0,
                'passed': 0
            }
            
            for var_idx, var in enumerate(variations, 1):
                # Check for shutdown request
                if _shutdown_requested:
                    print(f"\n⚠️  Shutdown requested during validation. Stopping...")
                    break
                
                if country_added >= needed_count:
                    break
                
                if var_idx % 5 == 0 or var_idx == len(variations):
                    print(f"     Validating variation {var_idx}/{len(variations)}... ({validation_stats['passed']} passed so far)")
                # Check 1: looks_like_address
                try:
                    if not looks_like_address(var):
                        validation_stats['looks_like_address_failed'] += 1
                        continue  # Skip addresses that don't pass validation
                except Exception as e:
                    validation_stats['looks_like_address_failed'] += 1
                    continue  # Skip on error
                
                # Check 2: validate_address_region
                try:
                    if not validate_address_region(var, country):
                        validation_stats['region_validation_failed'] += 1
                        continue  # Skip addresses that don't pass region validation
                except Exception as e:
                    validation_stats['region_validation_failed'] += 1
                    continue  # Skip on error
                
                # Check 3: check_with_nominatim (score >= 0.9)
                score = 0.0
                try:
                    api_result = check_with_nominatim(
                        address=var,
                        validator_uid=1,
                        miner_uid=1,
                        seed_address=original_addr,
                        seed_name="Variation"
                    )
                    
                    if isinstance(api_result, dict):
                        score = api_result.get("score", 0.0)
                        if score < 0.9:
                            validation_stats['nominatim_failed'] += 1
                            continue  # Skip addresses with score < 0.9
                    else:
                        validation_stats['nominatim_failed'] += 1
                        continue  # Skip if API validation failed
                except Exception as e:
                    validation_stats['nominatim_failed'] += 1
                    continue  # Skip on error
                
                # Check 4: normalize_address_for_deduplication (uniqueness)
                norm = normalize_address_for_deduplication(var)
                if norm not in existing_normalized:
                    unique_variations.append((var, norm, score))
                    existing_normalized.add(norm)  # Track for this run
                    validation_stats['passed'] += 1
                else:
                    validation_stats['duplicate'] += 1
                
                # Check for shutdown before sleeping
                if _shutdown_requested:
                    break
                time.sleep(1)  # Rate limiting for Nominatim API calls
                if _shutdown_requested:
                    break
            
            print(f"  ✅ [4/6] Validation complete:")
            print(f"     • Passed all 4 checks: {validation_stats['passed']}")
            print(f"     • Failed looks_like_address: {validation_stats['looks_like_address_failed']}")
            print(f"     • Failed region validation: {validation_stats['region_validation_failed']}")
            print(f"     • Failed Nominatim (score < 0.9): {validation_stats['nominatim_failed']}")
            print(f"     • Duplicates: {validation_stats['duplicate']}")
            
            # Add to variations file (new_addresses_variations.json format)
            print(f"  [5/6] 💾 Adding {min(len(unique_variations), needed_count - country_added)} addresses to variations file...")
            added_this_round = 0
            for var, norm, score in unique_variations:
                if country_added >= needed_count:
                    break
                
                variations_data['addresses_by_country'][country].append({
                    "address": var,
                    "score": score,  # Actual score from check_with_nominatim
                    "cheat_normalized_address": norm,
                    "source_city": components.get('city', ''),
                    "referenced_from": original_addr,
                    "created_from": f"Generated from {country} cache address (variation)",
                    "country": country
                })
                country_added += 1
                total_added += 1
                added_this_round += 1
                print(f"     ✅ Added: {var[:70]}... (Score: {score:.2f})")
            
            print(f"  ✅ [5/6] Added {added_this_round} addresses this round")
            current_total = len(variations_data['addresses_by_country'][country])
            print(f"  📊 Total for {country} in variations file: {current_total} addresses")
            
            total_generated += len(variations)
            
            # Save progress after each address (incremental save)
            print(f"  [6/6] 💾 Saving progress to {GENERATED_CACHE_FILE}...")
            save_progress(variations_data)
            print(f"  ✅ [6/6] Progress saved!")
            
            # Check for shutdown before sleeping
            if _shutdown_requested:
                break
            time.sleep(1)  # Rate limiting
            if _shutdown_requested:
                break
        
        # Check for shutdown before processing next country
        if _shutdown_requested:
            break
        
        final_count = len(variations_data['addresses_by_country'][country])
        print(f"\n{'='*80}")
        print(f"✅ COMPLETED: {country}")
        print(f"   Total addresses in variations file: {final_count}")
        print(f"   Generated this run: {country_added} addresses")
        print(f"{'='*80}\n")
        
        # Save progress after each country
        save_progress(variations_data)
    
    # Final save (always save, even if shutdown was requested)
    if _shutdown_requested:
        print("\n💾 Saving final progress before exit...")
    save_progress(variations_data)
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total variations generated: {total_generated}")
    print(f"Total unique variations added: {total_added}")
    print(f"Addresses saved to: {GENERATED_CACHE_FILE}")
    print(f"Note: normalized_address_cache.json was NOT modified (read-only)")
    if _shutdown_requested:
        print(f"\n⚠️  Script stopped by user (Ctrl+C). Progress saved.")
        print(f"   Run the script again to continue - it will skip already processed countries.")

if __name__ == "__main__":
    process_countries_with_less_than_15()

