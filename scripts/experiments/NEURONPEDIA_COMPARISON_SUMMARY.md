# Neuronpedia Baseline Comparison - Implementation Summary

## Overview

The `compare_grouping_methods.py` script has been enhanced to upload geometric baseline clustering results to Neuronpedia, enabling direct comparison of concept-aligned grouping against cosine similarity and layer adjacency baselines using Neuronpedia's completeness and replacement scores.

## What Was Implemented

### 1. New Functions

**`create_grouped_dataframe(df, cluster_labels, method_name)`**
- Converts cluster labels (numpy arrays) to DataFrame format required by Neuronpedia
- Generates supernode names:
  - `concept_aligned`: Uses existing supernode_name (e.g., "Texas", "Say (Austin)")
  - `cosine_similarity`: Generates "cosine_cluster_0", "cosine_cluster_1", etc.
  - `layer_adjacency`: Generates "layer_cluster_0", "layer_cluster_1", etc.
- Aggregates by feature_key to ensure one supernode per feature

**`upload_baseline_to_neuronpedia(df, cluster_labels, method_name, ...)`**
- Uploads a clustering method to Neuronpedia as a subgraph
- Uses the existing `upload_subgraph_to_neuronpedia` function from `02_node_grouping.py`
- Generates descriptive display names for each method
- Returns Neuronpedia response with upload status

### 2. Enhanced CLI Arguments

New arguments added to `compare_grouping_methods.py`:

```bash
--upload_to_neuronpedia          # Enable Neuronpedia upload
--graph_json PATH                # Path to graph JSON (required for upload)
--api_key KEY                    # Neuronpedia API key (required for upload)
--selected_nodes_json PATH       # Optional: selected nodes for accurate pinnedIds
--upload_concept_aligned         # Upload concept-aligned grouping
--upload_cosine                  # Upload cosine similarity baseline
--upload_layer_adjacency         # Upload layer adjacency baseline
```

### 3. Modified Main Function

The main function now:
1. Validates upload arguments (graph JSON, API key)
2. Loads selected nodes data if provided
3. Stores cluster labels for each method
4. Uploads selected methods to Neuronpedia after evaluation
5. Saves upload results in output JSON

### 4. Documentation

Created comprehensive documentation:
- `README_NEURONPEDIA_BASELINE_COMPARISON.md` - Full user guide
- `EXAMPLE_NEURONPEDIA_COMPARISON.sh` - Example shell script with commands
- `NEURONPEDIA_COMPARISON_SUMMARY.md` - This summary document

## How It Works

### Workflow

```
Input CSV (node_grouping_final.csv)
  ↓
Evaluation (local metrics)
  ├─ Concept-Aligned Grouping
  ├─ Cosine Similarity Baseline
  └─ Layer Adjacency Baseline
  ↓
Store cluster_labels for each method
  ↓
Upload to Neuronpedia (if requested)
  ├─ Create grouped DataFrame
  ├─ Generate supernode names
  └─ Upload via existing upload function
  ↓
Output JSON with results + upload status
```

### Data Flow

1. **Read CSV**: Load node grouping CSV with feature_key and supernode_name
2. **Evaluate Methods**: Compute local metrics for each method
3. **Store Labels**: Keep cluster labels (numpy arrays) for upload
4. **Convert Format**: Transform cluster labels → DataFrame with supernode_name
5. **Upload**: Call `upload_subgraph_to_neuronpedia` for each method
6. **Save Results**: Output JSON includes upload status and subgraph IDs

## Usage Examples

### Basic Comparison (No Upload)

```bash
python scripts/experiments/compare_grouping_methods.py \
    --input_csv output/node_grouping_final.csv \
    --output_json output/comparison_local.json
```

### Full Comparison with Upload

```bash
python scripts/experiments/compare_grouping_methods.py \
    --input_csv output/node_grouping_final.csv \
    --graph_json output/st1_graph.json \
    --selected_nodes_json output/st1_feat_node_subset.json \
    --api_key YOUR_NEURONPEDIA_API_KEY \
    --upload_to_neuronpedia \
    --output_json output/comparison_neuronpedia.json
```

### Upload Specific Methods

```bash
python scripts/experiments/compare_grouping_methods.py \
    --input_csv output/node_grouping_final.csv \
    --graph_json output/st1_graph.json \
    --api_key YOUR_API_KEY \
    --upload_to_neuronpedia \
    --upload_concept_aligned \
    --upload_cosine
```

## Expected Results

### Local Metrics

**Coherence**:
- `peak_token_consistency`: Concept-aligned should be highest
- `activation_similarity`: Cosine similarity should be highest
- `influence_variance`: Lower is better, varies by method

**Stability**:
- `silhouette_score`: Higher is better, geometric methods often higher
- `davies_bouldin_score`: Lower is better, varies by method
- `cluster_size_entropy`: Higher = more balanced, layer adjacency often highest

**Interpretability**:
- `avg_cluster_size`, `max_cluster_size`, `min_cluster_size`: Descriptive stats
- `singleton_ratio`: Fraction of single-feature clusters

