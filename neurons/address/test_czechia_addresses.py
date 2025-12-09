#!/usr/bin/env python3
"""
Test script to validate 15 Czechia addresses and check for duplicates
"""

import os
import sys
import json
import time
import requests

# Add MIID validator to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

from reward import (
    looks_like_address,
    check_with_nominatim,
    extract_city_country,
    validate_address_region
)
from cheat_detection import normalize_address_for_deduplication

# User-Agent for API calls
USER_AGENT = os.getenv("USER_AGENT", "MIIDSubnet/1.0 (contact: prasadpsd2001@gmail.com)")

# Test addresses (variations of second Afghanistan address: Seh Aqrab Road, Kabul, 1006, Afghanistan)
test_addresses = [
    # Group A — Adding "3rd District"
    "Seh Aqrab Road, 3rd District Kabul, 1006, Afghanistan",
    "Seh Aqrab Road, Kabul, 3rd District 1006, Afghanistan",
    "Seh Aqrab Road, 3rd District Kabul, 1009, Afghanistan",
    # Group B — Adding "Kabul District"
    "Seh Aqrab Road, Kabul District Kabul, 1006, Afghanistan",
    "Seh Aqrab Road, Kabul, Kabul District 1006, Afghanistan",
    "Seh Aqrab Road, Kabul District Kabul, 1004, Afghanistan",
    "Seh Aqrab Road, Kabul District Kabul, 1009, Afghanistan",
    # Group C — Adding "Kabul Province"
    "Seh Aqrab Road, Kabul Province Kabul, 1006, Afghanistan",
    "Seh Aqrab Road, Kabul, Kabul Province 1006, Afghanistan",
    "Seh Aqrab Road, Kabul Province Kabul, 1009, Afghanistan",
    # Group D — Adding "Nahri Darsan"
    "Seh Aqrab Road, Nahri Darsan Kabul, 1006, Afghanistan",
    "Seh Aqrab Road, Kabul, Nahri Darsan 1006, Afghanistan",
    "Seh Aqrab Road, Nahri Darsan Kabul, 1004, Afghanistan",
    # Group E — Using Valid Postcode Variants
    "Seh Aqrab Road, Kabul, 1004, Afghanistan",
    "Seh Aqrab Road, Kabul, 1009, Afghanistan"
]

seed_address = "Seh Aqrab Road, Kabul, 1006, Afghanistan"
seed_name = "Test Name"

