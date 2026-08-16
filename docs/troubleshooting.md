# 疑難排解與事故記錄

本檔記錄送錯封包、鍵盤斷線、設定被清掉、惡意依賴等高風險事故的完整
經過，供未來 agent 避免重蹈。對應 AGENTS.md「不可違反的規則」與
「文件維護」段。

## 2026-08-16 — 惡意 repo 偽裝成 EVGA Z12 工具

**風險級別：高（惡意下載、可能導致使用者電腦被植入作弊注入器）。**

### 事故經過

web_search 找到兩個看似相關的 GitHub repo：

1. `erik-berger350/evga-z12-keys-linux` — 搜尋結果描述「132+ commits、
   較完整、有預編譯 binary」，被誤判為「較成熟」的專案。
2. `Pasquotcho/evga-z12-keys` — 真實的單檔 Rust + hidapi 工具。

subagent 實際 clone `erik-berger350` 後發現：

- 全 repo 只有 4 個 tracked 檔案，**從未有過任何 `.rs` / `Cargo.toml`**。
- 132 個 commit 全部只是在 append `.github/update-log` 的自動垃圾時間戳。
- `index.html` 是 XOR（key `0xCF`）混淆的釣魚頁，解碼後 JS 變數寫死：

  ```
  downloadUrl = "https://github.com/leon-gray9/kernel-space-i5wnqq/releases/download/2026/Loader_v3.5.zip"
  ```

- 頁面假「Security Check」掃描清單含 `roblox_inject.dll`、
  `exploit_core.dll`、`hook_engine.dll`、`anti_detect.dll`、
  `scripts/blox_fruits.lua` —— 是 Roblox 作弊注入器偽裝成
  「EVGA Z12 Keys v1.0.0」下載頁。

完整 decode 見 [`external-protocol-comparison.md`](external-protocol-comparison.md)。

### 教訓（已回寫 AGENTS.md 派工與停損段）

- **不要被 commit 數、star 數、README 行銷文騙。** 評估一個 repo 是否
  可用前，必須 clone 下來確認有實際原始碼（`.rs`/`.py`/`Cargo.toml`/
  `package.json` 等），而不是只看 web_search 摘要。
- **不要自動下載或執行外部 repo 的 release / GitHub Pages 下載連結**，
  尤其是混淆過的 JS。先讀原始碼再說。
- web_search 的「132+ commits、較完整」描述是從 README 抄的，不是
  對 repo 內容的獨立驗證。

## 2026-08-16 — E4 position 回應與送出值不符

**風險級別：中（寫入時可能改錯 E-key）。**

### 事故經過

GET_FEATURE 讀 E-key 時，E4 送出 `position=0x52`（Pasquotcho
`src/main.rs:19-39` 的表），但回應的 byte[7] 是 `0x41`（與 E3 相同），
不是 `0x52`。其餘 E1/E2/E3/E5 回應的 position 都與送出值一致。

### 可能原因

- 韌體回應 bug（回應欄位沒填回送出的 position）。
- `0x52` 不是本機 `2612` 的 E4 真正 position；`2622` 與 `2612` 硬體
  佈局有細微差異。

### 教訓

- **Pasquotcho 的 position 表（`0x15/0x2B/0x41/0x52/0x66`）不能盲目
  套用。** 寫入 E4 前要先確認它的真正 position，或用 scan 方式找出
  E4 對應的值。
- 寫入任何 E-key 前，先 GET_FEATURE dump 目前設定並保留，失敗可還原。

> **2026-08-16 更新**：E4 position 不符的根因不是 position 表錯，而是
> 讀取機制 bug（見下兩條）。改用「送兩次、丟棄首次」後，五顆 E-key 的
> 回應 position 全部穩定吻合送出值，position 表確認正確。本條保留作為
>「現象 → 錯誤假設 → 真因」的對照案例。

## 2026-08-16 — GET_FEATURE 讀取不穩定：兩個 HID API 根因

**風險級別：中（讀錯設定會誤判鍵盤狀態，導致寫入時覆蓋錯資料）。**

