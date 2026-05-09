"""
Curate emblematic features per role x dataset for the appendix CPAS gallery.

Reads the cross-dataset feature manifest, defines a role-specific
"emblematic-ness" score, picks the top-N candidates per (role, dataset) cell,
and emits a CSV that the renderer can iterate over.

Roles:
- SemDict-strict   : stable single-token semantic detector (Sem-Dict, strict)
- SemDict-fallback : early-layer semantic feature, dictionary-by-fallback
- SemConc          : multi-peak semantic, concept-level
- Relationship     : dense, low-sparsity (no clear single peak)
- Say-X            : late-layer feature peaking on a functional token

Output: output/research/emblematic_candidates.csv
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "output" / "research" / "feature_manifest.csv"
OUT_CSV = REPO / "output" / "research" / "emblematic_candidates.csv"

DATASETS = (
    "usa_states_batch",
    "book_characters_authors_batch",
    "products_founders_batch",
    "paintings_painters_batch",
)

# Tokens we deprioritize as "uninterpretable" peaks for SemDict / SemConc roles.
# Subword fragments with leading punctuation/digits, single chars, etc.
UNINTERESTING_TOKENS = {
    "", "<bos>", "<eos>", "<unk>", "<|endoftext|>", "<|begin_of_text|>",
    ".", ",", ":", ";", "?", "!", '"', "'", "(", ")", "[", "]", "{", "}",
    "-", "_", "/", "\\",
}

# Functional-vocabulary list mirrors paper appendix.
FUNCTIONAL_TOKENS = {
    # copulas
    "is", "was", "are", "were", "be", "been", "being", "am", "'s", "'re", "'m",
    # articles / demonstratives
    "the", "a", "an", "this", "that", "these", "those",
    # prepositions
    "of", "in", "on", "at", "to", "for", "with", "by", "from", "as",
    "into", "onto", "upon", "about", "above", "below", "between",
    "among", "through", "during", "before", "after",
    # conjunctions
    "and", "or", "but", "nor", "so", "yet",
    # relative / wh
    "which", "who", "whom", "whose", "where", "when", "why", "how",
    # auxiliaries
    "do", "does", "did", "have", "has", "had", "will", "would",
    "shall", "should", "can", "could", "may", "might", "must",
}


def is_alpha_word(tok: str) -> bool:
    """True if the displayed token has alphabetic content >= 2 chars."""
    if not isinstance(tok, str):
        return False
    s = tok.strip().lower()
    if s in UNINTERESTING_TOKENS:
        return False
    if len(s) < 2:
        return False
    return sum(c.isalpha() for c in s) >= 2


def is_content_token(tok: str) -> bool:
    """Alpha word that isn't in the English functional vocabulary."""
    if not is_alpha_word(tok):
        return False
    return tok.strip().lower() not in FUNCTIONAL_TOKENS


def is_functional_token(tok: str) -> bool:
    if not isinstance(tok, str):
        return False
    return tok.strip().lower() in FUNCTIONAL_TOKENS


def has_dump(repo: Path, dataset: str, entity: str) -> bool:
    return (repo / "output" / dataset / entity / "01 Prompt Probing" / "activations_dump.json").exists()


def has_graph(repo: Path, dataset: str, entity: str) -> bool:
    return (repo / "output" / dataset / entity / "00 Graph Generation" / "graph.json").exists()


def role_of(row: pd.Series) -> str | None:
    pl = row.get("pred_label")
    st = row.get("subtype")
    if pl == "Relationship":
        return "Relationship"
    if pl == 'Say "X"':
        return "Say-X"
    if pl == "Semantic":
        if st == "Dictionary":
            return "SemDict-strict"
        if st == "Dictionary (fallback)":
            return "SemDict-fallback"
        if st == "Concept":
            return "SemConc"
    return None


