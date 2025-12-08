#!/usr/bin/env python3
"""
New Gemini generator script - optimized for maximum scoring
Uses exact scoring mechanism from rewards.py
"""

import os
import json
import re
from typing import Dict, List, Any, Optional
import google.generativeai as genai
import time
import bittensor as bt


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
    
    # Extract rule percentage - look for "Approximately X% of the total"
    rule_pct_match = re.search(r'approximately\s+(\d+)%\s+of\s+the\s+total', query_template, re.I)
    if rule_pct_match:
        requirements['rule_percentage'] = int(rule_pct_match.group(1)) / 100
    else:
        # Fallback: look for any X% followed by "rule"
        rule_pct_match = re.search(r'(\d+)%\s+.*?rule', query_template, re.I)
        if rule_pct_match:
            requirements['rule_percentage'] = int(rule_pct_match.group(1)) / 100
    
    # Extract rules
    if 'convert' in query_template.lower() and 'initials' in query_template.lower():
        requirements['rules'].append('shorten_name_to_initials')
    if 'swap random adjacent letters' in query_template.lower():
        requirements['rules'].append('swap_random_letter')
    
    # Extract phonetic similarity - look for pattern like "phonetic similarity (20% Light, 60% Medium, 20% Far)"
    # Try full pattern first
    phonetic_pattern = re.search(r'phonetic.*?similarity.*?\([^)]*?(\d+)%\s+Light[^)]*?(\d+)%\s+Medium[^)]*?(\d+)%\s+Far', query_template, re.I)
    if phonetic_pattern:
        requirements['phonetic_similarity'] = {
            'Light': int(phonetic_pattern.group(1)) / 100,
            'Medium': int(phonetic_pattern.group(2)) / 100,
            'Far': int(phonetic_pattern.group(3)) / 100
        }
    else:
        # Fallback to individual matches - look for "X% Light", "X% Medium", "X% Far" after "phonetic"
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
    
    # Extract orthographic similarity - look for pattern like "orthographic similarity (30% Light, 40% Medium, 30% Far)"
    # Try full pattern first
    ortho_pattern = re.search(r'orthographic.*?similarity.*?\([^)]*?(\d+)%\s+Light[^)]*?(\d+)%\s+Medium[^)]*?(\d+)%\s+Far', query_template, re.I)
    if ortho_pattern:
        requirements['orthographic_similarity'] = {
            'Light': int(ortho_pattern.group(1)) / 100,
            'Medium': int(ortho_pattern.group(2)) / 100,
            'Far': int(ortho_pattern.group(3)) / 100
        }
    else:
        # Fallback to individual matches - look for "X% Light", "X% Medium", "X% Far" after "orthographic"
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


