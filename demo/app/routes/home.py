"""
Home page route - main matrix view
"""
from fasthtml.common import (
    Html, Head, Body, Title, Link, Script, Meta,
    Div, H1, H2, H3, P, A, Button, Span, Main, Header, Footer, Nav,
    Section, Article, Aside, Ul, Li, NotStr, Select, Option
)


def home_routes(app, rt, data_loader, annotate_mode: bool = False, registry=None):
    """Register home page routes."""
    
    @rt("/")
    def home():
        """Main page with matrix visualization."""
        stats = data_loader.get_stats()
        analysis = data_loader.get_analysis()
        insights = analysis.get('insights', [])
        dc = data_loader.get_domain_config()
        page_title = dc.get('display_name', 'Swap Explorer')
        is_usa = dc.get('is_usa_states', True)
        
        aggregate = stats.get('aggregate', {})
        perfect_rate = aggregate.get('perfect_rate', 0) * 100
        state_correct_rate = aggregate.get('state_correct_rate', 0) * 100
        suppression_rate = aggregate.get('suppression_rate', 0) * 100
        flip_at_01_rate = aggregate.get('flip_at_01_rate', 0) * 100
        has_flip_data = aggregate.get('flip_tracked', 0) > 0
        
        # Annotation mode badge
        annotate_badge = Span(cls="text-xs px-2 py-1 bg-amber-900/50 text-amber-400 rounded-full ml-2 animate-pulse")(
            "ANNOTATE MODE"
        ) if annotate_mode else None
        
        return Html(
            Head(
                Title(f"{page_title} - Swap Explorer"),
                Meta(charset="UTF-8"),
                Meta(name="viewport", content="width=device-width, initial-scale=1.0"),
                Link(rel="stylesheet", href="/static/css/tailwind.css"),
                Link(rel="preconnect", href="https://fonts.googleapis.com"),
                Link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin=""),
                Link(
                    rel="stylesheet",
                    href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
                ),
            ),
            Body(
                cls="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-white font-sans",
                **{"data-annotate-mode": "true" if annotate_mode else "false"}
            )(
                # Header
                Header(cls="border-b border-slate-800 bg-slate-900/50 backdrop-blur-sm sticky top-0 z-50")(
                    Div(cls="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between")(
                        Div(cls="flex items-center gap-4")(
                            H1(
                                cls="text-2xl font-bold bg-clip-text text-transparent mobile-title",
                                style="background-image: linear-gradient(to right, #0A4FFF, #3D7DFF);"
                            )(
                                f"{page_title} Swap Explorer"
                            ),
                            Span(cls="text-xs px-2 py-1 bg-slate-800 rounded-full text-slate-400 hidden-mobile")(
                                "Circuit Steering Demo"
                            ),
                            annotate_badge,
                        ),
                        Nav(cls="flex items-center gap-4")(
                            # Run selector dropdown (groups by dataset when registry is active)
                            _run_selector(data_loader, registry=registry),
                            Button(
                                id="about-btn",
                                cls="text-slate-300 hover:text-white transition-colors"
                            )("About"),
                            A(
                                href="https://arxiv.org/abs/2511.07002",
                                target="_blank",
                                cls="text-slate-400 hover:text-white transition-colors hidden-mobile"
                            )("arXiv"),
                            A(
                                href="https://github.com/peppinob-ol/circuit_tracer-prompt_rover",
                                target="_blank",
                                cls="text-slate-400 hover:text-white transition-colors hidden-mobile"
                            )("GitHub"),
                        ),
                    ),
                ),
                
                # Main content
                Main(cls="max-w-7xl mx-auto px-4 py-8")(
                    # Stats bar
                    Div(
                        id="kpi-bar",
                        cls="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8",
                        style=f"--kpi-cols: {5 if has_flip_data else 4};",
                    )(
                        *_kpi_cards(stats, perfect_rate, state_correct_rate,
                                    suppression_rate, flip_at_01_rate, has_flip_data),
                    ),
                    
                    # Main grid
                    Div(cls="grid grid-cols-1 lg:grid-cols-4 gap-8")(
                        # Matrix container (3 cols)
                        Div(cls="lg:col-span-3")(
                            Div(cls="bg-slate-900/50 rounded-xl border border-slate-800 p-6")(
                                Div(cls="flex items-center justify-between mb-6")(
                                    H2(cls="text-xl font-semibold")("Steering Matrix"),
                                    Div(cls="flex items-center gap-2")(
                                        Span(cls="text-xs text-slate-500")("Click cell for details"),
                                    ),
                                ),
                                # Matrix island mount point
                                Div(
                                    id="matrix-container",
                                    cls="relative",
                                    **{"data-api-url": "/api/matrix"}
                                )(
                                    Div(cls="text-center py-20 text-slate-500")(
                                        P("Loading matrix..."),
                                    ),
                                ),
                            ),
                        ),
                        
                        # Sidebar (1 col)
                        Aside(cls="space-y-6")(
                            # Legend with toggle
                            Div(cls="bg-slate-900/50 rounded-xl border border-slate-800 px-3 py-4")(
                                # Toggle switch
                                Div(cls="flex items-center justify-between gap-3 mb-2")(
                                    H3(
                                        id="legend-title",
                                        cls="text-sm font-semibold text-slate-400"
                                    )("TIER LEGEND"),
                                    Div(cls="flex items-center gap-3")(
                                        Span(
                                            id="color-mode-label-tier",
                                            cls="text-[10px] font-medium text-cyan-400",
                                        )("Tier"),
                                        Button(
                                            id="color-mode-toggle",
                                            cls="relative ml-1 mr-2 inline-flex h-5 w-9 flex-shrink-0 cursor-pointer items-center rounded-full border transition-colors focus:outline-none",
                                            style="background-color: #1e293b; border-color: #475569; box-shadow: inset 0 0 0 1px rgba(15, 23, 42, 0.35);",
                                            role="switch",
                                            **{"aria-checked": "false"},
                                        )(
                                            Span(
                                                id="color-mode-knob",
                                                cls="pointer-events-none inline-block h-4 w-4 rounded-full shadow-lg transition-transform",
                                                style="background-color: #22d3ee; transform: translateX(1px);",
                                            ),
                                        ),
                                        Span(
                                            id="color-mode-label-flip",
                                            cls="text-[10px] font-medium text-slate-500",
                                        )("Flip"),
                                    ),
                                ),
                                # Tier legend (shown by default)
                                Div(id="tier-legend", cls="space-y-2")(
                                    _legend_item("T5", "PERFECT", "#0A4FFF"),
                                    _legend_item("T4", "Partial + Answer", "#3D7DFF"),
                                    _legend_item("T3", "Partial", "#AFCBFF"),
                                    _legend_item("W", "Wrong Answer", "#FFE8E8"),
                                    _legend_item("T2", "Suppressed", "#FF7373"),
                                    _legend_item("T1", "Source Persists", "#C00000"),
                                ),
                                # Flip legend (hidden by default)
                                Div(id="flip-legend", cls="space-y-2", style="display: none;")(
                                    _legend_item("@0", "Immediate flip", "#10b981"),
                                    _legend_item("@1", "Flip at pos 1", "#34d399"),
                                    _legend_item("@2", "Flip at pos 2", "#a3e635"),
                                    _legend_item("@3", "Flip at pos 3", "#facc15"),
                                    _legend_item("@4+", "Late flip", "#fb923c"),
                                    _legend_item("Never", "No flip", "#7f1d1d"),
                                    _legend_item("--", "No trajectory data", "#1e293b"),
                                ),
                            ),
                            
                            # Insights
                            Div(cls="bg-slate-900/50 rounded-xl border border-slate-800 p-4")(
                                H3(cls="text-sm font-semibold text-slate-400 mb-3")("KEY INSIGHTS"),
                                Ul(cls="space-y-2 text-sm text-slate-300")(
                                    *[Li(cls="flex items-start gap-2")(
                                        Span(cls="text-emerald-400 mt-0.5")("*"),
                                        insight
                                    ) for insight in insights[:4]]
                                ),
                            ),
                            
                            # Tier distribution
                            Div(cls="bg-slate-900/50 rounded-xl border border-slate-800 p-4")(
                                H3(cls="text-sm font-semibold text-slate-400 mb-3")("TIER DISTRIBUTION"),
                                Div(cls="space-y-2")(
                                    *[_tier_bar(tier, count, stats.get('total_swaps', 1))
                                      for tier, count in sorted(stats.get('tier_counts', {}).items(), 
                                                               key=lambda x: x[0], reverse=True)]
                                ),
                            ),
                        ),
                    ),
                ),
                
                # Detail panel mount point
                Div(id="detail-panel"),
                
                # State card mount point
                Div(id="state-card-mount"),
                
                # About modal
                Div(
                    id="about-modal",
                    cls="fixed inset-0 z-[100] bg-black/70 backdrop-blur-sm flex items-start justify-center",
                    style="display: none; padding: 5.5rem 1.5rem 2rem 1.5rem;"
                )(
                    Div(cls="bg-slate-900 border border-slate-700 rounded-xl max-w-2xl w-full shadow-2xl flex flex-col", style="max-height: calc(100vh - 8rem);")(
                        # Modal header (fixed)
                        Div(cls="flex-shrink-0 bg-slate-900 border-b border-slate-800 rounded-t-xl flex items-center justify-between", style="padding: 1.25rem 2rem;")(
                            H2(cls="text-xl font-semibold text-white")("About This Experiment"),
                            Button(
                                id="about-close",
                                cls="text-slate-400 hover:text-white text-2xl leading-none"
                            )("x"),
                        ),
                        # Modal content (scrollable)
                        Div(cls="flex-1 overflow-y-auto space-y-6", style="padding: 1.5rem 2rem 2.5rem 2rem;")(
                            # Intro
                            Div(cls="space-y-3")(
                                P(cls="text-slate-300 leading-relaxed")(
                                    "An interactive demo exploring whether ",
                                    Span(cls="text-cyan-400 font-medium")("internal-state swaps"),
                                    " can redirect model outputs from one concept to another."
                                ),
                                P(cls="text-slate-400 text-sm leading-relaxed")(
                                    "The matrix visualizes pairwise steering experiments. ",
                                    "Each cell represents an attempt to redirect the model from a source entity (row) to a target entity (column), ",
                                    "evaluated on a tiered scale from T5 (perfect redirection) to T1 (source persists)."
                                ),
                                P(cls="text-slate-400 text-sm leading-relaxed")(
                                    "This is a working investigation into the geometry and causal structure of concept steering in LLMs, ",
                                    "with focus on how latent representations respond to controlled interventions."
                                ),
                            ),
                            # Steering method
                            Div(cls="bg-slate-800/50 rounded-lg p-4 border border-slate-700")(
                                H3(cls="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-3")("Steering Method"),
                                P(cls="text-slate-300 text-sm leading-relaxed mb-2")(
                                    "Each swap uses ",
                                    A(href="https://www.lesswrong.com/posts/zQqGhKPqaCBZZDCge/automated-circuit-interpretation-via-probe-prompting", target="_blank", cls="text-cyan-400 hover:underline")("Probe Prompting"),
                                    " to identify concept-related features via CLT transcoders. We then use ",
                                    A(href="https://github.com/safety-research/circuit-tracer", target="_blank", cls="text-cyan-400 hover:underline")("Circuit Tracer"),
                                    " to suppress source activations while amplifying target features during generation."
                                ),
                                P(cls="text-slate-500 text-xs mb-3")(
                                    "Model: ",
                                    Span(cls="text-slate-400")(dc.get('model_id', '') or "N/A"),
                                ),
                                Div(cls="font-mono text-xs bg-slate-900/50 rounded p-3 space-y-1")(
                                    Div(cls="flex items-center gap-3")(
                                        Span(cls="text-slate-500 w-28")("Source features"),
                                        Span(cls="text-red-400")(f"ablate {dc.get('m_ablate', -2)}x"),
                                        Span(cls="text-slate-600 text-[10px]")("(reverse direction)"),
                                    ),
                                    Div(cls="flex items-center gap-3")(
                                        Span(cls="text-slate-500 w-28")("Target features"),
                                        Span(cls="text-emerald-400")(f"amplify +{dc.get('m_amplify', 20)}x"),
                                        Span(cls="text-slate-600 text-[10px]")("(boost activation)"),
                                    ),
                                    Div(cls="flex items-center gap-3")(
                                        Span(cls="text-slate-500 w-28")("Generation"),
                                        Span(cls="text-slate-300")(f"{dc.get('n_tokens', 10)} tokens, temp {dc.get('temperature', 0.3)}"),
                                    ),
                                ),
                            ),
                            # Links section
                            Div(cls="space-y-4")(
                                H3(cls="text-sm font-semibold text-slate-400 uppercase tracking-wide")("Resources"),
                                Div(cls="grid grid-cols-2 gap-3 about-links")(
                                    _about_link(
                                        "arXiv Preprint",
                                        "Full paper with methods & results",
                                        "https://arxiv.org/abs/2511.07002",
                                        "paper"
                                    ),
                                    _about_link(
                                        "LessWrong Post",
                                        "Discussion & community feedback",
                                        "https://www.lesswrong.com/posts/zQqGhKPqaCBZZDCge",
                                        "blog"
                                    ),
                                    _about_link(
                                        "HuggingFace Demo",
                                        "Try probe-prompting yourself",
                                        "https://huggingface.co/spaces/Peppinob/attribution-graph-probing",
                                        "demo"
                                    ),
                                    _about_link(
                                        "GitHub Repo",
                                        "Probe-prompting pipeline code",
                                        "https://github.com/peppinob-ol/attribution-graph-probing",
                                        "code"
                                    ),
                                ),
                            ),
                            # References
                            Div(cls="space-y-4")(
                                H3(cls="text-sm font-semibold text-slate-400 uppercase tracking-wide")("References"),
                                Div(cls="grid grid-cols-2 gap-3 about-links")(
                                    _about_link(
                                        "Neuronpedia",
                                        "Interactive graph exploration",
                                        "https://www.neuronpedia.org/graph/info",
                                        "demo"
                                    ),
                                    _about_link(
                                        "Circuit Tracing",
                                        "Attribution graphs (Anthropic)",
                                        "https://transformer-circuits.pub/2025/attribution-graphs/methods.html",
                                        "paper"
                                    ),
                                ),
                            ),
                            # Author
                            Div(cls="border-t border-slate-800 pt-4")(
                                P(cls="text-xs text-slate-500")(
                                    "Built by ",
                                    A(
                                        href="https://www.linkedin.com/in/giuseppe-birardi-18a7b011/",
                                        target="_blank",
                                        cls="text-slate-400 hover:text-white"
                                    )("Giuseppe Birardi"),
                                    " | Orma Lab Srl"
                                ),
                            ),
                            Div(cls="border-t border-slate-800 pt-4")(
                                P(cls="text-xs text-slate-500")(
                                    "Thanks to ",
                                    A(
                                        href="https://www.eleuther.ai/",
                                        target="_blank",
                                        cls="text-slate-400 hover:text-white"
                                    )("eleuther.ai"),
                                    " for infrastructure"
                                ),
                            ),                            
                        ),
                    ),
                ),
                
                # Scripts
                Script(src="/static/islands/islands.js?v=12", type="module"),
                # Run selector script (handles cross-dataset switching)
                Script("""
                    (function() {
                        var sel = document.getElementById('run-selector');
                        if (!sel) return;
                        sel.addEventListener('change', async function(e) {
                            sel.disabled = true;
                            sel.style.opacity = '0.5';
                            try {
                                var r = await fetch('/api/runs/' + e.target.value, {
                                    method: 'POST'
                                });
                                if (r.ok) { window.location.href = '/?t=' + Date.now(); }
                                else { sel.disabled = false; sel.style.opacity = '1'; }
                            } catch (_) { sel.disabled = false; sel.style.opacity = '1'; }
                        });
                    })();
                """),
                # Color mode toggle script
                Script("""
                    (function() {
                        var toggle = document.getElementById('color-mode-toggle');
                        var knob   = document.getElementById('color-mode-knob');
                        var lblT   = document.getElementById('color-mode-label-tier');
                        var lblF   = document.getElementById('color-mode-label-flip');
                        var title  = document.getElementById('legend-title');
                        var tierLeg = document.getElementById('tier-legend');
                        var flipLeg = document.getElementById('flip-legend');
                        var mode = 'tier';

                        if (!toggle) return;

                        function apply() {
                            var isFlip = mode === 'flip';
                            toggle.style.backgroundColor = isFlip ? '#064e3b' : '#1e293b';
                            toggle.style.borderColor = isFlip ? '#10b981' : '#475569';
                            toggle.setAttribute('aria-checked', String(isFlip));
                            knob.style.transform = isFlip ? 'translateX(18px)' : 'translateX(1px)';
                            knob.style.backgroundColor = isFlip ? '#34d399' : '#22d3ee';
                            lblT.style.color = isFlip ? '#64748b' : '#22d3ee';
                            lblF.style.color = isFlip ? '#10b981' : '#64748b';
                            title.textContent = isFlip ? 'FLIP POSITION' : 'TIER LEGEND';
                            tierLeg.style.display = isFlip ? 'none' : '';
                            flipLeg.style.display = isFlip ? '' : 'none';
                            document.dispatchEvent(new CustomEvent('color-mode-changed', {
                                detail: { mode: mode }, bubbles: true
                            }));
                        }

                        toggle.onclick = function() {
                            mode = mode === 'tier' ? 'flip' : 'tier';
                            apply();
                        };
                    })();
                """),
                # About modal script
                Script("""
                    (function() {
                        const modal = document.getElementById('about-modal');
                        const openBtn = document.getElementById('about-btn');
                        const closeBtn = document.getElementById('about-close');
                        
                        function resetMatrixCells() {
                            // Reset any selected/highlighted matrix cells
                            document.querySelectorAll('.matrix-cell').forEach(function(cell) {
                                cell.style.transform = '';
                                cell.style.zIndex = '';
                                cell.style.boxShadow = '';
                                cell.style.outline = '';
                                cell.style.outlineOffset = '';
                                cell.classList.remove('selected');
                            });
                        }
                        
                        if (openBtn) {
                            openBtn.onclick = function() {
                                resetMatrixCells();
                                modal.style.display = 'flex';
                            };
                        }
                        
                        if (closeBtn) {
                            closeBtn.onclick = function() {
                                modal.style.display = 'none';
                            };
                        }
                        
                        if (modal) {
                            modal.onclick = function(e) {
                                if (e.target === modal) {
                                    modal.style.display = 'none';
                                }
                            };
                        }
                        
                        document.onkeydown = function(e) {
                            if (e.key === 'Escape' && modal && modal.style.display === 'flex') {
                                modal.style.display = 'none';
                            }
                        };
                    })();
                """),
            ),
        )


