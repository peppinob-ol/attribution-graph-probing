"""
Render extra SemDict-fallback candidates whose *fallback behaviour* is
visually legible: features that fire on the same concept across all probes
but whose peak token shifts (peak_consistency in (0.30, 0.95) and
n_distinct_peaks >= 2). Adds the rendered PNGs to the existing gallery and
emits a small HTML index for review.
"""
from __future__ import annotations

import html
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "research"))

from curate_emblematic_features import (  # noqa: E402
    has_dump,
    has_graph,
    is_content_token,
    role_of,
)
from render_emblematic_gallery import render_one  # noqa: E402

GALLERY = REPO / "output" / "activation_heatmaps" / "_gallery"
EXTRA_CSV = REPO / "output" / "research" / "extra_legible_fallback.csv"
INDEX_HTML = GALLERY / "_legible_fallback.html"
TOP_K_PER_DATASET = 3


def select() -> pd.DataFrame:
    df = pd.read_csv(REPO / "output" / "research" / "feature_manifest.csv")
    df["role"] = df.apply(role_of, axis=1)
    df = df[df["role"] == "SemDict-fallback"].copy()

    keep = df.apply(
        lambda r: has_dump(REPO, r["dataset"], r["entity"])
        and has_graph(REPO, r["dataset"], r["entity"]),
        axis=1,
    )
    df = df[keep].copy()
    df["content"] = df["main_peak_token"].apply(is_content_token)

    mask = (
        (df["n_active_prompts"] == df["n_prompts"])
        & (df["peak_consistency_main"] > 0.30)
        & (df["peak_consistency_main"] < 0.95)
        & (df["n_distinct_peaks"] >= 2)
        & df["content"]
    )
    sub = df[mask].copy()

    # Sweet spot peak_consistency ~0.6: clearly varies but still concentrated.
    sub["legibility"] = (
        1.5 * (1 - (sub["peak_consistency_main"] - 0.6).abs())
        + 0.6 * (sub["n_distinct_peaks"].clip(0, 4) / 4.0)
        + 0.4 * (sub["K_sem_distinct"].clip(0, 4) / 4.0)
        + 0.4 * (sub["layer"] <= 3).astype(int)
    )

    sub.sort_values("legibility", ascending=False, inplace=True)
    sub = sub.drop_duplicates(
        subset=["dataset", "entity", "layer", "feature"], keep="first"
    )

    picks = (
        sub.groupby("dataset", group_keys=False)
        .apply(lambda g: g.nlargest(TOP_K_PER_DATASET, "legibility"))
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
        lambda r: (
            f"SemDict-fallback__{r.dataset}__{r.entity}__"
            f"L{int(r.layer):02d}_F{int(r.feature)}.png"
        ),
        axis=1,
    )
    return picks


def render_all(picks: pd.DataFrame) -> pd.DataFrame:
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
    picks = picks.copy()
    picks["rendered"] = rendered
    return picks


def build_html(picks: pd.DataFrame) -> None:
    rows = picks[picks["rendered"] == True].copy()  # noqa: E712
    rows.sort_values(["dataset", "entity"], inplace=True)
    cards = []
    for _, r in rows.iterrows():
        feat_url = (
            f"https://www.neuronpedia.org/gemma-2-2b/{int(r.layer)}-clt-hp/{int(r.feature)}"
        )
        card = f"""
        <div class=\"card\">
          <h3>{html.escape(str(r.dataset))} / {html.escape(str(r.entity))}</h3>
          <div class=\"meta\">
            L{int(r.layer):02d} / F{int(r.feature)} ·
            peak <code>{html.escape(str(r.main_peak_token))}</code> ·
            consistency {r.peak_consistency_main:.2f} ·
            distinct peaks {int(r.n_distinct_peaks)} ·
            K_sem={int(r.K_sem_distinct)}
            <a href=\"{feat_url}\" target=\"_blank\">np</a>
          </div>
          <a href=\"{html.escape(r.png_name)}\" target=\"_blank\">
            <img src=\"{html.escape(r.png_name)}\" alt=\"{html.escape(r.png_name)}\" />
          </a>
        </div>
        """
        cards.append(card)
    page = f"""<!doctype html>
<html><head>
<meta charset=\"utf-8\" />
<title>SemDict-fallback (legible) candidates</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; padding: 24px; background: #fafafa; }}
  h1 {{ margin-bottom: 4px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(540px, 1fr)); gap: 24px; }}
  .card {{ background: #fff; border: 1px solid #e0e0e0; border-radius: 6px; padding: 12px; }}
  .card h3 {{ margin: 0 0 4px 0; font-size: 14px; color: #333; }}
  .meta {{ font-size: 12px; color: #666; margin-bottom: 8px; }}
  .meta code {{ background: #f0f0f0; padding: 1px 4px; border-radius: 3px; }}
  .meta a {{ color: #08c; margin-left: 6px; }}
  .card img {{ width: 100%; height: auto; border: 1px solid #eee; }}
</style>
</head><body>
<h1>SemDict-fallback &mdash; legible-fallback candidates</h1>
<p>{len(rows)} candidates · top-{TOP_K_PER_DATASET} per dataset</p>
<p>Selection: peak_consistency in (0.30, 0.95) AND n_distinct_peaks >= 2 AND
content peak token AND fires on every probe.</p>
<div class=\"grid\">{''.join(cards)}</div>
</body></html>"""
    INDEX_HTML.write_text(page, encoding="utf-8")
    print(f"wrote {INDEX_HTML} ({len(rows)} cards)")


def main() -> None:
    picks = select()
    picks = render_all(picks)
    EXTRA_CSV.parent.mkdir(parents=True, exist_ok=True)
    picks.to_csv(EXTRA_CSV, index=False)
    build_html(picks)


if __name__ == "__main__":
    main()
