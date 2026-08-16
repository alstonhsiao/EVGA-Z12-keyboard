# EVGA Z12 keymap position 全掃描結果

> 產生方式：`src/scan_positions.py --run`，對介面 1 送 256×2 次 GET_FEATURE
> （byte4=01 唯讀），掃描 position 0x00–0xFF，看哪些回 status 0xC0（有效）。
> 執行日期：2026-08-16。腳本路徑：[`src/scan_positions.py`](../src/scan_positions.py)。

## 1. 摘要

| 項目 | 值 |
|------|----|
| 掃描範圍 | position 0x00–0xFF（256 個） |
| 實機有效 position | **121 個**（回 status 0xC0） |
| 軟體 enum LedKeyPosition | 113 個具名鍵（排除 sentinel 0xC4 / 0xFF） |
| 兩者吻合 | 108 個 |
| 只在軟體有、實機無效 | 5 個：`0xA0`–`0xA4`（LED zone，非實體鍵，正常） |
| 只在實機有效、軟體沒列 | 13 個：`0x6C`–`0x78`（軟體 enum 的盲區，見下文） |

## 2. 軟體 enum vs 實機 差異

### 2.1 只在軟體有、實機無效（5 個，可解釋）

| position | 軟體名 | 說明 |
|----------|--------|------|
| 0xA0 | LED_Zone1 | 五區 RGB 的虛擬 zone，不是實體鍵，keymap 不會回 0xC0 |
| 0xA1 | LED_Zone2 | 同上 |
| 0xA2 | LED_Zone3 | 同上 |
| 0xA3 | LED_Zone4 | 同上 |
| 0xA4 | LED_Zone5 | 同上 |

這 5 個是 LED 區域索引，用在 report 6/7 的 RGB 封包，本來就不該出現在
keymap（report 4）的有效清單裡。**非異常。**

### 2.2 只在實機有效、軟體沒列（13 個，軟體 enum 的盲區）

| position | KeyDefine 解碼 | raw (byte7-11) |
|----------|----------------|----------------|
| 0x6C | `0x04`(0x04): p1=0x00 p2=0x00 p3=0x00 | `6c 04 00 00 00` |
| 0x6D | KeyboardEmulation: Menu | `6d 00 00 65 00` |
| 0x6E | KeyboardEmulation: RCtrl+0x00 | `6e 00 10 00 00` |
| 0x6F | KeyboardEmulation: Left | `6f 00 00 50 00` |
| 0x70 | KeyboardEmulation: Down | `70 00 00 51 00` |
| 0x71 | KeyboardEmulation: Right | `71 00 00 4f 00` |
| 0x72 | KeyboardEmulation: Num0 | `72 00 00 62 00` |
| 0x73 | KeyboardEmulation: Num. | `73 00 00 63 00` |
| 0x74 | Consumer(Media): consumerCode=0x00ea | `74 02 ea 00 00` |
| 0x75 | Consumer(Media): consumerCode=0x00e9 | `75 02 e9 00 00` |
| 0x76 | Consumer(Media): consumerCode=0x00e2 | `76 02 e2 00 00` |
| 0x77 | KeyboardEmulation: 0x32 | `77 00 00 32 00` |
| 0x78 | KeyboardEmulation: 0x64 | `78 00 00 64 00` |

觀察：

- 軟體 enum 在 `0x6B WinLock` 之後直接跳到 `0xA0 LED_Zone1`，中間
  `0x6C`–`0x78` 完全沒有具名。實機卻在這段回 0xC0，表示**軟體的
  LedKeyPosition enum 不完整**，韌體實際支援的 position 比 UI 列出的多。
- `0x6C` 回 function 0x04（腳本未定義的名稱），p1/p2/p3 全 0。0x04 不是
  KeyboardEmulation/Media/Macro/Disable 任何一種，是**第 5 種未還原的
  function**，需要進一步逆向（可能是「組合鍵/層切換」之類）。
- `0x6D`=Menu（HID 0x65）、`0x6E`=RCtrl 修飾、`0x6F/0x70/0x71`=方向鍵、
  `0x72/0x73`=Num0/Num. —— 這些看起來像**預設映射的延伸位置**（也許是
  FN 層或副鍵盤的第二映射）。
