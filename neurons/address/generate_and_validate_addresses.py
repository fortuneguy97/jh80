#!/usr/bin/env python3
"""
Generate addresses exactly like Poland (with house numbers) for other countries
and validate with rewards.py to ensure score 1.0.
"""

import json
import sys
import os
import time

# Add MIID to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID'))

from generate_address_cache import generate_addresses_for_country
from validator.reward import _grade_address_variations, validate_address_region, looks_like_address, check_with_nominatim

# Mock validator and miner objects
class MockValidator:
    def __init__(self):
        self.uid = 0

class MockMiner:
    def __init__(self):
        self.uid = 0

validator = MockValidator()
miner = MockMiner()

# Test countries (previously failing ones) - start with one for testing
test_countries = ['Philippines']  # Start with one country for faster testing

print("=" * 80)
print("GENERATE ADDRESSES (POLAND-STYLE) AND VALIDATE WITH REWARDS.PY")
print("=" * 80)
print(f"Strategy: Generate addresses with house numbers (like Poland)")
print(f"Then validate each step: heuristic → region → API → rewards.py")
print(f"Testing {len(test_countries)} country(ies): {', '.join(test_countries)}")
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
        print(f"  ⏳ Starting address generation for {country}...")
        print(f"  📍 This may take 1-2 minutes (Overpass API + Nominatim reverse geocoding)...")
        sys.stdout.flush()  # Force output
        
        addresses = generate_addresses_for_country(country, per_country=15, verbose=True)
        
        sys.stdout.flush()  # Force output after generation
        
        if len(addresses) < 15:
            print(f"\n⚠️  Only generated {len(addresses)}/15 addresses for {country}")
            all_results.append({
                "country": country,
                "addresses_generated": len(addresses),
                "status": "INCOMPLETE",
                "overall_score": None
            })
            continue
        
        print(f"\n✅ Generated {len(addresses)} addresses for {country}")
        
        # Step 2: Validate each address individually (like Poland)
        print(f"\n🔄 Step 2: Validating each address individually...")
        print("-" * 80)
        sys.stdout.flush()
        
        validated_addresses = []
        for i, addr in enumerate(addresses[:15], 1):
            sys.stdout.flush()  # Force output for each address
            print(f"\n  Address {i}/15: {addr[:70]}...")
            
            # Check 1: Looks like address
            looks = looks_like_address(addr)
            print(f"    ✅ Looks Like Address: {looks}")
            if not looks:
                print(f"    ❌ FAILED: Does not look like address")
                continue
            
            # Check 2: Region validation
            region = validate_address_region(addr, country)
            print(f"    ✅ Region Match: {region}")
            if not region:
                print(f"    ❌ FAILED: Region validation failed")
                continue
            
            # Check 3: API validation (test one to see if it's found)
            if i <= 3:  # Test first 3 with API
                print(f"    🔄 Testing with Nominatim API...")
                sys.stdout.flush()
                api_result = check_with_nominatim(addr, validator.uid, miner.uid, country, 'Test')
                sys.stdout.flush()
                if isinstance(api_result, dict):
                    score = api_result.get('score', 0)
                    area = api_result.get('min_area', 0)
                    print(f"    ✅ API Score: {score:.4f}, Area: {area:.2f} m²")
                    if score < 0.9:
                        print(f"    ⚠️  WARNING: API score is {score:.4f} (not 1.0)")
                elif isinstance(api_result, (int, float)):
                    print(f"    ⚠️  API Score: {api_result:.4f}")
                else:
                    print(f"    ⚠️  API Result: {api_result}")
            
            validated_addresses.append(addr)
            print(f"    ✅ VALIDATED: Address {i} passed all checks")
        
        if len(validated_addresses) < 15:
            print(f"\n⚠️  Only {len(validated_addresses)}/15 addresses passed validation")
            all_results.append({
                "country": country,
                "addresses_generated": len(addresses),
                "validated_addresses": len(validated_addresses),
                "status": "PARTIAL_VALIDATION",
                "overall_score": None
            })
            continue
        
        # Step 3: Test with rewards.py
        print(f"\n🔄 Step 3: Testing all 15 addresses with rewards.py...")
        print("-" * 80)
        
        test_name = "John Smith"
        variations = {
            test_name: [
                ["John Smith", "1990-01-01", addr] for addr in validated_addresses[:15]
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
            
            looks_like_address_score = looks_like_count / total_addrs
            region_match_score = region_match_count / total_addrs
        else:
            looks_like_address_score = 0.0
            region_match_score = 0.0
        
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
                api_call_score = sum(api_scores) / len(api_scores)
            else:
                api_call_score = 0.0
        else:
            api_call_score = 0.0
        
        # Check if score is 1.0
        is_perfect = overall_score >= 0.99
        
        status = "✅ PERFECT" if is_perfect else "⚠️  NOT PERFECT"
        print(f"\n{status} Overall Score: {overall_score:.4f}")
        print(f"   - Looks Like Address: {looks_like_address_score:.4f} ({looks_like_count}/{total_addrs})")
        print(f"   - Region Match: {region_match_score:.4f} ({region_match_count}/{total_addrs})")
        print(f"   - API Call: {api_call_score:.4f} ({len(api_attempts)} addresses checked)")
        
        if api_attempts:
            print(f"\n   📊 API Scores Detail:")
            for i, attempt in enumerate(api_attempts, 1):
                result_val = attempt.get("result", 0.0)
                addr = attempt.get("address", "")[:50]
                if isinstance(result_val, dict):
                    score = result_val.get("score", 0.0)
                    area = result_val.get("min_area", "N/A")
                    print(f"     {i}. {addr}... → Score: {score:.4f}, Area: {area} m²")
                elif isinstance(result_val, (int, float)):
                    print(f"     {i}. {addr}... → Score: {result_val:.4f}")
                else:
                    print(f"     {i}. {addr}... → Result: {result_val}")
        
        # Show failed addresses if any
        if region_match_count < total_addrs:
            print(f"\n   ❌ Failed Region Validation ({total_addrs - region_match_count} addresses):")
            for r in validation_results:
                if not r.get("region_match", False):
                    print(f"     - {r.get('address', '')[:60]}...")
        
        all_results.append({
            "country": country,
            "addresses_generated": len(addresses),
            "validated_addresses": len(validated_addresses),
            "overall_score": overall_score,
            "looks_like_address": looks_like_address_score,
            "region_match": region_match_score,
            "api_call": api_call_score,
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
    elif r.get("status") == "PARTIAL_VALIDATION":
        print(f"⚠️  {r['country']:20s} | PARTIAL: {r['validated_addresses']}/15 validated")
    else:
        status_icon = "✅" if r["is_perfect"] else "⚠️"
        print(f"{status_icon} {r['country']:20s} | "
              f"Score: {r['overall_score']:.4f} | "
              f"Looks: {r['looks_like_address']:.4f} | "
              f"Region: {r['region_match']:.4f} | "
              f"API: {r['api_call']:.4f}")

print("=" * 80)

if perfect_count == total_count and total_count > 0:
    print("\n🎉 SUCCESS! All countries scored 1.0!")
    sys.exit(0)
else:
    print("\n⚠️  Some countries did not score 1.0")
    sys.exit(1)

