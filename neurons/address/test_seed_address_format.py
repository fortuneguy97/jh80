"""
Test to see what format seed addresses are sent by the validator.
Check both positive samples (Country_Residence) and negative samples (get_random_country).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

# Try to import and check what format addresses use
try:
    import geonamescache
    gc = geonamescache.GeonamesCache()
    countries_data = gc.get_countries()
    
    print("="*100)
    print("CHECKING SEED ADDRESS FORMATS")
    print("="*100)
    print()
    
    # Check what get_random_country() would return
    print("1. NEGATIVE SAMPLES (get_random_country()):")
    print("-"*100)
    print("This uses GeonamesCache.get_countries()")
    print("Sample country names from GeonamesCache:")
    
    sample_countries = []
    for code, data in list(countries_data.items())[:10]:
        country_name = data.get('name', '')
        sample_countries.append(country_name)
        print(f"  - {country_name}")
    
    print()
    print("Format: Just country name (e.g., 'United States', 'United Kingdom')")
    print("✅ This format would work with region validation (just country)")
    print()
    
    # Check what Country_Residence might contain
    print("2. POSITIVE SAMPLES (Country_Residence from sanctioned individuals):")
    print("-"*100)
    print("This comes from the sanctioned individuals data file")
    print("Could be:")
    print("  - Just country name: 'United States'")
    print("  - City, Country format: 'New York, USA'")
    print("  - Just city name: 'London'")
    print()
    print("⚠️  We need to check the actual data file to see the format")
    print()
    
    # Check the query template to see what it says
    print("3. QUERY TEMPLATE MENTION:")
    print("-"*100)
    query_text = "The following address is the seed country/city to generate address variations for: {address}."
    print(f"Query template says: '{query_text}'")
    print()
    print("It says 'country/city' which suggests it could be either:")
    print("  - Just country: 'United States'")
    print("  - Just city: 'London'")
    print("  - City, Country: 'New York, USA'")
    print()
    
    # Test different formats
    print("4. TESTING DIFFERENT FORMATS:")
    print("-"*100)
    
    test_formats = [
        ("United States", "Just country name"),
        ("USA", "Just country code"),
        ("London", "Just city name"),
        ("New York, USA", "City, Country format"),
        ("New York, United States", "City, Full Country format"),
    ]
    
    for address, description in test_formats:
        print(f"\nFormat: {description}")
        print(f"  Address: '{address}'")
        print(f"  Has comma? {',' in address}")
        print(f"  Parts: {address.split(',') if ',' in address else [address]}")
    
    print()
    print("="*100)
    print("CONCLUSION:")
    print("="*100)
    print()
    print("The validator can send seed addresses in different formats:")
    print("  1. Just country name (from get_random_country) → ✅ Works with region validation")
    print("  2. Just city name (possible from Country_Residence) → ✅ Works with region validation")
    print("  3. City, Country format (possible from Country_Residence) → ❌ FAILS with region validation bug")
    print()
    print("The bug affects 'City, Country' format seeds, but other formats might work!")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

