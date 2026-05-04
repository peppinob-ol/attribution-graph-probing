#!/usr/bin/env python3
"""
Batch swap experiment runner.

Runs CT steering experiments that swap state concepts across pre-computed graphs.
For each source prompt, ablates source state features and amplifies target state features.

Usage:
    # Dry run (validate config and show plan)
    python run_batch_swaps.py --config configs/usa_states_swap.yml --dry-run
    
    # Run full matrix (2500 experiments)
    python run_batch_swaps.py --config configs/usa_states_swap.yml
    
    # Run specific pair only
    python run_batch_swaps.py --config configs/usa_states_swap.yml --pair texas_dallas:california_oakland
    
    # Run with an explicit run_id (recommended for resumability)
    python run_batch_swaps.py --config configs/usa_states_swap.yml --run-id my_run

    # Force re-run within the SAME run directory (overwrites results in that run)
    python run_batch_swaps.py --config configs/usa_states_swap.yml --run-id my_run --force

Prerequisites:
    - Run usa_states_full.yml first to generate graphs
    - All states must have: graph.json, node_grouping.csv, metrics.csv
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add parent to path for imports
SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SCRIPT_DIR.parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from pipeline.swap_loader import (
    SwapPair,
    load_swap_config,
    resolve_swap_pairs,
    validate_swap_inputs,
    get_swap_paths,
    get_swap_output_path,
    filter_existing_pairs,
)
from pipeline.swap_runs import (
    setup_swap_run_dir,
    write_run_artifacts,
)
from pipeline.graph_loader import load_graph_data
from pipeline.swap_evaluator import (
    evaluate_swap,
    create_swap_result,
    create_summary,
    aggregate_results_to_matrix,
    resolve_answer_field,
)
from pipeline.steering_remote_ct import process_remote_ct_steering_step
from pipeline.remote import create_control_master_from_config, SSHControlMaster
from pipeline.controls import create_intervention_builder
from pipeline.m_search import search_optimal_m, build_steer_fn


def _load_ct_steering_module():
    """Load 03_ct_steering.py module dynamically."""
    steering_path = SCRIPTS_DIR / "03_ct_steering.py"
    spec = importlib.util.spec_from_file_location("ct_steering", steering_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {steering_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["ct_steering"] = module
    spec.loader.exec_module(module)
    return module


def print_banner(text: str):
    """Print a section banner."""
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}")


def prepare_swap_features(
    ct_steering,
    config: Dict[str, Any],
    pair: SwapPair,
    data_from: Dict[str, Any],
    data_to: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], int, int, Dict[str, Any]]:
    """
    Prepare CT intervention features for a swap pair.

    Delegates to the control builder selected by ``config["control"]["mode"]``
    (defaults to ``"labeled"`` when absent).

    Returns:
        (features, ablate_count, amplify_count, control_metadata)
    """
    builder = create_intervention_builder(config)
    result = builder.build_for_pair(
        ct_steering=ct_steering,
        config=config,
        pair=pair,
        data_from=data_from,
        data_to=data_to,
    )
    return result.features, result.ablate_count, result.amplify_count, result.to_metadata()


def _run_local_ct_steering(
    ct_config: Dict[str, Any],
    steering_cfg: Dict[str, Any],
    prompts_path: Path,
    features_path: Path,
    output_path: Path,
    gpu_id: Optional[int] = None,
    verbose: bool = True,
    timeout: int = 600,
) -> bool:
    """Run batch_steering_ct.py as a local subprocess."""
    script_path = SCRIPTS_DIR / 'neuronpedia_steering' / 'batch_steering_ct.py'
    if not script_path.exists():
        print(f"  ERROR: batch_steering_ct.py not found at {script_path}")
        return False

    env = os.environ.copy()
    # Load .env for HF_TOKEN etc. if not already set
    env_file = Path(__file__).resolve().parents[3] / '.env'
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                env.setdefault(k.strip(), v.strip())
    env['MODEL_ID'] = ct_config.get('model_id', 'google/gemma-2-2b')
    env['TRANSCODER_SET'] = steering_cfg.get('transcoder_set', 'mntss/clt-gemma-2-2b-2.5M')
    env['PROMPTS_JSON_PATH'] = str(prompts_path)
    env['FEATURES_JSON_PATH'] = str(features_path)
    env['OUT_JSON_PATH'] = str(output_path)
    env['STEER_TEMPERATURE'] = str(steering_cfg.get('temperature', 0.3))
    env['STEER_N_TOKENS'] = str(steering_cfg.get('n_tokens', 10))
    env['STEER_FREQ_PENALTY'] = str(steering_cfg.get('freq_penalty', 2.0))
    env['STEER_SEED'] = str(steering_cfg.get('seed', 42))
    env['TOP_K'] = str(steering_cfg.get('top_k', 5))
    env['FREEZE_ATTENTION'] = 'true' if steering_cfg.get('freeze_attention') else 'false'
    if steering_cfg.get('track_trajectory'):
        env['TRACK_TRAJECTORY'] = 'true'
        tt = steering_cfg.get('target_token')
        st = steering_cfg.get('source_token')
        if tt:
            env['TARGET_TOKEN'] = str(tt)
        if st:
            env['SOURCE_TOKEN'] = str(st)
    if gpu_id is not None:
        env['CUDA_VISIBLE_DEVICES'] = str(gpu_id)
    env.setdefault('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True')

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            env=env, capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            print(f"  ERROR: Local CT steering failed (rc={result.returncode})")
            if result.stderr:
                for line in result.stderr.strip().split('\n')[-5:]:
                    print(f"    {line}")
            return False
        if verbose and result.stdout:
            for line in result.stdout.strip().split('\n')[-3:]:
                print(f"    {line}")
        return True
    except subprocess.TimeoutExpired:
        print(f"  ERROR: Local CT steering timed out ({timeout}s)")
        return False
    except Exception as e:
        print(f"  ERROR: Local CT steering failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Batched local execution: prepare all pairs on CPU, then 1 subprocess/GPU
# ---------------------------------------------------------------------------

@dataclass
class _PreparedPair:
    """A pair whose prompts+features have been computed on CPU."""
    pair: SwapPair
    prompt: str
    features: List[Dict[str, Any]]
    ablate_count: int
    amplify_count: int
    control_metadata: Optional[Dict[str, Any]] = None
    variant_suffix: str = ""


def _expand_control_variants(config: Dict[str, Any]) -> List[Tuple[Dict[str, Any], str]]:
    """
    Expand control config into (modified_config, variant_suffix) tuples.

    For labeled mode or single-replicate controls, returns a single entry
    with no suffix.  For replicate controls, returns one entry per replicate.
    For additivity with multiple ``runs``, returns one entry per field/role
    subset variant.  For ``random_template_matched`` with ``runs``, returns
    one entry per template variant x replicate so the random null inherits
    the same field-subset search budget as labeled field-additivity runs.
    """
    import copy
    control_cfg = config.get("control", {})
    mode = control_cfg.get("mode", "labeled") if control_cfg else "labeled"
    replicates = control_cfg.get("replicates", 1)

    def _subset_suffix(run_spec: Dict[str, Any], idx: int) -> Tuple[Dict[str, Any], str]:
        """Turn a ``runs`` entry into (concept_subset_dict, human_suffix)."""
        fields = run_spec.get("fields")
        roles = run_spec.get("concept_subset", run_spec.get("roles"))
        if fields is not None:
            return {"fields": list(fields)}, "_".join(str(f) for f in fields)
        if roles is not None and isinstance(roles, list):
            return {"roles": list(roles)}, "_".join(str(r) for r in roles)
        return dict(run_spec), f"v{idx}"

    if mode == "additivity" and "runs" in control_cfg:
        variants = []
        for i, run_spec in enumerate(control_cfg["runs"]):
            cfg = copy.deepcopy(config)
            subset, suffix = _subset_suffix(run_spec, i)
            cfg["control"]["concept_subset"] = subset
            variants.append((cfg, f"add_{suffix}"))
        return variants

    if mode == "random_template_matched":
        runs = control_cfg.get("runs")
        reps = max(int(replicates), 1)
        if runs:
            variants = []
            for i, run_spec in enumerate(runs):
                subset, suffix = _subset_suffix(run_spec, i)
                for r in range(reps):
                    cfg = copy.deepcopy(config)
                    cfg["control"]["concept_subset"] = copy.deepcopy(subset)
                    cfg["control"]["_current_replicate"] = r
                    variant_tag = f"rtm_{suffix}__r{r}"
                    variants.append((cfg, variant_tag))
            return variants
        # No field-subset runs: just replicate the full template.
        if reps <= 1:
            return [(config, "")]
        variants = []
        for r in range(reps):
            cfg = copy.deepcopy(config)
            cfg["control"]["_current_replicate"] = r
            variants.append((cfg, f"rtm_full__r{r}"))
        return variants

    if replicates <= 1:
        return [(config, "")]

    variants = []
    for r in range(replicates):
        cfg = copy.deepcopy(config)
        cfg["control"]["_current_replicate"] = r
        variants.append((cfg, f"r{r}"))
    return variants


def _prepare_pairs_cpu(
    ct_steering,
    config: Dict[str, Any],
    pairs: List[SwapPair],
    verbose: bool = True,
) -> Tuple[List[_PreparedPair], List[SwapPair]]:
    """Prepare prompts and features for all pairs (CPU only, fast)."""
    variants = _expand_control_variants(config)
    prepared: List[_PreparedPair] = []
    skipped: List[SwapPair] = []

    for i, pair in enumerate(pairs):
        paths = get_swap_paths(config, pair)
        try:
            data_from = load_graph_data(paths['from_graph_dir'], verbose=False)
            data_to = (
                load_graph_data(paths['to_graph_dir'], verbose=False)
                if pair.from_slug != pair.to_slug
                else data_from
            )
        except FileNotFoundError as e:
            if verbose:
                print(f"  SKIP {pair.from_slug}->{pair.to_slug}: {e}")
            skipped.append(pair)
            continue

        prompt = data_from.get('prompt')
        if not prompt:
            skipped.append(pair)
            continue

        for variant_config, variant_suffix in variants:
            features, abl, amp, ctrl_meta = prepare_swap_features(
                ct_steering, variant_config, pair, data_from, data_to
            )
            if not features:
                if not variant_suffix:
                    skipped.append(pair)
                continue

            prepared.append(_PreparedPair(
                pair, prompt, features, abl, amp, ctrl_meta, variant_suffix,
            ))

    if verbose:
        print(f"  Prepared {len(prepared)} items ({len(pairs)} pairs x "
              f"{len(variants)} variant(s)), skipped {len(skipped)}")
    return prepared, skipped


def _run_gpu_batch(
    gpu_id: int,
    batch: List[_PreparedPair],
    config: Dict[str, Any],
    work_root: Path,
    verbose: bool = True,
) -> List[Tuple[_PreparedPair, Optional[Dict[str, Any]]]]:
    """Run a batch of prepared pairs on a single GPU (one model load)."""
    ct_config = config.get('ct_steering', {})
    swap_cfg = config.get('swap', {})
    concept_fields = swap_cfg.get('concept_fields')

    answer_field = resolve_answer_field(swap_cfg=swap_cfg, concept_fields=concept_fields)
    track_traj = ct_config.get('track_trajectory', False)

    # Pre-compute full roster of answer tokens for contrastive controls
    all_answer_tokens: List[str] = []
    if track_traj:
        entities = config.get('_entities', [])
        seen: set = set()
        for ent in entities:
            val = ent.get(answer_field, '')
            if val and val not in seen:
                all_answer_tokens.append(val)
                seen.add(val)

    batch_dir = work_root / f"_gpu_batch_{gpu_id}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    prompts = []
    per_prompt_features: Dict[str, List] = {}
    for pp in batch:
        pid = pp.pair.swap_id
        if pp.variant_suffix:
            pid = f"{pid}__{pp.variant_suffix}"
        entry: Dict[str, Any] = {"id": pid, "text": pp.prompt}
        if track_traj:
            target_ans = pp.pair.to_entity.get(answer_field, '')
            source_ans = pp.pair.from_entity.get(answer_field, '')
            entry["target_token"] = target_ans
            entry["source_token"] = source_ans
            if all_answer_tokens:
                exclude = {target_ans, source_ans}
                entry["contrast_tokens"] = [t for t in all_answer_tokens if t not in exclude]
        prompts.append(entry)
        per_prompt_features[pid] = pp.features

    prompts_path = batch_dir / "prompts.json"
    features_path = batch_dir / "features.json"
    output_path = batch_dir / "steering_dump.json"

    with open(prompts_path, "w", encoding="utf-8") as f:
        json.dump(prompts, f)
    with open(features_path, "w", encoding="utf-8") as f:
        json.dump({"global": [], "per_prompt": per_prompt_features}, f)

    steering_cfg = {
        'transcoder_set': ct_config.get('transcoder_set', 'mntss/clt-gemma-2-2b-2.5M'),
        'temperature': ct_config.get('temperature', 0.3),
        'n_tokens': ct_config.get('n_tokens', 10),
        'freq_penalty': ct_config.get('freq_penalty', 2.0),
        'seed': ct_config.get('seed', 42),
        'top_k': ct_config.get('top_k', 5),
        'freeze_attention': ct_config.get('freeze_attention', False),
        'track_trajectory': track_traj,
    }

    timeout = max(120, len(batch) * 30)
    ok = _run_local_ct_steering(
        ct_config, steering_cfg,
        prompts_path, features_path, output_path,
        gpu_id=gpu_id, verbose=verbose, timeout=timeout,
    )

    results: List[Tuple[_PreparedPair, Optional[Dict[str, Any]]]] = []
    if not ok:
        return [(pp, None) for pp in batch]

    try:
        with open(output_path, "r", encoding="utf-8") as f:
            dump = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return [(pp, None) for pp in batch]

    result_by_id = {r['probe_id']: r for r in dump.get('results', [])}
    for pp in batch:
        pid = pp.pair.swap_id
        if pp.variant_suffix:
            pid = f"{pid}__{pp.variant_suffix}"
        raw = result_by_id.get(pid)
        if raw is None:
            results.append((pp, None))
            continue
        raw['prompt'] = pp.prompt
        raw['ablate_count'] = pp.ablate_count
        raw['amplify_count'] = pp.amplify_count

        evaluation = evaluate_swap(raw, pp.pair.from_entity, pp.pair.to_entity, concept_fields, swap_cfg=swap_cfg)
        duration_ms = 0
        swap_result = create_swap_result(
            pp.pair, raw, evaluation, config, duration_ms,
            control_metadata=pp.control_metadata,
        )

        paths = get_swap_paths(config, pp.pair, pp.variant_suffix)
        out_file = paths['output_file']
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(swap_result, f, indent=2, ensure_ascii=False)

        per_swap_features_path = paths['work_dir'] / "features.json"
        per_swap_features_path.parent.mkdir(parents=True, exist_ok=True)
        with open(per_swap_features_path, "w", encoding="utf-8") as f:
            json.dump(pp.features, f, indent=2)

        results.append((pp, swap_result))

    # --- M-search second pass on missed pairs ---
    m_search_cfg = config.get("m_search", {})
    if m_search_cfg.get("enabled"):
        m_original = ct_config.get("M_amplify", 2.0)
        missed = [
            (pp, sr) for pp, sr in results
            if sr and not sr.get("evaluation", {}).get("exact_match", {}).get("steered_has_to_answer")
        ]
        if missed and verbose:
            print(f"  [M-search] Running adaptive search on {len(missed)} missed pairs...")
        for pp, sr in missed:
            pair_paths = get_swap_paths(config, pp.pair, pp.variant_suffix)

            def _factory(pp_=pp, pair_paths_=pair_paths):
                return build_steer_fn(
                    features=pp_.features,
                    prompt=pp_.prompt,
                    pair=pp_.pair,
                    config=config,
                    work_dir=pair_paths_['work_dir'],
                    evaluate_swap_fn=evaluate_swap,
                    run_steering_fn=_run_local_ct_steering,
                    gpu_id=gpu_id,
                    verbose=False,
                )

            tuned = search_optimal_m(
                _factory, sr, m_original,
                m_min=m_search_cfg.get("m_min", 0.1),
                n_coarse_probes=m_search_cfg.get("n_coarse_probes", 6),
                n_fine_steps=m_search_cfg.get("n_fine_steps", 6),
                log_tolerance=m_search_cfg.get("log_tolerance", 0.1),
                min_kl_drop=m_search_cfg.get("min_kl_drop", 1.0),
            )
            if tuned:
                suffix = f"{pp.variant_suffix}__m_tuned" if pp.variant_suffix else "m_tuned"
                tuned_path = get_swap_output_path(config, pp.pair, variant_suffix=suffix)
                tuned_path.parent.mkdir(parents=True, exist_ok=True)
                with open(tuned_path, "w", encoding="utf-8") as f:
                    json.dump(tuned, f, indent=2, ensure_ascii=False)
                if verbose:
                    m_info = tuned.get("m_search", {})
                    m_val = m_info.get("m_tuned")
                    m_str = f"{m_val:.4f}" if isinstance(m_val, (int, float)) else str(m_val)
                    print(f"    {pp.pair.from_slug}->{pp.pair.to_slug}: "
                          f"hit at M={m_str} "
                          f"(phase {m_info.get('phase')}, {m_info.get('total_steps')} steps)")

    return results


def run_single_swap(
    ct_steering,
    config: Dict[str, Any],
    pair: SwapPair,
    verbose: bool = True,
    control_socket: Optional[str] = None,
    variant_suffix: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Run a single swap experiment.

    Args:
        ct_steering: The ct_steering module
        config: Swap configuration
        pair: The swap pair to run
        verbose: Print progress
        control_socket: Optional SSH ControlMaster socket for connection reuse
        variant_suffix: Optional control-variant tag (e.g. ``"add_state"``).
            When non-empty, the output JSON and per-pair work directory are
            namespaced by this suffix so that different variants of the same
            pair do not overwrite each other.

    Returns:
        Complete result dict, or None if failed
    """
    paths = get_swap_paths(config, pair, variant_suffix=variant_suffix)
    start_time = time.time()
    
    if verbose:
        print(f"\n[SWAP] {pair.from_slug} -> {pair.to_slug}")
    
    # Load graph data
    try:
        data_from = load_graph_data(paths['from_graph_dir'], verbose=False)
        if pair.from_slug != pair.to_slug:
            data_to = load_graph_data(paths['to_graph_dir'], verbose=False)
        else:
            data_to = data_from  # Identity swap
    except FileNotFoundError as e:
        print(f"  ERROR: {e}")
        return None
    
    # Get prompt from source graph
    prompt = data_from.get('prompt')
    if not prompt:
        print(f"  ERROR: No prompt found in {paths['from_graph_dir']}")
        return None
    
    # Prepare features
    features, ablate_count, amplify_count, ctrl_meta = prepare_swap_features(
        ct_steering, config, pair, data_from, data_to
    )
    
    if not features:
        print(f"  ERROR: No features extracted")
        return None
    
    if verbose:
        print(f"  Features: {ablate_count} ablate + {amplify_count} amplify = {len(features)} total")
    
    # Prepare work directory and files
    work_dir = paths['work_dir']
    work_dir.mkdir(parents=True, exist_ok=True)
    
    prompts_path = work_dir / "prompts.json"
    features_path = work_dir / "features.json"
    output_path = work_dir / "steering_dump.json"
    
    # Execute steering
    ct_config = config.get('ct_steering', {})
    remote_config = config.get('compute', {}).get('remote', {})
    swap_cfg = config.get('swap', {})
    concept_fields = swap_cfg.get('concept_fields')
    answer_field = resolve_answer_field(swap_cfg=swap_cfg, concept_fields=concept_fields)

    target_ans = pair.to_entity.get(answer_field, '')
    source_ans = pair.from_entity.get(answer_field, '')

    # Build contrast token list from dataset entities
    contrast_tokens_list: Optional[List[str]] = None
    if ct_config.get('track_trajectory', False):
        entities = config.get('_entities', [])
        exclude = {target_ans, source_ans}
        seen: set = set()
        contrast_tokens_list = []
        for ent in entities:
            val = ent.get(answer_field, '')
            if val and val not in exclude and val not in seen:
                contrast_tokens_list.append(val)
                seen.add(val)
        if not contrast_tokens_list:
            contrast_tokens_list = None

    # Write prompts.json
    prompt_entry: Dict[str, Any] = {"id": "swap_prompt", "text": prompt}
    if ct_config.get('track_trajectory', False):
        prompt_entry["target_token"] = target_ans
        prompt_entry["source_token"] = source_ans
        if contrast_tokens_list:
            prompt_entry["contrast_tokens"] = contrast_tokens_list
    prompts = [prompt_entry]
    with open(prompts_path, "w", encoding="utf-8") as f:
        json.dump(prompts, f, indent=2)

    # Write features.json
    with open(features_path, "w", encoding="utf-8") as f:
        json.dump(features, f, indent=2)

    steering_cfg = {
        'transcoder_set': ct_config.get('transcoder_set', 'mntss/clt-gemma-2-2b-2.5M'),
        'temperature': ct_config.get('temperature', 0.3),
        'n_tokens': ct_config.get('n_tokens', 6),
        'freq_penalty': ct_config.get('freq_penalty', 2.0),
        'seed': ct_config.get('seed', 42),
        'top_k': ct_config.get('top_k', 5),
        'freeze_attention': ct_config.get('freeze_attention', False),
        'track_trajectory': ct_config.get('track_trajectory', False),
        'target_token': target_ans,
        'source_token': source_ans,
        'control_tokens': ct_config.get('control_tokens'),
    }

    if remote_config.get('enabled', False):
        remote_exec_config = {
            'model': {'id': ct_config.get('model_id', 'google/gemma-2-2b')},
            'compute': config.get('compute', {}),
            'ct_steering': steering_cfg,
        }
        local_paths = {
            'prompts_json': prompts_path,
            'steering_features_json': features_path,
            'steering_dump_json': output_path,
            'base': work_dir,
        }
        seed = {'slug': pair.swap_id}
        success, metadata = process_remote_ct_steering_step(
            remote_exec_config, seed, local_paths, verbose=verbose,
            control_socket=control_socket
        )
        if not success:
            print(f"  ERROR: Remote steering failed")
            return None
    else:
        success = _run_local_ct_steering(
            ct_config, steering_cfg, prompts_path, features_path, output_path,
            gpu_id=config.get('_local_gpu_id'),
            verbose=verbose,
        )
        if not success:
            return None
    
    # Load results
    if not output_path.exists():
        print(f"  ERROR: Output file not found: {output_path}")
        return None
    
    with open(output_path, "r", encoding="utf-8") as f:
        steering_result = json.load(f)
    
    # Extract first result
    results_list = steering_result.get('results', [])
    if not results_list:
        print(f"  ERROR: No results in steering output")
        return None
    
    raw_result = results_list[0]
    raw_result['prompt'] = prompt
    raw_result['ablate_count'] = ablate_count
    raw_result['amplify_count'] = amplify_count
    
    # Evaluate
    evaluation = evaluate_swap(raw_result, pair.from_entity, pair.to_entity, concept_fields, swap_cfg=swap_cfg)
    
    duration_ms = (time.time() - start_time) * 1000
    
    result = create_swap_result(
        pair, raw_result, evaluation, config, duration_ms,
        control_metadata=ctrl_meta,
    )
    
    output_file = paths['output_file']
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    if verbose:
        exact = evaluation['exact_match']
        print(f"  Default: {raw_result.get('default', '')[:50]}...")
        print(f"  Steered: {raw_result.get('steered', '')[:50]}...")
        print(f"  Suppressed: {exact['from_suppressed']}, Target hit: {exact['steered_has_to_answer']}")

    # --- M-search post-hook: adaptive M for missed pairs ---
    m_search_cfg = config.get("m_search", {})
    if m_search_cfg.get("enabled") and not evaluation['exact_match'].get('steered_has_to_answer'):
        m_original = ct_config.get("M_amplify", 2.0)

        def _factory():
            return build_steer_fn(
                features=features,
                prompt=prompt,
                pair=pair,
                config=config,
                work_dir=paths['work_dir'],
                evaluate_swap_fn=evaluate_swap,
                run_steering_fn=_run_local_ct_steering,
                gpu_id=config.get('_local_gpu_id'),
                verbose=False,
            )

        tuned = search_optimal_m(
            _factory, result, m_original,
            m_min=m_search_cfg.get("m_min", 0.1),
            n_coarse_probes=m_search_cfg.get("n_coarse_probes", 6),
            n_fine_steps=m_search_cfg.get("n_fine_steps", 6),
            log_tolerance=m_search_cfg.get("log_tolerance", 0.1),
            min_kl_drop=m_search_cfg.get("min_kl_drop", 1.0),
        )
        if tuned:
            tuned_suffix = f"{variant_suffix}__m_tuned" if variant_suffix else "m_tuned"
            tuned_path = get_swap_output_path(config, pair, variant_suffix=tuned_suffix)
            tuned_path.parent.mkdir(parents=True, exist_ok=True)
            with open(tuned_path, "w", encoding="utf-8") as f:
                json.dump(tuned, f, indent=2, ensure_ascii=False)
            m_info = tuned.get("m_search", {})
            if verbose:
                m_val = m_info.get("m_tuned")
                m_str = f"{m_val:.4f}" if isinstance(m_val, (int, float)) else str(m_val)
                print(f"  M-search: hit at M={m_str} "
                      f"(phase {m_info.get('phase')}, {m_info.get('total_steps')} steps)")

    return result


