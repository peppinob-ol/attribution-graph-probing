#!/usr/bin/env python3
"""Test per l'API di generazione spiegazioni automatiche di Neuronpedia"""

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

# Endpoint per la generazione di spiegazioni
endpoint = "https://www.neuronpedia.org/api/explanation/generate"

# TEST 1: Token-Act-Pair per Gemma
test_configs = [
    {
        "name": "Test 1: Gemma-2-2b con token-act-pair",
        "payload": {
            "modelId": "gemma-2-2b",
            "layer": "1-clt-hp",
            "index": 11298,
            "explanationType": "oai_token-act-pair",
            "explanationModelName": "gpt-4o-mini"
        }
    },
    {
        "name": "Test 2: Gemma-2-2b layer diverso",
        "payload": {
            "modelId": "gemma-2-2b",
            "layer": "6-gemmascope-transcoder-16k",
            "index": 9220,
            "explanationType": "oai_token-act-pair",
            "explanationModelName": "gpt-4o-mini"
        }
    },
    {
        "name": "Test 3: GPT2-small (esempio dalla doc)",
        "payload": {
            "modelId": "gpt2-small",
            "layer": "8-res-jb",
            "index": 55,
            "explanationType": "oai_token-act-pair",
            "explanationModelName": "gpt-4o-mini"
        }
    }
]

headers = {
    "x-api-key": api_key,
    "Content-Type": "application/json"
}

for i, test in enumerate(test_configs, 1):
    print(f"\n{'=' * 80}")
    print(f"{test['name']}")
    print(f"{'=' * 80}")
    
    payload = test['payload']
    print(f"Payload:")
    print(json.dumps(payload, indent=2))
    print()
    
    try:
        print(f"[{i}] Invio richiesta POST a {endpoint}...")
        response = requests.post(
            endpoint, 
            json=payload, 
            headers=headers, 
            timeout=60  # Timeout più lungo perché la generazione può richiedere tempo
        )
        
        print(f"[{i}] Status Code: {response.status_code}")
        print(f"[{i}] Response Headers: {dict(response.headers)}")
        print()
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"[{i}] [OK] SUCCESS!")
                print(f"[{i}] Response:")
                print(json.dumps(data, indent=2))
            except json.JSONDecodeError:
                print(f"[{i}] [OK] SUCCESS (ma risposta non è JSON)")
                print(f"[{i}] Response text: {response.text[:500]}")
        elif response.status_code == 400:
            print(f"[{i}] [FAIL] BAD REQUEST (400)")
            print(f"[{i}] Possibili problemi:")
            print(f"     - Parametri non validi")
            print(f"     - modelId, layer o index non esistono")
            print(f"     - explanationType non supportato")
            print(f"[{i}] Response: {response.text}")
        elif response.status_code == 401:
            print(f"[{i}] [FAIL] UNAUTHORIZED (401)")
            print(f"[{i}] La API key non è valida o non ha i permessi")
            print(f"[{i}] Response: {response.text}")
        elif response.status_code == 403:
            print(f"[{i}] [FAIL] FORBIDDEN (403)")
            print(f"[{i}] Devi settare le API keys OpenAI/Anthropic/Google in:")
            print(f"[{i}] https://neuronpedia.org/settings")
            print(f"[{i}] Response: {response.text}")
        elif response.status_code == 404:
            print(f"[{i}] [FAIL] NOT FOUND (404)")
            print(f"[{i}] Feature non trovata o endpoint errato")
            print(f"[{i}] Response: {response.text}")
        elif response.status_code == 500:
            print(f"[{i}] [FAIL] SERVER ERROR (500)")
            print(f"[{i}] Errore interno del server")
            print(f"[{i}] Response: {response.text}")
        else:
            print(f"[{i}] [FAIL] UNEXPECTED STATUS: {response.status_code}")
            print(f"[{i}] Response: {response.text}")
            
    except requests.exceptions.Timeout:
        print(f"[{i}] [FAIL] TIMEOUT - La richiesta ha impiegato troppo tempo")
    except requests.exceptions.ConnectionError as e:
        print(f"[{i}] [FAIL] CONNECTION ERROR: {e}")
    except Exception as e:
        print(f"[{i}] [FAIL] ERROR: {type(e).__name__}: {e}")
    
    # Pausa tra i test per non sovraccaricare l'API
    if i < len(test_configs):
        print(f"\n[INFO] Attendo 2 secondi prima del prossimo test...")
        time.sleep(2)

print("\n" + "=" * 80)
print("Test completati!")
print("=" * 80)
print("\nNote importanti:")
print("1. Se ricevi 403, devi settare le API keys di OpenAI/Anthropic/Google su:")
print("   https://neuronpedia.org/settings")
print("2. explanationType supportati: 'oai_token-act-pair', 'oai_attention-head'")
print("3. explanationModelName deve essere tra quelli disponibili nel dropdown su Neuronpedia")
print("4. Verifica che modelId, layer e index esistano su Neuronpedia")

