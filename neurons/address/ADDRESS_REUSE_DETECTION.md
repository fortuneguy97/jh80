# How Address Reuse Gets Detected

## Two Detection Mechanisms

There are **TWO separate systems** that catch address reuse within a single miner:

1. **`reward.py`** - Checks duplicates **per name** (simpler normalization)
2. **`cheat_detection.py`** - Checks duplicates **across all names** (aggressive normalization)

---

## Detection #1: `reward.py` (Per-Name Duplicate Detection)

### How It Works

For **each seed name**, the system:
1. Collects all address variations for that name
2. Normalizes each address using `normalize_address()`
3. Counts duplicates: `duplicates = len(normalized_list) - len(set(normalized_list))`
4. Applies penalty: **5% per duplicate**, capped at **50% per name**

### Normalization Function (Simple)

```python
def normalize_address(addr_str):
    # "123 Main St, New York" → "123 main st new york"
    normalized = " ".join(addr_str.split()).lower()
    normalized = normalized.replace(",", " ").replace(";", " ").replace("-", " ")
    normalized = " ".join(normalized.split())
    return normalized
```

### Example: Caught Reusing Same Address

```python
# Miner submits variations for "John Smith"
variations = {
    "John Smith": [
        ["John Smith", "1990-01-01", "123 Main St, New York"],
        ["Jon Smith", "1990-01-01", "123 Main Street, NY"],      # Duplicate!
        ["Johnny Smith", "1990-01-01", "123 Main St, New York"],  # Duplicate!
        ["John Smyth", "1990-01-01", "456 Oak Ave, Boston"],      # Unique
        ["J. Smith", "1990-01-01", "123 Main St, New York"]      # Duplicate!
    ]
}

# After normalization:
normalized = [
    "123 main st new york",  # Original
    "123 main st new york",  # Duplicate (Street → St, NY → New York)
    "123 main st new york",  # Duplicate
    "456 oak ave boston",    # Unique
    "123 main st new york"   # Duplicate
]

# Detection:
# total_addresses = 5
# unique_addresses = 2  ({"123 main st new york", "456 oak ave boston"})
# duplicates = 5 - 2 = 3

# Penalty calculation:
# penalty = 3 duplicates × 0.05 = 0.15 (15%)
# Capped at 0.5 (50%), so penalty = 0.15

# This penalty is added to the "extra_names_penalty" for this name
```

### What Gets Caught

✅ **These are detected as duplicates:**
- `"123 Main St, New York"` vs `"123 Main Street, NY"`
- `"123 Main St"` vs `"123 Main St, New York"` (if normalization makes them same)
- `"123 Main St, New York"` vs `"123 Main St, New York"` (exact match)

❌ **These are NOT detected as duplicates:**
- `"123 Main St, New York"` vs `"123 Main St, Boston"` (different city)
- `"123 Main St"` vs `"456 Main St"` (different number)

---

## Detection #2: `cheat_detection.py` (Cross-Name Duplicate Detection)

### How It Works

For **the entire miner** (across ALL names):
1. Collects ALL addresses from ALL names
2. Normalizes each using `normalize_address_for_deduplication()` (very aggressive)
3. Counts duplicates: `duplicate_count = len(all_addresses) - len(set(all_addresses))`
4. Applies penalty: `min(duplicate_ratio * 0.2, 0.2)` = **up to 20% penalty**

### Normalization Function (Aggressive)

```python
def normalize_address_for_deduplication(addr):
    # 1. Remove disallowed Unicode
    # 2. NFKD normalization + remove diacritics
    # 3. Transliterate to ASCII (Arabic → English, etc.)
    # 4. Extract unique words
    # 5. Sort all letters alphabetically ← KEY DIFFERENCE!
    
    # "123 Main St, New York" → sorted letters from unique words
    # Result: "adeeghikmnorstttwxy" (sorted letters)
```

### Example: Caught Reusing Address Across Names

```python
# Miner submits variations for multiple names
miner_response = {
    "John Smith": [
        ["John Smith", "1990-01-01", "123 Main St, New York"],
        ["Jon Smith", "1990-01-01", "456 Oak Ave, Boston"]
    ],
    "Mary Johnson": [
        ["Mary Johnson", "1985-05-15", "123 Main Street, NY"],      # Duplicate!
        ["Marie Johnson", "1985-05-15", "789 Pine Rd, Chicago"]
    ],
    "David Brown": [
        ["David Brown", "1992-03-20", "123 Main St, New York"],      # Duplicate!
        ["Dave Brown", "1992-03-20", "123 Main St, NY"]            # Duplicate!
    ]
}

# After aggressive normalization (simplified for example):
all_addresses = [
    "adeeghikmnorstttwxy",  # "123 Main St, New York" (John Smith)
    "abceghiknoorstt",      # "456 Oak Ave, Boston" (John Smith)
    "adeeghikmnorstttwxy",  # "123 Main Street, NY" (Mary Johnson) - DUPLICATE!
    "acdeghikmnoprst",      # "789 Pine Rd, Chicago" (Mary Johnson)
    "adeeghikmnorstttwxy",  # "123 Main St, New York" (David Brown) - DUPLICATE!
    "adeeghikmnorstttwxy"   # "123 Main St, NY" (David Brown) - DUPLICATE!
]

# Detection:
# total_addresses = 6
# unique_addresses = 3
# duplicate_count = 6 - 3 = 3
# duplicate_ratio = 3/6 = 0.5 (50% are duplicates)

# Penalty calculation:
# penalty = 0.5 × 0.2 = 0.10 (10%)
# Capped at 0.2 (20%), so penalty = 0.10

# This is the "address_duplication_penalties[i]" for this miner
```

