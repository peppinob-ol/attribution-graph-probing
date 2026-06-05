# harness — read a GroupedCircuit, compute BOTH metric suites (env-harness)

- `metrics_ours/` — steering metrics: tier T1–T5, Hit%, vsMax, regime A/C/D/E,
  matched-random + top-K influence controls. Needs `groups` + `intervention`.
- `metrics_adag/` — clustering quality (silhouette, cluster-size CoV, opposing-sign
  intra-cluster pairs), description↔simulator Pearson correlation, 0×/2× ablation.
  Needs `units[].input_attribution/output_contribution` + `groups[].description`.
- `intervene/` — `clt.py` (ReplacementModel.feature_intervention) and `neuron.py`
  (neuron scale/zero hooks). Intervention runs in env-ours/env-adag, not env-harness;
  the harness consumes the resulting effect numbers.
- `run_metrics.py` — given a GroupedCircuit + suite, emit a results row → runs/.

Note: steering/ablation need a model on GPU, so those steps run in the model envs and
write effect artifacts; pure-stats metrics run here. Keep the split clean.
