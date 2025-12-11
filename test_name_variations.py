#!/usr/bin/env python3
"""
Simple test for name variation generation without bittensor dependency.
"""

import sys
import os

# Mock bittensor logging
class MockBT:
    class logging:
        @staticmethod
        def info(msg):
            print(f"INFO: {msg}")
        
        @staticmethod
        def debug(msg):
            print(f"DEBUG: {msg}")
        
        @staticmethod
        def warning(msg):
            print(f"WARNING: {msg}")

# Add mock to sys.modules
sys.modules['bittensor'] = MockBT()

# Now import our modules
from neurons.name.rule_based_variations import generate_rule_based_variations

def test_rule_based_variations():
    """Test rule-based variations."""
    print("Testing rule-based variations...")
    
    test_name = "John Smith"
    test_rules = ['swap_random_letter', 'delete_letter', 'replace_vowels']
    count = 5
    
    try:
        variations = generate_rule_based_variations(test_name, test_rules, count)
        print(f"✅ Generated {len(variations)} rule-based variations for '{test_name}':")
        for i, var in enumerate(variations, 1):
            print(f"  {i}. {var}")
        return True
    except Exception as e:
        print(f"❌ Error in rule-based variations: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_non_rule_based_fallback():
    """Test non-rule-based fallback variations."""
    print("\nTesting non-rule-based fallback variations...")
    
    # Import the fallback function
    from neurons.name.non_rule_based_variations import generate_phonetic_variations
    
    test_name = "John Smith"
    count = 3
    
    try:
        variations = generate_phonetic_variations(test_name, count)
        print(f"✅ Generated {len(variations)} phonetic variations for '{test_name}':")
        for i, var in enumerate(variations, 1):
            print(f"  {i}. {var}")
        return True
    except Exception as e:
        print(f"❌ Error in phonetic variations: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 Testing Name Variation Generation")
    print("=" * 50)
    
    success1 = test_rule_based_variations()
    success2 = test_non_rule_based_fallback()
    
    print("\n" + "=" * 50)
    if success1 and success2:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed!")