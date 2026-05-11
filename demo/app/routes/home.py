"""
Home page route - main matrix view
"""
from fasthtml.common import (
    Html, Head, Body, Title, Link, Script, Meta,
    Div, H1, H2, H3, P, A, Button, Span, Main, Header, Footer, Nav,
    Section, Article, Aside, Ul, Li, NotStr, Select, Option
)
from app.components.about import about_modal


def home_routes(app, rt, data_loader, annotate_mode: bool = False, registry=None):
    """Register home page routes."""
    
    @rt("/")
    def home():
        """Main page with matrix visualization."""
        stats = data_loader.get_stats()
        analysis = data_loader.get_analysis()
        insights = analysis.get('insights', [])
        dc = data_loader.get_domain_config()
        page_title = dc.get('display_name', 'Concept Swap Explorer')
        is_usa = dc.get('is_usa_states', True)
        # Field-additivity runs hold the canonical 3-field schema; legacy
        # 2-field runs lack the intermediate role and would mis-label the
        # field palette. Prefer the additivity run for the colour mapping
        # whenever the dataset has one.
        field_dc = _additivity_domain_config(registry, data_loader) or dc
        
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
                Title(f"{page_title} - Concept Swap Explorer"),
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
                                f"{page_title} Concept Swap Explorer"
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
                                    **_matrix_container_attrs(field_dc, is_usa),
                                )(
                                    Div(cls="text-center py-20 text-slate-500")(
                                        P("Loading matrix..."),
                                    ),
                                ),
                            ),
                        ),
                        
                        # Sidebar (1 col)
                        Aside(cls="space-y-6")(
                            # Legend with overlay selector
                            Div(cls="bg-slate-900/50 rounded-xl border border-slate-800 px-3 py-4")(
                                Div(cls="flex items-center justify-between gap-3 mb-2")(
                                    H3(
                                        id="legend-title",
                                        cls="text-sm font-semibold text-slate-400"
                                    )("TIER LEGEND"),
                                    Select(
                                        id="color-mode-select",
                                        cls="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-slate-300 hover:border-slate-500 focus:border-cyan-500 focus:outline-none cursor-pointer",
                                    )(
                                        Option(value="tier", selected=(not is_usa))("Tier"),
                                        Option(value="flip")("Flip"),
                                        Option(value="regime")("Regime"),
                                        Option(value="vsmax")("VsMax"),
                                        Option(value="field", selected=is_usa)("Field"),
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
                                # Regime legend (hidden by default)
                                Div(id="regime-legend", cls="space-y-2", style="display: none;")(
                                    _legend_item("A", "Clean Redirection", "#22d3ee"),
                                    _legend_item("B", "Both Boosted", "#818cf8"),
                                    _legend_item("C", "Diff. Disruption", "#facc15"),
                                    _legend_item("D", "Generic Disruption", "#f87171"),
                                    _legend_item("E", "Pure Suppression", "#fb923c"),
                                    _legend_item("--", "Unclassified", "#1e293b"),
                                ),
                                # VsMax legend (hidden by default)
                                Div(id="vsmax-legend", cls="space-y-2", style="display: none;")(
                                    _legend_item(">+2", "Strong positive", "#10b981"),
                                    _legend_item("+0..+2", "Weak positive", "#34d399"),
                                    _legend_item("0", "Neutral", "#a3e635"),
                                    _legend_item("-2..0", "Weak negative", "#fb923c"),
                                    _legend_item("<-2", "Strong negative", "#ef4444"),
                                    _legend_item("--", "No data", "#1e293b"),
                                ),
                                # Field legend (Okabe-Ito palette, mirrors paper figures/swap_matrix.pdf)
                                Div(id="field-legend", cls="space-y-2", style=("" if is_usa else "display: none;"))(
                                    *_field_legend_items(field_dc),
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
                about_modal(dc),
                
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
                # Color mode selector script
                Script("""
                    (function() {
                        var sel = document.getElementById('color-mode-select');
                        var title = document.getElementById('legend-title');
                        var legends = {
                            tier:   document.getElementById('tier-legend'),
                            flip:   document.getElementById('flip-legend'),
                            regime: document.getElementById('regime-legend'),
                            vsmax:  document.getElementById('vsmax-legend'),
                            field:  document.getElementById('field-legend')
                        };
                        var titles = {
                            tier:   'TIER LEGEND',
                            flip:   'FLIP POSITION',
                            regime: 'REGIME',
                            vsmax:  'VsMax',
                            field:  'FIELD SUBSET'
                        };
                        if (!sel) return;
                        function apply(mode) {
                            title.textContent = titles[mode] || mode.toUpperCase();
                            for (var k in legends) {
                                if (legends[k]) legends[k].style.display = k === mode ? '' : 'none';
                            }
                            document.dispatchEvent(new CustomEvent('color-mode-changed', {
                                detail: { mode: mode }, bubbles: true
                            }));
                        }
                        sel.addEventListener('change', function() { apply(sel.value); });
                        // Apply the initial selection (e.g. 'field' on USA homepage)
                        if (sel.value) apply(sel.value);
                        // Allow Svelte islands (e.g. the Matrix bestMode toggle)
                        // to request a colour-mode switch -- keeps the dropdown
                        // and legend in sync with internal state changes.
                        document.addEventListener('request-color-mode', function(e) {
                            var mode = e && e.detail && e.detail.mode;
                            if (!mode || !legends[mode]) return;
                            sel.value = mode;
                            apply(mode);
                        });
                    })();
                """),
                # About modal script (open/close only -- all data is static)
                Script("""
                    (function() {
                        var modal = document.getElementById('about-modal');
                        var openBtn = document.getElementById('about-btn');
                        var closeBtn = document.getElementById('about-close');

                        function resetMatrixCells() {
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
                            closeBtn.onclick = function() { modal.style.display = 'none'; };
                        }
                        if (modal) {
                            modal.onclick = function(e) {
                                if (e.target === modal) modal.style.display = 'none';
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
                    "target concept found", value_id="kpi-perfect"),
        _stat_card("Concept Correct", f"{state_correct_rate:.0f}%",
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


# Role-keyed Okabe-Ito palette (mirrors tools/render_swap_matrix.py FIELD_PALETTE).
# Keys are sorted role tuples so the demo stays domain-agnostic.
FIELD_ROLE_PALETTE = [
    (("answer", "input", "intermediate"), "#D55E00", "input + intermediate + answer"),
    (("input", "intermediate"),           "#E69F00", "input + intermediate"),
    (("answer", "input"),                 "#CC79A7", "input + answer"),
    (("answer", "intermediate"),          "#009E73", "intermediate + answer"),
    (("input",),                          "#56B4E9", "input only"),
    (("intermediate",),                   "#0072B2", "intermediate only"),
    (("answer",),                         "#F0E442", "answer only"),
]


def _domain_field_roles(dc: dict) -> dict:
    """Map concept-field names to roles {input, intermediate, answer}.

    Convention used across the four batch domains: ``concept_fields`` is
    ordered ``[input, intermediate, answer]``.  When fewer than three
    fields are configured we degrade gracefully (intermediate=input).
    """
    fields = dc.get("concept_fields") or []
    if not fields:
        return {"input": "", "intermediate": "", "answer": ""}
    return {
        "input": fields[0],
        "intermediate": fields[1] if len(fields) >= 3 else fields[0],
        "answer": fields[-1],
    }


def _field_legend_items(dc: dict):
    """Render the Field legend, named with the domain's actual field labels."""
    roles = _domain_field_roles(dc)
    name_for = {
        "input": roles["input"] or "input",
        "intermediate": roles["intermediate"] or "intermediate",
        "answer": roles["answer"] or "answer",
    }
    items = []
    for combo, color, _label in FIELD_ROLE_PALETTE:
        readable = " + ".join(name_for[r] for r in ("input", "intermediate", "answer") if r in combo)
        items.append(_legend_item("", readable, color))
    items.append(_legend_item("", "hit, no field tag", "#888888"))
    items.append(_legend_item("", "miss / no data", "#475569"))
    return items


def _additivity_domain_config(registry, data_loader) -> dict | None:
    """Return the domain-config of the dataset's field-additivity run, if any.

    The legacy 2-field swap runs (e.g. ``full_50states_v1``) lack the
    intermediate concept and would render the Field palette with only
    "input" + "answer" labels.  When the active dataset bundles a
    ``control_mode == 'additivity'`` run, we use *its* schema for the
    palette so reviewers get the full 3-role colouring without having
    to switch the dropdown first.
    """
    if registry is None:
        return None
    ds_id = registry.active_dataset_id
    if not ds_id:
        return None
    ds = registry._datasets.get(ds_id)
    if not ds:
        return None
    add_run = next(
        (r for r in ds["runs"] if r.get("control_mode") == "additivity"),
        None,
    )
    if not add_run:
        return None
    try:
        from app.data.loader import DataLoader
        loader = DataLoader(ds["dir"], run_id=add_run["id"])
        return loader.get_domain_config()
    except Exception:
        return None


def _matrix_container_attrs(dc: dict, is_usa: bool) -> dict:
    """Data attributes consumed by Matrix.svelte (via init.js).

    - ``data-default-best-mode``: auto-toggle Best per cell across runs
      on the USA homepage so the colored field-additivity matrix is the
      first thing the reviewer sees.
    - ``data-domain-input/intermediate/answer``: field-name -> role map
      so the Svelte palette can colour cells without hard-coding USA
      field names.
    """
    roles = _domain_field_roles(dc)
    return {
        "data-api-url": "/api/matrix",
        "data-default-best-mode": "true" if is_usa else "false",
        "data-domain-input": roles["input"],
        "data-domain-intermediate": roles["intermediate"],
        "data-domain-answer": roles["answer"],
    }


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

