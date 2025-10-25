import pandas as pd

df = pd.read_csv('output/STEP2_PEAK_CONSISTENCY.csv')

print("=" * 80)
print("ANALISI ANOMALIE PEAK_CONSISTENCY")
print("=" * 80)

print('\nSay X con consistency=1.0 (anomalie):')
sayx_high = df[(df['supernode_class']=='Say "X"') & (df['peak_consistency_main']==1.0)]
print(sayx_high[['feature_key', 'layer', 'main_peak_token', 'n_distinct_peaks']].to_string(index=False))

print('\n\nSemantic con consistency<0.5 (anomalie):')
sem_low = df[(df['supernode_class']=='Semantic') & (df['peak_consistency_main']<0.5)]
print(sem_low[['feature_key', 'layer', 'main_peak_token', 'n_distinct_peaks', 'peak_consistency_main']].to_string(index=False))

print('\n\nSemantic con consistency=0.0:')
sem_zero = df[(df['supernode_class']=='Semantic') & (df['peak_consistency_main']==0.0)]
print(sem_zero[['feature_key', 'layer', 'main_peak_token', 'n_distinct_peaks']].to_string(index=False))

# Analisi: forse n_distinct_peaks è più discriminante?
print("\n" + "=" * 80)
print("ANALISI n_distinct_peaks")
print("=" * 80)

sayx = df[df['supernode_class']=='Say "X"']
semantic = df[df['supernode_class']=='Semantic']

print(f"\nSay X n_distinct_peaks:")
print(f"  Min: {sayx['n_distinct_peaks'].min()}")
print(f"  Median: {sayx['n_distinct_peaks'].median():.0f}")
print(f"  Max: {sayx['n_distinct_peaks'].max()}")
print(f"  Distribuzione: {sayx['n_distinct_peaks'].value_counts().sort_index().to_dict()}")

print(f"\nSemantic n_distinct_peaks:")
print(f"  Min: {semantic['n_distinct_peaks'].min()}")
print(f"  Median: {semantic['n_distinct_peaks'].median():.0f}")
print(f"  Max: {semantic['n_distinct_peaks'].max()}")
print(f"  Distribuzione: {semantic['n_distinct_peaks'].value_counts().sort_index().to_dict()}")

# Combinazione: consistency alta E n_distinct_peaks basso
print("\n" + "=" * 80)
print("REGOLA COMBINATA: consistency >= 0.8 AND n_distinct_peaks <= 1")
print("=" * 80)

for cls in ['Say "X"', 'Semantic', 'Relationship']:
    subset = df[df['supernode_class']==cls]
    match = subset[(subset['peak_consistency_main'] >= 0.8) & (subset['n_distinct_peaks'] <= 1)]
    print(f"\n{cls}: {len(match)}/{len(subset)} ({100*len(match)/len(subset):.1f}%)")
    if len(match) > 0 and len(match) <= 5:
        print(f"  Feature keys: {match['feature_key'].tolist()}")

