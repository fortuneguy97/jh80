# Name Scoring Analysis: How It Works and Current Bottlenecks

## Overview

Name scoring is **20% of the total score** and is calculated using a complex formula that evaluates multiple dimensions of name variations. Understanding this mechanism is critical for achieving maximum scores.

## Scoring Formula

```
Final Score = (Name Quality × 0.20) + (DOB Score × 0.10) + (Address Score × 0.70)
Name Quality = (Base Score × 0.80) + (Rule Compliance × 0.20)
```

Where:
- **Base Score** = Weighted combination of First Name (30%) + Last Name (70%)
- **Rule Compliance** = Separate score for rule-based variations (20% of name quality)

## Base Score Components (for Non-Rule Variations)

The base score is calculated separately for **first name** and **last name**, then combined with weights (30% first, 70% last).

### 1. Similarity Distribution (60% weight within base score)

**CRITICAL**: This is the **biggest component** of name quality!

#### Phonetic Similarity
- Uses randomized subset of: **Soundex, Metaphone, NYSIIS**
- Algorithm selection is **deterministic per name** (seeded by hash of original name)
- **Boundaries**:
  - **Light**: 0.80-1.00 (same phonetic code)
  - **Medium**: 0.60-0.79 (similar phonetic code)
  - **Far**: 0.30-0.59 (different phonetic code)

#### Orthographic Similarity
- Uses **Levenshtein distance**: `score = 1.0 - (distance / max_length)`
- **Boundaries**:
  - **Light**: 0.70-1.00 (distance ≤ 30% of max length)
  - **Medium**: 0.50-0.69 (distance 31-50% of max length)
  - **Far**: 0.20-0.49 (distance 51-80% of max length)

#### Distribution Matching
The validator counts how many variations fall into each category and compares against the **required distribution** from the query template.

**Example from test results**:
- Required: 20% Light, 60% Medium, 20% Far (phonetic)
- Actual: Variations scored across all ranges, but distribution didn't match exactly
- **Result**: Low similarity score (0.4422 combined)

### 2. Count Score (15% weight)

- **Expected count**: `variation_count × (1 - rule_percentage)`
- **Tolerance**: 20% base + 5% per 10 expected variations (max 40%)
- **Example**: For 8 variations with 60% rules → expected 3.2 non-rule variations
- **Test result**: Got 6 non-rule variations (expected 3.2) → **Score: 0.5092**

### 3. Uniqueness Score (10% weight)

- Variations are considered "duplicates" if combined similarity > 0.99
- **Formula**: `unique_count / total_count`
- **Test result**: 4 unique out of 6 → **Score: 0.6667**

### 4. Length Score (15% weight)

- **Requirement**: Variations must be 60-140% of original length
- **Formula**: `min(len_var / len_orig, len_orig / len_var) × (1 - abs_diff / len_orig)`
- **Test result**: **Score: 0.8712** (good!)

## Rule Compliance Score (20% weight of name quality)

**CRITICAL**: This is a **separate 20% component** that can significantly impact the final name quality!

### How It Works

1. **Rule Identification**: Validator checks each variation against specified rules:
   - `shorten_name_to_initials`: Must convert ALL name parts to first letter
   - `swap_random_letter`: Must swap exactly 2 adjacent letters, length must match exactly

2. **Rule Compliance Metrics**:
   - **Quantity Score**: How many variations follow rules vs. expected
   - **Rule Diversity**: How many different rules are satisfied
   - **Overall Compliance Ratio**: `compliant_count / total_variations`

3. **Final Rule Score**: Combines quantity, diversity, and compliance ratio

### Test Results Analysis

**From test results**:
```json
"rule_compliance": {
  "score": 0.25,
  "metrics": {
    "compliant_variations_by_rule": {
      "shorten_name_to_initials": ["a.v.", "a. v."],
      "swap_random_letter": []
    },
    "compliance_ratio_overall_variations": 0.25,
    "overall_compliant_unique_variations_count": 2,
    "expected_compliant_variations_count": 4,
    "quantity_score": 0.5,
    "rule_diversity_factor": 0.5,
    "num_target_rules_met": 1,
    "total_target_rules": 2
  }
}
```

**Issues Identified**:
1. ✅ **Initials rule**: 2 variations recognized (good!)
2. ❌ **Swap letter rule**: 0 variations recognized (CRITICAL FAILURE!)
3. ❌ **Expected 4 rule-compliant variations, got only 2** (50% compliance)
4. ❌ **Only 1 out of 2 rules satisfied** (50% diversity)

## Current Bottlenecks (From Test Results)

### Bottleneck #1: Rule Compliance (Score: 0.25)

