# LessWrong Publication Checklist

This document provides a final checklist before publishing the blog post.

---

## Content Completeness

- [x] TL;DR (5-7 bullets, self-contained)
- [x] Epistemic status (clear confidence levels)
- [x] Introduction with personal narrative
- [x] Problem statement (circuit tracing bottleneck)
- [x] Failed approaches (naive clustering)
- [x] Method (5-stage pipeline, detailed)
- [x] Validation (4 validation strategies with quantitative results)
- [x] Results (Dallas→Austin case study with interventions)
- [x] Discussion (why ethnography works, connection to model biology)
- [x] Limitations (honest, specific)
- [x] What would change my mind (falsifiable)
- [x] Future work (immediate + long-term)
- [x] Reproducibility (code, data, commands)
- [x] Related work (ties to Neuronpedia landscape)
- [x] Acknowledgements
- [x] Disclosure (MATS application context)

---

## Clarity Improvements (Based on Neel's Feedback)

### Original Feedback:
> "I thought the writing could have been substantially clearer. In particular I found it difficult to understand exactly how you validated that your supernodes worked, which is a crucial part of the whole thing."

### Addressed:

- [x] **Validation section is now the longest and most detailed** (4 distinct validation strategies)
- [x] **Quantitative metrics with baselines** (table comparing ethnographic vs. cosine vs. adjacency)
- [x] **Intervention examples with predicted vs. actual outcomes** (steers, ablations, logit changes)
- [x] **Cross-prompt robustness with survival rates** (100% vs. 45-52% for baselines)
- [x] **Error analysis with failure modes** (when method breaks, why, how to detect)
- [x] **Reproducibility section with exact commands** (anyone can verify results)

### Specific Clarity Checks:

- [x] Every claim has supporting evidence (metric, intervention, or baseline comparison)
- [x] Technical terms defined on first use
- [x] Code snippets show implementation, not just concepts
- [x] Figures mapped to sections with detailed captions
- [x] Limitations stated explicitly, not buried
- [x] "What would change my mind" makes falsifiability clear

---

## Writing Style (Matching "On the Geometrical Nature of Insight")

- [x] Personal narrative opening (failure → insight → systematic approach)
- [x] Honest about limitations and uncertainties
- [x] Concrete examples before abstractions
- [x] Short paragraphs, bolded key claims
- [x] Active voice ("I rebuilt" not "The pipeline was rebuilt")
- [x] Speculation clearly marked (Discussion section)
- [x] Methods/Validation crisp and testable
- [x] Analogies and metaphors used sparingly, grounded in evidence

---

## Technical Accuracy

- [x] CLT/PLT terminology consistent with Neuronpedia landscape paper
- [x] Attribution graph mechanics correctly described
- [x] Intervention methodology (steers, ablations) technically sound
- [x] Metrics (cosine similarity, z-score, peak-on-label, activation density) well-defined
- [x] Baselines are fair comparisons (same number of clusters, same data)
- [x] Cross-prompt tests use appropriate held-out examples
- [x] Error analysis acknowledges known limitations (attention pathways, error nodes)

---

## Reproducibility

- [x] GitHub repo link provided
- [x] Exact commands for each pipeline stage
- [x] Random seeds specified for deterministic reproduction
- [x] Artifact checklist (graphs, prompts, supernodes, interventions)
- [x] Figure generation scripts mentioned
- [x] API requirements documented (Neuronpedia key)
- [x] Model/transcoder versions specified (Gemma-2-2B, Gemma Scope)

---

## Figure Quality

- [x] Figure plan created with 8 figures mapped to sections
- [x] Captions are self-contained and informative
- [x] Existing figures identified for reuse
- [x] New figures specified with data sources
- [x] Caption style guide follows your writing voice
- [x] Figures support claims rather than decorating

### Figures to Include:

1. Pipeline schematic (workflow overview)
2. Behavioral archetypes distribution
3. Controlled expansion visualization
4. Baseline comparison (multi-panel)
5. Dallas→Austin circuit subgraph
6. Intervention results (logit changes)
7. Cross-prompt stability (heatmap)
8. Failure mode analysis

---

## LessWrong Formatting

- [x] Markdown compatible (no custom HTML)
- [x] Code blocks use triple backticks with language tags
- [x] Tables use standard markdown format
- [x] Links are inline `[text](url)` format
- [x] Headings use `##` for sections, `###` for subsections
- [x] Bullet lists use `-` or `*` consistently
- [x] Block quotes use `>` for citations
- [x] Math notation avoided (not needed for this post)

