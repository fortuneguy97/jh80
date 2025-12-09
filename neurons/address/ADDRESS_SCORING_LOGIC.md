# Address Scoring Logic Documentation

## Overview

This document explains how address scoring works in the MIID validator, including where the logic is located and how it processes addresses from multiple names.

## Key Finding: Only 3 Addresses Are API Validated

**Important**: For all addresses across all names (e.g., 225 addresses from 15 names), only **3 addresses are randomly selected** for API validation via Nominatim.

---

## Code Location and Flow

### 1. Entry Point: `get_name_variation_rewards()`

**File**: `MIID/validator/reward.py`  
**Line**: 2212-2712

This is the main function that calculates rewards for all miners. It calls the address grading function once per miner.

```python
# Line 2667-2670
# Grade address variations before final reward calculation
start_time = time.time()
address_grading_score = _grade_address_variations(variations, seed_addresses, miner_metrics, self.uid, uid)
miner_metrics["address_grading"] = address_grading_score
```

**Key Point**: This function is called **once per miner**, not once per name. It processes all addresses from all names together.

---

### 2. Main Address Grading Function: `_grade_address_variations()`

**File**: `MIID/validator/reward.py`  
**Line**: 1885-2104

This function processes all addresses from all names and returns a single `overall_score`.

#### Step 1: Collect All Addresses from All Names

**Lines**: 1890-1903

```python
# Collect all addresses with their corresponding seed addresses
all_addresses = []
address_seed_mapping = []
for name_idx, name in enumerate(variations.keys()):
    if name in variations and len(variations[name]) >= 1 and name_idx < len(seed_addresses):
        # Extract address variations (index 2 of each [name_var, dob_var, address_var] array)
        all_variations = variations[name]
        address_variations = [var[2] for var in all_variations if len(var) > 2]
        if address_variations and seed_addresses[name_idx]:
            valid_addrs = [addr for addr in address_variations if addr and addr.strip()]
            all_addresses.extend(valid_addrs)  # ← ALL addresses combined here
            # Map each address to its corresponding seed address
            seed_addr = seed_addresses[name_idx]
            address_seed_mapping.extend([seed_addr] * len(valid_addrs))
```

**What happens**: All addresses from all 15 names are collected into a single `all_addresses` list.

---

#### Step 2: Heuristic Validation (All Addresses)

**Lines**: 1926-1983

```python
# Process each name and validate addresses
heuristic_perfect = True
region_matches = 0
api_validated_addresses = []  # Will store tuples of (addr, seed_addr, seed_name)

for name_idx, name in enumerate(variations.keys()):
    # ... extract address variations for this name ...
    
    for i, addr in enumerate(address_variations):
        # Step 1: Check if looks like address
        looks_like = looks_like_address(addr)
        
        # Step 2: Check if country or city matches seed
        region_match = False
        if looks_like:
            region_match = validate_address_region(addr, seed_addr)
        
        # Track validation results
        passed_validation = looks_like and region_match
        if not looks_like or not region_match:
            heuristic_perfect = False
        
        if passed_validation:
            # Store address for potential API validation
            api_validated_addresses.append((addr, seed_addr, name))
            region_matches += 1
```

**What happens**: 
- All addresses are validated with heuristics (looks_like_address + region_match)
- If **any** address fails → `heuristic_perfect = False` → return score 0.0 (no API calls)
- If **all** addresses pass → addresses are added to `api_validated_addresses` list

**Early Exit Check** (Lines 1985-2002):
```python
# If first 2 steps fail, return 0 immediately (no API call needed)
if not heuristic_perfect:
    return {
        "overall_score": 0.0,
        "heuristic_perfect": False,
        "api_result": False,
        ...
    }
```

---

#### Step 3: Random Selection for API Validation (ONLY 3 ADDRESSES)

**Lines**: 2013-2016

```python
if api_validated_addresses:
    # Randomly choose up to 3 different addresses for API validation with Nominatim
    max_addresses = min(3, len(api_validated_addresses))
    chosen_addresses = random.sample(api_validated_addresses, max_addresses)
```

**What happens**:
- From all addresses that passed heuristics (could be 225 addresses)
- **Only 3 addresses are randomly selected** using `random.sample()`
- These 3 addresses will be validated via Nominatim API

