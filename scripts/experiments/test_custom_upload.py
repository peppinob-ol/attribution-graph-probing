#!/usr/bin/env python3
"""
Test minimal per riprodurre "Unknown Source Set" su custom upload.

Prende un grafo locale (generato da circuit-tracer, NON dall'API Neuronpedia)
e lo carica direttamente per vedere se appare "Unknown Source Set".

Uso:
    python scripts/experiments/test_custom_upload.py
"""
import json
import os
import sys
import time

try:
    import requests
except ImportError:
    print("[ERRORE] Modulo 'requests' non trovato. Installa con: pip install requests")
    sys.exit(1)

# ===== CONFIGURAZIONE =====

def load_api_key() -> str:
    """Carica API key da .env o variabile d'ambiente"""
    api_key = os.environ.get('NEURONPEDIA_API_KEY')
    if api_key:
        return api_key
    
    env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
    if os.path.exists(env_path):
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('NEURONPEDIA_API_KEY='):
                        key = line.split('=', 1)[1].strip()
                        key = key.strip('"').strip("'")
                        if key:
                            return key
        except Exception as e:
            print(f"[ATTENZIONE] Errore leggendo .env: {e}")
    
    print("[ERRORE] API key non trovata in .env o variabili d'ambiente.")
    sys.exit(1)

API_KEY = load_api_key()

# File grafo generato dall'API che SICURAMENTE funziona
INPUT_GRAPH = "output/graph_data/test-graph-fox-20251018-230603.json"

# API endpoints
API_BASE = "https://www.neuronpedia.org/api"

# ===== FUNZIONI =====

