#!/usr/bin/env python3
"""
Fetch real addresses from Nominatim/OSM for all countries.
This script queries Nominatim API to get 20 real addresses per country.
"""

import json
import requests
import time
import re
from typing import List, Dict, Optional

# Rate limiting: 1 request per second (Nominatim policy)
NOMINATIM_DELAY = 1.0

def get_real_addresses_from_nominatim(country: str, limit: int = 20) -> List[str]:
    """
    Query Nominatim API for real addresses in a specific country.
    Returns actual addresses that exist in OSM.
    
    Args:
        country: Country name
        limit: Maximum number of addresses to fetch
        
    Returns:
        List of real addresses (formatted as "number street, city, country")
    """
    try:
        # Try different query strategies to get real addresses
        queries = [
            f"address in {country}",
            f"{country}",
        ]
        
        url = "https://nominatim.openstreetmap.org/search"
        headers = {
            "User-Agent": "MIID-Subnet-Address-Fetcher/1.0 (https://github.com/yanezcompliance/MIID-subnet; miner@yanezcompliance.com)"
        }
        
        all_results = []
        
        for query in queries:
            params = {
                "q": query,
                "format": "json",
                "limit": limit * 3,  # Fetch more to filter
                "addressdetails": 1,
                "extratags": 1,
                "namedetails": 1
            }
            
            try:
                response = requests.get(url, params=params, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    results = response.json()
                    if results:
                        all_results.extend(results)
                
                time.sleep(NOMINATIM_DELAY)
                break  # Only try first query for now
            except Exception:
                continue
        
        if not all_results:
            return []
        
        # Extract and format addresses
        real_addresses = []
        seen_addresses = set()
        seen_roads = set()
        
        for result in all_results:
            # Accept street-level or building-level results (place_rank >= 20)
            place_rank = result.get('place_rank', 0)
            if place_rank < 20:
                continue
            
            # Extract address components
            display_name = result.get('display_name', '')
            address_details = result.get('address', {})
            
            # Try to extract street/road name
            road = (
                address_details.get('road', '') or
                address_details.get('street', '') or
                address_details.get('street_name', '') or
                address_details.get('residential', '')
            )
            
            # Also check if it's a highway/road type
            result_class = result.get('class', '')
            result_type = result.get('type', '')
            if (result_class == 'highway' or result_type in ['residential', 'primary', 'secondary', 'tertiary']) and not road:
                road = result.get('name', '')
            
            # Extract house number
            house_number = address_details.get('house_number', '')
            if not house_number and display_name:
                # Try to extract number from display_name
                number_match = re.search(r'\b(\d+)\b', display_name.split(',')[0])
                if number_match:
                    house_number = number_match.group(1)
            
            # Extract city
            city = (
                address_details.get('city', '') or
                address_details.get('town', '') or
                address_details.get('village', '') or
                address_details.get('municipality', '') or
                address_details.get('state_district', '')
            )
            
            # Extract country (normalize)
            country_from_addr = address_details.get('country', '').lower()
            
            # If we have road and city, format the address
            if road and city:
                # Use house_number if available, otherwise skip
                if house_number:
                    number = house_number
                else:
                    # Try to extract from display_name
                    addr_match = re.match(r'^(\d+)\s+(.+?),\s*(.+?),\s*(.+?)$', display_name)
                    if addr_match:
                        number = addr_match.group(1)
                        street = addr_match.group(2).strip()
                        city = addr_match.group(3).strip()
                        country = addr_match.group(4).strip()
                    else:
                        # Skip addresses without house numbers (not precise enough)
                        continue
                
                # Format: "number street, city, country"
                formatted_addr = f"{number} {road}, {city}, {country}"
                
                # Normalize to avoid duplicates
                normalized_addr = formatted_addr.lower().strip()
                if normalized_addr not in seen_addresses and road.lower() not in seen_roads:
                    real_addresses.append(formatted_addr)
                    seen_addresses.add(normalized_addr)
                    seen_roads.add(road.lower())
                    
                    if len(real_addresses) >= limit:
                        break
        
        return real_addresses
    
    except Exception as e:
        print(f"  ❌ Error fetching addresses for {country}: {str(e)}")
        return []

def fetch_all_addresses(countries_file: str = 'all_validator_countries.json', output_file: str = 'real_addresses_db.json'):
    """
    Fetch real addresses for all countries from Nominatim/OSM.
    
    Args:
        countries_file: JSON file with list of countries
        output_file: Output JSON file for storing addresses
    """
    # Load countries
    with open(countries_file, 'r', encoding='utf-8') as f:
        all_countries = json.load(f)
    
    print("="*80)
    print("FETCHING REAL ADDRESSES FROM NOMINATIM/OSM")
    print("="*80)
    print(f"\n📋 Total countries: {len(all_countries)}")
    print(f"📋 Addresses per country: 20")
    print(f"📋 Total addresses to fetch: {len(all_countries) * 20}")
    print(f"\n⏱️  Estimated time: ~{len(all_countries) * NOMINATIM_DELAY / 60:.1f} minutes")
    print(f"   (Rate limit: 1 request/second)")
    print("\n" + "="*80)
    
    # Load existing database if it exists
    existing_db = {}
    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            existing_db = json.load(f)
        print(f"\n✅ Loaded existing database with {len(existing_db)} countries")
    except FileNotFoundError:
        print(f"\n📝 Starting fresh database")
    
    # Fetch addresses for each country
    real_addresses_db = existing_db.copy()
    successful = 0
    failed = []
    
    for i, country in enumerate(all_countries, 1):
        print(f"\n[{i}/{len(all_countries)}] Fetching addresses for: {country}")
        
        # Skip if already in database with enough addresses
        if country in real_addresses_db and len(real_addresses_db[country]) >= 20:
            print(f"  ✅ Already have {len(real_addresses_db[country])} addresses (skipping)")
            successful += 1
            continue
        
        # Fetch addresses
        addresses = get_real_addresses_from_nominatim(country, limit=20)
        
        if addresses:
            real_addresses_db[country] = addresses
            print(f"  ✅ Fetched {len(addresses)} real addresses")
            successful += 1
            
            # Save periodically (every 10 countries)
            if i % 10 == 0:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(real_addresses_db, f, indent=2, ensure_ascii=False)
                print(f"  💾 Saved progress ({i}/{len(all_countries)} countries)")
        else:
            print(f"  ❌ No addresses found")
            failed.append(country)
        
        # Rate limiting delay (already in function, but add extra for safety)
        if i < len(all_countries):
            time.sleep(0.5)
    
    # Final save
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(real_addresses_db, f, indent=2, ensure_ascii=False)
    
    print("\n" + "="*80)
    print("✅ FETCHING COMPLETE")
    print("="*80)
    print(f"\n📊 RESULTS:")
    print(f"   ✅ Successful: {successful}/{len(all_countries)}")
    print(f"   ❌ Failed: {len(failed)}")
    if failed:
        print(f"\n   Failed countries:")
        for country in failed[:10]:
            print(f"      - {country}")
        if len(failed) > 10:
            print(f"      ... and {len(failed) - 10} more")
    
    total_addresses = sum(len(addrs) for addrs in real_addresses_db.values())
    print(f"\n   📦 Total addresses in database: {total_addresses}")
    print(f"   💾 Saved to: {output_file}")
    print("="*80)

if __name__ == "__main__":
    import sys
    
    countries_file = sys.argv[1] if len(sys.argv) > 1 else 'all_validator_countries.json'
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'real_addresses_db.json'
    
    fetch_all_addresses(countries_file, output_file)

