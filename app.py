# -*- coding: utf-8 -*-
"""Rnote 公式助手 — 主程序
默认热键：ctrl+alt+shift+m 截取公式识别 / ctrl+alt+shift+c 识别剪贴板图片 / ctrl+alt+shift+q 退出。
弹窗右上角可现场修改快捷键、切换中/英文；弹窗里还能手动编辑/修正公式；也可直接编辑 config.json（hotkey / language 等）。
"""
import ctypes
import json
import os
import queue
import re
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
    "hotkey": "ctrl+alt+shift+m",
    "clipboard_hotkey": "ctrl+alt+shift+c",
    "quit_hotkey": "ctrl+alt+shift+q",
    "language": "zh",
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
BTN_BG = "#2c3242"
BTN_ACTIVE = "#3a4258"
FONT = "Microsoft YaHei UI"

# ---------------------------------------------------------------- 界面文案（中文 / English）
STRINGS = {
    "zh": {
        "app_name": "Rnote 公式助手",
        "snip_hint": "拖动框选公式 · Esc / 右键 取消",
        "recognized_label": "识别到的公式",
        "btn_hotkeys": "快捷键",
        "btn_language": "language",
        "btn_edit": "编辑",
        "edit_title": "编辑公式",
        "edit_hint": "直接修改 LaTeX，或手输普通算式（例：2x+7=15），改完点「重新计算」。",
        "edit_recalc": "重新计算",
        "edit_empty": "还没输入公式",
        "btn_copy_main": "复制结果",
        "btn_copy_latex": "复制 LaTeX",
        "btn_retry": "重新框选",
        "btn_close": "关闭 (Esc)",
        "op_solve": "解方程",
        "op_diff": "求导",
        "op_integrate": "积分",
        "op_simplify": "化简",
        "op_factor": "因式分解",
        "op_expand": "展开",
        "op_numeric": "数值",
        "no_result": "（没有算出结果）",
        "flash_copied": "已复制到剪贴板 ✓",
        "flash_auto_copy": "主结果已自动复制到剪贴板 ✓",
        "flash_wolfram": "LaTeX 已复制，浏览器已打开 WolframAlpha",
        "flash_wolfram_fail": "打开浏览器失败：",
        "op_failed": "操作失败：",
        "err_see_log": "出错了，详情见 rnote-ocr.log",
        "err_no_formula": "没识别到公式：框紧一点、写大一点再试试",
        "err_no_clipboard": "剪贴板里没有图片",
        "err_parse": "公式已识别，但没法解析成算式（可点 WolframAlpha 复制过去算）：",
        "err_compute": "计算失败：",
        "ready_toast": "公式助手已就绪 · {hk} 截取公式并计算",
        "already_running": "公式助手已经在运行了（看右下角托盘 fx 图标）。",
        "tray_snip": "识别公式 (截图)",
        "tray_clip": "识别剪贴板图片",
        "tray_manual": "手动输入公式…",
        "tray_hotkeys": "快捷键设置…",
        "tray_language": "语言：切换中/英",
        "tray_quit": "退出",
        "hk_title": "快捷键设置",
        "hk_snip": "框选识别",
        "hk_clip": "识别剪贴板",
        "hk_quit": "退出助手",
        "hk_change": "修改",
        "hk_press": "请按下新快捷键…（Esc 取消）",
        "hk_mods_snip_only": "纯修饰键组合只能用于「框选识别」",
        "hk_save": "保存",
        "hk_cancel": "取消",
        "hk_reset": "恢复默认",
        "hk_need_mod": "至少要包含 Ctrl 或 Alt",
        "hk_bad_key": "这个键不支持，换一个",
        "hk_dup": "和其他功能重复了，换一个",
        "hk_saved": "已保存，立即生效 ✓",
        "hk_save_fail": "保存失败：",
        "lang_switched": "已切换为中文",
    },
    "en": {
        "app_name": "Rnote Formula Helper",
        "snip_hint": "Drag to select the formula · Esc / right-click to cancel",
        "recognized_label": "Recognized formula",
        "btn_hotkeys": "Hotkeys",
        "btn_language": "language",
        "btn_edit": "Edit",
        "edit_title": "Edit formula",
        "edit_hint": "Fix the LaTeX, or type a plain formula (e.g. 2x+7=15), then click Recalculate.",
        "edit_recalc": "Recalculate",
        "edit_empty": "Nothing entered yet",
        "btn_copy_main": "Copy result",
        "btn_copy_latex": "Copy LaTeX",
        "btn_retry": "Reselect",
        "btn_close": "Close (Esc)",
        "op_solve": "Solve",
        "op_diff": "Derivative",
        "op_integrate": "Integral",
        "op_simplify": "Simplify",
        "op_factor": "Factor",
        "op_expand": "Expand",
        "op_numeric": "Numeric",
        "no_result": "(no result)",
        "flash_copied": "Copied to clipboard ✓",
        "flash_auto_copy": "Result auto-copied to clipboard ✓",
        "flash_wolfram": "LaTeX copied; WolframAlpha opened in the browser",
        "flash_wolfram_fail": "Failed to open browser: ",
        "op_failed": "Operation failed: ",
        "err_see_log": "Something went wrong — see rnote-ocr.log",
        "err_no_formula": "No formula recognized — select a tighter box and write larger",
        "err_no_clipboard": "No image in the clipboard",
        "err_parse": "Formula recognized, but it could not be parsed (try the WolframAlpha button): ",
        "err_compute": "Computation failed: ",
        "ready_toast": "Helper ready · press {hk} to capture a formula",
        "already_running": "The helper is already running (look for the fx tray icon).",
        "tray_snip": "Recognize formula (screen)",
        "tray_clip": "Recognize clipboard image",
        "tray_manual": "Enter formula manually…",
        "tray_hotkeys": "Hotkey settings…",
        "tray_language": "Language: 中文 / English",
        "tray_quit": "Quit",
        "hk_title": "Hotkey settings",
        "hk_snip": "Screen selection",
        "hk_clip": "Clipboard image",
        "hk_quit": "Quit helper",
        "hk_change": "Change",
        "hk_press": "Press the new hotkey… (Esc to cancel)",
        "hk_mods_snip_only": "A modifier-only combo can only be used for Screen selection",
        "hk_save": "Save",
        "hk_cancel": "Cancel",
        "hk_reset": "Reset defaults",
        "hk_need_mod": "Must include at least Ctrl or Alt",
        "hk_bad_key": "That key is not supported — try another",
        "hk_dup": "Already used by another action",
        "hk_saved": "Saved — active immediately ✓",
        "hk_save_fail": "Save failed: ",
        "lang_switched": "Switched to English",
    },
}

