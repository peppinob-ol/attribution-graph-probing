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


def _batch_root_from_run_dir(swap_run_dir: Path) -> Path:
    """``output/<batch>/_swaps/runs/<run>`` -> ``output/<batch>``.

    Works for every domain (USA, Books, Products, Paintings) since the batch
    layout is always ``output/<batch>/_swaps/runs/<run>/...``.
    """
    return Path(swap_run_dir).parent.parent.parent


def _slug_to_entity_dir(batch_root: Path, slug: str) -> Path:
    """``<slug>`` -> ``<batch_root>/<entity_dir>`` (case-folding tolerant).

    USA stores per-entity dirs as e.g. ``california_Oakland`` (capitalised
    second token); Books / Products / Paintings store them lowercase. We
    therefore try the raw slug first, then fall back to a case-insensitive
    scan of the batch root.
    """
    direct = batch_root / slug
    if direct.is_dir():
        return direct
    slug_lc = slug.lower()
    for candidate in batch_root.iterdir():
        if candidate.is_dir() and candidate.name.lower() == slug_lc:
            return candidate
    raise FileNotFoundError(f"Could not find entity dir for slug {slug!r} under {batch_root}")


# Back-compat alias: a few external scripts may still call the old name.
_slug_to_state_dir = lambda slug: _slug_to_entity_dir(USA_DIR, slug)  # noqa: E731


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
    substitutions: list[tuple[str, str]],
) -> str:
    """Substitute source domain tokens with target ones inside a supernode label.

    ``substitutions`` is a list of ``(src_token, tgt_token)`` pairs. Longer
    source tokens are applied first to avoid partial matches stealing characters
    from a longer one (e.g. ``Idaho Falls`` must run before ``Idaho``).
    """
    out = src_name
    ordered = sorted(
        ((s, t) for s, t in substitutions if s and t),
        key=lambda x: -len(x[0]),
    )
    for src_tok, tgt_tok in ordered:
        out = _make_substitution_re(src_tok).sub(tgt_tok, out)
    return out


# --------------------------------------------------------------------------- #
# Domain schema (USA / Books / Products / Paintings)                          #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _DomainSchema:
    """Field bindings for a single benchmark domain.

    Tells the renderer how to build entity cards and which source/target
    metadata fields to use when pairing supernode names across domains.

    Fields:
        name: short tag used in logs/CLI ("usa" / "books" / "products" / "paintings").
        required_meta_keys: keys that must all be present in the swap result's
            ``source`` block to consider this schema a match.
        headline_key: meta key holding the answer string shown as the entity
            card headline (e.g. "capital" for USA, "author" for Books).
        field_keys: ordered list of ``(label, meta_key)`` pairs displayed in
            the entity card under the headline.
        substitution_keys: meta keys whose values seed the supernode-name
            substitution dictionary used to map ablated supernodes onto
            amplified ones (the analogue of "Texas->California" rewriting).
        embedding_key: meta key holding the prompt-anchor entity that becomes
            the bottom "Emb:" node in the graph (city for USA, character for
            Books, product for Products, painting for Paintings).
        topk_keys: ``(from_key, to_key)`` to look up baseline probabilities
            in ``evaluation.target_in_topk`` for the unsteered column of
            the trajectory plot.
    """

    name: str
    required_meta_keys: tuple[str, ...]
    headline_key: str
    field_keys: tuple[tuple[str, str], ...]
    substitution_keys: tuple[str, ...]
    embedding_key: str
    topk_keys: tuple[str, str]


_DOMAIN_SCHEMAS: tuple[_DomainSchema, ...] = (
    _DomainSchema(
        name="usa",
        required_meta_keys=("state", "capital", "city"),
        headline_key="capital",
        field_keys=(("state", "state"), ("city", "city")),
        substitution_keys=("state", "capital", "city"),
        embedding_key="city",
        topk_keys=("from_capital_in_default_topk", "to_capital_in_default_topk"),
    ),
    _DomainSchema(
        name="books",
        required_meta_keys=("character", "book", "author"),
        headline_key="author",
        field_keys=(("book", "book"), ("character", "character")),
        substitution_keys=("character", "book", "author"),
        embedding_key="character",
        topk_keys=("from_answer_in_default_topk", "to_answer_in_default_topk"),
    ),
    _DomainSchema(
        name="products",
        required_meta_keys=("product", "company", "founder"),
        headline_key="founder",
        field_keys=(("company", "company"), ("product", "product")),
        substitution_keys=("product", "company", "founder"),
        embedding_key="product",
        topk_keys=("from_answer_in_default_topk", "to_answer_in_default_topk"),
    ),
    _DomainSchema(
        name="paintings",
        required_meta_keys=("painting", "painter", "first_name"),
        headline_key="first_name",
        field_keys=(("painter", "painter"), ("painting", "painting")),
        substitution_keys=("painting", "painter", "first_name"),
        embedding_key="painting",
        topk_keys=("from_answer_in_default_topk", "to_answer_in_default_topk"),
    ),
)


