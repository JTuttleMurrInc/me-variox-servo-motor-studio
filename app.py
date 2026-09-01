"""
Vario-X Motor Studio — Main Application Entry Point & GUI Controller.
Murrelektronik Vario-X Servo Motor Diagnostic, Tuning, Motion & Optical LED Ring Studio.
"""

import sys
import os
import time
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Dict

from core.esi_parser import EsiParser
from core.simulation import VirtualMotorDrive, VirtualMultiAxisDrive
from core.ecat_master import EthercatMaster, SlaveInfo
from core.motor_device import (
    MotorTelemetry, Cia402State, OperationMode,
    CMD_SHUTDOWN, CMD_SWITCH_ON, CMD_ENABLE_OPERATION, CMD_DISABLE_VOLTAGE,
    CMD_QUICK_STOP, CMD_FAULT_RESET
)
from core.led_ring import LedRingConfig

from gui.theme import (
    setup_ttk_styles, COLOR_BG_DARK, COLOR_BG_SURFACE, COLOR_BG_CARD,
    COLOR_BG_INPUT, COLOR_BG_ACCENT, COLOR_TEXT_PRIMARY, COLOR_TEXT_MUTED,
    COLOR_MURR_GREEN, COLOR_MURR_LIME, COLOR_WARNING, COLOR_DANGER,
    FONT_TITLE, FONT_SECTION, FONT_SUBTITLE, FONT_BODY, FONT_BODY_BOLD,
    FONT_MONO, FONT_MONO_BOLD, FONT_BADGE
)

from gui.tabs.dashboard_tab import DashboardTab
from gui.tabs.led_studio_tab import LedStudioTab
from gui.tabs.motion_tab import MotionTab
from gui.tabs.tuning_tab import TuningTab
from gui.tabs.sdo_explorer_tab import SdoExplorerTab
from gui.tabs.diagnostics_tab import DiagnosticsTab
from gui.components.about_dialog import AboutDialog

