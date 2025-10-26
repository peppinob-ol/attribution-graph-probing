# Automated Circuit Interpretation via Probe Prompting

*From concept hypotheses to concept‑aligned supernodes in attribution graphs*

---

## TL;DR

Circuit tracing with attribution graphs is powerful but bottlenecked by manual feature interpretation. I rebuilt my pipeline around probe prompting: generate structured concept hypotheses from the prompt, elicit concept‑selective activations for graph features, and group features into concept‑aligned supernodes via simple, testable criteria. Validation uses Neuronpedia’s graph metrics (Replacement and Completeness), baselines (cosine/adjacency clustering), and cross‑prompt stability—not steers/ablations (planned for a later iteration).

**Key results (high‑level):**
- **Probe prompting → activation signatures:** per‑feature concept profiles (label vs. label+description) enable falsifiable grouping
- **Concept‑aligned grouping beats naive clustering** on coherence and stability, while remaining simple to reproduce
- **Neuronpedia metrics** (Replacement/Completeness) improve for the cleaned subgraphs relative to the raw pruned graphs and naive baselines
- **Cross‑prompt:** concept‑aligned supernodes remain stable under controlled paraphrases and entity swaps within the same task family
 - **Works without attention features:** with well‑designed probe prompts, polysemantic MLP features can be interpreted and profiled even when activations are off‑distribution (likely due to attention extracting meaning subsets during inference), especially in early layers ("relationship" nodes)
 - **Largely automated process:** requires light user supervision only to set concept hypotheses (probe prompts); the measurement, grouping, and subgraph evaluation loop runs automatically


**Takeaway:** A measurement‑driven loop (probe → measure → group → re‑measure) yields interpretable subgraphs without requiring manual "feature ethnography"or interventions. Steers/ablations are valuable, but not necessary to get immediate gains in legibility and reproducibility.

---

## Epistemic Status

**Medium confidence** in the current pipeline on small models and short factual prompts; **low confidence** in broad generalization to long CoT, adversarial prompts, or larger models without adjustments. Validation presently relies on Neuronpedia’s metrics, baselines, and cross‑prompt tests. **Interventions (steers/ablations) are planned but not yet included in results.**

**What would change my mind:** If baselines (cosine/adjacency) match or beat on coherence/stability and Neuronpedia metrics; if cross‑prompt survival drops substantially; or if attention‑aware methods render the present grouping insufficient.

---

## Motivation: The Circuit Tracing Bottleneck

Attribution graphs surface the features and edges that contributed to a target logit. In practice, the workflow demands a lot of manual interpretation and ad‑hoc grouping. I wanted a workflow that:

1. proposes concepts to test rather than assuming them,
2. measures alignment between features and concepts directly,
3. groups by measured behavior, not vague similarity,
4. validates groups with simple, reproducible metrics.

This project grew out of two experiences: months of black‑box concept exploration (Prompt Rover) and a very hands‑on, manual pass over the classic “The capital of the state containing Dallas is Austin” graph. In the first experiment I literally printed activations and annotated them by hand over several days. That convinced me to automate the parts that can be automated—starting with probes.

---

## Method: Probe Prompting and Feature Grouping

The pipeline turns a pruned attribution graph into a concept‑aligned subgraph:

1. **Concept hypothesis generation**
   - From the seed prompt, generate a set of candidate concepts with short labels and contextual descriptions (e.g. "Dallas, entity: A city in Texas, USA.").
2. **Probe prompting**
   - For each concept, create a label+description; run Neuronpedia‑style feature activation for each probe over the selected feature subset.
3. **Activation signatures**
   - For each feature × concept, compute a small signature: cosine similarity vs. original prompt activation, robust z‑score, whether the peak aligns to the concept token, and activation density.
4. **Concept‑aligned grouping (feature engineering rules)**
   - Group features into supernodes when they pass simple, transparent thresholds on alignment to the same concept family across probes and (optionally) paraphrases; prevent duplicates (a feature cannot belong to multiple supernodes).
5. **Subgraph construction**
   - Pin concept‑aligned supernodes; include their connecting edges; compute Neuronpedia graph metrics on the resulting subgraph.

### Concept hypotheses (example)

Seed prompt: "The capital of the state containing Dallas is Austin."

- label: Dallas (entity)
- label: Texas (entity)
- label: capital (relationship)
- label: containing / in (spatial relationship)
- label: Austin (entity)

Example probe prompt:

```
entity: A city in Texas, USA is Dallas
```

### Activation signatures (per feature × concept)

For each feature, we run multiple probe prompts (one per concept) and compare how its activation pattern changes across them:

- peak_on_label: whether max activation sits on the concept token
- peak_consistency: fraction of probes where the feature peaks on the expected concept token
- activation_max / activation_mean / sparsity_ratio: strength and sparsity of activation per probe
- cross‑probe stability: whether peak token shifts appropriately when concept changes (e.g., Dallas→Oakland)

