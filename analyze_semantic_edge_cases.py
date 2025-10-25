import pandas as pd
import numpy as np

df = pd.read_csv('output/STEP2_PATTERN_ANALYSIS_FEATURES.csv')

print("=" * 80)
print("ANALISI CASI EDGE: Semantic vs Say X")
print("=" * 80)

# I 3 casi problematici
edge_cases = df[df['feature_key'].isin(['7_3144', '22_11998', '20_44686'])]
print("\n3 Semantic che vanno in Review:")
print(edge_cases[['feature_key', 'layer', 'func_vs_sem_pct', 'conf_F', 'conf_S', 
                   'n_active_prompts', 'K_sem_distinct', 'peak_idx_cv', 'sparsity_median']].to_string(index=False))

# Tutti i Semantic
semantic = df[df['supernode_class'] == 'Semantic']
print(f"\n\nTutti i Semantic (N={len(semantic)}):")
print("\nfunc_vs_sem_pct:")
print(f"  Min: {semantic['func_vs_sem_pct'].min():.1f}%")
print(f"  Q10: {np.percentile(semantic['func_vs_sem_pct'], 10):.1f}%")
print(f"  Q25: {np.percentile(semantic['func_vs_sem_pct'], 25):.1f}%")
print(f"  Median: {semantic['func_vs_sem_pct'].median():.1f}%")
print(f"  Q75: {np.percentile(semantic['func_vs_sem_pct'], 75):.1f}%")
print(f"  Max: {semantic['func_vs_sem_pct'].max():.1f}%")

print("\nn_active_prompts (su quanti prompt si attiva):")
print(f"  Min: {semantic['n_active_prompts'].min()}")
print(f"  Median: {semantic['n_active_prompts'].median():.0f}")
print(f"  Max: {semantic['n_active_prompts'].max()}")

print("\nK_sem_distinct (varietà token semantici):")
print(f"  Min: {semantic['K_sem_distinct'].min()}")
print(f"  Median: {semantic['K_sem_distinct'].median():.0f}")
print(f"  Max: {semantic['K_sem_distinct'].max()}")

print("\npeak_idx_cv (stabilità posizione):")
print(f"  Min: {semantic['peak_idx_cv'].min():.3f}")
print(f"  Median: {semantic['peak_idx_cv'].median():.3f}")
print(f"  Max: {semantic['peak_idx_cv'].max():.3f}")

# Say X per confronto
sayx = df[df['supernode_class'] == 'Say "X"']
print(f"\n\nSay X (N={len(sayx)}):")
print("\nfunc_vs_sem_pct:")
print(f"  Min: {sayx['func_vs_sem_pct'].min():.1f}%")
print(f"  Median: {sayx['func_vs_sem_pct'].median():.1f}%")
print(f"  Max: {sayx['func_vs_sem_pct'].max():.1f}%")

print("\nn_active_prompts:")
print(f"  Min: {sayx['n_active_prompts'].min()}")
print(f"  Median: {sayx['n_active_prompts'].median():.0f}")
print(f"  Max: {sayx['n_active_prompts'].max()}")

print("\nK_sem_distinct:")
print(f"  Min: {sayx['K_sem_distinct'].min()}")
print(f"  Median: {sayx['K_sem_distinct'].median():.0f}")
print(f"  Max: {sayx['K_sem_distinct'].max()}")

print("\npeak_idx_cv:")
print(f"  Min: {sayx['peak_idx_cv'].min():.3f}")
print(f"  Median: {sayx['peak_idx_cv'].median():.3f}")
print(f"  Max: {sayx['peak_idx_cv'].max():.3f}")

print("\n" + "=" * 80)
print("METRICHE DISCRIMINANTI")
print("=" * 80)

print("\n1. n_active_prompts (su 5 totali):")
print(f"   Semantic: min={semantic['n_active_prompts'].min()}, median={semantic['n_active_prompts'].median():.0f}, max={semantic['n_active_prompts'].max()}")
print(f"   Say X:    min={sayx['n_active_prompts'].min()}, median={sayx['n_active_prompts'].median():.0f}, max={sayx['n_active_prompts'].max()}")
print(f"   Gap: {semantic['n_active_prompts'].min() - sayx['n_active_prompts'].max()}")

print("\n2. K_sem_distinct (varietà token semantici):")
print(f"   Semantic: min={semantic['K_sem_distinct'].min()}, median={semantic['K_sem_distinct'].median():.0f}, max={semantic['K_sem_distinct'].max()}")
print(f"   Say X:    min={sayx['K_sem_distinct'].min()}, median={sayx['K_sem_distinct'].median():.0f}, max={sayx['K_sem_distinct'].max()}")
sem_k_nonzero = semantic[semantic['K_sem_distinct'] > 0]['K_sem_distinct']
print(f"   Semantic (K>0): min={sem_k_nonzero.min()}, median={sem_k_nonzero.median():.0f}")

print("\n3. peak_idx_cv (stabilità posizione):")
print(f"   Semantic: min={semantic['peak_idx_cv'].min():.3f}, median={semantic['peak_idx_cv'].median():.3f}, max={semantic['peak_idx_cv'].max():.3f}")
print(f"   Say X:    min={sayx['peak_idx_cv'].min():.3f}, median={sayx['peak_idx_cv'].median():.3f}, max={sayx['peak_idx_cv'].max():.3f}")

