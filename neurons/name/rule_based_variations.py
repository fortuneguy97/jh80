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
    
    # Use the comprehensive rule mapping
    for _ in range(count):
        variation = apply_rule_to_name(name, rule)
        if variation and variation != name:
            variations.append(variation)
    
    # Remove duplicates while preserving order
    unique_variations = []
    seen = set()
    for var in variations:
        if var.lower() not in seen:
            unique_variations.append(var)
            seen.add(var.lower())
    
    return unique_variations[:count]


def apply_rule_to_name(name: str, rule: str) -> str:
    """Apply a rule to a name using comprehensive rule mapping"""
    rule_map = {
        # Character replacement
        'replace_spaces_with_special_characters': apply_replace_spaces_with_special_chars,
        'replace_spaces_with_random_special_characters': apply_replace_spaces_with_special_chars,
        'replace_double_letters': apply_replace_double_letters,
        'replace_double_letters_with_single_letter': apply_replace_double_letters,
        'replace_vowels': apply_replace_random_vowels,
        'replace_random_vowels': apply_replace_random_vowels,
        'replace_random_vowel_with_random_vowel': apply_replace_random_vowels,
        'replace_random_consonants': apply_replace_random_consonants,
        'replace_random_consonant_with_random_consonant': apply_replace_random_consonants,
        
        # Character swapping
        'swap_adjacent_consonants': apply_swap_adjacent_consonants,
        'swap_adjacent_syllables': apply_swap_adjacent_syllables,
        'swap_random_letter': apply_swap_random_letter,
        
        # Character removal
        'delete_letter': apply_delete_random_letter,
        'delete_random_letter': apply_delete_random_letter,
        'remove_random_vowel': apply_remove_random_vowel,
        'remove_random_consonant': apply_remove_random_consonant,
        'remove_all_spaces': apply_remove_all_spaces,
        
        # Character insertion/duplication
        'duplicate_letters': apply_duplicate_random_letter,
        'duplicate_random_letter': apply_duplicate_random_letter,
        'duplicate_random_letter_as_double_letter': apply_duplicate_random_letter,
        'insert_random_letter': apply_insert_random_letter,
        'add_title_prefix': apply_add_title_prefix,
        'add_random_leading_title': apply_add_title_prefix,
        'add_title_suffix': apply_add_title_suffix,
        'add_random_trailing_title': apply_add_title_suffix,
        'add_special_characters': _add_special_characters_legacy,
        
        # Name formatting
        'initial_only_first_name': apply_initial_only_first_name,
        'shorten_to_initials': apply_shorten_to_initials,
        'shorten_name_to_initials': apply_shorten_to_initials,
        'abbreviate_name_parts': apply_abbreviate_name_parts,
        'shorten_name_to_abbreviations': apply_abbreviate_name_parts,
        
        # Structure change
        'reorder_name_parts': apply_reorder_name_parts,
        'name_parts_permutations': apply_reorder_name_parts,
        'reverse_name': _reverse_name_legacy,
        
        # Case and formatting
        'capitalize_random_letters': _capitalize_random_letters_legacy,
        'change_case_pattern': _change_case_pattern_legacy,
        
        # Accents and diacritics
        'add_accents': _add_accents_legacy,
        'remove_accents': _remove_accents_legacy,
        
        # Hyphens
        'add_hyphens': _add_hyphens_legacy,
        'remove_hyphens': _remove_hyphens_legacy,
        
        # Phonetic
        'phonetic_substitution': _phonetic_substitution_legacy,
        'double_consonants': _double_consonants_legacy,
        'simplify_consonants': _simplify_consonants_legacy,
    }
    
    func = rule_map.get(rule)
    if func:
        try:
            result = func(name)
            return result if result else name
        except Exception as e:
            bt.logging.warning(f"Error applying rule {rule}: {e}")
            return name
    else:
        bt.logging.warning(f"Unknown rule: {rule}")
        return name


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
    print(variations[:count])
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

# ============================================================================
# COMPREHENSIVE RULE FUNCTIONS (Added from reference implementation)
# ============================================================================

def apply_replace_spaces_with_special_chars(name: str) -> str:
    """Replace spaces with special characters"""
    if ' ' not in name:
        return name
    special_chars = ['_', '-', '.']  # Removed '@' to avoid penalties
    return name.replace(' ', random.choice(special_chars))


