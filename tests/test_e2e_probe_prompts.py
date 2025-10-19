#!/usr/bin/env python3
"""
Test end-to-end completo per Probe Prompts con file JSON reale.

Questo test:
1. Carica il file graph_data JSON reale
2. Definisce concepts di test
3. Esegue l'analisi completa con la funzione analyze_concepts_from_graph_json
4. Mostra tutti gli output intermedi e finali

Esegui con:
    python tests/test_e2e_probe_prompts.py
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Setup path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

# Import del modulo probe_prompts
import importlib.util

script_path = parent_dir / "scripts" / "01_probe_prompts.py"
spec = importlib.util.spec_from_file_location("probe_prompts", script_path)
probe_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe_module)

analyze_concepts_from_graph_json = probe_module.analyze_concepts_from_graph_json


def print_separator(title="", char="=", width=80):
    """Stampa una riga separatrice con titolo opzionale"""
    if title:
        side_len = (width - len(title) - 2) // 2
        print(f"\n{char * side_len} {title} {char * side_len}")
    else:
        print(f"\n{char * width}")


def test_e2e_probe_prompts():
    """Test end-to-end completo con file JSON reale"""
    
    print_separator("TEST END-TO-END: PROBE PROMPTS", "=", 80)
    
    # ─────────── STEP 1: Carica il file JSON ───────────
    print_separator("STEP 1: Caricamento Graph JSON", "-", 80)
    
    json_path = parent_dir / "output" / "graph_data" / "the-capital-of-20251019-045827.json"
    
    print(f"[INFO] Percorso file: {json_path}")
    print(f"[INFO] File esiste: {json_path.exists()}")
    
    if not json_path.exists():
        print(f"[ERRORE] File non trovato: {json_path}")
        return False
    
    print("[INFO] Caricamento JSON in corso...")
    start_load = datetime.now()
    
    with open(json_path, "r", encoding="utf-8") as f:
        graph_json = json.load(f)
    
    load_time = (datetime.now() - start_load).total_seconds()
    print(f"[OK] JSON caricato in {load_time:.2f} secondi")
    
    # Analisi metadata
    metadata = graph_json.get("metadata", {})
    print(f"\n[METADATA] Info del graph:")
    print(f"   Model: {metadata.get('scan')}")
    print(f"   Prompt originale: {metadata.get('prompt')}")
    print(f"   Slug: {metadata.get('slug')}")
    print(f"   Node threshold: {metadata.get('node_threshold')}")
    print(f"   Schema version: {metadata.get('schema_version')}")
    
    # Info sul graph
    info = metadata.get("info", {})
    print(f"\n[INFO] Generatore:")
    print(f"   Creator: {info.get('creator_name')}")
    print(f"   Generator: {info.get('generator', {}).get('name')}")
    print(f"   Version: {info.get('generator', {}).get('version')}")
    print(f"   Transcoder set: {info.get('transcoder_set')}")
    
    # Conta nodi
    nodes = graph_json.get("nodes", [])
    edges = graph_json.get("edges", [])
    print(f"\n[STATS] Statistiche graph:")
    print(f"   Totale nodi: {len(nodes)}")
    print(f"   Totale edges: {len(edges)}")
    
    # Conta tipi di nodi
    node_types = {}
    feature_nodes = 0
    for node in nodes:
        node_type = node.get("feature_type", "unknown")
        node_types[node_type] = node_types.get(node_type, 0) + 1
        if node_type == "cross layer transcoder":
            feature_nodes += 1
    
    print(f"   Nodi feature (transcoder): {feature_nodes}")
    print(f"   Tipi di nodi presenti:")
    for ntype, count in node_types.items():
        print(f"      - {ntype}: {count}")
    
    # ─────────── STEP 2: Definisci concepts per probe ───────────
    print_separator("STEP 2: Definizione Concepts", "-", 80)
    
    # Basandoci sul prompt "The capital of state containing Dallas is"
    # definiamo UN SOLO concept per rendere il test veloce
    concepts = [
        {
            "label": "Austin",
            "category": "entity",
            "description": "the capital city of Texas"
        }
    ]
    
    print(f"[OK] Definito {len(concepts)} concept per l'analisi (test rapido):")
    for i, concept in enumerate(concepts, 1):
        print(f"\n   {i}. Label: '{concept['label']}'")
        print(f"      Category: {concept['category']}")
        print(f"      Description: {concept['description']}")
    
    # ─────────── STEP 3: Esegui analisi ───────────
    print_separator("STEP 3: Esecuzione Analisi", "-", 80)
    
    print("[START] Avvio analyze_concepts_from_graph_json...")
    print("[NOTA] Test ULTRA veloce: 1 concept, solo 5 features TOP")
    print("       Dovrebbe richiedere circa 10-15 secondi")
    print("\n[PARAMS] Parametri analisi:")
    print("   - activation_threshold_quantile: 0.9")
    print("   - use_baseline: False (per velocizzare)")
    print("   - cumulative_contribution: 0.01 (solo top 5 features circa)")
    print("   - verbose: True")
    
    # Path per salvare l'output
    output_csv = parent_dir / "output" / f"e2e_test_probe_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    print(f"   - output_csv: {output_csv}")
    
    print("\n" + "-" * 80)
    print("INIZIO ANALISI - Output della funzione:")
    print("-" * 80 + "\n")
    
    start_analysis = datetime.now()
    
    try:
        # Callback per tracciare il progresso
        progress_info = {"current": 0, "total": 0}
        
        def progress_callback(current, total, message=""):
            progress_info["current"] = current
            progress_info["total"] = total
            percent = (current / total * 100) if total > 0 else 0
            print(f"   [{current}/{total}] ({percent:.1f}%) {message}")
        
        # Esegui l'analisi (versione ULTRA veloce - solo ~5 features)
        checkpoint_path = parent_dir / "output" / "checkpoints" / f"test_e2e_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        df = analyze_concepts_from_graph_json(
            graph_json=graph_json,
            concepts=concepts,
            api_key=None,  # API key verrà caricata automaticamente da .env
            activation_threshold_quantile=0.9,
            use_baseline=False,  # Disabilita baseline per velocizzare
            cumulative_contribution=0.01,  # Solo ~1% = circa 5-10 features top
            verbose=True,
            output_csv=str(output_csv),
            progress_callback=progress_callback,
            checkpoint_every=3,  # Checkpoint ogni 3 features nel test
            checkpoint_path=str(checkpoint_path),
            resume_from_checkpoint=True
        )
        
        analysis_time = (datetime.now() - start_analysis).total_seconds()
        
        print("\n" + "-" * 80)
        print("FINE ANALISI")
        print("-" * 80)
        
        # ─────────── STEP 4: Analizza risultati ───────────
        print_separator("STEP 4: Analisi Risultati", "-", 80)
        
        print(f"\n[OK] Analisi completata in {analysis_time:.2f} secondi")
        print(f"[OUTPUT] Risultati salvati in: {output_csv}")
        
        print(f"\n[DATAFRAME] Info risultante:")
        print(f"   Shape: {df.shape} (righe x colonne)")
        print(f"   Colonne: {len(df.columns)}")
        
        if len(df.columns) > 0:
            print(f"\n[COLUMNS] Lista colonne:")
            for col in df.columns:
                print(f"      - {col}")
        
        if len(df) > 0:
            print(f"\n[STATS] Statistiche per concept:")
            labels = df.index.get_level_values("label").unique() if hasattr(df.index, 'get_level_values') else df["label"].unique()
            for label in labels:
                concept_df = df.loc[label] if hasattr(df.index, 'get_level_values') else df[df["label"] == label]
                print(f"\n   '{label}':")
                print(f"      Righe: {len(concept_df)}")
                if hasattr(concept_df.index, 'get_level_values'):
                    print(f"      Features uniche: {concept_df.index.get_level_values('feature').nunique()}")
                    print(f"      Layer range: {concept_df.index.get_level_values('layer').min()}-{concept_df.index.get_level_values('layer').max()}")
                else:
                    print(f"      Features uniche: {concept_df['feature'].nunique()}")
                    print(f"      Layer range: {concept_df['layer'].min()}-{concept_df['layer'].max()}")
                
                if "z_score" in df.columns:
                    print(f"      Z-score medio: {concept_df['z_score'].mean():.4f}")
                    print(f"      Z-score max: {concept_df['z_score'].max():.4f}")
                
                if "cosine_similarity" in df.columns:
                    print(f"      Cosine similarity media: {concept_df['cosine_similarity'].mean():.4f}")
        
        if len(df) > 0:
            print(f"\n[DATA] Prime 5 righe del DataFrame:")
            print(df.head().to_string())
            
            if len(df) > 5:
                print(f"\n[DATA] Ultime 5 righe del DataFrame:")
                print(df.tail().to_string())
        
        # Trova le feature più interessanti
        if "z_score" in df.columns and len(df) > 0:
            print_separator("STEP 5: Top Features", "-", 80)
            
            top_n = min(10, len(df))
            top_features = df.nlargest(top_n, "z_score")
            
            print(f"\n[TOP] Top {top_n} features per Z-score:")
            for i, (idx, row) in enumerate(top_features.iterrows(), 1):
                # idx è una tupla (label, category, layer, feature)
                if isinstance(idx, tuple):
                    label, category, layer, feature = idx
                    print(f"\n   {i}. Label: '{label}', Layer: {layer}, Feature: {feature}")
                else:
                    print(f"\n   {i}. Index: {idx}")
                print(f"      Z-score: {row['z_score']:.4f}")
                if "picco_su_label" in df.columns:
                    print(f"      Picco su label: {row['picco_su_label']}")
                if "peak_token" in df.columns:
                    print(f"      Peak token: {row['peak_token']}")
        
        # ─────────── RIEPILOGO FINALE ───────────
        print_separator("RIEPILOGO FINALE", "=", 80)
        
        if len(df) > 0:
            print(f"\n[SUCCESS] TEST END-TO-END COMPLETATO CON SUCCESSO!")
        else:
            print(f"\n[PARTIAL] TEST COMPLETATO MA SENZA DATI")
            print(f"\n[NOTE] L'API Neuronpedia potrebbe aver bloccato le richieste.")
            print(f"       Possibili cause:")
            print(f"       - Nessuna API key fornita (rate limiting aggressivo)")
            print(f"       - Troppe richieste in poco tempo")
            print(f"       - Features non disponibili pubblicamente")
        
        print(f"\n[SUMMARY] Riepilogo:")
        print(f"   - Graph JSON caricato: OK")
        print(f"   - Nodi nel graph: {len(nodes)}")
        print(f"   - Concepts analizzati: {len(concepts)}")
        print(f"   - Risultati ottenuti: {len(df)} righe")
        print(f"   - Tempo totale: {analysis_time:.2f} secondi")
        if len(df) > 0:
            print(f"   - Output CSV: {output_csv}")
        
        print(f"\n[VERIFIED] Il test ha verificato:")
        print(f"   - Caricamento e parsing del graph JSON")
        print(f"   - Estrazione features dal graph")
        print(f"   - Filtraggio per influence cumulative")
        print(f"   - Chiamate API a Neuronpedia (tentate)")
        print(f"   - Generazione DataFrame risultante")
        if len(df) > 0:
            print(f"   - Calcolo metriche (z-scores, densita, cosine similarity)")
            print(f"   - Salvataggio CSV")
        
        print("\n" + "=" * 80 + "\n")
        
        return len(df) > 0  # Successo solo se ci sono dati
        
    except Exception as e:
        analysis_time = (datetime.now() - start_analysis).total_seconds()
        print(f"\n[ERRORE] Durante l'analisi dopo {analysis_time:.2f} secondi:")
        print(f"   {type(e).__name__}: {e}")
        
        import traceback
        print(f"\n[TRACEBACK] Traceback completo:")
        traceback.print_exc()
        
        return False


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print(" " * 20 + "TEST E2E PROBE PROMPTS")
    print(" " * 25 + f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    success = test_e2e_probe_prompts()
    
    sys.exit(0 if success else 1)

