# -*- coding: utf-8 -*-
"""截取「公式助手」弹窗窗口（含 DPI 感知处理），保存 popup_shot.png"""
import ctypes
from ctypes import wintypes

from PIL import ImageGrab

# 先声明 DPI 感知（在创建任何窗口前调用，可靠）
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)   # per-monitor aware
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.windll.user32
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL

hwnd = user32.FindWindowW(None, "公式助手")
if not hwnd:
    print("popup not found")
    raise SystemExit(1)

rect = wintypes.RECT()
if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
    print("GetWindowRect failed")
    raise SystemExit(1)
l, t, r, b = rect.left, rect.top, rect.right, rect.bottom
print(f"rect: {l},{t} {r - l}x{b - t}")
if r <= l or b <= t:
    print("bad rect")
    raise SystemExit(1)

img = ImageGrab.grab(bbox=(l, t, r, b), all_screens=True)
img.save("C:\\rnote-ocr\\popup_shot.png")
print("saved popup_shot.png", img.size)
