import re

def parse_query_template(query_template: str):
    """Extract requirements from query template"""
    requirements = {
        'variation_count': 15,
        'rule_percentage': 0,
        'rules': [],
        'phonetic_similarity': {},
        'orthographic_similarity': {},
        'uav_seed_name': None  # Phase 3: UAV seed name
    }
    
    # Extract variation count
    count_match = re.search(r'Generate\s+(\d+)\s+variations', query_template, re.I)
    if count_match:
        requirements['variation_count'] = int(count_match.group(1))
    
    # Extract rule percentage - look for patterns like "X% of", "approximately X%", "include X%"
    rule_pct_patterns = [
        r'approximately\s+(\d+)%\s+of',  # "Approximately 24% of"
        r'also\s+include\s+(\d+)%\s+of', # "also include 44% of"
        r'(\d+)%\s+of\s+the\s+total',     # "24% of the total"
        r'(\d+)%\s+of\s+variations',      # "24% of variations"
        r'include\s+(\d+)%',              # "include 24%"
        r'(\d+)%\s+should\s+follow'       # "24% should follow"
    ]
    for pattern in rule_pct_patterns:
        rule_pct_match = re.search(pattern, query_template, re.I)
        if rule_pct_match:
            pct = rule_pct_match.group(1)
            requirements['rule_percentage'] = int(pct) / 100
            break
    
    # Extract rules - check various phrasings
    # Character replacement
    if 'replace spaces with special characters' in query_template.lower() or 'replace spaces with random special characters' in query_template.lower():
        requirements['rules'].append('replace_spaces_with_special_characters')
    if 'replace double letters' in query_template.lower() or 'replace double letters with single letter' in query_template.lower():
        requirements['rules'].append('replace_double_letters')
    if 'replace random vowels' in query_template.lower() or 'replace vowels with different vowels' in query_template.lower():
        requirements['rules'].append('replace_random_vowels')
    if 'replace random consonants' in query_template.lower() or 'replace consonants with different consonants' in query_template.lower():
        requirements['rules'].append('replace_random_consonants')
    
    # Character swapping
    if 'swap adjacent consonants' in query_template.lower():
        requirements['rules'].append('swap_adjacent_consonants')
    if 'swap adjacent syllables' in query_template.lower():
        requirements['rules'].append('swap_adjacent_syllables')
    if 'swap random letter' in query_template.lower() or 'swap random adjacent letters' in query_template.lower():
        requirements['rules'].append('swap_random_letter')
    
    # Character removal
    if 'delete a random letter' in query_template.lower() or 'delete random letter' in query_template.lower():
        requirements['rules'].append('delete_random_letter')
    if 'remove random vowel' in query_template.lower() or 'remove a random vowel' in query_template.lower():
        requirements['rules'].append('remove_random_vowel')
    if 'remove random consonant' in query_template.lower() or 'remove a random consonant' in query_template.lower():
        requirements['rules'].append('remove_random_consonant')
    if 'remove all spaces' in query_template.lower() or 'remove spaces' in query_template.lower():
        requirements['rules'].append('remove_all_spaces')
    
    # Character insertion
    if 'duplicate a random letter' in query_template.lower() or 'duplicate random letter' in query_template.lower():
        requirements['rules'].append('duplicate_random_letter')
    if 'insert random letter' in query_template.lower() or 'insert a random letter' in query_template.lower():
        requirements['rules'].append('insert_random_letter')
    if 'add a title prefix' in query_template.lower() or 'title prefix' in query_template.lower() or 'add title prefix' in query_template.lower():
        requirements['rules'].append('add_title_prefix')
    if 'add a title suffix' in query_template.lower() or 'title suffix' in query_template.lower() or 'add title suffix' in query_template.lower():
        requirements['rules'].append('add_title_suffix')
    
    # Name formatting
    if 'use first name initial' in query_template.lower() or 'first name initial with last name' in query_template.lower():
        requirements['rules'].append('initial_only_first_name')
    if 'convert name to initials' in query_template.lower() or 'shorten name to initials' in query_template.lower():
        requirements['rules'].append('shorten_to_initials')
    if 'abbreviate name parts' in query_template.lower() or 'abbreviate' in query_template.lower() or 'shorten name to abbreviations' in query_template.lower():
        requirements['rules'].append('abbreviate_name_parts')
    
    # Structure change
    if 'reorder name parts' in query_template.lower() or 'reorder parts' in query_template.lower() or 'name parts permutations' in query_template.lower():
        requirements['rules'].append('reorder_name_parts')
    
    # Extract phonetic similarity distribution (Light/Medium/Far percentages)
    # First try VALIDATION HINTS section (more reliable format)
    phonetic_match = re.search(r'\[VALIDATION HINTS\].*?Phonetic similarity:\s*([^.;]+)', query_template, re.I | re.DOTALL)
    if phonetic_match:
        hints_text = phonetic_match.group(1)
        # Extract percentages from hints: "10% Light, 50% Medium, 40% Far"
        hints_match = re.search(r'(\d+)%\s+Light.*?(\d+)%\s+Medium.*?(\d+)%\s+Far', hints_text, re.I)
        if hints_match:
            light_pct = int(hints_match.group(1)) / 100.0
            medium_pct = int(hints_match.group(2)) / 100.0
            far_pct = int(hints_match.group(3)) / 100.0
            requirements['phonetic_similarity'] = {
                'Light': light_pct,
                'Medium': medium_pct,
                'Far': far_pct
            }
    
    # If not found in VALIDATION HINTS, try other patterns
    if 'phonetic_similarity' not in requirements or not requirements['phonetic_similarity']:
        phonetic_match = re.search(r'phonetic similarity.*?distribution.*?(\d+)%\s+Light.*?(\d+)%\s+Medium.*?(\d+)%\s+Far', query_template, re.I | re.DOTALL)
        if not phonetic_match:
            # Try alternative patterns
            phonetic_match = re.search(r'phonetic similarity.*?(\d+)%\s+Light.*?(\d+)%\s+Medium.*?(\d+)%\s+Far', query_template, re.I | re.DOTALL)
        if phonetic_match:
            light_pct = int(phonetic_match.group(1)) / 100.0
            medium_pct = int(phonetic_match.group(2)) / 100.0
            far_pct = int(phonetic_match.group(3)) / 100.0
            requirements['phonetic_similarity'] = {
                'Light': light_pct,
                'Medium': medium_pct,
                'Far': far_pct
            }
        else:
            # Fallback: check for simpler patterns
            if 'phonetic similarity' in query_template.lower():
                # Default to Medium if no specific distribution found
                requirements['phonetic_similarity'] = {'Medium': 1.0}
    
    # Extract orthographic similarity distribution (Light/Medium/Far percentages)
    # First try VALIDATION HINTS section (more reliable format)
    orthographic_match = re.search(r'\[VALIDATION HINTS\].*?Orthographic similarity:\s*([^.;]+)', query_template, re.I | re.DOTALL)
    if orthographic_match:
        hints_text = orthographic_match.group(1)
        # Extract percentages from hints: "70% Light, 30% Medium" or "70% Light, 30% Medium, 0% Far"
        hints_match = re.search(r'(\d+)%\s+Light.*?(\d+)%\s+Medium(?:.*?(\d+)%\s+Far)?', hints_text, re.I)
        if hints_match:
            light_pct = int(hints_match.group(1)) / 100.0
            medium_pct = int(hints_match.group(2)) / 100.0
            far_pct = int(hints_match.group(3)) / 100.0 if hints_match.lastindex >= 3 and hints_match.group(3) else 0.0
            requirements['orthographic_similarity'] = {
                'Light': light_pct,
                'Medium': medium_pct
            }
            if far_pct > 0:
                requirements['orthographic_similarity']['Far'] = far_pct
    
    # If not found in VALIDATION HINTS, try other patterns
    if 'orthographic_similarity' not in requirements or not requirements['orthographic_similarity']:
        orthographic_match = re.search(r'orthographic similarity.*?distribution.*?(\d+)%\s+Light.*?(\d+)%\s+Medium', query_template, re.I | re.DOTALL)
        if not orthographic_match:
            # Try alternative patterns (may include Far)
            orthographic_match = re.search(r'orthographic similarity.*?(\d+)%\s+Light.*?(\d+)%\s+Medium(?:.*?(\d+)%\s+Far)?', query_template, re.I | re.DOTALL)
        if orthographic_match:
            light_pct = int(orthographic_match.group(1)) / 100.0
            medium_pct = int(orthographic_match.group(2)) / 100.0
            far_pct = int(orthographic_match.group(3)) / 100.0 if orthographic_match.lastindex >= 3 and orthographic_match.group(3) else 0.0
            requirements['orthographic_similarity'] = {
                'Light': light_pct,
                'Medium': medium_pct
            }
            if far_pct > 0:
                requirements['orthographic_similarity']['Far'] = far_pct
        else:
            # Fallback: check for simpler patterns
            if 'orthographic similarity' in query_template.lower():
                # Default to Medium if no specific distribution found
                requirements['orthographic_similarity'] = {'Medium': 1.0}
    
    # Extract UAV seed name from Phase 3 requirements
    uav_match = re.search(r'For the seed "([^"]+)" ONLY', query_template, re.I)
    if uav_match:
        requirements['uav_seed_name'] = uav_match.group(1)
    
    return requirements