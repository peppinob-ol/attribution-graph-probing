"""
About modal -- detailed methodology and cross-domain validation results.

Static content derived from METHODOLOGY_REPORT.md (33,387 steering runs,
5 domains, 3 experimental conditions).  KPIs are hardcoded: they reflect
the full-scale experiment, not the currently selected run.
"""
from fasthtml.common import (
    Div, H2, H3, H4, P, A, Button, Span, NotStr, Ul, Li
)


def about_modal(dc: dict):
    """Top-level modal wrapper -- called from home.py."""
    return Div(
        id="about-modal",
        cls="fixed inset-0 z-[100] bg-black/70 backdrop-blur-sm flex items-start justify-center",
        style="display: none; padding: 5.5rem 1.5rem 2rem 1.5rem;",
    )(
        Div(
            cls="bg-slate-900 border border-slate-700 rounded-xl max-w-3xl w-full shadow-2xl flex flex-col",
            style="max-height: calc(100vh - 8rem);",
        )(
            _modal_header(),
            Div(
                cls="flex-1 overflow-y-auto space-y-6",
                style="padding: 1.5rem 2rem 2.5rem 2rem;",
            )(
                _section_intro(),
                _section_pipeline(dc),
                _section_classification(),
                _section_experimental_design(),
                _section_cross_domain_results(),
                _section_field_additivity(),
                _section_regime_taxonomy(),
                _section_domain_gradient(),
                _section_epistemic_status(),
                _section_references(),
                _section_footer(),
            ),
        ),
    )


# -- header / footer --------------------------------------------------------

def _modal_header():
    return Div(
        cls="flex-shrink-0 bg-slate-900 border-b border-slate-800 rounded-t-xl flex items-center justify-between",
        style="padding: 1.25rem 2rem;",
    )(
        Div(cls="flex items-center gap-3")(
            H2(cls="text-xl font-semibold text-white")("Methodology & Results"),
            Span(cls="text-[10px] px-2 py-0.5 rounded-full bg-cyan-900/40 text-cyan-400 font-mono")(
                "33,387 runs"
            ),
        ),
        Button(
            id="about-close",
            cls="text-slate-400 hover:text-white text-2xl leading-none",
        )("x"),
    )


def _section_footer():
    return Div(cls="border-t border-slate-800 pt-4 space-y-2")(
        P(cls="text-xs text-slate-500")(
            "Built by Anonymous Authors",
        ),
    )


# -- intro -------------------------------------------------------------------

def _section_intro():
    return Div(cls="space-y-4")(
        # Background: attribution graphs and CLT
        Div(cls="space-y-3")(
            P(cls="text-slate-300 leading-relaxed")(
                A(
                    href="https://transformer-circuits.pub/2025/attribution-graphs/methods.html",
                    target="_blank", cls="text-cyan-400 hover:underline font-medium",
                )("Attribution graphs"),
                " (Ameisen et al., 2025) are causal maps that trace how information "
                "flows from input tokens through internal features to output logits "
                "inside a language model. They are built on top of ",
                Span(cls="text-cyan-400 font-medium")("Cross-Layer Transcoders (CLT)"),
                " -- sparse dictionaries with ~2.5M features that replace MLP layers "
                "and decompose the residual stream into interpretable units. "
                "A replacement model freezes attention patterns and linearizes "
                "the residual stream through CLT features, allowing Anthropic's ",
                A(
                    href="https://github.com/safety-research/circuit-tracer",
                    target="_blank", cls="text-cyan-400 hover:underline",
                )("Circuit Tracer"),
                " to compute per-feature causal influence on any target logit.",
            ),
            P(cls="text-slate-300 leading-relaxed")(
                "These graphs typically contain hundreds to thousands of feature "
                "nodes. Manual interpretation -- inspecting activation patterns "
                "across corpus examples to assign semantic labels -- takes ~2 hours "
                "per prompt. This pipeline automates first-pass analysis using ",
                Span(cls="text-cyan-400 font-medium")("Probe Prompting"),
                ": an instructed LLM generates semantic probes that measure each "
                "feature's behavior under controlled semantic variation, classifies "
                "features into functional roles using transparent rules, groups them "
                "into labeled supernodes, and tests their causal relevance via "
                "feature swapping.",
            ),
        ),
        # What this demo shows
        Div(cls="bg-slate-800/30 rounded-lg p-3 border border-slate-700/50 space-y-2")(
            P(cls="text-slate-300 text-sm leading-relaxed")(
                Span(cls="text-slate-200 font-medium")("This demo "),
                "visualizes pairwise steering experiments across 33,387 runs "
                "and 5 knowledge domains. Each matrix cell represents an attempt "
                "to redirect the model from a source entity (row) to a target "
                "entity (column), using labeled feature swaps. Cells are colored "
                "on a tiered scale from T5 (target answer produced) to "
                "T1 (source persists).",
            ),
            P(cls="text-slate-400 text-xs leading-relaxed")(
                "The central question: do probe-prompted labels have ",
                Span(cls="text-cyan-400")("entity-specific causal leverage"),
                " -- i.e. do they steer the model toward the intended target -- "
                "or do they just generically disrupt output? "
                "Structurally matched random-feature controls (same count, same "
                "layer distribution) serve as the null hypothesis.",
            ),
        ),
    )


