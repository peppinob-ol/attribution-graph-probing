# Metriche Causali: Guida Completa

## 🧮 Introduzione: Perché Metriche Causali?

Le metriche semantiche tradizionali (cosine similarity, peak tokens) descrivono **cosa** fa una feature, ma non **come** influenza l'output. Le metriche causali aggiungono la dimensione della **causalità computazionale**.

### Metafora: Sistema Idraulico
Immagina il modello come un **sistema idraulico**:
- **Feature** = valvole che regolano il flusso
- **Edge causali** = tubi che connettono le valvole
- **Logit** = serbatoio finale dove arriva l'acqua

Le metriche semantiche dicono **quanto è aperta ogni valvola** (attivazione).  
Le metriche causali dicono **quanto flusso passa da una valvola all'altra** (causalità).

---

## 📊 Metriche Causali Principali

### 1. Node Influence (Influenza sul Logit)

**Definizione**: Quanto una feature contribuisce al logit attraverso propagazione backward.

#### Algoritmo
```python
def compute_node_influence(
    adjacency_matrix: torch.Tensor,
    n_features: int,
    n_logits: int,
    normalize: bool = True
) -> torch.Tensor:
    """
    Calcola node_influence per ogni feature propagando backward dai logits
    
    Algoritmo:
    1. Inizializza influence[logit] = 1.0 per ogni logit
    2. Propaga backward: influence[i] = sum_j (adj[j, i] * influence[j])
    3. Itera fino a convergenza (max 10 iterazioni)
    4. Ritorna influence delle feature (primi n_features nodi)
    """
    n_nodes = adjacency_matrix.shape[0]
    
    # Normalizza adjacency matrix per righe (per stabilità)
    if normalize:
        row_sums = adjacency_matrix.sum(dim=1, keepdim=True)
        row_sums[row_sums == 0] = 1  # Evita divisione per zero
        adj_normalized = adjacency_matrix / row_sums
    else:
        adj_normalized = adjacency_matrix
    
    # Logit nodes sono gli ultimi n_logits nodi
    logit_start = n_nodes - n_logits
    
    # Influence iniziale: 1.0 per ogni logit
    influence = torch.zeros(n_nodes)
    influence[logit_start:] = 1.0
    
    # Propaga backward attraverso il grafo
    for iteration in range(10):
        # influence[i] = sum_j (adj[j, i] * influence[j])
        new_influence = adj_normalized.T @ influence
        
        # Mantieni fisso l'influence dei logits
        new_influence[logit_start:] = 1.0
        
        # Check convergenza
        if torch.allclose(influence, new_influence, atol=1e-6):
            print(f"Convergenza raggiunta in {iteration+1} iterazioni")
            break
        
        influence = new_influence
    
    # Ritorna solo influence delle feature
    return influence[:n_features]
```

#### Esempio Concreto

```
Adjacency Matrix (semplificato):
         F0   F1   F2   L0   L1
    F0 [ 0    0.1  0.2  0    0  ]
    F1 [ 0    0    0.3  0.1  0  ]
    F2 [ 0    0    0    0.2  0.3]
    L0 [ 0    0    0    0    0  ]
    L1 [ 0    0    0    0    0  ]

Inizializzazione:
influence = [0, 0, 0, 1.0, 1.0]

Iterazione 1:
influence[F0] = adj[F1, F0] * infl[F1] + adj[F2, F0] * infl[F2] + ... = 0
influence[F1] = adj[L0, F1] * infl[L0] + ... = 0.1 * 1.0 = 0.1
influence[F2] = adj[L0, F2] * infl[L0] + adj[L1, F2] * infl[L1] = 0.2*1.0 + 0.3*1.0 = 0.5
influence = [0, 0.1, 0.5, 1.0, 1.0]

Iterazione 2:
influence[F0] = adj[F1, F0] * infl[F1] + adj[F2, F0] * infl[F2] = 0.1*0.1 + 0.2*0.5 = 0.11
influence[F1] = adj[F2, F1] * infl[F2] + adj[L0, F1] * infl[L0] = 0.3*0.5 + 0.1*1.0 = 0.25
influence[F2] = 0.5 (no changes)
influence = [0.11, 0.25, 0.5, 1.0, 1.0]

... (convergenza dopo ~5 iterazioni)

Final:
influence = [0.13, 0.28, 0.52, 1.0, 1.0]
```

