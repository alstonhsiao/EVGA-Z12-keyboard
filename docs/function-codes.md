# KeyDefine Function 碼語意（Z12）

來源：純靜態 IL 分析 `/tmp/edisp_full.il`（`EDispNetLib.dll` 反編譯）。
對應 enum：`EDispNetLib.Hardwares.Z12RGB.Defines.KeyFunction`（`IL 113147-113179`）。
對應 struct：`EDispNetLib.Hardwares.Z12RGB.Defines.KeyDefine`（`IL 113365-`，4 bytes：
`Function(uint8) + Parameter1(uint8) + Parameter2(uint8) + Parameter3(uint8)`）。

本檔只記錄靜態還原結果，未對鍵盤送任何 SET_REPORT。

---

## 結論：0x04 / 0x05 是什麼

| 碼 | enum 名稱 | 語意 | 實機出現位置 | 參數 |
|----|-----------|------|--------------|------|
| 0x04 | **FnKey** | FN 層切換鍵 | position 0x6C（`LKP_FN`） | p1/p2/p3 全 0，無意義 |
| 0x05 | **EKey** | E 鍵 = GameMode 切換鍵 | position 0x00（`LKP_GameMode`） | p1/p2/p3 全 0，無意義 |

兩者都是「特殊功能鍵標記」，不是可重映射的輸出動作。它們的 Parameter1/2/3
在 IL 的 `KeyDefine::.ctor(KeyFunction)` 裡被硬寫成 0（`IL 113428-113444`），
軟體端從不賦值；韌體端只認 function byte 決定該實體鍵的角色，參數欄不讀。

---

## 完整 KeyFunction enum（Z12RGB）

`IL 113147-113179`，`value__` 為 `unsigned int8`。注意 0x01、0x0A、
0x0D–0x10、0x1A–0x1D、0x24–0xFE 在 enum 裡沒有具名成員（空隙）。

| 碼 | enum 名稱 | 中文語意 | 參數欄含義 |
|----|-----------|----------|------------|
| 0x00 | KeyboardEmulation | 單鍵 / 修飾鍵+單鍵 / 修飾鍵+雙鍵 模擬 | P1=Modifier(flags), P2=HidKeyCode1, P3=HidKeyCode2 |
| 0x02 | ConsumerDeviceEmulation | 媒體 / Consumer 鍵 | P1=consumerCode % 256, P2=consumerCode / 256, P3=0 |
| 0x03 | MacroFunction | 巨集 | P1=macroNumber, P2=runMethod, P3=repeatTime |
| 0x04 | **FnKey** | FN 層切換鍵 | 全 0（無參數） |
| 0x05 | **EKey** | E 鍵 = GameMode 切換鍵 | 全 0（無參數） |
| 0x06 | MouseWheelScroll | 滾輪滾動 | P1=MouseWheelScroll enum 值 |
| 0x07 | MouseLeftClick | 滑鼠左鍵 | 無 |
| 0x08 | MouseRightClick | 滑鼠右鍵 | 無 |
| 0x09 | MouseWheelClick | 滾輪按下 | 無 |
| 0x0B | InformationReportKeyPosition | 回報按鍵 position（鍵盤定位用） | 無 |
| 0x0C | SystemControlReport | System Control report（Sleep / Power 等） | P1=SystemControl code |
| 0x11–0x19 | Profile1–Profile9 | 切到 profile 1–9 | 無 |
| 0x1E | ProfileCyclePlus | Profile 循環 + | 無 |
| 0x1F | ProfileCycleMinus | Profile 循環 - | 無 |
| 0x20 | IncreaseBrightness | 增加亮度 | 無 |
| 0x21 | DecreaseBrightness | 降低亮度 | 無 |
| 0x22 | IncreaseLightEffect | 下一個燈效 | 無 |
| 0x23 | DecreaseLightEffect | 上一個燈效 | 無 |
| 0xFF | Disable | 停用該鍵 | 無 |

> 本專案實機掃描（`docs/keymap-scan-result.md`）目前只見過 0x00、0x02、
> 0x03、0x04、0x05、0xFF。0x06–0x0C、0x11–0x23 是軟體 UI 可指派但尚未
> 在 onboard 預設 profile 裡觀察到的功能碼。

---

## 0x04 FnKey 詳解

### enum
`IL 113154`: `.field public static literal ... KeyFunction FnKey = int8(0x04)`

