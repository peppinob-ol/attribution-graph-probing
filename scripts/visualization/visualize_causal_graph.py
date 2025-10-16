#!/usr/bin/env python3
"""
Visualizzazione Attribution Graph con layout Layer × Token Position
Carica adjacency_matrix e mostra struttura causale reale
"""

import json
import torch
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch
from collections import defaultdict

class AttributionGraphVisualizer:
    """
    Visualizza attribution graph con layout corretto:
    - Asse X: Token positions
    - Asse Y: Layers (0 in basso, n_layers in alto)
    - Edge: Frecce causali con spessore proporzionale
    """
    
    def __init__(self, graph_path: str = "output/example_graph.pt"):
        """Carica grafo da file .pt"""
        self.graph_path = graph_path
        self.graph = None
        self.adjacency_matrix = None
        self.active_features = None
        self.feature_to_idx = {}
        self.personalities = {}
        
    def load_graph(self):
        """Carica attribution graph da file .pt"""
        if not Path(self.graph_path).exists():
            print(f"⚠️ Grafo non trovato: {self.graph_path}")
            print("📝 Creando grafo mock per dimostrazione...")
            return self._create_mock_graph()
        
        print(f"📥 Caricamento grafo da {self.graph_path}")
        
        # Carica con torch (il formato standard di circuit-tracer)
        graph_data = torch.load(self.graph_path, map_location='cpu')
        
        # Estrai componenti chiave
        self.adjacency_matrix = graph_data['adjacency_matrix']  # Matrice causale!
        self.active_features = graph_data['active_features']  # (n_active, 3): [layer, pos, idx]
        self.input_tokens = graph_data['input_tokens']
        self.logit_tokens = graph_data['logit_tokens']
        self.cfg = graph_data['cfg']
        
        print(f"✅ Grafo caricato:")
        print(f"   - Active features: {len(self.active_features)}")
        print(f"   - Input tokens: {len(self.input_tokens)}")
        print(f"   - Adjacency matrix shape: {self.adjacency_matrix.shape}")
        
        # Crea mapping feature_key → indice
        for i, (layer, pos, feat_idx) in enumerate(self.active_features):
            key = f"{layer.item()}_{feat_idx.item()}"
            self.feature_to_idx[key] = i
        
        return True
    
    def _create_mock_graph(self):
        """Crea grafo mock basato sui risultati cicciotti esistenti"""
        print("🎭 Creando grafo mock da cicciotti_supernodes.json...")
        
        # Carica supernodi cicciotti
        with open("output/cicciotti_supernodes.json", 'r') as f:
            cicciotti = json.load(f)
        
        # Estrai tutte le feature uniche
        all_features = set()
        for supernode in cicciotti.values():
            for member in supernode['members']:
                all_features.add(member)
        
        all_features = sorted(list(all_features))
        
        # Crea active_features: [layer, pos, feat_idx]
        self.active_features = []
        for feature_key in all_features:
            parts = feature_key.split('_')
            if len(parts) == 2:
                layer, feat_idx = int(parts[0]), int(parts[1])
                # Mock: assume ultima position per semplicità
                pos = 10  # Mock position
                self.active_features.append([layer, pos, feat_idx])
        
        self.active_features = torch.tensor(self.active_features)
        n_features = len(self.active_features)
        
        # Crea adjacency_matrix mock
        # Simulate causalità: feature in layer superiori causano quelle in layer inferiori
        self.adjacency_matrix = torch.zeros((n_features, n_features))
        
        for i, (layer_i, pos_i, feat_i) in enumerate(self.active_features):
            for j, (layer_j, pos_j, feat_j) in enumerate(self.active_features):
                # Edge da j → i se layer_j <= layer_i (flow bottom-up)
                if layer_j < layer_i:
                    # Forza casuale ma plausibile
                    strength = np.random.exponential(0.1) if np.random.rand() > 0.9 else 0
                    self.adjacency_matrix[i, j] = strength
        
        # Crea mapping
        for i, (layer, pos, feat_idx) in enumerate(self.active_features):
            key = f"{layer.item()}_{feat_idx.item()}"
            self.feature_to_idx[key] = i
        
        self.input_tokens = ["Fact", ":", "the", "capital", "of", "the", "state", 
                            "containing", "Dallas", "is"]
        self.logit_tokens = torch.tensor([0, 1, 2, 3, 4])  # Mock
        
        print(f"✅ Grafo mock creato con {n_features} feature")
        return True
    
    def load_personalities(self):
        """Carica personalità feature per labeling"""
        try:
            with open("output/feature_personalities_corrected.json", 'r') as f:
                self.personalities = json.load(f)
            print(f"✅ Caricati {len(self.personalities)} personalità")
        except Exception as e:
            print(f"⚠️ Impossibile caricare personalità: {e}")
    
    def get_top_causal_edges(self, n_top: int = 50) -> List[Tuple]:
        """
        Estrai le top N edge causali per visualizzazione
        Returns: [(source_idx, target_idx, strength), ...]
        """
        # Prendi valori assoluti (sia positivi che negativi sono causali)
        abs_matrix = self.adjacency_matrix.abs()
        
        # Flatten e trova top-k
        flat_values = abs_matrix.flatten()
        top_k_values, top_k_indices = torch.topk(flat_values, min(n_top, len(flat_values)))
        
        # Converti flat indices in (row, col)
        edges = []
        n_rows = abs_matrix.shape[0]
        
        for value, flat_idx in zip(top_k_values, top_k_indices):
            if value < 0.01:  # Threshold minimo
                continue
            row = flat_idx // abs_matrix.shape[1]
            col = flat_idx % abs_matrix.shape[1]
            edges.append((col.item(), row.item(), value.item()))
        
        return edges
    
    def visualize_layered_graph(self, output_path: str = "output/causal_graph_visualization.svg",
                                max_edges: int = 100):
        """
        Crea visualizzazione con layout Layer × Position corretto
        """
        print(f"\n🎨 Creando visualizzazione causale...")
        
        # Setup figura
        fig, ax = plt.subplots(figsize=(16, 12))
        
        # Dimensioni layout
        n_layers = int(self.active_features[:, 0].max()) + 1
        n_positions = int(self.active_features[:, 1].max()) + 1
        
        # Spacing
        x_spacing = 100  # Spacing tra token positions
        y_spacing = 50   # Spacing tra layers
        
        # Raggruppa feature per (layer, position)
        nodes_by_layer_pos = defaultdict(list)
        for i, (layer, pos, feat_idx) in enumerate(self.active_features):
            layer, pos, feat_idx = layer.item(), pos.item(), feat_idx.item()
            nodes_by_layer_pos[(layer, pos)].append({
                'idx': i,
                'feature_key': f"{layer}_{feat_idx}",
                'layer': layer,
                'pos': pos,
                'feat_idx': feat_idx
            })
        
        # Disegna nodi
        node_positions = {}  # idx → (x, y)
        node_colors_by_layer = plt.cm.tab20(np.linspace(0, 1, n_layers))
        
        for (layer, pos), nodes in nodes_by_layer_pos.items():
            x_base = pos * x_spacing
            y = layer * y_spacing
            
            # Se multiple feature nella stessa posizione, offset orizzontale
            n_nodes = len(nodes)
            x_offset_step = 15 if n_nodes > 1 else 0
            
            for offset_idx, node in enumerate(nodes):
                x = x_base + (offset_idx - n_nodes/2) * x_offset_step
                node_positions[node['idx']] = (x, y)
                
                # Disegna nodo
                color = node_colors_by_layer[layer % len(node_colors_by_layer)]
                circle = plt.Circle((x, y), radius=8, color=color, 
                                   alpha=0.7, zorder=10)
                ax.add_patch(circle)
                
                # Label (se disponibile)
                label = self._get_feature_label(node['feature_key'])
                if label and len(nodes) <= 3:  # Mostra label solo se non troppo affollato
                    ax.text(x, y - 15, label, fontsize=7, 
                           ha='center', va='top', rotation=45)
        
        # Disegna edge causali
        top_edges = self.get_top_causal_edges(n_top=max_edges)
        print(f"📊 Disegnando {len(top_edges)} edge causali...")
        
        max_strength = max([e[2] for e in top_edges]) if top_edges else 1
        
        for source_idx, target_idx, strength in top_edges:
            if source_idx not in node_positions or target_idx not in node_positions:
                continue
            
            x1, y1 = node_positions[source_idx]
            x2, y2 = node_positions[target_idx]
            
            # Spessore proporzionale alla forza
            linewidth = 0.5 + (strength / max_strength) * 2
            
            # Colore: blu per causality forward, rosso per backward
            color = 'blue' if y2 > y1 else 'red'
            alpha = 0.3 + (strength / max_strength) * 0.5
            
            # Freccia
            arrow = FancyArrowPatch(
                (x1, y1), (x2, y2),
                arrowstyle='->', 
                mutation_scale=10,
                linewidth=linewidth,
                color=color,
                alpha=alpha,
                zorder=5
            )
            ax.add_patch(arrow)
        
        # Aggiungi grid per layer
        for layer in range(n_layers):
            y = layer * y_spacing
            ax.axhline(y=y, color='gray', alpha=0.2, linestyle='--', linewidth=0.5)
            ax.text(-50, y, f"L{layer}", fontsize=9, ha='right', va='center',
                   color='gray')
        
        # Aggiungi token labels (se disponibili)
        if hasattr(self, 'input_tokens'):
            for pos, token in enumerate(self.input_tokens[:n_positions]):
                x = pos * x_spacing
                ax.text(x, -30, token, fontsize=9, ha='center', va='top',
                       rotation=0, weight='bold')
        
        # Setup assi
        ax.set_xlim(-100, n_positions * x_spacing + 100)
        ax.set_ylim(-50, n_layers * y_spacing + 50)
        ax.set_aspect('equal')
        ax.axis('off')
        
        # Titolo
        plt.title("Attribution Graph - Causal Structure\n(Layer × Token Position)", 
                 fontsize=16, weight='bold', pad=20)
        
        # Legenda
        legend_elements = [
            mpatches.Patch(color='blue', alpha=0.5, label='Forward causality'),
            mpatches.Patch(color='red', alpha=0.5, label='Backward causality'),
            plt.Line2D([0], [0], marker='o', color='w', 
                      markerfacecolor='gray', markersize=8, 
                      label='Feature node')
        ]
        ax.legend(handles=legend_elements, loc='upper right', fontsize=10)
        
        # Salva
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"✅ Visualizzazione salvata: {output_path}")
        
        return output_path
    
    def _get_feature_label(self, feature_key: str) -> str:
        """Ottieni label per feature (da personalities se disponibile)"""
        if feature_key in self.personalities:
            personality = self.personalities[feature_key]
            peak_token = personality.get('most_common_peak', '')
            # Truncate se troppo lungo
            if len(peak_token) > 10:
                peak_token = peak_token[:10] + '...'
            return peak_token
        return ""
    
    def print_causal_summary(self):
        """Stampa statistiche causali del grafo"""
        print("\n" + "="*60)
        print("📊 STATISTICHE GRAFO CAUSALE")
        print("="*60)
        
        # Feature per layer
        layers = self.active_features[:, 0].numpy()
        positions = self.active_features[:, 1].numpy()
        
        print(f"\n🔢 Feature per layer:")
        for layer in np.unique(layers):
            count = np.sum(layers == layer)
            print(f"   Layer {layer:2d}: {count:3d} feature")
        
        # Token positions
        print(f"\n📍 Feature per token position:")
        for pos in sorted(np.unique(positions)):
            count = np.sum(positions == pos)
            print(f"   Position {pos:2d}: {count:3d} feature")
        
        # Edge statistics
        non_zero_edges = (self.adjacency_matrix.abs() > 0.01).sum()
        total_possible = self.adjacency_matrix.numel()
        sparsity = 100 * (1 - non_zero_edges / total_possible)
        
        print(f"\n🔗 Statistiche edge:")
        print(f"   Edge causali significative: {non_zero_edges}")
        print(f"   Sparsity: {sparsity:.2f}%")
        print(f"   Max causal strength: {self.adjacency_matrix.abs().max():.4f}")
        print(f"   Mean causal strength: {self.adjacency_matrix.abs().mean():.4f}")


def main():
    """Visualizza attribution graph con causalità"""
    print("🎯 VISUALIZZAZIONE ATTRIBUTION GRAPH CON CAUSALITÀ")
    print("="*60)
    
    visualizer = AttributionGraphVisualizer()
    
    # Carica grafo (o crea mock)
    if not visualizer.load_graph():
        print("❌ Impossibile caricare grafo")
        return
    
    # Carica personalities per labeling
    visualizer.load_personalities()
    
    # Stampa statistiche
    visualizer.print_causal_summary()
    
    # Crea visualizzazione
    output_path = visualizer.visualize_layered_graph(max_edges=150)
    
    print(f"\n✅ Visualizzazione completata!")
    print(f"📁 Output: {output_path}")
    print("\n💡 Prossimi step:")
    print("   1. Guarda la visualizzazione SVG")
    print("   2. Verifica la struttura layer × position")
    print("   3. Osserva le edge causali (blu=forward, rosso=backward)")


if __name__ == "__main__":
    main()

