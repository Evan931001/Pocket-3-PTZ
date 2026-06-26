# GitHub Copy / GitHub 開源文案

Ready-to-paste text for publishing on GitHub. 直接複製貼上即可。

---

## Repository name / 名稱
```
pocket3-usb-ptz
```

## About (one line) / 簡介
EN:
```
Turn a DJI Osmo Pocket 3 into a remote-controllable PTZ camera over USB-C — OBS dock panel, joystick GUI, and Bitfocus Companion support.
```
中文：
```
把 DJI Osmo Pocket 3 透過 USB-C 變成可遙控的 PTZ 攝影機 — OBS 面板、搖桿 GUI、Bitfocus Companion 都能控。
```

## Topics / 標籤
```
dji  osmo-pocket-3  ptz  ptz-camera  obs  obs-studio  bitfocus-companion
directshow  uvc  camera-control  python  broadcast  webcam  live-streaming
```

---

## Intro paragraph / 介紹段落

EN:
> **Pocket 3 USB-C PTZ Control**
>
> The DJI Osmo Pocket 3 has no official wired remote pan/tilt/zoom solution. This project
> uses Windows DirectShow UVC camera control (the path behind OBS's "Camera Control" sliders)
> to drive the Pocket 3's pan / tilt / zoom in real time over a single USB-C cable — **without
> taking over the video stream**, so you can output the camera in OBS and control the gimbal at once.
>
> Four ways to operate: an OBS browser-dock panel with an analog joystick, a standalone joystick
> GUI (with a 中文/English switch), numpad control, and an OBS native-hotkey script. A built-in
> local HTTP API plugs straight into Bitfocus Companion / Stream Deck for one-tap preset recall.
>
> Pure Python, no compiling. Bluetooth (BLE/DUML) cannot control the gimbal on the Pocket 3, so
> this project takes the working UVC route.

中文：
> **Pocket 3 USB-C PTZ 控制**
>
> DJI Osmo Pocket 3 沒有官方的有線遙控雲台方案。本專案利用 Windows DirectShow 的 UVC 相機控制
> （OBS「相機控制」滑桿背後那條路），用一條 USB-C 線即時控制 pan / tilt / zoom，**且不佔用影像串流**
> ——可一邊用 OBS 出畫面、一邊遙控雲台。
>
> 四種操作：嵌進 OBS 的網頁面板（含類比搖桿）、獨立搖桿 GUI（含中／英切換）、小鍵盤控制、
> OBS 原生快捷鍵腳本。內建本機 HTTP API，可直接接 Bitfocus Companion / Stream Deck，做「一鍵叫機位」。
>
> 純 Python、免編譯。藍牙（BLE/DUML）在 Pocket 3 上無法控制雲台，因此走 UVC 這條可行路線。

---

## First release / 第一個 Release

**Tag:** `v1.0.0`
**Title:** `v1.0.0 — First public release / 首個公開版本`

**Notes (EN):**
```
First public release.

Features
- Real-time pan / tilt / zoom over USB-C / UVC (DirectShow IAMCameraControl)
- Does not take over the video stream; coexists with OBS
- OBS custom browser dock: analog joystick, center, zoom, sensitivity
- Standalone GUI: joystick, customizable keys, live values, 中文/English switch
- Numpad / arrow-key control, plus an OBS native-hotkey script
- Local HTTP API for Bitfocus Companion / Stream Deck
- Preset save/recall with smooth move-to-position
- Deadzone + response curve + velocity smoothing; adjustable sensitivity
- GUI and OBS panel share one config (sensitivity / center angle / camera)

Requirements
- Windows + Python 3.12 (64-bit)
- pip install pygrabber comtypes keyboard
- Pocket 3 in Webcam mode

Known limits
- ActiveTrack cannot be triggered over USB (DJI restriction)
- Zoom is digital
```

**Notes (中文):**
```
首個公開版本。

功能
- USB-C / UVC（DirectShow IAMCameraControl）即時控制 pan / tilt / zoom
- 不佔用影像串流，可與 OBS 並存
- OBS 自訂瀏覽器面板：類比搖桿、回正、Zoom、靈敏度
- 獨立 GUI：搖桿、可自訂按鍵、即時數值、中／英切換
- 小鍵盤 / 方向鍵控制，及 OBS 原生快捷鍵腳本
- 本機 HTTP API：可接 Bitfocus Companion / Stream Deck
- 機位（preset）儲存／叫出，叫出時平滑移動到位
- 死區 + 反應曲線 + 速度平滑，靈敏度可調
- GUI 與 OBS 面板共用設定（靈敏度／回正角度／相機）

環境需求
- Windows + Python 3.12（64-bit）
- pip install pygrabber comtypes keyboard
- Pocket 3 進 Webcam 模式

已知限制
- ActiveTrack 無法透過 USB 觸發（DJI 限制）
- 變焦為數位變焦
```

---

## Social preview / 社群預覽圖（可選）
Settings → General → Social preview，上傳 1280×640 的圖（例如 Pocket 3 + OBS 面板截圖）。

## One-line post / 一句話推文
EN:
```
Built a USB-C wired PTZ remote for the DJI Osmo Pocket 3 — control it from an OBS dock, a joystick GUI, or a Stream Deck, with one-tap preset recall. Pure Python, open source.
```
中文：
```
幫 DJI Osmo Pocket 3 做了 USB-C 有線 PTZ 遙控，OBS 面板 / 搖桿 GUI / Stream Deck 都能控，還能存機位一鍵叫出。純 Python，開源。
```
