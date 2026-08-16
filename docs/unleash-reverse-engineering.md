# EVGA Unleash RGB `EDispNetLib.dll` 逆向分析（2026-08-16）

純靜態分析，不碰鍵盤、不送任何 HID 封包。來源：EVGA Unleash RGB
1.0.28.0 安裝目錄下的 `EDispNetLib.dll`（699720 bytes，.NET assembly）。

## 工具與方法

| 工具 | 用途 |
|------|------|
| `monodis`（Mono 6.14.1）+ `MONO_PATH=/tmp/refs` | 反編譯完整 IL 到 `/tmp/edisp_full.il`（9.6 MB）。第一次因缺 `EvgaCore.dll` 等 reference 而 segfault，把主目錄所有 dll 複製到 `/tmp/refs/` 再跑 `monodis --output=` 即成功。 |
| `.venv/bin/python` + `dnfile 0.18.0` | 解析 .NET metadata（枚舉值、欄位 signature、Constant 表、TypeDef/Field/MethodDef 對應）。 |
| `monodis /tmp/refs/EvgaCore.dll` | 反編譯 `EvgaCore.dll` 取 `MacroActionTypeEnum`、`Win32MouseKeys`（巨集動作來源型別）。 |

DLL 路徑目錄名是亂碼（含 control char），用 Python `glob`/`shutil.copy` 複製到
`/tmp/edisp_main.dll` 再分析。完整 IL 反編譯落檔於 `/tmp/edisp_full.il`（暫存）。

---

## 與硬體事實的對照（VID/PID 確認）

`EDispNetLib.Hardwares.Z12RGB.Z12RGB` 靜態常數（`/tmp/edisp_full.il` ~L105273）：

| 常數 | 值 | 對照實機 |
|------|----|----------|
| `VENDOR_ID` | `0x3842` | ✅ 一致 |
| `PRODUCT_ID` | `0x2612` | ✅ 一致 |
| `PRODUCT_ID_UK` | `0x2622` | UK 版本 |
| `PRODUCT_ID_IAP` | `0x2606` | firmware update (IAP) 模式 PID |
| `Header1` | `0xEA` | ✅ 與實機 report 4 `0xEA 0x02` 家族一致 |
| `Header2` | `0x02` | ✅ 同上 |

---

## 問題 1：FeatureReportId 枚舉

來源：`EDispNetLib.Hardwares.Z12RGB.FeatureReportId`（typedef #460，IL ~L105285）
與共用 `EDispNetLib.Hardwares.USBHID.Keyboard.Enums.FeatureReportId`（#1040，
IL ~L217463）。Z12 版本是共用版的子集（去掉 TOF 相關項目）。

### Z12RGB.FeatureReportId（byte 值）

| 名稱 | 值 | 對照實機 descriptor |
|------|----|---------------------|
| `Information` | `0x03` | report 3（未在我們 descriptor 重點清單，但存在） |
| `GeneralUsb` | `0x04` | ✅ report 4 = 17 B（keymap / E-key mode / 一般命令） |
| `LedTest` | `0x04` | 同 report 4（LED test 也走 GeneralUsb report） |
| `FirmwareUpdate` | `0x05` | report 5 = 265 B |
| `LedColorSetting` | `0x06` | ✅ report 6 = 32 B（五區 RGB，OpenRGB Z15 可移植） |
| `LedPreset` | `0x07` | report 7 = 136 B（LED preset / profile-in-RAM 共用 ID） |
| `ProfileInRAM` | `0x07` | 同 report 7 |
| `ProfileUsb` | `0x08` | report 8 = 265 B |
| **`MacroUsb`** | **`0x09`** | ✅ **report 9 = 265 B — 巨集本體走這裡** |
| **`MacroNameUsb`** | **`0x0A`** | ✅ **report 10 (0x0A) = 59 B — 巨集「名稱」走這裡** |
| `SWCustomizeData` | `0x0F` | report 15 (0x0F) = 264 B |

**結論**：report ID 全部對得上實機 descriptor。我們之前用 GET_FEATURE 找不到
巨集本體，是因為巨集本體走 **report 9 (0x09)**，而我們 GET report 9 時沒帶正確的
`MacroDirection`/`MacroIndex`/`PackIndex`（巨集是分封包讀的，見問題 8）。report
4 只放巨集「引用」（`KeyFunction.MacroFunction=0x03` + `Parameter1`=巨集編號）。

### 共用版多了的項目（Z12 沒有）

| 名稱 | 值 | 說明 |
|------|----|------|
| `TOFLightEffectRecord` | `0x04` | TOF（飛時測距）機種才有 |
| `TOFLightEffectRecordData` | `0x0B` | 同上 |
| `TOFLightEffectRecordName` | `0x0C` | 同上 |

---

## 問題 2：GeneralUsbMainCommand 枚舉

來源：`EDispNetLib.Hardwares.Z12RGB.GeneralUsbMainCommand`（#462，IL ~L105332）。
這是 report 4（`GeneralUsbCommand`）第 4 byte 的主命令。

