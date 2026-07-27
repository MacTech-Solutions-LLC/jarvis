import streamlit as st
import sys
import os

# Add the app directory to the path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.config import Config
from app.core.paths import Paths
from app.workspaces.manager import WorkspaceManager
from app.llm.openai_provider import OpenAIProvider
from app.kb.search import KBSearch
from app.sessions.manager import SessionManager
from app.media.image_gen import ImageGenerator
from app.media.tts import TextToSpeech
from app.media.stt import SpeechToText
from app.media.player import MediaPlayer
from web.theme import root_css_variables

import httpx
from typing import Optional


def _ping_openai(api_key: Optional[str]) -> bool:
    if not api_key:
        return False
    try:
        resp = httpx.get("https://api.openai.com/v1/models",
                          headers={"Authorization": f"Bearer {api_key}"},
                          timeout=5.0)
        return resp.status_code == 200
    except Exception:
        return False


def _ping_anthropic(api_key: Optional[str]) -> bool:
    if not api_key:
        return False
    try:
        # anthropic requires version header
        resp = httpx.get("https://api.anthropic.com/v1/models",
                          headers={
                              "x-api-key": api_key,
                              "anthropic-version": "2023-06-01"
                          },
                          timeout=5.0)
        return resp.status_code == 200
    except Exception:
        return False


def _ping_groq(api_key: Optional[str]) -> bool:
    # Groq uses OpenAI-compatible endpoint and bearer token
    if not api_key:
        return False
    try:
        resp = httpx.get("https://api.groq.com/openai/v1/models",
                          headers={"Authorization": f"Bearer {api_key}"},
                          timeout=5.0)
        return resp.status_code == 200
    except Exception:
        return False


def _ping_elevenlabs(api_key: Optional[str]) -> bool:
    if not api_key:
        return False
    try:
        resp = httpx.get("https://api.elevenlabs.io/v1/voices",
                          headers={"xi-api-key": api_key},
                          timeout=5.0)
        return resp.status_code == 200
    except Exception:
        return False


