"""
Test per dimostrare come funziona il max(node_influence) per feature_key.

Una stessa feature_key può apparire più volte nel CSV con diversi ctx_idx,
e quindi con diversi valori di node_influence.

Per il grafico usiamo il valore massimo.
"""

import pandas as pd
from pathlib import Path

def main():
    csv_path = Path("output/graph_feature_static_metrics.csv")
    
    if not csv_path.exists():
        print(f"[ERROR] File non trovato: {csv_path}")
        return
    
    # Carica CSV
    df = pd.read_csv(csv_path)
    df['feature_key'] = df['layer'].astype(str) + '_' + df['id'].astype(str)
    
    # Trova features con più di una riga (diversi ctx_idx)
    feature_counts = df['feature_key'].value_counts()
    multi_ctx_features = feature_counts[feature_counts > 1]
    
    print("=" * 70)
    print("FEATURES CON MULTIPLI CONTESTI (ctx_idx)")
    print("=" * 70)
    print(f"\nFeatures totali nel CSV: {len(feature_counts)}")
    print(f"Features con 1 solo ctx_idx: {len(feature_counts[feature_counts == 1])}")
    print(f"Features con più ctx_idx: {len(multi_ctx_features)}")
    print(f"\nDistribuzione:")
    print(feature_counts.value_counts().sort_index())
    
    # Mostra esempi
    print("\n" + "=" * 70)
    print("ESEMPI DI FEATURES CON MULTIPLI node_influence")
    print("=" * 70)
    
    examples = [
        '0_18753',
        '0_40780', 
        '0_95475'
    ]
    
    for fk in examples:
        if fk in df['feature_key'].values:
            rows = df[df['feature_key'] == fk][['feature_key', 'ctx_idx', 'token', 'activation', 'node_influence']]
            
            print(f"\n[*] Feature: {fk}")
            print("-" * 70)
            for _, row in rows.iterrows():
                print(f"  ctx_idx={row['ctx_idx']:2d} | token={row['token']:15s} | "
                      f"activation={row['activation']:7.4f} | node_influence={row['node_influence']:10.6f}")
            
            # Mostra quale sarebbe il max
            max_row = rows.loc[rows['node_influence'].idxmax()]
            print(f"  -> MAX node_influence: {max_row['node_influence']:.6f} (ctx_idx={int(max_row['ctx_idx'])}, token={max_row['token']})")
    
    # Test della logica usata nel codice
    print("\n" + "=" * 70)
    print("TEST LOGICA: max(node_influence) per feature_key")
    print("=" * 70)
    
    # Simula la logica del codice
    csv_max = df.sort_values('node_influence').groupby('feature_key', as_index=False).last()
    csv_max = csv_max[['feature_key', 'node_influence', 'ctx_idx']]
    
    print(f"\nRighe originali CSV: {len(df)}")
    print(f"Righe dopo aggregazione (max per feature_key): {len(csv_max)}")
    
    # Verifica con gli esempi
    print("\nVerifica esempi:")
    for fk in examples:
        if fk in csv_max['feature_key'].values:
            row = csv_max[csv_max['feature_key'] == fk].iloc[0]
            print(f"  {fk}: node_influence={row['node_influence']:.6f}, ctx_idx={int(row['ctx_idx'])}")
    
    # Statistiche
    print("\n" + "=" * 70)
    print("STATISTICHE node_influence")
    print("=" * 70)
    
    print("\nPrima dell'aggregazione (tutte le righe CSV):")
    print(df['node_influence'].describe())
    
    print("\nDopo l'aggregazione (max per feature_key):")
    print(csv_max['node_influence'].describe())
    
    print("\n[OK] Test completato!")


if __name__ == "__main__":
    main()

