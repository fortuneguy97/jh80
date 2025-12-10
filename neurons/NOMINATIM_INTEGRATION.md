# Nominatim Integration in ollama_generator.py

## Overview

`ollama_generator.py` now includes **built-in Nominatim integration** to generate REAL, geocodable addresses that maximize validator scores.

## How It Works

```
┌─────────────────────────────────────────┐
│  Validator Request Arrives              │
│  Identity: ["John Smith", "1990-01-01", │
│            "New York, USA"]             │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Parse City & Country                   │
│  ├─ Extract: "New York", "USA"          │
│  └─ Check cache for this location       │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Fetch Real Addresses from Nominatim   │
│  ├─ Query: "New York, USA"              │
│  ├─ Filter: place_rank >= 18            │
│  ├─ Extract: Street names               │
│  └─ Format: "123 Broadway, New York,    │
│             USA"                         │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Build Ollama Prompt                    │
│  ├─ Include REAL addresses in prompt    │
│  ├─ Instruct: "Use these addresses"     │
│  └─ Show 15 real address examples       │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Ollama Generates Variations            │
│  ├─ Uses real addresses from prompt     │
│  ├─ Modifies street numbers slightly    │
│  └─ Returns: [[name, dob, address], ...]│
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Validator Checks with Nominatim       │
│  ├─ Geocodes 3 random addresses         │
│  ├─ Checks bounding box area            │
│  └─ Scores: 0.7-1.0 (REAL addresses!)   │
└─────────────────────────────────────────┘
```

## Key Features

### 1. **Automatic Address Fetching**
```python
# Automatically extracts city and country from seed address
city, country = parse_city_country_from_address("New York, USA")
# Returns: ("New York", "USA")

# Fetches real addresses from Nominatim
real_addresses = get_real_addresses_from_nominatim("New York", "USA", limit=30)
# Returns: ["123 Broadway, New York, USA", "456 5th Avenue, New York, USA", ...]
```

### 2. **Intelligent Caching**
```python
# Results are cached per city+country
_real_addresses_cache = {
    "new york,usa": ["123 Broadway, New York, USA", ...],
    "london,uk": ["10 Downing Street, London, UK", ...],
}

# Subsequent requests for same location use cache (no API call)
```

### 3. **Rate Limiting**
```python
# Respects Nominatim usage policy
time.sleep(1.0)  # 1 second between API calls
```

### 4. **Prompt Enhancement**
When real addresses are available, the prompt includes:
```
REAL ADDRESSES FROM OPENSTREETMAP (USE THESE FOR MAXIMUM SCORES):
================================================================================
Below are REAL, VERIFIED addresses from OpenStreetMap that are GUARANTEED to be geocodable.
Using these addresses will give you the HIGHEST scores (0.7-1.0).

INSTRUCTIONS:
1. Use these addresses as templates for your variations
2. You can modify street numbers slightly (e.g., 123 → 125, 127)
3. Keep the street name, city, and country EXACTLY as shown
4. Add postal codes if missing to meet 30+ character requirement
5. Add neighborhood/district names for extra length

REAL ADDRESSES TO USE:
  1. 123 Broadway, New York, USA
  2. 456 5th Avenue, New York, USA
  3. 789 Wall Street, New York, USA
  ...

CRITICAL: These are REAL addresses - using them = HIGH SCORES!
```

## Benefits

### Before (Without Nominatim):
```python
# Ollama imagines addresses
prompt = "Generate REAL addresses for New York, USA"
ollama_response = ["123 Fake St, New York, USA", "456 Imaginary Ave, New York, USA"]

# Validator checks with Nominatim
validator_score = 0.3  # Not geocodable = LOW SCORE ❌
```

### After (With Nominatim):
```python
# Fetch real addresses first
real_addresses = get_real_addresses_from_nominatim("New York", "USA")
# ["123 Broadway, New York, USA", "456 5th Avenue, New York, USA"]

# Include in prompt
prompt = f"Use these REAL addresses: {real_addresses}"
ollama_response = ["125 Broadway, New York, USA", "458 5th Avenue, New York, USA"]

# Validator checks with Nominatim
validator_score = 0.9  # Geocodable = HIGH SCORE ✅
```

## Score Comparison

