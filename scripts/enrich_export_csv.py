#!/usr/bin/env python3
"""
Script per arricchire il CSV di export con metriche di attivazione calcolate dal JSON.

Calcola per ogni riga (feature × prompt):
- activation_max: massimo escludendo BOS
- activation_sum: somma escludendo BOS  
- activation_mean: media escludendo BOS
- sparsity_ratio: (max - mean) / max
"""

import json
import pandas as pd
from pathlib import Path
import sys

def calculate_metrics(values):
    """Calcola metriche di attivazione escludendo BOS (primo elemento)."""
    if len(values) <= 1:
        return {
            'activation_max': 0.0,
            'activation_sum': 0.0,
            'activation_mean': 0.0,
            'sparsity_ratio': 0.0
        }
    
    # Escludi BOS (index 0)
    values_no_bos = values[1:]
    
    max_val = max(values_no_bos) if values_no_bos else 0.0
    sum_val = sum(values_no_bos) if values_no_bos else 0.0
    mean_val = sum_val / len(values_no_bos) if values_no_bos else 0.0
    
    # Sparsity: quanto è concentrata l'attivazione
    # 0 = uniforme, 1 = molto sparsa
    if max_val > 0:
        sparsity = (max_val - mean_val) / max_val
    else:
        sparsity = 0.0
    
    return {
        'activation_max': max_val,
        'activation_sum': sum_val,
        'activation_mean': mean_val,
        'sparsity_ratio': sparsity
    }

