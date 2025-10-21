# ========================= Neuronpedia Activations: multi-prompt one-shot (Colab) =========================
# COME USARE IN COLAB:
# 1. IMPORTANTE - Setup runtime:
#    - Vai a Runtime > Change runtime type > Hardware accelerator: T4 GPU (o superiore)
#    - Se ri-esegui questo codice, prima fai: Runtime > Restart session (per liberare GPU)
# 2. Carica questo file in una cella Colab (copia/incolla o usa "Upload to session storage")
# 3. Prepara i file JSON di input (vedi esempi sotto)
# 4. Esegui la cella - il codice:
#    - clona automaticamente il repo neuronpedia
#    - inizializza Model e SAEManager
#    - processa tutti i prompt
#    - salva un unico JSON con tutti i risultati
#
# INPUT FILES:
#   1) prompts.json - Formati accettati:
#      ["prompt1", "prompt2", ...]
#      oppure: [{"id": "p1", "text": "prompt1"}, {"id": "p2", "text": "prompt2"}]
#      oppure: {"prompts": [...come sopra...]}
#
#   2) features.json - Formati accettati:
#      [{"source": "10-gemmascope-res-16k", "index": 1234}, ...]
#      oppure: [{"layer": 10, "index": 1234}, ...]  (converte automaticamente)
#      oppure: {"features": [...come sopra...]}
#
# OUTPUT:
#   activations_dump.json con formato:
#   {
#     "model": "gemma-2-2b",
#     "source_set": "gemmascope-transcoder-16k",
#     "n_prompts": 5,
#     "n_features_requested": 55,
#     "results": [
#       {
#         "probe_id": "p1",
#         "prompt": "testo prompt",
#         "tokens": [...],
#         "counts": [[...]],
#         "activations": [{"source": "10-...", "index": 123, "values": [...], ...}, ...]
#       },
#       ...
#     ]
#   }
#
# NOTA IMPORTANTE: 
#   - Con INCLUDE_ZERO_ACTIVATIONS=True: include TUTTE le feature richieste (anche con valore 0)
#   - Con INCLUDE_ZERO_ACTIVATIONS=False: include SOLO le feature che si sono attivate (più compatto)
#   - Per analisi complete è consigliato True, per visualizzazioni è consigliato False
#
# NOTA: Usa la stessa pipeline di /activation/all (ActivationProcessor), garantendo coerenza.
# =========================================================================================================

import os, sys, json, shutil, time, re, traceback
from typing import Any

# --------------------------- CONFIGURAZIONE BASE (EDITA QUI) ---------------------------------------------
# Modello e SAE set (devono essere compatibili!)
# COMPATIBILITÀ PRINCIPALI:
#   gpt2-small       → "res-jb"
#   gemma-2-2b       → "gemmascope-res-16k", "gemmascope-transcoder-16k", "clt-hp" (Circuit Tracer)
#   gemma-2-2b-it    → "gemmascope-res-16k", "gemmascope-transcoder-16k"
# NOTA: altri SAE set potrebbero funzionare anche se non nel registry standard di SAELens
# RIFERIMENTI: https://www.neuronpedia.org/transcoders-hp (il set si chiama "clt-hp", non "transcoders-hp")
MODEL_ID    = "gemma-2-2b"               # "gpt2-small" | "gemma-2-2b" | "gemma-2-2b-it" | ecc.
SOURCE_SET  = "clt-hp"                   # "res-jb" | "gemmascope-res-16k" | "gemmascope-transcoder-16k" | "clt-hp"

# File di input (caricali su Colab/Drive; vedi schema sopra e example_*.json)
PROMPTS_JSON_PATH  = "/content/prompts.json"
FEATURES_JSON_PATH = "/content/features.json"

# File di output
OUT_JSON_PATH      = "/content/activations_dump.json"

# Se True, processa layer-by-layer per tutti i prompt (ottimizzato per SAE pesanti)
# IMPORTANTE: per SAE pesanti come clt-hp, impostare True per evitare OOM
# STRATEGIA OTTIMIZZATA:
#   - Scarica ogni layer UNA SOLA VOLTA
#   - Processa tutti i prompt con quel layer
#   - Pulisce cache HF e libera GPU
#   - Passa al layer successivo
# Risultato: ~5x più veloce rispetto a processare prompt-by-prompt con re-download
CHUNK_BY_LAYER = True  # ← True per clt-hp (consigliato), False per res-jb/gemmascope (leggeri)

