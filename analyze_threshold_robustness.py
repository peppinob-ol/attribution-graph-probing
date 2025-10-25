import pandas as pd
import numpy as np

df = pd.read_csv('output/STEP2_PATTERN_ANALYSIS_FEATURES.csv')

print("=" * 80)
print("ANALISI ROBUSTEZZA SOGLIE")
print("=" * 80)

# Analisi per ogni classe
for cls in ['Say "X"', 'Semantic', 'Relationship']:
    print(f"\n{'=' * 80}")
    print(f"CLASSE: {cls} (N={len(df[df['supernode_class']==cls])})")
    print("=" * 80)
    
    subset = df[df['supernode_class']==cls]
    
    # func_vs_sem_pct
    print("\n--- func_vs_sem_pct ---")
    vals = subset['func_vs_sem_pct'].values
    print(f"Min:    {vals.min():.1f}%")
    print(f"Q05:    {np.percentile(vals, 5):.1f}%")
    print(f"Q10:    {np.percentile(vals, 10):.1f}%")
    print(f"Q25:    {np.percentile(vals, 25):.1f}%")
    print(f"Median: {np.median(vals):.1f}%")
    print(f"Q75:    {np.percentile(vals, 75):.1f}%")
    print(f"Q90:    {np.percentile(vals, 90):.1f}%")
    print(f"Q95:    {np.percentile(vals, 95):.1f}%")
    print(f"Max:    {vals.max():.1f}%")
    
    # sparsity_median
    print("\n--- sparsity_median ---")
    vals = subset['sparsity_median'].values
    print(f"Min:    {vals.min():.3f}")
    print(f"Q05:    {np.percentile(vals, 5):.3f}")
    print(f"Q10:    {np.percentile(vals, 10):.3f}")
    print(f"Q25:    {np.percentile(vals, 25):.3f}")
    print(f"Median: {np.median(vals):.3f}")
    print(f"Q75:    {np.percentile(vals, 75):.3f}")
    print(f"Q90:    {np.percentile(vals, 90):.3f}")
    print(f"Q95:    {np.percentile(vals, 95):.3f}")
    print(f"Max:    {vals.max():.3f}")
    
    # conf_S
    print("\n--- conf_S ---")
    vals = subset['conf_S'].values
    print(f"Min:    {vals.min():.3f}")
    print(f"Q05:    {np.percentile(vals, 5):.3f}")
    print(f"Q10:    {np.percentile(vals, 10):.3f}")
    print(f"Q25:    {np.percentile(vals, 25):.3f}")
    print(f"Median: {np.median(vals):.3f}")
    print(f"Q75:    {np.percentile(vals, 75):.3f}")
    print(f"Q90:    {np.percentile(vals, 90):.3f}")
    print(f"Q95:    {np.percentile(vals, 95):.3f}")
    print(f"Max:    {vals.max():.3f}")
    
    # conf_F
    print("\n--- conf_F ---")
    vals = subset['conf_F'].values
    print(f"Min:    {vals.min():.3f}")
    print(f"Q05:    {np.percentile(vals, 5):.3f}")
    print(f"Q10:    {np.percentile(vals, 10):.3f}")
    print(f"Q25:    {np.percentile(vals, 25):.3f}")
    print(f"Median: {np.median(vals):.3f}")
    print(f"Q75:    {np.percentile(vals, 75):.3f}")
    print(f"Q90:    {np.percentile(vals, 90):.3f}")
    print(f"Q95:    {np.percentile(vals, 95):.3f}")
    print(f"Max:    {vals.max():.3f}")

print("\n" + "=" * 80)
print("ANALISI GAP TRA CLASSI")
print("=" * 80)

# Gap func_vs_sem_pct: Say X vs altri
sayx = df[df['supernode_class']=='Say "X"']['func_vs_sem_pct']
semantic = df[df['supernode_class']=='Semantic']['func_vs_sem_pct']
rel = df[df['supernode_class']=='Relationship']['func_vs_sem_pct']

print("\n--- func_vs_sem_pct ---")
print(f"Say X min:        {sayx.min():.1f}%")
print(f"Semantic max:     {semantic.max():.1f}%")
print(f"Relationship max: {rel.max():.1f}%")
print(f"\nGap Say X vs Semantic:     {sayx.min() - semantic.max():.1f}%")
print(f"Gap Say X vs Relationship: {sayx.min() - rel.max():.1f}%")

# Gap sparsity: Relationship vs altri
rel_sp = df[df['supernode_class']=='Relationship']['sparsity_median']
sem_sp = df[df['supernode_class']=='Semantic']['sparsity_median']
sayx_sp = df[df['supernode_class']=='Say "X"']['sparsity_median']

