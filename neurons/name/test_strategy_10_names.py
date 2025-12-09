"""
Test strategy-based generator with 10 complex names
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

from strategy_based_generator import generate_full_name_variations_strategy_based
from reward import calculate_variation_quality

# 10 Complex names for testing
complex_names = [
    "Constantinople Alexandrov",
    "Xavier Rodriguez",
    "Sebastian Martinez",
    "Theodore Williams",
    "Archimedes Johnson",
    "Guillermo Fernandez",
    "Bartholomew Anderson",
    "Christopher Thompson",
    "Alexander Petrovich",
    "Benjamin Harrison"
]

# Distribution for each name
light_count = 2
medium_count = 6
far_count = 2
total_count = light_count + medium_count + far_count

# Calculate target distribution percentages
light_pct = light_count / total_count
medium_pct = medium_count / total_count
far_pct = far_count / total_count

phonetic_similarity = {
    "Light": light_pct,
    "Medium": medium_pct,
    "Far": far_pct
}
orthographic_similarity = {
    "Light": light_pct,
    "Medium": medium_pct,
    "Far": far_pct
}

print("="*130)
print("STRATEGY-BASED GENERATOR TEST - 10 COMPLEX NAMES")
print("="*130)
print(f"Distribution: {light_count} Light, {medium_count} Medium, {far_count} Far (Total: {total_count} per name)")
print("This generator cycles through all 25 strategies systematically")
print()

results = []

for i, test_name in enumerate(complex_names, 1):
    print(f"Processing {i}/10: {test_name}...", end=" ", flush=True)
    
    try:
        # Generate variations using strategy-based generator
        variations = generate_full_name_variations_strategy_based(
            test_name,
            light_count=light_count,
            medium_count=medium_count,
            far_count=far_count,
            verbose=False  # Set to True to see strategy cycling
        )
        
        # Calculate scores directly
        final_score, base_score, detailed_metrics = calculate_variation_quality(
            original_name=test_name,
            variations=variations,
            phonetic_similarity=phonetic_similarity,
            orthographic_similarity=orthographic_similarity,
            expected_count=total_count,
            rule_based=None
        )
        
        # Extract similarity scores
        first_phonetic = 0
        first_orthographic = 0
        first_combined = 0
        last_phonetic = 0
        last_orthographic = 0
        last_combined = 0
        
        if "first_name" in detailed_metrics and "metrics" in detailed_metrics["first_name"]:
            first_metrics = detailed_metrics["first_name"]["metrics"]
            if "similarity" in first_metrics:
                sim = first_metrics["similarity"]
                first_phonetic = sim.get('phonetic', 0)
                first_orthographic = sim.get('orthographic', 0)
                first_combined = sim.get('combined', 0)
        
        if "last_name" in detailed_metrics and "metrics" in detailed_metrics["last_name"]:
            last_metrics = detailed_metrics["last_name"]["metrics"]
            if "similarity" in last_metrics:
                sim = last_metrics["similarity"]
                last_phonetic = sim.get('phonetic', 0)
                last_orthographic = sim.get('orthographic', 0)
                last_combined = sim.get('combined', 0)
        
        results.append({
            "name": test_name,
            "final_score": final_score,
            "base_score": base_score,
            "first_phonetic": first_phonetic,
            "first_orthographic": first_orthographic,
            "first_combined": first_combined,
            "last_phonetic": last_phonetic,
            "last_orthographic": last_orthographic,
            "last_combined": last_combined,
            "variations_count": len(variations)
        })
        
        print(f"✅ {final_score:.4f} ({len(variations)} vars)")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        results.append({
            "name": test_name,
            "error": str(e)
        })

print()
print("="*130)
print("RESULTS TABLE")
print("="*130)
print()

# Header
print(f"{'Name':<30} {'Final':<8} {'Base':<8} {'F-Phon':<8} {'F-Orth':<8} {'F-Comb':<8} {'L-Phon':<8} {'L-Orth':<8} {'L-Comb':<8} {'Vars':<6}")
print("-" * 130)

# Data rows
for result in results:
    if "error" in result:
        print(f"{result['name']:<30} {'ERROR':<8} {'ERROR':<8} {'ERROR':<8} {'ERROR':<8} {'ERROR':<8} {'ERROR':<8} {'ERROR':<8} {'ERROR':<8} {'ERROR':<6}")
    else:
        print(f"{result['name']:<30} "
              f"{result['final_score']:<8.4f} "
              f"{result['base_score']:<8.4f} "
              f"{result['first_phonetic']:<8.4f} "
              f"{result['first_orthographic']:<8.4f} "
              f"{result['first_combined']:<8.4f} "
              f"{result['last_phonetic']:<8.4f} "
              f"{result['last_orthographic']:<8.4f} "
              f"{result['last_combined']:<8.4f} "
              f"{result['variations_count']:<6}")

print()
print("="*130)
print("SUMMARY STATISTICS")
print("="*130)
print()

if results:
    successful = [r for r in results if "error" not in r]
    if successful:
        avg_final = sum(r["final_score"] for r in successful) / len(successful)
        avg_base = sum(r["base_score"] for r in successful) / len(successful)
        avg_first_phonetic = sum(r["first_phonetic"] for r in successful) / len(successful)
        avg_last_phonetic = sum(r["last_phonetic"] for r in successful) / len(successful)
        avg_first_combined = sum(r["first_combined"] for r in successful) / len(successful)
        avg_last_combined = sum(r["last_combined"] for r in successful) / len(successful)
        avg_variations = sum(r["variations_count"] for r in successful) / len(successful)
        
        print(f"{'Metric':<30} {'Average':<12} {'Min':<12} {'Max':<12}")
        print("-" * 66)
        print(f"{'Final Score':<30} {avg_final:<12.4f} {min(r['final_score'] for r in successful):<12.4f} {max(r['final_score'] for r in successful):<12.4f}")
        print(f"{'Base Score':<30} {avg_base:<12.4f} {min(r['base_score'] for r in successful):<12.4f} {max(r['base_score'] for r in successful):<12.4f}")
        print(f"{'First Name Phonetic':<30} {avg_first_phonetic:<12.4f} {min(r['first_phonetic'] for r in successful):<12.4f} {max(r['first_phonetic'] for r in successful):<12.4f}")
        print(f"{'Last Name Phonetic':<30} {avg_last_phonetic:<12.4f} {min(r['last_phonetic'] for r in successful):<12.4f} {max(r['last_phonetic'] for r in successful):<12.4f}")
        print(f"{'First Name Combined':<30} {avg_first_combined:<12.4f} {min(r['first_combined'] for r in successful):<12.4f} {max(r['first_combined'] for r in successful):<12.4f}")
        print(f"{'Last Name Combined':<30} {avg_last_combined:<12.4f} {min(r['last_combined'] for r in successful):<12.4f} {max(r['last_combined'] for r in successful):<12.4f}")
        print(f"{'Variations Generated':<30} {avg_variations:<12.1f} {min(r['variations_count'] for r in successful):<12} {max(r['variations_count'] for r in successful):<12}")
        
        print()
        best = max(successful, key=lambda x: x["final_score"])
        worst = min(successful, key=lambda x: x["final_score"])
        print(f"🏆 Best: {best['name']} (Final: {best['final_score']:.4f}, Vars: {best['variations_count']})")
        print(f"⚠️  Worst: {worst['name']} (Final: {worst['final_score']:.4f}, Vars: {worst['variations_count']})")
        
        # Count how many got full 10 variations
        full_variations = sum(1 for r in successful if r['variations_count'] == 10)
        print(f"\n✅ Names with full 10 variations: {full_variations}/{len(successful)}")

print()

