"""
Complete Variation Generator - Name, DOB, and Address
Generates variations for all three identity components using Ollama
"""

import os
import random
import re
from datetime import datetime, timedelta
from typing import List, Tuple, Dict

# Disable proxy for local Ollama
os.environ['NO_PROXY'] = '127.0.0.1,localhost'
os.environ['no_proxy'] = '127.0.0.1,localhost'
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''

import ollama


class VariationGenerator:
    def __init__(self, model_name='tinyllama:latest'):
        """
        Initialize the variation generator
        
        Args:
            model_name: Ollama model to use
                - 'tinyllama:latest' - Fast, low VRAM (2GB), good for testing
                - 'llama3.1:latest' - Better quality (10GB VRAM)
                - 'llama3.3:latest' - Best quality (40GB VRAM)
        """
        self.model_name = model_name
        self.client = ollama.Client(host='http://127.0.0.1:11434')
    
    def generate_name_variations(self, name: str, count: int = 30) -> List[str]:
        """Generate name variations using LLM"""
        prompt = f"""Generate {count} alternative spellings for the name: {name}

RULES:
- ONLY letters, spaces, hyphens, apostrophes
- NO numbers, NO addresses, NO dates
- Sound similar (phonetic)
- Look similar (orthographic)
- Same number of words

Return ONLY comma-separated names, nothing else."""

        try:
            response = self.client.chat(
                self.model_name,
                messages=[{
                    'role': 'system',
                    'content': 'You are an expert at generating name variations. Return ONLY comma-separated names.'
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
                }
            )
            
            # Parse response
            text = response['message']['content']
            variations = []
            
            for line in text.split('\n'):
                line = line.strip()
                if ',' in line:
                    parts = [p.strip() for p in line.split(',')]
                    for part in parts:
                        # Clean
                        cleaned = ''.join(c for c in part if not c.isdigit())
                        cleaned = cleaned.strip('.,;:!?()[]{}"\'-')
                        cleaned = cleaned.strip()
                        if cleaned and len(cleaned) > 1:
                            variations.append(cleaned)
            
            # Remove duplicates
            seen = set()
            unique = []
            for var in variations:
                var_lower = var.lower()
                if var_lower not in seen and var_lower != name.lower():
                    seen.add(var_lower)
                    unique.append(var)
            
            return unique[:count]
            
        except Exception as e:
            print(f"Error generating name variations: {e}")
            return []
    
    def generate_dob_variations(self, dob: str, count: int = 30) -> List[str]:
        """Generate DOB variations (±1-2 days, month, year)"""
        variations = []
        
        try:
            # Parse the original DOB
            # Try different formats
            date_obj = None
            for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%d/%m/%Y', '%m-%d-%Y', '%m/%d/%Y']:
                try:
                    date_obj = datetime.strptime(dob, fmt)
                    break
                except:
                    continue
            
            if not date_obj:
                # If can't parse, return original
                return [dob] * count
            
            # Generate variations
            for i in range(count):
                if i < 10:
                    # ±1-2 days
                    delta_days = random.choice([-2, -1, 1, 2])
                    new_date = date_obj + timedelta(days=delta_days)
                elif i < 20:
                    # ±1 month
                    delta_days = random.choice([-30, -28, 28, 30])
                    new_date = date_obj + timedelta(days=delta_days)
                elif i < 25:
                    # ±1 year
                    delta_days = random.choice([-365, 365])
                    new_date = date_obj + timedelta(days=delta_days)
                else:
                    # Missing day or month (partial dates)
                    if random.random() < 0.5:
                        # Year-month only
                        variations.append(new_date.strftime('%Y-%m'))
                        continue
                    else:
                        # Year only
                        variations.append(new_date.strftime('%Y'))
                        continue
                
                # Format as YYYY-MM-DD
                variations.append(new_date.strftime('%Y-%m-%d'))
            
            return variations[:count]
            
        except Exception as e:
            print(f"Error generating DOB variations: {e}")
            return [dob] * count
    
    def generate_address_variations(self, address: str, count: int = 30) -> List[str]:
        """Generate address variations (different street numbers, nearby streets)"""
        variations = []
        
        try:
            # Parse address components
            # Format: "123 Main Street, New York, NY 10001"
            parts = [p.strip() for p in address.split(',')]
            
            if len(parts) < 2:
                # Simple address, just vary the number
                return self._simple_address_variations(address, count)
            
            street_part = parts[0]  # "123 Main Street"
            city_part = parts[1] if len(parts) > 1 else ""
            rest = ", ".join(parts[2:]) if len(parts) > 2 else ""
            
            # Extract street number and name
            match = re.match(r'(\d+)\s+(.+)', street_part)
            if match:
                street_number = int(match.group(1))
                street_name = match.group(2)
                
                # Common street names for variations
                street_types = ['St', 'Street', 'Ave', 'Avenue', 'Rd', 'Road', 'Dr', 'Drive', 
                               'Ln', 'Lane', 'Blvd', 'Boulevard', 'Way', 'Ct', 'Court']
                street_names = ['Main', 'First', 'Second', 'Oak', 'Elm', 'Park', 'Washington', 
                               'Broadway', 'Maple', 'Cedar', 'Pine']
                
                for i in range(count):
                    if i < 15:
                        # Vary street number (±1-500)
                        delta = random.randint(-500, 500)
                        new_number = max(1, street_number + delta)
                        new_street = f"{new_number} {street_name}"
                    elif i < 25:
                        # Vary street name but keep number
                        new_street_name = random.choice(street_names)
                        new_street_type = random.choice(street_types)
                        new_street = f"{street_number} {new_street_name} {new_street_type}"
                    else:
                        # Vary both
                        delta = random.randint(-200, 200)
                        new_number = max(1, street_number + delta)
                        new_street_name = random.choice(street_names)
                        new_street_type = random.choice(street_types)
                        new_street = f"{new_number} {new_street_name} {new_street_type}"
                    
                    # Reconstruct address
                    if rest:
                        new_address = f"{new_street}, {city_part}, {rest}"
                    else:
                        new_address = f"{new_street}, {city_part}"
                    
                    variations.append(new_address)
            else:
                # No street number found, just return original
                variations = [address] * count
            
            return variations[:count]
            
        except Exception as e:
            print(f"Error generating address variations: {e}")
            return [address] * count
    
    def _simple_address_variations(self, address: str, count: int) -> List[str]:
        """Simple address variations when parsing fails"""
        variations = []
        
        # Try to find a number in the address
        numbers = re.findall(r'\d+', address)
        if numbers:
            base_number = int(numbers[0])
            for i in range(count):
                delta = random.randint(-100, 100)
                new_number = max(1, base_number + delta)
                new_address = re.sub(r'\d+', str(new_number), address, count=1)
                variations.append(new_address)
        else:
            # No numbers, just return original
            variations = [address] * count
        
        return variations
    
    def generate_complete_variations(self, name: str, dob: str, address: str, count: int = 30) -> List[List[str]]:
        """Generate complete identity variations [name, dob, address]"""
        print(f"Generating {count} variations for: {name}")
        
        # Generate variations for each component
        print("  - Generating name variations...")
        name_vars = self.generate_name_variations(name, count)
        
        print("  - Generating DOB variations...")
        dob_vars = self.generate_dob_variations(dob, count)
        
        print("  - Generating address variations...")
        address_vars = self.generate_address_variations(address, count)
        
        # Combine into complete variations
        variations = []
        for i in range(min(count, len(name_vars))):
            variation = [
                name_vars[i] if i < len(name_vars) else name,
                dob_vars[i] if i < len(dob_vars) else dob,
                address_vars[i] if i < len(address_vars) else address
            ]
            variations.append(variation)
        
        print(f"  ✓ Generated {len(variations)} complete variations")
        return variations


def test_generator():
    """Test the variation generator"""
    print("=" * 80)
    print("Testing Variation Generator")
    print("=" * 80)
    print()
    
    # Test data
    test_cases = [
        ("John Doe", "1990-05-15", "123 Main Street, New York, USA"),
        ("محمد شفیع پور", "1987-12-01", "456 Park Road, Tehran, Iran"),
    ]
    
    # Use tinyllama for testing (change to llama3.1 or llama3.3 for better quality)
    generator = VariationGenerator(model_name='tinyllama:latest')
    
    results = {}
    
    for name, dob, address in test_cases:
        print(f"Processing: {name}")
        print(f"  DOB: {dob}")
        print(f"  Address: {address}")
        print()
        
        variations = generator.generate_complete_variations(name, dob, address, count=15)
        results[name] = variations
        
        print(f"  Sample variations:")
        for i, var in enumerate(variations[:5], 1):
            print(f"    {i}. {var}")
        print()
    
    # Save to JSON
    import json
    with open('complete_variations.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print("=" * 80)
    print("✓ Results saved to: complete_variations.json")
    print("=" * 80)


if __name__ == "__main__":
    test_generator()
