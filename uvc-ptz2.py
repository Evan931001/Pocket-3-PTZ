#!/usr/bin/env python3
# ============================================================================
# uvc-ptz2.py — 用 DirectShow 相機控制（OBS 那條路）操控 Pocket 3 雲台
#
# 跟 OpenCV 版不同：這支直接綁裝置、拿 IAMCameraControl，不開影像串流，
# 所以「理論上」能跟 OBS 同時用（OBS 出畫面、這支控雲台）。
#
# 安裝：pip install pygrabber comtypes
#
# 用法：
#   python uvc-ptz2.py                探測：列裝置 + 列出支援的控制項與範圍 + 試轉 pan
#   python uvc-ptz2.py probe 1        指定裝置 index（自動找不到 OsmoPocket3 時用）
#   python uvc-ptz2.py kb             鍵盤控制
#   python uvc-ptz2.py kb 1           鍵盤控制 + 指定 index
# ============================================================================

import sys
import time
from ctypes import HRESULT, POINTER, c_long
from comtypes import COMMETHOD, GUID, IUnknown, COMError
from pygrabber.dshow_graph import SystemDeviceEnum

# 視訊輸入裝置類別 CLSID（直接傳字串，pygrabber 內部會轉 GUID）
VIDEO_CATEGORY = "{860BB310-5D01-11D0-BD3B-00A0C911CE86}"

# CameraControl 旗標
FLAG_AUTO = 0x0001
FLAG_MANUAL = 0x0002

# CameraControlProperty 索引（標準值；不確定就看 probe 印出來的範圍對照）
PROP_NAMES = {0: "Pan", 1: "Tilt", 2: "Roll", 3: "Zoom",
              4: "Exposure", 5: "Iris", 6: "Focus"}
PAN, TILT, ROLL, ZOOM = 0, 1, 2, 3


# ── IAMCameraControl 介面（IID 與 OBS 用的相機控制相同）─────────────────────
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
    print("偵測到的視訊裝置：")
    for i, n in enumerate(names):
        print(f"  [{i}] {n}")

    if index is None:
        index = next((i for i, n in enumerate(names) if "Osmo" in n or "Pocket" in n), None)
        if index is None:
            print("\n找不到 OsmoPocket3，請手動指定 index，例如：python uvc-ptz2.py probe 1")
            sys.exit(1)
    print(f"\n使用裝置 [{index}] {names[index]}")

    filt, name = sde.get_filter_by_index(VIDEO_CATEGORY, index)
    try:
        cam = filt.QueryInterface(IAMCameraControl)
    except COMError as e:
        print(f"這台裝置不支援 IAMCameraControl：{e}")
        sys.exit(1)
    return cam


def probe(cam):
    print("\n支援的控制項與範圍：")
    ranges = {}
    for prop, label in PROP_NAMES.items():
        try:
            mn, mx, step, default, caps = cam.GetRange(prop)
            cur, flags = cam.Get(prop)
            ranges[prop] = (mn, mx, step, default)
            print(f"  [{prop}] {label:9} min={mn} max={mx} step={step} default={default} 目前={cur}")
        except COMError:
            print(f"  [{prop}] {label:9} 不支援")

    if PAN not in ranges:
        print("\n這台沒有 Pan 控制項？把上面整段貼給我，我看是哪個 index 對應雲台。")
        return

    mn, mx, step, default = ranges[PAN]
    print(f"\n=== 測 Pan：在 {mn}~{mx} 之間來回，盯著相機看雲台 ===")
    for frac in (0.3, 0.7, 0.5):
        target = int(mn + (mx - mn) * frac)
        try:
            cam.Set(PAN, target, FLAG_MANUAL)
            print(f"  Set Pan={target}")
        except COMError as e:
            print(f"  Set Pan={target} 失敗：{e}")
        time.sleep(1.2)
    cam.Set(PAN, default, FLAG_MANUAL)

    print("\n判讀：")
    print("  雲台有轉 → 成功！這條真的通了，我接著做完整鍵盤＋Companion 版。")
    print("  Set 都失敗 → 把錯誤貼給我。")
    print("  沒轉但沒報錯 → 可能要先讓 OBS 開著畫面（串流要在跑馬達才動），或換 index。")


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def keyboard(cam):
    import msvcrt
    rng = {}
    for p in (PAN, TILT, ZOOM):
        try:
            mn, mx, step, default, caps = cam.GetRange(p)
            cur, _ = cam.Get(p)
            rng[p] = [mn, mx, cur]
        except COMError:
            rng[p] = None

    def move(p, delta):
        if rng[p] is None:
            return
        mn, mx, cur = rng[p]
        cur = clamp(cur + delta, mn, mx)
        rng[p][2] = cur
        try:
            cam.Set(p, int(cur), FLAG_MANUAL)
        except COMError:
            pass

    # 每按一下移動範圍的 1/40（pan/tilt）或 1 格（zoom）
    def step_of(p):
        if rng[p] is None:
            return 0
        return max(1, (rng[p][1] - rng[p][0]) // 40)

    print("\n[鍵盤] 方向鍵=pan/tilt  +/-=zoom  c=回中  q=離開")
    while True:
        ch = msvcrt.getch()
        if ch in (b"\x00", b"\xe0"):
            code = msvcrt.getch()
            if code == b"H": move(TILT, step_of(TILT))
            elif code == b"P": move(TILT, -step_of(TILT))
            elif code == b"K": move(PAN, -step_of(PAN))
            elif code == b"M": move(PAN, step_of(PAN))
        elif ch in (b"+", b"="):
            move(ZOOM, step_of(ZOOM) or 1)
        elif ch in (b"-", b"_"):
            move(ZOOM, -(step_of(ZOOM) or 1))
        elif ch in (b"c", b"C"):
            for p in (PAN, TILT):
                if rng[p]:
                    mid = (rng[p][0] + rng[p][1]) // 2
                    rng[p][2] = mid
                    try:
                        cam.Set(p, mid, FLAG_MANUAL)
                    except COMError:
                        pass
        elif ch in (b"q", b"Q", b"\x03"):
            break
        vals = {PROP_NAMES[p]: (rng[p][2] if rng[p] else "—") for p in (PAN, TILT, ZOOM)}
        print(f"  {vals}      ", end="\r")


def main():
    args = [a for a in sys.argv[1:]]
    mode = "probe"
    index = None
    for a in args:
        if a in ("probe", "kb"):
            mode = a
        elif a.isdigit():
            index = int(a)
    cam = find_camera(index)
    if mode == "kb":
        keyboard(cam)
    else:
        probe(cam)


if __name__ == "__main__":
    main()
