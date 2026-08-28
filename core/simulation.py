"""
High-Fidelity Virtual Vario-X Motor Drive Simulation Engine.
Enables full offline GUI operation, motion profile physics, CiA 402 state machine transitions,
LED Ring status synthesis, and CoE SDO/PDO emulation without physical hardware.
"""

import time
import math
import threading
from typing import Dict, Tuple, Optional, Callable

from core.motor_device import (
    Cia402State, OperationMode, MotorTelemetry, decode_cia402_state,
    CMD_SHUTDOWN, CMD_SWITCH_ON, CMD_ENABLE_OPERATION, CMD_DISABLE_VOLTAGE,
    CMD_QUICK_STOP, CMD_FAULT_RESET
)
from core.led_ring import LedRingConfig

class VirtualMotorDrive:
    """Virtual EtherCAT Servo Motor Drive."""

    def __init__(self):
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
        self.max_velocity = 3000.0 # RPM
        self.acceleration = 1500.0 # RPM/s
        self.deceleration = 1500.0 # RPM/s
        self.torque_actual = 0.0
        self.target_torque = 0.0
        self.following_error = 0.0

        # Physical / Diagnostic State
        self.dc_bus_nominal_mv = 48000
        self.dc_bus_mv = 48000
        self.temperature_c = 28.5
        self.sto_active = False
        self.error_code = 0x0000

        # 0x2FEF LED Ring
        self.led_ctrl_dword = 0x00000000 # Automatic driver mode by default
        self.led_status_dword = 0x000000DB # Green pulse default in automatic

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

        # LED Ring 0x2FEF
        self._set_sdo_u32(0x2FEF, 0x01, self.led_ctrl_dword)
        self._set_sdo_u32(0x2FEF, 0x02, self.led_status_dword)

        # Diagnostics 0x60F7
        self._set_sdo_u16(0x60F7, 0x11, int(self.temperature_c * 10)) # 0.1 deg C
        self._set_sdo_u16(0x60F7, 0x17, 1 if self.sto_active else 0)

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

    def write_sdo(self, index: int, sub_index: int, data: bytes) -> Optional[str]:
        """SDO Download handler in simulator."""
        with self._lock:
            self._set_sdo_raw(index, sub_index, data)

            if index == 0x6040 and sub_index == 0:
                cw = int.from_bytes(data[:2], 'little')
                self._handle_controlword(cw)
            elif index == 0x6060 and sub_index == 0:
                mode = int.from_bytes(data[:1], 'little', signed=True)
                self.mode_set = OperationMode(mode)
                self.mode_display = self.mode_set
                self._set_sdo_i8(0x6061, 0x00, self.mode_display)
            elif index == 0x607A and sub_index == 0:
                self.target_position = float(int.from_bytes(data[:4], 'little', signed=True))
            elif index == 0x60FF and sub_index == 0:
                self.target_velocity = float(int.from_bytes(data[:4], 'little', signed=True))
            elif index == 0x6071 and sub_index == 0:
                self.target_torque = float(int.from_bytes(data[:2], 'little', signed=True))
            elif index == 0x2FEF and sub_index == 1:
                self.led_ctrl_dword = int.from_bytes(data[:4], 'little')
                self._update_led_status()

            return None

    def read_sdo(self, index: int, sub_index: int) -> Tuple[Optional[bytes], Optional[str]]:
        """SDO Upload handler in simulator."""
        with self._lock:
            if index in self.sdo_store and sub_index in self.sdo_store[index]:
                return (self.sdo_store[index][sub_index], None)
            # Default zero bytes for uninitialized registers
            return (b'\x00\x00\x00\x00', None)

    def _handle_controlword(self, cw: int):
        self.controlword = cw
        current_state = decode_cia402_state(self.statusword)

        # Fault Reset (bit 7 rising)
        if (cw & 0x0080) != 0:
            self.error_code = 0x0000
            self.statusword = (self.statusword & ~0x0008) | 0x0040 # Switch on disabled
            self._update_led_status()
            return

        cmd = cw & 0x000F
        if cmd == 0x0006: # Shutdown
            self.statusword = 0x0221 # Ready to switch on
        elif cmd == 0x0007: # Switch on
            self.statusword = 0x0223 # Switched on
        elif cmd == 0x000F: # Enable operation
            self.statusword = 0x0227 # Operation enabled
        elif cmd == 0x0000: # Disable voltage
            self.statusword = 0x0240 # Switch on disabled
        elif cmd == 0x0002: # Quick stop
            self.statusword = 0x0207 # Quick stop active
            self.target_velocity = 0.0

        self._update_led_status()

    def _update_led_status(self):
        # Bit 31 of led_ctrl: User Mode
        is_user_mode = bool(self.led_ctrl_dword & (1 << 31))
        if is_user_mode:
            # User mode: LED_Status matches LED_CTRL
            self.led_status_dword = self.led_ctrl_dword
        else:
            # Driver Automatic Mode: synthesize status pattern
            cia_state = decode_cia402_state(self.statusword)
            if cia_state == Cia402State.FAULT or self.error_code != 0:
                # Red flashing 500ms
                self.led_status_dword = 0x00440000
            elif self.sto_active or cia_state == Cia402State.QUICK_STOP_ACTIVE:
                # Yellow flashing 500ms
                self.led_status_dword = 0x00004400
            elif cia_state == Cia402State.OPERATION_ENABLED:
                # Green solid or fast pulse
                self.led_status_dword = 0x00000011
            else:
                # Green flashing 500ms (Standby / Switched On)
                self.led_status_dword = 0x00000044
        
        self._set_sdo_u32(0x2FEF, 0x02, self.led_status_dword)

    def trigger_fault(self, error_code: int = 0x2310):
        """Simulate hardware/drive fault (e.g. overcurrent, overvoltage)."""
        with self._lock:
            self.error_code = error_code
            self.statusword = (self.statusword & ~0x006F) | 0x0008 # Fault active
            self.target_velocity = 0.0
            self.velocity_actual = 0.0
            self._update_led_status()

    def set_sto(self, active: bool):
        with self._lock:
            self.sto_active = active
            if active and decode_cia402_state(self.statusword) == Cia402State.OPERATION_ENABLED:
                self.statusword = 0x0207 # Quick stop / safe stop
                self.target_velocity = 0.0
    def set_led_ctrl(self, dword: int):
        """Sets Object 0x2FEF:01 LED_CTRL."""
        with self._lock:
            self.led_ctrl_dword = dword
            self._set_sdo_u32(0x2FEF, 0x01, dword)
            self._update_led_status()

    def sdo_read(self, idx: int, sub: int) -> Tuple[Optional[bytes], Optional[str]]:
        """Emulate SDO Upload from Virtual Drive."""
        with self._lock:
            if idx in self.sdo_store and sub in self.sdo_store[idx]:
                return self.sdo_store[idx][sub], None
            return None, f"SDO Object 0x{idx:04X}:{sub:02X} not found"

    def sdo_write(self, idx: int, sub: int, data: bytes) -> Optional[str]:
        """Emulate SDO Download to Virtual Drive."""
        with self._lock:
            if idx == 0x2FEF and sub == 0x01:
                val = int.from_bytes(data, 'little')
                self.led_ctrl_dword = val
                self._set_sdo_u32(0x2FEF, 0x01, val)
                self._update_led_status()
            elif idx == 0x6040 and sub == 0x00:
                val = int.from_bytes(data, 'little')
                self.controlword = val
                self._set_sdo_u16(0x6040, 0x00, val)
                self._process_state_machine()
                self._update_led_status()
            else:
                self._set_sdo_raw(idx, sub, data)
            return None

    def get_telemetry(self) -> MotorTelemetry:
        with self._lock:
            state = decode_cia402_state(self.statusword)
            cfg = LedRingConfig.from_dword(self.led_status_dword)
            return MotorTelemetry(
                timestamp=time.time(),
                statusword=self.statusword,
                controlword=self.controlword,
                cia_state=state,
                mode_display=int(self.mode_display),
                mode_set=int(self.mode_set),
                position_actual=int(self.position_actual),
                position_target=int(self.target_position),
                velocity_actual=int(self.velocity_actual),
                velocity_target=int(self.target_velocity),
                torque_actual=int(self.torque_actual),
                torque_target=int(self.target_torque),
                dc_bus_voltage_mv=int(self.dc_bus_mv),
                temperature_c=float(self.temperature_c),
                sto_active=self.sto_active,
                error_code=self.error_code,
                following_error=int(self.following_error),
                led_status_dword=self.led_status_dword,
                led_ctrl_dword=self.led_ctrl_dword,
                led_config=cfg
            )

    def _sim_loop(self):
        while self._running:
            now = time.perf_counter()
            dt = now - self._last_tick
            self._last_tick = now
            if dt > 0.1:
                dt = 0.1

            with self._lock:
                state = decode_cia402_state(self.statusword)
                if state == Cia402State.OPERATION_ENABLED and not self.sto_active:
                    # Motion physics
                    if self.mode_display in (OperationMode.PROFILE_VELOCITY, OperationMode.RATED_SPEED, OperationMode.CSV):
                        # Velocity Ramping
                        diff = self.target_velocity - self.velocity_actual
                        max_step = self.acceleration * dt
                        if abs(diff) <= max_step:
                            self.velocity_actual = self.target_velocity
                        else:
                            self.velocity_actual += math.copysign(max_step, diff)
                        
                        # Position Integration
                        self.position_actual += (self.velocity_actual * 10000.0 / 60.0) * dt
                        self.torque_actual = abs(self.velocity_actual / self.max_velocity) * 250.0 + 10.0
                    
                    elif self.mode_display in (OperationMode.PROFILE_POSITION, OperationMode.CSP):
                        # Position control
                        pos_diff = self.target_position - self.position_actual
                        if abs(pos_diff) > 5.0:
                            direction = 1.0 if pos_diff > 0 else -1.0
                            target_speed = min(self.max_velocity, math.sqrt(2.0 * self.acceleration * abs(pos_diff) / 100.0))
                            self.velocity_actual = direction * target_speed
                            step = (self.velocity_actual * 10000.0 / 60.0) * dt
                            if abs(step) >= abs(pos_diff):
                                self.position_actual = self.target_position
                                self.velocity_actual = 0.0
                                # Target reached bit 10
                                self.statusword |= (1 << 10)
                            else:
                                self.position_actual += step
                                self.statusword &= ~(1 << 10)
                        else:
                            self.velocity_actual = 0.0
                            self.statusword |= (1 << 10)
                    
                    # Thermal and Voltage dynamics under load
                    load_fraction = abs(self.velocity_actual / self.max_velocity)
                    self.dc_bus_mv = int(self.dc_bus_nominal_mv - (load_fraction * 800.0))
                    self.temperature_c = min(65.0, 28.5 + (load_fraction * 15.0))
                
                else:
                    # Drive disabled or stopped: coast to 0
                    if abs(self.velocity_actual) > 1.0:
                        self.velocity_actual -= math.copysign(self.deceleration * dt, self.velocity_actual)
                    else:
                        self.velocity_actual = 0.0
                    self.torque_actual = 0.0
                    self.dc_bus_mv = self.dc_bus_nominal_mv
                    self.temperature_c = max(25.0, self.temperature_c - (0.5 * dt))

                # Update live SDO registers
                self._set_sdo_u16(0x6041, 0x00, self.statusword)
                self._set_sdo_i32(0x6064, 0x00, int(self.position_actual))
                self._set_sdo_i32(0x606C, 0x00, int(self.velocity_actual))
                self._set_sdo_i16(0x6077, 0x00, int(self.torque_actual))
                self._set_sdo_u32(0x6079, 0x00, self.dc_bus_mv)
                self._set_sdo_u16(0x60F7, 0x11, int(self.temperature_c * 10))

            time.sleep(0.02)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.5)
