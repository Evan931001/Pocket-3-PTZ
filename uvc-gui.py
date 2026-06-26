#!/usr/bin/env python3
# ============================================================================
# uvc-gui.py — Pocket 3 雲台 GUI 控制（USB-C / DirectShow）
#   ‧ 畫面按鈕 + 全域按鍵（OBS 在前景也能控）
#   ‧ 按鍵可自訂（按「設定」再按要綁的鍵）；設定存 uvc-gui-config.json
#
# 安裝：pip install pygrabber comtypes keyboard
# 執行：python uvc-gui.py
# ============================================================================

import os
import sys
import json
import time
import tkinter as tk
from tkinter import ttk, messagebox
from ctypes import HRESULT, POINTER, c_long
from comtypes import COMMETHOD, GUID, IUnknown, COMError
from pygrabber.dshow_graph import SystemDeviceEnum

try:
    import keyboard
except ImportError:
    print("缺 keyboard 套件，請先跑：pip install keyboard")
    sys.exit(1)

VIDEO_CATEGORY = "{860BB310-5D01-11D0-BD3B-00A0C911CE86}"
FLAG_MANUAL = 0x0002
PAN, TILT, ZOOM = 0, 1, 3
UNITS_PER_DEG = 3600
DT = 0.025
ZOOM_SPEED = 0.40
DEADZONE = 0.06      # 搖桿死區
EXPO = 1.6           # 反應曲線（中間細膩、邊緣全速）
CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ptz-config.json")


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

ACTION_ORDER = ["pan_left", "pan_right", "tilt_up", "tilt_down", "zoom_in", "zoom_out",
                "center", "speed_up", "speed_down", "track", "quit"]
CONTINUOUS = {"pan_left", "pan_right", "tilt_up", "tilt_down", "zoom_in", "zoom_out"}

# ── 介面文字（中／英）──────────────────────────────────────────────────────
STRINGS = {
    "zh": {
        "title": "Pocket 3 PTZ 控制",
        "device": "裝置", "refresh": "重新整理", "connect": "連線",
        "not_connected": "尚未連線", "connected": "已連線：{}",
        "enum_fail": "列舉裝置失敗：{}", "connect_fail": "無法取得相機控制：{}", "error": "錯誤",
        "joystick": "搖桿（拖動：推越遠轉越快；放開停）",
        "center": "回正", "zoom_in": "Zoom ＋", "zoom_out": "Zoom −",
        "sensitivity": "靈敏度（搖桿全速；越低越平滑）",
        "home": "回正點（把鏡頭轉到想要的位置，再按下方按鈕）",
        "set_home": "設為目前位置", "home_saved": "回正點：pan {} / tilt {}", "home_none": "回正點：未設定（先設定）",
        "bindings": "自訂按鍵（按按鍵後再按下要綁定的鍵）",
        "reset_keys": "恢復預設按鍵", "press_key": "請按鍵…",
        "track_hint": "ActiveTrack 無法透過 USB 觸發（請在相機螢幕點主體）",
        "language": "語言",
    },
    "en": {
        "title": "Pocket 3 PTZ Control",
        "device": "Device", "refresh": "Refresh", "connect": "Connect",
        "not_connected": "Not connected", "connected": "Connected: {}",
        "enum_fail": "Failed to list devices: {}", "connect_fail": "Can't get camera control: {}", "error": "Error",
        "joystick": "Joystick (drag: farther = faster; release to stop)",
        "center": "Center", "zoom_in": "Zoom ＋", "zoom_out": "Zoom −",
        "sensitivity": "Sensitivity (joystick top speed; lower = smoother)",
        "home": "Home (aim the camera where you want, then click below)",
        "set_home": "Set current as home", "home_saved": "Home: pan {} / tilt {}", "home_none": "Home: not set (set it first)",
        "bindings": "Custom keys (click a key button, then press a key)",
        "reset_keys": "Reset to defaults", "press_key": "Press a key…",
        "track_hint": "ActiveTrack can't be triggered via USB (tap the subject on the camera screen)",
        "language": "Language",
    },
}
ACTION_LABELS_I18N = {
    "zh": {
        "pan_left": "Pan 左", "pan_right": "Pan 右", "tilt_up": "Tilt 上", "tilt_down": "Tilt 下",
        "zoom_in": "Zoom 放大", "zoom_out": "Zoom 縮小", "center": "回正",
        "speed_up": "速度 ＋", "speed_down": "速度 －", "track": "追蹤", "quit": "離開",
    },
    "en": {
        "pan_left": "Pan Left", "pan_right": "Pan Right", "tilt_up": "Tilt Up", "tilt_down": "Tilt Down",
        "zoom_in": "Zoom In", "zoom_out": "Zoom Out", "center": "Center",
        "speed_up": "Speed +", "speed_down": "Speed -", "track": "Track", "quit": "Quit",
    },
}

