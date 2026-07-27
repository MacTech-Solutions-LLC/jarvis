"""Single source of truth for the console's color palette.

`web/app.py` builds its injected CSS from ``PALETTE`` below, and
``tests/test_contrast.py`` / ``scripts/check_contrast.py`` verify every pair
in ``CONTRAST_PAIRS`` against WCAG 2.1 AA. If you change a color here, run
``python scripts/check_contrast.py`` (or the pytest suite) before committing.

The base theme colors (background/secondary background/text/accent) are also
set in ``.streamlit/config.toml`` so Streamlit's own chrome (widgets it does
not let us restyle via CSS) matches. Keep the two files in sync.
"""

PALETTE = {
    # Surfaces
    "bg": "#0B1220",             # page background
    "bg_elevated": "#121B2B",    # sidebar background
    "surface": "#17212F",        # card fill
    "surface_hover": "#1D2836",  # hovered card fill
    # Borders
    "border_subtle": "#26344A",  # decorative dividers only (not relied on for meaning)
    "border_strong": "#5A7699",  # input borders, non-focus interactive outlines
    # Text
    "text": "#EAF1FB",           # primary body text / headings
    "text_secondary": "#C3CEDD",  # secondary text
    "text_muted": "#93A1B5",     # captions, labels, timestamps
    # Interactive / accent
    "accent": "#3FC1E0",         # links, focus rings, primary buttons, selected state
    "on_accent": "#04141C",      # text/icons drawn on top of an accent-filled surface
    # Status
    "success": "#3ED598",
    "warning": "#F5B84C",
    "danger": "#F87171",
}

# Every (foreground, background, minimum_ratio, label) combination actually
# used somewhere in web/app.py. 4.5:1 = WCAG AA body text, 3.0:1 = AA large
# text / UI component boundaries (focus rings, input borders).
CONTRAST_PAIRS = [
    ("text", "bg", 4.5, "body text on page background"),
    ("text", "surface", 4.5, "body text on card surface"),
    ("text", "bg_elevated", 4.5, "body text on sidebar background"),
    ("text_secondary", "bg", 4.5, "secondary text on page background"),
    ("text_secondary", "surface", 4.5, "secondary text on card surface"),
    ("text_secondary", "bg_elevated", 4.5, "secondary text on sidebar background"),
    ("text_muted", "bg", 4.5, "muted/caption text on page background"),
    ("text_muted", "surface", 4.5, "muted/caption text on card surface"),
    ("text_muted", "bg_elevated", 4.5, "muted/caption text on sidebar background"),
    ("accent", "bg", 4.5, "accent text/links on page background"),
    ("accent", "surface", 4.5, "accent text/links on card surface"),
    ("accent", "bg_elevated", 4.5, "accent text/links on sidebar background"),
    ("on_accent", "accent", 4.5, "button label on accent-filled button"),
    ("success", "bg", 4.5, "success status text on page background"),
    ("success", "surface", 4.5, "success status text on card surface"),
    ("warning", "bg", 4.5, "warning status text on page background"),
    ("warning", "surface", 4.5, "warning status text on card surface"),
    ("danger", "bg", 4.5, "error status text on page background"),
    ("danger", "surface", 4.5, "error status text on card surface"),
    ("border_strong", "bg", 3.0, "interactive border on page background"),
    ("border_strong", "surface", 3.0, "interactive border on card surface"),
    ("accent", "surface_hover", 3.0, "focus ring on a hovered card"),
]


def hex_to_rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _linearize(channel_255):
    c = channel_255 / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(color):
    r, g, b = hex_to_rgb(color)
    return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)


def contrast_ratio(color_a, color_b):
    """WCAG 2.1 contrast ratio between two hex colors, always >= 1.0."""
    la, lb = relative_luminance(color_a), relative_luminance(color_b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def root_css_variables():
    """Render PALETTE as CSS custom properties for the :root block."""
    lines = [f"    --{key.replace('_', '-')}: {value};" for key, value in PALETTE.items()]
    return "\n".join(lines)
