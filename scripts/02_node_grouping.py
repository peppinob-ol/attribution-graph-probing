"""
02_node_grouping.py

Pipeline per classificare features in supernodi (Schema/Relationship/Semantic/Say X)
e assegnare nomi specifici "supernode_name".

Step 1: Preparazione dataset (peak_token_type e target_tokens)
Step 2-4: Classificazione e naming (da implementare)

Usage:
    python scripts/02_node_grouping.py --input output/2025-10-21T07-40_export.csv --output output/2025-10-21T07-40_GROUPED.csv
"""

import argparse
import json
import re
from pathlib import Path
from string import punctuation
from typing import List, Dict, Tuple, Optional, Any
import pandas as pd
import numpy as np


# ============================================================================
# STEP 1: CONFIGURAZIONE E CLASSIFICAZIONE TOKEN
# ============================================================================

# Dizionario token funzionali con direzione di ricerca per target_token
# forward: cerca il primo token semantico DOPO il peak_token
# backward: cerca il primo token semantico PRIMA del peak_token
# both: cerca sia prima che dopo (restituisce entrambi se trovati)
FUNCTIONAL_TOKEN_MAP = {
    # Articoli
    "the": "forward",
    "a": "forward",
    "an": "forward",
    
    # Preposizioni comuni
    "of": "forward",
    "in": "forward",
    "to": "forward",
    "for": "forward",
    "with": "forward",
    "on": "forward",
    "at": "forward",
    "from": "forward",
    "by": "forward",
    "about": "forward",
    "as": "forward",
    "over": "forward",
    "under": "forward",
    "between": "forward",
    "through": "forward",
    
    # Verbi ausiliari e copule
    "is": "forward",
    "are": "forward",
    "was": "forward",
    "were": "forward",
    "be": "forward",
    "been": "forward",
    "being": "forward",
    "has": "forward",
    "have": "forward",
    "had": "forward",
    "do": "forward",
    "does": "forward",
    "did": "forward",
    "can": "forward",
    "could": "forward",
    "will": "forward",
    "would": "forward",
    "should": "forward",
    "may": "forward",
    "might": "forward",
    "must": "forward",
    
    # Congiunzioni (guardano in entrambe le direzioni)
    "and": "both",
    "or": "both",
    "but": "both",
    "if": "forward",
    "because": "forward",
    "so": "forward",
    "than": "forward",
    "that": "forward",
    
    # Pronomi
    "it": "forward",
    "its": "forward",
    "this": "forward",
    "these": "forward",
    "those": "forward",
    "which": "forward",
    "who": "forward",
    "whom": "forward",
    "whose": "forward",
    "where": "forward",
    "when": "forward",
}


def is_punctuation(token: str) -> bool:
    """Verifica se un token è solo punteggiatura."""
    token_clean = str(token).strip()
    return token_clean != "" and all(ch in punctuation for ch in token_clean)


def is_function_like(token: str) -> bool:
    """
    Euristica per token funzionali non nel dizionario:
    - lunghezza <= 3 caratteri
    - tutto lowercase
    - non numeri
    - non acronimi uppercase (es. USA, UK)
    """
    token_stripped = str(token).strip()
    token_clean = token_stripped.lower()
    
    if len(token_clean) == 0 or len(token_clean) > 3:
        return False
    if token_clean.isdigit():
        return False
    
    # Escludi acronimi uppercase (USA, UK, etc.)
    if token_stripped.isupper() and len(token_stripped) >= 2:
        return False
    
    return token_clean.isalpha()


def classify_peak_token(token: str) -> str:
    """
    Classifica un peak_token come 'functional' o 'semantic'.
    
    functional: punteggiatura, token nel dizionario, o token function-like
    semantic: tutto il resto
    """
    token_clean = str(token).strip()
    token_lower = token_clean.lower()
    
    # Punteggiatura → functional
    if is_punctuation(token_clean):
        return "functional"
    
    # Nel dizionario → functional
    if token_lower in FUNCTIONAL_TOKEN_MAP:
        return "functional"
    
    # Euristica function-like → functional
    if is_function_like(token_clean):
        return "functional"
    
    # Default: semantic
    return "semantic"


def get_direction_for_functional(token: str) -> str:
    """
    Restituisce la direzione di ricerca per un token funzionale.
    
    Returns:
        "forward", "backward", "both", o "both" (default per punteggiatura)
    """
    token_lower = str(token).strip().lower()
    
    # Se nel dizionario, usa la direzione specificata
    if token_lower in FUNCTIONAL_TOKEN_MAP:
        return FUNCTIONAL_TOKEN_MAP[token_lower]
    
    # Punteggiatura: guarda in entrambe le direzioni
    if is_punctuation(token):
        return "both"
    
    # Default: forward
    return "forward"


def tokenize_prompt_fallback(prompt: str) -> List[str]:
    """
    Tokenizzazione fallback word+punct quando tokens JSON non disponibili.
    Pattern: cattura parole (lettere, numeri, trattini) e punteggiatura separatamente.
    """
    return re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9\-]+|[^\sA-Za-zÀ-ÖØ-öø-ÿ0-9]", prompt)


