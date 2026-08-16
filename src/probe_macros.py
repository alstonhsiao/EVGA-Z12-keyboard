#!/usr/bin/env python3
"""唯讀讀取 EVGA Z12 的巨集本體（report 9 / report 10）。

目的：從 Unleash RGB 軟體逆向還原的協定，實機驗證巨集讀取流程。
1. report 9 MacroStatus(Read) → 查哪些巨集編號已使用
2. report 10 MacroNameData(Read, idx) → 讀巨集名稱
3. report 9 MacroData(Read, idx, PackIndex 0..3) → 分 4 包讀巨集本體
4. 解碼 VK code 序列（初步，tag-based）

安全規則（對應 AGENTS.md 規則 1/3）：
- 只開介面 1（interface==1、usage_page==0x08、usage==0x4B）。
- 只送 Read（Direction=0x01），不送 Write。
- 送兩次、丟棄首次、取第二次（排空過時快取）。
- 同一方法失敗兩次就停。

封包結構（來源：docs/unleash-reverse-engineering.md）：

MacroStatus (report 9, 265B):
  [0]=0x09 [1]=0xEA [2]=Direction(Read=0x01) [3..264]=Status[263]
  Status[i]==1 → 巨集編號 (i+1) 已使用（程式碼從 serialized[8] 起檢查，
  即 Status[8]..Status[0x6B]，對應巨集編號 1..100）

MacroData (report 9, 265B):
  [0]=0x09 [1]=0xEA [2]=Direction [3]=Command(Data=0x01)
  [4]=MacroIndex [5]=PackIndex(0..3) [6]=ResponseCommand
  [7]=Checksum [8..263]=Data[256] [264]=Reserved

MacroNameData (report 10, 59B):
  [0]=0x0A [1]=0xEA [2]=0x02 [3]=Direction [4]=MacroIndex
  [5]=Reserved [6]=ResponseCommand [7]=Checksum [8]=NameCount
  [9..58]=Name[50] (UTF-8)

用法：
    .venv/bin/python src/probe_macros.py            # 列舉後退出
    .venv/bin/python src/probe_macros.py --run      # 真的送 GET_FEATURE
"""

import hid
import sys

VID = 0x3842
PID = 0x2612
TARGET_INTERFACE = 1
TARGET_USAGE_PAGE = 0x08
TARGET_USAGE = 0x4B

# Report sizes (from descriptor)
REPORT_9_SIZE = 265
REPORT_10_SIZE = 59

# Protocol constants (from EDispNetLib.dll reverse engineering)
HEADER1 = 0xEA
HEADER2 = 0x02
DIRECTION_READ = 0x01
DIRECTION_WRITE = 0x02  # 不用，僅供參考
MACRO_CMD_DATA = 0x01
MACRO_CMD_STATUS = 0x00
RESPONSE_SUCCESS = 0xC0
RESPONSE_FAIL = 0xC1

# 我們從 report 4 讀到的 E-key → 巨集編號對應
# (mod 值就是巨集編號)
EKEY_MACRO_INDICES = {
    "E1": 0x06,
    "E2": 0x07,
    "E3": 0x04,
    "E4": 0x05,
    "E5": 0x03,
}

