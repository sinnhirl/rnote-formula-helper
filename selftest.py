# -*- coding: utf-8 -*-
"""无界面自检：生成测试图 -> 识别 -> 计算，并单测解析/计算层。
用法：
    python selftest.py          # 全部
    python selftest.py parse    # 只测解析/计算（不加载模型）
    python selftest.py ocr      # 只测识别（首次会下载模型）
    python selftest.py plot     # 画图模块（Agg 后端）
"""
import sys
import tempfile
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
    print("== looks_like_table ==")
    lt_fails = []

    def lt_check(name, ok, detail=""):
        if ok:
            print(f"[table] {name} ok")
        else:
            print(f"[table] {name} FAIL {detail}")
            lt_fails.append(name)

    lt_cases = [
        (
            "Time (s) Velocity (mi/h) 0182.910169.020106.63099.840123.550175.160176.6",
            True,
        ),
        (
            "t (s) 00.51.01.52.02.53.0v (ft/s) 05.711.214.117.519.420.2",
            True,
        ),
        ("2 x+7=1 5", False),
        ("x^{2}-2x+1", False),
        (r"\frac{5}{2} x", False),
        ("sin x", False),
        ("1 2 3 4", True),
    ]
    for text, expected in lt_cases:
        got = pipeline.looks_like_table(text)
        lt_check(repr(text), got == expected, f"expected={expected} got={got}")
    if lt_fails:
        print(f"失败: {', '.join(lt_fails)}")
        sys.exit(1)

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
        "0_{.}75 \\times 4",
        "1.75^{2} }",
        "0.5×(4×6+5.875×4)",                       # VL 风格：Unicode ×
        "0.75^{2}+0.25^{2}\n\\times 4",            # VL 风格：跨行折成换行
        "\\frac{1.25^{2}+1.75^{2}}{2} \\div 0.5",  # VL 风格：Unicode ÷
        "[\\frac{1}{2}x^{2}-2x]_{2}^{5}+[2x-\\frac{1}{2}x^{2}]_{0}^{2}",  # 求值括号 → 13/2
        "[2x-\\frac{1}{2}x^{2}]^{2}_{0}",          # 求值括号（上下限顺序颠倒）→ 2
        ("[\\frac{1}{2}x^{2}-2x]\\frac{5}{2}+[2x-\\frac{1}{2}x^{2}]_{0}^{2}", {"fix_limits": True}),  # 上下限模式 → 13/2
        ("[\\frac{1}{2}x^{2}-2x]\\frac{5}{2}+[2x-\\frac{1}{2}x^{2}] 0^{2}", {"fix_limits": True}),   # 叠写 ]0^{2} → 13/2
        ("[2x-\\frac{1}{2}x^{2}] 0^{2}", {"fix_limits": True}),      # 叠写单独一段 → 2
    ]
    print("== 解析/计算层 ==")
    for case in cases:
        latex, kw = case if isinstance(case, tuple) else (case, {})
        try:
            r = pipeline.compute(latex, **kw)
            print(f"[calc] {latex!r} {kw or ''}-> ok={r['ok']} main={r.get('main_text')!r} err={r.get('error')!r}")
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


def plot_cases():
    print("== 画图模块 ==")
    import matplotlib

    matplotlib.use("Agg")
    import sympy as sp

    import plot_engine
    import table_reader

    fails = []

    def check(name, ok, detail=""):
        if ok:
            print(f"[plot] {name} ok")
        else:
            print(f"[plot] {name} FAIL {detail}")
            fails.append(name)

    x = sp.Symbol("x")
    try:
        _, ylim = plot_engine.auto_range(sp.sin(x), x)
        check("sin auto_range y bounded", abs(ylim[0]) <= 5 and abs(ylim[1]) <= 5, ylim)
    except Exception as e:
        check("sin auto_range", False, str(e))

    try:
        _, ylim = plot_engine.auto_range(1 / x, x)
        check("1/x y range", abs(ylim[0]) <= 100 and abs(ylim[1]) <= 100, ylim)
    except Exception as e:
        check("1/x auto_range", False, str(e))

    try:
        xlim, _ = plot_engine.auto_range(sp.log(x), x)
        check("ln(x) x lower", xlim[0] > -0.1, xlim)
    except Exception as e:
        check("ln(x) auto_range", False, str(e))

    try:
        fig = plot_engine.render_formula(sp.sin(x), x)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            fig.savefig(tf.name)
        check("render_formula savefig", True)
    except Exception as e:
        check("render_formula savefig", False, str(e))

    collinear = [(0.0, 0.0), (1.0, 2.0), (2.0, 4.0), (3.0, 6.0)]
    try:
        _, mode = plot_engine.render_table(collinear, connect="auto")
        check("collinear straight", mode == "straight", mode)
    except Exception as e:
        check("collinear straight", False, str(e))

    parab = [(0.0, 0.0), (1.0, 1.0), (2.0, 4.0), (3.0, 9.0), (4.0, 16.0)]
    try:
        _, mode = plot_engine.render_table(parab, connect="auto")
        check("parabola curve", mode == "curve", mode)
    except Exception as e:
        check("parabola curve", False, str(e))

    vert = (
        "<fcel>x<fcel>y<nl>"
        "<fcel>0<fcel>1<nl>"
        "<fcel>10<fcel>2<nl>"
        "<fcel>20<fcel>3<nl>"
        "<fcel>30<fcel>4<nl>"
    )
    vp = table_reader.parse_points(vert)
    check("parse_points vertical", vp == [(0, 1), (10, 2), (20, 3), (30, 4)], vp)

    row1 = " ".join(str(i) for i in range(7))
    row2 = " ".join(str(i * 10) for i in range(7))
    horiz = "<fcel>" + "<fcel>".join(row1.split()) + "<nl><fcel>" + "<fcel>".join(row2.split())
    hp = table_reader.parse_points(horiz)
    exp_h = list(zip([float(i) for i in range(7)], [float(i * 10) for i in range(7)]))
    check("parse_points horizontal", hp == exp_h, hp)

    tp = table_reader.text_to_points("1 2\n3, 4")
    check("text_to_points", tp == [(1.0, 2.0), (3.0, 4.0)], tp)

    if fails:
        print(f"失败: {', '.join(fails)}")
        sys.exit(1)
    print("全部通过")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    IMGS.mkdir(exist_ok=True)
    if mode in ("all", "parse"):
        parse_cases()
    if mode == "plot":
        plot_cases()
        return
    if mode in ("all", "ocr"):
        if mode == "all":
            make_printed("2x+7=15", IMGS / "printed_eq.png")
            make_handwritten("2x + 7 = 15", IMGS / "hand_eq.png")
            make_handwritten("12 + 34 =", IMGS / "hand_calc.png")
            make_handwritten("1/2 + 1/3", IMGS / "hand_frac.png")
        ocr_cases()


if __name__ == "__main__":
    main()
