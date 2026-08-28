"""
Interactive Live Diagnostic & Test Workbench for Vario-X Motor Demo.
Allows step-by-step interactive testing of LED Ring, Live Shaft Position, and CiA 402 states.
"""

import os
import sys
import time
import struct
from typing import Optional, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.ecat_raw import (
    RawEthercatMaster,
    REG_TYPE_REV, REG_STATION_ADDR, REG_AL_CONTROL, REG_AL_STATUS, REG_AL_STATUS_CODE,
    REG_SM0_CONFIG, REG_SM1_CONFIG, AL_STATE_INIT, AL_STATE_PREOP, AL_STATE_SAFEOP, AL_STATE_OP,
    AL_STATE_NAMES
)

class LiveMotorWorkbench:
    def __init__(self, adapter_name: Optional[str] = None):
        if not adapter_name:
            adapters = RawEthercatMaster.list_adapters()
            for a in adapters:
                if any(k in a.description for k in ["I219", "Ethernet Connection", "Intel(R) Ethernet"]):
                    adapter_name = a.name
                    break
            if not adapter_name and adapters:
                adapter_name = adapters[0].name

        self.adapter_name = adapter_name
        self.raw = RawEthercatMaster(adapter_name)
        self.mbx_cnt = 0
        self.station_addr = 0x1000

    def connect(self) -> bool:
        if not self.raw.open():
            print(f"[ERROR] Could not open network adapter: {self.adapter_name}")
            return False
        
        print(f"[OK] Opened Adapter: {self.adapter_name}")
        
        data, count = self.raw.brd(REG_TYPE_REV, 2)
        if count == 0:
            print("[ERROR] No EtherCAT slaves responded on broadcast read (BRD).")
            print("        Please check Ethernet cable and 24V logic power.")
            return False
        
        print(f"[OK] Found {count} slave(s) on bus.")
        self.init_slave()
        return True

    def init_slave(self):
        print(f"\n[*] Initializing Slave at Station 0x{self.station_addr:04X}...")
        self.raw.apwr(0, REG_STATION_ADDR, struct.pack('<H', self.station_addr))
        
        # 1. Reset to INIT
        self.raw.fpwr(self.station_addr, REG_AL_CONTROL, struct.pack('<H', AL_STATE_INIT))
        time.sleep(0.02)

        # 2. Configure Standard Mailbox SyncManagers
        sm0_cfg = struct.pack('<HHBBBB', 0x1000, 128, 0x26, 0x00, 0x01, 0x00)
        sm1_cfg = struct.pack('<HHBBBB', 0x1400, 128, 0x22, 0x00, 0x01, 0x00)
        self.raw.fpwr(self.station_addr, REG_SM0_CONFIG, sm0_cfg)
        self.raw.fpwr(self.station_addr, REG_SM1_CONFIG, sm1_cfg)

        # 3. Request PRE-OP
        self.raw.fpwr(self.station_addr, REG_AL_CONTROL, struct.pack('<H', AL_STATE_PREOP))
        time.sleep(0.05)

        al_data, _ = self.raw.fprd(self.station_addr, REG_AL_STATUS, 2)
        st = al_data[0] & 0x0F if al_data else 0
        print(f"[OK] Slave State: {AL_STATE_NAMES.get(st, 'Unknown')} (0x{st:02X})")

    def sdo_exec(self, index: int, sub: int, write_data: bytes = None) -> Tuple[Optional[bytes], Optional[str]]:
        self.mbx_cnt = (self.mbx_cnt % 7) + 1

        coe_hdr = struct.pack('<H', (0x02 << 12))
        if write_data is None:
            sdo_req = bytes([0x40]) + struct.pack('<H', index) + bytes([sub]) + b'\x00\x00\x00\x00'
        else:
            n = max(0, 4 - len(write_data))
            cs = 0x20 | 0x02 | 0x01 | ((n & 0x03) << 2)
            padded = write_data[:4] + (b'\x00' * (4 - len(write_data[:4])))
            sdo_req = bytes([cs]) + struct.pack('<H', index) + bytes([sub]) + padded

        payload = coe_hdr + sdo_req
        type_and_cnt = (self.mbx_cnt << 4) | 0x03
        mbx_hdr = struct.pack('<HHBB', len(payload), 0x0000, 0x00, type_and_cnt)
        full_mbx = mbx_hdr + payload
        full_mbx += b'\x00' * (128 - len(full_mbx))

        # Send Request with write retry
        w = 0
        for _ in range(8):
            w = self.raw.fpwr(self.station_addr, 0x1000, full_mbx)
            if w > 0:
                break
            time.sleep(0.005)

        # Allow motor MCU 20ms to process frame
        time.sleep(0.02)
        resp, rw = self.raw.fprd(self.station_addr, 0x1400, 128)
        if rw > 0 and len(resp) >= 12:
            sdo_cs = resp[8]
            if sdo_cs == 0x80:
                abort = struct.unpack('<I', resp[12:16])[0] if len(resp) >= 16 else 0
                return None, f"SDO Abort: 0x{abort:08X}"
            elif (sdo_cs & 0xE0) == 0x40:
                n_bytes = 4 - ((sdo_cs >> 2) & 0x03) if (sdo_cs & 0x02) else 4
                return resp[12:12+n_bytes], None
            elif (sdo_cs & 0xE0) == 0x60:
                return b"", None

        return None, "Timeout"

    def set_led(self, dword_val: int, desc: str = ""):
        print(f"\n[*] Applying LED_CTRL = 0x{dword_val:08X} ({desc})...")
        t0 = time.perf_counter()
        _, err = self.sdo_exec(0x2FEF, 0x01, dword_val.to_bytes(4, 'little'))
        dt = (time.perf_counter() - t0) * 1000
        if not err:
            print(f"[OK] LED_CTRL written successfully in {dt:.1f}ms! (Look at physical motor ring)")
        else:
            print(f"[ERROR] LED_CTRL write failed: {err}")

    def monitor_position_live(self, duration_s: float = 20.0):
        print(f"\n=======================================================")
        print(f" LIVE POSITION FEEDBACK MONITOR ({duration_s:.0f} SECONDS)")
        print(f" >>> ROTATE THE MOTOR SHAFT BY HAND NOW <<<")
        print(f"=======================================================")
        start_t = time.time()
        sample = 0
        last_pos = None

        while time.time() - start_t < duration_s:
            sample += 1
            t0 = time.perf_counter()
            d, err = self.sdo_exec(0x6064, 0x00)
            dt = (time.perf_counter() - t0) * 1000

            if d and len(d) >= 4:
                pos = struct.unpack('<i', d[:4])[0]
                delta = (pos - last_pos) if last_pos is not None else 0
                last_pos = pos
                revs = pos / 65536.0
                turn_inc = pos % 65536
                if turn_inc < 0: turn_inc += 65536
                deg = (turn_inc / 65536.0) * 360.0

                print(f"[{dt:4.1f}ms] Sample #{sample:3d} | Pos: {pos:>10,d} inc | {revs:>7.2f} rev | {deg:>5.1f}° | Delta: {delta:>+6d}")
            else:
                print(f"[{dt:4.1f}ms] Sample #{sample:3d} | Read Error: {err}")
            
            time.sleep(0.04)

    def read_all_telemetry(self):
        print("\n=======================================================")
        print(" FULL MOTOR TELEMETRY SNAPSHOT")
        print("=======================================================")
        items = [
            (0x1000, 0, "<I", "Device Type (0x1000)"),
            (0x6041, 0, "<H", "CiA 402 Statusword (0x6041)"),
            (0x6064, 0, "<i", "Position Actual Value (0x6064)"),
            (0x606C, 0, "<i", "Velocity Actual Value (0x606C)"),
            (0x6077, 0, "<h", "Torque Actual Value (0x6077)"),
            (0x6079, 0, "<I", "DC Bus Voltage (0x6079) [mV]"),
            (0x60F7, 0x17, "<H", "STO Status (0x60F7:17)"),
            (0x60F7, 0x11, "<h", "Temperature (0x60F7:11) [0.1°C]"),
            (0x2FEF, 1, "<I", "LED Control (0x2FEF:01)"),
        ]

        for idx, sub, fmt, name in items:
            d, err = self.sdo_exec(idx, sub)
            if d:
                sz = struct.calcsize(fmt)
                val = struct.unpack(fmt, d[:sz])[0]
                if "Voltage" in name:
                    val_str = f"{val} mV ({val/1000.0:.2f} V)"
                elif "Temperature" in name:
                    val_str = f"{val/10.0:.1f} °C"
                elif "Statusword" in name:
                    val_str = f"0x{val:04X}"
                elif "LED" in name:
                    val_str = f"0x{val:08X}"
                else:
                    val_str = f"{val:,}"
                print(f"  {name:<36}: {val_str}")
            else:
                print(f"  {name:<36}: [ERROR: {err}]")
            time.sleep(0.02)

    def interactive_menu(self):
        while True:
            print("\n=======================================================")
            print(" VARIO-X MOTOR LIVE INTERACTIVE WORKBENCH")
            print("=======================================================")
            print(" [1] Stream Live Position Feedback (Turn shaft by hand)")
            print(" [2] Take Full Telemetry Snapshot (Voltage, STO, Position, Speed)")
            print(" [3] Test LED: Solid RED (0x80110000)")
            print(" [4] Test LED: Solid GREEN (0x80000011)")
            print(" [5] Test LED: Solid YELLOW (0x80001100)")
            print(" [6] Test LED: Red/Green Split (Left Red, Right Green: 0x80100001)")
            print(" [7] Test LED: Fast Strobe White / Emergency (0x80888888)")
            print(" [8] Test LED: Reset to Auto Firmware Driver Mode (0x00000000)")
            print(" [9] Re-initialize Bus (INIT -> PRE-OP)")
            print(" [0] Exit")
            print("-------------------------------------------------------")
            
            try:
                choice = input("Select an option [0-9]: ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if choice == "1":
                self.monitor_position_live(duration_s=20.0)
            elif choice == "2":
                self.read_all_telemetry()
            elif choice == "3":
                self.set_led(0x80110000, "User Mode: Solid RED")
            elif choice == "4":
                self.set_led(0x80000011, "User Mode: Solid GREEN")
            elif choice == "5":
                self.set_led(0x80001100, "User Mode: Solid YELLOW")
            elif choice == "6":
                self.set_led(0x80100001, "User Mode: Left Red / Right Green")
            elif choice == "7":
                self.set_led(0x80888888, "User Mode: Fast Strobe")
            elif choice == "8":
                self.set_led(0x00000000, "Auto Firmware Driver Mode")
            elif choice == "9":
                self.init_slave()
            elif choice == "0":
                break

        self.raw.close()
        print("\n[OK] EtherCAT connection closed. Goodbye!")

if __name__ == "__main__":
    wb = LiveMotorWorkbench()
    if wb.connect():
        wb.interactive_menu()