def _kpi_cards(stats, perfect_rate, state_correct_rate,
               suppression_rate, flip_at_01_rate, has_flip_data):
    """Build the list of KPI stat cards (4 or 5 depending on flip data)."""
    cards = [
        _stat_card("Total Swaps", str(stats.get('total_swaps', 0)),
                    "experiments", value_id="kpi-total"),
        _stat_card("Perfect (T5)", f"{perfect_rate:.0f}%",
                    "target capital found", value_id="kpi-perfect"),
        _stat_card("State Correct", f"{state_correct_rate:.0f}%",
                    "T3+ success", value_id="kpi-correct"),
        _stat_card("Suppression", f"{suppression_rate:.0f}%",
                    "source removed", value_id="kpi-suppress"),
    ]
    if has_flip_data:
        cards.append(
            _stat_card("Logit Flip @0-1", f"{flip_at_01_rate:.0f}%",
                        "flip at pos 0 or 1", value_id="kpi-flip01"),
        )
    return cards


def _stat_card(title: str, value: str, subtitle: str, value_id: str = ""):
    """Render a stat card."""
    value_attrs = {"cls": "text-2xl font-bold mt-1 stat-value"}
    if value_id:
        value_attrs["id"] = value_id
    return Div(cls="bg-slate-900/50 rounded-xl border border-slate-800 p-4")(
        P(cls="text-xs text-slate-500 uppercase tracking-wide")(title),
        P(**value_attrs)(value),
        P(cls="text-xs text-slate-400 mt-1")(subtitle),
    )


