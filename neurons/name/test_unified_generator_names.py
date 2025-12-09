#!/usr/bin/env python3
"""
Test the unified generator for name generation
Following the documentation in UNIFIED_GENERATOR_EXPLANATION.md
"""

import sys
import os

# Add MIID/validator to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

from unified_generator import (
    generate_full_name_variations,
    generate_perfect_dob_variations,
    test_with_rewards
)

def main():
    """Test unified generator name generation"""
    print("="*80)
    print("TESTING UNIFIED GENERATOR - NAME GENERATION")
    print("="*80)
    print()
    
    # Test names
    test_names = [
        "John Smith",
        "Maria Garcia", 
        "Ahmed Hassan"
    ]
    
    # Configuration
    light_count = 2   # 20% of 10
    medium_count = 6  # 60% of 10
    far_count = 2     # 20% of 10
    total_count = light_count + medium_count + far_count
    
    print(f"Configuration:")
    print(f"  Light variations: {light_count} (20%)")
    print(f"  Medium variations: {medium_count} (60%)")
    print(f"  Far variations: {far_count} (20%)")
    print(f"  Total: {total_count}")
    print()
    print("="*80)
    print()
    
    all_results = {}
    
    for test_name in test_names:
        print(f"\n{'='*80}")
        print(f"TESTING: {test_name}")
        print(f"{'='*80}\n")
        
        # Generate name variations
        print("Step 1: Generating name variations...")
        print("-" * 80)
        name_variations = generate_full_name_variations(
            full_name=test_name,
            light_count=light_count,
            medium_count=medium_count,
            far_count=far_count,
            verbose=True
        )
        
        print(f"\n✅ Generated {len(name_variations)} name variations:")
        print("-" * 80)
        for i, var in enumerate(name_variations, 1):
            if i <= light_count:
                category = "Light"
            elif i <= light_count + medium_count:
                category = "Medium"
            else:
                category = "Far"
            print(f"  {i:2d}. {var:30s} [{category}]")
        
        # Generate DOB variations
        print(f"\nStep 2: Generating DOB variations...")
        print("-" * 80)
        seed_dob = "1990-01-15"
        dob_variations = generate_perfect_dob_variations(seed_dob, variation_count=total_count)
        
        print(f"✅ Generated {len(dob_variations)} DOB variations:")
        print("-" * 80)
        for i, var in enumerate(dob_variations, 1):
            print(f"  {i:2d}. {var}")
        
        # Test with rewards.py
        print(f"\nStep 3: Testing with rewards.py...")
        print("-" * 80)
        final_score, base_score, detailed_metrics = test_with_rewards(
            full_name=test_name,
            variations=name_variations,
            expected_count=total_count,
            light_count=light_count,
            medium_count=medium_count,
            far_count=far_count
        )
        
        # Store results
        all_results[test_name] = {
            'name_variations': name_variations,
            'dob_variations': dob_variations,
            'final_score': final_score,
            'base_score': base_score,
            'detailed_metrics': detailed_metrics
        }
        
        print(f"\n{'='*80}")
        print(f"RESULTS FOR: {test_name}")
        print(f"{'='*80}")
        print(f"  Final Score: {final_score:.4f}")
        print(f"  Base Score: {base_score:.4f}")
        print(f"  Name Variations: {len(name_variations)}")
        print(f"  DOB Variations: {len(dob_variations)}")
        print()
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print()
    print(f"{'Name':<20} {'Variations':<12} {'Final Score':<12} {'Base Score':<12}")
    print("-" * 80)
    for name, results in all_results.items():
        print(f"{name:<20} {len(results['name_variations']):<12} {results['final_score']:<12.4f} {results['base_score']:<12.4f}")
    print()
    print("="*80)

if __name__ == "__main__":
    main()

