# Address Validation Workflow

## Complete Validator Address Validation Process

This document explains the **3-step address validation** process used by validators to score miner-generated addresses.

---

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Miner Submits Variations                                   │
│  ["John Smith", "1990-01-01", "123 Broadway, New York, USA"]│
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: Format Validation (looks_like_address)             │
│  ├─ Length: 30-300 chars (after removing punctuation)       │
│  ├─ Letters: At least 20 letters                            │
│  ├─ Numbers: At least 1 digit in a comma-separated section  │
│  ├─ Commas: At least 2 commas                               │
│  ├─ Special chars: NO `, :, %, $, @, *, ^, [, ], {, }, _, «, »│
│  ├─ Uniqueness: At least 5 unique characters                │
│  └─ Result: PASS or FAIL                                    │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ├─ FAIL → Score = 0.0 (STOP)
                   │
                   ▼ PASS
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: Region Validation (validate_address_region)        │
│  ├─ Extract city and country from generated address         │
│  ├─ Compare with seed address                               │
│  ├─ Check: city_match OR country_match OR mapped_match      │
│  └─ Result: PASS or FAIL                                    │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ├─ FAIL → Score = 0.0 (STOP)
                   │
                   ▼ PASS
┌─────────────────────────────────────────────────────────────┐
│  STEP 3: Geocoding Validation (check_with_nominatim)        │
│  ├─ Randomly select up to 3 addresses                       │
│  ├─ Query Nominatim API for each address                    │
│  ├─ Check: place_rank >= 20, name in address, numbers match │
│  ├─ Calculate bounding box area                             │
│  └─ Score: 0.3-1.0 based on precision                       │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  Final Score                                                 │
│  ├─ All steps pass: 0.7-1.0 (based on bounding box)         │
│  ├─ Step 1 or 2 fails: 0.0                                  │
│  └─ Step 3 fails: 0.3 (not geocodable)                      │
└─────────────────────────────────────────────────────────────┘
```

---

## STEP 1: Format Validation (`looks_like_address`)

### Purpose
Checks if the address **looks like a real address** based on format rules.

### Validation Rules

#### 1. **Length Check**
```python
# Remove punctuation and count characters
address_len = re.sub(r'[^\w]', '', address.strip(), flags=re.UNICODE)

# Must be 30-300 characters
if len(address_len) < 30:
    return False  # TOO SHORT
if len(address_len) > 300:
    return False  # TOO LONG
```

**Examples:**
- ✅ `"456 Broadway, SoHo, New York, NY 10013, United States"` (58 chars)
- ❌ `"123 Main St, NY, USA"` (18 chars - TOO SHORT)
- ❌ `"225 Liberty St, New York, NY 10281, USA"` (29 chars - TOO SHORT)

#### 2. **Letter Count**
```python
# Count letters (Latin and non-Latin)
letter_count = len(re.findall(r'[^\W\d]', address, flags=re.UNICODE))

# Must have at least 20 letters
if letter_count < 20:
    return False
```

**Examples:**
- ✅ `"456 Broadway, New York, USA"` (21 letters)
- ❌ `"123 St, NY, USA"` (7 letters)

#### 3. **Number Check**
```python
# Must have at least 1 digit in a comma-separated section
sections = [s.strip() for s in address.split(',')]
sections_with_numbers = []
for section in sections:
    number_groups = re.findall(r"[0-9]+", section)
    if len(number_groups) > 0:
        sections_with_numbers.append(section)

# Need at least 1 section with numbers
if len(sections_with_numbers) < 1:
    return False
```

**Examples:**
- ✅ `"123 Broadway, New York, USA"` (has "123")
- ❌ `"Broadway, New York, USA"` (no numbers)

#### 4. **Comma Check**
```python
# Must have at least 2 commas
if address.count(",") < 2:
    return False
```

**Format:** `"Street, City, Country"` (minimum)

**Examples:**
- ✅ `"123 Broadway, New York, USA"` (2 commas)
- ❌ `"123 Broadway, New York"` (1 comma)

#### 5. **Special Character Check**
```python
# These characters are NOT allowed
special_chars = ['`', ':', '%', '$', '@', '*', '^', '[', ']', '{', '}', '_', '«', '»']

