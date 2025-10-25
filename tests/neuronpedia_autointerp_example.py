#!/usr/bin/env python3
"""
Esempio completo per usare l'API Auto-Interp di Neuronpedia

REQUISITI:
1. Imposta NEURONPEDIA_API_KEY nel file .env
2. Configura le API keys OpenAI/Anthropic/Google su:
   https://neuronpedia.org/settings

USO:
    python tests/neuronpedia_autointerp_example.py
"""

import os
import requests
from dotenv import load_dotenv
import json

class NeuronpediaAutoInterp:
    """Client per l'API Auto-Interp di Neuronpedia"""
    
    BASE_URL = "https://www.neuronpedia.org/api"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "x-api-key": api_key,
            "Content-Type": "application/json"
        })
    
    def generate_explanation(
        self,
        model_id: str,
        layer: str,
        index: int,
        explanation_type: str = "oai_token-act-pair",
        explanation_model: str = "gpt-4o-mini"
    ):
        """
        Genera una spiegazione per una feature specifica.
        
        Args:
            model_id: ID del modello (es. "gpt2-small", "gemma-2-2b")
            layer: Layer della feature (es. "8-res-jb")
            index: Indice della feature
            explanation_type: Tipo di spiegazione
                - "oai_token-act-pair" (default)
                - "oai_attention-head"
            explanation_model: Modello per generare la spiegazione
                - "gpt-4o-mini" (default)
                - "gpt-4"
                - "claude-3-5-sonnet"
                - etc.
        
        Returns:
            dict: Risposta dell'API o informazioni sull'errore
        """
        endpoint = f"{self.BASE_URL}/explanation/generate"
        
        payload = {
            "modelId": model_id,
            "layer": layer,
            "index": index,
            "explanationType": explanation_type,
            "explanationModelName": explanation_model
        }
        
        print(f"\n[GENERATE] Feature: {model_id}/{layer}/{index}")
        print(f"[GENERATE] Tipo: {explanation_type}, Modello: {explanation_model}")
        
        try:
            response = self.session.post(endpoint, json=payload, timeout=60)
            
            if response.status_code == 200:
                print("[GENERATE] [OK] Successo!")
                return {
                    "success": True,
                    "data": response.json()
                }
            elif response.status_code == 400:
                error_msg = response.json().get("message", "Errore sconosciuto")
                
                if "No auto-interp key" in error_msg:
                    print("[GENERATE] [FAIL] API keys non configurate!")
                    print("[GENERATE] Configura le keys su: https://neuronpedia.org/settings")
                    return {
                        "success": False,
                        "error": "no_autointerp_keys",
                        "message": "Configura le API keys OpenAI/Anthropic/Google su Neuronpedia"
                    }
                elif "already exists" in error_msg:
                    print("[GENERATE] [INFO] Spiegazione gia' esistente")
                    return {
                        "success": False,
                        "error": "already_exists",
                        "message": "La spiegazione esiste gia' per questa feature"
                    }
                else:
                    print(f"[GENERATE] [FAIL] Bad Request: {error_msg}")
                    return {
                        "success": False,
                        "error": "bad_request",
                        "message": error_msg
                    }
            else:
                print(f"[GENERATE] [FAIL] Status {response.status_code}: {response.text}")
                return {
                    "success": False,
                    "error": f"status_{response.status_code}",
                    "message": response.text
                }
                
        except requests.exceptions.Timeout:
            print("[GENERATE] [FAIL] Timeout")
            return {
                "success": False,
                "error": "timeout",
                "message": "La richiesta ha impiegato troppo tempo"
            }
        except Exception as e:
            print(f"[GENERATE] [FAIL] Errore: {e}")
            return {
                "success": False,
                "error": "exception",
                "message": str(e)
            }
    
    def get_feature(self, model_id: str, layer: str, index: int):
        """
        Ottiene i dettagli di una feature, incluse le spiegazioni esistenti.
        
        Args:
            model_id: ID del modello
            layer: Layer della feature
            index: Indice della feature
        
        Returns:
            dict: Dati della feature o errore
        """
        endpoint = f"{self.BASE_URL}/feature/{model_id}/{layer}/{index}"
        
        print(f"\n[FEATURE] Recupero feature: {model_id}/{layer}/{index}")
        
        try:
            response = self.session.get(endpoint, timeout=30)
            
            if response.status_code == 200:
                print("[FEATURE] [OK] Successo!")
                return {
                    "success": True,
                    "data": response.json()
                }
            else:
                print(f"[FEATURE] [FAIL] Status {response.status_code}")
                return {
                    "success": False,
                    "error": f"status_{response.status_code}",
                    "message": response.text
                }
        except Exception as e:
            print(f"[FEATURE] [FAIL] Errore: {e}")
            return {
                "success": False,
                "error": "exception",
                "message": str(e)
            }
    
    def score_explanation(
        self,
        explanation_id: str,
        scorer_model: str = "gpt-4o-mini",
        scorer_type: str = "recall_alt"
    ):
        """
        Calcola lo score di una spiegazione esistente.
        
        Args:
            explanation_id: ID della spiegazione (da ottenere con get_feature)
            scorer_model: Modello per lo scoring (es. "gpt-4o-mini")
            scorer_type: Tipo di scoring method:
                - "recall_alt" (default)
                - "eleuther_fuzz"
                - "eleuther_recall"
                - "eleuther_embedding"
        
        Returns:
            dict: Risposta dell'API o informazioni sull'errore
        """
        endpoint = f"{self.BASE_URL}/explanation/score"
        
        payload = {
            "explanationId": explanation_id,
            "scorerModel": scorer_model,
            "scorerType": scorer_type
        }
        
        print(f"\n[SCORE] Explanation ID: {explanation_id}")
        print(f"[SCORE] Scorer: {scorer_model} / {scorer_type}")
        
        try:
            response = self.session.post(endpoint, json=payload, timeout=60)
            
            if response.status_code == 200:
                print("[SCORE] [OK] Successo!")
                return {
                    "success": True,
                    "data": response.json()
                }
            elif response.status_code == 400:
                error_msg = response.json().get("message", "Errore sconosciuto")
                print(f"[SCORE] [FAIL] Bad Request: {error_msg}")
                return {
                    "success": False,
                    "error": "bad_request",
                    "message": error_msg
                }
            else:
                print(f"[SCORE] [FAIL] Status {response.status_code}: {response.text}")
                return {
                    "success": False,
                    "error": f"status_{response.status_code}",
                    "message": response.text
                }
                
        except Exception as e:
            print(f"[SCORE] [FAIL] Errore: {e}")
            return {
                "success": False,
                "error": "exception",
                "message": str(e)
            }


