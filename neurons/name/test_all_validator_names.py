#!/usr/bin/env python3
"""
Test the exhaustive generation system with all 15 names from the validator synapse.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

from generate_and_test_variations import generate_full_name_variations, test_with_rewards

# All 15 names from the validator synapse
NAMES = [
    "joel miller",
    "Mohamud Abdirahman",
    "sara lopez",
    "sydney stewart",
    "Alimzhon Tokhtakhunov",
    "kevin davenport",
    "Kifah Moulhem",
    "Leonel RIVERA",
    "bertrand lambert",
    "خالد العقيدات",  # Arabic
    "عبدالرّحمن جديس",  # Arabic
    "odette delahaye",  # UAV name
    "Михаил Шеремет",  # Russian
    "robert price",
    "patricia guillaume"
]

# Query template requirements
VARIATION_COUNT = 9
LIGHT_PERCENT = 10  # 10%
MEDIUM_PERCENT = 30  # 30%
FAR_PERCENT = 60  # 60%

# Calculate counts
light_count = max(1, int(VARIATION_COUNT * LIGHT_PERCENT / 100))  # At least 1
medium_count = max(1, int(VARIATION_COUNT * MEDIUM_PERCENT / 100))  # At least 1
far_count = VARIATION_COUNT - light_count - medium_count  # Rest go to Far

print("="*80)
print("COMPREHENSIVE TEST: ALL 15 VALIDATOR NAMES")
print("="*80)
print()
print(f"Variation count: {VARIATION_COUNT}")
print(f"Distribution: {light_count} Light ({LIGHT_PERCENT}%), {medium_count} Medium ({MEDIUM_PERCENT}%), {far_count} Far ({FAR_PERCENT}%)")
print()
print("="*80)
print()

results = []

for i, name in enumerate(NAMES, 1):
    print(f"[{i}/15] Testing: '{name}'")
    print("-" * 80)
    
    try:
        # Generate variations
        variations = generate_full_name_variations(
            name,
            light_count=light_count,
            medium_count=medium_count,
            far_count=far_count,
            verbose=False  # Less verbose for batch testing
        )
        
        if len(variations) >= VARIATION_COUNT * 0.7:
            # Test with rewards.py
            final_score, base_score, detailed_metrics = test_with_rewards(
                name,
                variations,
                expected_count=VARIATION_COUNT,
                light_count=light_count,
                medium_count=medium_count,
                far_count=far_count
            )
            
            # Extract phonetic similarity
            first_phonetic = 0.0
            last_phonetic = 0.0
            
            if "first_name" in detailed_metrics and "metrics" in detailed_metrics["first_name"]:
                first_metrics = detailed_metrics["first_name"]["metrics"]
                if "similarity" in first_metrics:
                    first_phonetic = first_metrics["similarity"].get("phonetic", 0.0)
            
            if "last_name" in detailed_metrics and "metrics" in detailed_metrics["last_name"]:
                last_metrics = detailed_metrics["last_name"]["metrics"]
                if "similarity" in last_metrics:
                    last_phonetic = last_metrics["similarity"].get("phonetic", 0.0)
            
            results.append({
                "name": name,
                "variations_count": len(variations),
                "final_score": final_score,
                "base_score": base_score,
                "first_phonetic": first_phonetic,
                "last_phonetic": last_phonetic,
                "success": first_phonetic >= 0.99 and last_phonetic >= 0.99
            })
            
            status = "✅ PERFECT" if results[-1]["success"] else "⚠️  NEEDS WORK"
            print(f"  {status}")
            print(f"  Variations: {len(variations)}/{VARIATION_COUNT}")
            print(f"  Final score: {final_score:.4f}")
            print(f"  Base score: {base_score:.4f}")
            print(f"  First phonetic: {first_phonetic:.4f}")
            print(f"  Last phonetic: {last_phonetic:.4f}")
        else:
            results.append({
                "name": name,
                "variations_count": len(variations),
                "final_score": 0.0,
                "base_score": 0.0,
                "first_phonetic": 0.0,
                "last_phonetic": 0.0,
                "success": False
            })
            print(f"  ❌ FAILED: Only {len(variations)}/{VARIATION_COUNT} variations")
    
    except Exception as e:
        print(f"  ❌ ERROR: {str(e)}")
        results.append({
            "name": name,
            "variations_count": 0,
            "final_score": 0.0,
            "base_score": 0.0,
            "first_phonetic": 0.0,
            "last_phonetic": 0.0,
            "success": False,
            "error": str(e)
        })
    
    print()

# Summary
print("="*80)
print("SUMMARY")
print("="*80)
print()

perfect_count = sum(1 for r in results if r["success"])
total_count = len(results)

print(f"Perfect phonetic similarity (1.0): {perfect_count}/{total_count}")
print()

print("Detailed Results:")
print("-" * 80)
for r in results:
    status = "✅" if r["success"] else "⚠️"
    print(f"{status} {r['name']:30s} | "
          f"Vars: {r['variations_count']:2d}/{VARIATION_COUNT} | "
          f"Score: {r['final_score']:.4f} | "
          f"First: {r['first_phonetic']:.4f} | "
          f"Last: {r['last_phonetic']:.4f}")

print()
print("="*80)
print(f"Overall Success Rate: {perfect_count}/{total_count} ({100*perfect_count/total_count:.1f}%)")
print("="*80)