DEFAULT_BINDINGS = {
    "pan_left":  {"sc": 75, "keypad": True, "label": "小鍵盤 4"},
    "pan_right": {"sc": 77, "keypad": True, "label": "小鍵盤 6"},
    "tilt_up":   {"sc": 72, "keypad": True, "label": "小鍵盤 8"},
    "tilt_down": {"sc": 80, "keypad": True, "label": "小鍵盤 2"},
    "zoom_in":   {"sc": 73, "keypad": True, "label": "小鍵盤 9"},
    "zoom_out":  {"sc": 71, "keypad": True, "label": "小鍵盤 7"},
    "center":    {"sc": 76, "keypad": True, "label": "小鍵盤 5"},
    "speed_up":  {"sc": 78, "keypad": True, "label": "小鍵盤 +"},
    "speed_down": {"sc": 74, "keypad": True, "label": "小鍵盤 -"},
    "track":     {"sc": 82, "keypad": True, "label": "小鍵盤 0"},
    "quit":      {"sc": 53, "keypad": True, "label": "小鍵盤 /"},
}


def load_config():
    cfg = {"device_index": None, "speed": 0.30, "home_deg": -90, "lang": "zh",
           "bindings": {k: dict(v) for k, v in DEFAULT_BINDINGS.items()}}
    try:
        with open(CONFIG, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k in ("device_index", "speed", "home_deg", "lang", "home_pan", "home_tilt"):
            if k in data:
                cfg[k] = data[k]
        for k, v in data.get("bindings", {}).items():
            cfg["bindings"][k] = v
    except Exception:
        pass
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("存設定失敗:", e)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def shape(v):
    """死區 + 指數曲線：輸入 -1..1 → 輸出 -1..1（中間更細膩）。"""
    a = abs(v)
    if a <= DEADZONE:
        return 0.0
    a = (a - DEADZONE) / (1 - DEADZONE)
    return (a ** EXPO) * (1.0 if v > 0 else -1.0)


# ── 全域鍵盤狀態（含「自訂綁定擷取」）────────────────────────────────────────
pressed = set()            # 目前按住：set of (scan_code, is_keypad)
capture_request = [None]   # 要擷取的 action 名稱
capture_result = [None]    # 擷取結果 (action, sc, keypad, label)


def on_event(e):
    keypad = bool(getattr(e, "is_keypad", False))
    if e.event_type == keyboard.KEY_DOWN:
        if capture_request[0] is not None:        # 正在自訂按鍵 → 吃掉這次按鍵當綁定
            label = ("小鍵盤 " if keypad else "") + (e.name or f"sc{e.scan_code}")
            capture_result[0] = (capture_request[0], e.scan_code, keypad, label)
            capture_request[0] = None
            return
        pressed.add((e.scan_code, keypad))
    elif e.event_type == keyboard.KEY_UP:
        pressed.discard((e.scan_code, keypad))


class App:
    def __init__(self, root):
        self.root = root
        self.cfg = load_config()
        self.bindings = self.cfg["bindings"]
        self.speed = self.cfg["speed"]
        self.cam = None
        self.axis = {}
        self.btn_held = set()
        self.prev_active = set()
        self.last_speed_adj = 0.0
        self.bind_btns = {}
        self.joy_vel = {"pan": 0.0, "tilt": 0.0}   # 搖桿類比速度 -1..1
        self.applied = {"pan": 0.0, "tilt": 0.0}    # 平滑後的實際速度
        self.goto = None                            # 回正平滑移動目標 {"pan":..,"tilt":..}
        self.lang = self.cfg.get("lang", "zh")
        self._status = ("not_connected", ())       # (字串key, 參數) 供切換語言時重繪
        self._tr = {}                               # 需翻譯的元件參照

        root.title(self.t("title"))
        root.resizable(False, False)
        self._build_ui()
        self._refresh_devices()
        keyboard.hook(on_event)
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.after(int(DT * 1000), self.tick)

    # ── 語言 ──────────────────────────────────────────────────────────────────
    def t(self, key, *args):
        s = STRINGS.get(self.lang, STRINGS["zh"]).get(key, key)
        return s.format(*args) if args else s

    def alabel(self, action):
        return ACTION_LABELS_I18N.get(self.lang, ACTION_LABELS_I18N["zh"])[action]

    def _set_status(self, key, *args):
        self._status = (key, args)
        self.status_var.set(self.t(key, *args))

    def set_language(self, lang):
        if lang not in STRINGS:
            return
        self.lang = lang
        self.cfg["lang"] = lang
        save_config(self.cfg)
        self.root.title(self.t("title"))
        # 更新所有靜態元件
        for widget, key in self._tr.items():
            try:
                widget.config(text=self.t(key))
            except Exception:
                pass
        # 動作列標籤
        for act, lbl in self.act_row_lbls.items():
            lbl.config(text=self.alabel(act))
        # 回正點標籤（動態）
        self.home_lbl.config(text=self._home_text())
        # 動態文字
        self.status_var.set(self.t(self._status[0], *self._status[1]))
        for act, b in self.bind_btns.items():
            if capture_request[0] != act:
                b.config(text=self.bindings[act]["label"])

    # ── UI ──────────────────────────────────────────────────────────────────
    def _build_ui(self):
        pad = {"padx": 6, "pady": 4}
        self.act_row_lbls = {}

        top = ttk.LabelFrame(self.root, text=self.t("device"))
        top.grid(row=0, column=0, sticky="ew", **pad)
        self._tr[top] = "device"
        self.device_combo = ttk.Combobox(top, width=30, state="readonly")
        self.device_combo.grid(row=0, column=0, **pad)
        b_ref = ttk.Button(top, text=self.t("refresh"), command=self._refresh_devices)
        b_ref.grid(row=0, column=1, **pad)
        self._tr[b_ref] = "refresh"
        b_con = ttk.Button(top, text=self.t("connect"), command=self.connect)
        b_con.grid(row=0, column=2, **pad)
        self._tr[b_con] = "connect"
        self.status_var = tk.StringVar(value=self.t("not_connected"))
        ttk.Label(top, textvariable=self.status_var).grid(row=1, column=0, columnspan=3, sticky="w", **pad)
        # 語言切換
        self.lang_combo = ttk.Combobox(top, width=12, state="readonly",
                                       values=["中文", "English"])
        self.lang_combo.current(0 if self.lang == "zh" else 1)
        self.lang_combo.grid(row=0, column=3, **pad)
        self.lang_combo.bind("<<ComboboxSelected>>",
                             lambda e: self.set_language("zh" if self.lang_combo.current() == 0 else "en"))

        # 搖桿
        ctrl = ttk.LabelFrame(self.root, text=self.t("joystick"))
        ctrl.grid(row=1, column=0, sticky="ew", **pad)
        self._tr[ctrl] = "joystick"
        self._build_joystick(ctrl)
        b_c = ttk.Button(ctrl, text=self.t("center"), command=self.do_center, width=8)
        b_c.grid(row=0, column=1, padx=6, pady=4)
        self._tr[b_c] = "center"
        self._hold_btn(ctrl, self.t("zoom_in"), "zoom_in", 0, 2)
        self._hold_btn(ctrl, self.t("zoom_out"), "zoom_out", 1, 2)

        # 靈敏度
        spd = ttk.LabelFrame(self.root, text=self.t("sensitivity"))
        spd.grid(row=2, column=0, sticky="ew", **pad)
        self._tr[spd] = "sensitivity"
        self.speed_var = tk.DoubleVar(value=self.speed * 100)
        self.speed_scale = ttk.Scale(spd, from_=2, to=120, variable=self.speed_var,
                                     command=self._on_speed, length=220)
        self.speed_scale.grid(row=0, column=0, **pad)
        self.speed_lbl = ttk.Label(spd, text=f"{self.speed:.0%}")
        self.speed_lbl.grid(row=0, column=1, **pad)

        # 回正點（記住目前位置）
        home = ttk.LabelFrame(self.root, text=self.t("home"))
        home.grid(row=3, column=0, sticky="ew", **pad)
        self._tr[home] = "home"
        b_seth = ttk.Button(home, text=self.t("set_home"), command=self.set_home)
        b_seth.grid(row=0, column=0, **pad)
        self._tr[b_seth] = "set_home"
        self.home_lbl = ttk.Label(home, text=self._home_text())
        self.home_lbl.grid(row=0, column=1, sticky="w", **pad)

        # 即時數值
        self.pos_var = tk.StringVar(value="pan — / tilt — / zoom —")
        ttk.Label(self.root, textvariable=self.pos_var).grid(row=4, column=0, sticky="w", **pad)

        # 自訂按鍵
        kb = ttk.LabelFrame(self.root, text=self.t("bindings"))
        kb.grid(row=0, column=1, rowspan=5, sticky="ns", **pad)
        self._tr[kb] = "bindings"
        for i, act in enumerate(ACTION_ORDER):
            lbl = ttk.Label(kb, text=self.alabel(act), width=10)
            lbl.grid(row=i, column=0, sticky="w", padx=4, pady=2)
            self.act_row_lbls[act] = lbl
            b = ttk.Button(kb, width=14, text=self.bindings[act]["label"],
                           command=lambda a=act: self.start_capture(a))
            b.grid(row=i, column=1, padx=4, pady=2)
            self.bind_btns[act] = b
        b_reset = ttk.Button(kb, text=self.t("reset_keys"), command=self.reset_bindings)
        b_reset.grid(row=len(ACTION_ORDER), column=0, columnspan=2, pady=6)
        self._tr[b_reset] = "reset_keys"

    def _hold_btn(self, parent, text, action, r, c):
        b = tk.Button(parent, text=text, width=6, height=2)
        b.grid(row=r, column=c, padx=4, pady=4)
        b.bind("<ButtonPress-1>", lambda e: self.btn_held.add(action))
        b.bind("<ButtonRelease-1>", lambda e: self.btn_held.discard(action))
        return b

    # ── 類比搖桿 ──────────────────────────────────────────────────────────────
    def _build_joystick(self, parent):
        sz = 150
        self.joy_cx = self.joy_cy = sz / 2
        self.joy_r = sz / 2 - 18           # 可推半徑
        cv = tk.Canvas(parent, width=sz, height=sz, bg="#1e1e22",
                       highlightthickness=1, highlightbackground="#45454d")
        cv.grid(row=0, column=0, rowspan=2, padx=6, pady=6)
        self.joy_canvas = cv
        cv.create_oval(self.joy_cx - self.joy_r, self.joy_cy - self.joy_r,
                       self.joy_cx + self.joy_r, self.joy_cy + self.joy_r,
                       outline="#55555f", width=2)
        cv.create_line(self.joy_cx, self.joy_cy - 6, self.joy_cx, self.joy_cy + 6, fill="#55555f")
        cv.create_line(self.joy_cx - 6, self.joy_cy, self.joy_cx + 6, self.joy_cy, fill="#55555f")
        kr = 22
        self.joy_knob = cv.create_oval(self.joy_cx - kr, self.joy_cy - kr,
                                       self.joy_cx + kr, self.joy_cy + kr,
                                       fill="#4a90d9", outline="")
        self.joy_kr = kr
        cv.bind("<Button-1>", self._joy_move)
        cv.bind("<B1-Motion>", self._joy_move)
        cv.bind("<ButtonRelease-1>", self._joy_release)

    def _joy_move(self, e):
        dx = e.x - self.joy_cx
        dy = e.y - self.joy_cy
        dist = (dx * dx + dy * dy) ** 0.5
        if dist > self.joy_r and dist > 0:
            dx *= self.joy_r / dist
            dy *= self.joy_r / dist
        self.joy_canvas.coords(self.joy_knob,
                               self.joy_cx + dx - self.joy_kr, self.joy_cy + dy - self.joy_kr,
                               self.joy_cx + dx + self.joy_kr, self.joy_cy + dy + self.joy_kr)
        self.joy_vel["pan"] = clamp(dx / self.joy_r, -1, 1)
        self.joy_vel["tilt"] = clamp(-dy / self.joy_r, -1, 1)   # 上 = tilt 正

    def _joy_release(self, _e):
        self.joy_vel["pan"] = 0.0
        self.joy_vel["tilt"] = 0.0
        self.joy_canvas.coords(self.joy_knob,
                               self.joy_cx - self.joy_kr, self.joy_cy - self.joy_kr,
                               self.joy_cx + self.joy_kr, self.joy_cy + self.joy_kr)

    # ── 裝置 ────────────────────────────────────────────────────────────────
    def _refresh_devices(self):
        try:
            self.names = SystemDeviceEnum().get_available_filters(VIDEO_CATEGORY)
        except Exception as e:
            self.names = []
            self._set_status("enum_fail", e)
        self.device_combo["values"] = self.names
        pick = self.cfg.get("device_index")
        if pick is None:
            pick = next((i for i, n in enumerate(self.names) if "Osmo" in n or "Pocket" in n), 0)
        if self.names:
            self.device_combo.current(min(pick, len(self.names) - 1))

    def connect(self):
        idx = self.device_combo.current()
        if idx < 0:
            return
        try:
            filt, name = SystemDeviceEnum().get_filter_by_index(VIDEO_CATEGORY, idx)
            self.cam = filt.QueryInterface(IAMCameraControl)
        except COMError as e:
            messagebox.showerror(self.t("error"), self.t("connect_fail", e))
            return
        self.axis = {}
        for p in (PAN, TILT, ZOOM):
            try:
                mn, mx, st, de, ca = self.cam.GetRange(p)
                cur, _ = self.cam.Get(p)
                self.axis[p] = {"min": mn, "max": mx, "span": (mx - mn) or 1,
                                "pos": float(cur), "sent": int(cur)}
            except COMError:
                self.axis[p] = None
        self.cfg["device_index"] = idx
        save_config(self.cfg)
        self._set_status("connected", name)

    # ── 相機動作 ──────────────────────────────────────────────────────────────
    def apply(self, p):
        a = self.axis.get(p)
        if a is None:
            return
        a["pos"] = clamp(a["pos"], a["min"], a["max"])
        iv = int(round(a["pos"]))
        if iv != a["sent"]:
            try:
                self.cam.Set(p, iv, FLAG_MANUAL)
                a["sent"] = iv
            except COMError:
                pass

    def _home_text(self):
        hp = self.cfg.get("home_pan")
        ht = self.cfg.get("home_tilt")
        if hp is None and ht is None:
            return self.t("home_none")
        return self.t("home_saved", hp, ht)

    def set_home(self):
        """把目前 pan/tilt 位置記成回正點。"""
        if self.axis.get(PAN):
            self.cfg["home_pan"] = self.axis[PAN]["sent"]
        if self.axis.get(TILT):
            self.cfg["home_tilt"] = self.axis[TILT]["sent"]
        save_config(self.cfg)
        self.home_lbl.config(text=self._home_text())

    def do_center(self):
        if not self.cam:
            return
        hp = self.cfg.get("home_pan")
        ht = self.cfg.get("home_tilt")
        g = {}
        # 有記過回正點 → 回到該位置；沒有 → 回到行程中點
        if self.axis.get(PAN):
            g["pan"] = float(hp) if hp is not None else \
                (self.axis[PAN]["min"] + self.axis[PAN]["max"]) / 2
        if self.axis.get(TILT):
            g["tilt"] = float(ht) if ht is not None else \
                (self.axis[TILT]["min"] + self.axis[TILT]["max"]) / 2
        self.goto = g       # 連續送指令平滑移動到位（不必先動搖桿喚醒）

    def _on_speed(self, _=None):
        self.speed = self.speed_var.get() / 100.0
        self.speed_lbl.config(text=f"{self.speed:.0%}")
        self.cfg["speed"] = self.speed

    # ── 自訂按鍵 ──────────────────────────────────────────────────────────────
    def start_capture(self, action):
        capture_request[0] = action
        self.bind_btns[action].config(text=self.t("press_key"))

    def reset_bindings(self):
        self.bindings = {k: dict(v) for k, v in DEFAULT_BINDINGS.items()}
        self.cfg["bindings"] = self.bindings
        save_config(self.cfg)
        for act, b in self.bind_btns.items():
            b.config(text=self.bindings[act]["label"])

    # ── 主迴圈 ────────────────────────────────────────────────────────────────
    def active_actions(self):
        act = set(self.btn_held)
        for a, b in self.bindings.items():
            if (b["sc"], bool(b.get("keypad", False))) in pressed:
                act.add(a)
        return act

    def tick(self):
        # 處理自訂按鍵擷取結果
        if capture_result[0] is not None:
            action, sc, keypad, label = capture_result[0]
            capture_result[0] = None
            self.bindings[action] = {"sc": sc, "keypad": keypad, "label": label}
            self.cfg["bindings"] = self.bindings
            save_config(self.cfg)
            self.bind_btns[action].config(text=label)

        act = self.active_actions()
        now = time.time()

        if self.cam:
            # pan / tilt 目標速度：搖桿類比 + 鍵盤（相加）
            tpan = self.joy_vel["pan"]
            if "pan_left" in act:
                tpan -= 1
            if "pan_right" in act:
                tpan += 1
            ttilt = self.joy_vel["tilt"]
            if "tilt_up" in act:
                ttilt += 1
            if "tilt_down" in act:
                ttilt -= 1
            # 死區 + 曲線
            tpan = shape(clamp(tpan, -1, 1))
            ttilt = shape(clamp(ttilt, -1, 1))
            # 有手動輸入就取消回正平滑移動
            if tpan or ttilt:
                self.goto = None
            # 平滑（低通：朝目標逼近，消除起停與斜向頓挫）
            resp = min(1.0, DT * 16)
            self.applied["pan"] += (tpan - self.applied["pan"]) * resp
            self.applied["tilt"] += (ttilt - self.applied["tilt"]) * resp
            if self.axis.get(PAN) and abs(self.applied["pan"]) > 1e-3:
                self.axis[PAN]["pos"] += self.axis[PAN]["span"] * self.speed * DT * self.applied["pan"]
                self.apply(PAN)
            if self.axis.get(TILT) and abs(self.applied["tilt"]) > 1e-3:
                self.axis[TILT]["pos"] += self.axis[TILT]["span"] * self.speed * DT * self.applied["tilt"]
                self.apply(TILT)

            # 回正平滑移動到位（每個週期都送指令，相機不必先被搖桿喚醒）
            if self.goto:
                done = True
                for p, nm in ((PAN, "pan"), (TILT, "tilt")):
                    if self.axis.get(p) and nm in self.goto:
                        target = self.goto[nm]
                        cur = self.axis[p]["pos"]
                        step = self.axis[p]["span"] * 0.6 * DT   # 全程 60%/秒
                        if abs(target - cur) <= step:
                            self.axis[p]["pos"] = target
                        else:
                            self.axis[p]["pos"] += step if target > cur else -step
                            done = False
                        self.apply(p)
                if done:
                    self.goto = None

            if self.axis.get(ZOOM):
                dz = self.axis[ZOOM]["span"] * ZOOM_SPEED * DT
                if "zoom_in" in act:
                    self.axis[ZOOM]["pos"] += dz; self.apply(ZOOM)
                if "zoom_out" in act:
                    self.axis[ZOOM]["pos"] -= dz; self.apply(ZOOM)

        # 速度（按住連續調，含節流）
        if ("speed_up" in act or "speed_down" in act) and now - self.last_speed_adj > 0.12:
            self.speed = clamp(self.speed + (0.05 if "speed_up" in act else -0.05), 0.05, 1.5)
            self.last_speed_adj = now
            self.speed_var.set(self.speed * 100)
            self._on_speed()

        # 單次觸發（剛按下的瞬間）
        newly = act - self.prev_active
        if "center" in newly:
            self.do_center()
        if "track" in newly:
            self._set_status("track_hint")
        if "quit" in newly:
            self.on_close()
            return
        self.prev_active = act

        # 即時數值
        def fmt(p):
            a = self.axis.get(p)
            return str(a["sent"]) if a else "—"
        self.pos_var.set(f"pan {fmt(PAN)} / tilt {fmt(TILT)} / zoom {fmt(ZOOM)}")

        self.root.after(int(DT * 1000), self.tick)

    def on_close(self):
        try:
            self._on_speed()
            save_config(self.cfg)
            keyboard.unhook_all()
        except Exception:
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
