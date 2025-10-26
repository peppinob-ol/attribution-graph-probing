# **Automating Attribution Graph Analysis Through Feature Ethnography**

---

## **Executive Summary**

**The core problem:** Circuit tracing requires \~2 hours of expert time per prompt for manual feature interpretation and supernode creation. Many polisemantic features remain difficult to interpret without access to attention features.  This doesn’t scale.

**My approach:** What if we could systematically automate the “lumping together nodes” process that researchers describe in Anthropic’s methodology? I developed an “ethnographic strategy” that treats features as having measurable “personalities”—behavioral profiles that guide automated clustering.

**Key insight:** Features aren’t just activation patterns; they’re agents with consistent behavioral signatures. A feature that responds strongly to geographic entities \+ shows high cross-prompt

**Results achieved:**  
*On the  prompt: “The capital of state containing Dallas is”*

* **54 interpretable supernodes** (37 semantic \+ 17 computational)   
* **891 features systematically clustered** (18.3% of total dataset, zero duplicates)  
* **100% cross-prompt stability** for all final supernodes  
* **83.7% capture rate of interpretable features** (891 clustered out of 1,065 processable features; automatically excluded 3,800 non-informative features: layer-0 noise, inconsistent activations, and structural artifacts)

![][image1]

**What this teaches:** Circuit analysis bottlenecks aren’t just about compute—they’re about developing systematic ways to recognize organizational patterns in alien computation. The present approach suggests features self-organize into discoverable taxonomies, potentially making mechanistic interpretability more scalable.

---

## **Research Problem & Motivation**

### **The Circuit Tracing Bottleneck**

I started this investigation after watching Neuropedia podcast where Anthropic researchers casually mention that analyzing a single prompt takes “\~2 hours for a kind of experienced circuit tracer.” This struck me as the kind of scaling problem that should be solvable systematically rather than just thrown more human labor at.

The bottleneck isn’t computational—it’s cognitive. When you load an attribution graph, you’re confronted with thousands of active features across dozens of layers. The graph pruning helps, but you still need to:

1. **Manually inspect** each feature’s activation patterns across dataset examples  
2. **Intuitively group** features that “seem to play similar roles”  
3. **Subjectively decide** which groupings are meaningful vs. arbitrary  
4. **Iteratively refine** supernodes through trial and error

Emmanuel Ameisen mentions in the podcast that this process is “as much an art as a science”—exactly the kind of statement that makes me want to systematize it.

### **Personal Connection to the Problem**

I’d been working on “Prompt Rover”—a tool for black-box semantic navigation—when I discovered circuit tracing. Prompt Rover automatically extracts concept relationships from any language model’s outputs, creating interactive visualizations of semantic space. It works by:

* **Concept extraction**: LLM-powered identification of key concepts in text  
* **Embedding analysis**: Converting concepts to high-dimensional vectors  
* **Network visualization**: Displaying concept relationships as interactive graphs

