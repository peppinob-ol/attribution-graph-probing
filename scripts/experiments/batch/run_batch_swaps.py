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
    
    # Force re-run (overwrite existing results)
    python run_batch_swaps.py --config configs/usa_states_swap.yml --force

Prerequisites:
    - Run usa_states_full.yml first to generate graphs
    - All states must have: graph.json, node_grouping.csv, metrics.csv
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
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
from pipeline.graph_loader import load_graph_data
from pipeline.swap_evaluator import (
    evaluate_swap,
    create_swap_result,
    create_summary,
    aggregate_results_to_matrix,
)
from pipeline.steering_remote_ct import process_remote_ct_steering_step


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
) -> List[Dict[str, Any]]:
    """
    Prepare CT intervention features for a swap pair.
    
    Args:
        ct_steering: The ct_steering module
        config: Swap configuration
        pair: The swap pair
        data_from: Graph data for source (loaded via load_graph_data)
        data_to: Graph data for target
    
    Returns:
        List of intervention feature dicts for batch_steering_ct.py
    """
    ct_config = config.get('ct_steering', {})
    M_ablate = ct_config.get('M_ablate', 0.0)
    M_amplify = ct_config.get('M_amplify', 2.0)
    steer_generated = ct_config.get('steer_generated_tokens', False)
    
    features = []
    ablate_count = 0
    amplify_count = 0
    
    # Extract source supernode for ABLATION
    try:
        supernode_from = ct_steering.extract_ct_supernode(
            grouping_df=data_from["grouping"],
            metrics_df=data_from["metrics"],
            concept=pair.from_concept,
            slug=pair.from_slug,
        )
        # MULTIPLICATION mode: use live activations from current prompt
        from_interventions = ct_steering.compute_ct_interventions(
            supernode_from,
            M_ablate,
            steer_generated_tokens=steer_generated,
            activations_map=None,  # Use live activations
            use_stored_as_base=False,
        )
        features.extend(from_interventions)
        ablate_count = len(from_interventions)
    except ValueError as e:
        print(f"  Warning: Could not extract '{pair.from_concept}' supernode: {e}")
    
    # Extract target supernode for AMPLIFICATION (from target graph)
    if pair.from_slug != pair.to_slug:  # Skip for identity swaps
        try:
            supernode_to = ct_steering.extract_ct_supernode(
                grouping_df=data_to["grouping"],
                metrics_df=data_to["metrics"],
                concept=pair.to_concept,
                slug=pair.to_slug,
            )
            # INJECTION mode: use stored activations from target graph
            activations_map_to = data_to.get("activations_map", {})
            to_interventions = ct_steering.compute_ct_interventions(
                supernode_to,
                M_amplify,
                steer_generated_tokens=steer_generated,
                activations_map=activations_map_to if activations_map_to else None,
                use_stored_as_base=True,
            )
            features.extend(to_interventions)
            amplify_count = len(to_interventions)
        except ValueError as e:
            print(f"  Warning: Could not extract '{pair.to_concept}' supernode: {e}")
    
    return features, ablate_count, amplify_count


