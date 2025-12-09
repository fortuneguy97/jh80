#!/usr/bin/env python3
"""
Test unified generator with names from Sanctioned_Transliteration.json
Measure timing for 15 complex names
"""

import sys
import os
import json
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

from unified_generator import (
    generate_full_name_variations,
    generate_perfect_dob_variations,
    test_with_rewards
)

def load_sanctioned_names(file_path: str, count: int = 15):
    """Load names from Sanctioned_Transliteration.json"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Extract names - use transliterated versions if available, otherwise use original
    names = []
    for entry in data[:count]:
        first_name = entry.get('FirstName', '')
        last_name = entry.get('LastName', '')
        
        # Combine first and last name
        if first_name and last_name:
            full_name = f"{first_name} {last_name}"
            names.append({
                'full_name': full_name,
                'script': entry.get('Script', 'latin'),
                'dob': entry.get('DOB', '1990-01-15'),
                'country': entry.get('Country_Residence', '')
            })
    
    return names

def main():
    """Test unified generator with sanctioned names and measure timing"""
    print("="*80)
    print("TESTING UNIFIED GENERATOR - SANCTIONED NAMES WITH TIMING")
    print("="*80)
    print()
    
    # Load sanctioned names
    sanctioned_file = os.path.join(
        os.path.dirname(__file__), 
        'MIID', 'validator', 'Sanctioned_Transliteration.json'
    )
    
    sanctioned_names = load_sanctioned_names(sanctioned_file, count=15)
    
    if not sanctioned_names:
        print("❌ No names loaded from sanctioned file")
        return
    
    print(f"Loaded {len(sanctioned_names)} names from sanctioned list")
    print()
    
    # Configuration for 15 variations
    light_count = 3   # 20% of 15
    medium_count = 9  # 60% of 15
    far_count = 3     # 20% of 15
    total_count = light_count + medium_count + far_count
    
    print(f"Configuration:")
    print(f"  Total names: {len(sanctioned_names)}")
    print(f"  Variations per name: {total_count}")
    print(f"  Light variations: {light_count} (20%)")
    print(f"  Medium variations: {medium_count} (60%)")
    print(f"  Far variations: {far_count} (20%)")
    print()
    print("="*80)
    print()
    
    all_results = {}
    total_start_time = time.time()
    
    for idx, name_data in enumerate(sanctioned_names, 1):
        test_name = name_data['full_name']
        name_start_time = time.time()
        
        print(f"\n{'='*80}")
        print(f"[{idx}/{len(sanctioned_names)}] TESTING: {test_name}")
        print(f"  Script: {name_data['script']}, Country: {name_data['country']}")
        print(f"{'='*80}\n")
        
        try:
            # Generate name variations
            print("Step 1: Generating name variations...")
            print("-" * 80)
            var_start = time.time()
            name_variations = generate_full_name_variations(
                full_name=test_name,
                light_count=light_count,
                medium_count=medium_count,
                far_count=far_count,
                verbose=False
            )
            var_time = time.time() - var_start
            
            print(f"✅ Generated {len(name_variations)} name variations in {var_time:.2f} seconds")
            if len(name_variations) < total_count:
                print(f"⚠️  Warning: Expected {total_count}, got {len(name_variations)}")
            
            # Generate DOB variations
            print(f"\nStep 2: Generating DOB variations...")
            print("-" * 80)
            dob_start = time.time()
            seed_dob = name_data.get('dob', '1990-01-15')
            dob_variations = generate_perfect_dob_variations(seed_dob, variation_count=total_count)
            dob_time = time.time() - dob_start
            print(f"✅ Generated {len(dob_variations)} DOB variations in {dob_time:.2f} seconds")
            
            # Test with rewards.py
            print(f"\nStep 3: Testing with rewards.py...")
            print("-" * 80)
            rewards_start = time.time()
            final_score, base_score, detailed_metrics = test_with_rewards(
                full_name=test_name,
                variations=name_variations,
                expected_count=total_count,
                light_count=light_count,
                medium_count=medium_count,
                far_count=far_count
            )
            rewards_time = time.time() - rewards_start
            
            name_total_time = time.time() - name_start_time
            
            # Store results
            all_results[test_name] = {
                'name_variations': name_variations,
                'dob_variations': dob_variations,
                'final_score': final_score,
                'base_score': base_score,
                'variation_count': len(name_variations),
                'expected_count': total_count,
                'detailed_metrics': detailed_metrics,
                'var_time': var_time,
                'dob_time': dob_time,
                'rewards_time': rewards_time,
                'total_time': name_total_time,
                'script': name_data['script'],
                'country': name_data['country']
            }
            
            print(f"\n✅ Results for {test_name}:")
            print(f"   Final Score: {final_score:.4f}")
            print(f"   Base Score: {base_score:.4f}")
            print(f"   Variations: {len(name_variations)}/{total_count}")
            print(f"   ⏱️  Timing:")
            print(f"      - Name generation: {var_time:.2f}s")
            print(f"      - DOB generation: {dob_time:.2f}s")
            print(f"      - Rewards testing: {rewards_time:.2f}s")
            print(f"      - Total: {name_total_time:.2f}s")
            
        except Exception as e:
            print(f"❌ Error processing {test_name}: {str(e)}")
            import traceback
            traceback.print_exc()
            all_results[test_name] = {
                'error': str(e),
                'final_score': 0.0,
                'base_score': 0.0,
                'variation_count': 0,
                'total_time': 0.0,
                'script': name_data.get('script', 'unknown'),
                'country': name_data.get('country', 'unknown')
            }
    
    total_time = time.time() - total_start_time
    
    # Final Summary
    print("\n" + "="*80)
    print("FINAL SUMMARY - ALL 15 SANCTIONED NAMES")
    print("="*80)
    print()
    print(f"{'Name':<35} {'Script':<10} {'Vars':<6} {'Score':<8} {'Time':<8} {'Status':<10}")
    print("-" * 80)
    
    total_final = 0.0
    total_base = 0.0
    successful = 0
    total_var_time = 0.0
    total_dob_time = 0.0
    total_rewards_time = 0.0
    
    for name, results in all_results.items():
        if 'error' in results:
            status = "ERROR"
            final_score = 0.0
            base_score = 0.0
            var_count = 0
            name_time = 0.0
            script = results.get('script', 'unknown')
        else:
            status = "OK" if results['variation_count'] >= results['expected_count'] else "PARTIAL"
            final_score = results['final_score']
            base_score = results['base_score']
            var_count = results['variation_count']
            name_time = results.get('total_time', 0.0)
            script = results.get('script', 'unknown')
            total_var_time += results.get('var_time', 0.0)
            total_dob_time += results.get('dob_time', 0.0)
            total_rewards_time += results.get('rewards_time', 0.0)
            total_final += final_score
            total_base += base_score
            successful += 1
        
        # Truncate long names for display
        display_name = name[:33] + ".." if len(name) > 35 else name
        print(f"{display_name:<35} {script:<10} {var_count:<6} {final_score:<8.4f} {name_time:<8.2f} {status:<10}")
    
    print("-" * 80)
    if successful > 0:
        avg_final = total_final / successful
        avg_base = total_base / successful
        avg_var_time = total_var_time / successful
        avg_dob_time = total_dob_time / successful
        avg_rewards_time = total_rewards_time / successful
        avg_total_time = total_time / len(sanctioned_names)
        
        print(f"{'AVERAGE':<35} {'':<10} {'':<6} {avg_final:<8.4f} {avg_total_time:<8.2f} {successful}/{len(sanctioned_names)}")
    
    print()
    print("="*80)
    print("TIMING BREAKDOWN")
    print("="*80)
    print(f"Total time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
    print(f"Average per name: {total_time/len(sanctioned_names):.2f} seconds")
    if successful > 0:
        print(f"  - Name generation: {avg_var_time:.2f}s per name")
        print(f"  - DOB generation: {avg_dob_time:.2f}s per name")
        print(f"  - Rewards testing: {avg_rewards_time:.2f}s per name")
    print()
    print(f"Total names tested: {len(sanctioned_names)}")
    print(f"Successful: {successful}")
    print(f"Failed: {len(sanctioned_names) - successful}")
    if successful > 0:
        print(f"Average Final Score: {avg_final:.4f}")
        print(f"Average Base Score: {avg_base:.4f}")
    print("="*80)

if __name__ == "__main__":
    main()

