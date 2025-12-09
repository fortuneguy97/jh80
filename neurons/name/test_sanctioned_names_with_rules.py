#!/usr/bin/env python3
"""
Test script: Generate variations for 15 names from sanctioned list
and score them using the validator's reward calculation.
"""

import sys
import os
import json
import random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

from maximize_orthographic_similarity import OrthographicBruteForceGenerator, generate_dob_variations
from reward import (
    get_name_variation_rewards,
    calculate_variation_quality,
    calculate_phonetic_similarity,
    calculate_orthographic_similarity
)
from rule_evaluator import evaluate_rule_compliance
import numpy as np
from typing import Dict, List, Any

# Mock validator class for testing
class MockValidator:
    def __init__(self):
        # Create a mock config object
        class MockConfig:
            class Neuron:
                burn_fraction = 0.40
                top_miner_cap = 10
                quality_threshold = 0.5
                decay_rate = 0.1
                blend_factor = 0.5
            neuron = Neuron()
        self.config = MockConfig()
        self.uid = 1  # Validator UID
    
    def get_name_variation_rewards(
        self,
        seed_names: List[str],
        seed_dob: List[str],
        seed_addresses: List[str],
        seed_script: List[str],
        responses: List[Dict[str, List[List[str]]]],
        uids: List[int],
        variation_count: int = 10,
        phonetic_similarity: Dict[str, float] = None,
        orthographic_similarity: Dict[str, float] = None,
        rule_based: Dict[str, Any] = None
    ):
        return get_name_variation_rewards(
            self,
            seed_names,
            seed_dob,
            seed_addresses,
            seed_script,
            responses,
            uids,
            variation_count,
            phonetic_similarity,
            orthographic_similarity,
            rule_based
        )

def load_addresses_from_cache() -> Dict[str, List[str]]:
    """Load addresses from normalized_address_cache.json, selecting countries with 15 addresses."""
    with open('normalized_address_cache.json', 'r', encoding='utf-8') as f:
        cache = json.load(f)
    
    addresses = cache.get('addresses', {})
    countries_with_15 = []
    
    # Find countries with exactly 15 addresses
    for country, addr_list in addresses.items():
        if isinstance(addr_list, list) and len(addr_list) == 15:
            countries_with_15.append(country)
            if len(countries_with_15) >= 15:
                break
    
    # Extract just the address strings
    country_addresses = {}
    for country in countries_with_15[:15]:  # Take first 15 countries
        country_addresses[country] = [addr.get('address', '') for addr in addresses[country] if addr.get('address')]
    
    return country_addresses

