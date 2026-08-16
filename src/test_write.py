#!/usr/bin/env python3
"""安全測試 EVGA Z12 的 SET_FEATURE 寫入（report 4 keymap）。

目的：驗證 report 4 的 keymap 寫入流程。選一顆安全的 E-key（E5），
先讀目前值 → 寫成單鍵 F13 → 讀回確認 → 存檔 → 再讀回確認。

安全措施：
- 只改 E5（position 0x66），目前綁巨集 #3，改成 F13 後可改回。
- 先 dump 目前值，保留可還原的 baseline。
- 寫入後讀回確認，確認無誤才存檔。
- 存檔命令 04 EA 02 12 00 00 00 01（存到 profile 1）。

封包結構：
  讀：04 EA 02 07 01 00 00 <pos> + 9B 0  (SubCmd=01=Read)
  寫：04 EA 02 07 00 00 00 <pos> <fn> <p1> <p2> <p3> + 5B 0  (SubCmd=00=Write)
  存檔：04 EA 02 12 00 00 00 <profileNum> + 9B 0

F13 的 HID usage = 0x68，function=0x00（KeyboardEmulation），
Parameter1=0x00（無 modifier），Parameter2=0x68（F13），Parameter3=0x00。

用法：
    .venv/bin/python src/test_write.py --run
"""

import hid
import sys
import time

VID = 0x3842
PID = 0x2612
TARGET_INTERFACE = 1
TARGET_USAGE_PAGE = 0x08
TARGET_USAGE = 0x4B

REPORT_SIZE = 17
HEADER1 = 0xEA
HEADER2 = 0x02
CMD_KEYMAP = 0x07
CMD_SAVE = 0x12
SUB_READ = 0x01
SUB_WRITE = 0x00
RESPONSE_SUCCESS = 0xC0

# E5 = position 0x66
E5_POS = 0x66
# F13 = HID usage 0x68
F13_HID = 0x68
# 存到 profile 1
PROFILE_NUM = 1


def find_device():
    candidates = []
    for d in hid.enumerate(VID, PID):
        if (d["interface_number"] == TARGET_INTERFACE
                and d["usage_page"] == TARGET_USAGE_PAGE
                and d["usage"] == TARGET_USAGE):
            candidates.append(d)
    return candidates


def send_and_read(dev, payload, discard_count=2):
    """送 report 4 並讀回。送 N 次丟棄前 N-1 次。"""
    for attempt in range(discard_count):
        req = bytearray(REPORT_SIZE)
        req[0] = 0x04
        for i, b in enumerate(payload):
            if 1 + i < REPORT_SIZE:
                req[1 + i] = b
        try:
            dev.send_feature_report(bytes(req))
        except OSError as e:
            return False, f"send: {e}"
        try:
            resp = dev.get_feature_report(0x04, REPORT_SIZE)
        except OSError as e:
            return False, f"get: {e}"
        if resp is None or len(resp) == 0:
            return False, "empty"
        time.sleep(0.05)
    return True, bytes(resp)


def read_key(dev, pos):
    """讀取一顆鍵的 KeyDefine。"""
    payload = bytes([
        HEADER1, HEADER2, CMD_KEYMAP, SUB_READ, 0x00, 0x00, pos
    ]) + bytes(9)
    return send_and_read(dev, payload, discard_count=2)


def write_key(dev, pos, fn, p1, p2, p3):
    """寫入一顆鍵的 KeyDefine。"""
    payload = bytes([
        HEADER1, HEADER2, CMD_KEYMAP, SUB_WRITE, 0x00, 0x00, pos,
        fn, p1, p2, p3
    ]) + bytes(5)
    return send_and_read(dev, payload, discard_count=2)


def save_profile(dev, profile_num):
    """存檔到指定 profile。"""
    payload = bytes([
        HEADER1, HEADER2, CMD_SAVE, 0x00, 0x00, 0x00, profile_num
    ]) + bytes(9)
    return send_and_read(dev, payload, discard_count=2)


def decode_keydefine(resp):
    """解碼 KeyDefine。"""
    if len(resp) < 12:
        return "too short"
    fn = resp[8]
    p1 = resp[9]
    p2 = resp[10]
    p3 = resp[11]
    if fn == 0x00:
        return f"KeyboardEmulation: mod=0x{p1:02x} key=0x{p2:02x} key2=0x{p3:02x}"
    elif fn == 0x03:
        return f"Macro: #{p1} runMethod=0x{p2:02x} repeat={p3}"
    elif fn == 0xFF:
        return "Disable"
    else:
        return f"fn=0x{fn:02x} p1=0x{p1:02x} p2=0x{p2:02x} p3=0x{p3:02x}"


