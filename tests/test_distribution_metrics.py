"""
Tests for position_0_distribution_metrics: entropy, entropy_delta, KL divergence.

Covers:
  - Entropy/KL computation logic matches torch reference implementation
  - Propagation through swap_evaluator into evaluation dict
  - Extraction in analyze_logit_trajectory into flat metric keys
  - Aggregation via compute_trajectory_summary
  - Edge cases: uniform distributions, identical distributions, degenerate (peaked)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pytest

BATCH_DIR = Path(__file__).resolve().parents[1] / "scripts" / "experiments" / "batch"
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"

if str(BATCH_DIR) not in sys.path:
    sys.path.insert(0, str(BATCH_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from pipeline.swap_evaluator import evaluate_swap
from analyze_logit_trajectory import extract_trajectory_metrics, compute_trajectory_summary


def _entropy(probs: List[float]) -> float:
    return -sum(p * math.log(p) for p in probs if p > 0)


def _kl(p: List[float], q: List[float], eps: float = 1e-10) -> float:
    return sum(
        pi * math.log(pi / max(qi, eps))
        for pi, qi in zip(p, q)
        if pi > 0
    )


def _make_dist_metrics(
    baseline_entropy: float,
    steered_entropy: float,
    kl_val: float,
) -> Dict[str, float]:
    return {
        "baseline_entropy": round(baseline_entropy, 4),
        "steered_entropy": round(steered_entropy, 4),
        "entropy_delta": round(steered_entropy - baseline_entropy, 4),
        "kl_baseline_to_steered": round(kl_val, 4),
    }


# ---------------------------------------------------------------------------
# Unit tests: entropy / KL math
# ---------------------------------------------------------------------------
class TestEntropyKLMath:
    """Verify the formulas used in batch_steering_ct against reference."""

    def test_uniform_distribution_entropy(self):
        n = 256000
        probs = [1.0 / n] * n
        H = _entropy(probs)
        assert abs(H - math.log(n)) < 1e-4

    def test_peaked_distribution_entropy(self):
        probs = [0.999] + [0.001 / 99] * 99
        H = _entropy(probs)
        assert H < 0.1

    def test_identical_distributions_kl_is_zero(self):
        probs = [0.25, 0.25, 0.25, 0.25]
        assert abs(_kl(probs, probs)) < 1e-10

    def test_kl_is_nonnegative(self):
        p = [0.9, 0.05, 0.05]
        q = [0.1, 0.1, 0.8]
        assert _kl(p, q) >= 0

    def test_kl_asymmetry(self):
        p = [0.9, 0.05, 0.05]
        q = [0.1, 0.1, 0.8]
        assert abs(_kl(p, q) - _kl(q, p)) > 0.01

    def test_entropy_delta_sign_when_steered_more_uniform(self):
        p_peaked = [0.95, 0.025, 0.025]
        p_uniform = [1 / 3, 1 / 3, 1 / 3]
        assert _entropy(p_uniform) - _entropy(p_peaked) > 0

    def test_entropy_delta_sign_when_steered_more_peaked(self):
        p_uniform = [1 / 3, 1 / 3, 1 / 3]
        p_peaked = [0.95, 0.025, 0.025]
        assert _entropy(p_peaked) - _entropy(p_uniform) < 0


# ---------------------------------------------------------------------------
# Propagation: swap_evaluator copies position_0_distribution_metrics
# ---------------------------------------------------------------------------
class TestSwapEvaluatorPropagation:

    _FROM_ENTITY = {"state": "Kansas", "capital": "Topeka", "city": "Wichita"}
    _TO_ENTITY = {"state": "Oklahoma", "capital": "Oklahoma City", "city": "Tulsa"}

    def _make_result(self, dist_metrics=None) -> Dict[str, Any]:
        result = {
            "default": "The capital is Topeka.",
            "steered": "The capital is Oklahoma City.",
            "default_topk": [{"token": " Topeka", "prob": 0.8}],
            "steered_topk": [{"token": " Oklahoma", "prob": 0.6}],
        }
        if dist_metrics is not None:
            result["position_0_distribution_metrics"] = dist_metrics
        return result

    def test_metrics_propagated_when_present(self):
        dm = _make_dist_metrics(3.5, 5.2, 12.8)
        result = self._make_result(dist_metrics=dm)
        ev = evaluate_swap(result, self._FROM_ENTITY, self._TO_ENTITY)
        assert "position_0_distribution_metrics" in ev
        assert ev["position_0_distribution_metrics"] == dm

    def test_metrics_absent_when_missing(self):
        result = self._make_result()
        ev = evaluate_swap(result, self._FROM_ENTITY, self._TO_ENTITY)
        assert "position_0_distribution_metrics" not in ev


# ---------------------------------------------------------------------------
# Extraction: analyze_logit_trajectory flattens into metric keys
# ---------------------------------------------------------------------------
class TestExtractTrajectoryMetrics:

    def _make_eval_with_dist(self, dm) -> Dict[str, Any]:
        return {
            "evaluation": {
                "logit_trajectory": {
                    "summary": {
                        "flip_position": 0,
                        "initial_gap": -2.0,
                        "best_gap": 10.0,
                        "gap_closure": 12.0,
                        "control_stability_mean": 5.0,
                        "control_stability_max": 8.0,
                    },
                    "trajectories": {},
                    "contrast_groups": {},
                },
                "position_0_distribution_metrics": dm,
            }
        }

    def test_flat_keys_present(self):
        dm = _make_dist_metrics(3.5, 5.2, 12.8)
        result = self._make_eval_with_dist(dm)
        metrics = extract_trajectory_metrics(result)
        assert metrics["baseline_entropy_0"] == 3.5
        assert metrics["steered_entropy_0"] == 5.2
        assert abs(metrics["entropy_delta_0"] - 1.7) < 0.01
        assert metrics["kl_baseline_to_steered_0"] == 12.8

    def test_flat_keys_absent_when_no_dist_metrics(self):
        result = {
            "evaluation": {
                "logit_trajectory": {
                    "summary": {
                        "flip_position": 0,
                        "initial_gap": -2.0,
                        "best_gap": 10.0,
                        "gap_closure": 12.0,
                        "control_stability_mean": 5.0,
                        "control_stability_max": 8.0,
                    },
                    "trajectories": {},
                    "contrast_groups": {},
                },
            }
        }
        metrics = extract_trajectory_metrics(result)
        assert metrics.get("baseline_entropy_0") is None
        assert metrics.get("kl_baseline_to_steered_0") is None


# ---------------------------------------------------------------------------
# Aggregation: compute_trajectory_summary includes distribution_metrics
# ---------------------------------------------------------------------------
class TestComputeTrajectorySummary:

    def _make_results(self, dist_metrics_list):
        results = []
        for dm in dist_metrics_list:
            r = {
                "evaluation": {
                    "logit_trajectory": {
                        "summary": {
                            "flip_position": 0,
                            "initial_gap": -2.0,
                            "best_gap": 10.0,
                            "gap_closure": 12.0,
                            "control_stability_mean": 5.0,
                            "control_stability_max": 8.0,
                        },
                        "trajectories": {},
                        "contrast_groups": {},
                    },
                }
            }
            if dm is not None:
                r["evaluation"]["position_0_distribution_metrics"] = dm
            results.append(r)
        return results

    def test_aggregation_produces_distribution_section(self):
        dms = [
            _make_dist_metrics(3.0, 5.0, 10.0),
            _make_dist_metrics(4.0, 6.0, 15.0),
            _make_dist_metrics(3.5, 5.5, 12.0),
        ]
        results = self._make_results(dms)
        summary = compute_trajectory_summary(results)
        assert "distribution_metrics" in summary
        dm_agg = summary["distribution_metrics"]
        assert abs(dm_agg["baseline_entropy"]["mean"] - 3.5) < 0.01
        assert abs(dm_agg["steered_entropy"]["mean"] - 5.5) < 0.01
        assert abs(dm_agg["kl_baseline_to_steered"]["mean"] - 12.333) < 0.1

    def test_aggregation_absent_when_no_metrics(self):
        results = self._make_results([None, None])
        summary = compute_trajectory_summary(results)
        assert "distribution_metrics" not in summary

    def test_aggregation_handles_mixed_presence(self):
        dms = [
            _make_dist_metrics(3.0, 5.0, 10.0),
            None,
            _make_dist_metrics(4.0, 6.0, 15.0),
        ]
        results = self._make_results(dms)
        summary = compute_trajectory_summary(results)
        assert "distribution_metrics" in summary
        dm_agg = summary["distribution_metrics"]
        assert abs(dm_agg["kl_baseline_to_steered"]["mean"] - 12.5) < 0.01


# ---------------------------------------------------------------------------
# Edge cases: degenerate distributions
# ---------------------------------------------------------------------------
class TestEdgeCases:

    def test_entropy_of_deterministic_distribution(self):
        probs = [1.0] + [0.0] * 99
        H = _entropy(probs)
        assert abs(H) < 1e-10

    def test_kl_from_uniform_to_peaked(self):
        n = 100
        p_uniform = [1.0 / n] * n
        p_peaked = [0.0] * n
        p_peaked[0] = 1.0
        kl_val = _kl(p_uniform, p_peaked, eps=1e-10)
        assert kl_val > 0

    def test_entropy_delta_metrics_round_trip(self):
        dm = _make_dist_metrics(2.5, 4.0, 8.3)
        assert abs(dm["entropy_delta"] - (4.0 - 2.5)) < 0.01
        assert dm["kl_baseline_to_steered"] == 8.3
