"""
CiA 402 Motion & Drive Control Tab.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

from core.motor_device import (
    Cia402State, OperationMode, MotorTelemetry, MODE_NAMES,
    CMD_SHUTDOWN, CMD_SWITCH_ON, CMD_ENABLE_OPERATION, CMD_DISABLE_VOLTAGE,
    CMD_QUICK_STOP, CMD_FAULT_RESET
)
from gui.theme import (
    COLOR_BG_SURFACE, COLOR_BG_CARD, COLOR_BG_INPUT, COLOR_BG_ACCENT,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_MUTED, COLOR_MURR_LIME, COLOR_MURR_GREEN,
    COLOR_WARNING, COLOR_DANGER, FONT_TITLE, FONT_SECTION, FONT_SUBTITLE,
    FONT_BODY_BOLD, FONT_MONO_BOLD, FONT_BADGE
)

class MotionTab(tk.Frame):
    """CiA 402 Motion Control, mode selection, jog, and setpoints."""

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COLOR_BG_SURFACE, padx=16, pady=16, **kwargs)
        self.app = app

        # Variables
        self.var_mode = tk.StringVar(value=MODE_NAMES[3])
        self.var_speed = tk.DoubleVar(value=0.0)
        self.var_pos = tk.IntVar(value=0)
        self.var_rel_pos = tk.IntVar(value=10000)

        # 2-Column Layout
        content = tk.Frame(self, bg=COLOR_BG_SURFACE)
        content.pack(fill="both", expand=True)

        col_left = tk.Frame(content, bg=COLOR_BG_SURFACE, width=460)
        col_left.pack(side="left", fill="both", expand=True, padx=(0, 16))
        self._build_cia_panel(col_left)

        col_right = tk.Frame(content, bg=COLOR_BG_SURFACE, width=460)
        col_right.pack(side="left", fill="both", expand=True)
        self._build_motion_panel(col_right)

    def _build_cia_panel(self, parent):
        # 1. State Machine Card
        card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=16, pady=16)
        card.pack(fill="x", pady=(0, 16))

        tk.Label(card, text="CiA 402 DRIVE STATE MACHINE", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_TITLE).pack(anchor="w")
        
        # State Readout
        state_box = tk.Frame(card, bg=COLOR_BG_INPUT, padx=12, pady=10)
        state_box.pack(fill="x", pady=(10, 14))

        self.lbl_current_state = tk.Label(
            state_box, text="STATE: SWITCH ON DISABLED (0x0240)",
            bg=COLOR_BG_INPUT, fg=COLOR_WARNING, font=FONT_MONO_BOLD
        )
        self.lbl_current_state.pack(anchor="w")

        # Step Sequence Buttons
        tk.Label(card, text="Standard Enable Sequence (0x6040 Controlword):", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_SUBTITLE).pack(anchor="w", pady=(0, 6))

        seq_grid = tk.Frame(card, bg=COLOR_BG_CARD)
        seq_grid.pack(fill="x")

        ttk.Button(seq_grid, text="1. Shutdown (0x0006)", style="Action.TButton", command=lambda: self.app.send_controlword(CMD_SHUTDOWN)).grid(row=0, column=0, sticky="ew", padx=2, pady=3)
        ttk.Button(seq_grid, text="2. Switch On (0x0007)", style="Action.TButton", command=lambda: self.app.send_controlword(CMD_SWITCH_ON)).grid(row=0, column=1, sticky="ew", padx=2, pady=3)
        ttk.Button(seq_grid, text="3. Enable Op (0x000F)", style="Murr.TButton", command=lambda: self.app.send_controlword(CMD_ENABLE_OPERATION)).grid(row=1, column=0, columnspan=2, sticky="ew", padx=2, pady=3)
        
        seq_grid.columnconfigure(0, weight=1)
        seq_grid.columnconfigure(1, weight=1)

        # Interlock & Emergency Actions
        tk.Label(card, text="Interlocks & Recovery:", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_SUBTITLE).pack(anchor="w", pady=(12, 6))

        rec_grid = tk.Frame(card, bg=COLOR_BG_CARD)
        rec_grid.pack(fill="x")

        ttk.Button(rec_grid, text="Quick Stop (0x0002)", style="Danger.TButton", command=lambda: self.app.send_controlword(CMD_QUICK_STOP)).grid(row=0, column=0, sticky="ew", padx=2, pady=3)
        ttk.Button(rec_grid, text="Disable Voltage (0x0000)", style="Action.TButton", command=lambda: self.app.send_controlword(CMD_DISABLE_VOLTAGE)).grid(row=0, column=1, sticky="ew", padx=2, pady=3)
        ttk.Button(rec_grid, text="Fault Reset (0x0080)", style="Action.TButton", command=lambda: self.app.send_controlword(CMD_FAULT_RESET)).grid(row=1, column=0, columnspan=2, sticky="ew", padx=2, pady=3)

        rec_grid.columnconfigure(0, weight=1)
        rec_grid.columnconfigure(1, weight=1)

        # 2. Operating Mode Selector Card
        mode_card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=16, pady=16)
        mode_card.pack(fill="both", expand=True)

        tk.Label(mode_card, text="OPERATING MODE (0x6060 / 0x6061)", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_TITLE).pack(anchor="w", pady=(0, 8))

        modes_list = list(MODE_NAMES.values())
        cb_mode = ttk.Combobox(mode_card, textvariable=self.var_mode, values=modes_list, state="readonly")
        cb_mode.pack(fill="x", pady=(0, 8))

        ttk.Button(mode_card, text="Set Mode of Operation (SDO 0x6060)", style="Action.TButton", command=self._apply_mode).pack(fill="x")

    def _build_motion_panel(self, parent):
        # Velocity Control Card
        vel_card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=16, pady=16)
        vel_card.pack(fill="x", pady=(0, 16))

        tk.Label(vel_card, text="VELOCITY COMMAND (0x60FF / RPM)", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_TITLE).pack(anchor="w")

        # Slider
        slider = tk.Scale(
            vel_card, from_=-3000, to=3000, orient="horizontal",
            variable=self.var_speed, command=lambda v: self._on_slider_speed(float(v)),
            bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, troughcolor=COLOR_BG_INPUT,
            highlightthickness=0, font=FONT_SUBTITLE, resolution=10
        )
        slider.pack(fill="x", pady=(8, 4))

        # Speed Presets
        presets_frame = tk.Frame(vel_card, bg=COLOR_BG_CARD)
        presets_frame.pack(fill="x", pady=4)

        for rpm in [0, 100, 500, 1000, 1500, 3000]:
            ttk.Button(presets_frame, text=f"{rpm}", style="Action.TButton", command=lambda r=rpm: self._set_speed(float(r))).pack(side="left", fill="x", expand=True, padx=2)

        # Jog Controls
        jog_frame = tk.Frame(vel_card, bg=COLOR_BG_CARD, pady=6)
        jog_frame.pack(fill="x")

        ttk.Button(jog_frame, text="<<< JOG REV (-500 RPM)", style="Action.TButton", command=lambda: self._set_speed(-500.0)).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(jog_frame, text="STOP (0 RPM)", style="Danger.TButton", command=lambda: self._set_speed(0.0)).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(jog_frame, text="JOG FWD (+500 RPM) >>>", style="Action.TButton", command=lambda: self._set_speed(500.0)).pack(side="left", fill="x", expand=True, padx=(4, 0))

        # Position Control Card
        pos_card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=16, pady=16)
        pos_card.pack(fill="both", expand=True)

        tk.Label(pos_card, text="POSITION COMMAND (0x607A / Counts)", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_TITLE).pack(anchor="w")

        p_box = tk.Frame(pos_card, bg=COLOR_BG_CARD, pady=8)
        p_box.pack(fill="x")

        tk.Label(p_box, text="Target Position:", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_BODY_BOLD).pack(side="left", padx=(0, 8))
        ttk.Entry(p_box, textvariable=self.var_pos, font=FONT_MONO_BOLD, width=14).pack(side="left", padx=(0, 8))
        ttk.Button(p_box, text="Move to Position", style="Murr.TButton", command=self._apply_position).pack(side="left")

        # Relative delta buttons
        rel_frame = tk.Frame(pos_card, bg=COLOR_BG_CARD, pady=6)
        rel_frame.pack(fill="x")

        ttk.Button(rel_frame, text="-50,000", style="Action.TButton", command=lambda: self._rel_move(-50000)).pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(rel_frame, text="-10,000", style="Action.TButton", command=lambda: self._rel_move(-10000)).pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(rel_frame, text="+10,000", style="Action.TButton", command=lambda: self._rel_move(10000)).pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(rel_frame, text="+50,000", style="Action.TButton", command=lambda: self._rel_move(50000)).pack(side="left", fill="x", expand=True, padx=2)

    def _apply_mode(self):
        mode_str = self.var_mode.get()
        mode_val = 3
        for k, v in MODE_NAMES.items():
            if v == mode_str:
                mode_val = k
                break
        data = int(mode_val).to_bytes(1, 'little', signed=True)
        err = self.app.sdo_write(0x6060, 0x00, data)
        if err:
            messagebox.showerror("Mode Switch Failed", f"Error setting Mode 0x6060:\n{err}")
        else:
            self.app.log(f"Set Mode of Operation: {mode_str} ({mode_val})")

    def _on_slider_speed(self, val: float):
        self._send_speed(val)

    def _set_speed(self, val: float):
        self.var_speed.set(val)
        self._send_speed(val)

    def _send_speed(self, val: float):
        rpm_int = int(val)
        data = rpm_int.to_bytes(4, 'little', signed=True)
        self.app.sdo_write(0x60FF, 0x00, data)

    def _apply_position(self):
        pos = self.var_pos.get()
        data = int(pos).to_bytes(4, 'little', signed=True)
        err = self.app.sdo_write(0x607A, 0x00, data)
        if not err:
            # Trigger position move (Controlword bit 4)
            self.app.send_controlword(0x003F)
            self.app.log(f"Target Position commanded: {pos} counts")

    def _rel_move(self, delta: int):
        curr_pos = self.app.current_telemetry.position_actual if self.app.current_telemetry else 0
        new_pos = curr_pos + delta
        self.var_pos.set(new_pos)
        self._apply_position()

    def update_telemetry(self, t: MotorTelemetry):
        state_str = t.cia_state.value.upper()
        color = COLOR_MURR_LIME if t.cia_state == Cia402State.OPERATION_ENABLED else COLOR_WARNING
        if t.cia_state == Cia402State.FAULT or t.error_code != 0:
            color = COLOR_DANGER
        self.lbl_current_state.config(
            text=f"STATE: {state_str} (Statusword 0x{t.statusword:04X})",
            fg=color
        )
