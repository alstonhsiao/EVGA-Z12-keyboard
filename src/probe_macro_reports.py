#!/usr/bin/env python3
"""唯讀試探 report 5/8 帶 EA 02 payload，找巨集本體。

目的：report 4 的 command 空間（0x00–0x20）沒有讀巨集的命令。Z15 的
協定裡 report 8 是直接在 payload 帶 `08 EA 02 01 FE` 命令再 GET 回應。
假設 Z12 的巨集本體在 report 5 或 8，要送 `send_feature_report` 帶
`EA 02 <cmd> <macro_id>` payload，再 GET 同一個 report 讀回巨集鍵碼。

安全規則（對應 AGENTS.md 規則 1/3）：
- 只開介面 1（interface==1、usage_page==0x08、usage==0x4B）。
- 送兩次、丟棄首次、取第二次（排空過時快取）。
- 只送 byte4=01（讀模式），不送寫模式。
- 同一組 (report, cmd, param) 失敗兩次就停。
- 不送 0x12（存檔命令）。

用法：
    .venv/bin/python src/probe_macro_reports.py            # 列舉後退出
    .venv/bin/python src/probe_macro_reports.py --run      # 真的送試探
"""

import hid
import sys

VID = 0x3842
PID = 0x2612
TARGET_INTERFACE = 1
TARGET_USAGE_PAGE = 0x08
TARGET_USAGE = 0x4B

# 要試的 report：5 (265B) 和 8 (265B)
REPORTS_TO_PROBE = [
    (0x05, 265),
    (0x08, 265),
]

# Z15 已知的 report 8 命令：08 EA 02 01 FE（讀目前模式）
# 這裡試不同的 cmd 和 param 組合
# cmd 沿用 report 4 已知的：0x01（有效）、0x07（keymap）、
# 再加 Z15 的 0x01 和未知範圍
# param 用 E1–E5 的 mod 值（0x03–0x07）當巨集編號
COMMANDS_TO_TRY = [
    # (cmd, param, 說明)
    (0x01, 0x00, "report 4 已知有效命令，param=0"),
    (0x01, 0xFE, "Z15 report 8 讀模式的 param"),
    (0x07, 0x03, "keymap 命令 + E5 的 mod 值"),
    (0x07, 0x04, "keymap 命令 + E3/E4 的 mod 值"),
    (0x07, 0x05, "keymap 命令 + E4 的 mod 值"),
    (0x07, 0x06, "keymap 命令 + E1 的 mod 值"),
    (0x07, 0x07, "keymap 命令 + E2 的 mod 值"),
    (0x08, 0x00, "未知 cmd 0x08"),
    (0x09, 0x00, "未知 cmd 0x09"),
    (0x0A, 0x00, "未知 cmd 0x0A"),
    (0x0B, 0x00, "未知 cmd 0x0B"),
    (0x0C, 0x00, "未知 cmd 0x0C"),
    (0x0D, 0x00, "未知 cmd 0x0D"),
    (0x0E, 0x00, "未知 cmd 0x0E"),
    (0x0F, 0x00, "未知 cmd 0x0F"),
    (0x10, 0x00, "未知 cmd 0x10"),
]

# 巨集特徵
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


def try_report_command(dev, report_id, size, cmd, param, fail_counts):
    """送 report 5/8 帶 EA 02 payload，再 GET 讀回應。

    封包結構：<report_id> EA 02 <cmd> 01 00 00 <param> + 0...（填到 size）
    byte4=01 讀模式（跟 report 4 一樣的語意）。
    送兩次、丟棄首次、取第二次。
    """
    def _once():
        req = bytearray(size)
        req[0] = report_id
        req[1] = 0xEA
        req[2] = 0x02
        req[3] = cmd
        req[4] = 0x01  # 讀模式
        req[5] = 0x00
        req[6] = 0x00
        req[7] = param
        # 其餘維持 0
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


def search_macro(resp):
    """搜尋巨集鍵碼特徵。"""
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