# Se True, include nell'output anche le feature richieste con attivazione = 0
# Se False, include solo le feature che si sono effettivamente attivate (più compatto)
INCLUDE_ZERO_ACTIVATIONS = True  # ← True per vedere tutte le 55 feature, False solo quelle attive

# Eventuale token HF per modelli gated (es. Gemma)
# IMPORTANTE: Non inserire mai token direttamente nel codice!
# Opzioni per fornire il token:
#   1. Variabile d'ambiente: export HF_TOKEN="your_token_here" (prima di eseguire lo script)
#   2. Colab Secrets: from google.colab import userdata; os.environ["HF_TOKEN"] = userdata.get('HF_TOKEN')
#   3. File .env locale (NON committare il file!)
# Se non è già impostato, lo script proseguirà senza token (funziona per modelli pubblici)
if "HF_TOKEN" not in os.environ:
    print("⚠️ HF_TOKEN non trovato. Se usi modelli gated (es. Gemma), imposta la variabile d'ambiente HF_TOKEN")

# ---------------------------------------------------------------------------------------------------------

# ========================= verifica preliminare file input (prima di caricare modello) ===================
if not os.path.exists(PROMPTS_JSON_PATH):
    raise FileNotFoundError(f"File prompts non trovato: {PROMPTS_JSON_PATH}")
if not os.path.exists(FEATURES_JSON_PATH):
    raise FileNotFoundError(f"File features non trovato: {FEATURES_JSON_PATH}")
print(f"✓ File input verificati:\n  - {PROMPTS_JSON_PATH}\n  - {FEATURES_JSON_PATH}")

# ========================= clona repo neuronpedia e setta sys.path =======================================
REPO_URL = "https://github.com/hijohnnylin/neuronpedia.git"
REPO_DIR = "/content/neuronpedia"

if not os.path.exists(REPO_DIR):
    import subprocess
    subprocess.run(["git", "clone", "-q", REPO_URL, REPO_DIR], check=True)

# Percorsi per importare i moduli interni (inference) e i modelli OpenAPI (client Python)
sys.path.append(f"{REPO_DIR}/apps/inference")
sys.path.append(f"{REPO_DIR}/packages/python/neuronpedia-inference-client")

# ========================= import: fedeli a all.py =======================================================
# (vedi all.py: usa Config/Model/SAEManager e ActivationProcessor)
# NOTA: i moduli sotto non sono in locale, verranno trovati dopo il clone del repo
from neuronpedia_inference.config import Config  # type: ignore
from neuronpedia_inference.shared import Model  # type: ignore
from neuronpedia_inference.sae_manager import SAEManager  # type: ignore
from neuronpedia_inference.endpoints.activation.all import ActivationProcessor  # type: ignore

from neuronpedia_inference_client.models.activation_all_post_request import ActivationAllPostRequest  # type: ignore
from neuronpedia_inference_client.models.activation_all_post200_response import ActivationAllPost200Response  # type: ignore
from neuronpedia_inference_client.models.activation_all_post200_response_activations_inner import ActivationAllPost200ResponseActivationsInner  # type: ignore

# Import per inizializzazione Model
try:
    from transformer_lens import HookedSAETransformer  # type: ignore
    USE_SAE_TRANSFORMER = True
except ImportError:
    from transformer_lens import HookedTransformer  # type: ignore
    USE_SAE_TRANSFORMER = False
from neuronpedia_inference.shared import STR_TO_DTYPE  # type: ignore

# ========================= cleanup memoria GPU + DISCO (importante per SAE pesanti come clt-hp) ===========
import torch
import gc

# CLEANUP DISCO: cache Hugging Face (importante per clt-hp che scarica 8-12 GB per layer!)
print("Pulizia cache Hugging Face (spazio disco)...")
HF_CACHE_DIR = os.path.expanduser("~/.cache/huggingface/hub")
if os.path.exists(HF_CACHE_DIR):
    # Calcola spazio usato prima
    def get_dir_size(path):
        total = 0
        try:
            for entry in os.scandir(path):
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat().st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += get_dir_size(entry.path)
        except (PermissionError, FileNotFoundError):
            pass
        return total
    
    cache_size_gb = get_dir_size(HF_CACHE_DIR) / 1024**3
    print(f"  Cache HF attuale: {cache_size_gb:.2f} GB")
    
    # Rimuovi solo i modelli SAE vecchi (non il modello base che è già scaricato)
    # Pattern: models--mntss--clt-* (i SAE clt-hp)
    cleaned_gb = 0
    for item in os.listdir(HF_CACHE_DIR):
        item_path = os.path.join(HF_CACHE_DIR, item)
        if "mntss--clt-" in item and os.path.isdir(item_path):
            item_size = get_dir_size(item_path) / 1024**3
            print(f"  Rimuovo cache SAE: {item} ({item_size:.2f} GB)")
            shutil.rmtree(item_path, ignore_errors=True)
            cleaned_gb += item_size
    
    if cleaned_gb > 0:
        print(f"  ✓ Liberati {cleaned_gb:.2f} GB di spazio disco")
    else:
        print(f"  Cache SAE già pulita")