def _legend_item(tier: str, label: str, color: str):
    """Render a legend item with hex color."""
    return Div(cls="flex items-center gap-2")(
        Div(cls="w-4 h-4 rounded", style=f"background-color: {color};"),
        Span(cls="text-xs text-slate-300")(f"{tier}: {label}"),
    )


def _tier_bar(tier_name: str, count: int, total: int):
    """Render a tier distribution bar."""
    pct = (count / total * 100) if total > 0 else 0
    tier_colors = {
        'PERFECT': '#0A4FFF',
        'TARGET_STATE_CITY': '#3D7DFF',
        'TARGET_STATE_ONLY': '#AFCBFF',
        'WRONG_STATE': '#FFE8E8',
        'SUPPRESSED_ONLY': '#FF7373',
        'SOURCE_PERSISTS': '#C00000',
    }
    color = tier_colors.get(tier_name, '#475569')
    short_name = tier_name.replace('_', ' ').title()[:12]
    
    return Div(cls="flex items-center gap-2")(
        Span(cls="text-xs text-slate-400 w-24 truncate")(short_name),
        Div(cls="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden")(
            Div(cls="h-full", style=f"width: {pct}%; background-color: {color};"),
        ),
        Span(cls="text-xs text-slate-500 w-8 text-right")(str(count)),
    )