def main():
    # Percorsi
    project_root = Path(__file__).parent.parent
    csv_input = project_root / "output" / "2025-10-21T07-40_export.csv"
    json_input = project_root / "output" / "activations_dump (2).json"
    csv_output = project_root / "output" / "2025-10-21T07-40_export_ENRICHED.csv"
    
    print(f"Caricamento dati...")
    print(f"  CSV: {csv_input}")
    print(f"  JSON: {json_input}")
    
    # Carica CSV
    df = pd.read_csv(csv_input, encoding='utf-8')
    print(f"CSV caricato: {len(df)} righe")
    
    # Carica JSON
    with open(json_input, 'r', encoding='utf-8') as f:
        json_data = json.load(f)
    print(f"JSON caricato: {len(json_data['results'])} prompts")
    
    # Crea dizionario di lookup: (source, index, prompt) -> values
    # e anche un dizionario per matching parziale: (source, index) -> {prompt: values}
    print(f"Creazione indice attivazioni...")
    activations_lookup = {}
    activations_by_source_index = {}
    
    for result in json_data['results']:
        prompt = result['prompt']
        
        for act in result['activations']:
            source = act['source']
            index = act['index']
            values = act['values']
            
            # Crea chiave univoca per matching esatto
            key = (source, index, prompt)
            activations_lookup[key] = values
            
            # Crea anche dizionario per matching parziale
            key_partial = (source, index)
            if key_partial not in activations_by_source_index:
                activations_by_source_index[key_partial] = {}
            activations_by_source_index[key_partial][prompt] = values
    
    print(f"Indicizzate {len(activations_lookup)} combinazioni (source, index, prompt)")
    
    # Calcola metriche per ogni riga del CSV
    print(f"Calcolo metriche...")
    
    new_metrics = []
    matched = 0
    not_matched = 0
    
    for idx, row in df.iterrows():
        source = row['source']
        index = int(row['index'])
        prompt = row['prompt']
        
        # Cerca prima con matching esatto
        key = (source, index, prompt)
        
        if key in activations_lookup:
            values = activations_lookup[key]
            metrics = calculate_metrics(values)
            matched += 1
        else:
            # Prova con matching parziale (substring)
            # Il prompt nel CSV potrebbe essere troncato con "..."
            key_partial = (source, index)
            found = False
            
            if key_partial in activations_by_source_index:
                prompt_csv = prompt.rstrip('.')  # Rimuovi "..." finale se presente
                
                # Cerca un prompt nel JSON che inizi con il prompt del CSV
                for json_prompt, values in activations_by_source_index[key_partial].items():
                    if json_prompt.startswith(prompt_csv):
                        metrics = calculate_metrics(values)
                        matched += 1
                        found = True
                        break
            
            if not found:
                # Non trovato nemmeno con substring, usa valori di default
                metrics = {
                    'activation_max': 0.0,
                    'activation_sum': 0.0,
                    'activation_mean': 0.0,
                    'sparsity_ratio': 0.0
                }
                not_matched += 1
                print(f"WARN Riga {idx}: non trovata attivazione per {source}/{index}/{prompt[:30]}...")
        
        new_metrics.append(metrics)
    
    # Aggiorna DataFrame con le nuove colonne
    print(f"Aggiornamento DataFrame...")
    
    # Rimuovi vecchie colonne se esistono
    cols_to_remove = ['activation_max', 'activation_sum']
    df = df.drop(columns=[c for c in cols_to_remove if c in df.columns], errors='ignore')
    
    # Aggiungi nuove colonne
    df['activation_max'] = [m['activation_max'] for m in new_metrics]
    df['activation_sum'] = [m['activation_sum'] for m in new_metrics]
    df['activation_mean'] = [m['activation_mean'] for m in new_metrics]
    df['sparsity_ratio'] = [m['sparsity_ratio'] for m in new_metrics]
    
    # Riordina colonne per leggibilità
    cols_order = ['feature_key', 'layer', 'index', 'source', 'prompt',
                  'activation_max', 'activation_sum', 'activation_mean', 'sparsity_ratio',
                  'peak_token', 'peak_token_idx', 'node_influence', 'csv_ctx_idx']
    
    # Usa solo colonne che esistono
    cols_order = [c for c in cols_order if c in df.columns]
    
    # Aggiungi colonne rimanenti che non sono in cols_order
    remaining_cols = [c for c in df.columns if c not in cols_order]
    final_cols = cols_order + remaining_cols
    
    df = df[final_cols]
    
    # Salva
    print(f"Salvataggio CSV arricchito...")
    df.to_csv(csv_output, index=False, encoding='utf-8')
    
    print(f"""
COMPLETATO!

Statistiche:
  - Righe processate: {len(df)}
  - Match trovati: {matched}
  - Non trovati: {not_matched}
  
File salvato: {csv_output.relative_to(project_root)}

Metriche aggiunte:
  - activation_max: massimo escludendo BOS
  - activation_sum: somma escludendo BOS
  - activation_mean: media escludendo BOS  
  - sparsity_ratio: (max - mean) / max [0=uniforme, 1=sparsa]
""")
    
    # Mostra statistiche metriche
    print("Statistiche Metriche:")
    print(f"  activation_max - media: {df['activation_max'].mean():.2f}, range: [{df['activation_max'].min():.2f}, {df['activation_max'].max():.2f}]")
    print(f"  activation_sum - media: {df['activation_sum'].mean():.2f}, range: [{df['activation_sum'].min():.2f}, {df['activation_sum'].max():.2f}]")
    print(f"  activation_mean - media: {df['activation_mean'].mean():.2f}, range: [{df['activation_mean'].min():.2f}, {df['activation_mean'].max():.2f}]")
    print(f"  sparsity_ratio - media: {df['sparsity_ratio'].mean():.3f}, range: [{df['sparsity_ratio'].min():.3f}, {df['sparsity_ratio'].max():.3f}]")
    
    avg_sparsity = df['sparsity_ratio'].mean()
    if avg_sparsity > 0.7:
        print(f"  => Features molto sparse (avg sparsity: {avg_sparsity:.3f})")
    elif avg_sparsity > 0.4:
        print(f"  => Sparsity moderata (avg sparsity: {avg_sparsity:.3f})")
    else:
        print(f"  => Features distribuite (avg sparsity: {avg_sparsity:.3f})")

if __name__ == "__main__":
    main()

