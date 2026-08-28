"""
Unit tests for core/simulation.py and core/motor_device.py.
"""

import unittest
import time
from core.simulation import VirtualMotorDrive
from core.motor_device import Cia402State, OperationMode, decode_cia402_state

class TestSimulation(unittest.TestCase):

    def setUp(self):
        self.sim = VirtualMotorDrive()

    def tearDown(self):
        self.sim.stop()

    def test_cia402_state_machine_flow(self):
        # 1. Initially Switch on disabled (0x0240)
        t = self.sim.get_telemetry()
        self.assertEqual(t.cia_state, Cia402State.SWITCH_ON_DISABLED)

        # 2. Shutdown (0x0006) -> Ready to switch on
        self.sim.write_sdo(0x6040, 0x00, (0x0006).to_bytes(2, 'little'))
        time.sleep(0.05)
        t = self.sim.get_telemetry()
        self.assertEqual(t.cia_state, Cia402State.READY_TO_SWITCH_ON)

        # 3. Switch On (0x0007) -> Switched on
        self.sim.write_sdo(0x6040, 0x00, (0x0007).to_bytes(2, 'little'))
        time.sleep(0.05)
        t = self.sim.get_telemetry()
        self.assertEqual(t.cia_state, Cia402State.SWITCHED_ON)

        # 4. Enable Operation (0x000F) -> Operation enabled
        self.sim.write_sdo(0x6040, 0x00, (0x000F).to_bytes(2, 'little'))
        time.sleep(0.05)
        t = self.sim.get_telemetry()
        self.assertEqual(t.cia_state, Cia402State.OPERATION_ENABLED)

    def test_velocity_motion_physics(self):
        # Enable drive
        self.sim.write_sdo(0x6040, 0x00, (0x0006).to_bytes(2, 'little'))
        self.sim.write_sdo(0x6040, 0x00, (0x0007).to_bytes(2, 'little'))
        self.sim.write_sdo(0x6040, 0x00, (0x000F).to_bytes(2, 'little'))

        # Set Mode: Profile Velocity (3)
        self.sim.write_sdo(0x6060, 0x00, (3).to_bytes(1, 'little', signed=True))

        # Command 1000 RPM
        self.sim.write_sdo(0x60FF, 0x00, (1000).to_bytes(4, 'little', signed=True))
        
        # Wait for ramping
        time.sleep(0.3)
        t = self.sim.get_telemetry()
        self.assertGreater(t.velocity_rpm, 200.0)
        self.assertGreater(t.torque_actual, 0)

    def test_led_ring_sdo_write_and_read(self):
        # Write LED_CTRL (0x2FEF:01) -> User mode + Solid Red (0x80110000)
        test_val = 0x80110000
        self.sim.write_sdo(0x2FEF, 0x01, test_val.to_bytes(4, 'little'))
        
        # Read LED_Status (0x2FEF:02)
        data, err = self.sim.read_sdo(0x2FEF, 0x02)
        self.assertIsNone(err)
        read_val = int.from_bytes(data, 'little')
        self.assertEqual(read_val, test_val)

    def test_sto_interlock(self):
        self.sim.write_sdo(0x6040, 0x00, (0x000F).to_bytes(2, 'little'))
        self.sim.set_sto(True)
        t = self.sim.get_telemetry()
        self.assertTrue(t.sto_active)

if __name__ == "__main__":
    unittest.main()
