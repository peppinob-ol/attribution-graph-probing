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
    load_config, validate_config, resolve_seeds, get_seed_paths
)
from pipeline.graph import process_graph_step
from pipeline.probes import process_probes_step
from pipeline.activations_local import process_activations_step
from pipeline.remote import process_remote_activation_step
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
    
    success_count = 0
    failed_seeds = []
    
    for i, seed in enumerate(seeds, 1):
        print(f"\n[{i}/{len(seeds)}] Seed: {seed['slug']}")
        print(f"{'─'*70}")
        
        paths = get_seed_paths(config, seed)
        
        # Create manifest (started)
        manifest = create_manifest(config, seed, paths, status='started')
        write_manifest(manifest, paths)
        
        seed_success = True
        error_msg = None
        
        try:
            # Step: Graph generation / feature export
            if steps.get('graph_generation') or steps.get('feature_export'):
                # Check if already done
                if paths['selected_features_json'].exists() and not force:
                    print(f"  [SKIP] Graph/features already exist (use --force to overwrite)")
                else:
                    if not process_graph_step(config, seed, paths, verbose=verbose):
                        seed_success = False
                        error_msg = "Graph/feature processing failed"
            
            # Step: Probe prompts
            if seed_success and steps.get('probe_prompts', True):
                if paths['prompts_json'].exists() and not force:
                    print(f"  [SKIP] Prompts already exist (use --force to overwrite)")
                else:
                    if not process_probes_step(config, seed, paths, verbose=verbose):
                        seed_success = False
                        error_msg = "Probe prompts processing failed"
            
            # Step: Activations
            if seed_success and steps.get('activations'):
                if paths['activations_dump_json'].exists() and not force:
                    print(f"  [SKIP] Activations already exist (use --force to overwrite)")
                else:
                    # Check if remote execution is enabled
                    remote_enabled = config.get('compute', {}).get('remote', {}).get('enabled', False)
                    
                    if remote_enabled:
                        # Use remote GPU node
                        success, remote_metadata = process_remote_activation_step(config, seed, paths, verbose=verbose)
                        if not success:
                            seed_success = False
                            error_msg = "Remote activations processing failed"
                        else:
                            # Update manifest with remote metadata
                            manifest.update(remote_metadata)
                    else:
                        # Use local execution
                        if not process_activations_step(config, seed, paths, verbose=verbose):
                            seed_success = False
                            error_msg = "Activations processing failed"
            
            # Step: Grouping
            if seed_success and steps.get('grouping'):
                if paths['grouping_csv'].exists() and not force:
                    print(f"  [SKIP] Grouping already exists (use --force to overwrite)")
                else:
                    if not process_grouping_step(config, seed, paths, verbose=verbose):
                        seed_success = False
                        error_msg = "Grouping processing failed"
        
        except Exception as e:
            seed_success = False
            error_msg = f"Exception: {e}"
            import traceback
            traceback.print_exc()
        
        # Update manifest
        from datetime import datetime
        manifest['timestamp_completed'] = datetime.now().isoformat()
        
        if seed_success:
            manifest['status'] = 'completed'
            write_manifest(manifest, paths)
            success_count += 1
            print(f"  ✓ Seed completed successfully")
        else:
            manifest['status'] = 'failed'
            manifest['error'] = error_msg
            write_manifest(manifest, paths)
            failed_seeds.append((seed['slug'], error_msg))
            print(f"  ✗ Seed failed: {error_msg}")
    
    # Summary
    print_banner("Batch Run Summary")
    print(f"Total seeds: {len(seeds)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {len(failed_seeds)}")
    
    if failed_seeds:
        print(f"\nFailed seeds:")
        for slug, error in failed_seeds:
            print(f"  - {slug}: {error}")
        return False
    
    print(f"\n✓ All seeds completed successfully")
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

