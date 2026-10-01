# -*- coding: utf-8 -*-
"""无界面自检：生成测试图 -> 识别 -> 计算，并单测解析/计算层。
用法：
    python selftest.py          # 全部
    python selftest.py parse    # 只测解析/计算（不加载模型）
    python selftest.py ocr      # 只测识别（首次会下载模型）
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import pipeline

BASE = Path(__file__).resolve().parent
IMGS = BASE / "selftest_imgs"


def make_printed(latex, path):
    from matplotlib.figure import Figure
    fig = Figure(dpi=200)
    fig.text(0, 0, f"${latex}$", fontsize=30, color="black")
    fig.savefig(path, bbox_inches="tight", pad_inches=0.3, facecolor="white")
    print(f"[img] {path.name}")


def make_handwritten(text, path, size=72):
    font = ImageFont.truetype(r"C:\Windows\Fonts\Inkfree.ttf", size)
    img = Image.new("RGB", (10, 10), "white")
    d = ImageDraw.Draw(img)
    bbox = d.textbbox((0, 0), text, font=font)
    img = Image.new("RGB", (bbox[2] + 60, bbox[3] + 60), "white")
    d = ImageDraw.Draw(img)
    d.text((30, 30), text, font=font, fill=(15, 15, 25))
    img.save(path)
    print(f"[img] {path.name}")


def parse_cases():
    cases = [
        "2x+7=15",
        "x^2-5x+6=0",
        "x^2=4",
        "3+4\\times 2",
        "\\frac{1}{2}+\\frac{1}{3}",
        "\\int x^2 dx",
        "\\frac{d}{dx}(x^3+2x)",
        "x^2-1",
        "\\sin x = \\frac{1}{2}",
        "x+y=3",
        "\\begin{matrix} x^{2} \\\\ +2x+1 \\end{matrix}",
        "0 , 75 + 1",
        "0.5 \\times( 4 \\times6+0.75^{2}+0.25^{2}",
    ]
    print("== 解析/计算层 ==")
    for latex in cases:
        try:
            r = pipeline.compute(latex)
            print(f"[calc] {latex!r} -> ok={r['ok']} main={r.get('main_text')!r} err={r.get('error')!r}")
            for (l, _lt, t) in r["results"]:
                print(f"        - {l}: {t!r}")
        except Exception as e:
            print(f"[calc] {latex!r} -> EXC {e}")


def ocr_cases():
    print("== OCR 识别 ==")
    for f in ["printed_eq.png", "sp_eq.png", "ink_eq_thick.png", "ink_calc.png", "sp_quad.png", "sp_frac.png"]:
        p = IMGS / f
        if not p.exists():
            continue
        try:
            latex = pipeline.ocr_latex(Image.open(p))
            r = pipeline.compute(latex)
            print(f"[ocr] {f} -> {latex!r} | main={r.get('main_text')!r}")
        except Exception as e:
            print(f"[ocr] {f} -> ERROR {e}")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    IMGS.mkdir(exist_ok=True)
    if mode in ("all", "parse"):
        parse_cases()
    if mode in ("all", "ocr"):
        if mode == "all":
            make_printed("2x+7=15", IMGS / "printed_eq.png")
            make_handwritten("2x + 7 = 15", IMGS / "hand_eq.png")
            make_handwritten("12 + 34 =", IMGS / "hand_calc.png")
            make_handwritten("1/2 + 1/3", IMGS / "hand_frac.png")
        ocr_cases()


if __name__ == "__main__":
    main()
