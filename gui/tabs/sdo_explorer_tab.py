"""
CoE SDO Object Dictionary Explorer Tab.
Parses and displays all objects from ESI XML with multi-axis target selection, inline SDO Read and Write.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Optional, List

from core.esi_parser import EsiParser, EsiObject, EsiSubItem
from gui.theme import (
    COLOR_BG_SURFACE, COLOR_BG_CARD, COLOR_BG_INPUT, COLOR_BG_ACCENT,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_MUTED, COLOR_MURR_LIME, COLOR_MURR_GREEN,
    COLOR_WARNING, COLOR_DANGER, FONT_TITLE, FONT_SECTION, FONT_SUBTITLE,
    FONT_BODY, FONT_BODY_BOLD, FONT_MONO, FONT_MONO_BOLD, FONT_BADGE
)

class SdoExplorerTab(tk.Frame):
    """Searchable Object Dictionary tree with multi-slave SDO Upload/Download."""

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COLOR_BG_SURFACE, padx=16, pady=16, **kwargs)
        self.app = app
        self.parser = app.esi_parser

        # Variables
        self.var_search = tk.StringVar()
        self.var_write_val = tk.StringVar()
        self.var_sdo_station = tk.StringVar(value="0x1000")
        self.selected_item = None # (index, subindex, dtype, access)

        # Top Search Bar
        self._build_search_bar()

        # Content: Left Treeview (2/3 width), Right Inspector (1/3 width)
        content = tk.Frame(self, bg=COLOR_BG_SURFACE)
        content.pack(fill="both", expand=True, pady=(12, 0))

        left_frame = tk.Frame(content, bg=COLOR_BG_SURFACE)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 16))
        self._build_tree(left_frame)

        right_frame = tk.Frame(content, bg=COLOR_BG_SURFACE, width=360)
        right_frame.pack(side="left", fill="y")
        self._build_inspector(right_frame)

        # Populate initial tree
        self.refresh_tree()

    def _build_search_bar(self):
        bar = tk.Frame(self, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=14, pady=10)
        bar.pack(fill="x")

        # Target Slave Selector
        tk.Label(bar, text="TARGET SLAVE:", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_BODY_BOLD).pack(side="left", padx=(0, 6))
        self.combo_sdo_station = ttk.Combobox(bar, textvariable=self.var_sdo_station, values=["0x1000", "0x1001"], state="readonly", width=8, font=FONT_BODY_BOLD)
        self.combo_sdo_station.pack(side="left", padx=(0, 14))

        tk.Label(bar, text="SEARCH:", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_BODY_BOLD).pack(side="left", padx=(0, 8))
        
        entry = ttk.Entry(bar, textvariable=self.var_search, font=FONT_BODY, width=28)
        entry.pack(side="left", padx=(0, 8))
        entry.bind("<KeyRelease>", lambda e: self.refresh_tree())

        ttk.Button(bar, text="Clear", style="Action.TButton", command=lambda: (self.var_search.set(""), self.refresh_tree())).pack(side="left", padx=(0, 12))

        # Stats
        total_objs = len(self.parser.device_info.objects) if self.parser.device_info else 0
        self.lbl_stats = tk.Label(
            bar, text=f"Total Objects Loaded: {total_objs} (ESI XML)",
            bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_SUBTITLE
        )
        self.lbl_stats.pack(side="right")

    def refresh_slaves(self, slaves):
        if slaves:
            vals = [f"0x{s.configured_addr:04X}" for s in slaves]
            self.combo_sdo_station.config(values=vals)
            if self.var_sdo_station.get() not in vals:
                self.var_sdo_station.set(vals[0])

    def _build_tree(self, parent):
        tree_card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1)
        tree_card.pack(fill="both", expand=True)

        columns = ("index", "sub", "name", "type", "access", "value")
        self.tree = ttk.Treeview(tree_card, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("index", text="Index", anchor="w")
        self.tree.heading("sub", text="Sub", anchor="center")
        self.tree.heading("name", text="Object Name", anchor="w")
        self.tree.heading("type", text="Data Type", anchor="w")
        self.tree.heading("access", text="Access", anchor="center")
        self.tree.heading("value", text="Value (Hex / Dec)", anchor="w")

        self.tree.column("index", width=80, stretch=False)
        self.tree.column("sub", width=50, stretch=False, anchor="center")
        self.tree.column("name", width=260, stretch=True)
        self.tree.column("type", width=90, stretch=False)
        self.tree.column("access", width=65, stretch=False, anchor="center")
        self.tree.column("value", width=160, stretch=True)

        # Scrollbar
        sb = ttk.Scrollbar(tree_card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)

        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.tree.bind("<<TreeviewSelect>>", self._on_select_item)

    def _build_inspector(self, parent):
        card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=14, pady=14)
        card.pack(fill="both", expand=True)

        tk.Label(card, text="SDO OBJECT INSPECTOR", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_TITLE).pack(anchor="w")
        
        # Details Box
        self.lbl_selected_title = tk.Label(card, text="Select an object from the list", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_SECTION, wraplength=280, justify="left")
        self.lbl_selected_title.pack(anchor="w", pady=(8, 4))

        self.lbl_meta = tk.Label(card, text="", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_MONO, justify="left")
        self.lbl_meta.pack(anchor="w", pady=(0, 10))

        ttk.Separator(card, orient="horizontal").pack(fill="x", pady=8)

        # Read Action
        tk.Label(card, text="SDO UPLOAD (READ)", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_SECTION).pack(anchor="w", pady=(4, 4))
        
        self.lbl_live_val = tk.Label(card, text="Value: --", bg=COLOR_BG_INPUT, fg=COLOR_MURR_LIME, font=FONT_MONO_BOLD, padx=8, pady=6)
        self.lbl_live_val.pack(fill="x", pady=(0, 6))

        self.btn_read = ttk.Button(card, text="🔄 Read from Selected Motor", style="Action.TButton", command=self.read_selected, state="disabled")
        self.btn_read.pack(fill="x", pady=(0, 12))

        ttk.Separator(card, orient="horizontal").pack(fill="x", pady=8)

        # Write Action
        tk.Label(card, text="SDO DOWNLOAD (WRITE)", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_SECTION).pack(anchor="w", pady=(4, 4))
        
        write_box = tk.Frame(card, bg=COLOR_BG_CARD)
        write_box.pack(fill="x", pady=(0, 6))

        tk.Label(write_box, text="New Value:", bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, font=FONT_SUBTITLE).pack(side="left", padx=(0, 6))
        self.entry_write = ttk.Entry(write_box, textvariable=self.var_write_val, font=FONT_MONO)
        self.entry_write.pack(side="left", fill="x", expand=True)

        self.btn_write = ttk.Button(card, text="💾 Write to Selected Motor", style="Murr.TButton", command=self.write_selected, state="disabled")
        self.btn_write.pack(fill="x")

    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        if not self.parser.device_info:
            return

        query = self.var_search.get().lower().strip()

        for obj in self.parser.device_info.objects.values():
            # Filter check
            idx_hex = f"0x{obj.index:04X}".lower()
            name_low = obj.name.lower()

            if query and (query not in idx_hex and query not in name_low):
                # Check subitems
                match_sub = any(query in s.name.lower() or query in s.data_type.lower() for s in obj.sub_items.values())
                if not match_sub:
                    continue

            if not obj.sub_items:
                # Single item object
                vals = (f"0x{obj.index:04X}", "0x00", obj.name, obj.data_type, "RW", "--")
                self.tree.insert("", "end", iid=f"{obj.index:04X}:00", values=vals)
            else:
                for sub in obj.sub_items.values():
                    access = "RW" if "w" in sub.access.lower() else "RO"
                    vals = (f"0x{obj.index:04X}", f"0x{sub.sub_index:02X}", f"  ↳ {sub.name}", sub.data_type, access, "--")
                    self.tree.insert("", "end", iid=f"{obj.index:04X}:{sub.sub_index:02X}", values=vals)

    def _on_select_item(self, event):
        sel = self.tree.selection()
        if not sel:
            return

        iid = sel[0]
        parts = iid.split(":")
        idx = int(parts[0], 16)
        sub = int(parts[1], 16)

        obj = self.parser.get_object(idx)
        if not obj:
            return

        subitem = obj.sub_items.get(sub)
        name = subitem.name if subitem else obj.name
        dtype = subitem.data_type if subitem else obj.data_type
        access = subitem.access if subitem else "rw"

        self.selected_item = (idx, sub, dtype, access)

        self.lbl_selected_title.config(text=f"0x{idx:04X}:{sub:02X} — {name}")
        self.lbl_meta.config(text=f"Data Type: {dtype} | Access: {access.upper()}")
        self.lbl_live_val.config(text="Value: --")

        self.btn_read.config(state="normal")
        can_write = ("w" in access.lower()) or ("write" in access.lower())
        self.btn_write.config(state="normal" if can_write else "disabled")

    def read_selected(self):
        if not self.selected_item:
            return
        idx, sub, dtype, _ = self.selected_item
        addr = int(self.var_sdo_station.get(), 16)

        data, err = self.app.sdo_read_slave(addr, idx, sub)
        if err:
            self.lbl_live_val.config(text=f"Error: {err}")
            self.app.log(f"SDO Read Error 0x{idx:04X}:{sub:02X} on 0x{addr:04X}: {err}")
        elif data:
            hex_str = "0x" + data[::-1].hex().upper() if len(data) <= 4 else data.hex()
            dec_val = int.from_bytes(data, 'little', signed=("int" in dtype.lower() and not "uint" in dtype.lower()))
            disp = f"{hex_str} ({dec_val})"
            self.lbl_live_val.config(text=disp)
            self.var_write_val.set(str(dec_val))
            
            # Update in tree
            iid = f"{idx:04X}:{sub:02X}"
            if self.tree.exists(iid):
                curr = list(self.tree.item(iid, "values"))
                curr[5] = disp
                self.tree.item(iid, values=curr)
            
            self.app.log(f"SDO Read 0x{idx:04X}:{sub:02X} from 0x{addr:04X} = {disp}")

    def write_selected(self):
        if not self.selected_item:
            return
        idx, sub, dtype, _ = self.selected_item
        val_str = self.var_write_val.get().strip()
        addr = int(self.var_sdo_station.get(), 16)

        try:
            val = int(val_str, 16) if (val_str.startswith("0x") or val_str.startswith("0X")) else int(val_str)
        except ValueError:
            messagebox.showerror("Invalid Value", f"Could not parse '{val_str}' as an integer.")
            return

        # Determine byte size from dtype
        size = 4
        if "8" in dtype: size = 1
        elif "16" in dtype: size = 2
        elif "32" in dtype: size = 4
        elif "64" in dtype: size = 8

        signed = ("int" in dtype.lower() and not "uint" in dtype.lower())
        data = val.to_bytes(size, 'little', signed=signed)

        err = self.app.sdo_write_slave(addr, idx, sub, data)
        if err:
            self.app.log(f"SDO Write Error 0x{idx:04X}:{sub:02X} on 0x{addr:04X}: {err}")
            messagebox.showerror("Write Error", f"SDO Download Failed:\n{err}")
        else:
            self.app.log(f"SDO Write 0x{idx:04X}:{sub:02X} on 0x{addr:04X} = {val} ({data.hex()})")
            # Automatically read back to confirm
            self.read_selected()
