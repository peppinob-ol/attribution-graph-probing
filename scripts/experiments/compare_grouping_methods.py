"""
Compare concept-aligned grouping vs geometric baselines.

STATUS: EXPLORATORY ONLY. NOT the paper's geometric baseline.

This script is an early exploration of intrinsic clustering metrics
(silhouette, Davies-Bouldin, cosine coherence) over cosine-similarity
and layer+influence adjacency clusterings. It must NOT be cited as
evidence for claim C1, for the following reasons:

- It uses silhouette-selected cluster counts, which the paper's
  baseline design explicitly rejects (see docs/baseline_design.md,
  Choice 3 -- the baseline must instead use K_CPAS(graph)).
- It includes a "layer + influence" adjacency baseline, which violates
  the cross-layer design choice (see docs/baseline_design.md, Choice
  2).
- It reports only intrinsic clustering metrics; it does NOT run the
  swap-intervention harness, so its outputs are not causal evidence
  for or against CPAS.
- It has no blacklist-compatible naming step, so its clusters cannot
  be fed into the existing concept-matched intervention pipeline.

The actual paper baseline is specified in docs/baseline_design.md and
will be implemented as a separate InterventionBuilder that shares the
batch pipeline's swap harness. Do not rewire this script into that
pipeline; write the new baseline fresh, per the design note.

Metrics computed:
- Coherence: activation pattern similarity, peak token consistency, influence variance
- Stability: silhouette score, Davies-Bouldin index, group size distribution
- Interpretability: semantic alignment scores
- Neuronpedia scores: completeness, replacement (optional, if --upload_to_neuronpedia)

Usage:
    python scripts/experiments/compare_grouping_methods.py --input_csv <path> --output_json <path>

    # With Neuronpedia upload for comparison:
    python scripts/experiments/compare_grouping_methods.py \
        --input_csv path/to/node_grouping_final.csv \
        --graph_json path/to/graph.json \
        --api_key YOUR_API_KEY \
        --upload_to_neuronpedia \
        --upload_concept_aligned \
        --upload_cosine \
        --upload_layer_adjacency
"""

import argparse
import json
import warnings
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from collections import defaultdict

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score, davies_bouldin_score
from sklearn.metrics.pairwise import cosine_similarity
from scipy.spatial.distance import pdist, squareform
from scipy.stats import entropy

# Import upload function from node_grouping script
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))
try:
    from scripts.node_grouping import upload_subgraph_to_neuronpedia
except ImportError:
    # Fallback: try loading as module
    import importlib.util
    script_path = parent_dir / "02_node_grouping.py"
    if script_path.exists():
        spec = importlib.util.spec_from_file_location("node_grouping", script_path)
        node_grouping_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(node_grouping_module)
        upload_subgraph_to_neuronpedia = node_grouping_module.upload_subgraph_to_neuronpedia
    else:
        upload_subgraph_to_neuronpedia = None


def parse_top_activations(act_str: str) -> List[Dict[str, Any]]:
    """Parse the top_activations_probe_original JSON string."""
    if pd.isna(act_str) or not act_str or act_str == "[]":
        return []
    try:
        return json.loads(act_str)
    except:
        return []


def get_activation_vector(act_list: List[Dict[str, Any]], all_tokens: List[str]) -> np.ndarray:
    """Convert activation list to a fixed-size vector based on all_tokens."""
    vec = np.zeros(len(all_tokens))
    token_to_idx = {token: i for i, token in enumerate(all_tokens)}
    
    for item in act_list:
        token = item.get("tk", "")
        act_val = item.get("act", 0.0)
        if token in token_to_idx:
            vec[token_to_idx[token]] = act_val
    
    return vec


