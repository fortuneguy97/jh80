#!/usr/bin/env python3
"""
Non-Rule-Based Name Variation Generator Module

This module generates name variations using Ollama AI for intelligent,
contextual variations that maintain phonetic and orthographic similarity.

The module includes:
- Ollama-powered intelligent name variations
- Phonetic similarity analysis
- Orthographic similarity analysis
- Script-specific transformations
- Fallback algorithmic variations
"""

import json
import random
import re
import requests
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


def generate_ollama_variations_with_dedup(name: str, count: int, phonetic_similarity: Dict[str, float], orthographic_similarity: Dict[str, float], existing_variations: set) -> List[str]:
    """
    Generate Ollama variations with deduplication against existing variations.
    
    Args:
        name: Original name
        count: Number of variations needed
        phonetic_similarity: Phonetic similarity requirements
        orthographic_similarity: Orthographic similarity requirements
        existing_variations: Set of already used variations (lowercase)
        
    Returns:
        List of unique variations not in existing_variations
    """
    bt.logging.debug(f"Generating Ollama variations with {len(existing_variations)} existing variations to avoid")
    
    # Generate extra variations to account for duplicates
    # Use count*3 instead of count*2 to have more options after deduplication
    generation_multiplier = 3
    
    try:
        # Create enhanced prompt that avoids existing variations
        prompt = _create_dedup_ollama_prompt(name, count, phonetic_similarity, orthographic_similarity, existing_variations)
        
        # Call Ollama API with higher generation count
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.1:latest",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.4,  # Slightly higher for more diversity
                    "top_p": 0.9,
                    "num_predict": 300   # More tokens for more variations
                }
            },
            timeout=45  # Longer timeout for more generation
        )
        
        if response.status_code == 200:
            ollama_output = response.json().get("response", "")
            bt.logging.debug(f"Ollama raw output: {ollama_output}")
            
            # Clean and validate with deduplication
            variations = _clean_ollama_variations_with_dedup(ollama_output, name, count, existing_variations)
            bt.logging.debug(f"Generated {len(variations)} unique Ollama variations")
            return variations
        else:
            bt.logging.warning(f"Ollama API error: {response.status_code}")
            return _fallback_variations_with_dedup(name, count, existing_variations)
            
    except Exception as e:
        bt.logging.warning(f"Ollama generation failed: {e}")
        return _fallback_variations_with_dedup(name, count, existing_variations)


def generate_ollama_variations(name: str, count: int, phonetic_similarity: Dict[str, float], orthographic_similarity: Dict[str, float]) -> List[str]:
    """
    Generate name variations using Ollama AI with proper cleaning for validator compliance.
    
    Args:
        name: Original name to generate variations for
        count: Number of variations to generate
        phonetic_similarity: Phonetic similarity requirements
        orthographic_similarity: Orthographic similarity requirements
        
    Returns:
        List of cleaned and validated name variations
    """
    bt.logging.debug(f"Generating {count} Ollama variations for: {name}")
    
    try:
        # Create prompt based on similarity requirements
        prompt = _create_ollama_prompt(name, count, phonetic_similarity, orthographic_similarity)
        
        # Call Ollama API
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.1:latest",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "num_predict": 200
                }
            },
            timeout=30
        )
        
        if response.status_code == 200:
            ollama_output = response.json().get("response", "")
            bt.logging.debug(f"Ollama raw output: {ollama_output}")
            
            # Clean and validate the variations
            variations = _clean_ollama_variations(ollama_output, name, count)
            bt.logging.debug(f"Generated {len(variations)} cleaned Ollama variations")
            return variations
        else:
            bt.logging.warning(f"Ollama API error: {response.status_code}")
            return _fallback_variations(name, count)
            
    except Exception as e:
        bt.logging.warning(f"Ollama generation failed: {e}")
        return _fallback_variations(name, count)