| 名稱 | 值 | 用途 |
|------|----|------|
| `ReadFirmwareVersion` | `0x01` | 讀韌體版 |
| `ResetKeyboard` | `0x02` | 重置鍵盤 |
| `EraseApFirmware` | `0x03` | 擦 AP 韌體（IAP 用，**禁止使用**） |
| `EnterIapMode` | `0x04` | 進入 IAP（**禁止使用**） |
| `Profile` | `0x06` | profile 切換 |
| **`KeyFunctionRam`** | **`0x07`** | ✅ **按鍵映射讀寫（我們已實證）** |
| `ResetProfile` | `0x09` | 重置當前 profile |
| **`EKeyMode`** | **`0x0B`** | E-key 模式切換（PC/Game） |
| `GameModeDisableKeysRam` | `0x0C` | Game mode 禁用鍵 |
| **`SaveProfile`** | **`0x12`** | ✅ **存檔（我們已知）** |
| `ReadConfiguration` | `0x22` | 讀設定 |
| `KeyboardUSUKKey` | `0x26` | US/UK 鍵盤配置 |
| `GameModeDisableKeysFNWINstatus` | `0x27` | Game mode FN/WIN 狀態 |
| `FnKeyDisable` | `0x30` | FN 鍵停用 |
| `ResetToFactoryDefault` | `0x31` | 恢復原廠 |
| `KeyPositionInformationReport` | `0x33` | 按鍵位置資訊報告 |
| `ExternalFlashStatus` | `0x34` | 外部 flash 狀態 |
| `SleepMode` | `0x03` | 睡眠模式（註：值與 EraseApFirmware 衝突，由 SubCommand 區分） |

**巨集相關的 MainCommand**：巨集本體**不走 GeneralUsbMainCommand / report 4**。
巨集有自己獨立的命令體系，走 report 9（`MacroUsb`）與 report 10（`MacroNameUsb`），
header 同樣是 `0xEA 0x02`，但命令欄位是 `MacroDirection` 與 `MacroMainCommand`
（見問題 6/8）。report 4 只在「把某顆 E-key 設成播放第 N 號巨集」時用到
`KeyFunctionRam(0x07)` + `KeyDefine.Function = MacroFunction(0x03)` +
`KeyDefine.Parameter1 = 巨集編號`。

---

## 問題 3：GeneralUsbSubCommand 枚舉

來源：`EDispNetLib.Hardwares.Z12RGB.GeneralUsbSubCommand`（#463，IL ~L105348）。
report 4 的第 5、6 byte（`GeneralUsbSubCommand1`、`GeneralUsbSubCommand2`）。
這些是「語意隨主命令而定」的子命令，多個語意共用同一數值。

| 名稱 | 值 | 語意 |
|------|----|------|
| `None` | `0x00` | 無 |
| `IAP` | `0x00` | IAP 模式 |
| `AP` | `0x01` | AP 模式 |
| `SetProfile` | `0x00` | 設定 profile |
| `GetProfile` | `0x01` | 讀取 profile |
| **`Write`** | **`0x00`** | 寫入 |
| **`Read`** | **`0x01`** | 讀取 |
| `Default` | `0x02` | 讀預設值 |
| `PrimaryKeyAssignment` | `0x00` | 主鍵層（SubCommand1 用） |
| `SecondaryKeyAssignment` | `0x01` | Shift 層（SubCommand1 用） |
| `WriteDateTime` | `0x00` | 寫日期時間 |
| `ClearDateTime` | `0x10` | 清日期時間 |
| `Disable` | `0x00` | 停用 |
| `Enable` | `0x01` | 啟用 |

按鍵映射讀寫時：`SubCommand1 = PrimaryKeyAssignment(0x00)` 或
`SecondaryKeyAssignment(0x01)`（主層 / Shift 層），`SubCommand2 = Write(0x00)` 或
`Read(0x01)`（見 `KeyFunctionRamFeatureReport:.ctor`，IL ~L105637）。

---

## 問題 4：EKeyMode 枚舉 — 與實證的差異

來源：`EDispNetLib.Hardwares.Z12RGB.EKeyMode`（#470，IL ~L105652）與共用
`USBHID.Keyboard.Enums.EKeyMode`（#1039）。兩者完全相同。

| 名稱 | 值 |
|------|----|
| `PCMode` | `0x00` |
| `GameMode` | `0x01` |

**⚠️ 重要澄清**：這個 `EKeyMode` **不是**我們實證的「單顆 E-key 的 function 值」。
`EKeyMode` 是整把鍵盤的「E-key 模式開關」，走
`EKeyModeFeatureReport`（report 4，`GeneralUsbMainCommand.EKeyMode = 0x0B`），
只有 PC/Game 兩種。

我們實證的「function=0x03 是巨集播放、0x00 是單鍵、0xFF 是 disable」其實是
**`EDispNetLib.Hardwares.Z12RGB.Defines.KeyFunction`** 枚舉（typedef #493，
IL ~L105800 區段），那是 `KeyDefine.Function` 欄位（report 4 裡每顆鍵的 function
碼），對應如下：

