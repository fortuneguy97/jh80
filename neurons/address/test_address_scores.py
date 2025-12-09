#!/usr/bin/env python3
"""
Test if addresses from cache all get score 1.0 when sent to rewards.py
Sends 15 addresses at once for a name and checks the scores.
"""

import json
import sys
import os

# Add MIID to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID'))

from validator.reward import _grade_address_variations

# Load address cache
with open('address_cache.json', 'r') as f:
    cache_data = json.load(f)

addresses_by_country = cache_data.get('addresses', {})

# Test with multiple countries
test_countries = list(addresses_by_country.keys())[:10]  # Test first 10 countries

print("=" * 80)
print("TESTING ADDRESS SCORES FROM CACHE")
print("=" * 80)
print(f"Testing {len(test_countries)} countries")
print("=" * 80)

# Mock validator and miner objects
class MockValidator:
    def __init__(self):
        self.uid = 0

class MockMiner:
    def __init__(self):
        self.uid = 0

validator = MockValidator()
miner = MockMiner()

all_passed = True
results_summary = []

for country in test_countries:
    country_addresses = addresses_by_country[country]
    
    if len(country_addresses) < 15:
        print(f"\n⚠️  {country}: Only {len(country_addresses)} addresses (need 15)")
        continue
    
    # Take first 15 addresses
    test_addresses = country_addresses[:15]
    
    # Create variations structure as validator expects
    # Format: {name: [[name_var, dob_var, address_var], ...]}
    test_name = "John Smith"  # Dummy name for testing
    variations = {
        test_name: [
            ["John Smith", "1990-01-01", addr] for addr in test_addresses
        ]
    }
    
    # Seed address is the country name
    seed_addresses = [country]
    
    # Mock miner_metrics
    miner_metrics = {}
    
    print(f"\n📍 Testing {country} ({len(test_addresses)} addresses)...")
    
    try:
        # Call the grading function
        result = _grade_address_variations(
            variations=variations,
            seed_addresses=seed_addresses,
            miner_metrics=miner_metrics,
            validator_uid=validator.uid,
            miner_uid=miner.uid
        )
        
        overall_score = result.get("overall_score", 0.0)
        detailed_breakdown = result.get("detailed_breakdown", {})
        
        # Calculate sub-scores from validation results
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
        
        # API call score from api_validation
        api_validation = detailed_breakdown.get("api_validation", {})
        api_attempts = api_validation.get("api_attempts", [])
        if api_attempts:
            # Extract scores from api_attempts
            api_scores = []
            for attempt in api_attempts:
                result = attempt.get("result", 0.0)
                if isinstance(result, (int, float)) and result > 0:
                    api_scores.append(result)
                elif isinstance(result, dict) and "score" in result:
                    api_scores.append(result["score"])
            if api_scores:
                api_call = sum(api_scores) / len(api_scores)
            else:
                api_call = 0.0
        else:
            api_call = 0.0
        
        # Check if score is 1.0
        is_perfect = overall_score >= 0.99  # Allow small floating point differences
        
        status = "✅" if is_perfect else "❌"
        print(f"   {status} Overall Score: {overall_score:.4f}")
        print(f"      - Looks Like Address: {looks_like_address:.4f}")
        print(f"      - Region Match: {region_match:.4f}")
        print(f"      - API Call: {api_call:.4f}")
        
        if not is_perfect:
            all_passed = False
            print(f"      ⚠️  Score is not 1.0!")
        
        results_summary.append({
            "country": country,
            "overall_score": overall_score,
            "looks_like_address": looks_like_address,
            "region_match": region_match,
            "api_call": api_call,
            "is_perfect": is_perfect
        })
        
    except Exception as e:
        import traceback
        print(f"   ❌ ERROR: {type(e).__name__}: {e}")
        print(f"   Traceback: {traceback.format_exc()}")
        all_passed = False
        results_summary.append({
            "country": country,
            "error": str(e),
            "is_perfect": False
        })

# Print summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

perfect_count = sum(1 for r in results_summary if r.get("is_perfect", False))
total_count = len(results_summary)

print(f"✅ Perfect scores (1.0): {perfect_count}/{total_count}")
print(f"❌ Non-perfect scores: {total_count - perfect_count}/{total_count}")

if perfect_count == total_count:
    print("\n🎉 ALL COUNTRIES SCORED 1.0!")
else:
    print("\n⚠️  Some countries did not score 1.0:")
    for r in results_summary:
        if not r.get("is_perfect", False):
            if "error" in r:
                print(f"   ❌ {r['country']}: ERROR - {r['error']}")
            else:
                print(f"   ⚠️  {r['country']}: {r['overall_score']:.4f} "
                      f"(looks: {r['looks_like_address']:.4f}, "
                      f"region: {r['region_match']:.4f}, "
                      f"api: {r['api_call']:.4f})")

print("\n" + "=" * 80)
print("DETAILED RESULTS")
print("=" * 80)
for r in results_summary:
    if "error" not in r:
        status = "✅" if r["is_perfect"] else "⚠️"
        print(f"{status} {r['country']:30s} | "
              f"Overall: {r['overall_score']:.4f} | "
              f"Looks: {r['looks_like_address']:.4f} | "
              f"Region: {r['region_match']:.4f} | "
              f"API: {r['api_call']:.4f}")

print("=" * 80)

if all_passed:
    print("\n✅ ALL TESTS PASSED - All addresses score 1.0!")
    sys.exit(0)
else:
    print("\n❌ SOME TESTS FAILED - Not all addresses score 1.0")
    sys.exit(1)

