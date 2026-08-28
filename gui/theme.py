"""
GUI theme tokens and styles for Vario-X Motor Studio.
Murrelektronik Industrial Brand Palette.
"""

import sys
import tkinter as tk
from tkinter import ttk

# Typography
FONT_FAMILY = "Segoe UI" if sys.platform == "win32" else "Helvetica"
FONT_MONO_FAMILY = "Consolas" if sys.platform == "win32" else "Courier"

FONT_APP_TITLE = (FONT_FAMILY, 14, "bold")
FONT_TAB = (FONT_FAMILY, 10, "bold")
FONT_TITLE = (FONT_FAMILY, 11, "bold")
FONT_SUBTITLE = (FONT_FAMILY, 9)
FONT_SECTION = (FONT_FAMILY, 10, "bold")
FONT_BODY = (FONT_FAMILY, 9)
FONT_BODY_BOLD = (FONT_FAMILY, 9, "bold")
FONT_MONO = (FONT_MONO_FAMILY, 9)
FONT_MONO_BOLD = (FONT_MONO_FAMILY, 9, "bold")
FONT_BADGE = (FONT_FAMILY, 8, "bold")
FONT_LARGE_VALUE = (FONT_FAMILY, 18, "bold")

# Color Palette
COLOR_BG_DARK       = "#041412" # Deep dark background
COLOR_BG_SURFACE    = "#07211E" # Main surface
COLOR_BG_CARD       = "#0E3E39" # Card containers
COLOR_BG_ACCENT     = "#195851" # Elevated border / hover
COLOR_BG_INPUT      = "#051A18" # Text entry background

COLOR_TEXT_PRIMARY  = "#FFFFFF"
COLOR_TEXT_MUTED    = "#80A8A3"
COLOR_TEXT_DIM      = "#4A6E6A"

COLOR_MURR_LIME     = "#8DEA3C" # Brand Murr Lime Green
COLOR_MURR_GREEN    = "#3DB60F" # Brand Green
COLOR_MURR_BLUE     = "#38BDF8" # Info / Accent Cyan
COLOR_WARNING       = "#F9E2AF" # Amber / Warning
COLOR_DANGER        = "#F38BA8" # Red / Fault
COLOR_DISABLED      = "#2D4B47"

# LED Colors for Canvas Rendering
LED_COLOR_RED_ON    = "#FF3B30"
LED_COLOR_RED_OFF   = "#3B1414"
LED_COLOR_RED_GLOW  = "#FF6961"

LED_COLOR_YEL_ON    = "#FFCC00"
LED_COLOR_YEL_OFF   = "#3A3311"
LED_COLOR_YEL_GLOW  = "#FFE066"

LED_COLOR_GRN_ON    = "#8DEA3C"
LED_COLOR_GRN_OFF   = "#1A3510"
LED_COLOR_GRN_GLOW  = "#B8F584"

LED_COLOR_DARK_OFF  = "#122824"

def setup_ttk_styles(root: tk.Tk):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    # Global Colors
    style.configure(".",
        background=COLOR_BG_SURFACE,
        foreground=COLOR_TEXT_PRIMARY,
        font=FONT_BODY
    )

    # Notebook Tabs
    style.configure("TNotebook",
        background=COLOR_BG_DARK,
        borderwidth=0
    )
    style.configure("TNotebook.Tab",
        background=COLOR_BG_SURFACE,
        foreground=COLOR_TEXT_MUTED,
        font=FONT_TAB,
        padding=[14, 8],
        borderwidth=0
    )
    style.map("TNotebook.Tab",
        background=[("selected", COLOR_BG_CARD), ("active", COLOR_BG_ACCENT)],
        foreground=[("selected", COLOR_MURR_LIME), ("active", COLOR_TEXT_PRIMARY)]
    )

    # Frame styles
    style.configure("Card.TFrame", background=COLOR_BG_CARD)
    style.configure("Surface.TFrame", background=COLOR_BG_SURFACE)
    style.configure("Dark.TFrame", background=COLOR_BG_DARK)

    # Label styles
    style.configure("Card.TLabel", background=COLOR_BG_CARD, foreground=COLOR_TEXT_PRIMARY, font=FONT_BODY)
    style.configure("CardMuted.TLabel", background=COLOR_BG_CARD, foreground=COLOR_TEXT_MUTED, font=FONT_BODY)
    style.configure("CardTitle.TLabel", background=COLOR_BG_CARD, foreground=COLOR_MURR_LIME, font=FONT_TITLE)
    style.configure("SurfaceTitle.TLabel", background=COLOR_BG_SURFACE, foreground=COLOR_TEXT_PRIMARY, font=FONT_TITLE)

    # Button styles
    style.configure("Murr.TButton",
        background=COLOR_MURR_GREEN,
        foreground="#FFFFFF",
        font=FONT_BODY_BOLD,
        padding=[10, 6],
        borderwidth=0
    )
    style.map("Murr.TButton",
        background=[("active", COLOR_MURR_LIME), ("disabled", COLOR_DISABLED)],
        foreground=[("active", "#000000"), ("disabled", COLOR_TEXT_DIM)]
    )

    style.configure("Action.TButton",
        background=COLOR_BG_ACCENT,
        foreground=COLOR_TEXT_PRIMARY,
        font=FONT_BODY_BOLD,
        padding=[8, 5],
        borderwidth=0
    )
    style.map("Action.TButton",
        background=[("active", COLOR_MURR_LIME), ("disabled", COLOR_DISABLED)],
        foreground=[("active", "#000000"), ("disabled", COLOR_TEXT_DIM)]
    )

    style.configure("Danger.TButton",
        background="#8B1E28",
        foreground=COLOR_TEXT_PRIMARY,
        font=FONT_BODY_BOLD,
        padding=[8, 5],
        borderwidth=0
    )
    style.map("Danger.TButton",
        background=[("active", COLOR_DANGER), ("disabled", COLOR_DISABLED)],
        foreground=[("active", "#000000"), ("disabled", COLOR_TEXT_DIM)]
    )

    # Entry & Combobox
    style.configure("TCombobox",
        fieldbackground=COLOR_BG_INPUT,
        background=COLOR_BG_ACCENT,
        foreground=COLOR_TEXT_PRIMARY,
        arrowcolor=COLOR_MURR_LIME
    )
    style.configure("TEntry",
        fieldbackground=COLOR_BG_INPUT,
        foreground=COLOR_TEXT_PRIMARY,
        insertcolor=COLOR_MURR_LIME
    )

    # Treeview
    style.configure("Treeview",
        background=COLOR_BG_INPUT,
        foreground=COLOR_TEXT_PRIMARY,
        fieldbackground=COLOR_BG_INPUT,
        font=FONT_BODY,
        rowheight=24,
        borderwidth=0
    )
    style.configure("Treeview.Heading",
        background=COLOR_BG_CARD,
        foreground=COLOR_MURR_LIME,
        font=FONT_BODY_BOLD,
        borderwidth=1,
        relief="flat"
    )
    style.map("Treeview",
        background=[("selected", COLOR_BG_ACCENT)],
        foreground=[("selected", COLOR_MURR_LIME)]
    )
