# Address Validation Process Documentation

## Overview

The address validation process in `rewards.py` is a **three-stage validation pipeline** that ensures generated addresses are:
1. **Structurally valid** (looks like a real address)
2. **Regionally correct** (matches the seed address's country/city)
3. **Geographically verified** (validated via Nominatim API)

The validation is performed in `_grade_address_variations()` function (lines 1885-2104 in `rewards.py`).

---

## Validation Flow

```
┌─────────────────────────────────────────────────────────────┐
│  Address Variation Submitted                                │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │  Stage 1: Heuristic Check     │
        │  looks_like_address()         │
        └───────────────┬───────────────┘
                        │
            ┌───────────┴───────────┐
            │                       │
         PASS                    FAIL
            │                       │
            ▼                       ▼
┌───────────────────────┐   ┌──────────────────────┐
│  Stage 2: Region      │   │  Return Score: 0.0    │
│  validate_address_   │   │  (No API call)        │
│  region()            │   └──────────────────────┘
└───────────┬───────────┘
            │
    ┌───────┴───────┐
    │               │
 PASS            FAIL
    │               │
    ▼               ▼
┌───────────────────────┐   ┌──────────────────────┐
│  Stage 3: API         │   │  Return Score: 0.0    │
│  check_with_nominatim │   │  (No API call)        │
│  (up to 3 addresses) │   └──────────────────────┘
└───────────┬───────────┘
            │
            ▼
    ┌───────────────┐
    │  Final Score  │
    │  (0.3 - 1.0)  │
    └───────────────┘
```

---

## Stage 1: Heuristic Validation (`looks_like_address`)

**Function**: `looks_like_address(address: str) -> bool`  
**Location**: Lines 193-246 in `rewards.py`

This function performs **structural validation** to ensure the address looks like a real address format.

### Validation Criteria

1. **Length Requirements**:
   - Minimum: 30 alphanumeric characters (after removing non-word chars)
   - Maximum: 300 alphanumeric characters
   - Must have at least 20 letters (Unicode letters included)

2. **Character Requirements**:
   - Must contain at least one letter (a-zA-Z)
   - Must have at least 5 unique characters
   - Must contain at least one digit (0-9) in at least one comma-separated section

3. **Format Requirements**:
   - Must have at least **2 commas** (indicating multiple address components)
   - Example: `"123 Main St, City, Country"` ✓
   - Example: `"123 Main St"` ✗ (only 1 comma or less)

4. **Forbidden Characters**:
   - The following special characters are **not allowed**:
     - `` ` ``, `:`, `%`, `$`, `@`, `*`, `^`, `[`, `]`, `{`, `}`, `_`, `«`, `»`
   - Example: `"123 Main St, City, Country"` ✓
   - Example: `"123 Main St@City, Country"` ✗ (contains `@`)

### Examples

**✅ Valid Addresses**:
- `"115 New Cavendish Street, London W1T 5DU, United Kingdom"`
- `"223 William Street, Melbourne VIC 3000, Australia"`
- `"Rosenthaler Straße 1, 10119 Berlin, Germany"`
- `"3 Upper Alma Road, Rosebank, Cape Town, 7700, South Africa"`

**❌ Invalid Addresses**:
- `"123 Main St"` (only 1 comma, needs 2+)
- `"Main Street"` (no numbers, too short)
- `"123"` (no letters, too short)
- `"123 Main St, City"` (only 1 comma)
- `"123 Main St@City, Country"` (forbidden character `@`)

---

## Stage 2: Region Validation (`validate_address_region`)

**Function**: `validate_address_region(generated_address: str, seed_address: str) -> bool`  
**Location**: Lines 633-683 in `rewards.py`

This function ensures the generated address matches the **country or city** of the seed address.

### Validation Process

1. **Extract City and Country**:
   - Uses `extract_city_country()` to parse the generated address
   - Extracts the last comma-separated segment as the country
   - Validates city against GeoNames database to ensure it's a real city in that country

2. **Country Matching**:
   - Normalizes country names using `COUNTRY_MAPPING` dictionary
   - Handles variations like:
     - `"korea, south"` → `"south korea"`
     - `"cote d'ivoire"` → `"ivory coast"`
     - `"netherlands"` → `"the netherlands"`
     - `"the gambia"` → `"gambia"`

3. **Special Region Handling**:
   - Special handling for disputed regions not in GeoNames:
     - `"luhansk"`, `"crimea"`, `"donetsk"`, `"west sahara"`, `"western sahara"`
   - For these regions, checks if the region name appears in the generated address

4. **Matching Logic**:
   - **City Match**: Generated city exactly matches seed address (case-insensitive)
   - **Country Match**: Generated country exactly matches seed address (case-insensitive)
   - **Mapped Match**: Generated country matches normalized seed address via `COUNTRY_MAPPING`
   - **Returns `True`** if **any** of these matches succeed

### Examples

**✅ Valid Region Matches**:
- Seed: `"Albania"`, Generated: `"10, Rruga Shtojzavallet, Durrës, 2021, Albania"` ✓
- Seed: `"United Kingdom"`, Generated: `"115 New Cavendish Street, London, United Kingdom"` ✓
- Seed: `"South Korea"`, Generated: `"123 Gangnam Street, Seoul, South Korea"` ✓

**❌ Invalid Region Matches**:
- Seed: `"Albania"`, Generated: `"123 Main St, Paris, France"` ✗ (wrong country)
- Seed: `"United Kingdom"`, Generated: `"115 New Cavendish Street, Berlin, Germany"` ✗ (wrong country)
- Seed: `"Albania"`, Generated: `"123 Main St"` ✗ (no city/country extracted)

---

## Stage 3: API Validation (`check_with_nominatim`)

**Function**: `check_with_nominatim(address: str, validator_uid: int, miner_uid: int, seed_address: str, seed_name: str)`  
**Location**: Lines 285-404 in `rewards.py`

This function validates addresses using the **Nominatim OpenStreetMap API** and returns a score based on bounding box precision.

### API Call Process

1. **Request Setup**:
   - URL: `https://nominatim.openstreetmap.org/search`
   - Parameters: `{"q": address, "format": "json"}`
   - User-Agent: `"YanezCompliance/{validator_uid} (https://yanezcompliance.com; omar@yanezcompliance.com)"`
   - Timeout: 5 seconds
   - Supports proxy via `PROXY_URL` environment variable

2. **Response Handling**:
   - **HTTP 403**: Rate limited or blocked → Returns `0.0`
   - **HTTP 200**: Parse JSON results
   - **No Results**: Returns `0.0`
   - **Timeout**: Returns `"TIMEOUT"`

3. **Result Filtering**:
   - **Place Rank**: Must be ≥ 20 (filters out very broad results)
   - **Name Match**: Result's `name` field must appear in the original address (case-insensitive)
   - **Number Match**: Numbers in `display_name` must be a subset of numbers in original address
     - Prevents false matches with different house numbers

4. **Bounding Box Scoring**:
   - Calculates bounding box area in square meters for all results
   - Uses the **smallest area** for scoring (most precise result)
   - Scoring based on area:
     - `< 100 m²`: Score = **1.0** (very precise, likely a building)
     - `< 1,000 m²`: Score = **0.9** (precise, likely a small area)
     - `< 10,000 m²`: Score = **0.8** (moderate precision)
     - `< 100,000 m²`: Score = **0.7** (less precise, likely a neighborhood)
     - `≥ 100,000 m²`: Score = **0.3** (very broad, likely a city/region)

### API Validation Strategy

- **Up to 3 addresses** are randomly selected from all addresses that passed Stages 1 and 2
- **1 second delay** between API calls to prevent rate limiting
- **Average score** of all successful API calls is used as the final base score
- If **any API call fails** (returns 0.0), the base score is set to **0.3**
- If **all API calls succeed**, the base score is the average of all scores

### Examples

**High Score (1.0)**:
- Address: `"115 New Cavendish Street, London, United Kingdom"`
- Bounding Box: 50 m² (very precise, likely a specific building)
- Score: **1.0**

**Medium Score (0.8)**:
- Address: `"Gangnam District, Seoul, South Korea"`
- Bounding Box: 5,000 m² (moderate precision, likely a neighborhood)
- Score: **0.8**

**Low Score (0.3)**:
- Address: `"Paris, France"`
- Bounding Box: 150,000 m² (very broad, city-level)
- Score: **0.3**

---

## Complete Validation Flow in `_grade_address_variations`

**Function**: `_grade_address_variations()`  
**Location**: Lines 1885-2104 in `rewards.py`

### Step-by-Step Process

1. **Collect All Addresses**:
   - Extracts address variations (index 2) from each `[name_var, dob_var, address_var]` array
   - Maps each address to its corresponding seed address

2. **Stage 1: Heuristic Validation** (for each address):
   - Calls `looks_like_address(address)`
   - If **any address fails**, sets `heuristic_perfect = False`

3. **Stage 2: Region Validation** (for each address):
   - Only validates addresses that passed Stage 1
   - Calls `validate_address_region(address, seed_address)`
   - If **any address fails**, sets `heuristic_perfect = False`
   - Tracks `region_matches` count

4. **Early Exit**:
   - If `heuristic_perfect = False`, returns immediately:
     ```python
     {
         "overall_score": 0.0,
         "heuristic_perfect": False,
         "api_result": False,
         "region_matches": region_matches,
         "total_addresses": len(all_addresses),
         "base_score": 0.0
     }
     ```
   - **No API calls are made** if heuristic validation fails

5. **Stage 3: API Validation** (only if all addresses passed Stages 1 & 2):
   - Randomly selects **up to 3 addresses** from validated addresses
   - Calls `check_with_nominatim()` for each selected address
   - Waits 1 second between calls
   - Collects scores from successful API calls

6. **Final Scoring**:
   - If **any API call failed** or **no successful calls**: `base_score = 0.3`
   - Otherwise: `base_score = average(nominatim_scores)`
   - Returns:
     ```python
     {
         "overall_score": base_score,
         "heuristic_perfect": True,
         "api_result": "SUCCESS" | "FAILED" | "TIMEOUT",
         "region_matches": region_matches,
         "total_addresses": len(all_addresses),
         "detailed_breakdown": {...}
     }
     ```

---

## Scoring Summary

| Condition | Score | Notes |
|-----------|-------|-------|
| **Stage 1 fails** | **0.0** | Address doesn't look like a real address |
| **Stage 2 fails** | **0.0** | Address doesn't match seed region |
| **Stage 3: All API calls fail** | **0.3** | API validation failed |
| **Stage 3: API timeout** | **0.3** | API timed out |
| **Stage 3: API success (area < 100 m²)** | **1.0** | Very precise location |
| **Stage 3: API success (area < 1,000 m²)** | **0.9** | Precise location |
| **Stage 3: API success (area < 10,000 m²)** | **0.8** | Moderate precision |
| **Stage 3: API success (area < 100,000 m²)** | **0.7** | Less precise |
| **Stage 3: API success (area ≥ 100,000 m²)** | **0.3** | Very broad location |

---

## Important Notes

### 1. **Strict Validation Order**
   - Validation is **strict and sequential**
   - If Stage 1 fails, Stages 2 and 3 are **skipped**
   - If Stage 2 fails, Stage 3 is **skipped**
   - This prevents unnecessary API calls

### 2. **API Rate Limiting**
   - Nominatim API has strict rate limits
   - 1 second delay between calls
   - HTTP 403 errors indicate rate limiting or blocking
   - Proper User-Agent header is required

### 3. **Address Duplication Detection**
   - Addresses are normalized using `normalize_address_for_deduplication()` in `cheat_detection.py`
   - Normalization removes house numbers, punctuation, and normalizes text
   - Duplicate addresses (after normalization) trigger penalties in post-processing

### 4. **Special Region Handling**
   - Disputed regions (Luhansk, Crimea, Donetsk, West Sahara) have special validation
   - These regions may not be in GeoNames database
   - Validation checks if region name appears in generated address

### 5. **Country Name Normalization**
   - `COUNTRY_MAPPING` handles country name variations
   - Examples: `"korea, south"` → `"south korea"`, `"netherlands"` → `"the netherlands"`
   - Ensures consistent country matching

---

## Code References

- **Main Validation Function**: `_grade_address_variations()` - Lines 1885-2104
- **Heuristic Check**: `looks_like_address()` - Lines 193-246
- **Region Validation**: `validate_address_region()` - Lines 633-683
- **City/Country Extraction**: `extract_city_country()` - Lines 458-555
- **API Validation**: `check_with_nominatim()` - Lines 285-404
- **Bounding Box Calculation**: `compute_bounding_box_areas_meters()` - Lines 248-282
- **Address Normalization**: `normalize_address_for_deduplication()` - Lines 121-165 in `cheat_detection.py`

---

## Example Validation Flow

### Example 1: Perfect Address

**Input**:
- Seed Address: `"Albania"`
- Generated Address: `"10, Rruga Shtojzavallet, Durrës, 2021, Albania"`

**Validation**:
1. **Stage 1**: ✓ Passes (has 2+ commas, numbers, letters, proper length)
2. **Stage 2**: ✓ Passes (country "Albania" matches seed)
3. **Stage 3**: ✓ API returns bounding box area = 80 m² → Score = 1.0

**Result**: `overall_score = 1.0`

---

### Example 2: Invalid Format

**Input**:
- Seed Address: `"Albania"`
- Generated Address: `"123 Main St"`

**Validation**:
1. **Stage 1**: ✗ Fails (only 1 comma, needs 2+)

**Result**: `overall_score = 0.0` (no API call made)

---

### Example 3: Wrong Region

**Input**:
- Seed Address: `"Albania"`
- Generated Address: `"115 New Cavendish Street, London, United Kingdom"`

**Validation**:
1. **Stage 1**: ✓ Passes
2. **Stage 2**: ✗ Fails (country "United Kingdom" doesn't match "Albania")

**Result**: `overall_score = 0.0` (no API call made)

---

### Example 4: API Failure

**Input**:
- Seed Address: `"Albania"`
- Generated Address: `"10, Rruga Shtojzavallet, Durrës, 2021, Albania"`

**Validation**:
1. **Stage 1**: ✓ Passes
2. **Stage 2**: ✓ Passes
3. **Stage 3**: ✗ API returns HTTP 403 (rate limited)

**Result**: `overall_score = 0.3` (API failure)

---

## Best Practices for Address Generation

1. **Format Requirements**:
   - Always include at least **2 commas** (e.g., `"Street, City, Country"`)
   - Include **house/street numbers** in at least one section
   - Ensure minimum **30 alphanumeric characters** and **20 letters**

2. **Region Matching**:
   - **Always match the seed address's country**
   - Use real city names that exist in that country (validated via GeoNames)
   - Use normalized country names from `COUNTRY_MAPPING`

3. **API Optimization**:
   - Use **specific addresses** (street + number) for higher scores
   - Avoid very broad addresses (city-only) which score 0.3
   - Ensure addresses are geocodable by Nominatim

4. **Avoid Duplicates**:
   - Use addresses from **different streets** to avoid normalization duplicates
   - Check normalization before assigning addresses
   - House numbers alone don't prevent duplicates (they're removed during normalization)

---

## Conclusion

The address validation process is a **three-stage pipeline** that ensures:
- **Structural validity** (looks like a real address)
- **Regional correctness** (matches seed address)
- **Geographic verification** (validated via API)

The strict sequential validation prevents unnecessary API calls and ensures only high-quality addresses receive high scores.





