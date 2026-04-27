"""
webui/app.py
--------------------
StayEase Streamlit Web UI — Chat interface for the AI booking agent.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uuid
from datetime import datetime

import streamlit as st
from api_client import BASE_URL, check_health, get_history, list_conversations, send_message, get_model_availability

# ---------------------------------------------------------------------------
# Page config & styling
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="StayEase AI Assistant",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

STAYEASE_BLUE = "#1E3A5F"
STAYEASE_GOLD = "#D4AF37"
INTENT_COLORS = {
    "search": "#22c55e",
    "book": "#3b82f6",
    "details": "#a855f7",
    "escalate": "#ef4444",
    "unknown": "#6b7280",
}

# ---------------------------------------------------------------------------+
# Custom CSS
# ---------------------------------------------------------------------------+

st.markdown(
    """
    <style>
    /* Hide Streamlit default header/footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: #0f172a;
        border-right: 1px solid #1e293b;
    }

    /* Section Headings */
    .sidebar-section-header {
        font-size: 11px;
        font-weight: 700;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin: 24px 0 8px 0;
        padding-bottom: 4px;
        border-bottom: 1px solid #1e293b;
    }

    /* New conversation button styling */
    div.stButton > button:first-child {
        background-color: #1e293b;
        color: #f8fafc;
        border: 1px solid #334155;
        border-radius: 10px;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    div.stButton > button:first-child:hover {
        background-color: #334155;
        border-color: #D4AF37;
        color: #D4AF37;
    }

    /* Sidebar conversation item */
    .conv-item {
        padding: 10px 14px;
        border-radius: 10px;
        margin: 6px 0;
        cursor: pointer;
        transition: all 0.2s ease;
        background: transparent;
        border: 1px solid transparent;
    }
    .conv-item:hover {
        background: rgba(30, 41, 59, 0.5);
        border: 1px solid #334155;
    }
    .conv-item.active {
        background: rgba(212, 175, 55, 0.05);
        border: 1px solid rgba(212, 175, 55, 0.3);
    }
    .conv-item .preview {
        font-size: 14px;
        font-weight: 500;
        color: #f1f5f9;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .conv-item .meta {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-top: 6px;
    }
    .conv-item .meta-time {
        font-size: 11px;
        color: #64748b;
    }

    /* Intent badge */
    .intent-badge {
        font-size: 10px;
        font-weight: 700;
        padding: 2px 6px;
        border-radius: 4px;
        text-transform: uppercase;
        color: white;
    }

    /* Status Card */
    .status-card {
        background: rgba(15, 23, 42, 0.6);
        backdrop-filter: blur(8px);
        border: 1px solid #1e293b;
        border-radius: 12px;
        padding: 12px;
        margin-top: 8px;
    }
    .status-item {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 8px;
    }
    .status-label {
        font-size: 11px;
        color: #94a3b8;
    }
    .status-value {
        font-size: 13px;
        font-weight: 600;
        color: #e2e8f0;
    }
    .status-detail {
        font-size: 10px;
        color: #64748b;
        line-height: 1.4;
    }

    /* Custom Scrollbar for Sidebar */
    [data-testid="stSidebar"]::-webkit-scrollbar {
        width: 4px;
    }
    [data-testid="stSidebar"]::-webkit-scrollbar-thumb {
        background: #1e293b;
        border-radius: 10px;
    }

    /* Standard components improvement */
    [data-testid="stChatInput"] {
        border-radius: 12px !important;
    }
    </style>

    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------+
# Session state init
# ---------------------------------------------------------------------------+

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []


# ---------------------------------------------------------------------------+
# Helper functions
# ---------------------------------------------------------------------------+


def format_timestamp(iso_str: str) -> str:
    """Format ISO timestamp to relative time."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now()
        diff = (now - dt.replace(tzinfo=None)).total_seconds()
        if diff < 60:
            return "just now"
        elif diff < 3600:
            return f"{int(diff/60)}m ago"
        elif diff < 86400:
            return f"{int(diff/3600)}h ago"
        else:
            return f"{int(diff/86400)}d ago"
    except Exception:
        return ""


def get_intent_color(intent: str | None) -> str:
    """Get color for intent badge."""
    return INTENT_COLORS.get(intent or "unknown", INTENT_COLORS["unknown"])


def is_booking_confirmation(metadata: dict | None) -> bool:
    """Check if this is a booking confirmation."""
    return metadata and metadata.get("booking_confirmed") is True


def render_booking_card(content: str, metadata: dict) -> str:
    """Render a booking confirmation card."""
    booking_id = metadata.get("booking_id", "")
    return f"""
    <div class="booking-card">
        <h3>✓ Booking Confirmed</h3>
        <div class="ref">{booking_id}</div>
        <div class="details">{content}</div>
    </div>
    """


def render_message(role: str, content: str, metadata: dict | None = None):
    """Render a single message."""
    if role == "user":
        with st.chat_message("user", avatar="👤"):
            st.markdown(f"<div style='color: white;'>{content}</div>", unsafe_allow_html=True)
    else:
        with st.chat_message("assistant", avatar="🏠"):
            if is_booking_confirmation(metadata):
                st.markdown(render_booking_card(content, metadata), unsafe_allow_html=True)
            else:
                st.markdown(content)


def load_conversation(conv_id: str):
    """Load a conversation from the API."""
    try:
        messages = get_history(conv_id)
        st.session_state.messages = [
            {
                "role": m["role"],
                "content": m["content"],
                "timestamp": m["timestamp"],
                "metadata": m.get("metadata"),
            }
            for m in messages
        ]
        st.session_state.conversation_id = conv_id
    except Exception as e:
        st.error(f"Could not load conversation: {e}")
        st.session_state.messages = []


def start_new_conversation():
    """Start a new conversation."""
    st.session_state.conversation_id = str(uuid.uuid4())
    st.session_state.messages = []


# ---------------------------------------------------------------------------+
# Sidebar
# ---------------------------------------------------------------------------+

with st.sidebar:
    st.markdown(
        """
        <div style='padding: 20px 0 10px 0;'>
            <h1 style='color: #f8fafc; margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.02em;'>
                <span style='color: #D4AF37;'>🏠</span> StayEase
            </h1>
            <p style='color: #64748b; margin: 4px 0 0 0; font-size: 13px;'>Premium Booking Intelligence</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("＋ New Chat", use_container_width=True):
        start_new_conversation()
        st.rerun()

    st.markdown("<div class='sidebar-section-header'>History</div>", unsafe_allow_html=True)

    try:
        convos = list_conversations()
        if not convos:
            st.markdown(
                "<p style='color: #475569; text-align: center; font-size: 13px; padding: 20px 0;'>No active sessions</p>",
                unsafe_allow_html=True,
            )
        else:
            for conv in convos:
                conv_id = conv["conversation_id"]
                is_active = conv_id == st.session_state.conversation_id
                color = get_intent_color(conv.get("last_intent"))
                preview = conv.get("last_message_preview") or "New conversation..."
                time_ago = format_timestamp(conv.get("updated_at"))

                css_class = "conv-item active" if is_active else "conv-item"
                st.markdown(
                    f"""
                    <div class='{css_class}'>
                        <div class='preview'>{preview}</div>
                        <div class='meta'>
                            <span class='intent-badge' style='background: {color};'>{conv.get('last_intent', 'unknown') or 'start'}</span>
                            <span class='meta-time'>{time_ago}</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button(
                    "Switch to Chat",
                    key=f"load_{conv_id}",
                    use_container_width=True,
                    on_click=load_conversation,
                    args=(conv_id,),
                ):
                    pass
    except Exception as e:
        st.error(f"History unavailable: {e}")

    # Bottom Section: System Dashboard
    st.markdown("<div class='sidebar-section-header'>System Status</div>", unsafe_allow_html=True)

    model_status = get_model_availability()
    status_icon = "●" # Use a solid dot for a cleaner look
    status_color = "#22c55e" if model_status["is_available"] else "#ef4444"
    
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown("<span style='font-size: 12px; color: #94a3b8; font-weight: 600;'>LLM AVAILABILITY</span>", unsafe_allow_html=True)
    with col2:
        if st.button("↻", key="refresh_model", help="Sync model status", use_container_width=True):
            st.rerun()

    st.markdown(
        f"""
        <div class='status-card'>
            <div class='status-item'>
                <span style='color: {status_color}; font-size: 14px;'>{status_icon}</span>
                <div style='flex: 1;'>
                    <div class='status-value'>{model_status["model_name"]}</div>
                    <div class='status-label'>{'Operational' if model_status['is_available'] else 'Interrupted'}</div>
                </div>
            </div>
            <div class='status-detail'>{model_status["status_detail"]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div style='margin-top: 30px; padding: 12px; border-top: 1px solid #1e293b; text-align: center;'>
            <div style='font-size: 10px; color: #475569; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;'>Session Identity</div>
            <code style='color: #64748b; background: transparent; font-size: 12px;'>{st.session_state.conversation_id[:8]}...</code>
        </div>
        """,
        unsafe_allow_html=True,
    )



# ---------------------------------------------------------------------------+
# Main panel
# ---------------------------------------------------------------------------+

st.markdown(
    f"""
    <div style='display: flex; align-items: center; justify-content: space-between; padding: 16px 24px; border-radius: 12px; background: linear-gradient(90deg, #1E3A5F 0%, #0f172a 100%); border: 1px solid #334155; margin-bottom: 24px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);'>
        <div style='display: flex; align-items: center; gap: 16px;'>
            <div style='font-size: 32px;'>🏠</div>
            <div>
                <h2 style='margin: 0; color: #f8fafc; font-size: 24px; font-weight: 600;'>StayEase AI Assistant</h2>
                <div style='color: #94a3b8; font-size: 14px; margin-top: 4px;'>Your premium booking agent for Bangladesh</div>
            </div>
        </div>
        <div style='text-align: right;'>
            <div style='color: #64748b; font-size: 11px; text-transform: uppercase; font-weight: 600; letter-spacing: 0.05em;'>Session ID</div>
            <code style='color: #D4AF37; background: rgba(212, 175, 55, 0.1); padding: 4px 8px; border-radius: 4px; font-size: 13px;'>{st.session_state.conversation_id[:8]}</code>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Check backend health
if not check_health():
    st.error(f"⚠ Could not reach the backend at {BASE_URL}. Is the API server running?")
    st.info("Start the backend with: `PYTHONPATH=. uv run fastapi dev api/main.py`")
    st.stop()

# Display existing messages
for msg in st.session_state.messages:
    render_message(msg["role"], msg["content"], msg.get("metadata"))

# Chat input
if prompt := st.chat_input("Type your message in Bengali or English..."):
    render_message("user", prompt)
    st.session_state.messages.append(
        {"role": "user", "content": prompt, "timestamp": datetime.now().isoformat()}
    )

    with st.spinner("🤔 Thinking..."):
        try:
            response = send_message(st.session_state.conversation_id, prompt)
            assistant_msg = {
                "role": "assistant",
                "content": response["content"],
                "timestamp": response["timestamp"],
                "metadata": response.get("metadata"),
            }
            st.session_state.messages.append(assistant_msg)
            render_message("assistant", response["content"], response.get("metadata"))
        except Exception as e:
            st.error(f"Error: {e}")
            st.session_state.messages.pop()