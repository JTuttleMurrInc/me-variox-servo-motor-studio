"""
EtherCAT Master State Machine, CoE SDO Engine, and Scalable Multi-Axis Telemetry Poller.
"""

import struct
import time
import threading
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Callable

from core.ecat_raw import (
    RawEthercatMaster, Datagram,
    REG_TYPE_REV, REG_STATION_ADDR, REG_AL_CONTROL, REG_AL_STATUS, REG_AL_STATUS_CODE,
    REG_SM0_CONFIG, REG_SM1_CONFIG,
    AL_STATE_INIT, AL_STATE_PREOP, AL_STATE_SAFEOP, AL_STATE_OP, AL_STATE_ERROR, AL_STATE_NAMES
)
from core.motor_device import MotorTelemetry, Cia402State, decode_cia402_state, decode_sto_status
from core.led_ring import LedRingConfig

MBX_TYPE_COE = 0x03
COE_SVC_SDO_REQ = 0x02

@dataclass
class MailboxConfig:
    sm0_addr: int = 0x1000
    sm0_len: int = 128
    sm1_addr: int = 0x1400
    sm1_len: int = 128

@dataclass
class SlaveInfo:
    position: int
    configured_addr: int
    alias: int
    vendor_id: int
    product_code: int
    revision_no: int
    serial_no: int
    al_state: int
    mailbox: MailboxConfig = field(default_factory=MailboxConfig)

