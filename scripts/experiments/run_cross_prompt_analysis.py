"""
Quick runner for cross-prompt robustness analysis.

Analyzes Dallas vs Oakland probes.
"""

from pathlib import Path
from analyze_cross_prompt_robustness import CrossPromptRobustnessAnalyzer

# File paths
BASE_DIR = Path(__file__).parent.parent.parent
OUTPUT_DIR = BASE_DIR / "output"

# Dallas probe (Texas capital)
DALLAS_CSV = OUTPUT_DIR / "examples/Dallas/node_grouping_final_20251027_173744.csv"
DALLAS_JSON = OUTPUT_DIR / "examples/Dallas/node_grouping_summary_20251027_173749.json"

# Oakland probe (California capital)
OAKLAND_CSV = OUTPUT_DIR / "examples/capital oakland/node_grouping_final_20251027_180941.csv"
OAKLAND_JSON = OUTPUT_DIR / "examples/capital oakland/node_grouping_summary_20251027_180951.json"

# Output directory
VALIDATION_DIR = OUTPUT_DIR / "validation"

def main():
    """Run the analysis."""
    print("Cross-Prompt Robustness Analysis")
    print("="*60)
    print(f"Comparing:")
    print(f"  - Dallas -> Austin (Texas)")
    print(f"  - Oakland -> Sacramento (California)")
    print("="*60)
    
    # Check files exist
    for name, path in [
        ("Dallas CSV", DALLAS_CSV),
        ("Dallas JSON", DALLAS_JSON),
        ("Oakland CSV", OAKLAND_CSV),
        ("Oakland JSON", OAKLAND_JSON)
    ]:
        if not path.exists():
            print(f"ERROR: {name} not found at {path}")
            return
        print(f"Found: {path.name}")
    
    print()
    
    # Run analysis
    analyzer = CrossPromptRobustnessAnalyzer(
        probe1_csv=str(DALLAS_CSV),
        probe1_json=str(DALLAS_JSON),
        probe1_name="Dallas",
        probe2_csv=str(OAKLAND_CSV),
        probe2_json=str(OAKLAND_JSON),
        probe2_name="Oakland",
        output_dir=str(VALIDATION_DIR)
    )
    
    results = analyzer.run_full_analysis()
    
    print("\nKey Findings:")
    print("-" * 60)
    
    # Print key metrics
    shared = results['shared_features_analysis']
    print(f"Feature Overlap: {shared['n_shared']}/{len(analyzer.df1)} ({shared['n_shared']/len(analyzer.df1)*100:.1f}%)")
    print(f"Grouping Consistency: {shared['consistency_rate']:.1f}%")
    
    sim = results['activation_similarity']
    print(f"Mean Activation Similarity: {1 - sim['activation_max_rel_diff'].mean():.3f}")
    
    transfer = results['supernode_transfer']
    
    # Universal concepts
    universal = transfer[transfer['category'] == 'universal']
    n_universal_success = len(universal[universal['transfer_status'] == 'Full transfer'])
    print(f"Universal Concept Transfer: {n_universal_success}/{len(universal)} ({n_universal_success/len(universal)*100:.0f}%)")
    
    # Entity-specific
    entity = transfer[transfer['category'] == 'entity_specific']
    n_entity_success = len(entity[entity['transfer_status'] == 'Appropriate non-transfer'])
    print(f"Entity Separation: {n_entity_success}/{len(entity)} ({n_entity_success/len(entity)*100:.0f}%)")
    
    print("\n" + "="*60)
    print(f"Results saved to: {VALIDATION_DIR}")
    print("="*60)

if __name__ == '__main__':
    main()