def emblematic_score(row: pd.Series) -> float:
    """Higher is more emblematic for the row's role.

    Each per-role score is roughly in [0, 6] and rewards:
      - clear alignment with the role's defining metric pattern
      - broad activation across probes (we want the figure to actually show signal)
      - interpretable / content-bearing peak tokens for semantic roles
      - functional peak tokens for Say-X
    """
    role = row["role"]
    pcm = float(row.get("peak_consistency_main", 0))
    nact = int(row.get("n_active_prompts", 0))
    nprompts = max(1, int(row.get("n_prompts", 5)))
    nactf = nact / nprompts
    layer = int(row.get("layer", 0))
    conf_F = float(row.get("conf_F", 0))
    K_sem = int(row.get("K_sem_distinct", 0))
    spar = float(row.get("sparsity_median", 0))
    tok = row.get("main_peak_token", "")
    content = 1.0 if is_content_token(tok) else 0.0
    functional = 1.0 if is_functional_token(tok) else 0.0
    alpha = 1.0 if is_alpha_word(tok) else 0.0

    if role == "SemDict-strict":
        # Stable single-token detector on a CONTENT word. We deliberately
        # penalize functional-peak features here so this row showcases
        # content-dictionary behavior distinct from Say-X.
        if nact < 3:
            return -1.0
        return (
            1.6 * pcm
            + 1.4 * nactf
            + 1.5 * content
            - 1.2 * functional
            + 0.4 * (1 if layer <= 2 else 0)
        )

    if role == "SemDict-fallback":
        # Early-layer (<=3) semantic feature with a content peak; the
        # peak_consistency is structurally lower than the strict subtype.
        if nact < 3:
            return -1.0
        return (
            1.5 * nactf
            + 0.7 * pcm
            + 1.2 * content
            - 0.8 * functional
            + 0.7 * (1 if layer <= 3 else 0)
        )

    if role == "SemConc":
        # Concept-level: peaks across multiple semantic tokens of the same kind.
        if nact < 4:
            return -1.0
        return (
            1.4 * nactf
            + 1.0 * (1 if K_sem >= 2 else 0)
            + 0.8 * (1 if K_sem in (3, 4) else 0)
            + 1.0 * content
            + 0.6 * (1 if 4 <= layer <= 18 else 0)
        )

    if role == "Relationship":
        # Dense, low-sparsity: should fire across many tokens of multiple
        # probes -- low sparsity_median is the signature, but we also need
        # the figure to actually have non-zero activations.
        if nact < 2:
            return -1.0
        return (
            2.0 * (1.0 - min(spar, 1.0))
            + 1.0 * nactf
            + 0.6 * (1 if 1 <= layer <= 18 else 0)
        )

    if role == "Say-X":
        # Late-layer feature peaking on a functional token with high conf_F.
        if nact < 3:
            return -1.0
        return (
            1.4 * conf_F
            + 1.4 * pcm
            + 1.2 * nactf
            + 1.0 * functional
            + 0.4 * (1 if layer >= 10 else 0)
        )

    return 0.0


def main() -> None:
    df = pd.read_csv(MANIFEST)
    df["role"] = df.apply(role_of, axis=1)
    df = df[df["role"].notna()].copy()

    # Restrict to entities with both a dump and a graph available.
    keep_mask = df.apply(
        lambda r: has_dump(REPO, r["dataset"], r["entity"])
        and has_graph(REPO, r["dataset"], r["entity"]),
        axis=1,
    )
    df = df[keep_mask].copy()

    df["score"] = df.apply(emblematic_score, axis=1)

    # For each (role, dataset, layer, feature), keep the entity with the best score.
    df.sort_values("score", ascending=False, inplace=True)
    dedup = df.drop_duplicates(subset=["role", "dataset", "layer", "feature"], keep="first")

    # Pick top-K per (role, dataset) cell. K=3 gives the user material to choose from
    # while keeping the gallery render budget below ~75 figures.
    K = 3
    picks = (
        dedup.groupby(["role", "dataset"], group_keys=False)
        .apply(lambda g: g.nlargest(K, "score"))
        .reset_index(drop=True)
    )

    # Tidy columns and write.
    cols = [
        "role", "dataset", "entity", "layer", "feature",
        "main_peak_token", "peak_consistency_main", "n_distinct_peaks",
        "K_sem_distinct", "func_vs_sem_pct", "conf_F", "conf_S",
        "sparsity_median", "n_active_prompts", "n_prompts",
        "pred_label", "subtype", "score",
    ]
    picks = picks[cols]
    picks["feature_id"] = picks.apply(lambda r: f"{int(r.layer)}-clt-hp:{int(r.feature)}", axis=1)
    picks["dump_path"] = picks.apply(
        lambda r: f"output/{r.dataset}/{r.entity}/01 Prompt Probing/activations_dump.json",
        axis=1,
    )
    picks["png_name"] = picks.apply(
        lambda r: f"{r.role}__{r.dataset}__{r.entity}__L{int(r.layer):02d}_F{int(r.feature)}.png",
        axis=1,
    )

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    picks.to_csv(OUT_CSV, index=False)

    # Print a per-(role, dataset) summary.
    print(f"Wrote {len(picks)} candidates to {OUT_CSV}")
    print()
    summary = picks.groupby(["role", "dataset"]).size().unstack(fill_value=0)
    print(summary.to_string())


if __name__ == "__main__":
    main()
