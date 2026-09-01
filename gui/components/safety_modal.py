"""
Live Physical Motion Safety Interlock Modal.
Requires explicit operator acknowledgment of rotating equipment hazards,
dynamic start/stop hazards, and active safeguarding before enabling motion.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from gui.theme import (
    COLOR_BG_DARK, COLOR_BG_SURFACE, COLOR_BG_CARD, COLOR_BG_INPUT, COLOR_BG_ACCENT,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_MUTED, COLOR_MURR_LIME, COLOR_MURR_GREEN,
    COLOR_WARNING, COLOR_DANGER, FONT_TITLE, FONT_SECTION, FONT_SUBTITLE,
    FONT_BODY, FONT_BODY_BOLD, FONT_MONO_BOLD, FONT_BADGE
)

class MotionSafetyModal(tk.Toplevel):
    """Safety interlock confirmation dialog required prior to physical motor movement."""

    def __init__(self, parent, on_confirm: Callable[[], None], on_cancel: Optional[Callable[[], None]] = None):
        super().__init__(parent)
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.confirmed = False

        self.title("⚠️ Live Physical Motion & Safety Safeguard Acknowledgment")
        self.geometry("640x510")
        self.resizable(False, False)
        self.configure(bg=COLOR_BG_DARK)
        self.transient(parent)
        self.grab_set()

        # Center on parent window
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        x = parent_x + max(0, (parent_w - 640) // 2)
        y = parent_y + max(0, (parent_h - 510) // 2)
        self.geometry(f"+{x}+{y}")

        self._build_ui()

    def _build_ui(self):
        # Header Banner
        hdr_frame = tk.Frame(self, bg="#381014", padx=20, pady=16)
        hdr_frame.pack(fill="x")

        tk.Label(hdr_frame, text="⚠️ LIVE MECHANICAL MOTION WARNING", bg="#381014", fg=COLOR_DANGER, font=(FONT_TITLE[0], 14, "bold")).pack(anchor="w")
        tk.Label(hdr_frame, text="Murrelektronik Vario-X Servo Motor Physical Safeguards", bg="#381014", fg="#FDA4AF", font=FONT_SUBTITLE).pack(anchor="w", pady=(2, 0))

        # Main Body
        body = tk.Frame(self, bg=COLOR_BG_SURFACE, padx=22, pady=18)
        body.pack(fill="both", expand=True)

        info_card = tk.Frame(body, bg=COLOR_BG_CARD, highlightbackground="#4A141A", highlightthickness=1, padx=16, pady=14)
        info_card.pack(fill="both", expand=True)

        tk.Label(info_card, text="MANDATORY SAFETY OPERATOR NOTICE:", bg=COLOR_BG_CARD, fg=COLOR_WARNING, font=FONT_BODY_BOLD).pack(anchor="w", pady=(0, 8))

        notices = [
            ("1. Rotating Equipment Hazard:", "Motor shaft motion will commence immediately and can accelerate, reverse, or stop at high speed (up to 6,000 RPM / 3.0 Nm peak torque)."),
            ("2. Personnel Clearances:", "Ensure hands, hair, loose clothing, jewelry, and loose tools are kept completely clear of the motor output shaft, coupling, and attached load."),
            ("3. Active Safeguarding & STO:", "Verify that proper physical guards, safety enclosures, and Safe Torque Off (STO) emergency interlocks are functional before enabling motion."),
            ("4. Emergency Stopping:", "You can trigger an immediate Quick Stop (0x0002) or cut 24V/48V power at any time using the emergency controls.")
        ]

        for title, desc in notices:
            row = tk.Frame(info_card, bg=COLOR_BG_CARD)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=f"• {title}", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_BODY_BOLD).pack(anchor="w")
            tk.Label(row, text=f"   {desc}", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_BODY, wraplength=540, justify="left").pack(anchor="w")

        # Acknowledgment Checkbox
        self.var_acknowledged = tk.BooleanVar(value=False)
        chk_box = tk.Frame(body, bg=COLOR_BG_SURFACE, pady=12)
        chk_box.pack(fill="x")

        chk = tk.Checkbutton(
            chk_box,
            text="I confirm all personnel and equipment are clear and safety guards are in place.",
            variable=self.var_acknowledged,
            bg=COLOR_BG_SURFACE, fg=COLOR_TEXT_PRIMARY,
            activebackground=COLOR_BG_SURFACE, activeforeground=COLOR_MURR_LIME,
            selectcolor=COLOR_BG_INPUT, font=FONT_BODY_BOLD,
            command=self._on_check_toggle
        )
        chk.pack(anchor="w")

        # Bottom Button Bar
        btn_bar = tk.Frame(self, bg=COLOR_BG_DARK, padx=20, pady=14)
        btn_bar.pack(fill="x")

        self.btn_confirm = tk.Button(
            btn_bar, text="🛡️ I Acknowledge — Enable Motion",
            bg=COLOR_BG_ACCENT, fg=COLOR_TEXT_MUTED, state="disabled",
            activebackground=COLOR_MURR_GREEN, activeforeground=COLOR_BG_DARK,
            font=FONT_BODY_BOLD, padx=16, pady=8, relief="flat",
            command=self._handle_confirm
        )
        self.btn_confirm.pack(side="right", padx=(10, 0))

        btn_cancel = tk.Button(
            btn_bar, text="Cancel Motion",
            bg=COLOR_BG_INPUT, fg=COLOR_TEXT_PRIMARY,
            activebackground=COLOR_BG_ACCENT, activeforeground=COLOR_TEXT_PRIMARY,
            font=FONT_BODY, padx=14, pady=8, relief="flat",
            command=self._handle_cancel
        )
        btn_cancel.pack(side="right")

    def _on_check_toggle(self):
        if self.var_acknowledged.get():
            self.btn_confirm.config(state="normal", bg=COLOR_MURR_GREEN, fg=COLOR_BG_DARK)
        else:
            self.btn_confirm.config(state="disabled", bg=COLOR_BG_ACCENT, fg=COLOR_TEXT_MUTED)

    def _handle_confirm(self):
        self.confirmed = True
        self.destroy()
        if self.on_confirm:
            self.on_confirm()

    def _handle_cancel(self):
        self.confirmed = False
        self.destroy()
        if self.on_cancel:
            self.on_cancel()
