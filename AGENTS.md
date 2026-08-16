# AGENTS.md #

EVGA Z12 鍵盤設定工具（macOS / Linux）。目標是在沒有官方 Unleash RGB
（Windows only）的情況下，用 HID feature report 讀寫鍵盤的 onboard
設定：按鍵映射、巨集、五區 RGB、最多 9 組內建設定檔。

本目錄已過探測階段：有 `src/evga_z12/` 協定函式庫與唯讀 CLI
`src/z12ctl.py`（Python 3 + hidapi）。keymap SET_FEATURE 寫入已用
`src/test_write.py` 驗證，但 CLI 尚未暴露寫入子命令。官方軟體只支援
Windows；macOS 上鍵盤當一般 USB HID 鍵盤可用，改映射 / 巨集 / 燈光
走本專案的 HID feature report。

---

## Quick Map

| 要做什麼 | 先讀哪個檔案 |
|----------|-------------|
| 了解專案目的、可行性、現況 | [`README.md`](README.md) |
| 跑唯讀 CLI（keymap / 巨集 / profile / LED） | `src/z12ctl.py`（`.venv/bin/python src/z12ctl.py --help`） |
| 看 2026-08-15 實機 HID 擷取與協定比對 | [`docs/research.md`](docs/research.md) |
| 動到 USB / HID report / 按鍵映射 / 巨集 | `docs/research.md`（協定文件尚未獨立成 usb-protocol） |
| 對照 OpenRGB 已還原的 Z15/Z20 RGB 協定 | OpenRGB `Controllers/EVGAUSBController/EVGAKeyboardController/` |
| 比對外部 Z12 repo（Pasquotcho 可用、erik 惡意） | [`docs/external-protocol-comparison.md`](docs/external-protocol-comparison.md) |
| Unleash RGB 軟體逆向分析（EDispNetLib.dll） | [`docs/unleash-reverse-engineering.md`](docs/unleash-reverse-engineering.md) |
| Profile 讀寫協定（封包結構、命令表） | [`docs/profile-protocol.md`](docs/profile-protocol.md) |
| 完整 key position 表（113+13 鍵） | [`docs/key-position-table.md`](docs/key-position-table.md) |
| keymap 全掃描結果（121 鍵實機驗證） | [`docs/keymap-scan-result.md`](docs/keymap-scan-result.md) |
| 送錯封包 / 鍵盤斷線 / 惡意依賴等事故與教訓 | [`docs/troubleshooting.md`](docs/troubleshooting.md) |

---

## 不可違反的規則

1. **未還原的指令禁止亂送 SET_REPORT。** 同一方法失敗兩次就停，帶完整
   失敗軌跡回報。禁止對未知 report ID 暴力掃描寫入。
2. **禁止對這把鍵盤做韌體更新 / 刷機。** 本專案只做設定讀寫。
3. **不可占用 boot keyboard interface（介面 0）。** 設定只開
   vendor collection 所在的滑鼠複合介面（Usage Page `0x08` /
   Usage `0x4B`）。搶走介面 0 會讓打字中斷。
4. **不可把 Z15/Z20 的 792-byte report 6 原封不動丟給 Z12。**
   Z12 的 report 6 只有 32 bytes。長度不符的封包有變磚風險。
5. **不自動 commit、不自動 push。** 完成後只輸出變更摘要。
6. **新程式碼必須乾淨編譯 / 通過 linter。** 選定語言後把 gate 寫死
   （C：`-Wall -Werror`；Python：`ruff` 或專案約定）。
7. **協定常數與 VID/PID 寫進原始碼前，必須能對上**
   [`docs/research.md`](docs/research.md) 的實機擷取。

---

## 派工與停損

1. 派工門檻：預估要讀超過 5 個檔案或 50KB、或需要掃整個目錄時，
   派 subagent，主對話只收結論；低於門檻自己做。
   - 正例：對照 OpenRGB Z15 控制器 + 本機 HID descriptor + 未來的
     USBPcap 擷取，整理完整封包對照表。
   - 反例：確認 VID/PID 是不是 `3842:2612` → 自己讀，不派工。
