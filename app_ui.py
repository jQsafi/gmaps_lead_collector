import os
import sys
import time
import subprocess
import io
import threading
from datetime import datetime, date
import streamlit as st
import pandas as pd
from scraper import scrape_google_maps, batch_scrape, DEFAULT_FIELDS
from whatsapp_sender import (
    format_whatsapp_number,
    check_login_status,
    launch_whatsapp_login_window,
    bulk_send_whatsapp,
    send_test_whatsapp_message,
    parse_manual_numbers,
    close_whatsapp_session
)
from campaign_engine import run_campaign
import database
import groq_helper

@st.cache_resource
def ensure_playwright_browsers():
    """Ensure Chromium browser binary is installed on Streamlit Cloud."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            exec_path = p.chromium.executable_path
            if not os.path.exists(exec_path):
                subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
    except Exception:
        try:
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        except Exception:
            pass

ensure_playwright_browsers()

def inject_gtm_into_index_html():
    """Inject Google Tag Manager directly into Streamlit's static index.html template."""
    try:
        from pathlib import Path
        index_file = Path(st.__file__).parent / "static" / "index.html"
        if index_file.exists():
            html_text = index_file.read_text(encoding="utf-8")
            gtm_id = "GTM-W7P72R2N"
            if gtm_id not in html_text:
                gtm_head_code = f"""<head>
<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':
new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
}})(window,document,'script','dataLayer','{gtm_id}');</script>
<!-- End Google Tag Manager -->"""
                gtm_body_code = f"""<body>
<!-- Google Tag Manager (noscript) -->
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id={gtm_id}"
height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
<!-- End Google Tag Manager (noscript) -->"""
                if "<head>" in html_text:
                    html_text = html_text.replace("<head>", gtm_head_code, 1)
                if "<body>" in html_text:
                    html_text = html_text.replace("<body>", gtm_body_code, 1)
                index_file.write_text(html_text, encoding="utf-8")
    except Exception:
        pass

inject_gtm_into_index_html()

st.set_page_config(
    page_title="Google Maps Lead & Phone Collector",
    page_icon="📍",
    layout="wide"
)

# Active GTM Runtime Injector
import streamlit.components.v1 as components
components.html(
    """
    <script>
    (function() {
        try {
            var targetWin = window.parent || window;
            var targetDoc = targetWin.document || document;
            if (!targetWin.dataLayer) {
                targetWin.dataLayer = [];
            }
            if (!targetWin._gtm_loaded) {
                targetWin._gtm_loaded = true;
                (function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
                new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
                j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
                'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
                })(targetWin, targetDoc, 'script', 'dataLayer', 'GTM-W7P72R2N');
            }
        } catch(e) {
            (function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
            new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
            j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
            'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
            })(window,document,'script','dataLayer','GTM-W7P72R2N');
        }
    })();
    </script>
    <noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-W7P72R2N"
    height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
    """,
    height=0,
    width=0
)

if "db_url" not in st.session_state:
    st.session_state["db_url"] = database.normalize_db_url()

# Custom CSS Design System
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');

html, body {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Restore and force Material Icons for Streamlit system icons */
[data-testid="stIconMaterial"],
[data-testid*="stIcon"],
[data-testid="stSidebarCollapseButton"] *,
button[kind="header"] *,
[class*="material-symbols"],
[class*="material-icons"],
.material-symbols-rounded,
.material-symbols-outlined,
.material-icons {
    font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Icons' !important;
    font-feature-settings: 'liga' !important;
    -webkit-font-feature-settings: 'liga' !important;
    text-transform: none !important;
    letter-spacing: normal !important;
    word-wrap: normal !important;
    white-space: nowrap !important;
    direction: ltr !important;
}

/* Apply Plus Jakarta Sans to standard text containers without affecting icon fonts */
.main, .stMarkdown, .stText, p, h1, h2, h3, h4, h5, h6, input, textarea, select, label, .stMetric {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* Hero Section */
.hero-wrapper {
    background: linear-gradient(135deg, rgba(37, 99, 235, 0.07) 0%, rgba(6, 182, 212, 0.05) 50%, rgba(99, 102, 241, 0.06) 100%);
    border: 1px solid rgba(226, 232, 240, 0.85);
    border-radius: 20px;
    padding: 2.2rem 2.4rem 1.8rem 2.4rem;
    margin-bottom: 1.8rem;
    position: relative;
    box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.04);
}

.hero-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: linear-gradient(135deg, rgba(37, 99, 235, 0.12) 0%, rgba(6, 182, 212, 0.12) 100%);
    color: #2563EB;
    border: 1px solid rgba(37, 99, 235, 0.25);
    border-radius: 9999px;
    padding: 0.35rem 0.9rem;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-bottom: 0.85rem;
}

.hero-title {
    font-size: 2.4rem;
    font-weight: 800;
    line-height: 1.15;
    background: linear-gradient(135deg, #0F172A 0%, #1E40AF 45%, #2563EB 80%, #06B6D4 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.03em;
    margin-bottom: 0.5rem;
}

.hero-subtitle {
    font-size: 1.02rem;
    color: #475569;
    max-width: 860px;
    line-height: 1.6;
    margin-bottom: 1.2rem;
}

.feature-ribbon {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
    gap: 12px;
    margin-top: 1rem;
}

.feature-pill {
    background: rgba(255, 255, 255, 0.9);
    border: 1px solid rgba(226, 232, 240, 0.95);
    border-radius: 12px;
    padding: 0.75rem 1rem;
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 0.84rem;
    font-weight: 600;
    color: #1E293B;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.02);
}

.feature-pill:hover {
    transform: translateY(-2px);
    border-color: #93C5FD;
    box-shadow: 0 6px 18px -2px rgba(37, 99, 235, 0.12);
}

.feature-pill-icon {
    font-size: 1.25rem;
    flex-shrink: 0;
}

/* Streamlit Tabs Modern Segmented Control */
div[data-baseweb="tab-list"] {
    background: #F1F5F9;
    border-radius: 14px;
    padding: 5px;
    gap: 6px;
    border: 1px solid #E2E8F0;
    margin-bottom: 1.6rem;
}

div[data-baseweb="tab-list"] button {
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.92rem !important;
    color: #64748B !important;
    padding: 0.55rem 1.1rem !important;
    border: none !important;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
}

div[data-baseweb="tab-list"] button:hover {
    color: #0F172A !important;
    background: rgba(255, 255, 255, 0.7) !important;
}

div[data-baseweb="tab-list"] button[aria-selected="true"] {
    background: #FFFFFF !important;
    color: #2563EB !important;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06), 0 1px 3px rgba(0, 0, 0, 0.03) !important;
}

div[data-baseweb="tab-highlight"] {
    display: none !important;
}

/* Primary Button Styling */
button[kind="primary"] {
    background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    border-radius: 10px !important;
    border: none !important;
    padding: 0.75rem 1.5rem !important;
    box-shadow: 0 6px 18px -3px rgba(37, 99, 235, 0.35) !important;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
}

button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 10px 24px -4px rgba(37, 99, 235, 0.45) !important;
    filter: brightness(1.04) !important;
}

button[kind="primary"]:active {
    transform: translateY(0px) !important;
}

/* Secondary Button Styling */
button[kind="secondary"] {
    border-radius: 9px !important;
    font-weight: 600 !important;
    border: 1px solid #CBD5E1 !important;
    background: #FFFFFF !important;
    transition: all 0.2s ease !important;
}

button[kind="secondary"]:hover {
    border-color: #2563EB !important;
    color: #2563EB !important;
    background: #EFF6FF !important;
}

/* Live Simulation Browser Window Mock */
.browser-window-frame {
    background: #0F172A;
    border-radius: 14px 14px 0 0;
    padding: 10px 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0px;
    border: 1px solid rgba(255, 255, 255, 0.1);
}

.browser-window-dots {
    display: flex;
    gap: 6px;
}

.window-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
}

.dot-red { background: #EF4444; }
.dot-yellow { background: #F59E0B; }
.dot-green { background: #10B981; }

.browser-window-title {
    color: #94A3B8;
    font-size: 0.75rem;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 500;
}

.live-badge {
    background: rgba(239, 68, 68, 0.2);
    color: #EF4444;
    border: 1px solid rgba(239, 68, 68, 0.4);
    font-size: 0.7rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 6px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    animation: pulse-live 2s infinite;
}

@keyframes pulse-live {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.55; }
}

/* Reusable Badges */
.pill-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 4px 11px;
    border-radius: 9999px;
    font-size: 0.8rem;
    font-weight: 700;
}

.pill-primary {
    background: #EFF6FF;
    color: #1D4ED8;
    border: 1px solid #BFDBFE;
}

.pill-success {
    background: #ECFDF5;
    color: #047857;
    border: 1px solid #A7F3D0;
}

/* Section Header Bar */
.tab-header-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 0.6rem;
}

.tab-header-card h3 {
    margin: 0 !important;
    font-size: 1.45rem !important;
    font-weight: 700 !important;
    color: #0F172A !important;
}

/* Dark mode adaptability */
@media (prefers-color-scheme: dark) {
    .hero-wrapper {
        background: linear-gradient(135deg, rgba(30, 58, 138, 0.22) 0%, rgba(6, 182, 212, 0.12) 50%, rgba(99, 102, 241, 0.18) 100%);
        border-color: rgba(255, 255, 255, 0.12);
    }
    .hero-title {
        background: linear-gradient(135deg, #F8FAFC 0%, #93C5FD 50%, #38BDF8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .hero-subtitle {
        color: #CBD5E1;
    }
    .feature-pill {
        background: rgba(30, 41, 59, 0.85);
        border-color: rgba(255, 255, 255, 0.1);
        color: #F1F5F9;
    }
    div[data-baseweb="tab-list"] {
        background: #1E293B;
        border-color: #334155;
    }
    div[data-baseweb="tab-list"] button[aria-selected="true"] {
        background: #0F172A !important;
        color: #60A5FA !important;
    }
    .tab-header-card h3 {
        color: #F8FAFC !important;
    }
    .custom-navbar {
        background: rgba(15, 23, 42, 0.85);
        border-color: rgba(255, 255, 255, 0.1);
    }
    .brand-title-text {
        color: #F8FAFC;
    }
    .brand-sub-text {
        color: #94A3B8;
    }
    .nav-status-chip {
        background: #1E293B;
        border-color: #334155;
        color: #CBD5E1;
    }
    .nav-profile-link {
        background: rgba(37, 99, 235, 0.2);
        color: #93C5FD;
        border-color: rgba(147, 197, 253, 0.3);
    }
    .nav-profile-link:hover {
        background: #2563EB;
        color: #FFFFFF !important;
    }
}

/* Clean Streamlit Default Chrome */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header[data-testid="stHeader"] {
    background: transparent !important;
}
.block-container {
    padding-top: 1.25rem !important;
    padding-bottom: 3.5rem !important;
}

/* Make Left Sidebar completely unscrollable & ultra-compact */
section[data-testid="stSidebar"] {
    overflow: hidden !important;
}

section[data-testid="stSidebar"] > div:first-child {
    overflow: hidden !important;
    padding: 0.85rem 0.9rem !important;
    height: 100% !important;
}

.sidebar-status-box {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 9px;
    padding: 7px 9px;
    display: grid;
    grid-template-columns: 1fr;
    gap: 5px;
    margin-bottom: 0.65rem;
}

.sidebar-status-item {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.72rem;
    color: #334155;
    white-space: nowrap;
}

.status-indicator-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
}

