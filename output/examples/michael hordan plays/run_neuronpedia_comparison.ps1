# PowerShell script to run Neuronpedia comparison on Michael Jordan example
# 
# Usage:
#   1. Set your API key: $env:NEURONPEDIA_API_KEY = "your-api-key-here"
#   2. Run this script: .\run_neuronpedia_comparison.ps1

# Change to project directory
Set-Location "c:\Github\attribution-graph-probing"

# Check if API key is set
if (-not $env:NEURONPEDIA_API_KEY) {
    Write-Host "ERROR: NEURONPEDIA_API_KEY environment variable not set" -ForegroundColor Red
    Write-Host "Please run: `$env:NEURONPEDIA_API_KEY = 'your-api-key-here'" -ForegroundColor Yellow
    exit 1
}

Write-Host "Running comparison with Neuronpedia upload..." -ForegroundColor Green
Write-Host ""

# Run the comparison script
python scripts/experiments/compare_grouping_methods.py `
    --input_csv "output/examples/michael hordan plays/02 Node Grouping/node_grouping_final_20251026_153754.csv" `
    --graph_json "output/examples/michael hordan plays/00 Graph Generation/fact_michael_jordan_202510262027-20251026-022811.json" `
    --selected_nodes_json "output/examples/michael hordan plays/00 Graph Generation/selected_features_with_nodes (1).json" `
    --api_key $env:NEURONPEDIA_API_KEY `
    --upload_to_neuronpedia `
    --output_json "output/examples/michael hordan plays/02 Node Grouping/comparison_with_neuronpedia.json"

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "SUCCESS! Comparison complete." -ForegroundColor Green
    Write-Host ""
    Write-Host "Results saved to: comparison_with_neuronpedia.json" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "1. Open Neuronpedia: https://www.neuronpedia.org/gemma-2-2b/graph?slug=fact_michael_jordan_202510262027-20251026-022811"
    Write-Host "2. Use 'Load Subgraph' button to load each uploaded method:"
    Write-Host "   - Concept-Aligned Grouping"
    Write-Host "   - Cosine Similarity Baseline"
    Write-Host "   - Layer Adjacency Baseline"
    Write-Host "3. Compare completeness and replacement scores"
} else {
    Write-Host ""
    Write-Host "ERROR: Script failed with exit code $LASTEXITCODE" -ForegroundColor Red
}

