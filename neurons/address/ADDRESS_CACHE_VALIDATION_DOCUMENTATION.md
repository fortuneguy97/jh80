# Address Cache Validation Documentation

## Overview

The `generate_address_cache.py` script validates addresses using the **exact same validation functions** from `rewards.py`. This ensures that cached addresses will pass validation in the actual validator and achieve high scores.

**Key Features:**
- ✅ Uses same validation functions as `rewards.py`
- ✅ Three-stage validation pipeline (heuristic → region → API)
- ✅ Normalization-based duplicate detection (matches validator)
- ✅ Final batch validation with `_grade_address_variations()`
- ✅ Only accepts addresses with score >= 0.9

---

## Validation Flow

```
┌─────────────────────────────────────────────────────────────┐
│  Address Candidate Found                                     │
│  (from Overpass API or Nominatim reverse geocoding)        │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │  STAGE 1: Heuristic Check      │
        │  looks_like_address()          │
        └───────────────┬───────────────┘
                        │
            ┌───────────┴───────────┐
            │                       │
         PASS                    FAIL
            │                       │
            ▼                       ▼
┌───────────────────────┐   ┌──────────────────────┐
│  STAGE 2: Region      │   │  REJECTED             │
│  validate_address_    │   │  (No API call)        │
│  region()            │   └──────────────────────┘
└───────────┬───────────┘
            │
    ┌───────┴───────┐
    │               │
 PASS            FAIL
    │               │
    ▼               ▼
┌───────────────────────┐   ┌──────────────────────┐
│  STAGE 3: API          │   │  REJECTED             │
│  check_with_nominatim │   │  (No API call)        │
│  (score >= 0.9)      │   └──────────────────────┘
└───────────┬───────────┘
            │
    ┌───────┴───────┐
    │               │
 PASS            FAIL
(score>=0.9)   (score<0.9)
    │               │
    ▼               ▼
┌───────────────────────┐   ┌──────────────────────┐
│  DUPLICATE CHECK       │   │  REJECTED             │
│  (normalization-based) │   │  (Low score)          │
└───────────┬───────────┘   └──────────────────────┘
            │
    ┌───────┴───────┐
    │               │
 UNIQUE          DUPLICATE
    │               │
    ▼               ▼
┌───────────────────────┐   ┌──────────────────────┐
│  ADDED TO LIST         │   │  SKIPPED              │
│  (up to 15 addresses)  │   │  (Duplicate detected) │
└───────────────────────┘   └──────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────┐
│  FINAL BATCH VALIDATION                     │
│  _grade_address_variations()                │
│  (Tests all 15 addresses together)          │
└───────────────┬─────────────────────────────┘
                │
        ┌───────┴───────┐
        │               │
    PASS            FAIL
(score>=0.9)   (score<0.9)
        │               │
        ▼               ▼
┌───────────────┐   ┌───────────────┐
│  ACCEPTED     │   │  REJECTED     │
│  (Saved to    │   │  (Regenerate) │
│   cache)      │   │               │
└───────────────┘   └───────────────┘
```

---

## Stage 1: Heuristic Validation

**Function**: `looks_like_address(address: str) -> bool`  
**Location**: Lines 1200, 1423, 1289, 1512 in `generate_address_cache.py`  
**Source**: `MIID/validator/reward.py` (Lines 193-246)

### Purpose
Performs **structural validation** to ensure the address looks like a real address format.

### Validation Criteria

1. **Length Requirements**:
   - Minimum: 30 alphanumeric characters
   - Maximum: 300 alphanumeric characters
   - Must have at least 20 letters

2. **Character Requirements**:
   - Must contain at least one letter (a-zA-Z)
   - Must have at least 5 unique characters
   - Must contain at least one digit (0-9) in at least one comma-separated section

