"""Opt-in Web Push, with per-account and per-friend checks at delivery and display."""
import base64
import hashlib
import json
import re
import secrets
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

SCHEMA = '''
CREATE TABLE IF NOT EXISTS push_subscriptions (
 endpoint TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
 session_token TEXT NOT NULL REFERENCES sessions(token) ON DELETE CASCADE,
 subscription TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS push_events (
 token TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),actor_id INTEGER NOT NULL REFERENCES users(id),
 kind TEXT NOT NULL,reference_id INTEGER NOT NULL,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS push_jobs (
 id INTEGER PRIMARY KEY,event_token TEXT NOT NULL REFERENCES push_events(token) ON DELETE CASCADE,
 endpoint TEXT NOT NULL REFERENCES push_subscriptions(endpoint) ON DELETE CASCADE,
 attempts INTEGER NOT NULL DEFAULT 0,next_attempt REAL NOT NULL DEFAULT 0);
'''


def initialize(db):
    db.executescript(SCHEMA)


def configuration(database):
    try:
        import pywebpush  # noqa: F401
        config = json.loads((Path(database).parent/'webpush.json').read_text())
        if not config.get('public_key') or not config.get('contact'):
            return None
        config['private_key'] = str(Path(database).parent/config['private_file'])
        if not Path(config['private_key']).is_file():
            return None
        return config
    except (ImportError,OSError,ValueError,KeyError):
        return None


def validate_subscription(value):
    if not isinstance(value,dict):
        raise ValueError()
    endpoint, keys = value.get('endpoint'), value.get('keys')
    if not isinstance(endpoint,str) or len(endpoint)>4096 or not isinstance(keys,dict):
        raise ValueError()
    url = urlsplit(endpoint)
    host = url.hostname or ''
    # Browser-operated services only: never let a subscriber turn push into arbitrary server-side requests.
    allowed = host in ('fcm.googleapis.com','updates.push.services.mozilla.com','push.services.mozilla.com','web.push.apple.com') or host.endswith('.push.apple.com') or host.endswith('.notify.windows.com')
    if url.scheme!='https' or not allowed or url.username or url.password or url.port not in (None,443) or url.fragment:
        raise ValueError('Unsupported push service.')
    cleaned = {}
    for name,length in [('p256dh',65),('auth',16)]:
        text = keys.get(name)
        if not isinstance(text,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}={0,2}',text):
            raise ValueError()
        decoded = base64.urlsafe_b64decode(text+'='*(-len(text)%4))
        if len(decoded)!=length or (name=='p256dh' and decoded[0]!=4):
            raise ValueError()
        cleaned[name] = text
    return {'endpoint':endpoint,'keys':cleaned}


def allowed(db,event):
    if time.time()-event['created']>3600:
        return False
    uid,actor = event['user_id'],event['actor_id']
    setting = db.execute('SELECT enabled FROM notification_settings WHERE user_id=?',(uid,)).fetchone()
    if setting and not setting['enabled']:
        return False
    if db.execute('SELECT 1 FROM friend_mutes WHERE user_id=? AND peer_id=?',(uid,actor)).fetchone():
        return False
    if event['kind']=='message':
        return bool(db.execute('''SELECT 1 FROM messages m LEFT JOIN message_reads r ON r.user_id=m.recipient_id AND r.peer_id=m.sender_id
            WHERE m.id=? AND m.recipient_id=? AND m.sender_id=? AND m.deleted=0 AND m.id>COALESCE(r.through_id,0)''',(event['reference_id'],uid,actor)).fetchone())
    return bool(db.execute("""SELECT 1 FROM friendships f LEFT JOIN request_reads r ON r.request_id=f.id AND r.user_id=?
        WHERE f.id=? AND (f.low_id=? OR f.high_id=?) AND f.sender_id=? AND f.status='pending' AND r.request_id IS NULL""",(uid,event['reference_id'],uid,uid,actor)).fetchone())


def enqueue(db,uid,actor,kind,reference):
    event={'user_id':uid,'actor_id':actor,'kind':kind,'reference_id':reference,'created':time.time()}
    if not allowed(db,event):
        return
    subscriptions=db.execute('''SELECT p.endpoint FROM push_subscriptions p JOIN sessions s ON s.token=p.session_token
        WHERE p.user_id=? AND s.expires>?''',(uid,time.time())).fetchall()
    if not subscriptions:
        return
    token=secrets.token_urlsafe(24)
    db.execute('INSERT INTO push_events VALUES(?,?,?,?,?,?)',(token,uid,actor,kind,reference,event['created']))
    db.executemany('INSERT INTO push_jobs(event_token,endpoint) VALUES(?,?)',[(token,row['endpoint']) for row in subscriptions])


