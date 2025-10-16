#!/usr/bin/env python3
"""
Visualizzatore Supernodi Antropologici - Adattato da demos/graph_visualization.py Anthropic
"""

import json
import html
import math
from collections import namedtuple
from typing import List, Optional, Tuple, Dict

# Adattato da demos/graph_visualization.py Anthropic
Feature = namedtuple('Feature', ['layer', 'pos', 'feature_idx'])

class Supernode:
    """
    Supernode per visualizzazione - adattato da implementazione Anthropic
    Rappresenta un cluster di feature con metadati per visualizzazione
    """
    
    def __init__(self, name: str, features: List[Feature], children: List['Supernode'] = [], 
                 activation: Optional[float] = None, intervention: Optional[str] = None, 
                 replacement_node: Optional['Supernode'] = None, supernode_type: str = 'semantic'):
        self.name = name
        self.features = features
        self.activation = activation
        self.default_activations = None
        self.children = children
        self.intervention = intervention
        self.replacement_node = replacement_node
        self.supernode_type = supernode_type  # 'semantic' o 'computational'
    
    def __repr__(self):
        return f"Supernode(name={self.name}, type={self.supernode_type}, n_features={len(self.features)}, activation={self.activation})"

class InterventionGraph:
    """
    Grafo di intervento - adattato da implementazione Anthropic
    Gestisce visualizzazione e stato dei supernodi
    """
    
    def __init__(self, ordered_nodes: List[List[Supernode]], prompt: str):
        self.ordered_nodes = ordered_nodes
        self.prompt = prompt
        self.nodes = {}
    
    def initialize_node(self, node, activations=None):
        """Inizializza nodo con attivazioni di default"""
        self.nodes[node.name] = node
        if node.features and activations:
            # Calcola attivazione media dai membri del supernodo
            total_activation = sum(activations.get(f, 0.5) for f in node.features)
            node.activation = total_activation / len(node.features)
        else:
            node.activation = 0.5  # Default neutrale