---

## Tone and Audience

- [x] Assumes reader familiarity with basic interpretability (SAEs, features, circuits)
- [x] Explains CLT/PLT differences for those who might not know
- [x] Avoids jargon where possible, defines when necessary
- [x] Balances technical depth with accessibility
- [x] Acknowledges uncertainty without undermining contributions
- [x] Invites replication and critique (epistemic humility)

---

## Call to Action

- [x] Explicit invitation for replication ("If you try this method...")
- [x] GitHub repo for immediate access
- [x] Clear next steps for interested researchers
- [x] Open questions highlighted in Future Work
- [x] Acknowledges this is one approach, not the only approach

---

## Pre-Publication Edits

### Pass 1: Clarity
- [ ] Read through entire post as if you're Neel
- [ ] Flag any section where validation is unclear
- [ ] Ensure every technical claim has supporting evidence
- [ ] Check that baselines are explained before results

### Pass 2: Conciseness
- [ ] Cut redundant explanations
- [ ] Merge similar paragraphs
- [ ] Remove hedging language ("might," "perhaps," "possibly") where claims are supported
- [ ] Keep hedging where uncertainty is genuine

### Pass 3: Flow
- [ ] Ensure smooth transitions between sections
- [ ] Check that narrative arc is clear (problem → failed approaches → solution → validation)
- [ ] Verify figures are referenced in text before appearing
- [ ] Confirm Related Work doesn't repeat Introduction

### Pass 4: Technical
- [ ] Double-check all numbers (metrics, percentages, counts)
- [ ] Verify code snippets are syntactically correct
- [ ] Confirm GitHub links work
- [ ] Test reproducibility commands (if possible)

### Pass 5: Final Polish
- [ ] Fix typos and grammar
- [ ] Ensure consistent terminology throughout
- [ ] Check that Epistemic Status matches content
- [ ] Verify Disclosure is accurate and complete

---

## Post-Publication

- [ ] Share on LessWrong
- [ ] Post link in relevant communities (Alignment Forum, Twitter/X, Discord)
- [ ] Monitor comments for:
  - Replication attempts
  - Technical critiques
  - Suggestions for improvement
  - Questions about methodology
- [ ] Update GitHub README with link to LessWrong post
- [ ] Consider writing follow-up if replication results come in

---

## Known Gaps (Acknowledge, Don't Hide)

1. **Medical vignette removed**: Original application included preeclampsia example; removed due to confounds and medical claims concerns. Mention in Limitations if asked.

2. **Attention pathways**: CLTs don't capture attention; this is a known limitation from landscape paper. Acknowledged in Limitations and Related Work.

3. **Single-model validation**: Only tested on Gemma-2-2B and Llama-3.1-1B. Acknowledged in Limitations and "What would change my mind."

4. **Manual validation steps**: Some intervention design still requires human judgment. Acknowledged in Future Work (automated validation).

5. **Prompt type narrowness**: Only tested on factual recall. Acknowledged in Limitations and Future Work.

---

## Success Criteria

This post succeeds if:

1. **Neel's feedback is addressed**: Validation is crystal clear, not buried or vague
2. **Reproducible**: Another researcher can follow the commands and verify results
3. **Falsifiable**: Clear criteria for when the method fails or should be abandoned
4. **Honest**: Limitations and failures are as visible as successes
5. **Useful**: Provides a validated starting point for others working on attribution graphs

This post does NOT need to:

1. Solve circuit tracing completely
2. Generalize to all models/prompts
3. Replace expert analysis
4. Be the final word on feature clustering

---

## Final Check Before Publishing

- [ ] Read Epistemic Status and confirm it matches content
- [ ] Read "What would change my mind" and confirm it's falsifiable
- [ ] Read Validation section and confirm it's clear and detailed
- [ ] Read Limitations and confirm they're honest and specific
- [ ] Read Reproducibility and confirm commands are complete
- [ ] Verify GitHub repo is public and up-to-date
- [ ] Check that figures are referenced in text
- [ ] Ensure no broken links
- [ ] Confirm Disclosure is accurate

---

## Publication Timeline

1. **Now**: Draft complete, figure plan ready
2. **Next**: Generate missing figures (4, 6, 7, 8)
3. **Then**: Final editing passes (5 passes above)
4. **Finally**: Publish on LessWrong, share widely, monitor feedback

---

**Status**: Draft complete. Ready for figure generation and final editing passes.

