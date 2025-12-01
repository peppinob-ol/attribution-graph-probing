"""
Interactive CLI browser for swap experiment results.

Browse individual swap results with detailed output comparison.
Supports colored output and note-taking.

Usage:
    python scripts/experiments/batch/browse_swaps.py
    python scripts/experiments/batch/browse_swaps.py --tier 5
    python scripts/experiments/batch/browse_swaps.py --from california --to texas
    python scripts/experiments/batch/browse_swaps.py --list
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from pipeline.swap_classifier import classify_swap_result, SwapTier

# Try to import colorama for colored output
try:
    from colorama import init, Fore, Back, Style
    init()
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False
    # Fallback - empty strings
    class Fore:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ""
        LIGHTRED_EX = LIGHTGREEN_EX = LIGHTYELLOW_EX = LIGHTBLUE_EX = ""
        LIGHTMAGENTA_EX = LIGHTCYAN_EX = LIGHTWHITE_EX = ""
    class Back:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ""
    class Style:
        BRIGHT = DIM = NORMAL = RESET_ALL = ""

# Global notes storage
NOTES: Dict[str, str] = {}


def load_all_swap_results(swaps_dir: Path) -> List[Dict[str, Any]]:
    """Load all swap result JSON files."""
    by_source_dir = swaps_dir / "by_source"
    if not by_source_dir.exists():
        raise FileNotFoundError(f"by_source directory not found: {by_source_dir}")
    
    results = []
    for source_dir in sorted(by_source_dir.iterdir()):
        if not source_dir.is_dir():
            continue
        for result_file in sorted(source_dir.glob("to_*.json")):
            try:
                with open(result_file, 'r', encoding='utf-8') as f:
                    result = json.load(f)
                    result['_file'] = str(result_file)
                    results.append(result)
            except (json.JSONDecodeError, IOError) as e:
                print(f"  Warning: Failed to load {result_file}: {e}")
    return results


def filter_results(
    results: List[Dict[str, Any]],
    from_state: Optional[str] = None,
    to_state: Optional[str] = None,
    tier: Optional[int] = None,
    tier_min: Optional[int] = None,
    tier_max: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Filter results by criteria."""
    filtered = results
    
    if from_state:
        from_lower = from_state.lower()
        filtered = [r for r in filtered 
                   if from_lower in r['source']['state'].lower() 
                   or from_lower in r['source']['slug'].lower()]
    
    if to_state:
        to_lower = to_state.lower()
        filtered = [r for r in filtered 
                   if to_lower in r['target']['state'].lower()
                   or to_lower in r['target']['slug'].lower()]
    
    # Add classification if not present
    for r in filtered:
        if 'classification' not in r:
            r['classification'] = classify_swap_result(r).to_dict()
    
    if tier is not None:
        filtered = [r for r in filtered if r['classification']['tier'] == tier]
    
    if tier_min is not None:
        filtered = [r for r in filtered if r['classification']['tier'] >= tier_min]
    
    if tier_max is not None:
        filtered = [r for r in filtered if r['classification']['tier'] <= tier_max]
    
    return filtered


def get_tier_color(tier: int) -> str:
    """Get color code for tier value."""
    colors = {
        5: Fore.LIGHTGREEN_EX,   # PERFECT - bright green
        4: Fore.GREEN,            # TARGET_STATE_CITY - green
        3: Fore.YELLOW,           # TARGET_STATE_ONLY - yellow
        2: Fore.LIGHTYELLOW_EX,   # SUPPRESSED_ONLY - light yellow
        1: Fore.LIGHTRED_EX,      # SOURCE_PERSISTS - light red
        0: Fore.RED,              # WRONG_STATE - red
    }
    return colors.get(tier, Fore.WHITE)


