"""Pagina 2 - Node Grouping: Classifica e nomina supernodi per interpretazione"""
import sys
from pathlib import Path

# Aggiungi parent directory al path
parent_dir = Path(__file__).parent.parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

import streamlit as st
import pandas as pd
import json
import io
from datetime import datetime

# Import funzioni node grouping
import importlib.util
script_path = parent_dir / "scripts" / "02_node_grouping.py"
spec = importlib.util.spec_from_file_location("node_grouping", script_path)
node_grouping = importlib.util.module_from_spec(spec)
spec.loader.exec_module(node_grouping)
prepare_dataset = node_grouping.prepare_dataset
classify_nodes = node_grouping.classify_nodes
name_nodes = node_grouping.name_nodes
DEFAULT_THRESHOLDS = node_grouping.DEFAULT_THRESHOLDS

st.set_page_config(page_title="Node Grouping", page_icon="🔗", layout="wide")

st.title("🔗 Node Grouping & Classification")

st.info("""
**Classifica e nomina automaticamente i supernodi** per facilitare l'interpretazione del grafo di attribuzione.

Questa pipeline trasforma le feature SAE in supernodi interpretabili attraverso 3 step:
1. **Preparazione**: Identifica token funzionali vs semantici e trova i target tokens
2. **Classificazione**: Assegna ogni feature a una classe (Semantic, Say X, Relationship)
3. **Naming**: Genera nomi descrittivi per ogni supernodo
""")

# ===== SIDEBAR: CONFIGURAZIONE =====

st.sidebar.header("⚙️ Configurazione")

# File upload
st.sidebar.subheader("📁 Input Files")

# Percorsi di default
default_csv_path = parent_dir / "output" / "2025-10-21T07-40_export_ENRICHED.csv"
default_json_path = parent_dir / "output" / "activations_dump (2).json"
default_graph_path = parent_dir / "output" / "graph_data" / "clt-hp-the-capital-of-201020250035-20251020-003525.json"

# Carica automaticamente i file di default se esistono e non sono già stati caricati
if 'default_files_loaded' not in st.session_state:
    st.session_state['default_files_loaded'] = False
    
    if default_csv_path.exists():
        st.session_state['default_csv'] = default_csv_path
        st.sidebar.info(f"✅ CSV caricato automaticamente: `{default_csv_path.name}`")
    
    if default_json_path.exists():
        st.session_state['default_json'] = default_json_path
        st.sidebar.info(f"✅ JSON caricato automaticamente: `{default_json_path.name}`")
    
    if default_graph_path.exists():
        st.session_state['default_graph'] = default_graph_path
        st.sidebar.info(f"✅ Graph JSON caricato automaticamente: `{default_graph_path.name}`")
    
    st.session_state['default_files_loaded'] = True

uploaded_csv = st.sidebar.file_uploader(
    "CSV Export (richiesto)",
    type=["csv"],
    help="File CSV generato da Probe Prompts (es. *_export.csv o *_export_ENRICHED.csv)"
)

uploaded_json = st.sidebar.file_uploader(
    "JSON Attivazioni (opzionale)",
    type=["json"],
    help="File JSON con attivazioni token-by-token (migliora naming per Relationship)"
)

uploaded_graph = st.sidebar.file_uploader(
    "Graph JSON (opzionale)",
    type=["json"],
    help="File Graph JSON originale (per csv_ctx_idx fallback in Semantic naming)"
)

# Parametri pipeline
st.sidebar.subheader("🎛️ Parametri Pipeline")

window_size = st.sidebar.slider(
    "Finestra ricerca target",
    min_value=3,
    max_value=15,
    value=7,
    help="Numero massimo di token da esplorare per trovare target semantici"
)

# Soglie classificazione
st.sidebar.subheader("📊 Soglie Classificazione")

# Gestione soglie (salva/carica)
st.sidebar.markdown("**💾 Gestione Soglie**")

col_save, col_load = st.sidebar.columns(2)

with col_save:
    # Prepara soglie correnti per export
    current_thresholds = {
        'dict_peak_consistency_min': st.session_state.get('dict_consistency', DEFAULT_THRESHOLDS['dict_peak_consistency_min']),
        'dict_n_distinct_peaks_max': st.session_state.get('dict_n_peaks', DEFAULT_THRESHOLDS['dict_n_distinct_peaks_max']),
        'sayx_func_vs_sem_min': st.session_state.get('sayx_func_min', DEFAULT_THRESHOLDS['sayx_func_vs_sem_min']),
        'sayx_conf_f_min': st.session_state.get('sayx_conf_f', DEFAULT_THRESHOLDS['sayx_conf_f_min']),
        'sayx_layer_min': st.session_state.get('sayx_layer', DEFAULT_THRESHOLDS['sayx_layer_min']),
        'rel_sparsity_max': st.session_state.get('rel_sparsity', DEFAULT_THRESHOLDS['rel_sparsity_max']),
        'sem_layer_max': st.session_state.get('sem_layer', DEFAULT_THRESHOLDS['sem_layer_max']),
        'sem_conf_s_min': st.session_state.get('sem_conf_s', DEFAULT_THRESHOLDS['sem_conf_s_min']),
        'sem_func_vs_sem_max': st.session_state.get('sem_func_vs_sem', DEFAULT_THRESHOLDS['sem_func_vs_sem_max']),
    }
    
    thresholds_json = json.dumps(current_thresholds, indent=2)
    st.download_button(
        label="💾 Salva",
        data=thresholds_json,
        file_name=f"thresholds_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
        help="Scarica le soglie correnti come JSON",
        use_container_width=True
    )

with col_load:
    uploaded_thresholds = st.file_uploader(
        "Carica Soglie",
        type=['json'],
        help="Carica soglie da file JSON",
        label_visibility="collapsed",
        key="upload_thresholds"
    )

