"""Build a small HTML index just for paintings SemConc candidates."""
from __future__ import annotations

import html
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
GALLERY = REPO / "output" / "activation_heatmaps" / "_gallery"
INDEX = GALLERY / "_paintings_semconc.html"


def main() -> None:
    csv = REPO / "output" / "research" / "extra_semconc_paintings.csv"
    df = pd.read_csv(csv)
    df = df[df["rendered"] == True].copy()  # noqa: E712
    df.sort_values(["entity", "layer"], inplace=True)

    cards = []
    for _, r in df.iterrows():
        feat_url = (
            f"https://www.neuronpedia.org/gemma-2-2b/{int(r.layer)}-clt-hp/{int(r.feature)}"
        )
        card = f"""
        <div class=\"card\">
          <h3>{html.escape(str(r.entity))}</h3>
          <div class=\"meta\">
            L{int(r.layer):02d} / F{int(r.feature)} ·
            peak token <code>{html.escape(str(r.main_peak_token))}</code> ·
            consistency {r.peak_consistency_main:.2f} ·
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
<title>SemConc — paintings (candidates)</title>
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
<h1>SemConc — paintings_painters_batch</h1>
<p>{len(df)} candidates · top-2 per painting entity</p>
<div class=\"grid\">{''.join(cards)}</div>
</body></html>"""

    INDEX.write_text(page, encoding="utf-8")
    print(f"wrote {INDEX} ({len(df)} cards)")


if __name__ == "__main__":
    main()
