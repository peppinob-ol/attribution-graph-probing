"""
Shared logic for selecting concept subsets.

Concept fields in this pipeline have a semantic role:
  - 'source' concepts: the entity being ablated (e.g. state, book)
  - 'link' concepts: bridging concepts (e.g. capital, character)
  - 'target' concepts: the answer being amplified (e.g. capital, author)

The labeled builder always uses all configured concept_fields for both
ablation and amplification.  The additivity builder can select subsets
like [source], [target], [source, target], [source, link, target].

This module maps abstract role names to the concrete concept_fields
entries from the swap config so that subset selection is data-driven.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def get_concept_fields(swap_cfg: Dict[str, Any]) -> List[str]:
    """
    Return the full list of concept fields from the swap config.

    Handles backward-compatible ``include_capitals`` / ``include_capital``.
    """
    raw = swap_cfg.get("concept_fields", None)
    if raw is None:
        fields: List[str] = ["state"]
    elif isinstance(raw, str):
        fields = [raw]
    elif isinstance(raw, list):
        fields = [str(x) for x in raw if str(x).strip()]
    else:
        raise ValueError("swap.concept_fields must be a string or list of strings")

    if bool(
        swap_cfg.get("include_capitals", False)
        or swap_cfg.get("include_capital", False)
    ):
        if "capital" not in fields:
            fields.append("capital")

    return fields


def resolve_concept_roles(
    concept_fields: List[str],
    role_map: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, List[str]]:
    """
    Map abstract roles to concrete concept field names.

    If ``role_map`` is not provided, infer a default mapping:
      - source: first field
      - link: middle fields (if any)
      - target: last field (same as answer_field convention)

    Parameters
    ----------
    concept_fields:
        e.g. ``["book", "author"]`` or ``["state", "capital"]``
    role_map:
        Optional explicit mapping, e.g.
        ``{"source": ["book"], "link": [], "target": ["author"]}``

    Returns
    -------
    dict mapping role name -> list of concept field names
    """
    if role_map is not None:
        return role_map

    if len(concept_fields) == 0:
        return {"source": [], "link": [], "target": []}
    if len(concept_fields) == 1:
        return {"source": concept_fields[:1], "link": [], "target": concept_fields[:1]}

    return {
        "source": concept_fields[:1],
        "link": concept_fields[1:-1],
        "target": concept_fields[-1:],
    }


def select_concept_subset(
    concept_fields: List[str],
    subset_roles: List[str],
    role_map: Optional[Dict[str, List[str]]] = None,
) -> List[str]:
    """
    Return the concept fields that belong to the requested roles.

    Parameters
    ----------
    concept_fields:
        All concept fields from config.
    subset_roles:
        e.g. ``["source"]``, ``["source", "target"]``,
        ``["source", "link", "target"]``
    role_map:
        Optional explicit role -> fields mapping.

    Returns
    -------
    Ordered, deduplicated list of concept field names.
    """
    roles = resolve_concept_roles(concept_fields, role_map)
    seen: set = set()
    result: List[str] = []
    for role in subset_roles:
        for field in roles.get(role, []):
            if field not in seen:
                seen.add(field)
                result.append(field)
    return result
