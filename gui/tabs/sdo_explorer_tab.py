"""
CoE SDO Object Dictionary Explorer Tab.
Parses and displays all objects from ESI XML with inline SDO Read and Write.
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
    """Searchable Object Dictionary tree with interactive SDO Upload/Download."""

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COLOR_BG_SURFACE, padx=16, pady=16, **kwargs)
        self.app = app
        self.parser = app.esi_parser

        # Variables
        self.var_search = tk.StringVar()
        self.var_write_val = tk.StringVar()
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

        tk.Label(bar, text="SEARCH OBJECT DICTIONARY:", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_BODY_BOLD).pack(side="left", padx=(0, 10))
        
        entry = ttk.Entry(bar, textvariable=self.var_search, font=FONT_BODY, width=32)
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

    def _build_tree(self, parent):
        tree_card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1)
        tree_card.pack(fill="both", expand=True)

        columns = ("index", "sub", "name", "type", "access", "live_val")
        self.tree = ttk.Treeview(tree_card, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("index", text="Index")
        self.tree.heading("sub", text="Sub")
        self.tree.heading("name", text="Object Name")
        self.tree.heading("type", text="Data Type")
        self.tree.heading("access", text="Access")
        self.tree.heading("live_val", text="Live Value")

        self.tree.column("index", width=80, anchor="center")
        self.tree.column("sub", width=50, anchor="center")
        self.tree.column("name", width=220, anchor="w")
        self.tree.column("type", width=80, anchor="center")
        self.tree.column("access", width=60, anchor="center")
        self.tree.column("live_val", width=140, anchor="w")

        scrollbar = ttk.Scrollbar(tree_card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", lambda e: self.read_selected_sdo())

    def _build_inspector(self, parent):
        card = tk.Frame(parent, bg=COLOR_BG_CARD, highlightbackground=COLOR_BG_ACCENT, highlightthickness=1, padx=16, pady=16)
        card.pack(fill="both", expand=True)

        tk.Label(card, text="SDO OBJECT INSPECTOR", bg=COLOR_BG_CARD, fg=COLOR_MURR_LIME, font=FONT_TITLE).pack(anchor="w", pady=(0, 10))

        # Details Box
        self.box_details = tk.Frame(card, bg=COLOR_BG_INPUT, padx=12, pady=10)
        self.box_details.pack(fill="x", pady=(0, 14))

        self.lbl_insp_title = tk.Label(self.box_details, text="Select an Object", bg=COLOR_BG_INPUT, fg=COLOR_TEXT_PRIMARY, font=FONT_MONO_BOLD)
        self.lbl_insp_title.pack(anchor="w")

        self.lbl_insp_info = tk.Label(
            self.box_details, text="Click an object in the dictionary to inspect, read, or write CoE SDO parameters.",
            bg=COLOR_BG_INPUT, fg=COLOR_TEXT_MUTED, font=FONT_SUBTITLE, justify="left"
        )
        self.lbl_insp_info.pack(anchor="w", pady=(4, 0))

        # Actions
        tk.Label(card, text="CoE Operations:", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_SECTION).pack(anchor="w", pady=(8, 4))

        # Read Button
        self.btn_read = ttk.Button(card, text="Read SDO (Upload)", style="Murr.TButton", command=self.read_selected_sdo)
        self.btn_read.pack(fill="x", pady=4)

        # Write Controls
        tk.Label(card, text="Write Value (Download):", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY, font=FONT_BODY_BOLD).pack(anchor="w", pady=(12, 4))
        
        w_box = tk.Frame(card, bg=COLOR_BG_CARD)
        w_box.pack(fill="x")
        self.entry_write = ttk.Entry(w_box, textvariable=self.var_write_val, font=FONT_MONO)
        self.entry_write.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.btn_write = ttk.Button(w_box, text="Write SDO", style="Action.TButton", command=self.write_selected_sdo)
        self.btn_write.pack(side="left")

    def refresh_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        if not self.parser.device_info:
            return

        query = self.var_search.get().strip().lower()

        for idx, obj in sorted(self.parser.device_info.objects.items()):
            # Check match
            match = (not query) or (query in obj.hex_index.lower()) or (query in obj.name.lower()) or (query in obj.category.lower())
            
            if not obj.sub_items:
                if match:
                    item_id = f"{obj.hex_index}:00"
                    self.tree.insert("", "end", iid=item_id, values=(
                        obj.hex_index, "0x00", obj.name, obj.data_type, obj.access, ""
                    ))
            else:
                for sub_idx, sub in sorted(obj.sub_items.items()):
                    sub_match = match or (query in sub.name.lower())
                    if sub_match:
                        item_id = f"{obj.hex_index}:{sub_idx:02X}"
                        self.tree.insert("", "end", iid=item_id, values=(
                            obj.hex_index, f"0x{sub_idx:02X}", sub.name, sub.data_type, sub.access, ""
                        ))

    def _on_tree_select(self, event):
        selected = self.tree.selection()
        if not selected:
            return
        item_id = selected[0]
        vals = self.tree.item(item_id, "values")
        if not vals:
            return

        idx_str, sub_str, name, dtype, access, live_val = vals
        idx = int(idx_str, 16)
        sub = int(sub_str, 16)

        self.selected_item = (idx, sub, dtype, access)
        self.lbl_insp_title.config(text=f"{idx_str}:{sub_str} - {name}")
        self.lbl_insp_info.config(
            text=f"Data Type: {dtype}\nAccess: {access.upper()}\nDefault: {live_val or 'N/A'}"
        )

    def read_selected_sdo(self):
        if not self.selected_item:
            return
        idx, sub, dtype, access = self.selected_item
        data, err = self.app.sdo_read(idx, sub)
        if err:
            messagebox.showerror("SDO Read Error", f"Failed reading 0x{idx:04X}:{sub:02X}:\n{err}")
        elif data is not None:
            val_str = self._format_data_bytes(data, dtype)
            item_id = f"0x{idx:04X}:{sub:02X}"
            if self.tree.exists(item_id):
                vals = list(self.tree.item(item_id, "values"))
                vals[5] = val_str
                self.tree.item(item_id, values=vals)
            self.lbl_insp_info.config(
                text=f"Data Type: {dtype}\nAccess: {access.upper()}\nLive Value: {val_str} (Hex: {data.hex()})"
            )
            self.app.log(f"SDO Read 0x{idx:04X}:{sub:02X} -> {val_str}")

    def write_selected_sdo(self):
        if not self.selected_item:
            return
        idx, sub, dtype, access = self.selected_item
        if "w" not in access.lower():
            messagebox.showwarning("Read Only", f"Object 0x{idx:04X}:{sub:02X} is marked Read Only ({access}).")
            return

        val_input = self.var_write_val.get().strip()
        data = self._parse_input_to_bytes(val_input, dtype)
        if data is None:
            messagebox.showerror("Invalid Value", f"Could not parse '{val_input}' for data type {dtype}.")
            return

        err = self.app.sdo_write(idx, sub, data)
        if err:
            messagebox.showerror("SDO Write Error", f"Failed writing 0x{idx:04X}:{sub:02X}:\n{err}")
        else:
            self.app.log(f"SDO Write 0x{idx:04X}:{sub:02X} = {val_input}")
            self.read_selected_sdo()

    def _format_data_bytes(self, data: bytes, dtype: str) -> str:
        d = dtype.upper()
        if "UINT" in d or "UDINT" in d or "USINT" in d:
            val = int.from_bytes(data, 'little', signed=False)
            return f"{val} (0x{val:X})"
        elif "INT" in d or "DINT" in d or "SINT" in d:
            val = int.from_bytes(data, 'little', signed=True)
            return f"{val}"
        elif "STRING" in d:
            return data.decode('utf-8', errors='ignore').rstrip('\x00')
        else:
            val = int.from_bytes(data, 'little', signed=False)
            return f"0x{val:X} ({data.hex()})"

    def _parse_input_to_bytes(self, input_str: str, dtype: str) -> Optional[bytes]:
        try:
            d = dtype.upper()
            val = int(input_str, 16) if (input_str.startswith("0x") or input_str.startswith("0X")) else int(input_str)
            
            if "USINT" in d or "UINT8" in d or d == "BYTE":
                return int(val & 0xFF).to_bytes(1, 'little', signed=False)
            elif "SINT" in d or "INT8" in d:
                return int(val).to_bytes(1, 'little', signed=True)
            elif "UINT" in d or "UINT16" in d or d == "WORD":
                return int(val & 0xFFFF).to_bytes(2, 'little', signed=False)
            elif "INT" in d or "INT16" in d:
                return int(val).to_bytes(2, 'little', signed=True)
            elif "UDINT" in d or "UINT32" in d or d == "DWORD":
                return int(val & 0xFFFFFFFF).to_bytes(4, 'little', signed=False)
            elif "DINT" in d or "INT32" in d:
                return int(val).to_bytes(4, 'little', signed=True)
            else:
                return int(val & 0xFFFFFFFF).to_bytes(4, 'little', signed=False)
        except Exception:
            return None
