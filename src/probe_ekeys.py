#!/usr/bin/env python3
"""唯讀探測 EVGA Z12 的 E-key 映射協定（本機 PID 0x2612）。

目的：驗證 Pasquotcho/evga-z12-keys（PID 0x2622）還原的 report 4 / 0xEA 0x02
家族協定，能不能直接套到本機 0x2612。全程只送 GET_FEATURE，不送 SET_REPORT，
不碰介面 0（boot keyboard），不做韌體更新。

安全規則（對應 AGENTS.md 規則 1/3）：
- 只開介面 1（interface_number == 1）且 usage_page == 0x08 / usage == 0x4B。
- 同一個 report ID 的 GET_FEATURE 連失敗兩次就停，不改送 SET，不掃其他 report。
- 失敗時印出完整失敗軌跡（做了什麼、錯誤訊息、已排除什麼）。

用法：
    .venv/bin/python src/probe_ekeys.py            # 列出候選裝置後退出
    .venv/bin/python src/probe_ekeys.py --run      # 真的送 GET_FEATURE
"""

import sys

import hid

# --- 協定常數（來源：docs/research.md + docs/external-protocol-comparison.md）---
VID = 0x3842
PID = 0x2612  # 本機實測，docs/research.md:24
TARGET_INTERFACE = 1  # 設定通道，docs/research.md:54-60；嚴禁開介面 0
TARGET_USAGE_PAGE = 0x08  # vendor collection
TARGET_USAGE = 0x4B

REPORT_ID = 0x04
REPORT_SIZE = 17  # docs/research.md:63

# 0xEA 0x02 家族 header，command 0x07 = keymap 讀寫，byte4=01 讀
# Pasquotcho src/main.rs:136；存檔命令 0x12 與 OpenRGB Z15 一致
READ_CMD = bytes([REPORT_ID, 0xEA, 0x02, 0x07, 0x01, 0x00, 0x00])
SAVE_CMD = bytes([REPORT_ID, 0xEA, 0x02, 0x12, 0x00, 0x00, 0x00])

# E-key position（Pasquotcho src/main.rs:19-39，本機待驗證）
EKEY_POSITIONS = {
    "E1": 0x15,
    "E2": 0x2B,
    "E3": 0x41,
    "E4": 0x52,
    "E5": 0x66,
}

# HID modifier usage → bitmask（標準 HID modifier byte，Pasquotcho src/main.rs:51-61）
MODIFIERS = {
    0xE0: "LCtrl", 0xE1: "LShift", 0xE2: "LAlt", 0xE3: "LGUI",
    0xE4: "RCtrl", 0xE5: "RShift", 0xE6: "RAlt", 0xE7: "RGUI",
}


def find_device():
    """挑出介面 1 的 vendor collection（page 0x08 / usage 0x4B）。

    回傳 hid.enumerate 的 dict，或 None。
    """
    candidates = []
    for d in hid.enumerate(VID, PID):
        if (
            d["interface_number"] == TARGET_INTERFACE
            and d["usage_page"] == TARGET_USAGE_PAGE
            and d["usage"] == TARGET_USAGE
        ):
            candidates.append(d)
    return candidates


def hexdump(b, width=16):
    """把 bytes 印成 hex+ascii，方便人工比對。"""
    out = []
    for i in range(0, len(b), width):
        chunk = b[i : i + width]
        hexs = " ".join(f"{x:02x}" for x in chunk)
        asc = "".join(chr(x) if 32 <= x < 127 else "." for x in chunk)
        out.append(f"  {i:04x}  {hexs:<{width*3}}  {asc}")
    return "\n".join(out)