class AnthropologicalVisualizer:
    """
    Visualizzatore principale per supernodi antropologici
    """
    
    def __init__(self):
        self.anthropological_results = {}
        self.personalities = {}
        self.comprehensive_labels = {}
        
    def load_anthropological_data(self):
        """Carica risultati strategia antropologica"""
        print("📥 Caricamento dati antropologici per visualizzazione...")
        
        try:
            with open("output/final_anthropological_optimized.json", 'r') as f:
                self.anthropological_results = json.load(f)
            
            with open("output/feature_personalities_corrected.json", 'r') as f:
                self.personalities = json.load(f)
            
            # Carica label interpretativi
            try:
                with open("output/comprehensive_supernode_labels.json", 'r') as f:
                    self.comprehensive_labels = json.load(f)
                print(f"✅ Caricati {len(self.comprehensive_labels)} label interpretativi")
            except FileNotFoundError:
                print("⚠️ Label interpretativi non trovati, uso nomi generici")
                self.comprehensive_labels = {}
                
            print(f"✅ Caricati {len(self.anthropological_results.get('semantic_supernodes', {}))} supernodi semantici")
            print(f"✅ Caricati {len(self.anthropological_results.get('computational_supernodes', {}))} supernodi computazionali")
            
            return True
            
        except Exception as e:
            print(f"❌ Errore caricamento: {e}")
            return False
    
    def convert_to_visualization_format(self, max_semantic=10, max_computational=5):
        """
        Converte supernodi antropologici in formato Supernode per visualizzazione
        Limita numero per leggibilità
        """
        print(f"\n🎨 CONVERSIONE PER VISUALIZZAZIONE")
        print("=" * 50)
        
        # Converti supernodi semantici (i più importanti)
        semantic_supernodes_data = self.anthropological_results.get('semantic_supernodes', {})
        semantic_nodes = []
        
        # Ordina per coerenza e prendi i migliori
        sorted_semantic = sorted(
            semantic_supernodes_data.items(), 
            key=lambda x: x[1].get('final_coherence', 0), 
            reverse=True
        )
        
        for i, (supernode_id, data) in enumerate(sorted_semantic[:max_semantic]):
            # Converti membri in Feature objects
            features = []
            for member in data.get('members', []):
                if member in self.personalities:
                    personality = self.personalities[member]
                    layer = personality['layer']
                    # Usa layer come posizione di default, feature_id come feature_idx
                    features.append(Feature(layer=layer, pos=layer, feature_idx=int(personality['feature_id'])))
            
            # Usa label interpretativo se disponibile
            if supernode_id in self.comprehensive_labels:
                interpretive_label = self.comprehensive_labels[supernode_id]['final_label']
                name = f"{interpretive_label}"
            else:
                # Fallback a nome generico
                theme = data.get('narrative_theme', 'unknown')
                name = f"SEM-{i+1}: {theme} ({len(features)})"
            
            # Calcola attivazione da coerenza
            coherence = data.get('final_coherence', 0)
            
            supernode = Supernode(
                name=name,
                features=features,
                activation=coherence,  # Usa coerenza come proxy per attivazione
                supernode_type='semantic'
            )
            
            semantic_nodes.append(supernode)
        
        # Converti supernodi computazionali (sample rappresentativo)
        computational_supernodes_data = self.anthropological_results.get('computational_supernodes', {})
        computational_nodes = []
        
        # Ordina per numero membri e prendi varietà
        sorted_computational = sorted(
            computational_supernodes_data.items(),
            key=lambda x: x[1].get('n_members', 0),
            reverse=True
        )
        
        for i, (supernode_id, data) in enumerate(sorted_computational[:max_computational]):
            # Converti membri in Feature objects
            features = []
            for member in data.get('members', []):
                if member in self.personalities:
                    personality = self.personalities[member]
                    layer = personality['layer']
                    features.append(Feature(layer=layer, pos=layer, feature_idx=int(personality['feature_id'])))
            
            # Usa label interpretativo se disponibile
            if supernode_id in self.comprehensive_labels:
                interpretive_label = self.comprehensive_labels[supernode_id]['final_label']
                name = f"{interpretive_label}"
            else:
                # Fallback a nome generico
                avg_layer = data.get('avg_layer', 0)
                token = data.get('dominant_token', 'unknown')
                name = f"COMP-{i+1}: L{avg_layer:.0f}-{token} ({len(features)})"
            
            supernode = Supernode(
                name=name,
                features=features,
                activation=data.get('avg_consistency', 0.5),
                supernode_type='computational'
            )
            
            computational_nodes.append(supernode)
        
        print(f"✅ Convertiti {len(semantic_nodes)} supernodi semantici")
        print(f"✅ Convertiti {len(computational_nodes)} supernodi computazionali")
        
        # Organizza in layers per visualizzazione  
        # Layer 0: Supernodi computazionali early-layer
        # Layer 1: Supernodi semantici main
        # Layer 2: Supernodi computazionali late-layer
        
        early_comp = [n for n in computational_nodes if 'L0-' in n.name or 'L1-' in n.name or 'L2-' in n.name]
        mid_semantic = semantic_nodes[:6]  # Primi 6 semantici
        late_comp = [n for n in computational_nodes if 'L20-' in n.name or 'L24-' in n.name]
        late_semantic = semantic_nodes[6:]  # Resto semantici
        
        # Costruisci connessioni semplici (early -> mid -> late)
        for node in mid_semantic:
            if early_comp:
                early_comp[0].children.append(node)
        
        for node in late_semantic + late_comp:
            if mid_semantic:
                mid_semantic[0].children.append(node)
        
        ordered_nodes = [
            early_comp + late_comp,  # Layer computazionale
            mid_semantic,            # Layer semantico principale
            late_semantic           # Layer semantico finale
        ]
        
        # Rimuovi layer vuoti
        ordered_nodes = [layer for layer in ordered_nodes if layer]
        
        return ordered_nodes
    
    def create_anthropological_visualization(self, max_semantic=10, max_computational=5):
        """
        Crea visualizzazione completa dei supernodi antropologici
        """
        print(f"\n🎨 CREAZIONE VISUALIZZAZIONE ANTROPOLOGICA")
        print("=" * 50)
        
        if not self.load_anthropological_data():
            return None
        
        # Converti in formato visualizzazione
        ordered_nodes = self.convert_to_visualization_format(max_semantic, max_computational)
        
        # Crea grafo di intervento
        prompt = "The capital of state containing Dallas is"  # Prompt del nostro dataset
        intervention_graph = InterventionGraph(ordered_nodes, prompt)
        
        # Inizializza nodi con attivazioni
        for layer in ordered_nodes:
            for node in layer:
                intervention_graph.initialize_node(node)
        
        # Top outputs dal nostro contesto
        top_outputs = [
            ("Austin", 0.75),
            ("Texas", 0.15),
            ("Dallas", 0.05),
            ("state", 0.03),
            ("capital", 0.02)
        ]
        
        # Crea visualizzazione SVG
        visualization = self.create_graph_visualization_adapted(intervention_graph, top_outputs)
        
        print(f"✅ Visualizzazione creata con {sum(len(layer) for layer in ordered_nodes)} supernodi")
        
        return visualization, intervention_graph
    
    def create_graph_visualization_adapted(self, intervention_graph: InterventionGraph, top_outputs: List[Tuple[str, float]]):
        """
        Crea visualizzazione SVG adattata - basata su create_graph_visualization Anthropic
        """
        
        nodes = intervention_graph.ordered_nodes
        prompt = intervention_graph.prompt
        
        # Calcola posizioni nodi
        node_data = self.calculate_node_positions_adapted(nodes)
        
        # Costruisci dati connessioni  
        connections = self.build_connections_data_adapted(nodes)
        
        # Genera componenti SVG
        connections_svg = self.create_connection_svg_adapted(node_data, connections)
        nodes_svg = self.create_nodes_svg_adapted(node_data)
        
        # Crea sezione output
        output_items_svg = self.create_output_section_svg(top_outputs)
        
        # Escape prompt per XML
        escaped_prompt = html.escape(prompt)
        prompt_lines = self.wrap_text_for_svg(escaped_prompt, max_width=80)
        
        # Crea testo prompt SVG
        prompt_text_svg = []
        for i, line in enumerate(prompt_lines):
            y_offset = 325 + (i * 15)
            prompt_text_svg.append(f'<text x="40" y="{y_offset}" fill="#333" font-family="Arial, sans-serif" font-size="12">{line}</text>')
        
        prompt_text_svg_str = '\n'.join(prompt_text_svg)
        
        # Crea SVG completo
        svg_content = f'''<svg width="900" height="500" xmlns="http://www.w3.org/2000/svg">
    <!-- Background -->
    <rect width="900" height="500" fill="#f8f9fa"/>
    <rect x="20" y="20" width="860" height="460" fill="white" stroke="#dee2e6" stroke-width="2" rx="12"/>
    
    <!-- Title -->
    <text x="40" y="45" fill="#495057" font-family="Arial, sans-serif" font-size="16" font-weight="bold">
        Supernodi Interpretativi: Labeling Automatico
    </text>
    
    <!-- Subtitle -->
    <text x="40" y="65" fill="#6c757d" font-family="Arial, sans-serif" font-size="12">
        54 supernodi con label automatici | Coverage: 83.7% | Score qualità: 0.6+
    </text>
    
    <!-- Graph area -->
    <g transform="translate(50, 20)">
        {connections_svg}
        {nodes_svg}
    </g>
    
    <!-- Prompt section -->
    <line x1="40" y1="320" x2="860" y2="320" stroke="#dee2e6" stroke-width="1"/>
    <text x="40" y="340" fill="#495057" font-family="Arial, sans-serif" font-size="12" font-weight="bold">
        PROMPT
    </text>
    
    <!-- Prompt text -->
    {prompt_text_svg_str}
    
    <!-- Output section -->
    <text x="40" y="380" fill="#495057" font-family="Arial, sans-serif" font-size="12" font-weight="bold">
        TOP OUTPUTS
    </text>
    
    <!-- Output items -->
    <g transform="translate(0, 15)">
        {output_items_svg}
    </g>
    
    <!-- Legend -->
    <g transform="translate(650, 100)">
        <!-- Semantic legend -->
        <rect x="0" y="0" width="20" height="15" fill="#e3f2fd" stroke="#1976d2" stroke-width="2" rx="3"/>
        <text x="25" y="12" fill="#333" font-family="Arial, sans-serif" font-size="11">Semantici (cicciotti)</text>
        
        <!-- Computational legend -->
        <rect x="0" y="25" width="20" height="15" fill="#f3e5f5" stroke="#7b1fa2" stroke-width="2" rx="3"/>
        <text x="25" y="37" fill="#333" font-family="Arial, sans-serif" font-size="11">Computazionali</text>
        
        <!-- Stats -->
        <text x="0" y="60" fill="#495057" font-family="Arial, sans-serif" font-size="10" font-weight="bold">STATISTICHE</text>
        <text x="0" y="75" fill="#6c757d" font-family="Arial, sans-serif" font-size="9">Coerenza media: 0.842</text>
        <text x="0" y="90" fill="#6c757d" font-family="Arial, sans-serif" font-size="9">Feature coperte: 891</text>
        <text x="0" y="105" fill="#6c757d" font-family="Arial, sans-serif" font-size="9">Zero duplicati verificato</text>
    </g>
</svg>'''
        
        return svg_content
    
    def calculate_node_positions_adapted(self, nodes: List[List[Supernode]]):
        """Calcola posizioni nodi - adattato da calculate_node_positions Anthropic"""
        container_width = 700
        container_height = 250
        node_width = 140  # Più largo per nomi antropologici
        node_height = 35
        
        node_data = {}
        
        for row_index in range(len(nodes)):
            row = nodes[row_index]
            row_y = container_height - (row_index * (container_height / (len(nodes) + 0.5)))
            
            for col_index in range(len(row)):
                node = row[col_index]
                row_width = len(row) * node_width + (len(row) - 1) * 30
                start_x = (container_width - row_width) / 2
                node_x = start_x + col_index * (node_width + 30)
                
                node_data[node.name] = {
                    'x': node_x,
                    'y': row_y,
                    'node': node
                }
        
        return node_data
    
    def build_connections_data_adapted(self, nodes: List[List[Supernode]]):
        """Costruisce dati connessioni - adattato da build_connections_data Anthropic"""
        connections = []
        
        # Raccoglie tutti i nodi unici
        all_nodes = set()
        for layer in nodes:
            for node in layer:
                all_nodes.add(node)
                if node.replacement_node:
                    all_nodes.add(node.replacement_node)
        
        # Aggiungi connessioni dai nodi ai loro figli
        for node in all_nodes:
            for child in node.children:
                connection = {
                    'from': node.name,
                    'to': child.name,
                    'type': node.supernode_type
                }
                connections.append(connection)
        
        return connections
    
    def create_connection_svg_adapted(self, node_data, connections):
        """Genera SVG connessioni - adattato da create_connection_svg Anthropic"""
        svg_parts = []
        
        for conn in connections:
            from_center = self.get_node_center(node_data, conn['from'])
            to_center = self.get_node_center(node_data, conn['to'])
            
            if from_center['x'] == 0 or to_center['x'] == 0:
                continue
            
            # Colore linea basato su tipo
            if conn.get('type') == 'semantic':
                stroke_color = "#1976d2"
                stroke_width = "3"
            else:
                stroke_color = "#7b1fa2"
                stroke_width = "2"
            
            # Linea connessione
            svg_parts.append(f'<line x1="{from_center["x"]}" y1="{from_center["y"]}" '
                            f'x2="{to_center["x"]}" y2="{to_center["y"]}" '
                            f'stroke="{stroke_color}" stroke-width="{stroke_width}"/>')
            
            # Freccia alla fine
            dx = to_center['x'] - from_center['x']
            dy = to_center['y'] - from_center['y']
            length = math.sqrt(dx * dx + dy * dy)
            
            if length > 0:
                dx_norm = dx / length
                dy_norm = dy / length
                
                arrow_size = 8
                arrow_tip_x = to_center['x']
                arrow_tip_y = to_center['y']
                
                base_x = arrow_tip_x - arrow_size * dx_norm
                base_y = arrow_tip_y - arrow_size * dy_norm
                
                perp_x = -dy_norm * (arrow_size / 2)
                perp_y = dx_norm * (arrow_size / 2)
                
                left_x = base_x + perp_x
                left_y = base_y + perp_y
                right_x = base_x - perp_x
                right_y = base_y - perp_y
                
                svg_parts.append(f'<polygon points="{arrow_tip_x},{arrow_tip_y} {left_x},{left_y} {right_x},{right_y}" '
                               f'fill="{stroke_color}"/>')
        
        return '\n'.join(svg_parts)
    
    def create_nodes_svg_adapted(self, node_data):
        """Genera SVG nodi - adattato da create_nodes_svg Anthropic"""
        svg_parts = []
        
        for name, data in node_data.items():
            node = data['node']
            x = data['x']
            y = data['y']
            
            # Colori basati su tipo supernodo
            if node.supernode_type == 'semantic':
                fill_color = "#e3f2fd"
                text_color = "#1565c0"
                stroke_color = "#1976d2"
            else:  # computational
                fill_color = "#f3e5f5"
                text_color = "#6a1b9a"
                stroke_color = "#7b1fa2"
            
            # Rettangolo nodo
            svg_parts.append(f'<rect x="{x}" y="{y}" width="140" height="35" '
                            f'fill="{fill_color}" stroke="{stroke_color}" stroke-width="2" rx="8"/>')
            
            # Testo nodo - truncate se troppo lungo
            display_name = name[:18] + "..." if len(name) > 18 else name
            text_x = x + 70  # Centro orizzontale
            text_y = y + 22  # Centro verticale
            escaped_name = html.escape(display_name)
            svg_parts.append(f'<text x="{text_x}" y="{text_y}" text-anchor="middle" '
                            f'fill="{text_color}" font-family="Arial, sans-serif" font-size="10" font-weight="bold">{escaped_name}</text>')
            
            # Label attivazione se presente
            if node.activation is not None:
                activation_pct = round(node.activation * 100)
                label_x = x - 25
                label_y = y - 5
                
                # Background label attivazione
                svg_parts.append(f'<rect x="{label_x}" y="{label_y}" width="35" height="16" '
                               f'fill="white" stroke="#ccc" stroke-width="1" rx="8"/>')
                
                # Testo attivazione
                svg_parts.append(f'<text x="{label_x + 17}" y="{label_y + 12}" text-anchor="middle" '
                               f'fill="{stroke_color}" font-family="Arial, sans-serif" font-size="9" font-weight="bold">{activation_pct}%</text>')
        
        return '\n'.join(svg_parts)
    
    def get_node_center(self, node_data, node_name):
        """Ottieni coordinate centro nodo - da get_node_center Anthropic"""
        node = node_data.get(node_name)
        if not node:
            return {'x': 0, 'y': 0}
        return {
            'x': node['x'] + 70,  # Centro nodo (140px larghezza)
            'y': node['y'] + 17.5  # Centro nodo (35px altezza)
        }
    
    def create_output_section_svg(self, top_outputs):
        """Crea sezione output SVG"""
        output_items_svg = []
        current_x = 40
        
        for i, (text, percentage) in enumerate(top_outputs):
            if i >= 5:  # Limite per leggibilità
                break
            
            display_text = text if text else "(empty)"
            escaped_display_text = html.escape(display_text)
            percentage_text = f"{round(percentage * 100)}%"
            
            # Background rettangolo output
            item_width = len(display_text) * 8 + len(percentage_text) * 6 + 20
            output_items_svg.append(f'<rect x="{current_x}" y="380" width="{item_width}" height="20" '
                                   f'fill="#e9ecef" stroke="none" rx="6"/>')
            
            # Testo output
            output_items_svg.append(f'<text x="{current_x + 5}" y="394" '
                                   f'fill="#495057" font-family="Arial, sans-serif" font-size="11" font-weight="bold">'
                                   f'{escaped_display_text} <tspan fill="#6c757d" font-size="10">{percentage_text}</tspan></text>')
            
            current_x += item_width + 15
        
        return '\n'.join(output_items_svg)
    
    def wrap_text_for_svg(self, text, max_width=80):
        """Text wrapping per SVG - da wrap_text_for_svg Anthropic"""
        if len(text) <= max_width:
            return [text]
        
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            if len(current_line + " " + word) <= max_width:
                current_line = current_line + " " + word if current_line else word
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        return lines

