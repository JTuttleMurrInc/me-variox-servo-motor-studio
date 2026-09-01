"""
High-Fidelity Virtual Vario-X Motor Drive Simulation Engine.
Enables full offline GUI operation, multi-axis simulation, motion profile physics,
CiA 402 state machine transitions, LED Ring status synthesis, and CoE SDO/PDO emulation without physical hardware.
"""

import time
import math
import threading
from typing import Dict, Tuple, List, Optional, Callable

from core.motor_device import (
    Cia402State, OperationMode, MotorTelemetry, decode_cia402_state,
    CMD_SHUTDOWN, CMD_SWITCH_ON, CMD_ENABLE_OPERATION, CMD_DISABLE_VOLTAGE,
    CMD_QUICK_STOP, CMD_FAULT_RESET
)
from core.led_ring import LedRingConfig

class VirtualMotorDrive:
    """Single Virtual EtherCAT Servo Motor Drive."""

    def __init__(self, station_addr: int = 0x1000):
        self.station_addr = station_addr
        self._lock = threading.Lock()
        
        # CiA 402 Registers
        self.controlword = 0x0000
        self.statusword = 0x0240 # Switch on disabled (Voltage enabled)
        self.mode_set = OperationMode.PROFILE_VELOCITY
        self.mode_display = OperationMode.PROFILE_VELOCITY
        
        # Motion State
        self.position_actual = 0.0
        self.target_position = 0.0
        self.velocity_actual = 0.0
        self.target_velocity = 0.0
        self.max_velocity = 4000.0 # RPM
        self.acceleration = 2500.0 # RPM/s
        self.deceleration = 2500.0 # RPM/s
        self.torque_actual = 0.0
        self.target_torque = 0.0
        self.following_error = 0.0

        # Physical / Diagnostic State
        self.dc_bus_nominal_mv = 45500
        self.dc_bus_mv = 45500
        self.temperature_c = 28.5
        self.sto_active = False
        self.error_code = 0x0000

        # 0x2FEF LED Ring
        self.led_ctrl_dword = 0x00000000 # Automatic driver mode
        self.led_status_dword = 0x000000DB # Green pulse default

        # Object Dictionary Store (index -> {subindex -> bytes})
        self.sdo_store: Dict[int, Dict[int, bytes]] = {}
        self._init_sdo_store()

        # Background Simulation Loop
        self._running = True
        self._last_tick = time.perf_counter()
        self._thread = threading.Thread(target=self._sim_loop, daemon=True)
        self._thread.start()

    def _init_sdo_store(self):
        # Identity
        self._set_sdo_raw(0x1000, 0x00, (0x00020192).to_bytes(4, 'little')) # CiA 402 Servo Drive
        self._set_sdo_raw(0x1018, 0x01, (0x000005D5).to_bytes(4, 'little')) # Vendor Murrelektronik
        self._set_sdo_raw(0x1018, 0x02, (0x00010000).to_bytes(4, 'little')) # Product Code
        self._set_sdo_raw(0x1018, 0x03, (0x00010001).to_bytes(4, 'little')) # Revision
        
        # CiA 402 Core
        self._set_sdo_u16(0x6040, 0x00, self.controlword)
        self._set_sdo_u16(0x6041, 0x00, self.statusword)
        self._set_sdo_i8(0x6060, 0x00, self.mode_set)
        self._set_sdo_i8(0x6061, 0x00, self.mode_display)
        self._set_sdo_i32(0x6064, 0x00, 0)
        self._set_sdo_i32(0x606C, 0x00, 0)
        self._set_sdo_i16(0x6077, 0x00, 0)
        self._set_sdo_i32(0x607A, 0x00, 0)
        self._set_sdo_i32(0x60FF, 0x00, 0)
        self._set_sdo_u32(0x6079, 0x00, self.dc_bus_mv)
        self._set_sdo_u16(0x603F, 0x00, self.error_code)

        # Profile Kinematics
        self._set_sdo_u32(0x6081, 0x00, 1092266) # 1000 RPM
        self._set_sdo_u32(0x6083, 0x00, 200000)
        self._set_sdo_u32(0x6084, 0x00, 200000)

        # LED Ring 0x2FEF
        self._set_sdo_u32(0x2FEF, 0x01, self.led_ctrl_dword)
        self._set_sdo_u32(0x2FEF, 0x02, self.led_status_dword)

        # Diagnostics 0x60F7
        self._set_sdo_u16(0x60F7, 0x11, 0) # STO Safe
        self._set_sdo_u16(0x60F7, 0x12, int(self.temperature_c))

    def _set_sdo_raw(self, idx: int, sub: int, data: bytes):
        if idx not in self.sdo_store:
            self.sdo_store[idx] = {}
        self.sdo_store[idx][sub] = data

    def _set_sdo_u16(self, idx: int, sub: int, val: int):
        self._set_sdo_raw(idx, sub, int(val & 0xFFFF).to_bytes(2, 'little'))

    def _set_sdo_i16(self, idx: int, sub: int, val: int):
        self._set_sdo_raw(idx, sub, int(val).to_bytes(2, 'little', signed=True))

    def _set_sdo_u32(self, idx: int, sub: int, val: int):
        self._set_sdo_raw(idx, sub, int(val & 0xFFFFFFFF).to_bytes(4, 'little'))

    def _set_sdo_i32(self, idx: int, sub: int, val: int):
        self._set_sdo_raw(idx, sub, int(val).to_bytes(4, 'little', signed=True))

    def _set_sdo_i8(self, idx: int, sub: int, val: int):
        self._set_sdo_raw(idx, sub, int(val).to_bytes(1, 'little', signed=True))

    def sdo_read(self, idx: int, sub: int) -> Tuple[Optional[bytes], Optional[str]]:
        with self._lock:
            if idx in self.sdo_store and sub in self.sdo_store[idx]:
                return self.sdo_store[idx][sub], None
            return None, f"Object 0x{idx:04X}:{sub:02X} not found in virtual SDO store"

    def sdo_write(self, idx: int, sub: int, data: bytes) -> Optional[str]:
        with self._lock:
            self._set_sdo_raw(idx, sub, data)
            
            # Handle standard CiA 402 register interactions
            if idx == 0x6040 and sub == 0x00 and len(data) >= 2:
                cw = int.from_bytes(data[:2], 'little')
                self._handle_controlword(cw)
            elif idx == 0x6060 and sub == 0x00:
                self.mode_set = int.from_bytes(data[:1], 'little', signed=True)
                self.mode_display = self.mode_set
                self._set_sdo_i8(0x6061, 0x00, self.mode_display)
            elif idx == 0x60FF and sub == 0x00 and len(data) >= 4:
                raw_val = int.from_bytes(data[:4], 'little', signed=True)
                if abs(raw_val) <= 6000:
                    self.target_velocity = float(raw_val)
                else:
                    self.target_velocity = (raw_val / 65536.0) * 60.0 # Convert inc/s to RPM
            elif idx == 0x607A and sub == 0x00 and len(data) >= 4:
                self.target_position = float(int.from_bytes(data[:4], 'little', signed=True))
            elif idx == 0x2FEF and sub == 0x01 and len(data) >= 4:
                self.led_ctrl_dword = int.from_bytes(data[:4], 'little')
                self.led_status_dword = self.led_ctrl_dword
                self._set_sdo_u32(0x2FEF, 0x01, self.led_ctrl_dword)
                self._set_sdo_u32(0x2FEF, 0x02, self.led_status_dword)
            return None

    def write_sdo(self, idx: int, sub: int, data: bytes) -> Optional[str]:
        return self.sdo_write(idx, sub, data)

    def read_sdo(self, idx: int, sub: int) -> Tuple[Optional[bytes], Optional[str]]:
        return self.sdo_read(idx, sub)

    def _handle_controlword(self, cw: int):
        self.controlword = cw
        self._set_sdo_u16(0x6040, 0x00, cw)
        
        # State transitions
        cmd = cw & 0x008F
        if cmd == 0x0006: # Shutdown
            self.statusword = (self.statusword & ~0x006F) | 0x0021 # Ready to switch on
        elif cmd == 0x0007: # Switch on
            self.statusword = (self.statusword & ~0x006F) | 0x0023 # Switched on
        elif cmd == 0x000F: # Enable operation
            self.statusword = (self.statusword & ~0x006F) | 0x0027 # Operation enabled
        elif (cw & 0x0080) == 0x0080: # Fault reset
            self.error_code = 0x0000
            self.statusword = (self.statusword & ~0x0008) | 0x0240 # Switch on disabled
        elif (cw & 0x0002) == 0x0000 and (cw & 0x0004) != 0: # Quick stop
            self.statusword = (self.statusword & ~0x006F) | 0x0007 # Quick stop active
            self.target_velocity = 0.0

        # Position setpoint trigger: bit 4 rising edge
        if (cw & (1 << 4)) and (self.mode_display == OperationMode.PROFILE_POSITION):
            if cw & (1 << 6): # Relative move
                self.position_actual += self.target_position
            self.statusword |= (1 << 12)

    def set_controlword(self, cw: int):
        self.sdo_write(0x6040, 0x00, cw.to_bytes(2, 'little'))

    def set_sto(self, active: bool):
        with self._lock:
            self.sto_active = active
            if active:
                self.statusword = (self.statusword & ~0x006F) | 0x0008 # Fault
                self._set_sdo_u16(0x60F7, 0x11, 6) # STO Tripped code
            else:
                self._set_sdo_u16(0x60F7, 0x11, 0)

    def set_led_ctrl(self, val: int):
        self.sdo_write(0x2FEF, 0x01, val.to_bytes(4, 'little'))

    def get_telemetry(self) -> MotorTelemetry:
        with self._lock:
            state = decode_cia402_state(self.statusword)
            cfg = LedRingConfig.from_dword(self.led_ctrl_dword) if self.led_ctrl_dword else None
            return MotorTelemetry(
                timestamp=time.time(),
                statusword=self.statusword,
                controlword=self.controlword,
                cia_state=state,
                mode_display=int(self.mode_display),
                mode_set=int(self.mode_set),
                position_actual=int(self.position_actual),
                velocity_actual=int(self.velocity_actual),
                torque_actual=int(self.torque_actual * 10),
                dc_bus_voltage_mv=self.dc_bus_mv,
                temperature_c=self.temperature_c,
                sto_code=6 if self.sto_active else 0,
                sto_active=self.sto_active,
                error_code=self.error_code,
                led_ctrl_dword=self.led_ctrl_dword,
                led_config=cfg
            )

    def _sim_loop(self):
        while self._running:
            now = time.perf_counter()
            dt = min(0.1, max(0.001, now - self._last_tick))
            self._last_tick = now

            with self._lock:
                is_enabled = (self.statusword & 0x006F) == 0x0027
                if is_enabled:
                    # Velocity loop simulation
                    if self.mode_display in (OperationMode.PROFILE_VELOCITY, OperationMode.RATED_SPEED, OperationMode.CSV):
                        diff = self.target_velocity - self.velocity_actual
                        if abs(diff) > 0.5:
                            rate = self.acceleration if diff > 0 else self.deceleration
                            delta_v = math.copysign(rate * dt, diff)
                            if abs(delta_v) >= abs(diff):
                                self.velocity_actual = self.target_velocity
                            else:
                                self.velocity_actual += delta_v
                            self.torque_actual = (delta_v / (self.acceleration * dt)) * 0.8
                        else:
                            self.velocity_actual = self.target_velocity
                            self.torque_actual = 0.05 * (self.velocity_actual / max(1.0, self.max_velocity))

                        # Integrate position: RPM -> rev/sec -> inc/sec
                        d_pos = (self.velocity_actual / 60.0) * 65536.0 * dt
                        self.position_actual += d_pos

                    elif self.mode_display == OperationMode.PROFILE_POSITION:
                        pos_diff = self.target_position - self.position_actual
                        if abs(pos_diff) > 5.0:
                            direction = 1.0 if pos_diff > 0 else -1.0
                            target_speed = min(self.max_velocity, math.sqrt(2.0 * self.acceleration * abs(pos_diff) / 100.0))
                            self.velocity_actual = direction * target_speed
                            step = (self.velocity_actual / 60.0) * 65536.0 * dt
                            if abs(step) >= abs(pos_diff):
                                self.position_actual = self.target_position
                                self.velocity_actual = 0.0
                                self.statusword |= (1 << 10)
                            else:
                                self.position_actual += step
                                self.statusword &= ~(1 << 10)
                        else:
                            self.velocity_actual = 0.0
                            self.statusword |= (1 << 10)

                else:
                    if abs(self.velocity_actual) > 1.0:
                        self.velocity_actual -= math.copysign(self.deceleration * dt, self.velocity_actual)
                    else:
                        self.velocity_actual = 0.0
                    self.torque_actual = 0.0

            time.sleep(0.02)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.5)

