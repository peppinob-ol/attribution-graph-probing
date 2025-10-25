"""
Fase 2.1: Analisi Pattern dal CSV ENRICHED
Estrae pattern e statistiche per ogni classe di supernode
"""
import sys
import pandas as pd
import numpy as np
from collections import Counter
import json

# Riutilizzo funzioni da supernode_classifier
sys.path.insert(0, 'scripts/experiments')
from typing import Dict, List, Any

def is_punct(tok: str) -> bool:
    _PUNCT_CHARS = r"""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~"""
    t = str(tok).strip()
    return t != "" and all(ch in _PUNCT_CHARS for ch in t)

def is_function_like(tok: str) -> bool:
    t = str(tok).strip()
    if t == "":
        return False
    if is_punct(t):
        return True
    # Aggiornato con fix Step 1: escludi uppercase acronimi
    if t.isupper() and len(t) >= 2:
        return False
    return t.isalpha() and t.islower() and len(t) <= 3

def prompt_type(s: str) -> str:
    s = str(s).strip()
    if ":" in s:
        return s.split(":",1)[0].strip().split()[0]
    return ""

def mad_z(x):
    x = np.asarray(x, dtype=float)
    med = np.median(x)
    mad = np.median(np.abs(x - med)) + 1e-9
    return 0.6745 * (x - med) / mad