def apply_delete_random_letter(name: str) -> str:
    """Delete a random letter"""
    if len(name) <= 1:
        return name
    idx = random.randint(0, len(name) - 1)
    return name[:idx] + name[idx+1:]


def apply_replace_double_letters(name: str) -> str:
    """Replace double letters with single letter"""
    name_lower = name.lower()
    for i in range(len(name_lower) - 1):
        if name_lower[i] == name_lower[i+1] and name[i].isalpha():
            return name[:i+1] + name[i+2:]
    return name


def apply_swap_adjacent_consonants(name: str) -> str:
    """Swap adjacent consonants"""
    vowels = "aeiou"
    name_lower = name.lower()
    for i in range(len(name_lower) - 1):
        if (name_lower[i].isalpha() and name_lower[i] not in vowels and
            name_lower[i+1].isalpha() and name_lower[i+1] not in vowels and
            name_lower[i] != name_lower[i+1]):
            return name[:i] + name[i+1] + name[i] + name[i+2:]
    return name


def apply_swap_adjacent_syllables(name: str) -> str:
    """Swap adjacent syllables (simplified: swap name parts)"""
    parts = name.split()
    if len(parts) >= 2:
        # Swap first and last name
        return " ".join([parts[-1]] + parts[1:-1] + [parts[0]])
    elif len(parts) == 1:
        # For single word, try to split in middle and swap
        word = parts[0]
        mid = len(word) // 2
        if mid > 0:
            return word[mid:] + word[:mid]
    return name


def apply_add_title_suffix(name: str) -> str:
    """Add a title suffix (Jr., PhD, etc.)"""
    suffixes = ['Jr.', 'Sr.', 'III', 'II']  # Removed PhD, MD to avoid penalties
    return name + " " + random.choice(suffixes)


def apply_abbreviate_name_parts(name: str) -> str:
    """Abbreviate name parts (e.g., "John" -> "J.")"""
    parts = name.split()
    if len(parts) >= 2:
        # Abbreviate first name
        parts[0] = parts[0][0] + "." if len(parts[0]) > 0 else parts[0]
    elif len(parts) == 1 and len(parts[0]) > 1:
        # If single word, abbreviate first letter
        parts[0] = parts[0][0] + "."
    return " ".join(parts)


def apply_replace_random_vowels(name: str) -> str:
    """Replace random vowels with different vowels"""
    vowels = {
        'a': ['e', 'i', 'o', 'u'], 'e': ['a', 'i', 'o', 'u'], 'i': ['a', 'e', 'o', 'u'],
        'o': ['a', 'e', 'i', 'u'], 'u': ['a', 'e', 'i', 'o'],
        'A': ['E', 'I', 'O', 'U'], 'E': ['A', 'I', 'O', 'U'], 'I': ['A', 'E', 'O', 'U'],
        'O': ['A', 'E', 'I', 'U'], 'U': ['A', 'E', 'I', 'O']
    }
    
    result = list(name)
    vowel_indices = [i for i, char in enumerate(name) if char.lower() in 'aeiou']
    
    if vowel_indices:
        # Replace 1-2 random vowels
        num_replacements = min(random.randint(1, 2), len(vowel_indices))
        indices_to_replace = random.sample(vowel_indices, num_replacements)
        
        for idx in indices_to_replace:
            char = name[idx]
            if char in vowels:
                result[idx] = random.choice(vowels[char])
    
    return ''.join(result)


def apply_remove_all_spaces(name: str) -> str:
    """Remove all spaces from name"""
    return name.replace(' ', '')


def apply_reorder_name_parts(name: str) -> str:
    """Reorder name parts (swap, reverse, etc.)"""
    parts = name.split()
    if len(parts) >= 2:
        # Different reordering strategies
        strategy = random.choice(['swap_first_last', 'reverse_all'])
        
        if strategy == 'swap_first_last':
            # Swap first and last
            return " ".join([parts[-1]] + parts[1:-1] + [parts[0]])
        elif strategy == 'reverse_all':
            # Reverse all parts
            return " ".join(reversed(parts))
    elif len(parts) == 1:
        # For single word, reverse it
        return parts[0][::-1]
    return name


