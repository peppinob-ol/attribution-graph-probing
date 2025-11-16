#!/bin/bash
# Proper fix for clt-hp chunking bug - handle None hook_name in both branches

NEURONPEDIA_DIR="/mnt/ssd-1/soar-automated_interpretability/graphs/giuseppe/neuronpedia"
ALL_PY="$NEURONPEDIA_DIR/apps/inference/neuronpedia_inference/endpoints/activation/all.py"

if [ ! -f "$ALL_PY" ]; then
    echo "ERROR: File not found: $ALL_PY"
    exit 1
fi

# Restore from backup if it exists
if [ -f "$ALL_PY.backup" ]; then
    echo "Restoring from backup..."
    cp "$ALL_PY.backup" "$ALL_PY"
fi

# Backup original
cp "$ALL_PY" "$ALL_PY.backup"

echo "Patching $ALL_PY to handle None hook_name in both branches..."

# Apply proper patch with Python (preserving indentation)
python3 << 'PYPATCH'
import re

file_path = "/mnt/ssd-1/soar-automated_interpretability/graphs/giuseppe/neuronpedia/apps/inference/neuronpedia_inference/endpoints/activation/all.py"

with open(file_path, 'r') as f:
    lines = f.readlines()

# Find and patch both cache accesses
patched_count = 0

for i, line in enumerate(lines):
    # Match lines with cache[hook_name].to(Config...
    if 'cache[hook_name].to(Config.get_instance().device)' in line and '=' in line:
        indent = len(line) - len(line.lstrip())
        indent_str = ' ' * indent
        
        # Determine variable name
        if 'mlp_activation_data' in line:
            var_name = 'mlp_activation_data'
            check_msg = f"Invalid hook_name for neurons: {{hook_name}}, selected_source: {{selected_source}}"
        else:
            var_name = 'activation_data'
            check_msg = f"Invalid hook_name: {{hook_name}}, selected_source: {{selected_source}}, cache_keys: {{list(cache.keys())[:5]}}"
        
        # Insert check before the line
        lines[i] = (
            f'{indent_str}if hook_name is None or hook_name not in cache:\n'
            f'{indent_str}    raise ValueError(f"{check_msg}")\n'
            f'{line}'
        )
        patched_count += 1
        print(f"Patched line {i+1}: {var_name}")

with open(file_path, 'w') as f:
    f.writelines(lines)

print(f"Patch applied successfully ({patched_count} locations)")
PYPATCH

echo "Done! Backup at $ALL_PY.backup"
echo "If the script now raises ValueError, check the error message for debugging info"