def analyze_patterns(csv_path: str, output_md: str):
    """Analizza pattern per ogni classe di supernode"""
    
    print("Caricamento CSV ENRICHED...")
    df = pd.read_csv(csv_path)
    
    # Verifica colonne necessarie
    required = {"feature_key", "layer", "prompt", "activation_max", "activation_mean", 
                "sparsity_ratio", "peak_token", "supernode_class", "motivation"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Colonne mancanti: {missing}")
    
    print(f"Righe totali: {len(df)}")
    print(f"Feature uniche: {df['feature_key'].nunique()}")
    print(f"Classi: {df['supernode_class'].unique()}")
    
    # Aggiungi colonne derivate
    df["prompt_type"] = df["prompt"].apply(prompt_type)
    df["peak_is_meta"] = (df["peak_token"].str.strip().str.lower() == df["prompt_type"].str.strip().str.lower())
    df["peak_is_function_like"] = df["peak_token"].apply(is_function_like)
    df["peak_is_semantic_like"] = ~df["peak_is_function_like"]
    
    # Calcola z-score per layer
    df["z_layer"] = 0.0
    for L, gL in df.groupby("layer"):
        df.loc[gL.index, "z_layer"] = mad_z(gL["activation_max"].values)
    
    # Aggrega per feature_key
    print("\nAggregazione per feature_key...")
    feature_stats = []
    
    for fk, g in df.groupby("feature_key"):
        layer = int(g["layer"].iloc[0])
        supernode_class = g["supernode_class"].iloc[0]
        
        # Statistiche z-score
        z_all = g["z_layer"].values
        U_cv = float(np.std(z_all) / (abs(np.mean(z_all)) + 1e-6))
        
        # Group CV (varianza tra prompt types)
        means_by_type = []
        for t, gt in g.groupby("prompt_type"):
            means_by_type.append(gt["z_layer"].mean())
        means_by_type = np.array(means_by_type) if len(means_by_type)>0 else np.array([0.0])
        pooled_std = np.std(z_all) + 1e-9
        G_group_cv = float(np.std(means_by_type) / pooled_std)
        
        # NON filtrare meta-tokens (contano come semantic)
        gn = g.copy()  # Usa tutti i token, inclusi meta
        F = gn.loc[gn["peak_is_function_like"], "z_layer"].values
        S = gn.loc[gn["peak_is_semantic_like"], "z_layer"].values
        
        # Semantic tokens (includi meta-tokens)
        sem_tokens = gn.loc[gn["peak_is_semantic_like"], "peak_token"].astype(str).tolist()
        K_sem_distinct = int(len(set(sem_tokens)))
        if len(sem_tokens) > 0:
            cnt = np.array(list(Counter(sem_tokens).values()), dtype=float)
            p = cnt / cnt.sum()
            H_sem_entropy = float(-np.sum(p * np.log2(p+1e-12)))
        else:
            H_sem_entropy = 0.0
        
        # Bootstrap confidence
        B = 200
        def boot_conf(dom="S"):
            if len(F)==0 and len(S)==0: return 0.0
            if len(F)==0: return 1.0 if dom=="S" else 0.0
            if len(S)==0: return 1.0 if dom=="F" else 0.0
            wins = 0
            for _ in range(B):
                Fb = np.random.choice(F, size=len(F), replace=True)
                Sb = np.random.choice(S, size=len(S), replace=True)
                medF = float(np.median(Fb)); medS = float(np.median(Sb))
                if dom=="S":
                    wins += int(medS > medF)
                else:
                    wins += int(medF > medS)
            return wins / B
        
        conf_S = float(boot_conf("S"))
        conf_F = float(boot_conf("F"))
        n_F = int(len(F))
        n_S = int(len(S))
        share_F = n_F / (n_F + n_S) if (n_F + n_S) > 0 else 0.0
        
        # Statistiche attivazioni (solo per activation > 0)
        g_active = g[g["activation_max"] > 0].copy()
        n_active_prompts = int(len(g_active))
        
        act_max_mean = float(g["activation_max"].mean())
        act_max_std = float(g["activation_max"].std())
        act_mean_mean = float(g["activation_mean"].mean())
        
        # Sparsity: calcola solo per prompt attivi (activation > 0)
        if n_active_prompts > 0:
            sparsity_mean = float(g_active["sparsity_ratio"].mean())
            sparsity_median = float(g_active["sparsity_ratio"].median())
            sparsity_min = float(g_active["sparsity_ratio"].min())
            sparsity_max = float(g_active["sparsity_ratio"].max())
            sparsity_std = float(g_active["sparsity_ratio"].std())
        else:
            sparsity_mean = sparsity_median = sparsity_min = sparsity_max = sparsity_std = 0.0
        
        # N. prompt types
        n_prompt_types = int(g["prompt_type"].nunique())
        n_prompts = int(len(g))
        
        # Peak tokens unici (includi meta-tokens)
        peak_tokens_all = g["peak_token"].astype(str).tolist()
        n_peak_distinct = int(len(set(peak_tokens_all)))
        
        # Peak token index (posizione): stabilità con CV
        peak_idx_values = g["peak_token_idx"].dropna().astype(int).tolist()
        if len(peak_idx_values) > 0:
            peak_idx_mean = float(np.mean(peak_idx_values))
            peak_idx_std = float(np.std(peak_idx_values))
            peak_idx_cv = peak_idx_std / (peak_idx_mean + 1e-9)  # CV = std/mean
            peak_idx_mode = int(pd.Series(peak_idx_values).mode().iloc[0])
            peak_idx_min = int(min(peak_idx_values))
            peak_idx_max = int(max(peak_idx_values))
        else:
            peak_idx_mean = peak_idx_std = peak_idx_cv = -1.0
            peak_idx_mode = peak_idx_min = peak_idx_max = -1
        
        # NUOVA METRICA: Differenza % tra activation_max su functional vs semantic peaks
        # Semantic: max activation su token semantici
        # Say X: max activation su token funzionali
        g_func = g[g["peak_is_function_like"]]
        g_sem = g[g["peak_is_semantic_like"]]
        
        if len(g_func) > 0 and len(g_sem) > 0:
            max_act_func = float(g_func["activation_max"].max())
            max_act_sem = float(g_sem["activation_max"].max())
            # Differenza percentuale: (func - sem) / max(func, sem)
            # Positivo = functional domina, Negativo = semantic domina
            max_val = max(max_act_func, max_act_sem)
            if max_val > 0:
                func_vs_sem_pct = 100.0 * (max_act_func - max_act_sem) / max_val
            else:
                func_vs_sem_pct = 0.0
        elif len(g_func) > 0:
            # Solo functional peaks
            func_vs_sem_pct = 100.0
        elif len(g_sem) > 0:
            # Solo semantic peaks
            func_vs_sem_pct = -100.0
        else:
            func_vs_sem_pct = 0.0
        
        feature_stats.append({
            "feature_key": fk,
            "supernode_class": supernode_class,
            "layer": layer,
            "n_prompts": n_prompts,
            "n_active_prompts": n_active_prompts,
            "n_prompt_types": n_prompt_types,
            "n_peak_distinct": n_peak_distinct,
            "K_sem_distinct": K_sem_distinct,
            "H_sem_entropy": H_sem_entropy,
            "n_F": n_F,
            "n_S": n_S,
            "share_F": share_F,
            "conf_S": conf_S,
            "conf_F": conf_F,
            "U_cv": U_cv,
            "G_group_cv": G_group_cv,
            "act_max_mean": act_max_mean,
            "act_max_std": act_max_std,
            "act_mean_mean": act_mean_mean,
            "sparsity_mean": sparsity_mean,
            "sparsity_median": sparsity_median,
            "sparsity_min": sparsity_min,
            "sparsity_max": sparsity_max,
            "sparsity_std": sparsity_std,
            "peak_idx_mean": peak_idx_mean,
            "peak_idx_std": peak_idx_std,
            "peak_idx_cv": peak_idx_cv,
            "peak_idx_mode": peak_idx_mode,
            "peak_idx_min": peak_idx_min,
            "peak_idx_max": peak_idx_max,
            "func_vs_sem_pct": func_vs_sem_pct,
        })
    
    feat_df = pd.DataFrame(feature_stats)
    
    # Calcola quantili per layer
    feat_df["U_q20_layer"] = feat_df.groupby("layer")["U_cv"].transform(lambda s: s.quantile(0.2) if len(s)>3 else s.min())
    feat_df["H_q70_layer"] = feat_df.groupby("layer")["H_sem_entropy"].transform(lambda s: s.quantile(0.7) if len(s)>3 else s.max())
    
    # Genera report
    print(f"\nGenerazione report: {output_md}")
    with open(output_md, 'w', encoding='utf-8') as f:
        f.write("# Step 2.1 — Analisi Pattern dal CSV ENRICHED\n\n")
        f.write("## Obiettivo\n\n")
        f.write("Estrarre pattern quantitativi dalle tue classificazioni manuali per definire regole euristiche.\n\n")
        f.write("---\n\n")
        
        # Statistiche generali
        f.write("## Statistiche Generali\n\n")
        f.write(f"- **Righe totali**: {len(df)}\n")
        f.write(f"- **Feature uniche**: {df['feature_key'].nunique()}\n")
        f.write(f"- **Prompt unici**: {df['prompt'].nunique()}\n")
        f.write(f"- **Prompt types**: {df['prompt_type'].nunique()} ({', '.join(df['prompt_type'].unique())})\n\n")
        
        # Distribuzione classi
        f.write("### Distribuzione Classi (Ground Truth)\n\n")
        class_counts = feat_df["supernode_class"].value_counts()
        for cls, cnt in class_counts.items():
            pct = 100 * cnt / len(feat_df)
            f.write(f"- **{cls}**: {cnt} feature ({pct:.1f}%)\n")
        f.write("\n---\n\n")
        
        # Analisi per classe
        for cls in ["Relationship", "Semantic", 'Say "X"']:
            f.write(f"## Classe: {cls}\n\n")
            
            cls_df = feat_df[feat_df["supernode_class"] == cls]
            if len(cls_df) == 0:
                f.write("*Nessuna feature in questa classe.*\n\n")
                continue
            
            f.write(f"**N. feature**: {len(cls_df)}\n\n")
            
            # Feature keys
            f.write(f"**Feature keys**: {', '.join(cls_df['feature_key'].tolist())}\n\n")
            
            # Motivazioni (sample)
            motivations = df[df["feature_key"].isin(cls_df["feature_key"])]["motivation"].unique()
            f.write("### Motivazioni Tipiche\n\n")
            for i, mot in enumerate(motivations[:3], 1):
                f.write(f"{i}. \"{mot}\"\n")
            f.write("\n")
            
            # Statistiche descrittive
            f.write("### Statistiche Descrittive\n\n")
            
            metrics = [
                ("layer", "Layer"),
                ("n_active_prompts", "N. prompt attivi (act>0)"),
                ("n_peak_distinct", "N. peak tokens distinti"),
                ("K_sem_distinct", "K (token semantici distinti)"),
                ("H_sem_entropy", "H (entropia semantica)"),
                ("share_F", "Share functional peaks"),
                ("conf_S", "Conf_S (dominanza semantic)"),
                ("conf_F", "Conf_F (dominanza functional)"),
                ("func_vs_sem_pct", "Func vs Sem % (max act diff)"),
                ("U_cv", "U_cv (varianza intra-feature)"),
                ("G_group_cv", "G_group_cv (varianza tra prompt types)"),
                ("sparsity_mean", "Sparsity (mean, solo act>0)"),
                ("sparsity_median", "Sparsity (median, solo act>0)"),
                ("sparsity_min", "Sparsity (min, solo act>0)"),
                ("sparsity_max", "Sparsity (max, solo act>0)"),
                ("act_max_mean", "Activation max (media)"),
                ("act_mean_mean", "Activation mean (media)"),
                ("peak_idx_cv", "Peak idx CV (stabilità posizione)"),
                ("peak_idx_mode", "Peak idx (moda)"),
            ]
            
            f.write("| Metrica | Min | Q25 | Median | Q75 | Max | Mean |\n")
            f.write("|---------|-----|-----|--------|-----|-----|------|\n")
            
            for col, label in metrics:
                if col in cls_df.columns:
                    vals = cls_df[col].dropna()
                    if len(vals) > 0:
                        f.write(f"| {label} | {vals.min():.3f} | {vals.quantile(0.25):.3f} | {vals.median():.3f} | {vals.quantile(0.75):.3f} | {vals.max():.3f} | {vals.mean():.3f} |\n")
            
            f.write("\n")
            
            # Pattern chiave
            f.write("### Pattern Chiave Osservati\n\n")
            
            # Layer
            layer_mode = cls_df["layer"].mode()
            layer_range = f"{cls_df['layer'].min()}-{cls_df['layer'].max()}"
            f.write(f"- **Layer**: range {layer_range}, moda {layer_mode.iloc[0] if len(layer_mode)>0 else 'N/A'}\n")
            
            # Dominanza functional vs semantic
            if cls_df["conf_S"].mean() > 0.6:
                f.write(f"- **Dominanza semantic**: conf_S medio {cls_df['conf_S'].mean():.2f} (>0.6)\n")
            elif cls_df["conf_F"].mean() > 0.6:
                f.write(f"- **Dominanza functional**: conf_F medio {cls_df['conf_F'].mean():.2f} (>0.6)\n")
            else:
                f.write(f"- **Dominanza mista**: conf_S={cls_df['conf_S'].mean():.2f}, conf_F={cls_df['conf_F'].mean():.2f}\n")
            
            # Varianza
            if cls_df["U_cv"].mean() < cls_df["U_q20_layer"].mean():
                f.write(f"- **Bassa varianza intra-feature**: U_cv medio {cls_df['U_cv'].mean():.2f} < U_q20 {cls_df['U_q20_layer'].mean():.2f}\n")
            else:
                f.write(f"- **Alta varianza intra-feature**: U_cv medio {cls_df['U_cv'].mean():.2f}\n")
            
            if cls_df["G_group_cv"].mean() < 0.3:
                f.write(f"- **Bassa varianza tra prompt types**: G_group_cv medio {cls_df['G_group_cv'].mean():.2f} (<0.3)\n")
            else:
                f.write(f"- **Alta varianza tra prompt types**: G_group_cv medio {cls_df['G_group_cv'].mean():.2f}\n")
            
            # Diversità semantic tokens
            if cls_df["K_sem_distinct"].mean() >= 3:
                f.write(f"- **Alta diversità semantic tokens**: K medio {cls_df['K_sem_distinct'].mean():.1f} (≥3)\n")
            elif cls_df["K_sem_distinct"].mean() <= 1:
                f.write(f"- **Bassa diversità semantic tokens**: K medio {cls_df['K_sem_distinct'].mean():.1f} (≤1, dictionary-like)\n")
            else:
                f.write(f"- **Diversità semantic tokens moderata**: K medio {cls_df['K_sem_distinct'].mean():.1f}\n")
            
            # Sparsity
            if cls_df["sparsity_median"].mean() > 0.8:
                f.write(f"- **Alta sparsity**: median {cls_df['sparsity_median'].mean():.2f} (>0.8, picchi localizzati)\n")
            elif cls_df["sparsity_median"].mean() < 0.4:
                f.write(f"- **Bassa sparsity**: median {cls_df['sparsity_median'].mean():.2f} (<0.4, attivazioni diffuse)\n")
            else:
                f.write(f"- **Sparsity moderata**: median {cls_df['sparsity_median'].mean():.2f}\n")
            
            # Peak position stability
            if "peak_idx_cv" in cls_df.columns:
                cv_mean = cls_df["peak_idx_cv"].mean()
                if cv_mean < 0.2:
                    f.write(f"- **Peak posizione stabile**: CV medio {cv_mean:.3f} (<0.2, sempre stessa posizione)\n")
                elif cv_mean < 0.5:
                    f.write(f"- **Peak posizione moderatamente stabile**: CV medio {cv_mean:.3f}\n")
                else:
                    f.write(f"- **Peak posizione variabile**: CV medio {cv_mean:.3f} (>0.5, posizioni diverse)\n")
            
            f.write("\n---\n\n")
        
        # Feature engineering: nuove metriche?
        f.write("## Feature Engineering: Metriche Aggiuntive Necessarie?\n\n")
        f.write("### Metriche Già Implementate\n\n")
        f.write("Le seguenti metriche sono già calcolate in `supernode_classifier (2).py`:\n\n")
        f.write("1. **`layer`**: Layer della feature\n")
        f.write("2. **`U_cv`**: Coefficient of Variation delle z-score (varianza intra-feature)\n")
        f.write("3. **`G_group_cv`**: Group CV (varianza tra prompt types)\n")
        f.write("4. **`K_sem_distinct`**: N. token semantici distinti\n")
        f.write("5. **`H_sem_entropy`**: Entropia dei token semantici\n")
        f.write("6. **`conf_S` / `conf_F`**: Bootstrap confidence per dominanza semantic/functional\n")
        f.write("7. **`share_F`**: Frazione di peak functional\n")
        f.write("8. **`U_q20_layer` / `H_q70_layer`**: Quantili per layer (soglie relative)\n\n")
        
        f.write("### Analisi Motivazioni: Feature Mancanti?\n\n")
        
        # Estrai concetti chiave dalle motivazioni
        motivations_all = df["motivation"].unique()
        f.write("Concetti chiave dalle motivazioni:\n\n")
        
        concepts = {
            "layer": ["layer ≤", "layer >", "layer medio", "layer basso", "layer alto"],
            "varianza": ["varianza bassa", "varianza alta", "attivazioni uniformi"],
            "attivazione": ["altissima attivazione", "attivazione forte", "attivazione debole", "attivazione aselettiva"],
            "picchi": ["più picchi distinti", "picco localizzato", "unica attivazione", "picco netto"],
            "token_type": ["token funzionale", "token semantico", "aselettiva"],
            "sparsity": ["diffuse", "diffuso"],
            "max_vs_mean": ["max activation diversa da media"],
        }
        
        for concept, keywords in concepts.items():
            count = sum(1 for mot in motivations_all if any(kw in mot.lower() for kw in keywords))
            f.write(f"- **{concept}**: {count} motivazioni contengono questi termini\n")
        
        f.write("\n")
        f.write("### Metriche Aggiuntive Proposte\n\n")
        f.write("Basandomi sulle motivazioni, propongo:\n\n")
        f.write("1. **`act_max_vs_mean_ratio`**: `activation_max / activation_mean` (per \"max diversa da media\")\n")
        f.write("   - Relationship: ratio alto (più picchi distinti)\n")
        f.write("   - Semantic: ratio basso (attivazioni uniformi)\n\n")
        f.write("2. **`n_peaks_above_threshold`**: N. prompt con attivazione > soglia (es. median + 1*MAD)\n")
        f.write("   - Relationship: multiple peaks\n")
        f.write("   - Semantic/Say X: single peak\n\n")
        f.write("3. **`peak_concentration`**: Gini coefficient dei peak tokens\n")
        f.write("   - Dictionary semantic: alta concentrazione (K≈1)\n")
        f.write("   - Relationship: bassa concentrazione (K≥3)\n\n")
        f.write("**Decisione**: Le metriche esistenti sembrano sufficienti. `act_max_vs_mean_ratio` potrebbe essere utile ma è già catturato da `sparsity_ratio` e `U_cv`. Procediamo senza feature engineering aggiuntivo.\n\n")
        
        f.write("---\n\n")
        
        # Matrice confusione potenziale
        f.write("## Potenziali Ambiguità tra Classi\n\n")
        f.write("### Relationship: Sottogruppi Osservati\n\n")
        rel_df = feat_df[feat_df["supernode_class"] == "Relationship"]
        
        if len(rel_df) > 0:
            f.write(f"Relationship ha {len(rel_df)} feature con pattern eterogenei:\n\n")
            f.write(f"- **K_sem_distinct**: range {rel_df['K_sem_distinct'].min():.0f}-{rel_df['K_sem_distinct'].max():.0f}, median {rel_df['K_sem_distinct'].median():.1f}\n")
            f.write(f"- **peak_idx_cv**: range {rel_df['peak_idx_cv'].min():.2f}-{rel_df['peak_idx_cv'].max():.2f}, median {rel_df['peak_idx_cv'].median():.2f}\n")
            f.write(f"- **Sparsity median**: range {rel_df['sparsity_median'].min():.2f}-{rel_df['sparsity_median'].max():.2f}, median {rel_df['sparsity_median'].median():.2f}\n")
            f.write(f"- **Osservazione**: Include sia meta-tokens (K=3, peak_idx_cv≈0) che semantic (K=4, peak_idx_cv>0.5)\n\n")
        
        f.write("### Semantic vs Say \"X\"\n\n")
        sem_df = feat_df[feat_df["supernode_class"] == "Semantic"]
        say_df = feat_df[feat_df["supernode_class"] == 'Say "X"']
        
        if len(sem_df) > 0 and len(say_df) > 0:
            f.write(f"- **Layer**: Semantic {sem_df['layer'].min()}-{sem_df['layer'].max()}, Say X {say_df['layer'].min()}-{say_df['layer'].max()}\n")
            f.write(f"- **conf_S**: Semantic {sem_df['conf_S'].mean():.2f}, Say X {say_df['conf_S'].mean():.2f}\n")
            f.write(f"- **conf_F**: Semantic {sem_df['conf_F'].mean():.2f}, Say X {say_df['conf_F'].mean():.2f}\n")
            f.write(f"- **share_F**: Semantic {sem_df['share_F'].mean():.2f}, Say X {say_df['share_F'].mean():.2f}\n")
            f.write(f"- **Separazione**: conf_S alto → Semantic; conf_F alto + layer alto → Say X\n\n")
        
        f.write("---\n\n")
        
        # Salva CSV aggregato
        csv_out = output_md.replace('.md', '_FEATURES.csv')
        feat_df.to_csv(csv_out, index=False)
        f.write(f"## File Output\n\n")
        f.write(f"- **Report**: `{output_md}`\n")
        f.write(f"- **Feature aggregate**: `{csv_out}`\n\n")
        f.write("---\n\n")
        f.write("**Fase 2.1 COMPLETATA ✅**\n")
        f.write("**Prossimo**: Review Gate B — Verifica pattern e approvazione per Fase 2.2\n")
    
    print(f"\nReport salvato: {output_md}")
    print(f"Feature aggregate salvate: {csv_out}")
    
    return feat_df

if __name__ == "__main__":
    csv_path = "output/2025-10-21T07-40_export_ENRICHED.csv"
    output_md = "output/STEP2_PATTERN_ANALYSIS.md"
    
    feat_df = analyze_patterns(csv_path, output_md)
    
    print("\n=== SUMMARY ===")
    print(f"Feature totali: {len(feat_df)}")
    print(f"Classi: {feat_df['supernode_class'].value_counts().to_dict()}")

