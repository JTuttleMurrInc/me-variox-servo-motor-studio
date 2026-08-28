"""
Automated Screen Capture Utility for Vario-X Motor Studio Documentation.
Uses native Windows PrintWindow API to cleanly capture all 5 tabs in high definition.
"""

import os
import time
import struct
import ctypes
from ctypes import wintypes
import tkinter as tk
from PIL import Image

from app import VarioXMotorStudioApp
from core.motor_device import OperationMode
from core.led_ring import RING_PRESETS

OUT_DIR = os.path.abspath("docs/screenshots")
os.makedirs(OUT_DIR, exist_ok=True)

def capture_hwnd(hwnd):
    """Captures a Windows HWND cleanly into a PIL Image."""
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top

    hwnd_dc = user32.GetWindowDC(hwnd)
    mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
    bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, w, h)
    gdi32.SelectObject(mem_dc, bitmap)

    # 2 = PW_RENDERFULLCONTENT (captures DirectComposition & Tkinter Canvas smoothly)
    user32.PrintWindow(hwnd, mem_dc, 2)

    header = struct.pack('<IiiHHIIIIII', 40, w, -h, 1, 32, 0, w * h * 4, 0, 0, 0, 0)
    buf = bytearray(w * h * 4)
    gdi32.GetDIBits(mem_dc, bitmap, 0, h, (ctypes.c_char * len(buf)).from_buffer(buf), ctypes.c_char_p(header), 0)

    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(hwnd, hwnd_dc)

    img = Image.frombuffer('RGBA', (w, h), bytes(buf), 'raw', 'BGRA', 0, 1)
    # Convert RGBA to RGB for clean markdown display
    return img.convert('RGB')

def capture_all_tabs():
    root = tk.Tk()
    app = VarioXMotorStudioApp(root, default_sim=True)
    
    # Standard 1280x820 resolution
    root.geometry("1280x820+50+50")
    root.update()
    
    # 1. Start virtual motor motion so telemetry gauges & oscilloscope are active
    app.action_enable_drive()
    app.virtual_motor.mode_display = OperationMode.PROFILE_VELOCITY
    app.virtual_motor.target_velocity = 1500.0
    
    # Populate simulation samples
    for _ in range(60):
        app._telemetry_tick()
        root.update()
        time.sleep(0.02)

    hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()

    tabs = [
        (0, "01_telemetry_dashboard.png", "Telemetry Dashboard"),
        (1, "02_led_ring_studio.png", "LED Color Ring Studio"),
        (2, "03_cia402_motion.png", "CiA 402 Motion Control"),
        (3, "04_sdo_explorer.png", "SDO Object Explorer"),
        (4, "05_bus_diagnostics.png", "Master & Bus Diagnostics")
    ]

    print("Capturing high-resolution screenshots for all tabs...")

    for tab_idx, filename, tab_name in tabs:
        app.notebook.select(tab_idx)
        
        # Set specific active state for tab
        if tab_idx == 1:
            app.tab_led_studio.load_preset(RING_PRESETS["Police Emergency (Red Left / Green Right Strobe)"])
            app.tab_led_studio.apply_to_motor()
        elif tab_idx == 2:
            app.tab_motion.var_speed.set(1500.0)
            app.tab_motion.var_pos.set(65536)
        
        for _ in range(15):
            app._telemetry_tick()
            root.update()
            time.sleep(0.02)
        
        img = capture_hwnd(hwnd)
        save_path = os.path.join(OUT_DIR, filename)
        img.save(save_path, "PNG")
        print(f"  [OK] Captured: {tab_name} ({img.size[0]}x{img.size[1]}) -> {filename}")

    root.destroy()
    print("All screenshots generated successfully in docs/screenshots/!")

if __name__ == "__main__":
    capture_all_tabs()