# Carica soglie da file se fornito
if uploaded_thresholds is not None:
    try:
        loaded_thresholds = json.load(uploaded_thresholds)
        
        # Valida che contenga tutte le chiavi necessarie
        required_keys = set(DEFAULT_THRESHOLDS.keys())
        loaded_keys = set(loaded_thresholds.keys())
        
        if required_keys == loaded_keys:
            # Aggiorna session state
            st.session_state['dict_consistency'] = loaded_thresholds['dict_peak_consistency_min']
            st.session_state['dict_n_peaks'] = loaded_thresholds['dict_n_distinct_peaks_max']
            st.session_state['sayx_func_min'] = loaded_thresholds['sayx_func_vs_sem_min']
            st.session_state['sayx_conf_f'] = loaded_thresholds['sayx_conf_f_min']
            st.session_state['sayx_layer'] = loaded_thresholds['sayx_layer_min']
            st.session_state['rel_sparsity'] = loaded_thresholds['rel_sparsity_max']
            st.session_state['sem_layer'] = loaded_thresholds['sem_layer_max']
            st.session_state['sem_conf_s'] = loaded_thresholds['sem_conf_s_min']
            st.session_state['sem_func_vs_sem'] = loaded_thresholds['sem_func_vs_sem_max']
            
            st.sidebar.success("✅ Soglie caricate!")
            # Rimuovi il file uploader per evitare reload continui
            st.session_state['upload_thresholds'] = None
            st.rerun()
        else:
            missing = required_keys - loaded_keys
            extra = loaded_keys - required_keys
            error_msg = []
            if missing:
                error_msg.append(f"Chiavi mancanti: {', '.join(missing)}")
            if extra:
                error_msg.append(f"Chiavi extra: {', '.join(extra)}")
            st.sidebar.error(f"❌ File JSON non valido:\n" + "\n".join(error_msg))
    except json.JSONDecodeError as e:
        st.sidebar.error(f"❌ Errore parsing JSON: {e}")
    except Exception as e:
        st.sidebar.error(f"❌ Errore caricamento soglie: {e}")

# Reset soglie
if st.sidebar.button("🔄 Reset Default", help="Ripristina soglie di default", use_container_width=True):
    for key in ['dict_consistency', 'dict_n_peaks', 'sayx_func_min', 'sayx_conf_f', 
                'sayx_layer', 'rel_sparsity', 'sem_layer', 'sem_conf_s', 'sem_func_vs_sem']:
        if key in st.session_state:
            del st.session_state[key]
    st.sidebar.success("✅ Soglie ripristinate!")
    st.rerun()

st.sidebar.markdown("---")

with st.sidebar.expander("Dictionary Semantic", expanded=False):
    dict_consistency = st.slider(
        "Peak Consistency (min)",
        min_value=0.5,
        max_value=1.0,
        value=st.session_state.get('dict_consistency', DEFAULT_THRESHOLDS['dict_peak_consistency_min']),
        step=0.05,
        help="Quanto spesso il token deve essere peak quando appare nel prompt",
        key='dict_consistency'
    )
    dict_n_peaks = st.number_input(
        "N Distinct Peaks (max)",
        min_value=1,
        max_value=5,
        value=st.session_state.get('dict_n_peaks', DEFAULT_THRESHOLDS['dict_n_distinct_peaks_max']),
        help="Numero massimo di token distinti come peak",
        key='dict_n_peaks'
    )

with st.sidebar.expander("Say X", expanded=False):
    sayx_func_min = st.slider(
        "Func vs Sem % (min)",
        min_value=0.0,
        max_value=100.0,
        value=st.session_state.get('sayx_func_min', DEFAULT_THRESHOLDS['sayx_func_vs_sem_min']),
        step=5.0,
        help="Differenza % tra max activation su functional vs semantic",
        key='sayx_func_min'
    )
    sayx_conf_f = st.slider(
        "Confidence F (min)",
        min_value=0.5,
        max_value=1.0,
        value=st.session_state.get('sayx_conf_f', DEFAULT_THRESHOLDS['sayx_conf_f_min']),
        step=0.05,
        help="Frazione di peak su token funzionali",
        key='sayx_conf_f'
    )
    sayx_layer = st.number_input(
        "Layer (min)",
        min_value=0,
        max_value=30,
        value=st.session_state.get('sayx_layer', DEFAULT_THRESHOLDS['sayx_layer_min']),
        help="Layer minimo per Say X (tipicamente layer alti)",
        key='sayx_layer'
    )

with st.sidebar.expander("Relationship", expanded=False):
    rel_sparsity = st.slider(
        "Sparsity (max)",
        min_value=0.0,
        max_value=1.0,
        value=st.session_state.get('rel_sparsity', DEFAULT_THRESHOLDS['rel_sparsity_max']),
        step=0.05,
        help="Sparsity massima (bassa = attivazione diffusa)",
        key='rel_sparsity'
    )

with st.sidebar.expander("Semantic (Concept)", expanded=False):
    sem_layer = st.number_input(
        "Layer (max)",
        min_value=0,
        max_value=10,
        value=st.session_state.get('sem_layer', DEFAULT_THRESHOLDS['sem_layer_max']),
        help="Layer massimo per fallback Dictionary",
        key='sem_layer'
    )
    sem_conf_s = st.slider(
        "Confidence S (min)",
        min_value=0.0,
        max_value=1.0,
        value=st.session_state.get('sem_conf_s', DEFAULT_THRESHOLDS['sem_conf_s_min']),
        step=0.05,
        help="Frazione di peak su token semantici",
        key='sem_conf_s'
    )
    sem_func_vs_sem = st.slider(
        "Func vs Sem % (max)",
        min_value=0.0,
        max_value=100.0,
        value=st.session_state.get('sem_func_vs_sem', DEFAULT_THRESHOLDS['sem_func_vs_sem_max']),
        step=5.0,
        help="Differenza % massima per considerare Semantic",
        key='sem_func_vs_sem'
    )

