"""
Graph Visualization per Circuit Tracer

Versione UNIFIED: merge di graph_visualization.py e graph_visualization_fixed.py

Layout intelligente:
- Se Feature hanno layer/pos: usa layout Layer × Position (improved)
- Altrimenti: fallback a layout semplice grid-based

Usage:
    from scripts.visualization.graph_visualization import (
        create_graph_visualization,
        Supernode,
        InterventionGraph,
        Feature
    )
"""

from collections import namedtuple, defaultdict
from typing import List, Optional, Tuple, Dict
import math
import html

import torch
from IPython.display import SVG


# ============================================================================
# DATA CLASSES
# ============================================================================

Feature = namedtuple('Feature', ['layer', 'pos', 'feature_idx'])


class InterventionGraph:
    """Grafo di intervento con prompt e nodi organizzati"""
    prompt: str
    ordered_nodes: List['Supernode']
    nodes: Dict[str, 'Supernode']

    def __init__(self, ordered_nodes: List['Supernode'], prompt: str):
        self.ordered_nodes = ordered_nodes
        self.prompt = prompt
        self.nodes = {}

    def initialize_node(self, node, activations):
        """Inizializza un nodo con le sue attivazioni di default"""
        self.nodes[node.name] = node
        if node.features:
            node.default_activations = torch.tensor([activations[feature] for feature in node.features])
        else:
            node.default_activations = None

    def set_node_activation_fractions(self, current_activations):
        """Imposta le frazioni di attivazione correnti per tutti i nodi"""
        for node in self.nodes.values():
            if node.features:
                current_node_activation = torch.tensor([current_activations[feature] for feature in node.features]) 
                node.activation = (current_node_activation / node.default_activations).mean().item()
            else:
                node.activation = None
            node.intervention = None
            node.replacement_node = None


class Supernode:
    """Nodo del grafo rappresentante un gruppo di feature"""
    name: str
    activation: float|None
    default_activations: torch.Tensor|None
    children: List['Supernode']
    intervention: None
    replacement_node: Optional['Supernode']

    def __init__(self, name: str, features: List[Feature], children: List['Supernode'] = [], 
                 intervention: Optional[str] = None, replacement_node: Optional['Supernode'] = None):
        self.name = name
        self.features = features
        self.activation = None
        self.default_activations = None
        self.children = children
        self.intervention = intervention
        self.replacement_node = replacement_node

    def __repr__(self):
        return f"Node(name={self.name}, activation={self.activation}, children={self.children}, intervention={self.intervention}, replacement_node={self.replacement_node})"


# ============================================================================
# LAYOUT FUNCTIONS - IMPROVED (Layer × Position based)
# ============================================================================