# Check spazio disco disponibile
if hasattr(shutil, 'disk_usage'):
    disk = shutil.disk_usage("/")
    free_gb = disk.free / 1024**3
    total_gb = disk.total / 1024**3
    print(f"  Spazio disco: {free_gb:.2f} GB liberi / {total_gb:.2f} GB totali")
    
    # Warn se poco spazio (serve almeno 15 GB per un layer clt-hp)
    if free_gb < 15.0:
        print(f"\n⚠️ ATTENZIONE: Spazio disco limitato ({free_gb:.2f} GB)")
        print(f"   I SAE clt-hp richiedono ~10-15 GB temporanei per layer durante il download")
        print(f"   Lo script procederà comunque - i layer verranno scaricati/eliminati uno alla volta")

# CLEANUP GPU
if torch.cuda.is_available():
    print("\nPulizia memoria GPU prima di iniziare...")
    torch.cuda.empty_cache()
    gc.collect()

    mem_free_gb = torch.cuda.mem_get_info()[0] / 1024**3
    mem_total_gb = torch.cuda.mem_get_info()[1] / 1024**3
    print(f"  GPU: {torch.cuda.get_device_name(0)}")
    print(f"  Memoria libera: {mem_free_gb:.2f} GB / {mem_total_gb:.2f} GB totali")

    # Check se c'è abbastanza memoria (gemma-2-2b richiede ~5-6 GB)
    if mem_free_gb < 4.0:
        print(f"\n⚠️ ATTENZIONE: Memoria GPU insufficiente ({mem_free_gb:.2f} GB liberi)")
        print("   Gemma-2-2b richiede almeno 4-5 GB liberi.")
        print("   SOLUZIONE: Runtime > Restart session, poi ri-esegui questa cella")
        raise RuntimeError(f"GPU memoria insufficiente: {mem_free_gb:.2f} GB liberi, servono almeno 4 GB")

# ========================= init environment come nel server ==============================================
# (all.py si aspetta che i singleton siano configurati via env Config)
device_guess = "cuda" if torch.cuda.is_available() else "cpu"
os.environ.setdefault("MODEL_ID", MODEL_ID)
os.environ.setdefault("SAE_SETS", json.dumps([SOURCE_SET]))   # lista di SAE set caricabili
os.environ.setdefault("DEVICE", device_guess)
os.environ.setdefault("TOKEN_LIMIT", "4096")
os.environ.setdefault("MODEL_DTYPE", "bfloat16" if device_guess == "cuda" else "float32")
os.environ.setdefault("SAE_DTYPE", "float32")

print(f"Configurazione environment:")
print(f"  MODEL_ID: {os.environ['MODEL_ID']}")
print(f"  DEVICE: {os.environ['DEVICE']}")
print(f"  MODEL_DTYPE: {os.environ['MODEL_DTYPE']}")

# ========================= init Config con parametri espliciti (non legge env vars!) ======================
# IMPORTANTE: Config.__init__() ha solo defaults, dobbiamo passare i parametri esplicitamente
Config._instance = None  # reset singleton
cfg = Config.__new__(Config)
cfg.__init__(
    model_id=MODEL_ID,
    sae_sets=[SOURCE_SET],
    device=device_guess,
    model_dtype=os.environ["MODEL_DTYPE"],
    sae_dtype=os.environ["SAE_DTYPE"],
    token_limit=int(os.environ["TOKEN_LIMIT"]),
)
Config._instance = cfg  # Registra come singleton

print(f"Config inizializzato: device={cfg.device}, dtype={cfg.model_dtype}, token_limit={cfg.token_limit}")