### Neuronpedia Scores (Manual Retrieval)

After upload, retrieve from Neuronpedia UI:

**Completeness**: How well the subgraph explains model behavior
- **Expected**: Concept-aligned > Cosine > Layer adjacency
- **Rationale**: Semantic groupings should better explain behavior than geometric groupings

**Replacement**: How well supernode groups can be replaced
- **Expected**: Concept-aligned ≥ Cosine ≈ Layer adjacency
- **Rationale**: Functionally coherent groups should have higher replacement scores

## Technical Details

### Supernode Naming

**Concept-Aligned**: Uses existing semantic names from classification
```python
"Texas", "Say (Austin)", "(city) related", "punctuation"
```

**Cosine Similarity**: Generic cluster names
```python
"cosine_cluster_0", "cosine_cluster_1", "cosine_cluster_2", ...
```

**Layer Adjacency**: Generic cluster names
```python
"layer_cluster_0", "layer_cluster_1", "layer_cluster_2", ...
```

### Feature-to-Cluster Mapping

For baselines:
1. Cluster labels are assigned per row (feature × prompt)
2. Aggregate by feature_key using mode (most common cluster)
3. All rows for a feature get the same supernode_name
4. This ensures consistency with the concept-aligned format

### Upload Process

The upload reuses the existing `upload_subgraph_to_neuronpedia` function:

1. Create grouped DataFrame with feature_key and supernode_name
2. Merge with original DataFrame to preserve all columns
3. Generate display name for the method
4. Call upload function with all parameters
5. Return upload response (success/error, subgraph ID)

## File Structure

```
scripts/
├── 02_node_grouping.py                          # Original upload function
└── experiments/
    ├── compare_grouping_methods.py              # Enhanced comparison script
    ├── README_NEURONPEDIA_BASELINE_COMPARISON.md  # User guide
    ├── EXAMPLE_NEURONPEDIA_COMPARISON.sh        # Example commands
    └── NEURONPEDIA_COMPARISON_SUMMARY.md        # This file
```

## Validation

### Import Validation

The script validates that `upload_subgraph_to_neuronpedia` is available:

```python
try:
    from scripts.node_grouping import upload_subgraph_to_neuronpedia
except ImportError:
    # Fallback: load from file
    import importlib.util
    ...
```

### Argument Validation

When `--upload_to_neuronpedia` is set:
- `--graph_json` is required
- `--api_key` is required
- Graph JSON file must exist
- If no specific upload flags set, uploads all methods by default

### Error Handling

Each upload is wrapped in try-except:
- Captures upload errors without stopping other uploads
- Stores error message in results JSON
- Prints summary of successful/failed uploads

## Benefits

1. **Direct Comparison**: Quantitative comparison using Neuronpedia's own metrics
2. **Fair Evaluation**: All methods use same input data and graph
3. **Reproducible**: Script can be rerun with different parameters
4. **Backward Compatible**: Upload is optional, doesn't affect local comparison
5. **Flexible**: Can upload specific methods or all at once

## Limitations

1. **Manual Score Retrieval**: Completeness/replacement scores must be retrieved from Neuronpedia UI
2. **API Rate Limits**: Multiple uploads may hit rate limits (add delays if needed)
3. **Generic Names**: Baseline methods use generic cluster names (not semantic)
4. **Same Cluster Count**: Baselines use same n_clusters as concept-aligned for fair comparison

## Future Enhancements

Potential improvements:

1. **Automatic Score Retrieval**: Query Neuronpedia API to get completeness/replacement scores
2. **Smart Naming**: Generate more descriptive names for baseline clusters
3. **Visualization**: Create comparison charts with all metrics including Neuronpedia scores
4. **Batch Upload**: Add delays between uploads to avoid rate limits
5. **Overwrite Support**: Add flags to overwrite existing subgraphs

## Testing

To test the implementation:

1. **Prerequisites**: Complete Steps 1-3 of the pipeline
2. **Local Test**: Run without upload to verify local metrics work
3. **Upload Test**: Run with upload using test API key
4. **Verify**: Check Neuronpedia UI for uploaded subgraphs
5. **Scores**: Manually retrieve and compare scores

## Troubleshooting

### Common Issues

**Import Error**: `upload_subgraph_to_neuronpedia function not available`
- **Solution**: Ensure `scripts/02_node_grouping.py` exists

**Missing Arguments**: `--graph_json is required`
- **Solution**: Provide all required arguments for upload

**Upload Fails**: Authentication or network errors
- **Solution**: Check API key validity and network connection

**Empty Clusters**: Some baselines produce empty/singleton clusters
- **Solution**: This is expected, comparison metrics account for this

## Conclusion

The enhanced script provides a comprehensive framework for comparing concept-aligned grouping against geometric baselines using both local metrics and Neuronpedia scores. This enables rigorous validation that semantic, behavior-driven clustering outperforms pure geometric methods in explaining model behavior.

