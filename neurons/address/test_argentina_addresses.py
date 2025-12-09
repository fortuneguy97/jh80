#!/usr/bin/env python3
"""
Test Argentina addresses from validated_address_cache_priority.json
against the rewards.py validator to check if they score 1.0
"""

import os
import sys
import json

# Add MIID validator to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

from reward import _grade_address_variations

CACHE_FILE = os.path.join(os.path.dirname(__file__), "validated_address_cache_priority.json")

def test_addresses_with_validator(country: str, addresses: list, verbose: bool = True) -> dict:
    """Test addresses using _grade_address_variations from rewards.py"""
    if not addresses:
        return {
            "country": country,
            "addresses_tested": 0,
            "overall_score": 0.0,
            "heuristic_perfect": False,
            "region_matches": 0,
            "api_result": "NO_ADDRESSES",
            "status": "FAIL"
        }
    
    # Format addresses like validator expects
    variations = {
        "Test Name": [
            ["Test Name", "1990-01-01", addr] for addr in addresses
        ]
    }
    
    # Seed addresses (one per name)
    seed_addresses = [country] * len(variations)
    
    # Call _grade_address_variations
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
    
    return {
        "country": country,
        "addresses_tested": len(addresses),
        "overall_score": overall_score,
        "heuristic_perfect": heuristic_perfect,
        "region_matches": region_matches,
        "api_result": api_result,
        "status": "PASS" if overall_score >= 0.9 else "FAIL"
    }

def main():
    """Main function to test Argentina addresses from cache"""
    # Argentina addresses from user
    argentina_addresses = [
        "1550 Avenida Cabildo, Buenos Aires, C1426, Argentina",
        "2447 Avenida Santa Fe, Buenos Aires, C1123, Argentina",
        "1055 San Juan, Rosario, 2000, Argentina",
        "990 Avenida José de San Martín, Granadero Baigorria, 2152, Argentina",
        "1001 Avenida Francia, Rosario, 2002, Argentina",
        "902 Vera Mujíca, Rosario, 2002, Argentina",
        "1925 Alvarez Thomas, Rosario, 2000, Argentina",
        "1101 Balcarce, Rosario, 2000, Argentina",
        "1399 Balcarce, Rosario, 2000, Argentina",
        "1601 Balcarce, Rosario, 2000, Argentina",
        "1799 Mariano Moreno, Rosario, 2000, Argentina",
        "2301 Mariano Moreno, Rosario, 2000, Argentina",
        "1299 España, Rosario, 2000, Argentina",
        "1501 España, Rosario, 2000, Argentina",
        "1001 Montevideo, Rosario, 2000, Argentina"
    ]
    
    print("="*80)
    print("TESTING ARGENTINA ADDRESSES WITH VALIDATOR")
    print("="*80)
    print(f"\n📋 Testing {len(argentina_addresses)} addresses for Argentina\n")
    
    # Test the addresses
    result = test_addresses_with_validator("Argentina", argentina_addresses, verbose=True)
    
    # Print results
    print("\n" + "="*80)
    print("VALIDATION RESULTS")
    print("="*80)
    print(f"Country: {result['country']}")
    print(f"Addresses tested: {result['addresses_tested']}")
    print(f"Overall Score: {result['overall_score']:.4f}")
    print(f"Heuristic Perfect: {result['heuristic_perfect']}")
    print(f"Region Matches: {result['region_matches']}/{result['addresses_tested']}")
    print(f"API Result: {result['api_result']}")
    print(f"\nStatus: {'✅ PASS' if result['status'] == 'PASS' else '❌ FAIL'}")
    print("="*80)
    
    # Save results
    output_file = "argentina_validation_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "test_date": __import__('datetime').datetime.now().isoformat(),
            "addresses": argentina_addresses,
            "validation_result": result
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Results saved to {output_file}")

if __name__ == '__main__':
    main()