# -- pipeline ----------------------------------------------------------------

def _section_pipeline(dc: dict):
    return Div(cls="bg-slate-800/50 rounded-lg p-4 border border-slate-700 space-y-4")(
        H3(cls="text-sm font-semibold text-slate-400 uppercase tracking-wide")(
            "Pipeline Overview"
        ),
        # four steps
        _pipeline_step(
            "1", "Attribution Graph",
            "Neuronpedia API generates a causal graph of CLT features for a "
            "seed prompt via a local replacement model (frozen attention, "
            "linearized residual stream). "
            "Features are selected by cumulative influence threshold (tau = 0.95).",
        ),
        _pipeline_step(
            "2", "Probe Prompting",
            "An instructed LLM generates semantic probes that reuse the seed "
            "prompt's token structure. Each feature is measured across all "
            "probes, producing a Cross-Prompt Activation Signature (CPAS) "
            "that captures functional vs semantic behavior.",
        ),
        _pipeline_step(
            "3", "Classification & Supernodes",
            "A transparent decision tree classifies features into four types "
            "(Semantic Dictionary, Semantic Concept, Say-X, Relationship) "
            "using explicit thresholds -- no learned parameters. "
            "Features sharing the same class and name form supernodes.",
        ),
        _pipeline_step(
            "4", "Feature Swapping",
            "Source supernodes are suppressed (ablate) while target supernodes "
            "are amplified via additive delta injection through CLT decoder "
            "vectors. Attention is NOT frozen -- the model can route around "
            "interventions, making positive results stronger evidence.",
        ),
        # intervention params
        Div(cls="font-mono text-xs bg-slate-900/50 rounded p-3 space-y-1")(
            _param_row("Model", dc.get('model_id', '') or "Gemma-2-2B-it (clt-hp)"),
            _param_row("Source features", f"ablate {dc.get('m_ablate', -2)}x", "text-red-400"),
            _param_row("Target features", f"amplify +{dc.get('m_amplify', 20)}x", "text-emerald-400"),
            _param_row("Generation",
                       f"{dc.get('n_tokens', 10)} tokens, temp {dc.get('temperature', 0.3)}, seed 42"),
        ),
    )


def _pipeline_step(num, title, desc):
    return Div(cls="flex gap-3")(
        Span(cls="flex-shrink-0 w-6 h-6 rounded-full bg-cyan-900/40 text-cyan-400 text-xs font-bold flex items-center justify-center mt-0.5")(num),
        Div()(
            P(cls="text-sm font-medium text-slate-200")(title),
            P(cls="text-xs text-slate-400 leading-relaxed mt-0.5")(desc),
        ),
    )


def _param_row(label, value, color="text-slate-300"):
    return Div(cls="flex items-center gap-3")(
        Span(cls="text-slate-500 w-28")(label),
        Span(cls=color)(value),
    )


# -- classification ----------------------------------------------------------

def _section_classification():
    return Div(cls="bg-slate-800/50 rounded-lg p-4 border border-slate-700 space-y-3")(
        H3(cls="text-sm font-semibold text-slate-400 uppercase tracking-wide")(
            "Feature Classification (Decision Tree)"
        ),
        P(cls="text-slate-400 text-xs leading-relaxed")(
            "Strict priority ordering -- the first matching rule wins. "
            "All thresholds are explicit and auditable."
        ),
        Div(cls="font-mono text-[11px] bg-slate-900/50 rounded p-3 space-y-1.5 text-slate-300 leading-snug")(
            P()(
                Span(cls="text-cyan-400")("1. "),
                "peak_consistency >= 0.80 AND n_distinct_peaks <= 1",
                Span(cls="text-emerald-400")(" -> Semantic Dictionary"),
            ),
            P()(
                Span(cls="text-cyan-400")("2. "),
                "func_vs_sem >= 50 AND conf_F >= 0.90 AND layer >= 7",
                Span(cls="text-emerald-400")(" -> Say-X (output promotion)"),
            ),
            P()(
                Span(cls="text-cyan-400")("3. "),
                "sparsity_median < 0.45",
                Span(cls="text-emerald-400")(" -> Relationship"),
            ),
            P()(
                Span(cls="text-cyan-400")("4. "),
                "layer <= 3 OR conf_S >= 0.50 OR func_vs_sem < 50",
                Span(cls="text-emerald-400")(" -> Semantic Concept"),
            ),
            P()(
                Span(cls="text-cyan-400")("5. "),
                "ELSE",
                Span(cls="text-yellow-400")(" -> Review (flagged)"),
            ),
        ),
    )


