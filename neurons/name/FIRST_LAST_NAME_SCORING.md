# First Name and Last Name Cumulative Scoring

## Overview

The validator calculates similarity scores **separately** for first name and last name, then combines them using weighted averaging.

## How It Works

### Step 1: Split the Name

The validator splits the full name into parts:
```python
name_parts = original_name.split()
first_name = name_parts[0]      # First word
last_name = name_parts[-1]     # Last word
```

**Example:**
- "John Smith" → first_name = "John", last_name = "Smith"
- "Mary Jane Watson" → first_name = "Mary", last_name = "Watson"

### Step 2: Extract Variations for Each Part

For each variation, the validator extracts the first and last name parts:

```python
for variation in non_rule_compliant_variations:
    parts = variation.split()
    if len(parts) >= 2:
        first_name_variations.append(parts[0])      # First word of variation
        last_name_variations.append(parts[-1])      # Last word of variation
```

**Example:**
- Variation: "Jon Smyth" → first_name_variation = "Jon", last_name_variation = "Smyth"
- Variation: "John Smit" → first_name_variation = "John", last_name_variation = "Smit"

### Step 3: Calculate Scores Separately

Each part is scored independently using `calculate_part_score()`:

```python
# Calculate first name score
first_name_score, first_metrics = calculate_part_score(
    first_name,                    # "John"
    first_name_variations,        # ["Jon", "Jhon", "Jhn", ...]
    phonetic_similarity,
    orthographic_similarity,
    expected_count
)

# Calculate last name score
last_name_score, last_metrics = calculate_part_score(
    last_name,                     # "Smith"
    last_name_variations,         # ["Smyth", "Smit", "Smth", ...]
    phonetic_similarity,
    orthographic_similarity,
    expected_count
)
```

Each `calculate_part_score()` returns a score (0.0-1.0) based on:
- Phonetic similarity distribution
- Orthographic similarity distribution
- Count score
- Uniqueness score
- Length score

### Step 4: Combine Scores with Weights

The scores are combined using **weighted averaging**:

```python
# Weights from MIID_REWARD_WEIGHTS
first_name_weight = 0.3   # 30%
last_name_weight = 0.7    # 70%

# Combined base score
base_score = (
    first_name_weight * first_name_score +
    last_name_weight * last_name_score
)
```

**Formula:**
```
base_score = 0.3 × first_name_score + 0.7 × last_name_score
```

## Examples

### Example 1: Perfect Scores

**Name:** "John Smith"

**First Name Variations:** ["Jon", "Jhon", "Jahn"] (all score 1.0)
- first_name_score = 1.0

**Last Name Variations:** ["Smyth", "Smithe", "Smth"] (all score 1.0)
- last_name_score = 1.0

**Combined Score:**
```
base_score = 0.3 × 1.0 + 0.7 × 1.0 = 0.3 + 0.7 = 1.0
```

### Example 2: Different Scores

**Name:** "John Smith"

**First Name Variations:** ["Jon", "Jhon", "Jhn"] (score 0.8)
- first_name_score = 0.8

**Last Name Variations:** ["Smyth", "Smit", "Sm"] (score 0.6)
- last_name_score = 0.6

**Combined Score:**
```
base_score = 0.3 × 0.8 + 0.7 × 0.6 = 0.24 + 0.42 = 0.66
```

### Example 3: One Part Perfect, One Part Low

**Name:** "John Smith"

**First Name Variations:** ["Jon", "Jhon", "Jahn"] (score 1.0)
- first_name_score = 1.0

**Last Name Variations:** ["Smyth", "Smit", "Sm"] (score 0.4)
- last_name_score = 0.4

**Combined Score:**
```
base_score = 0.3 × 1.0 + 0.7 × 0.4 = 0.3 + 0.28 = 0.58
```

**Key Insight:** Even with perfect first name, low last name score significantly reduces the combined score!

### Example 4: One Part Low, One Part Perfect

**Name:** "John Smith"

**First Name Variations:** ["Jon", "Jhn", "J"] (score 0.4)
- first_name_score = 0.4

**Last Name Variations:** ["Smyth", "Smithe", "Smth"] (score 1.0)
- last_name_score = 1.0

**Combined Score:**
```
base_score = 0.3 × 0.4 + 0.7 × 1.0 = 0.12 + 0.70 = 0.82
```

**Key Insight:** Last name has more weight (70%), so perfect last name can compensate for lower first name!

## Key Insights

### 1. **Last Name Has More Weight (70%)**
- Last name score is **more important** than first name score
- Focus on generating high-quality last name variations
- A perfect last name (1.0) can significantly boost the combined score

### 2. **Both Parts Must Be Good**
- Even with perfect first name (1.0), if last name is low (0.4):
  - Combined: 0.3 × 1.0 + 0.7 × 0.4 = 0.58
- Both parts need to score well for maximum combined score

### 3. **Separate Scoring**
- First name and last name are scored **independently**
- Each part has its own:
  - Phonetic similarity distribution
  - Orthographic similarity distribution
  - Count, uniqueness, length scores
- The validator checks if each part matches the target distribution separately

### 4. **Distribution Matching**
- The validator checks if **first name variations** match the target distribution (20% Light, 60% Medium, 20% Far)
- The validator checks if **last name variations** match the target distribution (20% Light, 60% Medium, 20% Far)
- **Both must match** for maximum score!

## Impact on Generation Strategy

### For Light Variations (1.0 score):
- **Both** first name AND last name must match all algorithms
- Example: "Jon Smyth" where:
  - "Jon" matches all algorithms for "John" → 1.0
  - "Smyth" matches all algorithms for "Smith" → 1.0
  - Combined: 0.3 × 1.0 + 0.7 × 1.0 = 1.0

### For Medium Variations (0.6-0.8 score):
- **Both** first name AND last name should have 2 algorithms matching
- Example: "Jhon Smit" where:
  - "Jhon" matches 2 algorithms for "John" → 0.7
  - "Smit" matches 2 algorithms for "Smith" → 0.7
  - Combined: 0.3 × 0.7 + 0.7 × 0.7 = 0.7

### For Far Variations (0.3-0.6 score):
- **Both** first name AND last name should have 0-1 algorithms matching
- Example: "Jhn Sm" where:
  - "Jhn" matches 1 algorithm for "John" → 0.4
  - "Sm" matches 1 algorithm for "Smith" → 0.4
  - Combined: 0.3 × 0.4 + 0.7 × 0.4 = 0.4

## Code Reference

From `MIID/validator/reward.py`:

```python
# Weights
MIID_REWARD_WEIGHTS = {
    "first_name_weight": 0.3,   # 30%
    "last_name_weight": 0.7     # 70%
}

# Combining scores
if last_name:
    base_score = (
        part_weights.get("first_name_weight", MIID_REWARD_WEIGHTS["first_name_weight"]) * first_name_score +
        part_weights.get("last_name_weight", MIID_REWARD_WEIGHTS["last_name_weight"]) * last_name_score
    )
else:
    base_score = first_name_score
```

## Summary

1. **Split:** Name is split into first and last name
2. **Score Separately:** Each part is scored independently
3. **Combine:** Scores are combined using 30% first name + 70% last name
4. **Distribution:** Both parts must match the target similarity distribution
5. **Strategy:** Focus on last name quality (70% weight), but both parts matter!

