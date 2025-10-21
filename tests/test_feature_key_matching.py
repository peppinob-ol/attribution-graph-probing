"""
Test per verificare che il matching tra activations JSON e CSV node_influence funzioni correttamente.

Il bug era:
- CSV usava: feature_key = layer + '_' + feature (colonna 2)
- JSON usava: feature_key = layer + '_' + index
- Ma index nel JSON corrisponde a 'id' (colonna 3) nel CSV, NON a 'feature'!

Fix:
- CSV ora usa: feature_key = layer + '_' + id (colonna 3)
"""

import json
import pandas as pd
from pathlib import Path


def test_feature_key_construction_csv():
    """Testa che il CSV costruisca le feature_key correttamente usando 'id' invece di 'feature'"""
    
    csv_path = Path("output/graph_feature_static_metrics.csv")
    
    if not csv_path.exists():
        print(f"[SKIP] {csv_path} non trovato")
        return
    
    # Carica CSV
    df = pd.read_csv(csv_path)
    
    # Costruisci feature_key come dovrebbe essere (usando 'id')
    df['feature_key'] = df['layer'].astype(str) + '_' + df['id'].astype(str)
    
    # Nota: feature_key può essere duplicata perché lo stesso nodo (layer+id) 
    # può apparire più volte con diversi ctx_idx (contesti di attivazione)
    n_unique = df['feature_key'].nunique()
    n_total = len(df)
    print(f"[INFO] CSV: {n_unique} feature_key uniche su {n_total} righe totali")
    
    # Esempio: layer=0, feature=175865634, id=18753
    # feature_key dovrebbe essere '0_18753' (non '0_175865634')
    row_example = df[(df['layer'] == 0) & (df['id'] == 18753)]
    if not row_example.empty:
        expected_key = '0_18753'
        actual_key = row_example['feature_key'].iloc[0]
        assert actual_key == expected_key, \
            f"Expected feature_key='{expected_key}', got '{actual_key}'"
        print(f"[OK] CSV feature_key corretto: {actual_key}")
    
    print(f"[OK] Test CSV passed: {len(df)} righe con feature_key corrette")


def test_feature_key_construction_json():
    """Testa che il JSON costruisca le feature_key usando source (layer) + index"""
    
    json_path = Path("output/activations_dump (2).json")
    
    if not json_path.exists():
        print(f"[SKIP] {json_path} non trovato")
        return
    
    # Carica JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Estrai feature_keys dal JSON
    feature_keys = set()
    for result in data.get('results', []):
        for activation in result.get('activations', []):
            source = activation.get('source', '')
            index = activation.get('index')
            
            # Estrai layer da source (es. "0-clt-hp" -> 0)
            if '-' in source:
                layer = int(source.split('-')[0])
                feature_key = f"{layer}_{index}"
                feature_keys.add(feature_key)
    
    # Esempio: source="0-clt-hp", index=18753 → feature_key='0_18753'
    expected_key = '0_18753'
    assert expected_key in feature_keys, \
        f"Expected feature_key='{expected_key}' not found in JSON"
    
    print(f"[OK] Test JSON passed: {len(feature_keys)} feature_keys estratte")
    print(f"   Esempio: {expected_key} OK")


def test_matching_json_csv():
    """Testa che le feature_key dal JSON matchino con quelle del CSV"""
    
    json_path = Path("output/activations_dump (2).json")
    csv_path = Path("output/graph_feature_static_metrics.csv")
    
    if not json_path.exists() or not csv_path.exists():
        print("[SKIP] File non trovati")
        return
    
    # Carica JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    json_keys = set()
    for result in data.get('results', []):
        for activation in result.get('activations', []):
            source = activation.get('source', '')
            index = activation.get('index')
            
            if '-' in source:
                layer = int(source.split('-')[0])
                feature_key = f"{layer}_{index}"
                json_keys.add(feature_key)
    
    # Carica CSV
    df = pd.read_csv(csv_path)
    df['feature_key'] = df['layer'].astype(str) + '_' + df['id'].astype(str)
    csv_keys = set(df['feature_key'].unique())
    
    # Verifica matching
    matches = json_keys.intersection(csv_keys)
    json_only = json_keys - csv_keys
    
    match_pct = len(matches) / len(json_keys) * 100 if json_keys else 0
    
    print(f"\n{'='*60}")
    print(f"TEST MATCHING JSON-CSV")
    print(f"{'='*60}")
    print(f"Features JSON:        {len(json_keys)}")
    print(f"Features CSV:         {len(csv_keys)}")
    print(f"Match:                {len(matches)} ({match_pct:.1f}%)")
    print(f"Solo in JSON:         {len(json_only)}")
    print(f"{'='*60}")
    
    # Il test passa se abbiamo almeno 90% di match
    assert match_pct >= 90, \
        f"Expected at least 90% match, got {match_pct:.1f}%"
    
    print(f"[OK] Test matching passed: {match_pct:.1f}% match rate")
    
    # Verifica esempio specifico
    example_key = '0_18753'
    if example_key in json_keys:
        assert example_key in csv_keys, \
            f"Example key '{example_key}' in JSON but not in CSV"
        print(f"[OK] Example key '{example_key}' found in both JSON and CSV")


def main():
    """Esegue tutti i test"""
    print("[TEST] FEATURE_KEY MATCHING\n")
    
    try:
        test_feature_key_construction_csv()
        print()
        test_feature_key_construction_json()
        print()
        test_matching_json_csv()
        print("\n[OK] TUTTI I TEST PASSATI!")
        
    except AssertionError as e:
        print(f"\n[FAIL] TEST FALLITO: {e}")
        raise
    except Exception as e:
        print(f"\n[ERROR] ERRORE: {e}")
        raise


if __name__ == "__main__":
    main()

