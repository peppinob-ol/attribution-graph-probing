#!/usr/bin/env python3
"""
Debug: simula esattamente come il codice costruisce il source.
"""

# Simula i metadata del graph JSON reale
metadata = {
    "scan": "gemma-2-2b",
    "prompt": "<bos>The capital of state containing Dallas is",
    "info": {
        "transcoder_set": "gemma",  # ← Questo è ciò che c'è nel JSON
        "source_urls": [
            "https://neuronpedia.org/gemma-2-2b/gemmascope-transcoder-16k",
            "https://huggingface.co/google/gemma-scope-2b-pt-transcoders"
        ]
    }
}

# Simula un nodo del graph
sample_node = {
    "node_id": "9_8335_6",  # layer_feature_ctx
    "feature": 1472083,  # ID interno (NON il feature index)
    "layer": "9",
    "ctx_idx": 6
}

print("=" * 80)
print("DEBUG: COSTRUZIONE SOURCE")
print("=" * 80)

# ═══════════ Estrazione metadata (dal codice reale) ═══════════

model_id = metadata.get("scan")
info = metadata.get("info", {})
transcoder_set_raw = info.get("transcoder_set", "")

print(f"\n[STEP 1] Metadata iniziali:")
print(f"   model_id: {model_id}")
print(f"   transcoder_set_raw: '{transcoder_set_raw}'")

# Conversione transcoder_set
if transcoder_set_raw and transcoder_set_raw.lower() == "gemma":
    transcoder_set = "gemmascope"
    print(f"   [CONV] Convertito 'gemma' -> 'gemmascope'")
elif transcoder_set_raw:
    transcoder_set = transcoder_set_raw
else:
    transcoder_set = "gemmascope"  # default

print(f"   transcoder_set (finale): '{transcoder_set}'")

# Determina source_type
source_urls = info.get("source_urls", [])
source_type = "res-16k"  # Default

print(f"\n[STEP 2] Determinazione source_type:")
print(f"   source_urls: {len(source_urls)} URLs")

for i, url in enumerate(source_urls):
    print(f"      {i+1}. {url}")
    if "transcoder" in url.lower():
        source_type = "transcoder-16k"
        print(f"         [OK] Trovato 'transcoder' -> source_type = '{source_type}'")
        break
    elif "res" in url.lower():
        source_type = "res-16k"
        print(f"         [OK] Trovato 'res' -> source_type = '{source_type}'")
        break

print(f"   source_type (finale): '{source_type}'")

# Costruisci template
source_template = f"{transcoder_set}-{source_type}"

print(f"\n[STEP 3] Costruzione template:")
print(f"   source_template = f\"{{transcoder_set}}-{{source_type}}\"")
print(f"   source_template = '{source_template}'")

# Verifica inference da nodo (potrebbe sovrascrivere!)
print(f"\n[STEP 4] Verifica inference da nodo:")
print(f"   node_id: {sample_node.get('node_id')}")
print(f"   Ha campo 'modelId'? {('modelId' in sample_node)}")

if "modelId" in sample_node:
    node_model = sample_node.get("modelId", "")
    print(f"   modelId dal nodo: '{node_model}'")
    if node_model and "-" in node_model:
        parts = node_model.split("-", 1)
        if len(parts) > 1:
            inferred_template = parts[1]
            print(f"   [WARN] SOVRASCRITTO con template inferito: '{inferred_template}'")
            source_template = inferred_template
else:
    print(f"   [OK] Nessun modelId nel nodo, template non sovrascritto")

# Estrai layer e feature dal node_id
node_id = sample_node.get("node_id", "")
parts = node_id.split("_")

if len(parts) >= 2:
    layer = int(parts[0])
    feature = int(parts[1])
    print(f"\n[STEP 5] Estrazione da node_id '{node_id}':")
    print(f"   layer: {layer}")
    print(f"   feature: {feature}")
    print(f"   (campo 'feature' nel nodo: {sample_node.get('feature')} - IGNORATO)")
else:
    layer = int(sample_node.get("layer", 0))
    feature = sample_node.get("feature", 0)
    print(f"\n[STEP 5] Estrazione fallback:")
    print(f"   layer: {layer}")
    print(f"   feature: {feature}")

# Costruisci source finale
source = f"{layer}-{source_template}"

print(f"\n[STEP 6] Source FINALE:")
print(f"   source = f\"{{layer}}-{{source_template}}\"")
print(f"   source = '{source}'")

# Test API
print(f"\n{'=' * 80}")
print("VERIFICA CON API")
print('=' * 80)

import requests
import json

payload = {
    "feature": {
        "modelId": model_id,
        "source": source,
        "index": str(feature)
    },
    "customText": "And you"
}

print(f"\n[PAYLOAD]")
print(json.dumps(payload, indent=2))

try:
    response = requests.post(
        "https://www.neuronpedia.org/api/activation/new",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=15
    )
    
    status = response.status_code
    print(f"\n[RESPONSE] Status: {status}")
    
    if status == 200:
        data = response.json()
        if "values" in data or "activations" in data:
            print(f"   [OK] SUCCESS! La feature esiste e risponde correttamente.")
            tokens = data.get("tokens", [])
            values = data.get("values", data.get("activations", {}).get("values", []))
            print(f"   Tokens: {tokens}")
            print(f"   Values: {values}")
        else:
            print(f"   [X] Response OK ma dati mancanti")
            print(f"   Keys: {list(data.keys())}")
    elif status == 500:
        print(f"   [X] SERVER ERROR 500")
        try:
            error_data = response.json()
            print(f"   Message: {error_data.get('message', 'No message')}")
        except:
            pass
    elif status == 404:
        print(f"   [X] NOT FOUND 404 - Feature non disponibile")
    else:
        print(f"   [X] HTTP ERROR {status}")

except Exception as e:
    print(f"   [X] EXCEPTION: {e}")

print("\n" + "=" * 80)
print(f"CONCLUSIONE: Il source costruito è '{source}'")
print("=" * 80 + "\n")

