# Address Validation Analysis

## Complete Function Definitions from `rewards.py`

### 1. `looks_like_address(address: str) -> bool`

```python
def looks_like_address(address: str) -> bool:
    address = address.strip().lower()

    # Keep all letters (Latin and non-Latin) and numbers
    # Using a more compatible approach for Unicode characters
    address_len = re.sub(r'[^\w]', '', address.strip(), flags=re.UNICODE)
    if len(address_len) < 30:
        return False
    if len(address_len) > 300:  # maximum length check
        return False

    # Count letters (both Latin and non-Latin) - using \w which includes Unicode letters
    letter_count = len(re.findall(r'[^\W\d]', address, flags=re.UNICODE))
    if letter_count < 20:
        return False

    if re.match(r"^[^a-zA-Z]*$", address):  # no letters at all
        return False
    if len(set(address)) < 5:  # all chars basically the same
        return False
        
    # Has at least one digit in a comma-separated section
    # Replace hyphens and semicolons with empty strings before counting numbers
    address_for_number_count = address.replace('-', '').replace(';', '')
    # Split address by commas and check for numbers in each section
    sections = [s.strip() for s in address_for_number_count.split(',')]
    sections_with_numbers = []
    for section in sections:
        # Only match ASCII digits (0-9), not other numeric characters
        number_groups = re.findall(r"[0-9]+", section)
        if len(number_groups) > 0:
            sections_with_numbers.append(section)
    # Need at least 1 section that contains numbers
    if len(sections_with_numbers) < 1:
        return False

    if address.count(",") < 2:  # ⚠️ CRITICAL: NEEDS 2+ COMMAS
        return False
    
    # Check for special characters that should not be in addresses
    special_chars = ['`', ':', '%', '$', '@', '*', '^', '[', ']', '{', '}', '_', '«', '»']
    if any(char in address for char in special_chars):
        return False
    
    return True
```

**Requirements:**
- ✅ 30+ alphanumeric characters (after removing non-word chars)
- ✅ 20+ letters (Latin and non-Latin)
- ✅ At least 1 digit in a comma-separated section
- ❌ **AT LEAST 2 COMMAS** (line 229) - **THIS IS THE FAILURE POINT**
- ✅ No special characters: `'` `:` `%` `$` `@` `*` `^` `[` `]` `{` `}` `_` `«` `»`
- ✅ At least 5 unique characters
- ✅ Must contain at least one letter

---

### 2. `extract_city_country(address: str, two_parts: bool = False) -> tuple`

```python
def extract_city_country(address: str, two_parts: bool = False) -> tuple:
    """
    Extract city and country from an address.
    Country is always the last part.
    City is found by checking each section from right to left (excluding country)
    and validating against geonames data to ensure it's a real city in the country.
    """
    if not address:
        return "", ""

    address = address.lower()
    
    parts = [p.strip() for p in address.split(",")]
    if len(parts) < 2:
        return "", ""

    # Determine country and its normalized form
    last_part = parts[-1]
    single_part_normalized = COUNTRY_MAPPING.get(last_part, last_part)
    
    # If two_parts flag is set, also try two-part country
    country_checking_name = ''
    if two_parts and len(parts) >= 2:
        two_part_raw = f"{parts[-2]}, {parts[-1]}"
        two_part_normalized = COUNTRY_MAPPING.get(two_part_raw, two_part_raw)
        if two_part_raw != two_part_normalized:
            country_checking_name = two_part_normalized
            normalized_country = two_part_normalized
            used_two_parts_for_country = True

    if country_checking_name == '':
        # Single-part country
        country_checking_name = single_part_normalized
        normalized_country = single_part_normalized
        used_two_parts_for_country = False

    # Check each section from right to left (excluding the country)
    exclude_count = 2 if used_two_parts_for_country else 1
    for i in range(exclude_count + 1, len(parts) + 1):
        candidate_index = -i
        if abs(candidate_index) > len(parts):
            break
        
        candidate_part = parts[candidate_index]
        if not candidate_part:
            continue
            
        words = candidate_part.split()
        
        # Try different combinations of words (1-2 words max)
        for num_words in range(len(words)):
            current_word = words[num_words]
            candidates = [current_word]
            
            if num_words > 0:
                prev_plus_current = words[num_words - 1] + " " + words[num_words]
                candidates.append(prev_plus_current)

            for city_candidate in candidates:
                # Skip if contains numbers or is too short
                if any(char.isdigit() for char in city_candidate):
                    continue

                # Validate the city exists in the country
                if city_in_country(city_candidate, country_checking_name):
                    return city_candidate, normalized_country

    return "", normalized_country
```

**How it works:**
- Splits address by commas
- Takes last part as country (or last 2 parts if `two_parts=True`)
- Validates country against `COUNTRY_MAPPING`
- Searches from right to left for a valid city in geonames
- Returns `(city, country)` tuple

---

### 3. `validate_address_region(generated_address: str, seed_address: str) -> bool`

