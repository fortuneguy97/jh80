# How Duplicate Addresses Are Detected

## Overview

Duplicate address detection uses a **normalization process** that converts addresses into a canonical form. Addresses that normalize to the same string are considered duplicates, even if they look different (e.g., different house numbers).

**Function**: `normalize_address_for_deduplication()`  
**Location**: Lines 121-169 in `MIID/validator/cheat_detection.py`

---

## Normalization Process

The normalization process consists of **5 steps** that progressively transform an address into a canonical form:

### Step 0: Remove Disallowed Unicode Characters

**Function**: `remove_disallowed_unicode()` (Lines 83-118)

Removes:
- Currency symbols (like £, €, $)
- Emoji
- Math operators
- Phonetic extensions (U+1D00 to U+1D7F)
- Latin Extended-D block (U+A720 to U+A7FF)

**Keeps**:
- Letters (any language)
- Diacritics (marks)
- ASCII digits (0-9)
- Spaces

**Example**:
```
Input:  "11, Rruga Jeronim de Rada, Kashar, 1050, Albania"
Output: "11, Rruga Jeronim de Rada, Kashar, 1050, Albania"
        (no change in this case)
```

---

### Step 1: Unicode Normalization (NFKD) + Diacritic Removal

1. **NFKD Normalization**: Decomposes characters (e.g., `é` → `e` + `´`)
2. **Remove Diacritics**: Removes combining marks (accents, umlauts, etc.)
3. **Lowercase**: Converts to lowercase

**Example**:
```
Input:  "11, Rruga Jeronim de Rada, Kashar, 1050, Albania"
Step 1: "11, rruga jeronim de rada, kashar, 1050, albania"
```

**Why**: Handles addresses with accented characters (e.g., `Café` → `cafe`)

---

### Step 2: Remove Punctuation and Symbols

1. **Replace Punctuation**: Replaces all punctuation with spaces:
   - `-`, `:`, `,`, `.`, `;`, `!`, `?`, `(`, `)`, `{`, `}`, `[`, `]`, `"`, `'`, `/`, `\`, `|`, `*`, `_`, `=`, `+`, `<`, `>`, `@`, `#`, `^`, `&`
2. **Collapse Whitespace**: Multiple spaces become single space
3. **Trim**: Removes leading/trailing spaces, hyphens, and colons

**Example**:
```
Input:  "11, rruga jeronim de rada, kashar, 1050, albania"
Step 2: "11  rruga jeronim de rada  kashar  1050  albania"
```

**Why**: Different punctuation formats should be treated the same:
- `"11, Street"` = `"11 Street"` = `"11-Street"`

---

### Step 3: Transliterate to ASCII

**Function**: `unidecode()` from `unidecode` library

Converts all non-ASCII characters to their ASCII equivalents:
- Arabic → ASCII
- Cyrillic → ASCII
- Chinese → ASCII
- Greek → ASCII
- etc.

**Example**:
```
Input:  "11  rruga jeronim de rada  kashar  1050  albania"
Step 3: "11  rruga jeronim de rada  kashar  1050  albania"
        (already ASCII, no change)
```

**Why**: Handles addresses in different scripts (e.g., `Москва` → `Moskva`)

---

### Step 4: Extract Unique Words

1. **Replace Commas**: Remaining commas become spaces
2. **Split by Spaces**: Split into words
3. **Get Unique Words**: Use `set()` to remove duplicate words
4. **Join**: Join unique words with spaces

**Example**:
```
Input:  "11  rruga jeronim de rada  kashar  1050  albania"
Step 4: "11 rruga jeronim de rada kashar 1050 albania"
        (removes duplicate spaces, keeps unique words)
```

**Why**: Word order doesn't matter for duplicate detection

---

### Step 5: Extract Letters, Sort, and Join

1. **Extract Letters**: Get all letters (non-word, non-digit characters)
   - Excludes Unicode characters `\u02BB` and `\u02BC`
2. **Sort**: Sort letters alphabetically
3. **Join**: Join sorted letters into a single string

**Example**:
```
Input:  "11 rruga jeronim de rada kashar 1050 albania"
Step 5: Extract letters: "rruga", "jeronim", "de", "rada", "kashar", "albania"
        → "rrugajeronimderadakasharalbania"
        → Sort: "aaaaaaabddeeghiijklmnnorrrrrsu..."
```