| `Defines.KeyFunction` 名稱 | 值 | 對照我們實證 |
|---------------------------|----|--------------|
| `KeyboardEmulation` | `0x00` | ✅ 0x00 = 單鍵 |
| `ConsumerDeviceEmulation` | `0x02` | consumer 多媒體鍵 |
| **`MacroFunction`** | **`0x03`** | ✅ **0x03 = 巨集播放** |
| `FnKey` | `0x04` | |
| `EKey` | `0x05` | |
| `MouseWheelScroll` | `0x06` | |
| `MouseLeftClick` | `0x07` | |
| `MouseRightClick` | `0x08` | |
| `MouseWheelClick` | `0x09` | |
| `InformationReportKeyPosition` | `0x0B` | |
| `SystemControlReport` | `0x0C` | |
| `Profile1`–`Profile9` | `0x11`–`0x19` | 切換 profile 1–9 |
| `ProfileCyclePlus` | `0x1E` | profile 循環+ |
| `ProfileCycleMinus` | `0x1F` | profile 循環- |
| `IncreaseBrightness` | `0x20` | |
| `DecreaseBrightness` | `0x21` | |
| `IncreaseLightEffect` | `0x22` | |
| `DecreaseLightEffect` | `0x23` | |
| **`Disable`** | **`0xFF`** | ✅ **0xFF = disable** |

`KeyDefine` 結構（typedef #498，IL ~L105808）：`Function:KeyFunction` +
`Parameter1:byte` + `Parameter2:byte` + `Parameter3:byte`（3 bytes 參數）。
巨集播放時 `Function=MacroFunction(0x03)`、`Parameter1=巨集編號(1-based)`。

---

## 問題 5：ResponseCommand 枚舉

來源：`EDispNetLib.Hardwares.Z12RGB.ResponseCommand`（#461，IL ~L105311）與
共用 `USBHID.Keyboard.Enums.ResponseCommand`（#1045）。兩者相同。

| 名稱 | 值 | 對照實證 |
|------|----|----------|
| **`Success`** | **`0xC0`** | ✅ 0xC0 = 成功 |
| **`Fail`** | **`0xC1`** | ✅ 0xC1 = 不支援 / 失敗 |
| `InProcess` | `0xC2` | 處理中（長操作輪詢用） |

確認與實證一致。程式碼中多處用 `ldc.i4 192`（0xC0）/`ldc.i4 193`（0xC1）比對
`ResponseCommand` 欄位判斷成敗（例如 `Z12Macro.LoadMapping` IL ~L109052、
`Z12Macro.SaveMacro` 建構 `MacroUsbFeatureReport` 時預設 `ResponseCommand=0xC1`）。

---

## 問題 6：巨集封包結構

巨集相關型別全在 `EDispNetLib.Hardwares.Z12RGB` 命名空間。**這是 Z12 專屬實作**，
不是 Z5/Z20 那套（Z5/Z20 有各自的 `MacroFunction`/`MacroDataDefine` 等，結構相似
但 report 長度不同）。

### 6.1 命令頭 `MacroCommand`（typedef #436，IL ~L98053）

`sequential` struct，`.pack 1`，欄位順序即封包位元組順序：

| offset | 欄位 | 型別 | `.ctor` 設定值 |
|--------|------|------|----------------|
| 0 | `ReportId` | byte | **`0x09`**（`MacroUsb`） |
| 1 | `Header1` | byte | **`0xEA`** |
| 2 | `Header2` | byte | **`0x02`** |
| 3 | `Command` | `MacroDirection` | 由參數傳入（Write=0x02 / Read=0x01） |
| 4 | `MacroIndex` | byte | 由參數傳入（1-based 巨集編號） |
| 5 | `Reserved` | byte | `0x00` |
| 6 | `ResponseCommand` | `ResponseCommand` | 由參數傳入 |

`MacroDirection` 枚舉（typedef #430）：`Read=0x01`、`Write=0x02`。

### 6.2 `MacroUsbFeatureReport`（typedef #437，IL ~L98087）— 記憶體中的完整巨集模板

這是**在記憶體中組裝的完整巨集記錄**，serialize 成 byte 陣列後再分封包送出
（不是直接當一個 HID report 送，因為它遠大於 265 B）。欄位：

| 欄位 | 型別 | `.ctor` 預設 |
|------|------|--------------|
| `Command` | `MacroCommand` | 見上（report 9, 0xEA 0x02, Direction, MacroIndex, 0xC1） |
| `CheckSum` | byte | 0（之後 `CalculateCheckSum()` 算） |
| `LengthOfMacroName` | byte | 0 |
| `MacroName` | byte[**50**] | `new byte[0x32]` |
| `RunMethodOfMacro` | `RunMethodOfMacro` | 0 |
| `RepeatTimeOfMacro` | byte | 0 |
| `TimeUnitOfMacro` | byte | 0 |
| `LengthOfMacroData` | uint16 | 0 |
| `MacroData` | byte[**967**] | `new byte[967]`（0x3C7） |
| `MacroStatusOfUse` | byte | 0（寫入時設 1=使用中、0xFF=刪除） |

`RunMethodOfMacro` 枚舉（typedef #431，IL ~L97990 區段）— 巨集播放模式：

| 名稱 | 值 |
|------|----|
| `Looping_KeyRelease` | `0x00` |
| `OneShot_KeyRelease` | `0x01` |
| `MultiStage_KeyRelease` | `0x02` |
| `Repeat_KeyRelease` | `0x03` |
| `TwoPhase` | `0x04` |
| `Looping_KeyPress` | `0x08` |
| `OneShot_KeyPress` | `0x09` |
| `MultiStage_KeyPress` | `0x0A` |
| `Repeat_KeyPress` | `0x0B` |
| `Hold` | `0x0C` |
| `Invalid` | `0xFF` |

`MacroDataDefine` 靜態常數（typedef #432，IL ~L97965）— 各種長度上限：

