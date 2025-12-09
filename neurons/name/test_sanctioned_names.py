#!/usr/bin/env python3
"""
Test 15 names from sanctioned transliteration list:
1. Load names from Sanctioned_Transliteration.json
2. Transliterate them to Latin script
3. Generate variations using variation_generator_simple.py
4. Test with validator to get scores
"""

import os
import sys
import json
import random
from typing import List, Dict

# Add paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

# Import validator functions
from reward import transliterate_name_with_llm, _grade_address_variations
from variation_generator_simple import generate_variations, IdentitySynapse

def load_sanctioned_names(count: int = 15) -> List[Dict]:
    """Load names from sanctioned transliteration file"""
    json_path = os.path.join(os.path.dirname(__file__), 'MIID', 'validator', 'Sanctioned_Transliteration.json')
    
    with open(json_path, 'r', encoding='utf-8') as f:
        all_names = json.load(f)
    
    # Select random 15 names
    selected = random.sample(all_names, min(count, len(all_names)))
    return selected

def transliterate_names(names: List[Dict]) -> Dict[str, str]:
    """Transliterate names to Latin script"""
    transliterated = {}
    
    for person in names:
        first_name = person.get('FirstName', '')
        last_name = person.get('LastName', '')
        script = person.get('Script', 'latin')
        full_name = f"{first_name} {last_name}".strip()
        
        if script == 'latin':
            transliterated[full_name] = full_name
        else:
            print(f"   Transliterating: {full_name} ({script})...")
            try:
                transliterated_name = transliterate_name_with_llm(full_name, script)
                transliterated[full_name] = transliterated_name
                print(f"   ✅ {full_name} → {transliterated_name}")
            except Exception as e:
                print(f"   ❌ Failed to transliterate {full_name}: {e}")
                # Use fallback: just use original
                transliterated[full_name] = full_name
    
    return transliterated

def get_addresses_for_country(country: str) -> List[str]:
    """Get addresses from cache for a country"""
    cache_file = os.path.join(os.path.dirname(__file__), 'validated_address_cache_new.json')
    
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache = json.load(f)
        
        if country in cache and isinstance(cache[country], list):
            addresses = cache[country]
            if len(addresses) >= 15:
                return addresses[:15]
            return addresses
    except Exception as e:
        print(f"   ⚠️  Could not load addresses for {country}: {e}")
    
    # Fallback: return country name as address
    return [country] * 15

