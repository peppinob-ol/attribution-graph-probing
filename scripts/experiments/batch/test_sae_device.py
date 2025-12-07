#!/usr/bin/env python3
"""
Minimal test to check SAE device placement.
Run on remote: python test_sae_device.py
"""
import os
import sys

# Setup path for neuronpedia
repo_base = os.environ.get("NP_WORKDIR", "/content")
np_repo = f"{repo_base}/neuronpedia"
if os.path.exists(np_repo):
    sys.path.insert(0, f"{np_repo}/apps/inference")

import torch
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"Device count: {torch.cuda.device_count()}")

# Test 1: Check sae_lens direct loading
print("\n=== Test 1: sae_lens direct loading ===")
try:
    from sae_lens import SAE
    
    # This is the CLT release that gets special-cased in the patch
    release = "mntss-gemma-2-2b-2.5m-clt-as-per-layer"
    sae_id = "0-clt-hp"  # Layer 0
    
    print(f"Loading SAE: {release} / {sae_id}")
    sae = SAE.from_pretrained(release=release, sae_id=sae_id, device="cuda")
    
    print(f"SAE device: {sae.W_enc.device}")
    print(f"SAE W_dec device: {sae.W_dec.device}")
    
    if "cpu" in str(sae.W_enc.device):
        print("WARNING: SAE is on CPU when it should be on CUDA!")
    else:
        print("OK: SAE is on CUDA as expected")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Check neuronpedia_inference SAE loading
print("\n=== Test 2: neuronpedia_inference SaeLensSAE loading ===")
try:
    from neuronpedia_inference.saes.saelens import SaeLensSAE
    
    # Check the source code of the load function
    import inspect
    source = inspect.getsource(SaeLensSAE.load)
    
    if "mntss-gemma-2-2b-2.5m-clt-as-per-layer" in source:
        print("FOUND: CPU special case for CLT in SaeLensSAE.load!")
        print("This is the patched version - will cause device mismatch!")
    else:
        print("OK: No CPU special case found - this is the original version")
    
    # Show relevant lines
    print("\nRelevant source:")
    for line in source.split('\n'):
        if 'device' in line.lower() or 'cpu' in line.lower():
            print(f"  {line}")
            
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("\n=== Test complete ===")












