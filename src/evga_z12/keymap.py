"""Keymap read and decode (report 4, KeyFunctionRam).

Reads the KeyDefine (4 bytes: Function + Parameter1/2/3) for each
physical key position. The 121 on-device valid positions are in
protocol.LED_KEY_POSITIONS (0x00-0x78). Both Primary (main) and Secondary
(Shift/FN) layers use the same position table, selected by SubCommand2.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import protocol
from .hid_io import HIDError, Z12Device

# Reverse lookups for binding parser
_HID_NAME_TO_USAGE = {name.lower(): code for code, name in protocol.HID_USAGE_NAMES.items()}
_CONSUMER_NAME_TO_CODE = {
    name.lower(): code for code, name in protocol.HID_CONSUMER_NAMES.items()
}
_MOD_ALIASES = {
    "lctrl": 0x01, "ctrl": 0x01, "control": 0x01,
    "lshift": 0x02, "shift": 0x02,
    "lalt": 0x04, "alt": 0x04, "option": 0x04, "opt": 0x04,
    "lgui": 0x08, "lwin": 0x08, "win": 0x08, "cmd": 0x08,
    "command": 0x08, "super": 0x08,
    "rctrl": 0x10,
    "rshift": 0x20,
    "ralt": 0x40, "altgr": 0x40,
    "rgui": 0x80, "rwin": 0x80,
}
_HID_ALIASES = {
    "esc": 0x29, "escape": 0x29,
    "return": 0x28, "enter": 0x28,
    "space": 0x2C, "spacebar": 0x2C,
    "bksp": 0x2A, "backspace": 0x2A,
    "del": 0x4C, "delete": 0x4C,
    "ins": 0x49, "insert": 0x49,
    "pgup": 0x4B, "pageup": 0x4B,
    "pgdn": 0x4E, "pagedown": 0x4E,
}

# Role keys: firmware treats these as identity, not remappable outputs.
# Writing untested Function 0x04/0x05 parameters is forbidden (function-codes.md).
_PROTECTED_POSITIONS = {0x00, 0x6C}  # GameMode, FN

# Which positions to scan in dump_keymap(). Excludes LED zones (0xA0+)
# which are not physical keys and return 0xC1 on keymap read.
SCAN_POSITIONS = sorted(protocol.LED_KEY_POSITIONS.keys())


@dataclass(frozen=True)
class KeyDefine:
    """Decoded KeyDefine (report 4 bytes 8-11)."""

    function: int
    param1: int
    param2: int
    param3: int

    @property
    def function_name(self) -> str:
        return protocol.KEY_FUNCTION_NAMES.get(self.function, f"0x{self.function:02x}")

    @property
    def is_default(self) -> bool:
        """True if this key maps to itself (KeyboardEmulation, no modifier,
        key2 = 0, and key1 matches the HID usage for this position).

        We cannot always determine this without a position->HID-usage map,
        so this is a best-effort heuristic for display purposes.
        """
        return (
            self.function == 0x00
            and self.param1 == 0x00
            and self.param3 == 0x00
        )

    def describe(self) -> str:
        """Human-readable description of the binding."""
        fn = self.function

        if fn == 0x00:  # KeyboardEmulation
            mods = [name for bit, name in protocol.MODIFIER_BITS.items() if self.param1 & bit]
            key1 = protocol.HID_USAGE_NAMES.get(self.param2, f"HID 0x{self.param2:02x}")
            mod_str = "+".join(mods) + "+" if mods else ""
            if self.param3:
                key2 = protocol.HID_USAGE_NAMES.get(self.param3, f"HID 0x{self.param3:02x}")
                return f"{mod_str}{key1}+{key2}"
            return f"{mod_str}{key1}"

        if fn == 0x02:  # Consumer
            code = self.param1 | (self.param2 << 8)
            name = protocol.HID_CONSUMER_NAMES.get(code, f"consumer 0x{code:04x}")
            return name

        if fn == 0x03:  # Macro
            run = protocol.RUN_METHOD_NAMES.get(self.param2, f"0x{self.param2:02x}")
            return f"macro#{self.param1} runMethod={run} repeat={self.param3}"

        if fn == 0x04:  # FnKey
            return "FnKey"

        if fn == 0x05:  # EKey
            return "EKey (GameMode toggle)"

        if fn == 0xFF:  # Disable
            return "disabled"

        # Profile1-9, brightness, etc.
        return self.function_name


@dataclass(frozen=True)
class KeyEntry:
    """A keymap read result for one position."""

    position: int
    position_name: str
    key_define: KeyDefine
    raw: bytes


def _build_read_payload(position: int, layer: int) -> bytes:
    """Build report 4 keymap read payload (bytes 1-16)."""
    return bytes([
        protocol.HEADER1,        # 0xEA
        protocol.HEADER2,        # 0x02
        protocol.CMD_KEY_FUNCTION_RAM,  # 0x07
        protocol.SUB_READ,       # 0x01
        layer,                   # 0x00=Primary, 0x01=Secondary
        0x00,
        position,
    ]) + bytes(9)


def read_key(dev: Z12Device, position: int, layer: int = protocol.SUB_PRIMARY_KEY) -> KeyEntry:
    """Read a single key's KeyDefine.

    Args:
        dev: Open Z12Device.
        position: LedKeyPosition (0x00-0x78).
        layer: SUB_PRIMARY_KEY (0x00) or SUB_SECONDARY_KEY (0x01).

    Returns:
        KeyEntry with decoded KeyDefine.

    Raises:
        HIDError: if the device returns a non-success status.
    """
    payload = _build_read_payload(position, layer)
    resp = dev.transact_report4(payload)
    status = resp[6]
    if status != protocol.RESPONSE_SUCCESS:
        raise HIDError(  # noqa: TRY301 - re-raise with context
            f"read_key(position=0x{position:02x}): status 0x{status:02x}"
        ) from None
    return KeyEntry(
        position=position,
        position_name=protocol.LED_KEY_POSITIONS.get(position, f"0x{position:02x}"),
        key_define=KeyDefine(
            function=resp[8],
            param1=resp[9],
            param2=resp[10],
            param3=resp[11],
        ),
        raw=bytes(resp),
    )


def _build_write_payload(
    position: int, key_define: KeyDefine, layer: int
) -> bytes:
    """Build report 4 keymap write payload (bytes 1-16).

    Layout matches the on-device write that succeeded in test_write.py:
    EA 02 07 00 <layer> 00 <pos> <fn> <p1> <p2> <p3> + 5 zeros.
    """
    return bytes([
        protocol.HEADER1,
        protocol.HEADER2,
        protocol.CMD_KEY_FUNCTION_RAM,
        protocol.SUB_WRITE,
        layer,
        0x00,
        position,
        key_define.function,
        key_define.param1,
        key_define.param2,
        key_define.param3,
    ]) + bytes(5)


def write_key(
    dev: Z12Device,
    position: int,
    key_define: KeyDefine,
    layer: int = protocol.SUB_PRIMARY_KEY,
) -> KeyEntry:
    """Write a key's KeyDefine (one SET_FEATURE), then read it back.

    Raises:
        ValueError: protected position (GameMode / FN) or role function.
        HIDError: device returned non-success.
    """
    if position in _PROTECTED_POSITIONS:
        name = protocol.LED_KEY_POSITIONS.get(position, f"0x{position:02x}")
        raise ValueError(f"refusing to remap protected key {name} (0x{position:02x})")
    if key_define.function in (0x04, 0x05):
        raise ValueError("refusing to write FnKey/EKey (untested parameters)")

    payload = _build_write_payload(position, key_define, layer)
    resp = dev.send_once_report4(payload)
    status = resp[6]
    if status != protocol.RESPONSE_SUCCESS:
        raise HIDError(f"write_key(position=0x{position:02x}): status 0x{status:02x}")
    return read_key(dev, position, layer)


def parse_binding(text: str) -> KeyDefine:
    """Parse a binding string into a KeyDefine.

    Examples:
        F13
        LCtrl+C
        Ctrl+Shift+C
        disable
        macro:6
        Mute
        0x68
    """
    raw = text.strip()
    if not raw:
        raise ValueError("empty binding")
    lowered = raw.lower()

    if lowered in {"disable", "disabled", "off", "none"}:
        return KeyDefine(0xFF, 0, 0, 0)

    if lowered.startswith("macro:") or lowered.startswith("macro#"):
        idx_str = raw.split(":", 1)[-1] if ":" in raw else raw.split("#", 1)[-1]
        try:
            idx = int(idx_str, 0)
        except ValueError as exc:
            raise ValueError(f"invalid macro index: {idx_str!r}") from exc
        if idx < 1 or idx > protocol.MACRO_TOTAL_COUNT:
            raise ValueError(f"macro index must be 1-{protocol.MACRO_TOTAL_COUNT}")
        # Default runMethod = OneShot_KeyRelease (0x01), matching E1–E5.
        return KeyDefine(0x03, idx, 0x01, 0)

    if lowered in {"fnkey", "fn", "ekey"}:
        raise ValueError("FnKey/EKey are role markers and cannot be assigned")

    consumer = _CONSUMER_NAME_TO_CODE.get(lowered)
    if consumer is not None:
        return KeyDefine(0x02, consumer & 0xFF, (consumer >> 8) & 0xFF, 0)

    parts = [p for p in raw.split("+") if p]
    if not parts:
        raise ValueError(f"invalid binding: {text!r}")

    modifier = 0
    keys: list[int] = []
    for part in parts:
        token = part.strip()
        bit = _MOD_ALIASES.get(token.lower())
        if bit is not None:
            modifier |= bit
            continue
        usage = _parse_hid_usage(token)
        keys.append(usage)

    if not keys and modifier:
        # Pure modifier (e.g. LCtrl) — KeyDefine stores it in Parameter1.
        return KeyDefine(0x00, modifier, 0, 0)
    if not keys:
        raise ValueError(f"invalid binding: {text!r}")
    if len(keys) > 2:
        raise ValueError("at most two simultaneous keys plus modifiers")
    key1 = keys[0]
    key2 = keys[1] if len(keys) > 1 else 0
    return KeyDefine(0x00, modifier, key1, key2)


def _parse_hid_usage(token: str) -> int:
    if token.lower().startswith("0x"):
        value = int(token, 16)
        if not (0x00 <= value <= 0xFF):
            raise ValueError(f"HID usage out of range: {token}")
        return value
    usage = _HID_ALIASES.get(token.lower())
    if usage is not None:
        return usage
    usage = _HID_NAME_TO_USAGE.get(token.lower())
    if usage is not None:
        return usage
    raise ValueError(f"unknown key: {token!r}")


def dump_keymap(dev: Z12Device, layer: int = protocol.SUB_PRIMARY_KEY) -> list[KeyEntry]:
    """Read all 121 valid key positions.

    Positions that return 0xC1 (invalid) are silently skipped — these
    are either LED zones or positions the firmware doesn't expose.
    """
    results: list[KeyEntry] = []
    for pos in SCAN_POSITIONS:
        try:
            entry = read_key(dev, pos, layer)
        except HIDError:
            try:
                entry = read_key(dev, pos, layer)
            except HIDError:
                continue
        results.append(entry)
    return results