# HID usage code → 名稱（用於巨集動作解碼，從 Pasquotcho keys.yaml）
HID_USAGE_NAMES = {
    0x04: "A", 0x05: "B", 0x06: "C", 0x07: "D", 0x08: "E", 0x09: "F",
    0x0A: "G", 0x0B: "H", 0x0C: "I", 0x0D: "J", 0x0E: "K", 0x0F: "L",
    0x10: "M", 0x11: "N", 0x12: "O", 0x13: "P", 0x14: "Q", 0x15: "R",
    0x16: "S", 0x17: "T", 0x18: "U", 0x19: "V", 0x1A: "W", 0x1B: "X",
    0x1C: "Y", 0x1D: "Z",
    0x1E: "1", 0x1F: "2", 0x20: "3", 0x21: "4", 0x22: "5",
    0x23: "6", 0x24: "7", 0x25: "8", 0x26: "9", 0x27: "0",
    0x28: "Enter", 0x29: "Esc", 0x2A: "Backspace", 0x2B: "Tab",
    0x2C: "Space",
    0x2D: "-", 0x2E: "=", 0x2F: "[", 0x30: "]", 0x31: "\\",
    0x33: ";", 0x34: "'", 0x35: "`", 0x36: ",", 0x37: ".", 0x38: "/",
    0x39: "CapsLock",
    0x3A: "F1", 0x3B: "F2", 0x3C: "F3", 0x3D: "F4", 0x3E: "F5",
    0x3F: "F6", 0x40: "F7", 0x41: "F8", 0x42: "F9", 0x43: "F10",
    0x44: "F11", 0x45: "F12",
    0x46: "PrintScreen", 0x47: "ScrollLock", 0x48: "Pause",
    0x49: "Insert", 0x4A: "Home", 0x4B: "PageUp",
    0x4C: "Delete", 0x4D: "End", 0x4E: "PageDown",
    0x4F: "Right", 0x50: "Left", 0x51: "Down", 0x52: "Up",
    0x53: "NumLock",
    0x59: "Num1", 0x5A: "Num2", 0x5B: "Num3", 0x5C: "Num4",
    0x5D: "Num5", 0x5E: "Num6", 0x5F: "Num7", 0x60: "Num8",
    0x61: "Num9", 0x62: "Num0",
    0x63: "Num.", 0x54: "Num/", 0x55: "Num*", 0x56: "Num-",
    0x57: "Num+", 0x58: "NumEnter",
    0x65: "Menu",
    0x68: "F13", 0x69: "F14", 0x6A: "F15", 0x6B: "F16",
    0x6C: "F17", 0x6D: "F18", 0x6E: "F19", 0x6F: "F20",
    0x70: "F21", 0x71: "F22", 0x72: "F23", 0x73: "F24",
    # Modifier keys (HID usage 0xE0–0xE7)
    0xE0: "LCtrl", 0xE1: "LShift", 0xE2: "LAlt", 0xE3: "LGUI",
    0xE4: "RCtrl", 0xE5: "RShift", 0xE6: "RAlt", 0xE7: "RGUI",
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
    """送 send_feature_report 帶 payload，再 GET 讀回應。

    discard_count=2：送兩次、丟棄首次、取第二次（預設，排空過時快取）。
    report 9/10 之間可能 cross-report 快取污染，可提高 discard_count。
    """
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
    return True, last_resp


def read_macro_status(dev, fail_counts):
    """送 report 9 MacroStatus(Read)，回傳 Status[263] 位元陣列。

    封包：[0x09, 0xEA, 0x01(Read), 0x00...(填到 265B)]
    回應：[0x09, 0xEA, 0x01, Status[263]...]
    """
    # MacroStatus: ReportId + Header1 + Direction(Read) + Status[263]
    # payload 从 byte 1 开始（byte 0 是 report ID，由 send_and_read 填）
    payload = bytes([HEADER1, DIRECTION_READ]) + bytes(263)
    ok, resp = send_and_read(dev, 0x09, REPORT_9_SIZE, payload, fail_counts)
    if not ok:
        return False, resp
    return True, resp


def read_macro_name(dev, macro_idx, fail_counts):
    """送 report 10 MacroNameData(Read, idx)，回傳名稱。

    封包：[0x0A, 0xEA, 0x02, 0x01(Read), idx, 0x00, 0xC1, 0x00, 0x00, 0x00...(59B)]
    """
    payload = bytearray(REPORT_10_SIZE - 1)  # 減去 report ID
    payload[0] = HEADER1      # 0xEA
    payload[1] = HEADER2      # 0x02
    payload[2] = DIRECTION_READ  # Read
    payload[3] = macro_idx    # MacroIndex
    payload[4] = 0x00         # Reserved
    payload[5] = RESPONSE_FAIL  # 預設 Fail（鍵盤成功時回 0xC0）
    # payload[6] = checksum（鍵盤算）
    # payload[7] = NameCount
    # payload[8..57] = Name[50]

    ok, resp = send_and_read(dev, 0x0A, REPORT_10_SIZE, bytes(payload), fail_counts)
    if not ok:
        return False, resp
    return True, resp


def read_macro_data(dev, macro_idx, pack_idx, fail_counts):
    """送 report 9 MacroData(Read, idx, packIdx)，回傳 Data[256]。

    封包：[0x09, 0xEA, 0x01(Read), 0x01(Data), idx, packIdx, 0x00, 0x00, 0x00...(265B)]
    """
    payload = bytearray(REPORT_9_SIZE - 1)
    payload[0] = HEADER1          # 0xEA
    payload[1] = DIRECTION_READ   # Read
    payload[2] = MACRO_CMD_DATA   # Data
    payload[3] = macro_idx        # MacroIndex
    payload[4] = pack_idx         # PackIndex
    payload[5] = 0x00             # ResponseCommand（鍵盤填）
    payload[6] = 0x00             # Checksum（鍵盤算）
    # payload[7..262] = Data[256]
    # payload[263] = Reserved

    ok, resp = send_and_read(dev, 0x09, REPORT_9_SIZE, bytes(payload), fail_counts,
                             discard_count=3)
    if not ok:
        return False, resp
    return True, resp


def decode_macro_data(data):
    """解碼巨集本體的 tag-based 編碼。

    實證格式（2026-08-16）：
    - 0x01 + 16-bit LE ms = 延遲（如 01 14 00 = 20ms）
    - 0x04 0x00 = 無延遲
    - 單 byte（0x01–0x73）= HID usage code 按下
    - 單 byte | 0x80（0x81–0xF3）= HID usage code 放開
    - 0x03 + 16-bit HID usage = 多媒體/系統鍵（3 bytes）
    - 滑鼠：0x80+X+Y 移動、0x7A/0x7B/0x7C 按下、0xFA/0xFB/0xFC 放開
    - 連續 8 個 0x00 = 動作結束

    回傳動作列表。
    """
    actions = []
    i = 0
    while i < len(data):
        b = data[i]

        # 結束判定：連續 8 個 0
        if b == 0x00:
            if all(x == 0 for x in data[i:i+8]):
                actions.append(("END", f"@offset {i}"))
                break
            i += 1
            continue

        # 延遲：0x01 + 16-bit LE ms
        if b == 0x01:
            if i + 2 < len(data):
                ms = data[i+1] | (data[i+2] << 8)
                actions.append(("DELAY", f"{ms}ms"))
                i += 3
            else:
                actions.append(("DELAY?", f"truncated @ {i}"))
                break

        # 無延遲（0x04 後面跟 0x00，且 0x04 不在延遲之後）
        # 注意：0x04 同時是 HID usage A。實測中 0x04 總是出現在延遲之後
        # 作為按鍵 A，NO_DELAY 從未出現。為安全起見，只在 0x04 後面
        # 確實是 0x00 且再後面不是按鍵模式時才當 NO_DELAY。
        elif b == 0x04:
            if i + 1 < len(data) and data[i+1] == 0x00:
                # 0x04 0x00 — 可能是 NO_DELAY 或 A 放開後的填充
                # 檢查再後面是否是延遲(0x01)或按鍵
                if i + 2 < len(data) and data[i+2] == 0x01:
                    # 後面跟延遲 → 0x04 是按鍵 A，0x00 是夾雜的
                    actions.append(("KEY_DOWN", "A"))
                    i += 1
                else:
                    actions.append(("NO_DELAY", ""))
                    i += 2
            else:
                # 0x04 後面不是 0x00 → 按 A
                actions.append(("KEY_DOWN", "A"))
                i += 1

        # 多媒體/系統鍵
        elif b == 0x03:
            if i + 2 < len(data):
                usage = data[i+1] | (data[i+2] << 8)
                actions.append(("MEDIA", f"HID usage 0x{usage:04x}"))
                i += 3
            else:
                actions.append(("MEDIA?", f"truncated @ {i}"))
                break

        # 滑鼠按鍵按下
        elif b in (0x7A, 0x7B, 0x7C):
            btn = {0x7A: "L", 0x7B: "R", 0x7C: "M"}[b]
            actions.append(("MOUSE_DOWN", btn))
            i += 1

        # 滑鼠按鍵放開
        elif b in (0xFA, 0xFB, 0xFC):
            btn = {0xFA: "L", 0xFB: "R", 0xFC: "M"}[b]
            actions.append(("MOUSE_UP", btn))
            i += 1

        # 滾輪
        elif b in (0xF8, 0x78):
            actions.append(("WHEEL", f"0x{b:02x}"))
            i += 1

        # 鍵盤鍵放開（usage | 0x80，範圍 0x81–0xF3，排除上面的滑鼠 tag）
        elif (b & 0x80) and b not in (0xFA, 0xFB, 0xFC, 0xF8, 0x7A, 0x7B, 0x7C):
            # 滑鼠移動 0x80 後面跟 2 byte 座標，鍵放開只有 1 byte
            # 區分方式：鍵放開的 usage 範圍是 0x04–0x73，所以 0x84–0xF3
            # 0x80 本身可能是滑鼠移動（如果後面跟座標）或 usage 0x00 放開（無意義）
            usage = b & 0x7F
            if usage == 0x00:
                # 0x80 可能是滑鼠移動 tag
                if i + 2 < len(data):
                    actions.append(("MOUSE_MOVE", f"x={data[i+1]} y={data[i+2]}"))
                    i += 3
                else:
                    actions.append(("UNKNOWN", f"0x{b:02x} @ {i}"))
                    i += 1
            else:
                name = HID_USAGE_NAMES.get(usage, f"HID 0x{usage:02x}")
                actions.append(("KEY_UP", name))
                i += 1

        # 鍵盤鍵按下（HID usage code 0x04–0x73，加上修飾鍵 0xE0–0xE7）
        elif (0x04 <= b <= 0x73) or (0xE0 <= b <= 0xE7):
            name = HID_USAGE_NAMES.get(b, f"HID 0x{b:02x}")
            actions.append(("KEY_DOWN", name))
            i += 1

        else:
            actions.append(("UNKNOWN", f"0x{b:02x} @ {i}"))
            i += 1

    return actions


def main():
    do_run = "--run" in sys.argv

    print(f"=== EVGA Z12 巨集讀取（PID {PID:#06x}）===")
    print(f"目標：介面 {TARGET_INTERFACE}")
    print(f"模式：{'實際送 GET_FEATURE（唯讀）' if do_run else '僅列舉（加 --run 才送）'}")
    print()

    candidates = find_device()
    if not candidates:
        print("找不到符合條件的裝置。")
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
    try:
        import time
        time.sleep(3)
    except KeyboardInterrupt:
        print("已中止。")
        return

    try:
        dev = hid.Device(path=candidates[0]["path"])
    except OSError as e:
        print(f"開裝置失敗：{e}")
        sys.exit(2)

    print(f"裝置已開：manufacturer={dev.manufacturer!r} product={dev.product!r}")
    print()

    fail_counts = {"write": 0, "read": 0}
    FAIL_LIMIT = 2

    # === 步驟 1：MacroStatus 查哪些巨集編號已使用 ===
    print("=" * 60)
    print("步驟 1：MacroStatus（report 9）— 查巨集使用狀態")
    print("=" * 60)

    ok, resp = read_macro_status(dev, fail_counts)
    if not ok:
        print(f"失敗：{resp}")
        if fail_counts["read"] >= FAIL_LIMIT or fail_counts["write"] >= FAIL_LIMIT:
            print(f"\n!! 連失敗 {FAIL_LIMIT} 次，停止。")
            dev.close()
            return
    else:
        print(f"回應（{len(resp)}B）：")
        print(hexdump(resp[:32]))  # 只印前 32 bytes
        print("  ...")

        # 解析 Status 位元陣列
        # 程式碼從 serialized[8] 起檢查（即 resp[8]），對應巨集編號 1..100
        # resp[8] == 1 → 巨集編號 1 已使用
        # resp[i] == 1 → 巨集編號 (i - 7) 已使用
        used_macros = []
        for i in range(8, min(8 + 100, len(resp))):
            if resp[i] == 1:
                macro_idx = i - 7
                used_macros.append(macro_idx)

        print(f"\n已使用的巨集編號：{used_macros if used_macros else '（無）'}")

        # 對照 E-key 的巨集編號
        print(f"\n對照 E-key：")
        for name, idx in EKEY_MACRO_INDICES.items():
            used = idx in used_macros
            print(f"  {name} → 巨集 #{idx:02d} → {'✅ 已使用' if used else '❌ 未使用'}")

    print()
    fail_counts = {"write": 0, "read": 0}

    # === 步驟 2：讀巨集名稱（report 10）===
    print("=" * 60)
    print("步驟 2：MacroNameData（report 10）— 讀巨集名稱")
    print("=" * 60)

    # 只讀我們知道有綁定到 E-key 的巨集編號
    macros_to_read = sorted(set(EKEY_MACRO_INDICES.values()))
    macro_names = {}

    for idx in macros_to_read:
        ekey = [k for k, v in EKEY_MACRO_INDICES.items() if v == idx][0]
        print(f"\n--- 巨集 #{idx:02d}（{ekey}）---")
        ok, resp = read_macro_name(dev, idx, fail_counts)
        if not ok:
            print(f"  失敗：{resp}")
            fail_counts = {"write": 0, "read": 0}
            continue

        status = resp[6] if len(resp) > 6 else None
        name_count = resp[8] if len(resp) > 8 else 0
        name_bytes = resp[9:9+50] if len(resp) > 9 else b""
        # 截取到第一個 0x00
        name = name_bytes.split(b'\x00')[0].decode('utf-8', errors='replace')

        print(f"  回應：{resp[:16].hex(' ')}...")
        print(f"  ResponseCommand: 0x{status:02x} ({'✅ Success' if status == 0xC0 else '❌ Fail' if status == 0xC1 else '???'})")
        print(f"  NameCount: {name_count}")
        print(f"  Name: {name!r}")

        if status == 0xC0 and name:
            macro_names[idx] = name

        fail_counts = {"write": 0, "read": 0}
        import time
        time.sleep(0.1)

    print()

    # === 步驟 3：讀巨集本體（report 9 MacroData, PackIndex 0..3）===
    print("=" * 60)
    print("步驟 3：MacroData（report 9）— 讀巨集本體（分 4 包）")
    print("=" * 60)
    print()
    print("封包結構：MacroData.Data[256] = serialized MacroUsbFeatureReport[8+packIdx*256 .. +256]")
    print("完整模板 1032B: [header 8B] [LengthOfName 1B] [Name 50B] [RunMethod 1B]")
    print("  [Repeat 1B] [TimeUnit 1B] [LengthOfData 2B] [MacroData 967B] [StatusOfUse 1B]")
    print("巨集動作本體在模板 offset 64 開始（= PackIndex0 Data offset 56）")
    print()

    for idx in macros_to_read:
        ekey = [k for k, v in EKEY_MACRO_INDICES.items() if v == idx][0]
        name = macro_names.get(idx, "(未知名稱)")
        print(f"\n{'='*40}")
        print(f"巨集 #{idx:02d}（{ekey}）— 名稱: {name!r}")
        print(f"{'='*40}")

        all_payload = bytearray()  # 拼回的 serialized[8..1031] = 1024B

        for pack_idx in range(4):
            print(f"\n  PackIndex {pack_idx}:")
            ok, resp = read_macro_data(dev, idx, pack_idx, fail_counts)
            if not ok:
                print(f"    失敗：{resp}")
                if fail_counts["read"] >= FAIL_LIMIT or fail_counts["write"] >= FAIL_LIMIT:
                    print(f"    !! 連失敗 {FAIL_LIMIT} 次，停止此巨集。")
                    break
                fail_counts = {"write": 0, "read": 0}
                continue

            status = resp[6] if len(resp) > 6 else None
            checksum = resp[7] if len(resp) > 7 else None
            data = resp[8:8+256] if len(resp) > 8 else b""

            # 驗證 checksum: -(sum of Data) & 0xFF
            calc_checksum = (-(sum(data))) & 0xFF

            print(f"    ResponseCommand: 0x{status:02x} ({'✅' if status == 0xC0 else '❌' if status == 0xC1 else '???'})")
            print(f"    Checksum: 0x{checksum:02x} (計算: 0x{calc_checksum:02x} {'✅' if checksum == calc_checksum else '❌'})")
            non_zero = sum(1 for b in data if b != 0)
            print(f"    Data[{len(data)}B]: {non_zero}B 非 0")
            if non_zero > 0:
                print(f"    前 32B: {data[:32].hex(' ')}")

            if status == 0xC0:
                all_payload.extend(data)

            fail_counts = {"write": 0, "read": 0}
            import time
            time.sleep(0.15)

        if all_payload:
            # all_payload = serialized[8..1031] = 1024B
            # 模板 offset 8 = all_payload[0] = LengthOfMacroName
            # 模板 offset 9..58 = all_payload[1..50] = MacroName[50]
            # 模板 offset 59 = all_payload[51] = RunMethodOfMacro
            # 模板 offset 60 = all_payload[52] = RepeatTimeOfMacro
            # 模板 offset 61 = all_payload[53] = TimeUnitOfMacro
            # 模板 offset 62..63 = all_payload[54..55] = LengthOfMacroData (uint16 LE)
            # 模板 offset 64..1030 = all_payload[56..1022] = MacroData[967]
            # 模板 offset 1031 = all_payload[1023] = MacroStatusOfUse

            print(f"\n  拼回的 payload（{len(all_payload)}B）:")
            if len(all_payload) > 0:
                length_of_name = all_payload[0]
                macro_name_bytes = all_payload[1:1+50]
                macro_name = macro_name_bytes.split(b'\x00')[0].decode('utf-8', errors='replace')
                run_method = all_payload[51] if len(all_payload) > 51 else None
                repeat_time = all_payload[52] if len(all_payload) > 52 else None
                time_unit = all_payload[53] if len(all_payload) > 53 else None
                length_of_data = (all_payload[54] | (all_payload[55] << 8)) if len(all_payload) > 55 else 0
                status_of_use = all_payload[1023] if len(all_payload) > 1023 else None

                run_method_names = {0: "Looping_KeyRelease", 1: "OneShot_KeyRelease",
                                    2: "MultiStage_KeyRelease", 3: "Repeat_KeyRelease",
                                    4: "TwoPhase", 8: "Looping_KeyPress",
                                    9: "OneShot_KeyPress", 10: "MultiStage_KeyPress"}
                status_names = {0: "未使用", 1: "使用中", 0xFF: "已刪除"}

                print(f"    LengthOfMacroName: {length_of_name}")
                print(f"    MacroName: {macro_name!r}")
                print(f"    RunMethodOfMacro: 0x{run_method:02x} ({run_method_names.get(run_method, '???')})" if run_method is not None else "")
                print(f"    RepeatTimeOfMacro: {repeat_time}")
                print(f"    TimeUnitOfMacro: {time_unit}")
                print(f"    LengthOfMacroData: {length_of_data} (0x{length_of_data:04x})")
                print(f"    MacroStatusOfUse: 0x{status_of_use:02x} ({status_names.get(status_of_use, '???')})" if status_of_use is not None else "")

                # 提取巨集動作本體 (MacroData[967] = all_payload[56..1022])
                macro_body = all_payload[56:56+967]
                actual_body = macro_body[:length_of_data] if length_of_data > 0 else macro_body
                non_zero_body = sum(1 for b in actual_body if b != 0)

                print(f"\n    巨集動作本體（LengthOfMacroData={length_of_data}, {non_zero_body}B 非 0）:")
                if non_zero_body > 0:
                    print(f"    前 64B: {actual_body[:64].hex(' ')}")
                    actions = decode_macro_data(actual_body)
                    print(f"    解碼動作（{len(actions)} 個）:")
                    for j, (tag, detail) in enumerate(actions):
                        print(f"      {j:3d}. [{tag}] {detail}")
                else:
                    print(f"    （動作本體全 0 或長度為 0）")

    print()
    dev.close()
    print("裝置已關閉。")


if __name__ == "__main__":
    main()