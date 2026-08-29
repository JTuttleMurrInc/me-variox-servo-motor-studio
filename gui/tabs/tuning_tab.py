"""
Servo Loop Tuning & Kinematics Studio Tab.
Covers Section 8.2.1 (Speed Controller & Filters) and Section 8.2.2 (Position Control Loop & Notch Filter).
Provides interactive PID/Feedforward parameterization, anti-resonant notch filter tuning,
smoothing filter synthesis, and one-click SDO batch flashing.
"""

import time
import math
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Optional, Tuple, Any

from gui.theme import (
    COLOR_BG_SURFACE, COLOR_BG_CARD, COLOR_BG_INPUT, COLOR_BG_ACCENT,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_MUTED, COLOR_MURR_LIME, COLOR_MURR_GREEN,
    COLOR_WARNING, COLOR_DANGER, FONT_TITLE, FONT_SECTION, FONT_SUBTITLE,
    FONT_BODY, FONT_BODY_BOLD, FONT_MONO, FONT_MONO_BOLD, FONT_BADGE
)

# Speed Feedback Filter Modes from Manual Section 8.2.1
FILTER_MODES = [
    (0, "Mode 0: 2nd-Order Low-Pass Filter (LPF)"),
    (1, "Mode 1: Direct Feedback (Original Speed)"),
    (2, "Mode 2: Speed Feedback from Encoder"),
    (4, "Mode 4: 1st-Order Low-Pass Filter (LPF)"),
    (10, "Mode 10: 2nd-Order FB LPF + 1st-Order Setpoint LPF"),
    (11, "Mode 11: Setpoint 1st-Order LPF Only"),
    (12, "Mode 12: Encoder FB + Setpoint 1st-Order LPF"),
    (14, "Mode 14: Dual 1st-Order LPFs (FB & Setpoint)")
]

class TuningCurveCanvas(tk.Canvas):
    """Real-Time Interactive Velocity Ramp, Position Response, & Notch Filter Bode Canvas."""

    def __init__(self, parent, height: int = 150, **kwargs):
        super().__init__(parent, height=height, bg=COLOR_BG_INPUT, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, **kwargs)
        self.bind("<Configure>", lambda e: self.redraw())
        self.accel = 107372
        self.decel = 107372
        self.bw_hz = 58
        self.filter_hz = 240
        self.notch_hz = 550
        self.notch_enabled = True
        self.pos_bw_hz = 10.0
        self.v_ff = 100.0
        self.redraw()

    def set_params(self, accel: int, decel: int, bw_hz: int, filter_hz: int, notch_hz: int, notch_on: bool, kpp: int, v_ff: int):
        self.accel = max(1000, accel)
        self.decel = max(1000, decel)
        self.bw_hz = max(1, bw_hz)
        self.filter_hz = max(10, filter_hz)
        self.notch_hz = max(100, notch_hz)
        self.notch_enabled = notch_on
        self.pos_bw_hz = kpp / 100.0
        self.v_ff = v_ff / 10.0
        self.redraw()

    def redraw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 50 or h < 50:
            return

        pad_x = 35
        pad_y = 20
        plot_w = w - 2 * pad_x
        plot_h = h - 2 * pad_y
        mid_y = pad_y + plot_h

        # Grid lines
        for i in range(5):
            gx = pad_x + (i * plot_w / 4)
            self.create_line(gx, pad_y, gx, pad_y + plot_h, fill="#0B2B26", dash=(2, 2))
            gy = pad_y + (i * plot_h / 4)
            self.create_line(pad_x, gy, pad_x + plot_w, gy, fill="#0B2B26", dash=(2, 2))

        # 1. Kinematic Velocity Ramp (Lime Green)
        t_acc_frac = max(0.1, min(0.4, 30000.0 / math.sqrt(self.accel)))
        t_dec_frac = max(0.1, min(0.4, 30000.0 / math.sqrt(self.decel)))
        t_cruise_frac = max(0.1, 1.0 - t_acc_frac - t_dec_frac)

        pts = [
            (pad_x, mid_y),
            (pad_x + plot_w * (t_acc_frac * 0.4), mid_y - plot_h * 0.2),
            (pad_x + plot_w * t_acc_frac, pad_y + 10),
            (pad_x + plot_w * (t_acc_frac + t_cruise_frac), pad_y + 10),
            (pad_x + plot_w * (t_acc_frac + t_cruise_frac + t_dec_frac * 0.6), mid_y - plot_h * 0.2),
            (pad_x + plot_w, mid_y)
        ]
        flat_pts = [c for pt in pts for c in pt]
        self.create_line(flat_pts, fill=COLOR_MURR_LIME, width=3, smooth=True, tags="ramp")
        
        # 2. Filter Frequency Magnitude Response with Notch Dip (Cyan)
        f_pts = []
        for i in range(45):
            fx = pad_x + (i / 44.0) * plot_w
            freq = 10.0 + (i / 44.0) * 1000.0 # 10 Hz to 1000 Hz
            # Low pass roll-off at filter_hz
            ratio = freq / float(self.filter_hz)
            gain = 1.0 / math.sqrt(1.0 + (ratio ** 4))
            
            # Anti-resonant Notch filter attenuation dip
            if self.notch_enabled:
                df = abs(freq - self.notch_hz) / 35.0
                notch_attenuation = 1.0 - (0.75 / (1.0 + (df ** 2)))
                gain *= notch_attenuation

            fy = pad_y + plot_h * (1.0 - gain * 0.85) - 4
            f_pts.extend([fx, fy])
        self.create_line(f_pts, fill="#38BDF8", width=2, dash=(3, 2), smooth=True)

        # Axis Legends & Badges
        self.create_text(pad_x + 6, pad_y + 12, text=f"Target Speed ({self.bw_hz} Hz Vc / {self.pos_bw_hz:.1f} Hz Pc)", fill=COLOR_MURR_LIME, font=FONT_BADGE, anchor="w")
        notch_str = f"Notch {self.notch_hz} Hz (ON)" if self.notch_enabled else "Notch (OFF)"
        self.create_text(w - pad_x - 6, pad_y + 12, text=f"FB Filter ({self.filter_hz} Hz) | {notch_str}", fill="#38BDF8", font=FONT_BADGE, anchor="e")
        self.create_text(pad_x, h - 6, text="Time 0.0s / 10 Hz", fill=COLOR_TEXT_MUTED, font=FONT_BADGE, anchor="w")
        self.create_text(w - pad_x, h - 6, text="Kinematic Profile & Bode Spectrum", fill=COLOR_TEXT_MUTED, font=FONT_BADGE, anchor="e")

