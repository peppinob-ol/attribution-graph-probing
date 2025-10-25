
"""
supernode_classifier.py
Robust classifier (Schema/Relationship/semantic/say X) with diagnostics,
plus Phase 2 specific-label assignment.
- pred_label is ALWAYS the class prediction.
- review is a separate boolean flag (with why_review string).
- Say X specific label is index-aligned using peak_token_idx from the SAME row
  (that has the max activation for that feature_key), with look-ahead and safe fallbacks.
"""
from typing import Any, Dict, Mapping, Tuple, List
from collections import Counter
import re
import numpy as np
import pandas as pd

__all__ = ["classify_features", "build_feature_table", "decide_with_explain", "assign_specific_labels"]

_PUNCT_CHARS = r"""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~"""

def is_punct(tok: str) -> bool:
    t = str(tok).strip()
    return t != "" and all(ch in _PUNCT_CHARS for ch in t)

def is_function_like(tok: str) -> bool:
    t = str(tok).strip()
    if t == "":
        return False
    if is_punct(t):
        return True
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

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

# ---- Build feature-level diagnostics ----
def build_feature_table(raw_df: pd.DataFrame) -> pd.DataFrame:
    required = {"feature_key","layer","prompt","activation_max","peak_token"}
    missing = required - set(raw_df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df = raw_df.copy()
    df["feature_key"] = df["feature_key"].astype(str)
    df["layer"] = df["layer"].astype(int)
    df["prompt"] = df["prompt"].astype(str)
    df["peak_token"] = df["peak_token"].astype(str)

    df["prompt_type"] = df["prompt"].apply(prompt_type)
    df["peak_is_meta"] = (df["peak_token"].str.strip().str.lower() == df["prompt_type"].str.strip().str.lower())
    df["peak_is_function_like"] = df["peak_token"].apply(is_function_like)
    df["peak_is_semantic_like"] = ~df["peak_is_function_like"]

    df["z_layer"] = 0.0
    for L, gL in df.groupby("layer"):
        df.loc[gL.index, "z_layer"] = mad_z(gL["activation_max"].values)

    rows = []
    for fk, g in df.groupby("feature_key"):
        layer_mode = g["layer"].mode()
        layer = int(layer_mode.iat[0]) if not layer_mode.empty else int(g["layer"].iloc[0])

        z_all = g["z_layer"].values
        U = float(np.std(z_all) / (abs(np.mean(z_all)) + 1e-6))

        means_by_type = []
        for t, gt in g.groupby("prompt_type"):
            means_by_type.append(gt["z_layer"].mean())
        means_by_type = np.array(means_by_type) if len(means_by_type)>0 else np.array([0.0])
        pooled_std = np.std(z_all) + 1e-9
        G = float(np.std(means_by_type) / pooled_std)

        gn = g[~g["peak_is_meta"]].copy()
        F = gn.loc[gn["peak_is_function_like"], "z_layer"].values
        S = gn.loc[gn["peak_is_semantic_like"],  "z_layer"].values

        sem_tokens = gn.loc[gn["peak_is_semantic_like"], "peak_token"].astype(str).tolist()
        K = int(len(set(sem_tokens)))
        if len(sem_tokens)>0:
            cnt = np.array(list(tuple.__iter__(tuple(Counter(sem_tokens).values()))), dtype=float) if False else np.array(list(Counter(sem_tokens).values()), dtype=float)
            p = cnt / cnt.sum()
            H = float(-np.sum(p * np.log2(p+1e-12)))
        else:
            H = 0.0

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
        n_F = int(len(F)); n_S = int(len(S))

        rows.append({
            "feature_key": fk, "layer": layer, "U_cv": U, "G_group_cv": G,
            "K_sem_distinct": K, "H_sem_entropy": H,
            "conf_S": conf_S, "conf_F": conf_F, "n_F": n_F, "n_S": n_S
        })

    feat = pd.DataFrame(rows)
    feat["U_q20_layer"] = feat.groupby("layer")["U_cv"].transform(lambda s: s.quantile(0.2) if len(s)>3 else s.min())
    feat["H_q70_layer"] = feat.groupby("layer")["H_sem_entropy"].transform(lambda s: s.quantile(0.7) if len(s)>3 else s.max())
    feat["share_F"] = feat["n_F"] / (feat["n_F"] + feat["n_S"]).replace({0: np.nan})
    feat["share_F"] = feat["share_F"].fillna(0.0)
    return feat

# ---- Decision rules with Review (separate flag) ----
def decide_with_explain(r: Mapping[str, Any]) -> Tuple[str, bool, float, str, Dict[str, float]]:
    layer = int(r["layer"]); K = int(r["K_sem_distinct"])
    H = float(r["H_sem_entropy"]); Hq70 = float(r["H_q70_layer"])
    confS = float(r["conf_S"]); confF = float(r["conf_F"])
    nS = int(r["n_S"]); nF = int(r["n_F"])
    shareF = float(r["share_F"])
    U = float(r["U_cv"]); Uq20 = float(r["U_q20_layer"]); G = float(r["G_group_cv"])

    # Main rules -> base label
    if layer <= 3 and (U <= Uq20) and (G <= 0.3):
        label, rule = "Schema", "schema_early"
    elif (layer <= 5) and (confF <= 0.1) and (K >= 3 or H >= Hq70):
        label, rule = "Relationship", "relationship_lowlayer"
    elif confS >= 0.6:
        label, rule = "semantic", "semantic_dominance"
    elif (layer <= 2) and (confF >= 0.6) and (K <= 1) and (confS < 0.55):
        label, rule = "semantic", "semantic_anchor_low"
    elif layer <= 10 and (confF >= 0.6) and (K <= 3):
        label, rule = "say X", "sayx_lowmid"
    elif (layer > 10) and (confF >= 0.6) and (shareF >= 0.6) and (K <= 3):
        label, rule = "say X", "sayx_high_dual"
    else:
        votes = Counter()
        votes["Schema"] += int(layer <= 3 and U <= Uq20 and G <= 0.5)
        votes["Relationship"] += int(layer <= 5 and confS < 0.6 and confF < 0.6 and K >= 2)
        votes["semantic"] += int(confS >= 0.55 or (layer > 10 and confF >= 0.6 and shareF < 0.6 and K <= 2))
        if layer > 10:
            votes["say X"] += int((confF >= 0.55) and (shareF >= 0.6) and (K <= 3))
        else:
            votes["say X"] += int((confF >= 0.55) and (K <= 3) and layer >= 3)
        label = max(votes.items(), key=lambda kv: kv[1])[0]
        rule = f"fallback_{label}"
    used_fallback = rule.startswith("fallback")

    # Confidence
    if label == "Schema":
        cU = clamp((Uq20 / (U + 1e-9)), 0, 1)
        cG = clamp((0.3 / (G + 1e-9)), 0, 1)
        conf = 0.5 * cU + 0.5 * cG
    elif label == "Relationship":
        cF = clamp(1.0 - confF, 0, 1)
        cD = 1.0 if (K >= 3 or H >= Hq70) else 0.0
        conf = 0.6 * cF + 0.4 * cD
    elif label == "semantic":
        conf = max(confS, 1.0 - confF) if rule != "semantic_dominance" else confS
    else:  # say X
        conf = (0.5*confF + 0.5*shareF) if rule=="sayx_high_dual" else confF

    # Review decision (separate from pred_label)
    review = False
    reasons: List[str] = []
    if used_fallback:
        review = True; reasons.append("fallback_decision")
    if label in ("semantic","say X") and max(confS, confF) < 0.6:
        review = True; reasons.append("low_signal_dominance")
    if label in ("Schema","Relationship") and conf < 0.5:
        review = True; reasons.append("low_confidence")
    why_review = ";".join(reasons)

    diags = {
        "layer": float(layer), "K": float(K), "H": float(H), "H_q70": float(Hq70),
        "conf_S": float(confS), "conf_F": float(confF), "share_F": float(shareF),
        "U_cv": float(U), "U_q20_layer": float(Uq20), "G_group_cv": float(G),
    }
    return label, review, float(conf), why_review, diags

def classify_features(raw_df: pd.DataFrame) -> pd.DataFrame:
    feat = build_feature_table(raw_df)
    rows = []
    for _, r in feat.iterrows():
        base, review, conf, why, diag = decide_with_explain(r)
        rows.append({
            "feature_key": r["feature_key"],
            "layer": int(r["layer"]),
            "pred_label": base,             # ALWAYS the class
            "base_label": base,             # identical (compat)
            "rule": "computed_in_decide",
            "used_fallback": why.startswith("fallback"),
            "confidence": round(conf,3),
            "review": review,
            "why_review": why,
            "conf_S": round(diag["conf_S"],3),
            "conf_F": round(diag["conf_F"],3),
            "share_F": round(diag["share_F"],3),
            "K_sem_distinct": int(diag["K"]),
            "H_sem_entropy": round(diag["H"],3),
            "H_q70_layer": round(diag["H_q70"],3),
            "U_cv": round(diag["U_cv"],3),
            "U_q20_layer": round(diag["U_q20_layer"],3),
            "G_group_cv": round(diag["G_group_cv"],3),
        })
    return pd.DataFrame(rows)

# ---- Phase 2: Specific label assignment ----

def _prompt_suffix(prompt: str) -> str:
    return prompt.split(":", 1)[1] if ":" in prompt else prompt

def _tokenize_words_and_punct(text: str):
    return re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9\-]+|[^\sA-Za-zÀ-ÖØ-öø-ÿ0-9]", text)

