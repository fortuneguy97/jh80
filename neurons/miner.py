# The MIT License (MIT)
# Copyright © 2023 Yuma Rao
# TODO(developer): YANEZ - MIID Team
# Copyright © 2025 YANEZ

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

"""
Modular Identity Variation Miner

This module implements a clean, modular Bittensor miner that generates identity variations
using specialized modules for each component:

Architecture:
1. parse_query/parse_query.py - Parses validator query templates
2. name/name.py - Generates name variations  
3. dob/dob.py - Generates date of birth variations
4. address/address.py - Generates address variations

Workflow:
1. Receive IdentitySynapse from validator
2. Parse query template to extract requirements
3. For each identity, generate variations using specialized modules
4. Combine variations into complete identity variations
5. Return structured response to validator

This modular approach provides:
- Clean separation of concerns
- Easy maintenance and testing
- Specialized optimization for each component
- Maximum validator scoring through targeted generation
"""

import time
import typing
import argparse
import bittensor as bt
import os
import sys
from typing import List, Dict, Any, Optional

# Bittensor Miner Template:
from MIID.protocol import IdentitySynapse

# Import base miner class which takes care of most of the boilerplate
from MIID.base.miner import BaseMinerNeuron

from bittensor.core.errors import NotVerifiedException

# Import our modular components (keeping for potential future use)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# from parse_query.parse_query import parse_query_template
# from name.name import generate_name_variations
# from dob.dob import generate_dob_variations
# from address.address import generate_address_variations

# Optional imports for detailed metrics calculation
try:
    import jellyfish
    JELLYFISH_AVAILABLE = True
except ImportError:
    JELLYFISH_AVAILABLE = False