def calculate_node_positions_improved(nodes: List[List['Supernode']]):
    """
    Layout MIGLIORATO: Usa layer e position REALI dalle Feature!
    
    Layout:
    - Asse X: Token position (da Feature.pos)
    - Asse Y: Layer (da Feature.layer) - bottom-up
    
    Returns:
        node_data: Dict[node_name, {x, y, node, layer, pos}]
        layer_range: (min_layer, max_layer)
        pos_range: (min_pos, max_pos)
    """
    container_width = 1200
    container_height = 1600
    node_width = 80
    node_height = 30
    
    # Spacing tra elementi
    x_spacing = 100
    y_spacing = 30
    
    # Determina range layer e positions
    all_nodes = []
    for layer_list in nodes:
        all_nodes.extend(layer_list)
    
    # Trova min/max layer e position dalle Feature
    min_layer, max_layer = float('inf'), 0
    min_pos, max_pos = float('inf'), 0
    
    for node in all_nodes:
        if node.features:
            for feature in node.features:
                min_layer = min(min_layer, feature.layer)
                max_layer = max(max_layer, feature.layer)
                min_pos = min(min_pos, feature.pos)
                max_pos = max(max_pos, feature.pos)
    
    # Se nessuna feature ha layer/pos, ritorna None per fallback
    if min_layer == float('inf'):
        return None
    
    # Raggruppa nodi per (layer, position) medio
    nodes_by_layer_pos = defaultdict(list)
    
    for node in all_nodes:
        if node.features:
            # Usa layer/pos della prima feature (o media se multiple)
            avg_layer = sum(f.layer for f in node.features) / len(node.features)
            avg_pos = sum(f.pos for f in node.features) / len(node.features)
            
            # Arrotonda per raggruppamento
            layer_key = int(round(avg_layer))
            pos_key = int(round(avg_pos))
            
            nodes_by_layer_pos[(layer_key, pos_key)].append(node)
        else:
            # Embedding nodes - mettili in basso (layer 0)
            pos_key = len(nodes_by_layer_pos) % 3
            nodes_by_layer_pos[(0, pos_key)].append(node)
    
    # Calcola posizioni nodi
    node_data = {}
    base_x = 100
    base_y = container_height - 150
    
    for (layer, pos), node_list in nodes_by_layer_pos.items():
        # Posizione base per questo (layer, pos)
        x_base = base_x + pos * x_spacing
        y_base = base_y - layer * y_spacing
        
        # Se multipli nodi nella stessa posizione, offset
        n_nodes = len(node_list)
        offset_step = 25 if n_nodes > 1 else 0
        
        for idx, node in enumerate(node_list):
            # Offset orizzontale per nodi multipli
            x_offset = (idx - (n_nodes - 1) / 2) * offset_step
            
            node_x = x_base + x_offset - node_width / 2
            node_y = y_base - node_height / 2
            
            node_data[node.name] = {
                'x': node_x,
                'y': node_y,
                'node': node,
                'layer': layer,
                'pos': pos
            }
    
    # Handle replacement nodes
    all_nodes_set = set(all_nodes)
    for node in all_nodes_set:
        if node.replacement_node and node.replacement_node.name not in node_data:
            original_pos = node_data.get(node.name)
            if original_pos:
                node_data[node.replacement_node.name] = {
                    'x': original_pos['x'] + 30,
                    'y': original_pos['y'] - 40,
                    'node': node.replacement_node,
                    'layer': original_pos.get('layer', 0),
                    'pos': original_pos.get('pos', 0)
                }
    
    return node_data, (int(min_layer), int(max_layer)), (int(min_pos), int(max_pos))


# ============================================================================
# LAYOUT FUNCTIONS - SIMPLE (Grid-based fallback)
# ============================================================================

def calculate_node_positions_simple(nodes: List[List['Supernode']]):
    """
    Layout SEMPLICE: Grid-based (fallback quando non ci sono layer/pos)
    """
    container_width = 600
    container_height = 250
    node_width = 100
    node_height = 35
    
    node_data = {}
    
    for row_index in range(len(nodes)):
        row = nodes[row_index]
        row_y = container_height - (row_index * (container_height / (len(nodes) + 0.5)))
        
        for col_index in range(len(row)):
            node = row[col_index]
            row_width = len(row) * node_width + (len(row) - 1) * 50
            start_x = (container_width - row_width) / 2
            node_x = start_x + col_index * (node_width + 50)
            
            node_data[node.name] = {
                'x': node_x,
                'y': row_y,
                'node': node,
                'layer': row_index,
                'pos': col_index
            }
    
    # Handle replacement nodes
    all_nodes = set()
    for layer in nodes:
        for node in layer:
            all_nodes.add(node)
            if node.replacement_node:
                all_nodes.add(node.replacement_node)
    
    for node in all_nodes:
        if node.replacement_node and node.replacement_node.name not in node_data:
            original_pos = node_data.get(node.name)
            if original_pos:
                node_data[node.replacement_node.name] = {
                    'x': original_pos['x'] + 30,
                    'y': original_pos['y'] - 35,
                    'node': node.replacement_node,
                    'layer': original_pos.get('layer', 0),
                    'pos': original_pos.get('pos', 0)
                }
    
    return node_data, (0, len(nodes)-1), (0, max(len(row) for row in nodes)-1 if nodes else 0)


# ============================================================================
# SVG GENERATION HELPERS
# ============================================================================

