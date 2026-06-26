#!/usr/bin/env python3
# ============================================================================
# uvc-numpad.py — Pocket 3 雲台控制，純小鍵盤版（USB-C / DirectShow）
#
# 用按鍵的 is_keypad 屬性判定，只認小鍵盤；方向鍵與主鍵盤數字皆無作用。
#
# 安裝：pip install pygrabber comtypes keyboard
# 用法：python uvc-numpad.py        （自動找 OsmoPocket3，找不到就 python uvc-numpad.py 1）
#
# 小鍵盤：
#   8 / 2   tilt 上/下      4 / 6   pan 左/右
#   5       回正（中心往左 90 度）   7 / 9   zoom 縮小/放大
#   + / -   速度 升/降      /       離開
#   0       追蹤（USB 無法觸發，按了會說明）
# ============================================================================

import sys
import time
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

RATE = 40.0
DT = 1.0 / RATE
DEFAULT_SPEED = 0.30
ZOOM_SPEED = 0.40

# 回正位置：中心往左 90 度。UVC pan 單位為角秒（1 度 = 3600）
HOME_PAN_OFFSET_DEG = -90      # 負 = 左
UNITS_PER_DEG = 3600

# 小鍵盤掃描碼
SC_UP, SC_DOWN, SC_LEFT, SC_RIGHT = 72, 80, 75, 77      # 8 2 4 6
SC_CENTER, SC_ZOUT, SC_ZIN, SC_TRACK = 76, 71, 73, 82   # 5 7 9 0
SC_PLUS, SC_MINUS, SC_SLASH = 78, 74, 53                # + - /


class IAMCameraControl(IUnknown):
    _iid_ = GUID("{C6E13370-30AC-11D0-A18C-00A0C9118956}")


IAMCameraControl._methods_ = [
    COMMETHOD([], HRESULT, "GetRange",
              (["in"], c_long, "Property"),
              (["out"], POINTER(c_long), "pMin"),
              (["out"], POINTER(c_long), "pMax"),
              (["out"], POINTER(c_long), "pSteppingDelta"),
              (["out"], POINTER(c_long), "pDefault"),
              (["out"], POINTER(c_long), "pCapsFlags")),
    COMMETHOD([], HRESULT, "Set",
              (["in"], c_long, "Property"),
              (["in"], c_long, "lValue"),
              (["in"], c_long, "Flags")),
    COMMETHOD([], HRESULT, "Get",
              (["in"], c_long, "Property"),
              (["out"], POINTER(c_long), "lValue"),
              (["out"], POINTER(c_long), "Flags")),
]


def find_camera(index=None):
    sde = SystemDeviceEnum()
    names = sde.get_available_filters(VIDEO_CATEGORY)
    if not names:
        print("找不到任何相機 / no cameras found")
        sys.exit(1)
    if index is None:
        index = next((i for i, n in enumerate(names) if "Osmo" in n or "Pocket" in n), None)
    if index is None:
        print("找不到 Osmo Pocket 3，請選擇相機 / Pocket 3 not found, choose a camera:")
        for i, n in enumerate(names):
            print(f"  [{i}] {n}")
        while True:
            s = input("輸入編號 / enter index: ").strip()
            if s.isdigit() and 0 <= int(s) < len(names):
                index = int(s)
                break
            print("無效編號 / invalid index")
    if not (0 <= index < len(names)):
        print(f"編號超出範圍 / index out of range: {index}")
        sys.exit(1)
    print(f"使用裝置 / using [{index}] {names[index]}")
    filt, _ = sde.get_filter_by_index(VIDEO_CATEGORY, index)
    return filt.QueryInterface(IAMCameraControl)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


# ── 只收小鍵盤的按鍵狀態 ─────────────────────────────────────────────────────
np_down = set()
other_down = set()


def on_event(e):
    if e.event_type == keyboard.KEY_DOWN:
        if getattr(e, "is_keypad", False):
            np_down.add(e.scan_code)
        elif e.name:
            other_down.add(e.name.lower())
    elif e.event_type == keyboard.KEY_UP:
        if getattr(e, "is_keypad", False):
            np_down.discard(e.scan_code)
        elif e.name:
            other_down.discard(e.name.lower())


def main():
    index = next((int(a) for a in sys.argv[1:] if a.isdigit()), None)
    cam = find_camera(index)

    axis = {}
    for p in (PAN, TILT, ZOOM):
        try:
            mn, mx, step, default, caps = cam.GetRange(p)
            cur, _ = cam.Get(p)
            axis[p] = {"min": mn, "max": mx, "span": (mx - mn) or 1,
                       "pos": float(cur), "sent": int(cur)}
        except COMError:
            axis[p] = None

    speed = DEFAULT_SPEED

    def apply(p):
        a = axis[p]
        if a is None:
            return
        a["pos"] = clamp(a["pos"], a["min"], a["max"])
        iv = int(round(a["pos"]))
        if iv != a["sent"]:
            try:
                cam.Set(p, iv, FLAG_MANUAL)
                a["sent"] = iv
            except COMError:
                pass

    keyboard.hook(on_event)
    print(f"\n[小鍵盤] 8/2=tilt 4/6=pan 5=回正(左90) 7/9=zoom +/-=速度({speed:.0%}) /=離開")
    print("0=追蹤(USB無法觸發)\n")

    last_adjust = 0.0
    track_warned = 0.0
    while True:
        if SC_SLASH in np_down or "q" in other_down:
            break

        now = time.time()
        if now - last_adjust > 0.15:
            if SC_PLUS in np_down:
                speed = clamp(speed + 0.05, 0.05, 1.5); last_adjust = now
                print(f"  速度 {speed:.0%}            ", end="\r")
            elif SC_MINUS in np_down:
                speed = clamp(speed - 0.05, 0.05, 1.5); last_adjust = now
                print(f"  速度 {speed:.0%}            ", end="\r")

        # 回正：中心往左 90 度
        if SC_CENTER in np_down:
            if axis[PAN]:
                c = (axis[PAN]["min"] + axis[PAN]["max"]) / 2
                axis[PAN]["pos"] = c + HOME_PAN_OFFSET_DEG * UNITS_PER_DEG
                apply(PAN)
            if axis[TILT]:
                axis[TILT]["pos"] = (axis[TILT]["min"] + axis[TILT]["max"]) / 2
                apply(TILT)

        if axis[PAN]:
            d = axis[PAN]["span"] * speed * DT
            if SC_LEFT in np_down:
                axis[PAN]["pos"] -= d; apply(PAN)
            if SC_RIGHT in np_down:
                axis[PAN]["pos"] += d; apply(PAN)
        if axis[TILT]:
            d = axis[TILT]["span"] * speed * DT
            if SC_UP in np_down:
                axis[TILT]["pos"] += d; apply(TILT)
            if SC_DOWN in np_down:
                axis[TILT]["pos"] -= d; apply(TILT)
        if axis[ZOOM]:
            dz = axis[ZOOM]["span"] * ZOOM_SPEED * DT
            if SC_ZIN in np_down:
                axis[ZOOM]["pos"] += dz; apply(ZOOM)
            if SC_ZOUT in np_down:
                axis[ZOOM]["pos"] -= dz; apply(ZOOM)

        if SC_TRACK in np_down and now - track_warned > 1.0:
            track_warned = now
            print("  [0] ActiveTrack 無法透過 USB 觸發；要追蹤請在相機螢幕點主體。   ", end="\r")

        time.sleep(DT)

    keyboard.unhook_all()
    print("\n結束。")


if __name__ == "__main__":
    main()
