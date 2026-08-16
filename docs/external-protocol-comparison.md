# 外部 repo 協定比對（2026-08-16，唯讀研究）

比對兩個 GitHub repo 還原的 HID 協定能否移植到本機這把 Z12（VID:PID
`3842:2612`）。本機協定事實來源：`docs/research.md`。本任務未送任何封包。

## 來源 repo

| repo | 狀態 | 結論 |
|------|------|------|
| `erik-berger350/evga-z12-keys-linux` | **無原始碼，是惡意釣魚頁** | 不可用、不可執行 |
| `Pasquotcho/evga-z12-keys` | 單檔 Rust + hidapi，可讀可寫 E1–E5 | 協定可用，PID 需驗證 |

## erik-berger350/evga-z12-keys-linux —— 惡意，勿碰

雖然號稱「132+ commits」，但全 repo 只有 4 個 tracked 檔案：

```
.github/update-log   ← 100 行自動產生的時間戳（run=xxxxx n=xxxxx），無意義
LICENSE              ← GPL3
README.md            ← 行銷文，宣稱是 Rust CLI，叫人去 GitHub Pages 下載
index.html           ← XOR 混淆的 JS，解開是釣魚頁
```

`git ls-remote` 確認只有 `main` 一個 branch、無 tag；`git log --all` 確認
歷史上從未出現過任何 `.rs` / `Cargo.toml` / `keys.yaml`。132 個 commit
全部只是在 append `.github/update-log` 的垃圾列。

解碼 `index.html`（`atob` + XOR key `0xCF`）後得到一個假「Security Check /
file integrity scan」頁面，其 JS 變數：

```
const downloadUrl = "https://github.com/leon-gray9/kernel-space-i5wnqq/releases/download/2026/Loader_v3.5.zip";
```

頁面假裝掃描的「檔案清單」包含 `roblox_inject.dll`、`exploit_core.dll`、
`hook_engine.dll`、`anti_detect.dll`、`lua_runtime.dll`、`scripts/blox_fruits.lua`
等 —— 這是一個 Roblox 作弊注入器，被包裝成「EVGA Z12 Keys v1.0.0」下載頁。

**結論：這個 repo 不是 Z12 工具，沒有任何協定資訊，且附帶惡意下載連結。
不要 clone、不要執行、不要下載它的 release。** 後續比對只針對 Pasquotcho。

## Pasquotcho/evga-z12-keys —— 協定可用

單檔 `src/main.rs`（316 行）、`keys.yaml`（HID usage 對照表）、
`Cargo.toml`（hidapi 2.6，linux-shared-hidraw）。git 只有 1 個 commit。

### 逐項驗收

#### 1. PID

`src/main.rs:6-7`：

```
const VENDOR_ID:  u16 = 0x3842;
const PRODUCT_ID: u16 = 0x2622;
```

`README.md:6` 寫 `Tested device: EVGA Z12 with USB ID 3842:2622`。

- 作者**只寫 2622**，沒有同時寫到 2612，也沒解釋兩者關係。
- 本機是 `2612`（`docs/research.md:24`）。`2612` vs `2622` 是 Z12 兩個
  revision/PID（OpenRGB issue #2670 也只記 `2612`）。作者沒提，需自行驗證。

#### 2. 介面

`src/main.rs:97-103` 挑裝置條件：

```
device.vendor_id() == VENDOR_ID
    && device.product_id() == PRODUCT_ID
    && device.interface_number() == INTERFACE   // INTERFACE = 1 (src/main.rs:8)
```

- 開的是 **介面 1**，跟本機 `docs/research.md:54-60`（介面 1、vendor
  collection page `0x08` / usage `0x4B`）的介面號一致。✅
- 但作者**只靠 interface_number==1，沒檢查 usage page / usage**。hidapi
  在 Linux 用 hidraw，一個介面號對一個 hidraw node，實務上夠用；但本機
  介面 2 的 usage pair 也含 `(0x08,0x4B)`（`docs/research.md:108`），若
  hidapi 把介面 2 也列出來，純比 interface_number 是安全的（介面 2 == 2）。
  結論：介面挑選與本機 descriptor 相容，但比 OpenRGB 的
  `REGISTER_HID_DETECTOR_IPU(...,0x08,0x4B)` 寬鬆。

