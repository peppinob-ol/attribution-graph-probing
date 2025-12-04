---
title: State Swap Explorer
emoji: 🗺️
colorFrom: green
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
license: gpl-3.0
---

# State Swap Explorer

**Interactive visualization of circuit steering experiments across US states**

Explore how knowledge circuits can be steered to change model predictions about US state capitals.

---

## What This Shows

This demo visualizes experiments where we:
1. Identify the "circuit" a language model uses to answer "The capital of the state containing [City] is..."
2. Swap circuits between states (e.g., replace Texas circuit with California circuit)
3. Measure how well the model now predicts the target state's capital

### The 50x50 Matrix

Each cell shows the result of swapping the source state's circuit into the target state's context:

| Tier | Result | Meaning |
|------|--------|---------|
| **T5** (Green) | PERFECT | Model outputs target capital (e.g., "Sacramento") |
| **T4** (Lime) | State + City | Model outputs a city in target state |
| **T3** (Yellow) | State Only | Model mentions target state |
| **T2** (Orange) | Suppressed | Source suppressed, no target content |
| **T1** (Red) | Failed | Source capital still appears |

### Click Any Cell

See detailed results including:
- Default vs steered model outputs
- Token probability changes
- Links to Neuronpedia circuit visualizations

---

## Related Research

- **Analysis Pipeline**: See the companion [Attribution Graph Probing](link-to-eda-space) Space for running your own analysis
- [Circuit Tracer](https://github.com/safety-research/circuit-tracer) by Anthropic
- [Attribution Graphs](https://transformer-circuits.pub/2025/attribution-graphs/)
- [Neuronpedia](https://www.neuronpedia.org)

---

## Data

This visualization shows results from 2,450 swap experiments (50 source states x 49 target states) using the Gemma-2-2B model with Cross-Layer Transcoders.

---

**Version**: 1.0.0  
**Model**: Gemma-2-2B  
**License**: GPL-3.0