# ===== MAIN: PIPELINE EXECUTION =====

# Usa file caricati o default
csv_to_use = uploaded_csv if uploaded_csv is not None else st.session_state.get('default_csv')
json_to_use = uploaded_json if uploaded_json is not None else st.session_state.get('default_json')
graph_to_use = uploaded_graph if uploaded_graph is not None else st.session_state.get('default_graph')

if csv_to_use is None:
    st.warning("⬆️ Carica un file CSV per iniziare")
    st.markdown("""
    ### 📖 Come Funziona
    
    #### Step 1: Preparazione Dataset
    - **Classifica token**: Identifica token funzionali (es. "is", "the", ",") vs semantici (es. "Texas", "capital")
    - **Target tokens**: Per token funzionali, trova il primo token semantico nella direzione specificata
    - **Fonte**: Usa tokens dal JSON se disponibile, altrimenti tokenizzazione fallback
    
    #### Step 2: Classificazione Nodi
    
    Ogni feature viene classificata in base a metriche aggregate:
    
    - **Semantic (Dictionary)**: Si attiva sempre sullo stesso token specifico
      - Es: Feature che si attiva solo su "Texas"
      - Caratteristiche: peak_consistency alta, n_distinct_peaks = 1
    
    - **Semantic (Concept)**: Si attiva su token semanticamente simili
      - Es: Feature che si attiva su "city", "capital", "state"
      - Caratteristiche: conf_S alta, layer medio-basso
    
    - **Say X**: Si attiva su token funzionali per predire il prossimo token
      - Es: Feature che si attiva su "is" prima di "Austin"
      - Caratteristiche: func_vs_sem alta, conf_F alta, layer alto
    
    - **Relationship**: Collega concetti semantici multipli
      - Es: Feature che si attiva su "city", "capital", "state" insieme
      - Caratteristiche: sparsity bassa (attivazione diffusa), K alto
    
    #### Step 3: Naming Supernodi
    
    Genera nomi descrittivi per ogni supernodo:
    
    - **Relationship**: `"(X) related"` dove X è il primo token semantico con max attivazione
    - **Semantic**: Nome del token con max activation (es. "Texas", "city")
    - **Say X**: `"Say (X)"` dove X è il target_token (es. "Say (Austin)")
    
    ### 🎯 Parametri Chiave
    
    - **Peak Consistency**: Quanto spesso un token è peak quando appare nel prompt
    - **Func vs Sem %**: Differenza % tra max activation su functional vs semantic
    - **Confidence F/S**: Frazione di peak su token funzionali/semantici
    - **Sparsity**: Quanto l'attivazione è concentrata (alta) vs diffusa (bassa)
    - **Layer**: Layer del modello dove risiede la feature
    """)
    st.stop()

# Carica CSV
try:
    if isinstance(csv_to_use, Path):
        # File di default (path)
        df = pd.read_csv(csv_to_use)
        csv_name = csv_to_use.name
    else:
        # File uploadato
        df = pd.read_csv(csv_to_use)
        csv_name = csv_to_use.name if hasattr(csv_to_use, 'name') else 'uploaded file'
    
    st.success(f"✅ CSV caricato: {csv_name} - {len(df)} righe, {df['feature_key'].nunique()} feature uniche")
except Exception as e:
    st.error(f"❌ Errore caricamento CSV: {e}")
    st.stop()

# Carica JSON (opzionale)
tokens_json = None
if json_to_use:
    try:
        if isinstance(json_to_use, Path):
            # File di default (path)
            with open(json_to_use, 'r', encoding='utf-8') as f:
                tokens_json = json.load(f)
            json_name = json_to_use.name
        else:
            # File uploadato
            tokens_json = json.load(json_to_use)
            json_name = json_to_use.name if hasattr(json_to_use, 'name') else 'uploaded file'
        
        n_prompts = len(tokens_json.get('results', []))
        st.success(f"✅ JSON attivazioni caricato: {json_name} - {n_prompts} prompt")
    except Exception as e:
        st.warning(f"⚠️ Errore caricamento JSON: {e}")

# ===== STEP 1: PREPARAZIONE =====

st.header("📋 Step 1: Preparazione Dataset")

with st.expander("ℹ️ Cosa fa questo step?", expanded=False):
    st.markdown("""
    **Classifica ogni token** come:
    - **Functional**: Token con bassa specificità semantica (es. "is", "the", ",")
    - **Semantic**: Token con significato specifico (es. "Texas", "capital")
    
    **Trova target tokens** per token funzionali:
    - Token funzionali "puntano" a token semantici vicini
    - Es: "is" → "Austin" (forward), "," → "Texas" (backward) + "USA" (forward)
    
    **Fonte tokens**:
    - Preferisce tokens dal JSON attivazioni (più accurato)
    - Fallback su tokenizzazione del prompt text
    """)

if st.button("▶️ Esegui Step 1", key="run_step1"):
    with st.spinner("Preparazione dataset in corso..."):
        try:
            df_prepared = prepare_dataset(
                df,
                tokens_json=tokens_json,
                window=window_size,
                verbose=False
            )
            
            # Salva in session state
            st.session_state['df_prepared'] = df_prepared
            
            # Statistiche
            n_functional = (df_prepared['peak_token_type'] == 'functional').sum()
            n_semantic = (df_prepared['peak_token_type'] == 'semantic').sum()
            n_json = (df_prepared['tokens_source'] == 'json').sum()
            n_fallback = (df_prepared['tokens_source'] == 'fallback').sum()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Token Funzionali", f"{n_functional} ({n_functional/len(df_prepared)*100:.1f}%)")
            with col2:
                st.metric("Token Semantici", f"{n_semantic} ({n_semantic/len(df_prepared)*100:.1f}%)")
            with col3:
                st.metric("Tokens da JSON", f"{n_json}/{len(df_prepared)}")
            
            st.success("✅ Step 1 completato!")
            
        except Exception as e:
            st.error(f"❌ Errore Step 1: {e}")
            import traceback
            st.code(traceback.format_exc())

