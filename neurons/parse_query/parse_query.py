#!/usr/bin/env python3
"""
Query Parser Module

This module parses the validator's query template to extract all requirements
for generating optimal variations. It analyzes the query to determine:
- Number of variations needed
- Phonetic similarity requirements
- Orthographic similarity requirements
- Rule-based transformation requirements
- UAV (Unknown Attack Vector) requirements

The parsed requirements are used by name, dob, and address generators
to create variations that maximize validator scoring.
"""

import re
import bittensor as bt
from typing import Dict, Any, List, Optional


def parse_query_template(query_template: str) -> Dict[str, Any]:
    """
    Parse the validator query template to extract all requirements.
    
    This function analyzes the query template and extracts:
    - Variation count (how many variations to generate)
    - Rule percentage (what percentage should follow specific rules)
    - Phonetic similarity distribution (Light/Medium/Far percentages)
    - Orthographic similarity distribution (Light/Medium/Far percentages)
    - Specific rules to apply
    - UAV seed name (if any)
    
    Args:
        query_template: The raw query template from validator
        
    Returns:
        Dictionary containing all parsed requirements:
        {
            'variation_count': int,
            'rule_percentage': float,
            'rules': List[str],
            'phonetic_similarity': Dict[str, float],
            'orthographic_similarity': Dict[str, float],
            'uav_seed_name': Optional[str],
            'original_query': str
        }
    """
    
    requirements = {
        'variation_count': 15,  # Default fallback
        'rule_percentage': 0.0,
        'rules': [],
        'phonetic_similarity': {},
        'orthographic_similarity': {},
        'uav_seed_name': None,
        'original_query': query_template
    }
    
    # Extract variation count - handle multiple formats
    variation_count = _extract_variation_count(query_template)
    if variation_count:
        requirements['variation_count'] = variation_count
    
    # Extract rule percentage
    rule_percentage = _extract_rule_percentage(query_template)
    if rule_percentage is not None:
        requirements['rule_percentage'] = rule_percentage
    
    # Extract specific rules
    rules = _extract_rules(query_template)
    if rules:
        requirements['rules'] = rules
    
    # Extract phonetic similarity distribution
    phonetic_sim = _extract_phonetic_similarity(query_template)
    if phonetic_sim:
        requirements['phonetic_similarity'] = phonetic_sim
    
    # Extract orthographic similarity distribution
    ortho_sim = _extract_orthographic_similarity(query_template)
    if ortho_sim:
        requirements['orthographic_similarity'] = ortho_sim
    
    # Extract UAV seed name
    uav_seed = _extract_uav_seed(query_template)
    if uav_seed:
        requirements['uav_seed_name'] = uav_seed
    
    return requirements


def _extract_variation_count(query_template: str) -> Optional[int]:
    """Extract the number of variations to generate."""
    count_patterns = [
        r'Generate\s+exactly\s+(\d+)\s+(?:name\s+)?variations',
        r'Generate\s+(\d+)\s+(?:name\s+)?variations',
        r'exactly\s+(\d+)\s+(?:name\s+)?variations',
        r'(\d+)\s+variations\s+of',
    ]
    
    for pattern in count_patterns:
        match = re.search(pattern, query_template, re.I)
        if match:
            return int(match.group(1))
    
    return None


def _extract_rule_percentage(query_template: str) -> Optional[float]:
    """Extract the percentage of variations that should follow rules."""
    rule_pct_patterns = [
        r'approximately\s+(\d+)%\s+of',
        r'also\s+include\s+(\d+)%\s+of',
        r'(\d+)%\s+of\s+the\s+total',
        r'(\d+)%\s+of\s+variations',
        r'include\s+(\d+)%',
        r'(\d+)%\s+should\s+follow'
    ]
    
    for pattern in rule_pct_patterns:
        match = re.search(pattern, query_template, re.I)
        if match:
            return int(match.group(1)) / 100
    
    return None


def _extract_rules(query_template: str) -> List[str]:
    """Extract specific transformation rules to apply."""
    rules = []
    query_lower = query_template.lower()
    
    # Map query text to rule identifiers
    rule_mappings = {
        'replace spaces with special characters': 'replace_spaces_with_special_characters',
        'replace vowels': 'replace_vowels',
        'add special characters': 'add_special_characters',
        'transliterate': 'transliterate',
        'remove a random consonant': 'remove_random_consonant',
        'remove random consonant': 'remove_random_consonant',
        'swap adjacent syllables': 'swap_adjacent_syllables',
        'swap adjacent consonants': 'swap_adjacent_consonants',
        'delete a random letter': 'delete_letter',
        'delete random letter': 'delete_letter',
        'convert': 'shorten_name_to_initials',  # "convert to initials"
        'swap random adjacent letters': 'swap_random_letter',
        'reorder name parts': 'reorder_name_parts'
    }
    
    for text_pattern, rule_id in rule_mappings.items():
        if text_pattern in query_lower:
            if rule_id not in rules:
                rules.append(rule_id)
    
    return rules