| 常數 | 值 | 意義 |
|------|----|------|
| `MacroReportLength` | `0x0408` (1032) | 完整 MacroUsbFeatureReport 序列化長度 |
| `MacroDataLength` | `0x03C7` (967) | `MacroData[]` 長度 |
| `MacroNameLength` | `0x0032` (50) | `MacroName[]` 長度 |
| `SoftwareCount` | `0x005A` (90) | 軟體巨集數上限 |
| `HardwareCount` | `0x000A` (10) | 硬體巨集數上限 |
| `TotalCount` | `0x0064` (100) | 總巨集數 |

> 90 軟體 + 10 硬體 = 100。1-based 編號 1..100。`Z12Macro.get_UserMacroCount`
> 回傳軟體可用數。

### 6.3 `MacroData`（typedef #487，IL ~L108180）— report 9 的實際分封包

這才是**實際透過 HID report 9 送出/讀取的封包**，每包帶 256 B payload。欄位：

| offset | 欄位 | 型別 | `.ctor(direction, macroIndex)` 設定 |
|--------|------|------|--------------------------------------|
| 0 | `ReportId` | byte | **`0x09`** |
| 1 | `Header1` | byte | **`0xEA`** |
| 2 | `Direction` | `MacroDirection` | 參數（Read=0x01/Write=0x02） |
| 3 | `Command` | `MacroMainCommand` | **`0x01` = Data**（`.ctor` 寫死 `ldc.i4.1`） |
| 4 | `MacroIndex` | byte | 參數 |
| 5 | `PackIndex` | byte | 封包序號（0,1,2,3）— 送時遞增 |
| 6 | `ResponseCommand` | `ResponseCommand` | 鍵盤回應填入 |
| 7 | `Checksum` | byte | `CalculateCheckSum()` 算 |
| 8..263 | `Data` | byte[**256**] | `marshal (fixed array [256])` |
| 264 | `Reserved` | byte | |

`MacroMainCommand` 枚舉（typedef #485）：`Status=0x00`、`Data=0x01`。
`MacroData` 只用 `Data(0x01)`；`Status(0x00)` 給 `MacroStatus` 用（見下）。

`MacroData.CalculateCheckSum()`（IL ~L108228）：`Checksum = -(sum of Data[0..255]) & 0xFF`。
即 Data 256 bytes 總和的負數 low byte。

> Report 9 descriptor 長度 265 B = ReportId(1) + Header1(1) + Direction(1) +
> Command(1) + MacroIndex(1) + PackIndex(1) + ResponseCommand(1) + Checksum(1) +
> Data[256] + Reserved(1) = 265。✅ 完全對上。

### 6.4 `MacroStatus`（typedef #486，IL ~L108110）— 查詢巨集使用狀態

| offset | 欄位 | 型別 | `.ctor(command)` 設定 |
|--------|------|------|------------------------|
| 0 | `ReportId` | byte | **`0x09`** |
| 1 | `Header1` | byte | **`0xEA`** |
| 2 | `Direction` | `MacroDirection` | 參數（用 `Read=0x01` 查詢） |
| 3..265 | `Status` | byte[**263**] | `marshal (fixed array [263])` — 位元陣列：`Status[i]==1` 表示巨集編號 (i+1) 已使用 |

> 1 + 1 + 1 + 263 = 266；report 9 是 265 B（含 ReportId），即 payload 264 B。
> `Direction` 佔 1 B、`Status[263]`。實際位元陣列從 offset 3 開始，程式碼從
> `Status[8]`（即整體 offset 11）起逐 byte 檢查 `==1`（`Z12Macro.LoadMapping`
> /`CleanAllMacroStatus`：`ldc.i4.8 stloc.2` 起始，`ldc.i4.s 0x6b`(107) 結束），
> 對應巨集編號 1..100。

### 6.5 `MacroNameData`（typedef #488，IL ~L108270）— report 10，巨集名稱

| offset | 欄位 | 型別 | `.ctor(direction, macroIndex)` 設定 |
|--------|------|------|--------------------------------------|
| 0 | `ReportId` | byte | **`0x0A`** |
| 1 | `Header1` | byte | **`0xEA`** |
| 2 | `Header2` | byte | **`0x02`** |
| 3 | `Direction` | `MacroDirection` | 參數 |
| 4 | `MacroIndex` | byte | 參數 |
| 5 | `RaversedByte5` | byte | `0x00`（命名拼錯 "Reversed"） |
| 6 | `ResponseCommand` | `ResponseCommand` | 預設 **`0xC1`**（Fail） |
| 7 | `Checksum` | byte | 0 |
| 8 | `NameCount` | byte | 0 |
| 9..58 | `Data` | byte[**50**] | `marshal (fixed array [50])` — UTF-8 名稱 |

> Report 10 (0x0A) descriptor = 59 B = 1..8 欄位(9) + Data[50] = 59。✅ 對上。
> 名稱用 UTF-8 編碼（`LoadMapping` 用 `Encoding.UTF8.GetString`），並把
> `bytearray(00 00 00)`（null terminator 系列）replace 成空字串。

### 6.6 `MacroNameStatusFeatureReport`（typedef #489）

只包一個 `MacroStatus Command` 欄位（class）。是 `MacroStatus` 查詢的 wrapper。

### 6.7 巨集本體編碼：`Z12Macro.GetMacorData`（IL ~L109260，1699 B 程式碼）

