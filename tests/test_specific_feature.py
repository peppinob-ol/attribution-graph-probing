#!/usr/bin/env python3
"""Test per la feature specifica che fallisce"""

import requests

model_id = "gemma-2-2b"
layer = "6"
feature = "9220"  # Dal warning
source = f"{layer}-gemmascope-transcoder-16k"
prompt = "Austin: the capital city of Texas"

endpoint = "https://www.neuronpedia.org/api/activation/new"
payload = {
    "feature": {
        "modelId": model_id,
        "source": source,
        "index": str(feature)
    },
    "customText": prompt
}

print(f"[TEST] Testing {source}/{feature}")
print(f"Prompt: {prompt}")
print("-" * 80)

try:
    response = requests.post(endpoint, json=payload, timeout=10)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"[OK] Success! Got {len(data.get('tokens', []))} tokens")
        print(f"Tokens: {data.get('tokens', [])[:10]}")  # Prime 10
    else:
        print(f"[FAIL] Response: {response.text[:200]}")
except Exception as e:
    print(f"[ERROR] {e}")


