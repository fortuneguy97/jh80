#!/usr/bin/env python3
"""
Test which names have rule-compliant variations only in Light category.
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

from maximize_orthographic_similarity import OrthographicBruteForceGenerator
from MIID.validator.rule_evaluator import evaluate_rule_compliance
from MIID.validator.reward import calculate_orthographic_similarity

def categorize_orthographic(original: str, variation: str) -> str:
    """Categorize variation into Light/Medium/Far based on orthographic similarity."""
    score = calculate_orthographic_similarity(original, variation)
    
    if score >= 0.7:
        return "Light"
    elif score >= 0.5:
        return "Medium"
    elif score >= 0.2:
        return "Far"
    else:
        return "VeryFar"

def test_name_for_rule_distribution(name: str, rules: list):
    """Test if rule-compliant variations are distributed across categories."""
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
    
    # Generate rule-compliant variations
    rule_compliant_scored = generator.generate_rule_compliant_variations_with_scores(max_per_rule=100)
    
    # Categorize rule-compliant variations
    categories = {"Light": [], "Medium": [], "Far": [], "VeryFar": []}
    
    for rule, scored_vars in rule_compliant_scored.items():
        for var, score, var_category in scored_vars:
            categories[var_category].append((var, score, rule))
    
    # Check if we have rule-compliant in multiple categories
    has_light = len(categories["Light"]) > 0
    has_medium = len(categories["Medium"]) > 0
    has_far = len(categories["Far"]) > 0
    
    total_rule_compliant = sum(len(v) for v in categories.values())
    
    return {
        "name": name,
        "has_light": has_light,
        "has_medium": has_medium,
        "has_far": has_far,
        "light_count": len(categories["Light"]),
        "medium_count": len(categories["Medium"]),
        "far_count": len(categories["Far"]),
        "total_rule_compliant": total_rule_compliant,
        "issue": not (has_medium or has_far)  # Issue if only Light exists
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
    
    print("=" * 80)
    print("TESTING RULE-COMPLIANT VARIATION DISTRIBUTION")
    print("=" * 80)
    print()
    print(f"Testing {len(names)} names from sanctioned list...")
    print()
    
    rules = ["delete_random_letter", "insert_random_letter", "swap_random_letter"]
    
    results = []
    for name in names:
        print(f"Testing: {name[:50]}")
        result = test_name_for_rule_distribution(name, rules)
        results.append(result)
        print(f"  Rule-compliant: Light={result['light_count']}, Medium={result['medium_count']}, Far={result['far_count']}")
        if result['issue']:
            print(f"  ⚠️  ISSUE: Only Light category has rule-compliant variations")
        else:
            print(f"  ✅ OK: Rule-compliant variations in multiple categories")
        print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    
    names_with_issue = [r for r in results if r['issue']]
    names_ok = [r for r in results if not r['issue']]
    
    print(f"Total names tested: {len(results)}")
    print(f"Names with issue (only Light): {len(names_with_issue)}")
    print(f"Names OK (multiple categories): {len(names_ok)}")
    print()
    
    if names_with_issue:
        print("NAMES WITH ISSUE (rule-compliant only in Light):")
        print("-" * 80)
        for r in names_with_issue:
            print(f"  • {r['name']}")
            print(f"    Rule-compliant: Light={r['light_count']}, Medium={r['medium_count']}, Far={r['far_count']}")
        print()
    
    if names_ok:
        print("NAMES OK (rule-compliant in multiple categories):")
        print("-" * 80)
        for r in names_ok:
            print(f"  • {r['name']}")
            print(f"    Rule-compliant: Light={r['light_count']}, Medium={r['medium_count']}, Far={r['far_count']}")
        print()
    
    # Detailed breakdown
    print("=" * 80)
    print("DETAILED BREAKDOWN")
    print("=" * 80)
    print()
    print(f"{'Name':<40} {'Light':<8} {'Medium':<8} {'Far':<8} {'Status':<10}")
    print("-" * 80)
    for r in results:
        status = "⚠️ ISSUE" if r['issue'] else "✅ OK"
        print(f"{r['name'][:40]:<40} {r['light_count']:<8} {r['medium_count']:<8} {r['far_count']:<8} {status:<10}")

if __name__ == "__main__":
    main()

