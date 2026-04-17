"""Tests for the cross-run best-per-cell aggregator."""
import json
import os
import tempfile
from pathlib import Path

import pytest

from demo.app.data.cross_run_best import (
    CrossRunBestAggregator,
    _score_from_swap,
)


def _make_swap(
    tier=None,
    steered_has_to_answer=False,
    steered_has_to_capital=False,
    target_rank=None,
    vsmax=None,
    control_mode="labeled",
):
    """Build a minimal swap JSON dict for testing."""
    data = {
        "evaluation": {
            "exact_match": {
                "steered_has_to_answer": steered_has_to_answer,
                "steered_has_to_capital": steered_has_to_capital,
                "from_suppressed": True,
            },
            "raw": {"default_output": "x", "steered_output": "y"},
        },
        "source": {"slug": "a"},
        "target": {"slug": "b"},
        "metadata": {
            "control": {
                "control_mode": control_mode,
            },
        },
    }
    if tier is not None:
        data["classification"] = {"tier": tier}
    if target_rank is not None:
        data["evaluation"]["baseline_logits"] = {
            "target": {"logit": 10.0, "prob": 0.1, "rank": target_rank},
            "source": {"logit": 11.0, "prob": 0.2, "rank": 1},
        }
    if vsmax is not None:
        data["evaluation"]["logit_trajectory"] = {
            "contrast_groups": {
                "same_dataset": {
                    "aggregate": {"best_target_minus_max": vsmax},
                }
            }
        }
    return data


def _write_swap(run_dir, from_slug, to_slug, swap_data, variant_suffix=""):
    by_source = run_dir / "by_source" / from_slug
    by_source.mkdir(parents=True, exist_ok=True)
    suffix = f"__{variant_suffix}" if variant_suffix else ""
    path = by_source / f"to_{to_slug}{suffix}.json"
    path.write_text(json.dumps(swap_data), encoding="utf-8")
    return path


