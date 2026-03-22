"""
Swap run directory management (traceable, non-overwriting outputs).

This module implements a lightweight experiment tracking pattern:
- Each invocation of run_batch_swaps writes to a unique run directory under:
    {graphs_root}/_swaps/runs/{run_id}/
- A run contains:
    - run_manifest.json (metadata: timestamps, git info, config hashes, CLI args)
    - config snapshots (swap config + optional source config)
    - by_source/ (per-pair results)
    - work/ (per-pair work files)

Design goals:
- Keep runs immutable and traceable (no silent overwrites).
- Keep it simple (no external tracking system required).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple


# scripts/experiments/batch/pipeline -> repo root is parents[4]
REPO_ROOT = Path(__file__).resolve().parents[4]


RUNS_DIRNAME = "runs"
LATEST_RUN_FILENAME = "_latest_run.txt"
RUN_INDEX_FILENAME = "_runs_index.jsonl"


def sanitize_run_id(text: str, *, max_len: int = 120) -> str:
    """
    Sanitize text for safe directory names (Windows-friendly).

    Keeps only ASCII letters/digits and a small safe set: "._-".
    Everything else becomes "_".
    """
    if not text:
        return "run"
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", text)
    safe = re.sub(r"_+", "_", safe).strip("._-")
    if not safe:
        safe = "run"
    if len(safe) > max_len:
        safe = safe[:max_len].rstrip("._-")
    return safe or "run"


def _sha1_bytes(data: bytes) -> str:
    h = hashlib.sha1()
    h.update(data)
    return h.hexdigest()


def file_sha1(path: Path) -> Optional[str]:
    """Return sha1 hex digest of a file, or None if it doesn't exist."""
    try:
        if not path.exists() or not path.is_file():
            return None
        return _sha1_bytes(path.read_bytes())
    except OSError:
        return None


def combined_files_sha1(paths: Sequence[Path]) -> str:
    """
    Compute a stable hash over a list of files (by file contents only).
    Missing files are ignored.
    """
    h = hashlib.sha1()
    for p in paths:
        try:
            if p.exists() and p.is_file():
                h.update(p.read_bytes())
                # Add a separator to avoid accidental concatenation ambiguity.
                h.update(b"\n--FILE_BOUNDARY--\n")
        except OSError:
            continue
    return h.hexdigest()


def get_swaps_container_dir(graphs_root: Path) -> Path:
    """Base directory that contains all swap runs for a graphs_root."""
    return graphs_root / "_swaps"


def get_swaps_runs_dir(graphs_root: Path) -> Path:
    """Directory containing all run subdirectories."""
    return get_swaps_container_dir(graphs_root) / RUNS_DIRNAME


def get_run_dir(graphs_root: Path, run_id: str) -> Path:
    """Directory for a specific run."""
    return get_swaps_runs_dir(graphs_root) / run_id


def resolve_swap_config_paths(
    swap_config_path: str,
    loaded_config: Dict[str, Any],
    *,
    script_dir: Optional[Path] = None,
) -> Tuple[Optional[Path], Optional[Path]]:
    """
    Resolve the swap config file and (optional) source config file on disk.

    Returns:
        (swap_cfg_path, source_cfg_path) as absolute Paths where possible.
    """
    cfg_path = Path(swap_config_path)
    if not cfg_path.exists() and script_dir is not None:
        candidate = script_dir / swap_config_path
        if candidate.exists():
            cfg_path = candidate
    cfg_path = cfg_path.resolve() if cfg_path.exists() else None

    source_cfg_path = None
    source_rel = (loaded_config.get("inputs") or {}).get("source_config")
    if source_rel and cfg_path is not None:
        cfg_dir = cfg_path.parent
        candidate = cfg_dir / str(source_rel)
        if candidate.exists():
            source_cfg_path = candidate.resolve()
        else:
            p2 = Path(str(source_rel))
            if p2.exists():
                source_cfg_path = p2.resolve()

    return cfg_path, source_cfg_path