# -- experimental design -----------------------------------------------------

def _section_experimental_design():
    return Div(cls="bg-slate-800/50 rounded-lg p-4 border border-slate-700 space-y-3")(
        H3(cls="text-sm font-semibold text-slate-400 uppercase tracking-wide")(
            "Experimental Design"
        ),
        P(cls="text-slate-400 text-sm leading-relaxed")(
            "Five domains spanning different associative complexity, "
            "each tested under three conditions:"
        ),
        # Domain table
        NotStr(
            '<table class="w-full text-xs mt-2">'
            '<thead><tr class="border-b border-slate-700">'
            '<th class="text-left py-1.5 px-2 text-slate-500">Domain</th>'
            '<th class="text-left py-1.5 px-2 text-slate-500">Seed Prompt</th>'
            '<th class="text-right py-1.5 px-2 text-slate-500">Seeds</th>'
            '<th class="text-right py-1.5 px-2 text-slate-500">Pairs</th>'
            '</tr></thead><tbody>'
            '<tr class="border-b border-slate-800">'
            '  <td class="py-1.5 px-2 text-slate-300 font-medium">USA States</td>'
            '  <td class="py-1.5 px-2 text-slate-400">"The capital of the state containing {city} is"</td>'
            '  <td class="py-1.5 px-2 text-right text-slate-400">50</td>'
            '  <td class="py-1.5 px-2 text-right text-slate-300">2,450</td>'
            '</tr>'
            '<tr class="border-b border-slate-800">'
            '  <td class="py-1.5 px-2 text-slate-300 font-medium">Books</td>'
            '  <td class="py-1.5 px-2 text-slate-400">"The book featuring {character} was written by"</td>'
            '  <td class="py-1.5 px-2 text-right text-slate-400">16</td>'
            '  <td class="py-1.5 px-2 text-right text-slate-300">240</td>'
            '</tr>'
            '<tr class="border-b border-slate-800">'
            '  <td class="py-1.5 px-2 text-slate-300 font-medium">Products</td>'
            '  <td class="py-1.5 px-2 text-slate-400">"The company that makes {product} was founded by"</td>'
            '  <td class="py-1.5 px-2 text-right text-slate-400">12</td>'
            '  <td class="py-1.5 px-2 text-right text-slate-300">132</td>'
            '</tr>'
            '<tr class="border-b border-slate-800">'
            '  <td class="py-1.5 px-2 text-slate-300 font-medium">Paintings</td>'
            '  <td class="py-1.5 px-2 text-slate-400">"The first name of the painter of {painting} is"</td>'
            '  <td class="py-1.5 px-2 text-right text-slate-400">10</td>'
            '  <td class="py-1.5 px-2 text-right text-slate-300">90</td>'
            '</tr>'
            '<tr>'
            '  <td class="py-1.5 px-2 text-slate-300 font-medium">Sounds</td>'
            '  <td class="py-1.5 px-2 text-slate-400">"The most common color of the animal that goes \'{sound}\' is"</td>'
            '  <td class="py-1.5 px-2 text-right text-slate-400">6</td>'
            '  <td class="py-1.5 px-2 text-right text-slate-300">30</td>'
            '</tr>'
            '</tbody></table>'
        ),
        P(cls="text-slate-500 text-xs mt-2 leading-relaxed")(
            "Three conditions per pair: ",
            Span(cls="text-cyan-400")("labeled"),
            " (concept supernodes), ",
            Span(cls="text-purple-400")("random"),
            " (feature-matched controls, 3 replicates), and ",
            Span(cls="text-slate-300")("field-add"),
            " variants (subsets of concept fields).",
        ),
    )


# -- cross-domain results (static) ------------------------------------------

_RESULTS = [
    # domain, n_best, hit_best, hit_rand, vsmax_best, vsmax_rand, rkgrp_best, rkgrp_rand, medrk_best, medrk_rand
    ("USA States",  "2,450", "38.8%",  "0.1%",  "+4.00", "-2.31", "1.47", "9.00",  "3",  "566"),
    ("Books",       "240",   "37.1%",  "0.3%",  "+7.76", "-0.15", "1.02", "2.43",  "2",  "283"),
    ("Products",    "132",   "24.2%",  "0.3%",  "+3.06", "+0.23", "1.27", "2.25",  "18", "354"),
    ("Paintings",   "90",    "6.7%",   "0.0%",  "+1.46", "-0.03", "1.41", "1.96",  "90", "196"),
    ("Sounds",      "30",    "20.0%",  "12.2%", "+4.69", "+3.14", "1.07", "1.08",  "5",  "24"),
]


