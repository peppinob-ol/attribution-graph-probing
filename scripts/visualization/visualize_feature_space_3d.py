#!/usr/bin/env python3
"""
Visualizzazione 3D dello spazio Feature Typology
(mean_consistency, max_affinity, logit_influence)
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

def create_3d_visualization():
    """Crea visualizzazione 3D dello spazio feature typology"""
    
    print("=" * 60)
    print("VISUALIZZAZIONE 3D FEATURE TYPOLOGY SPACE")
    print("=" * 60)
    
    # Carica dati
    print("\n📊 Caricamento dati...")
    try:
        with open("output/feature_typology.json", 'r', encoding='utf-8') as f:
            typology = json.load(f)
        print(f"   ✅ Caricati {len(typology)} feature")
    except FileNotFoundError:
        print("   ❌ File feature_typology.json non trovato!")
        print("   Esegui prima: python anthropological_basic.py")
        return
    
    # Estrai coordinate e tipi
    coords = np.array([v['coordinates'] for v in typology.values()])
    types = [v['type'] for v in typology.values()]
    
    # Statistiche per tipo
    type_counts = {}
    for t in types:
        type_counts[t] = type_counts.get(t, 0) + 1
    
    print("\n📈 Distribuzione per tipo:")
    for t, count in sorted(type_counts.items()):
        pct = count / len(types) * 100
        print(f"   {t.capitalize()}: {count} ({pct:.1f}%)")
    
    # Colori per tipo
    color_map = {
        'generalist': '#1f77b4',    # blu
        'specialist': '#ff7f0e',    # arancione
        'computational': '#2ca02c', # verde
        'hybrid': '#d62728'          # rosso
    }
    colors = [color_map.get(t, '#888888') for t in types]
    
    # Crea plot 3D
    print("\n🎨 Creazione visualizzazione 3D...")
    fig = plt.figure(figsize=(14, 10))
    ax = fig.add_subplot(111, projection='3d')
    
    # Scatter plot principale
    scatter = ax.scatter(coords[:, 0], coords[:, 1], coords[:, 2],
                        c=colors, alpha=0.6, s=20, edgecolors='w', linewidth=0.5)
    
    # Labels e titolo
    ax.set_xlabel('Mean Consistency\n(Generalizability)', fontsize=11, labelpad=10)
    ax.set_ylabel('Max Affinity\n(Specialization)', fontsize=11, labelpad=10)
    ax.set_zlabel('Logit Influence\n(Causal Importance)', fontsize=11, labelpad=10)
    ax.set_title('Feature Typology Space\n3D Behavioral Coordinates', 
                 fontsize=14, fontweight='bold', pad=20)
    
    # Griglia
    ax.grid(True, alpha=0.3)
    
    # Legenda
    from matplotlib.patches import Patch
    legend_elements = []
    for t in sorted(color_map.keys()):
        if t in type_counts:
            count = type_counts[t]
            pct = count / len(types) * 100
            label = f"{t.capitalize()} ({count}, {pct:.1f}%)"
            legend_elements.append(Patch(facecolor=color_map[t], label=label))
    
    ax.legend(handles=legend_elements, loc='upper left', 
             frameon=True, framealpha=0.9, fontsize=10)
    
    # Imposta limiti degli assi
    ax.set_xlim([0, 1])
    ax.set_ylim([0, 1])
    # zlim dipende dai dati (logit_influence può essere >1)
    
    # Angolo di visualizzazione ottimale
    ax.view_init(elev=20, azim=45)
    
    plt.tight_layout()
    
    # Salva
    output_path = 'output/feature_typology_3d.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"   ✅ Salvata: {output_path}")
    
    # Salva anche versione interattiva (opzionale)
    try:
        output_path_svg = 'output/feature_typology_3d.svg'
        plt.savefig(output_path_svg, format='svg', bbox_inches='tight')
        print(f"   ✅ Salvata versione SVG: {output_path_svg}")
    except:
        pass
    
    # Analisi addizionale: centroidi per tipo
    print("\n📍 Centroidi per tipo (mean coordinates):")
    for t in sorted(color_map.keys()):
        if t in type_counts:
            type_coords = coords[[i for i, typ in enumerate(types) if typ == t]]
            if len(type_coords) > 0:
                centroid = type_coords.mean(axis=0)
                print(f"   {t.capitalize()}:")
                print(f"      Mean Consistency: {centroid[0]:.3f}")
                print(f"      Max Affinity: {centroid[1]:.3f}")
                print(f"      Logit Influence: {centroid[2]:.3f}")
    
    print("\n✅ Visualizzazione 3D completata!")
    
    return fig

def create_2d_projections():
    """Crea proiezioni 2D degli assi principali"""
    
    print("\n📊 Creazione proiezioni 2D...")
    
    with open("output/feature_typology.json", 'r', encoding='utf-8') as f:
        typology = json.load(f)
    
    coords = np.array([v['coordinates'] for v in typology.values()])
    types = [v['type'] for v in typology.values()]
    
    color_map = {
        'generalist': '#1f77b4',
        'specialist': '#ff7f0e',
        'computational': '#2ca02c',
        'hybrid': '#d62728'
    }
    colors = [color_map.get(t, '#888888') for t in types]
    
    # Crea figura con 3 subplots
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    
    # Plot 1: Mean Consistency vs Max Affinity
    axes[0].scatter(coords[:, 0], coords[:, 1], c=colors, alpha=0.6, s=30, edgecolors='w', linewidth=0.5)
    axes[0].set_xlabel('Mean Consistency (Generalizability)', fontsize=10)
    axes[0].set_ylabel('Max Affinity (Specialization)', fontsize=10)
    axes[0].set_title('Consistency vs Affinity', fontsize=11, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].set_xlim([0, 1])
    axes[0].set_ylim([0, 1])
    
    # Plot 2: Mean Consistency vs Logit Influence
    axes[1].scatter(coords[:, 0], coords[:, 2], c=colors, alpha=0.6, s=30, edgecolors='w', linewidth=0.5)
    axes[1].set_xlabel('Mean Consistency (Generalizability)', fontsize=10)
    axes[1].set_ylabel('Logit Influence (Causal Importance)', fontsize=10)
    axes[1].set_title('Consistency vs Influence', fontsize=11, fontweight='bold')
    axes[1].grid(True, alpha=0.3)
    axes[1].set_xlim([0, 1])
    
    # Plot 3: Max Affinity vs Logit Influence
    axes[2].scatter(coords[:, 1], coords[:, 2], c=colors, alpha=0.6, s=30, edgecolors='w', linewidth=0.5)
    axes[2].set_xlabel('Max Affinity (Specialization)', fontsize=10)
    axes[2].set_ylabel('Logit Influence (Causal Importance)', fontsize=10)
    axes[2].set_title('Affinity vs Influence', fontsize=11, fontweight='bold')
    axes[2].grid(True, alpha=0.3)
    axes[2].set_xlim([0, 1])
    
    # Legenda comune
    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor=color_map[t], label=t.capitalize()) 
                      for t in sorted(color_map.keys())]
    fig.legend(handles=legend_elements, loc='upper center', ncol=4, 
              frameon=True, framealpha=0.9, fontsize=10, bbox_to_anchor=(0.5, 0.98))
    
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    
    output_path = 'output/feature_typology_2d_projections.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"   ✅ Salvata: {output_path}")
    
    return fig

if __name__ == "__main__":
    print("🎨 Avvio visualizzazione Feature Typology Space...")
    
    try:
        # Visualizzazione 3D
        fig_3d = create_3d_visualization()
        
        # Proiezioni 2D
        fig_2d = create_2d_projections()
        
        print("\n🏆 COMPLETATO!")
        print("   Visualizzazioni salvate in output/")
        
    except Exception as e:
        print(f"\n❌ Errore: {e}")
        import traceback
        traceback.print_exc()

