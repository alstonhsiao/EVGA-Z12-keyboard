# EVGA Z12 Profile 讀寫協定（靜態反編譯結果）

來源：EVGA Unleash RGB 1.0.28.0 的 `EDispNetLib.dll`，以 `monoodis`
反編譯為 `/tmp/edisp_full.il`（9.6 MB, 218363 行）後做純靜態分析。
**未對鍵盤送任何封包。** 所有結構、欄位、常數都標注 IL 行號。

命名空間：`EDispNetLib.Hardwares.Z12RGB`（Z12 專屬，與 Z5/Z15/Z20 並列）。

---

## TL;DR — 10 題答案

1. **ProfileNumberFeatureReport（report 4, 17 B）**：走 `04 EA 02 06 <subcmd> <profileNum> + 9B reserved`。
   `MainCommand=0x06 (Profile)`，`SubCommand1` = `0x00`(SetProfile)/`0x01`(GetProfile)，profile 編號在 **byte[5]**。ResponseCommand 必須是 `0xC0`(Success)。
2. **SaveProfileFeatureReport（report 4, 17 B）**：`04 EA 02 12 00 00 <profileNum> + 9B reserved`。MainCommand=`0x12`，SubCommand 兩個都是 `0x00`，**有帶 profile 編號**（ctor 參數 `profileNumber`）。
3. **ResetProfileFeatureReport（report 4, 17 B）**：`04 EA 02 09 00 00 <profileNum> + 9B reserved`。MainCommand=`0x09` (ResetProfile)。
4. **ProfileReadWrite enum**：`Read = 0x01`、`Write = 0x02`（report 8 分包用，**跟 ProfileFunction 不同**）。
5. **ProfileFunction enum**：`Write = 0x00`、`Read = 0x01`（report 8 主檔頭用）。
6. **ProfileUsbFeatureReport（report 8, 265 B）**：整個 profile 的主結構。開頭是 `ProfileCommand`（report 7 風格 `07 EA 02 <func> <profileNum> <resv>`），後面跟 CheckSum、ProfileName(126)、GameModeDisableKey、ReportRate、Reserved(126)、Primary[121]、Secondary[121]、Reserved1(56)、LedMain/LedSubMode、Reserved2(30)、各 LED 模式段。讀取 = 發 `Read(0x01)+profileNum` 再 `SetAndGetFeature`；寫入 = 發 `Write(0x00)+profileNum` 再 `SetAndGetFeature`。另有 `ProfileUsbFeatureReport256` 分包（256 B × 6，loop count = 6）。
7. **ProfileInRamUsbFeatureReport（report 7, 136 B）**：是「目前 RAM 中 profile 的單一 LED 模式參數」即時讀寫通道（MainCommand 0x0B-0x13 各 LED 模式），**不是整個 profile**。跟 report 8 的差別：report 8 = onboard storage 的整組 profile（含 keymap+LED 全部）；report 7 = 當前 RAM 中單一 LED 模式的 128 B 參數。
8. **Profile 邏輯類別流程**：`get_ProfileIndex` 先發 `ProfileNumberFeatureReport(GetProfile)` 拿當前 profile 編號 → 若 dict 沒有就 `ReadProfile()`。`ReadProfile(idx)` 發 `ProfileUsbFeatureReport(Read, idx)` 一次拿整組。`WriteProfile(idx)` 從 dict 取出、設 `Command=Write`、`CalculateCheckSum`、再 `SetAndGetFeature`。Profile 內容 = ProfileName + GameModeDisableKey + ReportRate + **Primary keymap[121] + Secondary keymap[121]** + LED 主/副模式 + 7 個 LED 模式參數段（StaticOn/Breathing/Pulse/RainbowWave/Trigger/StarShining，**無巨集本體**）。巨集綁定走 report 4 KeyFunctionRam（MainCommand 0x07），巨集本體走 report 9/10，不在 profile 內。
9. **9 組 profile 存儲**：profile 1–9 存在鍵盤 onboard storage，用 report 8 (`ProfileUsbFeatureReport`) 以 `ProfileNumber` 欄位定址讀寫。切換 = report 4 `ProfileNumberFeatureReport(SetProfile=0x00, profileNum)`（MainCommand 0x06）。存檔 = report 4 `SaveProfileFeatureReport(profileNum)`（MainCommand 0x12）。重置 = report 4 `ResetProfileFeatureReport(profileNum)`（MainCommand 0x09，0xFF = 全部）。特殊編號：`0x00`=ProfileCurrent、`0xFE`=DefaultProfile(用於 ReadProfile256ByteLoop 預設讀取)、`0xFF`=ProfileAll/ProfileOfRAM。
10. **ReadConfiguration(0x22)**：讀的是**韌體 flash 幾何**（IAPSize、APMaxSize、SectorSize、PageSize 各 uint16），**不是 profile / 設定**。與 profile 無關。

