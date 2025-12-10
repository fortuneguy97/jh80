#!/usr/bin/env python3
"""
Test script to verify MIID imports work correctly.
"""

try:
    print("Testing MIID imports...")
    
    # Test protocol import
    from MIID.protocol import IdentitySynapse
    print("✓ IdentitySynapse imported successfully")
    
    # Test base miner import
    from MIID.base.miner import BaseMinerNeuron
    print("✓ BaseMinerNeuron imported successfully")
    
    # Test bittensor import
    import bittensor as bt
    print("✓ Bittensor imported successfully")
    
    print("\n🎉 All imports successful! Your miner should work now.")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("\nTroubleshooting:")
    print("1. Make sure you're in the virtual environment:")
    print("   source miner_env/bin/activate")
    print("2. Install missing packages:")
    print("   pip install bittensor")
    
except Exception as e:
    print(f"❌ Unexpected error: {e}")