#### 3. Report ID

E-key 映射走 **report ID `0x04`**（`src/main.rs:136`、`:151`、`:168`）。

對照本機 `docs/research.md:63`：report `0x04` descriptor count 16、傳送
長度 17，用途「Save / NFI / 短命令」。**作者把 keymap 讀寫也塞進 report 4
的短命令通道**，而不是走 report 5/8/9（265B）。

#### 4. 封包開頭

開頭是 `0xEA 0x02` 家族。`src/main.rs`：

| 動作 | 開頭（report ID + header） | 行號 |
|------|------------------------------|------|
| 讀映射 | `04 EA 02 07 01 00 00 <pos>` | `:136` |
| 寫映射 | `04 EA 02 07 00 00 00 <pos> <fn> <mod> <k1> <k2>` | `:149-162` |
| 存檔   | `04 EA 02 12 00 00 00 00` | `:168` |

- 讀/寫用 command `0x07`，byte 4 區分 read(`01`)/write(`00`)。
- 存檔用 command `0x12`，與 OpenRGB Z15 的 Save `04 EA 02 12`（`docs/research.md:122`）**完全一致**。✅
- magic `0xEA 0x02` 與本機假設（`docs/research.md:116`、`:134`）一致。✅

#### 5. Report 長度

`src/main.rs:9`：`const REPORT_SIZE: usize = 17;`，所有報文都是
`[0u8; 17]`。對照本機 `docs/research.md:63`，report `0x04` 傳送長度 **17**。
**完全對得上**。✅

#### 6. Checksum

**沒有做 checksum。** `transact()`（`src/main.rs:111-133`）只：
1. `send_feature_report(request)`
2. 清零後 `request[0] = 0x04` 再 `get_feature_report`
3. 檢查回傳長度 == 17
4. 檢查 `request[6] == 0xc0`（成功碼）

封包 byte 5–7 一律填 `0x00`，沒有像 OpenRGB 那樣「從 byte 8 起每位相減」
（`docs/research.md:132`）的 checksum 計算。report 4 的 17-byte 短命令
似乎不需要 checksum（OpenRGB 的 report 4 範例也沒明顯 checksum 欄位，
checksum 主要出現在 report 6/7 的長封包）。這點與本機假設不衝突，但
**report 6/7 的 checksum 演算法仍要本機自行驗證**。

#### 7. 讀 vs 寫

**有做 GET_FEATURE 讀目前映射。** `read_key()`（`src/main.rs:134-145`）
送 `04 EA 02 07 01 00 00 <pos>`，回傳 byte 8–11 = `{function, modifier,
key1, key2}`。`status` 指令（`:227-232`）會把 E1–E5 全部讀出來印。

寫後也會再讀一次確認（`:256`、`:284`）。符合「先讀再寫、保留 dump」的
安全原則。

#### 8. 巨集 vs 單鍵映射

**只做單鍵映射，不做巨集序列。** `Mapping` 結構（`src/main.rs:41-47`）是
固定 4 欄 `{function, modifier, key1, key2}`：

- `function == 0x00`：單鍵 + 可選一個修飾鍵（`keyboard()`，`:51-61`）。
  修飾鍵用 bitmask（`1 << (usage-0xe0)`），即標準 HID modifier byte。
- `function == 0xff`：disable（`:79-84`）。
- 其它 `function` 值會被 `print_mapping` 當成「function=0xXX parameters=...」
  原樣印出（`:219-223`），但程式不會主動產生這些值。

所以它能設「E1 → F17」「E2 → Shift+A」，但**不能寫巨集序列**（如
「E1 → Ctrl+C then Ctrl+V」）。`keys.yaml` 是純 HID usage 表（A=0x04 …
F24=0x73、LEFTCTRL=0xE0 … RIGHTCTRL=0xE4），無巨集語意。巨集仍需 sniff
還原（與 `docs/research.md:147` 的「巨集沒有現成開源實作」結論一致）。

