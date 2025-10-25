import pandas as pd

df = pd.read_csv('output/STEP2_PEAK_CONSISTENCY.csv')
row = df[df['feature_key']=='0_95057'].iloc[0]

print('0_95057 (errore in V5):')
print(f'  supernode_class: {row["supernode_class"]}')
print(f'  layer: {row["layer"]}')
print(f'  peak_consistency_main: {row["peak_consistency_main"]}')
print(f'  n_distinct_peaks: {row["n_distinct_peaks"]}')
print(f'  main_peak_token: {row["main_peak_token"]}')

feat_df = pd.read_csv('output/STEP2_PATTERN_ANALYSIS_FEATURES.csv')
feat_row = feat_df[feat_df['feature_key']=='0_95057'].iloc[0]
print(f'  func_vs_sem_pct: {feat_row["func_vs_sem_pct"]}')
print(f'  conf_F: {feat_row["conf_F"]}')
print(f'  conf_S: {feat_row["conf_S"]}')
print(f'  sparsity_median: {feat_row["sparsity_median"]}')

print('\nPerche V4 lo classifica correttamente e V5 no?')
print('V4: Controlla peak_consistency PRIMA di Say X')
print('V5: Controlla peak_consistency PRIMA di Say X')
print('\nIl problema e che:')
print(f'  peak_consistency={row["peak_consistency_main"]:.3f} < 0.8 -> NON passa regola 1')
print(f'  sparsity={feat_row["sparsity_median"]:.3f} >= 0.45 -> NON passa regola 2')
print(f'  func={feat_row["func_vs_sem_pct"]:.1f}% >= 50 AND conf_F={feat_row["conf_F"]:.2f} >= 0.90 -> PASSA regola 3 (Say X)')
print('\nIn V4, layer <= 3 lo salva!')
print(f'  layer={row["layer"]} <= 3 -> Semantic')