# ========================= validazione MODEL_ID <-> SOURCE_SET =======================================
valid_models = cfg.get_valid_model_ids()
if MODEL_ID not in valid_models and cfg.custom_hf_model_id not in valid_models:
    print(f"\n⚠️ WARNING: SAE set '{SOURCE_SET}' non trovato nel registry standard di SAELens")
    print(f"  Modelli registrati per '{SOURCE_SET}': {valid_models if valid_models else '(nessuno)'}")
    print(f"\n  Proseguo comunque - se il SAE set esiste verrà caricato dinamicamente.")
    print(f"  Se ottieni errori di caricamento SAE, verifica la compatibilità MODEL_ID <-> SOURCE_SET")
    print(f"\n  Combinazioni standard note:")
    print(f"    - gpt2-small       → res-jb")
    print(f"    - gemma-2-2b       → gemmascope-res-16k, gemmascope-transcoder-16k, clt-hp")
    print(f"    - gemma-2-2b-it    → gemmascope-res-16k, gemmascope-transcoder-16k")
else:
    print(f"✓ Validazione: {MODEL_ID} + {SOURCE_SET} trovati nel registry SAELens")

# ========================= init Model (TransformerLens) ==============================================
print(f"\nCaricamento modello {MODEL_ID} su {cfg.device}...")
if USE_SAE_TRANSFORMER:
    print("  (usando HookedSAETransformer per ottimizzazione SAE)")
    model = HookedSAETransformer.from_pretrained(
        MODEL_ID,
        device=cfg.device,
        dtype=STR_TO_DTYPE[cfg.model_dtype],
        **cfg.model_kwargs
    )
else:
    model = HookedTransformer.from_pretrained(
        MODEL_ID,
        device=cfg.device,
        dtype=STR_TO_DTYPE[cfg.model_dtype],
        **cfg.model_kwargs
    )
Model.set_instance(model)
print(f"✓ Modello caricato: {model.cfg.n_layers} layer")

# ========================= init SAEManager e carica SAE ==============================================
# IMPORTANTE: inizializza SAEManager con i parametri corretti PRIMA di chiamare get_instance()
SAEManager._instance = None  # reset singleton per coerenza
# Crea l'istanza manualmente con i parametri corretti invece di usare il costruttore di default
sae_mgr = SAEManager.__new__(SAEManager)
sae_mgr.__init__(num_layers=model.cfg.n_layers, device=cfg.device)
SAEManager._instance = sae_mgr  # Registra come singleton

print(f"SAEManager configurato: device={sae_mgr.device}, layers={sae_mgr.num_layers}")

# IMPORTANTE: per SAE pesanti come clt-hp, NON caricare tutto subito (OOM)
# Il caricamento avverrà on-demand quando serve (tramite get_sae())
if CHUNK_BY_LAYER:
    print(f"⚠️ SAE set '{SOURCE_SET}' - caricamento on-demand per risparmiare memoria")
    print(f"   (i layer verranno caricati uno alla volta quando necessario)")
    # Setup solo metadati senza caricare i pesi
    sae_mgr.setup_neuron_layers()
    # Configura sae_set_to_saes per i metadati
    from neuronpedia_inference.config import get_saelens_neuronpedia_directory_df, config_to_json
    directory_df = get_saelens_neuronpedia_directory_df()
    config_json = config_to_json(directory_df, selected_sets_neuronpedia=[SOURCE_SET], selected_model=MODEL_ID)
    for sae_set in config_json:
        sae_mgr.valid_sae_sets.append(sae_set["set"])
        sae_mgr.sae_set_to_saes[sae_set["set"]] = sae_set["saes"]
    print(f"✓ SAE manager pronto (on-demand loading)")
else:
    print(f"Caricamento completo SAE set '{SOURCE_SET}'...")
    sae_mgr.load_saes()
    print(f"✓ SAE manager pronto")

# ========================= helper: lettura input robusta ================================================

