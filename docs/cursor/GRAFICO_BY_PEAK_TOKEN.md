# Grafico Alternativo: Colorato per Peak Token

**Data**: 21 Ottobre 2025

## Nuovo Grafico Aggiunto

Aggiunto secondo grafico "🎨 Alternative View: Colored by Peak Token" subito dopo il primo grafico principale.

---

## Confronto con Primo Grafico

| Aspetto | Grafico 1 (Prompts) | Grafico 2 (Peak Tokens) |
|---------|---------------------|-------------------------|
| **Colori** | Per prompt testato | Per token di picco |
| **Asse X** | Features (ordine node_influence) | Features (ordine node_influence) |
| **Asse Y (sx)** | Activation (max_value) | Activation (max_value) |
| **Asse Y (dx)** | node_influence (linea rossa) | node_influence (linea rossa) |
| **Scopo** | Confrontare performance su diversi prompt | Vedere quali token attivano le features |
| **Dati** | `verify_full` (stessa fonte) | `verify_full` (stessa fonte) |

---

## Struttura del Secondo Grafico

### Pivot Table

```python
pivot_by_token = plot_data_top.pivot_table(
    index='feature_key',       # Righe = features
    columns='peak_token',      # Colonne = token di picco
    values='activation_max',   # Valori = activation
    aggfunc='max',             # Aggregazione: max
    fill_value=0
)
```

**Differenza chiave:**
- Primo grafico: `columns='prompt'`
- Secondo grafico: `columns='peak_token'`

### Palette Colori

```python
import plotly.express as px
colors = px.colors.qualitative.Set3
```

**Set3**: Palette con 12 colori distintivi, ideale per distinguere token diversi.

Se ci sono più di 12 token, i colori si ripetono:
```python
if len(pivot_by_token.columns) > len(colors):
    colors = colors * (len(pivot_by_token.columns) // len(colors) + 1)
```

---

## Informazioni Aggiuntive

### Info Box

```
📊 Token Analysis:
- Tokens unici con picco: X
- Features visualizzate: Y
- Ogni colore = diverso token dove la feature raggiunge il picco
```

### Expander: Token Più Frequenti

Mostra tabella con:
- `peak_token`: Nome del token
- `count`: Numero di volte che appare come picco
- `percentage`: % rispetto al totale

**Esempio:**
```
peak_token | count | percentage
-----------|-------|------------
Dallas     |  45   |  32.1%
Texas      |  28   |  20.0%
is         |  22   |  15.7%
...
```

---

## Caso d'Uso

### Quando Usare il Primo Grafico

**Domanda:** "Come si comporta la feature X sui diversi prompt?"

**Esempio:**
- Feature `0_32742` si attiva molto sul prompt "Dallas city" ma poco su "Austin city"
- Utile per confrontare **robustezza** delle features

### Quando Usare il Secondo Grafico

**Domanda:** "Su quale token la feature X raggiunge il picco?"

**Esempio:**
- Feature `0_32742` ha sempre picco sul token "Dallas"
- Feature `1_45678` ha picco su token diversi: "is", "Texas", "capital"
- Utile per capire **selettività** delle features

---

## Esempio Interpretazione

### Feature Specializzata

```
Grafico 2:
Feature 0_32742: 
  [████████ Dallas] (tutto un colore)
```

**Interpretazione:**
- Feature **altamente specializzata**
- Si attiva sempre sullo stesso token ("Dallas")
- Probabile feature "detector" di città specifiche

### Feature Generalista

```
Grafico 2:
Feature 1_45678:
  [█ is][██ Texas][█ capital][█ city]... (tanti colori)
```

**Interpretazione:**
- Feature **generalista**
- Si attiva su token diversi a seconda del contesto
- Probabile feature per concetti più astratti

---

## Implementazione

### Codice Chiave

```python
# Stesso ordine del primo grafico (per node_influence)
pivot_by_token = pivot_by_token.loc[[f for f in top_feats if f in pivot_by_token.index]]

# Barre colorate per token
for i, token in enumerate(pivot_by_token.columns):
    token_label = str(token) if token is not None else "[NULL]"
    
    fig2.add_trace(go.Bar(
        name=token_label,
        x=pivot_by_token.index,
        y=pivot_by_token[token],
        marker_color=colors[i % len(colors)],  # Colore distintivo
        hovertemplate=f'<b>Peak Token: {token_label}</b>...'
    ))

# Linea node_influence (identica al primo grafico)
fig2.add_trace(go.Scatter(
    name='Importance (node_influence)',
    x=pivot_by_token.index,
    y=importance_line_2,
    mode='lines+markers',
    line=dict(color='red', width=3),
    yaxis='y2'
))
```