**Interpretazione**:
- **F2** ha node_influence più alto (0.52) → impatto forte sul logit
- **F1** ha node_influence medio (0.28) → impatto moderato
- **F0** ha node_influence basso (0.13) → impatto debole

#### Uso nel Sistema di Labelling

1. **Seed Selection**: Ordina feature per `node_influence` DESC
   - Feature con alta influence diventano seed primari
   - Rappresentano i "leader" causali del circuito

2. **Compatibilità Causale**: Feature con influence simili tendono a collaborare
   - Usato nel calcolo di `consistency_compat` in `compute_narrative_compatibility()`

3. **Clustering Residui**: Tier causale (HIGH/MED/LOW) basato su node_influence
   - Permette di distinguere feature computazionalmente importanti

---

### 2. Causal In-Degree (Genitori Causali)

**Definizione**: Numero di feature che hanno edge causale **entrante** verso la feature corrente.

```python
def compute_causal_in_degree(feature_idx: int, adjacency_matrix: torch.Tensor, tau_edge: float = 0.01) -> int:
    """
    In-degree: numero di feature j con adj[feature_idx, j] > tau_edge
    
    Interpretazione: quante feature "parlano" a questa feature
    """
    parents = []
    for j in range(adjacency_matrix.shape[1]):
        if adjacency_matrix[feature_idx, j].item() > tau_edge:
            parents.append(j)
    
    return len(parents)
```

#### Esempio

```
Feature 20_15589:
  Genitori causali (edge > 0.01):
    19_7477 → 20_15589 (weight=0.15)
    18_8959 → 20_15589 (weight=0.12)
    17_1084 → 20_15589 (weight=0.09)
    16_25   → 20_15589 (weight=0.08)
    15_2107 → 20_15589 (weight=0.07)
    14_4649 → 20_15589 (weight=0.06)
    14_2268 → 20_15589 (weight=0.05)
    7_6861  → 20_15589 (weight=0.03)
  
  causal_in_degree = 8
```

**Interpretazione**:
- **Alta in-degree** (es. 8) → feature che **integra informazioni** da molte fonti
- **Bassa in-degree** (es. 1-2) → feature specializzata su pochi input specifici
- **Zero in-degree** → feature iniziale (nei layer bassi) o isolata

#### Uso nel Sistema

- **Top Parents**: Usati per costruire il pool di candidati durante crescita supernodo
- **Vicinato Causale**: Similarity di genitori usata in `compute_narrative_compatibility()` (Jaccard)

---

### 3. Causal Out-Degree (Figli Causali)

**Definizione**: Numero di feature che ricevono edge causale **uscente** dalla feature corrente.

```python
def compute_causal_out_degree(feature_idx: int, adjacency_matrix: torch.Tensor, tau_edge: float = 0.01) -> int:
    """
    Out-degree: numero di feature k con adj[k, feature_idx] > tau_edge
    
    Interpretazione: quante feature ricevono input da questa feature
    """
    children = []
    for k in range(adjacency_matrix.shape[0]):
        if adjacency_matrix[k, feature_idx].item() > tau_edge:
            children.append(k)
    
    return len(children)
```

#### Esempio

```
Feature 20_15589:
  Figli causali (edge > 0.01):
    20_15589 → 21_5943  (weight=0.21)
    20_15589 → 22_3064  (weight=0.18)
    20_15589 → 23_1529  (weight=0.16)
    20_15589 → 24_13277 (weight=0.14)
    20_15589 → 25_16302 (weight=0.12)
    ... (18 altri figli)
  
  causal_out_degree = 23
```

