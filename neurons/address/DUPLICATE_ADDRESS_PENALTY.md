# Duplicate Address Penalty

## Answer: YES, You Must Send 15 DIFFERENT Addresses

The validator **checks for duplicate addresses** and applies penalties if you send the same address multiple times for a single name.

## How It Works

### 1. Address Normalization

The validator normalizes addresses before checking for duplicates:

```python
def normalize_address(addr_str):
    # Remove extra spaces, convert to lowercase
    normalized = " ".join(addr_str.split()).lower()
    # Replace commas, semicolons, hyphens with spaces
    normalized = normalized.replace(",", " ").replace(";", " ").replace("-", " ")
    # Remove multiple spaces
    normalized = " ".join(normalized.split())
    return normalized
```

**Examples:**
- `"123 Main St, New York"` → `"123 main st new york"`
- `"123-Main-St, New-York"` → `"123 main st new york"` (same!)
- `"123  Main  Street,  New  York"` → `"123 main street new york"` (same!)

### 2. Duplicate Detection

```python
normalized_addresses = [normalize_address(addr) for addr in address_variations]
duplicates = len(normalized_addresses) - len(set(normalized_addresses))
```

**Example:**
- 15 addresses, all normalize to same → `duplicates = 15 - 1 = 14`

### 3. Penalty Calculation

```python
penalty = duplicates × 0.05  # 5% per duplicate
penalty = min(penalty, 0.5)  # Max 50% penalty
```

**Example:**
- 14 duplicates × 0.05 = 0.7 → Capped at 0.5 (50% penalty)

### 4. Penalty Application

The penalty is applied to the final reward:

```python
total_penalty = extra_names_penalty  # Includes address_duplicates_penalty
completeness_multiplier = max(0.1, 1.0 - total_penalty)
final_reward = final_quality × completeness_multiplier
```

**Example:**
- If `address_duplicates_penalty = 0.5` (50%)
- `completeness_multiplier = 1.0 - 0.5 = 0.5`
- Final reward = `final_quality × 0.5` (50% reduction!)

## Penalty Breakdown

| Duplicates | Penalty | Completeness Multiplier | Final Reward Impact |
|------------|---------|------------------------|---------------------|
| 0 | 0% | 1.0 | No impact |
| 1 | 5% | 0.95 | 5% reduction |
| 5 | 25% | 0.75 | 25% reduction |
| 10 | 50% | 0.5 | 50% reduction |
| 14+ | 50% (capped) | 0.5 | 50% reduction |

## Examples

### ✅ Good: 15 Different Addresses
```python
addresses = [
    "123 Main St, New York, USA",
    "456 Oak Ave, Los Angeles, USA",
    "789 Pine Rd, Chicago, USA",
    # ... 12 more different addresses
]
# duplicates = 0
# penalty = 0%
# completeness_multiplier = 1.0
# ✅ No penalty!
```

### ❌ Bad: 15 Same Addresses
```python
addresses = [
    "123 Main St, New York, USA",
    "123 Main St, New York, USA",
    "123 Main St, New York, USA",
    # ... 12 more identical
]
# duplicates = 14
# penalty = 14 × 0.05 = 0.7 → capped at 0.5 (50%)
# completeness_multiplier = 0.5
# ❌ 50% penalty!
```

### ❌ Bad: 15 Addresses with Slight Variations
```python
addresses = [
    "123 Main St, New York, USA",
    "123 Main Street, New York, USA",  # "St" vs "Street"
    "123-Main-St, New-York, USA",      # Hyphens
    "123  Main  St,  New  York,  USA", # Extra spaces
    # ... all normalize to same
]
# After normalization: all become "123 main st new york usa"
# duplicates = 14
# penalty = 50%
# ❌ Still penalized!
```

## What This Means

1. **You MUST send 15 DIFFERENT addresses** for each name
2. **Slight variations don't help** - they normalize to the same
3. **Penalty is significant** - up to 50% reduction in final reward
4. **The validator checks this** - it's part of the `extra_names_penalty`

## Impact on Your Generator

Your `generate_perfect_addresses()` function already handles this correctly:
- ✅ Generates different addresses from Nominatim
- ✅ Filters by validation (ensures uniqueness)
- ✅ Returns unique addresses

The function should naturally return different addresses, so you're safe! Just make sure you're not accidentally duplicating addresses in `process_full_synapse()`.

## Code Location

**File:** `MIID/validator/reward.py`  
**Lines:** 2432-2442

```python
# Penalty for duplicate variations - addresses (with normalization)
address_duplicates_penalty = 0.0
if address_variations:
    normalized_addresses = [normalize_address(addr) for addr in address_variations if addr]
    duplicates_addresses = len(normalized_addresses) - len(set(normalized_addresses))
    if duplicates_addresses > 0:
        penalty_duplicates = duplicates_addresses * 0.05  # 5% per duplicate
        address_duplicates_penalty += penalty_duplicates

address_duplicates_penalty = min(address_duplicates_penalty, 0.5)  # Max 50% penalty
```

## Conclusion

**YES, you must send 15 different addresses for each name!**

Sending the same address (or addresses that normalize to the same) will result in:
- 5% penalty per duplicate
- Maximum 50% penalty
- Significant reduction in final reward

Your current `generate_perfect_addresses()` function should handle this correctly by generating unique addresses from Nominatim.

