#!/usr/bin/env python3
"""
Sync the demo app into a local Hugging Face Space checkout.

By default this syncs:
- app code and static assets from demo/
- the Space README from demo/README_HF.md
- only demo-enabled datasets from local output/ -> <space>/data

This keeps the Space aligned with the same multi-dataset demo view used locally.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
DEMO_DIR = SCRIPT_PATH.parent
REPO_ROOT = DEMO_DIR.parent
DEFAULT_SPACE_DIR = Path.home() / "state-swap-steering-explorer"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "output"
HF_BLOCKED_BINARY_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".pdf",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync demo files to a HF Space checkout.")
    parser.add_argument(
        "--space-dir",
        type=Path,
        default=DEFAULT_SPACE_DIR,
        help=f"Local HF Space checkout (default: {DEFAULT_SPACE_DIR})",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help=f"Local output root to mirror into <space>/data (default: {DEFAULT_OUTPUT_ROOT})",
    )
    parser.add_argument(
        "--skip-data",
        action="store_true",
        help="Sync code only and leave the existing <space>/data directory untouched.",
    )
    return parser.parse_args()


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def replace_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def remove_pycache(root: Path) -> None:
    for path in root.rglob("__pycache__"):
        if path.is_dir():
            shutil.rmtree(path)


def remove_work_dirs(root: Path) -> int:
    """Remove _work directories (GPU batch artifacts not needed for the demo)."""
    removed = 0
    for path in root.rglob("_work"):
        if path.is_dir():
            shutil.rmtree(path)
            removed += 1
    return removed


def remove_hf_blocked_binaries(root: Path) -> int:
    removed = 0
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in HF_BLOCKED_BINARY_SUFFIXES:
            path.unlink()
            removed += 1
    return removed


def require_dir(path: Path, label: str) -> None:
    if not path.exists() or not path.is_dir():
        raise SystemExit(f"{label} not found: {path}")


def _load_demo_registry(output_root: Path):
    sys.path.insert(0, str(DEMO_DIR))
    try:
        from app.data.loader import DemoRegistry
    finally:
        sys.path.pop(0)
    return DemoRegistry(output_root)


def copy_demo_datasets(output_root: Path, target_root: Path) -> Dict[str, object]:
    registry = _load_demo_registry(output_root)
    datasets = registry.list_datasets()
    if not datasets:
        raise SystemExit(f"No demo-enabled datasets found under: {output_root}")

    if target_root.exists():
        shutil.rmtree(target_root)
    target_root.mkdir(parents=True, exist_ok=True)

    copied_labels: List[str] = []
    for ds in datasets:
        src_dir = output_root / ds["id"]
        if not src_dir.exists():
            raise SystemExit(f"Expected dataset directory not found: {src_dir}")
        replace_tree(src_dir, target_root / ds["id"])
        copied_labels.append(ds["label"])

    return {
        "dataset_count": len(datasets),
        "dataset_labels": copied_labels,
    }


def summarize_output_root(output_root: Path) -> str:
    registry = _load_demo_registry(output_root)
    datasets = registry.list_datasets()
    runs = registry.list_all_runs()
    active_loader = registry.active_loader
    active_run = active_loader.get_current_run() if active_loader else "none"
    active_domain = (
        active_loader.get_domain_config().get("display_name", "Unknown")
        if active_loader else "Unknown"
    )
    return (
        f"datasets={len(datasets)} "
        f"runs={len(runs)} "
        f"active_dataset={registry.active_dataset_id or 'none'} "
        f"active_run={active_run or 'none'} "
        f"domain={active_domain}"
    )


def main() -> int:
    args = parse_args()
    space_dir = args.space_dir.resolve()
    output_root = args.output_root.resolve()

    require_dir(space_dir, "Space directory")
    if not (space_dir / ".git").exists():
        raise SystemExit(f"Space checkout is not a git repository: {space_dir}")

    file_map = {
        DEMO_DIR / "main.py": space_dir / "main.py",
        DEMO_DIR / "Dockerfile": space_dir / "Dockerfile",
        DEMO_DIR / "requirements.txt": space_dir / "requirements.txt",
        DEMO_DIR / "README_HF.md": space_dir / "README.md",
    }

    for src, dst in file_map.items():
        copy_file(src, dst)

    replace_tree(DEMO_DIR / "app", space_dir / "app")
    replace_tree(DEMO_DIR / "static", space_dir / "static")

    if not args.skip_data:
        require_dir(output_root, "Output root")
        data_copy_info = copy_demo_datasets(output_root, space_dir / "data")
        removed_binary_count = remove_hf_blocked_binaries(space_dir / "data")
        removed_work_count = remove_work_dirs(space_dir / "data")
    else:
        data_copy_info = None
        removed_binary_count = 0
        removed_work_count = 0

    remove_pycache(space_dir)

    print(f"Synced demo app to {space_dir}")
    if args.skip_data:
        print("Data sync: skipped")
    else:
        print(f"Data sync: demo-enabled datasets from {output_root} -> {space_dir / 'data'}")
        print(f"Datasets copied: {data_copy_info['dataset_count']} ({', '.join(data_copy_info['dataset_labels'])})")
        print(f"Removed HF-blocked binaries: {removed_binary_count}")
        if removed_work_count:
            print(f"Removed _work dirs: {removed_work_count}")
        print(f"Data summary: {summarize_output_root(space_dir / 'data')}")
    print("Next steps:")
    print(f"  cd {space_dir}")
    print("  git status")
    print("  git add main.py Dockerfile requirements.txt README.md app static data")
    print('  git commit -m "Sync demo"')
    print("  git push")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
