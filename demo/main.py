"""
Swap Explorer - FastHTML Demo App

Interactive visualization of circuit steering experiments (domain-agnostic).
Built with FastHTML + Vanilla JS islands + Tailwind CSS.

Usage:
    cd demo
    pip install -r requirements.txt
    python main.py                                  # Auto-discover datasets in ../output
    python main.py --output-dir ../output           # Explicit output root
    python main.py --data-dir ../output/book_characters_authors_batch  # Single dataset
    python main.py --annotate                       # Annotation mode

Then open http://localhost:8000

Environment Variables:
    OUTPUT_DIR - Path to output root for multi-dataset discovery
    DATA_DIR   - Path to a single dataset directory (legacy / HF Spaces)
"""
import os
import sys
from pathlib import Path

from fasthtml.common import fast_app, serve
from starlette.middleware.base import BaseHTTPMiddleware


class NoCacheMiddleware(BaseHTTPMiddleware):
    """Prevent browsers from caching dynamic pages and island JS."""
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path
        if (path == "/" or path.startswith("/api/")
                or path.startswith("/state/")
                or path.startswith("/static/islands/")):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


from app.routes.home import home_routes
from app.routes.api import api_routes
from app.routes.state import state_routes
from app.data.loader import DataLoader, DemoRegistry

# Paths
DEMO_DIR = Path(__file__).parent
STATIC_DIR = DEMO_DIR / "static"

# Parse CLI args
DATA_DIR = None
OUTPUT_DIR = None
for i, arg in enumerate(sys.argv):
    if arg == "--data-dir" and i + 1 < len(sys.argv):
        DATA_DIR = Path(sys.argv[i + 1])
    if arg == "--output-dir" and i + 1 < len(sys.argv):
        OUTPUT_DIR = Path(sys.argv[i + 1])

ANNOTATE_MODE = "--annotate" in sys.argv

# Resolve output root and data dir from env if not given via CLI
if OUTPUT_DIR is None and os.environ.get("OUTPUT_DIR"):
    OUTPUT_DIR = Path(os.environ["OUTPUT_DIR"])
if DATA_DIR is None and os.environ.get("DATA_DIR"):
    DATA_DIR = Path(os.environ["DATA_DIR"])

# Default output root is ../output relative to the demo folder
if OUTPUT_DIR is None:
    OUTPUT_DIR = DEMO_DIR.parent / "output"

# Build registry (always): it only activates if demo-enabled runs are found.
# When DATA_DIR is given, it becomes the preferred initial dataset.
registry = DemoRegistry(OUTPUT_DIR, initial_data_dir=DATA_DIR)

if registry.active_loader is not None:
    # Multi-dataset mode: delegate the active DataLoader through the registry
    data_loader = registry.active_loader
else:
    # Fallback: no display_demo runs found – use a single DataLoader
    if DATA_DIR is None:
        if (DEMO_DIR / "data").exists():
            DATA_DIR = DEMO_DIR / "data"
        else:
            DATA_DIR = OUTPUT_DIR / "usa_states_batch"
    data_loader = DataLoader(DATA_DIR)
    registry = None

# Create FastHTML app (static_path=DEMO_DIR so /static/* resolves to demo/static/*)
app, rt = fast_app(debug=True, static_path=str(DEMO_DIR))

# Add no-cache middleware for island JS files
app.add_middleware(NoCacheMiddleware)

# Register routes (registry may be None for legacy single-dataset mode)
home_routes(app, rt, data_loader, ANNOTATE_MODE, registry=registry)
api_routes(app, rt, data_loader, ANNOTATE_MODE, registry=registry)
state_routes(app, rt, data_loader)


if __name__ == "__main__":
    port = 8000
    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])

    dc = data_loader.get_domain_config()
    print("=" * 60)
    print(f"Swap Explorer  [{dc.get('display_name', 'Unknown Domain')}]")
    if ANNOTATE_MODE:
        print(">>> ANNOTATION MODE ENABLED <<<")
        print("  - Press 1-5 to change tier")
        print("  - Press N to add/edit notes")
    print("=" * 60)
    print(f"Static directory: {STATIC_DIR}")
    print(f"Output root:      {OUTPUT_DIR}")
    if registry:
        datasets = registry.list_datasets()
        print(f"Datasets found:   {len(datasets)}")
        for ds in datasets:
            marker = "*" if ds["is_active"] else " "
            print(f"  {marker} {ds['label']}  ({ds['run_count']} run(s))")
    else:
        print(f"Data directory:   {DATA_DIR}")
    print(f"Model:            {dc.get('model_id', 'N/A')}")
    print(f"Domain:           {dc.get('experiment_name', 'N/A')}")
    print("-" * 60)
    print(f"Starting server at http://localhost:{port}")
    print("-" * 60)

    serve(port=port)