class VarioXMotorStudioApp:
    """Root Application Controller."""

    def __init__(self, root: tk.Tk, default_sim: bool = True, adapter_name: Optional[str] = None):
        self.root = root
        self.root.title("Murrelektronik Vario-X Motor Studio — Multi-Axis EtherCAT Diagnostic & Motion Workbench")
        self.root.geometry("1320x860")
        self.root.minsize(1080, 720)
        self.root.configure(bg=COLOR_BG_DARK)

        setup_ttk_styles(self.root)
        self._setup_window_icon()

        # Core Engines
        self.esi_parser = EsiParser()
        self.esi_parser.load_default()

        self.virtual_multi = VirtualMultiAxisDrive()
        self.virtual_motor = self.virtual_multi.get_motor(0x1000)
        self.ecat_master = EthercatMaster()

        self.is_simulation = default_sim
        self.is_hardware_connected = False
        self.current_telemetry: Optional[MotorTelemetry] = None
        self._last_pos_log = None
        self._log_tick_cnt = 0

        # Connect callbacks
        self.ecat_master.on_log = self.log

        # Top Bar
        self._build_app_bar()

        # Tab Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        # Instantiate Tabs
        self.tab_dashboard = DashboardTab(self.notebook, self)
        self.tab_led_studio = LedStudioTab(self.notebook, self)
        self.tab_motion = MotionTab(self.notebook, self)
        self.tab_tuning = TuningTab(self.notebook, self)
        self.tab_sdo = SdoExplorerTab(self.notebook, self)
        self.tab_diag = DiagnosticsTab(self.notebook, self)

        self.notebook.add(self.tab_dashboard, text="  Telemetry Dashboard  ")
        self.notebook.add(self.tab_led_studio, text="  LED Color Ring Studio  ")
        self.notebook.add(self.tab_motion, text="  CiA 402 Motion Control  ")
        self.notebook.add(self.tab_tuning, text="  Servo Tuning & Kinematics  ")
        self.notebook.add(self.tab_sdo, text="  SDO Object Explorer  ")
        self.notebook.add(self.tab_diag, text="  Master & Bus Diagnostics  ")

        # Initial Log Message
        self.log("Vario-X Motor Studio initialized.")
        if self.esi_parser.device_info:
            self.log(f"ESI Loaded: {self.esi_parser.device_info.name} ({len(self.esi_parser.device_info.objects)} objects)")
        else:
            self.log("Warning: ESI XML file not found; running with default object definitions.")

        if adapter_name and not default_sim:
            ok = self.connect_hardware(adapter_name)
            if ok:
                self.scan_slaves()
                # Ensure all motors start in safe Shutdown state (0x0006)
                self.send_controlword(CMD_SHUTDOWN)
                # Start live cyclic telemetry polling
                self.ecat_master.start_cyclic_pdo(0.04)

        # Start Telemetry & Animation Loop (30 ms timer ~ 33 Hz)
        self._schedule_telemetry_tick()

    def _setup_window_icon(self):
        icon_ico = os.path.abspath(os.path.join(os.path.dirname(__file__), "assets", "app_icon.ico"))
        icon_png = os.path.abspath(os.path.join(os.path.dirname(__file__), "assets", "app_icon.png"))
        
        if os.path.exists(icon_ico):
            try:
                self.root.iconbitmap(default=icon_ico)
            except Exception:
                pass
        
        if os.path.exists(icon_png):
            try:
                img = tk.PhotoImage(file=icon_png)
                self.root.iconphoto(True, img)
                self._app_icon_ref = img
            except Exception:
                pass

    def _build_app_bar(self):
        bar = tk.Frame(self.root, bg=COLOR_BG_SURFACE, height=54, padx=16, pady=6)
        bar.pack(fill="x", side="top", pady=(0, 6))

        # Brand Logo / Label (Left)
        brand_frame = tk.Frame(bar, bg=COLOR_BG_SURFACE)
        brand_frame.pack(side="left", fill="y")

        logo_path = os.path.join(os.path.dirname(__file__), "assets", "murr_logo.png")
        if os.path.exists(logo_path):
            try:
                self._logo_img = tk.PhotoImage(file=logo_path)
                lbl_logo = tk.Label(brand_frame, image=self._logo_img, bg=COLOR_BG_SURFACE)
                lbl_logo.pack(side="left", padx=(0, 10))
            except Exception:
                lbl_brand = tk.Label(brand_frame, text="MURRELEKTRONIK", bg=COLOR_BG_SURFACE, fg=COLOR_MURR_LIME, font=FONT_TITLE)
                lbl_brand.pack(side="left", padx=(0, 10))
        else:
            lbl_brand = tk.Label(brand_frame, text="MURRELEKTRONIK", bg=COLOR_BG_SURFACE, fg=COLOR_MURR_LIME, font=FONT_TITLE)
            lbl_brand.pack(side="left", padx=(0, 10))

        lbl_sep = tk.Label(brand_frame, text="|", bg=COLOR_BG_SURFACE, fg=COLOR_TEXT_MUTED, font=FONT_SECTION)
        lbl_sep.pack(side="left", padx=(0, 10))

        lbl_app_title = tk.Label(brand_frame, text="Vario-X Motor Studio", bg=COLOR_BG_SURFACE, fg=COLOR_TEXT_PRIMARY, font=FONT_SECTION)
        lbl_app_title.pack(side="left")

        # Mode Indicator & Controls (Right)
        ctrl_frame = tk.Frame(bar, bg=COLOR_BG_SURFACE)
        ctrl_frame.pack(side="right", fill="y")

        self.lbl_mode_badge = tk.Label(
            ctrl_frame,
            text="● VIRTUAL SIMULATION" if self.is_simulation else "● LIVE ETHERCAT",
            bg="#16381C" if not self.is_simulation else "#1C3833",
            fg=COLOR_MURR_LIME if not self.is_simulation else "#38BDF8",
            font=FONT_BADGE,
            padx=10, pady=4
        )
        self.lbl_mode_badge.pack(side="left", padx=(0, 12))

        self.btn_toggle_mode = ttk.Button(
            ctrl_frame,
            text="Switch to Live Hardware" if self.is_simulation else "Switch to Simulation",
            style="Action.TButton",
            command=self.toggle_mode
        )
        self.btn_toggle_mode.pack(side="left", padx=(0, 8))

        btn_about = ttk.Button(
            ctrl_frame,
            text="About",
            style="Action.TButton",
            command=self.show_about
        )
        btn_about.pack(side="left")

    def show_about(self):
        AboutDialog(self.root)

    def toggle_mode(self):
        if self.is_simulation:
            adapters = self.ecat_master.raw.list_adapters()
            if not adapters:
                messagebox.showwarning(
                    "No Network Adapters",
                    "No Npcap / WinPcap adapters found.\nMake sure Npcap is installed in WinPcap API-compatible mode."
                )
                return

            target_adapter = None
            for a in adapters:
                if any(kw in a.description for kw in ['I219', 'Ethernet Connection', 'Intel(R) Ethernet', 'Realtek']):
                    target_adapter = a.name
                    break
            
            if not target_adapter and adapters:
                target_adapter = adapters[0].name

            if target_adapter:
                ok = self.connect_hardware(target_adapter)
                if ok:
                    self.scan_slaves()
                    self.send_controlword(CMD_SHUTDOWN)
                    self.ecat_master.start_cyclic_pdo(0.04)
                    self.is_simulation = False
                    self.lbl_mode_badge.config(text="● LIVE ETHERCAT", bg="#16381C", fg=COLOR_MURR_LIME)
                    self.btn_toggle_mode.config(text="Switch to Simulation")
                    self.log("Switched to Live EtherCAT Hardware Mode.")
        else:
            self.ecat_master.close()
            self.is_simulation = True
            self.lbl_mode_badge.config(text="● VIRTUAL SIMULATION", bg="#1C3833", fg="#38BDF8")
            self.btn_toggle_mode.config(text="Switch to Live Hardware")
            self.log("Switched to Virtual Motor Simulation.")

    def connect_hardware(self, adapter_name: str) -> bool:
        ok = self.ecat_master.open(adapter_name)
        if ok:
            self.is_hardware_connected = True
            self.is_simulation = False
            self.lbl_mode_badge.config(text="● LIVE ETHERCAT", bg="#16381C", fg=COLOR_MURR_LIME)
            self.btn_toggle_mode.config(text="Switch to Simulation")
            self.log(f"Connected to live adapter: {adapter_name}")
        else:
            self.log(f"Failed connecting to adapter {adapter_name}")
        return ok

    def scan_slaves(self):
        slaves = self.ecat_master.scan_slaves()
        if hasattr(self, 'tab_diag'):
            self.tab_diag.refresh_slaves(slaves)
        if hasattr(self, 'tab_sdo'):
            self.tab_sdo.refresh_slaves(slaves)
        if hasattr(self, 'tab_dashboard'):
            count = len(slaves)
            self.tab_dashboard.lbl_axes_count.config(text=f"DUAL ACTIVE AXES ({count} SLAVES FOUND)")

    # =========================================================================
    # MULTI-AXIS CONTROLWORD & SDO DISPATCH
    # =========================================================================

    def send_controlword(self, cw: int):
        """Broadcasts controlword to all active axes."""
        if self.is_simulation:
            self.virtual_multi.set_controlword_all(cw)
        else:
            for slave in self.ecat_master.slaves:
                self.send_controlword_slave(slave.configured_addr, cw)

    def send_controlword_slave(self, station_addr: int, cw: int):
        """Sends controlword to a specific slave station."""
        if self.is_simulation:
            self.virtual_multi.set_controlword(station_addr, cw)
        else:
            err = self.ecat_master.sdo_download(station_addr, 0x6040, 0x00, cw.to_bytes(2, 'little'))
            if err:
                self.log(f"Error sending Controlword 0x{cw:04X} to 0x{station_addr:04X}: {err}")
            else:
                self.log(f"Sent Controlword 0x{cw:04X} to 0x{station_addr:04X}")

    def sdo_read(self, index: int, sub_index: int):
        """Single-axis fallback: reads from 0x1000."""
        return self.sdo_read_slave(0x1000, index, sub_index)

    def sdo_read_slave(self, station_addr: int, index: int, sub_index: int):
        if self.is_simulation:
            return self.virtual_multi.sdo_read(station_addr, index, sub_index)
        else:
            return self.ecat_master.sdo_upload(station_addr, index, sub_index)

    def sdo_write(self, index: int, sub_index: int, data: bytes):
        """Single-axis fallback: writes to 0x1000."""
        return self.sdo_write_slave(0x1000, index, sub_index, data)

    def sdo_write_slave(self, station_addr: int, index: int, sub_index: int, data: bytes):
        if self.is_simulation:
            return self.virtual_multi.sdo_write(station_addr, index, sub_index, data)
        else:
            return self.ecat_master.sdo_download(station_addr, index, sub_index, data)

    def apply_led_config(self, cfg: LedRingConfig, station_addr: Optional[int] = None):
        """Applies LED configuration to specified slave, or broadcasts to all slaves if station_addr is None."""
        dword = cfg.to_dword()
        targets = [station_addr] if station_addr else ([s.configured_addr for s in self.ecat_master.slaves] if not self.is_simulation else [0x1000, 0x1001])
        
        for addr in targets:
            self.sdo_write_slave(addr, 0x2FEF, 0x01, dword.to_bytes(4, 'little'))
            if not self.is_simulation and addr in self.ecat_master.telemetry_by_addr:
                self.ecat_master.telemetry_by_addr[addr].led_ctrl_dword = dword
                self.ecat_master.telemetry_by_addr[addr].led_config = cfg
        
        self.log(f"Applied LED_CTRL: 0x{dword:08X} ({cfg.description}) to {len(targets)} axis/axes.")

    def action_enable_drive(self):
        if hasattr(self, 'tab_motion') and not self.tab_motion.safety_acknowledged:
            self.tab_motion._require_safety_acknowledgment(self._do_enable_drive)
        else:
            self._do_enable_drive()

    def _do_enable_drive(self):
        # Broadcast enable to all connected axes
        for s in (self.ecat_master.slaves if not self.is_simulation else [type('S', (), {'configured_addr': 0x1000}), type('S', (), {'configured_addr': 0x1001})]):
            addr = s.configured_addr
            self.sdo_write_slave(addr, 0x6060, 0x00, (3).to_bytes(1, 'little', signed=True))
            self.sdo_write_slave(addr, 0x6081, 0x00, (1092266).to_bytes(4, 'little'))
            self.sdo_write_slave(addr, 0x6083, 0x00, (150000).to_bytes(4, 'little'))
            self.sdo_write_slave(addr, 0x6084, 0x00, (150000).to_bytes(4, 'little'))
            
            self.send_controlword_slave(addr, CMD_SHUTDOWN)
            time.sleep(0.015)
            self.send_controlword_slave(addr, CMD_SWITCH_ON)
            time.sleep(0.015)
            self.send_controlword_slave(addr, CMD_ENABLE_OPERATION)
        self.log("Dispatched Drive Enable sequence across all active axes.")

    def action_disable_drive(self):
        self.send_controlword(CMD_DISABLE_VOLTAGE)
        self.log("All Axes Voltage Disabled (0x0000).")

    def action_quick_stop(self):
        self.send_controlword(CMD_QUICK_STOP)
        self.log("Quick Stop Executed on All Axes (0x0002).")

    def action_fault_reset(self):
        self.send_controlword(CMD_FAULT_RESET)
        self.log("Fault Reset Edge Sent to All Axes (0x0080).")

    def log(self, msg: str):
        timestamp = time.strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {msg}"
        print(formatted)
        if hasattr(self, 'tab_diag'):
            self.tab_diag.log_message(formatted)

    def _schedule_telemetry_tick(self):
        self._telemetry_tick()
        self.root.after(30, self._schedule_telemetry_tick)

    def _telemetry_tick(self):
        # Sample Multi-Axis telemetry
        if self.is_simulation:
            t_dict = self.virtual_multi.get_telemetry_dict()
        else:
            t_dict = self.ecat_master.telemetry_by_addr

        t1 = t_dict.get(0x1000)
        t2 = t_dict.get(0x1001)

        # Log status to terminal every ~500ms
        if not self.is_simulation and t1:
            self._log_tick_cnt += 1
            if self._log_tick_cnt % 15 == 0:
                p1 = t1.position_actual
                p2 = t2.position_actual if t2 else 0
                v1 = t1.velocity_rpm
                v2 = t2.velocity_rpm if t2 else 0
                bus1 = t1.dc_bus_voltage_v
                print(f"[{time.strftime('%H:%M:%S')}] [LIVE-DUAL] M1 (0x1000): {p1:>8,d} inc ({v1:>4d} RPM) | M2 (0x1001): {p2:>8,d} inc ({v2:>4d} RPM) | Bus: {bus1:.1f}V | State: {t1.cia_state.value}")

        # Update tabs
        self.tab_dashboard.update_multi_telemetry(t_dict)
        self.tab_motion.update_multi_telemetry(t_dict)
        self.tab_led_studio.update_animation()

def main():
    use_live = ("--live" in sys.argv)
    adapter = None

    if use_live:
        from core.ecat_raw import RawEthercatMaster
        raw = RawEthercatMaster()
        adapters = raw.list_adapters()
        for a in adapters:
            if any(kw in a.description for kw in ['I219', 'Ethernet Connection', 'Intel(R) Ethernet', 'Realtek']):
                adapter = a.name
                break
        if not adapter and adapters:
            adapter = adapters[0].name

    root = tk.Tk()
    app = VarioXMotorStudioApp(root, default_sim=not use_live, adapter_name=adapter)
    root.mainloop()

if __name__ == "__main__":
    main()
