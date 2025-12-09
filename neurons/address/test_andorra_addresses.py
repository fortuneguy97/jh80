#!/usr/bin/env python3
"""
Test Andorra addresses from validated cache using _grade_address_variations from rewards.py
"""

import os
import sys
import json

# Add MIID validator to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, 'MIID', 'validator'))

from reward import _grade_address_variations

# Andorra addresses from validated cache
andorra_addresses = [
    "53, Avinguda de Tarragona, Andorra la Vella, AD500, Andorra",
    "3, Carrer de l'obac, Escaldes-Engordany, AD700, Andorra",
    "15, Avinguda Doctor Mitjavila, Andorra la Vella, AD500, Andorra",
    "69, Avinguda Meritxell, Andorra la Vella, AD500, Andorra",
    "71, Avinguda Meritxell, Andorra la Vella, AD500, Andorra",
    "61, Avinguda Meritxell, Andorra la Vella, AD500, Andorra",
    "59, Avinguda Meritxell, Andorra la Vella, AD500, Andorra",
    "88, Avinguda Meritxell, Andorra la Vella, AD500, Andorra",
    "51, Carrer Pau Casals, Andorra la Vella, AD500, Andorra",
    "94, Avinguda Meritxell, Andorra la Vella, AD500, Andorra",
    "22, Carrer de la Geneta, Juberri, AD600, Andorra",
    "87, Avinguda del Princep Benlloch, Andorra la Vella, AD500, Andorra",
    "30, Avinguda del Princep Benlloch, Andorra la Vella, AD500, Andorra",
    "Sant Esteve de Juberri, Juberri, AD600, Andorra",
    "Residential de l'Aldosa, L'Aldosa, AD400, Andorra"
]

print("=" * 80)
print("TESTING ANDORRA ADDRESSES WITH rewards.py")
print("=" * 80)
print(f"Total addresses: {len(andorra_addresses)}")
print()

# Format addresses for _grade_address_variations
variations = {
    'Test': [['Test', '1990-01-01', addr] for addr in andorra_addresses]
}

# Call _grade_address_variations
print("Calling _grade_address_variations from rewards.py...")
print()

result = _grade_address_variations(
    variations=variations,
    seed_addresses=['Andorra'],
    miner_metrics={},
    validator_uid=101,
    miner_uid=501
)

# Display results
print("=" * 80)
print("VALIDATION RESULTS")
print("=" * 80)
print(f"Overall Score: {result.get('overall_score', 0.0):.4f}")
print(f"Heuristic Perfect: {result.get('heuristic_perfect', False)}")
print(f"Region Matches: {result.get('region_matches', 0)}/{len(andorra_addresses)}")
print(f"Total Addresses: {result.get('total_addresses', 0)}")
print(f"API Result: {result.get('api_result', 'N/A')}")
print()

# Detailed breakdown
breakdown = result.get('detailed_breakdown', {})
api_validation = breakdown.get('api_validation', {})

if api_validation:
    print("API Validation Details:")
    print(f"  Total eligible: {api_validation.get('total_eligible_addresses', 0)}")
    print(f"  API calls made: {api_validation.get('total_calls', 0)}")
    print(f"  Successful: {api_validation.get('total_successful_calls', 0)}")
    print(f"  Failed: {api_validation.get('total_failed_calls', 0)}")
    print()
    
    api_attempts = api_validation.get('api_attempts', [])
    if api_attempts:
        print("Individual API Results:")
        print()
        for i, attempt in enumerate(api_attempts, 1):
            addr = attempt.get('address', 'N/A')
            api_result_val = attempt.get('result', 'N/A')
            score_details = attempt.get('score_details', {}) or {}
            
            if isinstance(api_result_val, (int, float)):
                area = score_details.get('min_area', 'N/A') if score_details else 'N/A'
                status = "✅" if api_result_val >= 0.99 else "❌"
                print(f"  {status} [{i}] {addr[:60]}...")
                print(f"      Score: {api_result_val:.4f}, Area: {area} m²")
            elif api_result_val == "TIMEOUT":
                print(f"  ⏱️  [{i}] {addr[:60]}...")
                print(f"      Status: TIMEOUT")
            else:
                print(f"  ❌ [{i}] {addr[:60]}...")
                print(f"      Status: FAILED (Score: {api_result_val})")
            print()

# Address breakdown
validation_results = breakdown.get('validation_results', {})
if validation_results:
    test_results = validation_results.get('Test', [])
    if test_results:
        print("Individual Address Validation:")
        print()
        passed = 0
        failed = 0
        for i, addr_result in enumerate(test_results, 1):
            addr = addr_result.get('address', 'N/A')
            looks_like = addr_result.get('looks_like_address', False)
            region_match = addr_result.get('region_match', False)
            passed_val = addr_result.get('passed_validation', False)
            status = "✅" if passed_val else "❌"
            
            if passed_val:
                passed += 1
            else:
                failed += 1
            
            print(f"  {status} [{i}] {addr[:60]}...")
            print(f"      Heuristic: {looks_like}, Region: {region_match}, Passed: {passed_val}")
            print()
        
        print(f"Summary: {passed} passed, {failed} failed")
        print()

print("=" * 80)

# Save results
output_file = "andorra_validation_results.json"
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump({
        "addresses": andorra_addresses,
        "validation_result": result,
        "count": len(andorra_addresses)
    }, f, indent=2, ensure_ascii=False)

print(f"\n💾 Results saved to {output_file}")

