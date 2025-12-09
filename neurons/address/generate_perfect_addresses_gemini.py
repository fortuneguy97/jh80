#!/usr/bin/env python3
"""
Generate perfect addresses using Gemini and validate with rewards.py
Ensures final validator score is 1.0
"""

import os
import sys
import json
import time
import re
import logging
from datetime import datetime
from typing import List, Dict, Any, Tuple

# Setup logging
def setup_logging(country: str, output_file: str = None):
    """Setup logging to both console and file"""
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # Create log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    country_safe = re.sub(r'[^\w\s-]', '', country).strip().replace(' ', '_')
    log_file = os.path.join(log_dir, f"address_generation_{country_safe}_{timestamp}.log")
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"="*80)
    logger.info(f"ADDRESS GENERATION SESSION STARTED")
    logger.info(f"="*80)
    logger.info(f"Country: {country}")
    logger.info(f"Log file: {log_file}")
    logger.info(f"Output file: {output_file}")
    logger.info(f"="*80)
    
    return logger, log_file

# Parse arguments BEFORE importing bittensor (which happens via reward.py)
_original_argv = sys.argv.copy()
_country = None
_target = 15
_output = None

i = 1
while i < len(sys.argv):
    if sys.argv[i] == '--country' and i + 1 < len(sys.argv):
        _country = sys.argv[i + 1]
        i += 2
    elif sys.argv[i] == '--target' and i + 1 < len(sys.argv):
        _target = int(sys.argv[i + 1])
        i += 2
    elif sys.argv[i] == '--output' and i + 1 < len(sys.argv):
        _output = sys.argv[i + 1]
        i += 2
    elif sys.argv[i] in ['-h', '--help']:
        print("Usage: generate_perfect_addresses_gemini.py --country COUNTRY [--target N] [--output FILE]")
        print("  --country COUNTRY  Country name (required)")
        print("  --target N         Target number of perfect addresses (default: 15)")
        print("  --output FILE      Output JSON file path (optional)")
        sys.exit(0)
    else:
        i += 1

# Temporarily clear sys.argv to prevent bittensor from parsing it
_saved_argv = sys.argv
sys.argv = [sys.argv[0]]  # Keep only script name

# Add MIID validator to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MIID', 'validator'))

# Import after clearing argv
from reward import (
    _grade_address_variations,
    looks_like_address,
    validate_address_region,
    check_with_nominatim
)

# Restore argv
sys.argv = _saved_argv

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    print("ERROR: google-generativeai not installed. Run: pip install google-generativeai")
    GEMINI_AVAILABLE = False
    sys.exit(1)


