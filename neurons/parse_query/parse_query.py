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
        'target_names': [],  # Initialize target names list
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
    """
    Extract specific transformation rules to apply.
    
    This function uses comprehensive if-statement checks to detect all possible
    rule variations mentioned in the validator's query template.
    """
    rules = []
    query_lower = query_template.lower()
    
    # Character replacement rules
    if 'replace spaces with special characters' in query_lower or 'replace spaces with random special characters' in query_lower:
        rules.append('replace_spaces_with_special_characters')
    
    if 'replace double letters' in query_lower or 'replace double letters with single letter' in query_lower:
        rules.append('replace_double_letters')
    
    if 'replace random vowels' in query_lower or 'replace vowels with different vowels' in query_lower:
        rules.append('replace_random_vowels')
    
    if 'replace random consonants' in query_lower or 'replace consonants with different consonants' in query_lower:
        rules.append('replace_random_consonants')
    
    # Character swapping rules
    if 'swap adjacent consonants' in query_lower:
        rules.append('swap_adjacent_consonants')
    
    if 'swap adjacent syllables' in query_lower:
        rules.append('swap_adjacent_syllables')
    
    if 'swap random letter' in query_lower or 'swap random adjacent letters' in query_lower:
        rules.append('swap_random_letter')
    
    # Character removal rules
    if 'delete a random letter' in query_lower or 'delete random letter' in query_lower:
        rules.append('delete_random_letter')
    
    if 'remove random vowel' in query_lower or 'remove a random vowel' in query_lower:
        rules.append('remove_random_vowel')
    
    if 'remove random consonant' in query_lower or 'remove a random consonant' in query_lower:
        rules.append('remove_random_consonant')
    
    if 'remove all spaces' in query_lower or 'remove spaces' in query_lower:
        rules.append('remove_all_spaces')
    
    # Character insertion rules
    if 'duplicate a random letter' in query_lower or 'duplicate random letter' in query_lower:
        rules.append('duplicate_random_letter')
    
    if 'insert random letter' in query_lower or 'insert a random letter' in query_lower:
        rules.append('insert_random_letter')
    
    if 'add a title prefix' in query_lower or 'title prefix' in query_lower or 'add title prefix' in query_lower:
        rules.append('add_title_prefix')
    
    if 'add a title suffix' in query_lower or 'title suffix' in query_lower or 'add title suffix' in query_lower:
        rules.append('add_title_suffix')
    
    # Name formatting rules
    if 'use first name initial' in query_lower or 'first name initial with last name' in query_lower:
        rules.append('initial_only_first_name')
    
    if 'convert name to initials' in query_lower or 'shorten name to initials' in query_lower:
        rules.append('shorten_to_initials')
    
    if 'abbreviate name parts' in query_lower or 'abbreviate' in query_lower or 'shorten name to abbreviations' in query_lower:
        rules.append('abbreviate_name_parts')
    
    # Structure change rules
    if 'reorder name parts' in query_lower or 'reorder parts' in query_lower or 'name parts permutations' in query_lower:
        rules.append('reorder_name_parts')
    
    # Additional common rule patterns (for backward compatibility)
    if 'transliterate' in query_lower:
        rules.append('transliterate')
    
    if 'add special characters' in query_lower:
        rules.append('add_special_characters')
    
    # Remove duplicates while preserving order
    unique_rules = []
    for rule in rules:
        if rule not in unique_rules:
            unique_rules.append(rule)
    
    return unique_rules