def load_prompts(path: str) -> list[dict]:
    """
    Accetta:
      - lista di stringhe: ["text1", "text2", ...]
      - lista di oggetti: [{"id": "...", "text": "..."}, ...]
      - oggetto con chiave "prompts": come sopra
    Normalizza in lista di dict: [{"id": str, "text": str}, ...]
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # unwrap "prompts"
    if isinstance(data, dict) and "prompts" in data:
        data = data["prompts"]
    out = []
    if isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, str):
                out.append({"id": f"p{i}", "text": item})
            elif isinstance(item, dict):
                # campi tollerati: "text" o "prompt" + opzionale "id"
                text = item.get("text", item.get("prompt", None))
                if not isinstance(text, str):
                    raise ValueError(f"Prompt #{i} non valido: {item}")
                pid = str(item.get("id", f"p{i}"))
                out.append({"id": pid, "text": text})
            else:
                raise ValueError(f"Elemento prompt non riconosciuto: {type(item)}")
    else:
        raise ValueError("Formato prompts.json non valido")
    return out

def load_features(path: str, source_set: str) -> list[dict]:
    """
    Accetta:
      - lista di oggetti: [{"source":"L-source_set","index":int}, ...]
      - oppure [{"layer":int,"index":int}, ...] -> converto a {"source": f"{layer}-{source_set}", "index": int}
      - oppure oggetto {"features":[...]} come sopra
    Verifica che tutte le source abbiano il suffisso == source_set (coerenza col request all.py).
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "features" in data:
        data = data["features"]
    if not isinstance(data, list):
        raise ValueError("Formato features.json non valido")
    norm = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"feature #{i}: atteso oggetto, trovato {type(item)}")
        if "source" in item and "index" in item:
            source = str(item["source"])
            idx = int(item["index"])
            # controllo coerenza del suffisso con SOURCE_SET richiesto
            # Esempio: "10-res-jb" → suffisso "res-jb"
            if "-" not in source:
                # accetto anche formati tipo "blocks.10.hook_resid_post" → estraggo layer
                m = re.search(r"(\d+)", source)
                if not m:
                    raise ValueError(f"source non riconosciuta: {source}")
                layer = int(m.group(1))
                source = f"{layer}-{source_set}"
            else:
                suff = source.split("-", 1)[1]
                if suff != source_set:
                    raise ValueError(f"feature #{i}: source_set '{suff}' != atteso '{source_set}'")
            norm.append({"source": source, "index": idx})
        elif "layer" in item and "index" in item:
            layer = int(item["layer"])
            idx = int(item["index"])
            norm.append({"source": f"{layer}-{source_set}", "index": idx})
        else:
            raise ValueError(f"feature #{i}: campi attesi ('source','index') o ('layer','index')")
    return norm

# ========================= core: una chiamata ActivationProcessor per prompt =============================

def run_all_for_prompt(prompt_text: str, wanted_features: list[dict]) -> dict[str, Any]:
    """
    Costruisce un ActivationAllPostRequest come in all.py:
      - selected_sources = tutti i layer presenti nelle feature
      - niente feature_filter cross-layer (filtriamo dopo)
    Esegue ActivationProcessor.process_activations() e poi filtra le feature richieste.
    Ritorna dict con {"tokens":[...], "counts":[[...]], "activations":[...solo richieste...] }.
    """
    proc = ActivationProcessor()

    # layer distinti dalle feature richieste
    layers = sorted({int(f["source"].split("-")[0]) for f in wanted_features})
    selected_sources = [f"{L}-{SOURCE_SET}" for L in layers]

    # richieste identiche allo schema di /activation/all
    req = ActivationAllPostRequest(
        prompt=prompt_text,
        model=MODEL_ID,
        source_set=SOURCE_SET,
        selected_sources=selected_sources,
        ignore_bos=False,
        sort_by_token_indexes=[],   # puoi riempire se vuoi sommare su token specifici
        num_results=100_000
    )

    resp: ActivationAllPost200Response = proc.process_activations(req)  # metodo all.py (fedelissimo)

    # filtro: tengo solo le feature richieste
    want = {(f["source"], int(f["index"])) for f in wanted_features}
    found_features = set()
    filtered = []
    for a in resp.activations:
        src = a.source
        idx = int(a.index)
        if (src, idx) in want:
            obj = {
                "source": src,
                "index": idx,
                "values": list(a.values),
                "sum_values": float(a.sum_values) if a.sum_values is not None else None,
                "max_value": float(a.max_value),
                "max_value_index": int(a.max_value_index),
            }
            if getattr(a, "dfa_values", None) is not None:
                obj["dfa_values"] = list(a.dfa_values)
                obj["dfa_target_index"] = int(a.dfa_target_index)
                obj["dfa_max_value"] = float(a.dfa_max_value)
            filtered.append(obj)
            found_features.add((src, idx))
    
    # Aggiungi feature richieste ma non attivate (valore 0) se richiesto
    if INCLUDE_ZERO_ACTIVATIONS:
        num_tokens = len(resp.tokens)
        for f in wanted_features:
            src = f["source"]
            idx = int(f["index"])
            if (src, idx) not in found_features:
                obj = {
                    "source": src,
                    "index": idx,
                    "values": [0.0] * num_tokens,
                    "sum_values": 0.0,
                    "max_value": 0.0,
                    "max_value_index": 0,
                }
                filtered.append(obj)

    return {
        "tokens": list(resp.tokens),
        "counts": [[float(x) for x in row] for row in resp.counts],  # tabella attivazioni>0 per layer x token
        "activations": filtered
    }

