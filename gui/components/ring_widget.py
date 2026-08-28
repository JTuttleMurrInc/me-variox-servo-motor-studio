"""
Interactive Canvas Widget rendering the Vario-X Motor Squircle Faceplate and Animated Dual-Half LED Ring.
Accurately models the physical motor back connector layout:
- Rounded Square (Squircle) housing with 4 corner hex socket bolts
- Top-Center: X1 Power Connector (M17/M23)
- Top-Left: X4 Signal Connector (M8)
- Bottom-Left: X2 IN (EtherCAT M12)
- Bottom-Right: X3 OUT (EtherCAT M12)
- Vertically split Left/Right LED Perimeter Ring
"""

import time
import math
import tkinter as tk
from typing import Optional, Tuple, Callable

from core.led_ring import LedRingConfig, PATTERN_NAMES
from gui.theme import (
    COLOR_BG_CARD, COLOR_BG_DARK, COLOR_TEXT_PRIMARY, COLOR_TEXT_MUTED,
    COLOR_MURR_LIME, COLOR_MURR_GREEN, FONT_BADGE, FONT_MONO_BOLD, FONT_SUBTITLE,
    LED_COLOR_RED_ON, LED_COLOR_RED_OFF, LED_COLOR_RED_GLOW,
    LED_COLOR_YEL_ON, LED_COLOR_YEL_OFF, LED_COLOR_YEL_GLOW,
    LED_COLOR_GRN_ON, LED_COLOR_GRN_OFF, LED_COLOR_GRN_GLOW,
    LED_COLOR_DARK_OFF
)

