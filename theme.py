"""Look and feel for the University Assistant: midnight background, glowing violet accent.

The Gradio theme object styles components from the inside. The CSS below handles
everything the theme has no setting for: the full-screen layout, the header, the
welcome screen, the messages, answer formatting and the input dock.
"""

from urllib.parse import quote

import gradio as gr

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
ACCENT = "#a78bfa"       # soft violet: highlights, links, focus
ACCENT_DEEP = "#7c3aed"  # deep violet: buttons, user messages
GLOW = "139, 92, 246"    # RGB of the glow, used with different opacities
BG = "#08070f"           # page background (midnight)
PANEL = "#110f1c"        # cards
INPUT = "#14112a"        # input field
BORDER = "#26213d"
TEXT = "#e6e3f2"
MUTED = "#8b86a6"

CONTENT_WIDTH = "1200px"  # widest the conversation gets; everything else lines up with it

# Graduation cap icon (Lucide), used for the logo and the assistant's avatar
CAP_PATHS = (
    '<path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"/>'
    '<path d="M22 10v6"/><path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5"/>'
)
LOGO_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" '
    f'stroke-linecap="round" stroke-linejoin="round">{CAP_PATHS}</svg>'
)
_AVATAR_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
    '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
    f'<stop offset="0" stop-color="{ACCENT_DEEP}"/><stop offset="1" stop-color="#4c1d95"/>'
    '</linearGradient></defs><rect width="32" height="32" rx="9" fill="url(#g)"/>'
    '<g transform="translate(6.5 6.5) scale(0.79)" fill="none" stroke="#fff" stroke-width="2" '
    f'stroke-linecap="round" stroke-linejoin="round">{CAP_PATHS}</g></svg>'
)
AVATAR_URI = "data:image/svg+xml," + quote(_AVATAR_SVG)

# ---------------------------------------------------------------------------
# Gradio theme
# ---------------------------------------------------------------------------
violet = gr.themes.Color(
    c50="#f5f3ff", c100="#ede9fe", c200="#ddd6fe", c300="#c4b5fd",
    c400="#a78bfa", c500="#8b5cf6", c600="#7c3aed", c700="#6d28d9",
    c800="#5b21b6", c900="#4c1d95", c950="#2e1065",
    name="midnight_violet",
)

BASE = gr.themes.Base(
    primary_hue=violet,
    neutral_hue=gr.themes.colors.slate,
    font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"],
    font_mono=[gr.themes.GoogleFont("JetBrains Mono"), "ui-monospace", "monospace"],
    radius_size=gr.themes.sizes.radius_lg,
    spacing_size=gr.themes.sizes.spacing_lg,
)


def dual(theme, **colours):
    """Apply each colour to light and dark mode, skipping names this Gradio lacks."""
    out = {}
    for name, value in colours.items():
        if hasattr(theme, name):
            out[name] = value
        if hasattr(theme, name + "_dark"):
            out[name + "_dark"] = value
    return out


