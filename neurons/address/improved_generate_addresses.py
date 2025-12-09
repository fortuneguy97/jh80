#!/usr/bin/env python3
"""
improved_generate_addresses.py

Robust Gemini -> validator pipeline.

Requirements:
  - python >= 3.8
  - pip install google-generativeai requests
  - Make sure your local reward.py is accessible (update REWARD_PY_PATH if needed)
  - Set GEMINI_API_KEY environment variable before running

Usage:
  export GEMINI_API_KEY="..."
  python3 improved_generate_addresses.py --country "United Kingdom" --target 15 --output uk_perfect.json

Notes:
  - This script calls functions from MIID/validator/reward.py:
      check_with_nominatim, looks_like_address, validate_address_region, _grade_address_variations
    so it will behave exactly like your validator.
  - The script rate-limits between Nominatim calls using whatever check_with_nominatim implements.
"""

import os
import sys
import time
import json
import logging
import argparse
from typing import List, Dict, Any, Tuple
from pathlib import Path
import re
import math
import traceback

# Parse arguments BEFORE importing bittensor (to avoid conflicts)
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
        print("Usage: improved_generate_addresses.py [--country COUNTRY] [--target N] [--output FILE]")
        print("  --country COUNTRY  Country name (required)")
        print("  --target N         Target addresses per country (default: 15)")
        print("  --output FILE      Output JSON file (optional)")
        sys.exit(0)
    else:
        i += 1

# Temporarily clear sys.argv
_saved_argv = sys.argv
sys.argv = [sys.argv[0]]

# Add MIID validator to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
sys.path.insert(0, os.path.join(BASE_DIR, 'MIID', 'validator'))

# -------------------------
# Configurable constants
# -------------------------
MASTER_PROMPT_FILE = "master_prompt.txt"
BATCH_SIZE = 120           # how many candidates to request from Gemini per attempt
MAX_ATTEMPTS = 6           # attempts of generation/validation cycles before giving up
TARGET_PERFECT_DEFAULT = 15
RATE_LIMIT_SECONDS = 2.0   # between calls (script-level sleep) in addition to any internal delays