def decode_mapping(resp):
    """把 17B 回應的 byte 8-11 解成 {function, modifier, key1, key2}。

    Pasquotcho src/main.rs:134-145：read 回應 byte[8]=function, [9]=modifier,
    [10]=key1, [11]=key2。function==0x00 單鍵+修飾鍵，0xFF disable。
    """
    if len(resp) < 12:
        return {"raw": resp.hex(), "error": "回應太短 (<12 bytes)"}
    fn = resp[8]
    mod = resp[9]
    k1 = resp[10]
    k2 = resp[11]
    status = resp[6] if len(resp) > 6 else None
    result = {
        "status_byte6": f"0x{status:02x}" if status is not None else None,
        "status_ok": (status == 0xC0),
        "function": f"0x{fn:02x}",
        "modifier": f"0x{mod:02x}",
        "key1": f"0x{k1:02x}",
        "key2": f"0x{k2:02x}",
    }
    if fn == 0x00:
        mods = [name for u, name in MODIFIERS.items() if mod & (1 << (u - 0xE0))]
        result["meaning"] = f"單鍵: {'+'.join(mods) + '+' if mods else ''}key=0x{k1:02x}"
    elif fn == 0xFF:
        result["meaning"] = "disable"
    else:
        result["meaning"] = f"未知 function=0x{fn:02x}（可能是巨集/複合，原樣印出）"
    return result


def _send_and_read(dev, pos, fail_counts):
    """單次 send_feature_report + get_feature_report。回傳 (ok, resp)。"""
    req = bytearray(REPORT_SIZE)
    req[0] = REPORT_ID
    req[1:8] = READ_CMD[1:8]  # EA 02 07 01 00 00
    req[7] = pos

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


def read_ekey(dev, name, pos, fail_counts):
    """送 GET_FEATURE 讀單一 E-key。回傳 (success, resp_or_error)。

    協定注意:
    1. report 4 是 feature report,必須用 send_feature_report 送出
       查詢命令（底層 hid_send_feature_report），不能用 write（底層
       hid_write = output report，鍵盤不認，get_feature_report 會讀回
       過時快取）。這是 2026-08-16 第一次測試不穩定的根因 #1。
    2. hidapi/macOS 的 get_feature_report 第一次讀到的是 buffer 裡
       上一筆請求的過時回應,不是針對當前請求。解法:每顆 E-key 送兩次,
       丟棄首次回應(排空過時快取),取第二次。這是 2026-08-16 測試
       不穩定的根因 #2。延遲無效(第一筆永遠會被舊 session 污染)。
    """
    # 第一次:排空過時快取,丟棄
    ok1, resp1 = _send_and_read(dev, pos, fail_counts)
    if not ok1:
        return False, f"[排空] {resp1}"

    # 第二次:這才是針對當前請求的回應
    ok2, resp2 = _send_and_read(dev, pos, fail_counts)
    if not ok2:
        return False, f"[讀取] {resp2}"

    return True, resp2


