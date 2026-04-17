"""
Two-phase adaptive M_amplify search for missed swap pairs.

Phase 1 (coarse geometric probe): tests ~6 log-spaced M values from
m_min to m_original, stopping at the first hit.

Phase 2 (fine binary search at KL transition): only runs when Phase 1
found zero hits. Identifies where KL transitions from high to moderate
between adjacent probes and bisects that region in log-space.
"""
from __future__ import annotations

import copy
import json
import math
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


SteerResult = Dict[str, Any]


def _patch_features_m(features: List[Dict[str, Any]], m_amplify: float) -> List[Dict[str, Any]]:
    """Return a deep copy of *features* with amplify M values set to *m_amplify*.

    Only patches features that are genuine amplifications (M > 0).
    Features with negative M (source ablations) are left unchanged
    even when ``ablate`` is False -- the negative M itself signals
    ablation intent in the labeled intervention builder.
    """
    patched = []
    for f in features:
        f2 = dict(f)
        orig_m = f2.get("M", 0)
        is_ablation = f2.get("ablate", False) or (isinstance(orig_m, (int, float)) and orig_m < 0)
        if not is_ablation:
            f2["M"] = m_amplify
        patched.append(f2)
    return patched


def _extract_hit_kl(evaluation: Dict[str, Any]) -> Tuple[bool, Optional[float]]:
    """Extract (hit, kl) from an evaluation dict."""
    exact = evaluation.get("exact_match", {})
    hit = bool(exact.get("steered_has_to_answer", False))
    dist = evaluation.get("position_0_distribution_metrics") or {}
    kl = dist.get("kl_baseline_to_steered")
    return hit, kl


def _geomspace(m_min: float, m_max: float, n: int) -> List[float]:
    """Return *n* log-spaced values from *m_min* to *m_max* inclusive."""
    if n <= 1:
        return [m_max]
    log_min = math.log10(m_min)
    log_max = math.log10(m_max)
    step = (log_max - log_min) / (n - 1)
    return [10 ** (log_min + i * step) for i in range(n)]


# ------------------------------------------------------------------
# Phase 1
# ------------------------------------------------------------------

def coarse_probe(
    steer_fn: Callable[[float], Tuple[bool, Optional[float], SteerResult]],
    m_original: float,
    m_min: float = 0.1,
    n_probes: int = 6,
) -> Tuple[Optional[SteerResult], List[Dict[str, Any]]]:
    """Run coarse geometric probe, low-to-high, stopping at first hit.

    Returns:
        (best_result_or_None, probe_log)
        *probe_log* always contains all probes that were actually run.
    """
    probe_values = _geomspace(m_min, m_original, n_probes)
    probe_log: List[Dict[str, Any]] = []

    for m_val in probe_values:
        hit, kl, result = steer_fn(m_val)
        entry = {"m": round(m_val, 6), "hit": hit, "kl": kl}
        probe_log.append(entry)
        logger.info("  coarse_probe M=%.4f  hit=%s  kl=%s", m_val, hit, kl)
        if hit:
            return result, probe_log

    return None, probe_log


# ------------------------------------------------------------------
# Phase 2
# ------------------------------------------------------------------

def _find_best_kl_transition(
    probes: List[Dict[str, Any]],
    min_kl_drop: float = 1.0,
) -> Optional[Tuple[float, float, float]]:
    """Find the adjacent probe pair with the steepest KL drop (high->low M).

    Returns (m_lo, m_hi, kl_drop) or None if no clear transition exists.
    """
    sorted_probes = sorted(probes, key=lambda p: p["m"])
    best: Optional[Tuple[float, float, float]] = None

    for i in range(len(sorted_probes) - 1):
        lo = sorted_probes[i]
        hi = sorted_probes[i + 1]
        kl_lo = lo.get("kl")
        kl_hi = hi.get("kl")
        if kl_lo is None or kl_hi is None:
            continue
        drop = kl_hi - kl_lo
        if drop >= min_kl_drop and (best is None or drop > best[2]):
            best = (lo["m"], hi["m"], drop)

    return best


