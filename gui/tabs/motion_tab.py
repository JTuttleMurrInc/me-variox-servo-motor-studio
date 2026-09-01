"""
CiA 402 Multi-Axis Motion & Drive Control Tab.
Supports independent Axis 1, Axis 2, Synchronized Gantry, and Mirrored Dual-Axis Motion.
Features:
  - Multi-Axis Target Routing (Motor 1, Motor 2, Synchronized Dual, Mirrored Dual).
  - Safety Interlock Modal requirement prior to physical shaft movement.
  - Dedicated Setpoint Move Speed (Profile Velocity 0x6081) with 4000/6000 RPM limits.
  - 4,000 RPM Harmonic Reversing Sweep Routine (4 -> 2 -> 1 -> 0.5 -> 0.25 rev & reverse).
  - Multi-demo motion choreography suite with synchronized optical LED ring effects.
"""

import time
import math
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, List, Tuple, Callable, Dict

from core.motor_device import (
    Cia402State, OperationMode, MotorTelemetry, MODE_NAMES,
    CMD_SHUTDOWN, CMD_SWITCH_ON, CMD_ENABLE_OPERATION, CMD_DISABLE_VOLTAGE,
    CMD_QUICK_STOP, CMD_FAULT_RESET
)
from core.led_ring import LedRingConfig, RING_PRESETS
from gui.components.safety_modal import MotionSafetyModal
from gui.theme import (
    COLOR_BG_DARK, COLOR_BG_SURFACE, COLOR_BG_CARD, COLOR_BG_INPUT, COLOR_BG_ACCENT,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_MUTED, COLOR_MURR_LIME, COLOR_MURR_GREEN,
    COLOR_WARNING, COLOR_DANGER, FONT_TITLE, FONT_SECTION, FONT_SUBTITLE,
    FONT_BODY, FONT_BODY_BOLD, FONT_MONO, FONT_MONO_BOLD, FONT_BADGE
)

SPEED_RATED_RPM = 4000
SPEED_MAX_RPM = 6000
ENCODER_COUNTS_PER_REV = 65536

# Target Selection Modes
TARGET_M1 = "m1"
TARGET_M2 = "m2"
TARGET_DUAL_SYNC = "dual_sync"
TARGET_DUAL_MIRROR = "dual_mirror"

