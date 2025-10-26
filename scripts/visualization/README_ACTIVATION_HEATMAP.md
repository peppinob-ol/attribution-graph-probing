# Activation Heatmap Visualization

This script creates Neuronpedia-style heatmap visualizations of token activations from activation dump JSON files.

## Overview

The script implements the same logarithmic scaling and color mapping approach used by Neuronpedia to visualize how features activate on different tokens. Each token is displayed with a green background whose intensity corresponds to the activation value.

## Features

- **Logarithmic scaling**: Uses the same formula as Neuronpedia for opacity mapping
- **Individual feature visualizations**: Shows each feature's activations across tokens
- **Combined heatmap**: Matrix view of all features vs all tokens
- **Color coding**: Green intensity from light (low activation) to dark (high activation)
- **Special token handling**: Replaces special tokens with displayable characters
- **Value display**: Optional display of numerical activation values on tokens

## Usage

### Basic Usage

```bash
python scripts/visualization/activation_heatmap.py path/to/activations_dump.json
```

This will create visualizations in `output/activation_heatmaps/` by default.

### Command Line Options

```bash
python scripts/visualization/activation_heatmap.py INPUT_JSON [OPTIONS]

Required:
  INPUT_JSON              Path to activation dump JSON file

Optional:
  -o, --output-dir DIR    Output directory (default: output/activation_heatmaps)
  -k, --top-k N          Number of top features to visualize (default: 10)
  --probe-index N        Index of probe result to visualize (default: 0)
  --tokens-per-row N     Tokens per row in visualization (default: 20)
  --no-values            Hide activation values on tokens
  --combined-only        Only generate combined heatmap
```

### Examples

**Visualize top 5 features from a specific probe:**
```bash
python scripts/visualization/activation_heatmap.py \
  "output/examples/Dallas/activations_dump (2).json" \
  -k 5 \
  --probe-index 0 \
  -o output/my_visualizations
```

**Generate only the combined heatmap:**
```bash
python scripts/visualization/activation_heatmap.py \
  "output/examples/Dallas/activations_dump (2).json" \
  --combined-only
```

**Adjust layout for longer prompts:**
```bash
python scripts/visualization/activation_heatmap.py \
  "output/examples/Dallas/activations_dump (2).json" \
  --tokens-per-row 30
```

## Input Format

The script expects JSON files with this structure:

```json
{
  "model": "model-name",
  "results": [
    {
      "probe_id": "probe_0_Dallas",
      "prompt": "entity: A city in Texas, USA is Dallas",
      "tokens": ["<bos>", "entity", ":", " A", ...],
      "counts": [[9813.0, 72.0, ...], ...] // OR features array
    }
  ]
}
```

Supports both:
- Legacy `counts` format: 2D array [n_features][n_tokens]
- New `features` format: List of feature objects with metadata

## Output

The script generates:

1. **Combined heatmap** (`combined_heatmap.png`): Matrix visualization showing all features
2. **Individual feature images** (one per top-K feature): Detailed view of each feature's activations

All images are saved to: `{output_dir}/probe_{index}/`

## Color Scheme

- **Base color**: Emerald green (RGB: 52, 211, 153)
- **Opacity range**: 0.05 (minimum) to 1.0 (maximum)
- **Threshold**: Values below 0.00005 are not highlighted
- **Text color**: Black on light backgrounds, white on dark backgrounds

## Implementation Details

The visualization uses the exact same logarithmic opacity calculation as Neuronpedia:

```python
opacity = MINIMUM_OPACITY + (log10(1 + 9 * ratio) * scale) / log10(10)
```

Where:
- `ratio = current_value / max_value`
- `scale = 1 - MINIMUM_OPACITY`
- `MINIMUM_OPACITY = 0.05`

This creates a perceptually uniform color gradient that emphasizes differences in lower activation ranges while still showing the full dynamic range.

## Dependencies

- matplotlib
- numpy
- Python 3.7+

Install with:
```bash
pip install matplotlib numpy
```

