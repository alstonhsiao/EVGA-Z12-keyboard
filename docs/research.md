# EVGA Z12 研究筆記（2026-08-15）

實機接在這台 Mac 上擷取。目的：判斷能不能自幹設定工具，以及協定從哪裡著手。

## 來源

| 來源 | 用處 |
|------|------|
| 本機 `ioreg` / `hidutil` | VID/PID、三個 HID 介面、完整 Report Descriptor |
| [OpenRGB EVGAKeyboardController](https://github.com/CalcProgrammer1/OpenRGB/tree/master/Controllers/EVGAUSBController/EVGAKeyboardController) | 已還原的 Z15/Z20 RGB 協定 |
| [OpenRGB #2670 Z12](https://gitlab.com/CalcProgrammer1/OpenRGB/-/issues/2670) | 確認 Z12 為 `3842:2612`，缺 capture，仍未合併 |
| [OpenRGB #1909 Z15](https://gitlab.com/CalcProgrammer1/OpenRGB/-/issues/1909) | Z15/Z20 RGB 已做完並關閉 |
| [TechPowerUp Z12 軟體篇](https://www.techpowerup.com/review/evga-z12-rgb-gaming-keyboard/4.html) | Unleash 功能：9 profile、五區 RGB、全鍵映射 + Shift 層、巨集 |
| [RTINGS Z12](https://www.rtings.com/keyboard/reviews/evga/z12) | 全鍵可程式、五區而非單鍵 RGB |
| [官方產品頁](https://www.evga.com/products/product.aspx?pn=834-W0-12US-KR) | 料號 `834-W0-12US-KR` |
| [官方 Unleash](https://www.evga.com/unleash/) | Windows only；EVGA 周邊軟體已近停更 |

## 本機裝置

```
Product          Z12 Gaming Keyboard
Manufacturer     EVGA
idVendor         0x3842 (14402)
idProduct        0x2612 (9746)
bcdDevice        0xA01D (40989)
bcdUSB           0x0200
Device Speed     Full Speed 12 Mb/s
MaxPower         500 mA
iSerialNumber    0
bNumConfigurations 1
ReportInterval   1000 µs  → 1000 Hz
```

`hidutil list` 看到三組 HID device，都是 `0x3842 0x2612`。

## 三個 HID 介面

### 介面 0 — Boot keyboard（不要占用）

- `bInterfaceSubClass = 1`, `bInterfaceProtocol = 1`, BootProtocol = keyboard
- MaxInput 8 / MaxOutput 1 / MaxFeature 16
- 標準 boot keyboard：8 個 modifier bit、6 鍵陣列、Num/Caps/Scroll LED
- 額外：Usage Page `0xFF00` Usage `0x80` 的 **16-byte Feature**（無 Report ID）

Report Descriptor（81 bytes）：

```
05010906a101050719e029e715002501750195088102950175088101
050819012903950375019102950175059101
050719002aff00150026ff00750895068100
0600ff098075089510150026ff00b102
c0
```

### 介面 1 — 設定通道（Mouse + Consumer + System + vendor 0x08/0x4B）

- Usage pairs：`(1,2)` Mouse、`(1,1)` Pointer、`(0x0C,1)` Consumer、`(1,0x80)` System Control、**`(0x08,0x4B)`**
- MaxInput 10 / MaxOutput 1 / **MaxFeature 265**
- OpenRGB 偵測 Z15/Z20 用的就是 `page 0x08 / usage 0x4B`

Feature report（含 1-byte Report ID）：

| Report ID | Descriptor count | 傳送長度 | OpenRGB Z15 對應 |
|-----------|------------------|----------|------------------|
| `0x04` | 16 | **17** | 17 — Save / NFI / 短命令 |
| `0x05` | 264 | 265 | （Z15 RGB 驅動沒用） |
| `0x06` | 31 | **32** | Z15 是 **792**（單鍵 RGB）。Z12 五區，32 bytes 合理 |
| `0x07` | 135 | **136** | 136 — 模式 / 顏色 / 睡眠 |
| `0x08` | 264 | 265 | Z15 用 1597-byte report 8 讀目前模式 |
| `0x09` | 264 | 265 | 未知，可能是 keymap / profile |
| `0x0A` | 58 | 59 | 未知 |
| `0x0F` | 263 | 264 | 未知 |

其它 Report ID：

| ID | 用途 |
|----|------|
| `0x01` | 滑鼠輸入（8 鍵 + 滾輪 + X/Y）+ 16-byte vendor feature |
| `0x02` | Consumer Control（媒體鍵） |
| `0x03` | 6-byte dummy input |
| `0x12` | System Power/Sleep/Wake |

Report Descriptor（236 bytes）：

```
05010902a10185010901a10005091901290815002501950875018102
0600ff0940950275081581257f8106050109381581257f750895018106
05010930093116008026ff7f751095028106
050c0a3802750895011581257f8106
0600ff098075089510150026ff00b102
c0c0
050c0901a101850219002a9c021500269c02950175108100c0
05010980a1018512198129831500250175019503810695058103c0
0508094ba101
85031500250019002900750895068101
85049510b101
8505960801b101
8506961f00b101
85079587b101
8508960801b101
8509960801b101
850a953ab101
850f960701b101
c0
```

### 介面 2 — NKRO keyboard

- Usage pairs：`(1,6)` Keyboard + `(0x08,0x4B)`
- MaxInput 13 / MaxFeature 1
- Report ID `0x10`：modifier + reserved + 10-key 陣列
- Report ID `0x11`：6-byte dummy（0x08/0x4B）
- 幾乎沒有設定用 feature

## OpenRGB Z15/Z20 協定摘要（RGB only）

共同 header：`[report_id, 0xEA, 0x02, command, ...]`

| 動作 | Report | 開頭 |
|------|--------|------|
| Save | 4 / 17B | `04 EA 02 12` |
| NFI #1 | 4 / 17B | `04 EA 02 33 ... 01` |
| NFI #2 | 4 / 17B | `04 EA 02 06 01` |
| HW modes init | 6 / 792B | `06 EA 02` |
| Direct LEDs | 6 / 792B | `06 EA 02 01`，之後每鍵 4 bytes（亮度 RGB） |
| Mode / colour | 7 / 136B | `07 EA 02 0C ...` |
| Sleep | 7 / 136B | `07 EA 02 03` / `07 EA 02 1B` |
| Get mode | 8 / 1597B | `08 EA 02 01 FE` |

Checksum：從 byte 8 起到封包尾，每位相減。

模式編號：Off 0、Static 1、Breathing 2、Pulse 3、Spiral 4、Rainbow 5、Star 6、Trigger 7。

Z15 偵測條件：VID `3842`、介面、page `0x08`、usage `0x4B`。Z12 符合，只差 PID 與 report 6 長度。

## 假設（尚未送封包驗證）

1. Z12 與 Z15 同屬 Unleash HID 家族。Report 4（17B）與 report 7（136B）長度一致，短命令與模式/顏色封包很可能共用。
2. Report 6 在 Z12 縮成 32B，因為只有五區而不是 108 顆單鍵。`5 * 4 = 20` bytes 顏色 + 約 8 bytes header，塞得進 32。
3. 按鍵映射 / 巨集 / profile 本體比較可能在 report 5/8/9（265B）或 0x0F（264B）。OpenRGB 沒碰這些。約 100 鍵 × 2–3 bytes 約 200–300，長度對得上。
4. 介面 0 的 16-byte `FF00/80` feature 可能是簡短命令通道，或是與介面 1 report 1 的 vendor feature 同源。優先探測介面 1。

## 明確還沒做的事

- 沒有對 Z12 送過 GET_FEATURE / SET_FEATURE。
- 沒有 Windows Unleash 的 USBPcap 擷取。
- 沒有證實 9 組 profile 的封包格式。
- 沒有 keymap 的 HID usage ↔ 實體鍵位表。
- 不確定巨集是完全 onboard 播放，還是有些要靠 Unleash 常駐程式攔截。若是後者，Mac 上沒有 daemon 就不會觸發。TPU 寫「onboard profiles」，比較像前者，但仍要 sniff 才能定案。

## 建議的下一步（需使用者同意）

1. 用 hidapi **只讀** GET_FEATURE：report 4、6、7，看回傳是不是 `xx EA 02 ...`。失敗就停，不要改送 SET。
2. 若確認家族協定：先做五區 RGB 的唯寫小工具，封包長度用 Z12 的 32/136，不要複製 Z15 的 792。
3. 準備一台 Windows（或 USB 直通 VM），裝 Unleash，對「改一顆 E1」「改一個燈區」「存成 profile 2」各抓一份 USBPcap。
4. 對照 sniff 與 report 5/8/9，還原映射與巨集。

## 風險

- 送錯長度或亂填 checksum 可能讓燈卡住，通常拔插可恢復。
- 寫壞 keymap 可能讓某些鍵沒反應；應先讀出再寫，並保留 dump。
- 韌體更新封包（若存在）絕對不要重放。
- macOS 若誤開介面 0 並 Seize，鍵盤會暫時死掉，拔插即可。
