#!/usr/bin/env python3
"""
Reclassify swap results using hybrid classifier.

Uses rule-based classification with LLM fallback for uncertain cases.
Updates the JSON files in place with new classification data.
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any
from collections import Counter

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Load .env file if present
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

from scripts.experiments.batch.pipeline.swap_classifier import (
    classify_swap_result, ClassificationMethod, SwapTier
)


def reclassify_swaps(
    swaps_dir: Path,
    use_llm: bool = True,
    llm_threshold: float = 0.7,
    honor_manual: bool = True,
    dry_run: bool = False,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Reclassify all swaps in a directory.
    
    Args:
        swaps_dir: Path to swaps directory (should contain by_source/)
        use_llm: Whether to use LLM for uncertain cases
        llm_threshold: Confidence threshold for LLM fallback
        honor_manual: Whether to honor existing manual annotations
        dry_run: If True, don't write changes
        verbose: Print detailed progress
    
    Returns:
        Statistics dict
    """
    by_source = swaps_dir / "by_source"
    if not by_source.exists():
        print(f"Error: {by_source} not found")
        return {}
    
    stats = {
        "total": 0,
        "processed": 0,
        "manual_honored": 0,
        "rule_high": 0,
        "rule_low": 0,
        "llm_used": 0,
        "errors": 0,
        "tier_counts": Counter(),
        "changed": 0,
    }
    
    # Collect all swap files
    swap_files = list(by_source.glob("*/to_*.json"))
    total = len(swap_files)
    stats["total"] = total
    
    print(f"Processing {total} swap files...")
    print(f"  LLM fallback: {'enabled' if use_llm else 'disabled'}")
    print(f"  LLM threshold: {llm_threshold}")
    print(f"  Honor manual: {honor_manual}")
    print(f"  Dry run: {dry_run}")
    print()
    
    for i, swap_file in enumerate(swap_files):
        if (i + 1) % 100 == 0 or (i + 1) == total:
            print(f"  Progress: {i + 1}/{total} ({100*(i+1)/total:.1f}%) - LLM calls: {stats['llm_used']}")
        
        try:
            with open(swap_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Get old tier if exists
            old_tier = data.get('classification', {}).get('tier')
            
            # Classify
            result = classify_swap_result(
                data,
                use_llm=use_llm,
                llm_threshold=llm_threshold,
                honor_manual=honor_manual,
            )
            
            # Track method used
            if result.method == ClassificationMethod.MANUAL:
                stats["manual_honored"] += 1
            elif result.method == ClassificationMethod.LLM:
                stats["llm_used"] += 1
            elif result.method == ClassificationMethod.RULE_HIGH:
                stats["rule_high"] += 1
            else:
                stats["rule_low"] += 1
            
            # Track tier
            stats["tier_counts"][result.tier.name] += 1
            
            # Check if changed
            if old_tier != result.tier.value:
                stats["changed"] += 1
                if verbose:
                    print(f"    Changed: {swap_file.name} tier {old_tier} -> {result.tier.value}")
            
            # Update classification in data
            if 'classification' not in data:
                data['classification'] = {}
            
            # Preserve manual flag if it was manual
            was_manual = data['classification'].get('manually_edited', False)
            
            data['classification'].update({
                'tier': result.tier.value,
                'tier_name': result.tier.name,
                'cities_found': result.cities_found,
                'states_found': result.states_found,
                'notes': result.notes if not was_manual else data['classification'].get('notes', result.notes),
                'method': result.method.name,
                'confidence': result.confidence,
                'manually_edited': was_manual,
            })
            
            # Write back
            if not dry_run:
                with open(swap_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            
            stats["processed"] += 1
            
        except Exception as e:
            stats["errors"] += 1
            if verbose:
                print(f"    Error: {swap_file.name}: {e}")
    
    return stats


def main():
    parser = argparse.ArgumentParser(description="Reclassify swap results")
    parser.add_argument("swaps_dir", type=Path, help="Path to swaps run directory")
    parser.add_argument("--no-llm", action="store_true", help="Disable LLM fallback")
    parser.add_argument("--threshold", type=float, default=0.7, help="LLM threshold (default: 0.7)")
    parser.add_argument("--no-honor-manual", action="store_true", help="Don't honor manual annotations")
    parser.add_argument("--dry-run", action="store_true", help="Don't write changes")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if not args.swaps_dir.exists():
        print(f"Error: {args.swaps_dir} not found")
        sys.exit(1)
    
    stats = reclassify_swaps(
        swaps_dir=args.swaps_dir,
        use_llm=not args.no_llm,
        llm_threshold=args.threshold,
        honor_manual=not args.no_honor_manual,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )
    
    print()
    print("=" * 50)
    print("CLASSIFICATION SUMMARY")
    print("=" * 50)
    print(f"Total files: {stats['total']}")
    print(f"Processed: {stats['processed']}")
    print(f"Errors: {stats['errors']}")
    print(f"Changed: {stats['changed']}")
    print()
    print("Classification method:")
    print(f"  Manual honored: {stats['manual_honored']}")
    print(f"  Rule (high conf): {stats['rule_high']}")
    print(f"  Rule (low conf): {stats['rule_low']}")
    print(f"  LLM fallback: {stats['llm_used']}")
    print()
    print("Tier distribution:")
    for tier in SwapTier:
        count = stats['tier_counts'].get(tier.name, 0)
        pct = 100 * count / stats['processed'] if stats['processed'] > 0 else 0
        print(f"  {tier.value} - {tier.name}: {count} ({pct:.1f}%)")


if __name__ == "__main__":
    main()

