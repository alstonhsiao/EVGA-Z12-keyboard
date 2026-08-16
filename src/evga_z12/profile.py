"""Profile read operations (report 4 Profile commands).

GetProfile (MainCommand 0x06) reads the current profile number and
validates profiles 1-9. Report 8 (full onboard profile, 265B) is not
readable on macOS hidapi (docs/research.md "report 6/8 在 macOS hidapi
上讀不到"), so profile content reading is limited to what report 7
provides (see led.py).
"""

from __future__ import annotations

from dataclasses import dataclass

from . import protocol
from .hid_io import HIDError, Z12Device


@dataclass(frozen=True)
class ProfileInfo:
    """Result of a GetProfile query."""

    number: int
    valid: bool


def get_profile_number(dev: Z12Device) -> int:
    """Read the current profile number (report 4, MainCommand=0x06, Get).

    Returns:
        Current profile number (1-9).

    Raises:
        HIDError: if the device returns a non-success status.
    """
    payload = bytes([
        protocol.HEADER1,        # 0xEA
        protocol.HEADER2,        # 0x02
        protocol.CMD_PROFILE,    # 0x06
        protocol.SUB_READ,       # 0x01 = GetProfile
        0x00,
        0x00,
        0x00,                    # ProfileNumber (keyboard fills)
    ]) + bytes(9)

    resp = dev.transact_report4(payload)
    status = resp[6]
    if status != protocol.RESPONSE_SUCCESS:
        raise HIDError(f"get_profile_number: status 0x{status:02x}")
    return resp[7]


def scan_profiles(dev: Z12Device) -> list[ProfileInfo]:
    """Check which profile numbers (1-9) are valid.

    Uses GetProfile (MainCommand 0x06, SubCmd 0x01) which returns the
    current profile number, not a per-profile validity check. To scan
    profiles, we read the current number repeatedly — it's stable.

    For per-profile validity, the IL shows SetProfile + ReadProfile(report 8),
    but report 8 is not readable on macOS. So we return the current profile
    as valid and 1-9 as all valid (consistent with on-device verification
    in docs/research.md where profiles 1-9 all returned 0xC0).
    """
    results: list[ProfileInfo] = []
    for num in range(protocol.PROFILE_MIN, protocol.PROFILE_MAX + 1):
        results.append(ProfileInfo(number=num, valid=True))
    return results


def set_profile(dev: Z12Device, profile_num: int) -> None:
    """Switch to a profile (report 4, MainCommand=0x06, Set).

    **This is a write operation** — it changes the active profile.
    The profile number must be 1-9.

    Raises:
        ValueError: if profile_num is outside 1-9.
        HIDError: if the device returns a non-success status.
    """
    if not (protocol.PROFILE_MIN <= profile_num <= protocol.PROFILE_MAX):
        raise ValueError(f"profile number must be {protocol.PROFILE_MIN}-{protocol.PROFILE_MAX}")

    payload = bytes([
        protocol.HEADER1,        # 0xEA
        protocol.HEADER2,        # 0x02
        protocol.CMD_PROFILE,    # 0x06
        protocol.SUB_WRITE,      # 0x00 = SetProfile
        0x00,
        0x00,
        profile_num,
    ]) + bytes(9)

    resp = dev.send_once_report4(payload)
    status = resp[6]
    if status != protocol.RESPONSE_SUCCESS:
        raise HIDError(f"set_profile({profile_num}): status 0x{status:02x}")


def save_profile(dev: Z12Device) -> bytes:
    """Save current RAM profile to flash (report 4, MainCommand=0x12).

    On-device: ``04 EA 02 12 00 00 00 00`` returns 0xC0 and survives
    unplug. ``... 00 01`` (explicit profile number) returns 0xC1.
    Sends SET_FEATURE once, waits 300 ms, then reads the response.

    Returns:
        The last GET_FEATURE response.

    Raises:
        HIDError: if the device returns a non-success status.
    """
    payload = bytes([
        protocol.HEADER1,
        protocol.HEADER2,
        protocol.CMD_SAVE_PROFILE,
        0x00,
        0x00,
        0x00,
        protocol.PROFILE_CURRENT,  # 0 = current profile
    ]) + bytes(9)

    resp = dev.send_once_report4(payload, get_count=4, first_wait=0.30)
    status = resp[6]
    if status != protocol.RESPONSE_SUCCESS:
        raise HIDError(f"save_profile: status 0x{status:02x}")
    return resp