def find_target_tokens(
    tokens: List[str],
    peak_idx: int,
    direction: str,
    window: int = 7
) -> List[Dict[str, Any]]:
    """
    Cerca i target_tokens (primi token semantici) in una o più direzioni.
    
    Args:
        tokens: lista di token del prompt
        peak_idx: indice del peak_token (0-based, BOS già escluso se necessario)
        direction: "forward", "backward", o "both"
        window: finestra massima di ricerca
    
    Returns:
        Lista di dict con chiavi: token, index, distance, direction
        Lista vuota se nessun target trovato
    """
    targets = []
    
    def search_direction(start_idx: int, step: int, dir_name: str) -> Optional[Dict[str, Any]]:
        """Helper per cercare in una direzione."""
        for distance in range(1, window + 1):
            idx = start_idx + (distance * step)
            if idx < 0 or idx >= len(tokens):
                break
            
            candidate = tokens[idx]
            candidate_type = classify_peak_token(candidate)
            
            if candidate_type == "semantic":
                return {
                    "token": candidate,
                    "index": idx,
                    "distance": distance,
                    "direction": dir_name
                }
        return None
    
    # Cerca in base alla direzione
    if direction in ("forward", "both"):
        target_fwd = search_direction(peak_idx, 1, "forward")
        if target_fwd:
            targets.append(target_fwd)
    
    if direction in ("backward", "both"):
        target_bwd = search_direction(peak_idx, -1, "backward")
        if target_bwd:
            targets.append(target_bwd)
    
    return targets


def prepare_dataset(
    df: pd.DataFrame,
    tokens_json: Optional[Dict[str, Any]] = None,
    window: int = 7,
    verbose: bool = True
) -> pd.DataFrame:
    """
    Step 1: Arricchisce il dataframe con peak_token_type e target_tokens.
    
    Args:
        df: DataFrame con colonne: feature_key, prompt, peak_token, peak_token_idx
        tokens_json: Opzionale, JSON con attivazioni (per accedere a tokens array)
        window: Finestra di ricerca per target_tokens
        verbose: Stampa info di debug
    
    Returns:
        DataFrame arricchito con colonne:
        - peak_token_type: "functional" o "semantic"
        - target_tokens: lista JSON di dict con token, index, distance, direction
        - tokens_source: "json" o "fallback"
    """
    df = df.copy()
    
    # Prepara lookup tokens dal JSON (se disponibile)
    tokens_lookup = {}
    if tokens_json and "results" in tokens_json:
        for result in tokens_json["results"]:
            prompt = result.get("prompt", "")
            tokens = result.get("tokens", [])
            if prompt and tokens:
                tokens_lookup[prompt] = tokens
    
    # Nuove colonne
    df["peak_token_type"] = ""
    df["target_tokens"] = ""
    df["tokens_source"] = ""
    
    for idx, row in df.iterrows():
        peak_token = row["peak_token"]
        peak_idx = int(row["peak_token_idx"]) if pd.notna(row["peak_token_idx"]) else None
        prompt = row["prompt"]
        
        # Classifica peak_token
        peak_type = classify_peak_token(peak_token)
        df.at[idx, "peak_token_type"] = peak_type
        
        # Se semantic, target_token = peak_token stesso
        if peak_type == "semantic":
            targets = [{
                "token": peak_token,
                "index": peak_idx,
                "distance": 0,
                "direction": "self"
            }]
            df.at[idx, "target_tokens"] = json.dumps(targets)
            df.at[idx, "tokens_source"] = "n/a"
            continue
        
        # Se functional, cerca target_tokens
        # 1. Prova con tokens dal JSON
        tokens = tokens_lookup.get(prompt)
        tokens_source = "json"
        
        # 2. Fallback: tokenizza il prompt
        if not tokens:
            tokens = tokenize_prompt_fallback(prompt)
            tokens_source = "fallback"
        
        df.at[idx, "tokens_source"] = tokens_source
        
        # Determina direzione di ricerca
        direction = get_direction_for_functional(peak_token)
        
        # Aggiusta l'indice se usiamo tokenizzazione fallback
        # Il CSV ha peak_token_idx che esclude BOS (1-based rispetto al JSON originale)
        # Ma il prompt non ha BOS, quindi dobbiamo sottrarre 1
        adjusted_idx = peak_idx
        if tokens_source == "fallback" and peak_idx is not None and peak_idx > 0:
            adjusted_idx = peak_idx - 1
        
        # Cerca target_tokens
        if adjusted_idx is not None and 0 <= adjusted_idx < len(tokens):
            targets = find_target_tokens(tokens, adjusted_idx, direction, window)
        else:
            targets = []
        
        df.at[idx, "target_tokens"] = json.dumps(targets) if targets else "[]"
    
    if verbose:
        n_functional = (df["peak_token_type"] == "functional").sum()
        n_semantic = (df["peak_token_type"] == "semantic").sum()
        n_json = (df["tokens_source"] == "json").sum()
        n_fallback = (df["tokens_source"] == "fallback").sum()
        
        print(f"\n=== Step 1: Preparazione Dataset ===")
        print(f"Peak token types:")
        print(f"  - functional: {n_functional} ({n_functional/len(df)*100:.1f}%)")
        print(f"  - semantic:   {n_semantic} ({n_semantic/len(df)*100:.1f}%)")
        print(f"\nTokens source:")
        print(f"  - json:     {n_json}")
        print(f"  - fallback: {n_fallback}")
        print(f"  - n/a:      {len(df) - n_json - n_fallback}")
        
        # Conta target_tokens vuoti (Say ? candidati)
        df["_n_targets"] = df["target_tokens"].apply(lambda x: len(json.loads(x)) if x else 0)
        n_no_target = ((df["peak_token_type"] == "functional") & (df["_n_targets"] == 0)).sum()
        if n_no_target > 0:
            print(f"\nWARNING: {n_no_target} functional tokens senza target (-> Say (?) candidati)")
        df.drop(columns=["_n_targets"], inplace=True)
    
    return df