---

## 共用基礎結構

### GeneralUsbCommand（report 4 命令頭，7 B）
`IL 105370-105430`

```
struct GeneralUsbCommand {        // .pack 1
    uint8  ReportId;              // = 0x04              IL_0007: ldc.i4.4
    uint8  Header1;               // = 0xEA (234)        IL_000e: ldc.i4 234
    uint8  Header2;               // = 0x02              IL_0019: ldc.i4.2
    GeneralUsbMainCommand GeneralUsbMainCommand;
    GeneralUsbSubCommand  GeneralUsbSubCommand1;
    GeneralUsbSubCommand  GeneralUsbSubCommand2;
    ResponseCommand ResponseCommand;   // 回填
}
```
ctor: `IL 105400-105430`。所有 report 4 命令封包開頭固定 `04 EA 02`。

### GeneralUsbMainCommand enum `IL 105322-105344`
| 名稱 | 值 | 與 profile 相關 |
|------|----|----|
| ReadFirmwareVersion | 0x01 | |
| ResetKeyboard | 0x02 | |
| Profile | **0x06** | ✅ profile 切換/查詢 |
| KeyFunctionRam | 0x07 | keymap RAM 寫入 |
| ResetProfile | **0x09** | ✅ 重置 profile |
| EKeyMode | 0x0B | |
| GameModeDisableKeysRam | 0x0C | |
| SaveProfile | **0x12** | ✅ 存檔 |
| ReadConfiguration | **0x22** | ❌（是 flash 幾何，非 profile）|
| ResetToFactoryDefault | 0x31 | |

### GeneralUsbSubCommand enum `IL 105350-105370`
| 名稱 | 值 |
|------|----|
| SetProfile / Write / PrimaryKeyAssignment / WriteDateTime / Disable / IAP | 0x00 |
| GetProfile / Read / SecondaryKeyAssignment / Enable / AP | 0x01 |
| Default / ClearDateTime | 0x02 / 0x10 |

注意：`SetProfile=0x00` 與 `GetProfile=0x01` 是 profile 切換專用的 SubCommand 語意（放在 `GeneralUsbSubCommand1`）。

### ResponseCommand enum `IL 105309-105315`
| 名稱 | 值 |
|------|----|
| Success | **0xC0** (192) |
| Fail | 0xC1 |
| InProcess | 0xC2 |

所有 profile 命令回來後都檢查 `ResponseCommand == 0xC0`。

### FeatureReportId enum `IL 105288-105300`
| 名稱 | 值 |
|------|----|
| GeneralUsb / LedTest | 0x04 |
| LedColorSetting | 0x06 |
| LedPreset / ProfileInRAM | **0x07**（共用 ID）|
| ProfileUsb | **0x08** |
| MacroUsb | 0x09 |
| MacroNameUsb | 0x0A |
| SWCustomizeData | 0x0F |

---

## Q1. ProfileNumberFeatureReport（report 4, 17 B）— profile 編號讀寫

`IL 101723-101769`

```
struct ProfileNumberFeatureReport {     // .pack 1
    GeneralUsbCommand Command;          // 7 B: 04 EA 02 06 <sub1> <sub2> <resp>
    uint8 ProfileNumber;                // ★ profile 編號（1-9）
    uint8[9] Reserved;                  // marshal fixed array [9]
}
// total = 7 + 1 + 9 = 17 B ✓
```

ctor(subCommand, profileNumber=0): `IL 101750-101767`
- `ldc.i4.6` → MainCommand=0x06 (Profile)
- `ldarg.1` → SubCommand1 = 傳入的 subCommand（0x00=Set / 0x01=Get）
- `ldc.i4.0` → SubCommand2 = 0x00
- `ProfileNumber` = 傳入 profileNumber（預設 0）

封包樣式：
```
04 EA 02 06 <subcmd> 00 <resp> <profileNum> <9B reserved>
```
- **Set**（切換 profile）：subcmd=0x00 → `04 EA 02 06 00 00 <resp> <num> ...`
- **Get**（查詢當前）：subcmd=0x01 → `04 EA 02 06 01 00 <resp> <回填num> ...`

Profile 編號在 **byte offset 7**（0-indexed；去掉 report ID byte 後是 data[5]）。

### 使用點

