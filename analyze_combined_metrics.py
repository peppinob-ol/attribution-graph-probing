import pandas as pd
import numpy as np

df = pd.read_csv('output/STEP2_PATTERN_ANALYSIS_FEATURES.csv')

print("=" * 80)
print("ANALISI COMBINATA: func_vs_sem_pct + conf_F")
print("=" * 80)

# Casi problematici: Semantic con func_vs_sem_pct == 100
semantic_100 = df[(df['supernode_class'] == 'Semantic') & (df['func_vs_sem_pct'] == 100)]
print(f"\nSemantic con func_vs_sem_pct=100: {len(semantic_100)}/19")
print("\nLoro valori di conf_F:")
for _, row in semantic_100.iterrows():
    print(f"  {row['feature_key']:15s}: conf_F={row['conf_F']:.3f}, conf_S={row['conf_S']:.3f}, share_F={row['share_F']:.3f}")

sayx = df[df['supernode_class'] == 'Say "X"']
print(f"\n\nSay X (tutti):")
print(f"  conf_F: min={sayx['conf_F'].min():.3f}, median={sayx['conf_F'].median():.3f}, max={sayx['conf_F'].max():.3f}")
print(f"  conf_S: min={sayx['conf_S'].min():.3f}, median={sayx['conf_S'].median():.3f}, max={sayx['conf_S'].max():.3f}")
print(f"  share_F: min={sayx['share_F'].min():.3f}, median={sayx['share_F'].median():.3f}, max={sayx['share_F'].max():.3f}")

print("\n" + "=" * 80)
print("PROPOSTA: Regola combinata per Say X")
print("=" * 80)

print("\nOpzione A: func_vs_sem_pct >= 100 AND conf_F >= 1.0")
print("  Say X: TUTTI hanno (100, 1.0)")
print("  Semantic con 100: alcuni hanno conf_F < 1.0")

# Test
for conf_f_thresh in [1.0, 0.99, 0.98, 0.95, 0.90]:
    sayx_match = ((sayx['func_vs_sem_pct'] >= 100) & (sayx['conf_F'] >= conf_f_thresh)).sum()
    sem_match = ((semantic_100['func_vs_sem_pct'] >= 100) & (semantic_100['conf_F'] >= conf_f_thresh)).sum()
    print(f"\n  conf_F >= {conf_f_thresh:.2f}:")
    print(f"    Say X captured: {sayx_match}/{len(sayx)} ({100*sayx_match/len(sayx):.1f}%)")
    print(f"    Semantic false positive: {sem_match}/{len(semantic_100)}")

print("\n\nOpzione B: share_F (percentuale di peak funzionali)")
print("  Say X: TUTTI hanno share_F >= 0.2")
print("  Semantic: varia")

for share_f_thresh in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
    sayx_match = (sayx['share_F'] >= share_f_thresh).sum()
    sem_all = df[df['supernode_class'] == 'Semantic']
    sem_match = (sem_all['share_F'] >= share_f_thresh).sum()
    print(f"\n  share_F >= {share_f_thresh:.1f}:")
    print(f"    Say X captured: {sayx_match}/{len(sayx)} ({100*sayx_match/len(sayx):.1f}%)")
    print(f"    Semantic false positive: {sem_match}/{len(sem_all)}")

print("\n" + "=" * 80)
print("CONFUSION MATRIX CON REGOLE COMBINATE")
print("=" * 80)

# Test diverse combinazioni
test_cases = [
    # (func_thresh, conf_f_thresh, sparsity_thresh, conf_s_thresh, description)
    (100, 1.0, 0.40, 0.6, "Baseline rigida"),
    (100, 0.99, 0.40, 0.6, "conf_F >= 0.99"),
    (100, 0.98, 0.40, 0.6, "conf_F >= 0.98"),
    (100, 0.95, 0.40, 0.6, "conf_F >= 0.95"),
    (95, 0.98, 0.40, 0.6, "func >= 95, conf_F >= 0.98"),
    (90, 0.98, 0.40, 0.6, "func >= 90, conf_F >= 0.98"),
    (80, 0.95, 0.40, 0.6, "func >= 80, conf_F >= 0.95"),
]