def run_per_layer_for_prompt(prompt_text: str, wanted_features: list[dict]) -> dict[str, Any]:
    """
    Variante chunking: processa un layer per volta usando lo stesso ActivationProcessor.
    Identico al metodo, ma riduce memoria perché non calcola tutti i layer insieme.
    Unisce i risultati e poi filtra.
    IMPORTANTE: unload del SAE dopo ogni layer per liberare memoria GPU.
    """
    proc = ActivationProcessor()
    sae_mgr = SAEManager.get_instance()

    # raggruppa wanted_features per layer
    by_layer: dict[int, list[dict]] = {}
    for f in wanted_features:
        L = int(f["source"].split("-")[0])
        by_layer.setdefault(L, []).append(f)

    tokens_ref = None
    counts_accum = None
    activations_all = []

    for idx, (L, feats) in enumerate(sorted(by_layer.items())):
        sae_id = f"{L}-{SOURCE_SET}"
        print(f"    Layer {L} [{idx+1}/{len(by_layer)}]...", end=" ", flush=True)

        req = ActivationAllPostRequest(
            prompt=prompt_text,
            model=MODEL_ID,
            source_set=SOURCE_SET,
            selected_sources=[sae_id],  # un solo layer
            ignore_bos=False,
            sort_by_token_indexes=[],
            num_results=100_000
        )
        resp = proc.process_activations(req)

        if tokens_ref is None:
            tokens_ref = list(resp.tokens)
        # somma "counts" per layer (sono già per-layer; qui copio/riallineo)
        if counts_accum is None:
            counts_accum = [[float(x) for x in row] for row in resp.counts]
        else:
            # espandi counts_accum se necessario
            max_rows = max(len(counts_accum), len(resp.counts))
            if len(counts_accum) < max_rows:
                counts_accum += [[0.0]*len(tokens_ref) for _ in range(max_rows-len(counts_accum))]
            for r in range(len(resp.counts)):
                for c in range(len(resp.counts[r])):
                    counts_accum[r][c] += float(resp.counts[r][c])

        # prendi solo le feature desiderate di questo layer
        want = {(f"{L}-{SOURCE_SET}", int(f["index"])) for f in feats}
        found_in_layer = set()
        for a in resp.activations:
            src = a.source
            idx = int(a.index)
            if (src, idx) in want:
                obj = {
                    "source": src,
                    "index": idx,
                    "values": list(a.values),
                    "sum_values": float(a.sum_values) if a.sum_values is not None else None,
                    "max_value": float(a.max_value),
                    "max_value_index": int(a.max_value_index),
                }
                if getattr(a, "dfa_values", None) is not None:
                    obj["dfa_values"] = list(a.dfa_values)
                    obj["dfa_target_index"] = int(a.dfa_target_index)
                    obj["dfa_max_value"] = float(a.dfa_max_value)
                activations_all.append(obj)
                found_in_layer.add((src, idx))
        
        # Aggiungi feature richieste ma non attivate (valore 0) se richiesto
        if INCLUDE_ZERO_ACTIVATIONS and tokens_ref:
            for f in feats:
                src = f"{L}-{SOURCE_SET}"
                idx = int(f["index"])
                if (src, idx) not in found_in_layer:
                    obj = {
                        "source": src,
                        "index": idx,
                        "values": [0.0] * len(tokens_ref),
                        "sum_values": 0.0,
                        "max_value": 0.0,
                        "max_value_index": 0,
                    }
                    activations_all.append(obj)

        # Unload SAE per liberare memoria GPU (importante per SAE pesanti)
        if sae_id in sae_mgr.loaded_saes:
            sae_mgr.unload_sae(sae_id)
        
        # PULIZIA CACHE DISCO dopo ogni layer per liberare spazio (critico per clt-hp!)
        # Rimuove i file del layer appena processato dalla cache HF
        if SOURCE_SET == "clt-hp":
            try:
                HF_CACHE_DIR = os.path.expanduser("~/.cache/huggingface/hub")
                for item in os.listdir(HF_CACHE_DIR):
                    if "mntss--clt-" in item:
                        item_path = os.path.join(HF_CACHE_DIR, item)
                        if os.path.isdir(item_path):
                            shutil.rmtree(item_path, ignore_errors=True)
                torch.cuda.empty_cache()
                gc.collect()
            except Exception:
                pass  # Ignora errori di cleanup
        
        print(f"OK (unloaded + cleaned)", flush=True)

    return {
        "tokens": tokens_ref or [],
        "counts": counts_accum or [],
        "activations": activations_all
    }

