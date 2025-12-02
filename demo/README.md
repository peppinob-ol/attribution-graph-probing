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

1. Add to `requirements_hf.txt`:
   ```
   python-fasthtml>=0.6.0
   pandas>=2.0.0
   ```

2. Create Dockerfile or use Python runtime

3. Set entry point to `demo/main.py`

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

