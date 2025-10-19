#!/usr/bin/env python3
"""
Script di test per estrarre metriche statiche da JSON esistente.

Uso:
    python scripts/test_extract_metrics.py
"""
import sys
from pathlib import Path
import importlib.util

# Carica modulo direttamente
script_path = Path(__file__).parent / "00_neuronpedia_graph_generation.py"
spec = importlib.util.spec_from_file_location("neuronpedia_graph_generation", script_path)
graph_gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(graph_gen)

generate_static_metrics_csv = graph_gen.generate_static_metrics_csv

def main():
    """Test estrazione metriche"""
    
    # Trova il JSON più recente in output/graph_data
    json_dir = Path("output/graph_data")
    
    if not json_dir.exists():
        print(f"[ERRORE] Directory {json_dir} non trovata!")
        return
    
    json_files = sorted(json_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not json_files:
        print(f"[ERRORE] Nessun file JSON trovato in {json_dir}")
        return
    
    # Usa il più recente
    json_path = json_files[0]
    print(f"[OK] File JSON trovato: {json_path}")
    print(f"     Dimensione: {json_path.stat().st_size / (1024*1024):.2f} MB\n")
    
    # Estrai metriche
    csv_output = "output/graph_feature_static_metrics.csv"
    
    print("Estrazione metriche in corso...")
    df = generate_static_metrics_csv(
        str(json_path),
        csv_output,
        verbose=True
    )
    
    if df is not None:
        print(f"\n[OK] SUCCESSO! CSV salvato in: {csv_output}")
        print(f"\n[INFO] Preview dati:")
        print(df.head(10))
    else:
        print("\n[ERRORE] Estrazione fallita!")

if __name__ == "__main__":
    main()