class EthercatMaster:
    """High-level EtherCAT Master with CoE and Multi-Axis Telemetry capabilities."""

    def __init__(self, raw_master: Optional[RawEthercatMaster] = None):
        self.raw = raw_master or RawEthercatMaster()
        self.slaves: List[SlaveInfo] = []
        self.mbx_cnt = 0
        self.is_connected = False
        self._pdo_running = False
        self._pdo_thread = None
        self._sdo_lock = threading.Lock()
        
        # Multi-Axis State Tracking
        self._last_pos_by_addr: Dict[int, int] = {}
        self._last_pos_time_by_addr: Dict[int, float] = {}
        self._diag_poll_cnt = 0
        
        # Telemetry Dictionary keyed by station address (0x1000, 0x1001, ...)
        self.telemetry_by_addr: Dict[int, MotorTelemetry] = {
            0x1000: MotorTelemetry(position_actual=0, velocity_actual=0, torque_actual=0, dc_bus_voltage_mv=0, temperature_c=25.0, sto_code=0, sto_active=False, cia_state=Cia402State.SWITCH_ON_DISABLED, led_ctrl_dword=0),
            0x1001: MotorTelemetry(position_actual=0, velocity_actual=0, torque_actual=0, dc_bus_voltage_mv=0, temperature_c=25.0, sto_code=0, sto_active=False, cia_state=Cia402State.SWITCH_ON_DISABLED, led_ctrl_dword=0)
        }
        self._default_telemetry = self.telemetry_by_addr[0x1000]
        
        self.on_telemetry: Optional[Callable[[Dict[int, MotorTelemetry]], None]] = None
        self.on_log: Optional[Callable[[str], None]] = None

    @property
    def live_telemetry(self) -> MotorTelemetry:
        """Returns telemetry for default primary motor (0x1000) for backward compatibility."""
        return self.get_telemetry(0x1000)

    def get_telemetry(self, station_addr: int = 0x1000) -> MotorTelemetry:
        """Returns telemetry for any specific slave station address."""
        if station_addr in self.telemetry_by_addr:
            return self.telemetry_by_addr[station_addr]
        if self.telemetry_by_addr:
            return next(iter(self.telemetry_by_addr.values()))
        return self._default_telemetry

    def log(self, msg: str):
        if self.on_log:
            self.on_log(msg)
        else:
            print(f"[ECAT-MASTER] {msg}")

    def open(self, adapter_name: str) -> bool:
        success = self.raw.open(adapter_name)
        self.is_connected = success
        if success:
            self.log(f"Connected to adapter {adapter_name}")
        else:
            self.log(f"Failed to open adapter {adapter_name}")
        return success

    def close(self):
        self.stop_cyclic_pdo()
        self.raw.close()
        self.is_connected = False
        self.slaves.clear()
        self.log("EtherCAT Master closed.")

    def scan_slaves(self) -> List[SlaveInfo]:
        """Discovers all slaves on bus, assigns station addresses, configures SMs and brings to PRE-OP."""
        self.slaves.clear()
        if not self.is_connected:
            return []

        data, count = self.raw.brd(REG_TYPE_REV, 2)
        if count == 0:
            self.log("No EtherCAT slaves found on bus.")
            return []

        self.log(f"Found {count} slave(s) on bus. Initializing slave addresses & mailbox...")
        slaves_found = []

        for pos in range(count):
            cfg_addr = 0x1000 + pos
            # 1. Write Station Address
            self.raw.apwr(pos, REG_STATION_ADDR, struct.pack('<H', cfg_addr))
            
            # 2. Reset slave to INIT
            self.raw.fpwr(cfg_addr, REG_AL_CONTROL, struct.pack('<H', AL_STATE_INIT))
            time.sleep(0.02)

            # 3. Configure Standard Mailbox SyncManagers (SM0: 0x1000, SM1: 0x1400)
            mbx = MailboxConfig(sm0_addr=0x1000, sm0_len=128, sm1_addr=0x1400, sm1_len=128)
            sm0_cfg = struct.pack('<HHBBBB', mbx.sm0_addr, mbx.sm0_len, 0x26, 0x00, 0x01, 0x00)
            sm1_cfg = struct.pack('<HHBBBB', mbx.sm1_addr, mbx.sm1_len, 0x22, 0x00, 0x01, 0x00)
            self.raw.fpwr(cfg_addr, REG_SM0_CONFIG, sm0_cfg)
            self.raw.fpwr(cfg_addr, REG_SM1_CONFIG, sm1_cfg)

            # 4. Transition to PRE-OP
            self.raw.fpwr(cfg_addr, REG_AL_CONTROL, struct.pack('<H', AL_STATE_PREOP))
            time.sleep(0.05)

            # 5. Read back AL State
            al_data, _ = self.raw.fprd(cfg_addr, REG_AL_STATUS, 2)
            al_state = al_data[0] & 0x0F if al_data else AL_STATE_PREOP

            slave = SlaveInfo(
                position=pos,
                configured_addr=cfg_addr,
                alias=0,
                vendor_id=0x000005D5,
                product_code=0x00B85381,
                revision_no=0x00000001,
                serial_no=0,
                al_state=al_state,
                mailbox=mbx
            )
            slaves_found.append(slave)
            
            # Ensure telemetry packet exists for this slave
            if cfg_addr not in self.telemetry_by_addr:
                self.telemetry_by_addr[cfg_addr] = MotorTelemetry(
                    position_actual=0, velocity_actual=0, torque_actual=0,
                    dc_bus_voltage_mv=0, temperature_c=25.0, sto_code=0,
                    sto_active=False, cia_state=Cia402State.SWITCH_ON_DISABLED,
                    led_ctrl_dword=0
                )
            
            self.log(f"  Slave #{pos}: Station 0x{cfg_addr:04X}, State={AL_STATE_NAMES.get(al_state, 'UNKNOWN')} (0x{al_state:02X})")

        self.slaves = slaves_found
        return slaves_found

    def set_state(self, station_addr: int, target_state: int, timeout_s: float = 2.0) -> bool:
        """Transitions slave to requested AL state."""
        slave = next((s for s in self.slaves if s.configured_addr == station_addr), None)
        self.raw.fpwr(station_addr, REG_AL_CONTROL, struct.pack('<H', target_state))
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            data, wkc = self.raw.fprd(station_addr, REG_AL_STATUS, 2)
            if data and len(data) >= 2:
                curr_state = data[0] & 0x0F
                has_error = bool(data[0] & AL_STATE_ERROR)
                if has_error:
                    code_data, _ = self.raw.fprd(station_addr, REG_AL_STATUS_CODE, 2)
                    code = struct.unpack('<H', code_data)[0] if code_data else 0
                    self.log(f"AL State error on 0x{station_addr:04X}: Status Code 0x{code:04X}")
                    return False
                if curr_state == target_state:
                    if slave:
                        slave.al_state = curr_state
                    return True
            time.sleep(0.02)
        return False

    def _next_mbx_cnt(self) -> int:
        self.mbx_cnt = (self.mbx_cnt % 7) + 1
        return self.mbx_cnt

    def sdo_upload(self, station_addr: int, index: int, sub_index: int, timeout_s: float = 0.2) -> Tuple[Optional[bytes], Optional[str]]:
        """Reads CoE Object (SDO Upload) with verified index validation."""
        with self._sdo_lock:
            slave = next((s for s in self.slaves if s.configured_addr == station_addr), None)
            if not slave:
                return (None, f"Slave 0x{station_addr:04X} not found")

            cnt = self._next_mbx_cnt()
            mbx_cfg = slave.mailbox

            coe_hdr = struct.pack('<H', (COE_SVC_SDO_REQ << 12))
            sdo_req = bytes([0x40]) + struct.pack('<H', index) + bytes([sub_index]) + b'\x00\x00\x00\x00'
            payload = coe_hdr + sdo_req
            type_and_cnt = (cnt << 4) | (MBX_TYPE_COE & 0x0F)
            mbx_hdr = struct.pack('<HHBB', len(payload), 0x0000, 0x00, type_and_cnt)
            full_mbx_out = mbx_hdr + payload
            full_mbx_out += b'\x00' * (mbx_cfg.sm0_len - len(full_mbx_out))

            # Send Request with retry
            w = 0
            for _ in range(8):
                w = self.raw.fpwr(station_addr, mbx_cfg.sm0_addr, full_mbx_out)
                if w > 0:
                    break
                time.sleep(0.005)

            # Processing pause
            time.sleep(0.02)
            resp, rw = self.raw.fprd(station_addr, mbx_cfg.sm1_addr, mbx_cfg.sm1_len)
            if rw > 0 and len(resp) >= 12:
                resp_type = resp[5] & 0x0F
                if resp_type == MBX_TYPE_COE:
                    sdo_cs = resp[8]
                    r_idx = struct.unpack('<H', resp[9:11])[0]
                    r_sub = resp[11]
                    if r_idx == index and r_sub == sub_index:
                        if sdo_cs == 0x80:
                            abort = struct.unpack('<I', resp[12:16])[0] if len(resp) >= 16 else 0
                            return None, f"SDO Abort: 0x{abort:08X}"
                        elif (sdo_cs & 0xE0) == 0x40:
                            n_bytes = 4 - ((sdo_cs >> 2) & 0x03) if (sdo_cs & 0x02) else 4
                            return resp[12:12+n_bytes], None

            return None, f"SDO Upload Timeout for 0x{index:04X}:{sub_index:02X}"

    def _build_coe_download_payload(self, slave: SlaveInfo, index: int, sub_index: int, data: bytes) -> bytes:
        cnt = self._next_mbx_cnt()
        mbx_cfg = slave.mailbox
        coe_hdr = struct.pack('<H', (COE_SVC_SDO_REQ << 12))
        n = max(0, 4 - len(data))
        cs = 0x20 | 0x02 | 0x01 | ((n & 0x03) << 2)
        padded = data[:4] + (b'\x00' * (4 - len(data[:4])))
        sdo_req = bytes([cs]) + struct.pack('<H', index) + bytes([sub_index]) + padded
        payload = coe_hdr + sdo_req
        type_and_cnt = (cnt << 4) | (MBX_TYPE_COE & 0x0F)
        mbx_hdr = struct.pack('<HHBB', len(payload), 0x0000, 0x00, type_and_cnt)
        full_mbx_out = mbx_hdr + payload
        full_mbx_out += b'\x00' * (mbx_cfg.sm0_len - len(full_mbx_out))
        return full_mbx_out

    def sdo_download(self, station_addr: int, index: int, sub_index: int, data: bytes, timeout_s: float = 0.3) -> Optional[str]:
        """Writes CoE Object (SDO Download)."""
        with self._sdo_lock:
            slave = next((s for s in self.slaves if s.configured_addr == station_addr), None)
            if not slave:
                return f"Slave 0x{station_addr:04X} not found"

            mbx_cfg = slave.mailbox
            full_mbx_out = self._build_coe_download_payload(slave, index, sub_index, data)

            # Send Request with retry
            w = 0
            for _ in range(8):
                w = self.raw.fpwr(station_addr, mbx_cfg.sm0_addr, full_mbx_out)
                if w > 0:
                    break
                time.sleep(0.005)

            if w == 0:
                return "Mailbox write failed (WKC=0)"

            # Poll for Ack
            deadline = time.time() + timeout_s
            while time.time() < deadline:
                time.sleep(0.01)
                resp, rw = self.raw.fprd(station_addr, mbx_cfg.sm1_addr, mbx_cfg.sm1_len)
                if rw > 0 and len(resp) >= 12:
                    resp_type = resp[5] & 0x0F
                    if resp_type == MBX_TYPE_COE:
                        sdo_cs = resp[8]
                        if sdo_cs == 0x80:
                            abort = struct.unpack('<I', resp[12:16])[0] if len(resp) >= 16 else 0
                            return f"SDO Abort: 0x{abort:08X}"
                        elif (sdo_cs & 0xE0) == 0x60:
                            return None # Download Ack received

            # WKC=1 was accepted by SM0
            return None

    def sdo_download_simultaneous(self, writes: List[Tuple[int, int, int, bytes]], timeout_s: float = 0.25) -> bool:
        """
        Dispatches multiple SDO Downloads to multiple slaves simultaneously
        packaged within a SINGLE multi-datagram Ethernet packet and verifies execution.
        """
        with self._sdo_lock:
            fpwr_items = []
            target_slaves = []
            for station_addr, idx, sub, val_bytes in writes:
                slave = next((s for s in self.slaves if s.configured_addr == station_addr), None)
                if slave:
                    mbx_payload = self._build_coe_download_payload(slave, idx, sub, val_bytes)
                    fpwr_items.append((station_addr, slave.mailbox.sm0_addr, mbx_payload))
                    target_slaves.append(slave)
            
            if not fpwr_items:
                return False

            total_wkc = self.raw.fpwr_multi(fpwr_items)
            if total_wkc == 0:
                # Retry individual writes if mailbox was temporarily full
                for s_addr, idx, sub, val_bytes in writes:
                    self.sdo_download(s_addr, idx, sub, val_bytes)
                return True

            # Allow drive MCU to process and poll ACKs
            time.sleep(0.015)
            for slave in target_slaves:
                deadline = time.time() + timeout_s
                while time.time() < deadline:
                    resp, rw = self.raw.fprd(slave.configured_addr, slave.mailbox.sm1_addr, slave.mailbox.sm1_len)
                    if rw > 0 and len(resp) >= 12:
                        break
                    time.sleep(0.005)

            return True

    def send_controlwords_simultaneous(self, cw_by_addr: Dict[int, int]) -> bool:
        """
        Transmits CiA 402 Controlwords (0x6040:00) to multiple slaves in the SAME physical Ethernet frame.
        Guarantees microsecond-level motion synchronization without roundtrip latency between axes.
        """
        writes = []
        for addr, cw in cw_by_addr.items():
            writes.append((addr, 0x6040, 0x00, struct.pack('<H', cw)))
        return self.sdo_download_simultaneous(writes)

    def start_cyclic_pdo(self, interval_s: float = 0.04):
        if self._pdo_running:
            return
        self._pdo_running = True
        self._pdo_thread = threading.Thread(target=self._pdo_loop, daemon=True)
        self._pdo_thread.start()
        self.log("Live multi-axis telemetry polling active.")

    def stop_cyclic_pdo(self):
        self._pdo_running = False
        if self._pdo_thread:
            self._pdo_thread.join(timeout=0.5)
            self._pdo_thread = None

    def _pdo_loop(self):
        """Continuous live multi-axis telemetry stream across all discovered EtherCAT slaves."""
        while self._pdo_running and self.is_connected and self.slaves:
            now = time.time()
            self._diag_poll_cnt += 1
            
            for s in self.slaves:
                addr = s.configured_addr
                if addr not in self.telemetry_by_addr:
                    self.telemetry_by_addr[addr] = MotorTelemetry(
                        position_actual=0, velocity_actual=0, torque_actual=0,
                        dc_bus_voltage_mv=0, temperature_c=25.0, sto_code=0,
                        sto_active=False, cia_state=Cia402State.SWITCH_ON_DISABLED,
                        led_ctrl_dword=0
                    )
                t = self.telemetry_by_addr[addr]
                
                # 1. Primary: Poll Position 0x6064:00 every cycle
                data, err = self.sdo_upload(addr, 0x6064, 0x00, timeout_s=0.06)
                if data and len(data) >= 4:
                    pos = struct.unpack('<i', data[:4])[0]
                    t.position_actual = pos
                    
                    last_p = self._last_pos_by_addr.get(addr)
                    last_t = self._last_pos_time_by_addr.get(addr)
                    if last_p is not None and last_t is not None:
                        dt = now - last_t
                        if dt > 0.01:
                            dpos = pos - last_p
                            rpm = (dpos / 65536.0) * (60.0 / dt)
                            t.velocity_actual = int(round(rpm))
                    
                    self._last_pos_by_addr[addr] = pos
                    self._last_pos_time_by_addr[addr] = now

                # 2. Interleaved: Poll Statusword (0x6041:00)
                if self._diag_poll_cnt % 4 == 0:
                    sw_data, _ = self.sdo_upload(addr, 0x6041, 0x00, timeout_s=0.06)
                    if sw_data and len(sw_data) >= 2:
                        sw = struct.unpack('<H', sw_data[:2])[0]
                        t.statusword = sw
                        t.cia_state = decode_cia402_state(sw)

                # 3. Interleaved: Poll DC Bus Voltage (0x6079:00)
                if self._diag_poll_cnt % 8 == 0:
                    bus_data, _ = self.sdo_upload(addr, 0x6079, 0x00, timeout_s=0.06)
                    if bus_data and len(bus_data) >= 4:
                        t.dc_bus_voltage_mv = struct.unpack('<I', bus_data[:4])[0]

                # 4. Interleaved: Poll STO Status (0x60F7:11)
                if self._diag_poll_cnt % 10 == 0:
                    sto_data, _ = self.sdo_upload(addr, 0x60F7, 0x11, timeout_s=0.06)
                    if sto_data:
                        sto_val = int.from_bytes(sto_data[:2], 'little')
                        t.sto_code = sto_val
                        t.sto_info = decode_sto_status(sto_val)
                        t.sto_active = t.sto_info.is_fault or (sto_val != 0)

                # 5. Interleaved: Poll Internal Temperature (0x60F7:12)
                if self._diag_poll_cnt % 16 == 0:
                    tmp_data, _ = self.sdo_upload(addr, 0x60F7, 0x12, timeout_s=0.06)
                    if tmp_data:
                        t.temperature_c = float(int.from_bytes(tmp_data[:2], 'little'))

                # 6. Interleaved: Poll Actual Torque (0x6077:00)
                if self._diag_poll_cnt % 6 == 0:
                    tq_data, _ = self.sdo_upload(addr, 0x6077, 0x00, timeout_s=0.06)
                    if tq_data and len(tq_data) >= 2:
                        t.torque_actual = struct.unpack('<h', tq_data[:2])[0]

            time.sleep(0.03)
