# -*- coding: utf-8 -*-
"""表格截图 → 数值数据点：VL 识别 + fcel 格式解析。"""
from __future__ import annotations

import re

import vl_client

_TABLE_PROMPT = "Table Recognition:"

# 全角数字与常见全角符号 → 半角
_FULLWIDTH_TRANS = str.maketrans(
    "０１２３４５６７８９．－＋",
    "0123456789.-+",
)

_NUM_RE = re.compile(
    r"^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$"
)


def _norm_cell(s: str) -> str:
    return (s or "").strip().translate(_FULLWIDTH_TRANS)


def _is_numeric_cell(s: str) -> bool:
    t = _norm_cell(s)
    if not t:
        return False
    return bool(_NUM_RE.match(t))


def _cell_to_float(s: str) -> float:
    return float(_norm_cell(s))


_TAG = re.compile(r"<[^>]*>")


def parse_points(text: str) -> list[tuple[float, float]]:
    """解析 VL 表格输出（<fcel> 分格 / <nl> 分行），返回 (x,y) 列表。"""
    rows = [r for r in re.split(r"<\s*nl\s*>", text or "", flags=re.IGNORECASE) if r.strip()]
    numrows: list[list[float]] = []
    for r in rows:
        cells = [
            _TAG.sub("", c).strip()
            for c in re.split(r"<fcel>", r, flags=re.IGNORECASE)
            if c.strip()
        ]
        numrows.append([_cell_to_float(c) for c in cells if _is_numeric_cell(c)])
    multi = [nr for nr in numrows if len(nr) >= 3]
    twoc = [nr for nr in numrows if len(nr) == 2]
    # 横排：恰好两行多数字、且没有「每行 2 数字」的竖排行
    if len(multi) == 2 and not twoc:
        a, b = multi
        n = min(len(a), len(b))
        return list(zip(a[:n], b[:n]))
    pairs = [(nr[0], nr[1]) for nr in numrows if len(nr) >= 2]
    return pairs if len(pairs) >= 2 else []


def recognize_table(img, servers=None, timeout: float = 120.0) -> str:
    """识别表格图，返回 VL 原始文本。"""
    return vl_client.recognize(
        img, servers=servers, timeout=timeout, prompt=_TABLE_PROMPT
    )


def table_from_image(img, servers=None) -> tuple[list[tuple], str]:
    """识别并解析，返回 (points, raw_text)。"""
    raw = recognize_table(img, servers=servers)
    return parse_points(raw), raw


def points_to_text(points: list[tuple]) -> str:
    """数据点 → 每行 \"x y\" 文本。"""
    lines = []
    for x, y in points:
        lines.append(f"{x:g} {y:g}")
    return "\n".join(lines)


def text_to_points(text: str) -> list[tuple[float, float]]:
    """编辑框文本 → 数据点；非法行忽略。"""
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = re.split(r"[\s,\t]+", line)
        parts = [p for p in parts if p]
        if len(parts) < 2:
            continue
        try:
            out.append((float(parts[0]), float(parts[1])))
        except ValueError:
            continue
    return out
