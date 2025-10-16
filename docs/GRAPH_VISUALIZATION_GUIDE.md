# Guida alla Visualizzazione dei Grafi di Intervento

## Panoramica

Il modulo `graph_visualization.py` fornisce strumenti per visualizzare **grafi di intervento** (Attribution Graphs) utilizzati nell'analisi dei circuiti neurali dei modelli linguistici. Questa visualizzazione è ispirata al lavoro "Circuit Tracing" di Anthropic.

## Concetti Fondamentali

### 1. Feature
Una `Feature` è una tupla che identifica una specifica attivazione nel modello:
```python
Feature = namedtuple('Feature', ['layer', 'pos', 'feature_idx'])
# Esempio: Feature(layer=23, pos=10, feature_idx=12237)
```

### 2. Supernode
Un `Supernode` rappresenta un gruppo di features che hanno un ruolo semantico comune:
```python
supernode = Supernode(
    name='Texas',
    features=[Feature(20, 9, 15589), Feature(19, 9, 7477)],
    children=[austin_node],  # Collegamenti ad altri supernodes
    intervention=None,        # Intervento applicato (es. '-2x', '+2x')
    replacement_node=None     # Supernode sostitutivo
)
```

**Attributi chiave:**
- `activation`: frazione dell'attivazione corrente rispetto al default (0.0-1.0+)
- `default_activations`: attivazioni originali delle features
- `intervention`: descrizione dell'intervento (es. "-2x" = riduzione, "+2x" = amplificazione)
- `replacement_node`: nodo che sostituisce questo durante un intervento

### 3. InterventionGraph
Gestisce l'intero grafo di supernodes e tiene traccia dello stato:
```python
graph = InterventionGraph(
    ordered_nodes=[[layer0_nodes], [layer1_nodes], [layer2_nodes]],
    prompt="Il prompt testuale"
)
```

## Workflow di Utilizzo

### Fase 1: Creazione della Struttura

```python
from graph_visualization import create_graph_visualization, Supernode, InterventionGraph, Feature

# 1. Definisci i supernodes (dal basso verso l'alto nel grafo)
say_austin_node = Supernode(
    name='Say Austin',
    features=[Feature(layer=23, pos=10, feature_idx=12237)]
)

texas_node = Supernode(
    name='Texas',
    features=[Feature(20, 9, 15589), Feature(19, 9, 7477)],
    children=[say_austin_node]  # Texas influenza "Say Austin"
)

state_node = Supernode(
    name='state',
    features=[Feature(6, 7, 4012)],
    children=[texas_node]  # "state" influenza "Texas"
)

# 2. Organizza i nodi in layers (dal basso = input, verso alto = output)
ordered_nodes = [
    [state_node],           # Layer 0: concetti base
    [texas_node],           # Layer 1: concetti intermedi
    [say_austin_node]       # Layer 2: output
]

# 3. Crea il grafo
graph = InterventionGraph(
    ordered_nodes=ordered_nodes,
    prompt="Fact: the capital of the state containing Dallas is"
)
```

### Fase 2: Inizializzazione con Attivazioni Reali

```python
# Ottieni attivazioni dal modello (esempio pseudocodice)
logits, activations = model.get_activations(prompt)

# Inizializza ogni nodo con le sue attivazioni di default
for node in [state_node, texas_node, say_austin_node]:
    if node.features:  # Solo se ha features
        graph.initialize_node(node, activations)

# Imposta le attivazioni correnti (inizialmente = 100% del default)
graph.set_node_activation_fractions(activations)
```

### Fase 3: Visualizzazione

```python
# Ottieni top logits per mostrare gli output del modello
top_outputs = [
    ("Austin", 0.41),
    ("Texas", 0.05),
    ("the", 0.06),
    # ...
]

# Crea la visualizzazione SVG
svg = create_graph_visualization(graph, top_outputs)
# In un notebook Jupyter, questo mostrerà automaticamente il grafo
```

## Esecuzione di Interventi

Gli interventi permettono di **manipolare le attivazioni** per testare ipotesi causali:

