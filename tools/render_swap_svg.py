"""
Offline renderer for *intervention* circuit SVGs from already-computed swap runs.

Reads the artifacts produced by the supernode-swap pipeline under
``output/usa_states_batch/_swaps/runs/<run>/`` and produces a tutorial-style
diagram (boxes-and-arrows + activation % + intervention badges + replacement
nodes) without invoking a model. The numbers shown come straight from data
already on disk:

- ablated supernodes show **mean baseline activation in the source prompt**
  (per-feature ``activation`` from source ``00 Graph Generation/graph.json``);
- amplified replacement supernodes show **mean activation in the target
  prompt** (``stored_activation`` from the swap's ``features.json``, which is
  exactly the value that was scaled by ``M`` at intervention time);
- intervention badges (``-2x`` / ``+20x``) come from ``config.M_ablate`` /
  ``config.M_amplify`` of the swap result;
- top-output tokens come from ``evaluation.raw.steered_topk``.

All percentages are normalised by the maximum mean activation across both
sides of the swap, so cross-side magnitudes are directly comparable.

Layout mirrors the second example in
https://github.com/decoderesearch/circuit-tracer/blob/main/demos/circuit_tracing_tutorial.ipynb
"""

from __future__ import annotations

import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from render_circuit_svg import (  # noqa: E402
    SupernodeSpec,
    _build_supernode_objects,
    render_offline,
)
from graph_visualization import InterventionGraph  # noqa: E402  (vendored)

REPO_ROOT = _THIS_DIR.parent
USA_DIR = REPO_ROOT / "output" / "usa_states_batch"


# --------------------------------------------------------------------------- #
# Path helpers                                                                #
# --------------------------------------------------------------------------- #


def _slug_to_state_dir(slug: str) -> Path:
    """``california_oakland`` -> ``output/.../california_Oakland`` (case-folding tolerant)."""
    direct = USA_DIR / slug
    if direct.is_dir():
        return direct
    slug_lc = slug.lower()
    for candidate in USA_DIR.iterdir():
        if candidate.is_dir() and candidate.name.lower() == slug_lc:
            return candidate
    raise FileNotFoundError(f"Could not find state dir for slug {slug!r} under {USA_DIR}")


def _load_grouping(state_dir: Path) -> dict[tuple[int, int], str]:
    """``02 Node Grouping/node_grouping.csv`` -> ``{(layer, feat_idx): supernode_name}``."""
    out: dict[tuple[int, int], str] = {}
    p = state_dir / "02 Node Grouping" / "node_grouping.csv"
    if not p.exists():
        return out
    with p.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                out[(int(row["layer"]), int(row["feature"]))] = row.get("supernode_name", "").strip()
            except (KeyError, ValueError):
                continue
    return out


def _load_graph_activations(state_dir: Path) -> dict[tuple[int, int], list[float]]:
    """``graph.json`` -> ``{(layer, feat_idx): [activations across positions]}``."""
    out: dict[tuple[int, int], list[float]] = {}
    p = state_dir / "00 Graph Generation" / "graph.json"
    if not p.exists():
        return out
    with p.open("r", encoding="utf-8") as f:
        graph = json.load(f)
    for n in graph.get("nodes", []):
        if n.get("feature_type") != "cross layer transcoder":
            continue
        parts = (n.get("node_id") or "").split("_")
        if len(parts) != 3:
            continue
        try:
            layer, feat_idx, _pos = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            continue
        out.setdefault((layer, feat_idx), []).append(float(n.get("activation", 0.0)))
    return out


def _resolve_positions(
    state_dir: Path,
    layer_feat_pairs: set[tuple[int, int]],
) -> dict[tuple[int, int], int]:
    """Pick a representative ctx_idx for each (layer, feature_idx) from the state's graph.json."""
    out: dict[tuple[int, int], int] = {}
    p = state_dir / "00 Graph Generation" / "graph.json"
    if not p.exists():
        return out
    with p.open("r", encoding="utf-8") as f:
        graph = json.load(f)
    for n in graph.get("nodes", []):
        if n.get("feature_type") != "cross layer transcoder":
            continue
        parts = (n.get("node_id") or "").split("_")
        if len(parts) != 3:
            continue
        try:
            layer, feat_idx, pos = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            continue
        key = (layer, feat_idx)
        if key in layer_feat_pairs and key not in out:
            out[key] = pos
    return out


