#!/usr/bin/env python3
"""
Detailed test of 50 Cambodia guaranteed 0.9 addresses - check each address individually and batch validation
"""

import os
import sys
import json
import time

# Add MIID validator to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

from reward import check_with_nominatim, looks_like_address, validate_address_region, _grade_address_variations

def test_individual_address(address: str, country: str) -> dict:
    """Test a single address with all validation steps"""
    result = {
        "address": address,
        "heuristic": False,
        "region": False,
        "api_score": 0.0,
        "api_result": None,
        "status": "FAIL"
    }
    
    # Step 1: Heuristic check
    result["heuristic"] = looks_like_address(address)
    
    # Step 2: Region check
    result["region"] = validate_address_region(address, country)
    
    # Step 3: API check
    api_result = check_with_nominatim(
        address=address,
        validator_uid=101,
        miner_uid=501,
        seed_address=country,
        seed_name="Test"
    )
    
    if api_result == "TIMEOUT":
        result["api_result"] = "TIMEOUT"
        result["api_score"] = 0.0
    elif isinstance(api_result, dict):
        result["api_score"] = api_result.get('score', 0.0)
        result["api_result"] = "SUCCESS" if result["api_score"] >= 0.9 else "FAILED"
    elif isinstance(api_result, (int, float)):
        result["api_score"] = float(api_result)
        result["api_result"] = "SUCCESS" if result["api_score"] >= 0.9 else "FAILED"
    else:
        result["api_result"] = "FAILED"
        result["api_score"] = 0.0
    
    # Overall status
    if result["heuristic"] and result["region"] and result["api_score"] >= 0.99:
        result["status"] = "PASS"
    elif result["heuristic"] and result["region"] and result["api_score"] >= 0.9:
        result["status"] = "PASS_09"
    else:
        result["status"] = "FAIL"
    
    # Rate limit
    time.sleep(1.0)
    
    return result