### ToString（UI 顯示名稱）
`KeyDefine::ToString()` 在 `IL 113559` 的 switch 表，case 4 → `IL_0957`
（`IL 36814`）：
```
IL_0957:  ldstr "FN"
```
即 UI 把這個 function 顯示成 "FN"。

### 參數欄
`KeyDefine::.ctor(KeyFunction function)`（`IL 113428-113444`）建構時把
Function 設成傳入值，P1/P2/P3 全設 0。軟體沒有任何路徑替 FnKey 的
P1/P2/P3 賦其他值——FnKey 是「無參數純標記」。

### 韌體行為推斷
FnKey 標記的實體鍵（position 0x6C = `LKP_FN`）是 FN 層修飾鍵。按住它時，
韌體改用 **Secondary keymap**（`ProfileUsbFeatureReport.Secondary[121]`）
解碼其他鍵，放開時回到 Primary keymap。這對應 `ProfileUsbFeatureReport`
同時存 `Primary[121]` 和 `Secondary[121]` 兩組映射（`IL 103179-103180`）。

### FnKey 不走 keymap 重映射
`Profile::SetKeyFunctionDefault(uint8)`（`IL 104185-104335`）在逐鍵迴圈
（index 0 到 195）裡，明確跳過 position 0x68 和 0x6C：
```
IL 104227:  br IL_0166              // 進迴圈
IL 104228:  ldloc.1
IL 104229:  ldc.i4.s 0x68          // LKP_WIN
IL 104231:  beq IL_0162            // 跳過，不寫 keymap
IL 104232:  ldloc.1
IL 104233:  ldc.i4.s 0x6c          // LKP_FN
IL 104235:  beq IL_0162            // 跳過，不寫 keymap
```
（`IL 104228-104235`）
這證明 FN 鍵（0x6C）和 WIN 鍵（0x68）不透過 report 4 KeyFunctionRam 重映射，
而是由獨立機制控制（見下）。

### FnKey 相關獨立 feature report
- **`FnKeyStateFeatureReport`**（`IL 105852-105895`）：
  - `Command`（GeneralUsbMainCommand = `0x30` FnKeyDisable，`IL 105339`）
  - `DisableState`（uint8，0=啟用 FN、1=停用 FN）
- `Z12RGBHidDevice::SetFnKeyDisabled(bool)`（`IL 107178-107226`）：
  發 `FnKeyStateFeatureReport(subCmd, state)` 經 `SetAndGetFeature(..., 5)`。
  預設參數 `disabled = true`（`.param [1] = bool(true)`）。
- `Z12RGBHidDevice::GetFnKeyDisabled(bool&)`（`IL 107229-`）：讀回 DisableState。
- 另有 `FNWINStatus` enum（`IL 105836-105842`）：`WindowsL=0x00`、`FNL=0x01`，
  透過 `GameModeKeysWinFnRamFeatureReport`（MainCommand `0x27`，`IL 105338`）
  把左下角的實體鍵在「Windows 鍵」和「FN 鍵」角色之間互換。

### 與實機掃描的對照
`docs/keymap-scan-result.md` 記錄 position 0x6C 回 `04 00 00 00 00`
（function 0x04，p1/p2/p3 全 0），與本 IL 分析完全一致：0x04 = FnKey，
無參數。先前掃描文件把它標為「未還原 function 0x04，可能是層切換」——
**現已還原為 FnKey，確認是 FN 層修飾鍵標記**。

---

## 0x05 EKey 詳解

### enum
`IL 113155`: `.field public static literal ... KeyFunction EKey = int8(0x05)`

### ToString（UI 顯示名稱）
`KeyDefine::ToString()` switch case 5 → `IL_0962`（`IL 36818`）：
```
IL_0962:  ldstr "E"
```
即 UI 把這個 function 顯示成 "E"（E 鍵 = EVGA 鍵 / GameMode 鍵）。

### 參數欄
同 FnKey，`KeyDefine::.ctor(KeyFunction)`（`IL 113428-113444`）把 P1/P2/P3
全設 0。EKey 是「無參數純標記」。

### 韌體行為推斷
EKey 標記的實體鍵（position 0x00 = `LKP_GameMode`，`IL 112999`）是
GameMode 切換鍵。按下切換 PCMode ↔ GameMode；GameMode 下套用
`GameModeDisableKey` 的遮罩（停用 Win/Alt-Tab/Alt-F4 等）。

注意兩個層次的區別：
1. **keymap 裡的 function 0x05**：標記「這顆實體鍵是 EKey 開關」，
   存在 `Primary[0x00].Function = 0x05`。這是靜態標記，告訴韌體該鍵的角色。