### What Gets Caught (Aggressive)

✅ **These are detected as duplicates even if formatted differently:**
- `"123 Main St, New York"` vs `"123 Main Street, NY"` (same location, different format)
- `"123 Main St"` vs `"Main Street 123"` (same words, different order → sorted letters match)
- `"ул. Ленина, 10"` (Russian) vs `"Lenin Street, 10"` (English) (transliterated to same)

❌ **These are NOT detected as duplicates:**
- `"123 Main St"` vs `"456 Main St"` (different numbers)
- `"123 Main St, New York"` vs `"123 Main St, Boston"` (different cities)

---

## Real-World Example: How You Get Caught

### Scenario: Using a Small Address Pool

```python
# You have a JSON file with only 5 addresses:
addresses = [
    "123 Main St, New York",
    "456 Oak Ave, Boston",
    "789 Pine Rd, Chicago",
    "321 Elm St, Seattle",
    "654 Maple Dr, Portland"
]

# You're asked to generate 10 variations for "John Smith"
# You reuse addresses from your small pool:

miner_response = {
    "John Smith": [
        ["John Smith", "1990-01-01", "123 Main St, New York"],
        ["Jon Smith", "1990-01-01", "123 Main Street, NY"],      # Reused #1
        ["Johnny Smith", "1990-01-01", "123 Main St, New York"],  # Reused #1
        ["John Smyth", "1990-01-01", "456 Oak Ave, Boston"],
        ["J. Smith", "1990-01-01", "456 Oak Avenue, Boston"],      # Reused #2
        ["John S.", "1990-01-01", "789 Pine Rd, Chicago"],
        ["Jonny Smith", "1990-01-01", "789 Pine Road, Chicago"],  # Reused #3
        ["J Smith", "1990-01-01", "321 Elm St, Seattle"],
        ["Johnny S", "1990-01-01", "321 Elm Street, Seattle"],    # Reused #4
        ["J. S.", "1990-01-01", "654 Maple Dr, Portland"]
    ]
}

# Detection in reward.py (per-name):
# For "John Smith":
# - 10 addresses total
# - After normalization, many collapse to same strings
# - Let's say 6 unique addresses remain
# - duplicates = 10 - 6 = 4
# - penalty = 4 × 0.05 = 0.20 (20%)

# Detection in cheat_detection.py (cross-name):
# If you also reuse these same addresses for other names:
# - "Mary Johnson" uses same 5 addresses
# - "David Brown" uses same 5 addresses
# - Total: 30 addresses across 3 names
# - But only 5 unique addresses (after normalization)
# - duplicate_count = 30 - 5 = 25
# - duplicate_ratio = 25/30 = 0.833 (83% duplicates!)
# - penalty = 0.833 × 0.2 = 0.167 (16.7%)
# - Capped at 0.2, so penalty = 0.167

# Combined penalties can significantly reduce your reward!
```

---

## How to Avoid Getting Caught

### ✅ Safe Approach

```python
# Use a LARGE, DIVERSE address pool
# Generate unique addresses for each variation
# Or use addresses that are genuinely different

safe_response = {
    "John Smith": [
        ["John Smith", "1990-01-01", "123 Main St, New York"],
        ["Jon Smith", "1990-01-01", "456 Oak Ave, Boston"],      # Different
        ["Johnny Smith", "1990-01-01", "789 Pine Rd, Chicago"],   # Different
        ["John Smyth", "1990-01-01", "321 Elm St, Seattle"],      # Different
        ["J. Smith", "1990-01-01", "654 Maple Dr, Portland"]     # Different
    ]
}

# No duplicates detected → No penalties!
```

### ❌ Risky Approach

```python
# Using a small pool and reusing addresses
risky_response = {
    "John Smith": [
        ["John Smith", "1990-01-01", "123 Main St, New York"],
        ["Jon Smith", "1990-01-01", "123 Main St, New York"],     # Same!
        ["Johnny Smith", "1990-01-01", "123 Main St, New York"],  # Same!
        # ... more reuses
    ]
}

# High duplicate count → Penalties applied!
```

---

## Summary

**You get caught reusing addresses when:**

1. **Per-name reuse** (`reward.py`):
   - You submit the same (or very similar) address multiple times for the same seed name
   - Penalty: **5% per duplicate**, up to **50% per name**

2. **Cross-name reuse** (`cheat_detection.py`):
   - You reuse the same addresses across different seed names
   - Penalty: **Up to 20%** based on duplicate ratio

**Key Point**: The normalization functions are smart enough to catch:
- Format variations (`"St"` vs `"Street"`, `"NY"` vs `"New York"`)
- Punctuation differences (commas, dashes)
- Even transliterated versions of the same address

**Solution**: Use a **large, diverse address pool** and avoid reusing addresses within the same submission!

