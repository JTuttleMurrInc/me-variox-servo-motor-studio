"""
EtherCAT Slave Information (ESI) XML Parser for Vario-X Motor Drive.
Extracts Object Dictionary, DataTypes, SubItems, PDO mappings, and device identity metadata.
"""

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

@dataclass
class EsiSubItem:
    sub_index: int
    name: str
    data_type: str
    bit_size: int
    access: str
    default_value: Optional[str] = None
    pdo_mapping: Optional[str] = None

@dataclass
class EsiObject:
    index: int
    hex_index: str
    name: str
    data_type: str
    bit_size: int
    access: str
    category: str = "General"
    sub_items: Dict[int, EsiSubItem] = field(default_factory=dict)
    default_value: Optional[str] = None

@dataclass
class PdoEntry:
    index: int
    sub_index: int
    bit_len: int
    name: str
    data_type: str = ""

@dataclass
class PdoMapping:
    index: int
    hex_index: str
    name: str
    is_tx: bool # True = TxPDO (Inputs), False = RxPDO (Outputs)
    entries: List[PdoEntry] = field(default_factory=list)

    @property
    def total_bit_len(self) -> int:
        return sum(e.bit_len for e in self.entries)

    @property
    def total_byte_len(self) -> int:
        return (self.total_bit_len + 7) // 8

@dataclass
class EsiDeviceInfo:
    name: str
    vendor_id: int
    product_code: int
    revision_no: int
    order_number: str
    description: str
    objects: Dict[int, EsiObject] = field(default_factory=dict)
    tx_pdos: Dict[int, PdoMapping] = field(default_factory=dict)
    rx_pdos: Dict[int, PdoMapping] = field(default_factory=dict)

def _parse_int_str(val_str: Optional[str]) -> int:
    if not val_str:
        return 0
    val_str = val_str.strip()
    if val_str.startswith("#x") or val_str.startswith("#X"):
        return int(val_str[2:], 16)
    if val_str.startswith("0x") or val_str.startswith("0X"):
        return int(val_str[2:], 16)
    try:
        return int(val_str)
    except ValueError:
        return 0