class VirtualMultiAxisDrive:
    """Manages multi-axis simulation for multiple slave stations (0x1000, 0x1001, etc.)."""

    def __init__(self):
        self.motors: Dict[int, VirtualMotorDrive] = {
            0x1000: VirtualMotorDrive(0x1000),
            0x1001: VirtualMotorDrive(0x1001)
        }

    def get_motor(self, addr: int = 0x1000) -> VirtualMotorDrive:
        if addr not in self.motors:
            self.motors[addr] = VirtualMotorDrive(addr)
        return self.motors[addr]

    def get_telemetry_dict(self) -> Dict[int, MotorTelemetry]:
        return {addr: m.get_telemetry() for addr, m in self.motors.items()}

    def sdo_read(self, station_addr: int, idx: int, sub: int) -> Tuple[Optional[bytes], Optional[str]]:
        return self.get_motor(station_addr).sdo_read(idx, sub)

    def sdo_write(self, station_addr: int, idx: int, sub: int, data: bytes) -> Optional[str]:
        return self.get_motor(station_addr).sdo_write(idx, sub, data)

    def set_controlword(self, station_addr: int, cw: int):
        self.get_motor(station_addr).set_controlword(cw)

    def sdo_download_simultaneous(self, writes: List[Tuple[int, int, int, bytes]]) -> bool:
        for addr, idx, sub, data in writes:
            self.get_motor(addr).sdo_write(idx, sub, data)
        return True

    def send_controlwords_simultaneous(self, cw_by_addr: Dict[int, int]) -> bool:
        for addr, cw in cw_by_addr.items():
            self.get_motor(addr).set_controlword(cw)
        return True

    def stop(self):
        for m in self.motors.values():
            m.stop()