# Mostra risultati Step 1
if 'df_prepared' in st.session_state:
    df_prepared = st.session_state['df_prepared']
    
    st.subheader("📊 Risultati Step 1")
    
    # Tabella completa
    st.write(f"**Risultati completi** ({len(df_prepared)} righe):")
    display_cols = ['feature_key', 'prompt', 'peak_token', 'peak_token_type', 'target_tokens', 'tokens_source']
    st.dataframe(df_prepared[display_cols], use_container_width=True, height=400)
    
    # Download
    csv_step1 = df_prepared.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="💾 Download CSV Step 1",
        data=csv_step1,
        file_name=f"node_grouping_step1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )

# ===== STEP 2: CLASSIFICAZIONE =====

st.header("🏷️ Step 2: Classificazione Nodi")

with st.expander("ℹ️ Cosa fa questo step?", expanded=False):
    st.markdown("""
    **Classifica ogni feature** in base a metriche aggregate:
    
    **Albero Decisionale**:
    1. **Dictionary Semantic**: peak_consistency ≥ 0.8 AND n_distinct_peaks ≤ 1
    2. **Say X**: func_vs_sem ≥ 50% AND conf_F ≥ 0.90 AND layer ≥ 7
    3. **Relationship**: sparsity < 0.45
    4. **Semantic (Concept)**: layer ≤ 3 OR conf_S ≥ 0.50 OR func_vs_sem < 50%
    5. **Review**: Casi ambigui che richiedono revisione manuale
    
    **Metriche Calcolate**:
    - `peak_consistency_main`: Quanto spesso il token principale è peak quando appare
    - `n_distinct_peaks`: Numero di token distinti come peak
    - `func_vs_sem_pct`: Differenza % tra max activation su functional vs semantic
    - `conf_F / conf_S`: Frazione di peak su token funzionali/semantici
    - `sparsity_median`: Mediana sparsity (solo prompt attivi)
    - `K_sem_distinct`: Numero di token semantici distinti
    """)

if 'df_prepared' not in st.session_state:
    st.warning("⚠️ Esegui prima Step 1")
else:
    # Prepara soglie custom
    custom_thresholds = {
        'dict_peak_consistency_min': dict_consistency,
        'dict_n_distinct_peaks_max': dict_n_peaks,
        'sayx_func_vs_sem_min': sayx_func_min,
        'sayx_conf_f_min': sayx_conf_f,
        'sayx_layer_min': sayx_layer,
        'rel_sparsity_max': rel_sparsity,
        'sem_layer_max': sem_layer,
        'sem_conf_s_min': sem_conf_s,
        'sem_func_vs_sem_max': sem_func_vs_sem,
    }
    
    if st.button("▶️ Esegui Step 2", key="run_step2"):
        with st.spinner("Classificazione nodi in corso..."):
            try:
                df_classified = classify_nodes(
                    st.session_state['df_prepared'],
                    thresholds=custom_thresholds,
                    verbose=False
                )
                
                # Salva in session state
                st.session_state['df_classified'] = df_classified
                
                # Statistiche
                classifications = df_classified.groupby('feature_key')['pred_label'].first()
                label_counts = classifications.value_counts()
                
                st.success("✅ Step 2 completato!")
                
                # Visualizza distribuzione
                st.subheader("📊 Distribuzione Classi")
                
                cols = st.columns(len(label_counts))
                for i, (label, count) in enumerate(label_counts.items()):
                    with cols[i]:
                        pct = 100 * count / len(classifications)
                        st.metric(label, f"{count} ({pct:.1f}%)")
                
                # Review warnings
                n_review = df_classified['review'].sum()
                if n_review > 0:
                    st.warning(f"⚠️ {n_review} righe richiedono review manuale")
                    review_features = df_classified[df_classified['review']]['feature_key'].unique()
                    st.write(f"Feature keys: {', '.join(review_features[:5])}")
                
            except Exception as e:
                st.error(f"❌ Errore Step 2: {e}")
                import traceback
                st.code(traceback.format_exc())

