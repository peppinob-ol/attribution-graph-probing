"""
Render every emblematic-candidate CPAS figure, then build an HTML gallery
indexed by role x dataset for fast browsing/selection.
"""
from __future__ import annotations

import html
import shlex
import subprocess
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
CSV = REPO / "output" / "research" / "emblematic_candidates.csv"
GALLERY = REPO / "output" / "activation_heatmaps" / "_gallery"
HEATMAP_SCRIPT = REPO / "scripts" / "visualization" / "activation_heatmap.py"
PYTHON = REPO / ".venv" / "bin" / "python"

ROLE_ORDER = [
    "SemDict-strict",
    "SemDict-fallback",
    "SemConc",
    "Relationship",
    "Say-X",
]
DATASET_ORDER = [
    "usa_states_batch",
    "book_characters_authors_batch",
    "products_founders_batch",
    "paintings_painters_batch",
    "sounds_colors_batch",
]


def render_one(dump_path: Path, feature_id: str, png_path: Path) -> bool:
    """Run the existing activation_heatmap script in stacked-feature mode."""
    out_dir = png_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # The renderer always names its output as feature_<id>_stacked.png inside
    # --output-dir. We render into a temp subdir then move/rename.
    tmp_dir = out_dir / "_tmp"
    if tmp_dir.exists():
        for p in tmp_dir.iterdir():
            p.unlink()
    tmp_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(PYTHON), str(HEATMAP_SCRIPT),
        str(dump_path),
        "--feature-id", feature_id,
        "-o", str(tmp_dir),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=REPO)
    except subprocess.CalledProcessError as e:
        print(f"FAILED: {feature_id} on {dump_path}")
        print(e.stderr[-500:])
        return False
    expected = tmp_dir / f"feature_{feature_id.replace(':', '_')}_stacked.png"
    if not expected.exists():
        print(f"MISSING OUTPUT: {expected}")
        return False
    expected.rename(png_path)
    return True


def render_gallery() -> pd.DataFrame:
    df = pd.read_csv(CSV)
    df["png_rel"] = df["png_name"]
    statuses = []
    for i, row in df.iterrows():
        png = GALLERY / row["png_name"]
        ok = True
        if not png.exists():
            ok = render_one(REPO / row["dump_path"], row["feature_id"], png)
        statuses.append(ok)
        print(f"[{i+1:>2}/{len(df)}] {'OK' if ok else 'FAIL'}  {row['png_name']}")
    df["rendered"] = statuses
    return df


def build_html(df: pd.DataFrame) -> Path:
    """Build a per-role x dataset HTML index for fast browsing."""
    df = df[df["rendered"]].copy()
    parts: list[str] = []
    parts.append(
        """<!doctype html><html><head><meta charset='utf-8'>
<title>Emblematic CPAS Feature Gallery</title>
<style>
 body { font-family: -apple-system, sans-serif; margin: 16px; background: #fafafa; }
 h1 { margin-bottom: 4px; }
 h2 { margin: 20px 0 8px; padding: 6px 8px; background: #eef; border-left: 4px solid #66a; }
 h3 { margin: 12px 0 6px; padding: 4px 6px; background: #f4f4f4; border-left: 3px solid #999; font-weight: 600; }
 .card { display: inline-block; margin: 6px 8px 14px 0; vertical-align: top; max-width: 720px; }
 .meta { font-family: ui-monospace, Menlo, monospace; font-size: 11px; color: #333; padding: 4px 6px; background: #fff; border: 1px solid #ddd; border-bottom: 0; }
 img { max-width: 720px; border: 1px solid #ddd; display: block; }
 .nav { background: #fff; padding: 6px; border: 1px solid #ddd; margin-bottom: 12px; font-size: 12px; }
 .nav a { margin-right: 10px; }
</style></head><body>
"""
    )
    parts.append("<h1>Emblematic CPAS Feature Gallery</h1>")
    parts.append("<p>Top candidates per (role, dataset). Pick winners for the appendix; cell scoring rules in <code>scripts/research/curate_emblematic_features.py</code>.</p>")

    parts.append("<div class='nav'>")
    for role in ROLE_ORDER:
        parts.append(f"<a href='#{role}'>{html.escape(role)}</a>")
    parts.append("</div>")

    for role in ROLE_ORDER:
        parts.append(f"<h2 id='{role}'>{html.escape(role)}</h2>")
        for ds in DATASET_ORDER:
            sub = df[(df["role"] == role) & (df["dataset"] == ds)].sort_values("score", ascending=False)
            if sub.empty:
                continue
            parts.append(f"<h3>{html.escape(ds)}</h3>")
            for _, r in sub.iterrows():
                meta = (
                    f"{r['feature_id']}  ·  entity={r['entity']}  ·  peak={r['main_peak_token']!r}  "
                    f"·  pcm={float(r['peak_consistency_main']):.2f}  K_sem={int(r['K_sem_distinct'])}  "
                    f"sparsity={float(r['sparsity_median']):.2f}  n_active={int(r['n_active_prompts'])}/{int(r['n_prompts'])}  "
                    f"score={float(r['score']):.2f}"
                )
                parts.append(
                    "<div class='card'>"
                    f"<div class='meta'>{html.escape(meta)}</div>"
                    f"<img src='{html.escape(r['png_name'])}' loading='lazy'/></div>"
                )

    parts.append("</body></html>")
    out = GALLERY / "index.html"
    out.write_text("\n".join(parts), encoding="utf-8")
    return out


def main() -> None:
    df = render_gallery()
    out = build_html(df)
    print(f"\nGallery HTML: {out}")
    print(f"Gallery dir : {GALLERY}")


if __name__ == "__main__":
    main()
