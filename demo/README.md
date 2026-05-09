# Concept Swap Explorer

Interactive visualization of circuit steering experiments across US states. Built with FastHTML (Python backend), Vanilla JS islands, and Tailwind CSS.

## Overview

This demo app visualizes the results of steering experiments between US state knowledge circuits. Click on any cell in the heatmap to see detailed swap results, including:

- **Default vs Steered outputs** - Compare model outputs before and after intervention
- **Tier classification** - Success level from T1 (failed) to T5 (perfect)
- **First token analysis** - Token probabilities before/after steering
- **Neuronpedia links** - Direct links to subgraph visualizations

## Quick Start

### Prerequisites

- Python 3.10+
- Experiment data in `../output/usa_states_batch/`

### Installation

```bash
cd demo
pip install -r requirements.txt
```

### Run

```bash
python main.py
```

Open http://localhost:8000 in your browser.

By default, the local demo auto-discovers demo-enabled runs in `../output/` and
prefers `usa_states_batch` when it is available. To force a specific dataset,
either point `DATA_DIR` at one dataset or set `DEMO_DEFAULT_DATASET`.

Examples:

```bash
DEMO_DEFAULT_DATASET=book_characters_authors_batch python main.py
DATA_DIR=../output/usa_states_batch python main.py
```

## Project Structure

