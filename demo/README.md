# State Swap Explorer

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

## Project Structure

```
demo/
├── main.py                    # FastHTML entry point
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

The live demo is deployed at: https://huggingface.co/spaces/Peppinob/state-swap-steering-explorer

**HF Spaces repo location:** `C:\Github\state-swap-steering-explorer`

#### To deploy updates:

1. **Sync files from demo to HF repo:**
   ```powershell
   # Copy all source files
   Copy-Item -Path "C:\Github\circuit_tracer-prompt_rover\demo\main.py" -Destination "C:\Github\state-swap-steering-explorer\main.py" -Force
   Copy-Item -Path "C:\Github\circuit_tracer-prompt_rover\demo\Dockerfile" -Destination "C:\Github\state-swap-steering-explorer\Dockerfile" -Force
   Copy-Item -Path "C:\Github\circuit_tracer-prompt_rover\demo\requirements.txt" -Destination "C:\Github\state-swap-steering-explorer\requirements.txt" -Force
   Copy-Item -Path "C:\Github\circuit_tracer-prompt_rover\demo\README_HF.md" -Destination "C:\Github\state-swap-steering-explorer\README.md" -Force
   Copy-Item -Path "C:\Github\circuit_tracer-prompt_rover\demo\app\*" -Destination "C:\Github\state-swap-steering-explorer\app\" -Recurse -Force
   Copy-Item -Path "C:\Github\circuit_tracer-prompt_rover\demo\static\*" -Destination "C:\Github\state-swap-steering-explorer\static\" -Recurse -Force
   ```

2. **Commit and push:**
   ```powershell
   cd C:\Github\state-swap-steering-explorer
   git add .
   git commit -m "Sync updates from demo"
   git push
   ```

#### Important Notes:

- **README.md frontmatter colors:** HF Spaces only accepts these values for `colorFrom`/`colorTo`:
  `red`, `yellow`, `green`, `blue`, `indigo`, `purple`, `pink`, `gray`
  
  Do NOT use `emerald`, `amber`, etc. - they will cause push rejection.

- **Don't commit `__pycache__`** - already in `.gitignore`

- The HF Spaces repo contains the `data/` folder with experiment results (not in this demo folder)

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

