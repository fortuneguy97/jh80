#!/usr/bin/env python3
"""
Test unified generator with 15 complex names, each with 15 variations
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
    """Test unified generator with 15 complex names"""
    print("="*80)
    print("TESTING UNIFIED GENERATOR - 15 COMPLEX NAMES, 15 VARIATIONS EACH")
    print("="*80)
    print()
    
    # 15 complex/diverse names
    complex_names = [
        "Christopher Anderson",
        "Elizabeth Rodriguez",
        "Mohammed Al-Hassan",
        "Priya Sharma",
        "Jean-Pierre Dubois",
        "Yuki Tanaka",
        "Alejandro Martinez",
        "Fatima Al-Zahra",
        "Vladimir Petrov",
        "Sophia Williams",
        "Chen Wei",
        "Isabella Garcia",
        "Rajesh Kumar",
        "Emma Thompson",
        "Hassan Abdullah"
    ]
    
    # Configuration for 15 variations
    # Distribution: 20% Light, 60% Medium, 20% Far
    light_count = 3   # 20% of 15
    medium_count = 9  # 60% of 15
    far_count = 3     # 20% of 15
    total_count = light_count + medium_count + far_count
    
    print(f"Configuration:")
    print(f"  Total names: {len(complex_names)}")
    print(f"  Variations per name: {total_count}")
    print(f"  Light variations: {light_count} (20%)")
    print(f"  Medium variations: {medium_count} (60%)")
    print(f"  Far variations: {far_count} (20%)")
    print()
    print("="*80)
    print()
    
    all_results = {}
    
    for idx, test_name in enumerate(complex_names, 1):
        print(f"\n{'='*80}")
        print(f"[{idx}/{len(complex_names)}] TESTING: {test_name}")
        print(f"{'='*80}\n")
        
        try:
            # Generate name variations
            print("Step 1: Generating name variations...")
            print("-" * 80)
            name_variations = generate_full_name_variations(
                full_name=test_name,
                light_count=light_count,
                medium_count=medium_count,
                far_count=far_count,
                verbose=False  # Set to False to reduce output
            )
            
            print(f"✅ Generated {len(name_variations)} name variations")
            if len(name_variations) < total_count:
                print(f"⚠️  Warning: Expected {total_count}, got {len(name_variations)}")
            
            # Show first 5 variations as sample
            print("Sample variations (first 5):")
            for i, var in enumerate(name_variations[:5], 1):
                if i <= light_count:
                    category = "Light"
                elif i <= light_count + medium_count:
                    category = "Medium"
                else:
                    category = "Far"
                print(f"  {i}. {var} [{category}]")
            if len(name_variations) > 5:
                print(f"  ... and {len(name_variations) - 5} more")
            
            # Generate DOB variations
            print(f"\nStep 2: Generating DOB variations...")
            print("-" * 80)
            seed_dob = "1990-01-15"
            dob_variations = generate_perfect_dob_variations(seed_dob, variation_count=total_count)
            print(f"✅ Generated {len(dob_variations)} DOB variations")
            
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
                'variation_count': len(name_variations),
                'expected_count': total_count,
                'detailed_metrics': detailed_metrics
            }
            
            print(f"\n✅ Results for {test_name}:")
            print(f"   Final Score: {final_score:.4f}")
            print(f"   Base Score: {base_score:.4f}")
            print(f"   Variations: {len(name_variations)}/{total_count}")
            
        except Exception as e:
            print(f"❌ Error processing {test_name}: {str(e)}")
            import traceback
            traceback.print_exc()
            all_results[test_name] = {
                'error': str(e),
                'final_score': 0.0,
                'base_score': 0.0,
                'variation_count': 0
            }
    
    # Final Summary
    print("\n" + "="*80)
    print("FINAL SUMMARY - ALL 15 NAMES")
    print("="*80)
    print()
    print(f"{'Name':<30} {'Variations':<12} {'Final Score':<12} {'Base Score':<12} {'Status':<10}")
    print("-" * 80)
    
    total_final = 0.0
    total_base = 0.0
    successful = 0
    
    for name, results in all_results.items():
        if 'error' in results:
            status = "ERROR"
            final_score = 0.0
            base_score = 0.0
            var_count = 0
        else:
            status = "OK" if results['variation_count'] >= results['expected_count'] else "PARTIAL"
            final_score = results['final_score']
            base_score = results['base_score']
            var_count = results['variation_count']
            total_final += final_score
            total_base += base_score
            successful += 1
        
        print(f"{name:<30} {var_count:<12} {final_score:<12.4f} {base_score:<12.4f} {status:<10}")
    
    print("-" * 80)
    if successful > 0:
        avg_final = total_final / successful
        avg_base = total_base / successful
        print(f"{'AVERAGE':<30} {'':<12} {avg_final:<12.4f} {avg_base:<12.4f} {successful}/{len(complex_names)}")
    
    print()
    print("="*80)
    print(f"Total names tested: {len(complex_names)}")
    print(f"Successful: {successful}")
    print(f"Failed: {len(complex_names) - successful}")
    if successful > 0:
        print(f"Average Final Score: {avg_final:.4f}")
        print(f"Average Base Score: {avg_base:.4f}")
    print("="*80)

if __name__ == "__main__":
    main()

