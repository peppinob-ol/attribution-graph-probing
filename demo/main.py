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
"""
import sys
from pathlib import Path

from fasthtml.common import fast_app, serve
from starlette.staticfiles import StaticFiles

from app.routes.home import home_routes
from app.routes.api import api_routes
from app.routes.state import state_routes
from app.data.loader import DataLoader

# Paths
DEMO_DIR = Path(__file__).parent
STATIC_DIR = DEMO_DIR / "static"
DATA_DIR = DEMO_DIR.parent / "output" / "usa_states_batch"

# Check for --annotate flag
ANNOTATE_MODE = "--annotate" in sys.argv

# Initialize data loader
data_loader = DataLoader(DATA_DIR)

# Create FastHTML app
app, rt = fast_app(debug=True)

# Mount static files directory
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

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
