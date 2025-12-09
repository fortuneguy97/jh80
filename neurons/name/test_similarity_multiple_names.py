"""
Test similarity checking for multiple names using prime_generator.py and rewards.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

from prime_generator import generate_full_name_variations, test_with_rewards

# Test names
test_names = [
    "John Smith",
    "Mary Johnson",
    "Robert Williams",
    "Jennifer Brown",
    "Michael Davis"
]

# Distribution for each name
light_count = 2
medium_count = 6
far_count = 2
total_count = light_count + medium_count + far_count

print("="*80)
print("TESTING SIMILARITY FOR MULTIPLE NAMES")
print("="*80)
print()
print(f"Distribution: {light_count} Light, {medium_count} Medium, {far_count} Far")
print(f"Total variations per name: {total_count}")
print()
print("="*80)
print()

results = []

for i, test_name in enumerate(test_names, 1):
    print(f"\n{'='*80}")
    print(f"TEST {i}/{len(test_names)}: {test_name}")
    print(f"{'='*80}\n")
    
    try:
        # Generate variations
        print(f"Generating variations for '{test_name}'...")
        variations = generate_full_name_variations(
            test_name,
            light_count=light_count,
            medium_count=medium_count,
            far_count=far_count,
            verbose=False  # Set to False to reduce output
        )
        
        print(f"✅ Generated {len(variations)} variations")
        
        # Test with rewards.py
        final_score, base_score, detailed_metrics = test_with_rewards(
            test_name,
            variations,
            expected_count=total_count,
            light_count=light_count,
            medium_count=medium_count,
            far_count=far_count
        )
        
        # Extract similarity scores
        similarity_info = {}
        if "first_name" in detailed_metrics and "metrics" in detailed_metrics["first_name"]:
            first_metrics = detailed_metrics["first_name"]["metrics"]
            if "similarity" in first_metrics:
                sim = first_metrics["similarity"]
                similarity_info["first_name"] = {
                    "phonetic": sim.get('phonetic', 0),
                    "orthographic": sim.get('orthographic', 0),
                    "combined": sim.get('combined', 0)
                }
        
        if "last_name" in detailed_metrics and "metrics" in detailed_metrics["last_name"]:
            last_metrics = detailed_metrics["last_name"]["metrics"]
            if "similarity" in last_metrics:
                sim = last_metrics["similarity"]
                similarity_info["last_name"] = {
                    "phonetic": sim.get('phonetic', 0),
                    "orthographic": sim.get('orthographic', 0),
                    "combined": sim.get('combined', 0)
                }
        
        results.append({
            "name": test_name,
            "final_score": final_score,
            "base_score": base_score,
            "variations_count": len(variations),
            "similarity": similarity_info
        })
        
        print(f"\n✅ Test {i} completed: Final Score = {final_score:.4f}")
        
    except Exception as e:
        print(f"❌ Error testing '{test_name}': {e}")
        import traceback
        traceback.print_exc()
        results.append({
            "name": test_name,
            "error": str(e)
        })

print("\n" + "="*80)
print("SUMMARY OF ALL TESTS")
print("="*80)
print()

print(f"{'Name':<25} {'Final Score':<15} {'Base Score':<15} {'Variations':<12} {'Similarity'}")
print("-" * 80)

for result in results:
    if "error" in result:
        print(f"{result['name']:<25} {'ERROR':<15} {'ERROR':<15} {'ERROR':<12} {'ERROR'}")
    else:
        name = result['name']
        final = result['final_score']
        base = result['base_score']
        count = result['variations_count']
        
        # Get similarity info
        sim_str = "N/A"
        if "similarity" in result:
            sim = result["similarity"]
            if "first_name" in sim and "last_name" in sim:
                first_combined = sim["first_name"]["combined"]
                last_combined = sim["last_name"]["combined"]
                sim_str = f"F:{first_combined:.2f}/L:{last_combined:.2f}"
            elif "first_name" in sim:
                sim_str = f"F:{sim['first_name']['combined']:.2f}"
            elif "last_name" in sim:
                sim_str = f"L:{sim['last_name']['combined']:.2f}"
        
        print(f"{name:<25} {final:<15.4f} {base:<15.4f} {count:<12} {sim_str}")

print()
print("="*80)
print("DETAILED SIMILARITY BREAKDOWN")
print("="*80)
print()

for result in results:
    if "error" not in result and "similarity" in result:
        print(f"\n{result['name']}:")
        sim = result["similarity"]
        
        if "first_name" in sim:
            fn = sim["first_name"]
            print(f"  First Name:")
            print(f"    Phonetic: {fn['phonetic']:.4f}")
            print(f"    Orthographic: {fn['orthographic']:.4f}")
            print(f"    Combined: {fn['combined']:.4f}")
        
        if "last_name" in sim:
            ln = sim["last_name"]
            print(f"  Last Name:")
            print(f"    Phonetic: {ln['phonetic']:.4f}")
            print(f"    Orthographic: {ln['orthographic']:.4f}")
            print(f"    Combined: {ln['combined']:.4f}")

print()
print("="*80)
print("STATISTICS")
print("="*80)
print()

if results:
    successful = [r for r in results if "error" not in r]
    if successful:
        avg_final = sum(r["final_score"] for r in successful) / len(successful)
        avg_base = sum(r["base_score"] for r in successful) / len(successful)
        avg_variations = sum(r["variations_count"] for r in successful) / len(successful)
        
        print(f"Total tests: {len(results)}")
        print(f"Successful: {len(successful)}")
        print(f"Failed: {len(results) - len(successful)}")
        print()
        print(f"Average Final Score: {avg_final:.4f}")
        print(f"Average Base Score: {avg_base:.4f}")
        print(f"Average Variations Generated: {avg_variations:.1f}")
        
        # Best and worst
        if len(successful) > 0:
            best = max(successful, key=lambda x: x["final_score"])
            worst = min(successful, key=lambda x: x["final_score"])
            print()
            print(f"Best Score: {best['name']} ({best['final_score']:.4f})")
            print(f"Worst Score: {worst['name']} ({worst['final_score']:.4f})")

print()

