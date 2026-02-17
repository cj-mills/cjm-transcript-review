"""Demo application for cjm-transcript-review library.

Demonstrates the Review & Commit step with card stack navigation,
audio playback, and graph commit functionality.

Run with: python demo_app.py
"""

from typing import List, Dict, Any, Callable, Tuple
from functools import wraps
import asyncio

from fasthtml.common import (
    fast_app, Div, H1, H2, P, Span, Button, Input, Script,
    APIRouter, Details, Summary,
)

# DaisyUI components
from cjm_fasthtml_daisyui.core.resources import get_daisyui_headers
from cjm_fasthtml_daisyui.core.testing import create_theme_persistence_script
from cjm_fasthtml_daisyui.components.data_display.badge import badge, badge_styles, badge_sizes
from cjm_fasthtml_daisyui.utilities.semantic_colors import bg_dui, text_dui, border_dui
from cjm_fasthtml_daisyui.utilities.border_radius import border_radius

# Tailwind utilities
from cjm_fasthtml_tailwind.utilities.spacing import p, m
from cjm_fasthtml_tailwind.utilities.sizing import w, h, min_h, container, max_w
from cjm_fasthtml_tailwind.utilities.typography import font_size, font_weight, text_align
from cjm_fasthtml_tailwind.utilities.layout import overflow
from cjm_fasthtml_tailwind.utilities.borders import border
from cjm_fasthtml_tailwind.utilities.flexbox_and_grid import (
    flex_display, flex_direction, justify, items, gap, grow
)
from cjm_fasthtml_tailwind.core.base import combine_classes

# App core
from cjm_fasthtml_app_core.core.routing import register_routes
from cjm_fasthtml_app_core.core.htmx import handle_htmx_request

# State store
from cjm_workflow_state.state_store import SQLiteWorkflowStateStore

# Plugin system
from cjm_plugin_system.core.manager import PluginManager
from cjm_plugin_system.core.scheduling import SafetyScheduler

# Review library imports
from cjm_transcript_review.models import ReviewStepState, WorkingDocument
from cjm_transcript_review.html_ids import ReviewHtmlIds
from cjm_transcript_review.services.graph import GraphService


# =============================================================================
# Demo HTML IDs
# =============================================================================

class DemoHtmlIds:
    """HTML IDs for demo app layout."""
    CONTAINER = "review-demo-container"
    CONTENT = "review-demo-content"


# =============================================================================
# Demo Page Renderer
# =============================================================================

def render_demo_page() -> Callable:
    """Create the demo page content factory."""

    def page_content():
        """Render the demo page with placeholder content."""
        return Div(
            # Header
            Div(
                H1("Review & Commit Demo",
                   cls=combine_classes(font_size._3xl, font_weight.bold)),
                P(
                    "Phase 1: Library imports verified. Future phases will add review UI.",
                    cls=combine_classes(text_dui.base_content.opacity(70), m.b(4))
                ),
            ),

            # Content area
            Div(
                Div(
                    P("ReviewStepState:", cls=font_weight.semibold),
                    P(f"  {ReviewStepState.__name__}", cls=text_dui.base_content.opacity(70)),
                    cls=m.b(2)
                ),
                Div(
                    P("WorkingDocument:", cls=font_weight.semibold),
                    P(f"  {WorkingDocument.__name__}", cls=text_dui.base_content.opacity(70)),
                    cls=m.b(2)
                ),
                Div(
                    P("ReviewHtmlIds:", cls=font_weight.semibold),
                    P(f"  {ReviewHtmlIds.__name__}", cls=text_dui.base_content.opacity(70)),
                    cls=m.b(2)
                ),
                Div(
                    P("GraphService:", cls=font_weight.semibold),
                    P(f"  {GraphService.__name__}", cls=text_dui.base_content.opacity(70)),
                    cls=m.b(2)
                ),
                id=DemoHtmlIds.CONTENT,
                cls=combine_classes(
                    p(4), bg_dui.base_200, border_radius.box,
                    border_dui.base_300, border(1),
                )
            ),

            id=DemoHtmlIds.CONTAINER,
            cls=combine_classes(
                container, max_w._4xl, m.x.auto,
                h.full,
                flex_display, flex_direction.col,
                p(4),
            )
        )

    return page_content


# =============================================================================
# Main Application
# =============================================================================

def main():
    """Initialize the review demo and start the server."""
    print("\n" + "=" * 70)
    print("Initializing cjm-transcript-review Demo")
    print("=" * 70)

    # Initialize FastHTML app
    app, rt = fast_app(
        pico=False,
        hdrs=[*get_daisyui_headers(), create_theme_persistence_script()],
        title="Review Demo",
        htmlkw={'data-theme': 'light'},
        secret_key="demo-secret-key"
    )

    router = APIRouter(prefix="")

    # -------------------------------------------------------------------------
    # Set up state store
    # -------------------------------------------------------------------------
    import tempfile
    from pathlib import Path

    temp_db = Path(tempfile.gettempdir()) / "cjm_transcript_review_demo_state.db"
    state_store = SQLiteWorkflowStateStore(temp_db)
    workflow_id = "review-demo"

    print(f"  State store: {temp_db}")

    # -------------------------------------------------------------------------
    # Set up plugin manager
    # -------------------------------------------------------------------------
    print("\n[Plugin System]")
    plugin_manager = PluginManager(scheduler=SafetyScheduler())

    # Discover plugins from JSON manifests
    plugin_manager.discover_manifests()

    # Check for graph plugin
    graph_plugin_name = "cjm-graph-plugin-sqlite"
    graph_meta = plugin_manager.get_discovered_meta(graph_plugin_name)
    if graph_meta:
        print(f"  {graph_plugin_name}: discovered")
    else:
        print(f"  {graph_plugin_name}: not found")

    # Create graph service (plugin loaded on-demand)
    graph_service = GraphService(plugin_manager, graph_plugin_name)

    # -------------------------------------------------------------------------
    # Page routes
    # -------------------------------------------------------------------------
    page_content = render_demo_page()

    @router
    def index(request, sess):
        """Demo homepage."""
        return handle_htmx_request(request, page_content)

    # -------------------------------------------------------------------------
    # Register routes
    # -------------------------------------------------------------------------
    register_routes(app, router)

    # Debug output
    print("\n" + "=" * 70)
    print("Registered Routes:")
    print("=" * 70)
    for route in app.routes:
        if hasattr(route, 'path'):
            print(f"  {route.path}")
    print("=" * 70)
    print("Demo App Ready!")
    print("=" * 70 + "\n")

    return app


if __name__ == "__main__":
    import uvicorn
    import webbrowser
    import threading

    app = main()

    port = 5033
    host = "0.0.0.0"
    display_host = 'localhost' if host in ['0.0.0.0', '127.0.0.1'] else host

    print(f"Server: http://{display_host}:{port}")
    print()

    timer = threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}"))
    timer.daemon = True
    timer.start()

    uvicorn.run(app, host=host, port=port)
