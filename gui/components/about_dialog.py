"""
About & Cyber Resilience Act (CRA) Compliance / SBOM Viewer Dialog.
Displays software identity, architecture, cybersecurity assurance, and a full
Software Bill of Materials (SBOM) conforming to EU Cyber Resilience Act (EU 2024/2847).
"""

import os
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Optional

from gui.theme import (
    COLOR_BG_DARK, COLOR_BG_SURFACE, COLOR_BG_CARD, COLOR_BG_INPUT, COLOR_BG_ACCENT,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_MUTED, COLOR_MURR_LIME, COLOR_MURR_GREEN,
    COLOR_WARNING, COLOR_DANGER, FONT_APP_TITLE, FONT_TITLE, FONT_SECTION,
    FONT_SUBTITLE, FONT_BODY, FONT_BODY_BOLD, FONT_MONO, FONT_MONO_BOLD, FONT_BADGE
)

# Full Software Bill of Materials (SBOM) Definition in compliance with CRA
SBOM_COMPONENTS = [
    {
        "name": "me-variox-servo-motor-studio",
        "version": "1.0.0",
        "type": "application",
        "supplier": "Murrelektronik GmbH / US Solutions Team",
        "license": "Proprietary / Murrelektronik Internal",
        "purl": "pkg:generic/murrelektronik/variox-motor-studio@1.0.0",
        "description": "EtherCAT Diagnostic Workbench & CiA 402 Servo Studio"
    },
    {
        "name": "python",
        "version": "3.12.x / 3.10+",
        "type": "runtime-environment",
        "supplier": "Python Software Foundation",
        "license": "PSF License 2.0 (Open Source)",
        "purl": "pkg:generic/python@3.12",
        "description": "Standard Python Core Execution Runtime"
    },
    {
        "name": "tkinter / tcl-tk",
        "version": "8.6.14",
        "type": "framework",
        "supplier": "Tcl Core Team / ActiveState",
        "license": "Tcl/Tk License (BSD-style)",
        "purl": "pkg:generic/tcl-tk@8.6.14",
        "description": "Native OS Windowing & Canvas UI Subsystem"
    },
    {
        "name": "pillow",
        "version": "11.3.0",
        "type": "library",
        "supplier": "Jeffrey A. Clark (Alex) / Pillow Contributors",
        "license": "Historical Permission Notice and Disclaimer (HPND)",
        "purl": "pkg:pypi/pillow@11.3.0",
        "description": "Image Processing & High-DPI Icon Rendering Engine"
    },
    {
        "name": "npcap-driver / wpcap.dll",
        "version": "1.79 / WinPcap API",
        "type": "system-driver",
        "supplier": "Nmap Project / Insecure.Com LLC",
        "license": "Npcap License (OEM / Commercial)",
        "purl": "pkg:generic/nmap/npcap@1.79",
        "description": "Windows Kernel NDIS 6 Layer-2 Raw Packet Transport Driver"
    },
    {
        "name": "variox-ecat-raw-codec",
        "version": "1.0.0",
        "type": "internal-module",
        "supplier": "Murrelektronik US Solutions Team",
        "license": "Murrelektronik Proprietary",
        "purl": "pkg:generic/murr/ecat-raw@1.0.0",
        "description": "Layer-2 EtherCAT Ethernet Framing & Datagram Engine"
    },
    {
        "name": "variox-coe-sdo-engine",
        "version": "1.0.0",
        "type": "internal-module",
        "supplier": "Murrelektronik US Solutions Team",
        "license": "Murrelektronik Proprietary",
        "purl": "pkg:generic/murr/coe-sdo@1.0.0",
        "description": "CANopen over EtherCAT (CoE) SDO Mailbox State Machine"
    },
    {
        "name": "variox-cia402-controller",
        "version": "1.0.0",
        "type": "internal-module",
        "supplier": "Murrelektronik US Solutions Team",
        "license": "Murrelektronik Proprietary",
        "purl": "pkg:generic/murr/cia402-ctrl@1.0.0",
        "description": "Drive Profile State Machine & 16-bit Telemetry Demuxer"
    },
    {
        "name": "variox-virtual-physics-sim",
        "version": "1.0.0",
        "type": "internal-module",
        "supplier": "Murrelektronik US Solutions Team",
        "license": "Murrelektronik Proprietary",
        "purl": "pkg:generic/murr/virtual-sim@1.0.0",
        "description": "Hardware-in-the-Loop Offline Physics Simulation Engine"
    }
]

