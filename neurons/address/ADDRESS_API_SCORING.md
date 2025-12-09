# Address API Scoring Analysis

## How Addresses Are Scored

### Step 1: Pre-API Validation (Must Pass Both)
1. **Format Validation** (`looks_like_address()`)
   - Address length: 30-300 characters
   - Letter count: ≥20
   - Has numbers in comma sections
   - Comma count: ≥2
   - No disallowed characters
   - ✅ **Gemini: 100% pass rate**

2. **Region Validation** (`validate_address_region()`)
   - City/country must match seed address
   - ⚠️ **Gemini: 0% pass rate** (validator bug - see REGION_VALIDATION_ISSUE.md)

**If either fails → API is NOT called → Score = 0.0**

### Step 2: API Validation (Only if Step 1 passes)
- Validator randomly selects **up to 3 addresses** for API validation
- Calls Nominatim (OpenStreetMap) geocoding API
- Each address gets a score based on **bounding box area**:

| Bounding Box Area | Score |
|-------------------|-------|
| < 100 m²          | **1.0** (FULL SCORE) ✅ |
| < 1,000 m²        | 0.9 |
| < 10,000 m²       | 0.8 |
| < 100,000 m²      | 0.7 |
| ≥ 100,000 m²      | 0.3 |

### Step 3: Final Score Calculation
- **If any API call fails**: `base_score = 0.3`
- **If all API calls succeed**: `base_score = average of all API scores`

## To Get Full Score (1.0) from API

Addresses need to:
1. ✅ Pass format validation (Gemini: 100%)
2. ⚠️ Pass region validation (Gemini: 0% - validator bug)
3. ✅ Pass API validation with bounding box < 100 m²

**Current Status:**
- Format: ✅ 100% (perfect)
- Region: ⚠️ 0% (validator bug - affects all miners)
- API: ✅ Should work (addresses are real and geocodable)

## API Validation Requirements

For an address to pass API validation:
1. Must be geocodable on OpenStreetMap
2. Must have `place_rank >= 20`
3. The `name` field from API must be in the address
4. Numbers in `display_name` must match numbers in original address
5. Bounding box area determines score

## Gemini Address Quality

Gemini generates:
- ✅ Real, actual addresses (e.g., "225 Liberty Street, Financial District, New York, NY 10281, United States")
- ✅ Geocodable addresses (should pass Nominatim API)
- ✅ Specific addresses (should have small bounding boxes)
- ✅ Proper format (passes all format checks)

**Expected API Score:** Should be **0.9-1.0** (high precision addresses)

## Current Limitation

The **region validation bug** prevents addresses from reaching the API validation step. Once that's fixed (or if validator accepts addresses that pass format validation), Gemini addresses should score **0.9-1.0** from the API.

