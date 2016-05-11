# coding=utf-8

import unittest
from find_link.util import is_title_case, urlquote, is_disambig, norm, case_flip

class TestFindLinkUtil(unittest.TestCase):
    def test_is_test_case(self):
        self.assertTrue(is_title_case('Test'))
        self.assertTrue(is_title_case('Test Test'))
        self.assertFalse(is_title_case('test'))
        self.assertFalse(is_title_case('TEST TEST'))
        self.assertFalse(is_title_case('test test'))
        self.assertFalse(is_title_case('tEst Test'))

    def test_urlquote(self):
        self.assertEqual(urlquote('test'), 'test')
        self.assertEqual(urlquote('test test'), 'test+test')
        self.assertEqual(urlquote(u'na\xefve'), 'na%C3%AFve')

    def test_is_disambig(self):
        self.assertFalse(is_disambig({}))
        self.assertTrue(is_disambig({
            'templates': [{'title': 'disambig'}, {'title': 'magic'}]
        }))
        self.assertTrue(is_disambig({'templates': [{'title': 'geodis'}] }))
        self.assertTrue(is_disambig({'templates': [{'title': 'Disambig'}] }))

    def test_norm(self):
        self.assertEqual(norm('X'), 'x')
        self.assertEqual(norm('Tables'), 'table')
        self.assertEqual(norm('Tables!!!'), 'table')

    def test_case_flip(self):
        self.assertEqual(case_flip('a'), 'A')
        self.assertEqual(case_flip('A'), 'a')
        self.assertEqual(case_flip('1'), '1')