---

## Note Tecniche

### Gestione Token NULL

```python
if token is None or pd.isna(token):
    token_label = "[NULL]"
else:
    token_label = str(token)
```

**Quando succede:**
- `values` array vuoto o solo BOS
- `max_idx` non valido
- Edge case nel parsing

### Ordinamento Features

```python
# Mantiene STESSO ordine del primo grafico
pivot_by_token = pivot_by_token.loc[[f for f in top_feats if f in pivot_by_token.index]]
```

**Importante:** 
- Features ordinate per `node_influence` (decrescente)
- Stesso ordine in entrambi i grafici
- Facilita confronto visivo

### Aggregazione Max

```python
aggfunc='max'
```

**Perché max?**
- Una feature può apparire più volte con stesso `peak_token` (su prompt diversi)
- Prendiamo il valore massimo di activation per quella combinazione

**Esempio:**
```
feature_key | peak_token | prompt          | activation_max
0_32742     | Dallas     | "Dallas city"   | 105.4
0_32742     | Dallas     | "Dallas Texas"  | 98.2
```

→ Nel pivot: `0_32742 × Dallas = max(105.4, 98.2) = 105.4`

---

## Confronto Visivo

### Grafico 1 (Prompts)

```
Features (ordinate per node_influence) →

     [Prompt1][Prompt2][Prompt3]...
F1:  [█████  ][███    ][████   ]
F2:  [███    ][█████  ][██     ]
F3:  [██████ ][████   ][█████  ]
...
```

**Colori:** Prompt1 = blu, Prompt2 = rosso, Prompt3 = verde, ...

### Grafico 2 (Peak Tokens)

```
Features (ordinate per node_influence) →

     [Dallas][Texas][is][capital]...
F1:  [█████ ][      ][  ][       ]  ← Solo "Dallas"
F2:  [      ][█████ ][██][       ]  ← "Texas" e "is"
F3:  [██    ][███   ][  ][████   ]  ← Distribuito
...
```

**Colori:** Dallas = blu, Texas = rosso, is = verde, capital = giallo, ...

---

## Benefici

### 1. Complementarità

- **Grafico 1**: Comportamento su diversi **input**
- **Grafico 2**: Selettività su diversi **token**
- Insieme forniscono visione completa

### 2. Pattern Recognition

- **Facilita identificazione** features specializzate vs generaliste
- **Pattern visivi** immediati (mono-colore vs multi-colore)
- **Frequenza token** subito visibile nella legenda

### 3. Analisi Qualitativa

- "Questa feature è un detector di città?" → Guarda Grafico 2
- "Questa feature è robusta ai cambi di prompt?" → Guarda Grafico 1
- "Quali token sono più informativi?" → Expander token frequenti

---

## Possibili Estensioni Future

### 1. Filtro per Token

Aggiungere checkbox per mostrare solo features con picco su token specifico:
```python
selected_token = st.selectbox("Filtra per peak_token", ["All", "Dallas", "Texas", ...])
```

### 2. Heatmap Token × Feature

Visualizzazione alternativa come heatmap:
```python
fig3 = px.imshow(pivot_by_token, color_continuous_scale='Blues')
```

### 3. Clustering per Similarità Token

Raggruppare features che hanno pattern simili di peak_token:
```python
from sklearn.cluster import KMeans
clusters = KMeans(n_clusters=5).fit(pivot_by_token)
```

---

## Conclusioni

✅ **Grafico aggiunto**: Visualizzazione complementare al primo  
✅ **Stessi dati**: Usa `verify_full`, completamente consistente  
✅ **Info aggiuntive**: Token analysis + frequenze  
✅ **Facile confronto**: Stesso ordinamento features  
✅ **Interattivo**: Hover mostra dettagli per ogni barra  

**Il secondo grafico arricchisce l'analisi mostrando una prospettiva diversa sugli stessi dati!** 🎨