def run_swaps_parallel(
    ct_steering,
    config: Dict[str, Any],
    pairs: List[SwapPair],
    max_workers: int = 8,
    verbose: bool = True,
    control_socket: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], List[SwapPair]]:
    """
    Run multiple swaps in parallel using ThreadPoolExecutor.
    
    Args:
        ct_steering: The ct_steering module
        config: Swap configuration
        pairs: List of swap pairs to run
        max_workers: Maximum concurrent workers (default: 8 for 8 GPUs)
        verbose: Print progress
        control_socket: Optional SSH ControlMaster socket for connection reuse
    
    Returns:
        Tuple of (results list, failed pairs list)
    """
    results = []
    failed = []
    total = len(pairs)
    completed = 0
    start_time = time.time()
    
    # Track worker index for staggered starts (Windows workaround)
    import threading
    worker_counter = [0]
    counter_lock = threading.Lock()
    
    is_local = not config.get('compute', {}).get('remote', {}).get('enabled', False)
    available_gpus = list(range(max_workers)) if is_local else []

    def run_swap_worker(pair: SwapPair) -> Tuple[SwapPair, Optional[Dict[str, Any]], Optional[str], float]:
        """Worker function for a single swap."""
        with counter_lock:
            worker_idx = worker_counter[0]
            worker_counter[0] += 1

        if worker_idx < max_workers and not control_socket:
            time.sleep(worker_idx * 0.5)

        worker_config = dict(config)
        if available_gpus:
            worker_config['_local_gpu_id'] = available_gpus[worker_idx % len(available_gpus)]

        swap_start = time.time()
        try:
            result = run_single_swap(ct_steering, worker_config, pair, verbose=False,
                                     control_socket=control_socket)
            return (pair, result, None, time.time() - swap_start)
        except Exception as e:
            return (pair, None, str(e), time.time() - swap_start)
    
    print(f"  Starting {total} swaps with {max_workers} parallel workers...")
    print(f"  Start time: {datetime.now().strftime('%H:%M:%S')}")
    print(f"  (Press Ctrl+C to stop - may take a few seconds)")
    
    swap_times = []
    executor = ThreadPoolExecutor(max_workers=max_workers)
    try:
        # Submit all tasks
        future_to_pair = {executor.submit(run_swap_worker, pair): pair for pair in pairs}
        
        # Process as they complete
        for future in as_completed(future_to_pair):
            pair, result, error, swap_time = future.result()
            completed += 1
            swap_times.append(swap_time)
            
            if result:
                results.append(result)
                status = "OK"
                detail = f"suppressed={result['evaluation']['exact_match']['from_suppressed']}"
            else:
                failed.append(pair)
                status = "FAIL"
                detail = error or "failed"
            
            # Calculate ETA
            elapsed = time.time() - start_time
            avg_time = elapsed / completed
            remaining = (total - completed) * avg_time / max_workers
            eta = datetime.now() + timedelta(seconds=remaining)
            
            if verbose:
                print(f"  [{completed}/{total}] {pair.from_slug} -> {pair.to_slug}: {status} "
                      f"({swap_time:.1f}s, ETA: {eta.strftime('%H:%M:%S')})")
    
    except KeyboardInterrupt:
        print("\n\n  [INTERRUPT] Ctrl+C received - shutting down workers...")
        executor.shutdown(wait=False, cancel_futures=True)
        print("  [INTERRUPT] Cleaning up - please wait...")
        # Clear any stuck GPU locks on remote
        try:
            import subprocess
            subprocess.run(
                ['ssh', 'nodo207', 
                 'rmdir /mnt/ssd-1/soar-automated_interpretability/graphs/giuseppe/.locks/gpu* 2>/dev/null; echo done'],
                capture_output=True, timeout=10
            )
            print("  [INTERRUPT] GPU locks cleared on remote")
        except Exception:
            print("  [INTERRUPT] Warning: Could not clear remote GPU locks")
        raise
    finally:
        executor.shutdown(wait=True)
    
    # Print timing summary
    total_time = time.time() - start_time
    avg_swap_time = sum(swap_times) / len(swap_times) if swap_times else 0
    print(f"\n  Timing Summary:")
    print(f"    Total wall time: {total_time:.1f}s ({total_time/60:.1f} min)")
    print(f"    Avg swap time: {avg_swap_time:.1f}s")
    print(f"    Throughput: {total / total_time * 60:.1f} swaps/min")
    print(f"    Parallel speedup: ~{avg_swap_time * total / total_time:.1f}x")
    
    return results, failed


