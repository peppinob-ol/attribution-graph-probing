LESSWRONG
Automated Circuit Interpretation via Probe Prompting
32 min read
•
Contributions
•
Motivation
•
Method
•
1 Attribution Graph
•
1.1 Attribution Graph Generation
•
1.2 Filtering node subset
•
2 Probe prompts
•
2.1 Concept Hypothesis Generation
•
2.2 Probe Prompt Activations
•
2.3. Cross-Prompt Activation Signatures
•
3. Concept-Aligned Grouping
•
3.1  Target token preprocessing
•
3.2 Node type classification
•
3.3 Concept Aligned Naming
•
4. Subgraph Construction
•
Validation Strategy
•
Neuronpedia Graph Metrics
•
Baseline Comparisons
•
Cross-Prompt Robustness
•
Cross-Lingual Limitation
•
Case Study: “The Capital of the State Containing Dallas”
•
Experimental Setup
•
Probe Prompting
•
Concept-Aligned Grouping
•
Supernode Interpretation
•
Subgraph Construction and Validation
•
5.5 Cross-Prompt Robustness
•
Planned Extensions: Scale Evaluation and Causal Interventions
•
Limitations and Open Questions
•
Current Limitations
•
What Would Change My Mind
•
Open Questions for Future Work
•
Disclaimer
+
Interpretability (ML & AI)
Language Models (LLMs)
Sparse Autoencoders (SAEs)
AI
Frontpage
10
Automated Circuit Interpretation via Probe Prompting
by Giuseppe Birardi
1st Nov 2025

Browse auto-genearted subgraphs on Neuronpedia: 
Dallas-Austin | Oakland Sacramento | Michael Jordan-Basketball
 Small-Opposite | Petit-Contraire | Muscle-Diaprhagm
Summary: Attribution graphs reveal which features contribute to model outputs, but interpreting these features remains bottlenecked by manual analysis. I present an automated probe-prompting pipeline that extracts concept-aligned supernodes with minimal supervision. Features are measured against targeted, concept-varying prompts, grouped by behavioral signatures, and validated with Neuronpedia’s Replacement and Completeness metrics. On two classic “capitals” circuits, subgraphs average 0.53 Replacement and 0.83 Completeness, outperforming geometric clustering on interpretability metrics; entity-swap tests suggest an early-layer/late-layer split in what generalizes.
Demo: https://huggingface.co/spaces/Peppinob/attribution-graph-probing
Repo: https://github.com/peppinob-ol/attribution-graph-probing
 

Epistemic Status: medium confidence in the current pipeline on small model highly sparse transcoder (Gemma-2-2B/clt-hp), with short factual prompts; low confidence in broad generalization to long chain-of-thought reasoning, adversarial prompts, or larger models without adaptation. Validation currently relies on Neuronpedia's graph metrics and cross-prompt stability; causal interventions (steering/ablation experiments) and extensive prompt validations are planned but not yet implemented.

 

Contributions
Automated probe-prompting for attribution graphs. We present an end-to-end pipeline that (a) defines concept-targeted but context-varying probe prompts, (b) measures feature responses across probes, and (c) groups features by behavioral signatures into concept-aligned supernodes. Human input is limited to vetting the concept set; measurement, grouping, and subgraph construction are automated and reproducible (fixed configs, seeds, and logging).
Quantitative validation with Neuronpedia metrics, plus baselines. On two classic “capitals” circuits, our concept-aligned subgraphs attain ~0.53 Replacement and ~0.83 Completeness on Neuronpedia metrics, averaged across runs, and outperform geometric clustering on behavior-based interpretability metrics. We also document the expected trade-off: geometric clusters can be more compact (e.g., higher silhouette) yet less behaviorally coherent.
Cross-prompt stability and a layerwise hierarchy. Entity-swap studies indicate ~64% feature transfer between structurally similar prompts, with a clear hierarchy: early-layer features generalize strongly (~80–92% overlap), while late-layer features are more context-specific (~0–50%). This suggests a stable backbone of early abstractions supporting more specific late-stage computations.
Making polysemantic features legible. By profiling responses to carefully designed probes, the pipeline yields usable labels for common polysemantic types (e.g., “Say X”, “(token)-related”, relational features). These labels often agree with autointerp on monosemantic nodes and add structure where autointerp is generic, improving the readability of supernodes without manual corpus trawling.
Open resources and reproducible pipeline. I release a public demo and code repo with evaluation scripts for cross-prompt robustness and baseline comparisons; Neuronpedia metrics are fetched via the Neuronpedia API. The demo is mostly push-button, with one brief external Colab step (upload two files and run a cell). A single config emits per-graph reports (label coverage, robustness, Neuronpedia scores).
Planned scaling and causal tests. To demonstrate automation at scale, we will run a templated sweep over all US state–capital graphs (then all countries) and report per-graph and aggregate Neuronpedia metrics (Replacement/Completeness), label coverage, and cross-prompt stability. We will also run three causal interventions—feature ablations, steering, and cross-circuit transfers—and report logit deltas alongside Neuronpedia metrics before and after intervention.
Scope and limitations.
Current evidence is on Gemma-2-2B CLT-HP with short factual prompts. We are not claiming immediate generalization to long chain-of-thought, adversarial settings, or larger models without adaptation, and we do not yet model attention routing explicitly. These boundaries are stated to focus the empirical claims and guide the planned extensions above.
 

Motivation
Attribution graphs, introduced by the Anthropic team, rely on Cross-Layer Transcoders (CLTs) replacement models[1] to produce interpretable graphs of the features engaged during inference for a given logit. Starting from an input prompt and a selected target logit, the process generates a graph whose nodes represent the activation of CLT features across layers contributing to that output. CLT features are highly sparse and often monosemantic, enabling a causal interpretation of the model’s decision-making process.  

In practice, the current workflow demands a lot of manual interpretation. Human analysis involves starting from the final logit, identifying the most influential nodes, and inspecting their strongest activations over the training corpus to infer their semantic role. This approach is partially supported by autointerp methods such as those available on the Neuronpedia platform. Given the large number of nodes involved, users must manually select and group the most interpretable ones into supernodes. The resulting subgraph offers a more tractable, high-level view of the causal path from embeddings to the final logit. Current workflow require researchers to:

manually inspect feature activations across many examples;
intuitively group features that appear to play similar roles;
iteratively refine these groupings through trial and error.
As noted in Neuronpedia youtube podcast, analyzing a single prompt takes "~2 hours for an experienced circuit tracer." This manual interpretation doesn't scale. I wanted a workflow that:

