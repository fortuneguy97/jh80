#!/usr/bin/env python3
"""
Test Gemini-generated addresses with actual Nominatim API validation.
Checks if addresses will pass API validation and what scores they'll get.
"""

import os
import sys
import json
import requests
import time
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from MIID.validator.gemini_generator import generate_variations_with_gemini
from MIID.validator.reward import check_with_nominatim, compute_bounding_box_areas_meters
from MIID.protocol import IdentitySynapse

def test_address_with_api(address: str, seed_address: str, seed_name: str = "Test") -> dict:
    """Test a single address with Nominatim API."""
    result = {
        "address": address,
        "geocodable": False,
        "score": 0.0,
        "bounding_box_area": None,
        "place_rank": None,
        "api_result": None,
        "details": {}
    }
    
    try:
        # Call Nominatim API
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": address, "format": "json"}
        user_agent = "YanezCompliance/999 (https://yanezcompliance.com; omar@yanezcompliance.com)"
        
        response = requests.get(url, params=params, headers={"User-Agent": user_agent}, timeout=5)
        
        # Check response status
        if response.status_code != 200:
            result["api_result"] = f"HTTP_{response.status_code}"
            return result
        
        # Check content type
        content_type = response.headers.get('content-type', '')
        if 'application/json' not in content_type:
            result["api_result"] = f"INVALID_CONTENT_TYPE: {content_type}"
            return result
        
        try:
            results = response.json()
        except json.JSONDecodeError as e:
            result["api_result"] = f"JSON_ERROR: {str(e)}"
            result["details"]["response_text"] = response.text[:200]
            return result
        
        if len(results) == 0:
            result["api_result"] = "NO_RESULTS"
            return result
        
        # Extract numbers from original address
        original_numbers = set(re.findall(r"[0-9]+", address.lower()))
        
        # Filter results
        filtered_results = []
        for res in results:
            place_rank = res.get('place_rank', 0)
            if place_rank < 20:
                continue
            
            name = res.get('name', '')
            if name and name.lower() not in address.lower():
                continue
            
            display_name = res.get('display_name', '')
            if display_name:
                display_numbers = set(re.findall(r"[0-9]+", display_name.lower()))
                if original_numbers and display_numbers and not display_numbers.issubset(original_numbers):
                    continue
            
            filtered_results.append(res)
        
        if len(filtered_results) == 0:
            result["api_result"] = "FILTERED_OUT"
            return result
        
        # Calculate bounding box areas
        areas_data = compute_bounding_box_areas_meters(results)
        if len(areas_data) == 0:
            result["api_result"] = "NO_BOUNDING_BOX"
            return result
        
        areas = [item["area_m2"] for item in areas_data]
        min_area = min(areas)
        
        # Calculate score
        if min_area < 100:
            score = 1.0
        elif min_area < 1000:
            score = 0.9
        elif min_area < 10000:
            score = 0.8
        elif min_area < 100000:
            score = 0.7
        else:
            score = 0.3
        
        result["geocodable"] = True
        result["score"] = score
        result["bounding_box_area"] = min_area
        result["place_rank"] = filtered_results[0].get('place_rank', 0)
        result["api_result"] = "SUCCESS"
        result["details"] = {
            "num_results": len(results),
            "filtered_results": len(filtered_results),
            "min_area_m2": min_area,
            "all_areas": areas[:5]  # First 5 areas
        }
        
    except requests.exceptions.Timeout:
        result["api_result"] = "TIMEOUT"
    except Exception as e:
        result["api_result"] = f"ERROR: {str(e)}"
    
    return result

def main():
    """Test Gemini addresses with API validation."""
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not set")
        return
    
    # Generate addresses with Gemini
    synapse = IdentitySynapse(
        identity=[
            ["John Smith", "1990-05-15", "New York, USA"]
        ],
        query_template="Generate 5 variations of {name}. The following address is the seed country/city to generate address variations for: {address}. Generate unique real addresses within the specified country/city for each variation. The following date of birth is the seed DOB to generate variations for: {dob}.",
        timeout=360.0
    )
    
    print("="*80)
    print("Testing Gemini Addresses with Nominatim API Validation")
    print("="*80)
    
    print("\n🔄 Generating addresses with Gemini...")
    try:
        variations = generate_variations_with_gemini(
            synapse,
            gemini_api_key=api_key,
            gemini_model="gemini-2.0-flash-exp"
        )
    except Exception as e:
        print(f"❌ Generation failed: {e}")
        return
    
    print("✅ Generation complete\n")
    
    # Test each address
    for name, var_list in variations.items():
        if isinstance(var_list, dict):
            var_list = var_list.get('variations', [])
        
        print("="*80)
        print(f"Testing Addresses for: {name}")
        print("="*80)
        print(f"Total variations: {len(var_list)}\n")
        
        seed_address = "New York, USA"
        api_results = []
        
        # Test first 5 addresses
        for i, var in enumerate(var_list[:5], 1):
            address = var[2] if len(var) > 2 else ""
            if not address:
                continue
            
            print(f"📍 Testing Address {i}: {address}")
            result = test_address_with_api(address, seed_address, name)
            api_results.append(result)
            
            if result["api_result"] == "SUCCESS":
                print(f"   ✅ Geocodable: Yes")
                print(f"   📊 Score: {result['score']:.1f}")
                print(f"   📐 Bounding Box Area: {result['bounding_box_area']:.1f} m²")
                print(f"   🏆 Place Rank: {result['place_rank']}")
                print(f"   📍 Results: {result['details']['num_results']} total, {result['details']['filtered_results']} passed filters")
            elif result["api_result"] == "TIMEOUT":
                print(f"   ⏱️  API Timeout")
            elif result["api_result"] == "NO_RESULTS":
                print(f"   ❌ Not geocodable (no results)")
            elif result["api_result"] == "FILTERED_OUT":
                print(f"   ⚠️  Geocodable but filtered out (place_rank < 20 or validation failed)")
            else:
                print(f"   ❌ Error: {result['api_result']}")
            
            print()
            time.sleep(1)  # Rate limiting
        
        # Summary
        print("-"*80)
        print("API Validation Summary:")
        print("-"*80)
        
        successful = [r for r in api_results if r["api_result"] == "SUCCESS"]
        if successful:
            avg_score = sum(r["score"] for r in successful) / len(successful)
            avg_area = sum(r["bounding_box_area"] for r in successful) / len(successful)
            
            print(f"✅ Successful API calls: {len(successful)}/{len(api_results)}")
            print(f"📊 Average Score: {avg_score:.2f}")
            print(f"📐 Average Bounding Box Area: {avg_area:.1f} m²")
            
            # Score distribution
            score_1_0 = sum(1 for r in successful if r["score"] == 1.0)
            score_0_9 = sum(1 for r in successful if r["score"] == 0.9)
            score_0_8 = sum(1 for r in successful if r["score"] == 0.8)
            
            print(f"\nScore Distribution:")
            print(f"  1.0 (Full Score): {score_1_0}")
            print(f"  0.9: {score_0_9}")
            print(f"  0.8: {score_0_8}")
            
            if avg_score >= 0.9:
                print(f"\n🎉 EXCELLENT - Addresses will score 0.9-1.0 from API!")
            elif avg_score >= 0.7:
                print(f"\n✅ GOOD - Addresses will score 0.7-0.9 from API")
            else:
                print(f"\n⚠️  NEEDS IMPROVEMENT - Addresses score < 0.7")
        else:
            print(f"❌ No successful API calls")
        
        print()

if __name__ == "__main__":
    main()

