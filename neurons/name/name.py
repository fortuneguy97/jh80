#!/usr/bin/env python3
"""
Name Variation Generator Module

This module coordinates name variation generation by delegating to specialized
rule-based and non-rule-based variation generators. It calculates the appropriate
counts for each approach and combines the results.

The module focuses on:
- Calculating rule-based vs non-rule-based variation counts
- Delegating to specialized variation generators
- Combining and returning final variation lists
"""

import random
from typing import List, Dict, Any
import bittensor as bt

# Import specialized variation generators
from .rule_based_variations import generate_rule_based_variations
from .non_rule_based_variations import (
    generate_ollama_variations,
    generate_ollama_variations_with_dedup,
    generate_phonetic_variations,
    generate_orthographic_variations,
    generate_script_specific_variations,
    generate_transliteration_variations,
    generate_fallback_variations,
    detect_script_type
)


def generate_name_variations(name: str, parsed_query: Dict[str, Any]) -> List[str]:
    """
    Generate name variations based on parsed query requirements.
    
    This is the main coordinator that:
    1. Calculates rule-based vs non-rule-based counts
    2. Delegates to specialized generators
    3. Combines and returns results
    
    Args:
        name: The original name to generate variations for
        parsed_query: Parsed requirements from query template
        
    Returns:
        List of name variations that meet the requirements
    """
    bt.logging.info(f"🎯 Generating name variations for: '{name}'")
    
    # Extract parameters from parsed query
    variation_count = parsed_query.get('variation_count', 15)
    rule_percentage = parsed_query.get('rule_percentage', 0.0)
    rules = parsed_query.get('rules', [])
    
    # Calculate counts for each approach
    rule_based_count = int(variation_count * rule_percentage) if rules else 0
    non_rule_based_count = variation_count - rule_based_count
    
    variations = []
    used = set([name.lower()])
    
    # Generate rule-based variations first
    rule_variations = []
    if rule_based_count > 0 and rules:
        
        rule_variations = generate_rule_based_variations(name, rules, rule_based_count)
        
        print("--------------rule--------------")
        print(rule_variations)
        # Add rule-based variations to used set and final list
        for var in rule_variations:
            if var.lower() not in used:
                variations.append(var)
                used.add(var.lower())
        
    # Generate non-rule-based variations with deduplication
    if non_rule_based_count > 0:
        
        # Extract similarity requirements
        phonetic_similarity = parsed_query.get('phonetic_similarity', {})
        orthographic_similarity = parsed_query.get('orthographic_similarity', {})
        
        # Pass the used set to prevent duplicates
        non_rule_variations = generate_ollama_variations_with_dedup(
            name, non_rule_based_count, phonetic_similarity, orthographic_similarity, used.copy()
        )
        print("-----------------non_rule---------------")
        print(non_rule_variations)
        # Add non-rule variations with deduplication
        added_count = 0
        for var in non_rule_variations:
            if var.lower() not in used:
                variations.append(var)
                used.add(var.lower())
                added_count += 1
        
    
    # Ensure we have the target count
    if len(variations) < variation_count:
        bt.logging.info("   🔄 Generating fallback variations...")
        fallback_vars = generate_fallback_variations(name, variations, variation_count)
        variations.extend(fallback_vars)
    
    # Trim to exact count if we have too many
    variations = variations[:variation_count]
    
    return variations


def _generate_non_rule_based_variations(
    name: str, 
    count: int, 
    phonetic_similarity: Dict[str, float], 
    orthographic_similarity: Dict[str, float],
    used: set
) -> List[str]:
    """
    Generate non-rule-based variations using phonetic and orthographic similarity.
    
    Args:
        name: Original name
        count: Number of variations to generate
        phonetic_similarity: Phonetic similarity requirements (Light/Medium/Far percentages)
        orthographic_similarity: Orthographic similarity requirements (Light/Medium percentages)
        used: Set of already used variations (lowercase)
        
    Returns:
        List of non-rule-based variations
    """
    variations = []
    script_type = detect_script_type(name)
    
    bt.logging.debug(f"   📝 Script type: {script_type}")
    bt.logging.debug(f"   🎵 Phonetic similarity: {phonetic_similarity}")
    bt.logging.debug(f"   👁️ Orthographic similarity: {orthographic_similarity}")
    
    # Calculate distribution based on similarity requirements
    phonetic_count = 0
    orthographic_count = 0
    script_count = 0
    transliteration_count = 0
    
    # Distribute count based on similarity percentages
    if phonetic_similarity:
        total_phonetic = sum(phonetic_similarity.values())
        phonetic_count = int(count * total_phonetic * 0.4)  # 40% for phonetic
    
    if orthographic_similarity:
        total_orthographic = sum(orthographic_similarity.values())
        orthographic_count = int(count * total_orthographic * 0.4)  # 40% for orthographic
    
    # Remaining for script-specific and transliteration
    remaining = count - phonetic_count - orthographic_count
    if script_type != 'latin':
        transliteration_count = remaining // 2
        script_count = remaining - transliteration_count
    else:
        script_count = remaining
    
    bt.logging.debug(f"   🎵 Phonetic variations: {phonetic_count}")
    bt.logging.debug(f"   👁️ Orthographic variations: {orthographic_count}")
    bt.logging.debug(f"   📝 Script-specific variations: {script_count}")
    bt.logging.debug(f"   🔄 Transliteration variations: {transliteration_count}")
    
    # Generate phonetic variations
    if phonetic_count > 0:
        phonetic_vars = generate_phonetic_variations(name, phonetic_count)
        for var in phonetic_vars:
            if var.lower() not in used:
                variations.append(var)
                used.add(var.lower())
    
    # Generate orthographic variations
    if orthographic_count > 0:
        ortho_vars = generate_orthographic_variations(name, orthographic_count)
        for var in ortho_vars:
            if var.lower() not in used:
                variations.append(var)
                used.add(var.lower())
    
    # Generate script-specific variations
    if script_count > 0:
        script_vars = generate_script_specific_variations(name, script_type, script_count)
        for var in script_vars:
            if var.lower() not in used:
                variations.append(var)
                used.add(var.lower())
    
    # Generate transliteration variations for non-Latin names
    if transliteration_count > 0 and script_type != 'latin':
        trans_vars = generate_transliteration_variations(name, transliteration_count)
        for var in trans_vars:
            if var.lower() not in used:
                variations.append(var)
                used.add(var.lower())
    
    return variations





if __name__ == "__main__":
    # Test the coordinated name generator
    sample_query = {
        'variation_count': 10,
        'rule_percentage': 0.3,
        'rules': ['swap_random_letter', 'delete_letter'],
        'phonetic_similarity': {'Light': 0.4, 'Medium': 0.4, 'Far': 0.2},
        'orthographic_similarity': {'Light': 0.5, 'Medium': 0.5}
    }
    
    test_names = ["John Smith", "رشيد البزال", "Müller"]
    
    for name in test_names:
        print(f"\nTesting coordinated generation for: {name}")
        variations = generate_name_variations(name, sample_query)
        print(f"Generated {len(variations)} variations: {variations}")