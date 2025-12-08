"""
Local Test Script for Miner
This script tests the miner's name variation generation without Bittensor/wallet
Perfect for local Windows testing
"""

import sys
import os
import time
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ollama
import requests

# Disable proxy settings for local Ollama connection
os.environ['NO_PROXY'] = '127.0.0.1,localhost'
os.environ['no_proxy'] = '127.0.0.1,localhost'
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

# Mock classes for testing without Bittensor network
class MockDendrite:
    def __init__(self):
        self.hotkey = "5DUB7kNLvvx8Dj7D8tn54N1C7Xok6GodNPQE2WECCaL9Wgpr"  # Yanez validator
        self.nonce = int(time.time())
        self.uuid = "test-uuid-12345"

class MockSynapse:
    def __init__(self, identity, query_template):
        self.identity = identity
        self.query_template = query_template
        self.variations = {}
        self.timeout = 120.0
        self.dendrite = MockDendrite()
        self.computed_body_hash = "test-hash"

class MockConfig:
    class Neuron:
        model_name = 'llama3.1:latest'
        ollama_url = 'http://127.0.0.1:11434'
    
    class Logging:
        logging_dir = './logs'
    
    neuron = Neuron()
    logging = Logging()

def test_miner():
    """Test the miner with sample data"""
    
    print("=" * 80)
    print("MINER LOCAL TEST - Windows")
    print("=" * 80)
    print()
    
    # Check if Ollama is running
    print("1. Checking Ollama...")
    
    # First, test basic connectivity with disabled proxy
    try:
        proxies = {'http': None, 'https': None}
        response = requests.get("http://127.0.0.1:11434", proxies=proxies, timeout=5)
        if response.status_code == 200:
            print(f"   ✓ Ollama server is responding")
        else:
            print(f"   ⚠ Ollama responded with status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"   ✗ Cannot connect to Ollama!")
        print(f"   Error: {e}")
        print()
        print("   Please start Ollama:")
        print("   1. Open a new terminal")
        print("   2. Run: ollama serve")
        print("   3. Then run this script again")
        return
    
    # Now try to list models
    try:
        client = ollama.Client(host='http://127.0.0.1:11434')
        models = client.list().get('models', [])
        print(f"   ✓ Ollama is running")
        print(f"   ✓ Available models: {[m.get('name') for m in models]}")
    except Exception as e:
        print(f"   ✗ Error listing models!")
        print(f"   Error: {e}")
        print()
        print("   Ollama is running but cannot list models.")
        print("   Try running: ollama list")
        return
    
    # Check if tinyllama is available (for testing)
    print()
    print("2. Checking tinyllama model...")
    model_name = 'tinyllama:latest'  # Change to 'llama3.1:latest' for better quality
    model_exists = any(model.get('name') == model_name for model in models)
    
    if not model_exists:
        print(f"   ✗ Model {model_name} not found!")
        print(f"   Pulling model... (this may take a few minutes)")
        try:
            client.pull(model_name)
            print(f"   ✓ Model {model_name} pulled successfully")
        except Exception as e:
            print(f"   ✗ Failed to pull model: {e}")
            return
    else:
        print(f"   ✓ Model {model_name} is available")
    
    print()
    print("3. Creating test data...")
    
    # Sample test data (similar to what validators send)
    test_identities = [
        ["John Smith", "1990-01-15", "123 Main Street, New York, NY 10001"],
        ["Maria Garcia", "1985-06-20", "456 Oak Avenue, Los Angeles, CA 90001"],
        ["Mohammed Ali", "1992-03-10", "789 Pine Road, Chicago, IL 60601"],
    ]
    
    # Query template (similar to what validators use)
    query_template = """Generate 30 alternative spellings and variations for the name: {name}

IMPORTANT RULES:
- Generate ONLY name variations (no addresses, no dates, no numbers)
- Each variation should sound similar to the original name
- Each variation should look similar to the original name
- Keep the same number of words (if 2 words, return 2 words)
- Return variations as a comma-separated list
- Generate exactly 30 unique variations

Example transformations:
- ph ↔ f (Philip → Filip)
- c ↔ k (Carl → Karl)
- i ↔ y (Smith → Smyth)
- Double letters (Phillip → Philip)
- Silent letters (John → Jon)

Name to vary: {name}
"""
    
    print(f"   ✓ Testing with {len(test_identities)} identities:")
    for identity in test_identities:
        print(f"      - {identity[0]}")
    
    print()
    print("4. Testing miner (this will take a few seconds per name)...")
    print()
    
    # Create a simple test miner (standalone, no bittensor import needed)
    class TestMiner:
        def __init__(self):
            self.model_name = 'tinyllama:latest'  # Change to 'llama3.1:latest' for better quality
            
        def Get_Respond_LLM(self, prompt):
            """Query LLM with optimized parameters"""
            try:
                # Disable proxy for local connection
                os.environ['NO_PROXY'] = '127.0.0.1,localhost'
                os.environ['no_proxy'] = '127.0.0.1,localhost'
                
                client = ollama.Client(host='http://127.0.0.1:11434')
                response = client.chat(
                    self.model_name,
                    messages=[{
                        'role': 'system',
                        'content': (
                            "You are an expert linguist specializing in name variation generation.\n\n"
                            "CRITICAL RULES:\n"
                            "❌ NEVER include numbers (0-9)\n"
                            "❌ NEVER include address words (Street, Ave, Road, Dr, Lane, etc.)\n"
                            "❌ NEVER include date/month names (January, Feb, etc.)\n"
                            "✓ ONLY use letters, spaces, hyphens, and apostrophes\n\n"
                            "Generate 30 unique, high-quality variations. Return ONLY comma-separated names."
                        )
                    }, {
                        'role': 'user',
                        'content': prompt,
                    }],
                    options={
                        "num_predict": 1024,
                        "temperature": 0.5,
                        "top_p": 0.85,
                        "top_k": 40,
                        "repeat_penalty": 1.3,
                        "frequency_penalty": 0.8,
                        "presence_penalty": 0.7,
                        "mirostat": 2,
                        "mirostat_tau": 5.0,
                        "mirostat_eta": 0.1,
                    }
                )
                return response['message']['content']
            except Exception as e:
                print(f"   ✗ LLM query failed: {e}")
                raise
    
    # Initialize miner
    print("   Initializing test miner...")
    try:
        miner = TestMiner()
        print("   ✓ Test miner initialized (standalone, no Bittensor needed)")
        
    except Exception as e:
        print(f"   ✗ Failed to initialize test miner: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print()
    print("5. Generating complete variations (name + DOB + address)...")
    print()
    
    # Import the variation generator
    from variation_generator import VariationGenerator
    
    # Use tinyllama for testing (faster, less VRAM)
    # Change to 'llama3.1:latest' or 'llama3.3:latest' for better quality
    generator = VariationGenerator(model_name='tinyllama:latest')
    
    results = {}
    start_time = time.time()
    
    for i, identity in enumerate(test_identities, 1):
        name = identity[0]
        dob = identity[1]
        address = identity[2]
        
        print(f"   [{i}/{len(test_identities)}] Processing: {name}")
        print(f"       DOB: {dob}")
        print(f"       Address: {address[:50]}...")
        
        try:
            # Generate complete variations (name, DOB, address)
            variations = generator.generate_complete_variations(name, dob, address, count=15)
            
            results[name] = variations
            
            print(f"       ✓ Generated {len(variations)} complete variations")
            print(f"       Sample variation:")
            if variations:
                sample = variations[0]
                print(f"         Name: {sample[0]}")
                print(f"         DOB:  {sample[1]}")
                print(f"         Addr: {sample[2][:50]}...")
            
        except Exception as e:
            print(f"       ✗ Error: {e}")
            import traceback
            traceback.print_exc()
            results[name] = []
        
        print()
    
    total_time = time.time() - start_time
    
    print("=" * 80)
    print("TEST RESULTS")
    print("=" * 80)
    print()
    print(f"Total processing time: {total_time:.2f} seconds")
    print(f"Average time per identity: {total_time/len(test_identities):.2f} seconds")
    print()
    
    for name, variations in results.items():
        print(f"Name: {name}")
        print(f"  Variations generated: {len(variations)}")
        if len(variations) > 0:
            print(f"  First 5 complete variations:")
            for i, var in enumerate(variations[:5], 1):
                print(f"    {i}. Name: {var[0]}")
                print(f"       DOB:  {var[1]}")
                print(f"       Addr: {var[2][:60]}...")
                print()
        print()
    
    # Save results to JSON (in miner1 format)
    output_file = 'test_results.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Results saved to: {output_file}")
    print()
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    print()
    print("Format matches miner1 output:")
    print('  {"Name": [[name_var, dob_var, addr_var], ...]}')
    print()
    print("Next steps:")
    print("1. Review the variations in test_results.json")
    print("2. Check if variations are high quality")
    print("3. Integrate into miner.py for network deployment")
    print("4. If quality is low, try upgrading to llama3.3:latest")
    print()

if __name__ == "__main__":
    try:
        test_miner()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
