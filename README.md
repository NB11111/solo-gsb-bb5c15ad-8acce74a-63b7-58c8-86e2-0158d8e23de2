# 编织说明逐行针数校验

输入起针数与每行编织指令，逐行推算消耗/产出针数：上一行的产出即下一行的可用针数，
针数不足或超出时标出行号与差额，错误行及之后的行不再参与推算。页面展示所有有效行
的进出针数与首个错误。

## 指令语法

| 记号 | 含义 | 消耗 | 产出 |
| ---- | ---- | ---- | ---- |
| `k` | 下针 | 1 | 1 |
| `p` | 上针 | 1 | 1 |
| `yo` | 挂线 | 0 | 1 |
| `k2tog` | 两针并一针 | 2 | 1 |
| `(序列)*n` | 括号序列重复 n 次，可嵌套 | 累加 ×n | 累加 ×n |

- 记号大小写不敏感，可用空格或逗号分隔，单个记号后也可直接跟 `*n`（如 `k*6`）。
- 倍数 `n` 必须为正整数；`*0`、负数、缺失倍数都会被拒绝。
- 非法记号（如 `ssk`、`k3`）、括号不匹配、空括号都会被拒绝并指出位置。
- 解析只做算术累计，不展开重复项，`(k)*1000000000` 也能瞬间完成。

示例（起针 12）：

```text
(k2tog yo)*6
p*12
(k2tog)*6
(yo k2tog)*3
k*6
```

## 启动方式

### Docker Compose（推荐，一键安装依赖并启动）

```bash
docker compose up --build
```

### 仅 Docker

```bash
docker build -t knit-check .
docker run --rm -p 8000:8000 knit-check
```

### 本地运行

```bash
pip install -r requirements.txt
python app.py            # 开发方式
# 或：gunicorn --bind 0.0.0.0:8000 app:app
```

## 访问地址与端口

- 访问地址：<http://localhost:8000>
- 默认端口：`8000`

### 配置项

| 配置 | 方式 | 默认 |
| ---- | ---- | ---- |
| 服务监听端口 | 环境变量 `PORT` | `8000` |
| 对外映射端口 | `docker-compose.yml` 中 `ports` 的左侧 | `8000` |

例如改用 9000 端口访问：把 `docker-compose.yml` 的端口映射改为 `"9000:8000"` 即可；
本地运行时则使用 `PORT=9000 python app.py`。

## API

`POST /api/validate`，请求体 JSON：

```json
{"cast_on": 12, "pattern": "(k2tog yo)*6\np*12"}
```

响应：

```json
{
  "ok": true,
  "rows": [
    {"line": 1, "instruction": "(k2tog yo)*6", "in": 12, "consume": 12, "produce": 12, "out": 12}
  ],
  "error": null,
  "final": 12
}
```

出错时 `error` 形如 `{"line": 2, "type": "count", "diff": 1, "message": "...缺少 1 针"}`
（`type` 为 `parse` / `count` / `cast_on`），`rows` 只包含错误行之前的有效行。

## 运行测试

```bash
python -m unittest discover -v
```

## 项目结构

```text
app.py               Flask 应用与逐行推算逻辑
stitch_parser.py     指令词法/语法解析（算术累计，不展开重复项）
templates/index.html 页面
static/app.js        原生 JavaScript 前端
static/style.css     样式
test_stitch_parser.py 解析器单元测试
test_app.py          接口集成测试
Dockerfile / docker-compose.yml / requirements.txt
```
