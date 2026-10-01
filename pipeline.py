# -*- coding: utf-8 -*-
"""Rnote 公式助手 — 核心管道：图像预处理 / 手写公式识别(pix2text,备选pix2tex) / 计算(sympy)。

供 app.py(界面) 与 selftest.py(测试) 共用；本模块不依赖 tkinter。
"""
from __future__ import annotations

import contextlib
import io
import re
import sys
import time
import traceback
from pathlib import Path

from PIL import Image, ImageOps

BASE = Path(__file__).resolve().parent
LOG_FILE = BASE / "rnote-ocr.log"


def log(msg: str):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    try:
        if sys.stdout:                      # pythonw 下没有控制台，跳过
            print(line, flush=True)
    except Exception:
        pass


# ---------------------------------------------------------------- 图像预处理
def preprocess(img: Image.Image) -> Image.Image:
    """把截图处理成更适合识别的样子：
    深色画布 -> 反色成白底黑字；小图放大；提高对比；四周补白边。"""
    import numpy as np

    img = img.convert("RGB")
    g = img.convert("L")
    if float(np.asarray(g, dtype=np.float32).mean()) < 120:   # 深色背景
        img = ImageOps.invert(img)
        g = ImageOps.invert(g)
    g = ImageOps.autocontrast(g)
    img = Image.merge("RGB", (g, g, g))
    w, h = img.size
    if w < 420:                                              # 太小的图识别率差
        k = min(3.0, 420.0 / max(w, 1))
        img = img.resize((int(w * k), int(h * k)), Image.LANCZOS)
    img = ImageOps.expand(img, border=24, fill=(255, 255, 255))
    return img


# ---------------------------------------------------------------- 公式识别
# 两个引擎：pix2text 的 mfr-1.5（默认，对手写更准、更快）；pix2tex（备选）。
# config.json 里 "ocr_engine" 可切换；识别失败会自动换另一个引擎。
_tex_model = None
_p2t_model = None


