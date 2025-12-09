#!/usr/bin/env python3
"""
Test rule compliance for 15 names from sanctioned list.
Report percentage achieved out of 30% target.
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

from maximize_orthographic_similarity import OrthographicBruteForceGenerator
from MIID.validator.rule_evaluator import evaluate_rule_compliance

def test_name_rule_compliance(name: str, rules: list):
    """Test rule compliance for a single name."""
    target_distribution = {"Light": 0.2, "Medium": 0.6, "Far": 0.2}
    rule_based = {
        "selected_rules": rules,
        "rule_percentage": 30
    }
    
    generator = OrthographicBruteForceGenerator(
        original_name=name,
        target_distribution=target_distribution,
        rule_based=rule_based
    )
    
    # Generate variations
    variations, metrics = generator.generate_optimal_variations(variation_count=15)
    
    # Check rule compliance
    compliant_by_rule, compliance_ratio = evaluate_rule_compliance(
        original_name=name,
        variations=variations,
        rules=rules
    )
    
    # Get all compliant variations
    all_compliant = set()
    for rule_vars in compliant_by_rule.values():
        all_compliant.update(rule_vars)
    
    rule_compliant_count = len(all_compliant)
    rule_compliant_percentage = compliance_ratio * 100
    
    return {
        "name": name,
        "rule_compliant_count": rule_compliant_count,
        "rule_compliant_percentage": rule_compliant_percentage,
        "target_percentage": 30.0,
        "difference": rule_compliant_percentage - 30.0,
        "status": "✅ PASS" if rule_compliant_percentage >= 25.0 else "⚠️ LOW" if rule_compliant_percentage >= 20.0 else "❌ FAIL"
    }

def main():
    # Load sanctioned names
    sanctioned_file = os.path.join(os.path.dirname(__file__), "MIID", "validator", "Sanctioned_list.json")
    
    with open(sanctioned_file, 'r', encoding='utf-8') as f:
        sanctioned_data = json.load(f)
    
    # Get first 15 names
    names = []
    for entry in sanctioned_data[:15]:
        if isinstance(entry, dict):
            first_name = entry.get("FirstName", "")
            last_name = entry.get("LastName", "")
            if first_name and last_name:
                name = f"{first_name} {last_name}"
            elif first_name:
                name = first_name
            elif last_name:
                name = last_name
            else:
                name = ""
        else:
            name = str(entry)
        
        if name:
            names.append(name)
    
    print("=" * 100)
    print("RULE COMPLIANCE TEST - 15 NAMES FROM SANCTIONED LIST")
    print("=" * 100)
    print()
    print(f"Target: 30% rule compliance")
    print(f"Testing {len(names)} names...")
    print()
    
    # Mixed rules
    mixed_rules = [
        "delete_random_letter",
        "insert_random_letter",
        "swap_random_letter",
        "remove_all_spaces",
        "replace_spaces_with_random_special_characters",
        "shorten_name_to_initials",
        "name_parts_permutations",
        "initial_only_first_name"
    ]
    
    results = []
    for i, name in enumerate(names, 1):
        print(f"[{i}/{len(names)}] Testing: {name[:50]}")
        result = test_name_rule_compliance(name, mixed_rules)
        results.append(result)
        print(f"  Rule-compliant: {result['rule_compliant_count']}/15 ({result['rule_compliant_percentage']:.1f}%) | Target: 30% | {result['status']}")
        print()
    
    # Summary
    print("=" * 100)
    print("SUMMARY RESULTS")
    print("=" * 100)
    print()
    print(f"{'Name':<40} {'Achieved':<12} {'Target':<10} {'Diff':<10} {'Status':<10}")
    print("-" * 100)
    
    total_achieved = 0
    total_target = 0
    pass_count = 0
    low_count = 0
    fail_count = 0
    
    for r in results:
        print(f"{r['name'][:40]:<40} {r['rule_compliant_percentage']:>6.1f}%      {r['target_percentage']:>6.1f}%    {r['difference']:>+6.1f}%    {r['status']:<10}")
        total_achieved += r['rule_compliant_percentage']
        total_target += r['target_percentage']
        if r['status'] == "✅ PASS":
            pass_count += 1
        elif r['status'] == "⚠️ LOW":
            low_count += 1
        else:
            fail_count += 1
    
    print("-" * 100)
    avg_achieved = total_achieved / len(results)
    avg_target = total_target / len(results)
    avg_diff = avg_achieved - avg_target
    
    print(f"{'AVERAGE':<40} {avg_achieved:>6.1f}%      {avg_target:>6.1f}%    {avg_diff:>+6.1f}%")
    print()
    print("Status Breakdown:")
    print(f"  ✅ PASS (≥25%): {pass_count} names")
    print(f"  ⚠️  LOW (20-24%): {low_count} names")
    print(f"  ❌ FAIL (<20%): {fail_count} names")
    print()
    print("=" * 100)
    print()
    
    # Detailed statistics
    percentages = [r['rule_compliant_percentage'] for r in results]
    print("Statistics:")
    print(f"  Average: {sum(percentages)/len(percentages):.2f}%")
    print(f"  Minimum: {min(percentages):.2f}%")
    print(f"  Maximum: {max(percentages):.2f}%")
    print(f"  Median: {sorted(percentages)[len(percentages)//2]:.2f}%")
    print()
    
    # Names that achieved ≥30%
    high_achievers = [r for r in results if r['rule_compliant_percentage'] >= 30.0]
    if high_achievers:
        print(f"Names achieving ≥30% ({len(high_achievers)}):")
        for r in high_achievers:
            print(f"  • {r['name']}: {r['rule_compliant_percentage']:.1f}%")
        print()
    
    # Names that achieved <25%
    low_achievers = [r for r in results if r['rule_compliant_percentage'] < 25.0]
    if low_achievers:
        print(f"Names achieving <25% ({len(low_achievers)}):")
        for r in low_achievers:
            print(f"  • {r['name']}: {r['rule_compliant_percentage']:.1f}%")
        print()

if __name__ == "__main__":
    main()