def default_run_id(
    *,
    experiment_name: str,
    cfg_hash_short: str,
    ct_steering: Dict[str, Any],
) -> str:
    """
    Create a human-readable run_id that still stays reasonably short.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    exp = sanitize_run_id(experiment_name or "swap")

    mab = ct_steering.get("M_ablate", None)
    mam = ct_steering.get("M_amplify", None)
    seed = ct_steering.get("seed", None)

    parts = [ts, exp]
    if mab is not None:
        parts.append(f"mab{mab}")
    if mam is not None:
        parts.append(f"mam{mam}")
    if seed is not None:
        parts.append(f"seed{seed}")
    parts.append(f"cfg-{cfg_hash_short}")

    return sanitize_run_id("_".join(str(p) for p in parts))


def _run_git_cmd(args: Sequence[str], *, cwd: Path) -> Optional[str]:
    try:
        out = subprocess.check_output(
            ["git", *args],
            cwd=str(cwd),
            stderr=subprocess.DEVNULL,
        )
        return out.decode(errors="replace").strip()
    except Exception:
        return None


def get_git_metadata() -> Dict[str, Any]:
    """
    Best-effort git metadata for traceability.
    """
    commit = _run_git_cmd(["rev-parse", "HEAD"], cwd=REPO_ROOT)
    branch = _run_git_cmd(["rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO_ROOT)
    dirty = _run_git_cmd(["status", "--porcelain"], cwd=REPO_ROOT)
    return {
        "commit": commit or "unknown",
        "branch": branch or "unknown",
        "dirty": bool(dirty.strip()) if dirty is not None else None,
    }


def write_text_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def write_json_file(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def setup_swap_run_dir(
    *,
    graphs_root: Path,
    loaded_config: Dict[str, Any],
    swap_config_path: str,
    run_id: Optional[str],
    script_dir: Optional[Path] = None,
    create_dirs: bool = True,
) -> Tuple[str, Path, Dict[str, Any]]:
    """
    Create (or reuse) a run directory and return run metadata.

    Returns:
        (run_id, run_dir, meta)
    """
    swaps_container = get_swaps_container_dir(graphs_root)
    runs_dir = get_swaps_runs_dir(graphs_root)
    if create_dirs:
        runs_dir.mkdir(parents=True, exist_ok=True)

    swap_cfg_path, source_cfg_path = resolve_swap_config_paths(
        swap_config_path, loaded_config, script_dir=script_dir
    )
    cfg_hash = combined_files_sha1([p for p in [swap_cfg_path, source_cfg_path] if p is not None])
    cfg_hash_short = cfg_hash[:10]

    ct_cfg = loaded_config.get("ct_steering") or {}
    exp_name = loaded_config.get("experiment_name", "swap")

    if run_id:
        rid = sanitize_run_id(run_id)
    else:
        rid = default_run_id(
            experiment_name=str(exp_name),
            cfg_hash_short=cfg_hash_short,
            ct_steering=ct_cfg,
        )
        # Ensure uniqueness if auto-generated collides (rare but possible).
        candidate = runs_dir / rid
        if candidate.exists():
            suffix = 2
            while True:
                rid2 = sanitize_run_id(f"{rid}_v{suffix}")
                candidate2 = runs_dir / rid2
                if not candidate2.exists():
                    rid = rid2
                    break
                suffix += 1

    run_dir = get_run_dir(graphs_root, rid)
    if create_dirs:
        run_dir.mkdir(parents=True, exist_ok=True)

    meta: Dict[str, Any] = {
        "run_id": rid,
        "run_dir": str(run_dir),
        "graphs_root": str(graphs_root),
        "swaps_container_dir": str(swaps_container),
        "swap_config_path": str(swap_cfg_path) if swap_cfg_path else swap_config_path,
        "source_config_path": str(source_cfg_path) if source_cfg_path else None,
        "config_sha1": cfg_hash,
        "config_sha1_short": cfg_hash_short,
        "file_sha1": {
            "swap_config": file_sha1(swap_cfg_path) if swap_cfg_path else None,
            "source_config": file_sha1(source_cfg_path) if source_cfg_path else None,
        },
    }

    return rid, run_dir, meta


def write_run_artifacts(
    *,
    run_dir: Path,
    run_meta: Dict[str, Any],
    loaded_config: Dict[str, Any],
    argv: Sequence[str],
    status: str,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Write run manifest and top-level tracking files.
    """
    swaps_container = Path(run_meta["swaps_container_dir"])
    existing_display_demo = False
    existing_manifest_path = run_dir / "run_manifest.json"
    if existing_manifest_path.exists():
        try:
            with open(existing_manifest_path, "r", encoding="utf-8") as fh:
                existing_manifest = json.load(fh)
            existing_display_demo = bool(existing_manifest.get("display_demo", False))
        except (json.JSONDecodeError, OSError):
            existing_display_demo = False

    manifest = {
        "run_id": run_meta["run_id"],
        "run_dir": run_meta["run_dir"],
        "display_demo": bool(
            loaded_config.get("display_demo", existing_display_demo)
        ),
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "argv": list(argv),
        "git": get_git_metadata(),
        "platform": {
            "python": sys.version.split()[0],
            "os": os.name,
            "platform": sys.platform,
        },
        "config": {
            "experiment_name": loaded_config.get("experiment_name"),
            "swap": loaded_config.get("swap", {}),
            "ct_steering": loaded_config.get("ct_steering", {}),
            "compute": loaded_config.get("compute", {}),
            "inputs": loaded_config.get("inputs", {}),
        },
        "hashes": {
            "combined_config_sha1": run_meta.get("config_sha1"),
            "files": run_meta.get("file_sha1"),
        },
    }
    if extra:
        manifest.update(extra)

    # Run-local manifest
    write_json_file(run_dir / "run_manifest.json", manifest)

    # Resolved full config snapshot (useful for provenance)
    try:
        write_json_file(run_dir / "config_resolved.json", loaded_config)
    except TypeError:
        # Some configs may contain non-JSON-serializable values; skip gracefully.
        pass

    # Container-level pointers/index (best-effort)
    try:
        write_text_file(swaps_container / LATEST_RUN_FILENAME, str(run_meta["run_id"]))
        append_jsonl(
            swaps_container / RUN_INDEX_FILENAME,
            {
                "timestamp": manifest["timestamp"],
                "run_id": run_meta["run_id"],
                "run_dir": run_meta["run_dir"],
                "experiment_name": loaded_config.get("experiment_name"),
                "config_sha1_short": run_meta.get("config_sha1_short"),
                "git": manifest.get("git"),
            },
        )
    except OSError:
        # Non-fatal (permissions, concurrent edits, etc.)
        pass


