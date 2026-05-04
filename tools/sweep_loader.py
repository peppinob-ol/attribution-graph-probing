"""
Aggregate intervention-strength sweep data for a single swap pair across
multiple ``output/usa_states_batch/_swaps/runs/<run>/`` directories.

Each per-run JSON at ``by_source/<src_slug>/to_<tgt_slug>.json`` contains a
``default_topk`` (M=0 baseline, identical across runs of the same pair) and a
``steered_topk`` produced at the run's ``M_amplify``. Reading every run that
contains the pair gives an offline sweep over intervention strength.

The caller passes the *primary* run dir (e.g. ``full_50states_v1``) and the
swap id, and we return a sorted ``SweepData`` with one ``SweepPoint`` per
``M_amplify`` value plus a synthetic baseline at ``M=0``.

Token tracking:
- "source token"  = first-token of source.capital (e.g. "Des Moines" -> " Des")
- "target token"  = first-token of target.capital (e.g. "Salt Lake City" -> " Salt")
- Probability is read from the topk arrays; tokens missing from a topk are
  reported as ``None`` so callers can decide whether to plot 0 or skip.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SweepPoint:
    """One point on the intervention-strength curve."""
    M_amplify: int
    run_id: str
    is_baseline: bool  # True for the synthetic M=0 point read from default_topk
    source_prob: float | None
    target_prob: float | None
    top1_token: str | None
    top1_prob: float | None
    topk: list[dict]  # the steered (or default) topk at this M


@dataclass
class SweepData:
    swap_id: str
    src_slug: str
    tgt_slug: str
    source_token: str  # the token name we tracked for the "before" curve
    target_token: str  # the token name we tracked for the "after" curve
    source_capital: str
    target_capital: str
    primary_M: int  # M of the run we're rendering ("highlight" marker)
    points: list[SweepPoint] = field(default_factory=list)
    auto_decay_token: str | None = None  # top-1 of baseline (default_topk)
    auto_decay_curve: list[float | None] = field(default_factory=list)
    auto_grow_token: str | None = None   # token whose prob grows most across M
    auto_grow_curve: list[float | None] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _first_token_for(word: str, topk_to_disambiguate: list[dict] | None = None) -> str:
    """Best-effort guess of the leading-space token Gemma uses for ``word``.

    We have no tokenizer at hand, so we approximate as ``" " + first_word``.
    If a topk has any token starting with that prefix we use it as-is; this
    handles the rare case where the model splits "Des Moines" into " Des" or
    "Salt Lake City" into " Salt".
    """
    head = word.split(" ", 1)[0]
    candidate = f" {head}"
    if topk_to_disambiguate:
        for entry in topk_to_disambiguate:
            tok = entry.get("token", "")
            if tok == candidate or tok.lstrip() == head:
                return tok
    return candidate


def _prob_for_token(topk: list[dict], token: str) -> float | None:
    """Find ``token`` in topk; return its probability, or ``None`` if absent."""
    for entry in topk:
        if entry.get("token") == token:
            return float(entry.get("prob", 0.0))
    return None


def _read_run_M_amplify(run_dir: Path) -> int | None:
    """Read ``M_amplify`` from ``run_manifest.json``'s ``config.ct_steering``."""
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    cfg = (manifest.get("config") or {}).get("ct_steering") or {}
    M = cfg.get("M_amplify")
    return int(M) if M is not None else None


# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #


def collect_sweep_data(
    primary_run_dir: str | Path,
    swap_id: str,
    *,
    runs_root: str | Path | None = None,
) -> SweepData:
    """Walk every sibling run dir and assemble per-M topk data for this pair.

    Args:
        primary_run_dir: the run we're rendering (used to determine ``primary_M``).
        swap_id: ``<src_slug>__to__<tgt_slug>``.
        runs_root: directory containing all runs (default: parent of primary).

    Returns:
        A populated ``SweepData``. ``points`` is sorted by ``M_amplify``
        ascending and starts with a synthetic baseline at ``M=0``.
    """
    primary_run_dir = Path(primary_run_dir)
    runs_root = Path(runs_root) if runs_root else primary_run_dir.parent
    src_slug, _, tgt_slug = swap_id.partition("__to__")
    if not (src_slug and tgt_slug):
        raise ValueError(f"swap_id must be '<src>__to__<tgt>', got {swap_id!r}")

    primary_M = _read_run_M_amplify(primary_run_dir) or 20

    # Collect candidate per-run files for this exact pair.
    matches: list[tuple[int, str, dict]] = []  # (M_amplify, run_id, result_dict)
    primary_data: dict | None = None
    for run_dir in sorted(runs_root.iterdir()):
        if not run_dir.is_dir():
            continue
        result_path = run_dir / "by_source" / src_slug / f"to_{tgt_slug}.json"
        if not result_path.exists():
            continue
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        M = _read_run_M_amplify(run_dir)
        if M is None:
            continue
        matches.append((M, run_dir.name, data))
        if run_dir == primary_run_dir:
            primary_data = data

    if primary_data is None and matches:
        primary_data = matches[0][2]

    if primary_data is None:
        raise FileNotFoundError(
            f"No run dir under {runs_root} contains by_source/{src_slug}/to_{tgt_slug}.json"
        )

    # Identify source/target capitals + the tokens we track on the curve.
    src_meta = primary_data.get("source") or {}
    tgt_meta = primary_data.get("target") or {}
    src_capital = src_meta.get("capital", "")
    tgt_capital = tgt_meta.get("capital", "")

    # Disambiguate tokens against the topk that's most likely to contain them.
    default_topk = (primary_data.get("evaluation") or {}).get("raw", {}).get("default_topk", [])
    src_tok = _first_token_for(src_capital, topk_to_disambiguate=default_topk) if src_capital else (
        primary_data.get("evaluation", {}).get("first_token", {}).get("default", "")
    )
    # For the target, try the steered topk of the highest-M run we have.
    highest_M_topk: list[dict] = []
    if matches:
        highest = max(matches, key=lambda t: t[0])
        highest_M_topk = (highest[2].get("evaluation") or {}).get("raw", {}).get("steered_topk", [])
    tgt_tok = _first_token_for(tgt_capital, topk_to_disambiguate=highest_M_topk) if tgt_capital else (
        primary_data.get("evaluation", {}).get("first_token", {}).get("steered", "")
    )

    # Synthesize the baseline (M=0) point from the default topk.
    baseline_point = SweepPoint(
        M_amplify=0,
        run_id="(baseline)",
        is_baseline=True,
        source_prob=_prob_for_token(default_topk, src_tok),
        target_prob=_prob_for_token(default_topk, tgt_tok),
        top1_token=default_topk[0].get("token") if default_topk else None,
        top1_prob=float(default_topk[0].get("prob", 0.0)) if default_topk else None,
        topk=default_topk,
    )

    points: list[SweepPoint] = [baseline_point]
    seen_M: set[int] = {0}
    for M, run_id, data in sorted(matches, key=lambda t: t[0]):
        if M in seen_M:
            continue
        seen_M.add(M)
        steered_topk = (data.get("evaluation") or {}).get("raw", {}).get("steered_topk", [])
        points.append(
            SweepPoint(
                M_amplify=M,
                run_id=run_id,
                is_baseline=False,
                source_prob=_prob_for_token(steered_topk, src_tok),
                target_prob=_prob_for_token(steered_topk, tgt_tok),
                top1_token=steered_topk[0].get("token") if steered_topk else None,
                top1_prob=float(steered_topk[0].get("prob", 0.0)) if steered_topk else None,
                topk=steered_topk,
            )
        )

    # Auto-pick decay/grow tokens for the sweep plot:
    # - decay = baseline top-1 (matches the "ORIGINAL PREDICTION" header)
    # - grow  = primary run's steered top-1 (matches the "AFTER INTERVENTION" header)
    # Falling back to a max-growth heuristic when either is missing.
    decay_tok = points[0].top1_token
    decay_curve: list[float | None] = (
        [_prob_for_token(p.topk, decay_tok) for p in points] if decay_tok else []
    )

    grow_tok: str | None = None
    grow_curve: list[float | None] = []
    primary_steered_topk = (primary_data.get("evaluation") or {}).get("raw", {}).get(
        "steered_topk", []
    )
    if primary_steered_topk:
        grow_tok = primary_steered_topk[0].get("token")
    if grow_tok:
        grow_curve = [_prob_for_token(p.topk, grow_tok) for p in points]

    # If the auto-grow token matches the decay token (rare: original and after
    # are the same token, e.g. Salem -> Salem), drop the duplicate so the
    # renderer only draws one curve.
    if grow_tok and grow_tok == decay_tok:
        grow_tok = None
        grow_curve = []
    # Fallback: if we still don't have a grow token, search for the most-grown
    # token across all runs (excluding decay).
    elif not grow_tok:
        candidate_tokens: set[str] = set()
        for p in points[1:]:
            for entry in p.topk:
                tok = entry.get("token")
                if tok and tok != decay_tok:
                    candidate_tokens.add(tok)
        best_score = -1.0
        for tok in candidate_tokens:
            probs: list[float | None] = [_prob_for_token(p.topk, tok) for p in points]
            finals = [pr for pr in probs[1:] if pr is not None]
            if not finals:
                continue
            score = max(finals) * (len(finals) / max(1, len(points) - 1))
            if score > best_score:
                best_score = score
                grow_tok = tok
                grow_curve = probs

    return SweepData(
        swap_id=swap_id,
        src_slug=src_slug,
        tgt_slug=tgt_slug,
        source_token=src_tok,
        target_token=tgt_tok,
        source_capital=src_capital,
        target_capital=tgt_capital,
        primary_M=primary_M,
        points=points,
        auto_decay_token=decay_tok,
        auto_decay_curve=decay_curve,
        auto_grow_token=grow_tok,
        auto_grow_curve=grow_curve,
    )
