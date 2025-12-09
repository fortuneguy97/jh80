# How Miners Get 0.886 Address Score with 0.000 Sub-scores

## The Mystery

Miners are achieving:
- **Address Score: 0.886**
- **Looks Like Address: 0.000**
- **Address Region Match: 0.000**

This seems impossible because the validator code shows that if `heuristic_perfect` is False (which happens when addresses fail `looks_like_address` or `region_match`), it should return 0.0 immediately.

## Possible Explanations

### 1. Empty Seed Addresses Exploit

**The exploit:** If `seed_addresses` is empty or contains only `None`/empty strings, the validator returns `{"overall_score": 1.0}` immediately (line 1866-1867).

**How it works:**
```python
if not seed_addresses or not any(seed_addresses):
    return {"overall_score": 1.0}  # ⚠️ EXPLOIT!
```

**But wait:** This would give 1.0, not 0.886. So this might not be the full explanation.

### 2. Partial Validation Success

**Theory:** Maybe the metrics shown are **percentages** of addresses that passed, not boolean flags.

**How it could work:**
- If a miner sends 10 addresses:
  - 0 pass `looks_like_address` → "Looks Like Address: 0.000" (0/10 = 0%)
  - 0 pass `region_match` → "Address Region Match: 0.000" (0/10 = 0%)
  - But somehow some addresses still get API validation scores

**But this doesn't make sense** because the code explicitly returns 0.0 if `heuristic_perfect` is False (line 1965-1981).

### 3. API Scores Despite Failed Validation

**Theory:** Maybe the validator is calling the API even when validation fails, and the score comes from API results.

**Looking at the code:**
- Line 1965: If `heuristic_perfect` is False, it returns 0.0 immediately
- The API is only called if `api_validated_addresses` is not empty (line 1992)
- `api_validated_addresses` only contains addresses that passed BOTH `looks_like` AND `region_match` (line 1948-1951)

**So this shouldn't be possible** unless there's a bug or different code path.

### 4. Different Validator Version

**Theory:** The validator code might have been updated, and there's a different scoring mechanism that:
- Allows partial credit for API validation even when heuristic/region fails
- Calculates scores differently than what we see in the code

### 5. Special Region Handling

**Theory:** Maybe the miner is using special regions that bypass normal validation.

**Looking at the code (line 630-637):**
```python
SPECIAL_REGIONS = ["luhansk", "crimea", "donetsk", "west sahara", 'western sahara']

if seed_lower in SPECIAL_REGIONS:
    gen_lower = generated_address.lower()
    return seed_lower in gen_lower  # Simple substring match!
```

**How it could work:**
- If seed is "Crimea" (special region)
- Any address containing "crimea" passes region validation
- But `looks_like_address` might still fail
- However, if `looks_like` fails, `region_match` is never checked (line 1940-1941)

**So this still doesn't explain it.**

### 6. API Score Calculation Bug

**Theory:** Maybe the score of 0.886 is coming from a different calculation, not from `_grade_address_variations`.

**Looking at line 2060:**
```python
base_score = sum(nominatim_scores) / len(nominatim_scores)
```

**If somehow API calls are made:**
- And they return scores like 0.886
- But the validation results show 0.000

**This could happen if:**
- The metrics are calculated from `validation_results` (showing 0% pass rate)
- But the API is called anyway (maybe due to a bug)
- And the API returns a score of 0.886

### 7. Most Likely: Empty Seed Addresses with Partial Scoring

**Theory:** The validator might be:
1. Receiving empty `seed_addresses` for some names
2. Returning 1.0 for those (exploit)
3. But also processing other names with valid seeds
4. Averaging the scores: (1.0 + 0.0 + ...) / N = 0.886

**Or:**
- Some names have empty seeds → 1.0 score
- Other names have valid seeds but fail validation → 0.0 score
- Average = 0.886

## How to Achieve This Score

Based on the code analysis, here's what miners might be doing:

### Strategy 1: Exploit Empty Seed Addresses
1. Send addresses that don't match the seed format
2. Hope validator sends empty `seed_addresses` for some names
3. Get 1.0 score for those names
4. Get 0.0 for others
5. Average = 0.886

### Strategy 2: Use Special Regions
1. Use seed addresses that are special regions (Crimea, Luhansk, etc.)
2. Generate addresses containing those region names
3. Bypass normal region validation
4. But still need to pass `looks_like_address`

### Strategy 3: Find Validator Bug
1. There might be a bug in the validator that allows API calls even when validation fails
2. API returns scores based on bounding box area
3. Even failed addresses get partial credit from API

## Recommendation

To achieve a high address score, miners should:

1. **Try the empty seed exploit first:**
   - Generate addresses that might cause validator to send empty seeds
   - This gives automatic 1.0 score

2. **Use special regions:**
   - If validator sends special region seeds (Crimea, etc.)
   - Generate addresses containing those region names
   - Bypass normal validation

3. **Generate perfect addresses:**
   - Real addresses from Nominatim
   - Area < 100 m² (1.0 score from API)
   - Pass `looks_like_address` heuristic
   - Pass region validation (if possible, despite the bug)

4. **Test with actual validator:**
   - The code we see might not match the actual validator behavior
   - Test to see what actually works

## Conclusion

The score of 0.886 with 0.000 sub-scores is likely due to:
- Empty seed addresses exploit (1.0 score)
- Mixed with failed validations (0.0 score)
- Averaged to 0.886

Or there's a validator bug/feature we haven't identified that allows partial scoring even when validation fails.

