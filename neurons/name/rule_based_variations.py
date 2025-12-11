#!/usr/bin/env python3
"""
Rule-Based Name Variation Generator

This module generates name variations using specific transformation rules.
It applies deterministic rules based on parsed query requirements to create
controlled variations that follow specific patterns.

The module focuses on:
- Applying specific transformation rules (replace, swap, delete, etc.)
- Maintaining exact rule percentage compliance
- Ensuring uniqueness and quality of rule-based variations
"""

import random
import re
from typing import List, Dict, Any, Set
import bittensor as bt

# Optional imports for enhanced functionality
try:
    import jellyfish
    JELLYFISH_AVAILABLE = True
except ImportError:
    JELLYFISH_AVAILABLE = False
    bt.logging.warning("jellyfish not available - phonetic scoring will be limited")


def generate_rule_based_variations(name: str, rules: List[str], count: int) -> List[str]:
    """
    Generate rule-based name variations using specific transformation rules.
    
    Args:
        name: The original name to generate variations for
        rules: List of rule identifiers to apply
        count: Number of rule-based variations to generate
        
    Returns:
        List of rule-based name variations
    """
    bt.logging.debug(f"🔧 Generating {count} rule-based variations for: '{name}'")
    bt.logging.debug(f"   📋 Rules to apply: {rules}")
    
    if count <= 0 or not rules:
        return []
    
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
    
    bt.logging.debug(f"   ✅ Generated {len(variations)} rule-based variations")
    return variations


def _apply_single_rule(name: str, rule: str, count: int) -> List[str]:
    """
    Apply a single transformation rule to generate variations.
    
    Args:
        name: Original name
        rule: Rule identifier to apply
        count: Number of variations to generate with this rule
        
    Returns:
        List of variations created by applying the rule
    """
    variations = []
    
    if rule == 'replace_spaces_with_special_characters':
        variations.extend(_replace_spaces_with_special_characters(name, count))
    
    elif rule == 'replace_vowels':
        variations.extend(_replace_vowels(name, count))
    
    elif rule == 'delete_letter':
        variations.extend(_delete_letter(name, count))
    
    elif rule == 'swap_random_letter':
        variations.extend(_swap_random_letter(name, count))
    
    elif rule == 'shorten_name_to_initials':
        variations.extend(_shorten_name_to_initials(name, count))
    
    elif rule == 'reorder_name_parts':
        variations.extend(_reorder_name_parts(name, count))
    
    elif rule == 'add_special_characters':
        variations.extend(_add_special_characters(name, count))
    
    elif rule == 'capitalize_random_letters':
        variations.extend(_capitalize_random_letters(name, count))
    
    elif rule == 'duplicate_letters':
        variations.extend(_duplicate_letters(name, count))
    
    elif rule == 'reverse_name':
        variations.extend(_reverse_name(name, count))
    
    elif rule == 'add_accents':
        variations.extend(_add_accents(name, count))
    
    elif rule == 'remove_accents':
        variations.extend(_remove_accents(name, count))
    
    elif rule == 'change_case_pattern':
        variations.extend(_change_case_pattern(name, count))
    
    elif rule == 'add_hyphens':
        variations.extend(_add_hyphens(name, count))
    
    elif rule == 'remove_hyphens':
        variations.extend(_remove_hyphens(name, count))
    
    elif rule == 'phonetic_substitution':
        variations.extend(_phonetic_substitution(name, count))
    
    elif rule == 'double_consonants':
        variations.extend(_double_consonants(name, count))
    
    elif rule == 'simplify_consonants':
        variations.extend(_simplify_consonants(name, count))
    
    else:
        bt.logging.warning(f"Unknown rule: {rule}")
    
    return variations[:count]


def _replace_spaces_with_special_characters(name: str, count: int) -> List[str]:
    """Replace spaces with special characters."""
    variations = []
    if ' ' in name:
        special_chars = ['_', '-', '.', '+', '=', '~']
        for i, char in enumerate(special_chars):
            if i >= count:
                break
            var = name.replace(' ', char)
            variations.append(var)
    return variations