def _extract_phonetic_similarity(query_template: str) -> Dict[str, float]:
    """Extract phonetic similarity distribution requirements."""
    phonetic_sim = {}
    
    # Enhanced patterns to match your query format
    patterns = [
        # Pattern 1: "phonetic similarity (30% Light, 40% Medium, 30% Far)"
        r'phonetic\s+similarity\s*\(([^)]+)\)',
        # Pattern 2: "phonetic similarity: 30% Light, 40% Medium, 30% Far"
        r'phonetic\s+similarity[:\s]+([^.]+)',
        # Pattern 3: Original patterns
        r'phonetic.*?Light[:\s]+(\d+)%.*?Medium[:\s]+(\d+)%.*?Far[:\s]+(\d+)%',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, query_template, re.I | re.DOTALL)
        if match:
            similarity_text = match.group(1) if len(match.groups()) == 1 else match.group(0)
            
            # Extract percentages for Light, Medium, Far
            light_match = re.search(r'(\d+)%\s*Light', similarity_text, re.I)
            medium_match = re.search(r'(\d+)%\s*Medium', similarity_text, re.I)
            far_match = re.search(r'(\d+)%\s*Far', similarity_text, re.I)
            
            if light_match:
                phonetic_sim['Light'] = int(light_match.group(1)) / 100
            if medium_match:
                phonetic_sim['Medium'] = int(medium_match.group(1)) / 100
            if far_match:
                phonetic_sim['Far'] = int(far_match.group(1)) / 100
            
            # If we found any matches, break
            if phonetic_sim:
                break
    
    bt.logging.debug(f"Extracted phonetic similarity: {phonetic_sim}")
    return phonetic_sim


def _extract_orthographic_similarity(query_template: str) -> Dict[str, float]:
    """Extract orthographic similarity distribution requirements."""
    ortho_sim = {}
    
    # Enhanced patterns to match your query format
    patterns = [
        # Pattern 1: "orthographic similarity (50% Light, 50% Medium)"
        r'orthographic\s+similarity\s*\(([^)]+)\)',
        # Pattern 2: "orthographic similarity: 50% Light, 50% Medium"
        r'orthographic\s+similarity[:\s]+([^.]+)',
        # Pattern 3: Original patterns
        r'orthographic.*?Light[:\s]+(\d+)%.*?Medium[:\s]+(\d+)%.*?Far[:\s]+(\d+)%',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, query_template, re.I | re.DOTALL)
        if match:
            similarity_text = match.group(1) if len(match.groups()) == 1 else match.group(0)
            
            # Extract percentages for Light, Medium, Far
            light_match = re.search(r'(\d+)%\s*Light', similarity_text, re.I)
            medium_match = re.search(r'(\d+)%\s*Medium', similarity_text, re.I)
            far_match = re.search(r'(\d+)%\s*Far', similarity_text, re.I)
            
            if light_match:
                ortho_sim['Light'] = int(light_match.group(1)) / 100
            if medium_match:
                ortho_sim['Medium'] = int(medium_match.group(1)) / 100
            if far_match:
                ortho_sim['Far'] = int(far_match.group(1)) / 100
            
            # If we found any matches, break
            if ortho_sim:
                break
    
    bt.logging.debug(f"Extracted orthographic similarity: {ortho_sim}")
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


def extract_names_from_identity(identity_list) -> List[str]:
    """
    Extract names from synapse.identity list.
    This is the CRITICAL function that prevents extra names penalty.
    """
    names = []
    
    if not identity_list:
        return names
    
    for identity in identity_list:
        if isinstance(identity, (list, tuple)) and len(identity) > 0:
            name = identity[0]
            if isinstance(name, str) and name.strip():
                cleaned_name = name.strip()
                if _is_valid_name(cleaned_name):
                    names.append(cleaned_name)
    
    bt.logging.info(f"Extracted {len(names)} names from identity list")
    return names


def extract_names_from_synapse(synapse) -> List[str]:
    """
    Extract names from synapse attributes as fallback.
    """
    names = []
    
    # Try to extract from identity attribute
    if hasattr(synapse, 'identity') and synapse.identity:
        names = extract_names_from_identity(synapse.identity)
    
    # Try other possible attributes if identity doesn't work
    if not names:
        for attr_name in ['names', 'name_list', 'target_names']:
            if hasattr(synapse, attr_name):
                attr_value = getattr(synapse, attr_name)
                if isinstance(attr_value, list):
                    for item in attr_value:
                        if isinstance(item, str) and item.strip():
                            names.append(item.strip())
                elif isinstance(attr_value, str) and attr_value.strip():
                    names.append(attr_value.strip())
    
    return names