def run_single_swap(
    ct_steering,
    config: Dict[str, Any],
    pair: SwapPair,
    verbose: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Run a single swap experiment.
    
    Args:
        ct_steering: The ct_steering module
        config: Swap configuration
        pair: The swap pair to run
        verbose: Print progress
    
    Returns:
        Complete result dict, or None if failed
    """
    paths = get_swap_paths(config, pair)
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
    features, ablate_count, amplify_count = prepare_swap_features(
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
    
    # Write prompts.json
    prompts = [{"id": "swap_prompt", "text": prompt}]
    with open(prompts_path, "w", encoding="utf-8") as f:
        json.dump(prompts, f, indent=2)
    
    # Write features.json
    with open(features_path, "w", encoding="utf-8") as f:
        json.dump(features, f, indent=2)
    
    # Execute steering
    ct_config = config.get('ct_steering', {})
    remote_config = config.get('compute', {}).get('remote', {})
    
    if remote_config.get('enabled', False):
        # Remote execution
        steering_cfg = {
            'transcoder_set': ct_config.get('transcoder_set', 'mntss/clt-gemma-2-2b-2.5M'),
            'temperature': ct_config.get('temperature', 0.3),
            'n_tokens': ct_config.get('n_tokens', 6),
            'freq_penalty': ct_config.get('freq_penalty', 2.0),
            'seed': ct_config.get('seed', 42),
            'top_k': ct_config.get('top_k', 5),
            'freeze_attention': ct_config.get('freeze_attention', False),
        }
        
        # Build config for remote executor
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
            remote_exec_config, seed, local_paths, verbose=verbose
        )
        
        if not success:
            print(f"  ERROR: Remote steering failed")
            return None
    else:
        # Local execution would go here
        # For now, require remote execution
        print("  ERROR: Local execution not yet implemented. Use remote.")
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
    evaluation = evaluate_swap(raw_result, pair.from_entity, pair.to_entity)
    
    duration_ms = (time.time() - start_time) * 1000
    
    # Create complete result
    result = create_swap_result(pair, raw_result, evaluation, config, duration_ms)
    
    # Save to output path
    output_file = paths['output_file']
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    if verbose:
        exact = evaluation['exact_match']
        print(f"  Default: {raw_result.get('default', '')[:50]}...")
        print(f"  Steered: {raw_result.get('steered', '')[:50]}...")
        print(f"  Suppressed: {exact['from_suppressed']}, Target hit: {exact['steered_has_to_capital']}")
    
    return result


def run_swaps_parallel(
    ct_steering,
    config: Dict[str, Any],
    pairs: List[SwapPair],
    max_workers: int = 8,
    verbose: bool = True,
) -> Tuple[List[Dict[str, Any]], List[SwapPair]]:
    """
    Run multiple swaps in parallel using ThreadPoolExecutor.
    
    Args:
        ct_steering: The ct_steering module
        config: Swap configuration
        pairs: List of swap pairs to run
        max_workers: Maximum concurrent workers (default: 8 for 8 GPUs)
        verbose: Print progress
    
    Returns:
        Tuple of (results list, failed pairs list)
    """
    results = []
    failed = []
    total = len(pairs)
    completed = 0
    start_time = time.time()
    
    def run_swap_worker(pair: SwapPair) -> Tuple[SwapPair, Optional[Dict[str, Any]], Optional[str], float]:
        """Worker function for a single swap."""
        swap_start = time.time()
        try:
            result = run_single_swap(ct_steering, config, pair, verbose=False)
            return (pair, result, None, time.time() - swap_start)
        except Exception as e:
            return (pair, None, str(e), time.time() - swap_start)
    
    print(f"  Starting {total} swaps with {max_workers} parallel workers...")
    print(f"  Start time: {datetime.now().strftime('%H:%M:%S')}")
    
    swap_times = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_pair = {executor.submit(run_swap_worker, pair): pair for pair in pairs}
        
        # Process as they complete
        for future in as_completed(future_to_pair):
            pair, result, error, swap_time = future.result()
            completed += 1
            swap_times.append(swap_time)
            
            if result:
                results.append(result)
                status = "✓"
                detail = f"suppressed={result['evaluation']['exact_match']['from_suppressed']}"
            else:
                failed.append(pair)
                status = "✗"
                detail = error or "failed"
            
            # Calculate ETA
            elapsed = time.time() - start_time
            avg_time = elapsed / completed
            remaining = (total - completed) * avg_time / max_workers
            eta = datetime.now() + timedelta(seconds=remaining)
            
            if verbose:
                print(f"  [{completed}/{total}] {pair.from_slug} -> {pair.to_slug}: {status} "
                      f"({swap_time:.1f}s, ETA: {eta.strftime('%H:%M:%S')})")
    
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
    """
    print_banner("Batch Swap Runner")
    print(f"Config: {config_path}")
    print(f"Dry run: {dry_run}")
    print(f"Force: {force}")
    if parallel:
        print(f"Parallel: {max_workers} workers")
    
    # Load config
    print_banner("Loading Configuration")
    try:
        config = load_swap_config(config_path)
    except Exception as e:
        print(f"ERROR: Failed to load config: {e}")
        return False
    
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
        print(f"\nOutput directory: {config['inputs']['graphs_root']}/_swaps/")
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
    
    if parallel:
        # Parallel execution using ThreadPoolExecutor
        results, failed = run_swaps_parallel(
            ct_steering, config, pending_pairs, 
            max_workers=max_workers, verbose=verbose
        )
    else:
        # Sequential execution (original behavior)
        results = []
        failed = []
        
        for i, pair in enumerate(pending_pairs, 1):
            print(f"\n[{i}/{len(pending_pairs)}]", end="")
            
            try:
                result = run_single_swap(ct_steering, config, pair, verbose=verbose)
                if result:
                    results.append(result)
                else:
                    failed.append(pair)
            except Exception as e:
                print(f"  ERROR: Exception during swap: {e}")
                failed.append(pair)
    
    # Aggregate results
    print_banner("Aggregating Results")
    
    graphs_root = Path(config['inputs']['graphs_root'])
    swaps_dir = graphs_root / "_swaps"
    
    # Create summary
    summary = create_summary(results, config)
    summary['failed_count'] = len(failed)
    summary['failed_pairs'] = [f"{p.from_slug}:{p.to_slug}" for p in failed]
    
    summary_path = swaps_dir / "_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"  Summary saved to: {summary_path}")
    
    # Create matrix if we have enough results
    if len(results) > 1:
        try:
            entities = config.get('_entities', [])
            matrix = aggregate_results_to_matrix(results, entities, 'steered_has_to_capital')
            matrix_path = swaps_dir / "_matrix.csv"
            matrix.to_csv(matrix_path)
            print(f"  Matrix saved to: {matrix_path}")
        except Exception as e:
            print(f"  Warning: Could not create matrix: {e}")
    
    # Final summary
    print_banner("Batch Complete")
    print(f"Total pairs: {len(all_pairs)}")
    print(f"Processed: {len(results)}")
    print(f"Failed: {len(failed)}")
    print(f"Skipped: {len(skipped_pairs)}")
    
    if results:
        exact_hits = sum(1 for r in results if r['evaluation']['exact_match']['steered_has_to_capital'])
        suppressed = sum(1 for r in results if r['evaluation']['exact_match']['from_suppressed'])
        print(f"\nSuccess rates (exact match):")
        print(f"  Target capital hit: {exact_hits}/{len(results)} ({100*exact_hits/len(results):.1f}%)")
        print(f"  Source suppressed: {suppressed}/{len(results)} ({100*suppressed/len(results):.1f}%)")
    
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
  
  # Force re-run
  python run_batch_swaps.py --config configs/usa_states_swap.yml --force
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
    
    args = parser.parse_args()
    
    success = run_batch_swaps(
        config_path=args.config,
        dry_run=args.dry_run,
        force=args.force,
        single_pair=args.pair,
        verbose=not args.quiet,
        parallel=args.parallel,
        max_workers=args.workers,
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

