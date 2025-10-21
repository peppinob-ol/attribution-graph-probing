#!/usr/bin/env python3
"""
Test rapido API Neuronpedia con valori hardcoded.

Uso:
    python scripts/experiments/test_api_quick.py
"""

import requests
import json

BASE_URL = "https://www.neuronpedia.org/api"

# Valori dal tuo esempio
model_id = "gemma-2-2b"
layer = 9
feature = 4114
test_text = "And you"

print("=" * 80)
print("TEST RAPIDO API NEURONPEDIA")
print("=" * 80)

print(f"\n[PARAMS] Parametri test:")
print(f"   Model: {model_id}")
print(f"   Layer: {layer}")
print(f"   Feature: {feature}")
print(f"   Text: '{test_text}'")

# Combinazioni da testare
test_combinations = [
    f"{layer}-gemmascope-transcoder-16k",  # Dal tuo esempio
    f"{layer}-gemmascope-res-16k",
    f"{layer}-gemma-transcoder-16k",
    f"{layer}-gemma-res-16k",
]

print(f"\n[TEST] Provo {len(test_combinations)} combinazioni:")
for i, source in enumerate(test_combinations, 1):
    print(f"   {i}. {source}")

results = []

print(f"\n{'=' * 80}")
print("INIZIO TEST")
print('=' * 80)

for i, source in enumerate(test_combinations, 1):
    print(f"\n[TEST {i}/{len(test_combinations)}] Source: {source}")
    
    payload = {
        "feature": {
            "modelId": model_id,
            "source": source,
            "index": str(feature)
        },
        "customText": test_text
    }
    
    print(f"   Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/activation/new",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        
        status_code = response.status_code
        
        print(f"   Status: {status_code}")
        
        if status_code == 200:
            try:
                data = response.json()
                has_values = "values" in data or "activations" in data
                
                if has_values:
                    print(f"   [SUCCESS]")
                    tokens = data.get("tokens", [])
                    
                    if "values" in data:
                        values = data.get("values", [])
                        print(f"   Formato: nuovo (values)")
                    else:
                        values = data.get("activations", {}).get("values", [])
                        print(f"   Formato: vecchio (activations.values)")
                    
                    print(f"   Tokens: {len(tokens)} - {tokens}")
                    print(f"   Values: {len(values)} - {values[:10] if len(values) > 10 else values}")
                    
                    results.append((source, "SUCCESS", status_code))
                else:
                    print(f"   [PARTIAL] Response OK ma dati mancanti")
                    print(f"   Keys: {list(data.keys())}")
                    results.append((source, "PARTIAL", status_code))
            except Exception as e:
                print(f"   [ERROR] Errore parsing JSON: {e}")
                print(f"   Raw response: {response.text[:500]}")
                results.append((source, "JSON_ERROR", status_code))
        
        elif status_code == 500:
            print(f"   [ERROR] SERVER ERROR 500")
            try:
                error_data = response.json()
                print(f"   Error data: {error_data}")
            except:
                print(f"   Raw: {response.text[:200]}")
            results.append((source, "ERROR_500", status_code))
        
        elif status_code == 404:
            print(f"   [ERROR] NOT FOUND 404")
            results.append((source, "NOT_FOUND", status_code))
        
        else:
            print(f"   [ERROR] HTTP ERROR {status_code}")
            try:
                error_data = response.json()
                print(f"   Error: {error_data}")
            except:
                print(f"   Raw: {response.text[:200]}")
            results.append((source, f"ERROR_{status_code}", status_code))
    
    except requests.exceptions.Timeout:
        print(f"   [TIMEOUT] dopo 15s")
        results.append((source, "TIMEOUT", None))
    
    except Exception as e:
        print(f"   [EXCEPTION] {type(e).__name__}: {e}")
        results.append((source, "EXCEPTION", None))

# Summary
print(f"\n{'=' * 80}")
print("SUMMARY")
print('=' * 80)

successes = [r for r in results if r[1] == "SUCCESS"]
errors = [r for r in results if "ERROR" in r[1]]

print(f"\n[RESULTS] {len(results)} test eseguiti:")
print(f"   Successi: {len(successes)}")
print(f"   Errori: {len(errors)}")

if successes:
    print(f"\n[SUCCESS] Source format che FUNZIONANO:")
    for source, status, code in successes:
        print(f"   -> {source}")
    
    print(f"\n[RECOMMENDATION] Usa questo pattern nel codice:")
    success_source = successes[0][0]
    # Estrai il template (senza layer)
    template = "-".join(success_source.split("-")[1:])
    print(f"   source_template = \"{template}\"")
    print(f"   source = f\"{{layer}}-{template}\"")
else:
    print(f"\n[FAILED] Nessun source format ha funzionato!")

print(f"\n[DETAILS] Dettaglio completo:")
for source, status, code in results:
    print(f"   {source:40} -> {status:20} (HTTP {code})")

print("\n" + "=" * 80 + "\n")

