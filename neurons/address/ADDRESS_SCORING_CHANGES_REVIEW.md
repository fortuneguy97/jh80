# Address Scoring Changes Review

## Summary of Recent Changes

I've reviewed the recent commits related to address scoring. Here are the key changes:

## 1. **Address Quality Improvements** (Nov 19, 2025)

### Change: Bounding Box Area-Based Scoring
**Commit:** `1b6a02c` - "adding boundry area to increase quality"

**What Changed:**
- **Before:** `check_with_nominatim()` returned `True/False` (boolean)
- **After:** Returns a **score dictionary** with bounding box area-based scoring

**New Scoring System:**
```python
# Score based on smallest bounding box area:
if min_area < 100 m²:      score = 1.0  ✅ Perfect
elif min_area < 1000 m²:   score = 0.9  ✅ Excellent
elif min_area < 10000 m²:  score = 0.8  ✅ Good
elif min_area < 100000 m²: score = 0.7  ✅ Fair
else:                      score = 0.3  ⚠️  Large area (was 0.0)
```

**Key Features:**
- Uses **smallest bounding box area** from all Nominatim results
- Calculates area in **square meters** (not degrees)
- Returns detailed score dictionary with area information

### Change: Fair Scoring for Large Areas
**Commit:** `d57be49` - "making it more fair if area is too big"

**What Changed:**
- **Before:** Areas ≥ 100,000 m² → score = 0.0
- **After:** Areas ≥ 100,000 m² → score = 0.3

**Impact:** Miners with large-area addresses now get partial credit (0.3) instead of zero.

### Change: Stricter Failure Handling
**Commit:** `3c171b0` - "don't get points if any of them fail"

**What Changed:**
- **Before:** If no successful API calls → score = 0.3
- **After:** If **ANY** API call fails OR no successful calls → score = 0.3

**Impact:** More strict - even one failure reduces the score to 0.3.

## 2. **Looks Like Address Exploit Fix** (Nov 18, 2025)

**Commit:** `61f21d6` - "Looks like address exploit (#49)"

**What Changed:**
1. **Parse API returns** to ensure addresses are valid
2. **Removed more symbols** in cheat detection

**Impact:** 
- Fixed the exploit we discovered
- Stricter validation of addresses returned from Nominatim API
- More symbols blocked in cheat detection

## 3. **Current Address Scoring Flow**

### Step 1: Heuristic Check (`looks_like_address`)
- ✅ Must have 30+ characters (alphanumeric)
- ✅ Must have 20+ letters
- ✅ Must have 2+ commas
- ✅ Must have numbers
- ✅ Must not have special characters (`:`, `%`, `$`, `@`, `*`, etc.)

### Step 2: Region Validation (`validate_address_region`)
- ✅ City/country must match seed address
- ⚠️ **BUG STILL EXISTS:** Compares extracted city/country against entire seed string
- This will fail for "City, Country" format seeds

### Step 3: API Validation (`check_with_nominatim`)
- ✅ Address must exist in Nominatim
- ✅ Place rank ≥ 20
- ✅ Name field must be in address
- ✅ Numbers in display_name must match original address
- ✅ Score based on **smallest bounding box area**:
  - < 100 m² → 1.0
  - < 1000 m² → 0.9
  - < 10000 m² → 0.8
  - < 100000 m² → 0.7
  - ≥ 100000 m² → 0.3

### Final Score Calculation
```python
if nominatim_failed_calls > 0 or len(nominatim_scores) == 0:
    base_score = 0.3  # Any failure = 0.3
else:
    base_score = sum(nominatim_scores) / len(nominatim_scores)  # Average of successful scores
```

## 4. **Key Changes Summary**

| Aspect | Before | After |
|--------|--------|-------|
| **API Return** | Boolean (True/False) | Score dictionary with area-based scoring |
| **Large Areas** | 0.0 score | 0.3 score (more fair) |
| **Failure Handling** | Only if all fail | If ANY fail → 0.3 |
| **Scoring Method** | Pass/Fail | Area-based (100m² = 1.0, 1000m² = 0.9, etc.) |
| **Exploit** | Empty seeds = 1.0 | Still exists (line 1866-1867) |

## 5. **What This Means for Miners**

### ✅ **Good News:**
1. **Area-based scoring** is more fair - smaller areas get higher scores
2. **Large areas** now get 0.3 instead of 0.0
3. **Detailed scoring** allows for partial credit

### ⚠️ **Challenges:**
1. **Region validation bug** still exists - will fail for "City, Country" format
2. **Stricter failure handling** - one failure = 0.3 score
3. **Exploit still works** - empty seed addresses = 1.0

### 🎯 **Strategy:**
1. **Generate addresses with small bounding box areas** (< 100 m² for 1.0 score)
2. **Use real addresses from Nominatim** (they'll have valid bounding boxes)
3. **Ensure all addresses pass validation** (one failure = 0.3)
4. **Consider the exploit** if validator sends empty seeds

## 6. **Recommendations**

1. **Update address generation** to prioritize addresses with small bounding box areas
2. **Test with actual validator** to see if region validation bug is still an issue
3. **Monitor for empty seed addresses** - exploit still works
4. **Focus on quality** - one failure reduces score to 0.3

## 7. **Code Locations**

- **Address grading:** `MIID/validator/reward.py` line 1864-2083
- **API validation:** `MIID/validator/reward.py` line 285-385
- **Bounding box calculation:** `MIID/validator/reward.py` line 245-290
- **Exploit location:** `MIID/validator/reward.py` line 1866-1867