for func_t, conf_f_t, sparsity_t, conf_s_t, desc in test_cases:
    predictions = []
    for _, row in df.iterrows():
        # Regola 1: Say X (combinata)
        if row['func_vs_sem_pct'] >= func_t and row['conf_F'] >= conf_f_t:
            pred = 'Say "X"'
        # Regola 2: Relationship
        elif row['sparsity_median'] < sparsity_t:
            pred = 'Relationship'
        # Regola 3: Semantic
        elif row['conf_S'] >= conf_s_t:
            pred = 'Semantic'
        else:
            pred = 'Review'
        predictions.append(pred)
    
    df_test = df.copy()
    df_test['pred'] = predictions
    
    # Calcola accuracy
    correct = (df_test['supernode_class'] == df_test['pred']).sum()
    total = len(df_test)
    acc = 100 * correct / total
    
    # Conta review
    n_review = (df_test['pred'] == 'Review').sum()
    
    print(f"\n{desc}:")
    print(f"  Accuracy: {acc:.1f}% ({correct}/{total}), Review: {n_review}")
    
    # Per classe
    for cls in ['Say "X"', 'Semantic', 'Relationship']:
        subset = df_test[df_test['supernode_class'] == cls]
        cls_correct = (subset['supernode_class'] == subset['pred']).sum()
        cls_total = len(subset)
        cls_acc = 100 * cls_correct / cls_total if cls_total > 0 else 0
        
        # Mostra errori
        errors = subset[subset['supernode_class'] != subset['pred']]
        if len(errors) > 0:
            error_types = errors['pred'].value_counts().to_dict()
            error_str = ", ".join([f"{k}:{v}" for k, v in error_types.items()])
            print(f"    {cls:15s}: {cls_acc:5.1f}% ({cls_correct}/{cls_total}) - Errori: {error_str}")
        else:
            print(f"    {cls:15s}: {cls_acc:5.1f}% ({cls_correct}/{cls_total})")

print("\n" + "=" * 80)
print("ANALISI ALTERNATIVA: share_F invece di func_vs_sem_pct")
print("=" * 80)

test_cases_alt = [
    # (share_f_thresh, sparsity_thresh, conf_s_thresh, description)
    (0.8, 0.40, 0.6, "share_F >= 0.8 (molto conservativa)"),
    (0.7, 0.40, 0.6, "share_F >= 0.7"),
    (0.6, 0.40, 0.6, "share_F >= 0.6"),
    (0.5, 0.40, 0.6, "share_F >= 0.5"),
    (0.4, 0.40, 0.6, "share_F >= 0.4"),
]

for share_f_t, sparsity_t, conf_s_t, desc in test_cases_alt:
    predictions = []
    for _, row in df.iterrows():
        # Regola 1: Say X (share_F)
        if row['share_F'] >= share_f_t:
            pred = 'Say "X"'
        # Regola 2: Relationship
        elif row['sparsity_median'] < sparsity_t:
            pred = 'Relationship'
        # Regola 3: Semantic
        elif row['conf_S'] >= conf_s_t:
            pred = 'Semantic'
        else:
            pred = 'Review'
        predictions.append(pred)
    
    df_test = df.copy()
    df_test['pred'] = predictions
    
    correct = (df_test['supernode_class'] == df_test['pred']).sum()
    total = len(df_test)
    acc = 100 * correct / total
    n_review = (df_test['pred'] == 'Review').sum()
    
    print(f"\n{desc}:")
    print(f"  Accuracy: {acc:.1f}% ({correct}/{total}), Review: {n_review}")
    
    for cls in ['Say "X"', 'Semantic', 'Relationship']:
        subset = df_test[df_test['supernode_class'] == cls]
        cls_correct = (subset['supernode_class'] == subset['pred']).sum()
        cls_total = len(subset)
        cls_acc = 100 * cls_correct / cls_total if cls_total > 0 else 0
        errors = subset[subset['supernode_class'] != subset['pred']]
        if len(errors) > 0:
            error_types = errors['pred'].value_counts().to_dict()
            error_str = ", ".join([f"{k}:{v}" for k, v in error_types.items()])
            print(f"    {cls:15s}: {cls_acc:5.1f}% ({cls_correct}/{cls_total}) - Errori: {error_str}")
        else:
            print(f"    {cls:15s}: {cls_acc:5.1f}% ({cls_correct}/{cls_total})")

