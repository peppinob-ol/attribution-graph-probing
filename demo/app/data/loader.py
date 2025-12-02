"""
Data loader for swap experiment results.

Reads from output/usa_states_batch/ directory structure:
- _swaps/_matrix.csv - Tier matrix
- _swaps/_analysis_v3/*.json - Analysis data
- _swaps/by_source/*/to_*.json - Swap details
- */manifest.json - Neuronpedia URLs
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import csv
from functools import lru_cache


class DataLoader:
    """Load and cache swap experiment data."""
    
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.swaps_dir = self.data_dir / "_swaps"
        self._matrix_cache: Optional[Dict] = None
        self._states_cache: Optional[List[Dict]] = None
        self._analysis_cache: Optional[Dict] = None
        self._stats_cache: Optional[Dict] = None
    
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
                
                states.append({
                    'slug': slug,
                    'state': state_info.get('state', state_name),
                    'capital': state_info.get('capital', ''),
                    'city': state_info.get('city', self._slug_to_city(slug)),
                    'abbr': self._state_to_abbr(state_info.get('state', state_name)),
                    'archetype': arch_data.get('archetype', 'Unknown'),
                    'native_prob': arch_data.get('native_prob', 0),
                    'supernodes': arch_data.get('supernodes', 0),
                    'src_tier': arch_data.get('src_tier', 0),
                    'tgt_tier': arch_data.get('tgt_tier', 0),
                    'neuronpedia_url': neuronpedia_url,
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

