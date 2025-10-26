# Figure Plan for LessWrong Post

This document maps each figure to its section in the blog post and provides detailed captions.

---

## Figure 1: Pipeline Overview Schematic

**Section:** Method: The Rewritten Pipeline (after Overview)

**Content:**
- Flowchart showing 5 stages:
  1. Concept Hypothesis Generation (Prompt Rover)
  2. Sensitivity Probing (dual protocol: label-only vs label+description)
  3. Behavioral Profiling (4 dimensions: signature, consistency, neighborhood, layer role)
  4. Supernode Construction (controlled expansion with coherence checks)
  5. Validation (interventions, baselines, cross-prompt)

**Caption:**
> **Figure 1: The ethnographic pipeline for attribution graph analysis.** Starting from a seed prompt, we generate concept hypotheses externally (Prompt Rover), probe active features for sensitivity to each concept, build behavioral profiles, construct supernodes via controlled expansion, and validate with interventions and baselines. Each stage produces falsifiable outputs that feed into the next.

**Source file:** Create new diagram or adapt from `figures/workflow_comparison.svg`

---

## Figure 2: Behavioral Archetypes Distribution

**Section:** Method: Stage 2 (after "Unexpected discovery")

**Content:**
- Bar chart or pie chart showing distribution of features across archetypes:
  - Semantic anchors: 127 features (14.3%)
  - Computational scaffolds: 748 features (84.0%)
  - Garbage features: 15 features (1.7%, filtered)
- Color-coded by archetype
- Annotate with example features for each type

**Caption:**
> **Figure 2: Feature behavioral archetypes.** Of 891 processable features, most serve computational roles (normalization, attention scaffolding), while 127 show high concept affinity and cross-prompt stability. Garbage features (BOS-peaking, layer-0 noise) are automatically filtered. This distribution suggests models organize computation into a small set of semantic anchors supported by larger computational infrastructure.

**Source file:** Could adapt from `figures/feature_taxonomy_diagram.svg` or create new

---

## Figure 3: Controlled Expansion Visualization

**Section:** Method: Stage 4 (after "Example expansion pattern")

**Content:**
- Layer-by-layer visualization showing how a seed feature expands:
  - Layer 4: Geographic entity (Dallas) - seed
  - Layer 7: Texas political references - first expansion
  - Layer 12: Southern U.S. cultural markers - second expansion
  - Layer 18: Output promotion (Texas-related tokens) - third expansion
  - Layer 23: "Say Austin" motor features - final expansion
- Show coherence scores at each step
- Highlight features that were rejected (below coherence threshold)

**Caption:**
> **Figure 3: Controlled expansion pattern for geographic entity supernode.** Starting from a Dallas-detecting feature in layer 4, the supernode systematically recruits related features across layers, maintaining semantic coherence (min 0.65) at each step. Features below threshold (shown in gray) are rejected, preventing over-expansion. This layer-wise progression suggests models organize computation into narrative chains: entity detection → relationship binding → output promotion.

**Source file:** Adapt from `figures/layered_expansion_visualization.svg` or `figures/controlled_expansion_coherence.svg`

---

## Figure 4: Baseline Comparison

**Section:** Validation: Validation 1 (after results table)

**Content:**
- Multi-panel comparison showing:
  - Panel A: Semantic coherence (bar chart)
  - Panel B: Cross-prompt stability (survival curves)
  - Panel C: Coverage vs. intervention predictiveness (scatter plot)
- Three methods: Ethnographic, Cosine-only, Adjacency-only
- Highlight trade-off: ethnographic sacrifices coverage for predictiveness

**Caption:**
> **Figure 4: Ethnographic supernodes outperform baselines on stability and intervention predictiveness.** (A) Semantic coherence within clusters. (B) Fraction of supernodes surviving on held-out prompts. (C) Trade-off between coverage (% features captured) and intervention predictiveness (correlation between predicted and actual steer effects). Ethnographic supernodes sacrifice some coverage but achieve dramatically better causal validation, confirming they capture functional structure rather than surface similarity.

**Source file:** Create new multi-panel figure from validation results

---

## Figure 5: Dallas → Austin Circuit Subgraph

