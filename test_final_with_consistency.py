import pandas as pd

# Carica dati
features_df = pd.read_csv('output/STEP2_PATTERN_ANALYSIS_FEATURES.csv')
consistency_df = pd.read_csv('output/STEP2_PEAK_CONSISTENCY.csv')

# Merge
df = features_df.merge(
    consistency_df[['feature_key', 'peak_consistency_main', 'n_distinct_peaks', 'main_peak_token']], 
    on='feature_key'
)

print("=" * 80)
print("TEST ALBERO DECISIONALE CON PEAK_CONSISTENCY")
print("=" * 80)

def classify_v4_with_consistency(row):
    """
    Versione con peak_consistency invece di n_active_prompts
    """
    # Regola 1: Dictionary Semantic (layer basso + consistency alta)
    # Quando il token appare, e' SEMPRE il peak
    if row['peak_consistency_main'] >= 0.8 and row['n_distinct_peaks'] <= 1:
        return 'Semantic'
    
    # Regola 2: Say X - dominanza functional schiacciante + layer alto
    # (peak_consistency bassa o n_distinct_peaks > 1 esclude dictionary)
    if (row['func_vs_sem_pct'] >= 50 and 
        row['conf_F'] >= 0.90 and 
        row['layer'] >= 7):
        return 'Say "X"'
    
    # Regola 3: Relationship - attivazioni diffuse
    if row['sparsity_median'] < 0.45:
        return 'Relationship'
    
    # Regola 4: Semantic - altri casi
    if row['layer'] <= 3 or row['conf_S'] >= 0.50 or row['func_vs_sem_pct'] < 50:
        return 'Semantic'
    
    # Regola 5: Review
    return 'Review'

def classify_v5_simplified(row):
    """
    Versione semplificata: peak_consistency come discriminante primario
    """
    # Regola 1: Dictionary Semantic (priorita' massima)
    if row['peak_consistency_main'] >= 0.8 and row['n_distinct_peaks'] <= 1:
        return 'Semantic'
    
    # Regola 2: Relationship
    if row['sparsity_median'] < 0.45:
        return 'Relationship'
    
    # Regola 3: Say X
    if row['func_vs_sem_pct'] >= 50 and row['conf_F'] >= 0.90:
        return 'Say "X"'
    
    # Regola 4: Semantic (altri casi)
    if row['conf_S'] >= 0.50 or row['func_vs_sem_pct'] < 50:
        return 'Semantic'
    
    # Regola 5: Review
    return 'Review'

versions = [
    ('V4: consistency + layer', classify_v4_with_consistency),
    ('V5: consistency prioritaria (no layer)', classify_v5_simplified),
]

for name, classify_fn in versions:
    print(f"\n{'=' * 80}")
    print(f"{name}")
    print("=" * 80)
    
    df_test = df.copy()
    df_test['pred'] = df_test.apply(classify_fn, axis=1)
    
    correct = (df_test['supernode_class'] == df_test['pred']).sum()
    total = len(df_test)
    acc = 100 * correct / total
    n_review = (df_test['pred'] == 'Review').sum()
    
    print(f"\nAccuracy: {acc:.1f}% ({correct}/{total}), Review: {n_review}/{total}")
    
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
            
            # Mostra feature keys degli errori
            if len(errors) <= 5:
                print(f"    Errori: {errors['feature_key'].tolist()}")
        else:
            print(f"  {cls:15s}: {cls_acc:5.1f}% ({cls_correct:2d}/{cls_total:2d}) | OK")

print("\n" + "=" * 80)
print("RACCOMANDAZIONE FINALE")
print("=" * 80)

print("""
V5 (consistency prioritaria) e' piu' semplice e robusta!

ALBERO DECISIONALE FINALE:

1. IF peak_consistency >= 0.8 AND n_distinct_peaks <= 1
   THEN Semantic (Dictionary)
   
2. ELSE IF sparsity_median < 0.45
   THEN Relationship
   
3. ELSE IF func_vs_sem_pct >= 50 AND conf_F >= 0.90
   THEN Say "X"
   
4. ELSE IF conf_S >= 0.50 OR func_vs_sem_pct < 50
   THEN Semantic (Concept)
   
5. ELSE
   Review

MOTIVAZIONI:

- **peak_consistency**: Discriminante primario per Dictionary Semantic
  - "Quando il token appare, e' SEMPRE il peak?" -> Dictionary
  - Elimina dipendenza da layer (piu' robusto)
  
- **n_distinct_peaks <= 1**: Conferma che il token e' consistente
  - Say X hanno n_distinct_peaks=2 (il token varia)
  - Dictionary hanno n_distinct_peaks=1 (sempre lo stesso token)

- **func_vs_sem_pct >= 50**: Dominanza functional schiacciante per Say X

- **sparsity < 0.45**: Relationship (invariato)

VANTAGGI:

- NON richiede layer (piu' robusto per generalizzazione)
- Cattura il concetto giusto: "token sempre peak quando presente"
- Piu' semplice (meno condizioni)
- Separazione netta: 0% Say X con consistency alta + n_distinct <= 1
""")

