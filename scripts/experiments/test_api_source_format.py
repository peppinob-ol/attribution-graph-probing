#!/usr/bin/env python3
"""
Script per testare il formato corretto del source per le API di Neuronpedia.

Testa diverse combinazioni per capire quale funziona.

Uso:
    python scripts/experiments/test_api_source_format.py
"""

import sys
import json
import requests
from pathlib import Path
from typing import Dict, List, Tuple

# Setup path
parent_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(parent_dir))

# API info
BASE_URL = "https://www.neuronpedia.org/api"
TEST_TEXT = "And you"

# Carica graph JSON per estrarre info reali
graph_path = parent_dir / "output" / "graph_data" / "the-capital-of-20251019-045827.json"

print("=" * 80)
print("TEST API SOURCE FORMAT - Neuronpedia")
print("=" * 80)

# Carica graph
print(f"\n[LOAD] Caricamento graph: {graph_path.name}")
with open(graph_path, 'r', encoding='utf-8') as f:
    graph_json = json.load(f)

metadata = graph_json.get("metadata", {})
info = metadata.get("info", {})

model_id = metadata.get("scan")
transcoder_set = info.get("transcoder_set", "")
source_urls = info.get("source_urls", [])

print(f"\n[METADATA] Info dal graph:")
print(f"   Model ID: {model_id}")
print(f"   Transcoder set: {transcoder_set}")
print(f"   Source URLs: {len(source_urls)} URLs")
if source_urls:
    print(f"   Prima URL: {source_urls[0][:80]}...")

# Estrai un nodo di esempio
nodes = graph_json.get("nodes", [])
sample_node = None

for node in nodes:
    if node.get("feature_type") == "cross layer transcoder":
        sample_node = node
        break

if not sample_node:
    print("\n[ERROR] Nessun nodo feature trovato nel graph!")
    sys.exit(1)

print(f"\n[NODE] Nodo di esempio:")
print(f"   node_id: {sample_node.get('node_id')}")
print(f"   layer: {sample_node.get('layer')}")
print(f"   feature: {sample_node.get('feature')}")
print(f"   ctx_idx: {sample_node.get('ctx_idx')}")

# Estrai layer e feature dal node_id
node_id = sample_node.get("node_id", "")
parts = node_id.split("_")
layer = int(parts[0]) if len(parts) > 0 else sample_node.get("layer")
feature = int(parts[1]) if len(parts) > 1 else sample_node.get("feature")

print(f"\n[PARSED] Dal node_id '{node_id}':")
print(f"   Layer: {layer}")
print(f"   Feature: {feature}")

# Definisci le combinazioni da testare
print(f"\n[TEST] Provo diverse combinazioni di source format...")
print(f"       Model: {model_id}")
print(f"       Layer: {layer}")
print(f"       Feature: {feature}")
print(f"       Text: '{TEST_TEXT}'")

test_combinations = []

# Se transcoder_set è "gemma", prova sia "gemma" che "gemmascope"
transcoder_variants = ["gemmascope"]
if transcoder_set:
    if transcoder_set.lower() == "gemma":
        transcoder_variants = ["gemmascope", "gemma"]
    else:
        transcoder_variants = [transcoder_set, "gemmascope"]

# Tipi di source
type_variants = ["res-16k", "transcoder-16k"]

# Determina tipo dalle URL se disponibili
detected_type = None
for url in source_urls:
    if "transcoder" in url.lower():
        detected_type = "transcoder-16k"
        break
    elif "res" in url.lower():
        detected_type = "res-16k"
        break

if detected_type:
    print(f"       Tipo rilevato dagli URL: {detected_type}")
    # Metti il tipo rilevato per primo
    if detected_type in type_variants:
        type_variants.remove(detected_type)
        type_variants.insert(0, detected_type)

# Genera tutte le combinazioni
for trans_set in transcoder_variants:
    for src_type in type_variants:
        source = f"{layer}-{trans_set}-{src_type}"
        test_combinations.append({
            "source": source,
            "transcoder_set": trans_set,
            "type": src_type
        })

