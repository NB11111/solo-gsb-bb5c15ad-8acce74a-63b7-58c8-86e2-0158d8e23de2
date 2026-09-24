import unittest

from stitch_parser import ParseError, parse_row


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


if __name__ == '__main__':
    unittest.main()
