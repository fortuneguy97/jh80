#!/usr/bin/env python3
"""
Generate perfect addresses for ALL countries using Gemini.
Features:
- Resumable progress (saves on Ctrl+C)
- Exponential retry (100 -> 200 -> 400 -> ...)
- Country-specific prompts
- Progress tracking
"""

import os
import sys
import json
import time
import re
import logging
import signal
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
import geonamescache

# Setup logging
def setup_logging():
    """Setup logging to both console and file"""
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"all_countries_generation_{timestamp}.log")
    
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
    logger.info(f"ALL COUNTRIES ADDRESS GENERATION STARTED")
    logger.info(f"="*80)
    logger.info(f"Log file: {log_file}")
    logger.info(f"="*80)
    
    return logger, log_file

# Parse arguments BEFORE importing bittensor
_original_argv = sys.argv.copy()
_cache_file = "all_countries_address_cache.json"
_target_per_country = 15

i = 1
while i < len(sys.argv):
    if sys.argv[i] == '--cache' and i + 1 < len(sys.argv):
        _cache_file = sys.argv[i + 1]
        i += 2
    elif sys.argv[i] == '--target' and i + 1 < len(sys.argv):
        _target_per_country = int(sys.argv[i + 1])
        i += 2
    elif sys.argv[i] in ['-h', '--help']:
        print("Usage: generate_all_countries_addresses.py [--cache FILE] [--target N]")
        print("  --cache FILE  Cache file path (default: all_countries_address_cache.json)")
        print("  --target N     Target addresses per country (default: 15)")
        sys.exit(0)
    else:
        i += 1

# Temporarily clear sys.argv
_saved_argv = sys.argv
sys.argv = [sys.argv[0]]

# Add MIID validator to path (safe __file__ handling)
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
sys.path.insert(0, os.path.join(BASE_DIR, 'MIID', 'validator'))

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


def country_has_osm_addressing(country: str) -> bool:
    """
    Check if a country has sufficient OSM house-number coverage.
    Some countries have very weak or no house-number mapping in OSM,
    making it impossible to generate perfect addresses.
    """
    weak_osm_countries = {
        "Afghanistan", "Somalia", "Yemen", "Sudan", "South Sudan",
        "Chad", "Niger", "Eritrea", "Libya", "Syria", "Iraq",
        "Central African Republic", "Democratic Republic of the Congo", 
        "DR Congo", "Congo, Democratic Republic of the", "Laos", 
        "North Korea", "Burundi", "Madagascar", "Mali", "Mozambique",
        "Myanmar", "Burma", "Guinea", "Guinea-Bissau", "Sierra Leone",
        "Liberia", "Togo", "Benin", "Burkina Faso", "Mauritania"
    }
    return country not in weak_osm_countries


def normalize_country_name(country: str) -> str:
    """Normalize country names to match GeonamesCache format"""
    country = country.strip()
    
    # Country name mappings (from reward.py COUNTRY_MAPPING)
    mappings = {
        "korea, south": "South Korea",
        "korea, north": "North Korea",
        "cote d ivoire": "Ivory Coast",
        "côte d'ivoire": "Ivory Coast",
        "cote d'ivoire": "Ivory Coast",
        "the gambia": "Gambia",
        "netherlands": "The Netherlands",
        "holland": "The Netherlands",
        "congo, democratic republic of the": "Democratic Republic of the Congo",
        "drc": "Democratic Republic of the Congo",
        "congo, republic of the": "Republic of the Congo",
        "burma": "Myanmar",
        "bonaire": "Bonaire, Saint Eustatius and Saba",
        "usa": "United States",
        "us": "United States",
        "united states of america": "United States",
        "uk": "United Kingdom",
        "great britain": "United Kingdom",
        "britain": "United Kingdom",
        "uae": "United Arab Emirates",
        "u.s.a.": "United States",
        "u.s.": "United States",
        "u.k.": "United Kingdom",
    }
    
    country_lower = country.lower()
    if country_lower in mappings:
        return mappings[country_lower]
    
    return country


