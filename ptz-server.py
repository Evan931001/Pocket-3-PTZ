#!/usr/bin/env python3
# ============================================================================
# ptz-server.py — 背景控制程式 + 網頁面板（給 OBS 自訂瀏覽器停駐視窗用）
#
# 背景用 DirectShow IAMCameraControl 控 Pocket 3 雲台（不開串流，與 OBS 並存），
# 同時在 http://127.0.0.1:8723/ 提供一個控制面板網頁。
#
# 安裝：pip install pygrabber comtypes
# 執行：python ptz-server.py     （保持這個視窗開著）
# OBS：停駐視窗 → 自訂瀏覽器停駐視窗 → 網址填 http://127.0.0.1:8723/
# ============================================================================

import os
import time
import json
import threading
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ctypes import HRESULT, POINTER, c_long
from comtypes import COMMETHOD, GUID, IUnknown, COMError
import comtypes

# 與 uvc-gui.py 共用的設定檔（速度 / 回正角度 / 相機）
CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ptz-config.json")


def load_cfg():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cfg(updates):
    try:
        cur = load_cfg()
        cur.update(updates)
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(cur, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


PORT = 8723
VIDEO_CATEGORY = "{860BB310-5D01-11D0-BD3B-00A0C911CE86}"
FLAG_MANUAL = 0x0002
PAN, TILT, ZOOM = 0, 1, 3
UNITS_PER_DEG = 3600
DT = 0.025
ZOOM_SPEED = 0.40
DEADZONE = 0.06      # 搖桿死區（避免手抖/回中漂移）
EXPO = 1.6           # 反應曲線：中間輕推細膩，邊緣才全速


class IAMCameraControl(IUnknown):
    _iid_ = GUID("{C6E13370-30AC-11D0-A18C-00A0C9118956}")


IAMCameraControl._methods_ = [
    COMMETHOD([], HRESULT, "GetRange",
              (["in"], c_long, "Property"),
              (["out"], POINTER(c_long), "pMin"), (["out"], POINTER(c_long), "pMax"),
              (["out"], POINTER(c_long), "pSteppingDelta"),
              (["out"], POINTER(c_long), "pDefault"), (["out"], POINTER(c_long), "pCapsFlags")),
    COMMETHOD([], HRESULT, "Set",
              (["in"], c_long, "Property"), (["in"], c_long, "lValue"), (["in"], c_long, "Flags")),
    COMMETHOD([], HRESULT, "Get",
              (["in"], c_long, "Property"),
              (["out"], POINTER(c_long), "lValue"), (["out"], POINTER(c_long), "Flags")),
]

# ── 共享狀態（HTTP 執行緒寫、控制執行緒讀）──────────────────────────────────
state = {
    "vel": {PAN: 0.0, TILT: 0.0, ZOOM: 0.0},
    "speed": 0.30,
    "home_deg": -90,
    "center_req": False,
    "sethome_req": False,
    "connect_req": None,
    "rescan_req": False,
    "preset_req": None,      # ("save"|"recall", n)
    "goto": None,            # 平滑移動目標 {"pan":..,"tilt":..,"zoom":..}
    "nudge": {PAN: 0.0, TILT: 0.0, ZOOM: 0.0},  # 點一下走一小步
    "devices": [],
    "connected": None,
    "device_index": None,
    "pos": {PAN: None, TILT: None, ZOOM: None},
}


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def shape(v):
    """死區 + 指數曲線：輸入 -1..1，輸出 -1..1（中間更細膩）。"""
    a = abs(v)
    if a <= DEADZONE:
        return 0.0
    a = (a - DEADZONE) / (1 - DEADZONE)
    return (a ** EXPO) * (1.0 if v > 0 else -1.0)


# ── 控制執行緒：所有相機 / COM 操作都在這條執行緒做 ──────────────────────────
def control_loop():
    comtypes.CoInitialize()
    from pygrabber.dshow_graph import SystemDeviceEnum
    cam = None
    axis = {}

    def read_devices():
        try:
            return SystemDeviceEnum().get_available_filters(VIDEO_CATEGORY)
        except Exception as e:
            print("列舉裝置失敗：", e)
            return []

    def connect(idx):
        nonlocal cam, axis
        try:
            filt, name = SystemDeviceEnum().get_filter_by_index(VIDEO_CATEGORY, idx)
            cam = filt.QueryInterface(IAMCameraControl)
        except Exception as e:
            print("連線失敗 / connect failed:", e)
            cam = None
            state["connected"] = None
            state["device_index"] = None
            return
        axis = {}
        for p in (PAN, TILT, ZOOM):
            try:
                mn, mx, st, de, ca = cam.GetRange(p)
                cur, _ = cam.Get(p)
                axis[p] = {"min": mn, "max": mx, "span": (mx - mn) or 1,
                           "pos": float(cur), "sent": int(cur)}
            except COMError:
                axis[p] = None
        state["connected"] = name
        state["device_index"] = idx
        save_cfg({"device_index": idx})
        print("已連線 / connected:", name)

    def apply(p):
        a = axis.get(p)
        if a is None or cam is None:
            return
        a["pos"] = clamp(a["pos"], a["min"], a["max"])
        iv = int(round(a["pos"]))
        if iv != a["sent"]:
            try:
                cam.Set(p, iv, FLAG_MANUAL)
                a["sent"] = iv
            except COMError:
                pass

    # 讀共用設定（GUI 調過的速度 / 回正角度會帶進來）
    cfg = load_cfg()
    if "speed" in cfg:
        state["speed"] = cfg["speed"]
    if "home_deg" in cfg:
        state["home_deg"] = cfg["home_deg"]
    presets = cfg.get("presets", {})   # {"1": {"pan":..,"tilt":..,"zoom":..}, ...}

    # 啟動：列裝置、自動連到 Pocket（優先用設定檔記住的相機）
    state["devices"] = read_devices()
    pref = cfg.get("device_index")
    auto = pref if (isinstance(pref, int) and 0 <= pref < len(state["devices"])) else \
        next((i for i, n in enumerate(state["devices"]) if "Osmo" in n or "Pocket" in n), None)
    if auto is not None:
        connect(auto)

    last_t = time.monotonic()
    applied = {PAN: 0.0, TILT: 0.0}   # 平滑後的實際速度

    while True:
        now_t = time.monotonic()
        dt = now_t - last_t
        last_t = now_t
        if dt > 0.1:        # 卡頓後不要一次跳太多
            dt = 0.1

        if state["rescan_req"]:
            state["rescan_req"] = False
            state["devices"] = read_devices()

        idx = state["connect_req"]
        if idx is not None:
            state["connect_req"] = None
            connect(idx)

        if cam:
            sp = state["speed"]
            # 手動移動時取消 preset 平滑移動
            if any(state["vel"].values()):
                state["goto"] = None
            # 速度漸進（朝目標逼近，消除起停與搖桿跳動造成的頓挫）
            resp = min(1.0, dt * 16)
            applied[PAN] += (shape(state["vel"][PAN]) - applied[PAN]) * resp
            applied[TILT] += (shape(state["vel"][TILT]) - applied[TILT]) * resp
            if axis.get(PAN) and abs(applied[PAN]) > 1e-3:
                axis[PAN]["pos"] += axis[PAN]["span"] * sp * dt * applied[PAN]
                apply(PAN)
            if axis.get(TILT) and abs(applied[TILT]) > 1e-3:
                axis[TILT]["pos"] += axis[TILT]["span"] * sp * dt * applied[TILT]
                apply(TILT)
            if axis.get(ZOOM) and state["vel"][ZOOM]:
                axis[ZOOM]["pos"] += axis[ZOOM]["span"] * ZOOM_SPEED * dt * state["vel"][ZOOM]
                apply(ZOOM)

            # nudge：點一下走一小步（全程 4%）
            for p in (PAN, TILT, ZOOM):
                nz = state["nudge"][p]
                if nz and axis.get(p):
                    state["nudge"][p] = 0.0
                    state["goto"] = None
                    axis[p]["pos"] += axis[p]["span"] * 0.04 * nz
                    apply(p)

            if state["center_req"]:
                state["center_req"] = False
                hc = load_cfg()
                hp = hc.get("home_pan")
                ht = hc.get("home_tilt")
                g = {}
                if axis.get(PAN):
                    g["pan"] = float(hp) if hp is not None else \
                        (axis[PAN]["min"] + axis[PAN]["max"]) / 2
                if axis.get(TILT):
                    g["tilt"] = float(ht) if ht is not None else \
                        (axis[TILT]["min"] + axis[TILT]["max"]) / 2
                state["goto"] = g       # 連續送指令平滑移動到位（不必先動搖桿喚醒）

            if state["sethome_req"]:
                state["sethome_req"] = False
                upd = {}
                if axis.get(PAN):
                    upd["home_pan"] = axis[PAN]["sent"]
                if axis.get(TILT):
                    upd["home_tilt"] = axis[TILT]["sent"]
                save_cfg(upd)
                print("已設回正點 / home set:", upd)

            # preset 存 / 叫
            pr = state["preset_req"]
            if pr is not None:
                state["preset_req"] = None
                action, n = pr
                key = str(n)
                if action == "save":
                    presets[key] = {nm: axis[p]["sent"]
                                    for p, nm in ((PAN, "pan"), (TILT, "tilt"), (ZOOM, "zoom"))
                                    if axis.get(p)}
                    save_cfg({"presets": presets})
                    print(f"已存 preset {key}：{presets[key]}")
                elif action == "recall" and key in presets:
                    state["goto"] = dict(presets[key])

            # preset 平滑移動到位
            g = state["goto"]
            if g:
                done = True
                for p, nm in ((PAN, "pan"), (TILT, "tilt"), (ZOOM, "zoom")):
                    if axis.get(p) and nm in g:
                        target = g[nm]
                        cur = axis[p]["pos"]
                        step = axis[p]["span"] * 0.6 * dt   # preset 移動速度（全程 60%/秒）
                        if abs(target - cur) <= step:
                            axis[p]["pos"] = target
                        else:
                            axis[p]["pos"] += step if target > cur else -step
                            done = False
                        apply(p)
                if done:
                    state["goto"] = None

            for p in (PAN, TILT, ZOOM):
                state["pos"][p] = axis[p]["sent"] if axis.get(p) else None

        time.sleep(DT)


# ── 網頁面板 ─────────────────────────────────────────────────────────────────
PAGE = """<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pocket PTZ</title><style>
:root{color-scheme:dark}
body{margin:0;background:#1e1e22;color:#e8e8ea;font-family:system-ui,"Microsoft JhengHei",sans-serif;
     user-select:none;-webkit-user-select:none;touch-action:none}
.wrap{padding:12px;max-width:300px;margin:auto}
.status{font-size:12px;color:#9aa;margin-bottom:8px;text-align:center}
.devrow{display:flex;gap:6px;margin-bottom:10px}
.devrow select{flex:1;background:#26262c;color:#e8e8ea;border:1px solid #45454d;
  border-radius:8px;padding:6px;font-size:12px;max-width:100%}
.devrow button{flex:0 0 auto;width:40px;background:#34343b;border:1px solid #45454d;
  border-radius:8px;color:#eee;font-size:15px;padding:6px 0;cursor:pointer}
.joybase{position:relative;width:200px;height:200px;margin:0 auto;border-radius:50%;
  background:radial-gradient(circle,#2a2a31 0%,#232329 70%,#1e1e22 100%);
  border:2px solid #45454d;touch-action:none}
.joybase::before,.joybase::after{content:"";position:absolute;background:#3a3a42}
.joybase::before{left:50%;top:8%;width:1px;height:84%;transform:translateX(-.5px)}
.joybase::after{top:50%;left:8%;height:1px;width:84%;transform:translateY(-.5px)}
.knob{position:absolute;width:70px;height:70px;border-radius:50%;
  left:65px;top:65px;background:#4a90d9;box-shadow:0 2px 8px rgba(0,0,0,.4);
  transition:left .08s,top .08s}
.knob.drag{transition:none;background:#5aa0e9}
.row{display:flex;gap:8px;margin-top:12px}
button{background:#34343b;border:1px solid #45454d;border-radius:10px;color:#eee;
       font-size:15px;padding:14px 0;cursor:pointer;touch-action:none;flex:1}
button:active{background:#4a90d9;border-color:#4a90d9}
.spd{margin-top:12px;font-size:13px;color:#bbb}
input[type=range]{width:100%}
</style></head><body><div class="wrap">
<div class="status" id="st">連線中… / Connecting…</div>
<div class="devrow">
  <select id="dev"></select>
  <button id="rescan" title="重新偵測 / Rescan">⟳</button>
</div>
<div class="joybase" id="base"><div class="knob" id="knob"></div></div>
<div class="row">
  <button id="c">回正 Center</button>
  <button id="seth">設回正點 Set home</button>
</div>
<div class="row">
  <button data-axis="zoom" data-v="-1">Zoom −</button>
  <button data-axis="zoom" data-v="1">Zoom ＋</button>
</div>
<div class="spd">靈敏度 <span id="sv">30</span>%
  <input type="range" id="sp" min="2" max="120" value="30"></div>
</div><script>
const api=(p)=>fetch(p).catch(()=>{});

// ── 類比搖桿 ──
const base=document.getElementById('base'), knob=document.getElementById('knob');
let dragging=false, pan=0, tilt=0, lastSent=0, R=70;
function place(dx,dy){knob.style.left=(65+dx)+'px';knob.style.top=(65+dy)+'px';}
function setVec(cx,cy,ex,ey){
  let dx=ex-cx, dy=ey-cy;
  const d=Math.hypot(dx,dy); R=base.clientWidth/2-30;
  if(d>R){dx*=R/d;dy*=R/d;}
  place(dx,dy);
  pan=Math.max(-1,Math.min(1,dx/R));
  tilt=Math.max(-1,Math.min(1,-dy/R));
}
function send(force){
  const now=Date.now();
  if(!force && now-lastSent<50) return;   // 節流 ~20Hz
  lastSent=now;
  api(`/vel?pan=${pan.toFixed(3)}&tilt=${tilt.toFixed(3)}`);
}
function start(e){dragging=true;knob.classList.add('drag');base.setPointerCapture(e.pointerId);move(e);}
function move(e){
  if(!dragging)return; e.preventDefault();
  const r=base.getBoundingClientRect();
  setVec(r.left+r.width/2, r.top+r.height/2, e.clientX, e.clientY);
  send(false);
}
function end(){
  dragging=false;knob.classList.remove('drag');
  pan=0;tilt=0;place(0,0);api('/vel?pan=0&tilt=0');
}
base.addEventListener('pointerdown',start);
base.addEventListener('pointermove',move);
base.addEventListener('pointerup',end);
base.addEventListener('pointercancel',end);
base.addEventListener('pointerleave',()=>{if(dragging)send(true);});

// ── zoom（按住）/ 回正 / 速度 ──
function hold(btn){const v=btn.dataset.v;
  btn.addEventListener('pointerdown',e=>{e.preventDefault();api(`/vel?zoom=${v}`)});
  ['pointerup','pointerleave','pointercancel'].forEach(ev=>btn.addEventListener(ev,()=>api('/vel?zoom=0')));
}
document.querySelectorAll('button[data-axis="zoom"]').forEach(hold);
document.getElementById('c').onclick=()=>api('/center');
document.getElementById('seth').onclick=()=>api('/sethome');
const sp=document.getElementById('sp'),sv=document.getElementById('sv');
sp.oninput=()=>{sv.textContent=sp.value;api(`/speed?v=${sp.value/100}`)};

// ── 相機選擇 / camera select ──
const dev=document.getElementById('dev');
let devKey='';
dev.onchange=()=>{api(`/connect?index=${dev.value}`);
  document.getElementById('st').textContent='連線中… / Connecting…';};
document.getElementById('rescan').onclick=async()=>{await api('/rescan');devKey='';};
function updateDevices(list,sel){
  const key=(list||[]).join('|');
  if(key!==devKey){devKey=key;
    dev.innerHTML=(list||[]).map((n,i)=>`<option value="${i}">${i}: ${n}</option>`).join('')
      || '<option>（找不到相機 / no camera）</option>';}
  if(document.activeElement!==dev && sel!=null && sel>=0) dev.value=sel;
}

async function poll(){
  try{const r=await fetch('/status');const d=await r.json();
    updateDevices(d.devices, d.device_index);
    document.getElementById('st').textContent=
      d.connected?`✓ ${d.connected}  pan ${d.pos.pan??'—'} tilt ${d.pos.tilt??'—'}`
                 :'未連線 / not connected（請從上方選相機 / pick a camera above）';
    sv.textContent=Math.round((d.speed||0.3)*100);
  }catch(e){document.getElementById('st').textContent='背景程式未啟動 / server not running';}
}
setInterval(poll,800);poll();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)

        if u.path == "/":
            return self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")

        if u.path == "/vel":
            for name, p in (("pan", PAN), ("tilt", TILT), ("zoom", ZOOM)):
                if name in q:
                    try:
                        state["vel"][p] = clamp(float(q[name][0]), -1, 1)
                    except ValueError:
                        pass
        elif u.path == "/nudge":
            for name, p in (("pan", PAN), ("tilt", TILT), ("zoom", ZOOM)):
                if name in q:
                    try:
                        state["nudge"][p] += float(q[name][0])
                    except ValueError:
                        pass
        elif u.path == "/center":
            state["center_req"] = True
        elif u.path == "/sethome":
            state["sethome_req"] = True
        elif u.path == "/preset/recall":
            try:
                state["preset_req"] = ("recall", int(q.get("n", ["1"])[0]))
            except ValueError:
                pass
        elif u.path == "/preset/save":
            try:
                state["preset_req"] = ("save", int(q.get("n", ["1"])[0]))
            except ValueError:
                pass
        elif u.path == "/speed":
            try:
                state["speed"] = clamp(float(q.get("v", ["0.3"])[0]), 0.05, 1.5)
                save_cfg({"speed": state["speed"]})
            except ValueError:
                pass
        elif u.path == "/connect":
            try:
                state["connect_req"] = int(q.get("index", ["0"])[0])
            except ValueError:
                pass
        elif u.path == "/rescan":
            state["rescan_req"] = True
        elif u.path == "/status":
            body = json.dumps({
                "connected": state["connected"],
                "devices": state["devices"],
                "device_index": state["device_index"],
                "speed": state["speed"],
                "pos": {"pan": state["pos"][PAN], "tilt": state["pos"][TILT], "zoom": state["pos"][ZOOM]},
            }).encode("utf-8")
            return self._send(200, body, "application/json")
        else:
            return self._send(404, b"not found", "text/plain")

        return self._send(200, b'{"ok":true}', "application/json")


def main():
    threading.Thread(target=control_loop, daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"PTZ 控制面板已啟動：http://127.0.0.1:{PORT}/")
    print("在 OBS：停駐視窗 → 自訂瀏覽器停駐視窗 → 網址填上面那個。關掉這視窗就停止。")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