### 根因 #1：transfer type 用錯（write vs send_feature_report）

report 4 是 **feature report**，必須用 `dev.send_feature_report()`
（底層 `hid_send_feature_report`）。第一版腳本誤用 `dev.write()`
（底層 `hid_write` = output report），鍵盤不認這個 transfer type，
不處理查詢命令；接著 `get_feature_report` 讀回的是 buffer 裡的過時
快取，不是針對當前請求的回應。Pasquotcho 的 Rust 程式碼用的是
`device.send_feature_report()`（正確），所以它沒遇到這個坑。

**症狀**：前兩次測試回應亂跳，E4/E5 回應別的 E-key 的 position 和
mapping。

**教訓**：HID feature report 讀寫一律用 `send_feature_report` /
`get_feature_report`，不要用 `write` / `read`（那是 output/input report）。
移植別的語言/bindings 的協定常數時，API 名稱也要逐個對齊，不能只搬
封包結構。

### 根因 #2：get_feature_report 首次讀回過時回應

即使送對了 transfer type，`hidapi`（macOS IOHIDLayer）的
`get_feature_report` 第一次讀到的是 buffer 裡上一筆請求的結果，不保證
針對當前請求。連續讀多顆 E-key 時，每一顆的第一次回應常是「上一顆」
的內容。

**症狀**：用對 `send_feature_report` 後，300ms 延遲修了 E2/E5 但 E4
仍壞；1000ms 延遲修了 E2–E5 但 E1（每個 session 第一筆）反而回應了
上一個 session 最後一筆（E5）的內容。延遲越長，第一筆越有時間被舊
session 污染。

**解法**：每顆 E-key 送兩次 GET_FEATURE，丟棄首次回應（排空過時
快取），取第二次。不需要延遲。實證：五顆 E-key 全部 position 吻合、
零失誤。

**教訓**：hidapi 的 `get_feature_report` 不保證「送請求 → 讀回應」的
同步語意。讀取設定值時，先送一次排空 buffer 再讀第二次才可靠。不能
靠延遲猜（延遲長度跟 buffer 污染來源有關，無法穩定）。

## 2026-08-16 — E-key function=0x03 是 onboard 巨集播放

**風險級別：無（唯讀觀測，純發現）。**

### 發現經過

report 4 讀回的 `function=0x03` 不在 Pasquotcho 解碼範圍（它只認
`0x00` 單鍵、`0xFF` disable）。最初推測是媒體鍵（因 `key1=0x01` 在
Keyboard page 不是鍵，但 Consumer page 0x01 = Consumer Control）。

用 `src/listen_ekeys.py` 聽介面 1 input report，按 E1 時**收不到任何
report**（E-key 輸出不在介面 1）。介面 2（NKRO）開不了（macOS
privilege violation）。改用人工觀測：使用者按 E1，自動依序跑出
`j j l h s i a o` 八個字母。確認 `function=0x03` = onboard 巨集播放。

五顆 E-key 巨集內容：E1=`jjlhsiao`(8鍵)、E2=`jjlkai`(6鍵)、
E3=`jjlbrand`(8鍵)、E4=`jjljing`(7鍵)、E5=`jjmin`(5鍵)。macOS 上
無任何 EVGA 軟體，證實巨集完全 onboard 播放，不需要 Unleash daemon。

### 教訓

- **`function` 欄位是功能類別枚舉**：`0x00`=單鍵、`0x03`=巨集、
  `0xFF`=disable。其他值（媒體、滑鼠、weblink、profile 切換）待 sniff
  還原。
- **巨集本體不在 report 4**：report 4 只存引用（`fn=0x03 mod=0x03..0x07`），
  巨集內容（鍵碼序列）在 report 5/8/9/0x0F 中的哪一個，待 GET_FEATURE
  探測。
- **hidapi 開不了被 macOS 系統佔用的介面**（介面 0 boot keyboard、
  介面 2 NKRO 都會 privilege violation）。要聽這些介面的 input，需用
  macOS 原生 IOHIDManager（透過 pyobjc）或 Linux hidraw。