def display_result(result: Dict[str, Any], index: int = 0, total: int = 1, show_note_prompt: bool = False) -> Optional[str]:
    """Display a single swap result in detail with colors."""
    source = result['source']
    target = result['target']
    evaluation = result.get('evaluation', {})
    raw = evaluation.get('raw', {})
    classification = result.get('classification', {})
    swap_id = result.get('swap_id', f"{source['slug']}__to__{target['slug']}")
    
    tier = classification.get('tier', 2)
    tier_name = classification.get('tier_name', '?')
    tier_color = get_tier_color(tier)
    
    # Header
    print(f"\n{Style.BRIGHT}{Fore.CYAN}{'=' * 70}{Style.RESET_ALL}")
    print(f"{Style.BRIGHT}[{index + 1}/{total}] {Fore.MAGENTA}{source['slug']}{Fore.WHITE} --> {Fore.CYAN}{target['slug']}{Style.RESET_ALL}")
    print(f"{Style.BRIGHT}{Fore.CYAN}{'=' * 70}{Style.RESET_ALL}")
    
    # States and capitals - side by side
    print(f"\n{Style.BRIGHT}{'FROM:':<20} {'TO:':<20}{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}{source['state']:<20}{Style.RESET_ALL} {Fore.CYAN}{target['state']:<20}{Style.RESET_ALL}")
    print(f"  Capital: {Fore.YELLOW}{source['capital']:<12}{Style.RESET_ALL}   Capital: {Fore.LIGHTGREEN_EX}{target['capital']:<12}{Style.RESET_ALL}")
    print(f"  City: {source['city']:<14}   City: {target['city']:<14}")
    
    # Classification with color
    print(f"\n{Style.BRIGHT}TIER:{Style.RESET_ALL} {tier_color}{Style.BRIGHT}{tier} - {tier_name}{Style.RESET_ALL}")
    print(f"  {Fore.WHITE}{classification.get('notes', 'N/A')}{Style.RESET_ALL}")
    if classification.get('cities_found'):
        cities = classification['cities_found']
        if isinstance(cities, list):
            cities_str = ', '.join(cities)
        else:
            cities_str = str(cities)
        print(f"  Found: {Fore.YELLOW}{cities_str}{Style.RESET_ALL}")
    
    # Outputs
    print(f"\n{Fore.BLUE}{'-' * 70}{Style.RESET_ALL}")
    print(f"{Style.BRIGHT}DEFAULT OUTPUT:{Style.RESET_ALL}")
    default_out = raw.get('default_output', 'N/A')[:200]
    # Highlight source capital in default output
    if source['capital'] in default_out:
        default_out = default_out.replace(source['capital'], f"{Fore.YELLOW}{source['capital']}{Style.RESET_ALL}")
    print(f"  {default_out}")
    
    print(f"\n{Fore.BLUE}{'-' * 70}{Style.RESET_ALL}")
    print(f"{Style.BRIGHT}STEERED OUTPUT:{Style.RESET_ALL}")
    steered_out = raw.get('steered_output', 'N/A')[:250]
    # Highlight target capital in green, source capital in red
    if target['capital'] in steered_out:
        steered_out = steered_out.replace(target['capital'], f"{Fore.LIGHTGREEN_EX}{Style.BRIGHT}{target['capital']}{Style.RESET_ALL}")
    if source['capital'] in steered_out:
        steered_out = steered_out.replace(source['capital'], f"{Fore.RED}{source['capital']}{Style.RESET_ALL}")
    print(f"  {steered_out}")
    
    # First tokens
    first_token = evaluation.get('first_token', {})
    print(f"\n{Fore.BLUE}{'-' * 70}{Style.RESET_ALL}")
    print(f"{Style.BRIGHT}FIRST TOKEN:{Style.RESET_ALL}")
    default_tok = first_token.get('default', '?')
    steered_tok = first_token.get('steered', '?')
    print(f"  Default: {Fore.YELLOW}'{default_tok}'{Style.RESET_ALL} (prob: {first_token.get('default_prob', 0):.3f})")
    print(f"  Steered: {Fore.CYAN}'{steered_tok}'{Style.RESET_ALL} (prob: {first_token.get('steered_prob', 0):.3f})")
    
    # Exact match stats with color
    exact = evaluation.get('exact_match', {})
    print(f"\n{Fore.BLUE}{'-' * 70}{Style.RESET_ALL}")
    
    has_target = exact.get('steered_has_to_capital', False)
    suppressed = exact.get('from_suppressed', False)
    
    has_target_color = Fore.GREEN if has_target else Fore.RED
    suppressed_color = Fore.GREEN if suppressed else Fore.RED
    
    print(f"{Style.BRIGHT}STATUS:{Style.RESET_ALL}")
    print(f"  Steered has target capital: {has_target_color}{has_target}{Style.RESET_ALL}")
    print(f"  Source suppressed: {suppressed_color}{suppressed}{Style.RESET_ALL}")
    
    # Show existing note if any
    if swap_id in NOTES:
        print(f"\n{Fore.LIGHTYELLOW_EX}{Style.BRIGHT}YOUR NOTE:{Style.RESET_ALL}")
        print(f"  {Fore.LIGHTYELLOW_EX}{NOTES[swap_id]}{Style.RESET_ALL}")
    
    print(f"{Style.BRIGHT}{Fore.CYAN}{'=' * 70}{Style.RESET_ALL}")
    
    return swap_id


