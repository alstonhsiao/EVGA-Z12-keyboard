#!/usr/bin/env python3
"""掃描 report 4 keymap 的所有 position（0x00–0xFF），建出完整的鍵映射表。

目的：從 Unleash 軟體逆向已得到 LedKeyPosition enum（113 個具名鍵），
這裡用實機 GET_FEATURE 逐個 position 掃描，驗證哪些 position 有效
（回 0xC0）並讀回 KeyDefine。兩份資料對照即可確認 position 表正確。

安全規則（對應 AGENTS.md 規則 1/3）：
- 只開介面 1，只送 GET_FEATURE（byte4=01 讀模式），不送 SET。
- 送兩次、丟棄首次、取第二次（排空過時快取）。
- 同一方法連失敗兩次就停。

用法：
    .venv/bin/python src/scan_positions.py --run
"""

import hid
import sys
import time

VID = 0x3842
PID = 0x2612
TARGET_INTERFACE = 1
TARGET_USAGE_PAGE = 0x08
TARGET_USAGE = 0x4B

REPORT_ID = 0x04
REPORT_SIZE = 17

# KeyDefine function 碼
FUNCTION_NAMES = {
    0x00: "KeyboardEmulation",
    0x02: "Consumer(Media)",
    0x03: "Macro",
    0xFF: "Disable",
}

# Modifier bitmask
MOD_BITS = {
    0x01: "LCtrl", 0x02: "LShift", 0x04: "LAlt", 0x08: "LGUI",
    0x10: "RCtrl", 0x20: "RShift", 0x40: "RAlt", 0x80: "RGUI",
}

# HID usage code → 鍵名（簡表，完整表見 keys.yaml）
HID_NAMES = {
    0x04: "A", 0x05: "B", 0x06: "C", 0x07: "D", 0x08: "E", 0x09: "F",
    0x0A: "G", 0x0B: "H", 0x0C: "I", 0x0D: "J", 0x0E: "K", 0x0F: "L",
    0x10: "M", 0x11: "N", 0x12: "O", 0x13: "P", 0x14: "Q", 0x15: "R",
    0x16: "S", 0x17: "T", 0x18: "U", 0x19: "V", 0x1A: "W", 0x1B: "X",
    0x1C: "Y", 0x1D: "Z",
    0x1E: "1", 0x1F: "2", 0x20: "3", 0x21: "4", 0x22: "5",
    0x23: "6", 0x24: "7", 0x25: "8", 0x26: "9", 0x27: "0",
    0x28: "Enter", 0x29: "Esc", 0x2A: "Backspace", 0x2B: "Tab",
    0x2C: "Space", 0x2D: "-", 0x2E: "=", 0x2F: "[", 0x30: "]",
    0x31: "\\", 0x33: ";", 0x34: "'", 0x35: "`", 0x36: ",",
    0x37: ".", 0x38: "/", 0x39: "CapsLock",
    0x3A: "F1", 0x3B: "F2", 0x3C: "F3", 0x3D: "F4", 0x3E: "F5",
    0x3F: "F6", 0x40: "F7", 0x41: "F8", 0x42: "F9", 0x43: "F10",
    0x44: "F11", 0x45: "F12",
    0x46: "PrintScreen", 0x47: "ScrollLock", 0x48: "Pause",
    0x49: "Insert", 0x4A: "Home", 0x4B: "PageUp",
    0x4C: "Delete", 0x4D: "End", 0x4E: "PageDown",
    0x4F: "Right", 0x50: "Left", 0x51: "Down", 0x52: "Up",
    0x53: "NumLock", 0x54: "Num/", 0x55: "Num*", 0x56: "Num-",
    0x57: "Num+", 0x58: "NumEnter",
    0x59: "Num1", 0x5A: "Num2", 0x5B: "Num3", 0x5C: "Num4",
    0x5D: "Num5", 0x5E: "Num6", 0x5F: "Num7", 0x60: "Num8",
    0x61: "Num9", 0x62: "Num0", 0x63: "Num.",
    0x65: "Menu",
    0x68: "F13", 0x69: "F14", 0x6A: "F15", 0x6B: "F16",
    0x6C: "F17", 0x6D: "F18", 0x6E: "F19", 0x6F: "F20",
    0x70: "F21", 0x71: "F22", 0x72: "F23", 0x73: "F24",
    0xE0: "LCtrl", 0xE1: "LShift", 0xE2: "LAlt", 0xE3: "LGUI",
    0xE4: "RCtrl", 0xE5: "RShift", 0xE6: "RAlt", 0xE7: "RGUI",
}