proposes concepts to test rather than assuming them,
measures alignment between features and concepts directly,
groups by measured behavior, not presumed similarity,
validates groups with simple, reproducible metrics.
This project grew out of two experiences: months of black‑box concept exploration (both theoretical and practical) and a very hands‑on, manual pass over the classic “The capital of the state containing Dallas is Austin” graph. In the first experiment I literally printed activations and annotated them by hand over several days, until formulating an alternative hypothesis: that attribution graphs can be probed using conceptually aligned but contextually varied prompts.

This approach can be visualized metaphorically as projecting multiple lights onto a single complex object: each light (probe prompt) reveals a different shadow (activation pattern), and by comparing these shadows, one can reconstruct the object’s underlying structure—the main conceptual components shaping the model’s reasoning.

 
Method

The experimental method consists of three main stages. First, the attribution graph is generated via Anthropic’s open-source Circuit Tracing library, mediated by Neuronpedia’s API, selecting a subset of nodes according to a defined Cumulative Influence Threshold. Second, a set of representative probe prompts is generated to isolate and characterize semantic concepts, and their feature activations are measured using Neuronpedia’s feature activation for text​ method. Third, a feature-engineering stage classifies each feature according to its role within the graph through heuristic thresholds on cross-prompt behavioral signatures, grouping features with matching semantic labels into supernodes. Fourth, the resulting supernode subgraph is then visualized within Neuronpedia to support interpretable causal analysis of model behavior. We dive into relevant sub-steps:

 

1 Attribution Graph
1.1 Attribution Graph Generation
The attribution graph is generated via Anthropic’s open-source Circuit Tracing library, mediated by Neuronpedia’s API. Attribution graph JSON represents causal computation flow from input tokens → features → target logit, with influence scores measuring each feature’s contribution to the prediction.

Component	Content	Description
Metadata	prompt_tokens, model, transcoder_set	Prompt, model ID, SAE configuration
Nodes	[{node_id, layer, feature, ctx_idx, activation, influence}]	Features (4,000-6,000 after pruning) with layer position, activation strength over each token, and influence score
Links	[{source, target, weight}]	Directed edges showing attribution flow between features
Thresholds	node_threshold: 0.8, edge_threshold: 0.85	Pruning parameters for graph sparsification
 

1.2 Filtering node subset 

The classic Cumulative Influence Threshold used in Circuit Tracing paper is used here to choose the subset of nodes to interpretate. The streamlit interface offers convenient visual feedback of influence of single nodes and numeric indicators to choose a convenient threshold.

 

2 Probe prompts
2.1 Concept Hypothesis Generation
From the seed prompt, an instructed language model can generate candidate concepts with short labels and contextual descriptions. For example, given:

Seed prompt: “The capital of the state containing Dallas is Austin”

the language model extract concepts such as:

Dallas (entity): A major city in Texas, USA
Texas (entity): A state in the southwestern United States
capital (relationship): The primary administrative city of a political region
containing (relationship): Geographic containment relationship
Austin (entity): The capital city of Texas
These concepts become testable hypotheses about what different features in the circuit might represent.

 

2.2 Probe Prompt Activations
For each accepted concept, we create probe prompts that maintain syntactic structure while varying semantic content:

Example probe prompt:

entity: A city in Texas, USA is Dallas.

This prompt:

follows the same syntactic template as the seed prompt
Places the concept token in a semantically appropriate context
includes the same functional tokens (e.g., “is”) to maintain positional structure
Feature activations over probe prompts are measured using Neuronpedia API’s feature activation for text​ method. I recreated it with a batch logic in a colab notebook environment to avoid API rate limits[2]. 

 

2.3. Cross-Prompt Activation Signatures

Feature 20-clt-hp:74108 (Say "Capital"): Activates on functional "is" across diverse semantic contexts. Consistent peak before output targets indicates procedural output promotion role, not semantic detection. Max peak token (63.31) before "capital".
For each feature, we measure how its activation pattern changes across probe prompts. This creates a behavioral signature that distinguishes functionally different features even when they have similar decoder vectors. For each feature × concept pair, we compute:

Per-probe metrics (computed on each individual probe prompt):

Cosine similarity: how similar is the feature’s activation pattern on the probe prompt to its pattern on the original prompt.
Robust z-score (IQR-based): how much does activation deviate from baseline, using outlier-resistant statistics.
Peak token: which token has maximum activation (excluding BOS).
Activation density: what fraction of tokens exceed the activation threshold (75th percentile).
Sparsity ratio: (peak_activation - mean_activation) / peak_activation—measures concentration
High sparsity (~1.0): Feature activates sharply on one token
Low sparsity (~0): Feature activates diffusely across many tokens
Aggregated cross-probe metrics (computed across all probes for a feature):

Peak consistency: across all probe prompts containing a concept, how often does the peak fall on the concept token.
Number of distinct peaks: how many different token types does the feature peak on across probes.
Functional vs. Semantic percentage: what percentage of probe prompts does the feature peak on functional tokens (e.g., “is”, “the”) vs. semantic tokens (e.g., “Dallas”, “capital”).
Semantic confidence: peak_consistency when the feature peaks on semantic tokens
Functional confidence: peak_consistency when the feature peaks on functional tokens
These metrics compare the same feature across different prompts. A feature that consistently peaks on “Dallas” tokens across varied contexts (high peak_consistency, low n_distinct_peaks) behaves differently from one that peaks on different tokens depending on context—even if both have high activation on some “Dallas” token in the original prompt.

Example: Consider two features that both activate strongly on “Dallas” in the original prompt:

Feature A: In probe prompts, peaks on “Dallas” (90% of time), “Houston” (5%), “Texas” (5%) → peak_consistency = 0.90, n_distinct_peaks = 3, semantic_confidence = 0.90
Feature B: In probe prompts, peaks on “Dallas” (40%), “is” (30%), “city” (20%), “state” (10%) → peak_consistency = 0.40, n_distinct_peaks = 4, mixed behavior
Feature A is a stable “Dallas detector,” while Feature B is context-dependent and polysemantic. The aggregated cross-probe metrics reveal this distinction.

 

 

3. Concept-Aligned Grouping
Features are grouped into supernodes by a 3 stage process: target token preprocessing, node type classification, and node naming. 

3.1  Target token preprocessing
Before classification, all tokens in probe prompts are preprocessed into two categories:

Semantic tokens: Content-bearing words with specific meaning (e.g., “Texas”, “capital”, “Austin”)
Functional tokens: Low-specificity words serving as “semantic bridges” (e.g., “is”, “the”, punctuation). These have usually low embedding magnitude[3] but accumulate contextual meaning from adjacent semantic tokens.
For each feature that peaks on a functional token, we identify the target token—the nearest semantic token within a ±5 token window (configurable). Direction is determined by a predefined functional token dictionary:

"is" → forward (e.g., “is Austin”)
"," → bidirectional (e.g., “Texas,” or “, USA”)
"the" → forward (e.g., “the capital”)
Caveat: Some early-layer features (layer ≤3) detect functional tokens themselves (e.g., context-independent “is” detectors). These are later classified as semantic despite the token type.

Purpose: Target tokens enable interpretable naming of Say X nodes. A feature peaking on “is” before “Austin” across contexts becomes “Say (Austin)”, linking functional behavior to semantic content it promotes.

 

3.2 Node type classification

Node type classification is obtained applying transparent, testable thresholds to the aggregated cross-probe metrics defined in section 3. These thresholds were tuned on held-out examples and are designed to capture distinct functional roles:

Dictionary/Semantic nodes (entity detectors, e.g., “Dallas”):

peak_consistency ≥ 0.80: When the concept token appears in a probe, it must be the activation peak ≥80% of the time
n_distinct_peaks ≤ 1: Feature should peak consistently on the same token type (not scatter across multiple tokens)
layer ≤ 3 OR semantic_confidence ≥ 0.50: Early layers where token detection occurs, OR high confidence in semantic behavior
Relationship nodes (spatial/abstract relations, e.g., “containing”):

sparsity < 0.45: Relationship features activate diffusely across relation phrases (median sparsity ratio across probes < 0.45)
Typically found in layers 0-3 where early binding operations occur
Often polysemantic until disambiguated by attention—hence lower peak consistency
Say X nodes (output promotion, e.g., “Say Austin”):

func_vs_sem ≥ 50%: Feature peaks on functional tokens (e.g., “is”, “the”) in ≥50% of probe prompts, indicating functional rather than semantic role
confidence_functional ≥ 0.90: High peak consistency when peaking on functional tokens
layer ≥ 7: Output promotion occurs in mid-to-late layers
Cross-prompt stability (applied to all groups):

Supernode features must activate consistently. Entity swaps show partial transfer (64%), though paraphrases and structural variations remain untested.
Peak tokens shift appropriately (e.g., Dallas→Houston when the city changes)
Duplicate prevention: each feature belongs to at most one supernode; conflicts are resolved by highest alignment score (computed as weighted combination of peak_consistency, semantic_confidence, and layer appropriateness).

 

3.3 Concept Aligned Naming
After classification, features receive interpretable names based on their functional role. The naming system applies distinct strategies per node type:

Node Type	Source	Selection Criterion	Format	Example
Semantic	Peak token (max activation)	Highest activation_max on semantic tokens	"token"	"Texas"
Say X	Target token (preprocessing)	Nearest semantic target from functional peak 	"Say (token)"	"Say (Austin)"
Relationship	Aggregated semantic tokens (all probes)	Highest aggregated activation on extended vocabulary	"(token) related"	"(containing) related"
Semantic nodes are named by selecting the semantic token where they activate most strongly. The system filters records where features peak on semantic tokens, sorts by activation strength, and selects the highest-activation token not in a user-configurable blacklist. For example, a feature that consistently peaks on “Texas” receives the name "Texas". If no semantic peaks are found, the system falls back to the token position from the original prompt.

Say X nodes are named by identifying the target semantic token they predict or promote. Since these features peak on functional tokens (like “is” or “the”), the naming uses the target tokens discovered during preprocessing.  The final format is "Say (token)", such as "Say (Austin)" for a feature peaking on “is” before “Austin”.

Relationship nodes are named through a two-staged process. The system constructs an extended semantic vocabulary combining tokens from the original prompt with concept names discovered during Semantic node classification. It then aggregates activation values for each semantic token across all probes and selects the highest-activation token (excluding blacklisted entries). The format is "(token) related", producing names like "(containing) related" for features that activate diffusely on spatial relationship phrases.

Blacklist system: A user-configurable set of generic tokens (e.g., {“entity”, “attribute”}) enables filtering uninformative words. 

 

4. Subgraph Construction
Once concept-aligned supernodes are defined, we construct interpretable subgraphs by (1) pinning features grouped by supernode name, (2) pinning corresponding token embedding nodes when semantic supernodes exist, and (3) pinning the output logit to complete the circuit from input to prediction.

These subgraphs are uploaded to Neuronpedia for metric computation (Replacement/ Completeness scores) and interactive analysis. Researchers can navigate the subgraph to examine individual feature attributions and compare against three baselines: the raw pruned graph, feature-specific activation patterns, and autointerp labels.

 

Empirical finding: the heuristic naming system often converges with Neuronpedia autointerp labels for monosemantic features, but often reveals complementary insights for polysemantic "Relationship" and "Say X" features. For example, in Dallas-Austin graph feature 1_12928 receives the generic autointerp label "AssemblyCulture" but our system labels it "(texas) related".

Examining its full top activations in Neuronpedia reveals an official Texas government document containing both "Texas" and "Austin" (the state capital, output logit of the seed prompt), grounding the interpretation in specific corpus content. This suggests probe-based concept alignment can serve as both hypothesis generation and validation for mechanistic interpretability.


Feature 1_12928 top activation
Texas government document containing "Texas" and "Austin" (dark green = high activation). Validates probe-based label "(texas) related" vs. autointerp's "AssemblyCulture."
Validation Strategy
Due to the early stage of development of the method, validation is designed to be simple and reproducible without requiring causal interventions (though we plan to add those).

Neuronpedia Graph Metrics
We report both Replacement and Completeness scores for:

The raw pruned attribution graph (all features)
The concept-aligned subgraph (pinned supernodes + connected nodes)
Replacement Score: Measures the fraction of end-to-end influence from input tokens to output logits that flows through feature nodes rather than error nodes. This strict metric rewards complete explanations where tokens influence logits entirely through features. The subgraph score treats unpinned features as error nodes, testing whether our selected supernodes capture the essential causal structure.

Completeness Score: Measures the fraction of incoming edges to all nodes (weighted by influence on output) that originate from feature/token nodes rather than error nodes. This gives partial credit for nodes that are mostly explained by features, even if some error influence remains. Again, unpinned features are treated as error nodes for subgraph scoring.

Table: Graph vs. Subgraph Metrics

Prompt

Graph Replacement

Subgraph Replacement

Graph Completeness

Subgraph Completeness

Austin (Dallas prompt)

0.7245

0.5655

0.9041

0.8323

Oakland (entity swap)

0.7035

0.5680

0.8964

0.8346

Michael Jordan (sports)

0.6930

0.4905

0.8989

0.8117

Small opposite

(general)