**Why**: 
- **Removes numbers** (house numbers don't matter for duplicate detection)
- **Sorts letters** (word order doesn't matter)
- **Creates a canonical form** that's the same for addresses on the same street

---

## Complete Example

### Input Addresses

```
Address 1: "11, Rruga Jeronim de Rada, Kashar, 1050, Albania"
Address 2: "5, Rruga Jeronim de Rada, Kashar, 1050, Albania"
Address 3: "9, Rruga Jeronim de Rada, Kashar, 1050, Albania"
```

### Normalization Process

| Step | Address 1 | Address 2 | Address 3 |
|------|-----------|-----------|-----------|
| **Original** | `11, Rruga Jeronim de Rada, Kashar, 1050, Albania` | `5, Rruga Jeronim de Rada, Kashar, 1050, Albania` | `9, Rruga Jeronim de Rada, Kashar, 1050, Albania` |
| **Step 1** (Lowercase) | `11, rruga jeronim de rada, kashar, 1050, albania` | `5, rruga jeronim de rada, kashar, 1050, albania` | `9, rruga jeronim de rada, kashar, 1050, albania` |
| **Step 2** (Remove punctuation) | `11  rruga jeronim de rada  kashar  1050  albania` | `5  rruga jeronim de rada  kashar  1050  albania` | `9  rruga jeronim de rada  kashar  1050  albania` |
| **Step 3** (Transliterate) | `11  rruga jeronim de rada  kashar  1050  albania` | `5  rruga jeronim de rada  kashar  1050  albania` | `9  rruga jeronim de rada  kashar  1050  albania` |
| **Step 4** (Unique words) | `11 rruga jeronim de rada kashar 1050 albania` | `5 rruga jeronim de rada kashar 1050 albania` | `9 rruga jeronim de rada kashar 1050 albania` |
| **Step 5** (Sorted letters) | `aaaaaaabddeeghiijklmnnorrrrrsu...` | `aaaaaaabddeeghiijklmnnorrrrrsu...` | `aaaaaaabddeeghiijklmnnorrrrrsu...` |

### Result

✅ **All three addresses normalize to the SAME string!**  
→ They are detected as **DUPLICATES**

---

## Duplicate Detection Logic

**Location**: Lines 416-425 in `MIID/validator/cheat_detection.py`

### Process

1. **Normalize All Addresses**:
   ```python
   all_addresses = []
   for addr in address_variations:
       normalized = normalize_address_for_deduplication(addr)
       all_addresses.append(normalized)
   ```

2. **Count Unique Addresses**:
   ```python
   unique_addresses = set(all_addresses)
   duplicate_count = len(all_addresses) - len(unique_addresses)
   ```

3. **Calculate Penalty**:
   ```python
   if duplicate_count > 0:
       duplicate_ratio = duplicate_count / len(all_addresses)
       normalized_penalty = duplicate_ratio * 0.2  # Max 20% penalty
       address_duplication_penalties[i] = min(normalized_penalty, 0.2)
   ```

### Penalty Calculation

- **Duplicate Ratio**: `duplicate_count / total_addresses`
- **Penalty**: `duplicate_ratio × 0.2` (capped at 0.2 = 20%)
- **Example**:
  - 15 addresses total
  - 5 duplicates
  - Duplicate ratio: 5/15 = 0.333
  - Penalty: 0.333 × 0.2 = **0.0667 (6.67%)**

---

## Why This Approach?

### 1. **Handles Different Formats**
- `"11, Street, City"` = `"11 Street City"` = `"11-Street-City"`
- All normalize to the same form

### 2. **Ignores House Numbers**
- `"11, Street"` = `"5, Street"` = `"9, Street"`
- House numbers are removed in Step 5 (only letters are kept)

### 3. **Handles Different Scripts**
- `"Москва"` (Cyrillic) = `"Moskva"` (ASCII)
- Both transliterate to the same ASCII form

### 4. **Handles Accents**
- `"Café"` = `"Cafe"`
- Diacritics are removed in Step 1

### 5. **Word Order Doesn't Matter**
- `"Street Main"` = `"Main Street"`
- Letters are sorted in Step 5

---

## Examples of Duplicate Detection

### Example 1: Same Street, Different House Numbers

**Input**:
```
"11, Rruga Jeronim de Rada, Kashar, 1050, Albania"
"5, Rruga Jeronim de Rada, Kashar, 1050, Albania"
"9, Rruga Jeronim de Rada, Kashar, 1050, Albania"
```

**Result**: ✅ **DUPLICATES** (all normalize to same string)

---

### Example 2: Different Punctuation

**Input**:
```
"11, Main Street, City, Country"
"11 Main Street City Country"
"11-Main-Street-City-Country"
```

**Result**: ✅ **DUPLICATES** (punctuation removed in Step 2)

---

### Example 3: Different Scripts

**Input**:
```
"Москва, Россия"  (Cyrillic)
"Moskva, Rossiya"  (ASCII transliteration)
```

**Result**: ✅ **DUPLICATES** (transliterated to same ASCII in Step 3)

---

### Example 4: Different Streets

**Input**:
```
"11, Rruga Jeronim de Rada, Kashar, 1050, Albania"
"26, Bulevardi i Palmave, Golem, 2504, Albania"
```

**Result**: ❌ **NOT DUPLICATES** (different streets normalize to different strings)

---

## How to Avoid Duplicate Detection

### 1. **Use Different Streets**
- Don't use multiple addresses on the same street
- Use addresses from different streets, neighborhoods, or cities

### 2. **Check Normalization Before Assignment**
```python
from MIID.validator.cheat_detection import normalize_address_for_deduplication

addresses = ["11, Street A", "5, Street A", "9, Street B"]
normalized = [normalize_address_for_deduplication(addr) for addr in addresses]
unique_count = len(set(normalized))

if unique_count < len(addresses):
    print("Warning: Duplicate addresses detected!")
```

### 3. **Use Addresses from Different Locations**
- Different streets
- Different neighborhoods
- Different cities (if allowed by seed address)

---

## Code References

- **Normalization Function**: `normalize_address_for_deduplication()` - Lines 121-169 in `cheat_detection.py`
- **Unicode Removal**: `remove_disallowed_unicode()` - Lines 83-118 in `cheat_detection.py`
- **Duplicate Detection**: Lines 416-425 in `cheat_detection.py`
- **Penalty Application**: Lines 1719-1726 in `reward.py`

---

## Summary

Duplicate address detection uses a **5-step normalization process**:

1. **Remove disallowed Unicode** (currency, emoji, etc.)
2. **NFKD normalization + diacritic removal + lowercase**
3. **Remove punctuation and symbols**
4. **Transliterate to ASCII**
5. **Extract letters, sort, and join**

Addresses that normalize to the **same string** are considered duplicates, even if they:
- Have different house numbers
- Use different punctuation
- Are in different scripts
- Have different word orders

The penalty is calculated as: `(duplicate_count / total_addresses) × 0.2`, capped at 20%.





