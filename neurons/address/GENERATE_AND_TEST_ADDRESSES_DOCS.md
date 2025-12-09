# Generate and Test Addresses Script Documentation

## 📋 Overview

`generate_and_test_addresses.py` is a comprehensive address generation and validation tool that:
- Queries OpenStreetMap (OSM) via Overpass API to find real buildings with address tags
- Assembles complete addresses from OSM data
- Validates each address using the same validation logic as `rewards.py`
- Performs batch validation to ensure addresses achieve perfect scores (1.0)
- Generates a cache of validated addresses for use in the MIID subnet

## 🎯 Purpose

This script is designed to:
1. **Generate high-quality addresses** that will pass the MIID validator's strict validation
2. **Ensure addresses score 1.0** by using the exact same validation functions as `rewards.py`
3. **Create a reliable address cache** for testing and production use
4. **Validate addresses comprehensively** through multiple validation stages

## 🔄 Workflow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Query Overpass API                                        │
│    - Search for buildings with address tags                  │
│    - Filter by country (and optionally city)                 │
│    - Extract address components (house number, street, etc.) │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Assemble Addresses                                         │
│    - Combine OSM tags into full address strings              │
│    - Format: "Number Street, City, Postcode, Country"        │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Individual Validation (for each address)                  │
│    Step 1: Heuristic Check (looks_like_address)              │
│    Step 2: Region Validation (validate_address_region)      │
│    Step 3: Nominatim API Check (check_with_nominatim)         │
│    → Only addresses scoring ≥ 0.99 are kept                  │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Batch Validation                                           │
│    - Test all addresses together using _grade_address_variations │
│    - Verify final overall score                              │
│    - Generate detailed validation report                     │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Save Results                                               │
│    - Export to JSON file with metadata                       │
│    - Include validation details and scores                   │
└─────────────────────────────────────────────────────────────┘
```

## 📦 Dependencies

### Required Python Packages:
- `requests` - For API calls to Overpass and Nominatim
- `logging` - For detailed logging
- `json` - For data serialization
- `argparse` - For command-line arguments

### Required MIID Components:
- `MIID/validator/reward.py` - Contains validation functions:
  - `looks_like_address()` - Heuristic address format validation
  - `validate_address_region()` - Country/region matching
  - `check_with_nominatim()` - Nominatim API validation
  - `_grade_address_variations()` - Batch validation scoring

## 🚀 Usage

### Basic Usage

```bash
# Generate 15 perfect addresses for a country
python3 generate_and_test_addresses.py --country "United Kingdom"

# Generate addresses for a specific city
python3 generate_and_test_addresses.py --country "United Kingdom" --city "London"

# Custom target number of addresses
python3 generate_and_test_addresses.py --country "United States" --target 50

# Save results to file
python3 generate_and_test_addresses.py --country "France" --output addresses_france.json
```

### Command-Line Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--country` | ✅ Yes | None | Country name (e.g., "United Kingdom", "United States") |
| `--city` | ❌ No | None | City name for targeted search (e.g., "London", "New York") |
| `--target` | ❌ No | 15 | Number of perfect addresses to generate |
| `--output` | ❌ No | None | Output JSON file path (if not specified, results are only logged) |

### Examples

```bash
# UK addresses
python3 generate_and_test_addresses.py --country "United Kingdom" --city "Oxford" --target 15

# US addresses
python3 generate_and_test_addresses.py --country "United States" --city "New York" --target 20

# French addresses with output file
python3 generate_and_test_addresses.py --country "France" --city "Paris" --output france_addresses.json
```

## 🔍 Detailed Function Breakdown

### 1. `query_overpass_for_addresses()`

**Purpose**: Query Overpass API to find buildings with complete address tags

**How it works**:
1. Constructs Overpass query to search within country boundaries
2. Optionally restricts to specific city within country (prevents wrong matches, e.g., Oxford UK vs Oxford Ohio)
3. Filters for nodes/ways/relations with both `addr:housenumber` and `addr:street` tags
4. Extracts address components from OSM tags
5. Validates coordinates are within expected country boundaries

**Query Structure**:
```overpass
[out:json][timeout:30];
area["name"="United Kingdom"]["admin_level"="2"]->.country;
area["name"="Oxford"]["place"~"^(city|town)$"](area.country)->.city;
(
  nwr["addr:housenumber"]["addr:street"](area.city);
);
out body;
>;
out skel qt;
```

