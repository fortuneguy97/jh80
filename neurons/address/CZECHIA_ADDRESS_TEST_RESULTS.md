# Czechia Address Test Results - Detailed Analysis

## Test Configuration
- **USER_AGENT**: `MIIDSubnet/1.0 (contact: prasadpsd2001@gmail.com)`
- **Rate Limiting**: ✅ **1 second sleep between Nominatim API calls** (except first address)
- **Total Addresses Tested**: 15

## Summary

### Overall Results
- ✅ **Passed (score >= 0.9)**: **1 address** (6.7%)
- ✗ **Failed**: **14 addresses** (93.3%)
- **Unique Normalized Addresses**: **9**
- **Duplicate Groups**: **4 groups** (6 addresses are duplicates)

### Only 1 Address Passed
**Address #5**: `Heršpická 875/6a, Štýřice, Brno, South Moravian Region, 639 00, Czechia`
- Score: **1.0**
- Normalized: `aaaaabcccceeeeghhhiiiiikmnnnooooprrrrrsssttuvyz`
- Status: **UNIQUE** (not a duplicate)

## Why Geocoding Failed - Detailed Analysis

### Failure Reasons

#### 1. **No Results Found (0 results)** - 9 addresses
Nominatim returned 0 results for these addresses:
- #1: `875/6a Heršpická, Štýřice, Brno, Czechia 639 00`
- #6: `Štýřice, 875/6a Heršpická, Brno, Czechia`
- #8: `South Moravian Region, Brno, Heršpická 875/6a, Czechia`
- #9: `Okres Brno-město, Heršpická 875/6a, Brno, 639 00, Czechia`
- #10: `Southeast, Heršpická 875/6a, Brno, Czechia`
- #11: `875/6a Heršpická, Brno City, South Moravian Region, Czechia`
- #12: `875/6a Heršpická, Brno Municipality, Czechia`
- #13: `875/6a Heršpická, Štýřice District, Brno, Czechia`
- #15: `Heršpická 875/6a, Štýřice, Brno 639-00, Czechia`

**Reason**: These address formats don't match Nominatim's search patterns. Reordering components or using alternative names ("Brno City", "Brno Municipality", "Štýřice District") causes Nominatim to return no results.

#### 2. **Results Found But Filtered Out** - 5 addresses

These addresses returned results from Nominatim, but all results were filtered out due to validation rules:

##### Address #2: `875/6a Heršpická, Brno, South Moravian Region, Czechia`
- **Nominatim Results**: 2 results
- **First Result**: `875/6a, Heršpická, Štýřice, Brno, okres Brno-město, Jihomoravský kraj, Jihovýchod, 639 00, Česko`
- **Place Rank**: 30 ✅
- **Filtered Out Because**:
  - Result 1: **Numbers mismatch** - Display name contains "639 00" but original address only has "875" and "6"
  - Result 2: **Name not in address** - Result name is "Brno 8" which is not in the query

##### Address #3: `Heršpická 875/6a, Brno, Southeast, Czechia`
- **Nominatim Results**: 2 results
- **Filtered Out Because**:
  - Result 1: **Numbers mismatch** - Display name has "639 00" not in original
  - Result 2: **Name not in address** - "Brno 8" not in query

##### Address #4: `875/6a Heršpická, Brno, okres Brno-město, Czechia`
- **Nominatim Results**: 2 results
- **Filtered Out Because**:
  - Result 1: **Numbers mismatch** - Display name has "639 00" not in original
  - Result 2: **Name not in address** - "Brno 8" not in query

##### Address #7: `Brno, 875/6a Heršpická, South Moravian Region, Czechia`
- **Nominatim Results**: 1 result
- **First Result**: `Brno 8, 875/6a, Heršpická, Štýřice, Brno, okres Brno-město, Jihomoravský kraj, Jihovýchod, 639 00, Česko`
- **Filtered Out Because**:
  - Result 1: **Name not in address** - Result name is "Brno 8" which is not in the query

##### Address #14: `875/6a Heršpická, Brno 63900, Czechia`
- **Nominatim Results**: 2 results
- **Filtered Out Because**:
  - Result 1: **Name not in address** - "Brno 8" not in query
  - Result 2: **Numbers mismatch** - Display name has "639 00" but query has "63900" (no space)