ADDRESS_GENERATION_PROMPT = """You are an address generation engine.

Generate exactly 100 REAL, VALID postal addresses from the COUNTRY I specify.

Follow these rules STRICTLY:

============================================================
ADDRESS RULES (MUST FOLLOW EXACTLY)
============================================================

1. All addresses MUST be real buildings that exist in OpenStreetMap (OSM).

2. Each address MUST be a small building (<100 m² footprint) or very likely to be.

3. Use this EXACT format:
   "{{house_number}} {{street_name}}, {{city}}, {{postcode}}, {{country}}"

4. Each address MUST contain:
   - A real house number
   - A real street
   - A real city or town
   - A real postcode
   - EXACT country name at the end

5. ASCII ONLY (no accented letters).

6. At least 3 comma sections (house/street, city, postcode, country).

7. No business names, no POIs, no apartments, no schools, no malls.

8. At least 15 out of 100 MUST:
   - Resolve on Nominatim Search
   - Return a building polygon (not a road)
   - Have area <100 m²

============================================================
OSM SMALL-BUILDING ZONE RESTRICTION (CRITICAL)
============================================================

Only generate addresses from REAL residential streets that contain MANY 
small detached buildings (<100 m²) on OSM.

For United Kingdom, use ONLY these specific city zones with known OSM coverage:

• Oxford – Walton Street area, Iffley Fields
• Manchester – Northern Quarter backstreets
• Birmingham – Small Heath residential blocks
• Sheffield – Nether Edge small streets
• Glasgow – Dennistoun residential rows
• Leeds – Hyde Park backstreets
• Bristol – Totterdown small houses
• Edinburgh – New Town mews houses
• London – Residential mews in Kensington, Chelsea, Marylebone
• Cambridge – Residential streets near city center
• Liverpool – Residential terraces in specific areas
• Nottingham – Residential areas with small houses

Every address MUST be from one of these real OSM streets.

Use ONLY street names that actually exist in these areas, and use ONLY real 
house numbers that exist on those streets.

Examples of VALID OSM-based small streets in UK:
• "Walton Street" (Oxford)
• "King Edward Street" (various cities)
• "Green Street" (various cities)
• "Lavery Court" (Glasgow)
• "Park Mews" (London)
• "Upper Meynell Street" (Birmingham)
• "Dane Road" (Manchester)
• "Victoria Mews" (various cities)
• "Albert Road" (residential sections only)
• "Queen's Lane" (Oxford)
• "Grove Street" (various cities)
• "Church Lane" (various cities)
• "Mill Lane" (various cities)
• "Back Street" (various cities)
• "Mews" streets (London, Edinburgh)

CRITICAL: Do NOT invent street names. Only use streets that actually exist 
in OSM in the zones listed above. These streets are known to have small 
residential buildings that will pass OSM validation.

============================================================
EXAMPLE PERFECT ADDRESSES (DO NOT REPEAT THESE)
============================================================

Example 1:
"24 Market Street, Manchester, M1 1WR, United Kingdom"

Example 2:
"32 High Street, Oxford, OX1 4AW, United Kingdom"

Use these as a style reference for how all output addresses must look.

============================================================
YOUR TASK
============================================================

COUNTRY = {country}

Output exactly 100 addresses for this country.

Each address must:
1. Follow all rules above
2. Be from the OSM small-building zones specified
3. Use only real street names from those zones
4. Use only real house numbers from those streets

Return ONLY the addresses, one per line, no numbering, no explanations."""


