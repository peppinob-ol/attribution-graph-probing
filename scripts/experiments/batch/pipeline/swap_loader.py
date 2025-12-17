"""
Swap experiment loader and configuration utilities.

Handles loading swap configurations, resolving swap pairs,
and validating inputs for batch swap experiments.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from .loader import load_config
from .graph_loader import validate_graph_inputs


# Absolute path to repo root (scripts/experiments/batch/pipeline -> parents[4])
REPO_ROOT = Path(__file__).resolve().parents[4]

_SWAPS_DIR_CONFIG_KEY = "_swaps_dir"


@dataclass
class SwapPair:
    """Represents a single swap experiment pair."""
    from_slug: str
    to_slug: str
    from_entity: Dict[str, str]  # {slug, city, state, capital}
    to_entity: Dict[str, str]
    
    @property
    def from_concept(self) -> str:
        """Get concept name for source (state name lowercase)."""
        return self.from_entity['state'].lower()
    
    @property
    def to_concept(self) -> str:
        """Get concept name for target (state name lowercase)."""
        return self.to_entity['state'].lower()
    
    @property
    def swap_id(self) -> str:
        """Unique identifier for this swap."""
        return f"{self.from_slug}__to__{self.to_slug}"
    
    @property
    def is_identity(self) -> bool:
        """True if this is an identity swap (same source and target)."""
        return self.from_slug == self.to_slug


def load_swap_config(config_path: str) -> Dict[str, Any]:
    """
    Load swap experiment configuration.
    
    If inputs.source_config is specified, loads entities from there.
    
    Args:
        config_path: Path to the swap config YAML file
    
    Returns:
        Merged configuration dict with entities populated
    """
    config = load_config(config_path)
    config_dir = Path(config_path).parent
    
    # Load entities from source config if specified
    inputs = config.get('inputs', {})
    source_config_path = inputs.get('source_config')
    
    # Resolve graphs_root to absolute path
    graphs_root = inputs.get('graphs_root', 'output/usa_states_batch')
    graphs_root_path = Path(graphs_root)

    if not graphs_root_path.is_absolute():
        candidate_repo = REPO_ROOT / graphs_root
        candidate_config = config_dir / graphs_root

        if candidate_repo.exists():
            graphs_root_path = candidate_repo
        elif candidate_config.exists():
            graphs_root_path = candidate_config
        else:
            graphs_root_path = candidate_repo  # Fall back (will fail validation later)
    
    # Update config with resolved absolute path
    resolved = graphs_root_path.resolve()
    config['inputs']['graphs_root'] = str(resolved)
    print(f"  [CONFIG] Resolved graphs_root: {resolved}")
    
    if source_config_path:
        # Resolve relative to config file location
        config_dir = Path(config_path).parent
        source_path = config_dir / source_config_path
        if not source_path.exists():
            # Try as absolute or relative to cwd
            source_path = Path(source_config_path)
        
        if source_path.exists():
            source_config = load_config(str(source_path))
            
            # Extract entities from source config
            # Path: graph_generation.templated.entities.items
            entities = (
                source_config
                .get('graph_generation', {})
                .get('templated', {})
                .get('entities', {})
                .get('items', [])
            )
            
            if entities:
                config['_entities'] = entities
                print(f"  [CONFIG] Loaded {len(entities)} entities from {source_config_path}")
            
            # Inherit compute settings if requested
            if config.get('compute', {}).get('inherit_from_source', False):
                source_compute = source_config.get('compute', {})
                override_compute = config.get('compute', {})

                merged_compute = dict(source_compute) if source_compute else {}
                # Merge top-level keys (non-remote)
                for key, value in override_compute.items():
                    if key != 'remote':
                        merged_compute[key] = value

                # Merge remote settings deeply
                source_remote = (source_compute or {}).get('remote', {})
                override_remote = override_compute.get('remote', {})

                merged_remote = dict(source_remote) if source_remote else {}
                merged_remote.update(override_remote or {})

                if merged_remote:
                    merged_compute['remote'] = merged_remote

                config['compute'] = merged_compute
                print("  [CONFIG] Inherited compute settings from source config")
        else:
            raise FileNotFoundError(f"Source config not found: {source_config_path}")
    
    # Validate we have entities
    if '_entities' not in config or not config['_entities']:
        raise ValueError("No entities found. Specify inputs.source_config or provide entities directly.")
    
    return config


def resolve_swap_pairs(config: Dict[str, Any]) -> List[SwapPair]:
    """
    Generate swap pairs based on configuration mode.
    
    Modes:
        - 'matrix': Generate all NxN combinations
        - 'defined_pairs': Use explicitly defined pairs
    
    Args:
        config: Loaded swap configuration
    
    Returns:
        List of SwapPair objects
    """
    entities = config.get('_entities', [])
    swap_config = config.get('swap', {})
    mode = swap_config.get('mode', 'matrix')
    
    # Build entity lookup by slug
    entity_by_slug: Dict[str, Dict[str, str]] = {
        e['slug']: e for e in entities
    }
    
    pairs: List[SwapPair] = []
    
    if mode == 'matrix':
        # Generate all NxN combinations
        include_identity = swap_config.get('include_identity', True)
        
        # Optional: filter to a subset of entities
        subset_slugs = swap_config.get('subset')
        if subset_slugs:
            subset_set = set(subset_slugs)
            filtered_entities = [e for e in entities if e['slug'] in subset_set]
            if len(filtered_entities) < len(subset_slugs):
                found = {e['slug'] for e in filtered_entities}
                missing = subset_set - found
                print(f"  [WARNING] Subset entities not found: {missing}")
            matrix_entities = filtered_entities
            print(f"  [PAIRS] Using subset of {len(matrix_entities)} entities")
        else:
            matrix_entities = entities
        
        for from_entity in matrix_entities:
            for to_entity in matrix_entities:
                # Skip identity swaps if not wanted
                if from_entity['slug'] == to_entity['slug'] and not include_identity:
                    continue
                
                pairs.append(SwapPair(
                    from_slug=from_entity['slug'],
                    to_slug=to_entity['slug'],
                    from_entity=from_entity,
                    to_entity=to_entity,
                ))
        
        n_identity = len(matrix_entities) if include_identity else 0
        print(f"  [PAIRS] Matrix mode: {len(pairs)} pairs ({len(matrix_entities)}x{len(matrix_entities)}, {n_identity} identity)")
    
    elif mode == 'defined_pairs':
        # Use explicitly defined pairs
        defined = swap_config.get('pairs', [])
        
        for pair_def in defined:
            # Support both list format [from, to] and dict format {from:, to:}
            if isinstance(pair_def, list) and len(pair_def) == 2:
                from_slug, to_slug = pair_def
            elif isinstance(pair_def, dict):
                from_slug = pair_def.get('from') or pair_def.get('from_slug')
                to_slug = pair_def.get('to') or pair_def.get('to_slug')
            else:
                raise ValueError(f"Invalid pair definition: {pair_def}")
            
            def resolve_slug(slug: str, role: str) -> str:
                if slug in entity_by_slug:
                    return slug
                slug_lower = slug.lower()
                for canonical_slug in entity_by_slug.keys():
                    if canonical_slug.lower() == slug_lower:
                        return canonical_slug
                raise ValueError(f"Unknown {role} slug: {slug}")

            from_slug = resolve_slug(from_slug, "source")
            to_slug = resolve_slug(to_slug, "target")
            
            pairs.append(SwapPair(
                from_slug=from_slug,
                to_slug=to_slug,
                from_entity=entity_by_slug[from_slug],
                to_entity=entity_by_slug[to_slug],
            ))
        
        print(f"  [PAIRS] Defined pairs mode: {len(pairs)} pairs")
    
    else:
        raise ValueError(f"Unknown swap mode: {mode}")
    
    return pairs


def validate_swap_inputs(
    config: Dict[str, Any],
    pairs: List[SwapPair],
) -> List[str]:
    """
    Validate that all required graph files exist for the swap pairs.
    
    Args:
        config: Loaded swap configuration
        pairs: List of swap pairs to validate
    
    Returns:
        List of error messages (empty if all inputs are valid)
    """
    graphs_root = Path(config.get('inputs', {}).get('graphs_root', 'output/usa_states_batch'))
    
    # Collect unique slugs to validate
    slugs_to_check = set()
    for pair in pairs:
        slugs_to_check.add(pair.from_slug)
        slugs_to_check.add(pair.to_slug)
    
    errors: List[str] = []
    
    for slug in sorted(slugs_to_check):
        # Use case-insensitive directory lookup
        graph_dir = _find_graph_dir_case_insensitive(graphs_root, slug)
        
        if not graph_dir.exists():
            errors.append(f"Graph directory not found: {graph_dir} (slug: {slug})")
            continue
        
        # Validate required files
        file_errors = validate_graph_inputs(graph_dir)
        errors.extend(file_errors)
    
    if errors:
        print(f"  [VALIDATE] {len(errors)} validation errors found")
    else:
        print(f"  [VALIDATE] All {len(slugs_to_check)} graph directories validated OK")
    
    return errors


def get_swap_output_path(
    config: Dict[str, Any],
    pair: SwapPair,
) -> Path:
    """
    Get the output file path for a swap result.
    
    Structure: {outputs_root}/_swaps/by_source/{from_slug}/to_{to_slug}.json
    
    Args:
        config: Loaded swap configuration
        pair: The swap pair
    
    Returns:
        Path to the output JSON file
    """
    graphs_root = Path(config.get('inputs', {}).get('graphs_root', 'output/usa_states_batch'))
    swaps_dir = Path(config.get(_SWAPS_DIR_CONFIG_KEY) or (graphs_root / "_swaps"))
    
    output_dir = swaps_dir / "by_source" / pair.from_slug
    output_file = output_dir / f"to_{pair.to_slug}.json"
    
    return output_file


def _find_graph_dir_case_insensitive(graphs_root: Path, slug: str) -> Path:
    """
    Find graph directory matching slug, case-insensitively.
    
    Handles mismatch between config slugs (e.g., 'alabama_birmingham')
    and actual directory names (e.g., 'alabama_Birmingham').
    
    Args:
        graphs_root: Root directory containing graph folders
        slug: The slug to find
    
    Returns:
        Path to the matching directory (or original path if not found)
    """
    graphs_root = Path(graphs_root)
    
    # Try exact match first
    exact_path = graphs_root / slug
    if exact_path.exists():
        return exact_path
    
    # Try case-insensitive match
    slug_lower = slug.lower()
    if graphs_root.exists():
        try:
            for entry in graphs_root.iterdir():
                if entry.is_dir() and entry.name.lower() == slug_lower:
                    return entry
        except (PermissionError, OSError) as e:
            print(f"  Warning: Error iterating {graphs_root}: {e}")
    
    # Return original (will fail validation with clear error)
    return exact_path


def get_swap_paths(
    config: Dict[str, Any],
    pair: SwapPair,
) -> Dict[str, Path]:
    """
    Get all relevant paths for a swap experiment.
    
    Args:
        config: Loaded swap configuration
        pair: The swap pair
    
    Returns:
        Dict with keys: from_graph_dir, to_graph_dir, output_file, work_dir
    """
    graphs_root = Path(config.get('inputs', {}).get('graphs_root', 'output/usa_states_batch'))
    swaps_dir = Path(config.get(_SWAPS_DIR_CONFIG_KEY) or (graphs_root / "_swaps"))
    
    return {
        'from_graph_dir': _find_graph_dir_case_insensitive(graphs_root, pair.from_slug),
        'to_graph_dir': _find_graph_dir_case_insensitive(graphs_root, pair.to_slug),
        'output_file': get_swap_output_path(config, pair),
        'work_dir': swaps_dir / "work" / pair.swap_id,
    }


def filter_existing_pairs(
    config: Dict[str, Any],
    pairs: List[SwapPair],
    force: bool = False,
) -> Tuple[List[SwapPair], List[SwapPair]]:
    """
    Filter pairs into pending and already-completed.
    
    Args:
        config: Loaded swap configuration
        pairs: All swap pairs
        force: If True, return all pairs as pending
    
    Returns:
        Tuple of (pending_pairs, skipped_pairs)
    """
    if force:
        return pairs, []
    
    pending = []
    skipped = []
    
    for pair in pairs:
        output_path = get_swap_output_path(config, pair)
        if output_path.exists():
            skipped.append(pair)
        else:
            pending.append(pair)
    
    if skipped:
        print(f"  [SKIP] {len(skipped)} pairs already completed (use --force to re-run)")
    
    return pending, skipped

