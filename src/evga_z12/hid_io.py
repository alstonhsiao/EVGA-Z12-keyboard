"""Low-level HID I/O for the EVGA Z12 vendor interface.

Opens interface 1 (usage page 0x08 / usage 0x4B) only — never interface 0
(boot keyboard) per AGENTS.md rule 3. Handles the hidapi feature-report
cache-pollution workaround documented in docs/troubleshooting.md:
get_feature_report returns a stale response from the previous request, so
every transact sends N times and discards the first N-1 responses.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import hid

from . import protocol

# Inter-attempt delay (ms) to let the keyboard fill the feature report
# buffer. The probe scripts found 50ms sufficient; pure delay alone does
# NOT fix stale cache (troubleshooting.md root cause #2), but a short
# sleep between send+get cycles avoids hammering the device.
_INTER_ATTEMPT_DELAY = 0.05


class DeviceNotFoundError(Exception):
    """No EVGA Z12 vendor interface found."""


class HIDError(Exception):
    """A send_feature_report or get_feature_report call failed."""


@dataclass(frozen=True)
class DeviceInfo:
    path: bytes
    interface_number: int
    usage_page: int
    usage: int
    manufacturer: str
    product: str


def find_device() -> DeviceInfo:
    """Locate the Z12 vendor interface (interface 1, 0x08/0x4B).

    Raises DeviceNotFoundError if no matching interface is present.
    """
    for d in hid.enumerate(protocol.VENDOR_ID, protocol.PRODUCT_ID):
        if (
            d["interface_number"] == protocol.TARGET_INTERFACE
            and d["usage_page"] == protocol.TARGET_USAGE_PAGE
            and d["usage"] == protocol.TARGET_USAGE
        ):
            return DeviceInfo(
                path=d["path"],
                interface_number=d["interface_number"],
                usage_page=d["usage_page"],
                usage=d["usage"],
                manufacturer=d.get("manufacturer_string", ""),
                product=d.get("product_string", ""),
            )
    raise DeviceNotFoundError(
        f"No EVGA Z12 vendor interface found "
        f"(VID {protocol.VENDOR_ID:#06x} PID {protocol.PRODUCT_ID:#06x} "
        f"interface {protocol.TARGET_INTERFACE})"
    )


class Z12Device:
    """Open HID connection to the Z12 vendor interface.

    Context manager; closes automatically on exit.
    """

    def __init__(self, device_info: DeviceInfo | None = None):
        self._info = device_info or find_device()
        self._dev: hid.Device | None = None

    def __enter__(self) -> Z12Device:
        self._dev = hid.Device(path=self._info.path)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self) -> None:
        if self._dev is not None:
            self._dev.close()
            self._dev = None

    @property
    def info(self) -> DeviceInfo:
        return self._info

    @property
    def manufacturer(self) -> str:
        return self._dev.manufacturer if self._dev else self._info.manufacturer

    @property
    def product(self) -> str:
        return self._dev.product if self._dev else self._info.product

    def transact(
        self,
        report_id: int,
        size: int,
        payload: bytes | bytearray,
        discard: int = 2,
    ) -> bytes:
        """Send a feature report and read back the response.

        Sends the report ``discard`` times, discarding all but the last
        response to flush stale hidapi cache (troubleshooting.md root
        cause #2). The first byte of the request is set to ``report_id``;
        ``payload`` fills bytes 1..N-1.

        Args:
            report_id: Feature report ID (0x04, 0x07, 0x09, 0x0A, ...).
            size: Total report length including the report ID byte.
            payload: Bytes to place at offset 1..len(payload) of the
                request. Remaining bytes up to ``size`` are zero-filled.
            discard: Number of send+get cycles; the last response is
                returned. Default 2 (send twice, keep second).

        Returns:
            The final response bytes (length == size on success).

        Raises:
            HIDError: if send or get fails, or response is empty.
        """
        if self._dev is None:
            raise HIDError("Device not opened (use 'with Z12Device() as dev:')")

        last_resp: bytes | None = None
        for _ in range(discard):
            req = bytearray(size)
            req[0] = report_id
            for i, b in enumerate(payload):
                if 1 + i < size:
                    req[1 + i] = b
            try:
                self._dev.send_feature_report(bytes(req))
            except OSError as exc:
                raise HIDError(f"send_feature_report(report {report_id:#04x}): {exc}") from exc

            try:
                resp = self._dev.get_feature_report(report_id, size)
            except OSError as exc:
                raise HIDError(f"get_feature_report(report {report_id:#04x}): {exc}") from exc

            if resp is None or len(resp) == 0:
                raise HIDError(f"get_feature_report(report {report_id:#04x}) returned empty")
            last_resp = bytes(resp)
            time.sleep(_INTER_ATTEMPT_DELAY)

        assert last_resp is not None
        return last_resp

    def send_once(
        self,
        report_id: int,
        size: int,
        payload: bytes | bytearray,
        get_count: int = 4,
        first_wait: float = 0.05,
    ) -> bytes:
        """SET_FEATURE once, then GET several times (no resend).

        Use this for writes. ``transact`` repeats send+get, which would
        fire the same write multiple times. SaveProfile was verified with
        a single SET and four GETs (docs/research.md).
        """
        if self._dev is None:
            raise HIDError("Device not opened (use 'with Z12Device() as dev:')")

        req = bytearray(size)
        req[0] = report_id
        for i, b in enumerate(payload):
            if 1 + i < size:
                req[1 + i] = b
        try:
            self._dev.send_feature_report(bytes(req))
        except OSError as exc:
            raise HIDError(f"send_feature_report(report {report_id:#04x}): {exc}") from exc

        time.sleep(first_wait)
        last_resp: bytes | None = None
        for _ in range(get_count):
            try:
                resp = self._dev.get_feature_report(report_id, size)
            except OSError as exc:
                raise HIDError(f"get_feature_report(report {report_id:#04x}): {exc}") from exc
            if resp is None or len(resp) == 0:
                raise HIDError(f"get_feature_report(report {report_id:#04x}) returned empty")
            last_resp = bytes(resp)
            time.sleep(_INTER_ATTEMPT_DELAY)

        assert last_resp is not None
        return last_resp

    def send_once_report4(
        self,
        payload: bytes | bytearray,
        get_count: int = 4,
        first_wait: float = 0.05,
    ) -> bytes:
        """Single SET of report 4, then GET ``get_count`` times."""
        return self.send_once(
            protocol.REPORT_GENERAL_USB,
            protocol.REPORT_GENERAL_USB_SIZE,
            payload,
            get_count=get_count,
            first_wait=first_wait,
        )

    def transact_report4(self, payload: bytes | bytearray, discard: int = 3) -> bytes:
        """Convenience wrapper for report 4 (GeneralUsb, 17B).

        Default discard=3: the first request after opening the device
        often returns stale cache from a previous hidapi session, so an
        extra flush cycle is needed beyond the normal discard=2.
        """
        return self.transact(
            protocol.REPORT_GENERAL_USB,
            protocol.REPORT_GENERAL_USB_SIZE,
            payload,
            discard=discard,
        )

    @staticmethod
    def check_success(resp: bytes, offset: int = 6) -> bool:
        """Check if response byte at ``offset`` is RESPONSE_SUCCESS."""
        return len(resp) > offset and resp[offset] == protocol.RESPONSE_SUCCESS
