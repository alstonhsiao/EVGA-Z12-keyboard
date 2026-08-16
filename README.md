# EVGA Z12 config tool

**Status: 0.1.0-alpha.** Experimental. Tested on one macOS machine with one
keyboard (`3842:2612`). Not a replacement for EVGA Unleash RGB.

Configure an [EVGA Z12](https://www.evga.com/products/product.aspx?pn=834-W0-12US-KR)
from macOS (Linux untested) using HID feature reports. Settings are stored
**on the keyboard**, so they follow the device to another computer.

Official Unleash RGB is Windows-only. This tool can read and write keymap,
short macros, profiles, and LED *modes*. It does **not** update firmware.

---

# 中文

**0.1.0-alpha。** 實驗性質。只在一台 Mac、一把 `3842:2612` 上驗證過。
不是 Unleash 的完整替代品。設定寫在鍵盤 onboard，拔到別台電腦仍然有效。

## 風險（寫入前請讀）

- 寫入會立刻改鍵盤 RAM；`--save` / `profile save` 會寫進 flash。
- 改錯 keymap 可能讓某些鍵沒反應。先 `keymap get` / `keymap dump`，記下原值。
- **不要**做韌體更新。本專案沒有、也不會提供刷機。
- 只開 HID **介面 1**（vendor `0x08` / `0x4B`）。不要搶 boot keyboard（介面 0）。
- 作者不保證你的鍵盤不會被改亂。自用風險自負。

## 已測硬體

```
VID:PID     3842:2612
Product     EVGA Z12 Gaming Keyboard
bcdDevice   0xA01D
```

UK 版 `3842:2622`、Linux、Z15/Z20 **未測**。

## 安裝（macOS）

需要 Python 3.10+、Homebrew 的 hidapi，以及系統「輸入監控」權限。

```bash
brew install hidapi
git clone https://github.com/alstonhsiao/EVGA-Z12-keyboard.git
cd EVGA-Z12-keyboard
python3 -m venv .venv
.venv/bin/pip install hid
```

第一次執行若打不開裝置：

**系統設定 → 隱私權與安全性 → 輸入監控**，勾選你用來跑 Python / Terminal 的 App。

```bash
.venv/bin/python src/z12ctl.py info
```

應看到 `VID:PID 0x3842:0x2612` 與介面 1。

## 常用命令

```bash
.venv/bin/python src/z12ctl.py info
.venv/bin/python src/z12ctl.py keymap dump
.venv/bin/python src/z12ctl.py keymap get E5
.venv/bin/python src/z12ctl.py keymap set E5 F13          # RAM only
.venv/bin/python src/z12ctl.py keymap set E5 F13 --save   # RAM + flash
.venv/bin/python src/z12ctl.py profile get
.venv/bin/python src/z12ctl.py profile set 2
.venv/bin/python src/z12ctl.py profile save
.venv/bin/python src/z12ctl.py macro list
.venv/bin/python src/z12ctl.py macro get 3
.venv/bin/python src/z12ctl.py macro set 3 --name hello z
.venv/bin/python src/z12ctl.py led get
.venv/bin/python src/z12ctl.py led set StaticOn --sub 2
.venv/bin/python src/z12ctl.py led set RainbowWave --sub 2 --save
```

`keymap set` 的 binding 例如：`F13`、`LCtrl+C`、`disable`、`macro:3`、`Mute`。  
`macro set` 目前只接受**單鍵 tap**（`z`、`F13`）。已有資料的槽要加 `--force`。  
`profile set` 會載入該號 flash；RAM 裡還沒 `save` 的修改會丟掉。

## 能做 / 還不能做

| 可以 | 還沒有 |
|------|--------|
| 讀寫 121 鍵 keymap | 巨集刪除、組合鍵巨集、滑鼠巨集 |
| 存檔到 flash（`profile save`） | 重置 profile |
| 切換 profile 1–9 | LED 顏色 / 速度（只能切模式） |
| 切 LED 模式（Off / Static / Rainbow…） | report 6/8（macOS hidapi 讀不到） |
| 寫短巨集並 onboard 播放 | 自動化測試、Linux 實測 |
| | 改 GameMode / FN 角色（刻意拒絕） |

## 文件

| 檔案 | 內容 |
|------|------|
| [`docs/research.md`](docs/research.md) | 實機協定與測試紀錄 |
| [`AGENTS.md`](AGENTS.md) | 給開發 agent 的規則（含不可亂送封包） |
| [`docs/troubleshooting.md`](docs/troubleshooting.md) | 惡意 repo、HID 快取等教訓 |

## 授權

[MIT](LICENSE)。沒有保固。

---

# English

**0.1.0-alpha.** Experimental CLI for the EVGA Z12 on macOS. Settings live
in onboard memory. Not a full Unleash replacement. Firmware updates are
out of scope.

### Risks

Writes change the keyboard immediately. `--save` persists them across
unplug. Dump bindings before you change them. Do not flash firmware.
Only open HID interface 1. No warranty.

### Install (macOS)

```bash
brew install hidapi
git clone https://github.com/alstonhsiao/EVGA-Z12-keyboard.git
cd EVGA-Z12-keyboard
python3 -m venv .venv
.venv/bin/pip install hid
```

Grant **Input Monitoring** to Terminal (or your Python app), then:

```bash
.venv/bin/python src/z12ctl.py info
```

Tested only on `3842:2612`. PID `2622` and Linux are untested.

### What works

Keymap read/write, profile get/set/save, LED *mode* switch, short
onboard macros (plain key taps). See the Chinese command list above
(same commands).

License: [MIT](LICENSE).