def _section_cross_domain_results():
    rows_html = ""
    for d, n, hb, hr, vb, vr, rb, rr, mb, mr in _RESULTS:
        rows_html += (
            f'<tr class="border-b border-slate-800">'
            f'  <td class="py-1.5 px-2 text-slate-300 font-medium">{d}</td>'
            f'  <td class="py-1.5 px-2 text-right text-slate-400">{n}</td>'
            f'  <td class="py-1.5 px-2 text-right text-cyan-400 font-mono">{hb}</td>'
            f'  <td class="py-1.5 px-2 text-right text-red-400/60 font-mono">{hr}</td>'
            f'  <td class="py-1.5 px-2 text-right text-cyan-400 font-mono">{vb}</td>'
            f'  <td class="py-1.5 px-2 text-right text-red-400/60 font-mono">{vr}</td>'
            f'  <td class="py-1.5 px-2 text-right text-cyan-400 font-mono">{rb}</td>'
            f'  <td class="py-1.5 px-2 text-right text-red-400/60 font-mono">{rr}</td>'
            f'  <td class="py-1.5 px-2 text-right text-cyan-400 font-mono">{mb}</td>'
            f'  <td class="py-1.5 px-2 text-right text-red-400/60 font-mono">{mr}</td>'
            f'</tr>'
        )

    return Div(cls="bg-slate-800/50 rounded-lg p-4 border border-slate-700 space-y-3")(
        Div(cls="flex items-center justify-between")(
            H3(cls="text-sm font-semibold text-slate-400 uppercase tracking-wide")(
                "Cross-Domain Validation Results"
            ),
            Span(cls="text-[10px] text-slate-500 font-mono")("best field-add variant vs random"),
        ),
        P(cls="text-slate-400 text-xs leading-relaxed")(
            "The best field-add variant (intermediate+answer fields) vs structurally matched random controls. "
            "Random controls use the same feature count and layer distribution but sampled randomly from the graph."
        ),
        # Primary metrics table
        Div(cls="overflow-x-auto")(
            NotStr(
                '<table class="w-full text-xs">'
                '<thead><tr class="border-b border-slate-700">'
                '<th class="text-left py-1.5 px-2 text-slate-500" rowspan="2">Domain</th>'
                '<th class="text-right py-1.5 px-2 text-slate-500" rowspan="2">N</th>'
                '<th class="text-center py-1 px-2 text-slate-500 border-b border-slate-700" colspan="2">Hit%</th>'
                '<th class="text-center py-1 px-2 text-slate-500 border-b border-slate-700" colspan="2">vsMax</th>'
                '<th class="text-center py-1 px-2 text-slate-500 border-b border-slate-700" colspan="2">RkGrp</th>'
                '<th class="text-center py-1 px-2 text-slate-500 border-b border-slate-700" colspan="2">MedRk</th>'
                '</tr><tr class="border-b border-slate-700">'
                '<th class="text-right py-1 px-2 text-cyan-500/60 text-[10px]">Best</th>'
                '<th class="text-right py-1 px-2 text-red-400/40 text-[10px]">Rnd</th>'
                '<th class="text-right py-1 px-2 text-cyan-500/60 text-[10px]">Best</th>'
                '<th class="text-right py-1 px-2 text-red-400/40 text-[10px]">Rnd</th>'
                '<th class="text-right py-1 px-2 text-cyan-500/60 text-[10px]">Best</th>'
                '<th class="text-right py-1 px-2 text-red-400/40 text-[10px]">Rnd</th>'
                '<th class="text-right py-1 px-2 text-cyan-500/60 text-[10px]">Best</th>'
                '<th class="text-right py-1 px-2 text-red-400/40 text-[10px]">Rnd</th>'
                '</tr></thead><tbody>'
                + rows_html +
                '</tbody></table>'
            ),
        ),
        # Key takeaway
        Div(cls="mt-2 text-xs text-slate-400 leading-relaxed bg-slate-900/50 rounded p-2.5 border-l-2 border-cyan-600")(
            Span(cls="text-cyan-400 font-medium")("Key finding: "),
            "suppression is generic, targeting is specific. "
            "Random controls achieve equal or higher source suppression (75-87%), "
            "but near-zero target hit rates and negative vsMax. "
            "Only labeled supernodes steer toward the correct target entity.",
        ),
    )