**Returns**: List of address dictionaries with:
- `housenumber` - House/building number
- `street` - Street name
- `city` - City name
- `postcode` - Postal code (if available)
- `country` - Country name
- `lat` / `lon` - Coordinates
- `osm_type` / `osm_id` - OSM element identifiers

### 2. `assemble_address()`

**Purpose**: Combine OSM address components into a formatted address string

**Format**: `"Number Street, City, Postcode, Country"`

**Example**:
- Input: `{housenumber: "26", street: "High Street", city: "Oxford", postcode: "OX1 1DP", country: "United Kingdom"}`
- Output: `"26 High Street, Oxford, OX1 1DP, United Kingdom"`

### 3. `validate_single_address()`

**Purpose**: Validate a single address through all three validation stages

**Validation Pipeline**:

#### Stage 1: Heuristic Check
- **Function**: `looks_like_address()`
- **Purpose**: Verify address format matches expected patterns
- **Checks**:
  - Contains house number
  - Contains street name
  - Proper formatting
  - Valid characters
- **Result**: Pass/Fail (boolean)

#### Stage 2: Region Validation
- **Function**: `validate_address_region()`
- **Purpose**: Verify address belongs to the specified country
- **Checks**:
  - Country name appears in address
  - Country matches expected country
  - Handles country name variations (UK/United Kingdom, USA/United States)
- **Result**: Pass/Fail (boolean)

#### Stage 3: Nominatim API Check
- **Function**: `check_with_nominatim()`
- **Purpose**: Verify address exists in OpenStreetMap and calculate precision score
- **Process**:
  1. Searches Nominatim API for the address
  2. Calculates bounding box area of results
  3. Scores based on area:
     - `< 100 m²` → Score 1.0 (perfect)
     - `< 1000 m²` → Score 0.9
     - `< 10000 m²` → Score 0.8
     - `< 100000 m²` → Score 0.7
     - `≥ 100000 m²` → Score 0.3
- **Result**: Score (0.0 to 1.0) or "TIMEOUT" or 0.0

**Returns**: `(is_perfect: bool, score: float, details: dict)`

**Details Dictionary Contains**:
- `address` - The address string
- `heuristic` - Heuristic check result
- `region` - Region validation result
- `api_score` - Nominatim API score
- `api_area` - Building area in square meters
- `api_result` - "SUCCESS", "TIMEOUT", or "FAILED"

### 4. `generate_and_validate_addresses()`

**Purpose**: Main generation loop that queries Overpass and validates addresses until target is reached

**Process**:
1. **Query Overpass** for address candidates
2. **Assemble** addresses from OSM data
3. **Deduplicate** addresses (skip already tried)
4. **Validate** each candidate address
5. **Collect** perfect addresses (score ≥ 0.99)
6. **Repeat** if target not reached (up to 5 attempts)
7. **Return** list of perfect addresses

**Retry Logic**:
- Maximum 5 attempts
- Increases query limit if no addresses found
- Tries different cities if multiple cities specified
- Rate limits between queries (5 seconds)

**Rate Limiting**:
- 2 seconds between individual address validations
- 5 seconds between Overpass queries
- Respects Nominatim's 1 request/second limit

### 5. `test_batch_with_rewards()`

**Purpose**: Final batch validation using the exact same function as the MIID validator

**How it works**:
1. Formats addresses into the structure expected by `_grade_address_variations()`
2. Calls `_grade_address_variations()` from `rewards.py`
3. Extracts and logs detailed validation results
4. Returns complete validation report

**Output Includes**:
- Overall score (0.0 to 1.0)
- Heuristic validation results
- Region matching statistics
- API validation details:
  - Total API calls made
  - Successful vs failed calls
  - Individual address scores and areas

## 📊 Logging

### Log Files
- **Location**: `logs/address_generation_YYYYMMDD_HHMMSS.log`
- **Format**: Timestamped log files with detailed validation information

### Log Levels
- **INFO**: Normal operation, validation results
- **WARNING**: Non-critical issues (timeouts, retries)
- **ERROR**: Critical failures (API errors, validation failures)
- **DEBUG**: Detailed traceback information

