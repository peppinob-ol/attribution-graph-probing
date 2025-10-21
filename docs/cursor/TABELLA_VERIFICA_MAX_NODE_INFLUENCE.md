# Tabella Verifica: Gestione max(node_influence) per feature_key

**Data**: 21 Ottobre 2025

## Problema

Una stessa `feature_key` può apparire **più volte** nel CSV `graph_feature_static_metrics.csv` con:
- Diversi `ctx_idx` (posizioni del token nella sequenza)
- Diversi valori di `node_influence`
- Diversi token dove la feature si attiva

### Esempio: Feature `0_95475`

```
layer,feature,id,ctx_idx,token,activation,node_influence
0,4557881025,95475,2, capital,8.9375,0.001381
0,4557881025,95475,4, state,10.6875,0.001515
0,4557881025,95475,5, containing,5.4688,0.000835
0,4557881025,95475,6, Dallas,7.8750,0.001667  ← MAX!
```

**Feature_key**: `0_95475` (uguale in tutte le righe)  
**node_influence**: 4 valori diversi!

## Soluzione Implementata

Nella **Tabella di Verifica Dati** (sezione "📈 Main Chart: Importance vs Activation"):

1. ✅ **Selezioniamo `max(node_influence)`** per ogni `feature_key`
2. ✅ **Aggiungiamo colonna `csv_ctx_idx`** per vedere quale contesto ha il max
3. ✅ **Una sola riga per combinazione `feature_key × prompt`**

### Codice Implementato

```python
# Carica CSV completo
csv_full = pd.read_csv(csv_path, encoding='utf-8')
csv_full['feature_key'] = csv_full['layer'].astype(int).astype(str) + '_' + csv_full['id'].astype(int).astype(str)

# Per ogni feature_key, prendi max(node_influence) e il ctx_idx corrispondente
csv_max = csv_full.sort_values('node_influence').groupby('feature_key', as_index=False).last()
csv_max = csv_max[['feature_key', 'node_influence', 'ctx_idx']]
csv_max = csv_max.rename(columns={'ctx_idx': 'csv_ctx_idx'})

# Merge con dati JSON
verify_full = verify_df.merge(csv_max, on='feature_key', how='left')
```

## Statistiche dal CSV Reale

### Distribuzione Features per Numero di Contesti

```
Contesti | Features
---------|----------
1        | 201 (86%)
2        |  14 (6%)
3        |   6 (3%)
4        |   3 (1%)
5        |   2 (1%)
6        |   4 (2%)
7        |   4 (2%)
---------|----------
Totali   | 234
```

- **234 features uniche** (feature_key)
- **321 righe totali** nel CSV
- **33 features (14%)** hanno multipli contesti

### Esempi Reali

#### Feature `0_18753` (2 contesti)

```
ctx_idx | token | activation | node_influence
--------|-------|------------|---------------
   3    |  of   |   6.0000   |   0.001689
   7    |  is   |   6.0625   |   0.007613  ← MAX!
```

**Risultato nella tabella**: `node_influence=0.007613`, `csv_ctx_idx=7`

#### Feature `0_95475` (4 contesti)

```
ctx_idx | token      | activation | node_influence
--------|------------|------------|---------------
   2    |  capital   |   8.9375   |   0.001381
   4    |  state     |  10.6875   |   0.001515
   5    | containing |   5.4688   |   0.000835
   6    |  Dallas    |   7.8750   |   0.001667  ← MAX!
```

**Risultato nella tabella**: `node_influence=0.001667`, `csv_ctx_idx=6`

### Effetto sull'Aggregazione

**Prima dell'aggregazione** (tutte le righe CSV):
- Righe: 321
- Mean node_influence: 0.002565
- Max: 0.069245

**Dopo l'aggregazione** (max per feature_key):
- Righe: 234 (una per feature_key)
- Mean node_influence: 0.003077 (leggermente più alto, come ci si aspetta)
- Max: 0.069245 (invariato)

## Colonne nella Tabella di Verifica

