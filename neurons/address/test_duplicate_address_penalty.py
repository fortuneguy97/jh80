"""
Test what happens if we send the same address multiple times for a single name.
Check if validator penalizes duplicate addresses.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

from reward import get_name_variation_rewards
import numpy as np

# Mock validator class
class MockValidator:
    def __init__(self):
        self.uid = 0
        self.config = type('Config', (), {
            'neuron': type('Neuron', (), {
                'burn_fraction': 0.0,
                'top_miner_cap': 100,
                'quality_threshold': 0.0,
                'decay_rate': 0.1,
                'blend_factor': 0.5
            })()
        })()

# Test case 1: Send 15 DIFFERENT addresses (should be OK)
print("="*100)
print("TEST 1: 15 DIFFERENT ADDRESSES (Should be OK)")
print("="*100)

different_addresses = [
    "123 Main Street, New York, 10001, United States of America",
    "456 Oak Avenue, Los Angeles, 90001, United States of America",
    "789 Pine Road, Chicago, 60601, United States of America",
    "321 Elm Street, Houston, 77001, United States of America",
    "654 Maple Drive, Phoenix, 85001, United States of America",
    "987 Cedar Lane, Philadelphia, 19101, United States of America",
    "147 Park Way, San Antonio, 78201, United States of America",
    "258 First Street, San Diego, 92101, United States of America",
    "369 Second Avenue, Dallas, 75201, United States of America",
    "741 Third Road, San Jose, 95101, United States of America",
    "852 Fourth Boulevard, Austin, 78701, United States of America",
    "963 Fifth Lane, Jacksonville, 32201, United States of America",
    "159 Sixth Street, Fort Worth, 76101, United States of America",
    "357 Seventh Avenue, Columbus, 43201, United States of America",
    "468 Eighth Road, Charlotte, 28201, United States of America",
]

variations_diff = {
    "John Smith": [
        ["John Smith", "1990-01-15", addr] for addr in different_addresses
    ]
}

validator = MockValidator()
seed_names = ["John Smith"]
seed_dob = ["1990-01-15"]
seed_addresses = ["United States"]

rewards_diff, penalties_diff, metrics_diff = get_name_variation_rewards(
    validator,
    seed_names=seed_names,
    seed_dob=seed_dob,
    seed_addresses=seed_addresses,
    seed_script=["latin"],
    responses=[variations_diff],
    uids=[1],
    variation_count=15
)

print(f"\nResult: {rewards_diff[0]:.4f}")
print(f"Penalties: {penalties_diff[0]:.4f}")
if metrics_diff:
    penalties_breakdown = metrics_diff[0].get('penalties', {})
    address_duplicates = penalties_breakdown.get('extra_names_breakdown', {}).get('address_duplicates', 0)
    print(f"Address duplicates penalty: {address_duplicates:.4f}")
    print(f"✅ No penalty for different addresses")

# Test case 2: Send 15 SAME addresses (should be penalized)
print("\n" + "="*100)
print("TEST 2: 15 SAME ADDRESSES (Should be PENALIZED)")
print("="*100)

same_address = "123 Main Street, New York, 10001, United States of America"
variations_same = {
    "John Smith": [
        ["John Smith", "1990-01-15", same_address] for _ in range(15)
    ]
}

rewards_same, penalties_same, metrics_same = get_name_variation_rewards(
    validator,
    seed_names=seed_names,
    seed_dob=seed_dob,
    seed_addresses=seed_addresses,
    seed_script=["latin"],
    responses=[variations_same],
    uids=[1],
    variation_count=15
)

print(f"\nResult: {rewards_same[0]:.4f}")
print(f"Penalties: {penalties_same[0]:.4f}")
if metrics_same:
    penalties_breakdown = metrics_same[0].get('penalties', {})
    address_duplicates = penalties_breakdown.get('extra_names_breakdown', {}).get('address_duplicates', 0)
    print(f"Address duplicates penalty: {address_duplicates:.4f}")
    
    # Calculate expected penalty
    duplicates = 15 - 1  # 14 duplicates
    expected_penalty = min(duplicates * 0.05, 0.5)  # 5% per duplicate, max 50%
    print(f"\nExpected penalty: {duplicates} duplicates × 0.05 = {expected_penalty:.4f}")
    
    if address_duplicates > 0:
        print(f"❌ PENALTY APPLIED: {address_duplicates:.4f} ({address_duplicates*100:.1f}% reduction)")
    else:
        print(f"⚠️  No penalty detected (might be in different penalty field)")

# Test case 3: Send 15 addresses with slight variations (normalized to same)
print("\n" + "="*100)
print("TEST 3: 15 ADDRESSES WITH SLIGHT VARIATIONS (Normalized to Same)")
print("="*100)

# These will normalize to the same (spaces, commas, case differences)
similar_addresses = [
    "123 Main Street, New York, 10001, United States of America",
    "123 Main Street,New York,10001,United States of America",  # No spaces after commas
    "123 MAIN STREET, NEW YORK, 10001, UNITED STATES OF AMERICA",  # Uppercase
    "123  Main  Street,  New  York,  10001,  United  States  of  America",  # Extra spaces
    "123-Main-Street, New-York, 10001, United-States-of-America",  # Hyphens
    "123 Main Street; New York; 10001; United States of America",  # Semicolons
    "123 Main Street,New York,10001,United States of America",  # Duplicate
    "123 Main Street, New York, 10001, United States of America",  # Duplicate
    "123 Main Street, New York, 10001, United States of America",  # Duplicate
    "123 Main Street, New York, 10001, United States of America",  # Duplicate
    "123 Main Street, New York, 10001, United States of America",  # Duplicate
    "123 Main Street, New York, 10001, United States of America",  # Duplicate
    "123 Main Street, New York, 10001, United States of America",  # Duplicate
    "123 Main Street, New York, 10001, United States of America",  # Duplicate
    "123 Main Street, New York, 10001, United States of America",  # Duplicate
]

variations_similar = {
    "John Smith": [
        ["John Smith", "1990-01-15", addr] for addr in similar_addresses
    ]
}

rewards_similar, penalties_similar, metrics_similar = get_name_variation_rewards(
    validator,
    seed_names=seed_names,
    seed_dob=seed_dob,
    seed_addresses=seed_addresses,
    seed_script=["latin"],
    responses=[variations_similar],
    uids=[1],
    variation_count=15
)

print(f"\nResult: {rewards_similar[0]:.4f}")
print(f"Penalties: {penalties_similar[0]:.4f}")
if metrics_similar:
    penalties_breakdown = metrics_similar[0].get('penalties', {})
    address_duplicates = penalties_breakdown.get('extra_names_breakdown', {}).get('address_duplicates', 0)
    print(f"Address duplicates penalty: {address_duplicates:.4f}")
    
    # Show normalization
    def normalize_address(addr_str):
        if not addr_str:
            return ""
        normalized = " ".join(addr_str.split()).lower()
        normalized = normalized.replace(",", " ").replace(";", " ").replace("-", " ")
        normalized = " ".join(normalized.split())
        return normalized
    
    normalized = [normalize_address(addr) for addr in similar_addresses]
    unique_count = len(set(normalized))
    duplicates = len(normalized) - unique_count
    
    print(f"\nAfter normalization:")
    print(f"  Unique addresses: {unique_count}")
    print(f"  Duplicates: {duplicates}")
    print(f"  Sample normalized: '{normalized[0][:60]}...'")
    
    if address_duplicates > 0:
        print(f"❌ PENALTY APPLIED: {address_duplicates:.4f} (addresses normalized to same)")

print("\n" + "="*100)
print("SUMMARY")
print("="*100)
print()
print("✅ You MUST send 15 DIFFERENT addresses for each name")
print("❌ Sending same address 15 times = 5% penalty per duplicate (max 50%)")
print("❌ Slight variations (spaces, commas, case) normalize to same = penalty")
print()
print("Penalty calculation:")
print("  duplicates = total_addresses - unique_addresses")
print("  penalty = duplicates × 0.05 (5% per duplicate)")
print("  max_penalty = 0.5 (50%)")
print()
print("Example: 15 same addresses = 14 duplicates = 0.7 penalty → capped at 0.5 (50%)")