# -- primary metrics ---------------------------------------------------------

def _section_primary_metrics():
    """Kept for reference but folded into cross-domain results."""
    return Div(cls="bg-slate-800/50 rounded-lg p-4 border border-slate-700")(
        H3(cls="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-3")(
            "Primary Metrics"
        ),
        P(cls="text-slate-400 text-sm leading-relaxed mb-3")(
            "Three metrics best discriminate labeled interventions from random controls:"
        ),
        Div(cls="space-y-2 text-xs")(
            _metric_row("Hit%",
                "Target answer appears in steered output. Zero for random controls in strong domains."),
            _metric_row("vsMax",
                "best(target_logit - max(other_dataset_answers)). "
                "Positive = target beats all same-domain alternatives. "
                "The cleanest cross-domain specificity discriminator."),
            _metric_row("Recovery",
                "Target logit exceeds its own unsteered baseline at any position. "
                "92% labeled vs 29% random in USA (regime C)."),
        ),
    )


def _metric_row(name, desc):
    return Div(cls="flex gap-2")(
        Span(cls="text-cyan-400 font-bold w-16 shrink-0")(name),
        Span(cls="text-slate-400")(desc),
    )


# -- field additivity --------------------------------------------------------

_FIELD_ADD = [
    ("USA States",  "state+capital",   "mid+ans", "38.8%", "24.7%", "+14.1pp"),
    ("Books",       "book+author",     "mid+ans", "37.1%", "3.8%",  "+33.3pp"),
    ("Products",    "company+founder", "mid+ans", "24.2%", "15.2%", "+9.0pp"),
    ("Sounds",      "sound+animal",    "in+mid",  "20.0%", "0.0%",  "+20.0pp"),
    ("Paintings",   "first_name",      "ans",     "6.7%",  "3.3%",  "+3.4pp"),
]


def _section_field_additivity():
    rows_html = ""
    for domain, fields, role, best_hit, full_hit, delta in _FIELD_ADD:
        rows_html += (
            f'<tr class="border-b border-slate-800">'
            f'  <td class="py-1.5 px-2 text-slate-300">{domain}</td>'
            f'  <td class="py-1.5 px-2 text-cyan-400 font-mono text-xs">{fields}</td>'
            f'  <td class="py-1.5 px-2 text-slate-400">{role}</td>'
            f'  <td class="py-1.5 px-2 text-right text-cyan-400 font-mono">{best_hit}</td>'
            f'  <td class="py-1.5 px-2 text-right text-purple-400 font-mono">{full_hit}</td>'
            f'  <td class="py-1.5 px-2 text-right text-emerald-400 font-mono">{delta}</td>'
            f'</tr>'
        )

    return Div(cls="bg-slate-800/50 rounded-lg p-4 border border-slate-700 space-y-3")(
        H3(cls="text-sm font-semibold text-slate-400 uppercase tracking-wide")(
            'Field Additivity: The "Less is More" Effect'
        ),
        P(cls="text-slate-400 text-xs leading-relaxed")(
            "Each domain's concept fields map to semantic roles: "
            "input (mentioned in prompt), intermediate (bridging concept), "
            "answer (what the model produces). Including input-field supernodes "
            "degrades steering -- often dramatically.",
        ),
        Div(cls="overflow-x-auto")(
            NotStr(
                '<table class="w-full text-xs">'
                '<thead><tr class="border-b border-slate-700">'
                '<th class="text-left py-1.5 px-2 text-slate-500">Domain</th>'
                '<th class="text-left py-1.5 px-2 text-slate-500">Best subset</th>'
                '<th class="text-left py-1.5 px-2 text-slate-500">Role</th>'
                '<th class="text-right py-1.5 px-2 text-slate-500">Best Hit%</th>'
                '<th class="text-right py-1.5 px-2 text-slate-500">Full 3f</th>'
                '<th class="text-right py-1.5 px-2 text-slate-500">Delta</th>'
                '</tr></thead><tbody>'
                + rows_html +
                '</tbody></table>'
            ),
        ),
        Div(cls="mt-2 text-xs text-slate-400 leading-relaxed bg-slate-900/50 rounded p-2.5 border-l-2 border-emerald-600")(
            Span(cls="text-emerald-400 font-medium")("Interpretation: "),
            "Input-field supernodes encode the concept the model reads in the prompt, "
            "not the concept it needs to produce. "
            "Including them activates competing circuits that dilute the answer signal. "
            "The optimal subset is consistently intermediate+answer.",
        ),
    )


# -- regime taxonomy ---------------------------------------------------------