### Why Address #5 Passed

**Address #5**: `Heršpická 875/6a, Štýřice, Brno, South Moravian Region, 639 00, Czechia`

✅ **Success Factors**:
1. **Contains postal code "639 00"** - This matches the numbers in Nominatim's display_name
2. **Proper component order** - Street, district, city, region, postal code, country
3. **Numbers match** - Original has `{'6', '639', '875', '00'}` which matches display_name numbers
4. **Name match** - Result name is in the address
5. **Place rank >= 20** - Result has place_rank 30

**Result Details**:
- Nominatim found: `875/6a, Heršpická, Štýřice, Brno, okres Brno-město, Jihomoravský kraj, Jihovýchod, 639 00, Česko`
- Place rank: 30
- All filters passed ✅
- Score: 1.0 (bounding box area < 100 m²)

## Duplicate Groups

### Group 1 (3 addresses)
- #1: `875/6a Heršpická, Štýřice, Brno, Czechia 639 00`
- #6: `Štýřice, 875/6a Heršpická, Brno, Czechia`
- #15: `Heršpická 875/6a, Štýřice, Brno 639-00, Czechia`
- **Normalized**: `aaabcccceeehhiiiknoprrrsstyz`
- **Note**: All failed geocoding (0 results)

### Group 2 (3 addresses)
- #2: `875/6a Heršpická, Brno, South Moravian Region, Czechia`
- #7: `Brno, 875/6a Heršpická, South Moravian Region, Czechia`
- #8: `South Moravian Region, Brno, Heršpická 875/6a, Czechia`
- **Normalized**: `aaaaabccceeeghhhiiiikmnnnooooprrrrsstuvz`
- **Note**: All failed geocoding (filtered out)

### Group 3 (2 addresses)
- #3: `Heršpická 875/6a, Brno, Southeast, Czechia`
- #10: `Southeast, Heršpická 875/6a, Brno, Czechia`
- **Normalized**: `aaaabccceeehhhiiknooprrsssttuz`
- **Note**: All failed geocoding (filtered out)

### Group 4 (2 addresses)
- #4: `875/6a Heršpická, Brno, okres Brno-město, Czechia`
- #9: `Okres Brno-město, Heršpická 875/6a, Brno, 639 00, Czechia`
- **Normalized**: `aaabbccceeeehhiikkmnnooooprrrrssstz`
- **Note**: All failed geocoding (#4 filtered out, #9 no results)

## Key Findings

### 1. Rate Limiting
✅ **1 second sleep IS implemented** between Nominatim API calls (except first address)
- All calls after the first include: `⏳ Waiting 1 second before API call (rate limiting)...`
- No 403 or 429 errors encountered

### 2. Why Most Addresses Fail

#### A. Missing Postal Code
- Addresses without postal code "639 00" fail the **number matching filter**
- Nominatim returns results with postal code "639 00", but addresses without it fail validation

#### B. Alternative Names Don't Work
- "Brno City" → 0 results
- "Brno Municipality" → 0 results
- "Štýřice District" → 0 results
- Nominatim doesn't recognize these alternative names

#### C. Component Reordering
- Reordering address components (e.g., starting with "Štýřice" or "South Moravian Region") → 0 results
- Nominatim expects standard format: Street, City, Region, Country

#### D. Name Filter Too Strict
- Results with name "Brno 8" are filtered out because "Brno 8" is not in the query
- This is a strict validation rule that may be too restrictive

### 3. What Works

✅ **Address format that works**:
```
Street Number/Letter Street Name, District, City, Region, Postal Code, Country
```

Example:
```
Heršpická 875/6a, Štýřice, Brno, South Moravian Region, 639 00, Czechia
```

**Key requirements**:
1. Include postal code in the query
2. Use standard component order
3. Don't use alternative names ("City", "Municipality", "District")
4. Don't reorder components

## Recommendations

1. **Always include postal code** in address variations
2. **Use standard address format** - don't reorder components
3. **Avoid alternative names** - use official names only
4. **Consider relaxing name filter** - "Brno 8" might be acceptable if it's a valid result
5. **Test address variations** before using them in production

## Full Log File

Complete detailed logs saved to: `test_czechia_full_log.txt`

