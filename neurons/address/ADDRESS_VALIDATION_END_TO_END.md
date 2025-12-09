# Address Validation: End-to-End Flow

## ✅ All Components Now Use the Same Functions from `rewards.py`

### 1. **Address Cache Generation** (`generate_address_cache.py`)

**Purpose**: Pre-generate and cache addresses for all countries

**Validation Functions Used** (from `MIID/validator/reward.py`):
- ✅ `looks_like_address(address)` - Heuristic check
- ✅ `validate_address_region(address, seed_address)` - Region validation
- ✅ `compute_bounding_box_areas_meters([result])` - Area calculation

**Flow**:
```
Nominatim API → looks_like_address() → validate_address_region() → compute_bounding_box_areas_meters() → Cache
```

---

### 2. **Miner Address Generation** (`unified_generator.py`)

**Purpose**: Generate addresses when validator requests them

**Validation Functions Used** (from `MIID/validator/reward.py`):
- ✅ `looks_like_address(address)` - Heuristic check
- ✅ `validate_address_region(address, seed_address)` - Region validation
- ✅ `compute_bounding_box_areas_meters([result])` - Area calculation (FIXED - was manual before)

**Flow**:
```
Cache Check → If miss: Nominatim API → looks_like_address() → validate_address_region() → compute_bounding_box_areas_meters() → Return
```

---

### 3. **Validator Scoring** (`rewards.py` - `_grade_address_variations`)

**Purpose**: Score addresses submitted by miners

**Validation Functions Used** (from `MIID/validator/reward.py`):
- ✅ `looks_like_address(addr)` - Heuristic check (line 1936)
- ✅ `validate_address_region(addr, seed_addr)` - Region validation (line 1941)
- ✅ `check_with_nominatim(addr, ...)` - API validation (line 2003)
  - Which internally uses `compute_bounding_box_areas_meters()` (line 340)

**Flow**:
```
Miner Addresses → looks_like_address() → validate_address_region() → check_with_nominatim() → Score
                                                                    ↓
                                                    compute_bounding_box_areas_meters()
```

---

## Validation Order (Same in All Components)

1. **Heuristic Check** (`looks_like_address`)
   - 30+ characters
   - 20+ letters
   - 2+ commas
   - Has numbers

2. **Region Validation** (`validate_address_region`)
   - Extracts city/country from address
   - Matches against seed address
   - Uses `COUNTRY_MAPPING` for normalization
   - Handles special regions (Luhansk, Crimea, etc.)

3. **API Validation** (`check_with_nominatim` or `compute_bounding_box_areas_meters`)
   - Calculates bounding box area
   - Score based on area:
     - < 100 m² = 1.0
     - < 1000 m² = 0.9
     - < 10000 m² = 0.8
     - < 100000 m² = 0.7
     - Otherwise = 0.3

---

## Consistency Guarantees

### ✅ **Same Functions**
All three components import and use the exact same functions from `MIID/validator/reward.py`:
- No duplicate code
- No manual calculations
- No custom logic

### ✅ **Same Validation Order**
All components validate in the same order:
1. Heuristic first
2. Region second
3. API/Area third

### ✅ **Same Area Calculation**
All components use `compute_bounding_box_areas_meters()`:
- Same formula: `111,000 m/degree` for latitude
- Same longitude adjustment: `111,000 * cos(latitude)` for longitude
- Same area calculation: `width_m * height_m`

### ✅ **Same Scoring Logic**
- Addresses with area < 100 m² = 1.0 score
- Same thresholds for all score levels

---

## Benefits

1. **Predictability**: Addresses that pass cache generation will pass miner generation and validator scoring
2. **Consistency**: No discrepancies between what we cache and what gets scored
3. **Maintainability**: Single source of truth (`rewards.py`) for all validation logic
4. **Accuracy**: No manual calculations that might differ from validator logic

---

## Files Updated

1. ✅ `generate_address_cache.py` - Uses `validate_address_region()` and `compute_bounding_box_areas_meters()`
2. ✅ `unified_generator.py` - Uses `compute_bounding_box_areas_meters()` instead of manual calculation
3. ✅ `rewards.py` - Source of truth (no changes needed)

---

## Testing

To verify end-to-end consistency:

1. **Generate cache**: `python3 generate_address_cache.py`
2. **Test miner generation**: Addresses from cache should pass all validations
3. **Test validator scoring**: Same addresses should score 1.0

All three steps use the **exact same functions**, ensuring perfect consistency.

