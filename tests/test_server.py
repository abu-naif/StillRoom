import base64
import http.client
import json
import sqlite3
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
        content_type = response.getheader("Content-Type", "")
        body = response.read()
        conn.close()
        return status, session, json.loads(body) if "application/json" in content_type else body

    def test_public_assets_revalidate_on_mobile_refresh(self):
        for path in ('/', '/app.js', '/styles.css', '/sw.js'):
            conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
            conn.request('HEAD', path)
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader('Cache-Control'), 'no-cache, must-revalidate')
            response.read()
            conn.close()

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

    def test_friend_requests_messages_and_attachments(self):
        def account(name):
            status, cookie, _ = self.request('/api/register', {'username': name, 'password': 'a long chat password'})
            self.assertEqual(status, 200)
            cookie = cookie.split(';')[0]
            return cookie, self.request('/api/me', cookie=cookie)[2]['id']
        alice, aid = account('chat-alice')
        bob, bid = account('chat-bob')
        outsider, oid = account('chat-outsider')
        self.assertEqual(self.request('/api/social')[0], 401)
        self.assertEqual(self.request('/api/messages?peer='+str(bid), cookie=alice)[0], 403)
        message = {'peer': bid, 'text': 'Hello 👋 ❤️', 'client_id': 'test-message-000001'}
        self.assertEqual(self.request('/api/messages/send', message, alice)[0], 403)
        self.assertEqual(self.request('/api/friends/request', {'username': 'chat-alice'}, alice)[0], 400)
        self.assertEqual(self.request('/api/friends/request', {'username': 'no-such-user'}, alice)[0], 404)
        self.assertEqual(self.request('/api/friends/request', {'username': 'CHAT-BOB'}, alice)[0], 200)
        self.assertEqual(self.request('/api/friends/request', {'username': 'chat-alice'}, bob)[0], 409)
        row = self.request('/api/social', cookie=bob)[2][0]
        self.assertEqual(row['status'], 'pending')
        self.assertEqual(row['peer_id'], aid)
        action = {'request_id': row['id'], 'action': 'accept'}
        self.assertEqual(self.request('/api/friends/respond', action, alice)[0], 403)
        self.assertEqual(self.request('/api/friends/respond', action, outsider)[0], 404)
        self.assertEqual(self.request('/api/friends/respond', action, bob)[0], 200)
        self.assertEqual(self.request('/api/social', cookie=alice)[2][0]['status'], 'accepted')
        status, _, sent = self.request('/api/messages/send', message, alice)
        self.assertEqual(status, 200)
        self.assertEqual(self.request('/api/messages/send', message, alice)[2]['id'], sent['id'])
        self.assertEqual(self.request('/api/messages/typing', {'peer': bid, 'typing': True}, outsider)[0], 403)
        self.assertEqual(self.request('/api/messages/typing', {'peer': bid, 'typing': 'yes'}, alice)[0], 400)
        self.assertEqual(self.request('/api/messages/typing', {'peer': bid, 'typing': True}, alice)[0], 200)
        self.assertTrue(self.request('/api/social', cookie=bob)[2][0]['typing'])
        self.assertFalse(self.request('/api/social', cookie=alice)[2][0]['typing'])
        self.assertEqual(self.request('/api/social', cookie=alice)[2][0]['last_message']['id'], sent['id'])
        self.assertEqual(self.request('/api/messages?peer='+str(bid), cookie=alice)[2]['read_through'], 0)
        self.assertEqual(self.request('/api/messages/read', {'peer': aid, 'through': sent['id']}, bob)[0], 200)
        self.assertEqual(self.request('/api/social', cookie=alice)[2][0]['read_through'], sent['id'])
        self.assertEqual(self.request('/api/messages?peer='+str(bid), cookie=alice)[2]['read_through'], sent['id'])
        self.request('/api/messages/typing', {'peer': bid, 'typing': False}, alice)
        self.assertFalse(self.request('/api/social', cookie=bob)[2][0]['typing'])

        conversation = self.request('/api/messages?peer='+str(aid), cookie=bob)[2]['messages']
        self.assertEqual(len(conversation), 1)
        self.assertEqual(conversation[0]['text'], 'Hello 👋 ❤️')
        self.assertEqual(self.request('/api/messages?peer='+str(aid), cookie=outsider)[0], 403)
        self.assertEqual(self.request('/api/messages/send', {**message, 'text': '  ', 'client_id': 'empty-message-00001'}, alice)[0], 400)
        files = [
            ('paper.pdf', 'application/pdf', b'%PDF-1.4\nexample'),
            ('picture.png', 'image/png', b'\x89PNG\r\n\x1a\nexample'),
            ('voice.webm', 'audio/webm', b'\x1aE\xdf\xa3example'),
        ]
        for index, (name, mime, content) in enumerate(files):
            payload = {'peer': aid, 'text': '', 'client_id': 'attachment-message-'+str(index), 'attachment': {'name': name, 'mime': mime, 'data': base64.b64encode(content).decode()}}
            if mime.startswith('audio/'):
                payload['attachment']['duration'] = 3.5
            status, _, item = self.request('/api/messages/send', payload, bob)
            self.assertEqual(status, 200)
            self.assertNotIn('attachment', item)
            self.assertEqual(item['duration'], 3.5 if mime.startswith('audio/') else None)
            path = '/api/attachments/'+str(item['id'])
            self.assertEqual(self.request(path, cookie=alice)[2], content)
            self.assertEqual(self.request(path, cookie=bob)[2], content)
            self.assertEqual(self.request(path, cookie=outsider)[0], 404)
            self.assertEqual(self.request(path)[0], 401)
            with start.connect() as db:
                self.assertEqual(db.execute('SELECT attachment FROM messages WHERE id=?', (item['id'],)).fetchone()[0], content)
        for index, duration in enumerate([-1, float('nan'), '10', True]):
            payload = {'peer': aid, 'client_id': 'bad-duration-test-'+str(index), 'attachment': {'name': 'voice.webm', 'mime': 'audio/webm', 'data': base64.b64encode(files[2][2]).decode(), 'duration': duration}}
            self.assertEqual(self.request('/api/messages/send', payload, bob)[0], 400)
        invalid = {'peer': bid, 'client_id': 'bad-attachment-00001', 'attachment': {'name': 'bad.pdf', 'mime': 'application/pdf', 'data': base64.b64encode(b'<script>bad</script>').decode()}}
        self.assertEqual(self.request('/api/messages/send', invalid, alice)[0], 400)
        invalid['attachment'] = {'name': 'bad.svg', 'mime': 'image/svg+xml', 'data': base64.b64encode(b'<svg/>').decode()}
        self.assertEqual(self.request('/api/messages/send', invalid, alice)[0], 400)
        result = self.request('/api/messages?peer='+str(bid)+'&after='+str(sent['id']), cookie=alice)[2]['messages']
        self.assertEqual(len(result), 3)
        before = self.request('/api/messages?peer='+str(bid)+'&before='+str(result[0]['id']), cookie=alice)[2]['messages']
        self.assertEqual([r['id'] for r in before], [sent['id']])
        # Large conversations are paginated without exposing other chats.
        with start.connect() as db:
            for index in range(105):
                db.execute('INSERT INTO messages(sender_id,recipient_id,text,created,client_id) VALUES(?,?,?,?,?)',
                           (aid, bid, 'page '+str(index), 1, 'pagination-message-'+str(index)))
        latest = self.request('/api/messages?peer='+str(bid), cookie=alice)[2]
        self.assertEqual(len(latest['messages']), 100)
        self.assertTrue(latest['more'])
        earlier = self.request('/api/messages?peer='+str(bid)+'&before='+str(latest['messages'][0]['id']), cookie=alice)[2]
        self.assertEqual(len(earlier['messages']), 9)
        self.assertFalse(earlier['more'])
        # Existing databases are extended without losing messages or file bytes.
        start.initialize()
        self.assertEqual(self.request('/api/attachments/'+str(sent['id']+1), cookie=alice)[2], files[0][2])
        from chat import attachment, MAX_ATTACHMENT
        with self.assertRaises(ValueError):
            attachment({'name': 'too-large.pdf', 'mime': 'application/pdf',
                        'data': base64.b64encode(b'%PDF-'+b'x'*MAX_ATTACHMENT).decode()})
        with self.assertRaises(ValueError):
            attachment({'name': 'bad.pdf', 'mime': 'application/pdf', 'data': 'not base64!!!'})
        # Requests can be declined and cancelled, then sent again.
        self.request('/api/friends/request', {'username': 'chat-outsider'}, alice)
        request_id = self.request('/api/social', cookie=outsider)[2][0]['id']
        self.assertEqual(self.request('/api/friends/respond', {'request_id': request_id, 'action': 'decline'}, outsider)[0], 200)
        self.request('/api/friends/request', {'username': 'chat-outsider'}, alice)
        request_id = self.request('/api/social', cookie=outsider)[2][0]['id']
        self.assertEqual(self.request('/api/friends/respond', {'request_id': request_id, 'action': 'cancel'}, alice)[0], 200)
        self.assertEqual(self.request('/api/social', cookie=outsider)[2], [])

    def test_message_actions_and_friend_mutes(self):
        users=[]
        for name in ['action-alice','action-bob','action-outsider']:
            _,cookie,_=self.request('/api/register',{'username':name,'password':'message action password'})
            cookie=cookie.split(';')[0]
            users.append((cookie,self.request('/api/me',cookie=cookie)[2]['id']))
        (alice,aid),(bob,bid),(other,oid)=users
        self.request('/api/friends/request',{'username':'action-bob'},alice)
        rid=self.request('/api/social',cookie=bob)[2][0]['id']
        self.request('/api/friends/respond',{'request_id':rid,'action':'accept'},bob)
        _,_,sent=self.request('/api/messages/send',{'peer':bid,'text':'Original text','client_id':'action-message-0001'},alice)
        original=self.request('/api/messages?peer='+str(aid),cookie=bob)[2]
        self.assertEqual(self.request('/api/messages/edit',{'message_id':sent['id'],'text':'not yours'},bob)[0],404)
        self.assertEqual(self.request('/api/messages/delete',{'message_id':sent['id']},other)[0],404)
        status,_,edited=self.request('/api/messages/edit',{'message_id':sent['id'],'text':'Edited text'},alice)
        self.assertEqual(status,200)
        self.assertIsNotNone(edited['edited'])
        updates=self.request('/api/messages?peer='+str(aid)+'&after='+str(sent['id'])+'&changes_after='+str(original['revision']),cookie=bob)[2]
        self.assertEqual(updates['changes'][0]['text'],'Edited text')
        self.assertEqual(self.request('/api/messages/edit',{'message_id':sent['id'],'text':' '},alice)[0],400)
        self.assertEqual(self.request('/api/friends/mute',{'peer':oid,'muted':True},bob)[0],403)
        self.assertEqual(self.request('/api/friends/mute',{'peer':aid,'muted':True},bob)[0],200)
        self.assertTrue(self.request('/api/social',cookie=bob)[2][0]['muted'])
        self.assertFalse(self.request('/api/social',cookie=alice)[2][0]['muted'])
        self.assertEqual(self.request('/api/notifications',cookie=bob)[2]['total'],0)
        self.request('/api/friends/mute',{'peer':aid,'muted':False},bob)
        self.assertEqual(self.request('/api/notifications',cookie=bob)[2]['total'],1)
        status,_,deleted=self.request('/api/messages/delete',{'message_id':sent['id']},alice)
        self.assertEqual(status,200)
        self.assertTrue(deleted['deleted'])
        self.assertEqual(deleted['text'],'')
        self.assertEqual(self.request('/api/messages/edit',{'message_id':sent['id'],'text':'revive'},alice)[0],409)
        self.assertEqual(self.request('/api/messages/delete',{'message_id':sent['id']},alice)[0],200)
        self.assertEqual(self.request('/api/notifications',cookie=bob)[2]['total'],0)
        updates=self.request('/api/messages?peer='+str(aid)+'&after='+str(sent['id'])+'&changes_after='+str(updates['revision']),cookie=bob)[2]
        self.assertTrue(updates['changes'][0]['deleted'])

    def test_notification_preferences_and_read_state(self):
        def account(name):
            status, cookie, _ = self.request('/api/register', {'username': name, 'password': 'notification test password'})
            self.assertEqual(status, 200)
            cookie = cookie.split(';')[0]
            return cookie, self.request('/api/me', cookie=cookie)[2]['id']
        alice, aid = account('notify-alice')
        bob, bid = account('notify-bob')
        outsider, oid = account('notify-outsider')
        self.assertEqual(self.request('/api/notifications')[0], 401)
        self.assertEqual(self.request('/api/notifications', cookie=bob)[2]['total'], 0)
        self.request('/api/friends/request', {'username': 'notify-bob'}, alice)
        pending = self.request('/api/notifications', cookie=bob)[2]
        self.assertTrue(pending['enabled'])
        self.assertEqual(pending['total'], 1)
        self.assertEqual(pending['requests'][0]['username'], 'notify-alice')
        rid = pending['requests'][0]['id']
        # Another user cannot acknowledge someone else's request.
        self.request('/api/notifications/read-requests', {'ids': [rid]}, outsider)
        self.assertEqual(self.request('/api/notifications', cookie=bob)[2]['total'], 1)
        self.request('/api/notifications/read-requests', {'ids': [rid]}, bob)
        self.assertEqual(self.request('/api/notifications', cookie=bob)[2]['total'], 0)
        self.assertEqual(self.request('/api/social', cookie=bob)[2][0]['status'], 'pending')
        self.request('/api/friends/respond', {'request_id': rid, 'action': 'accept'}, bob)
        def send(client_id, text):
            return self.request('/api/messages/send', {'peer': bid, 'text': text, 'client_id': client_id}, alice)[2]['id']
        first = send('notification-msg-0001', 'hello')
        self.assertEqual(self.request('/api/notifications', cookie=alice)[2]['total'], 0)
        unread = self.request('/api/notifications', cookie=bob)[2]
        self.assertEqual(unread['total'], 1)
        self.assertEqual(unread['conversations'][0]['peer_id'], aid)
        # Fetching or background polling must not silently read a conversation.
        self.request('/api/messages?peer='+str(aid), cookie=bob)
        self.assertEqual(self.request('/api/notifications', cookie=bob)[2]['total'], 1)
        self.assertEqual(self.request('/api/messages/read', {'peer': aid, 'through': first}, outsider)[0], 403)
        self.assertEqual(self.request('/api/messages/read', {'peer': aid, 'through': 99999999}, bob)[0], 400)
        self.assertEqual(self.request('/api/messages/read', {'peer': aid, 'through': first}, bob)[0], 200)
        self.assertEqual(self.request('/api/notifications', cookie=bob)[2]['total'], 0)
        second = send('notification-msg-0002', 'another message')
        self.assertEqual(self.request('/api/notifications/settings', {'enabled': False}, bob)[0], 200)
        muted = self.request('/api/notifications', cookie=bob)[2]
        self.assertFalse(muted['enabled'])
        self.assertEqual(muted['total'], 1)  # Unread state stays available when notifications are reenabled.
        self.assertTrue(self.request('/api/notifications', cookie=alice)[2]['enabled'])
        start.initialize()
        self.assertFalse(self.request('/api/notifications', cookie=bob)[2]['enabled'])
        self.request('/api/notifications/settings', {'enabled': True}, bob)
        self.assertTrue(self.request('/api/notifications', cookie=bob)[2]['enabled'])
        self.request('/api/messages/read', {'peer': aid, 'through': second}, bob)
        self.request('/api/messages/read', {'peer': aid, 'through': first}, bob)
        self.assertEqual(self.request('/api/notifications', cookie=bob)[2]['total'], 0)
        self.assertEqual(self.request('/api/notifications/settings', {'enabled': 'false'}, bob)[0], 400)
        self.assertEqual(self.request('/api/notifications/read-requests', {'ids': 'all'}, bob)[0], 400)
        # Deleting a request deletes its acknowledgement, including when SQLite reuses an ID.
        self.request('/api/friends/request', {'username': 'notify-outsider'}, alice)
        rid = self.request('/api/notifications', cookie=outsider)[2]['requests'][0]['id']
        self.request('/api/notifications/read-requests', {'ids': [rid]}, outsider)
        self.request('/api/friends/respond', {'request_id': rid, 'action': 'cancel'}, alice)
        self.request('/api/friends/request', {'username': 'notify-outsider'}, alice)
        self.assertEqual(self.request('/api/notifications', cookie=outsider)[2]['total'], 1)

    def test_existing_chat_database_duration_migration(self):
        import chat
        db = sqlite3.connect(':memory:')
        db.row_factory = sqlite3.Row
        try:
            db.execute('CREATE TABLE users(id INTEGER PRIMARY KEY)')
            db.executescript("""CREATE TABLE messages(
                id INTEGER PRIMARY KEY, sender_id INTEGER, recipient_id INTEGER, text TEXT,
                created REAL, client_id TEXT, filename TEXT, mime TEXT, size INTEGER, attachment BLOB);
                INSERT INTO messages VALUES(1,1,2,'old message',1,'old-client-id','voice.webm','audio/webm',4,X'1a45dfa3');""")
            chat.initialize(db)
            chat.initialize(db)
            row = db.execute('SELECT * FROM messages WHERE id=1').fetchone()
            self.assertEqual(row['text'], 'old message')
            self.assertEqual(row['attachment'], b'\x1aE\xdf\xa3')
            self.assertIsNone(row['duration'])
        finally:
            db.close()

    def test_install_assets_and_configured_https_origin(self):
        for path in ['/manifest.webmanifest', '/sw.js', '/icons/icon-192.png', '/icons/icon-512.png', '/icons/apple-touch-icon.png']:
            status, _, _ = self.request(path)
            self.assertEqual(status, 200, path)
        manifest = json.loads(self.request('/manifest.webmanifest')[2])
        self.assertEqual(manifest['display'], 'standalone')
        for icon in manifest['icons']:
            content = self.request(icon['src'])[2]
            self.assertEqual(content[:8], b'\x89PNG\r\n\x1a\n')
            size = int(icon['sizes'].split('x')[0])
            self.assertEqual(int.from_bytes(content[16:20], 'big'), size)
        origin = 'https://stillroom.example.test'
        self.server.public_origin = origin
        try:
            data = {'username': 'https-user', 'password': 'https test password'}
            self.assertEqual(self.request('/api/register', data, headers={'Origin': 'https://wrong.test'})[0], 403)
            status, cookie, _ = self.request('/api/register', data, headers={'Origin': origin})
            self.assertEqual(status, 200)
            self.assertIn('; Secure', cookie)
        finally:
            del self.server.public_origin

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
