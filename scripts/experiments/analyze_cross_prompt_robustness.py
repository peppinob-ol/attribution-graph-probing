"""
Cross-Prompt Robustness Analysis
================================

Analyzes stability of discovered supernodes and features across different probe variations.

Tests semantic transfer by comparing:
- Dallas -> Austin (Texas capital)
- Oakland -> Sacramento (California capital)

Both test the same conceptual relationship with different entities.
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from typing import Dict, List, Tuple, Set
from collections import defaultdict
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime


class CrossPromptRobustnessAnalyzer:
    """Analyzes robustness of supernodes and features across different prompts."""
    
    def __init__(self, probe1_csv: str, probe1_json: str, probe1_name: str,
                 probe2_csv: str, probe2_json: str, probe2_name: str,
                 output_dir: str = "output/validation"):
        """
        Initialize analyzer with two probe datasets.
        
        Args:
            probe1_csv: Path to first probe's node_grouping_final CSV
            probe1_json: Path to first probe's node_grouping_summary JSON
            probe1_name: Human-readable name (e.g., "Dallas")
            probe2_csv: Path to second probe's CSV
            probe2_json: Path to second probe's JSON
            probe2_name: Human-readable name (e.g., "Oakland")
            output_dir: Where to save results
        """
        self.probe1_name = probe1_name
        self.probe2_name = probe2_name
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load data
        self.df1 = pd.read_csv(probe1_csv)
        self.df2 = pd.read_csv(probe2_csv)
        
        with open(probe1_json, 'r') as f:
            self.summary1 = json.load(f)
        with open(probe2_json, 'r') as f:
            self.summary2 = json.load(f)
        
        print(f"Loaded {self.probe1_name}: {len(self.df1)} features")
        print(f"Loaded {self.probe2_name}: {len(self.df2)} features")
        
        # Results storage
        self.results = {}
        
    def get_feature_id(self, row) -> str:
        """Get unique feature identifier (layer_index)."""
        return row['feature_key']
    
    def categorize_supernodes(self) -> Dict[str, List[str]]:
        """
        Categorize supernodes into universal, entity-specific, and output types.
        
        Returns:
            Dictionary with categories as keys and lists of supernode names
        """
        s1_nodes = set(self.df1['supernode_name'].dropna().unique())
        s2_nodes = set(self.df2['supernode_name'].dropna().unique())
        
        # Universal: appear in both (or should appear in both conceptually)
        universal_keywords = ['is', 'of', 'capital', 'containing', 'related', 'seat']
        
        # Entity-specific: state/city names
        entity_keywords = [
            'Texas', 'California', 'Dallas', 'Oakland', 'Austin', 'Sacramento',
            'United'  # might appear in "United States" context
        ]
        
        # Output promotion: "Say (X)"
        sayx_pattern = 'Say ('
        
        categorized = {
            'universal': [],
            'entity_specific': [],
            'output_promotion': [],
            'uncategorized': []
        }
        
        all_nodes = s1_nodes | s2_nodes
        
        for node in all_nodes:
            if pd.isna(node) or node == '':
                continue
                
            if sayx_pattern in node:
                categorized['output_promotion'].append(node)
            elif any(kw.lower() in node.lower() for kw in entity_keywords):
                categorized['entity_specific'].append(node)
            elif any(kw.lower() in node.lower() for kw in universal_keywords):
                categorized['universal'].append(node)
            else:
                categorized['uncategorized'].append(node)
        
        return categorized
    
    def analyze_supernode_transfer(self) -> pd.DataFrame:
        """
        Analyze which supernodes transfer between probes.
        
        Returns:
            DataFrame with transfer analysis
        """
        s1_nodes = set(self.df1['supernode_name'].dropna().unique())
        s2_nodes = set(self.df2['supernode_name'].dropna().unique())
        
        categories = self.categorize_supernodes()
        
        results = []
        
        for category, nodes in categories.items():
            for node in nodes:
                in_probe1 = node in s1_nodes
                in_probe2 = node in s2_nodes
                
                # Get feature counts and influence
                count1 = len(self.df1[self.df1['supernode_name'] == node]) if in_probe1 else 0
                count2 = len(self.df2[self.df2['supernode_name'] == node]) if in_probe2 else 0
                
                influence1 = self.df1[self.df1['supernode_name'] == node]['node_influence'].sum() if in_probe1 else 0
                influence2 = self.df2[self.df2['supernode_name'] == node]['node_influence'].sum() if in_probe2 else 0
                
                # Determine transfer success
                if category == 'universal':
                    transfer = 'Full transfer' if (in_probe1 and in_probe2) else 'Failed transfer'
                elif category == 'entity_specific':
                    transfer = 'Appropriate non-transfer' if (in_probe1 != in_probe2) else 'Unexpected presence'
                elif category == 'output_promotion':
                    # Check if parallel structure exists
                    if in_probe1 and in_probe2:
                        transfer = 'Unexpected (should be entity-specific)'
                    elif in_probe1 or in_probe2:
                        transfer = 'Target-appropriate (single probe)'
                    else:
                        transfer = 'Neither probe'
                else:
                    transfer = 'Check manually'
                
                results.append({
                    'supernode_name': node,
                    'category': category,
                    f'{self.probe1_name}_present': in_probe1,
                    f'{self.probe2_name}_present': in_probe2,
                    f'{self.probe1_name}_n_features': count1,
                    f'{self.probe2_name}_n_features': count2,
                    f'{self.probe1_name}_influence': influence1,
                    f'{self.probe2_name}_influence': influence2,
                    'transfer_status': transfer
                })
        
        df_transfer = pd.DataFrame(results)
        df_transfer = df_transfer.sort_values(['category', 'supernode_name'])
        
        self.results['supernode_transfer'] = df_transfer
        return df_transfer
    
    def analyze_shared_features(self) -> Dict:
        """
        Analyze features that appear in both probes.
        
        Returns:
            Dictionary with shared feature analysis
        """
        # Get feature IDs from both probes
        features1 = set(self.df1['feature_key'])
        features2 = set(self.df2['feature_key'])
        
        shared = features1 & features2
        unique1 = features1 - features2
        unique2 = features2 - features1
        
        print(f"\nFeature Overlap:")
        print(f"  Shared: {len(shared)} ({len(shared)/len(features1)*100:.1f}% of {self.probe1_name})")
        print(f"  {self.probe1_name} unique: {len(unique1)}")
        print(f"  {self.probe2_name} unique: {len(unique2)}")
        
        # Analyze shared features by layer
        layer_analysis = []
        
        for layer in sorted(self.df1['layer'].unique()):
            f1_layer = set(self.df1[self.df1['layer'] == layer]['feature_key'])
            f2_layer = set(self.df2[self.df2['layer'] == layer]['feature_key'])
            
            shared_layer = f1_layer & f2_layer
            
            if len(f1_layer) > 0:
                overlap_pct = len(shared_layer) / len(f1_layer) * 100
                layer_analysis.append({
                    'layer': layer,
                    'n_shared': len(shared_layer),
                    f'n_{self.probe1_name}': len(f1_layer),
                    f'n_{self.probe2_name}': len(f2_layer),
                    'overlap_pct': overlap_pct
                })
        
        df_layer_overlap = pd.DataFrame(layer_analysis)
        
        # Analyze grouping consistency for shared features
        consistent_grouping = 0
        inconsistent_grouping = 0
        grouping_details = []
        
        for feat in shared:
            row1 = self.df1[self.df1['feature_key'] == feat].iloc[0]
            row2 = self.df2[self.df2['feature_key'] == feat].iloc[0]
            
            sn1 = row1['supernode_name']
            sn2 = row2['supernode_name']
            
            # Check if groupings are semantically equivalent
            if pd.isna(sn1) and pd.isna(sn2):
                consistent = True
            elif pd.isna(sn1) or pd.isna(sn2):
                consistent = False
            else:
                # Simple check: same name = consistent
                # More sophisticated: check category equivalence
                consistent = (sn1 == sn2) or self._are_equivalent_groups(sn1, sn2)
            
            if consistent:
                consistent_grouping += 1
            else:
                inconsistent_grouping += 1
            
            grouping_details.append({
                'feature_key': feat,
                'layer': row1['layer'],
                f'{self.probe1_name}_supernode': sn1,
                f'{self.probe2_name}_supernode': sn2,
                'consistent': consistent
            })
        
        consistency_rate = consistent_grouping / len(shared) * 100 if len(shared) > 0 else 0
        
        print(f"\nShared Feature Grouping Consistency:")
        print(f"  Consistent: {consistent_grouping}/{len(shared)} ({consistency_rate:.1f}%)")
        print(f"  Inconsistent: {inconsistent_grouping}/{len(shared)}")
        
        df_grouping = pd.DataFrame(grouping_details)
        
        return {
            'shared_features': shared,
            'unique_to_probe1': unique1,
            'unique_to_probe2': unique2,
            'n_shared': len(shared),
            'n_unique1': len(unique1),
            'n_unique2': len(unique2),
            'consistency_rate': consistency_rate,
            'layer_overlap': df_layer_overlap,
            'grouping_details': df_grouping
        }
    
    def _are_equivalent_groups(self, sn1: str, sn2: str) -> bool:
        """Check if two supernode names represent equivalent concepts."""
        # Universal concepts
        universal = ['is', 'of', 'capital', 'seat', 'containing']
        if any(u in sn1.lower() and u in sn2.lower() for u in universal):
            return True
        
        # Relationship patterns
        if 'related' in sn1.lower() and 'related' in sn2.lower():
            return True
        
        return False
    
    def analyze_activation_similarity(self) -> pd.DataFrame:
        """
        Compare activation profiles for shared features.
        
        Returns:
            DataFrame with activation similarity metrics
        """
        shared = self.results.get('shared_features_analysis', {}).get('shared_features', set())
        
        if not shared:
            # Run shared features analysis first
            self.results['shared_features_analysis'] = self.analyze_shared_features()
            shared = self.results['shared_features_analysis']['shared_features']
        
        similarity_results = []
        
        for feat in shared:
            row1 = self.df1[self.df1['feature_key'] == feat].iloc[0]
            row2 = self.df2[self.df2['feature_key'] == feat].iloc[0]
            
            # Compare activation metrics
            act_max_diff = abs(row1['activation_max'] - row2['activation_max'])
            act_max_rel = act_max_diff / max(row1['activation_max'], row2['activation_max'], 1e-6)
            
            sparsity_diff = abs(row1['sparsity_ratio'] - row2['sparsity_ratio'])
            
            influence_diff = abs(row1['node_influence'] - row2['node_influence'])
            
            peak_same = (row1['peak_token'] == row2['peak_token'])
            peak_type_same = (row1['peak_token_type'] == row2['peak_token_type'])
            
            similarity_results.append({
                'feature_key': feat,
                'layer': row1['layer'],
                f'{self.probe1_name}_supernode': row1['supernode_name'],
                f'{self.probe2_name}_supernode': row2['supernode_name'],
                'activation_max_diff': act_max_diff,
                'activation_max_rel_diff': act_max_rel,
                'sparsity_diff': sparsity_diff,
                'influence_diff': influence_diff,
                'peak_token_same': peak_same,
                'peak_type_same': peak_type_same,
                f'{self.probe1_name}_peak': row1['peak_token'],
                f'{self.probe2_name}_peak': row2['peak_token']
            })
        
        df_similarity = pd.DataFrame(similarity_results)
        
        # Summary statistics
        print(f"\nActivation Similarity (shared features, n={len(df_similarity)}):")
        print(f"  Mean activation_max relative diff: {df_similarity['activation_max_rel_diff'].mean():.3f}")
        print(f"  Mean sparsity diff: {df_similarity['sparsity_diff'].mean():.3f}")
        print(f"  Peak token same: {df_similarity['peak_token_same'].sum()}/{len(df_similarity)} ({df_similarity['peak_token_same'].sum()/len(df_similarity)*100:.1f}%)")
        print(f"  Peak type same: {df_similarity['peak_type_same'].sum()}/{len(df_similarity)} ({df_similarity['peak_type_same'].sum()/len(df_similarity)*100:.1f}%)")
        
        self.results['activation_similarity'] = df_similarity
        return df_similarity
    
    def analyze_substitution_patterns(self) -> Dict:
        """
        Analyze how entity-specific features substitute between probes.
        
        Returns:
            Dictionary with substitution analysis
        """
        # Get entity-specific supernodes
        entity_nodes1 = self.df1[
            self.df1['supernode_name'].str.contains('Dallas|Texas|Austin', case=False, na=False)
        ]
        entity_nodes2 = self.df2[
            self.df2['supernode_name'].str.contains('Oakland|California|Sacramento', case=False, na=False)
        ]
        
        # Analyze by layer
        substitution_by_layer = []
        
        for layer in sorted(set(entity_nodes1['layer'].unique()) | set(entity_nodes2['layer'].unique())):
            e1_layer = entity_nodes1[entity_nodes1['layer'] == layer]
            e2_layer = entity_nodes2[entity_nodes2['layer'] == layer]
            
            substitution_by_layer.append({
                'layer': layer,
                f'{self.probe1_name}_entity_features': len(e1_layer),
                f'{self.probe2_name}_entity_features': len(e2_layer),
                f'{self.probe1_name}_supernodes': e1_layer['supernode_name'].nunique(),
                f'{self.probe2_name}_supernodes': e2_layer['supernode_name'].nunique()
            })
        
        df_substitution = pd.DataFrame(substitution_by_layer)
        
        print(f"\nEntity-Specific Feature Substitution:")
        print(f"  {self.probe1_name} entity features: {len(entity_nodes1)}")
        print(f"  {self.probe2_name} entity features: {len(entity_nodes2)}")
        
        return {
            'substitution_by_layer': df_substitution,
            'entity_features_probe1': entity_nodes1,
            'entity_features_probe2': entity_nodes2
        }
    
    def generate_paper_table(self) -> str:
        """Generate markdown table for paper (Table 3)."""
        df_transfer = self.results.get('supernode_transfer')
        if df_transfer is None:
            df_transfer = self.analyze_supernode_transfer()
        
        # Select key supernodes for the table
        key_supernodes = [
            # Universal concepts
            'is', 'capital', 'of', 'containing', '(containing) related', '(capital) related',
            # Entity-specific
            'Texas', 'California', 'Dallas', 'Oakland',
            # Output promotion
            'Say (Austin)', 'Say (Sacramento)', 'Say (capital)'
        ]
        
        table_rows = []
        table_rows.append("| Supernode | Category | Dallas Probe | Oakland Probe | Transfer Status |")
        table_rows.append("|-----------|----------|--------------|---------------|-----------------|")
        
        for sn in key_supernodes:
            row = df_transfer[df_transfer['supernode_name'] == sn]
            if len(row) == 0:
                continue
            row = row.iloc[0]
            
            p1_status = f"{row[f'{self.probe1_name}_n_features']} features" if row[f'{self.probe1_name}_present'] else "-"
            p2_status = f"{row[f'{self.probe2_name}_n_features']} features" if row[f'{self.probe2_name}_present'] else "-"
            
            # Emoji for transfer status
            status_emoji = {
                'Full transfer': '✓ Full transfer',
                'Appropriate non-transfer': '✓ Appropriate non-transfer',
                'Target-appropriate (single probe)': '✓ Target-appropriate',
                'Failed transfer': '✗ Failed',
                'Unexpected presence': '⚠ Unexpected'
            }
            status = status_emoji.get(row['transfer_status'], row['transfer_status'])
            
            table_rows.append(f"| {sn} | {row['category']} | {p1_status} | {p2_status} | {status} |")
        
        return "\n".join(table_rows)
    
    def visualize_results(self):
        """Generate all visualizations."""
        fig = plt.figure(figsize=(16, 12))
        gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.3)
        
        # 1. Layer overlap heatmap
        ax1 = fig.add_subplot(gs[0, :])
        self._plot_layer_overlap(ax1)
        
        # 2. Supernode presence matrix
        ax2 = fig.add_subplot(gs[1, 0])
        self._plot_supernode_presence(ax2)
        
        # 3. Activation similarity
        ax3 = fig.add_subplot(gs[1, 1])
        self._plot_activation_similarity(ax3)
        
        # 4. Transfer success by category
        ax4 = fig.add_subplot(gs[2, 0])
        self._plot_transfer_success(ax4)
        
        # 5. Entity substitution
        ax5 = fig.add_subplot(gs[2, 1])
        self._plot_entity_substitution(ax5)
        
        plt.savefig(
            self.output_dir / f'cross_prompt_robustness_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png',
            dpi=300, bbox_inches='tight'
        )
        print(f"\nVisualizations saved to {self.output_dir}")
        plt.close()
    
    def _plot_layer_overlap(self, ax):
        """Plot feature overlap by layer."""
        df = self.results['shared_features_analysis']['layer_overlap']
        
        x = df['layer']
        width = 0.35
        
        ax.bar(x - width/2, df[f'n_{self.probe1_name}'], width, label=self.probe1_name, alpha=0.8)
        ax.bar(x + width/2, df[f'n_{self.probe2_name}'], width, label=self.probe2_name, alpha=0.8)
        
        # Overlay overlap percentage
        ax2 = ax.twinx()
        ax2.plot(x, df['overlap_pct'], 'ro-', label='Overlap %', linewidth=2, markersize=6)
        ax2.set_ylabel('Overlap %', color='r')
        ax2.tick_params(axis='y', labelcolor='r')
        ax2.set_ylim([0, 100])
        
        ax.set_xlabel('Layer')
        ax.set_ylabel('Number of Features')
        ax.set_title('Feature Overlap by Layer')
        ax.legend(loc='upper left')
        ax2.legend(loc='upper right')
        ax.grid(True, alpha=0.3)
    
    def _plot_supernode_presence(self, ax):
        """Plot supernode presence matrix."""
        df = self.results['supernode_transfer']
        
        # Create presence matrix
        supernodes = df['supernode_name'].values
        presence_matrix = np.zeros((len(supernodes), 2))
        
        for i, sn in enumerate(supernodes):
            row = df[df['supernode_name'] == sn].iloc[0]
            presence_matrix[i, 0] = 1 if row[f'{self.probe1_name}_present'] else 0
            presence_matrix[i, 1] = 1 if row[f'{self.probe2_name}_present'] else 0
        
        sns.heatmap(presence_matrix, 
                    yticklabels=supernodes, 
                    xticklabels=[self.probe1_name, self.probe2_name],
                    cmap='RdYlGn', cbar_kws={'label': 'Present'},
                    linewidths=0.5, ax=ax, vmin=0, vmax=1)
        ax.set_title('Supernode Presence Matrix')
        ax.set_ylabel('')
    
    def _plot_activation_similarity(self, ax):
        """Plot activation similarity distribution."""
        df = self.results['activation_similarity']
        
        ax.hist(df['activation_max_rel_diff'], bins=30, alpha=0.7, edgecolor='black')
        ax.axvline(df['activation_max_rel_diff'].median(), color='r', 
                   linestyle='--', label=f'Median: {df["activation_max_rel_diff"].median():.3f}')
        ax.set_xlabel('Relative Activation Difference')
        ax.set_ylabel('Count (Shared Features)')
        ax.set_title('Activation Similarity for Shared Features')
        ax.legend()
        ax.grid(True, alpha=0.3)
    
    def _plot_transfer_success(self, ax):
        """Plot transfer success by category."""
        df = self.results['supernode_transfer']
        
        # Count by category and transfer status
        category_counts = df.groupby(['category', 'transfer_status']).size().unstack(fill_value=0)
        
        category_counts.plot(kind='bar', stacked=False, ax=ax, width=0.8)
        ax.set_xlabel('Category')
        ax.set_ylabel('Count')
        ax.set_title('Transfer Success by Supernode Category')
        ax.legend(title='Transfer Status', bbox_to_anchor=(1.05, 1), loc='upper left')
        ax.grid(True, alpha=0.3, axis='y')
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    def _plot_entity_substitution(self, ax):
        """Plot entity substitution patterns by layer."""
        df = self.results['substitution_patterns']['substitution_by_layer']
        
        x = df['layer']
        width = 0.35
        
        ax.bar(x - width/2, df[f'{self.probe1_name}_entity_features'], width, 
               label=self.probe1_name, alpha=0.8)
        ax.bar(x + width/2, df[f'{self.probe2_name}_entity_features'], width, 
               label=self.probe2_name, alpha=0.8)
        
        ax.set_xlabel('Layer')
        ax.set_ylabel('Number of Entity-Specific Features')
        ax.set_title('Entity-Specific Feature Distribution by Layer')
        ax.legend()
        ax.grid(True, alpha=0.3)
    
    def generate_report(self) -> str:
        """Generate comprehensive markdown report."""
        report = [
            "# Cross-Prompt Robustness Analysis Report",
            f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"\n## Probes Compared",
            f"- **Probe 1**: {self.probe1_name}",
            f"- **Probe 2**: {self.probe2_name}",
            "\n## Executive Summary\n"
        ]
        
        # Summary statistics
        shared_analysis = self.results['shared_features_analysis']
        transfer_df = self.results['supernode_transfer']
        
        report.append(f"### Feature-Level Statistics")
        report.append(f"- Total shared features: **{shared_analysis['n_shared']}**")
        report.append(f"- Grouping consistency rate: **{shared_analysis['consistency_rate']:.1f}%**")
        report.append(f"- Mean activation similarity: **{self.results['activation_similarity']['activation_max_rel_diff'].mean():.3f}**")
        
        report.append(f"\n### Supernode-Level Statistics")
        
        # Count transfer successes by category
        for category in ['universal', 'entity_specific', 'output_promotion']:
            cat_df = transfer_df[transfer_df['category'] == category]
            n_total = len(cat_df)
            # Count successful transfers based on category-appropriate outcomes
            if category == 'universal':
                n_success = len(cat_df[cat_df['transfer_status'] == 'Full transfer'])
            elif category == 'entity_specific':
                n_success = len(cat_df[cat_df['transfer_status'] == 'Appropriate non-transfer'])
            else:  # output_promotion
                n_success = len(cat_df[cat_df['transfer_status'].str.contains('Target-appropriate', na=False)])
            report.append(f"- **{category}**: {n_success}/{n_total} successful transfers")
        
        report.append("\n## Detailed Analysis\n")
        report.append("### Table 3: Cross-Prompt Transfer Results\n")
        report.append(self.generate_paper_table())
        
        report.append("\n### Feature Overlap by Layer\n")
        overlap_df = shared_analysis['layer_overlap']
        
        # Create markdown table manually
        cols = overlap_df.columns.tolist()
        report.append("| " + " | ".join(cols) + " |")
        report.append("|" + "|".join(["-" * (len(c)+2) for c in cols]) + "|")
        for _, row in overlap_df.iterrows():
            report.append("| " + " | ".join([str(row[c]) for c in cols]) + " |")
        
        report.append("\n## Interpretation\n")
        report.append(self._generate_interpretation())
        
        return "\n".join(report)
    
    def _generate_interpretation(self) -> str:
        """Generate interpretation of results."""
        interp = []
        
        shared_analysis = self.results['shared_features_analysis']
        consistency_rate = shared_analysis['consistency_rate']
        
        if consistency_rate > 80:
            interp.append("✓ **High grouping consistency** indicates robust concept discovery.")
        elif consistency_rate > 60:
            interp.append("⚠ **Moderate grouping consistency** suggests some concepts are probe-dependent.")
        else:
            interp.append("✗ **Low grouping consistency** indicates potential overfitting to specific probes.")
        
        # Check entity separation
        transfer_df = self.results['supernode_transfer']
        entity_df = transfer_df[transfer_df['category'] == 'entity_specific']
        
        appropriate_non_transfer = len(entity_df[entity_df['transfer_status'] == 'Appropriate non-transfer'])
        total_entity = len(entity_df)
        
        if appropriate_non_transfer / total_entity > 0.8:
            interp.append("\n✓ **Clean entity separation** - entity-specific supernodes correctly do not transfer.")
        else:
            interp.append("\n⚠ **Entity mixing detected** - some entity-specific features appear in both probes.")
        
        # Check universal transfer
        universal_df = transfer_df[transfer_df['category'] == 'universal']
        full_transfer = len(universal_df[universal_df['transfer_status'] == 'Full transfer'])
        total_universal = len(universal_df)
        
        if full_transfer / total_universal > 0.7:
            interp.append("\n✓ **Strong semantic transfer** - universal concepts consistently identified.")
        else:
            interp.append("\n⚠ **Weak semantic transfer** - universal concepts not consistently identified.")
        
        return "\n".join(interp)
    
    def run_full_analysis(self):
        """Run all analyses and generate outputs."""
        print("="*60)
        print("CROSS-PROMPT ROBUSTNESS ANALYSIS")
        print("="*60)
        
        # 1. Supernode transfer
        print("\n[1/5] Analyzing supernode transfer...")
        self.analyze_supernode_transfer()
        
        # 2. Shared features
        print("\n[2/5] Analyzing shared features...")
        self.results['shared_features_analysis'] = self.analyze_shared_features()
        
        # 3. Activation similarity
        print("\n[3/5] Analyzing activation similarity...")
        self.analyze_activation_similarity()
        
        # 4. Substitution patterns
        print("\n[4/5] Analyzing substitution patterns...")
        self.results['substitution_patterns'] = self.analyze_substitution_patterns()
        
        # 5. Generate outputs
        print("\n[5/5] Generating outputs...")
        
        # Save detailed results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save CSVs
        for key, df in self.results.items():
            if isinstance(df, pd.DataFrame):
                output_path = self.output_dir / f'{key}_{timestamp}.csv'
                df.to_csv(output_path, index=False)
                print(f"  Saved: {output_path}")
        
        # Generate and save report
        report = self.generate_report()
        report_path = self.output_dir / f'cross_prompt_report_{timestamp}.md'
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"  Saved: {report_path}")
        
        # Generate visualizations
        self.visualize_results()
        
        print("\n" + "="*60)
        print("ANALYSIS COMPLETE")
        print("="*60)
        
        return self.results


def main():
    """Run cross-prompt robustness analysis."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze cross-prompt robustness')
    parser.add_argument('--probe1-csv', required=True, help='Path to first probe CSV')
    parser.add_argument('--probe1-json', required=True, help='Path to first probe JSON summary')
    parser.add_argument('--probe1-name', required=True, help='Name for first probe')
    parser.add_argument('--probe2-csv', required=True, help='Path to second probe CSV')
    parser.add_argument('--probe2-json', required=True, help='Path to second probe JSON summary')
    parser.add_argument('--probe2-name', required=True, help='Name for second probe')
    parser.add_argument('--output-dir', default='output/validation', help='Output directory')
    
    args = parser.parse_args()
    
    analyzer = CrossPromptRobustnessAnalyzer(
        probe1_csv=args.probe1_csv,
        probe1_json=args.probe1_json,
        probe1_name=args.probe1_name,
        probe2_csv=args.probe2_csv,
        probe2_json=args.probe2_json,
        probe2_name=args.probe2_name,
        output_dir=args.output_dir
    )
    
    analyzer.run_full_analysis()


if __name__ == '__main__':
    main()