This cross‑probe comparison reveals whether a feature is genuinely concept‑selective or polysemantic.

### Grouping criteria 

Features are grouped into concept‑aligned supernodes using transparent, testable thresholds. These were tuned on the Dallas→Austin prompt and validated on held‑out examples. All thresholds are configurable via CLI or JSON config.

**Dictionary/Semantic nodes** (entity detectors, e.g., "Dallas"):
- `peak_consistency ≥ 0.80`: When the concept token appears in a probe, it must be the activation peak ≥80% of the time
- `n_distinct_peaks ≤ 1`: Feature should peak consistently on the same token (not scatter across multiple tokens)
- `layer ≤ 3` OR `semantic_confidence ≥ 0.50`: Early layers or high semantic alignment to concept

**Relationship nodes** (spatial/abstract relations, e.g., "containing"):
- `sparsity < 0.45`: Relationship features tend to be less sparse (activate on multiple tokens in the relation phrase)
- Often polysemantic and found in layers 0-3 where early binding operations occur

**Say X nodes** (output promotion, e.g., "Say Austin"):
- `func_vs_sem ≥ 50%`: Functional role dominates over semantic content (promotes output token regardless of input semantics)
- `confidence_functional ≥ 0.90`: High confidence in functional classification
- `layer ≥ 7`: Output promotion happens in mid-to-late layers

**Cross‑prompt stability** (applied to all groups):
- Supernode features must activate consistently (≥70% overlap) on paraphrases and entity swaps within the task family
- Peak tokens shift appropriately (e.g., Dallas→Houston when city changes)

**Duplicate prevention**: Each feature belongs to at most one supernode; conflicts resolved by highest alignment score.

These thresholds are implemented in `scripts/02_node_grouping.py::DEFAULT_THRESHOLDS` and can be exported/imported as JSON for reproducibility.

---

## Validation

Validation is designed to be simple and reproducible without interventions.

### Neuronpedia metrics (Graph vs. Subgraph)

We report both Replacement and Completeness for the raw pruned graph and for the concept‑aligned subgraph (pinned supernodes + connected nodes).

**Replacement Score**

Measures the fraction of end‑to‑end influence from input tokens to output logits that flows through feature nodes rather than error nodes. This is a strict metric that rewards complete explanations where tokens influence logits entirely through features.

The graph score is for the entire pruned attribution graph, while the subgraph score is only for your pinned nodes and the nodes that are connected to them. It treats features not included in the subgraph as error nodes by merging their edge weights with the corresponding error nodes (based on layer and position), then computes replacement and completeness scores using the modified adjacency matrix.

**Completeness Score**

Measures the fraction of incoming edges to all nodes (weighted by each node’s influence on the output) that originate from feature or token nodes rather than error nodes. This metric gives partial credit for nodes that are mostly explained by features, even if some error influence remains.

The graph score is for the entire pruned attribution graph, while the subgraph score is only for your pinned nodes and the nodes that are connected to them. It treats features not included in the subgraph as error nodes by merging their edge weights with the corresponding error nodes (based on layer and position), then computes replacement and completeness scores using the modified adjacency matrix.

> TODO: Insert measured Replacement/Completeness (graph vs. subgraph) for the Dallas→Austin run(s).

### Baselines

We compare concept‑aligned grouping to two naive baselines:

- **Cosine‑only clustering:** cluster features by decoder‑vector similarity
- **Adjacency‑only clustering:** cluster by attribution edge connectivity (e.g., Louvain)

**Metrics:**

- Semantic coherence (avg pairwise cosine within cluster on probe activations)
- Cross‑prompt stability (fraction of clusters that survive controlled variations)
- Neuronpedia metrics (Replacement/Completeness) at subgraph level

> TODO: Insert baseline numbers vs. concept‑aligned grouping (coherence, stability, Replacement/Completeness).

### Cross‑prompt robustness

Prompts within the same task family (entity swaps, mild reorderings, paraphrases). Survival means: (i) supernode features activate consistently; (ii) layer/token distributions remain similar; (iii) the aligned concept shifts appropriately (e.g., Dallas→Houston without collapsing to unrelated entities).

> TODO: Insert survival rates and notable failure modes.

---

## Case Study: “Dallas → Austin” (Probe‑Only)

We apply the pipeline to the classic prompt “The capital of the state containing Dallas is Austin.”

**What we show:**

- Probe activation heatmaps per concept (label vs. label+description)
- Concept alignment matrices (features × concepts)
- Concept‑aligned supernodes (e.g., Geographic Entity: Dallas; US State: Texas; Capital Relation; Spatial Containment; Output Promotion) and the resulting cleaned subgraph
- Neuronpedia metrics (graph vs. subgraph) and baseline comparisons

