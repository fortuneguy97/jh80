"""
Test Universal Letter Removal Strategy on Multiple Names
Score variations using actual rewards.py functions
"""

from universal_letter_removal import generate_variations_by_category
from MIID.validator.reward import calculate_variation_quality, calculate_phonetic_similarity

# Test with multiple different names
test_names = [
    "John Smith",
    "Mary Johnson",
    "Robert Williams",
    "Sarah Brown",
    "Michael Davis"
]

print("="*80)
print("TESTING: Universal Letter Removal Strategy on Multiple Names")
print("="*80)
print()

for name in test_names:
    print("="*80)
    print(f"Testing: {name}")
    print("="*80)
    
    # Generate 8 variations (2 Light, 5 Medium, 1 Far)
    variations = generate_variations_by_category(name, light_count=2, medium_count=5, far_count=1)
    
    # Split name
    parts = name.split()
    first_original = parts[0]
    last_original = parts[1] if len(parts) > 1 else ""
    
    print(f"\nGenerated {len(variations)} variations:")
    print("-" * 80)
    
    # Show individual similarities
    first_scores = []
    last_scores = []
    
    for i, var in enumerate(variations, 1):
        var_parts = var.split()
        first_var = var_parts[0] if len(var_parts) > 0 else ""
        last_var = var_parts[1] if len(var_parts) > 1 else ""
        
        first_score = calculate_phonetic_similarity(first_original, first_var) if first_var else 0.0
        last_score = calculate_phonetic_similarity(last_original, last_var) if last_var else 0.0
        
        first_scores.append(first_score)
        last_scores.append(last_score)
        
        first_cat = "Light" if 0.8 <= first_score <= 1.0 else "Medium" if 0.6 <= first_score < 0.8 else "Far" if 0.3 <= first_score < 0.6 else "Too Low"
        last_cat = "Light" if 0.8 <= last_score <= 1.0 else "Medium" if 0.6 <= last_score < 0.8 else "Far" if 0.3 <= last_score < 0.6 else "Too Low"
        
        print(f"  {i}. {var:25s}")
        print(f"      First: {first_score:.4f} ({first_cat:8s}), Last: {last_score:.4f} ({last_cat:8s})")
    
    # Count distribution
    first_light = sum(1 for s in first_scores if 0.8 <= s <= 1.0)
    first_medium = sum(1 for s in first_scores if 0.6 <= s < 0.8)
    first_far = sum(1 for s in first_scores if 0.3 <= s < 0.6)
    
    last_light = sum(1 for s in last_scores if 0.8 <= s <= 1.0)
    last_medium = sum(1 for s in last_scores if 0.6 <= s < 0.8)
    last_far = sum(1 for s in last_scores if 0.3 <= s < 0.6)
    
    print()
    print("Distribution:")
    print(f"  First Name: Light {first_light}/8, Medium {first_medium}/8, Far {first_far}/8")
    print(f"  Last Name:  Light {last_light}/8, Medium {last_medium}/8, Far {last_far}/8")
    print()
    
    # Score using actual validator function
    print("Scoring with rewards.py:")
    print("-" * 80)
    
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
    
    print(f"Final Score: {final_score:.4f}")
    print(f"Base Score: {base_score:.4f}")
    print()
    print("First Name Similarity Score: {:.4f}".format(
        first_metrics.get('similarity', {}).get('combined', 0)
    ))
    print("Last Name Similarity Score: {:.4f}".format(
        last_metrics.get('similarity', {}).get('combined', 0)
    ))
    print()
    print()

print("="*80)
print("SUMMARY")
print("="*80)
print("The universal letter removal strategy has been tested on multiple names.")
print("Check the similarity scores above to see how well it matches the target")
print("distribution (20% Light, 60% Medium, 20% Far) for both first and last names.")

