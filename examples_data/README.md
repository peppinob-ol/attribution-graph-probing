# Example Data - Dallas

This directory contains a complete example analysis for demonstration purposes.

## Dataset: Dallas - Austin Prediction

**Prompt**: "The capital of state containing Dallas is"  
**Target**: " Austin"  
**Model**: Gemma-2-2B with Cross-Layer Transcoders (CLT)  
**Features**: 55 features analyzed

## Files Included

### Stage 1: Graph Generation
- `clt-hp-the-capital-of-201020250035-20251020-003525.json` - Complete attribution graph
- `selected_features_with_nodes.json` - Selected features for analysis

### Stage 2: Probe Prompts
- `prompts.json` - Semantic concepts used for probing
- `2025-10-21T07-40_export_ENRICHED.csv` - Activation analysis results
- `activations_dump (2).json` - Raw activation data

### Stage 3: Node Grouping
- `node_grouping_final_20251027_173744.csv` - Final classification and naming
- `node_grouping_summary_20251027_173749.json` - Summary statistics
- `node_grouping_step1_20251027_180825.csv` - Token classification
- `node_grouping_step2_20251027_180821.csv` - Feature classification

## How to Use

1. Navigate to each stage page in the Streamlit app
2. Use the "Load Example" or file upload options
3. Load the corresponding files from this directory
4. Explore the visualizations and results

## Results Summary

The analysis identified:
- **Semantic (Dictionary)** features: Tokens like "Dallas", "Texas", "Austin"
- **Semantic (Concept)** features: Related concepts about cities and states
- **Say "X"** features: Output prediction mechanisms
- **Relationship** features: Connections between geographical entities

This demonstrates the complete pipeline for automated sparse feature interpretation.