def _write_manifest(run_dir, run_id, control_mode="labeled"):
    manifest = {
        "run_id": run_id,
        "display_demo": True,
        "status": "completed",
        "config": {
            "experiment_name": f"test_{run_id}",
            "control": {"mode": control_mode},
            "inputs": {"graphs_root": str(run_dir.parent.parent.parent)},
        },
    }
    (run_dir / "run_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    resolved = {"control": {"mode": control_mode}}
    (run_dir / "config_resolved.json").write_text(
        json.dumps(resolved), encoding="utf-8"
    )
    return manifest


def _build_fixture(tmp_path, runs_spec):
    """Create a dataset dir with multiple runs.

    runs_spec: list of (run_id, control_mode, cells_dict)
      cells_dict: {(from, to): swap_kwargs}
    Returns (datasets dict expected by aggregator, dataset_id).
    """
    dataset_dir = tmp_path / "test_dataset_batch"
    swaps_dir = dataset_dir / "_swaps" / "runs"
    swaps_dir.mkdir(parents=True)

    runs = []
    for run_id, control_mode, cells in runs_spec:
        run_dir = swaps_dir / run_id
        run_dir.mkdir()
        manifest = _write_manifest(run_dir, run_id, control_mode)
        for (from_slug, to_slug), kwargs in cells.items():
            _write_swap(run_dir, from_slug, to_slug, _make_swap(**kwargs))

        swap_count = sum(
            1 for _ in (run_dir / "by_source").glob("*/to_*.json")
        ) if (run_dir / "by_source").exists() else 0

        runs.append({
            "id": run_id,
            "manifest": manifest,
            "swap_count": swap_count,
            "control_mode": control_mode,
            "semantic_label": run_id.replace("_", " ").title(),
        })

    dataset_id = dataset_dir.name
    datasets = {
        dataset_id: {
            "dir": dataset_dir,
            "label": "Test Dataset",
            "runs": runs,
        }
    }
    return datasets, dataset_id


# -----------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------


class TestScoreTuple:
    def test_higher_tier_wins(self):
        a = _score_from_swap(_make_swap(tier=5), "run_a")
        b = _score_from_swap(_make_swap(tier=2), "run_b")
        assert a > b

    def test_exact_match_tiebreak(self):
        a = _score_from_swap(
            _make_swap(tier=2, steered_has_to_answer=True), "run_a"
        )
        b = _score_from_swap(
            _make_swap(tier=2, steered_has_to_answer=False), "run_b"
        )
        assert a > b

    def test_target_rank_tiebreak(self):
        a = _score_from_swap(_make_swap(tier=2, target_rank=1), "run_a")
        b = _score_from_swap(_make_swap(tier=2, target_rank=50), "run_b")
        assert a > b

    def test_vsmax_tiebreak(self):
        a = _score_from_swap(
            _make_swap(tier=2, target_rank=5, vsmax=3.0), "run_a"
        )
        b = _score_from_swap(
            _make_swap(tier=2, target_rank=5, vsmax=-1.0), "run_b"
        )
        assert a > b

    def test_missing_rank_loses(self):
        a = _score_from_swap(_make_swap(tier=2, target_rank=None), "run_a")
        b = _score_from_swap(_make_swap(tier=2, target_rank=9999), "run_b")
        assert b > a

    def test_stable_runid_tiebreak(self):
        swap = _make_swap(tier=5, target_rank=1, vsmax=2.0)
        a = _score_from_swap(swap, "run_z")
        b = _score_from_swap(swap, "run_a")
        assert a > b  # "run_z" > "run_a" lexicographically


class TestAggregator:
    def test_higher_tier_from_different_run(self, tmp_path):
        datasets, ds_id = _build_fixture(tmp_path, [
            ("run_a", "labeled", {
                ("x", "y"): {"tier": 2},
            }),
            ("run_b", "labeled", {
                ("x", "y"): {"tier": 5},
            }),
        ])
        agg = CrossRunBestAggregator(datasets)
        result = agg.get_best_matrix(ds_id)
        assert result["matrix"]["x"]["y"] == 5
        assert result["winners"]["x"]["y"]["run_id"] == "run_b"

    def test_random_run_excluded(self, tmp_path):
        datasets, ds_id = _build_fixture(tmp_path, [
            ("run_random", "random_feature_matched", {
                ("x", "y"): {"tier": 5},
            }),
            ("run_classic", "labeled", {
                ("x", "y"): {"tier": 2},
            }),
        ])
        agg = CrossRunBestAggregator(datasets)
        result = agg.get_best_matrix(ds_id)
        assert result["matrix"]["x"]["y"] == 2
        assert result["winners"]["x"]["y"]["run_id"] == "run_classic"

    def test_random_run_only_returns_empty(self, tmp_path):
        datasets, ds_id = _build_fixture(tmp_path, [
            ("run_random", "random_feature_matched", {
                ("x", "y"): {"tier": 5},
            }),
        ])
        agg = CrossRunBestAggregator(datasets)
        result = agg.get_best_matrix(ds_id)
        assert result["matrix"] == {}
        assert result["winners"] == {}

    def test_tiebreak_rank_then_vsmax(self, tmp_path):
        datasets, ds_id = _build_fixture(tmp_path, [
            ("run_a", "labeled", {
                ("x", "y"): {
                    "tier": 2, "target_rank": 5, "vsmax": 1.0,
                },
            }),
            ("run_b", "labeled", {
                ("x", "y"): {
                    "tier": 2, "target_rank": 1, "vsmax": -1.0,
                },
            }),
        ])
        agg = CrossRunBestAggregator(datasets)
        result = agg.get_best_matrix(ds_id)
        assert result["winners"]["x"]["y"]["run_id"] == "run_b"

    def test_tiebreak_vsmax_when_rank_equal(self, tmp_path):
        datasets, ds_id = _build_fixture(tmp_path, [
            ("run_a", "labeled", {
                ("x", "y"): {
                    "tier": 2, "target_rank": 3, "vsmax": -2.0,
                },
            }),
            ("run_b", "labeled", {
                ("x", "y"): {
                    "tier": 2, "target_rank": 3, "vsmax": 4.5,
                },
            }),
        ])
        agg = CrossRunBestAggregator(datasets)
        result = agg.get_best_matrix(ds_id)
        assert result["winners"]["x"]["y"]["run_id"] == "run_b"
        assert result["winners"]["x"]["y"]["vsmax"] == 4.5

    def test_caching(self, tmp_path):
        datasets, ds_id = _build_fixture(tmp_path, [
            ("run_a", "labeled", {("x", "y"): {"tier": 5}}),
        ])
        agg = CrossRunBestAggregator(datasets)
        r1 = agg.get_best_matrix(ds_id)
        r2 = agg.get_best_matrix(ds_id)
        assert r1 is r2

    def test_invalidate_clears_cache(self, tmp_path):
        datasets, ds_id = _build_fixture(tmp_path, [
            ("run_a", "labeled", {("x", "y"): {"tier": 5}}),
        ])
        agg = CrossRunBestAggregator(datasets)
        r1 = agg.get_best_matrix(ds_id)
        agg.invalidate(ds_id)
        r2 = agg.get_best_matrix(ds_id)
        assert r1 is not r2

    def test_allowed_slugs_intersection_drops_missing_cells(self, tmp_path):
        """Cross-run cell pruning: if any visible run has deleted an
        entity, that entity's row/column must disappear from the best
        matrix as well, even if other runs still hold data for it.
        """
        datasets, ds_id = _build_fixture(tmp_path, [
            # run_a covers both 'x' and 'z'
            ("run_classic", "labeled", {
                ("x", "y"): {"tier": 5},
                ("z", "y"): {"tier": 5},
                ("x", "z"): {"tier": 5},
            }),
            # run_b is missing the entity 'z' (user erased its swaps)
            ("run_additivity", "additivity", {
                ("x", "y"): {"tier": 2},
            }),
        ])

        class _StubRegistry:
            def __init__(self, datasets):
                self._datasets = datasets

            def get_allowed_slugs(self, _ds_id):
                # Mirror what DemoRegistry would compute: 'z' is absent
                # from run_additivity, so it gets dropped everywhere.
                return {"x", "y"}

        agg = CrossRunBestAggregator(_StubRegistry(datasets))
        result = agg.get_best_matrix(ds_id)
        assert "z" not in result["matrix"]
        assert "z" not in result["matrix"].get("x", {})
        # The (x, y) cell still wins from run_classic (tier 5 > tier 2)
        assert result["matrix"]["x"]["y"] == 5

    def test_winner_meta_fields(self, tmp_path):
        datasets, ds_id = _build_fixture(tmp_path, [
            ("run_a", "additivity", {
                ("x", "y"): {
                    "tier": 5, "target_rank": 2, "vsmax": 3.5,
                    "control_mode": "additivity",
                },
            }),
        ])
        agg = CrossRunBestAggregator(datasets)
        w = agg.get_best_matrix(ds_id)["winners"]["x"]["y"]
        assert w["run_id"] == "run_a"
        assert w["tier"] == 5
        assert w["target_rank"] == 2
        assert w["vsmax"] == 3.5
        assert w["control_mode"] == "additivity"
