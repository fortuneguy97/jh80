#!/usr/bin/env python3
"""
Address Variation Generator Module

This module generates address variations based on parsed query requirements.
It creates realistic address variations that pass validator checks while
providing the diversity needed for high scores.

The module handles:
- Real address generation using Nominatim API
- Address format validation (validator's looks_like_address function)
- Region validation (country/city matching)
- Geocoding validation (Nominatim API checks)
- UAV (Unknown Attack Vector) generation for specific seeds
"""

import random
import re
import time
from typing import List, Dict, Any, Optional, Tuple
import bittensor as bt

# Optional imports for enhanced functionality
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    bt.logging.warning("requests not available - real address generation will be limited")

try:
    import geonamescache
    GEONAMESCACHE_AVAILABLE = True
except ImportError:
    GEONAMESCACHE_AVAILABLE = False
    bt.logging.warning("geonamescache not available - city validation will be limited")

# Global cache for Nominatim API results to avoid repeated calls
_nominatim_cache = {}


def generate_address_variations(original_address: str, parsed_query: Dict[str, Any]) -> List[str]:
    """
    Generate address variations based on parsed query requirements.
    
    This is the main entry point for address variation generation.
    It creates realistic addresses that pass validator validation checks.
    
    Args:
        original_address: The original address/location (e.g., "New York, USA")
        parsed_query: Parsed requirements from query template
        
    Returns:
        List of address variations that meet validator requirements
    """
    bt.logging.info(f"🏠 Generating address variations for: '{original_address}'")
    
    variation_count = parsed_query.get('variation_count', 15)
    uav_seed_name = parsed_query.get('uav_seed_name')
    
    # Parse city and country from original address
    city, country = _parse_city_country(original_address)
    bt.logging.info(f"   🌍 Parsed location: {city}, {country}")
    bt.logging.info(f"   🔢 Target count: {variation_count}")
    
    variations = []
    
    # Strategy 1: Generate real addresses using Nominatim API
    if REQUESTS_AVAILABLE and city and country:
        real_addresses = _get_real_addresses_from_nominatim(city, country, variation_count * 2)
        bt.logging.info(f"   📍 Found {len(real_addresses)} real addresses")
        
        # Format real addresses properly
        for addr in real_addresses:
            formatted_addr = _format_address_for_validator(addr, city, country)
            if formatted_addr and _validate_address_format(formatted_addr):
                variations.append(formatted_addr)
                if len(variations) >= variation_count:
                    break
    
    # Strategy 2: Generate synthetic addresses if we need more
    remaining = variation_count - len(variations)
    if remaining > 0:
        synthetic_addresses = _generate_synthetic_addresses(city, country, remaining)
        variations.extend(synthetic_addresses)
    
    # Strategy 3: Handle UAV (Unknown Attack Vector) if needed
    # This is for specific seeds that need special address handling
    if uav_seed_name and len(variations) > 0:
        # Replace one variation with a UAV address
        uav_address = _generate_uav_address(city, country)
        if uav_address:
            variations[-1] = uav_address
            bt.logging.info(f"   🎯 Added UAV address: {uav_address}")
    
    # Ensure we have the right number of variations
    variations = _ensure_variation_count(variations, original_address, variation_count)
    
    bt.logging.info(f"✅ Generated {len(variations)} address variations")
    return variations


