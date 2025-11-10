# Neuronpedia Baseline Comparison - Michael Jordan Example

## Quick Start

### Step 1: Set Your API Key

```powershell
$env:NEURONPEDIA_API_KEY = "your-neuronpedia-api-key-here"
```

### Step 2: Run the Comparison

**Option A - Use the PowerShell script:**
```powershell
cd "output/examples/michael hordan plays"
.\run_neuronpedia_comparison.ps1
```

**Option B - Run directly:**
```powershell
cd c:\Github\circuit_tracer-prompt_rover

python scripts/experiments/compare_grouping_methods.py `
    --input_csv "output/examples/michael hordan plays/02 Node Grouping/node_grouping_final_20251026_153754.csv" `
    --graph_json "output/examples/michael hordan plays/00 Graph Generation/fact_michael_jordan_202510262027-20251026-022811.json" `
    --selected_nodes_json "output/examples/michael hordan plays/00 Graph Generation/selected_features_with_nodes (1).json" `
    --api_key $env:NEURONPEDIA_API_KEY `
    --upload_to_neuronpedia `
    --output_json "output/examples/michael hordan plays/02 Node Grouping/comparison_with_neuronpedia.json"
```

## What This Will Do

1. **Load Your Data**
   - 172 features from node grouping
   - 16 concept-aligned supernodes
   - Graph structure from Neuronpedia

2. **Compute Local Metrics**
   - Coherence (peak token consistency, activation similarity)
   - Stability (silhouette score, Davies-Bouldin)
   - Interpretability (cluster sizes)

3. **Upload 3 Methods to Neuronpedia**
   - **Concept-Aligned Grouping** - Your semantic supernodes (Michael, basketball, Say (basketball), etc.)
   - **Cosine Similarity Baseline** - Activation pattern clusters (cosine_cluster_0, cosine_cluster_1, ...)
   - **Layer Adjacency Baseline** - Position-based clusters (layer_cluster_0, layer_cluster_1, ...)

4. **Save Results**
   - Output JSON with all metrics
   - Upload status for each method
   - Subgraph IDs for Neuronpedia

## Expected Results (Based on Local Metrics)

### Concept-Aligned Grouping
✅ **Best for semantic coherence**
- Peak Token Consistency: **0.425** (highest)
- Activation Similarity: **0.762** (highest)
- No singleton clusters (all clusters have ≥4 features)
- **Expected Neuronpedia Scores**: Highest completeness & replacement

### Cosine Similarity Baseline
⚠️ **Geometrically focused**
- Peak Token Consistency: **0.183** (lower)
- Activation Similarity: **0.130** (lower)
- Silhouette Score: **-0.386** (negative = poor clustering)
- 87.5% singleton clusters (14 out of 16 clusters have only 1 feature)
- **Expected Neuronpedia Scores**: Lower completeness & replacement

### Layer Adjacency Baseline
⚠️ **Position-based only**
- Will cluster features by layer position
- May miss semantic relationships
- **Expected Neuronpedia Scores**: Lowest completeness & replacement

## After Upload: View on Neuronpedia

### Your Existing Graph
https://www.neuronpedia.org/gemma-2-2b/graph?slug=fact_michael_jordan_202510262027-20251026-022811

### Loading Subgraphs

1. Open your graph on Neuronpedia
2. Click **"Load Subgraph"** button (bottom-left panel)
3. You'll see 3 new subgraphs:
   - Concept-Aligned Grouping
   - Cosine Similarity Baseline
   - Layer Adjacency Baseline
4. Load each one to compare

### Retrieving Scores

For each subgraph:
1. Load the subgraph
2. Look for **Completeness** score (higher = better explanation of behavior)
3. Look for **Replacement** score (higher = more coherent functional groups)
4. Compare across all three methods

### Expected Pattern

```
Method                      | Completeness | Replacement | Peak Token Consistency
----------------------------|--------------|-------------|----------------------
Concept-Aligned             | Highest ✅   | Highest ✅  | 0.425 ✅
Cosine Similarity           | Medium ⚠️    | Medium ⚠️   | 0.183 ⚠️
Layer Adjacency             | Lowest ❌    | Lowest ❌   | TBD ❌
```

## Files Used

### Input Files
- **Node Grouping CSV**: Contains 172 features with semantic supernode names
  - Path: `02 Node Grouping/node_grouping_final_20251026_153754.csv`
  - Features: 172
  - Supernodes: 16
  
- **Graph JSON**: Original attribution graph from Neuronpedia
  - Path: `00 Graph Generation/fact_michael_jordan_202510262027-20251026-022811.json`
  - Matches: https://www.neuronpedia.org/gemma-2-2b/graph?slug=fact_michael_jordan_202510262027-20251026-022811
  
- **Selected Nodes JSON**: Feature subset for accurate upload
  - Path: `00 Graph Generation/selected_features_with_nodes (1).json`

### Output Files
- **comparison_with_neuronpedia.json**: Complete results with upload status
- **Local comparison already exists**: `node_grouping_final_20251026_153754_comparison.json`

## Interpretation

### Why Concept-Aligned Should Win

1. **Semantic Coherence**
   - Groups features by behavior (e.g., all "Michael" related features together)
   - Higher peak token consistency (0.425 vs 0.183)
   - More stable cluster sizes (no singletons)

2. **Functional Relevance**
   - Supernodes represent meaningful concepts ("Michael", "basketball", "Say (basketball)")
   - Should have higher completeness on Neuronpedia (better explains model behavior)
   - Should have higher replacement (features in same group are functionally similar)

3. **Geometric Methods Fail**
   - Cosine similarity: 87.5% singleton clusters (not useful groupings)
   - Layer adjacency: Ignores semantic relationships
   - Negative silhouette scores indicate poor clustering quality

## Troubleshooting

### API Key Issues
```powershell
# Check if set
if ($env:NEURONPEDIA_API_KEY) { "Key is set" } else { "Key NOT set" }

# Set it
$env:NEURONPEDIA_API_KEY = "your-key-here"
```

### Upload Fails
- Check network connection
- Verify API key is valid
- Check Neuronpedia status

### Script Errors
- Ensure Python dependencies installed: `pip install -r requirements.txt`
- Check file paths are correct
- Look for error messages in output

## Next Steps After Running

1. ✅ Script completes successfully
2. ✅ Check `comparison_with_neuronpedia.json` for upload status
3. ✅ Open Neuronpedia graph
4. ✅ Load each subgraph
5. ✅ Record completeness & replacement scores
6. ✅ Compare: Concept-aligned should have highest scores
7. ✅ Document results for paper/presentation

## References

- Neuronpedia Graph: [fact_michael_jordan_202510262027-20251026-022811](https://www.neuronpedia.org/gemma-2-2b/graph?slug=fact_michael_jordan_202510262027-20251026-022811)
- Documentation: `scripts/experiments/README_NEURONPEDIA_BASELINE_COMPARISON.md`
- Implementation: `scripts/experiments/compare_grouping_methods.py`