**Interpretazione**:
- **Alta out-degree** (es. 23) → feature **hub causale** che influenza molti nodi
- **Bassa out-degree** (es. 1-2) → feature specializzata su pochi output
- **Out-degree verso logit** → feature finale che parla direttamente all'output ("Say Austin")

#### Uso nel Sistema

- **Top Children**: Identificano feature downstream influenzate
- **Hub Detection**: Feature con out-degree >> in-degree sono hub di diffusione

---

### 4. Top Parents & Top Children (Vicinato Causale)

**Definizione**: Liste dei top-k genitori/figli ordinati per peso edge.

```python
def compute_top_k_neighbors(
    feature_idx: int,
    adjacency_matrix: torch.Tensor,
    tau_edge: float = 0.01,
    top_k: int = 5,
    direction: str = 'parents'
) -> List[Tuple[str, float]]:
    """
    Estrae top-k vicini causali ordinati per peso edge
    
    direction='parents': feature j con adj[feature_idx, j] > tau_edge
    direction='children': feature k con adj[k, feature_idx] > tau_edge
    """
    neighbors = []
    
    if direction == 'parents':
        for j in range(adjacency_matrix.shape[1]):
            weight = adjacency_matrix[feature_idx, j].item()
            if weight > tau_edge:
                neighbors.append((j, weight))
    else:  # children
        for k in range(adjacency_matrix.shape[0]):
            weight = adjacency_matrix[k, feature_idx].item()
            if weight > tau_edge:
                neighbors.append((k, weight))
    
    # Ordina per peso decrescente e prendi top-k
    neighbors.sort(key=lambda x: x[1], reverse=True)
    
    return neighbors[:top_k]
```

#### Esempio

```json
{
  "20_15589": {
    "top_parents": [
      ["19_7477", 0.1523],
      ["18_8959", 0.1245],
      ["17_1084", 0.0987],
      ["16_25", 0.0856],
      ["15_2107", 0.0734]
    ],
    "top_children": [
      ["21_5943", 0.2134],
      ["22_3064", 0.1876],
      ["23_1529", 0.1654],
      ["24_13277", 0.1432],
      ["25_16302", 0.1211]
    ]
  }
}
```

**Interpretazione**:
- **Top Parents**: Le 5 feature che **influenzano maggiormente** 20_15589
- **Top Children**: Le 5 feature **maggiormente influenzate** da 20_15589

#### Uso nel Sistema

1. **Pool Candidati**: Durante crescita supernodo, `top_parents` dei membri attuali diventano candidati
   ```python
   for member_key in cicciotto['members']:
       for parent_key, weight in causal_metrics[member_key]['top_parents']:
           candidates.append(parent_key)
   ```

2. **Jaccard Similarity**: Overlap tra vicinati causali indica compatibilità
   ```python
   seed_neighbors = set(top_parents(seed) + top_children(seed))
   cand_neighbors = set(top_parents(cand) + top_children(cand))
   jaccard = len(seed_neighbors & cand_neighbors) / len(seed_neighbors | cand_neighbors)
   ```

3. **Bootstrap 2-Hop**: Aggiungi anche genitori dei genitori
   ```python
   for parent_key in top_parents(member):
       for grandparent_key, weight in top_parents(parent_key):
           second_hop_candidates.append((grandparent_key, weight * 0.5))
   ```

---

### 5. Position at Final (Feature Finale)

**Definizione**: Boolean che indica se la feature è alla posizione finale del prompt.

```python
def detect_position_at_final(feature_key: str, graph_data: Dict) -> bool:
    """
    Verifica se feature è alla posizione massima del prompt
    
    Utile per identificare feature "Say X" che parlano direttamente al logit
    """
    # Trova posizione di questa feature
    for layer, pos, feat_idx in graph_data['active_features']:
        if f"{layer.item()}_{feat_idx.item()}" == feature_key:
            feature_position = pos.item()
            break
    
    # Trova posizione massima nel prompt
    max_position = max(pos.item() for _, pos, _ in graph_data['active_features'])
    
    return feature_position == max_position
```