class LedRingWidget(tk.Canvas):
    """Visual Motor & LED Ring Component with squircle geometry and exact connector faceplate."""

    def __init__(self, parent, size: int = 280, **kwargs):
        super().__init__(
            parent,
            width=size,
            height=size,
            bg=COLOR_BG_CARD,
            highlightthickness=0,
            **kwargs
        )
        self.size = size
        self.cx = size / 2.0
        self.cy = size / 2.0
        
        self.config = LedRingConfig(user_mode=False)
        self.on_side_click: Optional[Callable[[str], None]] = None

        # Bindings
        self.bind("<Button-1>", self._on_click)

        # Draw initial static frame
        self._draw_frame()

    def set_config(self, cfg: LedRingConfig):
        self.config = cfg

    def _on_click(self, event):
        # Click on Left or Right half
        if self.on_side_click:
            side = "left" if event.x < self.cx else "right"
            self.on_side_click(side)

    def _get_color_codes(self, color_name: Optional[str]) -> Tuple[str, str]:
        if color_name == "red":
            return (LED_COLOR_RED_ON, LED_COLOR_RED_GLOW)
        elif color_name == "yellow":
            return (LED_COLOR_YEL_ON, LED_COLOR_YEL_GLOW)
        elif color_name == "green":
            return (LED_COLOR_GRN_ON, LED_COLOR_GRN_GLOW)
        return (LED_COLOR_DARK_OFF, LED_COLOR_DARK_OFF)

    def _draw_rounded_rect(self, x1, y1, x2, y2, radius=25, **kwargs):
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1
        ]
        return self.create_polygon(points, **kwargs, smooth=True)

    def _draw_hex_bolt(self, cx, cy, r_outer, r_inner):
        # Bolt washer circle
        self.create_oval(cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer, fill="#0F2D28", outline="#205E56", width=1)
        # Hex socket
        hex_pts = []
        for i in range(6):
            ang = math.radians(i * 60 + 30)
            hex_pts.extend([cx + r_inner * math.cos(ang), cy + r_inner * math.sin(ang)])
        self.create_polygon(hex_pts, fill="#051815", outline="#205E56", width=1)

    def _draw_hex_nut(self, cx, cy, r):
        hex_pts = []
        for i in range(6):
            ang = math.radians(i * 60)
            hex_pts.extend([cx + r * math.cos(ang), cy + r * math.sin(ang)])
        self.create_polygon(hex_pts, fill="#123631", outline="#246D63", width=1)

    def _draw_connector_pins(self, cx, cy, count, radius):
        for i in range(count):
            ang = math.radians(i * (360.0 / count) - 90)
            px = cx + radius * math.cos(ang)
            py = cy + radius * math.sin(ang)
            self.create_oval(px - 1.5, py - 1.5, px + 1.5, py + 1.5, fill="#D97706", outline="")

    def _draw_frame(self):
        self.delete("all")
        s = self.size
        cx, cy = self.cx, self.cy
        pad = s * 0.05
        w = s - 2 * pad
        h = s - 2 * pad
        r_corner = s * 0.12

        # 1. Outer Dark Motor Squircle Housing
        self._draw_rounded_rect(pad, pad, pad + w, pad + h, radius=r_corner, fill="#071E1A", outline="#195851", width=2)
        
        # Inner Faceplate Bezel
        inner_pad = pad + s * 0.04
        inner_w = s - 2 * inner_pad
        inner_h = s - 2 * inner_pad
        self._draw_rounded_rect(inner_pad, inner_pad, inner_pad + inner_w, inner_pad + inner_h, radius=r_corner*0.8, fill="#041210", outline="#0B302B", width=1)

        # 2. Four Corner Hex Socket Mounting Bolts
        bolt_offset = pad + s * 0.045
        bolt_r_out = s * 0.040
        bolt_r_in = s * 0.020
        # Top-Left
        self._draw_hex_bolt(bolt_offset, bolt_offset, bolt_r_out, bolt_r_in)
        # Top-Right
        self._draw_hex_bolt(s - bolt_offset, bolt_offset, bolt_r_out, bolt_r_in)
        # Bottom-Left
        self._draw_hex_bolt(bolt_offset, s - bolt_offset, bolt_r_out, bolt_r_in)
        # Bottom-Right
        self._draw_hex_bolt(s - bolt_offset, s - bolt_offset, bolt_r_out, bolt_r_in)

        # 3. Connectors matching exact physical layout

        # X1: Power Connector (Top Center)
        x1_cx, x1_cy = cx + s * 0.02, cy - s * 0.17
        x1_r = s * 0.125
        self._draw_hex_nut(x1_cx, x1_cy, x1_r * 1.15)
        self.create_oval(x1_cx - x1_r, x1_cy - x1_r, x1_cx + x1_r, x1_cy + x1_r, fill="#0B2320", outline="#2F857A", width=1.5)
        self.create_oval(x1_cx - x1_r*0.65, x1_cy - x1_r*0.65, x1_cx + x1_r*0.65, x1_cy + x1_r*0.65, fill="#051412", outline="#205E56")
        self._draw_connector_pins(x1_cx, x1_cy, 6, x1_r * 0.42)
        self.create_text(x1_cx, x1_cy - x1_r - 7, text="X1", fill=COLOR_TEXT_PRIMARY, font=FONT_BADGE)

        # X4: Signal Connector (Top Left)
        x4_cx, x4_cy = cx - s * 0.26, cy - s * 0.16
        x4_r = s * 0.070
        self._draw_hex_nut(x4_cx, x4_cy, x4_r * 1.15)
        self.create_oval(x4_cx - x4_r, x4_cy - x4_r, x4_cx + x4_r, x4_cy + x4_r, fill="#0B2320", outline="#2F857A", width=1.5)
        self.create_oval(x4_cx - x4_r*0.65, x4_cy - x4_r*0.65, x4_cx + x4_r*0.65, x4_cy + x4_r*0.65, fill="#051412", outline="#205E56")
        self._draw_connector_pins(x4_cx, x4_cy, 4, x4_r * 0.4)
        self.create_text(x4_cx, x4_cy - x4_r - 7, text="X4", fill=COLOR_TEXT_PRIMARY, font=FONT_BADGE)

        # X2 IN: EtherCAT IN Connector (Bottom Left)
        x2_cx, x2_cy = cx - s * 0.19, cy + s * 0.18
        x2_r = s * 0.110
        self.create_oval(x2_cx - x2_r*1.12, x2_cy - x2_r*1.12, x2_cx + x2_r*1.12, x2_cy + x2_r*1.12, fill="#123631", outline="#205E56")
        self.create_oval(x2_cx - x2_r, x2_cy - x2_r, x2_cx + x2_r, x2_cy + x2_r, fill="#0B2320", outline="#2F857A", width=1.5)
        self.create_oval(x2_cx - x2_r*0.65, x2_cy - x2_r*0.65, x2_cx + x2_r*0.65, x2_cy + x2_r*0.65, fill="#051412", outline="#205E56")
        self._draw_connector_pins(x2_cx, x2_cy, 4, x2_r * 0.4)
        self.create_text(x2_cx, x2_cy + x2_r + 8, text="X2 IN", fill=COLOR_TEXT_PRIMARY, font=FONT_BADGE)

        # X3 OUT: EtherCAT OUT Connector (Bottom Right)
        x3_cx, x3_cy = cx + s * 0.19, cy + s * 0.18
        x3_r = s * 0.110
        self.create_oval(x3_cx - x3_r*1.12, x3_cy - x3_r*1.12, x3_cx + x3_r*1.12, x3_cy + x3_r*1.12, fill="#123631", outline="#205E56")
        self.create_oval(x3_cx - x3_r, x3_cy - x3_r, x3_cx + x3_r, x3_cy + x3_r, fill="#0B2320", outline="#2F857A", width=1.5)
        self.create_oval(x3_cx - x3_r*0.65, x3_cy - x3_r*0.65, x3_cx + x3_r*0.65, x3_cy + x3_r*0.65, fill="#051412", outline="#205E56")
        self._draw_connector_pins(x3_cx, x3_cy, 4, x3_r * 0.4)
        self.create_text(x3_cx, x3_cy + x3_r + 8, text="X3 OUT", fill=COLOR_TEXT_PRIMARY, font=FONT_BADGE)

        # Center Division Dashed Line (Vertical split between Left & Right)
        self.create_line(cx, pad + 2, cx, pad + s*0.06, fill="#2F857A", dash=(2, 2))
        self.create_line(cx, s - pad - s*0.06, cx, s - pad - 2, fill="#2F857A", dash=(2, 2))

        # 4. LED Strip Base Paths (Left and Right)
        # Left LED Perimeter Strip
        left_pts = [
            cx - 2, pad + 2,
            pad + r_corner, pad + 2,
            pad + 2, pad + 2,
            pad + 2, pad + r_corner,
            pad + 2, s - pad - r_corner,
            pad + 2, s - pad - 2,
            pad + r_corner, s - pad - 2,
            cx - 2, s - pad - 2
        ]
        self.create_line(left_pts, fill="#0A221E", width=5, smooth=True, tags="left_track", capstyle="round")

        # Right LED Perimeter Strip
        right_pts = [
            cx + 2, pad + 2,
            s - pad - r_corner, pad + 2,
            s - pad - 2, pad + 2,
            s - pad - 2, pad + r_corner,
            s - pad - 2, s - pad - r_corner,
            s - pad - 2, s - pad - 2,
            s - pad - r_corner, s - pad - 2,
            cx + 2, s - pad - 2
        ]
        self.create_line(right_pts, fill="#0A221E", width=5, smooth=True, tags="right_track", capstyle="round")

        # Left LED Glowing Dynamic Line (tags="left_led")
        self.create_line(left_pts, fill=LED_COLOR_DARK_OFF, width=5, smooth=True, tags="left_led", capstyle="round")
        # Right LED Glowing Dynamic Line (tags="right_led")
        self.create_line(right_pts, fill=LED_COLOR_DARK_OFF, width=5, smooth=True, tags="right_led", capstyle="round")

        # Center Status Tag (Placed in open center zone between X1 and X2/X3)
        self.create_text(cx, cy - 2, text="VARIO-X", fill=COLOR_MURR_LIME, font=(FONT_MONO_BOLD[0], 9, "bold"), tags="txt_title")
        self.create_text(cx, cy + 10, text="AUTO MODE", fill=COLOR_TEXT_MUTED, font=FONT_BADGE, tags="txt_mode")

    def update_frame(self, now: Optional[float] = None):
        """Animates and colors the Left & Right halves according to current LedRingConfig."""
        if now is None:
            now = time.time()

        left_state = self.config.get_left_state()
        right_state = self.config.get_right_state()

        l_color_name, l_is_on = left_state.active_color(now)
        r_color_name, r_is_on = right_state.active_color(now)

        l_color_hex, l_glow_hex = self._get_color_codes(l_color_name if l_is_on else None)
        r_color_hex, r_glow_hex = self._get_color_codes(r_color_name if r_is_on else None)

        # Update lines
        self.itemconfig("left_led", fill=l_color_hex)
        self.itemconfig("right_led", fill=r_color_hex)

        # Update Center Mode Label
        if self.config.user_mode:
            self.itemconfig("txt_mode", text="USER MODE", fill="#38BDF8")
        else:
            self.itemconfig("txt_mode", text="AUTO MODE", fill=COLOR_TEXT_MUTED)

    def update_animation(self):
        self.update_frame()
