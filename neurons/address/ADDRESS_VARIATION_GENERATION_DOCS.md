# Address Variation Generation Documentation

## Overview

The `generate_address_variations_from_cache.py` script generates unique address variations from existing addresses in `normalized_address_cache.json` for countries that have fewer than 15 addresses. All generated addresses must pass **4 strict validations** before being added to `new_addresses_variations.json`.

---

## Purpose

- **Input**: Countries with < 15 addresses in `normalized_address_cache.json`
- **Output**: Unique address variations that pass all validations
- **Goal**: Expand address pools for countries that need more addresses

---

## How It Works

### Step 1: Identify Target Countries

The script scans `normalized_address_cache.json` and identifies all countries with fewer than 15 addresses:

```python
for country, addresses in addresses_by_country.items():
    count = len(addresses)
    if count > 0 and count < 15:
        countries_to_process.append((country, addresses))
```

**Example:**
- Afghanistan: 3 addresses → **Process**
- Czechia: 15 addresses → **Skip**
- Andorra: 13 addresses → **Process**

---

### Step 2: Extract Components from Nominatim

For each address in a target country, the script:

1. **Queries Nominatim API** to get detailed address components
2. **Extracts components** from the first result:
   - `road` (street name)
   - `city`
   - `postcode`
   - `country`
   - `suburb`
   - `residential`
   - `county`
   - `state`

**Example:**

**Input Address:**
```
Seh Aqrab Road, Kabul, 1006, Afghanistan
```

**Nominatim Response Components:**
```json
{
  "road": "Seh Aqrab Road",
  "city": "Kabul",
  "postcode": "1006",
  "country": "Afghanistan",
  "suburb": "ناحیه سوم",
  "residential": "Nahri Darsan",
  "county": "کابل ښاروالۍ",
  "state": "ولایت كابل"
}
```

---

### Step 3: Generate Variations

The script generates variations by **combining components** in different orders and combinations.

#### Variation Strategy

**Base Variation:**
```
{road}, {city}, {postcode}, {country}
```

**Single Extra Component:**
```
{road}, {extra} {city}, {postcode}, {country}
{road}, {city}, {extra} {postcode}, {country}
```

**Multiple Extra Components:**
```
{road}, {extra1} {city}, {postcode}, {extra2}, {country}
```

**Example from Afghanistan:**

**Original Address:**
```
Seh Aqrab Road, Kabul, 1006, Afghanistan
```

**Extracted Components:**
- Road: `Seh Aqrab Road`
- City: `Kabul` (کابل)
- Postcode: `1006`
- Country: `Afghanistan`
- Extra components:
  - `ناحیه سوم` (suburb)
  - `Nahri Darsan` (residential)
  - `کابل ښاروالۍ` (county)
  - `ولایت كابل` (state)

**Generated Variations (21 total):**

1. `Seh Aqrab Road, Kabul, 1006, Afghanistan` (base)
2. `Seh Aqrab Road, ناحیه سوم Kabul, 1006, Afghanistan`
3. `Seh Aqrab Road, Kabul, ناحیه سوم 1006, Afghanistan`
4. `Seh Aqrab Road, Nahri Darsan Kabul, 1006, Afghanistan`
5. `Seh Aqrab Road, Kabul, Nahri Darsan 1006, Afghanistan`
6. `Seh Aqrab Road, کابل ښاروالۍ Kabul, 1006, Afghanistan`
7. `Seh Aqrab Road, Kabul, کابل ښاروالۍ 1006, Afghanistan`
8. `Seh Aqrab Road, ولایت كابل Kabul, 1006, Afghanistan`
9. `Seh Aqrab Road, Kabul, ولایت كابل 1006, Afghanistan`
10. `Seh Aqrab Road, ناحیه سوم Kabul, 1006, Nahri Darsan, Afghanistan`
11. `Seh Aqrab Road, ناحیه سوم Kabul, 1006, کابل ښاروالۍ, Afghanistan`
12. `Seh Aqrab Road, ناحیه سوم Kabul, 1006, ولایت كابل, Afghanistan`
13. `Seh Aqrab Road, Nahri Darsan Kabul, 1006, ناحیه سوم, Afghanistan`
14. `Seh Aqrab Road, Nahri Darsan Kabul, 1006, کابل ښاروالۍ, Afghanistan`
15. `Seh Aqrab Road, Nahri Darsan Kabul, 1006, ولایت كابل, Afghanistan`
16. `Seh Aqrab Road, کابل ښاروالۍ Kabul, 1006, ناحیه سوم, Afghanistan`
17. `Seh Aqrab Road, کابل ښاروالۍ Kabul, 1006, Nahri Darsan, Afghanistan`
18. `Seh Aqrab Road, کابل ښاروالۍ Kabul, 1006, ولایت كابل, Afghanistan`
19. `Seh Aqrab Road, ولایت كابل Kabul, 1006, ناحیه سوم, Afghanistan`
20. `Seh Aqrab Road, ولایت كابل Kabul, 1006, Nahri Darsan, Afghanistan`
21. `Seh Aqrab Road, ولایت كابل Kabul, 1006, کابل ښاروالۍ, Afghanistan`