print(f"\n[COMBINATIONS] Testo {len(test_combinations)} combinazioni:")
for i, combo in enumerate(test_combinations, 1):
    print(f"   {i}. {combo['source']}")

# Testa ogni combinazione
print(f"\n{'=' * 80}")
print("INIZIO TEST")
print('=' * 80)

results = []

for i, combo in enumerate(test_combinations, 1):
    source = combo["source"]
    
    print(f"\n[TEST {i}/{len(test_combinations)}] Source: {source}")
    
    payload = {
        "feature": {
            "modelId": model_id,
            "source": source,
            "index": str(feature)
        },
        "customText": TEST_TEXT
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/activation/new",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        status_code = response.status_code
        
        if status_code == 200:
            data = response.json()
            success = "values" in data or "activations" in data
            
            if success:
                print(f"   ✓ SUCCESS! Status: {status_code}")
                tokens = data.get("tokens", [])
                values = data.get("values", data.get("activations", {}).get("values", []))
                print(f"      Tokens: {len(tokens)}")
                print(f"      Values: {len(values)}")
                print(f"      Sample tokens: {tokens[:5]}")
                results.append({
                    "source": source,
                    "status": "success",
                    "code": status_code
                })
            else:
                print(f"   × PARTIAL: Status {status_code} ma dati mancanti")
                print(f"      Response keys: {list(data.keys())}")
                results.append({
                    "source": source,
                    "status": "partial",
                    "code": status_code,
                    "keys": list(data.keys())
                })
        else:
            print(f"   × FAILED: Status {status_code}")
            try:
                error_data = response.json()
                print(f"      Error: {error_data}")
            except:
                print(f"      Response: {response.text[:200]}")
            
            results.append({
                "source": source,
                "status": "error",
                "code": status_code
            })
    
    except requests.exceptions.Timeout:
        print(f"   × TIMEOUT")
        results.append({
            "source": source,
            "status": "timeout",
            "code": None
        })
    
    except Exception as e:
        print(f"   × EXCEPTION: {e}")
        results.append({
            "source": source,
            "status": "exception",
            "code": None,
            "error": str(e)
        })

# Summary
print(f"\n{'=' * 80}")
print("SUMMARY")
print('=' * 80)

successes = [r for r in results if r["status"] == "success"]
errors = [r for r in results if r["status"] == "error"]
timeouts = [r for r in results if r["status"] == "timeout"]
exceptions = [r for r in results if r["status"] == "exception"]

print(f"\n[RESULTS] {len(test_combinations)} test eseguiti:")
print(f"   ✓ Successi: {len(successes)}")
print(f"   × Errori: {len(errors)}")
print(f"   ⏱ Timeout: {len(timeouts)}")
print(f"   ⚠ Exception: {len(exceptions)}")

if successes:
    print(f"\n[SUCCESS] Source format che funzionano:")
    for r in successes:
        print(f"   ✓ {r['source']}")
    
    print(f"\n[RECOMMENDATION] Usa questo formato nel codice:")
    success_source = successes[0]["source"]
    # Estrai il template (senza layer)
    template = "-".join(success_source.split("-")[1:])
    print(f"   source_template = \"{template}\"")
    print(f"   source = f\"{{layer}}-{template}\"")

if errors:
    print(f"\n[FAILED] Source format che hanno dato errore:")
    for r in errors:
        print(f"   × {r['source']} (HTTP {r['code']})")

# Salva risultati
output_path = parent_dir / "output" / "api_source_format_test.json"
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump({
        "model_id": model_id,
        "test_node": {
            "node_id": node_id,
            "layer": layer,
            "feature": feature
        },
        "combinations_tested": test_combinations,
        "results": results,
        "summary": {
            "successes": len(successes),
            "errors": len(errors),
            "timeouts": len(timeouts),
            "exceptions": len(exceptions)
        }
    }, f, indent=2)

print(f"\n[SAVED] Risultati salvati in: {output_path}")
print("\n" + "=" * 80 + "\n")