def _section_regime_taxonomy():
    return Div(cls="bg-slate-800/50 rounded-lg p-4 border border-slate-700 space-y-3")(
        H3(cls="text-sm font-semibold text-slate-400 uppercase tracking-wide")(
            "Logit-Shift Regime Taxonomy"
        ),
        P(cls="text-slate-400 text-xs leading-relaxed")(
            "Each swap is classified by what happens to target and source logits "
            "at position 0. The best variant shifts cases from weak regimes to strong ones:"
        ),
        Div(cls="overflow-x-auto")(
            NotStr(
                '<table class="w-full text-xs">'
                '<thead><tr class="border-b border-slate-700">'
                '<th class="text-left py-1.5 px-2 text-slate-500">Regime</th>'
                '<th class="text-left py-1.5 px-2 text-slate-500">Target</th>'
                '<th class="text-left py-1.5 px-2 text-slate-500">Source</th>'
                '<th class="text-left py-1.5 px-2 text-slate-500">Flip?</th>'
                '<th class="text-left py-1.5 px-2 text-slate-500">Intuition</th>'
                '<th class="text-center py-1.5 px-2 text-slate-500" colspan="3">Regime A% (best / labeled / rnd)</th>'
                '</tr></thead><tbody>'
                '<tr class="border-b border-slate-800">'
                '  <td class="py-1.5 px-2 font-bold text-emerald-400">A</td>'
                '  <td class="py-1.5 px-2 text-emerald-400">UP</td>'
                '  <td class="py-1.5 px-2 text-red-400">DOWN</td>'
                '  <td class="py-1.5 px-2 text-emerald-400">yes</td>'
                '  <td class="py-1.5 px-2 text-slate-300">Clean redirection</td>'
                '  <td class="py-1.5 px-2 text-right font-mono text-cyan-400">35%</td>'
                '  <td class="py-1.5 px-2 text-right font-mono text-purple-400">9%</td>'
                '  <td class="py-1.5 px-2 text-right font-mono text-red-400/60">19%</td>'
                '</tr>'
                '<tr class="border-b border-slate-800">'
                '  <td class="py-1.5 px-2 font-bold text-yellow-400">C</td>'
                '  <td class="py-1.5 px-2 text-red-400">DOWN</td>'
                '  <td class="py-1.5 px-2 text-red-400">DOWN</td>'
                '  <td class="py-1.5 px-2 text-emerald-400">yes</td>'
                '  <td class="py-1.5 px-2 text-slate-300">Differential disruption</td>'
                '  <td class="py-1.5 px-2" colspan="3"></td>'
                '</tr>'
                '<tr class="border-b border-slate-800">'
                '  <td class="py-1.5 px-2 font-bold text-red-400">D</td>'
                '  <td class="py-1.5 px-2 text-red-400">DOWN</td>'
                '  <td class="py-1.5 px-2 text-red-400">DOWN</td>'
                '  <td class="py-1.5 px-2 text-red-400">no</td>'
                '  <td class="py-1.5 px-2 text-slate-300">Generic disruption</td>'
                '  <td class="py-1.5 px-2" colspan="3"></td>'
                '</tr>'
                '<tr>'
                '  <td class="py-1.5 px-2 font-bold text-slate-400">E</td>'
                '  <td class="py-1.5 px-2 text-slate-500">FLAT</td>'
                '  <td class="py-1.5 px-2 text-red-400">DOWN</td>'
                '  <td class="py-1.5 px-2 text-emerald-400">yes</td>'
                '  <td class="py-1.5 px-2 text-slate-300">Pure suppression</td>'
                '  <td class="py-1.5 px-2" colspan="3"></td>'
                '</tr>'
                '</tbody></table>'
            ),
        ),
        # Regime A prevalence mini-table
        P(cls="text-xs text-slate-500 mt-2")(
            "Regime A prevalence (cleanest evidence) for best variant vs full labeled vs random:"
        ),
        Div(cls="overflow-x-auto mt-1")(
            NotStr(
                '<table class="w-full text-xs">'
                '<thead><tr class="border-b border-slate-700">'
                '<th class="text-left py-1 px-2 text-slate-500">Domain</th>'
                '<th class="text-right py-1 px-2 text-cyan-500/60">Best</th>'
                '<th class="text-right py-1 px-2 text-purple-400/60">Labeled</th>'
                '<th class="text-right py-1 px-2 text-red-400/40">Random</th>'
                '<th class="text-right py-1 px-2 text-slate-500">Regime D (rnd)</th>'
                '</tr></thead><tbody>'
                '<tr class="border-b border-slate-800">'
                '  <td class="py-1 px-2 text-slate-300">USA</td>'
                '  <td class="py-1 px-2 text-right font-mono text-cyan-400">34.9%</td>'
                '  <td class="py-1 px-2 text-right font-mono text-purple-400">8.9%</td>'
                '  <td class="py-1 px-2 text-right font-mono text-red-400/60">19.4%</td>'
                '  <td class="py-1 px-2 text-right font-mono text-red-400/40">45.3%</td>'
                '</tr>'
                '<tr class="border-b border-slate-800">'
                '  <td class="py-1 px-2 text-slate-300">Books</td>'
                '  <td class="py-1 px-2 text-right font-mono text-cyan-400">62.1%</td>'
                '  <td class="py-1 px-2 text-right font-mono text-purple-400">38.8%</td>'
                '  <td class="py-1 px-2 text-right font-mono text-red-400/60">40.8%</td>'
                '  <td class="py-1 px-2 text-right font-mono text-red-400/40">34.6%</td>'
                '</tr>'
                '<tr class="border-b border-slate-800">'
                '  <td class="py-1 px-2 text-slate-300">Products</td>'
                '  <td class="py-1 px-2 text-right font-mono text-cyan-400">62.1%</td>'
                '  <td class="py-1 px-2 text-right font-mono text-purple-400">56.8%</td>'
                '  <td class="py-1 px-2 text-right font-mono text-red-400/60">51.5%</td>'
                '  <td class="py-1 px-2 text-right font-mono text-red-400/40">22.0%</td>'
                '</tr>'
                '<tr>'
                '  <td class="py-1 px-2 text-slate-300">Paintings</td>'
                '  <td class="py-1 px-2 text-right font-mono text-cyan-400">47.8%</td>'
                '  <td class="py-1 px-2 text-right font-mono text-purple-400">17.8%</td>'
                '  <td class="py-1 px-2 text-right font-mono text-red-400/60">23.3%</td>'
                '  <td class="py-1 px-2 text-right font-mono text-red-400/40">42.2%</td>'
                '</tr>'
                '</tbody></table>'
            ),
        ),
        Div(cls="mt-2 text-xs text-slate-400 leading-relaxed bg-slate-900/50 rounded p-2.5 border-l-2 border-yellow-600")(
            "Random controls concentrate in regime D (42-45% generic disruption), "
            "while the best variant concentrates in regime A (clean redirection). "
            "Within regime C, labeled interventions produce target recovery 92% of the time (USA) vs 29% for random.",
        ),
    )


