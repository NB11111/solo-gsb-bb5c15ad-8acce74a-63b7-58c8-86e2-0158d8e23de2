"""编织指令解析器：按括号与倍数计算每行的消耗/产出针数。

支持的记号（大小写不敏感，可用空格或逗号分隔）：
  k       下针：消耗 1 针，产出 1 针
  p       上针：消耗 1 针，产出 1 针
  yo      挂线：不消耗，产出 1 针
  k2tog   两针并一针：消耗 2 针，产出 1 针
  (序列)*n  括号序列重复 n 次，可嵌套；单个记号后也可跟 *n
  (序列)*{n1|n2|...}  多尺码倍数：竖线分隔的正整数按尺码顺序分别取值，
            仅可用于 parse_row_sizes；普通 *n 对所有尺码生效，两种重复
            可以任意嵌套。

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
  | (?P<LBRACE>\{)
  | (?P<RBRACE>\})
  | (?P<PIPE>\|)
  | (?P<STAR>\*)
  | (?P<NUM>\d+)
  | (?P<SEP>[\s,]+)
""", re.IGNORECASE | re.VERBOSE)


class ParseError(ValueError):
    """指令解析错误。message 中包含定位信息，pos 为从 1 开始的字符位置。"""

    def __init__(self, message, pos=None):
        super().__init__(message)
        # 调用方统一传入 0 起始的下标，这里转成人类习惯的“第 N 个字符”
        self.pos = None if pos is None else pos + 1


def _tokenize(text):
    tokens = []
    pos = 0
    while pos < len(text):
        m = TOKEN_RE.match(text, pos)
        if not m:
            raise ParseError(
                "无法识别的记号 {!r}（第 {} 个字符）".format(text[pos], pos + 1),
                pos)
        if m.lastgroup != 'SEP':
            tokens.append((m.lastgroup, m.group(), m.start()))
        pos = m.end()
    return tokens


