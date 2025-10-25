import pandas as pd

df = pd.read_csv('output/STEP2_PATTERN_ANALYSIS_FEATURES.csv')

print("=" * 80)
print("ALBERO DECISIONALE ROBUSTO")
print("=" * 80)

# Test diverse configurazioni
configs = [
    {
        'name': 'BASELINE (rigida)',
        'rules': [
            ('func_vs_sem_pct >= 100 AND conf_F >= 1.0', 'Say "X"'),
            ('sparsity_median < 0.40', 'Relationship'),
            ('conf_S >= 0.6', 'Semantic'),
        ]
    },
    {
        'name': 'PROPOSTA 1: Layer + func',
        'rules': [
            ('layer >= 7 AND func_vs_sem_pct >= 90 AND conf_F >= 0.95', 'Say "X"'),
            ('sparsity_median < 0.45', 'Relationship'),
            ('conf_S >= 0.5 OR layer <= 2', 'Semantic'),
        ]
    },
    {
        'name': 'PROPOSTA 2: Layer + func (più conservativa)',
        'rules': [
            ('layer >= 5 AND func_vs_sem_pct >= 80 AND conf_F >= 0.90', 'Say "X"'),
            ('sparsity_median < 0.50', 'Relationship'),
            ('conf_S >= 0.4 OR layer <= 3', 'Semantic'),
        ]
    },
    {
        'name': 'PROPOSTA 3: Layer forte',
        'rules': [
            ('layer >= 7 AND func_vs_sem_pct >= 50', 'Say "X"'),
            ('sparsity_median < 0.45', 'Relationship'),
            ('layer <= 6 OR conf_S >= 0.5', 'Semantic'),
        ]
    },
]

for config in configs:
    print(f"\n{'=' * 80}")
    print(f"{config['name']}")
    print("=" * 80)
    
    predictions = []
    for _, row in df.iterrows():
        pred = 'Review'
        for rule_str, label in config['rules']:
            # Valuta la regola
            try:
                if eval(rule_str, {}, {
                    'layer': row['layer'],
                    'func_vs_sem_pct': row['func_vs_sem_pct'],
                    'conf_F': row['conf_F'],
                    'conf_S': row['conf_S'],
                    'sparsity_median': row['sparsity_median'],
                }):
                    pred = label
                    break
            except:
                pass
        predictions.append(pred)
    
    df_test = df.copy()
    df_test['pred'] = predictions
    
    # Accuracy
    correct = (df_test['supernode_class'] == df_test['pred']).sum()
    total = len(df_test)
    acc = 100 * correct / total
    n_review = (df_test['pred'] == 'Review').sum()
    
    print(f"\nAccuracy: {acc:.1f}% ({correct}/{total}), Review: {n_review}")
    
    # Per classe
    for cls in ['Say "X"', 'Semantic', 'Relationship']:
        subset = df_test[df_test['supernode_class'] == cls]
        cls_correct = (subset['supernode_class'] == subset['pred']).sum()
        cls_total = len(subset)
        cls_acc = 100 * cls_correct / cls_total if cls_total > 0 else 0
        
        errors = subset[subset['supernode_class'] != subset['pred']]
        if len(errors) > 0:
            error_types = errors['pred'].value_counts().to_dict()
            error_str = ", ".join([f"{k}:{v}" for k, v in error_types.items()])
            print(f"  {cls:15s}: {cls_acc:5.1f}% ({cls_correct}/{cls_total}) - Errori: {error_str}")
        else:
            print(f"  {cls:15s}: {cls_acc:5.1f}% ({cls_correct}/{cls_total})")
    
    # Mostra regole
    print("\nRegole:")
    for i, (rule, label) in enumerate(config['rules'], 1):
        print(f"  {i}. IF {rule}")
        print(f"     THEN {label}")
    print(f"  {len(config['rules'])+1}. ELSE Review")

print("\n" + "=" * 80)
print("RACCOMANDAZIONE FINALE")
print("=" * 80)

print("""
Basandomi sull'analisi, raccomando:

ALBERO DECISIONALE ROBUSTO:

1. IF layer >= 7 AND func_vs_sem_pct >= 80 AND conf_F >= 0.90
   THEN Say "X"
   
2. ELSE IF sparsity_median < 0.45
   THEN Relationship
   
3. ELSE IF layer <= 3 OR conf_S >= 0.50
   THEN Semantic
   
4. ELSE
   Review (con diagnostiche)

MOTIVAZIONI:

- **Say X**: Layer >= 7 separa dai Semantic layer 0 (gap di 7 layer)
  - func_vs_sem_pct >= 80 (invece di 100) da margine per variabilita
  - conf_F >= 0.90 (invece di 1.0) da margine per noise

- **Relationship**: sparsity < 0.45 (invece di 0.40) copre gap di 0.34
  - Margine di sicurezza: 0.11 da ogni lato

- **Semantic**: layer <= 3 cattura i "dictionary" layer bassi
  - conf_S >= 0.50 (invece di 0.60) piu inclusivo
  - Ordine "OR" permette di catturare entrambi i sottotipi

ROBUSTEZZA:

- Layer: gap di 7 (molto robusto)
- Sparsity: gap di 0.34, soglia a 0.45 (margine 0.11)
- func_vs_sem_pct: abbassato da 100 a 80 (20% margine)
- conf_F: abbassato da 1.0 a 0.90 (10% margine)
- conf_S: abbassato da 0.6 a 0.50 (16% margine)
""")

