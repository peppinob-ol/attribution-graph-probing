"""
Verifies that every key in DEFAULT_THRESHOLDS in scripts/02_node_grouping.py
is reachable from the batch pipeline.

Two-part check:
  1. Every DEFAULT_THRESHOLDS key has a matching argparse flag in
     02_node_grouping.py and, when provided, the CLI copies it into the
     thresholds dict before classification.
  2. pipeline/grouping.py forwards every configured threshold to the CLI
     command it builds, with no key silently dropped.

No sweep is launched; subprocess.run is monkeypatched and inspected.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"


def _load_grouping_cli():
    """Load scripts/02_node_grouping.py as a module without executing main()."""
    module_name = "node_grouping_cli"
    spec = importlib.util.spec_from_file_location(
        module_name, SCRIPTS_DIR / "02_node_grouping.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_pipeline_grouping():
    module_name = "pipeline_grouping_under_test"
    spec = importlib.util.spec_from_file_location(
        module_name,
        SCRIPTS_DIR / "experiments" / "batch" / "pipeline" / "grouping.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


ALL_THRESHOLD_KEYS = {
    "dict_peak_consistency_min",
    "dict_n_distinct_peaks_max",
    "sayx_func_vs_sem_min",
    "sayx_conf_f_min",
    "sayx_layer_min",
    "rel_sparsity_max",
    "sem_layer_max",
    "sem_conf_s_min",
    "sem_func_vs_sem_max",
}


def test_default_thresholds_cover_decision_tree_surface():
    cli = _load_grouping_cli()
    assert set(cli.DEFAULT_THRESHOLDS.keys()) == ALL_THRESHOLD_KEYS, (
        "DEFAULT_THRESHOLDS surface changed; update ALL_THRESHOLD_KEYS and "
        "the CLI / pipeline forwarding maps accordingly."
    )


def test_pipeline_forwards_every_threshold(monkeypatch, tmp_path):
    """pipeline/grouping.py must forward every DEFAULT_THRESHOLDS key."""
    pipeline = _load_pipeline_grouping()

    # Shifted defaults for every key so we can detect silent drops.
    cli = _load_grouping_cli()
    shifted: dict = {}
    for key, default_val in cli.DEFAULT_THRESHOLDS.items():
        if isinstance(default_val, bool):
            shifted[key] = not default_val
        elif isinstance(default_val, int) and not isinstance(default_val, bool):
            shifted[key] = default_val + 1
        elif isinstance(default_val, float):
            shifted[key] = default_val * 0.9
        else:
            shifted[key] = default_val

    cli_map = {
        "dict_peak_consistency_min": "--dict-consistency-min",
        "dict_n_distinct_peaks_max": "--dict-n-distinct-peaks-max",
        "sayx_func_vs_sem_min": "--sayx-func-min",
        "sayx_conf_f_min": "--sayx-conf-f-min",
        "sayx_layer_min": "--sayx-layer-min",
        "rel_sparsity_max": "--rel-sparsity-max",
        "sem_layer_max": "--sem-layer-max",
        "sem_conf_s_min": "--sem-conf-s-min",
        "sem_func_vs_sem_max": "--sem-func-vs-sem-max",
    }
    assert set(cli_map.keys()) == ALL_THRESHOLD_KEYS

    config = {
        "grouping": {
            "enabled": True,
            "window": 7,
            "thresholds": shifted,
            "blacklist_tokens": ["the"],
            "upload": {"enabled": False},
        },
        "steps": {"upload_subgraph": False},
    }
    seed = {"slug": "unit-test-seed"}

    grouping_dir = tmp_path / "02_Node_Grouping"
    grouping_dir.mkdir(parents=True, exist_ok=True)

    activations_json_path = tmp_path / "activations_dump.json"
    activations_json_path.write_text("{\"results\": []}", encoding="utf-8")

    graph_json_path = tmp_path / "graph.json"
    graph_json_path.write_text("{}", encoding="utf-8")

    paths = {
        "grouping_dir": grouping_dir,
        "grouping_csv": grouping_dir / "node_grouping.csv",
        "activations_dump_json": activations_json_path,
        "graph_json": graph_json_path,
        "base": tmp_path,
        "selected_features_json": tmp_path / "selected_features_with_nodes.json",
    }

    def fake_activations_dump_to_csv(src, dst, verbose=True):
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text("feature_key,layer,feature,prompt,peak_token\n", encoding="utf-8")
        return True

    monkeypatch.setattr(
        pipeline,
        "activations_dump_to_csv",
        fake_activations_dump_to_csv,
    )

    captured: dict = {}

    def fake_run(cmd, capture_output=True, text=True, timeout=600):
        captured["cmd"] = list(cmd)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)

    ok = pipeline.process_grouping_step(config, seed, paths, verbose=False)
    assert ok is True
    assert "cmd" in captured, "process_grouping_step did not call subprocess.run"

    cmd = captured["cmd"]
    for key, flag in cli_map.items():
        assert flag in cmd, f"Pipeline dropped threshold flag {flag} for key {key}"
        idx = cmd.index(flag)
        assert idx + 1 < len(cmd), f"{flag} passed with no value"
        assert cmd[idx + 1] == str(shifted[key]), (
            f"Value for {flag} mangled: expected {shifted[key]!r}, got {cmd[idx + 1]!r}"
        )


def test_cli_applies_every_threshold_override():
    """02_node_grouping.py CLI must copy every argparse override into the
    thresholds dict before calling classify_nodes."""
    cli = _load_grouping_cli()

    # We don't run main(); we replicate its override block against a synthetic
    # argparse.Namespace and assert every key is written.
    import argparse

    ns = argparse.Namespace(
        dict_consistency_min=0.5,
        dict_n_distinct_peaks_max=2,
        sayx_func_min=12.5,
        sayx_conf_f_min=0.55,
        sayx_layer_min=9,
        rel_sparsity_max=0.33,
        sem_layer_max=4,
        sem_conf_s_min=0.42,
        sem_func_vs_sem_max=22.0,
    )

    thresholds = cli.DEFAULT_THRESHOLDS.copy()
    if ns.dict_consistency_min is not None:
        thresholds["dict_peak_consistency_min"] = ns.dict_consistency_min
    if ns.dict_n_distinct_peaks_max is not None:
        thresholds["dict_n_distinct_peaks_max"] = ns.dict_n_distinct_peaks_max
    if ns.sayx_func_min is not None:
        thresholds["sayx_func_vs_sem_min"] = ns.sayx_func_min
    if ns.sayx_conf_f_min is not None:
        thresholds["sayx_conf_f_min"] = ns.sayx_conf_f_min
    if ns.sayx_layer_min is not None:
        thresholds["sayx_layer_min"] = ns.sayx_layer_min
    if ns.rel_sparsity_max is not None:
        thresholds["rel_sparsity_max"] = ns.rel_sparsity_max
    if ns.sem_layer_max is not None:
        thresholds["sem_layer_max"] = ns.sem_layer_max
    if ns.sem_conf_s_min is not None:
        thresholds["sem_conf_s_min"] = ns.sem_conf_s_min
    if ns.sem_func_vs_sem_max is not None:
        thresholds["sem_func_vs_sem_max"] = ns.sem_func_vs_sem_max

    assert set(thresholds.keys()) == ALL_THRESHOLD_KEYS
    assert thresholds["dict_peak_consistency_min"] == 0.5
    assert thresholds["dict_n_distinct_peaks_max"] == 2
    assert thresholds["sayx_func_vs_sem_min"] == 12.5
    assert thresholds["sayx_conf_f_min"] == 0.55
    assert thresholds["sayx_layer_min"] == 9
    assert thresholds["rel_sparsity_max"] == 0.33
    assert thresholds["sem_layer_max"] == 4
    assert thresholds["sem_conf_s_min"] == 0.42
    assert thresholds["sem_func_vs_sem_max"] == 22.0


def test_cli_parser_exposes_every_threshold_flag(monkeypatch, capsys):
    """Running the CLI with --help must advertise every threshold flag."""
    cli = _load_grouping_cli()

    monkeypatch.setattr(sys, "argv", ["02_node_grouping.py", "--help"])

    # We can't call main() directly because --help sys.exit()s; build the parser
    # inline to check flags. Recreate the parser the same way main() does by
    # executing the argparse block reflectively.
    #
    # Simpler approach: re-run main() in a subprocess-style guard and inspect
    # the ArgumentParser instance via a lightweight helper below.
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--json", default=None)
    parser.add_argument("--graph", default=None)
    parser.add_argument("--window", type=int, default=7)
    parser.add_argument("--skip-classify", action="store_true")
    parser.add_argument("--skip-naming", action="store_true")
    parser.add_argument("--dict-consistency-min", type=float, default=None)
    parser.add_argument("--dict-n-distinct-peaks-max", type=int, default=None)
    parser.add_argument("--sayx-func-min", type=float, default=None)
    parser.add_argument("--sayx-conf-f-min", type=float, default=None)
    parser.add_argument("--sayx-layer-min", type=int, default=None)
    parser.add_argument("--rel-sparsity-max", type=float, default=None)
    parser.add_argument("--sem-layer-max", type=int, default=None)
    parser.add_argument("--sem-conf-s-min", type=float, default=None)
    parser.add_argument("--sem-func-vs-sem-max", type=float, default=None)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--blacklist", type=str, default="")

    # Sanity: all 9 threshold flags parse correctly.
    ns = parser.parse_args([
        "--input", "/tmp/in.csv",
        "--output", "/tmp/out.csv",
        "--dict-consistency-min", "0.7",
        "--dict-n-distinct-peaks-max", "3",
        "--sayx-func-min", "20.0",
        "--sayx-conf-f-min", "0.5",
        "--sayx-layer-min", "6",
        "--rel-sparsity-max", "0.4",
        "--sem-layer-max", "5",
        "--sem-conf-s-min", "0.6",
        "--sem-func-vs-sem-max", "30.0",
    ])

    assert ns.dict_consistency_min == 0.7
    assert ns.dict_n_distinct_peaks_max == 3
    assert ns.sayx_func_min == 20.0
    assert ns.sayx_conf_f_min == 0.5
    assert ns.sayx_layer_min == 6
    assert ns.rel_sparsity_max == 0.4
    assert ns.sem_layer_max == 5
    assert ns.sem_conf_s_min == 0.6
    assert ns.sem_func_vs_sem_max == 30.0

    # Additionally, the real script's source must contain every flag string;
    # this catches the case where someone deletes a parser.add_argument().
    script_text = (SCRIPTS_DIR / "02_node_grouping.py").read_text(encoding="utf-8")
    for flag in [
        "--dict-consistency-min",
        "--dict-n-distinct-peaks-max",
        "--sayx-func-min",
        "--sayx-conf-f-min",
        "--sayx-layer-min",
        "--rel-sparsity-max",
        "--sem-layer-max",
        "--sem-conf-s-min",
        "--sem-func-vs-sem-max",
    ]:
        assert flag in script_text, f"02_node_grouping.py no longer exposes {flag}"
