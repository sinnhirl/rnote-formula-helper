# -*- coding: utf-8 -*-
"""Rnote 公式助手 — 主程序
热键：Ctrl+Alt+M 截取公式识别；Ctrl+Alt+Shift+M 识别剪贴板图片；
      Ctrl+Alt+Shift+Q 退出。热键可在 config.json 修改。
"""
import ctypes
import json
import os
import queue
import sys
import threading
import time
import traceback
import urllib.parse
from pathlib import Path

import tkinter as tk

from PIL import Image, ImageDraw, ImageGrab, ImageTk

import pipeline
from pipeline import log

BASE = Path(__file__).resolve().parent

DEFAULT_CFG = {
    "hotkey": "ctrl+alt+m",
    "clipboard_hotkey": "ctrl+alt+shift+m",
    "quit_hotkey": "ctrl+alt+shift+q",
    "ocr_engine": "pix2text",
    "snip_method": "builtin",
    "snip_timeout_s": 90,
    "auto_copy": True,
}

BG = "#20242e"
PANEL = "#171a21"
FG = "#e6e9f0"
SUB = "#9aa4b8"
ACCENT = "#8ab4ff"
ACCENT_BG = "#6ea8ff"
OK_GREEN = "#7fe08a"


def load_cfg():
    cfg = dict(DEFAULT_CFG)
    try:
        cfg.update(json.loads((BASE / "config.json").read_text(encoding="utf-8")))
    except Exception as e:
        log(f"读取 config.json 失败，用默认值: {e}")
    return cfg


CFG = load_cfg()


def clip_seq():
    return ctypes.windll.user32.GetClipboardSequenceNumber()


def cursor_pos():
    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def snip_image(timeout):
    """打开系统截图(框选)，等待剪贴板出现新图片。返回 PIL 图片或 None。"""
    seq = clip_seq()
    method = CFG["snip_method"]
    try:
        if method == "win+shift+s":
            import keyboard
            keyboard.send("windows+shift+s")
        else:
            os.startfile("ms-screenclip:")
    except Exception as e:
        log(f"启动截图失败({method})，改用键盘方式: {e}")
        import keyboard
        keyboard.send("windows+shift+s")
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(0.15)
        if clip_seq() != seq:
            img = ImageGrab.grabclipboard()
            if isinstance(img, Image.Image):
                return img
            seq = clip_seq()
    return None


def clipboard_image():
    img = ImageGrab.grabclipboard()
    return img if isinstance(img, Image.Image) else None


