# 编织说明逐行针数校验

输入起针数与每行编织指令，逐行推算消耗/产出针数：上一行的产出即下一行的可用针数，
针数不足或超出时标出行号与差额，错误行及之后的行不再参与推算。支持单尺码与多尺码两种
模式；多尺码模式下多个尺码共用同一份逐行指令、并排展示各自的有效行、首个错误和最终针数。

## 单条启动命令

```bash
docker compose up --build
```

启动后浏览器访问 <http://localhost:8000> 即可使用。

必要配置：无；服务默认监听容器内 `8000` 端口，compose 已映射到宿主机 `8000`。
如需更换宿主机访问端口，把 `docker-compose.yml` 中 `"8000:8000"` 左侧改掉即可。

## 指令语法

| 记号 | 含义 | 消耗 | 产出 |
| ---- | ---- | ---- | ---- |
| `k` | 下针 | 1 | 1 |
| `p` | 上针 | 1 | 1 |
| `yo` | 挂线 | 0 | 1 |
| `k2tog` | 两针并一针 | 2 | 1 |
| `(序列)*n` | 括号序列重复 n 次，可嵌套 | 累加 ×n | 累加 ×n |
| `(序列)*{n1\|n2\|…}` | 多尺码倍数：竖线分隔的正整数按尺码顺序分别取值 | 各尺码分别 ×n | 各尺码分别 ×n |

- 记号大小写不敏感，可用空格或逗号分隔，单个记号后也可直接跟 `*n`（如 `k*6`）。
- 普通 `*n` 对所有尺码生效；多尺码倍数 `*{6|8|10}` 中的项数必须与尺码数一致，
  顺序与页面上尺码的输入顺序一一对应。两种重复可以任意嵌套，例如
  `((k yo)*2 k2tog)*{2|3|4}`、`((k)*{1|2} yo)*3`。`{}` 内允许空格，如 `*{ 2 | 3 }`。
- 倍数 `n` 必须为正整数；`*0`、负数、缺失倍数、`*{|2}` 空项、项数与尺码数不符都会被
  拒绝，并在响应中给出原文行号 `line` 与 1 起始的字符位置 `column`。
- `*{...}` 只能用于多尺码校验；单尺码模式（`/api/validate`）遇到它会报解析错误，
  请改用普通 `*n`。
- 非法记号（如 `ssk`、`k3`）、括号不匹配、空括号都会被拒绝并指出位置。
- 解析只做算术累计，不展开重复项，`(k)*1000000000` 也能瞬间完成。

单尺码示例（起针 12）：

```text
(k2tog yo)*6
p*12
(k2tog)*6
(yo k2tog)*3
k*6
```

多尺码示例（S/M/L 起针 6/8/10）：

```text
(k2tog yo)*{3|4|5}
p*{6|8|10}
(k2tog)*{3|4|5}
```

多尺码推算规则：各尺码独立沿用上一行的产出作为下一行的可用针数；某个尺码出现针数差额
或解析错误后仅停止该尺码，其他尺码继续推算。响应中每个尺码分别返回有效行 `rows`、
首个错误 `error` 与最终针数 `final`（出错尺码没有 `final`）。

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

### `POST /api/validate`（单尺码）

请求体 JSON：

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

出错时 `error` 形如 `{"line": 2, "type": "count", "diff": 1, "column": 5, "message": "...缺少 1 针"}`
（`type` 为 `parse` / `count` / `cast_on`；解析错误带 `column`，针数错误带
`available` / `consume` / `diff`），`rows` 只包含错误行之前的有效行。

### `POST /api/validate-sizes`（多尺码，与单尺码接口共存）

请求体 JSON：`sizes` 按页面顺序给出尺码名与各自起针数，`pattern` 为共用的逐行指令：

```json
{
  "sizes": [
    {"name": "S", "cast_on": 6},
    {"name": "M", "cast_on": 8},
    {"name": "L", "cast_on": 10}
  ],
  "pattern": "(k2tog yo)*{3|4|5}\np*{6|8|10}\n(k2tog)*{3|4|5}"
}
```

响应：每个尺码独立给出 `rows` / `error` / `final`；某尺码出错只停止该尺码，
不影响其他尺码：

```json
{
  "ok": false,
  "error": null,
  "sizes": [
    {"name": "S", "cast_on": 6, "ok": false,
     "rows": [{"line": 1, "instruction": "(k2tog yo)*{3|4|5}", "in": 6, "consume": 6, "produce": 6, "out": 6}],
     "error": {"line": 2, "type": "count", "available": 6, "consume": 8, "diff": 2,
               "message": "需要消耗 8 针，但仅有 6 针可用，缺少 2 针"}},
    {"name": "M", "cast_on": 8, "ok": true, "rows": ["..."], "error": null, "final": 4},
    {"name": "L", "cast_on": 10, "ok": true, "rows": ["..."], "error": null, "final": 5}
  ]
}
```

- 顶层 `ok` 表示是否所有尺码都通过；解析错误对所有尚未停止的尺码同时生效，
  同样带 `line` 与 `column`。
- 请求本身不合法时（`sizes` 不是非空数组、尺码名为空/重复、起针数不是正整数）：

```json
{"ok": false, "sizes": [], "error": {"type": "request", "message": "至少需要一个尺码"}}
```

## 运行测试

```bash
python -m unittest discover -v
```

## 项目结构

```text
app.py               Flask 应用与单/多尺码逐行推算逻辑
stitch_parser.py     指令词法/语法解析（算术累计，不展开重复项；支持 *{n1|n2|…}）
templates/index.html 页面（单尺码/多尺码两个页签）
static/app.js        原生 JavaScript 前端（多尺码结果并排卡片）
static/style.css     样式
test_stitch_parser.py 解析器单元测试
test_app.py          两个接口的集成测试
Dockerfile / docker-compose.yml / requirements.txt
```
