"""
CiA 402 Motion & Drive Control Tab.
Full multi-mode motion engine for Profile Velocity (PV) and Profile Position (PP).
Includes dedicated Setpoint Move Velocity controls, 4000 RPM rated limit enforcement,
and Section 5.3 reduced-torque Extended Speed (6000 RPM) safety acknowledgment.
"""

import time
import math
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
    FONT_BODY, FONT_BODY_BOLD, FONT_MONO, FONT_MONO_BOLD, FONT_BADGE
)

# Section 5.3 Performance Boundaries
SPEED_RATED_RPM = 4000
SPEED_MAX_RPM = 6000

class MotionTab(tk.Frame):
    """CiA 402 Motion Control, mode selection, jog, and coordinated setpoints."""

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COLOR_BG_SURFACE, padx=16, pady=16, **kwargs)
        self.app = app
        self.extended_speed_unlocked = False

        # Motion Parameters
        self.var_mode = tk.StringVar(value=MODE_NAMES[3])
        self.var_speed_rpm = tk.DoubleVar(value=0.0)
        self.var_pos = tk.IntVar(value=0)
        
        # Kinematic Limits
        self.var_move_rpm = tk.IntVar(value=1000)          # 0x6081 Profile Move Velocity (RPM)
        self.var_accel = tk.IntVar(value=150000)           # 0x6083 Profile Accel (inc/s²)
        self.var_decel = tk.IntVar(value=150000)           # 0x6084 Profile Decel (inc/s²)
        self.var_is_relative = tk.BooleanVar(value=False)  # Bit 6 in 0x6040

        # Layout: 2 Columns
        content = tk.Frame(self, bg=COLOR_BG_SURFACE)
        content.pack(fill="both", expand=True)

        col_left = tk.Frame(content, bg=COLOR_BG_SURFACE, width=470)
        col_left.pack(side="left", fill="both", expand=True, padx=(0, 16))
        self._build_cia_panel(col_left)

        col_right = tk.Frame(content, bg=COLOR_BG_SURFACE, width=470)
        col_right.pack(side="left", fill="both", expand=True)
        self._build_motion_panel(col_right)

    def _build_cia_panel(self, parent):
        # 1. State Machine Card
        card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=16, pady=14)
        card.pack(fill="x", pady=(0, 14))

        tk.Label(card, text="CiA 402 DRIVE STATE MACHINE", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_TITLE).pack(anchor="w")
        
        # State Readout
        state_box = tk.Frame(card, bg=COLOR_BG_INPUT, padx=12, pady=8)
        state_box.pack(fill="x", pady=(8, 12))

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
        ttk.Button(seq_grid, text="3. Enable Op (0x000F)", style="Murr.TButton", command=self._full_enable_drive).grid(row=1, column=0, columnspan=2, sticky="ew", padx=2, pady=3)
        
        seq_grid.columnconfigure(0, weight=1)
        seq_grid.columnconfigure(1, weight=1)

        # Interlocks & Emergency Actions
        tk.Label(card, text="Interlocks & Recovery:", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_SUBTITLE).pack(anchor="w", pady=(10, 6))

        rec_grid = tk.Frame(card, bg=COLOR_BG_CARD)
        rec_grid.pack(fill="x")

        ttk.Button(rec_grid, text="Quick Stop (0x0002)", style="Danger.TButton", command=lambda: self.app.send_controlword(CMD_QUICK_STOP)).grid(row=0, column=0, sticky="ew", padx=2, pady=3)
        ttk.Button(rec_grid, text="Disable Voltage (0x0000)", style="Action.TButton", command=lambda: self.app.send_controlword(CMD_DISABLE_VOLTAGE)).grid(row=0, column=1, sticky="ew", padx=2, pady=3)
        ttk.Button(rec_grid, text="Fault Reset (0x0080)", style="Action.TButton", command=lambda: self.app.send_controlword(CMD_FAULT_RESET)).grid(row=1, column=0, columnspan=2, sticky="ew", padx=2, pady=3)

        rec_grid.columnconfigure(0, weight=1)
        rec_grid.columnconfigure(1, weight=1)

        # 2. Acceleration / Deceleration Trajectory Profile Card
        kin_card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=16, pady=14)
        kin_card.pack(fill="both", expand=True)

        tk.Label(kin_card, text="TRAJECTORY ACCELERATION LIMITS", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_TITLE).pack(anchor="w")
        tk.Label(kin_card, text="Applied to both Velocity and Position modes", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_SUBTITLE).pack(anchor="w", pady=(0, 8))

        # Profile Acceleration
        row_a = tk.Frame(kin_card, bg=COLOR_BG_CARD)
        row_a.pack(fill="x", pady=4)
        tk.Label(row_a, text="Profile Acceleration (0x6083):", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_BODY_BOLD).pack(side="left")
        tk.Label(row_a, text="inc/s²", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_BADGE).pack(side="right")
        ttk.Entry(row_a, textvariable=self.var_accel, width=9, font=FONT_MONO_BOLD).pack(side="right", padx=6)

        # Profile Deceleration
        row_d = tk.Frame(kin_card, bg=COLOR_BG_CARD)
        row_d.pack(fill="x", pady=4)
        tk.Label(row_d, text="Profile Deceleration (0x6084):", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_BODY_BOLD).pack(side="left")
        tk.Label(row_d, text="inc/s²", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_BADGE).pack(side="right")
        ttk.Entry(row_d, textvariable=self.var_decel, width=9, font=FONT_MONO_BOLD).pack(side="right", padx=6)

        # Motor Specification Box (Section 5.3)
        spec_box = tk.LabelFrame(kin_card, text=" Motor Performance (Section 5.3) ", bg=COLOR_BG_CARD, fg="#38BDF8", font=FONT_BODY_BOLD, padx=10, pady=8)
        spec_box.pack(fill="x", pady=(10, 0))

        tk.Label(spec_box, text="• Rated Speed: 4,000 RPM (0.8 Nm S1 Rated Torque)", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_BODY).pack(anchor="w")
        tk.Label(spec_box, text="• Max Speed: 6,000 RPM (Reduced Torque / Field Weakening)", bg=COLOR_BG_CARD, fg=COLOR_WARNING, font=FONT_BODY).pack(anchor="w")
        tk.Label(spec_box, text="• Peak Torque: 3.0 Nm | Rated Power: 420 W", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_BADGE).pack(anchor="w", pady=(2, 0))

    def _build_motion_panel(self, parent):
        # 1. Velocity / Jog Control Card
        vel_card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=16, pady=14)
        vel_card.pack(fill="x", pady=(0, 14))

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
        self.slider_vel.pack(fill="x", pady=(6, 4))

        # Speed Presets
        presets_frame = tk.Frame(vel_card, bg=COLOR_BG_CARD)
        presets_frame.pack(fill="x", pady=3)

        for rpm in [0, 250, 500, 1000, 2000, 4000]:
            ttk.Button(presets_frame, text=f"{rpm}", style="Action.TButton", command=lambda r=rpm: self._set_speed(float(r))).pack(side="left", fill="x", expand=True, padx=2)
        
        # 6000 RPM Extended preset button
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
        pos_card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=16, pady=14)
        pos_card.pack(fill="both", expand=True)

        tk.Label(pos_card, text="POSITION SETPOINT COMMAND (0x607A)", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_TITLE).pack(anchor="w")
        tk.Label(pos_card, text="Coordinates in Encoder Counts (65,536 inc = 1 Revolution)", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_SUBTITLE).pack(anchor="w", pady=(0, 6))

        # Dedicated Setpoint Move Speed Control (0x6081)
        speed_box = tk.LabelFrame(pos_card, text=" Setpoint Move Speed (Profile Velocity 0x6081) ", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_BODY_BOLD, padx=8, pady=6)
        speed_box.pack(fill="x", pady=(0, 8))

        s_row = tk.Frame(speed_box, bg=COLOR_BG_CARD)
        s_row.pack(fill="x", pady=2)
        tk.Label(s_row, text="Target Move Velocity:", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_BODY_BOLD).pack(side="left")
        tk.Label(s_row, text="RPM", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_BADGE).pack(side="right")
        self.entry_move_rpm = ttk.Entry(s_row, textvariable=self.var_move_rpm, font=FONT_MONO_BOLD, width=8)
        self.entry_move_rpm.pack(side="right", padx=6)

        # Move Speed Quick Presets
        s_presets = tk.Frame(speed_box, bg=COLOR_BG_CARD)
        s_presets.pack(fill="x", pady=(4, 2))
        for pr_rpm in [250, 500, 1000, 2000, 4000]:
            ttk.Button(s_presets, text=f"{pr_rpm} RPM", style="Action.TButton", command=lambda r=pr_rpm: self._set_move_speed(r)).pack(side="left", fill="x", expand=True, padx=2)
        
        self.btn_6k_move = tk.Button(
            s_presets, text="6000 RPM*", bg=COLOR_BG_INPUT, fg=COLOR_WARNING,
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

    def _prompt_extended_speed_acknowledgment(self) -> bool:
        """Prompts user to acknowledge Section 5.3 reduced-torque operation for speeds > 4000 RPM."""
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
            # Expand slider range to ±6000
            self.slider_vel.config(from_=-SPEED_MAX_RPM, to=SPEED_MAX_RPM)
            self.lbl_vel_mode_badge.config(text="EXTENDED UNLOCKED (≤6000 RPM)", bg="#4A2A0A", fg=COLOR_WARNING)
            self.app.log("User acknowledged Section 5.3: Extended 6,000 RPM operation enabled.")
            return True
        return False

    def _set_move_speed(self, rpm: int):
        """Sets move speed with 4000/6000 RPM validation."""
        if rpm > SPEED_RATED_RPM:
            if not self._prompt_extended_speed_acknowledgment():
                rpm = SPEED_RATED_RPM
        self.var_move_rpm.set(rpm)
        self.app.log(f"Configured Setpoint Move Speed: {rpm} RPM")

    def _full_enable_drive(self):
        """Standard Drive Enable sequence with mode and trajectory limits initialized."""
        # 1. Switch Mode to Profile Velocity (3)
        self.app.sdo_write(0x6060, 0x00, (3).to_bytes(1, 'little', signed=True))
        
        # 2. Write Profile Accel and Decel
        self._flash_kinematics()

        # 3. CiA 402 Enable Sequence: 0x06 -> 0x07 -> 0x0F
        self.app.send_controlword(CMD_SHUTDOWN)
        self.after(40, lambda: self.app.send_controlword(CMD_SWITCH_ON))
        self.after(80, lambda: self.app.send_controlword(CMD_ENABLE_OPERATION))
        self.app.log("Full Drive Enable initiated (Mode 3, Accel/Decel loaded, Controlword 0x000F).")

    def _flash_kinematics(self):
        """Flashing 0x6081 (Profile Velocity), 0x6083 (Accel), 0x6084 (Decel)."""
        rpm = self.var_move_rpm.get()
        if rpm > SPEED_RATED_RPM and not self.extended_speed_unlocked:
            rpm = SPEED_RATED_RPM
            self.var_move_rpm.set(rpm)

        vel_inc_s = int(round(rpm * 65536.0 / 60.0))
        accel = int(self.var_accel.get())
        decel = int(self.var_decel.get())

        self.app.sdo_write(0x6081, 0x00, vel_inc_s.to_bytes(4, 'little'))
        self.app.sdo_write(0x6083, 0x00, accel.to_bytes(4, 'little'))
        self.app.sdo_write(0x6084, 0x00, decel.to_bytes(4, 'little'))
        self.app.log(f"Configured Motion Trajectory: Profile Vel={rpm} RPM ({vel_inc_s} inc/s), Acc={accel}, Dec={decel}")

    def _on_slider_speed(self, val: float):
        if abs(val) > SPEED_RATED_RPM and not self.extended_speed_unlocked:
            if not self._prompt_extended_speed_acknowledgment():
                clamped = math.copysign(SPEED_RATED_RPM, val)
                self.var_speed_rpm.set(clamped)
                val = clamped
        self._send_speed(val)

    def _set_speed(self, val: float):
        if abs(val) > SPEED_RATED_RPM and not self.extended_speed_unlocked:
            if not self._prompt_extended_speed_acknowledgment():
                val = math.copysign(SPEED_RATED_RPM, val)
        self.var_speed_rpm.set(val)
        self._send_speed(val)

    def _send_speed(self, val: float):
        """Commands Target Velocity (0x60FF) bundled with Mode 3 and Accel/Decel limits."""
        # Check hard cap at 6000 RPM
        if abs(val) > SPEED_MAX_RPM:
            val = math.copysign(SPEED_MAX_RPM, val)
            self.var_speed_rpm.set(val)

        # 1. Ensure Mode is Profile Velocity (Mode 3)
        self.app.sdo_write(0x6060, 0x00, (3).to_bytes(1, 'little', signed=True))
        
        # 2. Convert RPM to increments/second (65536 inc = 1 rev)
        vel_inc_s = int(round(val * 65536.0 / 60.0))
        
        # 3. Write Profile Limits
        accel = int(self.var_accel.get())
        decel = int(self.var_decel.get())
        self.app.sdo_write(0x6083, 0x00, accel.to_bytes(4, 'little'))
        self.app.sdo_write(0x6084, 0x00, decel.to_bytes(4, 'little'))

        # 4. Write Target Velocity
        self.app.sdo_write(0x60FF, 0x00, vel_inc_s.to_bytes(4, 'little', signed=True))
        
        # 5. Ensure Controlword is Operation Enabled
        self.app.send_controlword(CMD_ENABLE_OPERATION)
        self.app.log(f"Commanded Velocity: {val:.1f} RPM ({vel_inc_s} inc/s)")

    def _apply_position(self):
        """Commands Target Position (0x607A) bundled with Mode 1, Velocity, Accel, Decel, and Setpoint Pulse."""
        pos = self.var_pos.get()
        is_rel = self.var_is_relative.get()
        
        # Check Move Speed with 4000/6000 RPM permission
        rpm = self.var_move_rpm.get()
        if rpm > SPEED_RATED_RPM and not self.extended_speed_unlocked:
            if not self._prompt_extended_speed_acknowledgment():
                rpm = SPEED_RATED_RPM
                self.var_move_rpm.set(rpm)
        elif rpm > SPEED_MAX_RPM:
            rpm = SPEED_MAX_RPM
            self.var_move_rpm.set(rpm)

        # 1. Switch to Profile Position Mode (Mode 1)
        self.app.sdo_write(0x6060, 0x00, (1).to_bytes(1, 'little', signed=True))

        # 2. Write Profile Velocity (0x6081), Accel (0x6083), Decel (0x6084)
        vel_inc_s = int(round(rpm * 65536.0 / 60.0))
        accel = int(self.var_accel.get())
        decel = int(self.var_decel.get())

        self.app.sdo_write(0x6081, 0x00, vel_inc_s.to_bytes(4, 'little'))
        self.app.sdo_write(0x6083, 0x00, accel.to_bytes(4, 'little'))
        self.app.sdo_write(0x6084, 0x00, decel.to_bytes(4, 'little'))

        # 3. Write Target Position (0x607A)
        self.app.sdo_write(0x607A, 0x00, int(pos).to_bytes(4, 'little', signed=True))

        # 4. Trigger Setpoint Pulse (0x000F -> 0x003F for Immediate Absolute, or 0x007F for Immediate Relative)
        cw_cmd = 0x007F if is_rel else 0x003F
        self.app.send_controlword(0x000F) # Clear bit 4
        self.after(30, lambda: self.app.send_controlword(cw_cmd)) # Rising edge on bit 4
        
        mode_tag = "RELATIVE" if is_rel else "ABSOLUTE"
        self.app.log(f"Position Move Triggered ({mode_tag}): Target={pos:,d} counts @ {rpm} RPM ({vel_inc_s} inc/s)")

    def _rel_move(self, delta: int):
        """Relative step increment."""
        self.var_is_relative.set(True)
        self.var_pos.set(delta)
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
