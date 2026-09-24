"""编织说明逐行针数校验 —— Flask 后端。

POST /api/validate
  单尺码校验。
  请求: {"cast_on": 12, "pattern": "(k2tog yo)*6\np*12\n..."}
  响应: {
    "ok": true/false,
    "rows": [{"line", "instruction", "in", "consume", "produce", "out"}, ...],
    "error": null | {"line", "column"?, "type": "parse"|"count"|"cast_on",
                     "message", "available"?, "consume"?, "diff"?},
    "final": 全部通过时的最终针数
  }

POST /api/validate-sizes
  多尺码校验：同一份逐行指令按尺码分别推算，多尺码倍数写成
  *{n1|n2|...}（竖线分隔，按尺码顺序取值），普通 *n 对所有尺码生效。
  请求: {"sizes": [{"name": "S", "cast_on": 6}, ...], "pattern": "..."}
  响应: {
    "ok": 所有尺码是否全部通过,
    "sizes": [
      {"name", "cast_on", "ok", "rows": [...],
       "error": null | {"line", "column"?, "type", "message", ...},
       "final": 通过时的最终针数}
    ],
    "error": null | {"type": "request", "message"}   # 请求本身非法
  }

逐行推算规则：上一行的产出即下一行的可用针数；某行消耗与可用针数
不一致（不足或超出）或指令非法时，记录该行号（解析错误还带字符位置）
并停止该尺码的推算，其他尺码继续各自推算。
"""

import os

from flask import Flask, jsonify, render_template, request

from stitch_parser import ParseError, parse_row, parse_row_sizes

app = Flask(__name__)


def _parse_cast_on(raw):
    """校验起针数，返回 (数值, 错误消息)。只接受正整数。"""
    if isinstance(raw, bool):  # bool 是 int 的子类，需先排除
        return None, "起针数必须为正整数"
    if isinstance(raw, int):
        value = raw
    elif isinstance(raw, str):
        s = raw.strip()
        if not s.isdigit():
            return None, "起针数必须为正整数"
        value = int(s)
    else:
        return None, "起针数必须为正整数"
    if value <= 0:
        return None, "起针数必须为正整数（大于 0）"
    return value, None


def _count_error(lineno, text, available, consume):
    """构造针数差额错误。"""
    diff = consume - available
    if diff > 0:
        message = "需要消耗 {} 针，但仅有 {} 针可用，缺少 {} 针".format(
            consume, available, diff)
    else:
        message = "只消耗了 {} 针，可用的 {} 针还剩 {} 针未使用".format(
            consume, available, -diff)
    return {
        "line": lineno,
        "type": "count",
        "instruction": text,
        "available": available,
        "consume": consume,
        "diff": diff,
        "message": message,
    }


def _parse_sizes(raw):
    """校验多尺码入参，返回 [{name, cast_on}, ...] 或错误消息。"""
    if not isinstance(raw, list):
        return None, "sizes 必须是数组，每项包含 name 与 cast_on"
    if not raw:
        return None, "至少需要一个尺码"
    sizes = []
    names = set()
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            return None, "第 {} 个尺码必须是包含 name 与 cast_on 的对象".format(idx + 1)
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            return None, "第 {} 个尺码缺少名称".format(idx + 1)
        name = name.strip()
        if name in names:
            return None, "尺码名称不能重复：{!r}".format(name)
        cast_on, err = _parse_cast_on(item.get("cast_on"))
        if err:
            return None, "尺码 {!r} 的起针数无效：{}".format(name, err)
        names.add(name)
        sizes.append({"name": name, "cast_on": cast_on})
    return sizes, None


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/validate")
def validate():
    data = request.get_json(silent=True) or {}

    cast_on, err = _parse_cast_on(data.get("cast_on"))
    if err:
        return jsonify({
            "ok": False,
            "rows": [],
            "error": {"line": None, "type": "cast_on", "message": err},
        })

    pattern = data.get("pattern", "")
    if not isinstance(pattern, str):
        pattern = str(pattern)

    rows = []
    error = None
    available = cast_on
    for lineno, raw_line in enumerate(pattern.splitlines(), 1):
        text = raw_line.strip()
        if not text:  # 跳过空行，行号仍按原始文本计算
            continue
        try:
            consume, produce = parse_row(text)
        except ParseError as exc:
            error = {
                "line": lineno,
                "type": "parse",
                "instruction": text,
                "message": str(exc),
                "column": exc.pos,
            }
            break
        if consume != available:
            error = _count_error(lineno, text, available, consume)
            break
        rows.append({
            "line": lineno,
            "instruction": text,
            "in": available,
            "consume": consume,
            "produce": produce,
            "out": produce,
        })
        available = produce

    result = {"ok": error is None, "rows": rows, "error": error}
    if error is None:
        result["final"] = available
    return jsonify(result)


@app.post("/api/validate-sizes")
def validate_sizes():
    data = request.get_json(silent=True) or {}

    sizes, err = _parse_sizes(data.get("sizes"))
    if err:
        return jsonify({"ok": False, "sizes": [], "error": {
            "type": "request", "message": err}})

    pattern = data.get("pattern", "")
    if not isinstance(pattern, str):
        pattern = str(pattern)

    lines = [(lineno, raw.strip())
             for lineno, raw in enumerate(pattern.splitlines(), 1)
             if raw.strip()]

    # 每行只解析一次，各尺码共享解析结果；解析错误按尺码在“仍活跃”时记入
    # parsed[lineno] = {"text", "pairs": [...]} 或 {"text", "error": {...}}
    parsed = []
    for lineno, text in lines:
        entry = {"line": lineno, "text": text}
        try:
            entry["pairs"] = parse_row_sizes(text, len(sizes))
        except ParseError as exc:
            entry["error"] = {
                "line": lineno,
                "type": "parse",
                "instruction": text,
                "message": str(exc),
                "column": exc.pos,
            }
        parsed.append(entry)

    results = []
    for idx, size in enumerate(sizes):
        rows = []
        error = None
        available = size["cast_on"]
        for entry in parsed:
            if "error" in entry:  # 同一份指令，各尺码看到同一个解析错误
                error = dict(entry["error"])
                break
            consume, produce = entry["pairs"][idx]
            if consume != available:
                error = _count_error(entry["line"], entry["text"], available, consume)
                break
            rows.append({
                "line": entry["line"],
                "instruction": entry["text"],
                "in": available,
                "consume": consume,
                "produce": produce,
                "out": produce,
            })
            available = produce
        result = {
            "name": size["name"],
            "cast_on": size["cast_on"],
            "ok": error is None,
            "rows": rows,
            "error": error,
        }
        if error is None:
            result["final"] = available
        results.append(result)

    return jsonify({
        "ok": all(r["ok"] for r in results),
        "sizes": results,
        "error": None,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