# Mostra risultati Step 2
if 'df_classified' in st.session_state:
    df_classified = st.session_state['df_classified']
    
    st.subheader("📊 Risultati Step 2")
    
    # Filtro per classe
    selected_classes = st.multiselect(
        "Filtra per classe",
        options=df_classified['pred_label'].unique(),
        default=df_classified['pred_label'].unique()
    )
    
    df_filtered = df_classified[df_classified['pred_label'].isin(selected_classes)]
    
    # Riordina colonne
    priority_cols = [
        'feature_key', 'layer', 'prompt', 'supernode_class', 'pred_label', 
        'subtype', 'confidence', 'review', 'why_review', 'peak_token'
    ]
    
    # Colonne rimanenti (escludi quelle già in priority)
    other_cols = [col for col in df_filtered.columns if col not in priority_cols]
    
    # Ordine finale: priority + altre
    ordered_cols = [col for col in priority_cols if col in df_filtered.columns] + other_cols
    df_display = df_filtered[ordered_cols]
    
    # Tabella completa con tutte le colonne
    st.write(f"**Risultati completi** ({len(df_filtered)} righe, {len(df_filtered.columns)} colonne):")
    st.dataframe(
        df_display, 
        use_container_width=True, 
        height=400,
        column_config={
            "prompt": st.column_config.TextColumn(
                "prompt",
                width="medium",  # Larghezza ridotta
                help="Testo del prompt"
            )
        }
    )
    
    # Ricerca e spiegazione feature
    st.subheader("🔍 Spiega Classificazione Feature")
    
    col_search, col_filter = st.columns([3, 1])
    
    with col_search:
        feature_to_explain = st.text_input(
            "Cerca feature_key",
            placeholder="es. 22_11998",
            help="Inserisci il feature_key per vedere la spiegazione della classificazione"
        )
    
    with col_filter:
        st.write("")  # Spacer per allineamento
        filter_table = st.checkbox(
            "Filtra tabella",
            value=True,
            help="Mostra solo le righe della feature cercata nella tabella sopra"
        )
    
    # Aggiorna tabella se feature cercata e filtro attivo
    if feature_to_explain and filter_table:
        df_filtered_search = df_display[df_display['feature_key'] == feature_to_explain]
        
        if len(df_filtered_search) > 0:
            st.info(f"📌 Tabella filtrata per feature: **{feature_to_explain}** ({len(df_filtered_search)} righe)")
            st.dataframe(
                df_filtered_search, 
                use_container_width=True, 
                height=min(200, len(df_filtered_search) * 35 + 38),  # Altezza dinamica
                column_config={
                    "prompt": st.column_config.TextColumn(
                        "prompt",
                        width="medium",
                        help="Testo del prompt"
                    )
                }
            )
        else:
            st.warning(f"⚠️ Nessuna riga trovata per feature '{feature_to_explain}' nei risultati filtrati")
    
    if feature_to_explain:
        # Trova la feature
        feature_data = df_classified[df_classified['feature_key'] == feature_to_explain]
        
        if len(feature_data) == 0:
            st.warning(f"⚠️ Feature '{feature_to_explain}' non trovata nel dataset")
        else:
            # Prendi il primo record (tutti hanno stessa classificazione per feature_key)
            record = feature_data.iloc[0]
            
            # Estrai metriche aggregate (ricalcola se necessario)
            feature_group = df_classified[df_classified['feature_key'] == feature_to_explain]
            feature_metrics_df = node_grouping.aggregate_feature_metrics(feature_group)
            
            if len(feature_metrics_df) > 0:
                metrics = feature_metrics_df.iloc[0]
                
                # Box con info generale
                st.info(f"""
                **Feature**: `{feature_to_explain}`  
                **Classificazione**: **{record['pred_label']}**  
                **Subtype**: {record['subtype'] if pd.notna(record['subtype']) else 'N/A'}  
                **Confidence**: {record['confidence']:.2f}  
                **Review**: {'⚠️ Sì' if record['review'] else '✅ No'}
                """)
                
                # Metriche chiave
                st.write("**📊 Metriche Aggregate**:")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Layer", int(metrics['layer']))
                with col2:
                    st.metric("Peak Consistency", f"{metrics['peak_consistency_main']:.2f}")
                with col3:
                    st.metric("N Distinct Peaks", int(metrics['n_distinct_peaks']))
                with col4:
                    st.metric("Func vs Sem %", f"{metrics['func_vs_sem_pct']:.1f}%")
                
                col5, col6, col7, col8 = st.columns(4)
                with col5:
                    st.metric("Conf F", f"{metrics['conf_F']:.2f}")
                with col6:
                    st.metric("Conf S", f"{metrics['conf_S']:.2f}")
                with col7:
                    st.metric("Sparsity", f"{metrics['sparsity_median']:.2f}")
                with col8:
                    st.metric("K Semantic", int(metrics['K_sem_distinct']))
                
                # Genera spiegazione
                st.write("**💡 Spiegazione Classificazione**:")
                
                pred_label = record['pred_label']
                layer = int(metrics['layer'])
                peak_cons = metrics['peak_consistency_main']
                n_peaks = int(metrics['n_distinct_peaks'])
                func_vs_sem = metrics['func_vs_sem_pct']
                conf_F = metrics['conf_F']
                conf_S = metrics['conf_S']
                sparsity = metrics['sparsity_median']
                
                # Genera spiegazione basata sulla classe
                if pred_label == "Semantic":
                    # Determina quale regola ha attivato
                    if peak_cons >= custom_thresholds['dict_peak_consistency_min'] and n_peaks <= custom_thresholds['dict_n_distinct_peaks_max']:
                        explanation = f"""
La feature **{feature_to_explain}** è stata classificata come **Semantic (Dictionary)** perché:

1. **Peak Consistency** = {peak_cons:.2f} (≥ {custom_thresholds['dict_peak_consistency_min']:.2f} ✅)
   - Il token principale è peak in **{peak_cons*100:.0f}%** dei casi in cui appare nel prompt
   - Indica una feature molto selettiva su un token specifico

2. **N Distinct Peaks** = {n_peaks} (≤ {custom_thresholds['dict_n_distinct_peaks_max']} ✅)
   - La feature si attiva sempre sullo stesso token
   - Comportamento tipico di feature "dizionario" (es. sempre su "Texas")

**Regola applicata**: Dictionary Semantic (priorità massima)
                        """
                    elif layer <= custom_thresholds['sem_layer_max']:
                        explanation = f"""
La feature **{feature_to_explain}** è stata classificata come **Semantic (Dictionary fallback)** perché:

1. **Layer** = {layer} (≤ {custom_thresholds['sem_layer_max']} ✅)
   - Layer basso tipico di feature semantiche di base
   - Fallback conservativo per layer bassi

2. **Confidence S** = {conf_S:.2f}
   - Frazione di peak su token semantici: {conf_S*100:.0f}%

**Regola applicata**: Semantic Concept (fallback layer basso)
                        """
                    elif func_vs_sem < custom_thresholds['sem_func_vs_sem_max']:
                        explanation = f"""
La feature **{feature_to_explain}** è stata classificata come **Semantic (Concept)** perché:

1. **Func vs Sem %** = {func_vs_sem:.1f}% (< {custom_thresholds['sem_func_vs_sem_max']:.1f}% ✅)
   - La differenza tra max activation su functional vs semantic è piccola
   - Indica che la feature si attiva principalmente su token semantici

2. **Confidence S** = {conf_S:.2f}
   - Frazione di peak su token semantici: {conf_S*100:.0f}%

3. **Layer** = {layer}
   - Layer medio, tipico di feature concettuali

**Regola applicata**: Semantic Concept
                        """
                    else:
                        explanation = f"""
La feature **{feature_to_explain}** è stata classificata come **Semantic (Concept)** perché:

1. **Confidence S** = {conf_S:.2f} (≥ {custom_thresholds['sem_conf_s_min']:.2f} ✅)
   - Frazione di peak su token semantici: {conf_S*100:.0f}%
   - Dominanza di token semantici

2. **Layer** = {layer}

**Regola applicata**: Semantic Concept
                        """
                
                elif pred_label == 'Say "X"':
                    explanation = f"""
La feature **{feature_to_explain}** è stata classificata come **Say "X"** perché:

1. **Func vs Sem %** = {func_vs_sem:.1f}% (≥ {custom_thresholds['sayx_func_vs_sem_min']:.1f}% ✅)
   - La max activation su token funzionali è **{func_vs_sem:.1f}%** maggiore che su semantici
   - Indica forte preferenza per token funzionali (es. "is", ",")

2. **Confidence F** = {conf_F:.2f} (≥ {custom_thresholds['sayx_conf_f_min']:.2f} ✅)
   - Frazione di peak su token funzionali: {conf_F*100:.0f}%
   - Quasi tutti i peak sono su token funzionali

3. **Layer** = {layer} (≥ {custom_thresholds['sayx_layer_min']} ✅)
   - Layer alto tipico di feature predittive
   - Say X features sono tipicamente nei layer finali

**Regola applicata**: Say "X" (predice prossimo token)
                    """
                
                elif pred_label == "Relationship":
                    explanation = f"""
La feature **{feature_to_explain}** è stata classificata come **Relationship** perché:

1. **Sparsity** = {sparsity:.2f} (< {custom_thresholds['rel_sparsity_max']:.2f} ✅)
   - Sparsity bassa indica attivazione **diffusa** nel prompt
   - La feature si attiva su multipli token, non concentrata su uno solo

2. **K Semantic** = {int(metrics['K_sem_distinct'])}
   - Numero di token semantici distinti su cui si attiva
   - Indica collegamento tra concetti multipli

3. **Layer** = {layer}
   - Layer medio-basso tipico di feature relazionali

**Regola applicata**: Relationship (collega concetti multipli)
                    """
                
                else:
                    explanation = f"""
La feature **{feature_to_explain}** richiede **review manuale**.

**Motivo**: {record['why_review']}

**Metriche**:
- Layer: {layer}
- Peak Consistency: {peak_cons:.2f}
- Func vs Sem %: {func_vs_sem:.1f}%
- Confidence F/S: {conf_F:.2f} / {conf_S:.2f}
- Sparsity: {sparsity:.2f}
                    """
                
                st.markdown(explanation)
                
                # Mostra albero decisionale applicato
                with st.expander("🌳 Albero Decisionale Completo", expanded=False):
                    st.markdown(f"""
**Ordine di valutazione**:

1. ✅ **Dictionary Semantic**: peak_consistency ≥ {custom_thresholds['dict_peak_consistency_min']:.2f} AND n_distinct_peaks ≤ {custom_thresholds['dict_n_distinct_peaks_max']}
   - Risultato: {'✅ MATCH' if pred_label == 'Semantic' and peak_cons >= custom_thresholds['dict_peak_consistency_min'] and n_peaks <= custom_thresholds['dict_n_distinct_peaks_max'] else '❌ No match'}

2. ✅ **Say "X"**: func_vs_sem ≥ {custom_thresholds['sayx_func_vs_sem_min']:.1f}% AND conf_F ≥ {custom_thresholds['sayx_conf_f_min']:.2f} AND layer ≥ {custom_thresholds['sayx_layer_min']}
   - Risultato: {'✅ MATCH' if pred_label == 'Say "X"' else '❌ No match'}

3. ✅ **Relationship**: sparsity < {custom_thresholds['rel_sparsity_max']:.2f}
   - Risultato: {'✅ MATCH' if pred_label == 'Relationship' else '❌ No match'}

4. ✅ **Semantic (Concept)**: layer ≤ {custom_thresholds['sem_layer_max']} OR conf_S ≥ {custom_thresholds['sem_conf_s_min']:.2f} OR func_vs_sem < {custom_thresholds['sem_func_vs_sem_max']:.1f}%
   - Risultato: {'✅ MATCH' if pred_label == 'Semantic' else '❌ No match'}

5. ⚠️ **Review**: Casi ambigui

**Classificazione finale**: **{pred_label}**
                    """)
            else:
                st.error("❌ Impossibile calcolare metriche aggregate per questa feature")
    
    # Download
    csv_step2 = df_classified.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="💾 Download CSV Step 2",
        data=csv_step2,
        file_name=f"node_grouping_step2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )

# ===== STEP 3: NAMING =====

st.header("🏷️ Step 3: Naming Supernodi")

with st.expander("ℹ️ Cosa fa questo step?", expanded=False):
    st.markdown("""
    **Genera nomi descrittivi** per ogni supernodo:
    
    **Regole di Naming**:
    - **Relationship**: `"(X) related"` dove X è il primo token semantico con max attivazione dal prompt originale
      - Richiede JSON attivazioni per accuratezza
      - Fallback: usa peak_token del record con max activation
    
    - **Semantic**: Nome del token con max activation
      - Es: "Texas", "city", "capital"
      - Mantiene maiuscola se presente in almeno un'occorrenza
      - Casi edge: "punctuation", "Semantic (unknown)"
    
    - **Say X**: `"Say (X)"` dove X è il target_token del record con max activation
      - Es: "Say (Austin)", "Say (capital)"
      - Tie-break: distance minore, poi backward > forward
      - Fallback: "Say (?)" se nessun target trovato
    
    **Normalizzazione**:
    - Strip whitespace
    - Rimuove punteggiatura trailing (es. "entity:" → "entity")
    - Mantiene maiuscola se presente (es. "Texas" non "texas")
    """)

if 'df_classified' not in st.session_state:
    st.warning("⚠️ Esegui prima Step 2")