def _replace_vowels(name: str, count: int) -> List[str]:
    """Replace vowels with similar characters or numbers."""
    variations = []
    vowel_replacements = {
        'a': ['@', '4', 'α'], 'A': ['@', '4', 'Α'],
        'e': ['3', 'ε', '€'], 'E': ['3', 'Ε', '€'],
        'i': ['1', '!', 'ι'], 'I': ['1', '!', 'Ι'],
        'o': ['0', 'ο', '°'], 'O': ['0', 'Ο', '°'],
        'u': ['μ', 'υ', 'ü'], 'U': ['Μ', 'Υ', 'Ü']
    }
    
    for i in range(count):
        var = name
        # Replace one vowel at a time
        for vowel in 'aeiouAEIOU':
            if vowel in var and vowel in vowel_replacements:
                replacement = random.choice(vowel_replacements[vowel])
                var = var.replace(vowel, replacement, 1)  # Replace only first occurrence
                break
        
        if var != name:
            variations.append(var)
        
        if len(variations) >= count:
            break
    
    return variations


def _delete_letter(name: str, count: int) -> List[str]:
    """Remove random letters from the name."""
    variations = []
    
    for i in range(count):
        if len(name) > 2:  # Don't make names too short
            idx = random.randint(0, len(name) - 1)
            var = name[:idx] + name[idx+1:]
            variations.append(var)
    
    return variations


def _swap_random_letter(name: str, count: int) -> List[str]:
    """Swap adjacent letters in the name."""
    variations = []
    
    for i in range(count):
        if len(name) >= 2:
            idx = random.randint(0, len(name) - 2)
            var = name[:idx] + name[idx+1] + name[idx] + name[idx+2:]
            variations.append(var)
    
    return variations


def _shorten_name_to_initials(name: str, count: int) -> List[str]:
    """Convert name to initials in various formats."""
    variations = []
    parts = name.split()
    
    if len(parts) >= 2:
        # Different initial formats
        formats = [
            '.'.join([p[0].upper() for p in parts]),  # J.S.
            ''.join([p[0].upper() for p in parts]),   # JS
            ' '.join([p[0].upper() for p in parts]),  # J S
            '-'.join([p[0].upper() for p in parts]),  # J-S
        ]
        
        for i, fmt in enumerate(formats):
            if i >= count:
                break
            variations.append(fmt)
    
    return variations


def _reorder_name_parts(name: str, count: int) -> List[str]:
    """Reorder parts of the name in different ways."""
    variations = []
    parts = name.split()
    
    if len(parts) >= 2:
        reorder_patterns = [
            parts[::-1],  # Reverse order
            [parts[-1]] + parts[:-1],  # Last first
            [parts[0]] + parts[:0:-1],  # First + reverse rest
        ]
        
        # Add random shuffles
        for _ in range(count - len(reorder_patterns)):
            shuffled = parts.copy()
            random.shuffle(shuffled)
            reorder_patterns.append(shuffled)
        
        for i, pattern in enumerate(reorder_patterns):
            if i >= count:
                break
            var = ' '.join(pattern)
            if var != name:
                variations.append(var)
    
    return variations


def _add_special_characters(name: str, count: int) -> List[str]:
    """Add special characters to the name."""
    variations = []
    special_chars = ['!', '@', '#', '$', '%', '&', '*', '+', '=', '~']
    
    for i in range(count):
        char = random.choice(special_chars)
        position = random.choice(['start', 'end', 'middle'])
        
        if position == 'start':
            var = char + name
        elif position == 'end':
            var = name + char
        else:  # middle
            idx = random.randint(1, len(name) - 1)
            var = name[:idx] + char + name[idx:]
        
        variations.append(var)
    
    return variations


