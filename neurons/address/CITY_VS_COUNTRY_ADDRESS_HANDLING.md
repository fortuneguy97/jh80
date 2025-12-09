# City vs Country Address Handling

## Question

**What if the validator provides seed address as "London" instead of "United Kingdom"?**

If the validator asks for "London" and we have cached 15 addresses for "United Kingdom", will the validator accept those 15 addresses from UK even though they're from different cities (not all from London)?

## Answer: **NO, they will FAIL validation**

### Why?

The validator's `validate_address_region()` function checks:

```python
city_match = gen_city == seed_address_lower  # "london" == "london" ✓
country_match = gen_country == seed_address_lower  # "united kingdom" == "london" ✗
mapped_match = gen_country == mapped_seed  # "united kingdom" == mapped("london") ✗

if not (city_match or country_match or mapped_match):
    return False  # FAIL ❌
```

**If seed is "London" and we return UK addresses from different cities:**

| Generated Address | gen_city | gen_country | city_match | country_match | Result |
|-------------------|----------|-------------|------------|---------------|--------|
| "123 Main St, Manchester, UK" | "manchester" | "united kingdom" | ✗ (≠ "london") | ✗ (≠ "london") | ❌ FAIL |
| "456 Oak Ave, Birmingham, UK" | "birmingham" | "united kingdom" | ✗ (≠ "london") | ✗ (≠ "london") | ❌ FAIL |
| "789 Park Rd, London, UK" | "london" | "united kingdom" | ✓ (= "london") | ✗ (≠ "london") | ✅ PASS |

**Only addresses FROM London will pass!**

## Solution

I've updated `unified_generator.py` to handle this:

### 1. **Detect City Names**
```python
# Check if seed is a city name
is_city = seed_clean.lower() in city_to_country
```

### 2. **Filter by City**
If seed is a city name, filter cached addresses to only those from that specific city:

```python
if is_city:
    city_specific_addresses = []
    for addr in cached_addresses:
        gen_city, _ = extract_city_country(addr)
        if gen_city and gen_city.lower() == city_name.lower():
            city_specific_addresses.append(addr)
```

### 3. **Fallback to API**
If not enough city-specific addresses in cache, fall back to Nominatim API to search for that specific city.

## How It Works Now

### Scenario 1: Seed is Country Name
```
Seed: "United Kingdom"
→ Uses all cached UK addresses (from any city)
→ ✅ All 15 addresses pass validation
```

### Scenario 2: Seed is City Name
```
Seed: "London"
→ Filters cached UK addresses to only those from London
→ If < 15 London addresses in cache, searches Nominatim for more London addresses
→ ✅ All 15 addresses are from London and pass validation
```

### Scenario 3: Seed is "City, Country" Format
```
Seed: "London, United Kingdom"
→ Extracts country: "United Kingdom"
→ Filters to London addresses
→ ✅ All addresses are from London, UK
```

## Current Validator Behavior

Based on the code analysis:
- **Positive samples:** Send country name from `Country_Residence` (e.g., "United States", "United Kingdom")
- **Negative samples:** Send country name from `get_random_country()` (e.g., "France", "Germany")

**The validator typically sends COUNTRY names, not city names.**

However, the code now handles both cases:
- ✅ If validator sends country → uses all addresses from that country
- ✅ If validator sends city → filters to addresses from that city only

## Cache Strategy

**Current cache structure:**
```json
{
  "addresses": {
    "United Kingdom": [
      "123 Main St, London, UK",
      "456 Oak Ave, Manchester, UK",
      "789 Park Rd, Birmingham, UK",
      ...
    ]
  }
}
```

**For city filtering:**
- Cache stores addresses by country
- When seed is a city, we filter cached addresses to that city
- If not enough, we search Nominatim for that specific city

## Summary

✅ **Updated code now handles city names correctly:**
- Detects if seed is a city name
- Filters cached addresses to that specific city
- Falls back to API if needed
- Ensures all addresses pass region validation

✅ **If validator sends "London":**
- We return addresses FROM London only
- Not addresses from other UK cities
- All addresses will pass `validate_address_region()`