def _create_dedup_ollama_prompt(name: str, count: int, phonetic_similarity: Dict[str, float], orthographic_similarity: Dict[str, float], existing_variations: set) -> str:
    """Create a prompt for Ollama that avoids existing variations."""
    
    # Generate count*3 to have more options after deduplication
    generation_count = count * 3
    
    # Analyze similarity requirements
    phonetic_focus = sum(phonetic_similarity.values()) if phonetic_similarity else 0.5
    orthographic_focus = sum(orthographic_similarity.values()) if orthographic_similarity else 0.5
    
    # Create list of existing variations to avoid
    avoid_list = []
    for var in existing_variations:
        if var != name.lower():  # Don't include original name
            avoid_list.append(var.title())  # Convert to title case for display
    
    avoid_text = ""
    if avoid_list:
        avoid_text = f"\nDO NOT generate these variations (already exist):\n" + "\n".join(f"- {var}" for var in avoid_list[:10])  # Show max 10 to avoid prompt bloat
    
    prompt = f"""Generate {generation_count} UNIQUE realistic name variations for "{name}". 

CRITICAL REQUIREMENTS:
- Only return names, no explanations, numbering, or extra text
- Each variation on a new line
- Names should sound similar (phonetic similarity: {phonetic_focus:.1f})
- Names should look similar (visual similarity: {orthographic_focus:.1f})
- Keep the same name structure (single/multi-part names)
- Use ONLY letters, spaces, hyphens, and apostrophes
- NO numbers, addresses, dates, or special characters
- Length should be within 3 characters of original
- Make variations realistic and natural-sounding
- Focus on common spelling variations and phonetic alternatives
- AVOID DUPLICATES - each variation must be unique{avoid_text}

Examples of GOOD variations for "John Smith":
Jon Smith
John Smyth
Jhon Smith
John Smithe
Johan Smith
John Smit
Johnathan Smith
John Smythe

Examples of BAD variations (DO NOT generate):
John123
John Street
John 1990
J@hn Smith

Generate {generation_count} UNIQUE realistic variations for "{name}":\n"""
    
    return prompt


def _create_ollama_prompt(name: str, count: int, phonetic_similarity: Dict[str, float], orthographic_similarity: Dict[str, float]) -> str:
    """Create a prompt for Ollama to generate name variations."""
    
    # Generate count*2 to have more options for filtering
    generation_count = count * 2
    
    # Analyze similarity requirements
    phonetic_focus = sum(phonetic_similarity.values()) if phonetic_similarity else 0.5
    orthographic_focus = sum(orthographic_similarity.values()) if orthographic_similarity else 0.5
    
    prompt = f"""Generate {generation_count} realistic name variations for "{name}". 

CRITICAL REQUIREMENTS:
- Only return names, no explanations, numbering, or extra text
- Each variation on a new line
- Names should sound similar (phonetic similarity: {phonetic_focus:.1f})
- Names should look similar (visual similarity: {orthographic_focus:.1f})
- Keep the same name structure (single/multi-part names)
- Use ONLY letters, spaces, hyphens, and apostrophes
- NO numbers, addresses, dates, or special characters
- Length should be within 3 characters of original
- Make variations realistic and natural-sounding
- Focus on common spelling variations and phonetic alternatives

Examples of GOOD variations for "John Smith":
Jon Smith
John Smyth
Jhon Smith
John Smithe
Johan Smith
John Smit
Johnathan Smith
John Smythe

Examples of BAD variations (DO NOT generate):
John123
John Street
John 1990
J@hn Smith

Generate {generation_count} realistic variations for "{name}":\n"""
    
    return prompt


def _clean_ollama_variations_with_dedup(raw_output: str, original_name: str, target_count: int, existing_variations: set) -> List[str]:
    """Clean and validate Ollama output with deduplication against existing variations."""
    
    all_candidates = []
    used = existing_variations.copy()  # Start with existing variations
    
    bt.logging.debug(f"Processing Ollama output for {target_count} variations (avoiding {len(existing_variations)} existing)")
    
    # Split by lines and clean each variation
    lines = raw_output.strip().split('\n')
    
    # First pass: collect all valid candidates that don't duplicate
    for line in lines:
        # Basic cleaning
        cleaned = _clean_single_variation(line, original_name)
        
        if cleaned and cleaned.lower() not in used:
            # Validate using validator requirements
            if _validate_variation_quality(cleaned, original_name):
                # Additional deduplication check using similarity
                if not _is_too_similar_to_existing(cleaned, used):
                    all_candidates.append(cleaned)
                    used.add(cleaned.lower())
    
    # If we don't have enough candidates, try comma-separated format
    if len(all_candidates) < target_count:
        comma_parts = raw_output.replace('\n', ',').split(',')
        for part in comma_parts:
            if len(all_candidates) >= target_count * 2:  # Don't process too many
                break
                
            cleaned = _clean_single_variation(part, original_name)
            if cleaned and cleaned.lower() not in used:
                if _validate_variation_quality(cleaned, original_name):
                    if not _is_too_similar_to_existing(cleaned, used):
                        all_candidates.append(cleaned)
                        used.add(cleaned.lower())
    
    bt.logging.debug(f"Found {len(all_candidates)} unique candidates from Ollama")
    
    # Select the BEST variations for higher TAO rewards
    selected_variations = _select_best_variations(all_candidates, original_name, target_count)
    
    bt.logging.debug(f"Selected {len(selected_variations)} best unique variations")
    return selected_variations