def apply_replace_random_consonants(name: str) -> str:
    """Replace random consonants with different consonants"""
    consonants = {
        'b': ['c', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 'r', 's', 't', 'v', 'w', 'z'],
        'c': ['b', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 'r', 's', 't', 'v', 'w', 'z'],
        'd': ['b', 'c', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 'r', 's', 't', 'v', 'w', 'z'],
        'f': ['b', 'c', 'd', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 'r', 's', 't', 'v', 'w', 'z'],
        'g': ['b', 'c', 'd', 'f', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 'r', 's', 't', 'v', 'w', 'z'],
        'h': ['b', 'c', 'd', 'f', 'g', 'j', 'k', 'l', 'm', 'n', 'p', 'r', 's', 't', 'v', 'w', 'z'],
        'j': ['b', 'c', 'd', 'f', 'g', 'h', 'k', 'l', 'm', 'n', 'p', 'r', 's', 't', 'v', 'w', 'z'],
        'k': ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'l', 'm', 'n', 'p', 'r', 's', 't', 'v', 'w', 'z'],
        'l': ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'k', 'm', 'n', 'p', 'r', 's', 't', 'v', 'w', 'z'],
        'm': ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'n', 'p', 'r', 's', 't', 'v', 'w', 'z'],
        'n': ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'p', 'r', 's', 't', 'v', 'w', 'z'],
        'p': ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'r', 's', 't', 'v', 'w', 'z'],
        'r': ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 's', 't', 'v', 'w', 'z'],
        's': ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 'r', 't', 'v', 'w', 'z'],
        't': ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 'r', 's', 'v', 'w', 'z'],
        'v': ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 'r', 's', 't', 'w', 'z'],
        'w': ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 'r', 's', 't', 'v', 'z'],
        'z': ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 'r', 's', 't', 'v', 'w']
    }
    
    # Add uppercase versions
    for key in list(consonants.keys()):
        consonants[key.upper()] = [c.upper() for c in consonants[key]]
    
    result = list(name)
    consonant_indices = [i for i, char in enumerate(name) if char.isalpha() and char.lower() not in 'aeiou']
    
    if consonant_indices:
        # Replace 1-2 random consonants
        num_replacements = min(random.randint(1, 2), len(consonant_indices))
        indices_to_replace = random.sample(consonant_indices, num_replacements)
        
        for idx in indices_to_replace:
            char = name[idx]
            if char in consonants:
                result[idx] = random.choice(consonants[char])
    
    return ''.join(result)


def apply_swap_random_letter(name: str) -> str:
    """Swap random adjacent letters (not just consonants)"""
    if len(name) < 2:
        return name
    
    # Find all adjacent letter pairs
    swap_candidates = []
    for i in range(len(name) - 1):
        if name[i].isalpha() and name[i+1].isalpha() and name[i].lower() != name[i+1].lower():
            swap_candidates.append(i)
    
    if swap_candidates:
        idx = random.choice(swap_candidates)
        return name[:idx] + name[idx+1] + name[idx] + name[idx+2:]
    
    return name


def apply_remove_random_vowel(name: str) -> str:
    """Remove a random vowel"""
    vowels = 'aeiouAEIOU'
    vowel_indices = [i for i, char in enumerate(name) if char in vowels]
    
    if vowel_indices:
        idx = random.choice(vowel_indices)
        return name[:idx] + name[idx+1:]
    
    return name


def apply_remove_random_consonant(name: str) -> str:
    """Remove a random consonant"""
    consonant_indices = [i for i, char in enumerate(name) if char.isalpha() and char.lower() not in 'aeiou']
    
    if consonant_indices:
        idx = random.choice(consonant_indices)
        return name[:idx] + name[idx+1:]
    
    return name


def apply_duplicate_random_letter(name: str) -> str:
    """Duplicate a random letter"""
    if len(name) == 0:
        return name
    
    letter_indices = [i for i, char in enumerate(name) if char.isalpha()]
    
    if letter_indices:
        idx = random.choice(letter_indices)
        return name[:idx+1] + name[idx] + name[idx+1:]
    
    return name


def apply_insert_random_letter(name: str) -> str:
    """Insert a random letter"""
    if len(name) == 0:
        return random.choice('abcdefghijklmnopqrstuvwxyz')
    
    # Insert at random position
    idx = random.randint(0, len(name))
    random_letter = random.choice('abcdefghijklmnopqrstuvwxyz')
    
    # Preserve case context
    if idx > 0 and name[idx-1].isupper():
        random_letter = random_letter.upper()
    
    return name[:idx] + random_letter + name[idx:]


