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
- Evaluates handwritten evaluation brackets with limits: `[½x²−2x]_{2}^{5}` is computed as F(5)−F(2) (the usual shorthand when finishing a definite integral / antiderivative evaluation)
- **Limits-mode checkbox** in the popup: when OCR reads corner limits as a stacked fraction (`]\frac{5}{2}`) or a trailing power (`]0^{2}`), tick it to evaluate them as integration limits (top digit = upper limit, bottom digit = lower limit); untick to keep them as ordinary multiplication
- Popup extras: solve / derivative / integral / simplify / factor / expand / numeric value
- **Adjustable hotkeys** — record new ones right in the popup; takes effect immediately, no restart
- **UI language: 中文 / English** — one click in the popup switches the whole interface
- **Fix and recalc** — if a character is misread, hit **Edit** in the popup (or tray → *Enter formula manually…*) to correct the formula and recompute on the spot
- Three OCR engines with automatic fallback: `pix2text` (default, strong on handwriting), `pix2tex`, and an optional local **PaddleOCR-VL** server (strongest; ~0.3 s/formula on a GPU). Switch engines from the tray menu
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
2. **Recognize** — the selected region is recognized to LaTeX. With the
   default `pix2text` engine it is first preprocessed (auto-invert for dark
   canvases, upscale, contrast) and runs on CPU in roughly 0.2–0.5 s per
   formula. The optional `paddleocr-vl` engine sends the selection as-is to a
   local llama.cpp server (~0.3 s on GPU, ~2 s on CPU). `pix2tex` remains a
   fallback. Engines are tried in order; a failure moves on to the next one.
   Common OCR quirks are cleaned
   up before parsing: multi-line formulas (an OCR-produced `matrix` block is
   flattened to one line), a missing closing parenthesis, `0 , 75` for
   `0.75`, dotted subscripts (`0_{.}75`), stray braces left by flattened
   formulas, stray spaces inside numbers, and so on.
3. **Compute** — the LaTeX is parsed with `latex2sympy2` + SymPy: equations
   are solved, expressions are evaluated or simplified automatically.
4. **Show** — a popup presents the recognized LaTeX, the result, and one-click
   operations: solve, derivative, integral, simplify, factor, expand, numeric
   value. The top-right corner holds **Hotkeys** and **language**. A
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

**Fixing a misread** — recognition occasionally slips on tiny superscripts.
Click **Edit** in the popup (or, with no popup open, tray → *Enter formula
manually…*), correct the text (plain input like `2x+7=15` is fine), and click
**Recalculate** — the result updates immediately.

**Changing hotkeys** — in the popup, click **Hotkeys** (top-right), click
*Change* on a row, press the new combination, then *Save*. It takes effect
immediately and is written to `config.json`; *Reset defaults* restores the
original three. Modifier-only combos such as a bare `Ctrl+Alt+Shift` can be
recorded too: they fire on release after a 350 ms grace window, so
`Ctrl+Alt+Shift+C` / `+Q` keep working.

**Changing language** — in the popup, click **language** (top-right) to switch
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
| `ocr_engine` | `pix2text` | `pix2text`, `pix2tex`, or `paddleocr-vl` (needs a local llama.cpp server) |
| `vl_server_urls` | `["http://127.0.0.1:8111", "http://127.0.0.1:8112"]` | PaddleOCR-VL server addresses to try, in order |
| `vl_autostart` | `true` | launch the local PaddleOCR-VL server in the background on helper start (when the engine is `paddleocr-vl` and no server is up) |
| `vl_stop_on_exit` | `true` | on quit, stop the server — only if the helper started it (a manually started server is left alone) |
| `snip_method` | `builtin` | `builtin` = in-memory overlay; `ms-screenclip` = system screenshot tool (auto-saves files) |
| `snip_timeout_s` | `90` | Overlay auto-cancel timeout, seconds |
| `auto_copy` | `true` | Copy the main result to the clipboard automatically |

## Optional: PaddleOCR-VL engine

For the hardest handwriting, a local PaddleOCR-VL llama.cpp server can serve
as the recognition engine:

1. Start `llama-server` with the PaddleOCR-VL GGUF + `mmproj` (a GPU build is
   fastest; a CPU build runs ~2 s/formula on a laptop).
2. Tray icon → *OCR engine* → *PaddleOCR-VL*. A toast reports whether the
   server is reachable.
3. Recognition then posts the selection to `http://127.0.0.1:8111` (or
   `:8112`); if no server is up, it falls back to `pix2text` automatically.

The request format (image first, `OCR:` prompt, `temperature 0`) follows the
official PaddleOCR pipeline client and is implemented in `vl_client.py` with
no extra dependencies.

## Files

- `app.py` — tray app: hotkeys, popup UI with hotkey/language settings, built-in snip overlay, single-instance guard
- `pipeline.py` — preprocessing, OCR (pix2text / pix2tex / paddleocr-vl), parsing, computation, rendering
- `vl_client.py` — direct client for the optional PaddleOCR-VL llama.cpp server (stdlib only)
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
- **A character was misread (tiny superscripts are the usual suspects)** —
  click **Edit** in the popup (or tray → *Enter formula manually…*) and
  recalculate.
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