THEME = BASE.set(
    **dual(
        BASE,
        # Surfaces
        body_background_fill=BG,
        background_fill_primary=PANEL,
        background_fill_secondary=BG,
        block_background_fill="transparent",
        panel_background_fill=PANEL,
        code_background_fill="#0d0b18",

        # Text
        body_text_color=TEXT,
        body_text_color_subdued=MUTED,
        block_label_text_color=MUTED,
        block_title_text_color=MUTED,
        link_text_color=ACCENT,
        link_text_color_hover=TEXT,

        # Edges: one colour everywhere, accent only on focus
        border_color_primary=BORDER,
        border_color_accent=ACCENT,
        block_border_color=BORDER,
        block_border_width="0px",
        color_accent=ACCENT,
        color_accent_soft=f"rgba({GLOW}, 0.12)",

        # Inputs
        input_background_fill=INPUT,
        input_border_color=BORDER,
        input_border_color_hover=ACCENT,
        input_border_color_focus=ACCENT,
        input_placeholder_color=MUTED,
        input_shadow_focus=f"0 0 0 3px rgba({GLOW}, 0.22)",

        # Buttons
        button_primary_background_fill=ACCENT_DEEP,
        button_primary_background_fill_hover=ACCENT,
        button_primary_text_color="#ffffff",
        button_primary_border_color=ACCENT_DEEP,
        button_secondary_background_fill="transparent",
        button_secondary_background_fill_hover=f"rgba({GLOW}, 0.10)",
        button_secondary_text_color=TEXT,
        button_secondary_border_color=BORDER,

        # Controls
        checkbox_background_color_selected=ACCENT_DEEP,
        checkbox_border_color_selected=ACCENT_DEEP,
        checkbox_border_color_focus=ACCENT,
        slider_color=ACCENT_DEEP,
    )
)


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
CSS = f"""
:root {{
    --content: {CONTENT_WIDTH};
    --gutter: clamp(16px, 3.2vw, 44px);
    --accent: {ACCENT};
    --glow: {GLOW};
}}

/* ====================== Page: the whole window, never scrolls ====================== */
html, body, gradio-app {{ height: 100% !important; overflow: hidden !important; background: {BG} !important; }}
.gradio-container {{
    height: 100% !important; min-height: 0 !important;
    max-width: none !important; width: 100% !important;
    padding: 0 !important; margin: 0 !important;
    background: transparent !important;
}}
.gradio-container .main, .gradio-container .wrap, .gradio-container main.contain,
.gradio-container .column {{ min-height: 0 !important; }}
.gradio-container main.contain, .gradio-container .main {{
    padding: 0 !important; max-width: none !important; width: 100% !important;
}}

/* Ambient backdrop: violet aurora + a faint dot grid, so wide screens feel designed, not empty */
.gradio-container::before, .gradio-container::after {{
    content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 0;
}}
.gradio-container::before {{
    background:
        radial-gradient(1100px 520px at 50% -12%, rgba({GLOW}, 0.26), transparent 70%),
        radial-gradient(900px 640px at -5% 105%, rgba(76, 29, 149, 0.34), transparent 70%),
        radial-gradient(900px 640px at 105% 90%, rgba(109, 40, 217, 0.24), transparent 70%),
        radial-gradient(600px 400px at 12% 30%, rgba(59, 130, 246, 0.05), transparent 70%);
}}
.gradio-container::after {{
    background-image: radial-gradient(rgba(255, 255, 255, 0.07) 1px, transparent 1px);
    background-size: 26px 26px;
    -webkit-mask-image: radial-gradient(ellipse 75% 65% at 50% 40%, #000 20%, transparent 80%);
            mask-image: radial-gradient(ellipse 75% 65% at 50% 40%, #000 20%, transparent 80%);
    opacity: 0.7;
}}
.gradio-container > * {{ position: relative; z-index: 1; }}

.shell {{ width: 100% !important; gap: 0 !important; padding: 0 !important; }}

/* ====================== Header: full-width glass bar ====================== */
.topbar {{
    flex: 0 0 auto !important;
    align-items: center !important; gap: 12px !important; flex-wrap: nowrap !important;
    height: 64px; padding: 0 var(--gutter) !important;
    background: rgba(8, 7, 15, 0.55);
    backdrop-filter: blur(18px) saturate(140%); -webkit-backdrop-filter: blur(18px) saturate(140%);
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    box-shadow: 0 1px 0 rgba({GLOW}, 0.08), 0 8px 30px rgba(0, 0, 0, 0.25);
}}
.topbar > * {{ min-width: 0 !important; }}
.brand {{ display: flex; align-items: center; gap: 12px; }}
.brand-mark {{
    width: 34px; height: 34px; border-radius: 10px; flex-shrink: 0;
    display: grid; place-items: center;
    background: linear-gradient(135deg, {ACCENT_DEEP}, #4c1d95);
    box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.12) inset, 0 0 24px rgba({GLOW}, 0.45);
}}
.brand-mark svg {{ width: 19px; height: 19px; }}
.brand-title {{
    font-size: 15.5px; font-weight: 650; letter-spacing: -0.01em; color: #f3f1fb; white-space: nowrap;
}}
.brand-divider {{ width: 1px; height: 18px; background: rgba(255, 255, 255, 0.12); }}
.model-pill {{
    display: inline-flex; align-items: center; gap: 7px;
    font-family: 'JetBrains Mono', monospace; font-size: 11.5px; color: #cbbcff;
    background: rgba({GLOW}, 0.10); border: 1px solid rgba({GLOW}, 0.30);
    border-radius: 999px; padding: 3px 10px; white-space: nowrap;
}}
.model-pill::before {{
    content: ""; width: 6px; height: 6px; border-radius: 50%;
    background: #4ade80; box-shadow: 0 0 8px #4ade80;
}}
.new-chat {{
    flex: 0 0 auto !important;
    background: rgba(255, 255, 255, 0.03) !important;
    border: 1px solid rgba(255, 255, 255, 0.10) !important; border-radius: 10px !important;
    color: {TEXT} !important; font-weight: 500 !important; font-size: 13.5px !important;
    padding: 8px 14px !important; box-shadow: none !important;
}}
.new-chat:hover {{
    background: rgba({GLOW}, 0.12) !important; border-color: rgba({GLOW}, 0.45) !important;
    box-shadow: 0 0 20px rgba({GLOW}, 0.20) !important;
}}

/* ====================== Conversation area ====================== */
.chat {{
    border: none !important; background: transparent !important; box-shadow: none !important;
    padding: 0 !important; border-radius: 0 !important;
    flex: 1 1 0 !important; height: auto !important; min-height: 0 !important;
    overflow: hidden !important;  /* only the messages scroll, so there is one scrollbar */
}}
.chat > .wrap {{ display: none !important; }}      /* Gradio's loading overlay and timer */
.chat .top-panel {{ display: none !important; }}   /* the chat's own bin icon: New chat does that */
.chat .wrapper {{ background: transparent !important; }}

/* The scroll area spans the window (scrollbar at the far right); the messages are centred */
.chat .bubble-wrap {{
    background: transparent !important;
    padding: 36px var(--gutter) 28px !important;
    scrollbar-gutter: stable;
    -webkit-mask-image: linear-gradient(to bottom, transparent 0, #000 24px, #000 calc(100% - 24px), transparent 100%);
            mask-image: linear-gradient(to bottom, transparent 0, #000 24px, #000 calc(100% - 24px), transparent 100%);
}}
.chat .message-wrap {{
    max-width: var(--content); width: 100%; margin: 0 auto !important; gap: 10px !important;
    padding: 0 !important;
}}

/* ---- User messages: violet bubble on the right ---- */
.chat .message-row {{ max-width: 100% !important; width: 100% !important; }}
.chat .message-row.user-row {{ margin-top: 18px !important; justify-content: flex-end !important; }}
.chat .user-row .flex-wrap {{ width: 100% !important; max-width: 100% !important; justify-content: flex-end !important; }}
.chat .message-row.user-row .user.message {{
    max-width: min(72%, 720px) !important; width: fit-content !important;
    background: linear-gradient(135deg, rgba(124, 58, 237, 0.42), rgba(91, 33, 182, 0.30)) !important;
    border: 1px solid rgba({GLOW}, 0.40) !important;
    border-radius: 18px 18px 6px 18px !important;
    padding: 11px 16px !important;
    box-shadow: 0 6px 24px rgba({GLOW}, 0.16);
}}
.chat .user-row .user.message > .message {{ background: none !important; border: none !important; padding: 0 !important; }}
.chat .user-row .prose, .chat .user-row .prose p {{ color: #f4f1ff !important; font-size: 15px !important; margin: 0 !important; }}

/* ---- Assistant messages: no box, an avatar on the left ---- */
.chat .message-row.bot-row {{ position: relative; padding-left: 46px !important; margin-top: 6px !important; }}
.chat .message-row.bot-row::before {{
    content: ""; position: absolute; left: 0; top: 2px; width: 30px; height: 30px; border-radius: 9px;
    background: url("{AVATAR_URI}") center / cover no-repeat;
    box-shadow: 0 0 18px rgba({GLOW}, 0.35);
}}
.chat .message-row.bot-row .bot.message, .chat .bot-row .bot.message > .message {{
    background: transparent !important; border: none !important; box-shadow: none !important;
    padding: 0 !important; max-width: 100% !important; width: 100% !important;
}}

/* Copy buttons fade in on hover, lined up with the text */
.chat .message-buttons {{ opacity: 0; transition: opacity 0.2s ease; }}
.chat .message-buttons-left {{ padding-left: 46px !important; }}
.chat .message-row:hover + .message-buttons, .chat .message-buttons:hover,
.chat .message-buttons:focus-within {{ opacity: 1; }}
.chat .message-buttons button {{
    background: transparent !important; border: 1px solid transparent !important; color: {MUTED} !important;
}}
.chat .message-buttons button:hover {{ color: {TEXT} !important; border-color: {BORDER} !important; }}
@media (hover: none) {{ .chat .message-buttons {{ opacity: 1; }} }}

/* Typing dots (with the avatar) while the notes are being searched */
.chat .message-wrap > .container {{ position: relative; padding-left: 46px; margin-top: 6px; min-height: 30px; }}
.chat .message-wrap > .container::before {{
    content: ""; position: absolute; left: 0; top: 0; width: 30px; height: 30px; border-radius: 9px;
    background: url("{AVATAR_URI}") center / cover no-repeat;
    box-shadow: 0 0 18px rgba({GLOW}, 0.35); animation: ua-pulse 1.6s ease-in-out infinite;
}}
.chat .pending {{ background: transparent !important; border: none !important; box-shadow: none !important;
                  padding: 0 !important; min-height: 30px; display: flex !important; align-items: center; }}
.chat .pending .dot {{ background: {ACCENT} !important; box-shadow: 0 0 8px rgba({GLOW}, 0.8); }}
@keyframes ua-pulse {{ 0%, 100% {{ box-shadow: 0 0 10px rgba({GLOW}, 0.25); }} 50% {{ box-shadow: 0 0 26px rgba({GLOW}, 0.65); }} }}

/* ====================== Answer formatting ====================== */
.chat .bot-row .prose {{ font-size: 15.5px !important; line-height: 1.75 !important; color: {TEXT} !important; }}
.chat .bot-row .prose > *:first-child {{ margin-top: 0 !important; }}
.chat .bot-row .prose > *:last-child {{ margin-bottom: 0 !important; }}
.chat .bot-row .prose p {{ margin: 0 0 14px !important; }}
.chat .bot-row .prose strong {{ color: #fbfaff; font-weight: 620; }}
.chat .bot-row .prose em {{ color: #d9d2f5; }}
.chat .bot-row .prose h1, .chat .bot-row .prose h2, .chat .bot-row .prose h3, .chat .bot-row .prose h4 {{
    color: #f7f5ff !important; font-weight: 650 !important; letter-spacing: -0.01em;
    margin: 22px 0 10px !important; line-height: 1.35 !important;
}}
.chat .bot-row .prose h1 {{ font-size: 1.3rem !important; }}
.chat .bot-row .prose h2 {{ font-size: 1.15rem !important; }}
.chat .bot-row .prose h3, .chat .bot-row .prose h4 {{ font-size: 1.02rem !important; }}
.chat .bot-row .prose ul, .chat .bot-row .prose ol {{ margin: 4px 0 14px !important; padding-left: 22px !important; }}
.chat .bot-row .prose li {{ margin: 5px 0 !important; padding-left: 4px; }}
.chat .bot-row .prose li::marker {{ color: {ACCENT}; font-weight: 600; }}
.chat .bot-row .prose a {{ color: {ACCENT} !important; text-decoration: underline; text-underline-offset: 3px;
                          text-decoration-color: rgba({GLOW}, 0.45); }}
.chat .bot-row .prose hr {{ border: none; border-top: 1px solid {BORDER}; margin: 20px 0; }}

/* Tables: rounded card with a tinted header */
.chat .bot-row .prose table {{
    width: 100%; border-collapse: separate !important; border-spacing: 0 !important;
    border: 1px solid {BORDER} !important; border-radius: 12px; overflow: hidden;
    margin: 6px 0 16px !important; padding: 0 !important; font-size: 14px !important;
    background: rgba(17, 15, 28, 0.6);
}}
.chat .bot-row .prose thead, .chat .bot-row .prose tbody, .chat .bot-row .prose tr {{ border: none !important; background: none; }}
.chat .bot-row .prose th {{
    background: rgba({GLOW}, 0.12) !important; color: #f1edff !important; font-weight: 600 !important;
    text-align: left !important; padding: 11px 14px !important; border: none !important;
    border-bottom: 1px solid {BORDER} !important;
}}
.chat .bot-row .prose td {{
    padding: 10px 14px !important; border: none !important;
    border-top: 1px solid rgba(255, 255, 255, 0.05) !important; color: {TEXT} !important;
}}
.chat .bot-row .prose tr:nth-child(even) td {{ background: rgba(255, 255, 255, 0.02); }}

/* Quotes and inline code */
.chat .bot-row .prose blockquote {{
    margin: 4px 0 16px !important; padding: 12px 16px !important;
    border-left: 3px solid {ACCENT} !important; border-radius: 0 10px 10px 0;
    background: rgba({GLOW}, 0.08); color: {TEXT} !important; font-style: normal !important;
}}
.chat .bot-row .prose blockquote p {{ margin: 0 !important; }}
.chat .bot-row .prose :not(pre) > code {{
    font-family: 'JetBrains Mono', monospace; font-size: 0.84em;
    background: rgba({GLOW}, 0.14); color: #ddd2ff; border: 1px solid rgba({GLOW}, 0.25);
    border-radius: 6px; padding: 2px 6px;
}}
.chat .bot-row .prose pre {{
    background: #0d0b18 !important; border: 1px solid {BORDER} !important; border-radius: 12px !important;
    padding: 14px 16px !important;
}}

/* The "Outside your notes" section, set apart as an amber callout */
.chat .bot-row .prose .outside {{
    margin: 18px 0 4px; padding: 14px 16px 12px; border-radius: 12px;
    background: rgba(245, 158, 11, 0.07); border: 1px solid rgba(245, 158, 11, 0.28);
}}
.chat .bot-row .prose .outside-label {{
    display: inline-flex; align-items: center; gap: 6px; margin-bottom: 6px;
    font-size: 11.5px; font-weight: 650; letter-spacing: 0.06em; text-transform: uppercase; color: #fbbf24;
}}
.chat .bot-row .prose .outside p:last-child {{ margin-bottom: 0 !important; }}

/* ====================== Welcome screen ====================== */
.placeholder-content {{
    max-width: var(--content); width: 100%; margin: 0 auto !important;
    min-height: 100%; justify-content: safe center !important; gap: 36px !important; padding: 12px 0 24px;
}}
.placeholder-content .placeholder {{ height: auto !important; min-height: 0 !important; flex: 0 0 auto !important; }}
.placeholder-content .placeholder .prose {{ text-align: center; }}
.placeholder-content .examples {{ position: static !important; flex: 0 0 auto !important;
                                  padding: 0 !important; max-width: none !important; margin: 0 !important; }}
.hero-eyebrow {{
    display: inline-flex; align-items: center; gap: 8px; margin-bottom: 18px;
    padding: 6px 14px; border-radius: 999px;
    font-size: 12.5px; font-weight: 500; color: #cbbcff;
    background: rgba({GLOW}, 0.10); border: 1px solid rgba({GLOW}, 0.28);
    box-shadow: 0 0 24px rgba({GLOW}, 0.15);
}}
.placeholder-content h1 {{
    font-size: clamp(2rem, 3.4vw, 3rem) !important; font-weight: 700 !important;
    letter-spacing: -0.03em !important; line-height: 1.1 !important; margin: 0 0 14px !important;
    background: linear-gradient(180deg, #ffffff 30%, {ACCENT} 130%);
    -webkit-background-clip: text; background-clip: text; color: transparent !important;
}}
.placeholder-content .placeholder p {{
    color: {MUTED} !important; font-size: 1.05rem !important; max-width: 600px; margin: 0 auto !important;
    line-height: 1.6 !important; text-wrap: balance;
}}

/* Example cards: module label, question, arrow on hover */
.examples {{
    display: grid !important; grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
    gap: 14px !important; width: 100%; margin: 0 auto !important;
}}
button.example {{
    position: relative; display: flex !important; flex-direction: column !important;
    align-items: flex-start !important; justify-content: flex-start !important; gap: 12px;
    min-height: 132px !important; padding: 18px 18px 20px !important; text-align: left !important;
    background: linear-gradient(180deg, rgba(22, 19, 39, 0.85), rgba(14, 12, 25, 0.85)) !important;
    border: 1px solid {BORDER} !important; border-radius: 16px !important;
    color: {TEXT} !important; font-size: 14.5px !important; line-height: 1.5 !important;
    backdrop-filter: blur(8px);
    transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}}
button.example::before {{
    font-size: 11px; font-weight: 650; letter-spacing: 0.07em; text-transform: uppercase;
    color: var(--module-colour, {ACCENT});
    padding: 3px 9px; border-radius: 999px;
    background: color-mix(in srgb, var(--module-colour, {ACCENT}) 14%, transparent);
    border: 1px solid color-mix(in srgb, var(--module-colour, {ACCENT}) 32%, transparent);
}}
button.example::after {{
    content: "→"; position: absolute; right: 16px; bottom: 14px;
    color: {ACCENT}; font-size: 16px; opacity: 0; transform: translateX(-4px);
    transition: opacity 0.2s ease, transform 0.2s ease;
}}
button.example:hover {{
    border-color: rgba({GLOW}, 0.55) !important; transform: translateY(-2px);
    box-shadow: 0 12px 34px rgba(0, 0, 0, 0.35), 0 0 26px rgba({GLOW}, 0.18) !important;
}}
button.example:hover::after {{ opacity: 1; transform: none; }}
button.example .example-content, button.example .example-text-content {{ width: 100%; }}
button.example .example-text {{ white-space: normal !important; font-weight: 500; }}

/* ====================== Input dock ====================== */
.dock {{
    flex: 0 0 auto !important; gap: 10px !important;
    padding: 10px var(--gutter) 16px !important;
}}
.dock > * {{ max-width: var(--content) !important; width: 100% !important; margin: 0 auto !important; }}
.form:has(.ask), .ask, .ask label {{
    border: none !important; background: transparent !important; box-shadow: none !important; padding: 0 !important;
}}
.ask .input-container {{
    background: rgba(20, 17, 42, 0.88) !important;
    border: 1px solid rgba(255, 255, 255, 0.09) !important; border-radius: 18px !important;
    padding: 8px 8px 8px 20px !important; align-items: flex-end !important; gap: 10px;
    min-height: 60px;
    backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
    box-shadow: 0 18px 50px rgba(0, 0, 0, 0.45), 0 0 0 1px rgba({GLOW}, 0.06);
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
}}
.ask .input-container:focus-within {{
    border-color: rgba({GLOW}, 0.65) !important;
    box-shadow: 0 18px 50px rgba(0, 0, 0, 0.45), 0 0 0 4px rgba({GLOW}, 0.16), 0 0 36px rgba({GLOW}, 0.20) !important;
}}
.ask textarea {{
    background: transparent !important; border: none !important; box-shadow: none !important;
    padding: 10px 0 !important; font-size: 15.5px !important; line-height: 1.5 !important; color: {TEXT} !important;
}}
.ask textarea::placeholder {{ color: #6f6a8c !important; }}
.ask button {{
    flex-shrink: 0; width: 44px !important; min-width: 44px !important; height: 44px !important;
    margin: 0 !important; padding: 0 !important; border-radius: 13px !important;
    display: grid !important; place-items: center !important;
    background: linear-gradient(135deg, #8b5cf6, {ACCENT_DEEP}) !important; color: #fff !important;
    border: 1px solid rgba(255, 255, 255, 0.14) !important;
    box-shadow: 0 6px 20px rgba({GLOW}, 0.45) !important;
    transition: transform 0.15s ease, box-shadow 0.2s ease, filter 0.2s ease;
}}
.ask button:hover {{ filter: brightness(1.12); transform: translateY(-1px);
                    box-shadow: 0 8px 26px rgba({GLOW}, 0.6) !important; }}
.ask button.stop-button {{
    background: rgba(255, 255, 255, 0.06) !important; border: 1px solid rgba(255, 255, 255, 0.16) !important;
    box-shadow: none !important;
}}

.dock-footer {{
    display: flex; justify-content: space-between; align-items: center; gap: 16px;
    font-size: 12px; color: #6f6a8c !important; padding: 0 6px;
}}
.dock-footer span {{ color: #6f6a8c !important; }}
.dock-footer .note b {{ color: #d4a33a !important; font-weight: 500; }}
.dock-footer kbd {{
    font-family: 'JetBrains Mono', monospace; font-size: 10.5px; color: {MUTED};
    background: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.10);
    border-bottom-width: 2px; border-radius: 5px; padding: 1px 5px; margin: 0 2px;
}}

/* ====================== Scrollbars ====================== */
::-webkit-scrollbar {{ width: 8px; height: 8px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: rgba(255, 255, 255, 0.08); border-radius: 8px; }}
::-webkit-scrollbar-thumb:hover {{ background: rgba({GLOW}, 0.6); }}
* {{ scrollbar-color: rgba(255, 255, 255, 0.10) transparent; }}

/* ====================== Smaller screens ====================== */
@media (max-width: 1100px) {{
    .examples {{ grid-template-columns: repeat(2, minmax(0, 1fr)) !important; }}
}}
@media (max-width: 720px) {{
    .topbar {{ height: 56px; }}
    .brand-divider, .model-pill {{ display: none; }}
    .examples {{ grid-template-columns: 1fr !important; gap: 10px !important; }}
    button.example {{ min-height: 0 !important; padding: 12px 14px !important; gap: 8px; font-size: 14px !important; }}
    button.example::before {{ font-size: 10px; padding: 2px 8px; }}
    .hero-eyebrow {{ font-size: 11.5px; margin-bottom: 14px; }}
    .placeholder-content {{ gap: 22px !important; }}
    .placeholder-content .placeholder p {{ display: none; }}
    .placeholder-content h1 {{ font-size: 1.75rem !important; margin-bottom: 0 !important; }}
    .chat .bubble-wrap {{ padding: 28px 14px 16px !important; scrollbar-gutter: auto; }}
    .dock {{ padding-left: 14px !important; padding-right: 14px !important; }}
    .chat .message-row.bot-row {{ padding-left: 0 !important; }}
    .chat .message-row.bot-row::before {{ display: none; }}
    .chat .message-buttons-left {{ padding-left: 0 !important; }}
    .chat .message-row.user-row .user.message {{ max-width: 88% !important; }}
    .dock-footer {{ display: none; }}
    .dock {{ padding-bottom: 12px !important; }}
    .chat .message-wrap > .container {{ padding-left: 0; }}
    .chat .message-wrap > .container::before {{ display: none; }}
}}
"""