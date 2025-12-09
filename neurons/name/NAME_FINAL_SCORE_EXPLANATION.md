# Final Score Calculation for Names

## Overview
The **final score** for name variations is calculated in multiple layers, combining first name, last name, and rule compliance scores.

## Score Components

### 1. Individual Name Part Scores (First/Last)

Each name part (first name and last name) is scored based on:

- **Similarity (60% weight)**: Combined phonetic + orthographic similarity
  - Phonetic similarity: Uses Soundex, Metaphone, NYSIIS algorithms
  - Orthographic similarity: Uses Levenshtein distance
  - Distribution matching: How well variations match Light/Medium/Far distribution

- **Count (15% weight)**: Having the correct number of variations
  - Score = min(actual_count / expected_count, 1.0)

- **Uniqueness (10% weight)**: All variations are unique
  - Score = unique_count / total_count

- **Length (15% weight)**: Reasonable length variations
  - Score based on length ratios

### 2. Base Score (Combined First + Last Name)

```
base_score = (0.3 × first_name_score) + (0.7 × last_name_score)
```

- **First name weight**: 30%
- **Last name weight**: 70%

### 3. Final Score (Base + Rule Compliance)

```
final_score = (0.8 × base_score) + (0.2 × rule_compliance_score)
```

- **Base weight**: 80% (if rules are requested)
- **Rule compliance weight**: 20%
- If no rules are requested, `final_score = base_score` (100% base)

## Example Calculation

For "sara lopez" with perfect scores:

1. **First name "sara"**:
   - Similarity: 1.0 (perfect phonetic match)
   - Count: 1.0 (9/9 variations)
   - Uniqueness: 1.0 (all unique)
   - Length: 0.6 (reasonable lengths)
   - **First name score**: ~0.85

2. **Last name "lopez"**:
   - Similarity: 1.0 (perfect phonetic match)
   - Count: 1.0 (9/9 variations)
   - Uniqueness: 1.0 (all unique)
   - Length: 0.6 (reasonable lengths)
   - **Last name score**: ~0.85

3. **Base score**:
   - `base_score = 0.3 × 0.85 + 0.7 × 0.85 = 0.85`

4. **Final score** (assuming no rules):
   - `final_score = base_score = 0.85`

## Important Notes

1. **Phonetic similarity is critical**: It has the highest weight (60% of each name part score)
2. **Last name matters more**: 70% weight vs 30% for first name
3. **Distribution matching**: Variations must match the target Light/Medium/Far distribution
4. **Rule compliance**: Only affects final score if rules are requested (20% weight)

## From Test Results

Looking at the test output:
- **Final score**: The overall name quality score (base_score adjusted for rule compliance)
- **Base score**: The combined first/last name score before rule compliance
- **First name phonetic**: Phonetic similarity score for first name (0.0-1.0)
- **Last name phonetic**: Phonetic similarity score for last name (0.0-1.0)

## Overall Miner Reward

The final score shown in tests is **only for names**. The complete miner reward includes:

- **Name quality**: 20% weight
- **DOB quality**: 10% weight  
- **Address quality**: 70% weight

```
final_reward = (0.2 × name_quality) + (0.1 × dob_quality) + (0.7 × address_quality)
```

So a perfect name score (1.0) would contribute 0.2 to the overall reward, assuming perfect DOB and address.

