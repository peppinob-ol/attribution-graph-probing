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


def _fuzzy_contains(text: str, target: str) -> bool:
    """Check if *target* appears in *text* after normalising punctuation.

    Catches near-misses like "J.R.R Tolkien" vs "J.R.R. Tolkien".
    """
    if not text or not target:
        return False
    norm_target = target.replace('.', '').replace('-', ' ').lower()
    norm_text = text.replace('.', '').replace('-', ' ').lower()
    return bool(norm_target and norm_target in norm_text)


def _first_token_matches(steered_topk: List[Dict[str, Any]],
                         to_answer: str) -> bool:
    """Return True when the steered first token is a substring of the target answer.

    Handles subword tokens (e.g. "Dost" matching "Dostoevsky" in
    "Fyodor Dostoevsky") by checking the full answer string.
    Requires token length >= 2 to avoid trivial single-char matches.
    """
    if not steered_topk or not to_answer:
        return False
    steered_first = (steered_topk[0].get('token', '') or '').strip().lower()
    if len(steered_first) < 2:
        return False
    answer_norm = to_answer.replace('.', '').lower()
    return steered_first in answer_norm


def _get_answer_field(concept_fields: Optional[List[str]] = None) -> str:
    """Return the entity field that represents the expected model answer.

    Convention: the last element of concept_fields is the answer.
    Falls back to "capital" for backward-compatible USA behaviour.
    """
    if concept_fields and len(concept_fields) >= 1:
        return concept_fields[-1]
    return "capital"


def evaluate_swap(
    result: Dict[str, Any],
    entity_from: Dict[str, str],
    entity_to: Dict[str, str],
    concept_fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Capture all metrics for a swap result for later analysis.

    Domain-agnostic: uses ``concept_fields`` (from the swap config) to
    decide which entity field is the "answer" for exact-match checks.
    Falls back to ``capital`` when concept_fields is not provided (USA).

    Args:
        result: Raw steering result (steered, default, topk, etc.)
        entity_from: Source entity dict
        entity_to: Target entity dict
        concept_fields: Optional list of concept field names from swap config

    Returns:
        Dict with structured evaluation metrics
    """
    default_out = result.get('default', '')
    steered_out = result.get('steered', '')
    default_topk = result.get('default_topk', [])
    steered_topk = result.get('steered_topk', [])

    answer_field = _get_answer_field(concept_fields)
    from_answer = entity_from.get(answer_field, '')
    to_answer = entity_to.get(answer_field, '')

    evaluation = {
        'ground_truth': {k: entity_from.get(k, '') for k in entity_from if k != 'slug'},
        'ground_truth_to': {k: entity_to.get(k, '') for k in entity_to if k != 'slug'},
        'answer_field': answer_field,
        'from_answer': from_answer,
        'to_answer': to_answer,

        'exact_match': {
            'default_has_from_answer': bool(from_answer and from_answer in default_out),
            'steered_has_to_answer': bool(to_answer and to_answer in steered_out),
            'steered_has_to_answer_fuzzy': bool(
                to_answer and _fuzzy_contains(steered_out, to_answer)),
            'steered_has_from_answer': bool(from_answer and from_answer in steered_out),
            'from_suppressed': bool(from_answer and from_answer not in steered_out),
            'first_token_matches_target': _first_token_matches(
                steered_topk, to_answer),
            # Backward-compatible aliases for USA-based analysis code
            'default_has_from_capital': bool(from_answer and from_answer in default_out),
            'steered_has_to_capital': bool(to_answer and to_answer in steered_out),
            'steered_has_from_capital': bool(from_answer and from_answer in steered_out),
        },

        'first_token': {
            'default': default_topk[0].get('token', '') if default_topk else '',
            'default_prob': default_topk[0].get('prob', 0) if default_topk else 0,
            'steered': steered_topk[0].get('token', '') if steered_topk else '',
            'steered_prob': steered_topk[0].get('prob', 0) if steered_topk else 0,
        },

        'target_in_topk': {
            'to_answer_in_default_topk': _find_token_prob(default_topk, to_answer),
            'to_answer_in_steered_topk': _find_token_prob(steered_topk, to_answer),
            'from_answer_in_default_topk': _find_token_prob(default_topk, from_answer),
            'from_answer_in_steered_topk': _find_token_prob(steered_topk, from_answer),
            # Backward-compatible aliases
            'to_capital_in_default_topk': _find_token_prob(default_topk, to_answer),
            'to_capital_in_steered_topk': _find_token_prob(steered_topk, to_answer),
            'from_capital_in_default_topk': _find_token_prob(default_topk, from_answer),
            'from_capital_in_steered_topk': _find_token_prob(steered_topk, from_answer),
        },

        'raw': {
            'default_output': default_out,
            'steered_output': steered_out,
            'default_topk': default_topk,
            'steered_topk': steered_topk,
        },
    }

    if 'logit_trajectory' in result:
        evaluation['logit_trajectory'] = result['logit_trajectory']
    if 'baseline_logits' in result:
        evaluation['baseline_logits'] = result['baseline_logits']
    if 'position_0_comparison' in result:
        evaluation['position_0_comparison'] = result['position_0_comparison']

    return evaluation


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
    
    # Domain-agnostic: include full entity (state/capital/city for USA; character/book/author for books)
    source_ent = dict(pair.from_entity)
    target_ent = dict(pair.to_entity)
    source_ent['slug'] = pair.from_slug
    source_ent['prompt'] = raw_result.get('prompt', '')
    source_ent['concept'] = pair.from_concept
    target_ent['slug'] = pair.to_slug
    target_ent['concept'] = pair.to_concept
    return {
        'swap_id': pair.swap_id,
        'source': source_ent,
        'target': target_ent,
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

