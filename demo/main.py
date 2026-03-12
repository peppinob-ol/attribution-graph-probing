"""
State Swap Explorer - FastHTML Demo App

Interactive visualization of circuit steering experiments across US states.
Built with FastHTML + Vanilla JS islands + Tailwind CSS.

Usage:
    cd demo
    pip install -r requirements.txt
    python main.py              # View-only mode
    python main.py --annotate   # Annotation mode (allows editing tiers/notes)

Then open http://localhost:8000

Environment Variables:
    DATA_DIR - Path to usa_states_batch data (for HF Spaces deployment)
"""
import os
import sys
from pathlib import Path

from fasthtml.common import fast_app, serve
from starlette.middleware.base import BaseHTTPMiddleware

class NoCacheMiddleware(BaseHTTPMiddleware):
    """Add no-cache headers to island JS files to prevent stale code."""
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static/islands/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

from app.routes.home import home_routes
from app.routes.api import api_routes
from app.routes.state import state_routes
from app.data.loader import DataLoader

# Paths
DEMO_DIR = Path(__file__).parent
STATIC_DIR = DEMO_DIR / "static"

# Data directory: check env var first (for HF Spaces), then local paths
if os.environ.get("DATA_DIR"):
    DATA_DIR = Path(os.environ["DATA_DIR"])
elif (DEMO_DIR / "data").exists():
    # HF Spaces: data bundled in demo/data/
    DATA_DIR = DEMO_DIR / "data"
else:
    # Local development: data in ../output/usa_states_batch/
    DATA_DIR = DEMO_DIR.parent / "output" / "usa_states_batch"

# Check for --annotate flag
ANNOTATE_MODE = "--annotate" in sys.argv

# Initialize data loader
data_loader = DataLoader(DATA_DIR)

# Create FastHTML app (static_path=DEMO_DIR so /static/* resolves to demo/static/*)
app, rt = fast_app(debug=True, static_path=str(DEMO_DIR))

# Add no-cache middleware for island JS files
app.add_middleware(NoCacheMiddleware)

# Register routes
home_routes(app, rt, data_loader, ANNOTATE_MODE)
api_routes(app, rt, data_loader, ANNOTATE_MODE)
state_routes(app, rt, data_loader)


if __name__ == "__main__":
    # Parse port from args
    port = 8000
    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])
    
    print("=" * 60)
    print("State Swap Explorer")
    if ANNOTATE_MODE:
        print(">>> ANNOTATION MODE ENABLED <<<")
        print("  - Press 1-5 to change tier")
        print("  - Press N to add/edit notes")
    print("=" * 60)
    print(f"Static directory: {STATIC_DIR}")
    print(f"Data directory: {DATA_DIR}")
    
    if DATA_DIR.exists():
        states = list(DATA_DIR.iterdir())
        state_count = len([s for s in states if s.is_dir() and not s.name.startswith('_')])
        print(f"States found: {state_count}")
    
    print("-" * 60)
    print(f"Starting server at http://localhost:{port}")
    print("-" * 60)
    
    serve(port=port)
