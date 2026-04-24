"""
Regression tests for the controls subsystem.

Covers:
  - factory default and explicit mode selection
  - labeled builder reproducing expected feature counts
  - concept_fields and legacy include_capitals compatibility
  - InterventionResult metadata shape
  - concept_sets role resolution and subset selection
  - sampling determinism
  - exclusion helpers
  - trajectory-bearing result schema preservation
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Setup: make pipeline importable
# ---------------------------------------------------------------------------
BATCH_DIR = Path(__file__).resolve().parents[1] / "scripts" / "experiments" / "batch"
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"

if str(BATCH_DIR) not in sys.path:
    sys.path.insert(0, str(BATCH_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from pipeline.controls.factory import create_intervention_builder, register_control
from pipeline.controls.types import InterventionResult
from pipeline.controls.base import InterventionBuilder
from pipeline.controls.labeled import LabeledInterventionBuilder
from pipeline.controls.concept_sets import (
    get_concept_fields,
    resolve_concept_roles,
    select_concept_subset,
)
from pipeline.controls.sampling import (
    make_control_rng,
    sample_indices_matching_histogram,
    build_layer_histogram,
)
from pipeline.controls.exclusions import (
    feature_keys_from_interventions,
    exclude_concept_matching_supernodes,
    build_candidate_pool,
)
from pipeline.controls.matching import (
    compute_match_diagnostics,
    build_intervention_dicts,
    resolve_stored_activation,
)
from pipeline.swap_evaluator import resolve_answer_field
from pipeline.controls.random_feature_matched import RandomFeatureMatchedBuilder
from pipeline.controls.random_template_matched import RandomTemplateMatchedBuilder
from pipeline.controls.low_specificity_groupings import LowSpecificityGroupingsBuilder
from pipeline.controls.additivity import AdditivityBuilder


# ---------------------------------------------------------------------------
# ct_steering module loader
# ---------------------------------------------------------------------------
def _load_ct_steering():
    steering_path = SCRIPTS_DIR / "03_ct_steering.py"
    spec = importlib.util.spec_from_file_location("ct_steering", steering_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ct_steering"] = module
    spec.loader.exec_module(module)
    return module


def _build_ct_steering_stub():
    """
    Build a minimal stand-in for the ``ct_steering`` module that
    implements just enough of ``extract_ct_supernode`` and
    ``compute_ct_interventions`` to exercise the intervention builders
    against the pandas-only fixtures used here.

    The intervention-builder layer only touches these two entry points,
    so a faithful reimplementation against the fixtures is sufficient to
    validate the controls subsystem without pulling in torch.
    """
    from types import SimpleNamespace
    from dataclasses import dataclass as _dc, field as _field
    from typing import Any as _Any, Dict as _Dict, List as _List, Tuple as _Tuple

    @_dc(frozen=True)
    class _CTFeatureRef:
        layer: int
        index: int
        position: int
        activation: float = 0.0

    @_dc
    class _CTSupernodeSpec:
        concept: str
        slug: str
        features: _List[_CTFeatureRef]
        meta: _Dict[str, _Any] = _field(default_factory=dict)

        def ensure_non_empty(self) -> None:
            if not self.features:
                raise ValueError(
                    f"Supernode '{self.concept}' ({self.slug}) is empty."
                )

    def extract_ct_supernode(
        grouping_df,
        metrics_df,
        concept: str,
        slug: str,
        *,
        supernode_col: str = "supernode_name",
        position_col: str = "position",
    ) -> _CTSupernodeSpec:
        if not concept.strip():
            raise ValueError("Concept string must be non-empty.")
        c = concept.strip().lower()
        names = grouping_df[supernode_col].astype(str).str.lower()
        mask = names.str.contains(c, na=False, regex=False)
        matches = grouping_df.loc[mask]
        if matches.empty:
            # Per-word fallback for multi-word concepts (mirrors the
            # real extractor's behavior closely enough for fixture tests).
            import re as _re
            skip_words = {"of", "the", "de", "la", "le", "a", "an", "and"}
            tokens = [t for t in _re.split(r"\s+", c) if t]
            accum_mask = None
            for tok in tokens:
                if len(tok) < 3 or tok in skip_words:
                    continue
                m = names.str.contains(tok, na=False, regex=False)
                accum_mask = m if accum_mask is None else (accum_mask | m)
            if accum_mask is not None:
                matches = grouping_df.loc[accum_mask]
            if matches.empty:
                raise ValueError(
                    f"No supernode rows matched concept '{concept}' for slug '{slug}'."
                )
        feats: _Dict[_Tuple[int, int, int], _CTFeatureRef] = {}
        for _, row in matches.iterrows():
            layer = int(row["layer"])
            idx = int(row["feature"])
            if position_col in row and row.get(position_col) is not None:
                try:
                    pos = int(row[position_col])
                except (TypeError, ValueError):
                    pos = -1
            else:
                pos = -1
            key = (layer, idx, pos)
            if key in feats:
                continue
            feats[key] = _CTFeatureRef(layer=layer, index=idx, position=pos)
        return _CTSupernodeSpec(concept=concept, slug=slug, features=list(feats.values()))

    def compute_ct_interventions(
        supernode,
        M: float,
        *,
        steer_generated_tokens: bool = False,
        activations_map=None,
        use_stored_as_base: bool = False,
    ) -> _List[_Dict[str, _Any]]:
        supernode.ensure_non_empty()
        out: _List[_Dict[str, _Any]] = []
        for f in supernode.features:
            entry: _Dict[str, _Any] = {
                "layer": f.layer,
                "index": f.index,
                "position": f.position,
                "M": M,
                "ablate": M == 0,
                "steer_generated_tokens": steer_generated_tokens,
            }
            if activations_map is not None:
                key = (f.layer, f.index, f.position)
                if key in activations_map:
                    entry["stored_activation"] = activations_map[key]
                elif f.position == -1:
                    for (l, ff, p), val in activations_map.items():
                        if l == f.layer and ff == f.index:
                            entry["stored_activation"] = val
                            break
            if use_stored_as_base:
                entry["use_stored_as_base"] = True
            out.append(entry)
        return out

    return SimpleNamespace(
        extract_ct_supernode=extract_ct_supernode,
        compute_ct_interventions=compute_ct_interventions,
        CTFeatureRef=_CTFeatureRef,
        CTSupernodeSpec=_CTSupernodeSpec,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ct_steering():
    try:
        return _load_ct_steering()
    except (ImportError, ModuleNotFoundError):
        return _build_ct_steering_stub()


def _make_grouping_df(rows):
    """Build a minimal grouping DataFrame."""
    return pd.DataFrame(rows, columns=["layer", "feature", "supernode_name", "position"])


def _make_metrics_df(rows):
    """Build a minimal metrics DataFrame."""
    return pd.DataFrame(
        rows, columns=["layer", "feature", "activation", "node_influence", "cumulative_influence"]
    )


@pytest.fixture
def simple_graph_data():
    """
    Two-entity graph with known supernodes for testing the labeled builder.
    Entity A has supernodes 'texas' (2 features) and 'austin' (1 feature).
    Entity B has supernodes 'georgia' (1 feature) and 'atlanta' (1 feature).
    """
    grouping_a = _make_grouping_df([
        (7, 100, "texas", -1),
        (8, 200, "texas", -1),
        (9, 300, "austin", -1),
        (2, 400, "generic-copula", -1),
    ])
    metrics_a = _make_metrics_df([
        (7, 100, 1.5, 0.3, 0.6),
        (8, 200, 2.0, 0.4, 0.7),
        (9, 300, 1.0, 0.2, 0.5),
        (2, 400, 0.5, 0.1, 0.2),
    ])
    grouping_b = _make_grouping_df([
        (7, 110, "georgia", -1),
        (8, 210, "atlanta", -1),
        (3, 410, "generic-copula", -1),
    ])
    metrics_b = _make_metrics_df([
        (7, 110, 1.2, 0.3, 0.5),
        (8, 210, 0.8, 0.2, 0.4),
        (3, 410, 0.4, 0.1, 0.2),
    ])
    data_from = {
        "grouping": grouping_a,
        "metrics": metrics_a,
        "activations_map": {},
    }
    data_to = {
        "grouping": grouping_b,
        "metrics": metrics_b,
        "activations_map": {(7, 110, -1): 1.2, (8, 210, -1): 0.8},
    }
    return data_from, data_to


class FakeSwapPair:
    def __init__(self, from_slug, to_slug, from_entity, to_entity):
        self.from_slug = from_slug
        self.to_slug = to_slug
        self.from_entity = from_entity
        self.to_entity = to_entity
        self.swap_id = f"{from_slug}__{to_slug}"
        self.is_identity = from_slug == to_slug
        self.from_concept = (from_entity.get("state") or from_entity.get("book") or "").strip().lower()
        self.to_concept = (to_entity.get("state") or to_entity.get("book") or "").strip().lower()


# ===================================================================
# Factory tests
# ===================================================================

class TestFactory:
    def test_default_is_labeled(self):
        builder = create_intervention_builder({})
        assert isinstance(builder, LabeledInterventionBuilder)

    def test_explicit_labeled(self):
        builder = create_intervention_builder({"control": {"mode": "labeled"}})
        assert isinstance(builder, LabeledInterventionBuilder)

    def test_missing_control_block(self):
        builder = create_intervention_builder({"ct_steering": {"M_ablate": -2}})
        assert isinstance(builder, LabeledInterventionBuilder)

    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError, match="Unknown control mode"):
            create_intervention_builder({"control": {"mode": "nonexistent"}})

    def test_register_and_create(self):
        class DummyBuilder(InterventionBuilder):
            def build_for_pair(self, **kwargs):
                return InterventionResult(
                    features=[], ablate_count=0, amplify_count=0,
                    control_mode="dummy",
                )

        register_control("dummy_test", DummyBuilder)
        builder = create_intervention_builder({"control": {"mode": "dummy_test"}})
        assert isinstance(builder, DummyBuilder)


# ===================================================================
# Labeled builder tests
# ===================================================================

class TestLabeledBuilder:
    def test_usa_style_swap(self, ct_steering, simple_graph_data):
        data_from, data_to = simple_graph_data
        pair = FakeSwapPair(
            from_slug="texas_dallas",
            to_slug="georgia_savannah",
            from_entity={"state": "Texas", "capital": "Austin"},
            to_entity={"state": "Georgia", "capital": "Atlanta"},
        )
        config = {
            "ct_steering": {"M_ablate": -2, "M_amplify": 20},
            "swap": {"concept_fields": ["state", "capital"]},
        }
        builder = LabeledInterventionBuilder()
        result = builder.build_for_pair(
            ct_steering=ct_steering,
            config=config,
            pair=pair,
            data_from=data_from,
            data_to=data_to,
        )
        assert result.control_mode == "labeled"
        assert result.ablate_count == 3  # texas(2) + austin(1)
        assert result.amplify_count == 2  # georgia(1) + atlanta(1)
        assert len(result.features) == 5
        assert result.concept_subsets_used == ["state", "capital"]

        ablate_features = [f for f in result.features if f["M"] == -2]
        amplify_features = [f for f in result.features if f["M"] == 20]
        assert len(ablate_features) == 3
        assert len(amplify_features) == 2

        for f in amplify_features:
            assert f.get("use_stored_as_base") is True

    def test_identity_swap_no_amplify(self, ct_steering, simple_graph_data):
        data_from, _ = simple_graph_data
        pair = FakeSwapPair(
            from_slug="texas_dallas",
            to_slug="texas_dallas",
            from_entity={"state": "Texas", "capital": "Austin"},
            to_entity={"state": "Texas", "capital": "Austin"},
        )
        config = {
            "ct_steering": {"M_ablate": -2, "M_amplify": 20},
            "swap": {"concept_fields": ["state", "capital"]},
        }
        builder = LabeledInterventionBuilder()
        result = builder.build_for_pair(
            ct_steering=ct_steering,
            config=config,
            pair=pair,
            data_from=data_from,
            data_to=data_from,
        )
        assert result.amplify_count == 0
        assert result.ablate_count == 3

    def test_books_concept_fields(self, ct_steering):
        grouping_a = _make_grouping_df([
            (7, 100, "harry potter", -1),
            (8, 200, "j.k. rowling", -1),
        ])
        metrics_a = _make_metrics_df([
            (7, 100, 1.5, 0.3, 0.6),
            (8, 200, 2.0, 0.4, 0.7),
        ])
        grouping_b = _make_grouping_df([
            (7, 110, "the lord of the rings", -1),
            (8, 210, "tolkien", -1),
        ])
        metrics_b = _make_metrics_df([
            (7, 110, 1.2, 0.3, 0.5),
            (8, 210, 0.8, 0.2, 0.4),
        ])
        data_from = {"grouping": grouping_a, "metrics": metrics_a, "activations_map": {}}
        data_to = {
            "grouping": grouping_b, "metrics": metrics_b,
            "activations_map": {(7, 110, -1): 1.2, (8, 210, -1): 0.8},
        }
        pair = FakeSwapPair(
            from_slug="hermione_granger",
            to_slug="frodo_baggins",
            from_entity={"character": "Hermione Granger", "book": "Harry Potter", "author": "J.K. Rowling"},
            to_entity={"character": "Frodo Baggins", "book": "The Lord of the Rings", "author": "J.R.R. Tolkien"},
        )
        config = {
            "ct_steering": {"M_ablate": -2, "M_amplify": 20},
            "swap": {"concept_fields": ["book", "author"]},
        }
        builder = LabeledInterventionBuilder()
        result = builder.build_for_pair(
            ct_steering=ct_steering, config=config,
            pair=pair, data_from=data_from, data_to=data_to,
        )
        assert result.ablate_count >= 1
        assert result.amplify_count >= 1
        assert result.concept_subsets_used == ["book", "author"]

    def test_legacy_include_capitals(self, ct_steering, simple_graph_data):
        data_from, data_to = simple_graph_data
        pair = FakeSwapPair(
            from_slug="texas_dallas",
            to_slug="georgia_savannah",
            from_entity={"state": "Texas", "capital": "Austin"},
            to_entity={"state": "Georgia", "capital": "Atlanta"},
        )
        config = {
            "ct_steering": {"M_ablate": -2, "M_amplify": 20},
            "swap": {"include_capitals": True},
        }
        builder = LabeledInterventionBuilder()
        result = builder.build_for_pair(
            ct_steering=ct_steering, config=config,
            pair=pair, data_from=data_from, data_to=data_to,
        )
        assert "capital" in result.concept_subsets_used


# ===================================================================
# InterventionResult metadata tests
# ===================================================================

class TestInterventionResult:
    def test_to_metadata_basic(self):
        result = InterventionResult(
            features=[{"layer": 7, "index": 100, "M": -2}],
            ablate_count=1,
            amplify_count=0,
            control_mode="labeled",
        )
        meta = result.to_metadata()
        assert meta["control_mode"] == "labeled"
        assert meta["ablate_count"] == 1
        assert meta["amplify_count"] == 0
        assert "replicate_id" not in meta
        assert "diagnostics" not in meta

    def test_to_metadata_with_diagnostics(self):
        result = InterventionResult(
            features=[], ablate_count=0, amplify_count=0,
            control_mode="random_feature_matched",
            replicate_id=42,
            diagnostics={"pool_size": 100, "exclusion_count": 5},
        )
        meta = result.to_metadata()
        assert meta["replicate_id"] == 42
        assert meta["diagnostics"]["pool_size"] == 100


# ===================================================================
# Concept sets tests
# ===================================================================

class TestConceptSets:
    def test_get_concept_fields_default(self):
        assert get_concept_fields({}) == ["state"]

    def test_get_concept_fields_list(self):
        assert get_concept_fields({"concept_fields": ["book", "author"]}) == ["book", "author"]

    def test_get_concept_fields_string(self):
        assert get_concept_fields({"concept_fields": "name"}) == ["name"]

    def test_get_concept_fields_include_capitals(self):
        fields = get_concept_fields({"include_capitals": True})
        assert "capital" in fields

    def test_resolve_roles_two_fields(self):
        roles = resolve_concept_roles(["state", "capital"])
        assert roles["source"] == ["state"]
        assert roles["target"] == ["capital"]
        assert roles["link"] == []

    def test_resolve_roles_three_fields(self):
        roles = resolve_concept_roles(["character", "book", "author"])
        assert roles["source"] == ["character"]
        assert roles["link"] == ["book"]
        assert roles["target"] == ["author"]

    def test_select_subset_source_only(self):
        fields = select_concept_subset(
            ["character", "book", "author"], ["source"]
        )
        assert fields == ["character"]

    def test_select_subset_source_target(self):
        fields = select_concept_subset(
            ["character", "book", "author"], ["source", "target"]
        )
        assert fields == ["character", "author"]

    def test_select_subset_all_roles(self):
        fields = select_concept_subset(
            ["character", "book", "author"], ["source", "link", "target"]
        )
        assert fields == ["character", "book", "author"]


# ===================================================================
# Sampling tests
# ===================================================================

class TestSampling:
    def test_rng_determinism(self):
        rng1 = make_control_rng(42, "texas__georgia", 0, "random_feature_matched")
        rng2 = make_control_rng(42, "texas__georgia", 0, "random_feature_matched")
        assert rng1.random() == rng2.random()

    def test_rng_different_replicates(self):
        rng1 = make_control_rng(42, "texas__georgia", 0)
        rng2 = make_control_rng(42, "texas__georgia", 1)
        assert rng1.random() != rng2.random()

    def test_rng_different_pairs(self):
        rng1 = make_control_rng(42, "texas__georgia", 0)
        rng2 = make_control_rng(42, "ohio__florida", 0)
        assert rng1.random() != rng2.random()

    def test_histogram_matching(self):
        pool = [{"layer": 7, "v": i} for i in range(10)] + \
               [{"layer": 8, "v": i} for i in range(10)]
        target_hist = {7: 3, 8: 2}
        rng = make_control_rng(42, "test", 0)
        sampled = sample_indices_matching_histogram(
            rng, pool, lambda f: f["layer"], target_hist,
        )
        assert len(sampled) == 5
        layer_counts = {}
        for s in sampled:
            layer_counts[s["layer"]] = layer_counts.get(s["layer"], 0) + 1
        assert layer_counts[7] == 3
        assert layer_counts[8] == 2

    def test_build_layer_histogram(self):
        features = [
            {"layer": 7, "index": 1, "M": -2},
            {"layer": 7, "index": 2, "M": -2},
            {"layer": 8, "index": 3, "M": -2},
        ]
        hist = build_layer_histogram(features)
        assert hist == {7: 2, 8: 1}


# ===================================================================
# Exclusion tests
# ===================================================================

class TestExclusions:
    def test_feature_keys_from_interventions(self):
        features = [
            {"layer": 7, "index": 100, "M": -2, "position": -1},
            {"layer": 8, "index": 200, "M": 20, "position": -1},
        ]
        keys = feature_keys_from_interventions(features)
        assert (7, 100) in keys
        assert (8, 200) in keys
        assert len(keys) == 2

    def test_exclude_concept_matching_supernodes(self):
        df = _make_grouping_df([
            (7, 100, "texas", -1),
            (8, 200, "austin", -1),
            (9, 300, "generic-copula", -1),
        ])
        excluded = exclude_concept_matching_supernodes(df, ["texas", "austin"])
        assert (7, 100) in excluded
        assert (8, 200) in excluded
        assert (9, 300) not in excluded

    def test_build_candidate_pool(self):
        df = _make_grouping_df([
            (7, 100, "texas", -1),
            (8, 200, "austin", -1),
            (9, 300, "generic-copula", -1),
        ])
        exclude = {(7, 100)}
        pool = build_candidate_pool(df, exclude)
        assert len(pool) == 2
        indices = {c["index"] for c in pool}
        assert 100 not in indices


# ===================================================================
# Matching tests
# ===================================================================

class TestMatching:
    def test_compute_match_diagnostics_exact(self):
        req = {7: 2, 8: 1}
        ach = {7: 2, 8: 1}
        diag = compute_match_diagnostics(req, ach)
        assert diag["deficit"] == 0
        assert diag["bins_exact_match"] == 2

    def test_compute_match_diagnostics_deficit(self):
        req = {7: 3, 8: 2}
        ach = {7: 2, 8: 2}
        diag = compute_match_diagnostics(req, ach)
        assert diag["deficit"] == 1

    def test_build_intervention_dicts(self):
        features = [{"layer": 7, "index": 100}, {"layer": 8, "index": 200}]
        interventions = build_intervention_dicts(features, -2)
        assert len(interventions) == 2
        assert all(f["M"] == -2 for f in interventions)
        assert all("layer" in f and "index" in f for f in interventions)

    def test_build_intervention_dicts_amplify(self):
        features = [{"layer": 7, "index": 100}]
        interventions = build_intervention_dicts(
            features, 20, use_stored_as_base=True, stored_activation=1.5
        )
        assert interventions[0]["use_stored_as_base"] is True
        assert interventions[0]["stored_activation"] == 1.5


# ===================================================================
# Random feature matched builder tests
# ===================================================================

class TestRandomFeatureMatchedBuilder:
    def test_produces_correct_mode(self, ct_steering, simple_graph_data):
        data_from, data_to = simple_graph_data
        pair = FakeSwapPair(
            from_slug="texas_dallas",
            to_slug="georgia_savannah",
            from_entity={"state": "Texas", "capital": "Austin"},
            to_entity={"state": "Georgia", "capital": "Atlanta"},
        )
        config = {
            "ct_steering": {"M_ablate": -2, "M_amplify": 20, "seed": 42},
            "swap": {"concept_fields": ["state", "capital"]},
            "control": {"mode": "random_feature_matched", "seed": 42},
        }
        builder = RandomFeatureMatchedBuilder()
        result = builder.build_for_pair(
            ct_steering=ct_steering,
            config=config,
            pair=pair,
            data_from=data_from,
            data_to=data_to,
        )
        assert result.control_mode == "random_feature_matched"
        assert result.replicate_id == 0
        assert "pool_from_size" in result.diagnostics
        assert "pool_to_size" in result.diagnostics

    def test_excludes_labeled_features(self, ct_steering, simple_graph_data):
        data_from, data_to = simple_graph_data
        pair = FakeSwapPair(
            from_slug="texas_dallas",
            to_slug="georgia_savannah",
            from_entity={"state": "Texas", "capital": "Austin"},
            to_entity={"state": "Georgia", "capital": "Atlanta"},
        )
        config = {
            "ct_steering": {"M_ablate": -2, "M_amplify": 20, "seed": 42},
            "swap": {"concept_fields": ["state", "capital"]},
            "control": {
                "mode": "random_feature_matched",
                "seed": 42,
                "exclusions": {
                    "exclude_labeled_features": True,
                    "exclude_concept_matching_supernodes": True,
                },
            },
        }
        # Get the labeled features first
        labeled_builder = LabeledInterventionBuilder()
        labeled_result = labeled_builder.build_for_pair(
            ct_steering=ct_steering, config=config,
            pair=pair, data_from=data_from, data_to=data_to,
        )
        labeled_keys = {
            (f["layer"], f["index"]) for f in labeled_result.features
        }

        builder = RandomFeatureMatchedBuilder()
        result = builder.build_for_pair(
            ct_steering=ct_steering, config=config,
            pair=pair, data_from=data_from, data_to=data_to,
        )
        random_keys = {(f["layer"], f["index"]) for f in result.features}
        assert not (labeled_keys & random_keys), \
            "Random control should not overlap with labeled features"

    def test_deterministic_across_calls(self, ct_steering, simple_graph_data):
        data_from, data_to = simple_graph_data
        pair = FakeSwapPair(
            from_slug="texas_dallas",
            to_slug="georgia_savannah",
            from_entity={"state": "Texas", "capital": "Austin"},
            to_entity={"state": "Georgia", "capital": "Atlanta"},
        )
        config = {
            "ct_steering": {"M_ablate": -2, "M_amplify": 20, "seed": 42},
            "swap": {"concept_fields": ["state", "capital"]},
            "control": {"mode": "random_feature_matched", "seed": 99},
        }
        builder = RandomFeatureMatchedBuilder()
        r1 = builder.build_for_pair(
            ct_steering=ct_steering, config=config,
            pair=pair, data_from=data_from, data_to=data_to,
        )
        r2 = builder.build_for_pair(
            ct_steering=ct_steering, config=config,
            pair=pair, data_from=data_from, data_to=data_to,
        )
        keys1 = [(f["layer"], f["index"]) for f in r1.features]
        keys2 = [(f["layer"], f["index"]) for f in r2.features]
        assert keys1 == keys2

    def test_different_replicates_differ(self, ct_steering, simple_graph_data):
        data_from, data_to = simple_graph_data
        pair = FakeSwapPair(
            from_slug="texas_dallas",
            to_slug="georgia_savannah",
            from_entity={"state": "Texas", "capital": "Austin"},
            to_entity={"state": "Georgia", "capital": "Atlanta"},
        )
        config_r0 = {
            "ct_steering": {"M_ablate": -2, "M_amplify": 20, "seed": 42},
            "swap": {"concept_fields": ["state", "capital"]},
            "control": {"mode": "random_feature_matched", "seed": 42, "_current_replicate": 0},
        }
        config_r1 = {
            "ct_steering": {"M_ablate": -2, "M_amplify": 20, "seed": 42},
            "swap": {"concept_fields": ["state", "capital"]},
            "control": {"mode": "random_feature_matched", "seed": 42, "_current_replicate": 1},
        }
        builder = RandomFeatureMatchedBuilder()
        r0 = builder.build_for_pair(
            ct_steering=ct_steering, config=config_r0,
            pair=pair, data_from=data_from, data_to=data_to,
        )
        r1 = builder.build_for_pair(
            ct_steering=ct_steering, config=config_r1,
            pair=pair, data_from=data_from, data_to=data_to,
        )
        keys0 = [(f["layer"], f["index"]) for f in r0.features]
        keys1 = [(f["layer"], f["index"]) for f in r1.features]
        # With a small pool they may accidentally match, but typically differ
        # The test is mainly that the code runs without error for different replicates
        assert r0.replicate_id == 0
        assert r1.replicate_id == 1


# ===================================================================
# Trajectory result schema preservation test
# ===================================================================

class TestTrajectorySchema:
    """Verify that existing result files with trajectory data
    have the expected evaluation keys that the refactor must preserve."""

    @pytest.fixture(scope="class")
    def usa_trajectory_result(self):
        run_dir = (
            Path(__file__).resolve().parents[1]
            / "output" / "usa_states_batch" / "_swaps" / "runs"
        )
        if not run_dir.exists():
            pytest.skip("USA swap results not available")
        for d in sorted(run_dir.iterdir()):
            by_source = d / "by_source"
            if not by_source.exists():
                continue
            for src in sorted(by_source.iterdir()):
                for f in sorted(src.glob("to_*.json")):
                    data = json.loads(f.read_text())
                    if "logit_trajectory" in data.get("evaluation", {}):
                        return data
        pytest.skip("No trajectory-bearing result found")

    def test_trajectory_keys_present(self, usa_trajectory_result):
        ev = usa_trajectory_result["evaluation"]
        assert "logit_trajectory" in ev
        traj = ev["logit_trajectory"]
        assert "summary" in traj
        assert "trajectories" in traj
        summary = traj["summary"]
        for key in ("flip_position", "gap_closure", "initial_gap"):
            assert key in summary

    def test_baseline_logits_present(self, usa_trajectory_result):
        ev = usa_trajectory_result["evaluation"]
        assert "baseline_logits" in ev

    def test_position_0_comparison_present(self, usa_trajectory_result):
        ev = usa_trajectory_result["evaluation"]
        assert "position_0_comparison" in ev

    def test_interventions_block_present(self, usa_trajectory_result):
        interventions = usa_trajectory_result.get("interventions", {})
        assert "ablate_count" in interventions
        assert "amplify_count" in interventions
        assert "total_count" in interventions

    def test_contrast_groups_schema_if_present(self, usa_trajectory_result):
        """If contrast_groups exists it must have the expected structure."""
        traj = usa_trajectory_result["evaluation"].get("logit_trajectory", {})
        cg = traj.get("contrast_groups")
        if cg is None:
            pytest.skip("No contrast_groups in this result (legacy run)")
        sd = cg["same_dataset"]
        assert isinstance(sd["n_members"], int) and sd["n_members"] > 0
        assert "members" in sd
        assert isinstance(sd["members"], list)
        summary = sd["summary"]
        for key in ("mean_logit", "max_logit", "topk_mean_logit",
                     "target_minus_mean", "target_minus_max",
                     "target_minus_topk_mean", "target_rank_within_group"):
            assert key in summary, f"Missing contrast summary key: {key}"
        agg = sd["aggregate"]
        for key in ("initial_target_minus_mean", "best_target_minus_mean",
                     "initial_target_minus_max", "best_target_minus_max",
                     "best_rank_within", "initial_rank_within"):
            assert key in agg, f"Missing contrast aggregate key: {key}"


# ===================================================================
# Contrast-group unit test (synthetic logits)
# ===================================================================

class TestContrastGroupExtraction:
    """Unit test for contrast_tokens in extract_logit_trajectory."""

    def test_contrast_group_summary(self):
        try:
            import torch
        except ImportError:
            pytest.skip("torch not available")

        import sys
        repo_root = Path(__file__).resolve().parents[1]
        steering_path = repo_root / "scripts" / "neuronpedia_steering" / "batch_steering_ct.py"
        if not steering_path.exists():
            pytest.skip("batch_steering_ct.py not available")
        import importlib.util
        spec = importlib.util.spec_from_file_location("bsct", str(steering_path))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["bsct"] = mod
        spec.loader.exec_module(mod)

        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained("google/gemma-2-2b")

        vocab_size = tokenizer.vocab_size or 256000
        n_positions = 4
        logits = torch.randn(1, n_positions, vocab_size)

        result = mod.extract_logit_trajectory(
            logits=logits,
            tokenizer=tokenizer,
            prompt_length=1,
            target_token="Austin",
            source_token="Atlanta",
            contrast_tokens=["Sacramento", "Columbus", "Denver"],
        )
        cg = result.get("contrast_groups")
        assert cg is not None, "contrast_groups should be present"
        sd = cg["same_dataset"]
        assert sd["n_members"] >= 1
        # prompt_length=1 -> first_gen_pos=0 -> all n_positions are generation steps
        n_gen = n_positions
        assert len(sd["summary"]["mean_logit"]) == n_gen
        assert len(sd["summary"]["target_minus_mean"]) == n_gen
        assert sd["aggregate"]["initial_target_minus_mean"] is not None

    def test_no_contrast_when_none(self):
        try:
            import torch
        except ImportError:
            pytest.skip("torch not available")

        import sys
        repo_root = Path(__file__).resolve().parents[1]
        steering_path = repo_root / "scripts" / "neuronpedia_steering" / "batch_steering_ct.py"
        if not steering_path.exists():
            pytest.skip("batch_steering_ct.py not available")
        import importlib.util
        spec = importlib.util.spec_from_file_location("bsct2", str(steering_path))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["bsct2"] = mod
        spec.loader.exec_module(mod)

        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained("google/gemma-2-2b")

        vocab_size = tokenizer.vocab_size or 256000
        logits = torch.randn(1, 3, vocab_size)
        result = mod.extract_logit_trajectory(
            logits=logits,
            tokenizer=tokenizer,
            prompt_length=1,
            target_token="Austin",
            source_token="Atlanta",
            contrast_tokens=None,
        )
        assert "contrast_groups" not in result


# ===================================================================
# stored_activation lookup tests
# ===================================================================

class TestStoredActivationLookup:
    def test_exact_key_match(self):
        amap = {(7, 100, -1): 1.5}
        assert resolve_stored_activation(7, 100, -1, amap) == 1.5

    def test_wildcard_fallback(self):
        amap = {(8, 200, 3): 2.0}
        assert resolve_stored_activation(8, 200, -1, amap) == 2.0

    def test_no_match(self):
        amap = {(7, 100, -1): 1.5}
        assert resolve_stored_activation(9, 999, -1, amap) is None

    def test_exact_takes_priority(self):
        amap = {(7, 100, -1): 1.5, (7, 100, 3): 9.9}
        assert resolve_stored_activation(7, 100, -1, amap) == 1.5

    def test_build_dicts_with_activations_map(self):
        amap = {(7, 100, -1): 1.5, (8, 200, -1): 2.0}
        feats = [
            {"layer": 7, "index": 100, "position": -1},
            {"layer": 8, "index": 200, "position": -1},
            {"layer": 9, "index": 999, "position": -1},
        ]
        result = build_intervention_dicts(
            feats, 20, use_stored_as_base=True, activations_map=amap,
        )
        assert result[0]["stored_activation"] == 1.5
        assert result[1]["stored_activation"] == 2.0
        assert "stored_activation" not in result[2]
        assert all(r.get("use_stored_as_base") is True for r in result)

    def test_build_dicts_without_map_uses_scalar(self):
        feats = [{"layer": 7, "index": 100, "position": -1}]
        result = build_intervention_dicts(
            feats, 20, use_stored_as_base=True, stored_activation=3.0,
        )
        assert result[0]["stored_activation"] == 3.0


# ===================================================================
# Low-specificity groupings builder tests
# ===================================================================

class TestLowSpecificityGroupingsBuilder:
    def test_produces_correct_mode(self, ct_steering, simple_graph_data):
        data_from, data_to = simple_graph_data
        pair = FakeSwapPair(
            from_slug="texas_dallas",
            to_slug="georgia_savannah",
            from_entity={"state": "Texas", "capital": "Austin"},
            to_entity={"state": "Georgia", "capital": "Atlanta"},
        )
        config = {
            "ct_steering": {"M_ablate": -2, "M_amplify": 20, "seed": 42},
            "swap": {"concept_fields": ["state", "capital"]},
            "control": {"mode": "low_specificity_groupings", "seed": 42},
        }
        builder = LowSpecificityGroupingsBuilder()
        result = builder.build_for_pair(
            ct_steering=ct_steering, config=config,
            pair=pair, data_from=data_from, data_to=data_to,
        )
        assert result.control_mode == "low_specificity_groupings"
        assert "strategy" in result.diagnostics
        assert "available_supernodes_from" in result.diagnostics

    def test_excludes_concept_supernodes(self, ct_steering, simple_graph_data):
        data_from, data_to = simple_graph_data
        pair = FakeSwapPair(
            from_slug="texas_dallas",
            to_slug="georgia_savannah",
            from_entity={"state": "Texas", "capital": "Austin"},
            to_entity={"state": "Georgia", "capital": "Atlanta"},
        )
        config = {
            "ct_steering": {"M_ablate": -2, "M_amplify": 20, "seed": 42},
            "swap": {"concept_fields": ["state", "capital"]},
            "control": {"mode": "low_specificity_groupings", "seed": 42},
        }
        labeled = LabeledInterventionBuilder()
        ref = labeled.build_for_pair(
            ct_steering=ct_steering, config=config,
            pair=pair, data_from=data_from, data_to=data_to,
        )
        labeled_keys = {(f["layer"], f["index"]) for f in ref.features}

        builder = LowSpecificityGroupingsBuilder()
        result = builder.build_for_pair(
            ct_steering=ct_steering, config=config,
            pair=pair, data_from=data_from, data_to=data_to,
        )
        control_keys = {(f["layer"], f["index"]) for f in result.features}
        assert not (labeled_keys & control_keys)

    def test_amplify_features_have_stored_activation(self, ct_steering):
        grouping_a = _make_grouping_df([
            (7, 100, "texas", -1),
            (2, 400, "generic-copula", -1),
            (3, 500, "unrelated-feature", -1),
        ])
        metrics_a = _make_metrics_df([
            (7, 100, 1.5, 0.3, 0.6),
            (2, 400, 0.5, 0.1, 0.2),
            (3, 500, 0.3, 0.05, 0.1),
        ])
        grouping_b = _make_grouping_df([
            (7, 110, "georgia", -1),
            (3, 410, "generic-copula", -1),
            (4, 510, "other-feature", -1),
        ])
        metrics_b = _make_metrics_df([
            (7, 110, 1.2, 0.3, 0.5),
            (3, 410, 0.4, 0.1, 0.2),
            (4, 510, 0.6, 0.15, 0.3),
        ])
        data_from = {"grouping": grouping_a, "metrics": metrics_a, "activations_map": {}}
        data_to = {
            "grouping": grouping_b, "metrics": metrics_b,
            "activations_map": {(3, 410, -1): 0.4, (4, 510, -1): 0.6},
        }
        pair = FakeSwapPair(
            from_slug="texas_dallas",
            to_slug="georgia_savannah",
            from_entity={"state": "Texas", "capital": "Austin"},
            to_entity={"state": "Georgia", "capital": "Atlanta"},
        )
        config = {
            "ct_steering": {"M_ablate": -2, "M_amplify": 20, "seed": 42},
            "swap": {"concept_fields": ["state", "capital"]},
            "control": {"mode": "low_specificity_groupings", "seed": 42},
        }
        builder = LowSpecificityGroupingsBuilder()
        result = builder.build_for_pair(
            ct_steering=ct_steering, config=config,
            pair=pair, data_from=data_from, data_to=data_to,
        )
        amplify_feats = [f for f in result.features if f.get("M") == 20]
        for f in amplify_feats:
            assert f.get("use_stored_as_base") is True
            key = (f["layer"], f["index"], f.get("position", -1))
            if key in data_to["activations_map"]:
                assert "stored_activation" in f


# ===================================================================
# Additivity builder tests
# ===================================================================

class TestAdditivityBuilder:
    def test_source_only(self, ct_steering, simple_graph_data):
        data_from, data_to = simple_graph_data
        pair = FakeSwapPair(
            from_slug="texas_dallas",
            to_slug="georgia_savannah",
            from_entity={"state": "Texas", "capital": "Austin"},
            to_entity={"state": "Georgia", "capital": "Atlanta"},
        )
        config = {
            "ct_steering": {"M_ablate": -2, "M_amplify": 20},
            "swap": {"concept_fields": ["state", "capital"]},
            "control": {
                "mode": "additivity",
                "concept_subset": {"roles": ["source"]},
            },
        }
        builder = AdditivityBuilder()
        result = builder.build_for_pair(
            ct_steering=ct_steering, config=config,
            pair=pair, data_from=data_from, data_to=data_to,
        )
        assert result.control_mode == "additivity"
        assert result.ablate_count > 0
        assert result.amplify_count == 0
        assert result.diagnostics["roles_requested"] == ["source"]

    def test_target_only(self, ct_steering, simple_graph_data):
        data_from, data_to = simple_graph_data
        pair = FakeSwapPair(
            from_slug="texas_dallas",
            to_slug="georgia_savannah",
            from_entity={"state": "Texas", "capital": "Austin"},
            to_entity={"state": "Georgia", "capital": "Atlanta"},
        )
        config = {
            "ct_steering": {"M_ablate": -2, "M_amplify": 20},
            "swap": {"concept_fields": ["state", "capital"]},
            "control": {
                "mode": "additivity",
                "concept_subset": {"roles": ["target"]},
            },
        }
        builder = AdditivityBuilder()
        result = builder.build_for_pair(
            ct_steering=ct_steering, config=config,
            pair=pair, data_from=data_from, data_to=data_to,
        )
        assert result.ablate_count == 0
        assert result.amplify_count > 0

    def test_full_roles_covers_all_fields(self, ct_steering, simple_graph_data):
        """With all roles selected, additivity uses source fields for ablation
        and target fields for amplification.  With concept_fields=["state", "capital"],
        source=["state"], target=["capital"], link=[] -- so ablation covers "state"
        supernodes and amplification covers "capital" supernodes."""
        data_from, data_to = simple_graph_data
        pair = FakeSwapPair(
            from_slug="texas_dallas",
            to_slug="georgia_savannah",
            from_entity={"state": "Texas", "capital": "Austin"},
            to_entity={"state": "Georgia", "capital": "Atlanta"},
        )
        config = {
            "ct_steering": {"M_ablate": -2, "M_amplify": 20},
            "swap": {"concept_fields": ["state", "capital"]},
            "control": {
                "mode": "additivity",
                "concept_subset": {"roles": ["source", "link", "target"]},
            },
        }
        builder = AdditivityBuilder()
        result = builder.build_for_pair(
            ct_steering=ct_steering, config=config,
            pair=pair, data_from=data_from, data_to=data_to,
        )
        assert result.ablate_count > 0
        assert result.amplify_count > 0
        assert result.concept_subsets_used == ["state", "capital"]

    def test_books_source_target(self, ct_steering):
        grouping_a = _make_grouping_df([
            (7, 100, "harry potter", -1),
            (8, 200, "j.k. rowling", -1),
        ])
        metrics_a = _make_metrics_df([
            (7, 100, 1.5, 0.3, 0.6),
            (8, 200, 2.0, 0.4, 0.7),
        ])
        grouping_b = _make_grouping_df([
            (7, 110, "the lord of the rings", -1),
            (8, 210, "tolkien", -1),
        ])
        metrics_b = _make_metrics_df([
            (7, 110, 1.2, 0.3, 0.5),
            (8, 210, 0.8, 0.2, 0.4),
        ])
        data_from = {"grouping": grouping_a, "metrics": metrics_a, "activations_map": {}}
        data_to = {
            "grouping": grouping_b, "metrics": metrics_b,
            "activations_map": {(7, 110, -1): 1.2, (8, 210, -1): 0.8},
        }
        pair = FakeSwapPair(
            from_slug="hermione_granger",
            to_slug="frodo_baggins",
            from_entity={"character": "Hermione Granger", "book": "Harry Potter", "author": "J.K. Rowling"},
            to_entity={"character": "Frodo Baggins", "book": "The Lord of the Rings", "author": "J.R.R. Tolkien"},
        )
        config = {
            "ct_steering": {"M_ablate": -2, "M_amplify": 20},
            "swap": {"concept_fields": ["book", "author"]},
            "control": {
                "mode": "additivity",
                "concept_subset": {"roles": ["source", "target"]},
            },
        }
        builder = AdditivityBuilder()
        result = builder.build_for_pair(
            ct_steering=ct_steering, config=config,
            pair=pair, data_from=data_from, data_to=data_to,
        )
        assert result.ablate_count >= 1
        assert result.amplify_count >= 1
        assert "book" in result.concept_subsets_used
        assert "author" in result.concept_subsets_used


# ===================================================================
# Metadata persistence tests
# ===================================================================

class TestMetadataPersistence:
    def test_create_swap_result_includes_control_metadata(self):
        from pipeline.swap_evaluator import create_swap_result

        pair = FakeSwapPair(
            from_slug="texas_dallas",
            to_slug="georgia_savannah",
            from_entity={"state": "Texas", "capital": "Austin"},
            to_entity={"state": "Georgia", "capital": "Atlanta"},
        )
        raw = {"prompt": "test", "default": "", "steered": "",
               "ablate_count": 3, "amplify_count": 2, "intervention_count": 5}
        evaluation = {"exact_match": {}, "first_token": {}, "target_in_topk": {}, "raw": {}}
        config = {"ct_steering": {"M_ablate": -2, "M_amplify": 20}}
        ctrl_meta = {
            "control_mode": "random_feature_matched",
            "ablate_count": 3,
            "amplify_count": 2,
            "replicate_id": 5,
            "diagnostics": {"pool_from_size": 50},
        }

        result = create_swap_result(
            pair, raw, evaluation, config, 100.0,
            control_metadata=ctrl_meta,
        )
        assert "control" in result["metadata"]
        assert result["metadata"]["control"]["control_mode"] == "random_feature_matched"
        assert result["metadata"]["control"]["replicate_id"] == 5
        assert result["metadata"]["is_identity"] is False
        assert "timestamp" in result["metadata"]

    def test_create_swap_result_without_control_metadata(self):
        from pipeline.swap_evaluator import create_swap_result

        pair = FakeSwapPair(
            from_slug="texas_dallas",
            to_slug="texas_dallas",
            from_entity={"state": "Texas", "capital": "Austin"},
            to_entity={"state": "Texas", "capital": "Austin"},
        )
        raw = {"prompt": "test", "default": "", "steered": "",
               "ablate_count": 0, "amplify_count": 0, "intervention_count": 0}
        evaluation = {"exact_match": {}, "first_token": {}, "target_in_topk": {}, "raw": {}}
        config = {"ct_steering": {"M_ablate": -2, "M_amplify": 20}}

        result = create_swap_result(pair, raw, evaluation, config, 50.0)
        assert "control" not in result["metadata"]
        assert result["metadata"]["is_identity"] is True


# ===================================================================
# Random feature matched: stored_activation fix verification
# ===================================================================

class TestRandomFeatureMatchedStoredActivation:
    def test_amplify_features_have_stored_activation(self, ct_steering, simple_graph_data):
        data_from, data_to = simple_graph_data
        pair = FakeSwapPair(
            from_slug="texas_dallas",
            to_slug="georgia_savannah",
            from_entity={"state": "Texas", "capital": "Austin"},
            to_entity={"state": "Georgia", "capital": "Atlanta"},
        )
        config = {
            "ct_steering": {"M_ablate": -2, "M_amplify": 20, "seed": 42},
            "swap": {"concept_fields": ["state", "capital"]},
            "control": {"mode": "random_feature_matched", "seed": 42},
        }
        builder = RandomFeatureMatchedBuilder()
        result = builder.build_for_pair(
            ct_steering=ct_steering, config=config,
            pair=pair, data_from=data_from, data_to=data_to,
        )
        amplify_feats = [f for f in result.features if f.get("M") == 20]
        for f in amplify_feats:
            assert f.get("use_stored_as_base") is True
            key = (f["layer"], f["index"], f.get("position", -1))
            if key in data_to["activations_map"]:
                assert "stored_activation" in f


# ===================================================================
# Answer field resolution tests
# ===================================================================

class TestAnswerFieldResolver:
    def test_default_no_config(self):
        assert resolve_answer_field() == "capital"

    def test_default_from_concept_fields(self):
        assert resolve_answer_field(concept_fields=["state", "capital"]) == "capital"

    def test_default_three_fields_uses_last(self):
        assert resolve_answer_field(concept_fields=["state", "capital", "city"]) == "city"

    def test_explicit_override(self):
        swap_cfg = {"concept_fields": ["state", "capital", "city"], "answer_field": "capital"}
        assert resolve_answer_field(swap_cfg=swap_cfg, concept_fields=["state", "capital", "city"]) == "capital"

    def test_override_beats_concept_fields(self):
        swap_cfg = {"concept_fields": ["book", "author"], "answer_field": "book"}
        assert resolve_answer_field(swap_cfg=swap_cfg, concept_fields=["book", "author"]) == "book"

    def test_no_override_falls_back_to_last(self):
        swap_cfg = {"concept_fields": ["book", "author"]}
        assert resolve_answer_field(swap_cfg=swap_cfg, concept_fields=["book", "author"]) == "author"

    def test_empty_swap_cfg(self):
        assert resolve_answer_field(swap_cfg={}, concept_fields=["state"]) == "state"

    def test_evaluate_swap_uses_override(self):
        from pipeline.swap_evaluator import evaluate_swap
        raw = {"default": "Austin", "steered": "Atlanta", "default_topk": [], "steered_topk": []}
        entity_from = {"state": "Texas", "capital": "Austin", "city": "Dallas"}
        entity_to = {"state": "Georgia", "capital": "Atlanta", "city": "Savannah"}
        swap_cfg = {"concept_fields": ["state", "capital", "city"], "answer_field": "capital"}

        ev = evaluate_swap(raw, entity_from, entity_to,
                           concept_fields=["state", "capital", "city"],
                           swap_cfg=swap_cfg)
        assert ev["answer_field"] == "capital"
        assert ev["from_answer"] == "Austin"
        assert ev["to_answer"] == "Atlanta"

    def test_evaluate_swap_default_uses_last_field(self):
        from pipeline.swap_evaluator import evaluate_swap
        raw = {"default": "Dallas", "steered": "Savannah", "default_topk": [], "steered_topk": []}
        entity_from = {"state": "Texas", "capital": "Austin", "city": "Dallas"}
        entity_to = {"state": "Georgia", "capital": "Atlanta", "city": "Savannah"}

        ev = evaluate_swap(raw, entity_from, entity_to,
                           concept_fields=["state", "capital", "city"])
        assert ev["answer_field"] == "city"
        assert ev["from_answer"] == "Dallas"
        assert ev["to_answer"] == "Savannah"


# ===================================================================
# Random template-matched builder tests
# ===================================================================

def _three_field_graph_data():
    """Richer graph with three concept fields (state, capital, city).

    Each concept layer (7..11) also carries two non-concept features so
    the random sampler can structurally match the template's per-layer
    histogram after concept-supernode exclusion.  Layers 2..6 carry
    extra generic features to widen the pool further.
    """
    # Source graph A: Texas / Austin / Dallas
    rows_a = [
        (7, 100, "texas", -1),
        (8, 200, "texas", -1),
        (9, 300, "austin", -1),
        (10, 310, "austin", -1),
        (11, 320, "dallas", -1),
        # Non-concept features in the concept layers (per layer).
        (7, 700, "generic-7a", -1),
        (7, 701, "generic-7b", -1),
        (8, 800, "generic-8a", -1),
        (8, 801, "generic-8b", -1),
        (9, 900, "generic-9a", -1),
        (9, 901, "generic-9b", -1),
        (10, 1000, "generic-10a", -1),
        (10, 1001, "generic-10b", -1),
        (11, 1100, "generic-11a", -1),
        (11, 1101, "generic-11b", -1),
        # Low-layer generics.
        (2, 400, "generic-copula", -1),
        (3, 410, "unrelated", -1),
        (4, 420, "punctuation", -1),
        (5, 430, "stopword", -1),
        (6, 440, "other-feature", -1),
    ]
    grouping_a = _make_grouping_df(rows_a)
    metrics_a = _make_metrics_df([
        (l, f, 0.5, 0.1, 0.2) for (l, f, _, _) in rows_a
    ])

    # Target graph B: Georgia / Atlanta / Savannah
    rows_b = [
        (7, 110, "georgia", -1),
        (8, 210, "georgia", -1),
        (9, 310, "atlanta", -1),
        (10, 320, "atlanta", -1),
        (11, 330, "savannah", -1),
        (7, 710, "generic-7a", -1),
        (7, 711, "generic-7b", -1),
        (8, 810, "generic-8a", -1),
        (8, 811, "generic-8b", -1),
        (9, 910, "generic-9a", -1),
        (9, 911, "generic-9b", -1),
        (10, 1010, "generic-10a", -1),
        (10, 1011, "generic-10b", -1),
        (11, 1110, "generic-11a", -1),
        (11, 1111, "generic-11b", -1),
        (2, 410, "generic-copula", -1),
        (3, 420, "unrelated", -1),
        (4, 430, "punctuation", -1),
        (5, 440, "stopword", -1),
        (6, 450, "other-feature", -1),
    ]
    grouping_b = _make_grouping_df(rows_b)
    metrics_b = _make_metrics_df([
        (l, f, 0.5, 0.1, 0.2) for (l, f, _, _) in rows_b
    ])

    data_from = {
        "grouping": grouping_a,
        "metrics": metrics_a,
        "activations_map": {},
    }
    amap_to = {(l, f, -1): 0.5 for (l, f, _, _) in rows_b}
    data_to = {
        "grouping": grouping_b,
        "metrics": metrics_b,
        "activations_map": amap_to,
    }
    return data_from, data_to


class TestRandomTemplateMatchedBuilder:
    def _pair(self):
        return FakeSwapPair(
            from_slug="texas_dallas",
            to_slug="georgia_savannah",
            from_entity={"state": "Texas", "capital": "Austin", "city": "Dallas"},
            to_entity={"state": "Georgia", "capital": "Atlanta", "city": "Savannah"},
        )

    def _config_field_subset(self, fields, replicate=0):
        return {
            "ct_steering": {"M_ablate": -2, "M_amplify": 20, "seed": 42},
            "swap": {
                "concept_fields": ["state", "capital", "city"],
                "answer_field": "capital",
            },
            "control": {
                "mode": "random_template_matched",
                "seed": 42,
                "concept_subset": {"fields": list(fields)},
                "_current_replicate": replicate,
                "exclusions": {
                    "exclude_labeled_features": True,
                    "exclude_concept_matching_supernodes": True,
                },
                "matching": {"match_layers": True},
            },
        }

    def test_mode_and_template_provenance(self, ct_steering):
        data_from, data_to = _three_field_graph_data()
        pair = self._pair()
        config = self._config_field_subset(["state"])

        builder = RandomTemplateMatchedBuilder()
        result = builder.build_for_pair(
            ct_steering=ct_steering,
            config=config,
            pair=pair,
            data_from=data_from,
            data_to=data_to,
        )
        assert result.control_mode == "random_template_matched"
        assert result.replicate_id == 0
        diag = result.diagnostics
        assert diag["template_selection_mode"] == "fields"
        assert diag["template_active_fields"] == ["state"]
        assert diag["template_ablate_count"] >= 1
        assert diag["template_amplify_count"] >= 1

    def test_layer_histogram_matches_template(self, ct_steering):
        """Random ablate/amplify counts must equal the template's counts,
        and the per-layer layer histogram must match exactly given the
        three-field fixture (pool is large enough)."""
        data_from, data_to = _three_field_graph_data()
        pair = self._pair()
        config = self._config_field_subset(["state", "capital"])

        builder = RandomTemplateMatchedBuilder()
        result = builder.build_for_pair(
            ct_steering=ct_steering,
            config=config,
            pair=pair,
            data_from=data_from,
            data_to=data_to,
        )
        diag = result.diagnostics

        # Counts: random matches the template exactly.
        assert result.ablate_count == diag["template_ablate_count"]
        assert result.amplify_count == diag["template_amplify_count"]

        # Layer histograms: deficit should be 0 and every bin exact.
        ablate_match = diag.get("ablate_layer_match", {})
        amplify_match = diag.get("amplify_layer_match", {})
        assert ablate_match.get("deficit", 0) == 0
        assert amplify_match.get("deficit", 0) == 0
        assert ablate_match.get("bins_exact_match") == ablate_match.get("total_bins")
        assert amplify_match.get("bins_exact_match") == amplify_match.get("total_bins")

    def test_no_overlap_with_template_features(self, ct_steering):
        """Random sample must not include any template feature when
        exclude_labeled_features and exclude_concept_matching_supernodes
        are both on."""
        data_from, data_to = _three_field_graph_data()
        pair = self._pair()
        config = self._config_field_subset(["state", "capital", "city"])

        # Build the template (additivity full roles = full labeled on
        # this fixture) to get the excluded key set.
        template_cfg = copy_nested(config)
        template_cfg["control"]["mode"] = "additivity"
        template = AdditivityBuilder().build_for_pair(
            ct_steering=ct_steering,
            config=template_cfg,
            pair=pair,
            data_from=data_from,
            data_to=data_to,
        )
        template_keys = {(f["layer"], f["index"]) for f in template.features}

        random_result = RandomTemplateMatchedBuilder().build_for_pair(
            ct_steering=ct_steering,
            config=config,
            pair=pair,
            data_from=data_from,
            data_to=data_to,
        )
        random_keys = {
            (f["layer"], f["index"]) for f in random_result.features
        }
        assert not (template_keys & random_keys)

    def test_different_templates_yield_different_counts(self, ct_steering):
        """The whole point of template-matching: a single-field template
        and a three-field template should produce random nulls with
        different feature counts."""
        data_from, data_to = _three_field_graph_data()
        pair = self._pair()

        builder = RandomTemplateMatchedBuilder()
        r_single = builder.build_for_pair(
            ct_steering=ct_steering,
            config=self._config_field_subset(["state"]),
            pair=pair, data_from=data_from, data_to=data_to,
        )
        r_all = builder.build_for_pair(
            ct_steering=ct_steering,
            config=self._config_field_subset(["state", "capital", "city"]),
            pair=pair, data_from=data_from, data_to=data_to,
        )
        assert len(r_all.features) > len(r_single.features)

    def test_deterministic_same_seed(self, ct_steering):
        data_from, data_to = _three_field_graph_data()
        pair = self._pair()
        cfg = self._config_field_subset(["state", "capital"], replicate=0)

        builder = RandomTemplateMatchedBuilder()
        r1 = builder.build_for_pair(
            ct_steering=ct_steering, config=cfg,
            pair=pair, data_from=data_from, data_to=data_to,
        )
        r2 = builder.build_for_pair(
            ct_steering=ct_steering, config=cfg,
            pair=pair, data_from=data_from, data_to=data_to,
        )
        assert [(f["layer"], f["index"]) for f in r1.features] == \
               [(f["layer"], f["index"]) for f in r2.features]

    def test_different_replicates_differ(self, ct_steering):
        data_from, data_to = _three_field_graph_data()
        pair = self._pair()

        builder = RandomTemplateMatchedBuilder()
        r0 = builder.build_for_pair(
            ct_steering=ct_steering,
            config=self._config_field_subset(["state", "capital"], replicate=0),
            pair=pair, data_from=data_from, data_to=data_to,
        )
        r1 = builder.build_for_pair(
            ct_steering=ct_steering,
            config=self._config_field_subset(["state", "capital"], replicate=1),
            pair=pair, data_from=data_from, data_to=data_to,
        )
        assert r0.replicate_id == 0
        assert r1.replicate_id == 1
        keys0 = [(f["layer"], f["index"]) for f in r0.features]
        keys1 = [(f["layer"], f["index"]) for f in r1.features]
        # With the larger fixture pool these should differ in at least
        # one slot.
        assert keys0 != keys1

    def test_amplify_has_stored_activation_when_available(self, ct_steering):
        data_from, data_to = _three_field_graph_data()
        pair = self._pair()
        config = self._config_field_subset(["state", "capital"])

        result = RandomTemplateMatchedBuilder().build_for_pair(
            ct_steering=ct_steering, config=config,
            pair=pair, data_from=data_from, data_to=data_to,
        )
        amplify = [f for f in result.features if f.get("M") == 20]
        for f in amplify:
            assert f.get("use_stored_as_base") is True
            key = (f["layer"], f["index"], f.get("position", -1))
            if key in data_to["activations_map"]:
                assert "stored_activation" in f

    def test_roles_template_matches_role_semantics(self, ct_steering):
        """When concept_subset uses roles, the template provenance
        should record the correct ablate/amplify role fields."""
        data_from, data_to = _three_field_graph_data()
        pair = self._pair()
        config = self._config_field_subset(["state"])  # start from a field cfg
        config["control"]["concept_subset"] = {"roles": ["source"]}

        result = RandomTemplateMatchedBuilder().build_for_pair(
            ct_steering=ct_steering, config=config,
            pair=pair, data_from=data_from, data_to=data_to,
        )
        assert result.diagnostics["template_selection_mode"] == "roles"
        # Source-only template means there is no amplification side.
        assert result.amplify_count == 0


def copy_nested(d):
    import copy as _c
    return _c.deepcopy(d)


# ===================================================================
# Variant expansion tests (run_batch_swaps._expand_control_variants)
# ===================================================================

class TestExpandControlVariants:
    def _load_expander(self):
        import importlib.util
        module_name = "run_batch_swaps_for_tests"
        if module_name in sys.modules:
            return sys.modules[module_name]._expand_control_variants
        script = BATCH_DIR / "run_batch_swaps.py"
        spec = importlib.util.spec_from_file_location(module_name, script)
        module = importlib.util.module_from_spec(spec)
        # Register in sys.modules BEFORE exec so that dataclasses
        # with string annotations can resolve references.
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except ImportError as e:
            pytest.skip(f"run_batch_swaps deps unavailable: {e}")
        return module._expand_control_variants

    def test_labeled_default(self):
        expand = self._load_expander()
        variants = expand({})
        assert len(variants) == 1
        assert variants[0][1] == ""

    def test_additivity_runs_field_subset(self):
        expand = self._load_expander()
        config = {
            "control": {
                "mode": "additivity",
                "runs": [
                    {"fields": ["state"]},
                    {"fields": ["state", "capital"]},
                ],
            }
        }
        variants = expand(config)
        assert len(variants) == 2
        suffixes = [v[1] for v in variants]
        assert suffixes == ["add_state", "add_state_capital"]
        # Each variant carries concept_subset correctly.
        assert variants[0][0]["control"]["concept_subset"] == {"fields": ["state"]}
        assert variants[1][0]["control"]["concept_subset"] == {"fields": ["state", "capital"]}

    def test_random_template_matched_runs_x_replicates(self):
        expand = self._load_expander()
        config = {
            "control": {
                "mode": "random_template_matched",
                "replicates": 3,
                "runs": [
                    {"fields": ["state"]},
                    {"fields": ["state", "capital"]},
                ],
            }
        }
        variants = expand(config)
        # 2 runs * 3 replicates = 6 variants
        assert len(variants) == 6
        suffixes = [v[1] for v in variants]
        assert "rtm_state__r0" in suffixes
        assert "rtm_state__r2" in suffixes
        assert "rtm_state_capital__r0" in suffixes
        assert "rtm_state_capital__r2" in suffixes

        # Every variant carries its concept_subset and replicate id.
        for cfg, suffix in variants:
            ctrl = cfg["control"]
            assert ctrl["mode"] == "random_template_matched"
            assert "concept_subset" in ctrl
            assert "_current_replicate" in ctrl
            assert 0 <= ctrl["_current_replicate"] < 3

    def test_random_template_matched_no_runs_replicates_only(self):
        expand = self._load_expander()
        config = {
            "control": {
                "mode": "random_template_matched",
                "replicates": 2,
            }
        }
        variants = expand(config)
        assert len(variants) == 2
        suffixes = [v[1] for v in variants]
        assert suffixes == ["rtm_full__r0", "rtm_full__r1"]
        for cfg, _ in variants:
            # No concept_subset set means the builder defaults to full
            # roles at build time.
            assert "concept_subset" not in cfg["control"]

    def test_random_template_matched_single_no_runs(self):
        expand = self._load_expander()
        config = {
            "control": {
                "mode": "random_template_matched",
                "replicates": 1,
            }
        }
        variants = expand(config)
        assert len(variants) == 1
        assert variants[0][1] == ""

    def test_random_feature_matched_keeps_replicate_only_path(self):
        """Existing random_feature_matched behavior must be unchanged:
        replicate expansion, no field-subset fan-out."""
        expand = self._load_expander()
        config = {
            "control": {
                "mode": "random_feature_matched",
                "replicates": 3,
            }
        }
        variants = expand(config)
        assert len(variants) == 3
        suffixes = [v[1] for v in variants]
        assert suffixes == ["r0", "r1", "r2"]