**get_ProfileIndex** `IL 103762-103810`（查詢當前 profile）
```
ldc.i4.1                          // subCommand = GetProfile (0x01)
ldc.i4.0                          // profileNumber = 0
newobj ProfileNumberFeatureReport(GetProfile, 0)
SetAndGetFeature(..., 0x64)       // timeout 100 ms
if ResponseCommand == 0xC0:
    _profileIndex = .ProfileNumber
    if !dict.ContainsKey(_profileIndex): ReadProfile()
```

**set_ProfileIndex** `IL 103812-103870`（切換 profile，1–9 才接受）
```
if value < ProfileMin(1) || value > ProfileMax(9): return
ldc.i4.0                          // subCommand = SetProfile (0x00)
newobj ProfileNumberFeatureReport(SetProfile, value)
SetAndGetFeature(..., 0x64)       // 100 ms
if ResponseCommand == 0xC0:
    _profileIndex = value
    if !dict.ContainsKey(value): ReadProfile()
```

**SetProfileNumber(number)** `IL 103920-103970`（公開 API，同 set_ProfileIndex 但不動 dict）
- 範圍檢查 1 ≤ number ≤ 9，否則 false
- `ProfileNumberFeatureReport(SetProfile=0x00, number)`
- `SetAndGetFeature(..., 0x64)` → 回 `ResponseCommand==0xC0`

**GetProfileNumber(out number)** `IL 103972-104011`（公開 API）
- `ProfileNumberFeatureReport(GetProfile=0x01, 0)`
- `SetAndGetFeature(..., 0x05)`（timeout 5 ms，**比 set 短**）
- 成功則 `number = .ProfileNumber`

---

## Q2. SaveProfileFeatureReport（report 4, 17 B）— 存檔

`IL 101774-101819`

```
struct SaveProfileFeatureReport {       // .pack 1
    GeneralUsbCommand Command;          // 04 EA 02 12 00 00 <resp>
    uint8 ProfileNumber;                // ★ 帶 profile 編號
    uint8[9] Reserved;
}   // 17 B
```

ctor(profileNumber): `IL 101800-101817`
- `ldc.i4.s 0x12` → MainCommand=0x12 (SaveProfile)
- `ldc.i4.0`, `ldc.i4.0` → SubCommand1=0, SubCommand2=0
- `ProfileNumber` = 傳入

封包：`04 EA 02 12 00 00 <resp> <profileNum> <9B>`

**與已知 `04 EA 02 12 00 00 00 00` 對比**：軟體版**有帶 profile 編號**（byte offset 7）。無參數版 `SaveProfile()` 預設傳 0（= 當前 profile）。

### SaveProfile(number) `IL 104025-104078`
- 範圍：ProfileMin(1) ≤ number ≤ ProfileMax(9)，**或 number==0**（當前）
- `new SaveProfileFeatureReport(number)`
- `SetAndGetFeature(..., 300)`（timeout **300 ms**，存檔較慢）
- 成功條件 `ResponseCommand == 0xC0`
- `SaveProfile()`（無參）`IL 104018` 直接呼叫 `SaveProfile(0)`

---

## Q3. ResetProfileFeatureReport（report 4, 17 B）— 重置

`IL 103633-103679`

```
struct ResetProfileFeatureReport {      // .pack 1
    GeneralUsbCommand Command;          // 04 EA 02 09 00 00 <resp>
    uint8 ProfileNumber;
    uint8[9] Reserved;
}   // 17 B
```

ctor(profileNumber): `IL 103660-103677`
- `ldc.i4.s 0x09` → MainCommand=0x09 (ResetProfile)
- SubCommand1=0, SubCommand2=0

封包：`04 EA 02 09 00 00 <resp> <profileNum> <9B>`

### ResetProfile(number) `IL 104082-104170`
- 接受範圍：1 ≤ number ≤ 9，**或 number == 0xFF (255)**（全部重置）
- 若 number == 0xFF：`SetAndGetFeature(..., 1700)`（timeout **1700 ms**，全清很慢）
- 否則：`SetAndGetFeature(..., 0x64)`（100 ms）
- 成功條件 `ResponseCommand == 0xC0`
- 若是 0xFF 全清成功，接著 loop `ProfileMin..ProfileMax`（但 loop body 空轉，疑似佔位/未完成）

---

## Q4. ProfileReadWrite enum（report 8 分包用）

`IL 101833-101843`

| 名稱 | 值 |
|------|----|
| Read | **0x01** |
| Write | **0x02** |