.dot-online {
    background: #10B981;
    box-shadow: 0 0 4px rgba(16, 185, 129, 0.4);
}

.dot-idle {
    background: #94A3B8;
}

@media (prefers-color-scheme: dark) {
    .sidebar-status-box {
        background: #1E293B;
        border-color: #334155;
    }
    .sidebar-status-item {
        color: #CBD5E1;
    }
}

/* Fixed Ultra-Compact Bottom Footer */
.fixed-compact-footer {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    width: 100%;
    height: 32px;
    background: rgba(255, 255, 255, 0.94);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-top: 1px solid rgba(226, 232, 240, 0.95);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 1.5rem;
    font-size: 0.74rem;
    color: #64748B;
    z-index: 99999;
    box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.02);
    box-sizing: border-box;
}

.fixed-compact-footer a {
    color: #2563EB;
    font-weight: 600;
    text-decoration: none;
    transition: color 0.15s ease;
}

.fixed-compact-footer a:hover {
    color: #1D4ED8;
    text-decoration: underline;
}

@media (prefers-color-scheme: dark) {
    .fixed-compact-footer {
        background: rgba(15, 23, 42, 0.94);
        border-top-color: rgba(255, 255, 255, 0.08);
        color: #94A3B8;
        box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.3);
    }
    .fixed-compact-footer a {
        color: #60A5FA;
    }
}

/* Custom Top Navigation Bar */
.custom-navbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.85rem 1.4rem;
    background: rgba(255, 255, 255, 0.9);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border: 1px solid rgba(226, 232, 240, 0.95);
    border-radius: 16px;
    margin-bottom: 1.3rem;
    box-shadow: 0 4px 18px -2px rgba(0, 0, 0, 0.03);
}

.nav-brand-group {
    display: flex;
    align-items: center;
    gap: 12px;
}

.brand-title-text {
    font-size: 1.25rem;
    font-weight: 800;
    color: #0F172A;
    letter-spacing: -0.02em;
    display: flex;
    align-items: center;
    gap: 8px;
    line-height: 1.2;
}

.brand-badge {
    background: linear-gradient(135deg, #2563EB 0%, #06B6D4 100%);
    color: #FFFFFF;
    font-size: 0.65rem;
    font-weight: 800;
    padding: 2px 7px;
    border-radius: 6px;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}

.brand-sub-text {
    font-size: 0.76rem;
    color: #64748B;
    font-weight: 500;
}

.nav-actions-group {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
}

.nav-status-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px;
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 9999px;
    font-size: 0.78rem;
    font-weight: 600;
    color: #334155;
}

.nav-profile-link {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 13px;
    background: linear-gradient(135deg, rgba(37, 99, 235, 0.08) 0%, rgba(6, 182, 212, 0.08) 100%);
    border: 1px solid rgba(37, 99, 235, 0.22);
    border-radius: 9999px;
    font-size: 0.78rem;
    font-weight: 700;
    color: #2563EB;
    text-decoration: none;
    transition: all 0.2s ease;
}

.nav-profile-link:hover {
    background: #2563EB;
    color: #FFFFFF !important;
    border-color: #2563EB;
    text-decoration: none;
}
</style>
""", unsafe_allow_html=True)

# Vector Brand Logo (Radar + Map Pin)
GH_LOGO_SVG = """<svg width="38" height="38" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="48" height="48" rx="12" fill="url(#gh-grad)"/>
  <circle cx="24" cy="21" r="14" stroke="white" stroke-opacity="0.25" stroke-width="2" stroke-dasharray="3 3"/>
  <circle cx="24" cy="21" r="9" stroke="white" stroke-opacity="0.4" stroke-width="1.8"/>
  <path d="M24 9C18.477 9 14 13.477 14 19C14 25.5 24 37 24 37C24 37 34 25.5 34 19C34 13.477 29.523 9 24 9Z" fill="white"/>
  <circle cx="24" cy="19" r="4.5" fill="url(#gh-grad-center)"/>
  <defs>
    <linearGradient id="gh-grad" x1="0" y1="0" x2="48" y2="48" gradientUnits="userSpaceOnUse">
      <stop stop-color="#1E40AF"/>
      <stop offset="0.5" stop-color="#2563EB"/>
      <stop offset="1" stop-color="#06B6D4"/>
    </linearGradient>
    <linearGradient id="gh-grad-center" x1="19.5" y1="14.5" x2="28.5" y2="23.5" gradientUnits="userSpaceOnUse">
      <stop stop-color="#1E40AF"/>
      <stop offset="1" stop-color="#0284C7"/>
    </linearGradient>
  </defs>
</svg>"""

# Dynamic connectivity status
is_wa_nav_ok = st.session_state.get("whatsapp_logged_in", False) or check_login_status()
wa_badge_html = '<span style="color:#10B981; font-weight:bold;">●</span> WhatsApp Active' if is_wa_nav_ok else '<span style="color:#94A3B8;">○</span> WhatsApp Idle'
db_badge_html = '<span style="color:#10B981; font-weight:bold;">●</span> Database Synced'

# Branded Sidebar (Unscrollable & Ultra-Compact)
with st.sidebar:
    wa_dot = '<span class="status-indicator-dot dot-online"></span>' if is_wa_nav_ok else '<span class="status-indicator-dot dot-idle"></span>'
    wa_text = "WhatsApp: <strong>Active</strong>" if is_wa_nav_ok else "WhatsApp: <strong>Idle</strong>"
    leads_in_mem = len(st.session_state.get("active_leads_df", []))

    sidebar_html = f"""<div style="padding: 0; margin: 0;">
<div style="display:flex; align-items:center; gap:9px; margin-bottom: 0.6rem;">
{GH_LOGO_SVG}
<div>
<div style="font-size:1.05rem; font-weight:800; color:#0F172A; line-height:1.2;">GeoHunter <span style="font-size:0.6rem; background:linear-gradient(135deg, #2563EB, #06B6D4); color:#fff; padding:1px 5px; border-radius:4px;">PRO</span></div>
<div style="font-size:0.7rem; color:#64748B;">v2.5 Enterprise</div>
</div>
</div>
<div style="font-size:0.68rem; font-weight:700; color:#475569; text-transform:uppercase; letter-spacing:0.04em; margin-bottom:3px;">⚡ System Health</div>
<div class="sidebar-status-box">
<div class="sidebar-status-item">{wa_dot}<span>{wa_text}</span></div>
<div class="sidebar-status-item"><span class="status-indicator-dot dot-online"></span><span>Database: <strong>Online</strong></span></div>
<div class="sidebar-status-item"><span class="status-indicator-dot dot-online"></span><span>AI Core: <strong>Ready</strong></span></div>
<div class="sidebar-status-item"><span class="status-indicator-dot dot-online"></span><span>Browser: <strong>Ready</strong></span></div>
</div>
<div style="display:flex; align-items:center; justify-content:space-between; background:rgba(37,99,235,0.06); border:1px solid rgba(37,99,235,0.18); border-radius:8px; padding:5px 9px; margin-bottom:0.6rem;">
<span style="font-size:0.73rem; color:#1E40AF; font-weight:600;">📊 Cached Leads</span>
<span style="font-size:0.85rem; color:#1E40AF; font-weight:800;">{leads_in_mem:,}</span>
</div>
<div style="border-top:1px solid #E2E8F0; padding-top:6px; font-size:0.7rem; color:#64748B; line-height:1.4;">
<div><strong>Shafayat Hossain</strong> &bull; <a href="https://jqsafi.github.io/" target="_blank" style="color:#2563EB; text-decoration:none; font-weight:600;">Portfolio ↗</a></div>
<div style="font-size:0.64rem; opacity:0.8;">© 2026 All rights reserved</div>
</div>
</div>"""
    st.markdown(sidebar_html, unsafe_allow_html=True)

# Top Navigation Bar
st.markdown(f"""
<div class="custom-navbar">
    <div class="nav-brand-group">
        {GH_LOGO_SVG}
        <div>
            <div class="brand-title-text">
                GeoHunter <span class="brand-badge">PRO v2.5</span>
            </div>
            <div class="brand-sub-text">Google Maps B2B Lead Intelligence & WhatsApp Outreach Engine</div>
        </div>
    </div>
    <div class="nav-actions-group">
        <div class="nav-status-chip">{wa_badge_html}</div>
        <div class="nav-status-chip">{db_badge_html}</div>
        <a href="https://jqsafi.github.io/" target="_blank" class="nav-profile-link">
            <span>Shafayat Hossain</span>
            <span style="font-size:0.8rem;">↗</span>
        </a>
    </div>
</div>
""", unsafe_allow_html=True)

# Hero Banner
st.markdown("""
<div class="hero-wrapper">
    <div class="hero-badge">
        <span>⚡ GeoHunter Pro Enterprise Suite v2.5</span>
    </div>
    <div class="hero-title">
        📍 Google Maps Lead & Outreach Engine
    </div>
    <div class="hero-subtitle">
        High-velocity local B2B lead generation with automated phone extraction, AI sales copywriting, and direct WhatsApp Web messaging campaigns.
    </div>
    <div class="feature-ribbon">
        <div class="feature-pill">
            <span class="feature-pill-icon">📍</span>
            <div><strong>Precision Scraping</strong><br><span style="font-size:0.75rem;opacity:0.8;">Phones, Websites, Ratings & Addresses</span></div>
        </div>
        <div class="feature-pill">
            <span class="feature-pill-icon">🧠</span>
            <div><strong>AI Sales Strategist</strong><br><span style="font-size:0.75rem;opacity:0.8;">B2B Target Buyer & High-Intent Queries</span></div>
        </div>
        <div class="feature-pill">
            <span class="feature-pill-icon">💬</span>
            <div><strong>WhatsApp Campaign</strong><br><span style="font-size:0.75rem;opacity:0.8;">1-Click QR Session + Media Attachments</span></div>
        </div>
        <div class="feature-pill">
            <span class="feature-pill-icon">🗄️</span>
            <div><strong>Cloud Database Vault</strong><br><span style="font-size:0.75rem;opacity:0.8;">Supabase, PostgreSQL, Neon & SQLite Sync</span></div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Helper function for live simulation header