def _is_valid_name(name: str) -> bool:
    """
    Validate that a string is a valid name.
    """
    if not name or len(name.strip()) < 2:
        return False
    
    # Check for basic name patterns (letters, spaces, hyphens, apostrophes)
    if not re.match(r"^[A-Za-zÀ-ÿ]+([ '\-][A-Za-zÀ-ÿ]+)*$", name):
        return False
    
    # Reject if it looks like an address or date
    name_lower = name.lower()
    
    # Check for numbers (names shouldn't have numbers)
    if re.search(r'\d', name):
        return False
    
    # Check for address indicators
    address_words = ['street', 'st', 'avenue', 'ave', 'road', 'rd', 'drive', 'dr', 'lane', 'ln']
    for word in address_words:
        if word in name_lower:
            return False
    
    return True


def get_complete_requirements(query_template: str, synapse=None) -> Dict[str, Any]:
    """
    Get complete requirements including target names from both query and synapse.
    This is the main function to use in your miner.
    """
    # Parse query template
    requirements = parse_query_template(query_template)
    
    # Initialize target_names if not present
    if 'target_names' not in requirements:
        requirements['target_names'] = []
    
    # CRITICAL FIX: For {name} templates, extract names from synapse.identity
    if '{name}' in query_template and synapse and hasattr(synapse, 'identity'):
        identity_names = extract_names_from_identity(synapse.identity)
        if identity_names:
            requirements['target_names'] = identity_names
            bt.logging.info(f"🎯 Extracted {len(identity_names)} target names from synapse.identity: {identity_names}")
    
    # If no target names found in query, try to get from synapse attributes
    elif not requirements['target_names'] and synapse:
        synapse_names = extract_names_from_synapse(synapse)
        if synapse_names:
            requirements['target_names'] = synapse_names
            bt.logging.info(f"🎯 Extracted target names from synapse attributes: {synapse_names}")
    
    # Final validation
    if not requirements['target_names']:
        bt.logging.error("❌ CRITICAL: No target names found! This will cause severe penalties!")
        bt.logging.error(f"Query: {query_template[:200]}...")
        if synapse:
            bt.logging.error(f"Synapse has identity: {hasattr(synapse, 'identity')}")
            if hasattr(synapse, 'identity'):
                bt.logging.error(f"Identity count: {len(synapse.identity) if synapse.identity else 0}")
    
    return requirements


def validate_requirements(requirements: Dict[str, Any]) -> bool:
    """
    Validate that requirements are complete to avoid penalties.
    """
    issues = []
    
    # Check target names
    if not requirements.get('target_names'):
        issues.append("No target names - will cause extra/missing names penalties")
    
    # Check variation count
    if requirements.get('variation_count', 0) <= 0:
        issues.append("Invalid variation count")
    
    # Check rule percentage
    rule_pct = requirements.get('rule_percentage', 0)
    if rule_pct < 0 or rule_pct > 1:
        issues.append(f"Invalid rule percentage: {rule_pct}")
    
    if issues:
        bt.logging.error("❌ Requirements validation failed:")
        for issue in issues:
            bt.logging.error(f"   - {issue}")
        return False
    
    bt.logging.info("✅ Requirements validation passed")
    return True


if __name__ == "__main__":
    # Test the parser with a sample query
    sample_query = """Generate exactly 11 variations of {name}. Ensure the generated variations reflect phonetic similarity (30% Light, 40% Medium, 30% Far) and orthographic similarity (50% Light, 50% Medium). Approximately 51% of all generated variations should follow these rule-based transformations: Reorder name parts."""
    
    requirements = parse_query_template(sample_query)
    print("Parsed requirements:", requirements)