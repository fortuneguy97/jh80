# Name Scoring Bottlenecks Analysis

## Test Results Summary

**Test Name**: Maria Garcia  
**Name Quality Score**: 0.4128 ✅ (Above 0.4 target)  
**Name Component (20% weight)**: 0.0826

---

## Detailed Breakdown

### 1. Similarity Score (60% weight within name quality) - **MAJOR BOTTLENECK**

**Current Performance:**
- **First Name Similarity**: 0.2073 (Very Low)
  - Phonetic: 0.0000 ❌ (All variations fail phonetic matching)
  - Orthographic: 0.4146 (Moderate)
- **Last Name Similarity**: 0.0198 ❌ (Extremely Low)
  - Phonetic: 0.2250 (Low)
  - Orthographic: 0.1717 (Very Low)

**Problem:**
- The validator applies a **penalty multiplier of 0.1** when similarity score < 0.2 (see `rewards.py` line 914-918)
- This means similarity scores below 0.2 are reduced to 10% of their original value
- **Last name similarity (0.0198) is being penalized**, reducing the overall score significantly

**Required Distribution (from query template):**
- Phonetic: 10% Light (0.80-1.00), 30% Medium (0.60-0.79), 60% Far (0.30-0.59)
- Orthographic: 20% Light (0.70-1.00), 50% Medium (0.50-0.69), 30% Far (0.20-0.49)

**Actual Variations Generated:**
1. `m.g.` (initials - rule-compliant)
2. `m. g.` (initials - rule-compliant)
3. `mg` (initials - rule-compliant)
4. `Maira Garcia` (should be Medium/Far phonetic, Medium orthographic)
5. `Maria Gracia` (should be Medium/Far phonetic, Medium orthographic)
6. `Marai Garcia` (should be Medium/Far phonetic, Medium orthographic)
7. `Maria Garcai` (should be Medium/Far phonetic, Medium orthographic)
8. `Maria Garcis` (should be Medium/Far phonetic, Medium orthographic)
9. `Mariia Garcia` (should be Medium/Far phonetic, Medium orthographic)

**Issue**: The variations are not matching the required similarity distribution. The validator checks if variations fall into the correct ranges (Light/Medium/Far) and penalizes mismatches.

**Example of Correct Distribution:**
For 9 variations with 10% Light, 30% Medium, 60% Far phonetic:
- 1 variation should score 0.80-1.00 (Light)
- 3 variations should score 0.60-0.79 (Medium)
- 5 variations should score 0.30-0.59 (Far)

**Current Problem**: Most variations are scoring outside these ranges, causing the distribution quality to be very low.

---

### 2. Rule Compliance (20% weight within name quality) - **MODERATE BOTTLENECK**

**Current Performance:**
- **Score**: 0.3750
- **Expected**: 2-3 variations (30% of 9 = 2.7, rounded to 3)
- **Actual**: 3 variations (initials only)
- **Rules Met**: 1/2 (only `shorten_name_to_initials`, missing `swap_random_letter`)

**Problem:**
- **Zero variations** with `swap_random_letter` rule applied
- This causes `rule_diversity_factor = 0.5` (only 1 of 2 rules satisfied)
- The validator expects BOTH rules to be applied

**Example of Missing Rule:**
- Original: "Maria Garcia" (length: 12)
- Should generate: "Maira Garcia" (swapped 'a' and 'i' in "Maria") ✓
- Should generate: "Maria Gacria" (swapped 'r' and 'c' in "Garcia") ✓
- **CRITICAL**: Length must match EXACTLY (12 characters)