class EsiParser:
    """Parses EtherCAT ESI XML files and indexes the Object Dictionary."""

    def __init__(self, xml_path: Optional[str] = None):
        self.xml_path = xml_path or self._find_default_esi()
        self.device_info: Optional[EsiDeviceInfo] = None
        if self.xml_path and os.path.exists(self.xml_path):
            self.load(self.xml_path)

    def load_default(self) -> EsiDeviceInfo:
        if self.xml_path and os.path.exists(self.xml_path):
            return self.load(self.xml_path)
        if not self.device_info:
            self.device_info = self._build_embedded_default()
        return self.device_info

    def _build_embedded_default(self) -> EsiDeviceInfo:
        """Built-in default standard Vario-X dictionary for standalone operation without external XML."""
        info = EsiDeviceInfo(
            name="Vario-X Motor Drive",
            vendor_id=0x000005D5,
            product_code=0x00B85381,
            revision_no=0x00000001,
            order_number="MD60-1-4000-F0S16M16-01",
            description="Murrelektronik Vario-X Integrated Servo Motor"
        )
        
        objects_def = [
            (0x1000, "Device Type", "UNSIGNED32", 32, "ro", "Communication / Identity"),
            (0x1008, "Manufacturer Device Name", "VISIBLE_STRING", 32, "ro", "Communication / Identity"),
            (0x1009, "Manufacturer Hardware Version", "VISIBLE_STRING", 32, "ro", "Communication / Identity"),
            (0x100A, "Manufacturer Software Version", "VISIBLE_STRING", 32, "ro", "Communication / Identity"),
            (0x1018, "Identity Object", "RECORD", 32, "ro", "Communication / Identity"),
            (0x2FEF, "LED Ring Control / Status", "RECORD", 32, "rw", "LED Ring Control (0x2FEF)"),
            (0x6040, "Controlword", "UNSIGNED16", 16, "rw", "CiA 402 Core Motion"),
            (0x6041, "Statusword", "UNSIGNED16", 16, "ro", "CiA 402 Core Motion"),
            (0x6060, "Modes of Operation", "INTEGER8", 8, "rw", "CiA 402 Core Motion"),
            (0x6061, "Modes of Operation Display", "INTEGER8", 8, "ro", "CiA 402 Core Motion"),
            (0x6064, "Position Actual Value", "INTEGER32", 32, "ro", "CiA 402 Core Motion"),
            (0x606C, "Velocity Actual Value", "INTEGER32", 32, "ro", "CiA 402 Core Motion"),
            (0x6077, "Torque Actual Value", "INTEGER16", 16, "ro", "CiA 402 Core Motion"),
            (0x6079, "DC Link Circuit Voltage", "UNSIGNED32", 32, "ro", "CiA 402 Core Motion"),
            (0x607A, "Target Position", "INTEGER32", 32, "rw", "CiA 402 Core Motion"),
            (0x6081, "Profile Velocity", "UNSIGNED32", 32, "rw", "CiA 402 Drive Profile"),
            (0x6083, "Profile Acceleration", "UNSIGNED32", 32, "rw", "CiA 402 Drive Profile"),
            (0x6084, "Profile Deceleration", "UNSIGNED32", 32, "rw", "CiA 402 Drive Profile"),
            (0x6085, "Quick Stop Deceleration", "UNSIGNED32", 32, "rw", "CiA 402 Drive Profile"),
            (0x608F, "Position Encoder Resolution", "RECORD", 32, "ro", "CiA 402 Drive Profile"),
            (0x60FF, "Target Velocity", "INTEGER32", 32, "rw", "CiA 402 Core Motion"),
            (0x60F7, "Manufacturer Diagnostics", "RECORD", 32, "ro", "Manufacturer Specific"),
        ]

        for idx, name, dtype, bits, access, cat in objects_def:
            obj = EsiObject(
                index=idx,
                hex_index=f"0x{idx:04X}",
                name=name,
                data_type=dtype,
                bit_size=bits,
                access=access,
                category=cat
            )
            if idx == 0x2FEF:
                obj.sub_items[0x01] = EsiSubItem(0x01, "LED_CTRL", "UNSIGNED32", 32, "rw")
                obj.sub_items[0x02] = EsiSubItem(0x02, "LED_Status", "UNSIGNED32", 32, "ro")
            elif idx == 0x1018:
                obj.sub_items[0x01] = EsiSubItem(0x01, "Vendor ID", "UNSIGNED32", 32, "ro")
                obj.sub_items[0x02] = EsiSubItem(0x02, "Product Code", "UNSIGNED32", 32, "ro")
                obj.sub_items[0x03] = EsiSubItem(0x03, "Revision Number", "UNSIGNED32", 32, "ro")
                obj.sub_items[0x04] = EsiSubItem(0x04, "Serial Number", "UNSIGNED32", 32, "ro")
            elif idx == 0x608F:
                obj.sub_items[0x01] = EsiSubItem(0x01, "Encoder Increments", "UNSIGNED32", 32, "ro")
                obj.sub_items[0x02] = EsiSubItem(0x02, "Motor Revolutions", "UNSIGNED32", 32, "ro")
            elif idx == 0x60F7:
                obj.sub_items[0x11] = EsiSubItem(0x11, "Internal Temperature", "UNSIGNED16", 16, "ro")
                obj.sub_items[0x17] = EsiSubItem(0x17, "Safe Torque Off (STO) State", "UNSIGNED16", 16, "ro")
            info.objects[idx] = obj

        return info

    @staticmethod
    def _find_default_esi() -> Optional[str]:
        candidates = [
            os.path.join(os.path.dirname(__file__), "..", "EtherCAT", "EtherCAT", "Vario-X MotorDrive_240828.xml"),
            os.path.join(os.path.dirname(__file__), "..", "EtherCAT", "EtherCAT", "Vario-X Drive.xml"),
            os.path.join(os.path.dirname(__file__), "..", "EtherCAT", "Vario-X MotorDrive_240828.xml"),
            os.path.join(os.path.dirname(__file__), "..", "EtherCAT", "Vario-X Drive.xml"),
        ]
        for c in candidates:
            abs_c = os.path.abspath(c)
            if os.path.exists(abs_c):
                return abs_c
        return None

    def load(self, xml_path: str) -> EsiDeviceInfo:
        self.xml_path = xml_path
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # 1. Parse DataTypes definitions
        data_types: Dict[str, List[EsiSubItem]] = {}
        for dt_elem in root.iter("DataType"):
            dt_name = dt_elem.findtext("Name")
            if not dt_name:
                continue
            subs: List[EsiSubItem] = []
            for s_elem in dt_elem.iter("SubItem"):
                s_idx_str = s_elem.findtext("SubIdx")
                s_idx = _parse_int_str(s_idx_str) if s_idx_str is not None else len(subs)
                s_name = s_elem.findtext("Name") or f"SubIndex {s_idx:03d}"
                s_type = s_elem.findtext("Type") or "UNKNOWN"
                s_bits = int(s_elem.findtext("BitSize") or 0)
                
                flags = s_elem.find("Flags")
                access = "ro"
                pdo = None
                if flags is not None:
                    access = flags.findtext("Access") or "ro"
                    pdo = flags.findtext("PdoMapping")
                
                subs.append(EsiSubItem(
                    sub_index=s_idx,
                    name=s_name,
                    data_type=s_type,
                    bit_size=s_bits,
                    access=access,
                    pdo_mapping=pdo
                ))
            if subs:
                data_types[dt_name] = subs

        # 2. Find device descriptions
        dev_elem = root.find(".//Device")
        dev_name = "Vario-X Motor Drive"
        vendor_id = 0x000005D5
        product_code = 0x00B85381
        rev_no = 1
        order_num = "V000-MDDC0-0000001"
        desc = "Murrelektronik Vario-X Integrated Servo Motor"

        if dev_elem is not None:
            type_elem = dev_elem.find("Type")
            if type_elem is not None:
                product_code = _parse_int_str(type_elem.attrib.get("ProductCode"))
                rev_no = _parse_int_str(type_elem.attrib.get("RevisionNo"))
                order_num = type_elem.text or order_num
            
            name_elem = dev_elem.find("Name")
            if name_elem is not None and name_elem.text:
                desc = name_elem.text
                dev_name = f"Vario-X Motor Drive ({desc})"

            vendor_elem = root.find(".//Vendor/Id")
            if vendor_elem is not None and vendor_elem.text:
                vendor_id = _parse_int_str(vendor_elem.text)

        info = EsiDeviceInfo(
            name=dev_name,
            vendor_id=vendor_id,
            product_code=product_code,
            revision_no=rev_no,
            order_number=order_num,
            description=desc
        )

        # 3. Parse Object Dictionary
        for obj in root.iter("Object"):
            idx_str = obj.findtext("Index") or ""
            idx = _parse_int_str(idx_str)
            name = obj.findtext("Name") or f"Object 0x{idx:04X}"
            dtype = obj.findtext("Type") or "UNKNOWN"
            bit_size = int(obj.findtext("BitSize") or 0)
            
            flags = obj.find("Flags")
            access = "ro"
            pdo_map = None
            if flags is not None:
                access = flags.findtext("Access") or "ro"
                pdo_map = flags.findtext("PdoMapping")

            def_val = obj.findtext("DefaultData")
            category = self._categorize_index(idx)

            esi_obj = EsiObject(
                index=idx,
                hex_index=f"0x{idx:04X}",
                name=name,
                data_type=dtype,
                bit_size=bit_size,
                access=access,
                category=category,
                default_value=def_val
            )

            # Check if type is defined in DataTypes
            if dtype in data_types:
                for dt_sub in data_types[dtype]:
                    esi_obj.sub_items[dt_sub.sub_index] = EsiSubItem(
                        sub_index=dt_sub.sub_index,
                        name=dt_sub.name,
                        data_type=dt_sub.data_type,
                        bit_size=dt_sub.bit_size,
                        access=dt_sub.access,
                        pdo_mapping=dt_sub.pdo_mapping
                    )
            
            # Also parse any inline SubItems if present
            sub_idx_counter = 0
            for sub in obj.iter("SubItem"):
                s_idx_str = sub.findtext("SubIdx")
                sub_idx = _parse_int_str(s_idx_str) if s_idx_str is not None else sub_idx_counter
                sub_name = sub.findtext("Name") or f"SubIndex {sub_idx:03d}"
                sub_type = sub.findtext("Type") or dtype
                sub_size = int(sub.findtext("BitSize") or 0)
                sub_flags = sub.find("Flags")
                sub_access = access
                sub_pdo = pdo_map
                if sub_flags is not None:
                    sub_access = sub_flags.findtext("Access") or sub_access
                    sub_pdo = sub_flags.findtext("PdoMapping") or sub_pdo
                
                sub_def = sub.findtext("DefaultData")
                if not sub_def:
                    info_elem = sub.find("Info")
                    if info_elem is not None:
                        sub_def = info_elem.findtext("DefaultData")

                if sub_idx in esi_obj.sub_items:
                    if sub_def:
                        esi_obj.sub_items[sub_idx].default_value = sub_def
                else:
                    esi_obj.sub_items[sub_idx] = EsiSubItem(
                        sub_index=sub_idx,
                        name=sub_name,
                        data_type=sub_type,
                        bit_size=sub_size,
                        access=sub_access,
                        default_value=sub_def,
                        pdo_mapping=sub_pdo
                    )
                sub_idx_counter += 1

            info.objects[idx] = esi_obj

        # 4. Parse TxPDOs (Inputs from slave to master)
        for pdo in root.iter("TxPdo"):
            idx = _parse_int_str(pdo.findtext("Index"))
            name = pdo.findtext("Name") or f"TxPDO 0x{idx:04X}"
            mapping = PdoMapping(index=idx, hex_index=f"0x{idx:04X}", name=name, is_tx=True)
            for entry in pdo.iter("Entry"):
                e_idx = _parse_int_str(entry.findtext("Index"))
                e_sub = _parse_int_str(entry.findtext("SubIndex"))
                e_bit = int(entry.findtext("BitLen") or 0)
                e_name = entry.findtext("Name") or f"Entry 0x{e_idx:04X}:{e_sub:02X}"
                e_type = entry.findtext("DataType") or ""
                mapping.entries.append(PdoEntry(e_idx, e_sub, e_bit, e_name, e_type))
            info.tx_pdos[idx] = mapping

        # 5. Parse RxPDOs (Outputs from master to slave)
        for pdo in root.iter("RxPdo"):
            idx = _parse_int_str(pdo.findtext("Index"))
            name = pdo.findtext("Name") or f"RxPDO 0x{idx:04X}"
            mapping = PdoMapping(index=idx, hex_index=f"0x{idx:04X}", name=name, is_tx=False)
            for entry in pdo.iter("Entry"):
                e_idx = _parse_int_str(entry.findtext("Index"))
                e_sub = _parse_int_str(entry.findtext("SubIndex"))
                e_bit = int(entry.findtext("BitLen") or 0)
                e_name = entry.findtext("Name") or f"Entry 0x{e_idx:04X}:{e_sub:02X}"
                e_type = entry.findtext("DataType") or ""
                mapping.entries.append(PdoEntry(e_idx, e_sub, e_bit, e_name, e_type))
            info.rx_pdos[idx] = mapping

        self.device_info = info
        return info

    @staticmethod
    def _categorize_index(index: int) -> str:
        if 0x1000 <= index <= 0x1FFF:
            return "Communication / Identity"
        elif 0x2000 <= index <= 0x5FFF:
            if index == 0x2FEF:
                return "LED Ring Control (0x2FEF)"
            return "Manufacturer Specific"
        elif 0x6000 <= index <= 0x6FFF:
            if index in (0x6040, 0x6041, 0x6060, 0x6061, 0x607A, 0x6064, 0x60FF, 0x606C, 0x6071, 0x6077):
                return "CiA 402 Core Motion"
            return "CiA 402 Drive Profile"
        return "General"

    def search(self, query: str) -> List[EsiObject]:
        if not self.device_info:
            return []
        q = query.lower()
        results = []
        for obj in self.device_info.objects.values():
            if q in obj.hex_index.lower() or q in obj.name.lower() or q in obj.category.lower():
                results.append(obj)
                continue
            for sub in obj.sub_items.values():
                if q in sub.name.lower():
                    results.append(obj)
                    break
        return results
