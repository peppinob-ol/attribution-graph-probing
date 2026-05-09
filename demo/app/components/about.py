"""
About modal -- detailed methodology and cross-domain validation results.

Static content derived from the paper (41,784 swap runs, 4 evaluation
domains, four experimental conditions).  KPIs are hardcoded: they reflect
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
                "41,784 runs"
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
                "visualizes pairwise steering experiments across 41,784 runs "
                "spanning the four evaluation domains. "
                "Each matrix cell represents an attempt to redirect the model "
                "from a source entity (row) to a target entity (column), using "
                "labeled feature swaps. Cells are colored on a tiered scale "
                "from T5 (target answer produced) to T1 (source persists).",
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
                       f"{dc.get('n_tokens', 10)} tokens, temp {dc.get('temperature', 0.3)}, "
                       f"freq penalty 2.0, seed 42"),
            _param_row("M-search", "adaptive rescue; winning M bimodal at ~2.4 and ~6.9"),
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
            "Four evaluation domains spanning two-hop factual recall in different "
            "relational structures and answer geometries. Each domain has a fixed "
            "seed-prompt template with three semantic fields (input, intermediate, "
            "answer):"
        ),
        # Domain table
        NotStr(
            '<table class="w-full text-xs mt-2">'
            '<thead><tr class="border-b border-slate-700">'
            '<th class="text-left py-1.5 px-2 text-slate-500">Domain</th>'
            '<th class="text-left py-1.5 px-2 text-slate-500">Seed Prompt</th>'
            '<th class="text-right py-1.5 px-2 text-slate-500">Entities</th>'
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
            '  <td class="py-1.5 px-2 text-right text-slate-400">10</td>'
            '  <td class="py-1.5 px-2 text-right text-slate-300">90</td>'
            '</tr>'
            '<tr class="border-b border-slate-800">'
            '  <td class="py-1.5 px-2 text-slate-300 font-medium">Products</td>'
            '  <td class="py-1.5 px-2 text-slate-400">"The company that makes {product} was founded by"</td>'
            '  <td class="py-1.5 px-2 text-right text-slate-400">12</td>'
            '  <td class="py-1.5 px-2 text-right text-slate-300">132</td>'
            '</tr>'
            '<tr>'
            '  <td class="py-1.5 px-2 text-slate-300 font-medium">Paintings</td>'
            '  <td class="py-1.5 px-2 text-slate-400">"The first name of the painter of {painting} is"</td>'
            '  <td class="py-1.5 px-2 text-right text-slate-400">10</td>'
            '  <td class="py-1.5 px-2 text-right text-slate-300">90</td>'
            '</tr>'
            '</tbody></table>'
        ),
        P(cls="text-slate-500 text-xs mt-2 leading-relaxed")(
            "Each pair runs under four conditions: ",
            Span(cls="text-cyan-400")("labeled"),
            " 3-field baseline at M=20, ",
            Span(cls="text-purple-400")("matched-random"),
            " controls (3 replicates per pair, same feature count and per-layer "
            "histogram, sampled outside concept-aligned supernodes), ",
            Span(cls="text-slate-300")("field-additivity"),
            " variants (7 subsets of the three concept fields), and ",
            Span(cls="text-emerald-400")("adaptive M-search"),
            " (rescue passes for missed pairs). Total: 41,784 swap runs.",
        ),
    )


# -- cross-domain results (static) ------------------------------------------

_RESULTS = [
    # domain, N, hit_ours, vsmax_ours, hit_rand, vsmax_rand, hit_topk, vsmax_topk
    ("USA States", "2,450", "72.8%", "+6.15",  "0.7%", "-1.23",  "4.2%", "-1.92"),
    ("Books",      "90",    "77.8%", "+10.38", "0.0%", "+0.19",  "4.4%", "+1.57"),
    ("Products",   "132",   "41.7%", "+5.42",  "7.6%", "+1.17",  "1.1%", "+0.63"),
    ("Paintings",  "90",    "18.9%", "+3.45",  "1.1%", "+1.27",  "7.1%", "+0.16"),
]


def _section_cross_domain_results():
    rows_html = ""
    for d, n, h_ours, v_ours, h_rnd, v_rnd, h_top, v_top in _RESULTS:
        rows_html += (
            f'<tr class="border-b border-slate-800">'
            f'  <td class="py-1.5 px-2 text-slate-300 font-medium">{d}</td>'
            f'  <td class="py-1.5 px-2 text-right text-slate-400">{n}</td>'
            f'  <td class="py-1.5 px-2 text-right text-cyan-400 font-mono">{h_ours}</td>'
            f'  <td class="py-1.5 px-2 text-right text-cyan-400 font-mono">{v_ours}</td>'
            f'  <td class="py-1.5 px-2 text-right text-red-400/70 font-mono">{h_rnd}</td>'
            f'  <td class="py-1.5 px-2 text-right text-red-400/70 font-mono">{v_rnd}</td>'
            f'  <td class="py-1.5 px-2 text-right text-purple-400/80 font-mono">{h_top}</td>'
            f'  <td class="py-1.5 px-2 text-right text-purple-400/80 font-mono">{v_top}</td>'
            f'</tr>'
        )

    return Div(cls="bg-slate-800/50 rounded-lg p-4 border border-slate-700 space-y-3")(
        Div(cls="flex items-center justify-between")(
            H3(cls="text-sm font-semibold text-slate-400 uppercase tracking-wide")(
                "Cross-Domain Headline"
            ),
            Span(cls="text-[10px] text-slate-500 font-mono")(
                "harness vs matched-random vs influence-matched top-K"
            ),
        ),
        P(cls="text-slate-400 text-xs leading-relaxed")(
            Span(cls="text-cyan-400 font-medium")("Ours"), ": per-pair best "
            "field-additivity variant with adaptive M-search on labeled features. ",
            Span(cls="text-red-400/80 font-medium")("Rand."),
            ": matched-random control under the same per-pair best-of "
            "(3 replicates x {default, M-tuned}) construction -- same feature "
            "count and per-layer histogram, sampled outside concept-aligned "
            "supernodes. ",
            Span(cls="text-purple-400 font-medium")("Top-K"),
            ": influence-matched top-K-by-graph-influence baseline with "
            "adaptive M-search. Books and Paintings use the 10-entity / "
            "90-pair demo intersection so the Top-K coverage is symmetric.",
        ),
        # Primary metrics table
        Div(cls="overflow-x-auto")(
            NotStr(
                '<table class="w-full text-xs">'
                '<thead><tr class="border-b border-slate-700">'
                '<th class="text-left py-1.5 px-2 text-slate-500" rowspan="2">Domain</th>'
                '<th class="text-right py-1.5 px-2 text-slate-500" rowspan="2">N</th>'
                '<th class="text-center py-1 px-2 text-slate-500 border-b border-slate-700" colspan="2">Ours (FA+M-srch)</th>'
                '<th class="text-center py-1 px-2 text-slate-500 border-b border-slate-700" colspan="2">Rand. +M-srch</th>'
                '<th class="text-center py-1 px-2 text-slate-500 border-b border-slate-700" colspan="2">Top-K</th>'
                '</tr><tr class="border-b border-slate-700">'
                '<th class="text-right py-1 px-2 text-cyan-500/70 text-[10px]">Hit%</th>'
                '<th class="text-right py-1 px-2 text-cyan-500/70 text-[10px]">vsMax</th>'
                '<th class="text-right py-1 px-2 text-red-400/60 text-[10px]">Hit%</th>'
                '<th class="text-right py-1 px-2 text-red-400/60 text-[10px]">vsMax</th>'
                '<th class="text-right py-1 px-2 text-purple-400/70 text-[10px]">Hit%</th>'
                '<th class="text-right py-1 px-2 text-purple-400/70 text-[10px]">vsMax</th>'
                '</tr></thead><tbody>'
                + rows_html +
                '</tbody></table>'
            ),
        ),
        # Key takeaway
        Div(cls="mt-2 text-xs text-slate-400 leading-relaxed bg-slate-900/50 rounded p-2.5 border-l-2 border-cyan-600")(
            Span(cls="text-cyan-400 font-medium")("Key finding: "),
            "labeled supernodes pass the operational test in all four domains. "
            "The labeled--random Hit% gap is at least 11pp in every domain even "
            "after applying M-search to the random side, and the labeled--random "
            "vsMax gap is at least +0.2 in every domain. Influence-matched top-K "
            "underperforms the labeled bag despite using the same per-pair "
            "graph-influence budget, so the steering signal is distributed "
            "across the labeled feature set rather than concentrated in the "
            "highest-influence nodes.",
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
    ("USA States", "state + capital",   "mid+ans", "38.8%", "24.7%", "+14.1pp"),
    ("Books",      "book + author",     "mid+ans", "37.1%", "3.8%",  "+33.3pp"),
    ("Products",   "company + founder", "mid+ans", "24.2%", "15.2%", "+9.0pp"),
    ("Paintings",  "first_name (1-fld)", "ans",    "6.7%",  "3.3%",  "+3.4pp"),
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
            "answer (what the model produces). Numbers below are Best-subset "
            "Hit% vs the all-3-field labeled baseline, both at M=20. "
            "In 3 of 4 domains, intermediate+answer carry the strongest signal; "
            "including input-field features dilutes the redirection signal.",
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
            "at position 0 relative to their unsteered baselines. Four regimes "
            "matter for interpretation:"
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
                '</tr></thead><tbody>'
                '<tr class="border-b border-slate-800">'
                '  <td class="py-1.5 px-2 font-bold text-emerald-400">A</td>'
                '  <td class="py-1.5 px-2 text-emerald-400">UP</td>'
                '  <td class="py-1.5 px-2 text-red-400">DOWN</td>'
                '  <td class="py-1.5 px-2 text-emerald-400">yes</td>'
                '  <td class="py-1.5 px-2 text-slate-300">Clean redirection</td>'
                '</tr>'
                '<tr class="border-b border-slate-800">'
                '  <td class="py-1.5 px-2 font-bold text-yellow-400">C</td>'
                '  <td class="py-1.5 px-2 text-red-400">DOWN</td>'
                '  <td class="py-1.5 px-2 text-red-400">DOWN</td>'
                '  <td class="py-1.5 px-2 text-emerald-400">yes</td>'
                '  <td class="py-1.5 px-2 text-slate-300">Differential disruption</td>'
                '</tr>'
                '<tr class="border-b border-slate-800">'
                '  <td class="py-1.5 px-2 font-bold text-red-400">D</td>'
                '  <td class="py-1.5 px-2 text-red-400">DOWN</td>'
                '  <td class="py-1.5 px-2 text-red-400">DOWN</td>'
                '  <td class="py-1.5 px-2 text-red-400">no</td>'
                '  <td class="py-1.5 px-2 text-slate-300">Generic disruption</td>'
                '</tr>'
                '<tr>'
                '  <td class="py-1.5 px-2 font-bold text-slate-400">E</td>'
                '  <td class="py-1.5 px-2 text-slate-500">FLAT</td>'
                '  <td class="py-1.5 px-2 text-red-400">DOWN</td>'
                '  <td class="py-1.5 px-2 text-emerald-400">yes</td>'
                '  <td class="py-1.5 px-2 text-slate-300">Pure suppression</td>'
                '</tr>'
                '</tbody></table>'
            ),
        ),
        # Regime A / D prevalence per domain (paper appx:regime, tab:regime-prev)
        P(cls="text-xs text-slate-500 mt-2")(
            "Regime A (clean redirection) and Regime D (generic disruption) "
            "prevalence under three conditions: best field-additivity variant, "
            "full labeled (M=20, all three fields), and the symmetric matched-"
            "random control under per-pair best-of (3 replicates x adaptive M):"
        ),
        Div(cls="overflow-x-auto mt-1")(
            NotStr(
                '<table class="w-full text-xs">'
                '<thead><tr class="border-b border-slate-700">'
                '<th class="text-left py-1 px-2 text-slate-500" rowspan="2">Domain</th>'
                '<th class="text-center py-1 px-2 text-slate-500 border-b border-slate-700" colspan="3">Regime A %</th>'
                '<th class="text-center py-1 px-2 text-slate-500 border-b border-slate-700" colspan="3">Regime D %</th>'
                '</tr><tr class="border-b border-slate-700">'
                '<th class="text-right py-1 px-2 text-cyan-500/70 text-[10px]">Best</th>'
                '<th class="text-right py-1 px-2 text-purple-400/70 text-[10px]">Labeled</th>'
                '<th class="text-right py-1 px-2 text-red-400/60 text-[10px]">Rand+M</th>'
                '<th class="text-right py-1 px-2 text-cyan-500/70 text-[10px]">Best</th>'
                '<th class="text-right py-1 px-2 text-purple-400/70 text-[10px]">Labeled</th>'
                '<th class="text-right py-1 px-2 text-red-400/60 text-[10px]">Rand+M</th>'
                '</tr></thead><tbody>'
                '<tr class="border-b border-slate-800">'
                '  <td class="py-1 px-2 text-slate-300">USA</td>'
                '  <td class="py-1 px-2 text-right font-mono text-cyan-400">34.9</td>'
                '  <td class="py-1 px-2 text-right font-mono text-purple-400">8.9</td>'
                '  <td class="py-1 px-2 text-right font-mono text-red-400/70">15.3</td>'
                '  <td class="py-1 px-2 text-right font-mono text-cyan-400">9.1</td>'
                '  <td class="py-1 px-2 text-right font-mono text-purple-400">19.4</td>'
                '  <td class="py-1 px-2 text-right font-mono text-red-400/70">38.7</td>'
                '</tr>'
                '<tr class="border-b border-slate-800">'
                '  <td class="py-1 px-2 text-slate-300">Books</td>'
                '  <td class="py-1 px-2 text-right font-mono text-cyan-400">62.1</td>'
                '  <td class="py-1 px-2 text-right font-mono text-purple-400">38.8</td>'
                '  <td class="py-1 px-2 text-right font-mono text-red-400/70">26.7</td>'
                '  <td class="py-1 px-2 text-right font-mono text-cyan-400">3.3</td>'
                '  <td class="py-1 px-2 text-right font-mono text-purple-400">3.3</td>'
                '  <td class="py-1 px-2 text-right font-mono text-red-400/70">34.4</td>'
                '</tr>'
                '<tr class="border-b border-slate-800">'
                '  <td class="py-1 px-2 text-slate-300">Products</td>'
                '  <td class="py-1 px-2 text-right font-mono text-cyan-400">62.1</td>'
                '  <td class="py-1 px-2 text-right font-mono text-purple-400">56.8</td>'
                '  <td class="py-1 px-2 text-right font-mono text-red-400/70">28.8</td>'
                '  <td class="py-1 px-2 text-right font-mono text-cyan-400">2.3</td>'
                '  <td class="py-1 px-2 text-right font-mono text-purple-400">2.3</td>'
                '  <td class="py-1 px-2 text-right font-mono text-red-400/70">18.9</td>'
                '</tr>'
                '<tr>'
                '  <td class="py-1 px-2 text-slate-300">Paintings</td>'
                '  <td class="py-1 px-2 text-right font-mono text-cyan-400">47.8</td>'
                '  <td class="py-1 px-2 text-right font-mono text-purple-400">17.8</td>'
                '  <td class="py-1 px-2 text-right font-mono text-red-400/70">16.7</td>'
                '  <td class="py-1 px-2 text-right font-mono text-cyan-400">2.2</td>'
                '  <td class="py-1 px-2 text-right font-mono text-purple-400">6.7</td>'
                '  <td class="py-1 px-2 text-right font-mono text-red-400/70">36.7</td>'
                '</tr>'
                '</tbody></table>'
            ),
        ),
        Div(cls="mt-2 text-xs text-slate-400 leading-relaxed bg-slate-900/50 rounded p-2.5 border-l-2 border-yellow-600")(
            "The best variant pushes many more cases into regime A (clean "
            "redirection) than full labeled does (USA: 8.9 -> 34.9%; Books: "
            "38.8 -> 62.1%); removing input-field features eliminates the "
            "generic disruption that was pushing cases into regime C/D. "
            "The symmetric matched-random + M-search control concentrates in "
            "regime D (35-39% in USA, Books, Paintings) -- this is why vsMax "
            "separates labeled from random even when both produce high "
            "suppression rates. Within USA regime C, labeled features show a "
            "92% vs 29% target-recovery gap over random; this signal does ",
            Span(cls="text-slate-300 italic")("not"),
            " generalize -- in Books regime C the same gap collapses to "
            "92% vs 89%, so target-recovery is treated as a supporting "
            "within-regime signal rather than a primary metric.",
        ),
    )


# -- domain gradient ---------------------------------------------------------

def _section_domain_gradient():
    return Div(cls="bg-slate-800/50 rounded-lg p-4 border border-slate-700 space-y-3")(
        H3(cls="text-sm font-semibold text-slate-400 uppercase tracking-wide")(
            "Domain Gradient & Operating Envelope"
        ),
        P(cls="text-slate-400 text-xs leading-relaxed")(
            "Labeled--random vsMax gap (logit margin over the strongest "
            "competing dataset answer) at the default operating point "
            "(all-3-fields, M=20, per-replicate matched-random control). "
            "Specificity tracks associative complexity and answer-field "
            "coarseness, not graph size:"
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
                '  <td class="py-1.5 px-2 text-slate-400">small answer space, distinctive author signatures</td>'
                '</tr>'
                '<tr class="border-b border-slate-800">'
                '  <td class="py-1.5 px-2 text-slate-300">USA States</td>'
                '  <td class="py-1.5 px-2 text-right font-mono text-cyan-400">+5.17</td>'
                '  <td class="py-1.5 px-2 text-emerald-400">Strong</td>'
                '  <td class="py-1.5 px-2 text-slate-400">large N, high scaffold compatibility</td>'
                '</tr>'
                '<tr class="border-b border-slate-800">'
                '  <td class="py-1.5 px-2 text-slate-300">Products</td>'
                '  <td class="py-1.5 px-2 text-right font-mono text-cyan-400">+3.23</td>'
                '  <td class="py-1.5 px-2 text-yellow-400">Moderate</td>'
                '  <td class="py-1.5 px-2 text-slate-400">moderate scaffold, mid relational complexity</td>'
                '</tr>'
                '<tr>'
                '  <td class="py-1.5 px-2 text-slate-300">Paintings</td>'
                '  <td class="py-1.5 px-2 text-right font-mono text-slate-400">+1.58</td>'
                '  <td class="py-1.5 px-2 text-orange-400">Weak</td>'
                '  <td class="py-1.5 px-2 text-slate-400">multi-step inference, coarse first-name answer</td>'
                '</tr>'
                '</tbody></table>'
            ),
        ),
        P(cls="text-xs text-slate-500 mt-2 leading-relaxed italic")(
            "Under the symmetric matched-random + M-search harness the same "
            "ordering holds (Books +6.5, USA +4.1, Products +2.3, Paintings "
            "+0.2). The cross-domain ordering matches the operational-"
            "usefulness verdict, which is why vsMax serves as a primary "
            "metric rather than a diagnostic.",
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
                "Three lines of evidence across 4/4 evaluation domains: "
                "(1) labeled--random Hit% gap >= 11pp and labeled--random "
                "vsMax gap >= +0.2 in every domain, even after symmetric "
                "M-search on the random side; (2) field-level decomposition "
                "shows the signal concentrates in intermediate+answer features "
                "(9-33pp Hit% gain over all-3-fields); (3) the best variant "
                "concentrates in regime A (clean redirection, 35-62% per "
                "domain) while matched-random concentrates in regime D "
                "(generic disruption, 35-39% in 3/4 domains).",
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