class TuningTab(tk.Frame):
    """Servo Speed, Position Loop & Anti-Resonance Tuning Studio Tab."""

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COLOR_BG_SURFACE, padx=16, pady=16, **kwargs)
        self.app = app

        # Section 8.2.1 Speed Loop Variables
        self.var_bw_hz = tk.IntVar(value=58)          # 0x2FF0:0A (1..700 Hz)
        self.var_kvp = tk.IntVar(value=14)            # 0x60F9:01 (1..32767)
        self.var_kvi = tk.IntVar(value=0)             # 0x60F9:02 (0..1023)
        self.var_kvi32 = tk.IntVar(value=10)          # 0x60F9:07 (0..32767)
        self.var_fb_mode = tk.IntVar(value=0)         # 0x60F9:06 (0..14)
        self.var_fb_n = tk.IntVar(value=7)            # 0x60F9:05 (0..45 -> 100+N*20 Hz)
        self.var_out_filter_n = tk.IntVar(value=1)    # 0x60F9:15 (1..127)
        self.var_kvi_limit = tk.IntVar(value=262144)  # 0x60F9:08

        # Section 8.2.2 Position Loop & Feedforward Variables
        self.var_kpp = tk.IntVar(value=1000)          # 0x60FB:01 (0.01 Hz -> 1000 = 10.00 Hz)
        self.var_v_ff = tk.IntVar(value=1000)         # 0x2FF0:1A (permille 1000 = 100.0%)
        self.var_acc_ff = tk.IntVar(value=0)          # 0x2FF0:1B (permille)
        self.var_pos_filter_n = tk.IntVar(value=1)    # 0x60FB:05 (1..255 ms smoothing)
        self.var_max_follow_err = tk.IntVar(value=5242) # 0x2FF0:0E (*100 = 524,200 counts)

        # Section 8.2.2 Anti-Resonant Notch Filter Variables
        self.var_notch_n = tk.IntVar(value=45)        # 0x60F9:03 (0..90 -> F = N*10 + 100 Hz = 550 Hz)
        self.var_notch_on = tk.BooleanVar(value=True) # 0x60F9:04 (0 = ON, 1 = OFF)

        # Section 8.2.1 Motion Profile Kinematics
        self.var_accel = tk.IntVar(value=107372)      # 0x6083:00
        self.var_decel = tk.IntVar(value=107372)      # 0x6084:00
        self.var_quick_decel = tk.IntVar(value=654980)# 0x6085:00

        # Layout: 3 Columns Top, Full-Width Curve Canvas Bottom
        top_row = tk.Frame(self, bg=COLOR_BG_SURFACE)
        top_row.pack(fill="both", expand=True)

        # Col 1: Speed Controller (8.2.1)
        col1 = tk.Frame(top_row, bg=COLOR_BG_SURFACE)
        col1.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self._build_speed_loop_panel(col1)

        # Col 2: Position Loop & Notch Filter (8.2.2)
        col2 = tk.Frame(top_row, bg=COLOR_BG_SURFACE)
        col2.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self._build_position_loop_panel(col2)

        # Col 3: Presets & SDO Actions
        col3 = tk.Frame(top_row, bg=COLOR_BG_SURFACE, width=280)
        col3.pack(side="left", fill="both", padx=(0, 0))
        self._build_actions_panel(col3)

        # Bottom Row: Real-Time Dynamic Response Curve
        bottom_box = tk.Frame(self, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=12, pady=10)
        bottom_box.pack(fill="x", pady=(10, 0))

        tk.Label(bottom_box, text="LIVE KINEMATIC TRAJECTORY, POSITION RESPONSE & NOTCH BODE SPECTRUM", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_SECTION).pack(anchor="w", pady=(0, 4))
        self.curve_canvas = TuningCurveCanvas(bottom_box, height=135)
        self.curve_canvas.pack(fill="x", expand=True)

        self._update_curve()

    def _build_speed_loop_panel(self, parent):
        card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=14, pady=12)
        card.pack(fill="both", expand=True)

        tk.Label(card, text="SPEED CONTROLLER & FILTERS (8.2.1)", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_TITLE).pack(anchor="w")
        tk.Label(card, text="Objects 0x60F9 & 0x2FF0 PID Gains & Filters", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_SUBTITLE).pack(anchor="w", pady=(0, 6))

        # 1. Bandwidth (0x2FF0:0A)
        self._create_slider_row(card, "Speed Bandwidth (Velocity_BW):", self.var_bw_hz, 1, 300, "Hz", obj_tag="0x2FF0:0A")
        
        # 2. Proportional Gain Kvp[0] (0x60F9:01)
        self._create_slider_row(card, "Speed Proportional Gain (Kvp[0]):", self.var_kvp, 1, 100, "", obj_tag="0x60F9:01")

        # 3. Integral Gain Kvi/32 (0x60F9:07)
        self._create_slider_row(card, "Speed Integral Fine Gain (Kvi/32):", self.var_kvi32, 0, 200, "", obj_tag="0x60F9:07")

        # 4. Feedback Filter Mode (0x60F9:06)
        mode_box = tk.Frame(card, bg=COLOR_BG_CARD)
        mode_box.pack(fill="x", pady=2)
        tk.Label(mode_box, text="Feedback Filter Structure (0x60F9:06):", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_BODY_BOLD).pack(anchor="w")
        
        combo_vals = [m[1] for m in FILTER_MODES]
        self.combo_fb_mode = ttk.Combobox(mode_box, values=combo_vals, state="readonly", font=FONT_BODY)
        self.combo_fb_mode.current(0)
        self.combo_fb_mode.pack(fill="x", pady=(2, 0))
        self.combo_fb_mode.bind("<<ComboboxSelected>>", self._on_mode_change)

        # 5. Feedback Filter Bandwidth Speed_Fb_N (0x60F9:05)
        self._create_slider_row(card, "Feedback Filter N (Speed_Fb_N):", self.var_fb_n, 0, 45, "", obj_tag="0x60F9:05",
                                desc_calc=lambda n: f"Cutoff: {100 + n*20} Hz")

        # 6. Torque Output Filter (0x60F9:15)
        self._create_slider_row(card, "Torque Low-Pass Filter (Output_Filter_N):", self.var_out_filter_n, 1, 64, "", obj_tag="0x60F9:15")

    def _build_position_loop_panel(self, parent):
        card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=14, pady=12)
        card.pack(fill="both", expand=True)

        tk.Label(card, text="POSITION CONTROL & NOTCH (8.2.2)", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_TITLE).pack(anchor="w")
        tk.Label(card, text="Objects 0x60FB & 0x2FF0 Feedforward & Anti-Resonance", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_SUBTITLE).pack(anchor="w", pady=(0, 6))

        # 1. Position Proportional Gain Kpp[0] (0x60FB:01)
        self._create_slider_row(card, "Position Gain Kpp (0.01 Hz):", self.var_kpp, 100, 3000, "", obj_tag="0x60FB:01",
                                desc_calc=lambda v: f"BW: {v/100.0:.1f} Hz")

        # 2. Velocity Feedforward K_Velocity_FF (0x2FF0:1A)
        self._create_slider_row(card, "Velocity Feedforward (K_Velocity_FF):", self.var_v_ff, 0, 2000, "‰", obj_tag="0x2FF0:1A",
                                desc_calc=lambda v: f"{v/10.0:.1f}%")

        # 3. Position Smoothing Filter Pos_Filter_N (0x60FB:05)
        self._create_slider_row(card, "Position Smoothing Filter (Pos_Filter_N):", self.var_pos_filter_n, 1, 50, "ms", obj_tag="0x60FB:05")

        # 4. Anti-Resonant Notch Filter Group
        notch_box = tk.LabelFrame(card, text=" Anti-Resonance Notch Filter (0x60F9:03/04) ", bg=COLOR_BG_CARD, fg="#38BDF8", font=FONT_BODY_BOLD, padx=8, pady=6)
        notch_box.pack(fill="x", pady=(4, 0))

        chk_row = tk.Frame(notch_box, bg=COLOR_BG_CARD)
        chk_row.pack(fill="x")
        chk = tk.Checkbutton(chk_row, text="Enable Notch Filter (0x60F9:04)", variable=self.var_notch_on,
                             bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, activebackground=COLOR_BG_CARD,
                             activeforeground=COLOR_MURR_LIME, selectcolor=COLOR_BG_INPUT, font=FONT_BODY_BOLD, command=self._update_curve)
        chk.pack(side="left")

        self._create_slider_row(notch_box, "Notch Frequency N (Notch_N):", self.var_notch_n, 0, 90, "", obj_tag="0x60F9:03",
                                desc_calc=lambda n: f"{n*10 + 100} Hz Center")

    def _build_actions_panel(self, parent):
        card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=14, pady=12)
        card.pack(fill="both", expand=True)

        tk.Label(card, text="TUNING PRESETS & SDO", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_TITLE).pack(anchor="w")
        tk.Label(card, text="Batch Parameter Sets", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_SUBTITLE).pack(anchor="w", pady=(0, 6))

        presets = [
            ("🏭 Factory Default", self.apply_preset_default, "Standard 58 Hz BW, Kpp=1000, Notch=550Hz"),
            ("⚡ High-Speed / Rigid", self.apply_preset_rigid, "120 Hz BW, Kpp=2000, 100% V-FF"),
            ("🏋️ Heavy Load / Elastic", self.apply_preset_heavy, "35 Hz BW, Kpp=600, Pos_Filter=8ms"),
            ("🔇 Low-Noise / Anti-Resonance", self.apply_preset_quiet, "Notch=450Hz Active, N=8 Filter")
        ]

        for title, cmd, desc in presets:
            p_btn = tk.Button(card, text=title, bg=COLOR_BG_INPUT, fg=COLOR_TEXT_PRIMARY, activebackground=COLOR_BG_ACCENT,
                              activeforeground=COLOR_TEXT_PRIMARY, font=FONT_BODY_BOLD, anchor="w", padx=10, pady=5,
                              relief="flat", highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, command=cmd)
            p_btn.pack(fill="x", pady=2)
            tk.Label(card, text=f"   {desc}", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_BADGE).pack(anchor="w", pady=(0, 3))

        tk.Frame(card, height=1, bg=COLOR_BG_ACCENT).pack(fill="x", pady=8)

        # Batch SDO Actions
        btn_apply = ttk.Button(card, text="🚀 Apply Tuning to Motor", style="Action.TButton", command=self.write_tuning_to_motor)
        btn_apply.pack(fill="x", pady=3)

        btn_read = ttk.Button(card, text="📥 Read Active from Motor", style="Action.TButton", command=self.read_tuning_from_motor)
        btn_read.pack(fill="x", pady=3)

    def _create_slider_row(self, parent, label_text: str, var: tk.IntVar, min_v: int, max_v: int, unit_str: str = "",
                           obj_tag: str = "", desc_calc: Optional[Any] = None):
        box = tk.Frame(parent, bg=COLOR_BG_CARD)
        box.pack(fill="x", pady=2)

        hdr = tk.Frame(box, bg=COLOR_BG_CARD)
        hdr.pack(fill="x")

        tk.Label(hdr, text=label_text, bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_BODY_BOLD).pack(side="left")
        if obj_tag:
            tk.Label(hdr, text=f" [{obj_tag}]", bg=COLOR_BG_CARD, fg="#38BDF8", font=FONT_BADGE).pack(side="left")

        extra_init = f" ({desc_calc(var.get())})" if desc_calc else ""
        val_lbl = tk.Label(hdr, text=f"{var.get()} {unit_str}{extra_init}", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_BODY_BOLD)
        val_lbl.pack(side="right")

        def on_slide(val_s):
            v = int(float(val_s))
            var.set(v)
            extra = f" ({desc_calc(v)})" if desc_calc else ""
            val_lbl.config(text=f"{v} {unit_str}{extra}")
            self._update_curve()

        scale = ttk.Scale(box, from_=min_v, to=max_v, orient="horizontal", value=var.get(), command=on_slide)
        scale.pack(fill="x", pady=(1, 0))

    def _on_mode_change(self, event=None):
        idx = self.combo_fb_mode.current()
        if 0 <= idx < len(FILTER_MODES):
            self.var_fb_mode.set(FILTER_MODES[idx][0])
            self._update_curve()

    def _update_curve(self):
        f_hz = 100 + self.var_fb_n.get() * 20
        n_hz = self.var_notch_n.get() * 10 + 100
        self.curve_canvas.set_params(
            accel=self.var_accel.get(),
            decel=self.var_decel.get(),
            bw_hz=self.var_bw_hz.get(),
            filter_hz=f_hz,
            notch_hz=n_hz,
            notch_on=self.var_notch_on.get(),
            kpp=self.var_kpp.get(),
            v_ff=self.var_v_ff.get()
        )

    def apply_preset_default(self):
        self.var_bw_hz.set(58)
        self.var_kvp.set(14)
        self.var_kvi32.set(10)
        self.var_fb_n.set(7)
        self.var_fb_mode.set(0)
        self.combo_fb_mode.current(0)
        self.var_out_filter_n.set(1)
        self.var_kpp.set(1000)
        self.var_v_ff.set(1000)
        self.var_pos_filter_n.set(1)
        self.var_notch_n.set(45)
        self.var_notch_on.set(True)
        self._update_curve()
        self.app.log("Loaded Factory Default Tuning Preset.")

    def apply_preset_rigid(self):
        self.var_bw_hz.set(120)
        self.var_kvp.set(28)
        self.var_kvi32.set(25)
        self.var_fb_n.set(15) # 400 Hz
        self.var_fb_mode.set(4)
        self.combo_fb_mode.current(3)
        self.var_out_filter_n.set(1)
        self.var_kpp.set(2200) # 22.0 Hz position BW
        self.var_v_ff.set(1000) # 100% feedforward
        self.var_pos_filter_n.set(1)
        self.var_notch_n.set(50) # 600 Hz notch
        self.var_notch_on.set(True)
        self._update_curve()
        self.app.log("Loaded High-Speed / Rigid Tuning Preset.")

    def apply_preset_heavy(self):
        self.var_bw_hz.set(35)
        self.var_kvp.set(9)
        self.var_kvi32.set(8)
        self.var_fb_n.set(5) # 200 Hz
        self.var_fb_mode.set(0)
        self.combo_fb_mode.current(0)
        self.var_out_filter_n.set(4)
        self.var_kpp.set(600) # 6.0 Hz position BW
        self.var_v_ff.set(800) # 80% feedforward
        self.var_pos_filter_n.set(8) # 8ms smoothing filter
        self.var_notch_n.set(35) # 450 Hz notch
        self.var_notch_on.set(True)
        self._update_curve()
        self.app.log("Loaded Heavy Load / Elastic Inertia Preset.")

    def apply_preset_quiet(self):
        self.var_bw_hz.set(45)
        self.var_kvp.set(11)
        self.var_kvi32.set(12)
        self.var_fb_n.set(7)
        self.var_fb_mode.set(10)
        self.combo_fb_mode.current(4)
        self.var_out_filter_n.set(8)
        self.var_kpp.set(800)
        self.var_v_ff.set(900)
        self.var_pos_filter_n.set(4)
        self.var_notch_n.set(40) # 500 Hz notch
        self.var_notch_on.set(True)
        self._update_curve()
        self.app.log("Loaded Low-Noise / Anti-Resonance Tuning Preset.")

    def write_tuning_to_motor(self):
        """Flashing all Section 8.2.1 & 8.2.2 tuning parameters via SDO."""
        notch_val = 0 if self.var_notch_on.get() else 1 # 0: ON, 1: OFF

        writes = [
            # Speed Loop (8.2.1)
            (0x60F9, 0x01, self.var_kvp.get().to_bytes(2, 'little'), "Kvp[0] Speed Proportional Gain"),
            (0x2FF0, 0x0A, self.var_bw_hz.get().to_bytes(2, 'little'), "Velocity_BW Speed Bandwidth"),
            (0x60F9, 0x07, self.var_kvi32.get().to_bytes(2, 'little'), "Kvi/32 Speed Integral Gain"),
            (0x60F9, 0x05, self.var_fb_n.get().to_bytes(1, 'little'), "Speed_Fb_N Filter Cutoff"),
            (0x60F9, 0x06, self.var_fb_mode.get().to_bytes(1, 'little'), "Speed_Mode Feedback Mode"),
            (0x60F9, 0x15, self.var_out_filter_n.get().to_bytes(1, 'little'), "Output_Filter_N Torque Filter"),
            
            # Position Loop & Notch (8.2.2)
            (0x60FB, 0x01, self.var_kpp.get().to_bytes(2, 'little'), "Kpp[0] Position Proportional Gain"),
            (0x2FF0, 0x1A, self.var_v_ff.get().to_bytes(2, 'little'), "K_Velocity_FF Feedforward"),
            (0x60FB, 0x05, self.var_pos_filter_n.get().to_bytes(1, 'little'), "Pos_Filter_N Smoothing Filter"),
            (0x60F9, 0x03, self.var_notch_n.get().to_bytes(1, 'little'), "Notch_N Resonance Frequency"),
            (0x60F9, 0x04, notch_val.to_bytes(1, 'little'), "Notch_On Filter Enable (0=On, 1=Off)")
        ]

        success_cnt = 0
        for idx, sub, data, desc in writes:
            err = self.app.sdo_write(idx, sub, data)
            if not err:
                success_cnt += 1
            time.sleep(0.01)

        self.app.log(f"Applied Section 8.2 Tuning: {success_cnt}/{len(writes)} objects written over SDO.")
        messagebox.showinfo("Tuning Applied", f"Successfully flashed {success_cnt}/{len(writes)} tuning parameters (Speed & Position Loops) to drive.")

    def read_tuning_from_motor(self):
        """Reads active tuning parameters live from motor."""
        # 1. Bandwidth 0x2FF0:0A
        d, _ = self.app.sdo_read(0x2FF0, 0x0A)
        if d: self.var_bw_hz.set(int.from_bytes(d[:2], 'little'))

        # 2. Kvp 0x60F9:01
        d, _ = self.app.sdo_read(0x60F9, 0x01)
        if d: self.var_kvp.set(int.from_bytes(d[:2], 'little'))

        # 3. Kvi/32 0x60F9:07
        d, _ = self.app.sdo_read(0x60F9, 0x07)
        if d: self.var_kvi32.set(int.from_bytes(d[:2], 'little'))

        # 4. Filter N 0x60F9:05
        d, _ = self.app.sdo_read(0x60F9, 0x05)
        if d: self.var_fb_n.set(d[0])

        # 5. Position Gain Kpp 0x60FB:01
        d, _ = self.app.sdo_read(0x60FB, 0x01)
        if d: self.var_kpp.set(int.from_bytes(d[:2], 'little'))

        # 6. Velocity Feedforward 0x2FF0:1A
        d, _ = self.app.sdo_read(0x2FF0, 0x1A)
        if d: self.var_v_ff.set(int.from_bytes(d[:2], 'little'))

        # 7. Position Smoothing Filter 0x60FB:05
        d, _ = self.app.sdo_read(0x60FB, 0x05)
        if d: self.var_pos_filter_n.set(d[0])

        # 8. Notch N 0x60F9:03 & Notch On 0x60F9:04
        d, _ = self.app.sdo_read(0x60F9, 0x03)
        if d: self.var_notch_n.set(d[0])

        d, _ = self.app.sdo_read(0x60F9, 0x04)
        if d: self.var_notch_on.set(d[0] == 0) # 0 is ON

        self._update_curve()
        self.app.log("Read live Section 8.2 tuning parameters from motor.")
