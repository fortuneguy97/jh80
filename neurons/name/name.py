#!/usr/bin/env python3
"""
Name Variation Generator Module

This module generates name variations based on parsed query requirements.
It handles different name types (Latin, Arabic, Cyrillic, CJK) and applies
various transformation techniques to create high-scoring variations.

The module focuses on:
- Phonetic similarity (how names sound)
- Orthographic similarity (how names look)
- Rule-based transformations
- Script-specific variations
"""

import random
import re
from typing import List, Dict, Any, Optional
import bittensor as bt

# Optional imports for enhanced functionality
try:
    import jellyfish
    JELLYFISH_AVAILABLE = True
except ImportError:
    JELLYFISH_AVAILABLE = False
    bt.logging.warning("jellyfish not available - phonetic scoring will be limited")

try:
    from unidecode import unidecode
    UNIDECODE_AVAILABLE = True
except ImportError:
    UNIDECODE_AVAILABLE = False
    bt.logging.warning("unidecode not available - transliteration will be limited")


def generate_name_variations(name: str, parsed_query: Dict[str, Any]) -> List[str]:
    """
    Generate name variations based on parsed query requirements.
    
    This is the main entry point for name variation generation.
    It analyzes the name script and applies appropriate generation strategies.
    
    Args:
        name: The original name to generate variations for
        parsed_query: Parsed requirements from query template
        
    Returns:
        List of name variations that meet the requirements
    """
    bt.logging.info(f"🎯 Generating name variations for: '{name}'")
    
    variation_count = parsed_query.get('variation_count', 15)
    script_type = _detect_script_type(name)
    
    bt.logging.info(f"   📝 Script type: {script_type}")
    bt.logging.info(f"   🔢 Target count: {variation_count}")
    
    # Choose generation strategy based on script type
    if script_type == 'latin':
        variations = _generate_latin_variations(name, parsed_query)
    else:
        variations = _generate_non_latin_variations(name, script_type, parsed_query)
    
    # Ensure we have the right number of variations
    variations = _ensure_variation_count(variations, name, variation_count)
    
    bt.logging.info(f"✅ Generated {len(variations)} name variations")
    return variations


def _detect_script_type(name: str) -> str:
    """
    Detect the script type of the name.
    
    Args:
        name: The name to analyze
        
    Returns:
        Script type: 'latin', 'arabic', 'cyrillic', or 'cjk'
    """
    # Check for Arabic script
    if re.search(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]', name):
        return 'arabic'
    
    # Check for Cyrillic script
    if re.search(r'[\u0400-\u04FF\u0500-\u052F\u2DE0-\u2DFF\uA640-\uA69F]', name):
        return 'cyrillic'
    
    # Check for CJK (Chinese, Japanese, Korean)
    if re.search(r'[\u4E00-\u9FFF\u3400-\u4DBF\u3040-\u309F\u30A0-\u30FF\uAC00-\uD7AF]', name):
        return 'cjk'
    
    # Default to Latin
    return 'latin'


