"""
State profile page route
"""
from fasthtml.common import (
    Html, Head, Body, Title, Link, Script, Meta,
    Div, H1, H2, H3, P, A, Button, Span, Main, Header, Section,
    Table, Thead, Tbody, Tr, Th, Td
)


def state_routes(app, rt, data_loader):
    """Register state profile routes."""
    
    @rt("/state/{slug}")
    def state_profile(slug: str):
        """State profile page."""
        states = data_loader.get_states()
        state = next((s for s in states if s['slug'] == slug), None)
        
        if state is None:
            return Html(
                Body(cls="min-h-screen bg-slate-950 text-white flex items-center justify-center")(
                    Div(cls="text-center")(
                        H1(cls="text-4xl font-bold text-red-500")("State Not Found"),
                        A(href="/", cls="text-cyan-400 hover:underline mt-4 block")("Back to Matrix"),
                    ),
                ),
            )
        
        matrix = data_loader.get_matrix()
        as_source = matrix.get(slug, {})
        as_target = {k: v.get(slug) for k, v in matrix.items() if k != slug and v.get(slug) is not None}
        
        # Calculate averages
        source_tiers = [t for t in as_source.values() if t is not None]
        target_tiers = [t for t in as_target.values() if t is not None]
        avg_source = sum(source_tiers) / len(source_tiers) if source_tiers else 0
        avg_target = sum(target_tiers) / len(target_tiers) if target_tiers else 0
        
        archetype_colors = {
            'Mixed': 'text-slate-400',
            'Exchanger': 'text-emerald-400',
            'Magnet': 'text-cyan-400',
            'Escape': 'text-yellow-400',
            'Trap': 'text-red-400',
            'Unknown': 'text-slate-500',
        }
        
        return Html(
            Head(
                Title(f"{state['state']} - State Swap Explorer"),
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
            Body(cls="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-white font-sans")(
                # Header
                Header(cls="border-b border-slate-800 bg-slate-900/50 backdrop-blur-sm")(
                    Div(cls="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between")(
                        Div(cls="flex items-center gap-4")(
                            A(href="/", cls="text-slate-400 hover:text-white transition-colors")(
                                "< Back to Matrix"
                            ),
                        ),
                    ),
                ),
                
                # Main content
                Main(cls="max-w-5xl mx-auto px-4 py-8")(
                    # State header
                    Div(cls="mb-8")(
                        Div(cls="flex items-center justify-between mb-4")(
                            Div(cls="flex items-center gap-4")(
                                Span(cls="text-5xl font-bold")(state['abbr']),
                                Div()(
                                    H1(cls="text-3xl font-bold")(state['state']),
                                    P(cls="text-slate-400")(f"City: {state['city']}"),
                                ),
                            ),
                            # Neuronpedia subgraph button on the right
                            Button(
                                id="subgraph-btn",
                                cls="px-4 py-2 rounded-lg bg-cyan-900/30 hover:bg-cyan-900/50 text-cyan-400 text-sm transition-colors border border-cyan-800/50 flex items-center gap-2",
                                **{"data-slug": slug}
                            )(
                                Span()("Neuronpedia"),
                                Span(cls="text-cyan-600")("->"),
                            ) if state.get('neuronpedia_url') else None,
                        ),
                        Div(cls="flex items-center gap-3")(
                            Span(cls=f"px-3 py-1 rounded-full bg-slate-800 text-sm {archetype_colors.get(state['archetype'], '')}")(
                                f"Archetype: {state['archetype']}"
                            ),
                        ),
                    ),
                    
                    # Stats grid
                    Div(cls="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8")(
                        _profile_stat("Native Prob", f"{state['native_prob']:.3f}"),
                        _profile_stat("Supernodes", str(state['supernodes'])),
                        _profile_stat("Avg as Source", f"{avg_source:.2f}"),
                        _profile_stat("Avg as Target", f"{avg_target:.2f}"),
                    ),
                    
                    # Performance bars
                    Div(cls="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8")(
                        # As Source
                        Div(cls="bg-slate-900/50 rounded-xl border border-slate-800 p-6")(
                            H2(cls="text-lg font-semibold mb-4")(
                                f"As Source ({state['abbr']} -> )"
                            ),
                            P(cls="text-sm text-slate-400 mb-4")(
                                f"How well can we steer FROM {state['state']}?"
                            ),
                            _tier_mini_grid(as_source, states),
                        ),
                        
                        # As Target
                        Div(cls="bg-slate-900/50 rounded-xl border border-slate-800 p-6")(
                            H2(cls="text-lg font-semibold mb-4")(
                                f"As Target (-> {state['abbr']})"
                            ),
                            P(cls="text-sm text-slate-400 mb-4")(
                                f"How well can we steer TO {state['state']}?"
                            ),
                            _tier_mini_grid(as_target, states),
                        ),
                    ),
                    
                    # Raw data tables
                    Div(cls="grid grid-cols-1 md:grid-cols-2 gap-8")(
                        _swaps_table("Swaps as Source", as_source, slug, states, "to"),
                        _swaps_table("Swaps as Target", as_target, slug, states, "from"),
                    ),
                ),
                
                # Inline script for subgraph button
                Script("""
                    document.addEventListener('DOMContentLoaded', function() {
                        const btn = document.getElementById('subgraph-btn');
                        if (btn) {
                            btn.addEventListener('click', async function() {
                                const slug = this.dataset.slug;
                                const originalText = this.textContent;
                                this.textContent = 'Loading...';
                                this.disabled = true;
                                
                                try {
                                    const res = await fetch('/api/state/' + slug + '/subgraph-url?max_features=100');
                                    if (!res.ok) throw new Error('Failed');
                                    const data = await res.json();
                                    if (data.url) {
                                        window.open(data.url, '_blank');
                                    }
                                } catch (e) {
                                    alert('Could not generate subgraph URL');
                                } finally {
                                    this.textContent = originalText;
                                    this.disabled = false;
                                }
                            });
                        }
                    });
                """),
            ),
        )


def _profile_stat(label: str, value: str):
    """Render a profile stat card."""
    return Div(cls="bg-slate-900/50 rounded-lg border border-slate-800 p-4 text-center")(
        P(cls="text-xs text-slate-500 uppercase")(label),
        P(cls="text-xl font-bold mt-1")(value),
    )


def _tier_mini_grid(tiers: dict, states: list):
    """Render a mini grid of tier results."""
    if not tiers:
        return P(cls="text-slate-500 text-sm")("No data available")
    
    tier_colors = {
        5: 'bg-emerald-500',
        4: 'bg-lime-500',
        3: 'bg-yellow-500',
        2: 'bg-orange-400',
        1: 'bg-red-500',
        0: 'bg-slate-600',
    }
    
    # Get state abbrs
    slug_to_abbr = {s['slug']: s['abbr'] for s in states}
    
    return Div(cls="flex flex-wrap gap-2")(
        *[Div(cls=f"w-10 h-10 rounded flex items-center justify-center text-xs font-bold {tier_colors.get(tier, 'bg-slate-700')}")(
            slug_to_abbr.get(slug, slug[:2].upper())
        ) for slug, tier in sorted(tiers.items()) if tier is not None]
    )


def _swaps_table(title: str, swaps: dict, current_slug: str, states: list, direction: str):
    """Render a swaps table."""
    slug_to_abbr = {s['slug']: s['abbr'] for s in states}
    
    return Div(cls="bg-slate-900/50 rounded-xl border border-slate-800 p-4")(
        H3(cls="text-sm font-semibold text-slate-400 mb-3")(title),
        Div(cls="overflow-x-auto")(
            Table(cls="w-full text-sm")(
                Thead()(
                    Tr(cls="border-b border-slate-700")(
                        Th(cls="text-left py-2 text-slate-400")("State"),
                        Th(cls="text-center py-2 text-slate-400")("Tier"),
                        Th(cls="text-right py-2 text-slate-400")(""),
                    ),
                ),
                Tbody()(
                    *[Tr(cls="border-b border-slate-800 hover:bg-slate-800/50")(
                        Td(cls="py-2")(slug_to_abbr.get(slug, slug)),
                        Td(cls="py-2 text-center")(
                            Span(cls=f"px-2 py-0.5 rounded text-xs font-bold {_tier_badge_color(tier)}")(
                                str(tier) if tier is not None else "-"
                            )
                        ),
                        Td(cls="py-2 text-right")(
                            A(
                                href=f"/?from={current_slug}&to={slug}" if direction == "to" else f"/?from={slug}&to={current_slug}",
                                cls="text-cyan-400 hover:underline text-xs"
                            )("View")
                        ),
                    ) for slug, tier in sorted(swaps.items())]
                ),
            ),
        ) if swaps else P(cls="text-slate-500 text-sm")("No swaps recorded"),
    )


def _tier_badge_color(tier):
    """Get badge color for tier."""
    colors = {
        5: 'bg-emerald-500/20 text-emerald-400',
        4: 'bg-lime-500/20 text-lime-400',
        3: 'bg-yellow-500/20 text-yellow-400',
        2: 'bg-orange-400/20 text-orange-400',
        1: 'bg-red-500/20 text-red-400',
    }
    return colors.get(tier, 'bg-slate-600/20 text-slate-400')

