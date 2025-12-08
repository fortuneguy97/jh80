#!/usr/bin/env python3
"""
Hybrid Gemini Generator - Manual Rule Application + Gemini for Non-Rule Variations
- Applies rules manually for perfect rule compliance
- Uses Gemini only for non-rule-based variations
"""

import os
import json
import re
import random
import math
from typing import Dict, List, Any, Optional, Tuple
import google.generativeai as genai
import bittensor as bt

# Import rule functions from validator
from MIID.validator.rule_extractor import RULE_DESCRIPTIONS, RULE_FUNCTIONS, get_rule_description
from MIID.validator.rule_evaluator import (
    is_letters_swapped, is_initials_only, is_first_name_initial,
    is_name_parts_permutation, is_letter_removed, is_vowel_removed,
    is_consonant_removed, is_all_spaces_removed, is_letter_duplicated,
    is_random_letter_inserted, is_title_added, is_suffix_added,
    is_vowel_replaced, is_consonant_replaced, is_double_letter_replaced,
    is_space_replaced_with_special_chars, is_adjacent_consonants_swapped
)
from MIID.validator.reward import (
    calculate_phonetic_similarity,
    calculate_orthographic_similarity
)
import Levenshtein


def parse_query_template(query_template: str) -> Dict[str, Any]:
    """Parse query template to extract requirements."""
    requirements = {
        'variation_count': 8,
        'rule_percentage': 0.0,
        'rules': [],
        'phonetic_similarity': {},
        'orthographic_similarity': {},
        'uav_seed_name': None
    }
    
    # Extract variation count
    count_match = re.search(r'Generate\s+(?:exactly\s+)?(\d+)\s+variations', query_template, re.I)
    if count_match:
        requirements['variation_count'] = int(count_match.group(1))
    
    # Extract rule percentage
    rule_pct_match = re.search(r'approximately\s+(\d+)%\s+of\s+the\s+total', query_template, re.I)
    if rule_pct_match:
        requirements['rule_percentage'] = int(rule_pct_match.group(1)) / 100
    else:
        rule_pct_match = re.search(r'(\d+)%\s+.*?rule', query_template, re.I)
        if rule_pct_match:
            requirements['rule_percentage'] = int(rule_pct_match.group(1)) / 100
    
    # Extract rules from query template by matching against RULE_DESCRIPTIONS
    query_lower = query_template.lower()
    found_rules = set()
    
    # Match each rule description against the query template
    for rule_name, description in RULE_DESCRIPTIONS.items():
        desc_lower = description.lower()
        # Extract keywords from description
        keywords = desc_lower.split()
        # Check if key terms from description appear in query
        # Use flexible matching - check for key words
        key_terms = [w for w in keywords if len(w) > 3]  # Skip short words like "a", "the"
        
        # Special handling for common patterns
        if 'initial' in desc_lower and 'name' in desc_lower:
            if ('initial' in query_lower and 'name' in query_lower) or ('convert' in query_lower and 'initial' in query_lower):
                found_rules.add(rule_name)
        elif 'swap' in desc_lower:
            if 'swap' in query_lower:
                if 'consonant' in desc_lower and 'consonant' in query_lower:
                    found_rules.add(rule_name)
                elif 'syllable' in desc_lower and 'syllable' in query_lower:
                    found_rules.add(rule_name)
                elif 'letter' in desc_lower and 'letter' in query_lower:
                    found_rules.add(rule_name)
        elif 'remove' in desc_lower or 'delete' in desc_lower:
            if ('remove' in query_lower or 'delete' in query_lower):
                if 'vowel' in desc_lower and 'vowel' in query_lower:
                    found_rules.add(rule_name)
                elif 'consonant' in desc_lower and 'consonant' in query_lower:
                    found_rules.add(rule_name)
                elif 'letter' in desc_lower and 'letter' in query_lower:
                    found_rules.add(rule_name)
                elif 'space' in desc_lower and 'space' in query_lower:
                    found_rules.add(rule_name)
        elif 'replace' in desc_lower:
            if 'replace' in query_lower:
                if 'space' in desc_lower and 'space' in query_lower:
                    found_rules.add(rule_name)
                elif 'vowel' in desc_lower and 'vowel' in query_lower:
                    found_rules.add(rule_name)
                elif 'consonant' in desc_lower and 'consonant' in query_lower:
                    found_rules.add(rule_name)
                elif 'double' in desc_lower and 'double' in query_lower:
                    found_rules.add(rule_name)
        elif 'duplicate' in desc_lower or 'insert' in desc_lower:
            if 'duplicate' in query_lower or 'insert' in query_lower:
                if 'letter' in desc_lower and 'letter' in query_lower:
                    found_rules.add(rule_name)
        elif 'title' in desc_lower:
            if 'title' in query_lower or 'prefix' in query_lower or 'suffix' in query_lower:
                if 'prefix' in desc_lower or 'leading' in desc_lower:
                    if 'prefix' in query_lower or 'leading' in query_lower:
                        found_rules.add(rule_name)
                elif 'suffix' in desc_lower or 'trailing' in desc_lower:
                    if 'suffix' in query_lower or 'trailing' in query_lower:
                        found_rules.add(rule_name)
        elif 'permutation' in desc_lower or 'reorder' in desc_lower:
            if 'permutation' in query_lower or 'reorder' in query_lower:
                found_rules.add(rule_name)
        elif 'abbrev' in desc_lower:
            if 'abbrev' in query_lower:
                found_rules.add(rule_name)
    
    requirements['rules'] = list(found_rules)
    
    # Extract phonetic similarity
    phonetic_pattern = re.search(r'phonetic.*?similarity.*?\([^)]*?(\d+)%\s+Light[^)]*?(\d+)%\s+Medium[^)]*?(\d+)%\s+Far', query_template, re.I)
    if phonetic_pattern:
        requirements['phonetic_similarity'] = {
            'Light': int(phonetic_pattern.group(1)) / 100,
            'Medium': int(phonetic_pattern.group(2)) / 100,
            'Far': int(phonetic_pattern.group(3)) / 100
        }
    else:
        phonetic_light = re.search(r'phonetic[^%]*?(\d+)%\s+Light', query_template, re.I)
        phonetic_medium = re.search(r'phonetic[^%]*?(\d+)%\s+Medium', query_template, re.I)
        phonetic_far = re.search(r'phonetic[^%]*?(\d+)%\s+Far', query_template, re.I)
        if phonetic_light or phonetic_medium or phonetic_far:
            requirements['phonetic_similarity'] = {}
            if phonetic_light:
                requirements['phonetic_similarity']['Light'] = int(phonetic_light.group(1)) / 100
            if phonetic_medium:
                requirements['phonetic_similarity']['Medium'] = int(phonetic_medium.group(1)) / 100
            if phonetic_far:
                requirements['phonetic_similarity']['Far'] = int(phonetic_far.group(1)) / 100
    
    # Extract orthographic similarity
    ortho_pattern = re.search(r'orthographic.*?similarity.*?\([^)]*?(\d+)%\s+Light[^)]*?(\d+)%\s+Medium[^)]*?(\d+)%\s+Far', query_template, re.I)
    if ortho_pattern:
        requirements['orthographic_similarity'] = {
            'Light': int(ortho_pattern.group(1)) / 100,
            'Medium': int(ortho_pattern.group(2)) / 100,
            'Far': int(ortho_pattern.group(3)) / 100
        }
    else:
        ortho_light = re.search(r'orthographic[^%]*?(\d+)%\s+Light', query_template, re.I)
        ortho_medium = re.search(r'orthographic[^%]*?(\d+)%\s+Medium', query_template, re.I)
        ortho_far = re.search(r'orthographic[^%]*?(\d+)%\s+Far', query_template, re.I)
        if ortho_light or ortho_medium or ortho_far:
            requirements['orthographic_similarity'] = {}
            if ortho_light:
                requirements['orthographic_similarity']['Light'] = int(ortho_light.group(1)) / 100
            if ortho_medium:
                requirements['orthographic_similarity']['Medium'] = int(ortho_medium.group(1)) / 100
            if ortho_far:
                requirements['orthographic_similarity']['Far'] = int(ortho_far.group(1)) / 100
    
    # Extract UAV seed name
    uav_match = re.search(r'For the seed "([^"]+)" ONLY', query_template, re.I)
    if uav_match:
        requirements['uav_seed_name'] = uav_match.group(1)
    
    return requirements