**Example**:
- 225 addresses total (15 names × 15 addresses)
- All 225 pass heuristics
- 3 addresses randomly selected (e.g., address #47, #123, #201)
- Only these 3 get API calls

---

#### Step 4: API Validation (Nominatim Calls)

**Lines**: 2021-2059

```python
# Try Nominatim API (up to 3 calls)
nominatim_scores = []
for i, (addr, seed_addr, seed_name) in enumerate(nominatim_addresses):
    result = check_with_nominatim(addr, validator_uid, miner_uid, seed_addr, seed_name)
    
    # Extract score and details from result
    score = None
    if isinstance(result, dict) and "score" in result:
        score = result["score"]
        nominatim_successful_calls += 1
        nominatim_scores.append(result["score"])
    elif result == "TIMEOUT":
        nominatim_timeout_calls += 1
    else:
        nominatim_failed_calls += 1
    
    # Wait 1 second between API calls to prevent rate limiting
    if i < len(nominatim_addresses) - 1:
        time.sleep(1.0)
```

**What happens**:
- Up to 3 API calls are made (one per selected address)
- Each API call returns a score (1.0, 0.9, 0.8, 0.7, or 0.3 based on bounding box area)
- Scores are stored in `nominatim_scores` list

---

#### Step 5: Calculate Final Address Score

**Lines**: 2075-2081

```python
# Scoring based on individual API results using actual scores from API calls
if nominatim_failed_calls > 0 or len(nominatim_scores) == 0:
    # Any failure or no successful calls results in 0.3 score
    base_score = 0.3
else:
    # Use the average of all successful API call scores
    base_score = sum(nominatim_scores) / len(nominatim_scores)
```

**What happens**:
- If **any** API call fails → `base_score = 0.3`
- If **all** API calls succeed → `base_score = average of the 3 API scores`

**Example**:
- 3 API calls: scores = [1.0, 1.0, 0.9]
- `base_score = (1.0 + 1.0 + 0.9) / 3 = 0.967`

---

#### Step 6: Return Overall Score

**Lines**: 2097-2104

```python
return {
    "overall_score": base_score,  # ← Single score for ALL addresses
    "heuristic_perfect": heuristic_perfect,
    "api_result": api_result,
    "region_matches": region_matches,
    "total_addresses": len(all_addresses),
    "detailed_breakdown": address_breakdown
}
```

**What happens**: Returns a single `overall_score` for all addresses from all names.

---

### 3. Final Reward Calculation

**File**: `MIID/validator/reward.py`  
**Lines**: 2667-2702

```python
# Grade address variations before final reward calculation
address_grading_score = _grade_address_variations(variations, seed_addresses, miner_metrics, self.uid, uid)
miner_metrics["address_grading"] = address_grading_score

# Calculate final reward incorporating DOB and address grading
if quality_scores:
    avg_quality = sum(quality_scores) / len(quality_scores)
    avg_base_score = sum(base_scores) / len(base_scores)
    
    # Separate weights for each component
    quality_weight = 0.2
    dob_weight = 0.1
    address_weight = 0.7  # ← Address has 70% weight
    
    # Calculate each component separately
    quality_component = avg_quality * quality_weight
    
    # DOB component
    dob_component = dob_grading_score["overall_score"] * dob_weight
    
    # Address component
    address_component = address_grading_score["overall_score"] * address_weight
    
    # Final quality is sum of all components
    final_quality = quality_component + dob_component + address_component
    
    rewards[i] = final_quality * completeness_multiplier
```

**What happens**:
- The single `overall_score` from address grading is multiplied by 0.7 (70% weight)
- Combined with name quality (20%) and DOB (10%)
- Final reward = `(quality × 0.2) + (dob × 0.1) + (address × 0.7)`

---

## API Validation Function: `check_with_nominatim()`

**File**: `MIID/validator/reward.py`  
**Lines**: 285-412

This function validates a single address via Nominatim API and returns a score based on bounding box area.

### Score Calculation (Lines 372-382)

```python
# Use the smallest area for scoring
min_area = min(areas)

# Score based on smallest area
if min_area < 100:
    score = 1.0
elif min_area < 1000:
    score = 0.9
elif min_area < 10000:
    score = 0.8
elif min_area < 100000:
    score = 0.7
else:
    score = 0.3
```

**Scoring Rules**:
- `< 100 m²` → **1.0** (very precise location)
- `< 1,000 m²` → **0.9**
- `< 10,000 m²` → **0.8**
- `< 100,000 m²` → **0.7**
- `≥ 100,000 m²` → **0.3** (too broad)

---

## Complete Flow Diagram

```
15 Names × 15 Addresses = 225 Total Addresses
         ↓
[Step 1: Collect All Addresses]
    Collect all 225 addresses into single list
         ↓
[Step 2: Heuristic Validation]
    Validate ALL 225 addresses:
    - looks_like_address() ✓
    - validate_address_region() ✓
         ↓
    If ANY fails → Return 0.0 (no API calls)
    If ALL pass → Continue
         ↓
[Step 3: Random Selection]
    Randomly select 3 addresses from 225
    (e.g., address #47, #123, #201)
         ↓
[Step 4: API Validation]
    Make 3 Nominatim API calls:
    - Address #47 → Score: 1.0
    - Address #123 → Score: 1.0
    - Address #201 → Score: 0.9
         ↓
[Step 5: Calculate Average]
    base_score = (1.0 + 1.0 + 0.9) / 3 = 0.967
         ↓
[Step 6: Return Overall Score]
    Return overall_score = 0.967
         ↓
[Step 7: Final Reward]
    address_component = 0.967 × 0.7 = 0.677
    final_reward = quality_component + dob_component + address_component
```

---

## Key Takeaways

1. **Single Function Call**: `_grade_address_variations()` is called **once per miner**, not once per name.

2. **All Addresses Combined**: All addresses from all names are collected into a single list and processed together.

3. **Heuristic Validation**: **ALL** addresses must pass heuristics, or the score is 0.0.

4. **API Validation**: Only **3 addresses** are randomly selected for API validation, regardless of total count.

5. **Single Overall Score**: One `overall_score` is returned for all addresses, not separate scores per name.

6. **Final Weight**: Address score has **70% weight** in final reward calculation.

7. **Sample-Based Validation**: The validator uses a sample-based approach - all addresses must pass heuristics, but only a small sample (3) are validated via API.

---

## Code References Summary

| Component | File | Lines | Description |
|-----------|------|-------|-------------|
| Entry Point | `reward.py` | 2667-2670 | Calls `_grade_address_variations()` |
| Main Function | `reward.py` | 1885-2104 | `_grade_address_variations()` - processes all addresses |
| Address Collection | `reward.py` | 1890-1903 | Collects all addresses from all names |
| Heuristic Validation | `reward.py` | 1926-1983 | Validates all addresses with heuristics |
| Random Selection | `reward.py` | 2013-2016 | **Selects only 3 addresses for API** |
| API Validation | `reward.py` | 2021-2059 | Makes up to 3 Nominatim API calls |
| Score Calculation | `reward.py` | 2075-2081 | Calculates average of API scores |
| API Function | `reward.py` | 285-412 | `check_with_nominatim()` - validates single address |
| Final Reward | `reward.py` | 2667-2702 | Combines address score (70% weight) with other components |

---

## Example Scenarios

### Scenario 1: Perfect Addresses
- **225 addresses** total
- **All 225** pass heuristics
- **3 addresses** randomly selected for API
- **All 3 API calls** return 1.0
- **Final score**: `(1.0 + 1.0 + 1.0) / 3 = 1.0`

### Scenario 2: Mixed Quality
- **225 addresses** total
- **All 225** pass heuristics
- **3 addresses** randomly selected for API
- **API scores**: [1.0, 0.9, 0.8]
- **Final score**: `(1.0 + 0.9 + 0.8) / 3 = 0.9`

### Scenario 3: One API Failure
- **225 addresses** total
- **All 225** pass heuristics
- **3 addresses** randomly selected for API
- **2 succeed** (1.0, 1.0), **1 fails** (0.0)
- **Final score**: `0.3` (any failure caps at 0.3)

### Scenario 4: Heuristic Failure
- **225 addresses** total
- **224 pass**, **1 fails** heuristics
- **Final score**: `0.0` (no API calls made)

---

## Notes

- The validator does **NOT** validate each name's addresses separately
- The validator does **NOT** average 15 separate address scores
- The validator processes all addresses together and returns one overall score
- Only 3 addresses are API validated, regardless of total count (could be 10, 50, 225, or 1000 addresses)