2. 派工三件套：每次派 subagent 必須寫明 (1) 目標與動機 (2) 驗收條件
   (3) 回報格式——只回結論 + 檔案:行號，長產物落檔傳路徑。
3. 停損線：同一子任務用同一種方法連錯兩次，停止重試；
   帶完整失敗軌跡（做了什麼、錯誤訊息、已排除什麼）回報使用者，
   不得換個小花樣試第三次。
4. **外部 repo 先 clone 檢查有無實際原始碼，別被 commit 數 / star 數 /
   README 行銷文騙。** 反例（2026-08-16）：`erik-berger350/evga-z12-keys-linux`
   假「132 commits」實為垃圾時間戳 + XOR 混淆的 Roblox 作弊注入器下載頁，
   web_search 摘要把它描述成「較成熟」是錯的。不要自動下載或執行外部
   repo 的 release / GitHub Pages 連結。詳見
   [`docs/troubleshooting.md`](docs/troubleshooting.md)。

---

## 專案目的（給 agent 的一句話）

做一個類似 RatSlap 的開源 CLI：在 macOS（與 Linux）上設定 EVGA Z12，
把設定寫進鍵盤 onboard memory，拔到別台電腦仍然有效。

優先順序：

1. ~~安全探測：只讀 GET_FEATURE，確認 report 4/6/7 是否走 `0xEA 0x02`
   家族協定。~~ → **2026-08-16 完成**。report 4/7/9/10 已實機驗證。
2. ~~讀寫設定檔 / 目前模式（讀）。~~ → GetProfile + report 7 LED 讀取完成。
3. ~~按鍵重新映射（讀 + SET_FEATURE 寫入驗證）。~~ → CLI
   `keymap get/dump/set`（2026-08-16 實機：E5→F13→還原 macro#3）。
4. ~~CLI 唯讀整合。~~ → **2026-08-16 完成**（`src/z12ctl.py`）。
5. ~~存檔命令格式（profile=0）。~~ → CLI `profile save`；拔插後仍在。
6. CLI 寫入子命令：~~keymap set / profile save~~ 完成。巨集 / LED /
   SetProfile 尚未做。
7. 五區 RGB 寫入（report 6 在 macOS 讀不到，改走 report 7）。

---

## 硬體事實（2026-08-15 本機實測）