- `0x74/0x75/0x76` 是 media consumer code：
  - `0xE9` = Volume Increment
  - `0xEA` = Volume Decrement
  - `0xE2` = Mute
  這三個是標準 HID Consumer Page 音量鍵。
- `0x77`=HID 0x32（非標準鍵盤區，對應「鍵盤 0x32」即 `~`/non-US `#`）、
  `0x78`=HID 0x64（F13 區以外，可能是國際鍵）。這兩個是腳本 HID_NAMES
  表查不到而顯示原始碼，不是錯誤。

> 結論：軟體 enum 漏了 `0x6C`–`0x78` 共 13 個 position。`docs/` 裡的
> key-position-table 應補上這段。`0x6C` 的 function 0x04 是新發現，
> 需要後續還原。

## 3. 每個有效 position 的 KeyDefine 解碼

> 欄位：position → `Function: 內容`。raw 為 report 4 回應的 byte7–11
> （position / function / p1 / p2 / p3）。
>
> 標記說明：
> - **【預設】** = 按鍵映射到自身 HID 碼（沒被改過）。
> - **【改過】** = 被重新映射到別的鍵/巨集/媒體鍵/停用。

### 0x00–0x10：功能鍵區

| position | 名稱 | 解碼 | raw | 狀態 |
|----------|------|------|-----|------|
| 0x00 | GameMode | `0x05`(0x05): p1=0 p2=0 p3=0 | `00 05 00 00 00` | 特殊：GameMode 開關，function 0x05 未還原 |
| 0x01 | ESC | KeyboardEmulation: Esc | `01 00 00 29 00` | 【預設】 |
| 0x02 | F1 | KeyboardEmulation: F1 | `02 00 00 3a 00` | 【預設】 |
| 0x03 | F2 | KeyboardEmulation: F2 | `03 00 00 3b 00` | 【預設】 |
| 0x04 | F3 | KeyboardEmulation: F3 | `04 00 00 3c 00` | 【預設】 |
| 0x05 | F4 | KeyboardEmulation: F4 | `05 00 00 3d 00` | 【預設】 |
| 0x06 | F5 | KeyboardEmulation: F5 | `06 00 00 3e 00` | 【預設】 |
| 0x07 | F6 | KeyboardEmulation: F6 | `07 00 00 3f 00` | 【預設】 |
| 0x08 | F7 | KeyboardEmulation: F7 | `08 00 00 40 00` | 【預設】 |
| 0x09 | F8 | KeyboardEmulation: F8 | `09 00 00 41 00` | 【預設】 |
| 0x0A | F9 | KeyboardEmulation: F9 | `0a 00 00 42 00` | 【預設】 |
| 0x0B | F10 | KeyboardEmulation: F10 | `0b 00 00 43 00` | 【預設】 |
| 0x0C | F11 | KeyboardEmulation: F11 | `0c 00 00 44 00` | 【預設】 |
| 0x0D | F12 | KeyboardEmulation: F12 | `0d 00 00 45 00` | 【預設】 |
| 0x0E | PrintScreen | KeyboardEmulation: PrintScreen | `0e 00 00 46 00` | 【預設】 |
| 0x0F | ScrollLock | KeyboardEmulation: ScrollLock | `0f 00 00 47 00` | 【預設】 |
| 0x10 | Pause | KeyboardEmulation: Pause | `10 00 00 48 00` | 【預設】 |

### 0x11–0x14： Grave / 1 / 2 / 3 —— 已被改成媒體鍵

