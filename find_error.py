import pandas as pd

df = pd.read_csv('output/STEP2_PATTERN_ANALYSIS_FEATURES.csv')

def classify_v3(row):
    if row['func_vs_sem_pct'] >= 50 and row['conf_F'] >= 0.90 and row['n_active_prompts'] <= 3:
        return 'Say "X"'
    elif row['sparsity_median'] < 0.45:
        return 'Relationship'
    elif row['layer'] <= 3 or row['conf_S'] >= 0.50 or row['func_vs_sem_pct'] < 50:
        return 'Semantic'
    else:
        return 'Review'

df['pred'] = df.apply(classify_v3, axis=1)

errors = df[(df['supernode_class'] != df['pred']) & (df['supernode_class'] == 'Semantic')]
print('Semantic classificato come Say X:')
print(errors[['feature_key', 'layer', 'func_vs_sem_pct', 'conf_F', 'conf_S', 'n_active_prompts', 'K_sem_distinct', 'sparsity_median']].to_string(index=False))