def load_sanctioned_names(count: int = 15) -> List[Dict[str, str]]:
    """Load names from sanctioned list."""
    with open('MIID/validator/Sanctioned_list.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Select random names
    selected = random.sample(data, min(count, len(data)))
    
    # Load addresses from cache
    country_addresses = load_addresses_from_cache()
    country_list = list(country_addresses.keys())
    
    # Extract name, DOB, and country
    names_data = []
    for i, item in enumerate(selected):
        first_name = item.get('FirstName', '')
        last_name = item.get('LastName', '')
        full_name = f"{first_name} {last_name}".strip()
        dob = item.get('DOB', '1980-01-01')
        original_country = item.get('Country_Residence', 'Unknown')
        
        # Assign addresses from cache (cycle through countries if needed)
        assigned_country = country_list[i % len(country_list)]
        addresses = country_addresses[assigned_country]
        
        names_data.append({
            'name': full_name,
            'first_name': first_name,
            'last_name': last_name,
            'dob': dob,
            'country': original_country,
            'addresses': addresses  # Add addresses from cache
        })
    
    return names_data

# Global rule set that will be used for all names (to match validator expectations)
COMMON_RULES = ["delete_random_letter", "insert_random_letter", "swap_random_letter"]

def generate_variations_for_name(name_data: Dict, variation_count: int = 15, use_common_rules: bool = True) -> Dict[str, Any]:
    """Generate variations for a single name with rule compliance."""
    full_name = name_data['name']
    first_name = name_data['first_name']
    last_name = name_data['last_name']
    dob = name_data['dob']
    
    if use_common_rules:
        # Use common rules that work for all names (to match validator expectations)
        selected_rules = COMMON_RULES
        rule_percentage = 30
    else:
        # Select random rules (1-3 rules, 30% compliance)
        # First, filter rules to only those applicable to this name
        from rule_evaluator import has_double_letters, has_diff_adjacent_consonants
        
        all_rules = [
            "replace_double_letters_with_single_letter",
            "swap_adjacent_consonants",
            "delete_random_letter",
            "remove_random_vowel",
            "remove_random_consonant",
            "replace_random_vowel_with_random_vowel",
            "replace_random_consonant_with_random_consonant",
            "swap_random_letter",
            "insert_random_letter",
            "duplicate_random_letter_as_double_letter",
            "remove_all_spaces",
            "replace_spaces_with_random_special_characters",
            "initial_only_first_name",
            "shorten_name_to_initials",
            "shorten_name_to_abbreviations",
            "name_parts_permutations"
        ]
        
        # Filter to only applicable rules (validator lowercases names, so check lowercase version)
        name_lower = full_name.lower()
        applicable_rules = []
        for rule in all_rules:
            applicable = True
            # Rule: Name parts permutations / initials (require multi-part name)
            if rule in ('name_parts_permutations', 'initial_only_first_name', 'shorten_name_to_initials', 'shorten_name_to_abbreviations'):
                if len(name_lower.split()) < 2:
                    applicable = False
            # Rule: Space removal/replacement (requires a space)
            if rule in ('replace_spaces_with_random_special_characters', 'remove_all_spaces'):
                if ' ' not in name_lower:
                    applicable = False
            # Rule: Double letter replacement (requires double letters)
            if rule == 'replace_double_letters_with_single_letter':
                if not has_double_letters(name_lower):
                    applicable = False
            # Rule: Adjacent consonant swap (requires swappable adjacent consonants)
            if rule == 'swap_adjacent_consonants':
                if not has_diff_adjacent_consonants(name_lower):
                    applicable = False
            
            if applicable:
                applicable_rules.append(rule)
        
        # If no rules are applicable, use fallback rules that always work
        if not applicable_rules:
            applicable_rules = ['delete_random_letter', 'insert_random_letter', 'swap_random_letter']
        
        # Select 1-3 rules from applicable rules
        num_rules = random.randint(1, min(3, len(applicable_rules)))
        selected_rules = random.sample(applicable_rules, num_rules)
        rule_percentage = 30
    
    rule_based = {
        "selected_rules": selected_rules,
        "rule_percentage": rule_percentage
    }
    
    # Generate name variations
    target_distribution = {"Light": 0.2, "Medium": 0.6, "Far": 0.2}
    generator = OrthographicBruteForceGenerator(full_name, target_distribution, rule_based)
    name_variations, name_metrics = generator.generate_optimal_variations(variation_count)
    
    # Generate DOB variations
    dob_variations = generate_dob_variations(dob, variation_count)
    
    # Use addresses from cache if available, otherwise empty
    if 'addresses' in name_data and name_data['addresses']:
        # Use the addresses from cache (should be 15 addresses)
        address_variations = name_data['addresses'][:variation_count]
        # Pad with empty strings if needed
        while len(address_variations) < variation_count:
            address_variations.append("")
    else:
        # Create empty addresses
        address_variations = [""] * variation_count
    
    # Create response structure: [name_var, dob_var, address_var]
    variations_list = []
    for i in range(variation_count):
        name_var = name_variations[i] if i < len(name_variations) else ""
        dob_var = dob_variations[i] if i < len(dob_variations) else dob
        addr_var = address_variations[i] if i < len(address_variations) else ""
        variations_list.append([name_var, dob_var, addr_var])
    
    return {
        "name": full_name,
        "variations": variations_list,
        "rule_based": rule_based,
        "name_metrics": name_metrics
    }

def main():
    print("=" * 80)
    print("TESTING SANCTIONED NAMES WITH RULE COMPLIANCE")
    print("=" * 80)
    print()
    
    # Load 15 names from sanctioned list
    print("📋 Loading 15 names from sanctioned list...")
    names_data = load_sanctioned_names(15)
    
    # Set random seed for reproducibility
    random.seed(42)
    
    print(f"✅ Loaded {len(names_data)} names")
    print()
    
    # Generate variations for each name
    print("🔧 Generating variations for each name...")
    print("-" * 80)
    
    all_responses = {}
    seed_names = []
    seed_dobs = []
    seed_addresses = []
    seed_scripts = []
    
    for i, name_data in enumerate(names_data, 1):
        print(f"\n[{i}/15] Processing: {name_data['name']}")
        result = generate_variations_for_name(name_data, variation_count=15)
        
        all_responses[result['name']] = result['variations']
        seed_names.append(result['name'])
        seed_dobs.append(name_data['dob'])
        # Extract city or country from first address to use as seed_address
        # The validator expects seed_address to be just city/country, not full address
        seed_address = ""
        if name_data.get('addresses'):
            first_addr = name_data['addresses'][0]
            # Extract country (last part after comma) or city (second to last)
            parts = [p.strip() for p in first_addr.split(',')]
            if len(parts) >= 2:
                # Use country (last part) as seed address
                seed_address = parts[-1]
            elif len(parts) == 1:
                seed_address = parts[0]
        seed_addresses.append(seed_address)
        seed_scripts.append("latin")  # Assume Latin script
        
        print(f"   Generated {len(result['variations'])} variations")
        if result['name_metrics'].get('rule_compliance'):
            rc = result['name_metrics']['rule_compliance']
            print(f"   Rule compliance: {rc['rule_compliant_percentage']:.1f}% ({rc['rule_compliant_count']} variations)")
            print(f"   Rules: {rc['possible_rules']}")
    
    print()
    print("=" * 80)
    print("CALCULATING SCORES USING VALIDATOR")
    print("=" * 80)
    print()
    
    # Prepare data for validator - need to create response objects
    class MockResponse:
        def __init__(self, variations):
            self.variations = variations
    
    responses = [MockResponse(all_responses)]
    uids = [1]  # Single miner UID
    
    # Match the generator's distribution: Light=20%, Medium=60%, Far=20%
    phonetic_similarity = {"Light": 0.2, "Medium": 0.6, "Far": 0.2}
    orthographic_similarity = {"Light": 0.2, "Medium": 0.6, "Far": 0.2}
    
    # Use the same common rules for validator that we used for generation
    rule_based = {
        "selected_rules": COMMON_RULES,
        "rule_percentage": 30
    }
    
    # Calculate rewards
    validator = MockValidator()
    rewards, reward_uids, detailed_metrics = validator.get_name_variation_rewards(
        seed_names=seed_names,
        seed_dob=seed_dobs,
        seed_addresses=seed_addresses,
        seed_script=seed_scripts,
        responses=responses,
        uids=uids,
        variation_count=15,
        phonetic_similarity=phonetic_similarity,
        orthographic_similarity=orthographic_similarity,
        rule_based=rule_based
    )
    
    # Extract detailed metrics
    if detailed_metrics and len(detailed_metrics) > 0:
        metrics = detailed_metrics[0]
        
        # Get final score (post_penalty_reward or final_reward)
        final_score = metrics.get('post_penalty_reward', metrics.get('final_reward', 0.0))
        
        print("FINAL SCORE")
        print("=" * 80)
        print(f"{final_score:.3f}")
        print()
        
        # Names score (average quality)
        names_score = metrics.get('average_quality', 0.0)
        print("Names")
        print("-" * 80)
        print(f"{names_score:.3f}")
        print()
        
        print("Basic Quality Score")
        print("-" * 80)
        print(f"{names_score:.3f}")
        print()
        
        # Similarity Score (average_base_score)
        similarity_score = metrics.get('average_base_score', metrics.get('similarity_score', 0.0))
        print("Similarity Score")
        print("-" * 80)
        print(f"{similarity_score:.3f}")
        print()
        
        # Phonetic and Orthographic - extract from name_metrics
        phonetic_avg = 0.0
        orthographic_avg = 0.0
        name_metrics_dict = metrics.get('name_metrics', {})
        if name_metrics_dict:
            phonetic_scores_all = []
            orthographic_scores_all = []
            for name, name_metrics in name_metrics_dict.items():
                if isinstance(name_metrics, dict):
                    # Extract from first_name metrics
                    if 'first_name' in name_metrics and 'metrics' in name_metrics['first_name']:
                        first_metrics = name_metrics['first_name']['metrics']
                        if 'variations' in first_metrics:
                            for var_data in first_metrics['variations']:
                                if 'phonetic_score' in var_data:
                                    phonetic_scores_all.append(var_data['phonetic_score'])
                                if 'orthographic_score' in var_data:
                                    orthographic_scores_all.append(var_data['orthographic_score'])
                    
                    # Extract from last_name metrics
                    if 'last_name' in name_metrics and 'metrics' in name_metrics['last_name']:
                        last_metrics = name_metrics['last_name']['metrics']
                        if 'variations' in last_metrics:
                            for var_data in last_metrics['variations']:
                                if 'phonetic_score' in var_data:
                                    phonetic_scores_all.append(var_data['phonetic_score'])
                                if 'orthographic_score' in var_data:
                                    orthographic_scores_all.append(var_data['orthographic_score'])
            
            if phonetic_scores_all:
                phonetic_avg = sum(phonetic_scores_all) / len(phonetic_scores_all)
            if orthographic_scores_all:
                orthographic_avg = sum(orthographic_scores_all) / len(orthographic_scores_all)
        
        print("Phonetic Similarity")
        print("-" * 80)
        print(f"{phonetic_avg:.3f}")
        print()
        
        print("Orthographic Similarity")
        print("-" * 80)
        print(f"{orthographic_avg:.3f}")
        print()
        
        # Count, Uniqueness, Length scores - extract from name_metrics
        count_score = 0.0
        uniqueness_score = 0.0
        length_score = 0.0
        if name_metrics_dict:
            count_scores = []
            uniqueness_scores = []
            length_scores = []
            for name, name_metrics in name_metrics_dict.items():
                if isinstance(name_metrics, dict):
                    # Extract from first_name metrics
                    if 'first_name' in name_metrics and 'metrics' in name_metrics['first_name']:
                        first_metrics = name_metrics['first_name']['metrics']
                        if 'count' in first_metrics and 'score' in first_metrics['count']:
                            count_scores.append(first_metrics['count']['score'])
                        if 'uniqueness' in first_metrics and 'score' in first_metrics['uniqueness']:
                            uniqueness_scores.append(first_metrics['uniqueness']['score'])
                        if 'length' in first_metrics and 'score' in first_metrics['length']:
                            length_scores.append(first_metrics['length']['score'])
                    
                    # Extract from last_name metrics
                    if 'last_name' in name_metrics and 'metrics' in name_metrics['last_name']:
                        last_metrics = name_metrics['last_name']['metrics']
                        if 'count' in last_metrics and 'score' in last_metrics['count']:
                            count_scores.append(last_metrics['count']['score'])
                        if 'uniqueness' in last_metrics and 'score' in last_metrics['uniqueness']:
                            uniqueness_scores.append(last_metrics['uniqueness']['score'])
                        if 'length' in last_metrics and 'score' in last_metrics['length']:
                            length_scores.append(last_metrics['length']['score'])
            
            if count_scores:
                count_score = sum(count_scores) / len(count_scores)
            if uniqueness_scores:
                uniqueness_score = sum(uniqueness_scores) / len(uniqueness_scores)
            if length_scores:
                length_score = sum(length_scores) / len(length_scores)
        
        print("Count Score")
        print("-" * 80)
        print(f"{count_score:.3f}")
        print()
        
        print("Uniqueness Score")
        print("-" * 80)
        print(f"{uniqueness_score:.3f}")
        print()
        
        print("Length Score")
        print("-" * 80)
        print(f"{length_score:.3f}")
        print()
        
        # Rule Compliance Score
        rule_compliance_score = 0.0
        rule_compliance = metrics.get('rule_compliance', {})
        if rule_compliance:
            rule_compliance_score = rule_compliance.get('overall_score', 0.0)
        
        print("Rule Compliance Score")
        print("-" * 80)
        print(f"{rule_compliance_score:.3f}")
        print()
        
        # Debug rule compliance breakdown
        if rule_compliance:
            print("Rule Compliance Breakdown (Debug)")
            print("-" * 80)
            by_name = rule_compliance.get('by_name', {})
            if by_name:
                for name, rc_metrics in list(by_name.items())[:3]:  # Show first 3
                    print(f"  {name}:")
                    print(f"    Score: {rc_metrics.get('score', 0.0):.3f}")
                    print(f"    Expected: {rc_metrics.get('expected_compliant_variations_count', 0)}")
                    print(f"    Actual: {rc_metrics.get('overall_compliant_unique_variations_count', 0)}")
                    print(f"    Quantity Score: {rc_metrics.get('quantity_score', 0.0):.3f}")
                    print(f"    Diversity Factor: {rc_metrics.get('rule_diversity_factor', 0.0):.3f}")
                    print(f"    Rules Met: {rc_metrics.get('num_target_rules_met', 0)}/{rc_metrics.get('total_target_rules', 0)}")
            print()
        
        # Address Score
        address_grading = metrics.get('address_grading', {})
        address_score = address_grading.get('overall_score', 0.0)
        print("Address Score")
        print("-" * 80)
        print(f"{address_score:.3f}")
        print()
        
        # Address sub-scores
        looks_like_addr = address_grading.get('looks_like_address_score', 0.0)
        print("Looks Like Address")
        print("-" * 80)
        print(f"{looks_like_addr:.3f}")
        print()
        
        region_match = address_grading.get('region_match_score', 0.0)
        print("Address Regain Match")
        print("-" * 80)
        print(f"{region_match:.3f}")
        print()
        
        api_score = address_grading.get('api_validation_score', 0.0)
        print("Address API call")
        print("-" * 80)
        print(f"{api_score:.3f}")
        print()
        
        # DOB Score
        dob_grading = metrics.get('dob_grading', {})
        dob_score = dob_grading.get('overall_score', 0.0)
        print("DOB Score")
        print("-" * 80)
        print(f"{dob_score:.3f}")
        print()
        
        # Penalties
        penalties = metrics.get('penalties', {})
        
        print("Completeness Multiplier")
        print("-" * 80)
        completeness = metrics.get('completeness_multiplier', 1.0)
        print(f"{completeness:.3f}")
        print()
        
        print("Extra names penalty")
        print("-" * 80)
        extra_penalty = penalties.get('extra_names_penalty', 0.0)
        print(f"{extra_penalty:.3f}")
        print()
        
        print("Missing names penalty")
        print("-" * 80)
        missing_penalty = penalties.get('missing_names_penalty', 0.0)
        print(f"{missing_penalty:.3f}")
        print()
        
        print("Post Penalty")
        print("-" * 80)
        print(f"{final_score:.3f}")
        print()
        
        print("Address Penalty")
        print("-" * 80)
        addr_penalty = penalties.get('address_penalty', 0.0)
        print(f"{addr_penalty:.3f}")
        print()
        
        print("Collusion Penalty")
        print("-" * 80)
        collusion_penalty = penalties.get('collusion_penalty', 0.0)
        print(f"{collusion_penalty:.3f}")
        print()
        
        print("Duplication Penalty")
        print("-" * 80)
        dup_penalty = penalties.get('duplication_penalty', 0.0)
        print(f"{dup_penalty:.3f}")
        print()
        
        print("Signature Copy Penalty")
        print("-" * 80)
        sig_penalty = penalties.get('signature_copy_penalty', 0.0)
        print(f"{sig_penalty:.3f}")
        print()
        
        print("Special Chars Penalty")
        print("-" * 80)
        special_chars_penalty = penalties.get('special_chars_penalty', 0.0)
        print(f"{special_chars_penalty:.3f}")
        print()
    else:
        print("❌ No detailed metrics returned")
        print(f"Rewards: {rewards}")
        if detailed_metrics:
            print(f"Detailed metrics keys: {list(detailed_metrics[0].keys())}")
        else:
            print("No detailed metrics available")

if __name__ == "__main__":
    main()