def main():
    """Test all 50 Cambodia addresses individually and as a batch"""
    cambodia_addresses = [
        # 1-10
        "The Little Red Fox Espresso, Siem Reap, 171202, Cambodia",
        "Gelato Lab, Siem Reap, 171202, Cambodia",
        "The Hive Café, Siem Reap, 171202, Cambodia",
        "The Missing Socks Laundry Café, Siem Reap, 171204, Cambodia",
        "Brother Bong Café, Siem Reap, 171204, Cambodia",
        "The Source Café, Siem Reap, 171204, Cambodia",
        "Crane Café, Siem Reap, 171202, Cambodia",
        "The Hideout Barista & Lounge, Siem Reap, 171204, Cambodia",
        "Sombai Cocktails & Liquor House, Siem Reap, 171204, Cambodia",
        "Banlle Vegetarian Restaurant, Siem Reap, 171202, Cambodia",
        # 11-20
        "Fresh Fruit Factory, Siem Reap, 171204, Cambodia",
        "Jomnan's Kitchen, Siem Reap, 171202, Cambodia",
        "Footprint Café, Siem Reap, 171204, Cambodia",
        "The Station Wine Bar, Siem Reap, 171204, Cambodia",
        "The Red Angkor Café, Siem Reap, 171204, Cambodia",
        "Khmer Grill, Siem Reap, 171202, Cambodia",
        "The Night Market Café, Siem Reap, 171204, Cambodia",
        "Angkor Muscle Gym, Siem Reap, 171202, Cambodia",
        "Angkor Market Mini Mart, Siem Reap, 171205, Cambodia",
        "Sambo Café, Siem Reap, 171204, Cambodia",
        # 21-30
        "Paris Bakery, Siem Reap, 171202, Cambodia",
        "Khmer Chef Restaurant, Siem Reap, 171204, Cambodia",
        "The Continental Bakery, Siem Reap, 171202, Cambodia",
        "The Mansion Siem Reap, Siem Reap, 171202, Cambodia",
        "The Urban Retreat Spa, Siem Reap, 171204, Cambodia",
        "Cambodian BBQ Restaurant, Siem Reap, 171204, Cambodia",
        "Olive Cuisine de Saison, Siem Reap, 171202, Cambodia",
        "Yellow Mango Café, Siem Reap, 171204, Cambodia",
        "Annadya Café, Siem Reap, 171205, Cambodia",
        "The Veg G Table, Siem Reap, 171202, Cambodia",
        # 31-40
        "The Local Cafe, Siem Reap, 171204, Cambodia",
        "Khmer Family Restaurant, Siem Reap, 171204, Cambodia",
        "The Republic Siem Reap, Siem Reap, 171204, Cambodia",
        "Vintner Wine Shop, Siem Reap, 171202, Cambodia",
        "Viva Mexican Restaurant, Siem Reap, 171202, Cambodia",
        "Rosy Guesthouse Café, Siem Reap, 171202, Cambodia",
        "Peace Café, Siem Reap, 171202, Cambodia",
        "The Harbour Restaurant, Siem Reap, 171204, Cambodia",
        "Domino Minimart, Siem Reap, 171205, Cambodia",
        "Siem Reap Massage & Spa Lounge, Siem Reap, 171202, Cambodia",
        # 41-50
        "The Blue Pumpkin, Siem Reap, 171205, Cambodia",
        "SO CHOU – French Pastry & Choux, Siem Reap, 171202, Cambodia",
        "Yoga Space, Siem Reap, 171202, Cambodia",
        "0207 River Road, Siem Reap, 171201, Cambodia",
        "The Grey Restaurant, Siem Reap, 171202, Cambodia",
        "Sala Bai Restaurant School, Siem Reap, 171204, Cambodia",
        "The Bean Embassy, Siem Reap, 171202, Cambodia",
        "Lemongrass Garden Spa, Siem Reap, 171204, Cambodia",
        "Sothy's Pepper Farm Shop, Siem Reap, 171205, Cambodia",
        "La Pasta Siem Reap, Siem Reap, 171202, Cambodia"
    ]
    
    print("="*80)
    print("DETAILED VALIDATION OF 50 CAMBODIA GUARANTEED 0.9 ADDRESSES")
    print("="*80)
    print(f"\n📋 Testing {len(cambodia_addresses)} addresses individually\n")
    print("⚠️  This will take approximately 50+ seconds due to rate limiting...\n")
    
    results = []
    for i, address in enumerate(cambodia_addresses, 1):
        print(f"[{i}/{len(cambodia_addresses)}] Testing: {address[:60]}...")
        result = test_individual_address(address, "Cambodia")
        results.append(result)
        
        # Print result (only show every 5th or failed addresses)
        status_icon = "✅" if result["status"] == "PASS" else "⚠️" if result["status"] == "PASS_09" else "❌"
        if result["status"] == "FAIL" or i % 5 == 0:
            print(f"     {status_icon} Heuristic: {result['heuristic']}, Region: {result['region']}, API: {result['api_score']:.4f} ({result['api_result']})")
        print()
    
    # Summary
    print("="*80)
    print("INDIVIDUAL VALIDATION SUMMARY")
    print("="*80)
    
    passed_10 = sum(1 for r in results if r["status"] == "PASS" and r["api_score"] >= 0.99)
    passed_09 = sum(1 for r in results if r["status"] == "PASS_09" and 0.9 <= r["api_score"] < 0.99)
    failed = sum(1 for r in results if r["status"] == "FAIL")
    
    print(f"✅ Score 1.0: {passed_10}/{len(cambodia_addresses)}")
    print(f"⚠️  Score 0.9: {passed_09}/{len(cambodia_addresses)}")
    print(f"❌ Failed: {failed}/{len(cambodia_addresses)}")
    print()
    
    # Show all passing addresses
    print("="*80)
    print("PASSING ADDRESSES (Score >= 0.9)")
    print("="*80)
    passing = [r for r in results if r["api_score"] >= 0.9]
    if passing:
        for i, r in enumerate(passing, 1):
            score_label = "1.0" if r["api_score"] >= 0.99 else "0.9"
            print(f"{i}. {r['address']} (Score: {r['api_score']:.4f} [{score_label}])")
    else:
        print("None")
    
    # Show failed addresses (first 10)
    if failed > 0:
        print(f"\n{'='*80}")
        print(f"FAILED ADDRESSES (First 10 of {failed})")
        print("="*80)
        failed_list = [r for r in results if r["status"] == "FAIL"]
        for i, r in enumerate(failed_list[:10], 1):
            print(f"{i}. {r['address']}")
            print(f"   Heuristic: {r['heuristic']}, Region: {r['region']}, API: {r['api_score']:.4f}")
        if failed > 10:
            print(f"\n... and {failed - 10} more failed addresses")
    
    # Test with batch validator (using all 50 addresses)
    print("\n" + "="*80)
    print("BATCH VALIDATION (using _grade_address_variations)")
    print("="*80)
    print(f"Using all {len(cambodia_addresses)} addresses for batch validation...\n")
    
    variations = {
        "Test Name": [
            ["Test Name", "1990-01-01", addr] for addr in cambodia_addresses
        ]
    }
    
    seed_addresses = ["Cambodia"] * len(variations)
    
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
    
    print(f"Overall Score: {overall_score:.4f}")
    print(f"Heuristic Perfect: {heuristic_perfect}")
    print(f"Region Matches: {region_matches}/{len(cambodia_addresses)}")
    print(f"API Result: {api_result}")
    print(f"Status: {'✅ PASS' if overall_score >= 0.9 else '❌ FAIL'}")
    
    # Save results
    output_file = "cambodia_50_addresses_validation_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "test_date": __import__('datetime').datetime.now().isoformat(),
            "addresses": cambodia_addresses,
            "individual_results": results,
            "batch_validation": validation_result,
            "summary": {
                "total": len(results),
                "score_10": passed_10,
                "score_09": passed_09,
                "failed": failed,
                "overall_score": overall_score,
                "passing_addresses": [r['address'] for r in results if r['api_score'] >= 0.9]
            }
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Detailed results saved to {output_file}")

if __name__ == '__main__':
    main()