這是把 `List<MacroAction>` 編碼成 `MacroUsbFeatureReport.MacroData[]` 的核心。
來源動作型別是 `EvgaCore.DataStruct.MacroAction`，其
`MacroActionTypeEnum`（`/tmp/evgacore.il` ~L3526）：

| MacroActionType | 值 |
|-----------------|----|
| `None` | 0 |
| `Start` | 1 |
| `MouseToZero` | 2 |
| `MouseToCurrent` | 3 |
| `MouseMove` | 4 |
| `MouseDown` | 5 |
| `MouseUp` | 6 |
| `MouseWheel` | 7 |
| `KeyDown` | 8 |
| `KeyUp` | 9 |

`Win32MouseKeys`（flags，`/tmp/evgacore.il` ~L3910）：`Left=0x02`、
`Right=0x08`、`Middle=0x20`。

`GetMacorData` 對每個 action 先寫「延遲」再寫「動作」。編碼成 byte 串（tag-based）：

#### 延遲編碼（每個 action 開頭）

| 條件 | 寫入 bytes | 意義 |
|------|-----------|------|
| `TimeSpan.TotalMs > 0` | `0x01`, `ms & 0xFF`, `(ms >> 8) & 0xFF` | tag 0x01 + 16-bit LE 毫秒延遲 |
| `TimeSpan.TotalMs <= 0` | `0x04`, `0x00` | 無延遲標記 |

> 上限檢查：寫入位置 `>= 964` 就 throw `MacroFullException`（967 - 3 bytes 餘裕）。

#### 動作編碼（依 MacroActionType 的 switch，`type - 2`）

| MacroActionType | 寫入 bytes | 說明 |
|-----------------|-----------|------|
| `MouseToZero` (2) | `0x80, 0xD0, 0x8A, 0xD0, 0x8A` | 5 B 固定序列（游標歸零） |
| `MouseToCurrent`/`MouseMove` (3,4) | `0x80, Xlo, Xhi, Ylo, Yhi` | 5 B，X/Y 各 16-bit LE |
| `MouseDown` (5) | `0x7A`(Left) / `0x7B`(Right) / `0x7C`(Middle) | 1 B |
| `MouseUp` (6) | `0xFA`(Left) / `0xFB`(Right) / `0xFC`(Middle) | 1 B |
| `MouseWheel` (7) | `0xF8`(Delta>0) / `0x78`(Delta<=0) | 1 B |
| `KeyDown` (8) | 見下 | 鍵盤按下 |
| `KeyUp` (9) | 見下 | 鍵盤放開 |

#### 鍵盤按鍵編碼（KeyDown=8 / KeyUp=9，IL ~L109710 / ~L110240）

按鍵**不是直接放 HID usage code**，而是經過 Windows VirtualKeyCode / ScanCode
轉換，有三條路徑（優先序如下）：

1. **NumLock/方向鍵等擴充鍵**（`Flags & 1` 且 ScanCode 屬於 keypad/方向鍵範圍）：
   先把 ScanCode 對應到一個 keypad HID-usage byte（如 `0x49`–`0x58`、`0x46`、
   `0x53`、`0x54` 等），寫成**單一 byte**。NumLock 切換時的 Ctrl/Alt
   (ScanCode 0x1D/0x38 + VK 0xA3/0xA5) 會被改寫成 extended code 57373/57400。

2. **ScanCode → VirtualKeyCode 一對一表**
   (`MacroFunctionBase.get_ScanCodeToVirtualKeyCode`，`Dictionary<byte,byte>`)：
   若 ScanCode 在表中且 `ScanCode == extendedScanCode`，寫**單一 VK byte**。

3. **ScanCode → VirtualKeyCode 二號表**
   (`get_ScanCodeToVirtualKeyCode2`，`Dictionary<uint,byte>`，key 是 32-bit
   extended scan code)：寫**單一 VK byte**。

4. **VirtualKeyCode → HID usage**
   (`Z12Macro.get_VirtualKeyCodeToHidUsageMapping2`，`Dictionary<byte,ushort>`)：
   寫 **`0x03` + usageLo + usageHi**（3 bytes，16-bit LE HID usage）。
   這是 fallback：當 VK 對應到一個 >255 的 HID usage（多媒體/系統鍵）時用。

**結論**：巨集裡的按鍵編碼是 **Windows VirtualKeyCode 為主**（單 byte），
少數鍵用 **`0x03` + 16-bit HID usage**。**不是純 HID usage code**。修飾鍵
（Ctrl/Alt/Shift/Win）的 HID modifier 位元在 `Defines.Modifier` 枚舉
（typedef #494）：`LeftCtrl=0x01`、`LeftShift=0x02`、`LeftAlt=0x04`、
`LeftGUI=0x08`、`RightCtrl=0x10`、`RightShift=0x20`、`RightAlt=0x40`、
`RightGUI=0x80`（標準 HID modifier bitmap）。巨集編碼中修飾鍵當成獨立按鍵動作
（按下/放開各一個 VK byte），不走 modifier bitmap。

> ⚠️ 對 macOS 工具的影響：因為巨集存的是 VK/scan code，跨平台解碼需要一份
> VK→HID usage 對應表。`Z12Macro` 的 `VirtualKeyCodeToHidUsageMapping2` 是
> 在 `.cctor`（靜態建構）裡硬編的 `Dictionary<byte,ushort>`（IL ~L99002 區段
> 起大量 `ldc.i4`/`stfld`）。要完整還原需把該 dictionary 的所有 entry 抽出來。

