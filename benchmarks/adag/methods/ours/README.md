# methods/ours — emit GroupedCircuit from our pipeline (env-ours)

Wraps our CLT + probe-prompting pipeline (scripts/01_probe_prompts.py,
02_node_grouping.py, 03_ct_steering.py) to produce a `GroupedCircuit` on the
CLT substrate.

Planned:
- `emit_clt_groups.py` — load Llama-3.2-1B (or Gemma-2-2B) + CLT via circuit-tracer
  ReplacementModel, build the feature attribution graph, run probe-prompting grouping
  → GroupedCircuit (substrate=clt, grouping=probe_prompting).  [cell A]
- local activation adapter to replace the Neuronpedia source (Neuronpedia has no
  clt-llama features) — use ReplacementModel.get_activations.