def main():
    """Esempio d'uso"""
    
    print("=" * 80)
    print("Neuronpedia Auto-Interp API - Esempio d'uso")
    print("=" * 80)
    
    # Carica API key
    load_dotenv()
    api_key = os.getenv("NEURONPEDIA_API_KEY")
    
    if not api_key:
        print("\n[ERROR] NEURONPEDIA_API_KEY non trovata!")
        print("Aggiungi NEURONPEDIA_API_KEY=your-key nel file .env")
        return
    
    print(f"\n[INFO] API Key: {api_key[:15]}...")
    
    # Inizializza client
    client = NeuronpediaAutoInterp(api_key)
    
    # Esempio 1: Genera spiegazione per GPT2-small
    print("\n" + "=" * 80)
    print("ESEMPIO 1: Genera spiegazione")
    print("=" * 80)
    
    result = client.generate_explanation(
        model_id="gpt2-small",
        layer="8-res-jb",
        index=55,
        explanation_type="oai_token-act-pair",
        explanation_model="gpt-4o-mini"
    )
    
    if result["success"]:
        print("\n[RISULTATO]")
        print(json.dumps(result["data"], indent=2))
    else:
        print(f"\n[ERRORE] {result['error']}: {result['message']}")
    
    # Esempio 2: Recupera feature e ottieni score
    print("\n" + "=" * 80)
    print("ESEMPIO 2: Recupera feature e ottieni score della spiegazione")
    print("=" * 80)
    
    # Prima recupera la feature per ottenere l'explanationId
    feature_result = client.get_feature(
        model_id="gpt2-small",
        layer="8-res-jb",
        index=55
    )
    
    if feature_result["success"]:
        feature_data = feature_result["data"]
        explanations = feature_data.get("explanations", [])
        
        if explanations:
            explanation_id = explanations[0].get("id")
            print(f"\n[INFO] Trovato explanation ID: {explanation_id}")
            
            # Ora calcola lo score
            score_result = client.score_explanation(
                explanation_id=explanation_id,
                scorer_model="gpt-4o-mini",
                scorer_type="recall_alt"
            )
            
            if score_result["success"]:
                print("\n[RISULTATO SCORE]")
                score_data = score_result["data"]
                if "score" in score_data:
                    score_value = score_data["score"].get("value", "N/A")
                    print(f"Score value: {score_value}")
                print(json.dumps(score_data, indent=2))
            else:
                print(f"\n[ERRORE SCORE] {score_result['error']}: {score_result['message']}")
        else:
            print("\n[INFO] Nessuna spiegazione trovata per questa feature")
    else:
        print(f"\n[ERRORE FEATURE] {feature_result['error']}: {feature_result['message']}")
    
    # Esempio 3: Prova con Gemma
    print("\n" + "=" * 80)
    print("ESEMPIO 3: Genera spiegazione per Gemma-2-2b")
    print("=" * 80)
    
    result = client.generate_explanation(
        model_id="gemma-2-2b",
        layer="6-gemmascope-res-16k",
        index=9220,
        explanation_type="oai_token-act-pair",
        explanation_model="gpt-4o-mini"
    )
    
    if result["success"]:
        print("\n[RISULTATO]")
        print(json.dumps(result["data"], indent=2))
    else:
        print(f"\n[ERRORE] {result['error']}: {result['message']}")
    
    print("\n" + "=" * 80)
    print("Test completati!")
    print("=" * 80)


if __name__ == "__main__":
    main()

