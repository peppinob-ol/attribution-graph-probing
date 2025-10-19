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
from datetime import datetime
import logging

# Carica variabili d'ambiente da .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv non installato, continua senza

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('probe_prompts.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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
    
    @rate_limited(max_per_second=2)  # Ridotto da 5 a 2 per evitare rate limiting
    def get_activations(self, model_id: str, source: str, index: str, 
                       custom_text: str, max_retries: int = 3) -> dict:
        """
        Ottiene attivazioni per una feature su un testo custom con retry logic
        
        Args:
            model_id: ID del modello
            source: Source della feature
            index: Indice della feature
            custom_text: Testo da analizzare
            max_retries: Numero massimo di tentativi
            
        Returns:
            {
                "tokens": [...],
                "values": [...],
                "maxValue": float,
                ...
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
        
        last_error = None
        for attempt in range(max_retries):
            try:
                response = self.session.post(endpoint, json=payload, timeout=30)
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.HTTPError as e:
                last_error = e
                if response.status_code == 429:  # Too Many Requests
                    wait_time = min(2 ** attempt * 2, 60)  # Backoff esponenziale (max 60s)
                    logger.warning(f"Rate limit hit for {source}/{index}, waiting {wait_time}s (attempt {attempt+1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                elif response.status_code == 500:
                    logger.error(f"Server error 500 for {source}/{index}")
                    return {"error": "500_server_error", "source": source, "index": index}
                elif response.status_code == 404:
                    logger.warning(f"Feature non trovata (404): {source}/{index}")
                    return {"error": "404_not_found", "source": source, "index": index}
                else:
                    logger.error(f"HTTP {response.status_code} per {source}/{index}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                    return None
                    
            except requests.exceptions.Timeout:
                last_error = Exception("Timeout")
                wait_time = min(2 ** attempt, 30)
                logger.warning(f"Timeout per {source}/{index}, retry {attempt+1}/{max_retries} dopo {wait_time}s")
                if attempt >= max_retries - 1:
                    return {"error": "timeout", "source": source, "index": index}
                time.sleep(wait_time)
                continue
                
            except requests.exceptions.RequestException as e:
                last_error = e
                logger.error(f"Request error for {source}/{index}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return {"error": "other_error", "source": source, "index": index, "message": str(e)}
        
        # Tutti i tentativi falliti
        logger.error(f"Failed after {max_retries} attempts for {source}/{index}: {last_error}")
        return {"error": "other_error", "source": source, "index": index, "message": str(last_error)}
    
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


def save_checkpoint(records: List[Dict], checkpoint_path: str, metadata: Dict = None):
    """
    Salva checkpoint dei risultati parziali
    
    Args:
        records: Lista di record processati finora
        checkpoint_path: Path dove salvare il checkpoint
        metadata: Metadata aggiuntivi (es: progress info)
    """
    checkpoint_data = {
        "records": records,
        "metadata": metadata or {},
        "timestamp": datetime.now().isoformat(),
        "num_records": len(records)
    }
    
    checkpoint_file = Path(checkpoint_path)
    checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Salva con nome temporaneo poi rinomina (atomic write)
    temp_file = checkpoint_file.with_suffix('.tmp')
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(checkpoint_data, f, indent=2)
    
    temp_file.replace(checkpoint_file)
    logger.info(f"Checkpoint salvato: {len(records)} records in {checkpoint_path}")


def load_checkpoint(checkpoint_path: str) -> Tuple[List[Dict], Dict]:
    """
    Carica checkpoint da file
    
    Returns:
        Tuple di (records, metadata)
    """
    checkpoint_file = Path(checkpoint_path)
    
    if not checkpoint_file.exists():
        logger.info(f"Nessun checkpoint trovato in {checkpoint_path}")
        return [], {}
    
    try:
        with open(checkpoint_file, 'r', encoding='utf-8') as f:
            checkpoint_data = json.load(f)
        
        records = checkpoint_data.get("records", [])
        metadata = checkpoint_data.get("metadata", {})
        timestamp = checkpoint_data.get("timestamp", "unknown")
        
        logger.info(f"Checkpoint caricato: {len(records)} records da {timestamp}")
        return records, metadata
        
    except Exception as e:
        logger.error(f"Errore nel caricamento checkpoint: {e}")
        return [], {}


def get_processed_keys(records: List[Dict]) -> set:
    """
    Estrae le chiavi (label, layer, feature) già processate dai records
    
    Returns:
        Set di tuple (label, layer, feature)
    """
    return {
        (r["label"], r["layer"], r["feature"]) 
        for r in records
    }


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
    progress_callback: Optional[callable] = None,
    checkpoint_every: int = 10,
    checkpoint_path: Optional[str] = None,
    resume_from_checkpoint: bool = True
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
        checkpoint_every: Salva checkpoint ogni N features processate
        checkpoint_path: Path per salvare checkpoint (default: auto-generato)
        resume_from_checkpoint: Se True, riprende da checkpoint esistente
        
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
    
    # Se api_key non fornita, prova a caricarla da .env
    if api_key is None:
        api_key = os.getenv("NEURONPEDIA_API_KEY")
        if api_key and verbose:
            print(f"[INFO] Using API key from .env: {api_key[:10]}...")
    
    api = NeuronpediaAPI(api_key)
    
    # Setup checkpoint path
    if checkpoint_path is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        checkpoint_path = f"output/checkpoints/probe_prompts_{timestamp}.json"
    
    # Carica checkpoint se richiesto
    existing_records = []
    processed_keys = set()
    
    if resume_from_checkpoint:
        existing_records, checkpoint_metadata = load_checkpoint(checkpoint_path)
        if existing_records:
            processed_keys = get_processed_keys(existing_records)
            logger.info(f"Riprendendo da checkpoint: {len(existing_records)} records, {len(processed_keys)} combinazioni già processate")
            if verbose:
                print(f"[RESUME] Caricati {len(existing_records)} records da checkpoint")
                print(f"[RESUME] Skip {len(processed_keys)} combinazioni già processate")
    
    # ───────────── Estrazione metadata dal JSON ─────────────
    if verbose:
        print("[INFO] Parsing graph JSON...")
    
    metadata = graph_json.get("metadata", {})
    model_id = metadata.get("scan")
    original_prompt = metadata.get("prompt", "")
    
    if not model_id:
        raise ValueError("[ERROR] JSON manca 'metadata.scan' (model_id)")
    
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
        print(f"[INFO] Source template base: {source_template}")
    
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
            print(f"[INFO] Source template inferito: {source_template}")
    
    if verbose:
        print(f"[OK] Found {len(features_in_graph)} features in graph")
        print(f"[INFO] Model: {model_id}")
        print(f"[INFO] Source template: {source_template}")
        print(f"[INFO] Original prompt: '{original_prompt[:50]}...'")
    
    # ───────────── Filtraggio per influence ─────────────
    (filtered_features, 
     threshold_influence, 
     num_selected, 
     num_total) = filter_features_by_influence(features_in_graph, cumulative_contribution)
    
    if verbose:
        print(f"\n[FILTER] Filtraggio per influence (cumulative {cumulative_contribution*100:.1f}%):")
        print(f"   Selected: {num_selected}/{num_total} features")
        print(f"   Threshold influence: {threshold_influence:.6f}")
    
    # ───────────── Baseline (opzionale) ─────────────
    baseline_stats = {}
    
    if use_baseline and original_prompt:
        if verbose:
            print(f"\n[BASELINE] Computing baseline activations for {len(filtered_features)} features...")
        
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
        print(f"[OK] Baseline computed for {len(baseline_stats)} features\n")
    
    # ───────────── Loop sui concetti ─────────────
    records = existing_records.copy()  # Inizia con records da checkpoint
    total_calls = len(concepts) * len(filtered_features)
    current_call = len(existing_records)  # Riprendi dal count esistente
    skipped_count = 0
    last_checkpoint_time = time.time()
    checkpoint_interval = 300  # Salva anche ogni 5 minuti
    
    # Contatori errori per tipo
    error_counts = {
        "500_server_error": 0,
        "404_not_found": 0,
        "429_rate_limit": 0,
        "timeout": 0,
        "other_error": 0,
        "no_data": 0,
        "no_values": 0
    }
    error_details = []  # Lista dettagliata errori per debugging
    
    try:
        for concept_idx, concept in enumerate(concepts):
            label = concept.get("label", "").strip()
            category = concept.get("category", "").strip()
            description = concept.get("description", "").strip()
            
            prompt = f"{label}: {description}"
            
            if verbose:
                print(f"\n[CONCEPT] {concept_idx+1}/{len(concepts)}: '{label}' ({category})")
            
            # Tokenizza il label (approssimativo)
            label_tokens_approx = tokenize_simple(label)
            
            for feat_idx, feat in enumerate(filtered_features):
                layer = feat["layer"]
                feature = feat["feature"]
                
                # Skip se già processato
                if (label, layer, feature) in processed_keys:
                    skipped_count += 1
                    continue
                
                current_call += 1
                
                # Callback più frequente (ogni feature)
                if progress_callback:
                    progress_callback(current_call, total_calls, f"concept '{label}' ({concept_idx+1}/{len(concepts)})")
                
                # Log verboso ogni 10 features
                if verbose and feat_idx % 10 == 0:
                    print(f"  [{label}] Features: {feat_idx}/{len(filtered_features)} "
                          f"(chiamate totali: {current_call}/{total_calls}, skipped: {skipped_count})")
                    import sys
                    sys.stdout.flush()  # Forza flush per Streamlit
                
                source = f"{layer}-{source_template}"
            
            # ════════ API Call ════════
            result = api.get_activations(model_id, source, str(feature), prompt)
            
            # Gestione errori strutturati
            if not result:
                error_counts["no_data"] += 1
                error_details.append({
                    "concept": label,
                    "source": source,
                    "feature": feature,
                    "error_type": "no_data",
                    "message": "API returned None"
                })
                if verbose and error_counts["no_data"] % 50 == 1:
                    print(f"[WARNING] Skipping {source}/{feature} - no data (totale errori no_data: {error_counts['no_data']})")
                    import sys
                    sys.stdout.flush()
                continue
            
            # Check se result contiene un errore
            if isinstance(result, dict) and "error" in result:
                error_type = result["error"]
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
                error_details.append({
                    "concept": label,
                    "source": source,
                    "feature": feature,
                    "error_type": error_type,
                    "message": result.get("message", "")
                })
                total_errors = sum(error_counts.values())
                if verbose and total_errors % 50 == 1:
                    print(f"[WARNING] {error_type} per {source}/{feature} (totale errori: {total_errors})")
                    import sys
                    sys.stdout.flush()
                continue
            
            # ════════ Parsing Response ════════
            # L'API può restituire due formati diversi:
            # Formato 1 (vecchio): {"tokens": [...], "activations": {"values": [...], ...}}
            # Formato 2 (nuovo): {"tokens": [...], "values": [...], "maxValue": ...}
            tokens = result.get("tokens", [])
            
            if "activations" in result:
                # Formato vecchio
                act_data = result["activations"]
                act_values = torch.tensor(act_data["values"], dtype=torch.float32)
            elif "values" in result:
                # Formato nuovo
                act_values = torch.tensor(result["values"], dtype=torch.float32)
            else:
                error_counts["no_values"] += 1
                error_details.append({
                    "concept": label,
                    "source": source,
                    "feature": feature,
                    "error_type": "no_values",
                    "message": f"Response missing values field. Keys: {list(result.keys())}"
                })
                if verbose and error_counts["no_values"] % 50 == 1:
                    print(f"[WARNING] Skipping {source}/{feature} - no values in response (totale: {error_counts['no_values']})")
                    import sys
                    sys.stdout.flush()
                continue
            
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
            
            # ════════ Checkpoint ════════
            # Salva checkpoint ogni N features O ogni M minuti
            should_checkpoint = (
                (len(records) % checkpoint_every == 0 and len(records) > len(existing_records)) or
                (time.time() - last_checkpoint_time > checkpoint_interval)
            )
            
            if should_checkpoint:
                checkpoint_metadata = {
                    "current_concept": concept_idx + 1,
                    "total_concepts": len(concepts),
                    "current_feature": feat_idx + 1,
                    "total_features": len(filtered_features),
                    "total_calls": current_call,
                    "skipped": skipped_count,
                    "error_counts": error_counts,
                    "total_errors": sum(error_counts.values())
                }
                save_checkpoint(records, checkpoint_path, checkpoint_metadata)
                last_checkpoint_time = time.time()
        
        # Salva checkpoint finale per questo concept
        checkpoint_metadata = {
            "current_concept": concept_idx + 1,
            "total_concepts": len(concepts),
            "total_calls": current_call,
            "skipped": skipped_count,
            "error_counts": error_counts,
            "total_errors": sum(error_counts.values()),
            "status": "completed_concept"
        }
        save_checkpoint(records, checkpoint_path, checkpoint_metadata)
    
    except KeyboardInterrupt:
        logger.warning("Interruzione rilevata (Ctrl+C). Salvataggio checkpoint finale...")
        if verbose:
            print("\n[INTERRUPT] Salvataggio checkpoint prima di uscire...")
        
        checkpoint_metadata = {
            "status": "interrupted",
            "total_calls": current_call,
            "skipped": skipped_count,
            "error_counts": error_counts,
            "total_errors": sum(error_counts.values())
        }
        save_checkpoint(records, checkpoint_path, checkpoint_metadata)
        
        if verbose:
            print(f"[SAVED] Checkpoint salvato con {len(records)} records")
            print(f"[INFO] Per riprendere, riesegui con lo stesso checkpoint_path: {checkpoint_path}")
        
        raise  # Re-raise per permettere gestione upstream
    
    except Exception as e:
        logger.error(f"Errore durante l'analisi: {e}")
        # Salva checkpoint anche in caso di errore
        checkpoint_metadata = {
            "status": "error",
            "error": str(e),
            "total_calls": current_call,
            "error_counts": error_counts,
            "total_errors": sum(error_counts.values())
        }
        save_checkpoint(records, checkpoint_path, checkpoint_metadata)
        raise
    
    # ═══════════ DataFrame Construction ═══════════
    if not records:
        if verbose:
            print("[WARNING] No records generated!")
        return pd.DataFrame()
    
    df = pd.DataFrame.from_records(records)
    df = df.set_index(["label", "category", "layer", "feature"]).sort_index()
    
    if verbose:
        print(f"\n[DONE] Analysis complete! Generated {len(df)} records")
        print(f"   Unique concepts: {df.index.get_level_values('label').nunique()}")
        print(f"   Unique features: {df.index.get_level_values('feature').nunique()}")
        
        # Summary errori
        total_errors = sum(error_counts.values())
        print(f"\n[ERRORS] Statistiche errori:")
        print(f"   Totale errori: {total_errors}")
        print(f"   Successi: {len(records)}")
        print(f"   Tasso successo: {len(records)/(len(records)+total_errors)*100:.1f}%")
        print(f"\n   Dettaglio per tipo:")
        for error_type, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                print(f"      - {error_type}: {count} ({count/total_errors*100:.1f}%)")
        
        # Salva log dettagliato errori se ci sono molti errori
        if total_errors > 0 and output_csv:
            error_log_path = Path(output_csv).with_name(Path(output_csv).stem + "_errors.json")
            with open(error_log_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "error_counts": error_counts,
                    "total_errors": total_errors,
                    "success_count": len(records),
                    "error_details": error_details[:1000]  # Primi 1000 errori per non esplodere il file
                }, f, indent=2)
            print(f"\n   Log errori salvato in: {error_log_path}")
    
    if output_csv and not df.empty:
        # Salva con reset_index per avere tutte le colonne come colonne normali
        df.reset_index().to_csv(output_csv, index=False, encoding='utf-8')
        if verbose:
            print(f"[SAVED] Results saved to: {output_csv}")
    
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