class SnipOverlay:
    """全屏半透明遮罩：拖动框选一块区域，直接从内存截取。
    不调用系统截图工具、不写磁盘、不经过剪贴板；完成后回调 on_done(PIL图 或 None=取消)。"""

    def __init__(self, master, on_done):
        self.on_done = on_done
        self.done = False
        self.start = None
        self.rect_id = None
        self.win = tk.Toplevel(master)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.title("RnoteSnipOverlay")
        u = ctypes.windll.user32
        sw, sh = u.GetSystemMetrics(0), u.GetSystemMetrics(1)
        self.win.geometry(f"{sw}x{sh}+0+0")
        try:
            self.win.attributes("-alpha", 0.35)     # 半透明变暗，能看清下面
        except Exception:
            pass
        self.canvas = tk.Canvas(self.win, bg="#0b0e14", highlightthickness=0,
                                cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_text(sw // 2, 44, text="拖动框选公式 · Esc / 右键 取消",
                                fill="#e6e9f0", font=("Microsoft YaHei UI", 13))
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<Button-3>", lambda e: self._finish(None))
        self.win.bind("<Escape>", lambda e: self._finish(None))
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()
        try:
            self.win.grab_set()
        except Exception:
            pass

    def _press(self, e):
        self.start = (e.x_root, e.y_root)

    def _drag(self, e):
        if not self.start:
            return
        x0, y0 = self.start
        if self.rect_id is None:
            self.rect_id = self.canvas.create_rectangle(x0, y0, e.x_root, e.y_root,
                                                        outline="#7fd0ff", width=2)
        else:
            self.canvas.coords(self.rect_id, x0, y0, e.x_root, e.y_root)

    def _release(self, e):
        if not self.start:
            self._finish(None)
            return
        x0, y0 = self.start
        x1, y1 = e.x_root, e.y_root
        l, t = min(x0, x1), min(y0, y1)
        r, b = max(x0, x1), max(y0, y1)
        if r - l < 12 or b - t < 12:        # 误触，取消
            self._finish(None)
            return
        self._finish((l, t, r, b))

    def _finish(self, bbox):
        if self.done:
            return
        self.done = True
        try:
            self.win.grab_release()
        except Exception:
            pass
        self.win.destroy()
        if bbox is None:
            log("框选取消")
            self.on_done(None)
            return
        log(f"框选区域: {bbox}")

        def _grab():
            time.sleep(0.18)                # 等 DWM 把遮罩从画面撤掉再截
            try:
                img = ImageGrab.grab(bbox=bbox, all_screens=True)
            except Exception as ex:
                log(f"内置截图失败: {ex}")
                img = None
            self.on_done(img)

        threading.Thread(target=_grab, daemon=True).start()


class HelperApp:
    def __init__(self):
        self.cfg = CFG
        self.q = queue.Queue()
        self.popup = None
        self.busy = False
        self.tray = None
        self._overlay = None
        self._status = None
        self.root = tk.Tk()
        self.root.withdraw()
        self._register_hotkeys()
        self.root.after(80, self._poll_queue)
        threading.Thread(target=self._preload, daemon=True).start()

    # ------------------------------------------------------------ 热键
    def _register_hotkeys(self):
        import keyboard
        keyboard.add_hotkey(self.cfg["hotkey"], lambda: self.q.put(("snip",)))
        keyboard.add_hotkey(self.cfg["clipboard_hotkey"], lambda: self.q.put(("clip",)))
        keyboard.add_hotkey(self.cfg["quit_hotkey"], lambda: self.q.put(("quit",)))
        log(f"热键已注册: {self.cfg['hotkey']} 截屏识别 / "
            f"{self.cfg['clipboard_hotkey']} 剪贴板 / {self.cfg['quit_hotkey']} 退出")

    def _preload(self):
        try:
            t0 = time.time()
            pipeline.warmup()
            pipeline.render_latex("x^2", 14, "#ffffff")   # 预热 matplotlib
            log(f"预热完成 ({time.time() - t0:.1f}s)")
        except Exception:
            log("预热失败(不影响启动):\n" + traceback.format_exc())

    # ------------------------------------------------------------ 队列/线程
    def _poll_queue(self):
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "snip":
                    self._begin_snip()
                elif kind == "snipimg":
                    self._on_snip_image(msg[1])
                elif kind == "clip":
                    self._start_worker(True)
                elif kind == "result":
                    self._show_result(*msg[1])
                elif kind == "error":
                    self._show_error(msg[1])
                elif kind == "quit":
                    self._quit()
                    return
        except queue.Empty:
            pass
        self.root.after(80, self._poll_queue)

    def _begin_snip(self):
        """截屏识别入口：默认内置框选；可在 config.json 换回系统截图工具。"""
        if self.busy:
            log("忙（上一次还没处理完），忽略本次请求")
            return
        if self.cfg.get("snip_method", "builtin") == "builtin":
            self.busy = True
            log("开始内置框选")
            try:
                self._overlay = SnipOverlay(self.root, lambda im: self.q.put(("snipimg", im)))
            except Exception:
                self.busy = False
                log("内置框选启动失败，改用系统截图:\n" + traceback.format_exc())
                self._start_worker(False)
        else:
            self._start_worker(False)

    def _on_snip_image(self, img):
        self.busy = False
        if img is None:
            return                          # 取消框选
        self._start_worker_img(img, "画面框选")

    def _start_worker(self, from_clipboard):
        if self.busy:
            return
        self.busy = True
        threading.Thread(target=self._worker, args=(from_clipboard,), daemon=True).start()

    def _start_worker_img(self, img, note):
        if self.busy:
            return
        self.busy = True
        threading.Thread(target=self._worker_img, args=(img, note), daemon=True).start()

    def _worker_img(self, img, note):
        try:
            log("触发: " + note)
            self._process(img)
        except Exception:
            log("处理出错:\n" + traceback.format_exc())
            self.q.put(("error", "出错了，详情见 C:\\rnote-ocr\\rnote-ocr.log"))
        finally:
            self.busy = False

    def _worker(self, from_clipboard):
        try:
            log("触发: " + ("剪贴板识别" if from_clipboard else "截屏识别"))
            if from_clipboard:
                img = clipboard_image()
                if img is None:
                    log("剪贴板里没有图片")
                    self.q.put(("error", "剪贴板里没有图片"))
                    return
            else:
                img = snip_image(self.cfg["snip_timeout_s"])
                if img is None:
                    log("截屏取消或超时")
                    return      # 取消或超时，静默结束
            self._process(img)
        except Exception:
            log("处理出错:\n" + traceback.format_exc())
            self.q.put(("error", "出错了，详情见 C:\\rnote-ocr\\rnote-ocr.log"))
        finally:
            self.busy = False

    def _process(self, img):
        log(f"已截取 {img.size[0]}x{img.size[1]}")
        latex = pipeline.ocr_latex(img)
        log(f"识别结果: {latex}")
        if not latex.strip():
            self.q.put(("error", "没识别到公式：框紧一点、写大一点再试试"))
            return
        res = pipeline.compute(latex)
        self.q.put(("result", (img, latex, res)))

    def _quit(self):
        try:
            if self.tray:
                self.tray.stop()
        except Exception:
            pass
        self.root.destroy()

    # ------------------------------------------------------------ 结果弹窗
    def _show_result(self, img, latex, r):
        if self.popup is not None and self.popup.winfo_exists():
            self.popup.destroy()
        win = tk.Toplevel(self.root)
        self.popup = win
        win.title("公式助手")
        win.configure(bg=BG)
        win.attributes("-topmost", True)
        try:
            win.iconbitmap(str(BASE / "icon.ico"))
        except Exception:
            pass

        self._cur_latex = latex
        self._cur_res = r
        self._main_text = r.get("main_text") or latex

        frm = tk.Frame(win, bg=BG, padx=16, pady=12)
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text="识别到的公式", bg=BG, fg=SUB,
                 font=("Microsoft YaHei UI", 9)).pack(anchor="w")
        self._render_into(frm, latex, color="#d7dcea", size=20)

        self._res_holder = tk.Frame(frm, bg=BG)
        self._res_holder.pack(fill="x")
        if r.get("main_latex"):
            self._set_main(r["main_latex"])
        if r.get("error"):
            tk.Label(frm, text=r["error"], bg=BG, fg="#ffb4a8", wraplength=520,
                     justify="left", font=("Microsoft YaHei UI", 10)).pack(anchor="w", pady=(4, 0))

        rows = r.get("results") or []
        txt = tk.Text(frm, height=min(6, max(2, len(rows) + 1)), bg=PANEL, fg=FG,
                      relief="flat", wrap="word", font=("Microsoft YaHei UI", 10),
                      insertbackground=FG)
        txt.pack(fill="x", pady=(8, 0))
        content = "\n".join(f"[{l}] {t}" for (l, _, t) in rows)
        txt.insert("1.0", content or "（没有算出结果）")
        txt.bind("<Key>", lambda e: "break")    # 只读但可选中复制
        self._txt = txt

        row1 = tk.Frame(frm, bg=BG)
        row1.pack(fill="x", pady=(10, 2))
        row2 = tk.Frame(frm, bg=BG)
        row2.pack(fill="x", pady=(2, 0))

        def mkbtn(parent, text, cmd, accent=False):
            b = tk.Button(parent, text=text, command=cmd,
                          bg=(ACCENT_BG if accent else "#2c3242"),
                          fg=("#10141c" if accent else FG),
                          activebackground="#3a4258", activeforeground="#ffffff",
                          relief="flat", padx=10, pady=3, cursor="hand2",
                          font=("Microsoft YaHei UI", 10))
            b.pack(side="left", padx=(0, 6))
            return b

        mkbtn(row1, "复制结果", self._copy_main, True)
        mkbtn(row1, "复制 LaTeX", lambda: self._copy_text(latex))
        mkbtn(row1, "重新框选", lambda: self._retry(win))
        mkbtn(row1, "关闭 (Esc)", win.destroy)

        for label, op in [("解方程", "solve"), ("求导", "diff"), ("积分", "integrate"),
                          ("化简", "simplify"), ("因式分解", "factor"), ("展开", "expand"),
                          ("数值", "numeric")]:
            mkbtn(row2, label, (lambda o=op: self._do_op(o)))
        mkbtn(row2, "WolframAlpha", lambda: self._open_wolfram(latex))

        self._status = tk.Label(frm, text="", bg=BG, fg=OK_GREEN,
                                font=("Microsoft YaHei UI", 9))
        self._status.pack(anchor="e")

        win.bind("<Escape>", lambda e: win.destroy())

        if self.cfg.get("auto_copy") and r.get("ok") and r.get("main_text"):
            self._copy_text(r["main_text"], quiet=True)
            self._flash("主结果已自动复制到剪贴板 ✓")

        # 定位到光标附近（限制在主屏幕内）
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        reqw, reqh = win.winfo_reqwidth(), win.winfo_reqheight()
        cx, cy = cursor_pos()
        x = min(max(10, cx - reqw // 3), max(10, sw - reqw - 20))
        y = min(max(10, cy + 24), max(10, sh - reqh - 60))
        win.geometry(f"+{x}+{y}")
        win.lift()
        try:
            win.focus_force()
        except Exception:
            pass

    def _render_into(self, parent, latex, color, size):
        try:
            im = pipeline.render_latex(latex, fontsize=size, color=color)
            photo = ImageTk.PhotoImage(im)
            lbl = tk.Label(parent, image=photo, bg=BG)
            lbl.image = photo
            lbl.pack(anchor="w", pady=(2, 6))
        except Exception:
            tk.Label(parent, text=latex, bg=BG, fg=FG, wraplength=520, justify="left",
                     font=("Consolas", 11)).pack(anchor="w", pady=(2, 6))

    def _set_main(self, latex):
        for c in self._res_holder.winfo_children():
            c.destroy()
        tk.Label(self._res_holder, text="=", bg=BG, fg=SUB,
                 font=("Microsoft YaHei UI", 12)).pack(anchor="w", pady=(2, 0))
        self._render_into(self._res_holder, latex, color=ACCENT, size=24)

    def _do_op(self, op):
        try:
            label, lt, tt = pipeline.do_op(self._cur_res["expr"], self._cur_res["sym"], op)
        except Exception as e:
            label, lt, tt = op, None, f"操作失败: {e}"
        self._txt.insert("end", f"\n[{label}] {tt}")
        self._txt.see("end")
        if lt:
            self._set_main(lt)
        if tt and not str(tt).startswith("操作失败"):
            self._main_text = tt
        self._flash(f"{label} ✓")

    def _copy_text(self, text, quiet=False):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            if not quiet:
                self._flash("已复制到剪贴板 ✓")
        except Exception as e:
            log(f"复制失败: {e}")

    def _copy_main(self):
        self._copy_text(self._main_text or self._cur_latex)

    def _flash(self, text):
        if self._status is None:
            return
        try:
            self._status.configure(text=text)
            self._status.after(1600, lambda: self._status.configure(text=""))
        except Exception:
            pass

    def _retry(self, win):
        win.destroy()
        self.q.put(("snip",))

    def _open_wolfram(self, latex):
        self._copy_text(latex, quiet=True)
        url = "https://www.wolframalpha.com/input?i=" + urllib.parse.quote(latex)
        try:
            os.startfile(url)
            self._flash("LaTeX 已复制，浏览器已打开 WolframAlpha")
        except Exception as e:
            self._flash(f"打开浏览器失败: {e}")

    def _show_error(self, msg):
        self._toast(msg, bg="#4a2530", fg="#ffcfc8")

    # ------------------------------------------------------------ 提示条
    def _toast(self, text, ms=3200, bg="#2b3245", fg="#dfe6f5"):
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=bg)
        tk.Label(win, text=text, bg=bg, fg=fg, font=("Microsoft YaHei UI", 10),
                 padx=14, pady=8).pack()
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"+{sw - win.winfo_reqwidth() - 24}+{sh - win.winfo_reqheight() - 72}")
        win.after(ms, win.destroy)

    # ------------------------------------------------------------ 托盘
    def start_tray(self):
        try:
            import pystray

            img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.rounded_rectangle([2, 2, 62, 62], radius=14, fill=(58, 92, 168, 255))
            try:
                from PIL import ImageFont
                f = ImageFont.truetype("segoeuib.ttf", 30)
            except Exception:
                f = None
            d.text((14, 16), "fx", fill=(255, 255, 255, 255), font=f)
            menu = pystray.Menu(
                pystray.MenuItem("识别公式 (截图)", lambda: self.q.put(("snip",))),
                pystray.MenuItem("识别剪贴板图片", lambda: self.q.put(("clip",))),
                pystray.MenuItem("退出", lambda: self.q.put(("quit",))),
            )
            self.tray = pystray.Icon("rnote_ocr", img, "Rnote 公式助手", menu)
            threading.Thread(target=self.tray.run, daemon=True).start()
            log("托盘图标已启动")
        except Exception:
            log("托盘启动失败(不影响使用):\n" + traceback.format_exc())

    def run(self):
        self._toast(f"公式助手已就绪 · {self.cfg['hotkey']} 截取公式并计算", ms=3000)
        self.root.mainloop()


def main():
    if os.name != "nt":
        raise SystemExit("仅支持 Windows")
    if sys.stderr is None:      # pythonw 下没有控制台，防止库往 None 写
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    # 单实例保护：已有实例在跑就提示并退出，避免热键/托盘重复注册
    k32 = ctypes.windll.kernel32
    k32.CreateMutexW.restype = ctypes.c_void_p
    k32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    k32.CreateMutexW(None, False, "RnoteOcrHelper_SingleInstance")
    if k32.GetLastError() == 183:      # ERROR_ALREADY_EXISTS
        log("已有实例在运行，本次启动退出")
        ctypes.windll.user32.MessageBoxW(
            None, "公式助手已经在运行了（看右下角托盘 fx 图标）。", "Rnote 公式助手", 0x40)
        raise SystemExit(0)
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    (BASE / ".pid").write_text(str(os.getpid()), encoding="utf-8")
    log("=== 启动 ===")
    app = HelperApp()
    app.start_tray()
    try:
        app.run()
    finally:
        log("=== 退出 ===")


if __name__ == "__main__":
    main()
