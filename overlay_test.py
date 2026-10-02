# -*- coding: utf-8 -*-
"""自动化测试：内置框选流程。
显示测试公式图 → 按 config.json 里配置的框选热键触发 → 检测遮罩窗口 → 模拟拖框 → 验证弹窗出现。"""
import ctypes
import json
import time
from ctypes import wintypes

import tkinter as tk

import keyboard
from PIL import Image, ImageTk

IMG_PATH = r"C:\rnote-ocr\selftest_imgs\sp_eq.png"

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

u = ctypes.windll.user32
u.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
u.FindWindowW.restype = wintypes.HWND
u.PostMessageW.argtypes = [wintypes.HWND, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]

sw, sh = u.GetSystemMetrics(0), u.GetSystemMetrics(1)

img = Image.open(IMG_PATH)
iw, ih = img.size
cx, cy = sw // 2, sh // 2
left, top = cx - iw // 2, cy - ih // 2

root = tk.Tk()
root.overrideredirect(True)
root.geometry(f"{sw}x{sh}+0+0")
root.attributes("-topmost", True)
canvas = tk.Canvas(root, bg="white", highlightthickness=0)
canvas.pack(fill="both", expand=True)
photo = ImageTk.PhotoImage(img)
canvas.create_image(cx, cy, image=photo)
root.update()
print(f"[viewer] image at ({left},{top}) size {iw}x{ih}")

time.sleep(0.6)
# 慢速模拟框选热键（读 config.json 的 hotkey；跨进程模拟才有效——同进程模拟会被 keyboard 库自己忽略）
with open(r"C:\rnote-ocr\config.json", encoding="utf-8") as _f:
    _hk = json.load(_f).get("hotkey", "ctrl+alt+shift+m")
_parts = [p for p in _hk.split("+") if p]
try:
    for _k in _parts:
        keyboard.press(_k)
        time.sleep(0.1)
    time.sleep(0.8)   # 纯修饰键版本要按住等遮罩（取消窗口 350ms）
finally:
    for _k in reversed(_parts):
        try:
            keyboard.release(_k)
        except Exception:
            pass
print(f"[step] hotkey {_hk} sent")

h = 0
for _ in range(50):
    time.sleep(0.1)
    h = u.FindWindowW(None, "RnoteSnipOverlay")
    if h:
        break
print("[step] overlay hwnd:", h)
if not h:
    print("[warn] overlay not found, 仍然继续模拟拖框（若遮罩在，拖框照样生效）")
time.sleep(0.5)
x0, y0 = left - 12, top - 12
x1, y1 = left + iw + 12, top + ih + 12
u.SetCursorPos(x0, y0)
time.sleep(0.2)
u.mouse_event(0x0002, 0, 0, 0, 0)      # 左键按下
for i in range(1, 15):
    u.SetCursorPos(x0 + (x1 - x0) * i // 14, y0 + (y1 - y0) * i // 14)
    time.sleep(0.03)
u.mouse_event(0x0004, 0, 0, 0, 0)      # 左键松开
print(f"[step] drag done: ({x0},{y0}) -> ({x1},{y1})")

popup = 0
for _ in range(60):
    time.sleep(0.1)
    popup = u.FindWindowW(None, "Rnote 公式助手")
    if popup:
        break
print("[step] popup hwnd:", popup)

time.sleep(0.8)
keyboard.send("esc")
time.sleep(0.5)
still = u.FindWindowW(None, "Rnote 公式助手")
if still:
    u.PostMessageW(still, 0x0010, None, None)   # WM_CLOSE 兜底
    time.sleep(0.3)
root.destroy()
print("RESULT:", "OK" if popup else "FAIL")