def run_layer_by_layer_all_prompts(prompts: list[dict], wanted_features: list[dict]) -> list[dict]:
    """
    OTTIMIZZAZIONE: processa tutti i prompt layer-by-layer invece di prompt-by-prompt.
    Questo minimizza i re-download dei SAE (ogni layer viene scaricato 1 sola volta).
    
    Strategia:
    1. Raggruppa features per layer
    2. Per ogni layer:
       - Scarica il SAE una sola volta
       - Processa TUTTI i prompt con quel layer
       - Scarica il SAE e pulisce la cache
    3. Riorganizza i risultati per prompt
    """
    proc = ActivationProcessor()
    sae_mgr = SAEManager.get_instance()
    
    # Raggruppa features per layer
    by_layer: dict[int, list[dict]] = {}
    for f in wanted_features:
        L = int(f["source"].split("-")[0])
        by_layer.setdefault(L, []).append(f)
    
    # Dizionario per accumulare risultati per prompt
    # prompt_id -> {"tokens": [...], "counts": [...], "activations": [...]}
    results_by_prompt: dict[str, dict] = {p["id"]: {"tokens": None, "counts": None, "activations": []} for p in prompts}
    
    layers_sorted = sorted(by_layer.keys())
    print(f"\n⚡ OTTIMIZZAZIONE: processando {len(layers_sorted)} layer per {len(prompts)} prompt")
    print(f"   (ogni layer viene scaricato 1 sola volta)\n")
    
    for idx, L in enumerate(layers_sorted, 1):
        sae_id = f"{L}-{SOURCE_SET}"
        feats = by_layer[L]
        
        print(f"  Layer {L} [{idx}/{len(layers_sorted)}] - processando {len(prompts)} prompt...", end=" ", flush=True)
        
        # Processa tutti i prompt con questo layer
        for p in prompts:
            pid, text = p["id"], p["text"]
            
            req = ActivationAllPostRequest(
                prompt=text,
                model=MODEL_ID,
                source_set=SOURCE_SET,
                selected_sources=[sae_id],
                ignore_bos=False,
                sort_by_token_indexes=[],
                num_results=100_000
            )
            resp = proc.process_activations(req)
            
            # Salva tokens e counts (solo la prima volta per questo prompt)
            if results_by_prompt[pid]["tokens"] is None:
                results_by_prompt[pid]["tokens"] = list(resp.tokens)
                results_by_prompt[pid]["counts"] = [[float(x) for x in row] for row in resp.counts]
            
            # Aggiungi activations filtrate
            want = {(f"{L}-{SOURCE_SET}", int(f["index"])) for f in feats}
            found_features = set()  # traccia quali feature sono state trovate
            
            for a in resp.activations:
                src = a.source
                idx_feat = int(a.index)
                if (src, idx_feat) in want:
                    obj = {
                        "source": src,
                        "index": idx_feat,
                        "values": list(a.values),
                        "sum_values": float(a.sum_values) if a.sum_values is not None else None,
                        "max_value": float(a.max_value),
                        "max_value_index": int(a.max_value_index),
                    }
                    if getattr(a, "dfa_values", None) is not None:
                        obj["dfa_values"] = list(a.dfa_values)
                        obj["dfa_target_index"] = int(a.dfa_target_index)
                        obj["dfa_max_value"] = float(a.dfa_max_value)
                    results_by_prompt[pid]["activations"].append(obj)
                    found_features.add((src, idx_feat))
            
            # Aggiungi feature richieste ma non attivate (valore 0) se richiesto
            if INCLUDE_ZERO_ACTIVATIONS:
                num_tokens = len(results_by_prompt[pid]["tokens"]) if results_by_prompt[pid]["tokens"] else 0
                for f in feats:
                    src = f"{L}-{SOURCE_SET}"
                    idx_feat = int(f["index"])
                    if (src, idx_feat) not in found_features and num_tokens > 0:
                        # Feature richiesta ma non attivata - aggiungi con valori a zero
                        obj = {
                            "source": src,
                            "index": idx_feat,
                            "values": [0.0] * num_tokens,
                            "sum_values": 0.0,
                            "max_value": 0.0,
                            "max_value_index": 0,
                        }
                        results_by_prompt[pid]["activations"].append(obj)
        
        # Unload SAE e pulisci cache (una sola volta dopo aver processato tutti i prompt)
        if sae_id in sae_mgr.loaded_saes:
            sae_mgr.unload_sae(sae_id)
        
        if SOURCE_SET == "clt-hp":
            try:
                HF_CACHE_DIR = os.path.expanduser("~/.cache/huggingface/hub")
                for item in os.listdir(HF_CACHE_DIR):
                    if "mntss--clt-" in item:
                        item_path = os.path.join(HF_CACHE_DIR, item)
                        if os.path.isdir(item_path):
                            shutil.rmtree(item_path, ignore_errors=True)
                torch.cuda.empty_cache()
                gc.collect()
            except Exception:
                pass
        
        print(f"✓ (cleaned)", flush=True)
    
    # Riorganizza risultati nell'ordine originale dei prompt
    return [
        {
            "probe_id": p["id"],
            "prompt": p["text"],
            "tokens": results_by_prompt[p["id"]]["tokens"] or [],
            "counts": results_by_prompt[p["id"]]["counts"] or [],
            "activations": results_by_prompt[p["id"]]["activations"],
        }
        for p in prompts
    ]