---

### Step 4: Apply 4 Validations

Each generated variation must pass **ALL 4 validations** before being added:

#### ✅ Validation 1: `looks_like_address`

**Purpose**: Heuristic check to ensure the address looks valid

**Checks:**
- Length: 30-300 characters (after removing non-word characters)
- Letter count: At least 20 letters
- Contains at least one Latin letter
- At least 5 unique characters
- At least 1 section with numbers
- At least 2 commas
- No disallowed special characters (`:`, `%`, `$`, `@`, `*`, `^`, `[`, `]`, `{`, `}`, `_`, `«`, `»`)

**Example:**
```python
✅ "Seh Aqrab Road, ناحیه سوم Kabul, 1006, Afghanistan"  # Passes
❌ "Seh Aqrab Road"  # Fails (no commas, too short)
❌ "123, 456, 789"  # Fails (no letters)
```

---

#### ✅ Validation 2: `validate_address_region`

**Purpose**: Ensures the generated address matches the correct region (city/country) from the original address

**Checks:**
- Extracts city and country from both addresses
- Verifies they match (with special handling for disputed regions)
- Uses GeoNames database for validation

**Example:**
```python
Original: "Seh Aqrab Road, Kabul, 1006, Afghanistan"
✅ "Seh Aqrab Road, ناحیه سوم Kabul, 1006, Afghanistan"  # Passes (Kabul, Afghanistan)
❌ "Seh Aqrab Road, Paris, 1006, France"  # Fails (wrong city/country)
```

---

#### ✅ Validation 3: `check_with_nominatim`

**Purpose**: API validation using Nominatim geocoding

**Checks:**
- Queries Nominatim API with the address
- Calculates bounding box area
- Returns score based on area (smaller area = higher score)
- **Requires score >= 0.9** to pass

**Scoring:**
- Area < 0.01 m² → Score: 1.0
- Area 0.01-1.0 m² → Score: 0.95
- Area 1.0-10 m² → Score: 0.90
- Area >= 10 m² → Score: 0.0 (fails)

**Example:**
```python
✅ "Seh Aqrab Road, ناحیه سوم Kabul, 1006, Afghanistan"  # Score: 1.0 (passes)
❌ "Seh Aqrab Road, Random Place, 1006, Afghanistan"  # Score: 0.0 (fails)
```

**Rate Limiting:**
- 1 second sleep between each Nominatim API call
- Prevents 403 errors and rate limiting

---

#### ✅ Validation 4: `normalize_address_for_deduplication`

**Purpose**: Ensures uniqueness by normalizing and comparing addresses

**Normalization Process:**
1. Remove disallowed Unicode characters
2. Unicode normalization (NFKD) + diacritic removal
3. Transliterate non-ASCII to ASCII (e.g., Arabic → Latin)
4. Extract unique words
5. Sort letters alphabetically

**Example:**
```python
Original: "Seh Aqrab Road, ناحیه سوم Kabul, 1006, Afghanistan"
Normalized: "aabcefghiklmnoqrsu" (sorted letters from transliterated text)

# Check against existing normalized addresses
if normalized not in existing_normalized:
    ✅ Add address (unique)
else:
    ❌ Skip address (duplicate)
```

**Example of Duplicate Detection:**
```python
Address 1: "Seh Aqrab Road, Kabul, 1006, Afghanistan"
Address 2: "Seh Aqrab Road, کابل, 1006, افغانستان"  # Same address, different script
# Both normalize to same string → Duplicate detected
```

---

### Step 5: Save Valid Addresses

Only variations that pass **ALL 4 validations** are added to `new_addresses_variations.json`:

```json
{
  "address": "Seh Aqrab Road, ناحیه سوم Kabul, 1006, Afghanistan",
  "score": 1.0,
  "cheat_normalized_address": "aabcefghiklmnoqrsu",
  "source_city": "Kabul",
  "referenced_from": "Seh Aqrab Road, Kabul, 1006, Afghanistan",
  "created_from": "Generated from Afghanistan cache address (variation)",
  "country": "Afghanistan"
}
```

