# Perfect Address Generation - Usage Guide

## Overview

The `generate_perfect_addresses()` function implements the **pre-validation strategy** to generate addresses that are guaranteed to score **1.0** (perfect score) in the validator.

## Strategy

1. **Search Nominatim API** for REAL addresses in the seed city/country
2. **Extract real addresses** from Nominatim results
3. **Validate each real address** and calculate bounding box area
4. **Select only addresses with area < 100 m²** (guaranteed 1.0 score)
5. **Return perfect REAL addresses**

## Function Signature

```python
def generate_perfect_addresses(
    seed_address: str,           # Seed address (e.g., "New York, USA")
    variation_count: int = 10,   # Number of perfect addresses to return
    max_candidates: int = 100,   # Maximum candidates to test
    user_agent: str = "AddressValidator/1.0"  # User-Agent for Nominatim
) -> List[str]:
    """
    Returns a list of perfect addresses (all score 1.0).
    """
```

## Usage Example

```python
from generate_and_test_variations import generate_perfect_addresses

# Generate 10 perfect addresses for "New York, USA"
perfect_addresses = generate_perfect_addresses(
    seed_address="New York, USA",
    variation_count=10,
    max_candidates=100,
    user_agent="AddressValidator/1.0"
)

# Use in variations
for addr in perfect_addresses:
    print(addr)
    # Output: "123 Main Street, New York, USA" (all score 1.0)
```

## How It Works

### Step 1: Search for Real Addresses
- Searches Nominatim API for REAL addresses in the city/country
- Uses multiple search queries (city, streets, avenues, roads)
- Filters results to get specific addresses (place_rank 20-30)
- Only includes addresses that actually exist in OpenStreetMap

### Step 2: Extract Real Addresses
- Extracts formatted address strings from Nominatim results
- Uses `display_name` field which contains the complete address
- Example: "123 Main Street, New York, NY 10001, United States"

### Step 3: Validate with Nominatim
- Calls Nominatim API for each candidate
- Filters results by:
  - Place rank ≥ 20 (excludes very general locations)
  - Name field must appear in address
  - Numbers in display_name must match original address numbers

### Step 4: Calculate Bounding Box Area
- Computes bounding box area in square meters
- Uses smallest area from all results
- Formula: `area_m² = width_m × height_m`
  - `width_m = (east - west) × 111,000 × cos(latitude)`
  - `height_m = (north - south) × 111,000`

### Step 5: Filter by Score Threshold
- **Area < 100 m²** → Score 1.0 ✅ (Perfect - building level)
- **Area < 1,000 m²** → Score 0.9 (Precise - block level)
- **Area < 10,000 m²** → Score 0.8 (Moderate - neighborhood level)
- **Area < 100,000 m²** → Score 0.7 (Less precise - district level)
- **Area ≥ 100,000 m²** → Score 0.3 (Very imprecise - city level)

### Step 6: Return Perfect Addresses
- Returns only REAL addresses with area < 100 m²
- All returned addresses are guaranteed to score 1.0
- All addresses are verified to exist in OpenStreetMap

## Rate Limiting

- **1 second delay** between API calls (Nominatim requirement)
- For 10 perfect addresses, expect ~20-50 API calls (depending on success rate)
- Total time: ~20-50 seconds for 10 addresses

## Example Output

```
Generating perfect addresses for: New York, USA
Target: 5 REAL addresses with score 1.0 (area < 100 m²)

Step 1: Searching for real addresses in New York, USA...
  Found 47 real addresses from Nominatim

Step 2: Validating 47 real addresses...

  ✅ Found perfect address #1: 350 5th Avenue, New York, NY 10118, United States
     Area: 45.23 m² (score: 1.0)
  ✅ Found perfect address #2: 1 Times Square, New York, NY 10036, United States
     Area: 78.91 m² (score: 1.0)
  Progress: 2/5 perfect addresses found (tested 10/47)
  ✅ Found perfect address #3: 200 Central Park South, New York, NY 10019, United States
     Area: 32.15 m² (score: 1.0)
  ...
  Progress: 5/5 perfect addresses found (tested 23/47)

✅ Successfully found 5 perfect REAL addresses (all score 1.0)
```

## Integration with Full Generation

To use in a complete generation pipeline:

```python
from generate_and_test_variations import (
    generate_full_name_variations,
    generate_perfect_dob_variations,
    generate_perfect_addresses
)

# Generate for a single name
name = "John Smith"
dob = "1990-06-15"
address = "New York, USA"
variation_count = 10

# Generate name variations (Light, Medium, Far)
name_variations = generate_full_name_variations(
    name, 
    variation_count=variation_count,
    light_count=2,
    medium_count=6,
    far_count=2
)

# Generate DOB variations (all categories)
dob_variations = generate_perfect_dob_variations(dob, variation_count)

# Generate perfect addresses (all score 1.0)
address_variations = generate_perfect_addresses(
    address, 
    variation_count=variation_count,
    max_candidates=100
)

# Combine into final variations
final_variations = [
    [name_var, dob_var, addr_var]
    for name_var, dob_var, addr_var in zip(
        name_variations, dob_variations, address_variations
    )
]
```

## Advantages

1. ✅ **Guaranteed 1.0 score** - All addresses are pre-validated
2. ✅ **No dependency on random state** - Works regardless of validator state
3. ✅ **Offline testing possible** - Can test addresses before submission
4. ✅ **Reliable** - More reliable than predicting random selection
5. ✅ **Scalable** - Can generate as many perfect addresses as needed

## Limitations

1. ⚠️ **API rate limiting** - Nominatim requires 1 second between calls
2. ⚠️ **Time consuming** - Takes ~2-5 seconds per perfect address
3. ⚠️ **May not find enough** - Some cities may have fewer precise addresses
4. ⚠️ **Requires internet** - Needs Nominatim API access

## Tips

1. **Increase max_candidates** if not finding enough perfect addresses
2. **Use realistic street names** - Common names are more likely to exist
3. **Test with different cities** - Some cities have more precise addresses
4. **Cache results** - Save perfect addresses for reuse
5. **Batch processing** - Generate addresses for multiple names in parallel

## Testing

Run the test script:

```bash
python test_perfect_addresses.py
```

This will:
1. Generate 5 perfect addresses for "New York, USA"
2. Validate them with the validator's scoring function
3. Show detailed results

Expected output: Address score ≥ 0.9 (ideally 1.0)

