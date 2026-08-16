"""Macro read and decode (report 9 + report 10).

Three-step read flow (docs/unleash-reverse-engineering.md section 8.2):
1. MacroStatus (report 9, Direction=Read) -> bitmap of used macro indices
2. MacroNameData (report 10, Direction=Read, idx) -> UTF-8 name
3. MacroData (report 9, Direction=Read, idx, PackIndex 0..3) -> 4×256B
   payload reassembled into the 1032B MacroUsbFeatureReport template.

Macro actions use tag-based encoding with HID usage codes (not Windows
VK codes — verified on-device 2026-08-16, docs/research.md section
"巨集動作本體編碼").
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from . import protocol
from .hid_io import HIDError, Z12Device

# MacroStatus bitmap: resp[8] corresponds to macro index 1, resp[9] to 2,
# ... resp[107] to 100. (IL checks serialized[8..0x6B], i.e. indices 8..107)
_STATUS_START = 8
_STATUS_END = 8 + protocol.MACRO_TOTAL_COUNT  # exclusive

# Template layout after reassembling 4 packs (all_payload = serialized[8..1031]):
#   all_payload[0]      = LengthOfMacroName
#   all_payload[1..50]  = MacroName[50]
#   all_payload[51]     = RunMethodOfMacro
#   all_payload[52]     = RepeatTimeOfMacro
#   all_payload[53]     = TimeUnitOfMacro
#   all_payload[54..55] = LengthOfMacroData (uint16 LE)
#   all_payload[56..1022] = MacroData[967]
#   all_payload[1023]   = MacroStatusOfUse


@dataclass(frozen=True)
class MacroAction:
    """A single decoded macro action."""

    tag: str
    detail: str


@dataclass
class MacroInfo:
    """Full decoded macro."""

    index: int
    name: str
    run_method: int
    repeat_time: int
    time_unit: int
    data_length: int
    status_of_use: int
    actions: list[MacroAction]

    @property
    def run_method_name(self) -> str:
        return protocol.RUN_METHOD_NAMES.get(self.run_method, f"0x{self.run_method:02x}")

    @property
    def is_used(self) -> bool:
        return self.status_of_use == 0x01


def _parse_used_indices(resp: bytes) -> list[int]:
    """Parse MacroStatus bitmap: resp[8]==1 means macro #1 is in use."""
    used: list[int] = []
    for i in range(_STATUS_START, min(_STATUS_END, len(resp))):
        if resp[i] == 1:
            used.append(i - 7)
    return used


def read_macro_status(dev: Z12Device) -> list[int]:
    """Read MacroStatus (report 9) and return used macro indices.

    Unused slots are 0xFF; only a byte value of 1 counts as used. Stale
    hidapi responses drop used bits (1 -> 0xFF) rather than inventing
    them, so we union the ==1 bits across a few samples.
    """
    # MacroStatus: [0x09, 0xEA, Direction=Read, Status[263]...]
    payload = bytes([protocol.HEADER1, protocol.MACRO_DIR_READ]) + bytes(263)
    used: set[int] = set()
    for _ in range(3):
        resp = dev.transact(
            protocol.REPORT_MACRO_USB,
            protocol.REPORT_MACRO_USB_SIZE,
            payload,
            discard=4,
        )
        used.update(_parse_used_indices(resp))
        time.sleep(0.05)
    return sorted(used)


def _decode_name_bytes(resp: bytes) -> str:
    if len(resp) < 59:
        return ""
    name_count = resp[8]
    if name_count in (0, 0xFF):
        return ""
    name_bytes = resp[9 : 9 + min(name_count, 50)]
    return name_bytes.split(b"\x00")[0].decode("utf-8", errors="replace")


