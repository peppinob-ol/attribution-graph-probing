#!/usr/bin/env python3
"""
Testa multiple features dal graph per capire se il problema è sistemico.
"""

import requests
import json
import time

# Features estratte manualmente dal graph (dai primi 100 righe viste prima)
# Format: (layer, feature_id_dal_node_id)
test_features = [
    (0, 41),    # node_id: 0_41_1
    (0, 96),    # node_id: 0_96_1
    (0, 354),   # node_id: 0_354_1
    (0, 478),   # node_id: 0_478_1
    (9, 8335),  # La feature che sappiamo funziona
]

model_id = "gemma-2-2b"
source_template = "gemmascope-transcoder-16k"
test_text = "And you"

print("=" * 80)
print("TEST MULTIPLE FEATURES DAL GRAPH")
print("=" * 80)

print(f"\n[INFO] Testo {len(test_features)} features dal graph reale")
print(f"   Model: {model_id}")
print(f"   Template: {source_template}")
print(f"   Text: '{test_text}'")

results = []

for i, (layer, feature) in enumerate(test_features, 1):
    source = f"{layer}-{source_template}"
    
    print(f"\n[TEST {i}/{len(test_features)}] Layer {layer}, Feature {feature}")
    print(f"   Source: {source}")
    
    payload = {
        "feature": {
            "modelId": model_id,
            "source": source,
            "index": str(feature)
        },
        "customText": test_text
    }
    
    try:
        response = requests.post(
            "https://www.neuronpedia.org/api/activation/new",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        
        status = response.status_code
        
        if status == 200:
            data = response.json()
            if "values" in data or "activations" in data:
                values = data.get("values", data.get("activations", {}).get("values", []))
                print(f"   [OK] SUCCESS - Values: {values}")
                results.append((layer, feature, "SUCCESS", status))
            else:
                print(f"   [PARTIAL] Response OK ma dati mancanti - Keys: {list(data.keys())}")
                results.append((layer, feature, "PARTIAL", status))
        elif status == 500:
            print(f"   [ERROR] SERVER ERROR 500")
            try:
                error_data = response.json()
                msg = error_data.get('message', '')
                if 'not available' in msg:
                    print(f"   Motivo: Feature non disponibile")
                    results.append((layer, feature, "NOT_AVAILABLE", status))
                else:
                    print(f"   Message: {msg[:100]}")
                    results.append((layer, feature, "ERROR_500", status))
            except:
                results.append((layer, feature, "ERROR_500", status))
        elif status == 404:
            print(f"   [ERROR] NOT FOUND 404")
            results.append((layer, feature, "NOT_FOUND", status))
        elif status == 429:
            print(f"   [ERROR] RATE LIMIT 429")
            results.append((layer, feature, "RATE_LIMIT", status))
        else:
            print(f"   [ERROR] HTTP {status}")
            results.append((layer, feature, f"ERROR_{status}", status))
    
    except Exception as e:
        print(f"   [EXCEPTION] {type(e).__name__}: {e}")
        results.append((layer, feature, "EXCEPTION", None))
    
    # Piccolo delay per evitare rate limiting
    if i < len(test_features):
        time.sleep(0.5)

# Summary
print(f"\n{'=' * 80}")
print("SUMMARY")
print('=' * 80)

successes = [r for r in results if r[2] == "SUCCESS"]
not_available = [r for r in results if r[2] == "NOT_AVAILABLE"]
errors = [r for r in results if "ERROR" in r[2]]

print(f"\n[RESULTS] {len(test_features)} features testate:")
print(f"   SUCCESS: {len(successes)}")
print(f"   NOT AVAILABLE (500): {len(not_available)}")
print(f"   ALTRI ERRORI: {len(errors)}")

print(f"\n[DETAILS]")
for layer, feature, status, code in results:
    print(f"   Layer {layer:2d}, Feature {feature:6d}: {status:20s} (HTTP {code})")

if len(not_available) > 0:
    pct = len(not_available) / len(results) * 100
    print(f"\n[CONCLUSION]")
    print(f"   {pct:.1f}% delle features nel graph NON sono disponibili via API!")
    print(f"   Possibili motivi:")
    print(f"      - Features non pubblicamente accessibili")
    print(f"      - Features rimosse o archiviate")
    print(f"      - Inference API non abilitata per queste features")
    print(f"\n   Questo spiega l'alto tasso di errore nell'esecuzione precedente.")

print("\n" + "=" * 80 + "\n")

