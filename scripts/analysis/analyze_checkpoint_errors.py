#!/usr/bin/env python3
"""
Script per analizzare i checkpoint di probe_prompts e stimare gli errori.

Uso:
    python scripts/analysis/analyze_checkpoint_errors.py [checkpoint_path]
"""

import sys
import json
from pathlib import Path
from typing import Dict

def analyze_checkpoint(checkpoint_path: str):
    """Analizza un checkpoint e stima il numero di errori"""
    
    checkpoint_file = Path(checkpoint_path)
    
    if not checkpoint_file.exists():
        print(f"[ERROR] File non trovato: {checkpoint_path}")
        return
    
    print("=" * 80)
    print(f"ANALISI CHECKPOINT: {checkpoint_file.name}")
    print("=" * 80)
    
    with open(checkpoint_file, 'r', encoding='utf-8') as f:
        checkpoint_data = json.load(f)
    
    records = checkpoint_data.get("records", [])
    metadata = checkpoint_data.get("metadata", {})
    timestamp = checkpoint_data.get("timestamp", "unknown")
    
    print(f"\n[TIMESTAMP] {timestamp}")
    print(f"\n[STATS] Statistiche generali:")
    print(f"   Records salvati: {len(records)}")
    
    if metadata:
        print(f"\n[METADATA] Metadata:")
        for key, value in metadata.items():
            print(f"   {key}: {value}")
    
    # Calcola statistiche errori se disponibili
    if "error_counts" in metadata:
        error_counts = metadata["error_counts"]
        total_errors = metadata.get("total_errors", sum(error_counts.values()))
        
        print(f"\n[ERRORS] Statistiche errori (NUOVO formato con tracking):")
        print(f"   Totale errori: {total_errors}")
        print(f"   Successi: {len(records)}")
        total_attempts = len(records) + total_errors
        success_rate = (len(records) / total_attempts * 100) if total_attempts > 0 else 0
        print(f"   Tasso successo: {success_rate:.2f}%")
        
        print(f"\n   Dettaglio per tipo:")
        for error_type, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                pct = (count / total_errors * 100) if total_errors > 0 else 0
                print(f"      - {error_type}: {count} ({pct:.1f}%)")
    
    else:
        # Checkpoint vecchio formato - stima errori
        total_calls = metadata.get("total_calls", 0)
        skipped = metadata.get("skipped", 0)
        
        if total_calls > 0:
            estimated_errors = total_calls - len(records) - skipped
            
            print(f"\n[WARNING] Statistiche errori (STIMATO - vecchio formato senza tracking):")
            print(f"   Chiamate totali tentate: {total_calls}")
            print(f"   Skipped (da checkpoint): {skipped}")
            print(f"   Successi: {len(records)}")
            print(f"   Errori stimati: {estimated_errors}")
            
            if estimated_errors > 0:
                success_rate = (len(records) / total_calls * 100) if total_calls > 0 else 0
                error_rate = (estimated_errors / total_calls * 100) if total_calls > 0 else 0
                
                print(f"\n   [RATES] Tassi:")
                print(f"      Successo: {success_rate:.2f}%")
                print(f"      Errori: {error_rate:.2f}%")
                print(f"      Skip: {skipped/total_calls*100:.2f}%")
                
                print(f"\n   [NOTE] Con {estimated_errors} errori su {total_calls} chiamate,")
                print(f"      il tasso di errore e' molto alto ({error_rate:.1f}%)!")
                print(f"      Possibili cause:")
                print(f"         - Server Neuronpedia instabile o in manutenzione")
                print(f"         - Rate limiting aggressivo (nessuna/poca API key)")
                print(f"         - Features non disponibili pubblicamente")
                print(f"         - Source format errato per alcune features")
    
    # Analisi features processate
    if records:
        print(f"\n[FEATURES] Analisi features processate:")
        
        # Estrai features uniche
        unique_features = set()
        unique_layers = set()
        unique_labels = set()
        
        for rec in records:
            unique_features.add((rec.get("layer"), rec.get("feature")))
            unique_layers.add(rec.get("layer"))
            unique_labels.add(rec.get("label"))
        
        print(f"   Concepts unici: {len(unique_labels)}")
        print(f"   Features uniche: {len(unique_features)}")
        print(f"   Layer unici: {sorted(unique_layers)}")
        
        # Mostra distribuzione
        if len(unique_features) < 20:
            print(f"\n   Features processate:")
            for layer, feature in sorted(unique_features):
                count = sum(1 for r in records if r.get("layer") == layer and r.get("feature") == feature)
                print(f"      Layer {layer}, Feature {feature}: {count} concepts")
    
    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        checkpoint_path = sys.argv[1]
    else:
        # Usa l'ultimo checkpoint come default
        checkpoint_dir = Path(__file__).parent.parent.parent / "output" / "checkpoints"
        
        if checkpoint_dir.exists():
            checkpoints = sorted(checkpoint_dir.glob("probe_prompts_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            
            if checkpoints:
                print(f"[INFO] Nessun checkpoint specificato, uso l'ultimo disponibile\n")
                checkpoint_path = str(checkpoints[0])
            else:
                print("[ERROR] Nessun checkpoint trovato in output/checkpoints/")
                sys.exit(1)
        else:
            print("[ERROR] Directory checkpoints non trovata")
            sys.exit(1)
    
    analyze_checkpoint(checkpoint_path)

