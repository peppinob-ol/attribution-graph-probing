# Attribution Graph Probing

**Automated Attribution Graph Analysis through Probe Prompting**

This repository implements an automated pipeline for interpreting attribution graphs produced by transformer models with Cross-Layer Transcoders (CLTs). It builds on Anthropic's [Circuit Tracer](https://github.com/safety-research/circuit-tracer) and is intended as a downstream analysis layer that systematizes and scales feature-level interpretation.

The core idea -- developed in the [accompanying paper](https://www.lesswrong.com/posts/zQqGhKPqaCBZZDCge/automated-circuit-interpretation-via-probe-prompting) -- is to treat attribution graphs as objects that can be experimentally probed, measuring how features behave under controlled semantic variation rather than relying on decoder geometry or corpus examples alone.

---

## Overview

The project has three layers:

1. **Interpretation pipeline** (Stages 0-2): graph generation, probe prompting, and supernode construction.
2. **Causal testing framework** (Stage 3): feature swapping with labeled, random, and field-additivity controls across 5 domains and 33,387 steering runs.
3. **Research toolkit**: programmatic query, aggregation, statistical comparison, and pipeline tracing for qualitative and quantitative analysis of swap results.

### Key results

- **Labeled supernodes outperform random controls** in 4 of 5 domains (Cohen's d = 1.97 for vsMax in USA states)
- **Intermediate + answer fields** consistently outperform the full 3-field intervention ("less is more" effect: +14pp USA, +33pp books)
- **Suppression is generic; targeting is specific** -- random controls achieve equal suppression (83%) but near-zero hit rate (0.1%) vs labeled (24.7%)
- Full methodology: `METHODOLOGY_REPORT.md`
- Control experiment results: `output/FULLSCALE_CONTROL_REPORT.md`

---

## Quick Start

### Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file with API keys (needed for graph generation and probe prompting only):

```env
NEURONPEDIA_API_KEY='your-key'
OPENAI_API_KEY='your-key'
```

### Interactive UIs

```bash
# Streamlit app (pipeline stages 0-2)
streamlit run eda/app.py

# Swap Explorer (FastHTML demo -- reads from output/)
python demo/main.py
```

### Research toolkit (programmatic access)

```python
from scripts.utils.swap_query import SwapQuery
from scripts.utils.swap_stats import SwapStats
from scripts.utils.pipeline_tracer import PipelineTracer

q = SwapQuery()
s = SwapStats(q)
t = PipelineTracer()
```

Full usage and agentic research guidelines: `scripts/utils/AGENTIC_RESEARCH_GUIDE.md`

---

## Project Structure

```
attribution-graph-probing/
├── scripts/
│   ├── 00_neuronpedia_graph_generation.py  # Stage 0: graph extraction
│   ├── 01_probe_prompts.py                 # Stage 1: probe prompting
│   ├── 02_node_grouping.py                 # Stage 2: classification + supernodes
│   ├── 03_ct_steering.py                   # Stage 3: feature swapping engine
│   ├── experiments/batch/                  # Batch runner + configs + analysis
│   │   ├── run_batch_from_yaml.py          # Graph + grouping batch runner
│   │   ├── run_batch_swaps.py              # Swap batch runner (parallel, multi-GPU)
│   │   ├── configs/                        # YAML configs per domain/control mode
│   │   ├── pipeline/controls/              # Labeled, random, additivity builders
│   │   └── analyze_*.py                    # Analysis scripts
│   └── utils/                              # Research toolkit
│       ├── swap_query.py                   # Individual sample query + search
│       ├── swap_stats.py                   # Aggregation, comparison, statistics
│       ├── pipeline_tracer.py              # Upstream pipeline tracing
│       └── AGENTIC_RESEARCH_GUIDE.md       # LLM agentic research guidelines
│
├── demo/                                   # FastHTML Swap Explorer
│   ├── main.py                             # App entry point
│   ├── app/data/loader.py                  # Data loader (JSON + CSV)
│   ├── app/routes/                         # API and page routes
│   └── islands/                            # Svelte interactive components
│
├── eda/                                    # Streamlit application (pipeline UI)
│   ├── app.py
│   ├── pages/
│   └── README.md
│
├── output/                                 # Experiment data (per-domain)
│   ├── usa_states_batch/                   # 50 entities, 2450 pairs
│   ├── book_characters_authors_batch/      # 16 entities, 240 pairs
│   ├── products_founders_batch/            # 12 entities, 132 pairs
│   ├── paintings_painters_batch/           # 10 entities, 90 pairs
│   ├── sounds_colors_batch/               # 6 entities, 30 pairs
│   └── FULLSCALE_CONTROL_REPORT.md
│
├── tests/                                  # Test suite
├── METHODOLOGY_REPORT.md                   # Full methodology + epistemic status
├── requirements.txt
└── readme.md                               # This file
```

---

## Interpretation Pipeline (Stages 0-2)

### Stage 0: Graph Generation

**Script**: `scripts/00_neuronpedia_graph_generation.py`

Generates attribution graphs via Neuronpedia API. Extracts per-node static metrics (`node_influence`, `cumulative_influence`, `frac_external_raw`). Applies cumulative influence pruning to select features for probing.

### Stage 1: Probe Prompting

**Script**: `scripts/01_probe_prompts.py`

Generates concept-aligned probe prompts that vary semantic content while preserving syntactic structure. Measures per-feature activations across probes, producing cross-prompt behavioral signatures (peak token consistency, sparsity, functional vs semantic preference).

### Stage 2: Node Grouping

**Script**: `scripts/02_node_grouping.py`

Classifies features into functional types using a transparent decision tree:

| Category | Criterion | Examples |
|----------|-----------|----------|
| **Semantic (Dictionary)** | peak_consistency >= 0.80, n_distinct_peaks <= 1 | "capital", "of" |
| **Say "X"** | func_vs_sem_pct >= 50, conf_F >= 0.90, layer >= 7 | Say (Austin) |
| **Relationship** | sparsity_median < 0.45 | (entity) related |
| **Semantic (Concept)** | layer <= 3 or conf_S >= 0.50 | "Texas", "Dallas" |

Features sharing classification and name are grouped into supernodes.

---

## Causal Testing Framework (Stage 3)

### Feature Swapping

For a swap from entity A to entity B: ablate A's supernodes (M=-2) and amplify B's supernodes (M=20) via additive delta injection. Attention is **not** frozen during intervention.

### Control Modes

| Mode | Description | Purpose |
|------|-------------|---------|
| **Labeled** | All concept-matched supernodes | Baseline intervention |
| **Random x3** | Layer-matched random features, concept-excluded | Specificity control |
| **Field additivity** | 7 field subsets per pair (3 single, 3 pair, 1 triple) | Decomposition analysis |

### Datasets

| Dataset | Template | Fields | Entities | Pairs |
|---------|----------|--------|----------|-------|
| USA States | "The capital of the state containing {city} is" | state, capital, city | 50 | 2,450 |
| Books | "The book featuring {character} was written by" | book, author, character | 16 | 240 |
| Products | "The company that makes {product} was founded by" | company, founder, product | 12 | 132 |
| Paintings | "The first name of the painter of {painting} is" | painting, painter, first_name | 10 | 90 |
| Sounds | "The most common color of the animal that goes '{sound}' is" | sound, animal, color | 6 | 30 |

### Evaluation Metrics

- **Hit%**: target answer in steered output
- **Sup%**: source answer absent from steered output
- **vsMax**: target logit minus max other answer logit (best over trajectory)
- **RkGrp**: best rank within full answer contrast group
- **Gap closure**: max logit gap improvement over trajectory

---

## Research Toolkit

Three modules in `scripts/utils/` enable programmatic exploration of the full experimental dataset.

### `swap_query.py` -- Individual sample access

```python
q = SwapQuery()

# Search with filtering and sorting
results = q.search(
    dataset="usa_states_batch",
    run="fullscale_usa_field_add",
    variant="add_state",
    sort_by="source_error_node_pct",
    top_n=5,
)

# Full detail for one sample
detail = q.get("usa_states_batch", "fullscale_usa_field_add",
                "mississippi_gulfport", "arizona_tucson", variant="add_state")
q.describe(detail)
```

### `swap_stats.py` -- Aggregation and comparison

```python
s = SwapStats(q)

# Labeled vs random with bootstrap CIs and Cohen's d
comp = s.compare(
    a=dict(dataset="usa_states_batch", run="fullscale_usa_labeled", label="labeled"),
    b=dict(dataset="usa_states_batch", run="fullscale_usa_random", label="random"),
)
s.print_comparison(comp)

# Per-entity breakdown
rows = s.per_entity("usa_states_batch", "fullscale_usa_field_add",
                     variant="add_state", role="source")
s.print_entity_table(rows)
```

### `pipeline_tracer.py` -- Upstream debugging

```python
t = PipelineTracer()

# Graph quality + supernode breakdown for one entity
gp, grp = t.entity_profile("usa_states_batch", "mississippi_gulfport")
t.print_entity_profile(gp, grp)

# Trace concept-to-supernode matching
trace = t.trace_swap_matching(
    "usa_states_batch", "mississippi_gulfport", "arizona_tucson",
    concept_fields=["state"],
)
t.print_matching_trace(trace)
```

See `scripts/utils/AGENTIC_RESEARCH_GUIDE.md` for complete LLM agentic research guidelines.

---

## Documentation

- **Methodology**: `METHODOLOGY_REPORT.md` -- claims, evidence, epistemic status
- **Control results**: `output/FULLSCALE_CONTROL_REPORT.md` -- 33k-run analysis
- **Batch experiments**: `scripts/experiments/batch/README.md`
- **Agentic research**: `scripts/utils/AGENTIC_RESEARCH_GUIDE.md`
- **Streamlit guide**: `eda/README.md`
- **Demo app**: `demo/README.md`

### External References

- [Circuit Tracer](https://github.com/safety-research/circuit-tracer) (Anthropic)
- [Attribution Graphs paper](https://transformer-circuits.pub/2025/attribution-graphs/) (Ameisen et al., 2025)
- [Neuronpedia](https://www.neuronpedia.org)

---

## Changelog

### v3.0.0 (March 2026)
- Full-scale control experiment framework (labeled, random, field-additivity)
- 33,387 steering runs across 5 domains
- Research toolkit: swap_query, swap_stats, pipeline_tracer
- FastHTML Swap Explorer demo with multi-dataset support
- Logit trajectory tracking and contrast group analysis
- Methodology report with epistemic framing

### v2.0.0 (October 2025)
- Renewed pipeline (3 stages)
- Neuronpedia API integration
- Automated probe prompting and supernode classification
- Streamlit UI

### v1.x (Archived)
- Documentation in `docs/archive_old_pipeline/`

---

**Version**: 3.0.0
**License**: GPL-3.0
**Last Updated**: March 2026