3. **Format Requirements**:
   - Must have at least **2 commas** (indicating multiple address components)
   - Example: `"123 Main St, City, Country"` ✓
   - Example: `"123 Main St"` ✗ (only 1 comma or less)

4. **Forbidden Characters**:
   - Not allowed: `` ` ``, `:`, `%`, `$`, `@`, `*`, `^`, `[`, `]`, `{`, `}`, `_`, `«`, `»`

### Code Example

```python
# Line 1200 in generate_address_cache.py
if not looks_like_address(display):
    stats["validation_failed"] += 1
    if verbose:
        print(f"     ❌ REJECTED: Failed 'looks_like_address' heuristic")
    continue  # Skip this address
```

### Examples

**✅ Valid Addresses**:
- `"115 New Cavendish Street, London W1T 5DU, United Kingdom"`
- `"223 William Street, Melbourne VIC 3000, Australia"`
- `"10, Rruga Shtojzavallet, Durrës, 2021, Albania"`

**❌ Invalid Addresses**:
- `"123 Main St"` (only 1 comma, needs 2+)
- `"Main Street"` (no numbers, too short)
- `"123 Main St@City, Country"` (forbidden character `@`)

---

## Stage 2: Region Validation

**Function**: `validate_address_region(generated_address: str, seed_address: str) -> bool`  
**Location**: Lines 1207, 1430, 818, 717 in `generate_address_cache.py`  
**Source**: `MIID/validator/reward.py` (Lines 633-683)

### Purpose
Ensures the generated address matches the **country or city** of the seed address.

### Validation Process

1. **Extract City and Country**:
   - Uses `extract_city_country()` to parse the generated address
   - Extracts the last comma-separated segment as the country
   - Validates city against GeoNames database

2. **Country Matching**:
   - Normalizes country names using `COUNTRY_MAPPING` dictionary
   - Handles variations like:
     - `"korea, south"` → `"south korea"`
     - `"cote d'ivoire"` → `"ivory coast"`
     - `"netherlands"` → `"the netherlands"`

3. **Matching Logic**:
   - **City Match**: Generated city exactly matches seed address (case-insensitive)
   - **Country Match**: Generated country exactly matches seed address (case-insensitive)
   - **Mapped Match**: Generated country matches normalized seed address via `COUNTRY_MAPPING`
   - **Returns `True`** if **any** of these matches succeed

### Code Example

```python
# Line 1207 in generate_address_cache.py
if not validate_address_region(display, country):
    stats["validation_failed"] += 1
    if verbose:
        print(f"     ❌ REJECTED: Failed region validation")
    continue  # Skip this address
```

### Examples

**✅ Valid Region Matches**:
- Seed: `"Albania"`, Generated: `"10, Rruga Shtojzavallet, Durrës, 2021, Albania"` ✓
- Seed: `"United Kingdom"`, Generated: `"115 New Cavendish Street, London, United Kingdom"` ✓

**❌ Invalid Region Matches**:
- Seed: `"Albania"`, Generated: `"123 Main St, Paris, France"` ✗ (wrong country)
- Seed: `"Albania"`, Generated: `"123 Main St"` ✗ (no city/country extracted)

---

## Stage 3: API Validation

**Function**: `validate_address_with_api(address: str, country: str) -> Tuple[bool, float]`  
**Location**: Lines 1214, 1437, 1297, 1520, 1633 in `generate_address_cache.py`  
**Internal Function**: `check_with_nominatim()` from `rewards.py` (Lines 285-404)

### Purpose
Validates addresses using the **Nominatim OpenStreetMap API** and returns a score based on bounding box precision.

### Validation Process

1. **API Call**:
   - Calls `check_with_nominatim()` from `rewards.py`
   - Uses Nominatim API to geocode the address
   - Returns a score based on bounding box area

2. **Score Calculation**:
   - **< 100 m²**: Score = **1.0** (very precise, likely a building)
   - **< 1,000 m²**: Score = **0.9** (precise, likely a small area)
   - **< 10,000 m²**: Score = **0.8** (moderate precision)
   - **< 100,000 m²**: Score = **0.7** (less precise)
   - **≥ 100,000 m²**: Score = **0.3** (very broad)

3. **Acceptance Criteria**:
   - Only accepts addresses with **score >= 0.9** (both 1.0 and 0.9)
   - Rejects addresses with score < 0.9

### Code Example

```python
# Line 1214 in generate_address_cache.py
is_valid, score = validate_address_with_api(display, country, verbose=verbose)

