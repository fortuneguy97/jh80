"""
Comprehensive Test of Smart Phonetic Generator with Multiple Names
"""

from smart_phonetic_generator import generate_smart_variations, predict_score
from MIID.validator.reward import calculate_variation_quality

# Test with diverse names
test_names = [
    "John Smith",
    "Mary Johnson",
    "Robert Williams",
    "Sarah Brown",
    "Michael Davis",
    "David Miller",
    "Jennifer Wilson",
    "James Anderson"
]

print("="*80)
print("COMPREHENSIVE TEST: Smart Phonetic Generator with Multiple Names")
print("="*80)
print()

results_summary = []

for name in test_names:
    print("="*80)
    print(f"Testing: {name}")
    print("="*80)
    
    parts = name.split()
    first_original = parts[0]
    last_original = parts[1] if len(parts) > 1 else ""
    
    # Generate variations
    variations = generate_smart_variations(name, light_count=2, medium_count=5, far_count=1)
    
    print(f"\nGenerated {len(variations)} variations:")
    print("-" * 80)
    
    # Calculate predicted scores
    first_scores = []
    last_scores = []
    
    for i, var in enumerate(variations, 1):
        var_parts = var.split()
        first_var = var_parts[0] if len(var_parts) > 0 else ""
        last_var = var_parts[1] if len(var_parts) > 1 else ""
        
        first_pred = predict_score(first_original, first_var)
        last_pred = predict_score(last_original, last_var)
        
        first_scores.append(first_pred)
        last_scores.append(last_pred)
        
        if i <= 3:  # Show first 3 in detail
            first_cat = "Light" if 0.8 <= first_pred <= 1.0 else "Medium" if 0.6 <= first_pred < 0.8 else "Far" if 0.3 <= first_pred < 0.6 else "Too Low"
            last_cat = "Light" if 0.8 <= last_pred <= 1.0 else "Medium" if 0.6 <= last_pred < 0.8 else "Far" if 0.3 <= last_pred < 0.6 else "Too Low"
            print(f"  {i}. {var:25s} | First: {first_pred:.4f} ({first_cat:8s}), Last: {last_pred:.4f} ({last_cat:8s})")
    
    if len(variations) > 3:
        print(f"  ... ({len(variations) - 3} more variations)")
    
    # Count predicted distribution
    first_light = sum(1 for s in first_scores if 0.8 <= s <= 1.0)
    first_medium = sum(1 for s in first_scores if 0.6 <= s < 0.8)
    first_far = sum(1 for s in first_scores if 0.3 <= s < 0.6)
    
    last_light = sum(1 for s in last_scores if 0.8 <= s <= 1.0)
    last_medium = sum(1 for s in last_scores if 0.6 <= s < 0.8)
    last_far = sum(1 for s in last_scores if 0.3 <= s < 0.6)
    
    print(f"\nPredicted Distribution:")
    print(f"  First Name: Light {first_light}/8 (target: 2), Medium {first_medium}/8 (target: 5), Far {first_far}/8 (target: 1)")
    print(f"  Last Name:  Light {last_light}/8 (target: 2), Medium {last_medium}/8 (target: 5), Far {last_far}/8 (target: 1)")
    
    # Score with actual rewards.py
    print(f"\nActual Scoring with rewards.py:")
    print("-" * 80)
    
    try:
        final_score, base_score, metrics = calculate_variation_quality(
            original_name=name,
            variations=variations,
            phonetic_similarity={'Light': 0.2, 'Medium': 0.6, 'Far': 0.2},
            orthographic_similarity={'Light': 0.3, 'Medium': 0.4, 'Far': 0.3},
            expected_count=8,
            rule_based=None
        )
        
        first_metrics = metrics.get('first_name', {}).get('metrics', {})
        last_metrics = metrics.get('last_name', {}).get('metrics', {})
        
        first_sim = first_metrics.get('similarity', {}).get('combined', 0)
        last_sim = last_metrics.get('similarity', {}).get('combined', 0)
        
        print(f"Final Score: {final_score:.4f}")
        print(f"Base Score: {base_score:.4f}")
        print(f"First Name Similarity: {first_sim:.4f}")
        print(f"Last Name Similarity: {last_sim:.4f}")
        
        # Store results
        results_summary.append({
            'name': name,
            'final_score': final_score,
            'base_score': base_score,
            'first_sim': first_sim,
            'last_sim': last_sim,
            'first_light': first_light,
            'first_medium': first_medium,
            'first_far': first_far,
            'last_light': last_light,
            'last_medium': last_medium,
            'last_far': last_far
        })
        
    except Exception as e:
        print(f"Error scoring: {e}")
        results_summary.append({
            'name': name,
            'error': str(e)
        })
    
    print()

# Summary
print("="*80)
print("SUMMARY - All Names")
print("="*80)
print()

print(f"{'Name':<20} {'Final':<8} {'Base':<8} {'First Sim':<10} {'Last Sim':<10} {'Status'}")
print("-" * 80)

for result in results_summary:
    if 'error' in result:
        print(f"{result['name']:<20} {'ERROR':<8} {'ERROR':<8} {'ERROR':<10} {'ERROR':<10} {result['error']}")
    else:
        status = "✅ Good" if result['final_score'] > 0.4 else "⚠️  Needs Work"
        print(f"{result['name']:<20} {result['final_score']:<8.4f} {result['base_score']:<8.4f} {result['first_sim']:<10.4f} {result['last_sim']:<10.4f} {status}")

print()
print("="*80)
print("DISTRIBUTION ANALYSIS")
print("="*80)
print()

print(f"{'Name':<20} {'First Dist':<20} {'Last Dist':<20}")
print("-" * 80)

for result in results_summary:
    if 'error' not in result:
        first_dist = f"L:{result['first_light']} M:{result['first_medium']} F:{result['first_far']}"
        last_dist = f"L:{result['last_light']} M:{result['last_medium']} F:{result['last_far']}"
        print(f"{result['name']:<20} {first_dist:<20} {last_dist:<20}")

print()
print("="*80)
print("KEY INSIGHTS")
print("="*80)
print()

# Calculate averages
valid_results = [r for r in results_summary if 'error' not in r]
if valid_results:
    avg_final = sum(r['final_score'] for r in valid_results) / len(valid_results)
    avg_first_sim = sum(r['first_sim'] for r in valid_results) / len(valid_results)
    avg_last_sim = sum(r['last_sim'] for r in valid_results) / len(valid_results)
    
    print(f"Average Final Score: {avg_final:.4f}")
    print(f"Average First Name Similarity: {avg_first_sim:.4f}")
    print(f"Average Last Name Similarity: {avg_last_sim:.4f}")
    print()
    
    # Best and worst
    best = max(valid_results, key=lambda x: x['final_score'])
    worst = min(valid_results, key=lambda x: x['final_score'])
    
    print(f"Best: {best['name']} (Score: {best['final_score']:.4f})")
    print(f"Worst: {worst['name']} (Score: {worst['final_score']:.4f})")
    print()
    
    print("The smart generator:")
    print("  ✅ Successfully predicts scores using reverse-engineered algorithms")
    print("  ✅ Generates variations targeting specific score ranges")
    print("  ⚠️  Distribution matching needs improvement for some names")
    print("  💡 Works best for simple names (4-5 letters)")

