import unittest

from app import app


class TestValidateApi(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def post(self, cast_on, pattern):
        return self.client.post('/api/validate', json={
            'cast_on': cast_on,
            'pattern': pattern,
        }).get_json()

    def test_all_valid(self):
        data = self.post(12, '(k2tog yo)*6\np*12\n(k2tog)*6\n(yo k2tog)*3\nk*6')
        self.assertTrue(data['ok'])
        self.assertIsNone(data['error'])
        self.assertEqual(len(data['rows']), 5)
        self.assertEqual(data['rows'][0]['in'], 12)
        self.assertEqual(data['rows'][0]['consume'], 12)
        self.assertEqual(data['rows'][0]['out'], 12)
        self.assertEqual(data['rows'][2]['out'], 6)
        self.assertEqual(data['final'], 6)

    def test_count_shortfall(self):
        # 第 2 行需要 13 针，但只有 12 针，缺 1 针
        data = self.post(12, 'k*12\nk*13\nk*12')
        self.assertFalse(data['ok'])
        self.assertEqual(len(data['rows']), 1)  # 错误行及之后不再推算
        err = data['error']
        self.assertEqual(err['type'], 'count')
        self.assertEqual(err['line'], 2)
        self.assertEqual(err['diff'], 1)

    def test_count_leftover(self):
        # 第 2 行只消耗 10 针，剩余 2 针未使用
        data = self.post(12, 'k*12\nk*10')
        self.assertFalse(data['ok'])
        err = data['error']
        self.assertEqual(err['line'], 2)
        self.assertEqual(err['diff'], -2)

    def test_parse_error_stops(self):
        data = self.post(4, 'k*4\nssk\nk*4')
        self.assertFalse(data['ok'])
        self.assertEqual(len(data['rows']), 1)
        self.assertEqual(data['error']['type'], 'parse')
        self.assertEqual(data['error']['line'], 2)

    def test_parse_error_has_column(self):
        data = self.post(4, 'k*4\nk*ssk')
        err = data['error']
        self.assertEqual(err['type'], 'parse')
        self.assertEqual(err['line'], 2)
        self.assertIsNotNone(err['column'])

    def test_blank_lines_skipped_but_line_numbers_kept(self):
        data = self.post(2, 'k*2\n\nk*3')
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['line'], 3)

    def test_bad_cast_on(self):
        for bad in [0, -3, 'abc', '2.5', None, True]:
            data = self.post(bad, 'k*2')
            self.assertFalse(data['ok'], msg=repr(bad))
            self.assertEqual(data['error']['type'], 'cast_on')

    def test_string_cast_on_accepted(self):
        data = self.post('4', 'k*4')
        self.assertTrue(data['ok'])
        self.assertEqual(data['final'], 4)