def _clean_ollama_variations(raw_output: str, original_name: str, target_count: int) -> List[str]:
    """Clean and validate Ollama output, selecting best variations from count*2 generated."""
    
    all_candidates = []
    used = set([original_name.lower()])
    
    bt.logging.debug(f"Processing Ollama output for {target_count} variations (generated {target_count*2})")
    
    # Split by lines and clean each variation
    lines = raw_output.strip().split('\n')
    
    # First pass: collect all valid candidates
    for line in lines:
        # Basic cleaning
        cleaned = _clean_single_variation(line, original_name)
        
        if cleaned and cleaned.lower() not in used:
            # Validate using validator requirements
            if _validate_variation_quality(cleaned, original_name):
                all_candidates.append(cleaned)
                used.add(cleaned.lower())
    
    # If we don't have enough candidates, try comma-separated format
    if len(all_candidates) < target_count:
        comma_parts = raw_output.replace('\n', ',').split(',')
        for part in comma_parts:
            cleaned = _clean_single_variation(part, original_name)
            if cleaned and cleaned.lower() not in used:
                if _validate_variation_quality(cleaned, original_name):
                    all_candidates.append(cleaned)
                    used.add(cleaned.lower())
    
    bt.logging.debug(f"Found {len(all_candidates)} valid candidates from Ollama")
    
    # Second pass: select the BEST variations for higher TAO rewards
    selected_variations = _select_best_variations(all_candidates, original_name, target_count)
    
    bt.logging.debug(f"Selected {len(selected_variations)} best variations")
    return selected_variations


def _clean_single_variation(raw_variation: str, original_name: str) -> str:
    """Clean a single variation using the same logic as refer/miner.py Clean_extra."""
    
    if not raw_variation:
        return ""
    
    # Remove common prefixes from LLM responses
    prefixes = ["Variation:", "Alt:", "Alternative:", "-", "*", "•", "1.", "2.", "3.", "4.", "5.", 
                "6.", "7.", "8.", "9.", "10.", "11.", "12.", "13.", "14.", "15."]
    
    cleaned = raw_variation.strip()
    
    for prefix in prefixes:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
    
    # Remove numbering patterns
    cleaned = re.sub(r'^\d+[\.\)]\s*', '', cleaned)
    
    # Handle colons (e.g., "Here are variations: Name")
    if ":" in cleaned:
        cleaned = cleaned.split(":")[-1].strip()
    
    # Clean unwanted characters (based on Clean_extra function)
    cleaned = cleaned.replace('"', "")
    cleaned = cleaned.replace(".", "")
    cleaned = cleaned.replace("and ", "")
    
    # Remove multiple spaces
    while "  " in cleaned:
        cleaned = cleaned.replace("  ", " ")
    
    cleaned = cleaned.strip()
    
    # Only allow valid characters: letters, spaces, hyphens, apostrophes
    if not re.match(r"^[A-Za-zÀ-ÿ]+([ '\-][A-Za-zÀ-ÿ]+)*$", cleaned):
        return ""
    
    return cleaned


def _validate_variation_quality(variation: str, original_name: str) -> bool:
    """Validate variation using the same quality checks as refer/miner.py."""
    
    if not variation or variation.isspace():
        return False
    
    # Check if it's the same as original
    if variation.lower() == original_name.lower():
        return False
    
    # Check length reasonability (±3 characters max)
    if abs(len(variation) - len(original_name)) > 3:
        return False
    
    # Check for address patterns (CRITICAL)
    if _looks_like_address(variation):
        return False
    
    # Check for DOB patterns (CRITICAL)
    if _looks_like_dob(variation):
        return False
    
    # Check for problematic patterns (CRITICAL)
    if _contains_problematic_patterns(variation):
        return False
    
    # Check structure consistency
    name_parts = variation.split()
    original_parts = original_name.split()
    
    # Allow some flexibility in part count
    if abs(len(name_parts) - len(original_parts)) > 1:
        return False
    
    return True