if any(char in address for char in special_chars):
    return False
```

**Examples:**
- ✅ `"123 Broadway, New York, USA"`
- ❌ `"123 Broadway @ New York, USA"` (has @)
- ❌ `"123_Broadway, New York, USA"` (has _)

#### 6. **Uniqueness Check**
```python
# Must have at least 5 unique characters
if len(set(address)) < 5:
    return False
```

**Examples:**
- ✅ `"123 Broadway, New York, USA"` (many unique chars)
- ❌ `"111 1, 1, 1"` (only 3 unique chars)

#### 7. **Letter Existence**
```python
# Must contain at least one letter
if re.match(r"^[^a-zA-Z]*$", address):
    return False
```

**Examples:**
- ✅ `"123 Broadway, New York, USA"`
- ❌ `"123, 456, 789"` (no letters)

### Result
- **PASS** → Continue to Step 2
- **FAIL** → **Score = 0.0** (STOP - no further validation)

---

## STEP 2: Region Validation (`validate_address_region`)

### Purpose
Checks if the generated address is from the **same region** as the seed address.

### Validation Logic

#### 1. **Extract City and Country**
```python
def extract_city_country(address: str) -> Tuple[str, str]:
    """
    Extract city and country from address.
    
    Examples:
    - "New York, USA" → ("new york", "usa")
    - "123 Main St, London, UK" → ("london", "uk")
    - "456 Broadway, New York, NY, USA" → ("new york", "usa")
    """
    parts = [p.strip().lower() for p in address.split(',')]
    
    if len(parts) >= 2:
        country = parts[-1]  # Last part is country
        city = parts[-2]     # Second to last is city (or state)
        
        # If city looks like state code (2 letters), use part before it
        if len(city) == 2 and city.isupper() and len(parts) >= 3:
            city = parts[-3]
        
        return city, country
    
    return None, None
```

#### 2. **Compare with Seed Address**
```python
def validate_address_region(generated_address: str, seed_address: str) -> bool:
    # Extract from generated address
    gen_city, gen_country = extract_city_country(generated_address)
    
    # Normalize seed address
    seed_lower = seed_address.lower()
    seed_mapped = COUNTRY_MAPPING.get(seed_lower, seed_lower)
    
    # Check matches
    city_match = (gen_city == seed_lower)
    country_match = (gen_country == seed_lower)
    mapped_match = (gen_country == seed_mapped)
    
    # Pass if ANY match
    return (city_match or country_match or mapped_match)