def get_node_center(node_data, node_name, simple_mode=False):
    """Get center coordinates of a node"""
    node = node_data.get(node_name)
    if not node:
        return {'x': 0, 'y': 0}
    
    if simple_mode:
        return {
            'x': node['x'] + 50,
            'y': node['y'] + 17.5
        }
    else:
        return {
            'x': node['x'] + 40,
            'y': node['y'] + 15
        }


def create_connection_svg(node_data, connections, simple_mode=False):
    """Generate SVG elements for all connections"""
    svg_parts = []
    
    for conn in connections:
        from_center = get_node_center(node_data, conn['from'], simple_mode)
        to_center = get_node_center(node_data, conn['to'], simple_mode)
        
        if from_center['x'] == 0 or to_center['x'] == 0:
            continue
        
        # Determina colore e stile
        if conn.get('replacement'):
            stroke_color = "#D2691E"
            stroke_width = "4"
        elif not simple_mode:
            # Improved mode: colore basato su direzione causale
            from_node_data = node_data.get(conn['from'])
            to_node_data = node_data.get(conn['to'])
            
            is_forward = False
            if from_node_data and to_node_data:
                from_layer = from_node_data.get('layer', 0)
                to_layer = to_node_data.get('layer', 0)
                is_forward = to_layer > from_layer
            
            if is_forward:
                stroke_color = "#4169E1"  # Blu per forward causality
                stroke_width = "2.5"
            else:
                stroke_color = "#DC143C"  # Rosso per backward/lateral
                stroke_width = "2"
        else:
            # Simple mode: stile uniforme
            stroke_color = "#8B4513"
            stroke_width = "3"
        
        opacity = "0.6" if not simple_mode else "1.0"
        
        # Line
        svg_parts.append(f'<line x1="{from_center["x"]}" y1="{from_center["y"]}" '
                        f'x2="{to_center["x"]}" y2="{to_center["y"]}" '
                        f'stroke="{stroke_color}" stroke-width="{stroke_width}" '
                        f'opacity="{opacity}"/>')
        
        # Arrow
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
                           f'fill="{stroke_color}" opacity="{opacity}"/>')
    
    return '\n'.join(svg_parts)


