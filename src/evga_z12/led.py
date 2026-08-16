"""LED mode parameter read (report 7, ProfileInRAM).

Report 7 (136B) is the "current RAM" LED parameter channel. Unlike
report 8 (onboard profile, 265B) which is not readable on macOS hidapi,
report 7 is fully accessible. Each MainCommand (0x0C-0x12) reads one
LED mode's parameters; 0x0B reads keymap-related RAM state.

Packet structure (docs/profile-protocol.md:356):
  [0]=0x07 [1]=0xEA [2]=0x02 [3]=MainCommand [4..5]=SubCommand(uint16 LE)
  [6]=ResponseCommand [7]=CheckSum [8..135]=Data[128]
"""

from __future__ import annotations

from dataclasses import dataclass

from . import protocol
from .hid_io import HIDError, Z12Device

# All report 7 MainCommands and their display names
RAM_COMMANDS = [
    (protocol.RAM_CMD_KEY_FUNCTION, "KeyFunction"),
    (protocol.RAM_CMD_LED_LIGHTING_EFFECT_MODE, "LED_LightingEffectMode"),
    (protocol.RAM_CMD_LED_STATIC_ON, "LED_StaticOn"),
    (protocol.RAM_CMD_LED_BREATHING, "LED_Breathing"),
    (protocol.RAM_CMD_LED_PULSE, "LED_Pulse"),
    (protocol.RAM_CMD_LED_SPIRAL_RAINBOW, "LED_SpiralRainbow"),
    (protocol.RAM_CMD_LED_RAINBOW_WAVE, "LED_RainbowWave"),
    (protocol.RAM_CMD_LED_TRIGGER, "LED_Trigger"),
    (protocol.RAM_CMD_LED_STAR_SHINING, "LED_StarShining"),
]


@dataclass(frozen=True)
class LEDModeData:
    """One report 7 MainCommand read result."""

    main_command: int
    command_name: str
    success: bool
    status: int
    data: bytes  # 128B data segment

    @property
    def non_zero_count(self) -> int:
        return sum(1 for b in self.data if b != 0)


def read_led_mode(dev: Z12Device, main_cmd: int) -> LEDModeData:
    """Read one LED mode's parameters from report 7.

    Args:
        dev: Open Z12Device.
        main_cmd: Report 7 MainCommand (0x0B-0x13).

    Returns:
        LEDModeData with the 128B data segment.
    """
    payload = bytearray(protocol.REPORT_PROFILE_IN_RAM_SIZE - 1)
    payload[0] = protocol.HEADER1                        # 0xEA
    payload[1] = protocol.HEADER2                        # 0x02
    payload[2] = main_cmd                                # MainCommand
    payload[3] = protocol.SUB_READ & 0xFF               # SubCommand low byte
    payload[4] = (protocol.SUB_READ >> 8) & 0xFF        # SubCommand high byte
    payload[5] = 0x00                                    # ResponseCommand
    payload[6] = 0x00                                    # CheckSum

    last: LEDModeData | None = None
    for _ in range(2):
        resp = dev.transact(
            protocol.REPORT_PROFILE_IN_RAM,
            protocol.REPORT_PROFILE_IN_RAM_SIZE,
            bytes(payload),
            discard=3,
        )
        status = resp[6]
        data = bytes(resp[8 : 8 + 128]) if len(resp) > 8 else b""
        cmd_name = protocol.RAM_CMD_NAMES.get(main_cmd, f"0x{main_cmd:02x}")
        last = LEDModeData(
            main_command=main_cmd,
            command_name=cmd_name,
            success=(status == protocol.RESPONSE_SUCCESS),
            status=status,
            data=data,
        )
        if last.success:
            return last
    assert last is not None
    return last


def read_all_led_modes(dev: Z12Device) -> list[LEDModeData]:
    """Read all 9 report 7 MainCommands (0x0B-0x13)."""
    results: list[LEDModeData] = []
    for main_cmd, _name in RAM_COMMANDS:
        try:
            result = read_led_mode(dev, main_cmd)
        except HIDError:
            result = LEDModeData(
                main_command=main_cmd,
                command_name=protocol.RAM_CMD_NAMES.get(main_cmd, f"0x{main_cmd:02x}"),
                success=False,
                status=0,
                data=b"",
            )
        results.append(result)
    return results


def _checksum(data: bytes) -> int:
    """Report 7 checksum: -(sum of Data[128]) & 0xFF. Verified on-device."""
    return (-sum(data)) & 0xFF


def write_lighting_effect_mode(dev: Z12Device, main_mode: int, sub_mode: int = 0) -> LEDModeData:
    """Set the active LED mode (report 7, MainCommand 0x0C, Write).

    On-device 2026-08-16: RainbowWave 05 02 -> StaticOn 01 02 returned
    0xC0 and read back; restore 05 02 succeeded. One SET_FEATURE only.

    Raises:
        ValueError: unsupported mode (StarShining on Z12).
        HIDError: device returned non-success.
    """
    # LedMainLightingEffectMode.StarShining = 0x06; Z12 read of 0x13 returns C1.
    if main_mode == 0x06:
        raise ValueError("StarShining is not supported on Z12")

    data = bytearray(128)
    data[0] = main_mode & 0xFF
    data[1] = sub_mode & 0xFF
    payload = bytearray(protocol.REPORT_PROFILE_IN_RAM_SIZE - 1)
    payload[0] = protocol.HEADER1
    payload[1] = protocol.HEADER2
    payload[2] = protocol.RAM_CMD_LED_LIGHTING_EFFECT_MODE
    payload[3] = protocol.SUB_WRITE & 0xFF
    payload[4] = 0x00
    payload[5] = 0x00
    payload[6] = _checksum(data)
    payload[7 : 7 + 128] = data

    resp = dev.send_once(
        protocol.REPORT_PROFILE_IN_RAM,
        protocol.REPORT_PROFILE_IN_RAM_SIZE,
        bytes(payload),
        get_count=4,
        first_wait=0.10,
    )
    status = resp[6]
    if status != protocol.RESPONSE_SUCCESS:
        raise HIDError(f"write_lighting_effect_mode: status 0x{status:02x}")
    return read_led_mode(dev, protocol.RAM_CMD_LED_LIGHTING_EFFECT_MODE)


def decode_lighting_effect_mode(data: bytes) -> dict[str, int]:
    """Decode the LightingEffectMode data (MainCommand 0x0C).

    From on-device read (docs/research.md): data[0]=main mode, data[1]=sub mode.
    """
    if len(data) < 2:
        return {}
    main_mode = data[0]
    sub_mode = data[1]
    return {
        "main_mode": main_mode,
        "main_mode_name": protocol.LED_MAIN_MODE_NAMES.get(main_mode, f"0x{main_mode:02x}"),
        "sub_mode": sub_mode,
    }
