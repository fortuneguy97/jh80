#!/usr/bin/env python3
"""
Quick test: Generate 5 addresses for Philippines and validate with rewards.py
Shows progress in real-time.
"""

import sys
import os

# Add MIID to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID'))

print("=" * 80)
print("QUICK TEST: Generate 5 addresses for Philippines")
print("=" * 80)
print("Starting...")
sys.stdout.flush()

try:
    from generate_address_cache import generate_addresses_for_country
    
    print("\n🔄 Calling generate_addresses_for_country('Philippines', per_country=5)...")
    sys.stdout.flush()
    
    addresses = generate_addresses_for_country('Philippines', per_country=5, verbose=True)
    
    print(f"\n✅ Generated {len(addresses)} addresses")
    sys.stdout.flush()
    
    for i, addr in enumerate(addresses, 1):
        print(f"{i}. {addr}")
        sys.stdout.flush()
    
    # Now test with rewards.py
    if len(addresses) >= 5:
        print("\n" + "=" * 80)
        print("Testing with rewards.py...")
        print("=" * 80)
        sys.stdout.flush()
        
        from validator.reward import _grade_address_variations
        
        class MockValidator:
            def __init__(self):
                self.uid = 0
        
        class MockMiner:
            def __init__(self):
                self.uid = 0
        
        validator = MockValidator()
        miner = MockMiner()
        
        variations = {
            'John Smith': [
                ['John Smith', '1990-01-01', addr] for addr in addresses[:5]
            ]
        }
        
        result = _grade_address_variations(
            variations=variations,
            seed_addresses=['Philippines'],
            miner_metrics={},
            validator_uid=validator.uid,
            miner_uid=miner.uid
        )
        
        score = result.get('overall_score', 0.0)
        print(f"\n✅ Overall Score: {score:.4f}")
        sys.stdout.flush()
        
        if score >= 0.99:
            print("🎉 SUCCESS! Score is 1.0!")
        else:
            print("⚠️  Score is not 1.0")
            
except Exception as e:
    import traceback
    print(f"\n❌ ERROR: {type(e).__name__}: {e}")
    print(f"Traceback: {traceback.format_exc()}")
    sys.stdout.flush()

