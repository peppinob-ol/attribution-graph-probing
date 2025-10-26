"""
Activation Heatmap Visualization

Creates heatmap visualizations of token activations similar to Neuronpedia's display.
Uses the same logarithmic scaling and color mapping approach.
"""

import json
import argparse
from pathlib import Path
import math
from typing import List, Tuple, Optional
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.figure import Figure
import numpy as np


class ActivationHeatmapVisualizer:
    """Visualizes token activations with color-coded backgrounds."""
    
    # Colors from Neuronpedia
    EMERALD_RGB = (52, 211, 153)  # emerald-400
    ORANGE_RGB = (251, 146, 60)   # orange-400
    
    # Constants from Neuronpedia implementation
    MINIMUM_OPACITY = 0.05
    MINIMUM_THRESHOLD = 0.00005
    
    def __init__(self, 
                 figsize: Tuple[int, int] = (16, 3),
                 tokens_per_row: int = 50,
                 show_values: bool = True,
                 font_size: int = 8,
                 exclude_bos: bool = True):
        """
        Initialize the visualizer.
        
        Args:
            figsize: Figure size (width, height)
            tokens_per_row: Number of tokens to display per row
            show_values: Whether to show activation values above tokens
            font_size: Font size for tokens
            exclude_bos: Whether to exclude BOS token from max value calculation
        """
        self.figsize = figsize
        self.tokens_per_row = tokens_per_row
        self.show_values = show_values
        self.font_size = font_size
        self.exclude_bos = exclude_bos
        self.bos_tokens = ['<bos>', '<|endoftext|>', '<|begin_of_text|>']
    
    def calculate_opacity(self, value: float, max_value: float) -> float:
        """
        Calculate opacity using Neuronpedia's logarithmic scaling.
        
        Args:
            value: Current activation value
            max_value: Maximum activation value for normalization
            
        Returns:
            Opacity value between 0 and 1
        """
        if max_value == 0 or value <= self.MINIMUM_THRESHOLD:
            return 0.0
        
        ratio = value / max_value
        scale = 1 - self.MINIMUM_OPACITY
        
        # Logarithmic scaling formula from Neuronpedia
        opacity = self.MINIMUM_OPACITY + (math.log10(1 + 9 * ratio) * scale) / math.log10(10)
        
        # Clamp between 0 and 1
        return max(0.0, min(1.0, opacity))
    
    def get_background_color(self, 
                            value: float, 
                            max_value: float,
                            rgb: Tuple[int, int, int] = None) -> Tuple[float, float, float, float]:
        """
        Get RGBA background color for a token based on its activation value.
        
        Args:
            value: Activation value
            max_value: Maximum activation value for normalization
            rgb: RGB color tuple (defaults to emerald green)
            
        Returns:
            RGBA tuple with values between 0 and 1
        """
        if rgb is None:
            rgb = self.EMERALD_RGB
        
        opacity = self.calculate_opacity(value, max_value)
        
        # Convert RGB from 0-255 to 0-1 range
        r, g, b = rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0
        
        return (r, g, b, opacity)
    
    def replace_special_tokens(self, token: str) -> str:
        """
        Replace special tokens with displayable characters.
        
        Args:
            token: Original token string
            
        Returns:
            Displayable token string
        """
        replacements = {
            '\n': '↵',
            '\t': '→',
            ' ': '·',
            '<bos>': '<BOS>',
            '<eos>': '<EOS>',
            '<|endoftext|>': '<EOT>',
            '<|begin_of_text|>': '<BOT>',
        }
        
        # Check for exact matches first
        if token in replacements:
            return replacements[token]
        
        # Handle special Unicode characters
        display_token = token
        for old, new in replacements.items():
            display_token = display_token.replace(old, new)
        
        return display_token
    
    def calculate_max_value(self, tokens: List[str], values: List[float]) -> float:
        """
        Calculate max value, optionally excluding BOS tokens.
        
        Args:
            tokens: List of tokens
            values: List of activation values
            
        Returns:
            Maximum activation value
        """
        if not values:
            return 0.0
        
        if self.exclude_bos:
            filtered_values = [v for t, v in zip(tokens, values) 
                             if t not in self.bos_tokens]
            return max(filtered_values) if filtered_values else 0.0
        
        return max(values)
    
    def visualize_single_feature(self,
                                 tokens: List[str],
                                 values: List[float],
                                 feature_info: dict,
                                 probe_prompt: str = "") -> Figure:
        """
        Create visualization for a single feature's activations.
        
        Args:
            tokens: List of tokens
            values: List of activation values (same length as tokens)
            feature_info: Dictionary with feature metadata (source, index, etc.)
            probe_prompt: Optional prompt text to display as title
            
        Returns:
            Matplotlib Figure object
        """
        if len(tokens) != len(values):
            raise ValueError(f"Tokens and values must have same length: {len(tokens)} vs {len(values)}")
        
        max_value = self.calculate_max_value(tokens, values)
        
        # Calculate layout
        n_tokens = len(tokens)
        n_rows = math.ceil(n_tokens / self.tokens_per_row)
        
        # Adjust figure height based on number of rows
        fig_height = max(2, min(self.figsize[1], 1 + n_rows * 0.5))
        
        # Create figure
        fig, ax = plt.subplots(figsize=(self.figsize[0], fig_height))
        ax.set_xlim(0, self.tokens_per_row)
        ax.set_ylim(-0.2, n_rows + 0.8)
        ax.axis('off')
        
        # Title
        feature_id = f"{feature_info.get('source', 'unknown')}:{feature_info.get('index', '?')}"
        title = f"Feature {feature_id}"
        if probe_prompt:
            title = f"{title} | {probe_prompt}"
        if self.exclude_bos:
            title += f" | Max: {max_value:.2f} (excl. BOS)"
        else:
            title += f" | Max: {max_value:.2f}"
        
        ax.text(self.tokens_per_row / 2, n_rows + 0.3, title, 
               ha='center', va='bottom', fontsize=self.font_size + 1, 
               fontweight='bold')
        
        # Draw tokens
        for i, (token, value) in enumerate(zip(tokens, values)):
            row = n_rows - 1 - (i // self.tokens_per_row)
            col = i % self.tokens_per_row
            
            # Get background color
            bg_color = self.get_background_color(value, max_value)
            
            # Draw background rectangle
            rect = patches.Rectangle(
                (col, row), 1, 1,
                linewidth=1,
                edgecolor='lightgray',
                facecolor=bg_color,
                zorder=1
            )
            ax.add_patch(rect)
            
            # Display token
            display_token = self.replace_special_tokens(token)
            text_color = 'black' if bg_color[3] < 0.5 else 'white'
            
            ax.text(col + 0.5, row + 0.7, display_token,
                   ha='center', va='top',
                   fontsize=self.font_size,
                   fontfamily='monospace',
                   color=text_color,
                   zorder=2)
            
            # Show activation value if enabled
            if self.show_values and value > self.MINIMUM_THRESHOLD:
                ax.text(col + 0.5, row + 0.3,
                       f"{value:.2f}",
                       ha='center', va='bottom',
                       fontsize=self.font_size - 2,
                       color=text_color,
                       zorder=2,
                       alpha=0.8)
        
        plt.tight_layout()
        return fig
    
    def visualize_stacked_prompts_for_feature(self,
                                             feature_id: str,
                                             all_probe_data: List[dict],
                                             output_path: Optional[Path] = None) -> Figure:
        """
        Create stacked visualization of multiple prompts for a single feature.
        
        Args:
            feature_id: Feature identifier (e.g., "0-clt-hp:40780" or just "40780")
            all_probe_data: List of probe result dictionaries
            output_path: If provided, saves figure to this path
            
        Returns:
            Matplotlib Figure object
        """
        # Parse feature_id
        if ':' in feature_id:
            target_source, target_index = feature_id.split(':')
            target_index = int(target_index)
        else:
            target_source = None
            target_index = int(feature_id)
        
        # Collect matching features from all probes
        matched_probes = []
        for probe in all_probe_data:
            tokens = probe['tokens']
            
            # Find feature in this probe - prefer 'activations' or 'features' over 'counts'
            if 'activations' in probe or 'features' in probe:
                # New format - check both 'features' and 'activations' keys
                features = probe.get('features', probe.get('activations', []))
                for feature in features:
                    if feature.get('index') == target_index:
                        if target_source is None or feature.get('source') == target_source:
                            matched_probes.append({
                                'prompt': probe.get('prompt', ''),
                                'tokens': tokens,
                                'values': feature['values'],
                                'feature_info': feature
                            })
                            break
            elif 'counts' in probe and isinstance(probe['counts'], list):
                # Legacy format
                if target_index < len(probe['counts']):
                    matched_probes.append({
                        'prompt': probe.get('prompt', ''),
                        'tokens': tokens,
                        'values': probe['counts'][target_index],
                        'feature_info': {'source': 'unknown', 'index': target_index}
                    })
        
        if not matched_probes:
            raise ValueError(f"Feature {feature_id} not found in any probe data")
        
        print(f"Found {len(matched_probes)} probes with feature {feature_id}")
        
        # Calculate global max for consistent coloring
        global_max = 0.0
        for probe_data in matched_probes:
            max_val = self.calculate_max_value(probe_data['tokens'], probe_data['values'])
            global_max = max(global_max, max_val)
        
        # Calculate layout
        n_probes = len(matched_probes)
        max_tokens = max(len(p['tokens']) for p in matched_probes)
        n_cols = self.tokens_per_row
        
        # Adjust figure size for stacked view - reduced height
        row_height = 0.4  # Reduced by 10x from 1.2
        title_space = 0.4  # Reduced title space
        fig_height = n_probes * row_height + title_space
        
        fig, ax = plt.subplots(figsize=(self.figsize[0], fig_height))
        ax.set_xlim(0, n_cols)
        ax.set_ylim(0, n_probes + 0.5)
        ax.axis('off')
        
        # Main title
        feature_label = f"{matched_probes[0]['feature_info'].get('source', 'unknown')}:{target_index}"
        title = f"Feature {feature_label} - Stacked Prompts"
        if self.exclude_bos:
            title += f" (excl. BOS) | Global Max: {global_max:.2f}"
        else:
            title += f" | Global Max: {global_max:.2f}"
        
        ax.text(n_cols / 2, n_probes + 0.05, title,
               ha='center', va='bottom', fontsize=self.font_size + 4,
               fontweight='bold')
        
        # Draw each probe as a row
        for probe_idx, probe_data in enumerate(matched_probes):
            row = n_probes - probe_idx - 1
            tokens = probe_data['tokens']
            values = probe_data['values']
            prompt = probe_data['prompt']
            
            # Draw prompt label on the left
            prompt_label = prompt[:60] + '...' if len(prompt) > 60 else prompt
            ax.text(-0.5, row + 0.5, prompt_label,
                   ha='right', va='center', fontsize=self.font_size + 1,
                   style='italic', color='gray')
            
            # Draw tokens for this probe
            for token_idx, (token, value) in enumerate(zip(tokens, values)):
                if token_idx >= n_cols:
                    break
                
                col = token_idx
                
                # Get background color using global max
                bg_color = self.get_background_color(value, global_max)
                
                # Draw background rectangle
                rect = patches.Rectangle(
                    (col, row), 1, 1,
                    linewidth=0.5,
                    edgecolor='lightgray',
                    facecolor=bg_color,
                    zorder=1
                )
                ax.add_patch(rect)
                
                # Display token
                display_token = self.replace_special_tokens(token)
                text_color = 'black' if bg_color[3] < 0.5 else 'white'
                
                # Shorter token display for compact view
                if len(display_token) > 10:
                    display_token = display_token[:9] + '...'
                
                ax.text(col + 0.5, row + 0.7, display_token,
                       ha='center', va='top',
                       fontsize=self.font_size + 1,
                       fontfamily='monospace',
                       color=text_color,
                       zorder=2,
                       fontweight='bold')
                
                # Show value if significant
                if self.show_values and value > self.MINIMUM_THRESHOLD and value > global_max * 0.1:
                    ax.text(col + 0.5, row + 0.1,
                           f"{value:.1f}",
                           ha='center', va='bottom',
                           fontsize=self.font_size / 2,
                           color=text_color,
                           zorder=2,
                           alpha=0.8)
        
        plt.tight_layout()
        
        # Save if output path provided
        if output_path:
            fig.savefig(output_path, dpi=150, bbox_inches='tight')
            print(f"Saved stacked visualization: {output_path}")
        
        return fig
    
    def visualize_top_features(self,
                               tokens: List[str],
                               features_data: List[dict],
                               probe_prompt: str = "",
                               top_k: int = 10,
                               output_path: Optional[Path] = None) -> List[Figure]:
        """
        Create visualizations for the top K features by max activation.
        
        Args:
            tokens: List of tokens
            features_data: List of feature dictionaries with 'values', 'max_value', etc.
            probe_prompt: Optional prompt text
            top_k: Number of top features to visualize
            output_path: If provided, saves figures to this directory
            
        Returns:
            List of Figure objects
        """
        # Sort features by max_value
        sorted_features = sorted(features_data, 
                                key=lambda x: x.get('max_value', 0.0),
                                reverse=True)
        
        top_features = sorted_features[:top_k]
        
        figures = []
        for idx, feature in enumerate(top_features):
            fig = self.visualize_single_feature(
                tokens=tokens,
                values=feature['values'],
                feature_info=feature,
                probe_prompt=probe_prompt if idx == 0 else ""
            )
            figures.append(fig)
            
            # Save if output path provided
            if output_path:
                output_path.mkdir(parents=True, exist_ok=True)
                feature_id = f"{feature.get('source', 'unknown')}_{feature.get('index', 'unknown')}"
                filename = output_path / f"feature_{feature_id}_rank{idx+1}.png"
                fig.savefig(filename, dpi=150, bbox_inches='tight')
                print(f"Saved: {filename}")
        
        return figures
    
    def visualize_all_features_combined(self,
                                       tokens: List[str],
                                       features_data: List[dict],
                                       probe_prompt: str = "",
                                       output_path: Optional[Path] = None) -> Figure:
        """
        Create a combined heatmap showing all features.
        
        Args:
            tokens: List of tokens
            features_data: List of feature dictionaries
            probe_prompt: Optional prompt text
            output_path: If provided, saves figure to this path
            
        Returns:
            Matplotlib Figure object
        """
        n_features = len(features_data)
        n_tokens = len(tokens)
        
        # Create activation matrix
        activation_matrix = np.zeros((n_features, n_tokens))
        for i, feature in enumerate(features_data):
            activation_matrix[i, :] = feature['values']
        
        # Create figure
        fig, ax = plt.subplots(figsize=(max(16, n_tokens * 0.5), max(10, n_features * 0.3)))
        
        # Create heatmap
        im = ax.imshow(activation_matrix, aspect='auto', cmap='Greens', 
                      interpolation='nearest')
        
        # Set ticks
        ax.set_xticks(range(n_tokens))
        ax.set_xticklabels([self.replace_special_tokens(t) for t in tokens],
                          rotation=45, ha='right', fontsize=8)
        
        ax.set_yticks(range(n_features))
        feature_labels = [f"{f.get('source', '?')}:{f.get('index', '?')}" 
                         for f in features_data]
        ax.set_yticklabels(feature_labels, fontsize=8)
        
        # Labels
        ax.set_xlabel('Tokens', fontsize=10)
        ax.set_ylabel('Features', fontsize=10)
        
        # Title
        title = "All Features Activation Heatmap"
        if probe_prompt:
            title += f"\n{probe_prompt}"
        ax.set_title(title, fontsize=12, fontweight='bold', pad=20)
        
        # Colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Activation Value', rotation=270, labelpad=20)
        
        plt.tight_layout()
        
        # Save if output path provided
        if output_path:
            fig.savefig(output_path, dpi=150, bbox_inches='tight')
            print(f"Saved combined heatmap: {output_path}")
        
        return fig


def main():
    """Main function to process activation dump and create visualizations."""
    parser = argparse.ArgumentParser(
        description='Create heatmap visualizations from activation dump JSON'
    )
    parser.add_argument(
        'input_json',
        type=str,
        help='Path to activation dump JSON file'
    )
    parser.add_argument(
        '-o', '--output-dir',
        type=str,
        default='output/activation_heatmaps',
        help='Output directory for images (default: output/activation_heatmaps)'
    )
    parser.add_argument(
        '-k', '--top-k',
        type=int,
        default=10,
        help='Number of top features to visualize individually (default: 10)'
    )
    parser.add_argument(
        '--tokens-per-row',
        type=int,
        default=20,
        help='Tokens per row in visualization (default: 20)'
    )
    parser.add_argument(
        '--no-values',
        action='store_true',
        help='Hide activation values on tokens'
    )
    parser.add_argument(
        '--combined-only',
        action='store_true',
        help='Only generate combined heatmap, skip individual features'
    )
    parser.add_argument(
        '--probe-index',
        type=int,
        default=0,
        help='Index of probe result to visualize (default: 0)'
    )
    parser.add_argument(
        '--feature-id',
        type=str,
        help='Specific feature ID to visualize across all probes (e.g., "40780" or "0-clt-hp:40780")'
    )
    parser.add_argument(
        '--include-bos',
        action='store_true',
        help='Include BOS token in max value calculation (default: exclude)'
    )
    
    args = parser.parse_args()
    
    # Load JSON data
    input_path = Path(args.input_json)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    print(f"Loading data from: {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Extract results
    results = data.get('results', [])
    if not results:
        raise ValueError("No results found in JSON data")
    
    # Check if user wants stacked visualization for a specific feature
    if args.feature_id:
        print(f"\nGenerating stacked visualization for feature {args.feature_id}")
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize visualizer
        visualizer = ActivationHeatmapVisualizer(
            tokens_per_row=args.tokens_per_row,
            show_values=not args.no_values,
            exclude_bos=not args.include_bos
        )
        
        output_path = output_dir / f"feature_{args.feature_id.replace(':', '_')}_stacked.png"
        visualizer.visualize_stacked_prompts_for_feature(
            feature_id=args.feature_id,
            all_probe_data=results,
            output_path=output_path
        )
        
        print(f"\nStacked visualization saved to: {output_path}")
        print("Done!")
        return
    
    if args.probe_index >= len(results):
        raise ValueError(f"Probe index {args.probe_index} out of range (max: {len(results) - 1})")
    
    probe_data = results[args.probe_index]
    tokens = probe_data['tokens']
    probe_prompt = probe_data.get('prompt', '')
    
    # Get features data - check if it's in 'counts', 'features', or 'activations' format
    if 'activations' in probe_data:
        # Newer format with 'activations' key
        features_data = probe_data['activations']
    elif 'features' in probe_data:
        # Newer format with 'features' key
        features_data = probe_data['features']
    elif 'counts' in probe_data and isinstance(probe_data['counts'], list):
        # Legacy format: counts is a 2D array [n_features][n_tokens]
        counts = probe_data['counts']
        features_data = []
        for i, values in enumerate(counts):
            features_data.append({
                'source': 'unknown',
                'index': i,
                'values': values,
                'max_value': max(values) if values else 0.0,
                'max_value_index': values.index(max(values)) if values and max(values) > 0 else 0
            })
    else:
        features_data = []
    
    if not features_data:
        raise ValueError("No features data found in probe result")
    
    print(f"Found {len(tokens)} tokens and {len(features_data)} features")
    print(f"Prompt: {probe_prompt}")
    
    # Create output directory
    output_dir = Path(args.output_dir)
    probe_dir = output_dir / f"probe_{args.probe_index}"
    probe_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize visualizer
    visualizer = ActivationHeatmapVisualizer(
        tokens_per_row=args.tokens_per_row,
        show_values=not args.no_values,
        exclude_bos=not args.include_bos
    )
    
    # Generate combined heatmap
    print("\nGenerating combined heatmap...")
    combined_path = probe_dir / "combined_heatmap.png"
    visualizer.visualize_all_features_combined(
        tokens=tokens,
        features_data=features_data,
        probe_prompt=probe_prompt,
        output_path=combined_path
    )
    
    # Generate individual feature visualizations
    if not args.combined_only:
        print(f"\nGenerating top {args.top_k} individual feature visualizations...")
        visualizer.visualize_top_features(
            tokens=tokens,
            features_data=features_data,
            probe_prompt=probe_prompt,
            top_k=args.top_k,
            output_path=probe_dir
        )
    
    print(f"\nAll visualizations saved to: {probe_dir}")
    print("Done!")


if __name__ == '__main__':
    main()

