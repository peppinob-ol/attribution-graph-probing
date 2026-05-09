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
import matplotlib.patheffects as pe
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
            ' ': '',
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
    
    @staticmethod
    def _slice_after_first_colon(tokens: List[str], values: List[float]) -> Tuple[List[str], List[float]]:
        """
        Drop tokens up to and including the first ":" token.

        Used to strip prompt-type prefixes like "entity:" / "attribute:" /
        "relationship:" (along with any leading <BOS>) from probe rows.
        Returns the original lists unchanged if no ":" token is found.
        """
        for i, t in enumerate(tokens):
            s = t.strip()
            if s == ':' or s.endswith(':'):
                return tokens[i + 1:], values[i + 1:]
        return tokens, values

    @staticmethod
    def _capitalize_first_token(tokens: List[str]) -> List[str]:
        """
        Return a copy of ``tokens`` with the first letter of the first non-empty
        token uppercased. Preserves any leading whitespace on the token (e.g.
        " the" -> " The") so tokenization isn't disturbed for downstream code.
        Returns ``tokens`` unchanged if the first character is already non-lower.
        """
        if not tokens:
            return tokens
        first = tokens[0]
        stripped = first.lstrip()
        if not stripped or not stripped[0].islower():
            return tokens
        leading = first[:len(first) - len(stripped)]
        new = list(tokens)
        new[0] = leading + stripped[0].upper() + stripped[1:]
        return new

    def visualize_stacked_prompts_for_feature(self,
                                             feature_id: str,
                                             all_probe_data: List[dict],
                                             output_path: Optional[Path] = None,
                                             seed_row: Optional[dict] = None,
                                             clamp_after_colon: bool = True) -> Figure:
        """
        Create stacked visualization of multiple prompts for a single feature.

        Args:
            feature_id: Feature identifier (e.g., "0-clt-hp:40780" or just "40780")
            all_probe_data: List of probe result dictionaries
            output_path: If provided, saves figure to this path
            seed_row: Optional dict with keys ``tokens`` (List[str]) and ``values``
                (List[float]) describing the seed prompt's per-token activations
                for this feature. When provided, it is rendered as the first row
                with a darker border to distinguish it from probe rows.
            clamp_after_colon: If True, drop tokens up to and including the first
                ":" token in each probe (strips "entity:", "attribute:" prefixes).
                The seed row is exempt from this clamp; only its leading <bos>
                token is stripped.

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

        # Optionally drop tokens up to and including the first ':' so probe rows
        # start at the substantive prompt (skipping "entity:", "attribute:", etc.).
        if clamp_after_colon:
            for probe_data in matched_probes:
                probe_data['tokens'], probe_data['values'] = self._slice_after_first_colon(
                    probe_data['tokens'], probe_data['values']
                )

        # Prepend the seed-prompt row (if provided) before any layout/coloring math
        # so it participates in global_max and longest-token calculations.
        has_seed_row = bool(
            seed_row
            and seed_row.get('tokens')
            and seed_row.get('values') is not None
            and len(seed_row['tokens']) == len(seed_row['values'])
        )
        if has_seed_row:
            seed_tokens = list(seed_row['tokens'])
            seed_values = list(seed_row['values'])
            # Strip a leading <bos>-like marker so the seed row aligns visually
            # with the colon-clamped probe rows.
            if seed_tokens and seed_tokens[0].strip().lower() in (
                '<bos>', '<|begin_of_text|>', '<|endoftext|>'
            ):
                seed_tokens = seed_tokens[1:]
                seed_values = seed_values[1:]
            matched_probes.insert(0, {
                'prompt': seed_row.get('prompt', ''),
                'tokens': seed_tokens,
                'values': seed_values,
                'feature_info': matched_probes[0]['feature_info'],
                '_is_seed': True,
            })

        # Capitalize the first letter of every row's first token so probes that
        # start lowercase (e.g. "the state in which...") render as "The ...".
        for probe_data in matched_probes:
            probe_data['tokens'] = self._capitalize_first_token(probe_data['tokens'])

        # Calculate global max for consistent coloring (computed on what we'll render).
        global_max = 0.0
        for probe_data in matched_probes:
            max_val = self.calculate_max_value(probe_data['tokens'], probe_data['values'])
            global_max = max(global_max, max_val)
        
        # Calculate layout
        n_probes = len(matched_probes)
        max_tokens = max(len(p['tokens']) for p in matched_probes)
        n_cols = max(1, min(max_tokens, self.tokens_per_row))

        # Estimate the widest displayed token (in characters) so cells can be
        # widened to fit longer words without truncation.
        longest_display_chars = 1
        for probe_data in matched_probes:
            for token in probe_data['tokens'][:n_cols]:
                longest_display_chars = max(
                    longest_display_chars,
                    len(self.replace_special_tokens(token)),
                )

        # Approximate width of a bold monospace character at the token font size.
        # Empirically tuned: tight cells, but wide enough that 10-char bold-mono
        # tokens like "government" / "containing" sit clear of the cell borders.
        char_width_in = 0.067 * (self.font_size + 1) / 8.0
        # Minimal horizontal padding around the longest token.
        cell_width_in = max(0.32, (longest_display_chars + 0.4) * char_width_in)
        # Width is driven purely by cell content.
        fig_width = max(6.0, cell_width_in * n_cols)

        # Adjust figure size for stacked view - reduced height. The bold title is
        # gone, so we only need a tiny margin above the cells.
        row_height = 0.4  # Reduced by 10x from 1.2
        top_space = 0.08
        fig_height = n_probes * row_height + top_space

        # Reserve a left margin for per-row labels ("seed", "probe N").
        left_label_pad = 0.95
        # Small bleed beyond the cell extents so the bottom-most and right-most
        # cell borders aren't clipped at the axis edge (matplotlib clips patches
        # to the axes box, which would hide half a linewidth).
        edge_bleed = 0.04
        fig, ax = plt.subplots(
            figsize=(fig_width + left_label_pad * cell_width_in, fig_height)
        )
        ax.set_xlim(-left_label_pad, n_cols + edge_bleed)
        ax.set_ylim(-edge_bleed, n_probes + 0.05)
        ax.axis('off')

        # Number probes sequentially, leaving the seed (if present) at index 0.
        # Draw each probe as a row
        probe_counter = 0
        for probe_idx, probe_data in enumerate(matched_probes):
            row = n_probes - probe_idx - 1
            tokens = probe_data['tokens']
            values = probe_data['values']
            is_seed = bool(probe_data.get('_is_seed'))

            # Left-side label for every row.
            if is_seed:
                row_label = 'seed'
            else:
                probe_counter += 1
                row_label = f'probe {probe_counter}'
            ax.text(-left_label_pad + 0.05, row + 0.5, row_label,
                   ha='left', va='center',
                   fontsize=self.font_size,
                   color='dimgray',
                   fontstyle='italic',
                   zorder=2)

            # Draw tokens for this probe
            for token_idx, (token, value) in enumerate(zip(tokens, values)):
                if token_idx >= n_cols:
                    break

                col = token_idx

                # Get background color using global max
                bg_color = self.get_background_color(value, global_max)

                # Seed row uses a darker/thicker border to set it apart visually;
                # probe rows still get a clearly visible (but lighter, thinner) border.
                edge = '#5a6268' if is_seed else '#bdbdbd'
                ew = 1.6 if is_seed else 1.0

                # Draw background rectangle
                rect = patches.Rectangle(
                    (col, row), 1, 1,
                    linewidth=ew,
                    edgecolor=edge,
                    facecolor=bg_color,
                    zorder=1
                )
                ax.add_patch(rect)
                
                # Display token (always black for consistent legibility on green).
                display_token = self.replace_special_tokens(token)
                text_color = 'black'

                ax.text(col + 0.5, row + 0.7, display_token,
                       ha='center', va='top',
                       fontsize=self.font_size + 1,
                       fontfamily='monospace',
                       color=text_color,
                       zorder=2,
                       fontweight='bold')
                
                # Show the activation value whenever the cell is visibly colored,
                # i.e. whenever the value clears MINIMUM_THRESHOLD. The cell's
                # background opacity has a 0.05 floor for any non-zero value, so
                # if the user can see green we should also show the number.
                if self.show_values and value > self.MINIMUM_THRESHOLD:
                    halo_color = 'white' if text_color == 'black' else 'black'
                    ax.text(col + 0.5, row + 0.02,
                           f"{value:.1f}",
                           ha='center', va='bottom',
                           fontsize=max(6.0, self.font_size * 0.85),
                           color=text_color,
                           fontweight='bold',
                           zorder=3,
                           alpha=1.0,
                           path_effects=[
                               pe.withStroke(linewidth=2.0, foreground=halo_color, alpha=0.9)
                           ])
        
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


def _build_seed_row_from_dump(
    seed_dump_path: Path,
    feature_id: str,
    override_prompt: Optional[str] = None,
) -> Optional[dict]:
    """
    Build a seed-prompt row from a per-seed activations dump that contains
    *unpruned* per-token activations for the seed prompt (same schema as
    ``activations_dump.json``: ``{"results": [{"tokens": [...],
    "activations": [{"source", "index", "values": [...]}, ...]}, ...]}``).

    The first result is treated as the seed prompt. We pick the activation
    entry whose (source, index) matches ``feature_id`` and return its full
    per-token ``values`` list -- so the seed row reflects the actual feature
    behaviour on the seed, not the influence-pruned graph view.

    Returns ``None`` if the file is missing/unreadable, has no results, or does
    not contain the requested feature.
    """
    if not seed_dump_path.exists():
        return None

    try:
        with open(seed_dump_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Could not read seed activations dump at {seed_dump_path}: {e}")
        return None

    results = data.get('results') or []
    if not results:
        return None

    res = results[0]
    tokens = res.get('tokens') or []
    if not tokens:
        return None

    if ':' in feature_id:
        target_source, idx_str = feature_id.split(':', 1)
        target_index = int(idx_str)
    else:
        target_source = None
        target_index = int(feature_id)

    values: Optional[List[float]] = None
    for act in res.get('activations', []) or []:
        try:
            idx = int(act.get('index'))
        except (TypeError, ValueError):
            continue
        if idx != target_index:
            continue
        if target_source is not None and act.get('source') != target_source:
            continue
        values = [float(v) for v in (act.get('values') or [])]
        break

    if values is None or len(values) != len(tokens):
        return None

    seed_prompt_text = override_prompt or res.get('prompt', '')
    print(
        f"Seed row from dump: prompt={seed_prompt_text!r}, "
        f"max_activation={max(values) if values else 0.0:.4f}"
    )
    return {
        'tokens': list(tokens),
        'values': values,
        'prompt': seed_prompt_text,
    }


def _build_seed_row_from_graph(
    graph_json_path: Path,
    feature_id: str,
    override_prompt: Optional[str] = None,
) -> Optional[dict]:
    """
    Fallback: construct a seed-prompt row from the attribution graph at
    ``graph_json_path``. The graph is generated on the seed prompt, but its
    node set is **influence-pruned** (typical settings keep nodes that
    cumulatively account for ~80% of influence on the target logit). Diffuse
    features therefore appear sparser here than they really are -- prefer
    ``_build_seed_row_from_dump`` whenever a per-seed activations dump exists.

    Returns ``{'tokens', 'values', 'prompt'}`` or ``None`` if the file is
    missing/unreadable or contains no matching nodes.
    """
    if not graph_json_path.exists():
        return None

    try:
        with open(graph_json_path, 'r', encoding='utf-8') as f:
            graph = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Could not read seed graph at {graph_json_path}: {e}")
        return None

    metadata = graph.get('metadata', {}) or {}
    prompt_tokens = metadata.get('prompt_tokens')
    if not prompt_tokens:
        return None

    # Parse "<layer>-<set>:<index>" or just "<index>".
    if ':' in feature_id:
        target_source, idx_str = feature_id.split(':', 1)
        target_index = int(idx_str)
        layer_str = target_source.split('-', 1)[0]
        try:
            target_layer = int(layer_str)
        except ValueError:
            target_layer = None
    else:
        target_source = None
        target_layer = None
        target_index = int(feature_id)

    values = [0.0] * len(prompt_tokens)
    found_any = False
    for node in graph.get('nodes', []) or []:
        # node_id: "<layer>_<local_feature_index>_<ctx_idx>"
        node_id = node.get('node_id', '')
        parts = node_id.split('_')
        if len(parts) < 3:
            continue
        try:
            n_layer = int(parts[0])
            n_feat = int(parts[1])
            n_ctx = int(parts[-1])
        except ValueError:
            continue
        if target_layer is not None and n_layer != target_layer:
            continue
        if n_feat != target_index:
            continue
        if 0 <= n_ctx < len(values):
            values[n_ctx] += float(node.get('activation', 0.0))
            found_any = True

    if not found_any:
        if override_prompt is None:
            return None

    seed_prompt_text = override_prompt or metadata.get('prompt', '')
    print(
        f"Seed row from graph (PRUNED -- early-token activations may be missing): "
        f"prompt={seed_prompt_text!r}, "
        f"max_activation={max(values) if values else 0.0:.4f}"
    )
    return {
        'tokens': list(prompt_tokens),
        'values': values,
        'prompt': seed_prompt_text,
    }


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
    parser.add_argument(
        '--seed-prompt',
        type=str,
        default=None,
        help='Seed prompt to display as subtitle. If omitted, the script tries '
             'to auto-discover it from "<dump_dir>/../00 Graph Generation/graph.json".'
    )
    parser.add_argument(
        '--seed-activations',
        type=str,
        default=None,
        help='Path to a per-seed activations dump (same schema as activations_dump.json) '
             'whose first result is the seed prompt. When provided -- or when a sibling '
             '"seed_activations_dump.json" exists next to the input dump -- the seed row '
             'is built from these unpruned activations instead of the (pruned) attribution '
             'graph. Falls back to the graph if no dump is found.'
    )
    parser.add_argument(
        '--no-clamp-colon',
        action='store_true',
        help='Disable clamping of probe rows to start after the first ":" token.'
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

        # Resolve the seed row in priority order:
        #   1. explicit --seed-activations dump (unpruned, recommended)
        #   2. sibling seed_activations_dump.json next to the input dump (auto)
        #   3. influence-pruned attribution graph (last-ditch fallback)
        # Option (3) systematically under-shows diffuse features: the graph
        # only retains nodes whose influence on the target logit clears the
        # pruning threshold, so high-activation but low-influence positions
        # vanish from the seed row.
        seed_row = None
        candidate_dumps: List[Path] = []
        if args.seed_activations:
            candidate_dumps.append(Path(args.seed_activations))
        candidate_dumps.append(input_path.parent / "seed_activations_dump.json")
        for cand in candidate_dumps:
            seed_row = _build_seed_row_from_dump(
                seed_dump_path=cand,
                feature_id=args.feature_id,
                override_prompt=args.seed_prompt,
            )
            if seed_row is not None:
                break

        if seed_row is None:
            seed_row = _build_seed_row_from_graph(
                graph_json_path=input_path.parent.parent / "00 Graph Generation" / "graph.json",
                feature_id=args.feature_id,
                override_prompt=args.seed_prompt,
            )

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
            output_path=output_path,
            seed_row=seed_row,
            clamp_after_colon=not args.no_clamp_colon,
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