---

## 問題 7：Z12RGBHidDevice 類別

來源：`EDispNetLib.Hardwares.Z12RGB.Z12RGBHidDevice`（typedef #484，
IL ~L106368）。

- **繼承**：`extends [mscorlib]System.Object`（直接繼承 Object，**不是**繼承
  共用 `HidDevice`）。typedef 顯示 `extends=0x4d`（TypeRef Object）。
- **委派**：內含 `private initonly IHidDevice _hidDevice`。VID/PID/Version
  都是 `get_VendorId`/`get_ProductId`/`get_VersionNumber` 去呼叫
  `_hidDevice.get_VendorId()` 等（IL ~L106384/106407/106422）。**VID/PID 不在
  這個類別硬編**，硬編在 `Z12RGB` 靜態常數類（見文首）。
- **欄位**：`_hidDevice`、`_primaryDefaultKeyDefines:KeyDefine[]`、
  `_secondaryDefaultKeyDefines:KeyDefine[]`。
- **ctor**：`Z12RGBHidDevice(IHidDevice hidDevice)` 只把傳入的 hidDevice 存起來。
- **方法**（44 個，typedef #484 method list）：firmware（ReadIap/ReadAp/
  Erase/EnterIap）、`ReadDefaultKeyFunction`、`ReadKeyFunctionFromRam`、
  `WriteKeyFunctionToRam`（多個 overload）、`SetEKeyMode`/`GetEKeyMode`、
  `Write/ReadGameModeDisableKeys`、`Set/GetFnKeyDisabled`、
  `SetGameModeDisableKeysFNWINstatus`、`ResetToFactoryDefault`、
  `Set/GetKeyPositionInformationReport`、`ReadConfiguration`、
  `GetExternalFlashStatus`、`Set/GetKeyboardUSUKStatus`、`WriteKeyFunction`/
  `ReadKeyFunction`、`Set/GetSWCustomizeDataCommand`、`Get/SetSleepMode`、
  `SetSleepModeDefault`。
- **沒有巨集方法**：巨集讀寫不在 `Z12RGBHidDevice`，而在 `Z12Macro`
  （typedef #490，`extends EDispNetLib.Hardwares.MacroFunctionBase`）。
  `Z12RGBHidDevice` 只負責 report 4 那層（keymap/EKeyMode/profile/LED）。

### 與 Z15/Z20 比較

Z15/Z20 用 `Z15RGBUK`/`Z20RGB` 命名空間，各有自己的 `FeatureReportId`、
`GeneralUsbMainCommand`、`MacroUsbFeatureReport` 等。結構同名但 report 長度不同
（例如 Z20 的 `MacroUsbFeatureReport` `MacroData` 長度不同）。**不可把 Z15/Z20
的 report 9 封包原封不動丟給 Z12**（與 AGENTS.md 規則 4 一致）。命令碼
（MainCommand 0x07=keymap、0x12=save、Header 0xEA 0x02、Response 0xC0/0xC1）
在 Z12/Z15/Z20 之間一致，因為都來自共用的 `USBHID.Keyboard.Enums`。

---

## 問題 8：巨集讀寫完整流程

從 `Z12Macro`（typedef #490，IL ~L108359 起）的方法推斷。底層送收是
`MacroFunctionBase.ExecuteReport<T>(ref T report, int timeSpanMs)`（IL ~L1594），
它呼叫 `IHidDevice.SetAndGetFeature<T>(ref report, timeSpan)` — 即
**SET_FEATURE 再 GET_FEATURE**（一次來回）。timeSpan 多處用 `150` ms。

### 8.1 寫入巨集：`Z12Macro.SaveMacro(name, actions)`（IL ~L109137）

1. `idx = GetMacroIndex(name)`；若 `idx < 1`，呼叫 `CreateMacro(name)` 找一個
   1..UserMacroCount 之間沒用過的編號；仍 < 1 回傳 false。
2. 組 `MacroUsbFeatureReport`（記憶體模板）：
   `new MacroUsbFeatureReport(MacroDirection.Write=2, idx, ResponseCommand.Fail=0xC1)`。
3. `SetName(name)`、`MacroStatusOfUse = 1`（標記使用中）。
4. `GetMacorData(actions, report.MacroData, MacroData.Length-1)` 把動作編碼進
   `MacroData[967]`，回傳 `LengthOfMacroData`（uint16，實際編碼長度）。
5. `report.CalculateCheckSum()`。
6. `serialized = StructToByteArrayConverter.Serialize(report)`（整個 1032 B 模板
   序列化成 byte[]）。
7. 分封包送出（最多 4 包，每包 256 B）：
   - `md = new MacroData(MacroDirection.Write=2, idx)`（report 9, 0xEA,
     Command=Data=0x01, MacroIndex=idx, Data[256]）。
   - 迴圈 `packIndex = 0..3`（`blt IL_007b`，`< 4`）：
     `md.PackIndex = packIndex`；
     `Buffer.BlockCopy(serialized, srcOffset=8 + packIndex*256, md.Data, 0, 256)`
     （從 serialized offset 8 起跳過前 8 byte header，每包拷 256 B）；
     `md.CalculateCheckSum()`；
     `ExecuteReport<MacroData>(ref md, 150)`；成功才前進 `srcOffset`。

   > 4 × 256 = 1024 B payload；加上 8 byte header = 1032 = `MacroReportLength`。✅
   > 即一個巨集最多佔 1024 B 動作資料（`MacroDataLength 967` 是 `MacroData[]`
   > 本身，序列化時 `MacroData[]` 之外還有 name/runmethod 等，總 1032）。