def run_batch_swaps(
    config_path: str,
    dry_run: bool = False,
    force: bool = False,
    single_pair: Optional[str] = None,
    verbose: bool = True,
    parallel: bool = False,
    max_workers: int = 8,
    run_id: Optional[str] = None,
    gpu_ids: Optional[List[int]] = None,
):
    """
    Run batch swap experiments.
    
    Args:
        config_path: Path to swap config YAML
        dry_run: If True, only validate and show plan
        force: If True, overwrite existing results
        single_pair: If provided, only run this pair (format: "from_slug:to_slug")
        verbose: Print progress
        parallel: If True, run swaps in parallel (uses multiple GPUs)
        max_workers: Maximum parallel workers when parallel=True (default: 8)
        gpu_ids: Explicit list of GPU IDs to use (default: 0..max_workers-1)
    """
    print_banner("Batch Swap Runner")
    print(f"Config: {config_path}")
    print(f"Dry run: {dry_run}")
    print(f"Force: {force}")
    if run_id:
        print(f"Run ID: {run_id}")
    if parallel:
        print(f"Parallel: {max_workers} workers")
    
    # Load config
    print_banner("Loading Configuration")
    try:
        config = load_swap_config(config_path)
    except Exception as e:
        print(f"ERROR: Failed to load config: {e}")
        return False

    # Select a run directory to avoid overwriting old swap results.
    graphs_root = Path(config["inputs"]["graphs_root"])
    rid, run_dir, run_meta = setup_swap_run_dir(
        graphs_root=graphs_root,
        loaded_config=config,
        swap_config_path=config_path,
        run_id=run_id,
        script_dir=SCRIPT_DIR,
        create_dirs=not dry_run,
    )
    config["_swaps_dir"] = str(run_dir)

    print_banner("Swap Run Directory")
    print(f"Graphs root: {graphs_root}")
    print(f"Run ID: {rid}")
    print(f"Swaps output dir: {run_dir}")
    
    # Resolve pairs
    print_banner("Resolving Swap Pairs")
    try:
        all_pairs = resolve_swap_pairs(config)
    except Exception as e:
        print(f"ERROR: Failed to resolve pairs: {e}")
        return False
    
    # Filter to single pair if specified
    if single_pair:
        from_slug, to_slug = single_pair.split(':')
        all_pairs = [p for p in all_pairs if p.from_slug == from_slug and p.to_slug == to_slug]
        if not all_pairs:
            print(f"ERROR: Pair not found: {single_pair}")
            return False
        print(f"  Filtered to single pair: {single_pair}")
    
    # Validate inputs
    print_banner("Validating Inputs")
    errors = validate_swap_inputs(config, all_pairs)
    if errors:
        print(f"\nERROR: {len(errors)} validation errors:")
        for err in errors[:10]:
            print(f"  - {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")
        return False
    
    # Filter existing
    pending_pairs, skipped_pairs = filter_existing_pairs(config, all_pairs, force)
    
    print(f"\nPairs to process: {len(pending_pairs)}")
    print(f"Pairs to skip: {len(skipped_pairs)}")
    
    if dry_run:
        print_banner("Dry Run - Execution Plan")
        print(f"Would process {len(pending_pairs)} swap pairs")
        print(f"\nSample pairs:")
        for pair in pending_pairs[:5]:
            print(f"  - {pair.from_slug} -> {pair.to_slug}")
            print(f"    Concept: {pair.from_concept} -> {pair.to_concept}")
        if len(pending_pairs) > 5:
            print(f"  ... and {len(pending_pairs) - 5} more")
        print(f"\nOutput directory: {run_dir}")
        return True
    
    if not pending_pairs:
        print("\nNo pairs to process. Use --force to re-run.")
        return True
    
    # Load CT steering module
    print_banner("Loading CT Steering Module")
    try:
        ct_steering = _load_ct_steering_module()
        print("  Module loaded successfully")
    except ImportError as e:
        print(f"ERROR: Failed to load ct_steering module: {e}")
        return False
    
    # Run swaps
    print_banner(f"Running {len(pending_pairs)} Swaps")

    # Write run manifest + config snapshots (traceability).
    start_iso = datetime.now().isoformat()
    try:
        # Copy config files into the run dir (best-effort).
        swap_cfg_path = Path(run_meta.get("swap_config_path", ""))
        if swap_cfg_path.exists():
            shutil.copy2(swap_cfg_path, run_dir / "config_swap.yml")
        source_cfg = run_meta.get("source_config_path")
        if source_cfg:
            source_cfg_path = Path(source_cfg)
            if source_cfg_path.exists():
                shutil.copy2(source_cfg_path, run_dir / "config_source.yml")
    except Exception as e:
        print(f"  [WARN] Could not copy config snapshots: {e}")

    # Create a lightweight per-run notes file (helps experiment traceability).
    notes_path = run_dir / "notes.txt"
    if not notes_path.exists():
        try:
            notes_path.write_text(
                "Run notes\n"
                "---------\n"
                f"Run ID: {rid}\n"
                f"Started: {start_iso}\n"
                "\n"
                "Goal:\n"
                "- \n"
                "\n"
                "Hypothesis:\n"
                "- \n"
                "\n"
                "Changes vs previous run:\n"
                "- \n"
                "\n"
                "Observations:\n"
                "- \n"
                "\n"
                "Next steps:\n"
                "- \n",
                encoding="utf-8",
            )
        except OSError:
            pass

    write_run_artifacts(
        run_dir=run_dir,
        run_meta=run_meta,
        loaded_config=config,
        argv=sys.argv,
        status="started",
        extra={"timestamp_started": start_iso},
    )
    
    is_local = not config.get('compute', {}).get('remote', {}).get('enabled', False)

    if parallel and is_local:
        # Batched local execution: prepare all pairs on CPU, then 1 process/GPU
        actual_gpus = gpu_ids if gpu_ids else list(range(max_workers))
        n_gpus = min(len(actual_gpus), max_workers)
        actual_gpus = actual_gpus[:n_gpus]
        print(f"  [LOCAL] Batched execution on {n_gpus} GPUs {actual_gpus}")
        print(f"  [LOCAL] Phase 1: Preparing features (CPU)...")
        prepared, prep_skipped = _prepare_pairs_cpu(
            ct_steering, config, pending_pairs, verbose=verbose
        )
        failed = list(prep_skipped)

        if not prepared:
            print("  ERROR: No pairs could be prepared")
            results = []
        else:
            import math
            n_gpus = min(n_gpus, len(prepared))
            batch_size = math.ceil(len(prepared) / n_gpus)
            gpu_batches = [
                prepared[i:i + batch_size] for i in range(0, len(prepared), batch_size)
            ]
            print(f"  [LOCAL] Phase 2: Running {len(prepared)} pairs across "
                  f"{len(gpu_batches)} GPUs ({batch_size} pairs/GPU, 1 model load/GPU)")
            run_start = time.time()

            results = []
            with ThreadPoolExecutor(max_workers=len(gpu_batches)) as executor:
                work_root = Path(config['inputs']['graphs_root']) / '_swaps' / '_work'
                futures = {
                    executor.submit(
                        _run_gpu_batch, actual_gpus[idx], batch, config, work_root, verbose=False
                    ): actual_gpus[idx]
                    for idx, batch in enumerate(gpu_batches)
                }
                for future in as_completed(futures):
                    gpu_id = futures[future]
                    try:
                        batch_results = future.result()
                    except Exception as e:
                        print(f"  ERROR: GPU {gpu_id} batch failed: {e}")
                        batch_results = []
                    for pp, swap_result in batch_results:
                        if swap_result:
                            results.append(swap_result)
                        else:
                            failed.append(pp.pair)

            elapsed = time.time() - run_start
            print(f"  [LOCAL] Phase 2 done: {len(results)} OK, "
                  f"{len(failed)} failed, {elapsed:.1f}s total")

    elif parallel:
        # Remote parallel execution using SSH ControlMaster
        print("  [SSH] Starting ControlMaster for parallel execution...")
        control_master = create_control_master_from_config(config, verbose=verbose)
        control_socket = control_master.socket_path if control_master else None
        
        if control_socket:
            print(f"  [SSH] Connection multiplexing enabled")
        else:
            if max_workers > 8:
                print(f"  [SSH] WARNING: ControlMaster unavailable, capping workers to 8")
                max_workers = 8
        
        print(f"  [SSH] Clearing stale GPU locks...")
        try:
            result = subprocess.run(
                ['ssh', 'nodo207', 
                 'rmdir /mnt/ssd-1/soar-automated_interpretability/graphs/giuseppe/.locks/gpu* 2>/dev/null; echo cleared'],
                capture_output=True, text=True, timeout=10
            )
            if 'cleared' in result.stdout:
                print(f"  [SSH] Stale locks cleared")
        except Exception as e:
            print(f"  [SSH] Warning: Could not clear stale locks: {e}")
        
        try:
            results, failed = run_swaps_parallel(
                ct_steering, config, pending_pairs, 
                max_workers=max_workers, verbose=verbose,
                control_socket=control_socket
            )
        finally:
            if control_master:
                control_master.close()
                print("  [SSH] ControlMaster closed")
    else:
        # Sequential execution (original behavior, variant-aware)
        results = []
        failed = []
        variants = _expand_control_variants(config)

        for i, pair in enumerate(pending_pairs, 1):
            for variant_config, variant_suffix in variants:
                label = f"\n[{i}/{len(pending_pairs)}]"
                if variant_suffix:
                    label += f" ({variant_suffix})"
                print(label, end="")

                try:
                    result = run_single_swap(
                        ct_steering, variant_config, pair, verbose=verbose,
                        variant_suffix=variant_suffix,
                    )
                    if result:
                        results.append(result)
                    else:
                        failed.append(pair)
                except Exception as e:
                    print(f"  ERROR: Exception during swap: {e}")
                    failed.append(pair)
    
    # Aggregate results
    print_banner("Aggregating Results")
    
    swaps_dir = Path(config["_swaps_dir"])
    
    # Partition results by control mode for separate aggregation
    results_by_mode: Dict[str, List] = {}
    for r in results:
        mode = r.get("metadata", {}).get("control", {}).get("control_mode", "labeled")
        results_by_mode.setdefault(mode, []).append(r)

    summary = create_summary(results, config)
    summary['failed_count'] = len(failed)
    summary['failed_pairs'] = [f"{p.from_slug}:{p.to_slug}" for p in failed]
    if len(results_by_mode) > 1:
        summary['control_modes'] = {
            mode: len(mode_results) for mode, mode_results in results_by_mode.items()
        }
    
    summary_path = swaps_dir / "_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"  Summary saved to: {summary_path}")
    
    # Create matrix -- only safe for single-result-per-pair groups
    entities = config.get('_entities', [])
    for mode, mode_results in results_by_mode.items():
        if len(mode_results) <= 1:
            continue
        try:
            suffix = f"_{mode}" if mode != "labeled" else ""
            matrix = aggregate_results_to_matrix(
                mode_results, entities, 'steered_has_to_capital',
            )
            matrix_path = swaps_dir / f"_matrix{suffix}.csv"
            matrix.to_csv(matrix_path)
            print(f"  Matrix ({mode}): {matrix_path}")
        except Exception as e:
            print(f"  Warning: Could not create matrix for {mode}: {e}")
    
    # Final summary
    print_banner("Batch Complete")
    print(f"Total pairs: {len(all_pairs)}")
    print(f"Processed: {len(results)}")
    print(f"Failed: {len(failed)}")
    print(f"Skipped: {len(skipped_pairs)}")
    if len(results_by_mode) > 1:
        for mode, mode_results in sorted(results_by_mode.items()):
            print(f"  {mode}: {len(mode_results)} results")
    
    if results:
        exact_hits = sum(1 for r in results if r['evaluation']['exact_match']['steered_has_to_capital'])
        suppressed = sum(1 for r in results if r['evaluation']['exact_match']['from_suppressed'])
        print(f"\nSuccess rates (exact match, all modes):")
        print(f"  Target capital hit: {exact_hits}/{len(results)} ({100*exact_hits/len(results):.1f}%)")
        print(f"  Source suppressed: {suppressed}/{len(results)} ({100*suppressed/len(results):.1f}%)")

    # Finalize run manifest
    end_iso = datetime.now().isoformat()
    write_run_artifacts(
        run_dir=run_dir,
        run_meta=run_meta,
        loaded_config=config,
        argv=sys.argv,
        status="completed" if len(failed) == 0 else "completed_with_failures",
        extra={
            "timestamp_started": start_iso,
            "timestamp_completed": end_iso,
            "counts": {
                "total_pairs": len(all_pairs),
                "processed": len(results),
                "failed": len(failed),
                "skipped": len(skipped_pairs),
            },
            "outputs": {
                "summary_path": str(summary_path),
                "matrix_path": str(swaps_dir / "_matrix.csv"),
            },
        },
    )
    
    return len(failed) == 0


