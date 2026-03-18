"""
YAML config loader and validator for batch experiments.
Resolves seeds based on seeds_mode and validates required paths.
"""
import os
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional


def load_config(yaml_path: str) -> Dict[str, Any]:
    """Load and parse YAML config file."""
    with open(yaml_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config


def validate_config(config: Dict[str, Any]) -> List[str]:
    """
    Validate config structure and return list of errors.
    Returns empty list if valid.
    """
    errors = []
    
    # Required top-level keys
    required_keys = ['paths', 'model', 'features', 'get_activations', 'steps']
    for key in required_keys:
        if key not in config:
            errors.append(f"Missing required key: {key}")
    
    # Validate paths
    if 'paths' in config:
        if 'outputs_root' not in config['paths']:
            errors.append("Missing paths.outputs_root")
    
    # Validate model
    if 'model' in config:
        if 'id' not in config['model']:
            errors.append("Missing model.id")
        if 'source_set' not in config['model']:
            errors.append("Missing model.source_set")
    
    # Validate features
    if 'features' in config:
        if 'selection' not in config['features']:
            errors.append("Missing features.selection")
        if config['features'].get('selection') == 'cumulative_influence':
            if 'threshold' not in config['features']:
                errors.append("features.selection=cumulative_influence requires features.threshold")
    
    # Validate get_activations
    if 'get_activations' in config:
        if 'backend' not in config['get_activations']:
            errors.append("Missing get_activations.backend")
        backend = config['get_activations'].get('backend')
        if backend not in ['local', 'api']:
            errors.append(f"Invalid get_activations.backend: {backend} (must be 'local' or 'api')")
        if backend == 'local':
            local_cfg = config['get_activations'].get('local', {})
            gpus = local_cfg.get('gpus')
            if gpus is not None:
                if not isinstance(gpus, list) or not gpus:
                    errors.append("get_activations.local.gpus must be a non-empty list of GPU indices")
                else:
                    try:
                        for g in gpus:
                            if not isinstance(g, int) or g < 0:
                                raise ValueError("each element must be a non-negative integer")
                    except (ValueError, TypeError):
                        errors.append("get_activations.local.gpus must be a list of non-negative integers")
            batch_size = local_cfg.get('batch_size')
            if batch_size is not None:
                if not isinstance(batch_size, int) or batch_size <= 0:
                    errors.append("get_activations.local.batch_size must be a positive integer")
    
    # Validate steps
    if 'steps' in config:
        required_steps = ['graph_generation', 'feature_export', 'activations', 'grouping']
        for step in required_steps:
            if step not in config['steps']:
                errors.append(f"Missing steps.{step}")

    # Validate compute.remote batching knobs
    remote_cfg = config.get('compute', {}).get('remote', {})
    if remote_cfg.get('enabled'):
        batch_size = remote_cfg.get('batch_size')
        max_gpus = remote_cfg.get('max_gpus')

        if batch_size is not None:
            if not isinstance(batch_size, int) or batch_size <= 0:
                errors.append("compute.remote.batch_size must be a positive integer")
        if max_gpus is not None:
            if not isinstance(max_gpus, int) or max_gpus <= 0:
                errors.append("compute.remote.max_gpus must be a positive integer")
        max_retries = remote_cfg.get('max_retries')
        if max_retries is not None:
            if not isinstance(max_retries, int) or max_retries < 0:
                errors.append("compute.remote.max_retries must be a non-negative integer")

        # Ensure required connection fields exist
        host = remote_cfg.get('host')
        host_env = remote_cfg.get('host_env')
        if host and host_env:
            errors.append("compute.remote: specify either 'host' or 'host_env', not both")
        if not host and not host_env:
            errors.append("compute.remote requires 'host_env' (preferred) or literal 'host'")
        elif host_env and not isinstance(host_env, str):
            errors.append("compute.remote.host_env must be a string env var name")

        for key in ['user', 'base_dir', 'repo_dir', 'logs_dir', 'env_activate_cmd']:
            if key not in remote_cfg:
                errors.append(f"compute.remote missing required key '{key}' when enabled")
    
    return errors


def resolve_seeds(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Resolve seeds based on graph_generation.seeds_mode.
    Returns list of work items with: slug, graph_json (or prompt), entities (optional).
    """
    graph_gen = config.get('graph_generation', {})
    seeds_mode = graph_gen.get('seeds_mode', 'precomputed')
    
    if seeds_mode == 'precomputed':
        # Use precomputed_seeds list
        precomputed = config.get('precomputed_seeds', [])
        if not precomputed:
            raise ValueError("seeds_mode=precomputed but precomputed_seeds is empty")
        
        # Validate each seed has required fields
        for seed in precomputed:
            if 'slug' not in seed:
                raise ValueError(f"precomputed seed missing 'slug': {seed}")
            if 'graph_json' not in seed:
                raise ValueError(f"precomputed seed '{seed['slug']}' missing 'graph_json'")
        
        return precomputed
    
    elif seeds_mode == 'prompts_list':
        # Generate seeds from prompts_list
        prompts_list = graph_gen.get('prompts_list', {})
        items = prompts_list.get('items', [])
        
        if not items and 'file' in prompts_list:
            # Load from file
            prompts_file = prompts_list['file']
            with open(prompts_file, 'r', encoding='utf-8') as f:
                items = [line.strip() for line in f if line.strip()]
        
        if not items:
            raise ValueError("seeds_mode=prompts_list but no items or file provided")
        
        # Generate seeds with auto slugs
        seeds = []
        for i, prompt in enumerate(items):
            # Simple slug: first 3 words, lowercase, underscored
            words = prompt.split()[:3]
            slug = '_'.join(w.lower().strip('<>') for w in words)
            if not slug:
                slug = f"prompt_{i}"
            
            seeds.append({
                'slug': slug,
                'prompt': prompt,
                'mode': 'prompts_list'
            })
        
        return seeds
    
    elif seeds_mode == 'templated':
        # Generate seeds from template + entities
        templated = graph_gen.get('templated', {})
        seed_prompt_template = templated.get('seed_prompt')
        slug_template = templated.get('slug_template', '{slug}')
        entities_data = templated.get('entities', {})
        items = entities_data.get('items', [])
        
        if not seed_prompt_template:
            raise ValueError("seeds_mode=templated but templated.seed_prompt is missing")
        if not items:
            raise ValueError("seeds_mode=templated but templated.entities.items is empty")
        
        seeds = []
        for entity_set in items:
            # Fill template
            try:
                prompt = seed_prompt_template.format(**entity_set)
                slug = slug_template.format(**entity_set)
            except KeyError as e:
                raise ValueError(f"Template placeholder {e} not found in entity set: {entity_set}")
            
            seeds.append({
                'slug': slug,
                'prompt': prompt,
                'entity': entity_set,
                'mode': 'templated'
            })
        
        return seeds
    
    else:
        raise ValueError(f"Unknown seeds_mode: {seeds_mode}")


def get_seed_output_dir(config: Dict[str, Any], seed: Dict[str, Any]) -> Path:
    """Get output directory for a seed."""
    outputs_root = Path(config['paths']['outputs_root'])
    return outputs_root / seed['slug']


def get_seed_paths(config: Dict[str, Any], seed: Dict[str, Any]) -> Dict[str, Path]:
    """
    Get all relevant paths for a seed's pipeline.
    Returns dict with keys: base, graph_dir, probes_dir, grouping_dir, graph_json, etc.
    """
    base = get_seed_output_dir(config, seed)
    
    paths = {
        'base': base,
        'graph_dir': base / '00 Graph Generation',
        'probes_dir': base / '01 Prompt Probing',
        'grouping_dir': base / '02 Node Grouping',
    }
    
    # Specific files
    paths['graph_json'] = paths['graph_dir'] / 'graph.json'
    paths['graph_metrics_csv'] = paths['graph_dir'] / 'graph_feature_static_metrics.csv'
    paths['selected_features_json'] = paths['graph_dir'] / 'selected_features_with_nodes.json'
    paths['prompts_json'] = paths['probes_dir'] / 'prompts.json'
    paths['activations_dump_json'] = paths['probes_dir'] / 'activations_dump.json'
    paths['grouping_csv'] = paths['grouping_dir'] / 'node_grouping.csv'
    
    return paths


def plan_batches(seeds: List[Dict[str, Any]], batch_size: int) -> List[List[Dict[str, Any]]]:
    """
    Group seeds into batches of size batch_size.
    Returns list of batches preserving original order.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")

    if not seeds:
        return []

    batches: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []

    for seed in seeds:
        current.append(seed)
        if len(current) == batch_size:
            batches.append(current)
            current = []

    if current:
        batches.append(current)

    return batches