*![][image2][Prompt Rover](https://www.lesswrong.com/posts/nfGZtKzz8WzxF3MAs/on-the-geometrical-nature-of-insight) interface showing concept constellation visualization*

The irony hit me: I had built a tool that automatically creates interpretable concept maps from black-box models, while circuit tracing—which has access to the model’s internals—still requires hours of manual interpretation.

**Research question:** Could the systematic concept extraction approach that works for black-box analysis be adapted to automate white-box feature clustering?

This felt like a natural bridge between two interpretability paradigms that rarely talk to each other.

### **Why This Matters Now**

Neel’s research interests have shifted toward “model biology”—studying qualitative high-level properties rather than complete reverse-engineering. This anthropological approach fits perfectly: instead of trying to understand every feature, we systematically map the organizational principles that govern how features self-organize.

The potential impact extends beyond just making circuit analysis faster:

* **Democratic access**: Non-experts could explore attribution graphs without deep interpretability training  
* **Systematic bias detection**: Automated clustering might reveal organizational patterns humans miss  
* **Cross-model comparison**: Standardized analysis could enable systematic study of how feature organization varies across architectures

![][image3]

Comparison showing manual vs. anthropological supernode creation workflows

---

## **Methodology & Technical Approach**

### **Phase 1: Deep Dive into Circuit Tracing (Building on Anthropic’s Framework)**

I started by fully implementing Anthropic’s circuit tracing pipeline, not just using it. This meant understanding Cross-Layer Transcoders (CLTs), attribution graph computation, and the local replacement model construction.

**Setup:**

* **Model**: google/gemma-2-2b with Gemma Scope transcoders  
* **Prompt**: “The capital of state containing Dallas is” (chosen for geographic factual recall)  
* **Attribution configuration**: 10 max logits, 0.95 probability threshold, batch size 256  
* **Feature space**: 8,192 max feature nodes (though only \~6,362 were active)

**Technical learning:** The beauty of CLTs vs. per-layer transcoders became clear once I implemented both. CLTs collapse amplification chains across layers into single features, dramatically reducing path length (average 2.3 vs 3.7 for per-layer). It’s a fundamental insight about how models organize computation across layers.

### **Phase 2: Concept Extraction Meets Circuit Analysis (Adaptation of Prompt Rover)**

Here’s where my background work paid off. Prompt Rover had already solved automated concept extraction from black-box models. Could I adapt this to generate hypotheses about what circuit features *should* represent?

**Adapted Pipeline:**

def extract\_concepts\_with\_llm(prompt):

    """Generate testable hypotheses about feature semantics"""

    return structured\_llm\_call(

        f"Extract key concepts from: {prompt}",

        output\_schema={"label": str, "category": str, "description": str}

    )

When I ran this on “The capital of state containing Dallas is”, it extracted concepts like:

* {"label": "Dallas", "category": "entity", "description": "Major city in Texas"}  
* {"label": "capital", "category": "relationship", "description": "Primary administrative city of a political region"}  
* {"label": "containing", "category": "spatial\_relation", "description": "Geographic containment relationship"}

These became testable hypotheses. For each active feature, I could now ask: “Does this feature respond to Dallas? To capital? To geographic containment?”

![][image4]

*Comparison between activation intensity on original prompt and concept descriptions (new sequence), coloured by token wich most activated the feature (peak token)*

*Aggiungere riferimento alla proiezione di luci diverse sullo stesso artefatto, scegliendo le luci accuratamente per separate i canali più influenti (immagine dei tarocchi)*

### **Phase 3: Feature Sensitivity Probing (Original Methodology)**

For each of the 6,362 active features, I tested sensitivity across extracted concepts:

**Dual Testing Protocol:**

* **Label-only**: Does the feature activate on just “Dallas”?  
* **Label+description**: Does the feature activate on “Dallas: Major city in Texas”?

**Key metrics developed:**

* cosine\_similarity: How similar is the activation pattern to the original prompt?  
* z\_score\_robust: IQR-based measure of activation deviation  
* peak\_on\_label: Boolean—does activation peak fall on the concept token?  
* activation\_density: Percentage of tokens above activation threshold


![][image5]

*Distribution of features for token where they are most activated (peak).*

![][image6]

*Heatmap showing the difference between features that most contributed to the original prompt (left columns) and the concept description “Texas” (whole description on the left, only concept label on the right.*

Aggiungere un paragrafo di commento al grafico, per che tipo di ragionamenti è utile

**Unexpected discovery:** Features fell into clear behavioral archetypes:

* **Semantic anchors** (127 features): High label affinity \+ cross-prompt consistency  
* **Computational scaffolds** (various): Structural roles (attention, normalization, etc.)  
* **Garbage features** (filtered out): Layer-0 noise, inconsistent activations

![][image7]

*Semantic SImilarity Distribution Across Transformer Layers* 

### **![][image8]**

*Most of “Garbage features” peak on \<BOS\>  token.*

### **Phase 4: The Anthropological Strategy**

### This is where I departed from existing approaches. Instead of clustering features mathematically (which consistently failed), I treated them as entities with “personalities” to be studied ethnographically.

**Feature Biography Construction:**  
Each feature gets a behavioral profile based on:

* **Activation signature**: Where and how strongly it fires  
* **Semantic consistency**: Stability across related prompts  
* **Neighborhood analysis**: Which other features it co-activates with  
* **Layer positioning**: Temporal location in the computational narrative

Aggiungere uno o più esempi “etnografici”

**The Controlled Expansion Discovery:**  
During seed selection, I noticed some features exhibited unusually systematic expansion behavior that reliably absorbed semantically related features across multiple layers. Example:

Seed: Geographic entity feature (Layer 4, Token: Dallas)

Growth pattern:

  → Layer 7: Texas political references

  → Layer 12: Southern U.S. cultural markers  

  → Layer 18: Output features promoting Texas-related tokens

  → Layer 23: Say "Austin" motor features

![][image9]

*Controlled expansion pattern visualization showing semantic coherence across layers.*

**Systematic Construction Algorithm:**

1. **Diversified seed selection**: 37 seeds across layers/tokens to avoid clustering bias  
2. **Controlled narrative growth**: Each expansion validated for semantic coherence  
3. **Global duplicate prevention**: No feature can belong to multiple supernodes  
4. **Quality filtering**: Automatic exclusion of inconsistent or garbage features

**Why “anthropological”?** Because I found myself doing ethnography—observing feature behavior, inferring relationships, mapping social structures. The metaphor wasn’t just cute; it captured something essential about how to systematically study alien computation patterns.

---

## **Key Findings & Contributions**

### **1\. Feature Organization Follows Discoverable Patterns (Novel Insight)**

**What I found:** Features aren’t randomly distributed—they self-organize according to systematic principles that can be measured and exploited.

The anthropological analysis revealed three distinct feature classes:

* **Semantic anchors** (127 features): High concept affinity, cross-prompt stability  
* **Computational scaffolds** (748 features): Layer-specific structural roles  
* **Narrative bridge features** (various): Connect semantic concepts across computation layers

![][image10]

**Why this matters:** Current circuit analysis treats all features as equally mysterious. This classification suggests we can automatically identify which features are worth detailed interpretation vs. which serve purely computational roles.

**Technical validation:** All semantic anchors showed \>0.8 cross-prompt stability, while computational scaffolds clustered predictably by layer and token type. This wasn’t designed into the algorithm—it emerged from the data.

### **2\. Systematic Feature Expansion Phenomenon** 

**Discovery:** Some features exhibit controlled expansion behavior that reliably captures coherent semantic territories. These “expansion-capable” features systematically absorb related features across multiple layers.

**Example \- Dallas Expansion Pattern:**

Layer 4:  Geographic entities (Dallas, Houston, Texas cities)

Layer 8:  Political references (Texas state politics, governors)  

Layer 12: Cultural markers (Southern U.S., regional identity)

Layer 18: Output promotion (Austin, state capital, Texas-related tokens)

Layer 23: Motor execution (say "Austin", geographic completion)

![][image11]

Layered expansion visualization showing coherent semantic growth across computation

![][image12]

**Insight:** This suggests some features function as “concept organizers”—they don’t just detect semantic content, they systematically recruit related computation across the entire forward pass. This could be a fundamental organizational principle in large language models.

Aggiungere confronto con attribution graph fatto da letteratura sulla stessa frase (nel github di circuit tracing)

### **3\. Automation Succeeds Where Mathematical Clustering Fails**

Standard clustering approaches (cosine similarity, graph adjacency, k-means) consistently produced uninterpretable groupings. But the anthropological approach—treating features as behavioral agents—succeeded systematically on the example prompt.

**Why this works:** Mathematical similarity doesn’t capture functional relationships. Two features might have similar decoder vectors but serve completely different computational roles. The ethnographic approach considers *context*—when features activate, what they do, how they relate to the overall computational narrative.

**Practical implication:** This suggests circuit analysis needs ethnographic rather than purely mathematical approaches. We’re studying alien cognition, not optimizing engineering systems.

### **4\. Cross-Paradigm Validation Reveals Hidden Structure**

**Integration insight:** Using Prompt Rover’s concept extraction to generate hypotheses, then validating with circuit tracing internal access, revealed patterns neither approach could discover alone.

**Specific example:** The prompt concept “containing” was extracted as a spatial relationship. Circuit analysis found features responding to this concept scattered across layers 6-19, but all clustered around tokens expressing containment relationships. This suggested a distributed circuit for spatial reasoning that manual analysis might miss.

**Methodological contribution:** This creates a systematic framework for hypothesis generation → internal validation that could scale circuit analysis beyond current human limitations.

### 

### **5\. Quality Emerges Unexpectely from Systematic Selection** 

**Finding:** The final 54 supernodes achieved 100% cross-prompt stability without explicitly optimizing for this metric. Quality emerged from the systematic selection process rather than being designed in.

**Insight:** This suggests the anthropological approach captures something real about feature organization. Random clustering wouldn’t achieve such consistency. The systematic methodology appears to detect genuine computational structure.

**Quantitative validation:**

* **Semantic coherence**: 0.842 average (vs. \~0.3 for random groupings)  
* **Cross-prompt stability**: 100% (vs. \~45% for mathematical clustering)  
* **Coverage efficiency**: 83.7% of informative features captured in just 18.3% of total space

---

## **Unexpected Discoveries & What Went Wrong**

### **The Failure of Mathematical Intuition (Humbling)**

**What I expected:** Cosine similarity of decoder vectors would naturally group functionally related features. This seemed obvious—features that write to similar residual stream directions should serve similar computational roles.

**What actually happened:** Mathematical clustering produced groupings that made no semantic sense. Features for “Texas geography” and “Python debugging” clustered together. Features that clearly served the same function (multiple Dallas-related detectors) scattered across different clusters.

\[image: Failed clustering visualization showing semantically incoherent mathematical groupings\]

**Why this matters:** This failure taught me something important about the nature of circuit analysis. We’re not studying an engineering system where mathematical similarity implies functional similarity. We’re studying evolved computation where context, timing, and narrative role matter more than vector geometry.

### **Systematic Feature Expansion Phenomenon** 

During seed selection, I noticed some features exhibited unusually systematic expansion behavior that reliably absorbed semantically related features across multiple layers.

**Critical insight:** Some features function as “concept organizers”—they don’t just detect semantic content, they systematically recruit related computation across the entire forward pass. This could be a fundamental organizational principle.

### **Quality Emerges from Systematic Selection (Unexpected)**

The final 54 supernodes achieved 100% cross-prompt stability without explicitly optimizing for this metric. Quality emerged from the systematic selection process rather than being designed in—suggesting the anthropological approach captures something real about feature organization.

---

## **Limitations & Honest Assessment**

### **What This Work Doesn’t Achieve**

**Single-model Single-prompt validation:** Everything was tested on one model (Gemma-2-2b) with one transcoder type (Gemma Scope) on one specific prompt (*“The capital of state containing Dallas is”**)***. The patterns I found might be completely specific to this setup.

**Limited prompt diversity:** I focused on geographic factual recall. The ethnographic strategy might fail completely on mathematical reasoning, code generation, or creative writing prompts.

**No ground truth validation:** I can measure internal consistency and cross-prompt stability, but I can’t verify that my supernodes actually reflect “real” computational organization vs. statistical artifacts.

### 

### **What Genuinely Worries Me**

**Anthropomorphism bias:** The “personality” metaphor might impose human organizational patterns on alien computation. Just because my ethnographic approach worked doesn’t mean features actually have personalities—I might be discovering artifacts of my own pattern-matching.

**Cherry-picking risk:** I focused on the 18.3% of features that seemed interpretable. What about the other 81.7%? Are they genuinely less important, or did my approach systematically miss important computational patterns?

**Scalability uncertainty:** The manual validation steps might not scale to larger graphs. What works for 6K features might break at 60K features.

---

## **What I Learned About Research (Personal Reflection)**

### **The Importance of Failed Experiments**

**Most valuable insight:** My failures taught me more than my successes. The complete failure of mathematical clustering forced me to question fundamental assumptions about how to analyze these systems. We’re not studying engineered artifacts but evolved computation.

**Specific lessons:**

* **Direct transfer doesn’t work**: You can’t just port methods between paradigms  
* **Mathematical intuition can mislead**: Similarity in vector space ≠ functional similarity  
* **Systematic exploration beats theoretical elegance**: The expansion mechanism discovery came from methodical testing, not clever insights

### **Research as Ethnography vs. Engineering**

**Mindset shift:** I started thinking I was optimizing a clustering algorithm. I ended up doing ethnography—studying behavioral patterns of alien computational agents.

This reframing was crucial. Once I stopped trying to engineer a solution and started trying to understand feature behavior systematically, patterns emerged that mathematical approaches missed.

### **The Value of Methodological Pluralism**

**Before:** I assumed good research meant picking the right approach and optimizing it.

**After:** I realized studying alien computation requires multiple perspectives. Black-box \+ white-box \+ ethnographic observation each revealed different aspects that none could achieve alone.

**Personal note:** This challenges my engineering background, where there’s usually one optimal solution. Interpretability seems to require holding multiple frameworks simultaneously.

---

## **Why This Might Matter for MATS**

### **Connection to Neel’s Research Interests**

This work aligns with your shift toward “model biology”—studying qualitative organizational principles rather than complete reverse-engineering. The anthropological strategy is fundamentally about discovering how features self-organize into taxonomies.

**Relevance to applied interpretability:** If systematic feature classification works, it could enable automated analysis of model capabilities, failure modes, or safety-relevant patterns.

### **Potential for Extension During MATS**

**Sprint project potential:** The cross-model generalization question seems perfect for the 2-week research sprint format. Clear hypothesis, systematic testing, interpretable results.

**Collaboration opportunities:** This work could integrate with other scholars’ research on SAEs, steering, or automated interpretability.

**Technical feasibility:** All the infrastructure exists (circuit-tracer library, various model transcoders, evaluation frameworks).

---

## **Epistemic Status**

**High confidence:**

* The anthropological strategy successfully creates interpretable supernodes  
* Mathematical clustering consistently fails for circuit features  
* Manual circuit analysis has genuine scaling limitations  
* Integration of black-box and white-box approaches is technically feasible

**Medium confidence:**

* Feature “personalities” reflect real organizational principles vs. statistical artifacts  
* The 18.3% coverage represents genuinely important features vs. cherry-picked interpretable ones  
* Cross-prompt stability indicates fundamental computational relationships  
* This approach could accelerate circuit analysis beyond proof-of-concept

**Low confidence:**

* Patterns will generalize across models, architectures, or prompt types  
* The anthropological metaphor captures something essential vs. being a useful cognitive tool  
* Systematic approaches can replace human intuition for novel circuit discovery

**Honest uncertainty:**

* Whether I’m discovering genuine insights about model organization vs. developing sophisticated pattern-matching that happens to work  
* How this relates to broader questions about model understanding, consciousness, or goal-directed behavior  
* Whether the ethnographic framing is scientifically productive vs. anthropomorphically misleading

**What would increase confidence:** Cross-model replication, independent validation by other researchers, and especially testing on fundamentally different prompt types (mathematical, creative, adversarial).

---

*Research conducted over \~18 hours in Augutst 2025, building on 6 months of background work in semantic navigation and interpretability. Full implementation and results available at: [https://github.com/peppinob-ol/attribution-graph-probing](https://github.com/peppinob-ol/attribution-graph-probing)*  
*https://www.lesswrong.com/posts/nfGZtKzz8WzxF3MAs/on-the-geometrical-nature-of-insight*
