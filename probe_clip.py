# -*- coding: utf-8 -*-
"""验证：从剪贴板抓取图片这一链路是否可用"""
from PIL import ImageGrab

im = ImageGrab.grabclipboard()
print("grabbed:", type(im).__name__, getattr(im, "size", None))