def build_optimized_prompt(name: str, dob: str, address: str, requirements: Dict[str, Any]) -> str:
    """
    Build optimized prompt for maximum scoring.
    
    Scoring breakdown from rewards.py:
    - Name Quality: 20% weight (similarity, count, uniqueness, length, rules)
    - DOB Score: 10% weight (must cover ±1, ±3, ±30, ±90, ±365 days, year+month)
    - Address Score: 70% weight (format, region, API validation)
    
    Final Score = (name_quality * 0.2) + (dob_score * 0.1) + (address_score * 0.7)
    """
    
    variation_count = requirements['variation_count']
    rule_percentage = requirements['rule_percentage']
    rules = requirements.get('rules', [])
    phonetic_sim = requirements.get('phonetic_similarity', {})
    ortho_sim = requirements.get('orthographic_similarity', {})
    
    import math
    rule_count = math.ceil(variation_count * rule_percentage)
    
    # Calculate similarity distribution counts
    phonetic_light_count = int(variation_count * phonetic_sim.get("Light", 0))
    phonetic_medium_count = int(variation_count * phonetic_sim.get("Medium", 0))
    phonetic_far_count = int(variation_count * phonetic_sim.get("Far", 0))
    
    ortho_light_count = int(variation_count * ortho_sim.get("Light", 0))
    ortho_medium_count = int(variation_count * ortho_sim.get("Medium", 0))
    ortho_far_count = int(variation_count * ortho_sim.get("Far", 0))
    
    prompt = f"""You are generating identity variations for security testing. Your output will be scored using this EXACT formula:

FINAL SCORE = (Name Quality × 0.20) + (DOB Score × 0.10) + (Address Score × 0.70)

================================================================================
ORIGINAL IDENTITY:
================================================================================
Name: {name}
DOB: {dob}
Address: {address}

================================================================================
SCORING BREAKDOWN (CRITICAL - READ CAREFULLY):
================================================================================

1. NAME QUALITY (20% of total score):
   - Similarity Distribution: 60% weight within name quality
     * Phonetic: {phonetic_light_count} Light (0.80-1.00), {phonetic_medium_count} Medium (0.60-0.79), {phonetic_far_count} Far (0.30-0.59)
     * Orthographic: {ortho_light_count} Light (0.70-1.00), {ortho_medium_count} Medium (0.50-0.69), {ortho_far_count} Far (0.20-0.49)
   - Count: 15% weight - Must have EXACTLY {variation_count} variations
   - Uniqueness: 10% weight - All variations must be unique (combined similarity < 0.99)
   - Length: 15% weight - Variations must be 60-140% of original length
   - Rule Compliance: 20% weight - EXACTLY {rule_count} variations must follow rules

2. DOB SCORE (10% of total score):
   - MUST include at least ONE variation in EACH of these 6 categories:
     * ±1 day from {dob}
     * ±3 days from {dob}
     * ±30 days from {dob}
     * ±90 days from {dob}
     * ±365 days from {dob}
     * Year+Month only (format: YYYY-MM, no day)
   - Missing any category = 0% for DOB component (loses 10% of total score!)

3. ADDRESS SCORE (70% of total score - MOST IMPORTANT!):
   - Format Validation: Address must be 30-300 chars, 20+ letters, 2+ commas, 1+ digit
   - Region Match: Country/city must match seed address "{address}"
   - API Validation: Address must be geocodable on OpenStreetMap
   - ANY failure = 0% for address component (loses 70% of total score!)

================================================================================
NAME VARIATION REQUIREMENTS:
================================================================================

Generate EXACTLY {variation_count} variations for "{name}":

RULE-COMPLIANT VARIATIONS (Variations 1-{rule_count}):
⚠️  CRITICAL: You MUST apply rules to EXACTLY {rule_count} out of {variation_count} variations!
⚠️  Missing rules = 0% for rule compliance = loses 20% of name quality score!
⚠️  THIS IS EASY - JUST APPLY THE RULES BELOW TO {rule_count} VARIATIONS!
"""
    
    num_rules = len(rules)
    if num_rules > 0:
        variations_per_rule = rule_count // num_rules
        extra = rule_count % num_rules
        
        # Add execution plan
        prompt += f"""
EXECUTION PLAN FOR RULES:
- Variations 1-{variations_per_rule}: Apply Rule 1 (initials)
- Variations {variations_per_rule+1}-{rule_count}: Apply Rule 2 (swap letters)
- Total rule-compliant: {rule_count} variations
"""
    
    if 'shorten_name_to_initials' in rules:
        name_parts = name.split()
        if len(name_parts) >= 2:
            count_for_this_rule = variations_per_rule + (1 if 'shorten_name_to_initials' == rules[0] and extra > 0 else 0)
            initials_example = '.'.join([p[0].upper() for p in name_parts]) + '.'
            initials_example2 = ' '.join([p[0].upper() + '.' for p in name_parts])
            initials_example3 = ''.join([p[0].upper() for p in name_parts])
            prompt += f"""
  Rule 1: Convert to initials (APPLY TO {count_for_this_rule} VARIATIONS)
    * You MUST convert {count_for_this_rule} variations to initials
    * CRITICAL: Validator checks for EXACT formats:
      * Format 1: "F.L." (lowercase with dots, no spaces) - Example: "{initials_example.lower()}"
      * Format 2: "F. L." (lowercase with dots and spaces) - Example: "{initials_example2.lower()}"
      * Format 3: "FL" (lowercase, no dots, no spaces) - Example: "{initials_example3.lower()}"
    * Examples for "{name}":
      * "{name}" → "{initials_example.lower()}" ✓ (validator recognizes this)
      * "{name}" → "{initials_example2.lower()}" ✓ (validator recognizes this)
      * "{name}" → "{initials_example3.lower()}" ✓ (validator recognizes this)
    * WRONG: "{name}" → "A. Vyborny" ✗ (last name still there - NOT recognized!)
    * WRONG: "{name}" → "A V" ✗ (uppercase - NOT recognized! Use lowercase)
    * CRITICAL: ALL name parts must be converted to first letter, use lowercase, use one of the 3 formats above
"""
    
    if 'swap_random_letter' in rules:
        name_parts = name.split()
        count_for_this_rule = variations_per_rule + (1 if 'swap_random_letter' in rules and (len(rules) == 1 or 'swap_random_letter' == rules[-1]) and extra > 0 else 0)
        
        # Generate clear swap examples
        examples = []
        if len(name_parts) >= 2:
            first = name_parts[0]
            last = name_parts[-1]
            
            # Swap in first name - generate precise swaps that pass validator
            if len(first) >= 4:
                # Swap positions 2,3 (avoid creating duplicates)
                swapped_first1 = first[:2] + first[3] + first[2] + first[4:]
                examples.append(swapped_first1 + " " + " ".join(name_parts[1:]))
            if len(first) >= 6:
                # Swap positions 4,5
                swapped_first2 = first[:4] + first[5] + first[4] + (first[6:] if len(first) > 6 else "")
                examples.append(swapped_first2 + " " + " ".join(name_parts[1:]))
            
            # Swap in last name - generate precise swaps that pass validator
            if len(last) >= 3:
                # Swap positions 1,2
                swapped_last1 = last[0] + last[2] + last[1] + (last[3:] if len(last) > 3 else "")
                examples.append(" ".join(name_parts[:-1]) + " " + swapped_last1)
            if len(last) >= 5:
                # Swap positions 4,5 (only if last name has at least 6 characters)
                if len(last) > 5:
                    swapped_last2 = last[:4] + last[5] + last[4] + (last[6:] if len(last) > 6 else "")
                    examples.append(" ".join(name_parts[:-1]) + " " + swapped_last2)
                elif len(last) == 5:
                    # For exactly 5 chars, swap positions 3,4
                    swapped_last2 = last[:3] + last[4] + last[3]
                    examples.append(" ".join(name_parts[:-1]) + " " + swapped_last2)
        else:
            if len(name) >= 2:
                examples.append(name[0] + name[2] + name[1] + name[3:] if len(name) > 2 else name[1] + name[0])
        
        example1 = examples[0] if examples else name
        example2 = examples[1] if len(examples) > 1 else examples[0] if examples else name
        
        prompt += f"""
  Rule 2: Swap adjacent letters (APPLY TO {count_for_this_rule} VARIATIONS)
    * You MUST swap adjacent letters in EXACTLY {count_for_this_rule} variations
    * CRITICAL: Validator is VERY STRICT - checks for EXACT swap:
      ✓ Length must match original EXACTLY ({len(name)} characters - no more, no less!)
      ✓ Exactly 2 positions must differ (count character differences - must be exactly 2)
      ✓ Those 2 positions must be adjacent (positions i and i+1, next to each other)
      ✓ Letters must be swapped: original[i] == variation[i+1] AND original[i+1] == variation[i]
    * CORRECT Examples for "{name}" (length: {len(name)}):
      * "{name}" → "{example1}" ✓ (length: {len(example1)}, matches: {len(example1) == len(name)})
      * "{name}" → "{example2}" ✓ (length: {len(example2)}, matches: {len(example2) == len(name)})
    * STEP-BY-STEP HOW TO CREATE VALID SWAP:
      Step 1: Original name: "{name}" (length: {len(name)})
      Step 2: Pick two adjacent letters (e.g., positions 2&3 in first name, or 1&2 in last name)
      Step 3: Swap ONLY those two letters
      Step 4: Keep ALL other letters in EXACT same positions
      Step 5: Verify length is EXACTLY {len(name)} (count characters - must match!)
    * WRONG Examples (DO NOT USE - Validator REJECTS):
      ✗ "{name}" → "Aantoly Vyborny" (extra 'a' - length {len(name)+1}, NOT {len(name)}) - REJECTED!
      ✗ "{name}" → "Anatoly Vybory" (missing 'n' - length {len(name)-1}, NOT {len(name)}) - REJECTED!
      ✗ "{name}" → "Anatoly Vybornyy" (extra 'y' - length {len(name)+1}, NOT {len(name)}) - REJECTED!
      ✗ "{name}" → "Anatoly Vybornee" (extra 'e' - length {len(name)+1}, NOT {len(name)}) - REJECTED!
    * CORRECT Examples (Validator ACCEPTS):
      ✓ "{name}" → "{example1}" (swapped 2 adjacent, length {len(example1)} = {len(name)}) - ACCEPTED!
      ✓ "{name}" → "{example2}" (swapped 2 adjacent, length {len(example2)} = {len(name)}) - ACCEPTED!
    * VALIDATOR ALGORITHM (exact check):
      - Counts character differences: must be exactly 2
      - Checks positions are adjacent: abs(pos1 - pos2) == 1
      - Checks letters are swapped: original[pos1] == variation[pos2] AND original[pos2] == variation[pos1]
      - Checks length: len(original) == len(variation) - MUST BE EXACT!
    * CRITICAL CHECKLIST BEFORE USING A SWAP:
      ✓ Count characters: variation length = {len(name)}? (must match exactly!)
      ✓ Count differences: exactly 2 positions differ?
      ✓ Check adjacency: are those positions next to each other?
      ✓ Check swap: are the letters actually swapped (not just changed)?
"""
    
    prompt += f"""
NON-RULE VARIATIONS (Variations {rule_count+1}-{variation_count}):
  - These {variation_count - rule_count} variations should NOT follow rules
  - Focus on matching similarity distributions EXACTLY
  - Ensure uniqueness (vary both first AND last name parts)
  - Keep length in 60-140% range (original length: {len(name)})
  - CRITICAL: These are scored for similarity, count, uniqueness, and length

SIMILARITY DISTRIBUTION (CRITICAL - 60% WEIGHT - BIGGEST COMPONENT!):
  ⚠️  CRITICAL: Similarity is 60% of name quality score! This is the BIGGEST component!
  ⚠️  You MUST generate variations that will MEASURE into these EXACT ranges!
  
  Required Distribution:
  - Phonetic: {phonetic_light_count} Light (0.80-1.00), {phonetic_medium_count} Medium (0.60-0.79), {phonetic_far_count} Far (0.30-0.59)
  - Orthographic: {ortho_light_count} Light (0.70-1.00), {ortho_medium_count} Medium (0.50-0.69), {ortho_far_count} Far (0.20-0.49)
  
  HOW VALIDATOR CALCULATES SIMILARITY:
  
  1. PHONETIC SIMILARITY (uses randomized subset of: Soundex, Metaphone, NYSIIS):
     - Light (0.80-1.00): Variations that encode to SAME phonetic code
       * Use: i↔y, ph↔f, c↔k, silent letters, same pronunciation
       * Example: "John" → "Jon" (same sound) ✓
       * Example: "Smith" → "Smyth" (same sound) ✓
     - Medium (0.60-0.79): Variations that encode to SIMILAR phonetic codes
       * Use: Vowel changes that sound similar (a↔e, o↔u)
       * Example: "John" → "Jahn" (similar sound) ✓
     - Far (0.30-0.59): Variations that encode to DIFFERENT phonetic codes
       * Use: Significant sound changes but still related
       * Example: "John" → "Jonny" (different but related) ✓
  
  2. ORTHOGRAPHIC SIMILARITY (uses Levenshtein distance):
     - Light (0.70-1.00): Levenshtein distance ≤ 30% of max length
       * For "{name}" (length {len(name)}): distance ≤ {int(len(name) * 0.30)} characters
       * Example: "John" → "Jhon" (1 char difference) ✓
       * Example: "Smith" → "Smthi" (1 char swap) ✓
     - Medium (0.50-0.69): Levenshtein distance 31-50% of max length
       * For "{name}" (length {len(name)}): distance {int(len(name) * 0.31)}-{int(len(name) * 0.50)} characters
       * Example: "John" → "Jonh" (2 char changes) ✓
     - Far (0.20-0.49): Levenshtein distance 51-80% of max length
       * For "{name}" (length {len(name)}): distance {int(len(name) * 0.51)}-{int(len(name) * 0.80)} characters
       * Example: "John" → "Jonny" (more changes) ✓
  
  STRATEGY TO MATCH DISTRIBUTION:
  1. Generate {phonetic_light_count} variations with HIGH phonetic similarity:
     - Use same-sounding letter substitutions (i↔y, ph↔f, c↔k)
     - Keep pronunciation identical
  2. Generate {phonetic_medium_count} variations with MEDIUM phonetic similarity:
     - Use similar-sounding vowel changes
     - Keep recognizable pronunciation
  3. Generate {phonetic_far_count} variations with LOW phonetic similarity:
     - Use abbreviations or significant changes
     - Still related but different sound
  
  CRITICAL: Test your variations mentally - will they score in the right ranges?

================================================================================
DOB VARIATION REQUIREMENTS (CRITICAL - 10% WEIGHT - EASY TO GET 1.0!):
================================================================================

Seed DOB: {dob}

⚠️  THIS IS EASY - JUST FOLLOW THE LIST BELOW EXACTLY! ⚠️

You MUST include EXACTLY ONE variation in EACH of these 6 categories:

1. ±1 day: ONE date within 1 day of {dob}
   Example: If {dob} = "1990-06-15", use "1990-06-14" or "1990-06-16"

2. ±3 days: ONE date within 3 days of {dob} (but NOT ±1 day)
   Example: If {dob} = "1990-06-15", use "1990-06-12" or "1990-06-18"

3. ±30 days: ONE date within 30 days of {dob} (but NOT ±1 or ±3 days)
   Example: If {dob} = "1990-06-15", use "1990-07-15" (exactly 30 days)

4. ±90 days: ONE date within 90 days of {dob} (but NOT ±1, ±3, or ±30 days)
   Example: If {dob} = "1990-06-15", use "1990-08-15" (60 days) or "1990-09-13" (90 days)
   ⚠️  CRITICAL: Must be ≤90 days (NOT 91+ days - that goes to ±365 category!)
   ⚠️  THIS IS OFTEN MISSED - MAKE SURE YOU HAVE ONE WITHIN 90 DAYS!

5. ±365 days: ONE date within 365 days of {dob}
   Example: If {dob} = "1990-06-15", use "1991-06-15" or "1989-06-15"

6. Year+Month only: ONE date with format "YYYY-MM" (NO DAY!)
   Example: If {dob} = "1990-06-15", use "1990-06" (NOT "1990-06-15")
   ⚠️  THIS IS OFTEN MISSED - FORMAT MUST BE "YYYY-MM" WITH NO DAY!

DOB CHECKLIST (VERIFY BEFORE RETURNING):
✓ Do you have a date within ±1 day? (e.g., 1990-06-14 or 1990-06-16)
✓ Do you have a date within ±3 days? (e.g., 1990-06-12 or 1990-06-18)
✓ Do you have a date within ±30 days? (e.g., 1990-07-15)
✓ Do you have a date within ±90 days? (e.g., 1990-09-15) ← CHECK THIS!
✓ Do you have a date within ±365 days? (e.g., 1991-06-15)
✓ Do you have a date with format "YYYY-MM"? (e.g., 1990-06) ← CHECK THIS!

Missing ANY category = 0% DOB score = loses 10% of total score!

================================================================================
ADDRESS VARIATION REQUIREMENTS (CRITICAL - 70% WEIGHT - MOST IMPORTANT!):
================================================================================

Seed Address: {address}

CRITICAL: Address score is 70% of total score! Get this right!

1. FORMAT (must pass or score = 0):
   - Length: 30-300 characters (after removing ALL non-word characters)
     * Example: "123 Main Street, New York, NY, USA" = 30+ chars after removing spaces/commas
     * Count: letters + digits only (no spaces, commas, punctuation)
   - Letters: At least 20 letters (Latin or non-Latin)
   - Digits: At least 1 digit in a comma-separated section
     * Example: "123 Main Street" has digit in first section ✓
     * Example: "Main Street, New York" has NO digits ✗ (FAILS!)
   - Commas: At least 2 commas (format: "Street, City, State, Country")
     * Example: "123 Main Street, New York, NY, USA" has 3 commas ✓
   - NO special chars: `, :, %, $, @, *, ^, [, ], {{, }}, _, «, »
   - Unique chars: At least 5 unique characters
   - Must contain letters (not just numbers)
   
   CRITICAL EXAMPLES:
   ✓ GOOD: "123 Main Street, New York, New York, USA" (has digit, 2+ commas, 20+ letters)
   ✓ GOOD: "456 Oak Avenue, Brooklyn, New York, United States" (has digit, 2+ commas, 20+ letters)
   ✗ BAD: "Main Street, New York, USA" (NO digits - FAILS!)
   ✗ BAD: "123 Main St, NY" (only 1 comma - FAILS!)

2. REGION MATCH (must pass or score = 0):
   - CRITICAL: Validator extracts city and country from your address and compares against seed
   - Seed address: "{address}"
   - Validator extracts: city from your address, country from your address
   - Validator compares: extracted_city == seed_address OR extracted_country == seed_address OR extracted_country == COUNTRY_MAPPING(seed_address)
   - IMPORTANT: Use the EXACT same country format as seed
     * If seed is "New York, USA" → use "USA" (not "United States")
     * If seed is "London, UK" → use "UK" (not "United Kingdom")
     * If seed is "Paris, France" → use "France"
   - Format: "Street, City, State/Province, Country" (use same country format as seed)
   - Country matching is CRITICAL - if country doesn't match, score = 0

3. API VALIDATION (must pass or score = 0):
   - Address MUST be geocodable on OpenStreetMap (Nominatim API)
   - Validator randomly selects up to 3 addresses for API validation
   - API checks: place_rank >= 20, name must be in address, numbers must match
   - Score based on bounding box area (smaller = better):
     * < 100 m² = 1.0 (FULL SCORE)
     * < 1,000 m² = 0.9
     * < 10,000 m² = 0.8
     * < 100,000 m² = 0.7
     * Otherwise = 0.0

GENERATE REAL ADDRESSES:
- Use real street names, real cities, real countries
- Format: "Street Number Street Name, Neighborhood/District, City, State/Province, Country"
- CRITICAL: Address must be AT LEAST 30 characters after removing spaces/commas
  * Example: "123 Main Street, New York, NY, USA" = 25 chars (TOO SHORT - FAILS!)
  * Example: "123 Main Street, Manhattan, New York, New York, USA" = 35+ chars (GOOD!)
  * Add neighborhood/district/borough to make addresses longer
  * Use full state names instead of abbreviations when possible
- Ensure addresses are geocodable (test mentally: can you find this on a map?)
- All addresses must be from the same country/city as seed: {address}
- MUST include street number (digit) in first section
- MUST have at least 2 commas (3+ sections)

================================================================================
OUTPUT FORMAT:
================================================================================

Return ONLY valid JSON in this EXACT format:
{{
  "variations": [
    ["name_variation_1", "dob_variation_1", "address_variation_1"],
    ["name_variation_2", "dob_variation_2", "address_variation_2"],
    ...
  ]
}}

CRITICAL REQUIREMENTS:
- EXACTLY {variation_count} variations
- Each variation: [name, dob, address]
- DOB must cover ALL 6 categories (at least one each)
- Addresses must be REAL and geocodable
- NO text before or after JSON
- NO markdown code blocks
- NO explanations

================================================================================
FINAL CHECKLIST (VERIFY BEFORE RETURNING):
================================================================================

DOB CHECKLIST (MUST HAVE ALL 6 - THIS IS EASY!):
✓ One date within ±1 day of {dob}?
✓ One date within ±3 days of {dob}?
✓ One date within ±30 days of {dob}?
✓ One date within ±90 days of {dob}? ← CHECK THIS!
✓ One date within ±365 days of {dob}?
✓ One date with format "YYYY-MM" (no day)? ← CHECK THIS!

NAME RULES CHECKLIST (MUST HAVE {rule_count} VARIATIONS - CRITICAL!):
✓ {variations_per_rule if num_rules > 0 else rule_count} variations converted to initials?
  * Check: Are they lowercase? Format: "f.l." or "f. l." or "fl"?
  * Check: Are ALL name parts converted to first letter?
✓ {variations_per_rule if num_rules > 0 else rule_count} variations with swapped letters?
  * Check: Does length match original EXACTLY ({len(name)} characters)?
  * Check: Are exactly 2 adjacent letters swapped?
  * Check: No extra letters, no missing letters, no spaces inserted?
✓ Total: {rule_count} variations following rules?
  * Count your rule-compliant variations - must be EXACTLY {rule_count}!

ADDRESS CHECKLIST:
✓ All addresses have 30+ characters (after removing spaces/commas)?
✓ All addresses have 2+ commas?
✓ All addresses have digits in first section?
✓ All addresses use same country format as "{address}"?
✓ All addresses are REAL and geocodable?

GENERAL:
✓ EXACTLY {variation_count} variations?
✓ All variations are unique?
✓ Similarity distributions match?

Generate the variations now. Remember: 
- DOB is EASY - just follow the 6 categories!
- Address score is 70% - get it right!
- Rules are EASY - just apply them to {rule_count} variations!"""
    
    return prompt


