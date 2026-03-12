"""
Data loader for swap experiment results.

Reads from output/usa_states_batch/ directory structure:
- _swaps/runs/{run_id}/by_source/*/to_*.json - Swap details (run-specific)
- _swaps/by_source/*/to_*.json - Swap details (legacy fallback)
- _swaps/_analysis_v3/*.json - Analysis data
- */manifest.json - Neuronpedia URLs

Supports multiple experiment runs via run_id parameter.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import csv
from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


class DataLoader:
    """Load and cache swap experiment data with multi-run support."""
    
    def __init__(self, data_dir: Path, run_id: Optional[str] = None):
        self.data_dir = Path(data_dir)
        self.base_swaps_dir = self.data_dir / "_swaps"
        self.run_id = run_id
        self._set_swaps_dir()
        self._matrix_cache: Optional[Dict] = None
        self._states_cache: Optional[List[Dict]] = None
        self._analysis_cache: Optional[Dict] = None
        self._stats_cache: Optional[Dict] = None
    
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
        """Choose the default run for a fresh app load."""
        runs = self.list_runs()
        if not runs:
            return None

        preferred_prefixes = ("full_50states",)

        for prefix in preferred_prefixes:
            for run in runs:
                if run["id"].startswith(prefix):
                    return run["id"]

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
        self._matrix_cache = None
        self._states_cache = None
        self._analysis_cache = None
        self._stats_cache = None
    
    def get_matrix(self) -> Dict[str, Dict[str, Optional[int]]]:
        """Build tier matrix dynamically from individual swap JSON files."""
        if self._matrix_cache is not None:
            return self._matrix_cache
        
        matrix = {}
        
        # Scan by_source directory for swap results
        by_source_dir = self.swaps_dir / "by_source"
        if by_source_dir.exists():
            for source_dir in by_source_dir.iterdir():
                if not source_dir.is_dir():
                    continue
                from_slug = source_dir.name
                matrix[from_slug] = {}
                
                for swap_file in source_dir.glob("to_*.json"):
                    try:
                        with open(swap_file, 'r', encoding='utf-8') as f:
                            swap_data = json.load(f)
                        
                        # Extract target slug from filename or data
                        to_slug = swap_file.stem.replace("to_", "")
                        if not to_slug and swap_data.get('target'):
                            to_slug = swap_data['target'].get('slug', '')
                        
                        # Get tier from classification or compute it
                        tier = self._get_tier_from_swap(swap_data)
                        matrix[from_slug][to_slug] = tier
                        
                    except (json.JSONDecodeError, IOError):
                        continue
        
        # Also check work directory for additional swaps
        work_dir = self.swaps_dir / "work"
        if work_dir.exists():
            for swap_file in work_dir.glob("*.json"):
                try:
                    with open(swap_file, 'r', encoding='utf-8') as f:
                        swap_data = json.load(f)
                    
                    # Parse swap_id: from_slug__to__to_slug
                    swap_id = swap_file.stem
                    if "__to__" in swap_id:
                        from_slug, to_slug = swap_id.split("__to__")
                        
                        if from_slug not in matrix:
                            matrix[from_slug] = {}
                        
                        # Only add if not already in by_source
                        if to_slug not in matrix[from_slug]:
                            tier = self._get_tier_from_swap(swap_data)
                            matrix[from_slug][to_slug] = tier
                            
                except (json.JSONDecodeError, IOError):
                    continue
        
        self._matrix_cache = matrix
        return matrix
    
    def _get_tier_from_swap(self, swap_data: Dict) -> Optional[float]:
        """Extract tier from swap data, computing if necessary. Supports 2.5 for WRONG STATE."""
        # Try classification first
        if 'classification' in swap_data:
            tier = swap_data['classification'].get('tier')
            if tier is not None:
                return float(tier)  # Supports 2.5 for WRONG STATE
        
        # Compute from evaluation data
        evaluation = swap_data.get('evaluation', {})
        exact = evaluation.get('exact_match', {})
        
        if exact.get('steered_has_to_capital'):
            return 5  # PERFECT
        elif exact.get('from_suppressed') and not exact.get('steered_has_to_capital'):
            return 2  # SUPPRESSED_ONLY
        elif not exact.get('from_suppressed'):
            return 1  # SOURCE_PERSISTS
        else:
            return 3  # TARGET_STATE_ONLY (default)
    
    def get_states(self) -> List[Dict[str, Any]]:
        """Get list of all states with metadata from by_source directories."""
        if self._states_cache is not None:
            return self._states_cache
        
        states = []
        analysis = self.get_analysis()
        archetypes = analysis.get('archetypes', {})
        
        # Build archetype lookup
        archetype_lookup = {}
        for archetype, state_list in archetypes.items():
            for state_data in state_list:
                archetype_lookup[state_data['state']] = {
                    'archetype': archetype,
                    'native_prob': state_data.get('native_prob', 0),
                    'supernodes': state_data.get('supernodes', 0),
                    'src_tier': state_data.get('src_tier', 0),
                    'tgt_tier': state_data.get('tgt_tier', 0),
                }
        
        # Get states from by_source directory (has all 50 states)
        by_source_dir = self.swaps_dir / "by_source"
        if by_source_dir.exists():
            for source_dir in sorted(by_source_dir.iterdir()):
                if not source_dir.is_dir():
                    continue
                
                slug = source_dir.name
                state_name = self._slug_to_state_name(slug)
                arch_data = archetype_lookup.get(state_name, {})
                
                # Try to find Neuronpedia URL from manifest
                neuronpedia_url = self._get_neuronpedia_url(slug)
                
                # Get a sample swap to extract state info
                state_info = self._get_state_info_from_swap(source_dir)
                capital = state_info.get('capital', '')
                logit_flags = self._get_state_logit_flags(slug, capital)
                
                states.append({
                    'slug': slug,
                    'state': state_info.get('state', state_name),
                    'capital': capital,
                    'city': state_info.get('city', self._slug_to_city(slug)),
                    'abbr': self._state_to_abbr(state_info.get('state', state_name)),
                    'archetype': arch_data.get('archetype', 'Unknown'),
                    'native_prob': arch_data.get('native_prob', 0),
                    'supernodes': arch_data.get('supernodes', 0),
                    'src_tier': arch_data.get('src_tier', 0),
                    'tgt_tier': arch_data.get('tgt_tier', 0),
                    'neuronpedia_url': neuronpedia_url,
                    **logit_flags,
                })
        
        self._states_cache = states
        return states
    
    def _get_state_info_from_swap(self, source_dir: Path) -> Dict[str, str]:
        """Extract state info from a sample swap file."""
        for swap_file in source_dir.glob("to_*.json"):
            try:
                with open(swap_file, 'r', encoding='utf-8') as f:
                    swap_data = json.load(f)
                source = swap_data.get('source', {})
                if source:
                    return {
                        'state': source.get('state', ''),
                        'capital': source.get('capital', ''),
                        'city': source.get('city', ''),
                    }
            except (json.JSONDecodeError, IOError):
                continue
        return {}

    def _load_state_logit_metadata(self, state_dir: Path, capital: str) -> Dict[str, Any]:
        """Load top-logit metadata used by state warnings and filters."""
        graph_path = state_dir / "00 Graph Generation" / "graph.json"
        if not graph_path.exists():
            return {}

        try:
            with open(graph_path, 'r', encoding='utf-8') as f:
                graph = json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

        import re

        logits = []
        native_prob = 0
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
                target_token = match.group(1).strip() if match else clerp.strip().strip("'")

        logits.sort(key=lambda x: x['prob'], reverse=True)
        top_logits = logits[:5]
        capital_lower = capital.lower() if capital else ''
        capital_in_logits = any(
            token and len(token) > 1 and token.lower() in capital_lower
            for token in (logit.get('token', '') for logit in top_logits)
        )

        return {
            'logits': top_logits,
            'native_prob': native_prob,
            'target_token': target_token,
            'capital_is_top_logit': target_token.lower() in capital_lower if capital and target_token else False,
            'capital_in_logits': capital_in_logits,
        }

    def _get_state_logit_flags(self, slug: str, capital: str) -> Dict[str, Any]:
        """Return compact warning flags for the matrix state list."""
        state_dir = self._find_state_dir(slug)
        if not state_dir:
            return {}

        metadata = self._load_state_logit_metadata(state_dir, capital)
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
    
    def get_swap_detail(self, from_slug: str, to_slug: str) -> Optional[Dict[str, Any]]:
        """Load detailed swap result."""
        # Try by_source structure first
        by_source_path = self.swaps_dir / "by_source" / from_slug / f"to_{to_slug}.json"
        if by_source_path.exists():
            with open(by_source_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Enrich with Neuronpedia URLs
                data['source']['neuronpedia_url'] = self._get_neuronpedia_url(from_slug)
                data['target']['neuronpedia_url'] = self._get_neuronpedia_url(to_slug)
                return data
        
        # Try work directory
        work_path = self.swaps_dir / "work" / f"{from_slug}__to__{to_slug}.json"
        if work_path.exists():
            with open(work_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                data['source']['neuronpedia_url'] = self._get_neuronpedia_url(from_slug)
                data['target']['neuronpedia_url'] = self._get_neuronpedia_url(to_slug)
                return data
        
        return None
    
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
        self._matrix_cache = None
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
                    try:
                        with open(swap_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        if data.get('classification', {}).get('manually_edited'):
                            to_slug = swap_file.stem.replace("to_", "")
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
        
        aggregate = {
            'perfect_rate': perfect_count / total_swaps if total_swaps > 0 else 0,
            'state_correct_rate': state_correct_count / total_swaps if total_swaps > 0 else 0,
            'suppression_rate': suppressed_count / total_swaps if total_swaps > 0 else 0,
            'avg_tier': tier_sum / total_swaps if total_swaps > 0 else 0,
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
    
    def get_swap_features(self, from_slug: str, to_slug: str) -> Optional[Dict]:
        """
        Get intervention features for a swap.
        
        Loads from _swaps/work/{from_slug}__to__{to_slug}/features.json
        Returns structured data with ablated/amplified features grouped by layer.
        """
        swap_id = f"{from_slug}__to__{to_slug}"
        features_path = self.swaps_dir / "work" / swap_id / "features.json"
        
        if not features_path.exists():
            return None
        
        try:
            with open(features_path, 'r', encoding='utf-8') as f:
                raw_features = json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
        
        # Group features by type and layer
        ablated = []  # M < 0
        amplified = []  # M > 0
        layer_counts = {'ablated': {}, 'amplified': {}}
        
        for feat in raw_features:
            layer = feat.get('layer', 0)
            index = feat.get('index', 0)
            M = feat.get('M', 0)
            stored_activation = feat.get('stored_activation')
            
            # Build Neuronpedia link
            np_url = f"https://www.neuronpedia.org/gemma-2-2b/{layer}-clt-hp/{index}"
            
            feature_info = {
                'layer': layer,
                'index': index,
                'M': M,
                'stored_activation': stored_activation,
                'neuronpedia_url': np_url,
            }
            
            if M < 0:
                ablated.append(feature_info)
                layer_counts['ablated'][layer] = layer_counts['ablated'].get(layer, 0) + 1
            else:
                amplified.append(feature_info)
                layer_counts['amplified'][layer] = layer_counts['amplified'].get(layer, 0) + 1
        
        # Sort by layer
        ablated.sort(key=lambda x: (x['layer'], x['index']))
        amplified.sort(key=lambda x: (x['layer'], x['index']))
        
        return {
            'swap_id': swap_id,
            'ablated': ablated,
            'amplified': amplified,
            'layer_counts': layer_counts,
            'summary': {
                'ablate_count': len(ablated),
                'amplify_count': len(amplified),
                'total_count': len(ablated) + len(amplified),
            }
        }
    
    def get_state_profile(self, slug: str) -> Optional[Dict]:
        """
        Get comprehensive state profile with stats.
        
        Includes:
        - Native probability (target logit prob from graph)
        - Supernode/pinned feature counts
        - Feature count by layer
        - Attack score (avg tier when target - others steer to this state)
        - Defense score (avg tier when source - this state's prompt)
        - Wrong state rate
        - Capital city
        """
        # Find state directory
        state_dir = self._find_state_dir(slug)
        if not state_dir:
            return None
        
        state_name = self._slug_to_state_name(slug)
        profile = {
            'slug': slug,
            'state': state_name,
            'city': self._slug_to_city(slug),
            'capital': self._get_state_capital(state_name),
        }
        
        # Load manifest for Neuronpedia data
        manifest = self._load_manifest(state_dir)
        if manifest:
            np_data = manifest.get('neuronpedia', {})
            profile['supernodes'] = np_data.get('supernodes', 0)
            profile['pinned_nodes'] = np_data.get('pinned_nodes', 0)
            profile['neuronpedia_url'] = np_data.get('url', '')
        
        capital = profile.get('capital', '')
        profile.update(self._load_state_logit_metadata(state_dir, capital))
        
        # Load feature layer distribution
        features_path = state_dir / "00 Graph Generation" / "selected_features_with_nodes.json"
        if features_path.exists():
            try:
                with open(features_path, 'r', encoding='utf-8') as f:
                    features_data = json.load(f)
                features = features_data.get('features', [])
                profile['total_features'] = len(features)
                
                # Count by layer
                layer_counts = {}
                for feat in features:
                    layer = feat.get('layer', 0)
                    layer_counts[layer] = layer_counts.get(layer, 0) + 1
                profile['feature_layers'] = layer_counts
            except (json.JSONDecodeError, IOError):
                pass
        
        # Load state supernode features from node_grouping.csv
        grouping_path = state_dir / "02 Node Grouping" / "node_grouping.csv"
        if grouping_path.exists():
            try:
                state_concept = self._slug_to_state_name(slug).lower()
                supernode_features = []
                supernode_layer_counts = {}
                
                with open(grouping_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        supernode_name = row.get('supernode_name', '').lower()
                        # Match state name in supernode (e.g., "california", "texas")
                        if state_concept in supernode_name or supernode_name in state_concept:
                            layer = int(row.get('layer', 0))
                            supernode_features.append({
                                'layer': layer,
                                'feature': row.get('feature', ''),
                                'supernode_name': row.get('supernode_name', ''),
                            })
                            supernode_layer_counts[layer] = supernode_layer_counts.get(layer, 0) + 1
                
                profile['supernode_features'] = supernode_features
                profile['supernode_feature_count'] = len(supernode_features)
                profile['supernode_layer_counts'] = supernode_layer_counts
            except (IOError, ValueError):
                pass
        
        # Calculate attack/defense scores from matrix
        matrix = self.get_matrix()
        
        # Attack score: avg tier when this state is source (this state attacking others)
        attack_tiers = []
        if slug in matrix:
            for to_slug, tier in matrix[slug].items():
                if tier is not None and to_slug != slug:
                    attack_tiers.append(tier)
        profile['attack_avg'] = sum(attack_tiers) / len(attack_tiers) if attack_tiers else 0
        profile['attack_count'] = len(attack_tiers)
        # Success rate (T3+) when attacking
        attack_success = len([t for t in attack_tiers if t >= 3])
        profile['attack_success_rate'] = attack_success / len(attack_tiers) if attack_tiers else 0
        
        # Defense score: avg tier when this state is target (others attacking this state)
        defense_tiers = []
        wrong_state_count = 0
        for from_slug, targets in matrix.items():
            if from_slug != slug and slug in targets and targets[slug] is not None:
                tier = targets[slug]
                defense_tiers.append(tier)
                if tier == 2.5:
                    wrong_state_count += 1
        profile['defense_avg'] = sum(defense_tiers) / len(defense_tiers) if defense_tiers else 0
        profile['defense_count'] = len(defense_tiers)
        # Success rate (T3+) when being attacked (defense = others succeeded attacking this)
        defense_success = len([t for t in defense_tiers if t >= 3])
        profile['defense_success_rate'] = defense_success / len(defense_tiers) if defense_tiers else 0
        
        # Wrong state rate (T2.5) as target
        profile['wrong_state_rate'] = wrong_state_count / len(defense_tiers) if defense_tiers else 0
        profile['wrong_state_count'] = wrong_state_count
        
        # Token overlap flag
        overlap_slugs = [
            'colorado_colorado_springs', 'new_york_new_york_city',
            'virginia_virginia_beach', 'idaho_idaho_falls',
            'missouri_kansas_city', 'indiana_fort_wayne'
        ]
        profile['has_token_overlap'] = slug in overlap_slugs
        
        # Get swap summaries (just tier and basic info, not full outputs)
        profile['swaps_as_target'] = self._get_swap_summaries_as_target(slug)
        profile['swaps_as_source'] = self._get_swap_summaries_as_source(slug)
        
        return profile
    
    def _get_swap_summaries_as_target(self, slug: str) -> List[Dict]:
        """Get summary of swaps where this state is target (being attacked)."""
        matrix = self.get_matrix()
        states = self.get_states()
        state_map = {s['slug']: s for s in states}
        
        summaries = []
        for from_slug, targets in matrix.items():
            if from_slug != slug and slug in targets and targets[slug] is not None:
                tier = targets[slug]
                from_state = state_map.get(from_slug, {})
                summaries.append({
                    'from_slug': from_slug,
                    'from_state': from_state.get('state', from_slug),
                    'from_city': from_state.get('city', ''),
                    'tier': tier,
                })
        
        # Sort by tier descending (best results first)
        summaries.sort(key=lambda x: -x['tier'])
        return summaries
    
    def _get_swap_summaries_as_source(self, slug: str) -> List[Dict]:
        """Get summary of swaps where this state is source (defending)."""
        matrix = self.get_matrix()
        states = self.get_states()
        state_map = {s['slug']: s for s in states}
        
        summaries = []
        if slug in matrix:
            for to_slug, tier in matrix[slug].items():
                if to_slug != slug and tier is not None:
                    to_state = state_map.get(to_slug, {})
                    summaries.append({
                        'to_slug': to_slug,
                        'to_state': to_state.get('state', to_slug),
                        'to_city': to_state.get('city', ''),
                        'tier': tier,
                    })
        
        # Sort by tier descending (best results first)
        summaries.sort(key=lambda x: -x['tier'])
        return summaries
    
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
        
        # Extract state and city from slug for priority matching
        state_name = self._slug_to_state_name(slug)
        city_name = self._slug_to_city(slug)
        capital_name = self._get_state_capital(state_name)
        
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

