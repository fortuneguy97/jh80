#!/usr/bin/env python3
"""
Test script to verify config imports work correctly.
"""

try:
    print("Testing config imports...")
    
    # Test bittensor import
    import bittensor as bt
    print("✓ Bittensor imported successfully")
    
    # Test config import
    from MIID.utils.config import config
    print("✓ Config imported successfully")
    
    print("\n🎉 All config imports successful!")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()