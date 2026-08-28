"""
Unit tests for core/esi_parser.py.
"""

import unittest
import os
from core.esi_parser import EsiParser

class TestEsiParser(unittest.TestCase):

    def setUp(self):
        self.parser = EsiParser()

    def test_esi_loaded(self):
        self.assertIsNotNone(self.parser.device_info)
        info = self.parser.device_info
        self.assertIn("Vario-X", info.name)
        self.assertGreater(len(info.objects), 50)

    def test_key_objects_present(self):
        objs = self.parser.device_info.objects
        # CiA 402 Objects
        self.assertIn(0x6040, objs) # Controlword
        self.assertIn(0x6041, objs) # Statusword
        self.assertIn(0x6060, objs) # Modes of operation
        self.assertIn(0x6064, objs) # Position actual
        self.assertIn(0x606C, objs) # Velocity actual
        self.assertIn(0x6077, objs) # Torque actual
        self.assertIn(0x607A, objs) # Target position
        self.assertIn(0x60FF, objs) # Target velocity

        # LED Ring Object 0x2FEF
        self.assertIn(0x2FEF, objs)
        led_obj = objs[0x2FEF]
        self.assertIn(1, led_obj.sub_items) # LED_CTRL
        self.assertIn(2, led_obj.sub_items) # LED_Status

    def test_pdo_mappings_extracted(self):
        tx_pdos = self.parser.device_info.tx_pdos
        rx_pdos = self.parser.device_info.rx_pdos
        self.assertIn(0x1A00, tx_pdos)
        self.assertIn(0x1600, rx_pdos)
        
        # Verify 0x1A00 has statusword entry
        p_1a00 = tx_pdos[0x1A00]
        self.assertGreater(len(p_1a00.entries), 4)
        entry_indices = [e.index for e in p_1a00.entries]
        self.assertIn(0x6041, entry_indices)
        self.assertIn(0x6064, entry_indices)
        self.assertIn(0x2FEF, entry_indices)

    def test_search_functionality(self):
        results = self.parser.search("LED")
        self.assertTrue(any(r.index == 0x2FEF for r in results))

        cia_results = self.parser.search("Controlword")
        self.assertTrue(any(r.index == 0x6040 for r in cia_results))

if __name__ == "__main__":
    unittest.main()
