# Rnote Formula Helper

A small Windows utility that turns a **handwritten formula on screen** into a
**computed result** — a local, app-agnostic take on Apple Freeform's
"Math Results". Built for use alongside [Rnote](https://github.com/flxzt/rnote),
but it works over any app.

Press a hotkey, drag-select the formula you wrote, and a popup shows the
recognized LaTeX together with the computed result.

```
Ctrl+Alt+M  ->  dim overlay  ->  drag-select  ->  result popup
```

## How it works

1. **Capture** — a global hotkey opens a built-in selection overlay. The image
   lives in memory only: nothing is written to disk, no screenshot tool is
   invoked. `Esc` or right-click cancels the selection.
2. **Recognize** — the selection is preprocessed (auto-invert for dark
   canvases, upscale, contrast) and recognized to LaTeX with `pix2text`
   (MFR model, good with handwriting). CPU-only, roughly 0.2-0.5 s per
   formula. `pix2tex` is available as a fallback engine and is used
   automatically if the primary engine fails.
3. **Compute** — the LaTeX is parsed with `latex2sympy2` + SymPy: equations
   are solved, expressions are evaluated or simplified automatically.
4. **Popup** — shows the recognized LaTeX, the result, and one-click extra
   operations: solve, derivative, integral, simplify, factor, expand, numeric
   value. A WolframAlpha link is provided when the parser cannot handle the
   input.

## Hotkeys

| Hotkey | Action |
| --- | --- |
| `Ctrl+Alt+M` | Select a region on screen and recognize it |
| `Ctrl+Alt+Shift+M` | Recognize the image in the clipboard |
| `Ctrl+Alt+Shift+Q` | Quit |

Hotkeys, the OCR engine and the snip method can be changed in `config.json`
(`hotkey`, `clipboard_hotkey`, `quit_hotkey`, `ocr_engine`, `snip_method`).

## Files

- `app.py` — tray app: hotkeys, popup UI, built-in snip overlay, single-instance guard
- `pipeline.py` — preprocessing, OCR (pix2text / pix2tex), parsing, computation, rendering
- `selftest.py` — headless self-test: `python selftest.py` (parse, ocr, or full)
- `config.json` — hotkeys, OCR engine, snip method
- `selftest_imgs/` — sample images used by the self-test
- `README.txt` — quick-start notes (Chinese)

## Setup (development)

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python selftest.py parse
```

Run the app without a console window: `启动（无窗口）.vbs` (or
`pythonw.exe app.py`). For a debug console use `启动（调试模式）.cmd`.

## Notes

- OCR models are downloaded on first use; the first start is slow (~20-25 s
  warm-up), later recognitions are fast.
- Recognition is CPU-only. No GPU required.
- The captured image never touches the disk; the clipboard only ever carries
  the resulting text.

## Status

Work in progress — expect rough edges (private repository).