class MotionTab(tk.Frame):
    """CiA 402 Multi-Axis Motion Control, mode selection, jog, setpoints, and automated demo routines."""

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COLOR_BG_SURFACE, padx=16, pady=16, **kwargs)
        self.app = app
        self.safety_acknowledged = False
        self.extended_speed_unlocked = False
        self._routine_running = False
        self._routine_stop_event = threading.Event()

        # Multi-Axis Target Selection
        self.var_target_axis = tk.StringVar(value=TARGET_DUAL_SYNC)

        # Motion Parameters
        self.var_mode = tk.StringVar(value=MODE_NAMES[3])
        self.var_speed_rpm = tk.DoubleVar(value=0.0)
        self.var_pos = tk.IntVar(value=0)
        
        # Kinematic Limits
        self.var_move_rpm = tk.IntVar(value=1000)          # 0x6081 Profile Move Velocity (RPM)
        self.var_accel = tk.IntVar(value=200000)           # 0x6083 Profile Accel (inc/s²)
        self.var_decel = tk.IntVar(value=200000)           # 0x6084 Profile Decel (inc/s²)
        self.var_is_relative = tk.BooleanVar(value=False)  # Bit 6 in 0x6040

        # Routine Status Variables
        self.var_routine_name = tk.StringVar(value="Routine Idle")
        self.var_routine_step = tk.StringVar(value="Ready to execute multi-axis choreographed motion routines")
        self.var_routine_progress = tk.DoubleVar(value=0.0)

        # 1. Top Safety Status & Axis Selector Bar
        self._build_header_bar()

        # 2. Main 2-Column Content Layout
        content = tk.Frame(self, bg=COLOR_BG_SURFACE)
        content.pack(fill="both", expand=True, pady=(8, 0))

        col_left = tk.Frame(content, bg=COLOR_BG_SURFACE, width=470)
        col_left.pack(side="left", fill="both", expand=True, padx=(0, 16))
        self._build_cia_panel(col_left)
        self._build_demo_routines_panel(col_left)

        col_right = tk.Frame(content, bg=COLOR_BG_SURFACE, width=470)
        col_right.pack(side="left", fill="both", expand=True)
        self._build_motion_panel(col_right)

    def _build_header_bar(self):
        hdr_bar = tk.Frame(self, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=14, pady=8)
        hdr_bar.pack(fill="x")

        # Left Safety Interlock Status Pill
        self.lbl_safety_pill = tk.Label(
            hdr_bar, text="🛡️ MOTION SAFETY INTERLOCK: LOCKED (Acknowledgment Required)",
            bg="#381014", fg=COLOR_DANGER, font=FONT_BODY_BOLD, padx=10, pady=4
        )
        self.lbl_safety_pill.pack(side="left")

        # Center Multi-Axis Target Selection Tabs
        axis_box = tk.Frame(hdr_bar, bg=COLOR_BG_CARD)
        axis_box.pack(side="left", padx=20)

        tk.Label(axis_box, text="COMMAND TARGET:", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_BADGE).pack(side="left", padx=(0, 6))
        
        targets = [
            (TARGET_DUAL_SYNC, "🔗 Dual Sync"),
            (TARGET_DUAL_MIRROR, "🪞 Dual Mirror"),
            (TARGET_M1, "Axis 1 (0x1000)"),
            (TARGET_M2, "Axis 2 (0x1001)"),
        ]
        for val, lbl in targets:
            rb = tk.Radiobutton(
                axis_box, text=lbl, value=val, variable=self.var_target_axis,
                bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, selectcolor=COLOR_BG_INPUT,
                activebackground=COLOR_BG_CARD, activeforeground=COLOR_MURR_LIME,
                font=FONT_BODY_BOLD, indicatoron=False, padx=8, pady=3,
                command=self._on_target_change
            )
            rb.pack(side="left", padx=2)

        # Right Interlock Control Button
        self.btn_safety_toggle = tk.Button(
            hdr_bar, text="Arm / Acknowledge Safety Interlock",
            bg=COLOR_BG_INPUT, fg=COLOR_TEXT_PRIMARY, activebackground=COLOR_BG_ACCENT,
            font=FONT_BADGE, padx=10, pady=3, relief="flat",
            highlightbackground=COLOR_BG_ACCENT, highlightthickness=1,
            command=self._toggle_safety_interlock
        )
        self.btn_safety_toggle.pack(side="right")

    def _build_cia_panel(self, parent):
        card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=14, pady=12)
        card.pack(fill="x", pady=(0, 10))

        tk.Label(card, text="CiA 402 DUAL-AXIS STATE MACHINE", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_TITLE).pack(anchor="w")
        
        # Dual State Readout Box
        state_box = tk.Frame(card, bg=COLOR_BG_INPUT, padx=10, pady=6)
        state_box.pack(fill="x", pady=(6, 10))

        self.lbl_m1_state = tk.Label(state_box, text="M1 (0x1000): SWITCH ON DISABLED (0x0240)", bg=COLOR_BG_INPUT, fg=COLOR_WARNING, font=FONT_BADGE)
        self.lbl_m1_state.pack(anchor="w")

        self.lbl_m2_state = tk.Label(state_box, text="M2 (0x1001): SWITCH ON DISABLED (0x0240)", bg=COLOR_BG_INPUT, fg=COLOR_WARNING, font=FONT_BADGE)
        self.lbl_m2_state.pack(anchor="w", pady=(2, 0))

        # Step Sequence Buttons (Broadcast to target axes)
        tk.Label(card, text="Standard Enable Sequence (Controlword 0x6040):", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_SUBTITLE).pack(anchor="w", pady=(0, 6))

        seq_grid = tk.Frame(card, bg=COLOR_BG_CARD)
        seq_grid.pack(fill="x")

        ttk.Button(seq_grid, text="1. Shutdown (0x0006)", style="Action.TButton", command=lambda: self._send_controlword_targeted(CMD_SHUTDOWN)).grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(seq_grid, text="2. Switch On (0x0007)", style="Action.TButton", command=lambda: self._send_controlword_targeted(CMD_SWITCH_ON)).grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        ttk.Button(seq_grid, text="3. Enable Op (0x000F)", style="Murr.TButton", command=self._full_enable_drive).grid(row=1, column=0, columnspan=2, sticky="ew", padx=2, pady=2)
        
        seq_grid.columnconfigure(0, weight=1)
        seq_grid.columnconfigure(1, weight=1)

        # Interlocks & Emergency Actions
        rec_grid = tk.Frame(card, bg=COLOR_BG_CARD)
        rec_grid.pack(fill="x", pady=(6, 0))

        ttk.Button(rec_grid, text="Quick Stop All", style="Danger.TButton", command=self.app.action_quick_stop).grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(rec_grid, text="Disable All Voltage", style="Action.TButton", command=self.app.action_disable_drive).grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        ttk.Button(rec_grid, text="Reset All Faults", style="Action.TButton", command=self.app.action_fault_reset).grid(row=1, column=0, columnspan=2, sticky="ew", padx=2, pady=2)

        rec_grid.columnconfigure(0, weight=1)
        rec_grid.columnconfigure(1, weight=1)

    def _build_demo_routines_panel(self, parent):
        card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=14, pady=12)
        card.pack(fill="both", expand=True)

        tk.Label(card, text="AUTOMATED MOTION CHOREOGRAPHY", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_TITLE).pack(anchor="w")
        tk.Label(card, text="Multi-axis high-speed precision routines with optical LED sync", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_SUBTITLE).pack(anchor="w", pady=(0, 8))

        # Main Highlighted Routine: 4,000 RPM Harmonic Reversing Sweep
        btn_sweep = tk.Button(
            card, text="🌀 4,000 RPM Harmonic Reversing Sweep (4→2→1→0.5→0.25 Rev)",
            bg="#103622", fg=COLOR_MURR_LIME, activebackground=COLOR_MURR_GREEN, activeforeground=COLOR_BG_DARK,
            font=FONT_BODY_BOLD, anchor="w", padx=10, pady=7, relief="flat",
            highlightbackground=COLOR_MURR_LIME, highlightthickness=1,
            command=self.start_harmonic_sweep_routine
        )
        btn_sweep.pack(fill="x", pady=(0, 4))

        # Secondary Choreography Routines Grid (2 columns x 3 rows)
        r_grid = tk.Frame(card, bg=COLOR_BG_CARD)
        r_grid.pack(fill="x", pady=2)

        ttk.Button(r_grid, text="⚡ 0→4000 RPM Tacho Ramp", style="Action.TButton", command=self.start_tachometer_ramp_routine).grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(r_grid, text="🎡 4x90° Indexing Turntable", style="Action.TButton", command=self.start_turntable_routine).grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        
        ttk.Button(r_grid, text="📦 High-Speed Pick & Place Gantry", style="Action.TButton", command=self.start_pick_and_place_routine).grid(row=1, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(r_grid, text="⚙️ Rotary Flying Knife (4000 RPM)", style="Action.TButton", command=self.start_flying_shear_routine).grid(row=1, column=1, sticky="ew", padx=2, pady=2)

        ttk.Button(r_grid, text="🎯 Micro-Stepping Stiffness Test", style="Action.TButton", command=self.start_micro_precision_routine).grid(row=2, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(r_grid, text="🪞 Mirrored Synchronous Ballet", style="Action.TButton", command=self.start_dual_ballet_routine).grid(row=2, column=1, sticky="ew", padx=2, pady=2)

        r_grid.columnconfigure(0, weight=1)
        r_grid.columnconfigure(1, weight=1)

        # Routine Status Readout & Progress Bar
        status_box = tk.Frame(card, bg=COLOR_BG_INPUT, padx=10, pady=6)
        status_box.pack(fill="x", pady=(6, 4))

        tk.Label(status_box, textvariable=self.var_routine_name, bg=COLOR_BG_INPUT, fg="#38BDF8", font=FONT_BODY_BOLD).pack(anchor="w")
        tk.Label(status_box, textvariable=self.var_routine_step, bg=COLOR_BG_INPUT, fg=COLOR_TEXT_MUTED, font=FONT_BADGE).pack(anchor="w", pady=(2, 4))

        self.progress_bar = ttk.Progressbar(status_box, variable=self.var_routine_progress, maximum=100.0, mode="determinate")
        self.progress_bar.pack(fill="x")

        # Abort Routine Button
        self.btn_abort_routine = tk.Button(
            card, text="⏹️ Abort Running Routine", bg="#4A141A", fg=COLOR_DANGER,
            activebackground=COLOR_DANGER, activeforeground=COLOR_TEXT_PRIMARY,
            font=FONT_BODY_BOLD, padx=10, pady=4, relief="flat", state="disabled",
            command=self.stop_current_routine
        )
        self.btn_abort_routine.pack(fill="x", pady=(6, 0))

    def _build_motion_panel(self, parent):
        # 1. Velocity / Jog Control Card
        vel_card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=14, pady=12)
        vel_card.pack(fill="x", pady=(0, 10))

        v_hdr = tk.Frame(vel_card, bg=COLOR_BG_CARD)
        v_hdr.pack(fill="x")
        tk.Label(v_hdr, text="VELOCITY / JOG COMMAND (0x60FF)", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_TITLE).pack(side="left")
        self.lbl_vel_mode_badge = tk.Label(v_hdr, text="RATED (≤4000 RPM)", bg="#16381C", fg=COLOR_MURR_LIME, font=FONT_BADGE, padx=6, pady=2)
        self.lbl_vel_mode_badge.pack(side="right")

        # Velocity Slider
        self.slider_vel = tk.Scale(
            vel_card, from_=-SPEED_RATED_RPM, to=SPEED_RATED_RPM, orient="horizontal",
            variable=self.var_speed_rpm, command=lambda v: self._on_slider_speed(float(v)),
            bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, troughcolor=COLOR_BG_INPUT,
            highlightthickness=0, font=FONT_SUBTITLE, resolution=50
        )
        self.slider_vel.pack(fill="x", pady=(4, 4))

        # Speed Presets
        presets_frame = tk.Frame(vel_card, bg=COLOR_BG_CARD)
        presets_frame.pack(fill="x", pady=2)

        for rpm in [0, 250, 500, 1000, 2000, 4000]:
            ttk.Button(presets_frame, text=f"{rpm}", style="Action.TButton", command=lambda r=rpm: self._set_speed(float(r))).pack(side="left", fill="x", expand=True, padx=2)
        
        self.btn_6k_vel = tk.Button(
            presets_frame, text="6000*", bg=COLOR_BG_INPUT, fg=COLOR_WARNING,
            activebackground=COLOR_BG_ACCENT, activeforeground=COLOR_WARNING,
            font=FONT_BODY_BOLD, relief="flat", highlightbackground=COLOR_WARNING, highlightthickness=1,
            command=lambda: self._set_speed(6000.0)
        )
        self.btn_6k_vel.pack(side="left", fill="x", expand=True, padx=2)

        # Jog Controls
        jog_frame = tk.Frame(vel_card, bg=COLOR_BG_CARD, pady=4)
        jog_frame.pack(fill="x")

        ttk.Button(jog_frame, text="⏪ JOG REV (-500 RPM)", style="Action.TButton", command=lambda: self._set_speed(-500.0)).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(jog_frame, text="⏹️ STOP (0 RPM)", style="Danger.TButton", command=lambda: self._set_speed(0.0)).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(jog_frame, text="JOG FWD (+500 RPM) ⏩", style="Action.TButton", command=lambda: self._set_speed(500.0)).pack(side="left", fill="x", expand=True, padx=(4, 0))

        # 2. Position Setpoint Control Card
        pos_card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=14, pady=12)
        pos_card.pack(fill="both", expand=True)

        tk.Label(pos_card, text="POSITION SETPOINT COMMAND (0x607A)", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_TITLE).pack(anchor="w")
        tk.Label(pos_card, text="Coordinates in Encoder Counts (65,536 inc = 1 Revolution)", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_SUBTITLE).pack(anchor="w", pady=(0, 6))

        # Dedicated Setpoint Move Speed Control (0x6081)
        speed_box = tk.LabelFrame(pos_card, text=" Setpoint Move Speed (Profile Velocity 0x6081) ", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_BODY_BOLD, padx=8, pady=4)
        speed_box.pack(fill="x", pady=(0, 8))

        s_row = tk.Frame(speed_box, bg=COLOR_BG_CARD)
        s_row.pack(fill="x", pady=2)
        tk.Label(s_row, text="Target Move Velocity:", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_BODY_BOLD).pack(side="left")
        tk.Label(s_row, text="RPM", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_BADGE).pack(side="right")
        self.entry_move_rpm = ttk.Entry(s_row, textvariable=self.var_move_rpm, font=FONT_MONO_BOLD, width=8)
        self.entry_move_rpm.pack(side="right", padx=6)

        s_presets = tk.Frame(speed_box, bg=COLOR_BG_CARD)
        s_presets.pack(fill="x", pady=(2, 2))
        for pr_rpm in [250, 500, 1000, 2000, 4000]:
            ttk.Button(s_presets, text=f"{pr_rpm} RPM", style="Action.TButton", command=lambda r=pr_rpm: self._set_move_speed(r)).pack(side="left", fill="x", expand=True, padx=2)
        
        self.btn_6k_move = tk.Button(
            s_presets, text="6000*", bg=COLOR_BG_INPUT, fg=COLOR_WARNING,
            activebackground=COLOR_BG_ACCENT, activeforeground=COLOR_WARNING,
            font=FONT_BODY_BOLD, relief="flat", highlightbackground=COLOR_WARNING, highlightthickness=1,
            command=lambda: self._set_move_speed(6000)
        )
        self.btn_6k_move.pack(side="left", fill="x", expand=True, padx=2)

        # Position Command Input Box
        p_box = tk.Frame(pos_card, bg=COLOR_BG_CARD, pady=4)
        p_box.pack(fill="x")

        tk.Label(p_box, text="Target Pos:", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_BODY_BOLD).pack(side="left", padx=(0, 8))
        ttk.Entry(p_box, textvariable=self.var_pos, font=FONT_MONO_BOLD, width=12).pack(side="left", padx=(0, 8))
        
        chk_rel = tk.Checkbutton(
            p_box, text="Relative Move", variable=self.var_is_relative,
            bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, activebackground=COLOR_BG_CARD,
            activeforeground=COLOR_MURR_LIME, selectcolor=COLOR_BG_INPUT, font=FONT_BODY_BOLD
        )
        chk_rel.pack(side="left", padx=(0, 8))

        ttk.Button(p_box, text="🚀 Execute Move", style="Murr.TButton", command=self._apply_position).pack(side="left")

        # Quick Step Increments
        tk.Label(pos_card, text="Quick Step Increments (Executed with current move speed):", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_BADGE).pack(anchor="w", pady=(8, 2))
        rel_frame = tk.Frame(pos_card, bg=COLOR_BG_CARD)
        rel_frame.pack(fill="x")

        ttk.Button(rel_frame, text="-1 Rev (-65k)", style="Action.TButton", command=lambda: self._rel_move(-65536)).pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(rel_frame, text="-90° (-16k)", style="Action.TButton", command=lambda: self._rel_move(-16384)).pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(rel_frame, text="+90° (+16k)", style="Action.TButton", command=lambda: self._rel_move(16384)).pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(rel_frame, text="+1 Rev (+65k)", style="Action.TButton", command=lambda: self._rel_move(65536)).pack(side="left", fill="x", expand=True, padx=2)

    def _on_target_change(self):
        target = self.var_target_axis.get()
        self.app.log(f"Active Motion Command Target: {target.upper()}")

    def _get_target_addresses(self) -> List[Tuple[int, float]]:
        """
        Returns list of (station_addr, direction_multiplier) for current target mode:
          - TARGET_M1: [(0x1000, 1.0)]
          - TARGET_M2: [(0x1001, 1.0)]
          - TARGET_DUAL_SYNC: [(0x1000, 1.0), (0x1001, 1.0)]
          - TARGET_DUAL_MIRROR: [(0x1000, 1.0), (0x1001, -1.0)]
        """
        t = self.var_target_axis.get()
        if t == TARGET_M1:
            return [(0x1000, 1.0)]
        elif t == TARGET_M2:
            return [(0x1001, 1.0)]
        elif t == TARGET_DUAL_MIRROR:
            return [(0x1000, 1.0), (0x1001, -1.0)]
        else: # Dual Sync default
            return [(0x1000, 1.0), (0x1001, 1.0)]

    def _send_controlword_targeted(self, cw: int):
        for addr, _ in self._get_target_addresses():
            self.app.send_controlword_slave(addr, cw)

    def _require_safety_acknowledgment(self, on_confirmed_callback: Callable[[], None]) -> bool:
        if self.safety_acknowledged:
            on_confirmed_callback()
            return True

        def _on_confirm():
            self.safety_acknowledged = True
            self.lbl_safety_pill.config(text="🛡️ MOTION SAFETY INTERLOCK: ARMED & ACKNOWLEDGED", bg="#16381C", fg=COLOR_MURR_LIME)
            self.btn_safety_toggle.config(text="Disarm / Lock Safety Interlock")
            self.app.log("Safety Interlock armed and acknowledged by operator.")
            on_confirmed_callback()

        MotionSafetyModal(self.winfo_toplevel(), on_confirm=_on_confirm)
        return False

    def _toggle_safety_interlock(self):
        if self.safety_acknowledged:
            self.safety_acknowledged = False
            self.lbl_safety_pill.config(text="🛡️ MOTION SAFETY INTERLOCK: LOCKED (Acknowledgment Required)", bg="#381014", fg=COLOR_DANGER)
            self.btn_safety_toggle.config(text="Arm / Acknowledge Safety Interlock")
            # Force all motors into safe Shutdown (0x0006)
            self.app.action_disable_drive()
            self.app.log("Safety Interlock locked. All motors placed in Shutdown (0x0006 / Ready to Switch On).")
        else:
            self._require_safety_acknowledgment(lambda: None)

    def _prompt_extended_speed_acknowledgment(self) -> bool:
        if self.extended_speed_unlocked:
            return True

        msg = (
            "⚠️ HIGH-SPEED MOTOR PERFORMANCE NOTICE (Section 5.3):\n\n"
            "• Rated Speed: 4,000 RPM (0.8 Nm continuous S1 torque)\n"
            "• Maximum Speed: 6,000 RPM (operating in reduced-torque region)\n\n"
            "Operating between 4,001 and 6,000 RPM utilizes field weakening with "
            "diminished peak torque (1.5 Nm @ 6,000 RPM) and requires adherence to "
            "intermittent duty cycle limits (Section 5.3 Characteristic Curve).\n\n"
            "Do you acknowledge this operating condition and wish to enable extended 6,000 RPM operation?"
        )
        ack = messagebox.askyesno("Extended Speed Acknowledgment (6,000 RPM)", msg, icon="warning")
        if ack:
            self.extended_speed_unlocked = True
            self.slider_vel.config(from_=-SPEED_MAX_RPM, to=SPEED_MAX_RPM)
            self.lbl_vel_mode_badge.config(text="EXTENDED UNLOCKED (≤6000 RPM)", bg="#4A2A0A", fg=COLOR_WARNING)
            self.app.log("User acknowledged Section 5.3: Extended 6,000 RPM operation enabled.")
            return True
        return False

    def _set_move_speed(self, rpm: int):
        if rpm > SPEED_RATED_RPM:
            if not self._prompt_extended_speed_acknowledgment():
                rpm = SPEED_RATED_RPM
        self.var_move_rpm.set(rpm)
        self.app.log(f"Configured Setpoint Move Speed: {rpm} RPM")

    def _full_enable_drive(self):
        self._require_safety_acknowledgment(self._do_full_enable_drive)

    def _do_full_enable_drive(self):
        for addr, _ in self._get_target_addresses():
            self.app.sdo_write_slave(addr, 0x6060, 0x00, (3).to_bytes(1, 'little', signed=True))
            rpm = self.var_move_rpm.get()
            vel_inc_s = int(round(rpm * ENCODER_COUNTS_PER_REV / 60.0))
            self.app.sdo_write_slave(addr, 0x6081, 0x00, vel_inc_s.to_bytes(4, 'little'))
            self.app.sdo_write_slave(addr, 0x6083, 0x00, int(self.var_accel.get()).to_bytes(4, 'little'))
            self.app.sdo_write_slave(addr, 0x6084, 0x00, int(self.var_decel.get()).to_bytes(4, 'little'))
            
            self.app.send_controlword_slave(addr, CMD_SHUTDOWN)
            time.sleep(0.02)
            self.app.send_controlword_slave(addr, CMD_SWITCH_ON)
            time.sleep(0.02)
            self.app.send_controlword_slave(addr, CMD_ENABLE_OPERATION)
        self.app.log("Drive Enable sequence dispatched to active target axes.")

    def _on_slider_speed(self, val: float):
        if abs(val) > SPEED_RATED_RPM and not self.extended_speed_unlocked:
            if not self._prompt_extended_speed_acknowledgment():
                clamped = math.copysign(SPEED_RATED_RPM, val)
                self.var_speed_rpm.set(clamped)
                val = clamped
        self._require_safety_acknowledgment(lambda: self._send_speed(val))

    def _set_speed(self, val: float):
        if abs(val) > SPEED_RATED_RPM and not self.extended_speed_unlocked:
            if not self._prompt_extended_speed_acknowledgment():
                val = math.copysign(SPEED_RATED_RPM, val)
        self.var_speed_rpm.set(val)
        self._require_safety_acknowledgment(lambda: self._send_speed(val))

    def _send_speed(self, val: float):
        if abs(val) > SPEED_MAX_RPM:
            val = math.copysign(SPEED_MAX_RPM, val)
            self.var_speed_rpm.set(val)

        accel = int(self.var_accel.get())
        decel = int(self.var_decel.get())

        for addr, mult in self._get_target_addresses():
            directed_rpm = val * mult
            vel_inc_s = int(round(directed_rpm * ENCODER_COUNTS_PER_REV / 60.0))
            
            self.app.sdo_write_slave(addr, 0x6060, 0x00, (3).to_bytes(1, 'little', signed=True))
            self.app.sdo_write_slave(addr, 0x6083, 0x00, accel.to_bytes(4, 'little'))
            self.app.sdo_write_slave(addr, 0x6084, 0x00, decel.to_bytes(4, 'little'))
            self.app.sdo_write_slave(addr, 0x60FF, 0x00, vel_inc_s.to_bytes(4, 'little', signed=True))
            self.app.send_controlword_slave(addr, CMD_ENABLE_OPERATION)

        self.app.log(f"Commanded Velocity: {val:.1f} RPM to target {self.var_target_axis.get().upper()}")

    def _apply_position(self):
        self._require_safety_acknowledgment(self._do_apply_position)

    def _do_apply_position(self):
        pos = self.var_pos.get()
        is_rel = self.var_is_relative.get()
        
        rpm = self.var_move_rpm.get()
        if rpm > SPEED_RATED_RPM and not self.extended_speed_unlocked:
            if not self._prompt_extended_speed_acknowledgment():
                rpm = SPEED_RATED_RPM
                self.var_move_rpm.set(rpm)
        elif rpm > SPEED_MAX_RPM:
            rpm = SPEED_MAX_RPM
            self.var_move_rpm.set(rpm)

        vel_inc_s = int(round(rpm * ENCODER_COUNTS_PER_REV / 60.0))
        accel = int(self.var_accel.get())
        decel = int(self.var_decel.get())

        cw_cmd = 0x007F if is_rel else 0x003F

        for addr, mult in self._get_target_addresses():
            directed_pos = int(round(pos * mult)) if is_rel else pos
            self.app.sdo_write_slave(addr, 0x6060, 0x00, (1).to_bytes(1, 'little', signed=True))
            self.app.sdo_write_slave(addr, 0x6081, 0x00, vel_inc_s.to_bytes(4, 'little'))
            self.app.sdo_write_slave(addr, 0x6083, 0x00, accel.to_bytes(4, 'little'))
            self.app.sdo_write_slave(addr, 0x6084, 0x00, decel.to_bytes(4, 'little'))
            self.app.sdo_write_slave(addr, 0x607A, 0x00, int(directed_pos).to_bytes(4, 'little', signed=True))
            
            # Pulse setpoint
            self.app.send_controlword_slave(addr, 0x000F)
            time.sleep(0.005)
            self.app.send_controlword_slave(addr, cw_cmd)

        mode_tag = "RELATIVE" if is_rel else "ABSOLUTE"
        self.app.log(f"Multi-Axis Position Move Dispatched ({mode_tag}): Target={pos:,d} @ {rpm} RPM to {self.var_target_axis.get().upper()}")

    def _rel_move(self, delta: int):
        self._require_safety_acknowledgment(lambda: self._do_rel_move(delta))

    def _do_rel_move(self, delta: int):
        self.var_is_relative.set(True)
        self.var_pos.set(delta)
        self._do_apply_position()

    # =========================================================================
    # AUTOMATED MOTION CHOREOGRAPHY ROUTINES
    # =========================================================================

    def start_harmonic_sweep_routine(self):
        self._require_safety_acknowledgment(self._launch_harmonic_sweep)

    def _launch_harmonic_sweep(self):
        if self._routine_running:
            return

        steps = [
            (4.0, "+4.0 Revolutions Forward (CW)", 0x80080004),
            (-4.0, "-4.0 Revolutions Reverse (CCW)", 0x80080006),
            (2.0, "+2.0 Revolutions Forward (CW)", 0x80080004),
            (-2.0, "-2.0 Revolutions Reverse (CCW)", 0x80080006),
            (1.0, "+1.0 Revolution Forward (CW)", 0x80080004),
            (-1.0, "-1.0 Revolution Reverse (CCW)", 0x80080006),
            (0.5, "+0.50 Revolution Forward (CW)", 0x80080004),
            (-0.5, "-0.50 Revolution Reverse (CCW)", 0x80080006),
            (0.25, "+0.25 Revolution Forward (CW)", 0x80080004),
            (-0.25, "-0.25 Revolution Reverse (CCW)", 0x80080006),
            
            (-0.25, "-0.25 Revolution Reverse (CCW)", 0x80080006),
            (0.25, "+0.25 Revolution Forward (CW)", 0x80080004),
            (-0.5, "-0.50 Revolution Reverse (CCW)", 0x80080006),
            (0.5, "+0.50 Revolution Forward (CW)", 0x80080004),
            (-1.0, "-1.0 Revolution Reverse (CCW)", 0x80080006),
            (1.0, "+1.0 Revolution Forward (CW)", 0x80080004),
            (-2.0, "-2.0 Revolutions Reverse (CCW)", 0x80080006),
            (2.0, "+2.0 Revolutions Forward (CW)", 0x80080004),
            (-4.0, "-4.0 Revolutions Reverse (CCW)", 0x80080006),
            (4.0, "+4.0 Revolutions Forward (CW)", 0x80080004),
        ]

        self._start_routine_thread("🌀 Harmonic Reversing Sweep (4000 RPM)", steps, target_rpm=4000, accel=250000)

    def start_tachometer_ramp_routine(self):
        self._require_safety_acknowledgment(self._launch_tachometer_ramp)

    def _launch_tachometer_ramp(self):
        if self._routine_running:
            return

        def _run():
            self._routine_running = True
            self._routine_stop_event.clear()
            self._set_routine_ui_state(True, "⚡ 0→4000 RPM Tachometer Ramp", "Accelerating to 4,000 RPM...")
            
            try:
                targets = self._get_target_addresses()
                # 1. Enable Target Axes in Velocity Mode (3)
                for addr, _ in targets:
                    self.app.sdo_write_slave(addr, 0x6060, 0x00, (3).to_bytes(1, 'little', signed=True))
                    self.app.send_controlword_slave(addr, CMD_ENABLE_OPERATION)
                    self.app.sdo_write_slave(addr, 0x2FEF, 0x01, (0x800B000D).to_bytes(4, 'little'))
                
                # Ramp up
                total_steps = 40
                for i in range(total_steps + 1):
                    if self._routine_stop_event.is_set():
                        break
                    speed = (i / float(total_steps)) * 4000.0
                    for addr, mult in targets:
                        vel_inc = int(round(speed * mult * ENCODER_COUNTS_PER_REV / 60.0))
                        self.app.sdo_write_slave(addr, 0x60FF, 0x00, vel_inc.to_bytes(4, 'little', signed=True))
                    
                    prog = (i / (total_steps * 2.0)) * 100.0
                    self.var_routine_progress.set(prog)
                    self.var_routine_step.set(f"Accelerating: {int(speed)} RPM / 4,000 RPM")
                    time.sleep(0.08)

                time.sleep(1.0)

                # Ramp down
                for i in range(total_steps, -1, -1):
                    if self._routine_stop_event.is_set():
                        break
                    speed = (i / float(total_steps)) * 4000.0
                    for addr, mult in targets:
                        vel_inc = int(round(speed * mult * ENCODER_COUNTS_PER_REV / 60.0))
                        self.app.sdo_write_slave(addr, 0x60FF, 0x00, vel_inc.to_bytes(4, 'little', signed=True))
                    
                    prog = 50.0 + ((total_steps - i) / (total_steps * 2.0)) * 50.0
                    self.var_routine_progress.set(prog)
                    self.var_routine_step.set(f"Decelerating: {int(speed)} RPM / 0 RPM")
                    time.sleep(0.08)

                # Complete
                for addr, _ in targets:
                    self.app.sdo_write_slave(addr, 0x60FF, 0x00, (0).to_bytes(4, 'little', signed=True))
                    self.app.sdo_write_slave(addr, 0x2FEF, 0x01, (0x80010001).to_bytes(4, 'little'))
                
                self.var_routine_step.set("Tachometer sweep completed successfully.")
                self.app.log("Completed Tachometer Sweep Routine.")
            finally:
                self._set_routine_ui_state(False, "Routine Idle", "Ready")
                self._routine_running = False

        threading.Thread(target=_run, daemon=True).start()

    def start_turntable_routine(self):
        steps = [
            (0.25, "Indexing Station 1 (0° → 90°)", 0x80080004),
            (0.25, "Indexing Station 2 (90° → 180°)", 0x80080004),
            (0.25, "Indexing Station 3 (180° → 270°)", 0x80080004),
            (0.25, "Indexing Station 4 (270° → 360° / Home)", 0x80080002),
        ]
        self._require_safety_acknowledgment(lambda: self._start_routine_thread("🎡 4x90° Indexing Turntable (Dwell Carousel)", steps, target_rpm=1500, accel=180000, dwell_s=0.08))

    def start_pick_and_place_routine(self):
        steps = [
            (2.0, "Traverse to Pick Station (+2.0 Rev)", 0x80080007),
            (0.0, "Gripper Engage & Dwell (0.15s)", 0x800B0002),
            (-4.0, "High-Speed Gantry Transfer to Place (-4.0 Rev)", 0x80080005),
            (0.0, "Gripper Release & Place Dwell (0.15s)", 0x800B0002),
            (2.0, "Return to Home Datum (+2.0 Rev)", 0x80080003),
            
            (2.0, "Cycle 2: Traverse to Pick Station (+2.0 Rev)", 0x80080007),
            (0.0, "Cycle 2: Gripper Engage & Dwell", 0x800B0002),
            (-4.0, "Cycle 2: Transfer to Place (-4.0 Rev)", 0x80080005),
            (0.0, "Cycle 2: Gripper Release & Dwell", 0x800B0002),
            (2.0, "Cycle 2: Return to Home Datum (+2.0 Rev)", 0x80080003),
        ]
        self._require_safety_acknowledgment(lambda: self._start_routine_thread("📦 High-Speed Pick & Place Gantry", steps, target_rpm=3800, accel=240000, dwell_s=0.12))

    def start_flying_shear_routine(self):
        steps = [
            (1.0, "Cycle 1: Infeed Sync Traverse (+1.0 Rev)", 0x80080003),
            (0.5, "Cycle 1: High-Speed Flying Cut (+0.5 Rev @ 4000 RPM)", 0x80040050),
            (1.5, "Cycle 1: Outfeed Clear (+1.5 Rev)", 0x80080008),
            
            (1.0, "Cycle 2: Infeed Sync Traverse (+1.0 Rev)", 0x80080003),
            (0.5, "Cycle 2: High-Speed Flying Cut (+0.5 Rev @ 4000 RPM)", 0x80040050),
            (1.5, "Cycle 2: Outfeed Clear (+1.5 Rev)", 0x80080008),

            (1.0, "Cycle 3: Infeed Sync Traverse (+1.0 Rev)", 0x80080003),
            (0.5, "Cycle 3: High-Speed Flying Cut (+0.5 Rev @ 4000 RPM)", 0x80040050),
            (1.5, "Cycle 3: Outfeed Clear (+1.5 Rev)", 0x80080008),

            (1.0, "Cycle 4: Infeed Sync Traverse (+1.0 Rev)", 0x80080003),
            (0.5, "Cycle 4: High-Speed Flying Cut (+0.5 Rev @ 4000 RPM)", 0x80040050),
            (1.5, "Cycle 4: Outfeed Clear (+1.5 Rev)", 0x80080008),
        ]
        self._require_safety_acknowledgment(lambda: self._start_routine_thread("⚙️ Rotary Flying Knife (4000 RPM)", steps, target_rpm=4000, accel=280000, dwell_s=0.04))

    def start_micro_precision_routine(self):
        steps = [
            (0.05, "Step 1: +18.0° Micro-Increment", 0x80080004),
            (-0.05, "Step 2: -18.0° Micro-Return", 0x80080006),
            (0.02, "Step 3: +7.20° Sub-Degree Position", 0x80080008),
            (-0.02, "Step 4: -7.20° Sub-Degree Return", 0x80080008),
            (0.005, "Step 5: +1.80° Precision Vernier Step", 0x80080001),
            (-0.005, "Step 6: -1.80° Precision Vernier Return", 0x80080001),
            
            (0.01, "Stiffness Dither #1 (+3.6°)", 0x800B000D),
            (-0.01, "Stiffness Dither #1 (-3.6°)", 0x800B000D),
            (0.01, "Stiffness Dither #2 (+3.6°)", 0x800B000D),
            (-0.01, "Stiffness Dither #2 (-3.6°)", 0x800B000D),
            (0.01, "Stiffness Dither #3 (+3.6°)", 0x800B000D),
            (-0.01, "Stiffness Dither #3 (-3.6°)", 0x800B000D),
            (0.01, "Stiffness Dither #4 (+3.6°)", 0x800B000D),
            (-0.01, "Stiffness Dither #4 (-3.6°)", 0x800B000D),
        ]
        self._require_safety_acknowledgment(lambda: self._start_routine_thread("🎯 Micro-Stepping Stiffness Test", steps, target_rpm=2500, accel=300000, dwell_s=0.04))

    def start_dual_ballet_routine(self):
        steps = [
            (3.0, "Dual Mirror Phase 1: Opposing Full 3-Turn (+3 / -3 Rev)", 0x80080004),
            (-3.0, "Dual Mirror Phase 2: Opposing Reverse (-3 / +3 Rev)", 0x80080006),
            (1.5, "Dual Mirror Phase 3: Synchronized 1.5-Turn Pirouette", 0x80080008),
            (-1.5, "Dual Mirror Phase 4: Synchronized 1.5-Turn Counter", 0x80080005),
            (0.75, "Dual Mirror Phase 5: Quick Alternating Strobe (+0.75 Rev)", 0x800B000D),
            (-0.75, "Dual Mirror Phase 6: Quick Alternating Strobe (-0.75 Rev)", 0x800B000D),
            (3.0, "Grand Finale: 3-Turn High-Speed Synchrony (+3.0 Rev)", 0x80040050),
            (-3.0, "Grand Finale: 3-Turn Return to Datum (-3.0 Rev)", 0x80080001),
        ]
        self._require_safety_acknowledgment(lambda: self._start_routine_thread("🪞 Mirrored Synchronous Ballet", steps, target_rpm=3500, accel=250000, dwell_s=0.06))

    def _start_routine_thread(self, name: str, steps: List[Tuple[float, str, int]], target_rpm: int = 4000, accel: int = 200000, dwell_s: float = 0.08):
        def _worker():
            self._routine_running = True
            self._routine_stop_event.clear()
            self._set_routine_ui_state(True, name, "Initializing target axes...")
            
            try:
                targets = self._get_target_addresses()
                vel_inc_s = int(round(target_rpm * ENCODER_COUNTS_PER_REV / 60.0))
                for addr, _ in targets:
                    self.app.sdo_write_slave(addr, 0x6060, 0x00, (1).to_bytes(1, 'little', signed=True))
                    self.app.sdo_write_slave(addr, 0x6081, 0x00, vel_inc_s.to_bytes(4, 'little'))
                    self.app.sdo_write_slave(addr, 0x6083, 0x00, accel.to_bytes(4, 'little'))
                    self.app.sdo_write_slave(addr, 0x6084, 0x00, accel.to_bytes(4, 'little'))
                    self.app.send_controlword_slave(addr, CMD_ENABLE_OPERATION)
                time.sleep(0.04)

                total_steps = len(steps)
                for idx, (rev_delta, label, led_dword) in enumerate(steps, start=1):
                    if self._routine_stop_event.is_set():
                        break

                    prog = (idx / float(total_steps)) * 100.0
                    self.var_routine_progress.set(prog)
                    self.var_routine_step.set(f"Step {idx}/{total_steps}: {label} @ {target_rpm} RPM")
                    self.app.log(f"[{name}] Step {idx}/{total_steps}: {label}")

                    for addr, mult in targets:
                        if led_dword:
                            self.app.sdo_write_slave(addr, 0x2FEF, 0x01, led_dword.to_bytes(4, 'little'))
                        
                        inc_delta = int(round(rev_delta * mult * ENCODER_COUNTS_PER_REV))
                        self.app.sdo_write_slave(addr, 0x607A, 0x00, inc_delta.to_bytes(4, 'little', signed=True))
                        self.app.send_controlword_slave(addr, 0x000F)
                        time.sleep(0.005)
                        self.app.send_controlword_slave(addr, 0x007F)

                    move_time_s = (abs(rev_delta) / (target_rpm / 60.0)) + 0.12
                    deadline = time.time() + move_time_s
                    while time.time() < deadline:
                        if self._routine_stop_event.is_set():
                            break
                        time.sleep(0.02)

                    if dwell_s > 0:
                        time.sleep(dwell_s)

                for addr, _ in targets:
                    self.app.send_controlword_slave(addr, CMD_ENABLE_OPERATION)
                    self.app.sdo_write_slave(addr, 0x2FEF, 0x01, (0x80010001).to_bytes(4, 'little'))

                self.var_routine_step.set("Choreographed routine completed cleanly.")
                self.app.log(f"Routine '{name}' completed successfully.")
            finally:
                self._set_routine_ui_state(False, "Routine Idle", "Ready")
                self._routine_running = False

        threading.Thread(target=_worker, daemon=True).start()

    def stop_current_routine(self):
        if self._routine_running:
            self._routine_stop_event.set()
            self.app.action_quick_stop()
            self.var_routine_step.set("ROUTINE ABORTED BY OPERATOR (Quick Stop 0x0002).")
            self.app.log("Operator aborted running choreography routine.")

    def _set_routine_ui_state(self, running: bool, title: str, status: str):
        self.var_routine_name.set(title)
        self.var_routine_step.set(status)
        if running:
            self.btn_abort_routine.config(state="normal", bg=COLOR_DANGER, fg=COLOR_TEXT_PRIMARY)
        else:
            self.btn_abort_routine.config(state="disabled", bg="#4A141A", fg=COLOR_TEXT_MUTED)

    def update_multi_telemetry(self, t_dict: Dict[int, MotorTelemetry]):
        t1 = t_dict.get(0x1000)
        t2 = t_dict.get(0x1001)

        if t1:
            color1 = COLOR_MURR_LIME if t1.cia_state == Cia402State.OPERATION_ENABLED else COLOR_WARNING
            if t1.cia_state == Cia402State.FAULT: color1 = COLOR_DANGER
            self.lbl_m1_state.config(text=f"M1 (0x1000): {t1.cia_state.value.upper()} (0x{t1.statusword:04X})", fg=color1)

        if t2:
            color2 = COLOR_MURR_LIME if t2.cia_state == Cia402State.OPERATION_ENABLED else COLOR_WARNING
            if t2.cia_state == Cia402State.FAULT: color2 = COLOR_DANGER
            self.lbl_m2_state.config(text=f"M2 (0x1001): {t2.cia_state.value.upper()} (0x{t2.statusword:04X})", fg=color2)

    def update_telemetry(self, t: MotorTelemetry):
        self.update_multi_telemetry({0x1000: t, 0x1001: t})
