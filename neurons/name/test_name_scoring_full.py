#!/usr/bin/env python3
"""
Test Gemini-generated names against actual validator scoring to check if they score 1.0.
Tests all components: similarity, count, uniqueness, length, rules.
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from MIID.validator.gemini_generator import generate_variations_with_gemini
from MIID.validator.reward import (
    calculate_variation_quality,
    calculate_phonetic_similarity,
    calculate_orthographic_similarity,
    MIID_REWARD_WEIGHTS
)
from MIID.protocol import IdentitySynapse

def test_name_scoring(
    original_name: str,
    variations: list,
    phonetic_similarity: dict,
    orthographic_similarity: dict,
    expected_count: int,
    rule_based: dict = None
) -> dict:
    """Test name variations against validator scoring."""
    
    # Extract just the name variations (first element of each [name, dob, address])
    name_variations = [var[0] for var in variations if len(var) > 0 and var[0]]
    
    result = {
        "original_name": original_name,
        "variation_count": len(name_variations),
        "expected_count": expected_count,
        "components": {},
        "final_score": 0.0,
        "base_score": 0.0,
        "all_perfect": False
    }
    
    # Calculate quality using validator's function
    try:
        final_score, base_score, detailed_metrics = calculate_variation_quality(
            original_name=original_name,
            variations=name_variations,
            phonetic_similarity=phonetic_similarity,
            orthographic_similarity=orthographic_similarity,
            expected_count=expected_count,
            rule_based=rule_based
        )
        
        result["final_score"] = final_score
        result["base_score"] = base_score
        result["detailed_metrics"] = detailed_metrics
        
        # Extract component scores
        if "first_name" in detailed_metrics:
            first_metrics = detailed_metrics["first_name"]["metrics"]
            result["components"]["first_name"] = {
                "score": detailed_metrics["first_name"]["score"],
                "similarity": first_metrics.get("similarity", {}),
                "count": first_metrics.get("count", {}),
                "uniqueness": first_metrics.get("uniqueness", {}),
                "length": first_metrics.get("length", {})
            }
        
        if "last_name" in detailed_metrics:
            last_metrics = detailed_metrics["last_name"]["metrics"]
            result["components"]["last_name"] = {
                "score": detailed_metrics["last_name"]["score"],
                "similarity": last_metrics.get("similarity", {}),
                "count": last_metrics.get("count", {}),
                "uniqueness": last_metrics.get("uniqueness", {}),
                "length": last_metrics.get("length", {})
            }
        
        if "rule_compliance" in detailed_metrics:
            result["components"]["rule_compliance"] = {
                "score": detailed_metrics["rule_compliance"]["score"]
            }
        
        # Check if all components are perfect (1.0)
        all_perfect = True
        if "first_name" in result["components"]:
            if result["components"]["first_name"]["score"] < 0.99:
                all_perfect = False
        if "last_name" in result["components"]:
            if result["components"]["last_name"]["score"] < 0.99:
                all_perfect = False
        if final_score < 0.99:
            all_perfect = False
        
        result["all_perfect"] = all_perfect
        
    except Exception as e:
        result["error"] = str(e)
        import traceback
        result["traceback"] = traceback.format_exc()
    
    return result

def main():
    """Test Gemini names against full validator scoring."""
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not set")
        return
    
    # Test with a complex query that has similarity distributions
    query_template = """Generate 15 variations of {name}, ensuring phonetic similarity based on 10% Light, 50% Medium, and 40% Far types, and orthographic similarity based on 20% Light, 60% Medium, and 20% Far types. Approximately 30% of the total 15 variations should follow these rule-based transformations: Replace random consonants with different consonants, Replace random vowels with different vowels, and Delete a random letter. The following address is the seed country/city to generate address variations for: {address}. Generate unique real addresses within the specified country/city for each variation. The following date of birth is the seed DOB to generate variations for: {dob}."""
    
    synapse = IdentitySynapse(
        identity=[
            ["John Smith", "1990-05-15", "New York, USA"]
        ],
        query_template=query_template,
        timeout=360.0
    )
    
    print("="*80)
    print("Testing Gemini Names Against Full Validator Scoring")
    print("="*80)
    
    print("\n🔄 Generating variations with Gemini...")
    try:
        variations = generate_variations_with_gemini(
            synapse,
            gemini_api_key=api_key,
            gemini_model="gemini-2.0-flash-exp"
        )
    except Exception as e:
        print(f"❌ Generation failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("✅ Generation complete\n")
    
    # Test each name
    for name, var_list in variations.items():
        if isinstance(var_list, dict):
            var_list = var_list.get('variations', [])
        
        print("="*80)
        print(f"Testing: {name}")
        print("="*80)
        print(f"Variations generated: {len(var_list)}\n")
        
        # Parse requirements from query template
        phonetic_similarity = {
            "Light": 0.10,
            "Medium": 0.50,
            "Far": 0.40
        }
        orthographic_similarity = {
            "Light": 0.20,
            "Medium": 0.60,
            "Far": 0.20
        }
        expected_count = 15
        rule_based = {
            "rule_percentage": 0.30,
            "selected_rules": ["replace_consonants", "replace_vowels", "delete_letter"]
        }
        
        # Test scoring
        result = test_name_scoring(
            original_name=name,
            variations=var_list,
            phonetic_similarity=phonetic_similarity,
            orthographic_similarity=orthographic_similarity,
            expected_count=expected_count,
            rule_based=rule_based
        )
        
        if "error" in result:
            print(f"❌ Error: {result['error']}")
            print(result.get("traceback", ""))
            continue
        
        # Display results
        print(f"📊 FINAL SCORE: {result['final_score']:.4f}")
        print(f"📊 BASE SCORE: {result['base_score']:.4f}")
        print()
        
        # Component breakdown
        print("Component Scores:")
        print("-" * 80)
        
        if "first_name" in result["components"]:
            fn = result["components"]["first_name"]
            print(f"\n👤 First Name Score: {fn['score']:.4f}")
            print(f"   Similarity: {fn['similarity'].get('combined', 0):.4f}")
            print(f"     - Phonetic: {fn['similarity'].get('phonetic', 0):.4f}")
            print(f"     - Orthographic: {fn['similarity'].get('orthographic', 0):.4f}")
            print(f"   Count: {fn['count'].get('score', 0):.4f} ({fn['count'].get('actual', 0)}/{fn['count'].get('expected', 0)})")
            print(f"   Uniqueness: {fn['uniqueness'].get('score', 0):.4f} ({fn['uniqueness'].get('unique_count', 0)}/{fn['uniqueness'].get('total_count', 0)})")
            print(f"   Length: {fn['length'].get('score', 0):.4f}")
        
        if "last_name" in result["components"]:
            ln = result["components"]["last_name"]
            print(f"\n👤 Last Name Score: {ln['score']:.4f}")
            print(f"   Similarity: {ln['similarity'].get('combined', 0):.4f}")
            print(f"     - Phonetic: {ln['similarity'].get('phonetic', 0):.4f}")
            print(f"     - Orthographic: {ln['similarity'].get('orthographic', 0):.4f}")
            print(f"   Count: {ln['count'].get('score', 0):.4f} ({ln['count'].get('actual', 0)}/{ln['count'].get('expected', 0)})")
            print(f"   Uniqueness: {ln['uniqueness'].get('score', 0):.4f} ({ln['uniqueness'].get('unique_count', 0)}/{ln['uniqueness'].get('total_count', 0)})")
            print(f"   Length: {ln['length'].get('score', 0):.4f}")
        
        if "rule_compliance" in result["components"]:
            rc = result["components"]["rule_compliance"]
            print(f"\n📋 Rule Compliance Score: {rc['score']:.4f}")
        
        # Check each component
        print("\n" + "="*80)
        print("Component Analysis:")
        print("="*80)
        
        all_components_perfect = True
        
        # Similarity (60% weight)
        if "first_name" in result["components"]:
            fn_sim = result["components"]["first_name"]["similarity"].get("combined", 0)
            if fn_sim >= 0.99:
                print(f"✅ First Name Similarity: {fn_sim:.4f} (PERFECT)")
            else:
                print(f"⚠️  First Name Similarity: {fn_sim:.4f} (needs improvement)")
                all_components_perfect = False
        
        if "last_name" in result["components"]:
            ln_sim = result["components"]["last_name"]["similarity"].get("combined", 0)
            if ln_sim >= 0.99:
                print(f"✅ Last Name Similarity: {ln_sim:.4f} (PERFECT)")
            else:
                print(f"⚠️  Last Name Similarity: {ln_sim:.4f} (needs improvement)")
                all_components_perfect = False
        
        # Count (15% weight)
        if "first_name" in result["components"]:
            fn_count = result["components"]["first_name"]["count"].get("score", 0)
            if fn_count >= 0.99:
                print(f"✅ First Name Count: {fn_count:.4f} (PERFECT)")
            else:
                print(f"⚠️  First Name Count: {fn_count:.4f} (needs improvement)")
                all_components_perfect = False
        
        if "last_name" in result["components"]:
            ln_count = result["components"]["last_name"]["count"].get("score", 0)
            if ln_count >= 0.99:
                print(f"✅ Last Name Count: {ln_count:.4f} (PERFECT)")
            else:
                print(f"⚠️  Last Name Count: {ln_count:.4f} (needs improvement)")
                all_components_perfect = False
        
        # Uniqueness (10% weight)
        if "first_name" in result["components"]:
            fn_unique = result["components"]["first_name"]["uniqueness"].get("score", 0)
            if fn_unique >= 0.99:
                print(f"✅ First Name Uniqueness: {fn_unique:.4f} (PERFECT)")
            else:
                print(f"⚠️  First Name Uniqueness: {fn_unique:.4f} (needs improvement)")
                all_components_perfect = False
        
        if "last_name" in result["components"]:
            ln_unique = result["components"]["last_name"]["uniqueness"].get("score", 0)
            if ln_unique >= 0.99:
                print(f"✅ Last Name Uniqueness: {ln_unique:.4f} (PERFECT)")
            else:
                print(f"⚠️  Last Name Uniqueness: {ln_unique:.4f} (needs improvement)")
                all_components_perfect = False
        
        # Length (15% weight)
        if "first_name" in result["components"]:
            fn_length = result["components"]["first_name"]["length"].get("score", 0)
            if fn_length >= 0.99:
                print(f"✅ First Name Length: {fn_length:.4f} (PERFECT)")
            else:
                print(f"⚠️  First Name Length: {fn_length:.4f} (needs improvement)")
                all_components_perfect = False
        
        if "last_name" in result["components"]:
            ln_length = result["components"]["last_name"]["length"].get("score", 0)
            if ln_length >= 0.99:
                print(f"✅ Last Name Length: {ln_length:.4f} (PERFECT)")
            else:
                print(f"⚠️  Last Name Length: {ln_length:.4f} (needs improvement)")
                all_components_perfect = False
        
        # Rule Compliance (20% weight)
        if "rule_compliance" in result["components"]:
            rc_score = result["components"]["rule_compliance"]["score"]
            if rc_score >= 0.99:
                print(f"✅ Rule Compliance: {rc_score:.4f} (PERFECT)")
            else:
                print(f"⚠️  Rule Compliance: {rc_score:.4f} (needs improvement)")
                all_components_perfect = False
        
        # Final verdict
        print("\n" + "="*80)
        if result["final_score"] >= 0.99:
            print("🎉 PERFECT SCORE! All components are optimal!")
        elif result["final_score"] >= 0.90:
            print("✅ EXCELLENT SCORE! Very close to perfect!")
        elif result["final_score"] >= 0.70:
            print("✅ GOOD SCORE! Above average performance.")
        else:
            print("⚠️  NEEDS IMPROVEMENT - Score below 0.70")
        
        print(f"\nFinal Score: {result['final_score']:.4f} / 1.0")
        print(f"Base Score: {result['base_score']:.4f} / 1.0")
        
        # Show some variations
        print(f"\n📝 Sample Variations (first 5):")
        name_vars = [var[0] for var in var_list[:5] if len(var) > 0]
        for i, var in enumerate(name_vars, 1):
            p_score = calculate_phonetic_similarity(name, var)
            o_score = calculate_orthographic_similarity(name, var)
            print(f"   {i}. {var}")
            print(f"      Phonetic: {p_score:.3f}, Orthographic: {o_score:.3f}")

if __name__ == "__main__":
    main()