### Log Structure
```
================================================================================
ADDRESS GENERATION AND VALIDATION STARTED (Overpass API)
================================================================================
Log file: logs/address_generation_20251126_153000.log
================================================================================

================================================================================
GENERATING ADDRESSES FOR: United Kingdom (city: Oxford)
================================================================================
Using Overpass API to query OpenStreetMap for real addresses
================================================================================

📡 Querying Overpass API for United Kingdom (city: Oxford)
✅ Overpass response received in 2.45 seconds
   Found 1234 elements
✅ Extracted 856 addresses with required tags

📋 Testing 856 unique candidate addresses...
   Estimated time: ~28.5 minutes (2s per address)

  [1/856] Validating: 26 High Street, Oxford, OX1 1DP, United Kingdom...
      Step 1: Heuristic check...
         ✅ PASSED: Address format valid
      Step 2: Region validation...
         ✅ PASSED: Region matches United Kingdom
      Step 3: Nominatim API check...
         ✅ PASSED: Score=1.0000, Area=45.23 m² (took 1.23s)
  ✅ PERFECT ADDRESS FOUND! (1/15)
```

## 📁 Output Format

### JSON Output Structure

```json
{
  "country": "United Kingdom",
  "city": "Oxford",
  "perfect_addresses": [
    "26 High Street, Oxford, OX1 1DP, United Kingdom",
    "15 Broad Street, Oxford, OX1 3AS, United Kingdom",
    ...
  ],
  "count": 15,
  "final_score": 1.0,
  "validation_result": {
    "overall_score": 1.0,
    "heuristic_perfect": true,
    "region_matches": 15,
    "total_addresses": 15,
    "api_result": true,
    "detailed_breakdown": {
      "api_validation": {
        "total_eligible_addresses": 15,
        "total_calls": 3,
        "total_successful_calls": 3,
        "total_failed_calls": 0,
        "api_attempts": [
          {
            "address": "26 High Street, Oxford, OX1 1DP, United Kingdom",
            "api": "nominatim",
            "result": 1.0,
            "score_details": {
              "score": 1.0,
              "min_area": 45.23,
              "areas": [45.23],
              "num_results": 1
            }
          },
          ...
        ]
      }
    }
  },
  "timestamp": "2025-11-26T15:30:00Z"
}
```

## ⚙️ Configuration

### Overpass API Settings

```python
OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_TIMEOUT = 30  # seconds
```

### Rate Limiting

```python
# Between individual address validations
time.sleep(2.0)  # 2 seconds

# Between Overpass queries
time.sleep(5)  # 5 seconds
```

### Retry Logic

```python
max_attempts = 5  # Maximum Overpass query attempts
query_limit = 500  # Initial query limit (increases if needed)
```

## 🎯 Validation Criteria

An address is considered **perfect** (score 1.0) if:

1. ✅ **Heuristic Check Passes**
   - Contains house number
   - Contains street name
   - Proper formatting

2. ✅ **Region Validation Passes**
   - Country matches expected country
   - Address contains country name

3. ✅ **Nominatim API Score ≥ 0.99**
   - Address found in Nominatim
   - Building area < 100 m² (most precise)
   - Returns valid bounding box

## 🔧 Troubleshooting

### No Addresses Found from Overpass

**Symptoms**: `Found 0 elements` or `No addresses found from Overpass`

**Possible Causes**:
1. Country name doesn't match OSM data exactly
2. City name doesn't exist in OSM
3. No buildings with complete address tags in that area
4. Overpass API timeout

**Solutions**:
- Try without `--city` parameter (country-wide search)
- Verify country name spelling (use exact OSM country name)
- Try a different city
- Increase `OVERPASS_TIMEOUT` if timeouts occur

### All Addresses Fail Validation

**Symptoms**: Many addresses found but none pass validation

**Possible Causes**:
1. Addresses don't exist in Nominatim database
2. Address format doesn't match OSM data
3. Country has weak OSM coverage
4. Nominatim API rate limiting (403 errors)

**Solutions**:
- Check logs for specific failure reasons
- Try a different country/city with better OSM coverage
- Increase rate limiting delays
- Verify Nominatim API is accessible

### Nominatim API Timeouts

**Symptoms**: `TIMEOUT: API call timed out`

**Possible Causes**:
1. Nominatim API is slow or overloaded
2. Network connectivity issues
3. Rate limiting from Nominatim

**Solutions**:
- Wait and retry (script has retry logic)
- Use self-hosted Nominatim instance
- Increase timeout in `check_with_nominatim()` function

### Low Success Rate

**Symptoms**: Many addresses tested but few pass

**This is normal!** Address validation is strict by design:
- Only addresses with precise building locations (< 100 m²) score 1.0
- Many real addresses have larger bounding boxes (0.9, 0.8, 0.7 scores)
- The script will keep trying until target is reached

**Solutions**:
- Be patient (script will try multiple queries)
- Use cities with dense OSM data (major cities)
- Lower `--target` if needed

## 📈 Performance

### Typical Performance