**Current Variations:**
- `Maira Garcia` - length 12 ✓ (but validator didn't recognize as swapped)
- `Marai Garcia` - length 12 ✓ (but validator didn't recognize as swapped)
- `Maria Garcai` - length 12 ✓ (but validator didn't recognize as swapped)

**Why Validator Rejected Them:**
The validator's `is_letters_swapped` function checks:
1. Length must match exactly ✓
2. Exactly 2 positions must differ ✓
3. Those positions must be adjacent ✓
4. Letters must be swapped (original[i] == variation[i+1] AND original[i+1] == variation[i]) ❌

**Example Analysis:**
- Original: "Maria Garcia" → positions: M(0), a(1), r(2), i(3), a(4), space(5), G(6), a(7), r(8), c(9), i(10), a(11)
- Variation: "Maira Garcia" → positions: M(0), a(1), i(2), r(3), a(4), space(5), G(6), a(7), r(8), c(9), i(10), a(11)
- Differences: position 2 (r→i) and position 3 (i→r) ✓
- Check swap: original[2]='r' == variation[3]='r' ✓ AND original[3]='i' == variation[2]='i' ✓
- **This SHOULD pass!** But validator might be checking per name part separately.

**Root Cause**: The validator might be checking first name and last name separately, and "Maira" might not be recognized as a valid swap of "Maria" if the validator is strict about the swap detection algorithm.

---

### 3. Count Score (15% weight) - ✅ **PASSING**

- **First Name**: 1.0000 (6/6.3 variations) ✅
- **Last Name**: 1.0000 (6/6.3 variations) ✅
- **Status**: Perfect count matching

---

### 4. Uniqueness Score (10% weight) - **MODERATE BOTTLENECK**

**Current Performance:**
- **First Name**: 0.6667 (4 unique out of 6) ⚠️
- **Last Name**: 0.6667 (4 unique out of 6) ⚠️

**Problem:**
- Some variations are too similar (combined similarity > 0.99)
- This reduces uniqueness score

**Example of Duplicate Variations:**
- `m.g.`, `m. g.`, `mg` are all initials but might be considered similar
- Multiple variations with "Garcia" unchanged might be considered duplicates

**Solution**: Ensure all variations have combined similarity < 0.99 with each other.

---

### 5. Length Score (15% weight) - ✅ **PASSING**

- **First Name**: 0.9167 ✅
- **Last Name**: 1.0000 ✅
- **Status**: All variations within 60-140% of original length

---

## Scoring Formula Breakdown

```
Name Quality = (First Name Score × 0.3) + (Last Name Score × 0.7) + (Rule Compliance × 0.2)

Where:
- First Name Score = (Similarity × 0.60) + (Count × 0.15) + (Uniqueness × 0.10) + (Length × 0.15)
- Last Name Score = (Similarity × 0.60) + (Count × 0.15) + (Uniqueness × 0.10) + (Length × 0.15)
- Rule Compliance = (Quantity Score × 0.5) + (Rule Diversity × 0.5)
```

**Current Calculation:**
- First Name: 0.4786 = (0.2073 × 0.60) + (1.0 × 0.15) + (0.6667 × 0.10) + (0.9167 × 0.15) = 0.1244 + 0.15 + 0.0667 + 0.1375 = 0.4786 ✓
- Last Name: 0.3786 = (0.0198 × 0.60) + (1.0 × 0.15) + (0.6667 × 0.10) + (1.0 × 0.15) = 0.0119 + 0.15 + 0.0667 + 0.15 = 0.3786 ✓
- Rule Compliance: 0.3750 = (0.75 × 0.5) + (0.5 × 0.5) = 0.375 + 0.25 = 0.625 ❌ (Wait, this doesn't match. Let me recalculate...)

Actually, looking at the metrics:
- `quantity_score`: 0.75 (3/4 expected, but expected is 2.7, so 3/2.7 = 1.11, capped?)
- `rule_diversity_factor`: 0.5 (1/2 rules met)
- Score = 0.3750

**Final Name Quality:**
- Base Score = (0.4786 × 0.3) + (0.3786 × 0.7) = 0.1436 + 0.2650 = 0.4086
- With Rule Compliance: 0.4086 + (0.3750 × 0.2) = 0.4086 + 0.0750 = 0.4836 ❌

Wait, the actual score is 0.4128, which is lower. This suggests the rule compliance might be applied differently, or there's a penalty being applied.

---

## Key Bottlenecks Summary

1. **Similarity Distribution Mismatch** (60% weight) - **CRITICAL**
   - Variations not matching required Light/Medium/Far distribution
   - Similarity scores too low, triggering 0.1x penalty multiplier
   - **Impact**: Reduces similarity component from 60% to ~6% of name quality

2. **Rule Compliance - Missing Swap Rule** (20% weight) - **HIGH**
   - Zero variations with `swap_random_letter` rule
   - Rule diversity factor = 0.5 (only 1/2 rules)
   - **Impact**: Reduces rule compliance from 20% to ~10% of name quality

3. **Uniqueness** (10% weight) - **MODERATE**
   - Some variations too similar (combined similarity > 0.99)
   - **Impact**: Reduces uniqueness component from 10% to ~6.7% of name quality

---

## Recommendations to Reach 0.4+ Name Quality

### 1. Fix Similarity Distribution (Priority: CRITICAL)
- Generate variations that **exactly match** the required distribution:
  - For 10% Light phonetic: 1 variation with phonetic score 0.80-1.00
  - For 30% Medium phonetic: 3 variations with phonetic score 0.60-0.79
  - For 60% Far phonetic: 5 variations with phonetic score 0.30-0.59
- **Strategy**: 
  - Use same-sounding letter substitutions (i↔y, ph↔f) for Light
  - Use vowel changes (a↔e, o↔u) for Medium
  - Use abbreviations or significant changes for Far

### 2. Fix Rule Compliance (Priority: HIGH)
- Generate **at least 1-2 variations** with `swap_random_letter` rule
- **CRITICAL**: Length must match EXACTLY
- **Example for "Maria Garcia"**:
  - "Maira Garcia" (swap 'a' and 'i' in "Maria") - length 12 ✓
  - "Maria Gacria" (swap 'r' and 'c' in "Garcia") - length 12 ✓
- Test that validator recognizes these as swapped

### 3. Improve Uniqueness (Priority: MODERATE)
- Ensure all variations have combined similarity < 0.99
- Vary both first AND last name parts
- Avoid generating multiple variations that are too similar

---

## Example: Target Variations for "Maria Garcia"

**Required Distribution:**
- Phonetic: 1 Light, 3 Medium, 5 Far
- Orthographic: 2 Light, 5 Medium, 2 Far
- Rules: 3 variations (1-2 initials, 1-2 swapped)

**Ideal Variations:**
1. `m.g.` - Initials (rule) - Phonetic: Far, Orthographic: Far
2. `m. g.` - Initials (rule) - Phonetic: Far, Orthographic: Far
3. `Maira Garcia` - Swapped (rule) - Phonetic: Medium, Orthographic: Light
4. `Maria Gacria` - Swapped (rule) - Phonetic: Medium, Orthographic: Light
5. `Merya Garcia` - Phonetic: Light, Orthographic: Medium
6. `Maria Garcya` - Phonetic: Medium, Orthographic: Medium
7. `Mari Garcia` - Phonetic: Far, Orthographic: Medium
8. `Maria Garsia` - Phonetic: Medium, Orthographic: Medium
9. `M. Garcia` - Phonetic: Far, Orthographic: Far

**Key Points:**
- Variations 1-2: Initials (rule-compliant)
- Variations 3-4: Swapped letters (rule-compliant)
- Variations 5-9: Non-rule, matching similarity distribution

---

## Conclusion

**Current Score**: 0.4128 ✅ (Above 0.4 target)  
**Potential Score with Fixes**: ~0.6-0.7

**Main Issues:**
1. Similarity distribution not matching requirements (60% weight)
2. Missing swap_random_letter rule (20% weight)
3. Uniqueness could be improved (10% weight)

**Next Steps:**
1. Update Gemini prompt to generate variations that match similarity distribution EXACTLY
2. Add explicit instructions for swap_random_letter rule with length verification
3. Add uniqueness validation to ensure all variations are sufficiently different