def main():
    print("="*80)
    print("TESTING 15 NAMES FROM SANCTIONED TRANSLITERATION LIST")
    print("="*80)
    print()
    
    # Step 1: Load 15 names
    print("📋 Step 1: Loading 15 names from sanctioned transliteration list...")
    sanctioned_names = load_sanctioned_names(15)
    print(f"   ✅ Loaded {len(sanctioned_names)} names")
    print()
    
    # Step 2: Transliterate names
    print("🔄 Step 2: Transliterating names to Latin script...")
    transliterated_map = transliterate_names(sanctioned_names)
    print(f"   ✅ Transliterated {len(transliterated_map)} names")
    print()
    
    # Step 3: Create synapse and generate variations
    print("🔬 Step 3: Generating variations using unified generator...")
    
    # Prepare identities
    identities = []
    seed_addresses = []
    
    for person in sanctioned_names:
        first_name = person.get('FirstName', '')
        last_name = person.get('LastName', '')
        full_name = f"{first_name} {last_name}".strip()
        transliterated_name = transliterated_map.get(full_name, full_name)
        dob = person.get('DOB', '1990-01-01')
        country = person.get('Country_Residence', 'Unknown')
        
        # Get addresses for this country
        addresses = get_addresses_for_country(country)
        if addresses:
            address = addresses[0] if addresses else country
        else:
            address = country
        
        identities.append([transliterated_name, dob, address])
        seed_addresses.append(country)
    
    # Create query template
    query_template = """The following name is the seed name to generate variations for: {name}. 
Generate 15 variations of the name {name}, ensuring phonetic similarity: 100% Medium, and orthographic similarity: 100% Medium, 
and also include 45% of variations that follow: Replace spaces with special characters, and Delete a random letter. 
The following address is the seed country/city to generate address variations for: {address}. 
Generate unique real addresses within the specified country/city for each variation. 
The following date of birth is the seed DOB to generate variations for: {dob}.

[ADDITIONAL CONTEXT]:
- Address variations should be realistic addresses within the specified country/city
- DOB variations ATLEAST one in each category (±1 day, ±3 days, ±30 days, ±90 days, ±365 days, year+month only)
- For year+month, generate the exact DOB without day
- Each variation must have a different, realistic address and DOB"""
    
    # Create synapse
    synapse = IdentitySynapse(
        identity=identities,
        query_template=query_template,
        timeout=360.0
    )
    
    # Generate variations
    try:
        variations = generate_variations(synapse)
        print(f"   ✅ Generated variations for {len(variations)} names")
    except Exception as e:
        print(f"   ❌ Error generating variations: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print()
    
    # Step 4: Test with validator
    print("🧪 Step 4: Testing variations with validator...")
    
    # Prepare for validator
    miner_metrics = {}
    validator_uid = 101
    miner_uid = 501
    
    # Test each name
    results = {}
    for i, (original_name, transliterated_name) in enumerate(transliterated_map.items()):
        if transliterated_name not in variations:
            print(f"   ⚠️  No variations found for {transliterated_name}")
            continue
        
        print(f"\n   [{i+1}/15] Testing: {transliterated_name}")
        print(f"      Original: {original_name}")
        
        # Get seed address
        seed_address = seed_addresses[i] if i < len(seed_addresses) else "Unknown"
        
        # Create variations dict for this name only
        name_variations = {
            transliterated_name: variations[transliterated_name]
        }
        
        # Test with validator
        try:
            validation_result = _grade_address_variations(
                variations=name_variations,
                seed_addresses=[seed_address],
                miner_metrics=miner_metrics,
                validator_uid=validator_uid,
                miner_uid=miner_uid
            )
            
            overall_score = validation_result.get('overall_score', 0.0)
            heuristic_perfect = validation_result.get('heuristic_perfect', False)
            region_matches = validation_result.get('region_matches', 0)
            api_result = validation_result.get('api_result', 'UNKNOWN')
            
            results[transliterated_name] = {
                'original_name': original_name,
                'overall_score': overall_score,
                'heuristic_perfect': heuristic_perfect,
                'region_matches': region_matches,
                'api_result': api_result,
                'validation_result': validation_result
            }
            
            status = "✅ PASS" if overall_score >= 0.9 else "⚠️  PARTIAL" if overall_score >= 0.5 else "❌ FAIL"
            print(f"      {status} Score: {overall_score:.4f}")
            print(f"      Heuristic: {heuristic_perfect}, Region: {region_matches}/15, API: {api_result}")
            
        except Exception as e:
            print(f"      ❌ Error testing {transliterated_name}: {e}")
            results[transliterated_name] = {
                'original_name': original_name,
                'error': str(e)
            }
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    total = len(results)
    passed = sum(1 for r in results.values() if isinstance(r, dict) and r.get('overall_score', 0) >= 0.9)
    partial = sum(1 for r in results.values() if isinstance(r, dict) and 0.5 <= r.get('overall_score', 0) < 0.9)
    failed = sum(1 for r in results.values() if isinstance(r, dict) and r.get('overall_score', 0) < 0.5)
    
    print(f"Total Names Tested: {total}")
    print(f"✅ Passed (>= 0.9): {passed}/{total}")
    print(f"⚠️  Partial (0.5-0.9): {partial}/{total}")
    print(f"❌ Failed (< 0.5): {failed}/{total}")
    
    if total > 0:
        avg_score = sum(r.get('overall_score', 0) for r in results.values() if isinstance(r, dict)) / total
        print(f"Average Score: {avg_score:.4f}")
    
    # Save results
    output_file = "sanctioned_names_test_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "test_date": __import__('datetime').datetime.now().isoformat(),
            "sanctioned_names": sanctioned_names,
            "transliterated_map": transliterated_map,
            "results": results,
            "summary": {
                "total": total,
                "passed": passed,
                "partial": partial,
                "failed": failed,
                "average_score": avg_score if total > 0 else 0.0
            }
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Results saved to {output_file}")

if __name__ == '__main__':
    main()