def _looks_like_address(text: str) -> bool:
    """Check if text looks like an address (from refer/miner.py)."""
    if not text:
        return False
    
    text_lower = text.lower()
    
    # Check for ANY numbers
    if re.search(r'\d', text):
        return True
    
    # Address indicators
    address_indicators = [
        'street', 'st', 'avenue', 'ave', 'road', 'rd', 'drive', 'dr',
        'lane', 'ln', 'court', 'ct', 'place', 'pl', 'boulevard', 'blvd',
        'apt', 'apartment', 'suite', 'unit', 'floor', 'building',
        'north', 'south', 'east', 'west', 'n', 's', 'e', 'w',
        'p.o.', 'po', 'box', 'city', 'town', 'zip'
    ]
    
    for indicator in address_indicators:
        if re.search(r'\b' + re.escape(indicator) + r'\b', text_lower):
            return True
    
    return False


def _looks_like_dob(text: str) -> bool:
    """Check if text looks like a date of birth (from refer/miner.py)."""
    if not text:
        return False
    
    text_lower = text.lower()
    
    # Check for ANY numbers
    if re.search(r'\d', text):
        return True
    
    # Month names
    months = [
        'january', 'february', 'march', 'april', 'may', 'june',
        'july', 'august', 'september', 'october', 'november', 'december',
        'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'
    ]
    
    for month in months:
        if re.search(r'\b' + re.escape(month) + r'\b', text_lower):
            return True
    
    # Date-related words
    date_words = ['birth', 'birthday', 'born', 'date', 'dob', 'age', 'year', 'old']
    for word in date_words:
        if re.search(r'\b' + re.escape(word) + r'\b', text_lower):
            return True
    
    return False


def _contains_problematic_patterns(text: str) -> bool:
    """Check for problematic patterns (from refer/miner.py)."""
    if not text:
        return False
    
    text_lower = text.lower()
    
    # Generic words
    generic_words = [
        'unknown', 'none', 'null', 'n/a', 'na', 'test', 'example',
        'sample', 'temp', 'dummy', 'default', 'user', 'admin',
        'name', 'identity', 'person', 'individual', 'subject'
    ]
    if text_lower in generic_words:
        return True
    
    # Multiple consecutive spaces
    if '  ' in text or text != text.strip():
        return True
    
    # Starts or ends with special characters
    if text and (text[0] in "'-." or text[-1] in "'-."):
        return True
    
    # All uppercase or lowercase
    if len(text) > 2 and (text.isupper() or text.islower()):
        return True
    
    # Problematic characters
    problematic_chars = ['_', '#', '@', '$', '%', '^', '&', '*', 
                        '(', ')', '[', ']', '{', '}', '|', '\\',
                        '/', '<', '>', '?', '!', '~', '`', '+', '=']
    for char in problematic_chars:
        if char in text:
            return True
    
    return False


def _select_best_variations(candidates: List[str], original_name: str, target_count: int) -> List[str]:
    """
    Select the best variations from candidates to maximize TAO rewards.
    
    Scoring criteria:
    1. Length similarity (closer to original = higher score)
    2. Phonetic similarity (sounds similar = higher score)  
    3. Orthographic similarity (looks similar = higher score)
    4. Naturalness (common names/patterns = higher score)
    """
    if len(candidates) <= target_count:
        return candidates
    
    scored_variations = []
    
    for candidate in candidates:
        score = _calculate_variation_score(candidate, original_name)
        scored_variations.append((candidate, score))
    
    # Sort by score (highest first) and take top variations
    scored_variations.sort(key=lambda x: x[1], reverse=True)
    
    best_variations = [var for var, score in scored_variations[:target_count]]
    
    bt.logging.debug(f"Selected variations with scores:")
    for i, (var, score) in enumerate(scored_variations[:target_count]):
        bt.logging.debug(f"  {i+1}. {var} (score: {score:.3f})")
    
    return best_variations


