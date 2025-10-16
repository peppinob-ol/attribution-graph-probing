"""
Versione CORRETTA di graph_visualization.py
USA layer e position reali dalle Feature per il layout spaziale

Layout:
- Asse X: Token positions (da Feature.pos)
- Asse Y: Layers (da Feature.layer) - bottom-up
- Edge: Frecce causali con direzione (forward = layer aumenta)
"""

from collections import defaultdict
from typing import List, Optional, Tuple, Dict
import math
import html

import torch
from IPython.display import SVG

# Import base classes from original
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))
from graph_visualization import Feature, Supernode, InterventionGraph


def calculate_node_positions_FIXED(nodes: List[List['Supernode']]):
    """
    🔥 VERSIONE CORRETTA: Usa layer e position REALI dalle Feature!
    
    Layout:
    - Asse X: Token position (da Feature.pos)
    - Asse Y: Layer (da Feature.layer) - bottom-up
    
    Returns:
        node_data: Dict[node_name, {x, y, node, layer, pos}]
        layer_range: (min_layer, max_layer)
        pos_range: (min_pos, max_pos)
    """
    container_width = 1200  # Più largo per accomodare più positions
    container_height = 1600   # Più alto per più layers (era 800)
    node_width = 80
    node_height = 30
    
    # Spacing tra elementi
    x_spacing = 100  # Spazio tra token positions
    y_spacing = 30   # Spazio tra layers (ridotto da 50 a 30)
    
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
    
    # Se nessuna feature ha layer/pos, fallback a layout originale
    if min_layer == float('inf'):
        print("WARNING: Nessuna feature con layer/pos, usando layout arbitrario")
        return calculate_node_positions_ORIGINAL(nodes)
    
    print(f"INFO: Layout range: layers {min_layer}-{max_layer}, positions {min_pos}-{max_pos}")
    
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
            # Position basata sull'ordine (semplificato)
            pos_key = len(nodes_by_layer_pos) % 3  # Spread across first few positions
            nodes_by_layer_pos[(0, pos_key)].append(node)
    
    # Calcola posizioni nodi
    node_data = {}
    base_x = 100  # Margine sinistro
    base_y = container_height - 150  # Margine basso
    
    for (layer, pos), node_list in nodes_by_layer_pos.items():
        # Posizione base per questo (layer, pos)
        x_base = base_x + pos * x_spacing
        y_base = base_y - layer * y_spacing  # Layer 0 in basso, layer alto in alto
        
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


def calculate_node_positions_ORIGINAL(nodes: List[List['Supernode']]):
    """Fallback al layout originale se non ci sono Feature"""
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
                'layer': 0,
                'pos': 0
            }
    
    return node_data, (0, len(nodes)-1), (0, 0)


def get_node_center(node_data, node_name):
    """Get center coordinates of a node"""
    node = node_data.get(node_name)
    if not node:
        return {'x': 0, 'y': 0}
    return {
        'x': node['x'] + 40,  # Center of node (80px wide)
        'y': node['y'] + 15   # Center of node (30px tall)
    }


def create_connection_svg(node_data, connections):
    """Generate SVG elements for all connections with causal direction"""
    svg_parts = []
    
    for conn in connections:
        from_center = get_node_center(node_data, conn['from'])
        to_center = get_node_center(node_data, conn['to'])
        
        if from_center['x'] == 0 or to_center['x'] == 0:
            continue
        
        # Determina direzione causale (forward = layer aumenta)
        from_node_data = node_data.get(conn['from'])
        to_node_data = node_data.get(conn['to'])
        
        is_forward = False
        if from_node_data and to_node_data:
            from_layer = from_node_data.get('layer', 0)
            to_layer = to_node_data.get('layer', 0)
            is_forward = to_layer > from_layer
        
        # Colore basato su direzione
        if conn.get('replacement'):
            stroke_color = "#D2691E"
            stroke_width = "4"
        elif is_forward:
            stroke_color = "#4169E1"  # Blu per forward causality
            stroke_width = "2.5"
        else:
            stroke_color = "#DC143C"  # Rosso per backward/lateral
            stroke_width = "2"
        
        # Line
        svg_parts.append(f'<line x1="{from_center["x"]}" y1="{from_center["y"]}" '
                        f'x2="{to_center["x"]}" y2="{to_center["y"]}" '
                        f'stroke="{stroke_color}" stroke-width="{stroke_width}" '
                        f'opacity="0.6"/>')
        
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
                           f'fill="{stroke_color}" opacity="0.6"/>')
    
    return '\n'.join(svg_parts)