```
demo/
├── main.py                    # FastHTML entry point
├── Dockerfile                 # Hugging Face Spaces container
├── requirements.txt           # Python dependencies
├── app/
│   ├── routes/
│   │   ├── home.py            # Main page with matrix
│   │   ├── api.py             # JSON API endpoints
│   │   └── state.py           # State profile pages
│   ├── data/
│   │   └── loader.py          # Data loader for experiment results
│   └── components/
│       └── layout.py          # Reusable HTML components
├── static/
│   ├── css/
│   │   └── tailwind.css       # Pre-compiled Tailwind CSS
│   └── islands/
│       ├── Matrix.js          # Interactive heatmap
│       └── DetailPanel.js     # Slide-in detail panel
├── islands/                   # Svelte source (optional)
│   ├── Matrix.svelte
│   ├── DetailPanel.svelte
│   ├── package.json
│   └── build.js
└── README.md
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Main page with matrix visualization |
| `GET /state/{slug}` | State profile page |
| `GET /api/matrix` | Tier matrix as JSON |
| `GET /api/states` | All states with metadata |
| `GET /api/stats` | Aggregate statistics |
| `GET /api/swap/{from}/{to}` | Detailed swap result |
| `GET /api/state/{slug}` | State profile data |
| `GET /api/analysis` | Full analysis data |

## Tier System

| Tier | Name | Description | Color |
|------|------|-------------|-------|
| 5 | PERFECT | Target capital found in output | Emerald |
| 4 | STATE + CITY | Target state city found (not capital) | Lime |
| 3 | STATE ONLY | Target state mentioned only | Yellow |
| 2 | SUPPRESSED | Source suppressed, no target content | Orange |
| 1 | SOURCE PERSISTS | Source capital still in output | Red |

## Data Sources

The app reads from `../output/usa_states_batch/`:

- `_swaps/_matrix.csv` - Tier matrix
- `_swaps/_analysis_v3/*.json` - Analysis data
- `_swaps/by_source/*/to_*.json` - Individual swap results
- `*/manifest.json` - Neuronpedia URLs and metadata

### Neuronpedia subgraph URLs

By default, the demo opens a simplified Neuronpedia graph URL by constructing `pinnedIds` and `supernodes`.

If you want to open the uploaded Neuronpedia subgraph (using `manifest.json -> neuronpedia.subgraph_id`), call:

- `GET /api/state/{slug}/subgraph-url?mode=complete`

## Building Svelte Islands (Optional)

If you want to modify the Svelte components:

```bash
cd islands
npm install
npm run build    # One-time build
npm run watch    # Watch mode for development
```

This compiles `.svelte` files to `../static/islands/*.js`.

Note: Pre-compiled vanilla JS versions are included, so this step is optional.

## Rebuilding Tailwind CSS (Optional)

If you modify the CSS:

```bash
npx tailwindcss -i ./static/css/input.css -o ./static/css/tailwind.css --watch
```

## Deployment

### Hugging Face Spaces

This demo is packaged for a Docker Space and can be synced into a small Hugging Face repo that keeps the experiment data in a top-level `data/` folder.

#### Files to sync

- `demo/main.py` -> `main.py`
- `demo/Dockerfile` -> `Dockerfile`
- `demo/requirements.txt` -> `requirements.txt`
- `demo/README_HF.md` -> `README.md`
- `demo/app/` -> `app/`
- `demo/static/` -> `static/`
- demo-enabled dataset folders from `output/` -> `data/`

The Space should mirror the same demo-enabled datasets that local development
discovers in `output/`. After sync, the Space runs in multi-dataset mode with
`OUTPUT_DIR=/app/data`, so its header and run selector should match local.

#### Recommended sync workflow

```bash
python demo/sync_hf_space.py --space-dir /path/to/concept-swap-explorer
```

By default this script:

- syncs app code from `demo/`
- syncs the Space landing page from `demo/README_HF.md`
- scans local `output/` for `display_demo: true` runs
- copies only those dataset directories into the Space `data/` root
- removes binary analysis artifacts such as `.png` files that Hugging Face rejects on push
- removes copied `__pycache__` directories
- prints a quick data summary after the copy

Use `--skip-data` only when you intentionally want to preserve the existing
Space dataset.

#### Manual sync fallback

```bash
HF_REPO=/path/to/concept-swap-explorer

cp demo/main.py "$HF_REPO/main.py"
cp demo/Dockerfile "$HF_REPO/Dockerfile"
cp demo/requirements.txt "$HF_REPO/requirements.txt"
cp demo/README_HF.md "$HF_REPO/README.md"
python3 -c 'from pathlib import Path; import shutil
src = Path("demo")
output_root = Path("output")
dst = Path("'"$HF_REPO"'")
for name in ("app", "static"):
    target = dst / name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(src / name, target)
data_target = dst / "data"
if data_target.exists():
    shutil.rmtree(data_target)
data_target.mkdir(parents=True, exist_ok=True)
for dataset in (
    "book_characters_authors_batch",
    "paintings_painters_batch",
    "products_founders_batch",
    "usa_states_batch",
):
    shutil.copytree(output_root / dataset, data_target / dataset)
for path in data_target.rglob("*"):
    if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf"}:
        path.unlink()
for path in dst.rglob("__pycache__"):
    if path.is_dir():
        shutil.rmtree(path)'
```

#### Verification

Before pushing, verify the synced Space data from inside the Space checkout:

```bash
OUTPUT_DIR=./data python3 -c 'from app.data.loader import DemoRegistry; from pathlib import Path
reg = DemoRegistry(Path("data"))
print(reg.list_datasets())
print(reg.list_all_runs())'
```

You should see the same demo datasets and runs that local `demo/main.py`
discovers from `output/`.

#### Local container check

```bash
cd "$HF_REPO"
docker build -t concept-swap-explorer .
docker run --rm -p 7860:7860 concept-swap-explorer
```

Open `http://localhost:7860`.

#### Push to Hugging Face

```bash
cd "$HF_REPO"
git status
git add main.py Dockerfile requirements.txt README.md app static
git commit -m "Update Space app from demo"
git push
```

#### Notes

- Local development reads `../output/` by default, while the Space reads `./data`.
  The sync step above is what keeps those two worlds aligned.
- The Space Docker image sets `OUTPUT_DIR=/app/data`, so `data/` must contain
  dataset folders like `usa_states_batch/` and `book_characters_authors_batch/`,
  not a single dataset unpacked directly at the root.
- The Space app does not need analysis plot images from `_swaps`, and Hugging Face
  rejects those binary files in regular git pushes. The sync script removes them.
- `README.md` frontmatter colors in a Space must use supported values such as `blue`, `indigo`, `green`, or `yellow`.
- Do not commit `__pycache__`.
- The demo container listens on port `7860` and uses `uvicorn main:app --host 0.0.0.0`.

### Vercel / Railway

FastHTML apps can be deployed as serverless functions or containers.

## Features

- **Interactive 50x50 Matrix** - Sortable by state name, native probability, supernodes, or tier averages
- **Hover Preview** - Quick info on hover
- **Click Details** - Slide-in panel with full swap information
- **State Profiles** - Dedicated page for each state's performance
- **Neuronpedia Integration** - Direct links to subgraph visualizations
- **Responsive Design** - Works on desktop and mobile

## Tech Stack

- **Backend:** FastHTML (Python)
- **Frontend:** Vanilla JS islands (Svelte-compatible)
- **Styling:** Tailwind CSS
- **Fonts:** Space Grotesk + JetBrains Mono