**Problem**: Only 2/8 variations recognized as rule-compliant (expected 4-5)

**Root Causes**:
1. **Swap letter rule not recognized**:
   - Validator checks for **exact swap** of 2 adjacent letters
   - Length must match **exactly** (no extra/missing characters)
   - Example: "Anatoly Vyborny" (16 chars) → "Antaoly Vyborny" (16 chars) ✓
   - Wrong: "Anatoly Vybornyy" (17 chars) ✗

2. **Initials format issues**:
   - Validator recognizes: `"f.l."`, `"f. l."`, `"fl"` (lowercase)
   - Wrong: `"A. Vyborny"` (last name still there) ✗
   - Wrong: `"A V"` (uppercase) ✗

**Impact**: 
- Rule compliance score: 0.25 (instead of 1.0)
- Loses 20% × (1.0 - 0.25) = **15% of name quality**
- This alone reduces name quality from 0.47 to ~0.40

### Bottleneck #2: Similarity Distribution (Score: 0.4422)

**Problem**: Variations don't match the required similarity distribution

**Root Causes**:
1. **Phonetic similarity**: Variations not generating in the right ranges
   - Light (0.80-1.00): Need same-sounding substitutions (i↔y, ph↔f)
   - Medium (0.60-0.79): Need similar-sounding vowel changes
   - Far (0.30-0.59): Need significant but related changes

2. **Orthographic similarity**: Levenshtein distance not matching ranges
   - Light: Distance ≤ 30% of max length
   - Medium: Distance 31-50% of max length
   - Far: Distance 51-80% of max length

**Impact**:
- Similarity is 60% of base score
- Low similarity → low base score → low name quality

### Bottleneck #3: Count Mismatch (Score: 0.5092)

**Problem**: Got 6 non-rule variations, expected 3.2

**Root Cause**: Rule compliance is low, so more variations are classified as "non-rule"

**Impact**: 
- Count score: 0.5092 (instead of 1.0)
- Loses 15% × (1.0 - 0.5092) = **7.4% of base score**

### Bottleneck #4: Uniqueness (Score: 0.6667)

**Problem**: Only 4 unique variations out of 6

**Root Cause**: Some variations are too similar (combined similarity > 0.99)

**Impact**:
- Uniqueness score: 0.6667 (instead of 1.0)
- Loses 10% × (1.0 - 0.6667) = **3.3% of base score**

## Example: "Anatoly Vyborny" Scoring Breakdown

### Input
- **Name**: "Anatoly Vyborny" (16 characters)
- **Variations**: 8 total
- **Rules**: 60% rule-compliant (expected 4-5 variations)
- **Similarity**: 20% Light, 60% Medium, 20% Far (phonetic and orthographic)

### Generated Variations
1. `"a.v."` - Initials ✓ (recognized)
2. `"a. v."` - Initials ✓ (recognized)
3. `"antaoly Vyborny"` - Swap? ✗ (not recognized - why?)
4. `"anotly Vyborny"` - Swap? ✗ (not recognized - why?)
5. `"Anatoly Vyboryn"` - Non-rule
6. `"Anatoliy Vyborniy"` - Non-rule
7. `"Anatoly Vybory"` - Non-rule
8. `"Anatoly Vyborniy"` - Non-rule

### Scoring Results

**First Name ("Anatoly")**:
- Similarity: 0.4962 (phonetic: 0.55, orthographic: 0.4425)
- Count: 0.5092 (6 actual vs 3.2 expected)
- Uniqueness: 0.6667 (4 unique out of 6)
- Length: 0.8712
- **Score: 0.5715**

**Last Name ("Vyborny")**:
- Similarity: 0.3297 (phonetic: 0.0, orthographic: 0.6594)
- Count: 0.5092 (6 actual vs 3.2 expected)
- Uniqueness: 0.6667 (4 unique out of 6)
- Length: 0.8712
- **Score: 0.4715**

**Base Score**: (0.5715 × 0.3) + (0.4715 × 0.7) = **0.5270**

**Rule Compliance**: 0.25 (2/8 recognized, expected 4-5)

**Final Name Quality**: (0.5270 × 0.80) + (0.25 × 0.20) = **0.4716**

## Why Swap Letter Rule Failed

Looking at the variations:
- `"antaoly Vyborny"` - Swapped 'n' and 't' in "Anatoly" → "Antaoly"
  - Length: 16 ✓
  - But validator didn't recognize it - why?

**Possible reasons**:
1. Validator might check for swaps in **both** first and last name
2. Validator might require swaps to be in **specific positions**
3. Validator might have additional checks we're not aware of

