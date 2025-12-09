#!/usr/bin/env python3
"""
Test script to verify generator routing logic works correctly.

Usage:
    python neurons/test_routing.py
"""

import sys
import os

# Add neurons directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_ollama_availability():
    """Test if Ollama is available"""
    print("=" * 80)
    print("Testing Ollama Availability")
    print("=" * 80)
    
    try:
        import ollama
        print("✓ Ollama package is installed")
        
        try:
            models = ollama.list()
            print(f"✓ Ollama is running")
            print(f"✓ Available models: {len(models.get('models', []))}")
            
            for model in models.get('models', []):
                print(f"  - {model.get('name', 'unknown')}")
            
            return True
        except Exception as e:
            print(f"✗ Ollama is not running: {e}")
            print("  Start Ollama with: ollama serve")
            return False
            
    except ImportError:
        print("✗ Ollama package not installed")
        print("  Install with: pip install ollama")
        return False

def test_generator_imports():
    """Test if generator modules can be imported"""
    print("\n" + "=" * 80)
    print("Testing Generator Imports")
    print("=" * 80)
    
    # Test ollama_generator
    try:
        from ollama_generator import generate_variations_with_ollama
        print("✓ ollama_generator.py can be imported")
        print(f"  Function: generate_variations_with_ollama")
    except ImportError as e:
        print(f"✗ Failed to import ollama_generator: {e}")
    
    # Test variation_generator_clean
    try:
        from variation_generator_clean import generate_variations
        print("✓ variation_generator_clean.py can be imported")
        print(f"  Function: generate_variations")
    except ImportError as e:
        print(f"✗ Failed to import variation_generator_clean: {e}")
    
    # Test variation_generator (fallback)
    try:
        from variation_generator import VariationGenerator
        print("✓ variation_generator.py can be imported")
        print(f"  Class: VariationGenerator")
    except ImportError as e:
        print(f"✗ Failed to import variation_generator: {e}")

def test_routing_logic():
    """Test the routing logic"""
    print("\n" + "=" * 80)
    print("Testing Routing Logic")
    print("=" * 80)
    
    # Check Ollama availability
    try:
        import ollama
        ollama.list()
        ollama_available = True
        print("✓ Ollama check passed - would route to ollama_generator")
    except Exception as e:
        ollama_available = False
        print(f"✗ Ollama check failed - would route to variation_generator_clean")
        print(f"  Reason: {e}")
    
    # Show which generator would be used
    if ollama_available:
        print("\n🚀 PRIMARY GENERATOR: ollama_generator.py")
        print("   This provides maximum scoring with optimized prompts")
    else:
        print("\n📋 FALLBACK GENERATOR: variation_generator_clean.py")
        print("   This provides basic functionality without Ollama")

def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("MINER GENERATOR ROUTING TEST")
    print("=" * 80)
    
    # Test 1: Ollama availability
    ollama_ok = test_ollama_availability()
    
    # Test 2: Generator imports
    test_generator_imports()
    
    # Test 3: Routing logic
    test_routing_logic()
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if ollama_ok:
        print("✅ Your miner will use the OPTIMIZED Ollama generator")
        print("   This gives you the best chance at maximum TAO earnings!")
    else:
        print("⚠️  Your miner will use the FALLBACK generator")
        print("   Consider installing/starting Ollama for better scores:")
        print("   1. Install: curl -fsSL https://ollama.com/install.sh | sh")
        print("   2. Start: ollama serve")
        print("   3. Pull model: ollama pull llama3.1:latest")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
