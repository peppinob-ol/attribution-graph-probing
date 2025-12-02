#!/usr/bin/env python3
"""
Batch Annotation Tool for State Swap Explorer

Usage:
    python batch_annotate.py --preview   # Show what would change (dry run)
    python batch_annotate.py --apply     # Actually apply the changes

Edit the RULES list below to define your batch annotation rules.
"""
import json
import re
from pathlib import Path
from typing import Callable, Optional, List, Dict, Any
from dataclasses import dataclass

# ============================================================================
# CONFIGURATION - Edit these rules for your batch changes
# ============================================================================

@dataclass
class AnnotationRule:
    """A rule for batch annotation."""
    name: str
    description: str
    condition: Callable[[Dict], bool]  # Function that returns True if rule applies
    new_tier: Optional[float] = None    # New tier to set (None = don't change). Can be 2.5 for WRONG STATE
    note: Optional[str] = None          # Note to add (None = don't change)

# Define your rules here:
RULES: List[AnnotationRule] = [
    # Rule 1: Alaska Borough rule
    AnnotationRule(
        name="alaska_borough",
        description="Alaska target + 'borough' in steered output + tier < 3 -> tier 3",
        condition=lambda swap: (
            swap.get('target', {}).get('state', '').lower() == 'alaska' and
            'borough' in swap.get('evaluation', {}).get('raw', {}).get('steered_output', '').lower() and
            swap.get('classification', {}).get('tier', 0) < 3
        ),
        new_tier=3,
        note="In Alaska, a borough is an administrative division similar to a county in other U.S. states"
    ),
    
    # Add more rules here as needed:
    # 
    # Example: Set tier 2.5 (WRONG STATE) for specific patterns
    # AnnotationRule(
    #     name="wrong_state_example",
    #     description="Example of setting WRONG STATE tier",
    #     condition=lambda swap: (
    #         # Your condition here
    #         swap.get('classification', {}).get('tier', 0) < 3 and
    #         # Check if a different state appears in steered output
    #         'some_other_state' in swap.get('evaluation', {}).get('raw', {}).get('steered_output', '').lower()
    #     ),
    #     new_tier=2.5,  # WRONG STATE
    #     note="Reason for this classification"
    # ),
]

# ============================================================================
# SCRIPT LOGIC - No need to edit below this line
# ============================================================================

