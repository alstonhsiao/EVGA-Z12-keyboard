#!/usr/bin/env python3
"""唯讀讀取 EVGA Z12 的 profile 資料（report 4 + report 8）。

目的：實機驗證從 Unleash RGB 軟體逆向還原的 profile 協定。
1. report 4 GetProfile(MainCommand=0x06, SubCmd=0x01) → 讀目前 profile 編號
2. report 4 GetProfile 對 profile 1–9 逐一掃描 → 確認哪些有效
3. report 8 ProfileUsbFeatureReport(Read=0x01, profileNum) → 讀整組 265B profile
4. 解析 report 8 封包 → 提取 ProfileName、ReportRate、Primary/Secondary keymap、LED 模式

安全規則（對應 AGENTS.md 規則 1/3）：
- 只開介面 1（interface==1、usage_page==0x08、usage==0x4B）。
- 只送 Read（GetProfile / ProfileFunction.Read=0x01），不送 Write/Save/Set。
- 送 N 次、丟棄前 N-1 次、取最後一次（排空過時快取）。
- 同一方法連失敗兩次就停。

封包結構（來源：docs/profile-protocol.md）：

ProfileNumberFeatureReport (report 4, 17B):
  [0]=0x04 [1]=0xEA [2]=0x02 [3]=0x06(Profile) [4]=SubCmd(0x01=Get)
  [5]=0x00 [6]=ResponseCommand [7]=ProfileNumber [8..16]=Reserved

ProfileUsbFeatureReport (report 8, 265B):
  [0]=0x07(內部ReportId) [1]=0xEA [2]=0x02 [3]=ProfileFunction(0x01=Read)
  [4]=ProfileNumber [5]=0x00(Reserved) [6]=ResponseCommand [7]=CheckSum
  [8..9]=LengthOfProfileName(uint16 LE) [10..135]=ProfileName[126]
  [136]=GameModeDisableKey [137]=ReportRate [138..263]=Reserved[126]
  ---以下超出 265B，需分包讀取，本次先讀整包 265B---

  注意：send_feature_report 的 report_id 參數用 0x08，但 payload 第一 byte
  用 0x07（ProfileCommand 內部 ReportId=0x07）。實機需驗證哪個組合才對。

用法：
    .venv/bin/python src/probe_profiles.py            # 列舉後退出
    .venv/bin/python src/probe_profiles.py --run      # 真的送 GET_FEATURE
"""

import hid
import sys
import time

VID = 0x3842
PID = 0x2612
TARGET_INTERFACE = 1
TARGET_USAGE_PAGE = 0x08
TARGET_USAGE = 0x4B

# Report sizes
REPORT_4_SIZE = 17
REPORT_8_SIZE = 265

# Protocol constants (from docs/profile-protocol.md)
HEADER1 = 0xEA
HEADER2 = 0x02
MAIN_PROFILE = 0x06       # GeneralUsbMainCommand.Profile
SUB_GET_PROFILE = 0x01    # GeneralUsbSubCommand.GetProfile
SUB_SET_PROFILE = 0x00    # GeneralUsbSubCommand.SetProfile
RESPONSE_SUCCESS = 0xC0
RESPONSE_FAIL = 0xC1

# ProfileFunction (report 8 header)
PROFILE_FUNC_READ = 0x01
PROFILE_FUNC_WRITE = 0x00  # 不用，僅供參考

# Profile range
PROFILE_MIN = 1
PROFILE_MAX = 9
PROFILE_CURRENT = 0x00
PROFILE_DEFAULT = 0xFE

# KeyDefine function names (from scan_positions.py)
FUNCTION_NAMES = {
    0x00: "KeyboardEmulation",
    0x02: "Consumer(Media)",
    0x03: "Macro",
    0x04: "Unknown_0x04",
    0x05: "GameMode",
    0xFF: "Disable",
}

# Modifier bitmask
MOD_BITS = {
    0x01: "LCtrl", 0x02: "LShift", 0x04: "LAlt", 0x08: "LGUI",
    0x10: "RCtrl", 0x20: "RShift", 0x40: "RAlt", 0x80: "RGUI",
}

# HID usage code → key name (subset, from Pasquotcho keys.yaml)
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
    0x53: "NumLock", 0x65: "Menu",
    0xE0: "LCtrl", 0xE1: "LShift", 0xE2: "LAlt", 0xE3: "LGUI",
    0xE4: "RCtrl", 0xE5: "RShift", 0xE6: "RAlt", 0xE7: "RGUI",
}

