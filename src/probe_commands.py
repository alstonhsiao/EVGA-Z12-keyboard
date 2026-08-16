#!/usr/bin/env python3
"""唯讀試探 EVGA Z12 report 4 的未知 command，找讀巨集的命令。

目的：report 4 已知 command 0x07（讀寫 keymap）和 0x12（存檔）。
function=0x03 是巨集引用，巨集本體可能在 report 5/8，但需要先用
report 4 帶某個 command 選巨集編號。本腳本掃 command 0x00-0x20，
只送 byte4=01（讀模式），觀察回應結構找新命令。

安全規則（對應 AGENTS.md 規則 1/3）：
- 只開介面 1（interface==1、usage_page==0x08、usage==0x4B）。
- 只送 byte4=01（讀模式），不送 byte4=00（寫模式）。
- 跳過 0x07（已知 keymap 讀寫）和 0x12（存檔，會寫 onboard）。
- 每個 command 用「送兩次、丟棄首次」策略排空過時快取。
- 同一個 command 連失敗兩次就停。不掃 0x21 以上（避免未知危險區）。
- 這仍是 SET_FEATURE transfer（send_feature_report），因為 report 4
  的讀寫都靠 SET 送命令再 GET 讀回應。byte4=01 是協定層的「讀」語意。

用法：
    .venv/bin/python src/probe_commands.py            # 列出要掃的 command 後退出
    .venv/bin/python src/probe_commands.py --run      # 真的送試探
"""

import hid
import sys

VID = 0x3842
PID = 0x2612
TARGET_INTERFACE = 1
TARGET_USAGE_PAGE = 0x08
TARGET_USAGE = 0x4B

REPORT_ID = 0x04
REPORT_SIZE = 17

# 已知 command，掃描時跳過
KNOWN_COMMANDS = {
    0x07: "keymap 讀寫（byte4=01 讀 / 00 寫）",
    0x12: "存檔（會寫 onboard，跳過）",
}

# 掃描範圍：0x00–0x20，跳過已知
SCAN_RANGE = [c for c in range(0x00, 0x21) if c not in KNOWN_COMMANDS]

# 巨集特徵（E1 = jjlhsiao）
E1_MACRO_KEYS = bytes([0x0D, 0x0D, 0x0F, 0x0B, 0x16, 0x12, 0x04, 0x12])
JJL_PREFIX = bytes([0x0D, 0x0D, 0x0F])


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


