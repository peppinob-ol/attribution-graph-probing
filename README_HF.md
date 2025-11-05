---
title: Attribution Graph Probing
emoji: 🔬
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
license: gpl-3.0
---

# 🔬 Attribution Graph Probing

**Automated Attribution Graph Analysis through Probe Prompting**

Interactive research tool for automated analysis and interpretation of attribution graphs from Sparse Autoencoders (SAE) and Cross-Layer Transcoders (CLT).

---

## 🚀 Quick Start

This Space implements a **3-stage pipeline** for analyzing neural network features:

1. **🌐 Graph Generation**: Generate attribution graphs on Neuronpedia
2. **🔍 Probe Prompts**: Analyze feature activations on semantic concepts  
3. **🔗 Node Grouping**: Automatically classify and name features

### Try the Demo

Click through the sidebar pages to explore the Dallas example dataset included in this Space.

---

## 🔑 API Keys Required

To use this Space with your own data, you need:

1. **Neuronpedia API Key** - Get it from [neuronpedia.org](https://www.neuronpedia.org)
2. **OpenAI API Key** - For concept generation (optional)

Add these as **Secrets** in Space Settings:
- `NEURONPEDIA_API_KEY=your-key-here`
- `OPENAI_API_KEY=your-key-here`

Or enter them directly in the sidebar when using the app.

---

## 📊 Features

### Stage 1: Graph Generation
- Generate attribution graphs via Neuronpedia API
- Extract static metrics (node influence, cumulative influence)
- Interactive visualizations (layer × context position)
- Select relevant features for analysis

### Stage 2: Probe Prompts
- Auto-generate semantic concepts via OpenAI
- Measure feature activations across concepts
- Automatic checkpoints for long analyses
- Resume from interruptions

### Stage 3: Node Grouping
- Classify features into 4 categories:
  - **Semantic (Dictionary)**: Specific tokens
  - **Semantic (Concept)**: Related concepts
  - **Say "X"**: Output predictions
  - **Relationship**: Entity relationships
- Automatic naming based on activation patterns
- Upload to Neuronpedia for visualization

---

## 📁 Example Dataset

This Space includes the **Dallas example**:
- **Prompt**: "The capital of state containing Dallas is"
- **Target**: "Austin"
- **Features**: 55 features from Gemma-2-2B model
- **Complete pipeline outputs**: Graph, activations, classifications

Navigate to each stage page to explore the example data.

---

## 📖 Documentation

- **Complete Guide**: See `eda/README.md` in the Files tab
- **Quick Start**: `QUICK_START_STREAMLIT.md`
- **Main README**: `readme.md`

---

## 🔬 Research Context

This tool is part of research on **automated sparse feature interpretation** using probe prompting techniques.

**Related Work:**
- [Circuit Tracer](https://github.com/safety-research/circuit-tracer) by Anthropic
- [Attribution Graphs](https://transformer-circuits.pub/2025/attribution-graphs/)
- [Neuronpedia](https://www.neuronpedia.org)

---

## 🛠️ Technical Details

**Models Supported:**
- Gemma-2-2B, Gemma-2-9B
- GPT-2 Small
- Any model with SAE/CLT features on Neuronpedia

**Resource Usage:**
- RAM: ~2-3GB for typical analyses
- CPU: Efficient for API-based processing
- Storage: Outputs saved during session

---

## 📝 How to Use

### With Example Data (No API Keys Needed)
1. Navigate through the 3 stage pages in the sidebar
2. Load the Dallas example files provided
3. Explore visualizations and results

### With Your Own Data (API Keys Required)
1. Add your API keys in Settings → Secrets or in the sidebar
2. **Stage 1**: Generate a new graph with your prompt
3. **Stage 2**: Generate concepts and analyze activations
4. **Stage 3**: Classify and name features automatically

---

## 🤝 Contributing

This is a research project for mechanistic interpretability. Feedback and contributions welcome!

---

## 📄 License

GPL-3.0 - See LICENSE file for details

---

**Version**: 2.0.0-clean  
**Last Updated**: November 2025  
**Deployed on**: Hugging Face Spaces

