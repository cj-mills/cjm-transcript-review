"""Demo application for cjm-transcript-review library.

Demonstrates the Review card stack with navigation, audio playback,
keyboard navigation, and commit to graph. Works standalone for testing.

Run with: python demo_app.py
"""

from typing import List, Dict, Any, Callable
from pathlib import Path
import tempfile
import json

from fasthtml.common import (
    fast_app, Div, H1, P, Span, Button,
    APIRouter, FileResponse,
)

# Plugin system
from cjm_plugin_system.core.manager import PluginManager
from cjm_plugin_system.core.scheduling import SafetyScheduler

# DaisyUI components
from cjm_fasthtml_daisyui.core.resources import get_daisyui_headers
from cjm_fasthtml_daisyui.core.testing import create_theme_persistence_script
from cjm_fasthtml_daisyui.components.actions.button import btn, btn_colors, btn_sizes
from cjm_fasthtml_daisyui.components.data_display.badge import badge, badge_styles, badge_sizes
from cjm_fasthtml_daisyui.utilities.semantic_colors import bg_dui, text_dui, border_dui
from cjm_fasthtml_daisyui.utilities.border_radius import border_radius

# Tailwind utilities
from cjm_fasthtml_tailwind.utilities.spacing import p, m
from cjm_fasthtml_tailwind.utilities.sizing import w, h, min_h, container, max_w
from cjm_fasthtml_tailwind.utilities.typography import font_size, font_weight, uppercase, tracking
from cjm_fasthtml_tailwind.utilities.layout import overflow
from cjm_fasthtml_tailwind.utilities.borders import border
from cjm_fasthtml_tailwind.utilities.effects import ring
from cjm_fasthtml_tailwind.utilities.transitions_and_animation import transition, duration
from cjm_fasthtml_tailwind.utilities.flexbox_and_grid import (
    flex_display, flex_direction, justify, items, gap, grow
)
from cjm_fasthtml_tailwind.core.base import combine_classes

# App core
from cjm_fasthtml_app_core.core.routing import register_routes
from cjm_fasthtml_app_core.core.htmx import handle_htmx_request

# Interactions library
from cjm_fasthtml_interactions.core.state_store import get_session_id

# State store
from cjm_workflow_state.state_store import SQLiteWorkflowStateStore

# Card stack library
from cjm_fasthtml_card_stack.components.controls import render_width_slider
from cjm_fasthtml_card_stack.components.states import render_loading_state
from cjm_fasthtml_card_stack.core.constants import DEFAULT_VISIBLE_COUNT, DEFAULT_CARD_WIDTH

# Segmentation and alignment models
from cjm_transcript_segmentation.models import TextSegment
from cjm_transcript_vad_align.models import VADChunk

# Lucide icons
from cjm_fasthtml_lucide_icons.factory import lucide_icon

# Review library imports
from cjm_transcript_review.models import ReviewUrls
from cjm_transcript_review.html_ids import ReviewHtmlIds
from cjm_transcript_review.services.graph import GraphService
from cjm_transcript_review.components.card_stack_config import (
    REVIEW_CS_CONFIG, REVIEW_CS_IDS, REVIEW_CS_BTN_IDS,
)
from cjm_transcript_review.components.review_card import AssembledSegment
from cjm_transcript_review.components.step_renderer import (
    render_review_step, render_review_toolbar, render_review_footer,
    render_review_content, render_review_stats, render_review_keyboard_hints,
)
from cjm_transcript_review.routes.init import init_review_routers
from cjm_transcript_review.routes.core import (
    _load_review_context, _get_assembled_segments, _update_review_state,
)


# =============================================================================
# Demo HTML IDs
# =============================================================================

class DemoHtmlIds:
    """HTML IDs for demo app layout."""
    CONTAINER = "review-demo-container"
    COLUMN = "review-demo-column"
    COLUMN_HEADER = "review-demo-column-header"
    SHARED_TOOLBAR = "review-demo-toolbar"
    SHARED_CONTROLS = "review-demo-controls"
    SHARED_FOOTER = "review-demo-footer"
    MINI_STATS = "review-demo-mini-stats"
    KEYBOARD_SYSTEM = "review-demo-kb-system"
    SHARED_HINTS = "review-demo-hints"
    COMMIT_ALERT_CONTAINER = "commit-alert-container"


