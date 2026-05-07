"""
Render extra SemConc candidates for the paintings dataset (top-2 per painting
entity) so the user has a wider pool to pick from. Idempotent: reuses any PNG
that already exists in the gallery folder.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "research"))

from curate_emblematic_features import emblematic_score, role_of, has_dump, has_graph  # noqa: E402
from render_emblematic_gallery import render_one  # noqa: E402

GALLERY = REPO / "output" / "activation_heatmaps" / "_gallery"
EXTRA_CSV = REPO / "output" / "research" / "extra_semconc_paintings.csv"


def main() -> None:
    df = pd.read_csv(REPO / "output" / "research" / "feature_manifest.csv")
    df["role"] = df.apply(role_of, axis=1)
    df = df[(df["role"] == "SemConc") & (df["dataset"] == "paintings_painters_batch")].copy()

    keep = df.apply(
        lambda r: has_dump(REPO, r["dataset"], r["entity"])
        and has_graph(REPO, r["dataset"], r["entity"]),
        axis=1,
    )
    df = df[keep].copy()
    df["score"] = df.apply(emblematic_score, axis=1)
    df.sort_values("score", ascending=False, inplace=True)
    df = df.drop_duplicates(subset=["entity", "layer", "feature"], keep="first")

    # Top 2 per entity gives one painter-name feature + one painting/painter
    # generic feature for almost every painting.
    picks = (
        df.groupby("entity", group_keys=False)
        .apply(lambda g: g.nlargest(2, "score"))
        .reset_index(drop=True)
    )

    picks["feature_id"] = picks.apply(
        lambda r: f"{int(r.layer)}-clt-hp:{int(r.feature)}", axis=1
    )
    picks["dump_path"] = picks.apply(
        lambda r: f"output/{r.dataset}/{r.entity}/01 Prompt Probing/activations_dump.json",
        axis=1,
    )
    picks["png_name"] = picks.apply(
        lambda r: f"{r.role}__{r.dataset}__{r.entity}__L{int(r.layer):02d}_F{int(r.feature)}.png",
        axis=1,
    )

    cols = [
        "role", "dataset", "entity", "layer", "feature",
        "main_peak_token", "peak_consistency_main", "K_sem_distinct",
        "sparsity_median", "n_active_prompts", "score",
        "feature_id", "dump_path", "png_name",
    ]
    picks = picks[cols]
    EXTRA_CSV.parent.mkdir(parents=True, exist_ok=True)
    picks.to_csv(EXTRA_CSV, index=False)

    GALLERY.mkdir(parents=True, exist_ok=True)
    rendered = []
    for i, row in picks.iterrows():
        png = GALLERY / row["png_name"]
        if png.exists():
            print(f"[{i+1:>2}/{len(picks)}] SKIP {row['png_name']}")
            rendered.append(True)
            continue
        ok = render_one(REPO / row["dump_path"], row["feature_id"], png)
        rendered.append(ok)
        print(f"[{i+1:>2}/{len(picks)}] {'OK' if ok else 'FAIL'}  {row['png_name']}")
    picks["rendered"] = rendered
    picks.to_csv(EXTRA_CSV, index=False)


if __name__ == "__main__":
    main()