def create_nodes_svg(node_data, simple_mode=False):
    """Generate SVG elements for all nodes"""
    svg_parts = []
    
    # Collect all replacement nodes
    replacement_nodes = set()
    for data in node_data.values():
        node = data['node']
        if node.replacement_node:
            replacement_nodes.add(node.replacement_node.name)
    
    for name, data in node_data.items():
        node = data['node']
        x = data['x']
        y = data['y']
        layer = data.get('layer', 0)
        
        # Determine node colors and styles
        is_low_activation = node.activation is not None and node.activation <= 0.25
        has_negative_intervention = node.intervention and '-' in node.intervention
        is_replacement = name in replacement_nodes
        
        if is_low_activation or has_negative_intervention:
            fill_color = "#f0f0f0"
            text_color = "#bbb"
            stroke_color = "#ddd"
        elif is_replacement:
            fill_color = "#FFF8DC"
            text_color = "#333"
            stroke_color = "#D2691E"
        elif not simple_mode:
            # Improved mode: gradiente di colore basato su layer
            layer_hue = (layer * 30) % 360
            fill_color = f"hsl({layer_hue}, 70%, 85%)"
            text_color = "#333"
            stroke_color = "#999"
        else:
            # Simple mode: colore uniforme
            fill_color = "#e8e8e8"
            text_color = "#333"
            stroke_color = "#999"
        
        # Node rectangle
        if simple_mode:
            width, height = 100, 35
            font_size = 12
        else:
            width, height = 80, 30
            font_size = 10
        
        svg_parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
                        f'fill="{fill_color}" stroke="{stroke_color}" stroke-width="2" rx="{"8" if simple_mode else "6"}"/>')
        
        # Node text
        text_x = x + width / 2
        text_y = y + height / 2 + font_size / 3
        
        # Truncate PRIMA dell'escape per evitare di tagliare HTML entities
        max_len = 15 if simple_mode else 12
        truncated_name = name if len(name) <= max_len else name[:max_len-2] + '...'
        display_name = html.escape(truncated_name)
        
        svg_parts.append(f'<text x="{text_x}" y="{text_y}" text-anchor="middle" '
                        f'fill="{text_color}" font-family="Arial, sans-serif" font-size="{font_size}" font-weight="bold">{display_name}</text>')
        
        # Layer badge (solo in improved mode)
        if not simple_mode and layer > 0:
            badge_x = x - 8
            badge_y = y - 8
            svg_parts.append(f'<circle cx="{badge_x}" cy="{badge_y}" r="10" '
                           f'fill="white" stroke="#666" stroke-width="1"/>')
            svg_parts.append(f'<text x="{badge_x}" y="{badge_y + 4}" text-anchor="middle" '
                           f'fill="#666" font-family="Arial, sans-serif" font-size="8">{layer}</text>')
        
        # Activation percentage
        if node.activation is not None:
            activation_pct = round(node.activation * 100)
            
            if simple_mode:
                # Simple mode: background box
                label_x = x - 15
                label_y = y - 5
                svg_parts.append(f'<rect x="{label_x}" y="{label_y}" width="30" height="16" '
                               f'fill="white" stroke="#ccc" stroke-width="1" rx="4"/>')
                svg_parts.append(f'<text x="{label_x + 15}" y="{label_y + 12}" text-anchor="middle" '
                               f'fill="#8B4513" font-family="Arial, sans-serif" font-size="10" font-weight="bold">{activation_pct}%</text>')
            else:
                # Improved mode: testo semplice
                label_x = x + 75
                label_y = y - 5
                svg_parts.append(f'<text x="{label_x}" y="{label_y}" text-anchor="end" '
                               f'fill="#8B4513" font-family="Arial, sans-serif" font-size="9">{activation_pct}%</text>')
        
        # Intervention (simple mode only)
        if simple_mode and node.intervention:
            intervention_x = x - 20
            intervention_y = y - 5
            
            text_width = len(node.intervention) * 8 + 10
            escaped_intervention = html.escape(node.intervention)
            
            svg_parts.append(f'<rect x="{intervention_x}" y="{intervention_y}" width="{text_width}" height="16" '
                           f'fill="#D2691E" stroke="none" rx="12"/>')
            svg_parts.append(f'<text x="{intervention_x + text_width/2}" y="{intervention_y + 12}" text-anchor="middle" '
                           f'fill="white" font-family="Arial, sans-serif" font-size="10" font-weight="bold">{escaped_intervention}</text>')
    
    return '\n'.join(svg_parts)


def build_connections_data(nodes: List[List['Supernode']]):
    """Build connection data from node relationships"""
    connections = []
    
    # Collect all unique nodes
    all_nodes = set()
    
    def add_node_and_related(node):
        all_nodes.add(node)
        if node.replacement_node:
            add_node_and_related(node.replacement_node)
        for child in node.children:
            add_node_and_related(child)
    
    for layer in nodes:
        for node in layer:
            add_node_and_related(node)
    
    # Identify replacement nodes
    replacement_nodes = set()
    for node in all_nodes:
        if node.replacement_node:
            replacement_nodes.add(node.replacement_node.name)
    
    # Add connections
    for node in all_nodes:
        for child in node.children:
            if node.replacement_node:
                continue
            
            is_replacement = node.name in replacement_nodes
            
            connection = {
                'from': node.name,
                'to': child.name
            }
            if is_replacement:
                connection['replacement'] = True
            
            connections.append(connection)
    
    return connections


def wrap_text_for_svg(text, max_width=80):
    """Simple text wrapping for SVG"""
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


# ============================================================================
# MAIN VISUALIZATION FUNCTION
# ============================================================================

