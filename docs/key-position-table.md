# EVGA Z12 Key Position Table (from EDispNetLib.dll static analysis)

Source: static reverse engineering of `EDispNetLib.dll` (EVGA Unleash RGB
1.0.28.0). No HID packets were sent to the keyboard. All values come from
the .NET metadata / IL in the DLL (decompiled with `monodis` to
`/tmp/edisp_full.il`).

This document supersedes the 5-key E-key table previously obtained from
Pasquotcho's Rust code. The full keyboard position table is the enum
`EDispNetLib.Hardwares.Z12RGB.Defines.LedKeyPosition`.

---

## 1. Complete key position table

The `position` byte in report 4's keymap command (KeyFunctionRam,
GeneralUsbMainCommand=0x07) is a value of the
`EDispNetLib.Hardwares.Z12RGB.Defines.LedKeyPosition` enum
(IL `/tmp/edisp_full.il` lines 112995–113141). It is a `uint8` enum.

The 5 known E-key positions from Pasquotcho's Rust code match exactly:
E1=0x15, E2=0x2B, E3=0x41, E4=0x52, E5=0x66.

### Physical keys (0x00–0x78)

| position | name | HID usage (approx) | notes |
|----------|------|--------------------|-------|
| 0x00 | GameMode | — | special, not a physical key |
| 0x01 | ESC | 0x29 | |
| 0x02 | F1 | 0x3A | |
| 0x03 | F2 | 0x3B | |
| 0x04 | F3 | 0x3C | |
| 0x05 | F4 | 0x3D | |
| 0x06 | F5 | 0x3E | |
| 0x07 | F6 | 0x3F | |
| 0x08 | F7 | 0x40 | |
| 0x09 | F8 | 0x41 | |
| 0x0A | F9 | 0x42 | |
| 0x0B | F10 | 0x43 | |
| 0x0C | F11 | 0x44 | |
| 0x0D | F12 | 0x45 | |
| 0x0E | PrintScreen | 0x46 | |
| 0x0F | ScrollLock | 0x47 | |
| 0x10 | PauseBreak | 0x48 | |
| 0x11 | — | — | gap (no enum member) |
| 0x12 | MultimediaPreviousTrack | consumer | |
| 0x13 | MultimediaPlayPause | consumer | |
| 0x14 | MultimediaNextTrack | consumer | |
| 0x15 | E1 | — | macro key 1 ✓ matches Pasquotcho |
| 0x16 | GraveAccent | 0x35 | ` ` |
| 0x17 | 1 | 0x1E | |
| 0x18 | 2 | 0x1F | |
| 0x19 | 3 | 0x20 | |
| 0x1A | 4 | 0x21 | |
| 0x1B | 5 | 0x22 | |
| 0x1C | 6 | 0x23 | |
| 0x1D | 7 | 0x24 | |
| 0x1E | 8 | 0x25 | |
| 0x1F | 9 | 0x26 | |
| 0x20 | 0 | 0x27 | |
| 0x21 | Minus | 0x2D | `-` |
| 0x22 | Equals | 0x2E | `=` |
| 0x23 | Backspace | 0x2A | |
| 0x24 | Insert | 0x49 | |
| 0x25 | Home | 0x4A | |
| 0x26 | PageUp | 0x4B | |
| 0x27 | NumLock | 0x53 | |
| 0x28 | KeypadDivide | 0x54 | |
| 0x29 | KeypadMultiply | 0x55 | |
| 0x2A | KeypadMinus | 0x56 | |
| 0x2B | E2 | — | macro key 2 ✓ matches Pasquotcho |
| 0x2C | Tab | 0x2B | |
| 0x2D | Q | 0x14 | |
| 0x2E | W | 0x1A | |
| 0x2F | E | 0x08 | |
| 0x30 | R | 0x15 | |
| 0x31 | T | 0x17 | |
| 0x32 | Y | 0x1C | |
| 0x33 | U | 0x18 | |
| 0x34 | I | 0x0C | |
| 0x35 | O | 0x12 | |
| 0x36 | P | 0x13 | |
| 0x37 | LBracket | 0x2F | `[` |
| 0x38 | RBracket | 0x30 | `]` |
| 0x39 | BackSlash | 0x31 | `\` |
| 0x3A | Delete | 0x4C | |
| 0x3B | End | 0x4D | |
| 0x3C | PageDown | 0x4E | |
| 0x3D | Keypad7 | 0x5F | |
| 0x3E | Keypad8 | 0x60 | |
| 0x3F | Keypad9 | 0x61 | |
| 0x40 | KeypadPlus | 0x57 | |
| 0x41 | E3 | — | macro key 3 ✓ matches Pasquotcho |
| 0x42 | CapsLock | 0x39 | |
| 0x43 | A | 0x04 | |
| 0x44 | S | 0x16 | |
| 0x45 | D | 0x07 | |
| 0x46 | F | 0x09 | |
| 0x47 | G | 0x0A | |
| 0x48 | H | 0x0B | |
| 0x49 | J | 0x0D | |
| 0x4A | K | 0x0E | |
| 0x4B | L | 0x0F | |
| 0x4C | Semicolon | 0x33 | `;` |
| 0x4D | SingleQuotation | 0x34 | `'` |
| 0x4E | Enter | 0x28 | |
| 0x4F | Keypad4 | 0x5C | |
| 0x50 | Keypad5 | 0x5D | |
| 0x51 | Keypad6 | 0x5E | |
| 0x52 | E4 | — | macro key 4 ✓ matches Pasquotcho |
| 0x53 | LSHIFT | 0xE1 (left) | modifier position |
| 0x54 | Z | 0x1D | |
| 0x55 | X | 0x1B | |
| 0x56 | C | 0x06 | |
| 0x57 | V | 0x19 | |
| 0x58 | B | 0x05 | |
| 0x59 | N | 0x11 | |
| 0x5A | M | 0x10 | |
| 0x5B | Comma | 0x36 | `,` |
| 0x5C | Period | 0x37 | `.` |
| 0x5D | Slash | 0x38 | `/` |
| 0x5E | RSHIFT | 0xE5 (right) | modifier position |
| 0x5F | — | — | gap (Z5 has E6 here; Z12 omits it) |
| 0x60 | ArrowUp | 0x52 | |
| 0x61 | — | — | gap (Z5 has E7 here; Z12 omits it) |
| 0x62 | Keypad1 | 0x59 | |
| 0x63 | Keypad2 | 0x5A | |
| 0x64 | Keypad3 | 0x5B | |
| 0x65 | KeypadEnter | 0x58 | |
| 0x66 | E5 | — | macro key 5 ✓ matches Pasquotcho |
| 0x67 | LCONTROL | 0xE0 (left) | modifier position |
| 0x68 | WIN | 0xE3 (left GUI) | |
| 0x69 | LALT | 0xE2 (left Alt) | |
| 0x6A | Space | 0x2C | |
| 0x6B | RALT | 0xE6 (right Alt) | |
| 0x6C | FN | — | Fn layer key |
| 0x6D | Menu | 0x65 (Application) | |
| 0x6E | RCONTROL | 0xE4 (right Ctrl) | |
| 0x6F | ArrowLeft | 0x50 | |
| 0x70 | ArrowDown | 0x51 | |
| 0x71 | ArrowRight | 0x4F | |
| 0x72 | Keypad0 | 0x62 | |
| 0x73 | KeypadPeriod | 0x63 | |
| 0x74 | WheelUp | — | mouse wheel |
| 0x75 | WheelDown | — | mouse wheel |
| 0x76 | Mute | consumer | |
| 0x77 | Sharp | — | ISO key (#, non-US) |
| 0x78 | UK_BackSlash | 0x64 (Intl 6/§) | ISO key |

### Light-bar / logo LED zones (0xA0–0xC3)

These are NOT physical keys; they are addressable LED zones used by the
5-zone RGB feature. They appear in the same enum because the LED test
command reuses `LedKeyPosition` to address individual zones. The Z12 is
"5-zone RGB" but the firmware exposes a finer-grained zone grid:

| position | name |
|----------|------|
| 0xA0 | LeftLightBar1 |
| 0xA1 | LeftLightBar2 |
| 0xA2 | LeftLightBar3 |
| 0xA3 | LeftLightBar4 |
| 0xA4 | LeftLightBar5 |
| 0xA5 | LeftLightBar6 |
| 0xA6 | LeftLightBar7 |
| 0xA7 | LeftLightBar8 |
| 0xA8 | LeftLightBar9 |
| 0xB0 | RightLightBar1 |
| 0xB1 | RightLightBar2 |
| 0xB2 | RightLightBar3 |
| 0xB3 | RightLightBar4 |
| 0xB4 | RightLightBar5 |
| 0xB5 | RightLightBar6 |
| 0xB6 | RightLightBar7 |
| 0xB7 | RightLightBar8 |
| 0xB8 | RightLightBar9 |
| 0xC0 | Logo1 |
| 0xC1 | Logo2 |
| 0xC2 | Logo3 |
| 0xC3 | Logo4 |

### Sentinels

| position | name | meaning |
|----------|------|---------|
| 0xC4 | MAX_COUNT | upper bound for iteration (count = 196) |
| 0xFF | LEDNA | "LED N/A" — invalid / not-a-key marker |

### Gaps in the physical-key range

- `0x11`: no enum member between PauseBreak (0x10) and
  MultimediaPreviousTrack (0x12).
- `0x5F`: Z5/Z20 reserve this for E6 (a 6th macro key). Z12 has only 5
  macro keys, so it is omitted.
- `0x61`: Z5/Z20 reserve this for E7 (a 7th macro key). Z12 omits it.
- `0x79`–`0x9F`, `0xA9`–`0xAF`, `0xB9`–`0xBF`, `0xC4`–`0xFE`: unused.

The `GetMacroBindingList` method (IL line 31758) iterates
`Enum.GetValues(LedKeyPosition)` and skips `0xC4` (MAX_COUNT) and `0xFF`
(LEDNA) — confirming the whole enum is the canonical key list and those
two are sentinels.

### 2026-08-16 實機掃描修正：0x6C–0x78 軟體 enum 盲區

實機 GET_FEATURE 全掃描（`src/scan_positions.py`，見
[`keymap-scan-result.md`](keymap-scan-result.md)）發現軟體 enum 在
`0x6B`（WinLock）之後跳到 `0xA0`（LED zone），中間 `0x6C`–`0x78` 共
13 個 position **韌體實際有效（回 0xC0）但軟體沒具名**。這些 position
的 KeyDefine 解碼如下：

| position | 軟體 enum | 實機解碼 | 說明 |
|----------|-----------|---------|------|
| 0x6C | (未列) | function 0x04, p1/p2/p3=0 | **第 5 種 function，未還原**（可能是層切換） |
| 0x6D | (未列) | KeyboardEmulation: Menu (0x65) | Application/Menu 鍵 |
| 0x6E | (未列) | KeyboardEmulation: RCtrl modifier (0x10) | 右 Ctrl 修飾鍵 |
| 0x6F | (未列) | KeyboardEmulation: Left (0x50) | 方向左 |
| 0x70 | (未列) | KeyboardEmulation: Down (0x51) | 方向下 |
| 0x71 | (未列) | KeyboardEmulation: Right (0x4F) | 方向右 |
| 0x72 | (未列) | KeyboardEmulation: Num0 (0x62) | NumPad 0 |
| 0x73 | (未列) | KeyboardEmulation: Num. (0x63) | NumPad . |
| 0x74 | (未列) | Consumer: Volume Down (0xEA) | 音量減 |
| 0x75 | (未列) | Consumer: Volume Up (0xE9) | 音量加 |
| 0x76 | (未列) | Consumer: Mute (0xE2) | 靜音 |
| 0x77 | (未列) | KeyboardEmulation: HID 0x32 | 非 US `#`/`~` 鍵（ISO） |
| 0x78 | (未列) | KeyboardEmulation: HID 0x64 | 國際鍵（Intl 6/§） |

> **注意**：軟體 IL 的 `LedKeyPosition` enum 確實有 `0x6C`–`0x78` 的
> 成員（見上表「Physical keys」段的 FN/Menu/RCtrl/方向鍵/NumPad 等），
> 但 subagent 初步分析時誤判為「跳到 0xA0」。實機掃描確認這 13 個
> position 全部有效。軟體 enum 與實機的吻合度為 108/113（差異僅 5 個
> LED zone，本來就不該在 keymap）。

### 2026-08-16 function 碼（已從 IL 逆向還原）

實機掃描發現兩個未知 function，已從 IL 還原（見
[`function-codes.md`](function-codes.md)）：

| function | 出現位置 | 語意 | 狀態 |
|----------|---------|------|------|
| 0x04 | position 0x6C (FN) | **FnKey**：FN 層切換鍵，按住時用 Secondary keymap | ✅ 已還原 |
| 0x05 | position 0x00 (GameMode) | **EKey**：GameMode 切換鍵 | ✅ 已還原 |

兩者都是「實體鍵角色宣告」（不是輸出動作），Parameter 全 0。
完整 function 碼表見 [`function-codes.md`](function-codes.md)。

---

## 2. Encoding rule for the position byte

The position is **not** the HID usage code. It is the keyboard's own
physical/LED index, assigned in a fixed top-to-bottom, left-to-right
order that follows the physical layout of a full-size keyboard:

```
Row 0:  GameMode, ESC, F1–F12, PrintScreen, ScrollLock, PauseBreak,
        [gap], PrevTrack, PlayPause, NextTrack, E1
Row 1:  ` 1–0 - = Backspace  Insert Home PgUp  NumLk / * -
        E2
Row 2:  Tab Q–P [ ] \  Del End PgDn  7 8 9 +
        E3
Row 3:  CapsLk A–L ; ' Enter  (nav none)  4 5 6
        E4
Row 4:  LShift Z–/ RShift  [gap] Up  [gap]  1 2 3 Enter
        E5
Row 5:  LCtrl Win LAlt Space RAlt FN Menu RCtrl  ← ↓ →  0 .
        (mouse wheel) Mute # UK-\
Light bars: 0xA0–0xA8 (left 9), 0xB0–0xB8 (right 9)
Logo: 0xC0–0xC3 (4 zones)
```

The E-keys are interleaved at the end of each logical row, placed where
that row's leftmost macro key sits physically. The position values are
**dense and monotonic per row**; gaps exist only where a sibling product
(Z5/Z20) has extra macro keys (E6 at 0x5F, E7 at 0x61) that the Z12 lacks.

There is no arithmetic formula from HID usage to position; it is a
table lookup. The firmware's on-board LED controller is addressed by this
index, which is why it is shared between the keymap command and the
LED-test command.

Z12 vs Z5/Z20 note: the `EDispNetLib.Hardwares.Z5RGB.Defines.LedKeyPosition`
enum (IL line 35446) is byte-for-byte identical to the Z12 one **except**
the Z5 version additionally defines `LKP_E6 = 0x5F` and `LKP_E7 = 0x61`.
The Z12 simply omits those two members; the remaining values are
identical, so position values are stable across the Z12/Z15/Z20 family.

---

## 3. Shift layer (SecondaryKeyAssignment)

The primary (main) layer and the secondary (Shift/FN) layer use **the
same position table**. They are NOT separate position spaces.

The layer is selected by the `GeneralUsbSubCommand2` byte of the
`GeneralUsbCommand` header (IL `/tmp/edisp_full.il` lines 105359–105360,
enum `EDispNetLib.Hardwares.Z12RGB.GeneralUsbSubCommand`):

| GeneralUsbSubCommand2 value | name | layer |
|------------------------------|------|-------|
| 0x00 | PrimaryKeyAssignment | main layer |
| 0x01 | SecondaryKeyAssignment | Shift/FN layer |

The `KeyFunctionRamFeatureReport` constructor (IL line 34200 / Z12
equivalent) takes `(ReadWrite, PrimarySecondary, keyPosition, keyDefine)`
and packs them as:

```
byte[0]  ReportId            = 0x04
byte[1]  Header1             = 0xEA
byte[2]  Header2             = 0x02
byte[3]  GeneralUsbMainCommand = 0x07  (KeyFunctionRam)
byte[4]  GeneralUsbSubCommand1 = 0x00 (Write) / 0x01 (Read) / 0x02 (Default)
byte[5]  GeneralUsbSubCommand2 = 0x00 (Primary) / 0x01 (Secondary)
byte[6]  KeyPosition         (LedKeyPosition)
byte[7]  KeyDefine.Function
byte[8]  KeyDefine.Parameter1
byte[9]  KeyDefine.Parameter2
byte[10] KeyDefine.Parameter3
byte[11..] Reserved
```

So to read/write a key's Shift-layer binding, send the same position with
byte[5]=0x01 instead of 0x00. The `Profile.ReadKeyFunction` and
`Profile.WriteKeyFunction` methods (IL lines 25726, 25815, 25918) take
`primarySecondary` as their first argument and thread it into byte[5].

The bulk profile report `ProfileUsbFeatureReport` (IL line 23447) holds
two parallel arrays: `Primary` and `Secondary` (each
`KeyDefine[121]`), confirming the two layers are stored separately on
board but indexed by the same position.

---

## 4. KeyDefine structure (report 4 bytes 7–10)

Struct `EDispNetLib.Hardwares.Z12RGB.Defines.KeyDefine` (IL line 113365),
`.pack 1`, 4 bytes:

| offset | field | type | size |
|--------|-------|------|------|
| 0 | Function | `KeyFunction` (uint8) | 1 |
| 1 | Parameter1 | uint8 | 1 |
| 2 | Parameter2 | uint8 | 1 |
| 3 | Parameter3 | uint8 | 1 |

In report 4 these are bytes 7–10 (after `04 EA 02 07 RW Layer Pos`).

### KeyFunction enum (IL line 113149)

| value | name |
|-------|------|
| 0x00 | KeyboardEmulation |
| 0x02 | ConsumerDeviceEmulation |
| 0x03 | MacroFunction |
| 0x04 | FnKey |
| 0x05 | EKey |
| 0x06 | MouseWheelScroll |
| 0x07 | MouseLeftClick |
| 0x08 | MouseRightClick |
| 0x09 | MouseWheelClick |
| 0x0B | InformationReportKeyPosition |
| 0x0C | SystemControlReport |
| 0x11–0x19 | Profile1–Profile9 |
| 0x1E | ProfileCyclePlus |
| 0x1F | ProfileCycleMinus |
| 0x20 | IncreaseBrightness |
| 0x21 | DecreaseBrightness |
| 0x22 | IncreaseLightEffect |
| 0x23 | DecreaseLightEffect |
| 0xFF | Disable |

(0x01 is unused.)

### Parameter meaning per Function

The field meaning of Parameter1/2/3 depends on `Function`, decoded from
the `KeyDefine` constructors (IL lines 113378–113490):

| Function | Parameter1 | Parameter2 | Parameter3 |
|----------|-----------|------------|------------|
| 0x00 KeyboardEmulation | **Modifier** (see Modifier enum below) | **Key1** = `HidKeyCode` | **Key2** = `HidKeyCode` (2nd simultaneous key, 0 if none) |
| 0x02 ConsumerDeviceEmulation | `consumerCode & 0xFF` (low byte) | `consumerCode >> 8` (high byte) | 0 |
| 0x03 MacroFunction | macro number (0-based) | runMethod | repeatTime |
| 0x04 FnKey | 0 | 0 | 0 |
| 0x05 EKey | target E-key `LedKeyPosition` | 0 | 0 |
| 0x06 MouseWheelScroll | `MouseWheelScroll` (0=Up, 1=Down) | 0 | 0 |
| 0x07–0x09 Mouse* | 0 | 0 | 0 |
| 0x0B InformationReportKeyPosition | (the key position being queried) | 0 | 0 |
| 0x0C SystemControlReport | system control code | 0 | 0 |
| 0x11–0x19 ProfileN | 0 | 0 | 0 |
| 0x1E/0x1F ProfileCycle± | 0 | 0 | 0 |
| 0x20–0x23 Brightness/Effect | 0 | 0 | 0 |
| 0xFF Disable | 0 | 0 | 0 |

#### Important correction to prior assumption

For **function=0x00 (single key / keyboard emulation)**:
- Parameter1 = **Modifier** bitmask (NOT a generic parameter)
- Parameter2 = **Key1** (primary HID keycode, `HidKeyCode`)
- Parameter3 = **Key2** (optional second simultaneous HID keycode, 0 if unused)

This is established by the `KeyDefine(Modifier, HidKeyCode key1, HidKeyCode key2)`
constructor (IL line 113378): it sets Function=0, Parameter1=modifier,
Parameter2=key1, Parameter3=key2.

For **function=0x03 (macro)**: Parameter1 = macro number, Parameter2 =
runMethod, Parameter3 = repeatTime (constructor IL line 113468). The
single-arg macro constructor (IL line 113454) sets only Parameter1 and
leaves Parameter2/3 = 0.

### Modifier enum (IL line 113186), `[Flags]` bitmask

| bit | value | name |
|-----|-------|------|
| 0 | 0x01 | LeftControl |
| 1 | 0x02 | LeftShift |
| 2 | 0x04 | LeftAlt |
| 3 | 0x08 | LeftGUI |
| 4 | 0x10 | RightControl |
| 5 | 0x20 | RightShift |
| 6 | 0x40 | RightAlt |
| 7 | 0x80 | RightGUI |
| — | 0x00 | None |

These are OR-able. Example: Ctrl+Shift+C = `KeyDefine(Function=0,
P1=0x01|0x02=0x03, P2=HidKeyCode.HKC_C=0x06, P3=0)`.

### HidKeyCode enum (IL line 113208)

`uint8`, standard USB HID keyboard usage IDs:
A=0x04 … Z=0x1D, 1=0x1E … 0=0x27, Enter=0x28, Esc=0x29, Backspace=0x2A,
Tab=0x2B, Space=0x2C, Minus=0x2D, Equals=0x2E, LBracket=0x2F,
RBracket=0x30, BackSlash=0x31, Semicolon=0x33, SingleQuotation=0x34,
GraveAccent=0x35, Comma=0x36, Period=0x37, Slash=0x38, CapsLock=0x39,
F1=0x3A … F12=0x45, PrintScreen=0x46, ScrollLock=0x47, PauseBreak=0x48,
Insert=0x49, Home=0x4A, PageUp=0x4B, Delete=0x4C, End=0x4D,
PageDown=0x4E, RightArrow=0x4F, LeftArrow=0x50, DownArrow=0x51,
UpArrow=0x52, NumLock=0x53, KeypadSlash=0x54, KeypadStar=0x55,
KeypadMinus=0x56, KeypadPlus=0x57, KeypadEnter=0x58, Keypad1=0x59 …
Keypad9=0x61, Keypad0=0x62, KeypadPeriod=0x63, App=0x65,
F13=0x68 … F24=0x73, LSHIFT=0xE1. (These are raw HID usage values, NOT
the LedKeyPosition index.)

### HidConsumerCode enum (IL line 113329), `uint16`

16-bit consumer-page codes, split across Parameter1 (low byte) and
Parameter2 (high byte):

| code | name | P1 | P2 |
|------|------|----|----|
| 0x0B5 | Scan_Next_Track | 0xB5 | 0x00 |
| 0x0B6 | Scan_Previous_Track | 0xB6 | 0x00 |
| 0x0B7 | Stop | 0xB7 | 0x00 |
| 0x0CD | PlayPause | 0xCD | 0x00 |
| 0x0E2 | Mute | 0xE2 | 0x00 |
| 0x0E9 | Volume_Up | 0xE9 | 0x00 |
| 0x0EA | Volume_Down | 0xEA | 0x00 |
| 0x183 | Media_Select | 0x83 | 0x01 |
| 0x18A | Mail | 0x8A | 0x01 |
| 0x192 | Calculator | 0x92 | 0x01 |
| 0x194 | My_Computer | 0x94 | 0x01 |
| 0x221 | WWW_Search | 0x21 | 0x02 |
| 0x223 | WWW_Home | 0x23 | 0x02 |
| 0x224 | WWW_Back | 0x24 | 0x02 |
| 0x225 | WWW_Forward | 0x25 | 0x02 |
| 0x226 | WWW_Stop | 0x26 | 0x02 |
| 0x227 | WWW_Refresh | 0x27 | 0x02 |
| 0x22A | WWW_Favorites | 0x2A | 0x02 |

### MouseWheelScroll enum (IL line ~113490)

| value | name |
|-------|------|
| 0x00 | Up |
| 0x01 | Down |

---

## How the table is consumed (method references)

- `EDispNetLib.Hardwares.Z12RGB.Profile::WriteKeyFunctionToRam(GeneralUsbSubCommand primarySecondary, LedKeyPosition keyPosition, KeyDefine keyDefine)`
  — IL line 104338. Builds a `KeyFunctionRamFeatureReport` and calls
  `SetAndGetFeature` with report id 5. This is the live-RAM write path.
- `EDispNetLib.Hardwares.Z12RGB.Profile::ReadKeyFunction(...)` / `ReadDefaultKeyFunction(...)`
  — read path, same report with SubCommand1 = Read (0x01) / Default (0x02).
- `EDispNetLib.Hardwares.Z12RGB.KeyFunctionRamFeatureReport::.ctor(ReadWrite, PrimarySecondary, keyPosition, keyDefine)`
  — packs the packet; GeneralUsbMainCommand=0x07.
- `EDispNetLib.Hardwares.MacroFunctionBase::GetMacroBindingList()` (IL line 31758)
  — iterates `Enum.GetValues(LedKeyPosition)` skipping MAX_COUNT (0xC4)
  and LEDNA (0xFF), proving the enum is the authoritative key list.
- `EDispNetLib.Hardwares.Z12RGB.Information::ReadKeyPosition(...)` (IL line 95872)
  — the `KeyPositionInformationReportEnableDisableFeatureReport` path
  (GeneralUsbMainCommand=0x33), separate feature used to ask the
  keyboard which key is currently pressed.

---

## Summary for implementation

1. Position table = `Z12RGB.Defines.LedKeyPosition` enum (this file,
   section 1). 113 named members (incl. light-bar/logo zones); physical
   keys span 0x00–0x78.
2. Layer (Primary vs Secondary/Shift) is selected by packet byte[5]
   (`GeneralUsbSubCommand2`): 0x00 = primary, 0x01 = secondary. Same
   position table for both layers.
3. KeyDefine is 4 bytes: `{Function, Parameter1, Parameter2, Parameter3}`.
   For single-key bindings (Function=0x00): P1=Modifier bitmask, P2=Key1
   (HidKeyCode), P3=Key2 (HidKeyCode, 0 if none). For macros (0x03):
   P1=macro#, P2=runMethod, P3=repeatTime. For consumer (0x02):
   P1=low byte, P2=high byte of the 16-bit consumer code.
4. No SET_REPORT was sent during this analysis. All values are from
   static metadata.