| position | 名稱 | 解碼 | raw | 狀態 |
|----------|------|------|-----|------|
| 0x11 | Grave `` ` `` | Consumer(Media): 0x00b7 (Stop) | `11 02 b7 00 00` | 【改過】→ 媒體 Stop |
| 0x12 | 1 | Consumer(Media): 0x00b6 (Previous) | `12 02 b6 00 00` | 【改過】→ 媒體 Previous |
| 0x13 | 2 | Consumer(Media): 0x00cd (Play/Pause) | `13 02 cd 00 00` | 【改過】→ 媒體 Play/Pause |
| 0x14 | 3 | Consumer(Media): 0x00b5 (Next) | `14 02 b5 00 00` | 【改過】→ 媒體 Next |

> 這 4 顆被綁成媒體播放控制（Stop/Prev/PlayPause/Next）。對應 consumer
> page：0xB5=Next、0xB6=Previous、0xB7=Stop、0xCD=Play/Pause。

### 0x15：E1 巨集鍵

| position | 名稱 | 解碼 | raw | 狀態 |
|----------|------|------|-----|------|
| 0x15 | E1 | Macro: macro#6 runMethod=0x01 repeat=0 | `15 03 06 01 00` | 【巨集】綁到 macro#6 |

### 0x16–0x23：Tab 區起，整段被往後 shift 一格

| position | 名稱 | 解碼 | raw | 狀態 |
|----------|------|------|-----|------|
| 0x16 | Tab | KeyboardEmulation: `` ` `` | `16 00 00 35 00` | 【改過】Tab→ Grave |
| 0x17 | Q | KeyboardEmulation: 1 | `17 00 00 1e 00` | 【改過】Q→1 |
| 0x18 | W | KeyboardEmulation: 2 | `18 00 00 1f 00` | 【改過】W→2 |
| 0x19 | E | KeyboardEmulation: 3 | `19 00 00 20 00` | 【改過】E→3 |
| 0x1A | R | KeyboardEmulation: 4 | `1a 00 00 21 00` | 【改過】R→4 |
| 0x1B | T | KeyboardEmulation: 5 | `1b 00 00 22 00` | 【改過】T→5 |
| 0x1C | Y | KeyboardEmulation: 6 | `1c 00 00 23 00` | 【改過】Y→6 |
| 0x1D | U | KeyboardEmulation: 7 | `1d 00 00 24 00` | 【改過】U→7 |
| 0x1E | I | KeyboardEmulation: 8 | `1e 00 00 25 00` | 【改過】I→8 |
| 0x1F | O | KeyboardEmulation: 9 | `1f 00 00 26 00` | 【改過】O→9 |
| 0x20 | P | KeyboardEmulation: 0 | `20 00 00 27 00` | 【改過】P→0 |
| 0x21 | [ | KeyboardEmulation: - | `21 00 00 2d 00` | 【改過】[→- |
| 0x22 | ] | KeyboardEmulation: = | `22 00 00 2e 00` | 【改過】]→= |
| 0x23 | \\ | KeyboardEmulation: Backspace | `23 00 00 2a 00` | 【改過】\\→Backspace |

> 模式：這段每顆都映射成「原本在它左上方那一格」的鍵（Tab←Grave、
> Q←1、W←2…）。像把整個鍵盤往右下平移一格。

### 0x24–0x2A：CapsLock 區，續平移

| position | 名稱 | 解碼 | raw | 狀態 |
|----------|------|------|-----|------|
| 0x24 | CapsLock | KeyboardEmulation: Insert | `24 00 00 49 00` | 【改過】CapsLock→Insert |
| 0x25 | A | KeyboardEmulation: Home | `25 00 00 4a 00` | 【改過】A→Home |
| 0x26 | S | KeyboardEmulation: PageUp | `26 00 00 4b 00` | 【改過】S→PageUp |
| 0x27 | D | KeyboardEmulation: NumLock | `27 00 00 53 00` | 【改過】D→NumLock |
| 0x28 | F | KeyboardEmulation: Num/ | `28 00 00 54 00` | 【改過】F→Num/ |
| 0x29 | G | KeyboardEmulation: Num* | `29 00 00 55 00` | 【改過】G→Num* |
| 0x2A | H | KeyboardEmulation: Num- | `2a 00 00 56 00` | 【改過】H→Num- |

### 0x2B：E2 巨集鍵

| position | 名稱 | 解碼 | raw | 狀態 |
|----------|------|------|-----|------|
| 0x2B | E2 | Macro: macro#7 runMethod=0x01 repeat=0 | `2b 03 07 01 00` | 【巨集】綁到 macro#7 |

### 0x2C–0x3C：J 區起，續平移 + 跳到方向/編輯鍵

