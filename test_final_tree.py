import pandas as pd

df = pd.read_csv('output/STEP2_PATTERN_ANALYSIS_FEATURES.csv')

print("=" * 80)
print("TEST ALBERO DECISIONALE FINALE")
print("=" * 80)

def classify_v1_rigid(row):
    """Versione rigida originale"""
    if row['func_vs_sem_pct'] == 100 and row['conf_F'] >= 1.0:
        return 'Say "X"'
    elif row['sparsity_median'] < 0.40:
        return 'Relationship'
    elif row['conf_S'] >= 0.6:
        return 'Semantic'
    else:
        return 'Review'

def classify_v2_robust(row):
    """Versione robusta con layer"""
    if row['layer'] >= 7 and row['func_vs_sem_pct'] >= 80 and row['conf_F'] >= 0.90:
        return 'Say "X"'
    elif row['sparsity_median'] < 0.45:
        return 'Relationship'
    elif row['layer'] <= 3 or row['conf_S'] >= 0.50:
        return 'Semantic'
    else:
        return 'Review'

def classify_v3_very_robust(row):
    """Versione molto robusta"""
    if row['layer'] >= 5 and row['func_vs_sem_pct'] >= 70 and row['conf_F'] >= 0.85:
        return 'Say "X"'
    elif row['sparsity_median'] < 0.50:
        return 'Relationship'
    elif row['layer'] <= 5 or row['conf_S'] >= 0.40:
        return 'Semantic'
    else:
        return 'Review'

versions = [
    ('V1: Rigida (baseline)', classify_v1_rigid),
    ('V2: Robusta (layer >= 7, func >= 80)', classify_v2_robust),
    ('V3: Molto robusta (layer >= 5, func >= 70)', classify_v3_very_robust),
]

for name, classify_fn in versions:
    print(f"\n{'=' * 80}")
    print(f"{name}")
    print("=" * 80)
    
    df_test = df.copy()
    df_test['pred'] = df_test.apply(classify_fn, axis=1)
    
    # Accuracy
    correct = (df_test['supernode_class'] == df_test['pred']).sum()
    total = len(df_test)
    acc = 100 * correct / total
    n_review = (df_test['pred'] == 'Review').sum()
    
    print(f"\nAccuracy: {acc:.1f}% ({correct}/{total}), Review: {n_review}/{total} ({100*n_review/total:.1f}%)")
    
    # Per classe
    print("\nPer classe:")
    for cls in ['Say "X"', 'Semantic', 'Relationship']:
        subset = df_test[df_test['supernode_class'] == cls]
        cls_correct = (subset['supernode_class'] == subset['pred']).sum()
        cls_total = len(subset)
        cls_acc = 100 * cls_correct / cls_total if cls_total > 0 else 0
        
        errors = subset[subset['supernode_class'] != subset['pred']]
        if len(errors) > 0:
            error_counts = errors['pred'].value_counts().to_dict()
            error_str = ", ".join([f"{k}={v}" for k, v in error_counts.items()])
            print(f"  {cls:15s}: {cls_acc:5.1f}% ({cls_correct:2d}/{cls_total:2d}) | Errori: {error_str}")
        else:
            print(f"  {cls:15s}: {cls_acc:5.1f}% ({cls_correct:2d}/{cls_total:2d}) | OK")

print("\n" + "=" * 80)
print("ANALISI DETTAGLIATA: Dove fallisce V2?")
print("=" * 80)

df_test = df.copy()
df_test['pred'] = df_test.apply(classify_v2_robust, axis=1)

errors = df_test[df_test['supernode_class'] != df_test['pred']]
if len(errors) > 0:
    print(f"\nErrori totali: {len(errors)}")
    print("\nDettaglio errori:")
    for _, row in errors.iterrows():
        print(f"\n  {row['feature_key']:15s} (layer {row['layer']:2d})")
        print(f"    Ground truth: {row['supernode_class']:15s}")
        print(f"    Predicted:    {row['pred']:15s}")
        print(f"    Metriche: func={row['func_vs_sem_pct']:6.1f}%, conf_F={row['conf_F']:.2f}, conf_S={row['conf_S']:.2f}, sparsity={row['sparsity_median']:.3f}")
else:
    print("\nNessun errore!")

print("\n" + "=" * 80)
print("RACCOMANDAZIONE")
print("=" * 80)

print("""
Raccomando **V2: Robusta** come albero decisionale finale:

```
1. IF layer >= 7 AND func_vs_sem_pct >= 80 AND conf_F >= 0.90
   THEN Say "X"
   
2. ELSE IF sparsity_median < 0.45
   THEN Relationship
   
3. ELSE IF layer <= 3 OR conf_S >= 0.50
   THEN Semantic
   
4. ELSE
   Review
```

MARGINI DI ROBUSTEZZA:

| Parametro | Valore attuale | Margine | Dataset range |
|-----------|----------------|---------|---------------|
| layer (Say X) | >= 7 | +7 layer | Say X: 7-22, Semantic layer 0: 0 |
| func_vs_sem_pct | >= 80 | -20% | Say X: tutti 100% |
| conf_F | >= 0.90 | -0.10 | Say X: tutti 1.0 |
| sparsity | < 0.45 | +0.11 / -0.19 | Rel: 0.23-0.29, Altri: 0.64+ |
| conf_S | >= 0.50 | -0.10 | Semantic median: 0.06 (ma layer <= 3 copre i bassi) |

VANTAGGI:

- **Layer** fornisce separazione robusta (gap di 7)
- **Soglie abbassate** danno margine per variabilità futura
- **Sparsity** ha ampio margine (0.11 da ogni lato)
- **Fallback su layer** per Semantic layer bassi (dictionary features)
""")