**注意：Write=0x02，不是 0x00。** 這是 `ProfileCommandBytes256`（report 8 分包）用的方向碼。

---

## Q5. ProfileFunction enum（report 8 主檔頭用）

`IL 101822-101831`

| 名稱 | 值 |
|------|----|
| Write | **0x00** |
| Read | **0x01** |

這是 `ProfileCommand`（report 8 整檔頭）用的方向碼。**跟 ProfileReadWrite 是兩套**：
- `ProfileFunction`：整組 profile 一次讀寫（report 8 的 `ProfileUsbFeatureReport`）
- `ProfileReadWrite`：256 B 分包讀寫（report 8 的 `ProfileUsbFeatureReport256`）

---

## Q6. ProfileCommand / ProfileUsbFeatureReport（report 8, 265 B）

### ProfileCommand（report 8 命令頭，7 B）`IL 101849-101894`
```
struct ProfileCommand {              // .pack 1
    uint8 ReportId;                  // = 0x07       IL_0007: ldc.i4.7
    uint8 Header1;                   // = 0xEA       IL_000e: ldc.i4 234
    uint8 Header2;                   // = 0x02       IL_0019: ldc.i4.2
    ProfileFunction Command;         // Write=0x00 / Read=0x01
    uint8 ProfileNumber;             // ★ 要讀/寫哪個 profile (1-9 / 0xFE / 0xFF)
    uint8 Reserved;                  // = 0
    ResponseCommand ResponseCommand; // 回填
}
```
ctor(command, profileNumber): `IL 101862-101893`

**關鍵**：report 8 的命令頭用 **ReportId=0x07**（不是 0x08！）。`ProfileUsbFeatureReport` 結構的第一個欄位是 `ProfileCommand`，整包透過 report ID 8 傳輸，但內部 header byte 寫 0x07。這是 EVGA 協定的慣例（report 7/8 共用 0xEA 0x02 家族，由後續欄位區分）。

### ProfileUsbFeatureReport（整組 profile，265 B）`IL 103166-103315`
```
struct ProfileUsbFeatureReport {     // .pack 1
    ProfileCommand Command;          // 7 B (07 EA 02 <func> <profileNum> 00 <resp>)
    uint8 CheckSum;
    uint16 LengthOfProfileName;
    uint8[126] ProfileName;          // marshal fixed [126]
    GameModeDisableKey DisableKeys;  // uint8 flags
    uint8 ReportRate;
    uint8[126] Reserved;             // marshal fixed [126]
    KeyDefine[121] Primary;          // 主鍵映射，每個 4 B (Function+P1+P2+P3)
    KeyDefine[121] Secondary;        // 副鍵映射
    uint8[56] Reserved1;
    LedMainLightingEffectMode LedMainLightingEffectMode;
    LedSubLightingEffectMode  LedSubLightingEffectMode;
    uint8[30] Reserved2;
    ProfileStaticOn    StaticOn;
    ProfileBreathing   Breathing;
    ProfilePulse       Pulse;
    ProfileRainbowWave RainbowWave;
    ProfileTrigger     Trigger;
    ProfileStarShining StarShining;
}
```

ctor(ProfileFunction command, uint8 profileNumber): `IL 103208-103314`
- 建一個 `ProfileCommand(command, profileNumber)` 放進 Command
- CheckSum=0, LengthOfProfileName=0, DisableKeys=0x7F (ALL), 其餘 null/0
- 預設 LED 段：StaticOn(zone=0x80, ARGB(0,0,255,255))、Breathing、Pulse、RainbowWave、Trigger（各帶預設參數）

`CalculateCheckSum()` `IL 103316-`: 把 LengthOfProfileName（拆 hi/lo）、DisableKeys、ReportRate、ProfileName[]、Reserved[]、Primary[].Function/P1/P2/P3、Secondary[]、Reserved1[]、LedMainMode、LedSubMode、Reserved2[]、各 LED 段的 CheckSum() 全部相加取低 byte。

### 讀取流程 ReadProfile(indexOfProfile) `IL 104379-104445`
```
if indexOfProfile < 1 || > 9:   // 1-9
    if indexOfProfile != DefaultProfile(0xFE) && != 0xFF: return false
new ProfileUsbFeatureReport(Read=0x01, indexOfProfile)
SetAndGetFeature(..., 0x14)              // timeout 20 ms
if ResponseCommand == 0xC0:
    ProfileUsbFeatureReports[indexOfProfile] = report   // 存進 dict
```
接受 1–9、0xFE（預設）、0xFF（RAM/全部）。`ReadProfile()`（無參）`IL 104448` 用 `_profileIndex`。

