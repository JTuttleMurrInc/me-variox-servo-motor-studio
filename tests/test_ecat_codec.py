"""
Unit tests for core/ecat_raw.py datagram construction and parsing.
"""

import unittest
import struct
from core.ecat_raw import (
    RawEthercatMaster, Datagram, CMD_BRD, CMD_BWR, CMD_APRD, CMD_FPWR,
    ETH_TYPE_ETHERCAT
)

class TestEcatCodec(unittest.TestCase):

    def setUp(self):
        self.master = RawEthercatMaster()

    def test_build_and_parse_datagram_frame(self):
        # Create a BRD datagram for Register 0x0000 (Type/Rev, 2 bytes)
        dg = Datagram(
            cmd=CMD_BRD,
            idx=0x42,
            adp=0x0000,
            ado=0x0000,
            data=bytes([0x00, 0x00]),
            wkc=0
        )

        frame = self.master.build_frame([dg])
        
        # Check Ethernet Header (14 bytes)
        self.assertGreaterEqual(len(frame), 60) # Min Ethernet frame size
        ethertype = struct.unpack('>H', frame[12:14])[0]
        self.assertEqual(ethertype, ETH_TYPE_ETHERCAT)

        # Check EtherCAT Header
        ecat_hdr = struct.unpack('<H', frame[14:16])[0]
        ecat_len = ecat_hdr & 0x07FF
        ecat_type = (ecat_hdr >> 12) & 0x0F
        self.assertEqual(ecat_type, 1)

        # Parse frame
        parsed = self.master.parse_response(frame)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].cmd, CMD_BRD)
        self.assertEqual(parsed[0].idx, 0x42)
        self.assertEqual(parsed[0].ado, 0x0000)
        self.assertEqual(len(parsed[0].data), 2)

    def test_multi_datagram_packing(self):
        dg1 = Datagram(cmd=CMD_APRD, idx=1, adp=0x0000, ado=0x0130, data=bytes(2), wkc=0)
        dg2 = Datagram(cmd=CMD_FPWR, idx=2, adp=0x1000, ado=0x0120, data=bytes([0x02, 0x00]), wkc=0)

        frame = self.master.build_frame([dg1, dg2])
        parsed = self.master.parse_response(frame)

        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0].cmd, CMD_APRD)
        self.assertEqual(parsed[0].idx, 1)
        self.assertTrue(parsed[0].more_follows)
        self.assertEqual(parsed[1].cmd, CMD_FPWR)
        self.assertEqual(parsed[1].idx, 2)
        self.assertFalse(parsed[1].more_follows)

if __name__ == "__main__":
    unittest.main()
