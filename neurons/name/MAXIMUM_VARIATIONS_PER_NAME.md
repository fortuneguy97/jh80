# Maximum Variations Per Name

## Answer: **15 variations per name** (maximum)

## Details

### Variation Count Range

The validator requests a **random number of variations between 6 and 15** for each name.

**Code Location:** `MIID/validator/query_generator.py`

```python
# Line 74
DEFAULT_VARIATION_COUNT = 15

# Line 1382
variation_count = random.randint(6, DEFAULT_VARIATION_COUNT)
```

### Range Breakdown

| Minimum | Maximum | Default (Fallback) |
|---------|---------|-------------------|
| **6** | **15** | **15** |

### When Maximum (15) is Used

1. **Random Selection:** The validator randomly selects between 6-15, so 15 is possible
2. **Fallback Mode:** When using default query template (Line 1771):
   ```python
   variation_count = DEFAULT_VARIATION_COUNT  # 15
   ```

### Example Query Template

When the validator asks for variations, it might say:

```
Generate 15 variations of the name {name}, ensuring phonetic similarity...
```

Or:

```
Generate 9 variations of the name {name}, ensuring phonetic similarity...
```

The exact number is randomly selected between 6 and 15.

## What This Means for Your Generator

1. **You must handle 6-15 variations per name**
2. **Maximum is 15** - never more than 15
3. **Minimum is 6** - but you should generate the exact number requested
4. **Each name gets its own variation_count** - different names in the same synapse might have different counts

## Example Synapse

```python
IdentitySynapse(
    identity=[
        ["John Smith", "1990-01-15", "United States"],      # Might ask for 12 variations
        ["Jane Doe", "1985-03-20", "France"],              # Might ask for 8 variations
        ["Bob Johnson", "1992-07-10", "United Kingdom"]    # Might ask for 15 variations (max)
    ],
    query_template="Generate {variation_count} variations...",  # Number varies per name
    variations={}
)
```

## Code References

- **Constant:** `query_generator.py` Line 74: `DEFAULT_VARIATION_COUNT = 15`
- **Random Selection:** `query_generator.py` Line 1382: `random.randint(6, DEFAULT_VARIATION_COUNT)`
- **Fallback:** `query_generator.py` Line 1771: `variation_count = DEFAULT_VARIATION_COUNT`

## Summary

✅ **Maximum variations per name: 15**  
✅ **Range: 6-15 variations**  
✅ **Randomly selected per name**  
✅ **Your generator must handle up to 15 variations per name**

