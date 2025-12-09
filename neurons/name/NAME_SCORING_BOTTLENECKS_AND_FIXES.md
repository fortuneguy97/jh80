# Name Scoring Bottlenecks and Precise Fixes

## Current Status
- **Name Quality**: 0.4674 (Target: 1.0)
- **Rule Compliance**: 0.2500 (2/8 variations, need 5/8)
- **Similarity**: 0.2212 (very low, needs improvement)
- **Final Score**: 0.4043 (Target: 0.8)

## Bottlenecks Identified

### 1. Rule Compliance (20% weight) - CRITICAL
**Current**: Only 2/8 variations recognized as rule-compliant
**Required**: 5/8 variations (60% of 8)

**Issues**:
- Only 3 initials variations recognized (need 2-3)
- Only 1 swapped variation recognized (need 2-3)
- Many variations have wrong length (extra/missing letters)

**Validator Requirements**:
- **Initials**: Must be lowercase, format "f.l." or "f. l." or "fl"
- **Swapped**: Length must match EXACTLY, exactly 2 adjacent positions swapped

### 2. Similarity (60% weight) - CRITICAL
**Current**: 0.2212 (very low)
**Required**: Match distribution (20% Light, 60% Medium, 20% Far)

**Issues**:
- Variations don't match required similarity ranges
- Phonetic similarity too low (0.0664)
- Orthographic similarity low (0.3496)

### 3. Count (15% weight)
**Current**: 0.5092
**Issue**: Actual count (5) vs Expected (3.2) mismatch

### 4. Uniqueness (10% weight)
**Current**: 0.6667 - OK but could improve

### 5. Length (15% weight)
**Current**: 0.8712 - Good

## Precise Prompt Instructions Added

### For Rule Compliance:

1. **Initials Rule**:
   - Must use lowercase
   - Must use one of 3 formats: "f.l." or "f. l." or "fl"
   - ALL name parts must be converted to first letter
   - Examples provided for each name

2. **Swap Letter Rule**:
   - Length must match EXACTLY (character count)
   - Exactly 2 positions must differ
   - Those positions must be adjacent
   - Letters must be swapped (not just changed)
   - Step-by-step instructions provided
   - Wrong examples shown (what NOT to do)
   - Correct examples with length verification

### For Similarity:

1. **Phonetic Similarity**:
   - Light (0.80-1.00): Same-sounding substitutions (i↔y, ph↔f)
   - Medium (0.60-0.79): Similar-sounding vowel changes
   - Far (0.30-0.59): Significant changes but still related

2. **Orthographic Similarity**:
   - Light (0.70-1.00): Levenshtein ≤ 30% of max length
   - Medium (0.50-0.69): Levenshtein 31-50% of max length
   - Far (0.20-0.49): Levenshtein 51-80% of max length

3. **Distribution Requirements**:
   - Exact counts for each category
   - Examples of variations that fall into each range

## Key Improvements Made

1. ✅ **DOB**: Now consistently 1.0 (all 6 categories covered)
2. ✅ **Address Format**: Passing (Heuristic Perfect: True)
3. ✅ **Address Region**: Passing (8/8 matches)
4. ⚠️ **Address API**: Failing (0 successful, 3 failed)
5. ⚠️ **Name Rules**: Still low (2/8 instead of 5/8)
6. ⚠️ **Name Similarity**: Still low (0.22 instead of 0.6+)

## Next Steps

The prompt has been significantly improved with:
- Precise swap examples with length verification
- Step-by-step instructions
- Wrong examples to avoid
- Similarity distribution requirements
- Execution plans

The remaining issues are:
1. Gemini still not generating enough valid swapped variations
2. Similarity scores still too low

The prompt is now very explicit and should work better with more testing.

