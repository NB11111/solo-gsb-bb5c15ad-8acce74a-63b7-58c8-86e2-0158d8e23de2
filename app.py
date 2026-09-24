"""编织说明逐行针数校验 —— Flask 后端。

POST /api/validate
  请求: {"cast_on": 12, "pattern": "(k2tog yo)*6\np*12\n..."}
  响应: {
    "ok": true/false,
    "rows": [{"line", "instruction", "in", "consume", "produce", "out"}, ...],
    "error": null | {"line", "type": "parse"|"count"|"cast_on", "message",
                     "available"?, "consume"?, "diff"?},
    "final": 全部通过时的最终针数
  }

逐行推算规则：上一行的产出即下一行的可用针数；某行消耗与可用针数
不一致（不足或超出）或指令非法时，记录该行号与差额并停止，错误行
及其后的行不再继续推算。
"""

import os

from flask import Flask, jsonify, render_template, request

from stitch_parser import ParseError, parse_row

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
            }
            break
        if consume != available:
            diff = consume - available
            if diff > 0:
                message = "需要消耗 {} 针，但仅有 {} 针可用，缺少 {} 针".format(
                    consume, available, diff)
            else:
                message = "只消耗了 {} 针，可用的 {} 针还剩 {} 针未使用".format(
                    consume, available, -diff)
            error = {
                "line": lineno,
                "type": "count",
                "instruction": text,
                "available": available,
                "consume": consume,
                "diff": diff,
                "message": message,
            }
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