def read_macro_name(dev: Z12Device, macro_idx: int) -> str:
    """Read a macro's name (report 10).

    Report 10 often returns ResponseCommand 0xC1 even when the name
    payload is valid (docs/research.md cache notes). Accept a name when
    NameCount is 1..50, regardless of the status byte.
    """
    payload = bytearray(protocol.REPORT_MACRO_NAME_USB_SIZE - 1)
    payload[0] = protocol.HEADER1          # 0xEA
    payload[1] = protocol.HEADER2          # 0x02
    payload[2] = protocol.MACRO_DIR_READ   # Read
    payload[3] = macro_idx
    payload[4] = 0x00
    payload[5] = protocol.RESPONSE_FAIL    # keyboard fills 0xC0 on success

    last_name = ""
    for _ in range(2):
        resp = dev.transact(
            protocol.REPORT_MACRO_NAME_USB,
            protocol.REPORT_MACRO_NAME_USB_SIZE,
            bytes(payload),
            discard=3,
        )
        name = _decode_name_bytes(resp)
        if name:
            return name
        last_name = name
        time.sleep(0.1)
    return last_name


def _read_macro_data_pack(dev: Z12Device, macro_idx: int, pack_idx: int) -> bytes:
    """Read one 256B pack of macro data (report 9, MacroData).

    Report 9 often returns 0xC1 even when Data[] and checksum are valid
    (same cache behaviour as report 10). Accept a pack when
    Checksum == -(sum(Data)) & 0xFF.
    """
    payload = bytearray(protocol.REPORT_MACRO_USB_SIZE - 1)
    payload[0] = protocol.HEADER1          # 0xEA
    payload[1] = protocol.MACRO_DIR_READ   # Read
    payload[2] = protocol.MACRO_CMD_DATA   # 0x01 = Data
    payload[3] = macro_idx
    payload[4] = pack_idx
    payload[5] = 0x00                      # ResponseCommand (keyboard fills)
    payload[6] = 0x00                      # Checksum (keyboard fills)

    last_err = ""
    for _ in range(3):
        resp = dev.transact(
            protocol.REPORT_MACRO_USB,
            protocol.REPORT_MACRO_USB_SIZE,
            bytes(payload),
            discard=4,
        )
        data = bytes(resp[8 : 8 + protocol.MACRO_DATA_PAYLOAD])
        checksum = resp[7]
        calc = (-sum(data)) & 0xFF
        if checksum == calc:
            return data
        last_err = (
            f"macro data pack {pack_idx} for #{macro_idx}: "
            f"status 0x{resp[6]:02x} checksum 0x{checksum:02x}!=0x{calc:02x}"
        )
        time.sleep(0.15)
    raise HIDError(last_err)


def encode_key_taps(usages: list[int], delay_ms: int = 20) -> bytes:
    """Encode HID usages as delay-down-delay-up taps (on-device format)."""
    if delay_ms < 0 or delay_ms > 0xFFFF:
        raise ValueError("delay_ms must be 0-65535")
    out = bytearray()
    delay = bytes([0x01, delay_ms & 0xFF, (delay_ms >> 8) & 0xFF])
    for usage in usages:
        if not (0x04 <= usage <= 0x73 or 0xE0 <= usage <= 0xE7):
            raise ValueError(f"unsupported HID usage 0x{usage:02x} in macro tap")
        out += delay
        out.append(usage)
        out += delay
        out.append(usage | 0x80)
    if len(out) > 964:
        raise ValueError("macro action data exceeds firmware limit")
    return bytes(out)


def _build_write_template(
    name: str,
    action_bytes: bytes,
    run_method: int = 0x01,
) -> bytes:
    """Build the 1024B MacroUsbFeatureReport body (serialized[8..1031])."""
    name_b = name.encode("utf-8")
    if len(name_b) > 50:
        raise ValueError("macro name longer than 50 bytes UTF-8")
    if len(action_bytes) > 967:
        raise ValueError("macro action data longer than 967 bytes")
    payload = bytearray(1024)
    payload[0] = len(name_b)
    payload[1 : 1 + len(name_b)] = name_b
    payload[51] = run_method
    payload[52] = 0
    payload[53] = 0
    payload[54] = len(action_bytes) & 0xFF
    payload[55] = (len(action_bytes) >> 8) & 0xFF
    payload[56 : 56 + len(action_bytes)] = action_bytes
    payload[1023] = 0x01  # MacroStatusOfUse = in use
    return bytes(payload)


