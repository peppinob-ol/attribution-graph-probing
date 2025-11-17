import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER_DIR = REPO_ROOT / "scripts" / "experiments" / "batch"
for path in (REPO_ROOT, RUNNER_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.experiments.batch.run_batch_from_yaml import run_batch


def test_remote_retry_and_summary(tmp_path, monkeypatch):
    """Smoke test the remote retry + summary generation."""

    outputs_root = tmp_path / "outputs"
    config_path = tmp_path / "smoke.yml"

    config = {
        "version": 0.1,
        "experiment_name": "smoke_retry",
        "paths": {"outputs_root": str(outputs_root)},
        "model": {"id": "test-model", "source_set": "test-set"},
        "features": {"selection": "cumulative_influence", "threshold": 0.5},
        "probes": {"mode": "templated", "templated": {"templates": []}},
        "get_activations": {
            "backend": "local",
            "local": {"chunk_by_layer": True, "include_zero": True},
        },
        "compute": {
            "remote": {
                "enabled": True,
                "host": "localhost",
                "user": "tester",
                "base_dir": "/tmp",
                "repo_dir": "/tmp/repo",
                "logs_dir": "/tmp/logs",
                "env_activate_cmd": "true",
                "gpu_selection": "auto",
                "max_gpus": 1,
                "batch_size": 1,
                "max_retries": 1,
                "persist_sae_cache": False,
            }
        },
        "grouping": {"enabled": False, "upload": {"enabled": False}},
        "steps": {
            "graph_generation": False,
            "feature_export": False,
            "probe_prompts": False,
            "activations": True,
            "grouping": False,
            "upload_subgraph": False,
            "dry_run": False,
            "force": False,
        },
        "graph_generation": {
            "enabled": False,
            "seeds_mode": "templated",
            "templated": {
                "seed_prompt": "Prompt {city}",
                "slug_template": "{slug}",
                "entities": {"items": [{"slug": "seed_one", "city": "Test City"}]},
            },
        },
    }

    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    # Stub out remote connection check
    monkeypatch.setattr(
        "scripts.experiments.batch.run_batch_from_yaml.verify_remote_connection",
        lambda *args, **kwargs: True,
    )

    call_counter = {"attempts": 0}

    def fake_remote_batch(_config, batch_states, batch_id, verbose):
        call_counter["attempts"] += 1
        metadata = {"gpu_id": 0, "remote_log": f"{batch_id}.log", "batch_id": batch_id}
        per_seed = {}
        for state in batch_states:
            slug = state["seed"]["slug"]
            if call_counter["attempts"] == 1:
                per_seed[slug] = {
                    "success": False,
                    "error": "Simulated failure",
                    "remote_log": f"{slug}_fail.log",
                    "local_log": f"{slug}_fail_local.log",
                }
            else:
                per_seed[slug] = {
                    "success": True,
                    "remote_log": f"{slug}_ok.log",
                    "local_log": f"{slug}_ok_local.log",
                }
        batch_success = call_counter["attempts"] > 1
        return batch_success, metadata, per_seed

    monkeypatch.setattr(
        "scripts.experiments.batch.run_batch_from_yaml.process_remote_activation_batch",
        fake_remote_batch,
    )

    assert run_batch(str(config_path), dry_run=False, force=False, verbose=False)

    summary_files = sorted(outputs_root.glob("_summary_*.json"))
    assert summary_files, "summary file not generated"
    summary = json.loads(summary_files[-1].read_text(encoding="utf-8"))

    assert summary["remote"]["requeues"] == 1
    seed_entry = summary["seeds"][0]
    assert seed_entry["slug"] == "seed_one"
    assert seed_entry["status"] == "completed"
    assert seed_entry["retry_attempts"] == 1

    manifest_path = outputs_root / "seed_one" / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    assert manifest.get("remote")

