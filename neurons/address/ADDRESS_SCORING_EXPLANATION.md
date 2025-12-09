# Address Scoring - Detailed Explanation

## Overview
Address validation is a **three-step process** that must pass in order. If any step fails, the address scores 0.0. Only addresses that pass all three steps proceed to API validation.

## Three-Step Validation Process

### Step 1: `looks_like_address()` - Heuristic Validation
**Purpose**: Check if the address looks like a real address format.

**Requirements** (ALL must pass):
1. **Length requirements**:
   - Minimum 30 characters (after removing non-word characters)
   - Maximum 300 characters
   - At least 20 letters (Latin and non-Latin Unicode)

2. **Format requirements**:
   - Must contain at least 2 commas (`,`) - address should have multiple parts
   - Must have at least 5 unique characters (not all the same)
   - Must contain at least one letter (not just numbers/symbols)

3. **Number requirements**:
   - At least one comma-separated section must contain numbers (0-9)
   - Numbers must be ASCII digits (0-9), not other numeric characters

4. **Forbidden characters**:
   - Cannot contain: `` ` ``, `:`, `%`, `$`, `@`, `*`, `^`, `[`, `]`, `{`, `}`, `_`, `«`, `»`

**Result**:
- ✅ **Pass**: Address looks valid → Proceed to Step 2
- ❌ **Fail**: Returns `False` → Address scores **0.0** (no further validation)

---

### Step 2: `validate_address_region()` - Region Matching
**Purpose**: Validate that the generated address matches the seed address's region (city or country).

**Requirements**:
1. **Extract city and country** from generated address using `extract_city_country()`
2. **Extract city and country** from seed address
3. **Match requirement**: At least ONE of the following must match:
   - Generated city == Seed address (exact match, case-insensitive)
   - Generated country == Seed address (exact match, case-insensitive)
   - Generated country == Normalized seed address (using COUNTRY_MAPPING)

**Special Cases**:
- **Disputed regions**: Special handling for "luhansk", "crimea", "donetsk", "west sahara", "western sahara"
  - If seed is a disputed region, check if that region name appears in generated address

**Country Normalization**:
- Uses `COUNTRY_MAPPING` to normalize country names
- Examples: "USA" → "united states", "UK" → "united kingdom", "Cote d'Ivoire" → "ivory coast"

**City Validation**:
- Uses `geonamescache` to verify city exists in the country
- Checks from right to left (excluding country)
- Validates against real city data

**Result**:
- ✅ **Pass**: Region matches → Proceed to Step 3 (API validation)
- ❌ **Fail**: Returns `False` → Address scores **0.0** (no API call made)

---

### Step 3: `check_with_nominatim()` - API Validation
**Purpose**: Validate address using Nominatim (OpenStreetMap) API and score based on precision.

**API Call Details**:
- **Endpoint**: `https://nominatim.openstreetmap.org/search`
- **Method**: GET request with address as query parameter
- **Timeout**: 5 seconds
- **User-Agent**: `YanezCompliance/{validator_uid}` (required by Nominatim)

**API Validation Process**:

1. **Get results** from Nominatim API
   - If no results → Return **0.0**

2. **Filter results** (all filters must pass):
   - **Place rank**: Must be ≥ 20 (excludes very general locations)
   - **Name check**: If `name` field exists, it must appear in the original address (case-insensitive)
   - **Number check**: Numbers in `display_name` must be a subset of numbers in original address
     - Prevents false matches (e.g., "123 Main St" matching "456 Main St")

3. **Calculate bounding box area**:
   - For each result, compute bounding box area in square meters
   - Uses smallest area for scoring

4. **Score based on smallest bounding box area**:
   ```
   Area < 100 m²      → Score: 1.0  (Very precise - building level)
   Area < 1,000 m²    → Score: 0.9  (Precise - block level)
   Area < 10,000 m²   → Score: 0.8  (Moderate - neighborhood level)
   Area < 100,000 m²  → Score: 0.7  (Less precise - district level)
   Area ≥ 100,000 m²  → Score: 0.3  (Very imprecise - city level)
   ```

**API Call Selection**:
- Randomly selects **up to 3 addresses** from all addresses that passed Steps 1 & 2
- Each selected address is validated with Nominatim API
- 1 second delay between API calls (rate limiting)

**API Results**:
- **SUCCESS**: All API calls pass → Use average score from all successful calls
- **TIMEOUT**: Some calls timeout → Score may be reduced
- **FAILED**: Any call fails → Base score = **0.3**

---

## Final Scoring

