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
        self.geometry("660x600")
        self.minsize(620, 560)
        self.configure(bg=COLOR_BG_DARK)
        self.transient(parent)
        self.grab_set()

        # Center on parent window
        parent.update_idletasks()
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        x = parent_x + max(0, (parent_w - 660) // 2)
        y = parent_y + max(0, (parent_h - 600) // 2)
        self.geometry(f"+{x}+{y}")

        self._build_ui()

    def _build_ui(self):
        # 1. Top Header Banner (Packed Top)
        hdr_frame = tk.Frame(self, bg="#381014", padx=20, pady=14)
        hdr_frame.pack(side="top", fill="x")

        tk.Label(hdr_frame, text="⚠️ LIVE MECHANICAL MOTION WARNING", bg="#381014", fg=COLOR_DANGER, font=(FONT_TITLE[0], 14, "bold")).pack(anchor="w")
        tk.Label(hdr_frame, text="Murrelektronik Vario-X Servo Motor Physical Safeguards", bg="#381014", fg="#FDA4AF", font=FONT_SUBTITLE).pack(anchor="w", pady=(2, 0))

        # 2. Bottom Button Action Bar (Packed Bottom FIRST so it is always visible)
        btn_bar = tk.Frame(self, bg=COLOR_BG_DARK, padx=20, pady=16, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1)
        btn_bar.pack(side="bottom", fill="x")

        self.btn_confirm = tk.Button(
            btn_bar, text="🛡️ I Acknowledge — Enable Motion",
            bg=COLOR_BG_ACCENT, fg=COLOR_TEXT_MUTED, state="disabled",
            activebackground=COLOR_MURR_GREEN, activeforeground=COLOR_BG_DARK,
            font=FONT_BODY_BOLD, padx=18, pady=9, relief="flat",
            command=self._handle_confirm
        )
        self.btn_confirm.pack(side="right", padx=(12, 0))

        btn_cancel = tk.Button(
            btn_bar, text="Cancel Motion",
            bg=COLOR_BG_INPUT, fg=COLOR_TEXT_PRIMARY,
            activebackground=COLOR_BG_ACCENT, activeforeground=COLOR_TEXT_PRIMARY,
            font=FONT_BODY_BOLD, padx=16, pady=9, relief="flat",
            command=self._handle_cancel
        )
        btn_cancel.pack(side="right")

        # 3. Main Center Content Body (Fills remaining middle space)
        body = tk.Frame(self, bg=COLOR_BG_SURFACE, padx=20, pady=14)
        body.pack(side="top", fill="both", expand=True)

        info_card = tk.Frame(body, bg=COLOR_BG_CARD, highlightbackground="#4A141A", highlightthickness=1, padx=14, pady=12)
        info_card.pack(fill="both", expand=True)

        tk.Label(info_card, text="MANDATORY SAFETY OPERATOR NOTICE:", bg=COLOR_BG_CARD, fg=COLOR_WARNING, font=FONT_BODY_BOLD).pack(anchor="w", pady=(0, 6))

        notices = [
            ("1. Rotating Equipment Hazard:", "Motor shaft motion will commence immediately and can accelerate, reverse, or stop at high speed (up to 6,000 RPM / 3.0 Nm peak torque)."),
            ("2. Personnel Clearances:", "Ensure hands, hair, loose clothing, jewelry, and loose tools are kept completely clear of the motor output shaft, coupling, and attached load."),
            ("3. Active Safeguarding & STO:", "Verify that proper physical guards, safety enclosures, and Safe Torque Off (STO) emergency interlocks are functional before enabling motion."),
            ("4. Emergency Stopping:", "You can trigger an immediate Quick Stop (0x0002) or cut 24V/48V power at any time using the emergency controls.")
        ]

        for title, desc in notices:
            row = tk.Frame(info_card, bg=COLOR_BG_CARD)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=f"• {title}", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_BODY_BOLD).pack(anchor="w")
            tk.Label(row, text=f"   {desc}", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_BODY, wraplength=560, justify="left").pack(anchor="w")

        # Acknowledgment Checkbox Box
        self.var_acknowledged = tk.BooleanVar(value=False)
        chk_box = tk.Frame(body, bg=COLOR_BG_SURFACE, pady=8)
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

    def _on_check_toggle(self):
        if self.var_acknowledged.get():
            self.btn_confirm.config(state="normal", bg=COLOR_MURR_GREEN, fg=COLOR_BG_DARK, cursor="hand2")
        else:
            self.btn_confirm.config(state="disabled", bg=COLOR_BG_ACCENT, fg=COLOR_TEXT_MUTED, cursor="")

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
