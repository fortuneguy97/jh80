#!/usr/bin/env python3
"""
Test names with 0 phonetic similarity using unified generator
"""

import os
import sys
import json

# Flush output immediately
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

print("🔍 Testing names with 0 phonetic similarity...", flush=True)

# Add paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("📦 Importing modules...", flush=True)

try:
    from unified_generator import (
        generate_full_name_variations,
        generate_perfect_dob_variations
    )
    print("✅ Imports successful", flush=True)
except Exception as e:
    print(f"❌ Import error: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Names with 0 phonetic similarity
zero_phonetic_names = [
    "Kamel Amhaz",
    "Bogdan Shablya",
    "'Isa Qasir",
    "Alexey Kupriyanov",
    "Israa Rashed",
    "Valery Semyonov",
    "Victor Zavarzin"
]

def main():
    print("="*80, flush=True)
    print("TESTING NAMES WITH 0 PHONETIC SIMILARITY", flush=True)
    print("="*80, flush=True)
    print()
    
    variation_count = 15
    # Distribution: 30% Light, 50% Medium, 20% Far
    light_pct = 0.30
    medium_pct = 0.50
    far_pct = 0.20
    
    light_count = max(1, int(variation_count * light_pct))
    medium_count = max(1, int(variation_count * medium_pct))
    far_count = max(1, int(variation_count * far_pct))
    
    # Adjust to ensure total equals variation_count
    total = light_count + medium_count + far_count
    if total < variation_count:
        medium_count += (variation_count - total)
    elif total > variation_count:
        medium_count -= (total - variation_count)
    
    print(f"📋 Configuration:", flush=True)
    print(f"   Variation count: {variation_count}", flush=True)
    print(f"   Distribution: Light={light_count}, Medium={medium_count}, Far={far_count}", flush=True)
    print()
    
    all_results = {}
    
    for i, full_name in enumerate(zero_phonetic_names, 1):
        print(f"[{i}/{len(zero_phonetic_names)}] Processing: {full_name}", flush=True)
        
        try:
            # Generate name variations
            print(f"      🔄 Generating name variations (Light={light_count}, Medium={medium_count}, Far={far_count})...", flush=True)
            name_variations = generate_full_name_variations(
                full_name,
                light_count=light_count,
                medium_count=medium_count,
                far_count=far_count,
                verbose=False
            )
            print(f"      ✅ Generated {len(name_variations)} name variations", flush=True)
            
            # Show first 5 variations
            print(f"      📝 Sample variations (first 5):", flush=True)
            for j, var in enumerate(name_variations[:5], 1):
                print(f"         {j}. {var}", flush=True)
            
            all_results[full_name] = name_variations
            
        except Exception as e:
            print(f"      ❌ Error: {e}", flush=True)
            import traceback
            traceback.print_exc()
        
        print()
    
    # Save results
    output_file = "zero_phonetic_variations.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "test_date": __import__('datetime').datetime.now().isoformat(),
            "names_tested": zero_phonetic_names,
            "variations": all_results,
            "configuration": {
                "variation_count": variation_count,
                "light_count": light_count,
                "medium_count": medium_count,
                "far_count": far_count
            }
        }, f, indent=2, ensure_ascii=False)
    
    print("="*80, flush=True)
    print(f"✅ COMPLETE - Generated variations for {len(zero_phonetic_names)} names", flush=True)
    print(f"💾 Results saved to {output_file}", flush=True)
    print("="*80, flush=True)

if __name__ == '__main__':
    main()





