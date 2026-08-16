"""Keymap read and decode (report 4, KeyFunctionRam).

Reads the KeyDefine (4 bytes: Function + Parameter1/2/3) for each
physical key position. The 121 on-device valid positions are in
protocol.LED_KEY_POSITIONS (0x00-0x78). Both Primary (main) and Secondary
(Shift/FN) layers use the same position table, selected by SubCommand2.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import protocol
from .hid_io import Z12Device

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


# Import here to avoid circular import at module level
from .hid_io import HIDError  # noqa: E402


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