# =============================================================================
# Test Data from JSON
# =============================================================================

# Path to test state JSON file
TEST_STATE_JSON = Path(__file__).parent / "test_files" / "state_json.json"


def load_test_state() -> Dict[str, Any]:
    """Load test state from JSON file."""
    with open(TEST_STATE_JSON, "r") as f:
        return json.load(f)


# =============================================================================
# Demo Init Handler
# =============================================================================

def create_demo_init_handler(
    state_store: SQLiteWorkflowStateStore,
    workflow_id: str,
    urls: ReviewUrls,
):
    """Create init handler that loads test data from JSON and renders the step."""

    def init_handler(request, sess):
        """Initialize review with test data from JSON file."""
        session_id = get_session_id(sess)

        # Load test state from JSON
        test_state = load_test_state()

        # Initialize workflow state with test data
        workflow_state = state_store.get_state(workflow_id, session_id)

        # Copy step_states from test data
        workflow_state["step_states"] = test_state.get("step_states", {})

        # Set up review state with defaults (reset focused_index to 0 for demo)
        if "review" not in workflow_state["step_states"]:
            workflow_state["step_states"]["review"] = {}

        workflow_state["step_states"]["review"]["focused_index"] = 0
        workflow_state["step_states"]["review"]["visible_count"] = DEFAULT_VISIBLE_COUNT
        workflow_state["step_states"]["review"]["is_auto_mode"] = False
        workflow_state["step_states"]["review"]["card_width"] = DEFAULT_CARD_WIDTH
        workflow_state["step_states"]["review"]["playback_speed"] = 1.0
        workflow_state["step_states"]["review"]["auto_navigate"] = False

        state_store.update_state(workflow_id, session_id, workflow_state)

        # Load context and render
        ctx = _load_review_context(state_store, workflow_id, session_id)
        assembled = _get_assembled_segments(ctx)

        # Render main content (keyboard system is managed internally)
        content = render_review_content(
            assembled=assembled,
            focused_index=ctx.focused_index,
            visible_count=ctx.visible_count,
            card_width=ctx.card_width,
            urls=urls,
            media_path=ctx.media_path,
        )

        # OOB updates for chrome
        toolbar_oob = Div(
            render_review_toolbar(
                ctx.visible_count, ctx.is_auto_mode,
                playback_speed=ctx.playback_speed,
                auto_navigate=ctx.auto_navigate,
                urls=urls,
            ),
            id=DemoHtmlIds.SHARED_TOOLBAR,
            hx_swap_oob="innerHTML"
        )

        controls_oob = Div(
            render_width_slider(REVIEW_CS_CONFIG, REVIEW_CS_IDS, card_width=ctx.card_width),
            id=DemoHtmlIds.SHARED_CONTROLS,
            hx_swap_oob="innerHTML"
        )

        footer_oob = Div(
            render_review_footer(assembled, ctx.focused_index),
            id=DemoHtmlIds.SHARED_FOOTER,
            hx_swap_oob="innerHTML"
        )

        # Hints OOB (use library's hints function)
        hints_oob = Div(
            render_review_keyboard_hints(),
            id=DemoHtmlIds.SHARED_HINTS,
            hx_swap_oob="innerHTML"
        )

        # Mini-stats badge
        total = len(assembled)
        total_dur = sum(a.vad_chunk.duration for a in assembled)
        mini_stats_oob = Span(
            f"{total} segments \u00b7 {total_dur:.1f}s",
            id=DemoHtmlIds.MINI_STATS,
            cls=combine_classes(badge, badge_styles.ghost, badge_sizes.sm),
            hx_swap_oob="true",
        )

        return (content, toolbar_oob, controls_oob, footer_oob, hints_oob, mini_stats_oob)

    return init_handler


# =============================================================================
# Demo Page Renderer
# =============================================================================