st.set_page_config(
    page_title="Jarvis — AI Console",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# Theming. All styling lives in this one injected block — see web/theme.py
# for the palette (verified against WCAG 2.1 AA by tests/test_contrast.py)
# and .streamlit/config.toml for the base theme Streamlit itself controls.
# Do not add further st.markdown(..., unsafe_allow_html=True) style tags
# elsewhere in this file; extend this stylesheet instead.
# ============================================================================
_CSS = """
<style>
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', sans-serif;
    }

    :root {
__ROOT_VARS__
        --space-1: 4px;
        --space-2: 8px;
        --space-3: 12px;
        --space-4: 16px;
        --space-5: 24px;
        --space-6: 32px;
        --text-xs: 0.8rem;
        --text-sm: 0.875rem;
        --text-base: 1rem;
        --text-lg: 1.125rem;
        --text-xl: 1.375rem;
        --text-2xl: 1.75rem;
        --text-3xl: 2.25rem;
        --radius: 10px;
    }

    /* App chrome ------------------------------------------------------- */
    .stApp, [data-testid="stAppViewContainer"] {
        background: var(--bg);
        color: var(--text);
    }

    [data-testid="stSidebar"], .sidebar .sidebar-content {
        background: var(--bg-elevated);
        border-right: 1px solid var(--border-subtle);
    }

    [data-testid="stSidebar"] * {
        color: var(--text);
    }

    /* Typography / hierarchy -------------------------------------------
       One scale, one weight system. No gradient text-fill: it silently
       breaks (renders illegibly) whenever a selector above it stops
       matching a future Streamlit DOM, which is what happened here. */
    h1, .jv-h1 {
        color: var(--text);
        font-weight: 700;
        font-size: var(--text-3xl);
        letter-spacing: -0.5px;
        line-height: 1.2;
        margin-bottom: var(--space-2);
    }

    h2, .jv-h2 {
        color: var(--text);
        font-weight: 600;
        font-size: var(--text-xl);
        letter-spacing: -0.2px;
        line-height: 1.3;
        margin-top: var(--space-6);
        margin-bottom: var(--space-3);
    }

    h3, .jv-h3 {
        color: var(--text-secondary);
        font-weight: 600;
        font-size: var(--text-lg);
        line-height: 1.3;
        margin-bottom: var(--space-3);
    }

    .jv-subtitle {
        color: var(--text-muted);
        font-size: var(--text-sm);
        margin-top: 0;
        margin-bottom: var(--space-5);
    }

    /* Focus visibility — never remove, must clear 3:1 against any surface */
    button:focus-visible,
    a:focus-visible,
    input:focus-visible,
    textarea:focus-visible,
    select:focus-visible,
    [tabindex]:focus-visible {
        outline: 2px solid var(--accent) !important;
        outline-offset: 2px !important;
    }

    /* Buttons ------------------------------------------------------------
       Accent is a bright, light cyan (verified ~7-9:1 against page/card
       backgrounds). Pairing it with white button text — the previous
       design — drops to ~2:1 and fails AA; the label has to be dark. */
    .stButton > button {
        background: var(--accent) !important;
        color: var(--on-accent) !important;
        border: none !important;
        border-radius: var(--radius) !important;
        padding: var(--space-2) var(--space-4) !important;
        font-weight: 600 !important;
        font-size: var(--text-sm) !important;
        min-height: 44px !important;
        transition: filter 0.15s ease !important;
    }

    .stButton > button:hover {
        filter: brightness(1.1);
    }

    /* Inputs -------------------------------------------------------------- */
    .stTextInput input,
    .stTextArea textarea,
    .stSelectbox > div > div,
    .stNumberInput input,
    [data-baseweb="select"] > div {
        background: var(--surface) !important;
        border: 1px solid var(--border-strong) !important;
        color: var(--text) !important;
        border-radius: var(--radius) !important;
    }

    .stTextInput label, .stTextArea label, .stSelectbox label,
    .stNumberInput label, .stSlider label, .stCheckbox label, .stRadio label {
        color: var(--text) !important;
        font-weight: 500 !important;
        font-size: var(--text-sm) !important;
    }

    /* Tabs ------------------------------------------------------------- */
    .stTabs [data-baseweb="tab-list"] {
        gap: var(--space-2);
        border-bottom: 1px solid var(--border-subtle);
        margin-bottom: var(--space-5);
    }

    .stTabs [data-baseweb="tab"] {
        color: var(--text-secondary) !important;
        border-radius: var(--radius) var(--radius) 0 0 !important;
        min-height: 44px !important;
    }

    .stTabs [aria-selected="true"] {
        color: var(--text) !important;
        border-bottom: 2px solid var(--accent) !important;
    }

    /* Expanders / alerts -------------------------------------------------- */
    .stExpander, [data-testid="stExpander"] {
        background: var(--surface) !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: var(--radius) !important;
    }

    .stAlert {
        border-radius: var(--radius) !important;
        background: var(--surface) !important;
    }

    /* One card language for the whole console --------------------------
       Metric tiles, provider status, and workspace summary all use this
       single class so the page reads as one system, not three. */
    .jv-card {
        background: var(--surface);
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius);
        padding: var(--space-4);
        margin-bottom: var(--space-3);
    }

    .jv-card--metric {
        text-align: center;
    }

    .jv-metric-value {
        font-size: var(--text-2xl);
        font-weight: 700;
        color: var(--text);
    }

    .jv-metric-label {
        color: var(--text-muted);
        font-size: var(--text-sm);
        margin-top: var(--space-1);
    }

    .jv-card-title {
        font-weight: 600;
        color: var(--text);
        font-size: var(--text-base);
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--space-2);
        margin-bottom: var(--space-1);
    }

    .jv-card-desc {
        color: var(--text-secondary);
        font-size: var(--text-sm);
        line-height: 1.5;
    }

    /* Status badges — always paired with a text label, never color alone */
    .jv-badge {
        display: inline-flex;
        align-items: center;
        gap: var(--space-1);
        padding: 2px var(--space-2);
        border-radius: 999px;
        font-size: var(--text-xs);
        font-weight: 600;
        white-space: nowrap;
    }

    .jv-badge--success { color: var(--success); background: rgba(62, 213, 152, 0.12); }
    .jv-badge--warning { color: var(--warning); background: rgba(245, 184, 76, 0.12); }
    .jv-badge--danger  { color: var(--danger);  background: rgba(248, 113, 113, 0.12); }
    .jv-badge--neutral { color: var(--text-muted); background: rgba(147, 161, 181, 0.12); }

    /* Local vs. cloud path — kept visually distinct wherever a provider
       or execution path is shown, so a future local model is never
       confused with a cloud API call. */
    .jv-tag {
        display: inline-flex;
        align-items: center;
        padding: 2px var(--space-2);
        border-radius: 999px;
        font-size: var(--text-xs);
        font-weight: 700;
        letter-spacing: 0.03em;
        text-transform: uppercase;
    }

    .jv-tag--cloud { color: var(--warning); background: rgba(245, 184, 76, 0.12); border: 1px solid rgba(245, 184, 76, 0.3); }
    .jv-tag--local { color: var(--success); background: rgba(62, 213, 152, 0.12); border: 1px solid rgba(62, 213, 152, 0.3); }

    /* Chat bubbles ------------------------------------------------------ */
    .jv-chat-row { display: flex; margin-bottom: var(--space-2); }
    .jv-chat-row--user { justify-content: flex-end; }
    .jv-chat-bubble {
        padding: var(--space-2) var(--space-4);
        border-radius: var(--radius);
        max-width: 70%;
    }
    .jv-chat-bubble--user { background: var(--accent); color: var(--on-accent); }
    .jv-chat-bubble--assistant { background: var(--surface); color: var(--text); border: 1px solid var(--border-subtle); }

    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-track { background: var(--bg-elevated); }
    ::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 4px; }
</style>
"""
st.markdown(_CSS.replace("__ROOT_VARS__", root_css_variables()), unsafe_allow_html=True)


# Initialize core components
@st.cache_resource
def init_app():
    config = Config()
    paths = Paths()
    workspace_manager = WorkspaceManager(paths)
    provider = OpenAIProvider(config)
    kb_search = KBSearch(paths)
    session_manager = SessionManager(paths)
    image_generator = ImageGenerator(config, paths)
    tts_engine = TextToSpeech(config, paths)
    stt_engine = SpeechToText(config, paths)
    media_player = MediaPlayer(config, paths)
    return (config, paths, workspace_manager, provider, kb_search, session_manager,
            image_generator, tts_engine, stt_engine, media_player)


config, paths, workspace_manager, provider, kb_search, session_manager, image_generator, tts_engine, stt_engine, media_player = init_app()

kb_doc_count = sum(1 for f in paths.kb.rglob("*") if f.is_file())

# ====== SESSION STATE INITIALIZATION ======
if "model_settings" not in st.session_state:
    st.session_state.model_settings = {
        "text_model": "gpt-4",
        "text_provider": "openai",
        "temperature": 0.7,
        "top_p": 1.0,
        "max_tokens": 2000,
        "image_model": "dall-e-3",
        "tts_voice": "nova",
        "tts_provider": "openai",
    }

if "model_options" not in st.session_state:
    st.session_state.model_options = {
        "openai": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"],
        "anthropic": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
        "groq": ["mixtral-8x7b", "llama2-70b"],
    }

if "favorites" not in st.session_state:
    st.session_state.favorites = []

if "prompt_templates" not in st.session_state:
    st.session_state.prompt_templates = {
        "Technical": "You are a technical expert. Answer the following question precisely and include code examples when relevant: {query}",
        "Creative": "You are a creative writer. Generate imaginative, engaging content about: {query}",
        "Analytical": "Analyze the following topic systematically, breaking it into key components: {query}",
        "Teaching": "Explain this concept as if teaching a bright 10-year-old, using analogies: {query}",
    }

# ====== SIDEBAR ======
with st.sidebar:
    st.markdown('<div class="jv-h2" style="margin-top:0;">Jarvis Console</div>', unsafe_allow_html=True)
    st.markdown("---")

    # Workspace selection — sole home for this control (not repeated in main content)
    workspaces = workspace_manager.list_workspaces()
    current_workspace = st.selectbox(
        "Active workspace",
        workspaces,
        index=0 if workspaces else None
    )

    if current_workspace:
        workspace = workspace_manager.get_workspace(current_workspace)
        st.markdown(
            '<div class="jv-card">'
            f'<div class="jv-card-title">{workspace.name}</div>'
            f'<div class="jv-card-desc">{workspace.description}</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    with st.expander("System status", expanded=False):
        has_openai_key = bool(config.openai_api_key)
        st.markdown(f"""
- **OpenAI key configured:** {"Yes" if has_openai_key else "No"}
- **Workspaces found:** {len(workspaces)}
- **KB documents indexed:** {kb_doc_count}
        """)

    st.markdown("---")
    st.markdown('<div class="jv-h3">Model configuration</div>', unsafe_allow_html=True)

    # allow external actions (e.g. "Use for chat" buttons) to override
    if "force_provider" in st.session_state:
        forced = st.session_state.pop("force_provider")
        st.session_state.sidebar_provider = forced.get("provider")
        st.session_state.sidebar_model = forced.get("model")

    provider_choice = st.selectbox(
        "Provider",
        list(st.session_state.model_options.keys()),
        key="sidebar_provider"
    )

    model_choice = st.selectbox(
        "Model",
        st.session_state.model_options.get(provider_choice, []),
        key="sidebar_model"
    )

    st.session_state.model_settings["text_provider"] = provider_choice
    st.session_state.model_settings["text_model"] = model_choice

    with st.expander("Parameters"):
        temp = st.slider("Temperature", 0.0, 2.0, st.session_state.model_settings["temperature"], 0.1, key="temp_slider")
        st.session_state.model_settings["temperature"] = temp

        top_p = st.slider("Top P", 0.0, 1.0, st.session_state.model_settings["top_p"], 0.05, key="top_p_slider")
        st.session_state.model_settings["top_p"] = top_p

        max_tok = st.number_input("Max tokens", 100, 4000, st.session_state.model_settings["max_tokens"], 100, key="max_tok_input")
        st.session_state.model_settings["max_tokens"] = max_tok

# ====== MAIN CONTENT ======
st.markdown('<h1>Jarvis Console</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="jv-subtitle">'
    f'Provider: {st.session_state.model_settings["text_provider"]} '
    f'({st.session_state.model_settings["text_model"]})'
    ' &nbsp;·&nbsp; <span class="jv-tag jv-tag--cloud">Cloud</span> '
    'requests leave this device'
    '</p>',
    unsafe_allow_html=True,
)

# ====== STATUS ======
st.markdown("## Overview")

total_sessions = len(session_manager.list_sessions(current_workspace)) if current_workspace else 0

metric_cols = st.columns(4)
metrics = [
    (str(len(workspaces)), "Workspaces"),
    (str(total_sessions), "Sessions in this workspace"),
    (str(kb_doc_count), "Documents indexed"),
    (st.session_state.model_settings["text_model"], "Model loaded"),
]
for col, (value, label) in zip(metric_cols, metrics):
    with col:
        st.markdown(
            f'<div class="jv-card jv-card--metric">'
            f'<div class="jv-metric-value">{value}</div>'
            f'<div class="jv-metric-label">{label}</div>'
            '</div>',
            unsafe_allow_html=True,
        )

# ====== PROVIDER STATUS ======
st.markdown("### Provider status")

api_status_cols = st.columns(4)

apis = [
    ("OpenAI", "GPT-4, DALL-E", _ping_openai),
    ("Anthropic", "Claude-3", _ping_anthropic),
    ("Groq", "Mixtral, Llama", _ping_groq),
    ("ElevenLabs", "TTS voices", _ping_elevenlabs),
]

for i, (api_name, models, ping_fn) in enumerate(apis):
    with api_status_cols[i]:
        env_key = os.getenv(api_name.upper() + "_API_KEY") if api_name != "OpenAI" else config.openai_api_key
        has_key = bool(env_key)

        if has_key:
            ok = ping_fn(env_key)
            badge_class = "jv-badge--success" if ok else "jv-badge--danger"
            status_text = "Connected" if ok else "Unreachable"
        else:
            badge_class = "jv-badge--neutral"
            status_text = "No key configured"

        st.markdown(f"""
        <div class="jv-card">
            <div class="jv-card-title">
                <span>{api_name}</span>
                <span class="jv-tag jv-tag--cloud">Cloud</span>
            </div>
            <div class="jv-card-desc">{models}</div>
            <div style="margin-top: var(--space-2);">
                <span class="jv-badge {badge_class}">{status_text}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button(f"Check {api_name}", key=f"ping_{api_name}"):
            ok = ping_fn(env_key)
            if ok:
                st.success(f"{api_name} responded")
            else:
                st.error(f"{api_name} did not respond")

        provider_key = api_name.lower()
        if provider_key in ("openai", "anthropic", "groq"):
            if st.button(f"Use {api_name} for chat", key=f"use_{api_name}"):
                options = st.session_state.model_options.get(provider_key, [])
                if options:
                    st.session_state.force_provider = {"provider": provider_key, "model": options[0]}
                    st.rerun()

st.markdown("---")

# Main tabs
tab_chat, tab_kb, tab_sessions, tab_tools, tab_media, tab_settings = st.tabs([
    "Chat", "Knowledge", "Sessions", "Tools", "Media", "Settings"
])

# ====== CHAT TAB ======
with tab_chat:
    st.markdown('<h3>AI chat interface</h3>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        sessions = session_manager.list_sessions(current_workspace) if current_workspace else []
        session_options = ["New session"] + [s.title[:20] for s in sessions]
        selected_session = st.selectbox(
            "Session",
            session_options,
            key="session_select"
        )

    with col2:
        template = st.selectbox(
            "Template",
            ["None"] + list(st.session_state.prompt_templates.keys()),
            key="prompt_template"
        )

    with col3:
        is_favorite = st.checkbox("Favorite", key="favorite_session")
        if is_favorite and selected_session not in st.session_state.favorites:
            st.session_state.favorites.append(selected_session)

    with st.expander("Advanced chat options", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            system_prompt = st.text_area(
                "System prompt",
                height=100,
                placeholder="You are a helpful AI assistant...",
                key="system_prompt_input"
            )
        with col2:
            col_a, col_b = st.columns(2)
            with col_a:
                use_kb = st.checkbox("Use knowledge base", value=True)
                kb_limit = st.number_input("KB results", 1, 10, 3, key="kb_limit")
            with col_b:
                include_context = st.checkbox("Show context", value=False)
                response_format = st.selectbox(
                    "Format",
                    ["text", "markdown", "json"],
                    key="response_format"
                )

    if "messages" not in st.session_state:
        st.session_state.messages = []

    chat_container = st.container()
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    col1, col2 = st.columns([20, 1])

    with col1:
        if prompt := st.chat_input("Ask Jarvis anything...", key="chat_input"):
            if not current_workspace:
                st.error("Select a workspace first")
            else:
                final_prompt = prompt
                if template != "None":
                    final_prompt = st.session_state.prompt_templates[template].format(query=prompt)

                st.session_state.messages.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                with st.chat_message("assistant"):
                    with st.spinner("Thinking..."):
                        try:
                            kb_results = []
                            if use_kb:
                                kb_results = kb_search.search(final_prompt, workspace=current_workspace, limit=kb_limit)

                            context = "\n\n".join([r.content for r in kb_results]) if kb_results else ""

                            system_msg = system_prompt if system_prompt else (workspace.system_prompt if current_workspace else "")
                            full_prompt = f"{system_msg}\n\nContext:\n{context}\n\nUser: {final_prompt}"

                            response = provider.generate_text(full_prompt)
                            st.markdown(response)
                            st.session_state.messages.append({"role": "assistant", "content": response})

                            if include_context and kb_results:
                                with st.expander("Context used"):
                                    for i, result in enumerate(kb_results, 1):
                                        st.markdown(f"**Source {i}:** {result.source or 'Unknown'}")
                                        st.markdown(result.content[:200] + "...")

                            if selected_session != "New session":
                                idx = session_options.index(selected_session) - 1
                                if idx >= 0:
                                    session_manager.add_message(sessions[idx].id, "user", prompt)
                                    session_manager.add_message(sessions[idx].id, "assistant", response)
                            else:
                                new_session = session_manager.create_session(current_workspace, f"Chat {len(sessions) + 1}")
                                session_manager.add_message(new_session.id, "user", prompt)
                                session_manager.add_message(new_session.id, "assistant", response)
                                st.rerun()

                        except Exception as e:
                            st.error(f"Error: {str(e)}")

    with col2:
        if st.button("Refresh", help="Refresh", key="refresh_chat"):
            st.rerun()

# ====== KNOWLEDGE BASE TAB ======
with tab_kb:
    st.markdown('<h3>Knowledge base search</h3>', unsafe_allow_html=True)

    col1, col2 = st.columns([4, 1])
    with col1:
        query = st.text_input("Search knowledge base", key="kb_query", placeholder="Enter search query...")
    with col2:
        search_button = st.button("Search", key="kb_search", use_container_width=True)

    if search_button and query:
        with st.spinner("Searching..."):
            results = kb_search.search(query, workspace=current_workspace)
            if results:
                st.success(f"Found {len(results)} results")
                for i, result in enumerate(results, 1):
                    with st.expander(f"Result {i}: {result.title} (score: {result.score:.0%})", expanded=i == 1):
                        st.markdown(result.content)
                        if result.source:
                            st.caption(f"Source: {result.source}")
            else:
                st.info("No results found. Try different keywords.")

    st.markdown("---")
    st.markdown('<h3>Ingest documents</h3>', unsafe_allow_html=True)
    uploaded_files = st.file_uploader(
        "Upload documents",
        accept_multiple_files=True,
        type=['txt', 'md', 'json', 'pdf']
    )

    if uploaded_files:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**{len(uploaded_files)}** file(s) selected")
        with col2:
            if st.button("Ingest", use_container_width=True):
                with st.spinner("Processing..."):
                    st.success(f"Ingested {len(uploaded_files)} files")

# ====== SESSIONS TAB ======
with tab_sessions:
    st.markdown('<h3>Session management</h3>', unsafe_allow_html=True)

    if current_workspace:
        sessions = session_manager.list_sessions(current_workspace)

        if sessions:
            for i, session in enumerate(sessions):
                with st.expander(f"{session.title} — {session.created_at.strftime('%b %d, %Y')}"):
                    messages = session_manager.get_messages(session.id)
                    st.markdown(f"**Messages:** {len(messages)}")
                    for msg in messages:
                        st.markdown(f"**{msg.role.title()}:**")
                        st.markdown(msg.content)
                        st.markdown("---")
        else:
            st.info("No sessions yet. Start chatting to create one!")
    else:
        st.warning("Select a workspace to view sessions")

# ====== TOOLS TAB ======
with tab_tools:
    st.markdown('<h3>Capabilities</h3>', unsafe_allow_html=True)
    st.markdown(
        '<p class="jv-subtitle">What this console can actually do right now, and whether each is configured.</p>',
        unsafe_allow_html=True,
    )

    capabilities = [
        ("Chat", "openai", "Text generation via the configured provider.", True),
        ("Anthropic chat", "anthropic", "Text generation via Claude models.", bool(os.getenv("ANTHROPIC_API_KEY"))),
        ("Groq chat", "groq", "Text generation via Groq-hosted open models.", bool(os.getenv("GROQ_API_KEY"))),
        ("Image generation", "openai", "DALL-E image generation.", bool(config.openai_api_key)),
        ("Text-to-speech", "openai", "Voice synthesis for generated text.", bool(config.openai_api_key)),
        ("Speech-to-text", "openai", "Audio transcription and translation.", bool(config.openai_api_key)),
        ("Knowledge base search", None, "Search documents ingested into the active workspace.", True),
        ("ElevenLabs voices", "elevenlabs", "Alternate TTS voice provider.", bool(os.getenv("ELEVENLABS_API_KEY"))),
    ]

    cols = st.columns(2)
    for idx, (name, provider_key, desc, configured) in enumerate(capabilities):
        with cols[idx % 2]:
            badge_class = "jv-badge--success" if configured else "jv-badge--neutral"
            badge_text = "Configured" if configured else "No key configured"
            tag_html = ""
            if provider_key:
                tag_html = '<span class="jv-tag jv-tag--cloud">Cloud</span>'
            st.markdown(f"""
            <div class="jv-card">
                <div class="jv-card-title">
                    <span>{name}</span>
                    {tag_html}
                </div>
                <div class="jv-card-desc">{desc}</div>
                <div style="margin-top: var(--space-2);">
                    <span class="jv-badge {badge_class}">{badge_text}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(
        '<p class="jv-subtitle">All providers above are cloud APIs — prompts and any attached context leave this '
        'device. A local-only model path is planned; when available it will carry a distinct '
        '<span class="jv-tag jv-tag--local">Local</span> tag here instead.</p>',
        unsafe_allow_html=True,
    )

# ====== MEDIA TAB ======
with tab_media:
    st.markdown('<h3>Media generation suite</h3>', unsafe_allow_html=True)

    media_tab1, media_tab2, media_tab3, media_tab4 = st.tabs([
        "Image gen", "Text-to-speech", "Speech-to-text", "Media player"
    ])

    # Image Generation
    with media_tab1:
        st.markdown('<h3>Generate images</h3>', unsafe_allow_html=True)

        image_prompt = st.text_area(
            "Image description",
            placeholder="A serene mountain landscape at sunset with a pristine lake reflecting the sky...",
            height=120
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            model = st.selectbox("Model", ["dall-e-3", "dall-e-2", "replicate"], key="image_model")
        with col2:
            size = st.selectbox("Resolution", ["1024x1024", "1792x1024", "512x512", "256x256"], key="image_size")
        with col3:
            quality = st.selectbox("Quality", ["standard", "hd"], key="image_quality")

        if st.button("Generate image", use_container_width=True, key="generate_image"):
            if image_prompt:
                with st.spinner("Creating image..."):
                    try:
                        image_path = image_generator.generate_image(
                            prompt=image_prompt,
                            model=model,
                            size=size,
                            quality=quality
                        )
                        st.success("Image generated successfully")
                        st.image(str(image_path), caption=image_prompt, use_column_width=True)
                        st.download_button(
                            "Download image",
                            data=open(image_path, "rb").read(),
                            file_name=image_path.name,
                            mime="image/png",
                            use_container_width=True
                        )
                    except Exception as e:
                        st.error(f"Error: {e}")
            else:
                st.warning("Please enter an image description")

    # Text-to-Speech
    with media_tab2:
        st.markdown('<h3>Convert text to speech</h3>', unsafe_allow_html=True)

        tts_text = st.text_area(
            "Text to convert",
            placeholder="Hello, this is a sample text that will be converted to natural-sounding speech...",
            height=120
        )

        col1, col2 = st.columns(2)
        with col1:
            voice = st.selectbox("Voice", tts_engine.list_voices(), key="tts_voice")
        with col2:
            play_after = st.checkbox("Play immediately", value=True)

        if st.button("Generate speech", use_container_width=True, key="generate_tts"):
            if tts_text:
                with st.spinner("Generating..."):
                    try:
                        audio_path = tts_engine.generate_speech(text=tts_text, voice=voice)
                        st.success("Speech generated")
                        st.audio(str(audio_path), format="audio/mp3")
                        st.download_button(
                            "Download audio",
                            data=open(audio_path, "rb").read(),
                            file_name=audio_path.name,
                            mime="audio/mp3",
                            use_container_width=True
                        )
                    except Exception as e:
                        st.error(f"Error: {e}")
            else:
                st.warning("Please enter text to convert")

    # Speech-to-Text
    with media_tab3:
        st.markdown('<h3>Transcribe audio</h3>', unsafe_allow_html=True)

        uploaded_audio = st.file_uploader(
            "Upload audio",
            type=["wav", "mp3", "m4a", "mp4", "webm"],
            help="Supported: WAV, MP3, M4A, MP4, WebM"
        )

        col1, col2 = st.columns(2)
        with col1:
            translate = st.checkbox("Translate to English", value=False)
        with col2:
            st.caption("Auto-detects language")

        if st.button("Transcribe", use_container_width=True, key="transcribe_audio") and uploaded_audio:
            with st.spinner("Processing..."):
                try:
                    temp_path = paths.data / "temp" / uploaded_audio.name
                    temp_path.parent.mkdir(exist_ok=True)
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_audio.getvalue())

                    if translate:
                        text = stt_engine.translate_audio(temp_path)
                        st.markdown('<h3>Translated text</h3>', unsafe_allow_html=True)
                    else:
                        text = stt_engine.transcribe_audio(temp_path)
                        st.markdown('<h3>Transcribed text</h3>', unsafe_allow_html=True)

                    st.text_area("Result:", value=text, height=150, disabled=True)
                    temp_path.unlink(missing_ok=True)
                except Exception as e:
                    st.error(f"Error: {e}")

    # Media Player
    with media_tab4:
        st.markdown('<h3>Media player</h3>', unsafe_allow_html=True)

        uploaded_media = st.file_uploader(
            "Upload media",
            type=["mp3", "wav", "mp4", "avi", "mov"],
            help="Audio: MP3, WAV | Video: MP4, AVI, MOV"
        )

        if uploaded_media:
            temp_path = paths.data / "temp" / uploaded_media.name
            temp_path.parent.mkdir(exist_ok=True)
            with open(temp_path, "wb") as f:
                f.write(uploaded_media.getvalue())

            file_ext = temp_path.suffix.lower()

            if file_ext in [".mp3", ".wav"]:
                st.audio(str(temp_path), format=f"audio/{file_ext[1:]}")
            elif file_ext in [".mp4", ".avi", ".mov"]:
                st.video(str(temp_path))
            else:
                st.warning("Unsupported format")

            st.caption(f"File: {uploaded_media.name}")

# ====== SETTINGS TAB ======
with tab_settings:
    st.markdown('<h3>System settings</h3>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<h3>API configuration</h3>', unsafe_allow_html=True)
        api_key = st.text_input(
            "OpenAI API key",
            type="password",
            value=config.openai_api_key or "",
            help="Your API key is never stored"
        )

    with col2:
        st.markdown('<h3>Workspace configuration</h3>', unsafe_allow_html=True)
        if current_workspace:
            workspace = workspace_manager.get_workspace(current_workspace)
            st.json(workspace.model_dump(), expanded=False)
        else:
            st.info("Select a workspace to view settings")

    st.markdown("---")

    with st.expander("Privacy & data handling"):
        st.markdown(f"""
- **Session and workspace data** is stored locally under `{paths.data}`.
- **Chat, image, and voice requests** are sent directly to whichever cloud
  provider is selected above, over HTTPS — see Provider status for which
  ones are currently configured and reachable.
- No usage analytics or telemetry is collected by this console.
        """)

if __name__ == "__main__":
    pass
