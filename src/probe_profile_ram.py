#!/usr/bin/env python3
"""唯讀測試 report 7（ProfileInRAM, 136B）的各個 MainCommand。

目的：report 8（整組 profile, 265B）在 macOS 讀不到。report 7（136B）是
「當前 RAM 中」的 LED/keymap 參數通道，用 MainCommand 0x0B–0x13 讀。
- 0x0B = KeyFunction（可能是當前 RAM keymap）
- 0x0C = LED_LightingEffectMode
- 0x0D–0x13 = 各 LED 模式參數

封包結構（from docs/profile-protocol.md）：
  [0]=0x07 [1]=0xEA [2]=0x02 [3]=MainCommand [4..5]=SubCommand(uint16 LE)
  [6]=ResponseCommand [7]=CheckSum [8..135]=Data[128]

安全規則：只開介面 1，只送 Read（SubCommand=0x01），不碰介面 0。

用法：
    .venv/bin/python src/probe_profile_ram.py --run
"""

import hid
import sys
import time

VID = 0x3842
PID = 0x2612
TARGET_INTERFACE = 1
TARGET_USAGE_PAGE = 0x08
TARGET_USAGE = 0x4B

REPORT_7_SIZE = 136

HEADER1 = 0xEA
HEADER2 = 0x02
RESPONSE_SUCCESS = 0xC0

# Report 7 MainCommands
MAIN_COMMANDS = [
    (0x0B, "KeyFunction"),
    (0x0C, "LED_LightingEffectMode"),
    (0x0D, "LED_StaticOnParameters"),
    (0x0E, "LED_BreathingParameters"),
    (0x0F, "LED_PulseParameters"),
    (0x10, "LED_SpiralRainbowParameters"),
    (0x11, "LED_RainbowWaveParameters"),
    (0x12, "LED_TriggerParameters"),
    (0x13, "LED_StarShiningParameters"),
]

SUB_READ = 0x01


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
    """送 N 次丟棄前 N-1 次。"""
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


def read_report7(dev, main_cmd, sub_cmd=SUB_READ, discard_count=3):
    """送 report 7 ProfileInRAM 讀取。

    payload: EA 02 <main> <sub_lo> <sub_hi> 00 00 + 128B 0
    """
    payload = bytearray(REPORT_7_SIZE - 1)
    payload[0] = HEADER1        # 0xEA
    payload[1] = HEADER2        # 0x02
    payload[2] = main_cmd       # MainCommand
    payload[3] = sub_cmd & 0xFF # SubCommand low byte (uint16 LE)
    payload[4] = (sub_cmd >> 8) & 0xFF  # SubCommand high byte
    payload[5] = 0x00           # ResponseCommand (keyboard fills)
    payload[6] = 0x00           # CheckSum
    # payload[7..134] = Data[128]

    return send_and_read(dev, 0x07, REPORT_7_SIZE, bytes(payload), discard_count)


def main():
    do_run = "--run" in sys.argv

    print("=== EVGA Z12 report 7 (ProfileInRAM) 測試 ===")
    print(f"模式：{'實際送' if do_run else '僅列舉（加 --run）'}")
    print()

    candidates = find_device()
    if not candidates:
        print("找不到裝置。")
        sys.exit(1)

    if not do_run:
        print("將測試 report 7 的 9 個 MainCommand（0x0B–0x13）。")
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

    for main_cmd, name in MAIN_COMMANDS:
        print(f"--- MainCommand 0x{main_cmd:02x} ({name}) ---")
        ok, resp = read_report7(dev, main_cmd, discard_count=3)
        if not ok:
            print(f"  失敗：{resp}")
            print()
            continue

        status = resp[6] if len(resp) > 6 else None
        checksum = resp[7] if len(resp) > 7 else None
        data = resp[8:8+128] if len(resp) > 8 else b""
        non_zero = sum(1 for b in data if b != 0)

        status_str = f"0x{status:02x}" if status is not None else "None"
        print(f"  status={status_str} ({'✅' if status==0xC0 else '❌' if status==0xC1 else '???'})")
        print(f"  checksum=0x{checksum:02x}" if checksum is not None else "")
        print(f"  Data[{len(data)}B]: {non_zero}B 非 0")
        if non_zero > 0:
            print(f"  前 32B: {data[:32].hex(' ')}")
            print(hexdump(data[:64]))
        print()
        time.sleep(0.1)

    dev.close()
    print("裝置已關閉。")


if __name__ == "__main__":
    main()