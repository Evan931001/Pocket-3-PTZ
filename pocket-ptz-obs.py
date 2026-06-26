#!/usr/bin/env python3
# ============================================================================
# pocket-ptz-obs.py — OBS 腳本：用 OBS 快捷鍵控制 Pocket 3 雲台（USB-C / UVC）
#
# 安裝步驟見對話說明。重點：
#   ‧ 控制鍵在 OBS「設定 → 快捷鍵」裡搜尋「Pocket」自行指定（可自訂）
#   ‧ 裝置/速度/回正角度在「工具 → 腳本」選到本檔後的右側屬性面板設定
#   ‧ 需在 OBS 指定的那個 Python 裡：pip install pygrabber comtypes
# ============================================================================

import time
import obspython as obs
from ctypes import HRESULT, POINTER, c_long
from comtypes import COMMETHOD, GUID, IUnknown, COMError
import comtypes

VIDEO_CATEGORY = "{860BB310-5D01-11D0-BD3B-00A0C911CE86}"
FLAG_MANUAL = 0x0002
PAN, TILT, ZOOM = 0, 1, 3
UNITS_PER_DEG = 3600
DT_MS = 25
DT = DT_MS / 1000.0
ZOOM_SPEED = 0.40

ACTIONS = ["pan_left", "pan_right", "tilt_up", "tilt_down",
           "zoom_in", "zoom_out", "center", "speed_up", "speed_down"]
LABELS = {
    "pan_left": "Pocket: Pan 左", "pan_right": "Pocket: Pan 右",
    "tilt_up": "Pocket: Tilt 上", "tilt_down": "Pocket: Tilt 下",
    "zoom_in": "Pocket: Zoom 放大", "zoom_out": "Pocket: Zoom 縮小",
    "center": "Pocket: 回正", "speed_up": "Pocket: 速度 +", "speed_down": "Pocket: 速度 -",
}
CONTINUOUS = {"pan_left", "pan_right", "tilt_up", "tilt_down", "zoom_in", "zoom_out"}


# ── IAMCameraControl（與 OBS 相機控制同一介面）──────────────────────────────
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

# ── 全域狀態 ─────────────────────────────────────────────────────────────────
cam = None
axis = {}
speed = 0.30
home_deg = -90
device_index = 0
pressed = {a: False for a in ACTIONS}
hotkeys = {}
last_speed_adj = 0.0
com_ready = False


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def list_devices():
    try:
        from pygrabber.dshow_graph import SystemDeviceEnum
        return SystemDeviceEnum().get_available_filters(VIDEO_CATEGORY)
    except Exception as e:
        obs.script_log(obs.LOG_WARNING, f"列舉裝置失敗（pygrabber 未安裝？）：{e}")
        return []


def connect(idx):
    global cam, axis, com_ready
    try:
        if not com_ready:
            comtypes.CoInitialize()
            com_ready = True
        from pygrabber.dshow_graph import SystemDeviceEnum
        filt, name = SystemDeviceEnum().get_filter_by_index(VIDEO_CATEGORY, idx)
        cam = filt.QueryInterface(IAMCameraControl)
    except Exception as e:
        cam = None
        obs.script_log(obs.LOG_WARNING, f"連線失敗：{e}")
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
    obs.script_log(obs.LOG_INFO, f"已連線：{name}")


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


def do_center():
    if cam is None:
        return
    if axis.get(PAN):
        c = (axis[PAN]["min"] + axis[PAN]["max"]) / 2
        axis[PAN]["pos"] = c + home_deg * UNITS_PER_DEG
        apply(PAN)
    if axis.get(TILT):
        axis[TILT]["pos"] = (axis[TILT]["min"] + axis[TILT]["max"]) / 2
        apply(TILT)


def tick():
    global last_speed_adj, speed
    if cam:
        if axis.get(PAN):
            d = axis[PAN]["span"] * speed * DT
            if pressed["pan_left"]:
                axis[PAN]["pos"] -= d; apply(PAN)
            if pressed["pan_right"]:
                axis[PAN]["pos"] += d; apply(PAN)
        if axis.get(TILT):
            d = axis[TILT]["span"] * speed * DT
            if pressed["tilt_up"]:
                axis[TILT]["pos"] += d; apply(TILT)
            if pressed["tilt_down"]:
                axis[TILT]["pos"] -= d; apply(TILT)
        if axis.get(ZOOM):
            dz = axis[ZOOM]["span"] * ZOOM_SPEED * DT
            if pressed["zoom_in"]:
                axis[ZOOM]["pos"] += dz; apply(ZOOM)
            if pressed["zoom_out"]:
                axis[ZOOM]["pos"] -= dz; apply(ZOOM)

    now = time.time()
    if (pressed["speed_up"] or pressed["speed_down"]) and now - last_speed_adj > 0.12:
        speed = clamp(speed + (0.05 if pressed["speed_up"] else -0.05), 0.05, 1.5)
        last_speed_adj = now


def hotkey_cb(action, is_pressed):
    pressed[action] = is_pressed
    if is_pressed and action == "center":
        do_center()


# ── OBS 介面函式 ─────────────────────────────────────────────────────────────
def script_description():
    return ("用 OBS 快捷鍵控制 DJI Pocket 3 雲台（USB-C / UVC 相機控制）。\n"
            "1) 下方選相機、設速度與回正角度，按「連線」。\n"
            "2) 在「設定 → 快捷鍵」搜尋「Pocket」指定按鍵。\n"
            "需在 OBS 使用的 Python 裡：pip install pygrabber comtypes")


def script_properties():
    props = obs.obs_properties_create()
    dev = obs.obs_properties_add_list(props, "device", "相機裝置",
                                      obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_INT)
    names = list_devices()
    if not names:
        obs.obs_property_list_add_int(dev, "（找不到裝置／pygrabber 未安裝）", 0)
    for i, n in enumerate(names):
        obs.obs_property_list_add_int(dev, n, i)
    obs.obs_properties_add_float_slider(props, "speed", "速度 (%)", 5, 150, 1)
    obs.obs_properties_add_int(props, "home_deg", "回正角度（負=左）", -180, 180, 1)
    obs.obs_properties_add_button(props, "connect", "連線 / 重新連線",
                                  lambda *a: (connect(device_index), True)[1])
    return props


def script_defaults(settings):
    obs.obs_data_set_default_double(settings, "speed", 30.0)
    obs.obs_data_set_default_int(settings, "home_deg", -90)
    obs.obs_data_set_default_int(settings, "device", 0)


def script_update(settings):
    global speed, home_deg, device_index
    speed = obs.obs_data_get_double(settings, "speed") / 100.0
    home_deg = obs.obs_data_get_int(settings, "home_deg")
    new_idx = obs.obs_data_get_int(settings, "device")
    if new_idx != device_index or cam is None:
        device_index = new_idx
        connect(device_index)


def script_load(settings):
    for a in ACTIONS:
        hk = obs.obs_hotkey_register_frontend("pocket_ptz_" + a, LABELS[a],
                                              lambda is_pressed, act=a: hotkey_cb(act, is_pressed))
        hotkeys[a] = hk
        arr = obs.obs_data_get_array(settings, "hk_" + a)
        obs.obs_hotkey_load(hk, arr)
        obs.obs_data_array_release(arr)
    obs.timer_add(tick, DT_MS)


def script_save(settings):
    for a, hk in hotkeys.items():
        arr = obs.obs_hotkey_save(hk)
        obs.obs_data_set_array(settings, "hk_" + a, arr)
        obs.obs_data_array_release(arr)


def script_unload():
    obs.timer_remove(tick)