### 寫入流程 WriteProfile(index) `IL 104463-104531`
```
if index < 1 || > 9: return false
if !dict.ContainsKey(index):
    if !ReadProfile(index): return false
report = dict[index]
report.Command.Command = Write(0x00)     // 改成 Write
report.CalculateCheckSum()
SetAndGetFeature(..., 0x64)              // timeout 100 ms
return ResponseCommand == 0xC0
```
`WriteProfile()`（無參）用 `_profileIndex`。

### 分包版 ProfileUsbFeatureReport256（265 B，256 B data）`IL 103567-103629`
```
struct ProfileUsbFeatureReport256 {
    ProfileCommandBytes256 Command;     // 8 B
    uint8 CheckSum;
    uint8[256] Reserved;                // ★ 256 B 資料本體
}
struct ProfileCommandBytes256 {         // IL 101899-101944
    uint8 ReportId;          // = 0x08       IL_0007: ldc.i4.8
    uint8 Header1;           // = 0xEA       IL_000e: ldc.i4 234
    ProfileReadWrite Command;   // Read=0x01 / Write=0x02
    uint8 Reserved;          // = 0
    uint8 ProfileNumber;     // ★
    uint8 DataOffset;        // ★ 分包 offset (0, 1, 2, ...)
    uint8 Reserved6, Reserved7;
}
```
ctor(profileNumber, Offset): `IL 103589-103605`
- `ldc.i4.1` → **ProfileReadWrite=Read(0x01)**（這個 ctor 只做讀）
- `new ProfileCommandBytes256(Read, profileNumber, Offset)`
- Reserved = new byte[256]

`CalculateCheckSum()` `IL 103611-103625`：`CheckSum = (uint8)(-(0)) = 0`（簡化版，只回 0）。

### 分包讀取 ReadProfile256ByteLoop(indexOfProfile, out list) `IL 104548-104668`
```
for i in 0 .. _readProfileLoop(=6):           // ctor 設 _readProfileLoop = 6  (IL_0001: ldc.i4.6)
    if IsProfileIndexUpdate: break
    new ProfileUsbFeatureReport256(indexOfProfile, i)   // offset = i
    SetAndGetFeature(..., 160)               // timeout 160 ms
    if report.Reserved.Length == 256:
        foreach b in Reserved: list.Add(b)
    Thread.Sleep(160)                        // IL_0099: ldc.i4 160
return result
```
**共 6 次 × 256 B = 最多 1536 B** 的原始 profile dump（用於 diff 預設值）。ctor 還會在初始化時對 0xFE（預設 profile）跑一次：`IL 103900-103918` `ReadProfile256ByteLoop(0xFE, out _defProfileRead)`。

---

## Q7. ProfileInRamUsbFeatureReport（report 7, 136 B）— RAM 中 LED 參數

`IL 96180-96296`

```
struct ProfileInRamUsbFeatureReport {     // .pack 1
    FeatureReportId ReportId;             // = 0x07      IL_0007: ldc.i4.7
    uint8 Header1;                        // = 0xEA      IL_000e: ldc.i4 234
    uint8 Header2;                        // = 0x02      IL_0019: ldc.i4.2
    MainCommand MainCommand;              // 0x0B-0x13 各 LED 模式
    SubCommand SubCommand;                // Write=0 / Read=1 / ReadDefault=2
    ResponseCommand ResponseCommand;
    uint8 CheckSum;
    uint8[128] Data;                      // 序列化的 LED 參數 struct
}   // 1+1+1+1+2+1+1+128 = 136 B ✓ (SubCommand 是 uint16)
```

ctor(MainCommand, SubCommand): `IL 96209-96232`

`CalculateCheckSum<T>(T s)`: 把 `Data = Serialize(s)`，然後 sum(Data) 取負。
`Get<T>()`: `Deserialize<T>(Data)`。

### MainCommand enum（report 7 用）`IL 96019-96032`
| 名稱 | 值 |
|------|----|
| KeyFunction | 0x0B |
| LED_LightingEffectMode | 0x0C |
| LED_StaticOnParameters | 0x0D |
| LED_BreathingParameters | 0x0E |
| LED_PulseParameters | 0x0F |
| LED_SpiralRainbowParameters | 0x10 |
| LED_RainbowWaveParameters | 0x11 |
| LED_TriggerParameters | 0x12 |
| LED_StarShiningParameters | 0x13 |

### SubCommand enum（report 7 用，uint16）`IL 96039-96045`
| 名稱 | 值 |
|------|----|
| Write | 0x0000 |
| Read | 0x0001 |
| ReadDefault | 0x0002 |