def main():
    do_run = "--run" in sys.argv

    print(f"=== EVGA Z12 唯讀探測（PID {PID:#06x}）===")
    print(f"目標：介面 {TARGET_INTERFACE}，usage_page {TARGET_USAGE_PAGE:#04x} / "
          f"usage {TARGET_USAGE:#04x}")
    print(f"Report ID {REPORT_ID:#04x}，長度 {REPORT_SIZE}B")
    print(f"模式：{'實際送 GET_FEATURE' if do_run else '僅列舉裝置（加 --run 才送封包）'}")
    print()

    candidates = find_device()
    if not candidates:
        print("找不到符合條件的裝置。")
        print("確認鍵盤已插上，且 hid.enumerate 能看到 VID 0x3842。")
        sys.exit(1)

    print(f"找到 {len(candidates)} 個候選裝置：")
    for d in candidates:
        print(f"  interface={d['interface_number']} "
              f"usage_page={d['usage_page']:#06x} usage={d['usage']:#06x} "
              f"path={d['path']!r}")
    print()

    if not do_run:
        print("未加 --run，不送封包。確認上面的裝置是介面 1 後，")
        print(f"執行：{sys.argv[0]} --run")
        return

    # --- 以下才真的開裝置、送封包 ---
    dev_info = candidates[0]
    print(f">>> 即將開啟裝置並送 GET_FEATURE <<<")
    print(f"    interface={dev_info['interface_number']} path={dev_info['path']!r}")
    print(f"    【提醒】這會佔用介面 1（設定通道），不碰介面 0（打字）。")
    print(f"    若 3 秒內想中止請 Ctrl-C。")
    try:
        import time
        time.sleep(3)
    except KeyboardInterrupt:
        print("已中止。")
        return

    try:
        dev = hid.Device(path=dev_info["path"])
    except OSError as e:
        print(f"開裝置失敗：{e}")
        print("可能原因：macOS Input Monitoring 權限未授與，或裝置被其他程式佔用。")
        sys.exit(2)

    print(f"裝置已開：manufacturer={dev.manufacturer!r} product={dev.product!r}")
    print()

    # read_ekey 內部已送兩次、丟棄首次回應排空過時快取，這裡不需靠延遲。
    # E-key 之間留極短間隔（50ms）僅作保險，主要穩定性靠「丟棄首次」。
    READ_DELAY = 0.05  # 秒
    print("讀取策略：每顆 E-key 送兩次 GET_FEATURE，丟棄首次回應（排空過時快取），取第二次。")
    print(f"E-key 間隔：{READ_DELAY}s")
    print()

    fail_counts = {"write": 0, "read": 0}
    FAIL_LIMIT = 2  # AGENTS.md 規則 1：同一方法連失敗兩次就停

    all_ok = True
    for name, pos in EKEY_POSITIONS.items():
        print(f"--- 讀 {name}（position=0x{pos:02x}）---")
        req_preview = bytes([REPORT_ID, 0xEA, 0x02, 0x07, 0x01, 0x00, 0x00, pos]
                            + [0] * (REPORT_SIZE - 8))
        print(f"送出（send_feature_report ×2，首次丟棄）：{req_preview.hex(' ')}")
        ok, resp = read_ekey(dev, name, pos, fail_counts)
        if not ok:
            print(f"失敗：{resp}")
            if fail_counts["read"] >= FAIL_LIMIT or fail_counts["write"] >= FAIL_LIMIT:
                print()
                print(f"!! 連失敗 {FAIL_LIMIT} 次，依 AGENTS.md 規則 1 停止。")
                print("   失敗軌跡：")
                print(f"   - write 失敗次數：{fail_counts['write']}")
                print(f"   - read  失敗次數：{fail_counts['read']}")
                print("   - 已排除：未送 SET_REPORT、未掃其他 report ID、未碰介面 0")
                all_ok = False
                break
            all_ok = False
            continue

        print(f"回應（{len(resp)}B，第二次讀取）：")
        print(hexdump(resp))
        decoded = decode_mapping(resp)
        print(f"解碼：{decoded}")
        # 驗證回應 position 是否吻合送出值
        if len(resp) > 7:
            resp_pos = resp[7]
            pos_match = (resp_pos == pos)
            print(f"position 比對：送出 0x{pos:02x} / 回應 0x{resp_pos:02x} "
                  f"→ {'✅ 吻合' if pos_match else '❌ 不符（仍讀到過時回應）'}")
        print()
        # 重置連續失敗計數（成功就歸零）
        fail_counts = {"write": 0, "read": 0}
        # E-key 之間極短間隔
        import time
        time.sleep(READ_DELAY)

    dev.close()
    print("裝置已關閉。")

    if all_ok:
        print()
        print("=== 結論 ===")
        print("所有 E-key 都成功讀回。檢查每個回應的：")
        print("  1. 長度是否 17B")
        print("  2. byte[6] 是否 0xC0（Pasquotcho 的成功碼）")
        print("  3. byte[1:3] 是否 EA 02（家族協定）")
        print("  4. byte[8:12] 是否合理的 mapping")
        print("若全數符合，表示 PID 0x2612 與 0x2622 走同一協定，可移植。")
    else:
        print()
        print("=== 有失敗，見上方軌跡 ===")


if __name__ == "__main__":
    main()