def render_demo_page(
    urls: ReviewUrls,
    init_url: str,
) -> Callable:
    """Create the demo page content factory."""

    def page_content():
        """Render the demo page with card stack column."""

        # Column header
        header = Div(
            Span(
                "Review",
                cls=combine_classes(
                    font_size.sm, font_weight.bold,
                    uppercase, tracking.wide,
                    text_dui.base_content.opacity(50)
                )
            ),
            Span(
                "--",
                id=DemoHtmlIds.MINI_STATS,
                cls=combine_classes(badge, badge_styles.ghost, badge_sizes.sm)
            ),
            id=DemoHtmlIds.COLUMN_HEADER,
            cls=combine_classes(
                flex_display, justify.between, items.center,
                p(3), bg_dui.base_200,
                border_dui.base_300, border.b()
            )
        )

        # Column content (loading state with auto-trigger)
        content = Div(
            render_loading_state(REVIEW_CS_IDS, message="Loading review data..."),
            Div(
                hx_post=init_url,
                hx_trigger="load",
                hx_target=f"#{ReviewHtmlIds.REVIEW_CONTENT}",
                hx_swap="outerHTML"
            ),
            id=ReviewHtmlIds.REVIEW_CONTENT,
            cls=combine_classes(grow(), overflow.hidden, flex_display, flex_direction.col, p(4))
        )

        # Column
        column_cls = combine_classes(
            w.full, max_w._4xl, m.x.auto,
            min_h(0),
            flex_display, flex_direction.col,
            bg_dui.base_100, border_dui.base_300, border(1),
            border_radius.box,
            overflow.hidden,
            transition.all, duration._200,
            ring(1), "ring-primary",
        )

        column = Div(
            header,
            content,
            id=DemoHtmlIds.COLUMN,
            cls=column_cls
        )

        # Placeholder chrome
        hints = Div(
            P("Keyboard hints will appear here after initialization.",
              cls=combine_classes(font_size.sm, text_dui.base_content.opacity(50))),
            id=DemoHtmlIds.SHARED_HINTS,
            cls=str(p(2))
        )

        toolbar = Div(
            P("Toolbar will appear here after initialization.",
              cls=combine_classes(font_size.sm, text_dui.base_content.opacity(50))),
            id=DemoHtmlIds.SHARED_TOOLBAR,
            cls=str(p(2))
        )

        controls = Div(
            P("Width controls will appear here after initialization.",
              cls=combine_classes(font_size.sm, text_dui.base_content.opacity(50))),
            id=DemoHtmlIds.SHARED_CONTROLS,
            cls=str(p(2))
        )

        footer = Div(
            P("Footer with progress will appear here after initialization.",
              cls=combine_classes(font_size.sm, text_dui.base_content.opacity(50))),
            id=DemoHtmlIds.SHARED_FOOTER,
            cls=combine_classes(
                p(1), bg_dui.base_100,
                border_dui.base_300, border.t(),
                flex_display, justify.center, items.center
            )
        )

        # Commit button (only shown if commit URL is available)
        commit_button = None
        if urls.commit:
            commit_button = Button(
                lucide_icon("database"),
                Span("Commit to Graph", cls=str(m.l(2))),
                cls=combine_classes(btn, btn_colors.success, btn_sizes.sm, flex_display, items.center),
                hx_post=urls.commit,
                hx_swap="none",
            )

        # Alert container for commit feedback
        alert_container = Div(id=DemoHtmlIds.COMMIT_ALERT_CONTAINER)

        return Div(
            # Header with commit button
            Div(
                H1("Review Demo",
                   cls=combine_classes(font_size._3xl, font_weight.bold)),
                commit_button,
                cls=combine_classes(flex_display, justify.between, items.center)
            ),
            P(
                "Review assembled segments with timing and source info. Navigate with Up/Down arrows. Audio plays on navigation.",
                cls=combine_classes(text_dui.base_content.opacity(70), m.b(2))
            ),

            # Alert container (for commit feedback)
            alert_container,

            # Shared chrome
            hints,
            toolbar,
            controls,

            # Content area
            Div(
                column,
                cls=combine_classes(
                    grow(),
                    min_h(0),
                    flex_display,
                    flex_direction.col,
                    overflow.hidden,
                    p(1),
                )
            ),

            # Footer
            footer,

            id=DemoHtmlIds.CONTAINER,
            cls=combine_classes(
                container, max_w._5xl, m.x.auto,
                h.full,
                flex_display, flex_direction.col,
                p(4), p.x(2), p.b(0)
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
    temp_db = Path(tempfile.gettempdir()) / "cjm_transcript_review_demo_state.db"
    state_store = SQLiteWorkflowStateStore(temp_db)
    workflow_id = "review-demo"

    print(f"  State store: {temp_db}")
    print(f"  Test state JSON: {TEST_STATE_JSON}")

    # -------------------------------------------------------------------------
    # Set up plugin manager and graph service
    # -------------------------------------------------------------------------
    print("\n[Plugin System]")

    # Calculate project root from demo_app.py location
    project_root = Path(__file__).parent
    manifests_dir = project_root / ".cjm" / "manifests"

    plugin_manager = PluginManager(
        scheduler=SafetyScheduler(),
        search_paths=[manifests_dir]
    )
    plugin_manager.discover_manifests()

    # Load the graph plugin
    graph_plugin_name = "cjm-graph-plugin-sqlite"
    graph_meta = plugin_manager.get_discovered_meta(graph_plugin_name)
    graph_service = None

    if graph_meta:
        try:
            success = plugin_manager.load_plugin(graph_meta, {
                "db_path": graph_meta.manifest.get("db_path")
            })
            status = "loaded" if success else "failed"
            print(f"  {graph_plugin_name}: {status}")

            if success:
                graph_service = GraphService(plugin_manager, graph_plugin_name)
        except Exception as e:
            print(f"  {graph_plugin_name}: error - {e}")
    else:
        print(f"  {graph_plugin_name}: not found (commit disabled)")

    # -------------------------------------------------------------------------
    # Audio serving route
    # -------------------------------------------------------------------------
    audio_router = APIRouter(prefix="/audio")

    @audio_router
    def audio_src(path: str = None):
        """Serve audio file for Web Audio API playback."""
        if path and Path(path).exists():
            return FileResponse(path, media_type="audio/mpeg")
        from fasthtml.common import Response
        return Response(status_code=404, content="Audio file not found")

    audio_src_url = audio_src.to()

    # -------------------------------------------------------------------------
    # Set up review routes
    # -------------------------------------------------------------------------
    review_routers, review_urls, review_routes = init_review_routers(
        state_store=state_store,
        workflow_id=workflow_id,
        prefix="/review",
        audio_src_url=audio_src_url,
        graph_service=graph_service,
        alert_container_id=DemoHtmlIds.COMMIT_ALERT_CONTAINER,
    )

    # Create init handler
    init_router = APIRouter(prefix="/review")

    init_handler = create_demo_init_handler(state_store, workflow_id, review_urls)

    @init_router
    def init(request, sess):
        """Initialize review with test data."""
        return init_handler(request, sess)

    init_url = init.to()

    # -------------------------------------------------------------------------
    # Page routes
    # -------------------------------------------------------------------------
    page_content = render_demo_page(review_urls, init_url)

    @router
    def index(request, sess):
        """Demo homepage."""
        return handle_htmx_request(request, page_content)

    # -------------------------------------------------------------------------
    # Register routes
    # -------------------------------------------------------------------------
    register_routes(app, router, audio_router, init_router, *review_routers)

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
    print("Controls:")
    print("  Arrow Up/Down     - Navigate segments (auto-plays audio)")
    print("  Space             - Replay current segment")
    print("  Ctrl+Up/Down      - Page up/down")
    print("  Ctrl+Shift+Up     - Jump to first segment")
    print("  Ctrl+Shift+Down   - Jump to last segment")
    print("  [ / ]             - Adjust viewport width")
    print()
    print("Audio Controls (in toolbar):")
    print("  Speed selector    - Change playback speed (0.5x to 3x)")
    print("  Auto toggle       - Auto-advance to next segment on completion")
    print()

    timer = threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}"))
    timer.daemon = True
    timer.start()

    uvicorn.run(app, host=host, port=port)