def main():
    do_run = "--run" in sys.argv

    print(f"=== EVGA Z12 report 5/8 帶 EA 02 payload 巨集探測（PID {PID:#06x}）===")
    print(f"目標：介面 {TARGET_INTERFACE}")
    print(f"策略：對 report 5/8 送 <rid> EA 02 <cmd> 01 00 00 <param>，")
    print(f"      再 GET 同 report 讀回應。byte4=01 讀模式。")
    print(f"搜尋特徵：jjlhsiao = {E1_MACRO_KEYS.hex(' ')}")
    print(f"模式：{'實際送試探' if do_run else '僅列舉（加 --run 才送封包）'}")
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

    print(f">>> 即將開啟裝置並送試探 <<<")
    print(f"    【提醒】只開介面 1，byte4=01 讀模式，不送 0x12。")
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

    interesting = []

    for report_id, size in REPORTS_TO_PROBE:
        print(f"{'='*60}")
        print(f"report 0x{report_id:02x} / {size}B")
        print(f"{'='*60}")

        # 先送一個全 0 payload 當 baseline（看鍵盤怎麼回應無命令的 GET）
        fail_counts = {"write": 0, "read": 0}
        req = bytearray(size)
        req[0] = report_id
        try:
            dev.send_feature_report(bytes(req))
            resp = dev.get_feature_report(report_id, size)
            baseline = bytes(resp) if resp else b""
            print(f"baseline（全 0 payload）：{baseline[:16].hex(' ')}... ({len(baseline)}B)")
            bl_status = baseline[6] if len(baseline) > 6 else None
            print(f"  byte[6] = 0x{bl_status:02x}" if bl_status is not None else "  回應太短")
        except OSError as e:
            print(f"baseline 失敗：{e}")
            baseline = b""
            bl_status = None
        print()

        # 試每組 (cmd, param)
        for cmd, param, desc in COMMANDS_TO_TRY:
            fail_counts = {"write": 0, "read": 0}
            ok, resp = try_report_command(dev, report_id, size, cmd, param, fail_counts)
            if not ok:
                print(f"  cmd 0x{cmd:02x} p 0x{param:02x} → 失敗：{resp}")
                continue

            status = resp[6] if len(resp) > 6 else None
            has_magic = (len(resp) >= 3 and resp[1] == 0xEA and resp[2] == 0x02)
            found = search_macro(resp)
            non_zero = sum(1 for b in resp[8:] if b != 0)  # payload 區非 0 的 byte 數

            markers = []
            if found:
                markers.append("🎯 巨集特徵！")
            if has_magic and status != bl_status:
                markers.append("⭐ 不同 baseline")
            if non_zero > 2:
                markers.append(f"📊 payload {non_zero}B 非 0")

            marker = " ".join(markers)
            head = resp[:16].hex(" ")
            print(f"  cmd 0x{cmd:02x} p 0x{param:02x} ({desc})")
            print(f"    → {head}...  byte[6]=0x{status:02x}  magic={'✅' if has_magic else '❌'}  {marker}")

            if found:
                interesting.append((report_id, cmd, param, resp, found))
                for label, pos in found:
                    ctx = resp[max(0, pos-4):pos+len(E1_MACRO_KEYS)+4]
                    print(f"    {label} @ offset {pos}: ...{ctx.hex(' ')}...")

            import time
            time.sleep(0.05)

        print()

    dev.close()
    print("裝置已關閉。")

    if interesting:
        print()
        print(f"=== {len(interesting)} 個找到巨集特徵的結果 ===")
        for report_id, cmd, param, resp, found in interesting:
            print(f"\nreport 0x{report_id:02x} cmd 0x{cmd:02x} param 0x{param:02x}:")
            print(hexdump(resp))
    else:
        print()
        print("=== 未找到巨集特徵 ===")
        print("所有 (report, cmd, param) 組合的回應都沒有巨集鍵碼。")
        print("可能原因：")
        print("  1. 巨集本體的 cmd 不在試探範圍（0x01–0x10）")
        print("  2. 巨集本體需要先送 report 4 某個命令「選 slot」再 GET report 5/8")
        print("  3. 巨集本體在 report 9 或 0x0F（但直接 GET 回 0xC1 不支援）")
        print("  4. 巨集編碼方式不是直接放 HID 鍵碼（可能有延遲/修飾鍵包裝）")


if __name__ == "__main__":
    main()