```python
# Definisci un intervento: riduci "Texas" a -2x del suo valore
interventions = [
    (texas_node, -2.0)  # Moltiplica attivazioni per -2
]

# Applica l'intervento sul modello
intervention_values = [
    (*feature, scaling_factor * default_act)
    for node, scaling_factor in interventions
    for feature, default_act in zip(node.features, node.default_activations)
]

new_logits, new_activations = model.feature_intervention(prompt, intervention_values)

# Aggiorna il grafo con le nuove attivazioni
graph.set_node_activation_fractions(new_activations)

# Marca il nodo con l'intervento applicato
texas_node.activation = None  # Nasconde la percentuale
texas_node.intervention = '-2x'  # Mostra il badge intervento

# Visualizza il risultato
new_top_outputs = get_top_outputs(new_logits)
svg = create_graph_visualization(graph, new_top_outputs)
```

## Sostituzione di Nodi (Replacement Nodes)

Per interventi più complessi, puoi **sostituire interi supernodes**:

```python
# Crea un nodo sostitutivo (es. "California" invece di "Texas")
california_node = Supernode(
    name='California',
    features=[Feature(19, 10, 9209)],
    intervention='+2x',
    children=[say_sacramento_node]
)

# Configura la sostituzione
texas_node.replacement_node = california_node
say_austin_node.replacement_node = say_sacramento_node

# Il grafo mostrerà i nodi sostitutivi in arancione sopra gli originali
```

## Interpretazione della Visualizzazione

### Elementi Visivi

1. **Nodi (rettangoli)**:
   - Grigio normale: attivazione > 25%
   - Grigio chiaro: attivazione ≤ 25% o intervento negativo
   - Arancione (cornice): nodo sostitutivo

2. **Etichette attivazione** (angolo superiore sinistro):
   - Badge bianco con percentuale: mostra quanto il nodo è attivo
   - 100% = attivazione normale
   - < 25% = nodo quasi spento

3. **Badge intervento** (angolo superiore sinistro):
   - Badge arancione: mostra l'intervento applicato
   - "-2x" = riduzione, "+2x" = amplificazione

4. **Connessioni**:
   - Linee marroni: connessioni normali
   - Linee arancioni più spesse: connessioni da nodi sostitutivi

5. **Sezione Prompt**: mostra il prompt in input

6. **Sezione Top Outputs**: mostra i top-k token predetti dal modello con probabilità

### Esempio di Interpretazione

```
[State] 100% → [Texas] -2x → [Say Austin] 0%
                            ↑
            [California] +2x → [Say Sacramento] 27%
```

**Lettura**: 
- Il nodo "Texas" è stato intervento con -2x (ridotto fortemente)
- Di conseguenza "Say Austin" si è spento (0%)
- Il nodo sostitutivo "California" (+2x) ha attivato "Say Sacramento" (27%)
- Questo dimostra che il modello usa questi circuiti per il ragionamento geografico

## Caso d'Uso Tipico: Validazione di Circuiti

1. **Ipotesi**: "Il nodo 'Texas' causa l'output 'Austin'"
2. **Test**: Spegni il nodo "Texas" con intervento -2x
3. **Risultato atteso**: "Austin" scompare dai top outputs
4. **Conclusione**: Se l'output cambia come previsto, l'ipotesi è confermata

## Limitazioni

- Le visualizzazioni sono statiche (SVG)
- Supporta solo interventi di scaling moltiplicativo
- La posizione dei nodi è calcolata automaticamente (non personalizzabile)
- Funziona meglio con grafi di 3-4 layer e 5-10 nodi per layer

## Integrazione con Neuronpedia

Il formato è compatibile con i grafi di Neuronpedia. Puoi estrarre supernodes da URL:

```python
from utils import extract_supernode_features

url = "https://www.neuronpedia.org/gemma-2-2b/graph?slug=..."
supernodes = extract_supernode_features(url)
# Restituisce dict: {'nome_supernode': [Feature, Feature, ...]}
```

## Prossimi Passi

1. Esplora i notebook in `demos/` per esempi completi
2. Vedi `QUICK_REFERENCE.md` per comandi rapidi
3. Consulta `DATA_FLOW.md` per capire il flusso dati completo



