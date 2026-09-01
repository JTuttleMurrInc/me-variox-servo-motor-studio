"""
LED Ring Object (0x2FEF) Encoder, Decoder, and Animation Engine.

Spec Details from Murrelektronik Vario-X Motor Manual (V000-MDDC0-0000001):
Object 0x2FEF:01 - LED_CTRL (DWORD, Read/Write)
Object 0x2FEF:02 - LED_Status (DWORD, Read Only)

32-Bit Bitfield Layout:
  Bit 31:      LED_mode (0 = Driver / Automatic, 1 = User / Manual)
  Bits 30..24: Reserved (0)
  Bits 23..20: RRRR (Red Right Nibble)
  Bits 19..16: rrrr (Red Left Nibble)
  Bits 15..12: YYYY (Yellow Right Nibble)
  Bits 11..8:  yyyy (Yellow Left Nibble)
  Bits 7..4:   GGGG (Green Right Nibble)
  Bits 3..0:   gggg (Green Left Nibble)

Priority within group: Red > Yellow > Green
"""

import time
from enum import IntEnum
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, List

class BlinkPattern(IntEnum):
    OFF = 0x0
    SOLID_ON = 0x1
    ON_1S_OFF_1S = 0x2
    OFF_1S_ON_1S = 0x3
    ON_500MS_OFF_500MS = 0x4
    OFF_500MS_ON_500MS = 0x5
    ON_250MS_OFF_250MS = 0x6
    OFF_250MS_ON_250MS = 0x7
    FLASH_1HZ_SINGLE = 0x8
    FLASH_1HZ_DOUBLE = 0x9
    FLASH_1HZ_TRIPLE = 0xA
    FLASH_2HZ_SINGLE = 0xB
    FLASH_2HZ_SHIFT_125MS = 0xC
    FLASH_2HZ_SHIFT_250MS = 0xD
    FLASH_2HZ_SHIFT_375MS = 0xE
    FAST_STROBE_4HZ = 0xF

PATTERN_NAMES: Dict[int, str] = {
    0x0: "Off",
    0x1: "Solid On",
    0x2: "1s On / 1s Off (0.5 Hz)",
    0x3: "1s Off / 1s On (0.5 Hz Inverted)",
    0x4: "500ms On / 500ms Off (1 Hz)",
    0x5: "500ms Off / 500ms On (1 Hz Inverted)",
    0x6: "250ms On / 250ms Off (2 Hz)",
    0x7: "250ms Off / 250ms On (2 Hz Inverted)",
    0x8: "Every 1s, 125ms pulse (Single Flash)",
    0x9: "Every 1s, 2x 125ms pulse (Double Flash)",
    0xA: "Every 1s, 3x 125ms pulse (Triple Flash)",
    0xB: "Every 500ms, 125ms pulse (2 Hz Flash)",
    0xC: "Every 500ms, 125ms pulse (125ms phase shift)",
    0xD: "Every 500ms, 125ms pulse (250ms phase shift)",
    0xE: "Every 500ms, 125ms pulse (375ms phase shift)",
    0xF: "125ms Off / 125ms On (Fast Strobe 4 Hz)"
}

def eval_pattern_state(pattern_code: int, t_sec: float) -> bool:
    """
    Evaluates whether a pattern is illuminated (True) or dark (False) at time t_sec.
    """
    p = pattern_code & 0x0F
    if p == 0x0:
        return False
    elif p == 0x1:
        return True
    elif p == 0x2:
        return (t_sec % 2.0) < 1.0
    elif p == 0x3:
        return (t_sec % 2.0) >= 1.0
    elif p == 0x4:
        return (t_sec % 1.0) < 0.5
    elif p == 0x5:
        return (t_sec % 1.0) >= 0.5
    elif p == 0x6:
        return (t_sec % 0.5) < 0.25
    elif p == 0x7:
        return (t_sec % 0.5) >= 0.25
    elif p == 0x8:
        # Every 1s, 125ms on
        return (t_sec % 1.0) < 0.125
    elif p == 0x9:
        # Every 1s, twice 125ms on (0..125ms and 250..375ms)
        phase = t_sec % 1.0
        return (0.0 <= phase < 0.125) or (0.250 <= phase < 0.375)
    elif p == 0xA:
        # Every 1s, 3x 125ms on (0..125ms, 250..375ms, 500..625ms)
        phase = t_sec % 1.0
        return (0.0 <= phase < 0.125) or (0.250 <= phase < 0.375) or (0.500 <= phase < 0.625)
    elif p == 0xB:
        # Every 500ms, 125ms on
        return (t_sec % 0.5) < 0.125
    elif p == 0xC:
        # Every 500ms, 125ms on, 125ms shift
        phase = t_sec % 0.5
        return 0.125 <= phase < 0.250
    elif p == 0xD:
        # Every 500ms, 125ms on, 250ms shift
        phase = t_sec % 0.5
        return 0.250 <= phase < 0.375
    elif p == 0xE:
        # Every 500ms, 125ms on, 375ms shift
        phase = t_sec % 0.5
        return 0.375 <= phase < 0.500
    elif p == 0xF:
        # 125ms Off, 125ms On (250ms cycle)
        return (t_sec % 0.250) >= 0.125
    return False