def display_list(results: List[Dict[str, Any]]) -> None:
    """Display a compact list of all results with colors."""
    print(f"\n{Style.BRIGHT}{'#':<4} {'FROM':<25} {'TO':<25} {'TIER':<20} {'NOTE':<6}{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'-' * 85}{Style.RESET_ALL}")
    
    for i, r in enumerate(results):
        source = r['source']
        target = r['target']
        if 'classification' not in r:
            r['classification'] = classify_swap_result(r).to_dict()
        
        tier = r['classification']['tier']
        tier_name = r['classification']['tier_name']
        tier_color = get_tier_color(tier)
        
        swap_id = r.get('swap_id', f"{source['slug']}__to__{target['slug']}")
        has_note = "*" if swap_id in NOTES else ""
        
        print(f"{i:<4} {Fore.MAGENTA}{source['slug']:<25}{Style.RESET_ALL} "
              f"{Fore.CYAN}{target['slug']:<25}{Style.RESET_ALL} "
              f"{tier_color}{tier} - {tier_name:<12}{Style.RESET_ALL} "
              f"{Fore.YELLOW}{has_note}{Style.RESET_ALL}")
    
    print(f"\n{Style.BRIGHT}Total: {len(results)} results{Style.RESET_ALL}")
    if NOTES:
        print(f"{Fore.YELLOW}* = has note ({len(NOTES)} notes total){Style.RESET_ALL}")


def add_note(swap_id: str) -> None:
    """Prompt user to add a note for current swap."""
    print(f"\n{Fore.LIGHTYELLOW_EX}Enter note (or press Enter to skip):{Style.RESET_ALL}")
    try:
        note = input(f"{Fore.LIGHTYELLOW_EX}> {Style.RESET_ALL}").strip()
        if note:
            NOTES[swap_id] = note
            print(f"{Fore.GREEN}Note saved.{Style.RESET_ALL}")
    except (EOFError, KeyboardInterrupt):
        pass


def display_all_notes() -> None:
    """Display all notes taken during the session."""
    if not NOTES:
        print(f"\n{Fore.YELLOW}No notes recorded.{Style.RESET_ALL}")
        return
    
    print(f"\n{Style.BRIGHT}{Fore.CYAN}{'=' * 70}")
    print(f"YOUR NOTES ({len(NOTES)} total)")
    print(f"{'=' * 70}{Style.RESET_ALL}\n")
    
    for i, (swap_id, note) in enumerate(NOTES.items(), 1):
        parts = swap_id.split('__to__')
        if len(parts) == 2:
            from_slug, to_slug = parts
        else:
            from_slug, to_slug = swap_id, "?"
        print(f"{Style.BRIGHT}{i}. {Fore.MAGENTA}{from_slug}{Fore.WHITE} -> {Fore.CYAN}{to_slug}{Style.RESET_ALL}")
        print(f"   {Fore.LIGHTYELLOW_EX}{note}{Style.RESET_ALL}\n")
    
    print(f"{Fore.CYAN}{'=' * 70}{Style.RESET_ALL}")