def test_all_addresses():
    results = []
    normalized_addresses = {}
    duplicate_groups = {}
    
    print("=" * 80)
    print("TESTING 15 CZECHIA ADDRESSES")
    print("=" * 80)
    print()
    
    for i, address in enumerate(test_addresses, 1):
        print(f"Testing Address {i}: {address}")
        print("-" * 80)
        
        result = {
            "index": i,
            "address": address,
            "looks_like_address": False,
            "nominatim_score": None,
            "nominatim_result": None,
            "normalized": None,
            "is_duplicate": False,
            "duplicate_group": None,
            "status": "FAILED"
        }
        
        # Step 1: Check if it looks like an address
        try:
            looks_valid = looks_like_address(address)
            result["looks_like_address"] = looks_valid
            print(f"  ✓ looks_like_address: {looks_valid}")
            
            if not looks_valid:
                print(f"  ✗ FAILED: Does not look like an address")
                results.append(result)
                print()
                continue
        except Exception as e:
            print(f"  ✗ ERROR in looks_like_address: {e}")
            results.append(result)
            print()
            continue
        
        # Step 2: Normalize for deduplication
        try:
            normalized = normalize_address_for_deduplication(address)
            result["normalized"] = normalized
            print(f"  ✓ Normalized: {normalized}")
            
            # Check for duplicates
            if normalized in normalized_addresses:
                # Found duplicate
                duplicate_index = normalized_addresses[normalized]
                result["is_duplicate"] = True
                result["duplicate_group"] = duplicate_index
                
                # Add to duplicate groups
                if duplicate_index not in duplicate_groups:
                    duplicate_groups[duplicate_index] = [duplicate_index]
                duplicate_groups[duplicate_index].append(i)
                
                print(f"  ⚠ DUPLICATE: Same normalized address as Address {duplicate_index}")
            else:
                normalized_addresses[normalized] = i
                print(f"  ✓ UNIQUE normalized address")
        except Exception as e:
            print(f"  ✗ ERROR in normalization: {e}")
            results.append(result)
            print()
            continue
        
        # Step 3: Check with Nominatim API (with detailed logging)
        try:
            print(f"  → Checking with Nominatim API...")
            
            # Add 1 second sleep before Nominatim call (except for first address)
            if i > 1:
                print(f"  ⏳ Waiting 1 second before API call (rate limiting)...")
                time.sleep(1.0)
            
            # Make direct API call for detailed logging
            url = "https://nominatim.openstreetmap.org/search"
            params = {"q": address, "format": "json"}
            user_agent = os.getenv("USER_AGENT", "MIIDSubnet/1.0 (contact: prasadpsd2001@gmail.com)")
            
            print(f"  → Request URL: {url}")
            print(f"  → Query: {address}")
            print(f"  → User-Agent: {user_agent}")
            
            response = requests.get(url, params=params, headers={"User-Agent": user_agent}, timeout=10)
            
            print(f"  → HTTP Status: {response.status_code}")
            
            if response.status_code != 200:
                if response.status_code == 403:
                    print(f"  ✗ 403 Forbidden - Rate limited or blocked")
                    result["nominatim_result"] = "403_FORBIDDEN"
                    result["status"] = "FAILED"
                elif response.status_code == 429:
                    print(f"  ✗ 429 Too Many Requests - Rate limited")
                    result["nominatim_result"] = "429_RATE_LIMIT"
                    result["status"] = "FAILED"
                else:
                    print(f"  ✗ HTTP {response.status_code} - {response.text[:200]}")
                    result["nominatim_result"] = f"HTTP_{response.status_code}"
                    result["status"] = "FAILED"
            else:
                try:
                    results = response.json()
                    print(f"  → Total results from Nominatim: {len(results)}")
                    
                    if len(results) == 0:
                        print(f"  ✗ FAILED: No results found for address")
                        result["nominatim_result"] = "NO_RESULTS"
                        result["status"] = "FAILED"
                    else:
                        # Show first few results
                        print(f"  → First result: {results[0].get('display_name', 'N/A')[:100]}")
                        print(f"  → First result place_rank: {results[0].get('place_rank', 'N/A')}")
                        
                        # Extract numbers from original address
                        import re
                        original_numbers = set(re.findall(r"[0-9]+", address.lower()))
                        print(f"  → Numbers in address: {original_numbers}")
                        
                        # Filter results
                        filtered_results = []
                        for idx, result_item in enumerate(results):
                            place_rank = result_item.get('place_rank', 0)
                            name = result_item.get('name', '')
                            display_name = result_item.get('display_name', '')
                            
                            if place_rank < 20:
                                print(f"    Result {idx+1}: place_rank {place_rank} < 20 (filtered out)")
                                continue
                            
                            if name and name.lower() not in address.lower():
                                print(f"    Result {idx+1}: name '{name}' not in address (filtered out)")
                                continue
                            
                            display_numbers = set(re.findall(r"[0-9]+", display_name.lower()))
                            if original_numbers and display_numbers and not display_numbers.issubset(original_numbers):
                                print(f"    Result {idx+1}: numbers mismatch (filtered out)")
                                continue
                            
                            filtered_results.append(result_item)
                            print(f"    Result {idx+1}: ✓ PASSED filters (place_rank={place_rank})")
                        
                        print(f"  → Filtered results: {len(filtered_results)}")
                        
                        if len(filtered_results) == 0:
                            print(f"  ✗ FAILED: No results passed filters (place_rank >= 20, name match, number match)")
                            result["nominatim_result"] = "NO_FILTERED_RESULTS"
                            result["status"] = "FAILED"
                        else:
                            # Calculate score using check_with_nominatim
                            nominatim_result = check_with_nominatim(
                                address=address,
                                validator_uid=1,
                                miner_uid=1,
                                seed_address=seed_address,
                                seed_name=seed_name
                            )
                            
                            if isinstance(nominatim_result, dict):
                                score = nominatim_result.get("score", 0.0)
                                details = nominatim_result.get("details", {})
                                min_area = details.get("min_area_m2", "N/A")
                                
                                result["nominatim_score"] = score
                                result["nominatim_result"] = nominatim_result
                                print(f"  ✓ Nominatim score: {score}")
                                print(f"  → Min bounding box area: {min_area} m²")
                                
                                if score >= 0.9:
                                    result["status"] = "PASSED"
                                    print(f"  ✅ PASSED (score: {score})")
                                else:
                                    result["status"] = "FAILED"
                                    print(f"  ✗ FAILED (score: {score} < 0.9)")
                            elif nominatim_result == "TIMEOUT":
                                result["nominatim_result"] = "TIMEOUT"
                                result["status"] = "TIMEOUT"
                                print(f"  ⏱ TIMEOUT")
                            else:
                                result["nominatim_score"] = 0.0
                                result["status"] = "FAILED"
                                print(f"  ✗ FAILED: Geocoding failed (returned {type(nominatim_result)})")
                except json.JSONDecodeError as e:
                    print(f"  ✗ ERROR: Invalid JSON response: {e}")
                    print(f"  → Response text: {response.text[:500]}")
                    result["nominatim_result"] = "JSON_ERROR"
                    result["status"] = "FAILED"
                except Exception as e:
                    print(f"  ✗ ERROR processing response: {e}")
                    result["nominatim_result"] = f"ERROR: {str(e)}"
                    result["status"] = "FAILED"
        except requests.exceptions.Timeout:
            print(f"  ✗ TIMEOUT: Request timed out after 10 seconds")
            result["nominatim_result"] = "TIMEOUT"
            result["status"] = "TIMEOUT"
        except Exception as e:
            print(f"  ✗ ERROR in Nominatim check: {e}")
            import traceback
            print(f"  → Traceback: {traceback.format_exc()}")
            result["status"] = "ERROR"
        
        results.append(result)
        print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    
    passed = [r for r in results if r["status"] == "PASSED"]
    failed = [r for r in results if r["status"] == "FAILED"]
    timeout = [r for r in results if r["status"] == "TIMEOUT"]
    errors = [r for r in results if r["status"] == "ERROR"]
    duplicates = [r for r in results if r["is_duplicate"]]
    unique = [r for r in results if not r["is_duplicate"]]
    
    print(f"Total addresses: {len(results)}")
    print(f"  ✅ Passed (score >= 0.9): {len(passed)}")
    print(f"  ✗ Failed (score < 0.9): {len(failed)}")
    print(f"  ⏱ Timeout: {len(timeout)}")
    print(f"  ❌ Errors: {len(errors)}")
    print()
    print(f"Unique normalized addresses: {len(unique)}")
    print(f"Duplicate normalized addresses: {len(duplicates)}")
    print()
    
    # Passed addresses
    if passed:
        print("✅ PASSED ADDRESSES:")
        for r in passed:
            dup_info = f" (DUPLICATE of #{r['duplicate_group']})" if r["is_duplicate"] else " (UNIQUE)"
            print(f"  {r['index']:2d}. {r['address']}")
            print(f"      Score: {r['nominatim_score']:.2f}, Normalized: {r['normalized']}{dup_info}")
        print()
    
    # Failed addresses
    if failed:
        print("✗ FAILED ADDRESSES:")
        for r in failed:
            score_info = f" (score: {r['nominatim_score']:.2f})" if r['nominatim_score'] is not None else ""
            print(f"  {r['index']:2d}. {r['address']}{score_info}")
        print()
    
    # Duplicate groups
    if duplicate_groups:
        print("⚠ DUPLICATE GROUPS:")
        for group_id, indices in duplicate_groups.items():
            print(f"  Group {group_id}: Addresses {', '.join(map(str, indices))}")
            for idx in indices:
                if idx <= len(results):
                    r = results[idx - 1]
                    print(f"    #{idx}: {r['address']}")
                    print(f"         Normalized: {r['normalized']}")
        print()
    
    # Unique addresses that passed
    unique_passed = [r for r in passed if not r["is_duplicate"]]
    if unique_passed:
        print(f"✅ UNIQUE PASSED ADDRESSES ({len(unique_passed)}):")
        for r in unique_passed:
            print(f"  {r['index']:2d}. {r['address']}")
            print(f"      Score: {r['nominatim_score']:.2f}, Normalized: {r['normalized']}")
        print()
    
    return results, duplicate_groups

if __name__ == "__main__":
    test_all_addresses()