0.7343	0.6213	0.9081	0.8604
muscle diaphragm (anatomy)

0.6253

0.4518

0.8727

0.7896

Mean	0.6961	0.5394	0.8960	0.8257
 

The consistent 79-83% Completeness across all five prompts,
despite varying Replacement scores, indicates that concept-aligned grouping
successfully identifies features that explain model behavior, even when
the simplified circuit doesn’t fully replicate it. This trade-off—
interpretability vs. completeness—is acceptable for circuit analysis
purposes where understanding causal structure matters more than perfect
reconstruction. These are descriptive results from 5 examples. Broader
validation across prompt types, relationship schemas, and models is needed
to confirm generalization.

 

 

Baseline Comparisons
I compare our concept-aligned grouping to two geometric baselines:

Cosine-only clustering: Agglomerative clustering on 1 − cosine of activation vectors.
Layer adjacency clustering: Agglomerative (Ward) on normalized [layer, influence].
Important: Neuronpedia Replacement/Completeness are near-invariant here because all three uploads pin the same nodes. These scores primarily reflect node coverage and influence, not how nodes are grouped. We report them as a sanity check, but they do not discriminate interpretability in this setup.Interpretability metrics (used for comparison):

Peak Token Consistency (↑): fraction of samples whose peak token matches the cluster’s modal peak token.
Activation Pattern Similarity (↑): mean within-cluster cosine similarity on activation features.
Sparsity Consistency (↓): mean within-cluster std of sparsity ratio.
Silhouette (↑) and Davies–Bouldin (↓): geometric clustering quality (reported for context, not interpretability).
Table: Michael Jordan circuit, n=172 features, same pinned node set for all uploads

Replacement: Graph 0.6930 → Subgraph 0.4905 (all methods)
Completeness: Graph 0.8989 → Subgraph 0.8117 (all methods)
Metric

Concept-Aligned

Cosine Similarity

Layer Adjacency

Peak Token Consistency

0.425

0.183

0.301

Activation Pattern Similarity

0.762

0.130

0.415

Sparsity Consistency

0.255

0.399

0.335

Silhouette Score

0.124

-0.386

0.707

Davies-Bouldin Index

1.298

1.582

0.486

 

Note: Differences are descriptive; statistical significance tests not performed. Concept-aligned grouping shows higher behavioral coherence but lower geometric clustering quality. Statistical validation needed.

Intepretation:

Cosine similarity aggregates many nodes that are neither functionally nor semantically related; it produces high geometric separation only when it collapses to near-singletons and does not yield interpretable groups.
Layer clustering separates nodes because they live on different layers; this improves geometric indices (silhouette, DB) but does not induce semantic coherence within clusters.
Concept-aligned grouping yields substantially higher semantic coherence (token consistency, within-cluster activation similarity) even if geometric indices are lower.

 

Cross-Prompt Robustness
To test generalization, we evaluated on prompt families with:

Entity swaps: Dallas→Houston, Texas→California, Austin→Sacramento
Paraphrases: “The capital of the state containing Dallas” → “The seat of government for the state where Dallas is located”
Mild reorderings: “The state containing Dallas has capital Austin” (grammatical variations)
Survival criteria:

Supernode features activate consistently across variations (≥70% overlap)
Layer and token distributions remain similar
The aligned concept shifts appropriately (e.g., if Dallas→Houston, the “Dallas” supernode should activate on Houston instead)
 
Table 2: Cross-Prompt Robustness (Dallas→Oakland Entity Swap)

Metric

Value

Total Dallas Features

39

Transferred to Oakland

25 (64.1%)

Failed to Transfer

14 (35.9%)

Binomial Test (vs 50% chance)

p=0.054 (marginally non-significant)

Transferred Features: Mean Layer

6.3 (SD=5.2)

Failed Features: Mean Layer

16.4 (SD=5.8)

Activation Overlap (transferred)

1.000 (SD=0.000)

Peak Token Consistency

96% (appropriate concept shifts)

 

 

 

 

 

 

 

 

 

 

 

 

Entity swap used structurally identical prompts. Robustness to paraphrases,
reorderings, and cross-domain transfers untested.

 

Cross-Lingual Limitation 
A notable failure occurred when testing the standard English pipeline on the French equivalent of the antonymy prompt — “le contraire de ‘petit’ est” — using the same probe prompts as “the opposite of ‘small’ is”. The model produced incoherent activations and no valid supernode grouping. The issue arose from the language mismatch (English probes applied to French text) and the absence of French functional tokens in preprocessing. Performance improved when adding French-language probe prompts (linked example), expanding the blacklist to include mixed English and French functional terms («, concept, de, process, their, based), and performing minor manual refinements on the resulting subgraph. Nevertheless, the current prototype remains unreliable in multilingual contexts and requires explicit cross-lingual adaptation for robust use.

Case Study: “The Capital of the State Containing Dallas”
Experimental Setup
We applied the full pipeline to analyze model behavior on a canonical geographic reasoning prompt adapted from prior circuit tracing literature:

“The capital of the state containing Dallas is”

This prompt serves as an ideal test case for several reasons. First, it involves multi-hop geographic reasoning: identifying Dallas → retrieving the containing state (Texas) → recalling its capital (Austin). Second, manual circuit analysis exists for comparison, enabling validation of automated interpretations. Third, the structure naturally supports robustness testing through entity substitution (Houston, San Antonio, etc.), allowing us to assess cross-prompt stability of discovered concepts.

The raw attribution graph extracted from the model contained 322 nodes spanning 14 layers. We applied an influence threshold of 0.60 to prune weakly-connected nodes, retaining 80 nodes (24.8%) that collectively account for the core computational pathway. Selected nodes correspond to 39 unique features (excluding error/attribution artifacts).  


Nodes represent features (gray) and token embeddings (green) positioned by their context location and layer depth. Node size indicates causal influence (cubic scaling: size ∝ influence³). The graph shows computational flow from input embeddings (layer 0) through intermediate features to late-layer output promotion (layers 15-23), with dense clustering at output positions suggesting concentrated output formation mechanisms.
The 80 selected nodes capture 59% of cumulative graph influence while representing only 24.8% of nodes, indicating effective filtering of redundant or weakly-causal features.


Influence distribution shows heavy tail—top 24% of features account for 80% of causal effect (knee at green diamond, threshold τ=0.60).
Features present in multiple context token (n_ctx ≥ 5) showed 3.3× higher average activation (11.56 vs. 3.47) compared to single-context features, but maintained similar influence scores (0.538 vs. 0.540). This suggests that high-activation, multi-context features play distinct but comparably important roles to specialized single-context features.


