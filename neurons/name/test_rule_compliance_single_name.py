#!/usr/bin/env python3
"""
Test rule compliance for a single name - generate variations and check rule compliance.
"""

import sys
import os
import json

# Add paths
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

from variation_generator_clean import generate_name_variations_clean
from MIID.validator.rule_evaluator import evaluate_rule_compliance, RULE_EVALUATORS

def test_rule_compliance_for_name(name: str, rules: list, rule_percentage: float = 0.3):
    """
    Test rule compliance for a single name.
    
    Args:
        name: The original name
        rules: List of rule names to test
        rule_percentage: Percentage of variations that should be rule-based
    """
    print("=" * 80)
    print(f"TESTING RULE COMPLIANCE FOR: '{name}'")
    print("=" * 80)
    print()
    
    # Generate variations
    print(f"Generating 15 variations with {rule_percentage*100:.0f}% rule compliance...")
    print(f"Target rules: {rules}")
    print()
    
    variations = generate_name_variations_clean(
        original_name=name,
        variation_count=15,
        rule_percentage=rule_percentage,
        rules=rules,
        phonetic_similarity={"Light": 0.2, "Medium": 0.6, "Far": 0.2},
        orthographic_similarity={"Light": 0.2, "Medium": 0.6, "Far": 0.2}
    )
    
    print(f"Generated {len(variations)} variations:")
    for i, var in enumerate(variations, 1):
        print(f"  {i:2d}. {var}")
    print()
    
    # Check rule compliance
    print("Checking rule compliance...")
    compliant_by_rule, compliance_ratio = evaluate_rule_compliance(
        original_name=name,
        variations=variations,
        rules=rules
    )
    
    print()
    print("=" * 80)
    print("RULE COMPLIANCE RESULTS")
    print("=" * 80)
    print(f"Overall compliance ratio: {compliance_ratio:.3f} ({compliance_ratio*100:.1f}%)")
    print(f"Expected: {rule_percentage*100:.0f}%")
    print()
    
    # Show which variations match which rules
    print("Variations by Rule:")
    print("-" * 80)
    for rule in rules:
        compliant_vars = compliant_by_rule.get(rule, [])
        print(f"  {rule}:")
        if compliant_vars:
            print(f"    ✅ {len(compliant_vars)} variations match:")
            for var in compliant_vars:
                print(f"       - {var}")
        else:
            print(f"    ❌ 0 variations match")
    print()
    
    # Show which variations don't match any rules
    all_compliant = set()
    for rule_vars in compliant_by_rule.values():
        all_compliant.update(rule_vars)
    
    non_compliant = [var for var in variations if var not in all_compliant]
    if non_compliant:
        print(f"Non-compliant variations ({len(non_compliant)}):")
        for var in non_compliant:
            print(f"  - {var}")
        print()
    
    # Test each variation individually
    print("=" * 80)
    print("DETAILED RULE CHECK FOR EACH VARIATION")
    print("=" * 80)
    for i, var in enumerate(variations, 1):
        print(f"\n{i:2d}. Variation: '{var}'")
        matches = []
        for rule in rules:
            if rule in RULE_EVALUATORS:
                try:
                    evaluator = RULE_EVALUATORS[rule]
                    if evaluator(name, var):
                        matches.append(rule)
                        print(f"    ✅ Matches: {rule}")
                except Exception as e:
                    print(f"    ❌ Error checking {rule}: {e}")
        
        if not matches:
            print(f"    ❌ No rules matched")
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Name: {name}")
    print(f"Total variations: {len(variations)}")
    print(f"Compliant variations: {len(all_compliant)}")
    print(f"Non-compliant variations: {len(non_compliant)}")
    print(f"Compliance ratio: {compliance_ratio:.3f}")
    print(f"Target: {rule_percentage:.3f}")
    print(f"Status: {'✅ PASS' if compliance_ratio >= rule_percentage * 0.8 else '❌ FAIL'}")
    print("=" * 80)
    print()

if __name__ == "__main__":
    # Test with a few names
    test_names = [
        "Mohammed ALBASHIR",
        "Fadel Al-Balawi",
        "Vyacheslav Kozhevnikov",
        "John Smith",
        "Maria Garcia"
    ]
    
    rules = ["delete_random_letter", "insert_random_letter", "swap_random_letter"]
    rule_percentage = 0.3
    
    for name in test_names:
        test_rule_compliance_for_name(name, rules, rule_percentage)
        print("\n" * 2)