def write_macro(
    dev: Z12Device,
    macro_idx: int,
    name: str,
    action_bytes: bytes,
    run_method: int = 0x01,
) -> MacroInfo:
    """Write a macro as 4 MacroData packs (report 9, Direction=Write).

    Verified on-device 2026-08-16: slot #3, name z12test, F13 tap.
    Each pack is SET once. 150 ms between packs (Unleash ExecuteReport).

    Raises:
        ValueError: bad index / name / payload.
        HIDError: a pack failed twice.
    """
    if macro_idx < 1 or macro_idx > protocol.MACRO_TOTAL_COUNT:
        raise ValueError(f"macro index must be 1-{protocol.MACRO_TOTAL_COUNT}")
    template = _build_write_template(name, action_bytes, run_method)
    for pack_idx in range(protocol.MACRO_PACK_COUNT):
        chunk = template[pack_idx * 256 : (pack_idx + 1) * 256]
        if not _write_macro_pack(dev, macro_idx, pack_idx, chunk):
            time.sleep(0.15)
            if not _write_macro_pack(dev, macro_idx, pack_idx, chunk):
                raise HIDError(
                    f"macro write pack {pack_idx} for #{macro_idx} failed twice"
                )
        time.sleep(0.15)
    return read_macro(dev, macro_idx)


def _write_macro_pack(
    dev: Z12Device, macro_idx: int, pack_idx: int, data256: bytes
) -> bool:
    chk = (-sum(data256)) & 0xFF
    payload = bytearray(protocol.REPORT_MACRO_USB_SIZE - 1)
    payload[0] = protocol.HEADER1
    payload[1] = protocol.MACRO_DIR_WRITE
    payload[2] = protocol.MACRO_CMD_DATA
    payload[3] = macro_idx
    payload[4] = pack_idx
    payload[5] = 0x00
    payload[6] = chk
    payload[7 : 7 + protocol.MACRO_DATA_PAYLOAD] = data256
    resp = dev.send_once(
        protocol.REPORT_MACRO_USB,
        protocol.REPORT_MACRO_USB_SIZE,
        bytes(payload),
        get_count=3,
        first_wait=0.15,
    )
    # GET payload is often stale; accept C0, or echoed data matching our pack.
    echo = bytes(resp[8 : 8 + protocol.MACRO_DATA_PAYLOAD])
    if resp[6] == protocol.RESPONSE_SUCCESS:
        return True
    return resp[7] == chk and echo == data256


def read_macro(dev: Z12Device, macro_idx: int) -> MacroInfo:
    """Read a complete macro: status, name, and 4 data packs.

    Raises:
        HIDError: if any data pack returns non-success.
    """
    name = read_macro_name(dev, macro_idx)
    time.sleep(0.1)

    all_payload = bytearray()
    for pack_idx in range(protocol.MACRO_PACK_COUNT):
        data = _read_macro_data_pack(dev, macro_idx, pack_idx)
        all_payload.extend(data)
        time.sleep(0.15)

    return _parse_macro_template(macro_idx, name, all_payload)


def _parse_macro_template(idx: int, name: str, all_payload: bytes) -> MacroInfo:
    """Parse the reassembled 1024B template (serialized[8..1031])."""
    run_method = all_payload[51] if len(all_payload) > 51 else 0
    repeat_time = all_payload[52] if len(all_payload) > 52 else 0
    time_unit = all_payload[53] if len(all_payload) > 53 else 0
    data_length = (all_payload[54] | (all_payload[55] << 8)) if len(all_payload) > 55 else 0
    status_of_use = all_payload[1023] if len(all_payload) > 1023 else 0

    # MacroData[967] starts at all_payload[56]
    body = all_payload[56 : 56 + 967]
    actual_body = body[:data_length] if data_length > 0 else body
    actions = decode_macro_actions(actual_body)

    return MacroInfo(
        index=idx,
        name=name,
        run_method=run_method,
        repeat_time=repeat_time,
        time_unit=time_unit,
        data_length=data_length,
        status_of_use=status_of_use,
        actions=actions,
    )