2. **EKeyMode 全域狀態**：目前是 PCMode(0) 還是 GameMode(1)，
   走獨立的 `EKeyModeFeatureReport`（見下），不在 keymap 裡。

### EKey 相關獨立 feature report
- **`EKeyMode` enum**（`IL 105656-105663`）：
  - `PCMode = 0x00`
  - `GameMode = 0x01`
- **`EKeyModeFeatureReport`**（`IL 105668-105710`）：
  - `Command`（GeneralUsbMainCommand = `0x0B` EKeyMode，`IL 105333`）
  - `EKeyMode`（uint8，0 或 1）
  - `Reserved[9]`
- `Z12RGBHidDevice::SetEKeyMode(EKeyMode)`（`IL 107005-107040`）：
  發 `EKeyModeFeatureReport(subCmd=0(write), mode)` 經
  `SetAndGetFeature(..., 0x64)`。
- `Z12RGBHidDevice::GetEKeyMode(EKeyMode&)`（`IL 107043-`）：
  發 `EKeyModeFeatureReport(subCmd=1(read), ...)` 經
  `SetAndGetFeature(..., 5)`，讀回 EKeyMode 欄。

### GameMode 連動
GameMode 啟用時，以下鍵被遮罩（`GameModeDisableKey` flags，`IL 105719-105730`）：

| flag | 鍵 |
|------|----|
| 0x01 | ALT_TAB |
| 0x02 | TABKEY |
| 0x04 | CTRL_ESC |
| 0x08 | ALT_F4 |
| 0x10 | LSHIFTKEY |
| 0x20 | APPKEY |
| 0x40 | WINKEY |
| 0x7F | ALL |

透過 `GameModeDisableKeysRamFeatureReport`（MainCommand `0x0C`，`IL 105334`）
寫入；`WriteGameModeDisableKeysToRam` / `ReadGameModeDisableKeysFromRam`
（`IL 107088-` / `IL 107132-`）。注意 `ProfileUsbFeatureReport` 結構裡也有一個
`GameModeDisableKey DisableKeys` 欄位（`IL 103176`），是 profile 預設值；
RAM 版是執行期當前值。

### 與實機掃描的對照
`docs/keymap-scan-result.md` 記錄 position 0x00 回 `00 05 00 00 00`
（function 0x05，p1/p2/p3 全 0），與本 IL 分析完全一致：0x05 = EKey，
GameMode 切換鍵，無參數。先前掃描文件把它標為「GameMode 開關，
function 0x05 未還原」——**現已還原為 EKey**。

---

## 為何 0x04 / 0x05 的參數全 0

這兩個 function 是「實體鍵角色宣告」，不是「輸出動作」。對照其他 function：

| function | 角色 | 參數用途 |
|----------|------|----------|
| 0x00 KeyboardEmulation | 動作 | P1/P2/P3 描述要發什麼 HID 碼 |
| 0x02 Consumer | 動作 | P1/P2 描述 Consumer code |
| 0x03 MacroFunction | 動作 | P1=巨集編號、P2/P3=執行參數 |
| 0x04 FnKey | **角色** | 無（該鍵就是 FN 層修飾鍵本身） |
| 0x05 EKey | **角色** | 無（該鍵就是 GameMode 開關本身） |
| 0xFF Disable | 角色 | 無（停用） |

FnKey / EKey 的「行為」由韌體硬編碼，軟體只能：
- 把某顆實體鍵的 function 設成 0x04 / 0x05（改角色）；
- 透過獨立 feature report 讀寫 FnKey 停用狀態、EKeyMode、FNWIN 互換。

---

## Z12RGB.Defines 命名空間下的相關 enum（無其他遺漏 function 碼）

`EDispNetLib.Hardwares.Z12RGB.Defines` 命名空間下的型別（完整列表）：
`HidConsumerCode`、`HidKeyCode`、`KeyDefine`、`KeyFunction`、
`LedKeyPosition`、`LedZonePosition`、`Modifier`、`MouseWheelScroll`。

function 碼只存在於 `KeyFunction` enum（上面完整表），**沒有其他 enum
定義額外的 function 碼**。`Modifier` / `HidKeyCode` / `HidConsumerCode` /
`MouseWheelScroll` 是 0x00 / 0x02 / 0x03 / 0x06 function 的「參數值」空間，
不是 function 碼本身。