def apply_rule_shorten_name_to_initials(name: str) -> List[str]:
    """Apply shorten_name_to_initials rule - generate all valid formats."""
    name_parts = name.split()
    if len(name_parts) < 2:
        return []
    
    initials = []
    # Format 1: "f.l." (lowercase with dots, no spaces)
    initials.append('.'.join([p[0].lower() for p in name_parts]) + '.')
    # Format 2: "f. l." (lowercase with dots and spaces)
    initials.append(' '.join([p[0].lower() + '.' for p in name_parts]))
    # Format 3: "fl" (lowercase, no dots, no spaces)
    initials.append(''.join([p[0].lower() for p in name_parts]))
    
    return list(set(initials))  # Remove duplicates


def apply_rule_swap_random_letter(name: str, count: int = 1) -> List[str]:
    """Apply swap_random_letter rule - swap adjacent letters."""
    variations = []
    
    # Find all valid swap positions (adjacent letters that are different)
    # Check both within name parts and across spaces (but validator checks per part)
    swap_positions = []
    for i in range(len(name) - 1):
        if name[i] != name[i+1] and name[i].isalpha() and name[i+1].isalpha():
            # Don't swap across spaces
            if name[i] != ' ' and name[i+1] != ' ':
                swap_positions.append(i)
    
    if not swap_positions:
        return []
    
    # Generate variations by swapping at different positions
    # Try to swap in different name parts for diversity
    name_parts = name.split()
    used_positions = set()
    
    for i in range(min(count, len(swap_positions) * 2)):  # Allow more attempts
        # Try to find a position we haven't used yet
        pos = None
        for candidate_pos in swap_positions:
            if candidate_pos not in used_positions:
                pos = candidate_pos
                used_positions.add(pos)
                break
        
        # If all positions used, cycle through them
        if pos is None:
            pos = swap_positions[i % len(swap_positions)]
        
        swapped = list(name)
        swapped[pos], swapped[pos+1] = swapped[pos+1], swapped[pos]
        variation = ''.join(swapped)
        
        # Verify this swap would be recognized by validator
        # Validator checks: length matches, exactly 2 positions differ, adjacent, swapped
        if len(variation) == len(name):
            variations.append(variation)
            if len(variations) >= count:
                break
    
    return variations