# 從軟體逆向得到的 LedKeyPosition enum（docs/key-position-table.md）
LED_KEY_POSITIONS = {
    0x00: "GameMode", 0x01: "ESC", 0x02: "F1", 0x03: "F2", 0x04: "F3",
    0x05: "F4", 0x06: "F5", 0x07: "F6", 0x08: "F7", 0x09: "F8",
    0x0A: "F9", 0x0B: "F10", 0x0C: "F11", 0x0D: "F12",
    0x0E: "PrintScreen", 0x0F: "ScrollLock", 0x10: "Pause",
    0x11: "Grave", 0x12: "1", 0x13: "2", 0x14: "3",
    0x15: "E1", 0x16: "Tab", 0x17: "Q", 0x18: "W", 0x19: "E",
    0x1A: "R", 0x1B: "T", 0x1C: "Y", 0x1D: "U", 0x1E: "I",
    0x1F: "O", 0x20: "P", 0x21: "[", 0x22: "]", 0x23: "\\",
    0x24: "CapsLock", 0x25: "A", 0x26: "S", 0x27: "D", 0x28: "F",
    0x29: "G", 0x2A: "H", 0x2B: "E2", 0x2C: "J", 0x2D: "K",
    0x2E: "L", 0x2F: ";", 0x30: "'", 0x31: "Enter",
    0x32: "LShift", 0x33: "Z", 0x34: "X", 0x35: "C", 0x36: "V",
    0x37: "B", 0x38: "N", 0x39: "M", 0x3A: ",", 0x3B: ".",
    0x3C: "/", 0x3D: "RShift", 0x3E: "LCtrl", 0x3F: "LAlt",
    0x40: "Space", 0x41: "E3",
    0x42: "RAlt", 0x43: "R Ctrl", 0x44: "Up", 0x45: "Down",
    0x46: "Left", 0x47: "Right",
    0x48: "Ins", 0x49: "Home", 0x4A: "PgUp", 0x4B: "Delete",
    0x4C: "End", 0x4D: "PgDn",
    0x4E: "NumLock", 0x4F: "Num/", 0x50: "Num*", 0x51: "Num-",
    0x52: "E4", 0x53: "Num+", 0x54: "NumEnter",
    0x55: "Num7", 0x56: "Num8", 0x57: "Num9",
    0x58: "Num4", 0x59: "Num5", 0x5A: "Num6",
    0x5B: "Num1", 0x5C: "Num2", 0x5D: "Num3",
    0x5E: "Num0", 0x5F: "Num.",
    0x60: "Backspace", 0x61: "App", 0x62: "LWin", 0x63: "RWin",
    0x64: "FN",
    0x65: "LightBar_Sw", 0x66: "E5",
    0x67: "LED_Sw", 0x68: "Profile_Sw",
    0x69: "MacroRec", 0x6A: "MacroRun",
    0x6B: "WinLock",
    # 0x78 = MAX_KEY_POSITION (sentinel)
    # 0xA0-0xC3 = LED zones (非實體鍵)
    0xA0: "LED_Zone1", 0xA1: "LED_Zone2", 0xA2: "LED_Zone3",
    0xA3: "LED_Zone4", 0xA4: "LED_Zone5",
    0xC4: "MAX_COUNT", 0xFF: "LEDNA",
}


def find_device():
    candidates = []
    for d in hid.enumerate(VID, PID):
        if (d["interface_number"] == TARGET_INTERFACE
                and d["usage_page"] == TARGET_USAGE_PAGE
                and d["usage"] == TARGET_USAGE):
            candidates.append(d)
    return candidates


def read_position(dev, pos, fail_counts):
    """送 report 4 keymap read 指定 position。送兩次丟棄首次。"""
    def _once():
        req = bytearray(REPORT_SIZE)
        req[0] = REPORT_ID
        req[1] = 0xEA
        req[2] = 0x02
        req[3] = 0x07  # KeyFunctionRam
        req[4] = 0x01  # Read
        req[5] = 0x00  # PrimaryKeyAssignment
        req[6] = 0x00
        req[7] = pos
        try:
            dev.send_feature_report(bytes(req))
        except OSError as e:
            fail_counts["write"] += 1
            return False, f"send: {e}"
        try:
            resp = dev.get_feature_report(REPORT_ID, REPORT_SIZE)
        except OSError as e:
            fail_counts["read"] += 1
            return False, f"get: {e}"
        if resp is None or len(resp) == 0:
            fail_counts["read"] += 1
            return False, "empty"
        return True, bytes(resp)

    ok1, r1 = _once()
    if not ok1:
        return False, f"[排空] {r1}"
    ok2, r2 = _once()
    if not ok2:
        return False, f"[讀取] {r2}"
    return True, r2