(Left) Violin plot showing activation magnitude increases with context coverage (n_ctx). Multi-context features exhibit higher mean activation. (Right) Scatter plot reveals near-zero correlation between activation strength and causal influence (r=0.02, ρ=-0.12), demonstrating that highly-activating features are not necessarily causally important. Color indicates context breadth; size reflects influence.
The pruned graph revealed two distinct feature populations: multi-context generalists (n=8, present in ≥5 probes) with 3.3× higher average activation (11.56 vs. 3.47), and single-context specialists (n=75) with lower but comparably influential activations. This suggests a hierarchical organization where generalist features provide computational scaffolding while specialist features perform concept-specific detection.

 
Probe Prompting
Using the output of an instructed [5] language model, we obtained five targeted probe prompts to isolate distinct semantic and relational concepts:

Entity probes (semantic grounding):
"entity: A city in Texas, USA is Dallas"
"entity: The capital city of Texas is Austin"
"entity: A state in the United States is Texas"
Attribute probes (property detection):
"attribute: The primary city serving as the seat of government for a state is the capital city"
Relationship probes (relational binding):
"relationship: the state in which a city is located is the state containing"
These probes systematically vary the target concept (Dallas/ Austin/ Texas/ capital/ containing) while maintaining consistent linguistic structure, enabling direct comparison of feature activation patterns across conceptual categories. Prompts where not modified by me after the generation.

All 40 selected features demonstrated active engagement with probe prompts (100% coverage), with each feature activating (>0) on at least one probe and collectively accounting for 100% of the circuit's causal importance. This complete coverage validates our attribution-based feature selection: unlike activation-threshold methods that may include inert features, every feature in our pruned circuit participates meaningfully in the computation probed by concept-targeted prompts.


Top 14 features by influence (red line, right axis) showing activation patterns across five probe types (stacked bars, left axis). High-influence features (left) activate broadly across multiple probes; low-influence features (right) show probe-specific activation.
Initial analysis aggregating activation by probe prompt revealed insufficient
granularity for functional classification: features activating on the “Dallas
entity probe” could peak on “Dallas” (semantic), “entity:” (structural), " is"
(functional), or other tokens, representing fundamentally different computational
roles despite similar probe-level activation.
 


Peak tokens where features achieve maximum activation (n=70 observations from 40 features across 5 probes). Functional tokens dominate (" is": 42.9%), indicating prevalent output promotion behavior. Structural tokens ("entity", ":": 27.2% combined) suggest scaffolding roles. Semantic content tokens (" the", " city", " capital", " state", " containing": 20.0%) provide evidence for concept-selective detection.
We therefore refined our approach to use peak tokens—the specific tokens
where features achieve maximum activation—as the primary classification signal.
Peak token analysis  revealed a structured distribution: 42.9% of
feature-probe observations peaked on the functional token " is" (output promotion),
27.2% on structural tokens (“entity:”, “:”), and 20.0% on semantic content
(" city", " capital", " state", " containing"). This distribution directly
informed our classification thresholds: features consistently peaking on
functional tokens → Say X nodes; features peaking on semantic content with
high consistency → Semantic nodes; features with diffuse peaks across multiple
content tokens → Relationship nodes.


The heatmap shows which tokens activate which features most strongly. Green intensity indicates activation strength (darker = stronger). BOS token is excluded
After a prolonged "feature etnography" (I literally printed activations and annotated them by hand over several days, confronting the results with Neuronpedia feature cards) i realized that features exhibited systematic activation patterns aligned with probe concepts:

Entity-selective features peaked consistently on “Dallas”, “Austin”, or “Texas” tokens across their respective probes
Relationship features activated diffusely across relational phrases (“state containing”, “located in”)
Output promotion (SayX) features peaked on functional tokens (“is”) preceding target entities

 

Concept-Aligned Grouping
The 40 classified features underwent the three-stage grouping process (3.1-3.3) to assign interpretable concept-aligned names and merge features into supernodes. This section details the pipeline outputs and resulting supernode structure.

Before naming, all peak tokens were classified as either semantic (content-bearing: “Texas”, “capital”, “Dallas”) or functional (bridging: " is", " the", punctuation). For features peaking on functional tokens, we identified target semantic tokens within a ±5 token window using directional rules. Target token discovery successfully linked functional peaks to their promoted semantic content. For example:

Feature 0_40780 peaking on " is" → target: " Dallas" (forward distance 1)
Feature 7_66152 peaking on " is" → target: " Austin" (forward distance 1)
This preprocessing enabled interpretable naming: instead of generic “functional token detector,” features received specific labels like “Say (Austin)” based on their target context.

Applying the classification thresholds (3.2) to aggregated cross-probe metrics yielded the following distribution:

Feature Classification Results

Node Type	N Features	% of Total	Layer Range	Key Criteria Met
Semantic	19	48.7%	0-22	peak_consistency ≥ 0.80, n_distinct_peaks ≤ 1, layer ≤ 3 OR semantic_confidence ≥ 0.50
Say X	16	41.0%	7-22	func_vs_sem ≥ 50%, confidence_functional ≥ 0.90, layer ≥ 7
Relationship	4	10.3%	1	sparsity < 0.45, diffuse activation patterns
The near-perfect alignment between predicted classification (based on metrics) and observed peak token behavior validates the threshold design. Features classified as “Say X” indeed peak on functional tokens; “Semantic” features peak consistently on specific content tokens. Edge cases handled:

Feature 0_40780 (Layer 0, peaks on " is"): Initially ambiguous—layer 0 suggests semantic, but functional peak suggests Say X. Classified as Semantic with “Dictionary (fallback)” subtype due to layer constraint, despite functional behavior. Named " is" rather than “Say (X)” to reflect its unique role as an early-layer functional token detector.
Feature 20_44686 (Layer 20, mixed peaks): Peaks on “Dallas”, " is", “Texas” across probes. Classified as Semantic (“Texas”) with confidence 0.70, prioritizing the strongest semantic activation (Texas) over functional peaks.
Relationship features (1_12928, 1_72774, 1_52044): All show high universal activation (activate on all 5 probes) but peak on different semantic tokens per probe (" containing", " capital", " state"). This polysemantic behavior triggered Relationship classification via low peak_consistency and high diffuseness (sparsity < 0.45).
The 39 classified features were assigned interpretable names using node-type-specific strategies, then grouped into 13 supernodes based on name matching:

Table 3: Discovered Supernodes

