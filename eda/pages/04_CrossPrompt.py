"""Validazione Cross-Prompt"""
import streamlit as st
import pandas as pd
import plotly.express as px
from eda.utils.data_loader import load_validation, load_cicciotti
from eda.utils.plots import plot_heatmap_prompt_activation

st.set_page_config(page_title="Cross-Prompt", page_icon="🧪", layout="wide")

st.title("🧪 Validazione Cross-Prompt")
st.write("Robustezza supernodi su prompt diversi")

# Carica dati
validation = load_validation()
cicciotti = load_cicciotti()

if validation is None:
    st.error("Dati validazione non disponibili")
    st.stop()

if cicciotti is None:
    st.warning("Supernodi non disponibili per riferimenti")

st.write(f"**Supernodi validati:** {len(validation)}")

# Estrai prompts unici
all_prompts = set()
for sn_id, prompt_data in validation.items():
    all_prompts.update(prompt_data.keys())

st.write(f"**Prompts unici:** {len(all_prompts)}")

# Tabs
tab1, tab2, tab3 = st.tabs(["Heatmap", "Statistiche", "Dettaglio Supernodo"])

with tab1:
    st.header("Heatmap Attivazione")
    
    metric_choice = st.selectbox(
        "Metrica",
        ['n_active_members', 'avg_consistency', 'consistency_std']
    )
    
    fig_heat = plot_heatmap_prompt_activation(validation, metric=metric_choice)
    st.plotly_chart(fig_heat, use_container_width=True)

with tab2:
    st.header("Statistiche Robustezza")
    
    # Calcola statistiche per supernodo
    robustness_data = []
    
    for sn_id, prompt_data in validation.items():
        n_actives = [stats.get('n_active_members', 0) for stats in prompt_data.values()]
        avg_conss = [stats.get('avg_consistency', 0) for stats in prompt_data.values() 
                     if stats.get('avg_consistency', 0) > 0]
        
        if n_actives and avg_conss:
            robustness_data.append({
                'supernodo': sn_id,
                'n_prompts': len(prompt_data),
                'avg_active_members': sum(n_actives) / len(n_actives),
                'std_active_members': pd.Series(n_actives).std(),
                'avg_consistency_mean': sum(avg_conss) / len(avg_conss),
                'std_consistency': pd.Series(avg_conss).std(),
                'min_active': min(n_actives),
                'max_active': max(n_actives),
            })
    
    robust_df = pd.DataFrame(robustness_data)
    
    if len(robust_df) > 0:
        # Ordina per stabilità (bassa std)
        robust_df_sorted = robust_df.sort_values('std_active_members', ascending=True)
        
        st.subheader("Top 10 Supernodi Più Stabili")
        st.dataframe(robust_df_sorted.head(10), use_container_width=True)
        
        st.subheader("Top 10 Supernodi Più Variabili")
        st.dataframe(robust_df_sorted.tail(10), use_container_width=True)
        
        # Scatter stabilità
        st.subheader("Stabilità vs Attivazione Media")
        fig_stab = px.scatter(robust_df, x='avg_active_members', y='std_active_members',
                             hover_data=['supernodo'],
                             labels={'avg_active_members': 'Avg active members',
                                    'std_active_members': 'Std active members'},
                             title='Stabilità per supernodo')
        st.plotly_chart(fig_stab, use_container_width=True)
        
        # Export
        st.download_button(
            label="📥 Download robustness stats CSV",
            data=robust_df.to_csv(index=False),
            file_name='robustness_stats.csv',
            mime='text/csv'
        )
    else:
        st.warning("Nessuna statistica calcolabile")

with tab3:
    st.header("Dettaglio Supernodo")
    
    selected_sn = st.selectbox("Seleziona supernodo", sorted(validation.keys()))
    
    if selected_sn:
        prompt_data = validation[selected_sn]
        
        st.write(f"**Supernodo:** {selected_sn}")
        
        if cicciotti and selected_sn in cicciotti:
            sn = cicciotti[selected_sn]
            st.write(f"**Theme:** {sn.get('narrative_theme', '?')}")
            st.write(f"**N membri totali:** {len(sn.get('members', []))}")
        
        st.subheader("Attivazione per Prompt")
        
        # Tabella
        prompt_rows = []
        for prompt_key, stats in prompt_data.items():
            prompt_rows.append({
                'prompt': prompt_key[:50] + '...' if len(prompt_key) > 50 else prompt_key,
                'n_active_members': stats.get('n_active_members', 0),
                'avg_consistency': stats.get('avg_consistency', 0),
                'consistency_std': stats.get('consistency_std', 0),
            })
        
        prompt_df = pd.DataFrame(prompt_rows)
        st.dataframe(prompt_df, use_container_width=True)
        
        # Grafici
        col1, col2 = st.columns(2)
        
        with col1:
            fig1 = px.bar(prompt_df, x='prompt', y='n_active_members',
                         title='N active members per prompt')
            fig1.update_xaxes(tickangle=45)
            st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            fig2 = px.bar(prompt_df, x='prompt', y='avg_consistency',
                         title='Avg consistency per prompt')
            fig2.update_xaxes(tickangle=45)
            st.plotly_chart(fig2, use_container_width=True)
        
        # Summary
        st.subheader("Summary")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            avg_act = prompt_df['n_active_members'].mean()
            st.metric("Avg active members", f"{avg_act:.1f}")
        
        with col2:
            std_act = prompt_df['n_active_members'].std()
            st.metric("Std active members", f"{std_act:.2f}")
        
        with col3:
            avg_cons = prompt_df['avg_consistency'].mean()
            st.metric("Avg consistency", f"{avg_cons:.3f}")