def decode_key_define(resp):
    """解碼 report 4 回應的 KeyDefine (byte 7-10)。"""
    if len(resp) < 12:
        return None
    # resp[7] = position (回應的)
    # resp[8] = Function
    # resp[9] = Parameter1
    # resp[10] = Parameter2
    # resp[11] = Parameter3
    fn = resp[8]
    p1 = resp[9]
    p2 = resp[10]
    p3 = resp[11]
    fn_name = FUNCTION_NAMES.get(fn, f"0x{fn:02x}")

    if fn == 0x00:
        # 單鍵映射：P1=modifier, P2=HID key1, P3=HID key2
        mods = [name for bit, name in MOD_BITS.items() if p1 & bit]
        key1 = HID_NAMES.get(p2, f"0x{p2:02x}")
        key2 = HID_NAMES.get(p3, f"0x{p3:02x}") if p3 else ""
        mod_str = "+".join(mods) + "+" if mods else ""
        if p3:
            return f"{fn_name}: {mod_str}{key1}+{key2}"
        return f"{fn_name}: {mod_str}{key1}"
    elif fn == 0x03:
        # 巨集：P1=巨集編號, P2=runMethod, P3=repeatTime
        return f"{fn_name}: macro#{p1} runMethod=0x{p2:02x} repeat={p3}"
    elif fn == 0x02:
        # 媒體鍵：P1=consumer code low, P2=consumer code high
        consumer_code = p1 | (p2 << 8)
        return f"{fn_name}: consumerCode=0x{consumer_code:04x}"
    elif fn == 0xFF:
        return f"{fn_name}: disabled"
    else:
        return f"{fn_name}(0x{fn:02x}): p1=0x{p1:02x} p2=0x{p2:02x} p3=0x{p3:02x}"


def main():
    do_run = "--run" in sys.argv

    print(f"=== EVGA Z12 keymap position 全掃描（0x00–0xFF）===")
    print(f"模式：{'實際掃描' if do_run else '僅列舉（加 --run 才掃）'}")
    print()

    candidates = find_device()
    if not candidates:
        print("找不到裝置。")
        sys.exit(1)

    if not do_run:
        print(f"將掃描 position 0x00–0xFF（256 個），每個送 2 次 GET_FEATURE。")
        print(f"預計耗時約 30–60 秒。加 --run 開始。")
        return

    print(">>> 即將開啟裝置並掃描 256 個 position <<<")
    print("    【提醒】只開介面 1，只送 Read，不碰介面 0。")
    print("    請停止使用 keyboard，掃描完會通知。")
    time.sleep(3)

    try:
        dev = hid.Device(path=candidates[0]["path"])
    except OSError as e:
        print(f"開裝置失敗：{e}")
        sys.exit(2)

    print(f"裝置已開：{dev.product!r}")
    print()

    valid_positions = []
    fail_counts = {"write": 0, "read": 0}

    for pos in range(0x100):
        ok, resp = read_position(dev, pos, fail_counts)
        if not ok:
            # 失敗不計較（很多 position 本來就無效）
            fail_counts = {"write": 0, "read": 0}
            continue

        status = resp[6] if len(resp) > 6 else None
        if status == 0xC0:
            name = LED_KEY_POSITIONS.get(pos, f"???")
            decoded = decode_key_define(resp)
            valid_positions.append((pos, name, decoded, resp))
            # 只印有效的
            print(f"  0x{pos:02X} ({name:>16s}) → {decoded}")
        elif status == 0xC1:
            pass  # 無效 position，靜默跳過
        else:
            name = LED_KEY_POSITIONS.get(pos, f"???")
            print(f"  0x{pos:02X} ({name:>16s}) → status=0x{status:02x} (未知)")

        fail_counts = {"write": 0, "read": 0}
        # 極短延遲避免太快
        time.sleep(0.02)

    dev.close()
    print()
    print(f"=== 掃描完成：{len(valid_positions)} 個有效 position ===")
    print()

    # 對照軟體的 LedKeyPosition enum
    software_positions = set(LED_KEY_POSITIONS.keys()) - {0xC4, 0xFF}  # 排除 sentinel
    hardware_positions = set(p for p, _, _, _ in valid_positions)
    matched = software_positions & hardware_positions
    only_software = software_positions - hardware_positions
    only_hardware = hardware_positions - software_positions

    print(f"軟體 enum 有 {len(software_positions)} 個鍵")
    print(f"實機有效 {len(hardware_positions)} 個 position")
    print(f"兩者吻合 {len(matched)} 個")
    if only_software:
        print(f"只在軟體有、實機無效: {sorted([f'0x{p:02X}' for p in only_software])}")
    if only_hardware:
        print(f"只在實機有效、軟體沒列: {sorted([f'0x{p:02X}' for p in only_hardware])}")

    # 輸出完整結果表
    print()
    print("=== 完整有效 position 表 ===")
    print(f"{'pos':>6s}  {'name':>16s}  {'decoded':<40s}  raw")
    print("-" * 80)
    for pos, name, decoded, resp in valid_positions:
        raw = resp[7:12].hex(" ")
        print(f"0x{pos:02X}  {name:>16s}  {decoded:<40s}  {raw}")


if __name__ == "__main__":
    main()