def routes(handler,db,user,data=None,database=None):
    path=urlsplit(handler.path)
    if not path.path.startswith('/api/push/'):
        return False
    uid=user['id']
    config=configuration(database)
    if path.path=='/api/push/config' and data is None:
        handler.reply(200,{'configured':bool(config),'publicKey':config['public_key'] if config else None})
    elif path.path=='/api/push/check' and data is None:
        token=parse_qs(path.query).get('token',[''])[0]
        event=db.execute('SELECT * FROM push_events WHERE token=? AND user_id=?',(token,uid)).fetchone()
        if not event or not allowed(db,event):
            handler.reply(200,{'allowed':False})
        else:
            actor=db.execute('SELECT username FROM users WHERE id=?',(event['actor_id'],)).fetchone()
            handler.reply(200,{'allowed':True,'title':'Stillroom','body':f"{actor['username']} sent you "+('a friend request.' if event['kind']=='request' else 'a message.'),
                               'peer':event['actor_id'] if event['kind']=='message' else None,'tag':f"stillroom-{event['kind']}-{event['actor_id']}"})
    elif path.path=='/api/push/subscribe' and data is not None:
        if not config:
            handler.reply(503,{'error':'Device notifications need server setup. See the Web Push instructions in README.'})
        else:
            sub=validate_subscription(data.get('subscription'))
            token=hashlib.sha256(handler.token().encode()).hexdigest()
            if not db.execute('SELECT 1 FROM push_subscriptions WHERE endpoint=?',(sub['endpoint'],)).fetchone() and db.execute('SELECT COUNT(*) FROM push_subscriptions WHERE user_id=?',(uid,)).fetchone()[0]>=10:
                handler.reply(400,{'error':'This account already has 10 notification devices. Turn off an old device first.'})
                return True
            db.execute('DELETE FROM push_jobs WHERE endpoint=?',(sub['endpoint'],))
            db.execute('''INSERT INTO push_subscriptions VALUES(?,?,?,?,?) ON CONFLICT(endpoint) DO UPDATE SET
                user_id=excluded.user_id,session_token=excluded.session_token,subscription=excluded.subscription,created=excluded.created''',
                (sub['endpoint'],uid,token,json.dumps(sub),time.time()))
            db.commit()
            handler.reply(200,{'ok':True})
    elif path.path in ('/api/push/status','/api/push/unsubscribe') and data is not None:
        endpoint=data.get('endpoint')
        if not isinstance(endpoint,str) or len(endpoint)>4096:
            raise ValueError()
        token=hashlib.sha256(handler.token().encode()).hexdigest()
        row=db.execute('SELECT 1 FROM push_subscriptions WHERE endpoint=? AND user_id=? AND session_token=?',(endpoint,uid,token)).fetchone()
        if path.path.endswith('/unsubscribe'):
            db.execute('DELETE FROM push_subscriptions WHERE endpoint=? AND user_id=?',(endpoint,uid))
            db.commit()
        handler.reply(200,{'registered':bool(row) if path.path.endswith('/status') else False})
    else:
        handler.reply(404,{'error':'Not found.'})
    return True


def deliver_batch(connect,config,send=None):
    if send is None:
        from pywebpush import webpush
        import requests
        class NoRedirectSession(requests.Session):
            def post(self,*args,**kwargs):
                kwargs['allow_redirects']=False
                return super().post(*args,**kwargs)
        session=NoRedirectSession()
        def send(subscription,payload):
            return webpush(subscription_info=subscription,data=json.dumps(payload),vapid_private_key=config['private_key'],
                           vapid_claims={'sub':config['contact']},ttl=300,timeout=10,requests_session=session)
    else:
        session=None
    try:
        with connect() as db:
            db.execute('DELETE FROM push_events WHERE created<?',(time.time()-3600,))
            jobs=db.execute('SELECT id FROM push_jobs WHERE next_attempt<=? ORDER BY id LIMIT 20',(time.time(),)).fetchall()
        for item in jobs:
            with connect() as db:
                row=db.execute('''SELECT j.id AS job_id,j.attempts,p.subscription,s.expires,e.* FROM push_jobs j
                    JOIN push_subscriptions p ON p.endpoint=j.endpoint JOIN sessions s ON s.token=p.session_token
                    JOIN push_events e ON e.token=j.event_token WHERE j.id=?''',(item['id'],)).fetchone()
                if not row:
                    continue
                if row['expires']<=time.time() or not allowed(db,row):
                    db.execute('DELETE FROM push_jobs WHERE id=?',(row['job_id'],))
                    continue
                subscription=json.loads(row['subscription'])
            try:
                send(subscription,{'event':row['token']})
                with connect() as db:
                    db.execute('DELETE FROM push_jobs WHERE id=?',(row['job_id'],))
            except Exception as error:
                status=getattr(getattr(error,'response',None),'status_code',None)
                with connect() as db:
                    if status in (404,410):
                        db.execute('DELETE FROM push_subscriptions WHERE endpoint=?',(subscription['endpoint'],))
                    elif row['attempts']>=3:
                        db.execute('DELETE FROM push_jobs WHERE id=?',(row['job_id'],))
                    else:
                        db.execute('UPDATE push_jobs SET attempts=attempts+1,next_attempt=? WHERE id=?',(time.time()+30*2**row['attempts'],row['job_id']))
    finally:
        if session:
            session.close()


def start_worker(connect,database):
    config=configuration(database)
    stop=threading.Event()
    if not config:
        print('Background notifications are disabled: install requirements.txt and run push_setup.py --contact YOUR_HTTPS_ORIGIN using the server Python environment. See README.md.')
    if config:
        def run():
            while not stop.is_set():
                try:
                    deliver_batch(connect,config)
                except Exception:
                    # Never log subscription endpoints, credentials or message data.
                    print('Push delivery unavailable; pending notifications will be retried.')
                stop.wait(2)
        threading.Thread(target=run,name='stillroom-push',daemon=True).start()
    return stop