def _about_link(title: str, desc: str, url: str, icon_type: str):
    """Render a resource link card for the About modal."""
    icons = {
        'paper': '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>',
        'blog': '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z"></path></svg>',
        'demo': '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>',
        'code': '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path></svg>',
    }
    icon_svg = icons.get(icon_type, icons['code'])
    
    return A(
        href=url,
        target="_blank",
        cls="block p-3 bg-slate-800/50 rounded-lg border border-slate-700 hover:border-slate-500 hover:bg-slate-800 transition-all group"
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


def _run_selector(data_loader, registry=None):
    """Render run selector dropdown, grouped by dataset when registry is active."""
    current_run = data_loader.get_current_run()

    if registry is not None:
        all_runs = registry.list_all_runs()
    else:
        all_runs = data_loader.list_runs()

    if not all_runs:
        dc = data_loader.get_domain_config()
        stats = data_loader.get_stats()
        label = dc.get("display_name", "Dataset")
        total_swaps = stats.get("total_swaps", 0)
        text = f"{label} ({total_swaps} swaps)" if total_swaps else label
        return Span(cls="text-xs text-slate-500 hidden-mobile")(f"Dataset: {text}")

    def _short_label(run):
        ds = run.get("dataset_label", "")
        sem = run.get("semantic_label", "")
        count = run.get("swap_count", 0)
        if ds and sem:
            return f"{ds} - {sem} ({count} swaps)"
        if ds:
            return f"{ds} ({count} swaps)"
        name = run.get("name", run["id"])
        return f"{name} ({count})"

    # Group runs by dataset_label (or flat list if no label)
    from collections import OrderedDict
    groups = OrderedDict()
    for run in all_runs:
        key = run.get("dataset_label", "")
        groups.setdefault(key, []).append(run)

    options = []
    if len(groups) <= 1:
        for run in all_runs:
            options.append(Option(
                value=run["id"],
                selected=(run["id"] == current_run),
            )(_short_label(run)))
    else:
        for ds_label, runs in groups.items():
            group_options = []
            for run in runs:
                group_options.append(Option(
                    value=run["id"],
                    selected=(run["id"] == current_run),
                )(_short_label(run)))
            # NotStr to emit raw <optgroup> since fasthtml doesn't ship Optgroup
            inner = "".join(
                f'<option value="{r["id"]}"'
                f'{" selected" if r["id"] == current_run else ""}>'
                f'{_short_label(r)}</option>'
                for r in runs
            )
            options.append(NotStr(
                f'<optgroup label="{ds_label}">{inner}</optgroup>'
            ))

    return Div(cls="flex items-center gap-2")(
        Span(cls="text-xs text-slate-500 hidden-mobile")("Run:"),
        Select(
            id="run-selector",
            cls="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm text-slate-300 hover:border-slate-500 focus:border-cyan-500 focus:outline-none cursor-pointer"
        )(*options),
    )

