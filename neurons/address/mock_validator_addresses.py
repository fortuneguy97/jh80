#!/usr/bin/env python3
"""
Mock Validator for Address Validation
Simulates how the validator would grade address variations and returns the final score.
"""

import os
import sys
import json
from typing import Dict, Any

# Add MIID validator to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

from reward import _grade_address_variations

# Manchester addresses to test
MANCHESTER_ADDRESSES = [
    "1 Hilton Street, Manchester, M1 1JJ, United Kingdom",
    "3 Spear Street, Manchester, M1 1JU, United Kingdom",
    "5 Stevenson Square, Manchester, M1 1FB, United Kingdom",
    "7 Warwick Street, Manchester, M1 3BU, United Kingdom",
    "9 Little Lever Street, Manchester, M1 1HR, United Kingdom",
    "11 Back Piccadilly, Manchester, M1 1HP, United Kingdom",
    "13 Dale Street, Manchester, M1 1NJ, United Kingdom",
    "15 Hilton Street, Manchester, M1 1JN, United Kingdom",
    "17 Lever Street, Manchester, M1 1BY, United Kingdom",
    "19 Spear Street, Manchester, M1 1JN, United Kingdom",
    "21 Tib Street, Manchester, M1 1LW, United Kingdom",
    "23 Faraday Street, Manchester, M1 1BE, United Kingdom",
    "25 Hilton Street, Manchester, M1 1EL, United Kingdom",
    "27 Turner Street, Manchester, M4 1DW, United Kingdom",
    "29 Back Turner Street, Manchester, M4 1FN, United Kingdom"
]


