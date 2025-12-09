# Simple Address Generator

## Overview

This script (`generate_and_validate_addresses_simple.py`) generates addresses by:
1. **Pulling addresses directly from Nominatim** (via search or reverse geocoding)
2. **Validating each address immediately** with `rewards.py` functions
3. **Only keeping addresses** that pass all validation checks

## Usage

```bash
# Generate 15 addresses for a country
python3 generate_and_validate_addresses_simple.py --country "Poland" --count 15

# Generate with specific cities
python3 generate_and_validate_addresses_simple.py --country "Philippines" --count 15 --cities "Manila" "Cebu"

# Generate and test with rewards.py
python3 generate_and_validate_addresses_simple.py --country "Poland" --count 15 --test
```

## How It Works

### 1. Address Generation Strategy

The script uses multiple strategies to find addresses:

- **Country-wide search**: Searches for addresses in the entire country
- **City-specific search**: If cities are provided, searches each city
- **Reverse geocoding**: Uses random coordinates around major cities to get precise addresses
- **Generic queries**: Searches for "street", "avenue", "road", etc.

### 2. Validation Process

For each address found, the script validates:

1. **Heuristic Check** (`looks_like_address`):
   - Minimum 30 characters
   - Minimum 20 letters
   - At least 2 commas

2. **Region Validation** (`validate_address_region`):
   - Extracts city/country from address
   - Matches against seed country/city

3. **API Validation** (`check_with_nominatim`):
   - Searches Nominatim for the address
   - Calculates bounding box area
   - Score based on area (< 100 m² = 1.0, < 1000 m² = 0.9, etc.)

### 3. Address Format Priority

The script prioritizes addresses with **house numbers at the start** (like Poland format):
- ✅ Good: `"26, Siedlisko, gmina Grabowiec, ..."`
- ❌ Bad: `"San Gabriel 2nd, Bayambang, ..."`

This ensures addresses are precise and findable in Nominatim's API.

## Output

The script shows:
- **Real-time progress**: Each address is validated as it's found
- **Validation results**: Shows which checks pass/fail
- **Final summary**: Lists all valid addresses found
- **Optional testing**: With `--test`, runs `_grade_address_variations` to get final scores

## Example Output

```
================================================================================
GENERATING ADDRESSES FOR: POLAND
================================================================================
Target: 15 valid addresses
Search queries: 51
================================================================================

[Query 1/51] Searching: 'Poland'
  🔍 Searching Nominatim: 'Poland' (attempt 1/3)...
  ✅ Found 1 results from Nominatim
  🔄 Validating 1 addresses...

  [1/1] Testing: 18, Nowogrodzka, Krucza, ...
         ✅ Has house number at start: '18'
    ✅ PASSED | Looks: True | Region: True | API: 1.0000 (area: 77.85 m²)
  ✅ ACCEPTED (1/15): 18, Nowogrodzka, ...

📊 Progress: 1/15 valid addresses found
```

## Rate Limiting

The script respects Nominatim's rate limits:
- **1 request per second** (`NOMINATIM_SLEEP = 1.0`)
- **Automatic retries** for connection errors (3 attempts with exponential backoff)
- **User-Agent header** required (set via `USER_AGENT` environment variable)

## Troubleshooting

### No addresses found

- **Check network connectivity**: Nominatim may be unreachable
- **Check rate limits**: Too many requests may cause 429 errors
- **Try different cities**: Some cities have better address coverage

### API validation failing

- **Network timeouts**: Nominatim API may be slow or unreachable
- **Address format**: Ensure addresses have house numbers at start
- **Area too large**: Addresses with bounding box > 100 m² score lower

### Region validation failing

- **Country name mismatch**: Ensure country name matches exactly
- **City extraction**: Some addresses may not extract city correctly

## Configuration

Edit the script to customize:

```python
NOMINATIM_SLEEP = 1.0  # Seconds between requests
USER_AGENT = "Your-App/1.0 (contact@example.com)"  # Set via env var
```

## Next Steps

1. **Generate addresses for all countries**: Run the script for each country in your list
2. **Save to cache**: Add addresses to `address_cache.json` for reuse
3. **Test with full synapse**: Use generated addresses in `unified_generator.py`