def _capitalize_random_letters(name: str, count: int) -> List[str]:
    """Randomly capitalize letters in the name."""
    variations = []
    
    for i in range(count):
        var = ''
        for char in name:
            if char.isalpha():
                var += char.upper() if random.random() > 0.5 else char.lower()
            else:
                var += char
        
        if var != name:
            variations.append(var)
    
    return variations


def _duplicate_letters(name: str, count: int) -> List[str]:
    """Duplicate random letters in the name."""
    variations = []
    
    for i in range(count):
        if len(name) > 1:
            idx = random.randint(0, len(name) - 1)
            var = name[:idx+1] + name[idx] + name[idx+1:]
            variations.append(var)
    
    return variations


def _reverse_name(name: str, count: int) -> List[str]:
    """Reverse the name or parts of it."""
    variations = []
    
    # Full reverse
    variations.append(name[::-1])
    
    # Reverse each word separately
    parts = name.split()
    if len(parts) > 1:
        reversed_parts = [part[::-1] for part in parts]
        variations.append(' '.join(reversed_parts))
    
    # Reverse character pairs
    if len(name) >= 4:
        var = ''
        for i in range(0, len(name) - 1, 2):
            if i + 1 < len(name):
                var += name[i+1] + name[i]
            else:
                var += name[i]
        variations.append(var)
    
    return variations[:count]


if __name__ == "__main__":
    # Test rule-based variations
    test_name = "John Smith"
    test_rules = [
        'replace_spaces_with_special_characters',
        'replace_vowels',
        'delete_letter',
        'swap_random_letter',
        'shorten_name_to_initials',
        'reorder_name_parts'
    ]
    
    print(f"Testing rule-based variations for: {test_name}")
    
    for rule in test_rules:
        print(f"\nRule: {rule}")
        variations = generate_rule_based_variations(test_name, [rule], 3)
        print(f"Variations: {variations}")

def _add_accents(name: str, count: int) -> List[str]:
    """Add accents to vowels in the name."""
    variations = []
    
    accent_map = {
        'a': ['à', 'á', 'â', 'ã', 'ä', 'å'],
        'e': ['è', 'é', 'ê', 'ë'],
        'i': ['ì', 'í', 'î', 'ï'],
        'o': ['ò', 'ó', 'ô', 'õ', 'ö'],
        'u': ['ù', 'ú', 'û', 'ü'],
        'A': ['À', 'Á', 'Â', 'Ã', 'Ä', 'Å'],
        'E': ['È', 'É', 'Ê', 'Ë'],
        'I': ['Ì', 'Í', 'Î', 'Ï'],
        'O': ['Ò', 'Ó', 'Ô', 'Õ', 'Ö'],
        'U': ['Ù', 'Ú', 'Û', 'Ü']
    }
    
    for i in range(count):
        var = name
        for char in name:
            if char in accent_map:
                accented = random.choice(accent_map[char])
                var = var.replace(char, accented, 1)
                break
        
        if var != name:
            variations.append(var)
    
    return variations


def _remove_accents(name: str, count: int) -> List[str]:
    """Remove accents from the name."""
    variations = []
    
    if UNIDECODE_AVAILABLE:
        unaccented = unidecode(name)
        if unaccented != name:
            variations.append(unaccented)
    
    # Manual accent removal
    accent_map = {
        'à': 'a', 'á': 'a', 'â': 'a', 'ã': 'a', 'ä': 'a', 'å': 'a',
        'è': 'e', 'é': 'e', 'ê': 'e', 'ë': 'e',
        'ì': 'i', 'í': 'i', 'î': 'i', 'ï': 'i',
        'ò': 'o', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ö': 'o',
        'ù': 'u', 'ú': 'u', 'û': 'u', 'ü': 'u',
        'À': 'A', 'Á': 'A', 'Â': 'A', 'Ã': 'A', 'Ä': 'A', 'Å': 'A',
        'È': 'E', 'É': 'E', 'Ê': 'E', 'Ë': 'E',
        'Ì': 'I', 'Í': 'I', 'Î': 'I', 'Ï': 'I',
        'Ò': 'O', 'Ó': 'O', 'Ô': 'O', 'Õ': 'O', 'Ö': 'O',
        'Ù': 'U', 'Ú': 'U', 'Û': 'U', 'Ü': 'U'
    }
    
    var = name
    for accented, plain in accent_map.items():
        var = var.replace(accented, plain)
    
    if var != name and len(variations) < count:
        variations.append(var)
    
    return variations[:count]


