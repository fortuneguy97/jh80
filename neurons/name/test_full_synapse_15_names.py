#!/usr/bin/env python3
"""
Test full synapse with 15 names - exact replica from validator
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gemini_generator_hybrid import generate_with_gemini_hybrid, parse_query_template
from MIID.validator.reward import (
    calculate_variation_quality,
    _grade_dob_variations,
    _grade_address_variations,
    MIID_REWARD_WEIGHTS
)


def test_full_synapse():
    """Test the exact synapse from validator logs."""
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY environment variable not set")
        sys.exit(1)
    
    print("="*80)
    print("FULL SYNAPSE TEST - 15 NAMES")
    print("="*80)
    print()
    
    # Exact synapse from logs
    identities = [
        ["Anatoly Vyborny", "1965-6-8", "Russia"],
        ["رشدي مرمش", "1956-03-23", "Hong Kong"],
        ["Leonid Pasechnik", "1970-3-15", "Ukraine"],
        ["Aliaksei Rymasheuski", "1981-6-29", "Belarus"],
        ["denis bonneau", "1991-04-17", "Monaco"],
        ["luce guyon", "1998-03-02", "Turks and Caicos Islands"],
        ["purificación franch", "1982-09-09", "Cuba"],
        ["Ilya Buzin", "1980-8-21", "Russia"],
        ["thibaut marchal", "1995-09-25", "Portugal"],
        ["éric lebrun", "1946-05-15", "Fiji"],
        ["zoé joseph", "1979-08-08", "Thailand"],
        ["ягода пачаръзка", "1994-09-26", "Bulgaria"],
        ["cesar taylor", "1928-07-26", "South Sudan"],
        ["Володимир Бандура", "1990-7-15", "Ukraine"],
        ["alfred boulay", "1943-10-23", "Ivory Coast"]
    ]
    
    # Exact query template from logs
    query_template = """Generate exactly 8 variations of {name}, ensuring phonetic similarity (20% Light, 60% Medium, 20% Far) and orthographic similarity (30% Light, 40% Medium, 30% Far). Approximately 60% of the total 8 variations should follow these rule-based transformations: Additionally, generate variations that perform these transformations: Convert {name} to initials, and Swap random adjacent letters. The following address is the seed country/city to generate address variations for: {address}. Generate unique real addresses within the specified country/city for each variation. The following date of birth is the seed DOB to generate variations for: {dob}."""
    
    uav_seed_name = "purificación franch"
    
    print(f"📋 Query Template:")
    print(f"   Variation count: 8")
    print(f"   Rule percentage: 60%")
    print(f"   Rules: initials, swap_random_letter")
    print(f"   Phonetic: 20% Light, 60% Medium, 20% Far")
    print(f"   Orthographic: 30% Light, 40% Medium, 30% Far")
    print(f"   UAV seed: {uav_seed_name}")
    print()
    
    all_variations = {}
    all_scores = []
    
    # Process each identity (test with first 3 for speed, then all)
    test_count = min(3, len(identities))  # Test with 3 names first
    print(f"⚠️  Testing with first {test_count} names for speed...")
    print()
    
    for i, (name, dob, address) in enumerate(identities[:test_count], 1):
        print(f"[{i}/{test_count}] Processing: {name}")
        print(f"   DOB: {dob}, Address: {address}")
        
        try:
            variations_list = generate_with_gemini_hybrid(name, dob, address, query_template, api_key)
            
            if variations_list:
                all_variations[name] = variations_list
                print(f"   ✅ Generated {len(variations_list)} variations")
            else:
                print(f"   ❌ Failed to generate variations")
                all_variations[name] = []
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            all_variations[name] = []
        
        print()
    
    # Score all variations
    print("="*80)
    print("SCORING ALL NAMES")
    print("="*80)
    print()
    
    seed_names = [id[0] for id in identities]
    seed_dob = [id[1] for id in identities]
    seed_addresses = [id[2] for id in identities]
    
    # Parse requirements
    requirements = parse_query_template(query_template)
    phonetic_sim = requirements.get('phonetic_similarity', {})
    ortho_sim = requirements.get('orthographic_similarity', {})
    rule_based = {
        "selected_rules": requirements.get('rules', []),
        "rule_percentage": int(requirements['rule_percentage'] * 100)
    }
    
    validator_uid = 1
    miner_uid = 1
    miner_metrics = {}
    
    total_name_score = 0.0
    total_dob_score = 0.0
    total_address_score = 0.0
    
    for name in seed_names:
        if name not in all_variations or not all_variations[name]:
            continue
        
        variations_list = all_variations[name]
        variations_dict = {name: variations_list}
        
        # Name scoring
        name_variations = [var[0].lower() if var[0] else "" for var in variations_list if len(var) > 0]
        
        name_quality, base_score, name_metrics = calculate_variation_quality(
            original_name=name,
            variations=name_variations,
            phonetic_similarity=phonetic_sim,
            orthographic_similarity=ortho_sim,
            expected_count=requirements['variation_count'],
            rule_based=rule_based
        )
        
        total_name_score += name_quality
        
        # DOB scoring
        dob_result = _grade_dob_variations(variations_dict, [seed_dob[seed_names.index(name)]], miner_metrics)
        dob_score = dob_result.get("overall_score", 0.0)
        total_dob_score += dob_score
        
        # Address scoring
        address_result = _grade_address_variations(
            variations_dict, 
            [seed_addresses[seed_names.index(name)]], 
            miner_metrics, 
            validator_uid, 
            miner_uid
        )
        address_score = address_result.get("overall_score", 0.0)
        total_address_score += address_score
    
    # Calculate averages
    num_names = len([n for n in seed_names if n in all_variations and all_variations[n]])
    if num_names > 0:
        avg_name_score = total_name_score / num_names
        avg_dob_score = total_dob_score / num_names
        avg_address_score = total_address_score / num_names
    else:
        avg_name_score = 0.0
        avg_dob_score = 0.0
        avg_address_score = 0.0
    
    # Final score
    name_component = avg_name_score * 0.2
    dob_component = avg_dob_score * 0.1
    address_component = avg_address_score * 0.7
    final_score = name_component + dob_component + address_component
    
    print("="*80)
    print("FINAL SCORE SUMMARY")
    print("="*80)
    print()
    print(f"Names Processed: {num_names}/{test_count}")
    print()
    print(f"Average Name Quality: {avg_name_score:.4f}")
    print(f"Average DOB Score: {avg_dob_score:.4f}")
    print(f"Average Address Score: {avg_address_score:.4f}")
    print()
    print(f"Name Component (20%):  {name_component:.4f}")
    print(f"DOB Component (10%):   {dob_component:.4f}")
    print(f"Address Component (70%): {address_component:.4f}")
    print(f"{'='*80}")
    print(f"FINAL SCORE: {final_score:.4f}")
    print(f"{'='*80}")
    print()
    
    # Save results
    results = {
        "identities": identities,
        "query_template": query_template,
        "variations": all_variations,
        "scores": {
            "avg_name_quality": avg_name_score,
            "avg_dob_score": avg_dob_score,
            "avg_address_score": avg_address_score,
            "name_component": name_component,
            "dob_component": dob_component,
            "address_component": address_component,
            "final_score": final_score
        },
        "num_names_processed": num_names
    }
    
    with open("test_full_synapse_15_names_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Results saved to: test_full_synapse_15_names_results.json")
    
    return final_score


if __name__ == "__main__":
    score = test_full_synapse()
    print(f"\n{'✅ PASS' if score >= 0.8 else '❌ FAIL'}: Final Score = {score:.4f} (Target: 0.8)")
    sys.exit(0 if score >= 0.8 else 1)
