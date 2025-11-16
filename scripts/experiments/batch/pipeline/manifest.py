"""
Manifest generation for batch experiments.
Records experiment metadata, config, and run info.
"""
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


def get_git_info() -> Dict[str, str]:
    """Get current git commit hash and branch."""
    try:
        commit = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        
        branch = subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        
        return {'commit': commit, 'branch': branch}
    except:
        return {'commit': 'unknown', 'branch': 'unknown'}


def create_manifest(config: Dict[str, Any], seed: Dict[str, Any], paths: Dict[str, Path],
                   status: str = 'started', error: str = None) -> Dict[str, Any]:
    """
    Create manifest dict for a seed run.
    
    Args:
        config: Full experiment config
        seed: Seed config
        paths: Seed paths
        status: 'started', 'completed', 'failed'
        error: Error message if status='failed'
    """
    git_info = get_git_info()
    
    manifest = {
        'experiment_name': config.get('experiment_name', 'unknown'),
        'version': config.get('version', '0.1'),
        'seed': {
            'slug': seed['slug'],
            'mode': seed.get('mode', 'precomputed'),
        },
        'model': {
            'id': config['model']['id'],
            'source_set': config['model']['source_set'],
        },
        'features': {
            'selection': config['features']['selection'],
            'threshold': config['features'].get('threshold'),
        },
        'steps_enabled': config['steps'],
        'timestamp_started': datetime.now().isoformat(),
        'timestamp_completed': None,
        'status': status,
        'git': git_info,
        'compute': {
            'backend': config['get_activations']['backend'],
            'remote_enabled': config.get('compute', {}).get('remote', {}).get('enabled', False),
        },
        'remote': None,
    }
    
    if error:
        manifest['error'] = error
    
    return manifest


def write_manifest(manifest: Dict[str, Any], paths: Dict[str, Path]) -> None:
    """Write manifest to seed's base directory."""
    manifest_path = paths['base'] / 'manifest.json'
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