class TestValidateSizesApi(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def post(self, sizes, pattern):
        return self.client.post('/api/validate-sizes', json={
            'sizes': sizes,
            'pattern': pattern,
        }).get_json()

    def test_all_sizes_valid(self):
        data = self.post(
            [{'name': 'S', 'cast_on': 6}, {'name': 'M', 'cast_on': 8},
             {'name': 'L', 'cast_on': 10}],
            '(k2tog yo)*{3|4|5}\np*{6|8|10}\n(k2tog)*{3|4|5}')
        self.assertTrue(data['ok'])
        self.assertIsNone(data['error'])
        self.assertEqual([s['name'] for s in data['sizes']], ['S', 'M', 'L'])
        finals = {s['name']: s['final'] for s in data['sizes']}
        self.assertEqual(finals, {'S': 3, 'M': 4, 'L': 5})
        for size in data['sizes']:
            self.assertTrue(size['ok'])
            self.assertIsNone(size['error'])
            self.assertEqual(len(size['rows']), 3)

    def test_each_size_chains_its_own_output(self):
        # 第 1 行 (k yo)*{2|4}：S 消耗 2 产出 4；M 消耗 4 产出 8
        # 第 2 行 S 用 p*4；M 用 p*8，各自沿用自己上一行产出
        data = self.post(
            [{'name': 'S', 'cast_on': 2}, {'name': 'M', 'cast_on': 4}],
            '(k yo)*{2|4}\np*{4|8}')
        self.assertTrue(data['ok'])
        s, m = data['sizes']
        self.assertEqual(s['rows'][1]['in'], 4)
        self.assertEqual(m['rows'][1]['in'], 8)

    def test_one_size_stops_others_continue(self):
        # 起针 S=6, M=8：第 2 行 S 需要 8（缺 2）停止；M 正常继续到最终 4
        data = self.post(
            [{'name': 'S', 'cast_on': 6}, {'name': 'M', 'cast_on': 8}],
            '(k2tog yo)*{3|4}\np*{8|8}\nk2tog*{3|4}')
        self.assertFalse(data['ok'])
        s, m = data['sizes']
        self.assertFalse(s['ok'])
        self.assertEqual(s['error']['type'], 'count')
        self.assertEqual(s['error']['line'], 2)
        self.assertEqual(s['error']['diff'], 2)
        self.assertEqual(len(s['rows']), 1)  # 出错尺码停止
        self.assertNotIn('final', s)
        self.assertTrue(m['ok'])
        self.assertEqual(len(m['rows']), 3)  # 其他尺码继续
        self.assertEqual(m['final'], 4)

    def test_parse_error_applies_to_all_active_sizes(self):
        data = self.post(
            [{'name': 'S', 'cast_on': 2}, {'name': 'M', 'cast_on': 4}],
            'k*{2|4}\nssk\nk*{1|1}')
        s, m = data['sizes']
        self.assertFalse(s['ok'])
        self.assertFalse(m['ok'])
        self.assertEqual(s['error']['line'], 2)
        self.assertEqual(m['error']['line'], 2)
        self.assertEqual(s['error']['type'], 'parse')
        self.assertIsNotNone(s['error']['column'])
        self.assertEqual(len(s['rows']), 1)
        self.assertEqual(len(m['rows']), 1)

    def test_count_error_earlier_than_parse_error(self):
        # S 在第 1 行就针数不足（需要 4 只有 2），M 走到第 2 行解析错误
        data = self.post(
            [{'name': 'S', 'cast_on': 2}, {'name': 'M', 'cast_on': 4}],
            'k*{4|4}\nssk')
        s, m = data['sizes']
        self.assertEqual(s['error']['type'], 'count')
        self.assertEqual(s['error']['line'], 1)
        self.assertEqual(m['error']['type'], 'parse')
        self.assertEqual(m['error']['line'], 2)

    def test_brace_count_mismatch(self):
        data = self.post(
            [{'name': 'S', 'cast_on': 2}, {'name': 'M', 'cast_on': 4}],
            'k*{2|3|4}')
        s, m = data['sizes']
        self.assertFalse(s['ok'])
        self.assertFalse(m['ok'])
        err = s['error']
        self.assertEqual(err['type'], 'parse')
        self.assertEqual(err['line'], 1)
        self.assertIsNotNone(err['column'])
        self.assertIn('不一致', err['message'])

    def test_empty_pattern(self):
        data = self.post(
            [{'name': 'S', 'cast_on': 6}, {'name': 'M', 'cast_on': 8}], '')
        self.assertTrue(data['ok'])
        self.assertEqual([s['final'] for s in data['sizes']], [6, 8])

    def test_request_errors(self):
        # sizes 不是数组
        data = self.client.post('/api/validate-sizes',
                                json={'sizes': None, 'pattern': 'k'}).get_json()
        self.assertFalse(data['ok'])
        self.assertEqual(data['error']['type'], 'request')
        self.assertEqual(data['sizes'], [])

        # 空数组
        data = self.post([], 'k')
        self.assertEqual(data['error']['type'], 'request')

        # 缺名称 / 空名称 / 重名
        for sizes in [
            [{'cast_on': 6}],
            [{'name': '  ', 'cast_on': 6}],
            [{'name': 'S', 'cast_on': 6}, {'name': 'S', 'cast_on': 8}],
        ]:
            data = self.post(sizes, 'k')
            self.assertEqual(data['error']['type'], 'request', msg=repr(sizes))

        # 起针数非法
        for bad in [0, -1, 'abc', None, True]:
            data = self.post([{'name': 'S', 'cast_on': bad}], 'k')
            self.assertEqual(data['error']['type'], 'request', msg=repr(bad))

    def test_blank_lines_keep_line_numbers(self):
        data = self.post(
            [{'name': 'S', 'cast_on': 2}, {'name': 'M', 'cast_on': 2}],
            'k*{2|2}\n\nk*{3|3}')
        s, _ = data['sizes']
        self.assertFalse(s['ok'])
        self.assertEqual(s['error']['line'], 3)

    def test_string_cast_on_accepted(self):
        data = self.post(
            [{'name': 'S', 'cast_on': '6'}], 'k*6')
        self.assertTrue(data['ok'])
        self.assertEqual(data['sizes'][0]['final'], 6)


if __name__ == '__main__':
    unittest.main()
