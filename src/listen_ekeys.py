#!/usr/bin/env python3
"""聆聽 EVGA Z12 的 input report，看按 E-key 時鍵盤實際送出什麼。

目的：釐清 report 4 讀到的 function=0x03 / modifier=0x03..0x07 / key1=0x01
到底對應什麼 HID 事件。只讀 input report，不送任何 feature report，不送
SET，不改鍵盤設定。

聆聽三個 input 來源：
- 介面 1 report 0x01：滑鼠（8 鍵 + 滾輪 + X/Y）
- 介面 1 report 0x02：Consumer Control（媒體鍵）
- 介面 2 report 0x10：NKRO 鍵盤（modifier + 10-key 陣列）

用法：
    .venv/bin/python src/listen_ekeys.py
啟動後按 E-key（一次一顆），Ctrl-C 停止。每個 input report 會印出
時間戳、來源介面、report ID、hex + 解碼。
"""

import hid
import sys
import time

VID = 0x3842
PID = 0x2612

# 介面 1：滑鼠 + consumer + system + vendor 0x08/0x4B
# 介面 2：NKRO keyboard
# 不碰介面 0（boot keyboard 打字）

# 從 hid.enumerate 挑出介面 1 和介面 2 的裝置路徑
# hidapi 在 macOS 每個介面號對一個 device path

# Consumer page (0x0C) 常見媒體鍵 usage（16-bit report 時的值）
CONSUMER_USAGES = {
    0x00: "(release/none)",
    0xB5: "Scan Next Track",
    0xB6: "Scan Previous Track",
    0xB7: "Stop",
    0xCD: "Play/Pause",
    0xE2: "Mute",
    0xE9: "Volume Increment",
    0xEA: "Volume Decrement",
    0x183: "Fast Forward",
    0x184: "Rewind",
    0x018C: "Copy",
    0x018D: "Cut",
    0x018E: "Paste",
    0x0221: "Search",
    0x0223: "Home (browser)",
    0x0224: "Back (browser)",
    0x0225: "Forward (browser)",
    0x018A: "Undo",
    0x018B: "Redo",
}

# HID keyboard usage 0x04..0xA4 常用鍵名（從 Pasquotcho keys.yaml + 標準）
KEY_USAGES = {
    0x04: "A", 0x05: "B", 0x06: "C", 0x07: "D", 0x08: "E", 0x09: "F",
    0x0A: "G", 0x0B: "H", 0x0C: "I", 0x0D: "J", 0x0E: "K", 0x0F: "L",
    0x10: "M", 0x11: "N", 0x12: "O", 0x13: "P", 0x14: "Q", 0x15: "R",
    0x16: "S", 0x17: "T", 0x18: "U", 0x19: "V", 0x1A: "W", 0x1B: "X",
    0x1C: "Y", 0x1D: "Z",
    0x1E: "1", 0x1F: "2", 0x20: "3", 0x21: "4", 0x22: "5",
    0x23: "6", 0x24: "7", 0x25: "8", 0x26: "9", 0x27: "0",
    0x28: "Enter", 0x29: "Esc", 0x2A: "Backspace", 0x2B: "Tab",
    0x2C: "Space",
    0x3A: "F1", 0x3B: "F2", 0x3C: "F3", 0x3D: "F4", 0x3E: "F5",
    0x3F: "F6", 0x40: "F7", 0x41: "F8", 0x42: "F9", 0x43: "F10",
    0x44: "F11", 0x45: "F12",
    0x46: "PrintScreen", 0x47: "ScrollLock", 0x48: "Pause",
    0x49: "Insert", 0x4A: "Home", 0x4B: "PageUp",
    0x4C: "Delete", 0x4D: "End", 0x4E: "PageDown",
    0x4F: "Right", 0x50: "Left", 0x51: "Down", 0x52: "Up",
    0x53: "NumLock",
    0x65: "Menu",
    0x68: "F13", 0x69: "F14", 0x6A: "F15", 0x6B: "F16",
    0x6C: "F17", 0x6D: "F18", 0x6E: "F19", 0x6F: "F20",
    0x70: "F21", 0x71: "F22", 0x72: "F23", 0x73: "F24",
}

MOD_BITS = {
    0x01: "LCtrl", 0x02: "LShift", 0x04: "LAlt", 0x08: "LGUI",
    0x10: "RCtrl", 0x20: "RShift", 0x40: "RAlt", 0x80: "RGUI",
}

MOUSE_BITS = {
    0x01: "LBtn", 0x02: "RBtn", 0x04: "MBtn",
    0x08: "Btn4", 0x10: "Btn5", 0x20: "Btn6", 0x40: "Btn7", 0x80: "Btn8",
}


def hexdump(b):
    return " ".join(f"{x:02x}" for x in b)


