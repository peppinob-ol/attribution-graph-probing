#!/usr/bin/env python3
"""
Script per analizzare attivazioni di features su concepts specifici tramite API Neuronpedia.

Implementa la funzione analyze_concepts_from_graph_json che usa le API di Neuronpedia
per ottenere le attivazioni delle features su concepts definiti dall'utente.

Uso come script:
    python scripts/01_probe_prompts.py

Uso come modulo:
    from scripts.probe_prompts import analyze_concepts_from_graph_json
    
    concepts = [
        {"label": "Dallas", "category": "entity", "description": "a major city..."},
        ...
    ]
    df = analyze_concepts_from_graph_json(graph_json, concepts, api_key="...")
"""

import sys
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Tuple, List, Optional
import torch
import torch.nn.functional as F
import pandas as pd
import requests
import time
import json
from functools import wraps

# Assicurati che il path sia corretto per gli import
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))


# ===== RATE LIMITING =====

def rate_limited(max_per_second: int = 5):
    """Decorator per limitare chiamate API"""
    min_interval = 1.0 / max_per_second
    last_called = [0.0]
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            result = func(*args, **kwargs)
            last_called[0] = time.time()
            return result
        return wrapper
    return decorator


# ===== API CLIENT =====

class NeuronpediaAPI:
    """Client per interagire con Neuronpedia API"""
    
    BASE_URL = "https://www.neuronpedia.org/api"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"x-api-key": api_key})
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Cache per attivazioni baseline
        self._baseline_cache = {}
    
    @rate_limited(max_per_second=5)
    def get_activations(self, model_id: str, source: str, index: str, 
                       custom_text: str) -> dict:
        """
        Ottiene attivazioni per una feature su un testo custom
        
        Returns:
            {
                "tokens": [...],
                "activations": {
                    "values": [...],
                    "maxValue": float,
                    "maxValueIndex": int,
                    ...
                }
            }
        """
        endpoint = f"{self.BASE_URL}/activation/new"
        payload = {
            "feature": {
                "modelId": model_id,
                "source": source,
                "index": str(index)
            },
            "customText": custom_text
        }
        
        try:
            response = self.session.post(endpoint, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 500:
                print(f"❌ Server error for {source}/{index}")
                print(f"   Possibile causa: source format errato o feature non esistente")
                print(f"   Payload: modelId={model_id}, source={source}, index={index}")
            elif response.status_code == 404:
                print(f"⚠️  Feature non trovata: {source}/{index}")
            else:
                print(f"❌ HTTP {response.status_code} per {source}/{index}: {e}")
            return None
        except requests.exceptions.Timeout:
            print(f"⏱️  Timeout per {source}/{index}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching activations for {source}/{index}: {e}")
            return None
    
    def get_baseline_activations(self, model_id: str, source: str, 
                                 index: str, original_prompt: str) -> dict:
        """Cache-aware baseline activations"""
        cache_key = (model_id, source, index)
        
        if cache_key not in self._baseline_cache:
            result = self.get_activations(model_id, source, index, original_prompt)
            if result:
                self._baseline_cache[cache_key] = result
        
        return self._baseline_cache.get(cache_key)


# ===== HELPER FUNCTIONS =====

def find_subsequence(haystack: List[str], needle: List[str]) -> Optional[int]:
    """Trova la posizione di una sottosequenza in una lista"""
    if not needle:
        return None
    
    for i in range(len(haystack) - len(needle) + 1):
        if haystack[i:i+len(needle)] == needle:
            return i
    return None


def tokenize_simple(text: str) -> List[str]:
    """
    Tokenizzazione semplice per matching.
    NOTA: Questo è approssimativo. I token reali potrebbero differire.
    Usa i token ritornati dall'API come ground truth.
    """
    return text.strip().split()


def filter_features_by_influence(
    features: List[Dict],
    cumulative_contribution: float = 0.95
) -> Tuple[List[Dict], float, int, int]:
    """
    Filtra features per cumulative influence contribution.
    
    Args:
        features: Lista di dict con chiave "influence"
        cumulative_contribution: Soglia di contributo cumulativo (0-1)
        
    Returns:
        Tuple di:
        - Lista features filtrate (ordinate per influence desc)
        - Soglia di influence usata
        - Numero features selezionate
        - Numero features totali
    """
    if not features:
        return [], 0.0, 0, 0
    
    # Ordina per influence decrescente (valore assoluto)
    sorted_features = sorted(features, key=lambda f: abs(f.get("influence", 0)), reverse=True)
    
    # Calcola influence cumulativa
    total_influence = sum(abs(f.get("influence", 0)) for f in sorted_features)
    
    if total_influence == 0:
        return sorted_features, 0.0, len(sorted_features), len(features)
    
    cumulative = 0.0
    selected_features = []
    threshold_influence = 0.0
    
    for feat in sorted_features:
        abs_influence = abs(feat.get("influence", 0))
        cumulative += abs_influence / total_influence
        selected_features.append(feat)
        threshold_influence = abs_influence
        
        if cumulative >= cumulative_contribution:
            break
    
    return selected_features, threshold_influence, len(selected_features), len(features)


# ===== MAIN FUNCTION =====

def analyze_concepts_from_graph_json(
    graph_json: dict,
    concepts: List[Dict[str, str]],
    api_key: Optional[str] = None,
    activation_threshold_quantile: float = 0.9,
    use_baseline: bool = True,
    cumulative_contribution: float = 0.95,
    verbose: bool = True,
    output_csv: Optional[str] = None,
    progress_callback: Optional[callable] = None
) -> pd.DataFrame:
    """
    Analizza concetti usando un attribution graph JSON di Neuronpedia.
    
    Per ogni concept, crea un prompt "label: description" e calcola:
    - Attivazioni su tutto il prompt e sullo span del label (tramite API)
    - Z-scores (standard, robust IQR, log-scaled)
    - Metriche di densità, cosine similarity, ratio vs original
    
    Args:
        graph_json: JSON del graph (da file o da API /api/graph/{modelId}/{slug})
        concepts: Lista di dict con "label", "category", "description"
        api_key: API key di Neuronpedia (opzionale per lettura)
        activation_threshold_quantile: Quantile per threshold di densità
        use_baseline: Se calcolare metriche vs prompt originale
        cumulative_contribution: Soglia di contributo cumulativo influence (0-1)
        verbose: Print progress
        output_csv: Path opzionale per salvare il DataFrame in CSV
        progress_callback: Funzione opzionale da chiamare per aggiornamenti progresso
        
    Returns:
        DataFrame con colonne:
        - label, category, layer, feature (index)
        - attivazione_vecchio_prompt, original_position, influence
        - nuova_somma_sequenza, nuova_max_sequenza, nuova_media_sequenza
        - nuova_somma_label_span, nuova_max_label_span, nuova_media_label_span, nuova_l2_label_span
        - picco_su_label, peak_token, peak_position
        - label_span_start, label_span_end, seq_len
        - original_max, original_density, ratio_max_vs_original, cosine_similarity
        - density_attivazione, normalized_sum_label, normalized_sum_seq
        - percentile_in_sequence
        - z_score, z_score_robust, z_score_log
        - prompt
        
    Example:
        >>> with open("graph.json") as f:
        ...     graph_json = json.load(f)
        >>> concepts = [
        ...     {"label": "Dallas", "category": "entity", 
        ...      "description": "a major city located in the state of Texas"},
        ... ]
        >>> df = analyze_concepts_from_graph_json(graph_json, concepts, api_key="...")
        >>> df.to_csv("output/acts_compared.csv", index=False)
    """
    
    api = NeuronpediaAPI(api_key)
    
    # ───────────── Estrazione metadata dal JSON ─────────────
    if verbose:
        print("📊 Parsing graph JSON...")
    
    metadata = graph_json.get("metadata", {})
    model_id = metadata.get("scan")
    original_prompt = metadata.get("prompt", "")
    
    if not model_id:
        raise ValueError("❌ JSON manca 'metadata.scan' (model_id)")
    
    # Estrai source set (es: "gemmascope-res-16k")
    info = metadata.get("info", {})
    transcoder_set_raw = info.get("transcoder_set", "")
    
    # Per Gemma models, converte "gemma" → "gemmascope" (formato API)
    if transcoder_set_raw and transcoder_set_raw.lower() == "gemma":
        # Il graph ha "gemma" ma API vuole "gemmascope"
        transcoder_set = "gemmascope"
    elif transcoder_set_raw:
        transcoder_set = transcoder_set_raw
    elif "gemma" in model_id.lower():
        # Fallback per Gemma senza transcoder_set
        transcoder_set = "gemmascope"
    else:
        # Default generico
        transcoder_set = "gemmascope"
    
    # Determina il tipo (res vs transcoder) dai source_urls se disponibili
    source_urls = info.get("source_urls", [])
    source_type = "res-16k"  # Default
    
    # Controlla gli URL per determinare se è transcoder o res
    for url in source_urls:
        if "transcoder" in url.lower():
            source_type = "transcoder-16k"
            break
        elif "res" in url.lower():
            source_type = "res-16k"
            break
    
    # Fallback: controlla nel transcoder_set
    if source_type == "res-16k" and "transcoder" in transcoder_set.lower():
        source_type = "transcoder-16k"
    
    # Template per costruire source
    source_template = f"{transcoder_set}-{source_type}"
    
    if verbose:
        print(f"📝 Source template base: {source_template}")
    
    # ───────────── Estrazione features dal graph ─────────────
    nodes = graph_json.get("nodes", [])
    features_in_graph = []
    
    # Tenta di inferire il source format dal primo nodo valido
    inferred_source_template = None
    
    for node in nodes:
        # Skippa nodi non-feature (embedding, error nodes, etc)
        if node.get("feature_type") != "cross layer transcoder":
            continue
        
        layer = node.get("layer")
        
        # IMPORTANTE: il campo "feature" contiene un ID interno
        # Il vero feature index è nel node_id: "layer_feature_position"
        node_id = node.get("node_id", "")
        if "_" in node_id:
            parts = node_id.split("_")
            if len(parts) >= 2:
                try:
                    feature_idx = int(parts[1])  # Seconda parte = feature index reale
                except ValueError:
                    feature_idx = node.get("feature")  # Fallback
            else:
                feature_idx = node.get("feature")
        else:
            feature_idx = node.get("feature")
        
        if layer is None or feature_idx is None:
            continue
        
        # Inferisci source dal nodo se disponibile
        if inferred_source_template is None and "modelId" in node:
            # Alcuni graph includono il modelId nel nodo
            # Formato: "layer-set-type-size"
            node_model = node.get("modelId", "")
            if node_model and "-" in node_model:
                # Rimuovi layer prefix per ottenere template
                parts = node_model.split("-", 1)
                if len(parts) > 1:
                    inferred_source_template = parts[1]
        
        features_in_graph.append({
            "layer": int(layer),
            "feature": int(feature_idx),
            "original_activation": float(node.get("activation", 0)),
            "original_ctx_idx": int(node.get("ctx_idx", 0)),
            "influence": float(node.get("influence", 0)),
        })
    
    # Usa source inferito se disponibile
    if inferred_source_template:
        source_template = inferred_source_template
        if verbose:
            print(f"📝 Source template inferito: {source_template}")
    
    if verbose:
        print(f"✅ Found {len(features_in_graph)} features in graph")
        print(f"📝 Model: {model_id}")
        print(f"📝 Source template: {source_template}")
        print(f"📝 Original prompt: '{original_prompt[:50]}...'")
    
    # ───────────── Filtraggio per influence ─────────────
    (filtered_features, 
     threshold_influence, 
     num_selected, 
     num_total) = filter_features_by_influence(features_in_graph, cumulative_contribution)
    
    if verbose:
        print(f"\n🎯 Filtraggio per influence (cumulative {cumulative_contribution*100:.1f}%):")
        print(f"   Selected: {num_selected}/{num_total} features")
        print(f"   Threshold influence: {threshold_influence:.6f}")
    
    # ───────────── Baseline (opzionale) ─────────────
    baseline_stats = {}
    
    if use_baseline and original_prompt:
        if verbose:
            print(f"\n🔄 Computing baseline activations for {len(filtered_features)} features...")
        
        for i, feat in enumerate(filtered_features):
            # Callback per ogni feature
            if progress_callback:
                progress_callback(i + 1, len(filtered_features), "baseline")
            
            if verbose and i % 10 == 0:
                print(f"  Baseline: {i}/{len(filtered_features)}")
                import sys
                sys.stdout.flush()
            
            source = f"{feat['layer']}-{source_template}"
            result = api.get_baseline_activations(
                model_id, source, str(feat['feature']), original_prompt
            )
            
            if result and "activations" in result:
                act_vals = torch.tensor(result["activations"]["values"])
                baseline_stats[(feat['layer'], feat['feature'])] = {
                    "values": act_vals,
                    "max": float(act_vals.max()),
                    "mean": float(act_vals.mean()),
                    "density_threshold": float(torch.quantile(act_vals, activation_threshold_quantile)),
                    "tokens": result.get("tokens", [])
                }
    
    if verbose and baseline_stats:
        print(f"✅ Baseline computed for {len(baseline_stats)} features\n")
    
    # ───────────── Loop sui concetti ─────────────
    records = []
    total_calls = len(concepts) * len(filtered_features)
    current_call = 0
    
    for concept_idx, concept in enumerate(concepts):
        label = concept.get("label", "").strip()
        category = concept.get("category", "").strip()
        description = concept.get("description", "").strip()
        
        prompt = f"{label}: {description}"
        
        if verbose:
            print(f"\n🔍 Concept {concept_idx+1}/{len(concepts)}: '{label}' ({category})")
        
        # Tokenizza il label (approssimativo)
        label_tokens_approx = tokenize_simple(label)
        
        for feat_idx, feat in enumerate(filtered_features):
            current_call += 1
            
            # Callback più frequente (ogni feature)
            if progress_callback:
                progress_callback(current_call, total_calls, f"concept '{label}' ({concept_idx+1}/{len(concepts)})")
            
            # Log verboso ogni 10 features
            if verbose and feat_idx % 10 == 0:
                print(f"  [{label}] Features: {feat_idx}/{len(filtered_features)} "
                      f"(chiamate totali: {current_call}/{total_calls})")
                import sys
                sys.stdout.flush()  # Forza flush per Streamlit
            
            layer = feat["layer"]
            feature = feat["feature"]
            source = f"{layer}-{source_template}"
            
            # ════════ API Call ════════
            result = api.get_activations(model_id, source, str(feature), prompt)
            
            if not result or "activations" not in result:
                print(f"⚠️  Skipping {source}/{feature} - no data")
                import sys
                sys.stdout.flush()
                continue
            
            # ════════ Parsing Response ════════
            tokens = result.get("tokens", [])
            act_data = result["activations"]
            act_values = torch.tensor(act_data["values"])
            
            seq_len = len(act_values)
            max_val = float(act_values.max())
            max_pos = int(act_values.argmax())
            max_token = tokens[max_pos] if max_pos < len(tokens) else "?"
            
            # Threshold per densità
            thresh = float(torch.quantile(act_values, activation_threshold_quantile))
            density = float((act_values > thresh).sum() / seq_len)
            
            # ════════ Label Span Detection ════════
            # Trova label nei token ritornati dall'API
            start_idx = find_subsequence(tokens, label_tokens_approx)
            
            if start_idx is not None:
                end_idx = start_idx + len(label_tokens_approx) - 1
                if end_idx < len(act_values):
                    span_acts = act_values[start_idx:end_idx+1]
                    span_sum = float(span_acts.sum())
                    span_max = float(span_acts.max())
                    span_mean = float(span_acts.mean())
                    span_l2 = float(span_acts.norm(p=2))
                    peak_on_label = (start_idx <= max_pos <= end_idx)
                else:
                    span_sum = span_max = span_mean = span_l2 = float("nan")
                    peak_on_label = False
            else:
                span_sum = span_max = span_mean = span_l2 = float("nan")
                peak_on_label = False
                start_idx = end_idx = None
            
            # ════════ Baseline Comparison ════════
            baseline = baseline_stats.get((layer, feature))
            
            if baseline:
                orig_max = baseline["max"]
                orig_density = float((baseline["values"] > baseline["density_threshold"]).sum() 
                                    / len(baseline["values"]))
                
                # Cosine similarity (su lunghezza minima)
                min_len = min(len(act_values), len(baseline["values"]))
                cos_sim = float(F.cosine_similarity(
                    act_values[:min_len].unsqueeze(0),
                    baseline["values"][:min_len].unsqueeze(0)
                ))
                
                # Ratio (con clamp per evitare overflow)
                denom = max(abs(orig_max), 1e-3)
                ratio = max_val / denom
            else:
                orig_max = orig_density = cos_sim = ratio = float("nan")
            
            # ════════ Z-scores ════════
            std_robust = float(act_values.std()) + 1e-3
            z_score = (max_val - feat["original_activation"]) / std_robust
            
            # Z robust (IQR-based)
            q75, q25 = torch.quantile(act_values, 0.75).item(), torch.quantile(act_values, 0.25).item()
            iqr = max(q75 - q25, 1e-3)
            z_robust = 0.741 * (max_val - (q25 + q75) * 0.5) / iqr
            
            # Z log-scaled
            z_log = (torch.sign(torch.tensor(z_score)) * 
                    torch.log1p(torch.tensor(abs(z_score)))).item()
            
            # ════════ Normalized metrics ════════
            norm_sum_label = (span_sum / len(label_tokens_approx) 
                             if start_idx is not None and len(label_tokens_approx) > 0 
                             else float("nan"))
            norm_sum_seq = float(act_values.sum() / seq_len)
            
            percentile_in_seq = (float((act_values < span_max).sum() / seq_len) * 100 
                                if span_max == span_max else float("nan"))
            
            # ════════ Record ════════
            records.append({
                "label": label,
                "category": category,
                "layer": layer,
                "feature": feature,
                
                # Original graph data
                "attivazione_vecchio_prompt": feat["original_activation"],
                "original_position": feat["original_ctx_idx"],
                "influence": feat["influence"],
                
                # New prompt activations
                "nuova_somma_sequenza": float(act_values.sum()),
                "nuova_max_sequenza": max_val,
                "nuova_media_sequenza": float(act_values.mean()),
                
                # Label span metrics
                "nuova_somma_label_span": span_sum,
                "nuova_max_label_span": span_max,
                "nuova_media_label_span": span_mean,
                "nuova_l2_label_span": span_l2,
                "picco_su_label": peak_on_label,
                "peak_token": max_token,
                "peak_position": max_pos,
                
                # Span indices
                "label_span_start": start_idx,
                "label_span_end": end_idx,
                "seq_len": seq_len,
                
                # Baseline comparison
                "original_max": orig_max,
                "original_density": orig_density,
                "ratio_max_vs_original": ratio,
                "cosine_similarity": cos_sim,
                
                # Density & normalization
                "density_attivazione": density,
                "normalized_sum_label": norm_sum_label,
                "normalized_sum_seq": norm_sum_seq,
                "percentile_in_sequence": percentile_in_seq,
                
                # Z-scores
                "z_score": z_score,
                "z_score_robust": z_robust,
                "z_score_log": z_log,
                
                # Metadata
                "prompt": prompt,
            })
    
    # ═══════════ DataFrame Construction ═══════════
    if not records:
        if verbose:
            print("⚠️  No records generated!")
        return pd.DataFrame()
    
    df = pd.DataFrame.from_records(records)
    df = df.set_index(["label", "category", "layer", "feature"]).sort_index()
    
    if verbose:
        print(f"\n✅ Analysis complete! Generated {len(df)} records")
        print(f"   Unique concepts: {df.index.get_level_values('label').nunique()}")
        print(f"   Unique features: {df.index.get_level_values('feature').nunique()}")
    
    if output_csv and not df.empty:
        # Salva con reset_index per avere tutte le colonne come colonne normali
        df.reset_index().to_csv(output_csv, index=False, encoding='utf-8')
        if verbose:
            print(f"💾 Results saved to: {output_csv}")
    
    return df


# ===== MAIN =====

if __name__ == "__main__":
    print("Script 01_probe_prompts.py")
    print("=" * 60)
    print("Questo script fornisce la funzione analyze_concepts_from_graph_json")
    print("per analizzare le attivazioni su concepts specifici tramite API Neuronpedia.")
    print()
    print("Usa l'interfaccia Streamlit per eseguire l'analisi:")
    print("  streamlit run eda/app.py")
    print("  -> Naviga alla pagina '01_Probe_Prompts'")
    print()
    print("Oppure importa da Python:")
    print("  from scripts.probe_prompts import analyze_concepts_from_graph_json")
    print()
    print("Esempio d'uso:")
    print('  with open("graph.json") as f:')
    print("      graph_json = json.load(f)")
    print("  ")
    print('  concepts = [{"label": "AI", "category": "tech", "description": "..."}]')
    print('  df = analyze_concepts_from_graph_json(graph_json, concepts, api_key="...")')
    print('  df.to_csv("results.csv")')

