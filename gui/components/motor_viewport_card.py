"""
Motor Viewport Card Component.
Encapsulates complete real-time telemetry, gauges, optical LED ring preview,
and status pills for an individual servo motor slot.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable

from core.motor_device import MotorTelemetry, Cia402State, MODE_NAMES
from core.led_ring import LedRingConfig
from gui.components.ring_widget import LedRingWidget
from gui.components.gauge_widget import GaugeCard, PositionCard
from gui.theme import (
    COLOR_BG_DARK, COLOR_BG_SURFACE, COLOR_BG_CARD, COLOR_BG_INPUT, COLOR_BG_ACCENT,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_MUTED, COLOR_MURR_LIME, COLOR_MURR_GREEN,
    COLOR_WARNING, COLOR_DANGER, FONT_TITLE, FONT_SECTION, FONT_SUBTITLE,
    FONT_BODY, FONT_BODY_BOLD, FONT_MONO_BOLD, FONT_BADGE
)

class MotorViewportCard(tk.Frame):
    """Self-contained Dashboard Card for one servo motor axis."""

    def __init__(self, parent, title: str = "MOTOR 1 (0x1000)", station_addr: int = 0x1000,
                 on_zero_offset: Optional[Callable[[], None]] = None, **kwargs):
        super().__init__(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=12, pady=10, **kwargs)
        self.station_addr = station_addr
        self.on_zero_offset = on_zero_offset
        self.offset_counts = 0

        self._build_ui(title)

    def _build_ui(self, title: str):
        # 1. Header Bar with Title & Status Pills
        hdr = tk.Frame(self, bg=COLOR_BG_CARD)
        hdr.pack(fill="x", pady=(0, 8))

        # Title / Station Badge
        self.lbl_title = tk.Label(hdr, text=title, bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_SECTION)
        self.lbl_title.pack(side="left")

        # Status Pills (Right)
        pills = tk.Frame(hdr, bg=COLOR_BG_CARD)
        pills.pack(side="right")

        self.lbl_cia_pill = tk.Label(pills, text="DISABLED", bg="#1C3833", fg=COLOR_WARNING, font=FONT_BADGE, padx=6, pady=2)
        self.lbl_cia_pill.pack(side="left", padx=2)

        self.lbl_mode_pill = tk.Label(pills, text="PV MODE", bg="#123631", fg="#38BDF8", font=FONT_BADGE, padx=6, pady=2)
        self.lbl_mode_pill.pack(side="left", padx=2)

        self.lbl_sto_pill = tk.Label(pills, text="STO OK", bg="#16381C", fg=COLOR_MURR_LIME, font=FONT_BADGE, padx=6, pady=2)
        self.lbl_sto_pill.pack(side="left", padx=2)

        # 2. Split Body: Left = Optical Ring Preview, Right = Gauges Grid
        body = tk.Frame(self, bg=COLOR_BG_CARD)
        body.pack(fill="both", expand=True)

        # Left Column: Optical Ring
        ring_col = tk.Frame(body, bg=COLOR_BG_CARD, width=170)
        ring_col.pack(side="left", fill="y", padx=(0, 10))

        self.ring_widget = LedRingWidget(ring_col, size=155)
        self.ring_widget.pack(pady=(2, 4))

        self.lbl_ring_desc = tk.Label(ring_col, text="Auto Mode | 0x00000000", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_BADGE)
        self.lbl_ring_desc.pack()

        # Right Column: Live Telemetry Gauges
        gauges_col = tk.Frame(body, bg=COLOR_BG_CARD)
        gauges_col.pack(side="left", fill="both", expand=True)

        # Position Card
        self.card_pos = PositionCard(gauges_col, on_zero_offset=self._handle_zero)
        self.card_pos.pack(fill="x", pady=(0, 4))

        # 2x2 Sensor Gauges Grid
        grid = tk.Frame(gauges_col, bg=COLOR_BG_CARD)
        grid.pack(fill="both", expand=True)

        self.gauge_vel = GaugeCard(grid, title="ACTUAL VELOCITY", unit="RPM", min_val=-4000, max_val=4000)
        self.gauge_vel.grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=2)

        self.gauge_torque = GaugeCard(grid, title="ACTUAL TORQUE", unit="%", min_val=-100, max_val=100)
        self.gauge_torque.grid(row=0, column=1, sticky="ew", pady=2)

        self.gauge_bus = GaugeCard(grid, title="DC BUS VOLTAGE", unit="V", min_val=0, max_val=60)
        self.gauge_bus.grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=(2, 0))

        self.gauge_temp = GaugeCard(grid, title="TEMPERATURE", unit="°C", min_val=0, max_val=100)
        self.gauge_temp.grid(row=1, column=1, sticky="ew", pady=(2, 0))

        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

    def _handle_zero(self):
        self.offset_counts = self._last_raw_pos
        self.card_pos.set_position(0)
        if self.on_zero_offset:
            self.on_zero_offset()

    def update_telemetry(self, t: MotorTelemetry):
        self._last_raw_pos = t.position_actual
        rel_pos = t.position_actual - self.offset_counts
        
        # 1. Update Position
        self.card_pos.set_position(rel_pos)

        # 2. Update Gauges
        self.gauge_vel.set_value(float(t.velocity_rpm), f"{t.velocity_rpm}")
        self.gauge_torque.set_value(t.torque_percent, f"{t.torque_percent:.1f}")
        self.gauge_bus.set_value(t.dc_bus_voltage_v, f"{t.dc_bus_voltage_v:.1f}")
        self.gauge_temp.set_value(t.temperature_c, f"{t.temperature_c:.1f}")

        # 3. Update Pills
        # CiA 402 State
        state_str = t.cia_state.value.upper()
        if t.cia_state == Cia402State.OPERATION_ENABLED:
            self.lbl_cia_pill.config(text=state_str, bg="#16381C", fg=COLOR_MURR_LIME)
        elif t.cia_state in (Cia402State.FAULT, Cia402State.FAULT_REACTION_ACTIVE):
            self.lbl_cia_pill.config(text=state_str, bg="#4A141A", fg=COLOR_DANGER)
        else:
            self.lbl_cia_pill.config(text=state_str, bg="#1C3833", fg=COLOR_WARNING)

        # Operating Mode
        mode_name = MODE_NAMES.get(t.mode_of_operation, f"MODE {t.mode_of_operation}")
        self.lbl_mode_pill.config(text=mode_name)

        # STO Status
        if t.sto_info and t.sto_info.is_fault:
            if t.sto_info.code in (6, 11, 0x0B):
                self.lbl_sto_pill.config(text="STO TRIPPED / NO INPUT", bg="#4A141A", fg=COLOR_DANGER)
            elif t.sto_info.code == 3:
                self.lbl_sto_pill.config(text="STO A MISSING", bg="#4A141A", fg=COLOR_DANGER)
            elif t.sto_info.code == 5:
                self.lbl_sto_pill.config(text="STO B MISSING", bg="#4A141A", fg=COLOR_DANGER)
            else:
                self.lbl_sto_pill.config(text="STO TRIPPED", bg="#4A141A", fg=COLOR_DANGER)
        elif t.sto_active:
            self.lbl_sto_pill.config(text="STO TRIPPED / NO INPUT", bg="#4A141A", fg=COLOR_DANGER)
        else:
            self.lbl_sto_pill.config(text="STO OK (A+B HIGH)", bg="#16381C", fg=COLOR_MURR_LIME)

        # Optical Ring preview
        if t.led_config:
            self.ring_widget.set_config(t.led_config)
            self.lbl_ring_desc.config(text=t.led_config.description[:26])
