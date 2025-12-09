#!/usr/bin/env python3
"""
Generate Multiple Names with Orthographic Variations
===================================================

This script:
1. Loads names from Sanctioned_list.json
2. Generates 15 variations for each name using orthographic generator
3. Generates 15 DOB variations for each name
4. Outputs results in a format ready for validator testing
"""

import sys
import os
import json
import random
import logging
from typing import List, Dict, Any, Tuple
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'generate_multiple_names_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger(__name__)

# Add MIID/validator to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

# Import the orthographic generator
from maximize_orthographic_similarity import generate_full_name_variations, generate_dob_variations, normalize_dob_format


def load_sanctioned_names(count: int = 15) -> List[str]:
    """Load names from Sanctioned_list.json"""
    sanctioned_file = "MIID/validator/Sanctioned_list.json"
    
    if not os.path.exists(sanctioned_file):
        logger.error(f"❌ {sanctioned_file} not found")
        return []
    
    try:
        with open(sanctioned_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extract names from the JSON structure
        names = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    # Try FirstName + LastName combination
                    first_name = item.get('FirstName') or item.get('first_name') or item.get('firstname')
                    last_name = item.get('LastName') or item.get('last_name') or item.get('lastname')
                    
                    if first_name and last_name:
                        full_name = f"{first_name} {last_name}"
                        names.append(full_name)
                    else:
                        # Try single name field
                        name = (item.get('name') or item.get('Name') or 
                               item.get('full_name') or item.get('Full Name') or
                               item.get('fullName') or item.get('FullName'))
                        if name:
                            names.append(name)
                elif isinstance(item, str):
                    names.append(item)
        elif isinstance(data, dict):
            # Try to find a list of names in the dict
            for key, value in data.items():
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            first_name = item.get('FirstName') or item.get('first_name') or item.get('firstname')
                            last_name = item.get('LastName') or item.get('last_name') or item.get('lastname')
                            
                            if first_name and last_name:
                                full_name = f"{first_name} {last_name}"
                                names.append(full_name)
                            else:
                                name = (item.get('name') or item.get('Name') or 
                                       item.get('full_name') or item.get('Full Name') or
                                       item.get('fullName') or item.get('FullName'))
                                if name:
                                    names.append(name)
                        elif isinstance(item, str):
                            names.append(item)
                elif isinstance(value, dict):
                    # Nested dict structure
                    first_name = value.get('FirstName') or value.get('first_name') or value.get('firstname')
                    last_name = value.get('LastName') or value.get('last_name') or value.get('lastname')
                    
                    if first_name and last_name:
                        full_name = f"{first_name} {last_name}"
                        names.append(full_name)
                    else:
                        name = (value.get('name') or value.get('Name') or 
                               value.get('full_name') or value.get('Full Name') or
                               value.get('fullName') or value.get('FullName'))
                        if name:
                            names.append(name)
        
        # Remove duplicates and return requested count
        unique_names = list(dict.fromkeys(names))  # Preserves order
        selected = unique_names[:count] if len(unique_names) >= count else unique_names
        
        logger.info(f"✅ Loaded {len(selected)} names from {sanctioned_file}")
        logger.info(f"   Total unique names available: {len(unique_names)}")
        return selected
        
    except Exception as e:
        logger.error(f"❌ Error loading {sanctioned_file}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []


def generate_for_multiple_names(
    names: List[str],
    variation_count: int = 15,
    light_pct: float = 0.2,
    medium_pct: float = 0.6,
    far_pct: float = 0.2,
    seed_dob: str = "1985-03-15"
) -> Dict[str, Dict[str, Any]]:
    """
    Generate variations for multiple names.
    
    Returns:
        Dictionary mapping name to {
            'variations': [(first_var, last_var), ...],
            'dob_variations': [dob1, dob2, ...],
            'full_name_variations': ['First Last', ...]
        }
    """
    results = {}
    
    target_distribution = {
        "Light": light_pct,
        "Medium": medium_pct,
        "Far": far_pct
    }
    
    for i, name in enumerate(names, 1):
        logger.info("=" * 80)
        logger.info(f"Processing {i}/{len(names)}: {name}")
        logger.info("=" * 80)
        
        # Split name into first and last
        name_parts = name.strip().split()
        if len(name_parts) < 2:
            logger.warning(f"⚠️  Skipping '{name}' - needs at least first and last name")
            continue
        
        first_name = name_parts[0]
        last_name = " ".join(name_parts[1:])
        
        logger.info(f"  First: '{first_name}'")
        logger.info(f"  Last: '{last_name}'")
        
        # Generate name variations
        logger.info(f"  Generating {variation_count} name variations...")
        try:
            combined_variations, gen_metrics = generate_full_name_variations(
                first_name, last_name, target_distribution, variation_count
            )
            logger.info(f"  ✅ Generated {len(combined_variations)} name variations")
        except Exception as e:
            logger.error(f"  ❌ Error generating name variations: {e}")
            import traceback
            logger.error(traceback.format_exc())
            continue
        
        # Generate DOB variations
        logger.info(f"  Generating {variation_count} DOB variations...")
        try:
            dob_variations = generate_dob_variations(seed_dob, variation_count)
            logger.info(f"  ✅ Generated {len(dob_variations)} DOB variations")
        except Exception as e:
            logger.error(f"  ❌ Error generating DOB variations: {e}")
            import traceback
            logger.error(traceback.format_exc())
            continue
        
        # Format full name variations
        full_name_variations = [f"{first_var} {last_var}" for first_var, last_var in combined_variations]
        
        results[name] = {
            'variations': combined_variations,
            'dob_variations': dob_variations,
            'full_name_variations': full_name_variations,
            'first_name': first_name,
            'last_name': last_name,
            'metrics': gen_metrics
        }
        
        logger.info(f"  ✅ Completed: {name}")
        logger.info("")
    
    return results


def format_output(results: Dict[str, Dict[str, Any]], output_file: str = None):
    """Format and display results"""
    print("=" * 80)
    print("GENERATION RESULTS")
    print("=" * 80)
    print()
    
    for name, data in results.items():
        print(f"Name: {name}")
        print(f"  First: {data['first_name']}")
        print(f"  Last: {data['last_name']}")
        print(f"  Variations: {len(data['variations'])}")
        print(f"  DOB Variations: {len(data['dob_variations'])}")
        print()
        
        # Show first 3 variations as examples
        print("  Sample Variations:")
        for i, (first_var, last_var) in enumerate(data['variations'][:3], 1):
            dob_var = data['dob_variations'][i-1] if i-1 < len(data['dob_variations']) else "N/A"
            print(f"    {i}. {first_var} {last_var} | DOB: {dob_var}")
        print()
    
    # Format for JSON output
    json_output = {}
    for name, data in results.items():
        json_output[name] = {
            'original': name,
            'first_name': data['first_name'],
            'last_name': data['last_name'],
            'variations': [
                {
                    'full_name': f"{first_var} {last_var}",
                    'first_name': first_var,
                    'last_name': last_var,
                    'dob': dob_var
                }
                for (first_var, last_var), dob_var in zip(
                    data['variations'],
                    data['dob_variations']
                )
            ]
        }
    
    # Save to JSON file
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_output, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ Results saved to {output_file}")
        print(f"✅ Results saved to {output_file}")
    
    return json_output


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate orthographic variations for multiple names")
    parser.add_argument("--count", type=int, default=15, help="Number of names to process (default: 15)")
    parser.add_argument("--variations", type=int, default=15, help="Number of variations per name (default: 15)")
    parser.add_argument("--light", type=float, default=0.2, help="Target Light percentage (default: 0.2)")
    parser.add_argument("--medium", type=float, default=0.6, help="Target Medium percentage (default: 0.6)")
    parser.add_argument("--far", type=float, default=0.2, help="Target Far percentage (default: 0.2)")
    parser.add_argument("--dob", type=str, default="1985-03-15", help="Seed DOB (default: 1985-03-15)")
    parser.add_argument("--output", type=str, default=None, help="Output JSON file (default: auto-generated)")
    
    args = parser.parse_args()
    
    # Normalize percentages
    total = args.light + args.medium + args.far
    if total != 1.0:
        print(f"⚠️  Percentages sum to {total}, normalizing...")
        args.light /= total
        args.medium /= total
        args.far /= total
    
    print("=" * 80)
    print("MULTIPLE NAMES ORTHOGRAPHIC VARIATION GENERATOR")
    print("=" * 80)
    print()
    print(f"Names to process: {args.count}")
    print(f"Variations per name: {args.variations}")
    print(f"Target distribution: Light={args.light:.1%}, Medium={args.medium:.1%}, Far={args.far:.1%}")
    print(f"Seed DOB: {args.dob}")
    print()
    
    # Load names
    print("Loading names from Sanctioned_list.json...")
    names = load_sanctioned_names(args.count)
    
    if not names:
        print("❌ No names loaded. Exiting.")
        return
    
    if len(names) < args.count:
        print(f"⚠️  Only {len(names)} names available (requested {args.count})")
    
    print(f"✅ Loaded {len(names)} names")
    for i, name in enumerate(names, 1):
        print(f"  {i}. {name}")
    print()
    
    # Generate variations
    print("Generating variations...")
    print()
    results = generate_for_multiple_names(
        names,
        variation_count=args.variations,
        light_pct=args.light,
        medium_pct=args.medium,
        far_pct=args.far,
        seed_dob=args.dob
    )
    
    if not results:
        print("❌ No results generated. Exiting.")
        return
    
    # Format and save output
    output_file = args.output or f"orthographic_variations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    json_output = format_output(results, output_file)
    
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✅ Processed {len(results)} names")
    print(f"✅ Generated {args.variations} variations per name")
    print(f"✅ Generated {args.variations} DOB variations per name")
    print(f"✅ Results saved to: {output_file}")
    print()
    
    # Show statistics
    total_variations = sum(len(data['variations']) for data in results.values())
    total_dobs = sum(len(data['dob_variations']) for data in results.values())
    print(f"Total name variations: {total_variations}")
    print(f"Total DOB variations: {total_dobs}")
    print()


if __name__ == "__main__":
    main()