def try_command(dev, cmd, param, fail_counts):
    """送 report 4 帶指定 command 和 param（byte4=01 讀模式）。

    封包結構：04 EA 02 <cmd> 01 00 00 <param> + 9 bytes 0
    送兩次、丟棄首次、取第二次（排空過時快取）。
    """
    def _once():
        req = bytearray(REPORT_SIZE)
        req[0] = REPORT_ID
        req[1] = 0xEA
        req[2] = 0x02
        req[3] = cmd
        req[4] = 0x01  # 讀模式
        req[5] = 0x00
        req[6] = 0x00
        req[7] = param
        try:
            dev.send_feature_report(bytes(req))
        except OSError as e:
            fail_counts["write"] += 1
            return False, f"send_feature_report 失敗: {e}"
        try:
            resp = dev.get_feature_report(REPORT_ID, REPORT_SIZE)
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

    print(f"=== EVGA Z12 report 4 command 唯讀試探（PID {PID:#06x}）===")
    print(f"目標：介面 {TARGET_INTERFACE}，report 0x{REPORT_ID:02x} / {REPORT_SIZE}B")
    print(f"策略：掃 command 0x00–0x20，byte4=01（讀模式），跳過已知 0x07/0x12")
    print(f"      每個 command 用 param=0x00 試一次，有趣的再換 param 試")
    print(f"模式：{'實際送試探' if do_run else '僅列舉（加 --run 才送封包）'}")
    print()

    print("要掃的 command：")
    for cmd in SCAN_RANGE:
        print(f"  0x{cmd:02x}", end="")
        if (cmd - 0x00 + 1) % 8 == 0:
            print()
    print()
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
    print(f"    【提醒】只開介面 1，byte4=01 讀模式，跳過 0x07/0x12。")
    print(f"    若 3 秒內想中止請 Ctrl-C。")
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

    # 先記住「無反應」的回應樣本：送一個已知無效 command 看 baseline
    # 用 command 0xFF（超出範圍）看鍵盤怎麼回應「不支援」
    fail_counts = {"write": 0, "read": 0}
    print("--- baseline：command 0xFF（預期不支援）---")
    ok, resp = try_command(dev, 0xFF, 0x00, fail_counts)
    if ok:
        print(f"回應：{resp.hex(' ')}")
        baseline_status = resp[6] if len(resp) > 6 else None
        print(f"byte[6] = 0x{baseline_status:02x}" if baseline_status is not None else "回應太短")
        print(f"（後續 byte[6]==0x{baseline_status:02x} 的視為「不支援/無反應」）")
    else:
        print(f"baseline 失敗：{resp}")
        baseline_status = None
    print()

    # 掃描
    interesting = []
    fail_counts = {"write": 0, "read": 0}

    for cmd in SCAN_RANGE:
        ok, resp = try_command(dev, cmd, 0x00, fail_counts)
        if not ok:
            print(f"cmd 0x{cmd:02x} param 0x00 → 失敗：{resp}")
            if fail_counts["read"] >= 2 or fail_counts["write"] >= 2:
                print(f"\n!! 連失敗 2 次，停止。")
                break
            fail_counts = {"write": 0, "read": 0}
            continue

        fail_counts = {"write": 0, "read": 0}

        status = resp[6] if len(resp) > 6 else None
        # 跟 baseline 比，不一樣的才值得看
        is_baseline = (status == baseline_status)
        # 也檢查是否回應了巨集特徵
        has_macro = (E1_MACRO_KEYS in resp or JJL_PREFIX in resp)

        marker = ""
        if has_macro:
            marker = " 🎯 巨集特徵！"
            interesting.append((cmd, 0x00, resp, "巨集特徵"))
        elif not is_baseline:
            marker = " ⭐ 不同於 baseline"
            interesting.append((cmd, 0x00, resp, "不同回應"))

        print(f"cmd 0x{cmd:02x} param 0x00 → {resp.hex(' ')}  byte[6]=0x{status:02x}{marker}")

    print()
    print(f"=== 掃描完成，{len(interesting)} 個有趣的 command ===")
    for cmd, param, resp, reason in interesting:
        print(f"\ncmd 0x{cmd:02x} param 0x{param:02x}（{reason}）：")
        print(hexdump(resp))

    # 對有趣的 command 再用不同 param 試（如果有的話）
    if interesting:
        print()
        print(f"=== 對有趣的 command 換 param 試探 ===")
        for cmd, _, _, reason in interesting:
            if reason == "巨集特徵":
                # 用 E1–E5 的 mod 值（0x03–0x07）當 param 試
                params = [0x03, 0x04, 0x05, 0x06, 0x07]
            else:
                params = [0x01, 0x02, 0x03, 0x04, 0x05]
            for p in params:
                ok, resp = try_command(dev, cmd, p, {"write": 0, "read": 0})
                if ok:
                    status = resp[6] if len(resp) > 6 else None
                    has_macro = (E1_MACRO_KEYS in resp or JJL_PREFIX in resp)
                    marker = " 🎯" if has_macro else ""
                    print(f"cmd 0x{cmd:02x} param 0x{p:02x} → {resp.hex(' ')}  byte[6]=0x{status:02x}{marker}")
                    if has_macro:
                        print(f"  完整回應：")
                        print(hexdump(resp))
                else:
                    print(f"cmd 0x{cmd:02x} param 0x{p:02x} → 失敗：{resp}")

    dev.close()
    print()
    print("裝置已關閉。")


if __name__ == "__main__":
    main()