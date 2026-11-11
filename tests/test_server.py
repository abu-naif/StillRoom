import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import start


class AccountsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        start.DATABASE = Path(cls.temp.name) / 'test.sqlite3'
        start.initialize()
        cls.server = start.ThreadingHTTPServer(('127.0.0.1', 0), start.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.temp.cleanup()

    def request(self, path, data=None, cookie='', headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        hdr = {'Cookie': cookie, 'X-Stillroom': '1', 'Content-Type': 'application/json'}
        if headers:
            hdr.update(headers)
        conn.request('POST' if data is not None else 'GET', path, json.dumps(data) if data is not None else None, hdr)
        response = conn.getresponse()
        status, session = response.status, response.getheader('Set-Cookie')
        body = response.read()
        conn.close()
        return status, session, json.loads(body)

    def test_account_isolation_persistence_and_sessions(self):
        self.assertEqual(self.request('/api/history')[0], 401)
        user = {'username': 'alice', 'password': 'correct horse battery'}
        status, cookie, _ = self.request('/api/register', user)
        self.assertEqual(status, 200)
        self.assertIn('HttpOnly', cookie)
        cookie = cookie.split(';')[0]
        self.assertEqual(self.request('/api/me', cookie=cookie)[2]['username'], 'alice')
        video = {'provider': 'youtube', 'id': 'dQw4w9WgXcQ'}
        self.assertEqual(self.request('/api/watch', video, cookie)[0], 200)
        self.assertEqual(self.request('/api/save', {**video, 'notes': 'private note', 'position': 123.5, 'title': 'A video'}, cookie)[0], 200)
        self.assertEqual(self.request('/api/watch', video, cookie)[2]['position'], 123.5)
        _, bob, _ = self.request('/api/register', {'username': 'bob', 'password': 'another password'})
        bob = bob.split(';')[0]
        self.assertEqual(self.request('/api/history', cookie=bob)[2], [])
        self.assertEqual(self.request('/api/save', {**video, 'notes': 'overwrite'}, bob)[0], 404)
        self.request('/api/watch', video, bob)
        self.assertEqual(self.request('/api/history', cookie=bob)[2][0]['notes'], '')
        self.assertEqual(self.request('/api/history', cookie=cookie)[2][0]['notes'], 'private note')
        self.assertEqual(self.request('/api/logout', {}, cookie)[0], 200)
        self.assertEqual(self.request('/api/me', cookie=cookie)[0], 401)
        self.assertEqual(self.request('/api/login', {**user, 'password': 'wrong password'})[0], 401)
        status, again, _ = self.request('/api/login', user)
        self.assertEqual(status, 200)
        self.assertEqual(self.request('/api/history', cookie=again.split(';')[0])[2][0]['position'], 123.5)
        with start.connect() as db:
            stored = db.execute('SELECT password FROM users WHERE username="alice"').fetchone()[0]
            self.assertNotEqual(stored, user['password'])

    def test_validation_and_private_files(self):
        for path in ['/data/stillroom.sqlite3', '/.git/config', '/start.py', '/src/App.tsx', '/data/']:
            self.assertEqual(self.request(path)[0], 404)
        self.assertEqual(self.request('/api/register', {'username': 'short', 'password': 'short'})[0], 400)
        self.assertEqual(self.request('/api/register', {}, headers={'Origin': 'https://evil.example'})[0], 403)
        _, cookie, _ = self.request('/api/register', {'username': 'tester', 'password': 'test password long'})
        cookie = cookie.split(';')[0]
        video = {'provider': 'drive', 'id': 'drive-file', 'resourceKey': 'key'}
        self.request('/api/watch', video, cookie)
        self.assertEqual(self.request('/api/save', {**video, 'position': -1}, cookie)[0], 400)
        self.assertEqual(self.request('/api/save', {**video, 'position': float('nan')}, cookie)[0], 400)
        self.assertEqual(self.request('/api/watch', {**video, 'provider': 'invalid'}, cookie)[0], 400)
        with start.connect() as db:
            db.execute('UPDATE sessions SET expires=0')
        self.assertEqual(self.request('/api/history', cookie=cookie)[0], 401)


if __name__ == '__main__':
    unittest.main()
