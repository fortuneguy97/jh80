#!/usr/bin/env python3
"""
Test script to validate Afghanistan addresses using rewards.py functions
"""

import sys
import os
import time

# Add MIID validator to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

from reward import (
    looks_like_address,
    validate_address_region,
    check_with_nominatim
)

# Sleep between API calls to avoid rate limiting
API_SLEEP = 1.0

# Alternative Nominatim instances (uncomment to use):
# os.environ["NOMINATIM_URL"] = "https://nominatim.openstreetmap.org"  # Official (default)
# os.environ["NOMINATIM_URL"] = "https://geocode.maps.co"  # Alternative service
# os.environ["NOMINATIM_URL"] = "http://localhost:8080"  # Self-hosted instance

# Check if custom Nominatim URL is set
nominatim_url = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org")
print(f"Using Nominatim instance: {nominatim_url}")
print()

# Test addresses
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

def test_addresses():
    """Test all addresses with validation functions"""
    
    seed_address = "Afghanistan"
    seed_name = "Test"
    validator_uid = 101
    miner_uid = 501
    
    results = {
        "total": len(ADDRESSES_TO_TEST),
        "looks_like_address_pass": 0,
        "region_validation_pass": 0,
        "api_validation_pass": 0,
        "all_pass": 0,
        "details": []
    }
    
    print("=" * 80)
    print("TESTING AFGHANISTAN ADDRESSES")
    print("=" * 80)
    print(f"Total addresses to test: {len(ADDRESSES_TO_TEST)}")
    print()
    
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
                # Sleep before API call to avoid rate limiting
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
    
    # Print addresses that fail
    print("=" * 80)
    print("ADDRESSES THAT FAIL")
    print("=" * 80)
    failed_addresses = [r for r in results["details"] if not r["all_pass"]]
    for r in failed_addresses[:20]:  # Show first 20 failures
        reasons = []
        if not r["looks_like"]:
            reasons.append("looks_like_address")
        if not r["region_valid"]:
            reasons.append("region_validation")
        if not r["api_valid"]:
            reasons.append(f"api_validation (score: {r['api_score']})")
        print(f"❌ {r['address'][:60]}... | Failures: {', '.join(reasons)}")
    
    if len(failed_addresses) > 20:
        print(f"... and {len(failed_addresses) - 20} more failures")
    
    return results

if __name__ == "__main__":
    results = test_addresses()

