"""
Build the four Dallas swap conditions for the human-vs-auto smoke test.

For each condition we need a self-contained `graphs_root` that the swap
pipeline can point at. The five target slugs (california_oakland, new_york_new_york_city,
florida_miami, illinois_chicago, washington_seattle) are the same auto run for
every condition; only `texas_dallas` differs. We use symlinks for the targets
and a custom node_grouping.csv for the source.

Conditions:
  auto_dallas             -- the auto pipeline's existing grouping (baseline)
  human_dallas            -- 22 human-pinned features tagged with the human supernodes
  auto_top21_dallas       -- top 21 features in auto's grouping by node_influence
                             (size-matched to the human's 22)
  shuffled_labels_dallas  -- the 22 human features with supernode labels shuffled

The reference graph (graph.json, graph_feature_static_metrics.csv) is identical
across conditions; the swap pipeline's pruning and influence statistics rely on
this. Only supernode tagging differs.

Outputs:
  output/usa_states_fact_batch/_swap_conditions/
      auto_dallas/
      human_dallas/
      auto_top21_dallas/
      shuffled_labels_dallas/

Each condition directory has six slug subdirs; texas_dallas is the customized
one, the rest are symlinks to the canonical auto runs.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
BATCH_ROOT = REPO / "output" / "usa_states_fact_batch"
COND_ROOT = BATCH_ROOT / "_swap_conditions"
HUMAN_JSON = REPO / "output" / "research" / "dallas_austin_reference" / "human_annotated_subgraph.json"

SOURCE_SLUG = "texas_dallas"
TARGET_SLUGS = [
    "california_oakland",
    "new_york_new_york_city",
    "florida_miami",
    "illinois_chicago",
    "washington_seattle",
]
ALL_SLUGS = [SOURCE_SLUG] + TARGET_SLUGS

CONDITIONS = ("auto_dallas", "human_dallas", "auto_top21_dallas", "shuffled_labels_dallas")


def _human_supernode_to_concept(name: str) -> str:
    """Map human-supernode display name to a concept tag the swap loader can match.

    The swap loader does case-insensitive substring matching:
        concept_field=state -> concept='texas' -> match supernode whose
        lowercased name contains 'texas'.

    For human supernodes whose name does not embed an entity-specific token, we
    leave the name untouched (e.g. 'capital'); these will only match the swap's
    `capital`-field if entity.capital == 'capital', which never happens, so they
    will not contribute to the labeled-style swap. That is the *intended*
    behavior -- the human only annotated 'Texas' as a state-named supernode, so
    only that one drives the state-field swap.
    """
    return name


def link_target(condition_dir: Path, slug: str) -> None:
    src = BATCH_ROOT / slug
    dst = condition_dir / slug
    if dst.exists() or dst.is_symlink():
        return
    dst.symlink_to(src.resolve())


def link_inner(slug_dir_dst: Path, slug_dir_src: Path) -> None:
    """Make slug_dir_dst the destination subdirs by symlinking each piece.
    Only `02 Node Grouping/node_grouping.csv` will be replaced per condition.
    """
    for sub in ("00 Graph Generation",):
        s = slug_dir_src / sub
        d = slug_dir_dst / sub
        d.parent.mkdir(parents=True, exist_ok=True)
        if not d.exists():
            d.symlink_to(s.resolve())
    (slug_dir_dst / "02 Node Grouping").mkdir(parents=True, exist_ok=True)


def load_canonical_grouping() -> pd.DataFrame:
    p = BATCH_ROOT / SOURCE_SLUG / "02 Node Grouping" / "node_grouping.csv"
    df = pd.read_csv(p)
    df["layer"] = df["layer"].astype(int)
    df["feature"] = df["feature"].astype(int)
    df["peak_token_idx"] = df["peak_token_idx"].astype(int)
    return df


def load_human_pinned():
    """Return list of (layer, feature, ctx_idx, human_supernode, is_supernode_member, clerp)."""
    h = json.loads(HUMAN_JSON.read_text())
    rows = []
    seen = set()
    for sn in h["supernodes"]:
        for m in sn["members"]:
            if m.get("feature_type") != "cross layer transcoder":
                continue
            layer = int(m["layer"])
            feat = int(m["node_id"].split("_")[1])
            ctx = int(m["ctx_idx"])
            key = (layer, feat, ctx)
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "layer": layer, "feature": feat, "ctx_idx": ctx,
                "human_supernode": sn["name"],
                "is_supernode_member": True,
                "human_clerp": "",
            })
    for n in h["pinned_nodes"]:
        if n.get("feature_type") != "cross layer transcoder":
            continue
        layer = int(n["node_id"].split("_")[0])
        feat = int(n["node_id"].split("_")[1])
        ctx = int(n["ctx_idx"])
        key = (layer, feat, ctx)
        if key in seen:
            continue
        seen.add(key)
        clerp = (n.get("clerp") or "").strip()
        rows.append({
            "layer": layer, "feature": feat, "ctx_idx": ctx,
            "human_supernode": "(standalone)", "is_supernode_member": False,
            "human_clerp": clerp,
        })
    return rows


def make_human_grouping(canonical: pd.DataFrame, pinned: list) -> pd.DataFrame:
    """Subset canonical grouping to the human-pinned (layer, feature, peak_token_idx),
    then override supernode_name with the human supernode label.
    """
    rows = []
    for r in pinned:
        match = canonical[(canonical.layer == r["layer"]) &
                          (canonical.feature == r["feature"]) &
                          (canonical.peak_token_idx == r["ctx_idx"])]
        if match.empty:
            match = canonical[(canonical.layer == r["layer"]) &
                              (canonical.feature == r["feature"])]
            if match.empty:
                print(f"  [WARN] human-pinned not in our grouping: L{r['layer']} F{r['feature']} ctx={r['ctx_idx']}")
                continue
            row = match.iloc[0].to_dict()
            row["peak_token_idx"] = r["ctx_idx"]
        else:
            row = match.iloc[0].to_dict()
        # Use the human label; fold "preposition followed by place name" into
        # "state" per Phase-3 design choice
        label = r["human_supernode"]
        if label == "preposition followed by place name":
            label = "state"
        if label == "(standalone)":
            label = r["human_clerp"] or f"standalone_{r['layer']}_{r['feature']}"
        row["supernode_name"] = label
        rows.append(row)
    df = pd.DataFrame(rows)
    df = df[canonical.columns.tolist()]
    return df


def make_top21_grouping(canonical: pd.DataFrame, source_dir: Path,
                         k: int = 21) -> pd.DataFrame:
    """Pick the top *k* unique CLT (l, f) features by node_influence, restricted
    to features that appear in the canonical grouping, and subset the canonical
    grouping to those (l, f) pairs (all ctx rows preserved, like the auto run).
    """
    metrics = pd.read_csv(source_dir / "00 Graph Generation" / "graph_feature_static_metrics.csv")
    metrics["layer"] = metrics["layer"].astype(int)
    if "id" in metrics.columns:
        metrics["feature"] = metrics["id"].astype(int)
    else:
        metrics["feature"] = metrics["feature"].astype(int)
    metrics = metrics[(metrics["layer"] >= 0) & (metrics["layer"] < 26)]
    canonical_keys = set(zip(canonical.layer.astype(int), canonical.feature.astype(int)))
    metrics = metrics[metrics.apply(
        lambda r: (int(r["layer"]), int(r["feature"])) in canonical_keys, axis=1
    )]
    metrics["max_inf"] = metrics.groupby(["layer", "feature"])["node_influence"].transform("max")
    unique = metrics.drop_duplicates(subset=["layer", "feature"]).sort_values(
        "max_inf", ascending=False
    ).head(k)
    keep_keys = {(int(r.layer), int(r.feature)) for r in unique.itertuples()}
    sub = canonical[canonical.apply(
        lambda r: (int(r["layer"]), int(r["feature"])) in keep_keys, axis=1
    )]
    return sub


def make_shuffled_labels(human: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = human.copy().reset_index(drop=True)
    perm = rng.permutation(len(df))
    df["supernode_name"] = df["supernode_name"].iloc[perm].reset_index(drop=True)
    return df


def main():
    if not HUMAN_JSON.exists():
        print(f"ERROR: {HUMAN_JSON} not found")
        sys.exit(1)
    for s in ALL_SLUGS:
        p = BATCH_ROOT / s
        if not p.exists():
            print(f"ERROR: {p} missing -- run smoke_fact_6states first")
            sys.exit(1)

    COND_ROOT.mkdir(parents=True, exist_ok=True)
    canonical = load_canonical_grouping()
    pinned = load_human_pinned()
    human_grp = make_human_grouping(canonical, pinned)
    top21_grp = make_top21_grouping(canonical, BATCH_ROOT / SOURCE_SLUG)
    shuffled_grp = make_shuffled_labels(human_grp)

    print(f"\n[BUILT GROUPINGS] auto={len(canonical)} human={len(human_grp)} top21={len(top21_grp)} shuffled={len(shuffled_grp)}")

    grp_per_condition = {
        "auto_dallas": canonical,
        "human_dallas": human_grp,
        "auto_top21_dallas": top21_grp,
        "shuffled_labels_dallas": shuffled_grp,
    }
    for cond in CONDITIONS:
        cdir = COND_ROOT / cond
        cdir.mkdir(parents=True, exist_ok=True)
        # Source slug: copy structure
        src_dir = cdir / SOURCE_SLUG
        link_inner(src_dir, BATCH_ROOT / SOURCE_SLUG)
        ng = src_dir / "02 Node Grouping" / "node_grouping.csv"
        grp_per_condition[cond].to_csv(ng, index=False)
        # manifest for transparency
        manifest = src_dir / "manifest.json"
        manifest.write_text(json.dumps({
            "condition": cond,
            "n_features_in_grouping": int(grp_per_condition[cond][["layer", "feature"]].drop_duplicates().shape[0]),
            "n_rows": int(len(grp_per_condition[cond])),
            "supernodes": sorted(grp_per_condition[cond]["supernode_name"].dropna().unique().tolist()),
        }, indent=2, ensure_ascii=False))
        # Targets: symlink
        for t in TARGET_SLUGS:
            link_target(cdir, t)
        print(f"  [{cond}] graphs_root={cdir} | source features={grp_per_condition[cond][['layer','feature']].drop_duplicates().shape[0]} | supernodes={len(grp_per_condition[cond]['supernode_name'].dropna().unique())}")


if __name__ == "__main__":
    main()