# --------------------------------------------------------------------------- #
# Core data assembly                                                          #
# --------------------------------------------------------------------------- #


@dataclass
class _SupernodeData:
    name: str
    triples: list[tuple[int, int, int]]  # (layer, pos, feature_idx)
    activations: list[float]  # per-feature mean baseline activation

    @property
    def mean_activation(self) -> float:
        return sum(self.activations) / len(self.activations) if self.activations else 0.0


def _collect_ablated(
    feats: list[dict],
    src_grouping: dict[tuple[int, int], str],
    src_acts: dict[tuple[int, int], list[float]],
    src_positions: dict[tuple[int, int], int],
) -> dict[str, _SupernodeData]:
    """Group ablated features by source supernode label, attaching activations from source graph.json."""
    out: dict[str, _SupernodeData] = {}
    for f in feats:
        if f.get("M", 0) >= 0:
            continue
        layer, feat_idx = f["layer"], f["index"]
        name = src_grouping.get((layer, feat_idx))
        if not name:
            continue
        per_pos = src_acts.get((layer, feat_idx), [])
        # Use mean-across-positions as the per-feature activation summary.
        per_feat_act = sum(per_pos) / len(per_pos) if per_pos else 0.0
        pos = src_positions.get((layer, feat_idx), -1)
        sn = out.setdefault(name, _SupernodeData(name=name, triples=[], activations=[]))
        sn.triples.append((layer, pos, feat_idx))
        sn.activations.append(per_feat_act)
    return out


def _collect_amplified(
    feats: list[dict],
    tgt_grouping: dict[tuple[int, int], str],
    tgt_positions: dict[tuple[int, int], int],
) -> dict[str, _SupernodeData]:
    """Group amplified features by target supernode label, using stored_activation as activation."""
    out: dict[str, _SupernodeData] = {}
    for f in feats:
        if f.get("M", 0) <= 0:
            continue
        layer, feat_idx = f["layer"], f["index"]
        name = tgt_grouping.get((layer, feat_idx))
        if not name:
            continue
        per_feat_act = float(f.get("stored_activation", 0.0))
        pos = tgt_positions.get((layer, feat_idx), -1)
        sn = out.setdefault(name, _SupernodeData(name=name, triples=[], activations=[]))
        sn.triples.append((layer, pos, feat_idx))
        sn.activations.append(per_feat_act)
    return out


def _make_substitution_re(token: str) -> re.Pattern[str]:
    """Word-bounded, case-insensitive substitution regex (avoids partial matches)."""
    return re.compile(rf"\b{re.escape(token)}\b", flags=re.IGNORECASE)


def _pair_replacement_name(
    src_name: str,
    *,
    src_state: str,
    src_capital: str,
    src_city: str,
    tgt_state: str,
    tgt_capital: str,
    tgt_city: str,
) -> str:
    """Substitute source state/capital/city names with target ones inside a supernode label."""
    out = src_name
    for src_tok, tgt_tok in (
        (src_state, tgt_state),
        (src_capital, tgt_capital),
        (src_city, tgt_city),
    ):
        if not src_tok or not tgt_tok:
            continue
        out = _make_substitution_re(src_tok).sub(tgt_tok, out)
    return out


# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #


def render_swap_intervention(
    swap_run_dir: str | Path,
    swap_id: str,
    *,
    output_svg_path: str | Path | None = None,
    max_per_row: int = 4,
    compact: bool = True,
    layout: str = "compact",
) -> str:
    """Render an intervention SVG for a single swap, showing every intervened supernode.

    Args:
        swap_run_dir: path to ``output/usa_states_batch/_swaps/runs/<run>``.
        swap_id: ``<src_slug>__to__<tgt_slug>``.
        output_svg_path: where to write the SVG, or ``None`` to only return the string.
        max_per_row: cap on supernode boxes per row (cosmetic; default 4 keeps it readable).
        compact: if ``True`` (default), render with the portrait-oriented compact
            layout matching the published Anthropic figure; if ``False``, use the
            upstream landscape layout.
        layout: ``"compact"`` (default) is the standalone graph; ``"v2"`` adds a
            top header strip (PROMPT | ORIGINAL PREDICTION | AFTER INTERVENTION)
            and a bottom intervention-strength sweep plot built from sibling
            run dirs (e.g. ``sweep_usa_m*``, ``entropy_study_m*``, ``highm_*``).

    Returns:
        The raw SVG markup.
    """
    swap_run_dir = Path(swap_run_dir)
    work_dir = swap_run_dir / "work" / swap_id
    if not work_dir.exists():
        raise FileNotFoundError(f"swap work dir not found: {work_dir}")

    src_slug, _, tgt_slug = swap_id.partition("__to__")
    if not (src_slug and tgt_slug):
        raise ValueError(f"swap_id must be '<src>__to__<tgt>', got {swap_id!r}")

    result_path = swap_run_dir / "by_source" / src_slug / f"to_{tgt_slug}.json"
    feats = json.loads((work_dir / "features.json").read_text(encoding="utf-8"))
    result = json.loads(result_path.read_text(encoding="utf-8"))

    src_dir = _slug_to_state_dir(src_slug)
    tgt_dir = _slug_to_state_dir(tgt_slug)

    src_meta = result.get("source") or {}
    tgt_meta = result.get("target") or {}
    src_state = src_meta.get("state", "")
    src_capital = src_meta.get("capital", "")
    src_city = src_meta.get("city", "")
    tgt_state = tgt_meta.get("state", "")
    tgt_capital = tgt_meta.get("capital", "")
    tgt_city = tgt_meta.get("city", "")

    config = result.get("config") or {}
    M_ablate = int(config.get("M_ablate", -2))
    M_amplify = int(config.get("M_amplify", 20))

    src_grouping = _load_grouping(src_dir)
    tgt_grouping = _load_grouping(tgt_dir)
    src_acts = _load_graph_activations(src_dir)

    ablate_pairs = {(f["layer"], f["index"]) for f in feats if f.get("M", 0) < 0}
    amplify_pairs = {(f["layer"], f["index"]) for f in feats if f.get("M", 0) > 0}
    src_positions = _resolve_positions(src_dir, ablate_pairs)
    tgt_positions = _resolve_positions(tgt_dir, amplify_pairs)

    ablated = _collect_ablated(feats, src_grouping, src_acts, src_positions)
    amplified = _collect_amplified(feats, tgt_grouping, tgt_positions)

    # Cross-side normalisation by the global max mean activation.
    all_means = [s.mean_activation for s in (*ablated.values(), *amplified.values())]
    norm = max(all_means) if all_means else 1.0
    norm = norm if norm > 1e-9 else 1.0

    def _frac(mean_act: float) -> float:
        return max(0.0, min(1.0, mean_act / norm))

    # Pair source -> target supernodes by name substitution (state/capital/city tokens).
    pair_kwargs = dict(
        src_state=src_state, src_capital=src_capital, src_city=src_city,
        tgt_state=tgt_state, tgt_capital=tgt_capital, tgt_city=tgt_city,
    )

    # Group supernode names by row: "Say (...)" -> upper row, others -> lower row.
    def _is_say(name: str) -> bool:
        return name.lower().startswith("say (") or name.lower().startswith("say ")

    def _say_base(name: str) -> str | None:
        m = re.match(r"^Say \((.+)\)$", name) or re.match(r"^Say (.+)$", name)
        return m.group(1).strip().lower() if m else None

    def _by_features_desc(d: dict[str, _SupernodeData]) -> list[_SupernodeData]:
        return sorted(d.values(), key=lambda s: (-len(s.triples), s.name))

    ablated_concept = [s for s in _by_features_desc(ablated) if not _is_say(s.name)][:max_per_row]

    # Order Say-supernodes to mirror the concept-row order so arrows go straight up.
    say_by_base: dict[str, _SupernodeData] = {}
    for s in ablated.values():
        if _is_say(s.name):
            base = _say_base(s.name)
            if base:
                say_by_base[base] = s
    ablated_say: list[_SupernodeData] = []
    for c in ablated_concept:
        s = say_by_base.get(c.name.lower())
        if s is not None and s not in ablated_say:
            ablated_say.append(s)
    for s in _by_features_desc({n: d for n, d in ablated.items() if _is_say(n)}):
        if s not in ablated_say:
            ablated_say.append(s)
    ablated_say = ablated_say[:max_per_row]

    # Build SupernodeSpec list. Each ablated supernode -> spec (greyed via -intervention).
    # Pair to amplified by substitution; if the paired name exists, attach as replacement.
    specs: list[SupernodeSpec] = []
    used_amplified: set[str] = set()
    intervention_ablate = f"{M_ablate:+d}x"
    intervention_amplify = f"{M_amplify:+d}x" if M_amplify >= 0 else f"{M_amplify}x"

    def _add_pair(ab: _SupernodeData, children: list[str] | None = None) -> SupernodeSpec:
        paired = _pair_replacement_name(ab.name, **pair_kwargs)
        repl_data = amplified.get(paired)
        replacement_name: str | None = None
        if repl_data is not None and repl_data.name not in used_amplified:
            replacement_name = repl_data.name
            # Translate the original's children to their replacement counterparts
            # so the renderer draws orange arrows out of the replacement node.
            repl_children: list[str] = []
            for cname in children or []:
                translated = _pair_replacement_name(cname, **pair_kwargs)
                repl_children.append(translated if translated in amplified else cname)
            specs.append(
                SupernodeSpec(
                    name=repl_data.name,
                    features=repl_data.triples or None,
                    activation=_frac(repl_data.mean_activation),
                    intervention=intervention_amplify,
                    children=repl_children,
                )
            )
            used_amplified.add(repl_data.name)
        spec = SupernodeSpec(
            name=ab.name,
            features=ab.triples or None,
            activation=_frac(ab.mean_activation),
            intervention=intervention_ablate,
            replacement=replacement_name,
            children=list(children or []),
        )
        specs.append(spec)
        return spec

    # Lower row: concept supernodes (state, capital, ...). Children = same-named "Say (..)" nodes.
    say_names_by_concept: dict[str, str] = {}
    for s in ablated_say:
        # "Say (Sacramento)" -> base = "Sacramento"; "Say Austin" -> "Austin"
        m = re.match(r"^Say \((.+)\)$", s.name) or re.match(r"^Say (.+)$", s.name)
        if m:
            say_names_by_concept[m.group(1).strip().lower()] = s.name

    for ab in ablated_concept:
        children = [say_names_by_concept[ab.name.lower()]] if ab.name.lower() in say_names_by_concept else []
        _add_pair(ab, children=children)

    # Upper row: Say-* supernodes.
    for ab in ablated_say:
        _add_pair(ab)

    # Embedding (city) at the bottom; feeds into all concept-row supernodes.
    city_emb_name = f"Emb: {src_city}" if src_city else "Emb"
    specs.append(
        SupernodeSpec(
            name=city_emb_name,
            features=None,
            children=[a.name for a in ablated_concept],
        )
    )

    rows: list[list[str]] = [[city_emb_name]]
    if ablated_concept:
        rows.append([s.name for s in ablated_concept])
    if ablated_say:
        rows.append([s.name for s in ablated_say])

    steered = (result.get("evaluation") or {}).get("raw", {}).get("steered_topk", [])
    top_outputs = [(t.get("token", ""), float(t.get("prob", 0.0))) for t in steered[:5]]

    title_prompt = src_meta.get("prompt", "") or ""
    if title_prompt.startswith("<bos>"):
        title_prompt = title_prompt[len("<bos>"):]

    if layout == "v2":
        return _render_v2(
            specs=specs,
            rows=rows,
            prompt=title_prompt,
            primary_run_dir=swap_run_dir,
            swap_id=swap_id,
            default_first=(
                (result.get("evaluation") or {}).get("first_token", {}).get("default", ""),
                float((result.get("evaluation") or {}).get("first_token", {}).get("default_prob", 0.0)),
            ),
            steered_first=(
                (result.get("evaluation") or {}).get("first_token", {}).get("steered", ""),
                float((result.get("evaluation") or {}).get("first_token", {}).get("steered_prob", 0.0)),
            ),
            output_svg_path=output_svg_path,
        )

    return render_offline(
        graph_path=src_dir / "00 Graph Generation" / "graph.json",
        supernodes=specs,
        rows=rows,
        output_svg_path=output_svg_path,
        top_outputs=top_outputs or None,
        prompt_override=title_prompt,
        compact=compact,
    )


