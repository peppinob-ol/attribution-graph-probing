# Neuronpedia Baseline Comparison

This document describes how to use the enhanced `compare_grouping_methods.py` script to upload geometric baseline clustering results to Neuronpedia and compare them against the concept-aligned grouping.

## Overview

The script now supports uploading all three grouping methods to Neuronpedia as separate subgraphs:

1. **Concept-Aligned Grouping** - Your behavior-driven supernode classification
2. **Cosine Similarity Baseline** - Clustering based on activation pattern similarity
3. **Layer Adjacency Baseline** - Clustering based on layer position and influence

After uploading, you can retrieve **completeness** and **replacement** scores from Neuronpedia to quantitatively compare the methods.

## Requirements

- Node grouping CSV file (output from Step 3: Node Naming)
- Graph JSON file (from Step 1: Graph Generation)
- Selected Nodes JSON file (optional, from Step 1)
- Neuronpedia API key

## Usage

### Basic Comparison (No Upload)

Run the script without upload to compute local metrics only:

```bash
python scripts/experiments/compare_grouping_methods.py \
    --input_csv output/node_grouping_final_20241106_123456.csv \
    --output_json output/comparison_results.json
```

This computes:
- Coherence metrics (peak token consistency, activation similarity)
- Stability metrics (silhouette score, Davies-Bouldin index)
- Interpretability metrics (cluster size distribution)

### With Neuronpedia Upload

Upload all three methods to Neuronpedia for score comparison:

```bash
python scripts/experiments/compare_grouping_methods.py \
    --input_csv output/node_grouping_final_20241106_123456.csv \
    --graph_json output/st1_graph_20241106_123456.json \
    --selected_nodes_json output/st1_feat_node_subset_20241106_123456.json \
    --api_key YOUR_NEURONPEDIA_API_KEY \
    --upload_to_neuronpedia \
    --output_json output/comparison_with_neuronpedia.json
```

**Note**: If `--upload_to_neuronpedia` is set without specific upload flags, all three methods will be uploaded by default.

### Upload Specific Methods

Upload only selected methods:

```bash
python scripts/experiments/compare_grouping_methods.py \
    --input_csv output/node_grouping_final.csv \
    --graph_json output/st1_graph.json \
    --api_key YOUR_API_KEY \
    --upload_to_neuronpedia \
    --upload_concept_aligned \
    --upload_cosine
```

Available flags:
- `--upload_concept_aligned` - Upload concept-aligned grouping
- `--upload_cosine` - Upload cosine similarity baseline
- `--upload_layer_adjacency` - Upload layer adjacency baseline

## Output

### JSON Results

The script generates a JSON file with:

```json
{
  "input_file": "path/to/input.csv",
  "n_features": 150,
  "n_supernodes_concept": 25,
  "upload_to_neuronpedia": true,
  "results": {
    "concept_aligned": {
      "method": "concept_aligned",
      "coherence": {...},
      "stability": {...},
      "interpretability": {...},
      "neuronpedia_upload": {
        "success": true,
        "subgraph_id": "abc123"
      }
    },
    "cosine_similarity": {
      "method": "cosine_similarity",
      "coherence": {...},
      "stability": {...},
      "interpretability": {...},
      "neuronpedia_upload": {
        "success": true,
        "subgraph_id": "def456"
      }
    },
    "layer_adjacency": {
      "method": "layer_adjacency",
      "coherence": {...},
      "stability": {...},
      "interpretability": {...},
      "neuronpedia_upload": {
        "success": true,
        "subgraph_id": "ghi789"
      }
    }
  },
  "comparison": {
    "coherence": {...},
    "stability": {...}
  }
}
```

### Neuronpedia Subgraphs

Each method is uploaded as a separate subgraph with distinct naming:

- **Concept-Aligned Grouping**: Uses your original supernode names (e.g., "Texas", "Say (Austin)", "(city) related")
- **Cosine Similarity Baseline**: Uses generated names (e.g., "cosine_cluster_0", "cosine_cluster_1", ...)
- **Layer Adjacency Baseline**: Uses generated names (e.g., "layer_cluster_0", "layer_cluster_1", ...)

## Retrieving Neuronpedia Scores

After uploading, retrieve completeness and replacement scores from Neuronpedia:

1. Open each subgraph in the Neuronpedia UI
2. Navigate to the subgraph evaluation panel
3. Note the **completeness** and **replacement** scores
4. Compare across all three methods