#### Esempio

```json
{
  "24_13277": {
    "layer": 24,
    "position": 15,
    "position_at_final": true
  },
  "20_15589": {
    "layer": 20,
    "position": 15,
    "position_at_final": true
  },
  "3_3205": {
    "layer": 3,
    "position": 2,
    "position_at_final": false
  }
}
```

**Interpretazione**:
- **position_at_final=true**: Feature che processa l'**ultimo token** del prompt
  - Tipicamente hanno edge diretta verso logit
  - Candidati per "Say Austin" seed
- **position_at_final=false**: Feature che processano token intermedi

#### Uso nel Sistema

1. **Find Say Austin Seed**: Filtra solo feature con `position_at_final=true`
   ```python
   final_position_features = [f for f in features if f['position_at_final']]
   ```

2. **Position Proximity**: Parte della compatibilità causale (15%)
   ```python
   pos_distance = abs(seed.position - candidate.position)
   position_compat = max(0, 1 - pos_distance / 5)
   ```

---

### 6. Edge Density (Connettività Causale)

**Definizione**: Frazione di edge forti all'interno di un insieme di feature.

```python
def compute_edge_density(
    feature_keys: List[str],
    graph_data: Dict,
    feature_to_idx: Dict[str, int],
    tau_edge: float = 0.01
) -> float:
    """
    Edge density = (numero edge forti) / (numero possibili edge)
    
    Misura quanto un gruppo di feature è causalmente connesso internamente
    """
    if len(feature_keys) < 2:
        return 0.0
    
    # Filtra solo feature presenti nel grafo
    valid_features = [fkey for fkey in feature_keys if fkey in feature_to_idx]
    
    if len(valid_features) < 2:
        return 0.0
    
    # Converti a indici
    indices = [feature_to_idx[fkey] for fkey in valid_features]
    
    # Estrai sub-matrice
    adjacency_matrix = graph_data['adjacency_matrix']
    
    # Conta edge forti
    strong_edges = 0
    possible_edges = 0
    
    for i in indices:
        for j in indices:
            if i != j:
                possible_edges += 1
                if adjacency_matrix[i, j].item() > tau_edge:
                    strong_edges += 1
    
    edge_density = strong_edges / possible_edges if possible_edges > 0 else 0.0
    
    return edge_density
```

#### Esempio Concreto

```
Supernodo CICCIOTTO_2 (5 membri):
  Members: [24_13277, 23_1529, 22_3064, 21_11630, 22_11718]
  
  Edge forti (> 0.01):
    24_13277 → 23_1529 (0.15)
    23_1529  → 22_3064 (0.12)
    22_3064  → 21_11630 (0.08)
    21_11630 → 22_11718 (0.06)
    24_13277 → 22_3064 (0.05)  # salto
    23_1529  → 21_11630 (0.03)  # salto
  
  Total strong edges: 6
  Possible edges: 5*4 = 20 (tutti i possibili i→j con i≠j)
  
  Edge density = 6/20 = 0.30
```

**Interpretazione**:
- **Density alta** (>0.4): Supernodo **fortemente connesso** (circuito causale coeso)
- **Density media** (0.2-0.4): Supernodo **moderatamente connesso** (catena causale)
- **Density bassa** (<0.2): Cluster **debolmente connesso** (group semantico, non causale)

#### Uso nel Sistema

1. **Coherence del Supernodo** (30% del peso):
   ```python
   causal_density = compute_edge_density(cicciotto['members'], graph_data, ...)
   total_coherence = ... + causal_density * 0.30
   ```