---

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Load normalized_address_cache.json                        │
│    → Find countries with < 15 addresses                      │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. For each country:                                         │
│    For each address in country:                             │
│      → Query Nominatim API                                   │
│      → Extract components (road, city, postcode, extras)    │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Generate variations:                                      │
│    → Base: {road}, {city}, {postcode}, {country}            │
│    → With extras: {road}, {extra} {city}, {postcode}, ...   │
│    → Multi-extras: {road}, {extra1} {city}, ..., {extra2}   │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. For each variation, apply 4 validations:                 │
│                                                              │
│    ✅ Check 1: looks_like_address(var)                       │
│       → Skip if fails                                        │
│                                                              │
│    ✅ Check 2: validate_address_region(var, country)         │
│       → Skip if fails                                        │
│                                                              │
│    ✅ Check 3: check_with_nominatim(var) >= 0.9             │
│       → Skip if score < 0.9                                  │
│       → Sleep 1 second (rate limiting)                      │
│                                                              │
│    ✅ Check 4: normalize_address_for_deduplication(var)      │
│       → Skip if duplicate                                    │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Save valid addresses to new_addresses_variations.json    │
│    → Store: address, score, normalized, metadata             │
└─────────────────────────────────────────────────────────────┘
```

---

## Example: Complete Processing

### Input

**Country**: Afghanistan (3 addresses)

**Address 1**: `Seh Aqrab Road, Kabul, 1006, Afghanistan`

### Processing

1. **Query Nominatim**: Get components
2. **Extract**: road, city, postcode, country, suburb, residential, county, state
3. **Generate**: 21 raw variations
4. **Validate**: 
   - 8 variations fail `looks_like_address` (Persian-only addresses)
   - 1 variation fails `validate_address_region`
   - 2 variations fail `check_with_nominatim` (score < 0.9)
   - 3 variations are duplicates
5. **Result**: 7 unique variations pass all 4 validations

### Output

**7 addresses added to `new_addresses_variations.json`:**

1. `Seh Aqrab Road, ناحیه سوم Kabul, 1006, Afghanistan` (Score: 1.0)
2. `Seh Aqrab Road, Nahri Darsan Kabul, 1006, Afghanistan` (Score: 1.0)
3. `Seh Aqrab Road, کابل ښاروالۍ Kabul, 1006, Afghanistan` (Score: 1.0)
4. `Seh Aqrab Road, ولایت كابل Kabul, 1006, Afghanistan` (Score: 1.0)
5. `Seh Aqrab Road, ناحیه سوم Kabul, 1006, Nahri Darsan, Afghanistan` (Score: 1.0)
6. `Seh Aqrab Road, ناحیه سوم Kabul, 1006, کابل ښاروالۍ, Afghanistan` (Score: 1.0)
7. `Seh Aqrab Road, ناحیه سوم Kabul, 1006, ولایت كابل, Afghanistan` (Score: 1.0)

---

## Key Features

### ✅ Guaranteed Quality

- All addresses pass **4 strict validations**
- No duplicates (normalized deduplication)
- Valid geocoding (Nominatim API verified)
- Correct region (city/country match)

### ✅ Rate Limiting

- 1 second sleep between Nominatim API calls
- Prevents 403 errors and API throttling
- Respects Nominatim's usage policy

### ✅ Uniqueness

- Normalizes addresses using same logic as `cheat_detection.py`
- Transliterates non-Latin scripts to ASCII
- Prevents duplicate variations from being added

### ✅ Metadata Tracking

Each generated address includes:
- `referenced_from`: Original address used to generate variation
- `created_from`: How the address was created
- `source_city`: City extracted from Nominatim
- `score`: Actual validation score (0.9 or 1.0)

---

## Usage

```bash
# Run the script
python3 generate_address_variations_from_cache.py

# The script will:
# 1. Process all countries with < 15 addresses
# 2. Generate variations from existing addresses
# 3. Validate all variations with 4 checks
# 4. Save valid addresses to new_addresses_variations.json
```

---

## Output Format

**File**: `new_addresses_variations.json`

```json
{
  "description": "Newly created address variations from cache addresses",
  "created_at": "2024-12-19",
  "source": "Generated from addresses in normalized_address_cache.json",
  "addresses_by_country": {
    "Afghanistan": [
      {
        "address": "Seh Aqrab Road, ناحیه سوم Kabul, 1006, Afghanistan",
        "score": 1.0,
        "cheat_normalized_address": "aabcefghiklmnoqrsu",
        "source_city": "Kabul",
        "referenced_from": "Seh Aqrab Road, Kabul, 1006, Afghanistan",
        "created_from": "Generated from Afghanistan cache address (variation)",
        "country": "Afghanistan"
      }
    ]
  }
}
```

---

## Summary

The script generates address variations by:

1. **Extracting components** from Nominatim API responses
2. **Combining components** in different orders and combinations
3. **Validating each variation** with 4 strict checks:
   - Heuristic validation (`looks_like_address`)
   - Region validation (`validate_address_region`)
   - API validation (`check_with_nominatim` score >= 0.9)
   - Uniqueness check (`normalize_address_for_deduplication`)
4. **Saving only valid, unique addresses** to `new_addresses_variations.json`

This ensures all generated addresses are:
- ✅ Valid (pass all heuristics)
- ✅ Geocodable (verified by Nominatim)
- ✅ Regionally correct (match original city/country)
- ✅ Unique (no duplicates)

