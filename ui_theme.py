"""Shared "Minimal Slate" visual theme for the Streamlit UI.

Import and call inject_shared_theme() once near the top of every page
(after st.set_page_config) so all pages render identically. This module is
CSS/markup only -- it changes no app behavior.
"""

import streamlit as st

MINIMAL_SLATE_CSS = """
<style>
:root {
    --ms-bg: #F7F8FA;
    --ms-surface: #FFFFFF;
    --ms-text: #1F2430;
    --ms-muted: #6B7280;
    --ms-border: #E2E4E9;
    --ms-border-soft: #ECEDF1;
    --ms-accent: #4F46E5;
    --ms-accent-hover: #4338CA;
    --ms-accent-soft: #EEF0FF;
    --ms-card-radius: 14px;
    --ms-input-radius: 8px;
    --ms-shadow-card: 0 1px 3px rgba(0, 0, 0, 0.06);
    --ms-font: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, "Helvetica Neue", Arial, sans-serif;
}

/* ---- Base ---- */
.stApp {
    font-family: var(--ms-font);
    background: var(--ms-bg);
    color: var(--ms-text);
}

.stApp p,
.stApp li,
.stMarkdown,
.stMarkdown p,
.stMarkdown li,
.stText,
.stCaption,
div[data-testid="stMarkdownContainer"] p {
    color: var(--ms-text);
    font-family: var(--ms-font);
}

div[data-testid="stCaptionContainer"],
div[data-testid="stCaptionContainer"] *,
div[data-testid="stForm"] small,
div[data-testid="stForm"] [data-testid="stMarkdownContainer"] small {
    color: var(--ms-muted) !important;
}

.block-container {
    max-width: 1420px;
    padding-top: 1.1rem;
    padding-bottom: 1.6rem;
    padding-left: 1.1rem;
    padding-right: 1.1rem;
}

a, .stApp a {
    color: var(--ms-accent);
}

/* ---- Headings ---- */
.stApp h1,
.stApp h2,
.stApp h3,
.stApp h4,
.stApp h5,
.stApp h6,
div[data-testid="stWidgetLabel"] > label,
div[data-testid="stExpander"] summary,
div[data-testid="stFileUploaderDropzoneInstructions"] {
    color: var(--ms-text) !important;
    font-family: var(--ms-font);
}

.stApp h1 { font-weight: 800; }
.stApp h2 { font-weight: 700; }
.stApp h3 {
    font-weight: 700;
    display: inline-block;
    padding-bottom: 0.2rem;
    border-bottom: 2px solid var(--ms-accent);
    margin-bottom: 0.8rem;
}

/* ---- Section label (small uppercase + underline accent) ---- */
.section-heading {
    display: inline-block;
    margin: 0.6rem 0 0.5rem 0;
    color: var(--ms-accent);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding-bottom: 0.35rem;
    border-bottom: 2px solid var(--ms-accent);
}

/* Card wrapper around a section (soft shadow, no heavy border) */
div[data-testid="stVerticalBlock"] div:has(> div > .section-heading) {
    border: 1px solid var(--ms-border-soft);
    border-radius: var(--ms-card-radius);
    padding: 0.75rem 1rem 0.9rem 1rem;
    background: var(--ms-surface);
    box-shadow: var(--ms-shadow-card);
}

div[data-testid="stVerticalBlock"] {
    gap: 0.6rem;
}

/* ---- Hero header (plain, no full-width color bar) ---- */
.hero-wrap {
    width: 100%;
    margin: 0;
    padding: 0.2rem 0 1rem 0;
}

.hero {
    width: 100%;
    margin: 0;
    padding: 0;
    background: transparent;
    color: var(--ms-text) !important;
    border: none;
    box-shadow: none;
}

.hero h1 {
    font-family: var(--ms-font);
    margin: 0 0 0.2rem 0;
    font-size: 1.7rem;
    line-height: 1.3;
    font-weight: 800;
    color: var(--ms-text) !important;
    display: block;
    border-bottom: none;
    padding-bottom: 0;
}

.hero p {
    margin: 0;
    font-size: 0.98rem;
    line-height: 1.45;
    color: var(--ms-muted) !important;
}

/* ---- Flow / order-of-service item rows ---- */
.flow-item {
    margin: 0.5rem 0 0.4rem 0;
    padding: 0.55rem 0.7rem;
    border: 1px solid var(--ms-border-soft);
    border-left: 3px solid var(--ms-accent);
    background: var(--ms-surface);
    color: var(--ms-text) !important;
    border-radius: 8px;
    font-weight: 600;
    line-height: 1.45;
    overflow-wrap: anywhere;
    box-shadow: var(--ms-shadow-card);
}

/* ---- Inputs ---- */
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div,
div[data-baseweb="base-input"] {
    border-radius: var(--ms-input-radius);
    border: 1px solid var(--ms-border);
    background: var(--ms-surface);
    box-shadow: none;
    min-height: 2.5rem;
}

div[data-baseweb="input"] input,
div[data-baseweb="base-input"] input {
    padding-top: 0.55rem;
    padding-bottom: 0.55rem;
}

div[data-baseweb="select"] > div:hover,
div[data-baseweb="input"] > div:hover {
    border-color: var(--ms-accent);
}

div[data-baseweb="select"] > div:focus-within,
div[data-baseweb="input"] > div:focus-within {
    border-color: var(--ms-accent);
    box-shadow: 0 0 0 3px var(--ms-accent-soft);
}

textarea,
.stTextArea textarea {
    border-radius: var(--ms-input-radius) !important;
    border: 1px solid var(--ms-border) !important;
}

textarea:focus,
.stTextArea textarea:focus {
    border-color: var(--ms-accent) !important;
    box-shadow: 0 0 0 3px var(--ms-accent-soft) !important;
}

div[data-baseweb="input"] input,
div[data-baseweb="input"] input[type="number"],
div[data-baseweb="select"] input,
div[data-baseweb="select"] div,
div[data-baseweb="select"] span,
div[data-baseweb="select"] [role="combobox"],
div[data-baseweb="popover"] [role="option"] {
    color: var(--ms-text) !important;
    -webkit-text-fill-color: var(--ms-text) !important;
}

div[data-baseweb="input"] input::placeholder,
div[data-baseweb="select"] input::placeholder {
    color: var(--ms-muted) !important;
    -webkit-text-fill-color: var(--ms-muted) !important;
    opacity: 1;
}

div[data-testid="stWidgetLabel"] > label {
    color: var(--ms-text) !important;
    font-weight: 600;
    line-height: 1.45;
    overflow-wrap: anywhere;
}

/* ---- Tag / chip pills (multiselect: verses, chorus, etc.) ---- */
/* Streamlit/BaseWeb renders these as <span data-baseweb="tag">, not <div>. */
[data-baseweb="tag"] {
    background: var(--ms-accent-soft) !important;
    border-radius: 999px !important;
    border: none !important;
}

[data-baseweb="tag"] svg {
    fill: var(--ms-accent) !important;
}

/* Higher specificity than the generic `div[data-baseweb="select"] span`
   text-color rule below, which would otherwise win and force these back
   to the default text color. */
div[data-baseweb="select"] [data-baseweb="tag"] span,
[data-baseweb="tag"] span[title] {
    color: var(--ms-accent) !important;
    -webkit-text-fill-color: var(--ms-accent) !important;
}

/* ---- Tabs ---- */
div[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: transparent;
    border-bottom: 1px solid var(--ms-border);
    gap: 0.25rem;
}

div[data-testid="stTabs"] [data-baseweb="tab"] {
    border-radius: 8px 8px 0 0;
    color: var(--ms-muted) !important;
    font-weight: 600;
}

div[data-testid="stTabs"] [aria-selected="true"] {
    background: var(--ms-accent-soft);
    color: var(--ms-accent) !important;
    box-shadow: inset 0 -2px 0 var(--ms-accent);
}

/* ---- Buttons ---- */
.stButton > button {
    border-radius: var(--ms-input-radius);
    border: 1px solid var(--ms-accent);
    background: var(--ms-accent);
    color: #FFFFFF;
    font-weight: 700;
    min-height: 2.6rem;
    box-shadow: none;
}

.stButton > button:hover {
    background: var(--ms-accent-hover);
    border-color: var(--ms-accent-hover);
    color: #FFFFFF;
}

.stButton > button:focus:not(:active) {
    box-shadow: 0 0 0 3px var(--ms-accent-soft);
}

/* Secondary/download buttons keep the same shape but a lighter fill */
.stDownloadButton > button {
    border-radius: var(--ms-input-radius);
    border: 1px solid var(--ms-border);
    background: var(--ms-surface);
    color: var(--ms-accent);
    font-weight: 700;
    box-shadow: none;
}

.stDownloadButton > button:hover {
    border-color: var(--ms-accent);
    background: var(--ms-accent-soft);
}

/* ---- Alerts / expanders ---- */
div[data-testid="stAlert"] {
    border-radius: var(--ms-input-radius);
    border: 1px solid var(--ms-border-soft);
    box-shadow: var(--ms-shadow-card);
}

div[data-testid="stExpander"] {
    border: 1px solid var(--ms-border-soft);
    border-radius: var(--ms-card-radius);
    box-shadow: var(--ms-shadow-card);
}

@media (max-width: 900px) {
    .hero h1 {
        font-size: 1.35rem;
    }

    .block-container {
        padding-left: 0.75rem;
        padding-right: 0.75rem;
    }
}
</style>
"""


def inject_shared_theme():
    """Inject the shared Minimal Slate CSS. Call once near the top of every page."""
    st.markdown(MINIMAL_SLATE_CSS, unsafe_allow_html=True)