def _next_content_token(prompt: str, peak_tok: str) -> str:
    # legacy string-match helper (used only as last-resort fallback)
    suf = _prompt_suffix(prompt)
    toks = _tokenize_words_and_punct(suf)
    idxs = [i for i,t in enumerate(toks) if t == peak_tok]
    if not idxs:
        idxs = [i for i,t in enumerate(toks) if t.lower() == str(peak_tok).lower()]
    if not idxs:
        return ""
    i = idxs[0]
    for j in range(i+1, len(toks)):
        cand = toks[j]
        if is_function_like(cand) or is_punct(cand):
            continue
        return cand
    return ""

def _next_content_by_index(prompt: str, peak_idx: int, lookahead: int = 5) -> str:
    """
    Return the first non-functional token AFTER position `peak_idx` in the same prompt,
    scanning up to `lookahead` tokens ahead. Uses a simple word+punct tokenizer.
    """
    suf = _prompt_suffix(prompt)
    toks = _tokenize_words_and_punct(suf)
    try:
        i = int(peak_idx)
    except Exception:
        return ""
    if i < -1 or i >= len(toks):
        i = max(-1, min(i, len(toks)-1))
    for j in range(i+1, min(len(toks), i+1+lookahead)):
        cand = toks[j]
        if is_function_like(cand) or is_punct(cand):
            continue
        return cand
    return ""