def _calculate_variation_score(variation: str, original: str) -> float:
    """Calculate quality score for a variation to maximize TAO rewards."""
    
    score = 0.0
    
    # 1. Length similarity (25% weight) - closer length = higher score
    length_diff = abs(len(variation) - len(original))
    if length_diff == 0:
        length_score = 1.0
    elif length_diff == 1:
        length_score = 0.8
    elif length_diff == 2:
        length_score = 0.6
    elif length_diff == 3:
        length_score = 0.4
    else:
        length_score = 0.0
    
    score += length_score * 0.25
    
    # 2. Character similarity (25% weight) - similar characters = higher score
    char_similarity = _calculate_character_similarity(variation, original)
    score += char_similarity * 0.25
    
    # 3. Phonetic similarity (25% weight) - sounds similar = higher score
    phonetic_similarity = _calculate_phonetic_similarity(variation, original)
    score += phonetic_similarity * 0.25
    
    # 4. Naturalness (25% weight) - realistic names = higher score
    naturalness_score = _calculate_naturalness_score(variation, original)
    score += naturalness_score * 0.25
    
    return score


def _calculate_character_similarity(var1: str, var2: str) -> float:
    """Calculate character-level similarity between two strings."""
    if not var1 or not var2:
        return 0.0
    
    # Simple character overlap ratio
    set1 = set(var1.lower())
    set2 = set(var2.lower())
    
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    
    return intersection / union if union > 0 else 0.0


def _calculate_phonetic_similarity(var1: str, var2: str) -> float:
    """Calculate phonetic similarity between two names."""
    if not var1 or not var2:
        return 0.0
    
    # Simple phonetic similarity based on common transformations
    phonetic_pairs = [
        ('ph', 'f'), ('c', 'k'), ('s', 'z'), ('i', 'y'), 
        ('ck', 'k'), ('th', 't'), ('w', 'v'), ('j', 'g')
    ]
    
    var1_lower = var1.lower()
    var2_lower = var2.lower()
    
    # Check if they're phonetically similar
    for old, new in phonetic_pairs:
        if old in var1_lower and new in var2_lower:
            return 0.9
        if new in var1_lower and old in var2_lower:
            return 0.9
    
    # Check for common vowel substitutions
    vowel_subs = [('a', 'e'), ('i', 'y'), ('o', 'u')]
    for v1, v2 in vowel_subs:
        if v1 in var1_lower and v2 in var2_lower:
            return 0.8
        if v2 in var1_lower and v1 in var2_lower:
            return 0.8
    
    # Basic character similarity as fallback
    return _calculate_character_similarity(var1, var2)


def _calculate_naturalness_score(variation: str, original: str) -> float:
    """Calculate how natural/realistic a name variation looks."""
    
    score = 0.5  # Base score
    
    # Bonus for common name patterns
    if variation.istitle():  # Proper capitalization
        score += 0.2
    
    # Bonus for reasonable length
    if 2 <= len(variation) <= 20:
        score += 0.1
    
    # Bonus for common name endings
    common_endings = ['son', 'sen', 'ton', 'man', 'er', 'ly', 'th', 'te', 'ne']
    for ending in common_endings:
        if variation.lower().endswith(ending):
            score += 0.1
            break
    
    # Penalty for unusual character combinations
    unusual_patterns = ['qq', 'xx', 'zz', 'jj', 'kk']
    for pattern in unusual_patterns:
        if pattern in variation.lower():
            score -= 0.2
            break
    
    # Bonus for maintaining original structure
    orig_parts = len(original.split())
    var_parts = len(variation.split())
    if orig_parts == var_parts:
        score += 0.1
    
    return max(0.0, min(1.0, score))  # Clamp between 0 and 1


def _is_too_similar_to_existing(candidate: str, existing_variations: set) -> bool:
    """
    Check if candidate is too similar to existing variations.
    
    This prevents near-duplicates like "Jon" and "John" being both selected.
    """
    candidate_lower = candidate.lower()
    
    for existing in existing_variations:
        existing_lower = existing.lower()
        
        # Skip exact matches (already handled)
        if candidate_lower == existing_lower:
            continue
        
        # Check for very high similarity (potential duplicates)
        similarity = _calculate_character_similarity(candidate_lower, existing_lower)
        
        # If similarity is very high (>90%), consider it a duplicate
        if similarity > 0.9:
            bt.logging.debug(f"Rejecting '{candidate}' - too similar to existing '{existing}' (similarity: {similarity:.2f})")
            return True
        
        # Check for common near-duplicate patterns
        if _are_near_duplicates(candidate_lower, existing_lower):
            bt.logging.debug(f"Rejecting '{candidate}' - near duplicate of '{existing}'")
            return True
    
    return False