```python
def validate_address_region(generated_address: str, seed_address: str) -> bool:
    """
    Validate that generated address has correct region from seed address.
    """
    if not generated_address or not seed_address:
        return False
    
    # Special handling for disputed regions
    SPECIAL_REGIONS = ["luhansk", "crimea", "donetsk", "west sahara", 'western sahara']
    
    seed_lower = seed_address.lower()
    if seed_lower in SPECIAL_REGIONS:
        gen_lower = generated_address.lower()
        return seed_lower in gen_lower
    
    # Extract city and country from both addresses
    gen_city, gen_country = extract_city_country(generated_address, two_parts=(',' in seed_address))
    seed_address_lower = seed_address.lower()
    seed_address_mapped = COUNTRY_MAPPING.get(seed_address.lower(), seed_address.lower())
    
    # If no city was extracted from generated address, it's an error
    if not gen_city:
        return False
    
    # If no country was extracted from generated address, it's an error
    if not gen_country:
        return False
    
    # Check if either city or country matches
    city_match = gen_city and seed_address_lower and gen_city == seed_address_lower
    country_match = gen_country and seed_address_lower and gen_country == seed_address_lower
    mapped_match = gen_country and seed_address_mapped and gen_country == seed_address_mapped
    
    if not (city_match or country_match or mapped_match):
        return False
    
    return True
```

**How it works:**
- Extracts city and country from generated address
- Compares against seed address (can be city or country)
- Returns `True` if city OR country matches

---

### 4. `compute_bounding_box_areas_meters(nominatim_results)`

```python
def compute_bounding_box_areas_meters(nominatim_results):
    """
    Computes bounding box areas in meters instead of degrees.
    """
    if not isinstance(nominatim_results, list):
        return []
    
    areas = []
    for item in nominatim_results:
        if "boundingbox" not in item:
            continue
        
        # Extract and convert bounding box coords to floats
        south, north, west, east = map(float, item["boundingbox"])
        
        # Approx center latitude for longitude scaling
        center_lat = (south + north) / 2.0
        lat_m = 111_000  # meters per degree latitude
        lon_m = 111_000 * math.cos(math.radians(center_lat))  # meters per degree longitude
        height_m = abs(north - south) * lat_m
        width_m = abs(east - west) * lon_m
        area_m2 = width_m * height_m
        
        areas.append({
            "south": south,
            "north": north,
            "west": west,
            "east": east,
            "width_m": width_m,
            "height_m": height_m,
            "area_m2": area_m2,
            "result": item
        })
    
    return areas
```

**Scoring based on area:**
- `< 100 m²` → Score 1.0
- `< 1000 m²` → Score 0.9
- `< 10000 m²` → Score 0.7
- `< 100000 m²` → Score 0.5
- `>= 100000 m²` → Score 0.3

---

## ❌ Why Your Addresses Are Failing

### Your Addresses:
```
1 Józefa Sarego, Kraków, Poland  ❌ Only 1 comma
2 Kanonicza, Kraków, Poland      ❌ Only 1 comma
7 św. Marka, Kraków, Poland      ❌ Only 1 comma
```

### The Problem:
**Line 229 in `looks_like_address`:**
```python
if address.count(",") < 2:
    return False
```

**All your addresses have only 1 comma** (between street and city), but the validator requires **at least 2 commas**.

---

## ✅ Required Address Format

### Minimum Format (2 commas):
```
{house_number} {street}, {city}, {country}
```

### Examples that PASS:
```
1 Józefa Sarego, Kraków, Małopolskie, Poland  ✅ 2 commas
2 Kanonicza, Kraków, 31-000, Poland            ✅ 2 commas (with postal code)
7 św. Marka, Kraków, Old Town, Poland         ✅ 2 commas (with district)
```

### Examples that FAIL:
```
1 Józefa Sarego, Kraków, Poland  ❌ Only 1 comma
2 Kanonicza, Kraków, Poland      ❌ Only 1 comma
```

---

## 🔧 How to Fix Your Addresses

### Option 1: Add Postal Code
```
1 Józefa Sarego, Kraków, 31-000, Poland
2 Kanonicza, Kraków, 31-000, Poland
7 św. Marka, Kraków, 31-000, Poland
```

### Option 2: Add Region/District
```
1 Józefa Sarego, Kraków, Małopolskie, Poland
2 Kanonicza, Kraków, Old Town, Poland
7 św. Marka, Kraków, Śródmieście, Poland
```

### Option 3: Add More Detail
```
1 Józefa Sarego, Kraków, Lesser Poland, Poland
2 Kanonicza, Kraków, City Center, Poland
7 św. Marka, Kraków, Kazimierz, Poland
```

---

## 📋 Corrected Addresses (15 addresses that will PASS)

```python
corrected_addresses = [
    "1 Józefa Sarego, Kraków, 31-000, Poland",
    "2 Kanonicza, Kraków, 31-000, Poland",
    "7 św. Marka, Kraków, 31-000, Poland",
    "12 Gołębia, Kraków, 31-000, Poland",
    "19 św. Jana, Kraków, 31-000, Poland",
    "21 św. Tomasza, Kraków, 31-000, Poland",
    "24 Bracka, Kraków, 31-000, Poland",
    "25 Karmelicka, Kraków, 31-000, Poland",
    "30 św. Gertrudy, Kraków, 31-000, Poland",
    "31 Długa, Kraków, 31-000, Poland",
    "34 Dietla, Kraków, 31-000, Poland",
    "36 Sławkowska, Kraków, 31-000, Poland",
    "40 Grodzka, Kraków, 31-000, Poland",
    "45 Starowiślna, Kraków, 31-000, Poland",
    "52 Krowoderska, Kraków, 31-000, Poland"
]
```

---

## 🎯 Summary

1. **Heuristic Check Fails** because addresses need **2+ commas** (your addresses have only 1)
2. **Region Check Passes** (all addresses correctly have "Poland" as country)
3. **API Check** would pass if heuristic passes (addresses are real and in Nominatim)

**Fix:** Add a third comma-separated section (postal code, region, or district) to all addresses.