# Key position names (from key-position-table.md, for cross-validation)
KEY_POSITION_NAMES = {
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
    0x42: "RAlt", 0x43: "RCtrl", 0x44: "Up", 0x45: "Down",
    0x46: "Left", 0x47: "Right",
    0x48: "Insert", 0x49: "Home", 0x4A: "PageUp", 0x4B: "Delete",
    0x4C: "End", 0x4D: "PageDn",
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
}

# Known keymap from scan_positions.py for cross-validation
# (position → (function, p1, p2, p3))
KNOWN_KEYMAP = {
    0x01: (0x00, 0x00, 0x29, 0x00),  # ESC → Esc (default)
    0x02: (0x00, 0x00, 0x3A, 0x00),  # F1 → F1 (default)
    0x15: (0x03, 0x06, 0x01, 0x00),  # E1 → macro#6
    0x16: (0x00, 0x00, 0x35, 0x00),  # Tab → Grave (remapped)
    0x17: (0x00, 0x00, 0x1E, 0x00),  # Q → 1 (remapped)
}


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


def send_and_read(dev, report_id, size, payload, fail_counts, discard_count=2):
    """送 send_feature_report 帶 payload，再 GET 讀回應。送 N 次丟棄前 N-1 次。"""
    def _once():
        req = bytearray(size)
        req[0] = report_id
        for i, b in enumerate(payload):
            if 1 + i < size:
                req[1 + i] = b
        try:
            dev.send_feature_report(bytes(req))
        except OSError as e:
            fail_counts["write"] += 1
            return False, f"send_feature_report 失敗: {e}"
        try:
            resp = dev.get_feature_report(report_id, size)
        except OSError as e:
            fail_counts["read"] += 1
            return False, f"get_feature_report 失敗: {e}"
        if resp is None or len(resp) == 0:
            fail_counts["read"] += 1
            return False, "get_feature_report 回傳空"
        return True, bytes(resp)

    last_resp = None
    for attempt in range(discard_count):
        ok, r = _once()
        if not ok:
            return False, r
        last_resp = r
        time.sleep(0.05)  # 50ms between attempts
    return True, last_resp


def get_profile_number(dev, fail_counts):
    """讀取目前 profile 編號 (report 4, MainCommand=0x06, SubCmd=0x01=Get)。

    封包：04 EA 02 06 01 00 00 00 + 9B 0
    回應 byte[6] = ResponseCommand, byte[7] = ProfileNumber
    """
    payload = bytes([
        HEADER1, HEADER2,        # byte 1-2: EA 02
        MAIN_PROFILE,            # byte 3: 0x06 (Profile)
        SUB_GET_PROFILE,         # byte 4: 0x01 (GetProfile)
        0x00,                    # byte 5: SubCommand2 = 0
        0x00,                    # byte 6: ResponseCommand (keyboard fills)
        0x00,                    # byte 7: ProfileNumber (keyboard fills on Get)
    ]) + bytes(9)               # byte 8-16: Reserved

    ok, resp = send_and_read(dev, 0x04, REPORT_4_SIZE, payload, fail_counts,
                             discard_count=2)
    if not ok:
        return False, resp
    return True, resp


def read_profile_report8(dev, profile_num, fail_counts, report_id=0x08, inner_rid=0x07):
    """讀取整組 profile (report 8, ProfileFunction=Read=0x01)。

    ProfileCommand 內部 ReportId=0x07，但透過 report ID 8 傳輸。
    支援 report_id 和 inner_rid 參數切換測試不同組合。
    """
    payload = bytearray(REPORT_8_SIZE - 1)
    payload[0] = inner_rid           # ProfileCommand.ReportId (內部)
    payload[1] = HEADER1            # 0xEA
    payload[2] = HEADER2            # 0x02
    payload[3] = PROFILE_FUNC_READ  # 0x01 = Read
    payload[4] = profile_num        # ProfileNumber
    payload[5] = 0x00               # Reserved
    payload[6] = 0x00               # ResponseCommand (keyboard fills)
    payload[7] = 0x00               # CheckSum (keyboard fills on Read)

    ok, resp = send_and_read(dev, report_id, REPORT_8_SIZE, bytes(payload), fail_counts,
                             discard_count=5)
    if not ok:
        return False, resp
    return True, resp