與 function 行為相關但位於 `EDispNetLib.Hardwares.Z12RGB`（非 Defines）
的 enum / report：
- `EKeyMode`（0x05 EKey 的模式狀態）
- `GameModeDisableKey`（0x05 GameMode 的遮罩 flags）
- `FNWINStatus`（0x04 FnKey / WIN 鍵角色互換狀態）
- `FeatureReportId`、`GeneralUsbMainCommand`、`GeneralUsbSubCommand`
  （report 4 的 command byte 值，與 function byte 不同層）

---

## 相關 IL 行號索引（Z12RGB）

| 項目 | IL 行號 |
|------|---------|
| `KeyFunction` enum 定義 | 113147–113179 |
| `KeyDefine` struct 定義 | 113365– |
| `KeyDefine::.ctor(Modifier, key1, key2)`（0x00） | 113378–113396 |
| `KeyDefine::.ctor(HidConsumerCode)`（0x02） | 113399–113422 |
| `KeyDefine::.ctor(KeyFunction)`（0x04/0x05/0xFF 等） | 113428–113444 |
| `KeyDefine::.ctor(macroNumber)`（0x03） | 113450– |
| `KeyDefine::CheckSum()` | 113510–113533 |
| `KeyDefine::ToString()`（switch 含 FN/E） | 113537–，case 4 @ IL_0957(36814)，case 5 @ IL_0962(36818) |
| `LedKeyPosition` enum（LKP_GameMode=0x00, LKP_FN=0x6c, LKP_WIN=0x68） | 112999, 113100, 113104 |
| `EKeyMode` enum（PCMode=0, GameMode=1） | 105656–105663 |
| `EKeyModeFeatureReport`（MainCmd 0x0B） | 105668–105710 |
| `GameModeDisableKey` enum（flags） | 105719–105730 |
| `GameModeDisableKeysRamFeatureReport`（MainCmd 0x0C） | 105740–105778 |
| `FNWINStatus` enum（WindowsL=0, FNL=1） | 105836–105842 |
| `GameModeKeysWinFnRamFeatureReport`（MainCmd 0x27） | 105846–105847 |
| `FnKeyStateFeatureReport`（MainCmd 0x30） | 105852–105895 |
| `GeneralUsbMainCommand` enum（FnKeyDisable=0x30, EKeyMode=0x0B, ...） | 105333, 105334, 105338, 105339 |
| `Z12RGBHidDevice::SetEKeyMode` | 107005–107040 |
| `Z12RGBHidDevice::GetEKeyMode` | 107043–107086 |
| `Z12RGBHidDevice::WriteGameModeDisableKeysToRam` | 107088– |
| `Z12RGBHidDevice::ReadGameModeDisableKeysFromRam` | 107132– |
| `Z12RGBHidDevice::SetFnKeyDisabled` | 107178–107226 |
| `Z12RGBHidDevice::GetFnKeyDisabled` | 107229– |
| `Z12RGBHidDevice::SetGameModeDisableKeysFNWINstatus` | 107278– |
| `Z12RGBHidDevice::WriteKeyFunctionToRam(KeyFunction)`（建 KeyDefine 再寫） | 106814–106831 |
| `Profile::SetKeyFunctionDefault`（跳過 0x68/0x6c） | 104185–104335，跳過 @ 104228–104235 |
| `Z12Macro::GetMacorData`（只認 Function==3） | 109257–，檢查 Function==3 @ 110414, 110474 |

---

## 對本專案的影響

1. **`docs/keymap-scan-result.md`** 裡 position 0x6C「未還原 function 0x04」
   和 position 0x00「未還原 function 0x05」現已還原：
   - 0x04 = FnKey（FN 層修飾鍵，無參數）
   - 0x05 = EKey（GameMode 切換鍵，無參數）
2. **`docs/key-position-table.md`** 的 0x6C 條目可標記 function 0x04=FnKey；
   0x00 條目可標記 function 0x05=EKey。
3. **`docs/profile-protocol.md`** 的 KeyFunction enum 表可補上完整 0x04–0x23
   成員（目前該檔只列了 0x00/0x02/0x03/0xFF 的語意）。
4. 實作 CLI 時，讀到 function 0x04 / 0x05 應顯示 "FnKey" / "EKey"
   （或 UI 字串 "FN" / "E"），且知道這兩個 position 不走標準 keymap 重映射，
   而是由獨立 feature report（FnKeyState / EKeyMode）控制相關狀態。
5. **不要嘗試把 0x04 / 0x05 的 Parameter 改成非 0 值**——軟體從不這樣做，
   韌體行為未知，屬於 AGENTS.md「未還原的指令禁止亂送 SET_REPORT」的範圍。