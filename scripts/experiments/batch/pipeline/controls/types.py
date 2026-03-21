"""
Shared types for the controls subsystem.

These types define the contract between the runner (run_batch_swaps.py)
and any control-mode builder, and also carry diagnostics that future
analysis code can inspect.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class InterventionResult:
    """Return value of every InterventionBuilder.build_for_pair() call."""

    features: List[Dict[str, Any]]
    """Intervention dicts ready for batch_steering_ct.py."""

    ablate_count: int
    amplify_count: int

    control_mode: str
    """Which builder produced this result (e.g. 'labeled')."""

    concept_subsets_used: Optional[List[str]] = None
    """Which concept fields were actually matched (e.g. ['book', 'author'])."""

    replicate_id: Optional[int] = None
    """For repeated-randomization controls."""

    diagnostics: Dict[str, Any] = field(default_factory=dict)
    """
    Builder-specific diagnostics:
      - matching quality reports
      - exclusion counts
      - candidate pool sizes
      - anything auditable by downstream analysis
    """

    def to_metadata(self) -> Dict[str, Any]:
        """Flatten to a dict suitable for embedding in swap-result JSON."""
        meta: Dict[str, Any] = {
            "control_mode": self.control_mode,
            "ablate_count": self.ablate_count,
            "amplify_count": self.amplify_count,
        }
        if self.concept_subsets_used is not None:
            meta["concept_subsets_used"] = self.concept_subsets_used
        if self.replicate_id is not None:
            meta["replicate_id"] = self.replicate_id
        if self.diagnostics:
            meta["diagnostics"] = self.diagnostics
        return meta