def _render_v2(
    *,
    specs: list[SupernodeSpec],
    rows: list[list[str]],
    prompt: str,
    primary_run_dir: Path,
    swap_id: str,
    default_first: tuple[str, float],
    steered_first: tuple[str, float],
    output_svg_path: str | Path | None,
) -> str:
    """Build an InterventionGraph and call the v2 renderer with sweep data."""
    from circuit_svg_v2 import create_v2_visualization
    from sweep_loader import collect_sweep_data

    nodes_by_name = _build_supernode_objects(specs)
    ordered_nodes = [[nodes_by_name[name] for name in row] for row in rows]
    intervention_graph = InterventionGraph(ordered_nodes=ordered_nodes, prompt=prompt)
    for node in nodes_by_name.values():
        intervention_graph.nodes[node.name] = node

    sweep = collect_sweep_data(primary_run_dir, swap_id)
    svg_obj = create_v2_visualization(
        intervention_graph,
        prompt=prompt,
        original_pred=default_first,
        after_pred=steered_first,
        sweep=sweep,
    )
    svg_str = svg_obj.data
    if output_svg_path is not None:
        out = Path(output_svg_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(svg_str, encoding="utf-8")
    return svg_str


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #


def _cli(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    parser.add_argument(
        "--run",
        default="full_50states_v1",
        help="Swap run name under output/usa_states_batch/_swaps/runs/",
    )
    parser.add_argument(
        "--swap-id",
        default="california_oakland__to__texas_dallas",
        help="Swap id <src_slug>__to__<tgt_slug>",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Where to write the SVG. Defaults to <run>/by_source/<src>/to_<tgt>_circuit.svg",
    )
    parser.add_argument(
        "--max-per-row",
        type=int,
        default=4,
        help="Maximum supernode boxes per row (default 4)",
    )
    parser.add_argument(
        "--no-compact",
        dest="compact",
        action="store_false",
        help="Use the upstream landscape layout instead of the portrait compact one.",
    )
    parser.add_argument(
        "--layout",
        choices=("compact", "v2"),
        default="compact",
        help="'compact' = single graph (default); 'v2' = prompt + before/after + sweep plot.",
    )
    parser.set_defaults(compact=True)
    args = parser.parse_args(argv)

    swap_run_dir = USA_DIR / "_swaps" / "runs" / args.run
    out = args.output
    if out is None:
        src_slug, _, tgt_slug = args.swap_id.partition("__to__")
        suffix = "_circuit_v2.svg" if args.layout == "v2" else "_circuit.svg"
        out = swap_run_dir / "by_source" / src_slug / f"to_{tgt_slug}{suffix}"
    out_path = Path(out)
    svg = render_swap_intervention(
        swap_run_dir,
        args.swap_id,
        output_svg_path=out_path,
        max_per_row=args.max_per_row,
        compact=args.compact,
        layout=args.layout,
    )
    print(f"Wrote {len(svg)} bytes to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
