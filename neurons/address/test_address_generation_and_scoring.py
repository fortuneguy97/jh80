#!/usr/bin/env python3
"""
Generate 15 addresses for a country (with house number requirement) 
and test them with rewards.py to verify they all score 1.0.
"""

import json
import sys
import os

# Add MIID to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID'))

from generate_address_cache import generate_addresses_for_country
from validator.reward import _grade_address_variations

# Mock validator and miner objects
class MockValidator:
    def __init__(self):
        self.uid = 0

class MockMiner:
    def __init__(self):
        self.uid = 0

validator = MockValidator()
miner = MockMiner()

# Test countries (previously failing ones)
test_countries = ['Philippines', 'Russia', 'Afghanistan', 'Albania']

print("=" * 80)
print("GENERATE ADDRESSES AND TEST WITH REWARDS.PY")
print("=" * 80)
print(f"Testing {len(test_countries)} countries")
print("=" * 80)

all_results = []

for country in test_countries:
    print(f"\n{'='*80}")
    print(f"📍 COUNTRY: {country}")
    print(f"{'='*80}")
    
    # Step 1: Generate 15 addresses
    print(f"\n🔄 Step 1: Generating 15 addresses for {country}...")
    print("-" * 80)
    
    try:
        addresses = generate_addresses_for_country(country, per_country=15, verbose=True)
        
        if len(addresses) < 15:
            print(f"\n⚠️  Only generated {len(addresses)}/15 addresses for {country}")
            print(f"   Skipping rewards.py test (need 15 addresses)")
            all_results.append({
                "country": country,
                "addresses_generated": len(addresses),
                "status": "INCOMPLETE",
                "overall_score": None
            })
            continue
        
        print(f"\n✅ Generated {len(addresses)} addresses for {country}")
        
        # Step 2: Test with rewards.py
        print(f"\n🔄 Step 2: Testing addresses with rewards.py...")
        print("-" * 80)
        
        # Create variations structure as validator expects
        test_name = "John Smith"
        variations = {
            test_name: [
                ["John Smith", "1990-01-01", addr] for addr in addresses[:15]
            ]
        }
        
        seed_addresses = [country]
        miner_metrics = {}
        
        result = _grade_address_variations(
            variations=variations,
            seed_addresses=seed_addresses,
            miner_metrics=miner_metrics,
            validator_uid=validator.uid,
            miner_uid=miner.uid
        )
        
        overall_score = result.get("overall_score", 0.0)
        detailed_breakdown = result.get("detailed_breakdown", {})
        
        # Calculate sub-scores
        validation_results = detailed_breakdown.get("validation_results", {}).get(test_name, [])
        total_addrs = len(validation_results)
        
        if total_addrs > 0:
            looks_like_count = sum(1 for r in validation_results if r.get("looks_like_address", False))
            region_match_count = sum(1 for r in validation_results if r.get("region_match", False))
            passed_count = sum(1 for r in validation_results if r.get("passed_validation", False))
            
            looks_like_address = looks_like_count / total_addrs
            region_match = region_match_count / total_addrs
        else:
            looks_like_address = 0.0
            region_match = 0.0
        
        # API call score
        api_validation = detailed_breakdown.get("api_validation", {})
        api_attempts = api_validation.get("api_attempts", [])
        if api_attempts:
            api_scores = []
            for attempt in api_attempts:
                result_val = attempt.get("result", 0.0)
                if isinstance(result_val, (int, float)) and result_val > 0:
                    api_scores.append(result_val)
                elif isinstance(result_val, dict) and "score" in result_val:
                    api_scores.append(result_val["score"])
            if api_scores:
                api_call = sum(api_scores) / len(api_scores)
            else:
                api_call = 0.0
        else:
            api_call = 0.0
        
        # Check if score is 1.0
        is_perfect = overall_score >= 0.99
        
        status = "✅ PERFECT" if is_perfect else "⚠️  NOT PERFECT"
        print(f"\n{status} Overall Score: {overall_score:.4f}")
        print(f"   - Looks Like Address: {looks_like_address:.4f} ({looks_like_count}/{total_addrs})")
        print(f"   - Region Match: {region_match:.4f} ({region_match_count}/{total_addrs})")
        print(f"   - API Call: {api_call:.4f} ({len(api_attempts)} addresses checked)")
        
        if api_attempts:
            print(f"\n   API Scores Detail:")
            for i, attempt in enumerate(api_attempts, 1):
                result_val = attempt.get("result", 0.0)
                if isinstance(result_val, dict):
                    score = result_val.get("score", 0.0)
                    area = result_val.get("min_area", "N/A")
                    print(f"     {i}. Score: {score:.4f}, Area: {area} m²")
                elif isinstance(result_val, (int, float)):
                    print(f"     {i}. Score: {result_val:.4f}")
                else:
                    print(f"     {i}. Result: {result_val}")
        
        all_results.append({
            "country": country,
            "addresses_generated": len(addresses),
            "overall_score": overall_score,
            "looks_like_address": looks_like_address,
            "region_match": region_match,
            "api_call": api_call,
            "is_perfect": is_perfect,
            "status": "PERFECT" if is_perfect else "NOT_PERFECT"
        })
        
    except Exception as e:
        import traceback
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        all_results.append({
            "country": country,
            "status": "ERROR",
            "error": str(e),
            "overall_score": None
        })

# Print final summary
print("\n" + "=" * 80)
print("FINAL SUMMARY")
print("=" * 80)

perfect_count = sum(1 for r in all_results if r.get("is_perfect", False))
total_count = len([r for r in all_results if r.get("overall_score") is not None])

print(f"\n✅ Perfect scores (1.0): {perfect_count}/{total_count}")
print(f"⚠️  Non-perfect scores: {total_count - perfect_count}/{total_count}")

print("\n" + "-" * 80)
print("DETAILED RESULTS:")
print("-" * 80)
for r in all_results:
    if r.get("status") == "ERROR":
        print(f"❌ {r['country']:20s} | ERROR: {r.get('error', 'Unknown')}")
    elif r.get("status") == "INCOMPLETE":
        print(f"⚠️  {r['country']:20s} | INCOMPLETE: {r['addresses_generated']}/15 addresses")
    else:
        status_icon = "✅" if r["is_perfect"] else "⚠️"
        print(f"{status_icon} {r['country']:20s} | "
              f"Score: {r['overall_score']:.4f} | "
              f"Looks: {r['looks_like_address']:.4f} | "
              f"Region: {r['region_match']:.4f} | "
              f"API: {r['api_call']:.4f}")

print("\n" + "=" * 80)
if perfect_count == total_count and total_count > 0:
    print("🎉 SUCCESS! All countries scored 1.0!")
    sys.exit(0)
else:
    print("⚠️  Some countries did not score 1.0")
    sys.exit(1)