def load_all_countries_from_sanctioned_lists() -> set:
    """Load ALL countries from sanctioned lists (Country_Residence)"""
    countries_set = set()
    BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
    base_dir = os.path.join(BASE_DIR, 'MIID', 'validator')
    
    # 1. Load from Sanctioned_Transliteration.json
    trans_file = os.path.join(base_dir, 'Sanctioned_Transliteration.json')
    try:
        if os.path.exists(trans_file):
            with open(trans_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for person in data:
                    country = person.get('Country_Residence', '').strip()
                    if country:
                        countries_set.add(normalize_country_name(country))
    except Exception as e:
        logging.warning(f"Could not load Sanctioned_Transliteration.json: {e}")
    
    # 2. Load from Sanctioned_list.json
    list_file = os.path.join(base_dir, 'Sanctioned_list.json')
    try:
        if os.path.exists(list_file):
            with open(list_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for person in data:
                    country = person.get('Country_Residence', '').strip()
                    if country:
                        countries_set.add(normalize_country_name(country))
    except Exception as e:
        logging.warning(f"Could not load Sanctioned_list.json: {e}")
    
    # 3. Load from sanctioned_countries.json
    sanctioned_file = os.path.join(base_dir, 'sanctioned_countries.json')
    try:
        if os.path.exists(sanctioned_file):
            with open(sanctioned_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for category in data.values():
                    for entry in category:
                        country = entry.get('country', '').strip()
                        if country:
                            countries_set.add(normalize_country_name(country))
    except Exception as e:
        logging.warning(f"Could not load sanctioned_countries.json: {e}")
    
    return countries_set


def get_all_valid_countries() -> List[str]:
    """Get ALL countries that the validator might use:
    1. GeonamesCache valid countries (157)
    2. Countries from sanctioned lists (Country_Residence)
    3. Countries from sanctioned_countries.json
    """
    logger = logging.getLogger(__name__)
    
    excluded_territories = {
        'Antarctica',
        'Bouvet Island', 
        'Heard Island and McDonald Islands',
        'United States Minor Outlying Islands',
        'Tokelau',
        'British Indian Ocean Territory',
        'Netherlands Antilles',
        'Serbia and Montenegro',
        'Antigua and Barbuda',
        'Anguilla',
        'American Samoa',
        'Aland Islands',
        'Barbados',
        'Saint Barthelemy',
        'Bermuda',
        'Bonaire, Saint Eustatius and Saba ',
        'Cocos Islands',
        'Cook Islands',
        'Christmas Island',
        'Dominica',
        'Falkland Islands',
        'Micronesia',
        'Faroe Islands',
        'Grenada',
        'Guernsey',
        'Gibraltar',
        'Greenland',
        'South Georgia and the South Sandwich Islands',
        'Isle of Man',
        'Jersey',
        'Kiribati',
        'Saint Kitts and Nevis',
        'Liechtenstein',
        'Saint Martin',
        'Marshall Islands',
        'Northern Mariana Islands',
        'Maldives',
        'Norfolk Island',
        'Nauru',
        'Niue',
        'Saint Pierre and Miquelon',
        'Pitcairn',
        'Palau',
        'Solomon Islands',
        'Seychelles',
        'Saint Helena',
        'Svalbard and Jan Mayen',
        'San Marino',
        'Sao Tome and Principe',
        'Sint Maarten',
        'French Southern Territories',
        'Tonga',
        'Tuvalu',
        'Vatican',
        'Vanuatu',
        'Wallis and Futuna',
        'Samoa'
    }
    
    all_countries = set()
    
    # 1. Load from GeonamesCache (valid countries)
    try:
        logger.info("Loading GeonamesCache for country list...")
        geonames = geonamescache.GeonamesCache()
        countries_data = geonames.get_countries()
        
        for country_code, country_info in countries_data.items():
            country_name = country_info.get('name', '').strip()
            
            if not country_name:
                continue
            if country_name in excluded_territories:
                continue
            
            all_countries.add(country_name)
        
        logger.info(f"Loaded {len(all_countries)} countries from GeonamesCache")
        
    except Exception as e:
        logger.error(f"Error loading GeonamesCache: {e}")
    
    # 2. Load from sanctioned lists (Country_Residence)
    logger.info("Loading countries from sanctioned lists...")
    sanctioned_countries = load_all_countries_from_sanctioned_lists()
    all_countries.update(sanctioned_countries)
    logger.info(f"Added {len(sanctioned_countries)} countries from sanctioned lists")
    
    # Remove excluded territories
    all_countries = {c for c in all_countries if c not in excluded_territories}
    
    # Sort alphabetically for consistent processing
    valid_countries = sorted(all_countries)
    
    logger.info(f"✅ Total unique countries: {len(valid_countries)}")
    logger.info(f"   - From GeonamesCache: ~157")
    logger.info(f"   - From sanctioned lists: {len(sanctioned_countries)}")
    
    return valid_countries


def create_country_specific_prompt(country: str, count: int) -> str:
    """Create a sharp, country-specific prompt for Gemini"""
    
    # Base prompt template
    base_prompt = """You are an expert address generator for {country}.

Generate exactly {count} REAL, VALID postal addresses from {country} that exist in OpenStreetMap (OSM).

CRITICAL REQUIREMENTS:
1. All addresses MUST be real buildings that exist in OSM
2. Each address MUST be a small residential building (<100 m² footprint)
3. Use EXACT format: "{{house_number}} {{street_name}}, {{city}}, {{postcode}}, {country}"
4. ASCII ONLY (no accented letters)
5. At least 3 comma sections
6. No business names, POIs, apartments, schools, malls
7. House number MUST be at the START of the address

OSM VALIDATION REQUIREMENTS:
- Addresses must resolve on Nominatim Search API
- Must return a building polygon (not a road)
- Building area must be <100 m²
- Street name and house number must be EXACTLY correct in OSM

GENERATION STRATEGY:
Focus on residential areas with small detached houses, mews, terraces, or small residential buildings.
Use real street names from major cities in {country}.
Use real house numbers that exist on those streets.
Prioritize areas with dense OSM coverage.

Return ONLY the addresses, one per line, no numbering, no explanations."""
    
    return base_prompt.format(country=country, count=count)


class AllCountriesAddressGenerator:
    """Generate addresses for all countries with resumable progress"""
    
    def __init__(self, cache_file: str, target_per_country: int, validator_uid: int = 101, miner_uid: int = 501, logger=None):
        self.cache_file = cache_file
        self.target_per_country = target_per_country
        self.validator_uid = validator_uid
        self.miner_uid = miner_uid
        self.logger = logger or logging.getLogger(__name__)
        self.cache_data = self._load_cache()
        self.interrupted = False
        
        # Setup signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Configure Gemini
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            self.logger.error("GEMINI_API_KEY environment variable not set")
            raise ValueError("GEMINI_API_KEY environment variable not set")
        
        self.logger.info("Configuring Gemini API...")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-2.5-pro")
        self.logger.info("✅ Gemini API configured successfully (using gemini-2.5-pro)")
    
    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        self.logger.warning("\n⚠️  Interrupt received (Ctrl+C). Saving progress...")
        self.interrupted = True
        self._save_cache()
        self.logger.info("✅ Progress saved. You can resume by running the script again.")
        sys.exit(0)
    
    def _load_cache(self) -> Dict[str, Any]:
        """Load cache from file"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.logger.info(f"✅ Loaded cache from {self.cache_file}")
                    self.logger.info(f"   Countries already processed: {len(data.get('countries', {}))}")
                    return data
            except Exception as e:
                self.logger.warning(f"⚠️  Could not load cache: {e}. Starting fresh.")
        
        return {
            'countries': {},
            'metadata': {
                'created': datetime.now().isoformat(),
                'target_per_country': self.target_per_country
            }
        }
    
    def _save_cache(self):
        """Save cache to file"""
        try:
            self.cache_data['metadata']['last_updated'] = datetime.now().isoformat()
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache_data, f, indent=2, ensure_ascii=False)
            self.logger.debug(f"💾 Cache saved to {self.cache_file}")
        except Exception as e:
            self.logger.error(f"❌ Error saving cache: {e}")
    
    def generate_addresses_with_gemini(self, country: str, count: int) -> List[str]:
        """Generate addresses using Gemini with exponential retry"""
        prompt = create_country_specific_prompt(country, count)
        
        self.logger.info(f"📡 Sending request to Gemini API for {count} addresses...")
        
        try:
            start_time = time.time()
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=16384 if count > 400 else (8192 if count > 100 else 4096),
                    temperature=0.7,
                )
            )
            elapsed = time.time() - start_time
            self.logger.info(f"✅ Gemini API response received in {elapsed:.2f} seconds")
            
            # Check for blocked content or errors
            if not response.candidates or len(response.candidates) == 0:
                self.logger.error("❌ No candidates in response")
                return []
            
            candidate = response.candidates[0]
            finish_reason = getattr(candidate, 'finish_reason', 1)
            
            # Handle different finish reasons
            if finish_reason != 1:  # 1 = STOP (normal completion)
                finish_reason_map = {
                    2: "MAX_TOKENS",
                    3: "SAFETY (content blocked)",
                    4: "RECITATION",
                    5: "OTHER"
                }
                reason = finish_reason_map.get(finish_reason, f"UNKNOWN ({finish_reason})")
                
                if finish_reason == 3:  # SAFETY - content blocked, can't parse
                    self.logger.error(f"❌ Response blocked/failed: finish_reason={reason}")
                    self.logger.warning("⚠️  Content was blocked by safety filters. Try a different country or adjust prompt.")
                    return []
                elif finish_reason == 2:  # MAX_TOKENS - partial response, still try to parse
                    self.logger.warning(f"⚠️  Response hit token limit (finish_reason={reason}), but will parse partial response")
                else:
                    self.logger.warning(f"⚠️  Response finished with reason: {reason}, attempting to parse anyway")
            
            # Check if response has text
            if not hasattr(response, 'text') or not response.text:
                self.logger.error("❌ Response has no text content")
                return []
            
            # Parse addresses
            addresses = []
            raw_lines = response.text.strip().split('\n')
            self.logger.info(f"Parsing {len(raw_lines)} lines from Gemini response...")
            
            for i, line in enumerate(raw_lines, 1):
                original_line = line
                line = line.strip()
                # Remove numbering
                line = re.sub(r'^\d+[\.\)]\s*', '', line)
                line = re.sub(r'^-\s*', '', line)
                line = line.strip()
                
                if line and len(line) > 10:
                    addresses.append(line)
            
            self.logger.info(f"✅ Successfully parsed {len(addresses)} addresses")
            return addresses[:count]  # Limit to requested count
            
        except Exception as e:
            self.logger.error(f"❌ Error generating addresses: {str(e)}")
            return []
    
    def validate_address(
        self,
        address: str,
        seed_address: str
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """Validate a single address"""
        details = {
            'address': address,
            'heuristic': False,
            'region': False,
            'api_score': 0.0,
            'api_area': None,
            'api_result': None
        }
        
        # 1. Heuristic check
        if not looks_like_address(address):
            return False, 0.0, details
        
        details['heuristic'] = True
        
        # 2. Region check
        if not validate_address_region(address, seed_address):
            return False, 0.0, details
        
        details['region'] = True
        
        # 3. API check (with rate limiting)
        api_result = check_with_nominatim(
            address=address,
            validator_uid=self.validator_uid,
            miner_uid=self.miner_uid,
            seed_address=seed_address,
            seed_name="Test"
        )
        
        # Rate limit: 2 seconds between Nominatim calls
        time.sleep(2.0)
        
        if isinstance(api_result, dict):
            api_score = api_result.get('score', 0.0)
            api_area = api_result.get('min_area', None)
            details['api_score'] = api_score
            details['api_area'] = api_area
            details['api_result'] = 'SUCCESS'
            
            is_perfect = api_score >= 0.99
            return is_perfect, api_score, details
        else:
            details['api_result'] = 'FAILED'
            return False, 0.0, details
    
    def process_country(self, country: str) -> List[Dict[str, Any]]:
        """Process a single country with exponential retry"""
        self.logger.info(f"\n{'='*80}")
        self.logger.info(f"PROCESSING: {country}")
        self.logger.info(f"{'='*80}")
        
        # Check if already completed
        if country in self.cache_data['countries']:
            existing = self.cache_data['countries'][country]
            if len(existing.get('perfect_addresses', [])) >= self.target_per_country:
                self.logger.info(f"✅ {country} already completed ({len(existing['perfect_addresses'])} addresses)")
                return existing['perfect_addresses']
        
        perfect_addresses = []
        seed_address = f"123 Main Street, {country}"  # Simple seed for region validation
        
        # Exponential retry: 100 -> 200 -> 400 -> 800
        batch_sizes = [100, 200, 400, 800]
        batch_idx = 0
        
        while len(perfect_addresses) < self.target_per_country and batch_idx < len(batch_sizes):
            if self.interrupted:
                break
            
            batch_size = batch_sizes[batch_idx]
            self.logger.info(f"\n🔄 Attempt {batch_idx + 1}: Generating {batch_size} addresses...")
            
            # Generate addresses
            addresses = self.generate_addresses_with_gemini(country, batch_size)
            
            if not addresses:
                self.logger.warning(f"⚠️  No addresses generated. Retrying with larger batch...")
                batch_idx += 1
                continue
            
            # Validate addresses
            self.logger.info(f"Validating {len(addresses)} addresses...")
            validated_count = 0
            
            for i, address in enumerate(addresses, 1):
                if self.interrupted:
                    break
                
                if len(perfect_addresses) >= self.target_per_country:
                    break
                
                self.logger.info(f"[{i}/{len(addresses)}] Validating: {address[:60]}...")
                
                is_perfect, score, details = self.validate_address(address, seed_address)
                
                if is_perfect:
                    perfect_addresses.append({
                        'address': address,
                        'score': score,
                        'area_m2': details.get('api_area'),
                        'validated_at': datetime.now().isoformat()
                    })
                    self.logger.info(f"  ✅ PERFECT! Score: {score:.4f}, Area: {details.get('api_area', 'N/A')} m²")
                    self.logger.info(f"  Progress: {len(perfect_addresses)}/{self.target_per_country} perfect addresses")
                    
                    # Save progress after each perfect address
                    self.cache_data['countries'][country] = {
                        'perfect_addresses': perfect_addresses,
                        'last_updated': datetime.now().isoformat()
                    }
                    self._save_cache()
                else:
                    if details.get('api_result') == 'SUCCESS':
                        self.logger.info(f"  ⚠️  Good but not perfect. Score: {score:.4f}, Area: {details.get('api_area', 'N/A')} m²")
                    else:
                        self.logger.warning(f"  ❌ Failed: {details.get('api_result', 'UNKNOWN')}")
                
                validated_count += 1
            
            # Check if we need more addresses
            if len(perfect_addresses) < self.target_per_country:
                self.logger.warning(f"⚠️  Only found {len(perfect_addresses)}/{self.target_per_country} perfect addresses. Trying larger batch...")
                batch_idx += 1
            else:
                self.logger.info(f"✅ Target reached! Found {len(perfect_addresses)} perfect addresses")
                break
        
        # Final save
        self.cache_data['countries'][country] = {
            'perfect_addresses': perfect_addresses,
            'last_updated': datetime.now().isoformat()
        }
        self._save_cache()
        
        # Validate with mock validator if we have 15 addresses
        if len(perfect_addresses) >= self.target_per_country:
            self.logger.info(f"\n{'='*80}")
            self.logger.info(f"VALIDATING {len(perfect_addresses)} ADDRESSES WITH MOCK VALIDATOR")
            self.logger.info(f"{'='*80}")
            
            # Extract address strings from perfect_addresses (they're stored as dicts)
            address_strings = [addr['address'] if isinstance(addr, dict) else addr for addr in perfect_addresses[:self.target_per_country]]
            
            validator_score = self._validate_with_mock_validator(
                address_strings,
                country
            )
            
            # Update cache with validator score
            self.cache_data['countries'][country]['validator_score'] = validator_score
            self.cache_data['countries'][country]['validator_validated_at'] = datetime.now().isoformat()
            self._save_cache()
            
            if validator_score >= 0.99:
                self.logger.info(f"✅✅✅ SUCCESS: Validator score is {validator_score:.4f} (Perfect!)")
            else:
                self.logger.warning(f"⚠️  WARNING: Validator score is {validator_score:.4f} (Expected 1.0)")
        
        return perfect_addresses
    
    def _validate_with_mock_validator(
        self,
        addresses: List[str],
        country: str
    ) -> float:
        """Validate addresses using mock validator (_grade_address_variations)"""
        try:
            self.logger.info(f"🔄 Calling _grade_address_variations for {len(addresses)} addresses...")
            
            # Format addresses as variations (matching validator's expected format)
            # Format: {name: [[name_var, dob_var, address_var], ...]}
            seed_name = "Test Identity"
            seed_dob = "1990-01-01"
            variations = {
                seed_name: [
                    [seed_name, seed_dob, addr] for addr in addresses
                ]
            }
            
            # Seed addresses (one per name in variations)
            seed_addresses = [country]
            
            # Miner metrics (empty dict for mock)
            miner_metrics = {}
            
            # Call the validator's grading function
            result = _grade_address_variations(
                variations=variations,
                seed_addresses=seed_addresses,
                miner_metrics=miner_metrics,
                validator_uid=self.validator_uid,
                miner_uid=self.miner_uid
            )
            
            # Extract score
            overall_score = result.get('overall_score', 0.0)
            heuristic_perfect = result.get('heuristic_perfect', False)
            region_matches = result.get('region_matches', 0)
            total_addresses = result.get('total_addresses', len(addresses))
            api_result = result.get('api_result', 'UNKNOWN')
            
            self.logger.info(f"\n{'='*80}")
            self.logger.info(f"VALIDATOR VALIDATION RESULTS")
            self.logger.info(f"{'='*80}")
            self.logger.info(f"📊 Final Address Score: {overall_score:.4f}")
            self.logger.info(f"✅ Heuristic Check: {'PASSED' if heuristic_perfect else 'FAILED'}")
            self.logger.info(f"🌍 Region Matches: {region_matches}/{total_addresses}")
            self.logger.info(f"🔍 API Validation: {api_result}")
            self.logger.info(f"{'='*80}")
            
            return overall_score
            
        except Exception as e:
            self.logger.error(f"❌ Error in mock validator validation: {e}")
            self.logger.exception("Full traceback:")
            return 0.0
    
    def process_all_countries(self, countries: List[str]):
        """Process all countries"""
        total_countries = len(countries)
        completed = 0
        skipped = 0
        
        self.logger.info(f"\n{'='*80}")
        self.logger.info(f"STARTING PROCESSING FOR {total_countries} COUNTRIES")
        self.logger.info(f"{'='*80}")
        
        start_time = time.time()
        
        for idx, country in enumerate(countries, 1):
            if self.interrupted:
                break
            
            # Skip countries with weak OSM house-number coverage
            if not country_has_osm_addressing(country):
                self.logger.warning(f"\n[{idx}/{total_countries}] ⚠️  Skipping {country} — very weak OSM house-number coverage")
                self.logger.warning(f"   This country cannot produce perfect addresses due to lack of OSM data")
                skipped += 1
                # Mark as skipped in cache
                self.cache_data['countries'][country] = {
                    'perfect_addresses': [],
                    'skipped': True,
                    'skip_reason': 'Weak OSM house-number coverage',
                    'last_updated': datetime.now().isoformat()
                }
                self._save_cache()
                continue
            
            self.logger.info(f"\n[{idx}/{total_countries}] Processing {country}...")
            
            try:
                perfect_addresses = self.process_country(country)
                completed += 1
                
                self.logger.info(f"✅ {country}: {len(perfect_addresses)} perfect addresses")
                
            except Exception as e:
                self.logger.error(f"❌ Error processing {country}: {e}")
                self.logger.exception("Full traceback:")
                continue
        
        elapsed = time.time() - start_time
        
        self.logger.info(f"\n{'='*80}")
        self.logger.info(f"PROCESSING COMPLETE")
        self.logger.info(f"{'='*80}")
        self.logger.info(f"Countries processed: {completed}/{total_countries}")
        self.logger.info(f"Countries skipped (weak OSM): {skipped}")
        self.logger.info(f"Total time: {elapsed:.2f} seconds")
        self.logger.info(f"Cache file: {self.cache_file}")
        self.logger.info(f"{'='*80}")


def main():
    """Main entry point"""
    logger, log_file = setup_logging()
    
    logger.info("Loading valid countries...")
    countries = get_all_valid_countries()
    
    if not countries:
        logger.error("❌ No valid countries found. Exiting.")
        sys.exit(1)
    
    logger.info(f"✅ Found {len(countries)} valid countries to process")
    
    # Initialize generator
    generator = AllCountriesAddressGenerator(
        cache_file=_cache_file,
        target_per_country=_target_per_country,
        logger=logger
    )
    
    # Process all countries
    generator.process_all_countries(countries)
    
    logger.info("✅ Script completed successfully")


if __name__ == "__main__":
    main()

