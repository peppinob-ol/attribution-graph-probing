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