print("\n--- sparsity_median ---")
print(f"Relationship max: {rel_sp.max():.3f}")
print(f"Semantic min:     {sem_sp.min():.3f}")
print(f"Say X min:        {sayx_sp.min():.3f}")
print(f"\nGap Relationship vs Semantic: {sem_sp.min() - rel_sp.max():.3f}")
print(f"Gap Relationship vs Say X:    {sayx_sp.min() - rel_sp.max():.3f}")

# Gap conf_S: Semantic vs Say X
sem_cs = df[df['supernode_class']=='Semantic']['conf_S']
sayx_cs = df[df['supernode_class']=='Say "X"']['conf_S']
rel_cs = df[df['supernode_class']=='Relationship']['conf_S']

print("\n--- conf_S ---")
print(f"Semantic min:     {sem_cs.min():.3f}")
print(f"Say X max:        {sayx_cs.max():.3f}")
print(f"Relationship min: {rel_cs.min():.3f}")
print(f"\nGap Semantic vs Say X: {sem_cs.min() - sayx_cs.max():.3f}")

print("\n" + "=" * 80)
print("SOGLIE ROBUSTE PROPOSTE")
print("=" * 80)

print("\n1. func_vs_sem_pct per Say X:")
print(f"   Attuale: == 100%")
print(f"   Say X min: {sayx.min():.1f}%")
print(f"   Altri max: {max(semantic.max(), rel.max()):.1f}%")
print(f"   Gap: {sayx.min() - max(semantic.max(), rel.max()):.1f}%")
print(f"   PROPOSTA: >= {max(semantic.max(), rel.max()) + 0.1:.1f}% (margine 0.1%)")
if sayx.min() == 100 and max(semantic.max(), rel.max()) == 100:
    print(f"   NOTA: Nessun gap! Serve altra metrica (conf_F?)")

print("\n2. sparsity_median per Relationship:")
print(f"   Attuale: < 0.4")
print(f"   Relationship max: {rel_sp.max():.3f}")
print(f"   Altri min: {min(sem_sp.min(), sayx_sp.min()):.3f}")
print(f"   Gap: {min(sem_sp.min(), sayx_sp.min()) - rel_sp.max():.3f}")
midpoint = (rel_sp.max() + min(sem_sp.min(), sayx_sp.min())) / 2
print(f"   PROPOSTA: < {midpoint:.3f} (punto medio del gap)")

print("\n3. conf_S per Semantic:")
print(f"   Attuale: >= 0.6")
print(f"   Semantic min: {sem_cs.min():.3f}")
print(f"   Semantic Q10: {np.percentile(sem_cs, 10):.3f}")
print(f"   Say X max: {sayx_cs.max():.3f}")
if sem_cs.min() == 0.0:
    print(f"   NOTA: Alcuni Semantic hanno conf_S=0 (casi ambigui)")
    sem_cs_nonzero = sem_cs[sem_cs > 0]
    if len(sem_cs_nonzero) > 0:
        print(f"   Semantic min (escl. 0): {sem_cs_nonzero.min():.3f}")
        print(f"   PROPOSTA: >= {sem_cs_nonzero.min():.3f} (esclude casi ambigui)")

print("\n" + "=" * 80)
print("CONFUSION MATRIX SIMULATA CON SOGLIE PROPOSTE")
print("=" * 80)

# Test con diverse soglie
for func_thresh in [100, 95, 90, 85, 80]:
    for sparsity_thresh in [0.4, 0.45, 0.5]:
        for conf_s_thresh in [0.5, 0.6, 0.7]:
            predictions = []
            for _, row in df.iterrows():
                if row['func_vs_sem_pct'] >= func_thresh:
                    pred = 'Say "X"'
                elif row['sparsity_median'] < sparsity_thresh:
                    pred = 'Relationship'
                elif row['conf_S'] >= conf_s_thresh:
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
            
            if acc >= 90 or func_thresh == 100:  # Mostra solo soglie buone o baseline
                print(f"\nfunc>={func_thresh:3.0f}%, sparsity<{sparsity_thresh:.2f}, conf_S>={conf_s_thresh:.1f}: Acc={acc:.1f}% ({correct}/{total}), Review={n_review}")
                
                # Mostra errori per classe
                for cls in ['Say "X"', 'Semantic', 'Relationship']:
                    subset = df_test[df_test['supernode_class'] == cls]
                    cls_correct = (subset['supernode_class'] == subset['pred']).sum()
                    cls_total = len(subset)
                    cls_acc = 100 * cls_correct / cls_total if cls_total > 0 else 0
                    print(f"  {cls:15s}: {cls_acc:5.1f}% ({cls_correct}/{cls_total})")