# ============================================================================
# STEP 2: CLASSIFICAZIONE NODI (AGGREGAZIONE + DECISION TREE)
# ============================================================================

# Soglie standard (parametriche)
DEFAULT_THRESHOLDS = {
    # Dictionary Semantic
    "dict_peak_consistency_min": 0.8,
    "dict_n_distinct_peaks_max": 1,
    
    # Say X
    "sayx_func_vs_sem_min": 50.0,
    "sayx_conf_f_min": 0.90,
    "sayx_layer_min": 7,
    
    # Relationship
    "rel_sparsity_max": 0.45,
    
    # Semantic (concept)
    "sem_layer_max": 3,
    "sem_conf_s_min": 0.50,
    "sem_func_vs_sem_max": 50.0,
}


def calculate_peak_consistency(group_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calcola peak_consistency per una feature (group by feature_key).
    
    Metrica: "Quando il token X appare nel prompt, e' SEMPRE il peak_token?"
    
    Args:
        group_df: DataFrame con righe per una singola feature
        
    Returns:
        dict con:
            - peak_consistency_main: consistency del token piu' frequente come peak
            - n_distinct_peaks: numero di token distinti come peak
            - main_peak_token: token piu' frequente come peak
    """
    # Dizionario: token -> {as_peak: count, in_prompt: count}
    token_stats = {}
    
    for _, row in group_df.iterrows():
        peak_token = str(row['peak_token']).strip().lower()
        
        # Conta questo token come peak
        if peak_token not in token_stats:
            token_stats[peak_token] = {'as_peak': 0, 'in_prompt': 0}
        token_stats[peak_token]['as_peak'] += 1
        
        # Conta occorrenze nel prompt
        # Preferisci tokens JSON, fallback su prompt text
        if 'tokens' in row and pd.notna(row['tokens']):
            try:
                tokens = json.loads(row['tokens'])
                tokens_lower = [str(t).strip().lower() for t in tokens]
            except:
                tokens_lower = str(row['prompt']).lower().replace(',', ' , ').replace('.', ' . ').split()
        else:
            tokens_lower = str(row['prompt']).lower().replace(',', ' , ').replace('.', ' . ').split()
        
        # Conta occorrenze di ogni token
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
    
    # Trova token piu' frequente come peak
    if token_consistencies:
        most_frequent_peak = max(token_consistencies.items(), 
                                  key=lambda x: x[1]['as_peak'])
        main_peak_consistency = most_frequent_peak[1]['consistency']
        main_peak_token = most_frequent_peak[0]
    else:
        main_peak_consistency = 0.0
        main_peak_token = None
    
    # Numero di token distinti come peak
    n_distinct_peaks = len([t for t, s in token_consistencies.items() 
                            if s['as_peak'] > 0])
    
    return {
        'peak_consistency_main': main_peak_consistency,
        'n_distinct_peaks': n_distinct_peaks,
        'main_peak_token': main_peak_token
    }


def aggregate_feature_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggrega metriche per feature_key per la classificazione.
    
    Args:
        df: DataFrame con righe per feature×prompt
        
    Returns:
        DataFrame con una riga per feature e colonne:
        - feature_key, layer
        - peak_consistency_main, n_distinct_peaks, main_peak_token
        - func_vs_sem_pct, conf_F, conf_S
        - sparsity_median, K_sem_distinct
        - n_active_prompts
    """
    feature_stats = []
    
    for feature_key, group in df.groupby('feature_key'):
        layer = int(group['layer'].iloc[0])
        
        # Peak consistency
        consistency_metrics = calculate_peak_consistency(group)
        
        # Conta peak funzionali vs semantici (SOLO per prompt attivi, activation_max > 0)
        g_active = group[group['activation_max'] > 0]
        n_functional_peaks = (g_active['peak_token_type'] == 'functional').sum()
        n_semantic_peaks = (g_active['peak_token_type'] == 'semantic').sum()
        n_total_peaks = len(g_active)
        
        share_F = n_functional_peaks / n_total_peaks if n_total_peaks > 0 else 0.0
        
        # Bootstrap confidence (semplificato: usa share come proxy)
        conf_F = share_F
        conf_S = 1.0 - share_F
        
        # func_vs_sem_pct: differenza tra max activation su functional vs semantic
        # (SOLO per prompt attivi, activation_max > 0)
        g_func = g_active[g_active['peak_token_type'] == 'functional']
        g_sem = g_active[g_active['peak_token_type'] == 'semantic']
        
        if len(g_func) > 0 and len(g_sem) > 0:
            max_act_func = float(g_func['activation_max'].max())
            max_act_sem = float(g_sem['activation_max'].max())
            max_val = max(max_act_func, max_act_sem)
            if max_val > 0:
                func_vs_sem_pct = 100.0 * (max_act_func - max_act_sem) / max_val
            else:
                func_vs_sem_pct = 0.0
        elif len(g_func) > 0:
            func_vs_sem_pct = 100.0
        elif len(g_sem) > 0:
            func_vs_sem_pct = -100.0
        else:
            func_vs_sem_pct = 0.0
        
        # Sparsity: calcola solo per prompt attivi (activation > 0)
        n_active_prompts = len(g_active)
        
        if n_active_prompts > 0 and 'sparsity_ratio' in group.columns:
            sparsity_median = float(g_active['sparsity_ratio'].median())
        else:
            sparsity_median = 0.0
        
        # K_sem_distinct: numero di token semantici distinti
        sem_tokens = group[group['peak_token_type'] == 'semantic']['peak_token'].astype(str).tolist()
        K_sem_distinct = len(set([t.strip().lower() for t in sem_tokens]))
        
        feature_stats.append({
            'feature_key': feature_key,
            'layer': layer,
            'peak_consistency_main': consistency_metrics['peak_consistency_main'],
            'n_distinct_peaks': consistency_metrics['n_distinct_peaks'],
            'main_peak_token': consistency_metrics['main_peak_token'],
            'func_vs_sem_pct': func_vs_sem_pct,
            'conf_F': conf_F,
            'conf_S': conf_S,
            'share_F': share_F,
            'sparsity_median': sparsity_median,
            'K_sem_distinct': K_sem_distinct,
            'n_active_prompts': n_active_prompts,
            'n_prompts': len(group),
        })
    
    return pd.DataFrame(feature_stats)


def classify_node(
    metrics: Dict[str, Any],
    thresholds: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Classifica un nodo basandosi su metriche aggregate.
    
    Albero decisionale V4 Final con peak_consistency:
    1. IF peak_consistency >= 0.8 AND n_distinct_peaks <= 1 -> Semantic (Dictionary)
    2. ELSE IF func_vs_sem_pct >= 50 AND conf_F >= 0.90 AND layer >= 7 -> Say "X"
    3. ELSE IF sparsity_median < 0.45 -> Relationship
    4. ELSE IF layer <= 3 OR conf_S >= 0.50 OR func_vs_sem_pct < 50 -> Semantic (Concept)
    5. ELSE -> Review
    
    Args:
        metrics: dict con metriche aggregate per una feature
        thresholds: dict con soglie (usa DEFAULT_THRESHOLDS se None)
        
    Returns:
        dict con:
            - pred_label: "Semantic", "Say \"X\"", "Relationship"
            - subtype: "Dictionary", "Concept", None
            - confidence: float
            - review: bool
            - why_review: str
    """
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS
    
    peak_cons = metrics.get('peak_consistency_main', 0.0)
    n_peaks = metrics.get('n_distinct_peaks', 0)
    func_vs_sem = metrics.get('func_vs_sem_pct', 0.0)
    conf_F = metrics.get('conf_F', 0.0)
    conf_S = metrics.get('conf_S', 0.0)
    sparsity = metrics.get('sparsity_median', 0.0)
    layer = metrics.get('layer', 0)
    
    # Regola 1: Dictionary Semantic (priorita' massima)
    if (peak_cons >= thresholds['dict_peak_consistency_min'] and 
        n_peaks <= thresholds['dict_n_distinct_peaks_max']):
        return {
            'pred_label': 'Semantic',
            'subtype': 'Dictionary',
            'confidence': peak_cons,
            'review': False,
            'why_review': ''
        }
    
    # Regola 2: Say "X"
    if (func_vs_sem >= thresholds['sayx_func_vs_sem_min'] and 
        conf_F >= thresholds['sayx_conf_f_min'] and 
        layer >= thresholds['sayx_layer_min']):
        return {
            'pred_label': 'Say "X"',
            'subtype': None,
            'confidence': conf_F,
            'review': False,
            'why_review': ''
        }
    
    # Regola 3: Relationship
    if sparsity < thresholds['rel_sparsity_max']:
        return {
            'pred_label': 'Relationship',
            'subtype': None,
            'confidence': 1.0,
            'review': False,
            'why_review': ''
        }
    
    # Regola 4: Semantic (concept / altri)
    if (layer <= thresholds['sem_layer_max'] or 
        conf_S >= thresholds['sem_conf_s_min'] or 
        func_vs_sem < thresholds['sem_func_vs_sem_max']):
        
        # Calcola confidence
        if layer <= thresholds['sem_layer_max']:
            confidence = 0.9  # Alta per layer basso (fallback)
            subtype = 'Dictionary (fallback)'
        elif func_vs_sem < thresholds['sem_func_vs_sem_max']:
            confidence = max(0.7, 1.0 - abs(func_vs_sem) / 100)
            subtype = 'Concept'
        else:
            confidence = conf_S
            subtype = 'Concept'
        
        return {
            'pred_label': 'Semantic',
            'subtype': subtype,
            'confidence': confidence,
            'review': False,
            'why_review': ''
        }
    
    # Regola 5: Review
    return {
        'pred_label': 'Semantic',  # Default conservativo
        'subtype': 'Ambiguous',
        'confidence': 0.3,
        'review': True,
        'why_review': f"Ambiguous: peak_cons={peak_cons:.2f}, n_peaks={n_peaks}, func_vs_sem={func_vs_sem:.1f}%, layer={layer}"
    }


def classify_nodes(
    df: pd.DataFrame,
    thresholds: Optional[Dict[str, float]] = None,
    verbose: bool = True
) -> pd.DataFrame:
    """
    Step 2: Classifica tutti i nodi nel dataframe.
    
    Args:
        df: DataFrame preparato con Step 1
        thresholds: dict con soglie (usa DEFAULT_THRESHOLDS se None)
        verbose: stampa info
        
    Returns:
        DataFrame con colonne aggiuntive:
        - pred_label, subtype, confidence, review, why_review
    """
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS
    
    # Aggrega metriche per feature
    if verbose:
        print(f"\n=== Step 2: Classificazione Nodi ===")
        print(f"Aggregazione metriche per {df['feature_key'].nunique()} feature...")
    
    feature_metrics_df = aggregate_feature_metrics(df)
    
    # Classifica ogni feature
    classifications = []
    for _, row in feature_metrics_df.iterrows():
        metrics = row.to_dict()
        result = classify_node(metrics, thresholds)
        result['feature_key'] = row['feature_key']
        classifications.append(result)
    
    classifications_df = pd.DataFrame(classifications)
    
    # Merge con il dataframe originale
    df_classified = df.merge(
        classifications_df[['feature_key', 'pred_label', 'subtype', 'confidence', 'review', 'why_review']],
        on='feature_key',
        how='left'
    )
    
    if verbose:
        # Statistiche
        label_counts = classifications_df['pred_label'].value_counts()
        print(f"\nClassificazione completata:")
        for label, count in label_counts.items():
            pct = 100 * count / len(classifications_df)
            print(f"  - {label:15s}: {count:3d} ({pct:5.1f}%)")
        
        n_review = classifications_df['review'].sum()
        if n_review > 0:
            print(f"\nWARNING: {n_review} feature richiedono review")
            review_features = classifications_df[classifications_df['review']]['feature_key'].tolist()
            print(f"  Feature keys: {review_features[:5]}{'...' if len(review_features) > 5 else ''}")
    
    return df_classified


# ============================================================================
# STEP 3: NAMING SUPERNODI
# ============================================================================

def normalize_token_for_naming(token: str, all_occurrences: List[str]) -> str:
    """
    Normalizza un token per il naming mantenendo maiuscola se presente.
    
    Args:
        token: token da normalizzare
        all_occurrences: tutte le occorrenze di questo token nel dataset
        
    Returns:
        token normalizzato
    """
    # Strip whitespace
    token = str(token).strip()
    
    # Rimuovi punteggiatura trailing
    token = token.rstrip(punctuation)
    
    # Se vuoto, return
    if not token:
        return token
    
    # Controlla se esiste almeno un'occorrenza con prima lettera maiuscola
    has_uppercase = any(
        occ.strip() and occ.strip()[0].isupper() 
        for occ in all_occurrences 
        if occ.strip()
    )
    
    if has_uppercase:
        # Mantieni la prima occorrenza con maiuscola
        for occ in all_occurrences:
            occ_clean = occ.strip()
            if occ_clean and occ_clean[0].isupper():
                return occ_clean.rstrip(punctuation)
    
    # Altrimenti lowercase
    return token.lower()


def name_relationship_node(
    feature_key: str,
    feature_records: pd.DataFrame,
    activations_data: Optional[Dict] = None
) -> str:
    """
    Naming per nodi Relationship: "(X) related"
    dove X è il primo token semantico con max attivazione dal prompt originale.
    
    Args:
        feature_key: chiave della feature (es. "1_12928")
        feature_records: DataFrame con tutti i record per questa feature
        activations_data: Dict con 'tokens' e 'counts' dal JSON attivazioni
        
    Returns:
        supernode_name: str (es. "(capital) related")
    """
    # Trova record con activation_max massima
    max_record = feature_records.loc[feature_records['activation_max'].idxmax()]
    
    # Estrai primo token semantico con max attivazione dal prompt originale
    if activations_data and 'tokens' in activations_data and 'counts' in activations_data:
        tokens = activations_data['tokens']
        counts = activations_data['counts']  # array [n_tokens] per questa feature
        
        # Prompt originale: tutti i token tranne l'ultimo
        original_tokens = tokens[:-1]
        
        # Trova token semantico con max attivazione
        max_activation = -1
        best_token = None
        
        for idx, token in enumerate(original_tokens):
            # Escludi <bos> e altri token speciali
            if token.strip() in ['<bos>', '<eos>', '<pad>', '<unk>']:
                continue
            
            if classify_peak_token(token) == "semantic":
                activation = counts[idx]  # attivazione su questo token
                if activation > max_activation:
                    max_activation = activation
                    best_token = token
        
        if best_token:
            # Normalizza (mantieni maiuscola se presente)
            all_occurrences = [best_token]
            x = normalize_token_for_naming(best_token, all_occurrences)
            return f"({x}) related"
    
    # Fallback: usa peak_token del record con max activation
    peak_token = str(max_record['peak_token']).strip()
    all_occurrences = feature_records['peak_token'].astype(str).tolist()
    x = normalize_token_for_naming(peak_token, all_occurrences)
    return f"({x}) related"


def name_semantic_node(
    feature_key: str,
    feature_records: pd.DataFrame,
    graph_json_path: Optional[str] = None
) -> str:
    """
    Naming per nodi Semantic: peak_token SEMANTICO con max activation.
    Se tutti i peak sono funzionali, usa il token dal Graph JSON alla posizione csv_ctx_idx.
    
    Args:
        feature_key: chiave della feature
        feature_records: DataFrame con tutti i record per questa feature
        graph_json_path: Path opzionale al Graph JSON (per csv_ctx_idx fallback)
        
    Returns:
        supernode_name: str (es. "Texas", "city", "punctuation")
    """
    # Filtra solo peak_token semantici E activation_max > 0 (prompt attivi)
    semantic_records = feature_records[
        (feature_records['peak_token_type'] == 'semantic') & 
        (feature_records['activation_max'] > 0)
    ]
    
    # Se non ci sono peak semantici attivi, prova solo semantici (anche con activation 0)
    if len(semantic_records) == 0:
        semantic_records = feature_records[feature_records['peak_token_type'] == 'semantic']
    
    # Se ancora nessuno, fallback su tutti i record attivi
    if len(semantic_records) == 0:
        semantic_records = feature_records[feature_records['activation_max'] > 0]
        
        # Controlla se TUTTI i record attivi sono funzionali
        if len(semantic_records) > 0:
            all_functional = all(
                semantic_records['peak_token_type'] == 'functional'
            )
            
            # Se tutti funzionali E abbiamo csv_ctx_idx E graph_json_path
            if all_functional and 'csv_ctx_idx' in feature_records.columns and graph_json_path:
                # Usa il token dal Graph JSON alla posizione csv_ctx_idx
                csv_ctx_idx = feature_records.iloc[0].get('csv_ctx_idx')
                
                if pd.notna(csv_ctx_idx) and graph_json_path:
                    try:
                        with open(graph_json_path, 'r', encoding='utf-8') as f:
                            graph_json = json.load(f)
                        
                        prompt_tokens = graph_json.get('metadata', {}).get('prompt_tokens', [])
                        csv_ctx_idx_int = int(csv_ctx_idx)
                        
                        if 0 <= csv_ctx_idx_int < len(prompt_tokens):
                            token_from_graph = prompt_tokens[csv_ctx_idx_int]
                            
                            # Normalizza
                            all_occurrences = [token_from_graph]
                            return normalize_token_for_naming(token_from_graph, all_occurrences)
                    except Exception as e:
                        # Se fallisce, continua con la logica normale
                        pass
    
    # Ultimo fallback: tutti i record
    if len(semantic_records) == 0:
        semantic_records = feature_records
    
    # Trova record con activation_max massima tra i semantici
    max_record = semantic_records.loc[semantic_records['activation_max'].idxmax()]
    peak_token = str(max_record['peak_token']).strip()
    
    # Casi edge
    if not peak_token or peak_token == 'nan':
        return "Semantic (unknown)"
    if is_punctuation(peak_token):
        return "punctuation"
    
    # Normalizza: mantieni maiuscola se presente
    # Raccogli solo le occorrenze di QUESTO specifico token (case-insensitive match)
    peak_token_lower = peak_token.lower()
    all_occurrences = [
        str(t) for t in feature_records['peak_token'].astype(str).tolist()
        if str(t).strip().lower() == peak_token_lower
    ]
    # Se nessuna occorrenza trovata (edge case), usa il token stesso
    if not all_occurrences:
        all_occurrences = [peak_token]
    
    return normalize_token_for_naming(peak_token, all_occurrences)


def name_sayx_node(
    feature_key: str,
    feature_records: pd.DataFrame
) -> str:
    """
    Naming per nodi Say "X": "Say (X)" dove X è il target_token con max activation.
    
    Args:
        feature_key: chiave della feature
        feature_records: DataFrame con tutti i record per questa feature
        
    Returns:
        supernode_name: str (es. "Say (Austin)", "Say (?)")
    """
    # Trova record con activation_max massima
    max_record = feature_records.loc[feature_records['activation_max'].idxmax()]
    
    # Estrai target_tokens
    target_tokens_json = max_record.get('target_tokens', '[]')
    try:
        target_tokens = json.loads(target_tokens_json)
    except:
        target_tokens = []
    
    # Nessun target
    if not target_tokens:
        return "Say (?)"
    
    # Un solo target
    if len(target_tokens) == 1:
        x_raw = str(target_tokens[0].get('token', '?'))
        # Raccogli solo le occorrenze di QUESTO specifico token (case-insensitive)
        x_raw_lower = x_raw.strip().lower()
        all_x_occurrences = []
        for _, row in feature_records.iterrows():
            try:
                row_targets = json.loads(row.get('target_tokens', '[]'))
                for t in row_targets:
                    token_str = str(t.get('token', ''))
                    if token_str.strip().lower() == x_raw_lower:
                        all_x_occurrences.append(token_str)
            except:
                pass
        # Se nessuna occorrenza trovata, usa il token stesso
        if not all_x_occurrences:
            all_x_occurrences = [x_raw]
        x = normalize_token_for_naming(x_raw, all_x_occurrences)
        return f"Say ({x})"
    
    # Multipli target: tie-break per distance, poi preferisci BACKWARD (contesto)
    def sort_key(t):
        distance = t.get('distance', 999)
        direction = t.get('direction', '')
        # Backward ha priorità (0), forward (1)
        dir_priority = 0 if direction == 'backward' else 1
        return (distance, dir_priority)
    
    sorted_targets = sorted(target_tokens, key=sort_key)
    x_raw = str(sorted_targets[0].get('token', '?'))
    
    # Raccogli solo le occorrenze di QUESTO specifico token (case-insensitive)
    x_raw_lower = x_raw.strip().lower()
    all_x_occurrences = []
    for _, row in feature_records.iterrows():
        try:
            row_targets = json.loads(row.get('target_tokens', '[]'))
            for t in row_targets:
                token_str = str(t.get('token', ''))
                if token_str.strip().lower() == x_raw_lower:
                    all_x_occurrences.append(token_str)
        except:
            pass
    # Se nessuna occorrenza trovata, usa il token stesso
    if not all_x_occurrences:
        all_x_occurrences = [x_raw]
    
    x = normalize_token_for_naming(x_raw, all_x_occurrences)
    return f"Say ({x})"


def name_nodes(
    df: pd.DataFrame,
    activations_json_path: Optional[str] = None,
    graph_json_path: Optional[str] = None,
    verbose: bool = True
) -> pd.DataFrame:
    """
    Step 3: Assegna supernode_name a tutte le feature.
    
    Args:
        df: DataFrame classificato (con pred_label, subtype)
        activations_json_path: Path al JSON delle attivazioni (per Relationship)
        graph_json_path: Path al Graph JSON (per Semantic con csv_ctx_idx fallback)
        verbose: stampa info
        
    Returns:
        DataFrame con colonna supernode_name
    """
    df = df.copy()
    df['supernode_name'] = ''
    
    if verbose:
        print(f"\n=== Step 3: Naming Supernodi ===")
    
    # Carica JSON attivazioni se disponibile
    activations_by_prompt = {}
    feature_indices = {}  # Mapping feature_key -> indice in counts
    
    if activations_json_path:
        try:
            with open(activations_json_path, 'r', encoding='utf-8') as f:
                activations_json = json.load(f)
            
            # Indicizza per prompt text (non probe_id, perché il CSV non ha probe_id)
            for result in activations_json.get('results', []):
                prompt_text = result.get('prompt', '')
                activations_by_prompt[prompt_text] = {
                    'tokens': result.get('tokens', []),
                    'counts': result.get('counts', [])  # [n_features x n_tokens]
                }
            
            # Crea mapping feature_key -> indice in counts
            # Assumiamo che l'ordine delle feature nel CSV corrisponda all'ordine in counts
            # (questo è vero se il CSV è stato generato dallo stesso JSON)
            unique_features = df['feature_key'].unique()
            for idx, fk in enumerate(unique_features):
                feature_indices[fk] = idx
            
            if verbose:
                print(f"  JSON attivazioni caricato: {len(activations_by_prompt)} prompt")
                print(f"  Feature indices mappate: {len(feature_indices)}")
        except Exception as e:
            if verbose:
                print(f"  WARNING: Impossibile caricare JSON attivazioni: {e}")
            activations_by_prompt = {}
            feature_indices = {}
    
    # Aggrega per feature_key
    for feature_key, group in df.groupby('feature_key'):
        pred_label = group['pred_label'].iloc[0]
        
        # Naming basato sulla classe
        if pred_label == "Relationship":
            # Per Relationship, serve il JSON delle attivazioni
            # Prendi il record con MAX ACTIVATION per trovare il prompt corretto
            max_record = group.loc[group['activation_max'].idxmax()]
            prompt_text = max_record.get('prompt', '')
            
            # Estrai dati attivazioni per questo prompt
            activations_data = None
            if prompt_text in activations_by_prompt and feature_key in feature_indices:
                # Trova l'indice della feature nel counts
                feature_idx = feature_indices[feature_key]
                
                # Estrai la riga corrispondente a questa feature
                full_counts = activations_by_prompt[prompt_text]['counts']
                tokens = activations_by_prompt[prompt_text]['tokens']
                
                # counts[feature_idx] è l'array di attivazioni per questa feature
                activations_data = {
                    'tokens': tokens,
                    'counts': full_counts[feature_idx]
                }
            
            name = name_relationship_node(feature_key, group, activations_data)
        
        elif pred_label == "Semantic":
            name = name_semantic_node(feature_key, group, graph_json_path)
        
        elif pred_label == 'Say "X"':
            name = name_sayx_node(feature_key, group)
        
        else:
            # Fallback: usa pred_label
            name = pred_label
        
        # Assegna nome
        df.loc[df['feature_key'] == feature_key, 'supernode_name'] = name
    
    if verbose:
        # Statistiche
        n_features = df['feature_key'].nunique()
        n_unique_names = df.groupby('feature_key')['supernode_name'].first().nunique()
        
        print(f"Naming completato:")
        print(f"  - {n_features} feature")
        print(f"  - {n_unique_names} nomi unici")
        
        # Conta per tipo
        name_counts = df.groupby('feature_key').agg({
            'pred_label': 'first',
            'supernode_name': 'first'
        })['pred_label'].value_counts()
        
        print(f"\nNomi per classe:")
        for label, count in name_counts.items():
            print(f"  - {label:15s}: {count:3d}")
        
        # Mostra alcuni esempi
        print(f"\nEsempi:")
        for label in ['Relationship', 'Semantic', 'Say "X"']:
            examples = df[df['pred_label'] == label].groupby('feature_key')['supernode_name'].first().head(3)
            if len(examples) > 0:
                print(f"  {label}:")
                for name in examples:
                    print(f"    - {name}")
    
    return df


# ============================================================================
# MAIN CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Node Grouping Pipeline: Step 1 (prepare) + Step 2 (classify) + Step 3 (naming)"
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path al CSV di input (es. output/*_export.csv)"
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Path al CSV di output (es. output/*_GROUPED.csv)"
    )
    parser.add_argument(
        "--json",
        type=str,
        default=None,
        help="Path opzionale al JSON di attivazioni (per tokens array)"
    )
    parser.add_argument(
        "--graph",
        type=str,
        default=None,
        help="Path opzionale al Graph JSON (per csv_ctx_idx fallback in Semantic naming)"
    )
    parser.add_argument(
        "--window",
        type=int,
        default=7,
        help="Finestra di ricerca per target_tokens (default: 7)"
    )
    parser.add_argument(
        "--skip-classify",
        action="store_true",
        help="Salta Step 2 (classificazione), esegui solo Step 1"
    )
    parser.add_argument(
        "--skip-naming",
        action="store_true",
        help="Salta Step 3 (naming), esegui solo Step 1+2"
    )
    
    # Soglie parametriche (opzionali)
    parser.add_argument(
        "--dict-consistency-min",
        type=float,
        default=None,
        help=f"Soglia min peak_consistency per Dictionary (default: {DEFAULT_THRESHOLDS['dict_peak_consistency_min']})"
    )
    parser.add_argument(
        "--sayx-func-min",
        type=float,
        default=None,
        help=f"Soglia min func_vs_sem_pct per Say X (default: {DEFAULT_THRESHOLDS['sayx_func_vs_sem_min']})"
    )
    parser.add_argument(
        "--sayx-layer-min",
        type=int,
        default=None,
        help=f"Soglia min layer per Say X (default: {DEFAULT_THRESHOLDS['sayx_layer_min']})"
    )
    parser.add_argument(
        "--rel-sparsity-max",
        type=float,
        default=None,
        help=f"Soglia max sparsity per Relationship (default: {DEFAULT_THRESHOLDS['rel_sparsity_max']})"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Stampa info dettagliate"
    )
    
    args = parser.parse_args()
    
    # Carica CSV
    print(f"Caricamento CSV: {args.input}")
    df = pd.read_csv(args.input, encoding="utf-8")
    print(f"  -> {len(df)} righe caricate")
    
    # Carica JSON (opzionale)
    tokens_json = None
    if args.json:
        print(f"Caricamento JSON: {args.json}")
        with open(args.json, "r", encoding="utf-8") as f:
            tokens_json = json.load(f)
        print(f"  -> JSON caricato")
    
    # Step 1: Preparazione
    df_prepared = prepare_dataset(
        df,
        tokens_json=tokens_json,
        window=args.window,
        verbose=args.verbose
    )
    
    # Step 2: Classificazione (opzionale)
    if not args.skip_classify:
        # Prepara soglie custom (se specificate)
        thresholds = DEFAULT_THRESHOLDS.copy()
        if args.dict_consistency_min is not None:
            thresholds['dict_peak_consistency_min'] = args.dict_consistency_min
        if args.sayx_func_min is not None:
            thresholds['sayx_func_vs_sem_min'] = args.sayx_func_min
        if args.sayx_layer_min is not None:
            thresholds['sayx_layer_min'] = args.sayx_layer_min
        if args.rel_sparsity_max is not None:
            thresholds['rel_sparsity_max'] = args.rel_sparsity_max
        
        # Classifica
        df_classified = classify_nodes(
            df_prepared,
            thresholds=thresholds,
            verbose=args.verbose
        )
    else:
        df_classified = df_prepared
        if args.verbose:
            print("\nStep 2 skipped (--skip-classify)")
    
    # Step 3: Naming (opzionale)
    if not args.skip_naming and not args.skip_classify:
        # Naming richiede classificazione
        df_final = name_nodes(
            df_classified,
            activations_json_path=args.json,
            graph_json_path=args.graph,
            verbose=args.verbose
        )
    else:
        df_final = df_classified
        if args.verbose and args.skip_naming:
            print("\nStep 3 skipped (--skip-naming)")
        elif args.verbose and args.skip_classify:
            print("\nStep 3 skipped (richiede Step 2)")
    
    # Salva output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_final.to_csv(output_path, index=False, encoding="utf-8")
    print(f"\nOK Output salvato: {output_path}")
    print(f"   {len(df_final)} righe, {len(df_final.columns)} colonne")


if __name__ == "__main__":
    main()

