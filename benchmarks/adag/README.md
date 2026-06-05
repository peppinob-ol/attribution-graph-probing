# ADAG ↔ Probe-Prompting benchmark

Fair, reproducible comparison of **our** approach (CLT transcoder features + Probe
Prompting + steering) against **ADAG** (Transluce, arXiv:2604.07615 — MLP-neuron
circuits + spectral clustering + LLM descriptions).

## Idea
Both methods turn an attribution graph into interpreted supernodes. We compare them
**symmetrically**: every method's output is scored by **both** metric suites (ours +
theirs). To separate *algorithm* from *substrate* we run a 2×2:

|                | grouping = probe-prompting (ours) | grouping = spectral clustering (ADAG) |
|----------------|-----------------------------------|---------------------------------------|
| substrate=CLT  | A · our full system               | B · ADAG algo on our substrate        |
| substrate=neuron | C · our algo on their substrate | D · their full system                 |

Bridge models (run BOTH): **Llama-3.2-1B** (ADAG native + `clt-llama-3.2-1b-524k`)
and **Gemma-2-2B** (our native CLT `clt-gemma-2-2b-2.5M`; needs ADAG GeGLU port).

## The contract
Every method emits a `GroupedCircuit` (see `schema/`); every metric reads one. That
single artifact is what makes "both metrics on both methods" tractable. **The schema
is still DRAFT — to be finalized collaboratively.**

## Layout
- `schema/`   — the GroupedCircuit contract (draft)
- `methods/adag/` — git submodule → fork of TransluceAI/circuits (pinned)
- `methods/ours/` , `methods/adapters/` — emit GroupedCircuit from each pipeline + the
  cross cells (ADAG-clustering-on-CLT, probe-on-neurons)
- `harness/` — `metrics_ours/`, `metrics_adag/`, `intervene/`, `run_metrics.py`
- `configs/` — `models.yaml`, `tasks.yaml`, `cells.yaml`
- `envs/`    — three isolated, pinned uv environments (they cannot share one venv:
  TransformerLens vs HF/nnsight; see env files)
- `runs/`    — DVC-tracked artifacts

## Environments (isolated — pins from the smoke phase; driver = CUDA 12.2 → cu121)
```
uv venv --python 3.10 .venvs/ours  && uv pip install --python .venvs/ours  -r envs/env-ours.txt
uv venv --python 3.12 .venvs/adag  && uv pip install --python .venvs/adag  -r envs/env-adag.txt
uv venv --python 3.12 .venvs/harness && uv pip install --python .venvs/harness -r envs/env-harness.txt
```

## Status
- ✅ Feasibility + smoke PASS on Llama-3.2-1B (both substrates load & run). See the
  `adag-benchmark` memory for the env recipe and gotchas.
- ⏳ Fork ADAG → `peppinob-ol/circuits` (submodule), finalize schema, build adapters.

## Porting items (live in the fork)
- thread `use_chat_format` through `convert_inputs_to_circuits` (base model has no chat
  template; CLT is base-only); fix non-chat path to append `seed_response`.
- `Subject` config for Llama-3.2-1B (replace hardcoded `llama31_8B_instruct_config`).
- GeGLU grad-rule + 4-norm/softcapping handling for Gemma-2-2B.
