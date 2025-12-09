# Name Score Improvement Plan

## How Validator Evaluates Name Scores

### Scoring Formula

```
Name Quality = (Base Score × 0.8) + (Rule Compliance × 0.2)

Where Base Score = (First Name × 0.3) + (Last Name × 0.7)

And each part score = (Similarity × 0.60) + (Count × 0.15) + (Uniqueness × 0.10) + (Length × 0.15)
```

### Component Breakdown

#### 1. Similarity Distribution (60% weight) - **CRITICAL!**

**How it works:**
- Validator calculates phonetic and orthographic similarity for each variation
- Sorts all similarity scores
- Counts how many fall into each range:
  - **Phonetic**: Light (0.80-1.00), Medium (0.60-0.79), Far (0.30-0.59)
  - **Orthographic**: Light (0.70-1.00), Medium (0.50-0.69), Far (0.20-0.49)
- Compares actual distribution to target distribution
- **Penalty**: If similarity_score < 0.2, gets 0.1x multiplier (huge penalty!)

**How phonetic similarity is calculated:**
- Uses randomized subset of: Soundex, Metaphone, NYSIIS
- Selection is deterministic per name (seeded by hash of original name)
- Weighted average of selected algorithms

**How orthographic similarity is calculated:**
- Uses Levenshtein distance
- Formula: `1.0 - (distance / max_length)`
- For "John" (length 4):
  - Light (0.70-1.00): distance ≤ 1 character
  - Medium (0.50-0.69): distance 2 characters
  - Far (0.20-0.49): distance 3+ characters

**Key Issue**: Variations must actually score in the correct ranges!

#### 2. Count (15% weight)

- Must match expected count with tolerance (20% base + 5% per 10 variations)
- Example: Expected 8, tolerance = 20% = 1.6, so acceptable range is 6.4-9.6

#### 3. Uniqueness (10% weight)

- Validator checks pairwise: `combined_similarity = (phonetic × 0.7) + (orthographic × 0.3)`
- If `combined_similarity > 0.99`, variations are considered duplicates
- Score = unique_count / total_count

#### 4. Length (15% weight)

- Adaptive threshold: 60% for names ≤5 chars, 70% for longer names
- Formula: `length_ratio × (1.0 - min(1.0, absolute_diff / original_len))`
- Target: 60-140% of original length

#### 5. Rule Compliance (20% weight)

- Separate from base score
- Must satisfy expected percentage of variations
- Must satisfy all required rules

## Current Issues

1. **Similarity Distribution Mismatch** (60% weight)
   - Variations not scoring in correct ranges
   - Similarity scores too low, triggering 0.1x penalty

2. **Rule Compliance** (20% weight)
   - Some rules not being recognized
   - Missing expected rule-compliant variations

3. **Uniqueness** (10% weight)
   - Some variations too similar to each other

## Improvement Strategies

### 1. Fix Similarity Distribution (Priority: CRITICAL)

**Problem**: Gemini generates variations but they don't score in the correct ranges.

**Solution**: 
- Pre-calculate target similarity scores for each variation
- Generate variations that will actually score in those ranges
- Use phonetic algorithms to test variations before returning

**Implementation**:
```python
# For each target range, generate variations that will score correctly
# Light phonetic (0.80-1.00): Use same-sounding substitutions
# Medium phonetic (0.60-0.79): Use similar-sounding changes
# Far phonetic (0.30-0.59): Use different-sounding but related

# Light orthographic (0.70-1.00): 1 character change
# Medium orthographic (0.50-0.69): 2 character changes
# Far orthographic (0.20-0.49): 3+ character changes
```

### 2. Improve Prompt Instructions

**Current**: Generic instructions about similarity
**Improved**: Specific instructions with exact score targets

Example:
```
For "John Smith" (length 10):
- Light orthographic (0.70-1.00): Levenshtein distance ≤ 3
  * Generate: "Jhon Smith" (1 char), "Jonh Smith" (1 char)
- Medium orthographic (0.50-0.69): Levenshtein distance 4-5
  * Generate: "Jon Smyth" (4 chars), "John Smythe" (5 chars)
- Far orthographic (0.20-0.49): Levenshtein distance 6-8
  * Generate: "Johnny Smither" (6 chars), "Jonny Smithson" (8 chars)
```

### 3. Post-Processing Validation

**Add validation step**:
- After Gemini generates variations, calculate their actual similarity scores
- If distribution doesn't match, regenerate or adjust variations
- Ensure all variations are unique (combined similarity < 0.99)

### 4. Use Validator Functions Directly

**Instead of guessing**, use the validator's functions:
```python
from MIID.validator.reward import calculate_phonetic_similarity, calculate_orthographic_similarity

# Test each variation before including it
p_score = calculate_phonetic_similarity(original, variation)
o_score = calculate_orthographic_similarity(original, variation)

# Check if it falls in the correct range
if target_range == "Light" and 0.80 <= p_score <= 1.00:
    # Good!
```

## Recommended Implementation

1. **Generate variations with target scores in mind**
   - For each required range, generate variations that will score correctly
   - Use validator functions to verify scores before including

2. **Update Gemini prompt** with:
   - Exact Levenshtein distance targets
   - Specific phonetic transformation examples
   - Clear instructions for each similarity level

3. **Add post-processing validation**:
   - Calculate actual similarity scores
   - Adjust variations if distribution doesn't match
   - Ensure uniqueness

4. **Test and iterate**:
   - Run variations through validator
   - Check actual scores
   - Refine prompt based on results

## Expected Improvement

- Current: 0.5694 name quality
- Target: 0.8+ name quality
- If similarity distribution is fixed: +0.2-0.3 points
- If rule compliance is perfect: +0.05-0.1 points
- **Potential: 0.8-0.9 name quality** (vs current 0.57)