if is_valid and score >= 0.9:
    # Address passed API validation
    # Continue to duplicate check
else:
    stats["validation_failed"] += 1
    # Skip this address
    continue
```

### Examples

**✅ High Score (1.0)**:
- Address: `"115 New Cavendish Street, London, United Kingdom"`
- Bounding Box: 50 m² (very precise, likely a specific building)
- Score: **1.0** → Accepted

**✅ Medium Score (0.9)**:
- Address: `"Gangnam District, Seoul, South Korea"`
- Bounding Box: 500 m² (precise, likely a neighborhood)
- Score: **0.9** → Accepted

**❌ Low Score (0.3)**:
- Address: `"Paris, France"`
- Bounding Box: 150,000 m² (very broad, city-level)
- Score: **0.3** → Rejected (score < 0.9)

---

## Duplicate Detection

**Function**: `normalize_address_for_deduplication(addr: str) -> str`  
**Location**: Lines 1219, 1313, 1453, 1547, 1646 in `generate_address_cache.py`  
**Source**: `MIID/validator/cheat_detection.py` (Lines 121-169)

### Purpose
Detects duplicate addresses using **normalization-based matching**, exactly matching the validator's approach.

### Normalization Process

The normalization process consists of **5 steps**:

1. **Step 0**: Remove disallowed Unicode (currency, emoji, etc.)
2. **Step 1**: NFKD normalization + diacritic removal + lowercase
3. **Step 2**: Remove punctuation and symbols
4. **Step 3**: Transliterate to ASCII (handles Cyrillic, Arabic, etc.)
5. **Step 4**: Extract letters only, sort alphabetically, join

### Duplicate Checking Logic

```python
# Line 1219-1239 in generate_address_cache.py
# Step 1: Normalize address
normalized_display = normalize_address_for_deduplication(display)

# Step 2: Check normalized duplicate (matches validator)
if normalized_display in seen_normalized_addresses:
    stats["duplicates_skipped"] += 1
    continue  # Skip - duplicate detected

# Step 3: Check exact string match (for tracking)
if display in seen_addresses:
    stats["duplicates_skipped"] += 1
    continue  # Skip - exact duplicate