```

#### 3. **Country Mapping**
```python
COUNTRY_MAPPING = {
    "usa": "united states",
    "uk": "united kingdom",
    "uae": "united arab emirates",
    # ... more mappings
}
```

### Examples

#### ✅ **PASS Examples:**

**Seed:** `"New York, USA"`
- ✅ `"123 Broadway, New York, USA"` (city match)
- ✅ `"456 5th Ave, New York, United States"` (city match + mapped country)
- ✅ `"789 Wall St, Manhattan, New York, USA"` (city match)

**Seed:** `"London, UK"`
- ✅ `"10 Downing Street, London, UK"` (city match)
- ✅ `"221B Baker Street, London, United Kingdom"` (city match + mapped country)

#### ❌ **FAIL Examples:**

**Seed:** `"New York, USA"`
- ❌ `"123 Main St, Los Angeles, USA"` (wrong city)
- ❌ `"456 Oxford St, London, UK"` (wrong country)
- ❌ `"789 Champs-Élysées, Paris, France"` (wrong city and country)

### Result
- **PASS** → Continue to Step 3
- **FAIL** → **Score = 0.0** (STOP - no API call)

---

## STEP 3: Geocoding Validation (`check_with_nominatim`)

### Purpose
Verifies that the address is **real and geocodable** using OpenStreetMap's Nominatim API.

### Process

#### 1. **Random Selection**
```python
# Randomly choose up to 3 addresses that passed Steps 1 & 2
max_addresses = min(3, len(api_validated_addresses))
chosen_addresses = random.sample(api_validated_addresses, max_addresses)
```

**Why 3?**
- Balances validation thoroughness with API rate limits
- Reduces API costs
- Still catches fake addresses

#### 2. **Nominatim API Call**
```python
def check_with_nominatim(address: str, validator_uid: int, miner_uid: int, 
                         seed_address: str, seed_name: str) -> Union[float, str, dict]:
    """
    Query Nominatim API and return score based on bounding box area.
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json"}
    headers = {"User-Agent": "MIID-Subnet/1.0"}
    
    response = requests.get(url, params=params, headers=headers, timeout=5)
    results = response.json()
    
    if not results:
        return 0.0  # Not found
    
    # Filter results
    for result in results:
        # Check place_rank (must be >= 20 for street-level)
        if result.get('place_rank', 0) < 20:
            continue
        
        # Check if name is in address
        name = result.get('name', '').lower()
        if name not in address.lower():
            continue
        
        # Check if numbers match
        addr_numbers = re.findall(r'\d+', address)
        result_numbers = re.findall(r'\d+', result.get('display_name', ''))
        if not any(num in result_numbers for num in addr_numbers):
            continue
        
        # Calculate bounding box area
        bbox = result.get('boundingbox', [])
        area = calculate_bounding_box_area(bbox)
        
        # Score based on area (smaller = more precise = higher score)
        if area < 100:
            return 1.0  # < 100 m²
        elif area < 1000:
            return 0.9  # < 1,000 m²
        elif area < 10000:
            return 0.8  # < 10,000 m²
        elif area < 100000:
            return 0.7  # < 100,000 m²
        else:
            return 0.3  # ≥ 100,000 m²
    
    return 0.0  # No valid results
```

#### 3. **Bounding Box Area Calculation**
```python
def calculate_bounding_box_area(bbox: List[str]) -> float:
    """
    Calculate area in square meters from bounding box.
    
    Args:
        bbox: [min_lat, max_lat, min_lon, max_lon]
        
    Returns:
        Area in square meters
    """
    if len(bbox) != 4:
        return float('inf')
    
    min_lat, max_lat, min_lon, max_lon = map(float, bbox)
    
    # Use Haversine formula to calculate area
    # ... (complex calculation)
    
    return area_in_square_meters
```

### Scoring

| Bounding Box Area | Score | Precision Level |
|------------------|-------|-----------------|
| < 100 m² | 1.0 | **Exact address** (best) |
| < 1,000 m² | 0.9 | **Building/block** |
| < 10,000 m² | 0.8 | **Street** |
| < 100,000 m² | 0.7 | **Neighborhood** |
| ≥ 100,000 m² | 0.3 | **City/region** (imprecise) |
| Not geocodable | 0.3 | **Fake address** |

### Examples

#### ✅ **High Score (0.9-1.0):**
```
Address: "456 Broadway, SoHo, New York, NY 10013, United States"
Nominatim Result:
  - place_rank: 30 (building level)
  - name: "Broadway"
  - bounding_box: [40.7205, 40.7207, -74.0010, -74.0008]
  - area: 50 m²
Score: 1.0 ✅
```

#### ⚠️ **Medium Score (0.7-0.8):**
```
Address: "Broadway, New York, USA"
Nominatim Result:
  - place_rank: 26 (street level)
  - name: "Broadway"
  - bounding_box: [40.7, 40.8, -74.1, -74.0]
  - area: 50,000 m²
Score: 0.7 ⚠️
```

#### ❌ **Low Score (0.3):**
```
Address: "123 Fake Street, New York, USA"
Nominatim Result: []
Score: 0.3 ❌ (not geocodable)
```

### Caching
```python
# Results are cached to avoid repeated API calls
_nominatim_cache = LRUCache(max_size=10000)

# Cache key: hash of (address, seed_address, seed_name)
cache_key = hashlib.sha256(f"{address}|{seed_address}|{seed_name}".encode()).hexdigest()

# Check cache first
cached_result = _nominatim_cache.get(cache_key)
if cached_result is not None:
    return cached_result  # No API call needed
```

### Rate Limiting
```python
# Wait 1 second between API calls (Nominatim policy)
time.sleep(1.0)

# Exponential backoff on failures
if result == "TIMEOUT" or result == "API_ERROR":
    failure_count += 1
    wait_time = min(1.0 * (2 ** failure_count), 10.0)  # Max 10s
    time.sleep(wait_time)
```

---

## Final Scoring Logic

### If ALL Steps Pass:
```python
# Average scores from up to 3 API calls
if nominatim_scores:
    avg_score = sum(nominatim_scores) / len(nominatim_scores)
    return {
        "overall_score": avg_score,  # 0.7-1.0
        "heuristic_perfect": True,
        "api_result": True
    }
```

### If Step 1 or 2 Fails:
```python
return {
    "overall_score": 0.0,  # ZERO SCORE
    "heuristic_perfect": False,
    "api_result": False,
    "reason": "Format or region validation failed"
}
```

### If Step 3 Fails (not geocodable):
```python
return {
    "overall_score": 0.3,  # LOW SCORE
    "heuristic_perfect": True,
    "api_result": False,
    "reason": "Address not geocodable"
}
```

---

## Summary Table

| Validation Step | Check | Pass | Fail |
|----------------|-------|------|------|
| **Step 1: Format** | Length, letters, numbers, commas, special chars | → Step 2 | **Score = 0.0** |
| **Step 2: Region** | City/country matches seed | → Step 3 | **Score = 0.0** |
| **Step 3: Geocoding** | Nominatim API (3 random addresses) | **Score = 0.7-1.0** | **Score = 0.3** |

---

## Best Practices for Miners

### ✅ **DO:**
1. Use **real addresses** from Nominatim API
2. Ensure addresses are **30+ characters** (after removing punctuation)
3. Include **street numbers** for precision
4. Match **city and country** from seed address
5. Use **proper formatting**: `"Street, City, Country"`
6. Add **neighborhood/district** names for length

### ❌ **DON'T:**
1. Generate fake/imaginary addresses
2. Use addresses shorter than 30 characters
3. Include special characters (`, :, %, $, @, *, ^, [, ], {, }, _, «, »)
4. Use addresses from wrong city/country
5. Use landmarks instead of street addresses
6. Forget to include numbers in addresses

---

## Example: Complete Validation Flow

### Input
```python
Seed: "New York, USA"
Generated: "456 Broadway, SoHo, New York, NY 10013, United States"
```

### Step 1: Format Validation ✅
```
Length: 58 chars ✅ (30-300)
Letters: 38 letters ✅ (>= 20)
Numbers: "456", "10013" ✅ (>= 1 section with numbers)
Commas: 4 commas ✅ (>= 2)
Special chars: None ✅
Unique chars: 25 unique ✅ (>= 5)
Letters exist: Yes ✅
→ PASS
```

### Step 2: Region Validation ✅
```
Extract: city="new york", country="united states"
Seed: "new york, usa"
Mapped: "usa" → "united states"
city_match: "new york" == "new york" ✅
country_match: "united states" == "usa" ❌
mapped_match: "united states" == "united states" ✅
→ PASS (city_match OR mapped_match)
```

### Step 3: Geocoding Validation ✅
```
API Call: https://nominatim.openstreetmap.org/search?q=456+Broadway,+SoHo,+New+York,+NY+10013,+United+States
Result:
  - place_rank: 30 ✅ (>= 20)
  - name: "Broadway" ✅ (in address)
  - numbers: "456" ✅ (matches)
  - bounding_box: [40.7205, 40.7207, -74.0010, -74.0008]
  - area: 50 m² ✅ (< 100 m²)
→ Score: 1.0
```

### Final Score
```python
{
    "overall_score": 1.0,  # MAXIMUM SCORE ✅
    "heuristic_perfect": True,
    "api_result": True,
    "nominatim_successful_calls": 1
}
```

---

## Conclusion

The validator uses a **strict 3-step validation** process:
1. **Format** → Must look like an address
2. **Region** → Must match seed location
3. **Geocoding** → Must be real and geocodable

**Only addresses that pass ALL 3 steps get high scores (0.7-1.0).**

Use **Nominatim integration** in your miner to generate real addresses and maximize your TAO earnings! 🚀
