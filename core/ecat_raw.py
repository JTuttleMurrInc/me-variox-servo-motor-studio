"""
Layer-2 Npcap EtherCAT Raw Datagram Engine.
Direct raw frame injection and reception over Ethernet using wpcap.dll (Npcap).
"""

import ctypes
import os
import struct
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict

ETH_TYPE_ETHERCAT = 0x88A4

# EtherCAT Commands
CMD_APRD = 0x01  # Auto-Increment Physical Read
CMD_APWR = 0x02  # Auto-Increment Physical Write
CMD_FPRD = 0x04  # Configured Address Physical Read
CMD_FPWR = 0x05  # Configured Address Physical Write
CMD_BRD  = 0x07  # Broadcast Read
CMD_BWR  = 0x08  # Broadcast Write
CMD_LRD  = 0x0A  # Logical Read
CMD_LWR  = 0x0B  # Logical Write
CMD_LRW  = 0x0C  # Logical Read/Write

# ESC Standard Registers
REG_TYPE_REV      = 0x0000 # Type & Revision (2 bytes)
REG_BUILD         = 0x0002 # Build (2 bytes)
REG_FMMU_COUNT    = 0x0004 # Supported FMMUs (1 byte)
REG_SM_COUNT      = 0x0005 # Supported SyncManagers (1 byte)
REG_RAM_SIZE      = 0x0006 # RAM Size in KB (1 byte)
REG_STATION_ADDR  = 0x0010 # Configured Station Address (2 bytes)
REG_STATION_ALIAS = 0x0012 # Configured Station Alias (2 bytes)
REG_DL_STATUS     = 0x0110 # Data Link Status (2 bytes)
REG_AL_CONTROL    = 0x0120 # AL Control (2 bytes)
REG_AL_STATUS     = 0x0130 # AL Status (2 bytes)
REG_AL_STATUS_CODE= 0x0134 # AL Status Code (2 bytes)
REG_EEPROM_CTRL   = 0x0500 # EEPROM Control/Status
REG_EEPROM_ADDR   = 0x0504 # EEPROM Address
REG_EEPROM_DATA   = 0x0508 # EEPROM Data
REG_SM0_CONFIG    = 0x0800 # SyncManager 0 (Mailbox Out)
REG_SM1_CONFIG    = 0x0808 # SyncManager 1 (Mailbox In)
REG_SM2_CONFIG    = 0x0810 # SyncManager 2 (Process Data Out / RxPDO)
REG_SM3_CONFIG    = 0x0818 # SyncManager 3 (Process Data In / TxPDO)

# AL States
AL_STATE_INIT     = 0x01
AL_STATE_PREOP    = 0x02
AL_STATE_BOOTSTRAP= 0x03
AL_STATE_SAFEOP   = 0x04
AL_STATE_OP       = 0x08
AL_STATE_ERROR    = 0x10

AL_STATE_NAMES = {
    AL_STATE_INIT: "INIT",
    AL_STATE_PREOP: "PRE-OP",
    AL_STATE_BOOTSTRAP: "BOOT",
    AL_STATE_SAFEOP: "SAFE-OP",
    AL_STATE_OP: "OP",
}

# Npcap Structures
class pcap_pkthdr(ctypes.Structure):
    _fields_ = [
        ("tv_sec", ctypes.c_long),
        ("tv_usec", ctypes.c_long),
        ("caplen", ctypes.c_uint),
        ("len", ctypes.c_uint)
    ]

class pcap_addr(ctypes.Structure):
    pass
pcap_addr._fields_ = [
    ("next", ctypes.POINTER(pcap_addr)),
    ("addr", ctypes.c_void_p),
    ("netmask", ctypes.c_void_p),
    ("broadaddr", ctypes.c_void_p),
    ("dstaddr", ctypes.c_void_p)
]

class pcap_if(ctypes.Structure):
    pass
pcap_if._fields_ = [
    ("next", ctypes.POINTER(pcap_if)),
    ("name", ctypes.c_char_p),
    ("description", ctypes.c_char_p),
    ("addresses", ctypes.POINTER(pcap_addr)),
    ("flags", ctypes.c_uint)
]

def load_npcap_lib():
    paths = [
        r"C:\Windows\System32\Npcap\wpcap.dll",
        r"C:\Windows\System32\wpcap.dll",
        r"C:\Windows\SysWOW64\Npcap\wpcap.dll"
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                lib = ctypes.cdll.LoadLibrary(p)
                lib.pcap_findalldevs.argtypes = [ctypes.POINTER(ctypes.POINTER(pcap_if)), ctypes.c_char_p]
                lib.pcap_findalldevs.restype = ctypes.c_int
                lib.pcap_freealldevs.argtypes = [ctypes.POINTER(pcap_if)]
                lib.pcap_freealldevs.restype = None
                lib.pcap_open_live.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_char_p]
                lib.pcap_open_live.restype = ctypes.c_void_p
                lib.pcap_sendpacket.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
                lib.pcap_sendpacket.restype = ctypes.c_int
                lib.pcap_next_ex.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.POINTER(pcap_pkthdr)), ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte))]
                lib.pcap_next_ex.restype = ctypes.c_int
                lib.pcap_close.argtypes = [ctypes.c_void_p]
                lib.pcap_close.restype = None
                return lib
            except Exception:
                pass
    return None