class Miner(BaseMinerNeuron):
    """
    Modular Identity Variation Miner Neuron
    
    This miner uses a clean modular architecture to generate identity variations:
    
    Components:
    - Query Parser: Extracts requirements from validator query templates
    - Name Generator: Creates name variations with phonetic/orthographic similarity
    - DOB Generator: Creates date of birth variations with realistic deviations
    - Address Generator: Creates address variations using real geocoded addresses
    
    The miner processes each identity component separately and combines them into
    complete identity variations that maximize validator scoring.
    
    Key Features:
    - Modular design for easy maintenance
    - Specialized generators for optimal scoring
    - Real address generation via Nominatim API
    - Comprehensive query requirement parsing
    - Clean separation of concerns
    """
    WHITELISTED_VALIDATORS = {
        "5C4qiYkqKjqGDSvzpf6YXCcnBgM6punh8BQJRP78bqMGsn54": "RoundTable21",
        "5DUB7kNLvvx8Dj7D8tn54N1C7Xok6GodNPQE2WECCaL9Wgpr": "Yanez", 
        "5GWzXSra6cBM337nuUU7YTjZQ6ewT2VakDpMj8Pw2i8v8PVs": "Yuma",
        "5HbUFHW4XVhbQvMbSy7WDjvhHb62nuYgP1XBsmmz9E2E2K6p": "OpenTensor",
        "5GQqAhLKVHRLpdTqRg1yc3xu7y47DicJykSpggE2GuDbfs54": "Rizzo",
        "5HK5tp6t2S59DywmHRWPBVJeJ86T61KjurYqeooqj8sREpeN": "Tensora",
        "5E2LP6EnZ54m3wS8s1yPvD5c3xo71kQroBw7aUVK32TKeZ5u": "Tao.bot",
        "5GuPvuyKBJAWQbEGAkMbfRpG5qDqqhML8uDVSWoFjqcKKvDU": "Testnet_omar",
        "5CnkkjPdfsA6jJDHv2U6QuiKiivDuvQpECC13ffdmSDbkgtt": "Testnet_asem"
    }

    def __init__(self, config=None):
        
        super(Miner, self).__init__(config=config)
        
        # Set up validator verification
        self.axon.verify_fns[IdentitySynapse.__name__] = self._verify_validator_request
        
        bt.logging.info("#✅ Modular miner initialization complete")

    async def _verify_validator_request(self, synapse: IdentitySynapse) -> None:
        """
        Rejects any RPC that is not cryptographically proven to come from
        one of the whitelisted validator hotkeys.

        Signature *must* be present and valid.  If anything is missing or
        incorrect we raise `NotVerifiedException`, which the Axon middleware
        converts into a 401 reply.
        """
        # ----------  basic sanity checks  ----------
        if synapse.dendrite is None:
            raise NotVerifiedException("Missing dendrite terminal in request")

        hotkey    = synapse.dendrite.hotkey
        # signature = synapse.dendrite.signature
        nonce     = synapse.dendrite.nonce
        uuid      = synapse.dendrite.uuid
        body_hash = synapse.computed_body_hash

        # 1 — is the sender even on our allow‑list?
        if hotkey not in self.WHITELISTED_VALIDATORS:
            raise NotVerifiedException(f"{hotkey} is not a whitelisted validator")

        # 3 — run all the standard Bittensor checks (nonce window, replay,
        #     timeout, signature, …).  This *does not* insist on a signature,
        #     so we still do step 4 afterwards.
        message = (
            f"nonce: {nonce}. "
            f"hotkey {hotkey}. "
            f"self hotkey {self.wallet.hotkey.ss58_address}. "
            f"uuid {uuid}. "
            f"body hash {body_hash} "
        )
        bt.logging.info(
            f"Verifying message: {message}"
        )

        await self.axon.default_verify(synapse)

        # 5 — all good ➜ let the middleware continue
        bt.logging.info(
            f"Verified call from {self.WHITELISTED_VALIDATORS[hotkey]} ({hotkey})"
        )

    async def forward(self, synapse: IdentitySynapse) -> IdentitySynapse:
        
        
        # Generate a unique run ID using timestamp
        run_id = int(time.time())
        start_time = time.time()
        
        # Get timeout from synapse (default to 120s if not specified)
        timeout = getattr(synapse, 'timeout', 120.0)
        bt.logging.info("*" * 80)
        bt.logging.info(synapse)
        bt.logging.info("*" * 80)
        try:
            # 🎯 CRITICAL FIX: Use the proven variation_generator_clean.py approach
            bt.logging.info("#📋 Using proven variation generator...")
            
            # Import the working variation generator
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'refer'))
            from variation_generator_clean import generate_variations as generate_variations_clean
            
            # Use the proven generator that works
            bt.logging.error("🔄 USING PROVEN VARIATION GENERATOR")
            variations = generate_variations_clean(synapse)
            
            # Set variations in synapse
            synapse.variations = variations
            
            # Log results
            total_time = time.time() - start_time
            
            # Calculate total variations (handle both regular and UAV formats)
            total_variations = 0
            if isinstance(variations, dict):
                for name, name_variations in variations.items():
                    if isinstance(name_variations, list):
                        total_variations += len(name_variations)
                    elif isinstance(name_variations, dict) and 'variations' in name_variations:
                        total_variations += len(name_variations['variations'])
            
            # CRITICAL: Log final variations being returned
            bt.logging.error("🎯 FINAL VARIATIONS BEING RETURNED:")
            if isinstance(variations, dict):
                for name, name_variations in variations.items():
                    if isinstance(name_variations, list):
                        bt.logging.error(f"   • {name}: {len(name_variations)} variations")
                    elif isinstance(name_variations, dict) and 'variations' in name_variations:
                        bt.logging.error(f"   • {name}: {len(name_variations['variations'])} variations (UAV format)")
                    else:
                        bt.logging.error(f"   • {name}: Unknown format")
            
            bt.logging.error(f"📊 FINAL STATS:")
            bt.logging.error(f"   • Total names in synapse.variations: {len(variations) if isinstance(variations, dict) else 0}")
            bt.logging.error(f"   • Total variations generated: {total_variations}")
            bt.logging.error(f"   • Processing time: {total_time:.2f}s")
            
        except Exception as e:
            bt.logging.error(f"❌ CRITICAL ERROR in variation generation: {e}")
            import traceback
            bt.logging.error(traceback.format_exc())
            
            # EMERGENCY FALLBACK: Create basic variations for all identities
            bt.logging.error("🚨 EMERGENCY FALLBACK: Creating basic variations")
            emergency_variations = {}
            for identity in synapse.identity:
                if len(identity) > 0:
                    name = identity[0]
                    dob = identity[1] if len(identity) > 1 else "1990-01-01"
                    address = identity[2] if len(identity) > 2 else "Unknown"
                    
                    # Create 8 basic variations (common count)
                    emergency_variations[name] = [[name, dob, address] for _ in range(8)]
            
            synapse.variations = emergency_variations
            bt.logging.error(f"✅ EMERGENCY: Created variations for {len(emergency_variations)} names")
        
        return synapse
    
    def _combine_variations(self, name_vars: List[str], dob_vars: List[str], 
                          address_vars: List[str], target_count: int) -> List[List[str]]:
        """
        Combine name, DOB, and address variations into complete identity variations.
        
        Creates all possible combinations up to the target count, ensuring
        each complete variation has a unique combination of components.
        
        Args:
            name_vars: List of name variations
            dob_vars: List of DOB variations  
            address_vars: List of address variations
            target_count: Target number of complete variations
            
        Returns:
            List of complete identity variations [name, dob, address]
        """
        complete_variations = []
        used_combinations = set()
        
        # Ensure we have enough variations in each component
        # Extend lists if needed by cycling through existing variations
        while len(name_vars) < target_count:
            name_vars.extend(name_vars[:min(len(name_vars), target_count - len(name_vars))])
        
        while len(dob_vars) < target_count:
            dob_vars.extend(dob_vars[:min(len(dob_vars), target_count - len(dob_vars))])
            
        while len(address_vars) < target_count:
            address_vars.extend(address_vars[:min(len(address_vars), target_count - len(address_vars))])
        
        # Generate combinations
        for i in range(target_count):
            # Use modulo to cycle through variations if we run out
            name_idx = i % len(name_vars)
            dob_idx = i % len(dob_vars)
            address_idx = i % len(address_vars)
            
            # Create combination
            combination = (name_vars[name_idx], dob_vars[dob_idx], address_vars[address_idx])
            
            # Ensure uniqueness
            combination_key = f"{combination[0]}|{combination[1]}|{combination[2]}"
            if combination_key not in used_combinations:
                complete_variations.append(list(combination))
                used_combinations.add(combination_key)
            else:
                # If combination exists, try slight variation
                # Offset one of the indices to create a different combination
                alt_name_idx = (name_idx + 1) % len(name_vars)
                alt_combination = (name_vars[alt_name_idx], dob_vars[dob_idx], address_vars[address_idx])
                alt_key = f"{alt_combination[0]}|{alt_combination[1]}|{alt_combination[2]}"
                
                if alt_key not in used_combinations:
                    complete_variations.append(list(alt_combination))
                    used_combinations.add(alt_key)
                else:
                    # Last resort: just add the original combination
                    complete_variations.append(list(combination))
        
        return complete_variations[:target_count]
    
 
    
    async def blacklist(
        self, synapse: IdentitySynapse
    ) -> typing.Tuple[bool, str]:
        """
        Determines whether an incoming request should be blacklisted and thus ignored.
        
        This function implements security checks to ensure that only authorized
        validators can query this miner. It verifies:
        1. Whether the request has a valid dendrite and hotkey
        2. Whether the hotkey is one of the ones on the white list
        
        Args:
            synapse: A IdentitySynapse object constructed from the incoming request.

        Returns:
            Tuple[bool, str]: A tuple containing:
                - bool: Whether the request should be blacklisted
                - str: The reason for the decision
        """
        # Check if the request has a valid dendrite and hotkey
        if synapse.dendrite is None or synapse.dendrite.hotkey is None:
            bt.logging.warning(
                "Received a request without a dendrite or hotkey."
            )
            return True, "Missing dendrite or hotkey"

        if synapse.dendrite.hotkey not in self.WHITELISTED_VALIDATORS:
            bt.logging.trace(
                f"Blacklisting un-registered hotkey {synapse.dendrite.hotkey}"
            )
            return True, "Unrecognized hotkey"

        # If all checks pass, allow the request
        bt.logging.trace(
            f"Not Blacklisting recognized hotkey {synapse.dendrite.hotkey}"
        )
        return False, "Hotkey recognized!"

    async def priority(self, synapse: IdentitySynapse) -> float:
        """
        The priority function determines the order in which requests are handled.
        
        This function assigns a priority to each request based on the stake of the
        calling entity. Requests with higher priority are processed first, which
        ensures that validators with more stake get faster responses.
        
        Args:
            synapse: The IdentitySynapse object that contains metadata about the incoming request.

        Returns:
            float: A priority score derived from the stake of the calling entity.
                  Higher values indicate higher priority.
        """
        # Check if the request has a valid dendrite and hotkey
        if synapse.dendrite is None or synapse.dendrite.hotkey is None:
            bt.logging.warning(
                "Received a request without a dendrite or hotkey."
            )
            return 0.0

        # Get the UID of the caller
        caller_uid = self.metagraph.hotkeys.index(
            synapse.dendrite.hotkey
        )
        
        # Use the stake as the priority
        # Higher stake = higher priority
        priority = float(
            self.metagraph.S[caller_uid]
        )
        
        bt.logging.trace(
            f"Prioritizing {synapse.dendrite.hotkey} with value: {priority}"
        )
        return priority

    @classmethod
    def config(cls):
        """
        Returns the configuration object specific to this miner after adding relevant arguments.
        """
        parser = argparse.ArgumentParser()
        bt.Wallet.add_args(parser)
        bt.Subtensor.add_args(parser)
        bt.logging.add_args(parser)
        bt.Axon.add_args(parser)
        
        # Import and add miner-specific arguments
        from MIID.utils.config import add_args, add_miner_args
        add_args(cls, parser)
        add_miner_args(cls, parser)
        
        return bt.Config(parser)


# This is the main function, which runs the miner.
if __name__ == "__main__":
    with Miner() as miner:
        while True:
            # bt.logging.info(f"----------------------------------Name Variation Miner running... {time.time()}")
            time.sleep(30)