def apply_rule_swap_adjacent_syllables(name: str, count: int = 1) -> List[str]:
    """Apply swap_adjacent_syllables rule - swap adjacent syllables (simplified: swap name parts)."""
    name_parts = name.split()
    if len(name_parts) < 2:
        return []
    
    variations = []
    # Swap first and last name parts
    if len(name_parts) >= 2:
        swapped = name_parts[-1] + ' ' + ' '.join(name_parts[:-1])
        variations.append(swapped)
    
    return variations[:count]


def apply_rule_remove_random_consonant(name: str, count: int = 1) -> List[str]:
    """Apply remove_random_consonant rule - remove a random consonant."""
    vowels = 'aeiou'
    consonants = [i for i, c in enumerate(name) if c.isalpha() and c.lower() not in vowels]
    
    if not consonants:
        return []
    
    variations = []
    for i in range(min(count, len(consonants))):
        pos = consonants[i % len(consonants)]
        removed = name[:pos] + name[pos+1:]
        variations.append(removed)
    
    return variations


def apply_rule_remove_random_vowel(name: str, count: int = 1) -> List[str]:
    """Apply remove_random_vowel rule - remove a random vowel."""
    vowels = 'aeiou'
    vowel_positions = [i for i, c in enumerate(name) if c.lower() in vowels]
    
    if not vowel_positions:
        return []
    
    variations = []
    for i in range(min(count, len(vowel_positions))):
        pos = vowel_positions[i % len(vowel_positions)]
        removed = name[:pos] + name[pos+1:]
        variations.append(removed)
    
    return variations


def apply_rule_delete_random_letter(name: str, count: int = 1) -> List[str]:
    """Apply delete_random_letter rule - delete a random letter."""
    letter_positions = [i for i, c in enumerate(name) if c.isalpha()]
    
    if not letter_positions:
        return []
    
    variations = []
    for i in range(min(count, len(letter_positions))):
        pos = letter_positions[i % len(letter_positions)]
        removed = name[:pos] + name[pos+1:]
        variations.append(removed)
    
    return variations


def apply_rule_remove_all_spaces(name: str, count: int = 1) -> List[str]:
    """Apply remove_all_spaces rule - remove all spaces."""
    if ' ' not in name:
        return []
    return [name.replace(' ', '')] * count


def apply_rule_replace_spaces_with_special_chars(name: str, count: int = 1) -> List[str]:
    """Apply replace_spaces_with_random_special_characters rule."""
    if ' ' not in name:
        return []
    
    special_chars = ['-', '_', '.', '#', '@']
    variations = []
    for i in range(count):
        char = special_chars[i % len(special_chars)]
        variations.append(name.replace(' ', char))
    
    return variations


def apply_rule_replace_double_letters(name: str, count: int = 1) -> List[str]:
    """Apply replace_double_letters_with_single_letter rule."""
    variations = []
    name_lower = name.lower()
    
    # Find double letters
    double_positions = []
    for i in range(len(name_lower) - 1):
        if name_lower[i] == name_lower[i+1] and name_lower[i].isalpha():
            double_positions.append(i)
    
    if not double_positions:
        return []
    
    for i in range(min(count, len(double_positions))):
        pos = double_positions[i % len(double_positions)]
        # Remove one of the double letters
        replaced = name[:pos] + name[pos+1:]
        variations.append(replaced)
    
    return variations