# -- domain gradient ---------------------------------------------------------

def _section_domain_gradient():
    return Div(cls="bg-slate-800/50 rounded-lg p-4 border border-slate-700 space-y-3")(
        H3(cls="text-sm font-semibold text-slate-400 uppercase tracking-wide")(
            "Domain Gradient & Operating Envelope"
        ),
        P(cls="text-slate-400 text-xs leading-relaxed")(
            "Specificity tracks associative complexity and CLT reconstruction quality, "
            "not graph size:"
        ),
        Div(cls="overflow-x-auto")(
            NotStr(
                '<table class="w-full text-xs">'
                '<thead><tr class="border-b border-slate-700">'
                '<th class="text-left py-1.5 px-2 text-slate-500">Domain</th>'
                '<th class="text-right py-1.5 px-2 text-slate-500">vsMax gap</th>'
                '<th class="text-left py-1.5 px-2 text-slate-500">Strength</th>'
                '<th class="text-left py-1.5 px-2 text-slate-500">Correlates</th>'
                '</tr></thead><tbody>'
                '<tr class="border-b border-slate-800">'
                '  <td class="py-1.5 px-2 text-slate-300">Books</td>'
                '  <td class="py-1.5 px-2 text-right font-mono text-cyan-400">+6.13</td>'
                '  <td class="py-1.5 px-2 text-emerald-400">Strong</td>'
                '  <td class="py-1.5 px-2 text-slate-400">single-hop, specific answer field</td>'
                '</tr>'
                '<tr class="border-b border-slate-800">'
                '  <td class="py-1.5 px-2 text-slate-300">USA States</td>'
                '  <td class="py-1.5 px-2 text-right font-mono text-cyan-400">+5.17</td>'
                '  <td class="py-1.5 px-2 text-emerald-400">Strong</td>'
                '  <td class="py-1.5 px-2 text-slate-400">low CLT error (~10%)</td>'
                '</tr>'
                '<tr class="border-b border-slate-800">'
                '  <td class="py-1.5 px-2 text-slate-300">Products</td>'
                '  <td class="py-1.5 px-2 text-right font-mono text-cyan-400">+3.23</td>'
                '  <td class="py-1.5 px-2 text-yellow-400">Moderate</td>'
                '  <td class="py-1.5 px-2 text-slate-400">moderate error, mid complexity</td>'
                '</tr>'
                '<tr class="border-b border-slate-800">'
                '  <td class="py-1.5 px-2 text-slate-300">Paintings</td>'
                '  <td class="py-1.5 px-2 text-right font-mono text-slate-400">+1.58</td>'
                '  <td class="py-1.5 px-2 text-orange-400">Weak</td>'
                '  <td class="py-1.5 px-2 text-slate-400">multi-step, coarse answer field</td>'
                '</tr>'
                '<tr>'
                '  <td class="py-1.5 px-2 text-slate-300">Sounds</td>'
                '  <td class="py-1.5 px-2 text-right font-mono text-slate-500">+0.14</td>'
                '  <td class="py-1.5 px-2 text-red-400">Negligible</td>'
                '  <td class="py-1.5 px-2 text-slate-400">6 entities, 40% shared answers</td>'
                '</tr>'
                '</tbody></table>'
            ),
        ),
        P(cls="text-xs text-slate-500 mt-2 leading-relaxed italic")(
            "The method demonstrates entity-specific causal leverage primarily in "
            "single-hop factual domains with low CLT reconstruction error, "
            "with degradation tracking both associative complexity and answer-field coarseness.",
        ),
    )