class _Parser(object):
    """size_count 为 None 时解析单尺码（标量）；否则解析多尺码（向量）。"""

    def __init__(self, tokens, size_count=None):
        self.tokens = tokens
        self.i = 0
        self.n = size_count

    def peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def advance(self):
        tok = self.peek()
        self.i += 1
        return tok

    @staticmethod
    def _is_zero(c, p):
        if isinstance(c, list):
            return not any(c) and not any(p)
        return c == 0 and p == 0

    def parse_row(self):
        """row := sequence EOF"""
        c, p = self.parse_sequence()
        tok = self.peek()
        if tok is not None:
            kind, val, pos = tok
            if kind == 'RPAREN':
                raise ParseError("多余的右括号 ')'（第 {} 个字符）".format(pos + 1), pos)
            if kind == 'NUM':
                raise ParseError(
                    "意外的数字 {!r}（第 {} 个字符）：倍数需写成 (序列)*次数 的形式".format(val, pos + 1),
                    pos)
            if kind == 'STAR':
                raise ParseError(
                    "意外的 '*'（第 {} 个字符）：'*' 必须跟在记号或 ')' 之后".format(pos + 1),
                    pos)
            if kind == 'LBRACE':
                raise ParseError(
                    "意外的 '{{'（第 {} 个字符）：多尺码倍数需写成 '*{{n1|n2|...}}' 且跟在记号或 ')' 之后"
                    .format(pos + 1), pos)
            if kind == 'RBRACE':
                raise ParseError("多余的 '}}'（第 {} 个字符）".format(pos + 1), pos)
            if kind == 'PIPE':
                raise ParseError(
                    "意外的 '|'（第 {} 个字符）：'|' 只能出现在 '*{{...}}' 多尺码倍数中".format(pos + 1),
                    pos)
        if self.n is None:
            return (c, p)
        return list(zip(c, p))

    def parse_sequence(self):
        """sequence := item+，消耗/产出逐项累加（多尺码下逐尺码累加）"""
        if self.n is None:
            total_c = total_p = 0
        else:
            total_c = [0] * self.n
            total_p = [0] * self.n
        while True:
            tok = self.peek()
            if tok is None or tok[0] not in ('STITCH', 'LPAREN'):
                break
            c, p = self.parse_item()
            if self.n is None:
                total_c += c
                total_p += p
            else:
                total_c = [a + b for a, b in zip(total_c, c)]
                total_p = [a + b for a, b in zip(total_p, p)]
        return (total_c, total_p)

    def parse_item(self):
        """item := (STITCH | '(' sequence ')') repeat?"""
        kind, val, pos = self.advance()
        if kind == 'STITCH':
            sc, sp = STITCH_COUNTS[val.lower()]
            if self.n is None:
                c, p = sc, sp
            else:
                c, p = [sc] * self.n, [sp] * self.n
        else:  # LPAREN
            c, p = self.parse_sequence()
            if self._is_zero(c, p):
                raise ParseError("括号内不能为空（第 {} 个字符）".format(pos + 1), pos)
            tok = self.peek()
            if tok is None:
                raise ParseError(
                    "缺少与 '(' 对应的 ')'（第 {} 个字符）".format(pos + 1), pos)
            if tok[0] != 'RPAREN':
                raise ParseError(
                    "括号内出现意外的记号 {!r}（第 {} 个字符）".format(tok[1], tok[2] + 1),
                    tok[2])
            self.advance()

        mult = self.parse_repeat()
        if mult is not None:
            if self.n is None:
                c *= mult
                p *= mult
            elif isinstance(mult, list):
                c = [a * b for a, b in zip(c, mult)]
                p = [a * b for a, b in zip(p, mult)]
            else:
                c = [a * mult for a in c]
                p = [a * mult for a in p]
        return (c, p)

    def parse_repeat(self):
        """repeat := '*' (NUM | '{' NUM ('|' NUM)* '}')；无 '*' 时返回 None。"""
        tok = self.peek()
        if tok is None or tok[0] != 'STAR':
            return None
        star_pos = tok[2]
        self.advance()
        tok = self.peek()
        if tok is None:
            hint = "或 '*{n1|n2|...}' 形式的多尺码倍数" if self.n is not None else ""
            raise ParseError(
                "'*' 后必须跟正整数倍数{}（第 {} 个字符）".format(hint, star_pos + 1),
                star_pos)
        if tok[0] == 'LBRACE':
            return self.parse_brace_repeat(tok[2])
        if tok[0] != 'NUM':
            raise ParseError(
                "'*' 后必须跟正整数倍数（第 {} 个字符）".format(star_pos + 1), star_pos)
        self.advance()
        n = int(tok[1])
        if n <= 0:
            raise ParseError(
                "倍数必须为正整数，收到 {}（第 {} 个字符）".format(n, tok[2] + 1),
                tok[2])
        return n

    def parse_brace_repeat(self, brace_pos):
        """解析 '{' NUM ('|' NUM)* '}'，返回各尺码倍数组成的列表。"""
        self.advance()  # 消费 '{'
        if self.n is None:
            raise ParseError(
                "'*{{' 是多尺码倍数语法，单尺码校验请改用 '*n'（第 {} 个字符）"
                .format(brace_pos + 1), brace_pos)

        nums = []
        expect_num = True
        while True:
            tok = self.peek()
            if tok is None:
                if expect_num:
                    raise ParseError(
                        "缺少第 {} 个尺码倍数以及对应的 '}}'（第 {} 个字符）"
                        .format(len(nums) + 1, brace_pos + 1), brace_pos)
                raise ParseError(
                    "尺码倍数缺少对应的 '}}'（第 {} 个字符）".format(brace_pos + 1),
                    brace_pos)
            kind, val, pos = tok
            if expect_num:
                if kind == 'RBRACE':
                    raise ParseError(
                        "'{{}}' 中第 {} 个倍数为空，倍数必须是正整数（第 {} 个字符）"
                        .format(len(nums) + 1, pos + 1), pos)
                if kind != 'NUM':
                    raise ParseError(
                        "'{{}}' 中第 {} 个倍数必须是正整数（第 {} 个字符）"
                        .format(len(nums) + 1, pos + 1), pos)
                self.advance()
                n = int(val)
                if n <= 0:
                    raise ParseError(
                        "倍数必须为正整数，收到 {}（第 {} 个字符）".format(n, pos + 1), pos)
                nums.append(n)
                expect_num = False
            else:
                if kind == 'RBRACE':
                    self.advance()
                    break
                if kind == 'PIPE':
                    self.advance()
                    expect_num = True
                    continue
                raise ParseError(
                    "尺码倍数之间必须用 '|' 分隔（第 {} 个字符）".format(pos + 1), pos)

        if len(nums) != self.n:
            raise ParseError(
                "'{{...}}' 中共有 {} 个倍数，与尺码数 {} 不一致（第 {} 个字符）"
                .format(len(nums), self.n, brace_pos + 1), brace_pos)
        return nums


def parse_row(text):
    """解析一行指令，返回 (消耗针数, 产出针数)。非法输入抛出 ParseError。"""
    tokens = _tokenize(text)
    if not tokens:
        raise ParseError("该行没有有效指令")
    return _Parser(tokens).parse_row()


def parse_row_sizes(text, size_count):
    """解析一行多尺码指令，返回按尺码顺序排列的 (消耗, 产出) 列表。

    普通 *n 对所有尺码生效；'*{n1|n2|...}' 中的倍数按尺码顺序分别取值，
    项数必须等于 size_count。非法输入抛出 ParseError（含字符位置）。
    """
    if isinstance(size_count, bool) or not isinstance(size_count, int) or size_count <= 0:
        raise ValueError("size_count 必须为正整数")
    tokens = _tokenize(text)
    if not tokens:
        raise ParseError("该行没有有效指令")
    return _Parser(tokens, size_count).parse_row()