def prepare_minimal_graph(input_path: str) -> dict:
    """
    Carica un grafo generato dall'API (che FUNZIONA) e cambia SOLO lo slug.
    Mantiene tutti gli altri metadata identici per test pulito.
    """
    print("\n" + "=" * 70)
    print("PREPARAZIONE GRAFO PER RE-UPLOAD (CUSTOM)")
    print("=" * 70)
    
    if not os.path.exists(input_path):
        print(f"\n[ERRORE] File non trovato: {input_path}")
        print("\nEsegui prima:")
        print("  python scripts/experiments/generate_and_analyze_graph.py")
        sys.exit(1)
    
    print(f"\n[1/2] Caricamento grafo FUNZIONANTE dall'API: {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        graph = json.load(f)
    
    nodes = graph.get('nodes', [])
    links = graph.get('links', [])
    metadata = graph.get('metadata', {})
    
    print(f"[OK] Nodi: {len(nodes)}, Links: {len(links)}")
    
    # Stampa metadata originali
    print(f"\n[METADATA ORIGINALI]")
    print(f"   slug: {metadata.get('slug')}")
    print(f"   scan: {metadata.get('scan')}")
    print(f"   modelId: {metadata.get('modelId')}")
    print(f"   sourceSetSlug: {metadata.get('sourceSetSlug', 'N/A')}")
    print(f"   sourceSetName: {metadata.get('sourceSetName', 'N/A')}")
    
    info = metadata.get('info', {})
    print(f"   info.source_urls: {len(info.get('source_urls', []))} URL")
    print(f"   info.transcoder_set: {info.get('transcoder_set', 'N/A')}")
    print(f"   info.creator_name: {info.get('creator_name', 'N/A')}")
    
    # Cambia SOLO lo slug per renderlo unico (custom upload)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    original_slug = metadata.get('slug', 'test-custom')
    new_slug = f"custom-reupload-{timestamp}"
    
    print(f"\n[2/2] Modifica SOLO lo slug per simulare custom upload:")
    print(f"   OLD: {original_slug}")
    print(f"   NEW: {new_slug}")
    
    metadata['slug'] = new_slug
    
    # NON tocchiamo NESSUN altro metadata - devono rimanere identici!
    print(f"\n[IMPORTANTE] Tutti gli altri metadata rimangono IDENTICI!")
    print(f"   Questo isola il test: se ora appare 'Unknown Source Set',")
    print(f"   significa che il problema è il re-upload, non i metadata!")
    
    return graph

def save_prepared_graph(graph: dict, output_path: str):
    """Salva il grafo preparato localmente per debug"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
    
    file_size = os.path.getsize(output_path) / 1024 / 1024
    print(f"\n[OK] Grafo preparato salvato: {output_path}")
    print(f"     Dimensione: {file_size:.2f} MB")

def upload_via_neuronpedia_api(graph: dict):
    """
    Prova a caricare il grafo usando l'API di Neuronpedia.
    
    Nota: Potrebbe non esserci un endpoint specifico per custom upload.
    In tal caso, dobbiamo usare la libreria neuronpedia o il validator UI.
    """
    print("\n" + "=" * 70)
    print("TENTATIVO UPLOAD VIA API")
    print("=" * 70)
    
    # Prova endpoint /api/graph/upload (potrebbe non esistere)
    upload_url = f"{API_BASE}/graph/upload"
    
    print(f"\nTentativo 1: POST a {upload_url}")
    
    try:
        response = requests.post(
            upload_url,
            headers={
                "Content-Type": "application/json",
                "x-api-key": API_KEY
            },
            json=graph,
            timeout=60
        )
        
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:500]}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n[OK] Upload riuscito!")
            return result
        else:
            print(f"\n[INFO] Endpoint non disponibile o errore")
            return None
            
    except Exception as e:
        print(f"   Errore: {e}")
        return None

def upload_via_neuronpedia_lib(file_path: str):
    """
    Carica usando la libreria neuronpedia (se disponibile).
    """
    print("\n" + "=" * 70)
    print("TENTATIVO UPLOAD VIA LIBRERIA NEURONPEDIA")
    print("=" * 70)
    
    try:
        from neuronpedia.np_graph_metadata import NPGraphMetadata
        
        print(f"\n[OK] Libreria neuronpedia trovata")
        print(f"     Caricamento file: {file_path}")
        
        # Imposta API key
        os.environ['NEURONPEDIA_API_KEY'] = API_KEY
        
        # Upload
        graph = NPGraphMetadata.upload_file(file_path)
        
        print(f"\n[OK] Upload completato!")
        print(f"     URL: {graph.url}")
        print(f"     ID: {graph.id}")
        
        return graph
        
    except ImportError:
        print("\n[INFO] Libreria neuronpedia non installata")
        print("      Installa con: pip install neuronpedia")
        return None
    except Exception as e:
        print(f"\n[ERRORE] Upload fallito: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Test completo di custom upload"""
    print("\n" + "=" * 70)
    print("TEST RE-UPLOAD - RIPRODUZIONE 'Unknown Source Set'")
    print("=" * 70)
    print("\n🧪 ESPERIMENTO SCIENTIFICO:")
    print("   1. Prendiamo un grafo generato dall'API che FUNZIONA")
    print("   2. Cambiamo SOLO lo slug")
    print("   3. Lo ricarichiamo come 'custom upload'")
    print("   4. Verifichiamo se appare 'Unknown Source Set'\n")
    print("🎯 IPOTESI:")
    print("   Se appare 'Unknown Source Set' con metadata identici,")
    print("   significa che Neuronpedia tratta diversamente i re-upload!")
    print()
    
    try:
        # Step 1: Prepara grafo (cambia SOLO slug, resto identico)
        graph = prepare_minimal_graph(INPUT_GRAPH)
        
        # Step 2: Salva localmente per debug
        output_path = "output/graph_data/test_custom_upload_prepared.json"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        save_prepared_graph(graph, output_path)
        
        # Step 3: Prova upload via API diretta
        print("\n" + "=" * 70)
        print("STRATEGIA UPLOAD")
        print("=" * 70)
        print("\nProveremo 2 metodi:")
        print("  1. API diretta (POST /api/graph/upload)")
        print("  2. Libreria neuronpedia (NPGraphMetadata.upload_file)")
        
        result_api = upload_via_neuronpedia_api(graph)
        
        if not result_api:
            # Step 4: Prova upload via libreria
            result_lib = upload_via_neuronpedia_lib(output_path)
            
            if result_lib:
                print("\n" + "=" * 70)
                print("RISULTATO ESPERIMENTO")
                print("=" * 70)
                print(f"\n✅ Re-upload riuscito con libreria neuronpedia!")
                print(f"\n📊 VERIFICA IPOTESI:")
                print(f"   1. Grafo originale (funzionante):")
                print(f"      https://www.neuronpedia.org/graph/gemma-2-2b/test-graph-fox-20251018-230603")
                print(f"   2. Grafo re-upload (stesso metadata, slug diverso):")
                print(f"      {result_lib.url}")
                print(f"\n🔬 PROCEDURA TEST:")
                print(f"   1. Apri ENTRAMBI i link nel browser")
                print(f"   2. Confronta il 'Source Set' mostrato:")
                print(f"      - Originale: dovrebbe mostrare 'gemmascope-transcoder-16k'")
                print(f"      - Re-upload: mostra 'Unknown Source Set'? ⚠️")
                print(f"\n💡 INTERPRETAZIONE:")
                print(f"   ✅ Se ENTRAMBI mostrano il source set corretto:")
                print(f"      → Il problema era nei metadata, ora risolto!")
                print(f"   ❌ Se il re-upload mostra 'Unknown Source Set':")
                print(f"      → Neuronpedia tratta diversamente i custom upload")
                print(f"      → Contatta il team per supporto API custom upload")
                print(f"\n📁 File per debug:")
                print(f"   {output_path}")
            else:
                print("\n" + "=" * 70)
                print("UPLOAD NON RIUSCITO")
                print("=" * 70)
                print("\n❌ Nessun metodo di upload ha funzionato.")
                print("\n📝 ALTERNATIVE:")
                print("\n1. Upload manuale via UI:")
                print("   - Vai a: https://www.neuronpedia.org/graph/validator")
                print(f"   - Carica: {output_path}")
                print("   - Verifica se appare 'Unknown Source Set'")
                print("\n2. Contatta il team Neuronpedia per endpoint upload")
        
    except KeyboardInterrupt:
        print("\n\n[INFO] Operazione interrotta dall'utente.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERRORE] Errore inaspettato: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

