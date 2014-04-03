import unittest
import sys
sys.path.append('..')
import find_link

class TestWebApp(unittest.TestCase):
    def setUp(self):
        self.app = find_link.app.test_client()

    def test_fav_icon(self):
        rv = self.app.get('/favicon.ico')
        self.assertTrue(rv.headers.get('Location').endswith('/static/Link_edit.png'))
        self.assertEqual(rv.mimetype, 'text/html')
        self.assertEqual(rv.status_code, 302)

    def test_index(self):
        rv = self.app.get('/')
        self.assertEqual(rv.mimetype, 'text/html')
        self.assertEqual(rv.status_code, 200)

        rv = self.app.get('/?q=hackerspace')
        self.assertEqual(rv.mimetype, 'text/html')
        self.assertTrue(rv.headers.get('Location').endswith('/hackerspace'))
        self.assertEqual(rv.status_code, 302)

    def test_findlink(self):
        rv = self.app.get('/hackerspace')
        self.assertEqual(rv.mimetype, 'text/html')
        self.assertEqual(rv.status_code, 200)
