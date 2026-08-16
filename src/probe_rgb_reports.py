#!/usr/bin/env python3
"""唯讀探測 report 6(32B)和 report 7(136B)，確認是否含巨集本體。

目的：report 4/5/8/9/0x0F 都試過了，找不到巨集本體。report 6/7 是
OpenRGB Z15 已還原的 RGB report，理論上不放巨集，但 Z12 的 report 6
只有 32B（Z15 是 792B），結構差很多，值得快速 GET 確認。

安全規則：只開介面 1，只送 GET_FEATURE（send_feature_report 帶全 0
payload 再 GET），送兩次丟棄首次，不送 SET 寫入，不碰介面 0。

用法：
    .venv/bin/python src/probe_rgb_reports.py --run
"""

import hid
import sys

VID = 0x3842
PID = 0x2612
TARGET_INTERFACE = 1
TARGET_USAGE_PAGE = 0x08
TARGET_USAGE = 0x4B

REPORTS_TO_PROBE = [
    (0x06, 32),
    (0x07, 136),
]

E1_MACRO_KEYS = bytes([0x0D, 0x0D, 0x0F, 0x0B, 0x16, 0x12, 0x04, 0x12])
JJL_PREFIX = bytes([0x0D, 0x0D, 0x0F])
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


def search_macro(resp):
    found = []
    for label, pattern in [
        ("E1 完整 (jjlhsiao)", E1_MACRO_KEYS),
        ("jjl 前綴", JJL_PREFIX),
        ("jj 前綴", JJ_PREFIX),
    ]:
        idx = 0
        while True:
            pos = resp.find(pattern, idx)
            if pos == -1:
                break
            found.append((label, pos))
            idx = pos + 1
    return found


def get_report(dev, report_id, size, fail_counts):
    """送全 0 payload 的 send_feature_report 再 GET，送兩次丟棄首次。"""
    def _once():
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

    ok1, r1 = _once()
    if not ok1:
        return False, f"[排空] {r1}"
    ok2, r2 = _once()
    if not ok2:
        return False, f"[讀取] {r2}"
    return True, r2


def main():
    do_run = "--run" in sys.argv

    print(f"=== EVGA Z12 report 6/7 唯讀探測（PID {PID:#06x}）===")
    print(f"目標：介面 {TARGET_INTERFACE}")
    print(f"模式：{'實際送 GET_FEATURE' if do_run else '僅列舉（加 --run 才送）'}")
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

    print(">>> 即將開啟裝置並送 GET_FEATURE <<<")
    print("    【提醒】只開介面 1，不碰介面 0。")
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

    for report_id, size in REPORTS_TO_PROBE:
        print(f"{'='*60}")
        print(f"report 0x{report_id:02x} / {size}B")
        print(f"{'='*60}")

        fail_counts = {"write": 0, "read": 0}
        ok, resp = get_report(dev, report_id, size, fail_counts)
        if not ok:
            print(f"失敗：{resp}")
            print()
            continue

        print(f"回應（{len(resp)}B）：")
        print(hexdump(resp))
        print()

        has_magic = (len(resp) >= 3 and resp[1] == 0xEA and resp[2] == 0x02)
        status = resp[6] if len(resp) > 6 else None
        non_zero = sum(1 for b in resp[8:] if b != 0)
        found = search_macro(resp)

        print(f"EA 02 magic：{'✅' if has_magic else '❌'}")
        print(f"byte[6] = 0x{status:02x}" if status is not None else "回應太短")
        print(f"payload 非 0 byte 數：{non_zero}")
        if found:
            print(f"🎯 找到巨集特徵！")
            for label, pos in found:
                ctx = resp[max(0, pos-4):pos+len(E1_MACRO_KEYS)+4]
                print(f"  {label} @ offset {pos}: ...{ctx.hex(' ')}...")
        else:
            print("未找到巨集特徵。")
        print()

        import time
        time.sleep(0.1)

    dev.close()
    print("裝置已關閉。")


if __name__ == "__main__":
    main()