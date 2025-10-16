#!/usr/bin/env python3
"""
Visualizzazione Attribution Graph con layout Layer × Token Position
Layout corretto: X=token_position, Y=layer, con embeddings e logit nodes
"""

import torch
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch
import numpy as np
from pathlib import Path
import json
import sys
sys.path.insert(0, 'scripts')


def visualize_attribution_graph_layered(
    graph_path: str = "output/example_graph.pt",
    supernodes_path: str = "output/cicciotti_supernodes.json",
    output_path: str = "output/attribution_graph_layered.svg",
    tau_edge: float = 0.01,
    max_edges: int = 100
):
    """
    Visualizza Attribution Graph con layout corretto layer × token
    
    Args:
        graph_path: percorso al grafo .pt
        supernodes_path: percorso ai supernodi (opzionale, per colorare)
        output_path: percorso output SVG
        tau_edge: soglia minima per visualizzare edge
        max_edges: massimo numero di edge da visualizzare
    """
    print(f"📊 Visualizzazione Attribution Graph Layered")
    print(f"=" * 60)
    
    # Carica grafo
    from causal_utils import load_attribution_graph
    graph_data = load_attribution_graph(graph_path)
    
    if graph_data is None:
        print(f"❌ Impossibile caricare grafo")
        return
    
    adjacency_matrix = graph_data['adjacency_matrix']
    active_features = graph_data['active_features']
    input_tokens = graph_data['input_tokens']
    logit_tokens = graph_data['logit_tokens']
    cfg = graph_data['cfg']
    
    n_features = len(active_features)
    n_pos = len(input_tokens)
    n_layers = cfg.n_layers
    n_logits = len(logit_tokens)
    
    print(f"   Nodi: {n_features} features")
    print(f"   Tokens: {n_pos} positions")
    print(f"   Layers: {n_layers}")
    print(f"   Logits: {n_logits}")
    
    # Crea mapping feature_key → info
    feature_info = {}
    for i, (layer, pos, feat_idx) in enumerate(active_features):
        feature_key = f"{layer.item()}_{feat_idx.item()}"
        feature_info[feature_key] = {
            'layer': layer.item(),
            'pos': pos.item(),
            'feat_idx': feat_idx.item(),
            'node_idx': i
        }
    
    # Carica supernodi per colorare (opzionale)
    supernode_membership = {}
    if Path(supernodes_path).exists():
        try:
            with open(supernodes_path, 'r') as f:
                supernodes = json.load(f)
            
            for sn_id, sn_data in supernodes.items():
                for member in sn_data.get('members', []):
                    supernode_membership[member] = sn_id
            
            print(f"   Supernodi caricati: {len(supernodes)}")
        except:
            pass
    
    # Prepara figure
    fig, ax = plt.subplots(figsize=(16, 10))
    
    # Scala spaziale
    x_scale = 100  # pixel per token position
    y_scale = 40   # pixel per layer
    
    # ========== Disegna nodi feature ==========
    node_positions = {}
    colors = plt.cm.tab20(np.linspace(0, 1, 20))
    
    for fkey, info in feature_info.items():
        x = info['pos'] * x_scale
        y = info['layer'] * y_scale
        
        # Colore basato su supernode membership
        if fkey in supernode_membership:
            sn_id = supernode_membership[fkey]
            color_idx = hash(sn_id) % len(colors)
            color = colors[color_idx]
            alpha = 0.8
        else:
            color = 'lightgray'
            alpha = 0.4
        
        # Disegna nodo
        circle = plt.Circle((x, y), radius=5, color=color, alpha=alpha, zorder=10)
        ax.add_patch(circle)
        
        node_positions[info['node_idx']] = (x, y)
    
    # ========== Disegna embedding nodes ==========
    for pos_idx in range(n_pos):
        x = pos_idx * x_scale
        y = -y_scale  # Sotto layer 0
        
        rect = plt.Rectangle((x-10, y-5), 20, 10, color='green', alpha=0.6, zorder=10)
        ax.add_patch(rect)
        
        # Label token (se disponibile)
        if pos_idx < len(input_tokens):
            token_id = input_tokens[pos_idx]
            # Semplificato: mostra solo indice
            ax.text(x, y, f"T{pos_idx}", ha='center', va='center', fontsize=6, zorder=11)
    
    # ========== Disegna logit nodes ==========
    logit_y = (n_layers + 1) * y_scale
    for logit_idx in range(min(n_logits, 5)):  # Max 5 logit nodes
        x = (n_pos - 1) * x_scale + (logit_idx - 2) * 30  # Vicino alla posizione finale
        y = logit_y
        
        rect = plt.Rectangle((x-15, y-8), 30, 16, color='red', alpha=0.7, zorder=10)
        ax.add_patch(rect)
        
        # Label logit
        ax.text(x, y, f"L{logit_idx}", ha='center', va='center', fontsize=7, 
                color='white', weight='bold', zorder=11)
    
    # ========== Disegna edge (solo le più forti) ==========
    print(f"   Calcolo edge forti...")
    
    # Estrai edge tra feature nodes (ignora error/embed/logit per semplicità)
    feature_adj = adjacency_matrix[:n_features, :n_features]
    
    # Trova top edge
    edge_weights = []
    for i in range(n_features):
        for j in range(n_features):
            weight = feature_adj[i, j].item()
            if weight > tau_edge and i != j:  # Escludi self-loops
                edge_weights.append((i, j, weight))
    
    # Ordina e prendi top-N
    edge_weights.sort(key=lambda x: x[2], reverse=True)
    edge_weights = edge_weights[:max_edges]
    
    print(f"   Visualizzando {len(edge_weights)} edge")
    
    # Disegna edge
    for source_idx, target_idx, weight in edge_weights:
        if source_idx not in node_positions or target_idx not in node_positions:
            continue
        
        x1, y1 = node_positions[source_idx]
        x2, y2 = node_positions[target_idx]
        
        # Spessore e colore proporzionali al peso
        linewidth = min(3.0, weight * 50)
        alpha = min(0.8, weight * 10)
        
        # Colore: gradient da blu (debole) a rosso (forte)
        norm_weight = min(1.0, weight / 0.1)
        color = plt.cm.coolwarm(norm_weight)
        
        # Freccia
        arrow = FancyArrowPatch(
            (x1, y1), (x2, y2),
            arrowstyle='->', 
            color=color,
            linewidth=linewidth,
            alpha=alpha,
            zorder=5,
            mutation_scale=15
        )
        ax.add_patch(arrow)
    
    # ========== Layout e labels ==========
    ax.set_xlim(-50, n_pos * x_scale + 50)
    ax.set_ylim(-y_scale * 2, (n_layers + 2) * y_scale)
    
    ax.set_xlabel("Token Position", fontsize=12, weight='bold')
    ax.set_ylabel("Layer", fontsize=12, weight='bold')
    ax.set_title(f"Attribution Graph: Layer × Token Layout\n{n_features} features, {len(edge_weights)} strong edges",
                 fontsize=14, weight='bold')
    
    # Grid per posizioni
    ax.set_xticks([i * x_scale for i in range(n_pos)])
    ax.set_xticklabels([f"P{i}" for i in range(n_pos)])
    
    ax.set_yticks([i * y_scale for i in range(-1, n_layers + 2)])
    ax.set_yticklabels(['Embed'] + [f"L{i}" for i in range(n_layers)] + ['Logit'])
    
    ax.grid(True, alpha=0.2, linestyle='--')
    ax.set_aspect('equal', adjustable='box')
    
    # Legend
    legend_elements = [
        mpatches.Patch(color='green', alpha=0.6, label='Embedding Nodes'),
        mpatches.Patch(color='red', alpha=0.7, label='Logit Nodes'),
        mpatches.Patch(color='lightgray', alpha=0.4, label='Feature (no supernode)'),
        mpatches.Patch(color=colors[0], alpha=0.8, label='Feature (in supernode)')
    ]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=9)
    
    # Salva
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n✅ Grafo salvato: {output_path}")
    
    plt.close()


if __name__ == "__main__":
    visualize_attribution_graph_layered(
        graph_path="output/example_graph.pt",
        supernodes_path="output/cicciotti_supernodes.json",
        output_path="output/attribution_graph_layered.svg",
        tau_edge=0.01,
        max_edges=150
    )
    
    print(f"\n🎉 Visualizzazione completata!")

