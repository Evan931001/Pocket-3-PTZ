# Bitfocus Companion Integration

**English** | [繁體中文](#接-bitfocus-companion)

`ptz-server.py` exposes an HTTP API, so Companion can drive the gimbal using its
built-in **Generic HTTP** module. No extra module needed.

> Requirements: `start-ptz.bat` (the background program) must be running.
> Same PC as OBS → use `127.0.0.1`. Companion on a **different PC** → the server must be
> opened to the network (ask and I'll switch the bind to `0.0.0.0`); use that PC's LAN IP.

## 1. Add the Generic HTTP connection
Companion web UI → **Connections** → search **HTTP** → add "Generic: HTTP requests".
In its config, set **Base URL** to `http://127.0.0.1:8723` so buttons only need the path.

## 2. Endpoints (GET)
| Action | URL |
|--------|-----|
| Pan left (hold) | `/vel?pan=-1` |
| Pan right (hold) | `/vel?pan=1` |
| Tilt up (hold) | `/vel?tilt=1` |
| Tilt down (hold) | `/vel?tilt=-1` |
| Zoom in (hold) | `/vel?zoom=1` |
| Zoom out (hold) | `/vel?zoom=-1` |
| Stop an axis | `/vel?pan=0` (same for tilt/zoom) |
| Nudge one step | `/nudge?pan=-1` (tilt/zoom too; value can be ±) |
| Center (go to home) | `/center` |
| Set current pos as home | `/sethome` |
| Recall preset 1 | `/preset/recall?n=1` |
| Save preset 1 | `/preset/save?n=1` |
| Set sensitivity 20% | `/speed?v=0.2` |

## 3. Button setup

### Style A — hold to move (best feel)
One button needs two action groups — **Press** and **Release**:
- e.g. "Pan left": Press → GET `/vel?pan=-1`; Release → GET `/vel?pan=0`.
- Do the same for tilt/zoom (Release is always `=0`).

### Style B — tap to step (easiest, no Release)
One **Press** action only: GET `/nudge?pan=-1`. Good for fine trims; hold-tapping repeats.

### Presets — the killer feature for live work
- **Recall** button: Press → `/preset/recall?n=1` (smoothly moves to the saved angle).
- **Save** button: aim the gimbal, then press `/preset/save?n=1` (stored in `ptz-config.json`, persists).
  Tip: put save buttons on a separate page so you don't overwrite presets mid-show.

### Center / sensitivity
- Center: Press → `/center`
- Sensitivity steps: buttons calling `/speed?v=0.1`, `/speed?v=0.3`, `/speed?v=0.6` for slow/medium/fast.

## 4. FAQ
- **Nothing happens:** confirm `start-ptz.bat` is running and connected; opening `http://127.0.0.1:8723/`
  in a browser should show the panel.
- **Companion on another PC:** the server must be opened to the network and you use its LAN IP.
- **Preset moves too fast/slow:** preset move speed in `ptz-server.py` is "60%/sec of full range"; adjustable.

---

<a name="接-bitfocus-companion"></a>
# 接 Bitfocus Companion

[English](#bitfocus-companion-integration) | **繁體中文**

`ptz-server.py` 提供 HTTP 介面，Companion 用內建的 **Generic HTTP** 模組打網址就能控雲台。不用裝額外模組。

> 前提：`start-ptz.bat`（背景程式）要在跑。
> 與 OBS 同一台 → 用 `127.0.0.1`。Companion 在**另一台電腦** → 伺服器要對外開放（跟我說，我把綁定改成 `0.0.0.0`），網址換成那台的區網 IP。

## 一、加入 Generic HTTP 連線
Companion 網頁 → **Connections** → 搜尋 **HTTP** → 加「Generic: HTTP requests」。
在設定裡把 **Base URL** 填 `http://127.0.0.1:8723`，按鈕只要打後半段網址。

## 二、端點一覽（GET）
| 動作 | 網址 |
|------|------|
| Pan 左（持續） | `/vel?pan=-1` |
| Pan 右（持續） | `/vel?pan=1` |
| Tilt 上（持續） | `/vel?tilt=1` |
| Tilt 下（持續） | `/vel?tilt=-1` |
| Zoom 放大（持續） | `/vel?zoom=1` |
| Zoom 縮小（持續） | `/vel?zoom=-1` |
| 停止某軸 | `/vel?pan=0`（tilt/zoom 同理） |
| 點一下走一步 | `/nudge?pan=-1`（tilt/zoom 同理；數字可±） |
| 回正（回到回正點） | `/center` |
| 設目前位置為回正點 | `/sethome` |
| 叫出機位 1 | `/preset/recall?n=1` |
| 儲存機位 1 | `/preset/save?n=1` |
| 設靈敏度 20% | `/speed?v=0.2` |

## 三、按鈕設定

### 方式 A — 按住連續移動（手感最好）
一顆按鈕要設兩組動作——**按下(Press)** 與 **放開(Release)**：
- 例「Pan 左」：Press → GET `/vel?pan=-1`；Release → GET `/vel?pan=0`。
- tilt/zoom 比照（Release 一律 `=0`）。

### 方式 B — 點一下走一步（最好設，免 Release）
一顆只放一個 **Press** 動作：GET `/nudge?pan=-1`。適合微調，連點會連續走。

### 機位（Preset）— 直播最實用
- **叫出**按鈕：Press → `/preset/recall?n=1`（平滑移動到位）。
- **儲存**按鈕：先把雲台轉到想要的角度，再按 `/preset/save?n=1`（存到 `ptz-config.json`，重開也在）。
  建議把儲存按鈕另放一頁，避免直播時誤觸覆蓋。

### 回正 / 靈敏度
- 回正：Press → `/center`
- 靈敏度檔位：做幾顆按鈕打 `/speed?v=0.1`、`/speed?v=0.3`、`/speed?v=0.6` 當慢/中/快。

## 四、常見問題
- **按了沒反應：** 確認 `start-ptz.bat` 開著且已連線；瀏覽器開 `http://127.0.0.1:8723/` 看得到面板就代表伺服器活著。
- **Companion 在別台電腦：** 伺服器要對外開放並用區網 IP。
- **叫機位移動太快/太慢：** `ptz-server.py` 裡 preset 移動速度是「全程 60%/秒」，可調。
