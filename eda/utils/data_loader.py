"""Data loader con cache per tutti i file output"""
import json
import pandas as pd
import streamlit as st
from pathlib import Path
from typing import Optional, Dict, Any
import sys

# Aggiungi scripts al path per importare causal_utils
sys.path.insert(0, 'scripts')

from eda.config.defaults import OUTPUT_PATHS


@st.cache_data
def load_personalities() -> Optional[Dict]:
    """Carica feature personalities"""
    try:
        with open(OUTPUT_PATHS['personalities'], 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.warning(f"File {OUTPUT_PATHS['personalities']} non trovato")
        return None


@st.cache_data
def load_archetypes() -> Optional[Dict]:
    """Carica archetipi narrativi"""
    try:
        with open(OUTPUT_PATHS['archetypes'], 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.warning(f"File {OUTPUT_PATHS['archetypes']} non trovato")
        return None


@st.cache_data
def load_cicciotti() -> Optional[Dict]:
    """Carica supernodi cicciotti"""
    try:
        with open(OUTPUT_PATHS['cicciotti'], 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.warning(f"File {OUTPUT_PATHS['cicciotti']} non trovato")
        return None


@st.cache_data
def load_validation() -> Optional[Dict]:
    """Carica validazione cross-prompt"""
    try:
        with open(OUTPUT_PATHS['validation'], 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.warning(f"File {OUTPUT_PATHS['validation']} non trovato")
        return None


@st.cache_data
def load_final() -> Optional[Dict]:
    """Carica risultati finali completi"""
    try:
        with open(OUTPUT_PATHS['final'], 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.warning(f"File {OUTPUT_PATHS['final']} non trovato")
        return None


@st.cache_data
def load_thresholds() -> Optional[Dict]:
    """Carica soglie robuste"""
    try:
        with open(OUTPUT_PATHS['thresholds'], 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.warning(f"File {OUTPUT_PATHS['thresholds']} non trovato")
        return None


@st.cache_data
def load_static_metrics() -> Optional[pd.DataFrame]:
    """Carica metriche statiche feature"""
    try:
        df = pd.read_csv(OUTPUT_PATHS['static_metrics'])
        df['feature_key'] = df['layer'].astype(str) + '_' + df['feature'].astype(str)
        return df
    except FileNotFoundError:
        st.warning(f"File {OUTPUT_PATHS['static_metrics']} non trovato")
        return None


@st.cache_data
def load_acts() -> Optional[pd.DataFrame]:
    """Carica attivazioni"""
    try:
        return pd.read_csv(OUTPUT_PATHS['acts'], encoding='utf-8')
    except FileNotFoundError:
        st.warning(f"File {OUTPUT_PATHS['acts']} non trovato")
        return None


@st.cache_data
def load_labels() -> Optional[Dict]:
    """Carica label supernodi (opzionale)"""
    try:
        with open(OUTPUT_PATHS['labels'], 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return None


@st.cache_resource
def load_graph() -> Optional[Dict]:
    """Carica attribution graph (opzionale, pesante)"""
    try:
        import torch
        graph_data = torch.load(OUTPUT_PATHS['graph'], map_location='cpu', weights_only=False)
        
        # Crea feature_to_idx mapping
        feature_to_idx = {}
        for i, (layer, pos, feat_idx) in enumerate(graph_data['active_features']):
            feature_key = f"{layer.item()}_{feat_idx.item()}"
            feature_to_idx[feature_key] = i
        
        graph_data['feature_to_idx'] = feature_to_idx
        return graph_data
    except FileNotFoundError:
        return None
    except Exception as e:
        st.warning(f"Errore caricamento grafo: {e}")
        return None


def load_all_data() -> Dict[str, Any]:
    """Carica tutti i dati disponibili"""
    return {
        'personalities': load_personalities(),
        'archetypes': load_archetypes(),
        'cicciotti': load_cicciotti(),
        'validation': load_validation(),
        'final': load_final(),
        'thresholds': load_thresholds(),
        'static_metrics': load_static_metrics(),
        'acts': load_acts(),
        'labels': load_labels(),
        'graph': load_graph(),
    }


def check_data_availability() -> Dict[str, bool]:
    """Verifica quali dati sono disponibili"""
    return {
        'personalities': Path(OUTPUT_PATHS['personalities']).exists(),
        'archetypes': Path(OUTPUT_PATHS['archetypes']).exists(),
        'cicciotti': Path(OUTPUT_PATHS['cicciotti']).exists(),
        'validation': Path(OUTPUT_PATHS['validation']).exists(),
        'final': Path(OUTPUT_PATHS['final']).exists(),
        'thresholds': Path(OUTPUT_PATHS['thresholds']).exists(),
        'static_metrics': Path(OUTPUT_PATHS['static_metrics']).exists(),
        'acts': Path(OUTPUT_PATHS['acts']).exists(),
        'graph': Path(OUTPUT_PATHS['graph']).exists(),
        'labels': Path(OUTPUT_PATHS['labels']).exists(),
    }