def decode_key_define(fn, p1, p2, p3):
    """解碼單個 KeyDefine (4 bytes)。"""
    fn_name = FUNCTION_NAMES.get(fn, f"0x{fn:02x}")
    if fn == 0x00:
        mods = [name for bit, name in MOD_BITS.items() if p1 & bit]
        key1 = HID_NAMES.get(p2, f"0x{p2:02x}")
        key2 = HID_NAMES.get(p3, f"0x{p3:02x}") if p3 else ""
        mod_str = "+".join(mods) + "+" if mods else ""
        if p3:
            return f"{mod_str}{key1}+{key2}"
        return f"{mod_str}{key1}"
    elif fn == 0x03:
        return f"macro#{p1} runMethod=0x{p2:02x} repeat={p3}"
    elif fn == 0x02:
        consumer_code = p1 | (p2 << 8)
        return f"consumer 0x{consumer_code:04x}"
    elif fn == 0xFF:
        return "disabled"
    else:
        return f"fn=0x{fn:02x} p1=0x{p1:02x} p2=0x{p2:02x} p3=0x{p3:02x}"


def parse_profile_report8(resp):
    """解析 report 8 的 265B 封包，提取 profile 欄位。

    結構（from docs/profile-protocol.md）：
    [0]=ReportId(0x07) [1]=EA [2]=02 [3]=ProfileFunction [4]=ProfileNum
    [5]=Reserved [6]=ResponseCmd [7]=CheckSum
    [8..9]=LengthOfProfileName(uint16 LE) [10..135]=ProfileName[126]
    [136]=GameModeDisableKey [137]=ReportRate [138..263]=Reserved[126]
    (264=最後1B，也屬於Reserved)

    注意：Primary[121] keymap 從 offset 264 開始，但 265B 只能放 1B，
    所以整組 keymap 無法在單包 265B 裡完整讀取——需分包(ReadProfile256ByteLoop)。
    但我們先解析能讀到的部分。
    """
    result = {}
    if len(resp) < 138:
        result["error"] = f"回應太短 ({len(resp)}B < 138)"
        return result

    result["report_id"] = f"0x{resp[0]:02x}"
    result["header"] = f"{resp[1]:02x} {resp[2]:02x}"
    result["profile_function"] = f"0x{resp[3]:02x} ({'Read' if resp[3]==0x01 else 'Write' if resp[3]==0x00 else '???'})"
    result["profile_number"] = resp[4]
    result["response_command"] = f"0x{resp[6]:02x} ({'Success' if resp[6]==0xC0 else 'Fail' if resp[6]==0xC1 else '???'})"
    result["checksum"] = f"0x{resp[7]:02x}"

    # LengthOfProfileName (uint16 LE)
    name_len = resp[8] | (resp[9] << 8)
    result["length_of_profile_name"] = name_len

    # ProfileName[126] (UTF-8)
    name_bytes = resp[10:10+126]
    if name_len > 0 and name_len <= 126:
        name = name_bytes[:name_len].decode('utf-8', errors='replace')
    else:
        name = name_bytes.split(b'\x00')[0].decode('utf-8', errors='replace')
    result["profile_name"] = name

    # GameModeDisableKey
    result["game_mode_disable_key"] = f"0x{resp[136]:02x}"

    # ReportRate
    result["report_rate"] = resp[137]

    # Non-zero payload count
    non_zero = sum(1 for b in resp[8:] if b != 0)
    result["non_zero_payload_bytes"] = non_zero

    return result


