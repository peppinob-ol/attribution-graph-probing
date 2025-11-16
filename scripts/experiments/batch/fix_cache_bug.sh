#!/bin/bash
# Quick patch for TransformerLens ActivationCache bug with chunking
# Apply this on the remote node before running batch experiments with CHUNK_BY_LAYER=true

NEURONPEDIA_DIR="/mnt/ssd-1/soar-automated_interpretability/graphs/giuseppe/neuronpedia"
ALL_PY="$NEURONPEDIA_DIR/apps/inference/neuronpedia_inference/endpoints/activation/all.py"

if [ ! -f "$ALL_PY" ]; then
    echo "ERROR: File not found: $ALL_PY"
    exit 1
fi

# Backup original
cp "$ALL_PY" "$ALL_PY.backup" 2>/dev/null || true

echo "Patching $ALL_PY to handle None hook_name..."

# Create patched version with Python (more reliable than sed for multi-line)
python3 << 'PYPATCH'
import sys

file_path = "/mnt/ssd-1/soar-automated_interpretability/graphs/giuseppe/neuronpedia/apps/inference/neuronpedia_inference/endpoints/activation/all.py"

with open(file_path, 'r') as f:
    lines = f.readlines()

# Find and patch line 285 (0-indexed = 284)
# Original: activation_data = cache[hook_name].to(Config.get_instance().device)
# Patched: Add None check before

for i, line in enumerate(lines):
    if 'activation_data = cache[hook_name].to(Config.get_instance().device)' in line:
        indent = len(line) - len(line.lstrip())
        # Insert check before this line
        lines[i] = ' ' * indent + 'if hook_name is None:\n'
        lines.insert(i+1, ' ' * (indent+4) + 'raise ValueError(f"hook_name is None for selected_source")\n')
        lines.insert(i+2, line)  # Original line
        print(f"Patched line {i+1}")
        break

with open(file_path, 'w') as f:
    f.writelines(lines)

print("Patch applied successfully")
PYPATCH

echo "Done! Backup at $ALL_PY.backup"