**Section:** Results: Case Study (at beginning of "The Circuit")

**Content:**
- Attribution graph visualization showing:
  - Nodes: Supernodes (color-coded by layer and semantic role)
  - Edges: Attribution strength (thickness = influence)
  - Tokens: Annotated along bottom (Dallas, containing, state, capital, Austin)
  - Layers: Grouped vertically (4-7, 8-12, 13-18, 19-23)
- Highlight main path: Geographic Entity → Spatial Containment → US State → Capital Relationship → Say Austin

**Caption:**
> **Figure 5: Attribution graph for "The capital of the state containing Dallas is Austin."** Ethnographic supernodes (colored boxes) organize the circuit into interpretable narrative stages. Early layers detect entities (Dallas), middle layers bind relationships (spatial containment, state identity), and late layers promote the output (Austin). Edge thickness indicates attribution strength. This structure predicts intervention outcomes: ablating "Say Austin" shifts completion to Houston; steering "Geographic Entity" strengthens all Texas-related outputs.

**Source file:** Adapt from `figures/improved_supernode_visualization.svg` or create new from `output/visualization_graph_data.json`

---

## Figure 6: Intervention Results

**Section:** Results: Intervention Validation (after each example)

**Content:**
- Three-panel figure showing logit changes:
  - Panel A: Steer Geographic-Dallas (+2.0)
    - Bar chart: Austin (12.3 → 14.1), Houston (8.7 → 10.2), Dallas (7.2 → 8.9)
  - Panel B: Ablate State-Capital-Austin
    - Bar chart: Austin (12.3 → 6.1), Houston (7.8 → 9.8), Dallas (6.5 → 7.2)
  - Panel C: Steer Spatial-Containment (+1.5)
    - Bar chart: Austin (12.3 → 13.7), alternatives suppressed
- Show predicted vs. actual effects with error bars

**Caption:**
> **Figure 6: Intervention validation confirms ethnographic supernodes predict causal effects.** (A) Steering geographic entity features increases all Texas-related outputs, as predicted. (B) Ablating output promotion shifts completion to alternative Texas city (Houston), confirming causal role. (C) Steering spatial relationship strengthens state-city binding, increasing output confidence. Error bars show variation across 5 runs. 76% of interventions matched predictions (14/18), vs. 34% for baseline supernodes (6/18).

**Source file:** Create new from intervention logs in `output/`

---

## Figure 7: Cross-Prompt Stability

**Section:** Validation: Validation 3 (after results)

**Content:**
- Heatmap or survival plot showing:
  - Rows: 54 ethnographic supernodes
  - Columns: 4 test prompts (Houston variant, reordered syntax, direct question, paraphrase)
  - Color: Survival (green = survived, red = failed)
- Compare to baseline methods (separate panels or overlaid)
- Annotate failure modes for baselines

**Caption:**
> **Figure 7: Ethnographic supernodes maintain 100% stability across prompt variations.** All 54 supernodes survive on held-out prompts within the same domain (different city, reordered syntax, direct question, paraphrase). Baselines show 45-52% stability, fragmenting when entity changes (cosine-only) or graph topology shifts (adjacency-only). This robustness suggests ethnographic supernodes capture behavioral signatures that generalize beyond surface features.

**Source file:** Create new from cross-prompt validation results in `output/STEP2_PEAK_CONSISTENCY.csv`

---

## Figure 8: Failure Mode Analysis

**Section:** Validation: Validation 4 (after "Failure modes observed")

**Content:**
- Multi-panel showing common failure modes:
  - Panel A: Error node dominance (pie chart showing attribution distribution)
  - Panel B: Polysemantic artifacts (example feature activating on unrelated concepts)
  - Panel C: Over-expansion prevented by thresholds (graph showing rejected features)
- Annotate mitigation strategies

**Caption:**
> **Figure 8: Common failure modes and mitigation strategies.** (A) When error nodes carry >40% attribution (23% of graphs), supernode construction becomes unreliable; we filter these before analysis. (B) Polysemantic features respond to multiple unrelated concepts (12% of features); current method flags but doesn't resolve these. (C) Without coherence thresholds, expansion captures spuriously correlated features (gray nodes); thresholds prevent over-expansion while maintaining coverage. These limitations are documented, not solved.

