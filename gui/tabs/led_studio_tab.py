"""
LED Color Ring Studio Tab (Object 0x2FEF).
Full interactive control over the 32-bit optical status ring, pattern generator, presets, and bitfield inspector.
"""

import time
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Optional

from core.led_ring import (
    LedRingConfig, BlinkPattern, PATTERN_NAMES, RING_PRESETS
)
from gui.components.ring_widget import LedRingWidget
from gui.theme import (
    COLOR_BG_SURFACE, COLOR_BG_CARD, COLOR_BG_INPUT, COLOR_BG_ACCENT,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_MUTED, COLOR_MURR_LIME, COLOR_MURR_GREEN,
    COLOR_WARNING, COLOR_DANGER, FONT_TITLE, FONT_SECTION, FONT_SUBTITLE,
    FONT_BODY_BOLD, FONT_MONO, FONT_MONO_BOLD, FONT_BADGE,
    LED_COLOR_RED_ON, LED_COLOR_YEL_ON, LED_COLOR_GRN_ON
)

class LedStudioTab(tk.Frame):
    """Studio for parameterizing, synthesizing, and testing the 32-bit LED Ring."""

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COLOR_BG_SURFACE, padx=16, pady=16, **kwargs)
        self.app = app

        # State
        self.current_config = LedRingConfig(user_mode=True, green_left=0x1, green_right=0x1)

        # Variables
        self.var_user_mode = tk.BooleanVar(value=True)
        self.var_red_l = tk.StringVar(value="Off")
        self.var_yel_l = tk.StringVar(value="Off")
        self.var_grn_l = tk.StringVar(value="Solid On")
        
        self.var_red_r = tk.StringVar(value="Off")
        self.var_yel_r = tk.StringVar(value="Off")
        self.var_grn_r = tk.StringVar(value="Solid On")
        
        self.var_raw_hex = tk.StringVar(value="0x80000011")

        # Main 3-Column Layout
        # Col 1: Visual Ring & Real-Time Preview
        # Col 2: Channel Matrices & Controls
        # Col 3: Quick Presets & Bitfield Inspector
        content = tk.Frame(self, bg=COLOR_BG_SURFACE)
        content.pack(fill="both", expand=True)

        col_left = tk.Frame(content, bg=COLOR_BG_SURFACE, width=320)
        col_left.pack(side="left", fill="y", padx=(0, 16))
        self._build_visual_panel(col_left)

        col_mid = tk.Frame(content, bg=COLOR_BG_SURFACE, width=380)
        col_mid.pack(side="left", fill="both", expand=True, padx=(0, 16))
        self._build_channels_panel(col_mid)

        col_right = tk.Frame(content, bg=COLOR_BG_SURFACE, width=340)
        col_right.pack(side="left", fill="both", expand=True)
        self._build_presets_and_inspector(col_right)

        # Update initial state
        self._sync_ui_from_config()

    def _build_visual_panel(self, parent):
        card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=16, pady=16)
        card.pack(fill="both", expand=True)

        tk.Label(card, text="LIVE COLOR RING PREVIEW", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_TITLE).pack(anchor="w")
        tk.Label(card, text="Simulated 60FPS Optical Waveform", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_SUBTITLE).pack(anchor="w", pady=(0, 12))

        self.ring_widget = LedRingWidget(card, size=280)
        self.ring_widget.pack(pady=10)

        # Status Summary Box
        summary = tk.Frame(card, bg=COLOR_BG_INPUT, padx=10, pady=8)
        summary.pack(fill="x", pady=(10, 0))

        self.lbl_status_summary = tk.Label(
            summary, text="LEFT: GREEN (Solid)\nRIGHT: GREEN (Solid)",
            bg=COLOR_BG_INPUT, fg=COLOR_TEXT_PRIMARY, font=FONT_MONO, justify="left"
        )
        self.lbl_status_summary.pack(anchor="w")

        # Priority Rule Notice
        notice = tk.Label(
            card,
            text="Priority Order: Red > Yellow > Green\nIf multiple colors are active, the highest priority color overrides.",
            bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_SUBTITLE, justify="left"
        )
        notice.pack(anchor="w", pady=(12, 0))

    def _build_channels_panel(self, parent):
        card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=16, pady=16)
        card.pack(fill="both", expand=True)

        tk.Label(card, text="CHANNEL MATRIX & CONTROLS", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_TITLE).pack(anchor="w")
        
        # Target Axis Selector
        target_box = tk.Frame(card, bg=COLOR_BG_CARD, pady=4)
        target_box.pack(fill="x")
        tk.Label(target_box, text="Target Motor:", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_BADGE).pack(side="left", padx=(0, 6))
        self.var_led_target = tk.StringVar(value="all")
        for val, lbl in [("all", "All Motors (Broadcast)"), ("0x1000", "Motor 1 (0x1000)"), ("0x1001", "Motor 2 (0x1001)")]:
            tk.Radiobutton(
                target_box, text=lbl, value=val, variable=self.var_led_target,
                bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, selectcolor=COLOR_BG_INPUT,
                activebackground=COLOR_BG_CARD, activeforeground=COLOR_MURR_LIME,
                font=FONT_BADGE, indicatoron=False, padx=6, pady=2
            ).pack(side="left", padx=2)

        # User Mode vs Auto Mode Switch
        mode_frame = tk.Frame(card, bg=COLOR_BG_CARD, pady=6)
        mode_frame.pack(fill="x")

        chk_mode = tk.Checkbutton(
            mode_frame, text="Enable User Mode (Bit 31 = 1 / Manual Control)",
            variable=self.var_user_mode, command=self._on_control_change,
            bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, activebackground=COLOR_BG_CARD,
            activeforeground=COLOR_MURR_LIME, selectcolor=COLOR_BG_INPUT, font=FONT_BODY_BOLD
        )
        chk_mode.pack(anchor="w")

        # Separator
        ttk.Separator(card, orient="horizontal").pack(fill="x", pady=8)

        pattern_list = list(PATTERN_NAMES.values())

        # Dual Column: Left Side vs Right Side
        sides_frame = tk.Frame(card, bg=COLOR_BG_CARD)
        sides_frame.pack(fill="both", expand=True, pady=6)

        # LEFT HALF CONTROLS
        left_box = tk.Frame(sides_frame, bg=COLOR_BG_CARD)
        left_box.pack(side="left", fill="both", expand=True, padx=(0, 8))

        tk.Label(left_box, text="LEFT HALF (X2 Side)", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_SECTION).pack(anchor="w", pady=(0, 6))

        # Left Red
        f_rl = tk.Frame(left_box, bg=COLOR_BG_CARD)
        f_rl.pack(fill="x", pady=4)
        tk.Label(f_rl, text="Red (rrrr):", bg=COLOR_BG_CARD, fg=LED_COLOR_RED_ON, font=FONT_BODY_BOLD).pack(anchor="w")
        cb_rl = ttk.Combobox(f_rl, textvariable=self.var_red_l, values=pattern_list, state="readonly")
        cb_rl.pack(fill="x", pady=2)
        cb_rl.bind("<<ComboboxSelected>>", lambda e: self._on_control_change())

        # Left Yellow
        f_yl = tk.Frame(left_box, bg=COLOR_BG_CARD)
        f_yl.pack(fill="x", pady=4)
        tk.Label(f_yl, text="Yellow (yyyy):", bg=COLOR_BG_CARD, fg=LED_COLOR_YEL_ON, font=FONT_BODY_BOLD).pack(anchor="w")
        cb_yl = ttk.Combobox(f_yl, textvariable=self.var_yel_l, values=pattern_list, state="readonly")
        cb_yl.pack(fill="x", pady=2)
        cb_yl.bind("<<ComboboxSelected>>", lambda e: self._on_control_change())

        # Left Green
        f_gl = tk.Frame(left_box, bg=COLOR_BG_CARD)
        f_gl.pack(fill="x", pady=4)
        tk.Label(f_gl, text="Green (gggg):", bg=COLOR_BG_CARD, fg=LED_COLOR_GRN_ON, font=FONT_BODY_BOLD).pack(anchor="w")
        cb_gl = ttk.Combobox(f_gl, textvariable=self.var_grn_l, values=pattern_list, state="readonly")
        cb_gl.pack(fill="x", pady=2)
        cb_gl.bind("<<ComboboxSelected>>", lambda e: self._on_control_change())

        # RIGHT HALF CONTROLS
        right_box = tk.Frame(sides_frame, bg=COLOR_BG_CARD)
        right_box.pack(side="left", fill="both", expand=True, padx=(8, 0))

        tk.Label(right_box, text="RIGHT HALF (X3 Side)", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_SECTION).pack(anchor="w", pady=(0, 6))

        # Right Red
        f_rr = tk.Frame(right_box, bg=COLOR_BG_CARD)
        f_rr.pack(fill="x", pady=4)
        tk.Label(f_rr, text="Red (RRRR):", bg=COLOR_BG_CARD, fg=LED_COLOR_RED_ON, font=FONT_BODY_BOLD).pack(anchor="w")
        cb_rr = ttk.Combobox(f_rr, textvariable=self.var_red_r, values=pattern_list, state="readonly")
        cb_rr.pack(fill="x", pady=2)
        cb_rr.bind("<<ComboboxSelected>>", lambda e: self._on_control_change())

        # Right Yellow
        f_yr = tk.Frame(right_box, bg=COLOR_BG_CARD)
        f_yr.pack(fill="x", pady=4)
        tk.Label(f_yr, text="Yellow (YYYY):", bg=COLOR_BG_CARD, fg=LED_COLOR_YEL_ON, font=FONT_BODY_BOLD).pack(anchor="w")
        cb_yr = ttk.Combobox(f_yr, textvariable=self.var_yel_r, values=pattern_list, state="readonly")
        cb_yr.pack(fill="x", pady=2)
        cb_yr.bind("<<ComboboxSelected>>", lambda e: self._on_control_change())

        # Right Green
        f_gr = tk.Frame(right_box, bg=COLOR_BG_CARD)
        f_gr.pack(fill="x", pady=4)
        tk.Label(f_gr, text="Green (GGGG):", bg=COLOR_BG_CARD, fg=LED_COLOR_GRN_ON, font=FONT_BODY_BOLD).pack(anchor="w")
        cb_gr = ttk.Combobox(f_gr, textvariable=self.var_grn_r, values=pattern_list, state="readonly")
        cb_gr.pack(fill="x", pady=2)
        cb_gr.bind("<<ComboboxSelected>>", lambda e: self._on_control_change())

        # Action Buttons
        btn_bar = tk.Frame(card, bg=COLOR_BG_CARD)
        btn_bar.pack(fill="x", pady=(16, 0))

        ttk.Button(
            btn_bar, text="Apply to Motor (SDO Write 0x2FEF:01)",
            style="Murr.TButton", command=self.apply_to_motor
        ).pack(side="left", fill="x", expand=True, padx=(0, 6))

        ttk.Button(
            btn_bar, text="Read Status (0x2FEF:02)",
            style="Action.TButton", command=self.read_from_motor
        ).pack(side="left", fill="x", expand=True, padx=(6, 0))

    def _build_presets_and_inspector(self, parent):
        # 1. Quick Presets Card
        presets_card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=16, pady=14)
        presets_card.pack(fill="x", pady=(0, 14))

        tk.Label(presets_card, text="1-CLICK QUICK PRESETS", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_TITLE).pack(anchor="w", pady=(0, 8))

        p_grid = tk.Frame(presets_card, bg=COLOR_BG_CARD)
        p_grid.pack(fill="x")

        # Add preset buttons
        row, col = 0, 0
        for name, cfg in RING_PRESETS.items():
            btn = ttk.Button(
                p_grid, text=name, style="Action.TButton",
                command=lambda c=cfg: self.load_preset(c)
            )
            btn.grid(row=row, column=col, sticky="ew", padx=2, pady=2)
            col += 1
            if col > 1:
                col = 0
                row += 1
        p_grid.columnconfigure(0, weight=1)
        p_grid.columnconfigure(1, weight=1)

        # 2. Bitfield Inspector & Raw DWORD Card
        insp_card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=16, pady=14)
        insp_card.pack(fill="both", expand=True)

        tk.Label(insp_card, text="32-BIT BITFIELD BREAKDOWN", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_TITLE).pack(anchor="w")

        # Raw DWORD Hex Entry
        raw_box = tk.Frame(insp_card, bg=COLOR_BG_CARD, pady=8)
        raw_box.pack(fill="x")

        tk.Label(raw_box, text="Raw Hex DWORD:", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_BODY_BOLD).pack(side="left", padx=(0, 8))
        entry_hex = ttk.Entry(raw_box, textvariable=self.var_raw_hex, font=FONT_MONO_BOLD, width=14)
        entry_hex.pack(side="left", padx=(0, 8))

        ttk.Button(raw_box, text="Load Hex", style="Action.TButton", command=self.load_from_hex).pack(side="left")

        # Bitfield Table Display
        self.lbl_bitfields = tk.Label(
            insp_card, text="", bg=COLOR_BG_INPUT, fg=COLOR_TEXT_MUTED,
            font=FONT_MONO, justify="left", padx=10, pady=8
        )
        self.lbl_bitfields.pack(fill="both", expand=True, pady=(6, 0))

    def _name_to_code(self, name_str: str) -> int:
        for code, name in PATTERN_NAMES.items():
            if name == name_str:
                return code
        return 0

    def _code_to_name(self, code: int) -> str:
        return PATTERN_NAMES.get(code & 0xF, "Off")

    def _on_control_change(self):
        cfg = LedRingConfig(
            user_mode=self.var_user_mode.get(),
            red_right=self._name_to_code(self.var_red_r.get()),
            red_left=self._name_to_code(self.var_red_l.get()),
            yellow_right=self._name_to_code(self.var_yel_r.get()),
            yellow_left=self._name_to_code(self.var_yel_l.get()),
            green_right=self._name_to_code(self.var_grn_r.get()),
            green_left=self._name_to_code(self.var_grn_l.get())
        )
        self.current_config = cfg
        self._update_inspector(cfg)
        self.ring_widget.set_config(cfg)
        self.ring_widget.update_animation()

    def _sync_ui_from_config(self):
        cfg = self.current_config
        self.var_user_mode.set(cfg.user_mode)
        self.var_red_l.set(self._code_to_name(cfg.red_left))
        self.var_yel_l.set(self._code_to_name(cfg.yellow_left))
        self.var_grn_l.set(self._code_to_name(cfg.green_left))

        self.var_red_r.set(self._code_to_name(cfg.red_right))
        self.var_yel_r.set(self._code_to_name(cfg.yellow_right))
        self.var_grn_r.set(self._code_to_name(cfg.green_right))

        self._update_inspector(cfg)
        self.ring_widget.set_config(cfg)
        self.ring_widget.update_animation()

    def _update_inspector(self, cfg: LedRingConfig):
        dword = cfg.to_dword()
        self.var_raw_hex.set(f"0x{dword:08X}")

        bit31 = "1 (User Mode)" if cfg.user_mode else "0 (Auto Mode)"
        txt = (
            f"Bit 31 (Mode):    {bit31}\n"
            f"Bits 30..24:      0000000 (Reserved)\n"
            f"Bits 23..20 (RR): 0x{cfg.red_right:X} ({self._code_to_name(cfg.red_right)})\n"
            f"Bits 19..16 (rl): 0x{cfg.red_left:X} ({self._code_to_name(cfg.red_left)})\n"
            f"Bits 15..12 (YR): 0x{cfg.yellow_right:X} ({self._code_to_name(cfg.yellow_right)})\n"
            f"Bits 11..8  (yl): 0x{cfg.yellow_left:X} ({self._code_to_name(cfg.yellow_left)})\n"
            f"Bits 7..4   (GR): 0x{cfg.green_right:X} ({self._code_to_name(cfg.green_right)})\n"
            f"Bits 3..0   (gl): 0x{cfg.green_left:X} ({self._code_to_name(cfg.green_left)})\n"
            f"Binary: {dword:032b}"
        )
        self.lbl_bitfields.config(text=txt)

        # Summary text
        mode_str = "USER" if cfg.user_mode else "AUTO"
        l_color, _ = cfg.get_left_state().active_color(time.time())
        r_color, _ = cfg.get_right_state().active_color(time.time())
        self.lbl_status_summary.config(
            text=f"Mode: {mode_str}\nLeft Active: {str(l_color).upper()}\nRight Active: {str(r_color).upper()}"
        )

    def load_preset(self, cfg: LedRingConfig):
        self.current_config = cfg
        self._sync_ui_from_config()
        self.apply_to_motor()

    def load_from_hex(self):
        val_str = self.var_raw_hex.get().strip()
        try:
            val = int(val_str, 16) if (val_str.startswith("0x") or val_str.startswith("0X")) else int(val_str)
            self.current_config = LedRingConfig.from_dword(val)
            self._sync_ui_from_config()
        except ValueError:
            messagebox.showerror("Invalid Hex", f"Could not parse '{val_str}' as a 32-bit hex DWORD.")

    def apply_to_motor(self):
        """Sends SDO Download 0x2FEF:01 to selected motor or broadcasts to all."""
        target = self.var_led_target.get()
        target_addr = None if target == "all" else int(target, 16)
        self.app.apply_led_config(self.current_config, station_addr=target_addr)
        self.ring_widget.set_config(self.current_config)

    def read_from_motor(self):
        """Reads SDO Upload 0x2FEF:02 from motor / simulation."""
        target = self.var_led_target.get()
        addr = 0x1000 if target == "all" else int(target, 16)
        data, err = self.app.sdo_read_slave(addr, 0x2FEF, 0x02)
        if err:
            self.app.log(f"Error reading LED_Status (0x2FEF:02) from 0x{addr:04X}: {err}")
        elif data and len(data) >= 4:
            dword = int.from_bytes(data[:4], 'little')
            self.current_config = LedRingConfig.from_dword(dword)
            self._sync_ui_from_config()
            self.app.log(f"Read LED_Status from 0x{addr:04X}: 0x{dword:08X}")

    def update_animation(self):
        self.ring_widget.update_frame()