def apply_rule_replace_random_vowel(name: str, count: int = 1) -> List[str]:
    """Apply replace_random_vowel_with_random_vowel rule."""
    vowels = 'aeiou'
    vowel_positions = [i for i, c in enumerate(name) if c.lower() in vowels]
    
    if not vowel_positions:
        return []
    
    variations = []
    vowel_map = {'a': 'e', 'e': 'i', 'i': 'o', 'o': 'u', 'u': 'a'}
    
    for i in range(min(count, len(vowel_positions))):
        pos = vowel_positions[i % len(vowel_positions)]
        original_char = name[pos]
        new_vowel = vowel_map.get(original_char.lower(), 'a')
        # Preserve case
        if original_char.isupper():
            new_vowel = new_vowel.upper()
        replaced = name[:pos] + new_vowel + name[pos+1:]
        variations.append(replaced)
    
    return variations


def apply_rule_replace_random_consonant(name: str, count: int = 1) -> List[str]:
    """Apply replace_random_consonant_with_random_consonant rule."""
    vowels = 'aeiou'
    consonant_positions = [i for i, c in enumerate(name) if c.isalpha() and c.lower() not in vowels]
    
    if not consonant_positions:
        return []
    
    variations = []
    consonant_map = {'b': 'p', 'p': 'b', 'd': 't', 't': 'd', 'g': 'k', 'k': 'g', 'f': 'v', 'v': 'f'}
    
    for i in range(min(count, len(consonant_positions))):
        pos = consonant_positions[i % len(consonant_positions)]
        original_char = name[pos]
        new_consonant = consonant_map.get(original_char.lower(), 'b')
        # Preserve case
        if original_char.isupper():
            new_consonant = new_consonant.upper()
        replaced = name[:pos] + new_consonant + name[pos+1:]
        variations.append(replaced)
    
    return variations


def apply_rule_swap_adjacent_consonants(name: str, count: int = 1) -> List[str]:
    """Apply swap_adjacent_consonants rule."""
    vowels = 'aeiou'
    variations = []
    
    # Find adjacent consonants
    swap_positions = []
    for i in range(len(name) - 1):
        if (name[i].isalpha() and name[i].lower() not in vowels and
            name[i+1].isalpha() and name[i+1].lower() not in vowels and
            name[i].lower() != name[i+1].lower()):
            swap_positions.append(i)
    
    if not swap_positions:
        return []
    
    for i in range(min(count, len(swap_positions))):
        pos = swap_positions[i % len(swap_positions)]
        swapped = list(name)
        swapped[pos], swapped[pos+1] = swapped[pos+1], swapped[pos]
        variations.append(''.join(swapped))
    
    return variations


def apply_rule_duplicate_random_letter(name: str, count: int = 1) -> List[str]:
    """Apply duplicate_random_letter_as_double_letter rule."""
    letter_positions = [i for i, c in enumerate(name) if c.isalpha()]
    
    if not letter_positions:
        return []
    
    variations = []
    for i in range(min(count, len(letter_positions))):
        pos = letter_positions[i % len(letter_positions)]
        duplicated = name[:pos] + name[pos] + name[pos:]
        variations.append(duplicated)
    
    return variations


def apply_rule_insert_random_letter(name: str, count: int = 1) -> List[str]:
    """Apply insert_random_letter rule."""
    variations = []
    letters = 'abcdefghijklmnopqrstuvwxyz'
    
    for i in range(count):
        # Insert at random position
        pos = random.randint(0, len(name))
        random_letter = random.choice(letters)
        inserted = name[:pos] + random_letter + name[pos:]
        variations.append(inserted)
    
    return variations


def apply_rule_add_random_leading_title(name: str, count: int = 1) -> List[str]:
    """Apply add_random_leading_title rule."""
    titles = ['Mr.', 'Mrs.', 'Ms.', 'Dr.', 'Prof.']
    variations = []
    
    for i in range(count):
        title = titles[i % len(titles)]
        variations.append(f"{title} {name}")
    
    return variations


def apply_rule_add_random_trailing_title(name: str, count: int = 1) -> List[str]:
    """Apply add_random_trailing_title rule."""
    suffixes = ['Jr.', 'Sr.', 'III', 'PhD', 'MD']
    variations = []
    
    for i in range(count):
        suffix = suffixes[i % len(suffixes)]
        variations.append(f"{name} {suffix}")
    
    return variations


