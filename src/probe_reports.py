#!/usr/bin/env python3
"""唯讀探測 EVGA Z12 的 report 5/8/9/0x0F，找巨集本體存放位置。

目的：report 4 讀到 E-key 的 function=0x03 是 onboard 巨集引用，
巨集本體（鍵碼序列）存在哪個 report 未知。對 report 5/8/9/0x0F 各送
GET_FEATURE，看哪個回傳 EA 02 開頭且包含已知巨集鍵碼。

已知巨集（實證）：E1 = j j l h s i a o
對應 HID 鍵碼：0x0D 0x0D 0x0F 0x0B 0x16 0x12 0x04 0x12

安全規則（對應 AGENTS.md 規則 1/3）：
- 只開介面 1（interface_number == 1）且 usage_page == 0x08 / usage == 0x4B。
- 只送 GET_FEATURE，不送 SET_REPORT。
- 同一個 report ID 的 GET_FEATURE 連失敗兩次就停，不改送 SET，不掃其他 report。

用法：
    .venv/bin/python src/probe_reports.py            # 列出要探測的 report 後退出
    .venv/bin/python src/probe_reports.py --run      # 真的送 GET_FEATURE
"""

import hid
import sys

VID = 0x3842
PID = 0x2612
TARGET_INTERFACE = 1
TARGET_USAGE_PAGE = 0x08
TARGET_USAGE = 0x4B

# 要探測的 report ID 與 descriptor 長度（docs/research.md:63-69）
# 傳送長度 = descriptor count + 1 (report ID byte)
REPORTS_TO_PROBE = [
    (0x05, 265, "265B，Z15 RGB 驅動沒用，可能是 keymap/profile/巨集"),
    (0x08, 265, "265B，Z15 用 1597B report 8 讀目前模式；Z12 可能不同"),
    (0x09, 265, "265B，未知，可能是 keymap / profile / 巨集"),
    (0x0F, 264, "264B，未知"),
]

# E1 巨集鍵碼特徵（jjlhsiao = 0x0D 0x0D 0x0F 0x0B 0x16 0x12 0x04 0x12）
E1_MACRO_KEYS = bytes([0x0D, 0x0D, 0x0F, 0x0B, 0x16, 0x12, 0x04, 0x12])
# 較短的特徵（jjl = 0x0D 0x0D 0x0F）所有巨集開頭都有
JJL_PREFIX = bytes([0x0D, 0x0D, 0x0F])
# jj 開頭（E5 是 jjm，也是 0x0D 0x0D）
JJ_PREFIX = bytes([0x0D, 0x0D])


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


def probe_report(dev, report_id, size, fail_counts):
    """送 GET_FEATURE 讀指定 report。送兩次、丟棄首次、取第二次。

    跟 probe_ekeys.py 一樣的「排空過時快取」策略。
    """
    def _once():
        # send_feature_report 送一個全 0 的 buffer，第一 byte = report ID
        req = bytearray(size)
        req[0] = report_id
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

    # 第一次：排空，丟棄
    ok1, r1 = _once()
    if not ok1:
        return False, f"[排空] {r1}"
    # 第二次：採信
    ok2, r2 = _once()
    if not ok2:
        return False, f"[讀取] {r2}"
    return True, r2


def search_macro(resp):
    """在回應裡搜尋巨集鍵碼特徵。回傳找到的位置列表。"""
    found = []
    # 搜尋 E1 完整特徵
    idx = 0
    while True:
        pos = resp.find(E1_MACRO_KEYS, idx)
        if pos == -1:
            break
        found.append(("E1 完整 (jjlhsiao)", pos))
        idx = pos + 1
    # 搜尋 jjl 前綴
    idx = 0
    while True:
        pos = resp.find(JJL_PREFIX, idx)
        if pos == -1:
            break
        found.append(("jjl 前綴", pos))
        idx = pos + 1
    # 搜尋 jj 前綴
    idx = 0
    while True:
        pos = resp.find(JJ_PREFIX, idx)
        if pos == -1:
            break
        found.append(("jj 前綴", pos))
        idx = pos + 1
    return found


def main():
    do_run = "--run" in sys.argv

    print(f"=== EVGA Z12 report 5/8/9/0x0F 巨集本體探測（PID {PID:#06x}）===")
    print(f"目標：介面 {TARGET_INTERFACE}，usage_page {TARGET_USAGE_PAGE:#04x} / "
          f"usage {TARGET_USAGE:#04x}")
    print(f"搜尋特徵：E1 巨集 jjlhsiao = {E1_MACRO_KEYS.hex(' ')}")
    print(f"         jjl 前綴 = {JJL_PREFIX.hex(' ')}, jj 前綴 = {JJ_PREFIX.hex(' ')}")
    print(f"模式：{'實際送 GET_FEATURE' if do_run else '僅列舉（加 --run 才送封包）'}")
    print()

    print("要探測的 report：")
    for rid, size, desc in REPORTS_TO_PROBE:
        print(f"  report 0x{rid:02x} / {size}B — {desc}")
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
        print(f"執行：{sys.argv[0]} --run")
        return

    print(f">>> 即將開啟裝置並送 GET_FEATURE <<<")
    print(f"    【提醒】只開介面 1（設定通道），不碰介面 0（打字）。")
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

    for report_id, size, desc in REPORTS_TO_PROBE:
        print(f"{'='*60}")
        print(f"探測 report 0x{report_id:02x} / {size}B — {desc}")
        print(f"{'='*60}")

        ok, resp = probe_report(dev, report_id, size, fail_counts)
        if not ok:
            print(f"失敗：{resp}")
            if fail_counts["read"] >= FAIL_LIMIT or fail_counts["write"] >= FAIL_LIMIT:
                print(f"\n!! 連失敗 {FAIL_LIMIT} 次，依 AGENTS.md 規則 1 停止。")
                print(f"   write 失敗：{fail_counts['write']}, read 失敗：{fail_counts['read']}")
                break
            fail_counts = {"write": 0, "read": 0}
            print()
            continue

        # 重置失敗計數
        fail_counts = {"write": 0, "read": 0}

        print(f"回應（{len(resp)}B）：")
        print(hexdump(resp))
        print()

        # 檢查 EA 02 家族
        has_magic = (len(resp) >= 3 and resp[1] == 0xEA and resp[2] == 0x02)
        print(f"EA 02 magic：{'✅ 有' if has_magic else '❌ 無'}")

        # 搜尋巨集特徵
        found = search_macro(resp)
        if found:
            print(f"🎯 找到巨集鍵碼特徵！")
            for label, pos in found:
                ctx = resp[max(0, pos-4):pos+len(E1_MACRO_KEYS)+4]
                print(f"  {label} @ offset {pos}: ...{ctx.hex(' ')}...")
        else:
            print("未找到巨集鍵碼特徵。")
        print()

        import time
        time.sleep(0.1)

    dev.close()
    print("裝置已關閉。")


if __name__ == "__main__":
    main()