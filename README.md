# Pocket 3 PTZ Control (USB-C / UVC)

**English** | [繁體中文](#中文說明)



https://github.com/user-attachments/assets/bf871656-94cc-4690-b375-86fd611c2984





Turn a DJI Osmo Pocket 3 into a remote-controllable PTZ camera over a single
USB-C cable. It uses Windows DirectShow UVC camera control (the same path behind
OBS's "Camera Control" sliders) to drive pan / tilt / zoom in real time —
**without taking over the video stream**, so you can output the camera in OBS and
control the gimbal at the same time. Bluetooth (BLE/DUML) does **not** work for
gimbal control on the Pocket 3, which is why this project uses the UVC route.

## 1. Setup (once per machine)

1. **Install Python 3.12 (64-bit)** from https://www.python.org/downloads/ and
   tick **"Add Python to PATH"**. (The OBS native-script option only accepts 3.12.)
2. **Install packages:**
   ```
   pip install pygrabber comtypes keyboard
   ```
3. **Connect the camera:** plug the Pocket 3 in via USB-C and choose **Webcam mode**
   on the camera screen.

## 2. Four ways to use it

### A. OBS dock panel (recommended)
1. Double-click `start-ptz.bat`. A console shows "PTZ panel started" and auto-connects.
   **Keep that window open** (it is the control core).
2. In OBS: **Docks → Custom Browser Docks**, add one with URL:
   ```
   http://127.0.0.1:8723/
   ```
3. A panel appears inside OBS with an analog joystick, Center, Zoom, and Sensitivity.

### B. Standalone GUI
Double-click `start-gui.bat`, or:
```
python uvc-gui.py
```
Analog joystick, live values, customizable keys (click a key button, then press a key),
and a **language switch (中文 / English)** in the top-right.

> **Shared settings:** the GUI and the OBS panel share `ptz-config.json`, so sensitivity,
> center angle, and the chosen camera carry over. Custom keys are GUI-only (the panel uses buttons).

### C. Numpad control
```
python uvc-numpad.py
```
Numpad: `8/2/4/6` = tilt/pan, `5` = center, `7/9` = zoom, `+/-` = speed, `/` = quit.

### D. OBS native hotkeys
Load `pocket-ptz-obs.py` via OBS **Tools → Scripts** (first point Python Settings at your
Python 3.12 folder; the bottom line must read `Python 3.12.x`). Assign keys under
**Settings → Hotkeys**, search "Pocket".

## 3. Troubleshooting
- **Camera not auto-detected / wrong camera:** every tool lets you pick manually —
  the OBS panel has a camera dropdown + ⟳ rescan button at the top; the GUI has a device
  dropdown; `uvc-numpad.py` / `uvc-smooth.py` list all devices and ask you to type an index
  (or pass one: `python uvc-numpad.py 2`); the OBS script has a device list in its properties.
  Your choice is saved to `ptz-config.json`.
- **No camera / empty list:** confirm Webcam mode; confirm `pygrabber comtypes` are installed
  in the Python you actually use.
- **Connected but nothing moves:** run `python uvc-ptz2.py` to probe supported pan/tilt/zoom ranges.
- **OBS script shows "No properties available":** Python Settings still says "not loaded" — point it
  at the folder containing `python.exe`; it must show `Python 3.12.x`.
- **Center / Home:** "Home" is a remembered position, not a fixed angle (the camera's UVC units
  aren't real degrees). Aim the camera where you want, click **Set current as home** (GUI) or
  **Set home** (OBS panel), and **Center** returns there. Saved in `ptz-config.json` and shared
  between the GUI and the OBS panel.

## 4. Limitations
- **ActiveTrack cannot be triggered over USB** (a DJI restriction). Tap the subject on the camera screen.
- **Zoom is digital**, same as the camera itself.

## 5. Publish to GitHub
This folder already includes `.gitignore` (ignores each machine's `ptz-config.json`) and `LICENSE`.
> Edit `LICENSE` and replace `[your name or GitHub handle]` first.

1. On github.com → **New repository** (e.g. `pocket3-usb-ptz`), do **not** add a README, click Create.
2. In this folder, run (swap in your URL):
   ```
   git init
   git add .
   git commit -m "Pocket 3 USB-C PTZ control"
   git branch -M main
   git remote add origin https://github.com/<you>/pocket3-usb-ptz.git
   git push -u origin main
   ```
3. Later changes: `git add . && git commit -m "..." && git push`

## Files
| File | Purpose |
|------|---------|
| `ptz-server.py` | Background control program + web panel (for the OBS browser dock) |
| `start-ptz.bat` | Double-click launcher for `ptz-server.py` |
| `uvc-gui.py` | Standalone GUI (joystick, custom keys, language switch) |
| `start-gui.bat` | Double-click launcher for `uvc-gui.py` |
| `uvc-numpad.py` | Numpad control |
| `uvc-smooth.py` | Arrow-key control (smoothed) |
| `uvc-ptz2.py` | Probe tool: lists supported controls and ranges |
| `pocket-ptz-obs.py` | OBS native-hotkey script |
| `COMPANION.md` | Bitfocus Companion / Stream Deck guide |

<img width="890" height="464" alt="螢幕擷取畫面 2026-06-26 130740" src="https://github.com/user-attachments/assets/f09175b9-d679-4926-a7c5-a8dd82ba7b87" />

---

<a name="中文說明"></a>
# Pocket 3 PTZ 控制（USB-C / UVC）

[English](#pocket-3-ptz-control-usb-c--uvc) | **繁體中文**

把 DJI Osmo Pocket 3 透過一條 USB-C 線變成可遙控的 PTZ 攝影機。走的是 Windows DirectShow 的
UVC 相機控制（也就是 OBS「相機控制」滑桿背後那條路），即時控制 pan / tilt / zoom，
**而且不佔用影像串流**——可以一邊用 OBS 出畫面、一邊遙控雲台。藍牙（BLE/DUML）在 Pocket 3
上實測無法控制雲台，因此本專案走 UVC 這條可行路線。

## 一、安裝（每台機器一次）

1. **裝 Python 3.12（64-bit）**，到 https://www.python.org/downloads/ 下載，安裝時勾「Add Python to PATH」。
   （OBS 原生腳本那個選項只吃 3.12。）
2. **裝套件：**
   ```
   pip install pygrabber comtypes keyboard
   ```
3. **接相機：** Pocket 3 用 USB-C 接電腦，相機螢幕點進 **Webcam 模式**。

## 二、四種用法

### A. OBS 控制面板（最推薦）
1. 雙擊 `start-ptz.bat`，黑視窗顯示「PTZ 控制面板已啟動」並自動連線。**這個視窗要一直開著**（它是控制核心）。
2. OBS：「停駐視窗 → 自訂瀏覽器停駐視窗」，新增一個，網址：
   ```
   http://127.0.0.1:8723/
   ```
3. OBS 裡會出現含類比搖桿、回正、Zoom、靈敏度的面板。

### B. 獨立 GUI
雙擊 `start-gui.bat`，或：
```
python uvc-gui.py
```
類比搖桿、即時數值、可自訂按鍵（按按鍵後再按下要綁定的鍵），右上有**語言切換（中文 / English）**。

> **設定共用：** GUI 與 OBS 面板共用 `ptz-config.json`，靈敏度、回正角度、選的相機會沿用。
> 自訂按鍵為 GUI 專屬（面板用畫面按鈕）。

### C. 小鍵盤控制
```
python uvc-numpad.py
```
小鍵盤：`8/2/4/6`=tilt/pan、`5`=回正、`7/9`=zoom、`+/-`=速度、`/`=離開。

### D. OBS 原生快捷鍵
把 `pocket-ptz-obs.py` 用 OBS「工具 → 指令碼」載入（先在 Python 設定頁指到 Python 3.12 資料夾，
下面要顯示 `Python 3.12.x`）。到「設定 → 快捷鍵」搜尋「Pocket」指定按鍵。

## 三、疑難排解
- **沒自動抓到相機 / 抓錯台：** 每個工具都能手動選——OBS 面板頂端有相機下拉選單＋⟳重新偵測；
  GUI 有裝置下拉選單；`uvc-numpad.py` / `uvc-smooth.py` 會列出所有裝置請你輸入編號
  （也可直接帶入：`python uvc-numpad.py 2`）；OBS 腳本的屬性裡也有裝置清單。選擇會存進 `ptz-config.json`。
- **找不到相機 / 清單空的：** 確認在 Webcam 模式；確認 `pygrabber comtypes` 裝在你實際用的那個 Python。
- **連到了但按了不動：** 跑 `python uvc-ptz2.py` 看 pan/tilt/zoom 支援與範圍。
- **OBS 腳本顯示「無可用的屬性」：** Python 設定頁還是「未載入」——要指到含 `python.exe` 的資料夾，看到 `Python 3.12.x` 才對。
- **回正 / 回正點：** 「回正點」是記住的位置，不是固定角度（這台相機的 UVC 數值不是真實角度）。
  把鏡頭轉到想要的位置，按 **設為目前位置**（GUI）或 **設回正點**（OBS 面板），之後按 **回正** 就回到那裡。
  存在 `ptz-config.json`，GUI 與 OBS 面板共用。

## 四、限制
- **ActiveTrack 無法透過 USB 觸發**（DJI 限制），請在相機螢幕點主體。
- **變焦為數位變焦**，與相機本身一致。

## 五、上傳到 GitHub
本資料夾已含 `.gitignore`（忽略各機器自己的 `ptz-config.json`）與 `LICENSE`。
> 先把 `LICENSE` 裡的 `[your name or GitHub handle]` 改成你的名字。

1. github.com → **New repository**（例如 `pocket3-usb-ptz`），**不要**勾 Add README，按 Create。
2. 在這個資料夾執行（網址換成你的）：
   ```
   git init
   git add .
   git commit -m "Pocket 3 USB-C PTZ 控制工具"
   git branch -M main
   git remote add origin https://github.com/你的帳號/pocket3-usb-ptz.git
   git push -u origin main
   ```
3. 之後改動：`git add . && git commit -m "說明" && git push`

## 檔案
| 檔案 | 用途 |
|------|------|
| `ptz-server.py` | 背景控制程式＋網頁面板（給 OBS 自訂瀏覽器停駐視窗） |
| `start-ptz.bat` | 雙擊啟動 `ptz-server.py` |
| `uvc-gui.py` | 獨立 GUI（搖桿、可自訂按鍵、語言切換） |
| `start-gui.bat` | 雙擊啟動 `uvc-gui.py` |
| `uvc-numpad.py` | 小鍵盤控制 |
| `uvc-smooth.py` | 方向鍵控制（平滑版） |
| `uvc-ptz2.py` | 探測工具：列出支援的控制項與範圍 |
| `pocket-ptz-obs.py` | OBS 原生快捷鍵腳本 |
| `COMPANION.md` | Bitfocus Companion / Stream Deck 指南 |

<img width="834" height="466" alt="螢幕擷取畫面 2026-06-26 130744" src="https://github.com/user-attachments/assets/49aff2ae-dec9-43d7-88c1-c22a05b807aa" />

