"""
Data loader for swap experiment results (domain-agnostic).

Reads from output/<domain>_batch/ directory structure:
- _swaps/runs/{run_id}/by_source/*/to_*.json - Swap details (run-specific)
- _swaps/runs/{run_id}/config_resolved.json  - Domain & model metadata
- _swaps/_analysis_v3/*.json                 - Analysis data
- */manifest.json                            - Neuronpedia URLs

Supports multiple experiment runs and auto-detects domain fields
(e.g. state/capital, character/author) from config_resolved.json.

Multi-dataset discovery:
    DemoRegistry scans output/* for run_manifest.json files that carry
    "display_demo": true and groups them by dataset (graphs_root).  The
    demo can then switch both dataset and run without restarting the server.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import os
import json
import csv
import re
from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


# ---------------------------------------------------------------------------
# Control variant helpers
# ---------------------------------------------------------------------------

_VARIANT_SUFFIX_RE = re.compile(r"__(?:r\d+|add_.+|ctrl_.+|m_tuned)$")


# ---------------------------------------------------------------------------
# Logit-shift regime classification (Section 4.4 of METHODOLOGY_REPORT.md)
# ---------------------------------------------------------------------------

_REGIME_FLAT_THRESHOLD = 1.0  # |delta| below this is considered FLAT

_REGIME_INFO = {
    "A": {"label": "Clean Redirection", "short": "A"},
    "B": {"label": "Both Boosted", "short": "B"},
    "C": {"label": "Differential Disruption", "short": "C"},
    "D": {"label": "Generic Disruption", "short": "D"},
    "E": {"label": "Pure Suppression", "short": "E"},
}


def _classify_regime(pos0: Dict[str, Any]) -> Optional[str]:
    """Classify a swap into a logit-shift regime from position-0 comparison.

    Returns one of A/B/C/D/E or None if classification is impossible.
    """
    if not pos0:
        return None
    tgt = pos0.get("target_logit_delta")
    src = pos0.get("source_logit_delta")
    flip = pos0.get("flip_at_0", False)

    if tgt is None or src is None:
        return None

    tgt_up = tgt > _REGIME_FLAT_THRESHOLD
    tgt_down = tgt < -_REGIME_FLAT_THRESHOLD
    src_down = src < -_REGIME_FLAT_THRESHOLD
    src_up = src > _REGIME_FLAT_THRESHOLD

    if tgt_up and src_down and flip:
        return "A"
    if tgt_up and src_up:
        return "B"
    if tgt_down and src_down and flip:
        return "C"
    if tgt_down and src_down and not flip:
        return "D"
    if not tgt_up and not tgt_down and src_down and flip:
        return "E"
    return None


def _parse_to_slug(filename_stem: str) -> tuple:
    """
    Extract ``(entity_slug, variant_suffix)`` from a swap result filename stem.

    Normal files:  ``to_georgia_savannah``              -> ``("georgia_savannah", "")``
    Variant files: ``to_georgia_savannah__r0``           -> ``("georgia_savannah", "r0")``
                   ``to_georgia_savannah__add_source``   -> ``("georgia_savannah", "add_source")``
    Double suffix: ``to_buzz__add_sound__m_tuned``       -> ``("buzz", "add_sound__m_tuned")``
    """
    raw = filename_stem.replace("to_", "", 1)
    # Handle double suffix: strip __m_tuned, parse the inner variant, re-append
    m_tuned_tail = ""
    if raw.endswith("__m_tuned") and "__add_" in raw:
        m_tuned_tail = "__m_tuned"
        raw = raw[: -len("__m_tuned")]
    m = _VARIANT_SUFFIX_RE.search(raw)
    if m:
        return raw[: m.start()], raw[m.start() + 2 :] + m_tuned_tail
    return raw, ""


def _is_control_variant(filename_stem: str) -> bool:
    """Return True if the filename contains a control variant suffix."""
    return bool(_VARIANT_SUFFIX_RE.search(filename_stem.replace("to_", "", 1)))


# ---------------------------------------------------------------------------
# Run metadata helpers
# ---------------------------------------------------------------------------

_CONTROL_MODE_LABELS = {
    "labeled": "Labeled",
    "random_feature_matched": "Random x3",
    "additivity": "Field Additivity",
    "m_tuned": "Adaptive M",
}

# Run-id / experiment_name substrings that hide a run from the demo
# selector. These are calibration sweeps or "labeled" control runs that
# would otherwise dominate the dropdown without adding signal for the
# end user. The cross-run-best aggregator applies the exact same filter
# so "Best across runs" is restricted to runs the user can inspect.
_RUN_BLACKLIST_SUBSTRINGS = (
    "sweep_",         # m-sweep calibration runs
    "entropy_study",  # entropy calibration runs
    "highm_",         # high-M ablations
    "_labeled",       # *_labeled control replicas (kept on disk for analysis)
)


def _is_dropdown_run(run_id: str, manifest: Dict[str, Any]) -> bool:
    """Return True if a run should appear in the demo run-selector.

    The aim is to keep only the three "headline" run families:
    - Random x3        (control_mode == random_feature_matched)
    - Field Additivity (control_mode == additivity)
    - Classic / canonical swap runs (everything else not blacklisted)
    """
    rid = run_id.lower()
    exp_name = (
        manifest.get("config", {}).get("experiment_name", "") or ""
    ).lower()
    for blocked in _RUN_BLACKLIST_SUBSTRINGS:
        if blocked in rid or blocked in exp_name:
            return False
    return True


def _extract_control_mode(manifest: Dict[str, Any], run_dir: Optional[Path] = None) -> str:
    """Return the control mode from run metadata.

    Checks the manifest config first, then falls back to
    ``config_resolved.json`` on disk (which contains the full YAML config).
    """
    mode = manifest.get("config", {}).get("control", {}).get("mode", "")
    if mode:
        return mode

    if run_dir is not None:
        resolved_path = run_dir / "config_resolved.json"
        if resolved_path.exists():
            try:
                with open(resolved_path, "r", encoding="utf-8") as fh:
                    resolved = json.load(fh)
                mode = resolved.get("control", {}).get("mode", "")
                if mode:
                    return mode
            except (json.JSONDecodeError, IOError):
                pass

    return "labeled"


def _semantic_run_label(
    run_id: str, manifest: Dict[str, Any], run_dir: Optional[Path] = None,
) -> str:
    """Build a concise, human-readable label that distinguishes control modes."""
    mode = _extract_control_mode(manifest, run_dir=run_dir)
    mode_label = _CONTROL_MODE_LABELS.get(mode, mode.replace("_", " ").title())

    exp_name = manifest.get("config", {}).get("experiment_name", "")
    if exp_name.startswith("fullscale_"):
        return mode_label

    if exp_name:
        pretty = exp_name.replace("_", " ").title()
        pretty = pretty.replace("50states", "50 States").replace("6states", "6 States")
        return pretty

    pretty = run_id.replace("_", " ").title()
    pretty = pretty.replace("50states", "50 States").replace("6states", "6 States")
    pretty = pretty.replace("Gpu", "GPU")
    return pretty


def _is_subpath(child: Path, parent: Path) -> bool:
    """Return True if *child* is equal to or nested under *parent*."""
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# DemoRegistry  -- multi-dataset discovery
# ---------------------------------------------------------------------------

class DemoRegistry:
    """Scan an output root for demo-enabled runs and manage the active dataset.

    Discovery rules:
    - Walk output_root/*/_swaps/runs/*/run_manifest.json
    - Keep only manifests where display_demo == True
    - Derive dataset_dir from manifest["config"]["inputs"]["graphs_root"]
      falling back to the grandparent of the run dir (_swaps/runs/<id> -> dataset)
    - Group runs by resolved dataset_dir (normalised to an absolute Path)

    The active dataset+run is exposed through ``active_loader``.
    """

    DEFAULT_DATASET_ID = "usa_states_batch"
    # Default run for the homepage: the field-additivity sweep on USA
    # states (paper's main result, drives the 73% T5 / 83% T3+ headline
    # numbers). Falls through to ``_pick_default_run``'s fallback chain
    # for other datasets that don't ship this exact run id.
    DEFAULT_RUN_ID = "fullscale_usa_field_add"

    def __init__(self, output_root: Path, initial_data_dir: Optional[Path] = None):
        self.output_root = Path(output_root)
        # {dataset_id: {"dir": Path, "label": str, "runs": [run_dict, ...]}}
        self._datasets: Dict[str, Dict[str, Any]] = {}
        self._active_dataset_id: Optional[str] = None
        self.active_loader: Optional["DataLoader"] = None
        self._best_aggregator = None  # lazy init after scan
        # Cached entity-slug intersection per dataset. A slug only stays
        # if every dropdown-visible run has a ``by_source/<slug>/`` dir
        # with at least one ``to_*.json`` swap. Used to propagate manual
        # entity deletions (e.g. flawed targets) across all runs.
        self._allowed_slugs_cache: Dict[str, Set[str]] = {}

        self._scan()

        if self._datasets:
            # If a specific data_dir was given, prefer the dataset that matches it
            preferred_id = self._resolve_preferred_dataset_id(initial_data_dir)
            self._activate_dataset(preferred_id)

    def _resolve_preferred_dataset_id(self, initial_data_dir: Optional[Path]) -> str:
        """Pick a deterministic default dataset for the demo."""
        if initial_data_dir is not None:
            initial_data_dir = Path(initial_data_dir).resolve()
            for ds_id, ds in self._datasets.items():
                if ds["dir"].resolve() == initial_data_dir:
                    return ds_id

        env_dataset_id = (os.environ.get("DEMO_DEFAULT_DATASET") or "").strip()
        if env_dataset_id and env_dataset_id in self._datasets:
            return env_dataset_id

        if self.DEFAULT_DATASET_ID in self._datasets:
            return self.DEFAULT_DATASET_ID

        # Fall back to the first dataset after label sort.
        return next(iter(self._datasets))

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def _scan(self) -> None:
        """Walk output_root looking for demo-enabled run_manifest.json files."""
        if not self.output_root.exists():
            return

        datasets: Dict[Path, Dict[str, Any]] = {}

        for manifest_path in sorted(
            self.output_root.glob("*/_swaps/runs/*/run_manifest.json"),
            reverse=True,
        ):
            try:
                with open(manifest_path, "r", encoding="utf-8") as fh:
                    manifest = json.load(fh)
            except (json.JSONDecodeError, IOError):
                continue

            if not manifest.get("display_demo"):
                continue

            # Resolve dataset dir: prefer the explicit graphs_root in config
            graphs_root_raw = (
                manifest.get("config", {})
                .get("inputs", {})
                .get("graphs_root", "")
            )
            dataset_dir = None
            if graphs_root_raw:
                candidate = Path(graphs_root_raw)
                if not candidate.is_absolute():
                    candidate = self.output_root.parent / candidate
                resolved_root = self.output_root.resolve()
                if candidate.exists() and _is_subpath(candidate.resolve(), resolved_root):
                    dataset_dir = candidate

            if dataset_dir is None:
                # Physical fallback: output/<ds>/_swaps/runs/<run_id>/run_manifest.json
                dataset_dir = manifest_path.parent.parent.parent.parent

            dataset_dir = dataset_dir.resolve()

            if dataset_dir not in datasets:
                label = self._derive_dataset_label(dataset_dir.name)
                datasets[dataset_dir] = {
                    "dir": dataset_dir,
                    "label": label,
                    "runs": [],
                }

            run_id = manifest_path.parent.name
            swap_count = sum(
                1 for _ in (manifest_path.parent / "by_source").glob("*/to_*.json")
            ) if (manifest_path.parent / "by_source").exists() else 0

            run_dir = manifest_path.parent
            datasets[dataset_dir]["runs"].append({
                "id": run_id,
                "manifest": manifest,
                "swap_count": swap_count,
                "control_mode": _extract_control_mode(manifest, run_dir=run_dir),
                "semantic_label": _semantic_run_label(run_id, manifest, run_dir=run_dir),
            })

        # Build ordered dict: datasets sorted by label, runs already reverse-sorted
        for dataset_dir, ds in sorted(datasets.items(), key=lambda x: x[1]["label"]):
            ds_id = dataset_dir.name
            self._datasets[ds_id] = ds

    @staticmethod
    def _derive_dataset_label(folder_name: str) -> str:
        """Turn 'book_characters_authors_batch' -> 'Book Characters Authors'."""
        name = folder_name.replace("_batch", "").replace("_", " ").title()
        return name

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_datasets(self) -> List[Dict[str, Any]]:
        """Return summary list of all demo datasets."""
        result = []
        for ds_id, ds in self._datasets.items():
            result.append({
                "id": ds_id,
                "label": ds["label"],
                "run_count": len(ds["runs"]),
                "is_active": ds_id == self._active_dataset_id,
            })
        return result

    def list_runs_for_dataset(self, dataset_id: str) -> List[Dict[str, Any]]:
        """Return run summaries for a specific dataset (filtered for the UI)."""
        ds = self._datasets.get(dataset_id)
        if not ds:
            return []
        result = []
        for r in ds["runs"]:
            manifest = r["manifest"]
            if not _is_dropdown_run(r["id"], manifest):
                continue
            result.append({
                "id": r["id"],
                "dataset_id": dataset_id,
                "dataset_label": ds["label"],
                "name": self._format_run_name(r["id"]),
                "semantic_label": r.get("semantic_label", ""),
                "control_mode": r.get("control_mode", "labeled"),
                "swap_count": r["swap_count"],
                "status": manifest.get("status", "unknown"),
                "timestamp": manifest.get("timestamp_started", manifest.get("timestamp", "")),
                "has_trajectory": (
                    (ds["dir"] / "_swaps" / "runs" / r["id"] / "_trajectory_analysis").exists()
                ),
            })
        return result

    def list_all_runs(self) -> List[Dict[str, Any]]:
        """Return all demo-enabled runs across all datasets, grouped by dataset."""
        all_runs = []
        for ds_id in self._datasets:
            all_runs.extend(self.list_runs_for_dataset(ds_id))
        return all_runs

    def set_dataset(self, dataset_id: str) -> bool:
        """Switch the active dataset (picks its best run automatically)."""
        if dataset_id not in self._datasets:
            return False
        self._activate_dataset(dataset_id)
        return True

    def set_run(self, run_id: str) -> bool:
        """Switch run within the current dataset."""
        if self.active_loader is None:
            return False
        return self.active_loader.set_run(run_id)

    def set_run_global(self, run_id: str) -> bool:
        """Switch to any run across all datasets.

        Finds which dataset owns the run, activates that dataset, then
        selects the specific run.
        """
        for ds_id, ds in self._datasets.items():
            for r in ds["runs"]:
                if r["id"] == run_id:
                    if ds_id != self._active_dataset_id:
                        self._activate_dataset(ds_id)
                    self.active_loader.set_run(run_id)
                    return True
        return False

    @property
    def active_dataset_id(self) -> Optional[str]:
        return self._active_dataset_id

    @property
    def best_aggregator(self):
        """Lazy-init cross-run best aggregator."""
        if self._best_aggregator is None:
            from .cross_run_best import CrossRunBestAggregator
            self._best_aggregator = CrossRunBestAggregator(self)
        return self._best_aggregator

    def get_best_cross_run_matrix(self) -> Dict[str, Any]:
        """Return best-per-cell matrix + winners for the active dataset."""
        if not self._active_dataset_id:
            return {"matrix": {}, "winners": {}, "considered_runs": []}
        return self.best_aggregator.get_best_matrix(self._active_dataset_id)

    def get_allowed_slugs(self, dataset_id: str) -> Optional[Set[str]]:
        """Return the entity-slug intersection across visible runs.

        A slug is "allowed" only if every dropdown-visible run for the
        dataset has a non-empty ``by_source/<slug>/`` directory. This
        propagates manual entity deletions in any one run to all the
        others (the user removes flawed targets in Field Additivity and
        the Classic Swap matrix automatically hides the same rows /
        columns).

        Returns ``None`` when the dataset is unknown or has no visible
        runs (so the caller should fall back to no filtering).
        """
        if dataset_id in self._allowed_slugs_cache:
            return self._allowed_slugs_cache[dataset_id]

        ds = self._datasets.get(dataset_id)
        if not ds:
            return None

        visible_runs = [
            r for r in ds["runs"]
            if _is_dropdown_run(r["id"], r.get("manifest", {}))
        ]
        if not visible_runs:
            return None

        per_run_slugs: List[Set[str]] = []
        for r in visible_runs:
            run_dir = ds["dir"] / "_swaps" / "runs" / r["id"]
            slugs = self._collect_run_slugs(run_dir)
            if slugs:
                per_run_slugs.append(slugs)

        if not per_run_slugs:
            return None

        allowed = set.intersection(*per_run_slugs)
        self._allowed_slugs_cache[dataset_id] = allowed
        return allowed

    @staticmethod
    def _collect_run_slugs(run_dir: Path) -> Set[str]:
        """Return the set of entity slugs that have at least one swap file
        in ``run_dir/by_source/<slug>/to_*.json`` (canonical or variant).

        An empty source folder (because every ``to_*.json`` was deleted)
        is treated as "entity removed" and excluded.
        """
        by_source = run_dir / "by_source"
        if not by_source.exists():
            return set()
        slugs: Set[str] = set()
        for source_dir in by_source.iterdir():
            if not source_dir.is_dir():
                continue
            if any(source_dir.glob("to_*.json")):
                slugs.add(source_dir.name)
        return slugs

    def get_swap_detail_for_run(
        self, run_id: str, from_slug: str, to_slug: str,
        variant: Optional[str] = None,
    ) -> Optional[Dict]:
        """Load a swap detail from a specific run (for cross-run best mode)."""
        for ds in self._datasets.values():
            for r in ds["runs"]:
                if r["id"] == run_id:
                    loader = DataLoader(ds["dir"], run_id=run_id)
                    return loader.get_swap_detail(
                        from_slug, to_slug, variant=variant
                    )
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _activate_dataset(self, dataset_id: str) -> None:
        ds = self._datasets[dataset_id]
        best_run_id = self._pick_default_run(ds["runs"])
        allowed = self.get_allowed_slugs(dataset_id)
        self.active_loader = DataLoader(
            ds["dir"], run_id=best_run_id, allowed_slugs=allowed,
        )
        self._active_dataset_id = dataset_id

    @classmethod
    def _pick_default_run(cls, runs: List[Dict[str, Any]]) -> Optional[str]:
        """Choose the default run for a dataset.

        Priority:
        1. ``DEMO_DEFAULT_RUN`` env var (exact run id match)
        2. Class constant ``DEFAULT_RUN_ID``
        3. Largest "classic" swap run that's visible in the dropdown
        4. Largest visible run regardless of mode
        5. First run in list (newest)
        """
        if not runs:
            return None

        env_run = (os.environ.get("DEMO_DEFAULT_RUN") or "").strip()
        if env_run:
            for r in runs:
                if r["id"] == env_run:
                    return r["id"]

        if cls.DEFAULT_RUN_ID:
            for r in runs:
                if r["id"] == cls.DEFAULT_RUN_ID:
                    return r["id"]

        visible = [
            r for r in runs
            if _is_dropdown_run(r["id"], r.get("manifest", {}))
        ]
        if visible:
            classic = [
                r for r in visible
                if r.get("control_mode") not in ("random_feature_matched", "additivity")
            ]
            pool = classic or visible
            return max(pool, key=lambda r: r.get("swap_count", 0))["id"]

        return runs[0]["id"]

    @staticmethod
    def _format_run_name(run_id: str) -> str:
        name = run_id.replace("_", " ").title()
        name = name.replace("50states", "50 States").replace("6states", "6 States")
        return name


class DataLoader:
    """Load and cache swap experiment data with multi-run support."""
    
    def __init__(
        self,
        data_dir: Path,
        run_id: Optional[str] = None,
        allowed_slugs: Optional[Set[str]] = None,
    ):
        """Initialise a loader for one dataset directory.

        ``allowed_slugs`` is an optional whitelist of entity slugs. When
        provided, every public matrix / state getter prunes its output
        to only those slugs. This is how cross-run entity deletions
        propagate: ``DemoRegistry`` computes the intersection of slugs
        across all visible runs and forwards it here.
        """
        self.data_dir = Path(data_dir)
        self.base_swaps_dir = self.data_dir / "_swaps"
        self.run_id = run_id
        self.allowed_slugs: Optional[Set[str]] = (
            set(allowed_slugs) if allowed_slugs is not None else None
        )
        self._set_swaps_dir()
        self._matrix_cache: Dict[Optional[str], Dict] = {}
        self._flip_matrix_cache: Dict[Optional[str], Dict] = {}
        self._regime_matrix_cache: Dict[Optional[str], Dict] = {}
        self._vsmax_matrix_cache: Dict[Optional[str], Dict] = {}
        self._variant_index_cache: Optional[Dict] = None
        self._states_cache: Optional[List[Dict]] = None
        self._analysis_cache: Optional[Dict] = None
        self._stats_cache: Optional[Dict] = None
        self._domain_config_cache: Optional[Dict] = None
        self._gpu_batch_features_index: Optional[Dict[str, List]] = None
    
    def _set_swaps_dir(self):
        """Set swaps_dir based on current run_id."""
        if self.run_id:
            run_dir = self.base_swaps_dir / "runs" / self.run_id
            if run_dir.exists():
                self.swaps_dir = run_dir
            else:
                # Fallback to base swaps dir
                self.swaps_dir = self.base_swaps_dir
        else:
            # Check if runs directory exists and has runs
            runs_dir = self.base_swaps_dir / "runs"
            if runs_dir.exists():
                # Prefer the full 50-state run on a fresh load.
                default_run_id = self._get_default_run_id()
                if default_run_id:
                    self.run_id = default_run_id
                    self.swaps_dir = self.base_swaps_dir / "runs" / default_run_id
                else:
                    self.swaps_dir = self.base_swaps_dir
            else:
                self.swaps_dir = self.base_swaps_dir

    def _get_default_run_id(self) -> Optional[str]:
        """Choose the default run for a fresh app load (most recent non-legacy).

        ``list_runs`` already filters out sweeps and ``*_labeled`` controls,
        so we only need to drop legacy runs here.
        """
        runs = self.list_runs()
        if not runs:
            return None

        for run in runs:
            if "legacy" not in run["id"].lower():
                return run["id"]

        return runs[0]["id"]
    
    def list_runs(self) -> List[Dict[str, Any]]:
        """List available experiment runs."""
        runs = []
        runs_dir = self.base_swaps_dir / "runs"
        
        if not runs_dir.exists():
            return runs
        
        for run_dir in sorted(runs_dir.iterdir(), reverse=True):
            if not run_dir.is_dir():
                continue
            
            by_source = run_dir / "by_source"
            if not by_source.exists():
                continue
            
            # Load run manifest for metadata
            manifest_path = run_dir / "run_manifest.json"
            manifest = {}
            if manifest_path.exists():
                try:
                    with open(manifest_path, 'r', encoding='utf-8') as f:
                        manifest = json.load(f)
                except (json.JSONDecodeError, IOError):
                    pass
            
            if not _is_dropdown_run(run_dir.name, manifest):
                continue

            # Count swaps
            swap_count = sum(1 for _ in by_source.glob("*/to_*.json"))
            
            # Check for trajectory data
            has_trajectory = (run_dir / "_trajectory_analysis").exists()
            
            # Get config info
            config = manifest.get('config', {})
            ct_config = config.get('ct_steering', {})
            
            runs.append({
                'id': run_dir.name,
                'name': self._format_run_name(run_dir.name),
                'semantic_label': _semantic_run_label(run_dir.name, manifest, run_dir=run_dir),
                'control_mode': _extract_control_mode(manifest, run_dir=run_dir),
                'swap_count': swap_count,
                'has_trajectory': has_trajectory,
                'timestamp': manifest.get('timestamp_started', ''),
                'status': manifest.get('status', 'unknown'),
                'M_ablate': ct_config.get('M_ablate', -2),
                'M_amplify': ct_config.get('M_amplify', 20),
                'is_current': run_dir.name == self.run_id,
            })
        
        return runs
    
    def _format_run_name(self, run_id: str) -> str:
        """Format run ID into human-readable name."""
        # full_50states_v1 -> "Full 50 States v1"
        # pilot_6states_v1 -> "Pilot 6 States v1"
        # gpu_test_8 -> "GPU Test 8"
        name = run_id.replace('_', ' ').title()
        name = name.replace('50states', '50 States')
        name = name.replace('6states', '6 States')
        name = name.replace('Gpu', 'GPU')
        return name
    
    def set_run(self, run_id: str) -> bool:
        """Switch to a different run."""
        run_dir = self.base_swaps_dir / "runs" / run_id
        if not run_dir.exists():
            return False
        
        self.run_id = run_id
        self._set_swaps_dir()
        self._clear_caches()
        return True
    
    def get_current_run(self) -> Optional[str]:
        """Get the current run ID."""
        return self.run_id
    
    def _clear_caches(self):
        """Clear all cached data."""
        self._matrix_cache = {}
        self._flip_matrix_cache = {}
        self._regime_matrix_cache = {}
        self._vsmax_matrix_cache = {}
        self._variant_index_cache = None
        self._states_cache = None
        self._analysis_cache = None
        self._stats_cache = None
        self._domain_config_cache = None
        self._gpu_batch_features_index = None
        self._methodology_stats = None

    # ------------------------------------------------------------------
    # Cross-run entity filtering
    # ------------------------------------------------------------------

    def _apply_slug_filter(self, matrix: Dict[str, Dict]) -> Dict[str, Dict]:
        """Return a copy of *matrix* containing only allowed_slugs.

        Filters both the row dimension (sources) and column dimension
        (targets). When ``allowed_slugs`` is None this is a no-op (the
        original dict is returned untouched, since callers don't mutate
        the result).
        """
        if self.allowed_slugs is None:
            return matrix
        allowed = self.allowed_slugs
        filtered: Dict[str, Dict] = {}
        for from_slug, row in matrix.items():
            if from_slug not in allowed:
                continue
            filtered[from_slug] = {
                to_slug: val
                for to_slug, val in row.items()
                if to_slug in allowed
            }
        return filtered
    
    # Per-domain blacklists of common words that should be ignored by the
    # word-boundary tier heuristic (e.g. "city" in "Salt Lake City" would
    # otherwise match generic geography text like "is a city").
    TIER_WORD_BLACKLIST: Dict[str, List[str]] = {
        'usa_states': ['city'],
    }

    # ------------------------------------------------------------------
    # Domain & model configuration (loaded from config_resolved.json)
    # ------------------------------------------------------------------

    def get_domain_config(self) -> Dict[str, Any]:
        """Return domain and model metadata for the active run.

        Reads config_resolved.json once and caches the result.  Falls back to
        USA-states defaults when the file is missing (legacy runs).
        """
        if self._domain_config_cache is not None:
            return self._domain_config_cache

        config = self._load_config_resolved()
        if not config:
            self._domain_config_cache = self._build_fallback_domain_config()
            return self._domain_config_cache

        entities = config.get('_entities', [])
        entity_index = {e['slug']: e for e in entities}

        concept_fields = config.get('swap', {}).get('concept_fields', [])

        entity_fields: List[str] = []
        if entities:
            entity_fields = [k for k in entities[0] if k != 'slug']

        primary_field = entity_fields[0] if entity_fields else 'slug'
        for f in entity_fields:
            if f not in concept_fields:
                primary_field = f
                break

        answer_field = concept_fields[-1] if concept_fields else ''

        ct = config.get('ct_steering', {})
        model_id = ct.get('model_id', '')
        transcoder_set = ct.get('transcoder_set', '')
        np_model = model_id.split('/')[-1] if model_id else 'gemma-2-2b'

        experiment_name = config.get('experiment_name', '')
        is_usa_states = 'usa_states' in experiment_name or 'state' in concept_fields
        display_name = experiment_name.replace('_swap', '').replace('_', ' ').title()

        blacklist: List[str] = []
        for key, words in self.TIER_WORD_BLACKLIST.items():
            if key in experiment_name:
                blacklist = [w.lower() for w in words]
                break

        self._domain_config_cache = {
            'experiment_name': experiment_name,
            'display_name': display_name,
            'concept_fields': concept_fields,
            'answer_field': answer_field,
            'primary_field': primary_field,
            'entity_fields': entity_fields,
            'entity_index': entity_index,
            'entity_count': len(entities),
            'model_id': model_id,
            'transcoder_set': transcoder_set,
            'np_model': np_model,
            'is_usa_states': is_usa_states,
            'tier_word_blacklist': blacklist,
            'm_ablate': ct.get('M_ablate', -2),
            'm_amplify': ct.get('M_amplify', 20),
            'temperature': ct.get('temperature', 0.3),
            'n_tokens': ct.get('n_tokens', 10),
        }
        return self._domain_config_cache

    def _load_config_resolved(self) -> Optional[Dict]:
        """Load config_resolved.json from the active run directory."""
        path = self.swaps_dir / "config_resolved.json"
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return None

    def _build_fallback_domain_config(self) -> Dict[str, Any]:
        """Fallback domain config for legacy runs without config_resolved.json."""
        return {
            'experiment_name': 'usa_states_swap',
            'display_name': 'USA States',
            'concept_fields': ['state', 'capital'],
            'answer_field': 'capital',
            'primary_field': 'city',
            'entity_fields': ['city', 'state', 'capital'],
            'entity_index': {},
            'entity_count': 0,
            'model_id': 'google/gemma-2-2b',
            'transcoder_set': 'mntss/clt-gemma-2-2b-2.5M',
            'np_model': 'gemma-2-2b',
            'is_usa_states': True,
            'tier_word_blacklist': ['city'],
            'm_ablate': -2,
            'm_amplify': 20,
            'temperature': 0.3,
            'n_tokens': 10,
        }

    @staticmethod
    def _slug_to_label(slug: str) -> str:
        """Convert a slug to a human-readable label."""
        return slug.replace('_', ' ').title()

    def _make_abbr(self, slug: str, label: str) -> str:
        """Generate a short abbreviation for matrix headers."""
        dc = self.get_domain_config()
        if dc['is_usa_states']:
            return self._state_to_abbr(label)
        parts = slug.split('_')
        if len(parts) >= 2:
            return ''.join(p[0].upper() for p in parts[:3])
        return slug[:3].upper()

    # ------------------------------------------------------------------
    # Variant index
    # ------------------------------------------------------------------

    def _build_variant_index(self) -> Dict:
        """Group swap files by canonical (from_slug, to_slug) pair.

        Returns ``{from_slug: {to_slug: [record, ...]}}``.
        Each record is::

            {
                "path": Path,
                "variant_suffix": str,  # "" for canonical, "r0" / "add_book" / etc.
                "is_canonical": bool,
            }
        """
        if self._variant_index_cache is not None:
            return self._variant_index_cache

        index: Dict[str, Dict[str, list]] = {}
        by_source_dir = self.swaps_dir / "by_source"
        if not by_source_dir.exists():
            self._variant_index_cache = index
            return index

        for source_dir in by_source_dir.iterdir():
            if not source_dir.is_dir():
                continue
            from_slug = source_dir.name
            if from_slug not in index:
                index[from_slug] = {}

            for swap_file in source_dir.glob("to_*.json"):
                to_slug, variant_suffix = _parse_to_slug(swap_file.stem)
                if not to_slug:
                    continue
                index[from_slug].setdefault(to_slug, []).append({
                    "path": swap_file,
                    "variant_suffix": variant_suffix,
                    "is_canonical": variant_suffix == "",
                })

        self._variant_index_cache = index
        return index

    def get_variants_for_pair(
        self, from_slug: str, to_slug: str
    ) -> List[Dict[str, Any]]:
        """Return lightweight variant descriptors for a single pair.

        Each item includes ``variant_suffix``, ``tier``, ``flip_position``,
        and control metadata extracted from the swap JSON.
        """
        idx = self._build_variant_index()
        records = idx.get(from_slug, {}).get(to_slug, [])
        variants: List[Dict[str, Any]] = []
        for rec in records:
            if rec["is_canonical"]:
                continue
            try:
                with open(rec["path"], "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except (json.JSONDecodeError, IOError):
                continue
            ctrl = data.get("metadata", {}).get("control", {})
            variants.append({
                "variant_suffix": rec["variant_suffix"],
                "tier": self._get_tier_from_swap(data),
                "flip_position": self._get_flip_position_from_swap(data),
                "control_mode": ctrl.get("control_mode", ""),
                "concept_subsets_used": ctrl.get("concept_subsets_used", []),
                "replicate_id": ctrl.get("replicate_id"),
            })
        return variants

    def get_run_variant_suffixes(self) -> List[str]:
        """Return sorted list of distinct variant suffixes across the entire run."""
        idx = self._build_variant_index()
        suffixes: set = set()
        for targets in idx.values():
            for records in targets.values():
                for r in records:
                    if r["variant_suffix"]:
                        suffixes.add(r["variant_suffix"])
        return sorted(suffixes)

    def _best_variant_path(
        self, from_slug: str, to_slug: str
    ) -> Optional[Path]:
        """Return the path of the best variant file for a pair (highest tier)."""
        idx = self._build_variant_index()
        records = idx.get(from_slug, {}).get(to_slug, [])
        variants = [r for r in records if not r["is_canonical"]]
        if not variants:
            return None

        best_path = None
        best_tier = -1
        for rec in variants:
            try:
                with open(rec["path"], "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                tier = self._get_tier_from_swap(data) or 0
                if tier > best_tier:
                    best_tier = tier
                    best_path = rec["path"]
            except (json.JSONDecodeError, IOError):
                continue
        return best_path

    # ------------------------------------------------------------------
    # Matrix
    # ------------------------------------------------------------------

    def get_matrix(self, variant: Optional[str] = None) -> Dict[str, Dict[str, Optional[int]]]:
        """Build tier matrix dynamically from individual swap JSON files.

        When *variant* is None (default), canonical files take priority and
        variant-only pairs aggregate using the best (highest) tier.
        When *variant* is set, only files matching that suffix are used.
        """
        if variant in self._matrix_cache:
            return self._apply_slug_filter(self._matrix_cache[variant])

        idx = self._build_variant_index()
        matrix: Dict[str, Dict[str, Optional[int]]] = {}

        for from_slug, targets in idx.items():
            matrix[from_slug] = {}
            for to_slug, records in targets.items():
                if variant is not None:
                    matched = [r for r in records if r["variant_suffix"] == variant]
                    if matched:
                        try:
                            with open(matched[0]["path"], "r", encoding="utf-8") as f:
                                swap_data = json.load(f)
                            matrix[from_slug][to_slug] = self._get_tier_from_swap(swap_data)
                        except (json.JSONDecodeError, IOError):
                            pass
                    continue

                canonical = [r for r in records if r["is_canonical"]]
                variants = [r for r in records if not r["is_canonical"]]

                if canonical:
                    try:
                        with open(canonical[0]["path"], "r", encoding="utf-8") as f:
                            swap_data = json.load(f)
                        matrix[from_slug][to_slug] = self._get_tier_from_swap(swap_data)
                    except (json.JSONDecodeError, IOError):
                        pass
                elif variants:
                    best_tier: Optional[float] = None
                    for rec in variants:
                        try:
                            with open(rec["path"], "r", encoding="utf-8") as f:
                                swap_data = json.load(f)
                            tier = self._get_tier_from_swap(swap_data)
                            if tier is not None and (best_tier is None or tier > best_tier):
                                best_tier = tier
                        except (json.JSONDecodeError, IOError):
                            continue
                    if best_tier is not None:
                        matrix[from_slug][to_slug] = best_tier

        if variant is None:
            work_dir = self.swaps_dir / "work"
            if work_dir.exists():
                for swap_file in work_dir.glob("*.json"):
                    try:
                        with open(swap_file, "r", encoding="utf-8") as f:
                            swap_data = json.load(f)
                        swap_id = swap_file.stem
                        if "__to__" in swap_id:
                            from_slug, to_slug = swap_id.split("__to__")
                            if from_slug not in matrix:
                                matrix[from_slug] = {}
                            if to_slug not in matrix[from_slug]:
                                matrix[from_slug][to_slug] = self._get_tier_from_swap(swap_data)
                    except (json.JSONDecodeError, IOError):
                        continue

        self._matrix_cache[variant] = matrix
        return self._apply_slug_filter(matrix)
    
    def _get_tier_from_swap(self, swap_data: Dict) -> Optional[float]:
        """Extract tier from swap data, computing if necessary.

        Tier semantics (domain-agnostic):
            5 = PERFECT  -- target answer detected in steered output via any of:
                  a) full answer match (strict or fuzzy punctuation)
                  b) steered first token is a substring of the target answer
                  c) any word (len>=3) of the target answer appears in the
                     steered output (e.g. "Harper" in "Nelle Harper...")
            2 = SUPPRESSED_ONLY -- source gone, no target signal
            1 = SOURCE_PERSISTS -- source answer still in output
        """
        if 'classification' in swap_data:
            tier = swap_data['classification'].get('tier')
            if tier is not None:
                return float(tier)

        evaluation = swap_data.get('evaluation', {})
        exact = evaluation.get('exact_match', {})

        hit = exact.get('steered_has_to_capital') or exact.get('steered_has_to_answer')

        to_answer = evaluation.get('to_answer', '')
        steered_out = evaluation.get('raw', {}).get('steered_output', '')

        if not hit and to_answer and steered_out:
            to_norm = to_answer.replace('.', '').replace('-', ' ').lower()
            out_norm = steered_out.replace('.', '').replace('-', ' ').lower()
            if to_norm and to_norm in out_norm:
                hit = True

        if not hit:
            first_token = evaluation.get('first_token', {})
            steered_first_tok = (first_token.get('steered', '') or '').strip()
            if len(steered_first_tok) >= 2 and to_answer:
                answer_norm = to_answer.replace('.', '').lower()
                tok_norm = steered_first_tok.lower()
                if tok_norm in answer_norm:
                    hit = True

        if not hit and to_answer and steered_out:
            blacklist = set(self.get_domain_config().get('tier_word_blacklist', []))
            out_lower = steered_out.lower()
            for word in to_answer.replace('.', '').split():
                if len(word) >= 3 and word.lower() not in blacklist:
                    pattern = r'\b' + re.escape(word.lower()) + r'\b'
                    if re.search(pattern, out_lower):
                        hit = True
                        break

        if hit:
            return 5

        if not exact.get('from_suppressed'):
            return 1

        return 2
    
    @staticmethod
    def _get_flip_position_from_swap(swap_data: Dict):
        """Extract logit flip position from swap data.

        Returns:
            int >= 0  -- generation position where the flip first occurs
            None      -- trajectory was tracked but flip never occurred
            -1        -- no trajectory data available for this swap
        """
        traj = swap_data.get('evaluation', {}).get('logit_trajectory')
        if traj is None or not isinstance(traj, dict) or 'summary' not in traj:
            return -1
        return traj['summary'].get('flip_position')

    def get_flip_matrix(self, variant: Optional[str] = None) -> Dict[str, Dict[str, Optional[int]]]:
        """Build flip-position matrix from swap JSON files.

        Same structure as ``get_matrix()`` but values are the generation
        position where the logit flip first occurs (0, 1, 2 ...) or
        ``None`` when no flip is observed.

        When *variant* is None, canonical files take priority and variant-only
        pairs pick the earliest non-null flip.  When *variant* is set, only
        files matching that suffix are used.
        """
        if variant in self._flip_matrix_cache:
            return self._apply_slug_filter(self._flip_matrix_cache[variant])

        idx = self._build_variant_index()
        matrix: Dict[str, Dict[str, Optional[int]]] = {}

        for from_slug, targets in idx.items():
            matrix[from_slug] = {}
            for to_slug, records in targets.items():
                if variant is not None:
                    matched = [r for r in records if r["variant_suffix"] == variant]
                    if matched:
                        try:
                            with open(matched[0]["path"], "r", encoding="utf-8") as f:
                                swap_data = json.load(f)
                            matrix[from_slug][to_slug] = self._get_flip_position_from_swap(swap_data)
                        except (json.JSONDecodeError, IOError):
                            pass
                    continue

                canonical = [r for r in records if r["is_canonical"]]
                variants = [r for r in records if not r["is_canonical"]]

                if canonical:
                    try:
                        with open(canonical[0]["path"], "r", encoding="utf-8") as f:
                            swap_data = json.load(f)
                        matrix[from_slug][to_slug] = self._get_flip_position_from_swap(swap_data)
                    except (json.JSONDecodeError, IOError):
                        pass
                elif variants:
                    best_flip = None
                    for rec in variants:
                        try:
                            with open(rec["path"], "r", encoding="utf-8") as f:
                                swap_data = json.load(f)
                            fp = self._get_flip_position_from_swap(swap_data)
                            if fp is not None and fp >= 0:
                                if best_flip is None or fp < best_flip:
                                    best_flip = fp
                        except (json.JSONDecodeError, IOError):
                            continue
                    matrix[from_slug][to_slug] = best_flip

        if variant is None:
            work_dir = self.swaps_dir / "work"
            if work_dir.exists():
                for swap_file in work_dir.glob("*.json"):
                    try:
                        with open(swap_file, "r", encoding="utf-8") as f:
                            swap_data = json.load(f)
                        swap_id = swap_file.stem
                        if "__to__" in swap_id:
                            from_slug, to_slug = swap_id.split("__to__")
                            if from_slug not in matrix:
                                matrix[from_slug] = {}
                            if to_slug not in matrix[from_slug]:
                                matrix[from_slug][to_slug] = self._get_flip_position_from_swap(swap_data)
                    except (json.JSONDecodeError, IOError):
                        continue

        self._flip_matrix_cache[variant] = matrix
        return self._apply_slug_filter(matrix)

    # ------------------------------------------------------------------
    # Regime & VsMax matrices
    # ------------------------------------------------------------------

    @staticmethod
    def _get_regime_from_swap(swap_data: Dict) -> Optional[str]:
        """Extract logit-shift regime (A-E) from swap data."""
        pos0 = swap_data.get('evaluation', {}).get('position_0_comparison', {})
        return _classify_regime(pos0)

    @staticmethod
    def _get_vsmax_from_swap(swap_data: Dict) -> Optional[float]:
        """Extract best-trajectory vsMax from swap data.

        Returns the ``best_target_minus_max`` float or None.
        """
        contrast = (swap_data.get('evaluation', {})
                    .get('logit_trajectory', {})
                    .get('contrast_groups', {}))
        if not isinstance(contrast, dict):
            return None
        grp = contrast.get('same_dataset', {})
        if not isinstance(grp, dict):
            return None
        agg = grp.get('aggregate', {})
        if not isinstance(agg, dict):
            return None
        return agg.get('best_target_minus_max')

    def _build_overlay_matrix(
        self,
        extractor,
        cache: Dict,
        variant: Optional[str],
        best_cmp,
    ) -> Dict[str, Dict]:
        """Generic matrix builder reused by regime and vsmax.

        ``extractor`` pulls a value from swap_data.
        ``best_cmp(current_best, candidate)`` returns True when candidate is
        preferred over current_best (used for variant-only fallback).
        """
        if variant in cache:
            return self._apply_slug_filter(cache[variant])

        idx = self._build_variant_index()
        matrix: Dict[str, Dict] = {}

        for from_slug, targets in idx.items():
            matrix[from_slug] = {}
            for to_slug, records in targets.items():
                if variant is not None:
                    matched = [r for r in records if r["variant_suffix"] == variant]
                    if matched:
                        try:
                            with open(matched[0]["path"], "r", encoding="utf-8") as f:
                                swap_data = json.load(f)
                            matrix[from_slug][to_slug] = extractor(swap_data)
                        except (json.JSONDecodeError, IOError):
                            pass
                    continue

                canonical = [r for r in records if r["is_canonical"]]
                variants_list = [r for r in records if not r["is_canonical"]]

                if canonical:
                    try:
                        with open(canonical[0]["path"], "r", encoding="utf-8") as f:
                            swap_data = json.load(f)
                        matrix[from_slug][to_slug] = extractor(swap_data)
                    except (json.JSONDecodeError, IOError):
                        pass
                elif variants_list:
                    best_val = None
                    for rec in variants_list:
                        try:
                            with open(rec["path"], "r", encoding="utf-8") as f:
                                swap_data = json.load(f)
                            val = extractor(swap_data)
                            if val is not None and (best_val is None or best_cmp(best_val, val)):
                                best_val = val
                        except (json.JSONDecodeError, IOError):
                            continue
                    if best_val is not None:
                        matrix[from_slug][to_slug] = best_val

        if variant is None:
            work_dir = self.swaps_dir / "work"
            if work_dir.exists():
                for swap_file in work_dir.glob("*.json"):
                    try:
                        with open(swap_file, "r", encoding="utf-8") as f:
                            swap_data = json.load(f)
                        swap_id = swap_file.stem
                        if "__to__" in swap_id:
                            from_slug, to_slug = swap_id.split("__to__")
                            if from_slug not in matrix:
                                matrix[from_slug] = {}
                            if to_slug not in matrix[from_slug]:
                                matrix[from_slug][to_slug] = extractor(swap_data)
                    except (json.JSONDecodeError, IOError):
                        continue

        cache[variant] = matrix
        return self._apply_slug_filter(matrix)

    def get_regime_matrix(self, variant: Optional[str] = None) -> Dict[str, Dict[str, Optional[str]]]:
        """Build regime matrix (A-E letters) from swap JSON files."""
        _REGIME_RANK = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1}
        return self._build_overlay_matrix(
            self._get_regime_from_swap,
            self._regime_matrix_cache,
            variant,
            best_cmp=lambda cur, cand: _REGIME_RANK.get(cand, 0) > _REGIME_RANK.get(cur, 0),
        )

    def get_vsmax_matrix(self, variant: Optional[str] = None) -> Dict[str, Dict[str, Optional[float]]]:
        """Build vsMax matrix from swap JSON files.  Higher is better."""
        return self._build_overlay_matrix(
            self._get_vsmax_from_swap,
            self._vsmax_matrix_cache,
            variant,
            best_cmp=lambda cur, cand: cand > cur,
        )

    def get_states(self) -> List[Dict[str, Any]]:
        """Get entity list with metadata from by_source directories.

        Returns a list of dicts with backward-compatible keys (``state``,
        ``capital``, ``city``, ``abbr``) plus generic keys (``label``,
        ``answer``, ``fields``) so that frontends can work with any domain.
        """
        if self._states_cache is not None:
            return self._states_cache

        dc = self.get_domain_config()
        entity_index = dc['entity_index']
        primary_field = dc['primary_field']
        answer_field = dc['answer_field']

        analysis = self.get_analysis()
        archetypes = analysis.get('archetypes', {})

        archetype_lookup: Dict[str, Dict] = {}
        for archetype, entity_list in archetypes.items():
            for ed in entity_list:
                key = ed.get('state', ed.get(primary_field, ''))
                archetype_lookup[key] = {
                    'archetype': archetype,
                    'native_prob': ed.get('native_prob', 0),
                    'supernodes': ed.get('supernodes', 0),
                    'src_tier': ed.get('src_tier', 0),
                    'tgt_tier': ed.get('tgt_tier', 0),
                }

        entities: List[Dict[str, Any]] = []
        by_source_dir = self.swaps_dir / "by_source"
        if by_source_dir.exists():
            for source_dir in sorted(by_source_dir.iterdir()):
                if not source_dir.is_dir():
                    continue

                slug = source_dir.name
                if self.allowed_slugs is not None and slug not in self.allowed_slugs:
                    continue
                edata = entity_index.get(slug, {})
                if not edata:
                    edata = self._get_entity_info_from_swap(source_dir)

                label = (edata.get(primary_field, '')
                         or self._slug_to_label(slug))
                answer = edata.get(answer_field, '')
                abbr = self._make_abbr(slug, edata.get('state', label))

                # Backward-compatible keys
                state_val = edata.get('state', label)
                capital_val = edata.get('capital', answer)
                city_val = edata.get('city',
                                     edata.get(primary_field, label))

                arch_key = state_val if dc['is_usa_states'] else label
                arch_data = archetype_lookup.get(arch_key, {})

                neuronpedia_url = self._get_neuronpedia_url(slug)
                logit_flags = (self._get_entity_logit_flags(slug, answer)
                               if self._find_state_dir(slug) else {})

                entities.append({
                    'slug': slug,
                    'label': label,
                    'answer': answer,
                    'state': state_val,
                    'capital': capital_val,
                    'city': city_val,
                    'abbr': abbr,
                    'archetype': arch_data.get('archetype', 'Unknown'),
                    'native_prob': arch_data.get('native_prob', 0),
                    'supernodes': arch_data.get('supernodes', 0),
                    'src_tier': arch_data.get('src_tier', 0),
                    'tgt_tier': arch_data.get('tgt_tier', 0),
                    'neuronpedia_url': neuronpedia_url,
                    'fields': {k: v for k, v in edata.items()
                               if k != 'slug'},
                    **logit_flags,
                })

        self._states_cache = entities
        return entities

    def _get_entity_info_from_swap(self, source_dir: Path) -> Dict[str, str]:
        """Extract entity fields from a sample swap file's source section.

        Tries canonical files first, falls back to variant files for
        variant-only runs.
        """
        for swap_file in sorted(source_dir.glob("to_*.json")):
            try:
                with open(swap_file, 'r', encoding='utf-8') as f:
                    swap_data = json.load(f)
                source = swap_data.get('source', {})
                if source:
                    return {k: v for k, v in source.items()
                            if k not in ('prompt', 'concept',
                                         'neuronpedia_url')}
            except (json.JSONDecodeError, IOError):
                continue
        return {}

    def _load_entity_logit_metadata(self, entity_dir: Path,
                                     answer: str) -> Dict[str, Any]:
        """Load top-logit metadata from graph.json.

        ``answer`` is the expected output token (capital, author, etc.)
        used only for highlighting; the rest is model-agnostic.
        """
        graph_path = entity_dir / "00 Graph Generation" / "graph.json"
        if not graph_path.exists():
            return {}

        try:
            with open(graph_path, 'r', encoding='utf-8') as f:
                graph = json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

        import re

        logits: List[Dict] = []
        native_prob = 0.0
        target_token = ''

        for node in graph.get('nodes', []):
            clerp = node.get('clerp', '')
            prob = node.get('token_prob')
            if clerp and prob is not None and clerp.startswith('Output '):
                match = re.search(r'Output\s+"([^"]*)"', clerp)
                if match:
                    token = match.group(1).strip()
                    if token:
                        logits.append({
                            'token': token,
                            'prob': prob,
                            'is_target': node.get('is_target_logit', False),
                        })

            if node.get('is_target_logit') and not target_token:
                native_prob = node.get('token_prob', 0)
                match = re.search(r'Output\s+"([^"]*)"', clerp)
                target_token = (match.group(1).strip() if match
                                else clerp.strip().strip("'"))

        logits.sort(key=lambda x: x['prob'], reverse=True)
        top_logits = logits[:5]
        answer_lower = answer.lower() if answer else ''
        answer_in_logits = any(
            t and len(t) > 1 and t.lower() in answer_lower
            for t in (l.get('token', '') for l in top_logits)
        )

        return {
            'logits': top_logits,
            'native_prob': native_prob,
            'target_token': target_token,
            'capital_is_top_logit': (
                target_token.lower() in answer_lower
                if answer and target_token else False),
            'capital_in_logits': answer_in_logits,
        }

    def _get_entity_logit_flags(self, slug: str,
                                answer: str) -> Dict[str, Any]:
        """Return compact warning flags for the matrix entity list."""
        entity_dir = self._find_state_dir(slug)
        if not entity_dir:
            return {}
        metadata = self._load_entity_logit_metadata(entity_dir, answer)
        return {
            'capital_is_top_logit': metadata.get('capital_is_top_logit'),
            'capital_in_logits': metadata.get('capital_in_logits'),
        }
    
    def get_analysis(self) -> Dict[str, Any]:
        """Load analysis summary data."""
        if self._analysis_cache is not None:
            return self._analysis_cache
        
        analysis = {}
        analysis_dir = self.swaps_dir / "_analysis_v3"
        
        # Load tier summary
        tier_summary_path = analysis_dir / "tier_summary.json"
        if tier_summary_path.exists():
            with open(tier_summary_path, 'r', encoding='utf-8') as f:
                analysis['tier_summary'] = json.load(f)
        
        # Load swap factor summary
        factor_path = analysis_dir / "swap_factor_summary.json"
        if factor_path.exists():
            with open(factor_path, 'r', encoding='utf-8') as f:
                factor_data = json.load(f)
                analysis['correlations'] = factor_data.get('correlations', {})
                analysis['archetypes'] = factor_data.get('archetypes', {})
                analysis['insights'] = factor_data.get('insights', [])
                analysis['anomalies'] = factor_data.get('anomalies', {})
        
        self._analysis_cache = analysis
        return analysis
    
    def get_swap_detail(
        self, from_slug: str, to_slug: str, variant: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Load detailed swap result with variant resolution.

        Resolution order:
        1. Explicit *variant* requested -> load that variant file.
        2. Canonical file exists -> load it.
        3. Otherwise -> load the best variant for the pair.
        """
        data = None
        swap_path = None

        if variant:
            swap_path = (
                self.swaps_dir / "by_source" / from_slug
                / f"to_{to_slug}__{variant}.json"
            )
        else:
            canonical = self.swaps_dir / "by_source" / from_slug / f"to_{to_slug}.json"
            if canonical.exists():
                swap_path = canonical
            else:
                swap_path = self._best_variant_path(from_slug, to_slug)

        if swap_path is None or not swap_path.exists():
            work_path = self.swaps_dir / "work" / f"{from_slug}__to__{to_slug}.json"
            if work_path.exists():
                swap_path = work_path

        if swap_path is None or not swap_path.exists():
            return None

        with open(swap_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Enrich source/target with per-entity metadata
        data['source']['neuronpedia_url'] = self._get_neuronpedia_url(from_slug)
        data['target']['neuronpedia_url'] = self._get_neuronpedia_url(to_slug)

        for key, slug in (('source', from_slug), ('target', to_slug)):
            pct = self._get_error_node_influence(slug)
            if pct is not None:
                data[key]['error_node_influence_pct'] = pct

        # Inject derived metrics block (additive, null-safe)
        ctrl = data.get("metadata", {}).get("control", {})
        traj_summary = data.get("evaluation", {}).get("logit_trajectory", {}).get("summary", {})
        contrast = data.get("evaluation", {}).get("logit_trajectory", {}).get("contrast_groups", {})
        pos0 = data.get("evaluation", {}).get("position_0_comparison", {})

        regime = _classify_regime(pos0)
        regime_info = _REGIME_INFO.get(regime) if regime else None

        data["_derived"] = {
            "control_mode": ctrl.get("control_mode"),
            "fields_used": ctrl.get("concept_subsets_used"),
            "replicate_id": ctrl.get("replicate_id"),
            "flip_position": traj_summary.get("flip_position"),
            "gap_closure": traj_summary.get("gap_closure"),
            "initial_gap": traj_summary.get("initial_gap"),
            "best_gap": traj_summary.get("best_gap"),
            "regime": regime,
            "regime_label": regime_info["label"] if regime_info else None,
            "target_logit_delta": pos0.get("target_logit_delta"),
            "source_logit_delta": pos0.get("source_logit_delta"),
            "vs_max": None,
            "vs_topk": None,
            "rank_in_group": None,
            "vs_max_pos0": None,
            "vs_topk_pos0": None,
            "rank_in_group_pos0": None,
        }
        if isinstance(contrast, dict):
            grp = contrast.get("same_dataset", {})
            if isinstance(grp, dict):
                agg = grp.get("aggregate", {}) if isinstance(grp, dict) else {}
                data["_derived"]["vs_max"] = agg.get("best_target_minus_max")
                data["_derived"]["vs_topk"] = agg.get("best_target_minus_topk")
                data["_derived"]["rank_in_group"] = agg.get("best_rank_within")
                data["_derived"]["vs_max_pos0"] = agg.get("initial_target_minus_max")
                data["_derived"]["vs_topk_pos0"] = agg.get("initial_target_minus_topk")
                data["_derived"]["rank_in_group_pos0"] = agg.get("initial_rank_within")
                data["_derived"]["contrast_members"] = grp.get("members", [])
                data["_derived"]["contrast_n"] = grp.get("n_members", 0)
                data["_derived"]["contrast_topk_k"] = grp.get("topk_k", 3)

        # Variant availability summary
        variants = self.get_variants_for_pair(from_slug, to_slug)
        data["_variants"] = variants

        _, loaded_suffix = _parse_to_slug(swap_path.stem)
        data["_loaded_variant"] = loaded_suffix or None

        return data
    
    def save_annotation(self, from_slug: str, to_slug: str, 
                        tier: Optional[int] = None, 
                        notes: Optional[str] = None) -> Dict[str, Any]:
        """
        Save annotation (tier/notes) to the swap JSON file.
        
        Args:
            from_slug: Source state slug
            to_slug: Target state slug  
            tier: New tier value (1-5), or None to keep existing
            notes: Annotation notes, or None to keep existing
            
        Returns:
            Updated swap data with new stats
        """
        # Find the swap file
        swap_path = self.swaps_dir / "by_source" / from_slug / f"to_{to_slug}.json"
        if not swap_path.exists():
            swap_path = self.swaps_dir / "work" / f"{from_slug}__to__{to_slug}.json"
        
        if not swap_path.exists():
            raise FileNotFoundError(f"Swap file not found: {from_slug} -> {to_slug}")
        
        # Load existing data
        with open(swap_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Ensure classification section exists
        if 'classification' not in data:
            data['classification'] = {}
        
        # Update tier if provided
        if tier is not None:
            old_tier = data['classification'].get('tier')
            data['classification']['tier'] = tier
            data['classification']['manually_edited'] = True
            
        # Update notes if provided
        if notes is not None:
            data['classification']['notes'] = notes
            data['classification']['manually_edited'] = True
        
        # Save back to file
        with open(swap_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Clear caches so stats are recalculated
        self._matrix_cache = {}
        self._flip_matrix_cache = {}
        self._regime_matrix_cache = {}
        self._vsmax_matrix_cache = {}
        self._stats_cache = None
        
        # Return updated data with fresh stats
        return {
            'swap': data,
            'stats': self.get_stats(),
            'matrix_update': {
                'from': from_slug,
                'to': to_slug,
                'tier': data['classification'].get('tier'),
                'manually_edited': True,
            }
        }
    
    def get_annotated_swaps(self) -> List[Dict[str, str]]:
        """Get list of all manually annotated swaps."""
        annotated = []
        by_source_dir = self.swaps_dir / "by_source"
        
        if by_source_dir.exists():
            for source_dir in by_source_dir.iterdir():
                if not source_dir.is_dir():
                    continue
                from_slug = source_dir.name
                
                for swap_file in source_dir.glob("to_*.json"):
                    if _is_control_variant(swap_file.stem):
                        continue
                    try:
                        with open(swap_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        if data.get('classification', {}).get('manually_edited'):
                            to_slug, _ = _parse_to_slug(swap_file.stem)
                            annotated.append({
                                'from': from_slug,
                                'to': to_slug,
                                'tier': data['classification'].get('tier'),
                                'notes': data['classification'].get('notes', ''),
                            })
                    except (json.JSONDecodeError, IOError):
                        continue
        
        return annotated
    
    def get_stats(self) -> Dict[str, Any]:
        """Get aggregate statistics - computed dynamically from matrix."""
        if self._stats_cache is not None:
            return self._stats_cache
        
        matrix = self.get_matrix()
        analysis = self.get_analysis()
        
        # Count tiers from actual matrix data
        tier_counts = {
            'PERFECT': 0,           # 5
            'TARGET_STATE_CITY': 0, # 4
            'TARGET_STATE_ONLY': 0, # 3
            'SUPPRESSED_ONLY': 0,   # 2
            'SOURCE_PERSISTS': 0,   # 1
        }
        tier_names = {5: 'PERFECT', 4: 'TARGET_STATE_CITY', 3: 'TARGET_STATE_ONLY', 
                      2: 'SUPPRESSED_ONLY', 1: 'SOURCE_PERSISTS'}
        
        total_swaps = 0
        tier_sum = 0
        perfect_count = 0
        state_correct_count = 0  # T3+
        suppressed_count = 0     # T2+
        
        for from_slug, targets in matrix.items():
            for to_slug, tier in targets.items():
                if tier is not None and from_slug != to_slug:
                    total_swaps += 1
                    tier_sum += tier
                    
                    tier_name = tier_names.get(tier, 'UNKNOWN')
                    if tier_name in tier_counts:
                        tier_counts[tier_name] += 1
                    
                    if tier == 5:
                        perfect_count += 1
                    if tier >= 3:
                        state_correct_count += 1
                    if tier >= 2:
                        suppressed_count += 1
        
        # Calculate rates
        tier_rates = {}
        for name, count in tier_counts.items():
            tier_rates[name] = count / total_swaps if total_swaps > 0 else 0

        # Flip stats from trajectory data
        flip_matrix = self.get_flip_matrix()
        flip_tracked = 0
        flip_at_0 = 0
        flip_at_01 = 0
        for from_slug, targets in flip_matrix.items():
            for to_slug, fp in targets.items():
                if fp == -1:
                    continue
                flip_tracked += 1
                if fp is not None and fp <= 1:
                    flip_at_01 += 1
                if fp is not None and fp == 0:
                    flip_at_0 += 1

        aggregate = {
            'perfect_rate': perfect_count / total_swaps if total_swaps > 0 else 0,
            'state_correct_rate': state_correct_count / total_swaps if total_swaps > 0 else 0,
            'suppression_rate': suppressed_count / total_swaps if total_swaps > 0 else 0,
            'avg_tier': tier_sum / total_swaps if total_swaps > 0 else 0,
            'flip_at_01_rate': flip_at_01 / flip_tracked if flip_tracked > 0 else 0,
            'flip_at_0_rate': flip_at_0 / flip_tracked if flip_tracked > 0 else 0,
            'flip_tracked': flip_tracked,
        }
        
        stats = {
            'total_swaps': total_swaps,
            'tier_counts': tier_counts,
            'tier_rates': tier_rates,
            'aggregate': aggregate,
            'correlations': analysis.get('correlations', {}),
            'insights': analysis.get('insights', []),
        }
        self._stats_cache = stats
        return stats

    def get_methodology_stats(self) -> Dict[str, Any]:
        """Compute dynamic stats for the About / methodology panel.

        Scans the current run's swap files for regime distribution,
        aggregate vsMax, and target recovery rates.  Results are cached.
        """
        cache_key = "_methodology_stats"
        if hasattr(self, cache_key) and getattr(self, cache_key) is not None:
            return getattr(self, cache_key)

        stats = self.get_stats()
        dc = self.get_domain_config()
        total_swaps = stats.get("total_swaps", 0)
        aggregate = stats.get("aggregate", {})

        regime_counts: Dict[str, int] = {}
        vs_max_values: list = []
        recovery_count = 0
        recovery_total = 0

        by_source = self.swaps_dir / "by_source"
        if by_source.exists():
            for swap_path in by_source.glob("*/to_*.json"):
                if _is_control_variant(swap_path.stem):
                    continue
                try:
                    with open(swap_path, "r", encoding="utf-8") as fh:
                        d = json.load(fh)
                except (json.JSONDecodeError, IOError):
                    continue

                pos0 = d.get("evaluation", {}).get("position_0_comparison", {})
                regime = _classify_regime(pos0)
                if regime:
                    regime_counts[regime] = regime_counts.get(regime, 0) + 1

                contrast = (
                    d.get("evaluation", {})
                    .get("logit_trajectory", {})
                    .get("contrast_groups", {})
                    .get("same_dataset", {})
                    .get("aggregate", {})
                )
                vm = contrast.get("best_target_minus_max")
                if vm is not None:
                    vs_max_values.append(vm)

                traj_sum = d.get("evaluation", {}).get("logit_trajectory", {}).get("summary", {})
                baseline = d.get("evaluation", {}).get("baseline_logits", {})
                if traj_sum and baseline:
                    recovery_total += 1
                    tgt_baseline_logit = baseline.get("target", {}).get("logit")
                    best_gap = traj_sum.get("best_gap")
                    initial_gap = traj_sum.get("initial_gap")
                    if tgt_baseline_logit is not None and best_gap is not None:
                        recovery_count += 1

        regime_total = sum(regime_counts.values()) or 1

        result = {
            "display_name": dc.get("display_name", ""),
            "total_swaps": total_swaps,
            "entity_count": dc.get("entity_count", 0),
            "model_id": dc.get("model_id", ""),
            "concept_fields": dc.get("concept_fields", []),
            "answer_field": dc.get("answer_field", ""),
            "m_ablate": dc.get("m_ablate", -2),
            "m_amplify": dc.get("m_amplify", 20),
            "n_tokens": dc.get("n_tokens", 10),
            "temperature": dc.get("temperature", 0.3),
            "hit_rate": aggregate.get("perfect_rate", 0),
            "suppression_rate": aggregate.get("suppression_rate", 0),
            "flip_at_01_rate": aggregate.get("flip_at_01_rate", 0),
            "avg_tier": aggregate.get("avg_tier", 0),
            "vs_max_mean": (
                sum(vs_max_values) / len(vs_max_values)
                if vs_max_values else None
            ),
            "vs_max_positive_pct": (
                sum(1 for v in vs_max_values if v > 0) / len(vs_max_values)
                if vs_max_values else None
            ),
            "regime_counts": regime_counts,
            "regime_pcts": {
                k: round(v / regime_total * 100, 1)
                for k, v in regime_counts.items()
            },
            "regime_labels": {k: v["label"] for k, v in _REGIME_INFO.items()},
        }
        setattr(self, cache_key, result)
        return result

    def _get_gpu_batch_features_index(self) -> Dict[str, List]:
        """
        Build and cache a swap_id -> feature_list index from GPU batch files.

        Scans _swaps/_work/_gpu_batch_*/features.json which use the format:
          {"global": [...], "per_prompt": {"swap_id": [...features], ...}}
        """
        if self._gpu_batch_features_index is not None:
            return self._gpu_batch_features_index

        index: Dict[str, List] = {}
        work_dir = self.base_swaps_dir / "_work"
        if not work_dir.exists():
            self._gpu_batch_features_index = index
            return index

        for batch_file in sorted(work_dir.glob("_gpu_batch_*/features.json")):
            try:
                with open(batch_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for swap_id, feats in data.get('per_prompt', {}).items():
                    if isinstance(feats, list):
                        index[swap_id] = feats
            except (json.JSONDecodeError, IOError):
                pass

        self._gpu_batch_features_index = index
        return index

    def _resolve_features_path(
        self, from_slug: str, to_slug: str, variant: Optional[str] = None,
    ) -> Optional[Path]:
        """Find the features.json path for a swap, handling variant suffixes.

        Resolution order:
        1. Explicit variant -> ``work/{swap_id}__{variant}/features.json``
        2. Base path (labeled runs) -> ``work/{swap_id}/features.json``
        3. Best variant (mirroring ``get_swap_detail``) work dir.
        """
        base_swap_id = f"{from_slug}__to__{to_slug}"
        work_dir = self.swaps_dir / "work"

        if variant:
            p = work_dir / f"{base_swap_id}__{variant}" / "features.json"
            return p if p.exists() else None

        # Try the base path first (works for labeled runs with no suffix)
        p = work_dir / base_swap_id / "features.json"
        if p.exists():
            return p

        # Resolve via best variant (same logic as get_swap_detail)
        best_path = self._best_variant_path(from_slug, to_slug)
        if best_path is not None:
            _, variant_suffix = _parse_to_slug(best_path.stem)
            if variant_suffix:
                p = work_dir / f"{base_swap_id}__{variant_suffix}" / "features.json"
                if p.exists():
                    return p

        return None

    def get_swap_features(
        self, from_slug: str, to_slug: str, variant: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Get intervention features for a swap.

        Tries locations in order:
          1. Per-swap file via variant resolution (see ``_resolve_features_path``)
          2. GPU batch index: _swaps/_work/_gpu_batch_N/features.json  (per_prompt keyed)

        Returns structured data with ablated/amplified features grouped by layer,
        enriched with supernode_name from each entity's node_grouping.csv.
        Also returns source/target grouping lists with ablated/amplified flags.
        """
        swap_id = f"{from_slug}__to__{to_slug}"

        raw_features: Optional[List] = None
        features_path = self._resolve_features_path(from_slug, to_slug, variant)
        if features_path is not None:
            try:
                with open(features_path, 'r', encoding='utf-8') as f:
                    raw_features = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        # Fall back to GPU batch index
        if raw_features is None:
            index = self._get_gpu_batch_features_index()
            raw_features = index.get(swap_id)

        if raw_features is None:
            return None

        np_model = self.get_domain_config().get('np_model', 'gemma-2-2b')

        def _load_grouping_map(slug: str) -> Dict:
            """Return {(layer, index): supernode_name} for an entity."""
            entity_dir = self._find_state_dir(slug)
            if not entity_dir:
                return {}
            grouping_path = entity_dir / "02 Node Grouping" / "node_grouping.csv"
            if not grouping_path.exists():
                return {}
            result = {}
            try:
                with open(grouping_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        try:
                            key = (int(row.get('layer', 0)), int(row.get('feature', 0)))
                            result[key] = row.get('supernode_name', '')
                        except (ValueError, TypeError):
                            pass
            except IOError:
                pass
            return result

        def _load_all_groupings(slug: str) -> List[Dict[str, Any]]:
            """Return sorted groupings with total feature counts for an entity."""
            entity_dir = self._find_state_dir(slug)
            if not entity_dir:
                return []
            grouping_path = entity_dir / "02 Node Grouping" / "node_grouping.csv"
            if not grouping_path.exists():
                return []
            grouping_counts: Dict[str, int] = {}
            try:
                with open(grouping_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        sn = row.get('supernode_name', '').strip()
                        if sn:
                            grouping_counts[sn] = grouping_counts.get(sn, 0) + 1
            except IOError:
                pass
            return [
                {'name': name, 'feature_count': grouping_counts[name]}
                for name in sorted(grouping_counts)
            ]

        source_map = _load_grouping_map(from_slug)
        target_map = _load_grouping_map(to_slug)
        all_source_groupings = _load_all_groupings(from_slug)
        all_target_groupings = _load_all_groupings(to_slug)

        # Group features by type and layer
        ablated = []
        amplified = []
        layer_counts: Dict = {'ablated': {}, 'amplified': {}}
        ablated_grouping_names: set = set()
        amplified_grouping_names: set = set()

        for feat in raw_features:
            layer = feat.get('layer', 0)
            index = feat.get('index', 0)
            M = feat.get('M', 0)
            stored_activation = feat.get('stored_activation')
            np_url = f"https://www.neuronpedia.org/{np_model}/{layer}-clt-hp/{index}"

            if M < 0:
                sn = source_map.get((layer, index), '')
                feature_info = {
                    'layer': layer,
                    'index': index,
                    'M': M,
                    'stored_activation': stored_activation,
                    'neuronpedia_url': np_url,
                    'supernode_name': sn,
                }
                ablated.append(feature_info)
                layer_counts['ablated'][layer] = layer_counts['ablated'].get(layer, 0) + 1
                if sn:
                    ablated_grouping_names.add(sn)
            else:
                sn = target_map.get((layer, index), '')
                feature_info = {
                    'layer': layer,
                    'index': index,
                    'M': M,
                    'stored_activation': stored_activation,
                    'neuronpedia_url': np_url,
                    'supernode_name': sn,
                }
                amplified.append(feature_info)
                layer_counts['amplified'][layer] = layer_counts['amplified'].get(layer, 0) + 1
                if sn:
                    amplified_grouping_names.add(sn)

        ablated.sort(key=lambda x: (x['layer'], x['index']))
        amplified.sort(key=lambda x: (x['layer'], x['index']))

        source_groupings = [
            {
                'name': grouping['name'],
                'feature_count': grouping['feature_count'],
                'ablated': grouping['name'] in ablated_grouping_names,
            }
            for grouping in all_source_groupings
        ]
        target_groupings = [
            {
                'name': grouping['name'],
                'feature_count': grouping['feature_count'],
                'amplified': grouping['name'] in amplified_grouping_names,
            }
            for grouping in all_target_groupings
        ]

        return {
            'swap_id': swap_id,
            'ablated': ablated,
            'amplified': amplified,
            'layer_counts': layer_counts,
            'summary': {
                'ablate_count': len(ablated),
                'amplify_count': len(amplified),
                'total_count': len(ablated) + len(amplified),
            },
            'source_groupings': source_groupings,
            'target_groupings': target_groupings,
        }
    
    def get_state_profile(self, slug: str) -> Optional[Dict]:
        """Get comprehensive entity profile with stats (domain-agnostic)."""
        dc = self.get_domain_config()
        entity_index = dc['entity_index']
        edata = entity_index.get(slug, {})
        primary_field = dc['primary_field']
        answer_field = dc['answer_field']

        label = edata.get(primary_field, '') or self._slug_to_label(slug)
        answer = edata.get(answer_field, '')

        entity_dir = self._find_state_dir(slug)

        profile: Dict[str, Any] = {
            'slug': slug,
            'label': label,
            'answer': answer,
            'state': edata.get('state', label),
            'city': edata.get('city', edata.get(primary_field, label)),
            'capital': edata.get('capital', answer),
            'fields': {k: v for k, v in edata.items() if k != 'slug'},
        }

        if entity_dir:
            manifest = self._load_manifest(entity_dir)
            if manifest:
                np_data = manifest.get('neuronpedia', {})
                profile['supernodes'] = np_data.get('supernodes', 0)
                profile['pinned_nodes'] = np_data.get('pinned_nodes', 0)
                profile['neuronpedia_url'] = np_data.get('url', '')

                gq = manifest.get('graph_quality', {})
                pct = gq.get('error_node_influence_pct')
                if pct is not None:
                    profile['error_node_influence_pct'] = pct

            if 'error_node_influence_pct' not in profile:
                pct = self._get_error_node_influence(slug)
                if pct is not None:
                    profile['error_node_influence_pct'] = pct

            profile.update(
                self._load_entity_logit_metadata(entity_dir, answer))

            features_path = (entity_dir / "00 Graph Generation"
                             / "selected_features_with_nodes.json")
            if features_path.exists():
                try:
                    with open(features_path, 'r', encoding='utf-8') as f:
                        features_data = json.load(f)
                    features = features_data.get('features', [])
                    profile['total_features'] = len(features)
                    layer_counts: Dict[int, int] = {}
                    for feat in features:
                        layer = feat.get('layer', 0)
                        layer_counts[layer] = layer_counts.get(layer, 0) + 1
                    profile['feature_layers'] = layer_counts
                except (json.JSONDecodeError, IOError):
                    pass

            grouping_path = (entity_dir / "02 Node Grouping"
                             / "node_grouping.csv")
            if grouping_path.exists():
                try:
                    match_terms: set = set()
                    for cf in dc['concept_fields']:
                        val = edata.get(cf, '')
                        if val:
                            match_terms.add(val.lower())
                    if label:
                        match_terms.add(label.lower())

                    supernode_features = []
                    supernode_layer_counts: Dict[int, int] = {}
                    with open(grouping_path, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            sn = row.get('supernode_name', '').lower()
                            if any(t in sn or sn in t
                                   for t in match_terms):
                                layer = int(row.get('layer', 0))
                                supernode_features.append({
                                    'layer': layer,
                                    'feature': row.get('feature', ''),
                                    'supernode_name': row.get(
                                        'supernode_name', ''),
                                })
                                supernode_layer_counts[layer] = (
                                    supernode_layer_counts.get(layer, 0) + 1)

                    profile['supernode_features'] = supernode_features
                    profile['supernode_feature_count'] = len(
                        supernode_features)
                    profile['supernode_layer_counts'] = supernode_layer_counts
                except (IOError, ValueError):
                    pass

        # Attack/defense scores from matrix
        matrix = self.get_matrix()

        attack_tiers = []
        if slug in matrix:
            for to_slug, tier in matrix[slug].items():
                if tier is not None and to_slug != slug:
                    attack_tiers.append(tier)
        profile['attack_avg'] = (sum(attack_tiers) / len(attack_tiers)
                                 if attack_tiers else 0)
        profile['attack_count'] = len(attack_tiers)
        attack_ok = len([t for t in attack_tiers if t >= 3])
        profile['attack_success_rate'] = (attack_ok / len(attack_tiers)
                                          if attack_tiers else 0)

        defense_tiers = []
        wrong_count = 0
        for from_slug, targets in matrix.items():
            if (from_slug != slug and slug in targets
                    and targets[slug] is not None):
                tier = targets[slug]
                defense_tiers.append(tier)
                if tier == 2.5:
                    wrong_count += 1
        profile['defense_avg'] = (sum(defense_tiers) / len(defense_tiers)
                                  if defense_tiers else 0)
        profile['defense_count'] = len(defense_tiers)
        defense_ok = len([t for t in defense_tiers if t >= 3])
        profile['defense_success_rate'] = (defense_ok / len(defense_tiers)
                                           if defense_tiers else 0)
        profile['wrong_state_rate'] = (wrong_count / len(defense_tiers)
                                       if defense_tiers else 0)
        profile['wrong_state_count'] = wrong_count

        profile['has_token_overlap'] = False
        if dc['is_usa_states']:
            overlap_slugs = [
                'colorado_colorado_springs', 'new_york_new_york_city',
                'virginia_virginia_beach', 'idaho_idaho_falls',
                'missouri_kansas_city', 'indiana_fort_wayne',
            ]
            profile['has_token_overlap'] = slug in overlap_slugs

        profile['swaps_as_target'] = self._get_swap_summaries_as_target(slug)
        profile['swaps_as_source'] = self._get_swap_summaries_as_source(slug)

        return profile
    
    def _get_swap_summaries_as_target(self, slug: str) -> List[Dict]:
        """Swaps where this entity is the target."""
        matrix = self.get_matrix()
        entity_map = {s['slug']: s for s in self.get_states()}

        summaries = []
        for from_slug, targets in matrix.items():
            if from_slug != slug and slug in targets and targets[slug] is not None:
                tier = targets[slug]
                e = entity_map.get(from_slug, {})
                summaries.append({
                    'from_slug': from_slug,
                    'from_state': e.get('label', e.get('state', from_slug)),
                    'from_city': e.get('city', ''),
                    'tier': tier,
                })
        summaries.sort(key=lambda x: -x['tier'])
        return summaries

    def _get_swap_summaries_as_source(self, slug: str) -> List[Dict]:
        """Swaps where this entity is the source."""
        matrix = self.get_matrix()
        entity_map = {s['slug']: s for s in self.get_states()}

        summaries = []
        if slug in matrix:
            for to_slug, tier in matrix[slug].items():
                if to_slug != slug and tier is not None:
                    e = entity_map.get(to_slug, {})
                    summaries.append({
                        'to_slug': to_slug,
                        'to_state': e.get('label', e.get('state', to_slug)),
                        'to_city': e.get('city', ''),
                        'tier': tier,
                    })
        summaries.sort(key=lambda x: -x['tier'])
        return summaries
    
    def _get_error_node_influence(self, slug: str) -> Optional[float]:
        """Return error_node_influence_pct for an entity, with CSV fallback."""
        entity_dir = self._find_state_dir(slug)
        if not entity_dir:
            return None

        manifest = self._load_manifest(entity_dir)
        if manifest:
            gq = manifest.get('graph_quality', {})
            pct = gq.get('error_node_influence_pct')
            if pct is not None:
                return pct

        # Fallback: compute from graph_feature_static_metrics.csv
        csv_path = (entity_dir / "00 Graph Generation"
                    / "graph_feature_static_metrics.csv")
        if not csv_path.exists():
            return None
        try:
            total = 0.0
            error = 0.0
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ni = float(row.get('node_influence', 0) or 0)
                    total += ni
                    feat = row.get('feature', '')
                    if feat == '-1':
                        error += ni
            if total > 0:
                return round(error / total * 100, 2)
        except (IOError, ValueError):
            pass
        return None

    def _find_state_dir(self, slug: str) -> Optional[Path]:
        """Find the state directory, handling case variations."""
        state_dir = self.data_dir / slug
        if state_dir.exists():
            return state_dir
        
        # Try case variations
        for candidate in self.data_dir.iterdir():
            if candidate.is_dir() and candidate.name.lower().replace(' ', '_') == slug.lower():
                return candidate
        
        return None
    
    def _load_manifest(self, state_dir: Path) -> Optional[Dict]:
        """Load manifest.json from state directory."""
        manifest_path = state_dir / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return None

    @staticmethod
    def _add_query_params(url: str, params: Dict[str, str], overwrite: bool = False) -> str:
        """
        Add query params to a URL, preserving existing params.

        Args:
            url: Base URL
            params: Params to add
            overwrite: If True, overwrite existing keys. If False, keep existing keys.
        """
        try:
            parts = urlsplit(url)
        except Exception:
            return url

        existing = parse_qsl(parts.query, keep_blank_values=True)
        query_map = {}
        for k, v in existing:
            # Keep the first value for each key (Neuronpedia URLs typically do not repeat keys)
            if k not in query_map:
                query_map[k] = v

        for k, v in (params or {}).items():
            if k in query_map and not overwrite:
                continue
            query_map[k] = v

        new_query = urlencode(query_map, doseq=False)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))

    def get_complete_subgraph_url(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        Return the Neuronpedia "complete subgraph" URL using the uploaded subgraph ID.

        This uses neuronpedia.subgraph_id from manifest.json and appends it as the
        `subgraph` query parameter to the manifest neuronpedia.url.
        """
        state_dir = self._find_state_dir(slug)
        if not state_dir:
            return None

        manifest = self._load_manifest(state_dir)
        if not manifest:
            return None

        np_data = manifest.get('neuronpedia', {}) or {}
        base_url = (np_data.get('url') or '').strip()
        subgraph_id = (np_data.get('subgraph_id') or '').strip()
        if not base_url or not subgraph_id:
            return None

        full_url = self._add_query_params(base_url, {"subgraph": subgraph_id}, overwrite=False)
        return {
            "url": full_url,
            "base_url": base_url,
            "subgraph_id": subgraph_id,
            "mode": "complete",
        }
    
    def _get_neuronpedia_url(self, slug: str) -> Optional[str]:
        """Get Neuronpedia URL for a state slug."""
        # Try exact match first
        state_dir = self.data_dir / slug
        if state_dir.exists():
            manifest = self._load_manifest(state_dir)
            if manifest:
                return manifest.get('neuronpedia', {}).get('url')
        
        # Try case variations
        for candidate in self.data_dir.iterdir():
            if candidate.is_dir() and candidate.name.lower().replace(' ', '_') == slug.lower():
                manifest = self._load_manifest(candidate)
                if manifest:
                    return manifest.get('neuronpedia', {}).get('url')
        
        return None
    
    def _slug_to_state_name(self, slug: str) -> str:
        """Convert slug to state name."""
        # arizona_tucson -> Arizona
        parts = slug.split('_')
        if len(parts) >= 1:
            state = parts[0].replace('_', ' ').title()
            # Handle two-word states
            if len(parts) >= 2 and parts[0].lower() in ['new', 'north', 'south', 'west', 'rhode']:
                state = f"{parts[0].title()} {parts[1].title()}"
            return state
        return slug.title()
    
    def _slug_to_city(self, slug: str) -> str:
        """Extract city from slug."""
        # arizona_tucson -> Tucson
        parts = slug.split('_')
        state_parts = 1
        if parts[0].lower() in ['new', 'north', 'south', 'west', 'rhode']:
            state_parts = 2
        city_parts = parts[state_parts:]
        return ' '.join(p.title() for p in city_parts)
    
    def _state_to_abbr(self, state_name: str) -> str:
        """Convert state name to abbreviation."""
        abbrs = {
            'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR',
            'California': 'CA', 'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE',
            'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI', 'Idaho': 'ID',
            'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS',
            'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
            'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS',
            'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV',
            'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY',
            'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK',
            'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
            'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT',
            'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV',
            'Wisconsin': 'WI', 'Wyoming': 'WY'
        }
        return abbrs.get(state_name, state_name[:2].upper())
    
    def _get_state_capital(self, state_name: str) -> str:
        """Get the capital city for a state."""
        capitals = {
            'Alabama': 'Montgomery', 'Alaska': 'Juneau', 'Arizona': 'Phoenix', 'Arkansas': 'Little Rock',
            'California': 'Sacramento', 'Colorado': 'Denver', 'Connecticut': 'Hartford', 'Delaware': 'Dover',
            'Florida': 'Tallahassee', 'Georgia': 'Atlanta', 'Hawaii': 'Honolulu', 'Idaho': 'Boise',
            'Illinois': 'Springfield', 'Indiana': 'Indianapolis', 'Iowa': 'Des Moines', 'Kansas': 'Topeka',
            'Kentucky': 'Frankfort', 'Louisiana': 'Baton Rouge', 'Maine': 'Augusta', 'Maryland': 'Annapolis',
            'Massachusetts': 'Boston', 'Michigan': 'Lansing', 'Minnesota': 'Saint Paul', 'Mississippi': 'Jackson',
            'Missouri': 'Jefferson City', 'Montana': 'Helena', 'Nebraska': 'Lincoln', 'Nevada': 'Carson City',
            'New Hampshire': 'Concord', 'New Jersey': 'Trenton', 'New Mexico': 'Santa Fe', 'New York': 'Albany',
            'North Carolina': 'Raleigh', 'North Dakota': 'Bismarck', 'Ohio': 'Columbus', 'Oklahoma': 'Oklahoma City',
            'Oregon': 'Salem', 'Pennsylvania': 'Harrisburg', 'Rhode Island': 'Providence', 'South Carolina': 'Columbia',
            'South Dakota': 'Pierre', 'Tennessee': 'Nashville', 'Texas': 'Austin', 'Utah': 'Salt Lake City',
            'Vermont': 'Montpelier', 'Virginia': 'Richmond', 'Washington': 'Olympia', 'West Virginia': 'Charleston',
            'Wisconsin': 'Madison', 'Wyoming': 'Cheyenne'
        }
        return capitals.get(state_name, '')
    
    def get_simplified_subgraph_url(self, slug: str, max_features: int = 80,
                                     max_url_length: int = 4000) -> Optional[Dict]:
        """
        Generate a simplified subgraph URL with important features pinned.
        
        Priority order for pinning:
        1. Capital logit (layer 27) - always included
        2. City embedding (layer -1, city token) - always included  
        3. State-related features - always included if space
        4. Remaining features sorted by node_influence
        
        Args:
            slug: State slug (e.g., 'alabama_Birmingham')
            max_features: Maximum features to include (default 80)
            max_url_length: Maximum URL length (default 4000 chars)
            
        Returns:
            Dict with 'url', 'feature_count', 'supernode_count', 'url_length'
            or None if data not found
        """
        import csv
        from urllib.parse import quote
        
        state_dir = self._find_state_dir(slug)
        if not state_dir:
            return None
        
        # Load manifest for base URL
        manifest = self._load_manifest(state_dir)
        if not manifest or 'neuronpedia' not in manifest:
            return None
        
        base_url = manifest['neuronpedia'].get('url', '')
        if not base_url:
            return None
        
        dc = self.get_domain_config()
        edata = dc['entity_index'].get(slug, {})
        state_name = edata.get('state', self._slug_to_state_name(slug))
        city_name = edata.get('city', self._slug_to_city(slug))
        capital_name = edata.get('capital',
                                 edata.get(dc['answer_field'], '')
                                 or self._get_state_capital(state_name))
        
        # Load graph.json to get the TOP logit by probability
        # The metrics CSV has incomplete/empty data for layer 27
        graph_path = state_dir / "00 Graph Generation" / "graph.json"
        top_logit_node = None  # Will store the full node dict for the top logit
        top_logit_prob = 0
        if graph_path.exists():
            try:
                with open(graph_path, 'r', encoding='utf-8') as f:
                    graph_data = json.load(f)
                for node in graph_data.get('nodes', []):
                    clerp = node.get('clerp', '')
                    prob = node.get('token_prob', 0)
                    node_id = node.get('node_id', '')
                    # Output logits have format: "Output \" Token\" (p=0.123)"
                    if clerp.startswith('Output ') and prob and prob > top_logit_prob:
                        top_logit_prob = prob
                        # Build a node dict matching our format
                        top_logit_node = {
                            'node_id': node_id,  # Use node_id directly from graph.json
                            'layer': '27',
                            'feature_id': node_id.split('_')[1] if '_' in node_id else '',
                            'ctx_idx': '8',
                            'token': clerp,
                            'influence': prob,  # Use prob as influence
                            'supernode': 'output_logit',
                        }
            except (json.JSONDecodeError, IOError):
                pass
        
        # Load graph metrics (has node_influence)
        metrics_path = state_dir / "00 Graph Generation" / "graph_feature_static_metrics.csv"
        if not metrics_path.exists():
            return None
        
        # Load node grouping for supernode assignments
        # Key on {layer}_{feature} only, since a feature can appear at multiple positions
        # in the metrics file but node_grouping only has the peak position
        grouping_path = state_dir / "02 Node Grouping" / "node_grouping.csv"
        supernode_map = {}  # {layer}_{feature} -> supernode_name
        if grouping_path.exists():
            try:
                with open(grouping_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        layer = row.get('layer', '0')
                        feature = row.get('feature', '0')
                        key = f"{layer}_{feature}"
                        supernode_map[key] = row.get('supernode_name', '')
            except (IOError, csv.Error):
                pass
        
        # Parse metrics file
        embeddings = []      # Layer -1 (priority)
        output_logits = []   # Layer 27 (priority)
        priority_nodes = []  # State/city related
        other_nodes = []     # Everything else
        all_supernode_nodes = {}  # supernode_name -> list[node] (features only; excludes embeddings/logits)
        
        try:
            with open(metrics_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    layer = row.get('layer', '0')
                    feature = row.get('feature', '0')
                    ctx_idx = row.get('ctx_idx', '0')
                    token = row.get('token', '').strip()
                    feature_id = row.get('id', feature)  # For embeddings
                    
                    # Skip residual connections (feature=-1 in layers > -1)
                    if feature == '-1' and layer != '-1':
                        continue
                    
                    # Parse node_influence for sorting
                    try:
                        influence = float(row.get('node_influence', 0) or 0)
                    except (ValueError, TypeError):
                        influence = 0
                    
                    # Build node_id based on layer type
                    # IMPORTANT: Use feature_id (the 'id' column) for ALL node IDs
                    # The 'feature' column contains internal IDs that Neuronpedia doesn't recognize
                    if layer == '-1':
                        # Embedding: E_{id}_{ctx_idx}
                        node_id = f"E_{feature_id}_{ctx_idx}"
                    else:
                        # Regular feature: {layer}_{id}_{ctx_idx}
                        node_id = f"{layer}_{feature_id}_{ctx_idx}"
                    
                    # Get supernode from grouping or infer from token
                    # Key on {layer}_{feature_id} without position to match all occurrences
                    grouping_key = f"{layer}_{feature_id}"
                    supernode = supernode_map.get(grouping_key, '')
                    
                    # For embeddings (layer -1), infer supernode from token
                    if layer == '-1' and not supernode:
                        clean_token = token.strip()
                        if clean_token:
                            # Use cleaned token as supernode name
                            supernode = clean_token.replace('<', '').replace('>', '')
                    
                    # For output logits (layer 27), assign to output group
                    if layer == '27' and not supernode:
                        supernode = 'output_logit'
                    
                    node = {
                        'node_id': node_id,
                        'layer': layer,
                        'feature': feature,
                        'feature_id': feature_id,
                        'ctx_idx': ctx_idx,
                        'token': token,
                        'influence': influence,
                        'supernode': supernode,
                    }

                    # Track full membership for each supernode (features only)
                    if supernode and layer not in ('-1', '27'):
                        if supernode not in all_supernode_nodes:
                            all_supernode_nodes[supernode] = []
                        all_supernode_nodes[supernode].append(node)
                    
                    # Categorize by priority
                    if layer == '-1':
                        # Exclude functional embeddings (bos, The, of, the, etc.)
                        excluded_embeddings = {'bos', 'The', 'the', 'of', 'a', 'an', 'is'}
                        clean_token = token.strip()
                        if clean_token in excluded_embeddings or clean_token.replace('<', '').replace('>', '') in excluded_embeddings:
                            continue  # Skip this embedding
                        
                        embeddings.append(node)
                        # Check if this is city or state embedding
                        if city_name.lower() in token.lower():
                            node['priority'] = 'city'
                        elif state_name.lower() in token.lower():
                            node['priority'] = 'state'
                    elif layer == '27':
                        output_logits.append(node)
                    elif (city_name.lower() in token.lower() or
                          state_name.lower() in token.lower() or
                          (capital_name and capital_name.lower() in token.lower()) or
                          'capital' in supernode.lower() or
                          state_name.lower() in supernode.lower() or
                          city_name.lower() in supernode.lower() or
                          (capital_name and capital_name.lower() in supernode.lower())):
                        priority_nodes.append(node)
                    else:
                        other_nodes.append(node)
                        
        except (IOError, csv.Error) as e:
            return None
        
        # Sort each category by node_influence (descending)
        embeddings.sort(key=lambda x: -x['influence'])
        priority_nodes.sort(key=lambda x: -x['influence'])
        other_nodes.sort(key=lambda x: -x['influence'])
        
        # Use the top logit from graph.json (highest probability)
        # This is more reliable than the metrics CSV which has incomplete layer 27 data
        top_logit = top_logit_node

        # Identify supernodes whose NAME contains the state or capital name.
        # For these, we try to include the ENTIRE supernode group (all member nodes),
        # as long as there is capacity (max_features).
        import re

        def _norm_name(s: str) -> str:
            s = (s or '').lower().replace('_', ' ')
            s = re.sub(r'[^a-z0-9 ]+', ' ', s)
            return ' '.join(s.split())

        norm_state = _norm_name(state_name)
        norm_capital = _norm_name(capital_name)

        forced_supernodes = []  # [(priority, -max_influence, name)]
        if norm_state or norm_capital:
            for name, nodes in (all_supernode_nodes or {}).items():
                if not name or len(nodes) < 2:
                    continue
                norm_group = _norm_name(name)
                match_capital = bool(norm_capital) and (norm_capital in norm_group)
                match_state = bool(norm_state) and (norm_state in norm_group)
                if not (match_capital or match_state):
                    continue

                max_inf = 0
                try:
                    max_inf = max((n.get('influence') or 0) for n in nodes)
                except ValueError:
                    max_inf = 0

                forced_priority = 0 if match_capital else 1
                forced_supernodes.append((forced_priority, -max_inf, name))

        forced_supernodes.sort()

        # Build forced nodes (include whole matching supernode groups if they fit)
        forced_nodes = []
        forced_included = 0
        forced_omitted = 0
        forced_node_ids = set()

        reserved = len(embeddings) + (1 if top_logit else 0)
        remaining_forced = max_features - reserved
        if remaining_forced > 0 and forced_supernodes:
            for _, __, name in forced_supernodes:
                group_nodes = all_supernode_nodes.get(name, [])
                group_nodes_sorted = sorted(group_nodes, key=lambda x: -(x.get('influence') or 0))
                unique_group = [n for n in group_nodes_sorted if n.get('node_id') and n['node_id'] not in forced_node_ids]
                if len(unique_group) <= remaining_forced:
                    forced_nodes.extend(unique_group)
                    forced_node_ids.update(n['node_id'] for n in unique_group)
                    forced_included += 1
                    remaining_forced -= len(unique_group)
                else:
                    forced_omitted += 1

        # Build candidate nodes list (after reserving space for forced groups)
        # 1. Semantic embeddings (layer -1) - always included
        # 2. Top output logit (layer 27) - always included
        # 3. Forced groups (state/capital-named supernodes) - include whole group if it fits
        # 4. Priority nodes (state/city/capital related)
        # 5. Fill remaining with other high-influence nodes
        candidates = []
        candidates.extend(priority_nodes)
        remaining_slots = max_features - len(embeddings) - (1 if top_logit else 0) - len(forced_nodes) - len(priority_nodes)
        if remaining_slots > 0:
            candidates.extend(other_nodes[:remaining_slots])

        # First pass: only keep candidates that belong to supernodes with 2+ members
        temp_supernode_groups = {}
        for node in candidates:
            supernode = node.get('supernode', '')
            if not supernode:
                continue
            if supernode not in temp_supernode_groups:
                temp_supernode_groups[supernode] = []
            temp_supernode_groups[supernode].append(node)
        valid_supernodes = {k for k, v in temp_supernode_groups.items() if len(v) >= 2}

        # Build final selected list (deduplicated by node_id, preserving priority order)
        selected = []
        seen_node_ids = set()

        def _add_node(node: Dict[str, Any]) -> None:
            node_id = node.get('node_id', '')
            if not node_id or node_id in seen_node_ids:
                return
            seen_node_ids.add(node_id)
            selected.append(node)

        for node in embeddings:
            _add_node(node)
        if top_logit:
            _add_node(top_logit)
        for node in forced_nodes:
            _add_node(node)
        for node in candidates:
            if node.get('supernode', '') in valid_supernodes:
                _add_node(node)

        # Enforce max_features as a hard cap (forced groups are added before candidates,
        # so truncation only drops lower-priority tail nodes).
        if len(selected) > max_features:
            selected = selected[:max_features]
        
        # Build pinnedIds and supernodes
        pinned_ids = []
        supernode_groups = {}
        
        for node in selected:
            pinned_ids.append(node['node_id'])
            
            # Embeddings (layer -1) and output logits (layer 27) are pinned but NOT grouped
            if node['layer'] in ('-1', '27'):
                continue
            
            supernode = node['supernode']
            if supernode:
                if supernode not in supernode_groups:
                    supernode_groups[supernode] = []
                supernode_groups[supernode].append(node['node_id'])

        # Filter supernodes to only groups with 2+ members
        supernode_groups = {k: v for k, v in supernode_groups.items() if len(v) >= 2}
        
        # Build supernodes JSON array
        supernodes_array = []
        for name, ids in sorted(supernode_groups.items()):
            supernodes_array.append([name] + ids)
        
        # Encode and build URL
        pinned_param = ','.join(pinned_ids)
        supernodes_json = json.dumps(supernodes_array, separators=(',', ':'))
        
        separator = '&' if '?' in base_url else '?'
        full_url = f"{base_url}{separator}pinnedIds={quote(pinned_param)}&supernodes={quote(supernodes_json)}"
        
        # If URL too long, reduce features
        while len(full_url) > max_url_length and len(selected) > 20:
            # Remove lowest influence non-priority nodes
            selected = selected[:-5]
            pinned_ids = [n['node_id'] for n in selected]
            supernode_groups = {}
            for node in selected:
                # Skip embeddings and logits for grouping
                if node['layer'] in ('-1', '27'):
                    continue
                if node['supernode']:
                    if node['supernode'] not in supernode_groups:
                        supernode_groups[node['supernode']] = []
                    supernode_groups[node['supernode']].append(node['node_id'])
            
            # Filter to 2+ node groups only
            supernode_groups = {k: v for k, v in supernode_groups.items() if len(v) >= 2}
            supernodes_array = [[name] + ids for name, ids in sorted(supernode_groups.items())]
            pinned_param = ','.join(pinned_ids)
            supernodes_json = json.dumps(supernodes_array, separators=(',', ':'))
            full_url = f"{base_url}{separator}pinnedIds={quote(pinned_param)}&supernodes={quote(supernodes_json)}"
        
        return {
            'url': full_url,
            'base_url': base_url,
            'feature_count': len(selected),
            'supernode_count': len(supernode_groups),
            'url_length': len(full_url),
            'embeddings_count': len([n for n in selected if n['layer'] == '-1']),
            'logits_count': len([n for n in selected if n['layer'] == '27']),
            'priority_count': len([n for n in selected if n in priority_nodes]),
            'forced_supernodes_included': forced_included,
            'forced_supernodes_omitted': forced_omitted,
        }

