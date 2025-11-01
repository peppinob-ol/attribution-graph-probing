"""
Entry point for Hugging Face Spaces deployment
Redirects to the main Streamlit app in eda/app.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import and run the main app
# This allows the app to work both locally and on HF Spaces
# without modifying the original eda/app.py structure

# Change to eda directory context
import os
os.chdir(project_root)

# Import the main app module
from eda import app

# The streamlit app will be executed automatically when this module is loaded