def compute_activation_features(df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
    """
    Extract activation-based feature vectors for each feature.
    Returns: (feature_matrix, all_tokens)
    """
    all_tokens_set = set()
    
    # Collect all unique tokens
    for act_str in df["top_activations_probe_original"]:
        act_list = parse_top_activations(act_str)
        for item in act_list:
            all_tokens_set.add(item.get("tk", ""))
    
    all_tokens = sorted(list(all_tokens_set))
    
    # Build feature matrix
    feature_matrix = []
    for act_str in df["top_activations_probe_original"]:
        act_list = parse_top_activations(act_str)
        vec = get_activation_vector(act_list, all_tokens)
        feature_matrix.append(vec)
    
    return np.array(feature_matrix), all_tokens


def compute_layer_adjacency_features(df: pd.DataFrame) -> np.ndarray:
    """
    Build feature vectors based on layer and adjacency.
    Returns: feature_matrix (n_features x 2) with [layer, normalized_influence]
    """
    layers = df["layer"].values.astype(float)
    influences = df["node_influence"].values.astype(float)
    
    # Normalize
    layers_norm = (layers - layers.min()) / (layers.max() - layers.min() + 1e-10)
    influences_norm = (influences - influences.min()) / (influences.max() - influences.min() + 1e-10)
    
    return np.column_stack([layers_norm, influences_norm])


def cluster_by_cosine_similarity(feature_matrix: np.ndarray, n_clusters: int) -> np.ndarray:
    """
    Cluster features using cosine similarity and agglomerative clustering.
    """
    if feature_matrix.shape[0] < n_clusters:
        n_clusters = max(1, feature_matrix.shape[0] // 2)
    
    # Compute cosine similarity
    similarity_matrix = cosine_similarity(feature_matrix)
    
    # Convert to distance (1 - similarity)
    distance_matrix = 1 - similarity_matrix
    
    clustering = AgglomerativeClustering(
        n_clusters=n_clusters,
        metric='precomputed',
        linkage='average'
    )
    
    return clustering.fit_predict(distance_matrix)


def cluster_by_layer_adjacency(feature_matrix: np.ndarray, n_clusters: int) -> np.ndarray:
    """
    Cluster features based on layer and influence (adjacency-based).
    """
    if feature_matrix.shape[0] < n_clusters:
        n_clusters = max(1, feature_matrix.shape[0] // 2)
    
    clustering = AgglomerativeClustering(
        n_clusters=n_clusters,
        linkage='ward'
    )
    
    return clustering.fit_predict(feature_matrix)


def compute_coherence_metrics(df: pd.DataFrame, cluster_labels: np.ndarray) -> Dict[str, float]:
    """
    Compute coherence metrics for a given clustering.
    
    Metrics:
    - peak_token_consistency: fraction of features in each cluster with same peak token
    - activation_similarity: average cosine similarity within clusters
    - influence_variance: average normalized variance of influence within clusters
    - sparsity_consistency: average std of sparsity_ratio within clusters
    """
    metrics = {}
    
    # Peak token consistency
    peak_token_scores = []
    for cluster_id in np.unique(cluster_labels):
        cluster_mask = cluster_labels == cluster_id
        cluster_df = df[cluster_mask]
        
        if len(cluster_df) <= 1:
            continue
        
        # Most common peak token
        peak_tokens = cluster_df["peak_token"].value_counts()
        if len(peak_tokens) > 0:
            consistency = peak_tokens.iloc[0] / len(cluster_df)
            peak_token_scores.append(consistency)
    
    metrics["peak_token_consistency"] = float(np.mean(peak_token_scores)) if peak_token_scores else 0.0
    
    # Activation similarity within clusters
    feature_matrix, _ = compute_activation_features(df)
    if feature_matrix.shape[0] > 0 and feature_matrix.shape[1] > 0:
        activation_similarities = []
        
        for cluster_id in np.unique(cluster_labels):
            cluster_mask = cluster_labels == cluster_id
            cluster_features = feature_matrix[cluster_mask]
            
            if len(cluster_features) <= 1:
                continue
            
            # Pairwise cosine similarity
            sim_matrix = cosine_similarity(cluster_features)
            # Average excluding diagonal
            mask = np.ones_like(sim_matrix, dtype=bool)
            np.fill_diagonal(mask, False)
            avg_sim = sim_matrix[mask].mean()
            activation_similarities.append(avg_sim)
        
        metrics["activation_similarity"] = float(np.mean(activation_similarities)) if activation_similarities else 0.0
    else:
        metrics["activation_similarity"] = 0.0
    
    # Influence variance (lower is better)
    influence_variances = []
    for cluster_id in np.unique(cluster_labels):
        cluster_mask = cluster_labels == cluster_id
        cluster_df = df[cluster_mask]
        
        if len(cluster_df) <= 1:
            continue
        
        influences = cluster_df["node_influence"].values
        # Normalized std
        if influences.mean() > 0:
            norm_var = influences.std() / influences.mean()
            influence_variances.append(norm_var)
    
    metrics["influence_variance_avg"] = float(np.mean(influence_variances)) if influence_variances else 0.0
    
    # Sparsity consistency
    sparsity_stds = []
    for cluster_id in np.unique(cluster_labels):
        cluster_mask = cluster_labels == cluster_id
        cluster_df = df[cluster_mask]
        
        if len(cluster_df) <= 1:
            continue
        
        sparsities = cluster_df["sparsity_ratio"].values
        sparsity_stds.append(sparsities.std())
    
    metrics["sparsity_consistency_avg"] = float(np.mean(sparsity_stds)) if sparsity_stds else 0.0
    
    return metrics


def compute_stability_metrics(feature_matrix: np.ndarray, cluster_labels: np.ndarray) -> Dict[str, float]:
    """
    Compute stability metrics for a given clustering.
    
    Metrics:
    - silhouette_score: measures how similar an object is to its own cluster vs other clusters
    - davies_bouldin_score: ratio of within-cluster to between-cluster distances (lower is better)
    - cluster_size_entropy: entropy of cluster size distribution (higher = more balanced)
    """
    metrics = {}
    
    n_samples = len(cluster_labels)
    n_clusters = len(np.unique(cluster_labels))
    
    if n_samples < 2 or n_clusters < 2:
        metrics["silhouette_score"] = 0.0
        metrics["davies_bouldin_score"] = 0.0
        metrics["cluster_size_entropy"] = 0.0
        metrics["n_clusters"] = n_clusters
        return metrics
    
    # Silhouette score
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            sil_score = silhouette_score(feature_matrix, cluster_labels)
            metrics["silhouette_score"] = float(sil_score)
    except:
        metrics["silhouette_score"] = 0.0
    
    # Davies-Bouldin score
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            db_score = davies_bouldin_score(feature_matrix, cluster_labels)
            metrics["davies_bouldin_score"] = float(db_score)
    except:
        metrics["davies_bouldin_score"] = 0.0
    
    # Cluster size entropy
    unique, counts = np.unique(cluster_labels, return_counts=True)
    probs = counts / counts.sum()
    cluster_entropy = entropy(probs)
    metrics["cluster_size_entropy"] = float(cluster_entropy)
    metrics["n_clusters"] = n_clusters
    
    return metrics


def compute_interpretability_metrics(df: pd.DataFrame, cluster_labels: np.ndarray) -> Dict[str, float]:
    """
    Compute interpretability metrics.
    
    Metrics:
    - avg_cluster_size: average number of features per cluster
    - max_cluster_size: largest cluster size
    - min_cluster_size: smallest cluster size
    - singleton_ratio: fraction of clusters with only 1 feature
    """
    metrics = {}
    
    unique, counts = np.unique(cluster_labels, return_counts=True)
    
    metrics["avg_cluster_size"] = float(counts.mean())
    metrics["max_cluster_size"] = int(counts.max())
    metrics["min_cluster_size"] = int(counts.min())
    
    singleton_count = (counts == 1).sum()
    metrics["singleton_ratio"] = float(singleton_count / len(counts))
    
    return metrics


def evaluate_concept_aligned_grouping(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Evaluate the concept-aligned grouping (current approach using supernode_name).
    """
    # Use supernode_name as cluster labels
    supernode_names = df["supernode_name"].fillna("UNKNOWN")
    unique_names = supernode_names.unique()
    name_to_id = {name: i for i, name in enumerate(unique_names)}
    cluster_labels = np.array([name_to_id[name] for name in supernode_names])
    
    # Compute features for stability metrics
    feature_matrix_act, _ = compute_activation_features(df)
    
    # Compute all metrics
    coherence = compute_coherence_metrics(df, cluster_labels)
    stability = compute_stability_metrics(feature_matrix_act, cluster_labels)
    interpretability = compute_interpretability_metrics(df, cluster_labels)
    
    return {
        "method": "concept_aligned",
        "coherence": coherence,
        "stability": stability,
        "interpretability": interpretability,
    }


def evaluate_cosine_similarity_baseline(df: pd.DataFrame, n_clusters: int) -> Dict[str, Any]:
    """
    Evaluate cosine similarity clustering baseline.
    """
    feature_matrix, _ = compute_activation_features(df)
    
    if feature_matrix.shape[0] < 2:
        return {
            "method": "cosine_similarity",
            "error": "Not enough features",
        }
    
    cluster_labels = cluster_by_cosine_similarity(feature_matrix, n_clusters)
    
    coherence = compute_coherence_metrics(df, cluster_labels)
    stability = compute_stability_metrics(feature_matrix, cluster_labels)
    interpretability = compute_interpretability_metrics(df, cluster_labels)
    
    return {
        "method": "cosine_similarity",
        "coherence": coherence,
        "stability": stability,
        "interpretability": interpretability,
    }


def evaluate_layer_adjacency_baseline(df: pd.DataFrame, n_clusters: int) -> Dict[str, Any]:
    """
    Evaluate layer+adjacency clustering baseline.
    """
    feature_matrix = compute_layer_adjacency_features(df)
    
    if feature_matrix.shape[0] < 2:
        return {
            "method": "layer_adjacency",
            "error": "Not enough features",
        }
    
    cluster_labels = cluster_by_layer_adjacency(feature_matrix, n_clusters)
    
    coherence = compute_coherence_metrics(df, cluster_labels)
    stability = compute_stability_metrics(feature_matrix, cluster_labels)
    interpretability = compute_interpretability_metrics(df, cluster_labels)
    
    return {
        "method": "layer_adjacency",
        "coherence": coherence,
        "stability": stability,
        "interpretability": interpretability,
    }


# ============================================================================
# NEURONPEDIA UPLOAD FUNCTIONS
# ============================================================================

def create_grouped_dataframe(
    df: pd.DataFrame,
    cluster_labels: np.ndarray,
    method_name: str
) -> pd.DataFrame:
    """
    Convert cluster labels to DataFrame format for Neuronpedia upload.
    
    Args:
        df: Original DataFrame with feature_key column
        cluster_labels: numpy array of cluster IDs (one per row)
        method_name: "concept_aligned", "cosine_similarity", or "layer_adjacency"
    
    Returns:
        DataFrame with feature_key and supernode_name columns
    """
    df_copy = df.copy()
    df_copy['cluster_id'] = cluster_labels
    
    # Aggregate by feature_key (take mode of cluster_id for each feature)
    feature_to_cluster = {}
    for feature_key, group in df_copy.groupby('feature_key'):
        # Use mode (most common cluster for this feature)
        cluster_id = group['cluster_id'].mode()[0]
        feature_to_cluster[feature_key] = cluster_id
    
    # Generate supernode names based on method
    if method_name == "concept_aligned":
        # Use existing supernode_name
        df_grouped = df.groupby('feature_key').agg({
            'supernode_name': 'first'
        }).reset_index()
    else:
        # Generate new supernode names for baselines
        prefix = "cosine" if method_name == "cosine_similarity" else "layer"
        
        # Create mapping cluster_id -> supernode_name
        cluster_to_name = {}
        for feature_key, cluster_id in feature_to_cluster.items():
            if cluster_id not in cluster_to_name:
                cluster_to_name[cluster_id] = f"{prefix}_cluster_{cluster_id}"
        
        # Create DataFrame
        df_grouped = pd.DataFrame([
            {
                'feature_key': feature_key,
                'supernode_name': cluster_to_name[cluster_id]
            }
            for feature_key, cluster_id in feature_to_cluster.items()
        ])
    
    return df_grouped


def upload_baseline_to_neuronpedia(
    df: pd.DataFrame,
    cluster_labels: np.ndarray,
    method_name: str,
    graph_json_path: str,
    api_key: str,
    selected_nodes_data: Optional[Dict[str, Any]] = None,
    overwrite_id: Optional[str] = None,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Upload a baseline clustering to Neuronpedia.
    
    Args:
        df: Original DataFrame with feature_key
        cluster_labels: numpy array of cluster IDs
        method_name: "concept_aligned", "cosine_similarity", or "layer_adjacency"
        graph_json_path: Path to graph JSON file
        api_key: Neuronpedia API key
        selected_nodes_data: Optional node subset data
        overwrite_id: Optional ID to overwrite existing subgraph
        verbose: Print progress
    
    Returns:
        Response dict from Neuronpedia API
    """
    if upload_subgraph_to_neuronpedia is None:
        raise RuntimeError("upload_subgraph_to_neuronpedia function not available. Check import.")
    
    # Create grouped DataFrame
    df_grouped = create_grouped_dataframe(df, cluster_labels, method_name)
    
    # Merge with original df to get all required columns
    df_full = df.merge(df_grouped, on='feature_key', how='left', suffixes=('_orig', ''))
    
    # If supernode_name_orig exists, drop it (from merge)
    if 'supernode_name_orig' in df_full.columns:
        df_full = df_full.drop(columns=['supernode_name_orig'])
    
    # Generate display name
    method_display = {
        "concept_aligned": "Concept-Aligned",
        "cosine_similarity": "Cosine Similarity Baseline",
        "layer_adjacency": "Layer Adjacency Baseline"
    }
    display_name = f"{method_display.get(method_name, method_name)} Grouping"
    
    # Upload to Neuronpedia
    try:
        result = upload_subgraph_to_neuronpedia(
            df_grouped=df_full,
            graph_json_path=graph_json_path,
            api_key=api_key,
            display_name=display_name,
            overwrite_id=overwrite_id,
            selected_nodes_data=selected_nodes_data,
            verbose=verbose
        )
        return result
    except Exception as e:
        if verbose:
            print(f"ERROR uploading {method_name} to Neuronpedia: {e}")
        return {"error": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="Compare concept-aligned grouping vs geometric baselines"
    )
    parser.add_argument(
        "--input_csv",
        type=str,
        required=True,
        help="Path to node grouping CSV file"
    )
    parser.add_argument(
        "--output_json",
        type=str,
        default=None,
        help="Path to output JSON file (default: same dir as input with _comparison.json suffix)"
    )
    
    # Neuronpedia upload arguments
    parser.add_argument(
        "--upload_to_neuronpedia",
        action="store_true",
        help="Upload subgraphs to Neuronpedia for comparison"
    )
    parser.add_argument(
        "--graph_json",
        type=str,
        default=None,
        help="Path to graph JSON file (required if --upload_to_neuronpedia)"
    )
    parser.add_argument(
        "--api_key",
        type=str,
        default=None,
        help="Neuronpedia API key (required if --upload_to_neuronpedia)"
    )
    parser.add_argument(
        "--selected_nodes_json",
        type=str,
        default=None,
        help="Path to selected nodes JSON file (optional)"
    )
    parser.add_argument(
        "--upload_concept_aligned",
        action="store_true",
        help="Upload concept-aligned grouping to Neuronpedia"
    )
    parser.add_argument(
        "--upload_cosine",
        action="store_true",
        help="Upload cosine similarity baseline to Neuronpedia"
    )
    parser.add_argument(
        "--upload_layer_adjacency",
        action="store_true",
        help="Upload layer adjacency baseline to Neuronpedia"
    )
    
    args = parser.parse_args()
    
    input_path = Path(args.input_csv)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    if args.output_json:
        output_path = Path(args.output_json)
    else:
        output_path = input_path.parent / f"{input_path.stem}_comparison.json"
    
    # Validate Neuronpedia upload arguments
    if args.upload_to_neuronpedia:
        if not args.graph_json:
            raise ValueError("--graph_json is required when --upload_to_neuronpedia is set")
        if not args.api_key:
            raise ValueError("--api_key is required when --upload_to_neuronpedia is set")
        if not Path(args.graph_json).exists():
            raise FileNotFoundError(f"Graph JSON not found: {args.graph_json}")
        
        # If no specific upload flags set, upload all
        if not (args.upload_concept_aligned or args.upload_cosine or args.upload_layer_adjacency):
            args.upload_concept_aligned = True
            args.upload_cosine = True
            args.upload_layer_adjacency = True
            print("No specific upload flags set, uploading all methods")
    
    # Load selected nodes data if provided
    selected_nodes_data = None
    if args.selected_nodes_json:
        selected_nodes_path = Path(args.selected_nodes_json)
        if selected_nodes_path.exists():
            with open(selected_nodes_path, 'r', encoding='utf-8') as f:
                selected_nodes_data = json.load(f)
            print(f"Loaded selected nodes data: {selected_nodes_path}")
        else:
            print(f"WARNING: Selected nodes JSON not found: {selected_nodes_path}")
    
    print(f"Loading data from {input_path}...")
    df = pd.read_csv(input_path)
    
    print(f"Loaded {len(df)} features")
    print(f"Unique supernodes: {df['supernode_name'].nunique()}")
    
    # Determine n_clusters for baselines (use same as concept-aligned)
    n_clusters = df["supernode_name"].nunique()
    
    # Store cluster labels for Neuronpedia upload
    cluster_labels_dict = {}
    
    print("\n" + "="*80)
    print("EVALUATING CONCEPT-ALIGNED GROUPING")
    print("="*80)
    results_concept = evaluate_concept_aligned_grouping(df)
    print_results(results_concept)
    
    # Store concept-aligned cluster labels
    supernode_names = df["supernode_name"].fillna("UNKNOWN")
    unique_names = supernode_names.unique()
    name_to_id = {name: i for i, name in enumerate(unique_names)}
    cluster_labels_dict["concept_aligned"] = np.array([name_to_id[name] for name in supernode_names])
    
    print("\n" + "="*80)
    print("EVALUATING COSINE SIMILARITY BASELINE")
    print("="*80)
    results_cosine = evaluate_cosine_similarity_baseline(df, n_clusters)
    print_results(results_cosine)
    
    # Store cosine cluster labels
    if "error" not in results_cosine:
        feature_matrix, _ = compute_activation_features(df)
        cluster_labels_dict["cosine_similarity"] = cluster_by_cosine_similarity(feature_matrix, n_clusters)
    
    print("\n" + "="*80)
    print("EVALUATING LAYER ADJACENCY BASELINE")
    print("="*80)
    results_adjacency = evaluate_layer_adjacency_baseline(df, n_clusters)
    print_results(results_adjacency)
    
    # Store layer adjacency cluster labels
    if "error" not in results_adjacency:
        feature_matrix = compute_layer_adjacency_features(df)
        cluster_labels_dict["layer_adjacency"] = cluster_by_layer_adjacency(feature_matrix, n_clusters)
    
    # Upload to Neuronpedia if requested
    if args.upload_to_neuronpedia:
        print("\n" + "="*80)
        print("UPLOADING TO NEURONPEDIA")
        print("="*80)
        
        upload_results = {}
        
        # Upload concept-aligned
        if args.upload_concept_aligned and "concept_aligned" in cluster_labels_dict:
            print("\nUploading Concept-Aligned grouping...")
            try:
                result = upload_baseline_to_neuronpedia(
                    df=df,
                    cluster_labels=cluster_labels_dict["concept_aligned"],
                    method_name="concept_aligned",
                    graph_json_path=args.graph_json,
                    api_key=args.api_key,
                    selected_nodes_data=selected_nodes_data,
                    verbose=True
                )
                upload_results["concept_aligned"] = result
                if "error" not in result:
                    results_concept["neuronpedia_upload"] = result
                    print("  Concept-Aligned upload successful")
            except Exception as e:
                print(f"  ERROR: {e}")
                upload_results["concept_aligned"] = {"error": str(e)}
        
        # Upload cosine similarity
        if args.upload_cosine and "cosine_similarity" in cluster_labels_dict:
            print("\nUploading Cosine Similarity baseline...")
            try:
                result = upload_baseline_to_neuronpedia(
                    df=df,
                    cluster_labels=cluster_labels_dict["cosine_similarity"],
                    method_name="cosine_similarity",
                    graph_json_path=args.graph_json,
                    api_key=args.api_key,
                    selected_nodes_data=selected_nodes_data,
                    verbose=True
                )
                upload_results["cosine_similarity"] = result
                if "error" not in result:
                    results_cosine["neuronpedia_upload"] = result
                    print("  Cosine Similarity upload successful")
            except Exception as e:
                print(f"  ERROR: {e}")
                upload_results["cosine_similarity"] = {"error": str(e)}
        
        # Upload layer adjacency
        if args.upload_layer_adjacency and "layer_adjacency" in cluster_labels_dict:
            print("\nUploading Layer Adjacency baseline...")
            try:
                result = upload_baseline_to_neuronpedia(
                    df=df,
                    cluster_labels=cluster_labels_dict["layer_adjacency"],
                    method_name="layer_adjacency",
                    graph_json_path=args.graph_json,
                    api_key=args.api_key,
                    selected_nodes_data=selected_nodes_data,
                    verbose=True
                )
                upload_results["layer_adjacency"] = result
                if "error" not in result:
                    results_adjacency["neuronpedia_upload"] = result
                    print("  Layer Adjacency upload successful")
            except Exception as e:
                print(f"  ERROR: {e}")
                upload_results["layer_adjacency"] = {"error": str(e)}
        
        print("\n" + "="*80)
        print("NEURONPEDIA UPLOAD SUMMARY")
        print("="*80)
        for method, result in upload_results.items():
            if "error" in result:
                print(f"  {method}: FAILED - {result['error']}")
            else:
                print(f"  {method}: SUCCESS")
        
        print("\nNote: Retrieve completeness/replacement scores from Neuronpedia UI")
    
    # Compile all results
    all_results = {
        "input_file": str(input_path),
        "n_features": len(df),
        "n_supernodes_concept": n_clusters,
        "upload_to_neuronpedia": args.upload_to_neuronpedia,
        "results": {
            "concept_aligned": results_concept,
            "cosine_similarity": results_cosine,
            "layer_adjacency": results_adjacency,
        },
        "comparison": generate_comparison_summary(results_concept, results_cosine, results_adjacency)
    }
    
    # Save results
    print(f"\nSaving results to {output_path}...")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    
    print("\n" + "="*80)
    print("COMPARISON SUMMARY")
    print("="*80)
    print_comparison_summary(all_results["comparison"])
    
    print(f"\nDone! Results saved to {output_path}")


def print_results(results: Dict[str, Any]):
    """Print evaluation results."""
    method = results.get("method", "unknown")
    
    if "error" in results:
        print(f"  ERROR: {results['error']}")
        return
    
    print(f"\nMethod: {method}")
    
    if "coherence" in results:
        print("\n  Coherence Metrics:")
        for key, val in results["coherence"].items():
            print(f"    {key}: {val:.4f}")
    
    if "stability" in results:
        print("\n  Stability Metrics:")
        for key, val in results["stability"].items():
            if isinstance(val, float):
                print(f"    {key}: {val:.4f}")
            else:
                print(f"    {key}: {val}")
    
    if "interpretability" in results:
        print("\n  Interpretability Metrics:")
        for key, val in results["interpretability"].items():
            if isinstance(val, float):
                print(f"    {key}: {val:.4f}")
            else:
                print(f"    {key}: {val}")


def generate_comparison_summary(
    concept_results: Dict,
    cosine_results: Dict,
    adjacency_results: Dict
) -> Dict[str, Any]:
    """Generate comparison summary showing which method is better."""
    summary = {}
    
    # Coherence comparison (higher is better except for influence_variance)
    coherence_concept = concept_results.get("coherence", {})
    coherence_cosine = cosine_results.get("coherence", {})
    coherence_adjacency = adjacency_results.get("coherence", {})
    
    summary["coherence"] = {}
    
    for metric in ["peak_token_consistency", "activation_similarity"]:
        concept_val = coherence_concept.get(metric, 0.0)
        cosine_val = coherence_cosine.get(metric, 0.0)
        adjacency_val = coherence_adjacency.get(metric, 0.0)
        
        best_method = "concept_aligned"
        if cosine_val > concept_val:
            best_method = "cosine_similarity"
        if adjacency_val > max(concept_val, cosine_val):
            best_method = "layer_adjacency"
        
        summary["coherence"][metric] = {
            "concept_aligned": concept_val,
            "cosine_similarity": cosine_val,
            "layer_adjacency": adjacency_val,
            "best": best_method,
            "improvement_vs_cosine": (concept_val - cosine_val) / (cosine_val + 1e-10) * 100,
            "improvement_vs_adjacency": (concept_val - adjacency_val) / (adjacency_val + 1e-10) * 100,
        }
    
    # For influence_variance and sparsity_consistency, lower is better
    for metric in ["influence_variance_avg", "sparsity_consistency_avg"]:
        concept_val = coherence_concept.get(metric, 0.0)
        cosine_val = coherence_cosine.get(metric, 0.0)
        adjacency_val = coherence_adjacency.get(metric, 0.0)
        
        best_method = "concept_aligned"
        if cosine_val < concept_val:
            best_method = "cosine_similarity"
        if adjacency_val < min(concept_val, cosine_val):
            best_method = "layer_adjacency"
        
        summary["coherence"][metric] = {
            "concept_aligned": concept_val,
            "cosine_similarity": cosine_val,
            "layer_adjacency": adjacency_val,
            "best": best_method,
            "improvement_vs_cosine": (cosine_val - concept_val) / (cosine_val + 1e-10) * 100,
            "improvement_vs_adjacency": (adjacency_val - concept_val) / (adjacency_val + 1e-10) * 100,
        }
    
    # Stability comparison (silhouette higher is better, davies_bouldin lower is better)
    stability_concept = concept_results.get("stability", {})
    stability_cosine = cosine_results.get("stability", {})
    stability_adjacency = adjacency_results.get("stability", {})
    
    summary["stability"] = {}
    
    # Silhouette (higher is better)
    metric = "silhouette_score"
    concept_val = stability_concept.get(metric, 0.0)
    cosine_val = stability_cosine.get(metric, 0.0)
    adjacency_val = stability_adjacency.get(metric, 0.0)
    
    best_method = "concept_aligned"
    if cosine_val > concept_val:
        best_method = "cosine_similarity"
    if adjacency_val > max(concept_val, cosine_val):
        best_method = "layer_adjacency"
    
    summary["stability"][metric] = {
        "concept_aligned": concept_val,
        "cosine_similarity": cosine_val,
        "layer_adjacency": adjacency_val,
        "best": best_method,
        "improvement_vs_cosine": (concept_val - cosine_val) / (abs(cosine_val) + 1e-10) * 100,
        "improvement_vs_adjacency": (concept_val - adjacency_val) / (abs(adjacency_val) + 1e-10) * 100,
    }
    
    # Davies-Bouldin (lower is better)
    metric = "davies_bouldin_score"
    concept_val = stability_concept.get(metric, 0.0)
    cosine_val = stability_cosine.get(metric, 0.0)
    adjacency_val = stability_adjacency.get(metric, 0.0)
    
    best_method = "concept_aligned"
    if cosine_val < concept_val and cosine_val > 0:
        best_method = "cosine_similarity"
    if adjacency_val < min(concept_val, cosine_val) and adjacency_val > 0:
        best_method = "layer_adjacency"
    
    summary["stability"][metric] = {
        "concept_aligned": concept_val,
        "cosine_similarity": cosine_val,
        "layer_adjacency": adjacency_val,
        "best": best_method,
        "improvement_vs_cosine": (cosine_val - concept_val) / (cosine_val + 1e-10) * 100,
        "improvement_vs_adjacency": (adjacency_val - concept_val) / (adjacency_val + 1e-10) * 100,
    }
    
    return summary


def print_comparison_summary(summary: Dict[str, Any]):
    """Print a readable comparison summary."""
    print("\nCoherence Metrics:")
    print("-" * 80)
    for metric, data in summary.get("coherence", {}).items():
        print(f"\n{metric}:")
        print(f"  Concept-Aligned: {data['concept_aligned']:.4f}")
        print(f"  Cosine Similarity: {data['cosine_similarity']:.4f}")
        print(f"  Layer Adjacency: {data['layer_adjacency']:.4f}")
        print(f"  Best: {data['best']}")
        print(f"  Improvement vs Cosine: {data['improvement_vs_cosine']:.2f}%")
        print(f"  Improvement vs Adjacency: {data['improvement_vs_adjacency']:.2f}%")
    
    print("\n\nStability Metrics:")
    print("-" * 80)
    for metric, data in summary.get("stability", {}).items():
        print(f"\n{metric}:")
        print(f"  Concept-Aligned: {data['concept_aligned']:.4f}")
        print(f"  Cosine Similarity: {data['cosine_similarity']:.4f}")
        print(f"  Layer Adjacency: {data['layer_adjacency']:.4f}")
        print(f"  Best: {data['best']}")
        print(f"  Improvement vs Cosine: {data['improvement_vs_cosine']:.2f}%")
        print(f"  Improvement vs Adjacency: {data['improvement_vs_adjacency']:.2f}%")


if __name__ == "__main__":
    main()


