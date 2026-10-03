# -*- coding: utf-8 -*-
"""表达式 / 表格数据 → matplotlib Figure（不依赖 pyplot、backend 由调用方设置）。"""
from __future__ import annotations


class PlotError(ValueError):
    """无法出图；message 为可直接展示的中文短句。"""


def auto_range(expr, sym) -> tuple[tuple[float, float], tuple[float, float]]:
    """根据表达式在实数域上的有效采样，估计合适的 x/y 显示窗口。"""
    default_x = (-10.0, 10.0)
    try:
        import numpy as np

        x_arr = np.linspace(-50.0, 50.0, 4000)
        f = _lambdify(expr, sym)
        y_arr = f(x_arr)
        mask = np.isfinite(y_arr) & np.isreal(y_arr)
        y_real = np.real(y_arr[mask])
        x_valid = x_arr[mask]
        if x_valid.size == 0:
            raise PlotError("这条公式没有实数定义域，画不了图")

        x_min, x_max = float(x_valid.min()), float(x_valid.max())
        # 与 [-10,10] 相交；若不相交则用有效区间
        lo, hi = max(x_min, -10.0), min(x_max, 10.0)
        if lo >= hi:
            span = max(x_max - x_min, 1e-6)
            lo, hi = x_min - 0.05 * span, x_max + 0.05 * span
        else:
            span = hi - lo
            lo -= 0.05 * span
            hi += 0.05 * span
        lo = max(lo, x_min)
        hi = min(hi, x_max)
        xlim = (lo, hi)

        xs = np.linspace(xlim[0], xlim[1], 2000)
        ys = np.real(f(xs))
        ys = ys[np.isfinite(ys)]
        if ys.size == 0:
            return default_x, (-5.0, 5.0)
        y_lo, y_hi = np.percentile(ys, [2, 98])
        typical = max(abs(y_lo), abs(y_hi), 1e-9)
        margin = 0.1 * (y_hi - y_lo + 1e-9)
        y_lo, y_hi = y_lo - margin, y_hi + margin
        cap = min(50.0, 10.0 * typical)
        y_lo = max(y_lo, -cap)
        y_hi = min(y_hi, cap)
        if y_lo >= y_hi:
            y_lo, y_hi = -typical, typical
        return xlim, (float(y_lo), float(y_hi))
    except PlotError:
        raise
    except Exception:
        try:
            import numpy as np

            xs = np.linspace(-10, 10, 500)
            f = _lambdify(expr, sym)
            ys = np.real(f(xs))
            ys = ys[np.isfinite(ys)]
            if ys.size:
                y_lo, y_hi = np.percentile(ys, [2, 98])
                return default_x, (float(y_lo), float(y_hi))
        except Exception:
            pass
        return default_x, (-5.0, 5.0)


def _lambdify(expr, sym):
    import numpy as np
    from sympy import lambdify

    return lambdify(sym, expr, modules=["numpy"])


def render_formula(expr, sym, xlim=None, ylim=None, title=None) -> Figure:
    """绘制 y=f(x) 曲线。"""
    try:
        import numpy as np

        if xlim is None or ylim is None:
            ax_lim, ay_lim = auto_range(expr, sym)
            if xlim is None:
                xlim = ax_lim
            if ylim is None:
                ylim = ay_lim
        f = _lambdify(expr, sym)
        xs = np.linspace(xlim[0], xlim[1], 1500)
        ys = np.asarray(np.real(f(xs)), dtype=float)
        ys[~np.isfinite(ys)] = np.nan

        from matplotlib.figure import Figure

        fig = Figure(figsize=(6, 4), dpi=100)
        ax = fig.add_subplot(111)
        ax.plot(xs, ys, linewidth=2, color="#2563eb")
        ax.set_xlim(xlim)
        ax.set_ylim(ylim)
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.grid(True, alpha=0.3)
        if title:
            ax.set_title(title)
        fig.tight_layout()
        return fig
    except PlotError:
        raise
    except Exception as e:
        raise PlotError(f"画图失败：{e}") from e


def _smart_connect_mode(points: list[tuple[float, float]]) -> str:
    """auto 模式：返回 \"straight\" 或 \"curve\"（与 _tbl_test/run_samples 一致）。"""
    n = len(points)
    if n <= 3:
        return "straight"
    import numpy as np

    pts = sorted(points, key=lambda p: p[0])
    xs = np.array([p[0] for p in pts], dtype=float)
    ys = np.array([p[1] for p in pts], dtype=float)
    if len(np.unique(xs)) < len(xs):
        return "straight"
    a = np.vstack([xs, np.ones_like(xs)]).T
    coef, *_ = np.linalg.lstsq(a, ys, rcond=None)
    span = float(ys.max() - ys.min()) or 1.0
    err = float(np.max(np.abs(ys - a @ coef)) / span)
    if err < 0.02:
        return "straight"
    d2 = np.diff(ys, 2)
    if len(d2) and (np.all(d2 >= -1e-9) or np.all(d2 <= 1e-9)):
        return "curve"
    return "curve" if err > 0.05 else "straight"


def render_table(
    points, connect: str = "auto", title=None
) -> tuple[Figure, str]:
    """绘制表格数据；返回 (figure, 实际连线模式)。"""
    if len(points) < 2:
        raise PlotError("数据点不足，画不了图")

    mode = connect
    if mode == "auto":
        mode = _smart_connect_mode(list(points))
    if mode not in ("straight", "curve"):
        mode = "straight"

    import numpy as np

    pts = sorted(points, key=lambda p: p[0])
    xs = np.array([p[0] for p in pts], dtype=float)
    ys = np.array([p[1] for p in pts], dtype=float)

    from matplotlib.figure import Figure

    fig = Figure(figsize=(6, 4), dpi=100)
    ax = fig.add_subplot(111)

    drew_curve = False
    if mode == "curve" and len(np.unique(xs)) == len(xs) and len(pts) >= 3:
        try:
            from scipy.interpolate import make_interp_spline

            k = min(3, len(pts) - 1)
            spl = make_interp_spline(xs, ys, k=k)
            x_dense = np.linspace(xs.min(), xs.max(), max(200, len(pts) * 40))
            y_dense = spl(x_dense)
            ax.plot(x_dense, y_dense, linewidth=2, color="#2563eb")
            ax.plot(xs, ys, "o", color="#2563eb", markersize=6)
            drew_curve = True
        except Exception:
            pass
    if not drew_curve:
        mode = "straight"
        ax.plot(xs, ys, linewidth=2, color="#2563eb", marker="o", markersize=6, linestyle="-")

    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.grid(True, alpha=0.3)
    if title:
        ax.set_title(title)
    fig.tight_layout()
    return fig, mode