# -------------------------
# Setup logging
# -------------------------
log_dir = Path("logs")
log_dir.mkdir(parents=True, exist_ok=True)
timestamp = time.strftime("%Y%m%d_%H%M%S")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    handlers=[
        logging.FileHandler(log_dir / f"gen_addresses_{timestamp}.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("improved_generator")

# -------------------------
# Import reward functions from your local reward.py
# -------------------------
try:
    from reward import (
        looks_like_address,
        validate_address_region,
        check_with_nominatim,
        _grade_address_variations
    )
    logger.info(f"Loaded reward.py from MIID/validator/reward.py")
except Exception as e:
    logger.exception("Failed to import reward.py. Make sure the path is correct and file is executable.")
    raise

# Restore argv
sys.argv = _saved_argv

# -------------------------
# Gemini (google.generativeai) integration
# -------------------------
try:
    import google.generativeai as genai
    GEMINI_SDK = True
except Exception:
    GEMINI_SDK = False

def configure_gemini():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable not set.")
    if not GEMINI_SDK:
        raise RuntimeError("google-generativeai not installed. Run: pip install google-generativeai")
    genai.configure(api_key=api_key)
    # choose model with good deterministic generation
    model = genai.GenerativeModel("gemini-2.5-pro")
    return model

# -------------------------
# Prompt utilities
# -------------------------
def load_master_prompt() -> str:
    if not os.path.exists(MASTER_PROMPT_FILE):
        raise FileNotFoundError(f"{MASTER_PROMPT_FILE} missing. Run update_prompt.py to create it, or create manually.")
    with open(MASTER_PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read()

def sanitize_address(addr: str) -> str:
    """Light sanitization: strip, normalize whitespace, ensure ASCII where possible."""
    s = addr.strip()
    s = re.sub(r'\s+', ' ', s)
    # replace smart quotes etc:
    s = s.replace("'", "'").replace(""", '"').replace(""", '"')
    return s

# -------------------------
# Parsing Gemini output
# -------------------------
def parse_addresses_from_text(text: str) -> List[str]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out = []
    for line in lines:
        # remove leading numbering or bullets
        line = re.sub(r'^\d+[\.\)]\s*', '', line)
        line = re.sub(r'^[-\*\u2022]\s*', '', line)
        line = sanitize_address(line)
        # quick format filter: must have at least 3 commas (house/street, city, postcode, country)
        if line.count(",") >= 3:
            out.append(line)
    return out

# -------------------------
# Validation wrapper
# -------------------------
def validate_candidate(address: str, country_seed: str, validator_uid: int = 101, miner_uid: int = 501) -> Tuple[bool, float, Dict[str,Any]]:
    """
    Returns:
      is_perfect (bool), api_score (float), details (dict)
    uses functions from reward.py (your implementation).
    """
    details = {
        "address": address,
        "heuristic": False,
        "region": False,
        "api_result": None,
        "api_score": 0.0,
        "api_area": None,
    }

    try:
        # 1. heuristic
        details["heuristic"] = bool(looks_like_address(address))
        if not details["heuristic"]:
            return False, 0.0, details

        # 2. region
        details["region"] = bool(validate_address_region(address, country_seed))
        if not details["region"]:
            return False, 0.0, details

        # 3. nominatum / overpass validation
        api_res = check_with_nominatim(
            address=address,
            validator_uid=validator_uid,
            miner_uid=miner_uid,
            seed_address=country_seed,
            seed_name="generator"
        )
        # check_with_nominatim returns dict on success, "TIMEOUT" or similar otherwise
        if isinstance(api_res, dict):
            details["api_result"] = "SUCCESS"
            details["api_score"] = float(api_res.get("score", 0.0))
            details["api_area"] = float(api_res.get("min_area", 0.0)) if api_res.get("min_area") is not None else None
            is_perfect = details["api_score"] >= 0.99
            return is_perfect, details["api_score"], details
        elif api_res == "TIMEOUT":
            details["api_result"] = "TIMEOUT"
            return False, 0.0, details
        else:
            details["api_result"] = "FAILED"
            return False, 0.0, details
    except Exception:
        logger.exception("Exception during validation of address: %s", address)
        return False, 0.0, details

# -------------------------
# Generation + validate loop
# -------------------------
def generate_candidates_and_validate(model, country: str, target_perfect: int) -> Tuple[List[str], Dict[str,Any]]:
    """Main loop: generate batches and validate until target reached or attempts exhausted."""
    logger.info("=" * 80)
    logger.info("STARTING ADDRESS GENERATION FOR: %s", country)
    logger.info("=" * 80)
    logger.info("Target: %d perfect addresses", target_perfect)
    logger.info("Max attempts: %d", MAX_ATTEMPTS)
    logger.info("Batch size: %d (increases per attempt)", BATCH_SIZE)
    logger.info("Rate limit: %.1f seconds between Nominatim calls", RATE_LIMIT_SECONDS)
    
    master_prompt = load_master_prompt()
    logger.info("✅ Loaded master prompt (%d characters)", len(master_prompt))
    
    # inject country-specific line so prompt is explicit
    prompt_for_country = master_prompt + f"\n\nCOUNTRY = {country}\nReturn candidates exactly in the format: \"{{house_number}} {{street}}, {{city}}, {{postcode}}, {{country}}\" one per line.\n"
    logger.info("📝 Prompt prepared for country: %s", country)
    logger.info("   Total prompt length: %d characters", len(prompt_for_country))

    perfect_addresses: List[str] = []
    tried_addresses = set()
    stats = {"attempts": 0, "candidates_tested": 0, "perfect_found": 0, "heuristic_passed": 0, "region_passed": 0, "api_passed": 0, "api_failed": 0, "api_timeout": 0}

    for attempt in range(1, MAX_ATTEMPTS + 1):
        stats["attempts"] += 1
        to_request = BATCH_SIZE * attempt  # increase batch on retries
        logger.info("")
        logger.info("-" * 80)
        logger.info("🔄 ATTEMPT %d/%d", attempt, MAX_ATTEMPTS)
        logger.info("-" * 80)
        logger.info("Requesting %d candidate addresses from Gemini for country: %s", to_request, country)
        logger.info("Current progress: %d/%d perfect addresses found", len(perfect_addresses), target_perfect)

        try:
            logger.info("📡 Sending request to Gemini API...")
            start_time = time.time()
            resp = model.generate_content(
                prompt_for_country,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=8192 if to_request > 100 else 4096,
                    temperature=0.25,   # keep temperature low to prefer real patterns
                )
            )
            elapsed = time.time() - start_time
            logger.info("✅ Gemini API response received in %.2f seconds", elapsed)
            
            text = resp.text
            logger.info("📄 Response text length: %d characters", len(text))
            candidates = parse_addresses_from_text(text)
            logger.info("✅ Parsed %d candidate addresses from Gemini response", len(candidates))
            
            if len(candidates) == 0:
                logger.warning("⚠️  No addresses parsed from response. Response preview: %s", text[:200] if text else "Empty")
        except Exception as e:
            logger.exception("❌ Gemini request failed on attempt %d: %s", attempt, str(e))
            candidates = []

        # dedupe and filter
        unique_candidates = []
        for c in candidates:
            if c in tried_addresses:
                continue
            tried_addresses.add(c)
            unique_candidates.append(c)

        logger.info("")
        logger.info("🔍 VALIDATING %d UNIQUE CANDIDATES", len(unique_candidates))
        logger.info("   (This will take approximately %.1f minutes due to rate limiting)", 
                   (len(unique_candidates) * RATE_LIMIT_SECONDS) / 60.0)
        
        validation_start = time.time()
        for idx, addr in enumerate(unique_candidates, 1):
            stats["candidates_tested"] += 1
            logger.info("")
            logger.info("  [%d/%d] Testing: %s", idx, len(unique_candidates), addr[:70] + "..." if len(addr) > 70 else addr)
            
            validation_step_start = time.time()
            is_perfect, score, details = validate_candidate(addr, country)
            validation_step_elapsed = time.time() - validation_step_start
            
            # Track statistics
            if details.get("heuristic"):
                stats["heuristic_passed"] += 1
            if details.get("region"):
                stats["region_passed"] += 1
            if details.get("api_result") == "SUCCESS":
                stats["api_passed"] += 1
                if is_perfect:
                    perfect_addresses.append(addr)
                    stats["perfect_found"] += 1
                    logger.info("     ✅ PERFECT! Score=%.4f, Area=%.2f m² (validation took %.2fs)", 
                               score, details.get("api_area", 0), validation_step_elapsed)
                    logger.info("     Progress: %d/%d perfect addresses", len(perfect_addresses), target_perfect)
                    if len(perfect_addresses) >= target_perfect:
                        total_elapsed = time.time() - validation_start
                        logger.info("")
                        logger.info("🎉 TARGET REACHED! Found %d perfect addresses in %.1f seconds", 
                                   target_perfect, total_elapsed)
                        return perfect_addresses, stats
                else:
                    logger.info("     ⚠️  Good but not perfect: Score=%.4f (validation took %.2fs)", 
                               score, validation_step_elapsed)
            elif details.get("api_result") == "TIMEOUT":
                stats["api_timeout"] += 1
                logger.warning("     ⏱️  API TIMEOUT (validation took %.2fs)", validation_step_elapsed)
            else:
                stats["api_failed"] += 1
                failure_reason = []
                if not details.get("heuristic"):
                    failure_reason.append("heuristic")
                if not details.get("region"):
                    failure_reason.append("region")
                if details.get("api_result") != "SUCCESS":
                    failure_reason.append("api")
                logger.info("     ❌ Failed: %s (validation took %.2fs)", 
                           ", ".join(failure_reason) if failure_reason else "unknown", 
                           validation_step_elapsed)

            # basic rate limit to avoid hitting remote too fast
            logger.debug("     ⏳ Waiting %.1f seconds before next validation...", RATE_LIMIT_SECONDS)
            time.sleep(RATE_LIMIT_SECONDS)

        # if not enough found continue attempts
        validation_elapsed = time.time() - validation_start
        logger.info("")
        logger.info("📊 ATTEMPT %d SUMMARY", attempt)
        logger.info("   Validation time: %.1f seconds (%.1f minutes)", validation_elapsed, validation_elapsed / 60.0)
        logger.info("   Candidates tested: %d", stats["candidates_tested"])
        logger.info("   Heuristic passed: %d", stats["heuristic_passed"])
        logger.info("   Region passed: %d", stats["region_passed"])
        logger.info("   API passed: %d", stats["api_passed"])
        logger.info("   API failed: %d", stats["api_failed"])
        logger.info("   API timeout: %d", stats["api_timeout"])
        logger.info("   Perfect addresses found: %d/%d", len(perfect_addresses), target_perfect)
        
        if len(perfect_addresses) >= target_perfect:
            break
        
        if attempt < MAX_ATTEMPTS:
            logger.info("")
            logger.info("⏭️  Continuing to attempt %d (will request %d addresses)", 
                       attempt + 1, BATCH_SIZE * (attempt + 1))

    total_elapsed = time.time() - validation_start if 'validation_start' in locals() else 0
    logger.warning("")
    logger.warning("=" * 80)
    logger.warning("FINISHED ALL ATTEMPTS")
    logger.warning("=" * 80)
    logger.warning("Perfect addresses found: %d/%d", len(perfect_addresses), target_perfect)
    logger.warning("Total candidates tested: %d", stats["candidates_tested"])
    logger.warning("Total validation time: %.1f seconds (%.1f minutes)", total_elapsed, total_elapsed / 60.0)
    logger.warning("=" * 80)
    return perfect_addresses, stats

# -------------------------
# Entrypoint
# -------------------------
def main():
    parser = argparse.ArgumentParser(description="Improved Address Generator + Validator")
    parser.add_argument("--country", required=True, help="Country name (seed country) e.g. 'United Kingdom'")
    parser.add_argument("--target", type=int, default=TARGET_PERFECT_DEFAULT, help="Target perfect addresses (default 15)")
    parser.add_argument("--output", default=None, help="Output JSON file (optional)")
    parser.add_argument("--validator-uid", type=int, default=101)
    parser.add_argument("--miner-uid", type=int, default=501)
    args = parser.parse_args()

    try:
        model = configure_gemini()
    except Exception:
        logger.exception("Could not configure Gemini SDK. Aborting.")
        sys.exit(1)

    try:
        perfect_addresses, stats = generate_candidates_and_validate(model, args.country, args.target)
        result = {
            "country": args.country,
            "perfect_addresses": perfect_addresses,
            "count": len(perfect_addresses),
            "stats": stats,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            logger.info("Saved results to %s", args.output)
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        sys.exit(1)
    except Exception:
        logger.exception("Fatal error in main")
        sys.exit(1)

if __name__ == "__main__":
    print("Starting improved_generate_addresses.py...", file=sys.stderr)
    print(f"Arguments: {sys.argv}", file=sys.stderr)
    try:
        main()
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