def _are_near_duplicates(name1: str, name2: str) -> bool:
    """Check for common near-duplicate patterns."""
    
    # Single character difference
    if abs(len(name1) - len(name2)) == 1:
        longer = name1 if len(name1) > len(name2) else name2
        shorter = name2 if len(name1) > len(name2) else name1
        
        # Check if shorter is substring of longer
        if shorter in longer:
            return True
    
    # Common substitutions that create near-duplicates
    substitutions = [
        ('john', 'jon'), ('michael', 'mike'), ('william', 'will'),
        ('robert', 'rob'), ('james', 'jim'), ('richard', 'rick'),
        ('smith', 'smyth'), ('johnson', 'jonson'), ('brown', 'browne')
    ]
    
    for sub1, sub2 in substitutions:
        if (sub1 in name1 and sub2 in name2) or (sub2 in name1 and sub1 in name2):
            return True
    
    return False


def _fallback_variations_with_dedup(name: str, count: int, existing_variations: set) -> List[str]:
    """Generate fallback variations with deduplication."""
    
    fallback_vars = []
    used = existing_variations.copy()
    
    # Generate more phonetic variations to account for duplicates
    phonetic_candidates = generate_phonetic_variations(name, count * 2)
    
    for var in phonetic_candidates:
        if len(fallback_vars) >= count:
            break
        
        if var.lower() not in used:
            if not _is_too_similar_to_existing(var, used):
                fallback_vars.append(var)
                used.add(var.lower())
    
    # If still not enough, generate simple character modifications
    while len(fallback_vars) < count:
        # Simple modifications that avoid duplicates
        base_name = name
        
        # Try different modifications
        modifications = [
            lambda x: x.replace('a', 'e') if 'a' in x else x + 'e',
            lambda x: x.replace('i', 'y') if 'i' in x else x.replace('e', 'i'),
            lambda x: x[:-1] if len(x) > 3 else x + 'n',
            lambda x: x + 'h' if not x.endswith('h') else x[:-1]
        ]
        
        for mod_func in modifications:
            if len(fallback_vars) >= count:
                break
            
            try:
                modified = mod_func(base_name)
                if (modified != name and 
                    modified.lower() not in used and 
                    _validate_variation_quality(modified, name) and
                    not _is_too_similar_to_existing(modified, used)):
                    
                    fallback_vars.append(modified)
                    used.add(modified.lower())
            except:
                continue
        
        # Prevent infinite loop
        if len(fallback_vars) == 0:
            break
    
    return fallback_vars


def _fallback_variations(name: str, count: int) -> List[str]:
    """Generate fallback variations when Ollama fails."""
    return generate_phonetic_variations(name, count)


def generate_phonetic_variations(name: str, count: int) -> List[str]:
    """Generate phonetic variations as fallback."""
    variations = []
    used = set([name.lower()])
    
    # Simple phonetic transformations
    phonetic_rules = [
        ('ph', 'f'), ('f', 'ph'), ('c', 'k'), ('k', 'c'),
        ('s', 'z'), ('z', 's'), ('i', 'y'), ('y', 'i')
    ]
    
    for old, new in phonetic_rules:
        if len(variations) >= count:
            break
        if old in name.lower():
            var = name.replace(old, new)
            if var.lower() not in used and _validate_variation_quality(var, name):
                variations.append(var)
                used.add(var.lower())
    
    return variations[:count]


