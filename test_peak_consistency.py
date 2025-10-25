import pandas as pd
import json

# Carica CSV ENRICHED
df = pd.read_csv('output/2025-10-21T07-40_export_ENRICHED.csv')

print("=" * 80)
print("ANALISI PEAK CONSISTENCY")
print("=" * 80)

def calculate_peak_consistency(group):
    """
    Per ogni feature, calcola:
    - peak_consistency: % di volte che peak_token appare nel prompt ed e' effettivamente il peak
    
    Logica:
    1. Per ogni prompt, guarda peak_token
    2. Conta quante volte quel token appare come peak
    3. Conta quante volte quel token appare nel prompt (tokens o fallback)
    4. peak_consistency = (volte come peak) / (volte nel prompt)
    
    Se peak_token varia tra prompt, calcola consistency per ogni token unico
    e prendi la media pesata per frequenza.
    """
    
    feature_key = group['feature_key'].iloc[0]
    
    # Dizionario: token -> {as_peak: count, in_prompt: count}
    token_stats = {}
    
    for _, row in group.iterrows():
        peak_token = str(row['peak_token']).strip().lower()
        
        # Conta questo token come peak
        if peak_token not in token_stats:
            token_stats[peak_token] = {'as_peak': 0, 'in_prompt': 0}
        token_stats[peak_token]['as_peak'] += 1
        
        # Conta occorrenze nel prompt
        # Usa tokens JSON se disponibile, altrimenti fallback su prompt text
        if 'tokens' in row and pd.notna(row['tokens']):
            try:
                tokens = json.loads(row['tokens'])
                tokens_lower = [str(t).strip().lower() for t in tokens]
            except:
                # Fallback: split su spazi e punteggiatura
                tokens_lower = str(row['prompt']).lower().replace(',', ' , ').replace('.', ' . ').split()
        else:
            # Fallback: split su spazi e punteggiatura
            tokens_lower = str(row['prompt']).lower().replace(',', ' , ').replace('.', ' . ').split()
        
        # Conta occorrenze di ogni token nel prompt
        for token in set(tokens_lower):
            if token not in token_stats:
                token_stats[token] = {'as_peak': 0, 'in_prompt': 0}
            token_stats[token]['in_prompt'] += tokens_lower.count(token)
    
    # Calcola consistency per ogni token
    token_consistencies = {}
    for token, stats in token_stats.items():
        if stats['in_prompt'] > 0:
            consistency = stats['as_peak'] / stats['in_prompt']
            token_consistencies[token] = {
                'consistency': consistency,
                'as_peak': stats['as_peak'],
                'in_prompt': stats['in_prompt']
            }
    
    # Metrica aggregata: media pesata per frequenza come peak
    total_peaks = sum([s['as_peak'] for s in token_consistencies.values()])
    if total_peaks > 0:
        weighted_consistency = sum([
            s['consistency'] * s['as_peak'] / total_peaks 
            for s in token_consistencies.values()
        ])
    else:
        weighted_consistency = 0.0
    
    # Metrica alternativa: consistency del token più frequente come peak
    if token_consistencies:
        most_frequent_peak = max(token_consistencies.items(), 
                                  key=lambda x: x[1]['as_peak'])
        main_peak_consistency = most_frequent_peak[1]['consistency']
        main_peak_token = most_frequent_peak[0]
    else:
        main_peak_consistency = 0.0
        main_peak_token = None
    
    # Numero di token distinti come peak
    n_distinct_peaks = len([t for t, s in token_consistencies.items() if s['as_peak'] > 0])
    
    return pd.Series({
        'peak_consistency_weighted': weighted_consistency,
        'peak_consistency_main': main_peak_consistency,
        'main_peak_token': main_peak_token,
        'n_distinct_peaks': n_distinct_peaks,
        'token_stats': token_consistencies
    })

# Calcola per ogni feature
print("\nCalcolo peak_consistency per ogni feature...")
consistency_df = df.groupby('feature_key').apply(calculate_peak_consistency).reset_index()

