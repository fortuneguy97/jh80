import random
import re
from typing import List, Dict, Optional


# Import jellyfish for tiered similarity generation
try:
    import jellyfish
    JELLYFISH_AVAILABLE = True
except ImportError:
    JELLYFISH_AVAILABLE = False

# Import unidecode for transliteration
try:
    from unidecode import unidecode
    UNIDECODE_AVAILABLE = True
except ImportError:
    UNIDECODE_AVAILABLE = False
    print("⚠️  Warning: unidecode not available. Non-Latin scripts may not work well.")


from _name_variations import generate_name_variations

def generate_name_variations_clean(original_name: str, variation_count: int, 
                                   rule_percentage: float, rules,
                                   phonetic_similarity,
                                   orthographic_similarity) :
    """
    Generate name variations - rule-based and non-rule-based with tiered similarity targeting.
    
    Args:
        original_name: The original name to generate variations for
        variation_count: Total number of variations needed
        rule_percentage: Percentage of variations that should be rule-based
        rules: List of rule names to apply
        phonetic_similarity: Dict with Light/Medium/Far percentages (e.g., {'Light': 0.1, 'Medium': 0.3, 'Far': 0.6})
        orthographic_similarity: Dict with Light/Medium/Far percentages (e.g., {'Light': 0.7, 'Medium': 0.3})
    """
    # CRITICAL: Ensure exact rule percentage matching (validator checks this strictly)
    # Round to nearest integer for better accuracy
    rule_based_count = round(variation_count * rule_percentage)
    # Ensure we don't exceed total count
    rule_based_count = min(rule_based_count, variation_count)
    non_rule_count = variation_count - rule_based_count
    
    # Ensure non_rule_count is non-negative
    if non_rule_count < 0:
        non_rule_count = 0
        rule_based_count = variation_count
    
    variations = []
    used_variations = set()
    
    # Detect script type
    script = detect_script(original_name)
    is_non_latin = (script != 'latin')
    
    # Generate rule-based variations
    
    rule_attempts = {}
    for i in range(rule_based_count):
        if rules:
            rule = random.choice(rules)
            
            # Try applying the rule multiple times to get unique variations
            attempts = 0
            var = None
            while attempts < 20:  # Try up to 20 times to get a unique variation
                var = apply_rule_to_name(original_name, rule)
                
                # If we got a unique variation, use it
                if var.lower() not in used_variations and var != original_name:
                    break
                
                # If this rule always produces the same result, try a different rule
                if rule not in rule_attempts:
                    rule_attempts[rule] = 0
                rule_attempts[rule] += 1
                
                # If we've tried this rule too many times, pick a different one
                if rule_attempts[rule] > 5:
                    other_rules = [r for r in rules if r != rule]
                    if other_rules:
                        rule = random.choice(other_rules)
                        rule_attempts[rule] = 0
                    else:
                        # Only one rule available - break and try fallback strategies
                        break
                
                attempts += 1
            
            # Only add if we got a valid unique variation (NEVER add numeric suffixes)
            # CRITICAL: Check uniqueness using validator's combined_similarity threshold
            if var and var.lower() not in used_variations and var != original_name:
                # Check uniqueness against all existing variations (validator's threshold: > 0.99)
                is_unique = True
                for existing_var in variations:
                    phonetic_sim = calculate_phonetic_similarity_score(existing_var, var)
                    orthographic_sim = calculate_orthographic_similarity_score(existing_var, var)
                    combined_similarity = phonetic_sim * 0.7 + orthographic_sim * 0.3
                    
                    if combined_similarity > 0.99:  # Validator's uniqueness threshold
                        is_unique = False
                        break
                
                if is_unique:
                    variations.append(var)
                    used_variations.add(var.lower())
            elif var and var == original_name and attempts < 20:
                # If rule didn't change the name, try a different rule
                for alt_rule in rules:
                    if alt_rule != rule:
                        var = apply_rule_to_name(original_name, alt_rule)
                        if var.lower() not in used_variations and var != original_name:
                            # Check uniqueness
                            is_unique = True
                            for existing_var in variations:
                                phonetic_sim = calculate_phonetic_similarity_score(existing_var, var)
                                orthographic_sim = calculate_orthographic_similarity_score(existing_var, var)
                                combined_similarity = phonetic_sim * 0.7 + orthographic_sim * 0.3
                                
                                if combined_similarity > 0.99:
                                    is_unique = False
                                    break
                            
                            if is_unique:
                                variations.append(var)
                                used_variations.add(var.lower())
                                break
    
    # Generate non-rule variations using tiered similarity targeting
    print(f"        Rule-based: {rule_based_count} {variations[:5]}")
    
    if non_rule_count > 0:
        # For non-Latin scripts, skip tiered approach and go straight to script-specific variations
        if is_non_latin:
            print(f"        Detected {script} script - using script-specific variations")
            # Request 3x more variations to ensure we have enough unique ones
            non_latin_vars = generate_non_latin_variations(original_name, script, non_rule_count * 3)
            
            for var in non_latin_vars:
                if len(variations) >= variation_count:
                    break
                if var.lower() not in used_variations:
                    variations.append(var)
                    used_variations.add(var.lower())
        else:
            # For Latin scripts, use tiered similarity targeting with jellyfish
            if JELLYFISH_AVAILABLE and (phonetic_similarity or orthographic_similarity):
                # Use tiered generation to match target distribution
                non_rule_vars = generate_tiered_name_variations(
                    original_name,
                    non_rule_count,
                    phonetic_similarity,
                    orthographic_similarity
                )
            else:
                # Fallback: use simple name_variations.py if jellyfish not available
                non_rule_vars = generate_name_variations(original_name, limit=non_rule_count * 3)
            
            for var in non_rule_vars:
                if len(variations) >= variation_count:
                    break
                if var.lower() not in used_variations:
                    variations.append(var)
                    used_variations.add(var.lower())
    
    # Final fallback - only if we still don't have enough
    # NEVER use numeric suffixes - use character-level transformations instead
    if len(variations) < variation_count:
        remaining = variation_count - len(variations)
        if is_non_latin:
            # For non-Latin, ALWAYS use script-specific variations - NEVER numeric suffixes
            print(f"        Generating {remaining} more {script} script variations (no numeric suffixes)")
            
            # Generate many more variations to ensure we have enough
            non_latin_vars = generate_non_latin_variations(original_name, script, remaining * 5)
            
            for var in non_latin_vars:
                if len(variations) >= variation_count:
                    break
                if var.lower() not in used_variations:
                    variations.append(var)
                    used_variations.add(var.lower())
        
        # For BOTH Latin and non-Latin: create character-level variations manually
        # This ensures we never fall back to numeric suffixes
        if len(variations) < variation_count:
            remaining = variation_count - len(variations)
            parts = original_name.split()
            attempts = 0
            max_attempts = remaining * 10  # Try many times to get unique variations
            
            while len(variations) < variation_count and attempts < max_attempts:
                attempts += 1
                
                if len(parts) >= 2:
                    # Try different part orders and combinations
                    strategy = attempts % 6
                    if strategy == 0:
                        var = " ".join(parts[::-1])  # Reverse order
                    elif strategy == 1:
                        var = "".join(parts)  # Merge parts
                    elif strategy == 2:
                        var = parts[-1] + " " + " ".join(parts[:-1])  # Last name first
                    elif strategy == 3:
                        var = " ".join([parts[1]] + [parts[0]] + parts[2:]) if len(parts) > 2 else " ".join(parts[::-1])  # Swap first two
                    elif strategy == 4:
                        # Try applying character transformations to individual parts
                        modified_parts = list(parts)
                        part_idx = attempts % len(modified_parts)
                        word = modified_parts[part_idx]
                        if len(word) > 1:
                            # Try removing a character
                            char_idx = (attempts // len(modified_parts)) % (len(word) - 1) + 1
                            modified_parts[part_idx] = word[:char_idx] + word[char_idx+1:]
                            var = " ".join(modified_parts)
                        else:
                            var = None
                    else:
                        # Try merging with different separators
                        separators = ['', '-', '_', '.']
                        sep = separators[attempts % len(separators)]
                        var = sep.join(parts)
                elif len(parts) == 1 and len(parts[0]) > 1:
                    # For single word, try various character-level transformations
                    word = parts[0]
                    word_len = len(word)
                    strategy = attempts % 5
                    
                    if strategy == 0:
                        # Remove a character from different positions
                        idx = (attempts // 5) % (word_len - 1) + 1
                        var = word[:idx] + word[idx+1:]
                    elif strategy == 1:
                        # Swap adjacent characters
                        idx = (attempts // 5) % (word_len - 1)
                        chars = list(word)
                        chars[idx], chars[idx+1] = chars[idx+1], chars[idx]
                        var = ''.join(chars)
                    elif strategy == 2:
                        # Duplicate a character
                        idx = (attempts // 5) % word_len
                        var = word[:idx+1] + word[idx:]
                    elif strategy == 3:
                        # Capitalize different positions
                        var = word[:1].upper() + word[1:].lower() if word[0].islower() else word
                    else:
                        # Try vowel substitutions (common misspellings)
                        vowels = 'aeiou'
                        for i, char in enumerate(word.lower()):
                            if char in vowels:
                                # Replace with a different vowel
                                new_vowel = vowels[(vowels.index(char) + (attempts // 5) % len(vowels)) % len(vowels)]
                                var = word[:i] + new_vowel + word[i+1:]
                                break
                        else:
                            var = word
                else:
                    continue
                
                # Only add if valid and unique
                if var and var.lower() not in used_variations and var != original_name:
                    variations.append(var)
                    used_variations.add(var.lower())
    
    print(f"        Non-rule: {non_rule_count} {variations[:5]}")
    return variations[:variation_count]


def calculate_phonetic_similarity_score(original: str, variation: str) -> float:
    """
    Calculate phonetic similarity score using same logic as validator.
    Uses randomized subset of Soundex, Metaphone, NYSIIS.
    Returns: similarity score between 0.0 and 1.0
    """
    if not JELLYFISH_AVAILABLE:
        return 0.5  # Fallback medium similarity
    
    try:
        # Use same logic as validator - randomized subset of algorithms
        algorithms = {
            "soundex": lambda x, y: jellyfish.soundex(x) == jellyfish.soundex(y),
            "metaphone": lambda x, y: jellyfish.metaphone(x) == jellyfish.metaphone(y),
            "nysiis": lambda x, y: jellyfish.nysiis(x) == jellyfish.nysiis(y),
        }
        
        # Deterministically seed based on original name (same as validator)
        random.seed(hash(original) % 10000)
        selected_algorithms = random.sample(list(algorithms.keys()), k=min(3, len(algorithms)))
        
        # Generate random weights that sum to 1.0 (same as validator)
        weights = [random.random() for _ in selected_algorithms]
        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]
        
        # Calculate weighted phonetic score
        phonetic_score = sum(
            (1.0 if algorithms[algo](original, variation) else 0.0) * weight
            for algo, weight in zip(selected_algorithms, normalized_weights)
        )
        
        return float(phonetic_score)
    except Exception:
        return 0.5  # Fallback

def get_metaphone_match_score(original: str, candidate: str) -> str:
    """
    Determine phonetic similarity tier using actual similarity score calculation.
    Returns: 'Light', 'Medium', or 'Far'
    """
    score = calculate_phonetic_similarity_score(original, candidate)
    return get_phonetic_tier_from_score(score)

def get_phonetic_tier_from_score(score: float) -> str:
    """
    Categorize phonetic similarity score into Light/Medium/Far tier.
    Uses validator's exact boundaries: Light (0.80-1.00), Medium (0.60-0.79), Far (0.30-0.59)
    """
    if score >= 0.80:
        return 'Light'
    elif score >= 0.60:
        return 'Medium'
    elif score >= 0.30:
        return 'Far'
    else:
        return 'Far'  # Very low similarity

def get_orthographic_tier_from_score(score: float) -> str:
    """
    Categorize orthographic similarity score into Light/Medium/Far tier.
    Uses validator's exact boundaries: Light (0.70-1.00), Medium (0.50-0.69), Far (0.20-0.49)
    """
    if score >= 0.70:
        return 'Light'
    elif score >= 0.50:
        return 'Medium'
    elif score >= 0.20:
        return 'Far'
    else:
        return 'Far'  # Very low similarity

def get_levenshtein_tier(original: str, candidate: str) -> str:
    """
    Determine orthographic similarity tier using actual similarity score calculation.
    Returns: 'Light', 'Medium', or 'Far'
    """
    score = calculate_orthographic_similarity_score(original, candidate)
    return get_orthographic_tier_from_score(score)


def calculate_orthographic_similarity_score(original: str, variation: str) -> float:
    """
    Calculate orthographic similarity score using same logic as validator.
    Uses Levenshtein distance normalized to 0-1.
    Returns: similarity score between 0.0 and 1.0
    """
    if not JELLYFISH_AVAILABLE:
        return 0.5  # Fallback
    
    try:
        # Use same logic as validator - Levenshtein distance
        distance = jellyfish.levenshtein_distance(original.lower(), variation.lower())
        max_len = max(len(original), len(variation))
        
        if max_len == 0:
            return 1.0
        
        # Calculate similarity score (0-1), same as validator
        similarity = 1.0 - (distance / max_len)
        return float(similarity)
    except Exception:
        return 0.5  # Fallback
    
    
def generate_tiered_name_variations(
    original_name: str,
    non_rule_count: int,
    phonetic_similarity: Dict[str, float] = None,
    orthographic_similarity: Dict[str, float] = None
):
    """
    Generate name variations targeting specific Light/Medium/Far distributions.
    
    Uses jellyfish (Double Metaphone + Levenshtein) to categorize variations
    and select them to match the target distribution.
    """
    # Generate a large candidate pool using name_variations.py
    # Request 10x more candidates to ensure we have enough in each tier
    candidate_pool = generate_name_variations(original_name, limit=non_rule_count * 10)
    
    # Remove original name from pool
    candidate_pool = [c for c in candidate_pool if c.lower() != original_name.lower()]
    
    if not candidate_pool:
        # Fallback: generate simple variations
        return generate_name_variations(original_name, limit=non_rule_count)
    
    # If no similarity requirements specified, use default (all Medium)
    if not phonetic_similarity:
        phonetic_similarity = {'Medium': 1.0}
    if not orthographic_similarity:
        orthographic_similarity = {'Medium': 1.0}
    
    # Calculate required counts for each tier
    phonetic_counts = {}
    for tier in ['Light', 'Medium', 'Far']:
        phonetic_counts[tier] = int(non_rule_count * phonetic_similarity.get(tier, 0.0))
    
    orthographic_counts = {}
    for tier in ['Light', 'Medium', 'Far']:
        orthographic_counts[tier] = int(non_rule_count * orthographic_similarity.get(tier, 0.0))
    
    # Categorize candidates by both phonetic and orthographic similarity
    candidates_by_tiers = {
        'phonetic': {'Light': [], 'Medium': [], 'Far': []},
        'orthographic': {'Light': [], 'Medium': [], 'Far': []}
    }
    
    for candidate in candidate_pool:
        # Categorize by phonetic similarity
        phonetic_tier = get_metaphone_match_score(original_name, candidate)
        candidates_by_tiers['phonetic'][phonetic_tier].append(candidate)
        
        # Categorize by orthographic similarity
        orthographic_tier = get_levenshtein_tier(original_name, candidate)
        candidates_by_tiers['orthographic'][orthographic_tier].append(candidate)
    
    # CRITICAL: Filter candidates for uniqueness (validator checks combined_similarity > 0.99)
    # Pre-filter candidates to ensure they're not too similar to each other
    unique_candidates = []
    for candidate in candidate_pool:
        is_unique = True
        for unique_cand in unique_candidates:
            # Calculate combined similarity (same as validator: 0.7 phonetic + 0.3 orthographic)
            phonetic_sim = calculate_phonetic_similarity_score(unique_cand, candidate)
            orthographic_sim = calculate_orthographic_similarity_score(unique_cand, candidate)
            combined_similarity = phonetic_sim * 0.7 + orthographic_sim * 0.3
            
            if combined_similarity > 0.99:  # Validator's uniqueness threshold
                is_unique = False
                break
        
        if is_unique:
            unique_candidates.append(candidate)
    
    # Use unique candidates pool
    candidate_pool = unique_candidates
    if not candidate_pool:
        # If all candidates are too similar, generate more diverse ones
        candidate_pool = generate_name_variations(original_name, limit=non_rule_count * 20)
        candidate_pool = [c for c in candidate_pool if c.lower() != original_name.lower()]
    
    # Select variations to match target distribution
    # CRITICAL: Use actual similarity scores to categorize, not heuristics
    selected = []
    used = set()
    
    # Calculate actual similarity scores for all candidates and categorize
    candidates_with_scores = []
    for candidate in candidate_pool:
        if candidate.lower() in used or candidate.lower() == original_name.lower():
            continue
        
        phonetic_score = calculate_phonetic_similarity_score(original_name, candidate)
        orthographic_score = calculate_orthographic_similarity_score(original_name, candidate)
        phonetic_tier = get_phonetic_tier_from_score(phonetic_score)
        orthographic_tier = get_orthographic_tier_from_score(orthographic_score)
        
        candidates_with_scores.append({
            'candidate': candidate,
            'phonetic_score': phonetic_score,
            'orthographic_score': orthographic_score,
            'phonetic_tier': phonetic_tier,
            'orthographic_tier': orthographic_tier
        })
    
    # Shuffle for randomness
    random.shuffle(candidates_with_scores)
    
    # Strategy 1: Prioritize candidates that satisfy BOTH phonetic AND orthographic requirements
    # Sort candidates by how well they match both requirements
    for cand_data in candidates_with_scores:
        if len(selected) >= non_rule_count:
            break
        
        candidate = cand_data['candidate']
        phonetic_tier = cand_data['phonetic_tier']
        orthographic_tier = cand_data['orthographic_tier']
        phonetic_score = cand_data['phonetic_score']
        orthographic_score = cand_data['orthographic_score']
        
        # Count how many we've already selected in each tier
        phonetic_selected_count = sum(1 for v in selected 
                                     if get_phonetic_tier_from_score(
                                         calculate_phonetic_similarity_score(original_name, v)
                                     ) == phonetic_tier)
        orthographic_selected_count = sum(1 for v in selected 
                                         if get_orthographic_tier_from_score(
                                             calculate_orthographic_similarity_score(original_name, v)
                                         ) == orthographic_tier)
        
        # Check if this candidate helps us meet our targets
        phonetic_needed = phonetic_counts.get(phonetic_tier, 0) > phonetic_selected_count
        orthographic_needed = orthographic_counts.get(orthographic_tier, 0) > orthographic_selected_count
        
        # CRITICAL: Check uniqueness against already selected variations
        # Validator checks combined_similarity > 0.99 for uniqueness penalty
        is_unique = True
        for selected_var in selected:
            phonetic_sim = calculate_phonetic_similarity_score(selected_var, candidate)
            orthographic_sim = calculate_orthographic_similarity_score(selected_var, candidate)
            combined_similarity = phonetic_sim * 0.7 + orthographic_sim * 0.3
            
            if combined_similarity > 0.99:  # Validator's uniqueness threshold
                is_unique = False
                break
        
        # Priority: Select candidates that satisfy BOTH requirements first
        if is_unique:
            if phonetic_needed and orthographic_needed:
                # Perfect match - satisfies both requirements
                selected.append(candidate)
                used.add(candidate.lower())
            elif phonetic_needed or orthographic_needed:
                # Partial match - satisfies one requirement
                # Only add if we haven't met our targets yet
                selected.append(candidate)
                used.add(candidate.lower())
    
    # Strategy 2: Fill remaining slots prioritizing candidates that meet individual requirements
    if len(selected) < non_rule_count:
        remaining = non_rule_count - len(selected)
        for cand_data in candidates_with_scores:
            if len(selected) >= non_rule_count:
                break
            
            candidate = cand_data['candidate']
            if candidate.lower() in used:
                continue
            
            # Check uniqueness
            is_unique = True
            for selected_var in selected:
                phonetic_sim = calculate_phonetic_similarity_score(selected_var, candidate)
                orthographic_sim = calculate_orthographic_similarity_score(selected_var, candidate)
                combined_similarity = phonetic_sim * 0.7 + orthographic_sim * 0.3
                
                if combined_similarity > 0.99:
                    is_unique = False
                    break
            
            if is_unique:
                selected.append(candidate)
                used.add(candidate.lower())
    
    # Strategy 3: Generate more candidates if still needed
    if len(selected) < non_rule_count:
        remaining = non_rule_count - len(selected)
        # Generate many more candidates to ensure diversity
        extra_candidates = generate_name_variations(original_name, limit=remaining * 20)
        extra_candidates = [c for c in extra_candidates if c.lower() != original_name.lower() and c.lower() not in used]
        
        # Filter for uniqueness and categorize
        for candidate in extra_candidates:
            if len(selected) >= non_rule_count:
                break
            
            # Check uniqueness
            is_unique = True
            for selected_var in selected:
                phonetic_sim = calculate_phonetic_similarity_score(selected_var, candidate)
                orthographic_sim = calculate_orthographic_similarity_score(selected_var, candidate)
                combined_similarity = phonetic_sim * 0.7 + orthographic_sim * 0.3
                
                if combined_similarity > 0.99:
                    is_unique = False
                    break
            
            if is_unique:
                selected.append(candidate)
                used.add(candidate.lower())
                if len(selected) >= non_rule_count:
                    break
    
    # Debug: Log actual vs target distribution (optional, can be enabled for debugging)
    if len(selected) >= non_rule_count:
        # Calculate actual distribution for verification
        phonetic_dist = {'Light': 0, 'Medium': 0, 'Far': 0}
        orthographic_dist = {'Light': 0, 'Medium': 0, 'Far': 0}
        for var in selected:
            phonetic_tier = get_metaphone_match_score(original_name, var)
            orthographic_tier = get_levenshtein_tier(original_name, var)
            phonetic_dist[phonetic_tier] += 1
            orthographic_dist[orthographic_tier] += 1
        
        # Optional debug output (commented out for production)
        # print(f"   📊 Distribution - Phonetic: Light={phonetic_dist['Light']}/{phonetic_counts['Light']}, Medium={phonetic_dist['Medium']}/{phonetic_counts['Medium']}, Far={phonetic_dist['Far']}/{phonetic_counts['Far']}")
        # print(f"   📊 Distribution - Orthographic: Light={orthographic_dist['Light']}/{orthographic_counts['Light']}, Medium={orthographic_dist['Medium']}/{orthographic_counts['Medium']}, Far={orthographic_dist['Far']}/{orthographic_counts['Far']}")
    
    return selected[:non_rule_count]


def detect_script(name: str) -> str:
    """Detect the script type of a name"""
    # Check for Arabic characters
    if re.search(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]', name):
        return 'arabic'
    # Check for Cyrillic characters
    if re.search(r'[\u0400-\u04FF\u0500-\u052F\u2DE0-\u2DFF\uA640-\uA69F]', name):
        return 'cyrillic'
    # Check for Chinese/Japanese/Korean characters
    if re.search(r'[\u4E00-\u9FFF\u3040-\u309F\u30A0-\u30FF\uAC00-\uD7AF]', name):
        return 'cjk'
    # Check if contains non-Latin characters
    if re.search(r'[^\x00-\x7F]', name):
        return 'non-latin'
    return 'latin'

def generate_non_latin_variations(name: str, script: str, count: int):
    """Generate variations for non-Latin script names"""
    variations = []
    used = set([name.lower()])
    
    # Strategy 1: Script-specific transformations (keep original script) - PRIORITIZE THESE
    parts = name.split()
    
    # For Arabic/Cyrillic: Swap similar-looking characters, add/remove spaces
    if script in ['arabic', 'cyrillic']:
        # Swap adjacent parts
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
        
        # Add space in middle of long words
        for idx, part in enumerate(parts):
            if len(part) > 4:
                mid = len(part) // 2
                spaced = part[:mid] + " " + part[mid:]
                var = " ".join(parts[:idx] + [spaced] + parts[idx+1:])
                if var.lower() not in used:
                    variations.append(var)
                    used.add(var.lower())
                    break
        
        # Reverse parts order
        if len(parts) >= 2:
            reversed_parts = " ".join(parts[::-1])
            if reversed_parts.lower() not in used:
                variations.append(reversed_parts)
                used.add(reversed_parts.lower())
    
    # For CJK: Character-level variations
    if script == 'cjk':
        # Swap characters
        if len(parts) >= 2:
            swapped = " ".join([parts[-1]] + parts[:-1])
            if swapped.lower() not in used:
                variations.append(swapped)
                used.add(swapped.lower())
    
    # Strategy 2: Transliterate and generate variations (mix with script-specific)
    transliterated_vars = []
    if UNIDECODE_AVAILABLE and len(variations) < count:
        transliterated = unidecode(name)
        if transliterated and transliterated != name:
            # Generate variations on transliterated version (limit to avoid filling all slots)
            latin_vars = generate_name_variations(transliterated, limit=max(count - len(variations), count // 2))
            # Keep transliterated variations (valid for non-Latin names)
            for var in latin_vars:
                if var.lower() not in used:
                    transliterated_vars.append(var)
                    used.add(var.lower())
    
    # Mix script-specific and transliterated variations (prioritize script-specific)
    # Add script-specific first, then interleave with transliterated
    final_variations = variations[:]  # Copy script-specific variations
    translit_idx = 0
    while len(final_variations) < count and translit_idx < len(transliterated_vars):
        final_variations.append(transliterated_vars[translit_idx])
        translit_idx += 1
    variations = final_variations
    
    # Strategy 3: Character-level transformations (work for all scripts)
    # Generate variations by removing/duplicating/inserting characters
    max_char_variations = count
    attempts = 0
    while len(variations) < count and attempts < count * 3:
        attempts += 1
        
        # Remove a character
        if len(name) > 2:
            idx = random.randint(0, len(name) - 1)
            var = name[:idx] + name[idx+1:]
            if var and var.lower() not in used:
                variations.append(var)
                used.add(var.lower())
                if len(variations) >= count:
                    break
        
        # Duplicate a character
        if len(name) > 1:
            idx = random.randint(0, len(name) - 1)
            var = name[:idx+1] + name[idx] + name[idx+1:]
            if var.lower() not in used:
                variations.append(var)
                used.add(var.lower())
                if len(variations) >= count:
                    break
        
        # Swap adjacent characters (if not already done)
        if len(name) >= 2:
            idx = random.randint(0, len(name) - 2)
            var = name[:idx] + name[idx+1] + name[idx] + name[idx+2:]
            if var.lower() not in used:
                variations.append(var)
                used.add(var.lower())
                if len(variations) >= count:
                    break
    
    # Strategy 4: Add more transliterated variations if we still need more
    if UNIDECODE_AVAILABLE and len(variations) < count:
        transliterated = unidecode(name)
        if transliterated and transliterated != name:
            # Get more transliterated variations
            remaining = count - len(variations)
            more_latin_vars = generate_name_variations(transliterated, limit=remaining * 3)
            for var in more_latin_vars:
                if len(variations) >= count:
                    break
                if var.lower() not in used:
                    variations.append(var)
                    used.add(var.lower())
    
    # Strategy 5: If still not enough, create simple variations by modifying parts
    if len(variations) < count:
        remaining = count - len(variations)
        for i in range(remaining * 2):
            if len(variations) >= count:
                break
            parts = name.split()
            if len(parts) >= 2:
                # Try different part combinations
                if i % 3 == 0:
                    var = " ".join(parts[::-1])
                elif i % 3 == 1:
                    var = "".join(parts)
                else:
                    var = parts[-1] + " " + " ".join(parts[:-1])
            elif len(parts) == 1 and len(parts[0]) > 1:
                # For single word, try removing characters from different positions
                word = parts[0]
                idx = (i * 3) % (len(word) - 1) + 1
                var = word[:idx] + word[idx+1:]
            else:
                continue
            
            if var and var.lower() not in used:
                variations.append(var)
                used.add(var.lower())
    
    return variations[:count]

# =========================rlue===================================/

def apply_replace_spaces_with_special_chars(name: str) -> str:
    """Replace spaces with special characters"""
    if ' ' not in name:
        return name
    special_chars = ['_', '-', '@', '.']
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
    suffixes = ['Jr.', 'Sr.', 'PhD', 'MD', 'III', 'II', 'Esq.']
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
    vowels = {'a': ['e', 'i', 'o', 'u'], 'e': ['a', 'i', 'o', 'u'], 'i': ['a', 'e', 'o', 'u'],
              'o': ['a', 'e', 'i', 'u'], 'u': ['a', 'e', 'i', 'o'],
              'A': ['E', 'I', 'O', 'U'], 'E': ['A', 'I', 'O', 'U'], 'I': ['A', 'E', 'O', 'U'],
              'O': ['A', 'E', 'I', 'U'], 'U': ['A', 'E', 'I', 'O']}
    
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
        strategy = random.choice(['swap_first_last', 'reverse_all', 'random_shuffle'])
        
        if strategy == 'swap_first_last':
            # Swap first and last
            return " ".join([parts[-1]] + parts[1:-1] + [parts[0]])
        elif strategy == 'reverse_all':
            # Reverse all parts
            return " ".join(reversed(parts))
        else:  # random_shuffle
            # Shuffle all parts
            shuffled = parts.copy()
            random.shuffle(shuffled)
            return " ".join(shuffled)
    elif len(parts) == 1:
        # For single word, reverse it
        return parts[0][::-1]
    return name

def apply_replace_random_consonants(name: str) -> str:
    """Replace random consonants with different consonants"""
    consonants = {
        'b': ['c', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 'q', 'r', 's', 't', 'v', 'w', 'x', 'z'],
        'c': ['b', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 'q', 'r', 's', 't', 'v', 'w', 'x', 'z'],
        'd': ['b', 'c', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 'q', 'r', 's', 't', 'v', 'w', 'x', 'z'],
        'f': ['b', 'c', 'd', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 'q', 'r', 's', 't', 'v', 'w', 'x', 'z'],
        'g': ['b', 'c', 'd', 'f', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 'q', 'r', 's', 't', 'v', 'w', 'x', 'z'],
        'h': ['b', 'c', 'd', 'f', 'g', 'j', 'k', 'l', 'm', 'n', 'p', 'q', 'r', 's', 't', 'v', 'w', 'x', 'z'],
        'j': ['b', 'c', 'd', 'f', 'g', 'h', 'k', 'l', 'm', 'n', 'p', 'q', 'r', 's', 't', 'v', 'w', 'x', 'z'],
        'k': ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'l', 'm', 'n', 'p', 'q', 'r', 's', 't', 'v', 'w', 'x', 'z'],
        'l': ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'k', 'm', 'n', 'p', 'q', 'r', 's', 't', 'v', 'w', 'x', 'z'],
        'm': ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'n', 'p', 'q', 'r', 's', 't', 'v', 'w', 'x', 'z'],
        'n': ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'p', 'q', 'r', 's', 't', 'v', 'w', 'x', 'z'],
        'p': ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'q', 'r', 's', 't', 'v', 'w', 'x', 'z'],
        'q': ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 'r', 's', 't', 'v', 'w', 'x', 'z'],
        'r': ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 'q', 's', 't', 'v', 'w', 'x', 'z'],
        's': ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 'q', 'r', 't', 'v', 'w', 'x', 'z'],
        't': ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 'q', 'r', 's', 'v', 'w', 'x', 'z'],
        'v': ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 'q', 'r', 's', 't', 'w', 'x', 'z'],
        'w': ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 'q', 'r', 's', 't', 'v', 'x', 'z'],
        'x': ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 'q', 'r', 's', 't', 'v', 'w', 'z'],
        'z': ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 'q', 'r', 's', 't', 'v', 'w', 'x']
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
            if char.lower() in consonants:
                result[idx] = random.choice(consonants[char.lower() if char.islower() else char.upper()])
    
    return ''.join(result)