def _detect_schema(source_meta: dict) -> _DomainSchema:
    """Pick the first schema whose ``required_meta_keys`` are all present.

    Raises ``ValueError`` if no schema matches; this guards the renderer
    against silently producing nonsense for an unknown domain.
    """
    for schema in _DOMAIN_SCHEMAS:
        if all(k in source_meta for k in schema.required_meta_keys):
            return schema
    raise ValueError(
        f"Could not identify domain schema from source meta keys "
        f"{sorted(source_meta.keys())!r}; supported schemas: "
        f"{[s.name for s in _DOMAIN_SCHEMAS]}"
    )


def _build_substitutions(
    schema: _DomainSchema, src_meta: dict, tgt_meta: dict
) -> list[tuple[str, str]]:
    """Build ``[(src_tok, tgt_tok), ...]`` from the schema's substitution keys."""
    return [
        (str(src_meta.get(k, "") or ""), str(tgt_meta.get(k, "") or ""))
        for k in schema.substitution_keys
    ]


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
    features_path: str | Path | None = None,
    result_path: str | Path | None = None,
    entity_root: str | Path | None = None,
) -> str:
    """Render an intervention SVG for a single swap, showing every intervened supernode.

    Args:
        swap_run_dir: path to ``output/<batch>/_swaps/runs/<run>`` for any
            domain (USA states, Books characters, Products, Paintings).
        swap_id: ``<src_slug>__to__<tgt_slug>``.
        output_svg_path: where to write the SVG, or ``None`` to only return the string.
        max_per_row: cap on supernode boxes per row (cosmetic; default 4 keeps it readable).
        compact: if ``True`` (default), render with the portrait-oriented compact
            layout matching the published Anthropic figure; if ``False``, use the
            upstream landscape layout.
        layout: ``"compact"`` (default) is the standalone graph; ``"v2"`` adds a
            top header strip (PROMPT | ORIGINAL PREDICTION | AFTER INTERVENTION)
            and a bottom per-position trajectory plot; ``"strip"`` is a horizontal
            cards + outputs + features + trajectory layout.
        features_path: optional override for ``features.json``. Use this when the
            swap result file lives in one run dir but the feature list lives in
            another (Books field-additivity case studies, where ``result.json``
            is in a dated run and ``features.json`` is under
            ``fullscale_books_field_add/work/<swap_id>__add_<variant>/``).
            Defaults to ``swap_run_dir/work/<swap_id>/features.json``.
        entity_root: optional override for the per-entity directory root
            (defaults to the parent of ``swap_run_dir/_swaps``, i.e. the
            domain's batch root). Useful when running tests from outside the
            standard ``output/<batch>`` layout.

    Returns:
        The raw SVG markup.
    """
    swap_run_dir = Path(swap_run_dir)
    src_slug, _, tgt_slug = swap_id.partition("__to__")
    if not (src_slug and tgt_slug):
        raise ValueError(f"swap_id must be '<src>__to__<tgt>', got {swap_id!r}")

    feats_file = (
        Path(features_path)
        if features_path is not None
        else swap_run_dir / "work" / swap_id / "features.json"
    )
    if not feats_file.exists():
        raise FileNotFoundError(f"features.json not found at {feats_file}")

    result_file = (
        Path(result_path)
        if result_path is not None
        else swap_run_dir / "by_source" / src_slug / f"to_{tgt_slug}.json"
    )
    if not result_file.exists():
        raise FileNotFoundError(f"swap result not found at {result_file}")
    feats = json.loads(feats_file.read_text(encoding="utf-8"))
    result = json.loads(result_file.read_text(encoding="utf-8"))

    batch_root = Path(entity_root) if entity_root is not None else _batch_root_from_run_dir(swap_run_dir)
    src_dir = _slug_to_entity_dir(batch_root, src_slug)
    tgt_dir = _slug_to_entity_dir(batch_root, tgt_slug)

    src_meta = result.get("source") or {}
    tgt_meta = result.get("target") or {}
    schema = _detect_schema(src_meta)

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

    substitutions = _build_substitutions(schema, src_meta, tgt_meta)

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
        paired = _pair_replacement_name(ab.name, substitutions)
        repl_data = amplified.get(paired)
        replacement_name: str | None = None
        if repl_data is not None and repl_data.name not in used_amplified:
            replacement_name = repl_data.name
            # Translate the original's children to their replacement counterparts
            # so the renderer draws orange arrows out of the replacement node.
            repl_children: list[str] = []
            for cname in children or []:
                translated = _pair_replacement_name(cname, substitutions)
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

    # Embedding (prompt-anchor entity) at the bottom; feeds into all
    # concept-row supernodes. Domain-dependent: city for USA, character for
    # Books, product for Products, painting for Paintings.
    src_embedding = (src_meta.get(schema.embedding_key) or "").strip()
    emb_name = f"Emb: {src_embedding}" if src_embedding else "Emb"
    specs.append(
        SupernodeSpec(
            name=emb_name,
            features=None,
            children=[a.name for a in ablated_concept],
        )
    )

    rows: list[list[str]] = [[emb_name]]
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
            result=result,
            schema=schema,
            specs=specs,
            rows=rows,
            prompt=title_prompt,
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

    if layout == "strip":
        return _render_strip(
            result=result,
            schema=schema,
            ablated_concept=ablated_concept,
            ablated_say=ablated_say,
            amplified=amplified,
            M_ablate=M_ablate,
            M_amplify=M_amplify,
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


def _build_trajectory_plot(result: dict, schema: _DomainSchema):
    """Construct a :class:`TrajectoryPlot` from a swap ``result.json``.

    Lifted out of ``_render_strip`` so the v2 layout can render the exact
    same per-position curve below its prompt + before/after header + graph.
    Both layouts therefore share one curve renderer (no duplicate plot
    logic), with v2 wrapping it in a portrait canvas and the strip layout
    placing it side-by-side with the entity / output / feature panels.

    Domain-aware: trajectory token fallbacks come from the schema's headline
    field for USA (``capital``) and from ``evaluation.from_answer`` /
    ``to_answer`` for Books / Products / Paintings, which is where
    ``run_swap.py`` records the canonical answer string. Baseline-prob
    fallbacks for the unsteered column likewise consult the schema-specific
    keys in ``evaluation.target_in_topk``.
    """
    from circuit_svg_strip import TrajectoryPlot

    src_meta = result.get("source") or {}
    tgt_meta = result.get("target") or {}
    evaluation = result.get("evaluation") or {}

    src_headline_fallback = (
        str(src_meta.get(schema.headline_key) or "")
        or str(evaluation.get("from_answer") or "")
    )
    tgt_headline_fallback = (
        str(tgt_meta.get(schema.headline_key) or "")
        or str(evaluation.get("to_answer") or "")
    )

    raw = evaluation.get("raw", {})
    traj_root = evaluation.get("logit_trajectory", {}) or {}
    target_block = (traj_root.get("trajectories") or {}).get("target", {})
    source_block = (traj_root.get("trajectories") or {}).get("source", {})
    target_traj = target_block.get("trajectory") or {}
    source_traj = source_block.get("trajectory") or {}
    positions = list(target_traj.get("positions") or source_traj.get("positions") or [])
    target_probs = list(target_traj.get("probs") or [])
    source_probs = list(source_traj.get("probs") or [])
    generated_tokens = list(traj_root.get("generated_tokens") or [])
    target_token = target_block.get("token") or tgt_headline_fallback
    source_token = source_block.get("token") or src_headline_fallback

    def _normalise_probs(seq: list, length: int) -> list[float | None]:
        out: list[float | None] = []
        for i in range(length):
            if i < len(seq) and seq[i] is not None:
                try:
                    out.append(float(seq[i]))
                except (TypeError, ValueError):
                    out.append(None)
            else:
                out.append(None)
        return out

    n = len(positions)
    if not positions and generated_tokens:
        positions = list(range(len(generated_tokens)))
        n = len(positions)
    target_probs_n = _normalise_probs(target_probs, n)
    source_probs_n = _normalise_probs(source_probs, n)
    if len(generated_tokens) < n:
        generated_tokens = generated_tokens + [""] * (n - len(generated_tokens))
    else:
        generated_tokens = generated_tokens[:n]

    # Prepend an [unsteered] baseline column at position 0 so the chart shows
    # the natural M=0 starting point next to the steered trajectory.
    def _topk_lookup(topk: list, token: str) -> float | None:
        if not token:
            return None
        for entry in topk or []:
            if entry.get("token") == token:
                try:
                    return float(entry.get("prob", 0.0))
                except (TypeError, ValueError):
                    return None
        return None

    default_topk = raw.get("default_topk") or []
    target_in_topk = evaluation.get("target_in_topk") or {}
    from_topk_key, to_topk_key = schema.topk_keys
    src_base = _topk_lookup(default_topk, source_token)
    if src_base is None:
        src_base = target_in_topk.get(from_topk_key)
    tgt_base = _topk_lookup(default_topk, target_token)
    if tgt_base is None:
        tgt_base = target_in_topk.get(to_topk_key)
    # Tokens that fall outside default top-k still have a (very small) prob;
    # rendering them as 0.0 keeps the curves connected at the [unsteered]
    # column instead of breaking into separate dashed segments.
    src_base = float(src_base) if src_base is not None else 0.0
    tgt_base = float(tgt_base) if tgt_base is not None else 0.0

    positions = [-1, *positions]
    generated_tokens = ["[unsteered]", *generated_tokens]
    source_probs_n = [src_base, *source_probs_n]
    target_probs_n = [tgt_base, *target_probs_n]

    return TrajectoryPlot(
        positions=positions,
        generated_tokens=generated_tokens,
        source_token=source_token,
        target_token=target_token,
        probs_source=source_probs_n,
        probs_target=target_probs_n,
        primary_position=1,
    )


def _entity_card_from_meta(
    role: str, meta: dict, schema: _DomainSchema, answer_fallback: str
):
    """Build an :class:`EntityCard` from a swap result's ``source`` or ``target`` block.

    The headline is the answer field for the domain (capital / author /
    founder / first_name); the body fields are taken from
    ``schema.field_keys``. ``answer_fallback`` is used when the per-domain
    headline key is absent (e.g. the author was generated but missing in
    the metadata block) -- typically ``evaluation.from_answer`` or
    ``to_answer``.
    """
    from circuit_svg_strip import EntityCard

    headline = str(meta.get(schema.headline_key) or "").strip() or answer_fallback
    fields: list[tuple[str, str]] = []
    for label, key in schema.field_keys:
        val = str(meta.get(key) or "").strip()
        if val:
            fields.append((label, val))
    return EntityCard(role=role, headline=headline, fields=fields)


def _render_strip(
    *,
    result: dict,
    schema: _DomainSchema,
    ablated_concept: list[_SupernodeData],
    ablated_say: list[_SupernodeData],
    amplified: dict[str, _SupernodeData],
    M_ablate: int,
    M_amplify: int,
    output_svg_path: str | Path | None,
) -> str:
    """Render the horizontal strip layout: cards + outputs + features + position plot.

    Domain-aware: entity cards, supernode pairing, and trajectory token
    fallbacks all consult ``schema`` so the renderer works uniformly across
    USA states, Books, Products, and Paintings.
    """
    from circuit_svg_strip import SupernodeRow, create_strip_visualization

    src_meta = result.get("source") or {}
    tgt_meta = result.get("target") or {}
    evaluation = result.get("evaluation") or {}

    src_answer = str(evaluation.get("from_answer") or "")
    tgt_answer = str(evaluation.get("to_answer") or "")
    src_card = _entity_card_from_meta("Source", src_meta, schema, src_answer)
    tgt_card = _entity_card_from_meta("Target", tgt_meta, schema, tgt_answer)

    # Words to highlight in the default/steered output panels: the actual
    # full answer strings (e.g. "Salt Lake City", "F. Scott Fitzgerald",
    # "Phil Knight", "Claude Monet"), falling back to the headline key.
    src_word = src_card.headline or src_answer
    tgt_word = tgt_card.headline or tgt_answer

    raw = evaluation.get("raw", {})
    default_text = raw.get("default_output", "") or ""
    steered_text = raw.get("steered_output", "") or ""

    ablated_rows = [
        SupernodeRow(name=s.name, feature_count=len(s.triples))
        for s in (*ablated_concept, *ablated_say)
    ]
    amplified_rows = [
        SupernodeRow(name=s.name, feature_count=len(s.triples))
        for s in sorted(amplified.values(), key=lambda x: -len(x.triples))
    ]
    # Totals reflect every ablated/amplified feature applied in the run, not
    # just the (up to 2 + 2) groupings rendered in the panels.
    interventions = result.get("interventions") or {}
    ablate_total = int(interventions.get("ablate_count") or 0)
    amplify_total = int(interventions.get("amplify_count") or 0)

    trajectory = _build_trajectory_plot(result, schema)

    svg_str = create_strip_visualization(
        source_card=src_card,
        target_card=tgt_card,
        default_output=default_text,
        steered_output=steered_text,
        source_word=src_word,
        target_word=tgt_word,
        ablated=ablated_rows,
        amplified=amplified_rows,
        ablate_total_features=ablate_total,
        amplify_total_features=amplify_total,
        ablate_title="Ablated",
        amplify_title="Amplified",
        ablate_badge=f"{M_ablate:+d}x",
        amplify_badge=f"+{M_amplify}x" if M_amplify > 0 else f"{M_amplify}x",
        trajectory=trajectory,
    )

    if output_svg_path is not None:
        out = Path(output_svg_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(svg_str, encoding="utf-8")
    return svg_str


def _render_v2(
    *,
    result: dict,
    schema: _DomainSchema,
    specs: list[SupernodeSpec],
    rows: list[list[str]],
    prompt: str,
    default_first: tuple[str, float],
    steered_first: tuple[str, float],
    output_svg_path: str | Path | None,
) -> str:
    """Build an InterventionGraph and call the v2 renderer.

    The bottom plot shares the per-position trajectory panel with the strip
    layout (see :func:`_build_trajectory_plot`), so v2 and strip render the
    exact same source/target probability curves -- only the surrounding chrome
    differs (portrait header + graph for v2, horizontal cards/outputs/feature
    panels for strip).
    """
    from circuit_svg_v2 import create_v2_visualization

    nodes_by_name = _build_supernode_objects(specs)
    ordered_nodes = [[nodes_by_name[name] for name in row] for row in rows]
    intervention_graph = InterventionGraph(ordered_nodes=ordered_nodes, prompt=prompt)
    for node in nodes_by_name.values():
        intervention_graph.nodes[node.name] = node

    trajectory = _build_trajectory_plot(result, schema)

    svg_obj = create_v2_visualization(
        intervention_graph,
        prompt=prompt,
        original_pred=default_first,
        after_pred=steered_first,
        trajectory=trajectory,
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


_BATCH_ALIASES: dict[str, str] = {
    "usa": "usa_states_batch",
    "books": "book_characters_authors_batch",
    "products": "products_founders_batch",
    "paintings": "paintings_painters_batch",
}


def _cli(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    parser.add_argument(
        "--batch",
        default="usa",
        help=(
            "Domain batch name. Either an alias (usa / books / products / "
            "paintings) or the literal directory name under output/. "
            "Default: usa."
        ),
    )
    parser.add_argument(
        "--run",
        default="full_50states_v1",
        help="Swap run name under output/<batch>/_swaps/runs/",
    )
    parser.add_argument(
        "--swap-run-dir",
        default=None,
        help=(
            "Full path to the swap run dir, overriding --batch / --run. "
            "Use this when the run directory name doesn't follow the "
            "<batch>/_swaps/runs/<run> convention."
        ),
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
        "--features-path",
        default=None,
        help=(
            "Override the path to features.json for this swap. Required when "
            "the result file and the feature list live in different run dirs "
            "(typical for Books field-additivity case studies)."
        ),
    )
    parser.add_argument(
        "--result-path",
        default=None,
        help=(
            "Override the path to the swap result JSON. Required when the "
            "field-additivity variant suffix (e.g. ``__add_state_capital_city``) "
            "is part of the result filename instead of the swap_id."
        ),
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
        choices=("compact", "v2", "strip"),
        default="compact",
        help=(
            "'compact' = single graph (default); 'v2' = prompt + before/after + "
            "trajectory plot; 'strip' = horizontal cards + outputs + features + "
            "trajectory plot."
        ),
    )
    parser.set_defaults(compact=True)
    args = parser.parse_args(argv)

    if args.swap_run_dir is not None:
        swap_run_dir = Path(args.swap_run_dir)
    else:
        batch_name = _BATCH_ALIASES.get(args.batch, args.batch)
        swap_run_dir = REPO_ROOT / "output" / batch_name / "_swaps" / "runs" / args.run

    out = args.output
    if out is None:
        src_slug, _, tgt_slug = args.swap_id.partition("__to__")
        suffix = {
            "v2": "_circuit_v2.svg",
            "strip": "_circuit_strip.svg",
        }.get(args.layout, "_circuit.svg")
        out = swap_run_dir / "by_source" / src_slug / f"to_{tgt_slug}{suffix}"
    out_path = Path(out)
    svg = render_swap_intervention(
        swap_run_dir,
        args.swap_id,
        output_svg_path=out_path,
        max_per_row=args.max_per_row,
        compact=args.compact,
        layout=args.layout,
        features_path=Path(args.features_path) if args.features_path else None,
        result_path=Path(args.result_path) if args.result_path else None,
    )
    print(f"Wrote {len(svg)} bytes to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