**What we don’t claim here:**

- No steers/ablations; no causal claims beyond changes to Neuronpedia metrics and stability/coherence improvements

> TODO: Insert figures/tables exported from the `eda/pages` workflow (heatmaps, alignment matrices, cluster coherence vs. baselines, Replacement/Completeness deltas).

---

## Why Probe Prompting Helps

Pure geometry (decoder cosine, raw adjacency) often conflates functionally different features. Probe prompting supplies external hypotheses and tests whether features actually behave like instances of a concept—on demand and under small variations. That makes grouping falsifiable and easy to iterate: adjust concepts → re‑probe → re‑group.

This complements the “model biology” angle: we’re not reverse‑engineering everything; we’re building meso‑level units (concept‑aligned supernodes) whose behavior is testable across related inputs.

---

## Interventions (planned)

Steers/ablations are the natural next step to close the loop causally (predict logit changes from supernode edits, then test). In this iteration I focused on a fully probe‑based validation. I plan to:

- predict steer/ablation effects from concept‑aligned supernodes,
- run targeted interventions (frozen/unfrozen attention variants),
- report logit deltas alongside Neuronpedia metrics.

> Note: some utility helpers exist in the repo; they are not currently wired for the above analysis end‑to‑end.

---

## Limitations and What Would Change My Mind

**Not included yet:** steers/ablations. **Missing modality:** attention‑mediated nuance is not captured by CLT/PLT alone. Prompt family narrowness (factual geography). Small models only.

I would revise the approach if: baselines match/beat on Replacement/Completeness and stability; cross‑prompt survival collapses; or attention‑aware attribution consistently contradicts concept‑aligned grouping on held‑out tasks.

---

## Reproducibility

### Code and Data

Repo: [https://github.com/peppinob-ol/attribution-graph-probing](https://github.com/peppinob-ol/attribution-graph-probing)

Core pages used in this pipeline (runnable as scripts):

- `eda/pages/00_Graph_Generation.py`
- `eda/pages/01_Probe_Prompts.py`
- `eda/pages/02_Node_Grouping.py`

**How to run (example):**

```bash
# 1) Generate attribution graph (requires Neuronpedia API key)
python eda/pages/00_Graph_Generation.py \
  --prompt "The capital of the state containing Dallas is Austin" \
  --model gemma-2-2b

# 2) Run probe prompting (label and label+description)
python eda/pages/01_Probe_Prompts.py \
  --graph output/graph_data/latest.json \
  --concepts output/prompts.json

# 3) Group features into concept-aligned supernodes
python eda/pages/02_Node_Grouping.py \
  --features output/features.json \
  --output output/supernodes_final.json
```

> TODO: Confirm exact CLI flags as implemented in the current `eda/pages` scripts, and add the export commands for alignment heatmaps and metrics tables used in the figures.

**Determinism:**

```python
# In 01_Probe_Prompts.py
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)
torch.manual_seed(RANDOM_SEED)
```

Artifacts to export:

- Attribution graphs (JSON)
- Concept hypotheses (JSON)
- Probe activation results (CSV/Parquet)
- Supernode definitions (JSON)
- Baseline clustering outputs (CSV)
- Neuronpedia metrics (graph vs. subgraph)
- Cross‑prompt results (CSV)
- Figures (SVG/PNG)

---

## Related Work

- **Attribution graphs (CLT/PLT)**: Anthropic and Neuronpedia established the method and tooling; this post focuses on a probe‑based analysis loop that sits on top.
- **Black‑box concept extraction**: Prompt Rover (my prior work) for hypothesis generation; here used to seed white‑box validation.
- **Naive clustering pitfalls**: Cosine/adjacency grouping often fails functional interpretability; probe‑based grouping is behavior‑driven and falsifiable.

**Background note:** In my first pass on Dallas→Austin I performed an “ethnographic” manual annotation of activations to understand how nodes differentiate during inference. The present method automates what can be automated from that experience; the ethnographic framing is not required for this pipeline.

---

## Acknowledgements

Thanks to Neuronpedia for the tracer and metrics, Anthropic for the CLT paradigm, and the LessWrong/Alignment communities for discussion. Personal thanks to Neel Nanda: his feedback about “make validation clearer” directly shaped this probe‑centric rewrite.

---

**Disclaimer**: English is not my first language. I used language models to help edit grammar and clarity after writing my ideas. All core concepts, experiments, and engineering are my own.

---

> TODOs summary
> - Insert real numbers for coherence, stability, Replacement/Completeness (graph vs. subgraph)
> - Confirm CLI flags for `eda/pages` scripts and add export commands
> - Add figures from the pages (heatmaps, alignment matrices, baseline comparison)
> - Add cross‑prompt results table and failure modes