def apply_swap_random_letter(name: str) -> str:
    """Swap random adjacent letters (not just consonants)"""
    if len(name) < 2:
        return name
    
    # Find all adjacent letter pairs (case-insensitive, any letters)
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
    prefixes = ['Mr.', 'Mrs.', 'Ms.', 'Dr.', 'Prof.', 'Rev.', 'Sir', 'Lady']
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

def apply_rule_to_name(name: str, rule: str) -> str:
    """Apply a rule to a name"""
    rule_map = {
        # Character replacement
        'replace_spaces_with_special_characters': apply_replace_spaces_with_special_chars,
        'replace_double_letters': apply_replace_double_letters,
        'replace_random_vowels': apply_replace_random_vowels,
        'replace_random_consonants': apply_replace_random_consonants,
        
        # Character swapping
        'swap_adjacent_consonants': apply_swap_adjacent_consonants,
        'swap_adjacent_syllables': apply_swap_adjacent_syllables,
        'swap_random_letter': apply_swap_random_letter,
        
        # Character removal
        'delete_random_letter': apply_delete_random_letter,
        'remove_random_vowel': apply_remove_random_vowel,
        'remove_random_consonant': apply_remove_random_consonant,
        'remove_all_spaces': apply_remove_all_spaces,
        
        # Character insertion
        'duplicate_random_letter': apply_duplicate_random_letter,
        'insert_random_letter': apply_insert_random_letter,
        'add_title_prefix': apply_add_title_prefix,
        'add_title_suffix': apply_add_title_suffix,
        
        # Name formatting
        'initial_only_first_name': apply_initial_only_first_name,
        'shorten_to_initials': apply_shorten_to_initials,
        'abbreviate_name_parts': apply_abbreviate_name_parts,
        
        # Structure change
        'reorder_name_parts': apply_reorder_name_parts,
        
        # Aliases for validator rule names
        'replace_spaces_with_random_special_characters': apply_replace_spaces_with_special_chars,
        'replace_double_letters_with_single_letter': apply_replace_double_letters,
        'replace_random_vowel_with_random_vowel': apply_replace_random_vowels,
        'replace_random_consonant_with_random_consonant': apply_replace_random_consonants,
        'duplicate_random_letter_as_double_letter': apply_duplicate_random_letter,
        'add_random_leading_title': apply_add_title_prefix,
        'add_random_trailing_title': apply_add_title_suffix,
        'shorten_name_to_initials': apply_shorten_to_initials,
        'shorten_name_to_abbreviations': apply_abbreviate_name_parts,
        'name_parts_permutations': apply_reorder_name_parts,
    }
    func = rule_map.get(rule)
    return func(name) if func else name
# ======================================================
