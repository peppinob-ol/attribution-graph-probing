# methods/adapters — bridges between substrates/algorithms and the GroupedCircuit

- `adag_to_grouped.py` — ADAG `CircuitData` (df_node/df_edge: layer,token,neuron,
  attr_map,contrib_map,label) → GroupedCircuit (substrate=neuron).  [cell D source]
- `ours_to_grouped.py` — our CLT supernodes → GroupedCircuit (substrate=clt). [cell A]
- `adag_clustering_on_clt.py` — feed a CLT graph (as df_node/df_edge with attribution
  profiles) into ADAG's spectral clustering → GroupedCircuit. [cell B]
- `probe_on_neurons.py` — run our probe-prompting over neuron units (activations from
  ADAG's neuron circuit) → GroupedCircuit. [cell C]

The 2×2 (configs/cells.yaml) is just these four emitters → one GroupedCircuit each.
