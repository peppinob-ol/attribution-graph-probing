#!/usr/bin/env python3
"""Test con API key dal .env"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("NEURONPEDIA_API_KEY")

model_id = "gemma-2-2b"
source = "6-gemmascope-transcoder-16k"
feature = "9220"
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

print(f"[TEST] Con API key: {api_key[:15]}...")
print(f"Testing: {source}/{feature}")
print(f"Prompt: {prompt}")
print("-" * 80)

headers = {
    "x-api-key": api_key,
    "Content-Type": "application/json"
}

try:
    response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        if "activations" in data:
            print(f"[OK] Success! Got {len(data.get('tokens', []))} tokens")
            print(f"Tokens: {data.get('tokens', [])}")
            print(f"Max activation: {data['activations'].get('maxValue')}")
        else:
            print("[WARNING] No 'activations' in response")
            print(f"Response: {data}")
    else:
        print(f"[FAIL] Response: {response.text[:500]}")
except Exception as e:
    print(f"[ERROR] {e}")


