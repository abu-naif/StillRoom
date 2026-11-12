import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import start
import push_notify


def b64(value):
    return base64.urlsafe_b64encode(value).decode().rstrip('=')


class PushTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.previous=start.DATABASE
        start.DATABASE=Path(self.temp.name)/'test.sqlite3'
        start.initialize()
        self.sub={'endpoint':'https://fcm.googleapis.com/fcm/send/test-only','keys':{'p256dh':b64(b'\x04'+b'a'*64),'auth':b64(b'a'*16)}}
        with start.connect() as db:
            for uid in [1,2,3]:
                db.execute('INSERT INTO users VALUES(?,?,?,?)',(uid,'push-user-'+str(uid),'00'*16,'test-only'))
            db.execute('INSERT INTO sessions VALUES(?,?,?)',('test-session',2,time.time()+3600))
            db.execute("INSERT INTO friendships(low_id,high_id,sender_id,status,created) VALUES(1,2,1,'accepted',?)",(time.time(),))
            db.execute('INSERT INTO push_subscriptions VALUES(?,?,?,?,?)',(self.sub['endpoint'],2,'test-session',json.dumps(self.sub),time.time()))
            db.execute("INSERT INTO messages(sender_id,recipient_id,text,created,client_id) VALUES(1,2,'hello',?,'test-message-000001')",(time.time(),))

    def tearDown(self):
        start.DATABASE=self.previous
        self.temp.cleanup()

    def queue(self):
        with start.connect() as db:
            push_notify.enqueue(db,2,1,'message',1)

    def jobs(self):
        with start.connect() as db:
            return db.execute('SELECT COUNT(*) FROM push_jobs').fetchone()[0]

    def test_delivery_and_display_recheck_quiet_mute_read_logout(self):
        self.queue()
        self.assertEqual(self.jobs(),1)
        delivered=[]
        push_notify.deliver_batch(start.connect,{},send=lambda sub,payload:delivered.append((sub,payload)))
        self.assertEqual(len(delivered),1)
        self.assertEqual(set(delivered[0][1]),{'event'})  # No private text in notification payloads.
        self.assertEqual(self.jobs(),0)
        with start.connect() as db:
            event=db.execute('SELECT * FROM push_events').fetchone()
            self.assertTrue(push_notify.allowed(db,event))
            db.execute('INSERT INTO notification_settings VALUES(2,0)')
        self.queue()
        self.assertEqual(self.jobs(),0)
        with start.connect() as db:
            self.assertFalse(push_notify.allowed(db,event))
            db.execute('UPDATE notification_settings SET enabled=1')
            db.execute('INSERT INTO friend_mutes VALUES(2,1)')
        self.queue()
        self.assertEqual(self.jobs(),0)
        with start.connect() as db:
            self.assertFalse(push_notify.allowed(db,event))
            db.execute('DELETE FROM friend_mutes')
        self.queue()
        with start.connect() as db:
            db.execute('INSERT INTO message_reads VALUES(2,1,1)')
        push_notify.deliver_batch(start.connect,{},send=lambda *args:self.fail('Read message should not push'))
        self.assertEqual(self.jobs(),0)
        with start.connect() as db:
            db.execute('DELETE FROM message_reads')
        self.queue()
        with start.connect() as db:
            db.execute("DELETE FROM sessions WHERE token='test-session'")
        self.assertEqual(self.jobs(),0)

    def test_invalid_endpoints_keys_and_expired_provider(self):
        self.assertEqual(push_notify.validate_subscription(self.sub),self.sub)
        for endpoint in ['http://fcm.googleapis.com/test','https://127.0.0.1/test','https://fcm.googleapis.com.evil.test/test','https://evil@fcm.googleapis.com/test','https://fcm.googleapis.com:8443/test']:
            with self.assertRaises(ValueError):
                push_notify.validate_subscription({**self.sub,'endpoint':endpoint})
        with self.assertRaises(ValueError):
            push_notify.validate_subscription({**self.sub,'keys':{'p256dh':'bad','auth':'bad'}})
        self.queue()
        class Gone(Exception):
            response=type('Response',(),{'status_code':410})()
        def gone(*args):
            raise Gone()
        push_notify.deliver_batch(start.connect,{},send=gone)
        with start.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM push_subscriptions').fetchone()[0],0)
        self.assertEqual(self.jobs(),0)

    def test_queued_notifications_are_dropped_after_mute_or_quiet(self):
        self.queue()
        with start.connect() as db:
            db.execute('INSERT INTO friend_mutes VALUES(2,1)')
        push_notify.deliver_batch(start.connect,{},send=lambda *args:self.fail('Muted friend must not push'))
        self.assertEqual(self.jobs(),0)
        with start.connect() as db:
            db.execute('DELETE FROM friend_mutes')
        self.queue()
        with start.connect() as db:
            db.execute('INSERT INTO notification_settings VALUES(2,0)')
        push_notify.deliver_batch(start.connect,{},send=lambda *args:self.fail('Quiet mode must not push'))
        self.assertEqual(self.jobs(),0)

    def test_subscription_routes_bind_to_account_and_session(self):
        token='browser-device-token'
        digest=hashlib.sha256(token.encode()).hexdigest()
        with start.connect() as db:
            db.execute('INSERT INTO sessions VALUES(?,?,?)',(digest,1,time.time()+3600))
        class Handler:
            path='/api/push/subscribe'
            def token(self): return token
            def reply(self,status,data): self.result=(status,data)
        handler=Handler()
        with patch('push_notify.configuration',return_value={'public_key':'public-test','private_key':'secret-test'}):
            with start.connect() as db:
                push_notify.routes(handler,db,{'id':1},{'subscription':self.sub},database=start.DATABASE)
            self.assertEqual(handler.result[0],200)
            handler.path='/api/push/status'
            with start.connect() as db:
                push_notify.routes(handler,db,{'id':2},{'endpoint':self.sub['endpoint']},database=start.DATABASE)
            self.assertFalse(handler.result[1]['registered'])
            handler.path='/api/push/config'
            with start.connect() as db:
                push_notify.routes(handler,db,{'id':1},database=start.DATABASE)
            self.assertNotIn('private_key',handler.result[1])
            handler.path='/api/push/unsubscribe'
            with start.connect() as db:
                push_notify.routes(handler,db,{'id':2},{'endpoint':self.sub['endpoint']},database=start.DATABASE)
                self.assertIsNotNone(db.execute('SELECT 1 FROM push_subscriptions WHERE user_id=1').fetchone())
            with start.connect() as db:
                db.execute('DELETE FROM sessions WHERE token=?',(digest,))
                self.assertIsNone(db.execute('SELECT 1 FROM push_subscriptions WHERE user_id=1').fetchone())

    @unittest.skipUnless(importlib.util.find_spec('pywebpush'),'Optional Web Push dependency not installed')
    def test_actual_signing_encryption_and_private_key_permissions(self):
        from push_setup import setup
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
        config=setup(Path(self.temp.name),'mailto:test@example.com')
        self.assertEqual((Path(self.temp.name)/'vapid-private.pem').stat().st_mode&0o777,0o600)
        with self.assertRaises(ValueError):
            setup(Path(self.temp.name),'mailto:test@example.com')
        key=ec.generate_private_key(ec.SECP256R1())
        public=key.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
        sub={**self.sub,'keys':{'p256dh':b64(public),'auth':b64(b'a'*16)}}
        with start.connect() as db:
            db.execute('UPDATE push_subscriptions SET subscription=?',(json.dumps(sub),))
        self.queue()
        captured=[]
        import requests
        def post(session,url,**kwargs):
            captured.append((url,kwargs))
            response=requests.Response()
            response.status_code=201
            return response
        with patch('requests.Session.post',post):
            push_notify.deliver_batch(start.connect,push_notify.configuration(start.DATABASE))
        self.assertEqual(len(captured),1)
        self.assertFalse(captured[0][1]['allow_redirects'])
        self.assertIn('authorization',{key.lower() for key in captured[0][1]['headers']})
        self.assertEqual(captured[0][1]['headers']['Urgency'], 'high')
        self.assertEqual(str(captured[0][1]['headers']['ttl']), '3600')
        self.assertNotIn(b'hello',captured[0][1]['data'])
        self.assertEqual(self.jobs(),0)


if __name__=='__main__':
    unittest.main()
