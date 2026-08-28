"""
Telemetry Overview Dashboard Tab.
"""

import time
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from core.motor_device import MotorTelemetry, Cia402State, MODE_NAMES
from core.led_ring import LedRingConfig

from gui.theme import (
    COLOR_BG_DARK, COLOR_BG_SURFACE, COLOR_BG_CARD, COLOR_BG_ACCENT,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_MUTED, COLOR_MURR_LIME, COLOR_WARNING, COLOR_DANGER,
    FONT_TITLE, FONT_SECTION, FONT_SUBTITLE, FONT_BADGE
)
from gui.components.ring_widget import LedRingWidget
from gui.components.gauge_widget import GaugeCard, PositionCard
from gui.components.oscilloscope import ScopeChart

if TYPE_CHECKING:
    from app import VarioXMotorStudioApp

class DashboardTab(tk.Frame):
    """Tab 1: Live Overview & Telemetry Dashboard."""

    def __init__(self, parent, app: 'VarioXMotorStudioApp'):
        super().__init__(parent, bg=COLOR_BG_SURFACE)
        self.app = app
        self._build_ui()

    def _build_ui(self):
        # Top Header Bar inside tab
        hdr = tk.Frame(self, bg=COLOR_BG_SURFACE, padx=16, pady=12)
        hdr.pack(fill="x")

        # Left Info
        title_box = tk.Frame(hdr, bg=COLOR_BG_SURFACE)
        title_box.pack(side="left")

        tk.Label(title_box, text="VARIO-X SERVO DRIVE TELEMETRY", bg=COLOR_BG_SURFACE, fg=COLOR_MURR_LIME, font=FONT_TITLE).pack(anchor="w")
        self.lbl_bus_status = tk.Label(title_box, text="Bus: Initializing...", bg=COLOR_BG_SURFACE, fg=COLOR_TEXT_MUTED, font=FONT_SUBTITLE)
        self.lbl_bus_status.pack(anchor="w")

        # Right Status Pills
        pills_box = tk.Frame(hdr, bg=COLOR_BG_SURFACE)
        pills_box.pack(side="right")

        # CiA 402 State Pill
        self.lbl_cia_pill = tk.Label(
            pills_box, text="SWITCH ON DISABLED", bg="#1C3833", fg=COLOR_WARNING,
            font=FONT_BADGE, padx=10, pady=4
        )
        self.lbl_cia_pill.pack(side="left", padx=4)

        # Mode of Operation Pill
        self.lbl_mode_pill = tk.Label(
            pills_box, text="PROFILE VELOCITY MODE (PV)", bg="#123631", fg="#38BDF8",
            font=FONT_BADGE, padx=10, pady=4
        )
        self.lbl_mode_pill.pack(side="left", padx=4)

        # STO Status Pill
        self.lbl_sto_pill = tk.Label(
            pills_box, text="STO OK", bg="#16381C", fg=COLOR_MURR_LIME,
            font=FONT_BADGE, padx=10, pady=4
        )
        self.lbl_sto_pill.pack(side="left", padx=4)

        # Main Body (2 Columns)
        body = tk.Frame(self, bg=COLOR_BG_SURFACE, padx=14, pady=6)
        body.pack(fill="both", expand=True)

        col_left = tk.Frame(body, bg=COLOR_BG_SURFACE, width=320)
        col_left.pack(side="left", fill="y", padx=(0, 10))

        col_right = tk.Frame(body, bg=COLOR_BG_SURFACE)
        col_right.pack(side="left", fill="both", expand=True)

        self._build_left_panel(col_left)
        self._build_right_panel(col_right)

    def _build_left_panel(self, parent):
        # Ring Card
        ring_card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=12, pady=12)
        ring_card.pack(fill="x")

        tk.Label(ring_card, text="OPTICAL COLOR RING (0x2FEF)", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_SECTION).pack(anchor="w")
        
        self.ring_widget = LedRingWidget(ring_card, size=240)
        self.ring_widget.pack(pady=10)

        self.lbl_ring_desc = tk.Label(
            ring_card, text="Left: Standby | Right: Standby",
            bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_SUBTITLE
        )
        self.lbl_ring_desc.pack()

        # Quick Actions Card
        actions_card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=12, pady=12)
        actions_card.pack(fill="x", pady=(12, 0))

        tk.Label(actions_card, text="QUICK DRIVE ACTIONS", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_SECTION).pack(anchor="w", pady=(0, 8))

        btn_grid = tk.Frame(actions_card, bg=COLOR_BG_CARD)
        btn_grid.pack(fill="x")

        ttk.Button(btn_grid, text="1. Enable Drive", style="Murr.TButton", command=self.app.action_enable_drive).grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(btn_grid, text="Disable", style="Action.TButton", command=self.app.action_disable_drive).grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        ttk.Button(btn_grid, text="Quick Stop", style="Danger.TButton", command=self.app.action_quick_stop).grid(row=1, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(btn_grid, text="Reset Fault", style="Action.TButton", command=self.app.action_fault_reset).grid(row=1, column=1, sticky="ew", padx=2, pady=2)

        btn_grid.columnconfigure(0, weight=1)
        btn_grid.columnconfigure(1, weight=1)

    def _build_right_panel(self, parent):
        # 1. Top Row: Position Feedback Card (Full Width - 16-bit encoder: 65,536 counts/rev)
        self.card_position = PositionCard(parent, counts_per_rev=65536)
        self.card_position.pack(fill="x", pady=(0, 8))

        # 2. 4 Metric Cards in 2x2 Grid
        gauge_grid = tk.Frame(parent, bg=COLOR_BG_SURFACE)
        gauge_grid.pack(fill="x")

        self.gauge_speed = GaugeCard(gauge_grid, title="ACTUAL VELOCITY", unit="RPM", min_val=-3500, max_val=3500, warn_val=2800, fault_val=3200, is_bipolar=True)
        self.gauge_speed.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 6))

        self.gauge_torque = GaugeCard(gauge_grid, title="ACTUAL TORQUE", unit="%", min_val=-300, max_val=300, warn_val=150, fault_val=250, is_bipolar=True)
        self.gauge_torque.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=(0, 6))

        self.gauge_voltage = GaugeCard(gauge_grid, title="DC BUS VOLTAGE", unit="V", min_val=0, max_val=60, warn_val=52, fault_val=56, is_bipolar=False)
        self.gauge_voltage.grid(row=1, column=0, sticky="nsew", padx=(0, 6), pady=(6, 0))

        self.gauge_temp = GaugeCard(gauge_grid, title="DEVICE TEMPERATURE", unit="°C", min_val=0, max_val=100, warn_val=60, fault_val=75, is_bipolar=False)
        self.gauge_temp.grid(row=1, column=1, sticky="nsew", padx=(6, 0), pady=(6, 0))

        gauge_grid.columnconfigure(0, weight=1)
        gauge_grid.columnconfigure(1, weight=1)

        # 3. Oscilloscope Card below gauges
        scope_card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=12, pady=10)
        scope_card.pack(fill="both", expand=True, pady=(8, 0))

        tk.Label(scope_card, text="LIVE MOTION OSCILLOSCOPE (Speed / Position / Torque)", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_SECTION).pack(anchor="w", pady=(0, 4))
        
        self.scope = ScopeChart(scope_card, max_points=180, height=150)
        self.scope.pack(fill="both", expand=True)

    def update_telemetry(self, t: MotorTelemetry):
        # Update pills
        state_str = t.cia_state.value.upper()
        if t.cia_state == Cia402State.OPERATION_ENABLED:
            self.lbl_cia_pill.config(text=state_str, bg="#16381C", fg=COLOR_MURR_LIME)
        elif t.cia_state == Cia402State.FAULT or t.error_code != 0:
            self.lbl_cia_pill.config(text=f"FAULT: 0x{t.error_code:04X}", bg="#4A141A", fg=COLOR_DANGER)
        elif t.cia_state == Cia402State.QUICK_STOP_ACTIVE:
            self.lbl_cia_pill.config(text=state_str, bg="#4A3B14", fg=COLOR_WARNING)
        else:
            self.lbl_cia_pill.config(text=state_str, bg="#1C3833", fg=COLOR_WARNING)

        mode_name = MODE_NAMES.get(t.mode_display, f"Mode {t.mode_display}").upper()
        self.lbl_mode_pill.config(text=mode_name)

        if t.sto_info and t.sto_info.is_fault:
            self.lbl_sto_pill.config(text=f"STO: {t.sto_info.error_code_hex}", bg="#4A141A", fg=COLOR_DANGER)
        elif t.sto_active:
            self.lbl_sto_pill.config(text="STO TRIPPED", bg="#4A141A", fg=COLOR_DANGER)
        else:
            self.lbl_sto_pill.config(text="STO OK (A+B HIGH)", bg="#16381C", fg=COLOR_MURR_LIME)

        # Update Position Card
        self.card_position.set_position(t.position_actual)

        # Update Gauges
        self.gauge_speed.set_value(t.velocity_rpm, "{:.0f}")
        self.gauge_torque.set_value(t.torque_actual / 10.0, "{:.1f}")
        self.gauge_voltage.set_value(t.dc_bus_voltage_v, "{:.1f}")
        self.gauge_temp.set_value(t.temperature_c, "{:.1f}")

        # Update Scope with Speed, Position, Torque
        self.scope.append_sample(
            vel=t.velocity_rpm,
            pos=float(t.position_actual),
            torque=t.torque_actual / 10.0
        )

        # Update Ring
        if t.led_config:
            self.ring_widget.set_config(t.led_config)
            self.ring_widget.update_animation()
            
            # Ring text desc
            mode = "User Mode" if t.led_config.user_mode else "Auto Driver"
            self.lbl_ring_desc.config(text=f"Mode: {mode} | DWORD: 0x{t.led_ctrl_dword:08X}")