class PerfectAddressGenerator:
    """Generate and validate perfect addresses using Gemini"""
    
    def __init__(self, validator_uid: int = 101, miner_uid: int = 501, logger=None):
        self.validator_uid = validator_uid
        self.miner_uid = miner_uid
        self.perfect_addresses = []
        self.logger = logger or logging.getLogger(__name__)
        
        # Configure Gemini
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            self.logger.error("GEMINI_API_KEY environment variable not set")
            raise ValueError("GEMINI_API_KEY environment variable not set")
        
        self.logger.info("Configuring Gemini API...")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-2.5-pro")
        self.logger.info("✅ Gemini API configured successfully (using gemini-2.5-pro)")
    
    def generate_addresses_with_gemini(self, country: str) -> List[str]:
        """Generate 100 addresses using Gemini"""
        self.logger.info(f"\n{'='*80}")
        self.logger.info(f"GENERATING ADDRESSES FOR: {country}")
        self.logger.info(f"{'='*80}")
        
        prompt = ADDRESS_GENERATION_PROMPT.format(country=country)
        
        self.logger.info("📡 Sending request to Gemini API...")
        self.logger.debug(f"Prompt length: {len(prompt)} characters")
        
        try:
            start_time = time.time()
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=4096,
                    temperature=0.7,
                )
            )
            elapsed = time.time() - start_time
            self.logger.info(f"✅ Gemini API response received in {elapsed:.2f} seconds")
            self.logger.debug(f"Response length: {len(response.text)} characters")
            
            # Parse addresses from response
            addresses = []
            raw_lines = response.text.strip().split('\n')
            self.logger.info(f"Parsing {len(raw_lines)} lines from Gemini response...")
            
            for i, line in enumerate(raw_lines, 1):
                original_line = line
                line = line.strip()
                # Remove numbering if present (e.g., "1. ", "1) ", "- ")
                line = re.sub(r'^\d+[\.\)]\s*', '', line)
                line = re.sub(r'^-\s*', '', line)
                line = line.strip()
                
                if line and len(line) > 10:  # Basic validation
                    addresses.append(line)
                    self.logger.debug(f"  [{i}] Parsed: {line[:60]}...")
                else:
                    self.logger.debug(f"  [{i}] Skipped (too short or empty): {original_line[:60]}...")
            
            self.logger.info(f"✅ Successfully parsed {len(addresses)} addresses from Gemini response")
            final_addresses = addresses[:100]  # Limit to 100
            if len(addresses) > 100:
                self.logger.warning(f"⚠️  Limited to first 100 addresses (received {len(addresses)})")
            
            return final_addresses
            
        except Exception as e:
            self.logger.error(f"❌ Error generating addresses: {str(e)}")
            self.logger.exception("Full traceback:")
            return []
    
    def validate_address(
        self,
        address: str,
        seed_address: str
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Validate a single address using all rewards.py functions.
        Returns: (is_perfect, score, details)
        """
        self.logger.debug(f"Validating address: {address}")
        
        details = {
            'address': address,
            'heuristic': False,
            'region': False,
            'api_score': 0.0,
            'api_area': None,
            'api_result': None
        }
        
        # 1. Heuristic check
        self.logger.debug(f"  [1/3] Running heuristic check...")
        heuristic_ok = looks_like_address(address)
        details['heuristic'] = heuristic_ok
        
        if not heuristic_ok:
            self.logger.debug(f"  ❌ Heuristic check FAILED")
            return False, 0.0, details
        
        self.logger.debug(f"  ✅ Heuristic check PASSED")
        
        # 2. Region check
        self.logger.debug(f"  [2/3] Running region validation...")
        region_ok = validate_address_region(address, seed_address)
        details['region'] = region_ok
        
        if not region_ok:
            self.logger.debug(f"  ❌ Region validation FAILED")
            return False, 0.0, details
        
        self.logger.debug(f"  ✅ Region validation PASSED")
        
        # 3. API check (with rate limiting)
        self.logger.debug(f"  [3/3] Running API validation (Nominatim)...")
        api_start = time.time()
        api_result = check_with_nominatim(
            address=address,
            validator_uid=self.validator_uid,
            miner_uid=self.miner_uid,
            seed_address=seed_address,
            seed_name="Test"
        )
        api_elapsed = time.time() - api_start
        self.logger.debug(f"  API call completed in {api_elapsed:.2f} seconds")
        
        if isinstance(api_result, dict):
            api_score = api_result.get('score', 0.0)
            api_area = api_result.get('min_area', None)
            details['api_score'] = api_score
            details['api_area'] = api_area
            details['api_result'] = 'SUCCESS'
            
            # Perfect address: score >= 0.99 (area < 100 m²)
            is_perfect = api_score >= 0.99
            if is_perfect:
                self.logger.debug(f"  ✅ API validation PASSED (Score: {api_score:.4f}, Area: {api_area:.2f} m²)")
            else:
                self.logger.debug(f"  ⚠️  API validation GOOD but not perfect (Score: {api_score:.4f}, Area: {api_area:.2f} m²)")
            
            return is_perfect, api_score, details
        elif api_result == "TIMEOUT":
            details['api_result'] = 'TIMEOUT'
            self.logger.debug(f"  ⏱️  API validation TIMEOUT")
            return False, 0.0, details
        else:
            details['api_result'] = 'FAILED'
            self.logger.debug(f"  ❌ API validation FAILED")
            return False, 0.0, details
    
    def find_perfect_addresses(
        self,
        addresses: List[str],
        seed_address: str,
        target_count: int = 15
    ) -> List[str]:
        """
        Validate addresses and collect perfect ones (score >= 0.99).
        Returns when we have target_count perfect addresses.
        """
        self.logger.info(f"\n{'='*80}")
        self.logger.info(f"VALIDATING ADDRESSES (Target: {target_count} perfect addresses)")
        self.logger.info(f"{'='*80}\n")
        
        perfect_addresses = []
        validation_stats = {
            'total': len(addresses),
            'heuristic_pass': 0,
            'region_pass': 0,
            'api_perfect': 0,
            'api_good': 0,
            'api_failed': 0,
            'api_timeout': 0
        }
        
        start_time = time.time()
        
        for i, addr in enumerate(addresses, 1):
            if len(perfect_addresses) >= target_count:
                self.logger.info(f"✅ Target reached! Found {len(perfect_addresses)} perfect addresses")
                break
            
            elapsed = time.time() - start_time
            self.logger.info(f"[{i}/{len(addresses)}] ({elapsed:.1f}s) Validating: {addr[:60]}...")
            
            is_perfect, score, details = self.validate_address(addr, seed_address)
            
            # Update stats
            if details['heuristic']:
                validation_stats['heuristic_pass'] += 1
            if details['region']:
                validation_stats['region_pass'] += 1
            
            if details['api_result'] == 'SUCCESS':
                if is_perfect:
                    validation_stats['api_perfect'] += 1
                    perfect_addresses.append(addr)
                    self.logger.info(f"  ✅ PERFECT! Score: {score:.4f}, Area: {details['api_area']:.2f} m²")
                    self.logger.info(f"  Progress: {len(perfect_addresses)}/{target_count} perfect addresses found")
                else:
                    validation_stats['api_good'] += 1
                    self.logger.info(f"  ⚠️  Good but not perfect. Score: {score:.4f}, Area: {details['api_area']:.2f} m²")
            elif details['api_result'] == 'TIMEOUT':
                validation_stats['api_timeout'] += 1
                self.logger.warning(f"  ⏱️  API TIMEOUT")
            else:
                validation_stats['api_failed'] += 1
                self.logger.warning(f"  ❌ Failed: {details['api_result']}")
            
            # Rate limit: 2 seconds between API calls
            if i < len(addresses):
                time.sleep(2.0)
                self.logger.debug(f"  Rate limiting: waiting 2 seconds before next API call...")
        
        total_elapsed = time.time() - start_time
        
        self.logger.info(f"\n{'='*80}")
        self.logger.info("VALIDATION SUMMARY")
        self.logger.info(f"{'='*80}")
        self.logger.info(f"Total addresses tested: {validation_stats['total']}")
        self.logger.info(f"Heuristic pass: {validation_stats['heuristic_pass']}")
        self.logger.info(f"Region pass: {validation_stats['region_pass']}")
        self.logger.info(f"API perfect (score >= 0.99): {validation_stats['api_perfect']}")
        self.logger.info(f"API good (score < 0.99): {validation_stats['api_good']}")
        self.logger.info(f"API failed: {validation_stats['api_failed']}")
        self.logger.info(f"API timeout: {validation_stats['api_timeout']}")
        self.logger.info(f"Total validation time: {total_elapsed:.2f} seconds")
        self.logger.info(f"Average time per address: {total_elapsed/len(addresses):.2f} seconds")
        self.logger.info(f"\n✅ Found {len(perfect_addresses)} perfect addresses!")
        self.logger.info(f"{'='*80}\n")
        
        return perfect_addresses
    
    def validate_with_mock_validator(
        self,
        addresses: List[str],
        seed_address: str
    ) -> Dict[str, Any]:
        """Validate addresses using mock validator and return final score"""
        self.logger.info(f"\n{'='*80}")
        self.logger.info("MOCK VALIDATOR VALIDATION")
        self.logger.info(f"{'='*80}\n")
        self.logger.info(f"Validating {len(addresses)} addresses with mock validator...")
        
        # Format addresses as variations
        variations = {
            "Test Identity": [
                ["Test Identity", "1990-01-01", addr] for addr in addresses
            ]
        }
        
        seed_addresses = [seed_address]
        miner_metrics = {}
        
        self.logger.info("🔄 Calling _grade_address_variations...")
        validator_start = time.time()
        
        result = _grade_address_variations(
            variations=variations,
            seed_addresses=seed_addresses,
            miner_metrics=miner_metrics,
            validator_uid=self.validator_uid,
            miner_uid=self.miner_uid
        )
        
        validator_elapsed = time.time() - validator_start
        overall_score = result.get('overall_score', 0.0)
        
        self.logger.info(f"✅ Validator completed in {validator_elapsed:.2f} seconds")
        self.logger.info(f"\n{'='*80}")
        self.logger.info("FINAL VALIDATOR SCORE")
        self.logger.info(f"{'='*80}")
        self.logger.info(f"📊 Score: {overall_score:.4f}")
        
        # Log detailed breakdown
        heuristic_perfect = result.get('heuristic_perfect', False)
        region_matches = result.get('region_matches', 0)
        api_result = result.get('api_result', 'UNKNOWN')
        
        self.logger.info(f"Heuristic perfect: {heuristic_perfect}")
        self.logger.info(f"Region matches: {region_matches}/{len(addresses)}")
        self.logger.info(f"API result: {api_result}")
        
        if overall_score >= 0.99:
            self.logger.info("✅✅✅ SUCCESS: Final score is 1.0 (Perfect)!")
        else:
            self.logger.warning(f"⚠️  WARNING: Final score is {overall_score:.4f} (expected 1.0)")
        
        self.logger.info(f"{'='*80}\n")
        
        return result
    
    def generate_and_validate(
        self,
        country: str,
        target_perfect: int = 15
    ) -> Tuple[List[str], Dict[str, Any]]:
        """
        Main function: Generate addresses, validate, and return perfect ones.
        Returns: (perfect_addresses, validator_result)
        """
        session_start = time.time()
        self.logger.info(f"Starting address generation and validation session")
        self.logger.info(f"Target: {target_perfect} perfect addresses for {country}")
        
        # Generate addresses with Gemini
        addresses = self.generate_addresses_with_gemini(country)
        
        if not addresses:
            self.logger.error("❌ No addresses generated")
            return [], {}
        
        self.logger.info(f"Generated {len(addresses)} addresses, starting validation...")
        
        # Find perfect addresses
        perfect_addresses = self.find_perfect_addresses(
            addresses,
            seed_address=country,
            target_count=target_perfect
        )
        
        if len(perfect_addresses) < target_perfect:
            self.logger.warning(f"⚠️  Warning: Only found {len(perfect_addresses)} perfect addresses (target: {target_perfect})")
        
        # Validate with mock validator
        if perfect_addresses:
            self.logger.info(f"Validating {len(perfect_addresses)} perfect addresses with mock validator...")
            validator_result = self.validate_with_mock_validator(
                perfect_addresses,
                seed_address=country
            )
            
            total_elapsed = time.time() - session_start
            self.logger.info(f"✅ Session completed in {total_elapsed:.2f} seconds")
            
            return perfect_addresses, validator_result
        else:
            self.logger.error("❌ No perfect addresses found to validate")
            return [], {}


def main():
    """Main function"""
    # Use pre-parsed arguments
    country = _country
    target = _target
    output = _output
    
    if not country:
        print("ERROR: --country is required")
        print("Usage: generate_perfect_addresses_gemini.py --country COUNTRY [--target N] [--output FILE]")
        return
    
    if not GEMINI_AVAILABLE:
        print("❌ Gemini not available")
        return
    
    # Setup logging
    logger, log_file = setup_logging(country, output)
    logger.info(f"Script started with arguments: country={country}, target={target}, output={output}")
    
    try:
        # Create generator
        logger.info("Initializing PerfectAddressGenerator...")
        generator = PerfectAddressGenerator(logger=logger)
        
        # Generate and validate
        perfect_addresses, validator_result = generator.generate_and_validate(
            country=country,
            target_perfect=target
        )
        
        # Save results
        if output:
            output_data = {
                'country': country,
                'perfect_addresses': perfect_addresses,
                'count': len(perfect_addresses),
                'validator_score': validator_result.get('overall_score', 0.0) if validator_result else 0.0,
                'validator_result': validator_result if validator_result else {},
                'timestamp': datetime.now().isoformat(),
                'log_file': log_file
            }
            
            with open(output, 'w') as f:
                json.dump(output_data, f, indent=2)
            
            logger.info(f"💾 Results saved to: {output}")
        
        # Print summary
        logger.info(f"\n{'='*80}")
        logger.info("FINAL SUMMARY")
        logger.info(f"{'='*80}")
        logger.info(f"Country: {country}")
        logger.info(f"Perfect addresses found: {len(perfect_addresses)}")
        if validator_result:
            logger.info(f"Final validator score: {validator_result.get('overall_score', 0.0):.4f}")
        logger.info(f"Log file: {log_file}")
        logger.info(f"Output file: {output}")
        logger.info(f"{'='*80}\n")
        
        logger.info("="*80)
        logger.info("SESSION COMPLETED SUCCESSFULLY")
        logger.info("="*80)
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {str(e)}")
        logger.exception("Full traceback:")
        raise


if __name__ == "__main__":
    main()