def assign_specific_labels(raw_df: pd.DataFrame, labeled_features: pd.DataFrame) -> pd.DataFrame:
    df = raw_df.copy()
    df["activation_max"] = df["activation_max"].astype(float)
    # get the SAME row where activation_max is maximal per feature_key
    idx = df.groupby("feature_key")["activation_max"].idxmax()
    max_rows = df.loc[idx, ["feature_key","prompt","peak_token","peak_token_idx","activation_max"]].rename(
        columns={"peak_token":"peak_token_at_max", "peak_token_idx":"peak_token_idx_at_max", "activation_max":"activation_at_max"}
    )
    merged = labeled_features.merge(max_rows, on="feature_key", how="left")

    specs: List[str] = []
    for _, r in merged.iterrows():
        base = r["pred_label"]
        fk = r["feature_key"]
        if base == "Schema":
            lab = "Schema"
        elif base == "Relationship":
            lab = "Relationship"
        elif base == "semantic":
            sub = raw_df[raw_df["feature_key"] == fk].copy()
            sub["is_func"] = sub["peak_token"].apply(is_function_like)
            sub["is_meta"] = sub.apply(lambda x: x["peak_token"].strip().lower()==prompt_type(x["prompt"]).strip().lower(), axis=1)
            cand = sub[(~sub["is_func"]) & (~sub["is_meta"])]
            if cand.empty:
                row = sub.loc[sub["activation_max"].astype(float).idxmax()]
                lab = str(row["peak_token"])
            else:
                row = cand.loc[cand["activation_max"].astype(float).idxmax()]
                lab = str(row["peak_token"])
        elif base == "say X":
            # Robust: align by index and prompt from the SAME max row
            idx_at_max = r.get("peak_token_idx_at_max", None)
            next_tok = _next_content_by_index(str(r["prompt"]), int(idx_at_max) if pd.notnull(idx_at_max) else -1, lookahead=5)
            if not next_tok:
                # Last resort: string-based search
                next_tok = _next_content_token(str(r["prompt"]), str(r["peak_token_at_max"]))
            lab = f"Say ({next_tok})" if next_tok else "Say (?)"
        else:
            lab = str(base)
        specs.append(lab)

    out = merged.copy()
    out["specific_label"] = specs
    return out