@dataclass
class AdapterInfo:
    name: str
    description: str

@dataclass
class Datagram:
    cmd: int
    idx: int
    adp: int
    ado: int
    data: bytes
    wkc: int
    more_follows: bool = False

class RawEthercatMaster:
    """Low-level raw EtherCAT Master over Npcap."""

    def __init__(self, adapter_name: Optional[str] = None):
        self.wpcap = load_npcap_lib()
        self.adapter_name = adapter_name
        self.handle = None
        self.idx_counter = 0
        self.src_mac = bytes([0x00, 0x1B, 0x21, 0xDE, 0xAD, 0x01])
        self.dst_mac = bytes([0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])

    @classmethod
    def list_adapters(cls) -> List[AdapterInfo]:
        lib = load_npcap_lib()
        if not lib:
            return []
        alldevs = ctypes.POINTER(pcap_if)()
        errbuf = ctypes.create_string_buffer(256)
        ret = lib.pcap_findalldevs(ctypes.byref(alldevs), errbuf)
        res = []
        if ret == 0 and alldevs:
            curr = alldevs
            while curr:
                n = curr.contents.name.decode('utf-8', errors='ignore') if curr.contents.name else ""
                d = curr.contents.description.decode('utf-8', errors='ignore') if curr.contents.description else ""
                res.append(AdapterInfo(name=n, description=d))
                curr = curr.contents.next
            lib.pcap_freealldevs(alldevs)
        return res

    def open(self, adapter_name: Optional[str] = None) -> bool:
        if adapter_name:
            self.adapter_name = adapter_name
        if not self.adapter_name or not self.wpcap:
            return False
        
        self.close()
        errbuf = ctypes.create_string_buffer(256)
        # SnapLen 65536, Promisc 1, Timeout 20ms
        self.handle = self.wpcap.pcap_open_live(
            self.adapter_name.encode('ascii'),
            65536,
            1,
            20,
            errbuf
        )
        return bool(self.handle)

    def close(self):
        if self.handle and self.wpcap:
            self.wpcap.pcap_close(self.handle)
            self.handle = None

    def _next_idx(self) -> int:
        self.idx_counter = (self.idx_counter + 1) & 0xFF
        return self.idx_counter

    def build_frame(self, datagrams: List[Datagram]) -> bytes:
        dgram_bytes = bytearray()
        for i, dg in enumerate(datagrams):
            more = 1 if i < len(datagrams) - 1 else 0
            dlen = len(dg.data)
            # Datagram Header: Cmd (1), Idx (1), ADP (2), ADO (2), Len+More (2), IRQ (2)
            hdr = struct.pack('<BBHHH',
                dg.cmd,
                dg.idx,
                dg.adp,
                dg.ado,
                (dlen & 0x07FF) | (more << 15)
            )
            dgram_bytes.extend(hdr)
            dgram_bytes.extend(struct.pack('<H', 0)) # IRQ
            dgram_bytes.extend(dg.data)
            dgram_bytes.extend(struct.pack('<H', 0)) # WKC placeholder

        # EtherCAT Header: Length of datagram payload (11 bits) + Reserved (1 bit) + Type 1 (4 bits)
        ecat_len = len(dgram_bytes)
        ecat_hdr = struct.pack('<H', (ecat_len & 0x07FF) | (1 << 12))

        # Ethernet Header
        eth_hdr = self.dst_mac + self.src_mac + struct.pack('>H', ETH_TYPE_ETHERCAT)
        frame = eth_hdr + ecat_hdr + bytes(dgram_bytes)
        if len(frame) < 60:
            frame += b'\x00' * (60 - len(frame))
        return frame

    def parse_response(self, raw_pkt: bytes) -> List[Datagram]:
        if len(raw_pkt) < 14:
            return []
        ethertype = struct.unpack('>H', raw_pkt[12:14])[0]
        if ethertype != ETH_TYPE_ETHERCAT:
            return []
        
        if len(raw_pkt) < 16:
            return []
        ecat_hdr = struct.unpack('<H', raw_pkt[14:16])[0]
        ecat_len = ecat_hdr & 0x07FF
        ecat_type = (ecat_hdr >> 12) & 0x0F
        if ecat_type != 1:
            return []

        offset = 16
        end_offset = min(len(raw_pkt), 16 + ecat_len)
        results = []

        while offset + 12 <= end_offset:
            cmd, idx, adp, ado, len_flags = struct.unpack('<BBHHH', raw_pkt[offset:offset+8])
            # irq at offset+8..offset+10
            dlen = len_flags & 0x07FF
            more = bool(len_flags & 0x8000)
            
            data_start = offset + 10
            data_end = data_start + dlen
            wkc_start = data_end
            wkc_end = wkc_start + 2

            if wkc_end > len(raw_pkt):
                break

            data = raw_pkt[data_start:data_end]
            wkc = struct.unpack('<H', raw_pkt[wkc_start:wkc_end])[0]
            results.append(Datagram(cmd=cmd, idx=idx, adp=adp, ado=ado, data=data, wkc=wkc, more_follows=more))
            offset = wkc_end

        return results

    def transact(self, datagrams: List[Datagram], timeout_ms: int = 50) -> List[Datagram]:
        if not self.handle:
            return []

        frame = self.build_frame(datagrams)
        self.wpcap.pcap_sendpacket(self.handle, ctypes.c_char_p(frame), len(frame))

        start_t = time.perf_counter()
        header = ctypes.POINTER(pcap_pkthdr)()
        pkt_data = ctypes.POINTER(ctypes.c_ubyte)()

        expected_idx = datagrams[0].idx if datagrams else -1
        deadline = start_t + (timeout_ms / 1000.0)

        while time.perf_counter() < deadline:
            ret = self.wpcap.pcap_next_ex(self.handle, ctypes.byref(header), ctypes.byref(pkt_data))
            if ret == 1:
                raw_len = header.contents.len
                pkt = bytes(ctypes.string_at(pkt_data, raw_len))
                # Ignore our own outgoing echo frames
                if len(pkt) >= 12 and pkt[6:12] == self.src_mac:
                    continue
                parsed = self.parse_response(pkt)
                if parsed and (expected_idx < 0 or parsed[0].idx == expected_idx):
                    return parsed
            elif ret < 0:
                break
            time.sleep(0.0005)

        return []

    # High-level raw primitives
    def brd(self, ado: int, length: int) -> Tuple[bytes, int]:
        """Broadcast Read."""
        idx = self._next_idx()
        req = Datagram(cmd=CMD_BRD, idx=idx, adp=0x0000, ado=ado, data=bytes(length), wkc=0)
        res = self.transact([req])
        if res:
            return (res[0].data, res[0].wkc)
        return (b"", 0)

    def bwr(self, ado: int, data: bytes) -> int:
        """Broadcast Write."""
        idx = self._next_idx()
        req = Datagram(cmd=CMD_BWR, idx=idx, adp=0x0000, ado=ado, data=data, wkc=0)
        res = self.transact([req])
        if res:
            return res[0].wkc
        return 0

    def aprd(self, position: int, ado: int, length: int) -> Tuple[bytes, int]:
        """Auto-increment Physical Read."""
        idx = self._next_idx()
        adp = (-(position & 0xFFFF)) & 0xFFFF
        req = Datagram(cmd=CMD_APRD, idx=idx, adp=adp, ado=ado, data=bytes(length), wkc=0)
        res = self.transact([req])
        if res:
            return (res[0].data, res[0].wkc)
        return (b"", 0)

    def apwr(self, position: int, ado: int, data: bytes) -> int:
        """Auto-increment Physical Write."""
        idx = self._next_idx()
        adp = (-(position & 0xFFFF)) & 0xFFFF
        req = Datagram(cmd=CMD_APWR, idx=idx, adp=adp, ado=ado, data=data, wkc=0)
        res = self.transact([req])
        if res:
            return res[0].wkc
        return 0

    def fprd(self, station_addr: int, ado: int, length: int) -> Tuple[bytes, int]:
        """Configured Address Physical Read."""
        idx = self._next_idx()
        req = Datagram(cmd=CMD_FPRD, idx=idx, adp=station_addr, ado=ado, data=bytes(length), wkc=0)
        res = self.transact([req])
        if res:
            return (res[0].data, res[0].wkc)
        return (b"", 0)

    def fpwr(self, station_addr: int, ado: int, data: bytes) -> int:
        """Configured Address Physical Write."""
        idx = self._next_idx()
        req = Datagram(cmd=CMD_FPWR, idx=idx, adp=station_addr, ado=ado, data=data, wkc=0)
        res = self.transact([req])
        if res:
            return res[0].wkc
        return 0

    def fpwr_multi(self, writes: List[Tuple[int, int, bytes]]) -> int:
        """
        Configured Address Physical Write across multiple target slaves
        packaged within a SINGLE multi-datagram Ethernet packet.
        """
        if not writes:
            return 0
        datagrams = []
        for station_addr, ado, data in writes:
            idx = self._next_idx()
            datagrams.append(Datagram(cmd=CMD_FPWR, idx=idx, adp=station_addr & 0xFFFF, ado=ado, data=data, wkc=0))
        res = self.transact(datagrams)
        total_wkc = sum(r.wkc for r in res) if res else 0
        return total_wkc