def get_browser_window_frame(title_sub: str = "Chromium Live Session"):
    return f"""
    <div class="browser-window-frame">
        <div class="browser-window-dots">
            <div class="window-dot dot-red"></div>
            <div class="window-dot dot-yellow"></div>
            <div class="window-dot dot-green"></div>
        </div>
        <div class="browser-window-title">playwright://chromium &bull; {title_sub}</div>
        <div class="live-badge">● LIVE</div>
    </div>
    """

# Helper function to render 4-col metric cards
def render_leads_metric_summary(df: pd.DataFrame):
    if df is None or df.empty:
        return
    m1, m2, m3, m4 = st.columns(4)
    total_leads = len(df)
    phones_count = len(df[df["Phone"].astype(str).str.strip().ne("")]) if "Phone" in df.columns else 0
    web_count = len(df[df["Website"].astype(str).str.strip().ne("")]) if "Website" in df.columns else 0
    phone_rate = f"{(phones_count / total_leads * 100):.0f}%" if total_leads > 0 else "0%"
    
    with m1:
        st.metric("Total Extracted", f"{total_leads:,}")
    with m2:
        st.metric("Phone Numbers", f"{phones_count:,}", delta=phone_rate)
    with m3:
        st.metric("Websites", f"{web_count:,}")
    with m4:
        st.metric("Phone Coverage", phone_rate)

# Tabs: Campaigns, Reports, AI Strategist, Single Search, Batch Search, WhatsApp, Remote Database
tab_camp, tab_rep, tab_ai, tab1, tab2, tab3, tab4 = st.tabs([
    "🚀 Automated Campaigns (Auto-Scrape & Send)",
    "📊 Date/Time Campaign Reports",
    "💡 AI Sales Strategist",
    "🔍 Single Search", 
    "🗺️ Multi-Location / Multi-Keyword Search", 
    "💬 WhatsApp Manual Outreach", 
    "🗄️ Remote Database Archive"
])

