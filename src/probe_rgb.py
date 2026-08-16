#!/usr/bin/env python3
"""唯讀測試 report 6（LedColorSetting, 32B）的五區 RGB。

目的：report 6 是 Z12 的五區 RGB 設定（32B），OpenRGB Z15 用 792B report 6
做單鍵 RGB。Z12 只有五區，32B 合理。嘗試用 Z15 的協定（06 EA 02 01...）
讀取，看回應結構。

OpenRGB Z15 report 6 命令：
- Direct LEDs: 06 EA 02 01，之後每鍵 4 bytes（亮度 RGB）
- HW modes init: 06 EA 02

安全規則：只開介面 1，只送 GET_FEATURE，不碰介面 0。

用法：
    .venv/bin/python src/probe_rgb.py --run
"""

import hid
import sys
import time

VID = 0x3842
PID = 0x2612
TARGET_INTERFACE = 1
TARGET_USAGE_PAGE = 0x08
TARGET_USAGE = 0x4B

REPORT_6_SIZE = 32

HEADER1 = 0xEA
HEADER2 = 0x02


def find_device():
    candidates = []
    for d in hid.enumerate(VID, PID):
        if (d["interface_number"] == TARGET_INTERFACE
                and d["usage_page"] == TARGET_USAGE_PAGE
                and d["usage"] == TARGET_USAGE):
            candidates.append(d)
    return candidates


def hexdump(b, width=16):
    out = []
    for i in range(0, len(b), width):
        chunk = b[i:i + width]
        hexs = " ".join(f"{x:02x}" for x in chunk)
        asc = "".join(chr(x) if 32 <= x < 127 else "." for x in chunk)
        out.append(f"  {i:04x}  {hexs:<{width*3}}  {asc}")
    return "\n".join(out)


def send_and_read(dev, report_id, size, payload, discard_count=3):
    for attempt in range(discard_count):
        req = bytearray(size)
        req[0] = report_id
        for i, b in enumerate(payload):
            if 1 + i < size:
                req[1 + i] = b
        try:
            dev.send_feature_report(bytes(req))
        except OSError as e:
            return False, f"send: {e}"
        try:
            resp = dev.get_feature_report(report_id, size)
        except OSError as e:
            return False, f"get: {e}"
        if resp is None or len(resp) == 0:
            return False, "empty"
        time.sleep(0.05)
    return True, bytes(resp)


def main():
    do_run = "--run" in sys.argv

    print("=== EVGA Z12 report 6 (LedColorSetting, 32B) RGB 測試 ===")
    print(f"模式：{'實際送' if do_run else '僅列舉（加 --run）'}")
    print()

    candidates = find_device()
    if not candidates:
        print("找不到裝置。")
        sys.exit(1)

    if not do_run:
        print("將測試 report 6 的多種 payload 組合。")
        return

    print(">>> 開啟裝置，唯讀，不碰介面 0 <<<")
    time.sleep(2)

    try:
        dev = hid.Device(path=candidates[0]["path"])
    except OSError as e:
        print(f"開裝置失敗：{e}")
        sys.exit(2)

    print(f"裝置已開：{dev.product!r}")
    print()

    # 測試不同 payload 組合
    tests = [
        # (label, payload bytes after report ID)
        ("全 0 (baseline)", bytes(31)),
        ("EA 02 01 (Direct LEDs like Z15)", bytes([0xEA, 0x02, 0x01]) + bytes(28)),
        ("EA 02 00 (HW modes init)", bytes([0xEA, 0x02, 0x00]) + bytes(28)),
        ("EA 02 01 01 (Direct + zone?)", bytes([0xEA, 0x02, 0x01, 0x01]) + bytes(27)),
        ("EA 02 0C (Mode/colour like Z15 report 7)", bytes([0xEA, 0x02, 0x0C]) + bytes(28)),
        ("EA 02 03 (Sleep like Z15)", bytes([0xEA, 0x02, 0x03]) + bytes(28)),
        ("EA 02 01 00 (Direct + read)", bytes([0xEA, 0x02, 0x01, 0x00]) + bytes(27)),
    ]

    for label, payload in tests:
        print(f"--- {label} ---")
        ok, resp = send_and_read(dev, 0x06, REPORT_6_SIZE, payload, discard_count=3)
        if not ok:
            print(f"  失敗：{resp}")
            print()
            continue

        non_zero = sum(1 for b in resp if b != 0)
        status = resp[6] if len(resp) > 6 else None
        status_str = f"0x{status:02x}" if status is not None else "None"
        print(f"  回應（{len(resp)}B）：{non_zero}B 非 0, byte[6]={status_str}")
        print(f"  {hexdump(resp)}")
        print()
        time.sleep(0.1)

    dev.close()
    print("裝置已關閉。")


if __name__ == "__main__":
    main()