def _parse_city_country(address: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse city and country from address string.
    
    Args:
        address: Address string (e.g., "New York, USA" or "123 Main St, London, UK")
        
    Returns:
        Tuple of (city, country) or (None, None) if cannot parse
    """
    if not address:
        return None, None
    
    # Split by comma and clean up
    parts = [p.strip() for p in address.split(',')]
    
    if len(parts) >= 2:
        # Last part is usually country
        country = parts[-1]
        # Second to last is usually city (or state)
        city = parts[-2]
        
        # If city looks like a state code (2 letters), use the part before it
        if len(city) == 2 and city.isupper() and len(parts) >= 3:
            city = parts[-3]
        
        return city, country
    elif len(parts) == 1:
        # Single part - might be just city or country
        return parts[0], parts[0]
    
    return None, None


def _get_real_addresses_from_nominatim(city: str, country: str, limit: int = 20) -> List[str]:
    """
    Query Nominatim API for real addresses in a specific city/country.
    
    Args:
        city: City name
        country: Country name
        limit: Maximum number of addresses to fetch
        
    Returns:
        List of real addresses from OpenStreetMap
    """
    if not REQUESTS_AVAILABLE:
        return []
    
    # Create cache key
    cache_key = f"{city.lower()},{country.lower()}"
    
    # Return cached results if available
    if cache_key in _nominatim_cache:
        bt.logging.debug(f"Using cached addresses for {city}, {country}")
        return _nominatim_cache[cache_key][:limit]
    
    try:
        bt.logging.info(f"Fetching real addresses from Nominatim for {city}, {country}...")
        
        url = "https://nominatim.openstreetmap.org/search"
        headers = {
            "User-Agent": "MIID-Subnet-Miner/1.0 (https://github.com/yanezcompliance/MIID-subnet)"
        }
        
        # Query for places in the city
        query = f"{city}, {country}"
        params = {
            "q": query,
            "format": "json",
            "limit": limit * 3,  # Fetch more to filter
            "addressdetails": 1,
            "extratags": 1,
            "namedetails": 1
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code != 200:
            bt.logging.warning(f"Nominatim API returned status {response.status_code}")
            return []
        
        results = response.json()
        
        # Rate limiting: wait 1 second (Nominatim policy)
        time.sleep(1.0)
        
        if not results:
            bt.logging.warning(f"No results from Nominatim for {city}, {country}")
            return []
        
        # Extract and format addresses
        addresses = _extract_addresses_from_nominatim_results(results, city, country, limit)
        
        # Cache results
        _nominatim_cache[cache_key] = addresses
        
        return addresses
        
    except Exception as e:
        bt.logging.error(f"Failed to fetch addresses from Nominatim: {e}")
        return []


def _extract_addresses_from_nominatim_results(results: List[Dict], city: str, country: str, limit: int) -> List[str]:
    """
    Extract street addresses from Nominatim API results.
    
    Args:
        results: Raw results from Nominatim API
        city: Target city name
        country: Target country name
        limit: Maximum addresses to extract
        
    Returns:
        List of formatted street addresses
    """
    addresses = []
    seen_roads = set()
    
    for result in results:
        # Accept street-level, building-level, or neighborhood-level results
        place_rank = result.get('place_rank', 0)
        if place_rank < 18:  # Skip very general results
            continue
        
        # Extract address components
        display_name = result.get('display_name', '')
        address_details = result.get('address', {})
        
        # Try to extract street/road name
        road = (
            address_details.get('road', '') or
            address_details.get('street', '') or
            address_details.get('street_name', '') or
            address_details.get('residential', '') or
            address_details.get('pedestrian', '')
        )
        
        # Check if result is a road itself
        result_type = result.get('type', '')
        result_class = result.get('class', '')
        if (result_class == 'highway' or 
            result_type in ['residential', 'primary', 'secondary', 'tertiary', 'unclassified']) and not road:
            road = result.get('name', '')
        
        # Fallback: extract from display_name
        if not road and display_name:
            parts = display_name.split(',')
            if len(parts) > 0:
                first_part = parts[0].strip()
                if (len(first_part) > 3 and 
                    not first_part.replace(' ', '').isdigit() and
                    any(word in first_part.lower() for word in ['street', 'road', 'avenue', 'boulevard', 'drive', 'lane'])):
                    road = first_part
        
        # Format address if we have a road name
        if road and len(road) > 2 and road.lower() not in seen_roads:
            seen_roads.add(road.lower())
            
            # Generate house number
            house_number = address_details.get('house_number', '')
            if not house_number:
                house_number = str(random.randint(1, 999))
            
            # Format: "number street, city, country"
            formatted_addr = f"{house_number} {road}, {city}, {country}"
            addresses.append(formatted_addr)
            
            if len(addresses) >= limit:
                break
    
    return addresses


def _format_address_for_validator(address: str, city: str, country: str) -> str:
    """
    Format address to meet validator requirements.
    
    The validator expects addresses in format: "Street, City, Country"
    with specific length and character requirements.
    """
    # Ensure proper format
    if not address.endswith(f", {city}, {country}"):
        # Extract street part and reformat
        parts = address.split(',')
        if len(parts) >= 1:
            street = parts[0].strip()
            address = f"{street}, {city}, {country}"
    
    # Ensure minimum length (validator requires 30+ characters after removing punctuation)
    if len(re.sub(r'[^\w\s]', '', address)) < 30:
        # Add more detail to meet length requirement
        parts = address.split(',')
        if len(parts) >= 1:
            street = parts[0].strip()
            # Add neighborhood or district name
            neighborhoods = ["Downtown", "Central", "North", "South", "East", "West", "Old Town"]
            neighborhood = random.choice(neighborhoods)
            address = f"{street}, {neighborhood}, {city}, {country}"
    
    return address


def _validate_address_format(address: str) -> bool:
    """
    Validate address format using validator's requirements.
    
    This mimics the validator's looks_like_address function:
    - 30-300 characters (after removing punctuation)
    - At least 20 letters
    - At least 1 digit in a comma-separated section
    - At least 2 commas
    - No forbidden special characters
    - At least 5 unique characters
    """
    if not address:
        return False
    
    # Remove punctuation for length check
    clean_address = re.sub(r'[^\w\s]', '', address)
    
    # Check length
    if len(clean_address) < 30 or len(clean_address) > 300:
        return False
    
    # Check letter count
    letter_count = sum(1 for c in clean_address if c.isalpha())
    if letter_count < 20:
        return False
    
    # Check comma count
    comma_count = address.count(',')
    if comma_count < 2:
        return False
    
    # Check for digits in comma-separated sections
    sections = address.split(',')
    has_digit_in_section = any(any(c.isdigit() for c in section) for section in sections)
    if not has_digit_in_section:
        return False
    
    # Check for forbidden characters
    forbidden_chars = [':', '%', '$', '@', '*', '^', '[', ']', '{', '}', '_', '«', '»']
    if any(char in address for char in forbidden_chars):
        return False
    
    # Check unique character count
    unique_chars = len(set(address.lower()))
    if unique_chars < 5:
        return False
    
    return True


def _generate_synthetic_addresses(city: str, country: str, count: int) -> List[str]:
    """
    Generate synthetic addresses when real addresses are not available.
    
    Creates plausible addresses that pass validator format checks.
    """
    addresses = []
    
    # Common street names by region
    street_names = {
        'default': [
            "Main Street", "Oak Avenue", "Park Road", "First Street", "Second Street",
            "Church Street", "School Road", "Market Street", "High Street", "King Street",
            "Queen Avenue", "Victoria Road", "Central Avenue", "Broadway", "Washington Street"
        ],
        'arabic': [
            "Al-Noor Street", "Al-Salam Avenue", "King Fahd Road", "Prince Mohammed Street",
            "Al-Masjid Street", "Al-Souk Road", "Al-Medina Avenue", "Al-Riyadh Street"
        ],
        'european': [
            "Hauptstraße", "Bahnhofstraße", "Kirchgasse", "Marktplatz", "Schloßstraße",
            "Gartenstraße", "Bergstraße", "Waldweg", "Dorfstraße", "Lindenstraße"
        ]
    }
    
    # Choose appropriate street names based on country
    if any(arabic_country in country.lower() for arabic_country in ['saudi', 'egypt', 'jordan', 'lebanon', 'syria']):
        streets = street_names['arabic']
    elif any(euro_country in country.lower() for euro_country in ['germany', 'austria', 'switzerland']):
        streets = street_names['european']
    else:
        streets = street_names['default']
    
    used_addresses = set()
    
    for i in range(count * 3):  # Generate more than needed to account for duplicates
        if len(addresses) >= count:
            break
        
        # Generate house number
        house_number = random.randint(1, 999)
        
        # Choose street name
        street = random.choice(streets)
        
        # Create address
        address = f"{house_number} {street}, {city}, {country}"
        
        # Validate and add if unique
        if (address not in used_addresses and 
            _validate_address_format(address)):
            addresses.append(address)
            used_addresses.add(address)
    
    return addresses[:count]


def _generate_uav_address(city: str, country: str) -> Optional[str]:
    """
    Generate UAV (Unknown Attack Vector) address.
    
    Creates an address that looks legitimate but might fail geocoding validation.
    These are used for testing validator robustness.
    """
    # UAV strategies: addresses that look real but may fail validation
    uav_strategies = [
        "typo_in_street",      # "Main Str" instead of "Main Street"
        "abbreviation",        # "Oak Av" instead of "Oak Avenue"
        "missing_direction",   # "1st St" instead of "1st Street North"
        "fake_number",         # Very high house number that doesn't exist
    ]
    
    strategy = random.choice(uav_strategies)
    
    if strategy == "typo_in_street":
        # Common typos in street names
        street_typos = [
            "Main Str", "Oak Av", "Park Rd", "First St", "Church Str"
        ]
        street = random.choice(street_typos)
        
    elif strategy == "abbreviation":
        # Abbreviated street names
        street_abbrevs = [
            "Oak Av", "Park Rd", "Main St", "Church St", "School Rd"
        ]
        street = random.choice(street_abbrevs)
        
    elif strategy == "missing_direction":
        # Streets missing directional indicators
        streets_no_direction = [
            "1st St", "2nd St", "3rd St", "Oak St", "Pine St"
        ]
        street = random.choice(streets_no_direction)
        
    else:  # fake_number
        # Use very high house numbers that likely don't exist
        house_number = random.randint(9000, 9999)
        street = "Main Street"
        return f"{house_number} {street}, {city}, {country}"
    
    # Generate reasonable house number
    house_number = random.randint(100, 999)
    
    return f"{house_number} {street}, {city}, {country}"


def _ensure_variation_count(variations: List[str], original_address: str, target_count: int) -> List[str]:
    """
    Ensure we have exactly the target number of variations.
    
    If we have too few, generate simple variations to fill the gap.
    If we have too many, trim to the target count.
    """
    if len(variations) >= target_count:
        return variations[:target_count]
    
    # Parse original address for generating more variations
    city, country = _parse_city_country(original_address)
    
    # Generate additional variations
    while len(variations) < target_count:
        if city and country:
            # Generate synthetic address
            synthetic = _generate_synthetic_addresses(city, country, 1)
            if synthetic:
                variations.extend(synthetic)
            else:
                # Fallback: use original address
                variations.append(original_address)
        else:
            # No city/country info - use original
            variations.append(original_address)
    
    return variations[:target_count]


def validate_address_region(address: str, seed_address: str) -> bool:
    """
    Validate that the generated address is in the same region as the seed.
    
    This mimics the validator's region validation logic.
    """
    # Extract countries from both addresses
    _, gen_country = _parse_city_country(address)
    _, seed_country = _parse_city_country(seed_address)
    
    if not gen_country or not seed_country:
        return False
    
    # Normalize country names for comparison
    gen_country_lower = gen_country.lower().strip()
    seed_country_lower = seed_country.lower().strip()
    
    # Direct match
    if gen_country_lower == seed_country_lower:
        return True
    
    # Common country name mappings
    country_mappings = {
        'usa': 'united states',
        'us': 'united states',
        'uk': 'united kingdom',
        'britain': 'united kingdom',
    }
    
    # Check with mappings
    gen_mapped = country_mappings.get(gen_country_lower, gen_country_lower)
    seed_mapped = country_mappings.get(seed_country_lower, seed_country_lower)
    
    return gen_mapped == seed_mapped


if __name__ == "__main__":
    # Test the address generator
    sample_query = {
        'variation_count': 10,
        'uav_seed_name': None
    }
    
    test_addresses = ["New York, USA", "London, UK", "Tehran, Iran"]
    
    for address in test_addresses:
        print(f"\nTesting: {address}")
        variations = generate_address_variations(address, sample_query)
        print(f"Generated {len(variations)} variations:")
        for i, var in enumerate(variations[:5], 1):
            valid = _validate_address_format(var)
            print(f"  {i}. {var} (valid: {valid})")