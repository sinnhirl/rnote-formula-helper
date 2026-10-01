# -*- coding: utf-8 -*-
"""复现：纯白/空白图像是否会卡住识别"""
import time

from PIL import Image

import pipeline

for size in [(1034, 91), (484, 164), (800, 600)]:
    img = Image.new("RGB", size, "white")
    t0 = time.time()
    print(f"--- blank {size} ---", flush=True)
    try:
        latex = pipeline.ocr_latex(img)
        print(f"  result: {latex!r} in {time.time() - t0:.1f}s", flush=True)
    except Exception as e:
        print(f"  EXC {type(e).__name__}: {e}", flush=True)
img = Image.open(r"C:\rnote-ocr\selftest_imgs\sp_eq.png")
t0 = time.time()
print("--- normal sp_eq ---", flush=True)
latex = pipeline.ocr_latex(img)
print(f"  result: {latex!r} in {time.time() - t0:.1f}s", flush=True)
print("ALL DONE", flush=True)