# -- epistemic status --------------------------------------------------------

def _section_epistemic_status():
    return Div(cls="bg-slate-800/50 rounded-lg p-4 border border-slate-700 space-y-3")(
        H3(cls="text-sm font-semibold text-slate-400 uppercase tracking-wide")(
            "Epistemic Status"
        ),
        Div(cls="space-y-3")(
            _epistemic_level(
                "Level 1 -- Operational Labels",
                "WELL-SUPPORTED",
                "text-emerald-400",
                "The pipeline produces behaviorally grounded, interpretable "
                "supernode groupings. Feature categories are behaviorally "
                "distinct and useful for navigating circuits.",
            ),
            _epistemic_level(
                "Level 2 -- Causal Effects",
                "ESTABLISHED",
                "text-cyan-400",
                "Three lines of evidence: (1) labeled vs random specificity "
                "in 4/5 domains, (2) field-level decomposition showing the "
                "signal resides in semantically appropriate features, "
                "(3) target recovery rate 92% labeled vs 29% random within "
                "disruption regimes.",
            ),
            _epistemic_level(
                "Level 3 -- Mechanistic Explanation",
                "NOT CLAIMED",
                "text-slate-500",
                "Labels are behavioral abstractions, not ontological "
                "identifications. Thresholds have not undergone sensitivity "
                "analysis. Whether categories correspond to natural "
                "computational types remains open.",
            ),
        ),
    )


def _epistemic_level(title, badge_text, badge_color, desc):
    return Div(cls="flex gap-3")(
        Div(cls="flex-shrink-0 mt-0.5")(
            Span(cls=f"text-[10px] px-1.5 py-0.5 rounded font-bold {badge_color} bg-slate-900/60")(
                badge_text
            ),
        ),
        Div()(
            P(cls="text-xs font-medium text-slate-300")(title),
            P(cls="text-xs text-slate-400 leading-relaxed mt-0.5")(desc),
        ),
    )


# -- resources & references --------------------------------------------------

def _about_link(title, desc, url, icon_type):
    icons = {
        'paper': '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>',
        'blog': '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z"></path></svg>',
        'demo': '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>',
        'code': '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path></svg>',
    }
    icon_svg = icons.get(icon_type, icons['code'])
    return A(
        href=url, target="_blank",
        cls="block p-3 bg-slate-800/50 rounded-lg border border-slate-700 hover:border-slate-500 hover:bg-slate-800 transition-all group",
    )(
        Div(cls="flex items-start gap-3")(
            Span(cls="text-slate-500 group-hover:text-cyan-400 transition-colors mt-0.5")(
                NotStr(icon_svg)
            ),
            Div()(
                Div(cls="text-sm font-medium text-slate-200 group-hover:text-white")(title),
                Div(cls="text-xs text-slate-500")(desc),
            ),
        ),
    )


def _section_references():
    return Div(cls="space-y-4")(
        H3(cls="text-sm font-semibold text-slate-400 uppercase tracking-wide")(
            "References"
        ),
        Div(cls="grid grid-cols-2 gap-3 about-links")(
            _about_link("Neuronpedia", "Interactive graph exploration",
                        "https://www.neuronpedia.org/graph/info", "demo"),
            _about_link("Circuit Tracing", "Attribution graphs (Anthropic)",
                        "https://transformer-circuits.pub/2025/attribution-graphs/methods.html",
                        "paper"),
        ),
    )