### 封包結構對照

```
本機 report 4 (17B, docs/research.md:63)
┌─0───1───2───3───4───5───6───7───8────9────10───11──12..16─┐
│ID│EA│02│cmd│rd│??│??│pos│fn│mod│k1│k2│ 0..0                │
└──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──────────────────────┘

Pasquotcho read  (src/main.rs:136):  04 EA 02 07 01 00 00 <pos>            (+9B 0)
Pasquotcho write (src/main.rs:149):  04 EA 02 07 00 00 00 <pos> <fn> <mod> <k1> <k2> (+5B 0)
Pasquotcho save  (src/main.rs:168):  04 EA 02 12 00 00 00 00                (+9B 0)
回應成功碼: report[6] == 0xC0       (src/main.rs:127)
```

E-key position（`src/main.rs:19-39`）：E1=`0x15`、E2=`0x2B`、E3=`0x41`、
E4=`0x52`、E5=`0x66`。這 5 個 position 值不在本機筆記裡，是 Pasquotcho
從 sniff 還原的，**必須用本機 GET_FEATURE 驗證**。

## 移植可行性結論

### 可直接拿來用的部分

1. **家族協定假設被證實**：`0xEA 0x02` header、report 4 / 17B、command
   `0x07` 做 keymap 讀寫、command `0x12` 存檔 —— 與本機
   `docs/research.md` 的 OpenRGB Z15 摘要與「假設」段一致。Pasquotcho
   等於是 Z12 上 report 4 短命令通道的獨立第三方驗證。
2. **介面 1 + report 4 + 17B** 完全對得上本機 descriptor。
3. **讀寫雙向**：有 GET_FEATURE 讀映射，符合本專案「先讀再寫」原則。
4. **存檔命令 `04 EA 02 12`** 與 OpenRGB Z15 Save 完全相同。

### 必須先用本機 GET_FEATURE 驗證才能定案的點

1. **PID `2612` vs `2622`**：Pasquotcho 只測過 `2622`。本機是 `2612`。
   先用 `hidutil` / hidapi 開介面 1、送 `04 EA 02 07 01 00 00 0x15` 讀
   E1，若回傳 17B 且 `[6]==0xC0`，即證實 `2612` 走同一協定。失敗就停，
   不要改送 SET（遵守 AGENTS.md 規則 1）。
2. **E-key position 值**（`0x15/0x2B/0x41/0x52/0x66`）：本機筆記沒有這張
   表，是 Pasquotcho 從 sniff 得到。`2612` 與 `2622` 若硬體佈局相同應該
   一致，但仍要用 GET_FEATURE 逐鍵讀確認。
3. **回應成功碼 `0xC0` at byte 6**：本機筆記沒記此欄位，需驗證本機回應
   格式是否相同（byte 6 是否為 status、`0xC0` 是否代表成功）。
4. **無 checksum 是否安全**：report 4 短命令 Pasquotcho 不送 checksum。
   本機送 report 4 時可比照不送；但**report 6/7（32B/136B）的 checksum
   演算法仍需本機自行驗證**，不能從這個 repo 類推（它沒碰 report 6/7）。
5. **macOS hidapi 開介面 1 的權限**：Pasquotcho 是 Linux（hidraw），
   macOS 需 Input Monitoring 權限，且不能開介面 0（`docs/research.md`
   與 AGENTS.md 規則 3）。

### 移植建議

- **E1–E5 單鍵映射**：協定可信，可移植。先做唯讀 GET_FEATURE 探測（本機
  `2612`），確認後再把 Pasquotcho 的 `read_key` / `write_key` / `save`
  三個封包結構搬過來，PID 改成 `2612`（或同時接受 2612/2622）。
- **巨集、全鍵映射、Shift 層、9 組 profile、五區 RGB**：這個 repo 都沒
  做，仍需靠 sniff（report 5/8/9/0x0F + report 6/7）還原，與本機
  `docs/research.md:150-155` 的下一步計畫不變。
- **erik repo 完全不用考慮**：無原始碼且為惡意釣魚下載頁。