@dataclass
class SideColorState:
    """Colors configured for one half of the motor ring."""
    red: int = 0
    yellow: int = 0
    green: int = 0

    def active_color(self, t_sec: float) -> Tuple[Optional[str], float]:
        """
        Determines the visible color and brightness based on priority:
        Red > Yellow > Green.
        Returns (color_name, intensity 0.0..1.0)
        """
        # Check Red (Highest Priority)
        if self.red != 0:
            if eval_pattern_state(self.red, t_sec):
                return ("red", 1.0)
        
        # Check Yellow (Medium Priority)
        if self.yellow != 0:
            if eval_pattern_state(self.yellow, t_sec):
                return ("yellow", 1.0)

        # Check Green (Lowest Priority)
        if self.green != 0:
            if eval_pattern_state(self.green, t_sec):
                return ("green", 1.0)

        return (None, 0.0)

@dataclass
class LedRingConfig:
    """Full representation of 32-bit LED Ring control or status register."""
    user_mode: bool = False
    red_right: int = 0
    red_left: int = 0
    yellow_right: int = 0
    yellow_left: int = 0
    green_right: int = 0
    green_left: int = 0
    name: str = ""

    @property
    def description(self) -> str:
        if self.name:
            return self.name
        if not self.user_mode:
            return "Auto Firmware Driver Mode"
        parts = []
        if self.red_left or self.red_right:
            parts.append(f"Red(L:{self.red_left:#x},R:{self.red_right:#x})")
        if self.yellow_left or self.yellow_right:
            parts.append(f"Yel(L:{self.yellow_left:#x},R:{self.yellow_right:#x})")
        if self.green_left or self.green_right:
            parts.append(f"Grn(L:{self.green_left:#x},R:{self.green_right:#x})")
        return " | ".join(parts) if parts else "All Off"

    def to_dword(self) -> int:
        """Encodes config into 32-bit DWORD."""
        val = 0
        if self.user_mode:
            val |= (1 << 31)
        val |= (self.red_right & 0xF) << 20
        val |= (self.red_left & 0xF) << 16
        val |= (self.yellow_right & 0xF) << 12
        val |= (self.yellow_left & 0xF) << 8
        val |= (self.green_right & 0xF) << 4
        val |= (self.green_left & 0xF)
        return val

    @classmethod
    def from_dword(cls, dword: int) -> 'LedRingConfig':
        """Decodes 32-bit DWORD into config structure."""
        user_mode = bool(dword & (1 << 31))
        rr = (dword >> 20) & 0xF
        rl = (dword >> 16) & 0xF
        yr = (dword >> 12) & 0xF
        yl = (dword >> 8) & 0xF
        gr = (dword >> 4) & 0xF
        gl = dword & 0xF
        return cls(
            user_mode=user_mode,
            red_right=rr,
            red_left=rl,
            yellow_right=yr,
            yellow_left=yl,
            green_right=gr,
            green_left=gl
        )

    def get_left_state(self) -> SideColorState:
        return SideColorState(red=self.red_left, yellow=self.yellow_left, green=self.green_left)

    def get_right_state(self) -> SideColorState:
        return SideColorState(red=self.red_right, yellow=self.yellow_right, green=self.green_right)

    def eval_sides(self, t_sec: float) -> Tuple[Tuple[Optional[str], float], Tuple[Optional[str], float]]:
        """Returns ((left_color, left_intensity), (right_color, right_intensity)) at time t_sec."""
        return (
            self.get_left_state().active_color(t_sec),
            self.get_right_state().active_color(t_sec)
        )

