# -*- coding: utf-8 -*-
"""慢速模拟按下 ctrl+alt+shift+m（给全局热键 hook 反应时间）"""
import time

import keyboard

keyboard.press("ctrl"); time.sleep(0.08)
keyboard.press("alt"); time.sleep(0.08)
keyboard.press("shift"); time.sleep(0.08)
keyboard.press("m"); time.sleep(0.3)
keyboard.release("m")
keyboard.release("shift"); keyboard.release("alt"); keyboard.release("ctrl")
time.sleep(1)
print("keys sent")