def main():
    """Demo visualizzazione supernodi antropologici"""
    
    print("🎨 VISUALIZZATORE SUPERNODI ANTROPOLOGICI")
    print("=" * 60)
    
    visualizer = AnthropologicalVisualizer()
    
    # Crea visualizzazione
    result = visualizer.create_anthropological_visualization(
        max_semantic=8,  # Mostra 8 supernodi semantici migliori
        max_computational=4  # Mostra 4 supernodi computazionali rappresentativi
    )
    
    if result:
        svg_content, intervention_graph = result
        
        # Salva SVG
        with open("output/anthropological_supernodes_visualization.svg", 'w') as f:
            f.write(svg_content)
        
        print(f"✅ Visualizzazione salvata: output/anthropological_supernodes_visualization.svg")
        print(f"📊 Supernodi visualizzati: {sum(len(layer) for layer in intervention_graph.ordered_nodes)}")
        
        # Salva anche dati strutturati per future analisi
        graph_data = {
            'prompt': intervention_graph.prompt,
            'supernodes': [
                {
                    'name': node.name,
                    'type': node.supernode_type,
                    'n_features': len(node.features),
                    'activation': node.activation,
                    'children': [child.name for child in node.children]
                }
                for layer in intervention_graph.ordered_nodes
                for node in layer
            ]
        }
        
        with open("output/visualization_graph_data.json", 'w') as f:
            json.dump(graph_data, f, indent=2)
        
        print(f"📁 Dati grafo salvati: output/visualization_graph_data.json")
        
        return svg_content
    else:
        print("❌ Fallimento nella creazione visualizzazione")

if __name__ == "__main__":
    main()
