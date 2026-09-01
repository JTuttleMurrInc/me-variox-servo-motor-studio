"""
Murrelektronik Vario-X Motor Drive CiA 402 Device Model and Telemetry Controller.
"""

from enum import Enum, IntEnum
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Callable

from core.led_ring import LedRingConfig

class Cia402State(Enum):
    NOT_READY_TO_SWITCH_ON = "Not Ready to Switch On"
    SWITCH_ON_DISABLED = "Switch On Disabled"
    READY_TO_SWITCH_ON = "Ready to Switch On"
    SWITCHED_ON = "Switched On"
    OPERATION_ENABLED = "Operation Enabled"
    QUICK_STOP_ACTIVE = "Quick Stop Active"
    FAULT_REACTION_ACTIVE = "Fault Reaction Active"
    FAULT = "Fault"
    UNKNOWN = "Unknown"

class OperationMode(IntEnum):
    RATED_SPEED = -3
    NO_MODE = 0
    PROFILE_POSITION = 1
    PROFILE_VELOCITY = 3
    PROFILE_TORQUE = 4
    HOMING = 6
    CSP = 8
    CSV = 9
    CST = 10

MODE_NAMES: Dict[int, str] = {
    -3: "Rated Speed (Direct Velocity)",
    0: "No Mode Assigned",
    1: "Profile Position Mode (PP)",
    3: "Profile Velocity Mode (PV)",
    4: "Profile Torque Mode (TQ)",
    6: "Homing Mode (HM)",
    8: "Cyclic Synchronous Position (CSP)",
    9: "Cyclic Synchronous Velocity (CSV)",
    10: "Cyclic Synchronous Torque (CST)"
}

# Controlword Bit Masks & Commands
CMD_SHUTDOWN         = 0x0006
CMD_SWITCH_ON        = 0x0007
CMD_ENABLE_OPERATION = 0x000F
CMD_DISABLE_VOLTAGE  = 0x0000
CMD_QUICK_STOP       = 0x0002
CMD_DISABLE_OP       = 0x0007
CMD_FAULT_RESET      = 0x0080

@dataclass
class StoDiagnosticInfo:
    """Detailed STO Diagnostic state from Section 8.1.4 (Object 0x60F7.11)."""
    code: int
    error_code: int
    error_code_hex: str
    sto1_active: bool  # bit 6
    sto2_active: bool  # bit 7
    description: str
    is_fault: bool

STO_DIAGNOSTICS: Dict[int, StoDiagnosticInfo] = {
    0: StoDiagnosticInfo(0, 0x0000, "0x0000", False, False, "STO A = High, STO B = High, No Error (Safe)", False),
    1: StoDiagnosticInfo(1, 0xFF21, "0xFF21", False, True, "Self-diagnostics CPU cannot find STO high signal", True),
    2: StoDiagnosticInfo(2, 0xFF22, "0xFF22", False, True, "Theoretically impossible state (STO internal fault)", True),
    3: StoDiagnosticInfo(3, 0xFF1A, "0xFF1A", True, False, "STO A missing (Channel A Low)", True),
    4: StoDiagnosticInfo(4, 0xFF21, "0xFF21", False, True, "Theoretically impossible state (STO internal fault)", True),
    5: StoDiagnosticInfo(5, 0xFF1B, "0xFF1B", True, False, "STO B missing (Channel B Low)", True),
    6: StoDiagnosticInfo(6, 0xFF10, "0xFF10", True, False, "STO A & B transition High->Low within 100ms while active / Low at startup", True),
    7: StoDiagnosticInfo(7, 0xFF20, "0xFF20", False, True, "STO hardware error (Safety circuit defect)", True),
    11: StoDiagnosticInfo(11, 0xFF10, "0xFF10", True, True, "STO A & B Missing / No Input (Both Channels Low)", True),
}

