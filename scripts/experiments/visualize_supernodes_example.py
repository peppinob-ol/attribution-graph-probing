"""
Esempio di visualizzazione dei supernodes finali del progetto.

Questo script mostra come:
1. Caricare i supernodes finali dal file JSON
2. Creare una visualizzazione interattiva del grafo
3. (Opzionale) Simulare interventi senza modello reale

NOTA: Questo è un esempio semplificato per capire la visualizzazione.
Per l'analisi completa con un modello reale, vedi i notebook in demos/
"""

import json
from collections import namedtuple
from pathlib import Path

# Importa le classi di visualizzazione
import sys
sys.path.append(str(Path(__file__).parent.parent))
from scripts.visualization.graph_visualization import (
    create_graph_visualization,
    Supernode,
    InterventionGraph,
    Feature
)

def load_supernodes(json_path='output/final_anthropological_optimized.json'):
    """Carica i supernodes dal file JSON."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def create_simple_graph_example():
    """
    Crea un grafo di esempio semplice per capire la visualizzazione.
    
    Esempio: "Il contrario di 'piccolo' è '___'" → "grande"
    """
    
    # 1. Definisci i supernodes (dal livello basso verso alto)
    # NOTA: In un caso reale, le features verrebbero da un'analisi del modello
    
    # Output layer
    say_grande_node = Supernode(
        name='Say "grande"',
        features=[Feature(layer=23, pos=10, feature_idx=8683)],
        children=[]
    )
    
    # Intermediate layer: concetti
    piccolo_node = Supernode(
        name='piccolo',
        features=[
            Feature(layer=15, pos=5, feature_idx=5617),
            Feature(layer=14, pos=5, feature_idx=11360)
        ],
        children=[say_grande_node]
    )
    
    contrario_node = Supernode(
        name='contrario/opposto',
        features=[Feature(layer=4, pos=2, feature_idx=95)],
        children=[say_grande_node]
    )
    
    # Input layer: embedding
    emb_piccolo = Supernode(
        name='Emb: "piccolo"',
        features=None,  # Gli embeddings non hanno features SAE
        children=[piccolo_node]
    )
    
    emb_contrario = Supernode(
        name='Emb: "contrario"',
        features=None,
        children=[contrario_node]
    )
    
    # 2. Organizza in layers
    ordered_nodes = [
        [emb_contrario, emb_piccolo],        # Layer 0: embeddings
        [contrario_node, piccolo_node],      # Layer 1: concetti
        [say_grande_node]                     # Layer 2: output
    ]
    
    # 3. Crea il grafo
    prompt = 'Il contrario di "piccolo" è "'
    graph = InterventionGraph(ordered_nodes=ordered_nodes, prompt=prompt)
    
    # 4. Simula attivazioni (in un caso reale, vengono dal modello)
    # Per semplicità, usiamo valori fittizi
    mock_activations = {
        Feature(4, 2, 95): 1.0,
        Feature(15, 5, 5617): 0.95,
        Feature(14, 5, 11360): 0.98,
        Feature(23, 10, 8683): 1.0
    }
    
    # Inizializza nodi con attivazioni mock
    for node in [contrario_node, piccolo_node, say_grande_node]:
        if node.features:
            graph.initialize_node(node, mock_activations)
    
    # Imposta le attivazioni correnti
    graph.set_node_activation_fractions(mock_activations)
    
    # 5. Simula top outputs
    top_outputs = [
        ("grande", 0.82),
        ("grosso", 0.07),
        (" grande", 0.02),
        ("enorme", 0.01),
        ("gigante", 0.01)
    ]
    
    return graph, top_outputs

def demonstrate_intervention():
    """
    Dimostra un intervento: cosa succede se "spegniamo" il concetto di "piccolo"?
    """
    
    # Crea il grafo base
    graph, base_outputs = create_simple_graph_example()
    
    print("=" * 60)
    print("VISUALIZZAZIONE BASE (nessun intervento)")
    print("=" * 60)
    svg = create_graph_visualization(graph, base_outputs)
    
    # In un notebook Jupyter, `svg` si visualizzerebbe automaticamente
    # In uno script, possiamo salvarlo
    print("\n📊 Grafo base creato. Top output: 'grande' (82%)")
    
    # Ora simula un intervento: spegni "piccolo"
    print("\n" + "=" * 60)
    print("INTERVENTO: Spegni il nodo 'piccolo' (-2x)")
    print("=" * 60)
    
    # Trova il nodo piccolo
    piccolo_node = None
    for layer in graph.ordered_nodes:
        for node in layer:
            if node.name == 'piccolo':
                piccolo_node = node
                break
    
    if piccolo_node:
        # Simula l'effetto dell'intervento
        piccolo_node.activation = None
        piccolo_node.intervention = '-2x'
        
        # Il nodo "Say grande" dovrebbe attivarsi di meno
        say_grande = None
        for layer in graph.ordered_nodes:
            for node in layer:
                if 'Say' in node.name:
                    say_grande = node
                    break
        
        if say_grande and say_grande.features:
            # Simula riduzione attivazione
            say_grande.activation = 0.30  # Ridotto dal 100%
        
        # Simula nuovi outputs (ipotetico)
        new_outputs = [
            ("il", 0.12),
            ("un", 0.08),
            ("grande", 0.07),  # Ora molto più basso!
            ("the", 0.05),
            ("altro", 0.04)
        ]
        
        svg_intervento = create_graph_visualization(graph, new_outputs)
        print("\n📊 Grafo con intervento creato.")
        print("📉 'grande' è sceso dal 82% al 7%!")
        print("✅ Questo conferma che il nodo 'piccolo' è causalmente importante.")
    
    print("\n" + "=" * 60)
    print("Per visualizzare i grafi SVG, usa un notebook Jupyter")
    print("oppure salva l'SVG e aprilo in un browser.")
    print("=" * 60)

def analyze_real_supernodes():
    """
    Analizza i supernodes reali del progetto (se disponibili).
    """
    json_path = Path('output/final_anthropological_optimized.json')
    
    if not json_path.exists():
        print(f"\n⚠️  File {json_path} non trovato.")
        print("Esegui prima la pipeline di analisi per generare i supernodes.")
        return
    
    data = load_supernodes(json_path)
    
    print("\n" + "=" * 60)
    print("ANALISI SUPERNODES REALI")
    print("=" * 60)
    
    # Mostra statistiche
    if 'supernodes' in data:
        supernodes = data['supernodes']
        print(f"\n📊 Numero totale di supernodes: {len(supernodes)}")
        
        # Analizza distribuzione per layer
        layer_counts = {}
        for sn in supernodes:
            if 'features' in sn:
                for feature in sn['features']:
                    layer = feature.get('layer', 'unknown')
                    layer_counts[layer] = layer_counts.get(layer, 0) + 1
        
        print(f"\n📈 Distribuzione features per layer:")
        for layer in sorted(layer_counts.keys()):
            print(f"   Layer {layer}: {layer_counts[layer]} features")
        
        # Mostra esempi di supernodes
        print(f"\n🔍 Primi 5 supernodes:")
        for i, sn in enumerate(supernodes[:5]):
            name = sn.get('name', 'unnamed')
            n_features = len(sn.get('features', []))
            print(f"   {i+1}. '{name}' ({n_features} features)")
    
    print("\n💡 Per visualizzare questi supernodes, dovrai:")
    print("   1. Caricare un modello compatibile")
    print("   2. Ottenere le attivazioni su un prompt")
    print("   3. Creare il grafo InterventionGraph")
    print("   4. Usare create_graph_visualization()")
    print("\n📖 Vedi docs/GRAPH_VISUALIZATION_GUIDE.md per dettagli")

def main():
    """Funzione principale."""
    print("\n" + "=" * 60)
    print("ESEMPIO DI VISUALIZZAZIONE SUPERNODES")
    print("=" * 60)
    
    print("\n1️⃣  Creazione grafo di esempio...")
    demonstrate_intervention()
    
    print("\n2️⃣  Analisi supernodes reali del progetto...")
    analyze_real_supernodes()
    
    print("\n" + "=" * 60)
    print("✅ Esempio completato!")
    print("=" * 60)
    print("\n📚 Prossimi passi:")
    print("   - Leggi docs/GRAPH_VISUALIZATION_GUIDE.md")
    print("   - Esplora i notebook in demos/ (se disponibili)")
    print("   - Usa QUICK_REFERENCE.md per comandi rapidi")

if __name__ == '__main__':
    main()



