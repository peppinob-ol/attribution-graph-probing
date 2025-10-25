"""Pannello dettaglio singola feature"""
import streamlit as st
import pandas as pd
from typing import Dict, Optional
from eda.utils.plots import create_feature_neighborhood_graph


def render_feature_detail(feature_key: str, personalities: Dict, 
                          acts_data: Optional[pd.DataFrame] = None,
                          graph_available: bool = False):
    """Renderizza pannello dettaglio feature"""
    
    if feature_key not in personalities:
        st.error(f"Feature {feature_key} non trovata")
        return
    
    p = personalities[feature_key]
    
    st.subheader(f"Feature: {feature_key}")
    
    # Metriche principali in colonne
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Layer", p.get('layer', '?'), 
                 help="Transformer layer (0-25 for Gemma-2B)")
        st.metric("Position", p.get('position', '?'),
                 help="Token position in sequence where feature activates")
    
    with col2:
        st.metric("Mean Consistency", f"{p.get('mean_consistency', 0):.3f}",
                 help="Average cosine similarity between feature activation and label embedding across prompts. "
                      "Range [0,1]. Higher = more consistent semantic alignment.")
        st.metric("Max Affinity", f"{p.get('max_affinity', 0):.3f}",
                 help="Peak cosine similarity with label embedding. "
                      "Range [0,1]. Measures strongest semantic alignment observed.")
    
    with col3:
        st.metric("Conditional Cons.", f"{p.get('conditional_consistency', 0):.3f}",
                 help="Consistency computed only when feature is active (above adaptive threshold). "
                      "More robust than mean_consistency for sparse features.")
        st.metric("Node Influence", f"{p.get('node_influence', 0):.4f}",
                 help="Causal influence on target logits via backward propagation through attribution graph. "
                      "Can be negative. Higher absolute value = stronger causal impact.")
    
    with col4:
        st.metric("Output Impact", f"{p.get('output_impact', 0):.4f}",
                 help="Direct influence on output logits (logit_influence). "
                      "Computed from attribution graph edges to final logits. Range typically [0, 0.1].")
        st.metric("Peak Token", p.get('most_common_peak', '?'),
                 help="Token where this feature activates most frequently across all prompts")
    
    # Tabs per diverse viste
    tab1, tab2, tab3, tab4 = st.tabs(["Personalità", "Vicinato Causale", "Attivazioni", "Metadati"])
    
    with tab1:
        st.write("**Personalità completa:**")
        
        # Organizza per categorie
        st.write("*Semantica:*")
        st.json({
            'mean_consistency': p.get('mean_consistency', 0),
            'max_affinity': p.get('max_affinity', 0),
            'conditional_consistency': p.get('conditional_consistency', 0),
            'consistency_std': p.get('consistency_std', 0),
            'label_affinity': p.get('label_affinity', 0),
        })
        
        st.write("*Causale:*")
        st.json({
            'node_influence': p.get('node_influence', 0),
            'causal_in_degree': p.get('causal_in_degree', 0),
            'causal_out_degree': p.get('causal_out_degree', 0),
            'position_at_final': p.get('position_at_final', False),
        })
        
        st.write("*Contesto:*")
        st.json({
            'layer': p.get('layer', 0),
            'position': p.get('position', 0),
            'most_common_peak': p.get('most_common_peak', '?'),
            'activation_threshold': p.get('activation_threshold', 0),
            'n_observations': p.get('n_observations', 0),
        })
    
    with tab2:
        if not graph_available:
            st.warning("Grafo causale non disponibile")
        else:
            st.write("**Top 5 genitori causali:**")
            if 'top_parents' in p and p['top_parents']:
                parents_df = pd.DataFrame(p['top_parents'], columns=['feature_key', 'weight'])
                st.dataframe(parents_df, use_container_width=True)
            else:
                st.info("Nessun genitore causale")
            
            st.write("**Top 5 figli causali:**")
            if 'top_children' in p and p['top_children']:
                children_df = pd.DataFrame(p['top_children'], columns=['feature_key', 'weight'])
                st.dataframe(children_df, use_container_width=True)
            else:
                st.info("Nessun figlio causale")
            
            # Grafico vicinato
            st.write("**Grafico vicinato:**")
            fig = create_feature_neighborhood_graph(feature_key, personalities, max_neighbors=5)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        if acts_data is not None:
            # Filtra attivazioni per questa feature
            layer, feat_id = feature_key.split('_')
            feature_acts = acts_data[
                (acts_data['layer'] == int(layer)) &
                (acts_data['feature'] == int(feat_id))
            ]
            
            if len(feature_acts) > 0:
                st.write(f"**Attivazioni ({len(feature_acts)} record):**")
                
                # Mostra per prompt
                prompts = feature_acts['prompt'].unique()
                st.write(f"Attiva su {len(prompts)} prompt diversi")
                
                # Statistiche
                st.write("*Statistiche cosine similarity:*")
                cosine_vals = feature_acts['cosine_similarity'].dropna()
                if len(cosine_vals) > 0:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Mean", f"{cosine_vals.mean():.3f}")
                    with col2:
                        st.metric("Max", f"{cosine_vals.max():.3f}")
                    with col3:
                        st.metric("Std", f"{cosine_vals.std():.3f}")
                
                # Tabella sample
                st.write("*Sample attivazioni:*")
                display_cols = ['prompt', 'cosine_similarity', 'peak_token', 
                               'nuova_somma_sequenza', 'picco_su_label']
                available_cols = [c for c in display_cols if c in feature_acts.columns]
                st.dataframe(feature_acts[available_cols].head(10), use_container_width=True)
            else:
                st.info("Nessuna attivazione trovata nei dati")
        else:
            st.warning("Dati attivazioni non disponibili")
    
    with tab4:
        st.write("**Tutti i metadati:**")
        st.json(p)