def create_nodes_svg(node_data):
    """Generate SVG elements for all nodes with layer info"""
    svg_parts = []
    
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
        
        # Colore basato su layer
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
        else:
            # Gradiente di colore basato su layer
            layer_hue = (layer * 30) % 360
            fill_color = f"hsl({layer_hue}, 70%, 85%)"
            text_color = "#333"
            stroke_color = "#999"
        
        # Node rectangle
        svg_parts.append(f'<rect x="{x}" y="{y}" width="80" height="30" '
                        f'fill="{fill_color}" stroke="{stroke_color}" stroke-width="2" rx="6"/>')
        
        # Node text
        text_x = x + 40
        text_y = y + 20
        escaped_name = html.escape(name)
        # Truncate se troppo lungo
        display_name = escaped_name if len(escaped_name) <= 12 else escaped_name[:10] + '...'
        svg_parts.append(f'<text x="{text_x}" y="{text_y}" text-anchor="middle" '
                        f'fill="{text_color}" font-family="Arial, sans-serif" font-size="10" font-weight="bold">{display_name}</text>')
        
        # Layer badge
        if layer > 0:
            badge_x = x - 8
            badge_y = y - 8
            svg_parts.append(f'<circle cx="{badge_x}" cy="{badge_y}" r="10" '
                           f'fill="white" stroke="#666" stroke-width="1"/>')
            svg_parts.append(f'<text x="{badge_x}" y="{badge_y + 4}" text-anchor="middle" '
                           f'fill="#666" font-family="Arial, sans-serif" font-size="8">{layer}</text>')
        
        # Activation percentage
        if node.activation is not None:
            activation_pct = round(node.activation * 100)
            label_x = x + 75
            label_y = y - 5
            svg_parts.append(f'<text x="{label_x}" y="{label_y}" text-anchor="end" '
                           f'fill="#8B4513" font-family="Arial, sans-serif" font-size="9">{activation_pct}%</text>')
    
    return '\n'.join(svg_parts)


def build_connections_data(nodes: List[List['Supernode']]):
    """Build connection data from node relationships"""
    connections = []
    
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
    
    replacement_nodes = set()
    for node in all_nodes:
        if node.replacement_node:
            replacement_nodes.add(node.replacement_node.name)
    
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


def create_graph_visualization_FIXED(intervention_graph: InterventionGraph, 
                                     top_outputs: List[Tuple[str, float]]):
    """
    🔥 VERSIONE CORRETTA con layout Layer × Position
    """
    nodes = intervention_graph.ordered_nodes
    prompt = intervention_graph.prompt
    
    # Calcola posizioni CON layer/pos reali
    node_data, layer_range, pos_range = calculate_node_positions_FIXED(nodes)
    
    # Build connections
    connections = build_connections_data(nodes)
    
    # Generate SVG
    connections_svg = create_connection_svg(node_data, connections)
    nodes_svg = create_nodes_svg(node_data)
    
    # Grid lines per layers
    grid_svg_parts = []
    min_layer, max_layer = layer_range
    base_y = 1450  # Coordina con calculate_node_positions_FIXED (container_height - 150)
    y_spacing = 30  # Deve essere uguale a quello in calculate_node_positions_FIXED
    
    for layer in range(min_layer, max_layer + 1):
        y = base_y - layer * y_spacing
        grid_svg_parts.append(f'<line x1="50" y1="{y}" x2="1150" y2="{y}" '
                             f'stroke="#ddd" stroke-width="0.5" stroke-dasharray="5,5"/>')
        grid_svg_parts.append(f'<text x="30" y="{y + 5}" fill="#999" '
                             f'font-family="monospace" font-size="10">L{layer}</text>')
    
    grid_svg = '\n'.join(grid_svg_parts)
    
    # Token position markers
    min_pos, max_pos = pos_range
    base_x = 100
    x_spacing = 100
    token_markers = []
    
    for pos in range(min_pos, min(max_pos + 1, 15)):  # Limit to 15 positions
        x = base_x + pos * x_spacing
        token_markers.append(f'<text x="{x}" y="1530" fill="#666" text-anchor="middle" '
                           f'font-family="monospace" font-size="10">T{pos}</text>')
    
    tokens_svg = '\n'.join(token_markers)
    
    # Legenda
    legend_svg = '''
    <g transform="translate(950, 50)">
        <text x="0" y="0" fill="#666" font-size="12" font-weight="bold">Legenda:</text>
        <line x1="0" y1="15" x2="40" y2="15" stroke="#4169E1" stroke-width="2.5"/>
        <text x="45" y="20" fill="#666" font-size="10">Forward (↑layer)</text>
        <line x1="0" y1="35" x2="40" y2="35" stroke="#DC143C" stroke-width="2"/>
        <text x="45" y="40" fill="#666" font-size="10">Backward/Lateral</text>
    </g>
    '''
    
    # Output items
    output_items_svg = []
    current_x = 950
    current_y = 100
    
    for i, (text, percentage) in enumerate(top_outputs[:4]):  # Show top 4
        display_text = text if text else "(empty)"
        escaped_display_text = html.escape(display_text)
        percentage_text = f"{round(percentage * 100)}%"
        
        output_items_svg.append(f'<text x="{current_x}" y="{current_y + i*20}" fill="#333" '
                               f'font-family="Arial, sans-serif" font-size="10">'
                               f'{escaped_display_text}: <tspan fill="#666">{percentage_text}</tspan></text>')
    
    outputs_svg = '\n'.join(output_items_svg)
    
    # SVG completo
    svg_content = f'''<svg width="1300" height="1650" xmlns="http://www.w3.org/2000/svg">
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
    
    return SVG(svg_content)