### Expected Metrics

**Completeness**: Measures how well the subgraph explains the model's behavior
- Higher is better
- Concept-aligned grouping should have higher completeness if it captures meaningful behaviors

**Replacement**: Measures how well the supernode groups can be replaced without changing behavior
- Higher is better
- Good groupings should have high replacement scores

## Interpretation

### Coherence Metrics

- **Peak Token Consistency**: How often features in the same cluster activate on similar tokens
  - **Concept-aligned** should be highest (features grouped by semantic meaning)
  - **Cosine similarity** moderate (features with similar activation patterns)
  - **Layer adjacency** lowest (features grouped by position)

- **Activation Similarity**: Average cosine similarity within clusters
  - **Cosine similarity** should be highest (optimized for this metric)
  - **Concept-aligned** moderate to high
  - **Layer adjacency** potentially lower

### Stability Metrics

- **Silhouette Score**: Measures cluster separation (-1 to 1, higher is better)
- **Davies-Bouldin Score**: Ratio of within/between cluster distances (lower is better)

### Neuronpedia Scores

- **Completeness**: Behavior explanation quality
- **Replacement**: Functional coherence of groups

**Expected Result**: Concept-aligned grouping should achieve higher Neuronpedia scores despite potentially lower geometric metrics, demonstrating that semantic coherence trumps pure geometric similarity.

## Workflow Example

### Step 1: Run Node Grouping

```bash
# From Streamlit app or CLI
python scripts/02_node_grouping.py \
    --input output/probe_metrics.csv \
    --json output/activations.json \
    --graph output/st1_graph.json \
    --output output/node_grouping_final.csv
```

### Step 2: Compare Methods with Upload

```bash
python scripts/experiments/compare_grouping_methods.py \
    --input_csv output/node_grouping_final.csv \
    --graph_json output/st1_graph.json \
    --selected_nodes_json output/st1_feat_node_subset.json \
    --api_key $NEURONPEDIA_API_KEY \
    --upload_to_neuronpedia \
    --output_json output/comparison_neuronpedia.json
```

### Step 3: Collect Neuronpedia Scores

1. Open Neuronpedia and navigate to your uploaded subgraphs
2. Record completeness and replacement scores for each method
3. Add to comparison JSON manually or via API

### Step 4: Analyze Results

Compare metrics across methods:

```python
import json
import pandas as pd

with open('output/comparison_neuronpedia.json') as f:
    results = json.load(f)

# Create comparison table
comparison_data = []
for method in ['concept_aligned', 'cosine_similarity', 'layer_adjacency']:
    result = results['results'][method]
    comparison_data.append({
        'Method': method,
        'Peak Token Consistency': result['coherence']['peak_token_consistency'],
        'Activation Similarity': result['coherence']['activation_similarity'],
        'Silhouette Score': result['stability']['silhouette_score'],
        'Davies-Bouldin Score': result['stability']['davies_bouldin_score'],
        # Add Neuronpedia scores manually after retrieval
        'Completeness': None,  # Fill from Neuronpedia
        'Replacement': None    # Fill from Neuronpedia
    })

df = pd.DataFrame(comparison_data)
print(df.to_markdown())
```

## Troubleshooting

### Upload Fails

**Error**: `upload_subgraph_to_neuronpedia function not available`

**Solution**: Ensure `scripts/02_node_grouping.py` exists and is accessible

**Error**: `--graph_json is required`

**Solution**: Provide the graph JSON file path with `--graph_json`

**Error**: `Graph JSON not found`

**Solution**: Check the path to your graph JSON file

### Empty Clusters

**Error**: Some baselines produce empty clusters or singleton clusters

**Solution**: This is expected for geometric methods. The comparison metrics account for this.

### Different Number of Clusters

The script automatically uses the same number of clusters (from concept-aligned grouping) for all baseline methods to ensure fair comparison.

## Related Files

- `scripts/experiments/compare_grouping_methods.py` - Main comparison script
- `scripts/02_node_grouping.py` - Node grouping and Neuronpedia upload functions
- `scripts/experiments/visualize_comparison.py` - Visualization of comparison results
- `eda/pages/02_Node_Grouping.py` - Streamlit interface for node grouping

## References

- Neuronpedia API: https://www.neuronpedia.org/api-doc
- Supernode classification logic: `output/STEP3_READY_FOR_REVIEW.md`
- Node grouping tests: `tests/test_node_naming.py`

