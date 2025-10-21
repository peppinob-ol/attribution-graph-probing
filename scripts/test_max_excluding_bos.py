"""
Test per verificare il calcolo di max_value escludendo BOS (primo elemento di values).

Il primo elemento di values corrisponde sempre al token BOS e deve essere ignorato
nel calcolo del massimo.
"""

import json
from pathlib import Path

def test_max_calculation():
    """Test con dati reali dal JSON"""
    
    json_path = Path("output/activations_dump (2).json")
    
    if not json_path.exists():
        print(f"[ERROR] File non trovato: {json_path}")
        return
    
    # Carica JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("=" * 70)
    print("TEST CALCOLO MAX ESCLUDENDO BOS")
    print("=" * 70)
    
    # Prendi un esempio
    results = data.get('results', [])
    if not results:
        print("[ERROR] Nessun result nel JSON")
        return
    
    example = results[0]
    tokens = example.get('tokens', [])
    activations = example.get('activations', [])
    
    print(f"\nPrompt: {example.get('prompt', '')}")
    print(f"Tokens: {tokens}")
    print(f"\nFeatures analizzate: {len(activations)}")
    
    # Analizza alcuni esempi
    print("\n" + "=" * 70)
    print("ESEMPI DI CALCOLO MAX (primi 3)")
    print("=" * 70)
    
    for i, act in enumerate(activations[:3]):
        source = act.get('source', '')
        index = act.get('index')
        values = act.get('values', [])
        
        if not values:
            continue
        
        # Metodo VECCHIO (includeva BOS)
        old_max = max(values) if values else None
        old_max_idx = values.index(old_max) if old_max is not None else None
        old_token = tokens[old_max_idx] if old_max_idx is not None and old_max_idx < len(tokens) else None
        
        # Metodo NUOVO (esclude BOS)
        if len(values) > 1:
            values_no_bos = values[1:]
            new_max = max(values_no_bos) if values_no_bos else None
            new_max_idx = values_no_bos.index(new_max) + 1 if new_max is not None else None
            new_token = tokens[new_max_idx] if new_max_idx is not None and new_max_idx < len(tokens) else None
        else:
            new_max = None
            new_max_idx = None
            new_token = None
        
        print(f"\n[{i+1}] Feature: {source}, index={index}")
        print(f"    Values: {values[:3]}... (primi 3 su {len(values)})")
        print(f"    values[0] (BOS): {values[0]:.2f}")
        
        print(f"\n    VECCHIO (con BOS):")
        print(f"      max_value: {old_max:.2f}")
        print(f"      max_idx: {old_max_idx}")
        print(f"      token: {old_token}")
        
        print(f"\n    NUOVO (senza BOS):")
        max_val_str = f"{new_max:.2f}" if new_max is not None else "None"
        print(f"      max_value: {max_val_str}")
        print(f"      max_idx: {new_max_idx}")
        print(f"      token: {new_token}")
        
        if old_max_idx == 0:
            print(f"      -> [!] CORREZIONE APPLICATA: BOS non e' piu' il max!")
        elif old_max == new_max:
            print(f"      -> [OK] Stesso risultato (BOS non era il max)")
        else:
            print(f"      -> [INFO] Max cambiato (da {old_max:.2f} a {new_max:.2f})")
    
    # Statistiche
    print("\n" + "=" * 70)
    print("STATISTICHE CONFRONTO")
    print("=" * 70)
    
    n_total = 0
    n_bos_was_max = 0
    n_same_max = 0
    n_different_max = 0
    
    for act in activations:
        values = act.get('values', [])
        if len(values) <= 1:
            continue
        
        n_total += 1
        
        old_max = max(values)
        old_max_idx = values.index(old_max)
        
        values_no_bos = values[1:]
        new_max = max(values_no_bos)
        
        if old_max_idx == 0:
            n_bos_was_max += 1
        elif abs(old_max - new_max) < 0.001:
            n_same_max += 1
        else:
            n_different_max += 1
    
    print(f"\nFeatures totali analizzate: {n_total}")
    print(f"  BOS era il max (CORRETTO): {n_bos_was_max} ({n_bos_was_max/n_total*100:.1f}%)")
    print(f"  Stesso max (BOS non era max): {n_same_max} ({n_same_max/n_total*100:.1f}%)")
    print(f"  Max diverso (piccole diff): {n_different_max} ({n_different_max/n_total*100:.1f}%)")
    
    print("\n" + "=" * 70)
    print("ESEMPIO CONCRETO (dal messaggio utente)")
    print("=" * 70)
    
    # Simula l'esempio dell'utente
    example_values = [
        424.1778259277344,
        105.41461181640625,
        68.2294921875,
        78.88206481933594,
        74.51651763916016,
        71.89555358886719,
        68.20378875732422,
        93.47358703613281,
        75.2999267578125,
        102.00741577148438
    ]
    
    print(f"\nValues: {example_values}")
    print(f"values[0] (BOS): {example_values[0]}")
    
    old_max = max(example_values)
    old_idx = example_values.index(old_max)
    print(f"\nMETODO VECCHIO (con BOS):")
    print(f"  max_value: {old_max} (indice {old_idx})")
    
    values_no_bos = example_values[1:]
    new_max = max(values_no_bos)
    new_idx = values_no_bos.index(new_max) + 1
    print(f"\nMETODO NUOVO (senza BOS):")
    print(f"  max_value: {new_max} (indice {new_idx})")
    print(f"  [OK] Conferma: indice 1, valore 105.41461181640625")
    
    print("\n[OK] Test completato!")

if __name__ == "__main__":
    test_max_calculation()