class MockValidator:
    """Mock validator that simulates address validation"""
    
    def __init__(self, validator_uid: int = 101, miner_uid: int = 501):
        self.validator_uid = validator_uid
        self.miner_uid = miner_uid
    
    def validate_addresses(
        self,
        addresses: list,
        seed_address: str = "United Kingdom",
        seed_name: str = "Test Identity",
        seed_dob: str = "1990-01-01"
    ) -> Dict[str, Any]:
        """
        Validate a list of addresses using the validator's grading function.
        
        Args:
            addresses: List of address strings to validate
            seed_address: The seed address (country/region) to match against
            seed_name: The seed name (for formatting variations)
            seed_dob: The seed date of birth (for formatting variations)
        
        Returns:
            Dictionary containing validation results and final score
        """
        
        print("="*80)
        print("MOCK VALIDATOR - ADDRESS VALIDATION")
        print("="*80)
        print(f"\n📋 Validating {len(addresses)} addresses")
        print(f"🌍 Seed Address: {seed_address}")
        print(f"👤 Seed Name: {seed_name}")
        print(f"📅 Seed DOB: {seed_dob}")
        print(f"🔢 Validator UID: {self.validator_uid}")
        print(f"⛏️  Miner UID: {self.miner_uid}")
        print("\n" + "-"*80)
        
        # Format addresses as variations (matching validator's expected format)
        # Format: {name: [[name_var, dob_var, address_var], ...]}
        variations = {
            seed_name: [
                [seed_name, seed_dob, addr] for addr in addresses
            ]
        }
        
        # Seed addresses (one per name in variations)
        seed_addresses = [seed_address]
        
        # Miner metrics (empty dict for mock)
        miner_metrics = {}
        
        print("🔄 Calling _grade_address_variations...")
        print("-"*80)
        
        # Call the validator's grading function
        result = _grade_address_variations(
            variations=variations,
            seed_addresses=seed_addresses,
            miner_metrics=miner_metrics,
            validator_uid=self.validator_uid,
            miner_uid=self.miner_uid
        )
        
        return result
    
    def display_results(self, result: Dict[str, Any], addresses: list):
        """Display validation results in a formatted way"""
        
        print("\n" + "="*80)
        print("VALIDATION RESULTS")
        print("="*80)
        
        # Extract key metrics
        overall_score = result.get('overall_score', 0.0)
        heuristic_perfect = result.get('heuristic_perfect', False)
        region_matches = result.get('region_matches', 0)
        total_addresses = result.get('total_addresses', len(addresses))
        api_result = result.get('api_result', 'UNKNOWN')
        
        # Extract detailed breakdown
        detailed_breakdown = result.get('detailed_breakdown', {})
        api_validation = detailed_breakdown.get('api_validation', {})
        
        # Display summary
        print(f"\n📊 FINAL ADDRESS SCORE: {overall_score:.4f}")
        print(f"   (This is the score that would be used by the validator)")
        print()
        print(f"✅ Heuristic Check: {'PASSED' if heuristic_perfect else 'FAILED'}")
        print(f"🌍 Region Matches: {region_matches}/{total_addresses}")
        print(f"🔍 API Validation: {api_result}")
        
        # Display API validation details
        if api_validation:
            print(f"\n📡 API Validation Details:")
            print(f"   Total eligible addresses: {api_validation.get('total_eligible_addresses', 0)}")
            print(f"   API calls made: {api_validation.get('total_calls', 0)}")
            print(f"   Successful calls: {api_validation.get('total_successful_calls', 0)}")
            print(f"   Timeout calls: {api_validation.get('total_timeout_calls', 0)}")
            print(f"   Failed calls: {api_validation.get('total_failed_calls', 0)}")
            
            # Show individual API attempts
            api_attempts = api_validation.get('api_attempts', [])
            if api_attempts:
                print(f"\n   Individual API Results:")
                for i, attempt in enumerate(api_attempts, 1):
                    addr = attempt.get('address', 'N/A')
                    result_val = attempt.get('result', 'N/A')
                    score_details = attempt.get('score_details', {}) or {}
                    
                    if isinstance(result_val, (int, float)):
                        area = score_details.get('min_area', 'N/A') if score_details else 'N/A'
                        status = "✅" if result_val >= 0.99 else "❌"
                        print(f"   {status} [{i}] {addr[:60]}...")
                        print(f"        Score: {result_val:.4f}, Area: {area} m²")
                    elif result_val == "TIMEOUT":
                        print(f"   ⏱️  [{i}] {addr[:60]}... (TIMEOUT)")
                    else:
                        print(f"   ❌ [{i}] {addr[:60]}... (FAILED)")
        
        # Score interpretation
        print("\n" + "-"*80)
        print("SCORE INTERPRETATION:")
        if overall_score >= 0.99:
            print("   ✅ EXCELLENT: Score >= 0.99 (Perfect)")
        elif overall_score >= 0.8:
            print("   ⚠️  GOOD: Score >= 0.8 (Acceptable)")
        elif overall_score >= 0.3:
            print("   ⚠️  POOR: Score >= 0.3 (Minimum threshold)")
        else:
            print("   ❌ FAILED: Score < 0.3 (Rejected)")
        print("="*80)
        
        return overall_score


def main():
    """Main function to run the mock validator"""
    
    # Create mock validator
    validator = MockValidator(validator_uid=101, miner_uid=501)
    
    # Validate addresses
    result = validator.validate_addresses(
        addresses=MANCHESTER_ADDRESSES,
        seed_address="United Kingdom",
        seed_name="Test Identity",
        seed_dob="1990-01-01"
    )
    
    # Display results
    final_score = validator.display_results(result, MANCHESTER_ADDRESSES)
    
    # Save results to JSON file
    output_file = "validator_address_results.json"
    with open(output_file, 'w') as f:
        json.dump({
            "final_score": final_score,
            "addresses": MANCHESTER_ADDRESSES,
            "validation_result": result
        }, f, indent=2)
    
    print(f"\n💾 Results saved to: {output_file}")
    print(f"\n🎯 Final Address Score: {final_score:.4f}")
    
    return final_score


if __name__ == "__main__":
    main()

