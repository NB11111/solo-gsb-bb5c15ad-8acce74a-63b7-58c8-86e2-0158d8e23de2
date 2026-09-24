"""编织指令解析器：按括号与倍数计算每行的消耗/产出针数。

支持的记号（大小写不敏感，可用空格或逗号分隔）：
  k       下针：消耗 1 针，产出 1 针
  p       上针：消耗 1 针，产出 1 针
  yo      挂线：不消耗，产出 1 针
  k2tog   两针并一针：消耗 2 针，产出 1 针
  (序列)*n  括号序列重复 n 次，可嵌套；单个记号后也可跟 *n

解析只做算术累计，绝不展开重复项，因此 (k)*1000000000 也能瞬间算完。
"""

import re

# 记号 -> (消耗针数, 产出针数)
STITCH_COUNTS = {
    'k': (1, 1),
    'p': (1, 1),
    'yo': (0, 1),
    'k2tog': (2, 1),
}

# 注意 k2tog 必须排在 k 之前，保证最长匹配
TOKEN_RE = re.compile(r"""
    (?P<STITCH>k2tog|yo|k|p)
  | (?P<LPAREN>\()
  | (?P<RPAREN>\))
  | (?P<STAR>\*)
  | (?P<NUM>\d+)
  | (?P<SEP>[\s,]+)
""", re.IGNORECASE | re.VERBOSE)


class ParseError(ValueError):
    """指令解析错误，message 中已包含定位信息。"""


def _tokenize(text):
    tokens = []
    pos = 0
    while pos < len(text):
        m = TOKEN_RE.match(text, pos)
        if not m:
            raise ParseError(
                "无法识别的记号 {!r}（第 {} 个字符）".format(text[pos], pos + 1))
        if m.lastgroup != 'SEP':
            tokens.append((m.lastgroup, m.group(), m.start()))
        pos = m.end()
    return tokens


class _Parser(object):
    def __init__(self, tokens):
        self.tokens = tokens
        self.i = 0

    def peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def advance(self):
        tok = self.peek()
        self.i += 1
        return tok

    def parse_row(self):
        """row := sequence EOF"""
        counts = self.parse_sequence()
        tok = self.peek()
        if tok is not None:
            kind, val, pos = tok
            if kind == 'RPAREN':
                raise ParseError("多余的右括号 ')'（第 {} 个字符）".format(pos + 1))
            if kind == 'NUM':
                raise ParseError(
                    "意外的数字 {!r}（第 {} 个字符）：倍数需写成 (序列)*次数 的形式".format(val, pos + 1))
            if kind == 'STAR':
                raise ParseError(
                    "意外的 '*'（第 {} 个字符）：'*' 必须跟在记号或 ')' 之后".format(pos + 1))
        return counts

    def parse_sequence(self):
        """sequence := item+，消耗/产出逐项累加"""
        total_c = total_p = 0
        while True:
            tok = self.peek()
            if tok is None or tok[0] not in ('STITCH', 'LPAREN'):
                break
            c, p = self.parse_item()
            total_c += c
            total_p += p
        return (total_c, total_p)

    def parse_item(self):
        """item := (STITCH | '(' sequence ')') ('*' NUM)?"""
        kind, val, pos = self.advance()
        if kind == 'STITCH':
            c, p = STITCH_COUNTS[val.lower()]
        else:  # LPAREN
            c, p = self.parse_sequence()
            if (c, p) == (0, 0):
                raise ParseError("括号内不能为空（第 {} 个字符）".format(pos + 1))
            tok = self.peek()
            if tok is None:
                raise ParseError("缺少与 '(' 对应的 ')'（第 {} 个字符）".format(pos + 1))
            if tok[0] != 'RPAREN':
                raise ParseError(
                    "括号内出现意外的记号 {!r}（第 {} 个字符）".format(tok[1], tok[2] + 1))
            self.advance()
        tok = self.peek()
        if tok is not None and tok[0] == 'STAR':
            self.advance()
            ntok = self.peek()
            if ntok is None or ntok[0] != 'NUM':
                raise ParseError("'*' 后必须跟正整数倍数（第 {} 个字符）".format(tok[2] + 1))
            self.advance()
            n = int(ntok[1])
            if n <= 0:
                raise ParseError(
                    "倍数必须为正整数，收到 {}（第 {} 个字符）".format(n, ntok[2] + 1))
            c *= n
            p *= n
        return (c, p)


def parse_row(text):
    """解析一行指令，返回 (消耗针数, 产出针数)。非法输入抛出 ParseError。"""
    tokens = _tokenize(text)
    if not tokens:
        raise ParseError("该行没有有效指令")
    return _Parser(tokens).parse_row()