def decode_sto_status(sto_code: int) -> StoDiagnosticInfo:
    """Decodes Object 0x60F7.11 into detailed STO channel and fault diagnostics."""
    if sto_code in STO_DIAGNOSTICS:
        return STO_DIAGNOSTICS[sto_code]
    return StoDiagnosticInfo(
        code=sto_code,
        error_code=0xFFFF,
        error_code_hex=f"0x{sto_code:04X}",
        sto1_active=bool(sto_code & (1 << 6)),
        sto2_active=bool(sto_code & (1 << 7)),
        description=f"STO Diagnostic Code 0x{sto_code:02X}",
        is_fault=sto_code != 0
    )

@dataclass
class MotorTelemetry:
    """Live telemetry packet sampled from Vario-X Motor Drive."""
    timestamp: float = 0.0
    statusword: int = 0
    controlword: int = 0
    cia_state: Cia402State = Cia402State.SWITCH_ON_DISABLED
    mode_display: int = 0
    mode_set: int = 0
    position_actual: int = 0      # Counts
    position_target: int = 0      # Counts
    velocity_actual: int = 0      # Counts/s or RPM
    velocity_target: int = 0      # Counts/s or RPM
    torque_actual: int = 0        # 0.1% rated torque
    torque_target: int = 0
    dc_bus_voltage_mv: int = 48000 # mV
    temperature_c: float = 25.0   # °C
    sto_code: int = 0             # Object 0x60F7.11 (STO_Status)
    sto_info: Optional[StoDiagnosticInfo] = None
    sto_active: bool = False      # Safe Torque Off Tripped/Active
    error_code: int = 0
    following_error: int = 0
    led_status_dword: int = 0
    led_ctrl_dword: int = 0
    led_config: LedRingConfig = None

    def __post_init__(self):
        if self.sto_info is None:
            if self.sto_code == 0 and self.sto_active:
                self.sto_code = 6
            self.sto_info = decode_sto_status(self.sto_code)
            self.sto_active = self.sto_active or self.sto_info.is_fault or (self.sto_code != 0)
        if self.led_config is None:
            self.led_config = LedRingConfig.from_dword(self.led_ctrl_dword)

    @property
    def mode_of_operation(self) -> int:
        return self.mode_display

    @property
    def dc_bus_voltage_v(self) -> float:
        return self.dc_bus_voltage_mv / 1000.0

    @property
    def velocity_rpm(self) -> float:
        return float(self.velocity_actual)

    @property
    def torque_percent(self) -> float:
        return self.torque_actual / 10.0

def decode_cia402_state(statusword: int) -> Cia402State:
    """Decodes CiA 402 state from 16-bit Statusword."""
    # Mask low 7 bits and bit 6
    s = statusword
    # Bit 3: Fault
    if (s & 0x0008) != 0:
        if (s & 0x004F) == 0x000F:
            return Cia402State.FAULT_REACTION_ACTIVE
        return Cia402State.FAULT

    # Bit 6: Switch on disabled (xxxx xxxx x1xx 0000)
    if (s & 0x004F) == 0x0040:
        return Cia402State.SWITCH_ON_DISABLED

    # Quick Stop Active (xxxx xxxx x00x 0111)
    if (s & 0x006F) == 0x0007:
        return Cia402State.QUICK_STOP_ACTIVE

    # Operation Enabled (xxxx xxxx x01x 0111)
    if (s & 0x006F) == 0x0027:
        return Cia402State.OPERATION_ENABLED

    # Switched On (xxxx xxxx x01x 0011)
    if (s & 0x006F) == 0x0023:
        return Cia402State.SWITCHED_ON

    # Ready to Switch On (xxxx xxxx x01x 0001)
    if (s & 0x006F) == 0x0021:
        return Cia402State.READY_TO_SWITCH_ON

    # Not Ready to Switch On (xxxx xxxx x0xx 0000)
    if (s & 0x004F) == 0x0000:
        return Cia402State.NOT_READY_TO_SWITCH_ON

    return Cia402State.UNKNOWN