# 管道（pipeline.py）里产生的标签/文字 → 英文界面显示用
_PIPE_LABELS_EN = {
    "解方程": "Solve",
    "计算": "Result",
    "结果": "Result",
    "约等于": "≈",
    "化简": "Simplify",
    "因式分解": "Factor",
    "展开": "Expand",
    "数值": "Numeric",
    "求导": "Derivative",
    "积分": "Integral",
    "附加信息": "Extra",
    "方程": "Equation",
}
_TEXT_REPL_EN = {
    "✓ 等式成立": "✓ holds",
    "✗ 等式不成立": "✗ does not hold",
    "无解或没解出来": "No solution found",
}

_MOD_KEYS = {"Control_L": "ctrl", "Control_R": "ctrl", "Alt_L": "alt", "Alt_R": "alt",
             "Shift_L": "shift", "Shift_R": "shift"}
_MOD_ORDER = ["ctrl", "alt", "shift"]
_KEY_OK_RE = re.compile(r"^[a-z0-9]+$")
_EXTRA_KEYS = {"space", "tab", "enter", "backspace", "delete", "insert", "home", "end",
               "up", "down", "left", "right"}


def load_cfg():
    cfg = dict(DEFAULT_CFG)
    try:
        cfg.update(json.loads((BASE / "config.json").read_text(encoding="utf-8")))
    except Exception as e:
        log(f"读取 config.json 失败，用默认值: {e}")
    return cfg


CFG = load_cfg()


def save_cfg(cfg):
    """把当前配置写回 config.json（改快捷键 / 切语言后调用）。"""
    try:
        (BASE / "config.json").write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception as e:
        log(f"保存 config.json 失败: {e}")


def lang() -> str:
    v = CFG.get("language", "zh")
    return v if v in STRINGS else "zh"


def t(key: str, **kw) -> str:
    s = STRINGS.get(lang(), {}).get(key) or STRINGS["zh"].get(key, key)
    if kw:
        try:
            return s.format(**kw)
        except Exception:
            return s
    return s