### 使用點（LED 類別的方法）
- `WriteLedLightingEffectMode` `IL 96590`: `new ProfileInRamUsbFeatureReport(LED_LightingEffectMode=0x0C, Write=0x00)` → `SetFeature`
- `ReadLedLightingEffectMode` `IL 96633`: `new ...(0x0C, Read=0x01)` → `SetAndGetFeature` → `Get<LightingEffectMode>()`
- 同模式用於 StaticOn(0x0D)、Breathing(0x0E)、Pulse(0x0F)、RainbowWave(0x11)、Trigger(0x12)、StarShining(0x13)，各 `IL 96699-97766`

**結論**：report 7 = 「當前 RAM 中 profile 的單一 LED 模式參數」即時讀寫，128 B data 段塞一個 LED 模式 struct。跟 report 8（整組 onboard profile）是不同層次。report 7 改的是「現在正在顯示的」，report 8 改的是「存在 flash 裡的某號 profile」。

---

## Q8. Profile 邏輯類別（`EDispNetLib.Hardwares.Z12RGB.Profile`）

`IL 103682-104686`

### 靜態常數 `IL 103685-103689`
| 名稱 | 值 | 意義 |
|------|----|------|
| ProfileAll | 0xFF | 全部 profile |
| ProfileOfRAM | 0xFF | RAM 中的 profile |
| ProfileCurrent | 0x00 | 當前 profile |
| ProfileCurrentReadWrite | 0xFF | 讀寫時的「當前」 |
| ProfileDefaultReadWrite | 0xFE | 預設 profile（factory default）|

### 屬性
| 屬性 | 值 | IL |
|------|----|----|
| ProfileMin | **1** | `get_ProfileMin` 103728 |
| ProfileMax | **9** | `get_ProfileMax` 103738 |
| DefaultProfile | **0xFE (254)** | `get_DefaultProfile` 103748 |

### 欄位 `IL 103693-103705`
- `_hidDevice` (IHidDevice)
- `_readProfileLoop` = 6（256B 分包次數）
- `_currentProfileRead`, `_defProfileRead` (List<byte>)
- `primaryKeyParameter`, `secondaryParameter` (PrimaryKeyParameter/SecondaryKeyParameter)
- `defprimaryKeyParameter`, `defsecondaryParameter`（預設值，用於 diff）
- `_isProfileIndexUpdate` (bool)
- `ProfileUsbFeatureReports` : `Dictionary<uint8, ProfileUsbFeatureReport>` ★ 各 profile 的快取
- `_profileIndex` (uint8)

### ctor(hidDevice) `IL 103872-103918`
```
_readProfileLoop = 6
_profileIndex = 0xFF
ProfileUsbFeatureReports = new Dictionary()
ReadProfile256ByteLoop(0xFE, out _defProfileRead)   // 預先讀 factory default 全 dump
```

### 方法清單與流程
| 方法 | IL 行 | 流程摘要 |
|------|-------|---------|
| `get_ProfileIndex` | 103762 | 發 GetProfile 拿當前編號 → 若 dict 沒有就 ReadProfile() |
| `set_ProfileIndex` | 103812 | 1–9 才接受 → 發 SetProfile → 更新 _profileIndex → 必要時 ReadProfile() |
| `SetProfileNumber(number)` | 103920 | 公開切換；1–9；發 SetProfile；檢查 0xC0 |
| `GetProfileNumber(out n)` | 103972 | 公開查詢；發 GetProfile(timeout 5ms)；回填 n |
| `SaveProfile()` / `(n)` | 104017 / 104025 | 發 SaveProfileFeatureReport(n)；timeout 300ms；0xC0 |
| `ResetProfile(n)` | 104082 | 1–9 或 0xFF；0xFF 用 1700ms；其餘 100ms |
| `ReadProfile(idx)` / `()` | 104379 / 104448 | 發 ProfileUsbFeatureReport(Read, idx)；20ms；存 dict |
| `WriteProfile(idx)` / `()` | 104463 / 104537 | 從 dict 取 → Command=Write → CheckSum → SetAndGet 100ms |
| `ReadProfile256ByteLoop(idx, out)` / `()` | 104548 / 104673 | 6 × ProfileUsbFeatureReport256(idx, offset) → 1536B dump |
| `SetKeyFunctionDefault()` / `(idx)` | 104173 / 104185 | 把 defprimaryKeyParameter 寫回每個 key（走 WriteKeyFunctionToRam）|
| `WriteKeyFunctionToRam` | 104340-104376 | report 4 MainCommand 0x07 寫單鍵映射 |
| `GetKeyAssigned` | 104686+ | 查詢單鍵綁定 |