else:
    if st.button("▶️ Esegui Step 3", key="run_step3"):
        with st.spinner("Naming supernodi in corso..."):
            try:
                # Salva JSON temporaneo se disponibile
                json_path = None
                if tokens_json:
                    json_path = Path("temp_activations.json")
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(tokens_json, f)
                
                # Determina path al Graph JSON
                graph_path = None
                if graph_to_use:
                    if isinstance(graph_to_use, Path):
                        graph_path = str(graph_to_use)
                    else:
                        # Se è un file caricato, salva temporaneamente
                        graph_path = Path("temp_graph.json")
                        graph_json_content = json.loads(graph_to_use.read().decode('utf-8'))
                        with open(graph_path, 'w', encoding='utf-8') as f:
                            json.dump(graph_json_content, f)
                
                df_named = name_nodes(
                    st.session_state['df_classified'],
                    activations_json_path=str(json_path) if json_path else None,
                    graph_json_path=graph_path,
                    verbose=False
                )
                
                # Rimuovi file temporanei
                if json_path and json_path.exists():
                    json_path.unlink()
                if graph_path and Path(graph_path).name == "temp_graph.json" and Path(graph_path).exists():
                    Path(graph_path).unlink()
                
                # Salva in session state
                st.session_state['df_named'] = df_named
                
                # Statistiche
                n_features = df_named['feature_key'].nunique()
                n_unique_names = df_named.groupby('feature_key')['supernode_name'].first().nunique()
                
                st.success("✅ Step 3 completato!")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Feature Totali", n_features)
                with col2:
                    st.metric("Nomi Unici", n_unique_names)
                
                # Esempi per classe (compatti, senza duplicati)
                st.subheader("📝 Esempi Naming per Classe")
                
                for label in ['Relationship', 'Semantic', 'Say "X"']:
                    # Prendi nomi unici (no duplicati)
                    examples = df_named[df_named['pred_label'] == label].groupby('feature_key')['supernode_name'].first().unique()
                    if len(examples) > 0:
                        # Limita a max 5 esempi
                        examples_str = ', '.join([f'"{ex}"' for ex in examples[:5]])
                        st.write(f"**{label}**: {examples_str}")
                
            except Exception as e:
                st.error(f"❌ Errore Step 3: {e}")
                import traceback
                st.code(traceback.format_exc())