def _change_case_pattern(name: str, count: int) -> List[str]:
    """Change capitalization patterns."""
    variations = []
    
    if len(name) > 1:
        # Title case
        variations.append(name.title())
        
        # First letter lowercase
        variations.append(name[0].lower() + name[1:])
        
        # All caps first word only
        parts = name.split()
        if len(parts) > 1:
            variations.append(parts[0].upper() + ' ' + ' '.join(parts[1:]))
        
        # Alternating case
        alt_case = ''
        for i, char in enumerate(name):
            if char.isalpha():
                alt_case += char.upper() if i % 2 == 0 else char.lower()
            else:
                alt_case += char
        if alt_case != name:
            variations.append(alt_case)
    
    return variations[:count]


def _add_hyphens(name: str, count: int) -> List[str]:
    """Add hyphens to the name."""
    variations = []
    parts = name.split()
    
    if len(parts) >= 2:
        # Hyphenate all parts
        variations.append('-'.join(parts))
        
        # Hyphenate first two parts only
        if len(parts) > 2:
            variations.append(f"{parts[0]}-{parts[1]} {' '.join(parts[2:])}")
        
        # Hyphenate last two parts only
        if len(parts) > 2:
            variations.append(f"{' '.join(parts[:-2])} {parts[-2]}-{parts[-1]}")
    
    return variations[:count]


def _remove_hyphens(name: str, count: int) -> List[str]:
    """Remove hyphens from the name."""
    variations = []
    
    if '-' in name:
        # Remove all hyphens
        variations.append(name.replace('-', ' '))
        
        # Remove hyphens but keep as one word
        variations.append(name.replace('-', ''))
    
    return variations[:count]


def _phonetic_substitution(name: str, count: int) -> List[str]:
    """Apply phonetic substitutions."""
    variations = []
    
    phonetic_rules = [
        ('ph', 'f'), ('f', 'ph'),
        ('c', 'k'), ('k', 'c'),
        ('s', 'z'), ('z', 's'),
        ('i', 'y'), ('y', 'i'),
        ('ck', 'k'), ('k', 'ck'),
        ('th', 't'), ('t', 'th'),
        ('w', 'v'), ('v', 'w'),
        ('j', 'g'), ('g', 'j'),
        ('x', 'ks'), ('ks', 'x'),
        ('qu', 'kw'), ('kw', 'qu')
    ]
    
    for old, new in phonetic_rules:
        if len(variations) >= count:
            break
        if old in name.lower():
            var = name.replace(old, new)
            if var != name:
                variations.append(var)
    
    return variations[:count]


def _double_consonants(name: str, count: int) -> List[str]:
    """Double consonants in the name."""
    variations = []
    consonants = 'bcdfghjklmnpqrstvwxz'
    
    for i in range(len(name)):
        if len(variations) >= count:
            break
        if name[i].lower() in consonants:
            var = name[:i+1] + name[i] + name[i+1:]
            variations.append(var)
    
    return variations[:count]


def _simplify_consonants(name: str, count: int) -> List[str]:
    """Simplify double consonants."""
    variations = []
    
    for i in range(len(name) - 1):
        if len(variations) >= count:
            break
        if name[i] == name[i + 1] and name[i].isalpha():
            var = name[:i] + name[i+1:]
            variations.append(var)
    
    return variations[:count]