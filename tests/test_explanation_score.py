#!/usr/bin/env python3
"""
Test per l'API di scoring delle spiegazioni di Neuronpedia

NOTA: Questo endpoint richiede:
1. NEURONPEDIA_API_KEY nel .env
2. OpenRouter API key configurata su https://neuronpedia.org/settings

Il workflow corretto è:
1. Recupera la feature con GET /api/feature/{modelId}/{layer}/{index}
2. Estrai l'explanationId dall'array explanations
3. Usa questo explanationId per calcolare lo score
"""

import os
import requests
from dotenv import load_dotenv
import json
import time

# Carica la API key dal .env
load_dotenv()
api_key = os.getenv("NEURONPEDIA_API_KEY")

if not api_key:
    print("[ERROR] NEURONPEDIA_API_KEY non trovata nel .env")
    print("Aggiungi NEURONPEDIA_API_KEY=your-key nel file .env")
    exit(1)

print(f"[INFO] Usando API key: {api_key[:15]}...")
print("=" * 80)
print("\nQuesta API calcola lo score di spiegazioni esistenti.")
print("Workflow: Feature -> Get explanationId -> Score explanation")
print("=" * 80)

# Endpoints
feature_endpoint = "https://www.neuronpedia.org/api/feature"
score_endpoint = "https://www.neuronpedia.org/api/explanation/score"

# TEST: Score di spiegazioni esistenti
test_features = [
    {
        "name": "Test 1: GPT2-small feature 55",
        "modelId": "gpt2-small",
        "layer": "8-res-jb",
        "index": 55
    },
    {
        "name": "Test 2: Gemma-2-2b feature 9220",
        "modelId": "gemma-2-2b",
        "layer": "6-gemmascope-res-16k",
        "index": 9220
    }
]

headers = {
    "x-api-key": api_key,
    "Content-Type": "application/json"
}

for i, test_feature in enumerate(test_features, 1):
    print(f"\n{'=' * 80}")
    print(f"{test_feature['name']}")
    print(f"{'=' * 80}")
    
    model_id = test_feature['modelId']
    layer = test_feature['layer']
    index = test_feature['index']
    
    # Step 1: Recupera la feature per ottenere l'explanationId
    feature_url = f"{feature_endpoint}/{model_id}/{layer}/{index}"
    print(f"\n[{i}.1] Recupero feature: {model_id}/{layer}/{index}")
    print(f"[{i}.1] GET {feature_url}")
    
    try:
        feature_response = requests.get(feature_url, headers=headers, timeout=30)
        
        if feature_response.status_code != 200:
            print(f"[{i}.1] [FAIL] Status {feature_response.status_code}: {feature_response.text}")
            continue
        
        feature_data = feature_response.json()
        explanations = feature_data.get("explanations", [])
        
        if not explanations:
            print(f"[{i}.1] [INFO] Nessuna spiegazione trovata per questa feature")
            print(f"[{i}.1] Genera prima una spiegazione con /api/explanation/generate")
            continue
        
        # Prendi la prima spiegazione
        explanation = explanations[0]
        explanation_id = explanation.get("id")
        explanation_text = explanation.get("explanation", "N/A")
        
        print(f"[{i}.1] [OK] Feature recuperata!")
        print(f"[{i}.1] Trovate {len(explanations)} spiegazioni")
        print(f"[{i}.1] Explanation ID: {explanation_id}")
        print(f"[{i}.1] Spiegazione: {explanation_text[:100]}...")
        
        # Step 2: Calcola lo score
        print(f"\n[{i}.2] Calcolo score per explanation ID: {explanation_id}")
        
        score_payload = {
            "explanationId": explanation_id,
            "scorerModel": "gpt-4o-mini",
            "scorerType": "recall_alt"
        }
        
        print(f"[{i}.2] Payload:")
        print(json.dumps(score_payload, indent=2))
        
        score_response = requests.post(
            score_endpoint,
            json=score_payload,
            headers=headers,
            timeout=60
        )
        
        print(f"[{i}.2] Status Code: {score_response.status_code}")
        
        if score_response.status_code == 200:
            score_data = score_response.json()
            print(f"[{i}.2] [OK] Score calcolato con successo!")
            
            if "score" in score_data:
                score_info = score_data["score"]
                score_value = score_info.get("value", "N/A")
                print(f"\n[{i}.2] Score Value: {score_value}")
                print(f"[{i}.2] Score Details:")
                print(json.dumps(score_info, indent=2))
            else:
                print(f"[{i}.2] Response completa:")
                print(json.dumps(score_data, indent=2))
        else:
            error_msg = score_response.json().get("message", "Errore sconosciuto") if score_response.headers.get("content-type", "").startswith("application/json") else score_response.text
            print(f"[{i}.2] [FAIL] Status {score_response.status_code}")
            print(f"[{i}.2] Errore: {error_msg}")
            
            if "OpenRouter" in str(error_msg):
                print(f"[{i}.2] [INFO] Devi configurare una OpenRouter API key su:")
                print(f"[{i}.2]       https://neuronpedia.org/settings")
        
    except requests.exceptions.Timeout:
        print(f"[{i}] [FAIL] TIMEOUT")
    except requests.exceptions.ConnectionError as e:
        print(f"[{i}] [FAIL] CONNECTION ERROR: {e}")
    except Exception as e:
        print(f"[{i}] [FAIL] ERROR: {type(e).__name__}: {e}")
    
    # Pausa tra i test
    if i < len(test_features):
        print(f"\n[INFO] Attendo 2 secondi prima del prossimo test...")
        time.sleep(2)

print("\n" + "=" * 80)
print("Test completati!")
print("=" * 80)
print("\nNote:")
print("- Questo endpoint richiede una OpenRouter API key su https://neuronpedia.org/settings")
print("- Il workflow corretto e': Feature -> explanationId -> Score")
print("- Scorer types disponibili: recall_alt, eleuther_fuzz, eleuther_recall, eleuther_embedding")

