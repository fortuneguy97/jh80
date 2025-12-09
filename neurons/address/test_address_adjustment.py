"""
Test the address adjustment function to see if it can pass buggy region validation.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

from unified_generator import adjust_address_for_buggy_validation
from reward import validate_address_region, extract_city_country

# Test cases
test_cases = [
    {
        "seed": "New York, USA",
        "nominatim_address": "New York Public Library, 40, Hearst Plaza, Manhattan, New York, 10023, United States of America"
    },
    {
        "seed": "London, UK",
        "nominatim_address": "Spinex Disc Clinic, 11-13, Crosswall, Leadenhall Market, City of London, Greater London, England, EC3N 2JY, United Kingdom"
    }
]

print("="*100)
print("TESTING ADDRESS ADJUSTMENT FOR BUGGY VALIDATION")
print("="*100)
print()

for i, test in enumerate(test_cases, 1):
    seed = test["seed"]
    nominatim = test["nominatim_address"]
    
    print(f"Test {i}:")
    print(f"  Seed: {seed}")
    print(f"  Original: {nominatim}")
    print()
    
    # Extract from original
    orig_city, orig_country = extract_city_country(nominatim, two_parts=(',' in seed))
    print(f"  Original extraction: city='{orig_city}', country='{orig_country}'")
    
    # Test original validation
    orig_result = validate_address_region(nominatim, seed)
    print(f"  Original validation: {orig_result}")
    print()
    
    # Adjust address
    adjusted = adjust_address_for_buggy_validation(nominatim, seed)
    print(f"  Adjusted: {adjusted}")
    print()
    
    # Extract from adjusted
    adj_city, adj_country = extract_city_country(adjusted, two_parts=(',' in seed))
    print(f"  Adjusted extraction: city='{adj_city}', country='{adj_country}'")
    
    # Test adjusted validation
    adj_result = validate_address_region(adjusted, seed)
    print(f"  Adjusted validation: {adj_result}")
    
    if adj_result:
        print(f"  ✅ SUCCESS: Adjusted address passes validation!")
    else:
        print(f"  ❌ FAILED: Adjusted address still fails validation")
        print(f"     Bug compares: '{adj_city}' or '{adj_country}' == '{seed.lower()}'")
        print(f"     Neither matches!")
    
    print()
    print("-"*100)
    print()