8. 任一包失敗就中斷，回傳 false；全部成功回傳 true。

### 8.2 讀取巨集名稱與索引：`Z12Macro.LoadMapping(...)`（IL ~L109037）

1. `GerDefKeyMapping()`。
2. `st = new MacroStatus(MacroDirection.Read=1)`（report 9, 0xEA, Direction=Read）。
3. `ExecuteReport<MacroStatus>(ref st, 150)` — 送 Read，鍵盤回填 `Status[263]`
   位元陣列。
4. `serialized = Serialize(st)`；從 `serialized[8]` 起逐 byte（`i = 8..0x6B`）：
   若 `serialized[i] == 1` → 巨集編號 `macroIdx = i - 7` 已使用。
5. 對每個已使用的 `macroIdx`：
   - `nd = new MacroNameData(MacroDirection.Read=1, macroIdx)`（report 10,
     0xEA 0x02）。
   - `ExecuteReport<MacroNameData>(ref nd, 0x32=50)`；檢查
     `nd.ResponseCommand == 0xC0`(Success) 且 `nd.NameCount != 0xFF`。
   - `name = Encoding.UTF8.GetString(nd.Data)`，replace null 結尾。
   - 把 `(macroIdx → name)` 與 `(name → macroIdx)` 建進兩個 dictionary。

> **這就是為什麼我們純 GET_FEATURE report 9 讀不到巨集本體**：讀巨集本體要先
> 用 report 9 `MacroStatus`(Direction=Read, **無 Command=Data 欄位**) 查哪些
> 編號有巨集，再對每個編號用 report 9 `MacroData`(Direction=Read, Command=Data,
> PackIndex=0..3) 分 4 包讀 256 B 拼回。report 10 讀名稱。我們之前 GET report 9
> 沒帶 Direction/Command/MacroIndex/PackIndex，自然只讀到全 0 或不支援。

### 8.3 讀取巨集本體（推斷，未在 SaveMacro 之外看到獨立 LoadMacroByIndex IL）

`Z12Macro` 方法列表有 `LoadMacro`、`LoadMacroByIndex`、`SaveMacro`。讀取流程
依封包對稱性為：
- `MacroData(Read=1, macroIdx)`，`PackIndex` 0..3，逐包 `ExecuteReport`，
  鍵盤回填 `Data[256]` + `ResponseCommand`；拼 4 包 × 256 B 得 1024 B，
  反序列化成 `MacroUsbFeatureReport`，取 `MacroData[]` 前 `LengthOfMacroData` B
  即動作串，再依 6.7 的 tag 解碼。
- `Z12Macro.ReadProfile256ByteLoop(indexOfProfile, ref List<byte>)`（IL ~L110668 區段）
  是 profile 的 256 B 分包讀取（report 7/8），結構類似。

### 8.4 刪除巨集：`Z12Macro.DoDeleteMacro(macroIndex)`（IL ~L110490）

1. `if (!IsMacro) return false`。
2. `if (macroIndex <= 0) return false`。
3. `r = new MacroUsbFeatureReport(Write=2, macroIndex, Fail=0xC1)`。
4. `r.MacroStatusOfUse = 0xFF`（**刪除標記**）、`LengthOfMacroData = 0`、
   `LengthOfMacroName = 0`。
5. `r.CalculateCheckSum()`。
6. `ExecuteReport<MacroUsbFeatureReport>(ref r, 150)` 回傳結果。

> ⚠️ 注意：`DoDeleteMacro` 送的是 `MacroUsbFeatureReport`（記憶體模板）直接當
> report 送，**不是**分封包。這與 `SaveMacro`（分 4 包 `MacroData`）不同。
> 推測：刪除只需 header + status=0xFF，payload 全 0，鍵盤認 header 即可；
> 而 `MacroUsbFeatureReport` 序列化後 header 部分（前 8 B）與 `MacroData` 的
> 前 8 B 欄位佈局相容（ReportId/Header1/Header2/Direction/Command/MacroIndex/...）。
> **這點需實機驗證前先用 GET_FEATURE 確認 report 9 對短封包的接受度**，目前
> 僅從 IL 推斷。

### 8.5 清除全部巨集：`Z12Macro.CleanAllMacroStatus()`（IL ~L110580）

1. `st = new MacroStatus(Read=1)`；`ExecuteReport<MacroStatus>` 取使用狀態。
2. 對每個 `serialized[i]==1` 的 `macroIdx = i-7`：
   - 組 `MacroUsbFeatureReport(Write=2, macroIdx, Fail=0xC1)`，`SetName("")`、
     `MacroStatusOfUse=0xFF`、`LengthOfMacroData=0`、`CalculateCheckSum()`。
   - 組 `MacroData(Write=2, macroIdx)`，`PackIndex=0`，把
     `Serialize(report)` 從 offset 8 拷 256 B 進 `md.Data`，`CalculateCheckSum()`，
     `ExecuteReport<MacroData>`。
3. 與 `DoDeleteMacro` 的差異：`CleanAllMacroStatus` 走分封包路徑（較保守）。

### 8.6 巨集綁定到 E-key（report 4 路徑）