2. **Differenza Cicciotto vs Cluster Computazionale**:
   - Cicciotti: edge_density tipicamente 0.25-0.45 (crescita causale)
   - Cluster computazionali: edge_density tipicamente 0.10-0.25 (clustering semantico)

---

## 🎯 Metriche Aggregate per Supernodi

### Causal Connectivity (per Cluster Computazionali)

```python
cluster_info = {
    'members': [...],
    'causal_connectivity': 0.25,  # Edge density interno
    'avg_node_influence': 0.023,  # Media node_influence membri
    'causal_tier': 'MED'          # Classificazione causale
}
```

**Interpretazione**:
- `causal_connectivity`: Quanto i membri sono connessi tra loro
- `avg_node_influence`: Quanto il cluster influenza il logit
- `causal_tier`: Classificazione HIGH/MED/LOW basata su node_influence

---

## 🔍 Comparazione: Semantico vs Causale

### Feature "3_3205" (Contextual Specialist)

```json
{
  "3_3205": {
    "layer": 3,
    "most_common_peak": "Texas",
    
    "SEMANTICA": {
      "mean_consistency": 0.32,
      "max_affinity": 0.89,
      "conditional_consistency": 0.45
    },
    
    "CAUSALE": {
      "node_influence": 0.015,
      "causal_in_degree": 2,
      "causal_out_degree": 8,
      "top_parents": [
        ["2_8734", 0.08],
        ["1_14137", 0.05]
      ],
      "top_children": [
        ["4_14857", 0.12],
        ["5_7837", 0.09],
        ["6_4662", 0.07],
        ...
      ]
    }
  }
}
```

**Interpretazione Integrata**:
- **Semantica**: Bassa generalizzabilità (0.32) ma alta specializzazione (0.89) su "Texas"
- **Causale**: Bassa influence globale (0.015), ma hub locale (8 figli) → propaga info "Texas" a layer superiori
- **Ruolo**: **Detector specializzato** su "Texas" che alimenta feature downstream

---

## 📈 Soglie Causali nel Sistema

| Parametro | Valore | Uso |
|-----------|--------|-----|
| `tau_edge` | 0.01 | Soglia minima per considerare edge causale "forte" |
| `tau_edge_strong` | 0.05 | Soglia per edge "molto forte" (boost in compatibilità) |
| `tau_edge_bootstrap` | 0.03 | Soglia più permissiva per crescita bootstrap |
| `tau_node_high` | 0.1 | Node influence alta (tier HIGH) |
| `tau_node_med` | 0.01 | Node influence media (tier MED) |

**Come Tuning**:
1. `tau_edge` più basso → più edge considerati → supernodi più grandi
2. `tau_edge` più alto → meno edge considerati → supernodi più compatti
3. Valori attuali (0.01-0.05) sono **empiricamente ottimali** per Gemma-2B

---

## 🎓 Conclusioni

### Perché le Metriche Causali sono Fondamentali

1. **Distinguono Circuiti da Gruppi Casuali**
   - Semantica: "queste feature parlano tutte di Texas"
   - Causale: "queste feature collaborano in sequenza per produrre 'Texas'"

2. **Guidano la Crescita Organica**
   - Crescita backward seguendo edge causali → supernodi che rispecchiano circuiti reali
   - Alternativa: clustering semantico → gruppi artificiosi

3. **Quantificano l'Importanza Computazionale**
   - Node influence misura l'impatto sul logit
   - Edge density misura la coesione del circuito

4. **Permettono Interpretabilità Meccanicistica**
   - Non solo "cosa" fa il modello, ma "come" lo fa
   - Supernodi con alta edge density = circuiti interpretabili meccanicisticamente

### Sviluppi Futuri

- **Causal Attention Flow**: Tracciare edge causali attraverso i layer con attention weights
- **Multi-Hop Influence**: Estendere node_influence a percorsi causali multi-hop
- **Intervention-Based Metrics**: Misurare influence tramite ablation causale (più robusto)