def apply_rule_initial_only_first_name(name: str, count: int = 1) -> List[str]:
    """Apply initial_only_first_name rule."""
    name_parts = name.split()
    if len(name_parts) < 2:
        return []
    
    variations = []
    # Format: "F. LastName" or "F LastName"
    first_initial = name_parts[0][0].lower() + '.'
    last_name = ' '.join(name_parts[1:])
    variations.append(f"{first_initial} {last_name}")
    
    # Alternative format without dot
    variations.append(f"{name_parts[0][0].lower()} {last_name}")
    
    return variations[:count]


def apply_rule_name_parts_permutations(name: str, count: int = 1) -> List[str]:
    """Apply name_parts_permutations rule."""
    name_parts = name.split()
    if len(name_parts) < 2:
        return []
    
    variations = []
    # Simple permutation: swap first and last
    if len(name_parts) >= 2:
        swapped = name_parts[-1] + ' ' + ' '.join(name_parts[:-1])
        variations.append(swapped)
    
    return variations[:count]


def apply_rule_shorten_name_to_abbreviations(name: str, count: int = 1) -> List[str]:
    """Apply shorten_name_to_abbreviations rule - abbreviate name parts."""
    name_parts = name.split()
    if len(name_parts) < 2:
        return []
    
    variations = []
    # Abbreviate by taking first 2-3 letters of each part
    for i in range(count):
        abbreviated_parts = []
        for part in name_parts:
            if len(part) > 3:
                # Take first 3 letters
                abbreviated_parts.append(part[:3].lower())
            else:
                # Take first 2 letters
                abbreviated_parts.append(part[:2].lower())
        variations.append(' '.join(abbreviated_parts))
    
    return variations


def apply_rules_manually(name: str, rules: List[str], rule_count: int) -> List[str]:
    """
    Apply rules manually to generate rule-compliant variations.
    
    Args:
        name: Original name
        rules: List of rule names to apply
        rule_count: Total number of rule-compliant variations needed
    
    Returns:
        List of rule-compliant name variations
    """
    all_variations = []
    
    if not rules or rule_count == 0:
        return []
    
    # Distribute rule_count across rules
    num_rules = len(rules)
    variations_per_rule = rule_count // num_rules
    extra = rule_count % num_rules
    
    # Map rule names to their application functions
    rule_functions = {
        'shorten_name_to_initials': apply_rule_shorten_name_to_initials,
        'swap_random_letter': apply_rule_swap_random_letter,
        'swap_adjacent_syllables': apply_rule_swap_adjacent_syllables,
        'swap_adjacent_consonants': apply_rule_swap_adjacent_consonants,
        'remove_random_consonant': apply_rule_remove_random_consonant,
        'remove_random_vowel': apply_rule_remove_random_vowel,
        'delete_random_letter': apply_rule_delete_random_letter,
        'remove_all_spaces': apply_rule_remove_all_spaces,
        'replace_spaces_with_random_special_characters': apply_rule_replace_spaces_with_special_chars,
        'replace_double_letters_with_single_letter': apply_rule_replace_double_letters,
        'replace_random_vowel_with_random_vowel': apply_rule_replace_random_vowel,
        'replace_random_consonant_with_random_consonant': apply_rule_replace_random_consonant,
        'duplicate_random_letter_as_double_letter': apply_rule_duplicate_random_letter,
        'insert_random_letter': apply_rule_insert_random_letter,
        'add_random_leading_title': apply_rule_add_random_leading_title,
        'add_random_trailing_title': apply_rule_add_random_trailing_title,
        'initial_only_first_name': apply_rule_initial_only_first_name,
        'name_parts_permutations': apply_rule_name_parts_permutations,
        'shorten_name_to_abbreviations': apply_rule_shorten_name_to_abbreviations,
    }
    
    for i, rule in enumerate(rules):
        count_for_this_rule = variations_per_rule + (1 if i < extra else 0)
        
        if rule in rule_functions:
            func = rule_functions[rule]
            if rule == 'shorten_name_to_initials':
                # This function returns a list, take first count_for_this_rule
                variations = func(name)
                all_variations.extend(variations[:count_for_this_rule])
            else:
                # Other functions take count parameter
                variations = func(name, count_for_this_rule)
                all_variations.extend(variations)
        else:
            bt.logging.warning(f"⚠️ Rule '{rule}' not implemented, skipping...")
    
    # If we have fewer variations than needed, pad with duplicates
    while len(all_variations) < rule_count:
        if all_variations:
            all_variations.append(all_variations[-1])
        else:
            break
    
    # Trim to exact count
    return all_variations[:rule_count]