# Step 4: Add to lists
address_list.append(display)
seen_addresses.add(display)
seen_normalized_addresses.add(normalized_display)
```

### Examples

**Example 1: Same Street, Different House Numbers**

```
Address 1: "11, Rruga Jeronim de Rada, Kashar, 1050, Albania"
Address 2: "5, Rruga Jeronim de Rada, Kashar, 1050, Albania"
Address 3: "9, Rruga Jeronim de Rada, Kashar, 1050, Albania"
```

**Normalization**:
- All three normalize to: `"aaaaaaabddeeghiijklmnnorrrrrsu..."`

**Result**:
- ✅ Address 1: Added (first occurrence)
- ❌ Address 2: Skipped (normalizes to same as Address 1)
- ❌ Address 3: Skipped (normalizes to same as Address 1)

**Why**: House numbers are removed during normalization, so addresses on the same street normalize to the same string.

---

## Final Batch Validation

**Function**: `_grade_address_variations()`  
**Location**: Lines 1698-1754 in `generate_address_cache.py`  
**Source**: `MIID/validator/reward.py` (Lines 1885-2104)

### Purpose
Tests **all 15 addresses together** using the same validation logic as the validator. This ensures the addresses will score well in the actual validator.

### Validation Process

1. **Format Addresses**:
   ```python
   variations = {
       "Test Name": [
           ["Test Name", "1990-01-01", addr] for addr in results[:15]
       ]
   }
   ```

2. **Call Validator Function**:
   ```python
   validation_result = _grade_address_variations(
       variations=variations,
       seed_addresses=[country] * len(variations),
       miner_metrics={},
       validator_uid=101,
       miner_uid=501
   )
   ```

3. **Check Overall Score**:
   ```python
   overall_score = validation_result.get('overall_score', 0.0)
   
   if overall_score >= 0.9:
       # Accept addresses
       return results
   else:
       # Reject addresses - regenerate
       return []
   ```

### Acceptance Criteria

- **Overall Score >= 0.9**: Addresses are accepted and saved to cache
- **Overall Score < 0.9**: Addresses are rejected, script continues searching

### What It Validates

The `_grade_address_variations()` function performs:
- **Heuristic validation** for all addresses
- **Region validation** for all addresses
- **API validation** for up to 3 randomly selected addresses
- **Scoring** based on API results and validation passes

---

## Complete Validation Flow Example

### Scenario: Processing Address for Albania

```
1. Address Found:
   "11, Rruga Jeronim de Rada, Kashar, 1050, Albania"

2. Stage 1: Heuristic Check
   looks_like_address("11, Rruga Jeronim de Rada, Kashar, 1050, Albania")
   → ✓ PASS (has 2+ commas, numbers, letters, proper length)

3. Stage 2: Region Check
   validate_address_region("11, Rruga Jeronim de Rada, Kashar, 1050, Albania", "Albania")
   → ✓ PASS (country "Albania" matches seed)

4. Stage 3: API Check
   validate_address_with_api("11, Rruga Jeronim de Rada, Kashar, 1050, Albania", "Albania")
   → check_with_nominatim() → Score: 1.0 (area: 80 m²)
   → ✓ PASS (score >= 0.9)

5. Duplicate Check
   normalize_address_for_deduplication("11, Rruga Jeronim de Rada, Kashar, 1050, Albania")
   → "aaaaaaabddeeghiijklmnnorrrrrsu..."
   → Check if in seen_normalized_addresses
   → ✓ UNIQUE (not seen before)

6. Add to List
   address_list.append("11, Rruga Jeronim de Rada, Kashar, 1050, Albania")
   seen_addresses.add("11, Rruga Jeronim de Rada, Kashar, 1050, Albania")
   seen_normalized_addresses.add("aaaaaaabddeeghiijklmnnorrrrrsu...")
   → ✅ Address added successfully!

7. Final Batch Validation (after collecting 15 addresses)
   _grade_address_variations(variations, seed_addresses, ...)
   → overall_score: 0.95
   → ✓ PASS (score >= 0.9)
   → ✅ Addresses saved to cache