def _extract_phonetic_similarity(query_template: str) -> Dict[str, float]:
    """Extract phonetic similarity distribution requirements."""
    phonetic_sim = {}
    
    # Look for phonetic similarity patterns
    phonetic_light = re.search(r'phonetic.*?Light[:\s]+(\d+)%', query_template, re.I)
    phonetic_medium = re.search(r'phonetic.*?Medium[:\s]+(\d+)%', query_template, re.I)
    phonetic_far = re.search(r'phonetic.*?Far[:\s]+(\d+)%', query_template, re.I)
    
    if phonetic_light:
        phonetic_sim['Light'] = int(phonetic_light.group(1)) / 100
    if phonetic_medium:
        phonetic_sim['Medium'] = int(phonetic_medium.group(1)) / 100
    if phonetic_far:
        phonetic_sim['Far'] = int(phonetic_far.group(1)) / 100
    
    return phonetic_sim


def _extract_orthographic_similarity(query_template: str) -> Dict[str, float]:
    """Extract orthographic similarity distribution requirements."""
    ortho_sim = {}
    
    # Look for orthographic similarity patterns
    ortho_light = re.search(r'orthographic.*?Light[:\s]+(\d+)%', query_template, re.I)
    ortho_medium = re.search(r'orthographic.*?Medium[:\s]+(\d+)%', query_template, re.I)
    ortho_far = re.search(r'orthographic.*?Far[:\s]+(\d+)%', query_template, re.I)
    
    if ortho_light:
        ortho_sim['Light'] = int(ortho_light.group(1)) / 100
    if ortho_medium:
        ortho_sim['Medium'] = int(ortho_medium.group(1)) / 100
    if ortho_far:
        ortho_sim['Far'] = int(ortho_far.group(1)) / 100
    
    return ortho_sim


def _extract_uav_seed(query_template: str) -> Optional[str]:
    """Extract UAV (Unknown Attack Vector) seed name if specified."""
    uav_match = re.search(r'For the seed "([^"]+)" ONLY', query_template, re.I)
    if uav_match:
        return uav_match.group(1)
    
    return None


def get_similarity_counts(variation_count: int, similarity_dist: Dict[str, float]) -> Dict[str, int]:
    """
    Calculate exact counts for similarity distribution.
    
    Args:
        variation_count: Total number of variations to generate
        similarity_dist: Dictionary with Light/Medium/Far percentages
        
    Returns:
        Dictionary with Light/Medium/Far counts
    """
    counts = {}
    
    # Calculate base counts
    light_count = int(variation_count * similarity_dist.get("Light", 0))
    medium_count = int(variation_count * similarity_dist.get("Medium", 0))
    far_count = int(variation_count * similarity_dist.get("Far", 0))
    
    # Adjust for rounding to ensure total matches variation_count
    total_calculated = light_count + medium_count + far_count
    if total_calculated < variation_count:
        # Add remaining to largest category
        if medium_count >= light_count and medium_count >= far_count:
            medium_count += (variation_count - total_calculated)
        elif light_count >= far_count:
            light_count += (variation_count - total_calculated)
        else:
            far_count += (variation_count - total_calculated)
    
    counts['Light'] = light_count
    counts['Medium'] = medium_count
    counts['Far'] = far_count
    
    return counts


def calculate_rule_count(variation_count: int, rule_percentage: float) -> int:
    """
    Calculate how many variations should follow rules.
    
    Args:
        variation_count: Total number of variations
        rule_percentage: Percentage that should follow rules (0.0 to 1.0)
        
    Returns:
        Number of variations that should follow rules (rounded up)
    """
    import math
    return math.ceil(variation_count * rule_percentage)


if __name__ == "__main__":
    # Test the parser with a sample query
    sample_query = """Generate exactly 11 variations of {name}. Ensure the generated variations reflect phonetic similarity (30% Light, 40% Medium, 30% Far) and orthographic similarity (50% Light, 50% Medium). Approximately 51% of all generated variations should follow these rule-based transformations: Reorder name parts."""
    
    requirements = parse_query_template(sample_query)
    print("Parsed requirements:", requirements)