def build_gemini_prompt_for_non_rule(
    name: str, dob: str, address: str, 
    requirements: Dict[str, Any],
    rule_compliant_variations: List[str]
) -> str:
    """Build prompt for Gemini to generate non-rule-based variations AND DOB/address for all."""
    
    variation_count = requirements['variation_count']
    rule_count = len(rule_compliant_variations)
    non_rule_count = variation_count - rule_count
    
    phonetic_sim = requirements.get('phonetic_similarity', {})
    ortho_sim = requirements.get('orthographic_similarity', {})
    
    # Calculate similarity distribution counts for non-rule variations
    phonetic_light_count = int(non_rule_count * phonetic_sim.get("Light", 0))
    phonetic_medium_count = int(non_rule_count * phonetic_sim.get("Medium", 0))
    phonetic_far_count = int(non_rule_count * phonetic_sim.get("Far", 0))
    
    ortho_light_count = int(non_rule_count * ortho_sim.get("Light", 0))
    ortho_medium_count = int(non_rule_count * ortho_sim.get("Medium", 0))
    ortho_far_count = int(non_rule_count * ortho_sim.get("Far", 0))
    
    prompt = f"""You are generating identity variations for security testing. Rules have already been applied manually, so you only need to generate NON-RULE variations.

================================================================================
ORIGINAL IDENTITY:
================================================================================
Name: {name}
DOB: {dob}
Address: {address}

================================================================================
IMPORTANT: RULES ALREADY APPLIED
================================================================================
The following {rule_count} rule-compliant variations have already been generated:
{chr(10).join(f"  - {v}" for v in rule_compliant_variations)}

You need to generate EXACTLY {non_rule_count} ADDITIONAL variations that:
- Do NOT follow any rules (these are already covered)
- Match the similarity distribution EXACTLY
- Are unique and different from the rule-compliant variations above

================================================================================
SIMILARITY DISTRIBUTION (CRITICAL - MUST MATCH EXACTLY - 60% WEIGHT!):
================================================================================

⚠️  CRITICAL: Similarity is 60% of name quality score! This is the BIGGEST component!
⚠️  The validator calculates similarity and checks if your variations fall into the correct ranges!
⚠️  If similarity < 0.2, validator applies 0.1x penalty multiplier (huge penalty!)

For the {non_rule_count} non-rule variations, you MUST match this EXACT distribution:

Phonetic Similarity (uses Soundex/Metaphone/NYSIIS - randomized subset):
- {phonetic_light_count} variations with Light similarity (0.80-1.00)
  * These must encode to SAME phonetic code
  * Use: i↔y, ph↔f, c↔k, silent letters, same pronunciation
  * Example: "John" → "Jon" (same sound) ✓
- {phonetic_medium_count} variations with Medium similarity (0.60-0.79)
  * These must encode to SIMILAR phonetic codes
  * Use: Vowel changes that sound similar (a↔e, o↔u)
  * Example: "John" → "Jahn" (similar sound) ✓
- {phonetic_far_count} variations with Far similarity (0.30-0.59)
  * These must encode to DIFFERENT phonetic codes
  * Use: Abbreviations or significant sound changes
  * Example: "John" → "Jonny" (different but related) ✓

Orthographic Similarity (uses Levenshtein distance: score = 1.0 - (distance / max_length)):
- {ortho_light_count} variations with Light similarity (0.70-1.00)
  * For "{name}" (length {len(name)}): Levenshtein distance ≤ {int(len(name) * 0.30)} characters
  * Example: "John" → "Jhon" (1 char difference, distance=1, score=0.75) ✓
  * Example: "Smith" → "Smthi" (1 char swap, distance=1, score=0.80) ✓
- {ortho_medium_count} variations with Medium similarity (0.50-0.69)
  * For "{name}" (length {len(name)}): Levenshtein distance {int(len(name) * 0.31)}-{int(len(name) * 0.50)} characters
  * Example: "John" → "Jonh" (2 char changes, distance=2, score=0.50) ✓
- {ortho_far_count} variations with Far similarity (0.20-0.49)
  * For "{name}" (length {len(name)}): Levenshtein distance {int(len(name) * 0.51)}-{int(len(name) * 0.80)} characters
  * Example: "John" → "Jonny" (more changes, distance=3, score=0.40) ✓

CRITICAL: The validator checks if your variations match this EXACT distribution. Missing the distribution = low score!

================================================================================
PERFECT BIRTHDATE GENERATION (CRITICAL - VALIDATOR REQUIRES ALL CATEGORIES):
================================================================================

The validator scores DOB variations based on category coverage. You MUST include AT LEAST ONE date in EACH category:

Original DOB: {dob}

⚠️  THIS IS EASY - JUST FOLLOW THE LIST BELOW EXACTLY! ⚠️

You MUST include EXACTLY ONE variation in EACH of these 6 categories:

1. ±1 day: ONE date within 1 day of {dob}
   Example: If {dob} = "1990-06-15", use "1990-06-14" or "1990-06-16"

2. ±3 days: ONE date within 3 days of {dob} (but NOT ±1 day)
   Example: If {dob} = "1990-06-15", use "1990-06-12" or "1990-06-18"

3. ±30 days: ONE date within 30 days of {dob} (but NOT ±1 or ±3 days)
   Example: If {dob} = "1990-06-15", use "1990-07-15" (exactly 30 days)

4. ±90 days: ONE date within 90 days of {dob} (but NOT ±1, ±3, or ±30 days)
   Example: If {dob} = "1990-06-15", use "1990-08-15" (61 days) or "1990-08-14" (60 days) or "1990-09-13" (90 days)
   ⚠️  CRITICAL: Must be EXACTLY 31-90 days (NOT 91+ days - that goes to ±365 category!)
   ⚠️  THIS IS OFTEN MISSED - MAKE SURE YOU HAVE ONE WITHIN 31-90 DAYS!
   ⚠️  WRONG: "1990-09-15" is 92 days = goes to ±365 category ❌
   ⚠️  CORRECT: "1990-08-15" is 61 days = ±90 category ✓

5. ±365 days: ONE date within 365 days of {dob}
   Example: If {dob} = "1990-06-15", use "1991-06-15" or "1989-06-15"

6. Year+Month only: ONE date with format "YYYY-MM" (NO DAY!)
   Example: If {dob} = "1990-06-15", use "1990-06" (NOT "1990-06-15")
   ⚠️  THIS IS OFTEN MISSED - FORMAT MUST BE "YYYY-MM" WITH NO DAY!

CRITICAL REQUIREMENTS:
- Format: YYYY-MM-DD for full dates, YYYY-MM for year+month only
- ALL dates must be VALID (no Feb 30, etc.)
- You MUST include at least ONE date in EACH of the 6 categories above
- Score = (categories_found / 6) - if you miss any category, score decreases
- For maximum score (1.0), you need ALL 6 categories
- Missing ANY category = 0% for DOB component (loses 10% of total score!)

DOB CHECKLIST (VERIFY BEFORE RETURNING):
✓ Do you have a date within ±1 day of {dob}? (e.g., 1990-06-14 or 1990-06-16)
✓ Do you have a date within ±3 days of {dob}? (e.g., 1990-06-12 or 1990-06-18)
✓ Do you have a date within ±30 days of {dob}? (e.g., 1990-07-15)
✓ Do you have a date within ±90 days of {dob}? (e.g., 1990-09-15) ← CHECK THIS!
✓ Do you have a date within ±365 days of {dob}? (e.g., 1991-06-15)
✓ Do you have a date with format "YYYY-MM"? (e.g., 1990-06) ← CHECK THIS!

Missing ANY category = 0% DOB score = loses 10% of total score!

================================================================================
ADDRESS VARIATION REQUIREMENTS:
================================================================================

Seed Address: {address}

CRITICAL: Address score is 70% of total score!

1. FORMAT (must pass or score = 0):
   - Length: 30-300 characters (after removing punctuation)
   - Letters: At least 20 letters
   - Digits: At least 1 digit in a comma-separated section
   - Commas: At least 2 commas
   - NO special chars: `, :, %, $, @, *, ^, [, ], {{, }}, _, «, »
   - Format: "Street Number Street Name, Neighborhood, City, State/Province, Country"

2. REGION MATCH (must pass or score = 0):
   - Use the EXACT same country format as seed "{address}"
   - If seed is "New York, USA" → use "USA" (not "United States")

3. API VALIDATION:
   - Address MUST be geocodable on OpenStreetMap
   - Use REAL, SPECIFIC street addresses with street numbers

================================================================================
OUTPUT FORMAT:
================================================================================

Return ONLY valid JSON in this EXACT format:
{{
  "non_rule_variations": [
    ["name_variation_1", "dob_variation_1", "address_variation_1"],
    ["name_variation_2", "dob_variation_2", "address_variation_2"],
    ...
  ],
  "rule_variations_dob_address": [
    ["dob_variation_1", "address_variation_1"],
    ["dob_variation_2", "address_variation_2"],
    ...
  ]
}}

CRITICAL REQUIREMENTS:
- EXACTLY {non_rule_count} non-rule name variations in "non_rule_variations"
- EXACTLY {rule_count} DOB/address pairs in "rule_variations_dob_address" (for the {rule_count} rule-compliant names)
- Each variation: [name, dob, address] for non-rule, [dob, address] for rule
- DOB must cover ALL 6 categories across ALL variations
- Addresses must be REAL and geocodable
- NO text before or after JSON
- NO markdown code blocks
- NO explanations

Generate the {non_rule_count} non-rule variations AND {rule_count} DOB/address pairs now."""
    
    return prompt