def main():
    do_run = "--run" in sys.argv

    print("=== EVGA Z12 SET_FEATURE 寫入測試（E5 → F13）===")
    print(f"模式：{'實際執行' if do_run else '僅列舉（加 --run）'}")
    print()

    candidates = find_device()
    if not candidates:
        print("找不到裝置。")
        sys.exit(1)

    if not do_run:
        print("將執行：讀 E5 → 寫 F13 → 讀回確認 → 存檔 → 讀回確認")
        print("E5 目前綁巨集 #3，會改成 F13 單鍵。可記錄原值再改回。")
        return

    print(">>> 開啟裝置 <<<")
    print("    【提醒】這會改變 E5 的設定（巨集#3 → F13），存檔後持久化。")
    print("    請停止使用 keyboard。")
    time.sleep(3)

    try:
        dev = hid.Device(path=candidates[0]["path"])
    except OSError as e:
        print(f"開裝置失敗：{e}")
        sys.exit(2)

    print(f"裝置已開：{dev.product!r}")
    print()

    # Step 1: 讀目前 E5 的值（baseline）
    print("=" * 50)
    print("Step 1: 讀取 E5 目前值（baseline）")
    print("=" * 50)
    ok, resp = read_key(dev, E5_POS)
    if not ok:
        print(f"失敗：{resp}")
        dev.close()
        sys.exit(1)

    status = resp[6]
    print(f"  status=0x{status:02x} ({'✅' if status==0xC0 else '❌'})")
    print(f"  raw: {resp.hex(' ')}")
    baseline_fn = resp[8]
    baseline_p1 = resp[9]
    baseline_p2 = resp[10]
    baseline_p3 = resp[11]
    print(f"  解碼: {decode_keydefine(resp)}")
    print(f"  Baseline 保留: fn=0x{baseline_fn:02x} p1=0x{baseline_p1:02x} p2=0x{baseline_p2:02x} p3=0x{baseline_p3:02x}")
    print()

    if status != 0xC0:
        print("讀取失敗，不繼續寫入。")
        dev.close()
        sys.exit(1)

    # Step 2: 寫入 F13
    print("=" * 50)
    print("Step 2: 寫入 E5 = F13 (function=0x00, key=0x68)")
    print("=" * 50)
    ok, resp = write_key(dev, E5_POS, 0x00, 0x00, F13_HID, 0x00)
    if not ok:
        print(f"失敗：{resp}")
        dev.close()
        sys.exit(1)

    status = resp[6]
    print(f"  寫入回應: status=0x{status:02x} ({'✅' if status==0xC0 else '❌'})")
    print(f"  raw: {resp.hex(' ')}")
    print()

    # Step 3: 讀回確認
    print("=" * 50)
    print("Step 3: 讀回確認")
    print("=" * 50)
    ok, resp = read_key(dev, E5_POS)
    if not ok:
        print(f"失敗：{resp}")
        dev.close()
        sys.exit(1)

    status = resp[6]
    fn = resp[8]
    p1 = resp[9]
    p2 = resp[10]
    p3 = resp[11]
    print(f"  status=0x{status:02x} ({'✅' if status==0xC0 else '❌'})")
    print(f"  解碼: {decode_keydefine(resp)}")

    write_ok = (fn == 0x00 and p2 == F13_HID)
    print(f"  寫入成功：{'✅ E5 現在是 F13' if write_ok else '❌ 讀回值不符'}")
    print()

    if not write_ok:
        print("寫入未確認，不存檔。")
        dev.close()
        sys.exit(1)

    # Step 4: 存檔
    print("=" * 50)
    print(f"Step 4: 存檔到 profile {PROFILE_NUM}")
    print("=" * 50)
    ok, resp = save_profile(dev, PROFILE_NUM)
    if not ok:
        print(f"失敗：{resp}")
        dev.close()
        sys.exit(1)

    status = resp[6]
    print(f"  存檔回應: status=0x{status:02x} ({'✅' if status==0xC0 else '❌'})")
    print(f"  raw: {resp.hex(' ')}")
    print()

    # Step 5: 存檔後再讀回確認
    print("=" * 50)
    print("Step 5: 存檔後再讀回確認")
    print("=" * 50)
    time.sleep(0.5)  # 存檔後等一下
    ok, resp = read_key(dev, E5_POS)
    if not ok:
        print(f"失敗：{resp}")
        dev.close()
        sys.exit(1)

    status = resp[6]
    fn = resp[8]
    p2 = resp[10]
    print(f"  status=0x{status:02x} ({'✅' if status==0xC0 else '❌'})")
    print(f"  解碼: {decode_keydefine(resp)}")
    persisted = (fn == 0x00 and p2 == F13_HID)
    print(f"  持久化確認：{'✅ 存檔後仍是 F13' if persisted else '❌ 存檔後值變了'}")
    print()

    # Step 6: 還原原值
    print("=" * 50)
    print("Step 6: 還原 E5 原值")
    print("=" * 50)
    ok, resp = write_key(dev, E5_POS, baseline_fn, baseline_p1, baseline_p2, baseline_p3)
    if not ok:
        print(f"還原失敗：{resp}")
    else:
        status = resp[6]
        print(f"  還原寫入: status=0x{status:02x}")

    ok, resp = save_profile(dev, PROFILE_NUM)
    if not ok:
        print(f"還原存檔失敗：{resp}")
    else:
        status = resp[6]
        print(f"  還原存檔: status=0x{status:02x}")

    # 讀回確認還原
    ok, resp = read_key(dev, E5_POS)
    if ok:
        print(f"  還原確認: {decode_keydefine(resp)}")
    print()

    dev.close()
    print("裝置已關閉。")
    print()
    print("=== 總結 ===")
    print(f"  寫入 F13：{'✅' if write_ok else '❌'}")
    print(f"  存檔持久化：{'✅' if persisted else '❌'}")


if __name__ == "__main__":
    main()