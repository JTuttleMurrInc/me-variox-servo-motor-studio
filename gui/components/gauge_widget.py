"""
Specialized Dashboard Gauge and Card Widgets for Vario-X Motor Studio.
"""

import math
import tkinter as tk
from tkinter import ttk
from typing import Optional

from gui.theme import (
    COLOR_BG_CARD, COLOR_BG_INPUT, COLOR_BG_ACCENT,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_MUTED, COLOR_MURR_LIME,
    FONT_LARGE_VALUE, FONT_SUBTITLE, FONT_BODY_BOLD, FONT_BADGE
)

class PositionCard(tk.Frame):
    """Position Feedback Card displaying raw counts, 16-bit calculated revs, and a mechanical angle dial."""

    def __init__(self, parent, counts_per_rev: int = 65536, **kwargs):
        super().__init__(parent, bg=COLOR_BG_CARD, padx=12, pady=10, **kwargs)
        self.counts_per_rev = counts_per_rev  # 16-bit encoder = 65,536 inc / rev
        self.zero_offset = 0
        self.raw_position = 0

        # Header Row
        hdr = tk.Frame(self, bg=COLOR_BG_CARD)
        hdr.pack(fill="x")

        tk.Label(hdr, text="ACTUAL POSITION (ENCODER)", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_SUBTITLE).pack(side="left")
        
        btn_zero = ttk.Button(hdr, text="Zero Offset", style="Action.TButton", command=self.zero_position)
        btn_zero.pack(side="right")

        # Main Layout: Value Left, Mini Dial Right
        body = tk.Frame(self, bg=COLOR_BG_CARD)
        body.pack(fill="x", pady=(4, 6))

        val_box = tk.Frame(body, bg=COLOR_BG_CARD)
        val_box.pack(side="left", fill="both", expand=True)

        # Primary Large Counts Display
        self.lbl_counts = tk.Label(val_box, text="0 inc", bg=COLOR_BG_CARD, fg="#38BDF8", font=FONT_LARGE_VALUE)
        self.lbl_counts.pack(anchor="w")

        # Subtitle Revolutions & Angle
        self.lbl_sub = tk.Label(val_box, text="0.00 rev  |  0.0°", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_BODY_BOLD)
        self.lbl_sub.pack(anchor="w", pady=(2, 0))

        # Mini Dial Canvas (Angle indicator: starts pointing RIGHT, CCW positive, CW negative)
        self.dial_canvas = tk.Canvas(body, width=54, height=54, bg=COLOR_BG_INPUT, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1)
        self.dial_canvas.pack(side="right", padx=(8, 0))

        # Position Bar Indicator
        self.bar_canvas = tk.Canvas(self, height=6, bg=COLOR_BG_INPUT, highlightthickness=0)
        self.bar_canvas.pack(fill="x", pady=(4, 0))

    def zero_position(self):
        self.zero_offset = self.raw_position
        self.set_position(self.raw_position)

    def set_position(self, pos_counts: int):
        self.raw_position = pos_counts
        rel_counts = pos_counts - self.zero_offset
        revs = rel_counts / float(max(1, self.counts_per_rev))
        
        # Single-turn angle: 0..360 deg
        # Positive travel = CCW, Negative travel = CW
        turn_inc = rel_counts % self.counts_per_rev
        if turn_inc < 0:
            turn_inc += self.counts_per_rev
        deg = (turn_inc / float(self.counts_per_rev)) * 360.0

        # Formatted Display
        self.lbl_counts.config(text=f"{rel_counts:,} inc")
        self.lbl_sub.config(text=f"{revs:+.2f} rev  |  {deg:.1f}°")

        # Update Mini Dial Needle
        # Starts pointing RIGHT (0 deg). CCW is positive (decreasing canvas y), CW is negative (increasing canvas y).
        self.dial_canvas.delete("all")
        cx, cy, r = 27, 27, 22
        self.dial_canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline=COLOR_BG_ACCENT, fill=COLOR_BG_CARD)
        
        # Dial Center Hub
        self.dial_canvas.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill="#38BDF8", outline="")
        
        # Needle (0 deg points to the RIGHT at (cx + r, cy))
        rad = math.radians(deg)
        nx = cx + (r - 4) * math.cos(rad)
        ny = cy - (r - 4) * math.sin(rad)  # canvas y goes down, so minus moves up (CCW)
        self.dial_canvas.create_line(cx, cy, nx, ny, fill="#38BDF8", width=2, arrow="last", arrowshape=(8, 10, 3))

        # Update Multi-turn Bar Indicator
        self.bar_canvas.delete("all")
        bw = self.bar_canvas.winfo_width()
        if bw < 10:
            bw = 200
        norm_ang = (deg / 360.0) * bw
        self.bar_canvas.create_rectangle(0, 0, norm_ang, 6, fill="#38BDF8", outline="")

class MetricGaugeCard(tk.Frame):
    """Reusable numeric card displaying live motor telemetry with graphical bar."""

    def __init__(self, parent, title: str, unit: str = "", min_val: float = 0.0, max_val: float = 100.0,
                 warn_val: Optional[float] = None, fault_val: Optional[float] = None,
                 is_bipolar: bool = False, accent_color: str = COLOR_MURR_LIME,
                 format_str: str = "{:.1f}", **kwargs):
        super().__init__(parent, bg=COLOR_BG_CARD, padx=12, pady=10, **kwargs)
        self.title = title
        self.unit = unit
        self.min_val = min_val
        self.max_val = max_val
        self.warn_val = warn_val
        self.fault_val = fault_val
        self.is_bipolar = is_bipolar
        self.accent_color = accent_color
        self.format_str = format_str

        # Title Label
        tk.Label(self, text=self.title.upper(), bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_SUBTITLE).pack(anchor="w")

        # Value & Unit Row
        val_row = tk.Frame(self, bg=COLOR_BG_CARD)
        val_row.pack(anchor="w", pady=(2, 4))

        self.lbl_value = tk.Label(val_row, text=self.format_str.format(0.0), bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_LARGE_VALUE)
        self.lbl_value.pack(side="left")

        if self.unit:
            tk.Label(val_row, text=f" {self.unit}", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_SUBTITLE).pack(side="left", padx=(2, 0), pady=(6, 0))

        # Progress Bar Canvas
        self.bar_canvas = tk.Canvas(self, height=6, bg=COLOR_BG_INPUT, highlightthickness=0)
        self.bar_canvas.pack(fill="x", pady=(2, 0))

    def set_value(self, val: float, fmt_override: Optional[str] = None):
        # Format text
        fmt = fmt_override or self.format_str
        try:
            self.lbl_value.config(text=fmt.format(val))
        except (ValueError, TypeError):
            self.lbl_value.config(text=str(val))

        # Draw filled bar
        self.bar_canvas.delete("all")
        bw = self.bar_canvas.winfo_width()
        if bw < 10:
            bw = 200

        span = max(0.001, self.max_val - self.min_val)
        clamped = max(self.min_val, min(self.max_val, float(val)))
        frac = (clamped - self.min_val) / span
        fill_w = frac * bw

        self.bar_canvas.create_rectangle(0, 0, fill_w, 6, fill=self.accent_color, outline="")

# Backward compatibility alias
GaugeCard = MetricGaugeCard
