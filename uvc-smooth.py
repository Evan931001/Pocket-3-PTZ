#!/usr/bin/env python3
# ============================================================================
# uvc-smooth.py — Pocket 3 雲台「平滑」鍵盤控制（USB-C / DirectShow 相機控制）
#
# 跟 uvc-ptz2.py 同一條路，但改成固定頻率控制迴圈：
#   按住方向鍵 → 持續平滑移動；放開 → 停。不再一格一格跳。
#
# 安裝：pip install pygrabber comtypes keyboard
#
# 用法：
#   python uvc-smooth.py            自動找 OsmoPocket3
#   python uvc-smooth.py 1          指定裝置 index
#
# 操作：
#   ← → ↑ ↓   pan / tilt（按住連續移動）
#   z / x      zoom 縮小 / 放大
#   o / p      整體速度 降 / 升
#   c          回中位
#   q          離開
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

RATE = 40.0                  # 控制迴圈頻率 (Hz)
DT = 1.0 / RATE
DEFAULT_SPEED = 0.30         # pan/tilt 每秒移動「全程的幾成」
ZOOM_SPEED = 0.40            # zoom 每秒移動全程的幾成


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


def main():
    index = next((int(a) for a in sys.argv[1:] if a.isdigit()), None)
    cam = find_camera(index)

    # 讀各軸範圍與目前值
    axis = {}
    for p in (PAN, TILT, ZOOM):
        try:
            mn, mx, step, default, caps = cam.GetRange(p)
            cur, _ = cam.Get(p)
            axis[p] = {"min": mn, "max": mx, "span": (mx - mn) or 1, "pos": float(cur), "sent": int(cur)}
        except COMError:
            axis[p] = None

    speed = DEFAULT_SPEED

    def apply(p):
        a = axis[p]
        if a is None:
            return
        a["pos"] = clamp(a["pos"], a["min"], a["max"])
        iv = int(round(a["pos"]))
        if iv != a["sent"]:           # 只在數值真的變了才送，避免塞爆 USB
            try:
                cam.Set(p, iv, FLAG_MANUAL)
                a["sent"] = iv
            except COMError:
                pass

    print(f"\n[平滑控制] ←→↑↓=pan/tilt  z/x=zoom  o/p=速度({speed:.0%})  c=回中  q=離開\n")

    last_adjust = 0.0
    while True:
        if keyboard.is_pressed("q"):
            break

        # 速度調整（每 0.15 秒一次，避免狂跳）
        now = time.time()
        if now - last_adjust > 0.15:
            if keyboard.is_pressed("o"):
                speed = clamp(speed - 0.05, 0.05, 1.5); last_adjust = now
                print(f"  速度 {speed:.0%}            ", end="\r")
            elif keyboard.is_pressed("p"):
                speed = clamp(speed + 0.05, 0.05, 1.5); last_adjust = now
                print(f"  速度 {speed:.0%}            ", end="\r")

        # 回中
        if keyboard.is_pressed("c"):
            for p in (PAN, TILT):
                if axis[p]:
                    axis[p]["pos"] = (axis[p]["min"] + axis[p]["max"]) / 2
                    apply(p)

        # pan / tilt：按住就持續移動
        if axis[PAN]:
            d = axis[PAN]["span"] * speed * DT
            if keyboard.is_pressed("left"):
                axis[PAN]["pos"] -= d; apply(PAN)
            if keyboard.is_pressed("right"):
                axis[PAN]["pos"] += d; apply(PAN)
        if axis[TILT]:
            d = axis[TILT]["span"] * speed * DT
            if keyboard.is_pressed("up"):
                axis[TILT]["pos"] += d; apply(TILT)
            if keyboard.is_pressed("down"):
                axis[TILT]["pos"] -= d; apply(TILT)
        if axis[ZOOM]:
            dz = axis[ZOOM]["span"] * ZOOM_SPEED * DT
            if keyboard.is_pressed("x"):
                axis[ZOOM]["pos"] += dz; apply(ZOOM)
            if keyboard.is_pressed("z"):
                axis[ZOOM]["pos"] -= dz; apply(ZOOM)

        time.sleep(DT)

    print("\n結束。")


if __name__ == "__main__":
    main()
