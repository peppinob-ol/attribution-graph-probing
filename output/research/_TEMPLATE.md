# [Topic]: [Descriptive Title]

**Status**: Draft | Under review | Concluded
**Confidence**: Low | Medium | High
**Date**: YYYY-MM-DD
**Claim tested**: [Cite the specific claim from METHODOLOGY_REPORT.md, e.g.,
"C1: Feature swapping demonstrates entity-specific causal leverage" or a
sub-claim from the FULLSCALE_CONTROL_REPORT.md]

---

## Summary

(Write this section last. One paragraph stating the conclusion, the
confidence level, and the most important caveat.)

---

## 1. Question

What specific hypothesis is being tested? What would confirmation look
like? What would falsification look like? State the null hypothesis
explicitly.

## 2. Method

### Data scope

- Dataset(s):
- Run(s):
- Variant(s):
- N (samples):
- Filters applied:

### Queries and comparisons

Describe the exact SwapQuery / SwapStats / PipelineTracer calls used.
Include enough detail that someone could reproduce the analysis.

## 3. Evidence

### Aggregate results

(Tables, rates, effect sizes, bootstrap CIs. Numbers only -- no
interpretation in this section.)

### Representative samples

(Individual cases that illustrate the pattern. Include both confirming
and disconfirming examples.)

### Edge cases and outliers

(Cases that don't fit the pattern. These are often more informative
than the typical cases.)

## 4. Alternative Explanations

For each finding, explicitly consider:

| Finding | Proposed explanation | Alternative explanation | How to distinguish |
|---------|---------------------|----------------------|-------------------|
| | | | |

## 5. Threats to Validity

- **Pipeline artifacts**: Could concept matching quirks (reverse substring,
  blacklist gaps) explain the result?
- **Metric artifacts**: Is the result driven by a mechanical metric
  (flip@0) rather than a meaningful one (vsMax, gap closure)?
- **Sample size**: Is N sufficient for the claim being made?
- **Selection bias**: Were samples cherry-picked? Would the finding hold
  across all entities / pairs / domains?
- **Confounds**: Token overlap, error node density, feature count imbalance?

## 6. Conclusion

State the finding, its confidence level, and what it means for the
claim being tested. Be explicit about what this does and does not
establish.

### What this supports

### What this does not support

### Remaining uncertainties

## 7. Follow-up

- [ ] Next investigation needed
- [ ] Additional conditions to test
- [ ] Entries in `_LOG.md` that feed into this report

---

*Generated from investigation log entries: [list entry dates/topics]*
