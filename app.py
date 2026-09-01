"""
Main Application Entry Point for Vario-X Motor Studio.
"""

import sys
import os
import time
import argparse
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Tuple, Dict, Any

# Windows Taskbar custom icon hook
if sys.platform == "win32":
    try:
        import ctypes
        APP_USER_MODEL_ID = "murrelektronik.variox.motorstudio.v1"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass

from core.esi_parser import EsiParser
from core.simulation import VirtualMotorDrive
from core.motor_device import (
    MotorTelemetry, Cia402State,
    CMD_SHUTDOWN, CMD_SWITCH_ON, CMD_ENABLE_OPERATION, CMD_DISABLE_VOLTAGE, CMD_QUICK_STOP, CMD_FAULT_RESET
)
from core.ecat_raw import RawEthercatMaster
from core.ecat_master import EthercatMaster, SlaveInfo
from core.led_ring import LedRingConfig

from gui.theme import (
    setup_ttk_styles, COLOR_BG_DARK, COLOR_BG_CARD, COLOR_BG_ACCENT,
    COLOR_TEXT_PRIMARY, COLOR_MURR_LIME, FONT_APP_TITLE, FONT_BADGE, FONT_BODY_BOLD
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
        self.root.title("Murrelektronik Vario-X Motor Studio — EtherCAT Diagnostic & LED Ring Workbench")
        self.root.geometry("1280x820")
        self.root.minsize(1050, 700)
        self.root.configure(bg=COLOR_BG_DARK)

        setup_ttk_styles(self.root)
        self._setup_window_icon()

        # Core Engines
        self.esi_parser = EsiParser()
        self.esi_parser.load_default()

        self.virtual_motor = VirtualMotorDrive()
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
                # Start live cyclic telemetry polling
                self.ecat_master.start_cyclic_pdo(0.04)

        # Start Telemetry & Animation Loop (30 ms timer ~ 33 Hz)
        self._schedule_telemetry_tick()

    def _setup_window_icon(self):
        icon_ico = os.path.abspath(os.path.join(os.path.dirname(__file__), "assets", "app_icon.ico"))
        icon_png = os.path.abspath(os.path.join(os.path.dirname(__file__), "assets", "app_icon.png"))
        
        # 1. Native Windows Icon Bitmap (Sets taskbar + titlebar)
        if os.path.exists(icon_ico):
            try:
                self.root.iconbitmap(default=icon_ico)
            except Exception:
                try:
                    self.root.wm_iconbitmap(icon_ico)
                except Exception:
                    pass
        
        # 2. Modern High-DPI iconphoto
        if os.path.exists(icon_png):
            try:
                from PIL import ImageTk, Image
                pil_img = Image.open(icon_png)
                self._app_icon_img = ImageTk.PhotoImage(pil_img)
                self.root.iconphoto(True, self._app_icon_img)
            except Exception:
                pass

    def _build_app_bar(self):
        bar = tk.Frame(self.root, bg=COLOR_BG_DARK, padx=16, pady=10)
        bar.pack(fill="x")

        title_frame = tk.Frame(bar, bg=COLOR_BG_DARK)
        title_frame.pack(side="left")

        # Official Murrelektronik Vector Logo in header
        logo_png = os.path.abspath(os.path.join(os.path.dirname(__file__), "assets", "murr_logo.png"))
        if os.path.exists(logo_png):
            try:
                from PIL import Image, ImageTk
                im = Image.open(logo_png)
                h_target = 22
                w_target = int(im.width * (h_target / float(im.height)))
                im_resized = im.resize((w_target, h_target), Image.Resampling.LANCZOS)
                self._header_logo_img = ImageTk.PhotoImage(im_resized)
                self.lbl_logo = tk.Label(title_frame, image=self._header_logo_img, bg=COLOR_BG_DARK, bd=0, highlightthickness=0)
                self.lbl_logo.pack(side="left", padx=(0, 10))
            except Exception:
                tk.Label(title_frame, text="MURRELEKTRONIK", bg=COLOR_BG_DARK, fg=COLOR_MURR_LIME, font=(FONT_APP_TITLE[0], 15, "bold")).pack(side="left", padx=(0, 10))
        else:
            tk.Label(title_frame, text="MURRELEKTRONIK", bg=COLOR_BG_DARK, fg=COLOR_MURR_LIME, font=(FONT_APP_TITLE[0], 15, "bold")).pack(side="left", padx=(0, 10))

        tk.Label(title_frame, text="|  Vario-X Motor Studio (EtherCAT CoE / CiA 402)", bg=COLOR_BG_DARK, fg=COLOR_TEXT_PRIMARY, font=FONT_APP_TITLE).pack(side="left")

        # Right Action Frame
        right_frame = tk.Frame(bar, bg=COLOR_BG_DARK)
        right_frame.pack(side="right")

        # About / CRA Compliance Button
        self.btn_about = tk.Button(
            right_frame, text="ℹ️ About", bg=COLOR_BG_CARD, fg=COLOR_TEXT_PRIMARY,
            activebackground=COLOR_BG_ACCENT, activeforeground=COLOR_MURR_LIME,
            font=FONT_BODY_BOLD, padx=12, pady=3, relief="flat",
            highlightbackground=COLOR_BG_ACCENT, highlightthickness=1,
            command=self.show_about_dialog
        )
        self.btn_about.pack(side="left", padx=(0, 12))

        # Mode Badge on right
        self.lbl_top_mode = tk.Label(
            right_frame, text="SIMULATION MODE", bg="#16381C", fg=COLOR_MURR_LIME,
            font=FONT_BADGE, padx=12, pady=4
        )
        self.lbl_top_mode.pack(side="left")

    def show_about_dialog(self):
        AboutDialog(self.root)

    def set_simulation_mode(self, is_sim: bool):
        self.is_simulation = is_sim
        if is_sim:
            self.lbl_top_mode.config(text="SIMULATION MODE", bg="#16381C", fg=COLOR_MURR_LIME)
            self.tab_dashboard.lbl_bus_status.config(text="Bus: SIMULATION MODE | Slave 0x1000")
            self.log("Switched to Virtual Motor Simulation.")
        else:
            self.lbl_top_mode.config(text="LIVE HARDWARE MODE", bg="#123B44", fg="#38BDF8")
            self.tab_dashboard.lbl_bus_status.config(text="Bus: LIVE ETHERCAT (Npcap)")
            self.log("Switched to Live EtherCAT Hardware Mode.")

    def connect_hardware(self, adapter_name: str) -> bool:
        ok = self.ecat_master.open(adapter_name)
        self.is_hardware_connected = ok
        if ok:
            self.set_simulation_mode(False)
            self.log(f"Connected to live adapter: {adapter_name}")
            if hasattr(self, 'tab_diag'):
                self.tab_diag.var_sim_mode.set(False)
                self.tab_diag.lbl_link_status.config(text="STATUS: LIVE ETHERCAT CONNECTED", bg="#16381C", fg=COLOR_MURR_LIME)
                self.tab_diag.btn_connect.config(text="Disconnect")
        return ok

    def disconnect_hardware(self):
        self.ecat_master.close()
        self.is_hardware_connected = False
        self.set_simulation_mode(True)
        if hasattr(self, 'tab_diag'):
            self.tab_diag.var_sim_mode.set(True)
            self.tab_diag.lbl_link_status.config(text="STATUS: SIMULATION ACTIVE", bg="#16381C", fg=COLOR_MURR_LIME)
            self.tab_diag.btn_connect.config(text="Connect Live Bus")
        self.log("Disconnected from live hardware. Simulation activated.")

    def scan_slaves(self):
        if self.is_simulation:
            return [self.virtual_motor]
        slaves = self.ecat_master.scan_slaves()
        if hasattr(self, 'tab_diag'):
            self.tab_diag.update_slave_list()
        return slaves

    def set_al_state(self, target_state: int) -> bool:
        if self.is_simulation:
            return True
        if self.ecat_master.slaves:
            addr = self.ecat_master.slaves[0].configured_addr
            return self.ecat_master.set_state(addr, target_state)
        return False

    def send_controlword(self, cw: int):
        if self.is_simulation:
            self.virtual_motor.set_controlword(cw)
        else:
            if self.ecat_master.slaves:
                addr = self.ecat_master.slaves[0].configured_addr
                err = self.ecat_master.sdo_download(addr, 0x6040, 0x00, cw.to_bytes(2, 'little'))
                if err:
                    self.log(f"Error sending Controlword 0x{cw:04X}: {err}")
                else:
                    self.log(f"Sent Controlword: 0x{cw:04X}")

    def sdo_read(self, index: int, sub_index: int) -> Tuple[Optional[bytes], Optional[str]]:
        if self.is_simulation:
            if index == 0x2FEF and sub_index == 0x01:
                return self.virtual_motor.led_ctrl_dword.to_bytes(4, 'little'), None
            elif index == 0x2FEF and sub_index == 0x02:
                return self.virtual_motor.led_status_dword.to_bytes(4, 'little'), None
            elif index == 0x6064:
                return self.virtual_motor.position_actual.to_bytes(4, 'little', signed=True), None
            elif index == 0x6041:
                return self.virtual_motor.statusword.to_bytes(2, 'little'), None
            return bytes([0, 0, 0, 0]), None
        else:
            if not self.ecat_master.slaves:
                return None, "No EtherCAT slaves found on bus"
            addr = self.ecat_master.slaves[0].configured_addr
            return self.ecat_master.sdo_upload(addr, index, sub_index)

    def sdo_write(self, index: int, sub_index: int, data: bytes) -> Optional[str]:
        if self.is_simulation:
            if index == 0x2FEF and sub_index == 0x01:
                val = int.from_bytes(data, 'little')
                self.virtual_motor.set_led_ctrl(val)
            elif index == 0x6040:
                val = int.from_bytes(data, 'little')
                self.virtual_motor.set_controlword(val)
            return None
        else:
            if not self.ecat_master.slaves:
                return "No EtherCAT slaves found on bus"
            addr = self.ecat_master.slaves[0].configured_addr
            err = self.ecat_master.sdo_download(addr, index, sub_index, data)
            if not err and index == 0x2FEF and sub_index == 0x01 and len(data) >= 4:
                dword = int.from_bytes(data[:4], 'little')
                self.ecat_master.live_telemetry.led_ctrl_dword = dword
                self.ecat_master.live_telemetry.led_config = LedRingConfig.from_dword(dword)
            return err

    def apply_led_config(self, cfg: LedRingConfig):
        dword = cfg.to_dword()
        err = self.sdo_write(0x2FEF, 0x01, dword.to_bytes(4, 'little'))
        if err:
            self.log(f"Error applying LED_CTRL (0x2FEF:01): {err}")
            messagebox.showerror("SDO Write Failed", f"Error setting LED_CTRL (0x2FEF:01):\n{err}")
        else:
            self.log(f"Applied LED_CTRL: 0x{dword:08X} ({cfg.description})")
            if not self.is_simulation:
                self.ecat_master.live_telemetry.led_ctrl_dword = dword
                self.ecat_master.live_telemetry.led_config = cfg

    def action_enable_drive(self):
        self.send_controlword(CMD_SHUTDOWN)
        self.root.after(40, lambda: self.send_controlword(CMD_SWITCH_ON))
        self.root.after(80, lambda: self.send_controlword(CMD_ENABLE_OPERATION))
        self.log("Initiated Drive Enable Sequence (0x06 -> 0x07 -> 0x0F).")

    def action_disable_drive(self):
        self.send_controlword(CMD_DISABLE_VOLTAGE)
        self.log("Drive Voltage Disabled (0x0000).")

    def action_quick_stop(self):
        self.send_controlword(CMD_QUICK_STOP)
        self.log("Quick Stop Executed (0x0002).")

    def action_fault_reset(self):
        self.send_controlword(CMD_FAULT_RESET)
        self.log("Fault Reset Edge Sent (0x0080).")

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
        # Sample telemetry
        if self.is_simulation:
            t = self.virtual_motor.get_telemetry()
        else:
            t = self.ecat_master.live_telemetry

        self.current_telemetry = t

        # Log status to terminal every ~500ms
        if not self.is_simulation:
            self._log_tick_cnt += 1
            if self._log_tick_cnt % 15 == 0:
                self._last_pos_log = t.position_actual
                sto_str = "OK (A+B HIGH)" if not t.sto_active else ("TRIPPED" if not t.sto_info else t.sto_info.error_code_hex)
                print(f"[{time.strftime('%H:%M:%S')}] [LIVE-FEEDBACK] Pos: {t.position_actual:>10,d} inc | {t.position_actual/65536.0:>6.2f} rev | Speed: {t.velocity_rpm} RPM | Bus: {t.dc_bus_voltage_v:.1f}V | STO: {sto_str} | State: {t.cia_state.value}")

        # Update tabs
        self.tab_dashboard.update_telemetry(t)
        self.tab_led_studio.update_animation()
        self.tab_motion.update_telemetry(t)

        # Sync Dashboard optical ring preview to live LED config
        if not self.is_simulation and t.led_config:
            self.tab_dashboard.ring_widget.set_config(t.led_config)

def main():
    parser = argparse.ArgumentParser(description="Murrelektronik Vario-X Motor Studio")
    parser.add_argument("--sim", action="store_true", default=True, help="Start in Virtual Simulation Mode (default: True)")
    parser.add_argument("--live", action="store_true", help="Start in Live Hardware Mode")
    parser.add_argument("--adapter", type=str, default=None, help="Npcap Adapter Name")
    args = parser.parse_args()

    default_sim = True
    adapter_name = args.adapter
    if args.live:
        default_sim = False
        if not adapter_name:
            adapters = RawEthercatMaster.list_adapters()
            for a in adapters:
                if any(kw in a.description for kw in ["I219", "Ethernet Connection", "Intel(R) Ethernet"]):
                    adapter_name = a.name
                    break
            if not adapter_name and adapters:
                adapter_name = adapters[0].name

    root = tk.Tk()
    app = VarioXMotorStudioApp(root, default_sim=default_sim, adapter_name=adapter_name)
    
    def on_closing():
        app.virtual_motor.stop()
        if app.is_hardware_connected:
            app.disconnect_hardware()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