def generate_orthographic_variations(name: str, count: int) -> List[str]:
    """
    Generate variations that look similar to the original name.
    
    Uses character-level modifications to create variations with
    controlled orthographic similarity.
    
    Args:
        name: Original name to generate variations for
        count: Number of orthographic variations to generate
        
    Returns:
        List of visually similar name variations
    """
    variations = []
    used = set([name.lower()])
    
    bt.logging.debug(f"Generating {count} orthographic variations for: {name}")
    
    # Similar looking characters mapping
    similar_chars = {
        'a': ['@', 'α', 'à', 'á', 'â', 'ã'],
        'e': ['3', 'ε', 'è', 'é', 'ê', 'ë'],
        'i': ['1', 'l', 'ì', 'í', 'î', 'ï'],
        'o': ['0', 'ο', 'ò', 'ó', 'ô', 'õ'],
        's': ['$', '5', 'ş', 'š'],
        't': ['+', '7', 'ţ', 'ť'],
        'l': ['1', 'I', 'ł'],
        'g': ['9', 'q', 'ğ'],
        'n': ['ñ', 'ň'],
        'c': ['ç', 'č'],
        'u': ['ù', 'ú', 'û', 'ü'],
        'z': ['ž', 'ź', 'ż']
    }
    
    attempts = 0
    max_attempts = count * 5
    
    while len(variations) < count and attempts < max_attempts:
        attempts += 1
        
        # Character substitution with similar-looking characters
        if len(name) > 1:
            idx = random.randint(0, len(name) - 1)
            char = name[idx].lower()
            
            if char in similar_chars:
                replacement = random.choice(similar_chars[char])
                var = name[:idx] + replacement + name[idx+1:]
                if var.lower() not in used and var != name:
                    variations.append(var)
                    used.add(var.lower())
        
        # Character insertion (add vowels or consonants)
        if len(variations) < count and len(name) > 1:
            idx = random.randint(0, len(name))
            # More likely to insert vowels for natural sound
            insert_chars = ['a', 'e', 'i', 'o', 'u', 'h', 'r', 'n']
            char = random.choice(insert_chars)
            var = name[:idx] + char + name[idx:]
            if var.lower() not in used and var != name:
                variations.append(var)
                used.add(var.lower())
        
        # Character deletion (remove non-essential characters)
        if len(variations) < count and len(name) > 2:
            idx = random.randint(0, len(name) - 1)
            var = name[:idx] + name[idx+1:]
            if var and var.lower() not in used and var != name:
                variations.append(var)
                used.add(var.lower())
        
        # Character transposition (swap adjacent characters)
        if len(variations) < count and len(name) >= 2:
            idx = random.randint(0, len(name) - 2)
            var = name[:idx] + name[idx+1] + name[idx] + name[idx+2:]
            if var.lower() not in used and var != name:
                variations.append(var)
                used.add(var.lower())
    
    bt.logging.debug(f"Generated {len(variations)} orthographic variations")
    return variations[:count]


def generate_script_specific_variations(name: str, script_type: str, count: int) -> List[str]:
    """
    Generate variations specific to the script type of the name.
    
    Args:
        name: Original name
        script_type: Type of script ('arabic', 'cyrillic', 'cjk', etc.)
        count: Number of variations to generate
        
    Returns:
        List of script-specific variations
    """
    variations = []
    used = set([name.lower()])
    parts = name.split()
    
    bt.logging.debug(f"Generating {count} {script_type} script variations for: {name}")
    
    if script_type in ['arabic', 'cyrillic']:
        # Name part reordering
        if len(parts) >= 2:
            # Swap first and last parts
            swapped = " ".join([parts[-1]] + parts[1:-1] + [parts[0]])
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
        
        # Add connecting characters
        if len(parts) >= 2:
            connectors = ['-', '_', '.']
            for connector in connectors:
                connected = connector.join(parts)
                if connected.lower() not in used:
                    variations.append(connected)
                    used.add(connected.lower())
                    if len(variations) >= count:
                        break
    
    elif script_type == 'cjk':
        # For CJK names, focus on character-level modifications
        if len(name) > 1:
            # Remove random characters
            for _ in range(min(3, count - len(variations))):
                if len(name) > 2:
                    idx = random.randint(0, len(name) - 1)
                    var = name[:idx] + name[idx+1:]
                    if var and var.lower() not in used:
                        variations.append(var)
                        used.add(var.lower())
        
        # Reorder characters for multi-character names
        if len(name) >= 2:
            chars = list(name)
            for _ in range(min(2, count - len(variations))):
                random.shuffle(chars)
                var = ''.join(chars)
                if var.lower() not in used and var != name:
                    variations.append(var)
                    used.add(var.lower())
    
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
    
    bt.logging.debug(f"Generated {len(variations)} script-specific variations")
    return variations[:count]


