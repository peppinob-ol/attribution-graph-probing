import sys

file_path = sys.argv[1] if len(sys.argv) > 1 else "scripts/experiments/debug_source_construction.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('✓', '[OK]')
content = content.replace('⚠', '[WARN]')
content = content.replace('×', '[X]')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Cleaned {file_path}")