| Address Type | Geocodable? | Validator Score | TAO Earnings |
|-------------|-------------|-----------------|--------------|
| Fake/Imaginary | ❌ No | 0.3 | Low ❌ |
| Generic | ⚠️ Maybe | 0.3-0.5 | Low ⚠️ |
| Real (Nominatim) | ✅ Yes | 0.7-1.0 | High ✅ |

## Configuration

### Requirements
```bash
# Install requests for Nominatim API
pip install requests
```

### Optional: Disable Nominatim
If you want to disable Nominatim (not recommended):
```python
# In ollama_generator.py, set:
REQUESTS_AVAILABLE = False
```

## Monitoring

Watch your logs to see Nominatim in action:

```bash
# Successful fetch
🔄 Generating variations for: John Smith (UAV: False)
   Fetching real addresses for New York, USA...
   ✅ Got 25 real addresses from Nominatim

# Cache hit (no API call)
🔄 Generating variations for: Jane Doe (UAV: False)
   Fetching real addresses for New York, USA...
Using cached addresses for new york, usa

# No addresses found
🔄 Generating variations for: Bob Johnson (UAV: False)
   Fetching real addresses for Unknown City, Unknown...
   ⚠️  No real addresses found - Ollama will generate addresses
```

## Fallback Behavior

If Nominatim fails or returns no results:
1. ✅ Ollama still generates addresses (based on prompt instructions)
2. ⚠️ Addresses might not be geocodable (lower scores)
3. ℹ️ No error - miner continues working

## API Usage

### Nominatim API Endpoint
```
https://nominatim.openstreetmap.org/search
```

### Request Parameters
```python
params = {
    "q": "New York, USA",           # Query
    "format": "json",                # Response format
    "limit": 150,                    # Max results (30 * 5)
    "addressdetails": 1,             # Include address components
    "extratags": 1,                  # Include extra tags
    "namedetails": 1                 # Include name details
}
```

### Response Filtering
```python
# Only accept street-level or better
if result.get('place_rank', 0) >= 18:
    # Extract street name
    road = address_details.get('road', '')
    # Format address
    formatted = f"{number} {road}, {city}, {country}"
```

## Performance

### Cache Hit Rate
- First request for location: API call (1-2 seconds)
- Subsequent requests: Cache hit (<1ms)
- Cache size: Unlimited (grows with unique locations)

### API Call Frequency
- 1 call per unique city+country combination
- Rate limit: 1 second between calls
- Typical: 1-3 API calls per validator request

## Troubleshooting

### No Real Addresses Found
```
⚠️  No real addresses found - Ollama will generate addresses
```

**Causes:**
- City/country not recognized by Nominatim
- No street-level data available
- API timeout or error

**Solution:**
- Check city/country spelling
- Try alternative city names
- Ollama will still generate addresses (fallback)

### Requests Not Available
```
⚠️  Cannot fetch real addresses (requests=False)
```

**Solution:**
```bash
pip install requests
```

### API Timeout
```
Nominatim request failed: timeout
```

**Solution:**
- Check internet connection
- Nominatim might be down (rare)
- Cached results will be used if available

## Best Practices

1. ✅ **Always install requests**: `pip install requests`
2. ✅ **Let caching work**: Don't clear cache unnecessarily
3. ✅ **Monitor logs**: Check if real addresses are being fetched
4. ✅ **Respect rate limits**: Don't modify the 1-second delay
5. ✅ **Use proper User-Agent**: Already configured correctly

## Comparison with variation_generator_clean.py

Both files now have Nominatim integration:

| Feature | ollama_generator.py | variation_generator_clean.py |
|---------|-------------------|---------------------------|
| Nominatim Integration | ✅ Yes (built-in) | ✅ Yes (built-in) |
| Caching | ✅ Yes | ✅ Yes |
| Rate Limiting | ✅ Yes (1s) | ✅ Yes (1s) |
| Fallback | ✅ Ollama generates | ✅ Generic addresses |
| Code Duplication | ❌ No imports | ❌ No imports |

## Summary

**ollama_generator.py now generates REAL addresses** by:
1. ✅ Fetching real addresses from Nominatim API
2. ✅ Caching results for performance
3. ✅ Including real addresses in Ollama prompt
4. ✅ Respecting rate limits
5. ✅ Falling back gracefully if API fails

**Result:** Higher validator scores (0.7-1.0) = More TAO earnings! 🚀