def create_graph_visualization(intervention_graph: InterventionGraph, 
                               top_outputs: List[Tuple[str, float]],
                               force_simple: bool = False):
    """
    Crea visualizzazione SVG del grafo.
    
    INTELLIGENTE: usa automaticamente il layout migliore disponibile:
    - Se le Feature hanno layer/pos: usa layout Layer × Position (improved)
    - Altrimenti: fallback a layout semplice grid-based
    
    Args:
        intervention_graph: Il grafo di intervento
        top_outputs: Lista di tuple (token, probability)
        force_simple: Se True, forza l'uso del layout semplice
    
    Returns:
        SVG object per visualizzazione
    """
    nodes = intervention_graph.ordered_nodes
    prompt = intervention_graph.prompt
    
    # Prova layout improved (se non forzato simple)
    use_simple = force_simple
    node_data = None
    layer_range = (0, 0)
    pos_range = (0, 0)
    
    if not force_simple:
        result = calculate_node_positions_improved(nodes)
        if result is None:
            # Nessun layer/pos disponibile, fallback a simple
            use_simple = True
        else:
            node_data, layer_range, pos_range = result
    
    # Fallback a simple se necessario
    if use_simple:
        node_data, layer_range, pos_range = calculate_node_positions_simple(nodes)
    
    # Build connections
    connections = build_connections_data(nodes)
    
    # Generate SVG
    connections_svg = create_connection_svg(node_data, connections, use_simple)
    nodes_svg = create_nodes_svg(node_data, use_simple)
    
    # Generate layout-specific elements
    if use_simple:
        svg_content = _create_simple_svg(prompt, top_outputs, connections_svg, nodes_svg)
    else:
        svg_content = _create_improved_svg(prompt, top_outputs, connections_svg, nodes_svg, 
                                           layer_range, pos_range)
    
    return SVG(svg_content)


def _create_simple_svg(prompt, top_outputs, connections_svg, nodes_svg):
    """Generate simple layout SVG"""
    
    # Create output items
    output_y_start = 350
    output_items_svg = []
    current_x = 40
    
    for i, (text, percentage) in enumerate(top_outputs):
        if i >= 6:
            break
            
        display_text = text if text else "(empty)"
        escaped_display_text = html.escape(display_text)
        percentage_text = f"{round(percentage * 100)}%"
        
        item_width = len(display_text) * 8 + len(percentage_text) * 6 + 20
        output_items_svg.append(f'<rect x="{current_x}" y="{output_y_start}" width="{item_width}" height="20" '
                               f'fill="#e8e8e8" stroke="none" rx="6"/>')
        
        output_items_svg.append(f'<text x="{current_x + 5}" y="{output_y_start + 14}" '
                               f'fill="#333" font-family="Arial, sans-serif" font-size="11" font-weight="bold">'
                               f'{escaped_display_text} <tspan fill="#555" font-size="10">{percentage_text}</tspan></text>')
        
        current_x += item_width + 10
    
    output_items_svg_str = '\n'.join(output_items_svg)
    
    # Prompt text
    escaped_prompt = html.escape(prompt)
    prompt_lines = wrap_text_for_svg(escaped_prompt, max_width=80)
    
    prompt_text_svg = []
    for i, line in enumerate(prompt_lines):
        y_offset = 325 + (i * 15)
        prompt_text_svg.append(f'<text x="40" y="{y_offset}" fill="#333" font-family="Arial, sans-serif" font-size="12">{line}</text>')
    
    prompt_text_svg_str = '\n'.join(prompt_text_svg)
    
    return f'''<svg width="700" height="400" xmlns="http://www.w3.org/2000/svg">
    <!-- Background -->
    <rect width="700" height="400" fill="#f5f5f5"/>
    <rect x="20" y="20" width="660" height="360" fill="white" stroke="none" rx="12"/>
    
    <!-- Title -->
    <text x="40" y="45" fill="#666" font-family="Arial, sans-serif" font-size="14" font-weight="bold" 
          text-transform="uppercase" letter-spacing="1px">Graph &amp; Interventions</text>
    
    <!-- Graph area -->
    <g transform="translate(50, 0)">
        {connections_svg}
        {nodes_svg}
    </g>
    
    <!-- Prompt section -->
    <line x1="40" y1="290" x2="660" y2="290" stroke="#ddd" stroke-width="1"/>
    <text x="40" y="310" fill="#666" font-family="Arial, sans-serif" font-size="12" font-weight="bold" 
          text-transform="uppercase" letter-spacing="0.5px">Prompt</text>
    
    {prompt_text_svg_str}
    
    <!-- Top outputs section -->
    <text x="40" y="350" fill="#666" font-family="Arial, sans-serif" font-size="10" font-weight="bold" 
          text-transform="uppercase" letter-spacing="0.5px">Top Outputs</text>
    
    <g transform="translate(0, 5)">
        {output_items_svg_str}
    </g>
</svg>'''


