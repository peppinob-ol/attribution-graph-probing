"""Pannello dettaglio singolo supernodo con dry-run opzionale"""
import streamlit as st
import pandas as pd
from typing import Dict, Optional
from eda.utils.plots import plot_coherence_history, plot_member_distribution
from eda.utils.compute import compute_compatibility, compute_coherence


def render_supernode_detail(
    supernode_id: str,
    supernodes: Dict,
    personalities: Dict,
    graph_data: Optional[Dict] = None,
    enable_dryrun: bool = False,
    dryrun_params: Dict = None
):
    """Renderizza pannello dettaglio supernodo"""
    
    if supernode_id not in supernodes:
        st.error(f"Supernodo {supernode_id} non trovato")
        return
    
    sn = supernodes[supernode_id]
    
    st.subheader(f"Supernodo: {supernode_id}")
    
    # Metriche principali
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("N membri", len(sn.get('members', [])),
                 help="Number of features in this supernode")
        st.metric("Seed layer", sn.get('seed_layer', '?'),
                 help="Layer of the seed feature that initiated supernode growth")
    
    with col2:
        st.metric("Final coherence", f"{sn.get('final_coherence', 0):.3f}",
                 help="Final coherence score after growth completed. "
                      "Coherence = 0.30×consistency_homogeneity + 0.20×token_diversity + "
                      "0.20×layer_span + 0.30×causal_edge_density. Range [0,1].")
        st.metric("Growth iterations", sn.get('growth_iterations', 0),
                 help="Number of iterations (members added) during growth phase")
    
    with col3:
        st.metric("Narrative theme", sn.get('narrative_theme', '?'),
                 help="Semantic theme inferred from dominant tokens and context")
        st.metric("Seed logit inf.", f"{sn.get('seed_logit_influence', 0):.4f}",
                 help="Logit influence (output_impact) of the seed feature. "
                      "Higher = seed has stronger direct impact on target logits.")
    
    with col4:
        st.metric("Total influence", f"{sn.get('total_influence_score', 0):.2f}",
                 help="Sum of node_influence scores across all members. "
                      "Measures aggregate causal impact of the supernode.")
        # Stima edge density se grafo disponibile
        if graph_data:
            try:
                from scripts.causal_utils import compute_edge_density
                edge_dens = compute_edge_density(
                    sn['members'],
                    graph_data,
                    graph_data.get('feature_to_idx', {}),
                    tau_edge=0.01
                )
                st.metric("Edge density", f"{edge_dens:.3f}",
                         help="Density of causal edges within supernode. "
                              "Ratio of actual edges (weight > 0.01) to possible edges. Range [0,1].")
            except:
                st.metric("Edge density", "N/A")
        else:
            st.metric("Edge density", "N/A",
                     help="Causal graph not available. Cannot compute edge density.")
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Membri", "Crescita", "Dry-run"])
    
    with tab1:
        st.write("**Coherence history:**")
        if 'coherence_history' in sn:
            fig = plot_coherence_history(sn['coherence_history'], 
                                         title=f"Crescita {supernode_id}")
            st.plotly_chart(fig, use_container_width=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Distribuzione layer:**")
            fig_layer = plot_member_distribution(sn['members'], personalities, 
                                                 attr='layer', 
                                                 title='Layer membri')
            st.plotly_chart(fig_layer, use_container_width=True)
        
        with col2:
            st.write("**Token distribution:**")
            tokens = []
            for m in sn['members']:
                if m in personalities:
                    tokens.append(personalities[m].get('most_common_peak', '?'))
            token_counts = pd.Series(tokens).value_counts()
            st.bar_chart(token_counts)
    
    with tab2:
        st.write(f"**Membri ({len(sn.get('members', []))}):**")
        
        # Crea tabella membri con dettagli
        members_data = []
        for m in sn['members']:
            if m in personalities:
                p = personalities[m]
                members_data.append({
                    'feature': m,
                    'layer': p.get('layer', 0),
                    'token': p.get('most_common_peak', '?'),
                    'mean_cons': p.get('mean_consistency', 0),
                    'max_aff': p.get('max_affinity', 0),
                    'node_inf': p.get('node_influence', 0),
                })
        
        if members_data:
            members_df = pd.DataFrame(members_data)
            st.dataframe(members_df, use_container_width=True, height=400)
            
            # Export membri
            csv = members_df.to_csv(index=False)
            st.download_button(
                label="Download membri CSV",
                data=csv,
                file_name=f"{supernode_id}_members.csv",
                mime='text/csv'
            )
    
    with tab3:
        st.write("**Storia della crescita:**")
        
        if 'coherence_history' in sn:
            history_df = pd.DataFrame({
                'iteration': range(len(sn['coherence_history'])),
                'coherence': sn['coherence_history'],
                'n_members': range(1, len(sn['coherence_history']) + 1)
            })
            
            st.line_chart(history_df.set_index('iteration'))
            
            st.write("*Dettagli iterazioni:*")
            st.dataframe(history_df, use_container_width=True)
        
        st.write("**Seed:**")
        seed_key = sn.get('seed', '?')
        if seed_key in personalities:
            seed_p = personalities[seed_key]
            st.json({
                'feature_key': seed_key,
                'layer': seed_p.get('layer', 0),
                'token': seed_p.get('most_common_peak', '?'),
                'node_influence': seed_p.get('node_influence', 0),
                'mean_consistency': seed_p.get('mean_consistency', 0),
            })
    
    with tab4:
        if not enable_dryrun:
            st.info("Dry-run non abilitato. Vai in Fase 2 per configurare parametri.")
            return
        
        st.write("**Dry-run crescita con parametri correnti**")
        st.warning("⚠️ Funzionalità semplificata: confronto parametrico, non crescita completa")
        
        if dryrun_params and graph_data:
            st.write("*Parametri correnti:*")
            st.json(dryrun_params)
            
            # Simula compatibilità per primi N candidati potenziali
            seed_key = sn.get('seed')
            if seed_key and seed_key in personalities:
                seed_p = personalities[seed_key]
                
                st.write(f"**Seed: {seed_key}**")
                
                # Prendi top_parents come candidati esempio
                if 'top_parents' in seed_p and seed_p['top_parents']:
                    st.write("*Compatibilità candidati (top parents):*")
                    
                    candidates_compat = []
                    for cand_key, edge_w in seed_p['top_parents'][:5]:
                        if cand_key in personalities:
                            cand_p = personalities[cand_key]
                            
                            # Calcola compatibilità con parametri correnti
                            compat, breakdown = compute_compatibility(
                                seed_p, cand_p,
                                causal_weight=dryrun_params.get('causal_weight', 0.6),
                                adjacency_matrix=graph_data.get('adjacency_matrix') if graph_data else None,
                                feature_to_idx=graph_data.get('feature_to_idx') if graph_data else None,
                                tau_edge_strong=dryrun_params.get('tau_edge_strong', 0.05)
                            )
                            
                            candidates_compat.append({
                                'candidate': cand_key,
                                'edge_weight': edge_w,
                                'total_compat': compat,
                                'causal_score': breakdown.get('causal_score', 0),
                                'semantic_score': breakdown.get('semantic_score', 0),
                                'token': cand_p.get('most_common_peak', '?'),
                            })
                    
                    if candidates_compat:
                        compat_df = pd.DataFrame(candidates_compat)
                        st.dataframe(compat_df, use_container_width=True)
                        
                        # Confronto con threshold
                        threshold = dryrun_params.get('threshold_normal', 0.45)
                        st.write(f"*Threshold accettazione: {threshold:.2f}*")
                        accepted = compat_df[compat_df['total_compat'] > threshold]
                        st.write(f"Candidati accettati: {len(accepted)}/{len(compat_df)}")
                else:
                    st.info("Seed non ha top_parents disponibili")
        else:
            st.info("Grafo causale non disponibile per dry-run")

