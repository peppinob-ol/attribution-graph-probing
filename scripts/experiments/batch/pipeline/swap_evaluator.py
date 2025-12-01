"""
Swap experiment evaluation utilities.

Captures metrics for swap experiments for later analysis.
Follows "store dumb, analyze smart" principle - captures everything,
defers complex analysis to post-processing.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


def evaluate_swap(
    result: Dict[str, Any],
    entity_from: Dict[str, str],
    entity_to: Dict[str, str],
) -> Dict[str, Any]:
    """
    Capture all metrics for a swap result for later analysis.
    
    NOTE: exact_match is known to be imperfect for measuring swap success.
    A steered output of "San Francisco" when targeting California is a
    partial success, even though it's not the capital "Sacramento".
    Semantic similarity analysis is deferred to post-processing.
    
    Args:
        result: Raw steering result with keys:
            - steered: Steered output text
            - default: Default output text
            - steered_topk: List of {token, prob} for steered
            - default_topk: List of {token, prob} for default
            - intervention_count: Number of features modified
        entity_from: Source entity {slug, city, state, capital}
        entity_to: Target entity {slug, city, state, capital}
    
    Returns:
        Dict with structured evaluation metrics
    """
    default_out = result.get('default', '')
    steered_out = result.get('steered', '')
    default_topk = result.get('default_topk', [])
    steered_topk = result.get('steered_topk', [])
    
    return {
        # Ground truth from entities (for later analysis)
        'ground_truth': {
            'from_state': entity_from['state'],
            'from_capital': entity_from['capital'],
            'from_city': entity_from['city'],
            'to_state': entity_to['state'],
            'to_capital': entity_to['capital'],
            'to_city': entity_to['city'],
        },
        
        # Simple exact match checks (known to be imperfect)
        'exact_match': {
            'default_has_from_capital': entity_from['capital'] in default_out,
            'steered_has_to_capital': entity_to['capital'] in steered_out,
            'steered_has_from_capital': entity_from['capital'] in steered_out,
            'from_suppressed': entity_from['capital'] not in steered_out,
        },
        
        # First token prediction (most diagnostic for factual recall)
        'first_token': {
            'default': default_topk[0].get('token', '') if default_topk else '',
            'default_prob': default_topk[0].get('prob', 0) if default_topk else 0,
            'steered': steered_topk[0].get('token', '') if steered_topk else '',
            'steered_prob': steered_topk[0].get('prob', 0) if steered_topk else 0,
        },
        
        # Target token probability in topk
        'target_in_topk': {
            'to_capital_in_default_topk': _find_token_prob(default_topk, entity_to['capital']),
            'to_capital_in_steered_topk': _find_token_prob(steered_topk, entity_to['capital']),
            'from_capital_in_default_topk': _find_token_prob(default_topk, entity_from['capital']),
            'from_capital_in_steered_topk': _find_token_prob(steered_topk, entity_from['capital']),
        },
        
        # Raw outputs for semantic analysis later
        'raw': {
            'default_output': default_out,
            'steered_output': steered_out,
            'default_topk': default_topk,
            'steered_topk': steered_topk,
        },
    }


def _find_token_prob(topk: List[Dict[str, Any]], target: str) -> Optional[float]:
    """
    Find probability of target token in topk list.
    
    Handles common variations like leading space (" Sacramento" vs "Sacramento").
    
    Args:
        topk: List of {token, prob} dicts
        target: Target token to find
    
    Returns:
        Probability if found, None otherwise
    """
    if not topk or not target:
        return None
    
    # Handle both " Sacramento" and "Sacramento"
    target_variants = [
        target,
        f" {target}",
        target.lower(),
        f" {target.lower()}",
    ]
    
    for entry in topk:
        token = entry.get('token', '')
        if any(v in token for v in target_variants):
            return entry.get('prob')
    
    return None


def create_swap_result(
    pair,  # SwapPair
    raw_result: Dict[str, Any],
    evaluation: Dict[str, Any],
    config: Dict[str, Any],
    duration_ms: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Create a complete swap result record for storage.
    
    Args:
        pair: SwapPair object
        raw_result: Raw steering result
        evaluation: Output of evaluate_swap()
        config: Swap configuration
        duration_ms: Execution time in milliseconds
    
    Returns:
        Complete result dict ready for JSON serialization
    """
    ct_config = config.get('ct_steering', {})
    
    return {
        'swap_id': pair.swap_id,
        'source': {
            'slug': pair.from_slug,
            'prompt': raw_result.get('prompt', ''),
            'concept': pair.from_concept,
            'state': pair.from_entity['state'],
            'capital': pair.from_entity['capital'],
            'city': pair.from_entity['city'],
        },
        'target': {
            'slug': pair.to_slug,
            'concept': pair.to_concept,
            'state': pair.to_entity['state'],
            'capital': pair.to_entity['capital'],
            'city': pair.to_entity['city'],
        },
        'interventions': {
            'ablate_count': raw_result.get('ablate_count', 0),
            'amplify_count': raw_result.get('amplify_count', 0),
            'total_count': raw_result.get('intervention_count', 0),
        },
        'evaluation': evaluation,
        'config': {
            'M_ablate': ct_config.get('M_ablate', 0.0),
            'M_amplify': ct_config.get('M_amplify', 2.0),
            'temperature': ct_config.get('temperature', 0.3),
            'seed': ct_config.get('seed', 42),
            'freeze_attention': ct_config.get('freeze_attention', False),
        },
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'duration_ms': duration_ms,
            'is_identity': pair.is_identity,
        },
    }