Supernode Name	Node Type	N Features	Layer Range	Total Influence	Naming Strategy
Say (Austin)	Say X	11	7-22	0.0354	Target token from functional " is" peaks
is	Semantic	7	0	0.0319	Peak semantic token (functional detector)
Texas	Semantic	5	0-20	0.0269	Peak semantic token
(Texas) related	Relationship	2	1	0.0177	Aggregated activation (highest: “Texas”)
Dallas	Semantic	3	1-22	0.0117	Peak semantic token
Say (capital)	Say X	4	12-20	0.0106	Target token from functional peaks
(capital) related	Relationship	1	1	0.0096	Aggregated activation (highest: “capital”)
(containing) related	Relationship	1	1	0.0067	Aggregated activation (highest: “containing”)
capital	Semantic	1	0	0.0027	Peak semantic token
of	Semantic	1	0	0.0027	Peak semantic token
[3 additional nodes]	Various	3	—	<0.003	—
To validate concept-aligned naming, we examined whether supernode names reflect actual feature behavior by inspecting top aggregated activations (extracted from the extended semantic vocabulary across all probes), achieving full naming accuracy for top-5 supernodes by influence. The highest aggregated activation token consistently matches the assigned supernode name, confirming that naming strategies correctly capture dominant feature behavior:

Supernode	Assigned Name	Top-3 Activations	Match?
(Texas) related	Texas	Texas (100.97), Dallas (91.24), state (90.70)	✓
(capital) related	capital	capital (101.81), containing (97.75), seat (92.93)	✓
(containing) related	containing	containing (125.94), capital (118.34), state (110.75)	✓
Texas	Texas	Texas (18.45), is (5.99), all others (0.0)	✓
Dallas	Dallas	Dallas (21.47), is (20.13), all others (0.0)	✓
 

 

Supernode Interpretation
 
Say (X) supernodes

The largest supernode, “Say (Austin)” (11 features, 28% of circuit), spans layers 7-22 and accounts for 0.0354 total influence (9% of circuit). This distributed representation suggests output promotion is not localized to a single “answer-promoting feature” but rather emerges from coordinated activation of multiple late-layer features. Composition:

All 11 features peak on functional tokens (" is", " the") across probe prompts
Target token discovery consistently identified “Austin” as the forward semantic target
Layer distribution: 3 features (layers 7-12), 5 features (layers 13-18), 3 features (layers 19-22)
The multi-layer distribution suggests a hierarchical output promotion mechanism: early Say X features (layers 7-12) may initiate answer promotion, while late features (19-22) finalize the output logit boost. This aligns with prior circuit analysis showing gradual output shaping in transformer models.

Semantic supernodes

The semantic supernodes reveal how the model maintains entity representations across the circuit's depth. The "Texas" supernode comprises 5 features distributed across a broad layer range (0-20), with features consistently peaking on the "Texas" token whenever it appears in probe prompts. This wide vertical span suggests the model implements persistent entity tracking: rather than detecting Texas once in early layers and discarding the representation, the circuit maintains Texas-selective features throughout shallow, middle, and deep layers. 