def save_notes(output_path: Path) -> None:
    """Save notes to a JSON file."""
    if not NOTES:
        print("No notes to save.")
        return
    
    notes_data = {
        'timestamp': datetime.now().isoformat(),
        'count': len(NOTES),
        'notes': [
            {'swap_id': swap_id, 'note': note}
            for swap_id, note in NOTES.items()
        ]
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(notes_data, f, indent=2)
    
    print(f"{Fore.GREEN}Notes saved to: {output_path}{Style.RESET_ALL}")


def interactive_browse(results: List[Dict[str, Any]], notes_file: Optional[Path] = None) -> None:
    """Interactive browsing mode with note-taking."""
    if not results:
        print("No results to browse.")
        return
    
    # Add classification to all results
    for r in results:
        if 'classification' not in r:
            r['classification'] = classify_swap_result(r).to_dict()
    
    current = 0
    total = len(results)
    
    print(f"\n{Fore.CYAN}Browsing {total} results. Type 'help' for commands.{Style.RESET_ALL}")
    
    while True:
        swap_id = display_result(results[current], current, total)
        
        print(f"\n{Style.DIM}[n]ext [p]rev [j #] [l]ist [m]emo [notes] [save] [0-5] [q]uit [help]{Style.RESET_ALL}")
        
        try:
            cmd = input(f"{Fore.CYAN}> {Style.RESET_ALL}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n")
            break
        
        cmd_lower = cmd.lower()
        
        if cmd_lower == 'q' or cmd_lower == 'quit':
            break
        elif cmd_lower == 'n' or cmd == '':
            current = (current + 1) % total
        elif cmd_lower == 'p':
            current = (current - 1) % total
        elif cmd_lower == 'l' or cmd_lower == 'list':
            display_list(results)
        elif cmd_lower == 'm' or cmd_lower == 'memo' or cmd_lower == 'note':
            add_note(swap_id)
        elif cmd_lower == 'notes' or cmd_lower == 'review':
            display_all_notes()
        elif cmd_lower == 'save':
            save_path = notes_file or Path('swap_notes.json')
            save_notes(save_path)
        elif cmd_lower == 'help' or cmd_lower == '?':
            print(f"""
{Style.BRIGHT}Commands:{Style.RESET_ALL}
  {Fore.CYAN}n{Style.RESET_ALL} or Enter  - Next result
  {Fore.CYAN}p{Style.RESET_ALL}           - Previous result
  {Fore.CYAN}j ##{Style.RESET_ALL}        - Jump to index ##
  {Fore.CYAN}l{Style.RESET_ALL}           - List all results
  {Fore.CYAN}m{Style.RESET_ALL}           - Add memo/note for current result
  {Fore.CYAN}notes{Style.RESET_ALL}       - Review all your notes
  {Fore.CYAN}save{Style.RESET_ALL}        - Save notes to JSON file
  {Fore.CYAN}0-5{Style.RESET_ALL}         - Filter by tier (0=fail, 5=perfect)
  {Fore.CYAN}q{Style.RESET_ALL}           - Quit
""")
        elif cmd_lower.startswith('j'):
            try:
                num = int(cmd_lower[1:].strip())
                if 0 <= num < total:
                    current = num
                else:
                    print(f"{Fore.RED}Index out of range (0-{total-1}){Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid number{Style.RESET_ALL}")
        elif cmd_lower.isdigit() and len(cmd_lower) <= 2:
            try:
                num = int(cmd_lower)
                if 0 <= num <= 5:
                    # Filter by tier
                    tier = num
                    filtered = [r for r in results if r['classification']['tier'] == tier]
                    if filtered:
                        print(f"\n{Fore.CYAN}Filtered to tier {tier}: {len(filtered)} results{Style.RESET_ALL}")
                        interactive_browse(filtered, notes_file)
                        return  # Return after nested browse
                    else:
                        print(f"{Fore.YELLOW}No results with tier {tier}{Style.RESET_ALL}")
                elif 0 <= num < total:
                    # Jump to index
                    current = num
                else:
                    print(f"{Fore.RED}Index out of range (0-{total-1}){Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid input{Style.RESET_ALL}")
        elif cmd and not cmd.startswith('#'):
            # Treat as a note if it's text
            NOTES[swap_id] = cmd
            print(f"{Fore.GREEN}Note saved: {cmd[:50]}...{Style.RESET_ALL}" if len(cmd) > 50 else f"{Fore.GREEN}Note saved.{Style.RESET_ALL}")
    
    # End of session - show notes
    if NOTES:
        print(f"\n{Style.BRIGHT}Session ending. You have {len(NOTES)} notes.{Style.RESET_ALL}")
        display_all_notes()
        
        # Offer to save
        try:
            save_prompt = input(f"{Fore.CYAN}Save notes to file? [y/N]: {Style.RESET_ALL}").strip().lower()
            if save_prompt == 'y' or save_prompt == 'yes':
                save_path = notes_file or Path('output/usa_states_batch/_swaps/_analysis/session_notes.json')
                save_path.parent.mkdir(parents=True, exist_ok=True)
                save_notes(save_path)
        except (EOFError, KeyboardInterrupt):
            pass


def main():
    parser = argparse.ArgumentParser(
        description='Browse swap experiment results interactively'
    )
    parser.add_argument(
        '--swaps-dir',
        type=str,
        default='output/usa_states_batch/_swaps',
        help='Path to _swaps directory'
    )
    parser.add_argument(
        '--from', '-f',
        dest='from_state',
        type=str,
        help='Filter by source state (partial match)'
    )
    parser.add_argument(
        '--to', '-t',
        dest='to_state',
        type=str,
        help='Filter by target state (partial match)'
    )
    parser.add_argument(
        '--tier',
        type=int,
        choices=[0, 1, 2, 3, 4, 5],
        help='Filter by exact tier (0-5)'
    )
    parser.add_argument(
        '--tier-min',
        type=int,
        choices=[0, 1, 2, 3, 4, 5],
        help='Filter by minimum tier'
    )
    parser.add_argument(
        '--tier-max',
        type=int,
        choices=[0, 1, 2, 3, 4, 5],
        help='Filter by maximum tier'
    )
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='Show list view instead of interactive browse'
    )
    parser.add_argument(
        '--show',
        type=int,
        help='Show single result by index (0-based)'
    )
    
    args = parser.parse_args()
    
    # Resolve swaps directory
    swaps_dir = Path(args.swaps_dir)
    if not swaps_dir.is_absolute():
        script_dir = Path(__file__).parent
        repo_root = script_dir.parents[2]
        candidate = repo_root / args.swaps_dir
        if candidate.exists():
            swaps_dir = candidate
    
    if not swaps_dir.exists():
        print(f"Error: Swaps directory not found: {swaps_dir}")
        return 1
    
    # Load results
    print(f"Loading from: {swaps_dir}")
    results = load_all_swap_results(swaps_dir)
    print(f"Loaded {len(results)} swap results")
    
    # Filter
    results = filter_results(
        results,
        from_state=args.from_state,
        to_state=args.to_state,
        tier=args.tier,
        tier_min=args.tier_min,
        tier_max=args.tier_max,
    )
    
    if not results:
        print("No results match the filters.")
        return 0
    
    print(f"After filtering: {len(results)} results")
    
    # Notes file path
    notes_file = Path(args.swaps_dir) / "_analysis" / "session_notes.json"
    
    # Display mode
    if args.show is not None:
        if 0 <= args.show < len(results):
            display_result(results[args.show], args.show, len(results))
        else:
            print(f"{Fore.RED}Index {args.show} out of range (0-{len(results)-1}){Style.RESET_ALL}")
    elif args.list:
        display_list(results)
    else:
        interactive_browse(results, notes_file)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