def generate_transliteration_variations(name: str, count: int) -> List[str]:
    """
    Generate variations using transliteration for non-Latin names.
    
    Args:
        name: Original name (non-Latin script)
        count: Number of transliteration variations to generate
        
    Returns:
        List of transliterated variations
    """
    variations = []
    
    if not UNIDECODE_AVAILABLE:
        bt.logging.warning("unidecode not available - cannot generate transliteration variations")
        return variations
    
    bt.logging.debug(f"Generating {count} transliteration variations for: {name}")
    
    # Basic transliteration
    transliterated = unidecode(name)
    if transliterated and transliterated != name:
        variations.append(transliterated)
        
        # Generate variations of the transliterated version
        if len(variations) < count:
            # Use phonetic and orthographic methods on transliterated name
            remaining = count - len(variations)
            
            # Half phonetic, half orthographic
            phonetic_count = remaining // 2
            ortho_count = remaining - phonetic_count
            
            phonetic_vars = generate_phonetic_variations(transliterated, phonetic_count)
            ortho_vars = generate_orthographic_variations(transliterated, ortho_count)
            
            variations.extend(phonetic_vars)
            variations.extend(ortho_vars)
    
    bt.logging.debug(f"Generated {len(variations)} transliteration variations")
    return variations[:count]


def generate_fallback_variations(name: str, existing_variations: List[str], target_count: int) -> List[str]:
    """
    Generate simple fallback variations when other methods don't produce enough.
    
    Args:
        name: Original name
        existing_variations: Already generated variations
        target_count: Total number of variations needed
        
    Returns:
        Additional variations to reach target count
    """
    variations = []
    used = set([var.lower() for var in existing_variations] + [name.lower()])
    needed = target_count - len(existing_variations)
    
    if needed <= 0:
        return variations
    
    bt.logging.debug(f"Generating {needed} fallback variations for: {name}")
    
    attempts = 0
    max_attempts = needed * 10
    
    while len(variations) < needed and attempts < max_attempts:
        attempts += 1
        
        # Choose a base name (original or existing variation)
        base_names = [name] + existing_variations[:3]
        base_name = random.choice(base_names)
        
        # Simple modifications
        modification = random.choice(['remove', 'add', 'duplicate', 'case'])
        
        if modification == 'remove' and len(base_name) > 2:
            idx = random.randint(0, len(base_name) - 1)
            var = base_name[:idx] + base_name[idx+1:]
            if var and var.lower() not in used:
                variations.append(var)
                used.add(var.lower())
        
        elif modification == 'add':
            idx = random.randint(0, len(base_name))
            char = random.choice('aeiou')
            var = base_name[:idx] + char + base_name[idx:]
            if var.lower() not in used:
                variations.append(var)
                used.add(var.lower())
        
        elif modification == 'duplicate' and len(base_name) > 1:
            idx = random.randint(0, len(base_name) - 1)
            var = base_name[:idx+1] + base_name[idx] + base_name[idx+1:]
            if var.lower() not in used:
                variations.append(var)
                used.add(var.lower())
        
        elif modification == 'case' and base_name.isalpha():
            # Random case changes
            var = ''.join(c.upper() if random.random() > 0.5 else c.lower() for c in base_name)
            if var != base_name and var.lower() not in used:
                variations.append(var)
                used.add(var.lower())
    
    bt.logging.debug(f"Generated {len(variations)} fallback variations")
    return variations[:needed]


def detect_script_type(name: str) -> str:
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


if __name__ == "__main__":
    # Test the non-rule-based generators
    test_names = ["John Smith", "رشيد البزال", "Müller", "田中太郎"]
    
    for name in test_names:
        print(f"\nTesting non-rule-based variations for: {name}")
        script_type = detect_script_type(name)
        print(f"Script type: {script_type}")
        
        # Test phonetic variations
        phonetic_vars = generate_phonetic_variations(name, 3)
        print(f"Phonetic: {phonetic_vars}")
        
        # Test orthographic variations
        ortho_vars = generate_orthographic_variations(name, 3)
        print(f"Orthographic: {ortho_vars}")
        
        # Test script-specific variations
        script_vars = generate_script_specific_variations(name, script_type, 3)
        print(f"Script-specific: {script_vars}")
        
        # Test transliteration if non-Latin
        if script_type != 'latin':
            trans_vars = generate_transliteration_variations(name, 2)
            print(f"Transliteration: {trans_vars}")