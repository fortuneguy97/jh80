# Address Cache System

## Overview

This system pre-generates and caches addresses for all valid countries that the validator might choose, eliminating the need for real-time Nominatim API calls during validation.

## How It Works

1. **Pre-generation:** Run `generate_address_cache.py` to generate addresses for all ~200-300 valid countries
2. **Caching:** Addresses are stored in `address_cache.json` (local file)
3. **Fast Lookup:** When the validator asks for addresses, the generator checks the cache first
4. **Fallback:** If cache is unavailable, falls back to Nominatim API (slower)

## Benefits

- ✅ **Fast:** No API calls during validation (instant lookup)
- ✅ **Reliable:** No rate limiting issues
- ✅ **Complete:** Covers all countries the validator might choose
- ✅ **Validated:** All cached addresses pass all three validation checks (1.0 score)

## Setup

### Step 1: Generate the Cache

```bash
python generate_address_cache.py
```

This will:
- Load all valid countries from GeonamesCache (~200-300 countries)
- For each country, generate 15 addresses from Nominatim
- Validate each address (heuristic, region, API checks)
- Store in `address_cache.json`

**Time:** ~50-75 minutes (1 request/second × 200 countries × 15 addresses ≈ 50 minutes)

### Step 2: Use the Cache

The `unified_generator.py` automatically uses the cache:

```python
from unified_generator import generate_perfect_addresses

# This will check cache first, then fall back to API if needed
addresses = generate_perfect_addresses("United States", variation_count=15)
```

## Cache Structure

```json
{
  "addresses": {
    "United States": [
      "123 Main Street, New York, NY 10001, United States",
      "456 Oak Avenue, Los Angeles, CA 90001, United States",
      ...
    ],
    "France": [
      "10 Rue de la Paix, 75001 Paris, France",
      ...
    ],
    ...
  },
  "city_to_country": {
    "london": "United Kingdom",
    "paris": "France",
    "tokyo": "Japan",
    ...
  },
  "generated_at": "2025-01-23 10:30:00",
  "total_countries": 250,
  "cached_countries": 245,
  "failed_countries": ["Antarctica", "Vatican"]
}
```

## City Name Handling

The cache includes a `city_to_country` mapping that automatically maps city names to countries:

- `"London"` → `"United Kingdom"`
- `"Paris"` → `"France"`
- `"Tokyo"` → `"Japan"`

This allows the generator to handle city names in seed addresses:

```python
# These all work:
generate_perfect_addresses("United States", 15)  # Country name
generate_perfect_addresses("London", 15)         # City name → maps to UK
generate_perfect_addresses("London, United Kingdom", 15)  # City, Country format
```

## Address Validation

All cached addresses pass **all three validation checks**:

1. ✅ **Heuristic:** `looks_like_address()` (30+ chars, 20+ letters, 2+ commas)
2. ✅ **Region:** `validate_address_region()` (city/country matches seed)
3. ✅ **API:** Bounding box area < 100 m² (guaranteed 1.0 score)

## Cache Updates

If you need to update the cache:

1. Delete `address_cache.json`
2. Run `generate_address_cache.py` again
3. New addresses will be generated

## Troubleshooting

### Cache Not Found

If you see:
```
⚠️  Address cache not found at address_cache.json
   Run 'python generate_address_cache.py' to generate the cache
```

**Solution:** Run `generate_address_cache.py` to generate the cache.

### Cache Incomplete

If some countries failed:
```
❌ Failed to get enough addresses for [Country] (got 5)
```

**Solution:** The generator will fall back to Nominatim API for those countries. You can re-run the cache generator to try again.

### City Not Found

If a city name isn't in the mapping:
```
⚠️  City 'SomeCity' not in cache, falling back to Nominatim API
```

**Solution:** The generator will use Nominatim API as fallback. The city mapping covers most major cities, but not all.

## Performance

- **With Cache:** ~0.001 seconds per address (instant lookup)
- **Without Cache:** ~1 second per address (Nominatim API rate limit)

For a full synapse (15 names × 15 addresses = 225 addresses):
- **With Cache:** ~0.2 seconds total
- **Without Cache:** ~225 seconds (3.75 minutes)

## Files

- `generate_address_cache.py` - Script to generate the cache
- `address_cache.json` - Cache file (generated, not in git)
- `unified_generator.py` - Generator that uses the cache
- `ADDRESS_CACHE_README.md` - This file

## Notes

- The cache file is **not** committed to git (too large, ~1-2 MB)
- Each miner should generate their own cache
- Cache generation is a one-time setup (takes ~1 hour)
- Cache is valid indefinitely (addresses don't change)

