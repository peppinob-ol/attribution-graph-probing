"""
Graph data loader for batch experiments.

Provides shared utilities for loading graph data from batch pipeline outputs.
Extracted from texas_steering_pilot_ct.py for reuse across swap experiments.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple

import pandas as pd


def load_graph_data(graph_dir: Path, verbose: bool = True) -> Dict[str, Any]:
    """Load all data from a graph directory.
    
    Supports two directory structures:
    1. Batch pipeline structure:
       - {graph_dir}/02 Node Grouping/node_grouping.csv
       - {graph_dir}/00 Graph Generation/graph_feature_static_metrics.csv
       - {graph_dir}/00 Graph Generation/graph.json
    2. Flat structure:
       - {graph_dir}/node_grouping.csv
       - {graph_dir}/graph_feature_static_metrics.csv
       - {graph_dir}/graph.json
    
    Args:
        graph_dir: Path to the graph directory (e.g., output/usa_states_batch/texas_Dallas)
        verbose: If True, print loading progress
    
    Returns:
        Dict with keys:
            - 'grouping': DataFrame from node_grouping.csv
            - 'metrics': DataFrame from graph_feature_static_metrics.csv
            - 'prompt': Original prompt from graph.json metadata
            - 'activations_map': Dict mapping (layer, feature, position) to activation values
            - 'graph_dir': Path object of the graph directory
    """
    graph_dir = Path(graph_dir)
    
    # Try batch pipeline structure first
    grouping_path = graph_dir / "02 Node Grouping" / "node_grouping.csv"
    metrics_path = graph_dir / "00 Graph Generation" / "graph_feature_static_metrics.csv"
    graph_json_path = graph_dir / "00 Graph Generation" / "graph.json"
    
    # Fall back to flat structure
    if not grouping_path.exists():
        grouping_path = graph_dir / "node_grouping.csv"
    if not metrics_path.exists():
        metrics_path = graph_dir / "graph_feature_static_metrics.csv"
    if not graph_json_path.exists():
        graph_json_path = graph_dir / "graph.json"
    
    if not grouping_path.exists():
        raise FileNotFoundError(f"Node grouping not found: {grouping_path}")
    if not metrics_path.exists():
        raise FileNotFoundError(f"Feature metrics not found: {metrics_path}")
    
    # Load prompt and activations from graph.json
    prompt = None
    activations_map: Dict[Tuple[int, int, int], float] = {}
    
    if graph_json_path.exists():
        with open(graph_json_path, "r", encoding="utf-8") as f:
            graph_data = json.load(f)
        
        # Extract prompt
        prompt = graph_data.get("metadata", {}).get("prompt")
        if prompt and verbose:
            print(f"  [PROMPT] Loaded from graph.json: {prompt[:60]}...")
        
        # Extract activations from nodes by parsing node_id
        # node_id format: "{layer}_{feature}_{position}" e.g., "0_1861_7"
        nodes = graph_data.get("nodes", [])
        for node in nodes:
            node_id = node.get("node_id", "")
            activation = node.get("activation")
            if node_id and activation is not None:
                parts = node_id.split("_")
                if len(parts) >= 3:
                    try:
                        layer = int(parts[0])
                        feature = int(parts[1])
                        position = int(parts[2])
                        activations_map[(layer, feature, position)] = float(activation)
                    except (ValueError, IndexError):
                        pass  # Skip malformed node_ids
        
        if activations_map and verbose:
            print(f"  [ACTIVATIONS] Loaded {len(activations_map)} stored activations from graph.json")
    
    return {
        "grouping": pd.read_csv(grouping_path),
        "metrics": pd.read_csv(metrics_path),
        "prompt": prompt,
        "activations_map": activations_map,
        "graph_dir": graph_dir,
    }


def validate_graph_inputs(graph_dir: Path) -> list[str]:
    """
    Validate that required graph files exist.
    
    Args:
        graph_dir: Path to the graph directory
    
    Returns:
        List of error messages (empty if all files exist)
    """
    graph_dir = Path(graph_dir)
    errors = []
    
    # Check for batch pipeline structure
    required_files = [
        ("02 Node Grouping/node_grouping.csv", "node_grouping.csv"),
        ("00 Graph Generation/graph_feature_static_metrics.csv", "graph_feature_static_metrics.csv"),
        ("00 Graph Generation/graph.json", "graph.json"),
    ]
    
    for batch_path, flat_path in required_files:
        batch_full = graph_dir / batch_path
        flat_full = graph_dir / flat_path
        if not batch_full.exists() and not flat_full.exists():
            errors.append(f"Missing: {batch_path} or {flat_path} in {graph_dir}")
    
    return errors