def _generate_latin_variations(name: str, parsed_query: Dict[str, Any]) -> List[str]:
    """
    Generate variations for Latin script names.
    
    Uses multiple strategies:
    1. Rule-based transformations
    2. Phonetic variations
    3. Orthographic variations
    4. Character-level modifications
    """
    variations = []
    used = set([name.lower()])
    
    variation_count = parsed_query.get('variation_count', 15)
    rules = parsed_query.get('rules', [])
    rule_percentage = parsed_query.get('rule_percentage', 0.0)
    
    # Calculate how many variations should follow rules
    rule_count = int(variation_count * rule_percentage)
    
    bt.logging.info(f"   🔧 Rule-based variations needed: {rule_count}")
    
    # Strategy 1: Apply rule-based transformations
    if rules and rule_count > 0:
        rule_variations = _apply_rule_transformations(name, rules, rule_count)
        for var in rule_variations:
            if var.lower() not in used:
                variations.append(var)
                used.add(var.lower())
    
    # Strategy 2: Generate phonetic variations
    remaining = variation_count - len(variations)
    if remaining > 0:
        phonetic_vars = _generate_phonetic_variations(name, remaining // 2)
        for var in phonetic_vars:
            if var.lower() not in used and len(variations) < variation_count:
                variations.append(var)
                used.add(var.lower())
    
    # Strategy 3: Generate orthographic variations
    remaining = variation_count - len(variations)
    if remaining > 0:
        ortho_vars = _generate_orthographic_variations(name, remaining)
        for var in ortho_vars:
            if var.lower() not in used and len(variations) < variation_count:
                variations.append(var)
                used.add(var.lower())
    
    return variations


def _generate_non_latin_variations(name: str, script_type: str, parsed_query: Dict[str, Any]) -> List[str]:
    """
    Generate variations for non-Latin script names.
    
    Combines script-specific transformations with transliteration.
    """
    variations = []
    used = set([name.lower()])
    
    variation_count = parsed_query.get('variation_count', 15)
    
    # Strategy 1: Script-specific transformations
    script_vars = _apply_script_transformations(name, script_type, variation_count // 2)
    for var in script_vars:
        if var.lower() not in used:
            variations.append(var)
            used.add(var.lower())
    
    # Strategy 2: Transliteration + Latin variations
    if UNIDECODE_AVAILABLE and len(variations) < variation_count:
        transliterated = unidecode(name)
        if transliterated and transliterated != name:
            # Create a mini parsed_query for the transliterated version
            latin_query = parsed_query.copy()
            latin_query['variation_count'] = variation_count - len(variations)
            
            latin_vars = _generate_latin_variations(transliterated, latin_query)
            for var in latin_vars:
                if var.lower() not in used and len(variations) < variation_count:
                    variations.append(var)
                    used.add(var.lower())
    
    return variations


def _apply_rule_transformations(name: str, rules: List[str], count: int) -> List[str]:
    """
    Apply specific rule-based transformations to the name.
    
    Args:
        name: Original name
        rules: List of rule identifiers to apply
        count: Number of rule-based variations needed
        
    Returns:
        List of variations created by applying rules
    """
    variations = []
    used = set([name.lower()])
    
    # Distribute count across available rules
    variations_per_rule = max(1, count // len(rules)) if rules else 0
    
    for rule in rules:
        rule_vars = _apply_single_rule(name, rule, variations_per_rule)
        for var in rule_vars:
            if var.lower() not in used and len(variations) < count:
                variations.append(var)
                used.add(var.lower())
    
    return variations


def _apply_single_rule(name: str, rule: str, count: int) -> List[str]:
    """Apply a single transformation rule to generate variations."""
    variations = []
    
    if rule == 'replace_spaces_with_special_characters':
        # Replace spaces with special characters
        if ' ' in name:
            for char in ['_', '-', '.']:
                var = name.replace(' ', char)
                variations.append(var)
                if len(variations) >= count:
                    break
    
    elif rule == 'replace_vowels':
        # Replace vowels with similar characters
        vowels = 'aeiouAEIOU'
        replacements = {'a': '@', 'e': '3', 'i': '1', 'o': '0', 'u': 'v'}
        for i in range(count):
            var = name
            for vowel in vowels:
                if vowel.lower() in replacements and vowel in var:
                    var = var.replace(vowel, replacements[vowel.lower()])
                    break
            if var != name:
                variations.append(var)
    
    elif rule == 'delete_letter':
        # Remove a random letter
        for i in range(count):
            if len(name) > 2:
                idx = random.randint(0, len(name) - 1)
                var = name[:idx] + name[idx+1:]
                variations.append(var)
    
    elif rule == 'swap_random_letter':
        # Swap adjacent letters
        for i in range(count):
            if len(name) >= 2:
                idx = random.randint(0, len(name) - 2)
                var = name[:idx] + name[idx+1] + name[idx] + name[idx+2:]
                variations.append(var)
    
    elif rule == 'shorten_name_to_initials':
        # Convert to initials
        parts = name.split()
        if len(parts) >= 2:
            initials = '.'.join([p[0].upper() for p in parts])
            variations.append(initials)
    
    elif rule == 'reorder_name_parts':
        # Reorder name parts
        parts = name.split()
        if len(parts) >= 2:
            # Reverse order
            variations.append(' '.join(parts[::-1]))
            # Last name first
            if len(parts) > 2:
                variations.append(f"{parts[-1]} {' '.join(parts[:-1])}")
    
    return variations[:count]


def _generate_phonetic_variations(name: str, count: int) -> List[str]:
    """
    Generate variations that sound similar to the original name.
    
    Uses phonetic transformation rules to create variations that
    have high phonetic similarity scores.
    """
    variations = []
    used = set([name.lower()])
    
    # Common phonetic transformations
    phonetic_rules = [
        ('ph', 'f'), ('f', 'ph'),  # philip <-> filip
        ('c', 'k'), ('k', 'c'),    # carl <-> karl
        ('s', 'z'), ('z', 's'),    # susan <-> zuzan
        ('i', 'y'), ('y', 'i'),    # smith <-> smyth
        ('ck', 'k'), ('k', 'ck'),  # nick <-> nik
    ]
    
    attempts = 0
    while len(variations) < count and attempts < count * 3:
        attempts += 1
        
        # Apply phonetic transformations
        for old, new in phonetic_rules:
            if old in name.lower():
                var = name.replace(old, new)
                if var.lower() not in used:
                    variations.append(var)
                    used.add(var.lower())
                    if len(variations) >= count:
                        break
        
        # Remove double letters
        if len(variations) < count:
            for i in range(len(name) - 1):
                if name[i] == name[i + 1]:
                    var = name[:i] + name[i+1:]
                    if var.lower() not in used:
                        variations.append(var)
                        used.add(var.lower())
                        break
    
    return variations[:count]


def _generate_orthographic_variations(name: str, count: int) -> List[str]:
    """
    Generate variations that look similar to the original name.
    
    Uses character-level modifications to create variations with
    controlled orthographic similarity.
    """
    variations = []
    used = set([name.lower()])
    
    attempts = 0
    while len(variations) < count and attempts < count * 5:
        attempts += 1
        
        # Character substitution
        if len(name) > 1:
            idx = random.randint(0, len(name) - 1)
            char = name[idx]
            # Similar looking characters
            similar_chars = {
                'a': ['@', 'α'], 'e': ['3', 'ε'], 'i': ['1', 'l'], 'o': ['0', 'ο'],
                's': ['$', '5'], 't': ['+', '7'], 'l': ['1', 'I'], 'g': ['9', 'q']
            }
            if char.lower() in similar_chars:
                replacement = random.choice(similar_chars[char.lower()])
                var = name[:idx] + replacement + name[idx+1:]
                if var.lower() not in used:
                    variations.append(var)
                    used.add(var.lower())
        
        # Character insertion
        if len(variations) < count and len(name) > 1:
            idx = random.randint(0, len(name))
            char = random.choice('aeiou')
            var = name[:idx] + char + name[idx:]
            if var.lower() not in used:
                variations.append(var)
                used.add(var.lower())
        
        # Character deletion
        if len(variations) < count and len(name) > 2:
            idx = random.randint(0, len(name) - 1)
            var = name[:idx] + name[idx+1:]
            if var.lower() not in used:
                variations.append(var)
                used.add(var.lower())
    
    return variations[:count]


def _apply_script_transformations(name: str, script_type: str, count: int) -> List[str]:
    """Apply script-specific transformations for non-Latin names."""
    variations = []
    used = set([name.lower()])
    parts = name.split()
    
    if script_type in ['arabic', 'cyrillic']:
        # Swap name parts
        if len(parts) >= 2:
            swapped = " ".join([parts[-1]] + parts[:-1])
            if swapped.lower() not in used:
                variations.append(swapped)
                used.add(swapped.lower())
        
        # Remove spaces (merge parts)
        if len(parts) >= 2:
            merged = "".join(parts)
            if merged.lower() not in used:
                variations.append(merged)
                used.add(merged.lower())
        
        # Reverse parts order
        if len(parts) >= 2:
            reversed_parts = " ".join(parts[::-1])
            if reversed_parts.lower() not in used:
                variations.append(reversed_parts)
                used.add(reversed_parts.lower())
    
    # Fill remaining with character-level modifications
    while len(variations) < count:
        if len(name) > 2:
            # Random character removal
            idx = random.randint(0, len(name) - 1)
            var = name[:idx] + name[idx+1:]
            if var and var.lower() not in used:
                variations.append(var)
                used.add(var.lower())
        
        if len(variations) >= count:
            break
        
        # Random character duplication
        if len(name) > 1:
            idx = random.randint(0, len(name) - 1)
            var = name[:idx+1] + name[idx] + name[idx+1:]
            if var.lower() not in used:
                variations.append(var)
                used.add(var.lower())
    
    return variations[:count]


def _ensure_variation_count(variations: List[str], original_name: str, target_count: int) -> List[str]:
    """
    Ensure we have exactly the target number of variations.
    
    If we have too few, generate simple variations to fill the gap.
    If we have too many, trim to the target count.
    """
    if len(variations) >= target_count:
        return variations[:target_count]
    
    # Need more variations - generate simple ones
    used = set([var.lower() for var in variations] + [original_name.lower()])
    
    while len(variations) < target_count:
        # Simple character modifications
        base_name = random.choice([original_name] + variations[:3])
        
        if len(base_name) > 2:
            # Remove a character
            idx = random.randint(0, len(base_name) - 1)
            var = base_name[:idx] + base_name[idx+1:]
            if var and var.lower() not in used:
                variations.append(var)
                used.add(var.lower())
                continue
        
        # Add a character
        idx = random.randint(0, len(base_name))
        char = random.choice('aeiou')
        var = base_name[:idx] + char + base_name[idx:]
        if var.lower() not in used:
            variations.append(var)
            used.add(var.lower())
    
    return variations[:target_count]


if __name__ == "__main__":
    # Test the name generator
    sample_query = {
        'variation_count': 10,
        'rule_percentage': 0.3,
        'rules': ['swap_random_letter', 'delete_letter'],
        'phonetic_similarity': {'Light': 0.4, 'Medium': 0.4, 'Far': 0.2},
        'orthographic_similarity': {'Light': 0.5, 'Medium': 0.5}
    }
    
    test_names = ["John Smith", "رشيد البزال", "Müller"]
    
    for name in test_names:
        print(f"\nTesting: {name}")
        variations = generate_name_variations(name, sample_query)
        print(f"Generated: {variations}")