# Merge con ground truth
features_df = pd.read_csv('output/STEP2_PATTERN_ANALYSIS_FEATURES.csv')
consistency_df = consistency_df.merge(
    features_df[['feature_key', 'supernode_class', 'layer', 'func_vs_sem_pct', 'n_active_prompts']], 
    on='feature_key'
)

print("\n" + "=" * 80)
print("DISTRIBUZIONE PER CLASSE")
print("=" * 80)

for cls in ['Say "X"', 'Semantic', 'Relationship']:
    subset = consistency_df[consistency_df['supernode_class'] == cls]
    print(f"\n{cls} (N={len(subset)}):")
    print(f"  peak_consistency_main:")
    print(f"    Min:    {subset['peak_consistency_main'].min():.3f}")
    print(f"    Median: {subset['peak_consistency_main'].median():.3f}")
    print(f"    Max:    {subset['peak_consistency_main'].max():.3f}")
    print(f"  n_distinct_peaks:")
    print(f"    Min:    {subset['n_distinct_peaks'].min()}")
    print(f"    Median: {subset['n_distinct_peaks'].median():.0f}")
    print(f"    Max:    {subset['n_distinct_peaks'].max()}")

print("\n" + "=" * 80)
print("ESEMPI DETTAGLIATI")
print("=" * 80)

# Mostra alcuni esempi
print("\nSemantic (dovrebbero avere consistency alta):")
sem_examples = consistency_df[consistency_df['supernode_class'] == 'Semantic'].head(5)
for _, row in sem_examples.iterrows():
    print(f"\n  {row['feature_key']:15s} (layer {row['layer']:2d}):")
    print(f"    peak_consistency_main: {row['peak_consistency_main']:.3f}")
    print(f"    main_peak_token: {row['main_peak_token']}")
    print(f"    n_distinct_peaks: {row['n_distinct_peaks']}")

print("\n\nSay X (dovrebbero avere consistency bassa/variabile):")
sayx_examples = consistency_df[consistency_df['supernode_class'] == 'Say "X"'].head(5)
for _, row in sayx_examples.iterrows():
    print(f"\n  {row['feature_key']:15s} (layer {row['layer']:2d}):")
    print(f"    peak_consistency_main: {row['peak_consistency_main']:.3f}")
    print(f"    main_peak_token: {row['main_peak_token']}")
    print(f"    n_distinct_peaks: {row['n_distinct_peaks']}")

print("\n" + "=" * 80)
print("SOGLIE PROPOSTE")
print("=" * 80)

sayx = consistency_df[consistency_df['supernode_class'] == 'Say "X"']
semantic = consistency_df[consistency_df['supernode_class'] == 'Semantic']

print(f"\nSay X peak_consistency_main:")
print(f"  Min: {sayx['peak_consistency_main'].min():.3f}")
print(f"  Max: {sayx['peak_consistency_main'].max():.3f}")

print(f"\nSemantic peak_consistency_main:")
print(f"  Min: {semantic['peak_consistency_main'].min():.3f}")
print(f"  Max: {semantic['peak_consistency_main'].max():.3f}")

# Trova soglia ottimale
if sayx['peak_consistency_main'].max() < semantic['peak_consistency_main'].min():
    threshold = (sayx['peak_consistency_main'].max() + semantic['peak_consistency_main'].min()) / 2
    print(f"\nGap trovato! Soglia ottimale: {threshold:.3f}")
    print(f"  Say X max: {sayx['peak_consistency_main'].max():.3f}")
    print(f"  Semantic min: {semantic['peak_consistency_main'].min():.3f}")
    print(f"  Gap: {semantic['peak_consistency_main'].min() - sayx['peak_consistency_main'].max():.3f}")
else:
    print(f"\nNessun gap netto. Sovrapposizione:")
    print(f"  Say X max: {sayx['peak_consistency_main'].max():.3f}")
    print(f"  Semantic min: {semantic['peak_consistency_main'].min():.3f}")
    print(f"  Overlap: {sayx['peak_consistency_main'].max() - semantic['peak_consistency_main'].min():.3f}")

# Salva per analisi successiva
consistency_df.to_csv('output/STEP2_PEAK_CONSISTENCY.csv', index=False)
print(f"\n\nSalvato: output/STEP2_PEAK_CONSISTENCY.csv")

