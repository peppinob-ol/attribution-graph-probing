"""
Probe prompts handling for batch experiments.
Supports shared_file and templated modes.
"""
import json
import shutil
from pathlib import Path
from typing import Dict, Any, List


def process_probes_step(config: Dict[str, Any], seed: Dict[str, Any], paths: Dict[str, Path],
                        verbose: bool = True) -> bool:
    """
    Process probe prompts step for a seed.
    
    Depending on probes.mode:
    - shared_file: copy/symlink shared prompts.json
    - per_seed_file: use seed-specific prompts_json path
    - templated: render templates with seed entities
    
    Returns True if successful, False otherwise.
    """
    probes_dir = paths['probes_dir']
    probes_dir.mkdir(parents=True, exist_ok=True)
    
    prompts_json_path = paths['prompts_json']
    
    probes_config = config.get('probes', {})
    mode = probes_config.get('mode', 'shared_file')
    
    if mode == 'shared_file':
        # Copy shared prompts file
        shared_file_config = probes_config.get('shared_file', {})
        source_prompts = shared_file_config.get('prompts_json')
        
        if not source_prompts:
            print(f"ERROR: probes.mode=shared_file but probes.shared_file.prompts_json not set")
            return False
        
        source_path = Path(source_prompts)
        if not source_path.exists():
            print(f"ERROR: Shared prompts file not found: {source_path}")
            return False
        
        if verbose:
            print(f"  Copying shared prompts: {source_path} -> {prompts_json_path}")
        
        shutil.copy2(source_path, prompts_json_path)
        return True
    
    elif mode == 'per_seed_file':
        # Use per-seed prompts_json from seed config
        if 'prompts_json' not in seed:
            print(f"ERROR: probes.mode=per_seed_file but seed has no prompts_json field")
            return False
        
        source_path = Path(seed['prompts_json'])
        if not source_path.exists():
            print(f"ERROR: Per-seed prompts file not found: {source_path}")
            return False
        
        if verbose:
            print(f"  Copying per-seed prompts: {source_path} -> {prompts_json_path}")
        
        shutil.copy2(source_path, prompts_json_path)
        return True
    
    elif mode == 'templated':
        # Generate prompts from templates + seed entities
        if 'entity' not in seed:
            print(f"ERROR: probes.mode=templated but seed has no entity field")
            return False
        
        templated_config = probes_config.get('templated', {})
        templates = templated_config.get('templates', [])
        
        if not templates:
            print(f"ERROR: probes.mode=templated but probes.templated.templates is empty")
            return False
        
        if verbose:
            print(f"  Generating templated prompts for {len(templates)} templates...")
        
        # Render each template with seed entities
        prompts_list = []
        entity_set = seed['entity']
        
        for template in templates:
            probe_id = template.get('id', f"probe_{len(prompts_list)}")
            text_template = template.get('text', '')
            
            try:
                text = text_template.format(**entity_set)
                prompts_list.append({
                    'id': probe_id,
                    'text': text
                })
            except KeyError as e:
                print(f"WARNING: Template placeholder {e} not in entity set, skipping template {probe_id}")
                continue
        
        if not prompts_list:
            print(f"ERROR: No prompts generated from templates")
            return False
        
        # Write prompts.json
        with open(prompts_json_path, 'w', encoding='utf-8') as f:
            json.dump(prompts_list, f, indent=2, ensure_ascii=False)
        
        if verbose:
            print(f"    Generated {len(prompts_list)} probe prompts")
            print(f"    Wrote: {prompts_json_path}")
        
        return True
    
    else:
        print(f"ERROR: Unsupported probes.mode: {mode}")
        return False

