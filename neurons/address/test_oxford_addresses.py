#!/usr/bin/env python3
"""
Test Oxford addresses using mock validator
"""

import os
import sys
import time

# Add MIID validator to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
sys.path.insert(0, os.path.join(BASE_DIR, 'MIID', 'validator'))

# Import validation functions
from reward import _grade_address_variations

# Test addresses
test_addresses = [
    "1 Walton Street, Oxford, OX1 2HG, United Kingdom",
    "15 King Edward Street, Oxford, OX1 4HL, United Kingdom",
    "14 Queen's Lane, Oxford, OX1 4BZ, United Kingdom",
    "3 Grove Street, Oxford, OX1 4DS, United Kingdom",
    "7 Ship Street, Oxford, OX1 3DA, United Kingdom",
    "6 Bath Place, Oxford, OX1 3SU, United Kingdom",
    "12 Park Town, Oxford, OX2 6SJ, United Kingdom",
    "9 Museum Road, Oxford, OX1 3PX, United Kingdom",
    "8 St John Street, Oxford, OX1 2LG, United Kingdom",
    "22 Wellington Square, Oxford, OX1 2HY, United Kingdom",
    "10 Kybald Street, Oxford, OX1 3EP, United Kingdom",
    "11 Holywell Street, Oxford, OX1 3SD, United Kingdom",
    "5 St Michael's Street, Oxford, OX1 2DR, United Kingdom",
    "4 Longwall Street, Oxford, OX1 3TB, United Kingdom",
    "16 Canterbury Road, Oxford, OX2 6LU, United Kingdom"
]

# Seed address (for region validation)
seed_address = "United Kingdom"

def main():
    print("=" * 80)
    print("TESTING OXFORD ADDRESSES WITH MOCK VALIDATOR")
    print("=" * 80)
    print(f"\nTesting {len(test_addresses)} addresses as a batch...\n")
    
    # Create variations dict with ALL addresses: {name: [[name_var, dob_var, address_var], ...]}
    variations = {
        "Test": [["Test", "1990-01-01", addr] for addr in test_addresses]
    }
    
    print(f"📋 Testing all {len(test_addresses)} addresses together...")
    print(f"🌍 Seed Address: {seed_address}\n")
    
    # Grade all address variations together
    try:
        score_details = _grade_address_variations(
            variations=variations,
            seed_addresses=[seed_address],
            miner_metrics={},
            validator_uid=101,
            miner_uid=501
        )
        
        print("\n" + "=" * 80)
        print("VALIDATION RESULTS")
        print("=" * 80)
        
        if score_details:
            overall_score = score_details.get('overall_score', 0.0)
            heuristic_perfect = score_details.get('heuristic_perfect', False)
            region_matches = score_details.get('region_matches', 0)
            total_addresses = score_details.get('total_addresses', len(test_addresses))
            
            print(f"\n📊 FINAL ADDRESS SCORE: {overall_score:.4f}")
            print(f"✅ Heuristic Check: {'PASSED' if heuristic_perfect else 'FAILED'}")
            print(f"🌍 Region Matches: {region_matches}/{total_addresses}")
            
            # Show detailed breakdown
            detailed_breakdown = score_details.get('detailed_breakdown', {})
            api_validation = detailed_breakdown.get('api_validation', {})
            
            if api_validation:
                print(f"\n📡 API Validation Details:")
                print(f"   Total eligible addresses: {api_validation.get('total_eligible_addresses', 0)}")
                print(f"   API calls made: {api_validation.get('total_calls', 0)}")
                print(f"   Successful calls: {api_validation.get('total_successful_calls', 0)}")
                
                # Show individual API attempts
                api_attempts = api_validation.get('api_attempts', [])
                if api_attempts:
                    print(f"\n   Individual API Results:")
                    for i, attempt in enumerate(api_attempts, 1):
                        addr = attempt.get('address', 'N/A')
                        result_val = attempt.get('result', 'N/A')
                        score_details_api = attempt.get('score_details', {}) or {}
                        
                        if isinstance(result_val, (int, float)):
                            area = score_details_api.get('min_area', 'N/A') if score_details_api else 'N/A'
                            status = "✅" if result_val >= 0.99 else "❌"
                            print(f"   {status} [{i}] {addr[:60]}...")
                            print(f"        Score: {result_val:.4f}, Area: {area} m²")
                        elif result_val == "TIMEOUT":
                            print(f"   ⏱️  [{i}] {addr[:60]}... (TIMEOUT)")
                        else:
                            print(f"   ❌ [{i}] {addr[:60]}... (FAILED)")
            
            # Score interpretation
            print("\n" + "-" * 80)
            print("SCORE INTERPRETATION:")
            if overall_score >= 0.99:
                print("   ✅ EXCELLENT: Score >= 0.99 (Perfect)")
            elif overall_score >= 0.8:
                print("   ⚠️  GOOD: Score >= 0.8 (Acceptable)")
            elif overall_score >= 0.3:
                print("   ⚠️  POOR: Score >= 0.3 (Minimum threshold)")
            else:
                print("   ❌ FAILED: Score < 0.3 (Rejected)")
            print("=" * 80)
            
            return overall_score
        else:
            print("❌ No score details returned")
            return 0.0
    
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 0.0

if __name__ == "__main__":
    main()

