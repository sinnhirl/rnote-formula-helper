# -*- coding: utf-8 -*-
"""PaddleOCR-VL（llama.cpp 服务）直连客户端 —— 只用标准库。

请求方式对照 paddlex 官方客户端源码复刻（实测结果一致、0.2~2 秒/张）：
  一问一答：图在前、文本 "Formula Recognition:" 在后；temperature=0；max_tokens=8192。
服务端：llama-server（GPU: start_server.bat → 8111；CPU: start_server_cpu.bat → 8112）。
"""
from __future__ import annotations

import base64
import io
import json
import urllib.error
import urllib.request
from collections import Counter

DEFAULT_SERVERS = ["http://127.0.0.1:8111", "http://127.0.0.1:8112"]

# 2026-10-01 逐字对照实测：官方客户端在这类手写图上实际发的提示词是 "OCR:"（其布局器
# 把块判成文本块走了默认分支），读得又准又快；换成 "Formula Recognition:" 反而会复读/
# 串行（同图同参数 30 秒跑飞的实测）。所以这里就用 "OCR:"。
_PROMPT = "OCR:"
_MAX_TOKENS = 4096          # 与官方一致；配合复读检测 + 带惩罚重试兜底

_cache = {"api": None, "model": None, "model_api": None}


class ServerUnavailable(RuntimeError):
    """8111 / 8112 都探测不到在线的 llama-server。"""


def _norm_base(base: str) -> str:
    b = (base or "").strip().rstrip("/")
    return b[:-3].rstrip("/") if b.endswith("/v1") else b


def _get_json(url: str, timeout: float):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _post_json(url: str, payload: dict, timeout: float):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def find_server(servers=None, timeout: float = 1.5):
    """探测在线服务，返回 API 基地址（如 http://127.0.0.1:8111/v1）；都不在线返回 None。"""
    cands = [_norm_base(s) for s in (servers or DEFAULT_SERVERS) if s]
    if _cache["api"]:
        cands.sort(key=lambda c: c != _cache["api"])       # 上次成功的优先
    for base in cands:
        try:
            info = _get_json(base + "/health", timeout)
            if str(info.get("status", "ok")).lower() == "ok":
                _cache["api"] = base
                return base + "/v1"
        except Exception:
            continue
    _cache["api"] = None
    return None


def _model_name(api_base: str) -> str:
    if _cache["model"] and _cache["model_api"] == api_base:
        return _cache["model"]
    try:
        info = _get_json(api_base + "/models", 5)
        mid = str(info["data"][0]["id"])
    except Exception:
        mid = "model"
    _cache["model"], _cache["model_api"] = mid, api_base
    return mid


def _b64_png(img) -> str:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _looks_degenerate(text: str) -> bool:
    """复读机检测：同一 12 字符片段出现 ≥5 次即判为乱生成。"""
    t = (text or "").strip()
    if len(t) < 60:
        return False
    grams = Counter(t[i:i + 12] for i in range(len(t) - 12))
    return bool(grams) and grams.most_common(1)[0][1] >= 5


def _request(api_base: str, img, timeout: float, repeat_penalty=None) -> str:
    payload = {
        "model": _model_name(api_base),
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": "data:image/png;base64," + _b64_png(img)}},
                {"type": "text", "text": _PROMPT},
            ],
        }],
        "temperature": 0,
        "max_tokens": _MAX_TOKENS,
        "skip_special_tokens": True,        # 与官方客户端一致
    }
    if repeat_penalty is not None:
        payload["repeat_penalty"] = repeat_penalty
    out = _post_json(api_base + "/chat/completions", payload, timeout)
    return (out["choices"][0]["message"]["content"] or "").strip()


def recognize(img, servers=None, timeout: float = 120.0) -> str:
    """识别一张 PIL 图片 → LaTeX 文本。服务不在线时抛 ServerUnavailable。"""
    api_base = find_server(servers)
    if api_base is None:
        raise ServerUnavailable(
            "PaddleOCR-VL 服务不在线（8111/8112 无响应）：先运行 start_server.bat（GPU）"
            "或 start_server_cpu.bat（CPU）")
    try:
        txt = _request(api_base, img, timeout)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"PaddleOCR-VL 服务返回错误 HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        _cache["api"] = None
        raise ServerUnavailable(f"连接 PaddleOCR-VL 服务失败: {e}") from e
    if txt and not _looks_degenerate(txt):
        return txt
    # 复读/空输出：加 repetition penalty 重试一次
    try:
        txt2 = _request(api_base, img, timeout, repeat_penalty=1.10)
    except Exception as e:
        raise RuntimeError(f"识别输出异常（{'复读' if txt else '空'}），重试失败: {e}") from e
    if not txt2 or _looks_degenerate(txt2):
        raise RuntimeError("识别输出异常（复读/空），已放弃本次结果")
    return txt2