### Profile 內容組成（從 ProfileUsbFeatureReport 欄位推得）
1. **ProfileName**（126 B，長度由 LengthOfProfileName 標示）
2. **GameModeDisableKey**（1 B flags：ALT_TAB/TAB/CTRL_ESC/ALT_F4/LSHIFT/APPKEY/WINKEY，0x7F=ALL）
3. **ReportRate**（1 B，輪詢率）
4. **Reserved**（126 B）
5. **Primary keymap**：121 × KeyDefine(4B) = 484 B（Function + Parameter1/2/3）
6. **Secondary keymap**：121 × KeyDefine = 484 B（Shift 層 / 副映射）
7. **Reserved1**（56 B）
8. **LedMainLightingEffectMode**（Off/StaticOn/Breathing/Pulse/RainbowWave/StarShining/Trigger = 0/1/2/3/5/6/7）
9. **LedSubLightingEffectMode**（方向等子模式）
10. **Reserved2**（30 B）
11. **7 個 LED 模式參數段**：StaticOn / Breathing / Pulse / RainbowWave / Trigger / StarShining（各含 ZoneSelect/StartMode/StopMode/顏色/週期等，Z12 無 SpiralRainbow 段）

**不含**：巨集本體（report 9/10）、巨集名稱（report 0x0A）、巨集綁定（report 4 MainCommand 0x07 的 KeyFunctionRam，獨立於 profile struct）。巨集綁定是 per-key 的，理論上會跟著 profile 存，但在 `ProfileUsbFeatureReport` 結構裡是以 `KeyDefine.Function` 指向巨集編號，巨集本體另存。

### KeyDefine struct（4 B）`IL 113363-113374`
```
struct KeyDefine {           // .pack 1
    KeyFunction Function;    // uint8
    uint8 Parameter1;        // 修飾鍵 / 巨集號
    uint8 Parameter2;        // HID code 1
    uint8 Parameter3;        // HID code 2
}
```

### GameModeDisableKey enum（Flags）`IL 105715-105730`
| Flag | 值 |
|------|----|
| NONE | 0x00 |
| ALT_TAB | 0x01 |
| TABKEY | 0x02 |
| CTRL_ESC | 0x04 |
| ALT_F4 | 0x08 |
| LSHIFTKEY | 0x10 |
| APPKEY | 0x20 |
| WINKEY | 0x40 |
| ALL | 0x7F |

### LedMainLightingEffectMode enum `IL 95898-95908`
| 名稱 | 值 |
|------|----|
| Off | 0x00 |
| StaticOn | 0x01 |
| Breathing | 0x02 |
| Pulse | 0x03 |
| RainbowWave | 0x05 |
| StarShining | 0x06 |
| Trigger | 0x07 |
（無 SpiralRainbow = Z12 五區 RGB 沒這模式）

### LedSubLightingEffectMode enum `IL 95914-95931`
有多組同值 0x00 別名（None/StaticOff/StaticOn/Breathing/Pulse/Up/StarShining/TypeLighting），實際方向值：Down=0x01、Right=0x02、Left=0x03；OneKey=0x01、ThreeByThreeGrid=0x02。

---

## Q9. 9 組 profile 的存儲與切換

- **存儲位置**：鍵盤 onboard flash，每組 profile = 一份 `ProfileUsbFeatureReport`（report 8, 265 B 主檔 + 可選 256 B × 6 分包 dump）。
- **定址**：用 `ProfileCommand.ProfileNumber`（report 8 主檔）或 `ProfileCommandBytes256.ProfileNumber`（分包）指定 1–9。特殊：0xFE=factory default、0xFF=RAM/全部、0x00=當前。
- **切換**：report 4 `ProfileNumberFeatureReport` MainCommand=0x06, SubCommand1=0x00(SetProfile), profileNum=1–9。鍵盤收到後把該號 profile 從 flash 載入 RAM。
- **查詢當前**：report 4 MainCommand=0x06, SubCommand1=0x01(GetProfile) → 回填 ProfileNumber。
- **讀整組**：report 8 `ProfileUsbFeatureReport(Read=0x01, profileNum)`。
- **寫整組**：report 8 `ProfileUsbFeatureReport(Write=0x00, profileNum)` + CheckSum。
- **存檔到 flash**：report 4 `SaveProfileFeatureReport` MainCommand=0x12, profileNum。（把 RAM 寫進 flash 該號）
- **重置**：report 4 `ResetProfileFeatureReport` MainCommand=0x09, profileNum（0xFF=全清）。

