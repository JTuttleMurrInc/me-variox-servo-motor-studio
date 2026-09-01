"""
Telemetry Overview Dashboard Tab.
Presents side-by-side Dual Motor Viewports (Slot A & Slot B) with coordinated dual-axis actions
and simultaneous dual-channel motion oscilloscope.
"""

import time
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Dict

from core.motor_device import MotorTelemetry, Cia402State, MODE_NAMES
from core.led_ring import LedRingConfig

from gui.theme import (
    COLOR_BG_DARK, COLOR_BG_SURFACE, COLOR_BG_CARD, COLOR_BG_ACCENT,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_MUTED, COLOR_MURR_LIME, COLOR_MURR_GREEN,
    COLOR_WARNING, COLOR_DANGER, FONT_TITLE, FONT_SECTION, FONT_SUBTITLE, FONT_BADGE
)
from gui.components.motor_viewport_card import MotorViewportCard
from gui.components.oscilloscope import ScopeChart

if TYPE_CHECKING:
    from app import VarioXMotorStudioApp

class DashboardTab(tk.Frame):
    """Tab 1: Live Multi-Axis Dual Telemetry Dashboard."""

    def __init__(self, parent, app: 'VarioXMotorStudioApp'):
        super().__init__(parent, bg=COLOR_BG_SURFACE)
        self.app = app
        
        # Station address mapping for Slot A and Slot B
        self.slot_a_addr = 0x1000
        self.slot_b_addr = 0x1001
        
        self._build_ui()

    def _build_ui(self):
        # 1. Top Header Bar inside tab
        hdr = tk.Frame(self, bg=COLOR_BG_SURFACE, padx=16, pady=8)
        hdr.pack(fill="x")

        title_box = tk.Frame(hdr, bg=COLOR_BG_SURFACE)
        title_box.pack(side="left")

        tk.Label(title_box, text="VARIO-X DUAL-AXIS SERVO DRIVE TELEMETRY", bg=COLOR_BG_SURFACE, fg=COLOR_MURR_LIME, font=FONT_TITLE).pack(anchor="w")
        self.lbl_bus_status = tk.Label(title_box, text="Bus: Initializing Dual Axes (0x1000 & 0x1001)...", bg=COLOR_BG_SURFACE, fg=COLOR_TEXT_MUTED, font=FONT_SUBTITLE)
        self.lbl_bus_status.pack(anchor="w")

        # Global Bus Badge (Right)
        right_box = tk.Frame(hdr, bg=COLOR_BG_SURFACE)
        right_box.pack(side="right")

        self.lbl_axes_count = tk.Label(
            right_box, text="DUAL ACTIVE AXES (2 SLAVES)", bg="#16381C", fg=COLOR_MURR_LIME,
            font=FONT_BADGE, padx=10, pady=4
        )
        self.lbl_axes_count.pack(side="right")

        # 2. Main Dual-Motor Split Container (Slot A on left, Slot B on right)
        dual_container = tk.Frame(self, bg=COLOR_BG_SURFACE, padx=14, pady=2)
        dual_container.pack(fill="both", expand=True)

        # Slot A: Motor 1 (0x1000)
        self.slot_a = MotorViewportCard(dual_container, title="AXIS 1 — STATION 0x1000", station_addr=0x1000)
        self.slot_a.pack(side="left", fill="both", expand=True, padx=(0, 8))

        # Slot B: Motor 2 (0x1001)
        self.slot_b = MotorViewportCard(dual_container, title="AXIS 2 — STATION 0x1001", station_addr=0x1001)
        self.slot_b.pack(side="left", fill="both", expand=True, padx=(8, 0))

        # 3. Bottom Section: Coordinated Actions Bar & Dual Oscilloscope
        bottom_box = tk.Frame(self, bg=COLOR_BG_SURFACE, padx=14, pady=6)
        bottom_box.pack(fill="x", pady=(4, 10))

        # Actions & Scope Split
        action_col = tk.Frame(bottom_box, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=12, pady=8, width=280)
        action_col.pack(side="left", fill="y", padx=(0, 10))

        tk.Label(action_col, text="COORDINATED DUAL ACTIONS", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_SECTION).pack(anchor="w", pady=(0, 6))

        grid = tk.Frame(action_col, bg=COLOR_BG_CARD)
        grid.pack(fill="x")

        ttk.Button(grid, text="1. Enable All Axes", style="Murr.TButton", command=self.app.action_enable_drive).grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(grid, text="Disable All", style="Action.TButton", command=self.app.action_disable_drive).grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        ttk.Button(grid, text="Quick Stop All", style="Danger.TButton", command=self.app.action_quick_stop).grid(row=1, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(grid, text="Reset All Faults", style="Action.TButton", command=self.app.action_fault_reset).grid(row=1, column=1, sticky="ew", padx=2, pady=2)

        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        # Oscilloscope Card (Right)
        scope_col = tk.Frame(bottom_box, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=12, pady=8)
        scope_col.pack(side="left", fill="both", expand=True)

        tk.Label(scope_col, text="REAL-TIME DUAL-AXIS OSCILLOSCOPE (M1 Lime / M2 Amber Speed & Position)", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_SECTION).pack(anchor="w", pady=(0, 4))
        self.scope = ScopeChart(scope_col, height=105)
        self.scope.pack(fill="both", expand=True)

    def update_multi_telemetry(self, telemetry_dict: Dict[int, MotorTelemetry]):
        """Updates both Slot A and Slot B viewport cards and feeds the dual oscilloscope."""
        t_a = telemetry_dict.get(self.slot_a_addr)
        t_b = telemetry_dict.get(self.slot_b_addr)

        m1_vel = 0.0
        m1_pos = 0.0
        m2_vel = 0.0
        m2_pos = 0.0

        if t_a:
            self.slot_a.update_telemetry(t_a)
            m1_vel = float(t_a.velocity_rpm)
            m1_pos = float(t_a.position_actual)

        if t_b:
            self.slot_b.update_telemetry(t_b)
            m2_vel = float(t_b.velocity_rpm)
            m2_pos = float(t_b.position_actual)

        # Feed dual-channel oscilloscope
        self.scope.append_multi_sample(m1_vel, m1_pos, m2_vel, m2_pos)

    def update_telemetry(self, t: MotorTelemetry):
        """Single-axis fallback for compatibility."""
        self.update_multi_telemetry({0x1000: t, 0x1001: t})
