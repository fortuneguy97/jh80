# Generator Routing Logic

## Overview

The miner now uses intelligent routing to select the best variation generator based on availability:

```
┌─────────────────────────────────────────┐
│     Validator Request Arrives           │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│   Check: Is Ollama Available?           │
└──────────────┬──────────────────────────┘
               │
       ┌───────┴───────┐
       │               │
      YES             NO
       │               │
       ▼               ▼
┌──────────────┐  ┌──────────────────────┐
│   Ollama     │  │ variation_generator  │
│  Generator   │  │    _clean.py         │
│  (Primary)   │  │   (Fallback)         │
└──────────────┘  └──────────────────────┘
       │               │
       └───────┬───────┘
               │
               ▼
┌─────────────────────────────────────────┐
│   Return Variations to Validator        │
└─────────────────────────────────────────┘
```

## Generator Comparison

### 1. Ollama Generator (Primary - `ollama_generator.py`)

**When Used:**
- Ollama is installed and running
- Model is available (default: llama3.1)

**Advantages:**
- ✅ Optimized prompts for maximum validator scoring
- ✅ Explicit phonetic/orthographic similarity targeting
- ✅ Rule-based variation generation with exact percentages
- ✅ Real address generation with geocoding validation
- ✅ Perfect DOB category coverage
- ✅ Comprehensive query template parsing

**Features:**
- Parses validator requirements from query template
- Generates variations matching exact similarity distributions
- Applies rules with precise percentages
- Creates real, geocodable addresses
- Ensures all DOB categories are covered

### 2. Variation Generator Clean (Fallback - `variation_generator_clean.py`)

**When Used:**
- Ollama is not available or not running
- Ollama check fails

**Advantages:**
- ✅ No external dependencies (works offline)
- ✅ Rule-based transformations
- ✅ Basic LLM integration (if available)
- ✅ Real city names via geonamescache

**Features:**
- Basic query template parsing
- Rule application (20+ transformation rules)
- DOB variations (±1, ±3, ±30, ±90, ±365 days)
- Address variations with real city names

## Configuration

### Setting Ollama Model

You can specify which Ollama model to use:

```bash
python neurons/miner.py \
  --netuid 54 \
  --wallet.name your_wallet \
  --wallet.hotkey your_hotkey \
  --subtensor.network finney \
  --neuron.model_name llama3.1:latest
```

**Recommended Models:**
- `llama3.1:latest` (8B) - Best balance of quality and speed (DEFAULT)
- `llama3.3:latest` (70B) - Highest quality (requires 40GB+ VRAM)
- `qwen2.5:32b` - Excellent alternative (requires 20GB+ VRAM)

### Checking Ollama Status

Before running the miner, verify Ollama is working:

```bash
# Check if Ollama is running
ollama list

# Pull the model if needed
ollama pull llama3.1:latest

# Test the model
ollama run llama3.1:latest "Hello"
```

## Routing Logic in Code

```python
# Check if Ollama is available
try:
    import ollama
    ollama.list()  # Test if Ollama is running
    ollama_available = True
except Exception:
    ollama_available = False

# Route to appropriate generator
if ollama_available:
    # Use optimized Ollama generator
    from ollama_generator import generate_variations_with_ollama
    variations = generate_variations_with_ollama(synapse, ollama_model=self.model_name)
else:
    # Fallback to clean generator
    from variation_generator_clean import generate_variations as generate_variations_clean
    variations = generate_variations_clean(synapse)
```

## Monitoring

Watch your logs to see which generator is being used:

```bash
# Ollama generator (primary)
🚀 Routing request to Ollama generator for maximum scoring

# Clean generator (fallback)
📋 Routing request to variation_generator_clean.py (fallback)
```

## Troubleshooting

### Ollama Not Available

If you see:
```
⚠️  Ollama not available: [Errno 111] Connection refused
📋 Routing request to variation_generator_clean.py (fallback)
```

**Solution:**
1. Check if Ollama is running: `ollama list`
2. Start Ollama: `ollama serve`
3. Pull the model: `ollama pull llama3.1:latest`
4. Restart your miner

### Import Errors

If you see:
```
✗ Failed to import generator: No module named 'ollama_generator'
```

**Solution:**
1. Verify `ollama_generator.py` exists in `neurons/` directory
2. Check file permissions
3. Restart your miner

## Performance Tips

1. **Use Ollama Generator for Maximum Scores**
   - Ollama generator has optimized prompts for validator scoring
   - Targets exact phonetic/orthographic distributions
   - Generates real, geocodable addresses

2. **Ensure Ollama is Always Running**
   - Set up Ollama as a system service
   - Monitor Ollama health
   - Use process managers (systemd, pm2)

3. **Choose the Right Model**
   - llama3.1 (8B): Best for most miners (fast + quality)
   - llama3.3 (70B): Best quality but requires powerful GPU
   - qwen2.5 (32B): Good alternative with excellent quality

4. **Monitor Your Scores**
   - Check validator feedback
   - Adjust model if scores are low
   - Ensure Ollama is being used (check logs)

## Future Enhancements

Potential additions to the routing logic:

- **Gemini API Integration**: Add Google Gemini as another option
- **Multi-Model Ensemble**: Combine outputs from multiple models
- **Dynamic Model Selection**: Choose model based on query complexity
- **Caching**: Cache variations for common names
- **A/B Testing**: Compare scores between generators