`Z12Macro.GetMacroBindingList()`（IL ~L110360 區段）顯示：讀 keymap 時，對每個
key position 用 `KeyFunctionRamFeatureReport(ReadWrite=Read, PrimarySecondary,
LedKeyPosition, KeyDefine)`（report 4, MainCommand=KeyFunctionRam=0x07）讀回
`KeyDefine`；若 `KeyDefine.Function == MacroFunction(0x03)`，取
`KeyDefine.Parameter1` 為巨集編號，查名稱。即**綁定巨集到鍵 = 設該鍵的
`KeyDefine{Function=0x03, Parameter1=巨集編號, Parameter2=0, Parameter3=0}`**，
走 report 4 的 keymap 寫入（我們已實證的 0x07 路徑）。

---

## 對專案的具體結論

1. **巨集本體走 report 9 (0x09)，不是 report 4/5/6/7/8/0x0F**。我們之前
   GET_FEATURE 找不到是正常的 — report 9 巨集要分封包讀（先 `MacroStatus`
   查使用狀態，再 `MacroData` PackIndex 0..3 各讀 256 B）。
2. **report 10 (0x0A) 是巨集名稱**（50 B UTF-8）。
3. **協定家族 `0xEA 0x02` 在 report 9/10 同樣成立**（`MacroCommand.ctor` 與
   `MacroNameData.ctor` 都寫死 Header1=0xEA、Header2=0x02）。
4. **巨集本體是 Windows VK/scan-code 編碼**，不是純 HID usage。多數鍵是單 VK
   byte，少數多媒體/系統鍵是 `0x03` + 16-bit HID usage。跨平台工具需建 VK→HID
   對應表（可從 `Z12Macro.cctor` 的 dictionary 初始化 IL 抽出）。
5. **巨集最多 100 個**（90 軟體 + 10 硬體），1-based 編號。每個巨集動作資料
   上限 ~964 B（`MacroDataLength 967` 扣 3 B 餘裕）。
6. **刪除巨集 = report 9 送 `MacroStatusOfUse=0xFF`**；**寫入 = report 9 分
   4 個 `MacroData` 封包**（PackIndex 0..3，每包 256 B payload + checksum）。
7. **ResponseCommand 0xC0=成功、0xC1=失敗、0xC2=處理中**（與實證一致）。
8. `Z12RGBHidDevice` 不含巨集邏輯；巨集全在 `Z12Macro`（繼承
   `MacroFunctionBase`，後者提供 `ExecuteReport`/`CreateMacro`/`GetMacroIndex`
   /`ScanCodeToVirtualKeyCode` 等共用方法）。

### 下一步建議（純讀取驗證，遵守 AGENTS.md 規則）

- 先用 GET_FEATURE 送 report 9 `MacroStatus(Direction=Read)`（無 MacroIndex）
  讀 `Status[263]` 位元陣列，確認哪些巨集編號有資料 — 這是唯讀、低風險。
- 再對某個已使用編號送 report 9 `MacroData(Direction=Read, MacroIndex=N,
  PackIndex=0)`，看 `ResponseCommand` 是否回 0xC0 與 `Data[256]`。
- report 10 `MacroNameData(Direction=Read, MacroIndex=N)` 讀名稱。
- 以上皆為 GET_FEATURE / SET_FEATURE-with-Read-direction，未還原寫入前不送
  `Write` direction（遵守規則 1：未還原指令禁止 SET_REPORT；同一方法失敗兩次
  就停）。

### 已確認的協定常數（可寫進原始碼，對得上 research.md 實機擷取）

| 常數 | 值 | 來源 |
|------|----|------|
| VID | `0x3842` | `Z12RGB.VENDOR_ID` |
| PID | `0x2612` | `Z12RGB.PRODUCT_ID` |
| Header1 | `0xEA` | `Z12RGB.Header1` / `MacroCommand.ctor` / `GeneralUsbCommand.ctor` / `MacroNameData.ctor` |
| Header2 | `0x02` | `Z12RGB.Header2` / 同上 |
| Report MacroUsb | `0x09` | `FeatureReportId.MacroUsb` / `MacroCommand.ctor` / `MacroData.ctor` / `MacroStatus.ctor` |
| Report MacroNameUsb | `0x0A` | `FeatureReportId.MacroNameUsb` / `MacroNameData.ctor` |
| MacroDirection.Read | `0x01` | `MacroDirection` |
| MacroDirection.Write | `0x02` | `MacroDirection` |
| MacroMainCommand.Status | `0x00` | `MacroMainCommand` |
| MacroMainCommand.Data | `0x01` | `MacroMainCommand` / `MacroData.ctor` |
| ResponseCommand.Success | `0xC0` | `ResponseCommand` |
| ResponseCommand.Fail | `0xC1` | `ResponseCommand` |
| ResponseCommand.InProcess | `0xC2` | `ResponseCommand` |
| KeyFunction.MacroFunction | `0x03` | `Defines.KeyFunction` |
| KeyFunction.Disable | `0xFF` | `Defines.KeyFunction` |
| MacroData payload | 256 B/pack × 4 pack | `MacroData.Data[256]` / `SaveMacro` 迴圈 |
| MacroName | 50 B UTF-8 | `MacroNameData.Data[50]` / `MacroNameLength` |
| MacroReportLength | 1032 | `MacroDataDefine.MacroReportLength` |