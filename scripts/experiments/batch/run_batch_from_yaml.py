#!/usr/bin/env python3
"""
Batch experiment runner from YAML config.

Usage:
    python run_batch_from_yaml.py --config configs/usa_capitals_swap_full.yml [--dry-run] [--force]
"""
import argparse
import sys
from pathlib import Path

# Load .env file if available
try:
    from dotenv import load_dotenv
    # Look for .env in repo root (4 levels up from this script)
    env_path = Path(__file__).parent.parent.parent.parent / '.env'
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass  # python-dotenv not installed, continue without

# Add parent to path
parent_dir = Path(__file__).parent.parent.parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from pipeline.loader import (
    load_config, validate_config, resolve_seeds, get_seed_paths, plan_batches
)
from pipeline.graph import process_graph_step
from pipeline.probes import process_probes_step
from pipeline.activations_local import process_activations_step
from pipeline.remote import (
    process_remote_activation_step,
    process_remote_activation_batch
)
from pipeline.grouping import process_grouping_step
from pipeline.manifest import create_manifest, write_manifest


def print_banner(text: str):
    """Print a section banner."""
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}")


def run_batch(config_path: str, dry_run: bool = False, force: bool = False, verbose: bool = True):
    """
    Run batch experiment from YAML config.
    
    Args:
        config_path: Path to YAML config file
        dry_run: If True, only validate and print plan without executing
        force: If True, overwrite existing outputs
        verbose: Print detailed progress
    """
    print_banner(f"Batch Experiment Runner")
    print(f"Config: {config_path}")
    print(f"Dry run: {dry_run}")
    print(f"Force: {force}")
    
    # Load and validate config
    print_banner("Loading Config")
    try:
        config = load_config(config_path)
        if verbose:
            print(f"  Loaded: {config.get('experiment_name', 'unnamed')}")
            print(f"  Version: {config.get('version', 'unknown')}")
    except Exception as e:
        print(f"ERROR: Failed to load config: {e}")
        return False
    
    # Validate
    errors = validate_config(config)
    if errors:
        print(f"ERROR: Config validation failed:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    if verbose:
        print(f"  Config valid")
    
    # Resolve seeds
    print_banner("Resolving Seeds")
    try:
        seeds = resolve_seeds(config)
        if verbose:
            print(f"  Found {len(seeds)} seed(s):")
            for seed in seeds:
                print(f"    - {seed['slug']}")
    except Exception as e:
        print(f"ERROR: Failed to resolve seeds: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Get enabled steps
    steps = config['steps']
    enabled_steps = [k for k, v in steps.items() if v]
    
    if verbose:
        print(f"\n  Enabled steps: {', '.join(enabled_steps)}")
    
    # Dry run: print plan and exit
    if dry_run:
        print_banner("Dry Run - Execution Plan")
        print(f"Would process {len(seeds)} seed(s) with steps: {', '.join(enabled_steps)}")
        print(f"\nOutputs root: {config['paths']['outputs_root']}")
        print(f"\nPer-seed structure:")
        for seed in seeds[:3]:  # Show first 3
            paths = get_seed_paths(config, seed)
            print(f"\n  {seed['slug']}/")
            if steps.get('graph_generation') or steps.get('feature_export'):
                print(f"    00 Graph Generation/")
                print(f"      - graph.json")
                print(f"      - graph_feature_static_metrics.csv")
                print(f"      - selected_features_with_nodes.json")
            if steps.get('activations'):
                print(f"    01 Prompt Probing/")
                print(f"      - prompts.json")
                print(f"      - activations_dump.json")
            if steps.get('grouping'):
                print(f"    02 Node Grouping/")
                print(f"      - node_grouping.csv")
        
        if len(seeds) > 3:
            print(f"\n  ... and {len(seeds) - 3} more seed(s)")
        
        print(f"\nDry run complete. Use without --dry-run to execute.")
        return True
    
    # Execute for each seed
    print_banner(f"Processing {len(seeds)} Seed(s)")
    
    seed_states = []
    remote_config = config.get('compute', {}).get('remote', {})
    remote_enabled = remote_config.get('enabled', False)
    remote_batch_size = max(1, remote_config.get('batch_size', 1))
    remote_max_gpus = max(1, remote_config.get('max_gpus', 1))
    
    for i, seed in enumerate(seeds, 1):
        print(f"\n[{i}/{len(seeds)}] Seed: {seed['slug']}")
        print(f"{'─'*70}")
        
        paths = get_seed_paths(config, seed)
        manifest = create_manifest(config, seed, paths, status='started')
        write_manifest(manifest, paths)
        
        state = {
            'seed': seed,
            'paths': paths,
            'manifest': manifest,
            'success': True,
            'error': None,
            'activations_pending': False,
            'activations_done': False,
            'remote_metadata': {},
        }
        
        try:
            # Graph/features
            if state['success'] and (steps.get('graph_generation') or steps.get('feature_export')):
                if paths['selected_features_json'].exists() and not force:
                    print("  [SKIP] Graph/features already exist (use --force to overwrite)")
                else:
                    if not process_graph_step(config, seed, paths, verbose=verbose):
                        state['success'] = False
                        state['error'] = "Graph/feature processing failed"
            
            # Probes
            if state['success'] and steps.get('probe_prompts', True):
                if paths['prompts_json'].exists() and not force:
                    print("  [SKIP] Prompts already exist (use --force to overwrite)")
                else:
                    if not process_probes_step(config, seed, paths, verbose=verbose):
                        state['success'] = False
                        state['error'] = "Probe prompts processing failed"
            
            # Activations decision (execution deferred for remote batching)
            if state['success'] and steps.get('activations'):
                if paths['activations_dump_json'].exists() and not force:
                    print("  [SKIP] Activations already exist (use --force to overwrite)")
                    state['activations_done'] = True
                else:
                    if remote_enabled:
                        state['activations_pending'] = True
                        print("  [QUEUE] Activations scheduled for remote batch run")
                    else:
                        if process_activations_step(config, seed, paths, verbose=verbose):
                            state['activations_done'] = True
                        else:
                            state['success'] = False
                            state['error'] = "Activations processing failed"
            elif state['success'] and not steps.get('activations'):
                # Assume activations already exist when step disabled
                if paths['activations_dump_json'].exists():
                    state['activations_done'] = True
                else:
                    state['activations_done'] = False
            
            # Grouping deferred if activations pending
            if state['success'] and steps.get('grouping') and not state['activations_pending']:
                if paths['grouping_csv'].exists() and not force:
                    print("  [SKIP] Grouping already exists (use --force to overwrite)")
                else:
                    if not process_grouping_step(config, seed, paths, verbose=verbose):
                        state['success'] = False
                        state['error'] = "Grouping processing failed"
        
        except Exception as exc:
            state['success'] = False
            state['error'] = f"Exception: {exc}"
            import traceback
            traceback.print_exc()
        
        seed_states.append(state)
    
    # Remote batch activations stage
    if remote_enabled:
        pending_remote = [s for s in seed_states if s['success'] and s['activations_pending']]
        if pending_remote:
            print_banner(f"Remote Activations ({len(pending_remote)} seed(s))")
            batches = plan_batches(pending_remote, remote_batch_size)
            print(f"  Planned {len(batches)} batch(es) "
                  f"(batch_size={remote_batch_size}, max_gpus={remote_max_gpus})")
            
            from concurrent.futures import ThreadPoolExecutor, as_completed
            futures = {}
            with ThreadPoolExecutor(max_workers=remote_max_gpus) as executor:
                for batch_index, batch_states in enumerate(batches, 1):
                    batch_id = f"batch_{batch_index:03d}"
                    future = executor.submit(
                        process_remote_activation_batch,
                        config,
                        batch_states,
                        batch_id,
                        verbose
                    )
                    futures[future] = (batch_id, batch_states)
                
                for future in as_completed(futures):
                    batch_id, batch_states = futures[future]
                    try:
                        batch_success, metadata, per_seed = future.result()
                    except Exception as exc:
                        batch_success = False
                        metadata = {}
                        per_seed = {}
                        print(f"ERROR: Remote batch {batch_id} raised exception: {exc}")
                    
                    for batch_state in batch_states:
                        slug = batch_state['seed']['slug']
                        result = per_seed.get(slug, {})
                        if result.get('success'):
                            batch_state['activations_pending'] = False
                            batch_state['activations_done'] = True
                            batch_state['remote_metadata'] = {
                                'remote': {
                                    'gpu_id': metadata.get('gpu_id'),
                                    'remote_log': result.get('remote_log'),
                                    'local_log': result.get('local_log'),
                                    'batch_id': batch_id,
                                }
                            }
                        else:
                            batch_state['success'] = False
                            batch_state['error'] = result.get('error') or "Remote activations failed"
                            batch_state['remote_metadata'] = {
                                'remote': {
                                    'batch_id': batch_id,
                                    'remote_log': result.get('remote_log'),
                                    'local_log': result.get('local_log'),
                                    'gpu_id': metadata.get('gpu_id'),
                                    'error': result.get('error'),
                                }
                            }
    
    # Grouping pass for seeds whose activations completed after remote batching
    for state in seed_states:
        if not state['success']:
            continue
        if steps.get('grouping') and not state['activations_pending'] and not state['activations_done']:
            # Should not happen, warn
            print(f"WARNING: Seed {state['seed']['slug']} missing activations for grouping")
            continue
        if steps.get('grouping') and state['activations_done'] and state['paths']['grouping_csv'].exists() and not force:
            continue
        if steps.get('grouping') and state['activations_done'] and (force or not state['paths']['grouping_csv'].exists()):
            if not process_grouping_step(config, state['seed'], state['paths'], verbose=verbose):
                state['success'] = False
                state['error'] = "Grouping processing failed"
    
    # Finalize manifests and summary
    success_count = 0
    failed_seeds = []
    
    from datetime import datetime
    for state in seed_states:
        manifest = state['manifest']
        manifest['timestamp_completed'] = datetime.now().isoformat()
        if state['remote_metadata']:
            manifest.update(state['remote_metadata'])
        
        if state['success']:
            manifest['status'] = 'completed'
            write_manifest(manifest, state['paths'])
            success_count += 1
        else:
            manifest['status'] = 'failed'
            manifest['error'] = state['error']
            write_manifest(manifest, state['paths'])
            failed_seeds.append((state['seed']['slug'], state['error']))
    
    print_banner("Batch Run Summary")
    print(f"Total seeds: {len(seeds)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {len(failed_seeds)}")
    
    if failed_seeds:
        print("\nFailed seeds:")
        for slug, error in failed_seeds:
            print(f"  - {slug}: {error}")
        return False
    
    print("\n✓ All seeds completed successfully")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Run batch experiments from YAML config",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to validate config
  python run_batch_from_yaml.py --config configs/usa_capitals_swap_full.yml --dry-run
  
  # Execute batch run
  python run_batch_from_yaml.py --config configs/usa_capitals_swap_full.yml
  
  # Force overwrite existing outputs
  python run_batch_from_yaml.py --config configs/usa_capitals_swap_full.yml --force
        """
    )
    
    parser.add_argument(
        '--config',
        type=str,
        required=True,
        help='Path to YAML config file'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate config and print execution plan without running'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Overwrite existing outputs'
    )
    
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress verbose output'
    )
    
    args = parser.parse_args()
    
    # Run batch
    success = run_batch(
        config_path=args.config,
        dry_run=args.dry_run,
        force=args.force,
        verbose=not args.quiet
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

