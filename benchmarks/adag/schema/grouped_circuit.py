"""
GroupedCircuit — the canonical artifact contract for the ADAG↔ours benchmark.

==============================  DRAFT  ==============================
This schema is the make-or-break design point for symmetric metrics. It is a
STARTING POINT reflecting what we converged on so far; finalize collaboratively
(step "A") before relying on it. Validated against real outputs:
  - ADAG df_node columns: layer, token, neuron, attribution, activation,
    attr_map (10d input-attribution), contrib_map (5d output-contribution), label
  - ours: circuit-tracer CLT features (layer, pos, feature index) + supernode roles
=====================================================================

Design goal: every METHOD emits a GroupedCircuit; every METRIC reads one.
- ours metrics (steering: tier T1-T5, Hit%, vsMax, regime, controls) need
  `groups` + `intervention`.
- adag metrics (silhouette/CoV/opp-sign cluster quality; description↔simulator
  correlation; 0x/2x ablation) need `units[].attribution_profile` + `groups[].description`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class Unit:
    """One atomic unit of the circuit (a neuron OR a transcoder feature)."""
    uid: str                          # stable id, e.g. "L16.t10.n362" or "L16.t10.f32768"
    layer: int
    pos: int                          # token position
    index: int                        # neuron index OR feature index
    polarity: Optional[int] = None    # +1/-1 if the method splits by sign (ADAG does)
    activation: Optional[float] = None
    attribution: Optional[float] = None
    # attribution profiles (the substrate-agnostic vectors ADAG's analysis needs):
    input_attribution: Optional[list[float]] = None    # ADAG attr_map
    output_contribution: Optional[list[float]] = None  # ADAG contrib_map


@dataclass
class Group:
    """A supernode / cluster of units with its interpretation."""
    gid: str
    member_uids: list[str]
    label: Optional[str] = None        # short label (both methods can produce)
    description: Optional[str] = None  # NL description (needed by ADAG desc-sim metric)
    role: Optional[str] = None         # our functional role: input/intermediate/answer/...


@dataclass
class Intervention:
    """How metrics actually ablate/amplify a group on this substrate."""
    backend: Literal["feature_intervention", "neuron_scale"]
    # feature_intervention -> circuit-tracer ReplacementModel; neuron_scale -> hooks/ADAG steer


@dataclass
class GroupedCircuit:
    schema_version: str
    model_id: str
    substrate: Literal["clt", "neuron"]
    grouping: Literal["probe_prompting", "adag_clustering"]
    task: str
    prompt_set_id: str
    seed: int
    units: list[Unit] = field(default_factory=list)
    groups: list[Group] = field(default_factory=list)
    intervention: Optional[Intervention] = None
    transcoder_ref: Optional[str] = None      # e.g. mntss/clt-llama-3.2-1b-524k@<sha>
    extra: dict = field(default_factory=dict)  # method-specific provenance

    # TODO(step A): JSON (de)serialization + a validate() that asserts the fields
    # each metric suite requires are present, and a matching grouped_circuit.schema.json.