- **Overpass Query**: 2-5 seconds
- **Address Validation**: ~2 seconds per address (including API calls)
- **Total Time for 15 addresses**: 30-60 minutes (depends on success rate)

### Factors Affecting Performance

1. **OSM Data Density**: More addresses = faster generation
2. **Validation Success Rate**: Higher success rate = fewer queries needed
3. **Nominatim API Speed**: Faster API = quicker validation
4. **Network Latency**: Lower latency = faster API calls

## 🔐 Best Practices

1. **Start with Major Cities**: Better OSM coverage and faster results
2. **Use Specific Cities**: More targeted searches are faster
3. **Be Patient**: Validation is thorough and may take time
4. **Monitor Logs**: Check logs for detailed validation information
5. **Save Results**: Always use `--output` to save validated addresses
6. **Respect Rate Limits**: Don't modify rate limiting (respects Nominatim's limits)

## 🆚 Comparison with `generate_address_cache.py`

| Feature | `generate_and_test_addresses.py` | `generate_address_cache.py` |
|---------|--------------------------------|----------------------------|
| **Purpose** | Generate and test addresses for specific country/city | Generate comprehensive cache for all countries |
| **Scope** | Single country/city | All countries |
| **Validation** | Individual + batch validation | Individual validation only |
| **Output** | JSON file with validation details | JSON cache file |
| **Use Case** | Testing, targeted generation | Production cache generation |
| **Rate Limiting** | 2s between validations | 1s between validations |
| **Logging** | Detailed per-address logs | Summary logs |

## 📚 Related Files

- `MIID/validator/reward.py` - Validation functions
- `generate_address_cache.py` - Production cache generator
- `validate_cached_addresses.py` - Cache validation tool

## 🎓 Example Session

```bash
$ python3 generate_and_test_addresses.py --country "United Kingdom" --city "Oxford" --target 15 --output oxford_addresses.json

2025-11-26 15:30:00 | INFO     | ================================================================================
2025-11-26 15:30:00 | INFO     | ADDRESS GENERATION AND VALIDATION STARTED (Overpass API)
2025-11-26 15:30:00 | INFO     | ================================================================================
2025-11-26 15:30:00 | INFO     | Log file: logs/address_generation_20251126_153000.log
2025-11-26 15:30:00 | INFO     | ================================================================================

2025-11-26 15:30:00 | INFO     | ================================================================================
2025-11-26 15:30:00 | INFO     | GENERATING ADDRESSES FOR: United Kingdom (city: Oxford)
2025-11-26 15:30:00 | INFO     | ================================================================================
2025-11-26 15:30:00 | INFO     | Using Overpass API to query OpenStreetMap for real addresses
2025-11-26 15:30:00 | INFO     | ================================================================================

2025-11-26 15:30:02 | INFO     | ================================================================================
2025-11-26 15:30:02 | INFO     | ATTEMPT 1/5
2025-11-26 15:30:02 | INFO     | ================================================================================
2025-11-26 15:30:02 | INFO     | Current progress: 0/15 perfect addresses

2025-11-26 15:30:02 | INFO     | 📡 Querying Overpass API for United Kingdom (city: Oxford)
2025-11-26 15:30:05 | INFO     | ✅ Overpass response received in 2.45 seconds
2025-11-26 15:30:05 | INFO     |    Found 1234 elements
2025-11-26 15:30:05 | INFO     | ✅ Extracted 856 addresses with required tags

2025-11-26 15:30:05 | INFO     | 📋 Testing 856 unique candidate addresses...
2025-11-26 15:30:05 | INFO     |    Estimated time: ~28.5 minutes (2s per address)

[... validation process ...]

2025-11-26 15:58:30 | INFO     | 🎉 TARGET REACHED! Found 15 perfect addresses

2025-11-26 15:58:30 | INFO     | ================================================================================
2025-11-26 15:58:30 | INFO     | BATCH VALIDATION WITH rewards.py
2025-11-26 15:58:30 | INFO     | ================================================================================
2025-11-26 15:58:30 | INFO     | Testing 15 addresses together...

[... batch validation ...]

2025-11-26 15:58:35 | INFO     | Overall Score: 1.0000
2025-11-26 15:58:35 | INFO     | 💾 Results saved to oxford_addresses.json
```

## ✅ Summary

This script is a comprehensive tool for generating and validating high-quality addresses that will pass the MIID validator's strict requirements. It uses real OpenStreetMap data and validates addresses through the exact same pipeline used by the validator, ensuring 100% compatibility and perfect scores.

