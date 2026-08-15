# EVGA Z12 鍵盤設定工具

在 macOS（以及之後的 Linux）上設定 [EVGA Z12 RGB Gaming Keyboard](https://www.evga.com/products/product.aspx?pn=834-W0-12US-KR)，不依賴官方 Windows 軟體 **EVGA Unleash RGB**。

官方沒有 macOS / Linux 版。鍵盤插上 Mac 就能打字，但左邊五顆巨集鍵、全鍵重映射、五區 RGB、onboard 設定檔都改不了。這個專案要自己做那個設定程式。

## 結論：可以自己做

2026-08-15 已在本機接上實機確認：

| 問題 | 答案 |
|------|------|
| Mac 能不能當鍵盤用？ | 能。標準 USB HID，系統已辨識為 `EVGA Z12 Gaming Keyboard`。 |
| 有沒有現成開源設定工具？ | **沒有完整的。** [OpenRGB](https://openrgb.org/) 只做了 Z15/Z20 的 **RGB**，Z12 的 issue [#2670](https://gitlab.com/CalcProgrammer1/OpenRGB/-/issues/2670) 從 2022 開到現在，缺 USB capture。沒有人做過按鍵映射。 |
| 設定是不是寫在鍵盤裡？ | 是。Unleash 宣稱最多 **9 組 onboard profile**，換電腦不用重設。 |
| 協定從哪來？ | HID feature report。Vendor collection 是 Usage Page `0x08` / Usage `0x4B`，跟 OpenRGB 偵測 Z15/Z20 的用法相同。 |
| 我們能不能寫程式？ | **能。** RGB 幾乎可以從 OpenRGB 的 Z15 驅動改長度移植。按鍵映射 / 巨集需要在 Windows 上對 Unleash 做 USB sniff，或先做只讀探測。 |

詳細擷取與封包假設見 [`docs/research.md`](docs/research.md)。開發約束見 [`AGENTS.md`](AGENTS.md)。

## 這把鍵盤能改什麼

EVGA Unleash RGB（Windows）提供的能力，也就是本專案想覆蓋的範圍：

- 左側 5 顆可程式巨集鍵（含 Game Mode / `E` 鍵）
- 幾乎所有按鍵可重映射，另有一層 Shift 層
- 巨集編輯器
- 五區 RGB（不是單鍵 RGB），16.7M 色
- 最多 9 組存在鍵盤裡的設定檔
- 輪詢率（出廠預設 1000 Hz）
- 韌體更新（**本專案不做**，風險太高）

Z12 是薄膜鍵盤，不是機械、不能換軸，也沒有 Z20 的 TOF 感測器。

## 硬體識別

本機實測：

```
VID:PID     3842:2612
名稱        EVGA Z12 Gaming Keyboard
bcdDevice   0xA01D
USB         2.0 Full Speed (12 Mb/s), 500 mA
```

同一家族、OpenRGB 已支援 RGB 的型號：

| 型號 | PID |
|------|-----|
| Z15 ANSI | `3842:2608` |
| Z15 ISO  | `3842:260E` |
| Z20 ANSI | `3842:260A` |
| Z20 UK   | `3842:2610` |
| **Z12**  | **`3842:2612`**（尚未被 OpenRGB 收錄） |

## 現況

這個目錄現在只有文件。還沒有 CLI、還沒送過任何設定封包。

下一步（需你同意後才做）：

1. **只讀探測** — 對介面 1 的 feature report 4/6/7 做 GET，確認是不是 `EA 02` 家族，不寫入。
2. **Windows USB sniff** — 在有 Unleash 的 Windows（實體機或 USB 直通的 VM）上，用 USBPcap + Wireshark 各改一次：一顆鍵、一個 RGB 區、一個 profile。這是還原映射協定最快的路。
3. **先做 RGB CLI** — 風險最低、可對照 OpenRGB 原始碼。
4. **再做映射 / 巨集 / profile**。

macOS 開 HID 裝置需要「系統設定 → 隱私權與安全性 → 輸入監控」授權。探測時只開 vendor 介面，避免鍵盤暫時沒反應。

## 為什麼不直接用 OpenRGB

OpenRGB 只控制燈。Z12 甚至還沒進支援清單。本專案要的是 **RatSlap 那類東西**：映射、巨集、profile，順便把燈一起做。RGB 做穩之後，可以把 Z12 的燈控回饋給 OpenRGB。

## 授權

尚未選定。若大量引用 OpenRGB 的 Z15 控制器，那邊是 **GPL-2.0-or-later**，衍生的協定實作需要相容。
