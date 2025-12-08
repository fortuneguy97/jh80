# Complete Variation Generator

Generates variations for **name, DOB, and address** - matching miner1's output format.

## Files

- `variation_generator.py` - Complete variation generator class
- `start.py` - Test script using the generator
- `test_results.json` - Output file (created after running)

## Output Format

Matches miner1's format:
```json
{
  "John Doe": [
    ["Jon Doe", "1990-05-16", "375 Washington Ave, New York, USA"],
    ["John Smyth", "1990-05-14", "194 Park Rd, New York, USA"],
    ["Jon Smith", "1990-05-18", "26 Washington Ave, New York, USA"]
  ]
}
```

## How It Works

### 1. Name Variations (using LLM)
- Uses llama3.1 to generate phonetic/orthographic variations
- Applies same rules as miner.py
- Filters out invalid variations

### 2. DOB Variations (rule-based)
- ±1-2 days (10 variations)
- ±1 month (10 variations)
- ±1 year (5 variations)
- Partial dates: YYYY-MM or YYYY (5 variations)

### 3. Address Variations (rule-based)
- Different street numbers (±1-500)
- Different street names (Main, Oak, Elm, etc.)
- Different street types (St, Ave, Rd, etc.)
- Keeps city/country consistent

## Usage

### Test Locally
```bash
cd my/neurons
python start.py
```

### Use in Your Code
```python
from variation_generator import VariationGenerator

generator = VariationGenerator(model_name='llama3.1:latest')

# Generate 30 complete variations
variations = generator.generate_complete_variations(
    name="John Doe",
    dob="1990-05-15",
    address="123 Main Street, New York, USA",
    count=30
)

# Result: List of [name_var, dob_var, addr_var]
for var in variations:
    print(f"Name: {var[0]}, DOB: {var[1]}, Address: {var[2]}")
```

### Integrate into miner.py
```python
# In miner.py forward() method:
from variation_generator import VariationGenerator

generator = VariationGenerator(model_name=self.model_name)

variations = {}
for identity in synapse.identity:
    name, dob, address = identity[0], identity[1], identity[2]
    
    # Generate complete variations
    complete_vars = generator.generate_complete_variations(
        name, dob, address, count=30
    )
    
    variations[name] = complete_vars

synapse.variations = variations
```

## Customization

### Change Variation Counts
```python
# More DOB variations
dob_vars = generator.generate_dob_variations(dob, count=50)

# More address variations
addr_vars = generator.generate_address_variations(address, count=50)
```

### Change DOB Variation Strategy
Edit `generate_dob_variations()` in `variation_generator.py`:
```python
# Example: Only ±1 day variations
for i in range(count):
    delta_days = random.choice([-1, 1])
    new_date = date_obj + timedelta(days=delta_days)
    variations.append(new_date.strftime('%Y-%m-%d'))
```

### Change Address Variation Strategy
Edit `generate_address_variations()` in `variation_generator.py`:
```python
# Example: Only vary street number
for i in range(count):
    delta = random.randint(-100, 100)
    new_number = max(1, street_number + delta)
    new_street = f"{new_number} {street_name}"
```

## Expected Output

### Test Run
```
================================================================================
MINER LOCAL TEST - Windows
================================================================================

1. Checking Ollama...
   ✓ Ollama server is responding
   ✓ Ollama is running
   ✓ Available models: ['llama3.1:latest']

2. Checking llama3.1 model...
   ✓ Model llama3.1:latest is available

3. Creating test data...
   ✓ Testing with 3 identities:
      - John Smith
      - Maria Garcia
      - Mohammed Ali

4. Testing miner (this will take a few seconds per name)...
   Initializing test miner...
   ✓ Test miner initialized (standalone, no Bittensor needed)

5. Generating complete variations (name + DOB + address)...

   [1/3] Processing: John Smith
       DOB: 1990-01-15
       Address: 123 Main Street, New York, NY 10001...
Generating 15 variations for: John Smith
  - Generating name variations...
  - Generating DOB variations...
  - Generating address variations...
  ✓ Generated 15 complete variations
       ✓ Generated 15 complete variations
       Sample variation:
         Name: Jon Smith
         DOB:  1990-01-16
         Addr: 456 Main Street, New York, NY 10001...

================================================================================
TEST RESULTS
================================================================================

Total processing time: 25.34 seconds
Average time per identity: 8.45 seconds

Name: John Smith
  Variations generated: 15
  First 5 complete variations:
    1. Name: Jon Smith
       DOB:  1990-01-16
       Addr: 456 Main Street, New York, NY 10001...

    2. Name: John Smyth
       DOB:  1990-01-14
       Addr: 789 Oak Avenue, New York, NY 10001...

✓ Results saved to: test_results.json

================================================================================
TEST COMPLETE
================================================================================
```

## Troubleshooting

### "No name variations generated"
- Check Ollama is running: `ollama serve`
- Check model is available: `ollama list`
- Try simpler names first

### "DOB parsing failed"
- Check DOB format (YYYY-MM-DD recommended)
- Add more format parsers in `generate_dob_variations()`

### "Address variations all the same"
- Check address has a street number
- Verify address format: "123 Street Name, City, Country"

## Performance

- **Name variations**: 3-5 seconds (LLM call)
- **DOB variations**: <0.1 seconds (rule-based)
- **Address variations**: <0.1 seconds (rule-based)
- **Total per identity**: ~3-5 seconds

## Next Steps

1. ✅ Test locally with `python start.py`
2. ✅ Review `test_results.json` output
3. ✅ Integrate into `miner.py`
4. ✅ Deploy to network

Good luck! 🚀
