"""PlaceGuard Streamlit Dashboard.

A premium dark-theme dashboard for VOYGR's place validation system.

Features:
    - Input box for natural language queries or LLM JSON
    - Animated "Validate" button with loading state
    - Rich result card: status, confidence, issues, enriched data
    - Recent validations table
    - Benchmark scenario gallery sidebar
    - Real-time reasoning chain display
"""

import json
import time
from datetime import datetime
from typing import Optional

import httpx
import streamlit as st

# ---------------------------------------------------------------------------
# Page Configuration — must be first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="PlaceGuard | VOYGR",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE_URL = "http://localhost:8000"

# ---------------------------------------------------------------------------
# Custom CSS: dark theme + YC-level premium styling
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* === Base === */
    :root {
        --bg-primary:    #0d0d0f;
        --bg-secondary:  #16161a;
        --bg-card:       #1e1e24;
        --bg-card-hover: #26262e;
        --accent-blue:   #4f8ef7;
        --accent-green:  #2de08a;
        --accent-red:    #f74f4f;
        --accent-yellow: #f7d24f;
        --accent-purple: #a259ff;
        --text-primary:  #eeeef0;
        --text-muted:    #8a8a9a;
        --border:        #2a2a36;
        --radius:        12px;
    }

    html, body, [data-testid="stAppViewContainer"] {
        background-color: var(--bg-primary) !important;
        color: var(--text-primary);
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
    }

    /* Hide Streamlit chrome */
    #MainMenu, footer, header { visibility: hidden; }
    [data-testid="stSidebar"] { background-color: var(--bg-secondary) !important; }
    [data-testid="stSidebar"] * { color: var(--text-primary) !important; }

    /* === Cards === */
    .pg-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 24px;
        margin-bottom: 16px;
        transition: background 0.2s;
    }
    .pg-card:hover { background: var(--bg-card-hover); }

    /* === Status badges === */
    .badge-valid {
        background: rgba(45, 224, 138, 0.15);
        color: var(--accent-green);
        border: 1px solid rgba(45, 224, 138, 0.35);
        padding: 4px 14px;
        border-radius: 999px;
        font-size: 13px;
        font-weight: 600;
        display: inline-block;
    }
    .badge-invalid {
        background: rgba(247, 79, 79, 0.15);
        color: var(--accent-red);
        border: 1px solid rgba(247, 79, 79, 0.35);
        padding: 4px 14px;
        border-radius: 999px;
        font-size: 13px;
        font-weight: 600;
        display: inline-block;
    }
    .badge-uncertain {
        background: rgba(247, 210, 79, 0.15);
        color: var(--accent-yellow);
        border: 1px solid rgba(247, 210, 79, 0.35);
        padding: 4px 14px;
        border-radius: 999px;
        font-size: 13px;
        font-weight: 600;
        display: inline-block;
    }

    /* === Confidence bar === */
    .confidence-bar-bg {
        background: var(--bg-primary);
        border-radius: 999px;
        height: 8px;
        width: 100%;
        margin-top: 8px;
    }

    /* === Metric cells === */
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 12px;
        margin: 16px 0;
    }
    .metric-cell {
        background: var(--bg-secondary);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 14px 16px;
        text-align: center;
    }
    .metric-cell .val {
        font-size: 22px;
        font-weight: 700;
        margin: 4px 0;
    }
    .metric-cell .lbl {
        font-size: 11px;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }

    /* === Reasoning timeline === */
    .reasoning-item {
        border-left: 2px solid var(--accent-blue);
        padding: 4px 12px;
        margin-bottom: 8px;
        font-size: 13px;
        color: var(--text-muted);
    }

    /* === Issue chips === */
    .issue-error {
        background: rgba(247, 79, 79, 0.12);
        border: 1px solid rgba(247, 79, 79, 0.3);
        color: #f89a9a;
        border-radius: 6px;
        padding: 6px 12px;
        font-size: 12px;
        margin: 4px 0;
        display: block;
    }
    .issue-warning {
        background: rgba(247, 210, 79, 0.12);
        border: 1px solid rgba(247, 210, 79, 0.3);
        color: #f7d24f;
        border-radius: 6px;
        padding: 6px 12px;
        font-size: 12px;
        margin: 4px 0;
        display: block;
    }
    .issue-info {
        background: rgba(79, 142, 247, 0.12);
        border: 1px solid rgba(79, 142, 247, 0.3);
        color: #7fb0f9;
        border-radius: 6px;
        padding: 6px 12px;
        font-size: 12px;
        margin: 4px 0;
        display: block;
    }

    /* === Input styling === */
    [data-testid="stTextArea"] textarea {
        background: var(--bg-card) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius) !important;
        font-size: 14px !important;
    }
    [data-testid="stTextArea"] textarea:focus {
        border-color: var(--accent-blue) !important;
        box-shadow: 0 0 0 2px rgba(79, 142, 247, 0.2) !important;
    }

    /* === Primary button === */
    [data-testid="stButton"] > button {
        background: linear-gradient(135deg, #4f8ef7, #a259ff) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 10px 28px !important;
        font-weight: 600 !important;
        font-size: 15px !important;
        letter-spacing: 0.03em !important;
        transition: opacity 0.2s !important;
        width: 100%;
    }
    [data-testid="stButton"] > button:hover { opacity: 0.88 !important; }

    /* === Table === */
    [data-testid="stDataFrame"] {
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius) !important;
    }

    /* === Sidebar benchmark cards === */
    .bench-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 8px;
        cursor: pointer;
    }
    .bench-card:hover { background: var(--bg-card-hover); }
    .bench-title { font-size: 12px; font-weight: 600; color: var(--text-primary); }
    .bench-query { font-size: 11px; color: var(--text-muted); margin-top: 2px; }

    /* === Hero === */
    .hero-title {
        font-size: 36px;
        font-weight: 800;
        background: linear-gradient(135deg, #4f8ef7, #a259ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        letter-spacing: -0.5px;
        line-height: 1.15;
    }
    .hero-sub {
        font-size: 15px;
        color: var(--text-muted);
        margin-top: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def status_badge(status: str) -> str:
    """Return HTML badge for a validation status."""
    mapping = {
        "valid": ("badge-valid", "✓ VALID"),
        "invalid": ("badge-invalid", "✗ INVALID"),
        "uncertain": ("badge-uncertain", "~ UNCERTAIN"),
    }
    cls, label = mapping.get(status, ("badge-uncertain", "UNKNOWN"))
    return f'<span class="{cls}">{label}</span>'


def bool_icon(val: bool) -> str:
    """Return colored icon for boolean values."""
    return "✅" if val else "❌"


def confidence_color(c: float) -> str:
    """Return color for a confidence level."""
    if c >= 0.75:
        return "#2de08a"
    elif c >= 0.50:
        return "#f7d24f"
    else:
        return "#f74f4f"


def call_api(endpoint: str, method: str = "GET", payload: Optional[dict] = None):
    """Make an API call to the PlaceGuard backend."""
    try:
        with httpx.Client(timeout=30.0) as client:
            if method == "POST":
                resp = client.post(f"{API_BASE_URL}{endpoint}", json=payload)
            else:
                resp = client.get(f"{API_BASE_URL}{endpoint}")
        resp.raise_for_status()
        return resp.json(), None
    except httpx.ConnectError:
        return None, "⚠️ Cannot connect to PlaceGuard API. Is the backend running? (`make serve`)"
    except httpx.HTTPStatusError as e:
        return None, f"API error {e.response.status_code}: {e.response.text[:200]}"
    except Exception as e:
        return None, f"Unexpected error: {str(e)[:200]}"


def fetch_history():
    """Fetch validation history from the API."""
    data, err = call_api("/history?limit=20")
    if err:
        return [], err
    return data or [], None


def fetch_benchmarks():
    """Fetch benchmark scenarios from the API."""
    data, err = call_api("/benchmarks")
    if err:
        return [], err
    return data or [], None


# ---------------------------------------------------------------------------
# Sidebar: Benchmark Gallery
# ---------------------------------------------------------------------------

def render_sidebar():
    """Render the sidebar with benchmark examples and info."""
    with st.sidebar:
        st.markdown(
            """
            <div style='padding: 16px 0 8px 0;'>
                <span style='font-size:22px; font-weight:800; color:#4f8ef7;'>🛡️ PlaceGuard</span><br>
                <span style='font-size:12px; color:#8a8a9a;'>VOYGR · Place Validation API</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.divider()

        st.markdown("**📊 Benchmark Scenarios**", unsafe_allow_html=True)
        st.caption("Click to pre-fill the input")

        benchmarks, err = fetch_benchmarks()

        if err:
            st.warning(err)
        else:
            for bench in benchmarks:
                category_emoji = {
                    "valid_clear": "✅",
                    "hallucinated": "👻",
                    "stale_data": "⏳",
                    "edge_case": "🚫",
                    "international": "🌍",
                    "ambiguous": "❓",
                }.get(bench.get("test_category", ""), "🔹")

                if st.button(
                    f"{category_emoji} {bench['name']}",
                    key=f"bench_{bench['scenario_id']}",
                    help=bench.get("description", ""),
                    use_container_width=True,
                ):
                    st.session_state["query_input"] = bench["query"]
                    if bench.get("context"):
                        st.session_state["context_input"] = json.dumps(
                            bench["context"], indent=2
                        )
                    st.rerun()

        st.divider()
        st.markdown("**🔧 API Endpoints**")
        st.code(
            "POST /validate-place\nGET  /history\nGET  /benchmarks\nPOST /run-benchmark",
            language="text",
        )
        st.caption("Docs: [localhost:8000/docs](http://localhost:8000/docs)")

        st.divider()
        st.markdown("**⚡ Quick Stats**")
        history, _ = fetch_history()
        if history:
            valid_count = sum(1 for h in history if h.get("status") == "valid")
            invalid_count = sum(1 for h in history if h.get("status") == "invalid")
            uncertain_count = sum(1 for h in history if h.get("status") == "uncertain")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("✅ Valid", valid_count)
                st.metric("~ Uncertain", uncertain_count)
            with col2:
                st.metric("✗ Invalid", invalid_count)
                st.metric("Total", len(history))


# ---------------------------------------------------------------------------
# Result Card Rendering
# ---------------------------------------------------------------------------

def render_result_card(result: dict):
    """Render a rich validation result card."""
    status = result.get("status", "uncertain")
    name = result.get("name", "Unknown")
    confidence = float(result.get("confidence", 0.0))
    details = result.get("details", {})
    issues = result.get("issues", [])
    reasoning_chain = result.get("reasoning_chain", [])

    # Header
    st.markdown(
        f"""
        <div class="pg-card">
            <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px;">
                <div>
                    <div style="font-size:20px; font-weight:700; color:#eeeef0;">{name}</div>
                    <div style="font-size:13px; color:#8a8a9a; margin-top:2px;">
                        {details.get('address', '')} · {details.get('category', '')}
                    </div>
                </div>
                {status_badge(status)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Metrics grid
    safety_pct = f"{confidence * 100:.0f}%"
    safety_score = float(result.get("safety_score", 0.0))
    price_tier = details.get("price_tier") or "N/A"

    st.markdown(
        f"""
        <div class="metric-grid">
            <div class="metric-cell">
                <div class="lbl">Confidence</div>
                <div class="val" style="color:{confidence_color(confidence)};">
                    {safety_pct}
                </div>
            </div>
            <div class="metric-cell">
                <div class="lbl">Safety Score</div>
                <div class="val" style="color:{confidence_color(safety_score)};">
                    {safety_score:.0%}
                </div>
            </div>
            <div class="metric-cell">
                <div class="lbl">Price Tier</div>
                <div class="val" style="color:#a259ff;">{price_tier}</div>
            </div>
            <div class="metric-cell">
                <div class="lbl">Data Age</div>
                <div class="val" style="font-size:16px; color:#8a8a9a;">
                    {details.get("data_freshness", "N/A")}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Two-column detail section
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("**📍 Place Details**")
        st.markdown(
            f"""
            <div class="pg-card" style="padding:16px;">
                <table style="width:100%; font-size:13px; border-collapse:collapse;">
                    <tr><td style="color:#8a8a9a;padding:4px 0;">Exists</td>
                        <td style="text-align:right;">{bool_icon(result.get("exists", False))}</td></tr>
                    <tr><td style="color:#8a8a9a;padding:4px 0;">Operating</td>
                        <td style="text-align:right;">{bool_icon(result.get("operating", False))}</td></tr>
                    <tr><td style="color:#8a8a9a;padding:4px 0;">Price Verified</td>
                        <td style="text-align:right;">{bool_icon(result.get("price_verified", False))}</td></tr>
                    <tr><td style="color:#8a8a9a;padding:4px 0;">Hours</td>
                        <td style="text-align:right; color:#eeeef0;">{details.get("hours") or "N/A"}</td></tr>
                    <tr><td style="color:#8a8a9a;padding:4px 0;">City</td>
                        <td style="text-align:right; color:#eeeef0;">{details.get("city") or "N/A"}</td></tr>
                    <tr><td style="color:#8a8a9a;padding:4px 0;">Rating</td>
                        <td style="text-align:right; color:#f7d24f;">
                            {"⭐ " + str(details.get("average_rating", "N/A")) if details.get("average_rating") else "N/A"}
                        </td></tr>
                    <tr><td style="color:#8a8a9a;padding:4px 0;">Model</td>
                        <td style="text-align:right; color:#8a8a9a; font-size:11px;">{result.get("model_used", "N/A")}</td></tr>
                </table>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if details.get("reviews_summary"):
            st.markdown("**💬 Reviews Summary**")
            st.markdown(
                f'<div class="pg-card" style="padding:14px; font-size:13px; '
                f'color:#c0c0ce; font-style:italic;">"{details["reviews_summary"]}"</div>',
                unsafe_allow_html=True,
            )

    with col_right:
        st.markdown("**🔍 Reasoning Chain**")
        if reasoning_chain:
            chain_html = "".join(
                f'<div class="reasoning-item">{item}</div>'
                for item in reasoning_chain
            )
            st.markdown(
                f'<div class="pg-card" style="padding:14px;">{chain_html}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="pg-card" style="padding:14px; color:#8a8a9a;">No reasoning chain available</div>',
                unsafe_allow_html=True,
            )

        if issues:
            st.markdown(f"**⚠️ Issues ({len(issues)})**")
            issues_html = ""
            for issue in issues:
                css_cls = f"issue-{issue.get('severity', 'info')}"
                severity_icon = {"error": "🚫", "warning": "⚠️", "info": "ℹ️"}.get(
                    issue.get("severity", "info"), "ℹ️"
                )
                issues_html += (
                    f'<span class="{css_cls}">'
                    f'{severity_icon} <strong>{issue.get("field","")}</strong>: '
                    f'{issue.get("message","")}</span>'
                )
            st.markdown(
                f'<div class="pg-card" style="padding:12px;">{issues_html}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="pg-card" style="padding:14px; color:#2de08a;">✓ No issues found</div>',
                unsafe_allow_html=True,
            )

    # Raw JSON expander
    with st.expander("📄 Raw JSON Response", expanded=False):
        st.json(result)


# ---------------------------------------------------------------------------
# History Table
# ---------------------------------------------------------------------------

def render_history_table(history: list):
    """Render the recent validations history table."""
    if not history:
        st.markdown(
            '<div class="pg-card" style="text-align:center; color:#8a8a9a; padding:32px;">No validations yet</div>',
            unsafe_allow_html=True,
        )
        return

    # Build display data
    rows = []
    for h in history:
        status = h.get("status", "uncertain")
        status_icon = {"valid": "✅", "invalid": "❌", "uncertain": "⚠️"}.get(status, "❓")
        confidence = h.get("confidence", 0.0)
        rows.append({
            "Status": f"{status_icon} {status.upper()}",
            "Place": h.get("place_name", "Unknown")[:40],
            "Confidence": f"{confidence:.0%}",
            "Query": h.get("query", "")[:60] + ("..." if len(h.get("query", "")) > 60 else ""),
            "Model": h.get("model_used", "N/A"),
            "Time": h.get("timestamp", "")[:16].replace("T", " "),
        })

    import pandas as pd
    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------

def main():
    """Main Streamlit application."""

    # Initialize session state
    if "query_input" not in st.session_state:
        st.session_state["query_input"] = ""
    if "context_input" not in st.session_state:
        st.session_state["context_input"] = ""
    if "last_result" not in st.session_state:
        st.session_state["last_result"] = None

    # Sidebar
    render_sidebar()

    # Hero section
    st.markdown(
        """
        <div style="padding: 20px 0 28px 0;">
            <div class="hero-title">🛡️ PlaceGuard</div>
            <div class="hero-sub">
                Production-grade place validation for VOYGR · Powered by LangGraph ReAct Agent
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Input section
    st.markdown("### 🔍 Validate a Place")
    
    col_main, col_ctx = st.columns([3, 1])
    
    with col_main:
        query = st.text_area(
            label="Place query or LLM output",
            value=st.session_state.get("query_input", ""),
            placeholder=(
                "Try: 'Rooftop bar in Gangnam under $20 cocktails'\n"
                "Or paste raw LLM JSON about a place recommendation..."
            ),
            height=100,
            label_visibility="collapsed",
            key="query_text_area",
        )
    
    with col_ctx:
        context_raw = st.text_area(
            label="Context (JSON, optional)",
            value=st.session_state.get("context_input", ""),
            placeholder='{"city": "Seoul",\n "country": "KR"}',
            height=100,
            label_visibility="visible",
        )

    validate_btn = st.button(
        "🚀  Validate Place",
        type="primary",
        use_container_width=True,
    )

    # Handle validation
    if validate_btn:
        if not query or len(query.strip()) < 3:
            st.warning("Please enter a place query (at least 3 characters).")
        else:
            # Parse optional context JSON
            context = None
            if context_raw.strip():
                try:
                    context = json.loads(context_raw)
                except json.JSONDecodeError:
                    st.warning("⚠️ Context JSON is invalid — ignoring it.")

            # Show animated loading state
            with st.spinner("🤖 PlaceGuard agent is validating..."):
                progress = st.progress(0, text="Initializing agent…")
                time.sleep(0.3)
                progress.progress(20, text="Searching for place…")
                time.sleep(0.3)
                progress.progress(40, text="Checking operating status…")

                payload = {"query": query, "context": context}
                result, err = call_api("/validate-place", method="POST", payload=payload)
                
                progress.progress(80, text="Enriching data…")
                time.sleep(0.2)
                progress.progress(100, text="Done!")
                time.sleep(0.3)
                progress.empty()

            if err:
                st.error(err)
            elif result:
                st.session_state["last_result"] = result
                st.success("✅ Validation complete!")

    # Display result
    if st.session_state.get("last_result"):
        st.markdown("---")
        st.markdown("### 📋 Validation Result")
        render_result_card(st.session_state["last_result"])

    # History section
    st.markdown("---")
    col_hist_title, col_refresh = st.columns([5, 1])
    with col_hist_title:
        st.markdown("### 📜 Recent Validations")
    with col_refresh:
        if st.button("↻ Refresh", key="refresh_history"):
            st.rerun()

    history, hist_err = fetch_history()
    if hist_err:
        st.warning(hist_err)
    else:
        render_history_table(history)


if __name__ == "__main__":
    main()