def generate_with_gemini_hybrid(
    name: str, dob: str, address: str, query_template: str,
    api_key: str, model: str = "gemini-2.5-flash-lite"
) -> List[List[str]]:
    """
    Generate variations using hybrid approach:
    1. Apply rules manually for perfect rule compliance
    2. Use Gemini for non-rule-based variations
    """
    
    # Parse requirements
    requirements = parse_query_template(query_template)
    variation_count = requirements['variation_count']
    rule_percentage = requirements['rule_percentage']
    rules = requirements.get('rules', [])
    
    # Calculate rule count
    rule_count = math.ceil(variation_count * rule_percentage)
    non_rule_count = variation_count - rule_count
    
    bt.logging.info(f"🔧 Hybrid Generation for '{name}':")
    bt.logging.info(f"   Total variations: {variation_count}")
    bt.logging.info(f"   Rule-compliant (manual): {rule_count}")
    bt.logging.info(f"   Non-rule (Gemini): {non_rule_count}")
    bt.logging.info(f"   Rules: {rules}")
    
    all_variations = []
    
    # Step 1: Apply rules manually
    if rule_count > 0 and rules:
        rule_variations = apply_rules_manually(name, rules, rule_count)
        bt.logging.info(f"   ✅ Generated {len(rule_variations)} rule-compliant variations manually")
        
        # Create full variations with DOB and address (use original for now, Gemini will generate proper ones)
        for rule_var in rule_variations:
            all_variations.append([rule_var, dob, address])
    else:
        rule_variations = []
    
    # Step 2: Use Gemini for non-rule variations
    if non_rule_count > 0:
        # Build prompt for non-rule variations only
        prompt = build_gemini_prompt_for_non_rule(
            name, dob, address, requirements, rule_variations
        )
        
        # Configure Gemini
        genai.configure(api_key=api_key)
        model_instance = genai.GenerativeModel(model)
        
        try:
            response = model_instance.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.7,
                    "max_output_tokens": 16384,
                }
            )
            
            text = response.text.strip()
            
            # Remove markdown code blocks if present
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0].strip()
            elif '```' in text:
                text = text.split('```')[1].split('```')[0].strip()
            
            # Parse JSON
            json_start = text.find('{')
            json_end = text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = text[json_start:json_end]
                data = json.loads(json_str)
                
                # Get non-rule variations
                gemini_variations = data.get('non_rule_variations', [])
                bt.logging.info(f"   ✅ Generated {len(gemini_variations)} non-rule variations with Gemini")
                all_variations.extend(gemini_variations)
                
                # Update rule-compliant variations with DOB and address from Gemini
                rule_dob_address = data.get('rule_variations_dob_address', [])
                if len(rule_dob_address) == len(rule_variations):
                    for i, rule_var in enumerate(rule_variations):
                        if i < len(rule_dob_address):
                            dob_addr = rule_dob_address[i]
                            if len(dob_addr) >= 2:
                                # Update the rule variation with proper DOB and address
                                all_variations[i] = [rule_var, dob_addr[0], dob_addr[1]]
                else:
                    bt.logging.warning(f"   ⚠️ Mismatch: {len(rule_dob_address)} DOB/address pairs for {len(rule_variations)} rule variations")
            else:
                bt.logging.warning(f"   ⚠️ Failed to parse Gemini response for non-rule variations")
        
        except Exception as e:
            bt.logging.error(f"   ❌ Error generating non-rule variations with Gemini: {e}")
    
    # Update DOB and addresses for rule-compliant variations using Gemini's output
    # For now, we'll use a simple approach: generate DOB/address variations for all
    
    # Ensure exact count
    if len(all_variations) < variation_count:
        if all_variations:
            last_var = all_variations[-1]
            while len(all_variations) < variation_count:
                all_variations.append(last_var.copy() if isinstance(last_var, list) else last_var)
    elif len(all_variations) > variation_count:
        all_variations = all_variations[:variation_count]
    
    return all_variations


if __name__ == "__main__":
    # Test
    name = "Maria Garcia"
    dob = "1985-03-20"
    address = "Los Angeles, USA"
    query_template = """Generate exactly 9 variations of {name}, ensuring phonetic similarity (10% Light, 30% Medium, 60% Far) and orthographic similarity (20% Light, 50% Medium, 30% Far). Approximately 30% of the total 9 variations should follow these rule-based transformations: Convert {name} to initials, and Swap random adjacent letters."""
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not set")
    else:
        variations = generate_with_gemini_hybrid(name, dob, address, query_template, api_key)
        print(f"\nGenerated {len(variations)} variations:")
        for i, var in enumerate(variations, 1):
            print(f"{i}. Name: {var[0]}, DOB: {var[1]}, Addr: {var[2][:50]}...")