def load_swap(path: Path) -> Optional[Dict]:
    """Load a swap JSON file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"  Warning: Failed to load {path}: {e}")
        return None

def save_swap(path: Path, data: Dict) -> bool:
    """Save a swap JSON file."""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except IOError as e:
        print(f"  Error: Failed to save {path}: {e}")
        return False

def apply_rule(swap: Dict, rule: AnnotationRule) -> Dict:
    """Apply a rule to a swap, returning the modified swap."""
    if 'classification' not in swap:
        swap['classification'] = {}
    
    if rule.new_tier is not None:
        swap['classification']['tier'] = rule.new_tier
    
    if rule.note is not None:
        swap['classification']['notes'] = rule.note
    
    swap['classification']['manually_edited'] = True
    swap['classification']['batch_rule'] = rule.name
    
    return swap

def find_matching_swaps(data_dir: Path, rules: List[AnnotationRule]) -> Dict[str, List[tuple]]:
    """Find all swaps that match each rule."""
    matches = {rule.name: [] for rule in rules}
    
    by_source_dir = data_dir / "_swaps" / "by_source"
    if not by_source_dir.exists():
        print(f"Error: Directory not found: {by_source_dir}")
        return matches
    
    total_files = 0
    for source_dir in sorted(by_source_dir.iterdir()):
        if not source_dir.is_dir():
            continue
        
        for swap_file in sorted(source_dir.glob("to_*.json")):
            total_files += 1
            swap = load_swap(swap_file)
            if swap is None:
                continue
            
            for rule in rules:
                if rule.condition(swap):
                    from_slug = source_dir.name
                    to_slug = swap_file.stem.replace("to_", "")
                    current_tier = swap.get('classification', {}).get('tier', '?')
                    steered_preview = swap.get('evaluation', {}).get('raw', {}).get('steered_output', '')[:100]
                    matches[rule.name].append((swap_file, from_slug, to_slug, current_tier, steered_preview, swap))
    
    print(f"\nScanned {total_files} swap files.\n")
    return matches

def preview_changes(matches: Dict[str, List[tuple]], rules: List[AnnotationRule]):
    """Show what changes would be made."""
    total_changes = 0
    
    for rule in rules:
        rule_matches = matches[rule.name]
        if not rule_matches:
            print(f"📋 {rule.name}: No matches found")
            print(f"   {rule.description}\n")
            continue
        
        print(f"📋 {rule.name}: {len(rule_matches)} matches")
        print(f"   {rule.description}")
        print(f"   → Will set tier to: {rule.new_tier}")
        print(f"   → Will set note to: \"{rule.note[:50]}...\"" if rule.note and len(rule.note) > 50 else f"   → Will set note to: \"{rule.note}\"")
        print()
        
        for swap_file, from_slug, to_slug, current_tier, steered_preview, _ in rule_matches[:5]:
            print(f"   • {from_slug} → {to_slug} (current tier: {current_tier})")
            # Show relevant part of steered output
            if 'borough' in steered_preview.lower():
                idx = steered_preview.lower().find('borough')
                start = max(0, idx - 30)
                end = min(len(steered_preview), idx + 40)
                snippet = steered_preview[start:end]
                print(f"     \"...{snippet}...\"")
        
        if len(rule_matches) > 5:
            print(f"   ... and {len(rule_matches) - 5} more")
        
        print()
        total_changes += len(rule_matches)
    
    return total_changes

def apply_changes(matches: Dict[str, List[tuple]], rules: List[AnnotationRule]):
    """Apply the changes."""
    total_applied = 0
    total_failed = 0
    
    for rule in rules:
        rule_matches = matches[rule.name]
        if not rule_matches:
            continue
        
        print(f"\n🔧 Applying {rule.name}...")
        
        for swap_file, from_slug, to_slug, _, _, swap in rule_matches:
            modified_swap = apply_rule(swap, rule)
            if save_swap(swap_file, modified_swap):
                print(f"   ✓ {from_slug} → {to_slug}")
                total_applied += 1
            else:
                print(f"   ✗ {from_slug} → {to_slug} (failed)")
                total_failed += 1
    
    return total_applied, total_failed

def main():
    import sys
    
    # Paths
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / "output" / "usa_states_batch"
    
    if not data_dir.exists():
        print(f"Error: Data directory not found: {data_dir}")
        sys.exit(1)
    
    # Parse args
    preview_mode = "--preview" in sys.argv or len(sys.argv) == 1
    apply_mode = "--apply" in sys.argv
    
    if not preview_mode and not apply_mode:
        print(__doc__)
        sys.exit(0)
    
    print("=" * 60)
    print("Batch Annotation Tool")
    print("=" * 60)
    print(f"Data directory: {data_dir}")
    print(f"Rules defined: {len(RULES)}")
    print()
    
    # Find matches
    print("Scanning for matches...")
    matches = find_matching_swaps(data_dir, RULES)
    
    if preview_mode:
        print("=" * 60)
        print("PREVIEW MODE (no changes will be made)")
        print("=" * 60)
        total = preview_changes(matches, RULES)
        print("=" * 60)
        print(f"Total swaps that would be modified: {total}")
        print()
        print("To apply these changes, run:")
        print("  python batch_annotate.py --apply")
    
    elif apply_mode:
        # Confirm
        total_matches = sum(len(m) for m in matches.values())
        if total_matches == 0:
            print("No matches found. Nothing to do.")
            sys.exit(0)
        
        print("=" * 60)
        print("APPLY MODE")
        print("=" * 60)
        preview_changes(matches, RULES)
        
        print("=" * 60)
        confirm = input(f"Apply changes to {total_matches} files? [y/N]: ")
        if confirm.lower() != 'y':
            print("Aborted.")
            sys.exit(0)
        
        applied, failed = apply_changes(matches, RULES)
        
        print()
        print("=" * 60)
        print(f"Done! Applied: {applied}, Failed: {failed}")
        print("=" * 60)

if __name__ == "__main__":
    main()

