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
| [Pasquotcho/evga-z12-keys](https://github.com/Pasquotcho/evga-z12-keys) | **可用。** Rust + hidapi，已還原 Z12 E1–E5 單鍵映射協定（report 4 / 17B / `0xEA 0x02` 家族 / command `07` 讀寫、`12` 存檔）。作者只測過 PID `2622`，本機 `2612` 需驗證。詳見 [`external-protocol-comparison.md`](external-protocol-comparison.md) |
| ~~erik-berger350/evga-z12-keys-linux~~ | **惡意，勿碰。** 假「132 commits」實為垃圾時間戳，無任何 `.rs`/`Cargo.toml`；`index.html` 是 XOR 混淆的 Roblox 作弊注入器下載頁。詳見 [`external-protocol-comparison.md`](external-protocol-comparison.md) |

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

## 假設與驗證狀態

1. **✅ 已證實（2026-08-16 實機 GET_FEATURE）**：Z12 與 Z15 同屬 Unleash HID 家族。對介面 1 送 report 4 讀 E-key，回應開頭 `04 EA 02 07 01 00 C0 ...`，`0xEA 0x02` magic、command `0x07`、成功碼 `0xC0` 全部吻合。PID `2612` 與 Pasquotcho 的 `2622` 走同一協定。Report 4（17B）長度一致。Report 7（136B）尚待驗證。
2. Report 6 在 Z12 縮成 32B，因為只有五區而不是 108 顆單鍵。`5 * 4 = 20` bytes 顏色 + 約 8 bytes header，塞得進 32。**尚未驗證。**
3. **✅ 已證實（2026-08-16 實證）**：巨集是 **onboard 播放，不需要 Unleash 常駐程式**。按 E1 自動依序輸出 `j j l h s i a o`（8 鍵），macOS 上無任何 EVGA 軟體。巨集本體比較可能在 report 5/8/9（265B）或 0x0F（264B），**待 GET_FEATURE 讀取確認**。
4. 介面 0 的 16-byte `FF00/80` feature 可能是簡短命令通道，或是與介面 1 report 1 的 vendor feature 同源。優先探測介面 1。**尚未驗證。**

## 2026-08-16 實機 GET_FEATURE 探測結果

腳本：`src/probe_ekeys.py`（Python 3 + hidapi，`.venv/`）。只開介面 1
（`interface==1`、`usage_page==0x08`、`usage==0x4B`），只送 GET_FEATURE，
不送 SET，不碰介面 0。E-key position 表來自 Pasquotcho `src/main.rs:19-39`。

讀取機制（兩個根因，見 [`troubleshooting.md`](troubleshooting.md)）：
1. report 4 是 feature report，必須用 `send_feature_report`（不能用 `write`，
   後者是 output report，鍵盤不認）。
2. `get_feature_report` 首次讀回的是 buffer 裡上一筆的過時回應。解法：
   每顆 E-key 送兩次、丟棄首次、取第二次。延遲無效（第一筆永遠被舊
   session 污染）。

讀取命令：`04 EA 02 07 01 00 00 <pos>`（+ 9 bytes 0）。回應 17B，結構：
`[ID, EA, 02, 07, 01, 00, C0, pos, fn, mod, key1, key2, 0...]`。

穩定讀取結果（送兩次丟棄首次，全部 position 吻合）：

| E-key | pos | fn | mod | key1 | key2 | 實證輸出（按 E-key 自動播放） |
|-------|-----|----|----|------|------|------------------------------|
| E1 | 0x15 | 0x03 | 0x06 | 0x01 | 0x00 | `j j l h s i a o`（8 鍵） |
| E2 | 0x2B | 0x03 | 0x07 | 0x01 | 0x00 | `j j l k a i`（6 鍵） |
| E3 | 0x41 | 0x03 | 0x04 | 0x01 | 0x00 | `j j l b r a n d`（8 鍵） |
| E4 | 0x52 | 0x03 | 0x05 | 0x01 | 0x00 | `j j l j i n g`（7 鍵） |
| E5 | 0x66 | 0x03 | 0x03 | 0x01 | 0x00 | `j j m i n`（5 鍵） |

### `function` 欄位解碼（部分已知）

| function | 意義 | 來源 |
|----------|------|------|
| `0x00` | 單鍵映射（`key1` = HID 鍵碼，`mod` = modifier bitmask） | Pasquotcho |
| `0x03` | **onboard 巨集播放**（`mod` = 巨集引用/編號，本體在別的 report） | 2026-08-16 實證 |
| `0xFF` | disable | Pasquotcho |

`function=0x03` 時 `key1=0x01`、`key2=0x00` 固定，`mod` 值 0x03–0x07 對應
E1–E5 的巨集引用。巨集本體（如 `jjlhsiao` 的鍵碼序列）不在 report 4，
待讀 report 5/8/9/0x0F 確認存放位置。

### 巨集 onboard 播放（已證實）

按 E-key 自動依序輸出按鍵序列，macOS 上無任何 EVGA 軟體。證實巨集是
onboard 播放，不需要 Unleash 常駐程式。五個巨集都以 `jjl` 開頭（E5 是
`jj`），來源未知（可能是使用者之前用 Unleash 設的，或出廠預設）。

待解與注意點：

- **巨集本體存放位置未知**：report 4 只存引用（`fn=0x03 mod=0x06` 等），
  巨集內容（鍵碼序列）的存放位置尚未找到。2026-08-16 已用 GET_FEATURE
  直接探測 report 5/8/9/0x0F，結果如下（見「report 5/8/9/0x0F 直接
  GET_FEATURE 探測」段）：四個 report 都沒回傳巨集鍵碼。report 5/8
  回應的是 report 4 的過時快取；report 9/0x0F 回應開頭不是 EA 02 且
  byte[6]=0xC1（可能是「不支援/空」狀態碼）。**假設：巨集本體在
  report 5 或 8，但要先用 report 4 帶某個 command 選巨集編號，再 GET
  report 5/8 才會回傳該巨集的鍵碼序列**（類似 Z15 用 report 8 帶參數
  讀目前模式 `08 EA 02 01 FE`）。
- **`function=0x03` 的 `mod` 欄位語意未完全解**：0x03–0x07 對應 E5–E1，
  但不知道它是「巨集編號」還是「巨集所在 report 的 offset」，也不知道
  巨集長度資訊存哪。
- `byte[6] == 0xC0` 在本機確認是成功碼，與 Pasquotcho 一致。report 9/
  0x0F 直接 GET 回 `0xC1`，可能是「不支援/空」的狀態碼（待確認）。
- report 4 短命令**不需要 checksum**（Pasquotcho 不送，本機回應正常）；
  report 6/7 的 checksum 演算法仍待本機驗證。

## report 5/8/9/0x0F 直接 GET_FEATURE 探測（2026-08-16）

腳本：`src/probe_reports.py`。對 report 5/8/9/0x0F 各送 GET_FEATURE
（送兩次、丟棄首次），搜尋 E1 巨集鍵碼 `0D 0D 0F 0B 16 12 04 12`
（= jjlhsiao）及較短前綴。

| Report | 回應開頭 | EA 02 | byte[6] | 巨集特徵 | 判讀 |
|--------|---------|-------|---------|---------|------|
| 0x05 | `04 EA 02 07 01 00 C0 66...` | ✅ | 0xC0 | ❌ | 回應的是 report 4 的過時快取（E5 內容），非 report 5 本體 |
| 0x08 | `04 EA 02 07 01 00 C0 66...` | ✅ | 0xC0 | ❌ | 同上，report 4 過時快取 |
| 0x09 | `09 00 00 00 00 00 C1 66...` | ❌ | 0xC1 | ❌ | report ID 回映 0x09，非 EA 02 家族；0xC1 可能是「空/不支援」 |
| 0x0F | `0F 00 00 00 00 00 C1 66...` | ❌ | 0xC1 | ❌ | 同 report 9，非 EA 02 家族 |

結論：直接 GET_FEATURE 讀不到巨集本體。report 5/8 的回應被 report 4
快取污染（鍵盤沒回應 report 5/8 的內容）。report 9/0x0F 不是 EA 02
家族。下一步假設：巨集本體在 report 5 或 8，需要先用 report 4 帶
command 選巨集編號，再 GET report 5/8。

## report 4 command 空間唯讀試探（2026-08-16）

腳本：`src/probe_commands.py`。掃 report 4 的 command 0x00–0x20
（byte4=01 讀模式，跳過已知 0x07 keymap / 0x12 存檔），找讀巨集的命令。

baseline（command 0xFF）：`04 EA 02 00 01 00 C1 00 00 03 01 00...`，
byte[6]=0xC1（不支援）。

| command | 回應 byte[6] | 結果 |
|---------|-------------|------|
| 0x01 | 0xC0 ✅ | 有效！回應 `04 EA 02 01 01 00 C0 1D 00 03 01 00...`，byte[7]=0x1D。但無巨集特徵，用途未知（可能是 profile/模式查詢） |
| 0x07 | (跳過) | 已知 keymap 讀寫 |
| 0x00, 0x02–0x06, 0x08–0x11, 0x13–0x20 | 0xC1 | 全部不支援 |

command 0x01 換 param 0x01–0x05 全回 0xC1，只有 param=0x00 成功。

結論：report 4 的 command 空間（0x00–0x20）只有 0x01 和 0x07 有效，
沒有任何 command 回應包含巨集鍵碼。「用 report 4 帶 command 選巨集
編號」的假設排除。

## report 5/8 帶 EA 02 payload 試探（2026-08-16）

腳本：`src/probe_macro_reports.py`。對 report 5/8 送
`<rid> EA 02 <cmd> 01 00 00 <param>` payload（模仿 Z15 的
`08 EA 02 01 FE` 讀模式），再 GET 同 report 讀回應。試了 16 組
(cmd, param)（含 Z15 的 0x01/0xFE、keymap 0x07 配 E1–E5 mod 值、
未知 0x08–0x10）。

結果：report 5 和 8 對**所有** 32 組命令回應都是**全 0**（265B）。
沒有 EA 02 magic、沒有 payload、沒有巨集特徵。

結論：report 5 和 8 不接受 `EA 02` 家族命令。鍵盤收到帶 `EA 02` 的
report 5/8 payload 後不回應任何資料。「巨集本體在 report 5/8 帶參數
GET」的假設排除。

## report 6/7 直接 GET_FEATURE 探測（2026-08-16）

腳本：`src/probe_rgb_reports.py`。

| Report | 回應 | EA 02 | byte[6] | 巨集 |
|--------|------|-------|---------|------|
| 0x06 (32B) | 全 0 | ❌ | 0x00 | ❌ |
| 0x07 (136B) | `07 00...C1 00...` | ❌ | 0xC1 | ❌ |

Report 6 回全 0（鍵盤不回應）。Report 7 回 `0xC1`（不支援）。
兩者都沒有巨集本體，符合預期（它們是 RGB report）。

## 純 GET_FEATURE 唯讀探測結論（2026-08-16）

所有 feature report 和 report 4 命令空間都已試完：

| 探測方向 | 結果 |
|----------|------|
| report 4 command 0x00–0x20 | 只有 0x01（未知設定）和 0x07（keymap）有效，無巨集 |
| report 5/8 直接 GET | 回 report 4 過時快取 |
| report 5/8 帶 `EA 02 <cmd>` payload | 回全 0 |
| report 9/0x0F 直接 GET | `0xC1` 不支援 |
| report 6(32B) 直接 GET | 全 0 |
| report 7(136B) 直接 GET | `0xC1` 不支援 |

**巨集本體用純 GET_FEATURE 找不到。** 最可能原因：巨集內部用鍵盤
自己的 scan code 編碼存儲，不是直接放 HID usage code，所以搜尋
`0D 0D 0F...`（jjlhsiao 的 HID 碼）永遠找不到。或者巨集存放的讀取
方式需要先送我們還不知道的命令組合。

下一步需要 Windows USBPcap sniff 或逆向 Unleash RGB 軟體，才能還原
巨集讀寫協定。

## Unleash RGB 軟體逆向分析（2026-08-16）

從官方下載 EVGA Unleash RGB 1.0.28.0（NSIS installer），解壓後發現
是 .NET WPF 應用。核心協定邏輯在 `EDispNetLib.dll`（700KB，.NET
assembly）。用 `monodis`（Mono 6.14.1）反編譯 IL + `dnfile` 解析
metadata。完整分析見 [`unleash-reverse-engineering.md`](unleash-reverse-engineering.md)。

### Report ID 對照（軟體枚舉 ↔ 實機 descriptor，全部吻合）

| 軟體命名 | Report ID | 長度 | 用途 |
|----------|-----------|------|------|
| Information | 0x03 | — | 裝置資訊 |
| GeneralUsb | 0x04 | 17B | 短命令（keymap / EKeyMode / profile） |
| FirmwareUpdate | 0x05 | 265B | 韌體（**禁碰**） |
| LedColorSetting | 0x06 | 32B | 五區 RGB |
| LedPreset / ProfileInRAM | 0x07 | 136B | LED 模式 / 顏色 |
| ProfileUsb | 0x08 | 265B | profile |
| **MacroUsb** | **0x09** | **265B** | **巨集本體（分封包）** |
| **MacroNameUsb** | **0x0A** | **59B** | **巨集名稱** |
| SWCustomizeData | 0x0F | 264B | 軟體自訂資料 |

### 回應碼（ResponseCommand 枚舉，與實測完全一致）

| 值 | 名稱 | 實測對應 |
|----|------|---------|
| 0xC0 | Success | ✅ report 4 讀 E-key 成功 |
| 0xC1 | Fail | ✅ report 9/0x0F 直接 GET、不支援的 command |
| 0xC2 | InProcess | 尚未實測 |

### E-key function 碼（KeyDefine.Function，非 EKeyMode 枚舉）

| function 值 | 名稱 | 實證 |
|-------------|------|------|
| 0x00 | KeyboardEmulation（單鍵映射） | Pasquotcho 已知 |
| 0x03 | MacroFunction（巨集播放） | ✅ 2026-08-16 實證（E1=jjlhsiao 等） |
| 0xFF | Disable | Pasquotcho 已知 |

report 4 keymap 寫入 `KeyDefine{Function=0x03, Parameter1=巨集編號}`
即把 E-key 綁到第 N 號巨集。我們讀到的 `mod` 值 0x03–0x07 就是巨集
編號（E5=0x03、E3=0x04、E4=0x05、E1=0x06、E2=0x07）。

### 巨集封包結構

**MacroData（report 9, 265B）** — 巨集本體分封包：

```
[0]  ReportId = 0x09
[1]  Header1 = 0xEA
[2]  Direction (Read=0x01 / Write=0x02)
[3]  Command = 0x01 (Data)
[4]  MacroIndex (1-based, 1..100)
[5]  PackIndex (0..3, 分 4 包各 256B payload)
[6]  ResponseCommand (0xC0=成功)
[7]  Checksum = -(sum of Data[256]) & 0xFF
[8..263]  Data[256]
[264]  Reserved
```

**MacroNameData（report 10, 59B）** — 巨集名稱：

```
[0]  ReportId = 0x0A
[1]  Header1 = 0xEA
[2]  Header2 = 0x02
[3]  Direction (Read=0x01 / Write=0x02)
[4]  MacroIndex
[5]  Reserved
[6]  ResponseCommand
[7]  Checksum
[8]  NameCount
[9..58]  Name[50] (UTF-8)
```

**MacroStatus（report 9, 265B）** — 查哪些巨集編號已使用：

```
[0]  ReportId = 0x09
[1]  Header1 = 0xEA
[2]  Direction (Read=0x01)
[3..265]  Status[263] 位元陣列（Status[i]==1 → 巨集編號 i-7 已使用）
```

### 巨集本體編碼（tag-based，不是純 HID usage code）

巨集動作資料用 tag-based 編碼，**鍵盤鍵用 Windows VirtualKeyCode**，
不是 HID usage code。這解釋了之前搜尋 `0D 0D 0F`（jjlhsiao 的 HID
碼）找不到的原因。

| Tag | 意義 |
|-----|------|
| `0x01` + 16-bit LE ms | 延遲（毫秒） |
| `0x04 0x00` | 無延遲 |
| 單 byte（0x01–0x73） | 鍵盤鍵按下 = **HID usage code**（非 Windows VK code，見實證） |
| 單 byte \| `0x80` | 鍵盤鍵放開（usage code 的 bit 7 設 1） |
| `0x03` + 16-bit HID usage | 多媒體 / 系統鍵（3 bytes） |
| `0x80` + X + Y | 滑鼠移動（與鍵放開的 0x80 區分：滑鼠 0x80 後面跟 2 byte 座標） |
| `0x7A/0x7B/0x7C` | 滑鼠左/右/中鍵按下 |
| `0xFA/0xFB/0xFC` | 滑鼠左/右/中鍵放開 |
| `0xF8/0x78` | 滾輪 |

> **2026-08-16 實證修正**：逆向報告原本說巨集鍵碼是 Windows VK code，
> 實機讀取後確認是 **HID usage code**。E1 巨集 `jjlhsiao` 的本體開頭
> `01 14 00 0d 01 14 00 8d...`，`0x0d`=j（HID）、`0x0f`=l、`0x0b`=h、
> `0x16`=s、`0x0c`=i、`0x04`=a、`0x12`=o，與實證完全吻合。`0x8d`=
> `0x0d | 0x80` = j 放開。不需 VK→HID 對應表。

### 巨集讀寫完整流程

**讀取**（`LoadMapping`）：
1. 送 report 9 `MacroStatus`(Read=1) → 回 `Status[263]` 查哪些編號有巨集
2. 對每個已用編號，送 report 10 `MacroNameData`(Read=1, idx) → 讀巨集名稱
3. 送 report 9 `MacroData`(Read=1, idx, PackIndex 0..3) → 分 4 包讀 256B 拼回本體

**寫入**（`SaveMacro`）：
1. 組 `MacroUsbFeatureReport`（Write=2, idx, 0xC1）
2. `GetMacorData` 編碼動作 → `CalculateCheckSum`
3. 分 4 個 `MacroData` 封包（PackIndex 0..3）送 report 9
4. 每包之間 150ms 延遲（`ExecuteReport`，避免韌體 crash）

**刪除**（`DoDeleteMacro`）：
report 9 送 `MacroUsbFeatureReport`(Write=2, idx) 設
`MacroStatusOfUse=0xFF`、`LengthOfMacroData=0`、`LengthOfMacroName=0`。

**綁定到 E-key**：
report 4 keymap 寫入 `KeyDefine{Function=0x03, Parameter1=巨集編號}`。

### 為什麼之前 GET_FEATURE report 9 回 0xC1

直接送 report 9 全 0 payload 再 GET，鍵盤回 `0xC1`（Fail）是因為
沒有帶正確的 `Direction` + `Command` + `MacroIndex`。要送
`0x09 0xEA 0x01 0x01 <idx> <packIdx> 0x00 0x00 ...`（Read + Data 命令）
才會回巨集資料。

### 其他已還原的命令

| GeneralUsbMainCommand | 值 | 用途 |
|----------------------|-----|------|
| Profile | 0x06 | profile 操作 |
| KeyFunctionRam | 0x07 | keymap 讀寫（已實證） |
| EKeyMode | 0x0B | E-key 模式開關（PC/Game） |
| SaveProfile | 0x12 | 存檔（已實證） |

| GeneralUsbSubCommand | 值 | 用途 |
|---------------------|-----|------|
| Write | 0x00 | 寫入 |
| Read | 0x01 | 讀取 |
| PrimaryKeyAssignment | 0x00 | 主鍵層 |
| SecondaryKeyAssignment | 0x01 | Shift 層 |
| Default | 0x02 | 預設 |

## 巨集讀取實機驗證（2026-08-16）

腳本：`src/probe_macros.py`。用逆向還原的協定，實機讀取巨集本體。
唯讀（Direction=Read），送 `discard_count=3`（送 3 次丟棄前 2 次）排空
report 9/10 之間的 cross-report 快取污染。

### MacroStatus（report 9）— 已驗證 ✅

送 `09 EA 01`(Read) + 263B 0。回應 byte[8]..[14] = `01`，對應巨集編號
1–7 已使用。byte[15] 起為 `FF`（未使用）。五顆 E-key 的巨集編號
（3–7）全部確認已使用。

### MacroNameData（report 10）— 已驗證 ✅

送 `0A EA 02 01`(Read) + MacroIndex。回 `0xC0`(Success) 時讀到名稱：

| 巨集 # | E-key | 名稱 | LengthOfName |
|--------|-------|------|-------------|
| 3 | E5 | (快取問題未讀到) | — |
| 4 | E3 | `line 方韋` | 11 |
| 5 | E4 | `line敬庭` | 10 |
| 6 | E1 | `line蕭家兄弟` | 16 |
| 7 | E2 | `line 凱仁` | 11 |

名稱用 UTF-8 編碼，支援中文。以 `line` 開頭是使用者命名習慣。

### MacroData（report 9, PackIndex 0..3）— 已驗證 ✅

送 `09 EA 01 01`(Read+Data) + MacroIndex + PackIndex。回 `0xC0`(Success)，
Checksum = `-(sum of Data[256]) & 0xFF` 全部驗算通過。

4 個 PackIndex 的 Data[256] 拼回 = `MacroUsbFeatureReport` 序列化的
offset 8 起 1024B。模板欄位佈局（從拼回的 payload 解析）：

| payload offset | 模板 offset | 欄位 | 巨集 #06 實測值 |
|----------------|-------------|------|----------------|
| 0 | 8 | LengthOfMacroName | 16 |
| 1..50 | 9..58 | MacroName[50] | `line蕭家兄弟` |
| 51 | 59 | RunMethodOfMacro | 0x00 (Looping_KeyRelease) |
| 52 | 60 | RepeatTimeOfMacro | 0 |
| 53 | 61 | TimeUnitOfMacro | 0 |
| 54..55 | 62..63 | LengthOfMacroData (uint16 LE) | 64 |
| 56..1022 | 64..1030 | MacroData[967]（動作本體） | 見下 |
| 1023 | 1031 | MacroStatusOfUse | 0x01 (使用中) |

### 巨集動作本體編碼 — 已驗證 ✅

巨集 #06（E1, `line蕭家兄弟`）的動作本體前 64B：

```
01 14 00 0d 01 14 00 8d 01 14 00 0d 01 14 00 8d
01 14 00 0f 01 14 00 8f 01 14 00 0b 01 14 00 8b
01 14 00 16 01 14 00 96 01 14 00 0c 01 14 00 8c
01 14 00 04 01 14 00 84 01 14 00 12 01 14 00 92
```

解碼（`01 14 00` = 延遲 20ms，單 byte = HID usage 按下，byte|0x80 = 放開）：

```
延遲20ms → 按 j(0x0d) → 延遲20ms → 放 j(0x8d)
延遲20ms → 按 j(0x0d) → 延遲20ms → 放 j(0x8d)
延遲20ms → 按 l(0x0f) → 延遲20ms → 放 l(0x8f)
延遲20ms → 按 h(0x0b) → 延遲20ms → 放 h(0x8b)
延遲20ms → 按 s(0x16) → 延遲20ms → 放 s(0x96)
延遲20ms → 按 i(0x0c) → 延遲20ms → 放 i(0x8c)
延遲20ms → 按 a(0x04) → 延遲20ms → 放 a(0x84)
延遲20ms → 按 o(0x12) → 延遲20ms → 放 o(0x92)
```

**與實證（按 E1 自動輸出 `jjlhsiao`）完全吻合。**

巨集動作格式確認：
- `0x01` + 16-bit LE ms = 延遲（實測 `01 14 00` = 20ms）
- 單 byte（0x01–0x73）= HID usage code **按下**
- 單 byte | `0x80`（0x81–0xF3）= HID usage code **放開**
- 每個按鍵是「延遲 → 按下 → 延遲 → 放開」配對

> **重要修正**：逆向報告說巨集用 Windows VK code 是誤判。實證確認
> 用的是 **HID usage code**（`0x0d`=j、`0x04`=a 等），不需要
> VK→HID 對應表。`0x80` bit 是「放開」修飾，不是滑鼠 tag（滑鼠
> `0x80` 後面跟 2 byte 座標，鍵放開只有 1 byte）。

### 待解的快取問題

- 讀取多個巨集時，第一個巨集的 MacroData 會吃到 MacroStatus 或
  MacroNameData 的 cross-report 快取殘留。`discard_count=3` 解決了
  大部分，但偶爾第一個巨集仍回 `0xC1` 或 LengthOfMacroData=0。
- MacroStatus 的 Status 位元陣列有時 byte 值不是 0/1 而是 `FF`，
  可能是「未使用」的另一種編碼，待確認。
- MacroNameData 的 0xC0/0xC1 交替出現也是快取問題（送兩次丟棄首次
  在 report 10 不夠，可能要提高到 3 次）。

## 明確還沒做的事

- ~~沒有對 Z12 送過 GET_FEATURE / SET_FEATURE。~~ → GET_FEATURE（report 4/7/9/10）和 SET_FEATURE（report 4 keymap Write）都已驗證。
- ~~沒有 Windows Unleash 的 USBPcap 擷取。~~ → 直接逆向 Unleash RGB 軟體（EDispNetLib.dll），還原完整協定。
- ~~沒有證實 9 組 profile 的封包格式。~~ → GetProfile 已驗證（profile=1，1–9 全有效）。report 8 整組 profile macOS 讀不到，report 7 LED 參數可讀。
- ~~沒有 keymap 的 HID usage ↔ 實體鍵位表。~~ → 完整 121 鍵 position 表已確認。
- ~~不確定巨集是完全 onboard 播放。~~ → 已證實 onboard 播放，巨集讀取流程已驗證。
- ~~report 9/10 讀取流程未驗證。~~ → 已驗證。
- ~~function 0x04/0x05 未還原。~~ → 已從 IL 還原（FnKey/EKey）。
- ~~SET_FEATURE keymap 寫入未測。~~ → 已驗證（E5→F13 成功）。
- **待解決**：report 6/8 在 macOS hidapi 上讀不到（feature report GET 不回應）。
- ~~**待確認**：存檔命令 `04 EA 02 12 00 00 00 01` 回 0xC1，需測 profile=0。~~
  → **2026-08-16 已確認**：`04 EA 02 12 00 00 00 00` 回 0xC0；帶編號 1 回 0xC1。
  拔插後讀回一致，flash 持久化成立。
- **待驗證**：巨集寫入流程（report 9 Write 分封包）。
- **待製作**：CLI 工具（整合所有已驗證協定）。

## keymap 全掃描實機驗證（2026-08-16）

腳本：`src/scan_positions.py`。對 position 0x00–0xFF 逐個送 report 4
keymap read（唯讀），看哪些回 0xC0（有效）。完整結果見
[`keymap-scan-result.md`](keymap-scan-result.md)。

### 掃描數量

| 項目 | 數量 |
|------|------|
| 實機有效 position | 121 個 |
| 軟體 enum 有列 | 113 個 |
| 兩者吻合 | 108 個 |
| 軟體有列但實機無效 | 5 個（LED zone 0xA0–0xA4，正常） |
| 實機有效但軟體沒列 | 13 個（0x6C–0x78，軟體 enum 盲區，已補完） |

### Function 碼全表（已還原）

Function 0x04 和 0x05 已從 IL 逆向還原（見 [`function-codes.md`](function-codes.md)）。

| function | 名稱 | 語意 | Parameter |
|----------|------|------|-----------|
| 0x04 | FnKey | FN 層切換鍵（position 0x6C），按住時用 Secondary keymap | 全 0（角色宣告） |
| 0x05 | EKey | GameMode 切換鍵（position 0x00） | 全 0（角色宣告） |

完整 function 碼表（from `Z12RGB.Defines.KeyFunction` enum）：

| function | 名稱 | 語意 |
|----------|------|------|
| 0x00 | KeyboardEmulation | 單鍵/組合鍵映射 |
| 0x02 | Consumer | 媒體鍵（consumer code） |
| 0x03 | MacroFunction | 巨集播放 |
| 0x04 | FnKey | FN 層切換鍵（角色宣告） |
| 0x05 | EKey | GameMode 切換鍵（角色宣告） |
| 0x06 | MouseWheelScroll | 滑鼠滾輪 |
| 0x07–0x09 | MouseLeft/Right/MiddleClick | 滑鼠按鍵 |
| 0x0B | InformationReportKeyPosition | 按鍵位置資訊 |
| 0x0C | SystemControlReport | 系統控制 |
| 0x11–0x19 | Profile1–9 | 切換到 profile 1–9 |
| 0x1E/0x1F | ProfileCyclePlus/Minus | profile 循環切換 |
| 0x20–0x23 | Increase/DecreaseBrightness/LED | 亮度/燈效調整 |
| 0xFF | Disable | 停用該鍵 |

### 這把鍵盤的目前 keymap 狀態

掃描顯示這把鍵盤被大幅重新映射過（不是原廠預設）：
- Grave/1/2/3 → 媒體鍵（Stop/Prev/PlayPause/Next）
- 主鍵盤整段「左上平移一格」（Tab→Grave、Q→1、W→2...）
- 右半邊方向/編輯/NumPad → 字母鍵鏡像平移
- 5 顆 E-key 綁巨集 #3–#7
- Num. 和 App 被 disable
- 只有 ESC 和 F1–F12 等功能鍵維持預設

## profile 讀取實機驗證（2026-08-16）

腳本：`src/probe_profiles.py`。完整協定見 [`profile-protocol.md`](profile-protocol.md)。

### GetProfile（report 4, command 0x06）— 已驗證 ✅

送 `04 EA 02 06 01 00 00 00`（MainCommand=0x06, SubCmd=0x01=Get）。
回應 `04 EA 02 06 01 00 C0 01`，byte[6]=0xC0（Success），byte[7]=1（profile 編號）。

- 目前 profile：**1**
- 兩次讀取一致：✅
- 合法範圍（1–9）：✅

### Profile 1–9 掃描 — 已驗證 ✅

逐一讀取 profile 1–9，全部回 0xC0（有效）。

| profile | status | 有效 |
|---------|--------|------|
| 1–9 | 0xC0 | ✅ 全部有效 |

### Report 8（ProfileUsbFeatureReport）— macOS 限制 ❌

report 8 的整組 profile 讀取在 macOS hidapi 上**失敗**：
- 試了 `report_id=0x08 + inner_rid=0x07/0x08` 和 `report_id=0x07 + inner_rid=0x07`
- 鍵盤不回應 report 8 的 feature report GET
- `get_feature_report(0x08)` 始終回 report 4 buffer 殘留
- report 7 的 136B feature report 回 0xC1（不支援 ProfileCommand 讀取）

可能原因：report 8 是 Windows 專屬的 vendor feature report，macOS
IOHIDDevice 不認。需改用 report 7（136B）分段讀取或分包版
`ProfileUsbFeatureReport256`（256B × 6）。

### Profile 協定摘要（從逆向 + 實機驗證）

| 命令 | Report | MainCommand | 封包 | 實機驗證 |
|------|--------|-------------|------|---------|
| GetProfile | 4 (17B) | 0x06 | `04 EA 02 06 01 00 00 00` | ✅ 回 profile 編號 |
| SetProfile | 4 (17B) | 0x06 | `04 EA 02 06 00 00 00 <num>` | ✅ 1→2→1；profile 2 的 E5=disable |
| SaveProfile | 4 (17B) | 0x12 | `04 EA 02 12 00 00 00 00`（profile=0=當前） | ✅ 0xC0；`<num>=1` 回 0xC1 |
| ResetProfile | 4 (17B) | 0x09 | `04 EA 02 09 00 00 00 <num>` | 未測（會重置） |
| ReadProfile | 8 (265B) | — | `07 EA 02 01 <num> 00 00` | ❌ macOS 讀不到 |
| WriteProfile | 8 (265B) | — | `07 EA 02 00 <num> 00 00` | 未測 |

## report 7（ProfileInRAM, 136B）實機驗證（2026-08-16）

腳本：`src/probe_profile_ram.py`。report 7 在 macOS 上**完全可用**（跟
report 8 不同，report 8 讀不到）。9 個 MainCommand 裡 8 個回 0xC0。

封包結構：
```
[0]=0x07 [1]=0xEA [2]=0x02 [3]=MainCommand [4..5]=SubCommand(uint16 LE)
[6]=ResponseCommand [7]=CheckSum [8..135]=Data[128]
```

| MainCommand | 名稱 | Status | Data 內容 |
|-------------|------|--------|----------|
| 0x0B | KeyFunction | ✅ 0xC0 | `00 00 05...`（EKeyMode 或 keymap 狀態） |
| 0x0C | LED_LightingEffectMode | ✅ 0xC0 | `05 02`（主模式=5=Rainbow, 副模式=2） |
| 0x0D | LED_StaticOn | ✅ 0xC0 | `80...ff ff`（zone=0x80, 顏色=青色） |
| 0x0E | LED_Breathing | ✅ 0xC0 | 9B 參數 |
| 0x0F | LED_Pulse | ✅ 0xC0 | 29B 參數 |
| 0x10 | LED_SpiralRainbow | ✅ 0xC0 | 37B 參數 |
| 0x11 | LED_RainbowWave | ✅ 0xC0 | 27B 參數 |
| 0x12 | LED_Trigger | ✅ 0xC0 | 27B 參數 |
| 0x13 | LED_StarShining | ❌ 0xC1 | Z12 不支援此模式 |

report 7 = 「當前 RAM 中」的 LED/keymap 參數即時讀寫，128B data 段。
跟 report 8（整組 onboard profile, 265B）不同層次。report 7 改的是
「現在正在顯示的」，report 8 改的是「存在 flash 裡的某號 profile」。

### LED 模式寫入（2026-08-16）— 已驗證 ✅

Checksum：`CheckSum = -(sum of Data[128]) & 0xFF`（讀回 Rainbow `05 02`
時 byte[7]=0xF9，驗算通過）。

Write LightingEffectMode（MainCommand 0x0C, Sub=0x0000），只改 data[0:2]：
`07 EA 02 0C 00 00 00 <chk> 01 02 ...` → **0xC0**，讀回 StaticOn。
還原 `05 02` → **0xC0**，讀回 RainbowWave。未存檔、未碰 report 6。
CLI：`z12ctl led set StaticOn --sub 2` / `led set RainbowWave --sub 2`。

## SET_FEATURE 寫入測試（2026-08-16）

腳本：`src/test_write.py`。測試 report 4 keymap 的 Write 方向。

### Keymap 寫入 — 已驗證 ✅

流程：讀 E5 baseline（巨集 #3）→ 寫 E5 = F13（function=0x00, key=0x68）
→ 讀回確認 → 存檔 → 讀回確認 → 還原。

| 步驟 | 結果 |
|------|------|
| 讀 E5 baseline | ✅ `Macro: #3 runMethod=0x01` |
| 寫 E5 = F13 | ✅ `status=0xC0` |
| 讀回確認 | ✅ `KeyboardEmulation: key=0x68`（F13） |
| 存檔 `04 EA 02 12 00 00 00 01` | ❌ `status=0xC1`（Fail） |
| 存檔 `04 EA 02 12 00 00 00 00` | ✅ `status=0xC0`（2026-08-16，只送一次） |
| 存檔後讀回 | ✅ 仍是 F13（RAM 持久，存檔回 C1 但值在） |
| 還原 E5 | ✅ `Macro: #3`（已還原） |

**發現：**
1. **SET_FEATURE keymap 寫入成功**——report 4 Write(SubCmd=0x00) 完全可用。
2. **寫入即時生效**——不需要存檔就改變按鍵行為。
3. **存檔必須用 profile=0（當前）。** 2026-08-16 再測：
   `04 EA 02 12 00 00 00 00` 回 **0xC0**（連續 4 次 GET 一致）。
   `04 EA 02 12 00 00 00 01`（帶 profile 編號 1）回 **0xC1**。
   與 Unleash `SaveProfile(0)` / Pasquotcho 格式一致。只送一次
   SET_FEATURE，profile 編號與 E5/ESC keymap 讀回不變。
   **2026-08-16 拔插驗證**：拔 USB 再插回後 profile=1、E5=macro#3、
   ESC=Esc、LED=RainbowWave(0x05/0x02) 全部仍在。flash 持久化成立。
4. **存檔雖然回 C1，但 RAM 裡的值在重開裝置前不會丟**——存檔是寫 flash，
   C1 可能表示 flash 寫入失敗或參數不對，但 RAM 裡的修改仍有效。

## report 6（LedColorSetting, 32B）— macOS 讀不到 ❌

腳本：`src/probe_rgb.py`。試了 7 種 payload 組合（全 0、EA 02 01/00/0C/03
等），全部回 report 7 buffer 殘留 + 0xC1。跟 report 8 一樣，report 6 的
feature report GET 在 macOS 上不回應。五區 RGB 的讀取需用 report 7 的
LED 模式命令（0x0C–0x12），不用 report 6。

## 建議的下一步

1. ~~用 hidapi 只讀 GET_FEATURE：report 4、6、7~~ → report 4/7 已完成。report 6/8 在 macOS 讀不到。
2. ~~寫腳本讀巨集本體~~ → 已完成。
3. ~~五區 RGB~~ → report 6 讀不到，但 report 7（ProfileInRAM）能讀 LED 模式參數（0x0C–0x12），已驗證。
4. ~~讀寫設定檔 / profile~~ → GetProfile 已驗證（profile=1），report 7 能讀 LED 設定。report 8（整組 profile）macOS 讀不到。
5. ~~按鍵重新映射寫入~~ → ✅ 已驗證 SET_FEATURE keymap Write（E5→F13 成功）。
6. ~~**存檔命令修正**~~ → `04 EA 02 12 00 00 00 00`（profile=0）回 0xC0，
   拔插後讀回一致（flash 持久化成立）。
7. **巨集寫入**：協定已還原，HID usage code 編碼，待實機測試 Write 方向。
8. ~~**CLI 工具**~~ → 2026-08-16 唯讀 CLI `src/z12ctl.py` 已可用（info / keymap dump|get / macro list|get / profile get|list / led get）。寫入子命令尚未做。

## 風險

- 送錯長度或亂填 checksum 可能讓燈卡住，通常拔插可恢復。
- 寫壞 keymap 可能讓某些鍵沒反應；應先讀出再寫，並保留 dump。
- 韌體更新封包（若存在）絕對不要重放。
- macOS 若誤開介面 0 並 Seize，鍵盤會暫時死掉，拔插即可。