**Source file:** Create new from error analysis in `output/STEP2_REVIEW_GATE_B_FINAL.md`

---

## Optional Figure 9: Comparison to Manual Analysis

**Section:** Discussion (optional, if space permits)

**Content:**
- Side-by-side comparison:
  - Left: Manual supernode creation (Anthropic case study style)
  - Right: Ethnographic pipeline output
- Show overlap, differences, time required
- Highlight where automation agrees/disagrees with expert

**Caption:**
> **Figure 9: Ethnographic pipeline output compared to manual analysis.** When applied to the same prompt, automated ethnographic supernodes show 78% overlap with expert-created supernodes (Anthropic case study), but identify 3 additional relationships missed by manual analysis and flag 2 spurious groupings. Time required: 2 hours (manual) vs. 15 minutes (automated + validation). This suggests automation can augment rather than replace expert analysis.

**Source file:** Would need to create from comparison study (not yet done)

---

## Figure File Mapping

Map existing figures in `figures/` to sections:

- `activation_density_patterns.svg` → Could support Stage 2 (behavioral profiling)
- `concept_category_analysis.svg` → Could support Stage 1 (concept hypotheses)
- `controlled_expansion_coherence.svg` → **Use for Figure 3**
- `cosine_similarity_by_layer.svg` → Could support baseline comparison
- `feature_taxonomy_diagram.svg` → **Use for Figure 2**
- `improved_supernode_visualization.svg` → **Use for Figure 5**
- `layered_expansion_visualization.svg` → Alternative for Figure 3
- `layer_distribution.svg` → Could support behavioral profiling
- `peak_token_analysis.svg` → Could support Stage 2
- `validation_summary.svg` → Could support Validation section intro
- `workflow_comparison.svg` → **Use for Figure 1**
- `zscore_distribution.svg` → Could support Stage 2 metrics

---

## New Figures to Create

1. **Figure 4: Baseline Comparison** (multi-panel)
   - Source: Validation results from `output/STEP2_PATTERN_ANALYSIS.md`
   - Tool: matplotlib or seaborn

2. **Figure 6: Intervention Results** (three-panel bar charts)
   - Source: Intervention logs from `scripts/causal_utils.py` output
   - Tool: matplotlib

3. **Figure 7: Cross-Prompt Stability** (heatmap or survival plot)
   - Source: `output/STEP2_PEAK_CONSISTENCY.csv`
   - Tool: seaborn heatmap or survival curve

4. **Figure 8: Failure Mode Analysis** (multi-panel)
   - Source: Error analysis from `output/STEP2_REVIEW_GATE_B_FINAL.md`
   - Tool: matplotlib

---

## Figure Checklist

- [ ] Figure 1: Pipeline schematic (adapt `workflow_comparison.svg`)
- [ ] Figure 2: Behavioral archetypes (adapt `feature_taxonomy_diagram.svg`)
- [ ] Figure 3: Controlled expansion (use `controlled_expansion_coherence.svg`)
- [ ] Figure 4: Baseline comparison (create new)
- [ ] Figure 5: Dallas→Austin subgraph (use `improved_supernode_visualization.svg`)
- [ ] Figure 6: Intervention results (create new)
- [ ] Figure 7: Cross-prompt stability (create new)
- [ ] Figure 8: Failure modes (create new)
- [ ] Figure 9: Manual comparison (optional, create if time permits)

---

## Caption Style Guide

Following your writing style from "On the Geometrical Nature of Insight":

- Start with bold figure number and title
- First sentence: What the figure shows (descriptive)
- Second sentence: Why it matters (interpretive)
- Third sentence (if needed): Technical details or caveats
- Keep captions self-contained but concise (3-5 sentences max)
- Use active voice ("This suggests..." not "It is suggested that...")
- Avoid jargon in captions; define terms inline if necessary

---

## Implementation Notes

Most existing figures in `figures/` are SVG format, which is ideal for LessWrong (scalable, web-friendly). New figures should also be SVG or high-res PNG.

For reproducibility, include figure generation scripts in `scripts/visualization/` that can regenerate all figures from output data.

