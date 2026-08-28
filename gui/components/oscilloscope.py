"""
Real-time Multi-Channel Oscilloscope & Telemetry Strip Chart.
"""

import tkinter as tk
from collections import deque
from typing import Dict, List, Tuple
from gui.theme import (
    COLOR_BG_INPUT, COLOR_BG_CARD, COLOR_BG_ACCENT,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_MUTED, COLOR_TEXT_DIM,
    COLOR_MURR_LIME, COLOR_MURR_BLUE, COLOR_WARNING,
    FONT_BADGE, FONT_SUBTITLE
)

class ScopeChart(tk.Canvas):
    """Scrolling real-time waveform display."""

    def __init__(self, parent, max_points: int = 160, height: int = 160, **kwargs):
        super().__init__(
            parent,
            bg=COLOR_BG_INPUT,
            height=height,
            highlightbackground=COLOR_BG_ACCENT,
            highlightthickness=1,
            **kwargs
        )
        self.max_points = max_points
        self.history: Dict[str, deque] = {
            "velocity": deque(maxlen=max_points),
            "position": deque(maxlen=max_points),
            "torque": deque(maxlen=max_points),
        }
        self.channels = [
            {"id": "velocity", "name": "Speed (RPM)", "color": COLOR_MURR_LIME, "scale": 3000.0},
            {"id": "position", "name": "Position (kCounts)", "color": "#38BDF8", "scale": 100.0},
            {"id": "torque", "name": "Torque (% x10)", "color": COLOR_WARNING, "scale": 300.0},
        ]
        self.bind("<Configure>", lambda e: self.redraw())

    def append_sample(self, vel: float, pos: float, torque: float):
        self.history["velocity"].append(vel)
        # Position scaled in thousands of counts for smooth waveform plotting
        self.history["position"].append(pos / 1000.0)
        self.history["torque"].append(torque)
        self.redraw()

    def redraw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 20 or h < 20:
            return

        cy = h / 2.0

        # Draw Grid Lines
        self.create_line(0, cy, w, cy, fill="#123631", width=1, dash=(4, 4))
        self.create_line(0, h * 0.25, w, h * 0.25, fill="#0A221E", width=1, dash=(2, 4))
        self.create_line(0, h * 0.75, w, h * 0.75, fill="#0A221E", width=1, dash=(2, 4))

        # Channel Legends (Top Right)
        lx = w - 10
        for ch in reversed(self.channels):
            txt = ch["name"]
            color = ch["color"]
            item = self.create_text(lx, 12, text=txt, fill=color, font=FONT_BADGE, anchor="e")
            bbox = self.bbox(item)
            if bbox:
                lx = bbox[0] - 12

        # Draw Traces
        dx = w / max(1, self.max_points - 1)
        for ch in self.channels:
            data = self.history[ch["id"]]
            if len(data) < 2:
                continue

            scale = ch["scale"]
            color = ch["color"]
            coords = []
            start_x = w - (len(data) - 1) * dx

            for i, val in enumerate(data):
                x = start_x + i * dx
                norm = max(-1.0, min(1.0, val / scale))
                y = cy - norm * (h * 0.42)
                coords.extend([x, y])

            if len(coords) >= 4:
                self.create_line(*coords, fill=color, width=2, smooth=True)