軟體端 `Profile` 類別用 `Dictionary<byte, ProfileUsbFeatureReport> ProfileUsbFeatureReports` 快取讀過的 profile，避免重複讀。

---

## Q10. ReadConfiguration (0x22) — 是 flash 幾何，不是 profile

`ReadConfigurationFeatureReport` `IL 105945-105978`
```
struct ReadConfigurationFeatureReport {   // .pack 1
    GeneralUsbCommand Command;            // 04 EA 02 22 01 00 <resp>
    uint16 IAPSize;
    uint16 APMaxSize;
    uint16 SectorSize;
    uint16 PageSize;
    uint8[2] Reserved;
}
```
ctor: `IL 105968-105976` — MainCommand=0x22, SubCommand1=0x01, SubCommand2=0x00。

`Z12RGBHidDevice.ReadConfiguration(out iap, out ap, out sector, out page)` `IL 107470-107529`：
```
new ReadConfigurationFeatureReport()
SetAndGetFeature(...)
if ResponseCommand == 0xC0:
    iapSize  = .IAPSize
    apSize   = .APMaxSize
    sectorSize = .SectorSize
    pageSize = .PageSize
```

**結論**：ReadConfiguration(0x22) 讀的是韌體 flash 的 IAP/AP/Sector/Page 大小（給韌體更新用），**跟 profile / 鍵盤設定無關**。本專案不做韌體更新，可忽略此命令。

---

## 封包總表

### Report 4 (GeneralUsb, 17 B) — 命令通道
| 用途 | MainCmd | SubCmd1 | SubCmd2 | 封包（不含 report ID byte）| timeout |
|------|---------|---------|---------|---------------------------|---------|
| 切換 profile | 0x06 | 0x00 (Set) | 0x00 | `EA 02 06 00 00 <resp> <num> +9B` | 100ms |
| 查詢 profile | 0x06 | 0x01 (Get) | 0x00 | `EA 02 06 01 00 <resp> <num> +9B` | 5ms (Get) / 100ms (get_ProfileIndex) |
| 存檔 | 0x12 | 0x00 | 0x00 | `EA 02 12 00 00 <resp> <num> +9B` | 300ms |
| 重置 profile | 0x09 | 0x00 | 0x00 | `EA 02 09 00 00 <resp> <num> +9B` | 100ms / 1700ms(0xFF) |
| ReadConfiguration | 0x22 | 0x01 | 0x00 | `EA 02 22 01 00 <resp> + 8B` | — |

### Report 7 (ProfileInRAM, 136 B) — RAM 中單一 LED 模式
```
07 EA 02 <MainCmd 0x0C-0x13> <SubCmd 16bit> <resp> <chksum> <128B data>
```

### Report 8 (ProfileUsb, 265 B) — 整組 onboard profile
主檔頭：`07 EA 02 <ProfileFunc 0/1> <profileNum> 00 <resp>` + 258B profile 內容
分包頭：`08 EA 02 <ProfileReadWrite 1/2> 00 <profileNum> <offset> 00 00` + 1B chksum + 256B data

---

## 待實機驗證的點（純靜態分析無法確認）

1. report 8 主檔 `ProfileCommand.ReportId` 寫 0x07 但透過 report 8 傳輸——實際 HID feature report ID 是否真的用 0x08？
2. `ProfileUsbFeatureReport256` 的 `CalculateCheckSum` 恆回 0，是否鍵盤真的不檢查分包 checksum？
3. 256 B 分包的 `DataOffset` 單位是「第幾包」(0,1,2..5) 還是「byte offset / 256」——IL 顯示是迴圈索引 i，即第幾包。
4. profile 0xFE (factory default) 是否真存在於 Z12 flash，還是韌體硬編碼。
5. `ProfileUsbFeatureReport` 總長是否真的 265 B（欄位 marshal 加總需實測）。
6. ~~SaveProfile(0) 存的是「當前 RAM profile」還是 profile 0——軟體語意是當前，但鍵盤端是否區分。~~
   → 2026-08-16：`04 EA 02 12 00 00 00 00` 回 0xC0，`... 00 01` 回 0xC1。
   鍵盤接受 0=當前，不接受在 byte[7] 直接寫 profile 編號 1。
   拔插後讀回一致，flash 持久化成立。

這些都遵守 AGENTS.md 規則 1：**未還原的指令禁止亂送 SET_REPORT**，需先 GET_FEATURE 驗證再寫。