def main():
    parser = argparse.ArgumentParser(
        description="Run batch swap experiments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate config and show plan
  python run_batch_swaps.py --config configs/usa_states_swap.yml --dry-run
  
  # Run all swaps (sequential)
  python run_batch_swaps.py --config configs/usa_states_swap.yml
  
  # Run all swaps in PARALLEL (8 GPUs, ~8x faster)
  python run_batch_swaps.py --config configs/usa_states_swap.yml --parallel
  
  # Run single pair
  python run_batch_swaps.py --config configs/usa_states_swap.yml --pair texas_dallas:california_oakland
  
  # Run with an explicit run_id (recommended for resumability)
  python run_batch_swaps.py --config configs/usa_states_swap.yml --run-id my_run

  # Force re-run within the SAME run directory (overwrites results in that run)
  python run_batch_swaps.py --config configs/usa_states_swap.yml --run-id my_run --force
        """
    )
    
    parser.add_argument(
        '--config',
        type=str,
        required=True,
        help='Path to swap config YAML file'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate config and show plan without running'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Overwrite existing results'
    )
    
    parser.add_argument(
        '--pair',
        type=str,
        default=None,
        help='Run single pair only (format: from_slug:to_slug)'
    )
    
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress verbose output'
    )
    
    parser.add_argument(
        '--parallel',
        action='store_true',
        help='Run swaps in parallel using multiple GPUs (8x faster)'
    )
    
    parser.add_argument(
        '--workers',
        type=int,
        default=8,
        help='Number of parallel workers when --parallel is set (default: 8)'
    )

    parser.add_argument(
        '--gpus',
        type=str,
        default=None,
        help='Comma-separated GPU IDs to use (e.g. "4,5,6,7"). Default: 0..workers-1'
    )

    parser.add_argument(
        '--run-id',
        type=str,
        default=None,
        help=(
            "Optional run identifier. If not provided, a timestamped run_id is generated and "
            "outputs are written under {graphs_root}/_swaps/runs/{run_id}/. "
            "Use the same --run-id to resume a partial run without overwriting other runs."
        ),
    )
    
    args = parser.parse_args()
    
    parsed_gpus = None
    if args.gpus:
        parsed_gpus = [int(g.strip()) for g in args.gpus.split(',')]

    success = run_batch_swaps(
        config_path=args.config,
        dry_run=args.dry_run,
        force=args.force,
        single_pair=args.pair,
        verbose=not args.quiet,
        parallel=args.parallel,
        max_workers=args.workers,
        run_id=args.run_id,
        gpu_ids=parsed_gpus,
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