# Optical Direction Patterns (0x2FEF:01)
LED_CW_GREEN_CHASE   = 0x800000DB  # Clockwise rotating chaser (Green: Left 0xB -> Right 0xD)
LED_CCW_GREEN_CHASE  = 0x800000BD  # Counter-Clockwise rotating chaser (Green: Right 0xB -> Left 0xD)
LED_CW_AMBER_CHASE   = 0x8000DB00  # Clockwise rotating chaser (Amber: Left 0xB -> Right 0xD)
LED_CCW_AMBER_CHASE  = 0x8000BD00  # Counter-Clockwise rotating chaser (Amber: Right 0xB -> Left 0xD)
LED_CW_GREEN_RIGHT   = 0x80000010  # CW Direction Half-Ring Indicator (Right Solid Green)
LED_CCW_AMBER_LEFT   = 0x80000100  # CCW Direction Half-Ring Indicator (Left Solid Amber)
LED_STANDBY_GREEN    = 0x80000011  # Standby / Stopped Solid Green
LED_STANDBY_PULSE    = 0x80000044  # Standby / Stopped Gentle 1 Hz Pulse
LED_FAULT_RED        = 0x80110000  # Fault / E-Stop Solid Red

def get_direction_led_dword(direction_sign: float, color: str = "green", chaser: bool = True) -> int:
    """
    Returns 32-bit LED_CTRL DWORD that optically indicates physical motion direction.
      - direction_sign > 0: Clockwise / Forward rotation
      - direction_sign < 0: Counter-Clockwise / Reverse rotation
      - direction_sign == 0: Standby / Idle (Solid Green)
    """
    if direction_sign > 0:
        if chaser:
            return LED_CW_GREEN_CHASE if color == "green" else LED_CW_AMBER_CHASE
        else:
            return LED_CW_GREEN_RIGHT
    elif direction_sign < 0:
        if chaser:
            return LED_CCW_GREEN_CHASE if color == "green" else LED_CCW_AMBER_CHASE
        else:
            return LED_CCW_AMBER_LEFT
    else:
        return LED_STANDBY_GREEN

# Standard Presets
RING_PRESETS: Dict[str, LedRingConfig] = {
    "Auto Driver Mode (Firmware Controlled)": LedRingConfig(user_mode=False, name="Auto Driver Mode (Firmware Controlled)"),
    "Solid Green (Normal Operation)": LedRingConfig(user_mode=True, green_left=0x1, green_right=0x1, name="Solid Green (Normal Operation)"),
    "CW Motion (Green Chaser Left→Right)": LedRingConfig.from_dword(LED_CW_GREEN_CHASE),
    "CCW Motion (Green Chaser Right→Left)": LedRingConfig.from_dword(LED_CCW_GREEN_CHASE),
    "CW Motion (Amber Chaser Left→Right)": LedRingConfig.from_dword(LED_CW_AMBER_CHASE),
    "CCW Motion (Amber Chaser Right→Left)": LedRingConfig.from_dword(LED_CCW_AMBER_CHASE),
    "Green Pulse 1 Hz (Ready / Standby)": LedRingConfig(user_mode=True, green_left=0x4, green_right=0x4, name="Green Pulse 1 Hz (Ready / Standby)"),
    "Solid Yellow (Warning / Setup)": LedRingConfig(user_mode=True, yellow_left=0x1, yellow_right=0x1, name="Solid Yellow (Warning / Setup)"),
    "Yellow Flash 1 Hz (Caution Notice)": LedRingConfig(user_mode=True, yellow_left=0x8, yellow_right=0x8, name="Yellow Flash 1 Hz (Caution Notice)"),
    "Solid Red (E-Stop / Fault Active)": LedRingConfig(user_mode=True, red_left=0x1, red_right=0x1, name="Solid Red (E-Stop / Fault Active)"),
    "Red Strobe 2 Hz (Critical Alarm)": LedRingConfig(user_mode=True, red_left=0x6, red_right=0x6, name="Red Strobe 2 Hz (Critical Alarm)"),
    "Dual Amber / Green (Status Sync)": LedRingConfig(user_mode=True, yellow_left=0x1, green_right=0x1, name="Dual Amber / Green (Status Sync)"),
    "Police Emergency (Red Left / Green Right Strobe)": LedRingConfig(user_mode=True, red_left=0x4, green_right=0x5, name="Police Emergency (Red Left / Green Right Strobe)"),
    "Rotating Chaser Simulation (Phase Shift B/D)": LedRingConfig(user_mode=True, green_left=0xB, green_right=0xD, name="Rotating Chaser Simulation (Phase Shift B/D)"),
    "Double Blink Amber (Attention Required)": LedRingConfig(user_mode=True, yellow_left=0x9, yellow_right=0x9, name="Double Blink Amber (Attention Required)"),
    "Fast Strobe White/Mixed (Identification)": LedRingConfig(user_mode=True, green_left=0xF, green_right=0xF, yellow_left=0xF, yellow_right=0xF, name="Fast Strobe White/Mixed (Identification)"),
    "All Dark / LED Off": LedRingConfig(user_mode=True, name="All Dark / LED Off")
}