| position | 名稱 | 解碼 | raw | 狀態 |
|----------|------|------|-----|------|
| 0x2C | J | KeyboardEmulation: Tab | `2c 00 00 2b 00` | 【改過】J→Tab |
| 0x2D | K | KeyboardEmulation: Q | `2d 00 00 14 00` | 【改過】K→Q |
| 0x2E | L | KeyboardEmulation: W | `2e 00 00 1a 00` | 【改過】L→W |
| 0x2F | ; | KeyboardEmulation: E | `2f 00 00 08 00` | 【改過】;→E |
| 0x30 | ' | KeyboardEmulation: R | `30 00 00 15 00` | 【改過】'→R |
| 0x31 | Enter | KeyboardEmulation: T | `31 00 00 17 00` | 【改過】Enter→T |
| 0x32 | LShift | KeyboardEmulation: Y | `32 00 00 1c 00` | 【改過】LShift→Y |
| 0x33 | Z | KeyboardEmulation: U | `33 00 00 18 00` | 【改過】Z→U |
| 0x34 | X | KeyboardEmulation: I | `34 00 00 0c 00` | 【改過】X→I |
| 0x35 | C | KeyboardEmulation: O | `35 00 00 12 00` | 【改過】C→O |
| 0x36 | V | KeyboardEmulation: P | `36 00 00 13 00` | 【改過】V→P |
| 0x37 | B | KeyboardEmulation: [ | `37 00 00 2f 00` | 【改過】B→[ |
| 0x38 | N | KeyboardEmulation: ] | `38 00 00 30 00` | 【改過】N→] |
| 0x39 | M | KeyboardEmulation: \\ | `39 00 00 31 00` | 【改過】M→\\ |
| 0x3A | , | KeyboardEmulation: Delete | `3a 00 00 4c 00` | 【改過】,→Delete |
| 0x3B | . | KeyboardEmulation: End | `3b 00 00 4d 00` | 【改過】.→End |
| 0x3C | / | KeyboardEmulation: PageDown | `3c 00 00 4e 00` | 【改過】/→PageDown |

### 0x3D–0x40：修飾鍵/Space → 數字鍵盤上半

| position | 名稱 | 解碼 | raw | 狀態 |
|----------|------|------|-----|------|
| 0x3D | RShift | KeyboardEmulation: Num7 | `3d 00 00 5f 00` | 【改過】RShift→Num7 |
| 0x3E | LCtrl | KeyboardEmulation: Num8 | `3e 00 00 60 00` | 【改過】LCtrl→Num8 |
| 0x3F | LAlt | KeyboardEmulation: Num9 | `3f 00 00 61 00` | 【改過】LAlt→Num9 |
| 0x40 | Space | KeyboardEmulation: Num+ | `40 00 00 57 00` | 【改過】Space→Num+ |

### 0x41：E3 巨集鍵

| position | 名稱 | 解碼 | raw | 狀態 |
|----------|------|------|-----|------|
| 0x41 | E3 | Macro: macro#4 runMethod=0x01 repeat=0 | `41 03 04 01 00` | 【巨集】綁到 macro#4 |

### 0x42–0x51：右修飾/方向/編輯區 → 字母鍵盤 + NumPad 左半

| position | 名稱 | 解碼 | raw | 狀態 |
|----------|------|------|-----|------|
| 0x42 | RAlt | KeyboardEmulation: CapsLock | `42 00 00 39 00` | 【改過】RAlt→CapsLock |
| 0x43 | R Ctrl | KeyboardEmulation: A | `43 00 00 04 00` | 【改過】RCtrl→A |
| 0x44 | Up | KeyboardEmulation: S | `44 00 00 16 00` | 【改過】Up→S |
| 0x45 | Down | KeyboardEmulation: D | `45 00 00 07 00` | 【改過】Down→D |
| 0x46 | Left | KeyboardEmulation: F | `46 00 00 09 00` | 【改過】Left→F |
| 0x47 | Right | KeyboardEmulation: G | `47 00 00 0a 00` | 【改過】Right→G |
| 0x48 | Ins | KeyboardEmulation: H | `48 00 00 0b 00` | 【改過】Ins→H |
| 0x49 | Home | KeyboardEmulation: J | `49 00 00 0d 00` | 【改過】Home→J |
| 0x4A | PgUp | KeyboardEmulation: K | `4a 00 00 0e 00` | 【改過】PgUp→K |
| 0x4B | Delete | KeyboardEmulation: L | `4b 00 00 0f 00` | 【改過】Delete→L |
| 0x4C | End | KeyboardEmulation: ; | `4c 00 00 33 00` | 【改過】End→; |
| 0x4D | PgDn | KeyboardEmulation: ' | `4d 00 00 34 00` | 【改過】PgDn→' |
| 0x4E | NumLock | KeyboardEmulation: Enter | `4e 00 00 28 00` | 【改過】NumLock→Enter |
| 0x4F | Num/ | KeyboardEmulation: Num4 | `4f 00 00 5c 00` | 【改過】Num/→Num4 |
| 0x50 | Num* | KeyboardEmulation: Num5 | `50 00 00 5d 00` | 【改過】Num*→Num5 |
| 0x51 | Num- | KeyboardEmulation: Num6 | `51 00 00 5e 00` | 【改過】Num-→Num6 |

