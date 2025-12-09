#!/usr/bin/env python3
"""
Detailed test of Algeria addresses - check each address individually
"""

import os
import sys
import json
import time

# Add MIID validator to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

from reward import check_with_nominatim, looks_like_address, validate_address_region

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
    """Test all Algeria addresses individually"""
    algeria_addresses = [
        "1003, Cite Sakiet Sidi Youcef, Constantine, 25000, Algeria",
        "1004, ساقية سيدي يوسف, Constantine, 25000, Algeria",
        "16, Unité de Protection civile, 16000, Algeria",
        "22, Cité 632 Logements, Mohammadia, 16058, Algeria",
        "23, Cité 632 Logements, Mohammadia, 16058, Algeria",
        "24, Cité 632 Logements, Mohammadia, 16058, Algeria",
        "25, Cité 632 Logements, Mohammadia, 16058, Algeria",
        "BNP Paribas El Djazaïr, حيدرة, 16035, Algeria",
        "Bureau de poste de Birtouta, 16045, Algeria",
        "Caisse Nationale des Assurances Sociales des Travailleurs Salariés, Oran, 31000, Algeria",
        "Ecole Normale Supérieure de Constantine, Constantine, 25000, Algeria",
        "Hôtel militaire, Constantine, 25000, Algeria",
        "Pizza Pino, Bir Mourad Raïs, 16035, Algeria",
        "Pâtisserie les falaises, Constantine, 25000, Algeria",
        "Salle de musculation, Constantine, 25000, Algeria"
    ]
    
    print("="*80)
    print("DETAILED VALIDATION OF ALGERIA ADDRESSES")
    print("="*80)
    print(f"\n📋 Testing {len(algeria_addresses)} addresses individually\n")
    
    results = []
    for i, address in enumerate(algeria_addresses, 1):
        print(f"[{i}/{len(algeria_addresses)}] Testing: {address[:60]}...")
        result = test_individual_address(address, "Algeria")
        results.append(result)
        
        # Print result
        status_icon = "✅" if result["status"] == "PASS" else "⚠️" if result["status"] == "PASS_09" else "❌"
        print(f"     {status_icon} Heuristic: {result['heuristic']}, Region: {result['region']}, API: {result['api_score']:.4f} ({result['api_result']})")
        print()
    
    # Summary
    print("="*80)
    print("SUMMARY")
    print("="*80)
    
    passed_10 = sum(1 for r in results if r["status"] == "PASS" and r["api_score"] >= 0.99)
    passed_09 = sum(1 for r in results if r["status"] == "PASS_09" and 0.9 <= r["api_score"] < 0.99)
    failed = sum(1 for r in results if r["status"] == "FAIL")
    
    print(f"✅ Score 1.0: {passed_10}/15")
    print(f"⚠️  Score 0.9: {passed_09}/15")
    print(f"❌ Failed: {failed}/15")
    print()
    
    # Show failed addresses
    if failed > 0:
        print("Failed addresses:")
        for r in results:
            if r["status"] == "FAIL":
                print(f"  ❌ {r['address']}")
                print(f"     Heuristic: {r['heuristic']}, Region: {r['region']}, API: {r['api_score']:.4f} ({r['api_result']})")
    
    # Test with batch validator
    print("\n" + "="*80)
    print("BATCH VALIDATION (using _grade_address_variations)")
    print("="*80)
    
    from reward import _grade_address_variations
    
    variations = {
        "Test Name": [
            ["Test Name", "1990-01-01", addr] for addr in algeria_addresses
        ]
    }
    
    seed_addresses = ["Algeria"] * len(variations)
    
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
    print(f"Region Matches: {region_matches}/15")
    print(f"API Result: {api_result}")
    print(f"Status: {'✅ PASS' if overall_score >= 0.9 else '❌ FAIL'}")
    
    # Save results
    output_file = "algeria_detailed_validation_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "test_date": __import__('datetime').datetime.now().isoformat(),
            "addresses": algeria_addresses,
            "individual_results": results,
            "batch_validation": validation_result,
            "summary": {
                "total": len(results),
                "score_10": passed_10,
                "score_09": passed_09,
                "failed": failed,
                "overall_score": overall_score
            }
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Detailed results saved to {output_file}")

if __name__ == '__main__':
    main()
