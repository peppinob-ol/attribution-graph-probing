#!/usr/bin/env python3
"""
Top-k feature steering study (batch mode).

Creates a single batch with all (pair, k, M) combinations as separate prompts,
runs batch_steering_ct.py ONCE, then evaluates all results.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "experiments" / "batch"))

from pipeline.swap_evaluator import evaluate_swap


def load_graph_influence(graph_dir: Path) -> Dict[Tuple[int, int], float]:
    """Load per-(layer, feature_index) influence from graph.json."""
    graph_path = graph_dir / "00 Graph Generation" / "graph.json"
    graph = json.loads(graph_path.read_text())
    influence: Dict[Tuple[int, int], float] = {}
    for node in graph["nodes"]:
        parts = node["node_id"].split("_")
        if len(parts) != 3:
            continue
        try:
            layer, feat_idx = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        inf = node.get("influence")
        if inf is None:
            continue
        key = (layer, feat_idx)
        influence[key] = max(influence.get(key, 0), float(inf))
    return influence


def get_prompt_for_entity(output_root: Path, slug: str) -> Optional[str]:
    """Get the prompt from graph metadata."""
    graph_path = output_root / slug / "00 Graph Generation" / "graph.json"
    if not graph_path.exists():
        return None
    graph = json.loads(graph_path.read_text())
    return graph.get("metadata", {}).get("prompt")


def filter_topk_features(
    features: List[Dict[str, Any]],
    influence: Dict[Tuple[int, int], float],
    top_k: int,
    m_amplify: float,
) -> List[Dict[str, Any]]:
    """Keep all ablate features; keep only top-k amplify by influence, set M."""
    ablate = [f for f in features if f.get("M", 0) < 0]
    amplify = [f for f in features if f.get("M", 0) > 0]

    for f in amplify:
        f["_influence"] = influence.get((f["layer"], f["index"]), 0.0)

    amplify.sort(key=lambda f: f["_influence"], reverse=True)
    selected = amplify[:top_k]

    result = list(ablate)
    for f in selected:
        entry = {k: v for k, v in f.items() if not k.startswith("_")}
        entry["M"] = m_amplify
        result.append(entry)
    return result


def main():
    import argparse
    import yaml

    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--baseline-run", required=True)
    parser.add_argument("--source-config", required=True)
    parser.add_argument("--pairs", required=True, help="from:to,from:to,...")
    parser.add_argument("--top-k", default="1,3,5,10,67")
    parser.add_argument("--m-values", default="20,50,100,200")
    parser.add_argument("--answer-field", default="founder")
    args = parser.parse_args()

    output_root = REPO_ROOT / "output" / args.dataset
    pairs = [p.split(":") for p in args.pairs.split(",")]
    top_k_values = [int(x) for x in args.top_k.split(",")]
    m_values = [float(x) for x in args.m_values.split(",")]

    source_cfg = yaml.safe_load(Path(args.source_config).read_text())
    entity_items = (
        source_cfg.get("graph_generation", {})
        .get("templated", {}).get("entities", {}).get("items", [])
    )
    entities_by_slug = {e["slug"]: e for e in entity_items}
    print(f"Loaded {len(entities_by_slug)} entities")

    out_dir = output_root / "_swaps" / "runs" / "topk_study"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build batch: one "prompt" per (pair, k, M) combination
    all_prompts = []
    per_prompt_features: Dict[str, List[Dict[str, Any]]] = {}
    job_index: List[Dict[str, Any]] = []

    for from_slug, to_slug in pairs:
        features_path = (
            output_root / "_swaps" / "runs" / args.baseline_run
            / "work" / f"{from_slug}__to__{to_slug}" / "features.json"
        )
        if not features_path.exists():
            print(f"SKIP {from_slug}->{to_slug}: no features.json")
            continue

        base_features = json.loads(features_path.read_text())
        n_amplify = sum(1 for f in base_features if f.get("M", 0) > 0)

        prompt_text = get_prompt_for_entity(output_root, from_slug)
        if not prompt_text:
            print(f"SKIP {from_slug}->{to_slug}: no prompt")
            continue

        influence = load_graph_influence(output_root / to_slug)

        from_entity = entities_by_slug.get(from_slug, {"slug": from_slug})
        to_entity = entities_by_slug.get(to_slug, {"slug": to_slug})
        target_ans = to_entity.get(args.answer_field, "")
        source_ans = from_entity.get(args.answer_field, "")
        contrast = [
            e.get(args.answer_field, "")
            for e in entities_by_slug.values()
            if e.get(args.answer_field) and e.get(args.answer_field) not in (target_ans, source_ans)
        ]

        for k in top_k_values:
            if k > n_amplify:
                continue
            for m in m_values:
                pid = f"{from_slug}__{to_slug}__k{k}__m{int(m)}"
                filtered = filter_topk_features(base_features, influence, k, m)

                prompt_entry = {
                    "id": pid,
                    "text": prompt_text,
                    "target_token": target_ans,
                    "source_token": source_ans,
                    "contrast_tokens": contrast,
                }
                all_prompts.append(prompt_entry)
                per_prompt_features[pid] = filtered

                job_index.append({
                    "prompt_id": pid,
                    "from_slug": from_slug,
                    "to_slug": to_slug,
                    "top_k": k,
                    "M": m,
                    "n_amplify": sum(1 for f in filtered if f.get("M", 0) > 0),
                    "n_ablate": sum(1 for f in filtered if f.get("M", 0) < 0),
                })

        print(f"  {from_slug}->{to_slug}: {n_amplify} amplify features, "
              f"{len([j for j in job_index if j['from_slug']==from_slug])} jobs queued")

    print(f"\nTotal batch size: {len(all_prompts)} prompts")
    if not all_prompts:
        print("Nothing to run.")
        return

    # Write batch files
    prompts_path = out_dir / "prompts.json"
    features_path = out_dir / "features.json"
    output_path = out_dir / "steering_dump.json"

    with open(prompts_path, "w") as f:
        json.dump(all_prompts, f, indent=2)
    with open(features_path, "w") as f:
        json.dump({"global": [], "per_prompt": per_prompt_features}, f)

    # Run batch_steering_ct.py
    script_path = REPO_ROOT / "scripts" / "neuronpedia_steering" / "batch_steering_ct.py"
    env = os.environ.copy()
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip())

    env["MODEL_ID"] = "google/gemma-2-2b"
    env["TRANSCODER_SET"] = "mntss/clt-gemma-2-2b-2.5M"
    env["PROMPTS_JSON_PATH"] = str(prompts_path)
    env["FEATURES_JSON_PATH"] = str(features_path)
    env["OUT_JSON_PATH"] = str(output_path)
    env["STEER_TEMPERATURE"] = "0.3"
    env["STEER_N_TOKENS"] = "10"
    env["STEER_FREQ_PENALTY"] = "2.0"
    env["STEER_SEED"] = "42"
    env["STEER_TOP_K"] = "5"

    print(f"\nLaunching batch_steering_ct.py with {len(all_prompts)} prompts...")
    result = subprocess.run(
        [sys.executable, str(script_path)],
        env=env,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    if result.returncode != 0:
        print(f"STEERING FAILED:\n{result.stderr[-500:]}")
        return

    print("Steering complete. Evaluating results...")

    # Load results
    raw_data = json.loads(output_path.read_text())
    raw_results = raw_data.get("results", raw_data) if isinstance(raw_data, dict) else raw_data
    if isinstance(raw_results, list):
        results_by_id = {r.get("probe_id", r.get("prompt_id", r.get("id", str(i)))): r for i, r in enumerate(raw_results)}
    elif isinstance(raw_results, dict):
        results_by_id = raw_results
    else:
        print(f"Unexpected results format: {type(raw_results)}")
        return

    # Evaluate each job
    eval_results = []
    for job in job_index:
        pid = job["prompt_id"]
        steer_result = results_by_id.get(pid)
        if steer_result is None:
            print(f"  WARNING: no result for {pid}")
            eval_results.append({**job, "hit": None, "error": True})
            continue

        from_ent = entities_by_slug.get(job["from_slug"], {"slug": job["from_slug"]})
        to_ent = entities_by_slug.get(job["to_slug"], {"slug": job["to_slug"]})
        ev = evaluate_swap(steer_result, from_ent, to_ent)

        hit = ev.get("steered_has_to_answer", False)
        topk = steer_result.get("steered_topk") or [{}]
        first_tok = topk[0].get("token", "?")
        dist = ev.get("position_0_distribution_metrics", {})
        kl = dist.get("kl_baseline_to_steered")
        gen = steer_result.get("steered", "")

        eval_results.append({
            **job,
            "hit": hit,
            "first_token": first_tok,
            "kl": kl,
            "gen_snippet": gen[30:80],
            "steered_output": gen,
        })

    # Print summary
    print(f"\n{'='*70}")
    print("RESULTS TABLE")
    print(f"{'='*70}")
    print(f"{'Pair':<30} {'k':>3} {'M':>4} {'Hit':>4} {'1st token':>15} {'KL':>6}  Gen snippet")
    print("-" * 100)
    for r in eval_results:
        hit_s = "HIT" if r.get("hit") else ("ERR" if r.get("error") else "   ")
        kl_s = f"{r['kl']:.1f}" if r.get("kl") is not None else "-"
        tok = r.get("first_token", "?")[:15]
        gen = r.get("gen_snippet", "")[:40]
        print(f"  {r['from_slug']}->{r['to_slug']:<14} {r['top_k']:>3} {int(r['M']):>4} {hit_s:>4} {tok:>15} {kl_s:>6}  {gen}")

    print(f"\n{'='*70}")
    print("SUMMARY BY (k, M)")
    print(f"{'='*70}")
    for k in top_k_values:
        for m in m_values:
            subset = [r for r in eval_results if r["top_k"] == k and r["M"] == m and r.get("hit") is not None]
            hits = sum(1 for r in subset if r["hit"])
            total = len(subset)
            if total:
                print(f"  top-{k:>2}  M={int(m):>3}  {hits}/{total} hits ({100*hits/total:.0f}%)")

    summary_path = out_dir / "eval_results.json"
    with open(summary_path, "w") as f:
        json.dump(eval_results, f, indent=2)
    print(f"\nSaved to {summary_path}")


if __name__ == "__main__":
    main()