def fine_search_at_kl_transition(
    steer_fn: Callable[[float], Tuple[bool, Optional[float], SteerResult]],
    probes: List[Dict[str, Any]],
    max_steps: int = 6,
    log_tolerance: float = 0.1,
    min_kl_drop: float = 1.0,
) -> Tuple[Optional[SteerResult], List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Binary search in log-space within the steepest KL transition zone.

    Returns:
        (best_result_or_None, step_log, kl_transition_info)
    """
    transition = _find_best_kl_transition(probes, min_kl_drop=min_kl_drop)
    if transition is None:
        logger.info("  fine_search: no KL transition found -- skipping")
        return None, [], None

    m_lo, m_hi, kl_drop = transition
    kl_transition_info = {
        "m_lo": round(m_lo, 6),
        "m_hi": round(m_hi, 6),
        "kl_drop": round(kl_drop, 4),
    }
    logger.info(
        "  fine_search: targeting KL transition [%.4f, %.4f] (drop=%.2f)",
        m_lo, m_hi, kl_drop,
    )

    log_lo = math.log10(m_lo)
    log_hi = math.log10(m_hi)
    step_log: List[Dict[str, Any]] = []
    best_result: Optional[SteerResult] = None

    for _ in range(max_steps):
        if log_hi - log_lo < log_tolerance:
            break
        log_mid = (log_lo + log_hi) / 2
        m_mid = 10 ** log_mid

        hit, kl, result = steer_fn(m_mid)
        entry = {"m": round(m_mid, 6), "hit": hit, "kl": kl}
        step_log.append(entry)
        logger.info("  fine_search M=%.4f  hit=%s  kl=%s", m_mid, hit, kl)

        if hit:
            best_result = result
            break

        if kl is not None and kl >= (probes[-1].get("kl") or 0):
            log_hi = log_mid
        else:
            log_lo = log_mid

    return best_result, step_log, kl_transition_info


# ------------------------------------------------------------------
# Orchestrator
# ------------------------------------------------------------------

def search_optimal_m(
    steer_fn_factory: Callable[..., Callable[[float], Tuple[bool, Optional[float], SteerResult]]],
    baseline_result: Optional[Dict[str, Any]],
    m_original: float,
    *,
    m_min: float = 0.1,
    n_coarse_probes: int = 6,
    n_fine_steps: int = 6,
    log_tolerance: float = 0.1,
    min_kl_drop: float = 1.0,
) -> Optional[Dict[str, Any]]:
    """Two-phase adaptive search for the best M_amplify.

    Args:
        steer_fn_factory: callable that returns a ``steer_fn(m) -> (hit, kl, result)``
            closure. Called once so the caller can lazily set up resources.
        baseline_result: the saved swap result at *m_original* (may be None).
        m_original: the config-level M_amplify that produced the baseline miss.
        m_min: lowest M to probe.
        n_coarse_probes: number of Phase 1 log-spaced probes.
        n_fine_steps: max Phase 2 binary-search steps.
        log_tolerance: convergence threshold in log10(M) space.
        min_kl_drop: minimum KL drop between adjacent probes to trigger Phase 2.

    Returns:
        The best result dict (with ``m_search`` metadata) or None.
    """
    if baseline_result is not None:
        eval_ = baseline_result.get("evaluation", {})
        hit, _ = _extract_hit_kl(eval_)
        if hit:
            return None

    steer_fn = steer_fn_factory()

    # Phase 1
    phase1_result, probe_log = coarse_probe(
        steer_fn, m_original, m_min=m_min, n_probes=n_coarse_probes,
    )

    if phase1_result is not None:
        winning_m = next(p["m"] for p in probe_log if p["hit"])
        phase1_result["m_search"] = {
            "m_original": m_original,
            "m_tuned": winning_m,
            "phase": 1,
            "total_steps": len(probe_log),
            "phase1_probes": probe_log,
            "phase2_steps": [],
            "kl_transition": None,
        }
        return phase1_result

    # Phase 2
    phase2_result, step_log, kl_transition = fine_search_at_kl_transition(
        steer_fn, probe_log,
        max_steps=n_fine_steps,
        log_tolerance=log_tolerance,
        min_kl_drop=min_kl_drop,
    )

    total_steps = len(probe_log) + len(step_log)

    if phase2_result is not None:
        winning_m = next(s["m"] for s in step_log if s["hit"])
        phase2_result["m_search"] = {
            "m_original": m_original,
            "m_tuned": winning_m,
            "phase": 2,
            "total_steps": total_steps,
            "phase1_probes": probe_log,
            "phase2_steps": step_log,
            "kl_transition": kl_transition,
        }
        return phase2_result

    logger.info(
        "  m_search: no hit found in %d steps -- pair is a specificity failure",
        total_steps,
    )
    return None


# ------------------------------------------------------------------
# Integration helper for run_batch_swaps
# ------------------------------------------------------------------

def build_steer_fn(
    *,
    features: List[Dict[str, Any]],
    prompt: str,
    pair: Any,
    config: Dict[str, Any],
    work_dir: Path,
    evaluate_swap_fn: Callable,
    run_steering_fn: Callable,
    gpu_id: Optional[int] = None,
    verbose: bool = False,
) -> Callable[[float], Tuple[bool, Optional[float], SteerResult]]:
    """Build a steer_fn(m) closure for use with search_optimal_m.

    ``run_steering_fn`` must match the signature of ``_run_local_ct_steering``
    from run_batch_swaps.py.  ``evaluate_swap_fn`` must match ``evaluate_swap``.
    """
    ct_config = config.get("ct_steering", {})
    swap_cfg = config.get("swap", {})
    concept_fields = swap_cfg.get("concept_fields")

    steering_cfg = {
        "transcoder_set": ct_config.get("transcoder_set", "mntss/clt-gemma-2-2b-2.5M"),
        "temperature": ct_config.get("temperature", 0.3),
        "n_tokens": ct_config.get("n_tokens", 6),
        "freq_penalty": ct_config.get("freq_penalty", 2.0),
        "seed": ct_config.get("seed", 42),
        "top_k": ct_config.get("top_k", 5),
        "freeze_attention": ct_config.get("freeze_attention", False),
        "track_trajectory": False,
    }

    msearch_work = work_dir / "_m_search"
    msearch_work.mkdir(parents=True, exist_ok=True)

    prompts_path = msearch_work / "prompts.json"
    prompts_data = [{"id": "m_search_prompt", "text": prompt}]
    with open(prompts_path, "w", encoding="utf-8") as f:
        json.dump(prompts_data, f, indent=2)

    call_counter = [0]

    def steer_fn(m_value: float) -> Tuple[bool, Optional[float], SteerResult]:
        idx = call_counter[0]
        call_counter[0] += 1

        patched = _patch_features_m(features, m_value)

        features_path = msearch_work / f"features_{idx}.json"
        output_path = msearch_work / f"steering_dump_{idx}.json"
        with open(features_path, "w", encoding="utf-8") as f:
            json.dump(patched, f)

        ok = run_steering_fn(
            ct_config, steering_cfg, prompts_path, features_path, output_path,
            gpu_id=gpu_id, verbose=verbose,
        )
        if not ok:
            return False, None, {}

        try:
            with open(output_path, "r", encoding="utf-8") as f:
                dump = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return False, None, {}

        results_list = dump.get("results", [])
        if not results_list:
            return False, None, {}

        raw = results_list[0]
        raw["prompt"] = prompt
        raw["ablate_count"] = sum(1 for ft in patched if ft.get("ablate", False))
        raw["amplify_count"] = sum(1 for ft in patched if not ft.get("ablate", False))

        evaluation = evaluate_swap_fn(
            raw, pair.from_entity, pair.to_entity, concept_fields, swap_cfg=swap_cfg,
        )
        hit, kl = _extract_hit_kl(evaluation)

        cfg_copy = copy.deepcopy(config)
        cfg_copy.setdefault("ct_steering", {})["M_amplify"] = m_value

        from .swap_evaluator import create_swap_result
        result = create_swap_result(
            pair, raw, evaluation, cfg_copy, duration_ms=0,
        )
        return hit, kl, result

    return steer_fn
