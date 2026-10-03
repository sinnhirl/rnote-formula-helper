# -*- coding: utf-8 -*-
"""公式 / 表格数据 matplotlib 图窗（与识图弹窗并存、单实例复用）。"""
from __future__ import annotations

import ctypes
import re
import struct
import tempfile
from datetime import datetime
from pathlib import Path

import tkinter as tk

BASE = Path(__file__).resolve().parent

BG = "#20242e"
PANEL = "#171a21"
FG = "#e6e9f0"
SUB = "#9aa4b8"
ACCENT_BG = "#6ea8ff"
BTN_BG = "#2c3242"
BTN_ACTIVE = "#3a4258"
FONT = "Microsoft YaHei UI"

_GEOM_RE = re.compile(r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$")


def _nice_title(expr):
    """显示用标题：把未求值 Mul 形态（如 1*5*x）规整为 5*x；失败回退 str(expr)。"""
    import sympy as sp

    try:
        return str(sp.sympify(str(expr)))
    except Exception:
        return str(expr)


def _parse_range(text: str):
    """解析 \"min,max\"；空串返回 None（自动）。"""
    s = (text or "").strip().replace("，", ",")
    if not s:
        return None
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if len(parts) != 2:
        raise ValueError("需要两个数字，用逗号分隔")
    return (float(parts[0]), float(parts[1]))


def _apply_rendered_figure(dest_fig, src_fig, canvas):
    """把 render_* 返回的 Figure 画到 dest_fig（先 clf）。"""
    dest_fig.clf()
    if not src_fig.axes:
        canvas.draw()
        return
    src = src_fig.axes[0]
    dst = dest_fig.add_subplot(111)
    for line in src.get_lines():
        dst.plot(
            line.get_xdata(),
            line.get_ydata(),
            linewidth=line.get_linewidth(),
            color=line.get_color(),
            marker=line.get_marker(),
            markersize=line.get_markersize(),
            linestyle=line.get_linestyle(),
        )
    dst.set_xlim(src.get_xlim())
    dst.set_ylim(src.get_ylim())
    dst.set_xlabel(src.get_xlabel())
    dst.set_ylabel(src.get_ylabel())
    title = src.get_title()
    if title:
        dst.set_title(title)
    dst.grid(True, alpha=0.3)
    dest_fig.tight_layout()
    canvas.draw()


def _copy_figure_to_clipboard(fig) -> bool:
    """Windows CF_DIB：fig 的 RGBA → 剪贴板（bottom-up、BGRA、alpha=255）。"""
    try:
        from ctypes import wintypes

        fig.canvas.draw()
        w, h = fig.canvas.get_width_height()
        buf = bytes(fig.canvas.buffer_rgba())
        row = w * 4
        out = bytearray(row * h)
        for y in range(h):
            src = buf[y * row : (y + 1) * row]
            dst_off = (h - 1 - y) * row
            for i in range(0, row, 4):
                out[dst_off + i] = src[i + 2]
                out[dst_off + i + 1] = src[i + 1]
                out[dst_off + i + 2] = src[i]
                out[dst_off + i + 3] = 255
        total = 40 + len(out)
        bmi = struct.pack("<IIIHHIIIIII", 40, w, h, 1, 32, 0, len(out), 0, 0, 0, 0)

        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
        kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
        user32.SetClipboardData.restype = wintypes.HANDLE
        user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]

        GMEM_MOVEABLE = 0x0002
        h_global = kernel32.GlobalAlloc(GMEM_MOVEABLE, total)
        if not h_global:
            return False
        ptr = kernel32.GlobalLock(h_global)
        if not ptr:
            kernel32.GlobalFree(h_global)
            return False
        ctypes.memmove(ptr, bmi + bytes(out), total)
        kernel32.GlobalUnlock(h_global)
        if not user32.OpenClipboard(None):
            kernel32.GlobalFree(h_global)
            return False
        try:
            user32.EmptyClipboard()
            ok = user32.SetClipboardData(8, h_global)  # 8 = CF_DIB
            if ok:
                return True
            kernel32.GlobalFree(h_global)
            return False
        finally:
            user32.CloseClipboard()
    except Exception:
        return False