The "Dallas" supernode shows a similar but more selective pattern. Its 3 member features span layers 1-22, peaking exclusively on the "Dallas" token but only in probes where Dallas is the target entity. Feature 22_11998 provides a particularly illuminating case: positioned at layer 22 (the model's final layer), it shows strong activation on "Dallas" (21.47) while maintaining near-zero activation elsewhere. The presence of Dallas-specific features this late in the network suggests that entity information not only persists but continues to be computationally relevant even at the output stage. This challenges simplistic models of information flow where early layers "detect" entities and late layers merely "use" them—instead, the circuit appears to maintain explicit entity representations throughout its entire computational depth, possibly to support disambiguation or enable robust answer selection even when earlier layers introduce uncertainty.
 

Relationship Supernodes: Polysemantic Binding

The 4 Relationship features exhibit fundamentally different behavior from their Semantic counterparts, grouping into 3 supernodes based on aggregated semantic activation patterns rather than consistent peak tokens. All of these features concentrate exclusively in layer 1, pointing to an early-layer relational binding stage that establishes conceptual scaffolding before entity-specific processing begins.

The largest of these groups, "(Texas) related" (2 features), demonstrates the polysemantic nature of Relationship nodes. Feature 1_12928 provides a clear example: rather than peaking consistently on "Texas" like the Semantic Texas features, it peaks on structural prompt tokens—"entity", "attribute", "relationship"—that provide no direct semantic information. However, when we examine its activation profile across the extended semantic vocabulary (aggregating responses to all probe concepts), a clear pattern emerges: Texas receives the highest activation (100.97), followed by Dallas (91.24), state (90.70), and capital (74.52). This feature doesn't detect the token "Texas" itself but rather activates diffusely on Texas-related semantic content appearing in relational contexts.

Similarly, "(capital) related" (1 feature) shows how relationship binding operates independently of specific tokens. Feature 1_72774 peaks on diverse semantic tokens across probes—" city", " state", " primary"—but its aggregated activation profile reveals the highest response to "capital" (101.81). This suggests the feature binds capital-city relationships in entity probes, activating whenever the prompt involves governmental seat concepts regardless of which specific words appear.

The "(containing) related" supernode (1 feature) exhibits perhaps the clearest relational signature. Feature 1_52044 peaks on " USA", " capital", and " state" across different probes, yet when aggregated across all semantic contexts, it shows maximal activation on "containing" (125.94)—a word that appears only in the "relationship" probe. This featurepossibly  detects spatial and containment relations, activating strongly whenever the prompt involves geographic nesting or location-within-location semantics, even when the specific tokens expressing that relationship vary.

The striking concentration of all Relationship features in layer 1 suggests a distinct computational stage: early relational binding that establishes conceptual relationships before specific entities are tracked through deeper layers. These features appear to provide a semantic scaffold—a diffuse activation pattern spanning related concepts—that downstream entity-specific features (layers 0-20) can leverage for disambiguation. Unlike the monosemantic entity detectors that maintain narrow, persistent activations, Relationship features cast a broader net in early layers, potentially enabling the circuit to represent "Texas-related governmental structures" as a unified conceptual space before committing to specific tokens or answers.
 

The Unusual “is” Supernode

7 features (18% of circuit) grouped into the “is” supernode (all layer 0, total influence 0.0319). These features peak consistently on the token " is" across all probes, but were classified as Semantic rather than Say X due to the layer constraint (layer 0 < minimum Say X layer of 7).

Interpretation: these layer-0 features implement activation pooling at functional token positions. Rather than detecting structural syntax per se, they concentrate circuit budget: the 7 features collectively channel 8.2% of total influence to the " is" token, creating a high-activation substrate that late-layer Say X features (layers 7-22) inherit. This bottom-up boost is semantically agnostic—it amplifies whatever answer follows " is" regardless of content. The result is a two-stage promotion mechanism: (1) early budget allocation establishes where answers appear (layer 0), (2) late semantic features determine which answer to promote (layers 7-22). Even when multiple Say X features encode conflicting semantic preferences (e.g., competing city names), they all leverage the shared functional scaffold, explaining why the "Say (Austin)" supernode can comprise 11 diverse features yet produce coherent output.

 

Subgraph Construction and Validation
The 39 features were assembled into a minimal subgraph by pinning:

All supernode member features
Token embedding nodes for {Dallas, Austin, Texas, capital, containing}
The output logit for “Austin”

Extracted Subgraph for Geographic Reasoning Circuit 
Concept-aligned subgraph extracted using Replacement Score (0.7245) and Completeness Score (0.9041) thresholds. Nodes represent supernodes (circles) and token embeddings (squares), sized by causal influence. Edge thickness reflects connection strength.
The subgraph reveals a three-stage computational flow:  (1) Early relational binding (bottom-left: "(Texas) related", "(containing) related", "(capital) related" in layer 1) establishes conceptual scaffolding; (2) Entity tracking (center: "Texas", "Dallas" nodes spanning multiple layers) maintains semantic representations; (3) Output promotion (top-right: "Say (Austin)", "Say (capital)" in layers 7-22) concentrates on answer tokens. The "is" supernode (layer 0) serves as a functional scaffold, pooling computational budget at the answer position. Green edges highlight the dominant pathway from entity detection to output promotion. Subgraph Replacement Score (0.5655) and Completeness Score (0.8323) indicate successful compression while preserving core circuit function.

 
5.5 Cross-Prompt Robustness
To assess whether discovered supernodes represent stable computational structures versus probe-specific overfitting, we tested the pipeline on a structurally identical probe with substituted entities: Oakland → Sacramento (California capital) compared to the original Dallas → Austin (Texas capital). Both probes require the same multi-hop reasoning (identify city → retrieve state → recall capital) but differ in all factual content, enabling direct evaluation of which circuit components generalize.


Heatmap showing supernode presence and influence across Dallas→Austin (Texas) and Oakland→Sacramento (California) probes. Each cell's color intensity reflects total influence; width represents feature count. 
The 23 discovered supernodes stratified cleanly into three behavioral categories:

Universal concepts—representing domain-general linguistic operations—demonstrated perfect transfer: all 7 supernodes appeared in both probes with comparable structure (e.g., "is" copula: 35 features in Dallas, 45 in Oakland; "(capital) related" operator: 5 features in both).
Entity-specific supernodes showed perfect appropriate non-transfer: 8 supernodes appeared exclusively in their respective probes ("Texas"/"Dallas" vs "California"/"Oakland"), with zero inappropriate transfers.
Output promotion supernodes exhibited target-appropriate shifts: "Say (Austin)" (55 features, layers 7-22) appeared only in Dallas, while "Say (Sacramento)" (55 features, layers 7-22) appeared only in Oakland—a parallel structure indicating a consistent architectural pattern for answer promotion that reconfigures semantic content across probes.

(A) Feature overlap percentage by layer depth. Bars show shared features as percentage of minimum probe size. Gradient from 92% (layer 0) to 0% (layer 22) validates hierarchical organization: early layers implement universal operations, late layers specialize for entity-specific output. Regions annotated: Universal processing (L0-1, 80-92% overlap), Transition zone (L7-12, 67-100%), Entity-specific output (L16-22, 0-50%). (B) Distribution of activation magnitude differences for 25 shared features (relative difference = |Dallas - Oakland| / max). Strong peak at zero (72% of features show identical activation) indicates robust feature behavior. Long tail (28% moderate variation) reflects appropriate context-dependent modulation. Median = 0.0, mean = 0.058 (94% similarity).
Among 25 individual features appearing in both probes (12.8% of Dallas features), activation patterns showed high stability: 88% peaked on the same token (22/25), 96% on the same token type (24/25), and mean activation magnitude differed by only 5.8%. Supernode assignment consistency was 68% by naive automated checking, rising to 96% after accounting for appropriate entity-dependent variation (e.g., "(Texas) related" → "(California) related"). The low feature overlap rate (12.8%) reflects entity-specificity in SAE representations—most features encode particular facts—but the features that do overlap represent genuine computational primitives with robust cross-probe behavior.

Layer-wise analysis confirmed hierarchical organization: early layers (0-1) showed 80-92% feature overlap (universal operations), declining to 0-50% in late layers (16-22, entity-specific output promotion). This gradient held constant across probes, indicating the model maintains stable architectural layering while substituting factual content.

Reproducibility: Full pipeline outputs (activation data, metric tables, supernode groupings) and Neuronpedia subgraph are available at:

Neuronpedia
Github
 

Planned Extensions: Scale Evaluation and Causal Interventions
Probe-based validation shows behavioral consistency, but it is correlational. To strengthen the claims, we will (a) scale the evaluation to many graphs with a single, repeatable template and (b) run causal interventions that predictably move logits when we modify the learned structure.

We will evaluate automation at scale by generating a large, standardized set of attribution graphs using a single configuration. The sweep targets all 50 US states and their capitals (excluding DC for consistency), producing one attribution graph per prompt template and variant.

For each state–capital pair, we will  instantiate a small family of concept-targeted, context-varying prompts that query the same underlying relation with minimal surface changes. Examples include “The capital of the state containing {city} is …”, “{state}’s capital is …”, and cloze forms with distractors. Each template will be paired with entity-swap variants (e.g., Dallas/Texas/Austin ↔ Oakland/California/Sacramento). We also include negative controls (near-miss entities or plausible but wrong capitals) to check that supernodes do not fire indiscriminately.

For each state graph: the Neuronpedia scores for raw pruned graph vs. baseline clusters vs. our supernodes; coverage (fraction of influential features with assigned concept labels); stability under entity-swap and paraphrase; and any trade-off between behavioral coherence and geometric compactness. We will also provide aggregate summaries across all states (means, CIs, and variance decomposition by layer), highlighting the early-vs-late-layer hierarchy observed in the pilot (early layers generalize; late layers specialize).

Planned intervention experiments:

Ablation: Zero out “Say Austin” features → output probability for “Austin” should drop, alternative capitals (or “Texas”) should increase
Steering: Amplify “Texas” features while swapping in “California” semantics → output should shift toward “Sacramento”
Cross-circuit transfer: Replace “Dallas/Texas/Austin” supernodes with “Oakland/California/Sacramento” features → model should complete the circuit with the new capital
Implementation status: Utility helpers exist in the repository but are not yet wired for end-to-end analysis. We plan to:

Predict logit changes from supernode modifications
Run targeted interventions on both frozen and adaptive attention variants
Report intervention effects alongside Neuronpedia metrics
Limitations and Open Questions
Current Limitations
No causal interventions yet: our validation relies on cross-prompt stability and graph metrics. Ablation/steering experiments would provide stronger evidence.

Missing attention modality: Cross-Layer Transcoders (CLTs) capture residual stream transformations but not attention-mediated routing. Some circuit nuances—especially value-dependent attention patterns—remain invisible to our analysis.

Narrow prompt family: I focused on factual recall. The approach may not generalize to:

Mathematical reasoning (symbol manipulation, proof steps)
Creative generation (metaphor, style transfer)
Adversarial or out-of-distribution inputs
Small models only: Testing has been limited to Gemma-2-2B. Larger models may have different organizational principles that our heuristics don’t capture.

Polysemantic features in early layers: Our “relationship” nodes often show diffuse, context-dependent activation. These may represent genuine polysemanticity that requires attention-aware analysis to disambiguate fully.

Furthermore, several important limitations should be noted:

Small sample validation: Current validation uses only 1-2 examples per
claim, insufficient for broad generalization. The baseline comparison tests
one circuit (Michael Jordan); robustness testing uses two circuits (Dallas/Oakland).
No statistical significance testing: Baseline comparisons report descriptive
differences only (peak consistency: 0.425 vs 0.183) without t-tests, effect
sizes, or confidence intervals. We cannot claim these differences are
statistically significant.
Limited prompt variation testing: Cross-prompt robustness was tested only
on structurally identical prompts (entity substitution: Dallas→Oakland,
Texas→California). Robustness to paraphrases (“capital of Texas” vs “seat of
government for Texas”), syntactic reorderings, and cross-domain transfers
remains untested.
Trade-off in clustering quality: While concept-aligned grouping achieves
higher behavioral coherence metrics, it produces lower geometric clustering
quality (silhouette: 0.124 vs 0.707 for adjacency-based clustering). This
suggests our method prioritizes interpretability over geometric compactness.
Partial feature transfer: The 64% survival rate (25/39 features) on entity
swaps, while above chance (p=0.054, marginally non-significant), indicates
substantial prompt-specific components (36% failed). Failed features concentrate
in late layers (M=16.4 vs M=6.3 for transferred features), suggesting
hierarchical organization where early features generalize but late features
remain context-dependent.
Single model scope: results are from Gemma-2-2b/CLT-HP. Generalization across architectures and scales remains unvalidated.
Domain specificity: geographic reasoning may exhibit particularly clean concept structure. Validation on messier domains (e.g., social reasoning, abstract concepts) is needed.
Threshold sensitivity: classification thresholds (§3) were tuned on this example. Robustness to threshold variation and transferability to other prompts requires systematic ablation.
Baseline absence: se lack ground-truth manual circuit analysis for quantitative comparison. Future work should benchmark against expert-annotated circuits where available.
Autointerp comparison scope: systematic comparison across all 39 features would strengthen convergence claims.
 

What Would Change My Mind
I would revise or abandon this approach if:

Baselines match performance: If cosine/adjacency clustering achieves similar Replacement/Completeness scores and cross-prompt stability with less complexity
Stability collapses: If concept-aligned supernodes fail to transfer across even minor prompt variations in the same task family
Interventions contradict labels: If ablating “Say Austin” nodes doesn’t affect Austin probability, or if steering experiments produce unpredictable effects
Attention undermines grouping: If adding attention-aware features consistently reveals that our MLP-only groups are functionally incoherent
 
Open Questions for Future Work
How do probe prompts interact with prompt engineering best practices? Are some phrasings systematically better for eliciting clean activation patterns?
Can concept hypotheses be learned end-to-end? Instead of LLM-generated concepts, could we jointly optimize probe prompts and grouping criteria?
What’s the right granularity for supernodes? Our thresholds produce 40-60 groups; is this the sweet spot for human interpretability?
How does the approach scale to longer prompts? Multi-paragraph contexts may require hierarchical grouping strategies..
Disclaimer
English is not my first language. I used language models to help edit grammar and clarity after writing my ideas. All core concepts, experiments, and engineering are my own.

 

 

^
 A replacement model is a linearized model that freezes gradients for attention patterns and layer norms, and allows gradients only through linear components.This makes it possible to compute direct effects between features.

^
 about 0-15 minutes and a L4 are enough to obtain the activations over 5 prompts X 40 features

^
https://www.lesswrong.com/posts/pHPmMGEMYefk9jLeh/llm-basics-embedding-spaces-transformer-token-vectors-are

^
Size formula: size = (normalized_node_influence)³ × 1000 + 10.
Cubic scaling amplifies contrast (e.g. 0.5³ = 12.5%, 0.8³ = 51%).
Embedding and feature groups are scaled independently. 
Caution note: in the JSON file, the “influence” field represents the cumulative value before pruning. Therefore, estimating node_influence as the difference between consecutive cumulative values is only a normalized proxy (to be re-normalized on the current set), because the graph may already have been topologically pruned and the selection does not correspond to a contiguous prefix of the sorted nodes.

^
System prompt:
"""
Analyze the following text and extract the key concepts.

             

       INSTRUCTIONS:
       1. Identify the 1-10 most significant concepts in the text
       2. For each concept, provide:
       - A brief and precise label (maximum 5 words)
       - A category (entity, process, relationship, attribute, etc.)
       - A brief description of the concept in context

       Return ONLY a JSON array in the following format, without additional explanations:
       [
           {{
               "label": "concept label",
               "category": "category",
               "description": "brief description"
           }},
           ...
       ]

TEXT:
"""

1.
 A replacement model is a linearized model that freezes gradients for attention patterns and layer norms, and allows gradients only through linear components.This makes it possible to compute direct effects between features.

2.
 about 0-15 minutes and a L4 are enough to obtain the activations over 5 prompts X 40 features

3.
https://www.lesswrong.com/posts/pHPmMGEMYefk9jLeh/llm-basics-embedding-spaces-transformer-token-vectors-are

5.
System prompt:
"""
Analyze the following text and extract the key concepts.

             

       INSTRUCTIONS:
       1. Identify the 1-10 most significant concepts in the text
       2. For each concept, provide:
       - A brief and precise label (maximum 5 words)
       - A category (entity, process, relationship, attribute, etc.)
       - A brief description of the concept in context

       Return ONLY a JSON array in the following format, without additional explanations:
       [
           {{
               "label": "concept label",
               "category": "category",
               "description": "brief description"
           }},
           ...
       ]

TEXT:
"""