def apply_add_title_prefix(name: str) -> str:
    """Add a title prefix (Mr., Dr., etc.)"""
    prefixes = ['Mr.', 'Mrs.', 'Ms.', 'Dr.']  # Removed some to avoid penalties
    return random.choice(prefixes) + " " + name


def apply_initial_only_first_name(name: str) -> str:
    """Use first name initial with last name (e.g., 'John Doe' -> 'J. Doe')"""
    parts = name.split()
    if len(parts) >= 2:
        parts[0] = parts[0][0] + "." if len(parts[0]) > 0 else parts[0]
        return " ".join(parts)
    elif len(parts) == 1 and len(parts[0]) > 1:
        return parts[0][0] + "."
    return name


def apply_shorten_to_initials(name: str) -> str:
    """Convert name to initials (e.g., 'John Doe' -> 'J. D.')"""
    parts = name.split()
    if len(parts) >= 2:
        initials = [part[0] + "." for part in parts if len(part) > 0]
        return " ".join(initials)
    elif len(parts) == 1 and len(parts[0]) > 1:
        return parts[0][0] + "."
    return name


# ============================================================================
# LEGACY FUNCTION WRAPPERS (for backward compatibility)
# ============================================================================

def _add_special_characters_legacy(name: str) -> str:
    """Legacy wrapper for add_special_characters"""
    # Avoid special characters that cause penalties
    if len(name) > 1:
        idx = random.randint(1, len(name) - 1)
        return name[:idx] + "'" + name[idx:]  # Only use apostrophe
    return name


def _reverse_name_legacy(name: str) -> str:
    """Legacy wrapper for reverse_name"""
    return name[::-1]


def _capitalize_random_letters_legacy(name: str) -> str:
    """Legacy wrapper for capitalize_random_letters"""
    result = ''
    for char in name:
        if char.isalpha():
            result += char.upper() if random.random() > 0.5 else char.lower()
        else:
            result += char
    return result


def _change_case_pattern_legacy(name: str) -> str:
    """Legacy wrapper for change_case_pattern"""
    if len(name) > 1:
        return name.title()  # Simple title case
    return name


def _add_accents_legacy(name: str) -> str:
    """Legacy wrapper for add_accents"""
    accent_map = {
        'a': 'à', 'e': 'é', 'i': 'í', 'o': 'ó', 'u': 'ú',
        'A': 'À', 'E': 'É', 'I': 'Í', 'O': 'Ó', 'U': 'Ú'
    }
    
    result = list(name)
    for i, char in enumerate(name):
        if char in accent_map:
            result[i] = accent_map[char]
            break  # Only replace first occurrence
    
    return ''.join(result)


def _remove_accents_legacy(name: str) -> str:
    """Legacy wrapper for remove_accents"""
    if UNIDECODE_AVAILABLE:
        return unidecode(name)
    return name


def _add_hyphens_legacy(name: str) -> str:
    """Legacy wrapper for add_hyphens"""
    parts = name.split()
    if len(parts) >= 2:
        return '-'.join(parts)
    return name


def _remove_hyphens_legacy(name: str) -> str:
    """Legacy wrapper for remove_hyphens"""
    return name.replace('-', ' ')


def _phonetic_substitution_legacy(name: str) -> str:
    """Legacy wrapper for phonetic_substitution"""
    phonetic_rules = [
        ('ph', 'f'), ('f', 'ph'), ('c', 'k'), ('k', 'c'),
        ('s', 'z'), ('z', 's'), ('i', 'y'), ('y', 'i')
    ]
    
    for old, new in phonetic_rules:
        if old in name.lower():
            return name.replace(old, new)
    
    return name


def _double_consonants_legacy(name: str) -> str:
    """Legacy wrapper for double_consonants"""
    consonants = 'bcdfghjklmnpqrstvwxz'
    
    for i, char in enumerate(name):
        if char.lower() in consonants:
            return name[:i+1] + char + name[i+1:]
    
    return name


def _simplify_consonants_legacy(name: str) -> str:
    """Legacy wrapper for simplify_consonants"""
    for i in range(len(name) - 1):
        if name[i] == name[i + 1] and name[i].isalpha():
            return name[:i] + name[i+1:]
    
    return name