def decode_macro_actions(data: bytes) -> list[MacroAction]:
    """Decode tag-based macro action encoding.

    Encoding (docs/research.md "巨集動作本體編碼"):
      0x01 + 16-bit LE ms  -> delay
      0x04 0x00            -> no delay (rare; 0x04 usually = key A)
      0x03 + 16-bit usage  -> media/system key (3 bytes)
      single byte 0x04-0x73 -> HID usage key DOWN
      single byte | 0x80   -> HID usage key UP (0x84-0xF3)
      0x7A/0x7B/0x7C       -> mouse L/R/M down
      0xFA/0xFB/0xFC       -> mouse L/R/M up
      0xF8/0x78            -> mouse wheel
      0x80 + X + Y         -> mouse move (5 bytes: 0x80 Xlo Xhi Ylo Yhi)
      8 consecutive 0x00   -> end of actions
    """
    actions: list[MacroAction] = []
    i = 0
    mouse_tags = {0x7A, 0x7B, 0x7C, 0xFA, 0xFB, 0xFC, 0xF8, 0x78}

    while i < len(data):
        b = data[i]

        # End: 8 consecutive zeros
        if b == 0x00 and all(x == 0 for x in data[i : i + 8]):
            break

        # Delay: 0x01 + 16-bit LE ms
        if b == 0x01:
            if i + 2 < len(data):
                ms = data[i + 1] | (data[i + 2] << 8)
                actions.append(MacroAction("DELAY", f"{ms}ms"))
                i += 3
            else:
                actions.append(MacroAction("DELAY?", f"truncated @ {i}"))
                break
            continue

        # Media/system key: 0x03 + 16-bit HID usage
        if b == 0x03:
            if i + 2 < len(data):
                usage = data[i + 1] | (data[i + 2] << 8)
                actions.append(MacroAction("MEDIA", f"HID usage 0x{usage:04x}"))
                i += 3
            else:
                actions.append(MacroAction("MEDIA?", f"truncated @ {i}"))
                break
            continue

        # Mouse buttons down
        if b in (0x7A, 0x7B, 0x7C):
            btn = {0x7A: "Left", 0x7B: "Right", 0x7C: "Middle"}[b]
            actions.append(MacroAction("MOUSE_DOWN", btn))
            i += 1
            continue

        # Mouse buttons up
        if b in (0xFA, 0xFB, 0xFC):
            btn = {0xFA: "Left", 0xFB: "Right", 0xFC: "Middle"}[b]
            actions.append(MacroAction("MOUSE_UP", btn))
            i += 1
            continue

        # Mouse wheel
        if b in (0xF8, 0x78):
            direction = "up" if b == 0xF8 else "down"
            actions.append(MacroAction("WHEEL", direction))
            i += 1
            continue

        # Key up: usage | 0x80 (range 0x81-0xF3, excluding mouse tags)
        if b & 0x80 and b not in mouse_tags:
            usage = b & 0x7F
            if usage == 0x00:
                # 0x80 could be mouse move (followed by 4 bytes X/Y)
                if i + 4 < len(data):
                    x = data[i + 1] | (data[i + 2] << 8)
                    y = data[i + 3] | (data[i + 4] << 8)
                    actions.append(MacroAction("MOUSE_MOVE", f"x={x} y={y}"))
                    i += 5
                else:
                    actions.append(MacroAction("UNKNOWN", f"0x{b:02x} @ {i}"))
                    i += 1
            else:
                key_name = protocol.HID_USAGE_NAMES.get(usage, f"HID 0x{usage:02x}")
                actions.append(MacroAction("KEY_UP", key_name))
                i += 1
            continue

        # Key down: HID usage 0x04-0x73 or modifier 0xE0-0xE7
        if (0x04 <= b <= 0x73) or (0xE0 <= b <= 0xE7):
            key_name = protocol.HID_USAGE_NAMES.get(b, f"HID 0x{b:02x}")
            actions.append(MacroAction("KEY_DOWN", key_name))
            i += 1
            continue

        # 0x04 0x00 with a delay following -> key A then padding
        if b == 0x04 and i + 2 < len(data) and data[i + 1] == 0x00 and data[i + 2] == 0x01:
            actions.append(MacroAction("KEY_DOWN", "A"))
            i += 1
            continue

        # Fallback
        actions.append(MacroAction("UNKNOWN", f"0x{b:02x} @ {i}"))
        i += 1

    return actions