# Mostra risultati Step 3
if 'df_named' in st.session_state:
    df_named = st.session_state['df_named']
    
    st.subheader("📊 Risultati Step 3 (Finale)")
    
    # Filtro per classe
    selected_classes_final = st.multiselect(
        "Filtra per classe (finale)",
        options=df_named['pred_label'].unique(),
        default=df_named['pred_label'].unique(),
        key="filter_final"
    )
    
    df_filtered_final = df_named[df_named['pred_label'].isin(selected_classes_final)]
    
    # Riordina colonne
    priority_cols = [
        'feature_key', 'layer', 'prompt', 'supernode_label', 'supernode_name', 'pred_label', 
        'subtype', 'peak_token','activation_max', 'target_tokens'
    ]
    
    # Colonne rimanenti (escludi quelle già in priority)
    other_cols = [col for col in df_filtered_final.columns if col not in priority_cols]
    
    # Ordine finale: priority + altre
    ordered_cols = [col for col in priority_cols if col in df_filtered_final.columns] + other_cols
    df_display_final = df_filtered_final[ordered_cols]
    
    # Tabella completa con tutte le colonne
    st.write(f"**Risultati completi** ({len(df_filtered_final)} righe, {len(df_filtered_final.columns)} colonne):")
    st.dataframe(
        df_display_final, 
        use_container_width=True, 
        height=400,
        column_config={
            "prompt": st.column_config.TextColumn(
                "prompt",
                width="medium",  # Larghezza ridotta
                help="Testo del prompt"
            )
        }
    )
    
    # Raggruppa per supernode_name
    st.subheader("🔍 Analisi per Supernode Name")
    
    # Calcola node_influence per feature (prendi 1 valore per feature, non tutte le righe)
    if 'node_influence' in df_named.columns:
        # Prendi node_influence per ogni feature_key (usa il primo valore, sono tutti uguali per la stessa feature)
        feature_influence = df_named.groupby('feature_key')['node_influence'].first().reset_index()
        
        # Aggiungi supernode_name per ogni feature
        feature_to_name = df_named.groupby('feature_key')['supernode_name'].first().reset_index()
        feature_influence = feature_influence.merge(feature_to_name, on='feature_key')
        
        # Somma node_influence per supernode_name
        name_influence = feature_influence.groupby('supernode_name')['node_influence'].sum().reset_index()
        name_influence.columns = ['supernode_name', 'total_influence']
    else:
        name_influence = None
    
    # Aggregazioni base
    name_groups = df_named.groupby('supernode_name').agg({
        'feature_key': 'nunique',
        'pred_label': lambda x: x.mode()[0] if len(x) > 0 else '',
        'layer': lambda x: f"{x.min()}-{x.max()}" if x.min() != x.max() else str(x.min())
    }).reset_index()
    name_groups.columns = ['Supernode Name', 'N Features', 'Classe', 'Layer Range']
    
    # Aggiungi total_influence se disponibile
    if name_influence is not None:
        name_groups = name_groups.merge(
            name_influence.rename(columns={'supernode_name': 'Supernode Name', 'total_influence': 'Total Influence'}),
            on='Supernode Name',
            how='left'
        )
        # Ordina per Total Influence (decrescente)
        name_groups = name_groups.sort_values('Total Influence', ascending=False)
    else:
        name_groups = name_groups.sort_values('N Features', ascending=False)
    
    st.dataframe(name_groups, use_container_width=True)
    
    # Download finale
    st.subheader("💾 Download Risultati")
    
    col1, col2 = st.columns(2)
    
    with col1:
        csv_final = df_named.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download CSV Completo",
            data=csv_final,
            file_name=f"node_grouping_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    
    with col2:
        # Export summary JSON
        summary = {
            'timestamp': datetime.now().isoformat(),
            'n_features': int(df_named['feature_key'].nunique()),
            'n_unique_names': int(df_named.groupby('feature_key')['supernode_name'].first().nunique()),
            'class_distribution': df_named.groupby('feature_key')['pred_label'].first().value_counts().to_dict(),
            'thresholds_used': custom_thresholds,
            'top_supernodes': name_groups.head(10).to_dict('records')
        }
        
        json_summary = json.dumps(summary, indent=2).encode('utf-8')
        st.download_button(
            label="📥 Download Summary JSON",
            data=json_summary,
            file_name=f"node_grouping_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
    
    # Upload su Neuronpedia
    st.divider()
    st.subheader("🌐 Upload su Neuronpedia")
    
    st.info("Carica il subgrafo con i supernodes su Neuronpedia per visualizzazione interattiva.")
    
    # API Key input
    api_key = st.text_input(
        "API Key Neuronpedia",
        type="password",
        help="Inserisci la tua API key di Neuronpedia (richiesta per l'upload)"
    )
    
    # Display name
    display_name = st.text_input(
        "Display Name",
        value=f"Node Grouping - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        help="Nome visualizzato per il subgrafo su Neuronpedia"
    )
    
    # Overwrite ID (opzionale)
    overwrite_id = st.text_input(
        "Overwrite ID (opzionale)",
        value="",
        help="Se fornito, sovrascrive un subgrafo esistente invece di crearne uno nuovo"
    )
    
    # Verifica che abbiamo Graph JSON
    graph_json_available = st.session_state.get('graph_json_uploaded') is not None
    
    if not graph_json_available:
        st.warning("⚠️ Graph JSON non caricato. Carica il Graph JSON in Step 3 per abilitare l'upload.")
    
    # Bottone upload
    if st.button("🚀 Upload su Neuronpedia", disabled=not (api_key and graph_json_available)):
        if not api_key:
            st.error("❌ Inserisci la tua API Key!")
        elif not graph_json_available:
            st.error("❌ Carica il Graph JSON prima di procedere!")
        else:
            try:
                # Salva Graph JSON temporaneamente
                graph_to_use = st.session_state.get('graph_json_uploaded')
                
                if isinstance(graph_to_use, Path):
                    graph_path = str(graph_to_use)
                else:
                    # Se è un file caricato, salva temporaneamente
                    graph_path = "temp_graph_upload.json"
                    graph_json_content = json.loads(graph_to_use.read().decode('utf-8'))
                    with open(graph_path, 'w', encoding='utf-8') as f:
                        json.dump(graph_json_content, f)
                
                # Import funzione upload
                import sys
                import importlib.util
                spec = importlib.util.spec_from_file_location("node_grouping", "scripts/02_node_grouping.py")
                node_grouping = importlib.util.module_from_spec(spec)
                sys.modules["node_grouping"] = node_grouping
                spec.loader.exec_module(node_grouping)
                upload_subgraph_to_neuronpedia = node_grouping.upload_subgraph_to_neuronpedia
                
                # Upload
                with st.spinner("Uploading su Neuronpedia..."):
                    result = upload_subgraph_to_neuronpedia(
                        df_grouped=df_named,
                        graph_json_path=graph_path,
                        api_key=api_key,
                        display_name=display_name if display_name else None,
                        overwrite_id=overwrite_id if overwrite_id else None,
                        verbose=False
                    )
                
                # Rimuovi file temporaneo
                if Path(graph_path).name == "temp_graph_upload.json" and Path(graph_path).exists():
                    Path(graph_path).unlink()
                
                st.success("✅ Upload completato!")
                st.json(result)
                
                # Link al subgrafo (se disponibile nella response)
                if 'url' in result:
                    st.markdown(f"🔗 [Visualizza su Neuronpedia]({result['url']})")
                
            except Exception as e:
                st.error(f"❌ Errore upload: {e}")
                import traceback
                st.code(traceback.format_exc())

# ===== FOOTER =====

st.divider()

st.markdown("""
### 📚 Riferimenti

- **Script**: `scripts/02_node_grouping.py`
- **Documentazione**: `output/STEP3_READY_FOR_REVIEW.md`
- **Test**: `tests/test_node_naming.py`

### 💡 Suggerimenti

- **Relationship**: Fornisci sempre il JSON attivazioni per naming accurato
- **Soglie**: Inizia con i valori di default, poi affina in base ai risultati
- **Review**: Controlla manualmente le feature con `review=True`
- **Iterazione**: Puoi rieseguire Step 2 e 3 con soglie diverse senza rifare Step 1
""")