```

---

## Code Locations

### Validation Functions

| Function | Location in Script | Source File |
|----------|-------------------|-------------|
| `looks_like_address()` | Lines 1200, 1423, 1289, 1512 | `rewards.py` (193-246) |
| `validate_address_region()` | Lines 1207, 1430, 818, 717 | `rewards.py` (633-683) |
| `validate_address_with_api()` | Lines 1214, 1437, 1297, 1520, 1633 | `generate_address_cache.py` (849-940) |
| `check_with_nominatim()` | Called by `validate_address_with_api()` | `rewards.py` (285-404) |
| `normalize_address_for_deduplication()` | Lines 1219, 1313, 1453, 1547, 1646 | `cheat_detection.py` (121-169) |
| `_grade_address_variations()` | Lines 1717-1723 | `rewards.py` (1885-2104) |

### Validation Paths

The validation logic is applied in **5 different code paths**:

1. **Line ~1218**: Local node validation (USE_LOCAL_NODES_ONLY mode)
2. **Line ~1312**: Reverse geocoding from bbox (normal mode)
3. **Line ~1452**: Local node validation from cities (USE_LOCAL_NODES_ONLY mode)
4. **Line ~1546**: Reverse geocoding from cities (normal mode)
5. **Line ~1645**: Random sampling fallback

All paths use the **same validation logic** to ensure consistency.

---

## Key Differences from Simple Validation

### 1. **Strict Sequential Validation**
   - If Stage 1 fails, Stages 2 and 3 are **skipped**
   - If Stage 2 fails, Stage 3 is **skipped**
   - Prevents unnecessary API calls

### 2. **Score Threshold**
   - Only accepts addresses with **score >= 0.9** (both 1.0 and 0.9)
   - Rejects addresses with score < 0.9
   - Tracks `score_1_count` and `score_09_count` separately

### 3. **Normalization-Based Duplicate Detection**
   - Uses same normalization function as validator
   - Detects duplicates even with different house numbers
   - Prevents addresses that would cause penalties

### 4. **Final Batch Validation**
   - Tests all 15 addresses together
   - Uses exact same function as validator (`_grade_address_variations()`)
   - Rejects entire batch if overall score < 0.9

---

## Statistics Tracking

The script tracks validation statistics:

```python
stats = {
    "overpass_queries": 0,
    "nodes_fetched": 0,
    "local_validations": 0,
    "reverse_geocoded": 0,
    "validation_passed": 0,
    "validation_failed": 0,
    "duplicates_skipped": 0,
    "score_1_count": 0,  # Addresses with score 1.0
    "score_09_count": 0  # Addresses with score 0.9
}
```

### Example Output

```
📊 FINAL STATISTICS for Albania:
   ✅ Accepted: 15/15 addresses
   📊 Score distribution: 12 score 1.0, 3 score 0.9
   📡 Overpass queries: 5
   📦 Nodes fetched: 1,234
   🏠 Local validations: 8
   🔄 Reverse geocoded: 7
   ✅ Validation passed: 15
   ❌ Validation failed: 89
   🔁 Duplicates skipped: 12
```

---

## Benefits

### 1. **Exact Validator Matching**
   - Uses same validation functions as `rewards.py`
   - Ensures cached addresses will pass validation
   - Prevents surprises during actual validation

### 2. **High Quality Addresses**
   - Only accepts addresses with score >= 0.9
   - Ensures precise geocoding (small bounding boxes)
   - Final batch validation confirms quality

### 3. **Duplicate Prevention**
   - Normalization-based duplicate detection
   - Matches validator behavior exactly
   - Prevents duplicate penalties (0.0667 = 6.67%)

### 4. **Efficient Processing**
   - Sequential validation prevents unnecessary API calls
   - Early rejection for invalid addresses
   - Tracks statistics for monitoring

---

## Conclusion

The `generate_address_cache.py` script uses a **comprehensive three-stage validation pipeline** that:

1. ✅ Validates addresses using **exact same functions** as `rewards.py`
2. ✅ Performs **heuristic**, **region**, and **API validation**
3. ✅ Detects duplicates using **normalization-based matching**
4. ✅ Tests all addresses together with **final batch validation**
5. ✅ Only accepts addresses with **score >= 0.9**

This ensures that cached addresses will:
- ✅ Pass validation in the actual validator
- ✅ Achieve high scores (0.9 or 1.0)
- ✅ Not trigger duplicate penalties
- ✅ Match validator behavior exactly

---

## References

- **Main Script**: `generate_address_cache.py`
- **Validation Functions**: `MIID/validator/reward.py`
- **Duplicate Detection**: `MIID/validator/cheat_detection.py`
- **Address Validation Documentation**: `ADDRESS_VALIDATION_DOCUMENTATION.md`
- **Duplicate Detection Documentation**: `DUPLICATE_ADDRESS_DETECTION.md`