def _create_improved_svg(prompt, top_outputs, connections_svg, nodes_svg, layer_range, pos_range):
    """Generate improved layout SVG with Layer × Position"""
    
    min_layer, max_layer = layer_range
    min_pos, max_pos = pos_range
    
    # Grid lines per layers
    grid_svg_parts = []
    base_y = 1450
    y_spacing = 30
    
    for layer in range(min_layer, max_layer + 1):
        y = base_y - layer * y_spacing
        grid_svg_parts.append(f'<line x1="50" y1="{y}" x2="1150" y2="{y}" '
                             f'stroke="#ddd" stroke-width="0.5" stroke-dasharray="5,5"/>')
        grid_svg_parts.append(f'<text x="30" y="{y + 5}" fill="#999" '
                             f'font-family="monospace" font-size="10">L{layer}</text>')
    
    grid_svg = '\n'.join(grid_svg_parts)
    
    # Token position markers
    base_x = 100
    x_spacing = 100
    token_markers = []
    
    for pos in range(min_pos, min(max_pos + 1, 15)):
        x = base_x + pos * x_spacing
        token_markers.append(f'<text x="{x}" y="1530" fill="#666" text-anchor="middle" '
                           f'font-family="monospace" font-size="10">T{pos}</text>')
    
    tokens_svg = '\n'.join(token_markers)
    
    # Legenda
    legend_svg = '''
    <g transform="translate(950, 50)">
        <text x="0" y="0" fill="#666" font-size="12" font-weight="bold">Legenda:</text>
        <line x1="0" y1="15" x2="40" y2="15" stroke="#4169E1" stroke-width="2.5"/>
        <text x="45" y="20" fill="#666" font-size="10">Forward (layer up)</text>
        <line x1="0" y1="35" x2="40" y2="35" stroke="#DC143C" stroke-width="2"/>
        <text x="45" y="40" fill="#666" font-size="10">Backward/Lateral</text>
    </g>
    '''
    
    # Output items
    output_items_svg = []
    current_x = 950
    current_y = 100
    
    for i, (text, percentage) in enumerate(top_outputs[:4]):
        display_text = text if text else "(empty)"
        escaped_display_text = html.escape(display_text)
        percentage_text = f"{round(percentage * 100)}%"
        
        output_items_svg.append(f'<text x="{current_x}" y="{current_y + i*20}" fill="#333" '
                               f'font-family="Arial, sans-serif" font-size="10">'
                               f'{escaped_display_text}: <tspan fill="#666">{percentage_text}</tspan></text>')
    
    outputs_svg = '\n'.join(output_items_svg)
    
    return f'''<svg width="1300" height="1650" xmlns="http://www.w3.org/2000/svg">
    <rect width="1300" height="1650" fill="#fafafa"/>
    
    <text x="650" y="30" text-anchor="middle" fill="#333" 
          font-family="Arial, sans-serif" font-size="18" font-weight="bold">
        Attribution Graph - Layer × Token Position Layout
    </text>
    
    <text x="650" y="50" text-anchor="middle" fill="#666" 
          font-family="Arial, sans-serif" font-size="12">
        {html.escape(prompt)}
    </text>
    
    <!-- Grid -->
    {grid_svg}
    
    <!-- Token markers -->
    {tokens_svg}
    
    <!-- Connections -->
    {connections_svg}
    
    <!-- Nodes -->
    {nodes_svg}
    
    <!-- Legend -->
    {legend_svg}
    
    <!-- Top outputs -->
    <text x="950" y="85" fill="#666" font-size="12" font-weight="bold">Top Outputs:</text>
    {outputs_svg}
    
    <!-- Axis labels -->
    <text x="650" y="1570" text-anchor="middle" fill="#666" font-weight="bold" font-size="12">
        Token Position →
    </text>
    <text x="10" y="825" text-anchor="middle" fill="#666" font-weight="bold" font-size="12"
          transform="rotate(-90 10 825)">
        Layer →
    </text>
</svg>'''