def _cfg() -> dict:
    try:
        import json
        return json.loads((BASE / "config.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_tex_model():
    global _tex_model
    if _tex_model is None:
        from pix2tex.cli import LatexOCR
        t0 = time.time()
        _tex_model = LatexOCR()
        log(f"pix2tex 模型加载完成 ({time.time() - t0:.1f}s)")
    return _tex_model


def get_p2t_model():
    global _p2t_model
    if _p2t_model is None:
        from pix2text.latex_ocr import LatexOCR as P2TLatexOCR
        t0 = time.time()
        _p2t_model = P2TLatexOCR()
        log(f"pix2text(mfr) 模型加载完成 ({time.time() - t0:.1f}s)")
    return _p2t_model


def warmup(engine: str | None = None):
    """预加载识别模型（供界面启动时调用，避免第一次识别等太久）。"""
    eng = engine or _cfg().get("ocr_engine", "pix2text")
    if eng == "pix2tex":
        get_tex_model()
    else:
        get_p2t_model()


def clean_latex(s: str) -> str:
    s = (s or "").strip().strip("$").strip()
    for t in ("\\displaystyle", "\\!", "\\,", "\\;", "\\:", "~"):
        s = s.replace(t, " ")
    s = re.sub(r"\\left(?=[\(\[\{\|\.])", "", s)
    s = re.sub(r"\\right(?=[\)\]\}\|\.])", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _normalize_ocr(s: str) -> str:
    """修识别结果里常见的多余空格：'2 x+7=1 5' -> '2x+7=15'，'1 / 2' -> '1/2'，
    '0. 5' -> '0.5'（小数点后的空格会让 latex2sympy2 解析失败，实测踩过）。"""
    s = re.sub(r"(?<=\d)\s+(?=\d)", "", s)        # 1 2 -> 12
    s = re.sub(r"(?<=\d)\s*\.\s*(?=\d)", ".", s)  # 0. 5 / 0 .5 -> 0.5
    s = re.sub(r"(?<=\d)\s+(?=[a-zA-Z])", "", s)  # 2 x -> 2x
    s = re.sub(r"\s*/\s*", "/", s)                 # 1 / 2 -> 1/2
    return s.strip()


# 生成参数上限：防止空图/噪点触发"复读机"式乱生成（曾导致一次识别卡 50 秒）
_P2T_REC = {"max_new_tokens": 256, "no_repeat_ngram_size": 8}


def _is_blank(img: Image.Image) -> bool:
    """画面几乎全白/全黑（没框到东西）时直接跳过识别。"""
    import numpy as np
    g = np.asarray(img.convert("L"), dtype=np.float32)
    return bool(g.max() - g.min() < 25)


def ocr_latex(img: Image.Image) -> str:
    """输入 PIL 图片，输出 LaTeX 字符串。"""
    proc = preprocess(img)
    if _is_blank(proc):
        log("画面基本空白，跳过识别")
        return ""
    primary = _cfg().get("ocr_engine", "pix2text")
    last_err = None
    for eng in [primary] + [e for e in ("pix2text", "pix2tex") if e != primary]:
        try:
            if eng == "pix2text":
                out = get_p2t_model().recognize(proc, rec_config=_P2T_REC)
                latex = out.get("text", "") if isinstance(out, dict) else str(out)
            else:
                latex = get_tex_model()(proc)
            latex = _normalize_ocr(clean_latex(latex or ""))
            if latex:
                if eng != primary:
                    log(f"主引擎 {primary} 没出结果，已用 {eng}")
                return latex
        except Exception as e:
            last_err = e
            log(f"OCR 引擎 {eng} 失败: {e}")
    if last_err is not None:
        raise last_err
    return ""


# ---------------------------------------------------------------- LaTeX -> sympy
_L2S = None


def parse_latex(latex: str):
    import sympy as sp

    s = _normalize_ocr(latex.strip().strip("$").strip())
    s = s.rstrip("= ").strip()          # 末尾单独的等号（计算器习惯）
    global _L2S
    if _L2S is None:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                from latex2sympy2 import latex2sympy as _imported
            except Exception:
                from latex2sympy2_extended import latex2sympy as _imported
        _L2S = _imported
    l2s = _L2S

    def _call(src):
        # 屏蔽 antlr 运行时版本不一致的告警（不影响功能）
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return l2s(src)

    try:
        return _call(s)
    except Exception:
        if s.count("=") == 1:           # 解析库对等式偶发失败时手工拆分
            left, _, right = s.partition("=")
            return sp.Eq(_call(left), _call(right))
        raise


def _plain(expr) -> str:
    import sympy as sp
    try:
        if isinstance(expr, sp.Eq):
            return f"{sp.sstr(expr.lhs)} = {sp.sstr(expr.rhs)}"
        return sp.sstr(expr)
    except Exception:
        return str(expr)


def _fmt_solutions(sym, sols) -> tuple[str, str]:
    """返回 (latex, 纯文本)"""
    import sympy as sp
    if sym is None:
        return sp.latex(sols), str(sols)
    if len(sols) == 1:
        return sp.latex(sp.Eq(sym, sols[0])), f"{sym} = {sols[0]}"
    lt = ", ".join(sp.latex(sp.Eq(sym, s)) for s in sols)
    tt = f"{sym} = " + ", ".join(str(s) for s in sols)
    return lt, tt


def compute(latex: str) -> dict:
    """对识别结果做默认计算。
    返回 dict: ok / expr / sym / main_latex / main_text / results[(label,latex,text)] / error
    """
    import sympy as sp

    r = {"ok": False, "expr": None, "sym": None, "main_latex": None,
         "main_text": None, "results": [], "error": None}
    try:
        expr = parse_latex(latex)
    except Exception as e:
        r["error"] = f"公式已识别，但没法解析成算式（可点 WolframAlpha 复制过去算）：{e}"
        return r
    r["ok"] = True
    r["expr"] = expr

    def _flatten(x):
        if isinstance(x, list):
            for i in x:
                yield from _flatten(i)
        else:
            yield x

    try:
        if isinstance(expr, list):
            # 这个版本的 latex2sympy2 对等式会直接求解，返回 [Eq(x, 解), ...]
            sols, leftovers = [], []
            for it in _flatten(expr):
                if isinstance(it, sp.Eq) and it.lhs.is_Symbol:
                    sols.append((it.lhs, it.rhs))
                else:
                    leftovers.append(it)
            if sols:
                syms_in_order = []
                for s, _ in sols:
                    if s not in syms_in_order:
                        syms_in_order.append(s)
                if len(syms_in_order) == 1:
                    sym = syms_in_order[0]
                    r["sym"] = sym
                    vals = [v for s, v in sols if s == sym]
                    lt = ", ".join(sp.latex(sp.Eq(sym, v)) for v in vals)
                    tt = f"{sym} = " + ", ".join(str(v) for v in vals)
                else:
                    lt = ", ".join(sp.latex(sp.Eq(s, v)) for s, v in sols)
                    tt = ", ".join(f"{s} = {v}" for s, v in sols)
                r["main_latex"], r["main_text"] = lt, tt
                r["results"].append(("解方程", lt, tt))
                for lf in leftovers:
                    r["results"].append(("附加信息", sp.latex(lf), str(lf)))
            else:
                tt = "; ".join(str(x) for x in _flatten(expr))
                r["main_text"] = tt
                r["results"].append(("结果", None, tt))
        elif isinstance(expr, sp.Eq):
            syms = sorted(expr.free_symbols, key=lambda s: (s.name != "x", s.name))
            if syms:
                sym = syms[0]
                r["sym"] = sym
                sols = sp.solve(expr, sym)
                if sols:
                    lt, tt = _fmt_solutions(sym, sols)
                    r["main_latex"], r["main_text"] = lt, tt
                    r["results"].append(("解方程", lt, tt))
                else:
                    r["main_latex"] = sp.latex(expr)
                    r["main_text"] = f"没解出 {sym}"
                    r["results"].append(("方程", sp.latex(expr), r["main_text"]))
            else:   # 纯数字等式：3+4=7 -> 验证并给出结果
                lv = sp.simplify(expr.lhs)
                ok = sp.simplify(expr.lhs - expr.rhs) == 0
                r["main_latex"] = sp.latex(lv)
                r["main_text"] = f"{lv}" + ("  ✓ 等式成立" if ok else "  ✗ 等式不成立")
                r["results"].append(("计算", r["main_latex"], r["main_text"]))
        else:
            syms = sorted(expr.free_symbols, key=lambda s: (s.name != "x", s.name))
            sym = syms[0] if syms else None
            r["sym"] = sym
            handled = False
            if sym is not None and expr.atoms(sp.Integral):
                res = sp.simplify(expr.doit())
                r["main_latex"], r["main_text"] = sp.latex(res), str(res)
                r["results"].append(("积分", r["main_latex"], r["main_text"]))
                handled = True
            if sym is not None and expr.atoms(sp.Derivative):
                res = sp.simplify(expr.doit())
                r["main_latex"], r["main_text"] = sp.latex(res), str(res)
                r["results"].append(("求导", r["main_latex"], r["main_text"]))
                handled = True
            if not handled:
                simp = sp.simplify(expr)
                r["main_latex"] = sp.latex(simp)
                if simp.is_number:
                    r["main_text"] = str(simp)
                    r["results"].append(("计算", r["main_latex"], r["main_text"]))
                    if not simp.is_Integer:
                        try:
                            r["results"].append(("约等于", None, f"{float(simp):.6g}"))
                        except Exception:
                            pass
                else:
                    r["main_text"] = _plain(simp)
                    r["results"].append(("化简", r["main_latex"], r["main_text"]))
                    try:
                        f = sp.factor(simp)
                        if f != simp:
                            r["results"].append(("因式分解", sp.latex(f), str(f)))
                    except Exception:
                        pass
    except Exception as e:
        r["error"] = f"计算失败：{e}"
        if not r["main_latex"]:
            r["main_latex"] = latex
    return r


def do_op(expr, sym, op: str) -> tuple[str, str | None, str]:
    """弹窗按钮的附加操作。返回 (标签, latex 或 None, 纯文本)"""
    import sympy as sp

    if isinstance(expr, list):
        raise ValueError("这是方程（已直接给出解）；求导/积分等请对纯表达式使用")
    base = (expr.lhs - expr.rhs) if isinstance(expr, sp.Eq) else expr
    if sym is None:
        free = sorted(base.free_symbols, key=lambda s: (s.name != "x", s.name))
        sym = free[0] if free else sp.Symbol("x")

    if op == "diff":
        res = sp.simplify(sp.diff(base, sym))
        return f"d/d{sym}", sp.latex(res), str(res)
    if op == "integrate":
        res = sp.simplify(sp.integrate(base, sym))
        return f"∫ d{sym}", sp.latex(res), str(res)
    if op == "solve":
        target = expr if isinstance(expr, sp.Eq) else sp.Eq(base, 0)
        sols = sp.solve(target, sym)
        if not sols:
            return "解方程", None, "无解或没解出来"
        lt, tt = _fmt_solutions(sym, sols)
        return "解方程", lt, tt
    if op == "simplify":
        res = sp.simplify(base)
        return "化简", sp.latex(res), str(res)
    if op == "factor":
        res = sp.factor(base)
        return "因式分解", sp.latex(res), str(res)
    if op == "expand":
        res = sp.expand(base)
        return "展开", sp.latex(res), str(res)
    if op == "numeric":
        res = sp.N(base, 10)
        return "数值", sp.latex(res), str(res)
    raise ValueError(f"未知操作: {op}")


# ---------------------------------------------------------------- LaTeX 渲染（给界面用）
_rc_ready = False


def render_latex(latex: str, fontsize: int = 20, color: str = "#e6e9f0") -> Image.Image:
    """把 LaTeX 渲染成透明背景的 PIL 图片；失败会抛异常，调用方自行兜底。"""
    global _rc_ready
    # matplotlib 的 mathtext 不支持少数 LaTeX 命令，做点兼容处理
    for t in ("\\limits", "\\displaystyle", "\\!", "\\,", "\\;", "\\:"):
        latex = latex.replace(t, "" if t == "\\limits" else " ")
    latex = re.sub(r"\\left(?=[\(\[\{\|\.])", "", latex)
    latex = re.sub(r"\\right(?=[\)\]\}\|\.])", "", latex)
    from matplotlib.figure import Figure
    if not _rc_ready:
        try:
            from matplotlib import rcParams
            rcParams["mathtext.fontset"] = "cm"
        except Exception:
            pass
        _rc_ready = True
    fig = Figure(dpi=200)
    fig.patch.set_alpha(0)
    fig.text(0, 0, f"${latex}$", fontsize=fontsize, color=color)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0.1, transparent=True)
    buf.seek(0)
    im = Image.open(buf)
    im.load()
    return im.convert("RGBA")