### Scoring Logic:
```python
# If any address fails Steps 1 or 2:
overall_score = 0.0  # No API call made

# If all addresses pass Steps 1 & 2:
if nominatim_failed_calls > 0 or len(nominatim_scores) == 0:
    base_score = 0.3  # Any failure = 0.3
else:
    base_score = sum(nominatim_scores) / len(nominatim_scores)  # Average of all API scores
```

### Score Ranges:
- **1.0**: Perfect - all addresses pass, API returns precise results (< 100 m²)
- **0.9**: Excellent - API returns precise results (< 1,000 m²)
- **0.8**: Good - API returns moderate precision (< 10,000 m²)
- **0.7**: Acceptable - API returns less precise results (< 100,000 m²)
- **0.3**: Poor - API fails or returns very imprecise results (≥ 100,000 m²)
- **0.0**: Failed - Address doesn't look like address or region doesn't match

---

## Address Format Requirements

### Minimum Format:
```
[Street/Number], [City/Area], [Country]
```

**Example valid formats**:
- `"123 Main Street, New York, United States"`
- `"115 New Cavendish Street, London W1T 5DU, United Kingdom"`
- `"223 William Street, Melbourne VIC 3000, Australia"`
- `"Rosenthaler Straße 1, 10119 Berlin, Germany"`
- `"3 Upper Alma Road, Rosebank, Cape Town, 7700, South Africa"`

### Requirements Summary:
1. **At least 2 commas** (separates street, city, country)
2. **At least 30 characters** total
3. **At least 20 letters**
4. **At least one number** in one section
5. **Country must match** seed address (or normalized equivalent)
6. **City must be real** (validated against geonames data)

---

## Country Mapping

The validator uses `COUNTRY_MAPPING` to normalize country names:

```python
COUNTRY_MAPPING = {
    "usa": "united states",
    "us": "united states",
    "united states of america": "united states",
    "uk": "united kingdom",
    "great britain": "united kingdom",
    "britain": "united kingdom",
    "uae": "united arab emirates",
    "korea, south": "south korea",
    "cote d'ivoire": "ivory coast",
    "côte d'ivoire": "ivory coast",
    "the gambia": "gambia",
    "netherlands": "the netherlands",
    "holland": "the netherlands",
    "congo, democratic republic of the": "democratic republic of the congo",
    "drc": "democratic republic of the congo",
    "burma": "myanmar",
    # ... and more
}
```

---

## Special Cases

### Disputed Regions:
- **Luhansk, Crimea, Donetsk, West Sahara, Western Sahara**
- If seed address is a disputed region, check if region name appears in generated address
- Bypasses normal city/country validation

### Two-Part Countries:
- Some countries have two-part names: "Congo, Republic of the"
- `extract_city_country()` handles this with `two_parts` flag
- Automatically detected if comma is in seed address

---

## Examples

### ✅ Valid Address (Passes All Steps):
```
Seed: "New York, USA"
Generated: "123 Broadway, Manhattan, New York, United States"

Step 1: ✅ Looks like address (has commas, numbers, letters, proper length)
Step 2: ✅ Region matches (city "New York" matches, country "United States" matches "USA")
Step 3: ✅ API validates → Returns precise location → Score: 1.0
```

### ❌ Invalid Address (Fails Step 1):
```
Seed: "New York, USA"
Generated: "123 Main St"

Step 1: ❌ Doesn't look like address (only 1 comma, too short)
Result: Score 0.0 (no further validation)
```

### ❌ Invalid Address (Fails Step 2):
```
Seed: "New York, USA"
Generated: "123 Main Street, London, United Kingdom"

Step 1: ✅ Looks like address
Step 2: ❌ Region doesn't match (city "London" ≠ "New York", country "United Kingdom" ≠ "USA")
Result: Score 0.0 (no API call made)
```

### ⚠️ Valid Address (Passes Steps 1 & 2, API Returns Imprecise):
```
Seed: "New York, USA"
Generated: "Broadway, New York, United States"

Step 1: ✅ Looks like address
Step 2: ✅ Region matches
Step 3: ⚠️ API validates but returns large bounding box (≥ 100,000 m²)
Result: Score 0.3 (imprecise location)
```

---

## Key Takeaways

1. **All three steps must pass** - failure at any step = 0.0 score
2. **Format is critical** - must have proper structure (commas, numbers, length)
3. **Region matching is strict** - city or country must match seed
4. **API precision matters** - smaller bounding box = higher score
5. **Only 3 addresses** are randomly selected for API validation (to save time)
6. **Country normalization** - use standard country names or mapped equivalents

---

## Integration Notes

- Address validation happens **after** name and DOB validation
- Address score contributes **70%** to overall miner reward
- Each name gets its own address variations
- All addresses for a name are checked, but only up to 3 are API-validated
- API calls have rate limiting (1 second delay between calls)