### 0x52：E4 巨集鍵

| position | 名稱 | 解碼 | raw | 狀態 |
|----------|------|------|-----|------|
| 0x52 | E4 | Macro: macro#5 runMethod=0x01 repeat=0 | `52 03 05 01 00` | 【巨集】綁到 macro#5 |

### 0x53–0x5F：NumPad 右半 + 修飾鍵

| position | 名稱 | 解碼 | raw | 狀態 |
|----------|------|------|-----|------|
| 0x53 | Num+ | KeyboardEmulation: LShift+0x00 | `53 00 02 00 00` | 【改過】Num+→LShift（純修飾） |
| 0x54 | NumEnter | KeyboardEmulation: Z | `54 00 00 1d 00` | 【改過】NumEnter→Z |
| 0x55 | Num7 | KeyboardEmulation: X | `55 00 00 1b 00` | 【改過】Num7→X |
| 0x56 | Num8 | KeyboardEmulation: C | `56 00 00 06 00` | 【改過】Num8→C |
| 0x57 | Num9 | KeyboardEmulation: V | `57 00 00 19 00` | 【改過】Num9→V |
| 0x58 | Num4 | KeyboardEmulation: B | `58 00 00 05 00` | 【改過】Num4→B |
| 0x59 | Num5 | KeyboardEmulation: N | `59 00 00 11 00` | 【改過】Num5→N |
| 0x5A | Num6 | KeyboardEmulation: M | `5a 00 00 10 00` | 【改過】Num6→M |
| 0x5B | Num1 | KeyboardEmulation: , | `5b 00 00 36 00` | 【改過】Num1→, |
| 0x5C | Num2 | KeyboardEmulation: . | `5c 00 00 37 00` | 【改過】Num2→. |
| 0x5D | Num3 | KeyboardEmulation: / | `5d 00 00 38 00` | 【改過】Num3→/ |
| 0x5E | Num0 | KeyboardEmulation: RShift+0x00 | `5e 00 20 00 00` | 【改過】Num0→RShift（純修飾） |
| 0x5F | Num. | Disable: disabled | `5f ff 00 00 00` | 【停用】 |

### 0x60–0x6B：Backspace / 特殊鍵區

| position | 名稱 | 解碼 | raw | 狀態 |
|----------|------|------|-----|------|
| 0x60 | Backspace | KeyboardEmulation: Up | `60 00 00 52 00` | 【改過】Backspace→Up |
| 0x61 | App | Disable: disabled | `61 ff 00 00 00` | 【停用】 |
| 0x62 | LWin | KeyboardEmulation: Num1 | `62 00 00 59 00` | 【改過】LWin→Num1 |
| 0x63 | RWin | KeyboardEmulation: Num2 | `63 00 00 5a 00` | 【改過】RWin→Num2 |
| 0x64 | FN | KeyboardEmulation: Num3 | `64 00 00 5b 00` | 【改過】FN→Num3 |
| 0x65 | LightBar_Sw | KeyboardEmulation: NumEnter | `65 00 00 58 00` | 【改過】LightBar_Sw→NumEnter |
| 0x66 | E5 | Macro: macro#3 runMethod=0x01 repeat=0 | `66 03 03 01 00` | 【巨集】綁到 macro#3 |
| 0x67 | LED_Sw | KeyboardEmulation: LCtrl+0x00 | `67 00 01 00 00` | 【改過】LED_Sw→LCtrl（純修飾） |
| 0x68 | Profile_Sw | KeyboardEmulation: LGUI+0x00 | `68 00 08 00 00` | 【改過】Profile_Sw→LGUI（純修飾） |
| 0x69 | MacroRec | KeyboardEmulation: LAlt+0x00 | `69 00 04 00 00` | 【改過】MacroRec→LAlt（純修飾） |
| 0x6A | MacroRun | KeyboardEmulation: Space | `6a 00 00 2c 00` | 【改過】MacroRun→Space |
| 0x6B | WinLock | KeyboardEmulation: RAlt+0x00 | `6b 00 40 00 00` | 【改過】WinLock→RAlt（純修飾） |