| 項目 | 值 |
|------|----|
| 裝置 | EVGA Z12 Gaming Keyboard（薄膜、五區 RGB，非單鍵 RGB） |
| 料號 | `834-W0-12US-KR` |
| USB VID:PID | `3842:2612` |
| bcdDevice | `0xA01D` |
| 速度 | USB 2.0 Full Speed 12 Mb/s，500 mA |
| 序號 | 無（`iSerialNumber = 0`） |
| HID 介面數 | 3 |
| 官方軟體 | EVGA Unleash RGB（Windows only） |
| Onboard 設定檔 | 最多 9 組（評測記載，尚未用封包證實） |
| OpenRGB | Z12 issue [#2670](https://gitlab.com/CalcProgrammer1/OpenRGB/-/issues/2670) 仍開著；Z15/Z20 RGB 已支援 |

三個 HID 介面：

| 介面 | 角色 | 重點 |
|------|------|------|
| 0 | Boot keyboard | 標準 6KRO 打字。另有 16-byte vendor feature（page `0xFF00` / usage `0x80`）。**不要占用。** |
| 1 | Mouse + Consumer + System + **vendor 0x08/0x4B** | **設定通道。** Feature report 4/5/6/7/8/9/0x0A/0x0F。 |
| 2 | NKRO keyboard | Report ID `0x10` 的擴充鍵盤；幾乎沒有 feature。 |

介面 1 的 vendor collection 與 OpenRGB 偵測 Z15/Z20 用的
`REGISTER_HID_DETECTOR_IPU(..., 0x3842, pid, interface, 0x08, 0x4B)`
是同一個 usage。Z12 只是 PID 不同、report 6 比較短。

---

## 可行性結論

**可以自己做。** 不是從零猜協定：

- 打字在 macOS 已經可用（標準 HID，不需要驅動）。
- 設定走 HID feature report，不需要 kernel extension。
- Z15/Z20 的 RGB 協定已被 OpenRGB 還原（magic `0xEA`，report 4 = 17
  bytes、report 7 = 136 bytes，與 Z12 descriptor 長度一致）。
- 按鍵映射 / 巨集 **沒有** 現成開源實作，必須靠 Windows 上對 Unleash
  做 USB sniff（USBPcap + Wireshark），或先做只讀探測再 decod。
- 設定寫進 onboard memory 後跟著鍵盤走，Mac / Windows 都有效。
  但若某台 Windows 裝了 Unleash，它可能覆寫 onboard 設定。

詳見 [`docs/research.md`](docs/research.md)。

---

## 建議技術選型

協定還原期用 **Python 3 + hidapi**（迭代快、封包 hex dump 方便）。
穩定後如果要做成 RatSlap 風格的單一 CLI，再考慮 C + hidapi。

不要用 libusb 去 detach macOS 的 keyboard kernel driver。

macOS 開 HID 裝置需要「輸入監控」（Input Monitoring）權限。開錯介面
會讓鍵盤暫時沒反應，拔插 USB 可恢復。

---

## 跨平台按鍵映射

設定寫在鍵盤裡，換電腦不用重設。修飾鍵的 **HID 碼** 在不同 OS 意義不同：

| HID 修飾鍵 | macOS | Windows | 跨平台？ |
|------------|-------|---------|----------|
| `LeftCtrl` | ⌃ Ctrl | Ctrl | 是 |
| `LeftShift` | ⇧ Shift | Shift | 是 |
| `LeftAlt` | ⌥ Option | Alt | 是（快捷鍵語意可能不同） |
| `Left GUI` / Super | ⌘ Command | Win | **否** |

跨平台組合請用 `LeftCtrl+C/V/X/Z`，不要用 Super/Win/Cmd。
只給自己 Mac 用時，才把巨集鍵設成 Command 組合。

---

## 文件維護

| 級別 | 範圍 | 規則 |
| ---- | ---- | ---- |
| 可自行修改 | README 使用說明、research 裡的實測數據、INDEX | 事實性內容，改完在回報列出 |
| 改前必須先問 | 上面「不可違反的規則」、派工與停損 | 即使只是精簡措辭也要先問 |
| 只准追加 | 各文件的 `NEED_REVIEW` 標記 | 認為過時就標「建議歸檔」並提報，不得直接刪 |

完整事故經過追加到 `docs/troubleshooting.md`（檔案尚不存在就新建）。
同類坑第二次發生、或屬高風險（送錯封包、鍵盤斷線、設定被清掉）時，
在本檔對應規則後追加一行反例。

路徑檢查：例行維護時驗證本檔與 README 提到的路徑是否存在。

---

## 還沒有的東西（不要假裝存在）

- ~~沒有 `src/`、沒有 Makefile、沒有測試。~~ → 2026-08-16 新增 `src/`
  目錄：`evga_z12/` 函式庫、`z12ctl.py` 唯讀 CLI、以及探測腳本
  （`probe_*.py` / `scan_positions.py` / `test_write.py`）。Python 3
  + hidapi，`.venv/`。仍沒有 Makefile、沒有自動化測試。lint 用 ruff
  （`pyproject.toml`）。
- 沒有獨立 git remote（目前只是資料夾）。
- ~~沒有完整按鍵映射表~~ → 2026-08-16 完成。121 鍵 position 表 + 軟體
  逆向 + 實機掃描，見 [`docs/key-position-table.md`](docs/key-position-table.md)
  和 [`docs/keymap-scan-result.md`](docs/keymap-scan-result.md)。
- ~~沒有對 Z12 送過任何設定封包。~~ → GET_FEATURE（report 4/7/9/10）
  和 SET_FEATURE（report 4 keymap Write + SaveProfile）都已驗證。
  CLI 已有 `keymap set` 與 `profile save`。report 6/8 在 macOS hidapi
  上讀不到。巨集寫入尚未做成 CLI。
