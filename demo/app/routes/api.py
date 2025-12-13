"""
API routes for JSON data endpoints
"""
import json
from fasthtml.common import Response
from starlette.requests import Request


def api_routes(app, rt, data_loader, annotate_mode: bool = False):
    """Register API routes."""
    
    @rt("/api/config")
    def api_config():
        """Return app configuration including annotation mode."""
        return Response(
            content=json.dumps({
                "annotate_mode": annotate_mode,
                "version": "1.0.0",
            }),
            media_type="application/json"
        )
    
    @rt("/api/matrix")
    def api_matrix():
        """Return tier matrix as JSON."""
        matrix = data_loader.get_matrix()
        return Response(
            content=json.dumps(matrix),
            media_type="application/json"
        )
    
    @rt("/api/states")
    def api_states():
        """Return all states with metadata."""
        states = data_loader.get_states()
        return Response(
            content=json.dumps(states),
            media_type="application/json"
        )
    
    @rt("/api/stats")
    def api_stats():
        """Return aggregate statistics."""
        stats = data_loader.get_stats()
        return Response(
            content=json.dumps(stats),
            media_type="application/json"
        )
    
    @rt("/api/swap/{from_slug}/{to_slug}")
    def api_swap(from_slug: str, to_slug: str):
        """Return detailed swap result."""
        swap = data_loader.get_swap_detail(from_slug, to_slug)
        if swap is None:
            return Response(
                content=json.dumps({"error": "Swap not found"}),
                media_type="application/json",
                status_code=404
            )
        return Response(
            content=json.dumps(swap),
            media_type="application/json"
        )
    
    @rt("/api/state/{slug}")
    def api_state(slug: str):
        """Return state profile data."""
        states = data_loader.get_states()
        state = next((s for s in states if s['slug'] == slug), None)
        
        if state is None:
            return Response(
                content=json.dumps({"error": "State not found"}),
                media_type="application/json",
                status_code=404
            )
        
        # Get swaps where this state is source and target
        matrix = data_loader.get_matrix()
        as_source = matrix.get(slug, {})
        as_target = {k: v.get(slug) for k, v in matrix.items() if k != slug and v.get(slug) is not None}
        
        return Response(
            content=json.dumps({
                **state,
                'swaps_as_source': as_source,
                'swaps_as_target': as_target,
            }),
            media_type="application/json"
        )
    
    @rt("/api/state/{slug}/profile")
    def api_state_profile(slug: str):
        """
        Return comprehensive state profile with stats.
        
        Includes native probability, supernode count, feature layers,
        attack/defense scores, and token overlap flag.
        """
        profile = data_loader.get_state_profile(slug)
        if profile is None:
            return Response(
                content=json.dumps({"error": "State not found"}),
                media_type="application/json",
                status_code=404
            )
        return Response(
            content=json.dumps(profile),
            media_type="application/json"
        )
    
    @rt("/api/analysis")
    def api_analysis():
        """Return full analysis data."""
        analysis = data_loader.get_analysis()
        return Response(
            content=json.dumps(analysis),
            media_type="application/json"
        )
    
    @rt("/api/refresh")
    def api_refresh():
        """Clear caches and reload data."""
        data_loader._matrix_cache = None
        data_loader._states_cache = None
        data_loader._analysis_cache = None
        data_loader._stats_cache = None
        return Response(
            content=json.dumps({"status": "ok", "message": "Cache cleared"}),
            media_type="application/json"
        )
    
    @rt("/api/annotate/{from_slug}/{to_slug}", methods=["POST"])
    async def api_annotate(request: Request, from_slug: str, to_slug: str):
        """
        Save annotation for a swap (tier and/or notes).
        
        Request body (JSON):
            tier: int (1-5) - optional
            notes: str - optional
        
        Returns updated swap data and refreshed stats.
        """
        if not annotate_mode:
            return Response(
                content=json.dumps({"error": "Annotation mode not enabled"}),
                media_type="application/json",
                status_code=403
            )
        
        try:
            body = await request.json()
        except Exception:
            return Response(
                content=json.dumps({"error": "Invalid JSON body"}),
                media_type="application/json",
                status_code=400
            )
        
        tier = body.get('tier')
        notes = body.get('notes')
        
        # Validate tier if provided (supports 1, 2, 2.5, 3, 4, 5)
        if tier is not None:
            try:
                tier = float(tier)
                valid_tiers = [1, 2, 2.5, 3, 4, 5]
                if tier not in valid_tiers:
                    raise ValueError("Tier must be 1, 2, 2.5, 3, 4, or 5")
            except (ValueError, TypeError) as e:
                return Response(
                    content=json.dumps({"error": f"Invalid tier: {e}"}),
                    media_type="application/json",
                    status_code=400
                )
        
        try:
            result = data_loader.save_annotation(from_slug, to_slug, tier=tier, notes=notes)
            return Response(
                content=json.dumps(result),
                media_type="application/json"
            )
        except FileNotFoundError as e:
            return Response(
                content=json.dumps({"error": str(e)}),
                media_type="application/json",
                status_code=404
            )
        except Exception as e:
            return Response(
                content=json.dumps({"error": f"Failed to save: {e}"}),
                media_type="application/json",
                status_code=500
            )
    
    @rt("/api/annotated")
    def api_annotated():
        """Return list of all manually annotated swaps."""
        annotated = data_loader.get_annotated_swaps()
        return Response(
            content=json.dumps(annotated),
            media_type="application/json"
        )
    
    @rt("/api/swap/{from_slug}/{to_slug}/features")
    def api_swap_features(from_slug: str, to_slug: str):
        """
        Return intervention features for a swap.
        
        Returns list of features grouped by type (ablate/amplify) and layer.
        Each feature includes Neuronpedia link.
        """
        features = data_loader.get_swap_features(from_slug, to_slug)
        if features is None:
            return Response(
                content=json.dumps({"error": "Features not found", "features": []}),
                media_type="application/json",
                status_code=404
            )
        return Response(
            content=json.dumps(features),
            media_type="application/json"
        )
    
    @rt("/api/state/{slug}/subgraph-url")
    def api_subgraph_url(slug: str, request: Request):
        """
        Generate a simplified subgraph URL for a state.
        
        Query params:
            max_features: int (default 100) - max features to include
            max_url_length: int (default 4000) - max URL length before truncation
            
        Returns URL with:
        - All embeddings (input tokens)
        - Output logits (capital prediction)
        - State/city/capital related features (priority)
        - Top features by node_influence
        - Supernode groupings
        """
        # Mode:
        # - auto (default): prefer complete uploaded subgraph if available, else fallback to simplified
        # - complete: only return complete uploaded subgraph URL
        # - simplified: only return simplified pinnedIds/supernodes URL
        mode = (request.query_params.get("mode", "simplified") or "simplified").lower()
        if mode not in ("auto", "complete", "simplified"):
            mode = "simplified"

        # Prefer complete subgraph URL (uploaded subgraph_id) when available
        if mode in ("auto", "complete"):
            complete = data_loader.get_complete_subgraph_url(slug)
            if complete is not None:
                return Response(
                    content=json.dumps(complete),
                    media_type="application/json"
                )
            if mode == "complete":
                return Response(
                    content=json.dumps({"error": "Complete subgraph data not found"}),
                    media_type="application/json",
                    status_code=404
                )

        # Parse query params
        max_features = 100
        max_url_length = 4000
        
        try:
            if 'max_features' in request.query_params:
                max_features = int(request.query_params['max_features'])
                max_features = min(max(max_features, 20), 200)  # Clamp 20-200
            if 'max_url_length' in request.query_params:
                max_url_length = int(request.query_params['max_url_length'])
                max_url_length = min(max(max_url_length, 2000), 8000)  # Clamp 2000-8000
        except (ValueError, TypeError):
            pass
        
        result = data_loader.get_simplified_subgraph_url(
            slug, 
            max_features=max_features,
            max_url_length=max_url_length
        )
        
        if result is None:
            return Response(
                content=json.dumps({"error": "Subgraph data not found"}),
                media_type="application/json",
                status_code=404
            )

        # Tag response mode for callers (front-end ignores it, but it's useful for debugging)
        result["mode"] = "simplified"
        
        return Response(
            content=json.dumps(result),
            media_type="application/json"
        )