def aggregate_results_to_matrix(
    results: List[Dict[str, Any]],
    entities: List[Dict[str, str]],
    metric: str = 'steered_has_to_capital',
) -> pd.DataFrame:
    """
    Create a NxN matrix from swap results.
    
    Args:
        results: List of swap result dicts
        entities: List of entity dicts (for row/column ordering)
        metric: Which metric to use for matrix values.
            Options: 'steered_has_to_capital', 'from_suppressed',
                     'to_capital_in_steered_topk', etc.
    
    Returns:
        DataFrame with sources as rows, targets as columns
    """
    # Get ordered list of slugs
    slugs = [e['slug'] for e in entities]
    
    # Initialize matrix with NaN
    matrix = pd.DataFrame(
        index=slugs,
        columns=slugs,
        dtype=float,
    )
    matrix.index.name = 'from_slug'
    matrix.columns.name = 'to_slug'
    
    # Fill in values from results
    for result in results:
        from_slug = result['source']['slug']
        to_slug = result['target']['slug']
        
        # Navigate to metric value
        if metric in result.get('evaluation', {}).get('exact_match', {}):
            value = result['evaluation']['exact_match'][metric]
            # Convert bool to float
            value = 1.0 if value else 0.0
        elif metric in result.get('evaluation', {}).get('target_in_topk', {}):
            value = result['evaluation']['target_in_topk'][metric]
            if value is None:
                value = 0.0
        else:
            value = float('nan')
        
        matrix.loc[from_slug, to_slug] = value
    
    return matrix


def create_summary(
    results: List[Dict[str, Any]],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Create a summary of the swap experiment.
    
    Args:
        results: List of swap result dicts
        config: Swap configuration
    
    Returns:
        Summary dict with aggregate statistics
    """
    if not results:
        return {'error': 'No results to summarize'}
    
    # Count successes by different metrics
    exact_match_successes = sum(
        1 for r in results
        if r.get('evaluation', {}).get('exact_match', {}).get('steered_has_to_capital', False)
    )
    
    suppression_successes = sum(
        1 for r in results
        if r.get('evaluation', {}).get('exact_match', {}).get('from_suppressed', False)
    )
    
    identity_results = [r for r in results if r.get('metadata', {}).get('is_identity', False)]
    swap_results = [r for r in results if not r.get('metadata', {}).get('is_identity', False)]
    
    return {
        'experiment_name': config.get('experiment_name', 'unknown'),
        'timestamp': datetime.now().isoformat(),
        'counts': {
            'total_pairs': len(results),
            'identity_pairs': len(identity_results),
            'swap_pairs': len(swap_results),
        },
        'success_rates': {
            'exact_match_rate': exact_match_successes / len(results) if results else 0,
            'suppression_rate': suppression_successes / len(results) if results else 0,
        },
        'config': {
            'M_ablate': config.get('ct_steering', {}).get('M_ablate'),
            'M_amplify': config.get('ct_steering', {}).get('M_amplify'),
            'mode': config.get('swap', {}).get('mode'),
        },
    }