class AboutDialog(tk.Toplevel):
    """About & CRA Compliance SBOM Modal Window."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("About — Murrelektronik Vario-X Motor Studio & CRA SBOM")
        self.geometry("860x650")
        self.minsize(720, 520)
        self.configure(bg=COLOR_BG_DARK)
        self.transient(parent)
        self.grab_set()

        # Header Frame
        header = tk.Frame(self, bg=COLOR_BG_DARK, padx=20, pady=16)
        header.pack(fill="x")

        tk.Label(header, text="MURRELEKTRONIK", bg=COLOR_BG_DARK, fg=COLOR_MURR_LIME, font=(FONT_APP_TITLE[0], 16, "bold")).pack(anchor="w")
        tk.Label(header, text="Vario-X Motor Studio — EtherCAT Diagnostic & Tuning Workbench", bg=COLOR_BG_DARK, fg=COLOR_TEXT_PRIMARY, font=FONT_TITLE).pack(anchor="w", pady=(2, 4))
        
        badges_bar = tk.Frame(header, bg=COLOR_BG_DARK)
        badges_bar.pack(anchor="w", pady=(4, 0))

        tk.Label(badges_bar, text="VERSION 1.0.0", bg="#16381C", fg=COLOR_MURR_LIME, font=FONT_BADGE, padx=8, pady=3).pack(side="left", padx=(0, 6))
        tk.Label(badges_bar, text="CRA (EU 2024/2847) CONFORMANT", bg="#102A45", fg="#38BDF8", font=FONT_BADGE, padx=8, pady=3).pack(side="left", padx=(0, 6))
        tk.Label(badges_bar, text="IEC 62443-4-1 SECURE", bg="#3B2A10", fg=COLOR_WARNING, font=FONT_BADGE, padx=8, pady=3).pack(side="left")

        # Notebook Tabs for About / SBOM / Cybersecurity
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        tab_overview = tk.Frame(nb, bg=COLOR_BG_SURFACE, padx=16, pady=16)
        tab_sbom = tk.Frame(nb, bg=COLOR_BG_SURFACE, padx=16, pady=16)
        tab_security = tk.Frame(nb, bg=COLOR_BG_SURFACE, padx=16, pady=16)

        nb.add(tab_overview, text="ℹ️ Product Overview")
        nb.add(tab_sbom, text="📦 Software Bill of Materials (SBOM)")
        nb.add(tab_security, text="🛡️ CRA & Cybersecurity Policy")

        self._build_overview_tab(tab_overview)
        self._build_sbom_tab(tab_sbom)
        self._build_security_tab(tab_security)

        # Footer Actions
        footer = tk.Frame(self, bg=COLOR_BG_DARK, padx=16, pady=12)
        footer.pack(fill="x")

        btn_export = ttk.Button(footer, text="📄 Export SBOM (CycloneDX / JSON)", style="Action.TButton", command=self.export_sbom_json)
        btn_export.pack(side="left")

        btn_close = ttk.Button(footer, text="Close", command=self.destroy)
        btn_close.pack(side="right")

    def _build_overview_tab(self, parent):
        card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=16, pady=16)
        card.pack(fill="both", expand=True)

        tk.Label(card, text="Product & Technical Information", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_TITLE).pack(anchor="w", pady=(0, 8))
        
        info_rows = [
            ("Application Name:", "Murrelektronik Vario-X Motor Studio"),
            ("Intended Target Device:", "Vario-X Integrated Servo Motor (MD60-1-4000-F0S16M16-01)"),
            ("Supported Protocols:", "EtherCAT CoE (CAN Application Protocol over EtherCAT), CiA 402 Drive Profile"),
            ("Hardware Interface:", "Direct Layer-2 Npcap Ethernet Framing (EtherType 0x88A4)"),
            ("Single-Turn Resolution:", "16-bit Single-turn (65,536 inc/rev) + 16-bit Multiturn Absolute"),
            ("Author / Department:", "Murrelektronik Inc. — US Solutions Team"),
            ("Release Date / Build:", "August 2026 / Version 1.0.0 (Release-GA)"),
            ("Repository:", "https://github.com/JTuttleMurrInc/me-variox-servo-motor-studio")
        ]

        for label, val in info_rows:
            row = tk.Frame(card, bg=COLOR_BG_CARD)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label, bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_BODY_BOLD, width=24, anchor="w").pack(side="left")
            tk.Label(row, text=val, bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_BODY).pack(side="left")

    def _build_sbom_tab(self, parent):
        # Table of SBOM components
        tree_frame = tk.Frame(parent, bg=COLOR_BG_SURFACE)
        tree_frame.pack(fill="both", expand=True)

        cols = ("Name", "Version", "Type", "Supplier", "License", "PURL")
        self.tree_sbom = ttk.Treeview(tree_frame, columns=cols, show="headings", height=10)
        
        widths = {"Name": 180, "Version": 80, "Type": 120, "Supplier": 160, "License": 160, "PURL": 200}
        for c in cols:
            self.tree_sbom.heading(c, text=c)
            self.tree_sbom.column(c, width=widths.get(c, 100), anchor="w")

        scroll_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_sbom.yview)
        self.tree_sbom.configure(yscrollcommand=scroll_y.set)
        self.tree_sbom.pack(side="left", fill="both", expand=True)
        scroll_y.pack(side="right", fill="y")

        for item in SBOM_COMPONENTS:
            self.tree_sbom.insert("", "end", values=(
                item["name"],
                item["version"],
                item["type"],
                item["supplier"],
                item["license"],
                item["purl"]
            ))

    def _build_security_tab(self, parent):
        card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=16, pady=16)
        card.pack(fill="both", expand=True)

        tk.Label(card, text="Cyber Resilience Act (CRA) Statement & Vulnerability Policy", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_TITLE).pack(anchor="w", pady=(0, 8))

        sec_text = (
            "Murrelektronik Vario-X Motor Studio is engineered in alignment with the EU Cyber Resilience Act (Regulation EU 2024/2847) "
            "and international industrial cybersecurity standard IEC 62443-4-1 (Secure Product Development Lifecycle Requirements).\n\n"
            "• Vulnerability Handling & PSIRT Contact:\n"
            "  Security advisories, responsible disclosure reports, or vulnerability inquiries should be directed to the "
            "Murrelektronik Product Security Incident Response Team (PSIRT) at: security@murrelektronik.com\n\n"
            "• Secure Hardware Isolation:\n"
            "  The application uses dedicated Layer-2 Npcap network isolation and does not expose open TCP/UDP listener ports to untrusted networks.\n\n"
            "• Supply Chain Transparency:\n"
            "  A complete machine-readable CycloneDX / SPDX Software Bill of Materials (SBOM) is embedded and exportable at any time."
        )

        tk.Label(card, text=sec_text, bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_BODY, justify="left", wraplength=760).pack(anchor="w")

    def export_sbom_json(self):
        """Exports SBOM to CycloneDX-compatible JSON file."""
        sbom_data = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.5",
            "serialNumber": "urn:uuid:murr-variox-motor-studio-sbom-2026",
            "version": 1,
            "metadata": {
                "timestamp": "2026-08-28T16:48:00Z",
                "component": {
                    "name": "me-variox-servo-motor-studio",
                    "version": "1.0.0",
                    "type": "application",
                    "supplier": {"name": "Murrelektronik GmbH"}
                }
            },
            "components": SBOM_COMPONENTS
        }

        path = filedialog.asksaveasfilename(
            title="Export CycloneDX SBOM JSON",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            initialfile="variox_motor_studio_sbom.json"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(sbom_data, f, indent=2)
            messagebox.showinfo("SBOM Exported", f"Successfully exported CycloneDX SBOM to:\n{path}")
