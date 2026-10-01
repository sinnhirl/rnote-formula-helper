# Rnote Formula Helper

Handwrite a math formula **anywhere on your screen** — press a hotkey, drag a box
around it, and a popup shows the **recognized LaTeX** plus the **computed result**.
A local, app-agnostic take on Apple Freeform's "Math results", built for use
alongside [Rnote](https://github.com/flxzt/rnote) but working over any app.

`Ctrl+Alt+Shift+M` → drag-select → LaTeX + result (auto-copied to the clipboard)

- 100% local — recognition and computation run on your CPU; nothing is uploaded
- Nothing is written to disk — the captured region lives in memory and is released immediately
- No GPU required — roughly 0.2–0.5 s per formula once warmed up

## Features

- One-hotkey workflow: box-select the formula, get the answer
- Works over any application (Rnote, OneNote, a PDF, a recorded lecture, ...)
- Solves equations and evaluates expressions
- Popup extras: solve / derivative / integral / simplify / factor / expand / numeric value
- **Adjustable hotkeys** — record new ones right in the popup; takes effect immediately, no restart
- **UI language: 中文 / English** — one click in the popup switches the whole interface
- Two OCR engines with automatic fallback: `pix2text` (default, strong on handwriting) and `pix2tex`
- Built-in in-memory region select — no screenshot files, no clipboard-history pollution

## Examples

| You write on screen | Result |
| --- | --- |
| `2x+7=15` | `x = 4` |
| `4+4·(−0.5)²` | `5` |
| `x^2-5x+6=0` | `x = 2` or `x = 3` |
| `0.5·(4×6+0.75²+0.25²+…)` | `239/16` |

## How it works

1. **Capture** — a global hotkey (default `Ctrl+Alt+Shift+M`) opens a built-in
   selection overlay. The image lives in memory only: nothing is written to
   disk and no system screenshot tool is invoked. `Esc` or right-click cancels
   the selection.
2. **Recognize** — the selected region is preprocessed (auto-invert for dark
   canvases, upscale, contrast) and recognized to LaTeX with `pix2text`
   (MFR model, good with handwriting). CPU-only, roughly 0.2–0.5 s per
   formula. `pix2tex` is available as a fallback engine and is used
   automatically if the primary engine fails. Common OCR quirks are cleaned
   up before parsing: multi-line formulas (an OCR-produced `matrix` block is
   flattened to one line), a missing closing parenthesis, `0 , 75` for
   `0.75`, stray spaces inside numbers, and so on.
3. **Compute** — the LaTeX is parsed with `latex2sympy2` + SymPy: equations
   are solved, expressions are evaluated or simplified automatically.
4. **Show** — a popup presents the recognized LaTeX, the result, and one-click
   operations: solve, derivative, integral, simplify, factor, expand, numeric
   value. The top-right corner holds **Hotkeys** and **Language**. A
   WolframAlpha link is offered when the parser cannot handle the input.

## Requirements

- Windows 10 / 11
- Python 3.12 (tested; 3.10+ should work)
- No GPU — CPU inference only
- About 2 GB of disk for the environment (CPU PyTorch) plus the OCR models,
  which are downloaded and cached automatically on first use

## Installation

```bat
git clone https://github.com/sinnhirl/rnote-formula-helper.git
cd rnote-formula-helper
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python selftest.py parse
```

## Usage

| Hotkey (default) | Action |
| --- | --- |
| `Ctrl+Alt+Shift+M` | Box-select a formula on screen and recognize it |
| `Ctrl+Alt+Shift+C` | Recognize the image currently in the clipboard |
| `Ctrl+Alt+Shift+Q` | Quit |

The defaults sit on `Ctrl+Alt+Shift` on purpose: they are verified free on a
stock Windows 11 + NVIDIA setup. (`Ctrl+Alt+M`, for example, is commonly
grabbed by NVIDIA GeForce Experience as its microphone toggle.)

1. Write a formula in Rnote (or any app): `2x+7=15`, `x^2-5x+6=0`, ...
2. Press `Ctrl+Alt+Shift+M` — the screen dims; drag a box around the formula and
   release. `Esc` or right-click cancels.
3. The popup shows the recognized LaTeX and the computed result. The main
   result is already on your clipboard — paste it anywhere.
4. Need more? Use the popup buttons (solve, derivative, integral, simplify,
   factor, expand, numeric), or the WolframAlpha link as an escape hatch.

**Changing hotkeys** — in the popup, click **Hotkeys** (top-right), click
*Change* on a row, press the new combination, then *Save*. It takes effect
immediately and is written to `config.json`; *Reset defaults* restores the
original three.

**Changing language** — in the popup, click **Language** (top-right) to switch
the whole interface — popup, settings dialog, tray menu, notifications —
between 中文 and English.

Launching: double-click `start_silent.vbs` (no console window) or
`start_debug.cmd` (keeps a console open for logs). Quit via the tray icon,
`quit.cmd`, or the quit hotkey.

## Configuration

Edit `config.json` — or, for hotkeys and language, use the popup (applies
immediately). Other keys take effect after a restart.

| Key | Default | Description |
| --- | --- | --- |
| `hotkey` | `ctrl+alt+shift+m` | Main region-select hotkey |
| `clipboard_hotkey` | `ctrl+alt+shift+c` | Recognize the clipboard image |
| `quit_hotkey` | `ctrl+alt+shift+q` | Quit |
| `language` | `zh` | UI language: `zh` or `en` |
| `ocr_engine` | `pix2text` | `pix2text` (handwriting) or `pix2tex` |
| `snip_method` | `builtin` | `builtin` = in-memory overlay; `ms-screenclip` = system screenshot tool (auto-saves files) |
| `snip_timeout_s` | `90` | Overlay auto-cancel timeout, seconds |
| `auto_copy` | `true` | Copy the main result to the clipboard automatically |

## Files

- `app.py` — tray app: hotkeys, popup UI with hotkey/language settings, built-in snip overlay, single-instance guard
- `pipeline.py` — preprocessing, OCR (pix2text / pix2tex), parsing, computation, rendering
- `selftest.py` — headless self-test: `python selftest.py parse|ocr|all`
- `config.json` — hotkeys, language, OCR engine, snip method
- `selftest_imgs/` — sample images used by the self-test
- `start_silent.vbs` / `start_debug.cmd` / `quit.cmd` — launchers
- `make_icon_and_shortcut.ps1` — regenerates `icon.ico` and the Desktop shortcut
- `README.zh-CN.md` — 中文使用说明 (Chinese guide)

## Privacy

- Recognition and computation are fully local; no network access is required
  (the only outbound link is the WolframAlpha button, opened by you on demand).
- The captured image never touches the disk and is released right after OCR.
- The clipboard only ever receives the resulting text.

## Troubleshooting

- **First recognition is slow (~20–25 s)** — the OCR models warm up on the
  first use; later recognitions take well under a second.
- **Hotkey does nothing** — make sure the helper is running (fx icon in the
  system tray; it may be hiding in the overflow area). Logs: `rnote-ocr.log`.
- **Selecting a blank/white region does nothing** — intentional: blank regions
  are skipped instead of being misrecognized.
- **Hotkey conflicts** — change the hotkey from the popup (takes effect at
  once) or in `config.json`. Known grabby apps include NVIDIA GeForce
  Experience (`Ctrl+Alt+M`).

## Status

Early but functional, used daily alongside Rnote. Bug reports and suggestions
are welcome — please open an issue.

## License

MIT © 2026 sinnhirl — see [LICENSE](LICENSE).

## Acknowledgments

[pix2text](https://github.com/breezedeus/pix2text) ·
[pix2tex](https://github.com/lukas-blecher/LaTeX-OCR) ·
[latex2sympy2](https://github.com/OrangeX4/latex2sympy2) ·
[SymPy](https://www.sympy.org/) ·
inspired by [Rnote](https://github.com/flxzt/rnote)