def decode_consumer(data):
    """介面 1 report 0x02：16-bit little-endian consumer usage。"""
    if len(data) < 3:
        return "(太短)"
    usage = data[1] | (data[2] << 8)
    name = CONSUMER_USAGES.get(usage, f"unknown 0x{usage:04x}")
    return f"usage=0x{usage:04x} ({name})"


def decode_nkro(data):
    """介面 2 report 0x10：modifier + reserved + 10-key 陣列。"""
    if len(data) < 3:
        return "(太短)"
    mod = data[1]
    mods = [name for bit, name in MOD_BITS.items() if mod & bit]
    keys = []
    for b in data[3:3 + 10] if len(data) >= 13 else data[3:]:
        if b != 0:
            keys.append(KEY_USAGES.get(b, f"0x{b:02x}"))
    mod_str = "+".join(mods) if mods else "(none)"
    key_str = "+".join(keys) if keys else "(release)"
    return f"mod=[{mod_str}] keys=[{key_str}]"


def decode_mouse(data):
    """介面 1 report 0x01：8 button bits + X/Y + wheel。"""
    if len(data) < 5:
        return "(太短)"
    btns = data[1]
    btn_list = [name for bit, name in MOUSE_BITS.items() if btns & bit]
    x = data[2]
    y = data[3]
    wheel = data[4] if len(data) > 4 else 0
    # X/Y 是 signed
    if x >= 128:
        x -= 256
    if y >= 128:
        y -= 256
    return f"btns=[{'+'.join(btn_list) if btn_list else 'none'}] x={x} y={y} wheel={wheel}"


def main():
    print(f"=== EVGA Z12 input report 聆聽（PID {PID:#06x}）===")
    print("只讀 input report，不送任何封包，不改鍵盤設定。")
    print()

    # 找介面 1 和介面 2 的裝置路徑
    iface1_paths = []
    iface2_paths = []
    for d in hid.enumerate(VID, PID):
        if d["interface_number"] == 1:
            iface1_paths.append(d["path"])
        elif d["interface_number"] == 2:
            iface2_paths.append(d["path"])

    if not iface1_paths:
        print("找不到介面 1 裝置。")
        return

    # 命令列可選 --iface2 單獨聽介面 2（macOS 同時開兩個介面會 privilege violation）
    listen_iface2 = "--iface2" in sys.argv

    if listen_iface2 and not iface2_paths:
        print("找不到介面 2 裝置。")
        return

    if not listen_iface2:
        print(f"介面 1 路徑：{iface1_paths[0]!r}")
        print("(加 --iface2 可改聽介面 2 的 NKRO 鍵盤)")
    else:
        print(f"介面 2 路徑：{iface2_paths[0]!r}")
    print()

    # 只開一個介面
    path = iface2_paths[0] if listen_iface2 else iface1_paths[0]
    iface_label = "介面2" if listen_iface2 else "介面1"
    try:
        dev = hid.Device(path=path)
    except Exception as e:
        print(f"開裝置失敗（{iface_label}）：{e}")
        print("可能原因：macOS Input Monitoring 權限未授與，或裝置被系統佔用。")
        return
    dev.nonblocking = True

    print(f"{iface_label} 已開：{dev.product!r}")
    print()
    print(">>> 開始聆聽 <<<")
    print("現在請按 E-key（一次一顆，例如先按 E1）。")
    print("每按一顆，下面會印出對應的 input report。")
    print("Ctrl-C 停止。")
    print()

    BUF = 64
    start = time.time()

    try:
        while True:
            try:
                data = dev.read(BUF, timeout=50)
            except OSError:
                data = None
            if data:
                ts = time.time() - start
                rid = data[0]
                raw = hexdump(data)
                if listen_iface2:
                    if rid == 0x10:
                        dec = decode_nkro(data)
                        label = f"[介面2 NKRO report 0x10] {dec}"
                    elif rid == 0x11:
                        label = "[介面2 dummy report 0x11]"
                    else:
                        label = f"[介面2 report 0x{rid:02x}]"
                else:
                    if rid == 0x01:
                        dec = decode_mouse(data)
                        label = f"[介面1 滑鼠 report 0x01] {dec}"
                    elif rid == 0x02:
                        dec = decode_consumer(data)
                        label = f"[介面1 媒體 report 0x02] {dec}"
                    elif rid == 0x03:
                        label = "[介面1 dummy report 0x03]"
                    elif rid == 0x12:
                        label = f"[介面1 system report 0x12] {data[1]:08b}"
                    else:
                        label = f"[介面1 report 0x{rid:02x}]"
                print(f"{ts:7.3f}s  {label}")
                print(f"         raw: {raw}")

    except KeyboardInterrupt:
        print()
        print("停止聆聽。")

    dev.close()
    print("裝置已關閉。")


if __name__ == "__main__":
    main()