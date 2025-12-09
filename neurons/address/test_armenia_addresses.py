#!/usr/bin/env python3
"""
Test Armenia addresses from cache using _grade_address_variations from rewards.py
"""

import os
import sys
import json

# Add MIID validator to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, 'MIID', 'validator'))

# Import from rewards.py
from reward import _grade_address_variations

# Armenia addresses from cache
armenia_addresses = [
    "Արթ Սվիթ, 122 Նաիրի Զարյան փողոց, Երևան, 0014, Armenia",
    "Կոնվերս Բանկ, 26/1 Վազգեն Սարգսյանի փողոց, Երևան, 0010, Armenia",
    "Կոնվերս Բանկ, 19 Սայաթ-Նովայի պողոտա, Երևան, 0001, Armenia",
    "Կոնվերս Բանկ, 39/12 Մեսրոպ Մաշտոցի պողոտա, Երևան, 0002, Armenia",
    "Օլդ Մարանի, 7 Ալեք Մանուկյանի փողոց, Երևան, Armenia",
    "Թումանյան Շաուրմա, 32 Թումանյան փողոց, Armenia",
    "Խնկո Ապոր գրադարան, 42/1 Տերյան փողոց, Երևան, 0001, Armenia",
    "Pizza di Roma, 31 Մովսես Խորենացու փողոց, Երևան, Armenia",
    "Next, 13 Ամիրյան փողոց, Երևան, 0002, Armenia",
    "HSBC, 31 Մովսես Խորենացու փողոց, Երևան, Armenia",
    "Արդշինբանկ, 24 Տիգրան Մեծի պողոտա, Երևան, Armenia",
    "Grand Hotel Yerevan Royal Tulip, 14 Աբովյան փողոց, Երևան, 0001, Armenia",
    "Ինեկոբանկ, 17 Թումանյան փողոց, Երևան, 0001, Armenia",
    "Եվրոպա, 38 Հանրապետության փողոց, Երևան, 0010, Armenia",
    "Chalet, 8/1 Խանջյան փողոց, Երևան, Armenia"
]

def test_armenia_addresses():
    """Test Armenia addresses with _grade_address_variations"""
    
    print("=" * 80)
    print("TESTING ARMENIA ADDRESSES WITH rewards.py")
    print("=" * 80)
    print(f"Total addresses: {len(armenia_addresses)}")
    print()
    
    # Format addresses for _grade_address_variations
    # Format: variations = {'Test': [['Name', 'DOB', 'Address'], ...]}
    variations = {
        'Test': [['Test', '1990-01-01', addr] for addr in armenia_addresses]
    }
    
    # Call _grade_address_variations
    print("Calling _grade_address_variations from rewards.py...")
    print()
    
    result = _grade_address_variations(
        variations=variations,
        seed_addresses=['Armenia'],
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
    print(f"Region Matches: {result.get('region_matches', 0)}/{len(armenia_addresses)}")
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
                    print(f"      Status: FAILED")
                print()
    
    # Address breakdown
    address_breakdown = breakdown.get('address_breakdown', {})
    if address_breakdown:
        print("Address Breakdown:")
        print(f"  Total addresses: {len(address_breakdown)}")
        perfect_count = sum(1 for addr_data in address_breakdown.values() 
                           if addr_data.get('overall_score', 0) >= 0.99)
        print(f"  Perfect addresses (score >= 0.99): {perfect_count}/{len(address_breakdown)}")
        print()
    
    print("=" * 80)
    
    return result

if __name__ == "__main__":
    # Set User-Agent if not set
    if not os.getenv("USER_AGENT"):
        os.environ["USER_AGENT"] = "MIIDSubnet/1.0 (contact: test@example.com)"
    
    result = test_armenia_addresses()
    
    # Save results
    output_file = "armenia_validation_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "addresses": armenia_addresses,
            "validation_result": result,
            "count": len(armenia_addresses)
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Results saved to {output_file}")