print("\n" + "=" * 80)
print("SOGLIE PROPOSTE PER SAY X")
print("=" * 80)

# Test diverse combinazioni
test_configs = [
    ('func >= 80 AND conf_F >= 0.90 AND layer >= 7', 80, 0.90, 7, None, None),
    ('func >= 70 AND conf_F >= 0.90 AND layer >= 7', 70, 0.90, 7, None, None),
    ('func >= 60 AND conf_F >= 0.90 AND layer >= 7', 60, 0.90, 7, None, None),
    ('func >= 50 AND conf_F >= 0.90 AND layer >= 7', 50, 0.90, 7, None, None),
    ('func >= 80 AND conf_F >= 0.90 AND n_active <= 3', 80, 0.90, None, 3, None),
    ('func >= 70 AND conf_F >= 0.90 AND n_active <= 3', 70, 0.90, None, 3, None),
    ('func >= 60 AND conf_F >= 0.90 AND n_active <= 3', 60, 0.90, None, 3, None),
    ('func >= 50 AND conf_F >= 0.90 AND n_active <= 3', 50, 0.90, None, 3, None),
]

for desc, func_t, conf_f_t, layer_t, n_active_t, k_t in test_configs:
    sayx_match = 0
    sem_match = 0
    
    for _, row in sayx.iterrows():
        match = row['func_vs_sem_pct'] >= func_t and row['conf_F'] >= conf_f_t
        if layer_t is not None:
            match = match and row['layer'] >= layer_t
        if n_active_t is not None:
            match = match and row['n_active_prompts'] <= n_active_t
        if k_t is not None:
            match = match and row['K_sem_distinct'] <= k_t
        if match:
            sayx_match += 1
    
    for _, row in semantic.iterrows():
        match = row['func_vs_sem_pct'] >= func_t and row['conf_F'] >= conf_f_t
        if layer_t is not None:
            match = match and row['layer'] >= layer_t
        if n_active_t is not None:
            match = match and row['n_active_prompts'] <= n_active_t
        if k_t is not None:
            match = match and row['K_sem_distinct'] <= k_t
        if match:
            sem_match += 1
    
    print(f"\n{desc}:")
    print(f"  Say X:    {sayx_match:2d}/{len(sayx):2d} ({100*sayx_match/len(sayx):5.1f}%)")
    print(f"  Semantic: {sem_match:2d}/{len(semantic):2d} ({100*sem_match/len(semantic):5.1f}%) - FP")

print("\n" + "=" * 80)
print("ANALISI DETTAGLIATA: I 3 CASI EDGE")
print("=" * 80)

for _, row in edge_cases.iterrows():
    print(f"\n{row['feature_key']}:")
    print(f"  layer: {row['layer']}")
    print(f"  func_vs_sem_pct: {row['func_vs_sem_pct']:.1f}%")
    print(f"  conf_F: {row['conf_F']:.2f}, conf_S: {row['conf_S']:.2f}")
    print(f"  n_active_prompts: {row['n_active_prompts']}/5 ({100*row['n_active_prompts']/5:.0f}%)")
    print(f"  K_sem_distinct: {row['K_sem_distinct']}")
    print(f"  peak_idx_cv: {row['peak_idx_cv']:.3f}")
    print(f"  sparsity_median: {row['sparsity_median']:.3f}")
    
    # Confronta con Say X
    print(f"  Perché Semantic e non Say X?")
    if row['n_active_prompts'] > sayx['n_active_prompts'].max():
        print(f"    - n_active ({row['n_active_prompts']}) > Say X max ({sayx['n_active_prompts'].max()})")
    if row['func_vs_sem_pct'] < 50:
        print(f"    - func_vs_sem_pct ({row['func_vs_sem_pct']:.1f}%) < 50% (non dominanza functional)")

print("\n" + "=" * 80)
print("PROPOSTA ALBERO DECISIONALE AGGIORNATO")
print("=" * 80)

print("""
REGOLA SAY X (più conservativa):

IF func_vs_sem_pct >= 50 AND conf_F >= 0.90 AND n_active_prompts <= 3
   → Say "X"

MOTIVAZIONE:

1. func_vs_sem_pct >= 50: "differenza non schiacciante" = < 50%
   - Se func è solo leggermente più forte di sem, è Semantic
   - Se func è MOLTO più forte (>= 50%), potrebbe essere Say X
   
2. n_active_prompts <= 3: Say X si attivano sporadicamente (1-3/5 prompt)
   - Semantic si attivano su quasi tutti i prompt (3-5/5)
   - Gap: Say X max=3, Semantic min=1 (ma median=5)
   
3. conf_F >= 0.90: Conferma dominanza functional (già robusto)

LAYER come indicatore secondario (non obbligatorio):
   - Se layer >= 7 AND func >= 50 → aumenta confidence Say X
   - Se layer <= 3 AND n_active >= 4 → aumenta confidence Semantic

RISULTATO ATTESO:
   - 7_3144:  func=-25.3%, n_active=2 → Semantic (func < 50)
   - 22_11998: func=-6.2%, n_active=2 → Semantic (func < 50)
   - 20_44686: func=45.9%, n_active=1 → Semantic (func < 50, borderline)
   
   Tutti e 3 hanno func < 50% → Semantic corretto
""")