**Solution**: Need to test with exact swap examples and verify validator recognition

## Recommendations

### 1. Fix Rule Compliance (Highest Priority)

**For Initials**:
- ✅ Use lowercase: `"a.v."`, `"a. v."`, `"fl"`
- ✅ Convert ALL name parts to first letter
- ❌ Don't keep last name: `"A. Vyborny"` ✗

**For Swap Letters**:
- ✅ Length must match **exactly** (count characters!)
- ✅ Swap exactly 2 adjacent letters
- ✅ Verify: `len(original) == len(variation)`
- ❌ Don't add/remove letters
- ❌ Don't swap non-adjacent letters

### 2. Improve Similarity Distribution

**Strategy**:
1. Generate variations targeting specific similarity ranges
2. Test mentally: Will this variation score in Light/Medium/Far?
3. Use phonetic tricks: i↔y, ph↔f, c↔k for Light
4. Use Levenshtein distance calculations for orthographic

### 3. Improve Uniqueness

**Strategy**:
1. Vary both first AND last name parts
2. Avoid generating variations that are too similar
3. Test: Combined similarity < 0.99

### 4. Fix Count Mismatch

**Strategy**:
1. Fix rule compliance first (this will fix count automatically)
2. Ensure exactly `rule_count` variations follow rules
3. Ensure exactly `variation_count - rule_count` variations are non-rule

## Test Results: "John Smith" (Second Synapse)

### Results Summary
- **Name Quality**: 0.4841 ✅ (ABOVE 0.4 TARGET!)
- **Name Component**: 0.0968 (20% of 0.4841)
- **DOB Score**: 1.0000 ✅ (Perfect!)
- **Address Score**: 0.0000 ❌ (Failing format validation)

### Name Quality Breakdown

**First Name ("John")**:
- Similarity: 0.7429 (phonetic: 0.7264, orthographic: 0.7594) ✅
- Count: 0.6959 (5 actual vs 3.2 expected)
- Uniqueness: 1.0000 ✅ (Perfect!)
- Length: 0.9200 ✅
- **Score: 0.7881**

**Last Name ("Smith")**:
- Similarity: 0.0000 ❌ (phonetic: 0.0, orthographic: 0.0) - **CRITICAL ISSUE!**
- Count: 0.6959 (5 actual vs 3.2 expected)
- Uniqueness: 0.6000 (3 unique out of 5)
- Length: 1.0000 ✅
- **Score: 0.3144**

**Base Score**: (0.7881 × 0.3) + (0.3144 × 0.7) = **0.5114**

**Rule Compliance**: 0.3750 (3/8 recognized, expected 4-5)
- Initials: 3 recognized ✅
- Swap letters: 0 recognized ❌

**Final Name Quality**: (0.5114 × 0.80) + (0.3750 × 0.20) = **0.4841** ✅

### Key Findings

1. ✅ **Achieved target**: Name quality 0.4841 > 0.4
2. ❌ **Last name similarity is 0.0**: This is a critical issue - all last name variations are scoring 0 for both phonetic and orthographic similarity
3. ❌ **Swap letter rule not recognized**: 0 variations recognized (expected 2-3)
4. ⚠️ **Count mismatch**: 5 actual vs 3.2 expected (due to rule compliance issues)

### Why Last Name Similarity is 0.0

Looking at the variations:
- "smith" (original) vs "smith" (variation) → Should score high, but showing 0.0
- "simth" (variation) → Should score medium, but showing 0.0
- "smthi" (variation) → Should score medium, but showing 0.0

**Possible reasons**:
1. Validator might be comparing against a different base (full name vs last name only)
2. Variations might not be extracted correctly from full name
3. There might be a bug in similarity calculation for last names

## Target Scores

**Current**: Name Quality = 0.4841 ✅ (ABOVE 0.4 TARGET!)
**Previous Test**: Name Quality = 0.4716

**Improvements made**:
- ✅ Name quality increased from 0.4716 to 0.4841
- ✅ First name similarity improved significantly (0.7429 vs 0.4962)
- ✅ First name uniqueness perfect (1.0 vs 0.6667)
- ❌ Last name similarity dropped to 0.0 (was 0.3297)
- ⚠️ Rule compliance improved slightly (0.375 vs 0.25)

**Remaining issues**:
1. **Last name similarity = 0.0**: Critical - needs investigation
2. **Swap letter rule not recognized**: Need to fix swap examples
3. **Count mismatch**: Will fix automatically when rule compliance is fixed

**Priority**: 
1. Investigate why last name similarity is 0.0
2. Fix swap letter rule recognition
3. Improve rule compliance to reach 0.5+
