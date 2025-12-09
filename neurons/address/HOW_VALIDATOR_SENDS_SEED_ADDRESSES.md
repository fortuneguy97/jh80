# How Validator Sends Seed Addresses

## Summary

The validator can send seed addresses in **different formats** depending on the source:

1. **Negative samples** → Just country name (e.g., "United States")
2. **Positive samples** → Could be country, city, or "City, Country" format
3. **Query template** → Says "country/city" suggesting any format is possible

## Detailed Breakdown

### 1. Negative Samples (Generated Names)

**Source:** `get_random_country()` method  
**Location:** `MIID/validator/query_generator.py` line 1658, 1707, 1839

**Code:**
```python
address = self.get_random_country()
```

**What it returns:**
- Uses `GeonamesCache.get_countries()`
- Returns just country names like:
  - "United States"
  - "United Kingdom"
  - "France"
  - "Germany"
  - etc.

**Format:** Just country name (no comma, no city)

**Region Validation:** ✅ **WORKS** - Just country name matches the comparison logic

### 2. Positive Samples (Sanctioned Individuals)

**Source:** `Country_Residence` field from sanctioned individuals data  
**Location:** `MIID/validator/query_generator.py` line 1495, 1525

**Code:**
```python
address = str(person.get("Country_Residence", ""))
```

**What it contains:**
- Comes from the sanctioned individuals data file
- Could be in various formats:
  - Just country: "United States"
  - Just city: "London"
  - City, Country: "New York, USA"
  - City, Full Country: "New York, United States"

**Format:** Unknown - depends on the data file

**Region Validation:** ⚠️ **DEPENDS ON FORMAT**
- If just country → ✅ Works
- If just city → ✅ Works
- If "City, Country" → ❌ Fails (bug)

### 3. Query Template

**Location:** `MIID/validator/query_generator.py` line 1748

**Text:**
```
The following address is the seed country/city to generate address variations for: {address}.
```

**Meaning:**
- Says "country/city" suggesting it could be either
- Doesn't specify the exact format
- Miners need to handle any format

## Region Validation Impact

### ✅ Formats That Work:

1. **Just Country Name:**
   - Example: `"United States"`
   - Extraction: `gen_country = "united states"`
   - Comparison: `"united states" == "united states"` → ✅ True
   - Or: `"united states" == COUNTRY_MAPPING.get("united states")` → ✅ True

2. **Just City Name:**
   - Example: `"London"`
   - Extraction: `gen_city = "london"`
   - Comparison: `"london" == "london"` → ✅ True

3. **Special Regions:**
   - Example: `"Crimea"`
   - Uses special substring check → ✅ True

### ❌ Formats That Fail:

1. **City, Country Format:**
   - Example: `"New York, USA"`
   - Extraction: `gen_city = "york"`, `gen_country = "united states"`
   - Comparison: `"york" == "new york, usa"` → ❌ False
   - Comparison: `"united states" == "new york, usa"` → ❌ False
   - **Result:** Region validation fails → No API call → Score = 0.0

## Statistics

Based on the code:
- **Negative samples:** Always just country name (works ✅)
- **Positive samples:** Unknown format (could work or fail ⚠️)
- **Total:** Depends on the ratio of positive to negative samples

## Recommendations

1. **Test with actual validator** to see what formats are actually sent
2. **Handle all formats** in your address generation:
   - If just country → Generate addresses in that country
   - If just city → Generate addresses in that city
   - If "City, Country" → Generate addresses (will fail validation due to bug, but still generate them)
3. **Monitor for empty seeds** → Exploit still works (returns 1.0)

## Conclusion

The validator sends seed addresses in **multiple formats**:
- **Negative samples:** Just country name (works with validation ✅)
- **Positive samples:** Unknown format (could be any format ⚠️)

The region validation bug **only affects "City, Country" format** seeds. If the validator mostly sends just country names, the bug might not be a major issue. However, if it sends "City, Country" format, all those addresses will fail validation.

