#!/usr/bin/env python3
"""Test per trovare il formato corretto del source per l'API Neuronpedia"""

import requests
import json

# Info dal graph JSON
model_id = "gemma-2-2b"
layer = "0"
feature = "902"  # Prima feature dal graph

# Testa diversi formati
source_formats = [
    f"{layer}-gemmascope-transcoder-16k",  # Formato attuale (fallisce)
    f"{layer}-gemmascope-res-16k",         # Con res invece di transcoder
    "gemmascope-transcoder-16k",           # Senza layer prefix
    "gemmascope-res-16k",                  # res senza layer
    f"{layer}-res-16k",                    # Solo res-16k
    f"{layer}-transcoder-16k",             # Solo transcoder-16k
]

prompt = "Test prompt"

print("[TEST] Testing Neuronpedia API source formats")
print(f"Model: {model_id}")
print(f"Feature: layer={layer}, index={feature}")
print("-" * 80)

for source in source_formats:
    endpoint = "https://www.neuronpedia.org/api/activation/new"
    payload = {
        "feature": {
            "modelId": model_id,
            "source": source,
            "index": str(feature)
        },
        "customText": prompt
    }
    
    try:
        response = requests.post(endpoint, json=payload, timeout=10)
        status = response.status_code
        
        if status == 200:
            print(f"[OK]  {source:40} - SUCCESS")
            data = response.json()
            if "activations" in data:
                print(f"      -> Got {len(data.get('tokens', []))} tokens")
            break  # Trovato il formato giusto!
        elif status == 404:
            print(f"[404] {source:40} - Feature not found")
        elif status == 500:
            print(f"[500] {source:40} - Server error")
        else:
            print(f"[{status}] {source:40} - HTTP error")
    except Exception as e:
        print(f"[ERR] {source:40} - {e}")

print("-" * 80)
print("[DONE] Test completato")