def _tlabel(label: str) -> str:
    if lang() == "en":
        return _PIPE_LABELS_EN.get(label, label)
    return label


def _disp_text(s) -> str:
    s = str(s)
    if lang() == "en":
        for k, v in _TEXT_REPL_EN.items():
            s = s.replace(k, v)
    return s


def _combo_from(held, keyname: str) -> str:
    parts = [m for m in _MOD_ORDER if m in held]
    if keyname:
        parts.append(keyname.lower())
    return "+".join(parts)


def _pretty_hotkey(combo: str) -> str:
    names = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "win": "Win"}
    out = []
    for p in combo.split("+"):
        if p in names:
            out.append(names[p])
        elif len(p) == 1:
            out.append(p.upper())
        else:
            out.append(p.capitalize())
    return "+".join(out)


def _is_mods_only(combo: str) -> bool:
    """纯修饰键组合（如 ctrl+alt+shift）：按下即触发，没有普通键。"""
    parts = [p for p in (combo or "").split("+") if p]
    return bool(parts) and all(p in ("ctrl", "alt", "shift", "win") for p in parts)


def _valid_key_name(name: str) -> bool:
    name = name.lower()
    return bool(_KEY_OK_RE.match(name)) or name in _EXTRA_KEYS


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
        self.canvas.create_text(sw // 2, 44, text=t("snip_hint"),
                                fill="#e6e9f0", font=(FONT, 13))
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
        l, t_ = min(x0, x1), min(y0, y1)
        r, b = max(x0, x1), max(y0, y1)
        if r - l < 12 or b - t_ < 12:        # 误触，取消
            self._finish(None)
            return
        self._finish((l, t_, r, b))

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
        self._hk_handles = []
        self._capture_active = False
        self._hk_win = None
        self._cur_latex = None
        self._cur_res = None
        self._main_text = None
        self._snip_after_id = None
        self._edit_win = None
        self.root = tk.Tk()
        self.root.withdraw()
        self._register_hotkeys()
        self.root.after(80, self._poll_queue)
        threading.Thread(target=self._preload, daemon=True).start()

    # ------------------------------------------------------------ 热键
    def _hotkey_fire(self, kind):
        if self._capture_active:
            return                          # 正在录制新快捷键时，旧热键不响应
        self.q.put((kind,))

    def _register_hotkeys(self):
        import keyboard
        self._hk_handles = [
            keyboard.add_hotkey(self.cfg["hotkey"], lambda: self._hotkey_fire("snip")),
            keyboard.add_hotkey(self.cfg["clipboard_hotkey"], lambda: self._hotkey_fire("clip")),
            keyboard.add_hotkey(self.cfg["quit_hotkey"], lambda: self._hotkey_fire("quit")),
        ]
        log(f"热键已注册: {self.cfg['hotkey']} 截屏识别 / "
            f"{self.cfg['clipboard_hotkey']} 剪贴板 / {self.cfg['quit_hotkey']} 退出")

    def apply_hotkeys(self, hotkey, clipboard_hotkey, quit_hotkey):
        """更换热键并写入 config.json。成功返回 None；失败返回错误信息（保留旧热键）。"""
        import keyboard
        old = (self.cfg["hotkey"], self.cfg["clipboard_hotkey"], self.cfg["quit_hotkey"])
        for h in self._hk_handles:
            try:
                keyboard.remove_hotkey(h)
            except Exception:
                pass
        self._hk_handles = []
        handles = []
        try:
            handles.append(keyboard.add_hotkey(hotkey, lambda: self._hotkey_fire("snip")))
            handles.append(keyboard.add_hotkey(clipboard_hotkey, lambda: self._hotkey_fire("clip")))
            handles.append(keyboard.add_hotkey(quit_hotkey, lambda: self._hotkey_fire("quit")))
        except Exception as e:
            for h in handles:
                try:
                    keyboard.remove_hotkey(h)
                except Exception:
                    pass
            try:                            # 回滚到旧热键
                self._hk_handles.append(keyboard.add_hotkey(old[0], lambda: self._hotkey_fire("snip")))
                self._hk_handles.append(keyboard.add_hotkey(old[1], lambda: self._hotkey_fire("clip")))
                self._hk_handles.append(keyboard.add_hotkey(old[2], lambda: self._hotkey_fire("quit")))
            except Exception:
                log("热键回滚失败")
            return str(e)
        self._hk_handles = handles
        self.cfg.update(hotkey=hotkey, clipboard_hotkey=clipboard_hotkey, quit_hotkey=quit_hotkey)
        save_cfg(self.cfg)
        log(f"热键已更新: {hotkey} / {clipboard_hotkey} / {quit_hotkey}")
        return None

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
                    if _is_mods_only(self.cfg["hotkey"]):
                        self._schedule_snip()   # 纯修饰键：延迟一步，紧跟其后的 C/Q 组合可把它取消
                    else:
                        self._begin_snip()
                elif kind == "snipimg":
                    self._on_snip_image(msg[1])
                elif kind == "manual":
                    self._open_formula_editor(None)
                elif kind == "clip":
                    self._cancel_pending_snip()
                    self._start_worker(True)
                elif kind == "result":
                    self._show_result(*msg[1])
                elif kind == "error":
                    self._show_error(msg[1])
                elif kind == "open_hk":
                    self._open_hotkey_settings()
                elif kind == "toggle_lang":
                    self._on_toggle_language()
                elif kind == "quit":
                    self._cancel_pending_snip()
                    self._quit()
                    return
        except queue.Empty:
            pass
        self.root.after(80, self._poll_queue)

    def _schedule_snip(self):
        """纯修饰键组合：延迟 350ms 再弹框选，给 Ctrl+Alt+Shift+C / +Q 留出取消窗口。"""
        if self._snip_after_id is not None:
            return
        self._snip_after_id = self.root.after(350, self._snip_now)

    def _snip_now(self):
        self._snip_after_id = None
        # 延迟期间如果按了别的键（老的 M、或别家软件的组合键），说明用户想按的不是纯修饰键 —— 取消
        try:
            import keyboard
            with keyboard._pressed_events_lock:
                pressed = set(keyboard._pressed_events)
            allowed = set()
            for part in self.cfg["hotkey"].split("+"):
                allowed.update(keyboard.key_to_scan_codes(part, False))
            if pressed and not pressed <= allowed:
                log("框选等待期间检测到其他按键，已取消")
                return
        except Exception:
            pass
        self._begin_snip()

    def _cancel_pending_snip(self):
        if self._snip_after_id is not None:
            try:
                self.root.after_cancel(self._snip_after_id)
            except Exception:
                pass
            self._snip_after_id = None

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
            self.q.put(("error", t("err_see_log")))
        finally:
            self.busy = False

    def _worker(self, from_clipboard):
        try:
            log("触发: " + ("剪贴板识别" if from_clipboard else "截屏识别"))
            if from_clipboard:
                img = clipboard_image()
                if img is None:
                    log("剪贴板里没有图片")
                    self.q.put(("error", t("err_no_clipboard")))
                    return
            else:
                img = snip_image(self.cfg["snip_timeout_s"])
                if img is None:
                    log("截屏取消或超时")
                    return      # 取消或超时，静默结束
            self._process(img)
        except Exception:
            log("处理出错:\n" + traceback.format_exc())
            self.q.put(("error", t("err_see_log")))
        finally:
            self.busy = False

    def _process(self, img):
        log(f"已截取 {img.size[0]}x{img.size[1]}")
        latex = pipeline.ocr_latex(img)
        log(f"识别结果: {latex}")
        if not latex.strip():
            self.q.put(("error", t("err_no_formula")))
            return
        res = pipeline.compute(latex)
        self.q.put(("result", (img, latex, res)))

    def _quit(self):
        if self.tray:
            try:                                # 后台线程里停托盘，别把退出卡住（进程随后即退）
                threading.Thread(target=self.tray.stop, daemon=True).start()
            except Exception:
                pass
        self.root.destroy()

    # ------------------------------------------------------------ 结果弹窗
    def _show_result(self, img, latex, r, autocopy=None):
        if self.popup is not None and self.popup.winfo_exists():
            self.popup.destroy()
        win = tk.Toplevel(self.root)
        self.popup = win
        win.title(t("app_name"))
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

        # 顶部一行：左"识别到的公式"；右上角「快捷键」「语言」按钮
        head = tk.Frame(frm, bg=BG)
        head.pack(fill="x")
        tk.Label(head, text=t("recognized_label"), bg=BG, fg=SUB,
                 font=(FONT, 9)).pack(side="left")
        tk.Button(head, text=t("btn_language"), command=self._on_toggle_language,
                  bg=BTN_BG, fg=SUB, activebackground=BTN_ACTIVE,
                  activeforeground="#ffffff", relief="flat", padx=8, pady=0,
                  cursor="hand2", font=(FONT, 8)).pack(side="right")
        tk.Button(head, text=t("btn_hotkeys"), command=self._open_hotkey_settings,
                  bg=BTN_BG, fg=SUB, activebackground=BTN_ACTIVE,
                  activeforeground="#ffffff", relief="flat", padx=8, pady=0,
                  cursor="hand2", font=(FONT, 8)).pack(side="right", padx=(0, 6))

        self._render_into(frm, latex, color="#d7dcea", size=20)

        self._res_holder = tk.Frame(frm, bg=BG)
        self._res_holder.pack(fill="x")
        if r.get("main_latex"):
            self._set_main(r["main_latex"])
        if r.get("error"):
            kind = r.get("error_kind")
            detail = r.get("error_detail") or ""
            if kind == "parse":
                etext = t("err_parse") + detail
            elif kind == "compute":
                etext = t("err_compute") + detail
            else:
                etext = r["error"]
            tk.Label(frm, text=etext, bg=BG, fg="#ffb4a8", wraplength=520,
                     justify="left", font=(FONT, 10)).pack(anchor="w", pady=(4, 0))

        rows = r.get("results") or []
        txt = tk.Text(frm, height=min(6, max(2, len(rows) + 1)), bg=PANEL, fg=FG,
                      relief="flat", wrap="word", font=(FONT, 10),
                      insertbackground=FG)
        txt.pack(fill="x", pady=(8, 0))
        content = "\n".join(f"[{_tlabel(l)}] {_disp_text(tt)}" for (l, _, tt) in rows)
        txt.insert("1.0", content or t("no_result"))
        txt.bind("<Key>", lambda e: "break")    # 只读但可选中复制
        self._txt = txt

        row1 = tk.Frame(frm, bg=BG)
        row1.pack(fill="x", pady=(10, 2))
        row2 = tk.Frame(frm, bg=BG)
        row2.pack(fill="x", pady=(2, 0))

        def mkbtn(parent, text, cmd, accent=False):
            b = tk.Button(parent, text=text, command=cmd,
                          bg=(ACCENT_BG if accent else BTN_BG),
                          fg=("#10141c" if accent else FG),
                          activebackground=BTN_ACTIVE, activeforeground="#ffffff",
                          relief="flat", padx=10, pady=3, cursor="hand2",
                          font=(FONT, 10))
            b.pack(side="left", padx=(0, 6))
            return b

        mkbtn(row1, t("btn_copy_main"), self._copy_main, True)
        mkbtn(row1, t("btn_copy_latex"), lambda: self._copy_text(latex))
        mkbtn(row1, t("btn_edit"), lambda: self._open_formula_editor(self._cur_latex))
        mkbtn(row1, t("btn_retry"), lambda: self._retry(win))
        mkbtn(row1, t("btn_close"), win.destroy)

        for op, key in [("solve", "op_solve"), ("diff", "op_diff"), ("integrate", "op_integrate"),
                        ("simplify", "op_simplify"), ("factor", "op_factor"),
                        ("expand", "op_expand"), ("numeric", "op_numeric")]:
            mkbtn(row2, t(key), (lambda o=op: self._do_op(o)))
        mkbtn(row2, "WolframAlpha", lambda: self._open_wolfram(latex))

        self._status = tk.Label(frm, text="", bg=BG, fg=OK_GREEN,
                                font=(FONT, 9))
        self._status.pack(anchor="e")

        win.bind("<Escape>", lambda e: win.destroy())

        if autocopy is None:
            autocopy = self.cfg.get("auto_copy")
        if autocopy and r.get("ok") and r.get("main_text"):
            self._copy_text(r["main_text"], quiet=True)
            self._flash(t("flash_auto_copy"))

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
                 font=(FONT, 12)).pack(anchor="w", pady=(2, 0))
        self._render_into(self._res_holder, latex, color=ACCENT, size=24)

    def _do_op(self, op):
        ok = True
        try:
            label, lt, tt = pipeline.do_op(self._cur_res["expr"], self._cur_res["sym"], op)
        except Exception as e:
            ok = False
            label = t("op_" + op)
            lt, tt = None, t("op_failed") + str(e)
        disp = _tlabel(label)
        self._txt.insert("end", f"\n[{disp}] {_disp_text(tt)}")
        self._txt.see("end")
        if lt:
            self._set_main(lt)
        if ok and tt:
            self._main_text = tt
        self._flash(f"{disp} ✓")

    def _open_formula_editor(self, initial=None):
        """手动输入/修改公式：改完重新解析计算，直接出结果。（识别有小错时用它修）"""
        if self._edit_win is not None and self._edit_win.winfo_exists():
            self._edit_win.lift()
            self._edit_win.focus_force()
            return
        win = tk.Toplevel(self.root)
        self._edit_win = win
        win.title(t("edit_title"))
        win.configure(bg=BG)
        win.attributes("-topmost", True)
        win.resizable(False, False)
        try:
            win.iconbitmap(str(BASE / "icon.ico"))
        except Exception:
            pass
        frm = tk.Frame(win, bg=BG, padx=16, pady=12)
        frm.pack(fill="both", expand=True)
        tk.Label(frm, text=t("edit_hint"), bg=BG, fg=SUB, font=(FONT, 9),
                 wraplength=470, justify="left").pack(anchor="w")
        entry = tk.Entry(frm, font=("Consolas", 12), width=56, bg=PANEL, fg=FG,
                         insertbackground=FG, relief="flat")
        entry.pack(fill="x", pady=(8, 0), ipady=4)
        if initial:
            entry.insert(0, initial)
        err = tk.Label(frm, text="", bg=BG, fg="#ffb4a8", font=(FONT, 9))
        err.pack(anchor="w")

        def close_editor():
            self._edit_win = None
            win.destroy()

        def recalc():
            s = entry.get().strip()
            if not s:
                err.configure(text=t("edit_empty"))
                return
            try:
                r = pipeline.compute(s)
            except Exception as e:
                log("手动输入计算失败:\n" + traceback.format_exc())
                r = {"ok": False, "expr": None, "sym": None, "main_latex": None,
                     "main_text": None, "results": [], "error": str(e),
                     "error_kind": "compute", "error_detail": str(e)}
            close_editor()
            self._show_result(None, s, r)

        brow = tk.Frame(frm, bg=BG)
        brow.pack(fill="x", pady=(10, 0))

        def mkbtn(text, cmd, accent=False):
            b = tk.Button(brow, text=text, command=cmd,
                          bg=(ACCENT_BG if accent else BTN_BG),
                          fg=("#10141c" if accent else FG),
                          activebackground=BTN_ACTIVE, activeforeground="#ffffff",
                          relief="flat", padx=10, pady=3, cursor="hand2",
                          font=(FONT, 10))
            b.pack(side="left", padx=(0, 6))
            return b

        mkbtn(t("edit_recalc"), recalc, True)
        mkbtn(t("hk_cancel"), close_editor)
        entry.bind("<Return>", lambda e: recalc())
        win.bind("<Escape>", lambda e: close_editor())
        win.protocol("WM_DELETE_WINDOW", close_editor)

        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        win.geometry(f"+{(sw - w) // 2}+{max(40, (sh - h) // 3)}")
        win.lift()
        win.focus_force()
        entry.focus_force()

    def _copy_text(self, text, quiet=False):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            if not quiet:
                self._flash(t("flash_copied"))
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
            self._flash(t("flash_wolfram"))
        except Exception as e:
            self._flash(t("flash_wolfram_fail") + str(e))

    def _show_error(self, msg):
        self._toast(msg, bg="#4a2530", fg="#ffcfc8")

    # ------------------------------------------------------------ 语言 / 设置
    def _on_toggle_language(self):
        new = "en" if lang() == "zh" else "zh"
        self.cfg["language"] = new
        save_cfg(self.cfg)
        self._refresh_tray_menu()
        if self._hk_win is not None and self._hk_win.winfo_exists():
            self._capture_active = False
            self._hk_win.destroy()          # 语言变了，设置窗下次重开
        if self.popup is not None and self.popup.winfo_exists():
            self._show_result(None, self._cur_latex, self._cur_res, autocopy=False)
        self._toast(t("lang_switched"), ms=1800)

    def _open_hotkey_settings(self):
        if self._hk_win is not None and self._hk_win.winfo_exists():
            self._hk_win.lift()
            self._hk_win.focus_force()
            return
        win = tk.Toplevel(self.root)
        self._hk_win = win
        win.title(t("hk_title"))
        win.configure(bg=BG)
        win.attributes("-topmost", True)
        win.resizable(False, False)
        try:
            win.iconbitmap(str(BASE / "icon.ico"))
        except Exception:
            pass

        frm = tk.Frame(win, bg=BG, padx=18, pady=14)
        frm.pack(fill="both", expand=True)

        values = {
            "hotkey": self.cfg["hotkey"],
            "clipboard_hotkey": self.cfg["clipboard_hotkey"],
            "quit_hotkey": self.cfg["quit_hotkey"],
        }
        rows = [("hotkey", "hk_snip"), ("clipboard_hotkey", "hk_clip"), ("quit_hotkey", "hk_quit")]
        state = {"which": None, "held": set(), "mods": set()}
        displays = {}

        hint = tk.Label(frm, text="", bg=BG, fg=SUB, font=(FONT, 9))
        err = tk.Label(frm, text="", bg=BG, fg="#ffb4a8", font=(FONT, 9))

        def refresh():
            for k in values:
                displays[k].configure(text=_pretty_hotkey(values[k]))

        def end_capture():
            state["which"] = None
            state["held"] = set()
            state["mods"] = set()
            self._capture_active = False
            hint.configure(text="")

        def start_capture(key):
            state["which"] = key
            state["held"] = set()
            state["mods"] = set()
            self._capture_active = True
            err.configure(text="")
            hint.configure(text=t("hk_press"))
            win.focus_force()

        def finish_capture(combo):
            which = state["which"]
            if "ctrl" not in combo and "alt" not in combo:
                err.configure(text=t("hk_need_mod"))
                end_capture()
                return
            if which != "hotkey" and _is_mods_only(combo):
                err.configure(text=t("hk_mods_snip_only"))
                end_capture()
                return
            if any(combo == v and k != which for k, v in values.items()):
                err.configure(text=t("hk_dup"))
                end_capture()
                return
            values[which] = combo
            err.configure(text="")
            end_capture()
            refresh()

        def on_key_press(e):
            if state["which"] is None:
                return
            ks = e.keysym
            mod = _MOD_KEYS.get(ks)
            if mod:
                state["held"].add(mod)
                state["mods"].add(mod)
                tmp = _combo_from(state["held"], "")
                hint.configure(text=(_pretty_hotkey(tmp) + "+…") if tmp else t("hk_press"))
                return "break"
            if not _valid_key_name(ks):
                err.configure(text=t("hk_bad_key"))
                end_capture()
                return "break"
            finish_capture(_combo_from(state["held"], ks))
            return "break"

        def on_key_release(e):
            if state["which"] is None:
                return
            mod = _MOD_KEYS.get(e.keysym)
            if mod:
                state["held"].discard(mod)
                if not state["held"] and len(state["mods"]) >= 2:
                    finish_capture("+".join(m for m in _MOD_ORDER if m in state["mods"]))

        def on_escape(e):
            if state["which"] is not None:
                end_capture()
            else:
                close_dialog()
            return "break"

        win.bind("<KeyPress>", on_key_press)
        win.bind("<KeyRelease>", on_key_release)
        win.bind("<Escape>", on_escape)

        for key, label_key in rows:
            r = tk.Frame(frm, bg=BG)
            r.pack(fill="x", pady=3)
            tk.Label(r, text=t(label_key), bg=BG, fg=FG, width=16, anchor="w",
                     font=(FONT, 10)).pack(side="left")
            d = tk.Label(r, text="", bg=PANEL, fg=ACCENT, width=22, anchor="center",
                         font=("Consolas", 11))
            d.pack(side="left", padx=8)
            displays[key] = d
            tk.Button(r, text=t("hk_change"), command=lambda k=key: start_capture(k),
                      bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE,
                      activeforeground="#ffffff", relief="flat", padx=10, pady=1,
                      cursor="hand2", font=(FONT, 10)).pack(side="left")
        refresh()

        hint.pack(anchor="w", pady=(8, 0))
        err.pack(anchor="w")

        brow = tk.Frame(frm, bg=BG)
        brow.pack(fill="x", pady=(12, 0))

        def mkbtn(text, cmd, accent=False):
            b = tk.Button(brow, text=text, command=cmd,
                          bg=(ACCENT_BG if accent else BTN_BG),
                          fg=("#10141c" if accent else FG),
                          activebackground=BTN_ACTIVE, activeforeground="#ffffff",
                          relief="flat", padx=10, pady=3, cursor="hand2",
                          font=(FONT, 10))
            b.pack(side="left", padx=(0, 6))
            return b

        def close_dialog():
            end_capture()
            win.destroy()

        def do_save():
            e = self.apply_hotkeys(values["hotkey"], values["clipboard_hotkey"], values["quit_hotkey"])
            if e:
                err.configure(text=t("hk_save_fail") + e)
            else:
                self._flash(t("hk_saved"))
                close_dialog()

        def do_reset():
            values.update({k: DEFAULT_CFG[k] for k in
                           ("hotkey", "clipboard_hotkey", "quit_hotkey")})
            err.configure(text="")
            refresh()

        mkbtn(t("hk_save"), do_save, accent=True)
        mkbtn(t("hk_cancel"), close_dialog)
        mkbtn(t("hk_reset"), do_reset)

        win.protocol("WM_DELETE_WINDOW", close_dialog)

        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        win.geometry(f"+{(sw - w) // 2}+{max(40, (sh - h) // 3)}")
        win.lift()
        win.focus_force()

    # ------------------------------------------------------------ 提示条
    def _toast(self, text, ms=3200, bg="#2b3245", fg="#dfe6f5"):
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=bg)
        tk.Label(win, text=text, bg=bg, fg=fg, font=(FONT, 10),
                 padx=14, pady=8).pack()
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"+{sw - win.winfo_reqwidth() - 24}+{sh - win.winfo_reqheight() - 72}")
        win.after(ms, win.destroy)

    # ------------------------------------------------------------ 托盘
    def _build_tray_menu(self):
        import pystray
        return pystray.Menu(
            pystray.MenuItem(t("tray_snip"), lambda: self.q.put(("snip",))),
            pystray.MenuItem(t("tray_clip"), lambda: self.q.put(("clip",))),
            pystray.MenuItem(t("tray_manual"), lambda: self.q.put(("manual",))),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(t("tray_hotkeys"), lambda: self.q.put(("open_hk",))),
            pystray.MenuItem(t("tray_language"), lambda: self.q.put(("toggle_lang",))),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(t("tray_quit"), lambda: self.q.put(("quit",))),
        )

    def _refresh_tray_menu(self):
        if self.tray is None:
            return
        try:
            self.tray.menu = self._build_tray_menu()
            self.tray.update_menu()
        except Exception:
            log("托盘菜单刷新失败:\n" + traceback.format_exc())

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
            self.tray = pystray.Icon("rnote_ocr", img, t("app_name"), self._build_tray_menu())
            threading.Thread(target=self.tray.run, daemon=True).start()
            log("托盘图标已启动")
        except Exception:
            log("托盘启动失败(不影响使用):\n" + traceback.format_exc())

    def run(self):
        self._toast(t("ready_toast", hk=_pretty_hotkey(self.cfg["hotkey"])), ms=3000)
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
    k32.CloseHandle.argtypes = [ctypes.c_void_p]

    def _acquire_mutex():
        m = k32.CreateMutexW(None, False, "RnoteOcrHelper_SingleInstance")
        if k32.GetLastError() == 183:      # ERROR_ALREADY_EXISTS
            k32.CloseHandle(m)             # 放掉本次句柄，免得旧实例退出后还被它"续命"
            return None
        return m

    mutex = _acquire_mutex()
    if mutex is None:
        # 旧实例可能正在退出（解释器清理要几秒）——最多等 3 秒再下结论
        for _ in range(6):
            time.sleep(0.5)
            mutex = _acquire_mutex()
            if mutex is not None:
                break
    if mutex is None:
        log("已有实例在运行，本次启动退出")
        ctypes.windll.user32.MessageBoxW(
            None, t("already_running"), t("app_name"), 0x40)
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
    except Exception:
        log("运行异常:\n" + traceback.format_exc())
    log("=== 退出 ===")
    try:
        (BASE / ".pid").unlink(missing_ok=True)
    except Exception:
        pass
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    os._exit(0)      # torch/onnx 的解释器清理要 10 秒级；强制秒退，互斥锁立即释放，马上重启不被挡


if __name__ == "__main__":
    main()