| Colonna           | Fonte | Descrizione                                        |
|-------------------|-------|----------------------------------------------------|
| `feature_key`     | Calc  | Identificatore unico `layer_id`                    |
| `layer`           | JSON  | Layer del modello                                  |
| `index`           | JSON  | ID nel grafo (= id nel CSV)                        |
| `source`          | JSON  | Source set (es. "0-clt-hp")                        |
| `prompt`          | JSON  | Prompt testato (troncato a 50 char)                |
| `activation_max`  | JSON  | Massima attivazione sul prompt                     |
| `activation_sum`  | JSON  | Somma attivazioni su tutti i token                 |
| `peak_token`      | JSON  | Token dove la feature ha il picco                  |
| `peak_token_idx`  | JSON  | Indice del peak token nel prompt                   |
| `node_influence`  | CSV   | **MAX** influenza causale per questa feature_key   |
| `csv_ctx_idx`     | CSV   | Contesto dove node_influence è massima            |

## Perché Usiamo il MAX?

### Motivazione Teorica

Una feature può attivarsi in **diversi contesti** (token positions) con **diverse intensità di influenza**. 

Per il grafico vogliamo rappresentare:
- **Il massimo potenziale di influenza** di quella feature
- Un valore univoco per combinazione `feature_key × prompt`

### Alternativa Considerata (non usata)

Si potrebbe usare la **media** dei valori di node_influence, ma:
- ❌ Diluirebbe l'importanza delle features che hanno forte influenza in contesti specifici
- ❌ Non rifletterebbe il "potenziale massimo" della feature

### Scelta Implementata

✅ Usiamo il **MAX** perché:
- Rappresenta il massimo impatto causale della feature
- È coerente con l'approccio "peak-based" usato per le activations
- Mantiene una riga per combinazione feature × prompt

## Note sul Matching

### JSON vs CSV: Relazione many-to-one

**Dal JSON** (activations):
- Una feature viene testata su più prompt
- Ogni combinazione `feature_key × prompt` = 1 riga

**Dal CSV** (node_influence):
- Una feature può avere più righe (diversi ctx_idx)
- Ogni `feature_key` può avere da 1 a 7 valori di node_influence

**Nel Merge**:
- Left join: JSON ← CSV
- Per ogni feature_key dal JSON, prendiamo MAX(node_influence) dal CSV
- Risultato: una riga per ogni `feature_key × prompt`

### Esempio Completo

**JSON** (feature `0_95475` testata su 2 prompt):
```
feature_key | prompt                | activation_max
------------|----------------------|---------------
0_95475     | "entity: Dallas..."  | 12.5
0_95475     | "entity: Austin..."  | 10.3
```

**CSV** (feature `0_95475` con 4 contesti):
```
feature_key | ctx_idx | node_influence
------------|---------|---------------
0_95475     |    2    | 0.001381
0_95475     |    4    | 0.001515
0_95475     |    5    | 0.000835
0_95475     |    6    | 0.001667  ← MAX
```

**Tabella di Verifica** (dopo il merge):
```
feature_key | prompt                | activation_max | node_influence | csv_ctx_idx
------------|----------------------|----------------|----------------|------------
0_95475     | "entity: Dallas..."  | 12.5           | 0.001667       | 6
0_95475     | "entity: Austin..."  | 10.3           | 0.001667       | 6
```

✅ 2 righe (una per prompt), stesso `node_influence` (il max dal CSV)

## Test Automatico

**Script**: `scripts/test_max_node_influence.py`

Esegui per verificare:
```bash
python scripts/test_max_node_influence.py
```

Output atteso:
- Mostra distribuzione features per numero di contesti
- Esempi reali di features con multipli node_influence
- Verifica della logica di aggregazione
- Statistiche prima/dopo aggregazione

## Conclusioni

✅ **Implementazione corretta**: Una riga per `feature_key × prompt`  
✅ **MAX node_influence**: Rappresenta il massimo potenziale causale  
✅ **csv_ctx_idx**: Mostra quale contesto ha il valore massimo  
✅ **Test disponibile**: Verifica automatica con dati reali  
✅ **Documentazione completa**: Esempi e spiegazioni chiare  

Il sistema gestisce correttamente il fatto che una feature_key può avere multipli valori di node_influence nel CSV, selezionando sempre il massimo per la visualizzazione e l'analisi.