with tab_camp:
    st.markdown("""
    <div class="tab-header-card">
        <div style="display:flex; align-items:center; gap:12px;">
            <span style="font-size:1.6rem;">🚀</span>
            <div>
                <h3 style="margin:0; font-size:1.35rem; font-weight:700;">Automated Campaign Engine</h3>
                <span style="font-size:0.83rem; color:#64748B;">Continuous pipeline: scrape Google Maps, store in database, and immediately dispatch WhatsApp messages with duplicate protection</span>
            </div>
        </div>
        <span class="pill-badge pill-primary">Pipeline V3</span>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("Set up and launch an automated lead generation & outreach campaign. Leads are stored to the database as they are found, and WhatsApp messages are sent instantly with pause, resume, stop, and anti-duplicate rules.")

    if "camp_control_state" not in st.session_state:
        st.session_state["camp_control_state"] = {"paused": False, "stopped": False}
    if "camp_msg_content_val" not in st.session_state:
        st.session_state["camp_msg_content_val"] = "Hello {Name}, we noticed your business ({Category}) in {Address}. Are you currently accepting new orders/clients?"
    if "camp_locs_text" not in st.session_state:
        st.session_state["camp_locs_text"] = "stationary shop in uttara\nstationary shop in dhanmondi\nstationary shop in mirpur"

    col_c1, col_c2 = st.columns([1.4, 1])

    with col_c1:
        # Step 1: Campaign Name
        st.markdown("#### 1️⃣ Step 1: Campaign Identity")
        all_past_camps = database.get_all_campaigns(db_url=st.session_state.get("db_url"))
        past_camp_names = ["-- Create New Campaign --"] + ([f"#{row['ID']} - {row['Name']} ({row['Status']})" for _, row in all_past_camps.iterrows()] if not all_past_camps.empty else [])
        
        sel_camp_mode = st.selectbox("Campaign Mode:", options=past_camp_names, key="sel_camp_mode_choice")
        
        if sel_camp_mode == "-- Create New Campaign --":
            camp_name = st.text_input("Campaign Name *:", value=st.session_state.get("saved_camp_name", f"Campaign {datetime.now().strftime('%b %d - %H:%M')}"), placeholder="e.g. Uttara Stationery Super Sale", key="input_camp_name")
            current_active_camp_id = None
        else:
            camp_id_match = re.search(r"#(\d+)", sel_camp_mode)
            current_active_camp_id = int(camp_id_match.group(1)) if camp_id_match else None
            camp_data = database.get_campaign(current_active_camp_id, db_url=st.session_state.get("db_url")) if current_active_camp_id else {}
            camp_name = camp_data.get("Name", "Loaded Campaign")
            st.info(f"Loaded Campaign #{current_active_camp_id}: **{camp_name}** | Status: **{camp_data.get('Status')}**")
            if st.session_state.get("loaded_campaign_id_tracker") != current_active_camp_id:
                st.session_state["loaded_campaign_id_tracker"] = current_active_camp_id
                if camp_data.get("Message Template"):
                    st.session_state["camp_msg_content_val"] = camp_data["Message Template"]
                if camp_data.get("Locations"):
                    st.session_state["camp_locs_text"] = camp_data["Locations"]
                st.rerun()

        st.markdown("---")

        # Step 2: Campaign Message
        st.markdown("#### 2️⃣ Step 2: Campaign Message")
        
        # Saved Messages Memory selector
        saved_tpls = database.get_saved_message_templates(db_url=st.session_state.get("db_url"))
        if saved_tpls:
            tpl_options = ["-- Select from Saved Message Memory --"] + [f"{t['Title']}: {t['Content'][:40]}..." for t in saved_tpls]
            sel_saved_tpl = st.selectbox("📚 Memory Templates (Do not re-type):", options=tpl_options, key="sel_saved_tpl_key")
            if sel_saved_tpl != "-- Select from Saved Message Memory --":
                for t in saved_tpls:
                    if sel_saved_tpl.startswith(t['Title']):
                        if st.session_state.get("camp_msg_content_val") != t["Content"]:
                            st.session_state["camp_msg_content_val"] = t["Content"]
                            st.rerun()
                        break

        # AI Message Generator Expander
        with st.expander("🪄 Write Message with AI Copywriter Prompt", expanded=False):
            st.caption("Type a question or prompt describing what you want to offer. AI will write a tailored pitch:")
            ai_camp_prompt = st.text_input("AI Copywriter Prompt:", placeholder="e.g. Write a friendly 2-sentence pitch offering POS software with free demo", key="input_ai_camp_prompt")
            col_ai_btn1, col_ai_btn2 = st.columns([1, 1])
            with col_ai_btn1:
                if st.button("✨ Generate Message with AI", key="btn_gen_camp_ai_msg"):
                    if ai_camp_prompt.strip():
                        with st.spinner("AI is crafting your cold pitch..."):
                            gen_msg = groq_helper.generate_outreach_template(goal=ai_camp_prompt.strip())
                            st.session_state["last_gen_camp_ai_msg"] = gen_msg
                    else:
                        st.warning("Please enter a prompt.")
            
            last_ai_generated = st.session_state.get("last_gen_camp_ai_msg", "")
            if last_ai_generated:
                st.info(f"**Generated Pitch:**\n\n{last_ai_generated}")
                with col_ai_btn2:
                    if st.button("📥 Place Message into Box", key="btn_place_ai_msg_box"):
                        st.session_state["camp_msg_content_val"] = last_ai_generated
                        st.success("✅ Placed into message box!")
                        st.rerun()

        camp_message_text = st.text_area(
            "Campaign Message Template (Supports dynamic variables):",
            height=110,
            key="camp_msg_content_val"
        )
        st.caption("💡 Supported dynamic variables: `{Name}`, `{Category}`, `{Address}`, `{Phone}`, `{Website}`")

        # Save to memory button
        if st.button("💾 Save Message to Memory for Future Campaigns", key="btn_save_tpl_mem"):
            if camp_message_text.strip():
                database.save_message_template(
                    title=f"{camp_name[:25]} Pitch",
                    content=camp_message_text.strip(),
                    db_url=st.session_state.get("db_url")
                )
                st.success("✅ Message saved to Memory! You can select it in any future campaign without re-typing.")
                st.rerun()

        # Optional media attachment
        camp_media_file = st.file_uploader("📎 Attach Promo Media (Optional - Image, PDF brochure, Catalog):", type=["png", "jpg", "jpeg", "pdf", "mp4"], key="camp_media_up")

    with col_c2:
        # Step 3: Target Location (Single or Multiple)
        st.markdown("#### 3️⃣ Step 3: Target Locations")
        st.caption("Enter keywords and locations (one per line). User can edit or add locations when paused/stopped:")
        camp_locations_input = st.text_area(
            "Target Search Queries & Locations:",
            height=115,
            key="camp_locs_text"
        )
        
        loc_col1, loc_col2 = st.columns(2)
        with loc_col1:
            camp_max_per_loc = st.number_input("Max Leads / Location:", min_value=1, max_value=200, value=15, step=5, key="camp_max_lim")
        with loc_col2:
            camp_delay = st.slider("Delay (seconds):", min_value=3, max_value=30, value=6, key="camp_delay_val")

        camp_cc = st.text_input("Default Country Code (without +):", value="880", key="camp_cc_val")
        camp_visible_browser = st.checkbox("👁️ Visible Browser Mode", value=False, help="Show Chromium automation window on your desktop", key="camp_vis_mode")

        st.markdown("---")

        # Step 4: Connect with WhatsApp
        st.markdown("#### 4️⃣ Step 4: WhatsApp Connection")
        st.caption("Fresh connection required per campaign; session closes automatically upon completion.")
        
        is_wa_active = check_login_status()
        if is_wa_active:
            st.success("🟢 **WhatsApp Web Ready** (Authenticated session found)")
        else:
            st.warning("⚪ **WhatsApp Web Not Connected** (Please scan QR Code)")

        camp_qr_box = st.empty()
        wa_btn_col1, wa_btn_col2 = st.columns(2)
        with wa_btn_col1:
            if st.button("🔑 Connect / Scan QR", key="btn_camp_wa_connect", use_container_width=True):
                with st.spinner("Connecting to WhatsApp Web..."):
                    def camp_qr_cb(shot, note):
                        if shot is not None:
                            with camp_qr_box.container():
                                st.info(f"📱 {note}:")
                                st.image(shot, width=380)
                        else:
                            camp_qr_box.empty()

                    ok = launch_whatsapp_login_window(timeout_minutes=3, qr_callback=camp_qr_cb)
                    if ok:
                        st.success("🎉 WhatsApp connected successfully!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Authentication timed out or closed.")
        with wa_btn_col2:
            if st.button("🔄 Reset / Clear Session", key="btn_camp_wa_reset", use_container_width=True):
                close_whatsapp_session()
                st.info("WhatsApp session reset. Please connect afresh.")
                st.rerun()

    st.markdown("---")

    # Step 5: Start, Pause, Resume, Stop Campaign
    st.markdown("#### 5️⃣ Step 5: Live Campaign Execution")
    
    active_thread_state = st.session_state.get("camp_thread_state")
    is_worker_alive = active_thread_state is not None and active_thread_state.get("is_running", False)

    ctl1, ctl2, ctl3, ctl4 = st.columns([1.5, 1, 1, 1])
    with ctl1:
        start_camp_btn = st.button("🚀 Start Campaign Pipeline", type="primary", use_container_width=True, key="btn_start_camp", disabled=is_worker_alive)
    with ctl2:
        pause_camp_btn = st.button("⏸️ Pause", use_container_width=True, key="btn_pause_camp", disabled=not is_worker_alive)
    with ctl3:
        resume_camp_btn = st.button("▶️ Resume", use_container_width=True, key="btn_resume_camp")
    with ctl4:
        stop_camp_btn = st.button("⏹️ Stop", use_container_width=True, key="btn_stop_camp", disabled=not is_worker_alive)

    if pause_camp_btn and active_thread_state:
        active_thread_state["control"]["paused"] = True
        database.update_campaign_status(active_thread_state["campaign_id"], "Paused", db_url=st.session_state.get("db_url"))
        st.warning("⏸️ Pause signal sent! Campaign is pausing at next listing.")
        st.rerun()

    if resume_camp_btn:
        if active_thread_state and active_thread_state.get("is_running"):
            active_thread_state["control"]["paused"] = False
            # Dynamic update: user can change target locations or message while paused/stopped!
            new_locs = [l.strip() for l in camp_locations_input.split("\n") if l.strip()]
            active_thread_state["control"]["locations"] = new_locs
            active_thread_state["control"]["message_template"] = camp_message_text.strip()
            database.update_campaign_status(active_thread_state["campaign_id"], "Running", db_url=st.session_state.get("db_url"))
            st.success("▶️ Resume signal sent! Resumed campaign with latest target locations.")
            st.rerun()
        else:
            st.info("No active paused campaign thread. Click 'Start Campaign Pipeline' to launch.")

    if stop_camp_btn and active_thread_state:
        active_thread_state["control"]["stopped"] = True
        database.update_campaign_status(active_thread_state["campaign_id"], "Stopped", db_url=st.session_state.get("db_url"))
        st.error("⏹️ Stop signal sent! Halting campaign and closing browsers.")
        st.rerun()

    if start_camp_btn:
        if not camp_name.strip():
            st.error("⚠️ Please specify a Campaign Name in Step 1.")
        elif not camp_message_text.strip():
            st.error("⚠️ Please provide a Campaign Message in Step 2.")
        elif not camp_locations_input.strip():
            st.error("⚠️ Please provide at least one Target Location in Step 3.")
        else:
            loc_list = [l.strip() for l in camp_locations_input.split("\n") if l.strip()]
            
            if current_active_camp_id:
                active_cid = current_active_camp_id
                database.update_campaign_status(active_cid, "Running", db_url=st.session_state.get("db_url"))
            else:
                active_cid = database.create_campaign(
                    name=camp_name.strip(),
                    message_template=camp_message_text.strip(),
                    locations=camp_locations_input.strip(),
                    db_url=st.session_state.get("db_url")
                )
            
            st.session_state["active_campaign_id"] = active_cid

            saved_media_file_path = None
            if camp_media_file is not None:
                media_dir = os.path.abspath("./whatsapp_temp_media")
                os.makedirs(media_dir, exist_ok=True)
                saved_media_file_path = os.path.join(media_dir, camp_media_file.name)
                with open(saved_media_file_path, "wb") as f:
                    f.write(camp_media_file.getbuffer())

            # Initialize thread state
            thread_state = {
                "is_running": True,
                "campaign_id": active_cid,
                "campaign_name": camp_name.strip(),
                "control": {
                    "paused": False,
                    "stopped": False,
                    "locations": loc_list,
                    "message_template": camp_message_text.strip()
                },
                "stats": {"scraped": 0, "sent": 0, "failed": 0, "skipped": 0, "status": "Running"},
                "status_msg": "🚀 Starting campaign automation...",
                "screenshot": None,
                "grid_df": pd.DataFrame(),
                "error": None
            }
            st.session_state["camp_thread_state"] = thread_state

            def _bg_campaign_worker(cid, cname, ctemplate, clocs, cmax, ccode, cdelay, cvis, cmedia, db_url, state_dict):
                def _cb(msg, stats, screenshot=None, grid_df=None):
                    state_dict["status_msg"] = msg
                    state_dict["stats"] = stats
                    if screenshot is not None:
                        state_dict["screenshot"] = screenshot
                    if grid_df is not None:
                        state_dict["grid_df"] = grid_df

                try:
                    res = run_campaign(
                        campaign_id=cid,
                        campaign_name=cname,
                        message_template=ctemplate,
                        queries_or_locations=clocs,
                        max_per_location=cmax,
                        default_country_code=ccode,
                        delay_between_messages=cdelay,
                        show_browser=cvis,
                        media_path=cmedia,
                        db_url=db_url,
                        progress_callback=_cb,
                        control_state=state_dict["control"]
                    )
                    state_dict["status_msg"] = f"Finished ({res.get('status', 'Completed')})"
                except Exception as exc:
                    state_dict["error"] = str(exc)
                    state_dict["status_msg"] = f"Error: {exc}"
                finally:
                    state_dict["is_running"] = False

            w_thread = threading.Thread(
                target=_bg_campaign_worker,
                args=(
                    active_cid,
                    camp_name.strip(),
                    camp_message_text.strip(),
                    loc_list,
                    camp_max_per_loc,
                    camp_cc.strip(),
                    camp_delay,
                    camp_visible_browser,
                    saved_media_file_path,
                    st.session_state.get("db_url"),
                    thread_state
                ),
                daemon=True
            )
            w_thread.start()
            st.session_state["camp_thread_obj"] = w_thread
            st.rerun()

    # Fragment to auto-refresh live dashboard every 2 seconds when campaign is active
    @st.fragment(run_every="2s")
    def render_live_campaign_dashboard():
        state = st.session_state.get("camp_thread_state")
        if not state:
            col_g, col_s = st.columns([1.3, 1])
            with col_g:
                st.info("Live campaign data and outreach logs will appear here once started.")
            with col_s:
                st.markdown(get_browser_window_frame("Automated Campaign Simulation"), unsafe_allow_html=True)
                st.caption("Chromium browser automation preview will display live actions here.")
            return

        stats = state.get("stats", {})
        status_msg = state.get("status_msg", "Running...")
        ctrl = state.get("control", {})
        
        # Status header alert
        if ctrl.get("stopped"):
            st.error(f"⏹️ **Campaign Stopped:** {status_msg}")
        elif ctrl.get("paused"):
            st.warning(f"⏸️ **Campaign Paused:** {status_msg} (Edit locations or click 'Resume' above)")
        elif not state.get("is_running"):
            st.success(f"🎉 **Campaign Finished:** {status_msg}")
        else:
            st.info(f"⚡ **Active Status:** {status_msg}")

        # KPI Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📍 Leads Scraped", f"{stats.get('scraped', 0):,}")
        m2.metric("💬 WhatsApp Sent", f"{stats.get('sent', 0):,}")
        m3.metric("⏭️ Duplicates Prevented", f"{stats.get('skipped', 0):,}")
        m4.metric("❌ Failed / No Phone", f"{stats.get('failed', 0):,}")

        col_grid, col_sim = st.columns([1.3, 1])
        with col_grid:
            grid_df = state.get("grid_df")
            if grid_df is not None and not grid_df.empty:
                st.markdown(f"### 📋 Live Campaign Activity Stream ({len(grid_df)} events)")
                st.dataframe(grid_df, width="stretch")
            else:
                st.caption("Waiting for first extracted lead...")

        with col_sim:
            st.markdown(get_browser_window_frame(f"Action: {status_msg[:35]}"), unsafe_allow_html=True)
            shot = state.get("screenshot")
            if shot is not None:
                st.image(shot, use_container_width=True)
            else:
                st.caption("Live browser window will render snapshots as steps execute.")

    render_live_campaign_dashboard()

with tab_rep:
    st.markdown("""
    <div class="tab-header-card">
        <div style="display:flex; align-items:center; gap:12px;">
            <span style="font-size:1.6rem;">📊</span>
            <div>
                <h3 style="margin:0; font-size:1.35rem; font-weight:700;">Date & Time Campaign Reports</h3>
                <span style="font-size:0.83rem; color:#64748B;">Audit trail: historical outreach logs, delivery statuses, duplicates prevented, and performance metrics</span>
            </div>
        </div>
        <span class="pill-badge pill-primary">Audited Logs</span>
    </div>
    """, unsafe_allow_html=True)

    all_camps_df = database.get_all_campaigns(db_url=st.session_state.get("db_url"))
    camp_filter_options = ["All Campaigns"]
    if not all_camps_df.empty:
        camp_filter_options += [f"#{row['ID']} - {row['Name']}" for _, row in all_camps_df.iterrows()]

    f_col1, f_col2, f_col3, f_col4 = st.columns([1.5, 1, 1, 1])
    with f_col1:
        rep_camp_sel = st.selectbox("Select Campaign:", options=camp_filter_options, key="rep_sel_camp")
    with f_col2:
        rep_status_sel = st.selectbox("Delivery Status:", ["All", "Sent", "Failed", "Skipped Duplicate", "Invalid Number"], key="rep_sel_status")
    with f_col3:
        rep_start_date = st.date_input("From Date:", value=datetime.now().date(), key="rep_dt_start")
    with f_col4:
        rep_end_date = st.date_input("To Date:", value=datetime.now().date(), key="rep_dt_end")

    filter_cid = None
    if rep_camp_sel != "All Campaigns":
        m_id = re.search(r"#(\d+)", rep_camp_sel)
        if m_id:
            filter_cid = int(m_id.group(1))

    try:
        report_df = database.fetch_campaign_reports(
            campaign_id=filter_cid,
            start_date=rep_start_date,
            end_date=rep_end_date,
            status=rep_status_sel if rep_status_sel != "All" else None,
            db_url=st.session_state.get("db_url")
        )

        if not report_df.empty:
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            total_logs = len(report_df)
            sent_logs = len(report_df[report_df["Status"].str.lower() == "sent"])
            dup_logs = len(report_df[report_df["Status"].str.lower().str.contains("duplicate|skipped")])
            success_pct = f"{(sent_logs / total_logs * 100):.1f}%" if total_logs > 0 else "0%"

            kpi1.metric("Total Events Logged", f"{total_logs:,}")
            kpi2.metric("Messages Delivered", f"{sent_logs:,}", delta=success_pct)
            kpi3.metric("Duplicates Prevented", f"{dup_logs:,}")
            kpi4.metric("Success Rate", success_pct)

            st.markdown("---")
            st.dataframe(report_df, width="stretch")
            st.caption(f"Showing **{len(report_df)} outreach records** for selected filters.")

            e_col1, e_col2 = st.columns(2)
            with e_col1:
                rep_buf = io.BytesIO()
                with pd.ExcelWriter(rep_buf, engine='openpyxl') as writer:
                    report_df.to_excel(writer, index=False, sheet_name='Campaign_Report')
                st.download_button(
                    label="📥 Export Report to Excel (.xlsx)",
                    data=rep_buf.getvalue(),
                    file_name=f"campaign_report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="btn_dl_rep_excel"
                )
            with e_col2:
                rep_csv = report_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 Export Report to CSV (.csv)",
                    data=rep_csv,
                    file_name=f"campaign_report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="btn_dl_rep_csv"
                )
        else:
            st.info("No campaign activity logs found for the selected criteria.")
    except Exception as rep_err:
        st.error(f"Error loading campaign report: {rep_err}")

with tab_ai:
    st.markdown("""
    <div class="tab-header-card">
        <div style="display:flex; align-items:center; gap:12px;">
            <span style="font-size:1.6rem;">💡</span>
            <div>
                <h3 style="margin:0; font-size:1.35rem; font-weight:700;">AI Sales Strategist & Query Generator</h3>
                <span style="font-size:0.83rem; color:#64748B;">Neural AI powered market analysis, target buyer profiling, and high-intent query generation</span>
            </div>
        </div>
        <span class="pill-badge pill-primary">⚡ Enterprise AI Strategist</span>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("Describe what product or service you want to sell and your target location. Proprietary AI will analyze your target market, determine the best commercial client business types, generate high-intent Google Maps search queries, and craft a winning B2B sales outreach strategy.")

    col_q1, col_q2 = st.columns([2.5, 1.2])
    with col_q1:
        ai_user_ask = st.text_area(
            "What do you want to sell?",
            value="I want to sell POS billing software to retail shops and supermarkets.",
            height=90,
            placeholder="e.g. I want to sell commercial CCTV cameras, POS software, web development services",
            key="ai_sales_ask_input"
        )
    with col_q2:
        ai_custom_loc = st.text_input("Target Location * (Required):", value="Dhanmondi, Dhaka", placeholder="e.g. Dhanmondi, Dhaka", key="ai_loc_override")
        st.write("")
        btn_run_strategy = st.button("🚀 Analyze & Generate Queries", type="primary", use_container_width=True, key="btn_run_strat")

    if btn_run_strategy:
        if not ai_user_ask.strip():
            st.warning("⚠️ Please specify what product or service you want to sell.")
        elif not ai_custom_loc.strip():
            st.error("⚠️ Target Location is required! Please enter your target city, area or neighborhood.")
        else:
            with st.spinner("🤖 AI is analyzing your target market and identifying buyer prospects..."):
                strategy_result = groq_helper.suggest_search_queries_and_strategy(
                    user_goal_or_product=ai_user_ask,
                    location=ai_custom_loc
                )
                st.session_state["last_ai_strategy"] = strategy_result

    strategy_data = st.session_state.get("last_ai_strategy", {})
    if strategy_data:
        st.markdown("---")
        # 1. Target Audience & Market Analysis
        st.markdown("#### 🎯 1. Target Buyer Businesses")
        st.info(f"**Potential Clients to Target:**\n\n{strategy_data.get('target_buyers', 'Local businesses needing your product.')}")

        # 2. Recommended Search Queries
        st.markdown("#### 🔍 2. High-Intent Google Maps Search Queries")
        queries_list = strategy_data.get("suggested_queries", [])
        queries_text = "\n".join(queries_list)

        c_q_left, c_q_right = st.columns([2, 1])
        with c_q_left:
            st.markdown("Copy or transfer these ready-to-scrape Google Maps queries:")
            st.code(queries_text, language="text")
        with c_q_right:
            st.markdown("**One-Click Action:**")
            if st.button("🗺️ Send to Multi-Keyword Batch Search", key="btn_send_to_batch", use_container_width=True):
                st.session_state["tab2_batch_queries_area"] = queries_text
                st.session_state["batch_queries_input"] = queries_text
                st.session_state["ai_batch_queries_transferred"] = True
                st.rerun()

            if st.session_state.get("ai_batch_queries_transferred", False):
                st.success("✅ Loaded into Tab 2! Switch to '🗺️ Multi-Location / Multi-Keyword Search' to start scraping.")

        # 3. Strategy & Pitch
        st.markdown("---")
        col_strat1, col_strat2 = st.columns(2)
        with col_strat1:
            st.markdown("#### 📈 3. Actionable Sales & Outreach Strategy")
            st.success(strategy_data.get("sales_strategy", "Reach out directly introducing your offer."))
        with col_strat2:
            st.markdown("#### 💬 4. Recommended WhatsApp Cold Pitch")
            pitch_text = strategy_data.get("recommended_pitch", "")
            st.info(pitch_text)
            if st.button("💬 Use This Pitch in WhatsApp Automation", key="btn_send_pitch_to_wa", use_container_width=True):
                st.session_state["wa_msg_tmpl"] = pitch_text
                st.session_state["ai_pitch_transferred"] = True
                st.rerun()

            if st.session_state.get("ai_pitch_transferred", False):
                st.success("✅ Pitch copied into Tab 3! Switch to '💬 WhatsApp Automation' to start messaging.")

with tab1:
    st.markdown("""
    <div class="tab-header-card">
        <div style="display:flex; align-items:center; gap:12px;">
            <span style="font-size:1.6rem;">🔍</span>
            <div>
                <h3 style="margin:0; font-size:1.35rem; font-weight:700;">Single Target Scraper</h3>
                <span style="font-size:0.83rem; color:#64748B;">Extract verified local business leads with real-time browser preview and phone filters</span>
            </div>
        </div>
        <span class="pill-badge pill-primary">High-Precision Mode</span>
    </div>
    """, unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns([3, 1, 1, 1.2])
    with col1:
        single_query = st.text_input(
            "Search Query & Location:",
            value="stationary shop around uttara",
            placeholder="e.g. pharmacy in gulshan, stationary shop in uttara"
        )
    with col2:
        single_limit = st.number_input("Max Results:", min_value=5, max_value=300, value=25, step=5, key="single_lim")
    with col3:
        phone_only_1 = st.checkbox("📱 Phone Only", value=False, help="Only include businesses that have a phone number", key="po_1")
    with col4:
        show_browser_1 = st.checkbox("👁️ Open Visible Browser", value=False, help="Open external browser window (unchecked runs in background headless mode)", key="sb_1")

    # Fields selection
    with st.expander("📋 Select Fields to Collect", expanded=True):
        pcol1, pcol2, pcol3, pcol4 = st.columns([2, 1, 1, 1])
        with pcol1:
            st.caption("Customize which fields to scrape and export:")
        with pcol2:
            if st.button("All Fields", key="btn_all_1", use_container_width=True):
                st.session_state["fields_1"] = list(DEFAULT_FIELDS)
                st.rerun()
        with pcol3:
            if st.button("Contact Info", key="btn_cnt_1", use_container_width=True):
                st.session_state["fields_1"] = ["Name", "Phone", "WhatsApp", "Address", "Website"]
                st.rerun()
        with pcol4:
            if st.button("Minimal", key="btn_min_1", use_container_width=True):
                st.session_state["fields_1"] = ["Name", "Phone", "WhatsApp"]
                st.rerun()

        if "fields_1" not in st.session_state:
            st.session_state["fields_1"] = list(DEFAULT_FIELDS)

        selected_fields_1 = st.multiselect(
            "Fields:",
            options=DEFAULT_FIELDS,
            key="fields_1",
            help="Choose the data fields you want in your scraped results",
            label_visibility="collapsed"
        )

    start_single = st.button("🚀 Start Single Search", key="btn_single", type="primary", use_container_width=True)

    if start_single:
        if not single_query.strip():
            st.warning("⚠️ Please enter a search query.")
        elif not selected_fields_1:
            st.error("⚠️ Please select at least one field to collect.")
        else:
            col_table, col_screen = st.columns([1.2, 1])
            with col_table:
                progress_bar = st.progress(0)
                status_text = st.empty()
                grid_placeholder = st.empty()
            with col_screen:
                screen_placeholder = st.empty()
                with screen_placeholder.container():
                    st.markdown(get_browser_window_frame("Google Maps Single Search"), unsafe_allow_html=True)
                    st.info("Browser starting... Live Google Maps actions will stream here.")

            latest_shot = [None]

            def update_progress(current, total, msg, current_df=None, screenshot=None):
                pct = min(1.0, current / total) if total > 0 else 0
                progress_bar.progress(pct)
                status_text.markdown(f"**[{current}/{total}]** {msg}")
                if current_df is not None and not current_df.empty:
                    with grid_placeholder.container():
                        st.markdown(f"### 📋 Live Extracted Leads ({len(current_df)} collected)")
                        st.dataframe(current_df, width="stretch")
                if screenshot is not None:
                    latest_shot[0] = screenshot
                    with screen_placeholder.container():
                        st.markdown(get_browser_window_frame(f"Action: {msg}"), unsafe_allow_html=True)
                        st.image(screenshot, use_container_width=True)

            try:
                df = scrape_google_maps(
                    search_query=single_query,
                    max_results=single_limit,
                    headless=not show_browser_1,
                    phone_only=phone_only_1,
                    fields=selected_fields_1,
                    progress_callback=update_progress
                )
                
                if not df.empty:
                    st.session_state["active_leads_df"] = df
                    st.success(f"🎉 Successfully collected {len(df)} leads!")
                    with grid_placeholder.container():
                        st.markdown(f"### 📋 Extracted Leads ({len(df)} total)")
                        render_leads_metric_summary(df)
                        st.dataframe(df, width="stretch")
                    with screen_placeholder.container():
                        st.markdown(get_browser_window_frame("Scraping Complete"), unsafe_allow_html=True)
                        if latest_shot[0] is not None:
                            st.image(latest_shot[0], caption="Finished Scraping", use_container_width=True)
                        else:
                            st.success("Scraping finished successfully!")

                    # Export buttons
                    c1, c2 = st.columns(2)
                    
                    # Excel
                    buf = io.BytesIO()
                    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='Leads')
                    
                    c1.download_button(
                        label="📥 Download Excel (.xlsx)",
                        data=buf.getvalue(),
                        file_name=f"leads_{single_query.replace(' ', '_')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                    
                    # CSV
                    csv_data = df.to_csv(index=False).encode('utf-8-sig')
                    c2.download_button(
                        label="📥 Download CSV (.csv)",
                        data=csv_data,
                        file_name=f"leads_{single_query.replace(' ', '_')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )

                    # Auto-sync to database
                    try:
                        sync_res = database.save_leads_to_db(df, db_url=st.session_state.get("db_url"))
                        st.success(f"💾 Permanently recorded in Database: **{sync_res['inserted']} new**, **{sync_res['duplicates']} updated/deduplicated**.")
                    except Exception as dbe:
                        st.info(f"Database note: {dbe}")
                else:
                    st.warning("No listings found matching your criteria.")
            except Exception as e:
                st.error(f"Scraping error: {str(e)}")

with tab2:
    st.markdown("""
    <div class="tab-header-card">
        <div style="display:flex; align-items:center; gap:12px;">
            <span style="font-size:1.6rem;">🗺️</span>
            <div>
                <h3 style="margin:0; font-size:1.35rem; font-weight:700;">Multi-Location & Batch Harvester</h3>
                <span style="font-size:0.83rem; color:#64748B;">Automate multi-city or multi-niche lead scraping in continuous queues with deduplication</span>
            </div>
        </div>
        <span class="pill-badge pill-primary">Batch Harvester</span>
    </div>
    """, unsafe_allow_html=True)
    if st.session_state.get("ai_batch_queries_transferred", False):
        st.success("✨ **Loaded queries from AI Sales Strategist!** You can review or edit them below, then start your batch run.")

    st.markdown("Enter multiple keywords or locations (one per line):")
    default_batch_text = "stationary shop in uttara\nstationary shop in mirpur\nstationary shop in dhanmondi"
    if "tab2_batch_queries_area" not in st.session_state:
        st.session_state["tab2_batch_queries_area"] = st.session_state.get("batch_queries_input", default_batch_text)

    batch_input = st.text_area(
        "Search Queries:",
        value=st.session_state.get("tab2_batch_queries_area", default_batch_text),
        height=140,
        key="tab2_batch_queries_area"
    )
    
    col_b1, col_b2, col_b3 = st.columns([2, 1, 1.2])
    with col_b1:
        batch_limit = st.number_input("Max Results Per Query:", min_value=5, max_value=100, value=15, step=5, key="batch_lim")
    with col_b2:
        phone_only_2 = st.checkbox("📱 Phone Only", value=False, key="po_2")
    with col_b3:
        show_browser_2 = st.checkbox("👁️ Open Visible Browser", value=False, help="Open external browser window (unchecked runs in background headless mode)", key="sb_2")

    # Fields selection for batch
    with st.expander("📋 Select Fields to Collect", expanded=True):
        pcol_b1, pcol_b2, pcol_b3, pcol_b4 = st.columns([2, 1, 1, 1])
        with pcol_b1:
            st.caption("Customize which fields to scrape and export:")
        with pcol_b2:
            if st.button("All Fields", key="btn_all_2", use_container_width=True):
                st.session_state["fields_2"] = list(DEFAULT_FIELDS)
                st.rerun()
        with pcol_b3:
            if st.button("Contact Info", key="btn_cnt_2", use_container_width=True):
                st.session_state["fields_2"] = ["Name", "Phone", "WhatsApp", "Address", "Website"]
                st.rerun()
        with pcol_b4:
            if st.button("Minimal", key="btn_min_2", use_container_width=True):
                st.session_state["fields_2"] = ["Name", "Phone", "WhatsApp"]
                st.rerun()

        if "fields_2" not in st.session_state:
            st.session_state["fields_2"] = list(DEFAULT_FIELDS)

        selected_fields_2 = st.multiselect(
            "Fields:",
            options=DEFAULT_FIELDS,
            key="fields_2",
            help="Choose the data fields you want in your scraped results",
            label_visibility="collapsed"
        )

    start_batch = st.button("🚀 Start Batch Search", key="btn_batch", type="primary", use_container_width=True)

    if start_batch:
        if not batch_input.strip():
            st.warning("⚠️ Please enter at least one search query.")
        elif not selected_fields_2:
            st.error("⚠️ Please select at least one field to collect.")
        else:
            queries = [q.strip() for q in batch_input.split("\n") if q.strip()]
            if queries:
                col_b_table, col_b_screen = st.columns([1.2, 1])
                with col_b_table:
                    progress_bar_batch = st.progress(0)
                    status_text_batch = st.empty()
                    grid_placeholder_batch = st.empty()
                with col_b_screen:
                    screen_placeholder_batch = st.empty()
                    with screen_placeholder_batch.container():
                        st.markdown(get_browser_window_frame("Multi-Query Batch Harvester"), unsafe_allow_html=True)
                        st.info("Browser starting... Live Google Maps actions will stream here.")

                latest_batch_shot = [None]

                def update_progress_batch(current, total, msg, current_df=None, screenshot=None):
                    pct = min(1.0, current / total) if total > 0 else 0
                    progress_bar_batch.progress(pct)
                    status_text_batch.markdown(f"**[{current}/{total}]** {msg}")
                    if current_df is not None and not current_df.empty:
                        with grid_placeholder_batch.container():
                            st.markdown(f"### 📋 Live Extracted Leads ({len(current_df)} collected)")
                            st.dataframe(current_df, width="stretch")
                    if screenshot is not None:
                        latest_batch_shot[0] = screenshot
                        with screen_placeholder_batch.container():
                            st.markdown(get_browser_window_frame(f"Action: {msg}"), unsafe_allow_html=True)
                            st.image(screenshot, use_container_width=True)

                try:
                    df_batch = batch_scrape(
                        queries=queries,
                        max_per_query=batch_limit,
                        headless=not show_browser_2,
                        phone_only=phone_only_2,
                        fields=selected_fields_2,
                        progress_callback=update_progress_batch
                    )

                    if not df_batch.empty:
                        st.session_state["active_leads_df"] = df_batch
                        st.success(f"🎉 Batch search finished! Collected {len(df_batch)} total unique leads.")
                        with grid_placeholder_batch.container():
                            st.markdown(f"### 📋 Extracted Leads ({len(df_batch)} total)")
                            render_leads_metric_summary(df_batch)
                            st.dataframe(df_batch, width="stretch")
                        with screen_placeholder_batch.container():
                            st.markdown(get_browser_window_frame("Batch Scraping Complete"), unsafe_allow_html=True)
                            if latest_batch_shot[0] is not None:
                                st.image(latest_batch_shot[0], caption="Finished Batch Scraping", use_container_width=True)
                            else:
                                st.success("Batch scraping finished!")

                        c1, c2 = st.columns(2)
                        
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                            df_batch.to_excel(writer, index=False, sheet_name='All_Leads')
                        
                        c1.download_button(
                            label="📥 Download Combined Excel (.xlsx)",
                            data=buf.getvalue(),
                            file_name="combined_batch_leads.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )

                        csv_data = df_batch.to_csv(index=False).encode('utf-8-sig')
                        c2.download_button(
                            label="📥 Download Combined CSV (.csv)",
                            data=csv_data,
                            file_name="combined_batch_leads.csv",
                            mime="text/csv",
                            use_container_width=True
                        )

                        # Auto-sync batch leads to database
                        try:
                            sync_b_res = database.save_leads_to_db(df_batch, db_url=st.session_state.get("db_url"))
                            st.success(f"💾 Permanently recorded in Database: **{sync_b_res['inserted']} new**, **{sync_b_res['duplicates']} updated/deduplicated**.")
                        except Exception as dbe:
                            st.info(f"Database note: {dbe}")
                    else:
                        st.warning("No listings found.")
                except Exception as e:
                    st.error(f"Error during batch scrape: {str(e)}")

with tab3:
    st.markdown("""
    <div class="tab-header-card">
        <div style="display:flex; align-items:center; gap:12px;">
            <span style="font-size:1.6rem;">💬</span>
            <div>
                <h3 style="margin:0; font-size:1.35rem; font-weight:700;">Automated WhatsApp Web Campaign Hub</h3>
                <span style="font-size:0.83rem; color:#64748B;">Direct outreach with media attachments, editable lead tables, and pre-campaign test messaging</span>
            </div>
        </div>
        <span class="pill-badge pill-success">Outreach Engine V2</span>
    </div>
    """, unsafe_allow_html=True)

    is_logged_in = st.session_state.get("whatsapp_logged_in", False) or check_login_status()
    col_auth1, col_auth2 = st.columns([2.5, 1])
    with col_auth1:
        if is_logged_in:
            st.success("🟢 **WhatsApp Web Session Active** (Session connected and ready)")
        else:
            st.warning("⚪ **WhatsApp Web Session Not Connected** (Please scan QR Code once to authenticate)")
        qr_display_box = st.empty()
        if st.button("🔑 Connect / Scan QR Code", key="btn_wa_login", use_container_width=True):
            with st.spinner("Connecting to WhatsApp Web..."):
                def qr_stream_cb(screenshot, status_note):
                    if screenshot is not None:
                        with qr_display_box.container():
                            if "sync" in status_note.lower() or "connected" in status_note.lower() and "scan" not in status_note.lower():
                                st.info(f"🔄 **{status_note}**")
                            else:
                                st.info(f"📱 {status_note} (**Linked Devices &rarr; Link a Device**):")
                            st.image(screenshot, width=420)
                    else:
                        qr_display_box.empty()

                success = launch_whatsapp_login_window(timeout_minutes=3, qr_callback=qr_stream_cb)
                if success:
                    st.session_state["whatsapp_logged_in"] = True
                    st.success("🎉 Successfully connected to WhatsApp Web!")
                    qr_display_box.empty()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Login timed out or window was closed before scanning.")

    with col_auth2:
        if is_logged_in:
            if st.button("🔄 Reconnect / Reset", key="btn_wa_reset", use_container_width=True):
                st.session_state["whatsapp_logged_in"] = False
                import shutil
                from pathlib import Path
                from whatsapp_sender import DEFAULT_SESSION_DIR
                marker = Path(DEFAULT_SESSION_DIR) / "session_active.marker"
                if marker.exists():
                    try:
                        marker.unlink()
                    except Exception:
                        pass
                st.rerun()

    st.markdown("---")

    # Step 1: Select or Add Leads
    st.markdown("#### 1️⃣ Select or Add Leads to Message")
    has_active_leads = "active_leads_df" in st.session_state and not st.session_state["active_leads_df"].empty

    source_option = st.radio(
        "Choose leads source:",
        options=[
            "Recent Search Results", 
            "From Remote Database", 
            "Upload Excel / CSV File",
            "✍️ Enter / Paste Numbers Manually"
        ],
        horizontal=True,
        key="wa_source_radio"
    )

    wa_leads_df = pd.DataFrame()
    if source_option == "Recent Search Results":
        if has_active_leads:
            wa_leads_df = st.session_state["active_leads_df"].copy()
            st.info(f"Loaded **{len(wa_leads_df)} leads** from your latest search session.")
        else:
            st.warning("⚠️ No leads found in current session. Run a search in Tab 1 or Tab 2, or choose another source.")
    elif source_option == "From Remote Database":
        try:
            db_leads = database.fetch_leads_from_db(db_url=st.session_state.get("db_url"), has_phone_only=True)
            if not db_leads.empty:
                wa_leads_df = db_leads.copy()
                st.info(f"Loaded **{len(wa_leads_df)} leads** with phone numbers directly from the Remote Database.")
            else:
                st.warning("Remote Database has no leads with phone numbers yet. Scrape or import leads first.")
        except Exception as dbe:
            st.error(f"Failed to fetch leads from database: {dbe}")
    elif source_option == "Upload Excel / CSV File":
        uploaded_file = st.file_uploader("Upload leads file (.xlsx or .csv)", type=["xlsx", "csv"], key="wa_file_uploader")
        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith(".csv"):
                    wa_leads_df = pd.read_csv(uploaded_file)
                else:
                    wa_leads_df = pd.read_excel(uploaded_file)
                st.success(f"Loaded **{len(wa_leads_df)} leads** from uploaded file.")
            except Exception as e:
                st.error(f"Failed to read file: {e}")
    else:  # Manual entry
        st.caption("Paste or type numbers below. Formats supported: `01712345678` or `01712345678, Business Name` (one per line).")
        manual_text = st.text_area(
            "Enter Phone Numbers:",
            placeholder="01712345678\n01812345678, ABC Stationery\n+8801912345678, XYZ Superstore",
            height=130,
            key="wa_manual_input_area"
        )
        if manual_text.strip():
            parsed_list = parse_manual_numbers(manual_text)
            if parsed_list:
                wa_leads_df = pd.DataFrame(parsed_list)
                st.success(f"Loaded **{len(wa_leads_df)} manual contacts**.")
            else:
                st.warning("No valid phone numbers found in input.")

    # Allow appending custom numbers to any chosen source
    with st.expander("➕ Append Custom Numbers to Current Campaign List", expanded=False):
        col_app1, col_app2 = st.columns([1.5, 1])
        with col_app1:
            append_num = st.text_input("Phone Number to Add:", placeholder="e.g. 01712345678", key="wa_append_num_val")
        with col_app2:
            append_nm = st.text_input("Contact / Business Name:", placeholder="e.g. Target Lead", key="wa_append_name_val")
        if st.button("➕ Add Number", key="btn_wa_append_action"):
            if append_num.strip():
                if "wa_custom_appended_leads" not in st.session_state:
                    st.session_state["wa_custom_appended_leads"] = []
                st.session_state["wa_custom_appended_leads"].append({
                    "Name": append_nm.strip() or "Custom Lead",
                    "Phone": append_num.strip(),
                    "Category": "Manual Entry",
                    "Address": "",
                    "Website": ""
                })
                st.success(f"Appended {append_num} to list!")
                st.rerun()

    # Merge custom appended leads if any
    if "wa_custom_appended_leads" in st.session_state and st.session_state["wa_custom_appended_leads"]:
        appended_df = pd.DataFrame(st.session_state["wa_custom_appended_leads"])
        if wa_leads_df.empty:
            wa_leads_df = appended_df
        else:
            wa_leads_df = pd.concat([wa_leads_df, appended_df], ignore_index=True)

    valid_phone_leads = pd.DataFrame()
    if not wa_leads_df.empty:
        if "Phone" in wa_leads_df.columns:
            valid_phone_leads = wa_leads_df[wa_leads_df["Phone"].astype(str).str.strip().ne("")].copy()
            keep_cols = [c for c in ["Name", "Phone", "Category", "Address", "Website"] if c in valid_phone_leads.columns]
            valid_phone_leads = valid_phone_leads[keep_cols]
        else:
            valid_phone_leads = wa_leads_df.copy()

        st.markdown("##### 📝 Campaign Recipients (Editable Table)")
        st.caption("💡 You can edit names/numbers or click **➕ Add row** at the bottom of the table to add more numbers:")
        valid_phone_leads = st.data_editor(valid_phone_leads, num_rows="dynamic", use_container_width=True, key="wa_leads_editor")
        st.caption(f"Total valid recipient leads: **{len(valid_phone_leads)}**")

    st.markdown("---")
    st.markdown("#### 2️⃣ Compose Message & Automation Settings")

    # AI Assistant Expander
    with st.expander("✨ AI Message Copywriter & Pitch Assistant", expanded=False):
        g_conn, g_msg = groq_helper.test_groq_connection()
        if g_conn:
            st.caption("🟢 **AI Engine Status**: Active & Connected")
        else:
            st.caption(f"🔴 **AI Engine Status**: {g_msg}")

        col_ai1, col_ai2 = st.columns([2, 1])
        with col_ai1:
            ai_pitch_offer = st.text_input("Your Service / Offer / Pitch:", value="Exclusive 25% discount on stationery & school supplies", key="ai_pitch_input")
        with col_ai2:
            ai_tone = st.selectbox("Tone:", ["Friendly & Professional", "Direct & Concise", "Casual & Warm", "Urgent Promotion"], key="ai_tone_input")

        if st.button("🪄 Generate Cold Pitch with AI", key="btn_gen_ai_pitch"):
            with st.spinner("AI is crafting your cold pitch..."):
                new_tmpl = groq_helper.generate_outreach_template(goal=ai_pitch_offer, tone=ai_tone)
                if new_tmpl and not new_tmpl.startswith("Error"):
                    st.session_state["wa_msg_tmpl"] = new_tmpl
                    st.success("Pitch generated! Updated template below.")
                    st.rerun()
                else:
                    st.error(f"Generation error: {new_tmpl}")

    col_msg, col_settings = st.columns([1.5, 1])
    with col_msg:
        default_template = "Hello {Name}, I noticed your business ({Category}) in {Address}. Are you currently accepting new orders/clients?"
        message_template = st.text_area(
            "Message Template (Supports dynamic variables):",
            value=default_template,
            height=130,
            key="wa_msg_tmpl"
        )
        st.caption("💡 Supported variables: `{Name}`, `{Phone}`, `{Category}`, `{Address}`, `{Website}`")

    with col_settings:
        country_code = st.text_input("Default Country Code (without +):", value="880", help="e.g. 880 for Bangladesh, 1 for USA, 44 for UK", key="wa_cc")
        delay = st.slider("Safety Delay Between Messages (seconds):", min_value=5, max_value=30, value=8, help="Recommended to prevent WhatsApp spam flags", key="wa_delay")
        use_ai_personalize = st.checkbox("🤖 AI Dynamic 1-to-1 Personalization", value=False, help="Generate a unique personalized message for each individual business based on their name, category, and location", key="wa_use_ai")
        show_wa_browser = st.checkbox("👁️ Open Visible WhatsApp Browser", value=False, help="Open external browser window (unchecked runs in background headless mode)", key="wa_watch_browser")

    # Media attachment upload
    media_upload = st.file_uploader(
        "📎 Attach Media (Optional - Image, PDF brochure, Catalog, or Short Video):", 
        type=["png", "jpg", "jpeg", "pdf", "mp4"],
        help="Attach an image or PDF brochure to send with your message as a caption",
        key="wa_media_file"
    )
    saved_media_path = None
    if media_upload is not None:
        media_temp_dir = os.path.abspath("./whatsapp_temp_media")
        os.makedirs(media_temp_dir, exist_ok=True)
        saved_media_path = os.path.join(media_temp_dir, media_upload.name)
        with open(saved_media_path, "wb") as f:
            f.write(media_upload.getbuffer())
        st.success(f"📎 Attached file: **{media_upload.name}** ({media_upload.size // 1024} KB) — will be sent with your message as the caption!")

    # Test Message Block
    st.markdown("---")
    st.markdown("#### 🧪 Test Message Verification")
    st.caption("Send a real test message to your personal WhatsApp to preview how it renders before launching the full campaign.")

    col_test1, col_test2 = st.columns([1.5, 1])
    with col_test1:
        test_number = st.text_input(
            "Recipient Phone Number for Test Message:",
            placeholder="e.g. 01712345678 or +8801712345678",
            key="wa_test_phone_num"
        )
    with col_test2:
        test_name = st.text_input(
            "Contact Name (replaces {Name}):",
            value="Test Recipient",
            key="wa_test_contact_name"
        )

    test_rendered_msg = message_template.replace("{Name}", test_name or "Test Recipient")
    test_rendered_msg = test_rendered_msg.replace("{Phone}", test_number or "01712345678")
    test_rendered_msg = test_rendered_msg.replace("{Category}", "Test Business")
    test_rendered_msg = test_rendered_msg.replace("{Address}", "Dhaka, Bangladesh")
    test_rendered_msg = test_rendered_msg.replace("{Website}", "example.com")

    with st.expander("👁️ Preview Rendered Test Message", expanded=False):
        st.info(test_rendered_msg)
        if saved_media_path:
            st.caption(f"📎 Plus attachment: `{os.path.basename(saved_media_path)}`")

    test_msg_status_box = st.empty()
    test_preview_box = st.empty()

    if st.button("📲 Send Test WhatsApp Message", key="btn_send_test_message", use_container_width=True):
        if not is_logged_in:
            st.error("⚠️ WhatsApp Web session is not active! Please scan QR code in the Connect section above first.")
        elif not test_number.strip():
            st.warning("⚠️ Please enter a recipient phone number for the test message.")
        else:
            with st.spinner(f"Sending test WhatsApp message to {test_number}..."):
                def test_stream_cb(cur, tot, lead, res_dict, screenshot=None):
                    if screenshot is not None:
                        with test_preview_box.container():
                            st.image(screenshot, caption="Test Message Live Browser Preview", width=420)

                try:
                    test_res = send_test_whatsapp_message(
                        phone=test_number.strip(),
                        message=test_rendered_msg,
                        default_country_code=country_code,
                        headless=not show_wa_browser,
                        progress_callback=test_stream_cb,
                        media_path=saved_media_path
                    )

                    if test_res.get("status") == "Sent":
                        test_msg_status_box.success(f"🎉 Test message sent successfully to **{test_res.get('phone')}**! Verify it on your WhatsApp.")
                    else:
                        err_msg = test_res.get('error', 'Unknown error')
                        test_msg_status_box.error(f"❌ Failed to send test message: {err_msg} (Status: {test_res.get('status')})")
                        if "not logged in" in err_msg.lower():
                            st.session_state["whatsapp_logged_in"] = False
                except Exception as test_err:
                    test_msg_status_box.error(f"❌ Automation error while sending test message: {test_err}")

    st.markdown("---")
    st.markdown("#### 3️⃣ Launch Automated Bulk Campaign")
    start_campaign = st.button("🚀 Start Automated WhatsApp Campaign", key="btn_start_wa", type="primary", use_container_width=True)

    if start_campaign:
        if not is_logged_in:
            st.error("⚠️ WhatsApp Web is not logged in! Please click '🔑 Connect / Scan QR Code' above first.")
        elif valid_phone_leads.empty:
            st.error("⚠️ No leads with valid phone numbers available. Add or select leads above.")
        else:
            col_wa_l, col_wa_r = st.columns([1.2, 1])
            with col_wa_l:
                wa_progress = st.progress(0)
                wa_status = st.empty()
                wa_log_placeholder = st.empty()
            with col_wa_r:
                wa_screen_placeholder = st.empty()
                with wa_screen_placeholder.container():
                    st.markdown(get_browser_window_frame("WhatsApp Web Live Session"), unsafe_allow_html=True)
                    st.info("WhatsApp automation starting...")

            delivery_records = []

            def wa_callback(current, total, lead, res_dict, screenshot=None):
                pct = min(1.0, current / total) if total > 0 else 0
                wa_progress.progress(pct)
                status_text_msg = res_dict.get("status", "")
                lead_name = lead.get("Name", "") if lead else ""
                phone_val = res_dict.get("phone", "")
                wa_status.markdown(f"**[{current}/{total}]** Sending to **{lead_name}** ({phone_val}): `{status_text_msg}`")

                if res_dict and lead:
                    record_entry = {
                        "Name": lead_name,
                        "Phone": phone_val,
                        "Status": status_text_msg,
                        "Error": res_dict.get("error") or "None"
                    }
                    delivery_records.append(record_entry)
                    with wa_log_placeholder.container():
                        st.markdown(f"### 📋 Message Delivery Log ({len(delivery_records)} processed)")
                        st.dataframe(pd.DataFrame(delivery_records), width="stretch")

                if screenshot is not None:
                    with wa_screen_placeholder.container():
                        st.markdown(get_browser_window_frame(f"Action: {status_text_msg}"), unsafe_allow_html=True)
                        st.image(screenshot, use_container_width=True)

            leads_list = valid_phone_leads.to_dict("records")
            try:
                results = bulk_send_whatsapp(
                    leads=leads_list,
                    message_template=message_template,
                    default_country_code=country_code,
                    delay_between_messages=delay,
                    headless=not show_wa_browser,
                    progress_callback=wa_callback,
                    use_ai_personalization=use_ai_personalize,
                    ai_offer=message_template,
                    media_path=saved_media_path
                )
                st.success(f"🎉 WhatsApp Campaign Completed! Processed {len(results)} leads.")
                with wa_screen_placeholder.container():
                    st.markdown(get_browser_window_frame("WhatsApp Campaign Finished"), unsafe_allow_html=True)
                    st.success("All messages sent!")
            except Exception as err:
                st.error(f"WhatsApp automation error: {str(err)}")

with tab4:
    st.markdown("""
    <div class="tab-header-card">
        <div style="display:flex; align-items:center; gap:12px;">
            <span style="font-size:1.6rem;">🗄️</span>
            <div>
                <h3 style="margin:0; font-size:1.35rem; font-weight:700;">Remote Database & Cloud Vault</h3>
                <span style="font-size:0.83rem; color:#64748B;">Store, query, filter and archive all scraped B2B leads permanently across PostgreSQL, Supabase or SQLite</span>
            </div>
        </div>
        <span class="pill-badge pill-primary">Permanent Archive</span>
    </div>
    """, unsafe_allow_html=True)

    # Connection Settings
    with st.expander("⚙️ Database Connection Settings", expanded=True):
        col_db1, col_db2 = st.columns([3, 1])
        with col_db1:
            current_url = st.session_state.get("db_url", database.normalize_db_url())
            new_db_url = st.text_input(
                "Database Connection URL (PostgreSQL / Supabase / Neon / MySQL / SQLite):",
                value=current_url,
                type="password",
                help="e.g. postgresql://postgres:password@db.supabase.co:5432/postgres or sqlite:///gmaps_leads_archive.db",
                key="input_db_url"
            )
        with col_db2:
            st.write("")
            st.write("")
            if st.button("🔌 Test & Connect", key="btn_test_db", use_container_width=True):
                success, msg = database.test_connection(new_db_url)
                if success:
                    st.session_state["db_url"] = new_db_url
                    st.success("✅ Connection Successful!")
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")

        active_db = st.session_state.get("db_url", database.normalize_db_url())
        is_conn_ok, conn_msg = database.test_connection(active_db)
        if is_conn_ok:
            st.caption(f"🟢 **Status**: Connected (`{database.re.sub(r':([^@]+)@', ':****@', active_db)}`)")
        else:
            st.caption(f"🔴 **Status**: Disconnected ({conn_msg})")

    st.markdown("---")

    # Live Statistics
    try:
        stats = database.get_db_stats(st.session_state.get("db_url"))
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📊 Total Leads Stored", stats.get("total_leads", 0))
        m2.metric("📱 Leads with Phone", stats.get("leads_with_phone", 0))
        m3.metric("🏷️ Unique Categories", stats.get("unique_categories", 0))
        m4.metric("🔍 Queries Searched", stats.get("unique_queries", 0))
    except Exception as e:
        st.warning(f"Unable to read database stats: {e}")

    st.markdown("---")

    # Filter & Query Database Records
    st.markdown("#### 📋 Stored Leads Explorer")
    fcol1, fcol2, fcol3, fcol4 = st.columns([1.5, 1.5, 1, 1])
    with fcol1:
        search_kw = st.text_input("Filter by Query / Location:", key="db_kw_filter", placeholder="e.g. uttara, pharmacy")
    with fcol2:
        search_cat = st.text_input("Filter by Category:", key="db_cat_filter", placeholder="e.g. Stationery, Doctor")
    with fcol3:
        only_phone = st.checkbox("Phone Only", value=True, key="db_po_filter")
    with fcol4:
        db_limit = st.selectbox("Max Rows:", options=[50, 100, 250, 500, 1000], index=1, key="db_limit_sel")

    try:
        db_df = database.fetch_leads_from_db(
            db_url=st.session_state.get("db_url"),
            query_filter=search_kw,
            category_filter=search_cat,
            has_phone_only=only_phone,
            limit=db_limit
        )

        if not db_df.empty:
            st.dataframe(db_df, width="stretch")
            st.caption(f"Showing **{len(db_df)} records** from database.")

            # Export buttons
            e_col1, e_col2, e_col3 = st.columns([1, 1, 1.5])
            with e_col1:
                db_buf = io.BytesIO()
                with pd.ExcelWriter(db_buf, engine='openpyxl') as writer:
                    db_df.to_excel(writer, index=False, sheet_name='Archived_Leads')
                st.download_button(
                    label="📥 Download Excel (.xlsx)",
                    data=db_buf.getvalue(),
                    file_name="archived_leads.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="btn_dl_db_excel"
                )
            with e_col2:
                db_csv = db_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 Download CSV (.csv)",
                    data=db_csv,
                    file_name="archived_leads.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="btn_dl_db_csv"
                )
            with e_col3:
                if st.button("💬 Push These Leads to WhatsApp Tab", key="btn_push_wa", use_container_width=True):
                    st.session_state["active_leads_df"] = db_df
                    st.success("✅ Successfully loaded into WhatsApp Automation session! Switch to Tab 3 to send messages.")
        else:
            st.info("No records found matching filters.")
    except Exception as err:
        st.error(f"Error querying database: {err}")

# Fixed Ultra-Compact Bottom Footer
st.markdown(
    """
    <div class="fixed-compact-footer">
        <div>
            <span>📍 <strong>GeoHunter Pro</strong></span>
            <span style="opacity:0.4; margin: 0 6px;">|</span>
            <span>© 2026 Shafayat Hossain. All rights reserved.</span>
        </div>
        <div>
            <span>Developed by <a href="https://jqsafi.github.io/" target="_blank">Shafayat Hossain</a></span>
            <span style="opacity:0.4; margin: 0 6px;">|</span>
            <span style="font-size: 0.68rem; background: rgba(37,99,235,0.1); color: #2563EB; padding: 1px 6px; border-radius: 4px; font-weight: 700;">v2.5</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

