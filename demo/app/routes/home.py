"""
Home page route - main matrix view
"""
from fasthtml.common import (
    Html, Head, Body, Title, Link, Script, Meta,
    Div, H1, H2, H3, P, A, Button, Span, Main, Header, Footer, Nav,
    Section, Article, Aside, Ul, Li
)


def home_routes(app, rt, data_loader, annotate_mode: bool = False):
    """Register home page routes."""
    
    @rt("/")
    def home():
        """Main page with matrix visualization."""
        stats = data_loader.get_stats()
        analysis = data_loader.get_analysis()
        insights = analysis.get('insights', [])
        
        aggregate = stats.get('aggregate', {})
        perfect_rate = aggregate.get('perfect_rate', 0) * 100
        state_correct_rate = aggregate.get('state_correct_rate', 0) * 100
        suppression_rate = aggregate.get('suppression_rate', 0) * 100
        
        # Annotation mode badge
        annotate_badge = Span(cls="text-xs px-2 py-1 bg-amber-900/50 text-amber-400 rounded-full ml-2 animate-pulse")(
            "ANNOTATE MODE"
        ) if annotate_mode else None
        
        return Html(
            Head(
                Title("State Swap Explorer"),
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
                            H1(cls="text-2xl font-bold bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent")(
                                "State Swap Explorer"
                            ),
                            Span(cls="text-xs px-2 py-1 bg-slate-800 rounded-full text-slate-400")(
                                "Circuit Steering Demo"
                            ),
                            annotate_badge,
                        ),
                        Nav(cls="flex items-center gap-4")(
                            A(href="/", cls="text-slate-300 hover:text-white transition-colors")("Matrix"),
                            A(href="https://github.com", target="_blank", cls="text-slate-400 hover:text-white transition-colors")("GitHub"),
                        ),
                    ),
                ),
                
                # Main content
                Main(cls="max-w-7xl mx-auto px-4 py-8")(
                    # Stats bar
                    Div(cls="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8")(
                        _stat_card("Total Swaps", str(stats.get('total_swaps', 0)), "experiments"),
                        _stat_card("Perfect (T5)", f"{perfect_rate:.0f}%", "target capital found"),
                        _stat_card("State Correct", f"{state_correct_rate:.0f}%", "T3+ success"),
                        _stat_card("Suppression", f"{suppression_rate:.0f}%", "source removed"),
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
                            # Legend
                            Div(cls="bg-slate-900/50 rounded-xl border border-slate-800 p-4")(
                                H3(cls="text-sm font-semibold text-slate-400 mb-3")("TIER LEGEND"),
                                Div(cls="space-y-2")(
                                    _legend_item("T5", "PERFECT", "bg-emerald-500"),
                                    _legend_item("T4", "State + City", "bg-lime-500"),
                                    _legend_item("T3", "State Only", "bg-yellow-500"),
                                    _legend_item("T2", "Suppressed", "bg-orange-400"),
                                    _legend_item("T1", "Source Persists", "bg-red-500"),
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
                
                # Scripts
                Script(src="/static/islands/Matrix.js", type="module"),
                Script(src="/static/islands/DetailPanel.js", type="module"),
            ),
        )


def _stat_card(title: str, value: str, subtitle: str):
    """Render a stat card."""
    return Div(cls="bg-slate-900/50 rounded-xl border border-slate-800 p-4")(
        P(cls="text-xs text-slate-500 uppercase tracking-wide")(title),
        P(cls="text-2xl font-bold mt-1")(value),
        P(cls="text-xs text-slate-400 mt-1")(subtitle),
    )


def _legend_item(tier: str, label: str, color_class: str):
    """Render a legend item."""
    return Div(cls="flex items-center gap-2")(
        Div(cls=f"w-4 h-4 rounded {color_class}"),
        Span(cls="text-xs text-slate-300")(f"{tier}: {label}"),
    )


def _tier_bar(tier_name: str, count: int, total: int):
    """Render a tier distribution bar."""
    pct = (count / total * 100) if total > 0 else 0
    tier_colors = {
        'PERFECT': 'bg-emerald-500',
        'TARGET_STATE_CITY': 'bg-lime-500',
        'TARGET_STATE_ONLY': 'bg-yellow-500',
        'SUPPRESSED_ONLY': 'bg-orange-400',
        'SOURCE_PERSISTS': 'bg-red-500',
    }
    color = tier_colors.get(tier_name, 'bg-slate-600')
    short_name = tier_name.replace('_', ' ').title()[:12]
    
    return Div(cls="flex items-center gap-2")(
        Span(cls="text-xs text-slate-400 w-24 truncate")(short_name),
        Div(cls="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden")(
            Div(cls=f"h-full {color}", style=f"width: {pct}%"),
        ),
        Span(cls="text-xs text-slate-500 w-8 text-right")(str(count)),
    )