class PlotWindow:
    def __init__(self, master, cfg, save_cfg, t, on_as_formula=None):
        self.master = master
        self.cfg = cfg
        self.save_cfg = save_cfg
        self.t = t
        self.on_as_formula = on_as_formula

        self.last_latex = None
        self._mode = "formula"  # formula | table
        self._expr = None
        self._sym = None
        self._points: list[tuple[float, float]] = []
        self._data_expanded = True
        self._connect = cfg.get("plot_connect", "auto")
        self._flash_after = None
        self._edit_win = None

        self.win = tk.Toplevel(master)
        self.win.configure(bg=BG)
        self.win.withdraw()
        try:
            self.win.iconbitmap(str(BASE / "icon.ico"))
        except Exception:
            pass
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self.refresh_language()
        self._compute_and_set_minsize()
        self._restore_geometry()
        self.win.deiconify()

    def is_alive(self) -> bool:
        try:
            return self.win.winfo_exists()
        except Exception:
            return False

    def focus(self):
        if not self.is_alive():
            return
        self.win.lift()
        try:
            self.win.focus_force()
        except Exception:
            pass

    def refresh_language(self):
        if not self.is_alive():
            return
        self.win.title(self.t("plot_title"))
        self._btn_copy.configure(text=self.t("btn_plot_copy"))
        self._btn_save.configure(text=self.t("btn_plot_save"))
        self._lbl_x.configure(text=self.t("plot_x_label"))
        self._lbl_y.configure(text=self.t("plot_y_label"))
        self._range_hint.configure(text=self.t("plot_range_ph"))
        self._btn_mode_auto.configure(text=self.t("plot_mode_auto"))
        self._btn_mode_straight.configure(text=self.t("plot_mode_straight"))
        self._btn_mode_curve.configure(text=self.t("plot_mode_curve"))
        self._btn_edit_data.configure(text=self.t("btn_edit_data"))
        self._btn_as_formula.configure(text=self.t("btn_as_formula"))
        self._refresh_data_toggle_label()

    def update_formula(self, expr, sym, latex=None):
        import plot_engine

        self._mode = "formula"
        self._expr = expr
        self._sym = sym
        self.last_latex = latex
        self._show_mode_ui()
        self.focus()

        xlim = ylim = None
        try:
            xlim = _parse_range(self._x_entry.get())
            ylim = _parse_range(self._y_entry.get())
        except ValueError as e:
            self._flash(self.t("plot_err") + str(e))
            return

        try:
            new_fig = plot_engine.render_formula(
                expr, sym, xlim=xlim, ylim=ylim, title=_nice_title(expr)
            )
        except plot_engine.PlotError:
            raise
        _apply_rendered_figure(self.fig, new_fig, self.canvas)

    def update_table(self, points, latex=None):
        import plot_engine

        self._mode = "table"
        self._points = list(points)
        self.last_latex = latex
        self._connect = self.cfg.get("plot_connect", "auto")
        self._show_mode_ui()
        self._update_data_text()
        self._highlight_connect_buttons()
        self.focus()

        title = None
        try:
            new_fig, mode = plot_engine.render_table(
                self._points, connect=self._connect, title=title
            )
        except plot_engine.PlotError:
            raise
        _apply_rendered_figure(self.fig, new_fig, self.canvas)

    def _build_ui(self):
        frm = tk.Frame(self.win, bg=BG, padx=12, pady=10)
        frm.pack(fill="both", expand=True)

        row_copy = tk.Frame(frm, bg=BG)
        row_copy.pack(fill="x", pady=(0, 6))

        def mkbtn(parent, text, cmd, accent=False):
            b = tk.Button(
                parent,
                text=text,
                command=cmd,
                bg=(ACCENT_BG if accent else BTN_BG),
                fg=("#10141c" if accent else FG),
                activebackground=BTN_ACTIVE,
                activeforeground="#ffffff",
                relief="flat",
                padx=8,
                pady=2,
                cursor="hand2",
                font=(FONT, 9),
            )
            b.pack(side="left", padx=(0, 6))
            return b

        self._btn_copy = mkbtn(row_copy, "", self._copy_image)
        self._btn_save = mkbtn(row_copy, "", self._save_image)

        self._row_formula = tk.Frame(frm, bg=BG)
        self._row_formula.pack(fill="x", pady=(0, 6))
        self._lbl_x = tk.Label(
            self._row_formula, text="", bg=BG, fg=SUB, font=(FONT, 9)
        )
        self._lbl_x.pack(side="left")
        self._x_entry = tk.Entry(
            self._row_formula,
            width=14,
            bg=PANEL,
            fg=FG,
            insertbackground=FG,
            relief="flat",
            font=(FONT, 9),
        )
        self._x_entry.pack(side="left", padx=(4, 12))
        self._lbl_y = tk.Label(
            self._row_formula, text="", bg=BG, fg=SUB, font=(FONT, 9)
        )
        self._lbl_y.pack(side="left")
        self._y_entry = tk.Entry(
            self._row_formula,
            width=14,
            bg=PANEL,
            fg=FG,
            insertbackground=FG,
            relief="flat",
            font=(FONT, 9),
        )
        self._y_entry.pack(side="left", padx=(4, 8))
        self._range_hint = tk.Label(
            self._row_formula, text="", bg=BG, fg=SUB, font=(FONT, 8)
        )
        self._range_hint.pack(side="left")
        self._x_entry.bind("<Return>", lambda e: self._redraw_formula())
        self._y_entry.bind("<Return>", lambda e: self._redraw_formula())
        self._x_entry.bind("<FocusOut>", lambda e: self._redraw_formula())
        self._y_entry.bind("<FocusOut>", lambda e: self._redraw_formula())

        self._row_table = tk.Frame(frm, bg=BG)
        self._row_table.pack(fill="x", pady=(0, 6))
        self._btn_mode_auto = mkbtn(
            self._row_table, "", lambda: self._set_connect("auto")
        )
        self._btn_mode_straight = mkbtn(
            self._row_table, "", lambda: self._set_connect("straight")
        )
        self._btn_mode_curve = mkbtn(
            self._row_table, "", lambda: self._set_connect("curve")
        )
        self._btn_edit_data = mkbtn(self._row_table, "", self._open_edit_data)
        self._btn_as_formula = mkbtn(
            self._row_table, "", self._on_as_formula_click
        )
        self._btn_as_formula.pack_forget()
        self._btn_as_formula.pack(side="right")

        self._plot_area = tk.Frame(frm, bg=BG)
        self._plot_area.pack(fill="both", expand=True)

        from matplotlib.figure import Figure

        self.fig = Figure(figsize=(6, 4), dpi=100)
        self.fig.patch.set_facecolor(BG)
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        self.canvas = FigureCanvasTkAgg(self.fig, master=self._plot_area)
        self.canvas.get_tk_widget().configure(bg=BG)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        data_head = tk.Frame(frm, bg=BG)
        data_head.pack(fill="x", pady=(6, 0))
        self._btn_data_toggle = tk.Button(
            data_head,
            text="",
            command=self._toggle_data_panel,
            bg=BG,
            fg=SUB,
            activebackground=BG,
            activeforeground=FG,
            relief="flat",
            cursor="hand2",
            font=(FONT, 8),
        )
        self._btn_data_toggle.pack(anchor="w")

        self._data_frame = tk.Frame(frm, bg=BG)
        self._data_frame.pack(fill="x")
        self._data_text = tk.Text(
            self._data_frame,
            height=4,
            bg=BG,
            fg=SUB,
            relief="flat",
            font=("Consolas", 8),
            wrap="none",
        )
        self._data_text.pack(fill="x")
        self._data_text.bind("<Key>", lambda e: "break")

        self._status = tk.Label(frm, text="", bg=BG, fg="#7fe08a", font=(FONT, 9))
        self._status.pack(anchor="e", pady=(4, 0))

        self._show_mode_ui()

    def _apply_table_worst_case_layout(self):
        """表格模式 + 数据展开 + 示例曲线（测量用）。"""
        import plot_engine

        self._mode = "table"
        self._data_expanded = True
        self._points = [(0.0, 0.0), (1.0, 1.0)]
        self._show_mode_ui()
        self._update_data_text()
        new_fig, _ = plot_engine.render_table(
            self._points, connect=self._connect, title=None
        )
        _apply_rendered_figure(self.fig, new_fig, self.canvas)

    def _compute_and_set_minsize(self):
        """最坏情况（表格 + 数据区展开 + 已绘图表）下的自然尺寸，用于 minsize 与默认几何。"""
        need_w, need_h = 640, 920
        try:
            saved_mode = self._mode
            saved_expanded = self._data_expanded
            saved_points = list(self._points)

            self._apply_table_worst_case_layout()
            self.win.update_idletasks()
            need_w = max(self.win.winfo_reqwidth(), 640)

            self.fig.clf()
            self.canvas.draw()
            self.win.deiconify()
            self.win.geometry(f"{need_w}x677+0+0")
            self.win.update_idletasks()

            self._apply_table_worst_case_layout()
            try:
                self.master.update()
            except Exception:
                self.win.update_idletasks()
            need_h = self.win.winfo_reqheight()
            need_w = max(self.win.winfo_reqwidth(), 640)

            self._mode = saved_mode
            self._data_expanded = saved_expanded
            self._points = saved_points
            self._show_mode_ui()
            self.fig.clf()
            self.canvas.draw()
            self.win.withdraw()
        except Exception:
            need_h = 920
            need_w = max(getattr(self, "_need_w", 640), 640)
        self._need_w = need_w
        self._need_h = need_h
        self.win.minsize(need_w, need_h)

    def _show_mode_ui(self):
        if self._mode == "formula":
            self._row_formula.pack(fill="x", pady=(0, 6), before=self._plot_area)
            self._row_table.pack_forget()
            self._btn_data_toggle.pack_forget()
            self._data_frame.pack_forget()
        else:
            self._row_formula.pack_forget()
            self._row_table.pack(fill="x", pady=(0, 6), before=self._plot_area)
            self._btn_data_toggle.pack(anchor="w")
            if self._data_expanded:
                self._data_frame.pack(fill="x", before=self._status)

    def _flash(self, text):
        try:
            if self._flash_after is not None:
                self.win.after_cancel(self._flash_after)
            self._status.configure(text=text)
            self._flash_after = self.win.after(
                1600, lambda: self._status.configure(text="")
            )
        except Exception:
            pass

    def _redraw_formula(self):
        if self._mode != "formula" or self._expr is None or self._sym is None:
            return
        try:
            self.update_formula(self._expr, self._sym, latex=self.last_latex)
        except Exception:
            pass

    def _set_connect(self, mode: str):
        self._connect = mode
        self.cfg["plot_connect"] = mode
        try:
            self.save_cfg(self.cfg)
        except Exception:
            pass
        self._highlight_connect_buttons()
        if self._mode == "table" and len(self._points) >= 2:
            try:
                self.update_table(self._points, latex=self.last_latex)
            except Exception:
                pass

    def _highlight_connect_buttons(self):
        mapping = {
            "auto": self._btn_mode_auto,
            "straight": self._btn_mode_straight,
            "curve": self._btn_mode_curve,
        }
        for key, btn in mapping.items():
            if key == self._connect:
                btn.configure(bg=ACCENT_BG, fg="#10141c")
            else:
                btn.configure(bg=BTN_BG, fg=FG)

    def _refresh_data_toggle_label(self):
        key = "plot_data_show" if self._data_expanded else "plot_data_hide"
        self._btn_data_toggle.configure(text=self.t(key))

    def _toggle_data_panel(self):
        self._data_expanded = not self._data_expanded
        self._refresh_data_toggle_label()
        if self._data_expanded:
            self._data_frame.pack(fill="x", before=self._status)
        else:
            self._data_frame.pack_forget()

    def _update_data_text(self):
        import table_reader

        self._data_text.configure(state="normal")
        self._data_text.delete("1.0", "end")
        self._data_text.insert("1.0", table_reader.points_to_text(self._points))
        self._data_text.configure(state="disabled")

    def _open_edit_data(self):
        import table_reader

        if self._edit_win is not None and self._edit_win.winfo_exists():
            self._edit_win.lift()
            return
        dlg = tk.Toplevel(self.win)
        self._edit_win = dlg
        dlg.title(self.t("edit_data_title"))
        dlg.configure(bg=BG)
        try:
            dlg.iconbitmap(str(BASE / "icon.ico"))
        except Exception:
            pass
        frm = tk.Frame(dlg, bg=BG, padx=16, pady=12)
        frm.pack(fill="both", expand=True)
        tk.Label(
            frm,
            text=self.t("edit_data_hint"),
            bg=BG,
            fg=SUB,
            font=(FONT, 9),
            wraplength=420,
            justify="left",
        ).pack(anchor="w")
        txt = tk.Text(
            frm,
            height=12,
            width=48,
            bg=PANEL,
            fg=FG,
            insertbackground=FG,
            relief="flat",
            font=("Consolas", 10),
        )
        txt.pack(fill="both", pady=(8, 0))
        txt.insert("1.0", table_reader.points_to_text(self._points))
        err = tk.Label(frm, text="", bg=BG, fg="#ffb4a8", font=(FONT, 9))
        err.pack(anchor="w")

        def close_dlg():
            self._edit_win = None
            dlg.destroy()

        def apply_data():
            pts = table_reader.text_to_points(txt.get("1.0", "end"))
            if len(pts) < 2:
                err.configure(text=self.t("edit_data_bad"))
                return
            close_dlg()
            try:
                self.update_table(pts, latex=self.last_latex)
            except Exception as ex:
                import plot_engine

                if isinstance(ex, plot_engine.PlotError):
                    self._flash(self.t("plot_err") + str(ex))

        brow = tk.Frame(frm, bg=BG)
        brow.pack(fill="x", pady=(10, 0))

        def mkbtn(text, cmd, accent=False):
            b = tk.Button(
                brow,
                text=text,
                command=cmd,
                bg=(ACCENT_BG if accent else BTN_BG),
                fg=("#10141c" if accent else FG),
                activebackground=BTN_ACTIVE,
                activeforeground="#ffffff",
                relief="flat",
                padx=10,
                pady=3,
                cursor="hand2",
                font=(FONT, 10),
            )
            b.pack(side="left", padx=(0, 6))
            return b

        mkbtn(self.t("edit_data_apply"), apply_data, True)
        mkbtn(self.t("hk_cancel"), close_dlg)
        dlg.protocol("WM_DELETE_WINDOW", close_dlg)

    def _on_as_formula_click(self):
        if self.on_as_formula:
            self.on_as_formula()

    def _copy_image(self):
        if _copy_figure_to_clipboard(self.fig):
            self._flash(self.t("plot_copied"))
        else:
            self._flash(self.t("plot_copy_fail"))

    def _save_image(self):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        desktop = Path.home() / "Desktop"
        path = desktop / f"plot_{stamp}.png"
        try:
            if not desktop.is_dir():
                raise OSError("no desktop")
            self.fig.savefig(path, dpi=150, facecolor=self.fig.get_facecolor())
            self._flash(self.t("plot_saved", path=str(path)))
        except Exception:
            path = BASE / f"plot_{stamp}.png"
            self.fig.savefig(path, dpi=150, facecolor=self.fig.get_facecolor())
            self._flash(self.t("plot_saved", path=str(path)))

    def _restore_geometry(self):
        need_w = getattr(self, "_need_w", 640)
        need_h = getattr(self, "_need_h", 920)
        max_h = max(150, self.win.winfo_screenheight() - 80)

        geom = (self.cfg.get("plot_geom") or "").strip()
        m = _GEOM_RE.match(geom)
        if m:
            w, h, x, y = (
                int(m.group(1)),
                int(m.group(2)),
                int(m.group(3)),
                int(m.group(4)),
            )
            orig_w, orig_h = w, h
            if w >= 200 and h >= 150:
                if w < need_w:
                    w = need_w
                if h < need_h:
                    h = need_h
                h = min(h, max_h)
                self.win.geometry(f"{w}x{h}+{x}+{y}")
                if w != orig_w or h != orig_h:
                    self.cfg["plot_geom"] = f"{w}x{h}+{x}+{y}"
                    try:
                        self.save_cfg(self.cfg)
                    except Exception:
                        pass
                return
        self.win.update_idletasks()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        w = max(640, need_w)
        h = min(need_h, max_h)
        x = max(10, sw - w - 24)
        y = max(10, (sh - h) // 2)
        self.win.geometry(f"{w}x{h}+{x}+{y}")

    def _save_geometry(self):
        try:
            self.win.update_idletasks()
            g = self.win.geometry()
            if "+" in g:
                wh, pos = g.split("+", 1)
                w, h = wh.split("x")
                xs, ys = pos.split("+")
                self.cfg["plot_geom"] = f"{w}x{h}+{xs}+{ys}"
                self.save_cfg(self.cfg)
        except Exception:
            pass

    def _on_close(self):
        self._save_geometry()
        self.win.destroy()