### 0x6C–0x78：軟體 enum 盲區（13 個，已於 §2.2 討論）

| position | 解碼 | raw | 狀態 |
|----------|------|-----|------|
| 0x6C | `0x04`(0x04): p1=0 p2=0 p3=0 | `6c 04 00 00 00` | 未還原 function 0x04 |
| 0x6D | KeyboardEmulation: Menu | `6d 00 00 65 00` | 預設值（Menu） |
| 0x6E | KeyboardEmulation: RCtrl+0x00 | `6e 00 10 00 00` | 純修飾 RCtrl |
| 0x6F | KeyboardEmulation: Left | `6f 00 00 50 00` | 預設值（Left） |
| 0x70 | KeyboardEmulation: Down | `70 00 00 51 00` | 預設值（Down） |
| 0x71 | KeyboardEmulation: Right | `71 00 00 4f 00` | 預設值（Right） |
| 0x72 | KeyboardEmulation: Num0 | `72 00 00 62 00` | 預設值（Num0） |
| 0x73 | KeyboardEmulation: Num. | `73 00 00 63 00` | 預設值（Num.） |
| 0x74 | Consumer(Media): 0x00ea (Volume Decrement) | `74 02 ea 00 00` | 預設值（音量減） |
| 0x75 | Consumer(Media): 0x00e9 (Volume Increment) | `75 02 e9 00 00` | 預設值（音量加） |
| 0x76 | Consumer(Media): 0x00e2 (Mute) | `76 02 e2 00 00` | 預設值（靜音） |
| 0x77 | KeyboardEmulation: 0x32 | `77 00 00 32 00` | HID 0x32（非US #/~） |
| 0x78 | KeyboardEmulation: 0x64 | `78 00 00 64 00` | HID 0x64（國際鍵） |

## 4. 全鍵盤重新映射的整體觀察

這把 Z12 的 onboard keymap **幾乎被全面重新映射過**，不是原廠預設。
主要模式：

1. **左上區（Grave/1/2/3）→ 媒體鍵**（Stop/Prev/PlayPause/Next）。
2. **主鍵盤 Tab 開始整段「左上平移」**：Tab→Grave、Q→1、W→2… 一路到
   `\\`→Backspace；再從 CapsLock→Insert 接續到編輯鍵/NumPad 上排。
3. **右半邊方向/編輯/NumPad → 字母鍵 + NumPad 左半**，形成一個鏡像
   平移。
4. **5 顆巨集鍵 E1–E5** 分別綁到 macro#6/7/4/5/3（注意編號不連續、
   不照位置順序，表示使用者自己錄過巨集）。
5. **Num. 和 App 被 Disable**（0xFF）。
6. **多個特殊鍵（LED_Sw/Profile_Sw/MacroRec/WinLock/Num+/Num0）被改成
   純修飾鍵**（只送 modifier byte、不送 HID key），可能是要做組合鍵層。
7. **0x6C 出現未還原的 function 0x04**，全 0 參數。這是本次掃描的新發現，
   不在已知的 KeyboardEmulation/Media/Macro/Disable 四種之內。

> 注意：以上是 onboard memory 目前的內容（先前有人用 Unleash 改過）。
> 原廠預設應該是每顆映射到自身 HID 碼（如 Q→Q、W→W）。要還原成預設
> 需要送 SET_REPORT，本次掃描**沒有**做任何寫入。

## 5. 後續待辦

- 補完軟體 `LedKeyPosition` enum 漏掉的 `0x6C`–`0x78`（13 個 position）。
- 還原 function 0x04（0x6C）與 0x05（0x00 GameMode）的語意。
- 把 HID_NAMES 表補上 0x32、0x64 這兩個非US/國際鍵的名稱。
- 5 顆巨集鍵綁的 macro#3/4/5/6/7 需要讀 report 6/7 巨集區才能看到內容。