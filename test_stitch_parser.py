import unittest

from stitch_parser import ParseError, parse_row, parse_row_sizes


class TestParseRow(unittest.TestCase):
    def test_basic_stitches(self):
        self.assertEqual(parse_row('k'), (1, 1))
        self.assertEqual(parse_row('p'), (1, 1))
        self.assertEqual(parse_row('yo'), (0, 1))
        self.assertEqual(parse_row('k2tog'), (2, 1))

    def test_sequence_with_separators(self):
        self.assertEqual(parse_row('k k yo k2tog'), (4, 4))
        self.assertEqual(parse_row('k, k, yo, k2tog'), (4, 4))
        self.assertEqual(parse_row('kkyo k2tog'), (4, 4))

    def test_group_repeat(self):
        self.assertEqual(parse_row('(k2tog yo)*6'), (12, 12))
        self.assertEqual(parse_row('(k yo)*2 p'), (3, 5))

    def test_nested_groups(self):
        # (k yo)*2 -> (2,4)；+ k2tog -> (4,5)；整体 *3
        self.assertEqual(parse_row('((k yo)*2 k2tog)*3'), (12, 15))

    def test_atom_repeat(self):
        self.assertEqual(parse_row('k*3'), (3, 3))
        self.assertEqual(parse_row('k2tog*4'), (8, 4))

    def test_huge_multiplier_is_not_expanded(self):
        self.assertEqual(parse_row('(k yo)*1000000000'), (1000000000, 2000000000))

    def test_case_insensitive(self):
        self.assertEqual(parse_row('K2TOG, YO, K, P'), (4, 4))

    def test_invalid_tokens(self):
        for bad in ['ssk', 'k3', 'k 2', 'm1', 'k/p', 'k+yo']:
            with self.assertRaises(ParseError, msg=bad):
                parse_row(bad)

    def test_bad_parentheses(self):
        for bad in ['(k yo', 'k)', '()', '( )', '(k))*2', '(k (yo)']:
            with self.assertRaises(ParseError, msg=bad):
                parse_row(bad)

    def test_bad_multiplier(self):
        for bad in ['k*0', '(k)*0', 'k*-1', 'k*', 'k*yo', '*3 k', '(k)*2*3']:
            with self.assertRaises(ParseError, msg=bad):
                parse_row(bad)

    def test_empty_row(self):
        with self.assertRaises(ParseError):
            parse_row('   ')

    def test_size_syntax_rejected_in_single_mode(self):
        for bad in ['k*{2|3}', '(k)*{2|3}', 'k*{2}']:
            with self.assertRaises(ParseError, msg=bad) as cm:
                parse_row(bad)
            self.assertIsNotNone(cm.exception.pos)

    def test_stray_brace_and_pipe(self):
        for bad in ['k|p', 'k}p', 'k{2}p', '|', '}']:
            with self.assertRaises(ParseError, msg=bad):
                parse_row(bad)


class TestParseRowSizes(unittest.TestCase):
    def test_plain_repeat_applies_to_all_sizes(self):
        self.assertEqual(parse_row_sizes('k*3', 3), [(3, 3), (3, 3), (3, 3)])
        self.assertEqual(parse_row_sizes('(k yo)*2 p', 2), [(3, 5), (3, 5)])

    def test_size_repeat_takes_values_in_order(self):
        # k2tog: 消耗2/产出1；yo: 0/1
        self.assertEqual(
            parse_row_sizes('(k2tog yo)*{3|4|5}', 3),
            [(6, 6), (8, 8), (10, 10)])
        self.assertEqual(
            parse_row_sizes('p*{6|8|10}', 3),
            [(6, 6), (8, 8), (10, 10)])

    def test_single_element_brace(self):
        self.assertEqual(parse_row_sizes('k*{4}', 1), [(4, 4)])

    def test_mixed_plain_and_size_repeats(self):
        # k*2 对所有尺码 -> (2,2)；k2tog*{1|2} -> (2,1)/(4,2)
        self.assertEqual(
            parse_row_sizes('k*2 k2tog*{1|2}', 2),
            [(4, 3), (6, 4)])

    def test_nested_size_repeat_inside_group(self):
        # 内层 (k yo)*2 = (2,4)；整体 *{1|2}
        self.assertEqual(
            parse_row_sizes('((k yo)*2 k2tog)*{1|2}', 2),
            [(4, 5), (8, 10)])

    def test_plain_outer_with_size_inner(self):
        # 内层 (k)*{1|2} 分别 (1,1)/(2,2)，外层 *3
        self.assertEqual(
            parse_row_sizes('((k)*{1|2} yo)*3', 2),
            [(3, 6), (6, 9)])

    def test_whitespace_inside_braces(self):
        self.assertEqual(
            parse_row_sizes('k*{ 2 | 3 }', 2), [(2, 2), (3, 3)])

    def test_count_mismatch_reports_position(self):
        for bad in ['k*{1|2}', 'k*{1|2|3|4}']:
            with self.assertRaises(ParseError, msg=bad) as cm:
                parse_row_sizes(bad, 3)
            err = cm.exception
            self.assertIsNotNone(err.pos)
            # 'k*{1|2}' 中 '{' 位于第 3 个字符（下标 2）
            self.assertEqual(err.pos, 3)

    def test_illegal_multipliers_report_position(self):
        for bad in ['k*{0|2}', 'k*{1|}', 'k*{|2}', 'k*{1|2|}', 'k*{1 2}',
                    'k*{a|b}', 'k*{1|2', '{1|2}', 'k*{1|2}*3']:
            with self.assertRaises(ParseError, msg=bad) as cm:
                parse_row_sizes(bad, 2)
            self.assertIsNotNone(cm.exception.pos, msg=bad)

    def test_pipe_outside_braces(self):
        for bad in ['k|p', '(k)*{1|2}|p']:
            with self.assertRaises(ParseError, msg=bad):
                parse_row_sizes(bad, 2)

    def test_empty_row(self):
        with self.assertRaises(ParseError):
            parse_row_sizes('   ', 2)

    def test_bad_size_count(self):
        for bad in [0, -1, True, '2', None]:
            with self.assertRaises(ValueError, msg=repr(bad)):
                parse_row_sizes('k', bad)


if __name__ == '__main__':
    unittest.main()