# ========================= carica input, esegui per tutti i prompt, salva JSON ===========================

try:
    print(f"\n{'='*60}")
    print(f"Caricamento input files...")
    prompts = load_prompts(PROMPTS_JSON_PATH)
    features = load_features(FEATURES_JSON_PATH, SOURCE_SET)
    print(f"✓ {len(prompts)} prompt(s), {len(features)} feature(s)")

    if CHUNK_BY_LAYER:
        # OTTIMIZZAZIONE: processa layer-by-layer per tutti i prompt insieme
        # Questo minimizza i re-download (ogni layer viene scaricato 1 sola volta)
        results = run_layer_by_layer_all_prompts(prompts, features)
        
        # Stampa riepilogo per prompt
        print(f"\n{'='*60}")
        print(f"Riepilogo risultati:")
        for i, res in enumerate(results, 1):
            print(f"  [{i}/{len(results)}] {res['probe_id']}: {len(res['activations'])} attivazioni, {len(res['tokens'])} token")
    else:
        # Metodo classico: tutti i layer insieme per ogni prompt
        results = []
        for i, p in enumerate(prompts, 1):
            pid, text = p["id"], p["text"]
            print(f"\n[{i}/{len(prompts)}] Processando prompt '{pid}'...")
            print(f"  Text: {text[:60]}{'...' if len(text) > 60 else ''}")

            res = run_all_for_prompt(text, features)

            print(f"  ✓ {len(res['activations'])} attivazioni trovate, {len(res['tokens'])} token")
            results.append({
                "probe_id": pid,
                "prompt": text,
                "tokens": res["tokens"],
                "counts": res["counts"],
                "activations": res["activations"],
            })

    out = {
        "model": MODEL_ID,
        "source_set": SOURCE_SET,
        "device": Config.get_instance().device,
        "n_prompts": len(results),
        "n_features_requested": len(features),
        "results": results,
    }

    with open(OUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"✔ COMPLETATO!")
    print(f"{'='*60}")
    print(f"File salvato: {OUT_JSON_PATH}")
    print(f"Statistiche:")
    print(f"  - Prompt processati: {len(results)}")
    print(f"  - Features richieste: {len(features)}")
    print(f"  - Modello: {MODEL_ID}")
    print(f"  - SAE set: {SOURCE_SET}")
    print(f"  - Device: {out['device']}")

    # Dimensione file
    file_size_mb = os.path.getsize(OUT_JSON_PATH) / (1024 * 1024)
    print(f"  - Dimensione output: {file_size_mb:.2f} MB")
    print(f"{'='*60}")

except Exception as e:
    print(f"\n{'='*60}")
    print(f"✗ ERRORE!")
    print(f"{'='*60}")
    print(f"Messaggio: {e}")
    print(f"\nStack trace completo:")
    traceback.print_exc()
    print(f"{'='*60}")