def generate_with_gemini(name: str, dob: str, address: str, query_template: str, 
                        api_key: str, model: str = "gemini-2.5-flash-lite") -> List[List[str]]:
    """Generate variations using Gemini API."""
    
    # Parse requirements
    requirements = parse_query_template(query_template)
    
    # Build prompt
    prompt = build_optimized_prompt(name, dob, address, requirements)
    
    # Configure Gemini
    genai.configure(api_key=api_key)
    model_instance = genai.GenerativeModel(model)
    
    # Generate
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
        
        # Try to find JSON object
        try:
            # First, try to find the JSON object with "variations" key
            json_start = text.find('{')
            json_end = text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = text[json_start:json_end]
                data = json.loads(json_str)
                variations = data.get('variations', [])
                
                if variations and len(variations) > 0:
                    return variations
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON array directly
        try:
            array_start = text.find('[')
            array_end = text.rfind(']') + 1
            
            if array_start >= 0 and array_end > array_start:
                json_str = text[array_start:array_end]
                variations = json.loads(json_str)
                
                if variations and len(variations) > 0:
                    return variations
        except json.JSONDecodeError:
            pass
        
        # Last resort: extract arrays manually using regex
        array_pattern = r'\["([^"]+)",\s*"([^"]+)",\s*"([^"]+)"\]'
        matches = re.findall(array_pattern, text)
        if matches:
            return [[m[0], m[1], m[2]] for m in matches]
        
        bt.logging.error(f"Failed to parse Gemini response. First 500 chars: {text[:500]}")
        return []
        
    except Exception as e:
        bt.logging.error(f"Error generating with Gemini: {e}")
        return []


if __name__ == "__main__":
    # Test with a single name
    name = "John Smith"
    dob = "1990-06-15"
    address = "New York, USA"
    query_template = """Generate exactly 8 variations of {name}, ensuring phonetic similarity (20% Light, 60% Medium, 20% Far) and orthographic similarity (30% Light, 40% Medium, 30% Far). Approximately 60% of the total 8 variations should follow these rule-based transformations: Convert {name} to initials, and Swap random adjacent letters."""
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not set")
    else:
        variations = generate_with_gemini(name, dob, address, query_template, api_key)
        print(f"Generated {len(variations)} variations:")
        for i, var in enumerate(variations, 1):
            print(f"{i}. {var}")