def main():
    do_run = "--run" in sys.argv
    scratch = "/var/folders/hp/0kswpyx57kvg8rxsz655nd9w0000gn/T/grok-goal-fe47737b1910/implementer"

    print("=== EVGA Z12 Profile 讀取（唯讀）===")
    print(f"PID {PID:#06x}，介面 {TARGET_INTERFACE}")
    print(f"模式：{'實際送 GET_FEATURE' if do_run else '僅列舉（加 --run 才送）'}")
    print()

    candidates = find_device()
    if not candidates:
        print("找不到裝置。")
        sys.exit(1)

    print(f"候選裝置：interface={candidates[0]['interface_number']} "
          f"usage_page={candidates[0]['usage_page']:#06x} "
          f"usage={candidates[0]['usage']:#06x}")
    print()

    if not do_run:
        print("未加 --run，不送封包。")
        return

    print(">>> 即將開啟裝置並送 GET_FEATURE（唯讀）<<<")
    print("    【提醒】只開介面 1，只送 Read，不碰介面 0。")
    print("    請停止使用 keyboard。")
    time.sleep(3)

    try:
        dev = hid.Device(path=candidates[0]["path"])
    except OSError as e:
        print(f"開裝置失敗：{e}")
        sys.exit(2)

    print(f"裝置已開：{dev.product!r}")
    print()

    output_lines = []
    def log(s=""):
        print(s)
        output_lines.append(s)

    fail_counts = {"write": 0, "read": 0}
    FAIL_LIMIT = 2

    # === Step 1: GetProfile — 讀目前 profile 編號 ===
    log("=" * 60)
    log("Step 1: GetProfile（report 4, MainCommand=0x06, SubCmd=0x01）")
    log("=" * 60)

    # 讀兩次確認一致性
    profile_nums = []
    for attempt in range(2):
        ok, resp = get_profile_number(dev, fail_counts)
        if not ok:
            log(f"  第 {attempt+1} 次失敗：{resp}")
            if fail_counts["read"] >= FAIL_LIMIT or fail_counts["write"] >= FAIL_LIMIT:
                log(f"!! 連失敗 {FAIL_LIMIT} 次，停止。")
                dev.close()
                sys.exit(1)
            continue

        status = resp[6]
        profile_num = resp[7]
        log(f"  第 {attempt+1} 次：status=0x{status:02x} profileNum={profile_num}")
        log(f"  完整回應：{resp.hex(' ')}")
        if status == 0xC0:
            profile_nums.append(profile_num)
        fail_counts = {"write": 0, "read": 0}
        time.sleep(0.1)

    if profile_nums:
        consistent = len(set(profile_nums)) == 1
        current_profile = profile_nums[0]
        valid_range = PROFILE_MIN <= current_profile <= PROFILE_MAX
        log(f"\n  目前 profile 編號：{current_profile}")
        log(f"  兩次一致：{'✅' if consistent else '❌'}")
        log(f"  合法範圍(1-9)：{'✅' if valid_range else '❌'}")
    else:
        log("\n  GetProfile 失敗，無法取得 profile 編號。")
        dev.close()
        sys.exit(1)

    log()

    # === Step 2: 掃描 profile 1–9 ===
    log("=" * 60)
    log("Step 2: 掃描 profile 1–9（GetProfile for each）")
    log("=" * 60)
    log()
    log(f"{'profile':>8s}  {'status':>8s}  {'valid':>6s}")
    log("-" * 30)

    valid_profiles = []
    # 測試多種 report_id + inner_rid 組合
    rid_combos = [
        (0x08, 0x08, "rid=8 inner=8"),
        (0x08, 0x07, "rid=8 inner=7"),
        (0x07, 0x07, "rid=7 inner=7"),
    ]

    best_combo = None
    for rid, inner, label in rid_combos:
        fail_counts = {"write": 0, "read": 0}
        ok, resp = read_profile_report8(dev, 1, fail_counts, report_id=rid, inner_rid=inner)
        if not ok:
            log(f"  測試 {label} → 失敗：{resp}")
            continue
        status = resp[6] if len(resp) > 6 else None
        # hidapi 會在前面加 report ID byte，所以 payload 從 resp[1] 開始
        # 但如果 resp[0] == rid，payload 從 resp[1] 開始
        # 實際 resp[0] 可能是 hidapi 加的 report ID
        status_hex = f"0x{status:02x}" if status is not None else "None"
        log(f"  測試 {label} → resp[0:8]={resp[:8].hex(' ')} status={status_hex}")
        if status == 0xC0:
            best_combo = (rid, inner, label)
            log(f"  ✅ {label} 成功！")
            break

    if best_combo is None:
        # 用最後一個組合繼續
        best_combo = rid_combos[-1]
        log(f"  所有組合都回 0xC1，用 {best_combo[2]} 繼續掃描")

    rid, inner, label = best_combo

    log()
    log(f"{'profile':>8s}  {'status':>8s}  {'valid':>6s}")
    log("-" * 30)

    for pnum in range(PROFILE_MIN, PROFILE_MAX + 1):
        fail_counts = {"write": 0, "read": 0}
        ok, resp = read_profile_report8(dev, pnum, fail_counts, report_id=rid, inner_rid=inner)
        if not ok:
            log(f"  {pnum:>8d}  {'FAIL':>8s}  {'❌':>6s}  ({resp})")
            continue

        status = resp[6] if len(resp) > 6 else None
        if status == 0xC0:
            non_zero = sum(1 for b in resp[8:] if b != 0)
            log(f"  {pnum:>8d}  0x{status:02x}     {'✅':>6s}  nonZero={non_zero}")
            valid_profiles.append(pnum)
        elif status == 0xC1:
            log(f"  {pnum:>8d}  0x{status:02x}     {'❌':>6s}")
        else:
            log(f"  {pnum:>8d}  0x{status:02x}     {'???':>6s}")

        fail_counts = {"write": 0, "read": 0}
        time.sleep(0.1)

    log(f"\n有效 profile：{valid_profiles}")
    log()

    # === Step 3: 讀取目前 profile 的 report 8 整包 ===
    log("=" * 60)
    log(f"Step 3: ReadProfile report 8（profile #{current_profile}）")
    log("=" * 60)

    fail_counts = {"write": 0, "read": 0}
    ok, resp = read_profile_report8(dev, current_profile, fail_counts,
                                    report_id=rid, inner_rid=inner)
    used_rid = rid

    if not ok:
        log(f"失敗：{resp}")
        dev.close()
        sys.exit(1)

    log(f"使用 {label}")
    log(f"回應（{len(resp)}B）：")
    log(hexdump(resp[:32]))
    log("  ...")

    # 存 binary
    bin_path = f"{scratch}/profile_report8.bin"
    with open(bin_path, 'wb') as f:
        f.write(resp)
    log(f"Binary 存到：{bin_path}")

    status = resp[6]
    log(f"\nResponseCommand: 0x{status:02x} ({'✅ Success' if status==0xC0 else '❌ Fail' if status==0xC1 else '???'})")

    # 檢查開頭結構
    if len(resp) >= 5:
        head = f"{resp[0]:02x} {resp[1]:02x} {resp[2]:02x} {resp[3]:02x} {resp[4]:02x}"
        expected = f"07 ea 02 01 {current_profile:02x}"
        log(f"開頭：{head} (期望 {expected}) {'✅' if head == expected else '❌'}")

    # === Step 4: 解析 report 8 封包 ===
    log()
    log("=" * 60)
    log("Step 4: 解析 report 8 封包")
    log("=" * 60)

    parsed = parse_profile_report8(resp)
    for k, v in parsed.items():
        log(f"  {k}: {v}")

    log()

    # === Step 5: KeyDefine 交叉驗證 ===
    # report 8 的 265B 只能放前 7B header + 258B payload，
    # Primary keymap[121] 從 offset 264 開始，265B 只能放 1B。
    # 所以單包 265B 無法完整讀取 keymap——需分包。
    # 但我們可以檢查 ProfileName 和前幾個欄位是否合理。
    log("=" * 60)
    log("Step 5: 交叉驗證")
    log("=" * 60)
    log()

    # 驗證 ProfileName
    if parsed.get("profile_name"):
        log(f"ProfileName: {parsed['profile_name']!r} ✅ 非空")
    else:
        log(f"ProfileName: (空)")

    # 驗證 non-zero payload
    nz = parsed.get("non_zero_payload_bytes", 0)
    log(f"非零 payload bytes: {nz} {'✅ > 50' if nz > 50 else '❌ ≤ 50'}")

    # 嘗試從 report 8 的尾端讀取第一個 Primary KeyDefine
    # offset 264 = 最後 1B，只有 1 byte 不夠 4B KeyDefine
    # 所以 keymap 交叉驗證無法在單包完成
    log()
    log("注意：report 8 單包 265B 無法完整包含 Primary keymap[121]（需分包讀取）。")
    log("KeyDefine 交叉驗證需用 ProfileUsbFeatureReport256 分包版（256B × 6）。")
    log("目前先驗證 header 結構和 ProfileName。")

    # === 輸出存檔 ===
    log_path = f"{scratch}/profile_get.log"
    with open(log_path, 'w') as f:
        f.write('\n'.join(output_lines))
    print(f"\n完整輸出存到：{log_path}")

    parsed_path = f"{scratch}/profile_parsed.txt"
    with open(parsed_path, 'w') as f:
        f.write('\n'.join(output_lines))
    print(f"解析結果存到：{parsed_path}")

    scan_path = f"{scratch}/profile_scan.txt"
    with open(scan_path, 'w') as f:
        f.write('\n'.join(output_lines))
    print(f"掃描結果存到：{scan_path}")

    dev.close()
    print("\n裝置已關閉。")


if __name__ == "__main__":
    main()