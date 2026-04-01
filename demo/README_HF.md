---
title: Concept Swap Explorer
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
license: gpl-3.0
---

# Concept Swap Explorer -- Cross-Domain Circuit Steering

Interactive visualization of circuit steering experiments across 5 knowledge domains. Explore how feature-level interventions on attribution-graph circuits redirect model outputs from one concept to another.

---

## Domains

| Domain | Entities | Prompt pattern | Runs |
|--------|----------|----------------|------|
| **USA States** | 50 states | "The capital of the state containing [City] is..." | 4 |
| **Book Characters & Authors** | 16 characters | "The author of [Character] is..." | 4 |
| **Paintings & Painters** | 10 paintings | "The painter of [Painting] is..." | 4 |
| **Products & Founders** | 12 products | "The founder of [Product] is..." | 4 |
| **Sounds & Colors** | 6 synesthetic pairs | "The color of the sound of a [Sound] is..." | 4 |

Use the **Run** dropdown in the header to switch between domains and experiment types (labeled swaps, random-feature controls, field-add controls).

---

## What This Shows

For each domain the demo visualizes experiments where we:
1. Trace the attribution-graph circuit a language model uses to answer a factual prompt
2. Use **Probe Prompting** to identify concept-related CLT features and group them into supernodes
3. Swap source features out (ablate) while amplifying target features, then measure how the model's output changes

### The Steering Matrix

Each cell shows the result of swapping a source entity's circuit into a target entity's context:

| Tier | Result | Meaning |
|------|--------|---------|
| **T5** | PERFECT | Model outputs the target answer |
| **T4** | Partial + Answer | Target-domain content with the correct answer entity |
| **T3** | Partial | Target-domain content without the exact answer |
| **W** | Wrong Answer | Neither source nor target answer |
| **T2** | Suppressed | Source suppressed, no target content |
| **T1** | Source Persists | Source answer still appears in output |

### Click Any Cell

See detailed results including:
- Default vs steered model outputs
- Token probability changes
- Logit-flip trajectory (when available)
- Links to Neuronpedia circuit visualizations

### Experiment Types

Each domain includes multiple run types:
- **Labeled** -- swap matched supernodes between source and target circuits
- **Random** -- swap the same number of randomly chosen features (control)
- **Field-add** -- inject only target features without ablating source (control)

---

## Related Research

- [Automated Circuit Interpretation via Probe Prompting (arXiv)](https://arxiv.org/abs/2511.07002)
- [LessWrong discussion](https://www.lesswrong.com/posts/zQqGhKPqaCBZZDCge)
- [GitHub repository](https://github.com/peppinob-ol/attribution-graph-probing)
- [Circuit Tracer](https://github.com/safety-research/circuit-tracer)
- [Attribution Graphs (Anthropic)](https://transformer-circuits.pub/2025/attribution-graphs/)
- [Neuronpedia](https://www.neuronpedia.org)

---

## Data

This Space visualizes 33,387 steering runs across 5 domains and 3 experimental conditions (labeled, random-control, field-add-control), all performed on **Gemma-2-2B** with Cross-Layer Transcoders.

---

**Version**: 2.0.0
**Model**: Gemma-2-2B
**License**: GPL-3.0



