import pandas as pd

df = pd.read_csv('output/STEP2_PATTERN_ANALYSIS_FEATURES.csv')

sem_prob = df[(df['supernode_class']=='Semantic') & (df['func_vs_sem_pct']==100)]
print('Semantic problematici (func=100, conf_F=1.0):')
print(sem_prob[['feature_key', 'layer', 'func_vs_sem_pct', 'conf_F', 'share_F', 'K_sem_distinct', 'sparsity_median']].to_string(index=False))

print('\n\nSay X per confronto:')
sayx = df[df['supernode_class']=='Say "X"']
print(f'Layer: min={sayx["layer"].min()}, median={sayx["layer"].median():.0f}, max={sayx["layer"].max()}')
print(f'K_sem_distinct: min={sayx["K_sem_distinct"].min()}, median={sayx["K_sem_distinct"].median():.0f}, max={sayx["K_sem_distinct"].max()}')
print(f'share_F: min={sayx["share_F"].min():.2f}, median={sayx["share_F"].median():.2f}, max={sayx["share_F"].max():.2f}')

print('\n\nConfronto layer:')
print(f'Semantic problematici: min={sem_prob["layer"].min()}, median={sem_prob["layer"].median():.0f}, max={sem_prob["layer"].max()}')
print(f'Say X: min={sayx["layer"].min()}, median={sayx["layer"].median():.0f}, max={sayx["layer"].max()}')

print('\n\nPROPOSTA: Usare layer per distinguere?')
if sem_prob["layer"].max() < sayx["layer"].min():
    print(f'SI! Semantic problematici layer <= {sem_prob["layer"].max()}, Say X layer >= {sayx["layer"].min()}')
    print(f'Gap: {sayx["layer"].min() - sem_prob["layer"].max()} layer')
else:
    print('NO, c\'e sovrapposizione nei layer')
    print(f'Semantic problematici max layer: {sem_prob["layer"].max()}')
    print(f'Say X min layer: {sayx["layer"].min()}')

