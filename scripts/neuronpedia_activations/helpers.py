"""
Shared helpers for Neuronpedia activation scripts.
"""

from __future__ import annotations

import json
import re
from typing import List, Dict, Any


def load_prompts(path: str) -> List[Dict[str, str]]:
    """
    Load prompts from JSON file and normalize to [{"id": str, "text": str}, ...].
    Supports:
      - ["prompt 1", "prompt 2", ...]
      - [{"id": "...", "text": "..."}]
      - {"prompts": [... as above ...]}
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "prompts" in data:
        data = data["prompts"]

    prompts: List[Dict[str, str]] = []
    if not isinstance(data, list):
        raise ValueError("Invalid prompts.json format (expected list or {'prompts': [...]})")

    for i, item in enumerate(data):
        if isinstance(item, str):
            prompts.append({"id": f"p{i}", "text": item})
        elif isinstance(item, dict):
            text = item.get("text", item.get("prompt"))
            if not isinstance(text, str):
                raise ValueError(f"Prompt #{i} invalid: expected 'text' field")
            pid = str(item.get("id", f"p{i}"))
            entry: Dict[str, str] = {"id": pid, "text": text}
            for key in ("target_token", "source_token", "contrast_tokens"):
                if key in item:
                    entry[key] = item[key]
            prompts.append(entry)
        else:
            raise ValueError(f"Prompt #{i}: unsupported type {type(item)}")

    return prompts


def load_features(path: str, source_set: str) -> List[Dict[str, Any]]:
    """
    Load features from JSON file and normalize to [{"source": "L-source_set", "index": idx}, ...].
    Accepts either {"features": [...]} or a bare list.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "features" in data:
        data = data["features"]

    if not isinstance(data, list):
        raise ValueError("Invalid features.json format (expected list or {'features': [...]})")

    normalized: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"feature #{i}: expected object, got {type(item)}")

        if "source" in item and "index" in item:
            source = str(item["source"])
            idx = int(item["index"])
            if "-" not in source:
                match = re.search(r"(\d+)", source)
                if not match:
                    raise ValueError(f"feature #{i}: unable to infer layer from source '{source}'")
                layer = int(match.group(1))
                source = f"{layer}-{source_set}"
            else:
                suffix = source.split("-", 1)[1]
                if suffix != source_set:
                    raise ValueError(
                        f"feature #{i}: source_set '{suffix}' != expected '{source_set}'"
                    )
            normalized.append({"source": source, "index": idx})
        elif "layer" in item and "index" in item:
            layer = int(item["layer"])
            idx = int(item["index"])
            normalized.append({"source": f"{layer}-{source_set}", "index": idx})
        else:
            raise ValueError(f"feature #{i}: expected ('source','index') or ('layer','index')")

    return normalized

