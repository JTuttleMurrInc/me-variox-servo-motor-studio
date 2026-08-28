"""
Master & Bus Diagnostics Tab.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import TYPE_CHECKING, List

from core.ecat_raw import (
    RawEthercatMaster, AdapterInfo,
    AL_STATE_INIT, AL_STATE_PREOP, AL_STATE_SAFEOP, AL_STATE_OP, AL_STATE_NAMES
)
from core.ecat_master import SlaveInfo

from gui.theme import (
    COLOR_BG_DARK, COLOR_BG_SURFACE, COLOR_BG_CARD, COLOR_BG_ACCENT, COLOR_BG_INPUT,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_MUTED, COLOR_MURR_LIME, COLOR_WARNING, COLOR_DANGER,
    FONT_TITLE, FONT_SECTION, FONT_SUBTITLE, FONT_BODY, FONT_BODY_BOLD, FONT_MONO, FONT_BADGE
)

if TYPE_CHECKING:
    from app import VarioXMotorStudioApp

class DiagnosticsTab(tk.Frame):
    """Tab 5: Npcap Adapter, Slave Inventory, and Bus Diagnostics."""

    def __init__(self, parent, app: 'VarioXMotorStudioApp'):
        super().__init__(parent, bg=COLOR_BG_SURFACE, padx=16, pady=14)
        self.app = app
        self.adapters: List[AdapterInfo] = []

        self.var_sim_mode = tk.BooleanVar(value=app.is_simulation)
        self.var_adapter = tk.StringVar()

        self._build_top_controls()
        self._build_slave_table()
        self._build_log_console()

        self.refresh_adapters()

    def _build_top_controls(self):
        card = tk.Frame(self, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=16, pady=14)
        card.pack(fill="x", pady=(0, 14))

        tk.Label(card, text="ETHERCAT MASTER COMMUNICATIONS & ADAPTER CONFIGURATION", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_TITLE).pack(anchor="w")

        # Row 1: Mode Switch & Connect Controls
        r1 = tk.Frame(card, bg=COLOR_BG_CARD, pady=8)
        r1.pack(fill="x")

        chk_sim = tk.Checkbutton(
            r1, text="Virtual Motor Simulation Engine (Zero Hardware Required)",
            variable=self.var_sim_mode, command=self._on_sim_mode_toggle,
            bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, activebackground=COLOR_BG_CARD,
            activeforeground=COLOR_MURR_LIME, selectcolor=COLOR_BG_INPUT, font=FONT_BODY_BOLD
        )
        chk_sim.pack(side="left", padx=(0, 20))

        self.lbl_link_status = tk.Label(
            r1, text="STATUS: SIMULATION ACTIVE", bg="#16381C", fg=COLOR_MURR_LIME,
            font=FONT_BADGE, padx=10, pady=4
        )
        self.lbl_link_status.pack(side="right")

        # Row 2: Adapter Dropdown
        r2 = tk.Frame(card, bg=COLOR_BG_CARD, pady=4)
        r2.pack(fill="x")

        tk.Label(r2, text="Npcap Network Adapter:", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_BODY_BOLD).pack(side="left", padx=(0, 8))
        
        self.cb_adapters = ttk.Combobox(r2, textvariable=self.var_adapter, state="readonly", width=55)
        self.cb_adapters.pack(side="left", padx=(0, 8))

        ttk.Button(r2, text="Refresh", style="Action.TButton", command=self.refresh_adapters).pack(side="left", padx=(0, 4))
        
        self.btn_connect = ttk.Button(r2, text="Connect Live Bus", style="Murr.TButton", command=self.toggle_connect)
        self.btn_connect.pack(side="left", padx=(0, 4))

        ttk.Button(r2, text="Scan Slaves (BRD)", style="Action.TButton", command=self.scan_slaves).pack(side="left")

        # Row 3: Bus AL State Commands
        r3 = tk.Frame(card, bg=COLOR_BG_CARD, pady=6)
        r3.pack(fill="x")

        tk.Label(r3, text="Bus State Transitions:", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_SUBTITLE).pack(side="left", padx=(0, 10))
        
        ttk.Button(r3, text="Request INIT", style="Action.TButton", command=lambda: self.request_al_state(AL_STATE_INIT)).pack(side="left", padx=2)
        ttk.Button(r3, text="Request PRE-OP", style="Action.TButton", command=lambda: self.request_al_state(AL_STATE_PREOP)).pack(side="left", padx=2)
        ttk.Button(r3, text="Request SAFE-OP", style="Action.TButton", command=lambda: self.request_al_state(AL_STATE_SAFEOP)).pack(side="left", padx=2)
        ttk.Button(r3, text="Request OP", style="Murr.TButton", command=lambda: self.request_al_state(AL_STATE_OP)).pack(side="left", padx=2)

    def _build_slave_table(self):
        card = tk.Frame(self, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=16, pady=12)
        card.pack(fill="x", pady=(0, 14))

        tk.Label(card, text="ETHERCAT SLAVE INVENTORY", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_SECTION).pack(anchor="w", pady=(0, 8))

        cols = ("pos", "addr", "state", "vendor", "product", "mbx_out", "mbx_in")
        self.slave_tree = ttk.Treeview(card, columns=cols, show="headings", height=4)
        
        self.slave_tree.heading("pos", text="Pos")
        self.slave_tree.heading("addr", text="Station Address")
        self.slave_tree.heading("state", text="AL State")
        self.slave_tree.heading("vendor", text="Vendor ID")
        self.slave_tree.heading("product", text="Product Code")
        self.slave_tree.heading("mbx_out", text="Mailbox Out (SM0)")
        self.slave_tree.heading("mbx_in", text="Mailbox In (SM1)")

        self.slave_tree.column("pos", width=50, anchor="center")
        self.slave_tree.column("addr", width=120, anchor="center")
        self.slave_tree.column("state", width=130, anchor="center")
        self.slave_tree.column("vendor", width=120, anchor="center")
        self.slave_tree.column("product", width=120, anchor="center")
        self.slave_tree.column("mbx_out", width=140, anchor="center")
        self.slave_tree.column("mbx_in", width=140, anchor="center")

        self.slave_tree.pack(fill="x")

    def _build_log_console(self):
        card = tk.Frame(self, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=16, pady=12)
        card.pack(fill="both", expand=True)

        hdr = tk.Frame(card, bg=COLOR_BG_CARD)
        hdr.pack(fill="x", pady=(0, 6))

        tk.Label(hdr, text="LIVE PACKET & PROTOCOL LOG", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_SECTION).pack(side="left")
        ttk.Button(hdr, text="Clear Log", style="Action.TButton", command=self.clear_log).pack(side="right")

        f_txt = tk.Frame(card, bg=COLOR_BG_INPUT)
        f_txt.pack(fill="both", expand=True)

        self.txt_log = tk.Text(
            f_txt, bg=COLOR_BG_INPUT, fg=COLOR_MURR_LIME,
            font=FONT_MONO, wrap="none", insertbackground=COLOR_MURR_LIME,
            borderwidth=0, highlightthickness=0
        )
        sb_y = ttk.Scrollbar(f_txt, orient="vertical", command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=sb_y.set)

        self.txt_log.pack(side="left", fill="both", expand=True)
        sb_y.pack(side="right", fill="y")

    def log_message(self, msg: str):
        self.txt_log.insert(tk.END, f"{msg}\n")
        self.txt_log.see(tk.END)

    def clear_log(self):
        self.txt_log.delete("1.0", tk.END)

    def refresh_adapters(self):
        raw_list = RawEthercatMaster.list_adapters()
        
        # Sort so physical adapters (Intel I219, Ethernet) appear first
        def adapter_priority(a):
            desc = a.description.lower()
            if "i219" in desc or "intel(r) ethernet" in desc:
                return 0
            if "ethernet" in desc and not any(v in desc for v in ["virtual", "hyper-v", "loopback", "tap", "wintun"]):
                return 1
            if "wi-fi" in desc or "wireless" in desc:
                return 2
            return 3

        self.adapters = sorted(raw_list, key=adapter_priority)
        names = [f"{a.description} ({a.name[:20]}...)" for a in self.adapters]
        self.cb_adapters['values'] = names
        
        if names:
            # Pick Intel I219 or first physical ethernet adapter by default
            chosen_idx = 0
            for i, a in enumerate(self.adapters):
                if "i219" in a.description.lower() or ("ethernet" in a.description.lower() and "virtual" not in a.description.lower()):
                    chosen_idx = i
                    break
            self.cb_adapters.current(chosen_idx)

    def _on_sim_mode_toggle(self):
        is_sim = self.var_sim_mode.get()
        self.app.set_simulation_mode(is_sim)
        if is_sim:
            self.lbl_link_status.config(text="STATUS: SIMULATION ACTIVE", bg="#16381C", fg=COLOR_MURR_LIME)
            self.btn_connect.config(text="Connect Live Bus")
        else:
            self.lbl_link_status.config(text="STATUS: HARDWARE DISCONNECTED", bg="#4A141A", fg=COLOR_DANGER)
        self.update_slave_list()

    def toggle_connect(self):
        if self.app.is_hardware_connected:
            self.app.disconnect_hardware()
            self.lbl_link_status.config(text="STATUS: HARDWARE DISCONNECTED", bg="#4A141A", fg=COLOR_DANGER)
            self.btn_connect.config(text="Connect Live Bus")
        else:
            sel_idx = self.cb_adapters.current()
            if sel_idx < 0 or sel_idx >= len(self.adapters):
                messagebox.showerror("No Adapter", "Please select a valid network adapter.")
                return
            adapter = self.adapters[sel_idx]
            ok = self.app.connect_hardware(adapter.name)
            if ok:
                self.lbl_link_status.config(text="STATUS: LIVE ETHERCAT CONNECTED", bg="#16381C", fg=COLOR_MURR_LIME)
                self.btn_connect.config(text="Disconnect")
                self.scan_slaves()
            else:
                messagebox.showerror("Connection Failed", f"Could not open adapter:\n{adapter.description}")

    def scan_slaves(self):
        slaves = self.app.scan_slaves()
        self.update_slave_list()

    def request_al_state(self, state: int):
        ok = self.app.set_al_state(state)
        self.update_slave_list()
        state_name = AL_STATE_NAMES.get(state, hex(state))
        if ok:
            self.app.log(f"Bus state transition to {state_name} succeeded.")
        else:
            self.app.log(f"Bus state transition to {state_name} timed out or failed.")

    def update_slave_list(self):
        for item in self.slave_tree.get_children():
            self.slave_tree.delete(item)

        if self.app.is_simulation:
            self.slave_tree.insert("", "end", values=(
                "0", "0x1000", "OP (0x08)", "0x000005D5", "0x00B85381", "0x1000 (128B)", "0x1400 (128B)"
            ))
        else:
            for s in self.app.ecat_master.slaves:
                state_str = f"{AL_STATE_NAMES.get(s.al_state, 'UNKNOWN')} (0x{s.al_state:02X})"
                self.slave_tree.insert("", "end", values=(
                    str(s.position),
                    f"0x{s.configured_addr:04X}",
                    state_str,
                    f"0x{s.vendor_id:08X}",
                    f"0x{s.product_code:08X}",
                    f"0x{s.mailbox.sm0_addr:04X} ({s.mailbox.sm0_len}B)",
                    f"0x{s.mailbox.sm1_addr:04X} ({s.mailbox.sm1_len}B)",
                ))
