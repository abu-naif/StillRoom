"""Private friend requests and chat routes; attachments are SQLite BLOBs."""
import base64
import binascii
import re
import sqlite3
import time
from urllib.parse import urlsplit, parse_qs, quote

MAX_ATTACHMENT = 10 * 1024 * 1024
SCHEMA = '''
CREATE TABLE IF NOT EXISTS friendships (
 id INTEGER PRIMARY KEY, low_id INTEGER NOT NULL REFERENCES users(id),
 high_id INTEGER NOT NULL REFERENCES users(id), sender_id INTEGER NOT NULL REFERENCES users(id),
 status TEXT NOT NULL CHECK(status IN ('pending','accepted')), created REAL NOT NULL,
 UNIQUE(low_id,high_id), CHECK(low_id<high_id));
CREATE TABLE IF NOT EXISTS messages (
 id INTEGER PRIMARY KEY, sender_id INTEGER NOT NULL REFERENCES users(id),
 recipient_id INTEGER NOT NULL REFERENCES users(id), text TEXT NOT NULL,
 created REAL NOT NULL, client_id TEXT NOT NULL,
 filename TEXT, mime TEXT, size INTEGER, attachment BLOB,
 UNIQUE(sender_id,client_id), CHECK(sender_id<>recipient_id));
CREATE TABLE IF NOT EXISTS notification_settings (
 user_id INTEGER PRIMARY KEY REFERENCES users(id), enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)));
CREATE TABLE IF NOT EXISTS message_reads (
 user_id INTEGER NOT NULL REFERENCES users(id), peer_id INTEGER NOT NULL REFERENCES users(id),
 through_id INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(user_id,peer_id));
CREATE TABLE IF NOT EXISTS request_reads (
 user_id INTEGER NOT NULL REFERENCES users(id), request_id INTEGER NOT NULL REFERENCES friendships(id) ON DELETE CASCADE,
 PRIMARY KEY(user_id,request_id));
CREATE INDEX IF NOT EXISTS messages_inbox ON messages(recipient_id,sender_id,id);
CREATE INDEX IF NOT EXISTS messages_conversation ON messages(sender_id,recipient_id,id);
'''
COLUMNS = 'id,sender_id,recipient_id,text,created,filename,mime,size'


def friends(db, uid, peer):
    return db.execute("SELECT 1 FROM friendships WHERE low_id=? AND high_id=? AND status='accepted'", tuple(sorted((uid, peer)))).fetchone()


def positive(value):
    if isinstance(value, bool) or not str(value).isdigit() or not 0 < int(value) < 2**63:
        raise ValueError()
    return int(value)


def attachment(data):
    if data is None:
        return None, None, None
    if not isinstance(data, dict):
        raise ValueError()
    name, mime, encoded = data.get('name'), data.get('mime'), data.get('data')
    if not isinstance(name, str) or not 1 <= len(name) <= 200 or any(ord(c) < 32 for c in name) or '/' in name or '\\' in name:
        raise ValueError('Use a plain filename of up to 200 characters.')
    if not isinstance(mime, str) or not isinstance(encoded, str) or len(encoded) > (MAX_ATTACHMENT+2)//3*4:
        raise ValueError('Attachments must be at most 10 MB.')
    try:
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError('Invalid attachment encoding.')
    mime = mime.split(';')[0].lower()
    valid = {
        'application/pdf': content.startswith(b'%PDF-'),
        'image/png': content.startswith(b'\x89PNG\r\n\x1a\n'),
        'image/jpeg': content.startswith(b'\xff\xd8\xff'),
        'image/gif': content.startswith((b'GIF87a', b'GIF89a')),
        'image/webp': content.startswith(b'RIFF') and content[8:12] == b'WEBP',
        'audio/webm': content.startswith(b'\x1aE\xdf\xa3'),
        'audio/ogg': content.startswith(b'OggS'),
        'audio/mp4': content[4:8] == b'ftyp',
        'audio/wav': content.startswith(b'RIFF') and content[8:12] == b'WAVE',
        'audio/mpeg': content.startswith(b'ID3') or (len(content)>1 and content[0]==255 and content[1]&224==224),
    }
    if not content or len(content) > MAX_ATTACHMENT or not valid.get(mime):
        raise ValueError('Choose a valid PDF, PNG, JPEG, GIF, WebP, or supported audio file (up to 10 MB).')
    return name, mime, content


def get(handler, db, user):
    path = urlsplit(handler.path)
    uid = user['id']
    if path.path == '/api/notifications':
        setting = db.execute('SELECT enabled FROM notification_settings WHERE user_id=?', (uid,)).fetchone()
        requests = db.execute("""SELECT f.id,u.username FROM friendships f JOIN users u ON u.id=f.sender_id
            LEFT JOIN request_reads r ON r.request_id=f.id AND r.user_id=?
            WHERE (f.low_id=? OR f.high_id=?) AND f.sender_id<>? AND f.status='pending' AND r.request_id IS NULL
            ORDER BY f.created DESC""", (uid, uid, uid, uid)).fetchall()
        conversations = db.execute("""SELECT m.sender_id AS peer_id,u.username,COUNT(*) AS unread
            FROM messages m JOIN users u ON u.id=m.sender_id
            LEFT JOIN message_reads r ON r.user_id=m.recipient_id AND r.peer_id=m.sender_id
            WHERE m.recipient_id=? AND m.id>COALESCE(r.through_id,0)
            GROUP BY m.sender_id ORDER BY MAX(m.id) DESC""", (uid,)).fetchall()
        handler.reply(200, {'enabled': bool(setting['enabled']) if setting else True,
                            'requests': [dict(row) for row in requests],
                            'conversations': [dict(row) for row in conversations],
                            'total': len(requests)+sum(row['unread'] for row in conversations)})
    elif path.path == '/api/social':
        rows = db.execute('''SELECT f.id,f.sender_id,f.status,u.id AS peer_id,u.username
            FROM friendships f JOIN users u ON u.id=CASE WHEN f.low_id=? THEN f.high_id ELSE f.low_id END
            WHERE f.low_id=? OR f.high_id=? ORDER BY u.username''', (uid, uid, uid)).fetchall()
        handler.reply(200, [dict(row) for row in rows])
    elif path.path == '/api/messages':
        try:
            args = parse_qs(path.query)
            peer = positive(args.get('peer', [''])[0])
            before = positive(args['before'][0]) if 'before' in args else 2**63-1
            after = positive(args['after'][0]) if 'after' in args else 0
            if not friends(db, uid, peer):
                handler.reply(403, {'error': 'Accept a friend request before chatting.'})
            else:
                rows = db.execute(f'''SELECT {COLUMNS} FROM messages WHERE
                    ((sender_id=? AND recipient_id=?) OR (sender_id=? AND recipient_id=?))
                    AND id<? AND id>? ORDER BY id {'ASC' if after else 'DESC'} LIMIT 101''', (uid, peer, peer, uid, before, after)).fetchall()
                more = len(rows) > 100
                items = rows[:100]
                handler.reply(200, {'messages': [dict(r) for r in (items if after else reversed(items))], 'more': more})
        except (ValueError, IndexError):
            handler.reply(400, {'error': 'Invalid conversation.'})
    elif path.path.startswith('/api/attachments/'):
        try:
            mid = positive(path.path.removeprefix('/api/attachments/'))
        except ValueError:
            handler.reply(404, {'error': 'Attachment not found.'})
            return True
        row = db.execute('SELECT * FROM messages WHERE id=? AND (sender_id=? OR recipient_id=?)', (mid, uid, uid)).fetchone()
        if not row or row['attachment'] is None:
            handler.reply(404, {'error': 'Attachment not found.'})
        else:
            handler.send_response(200)
            handler.send_header('Content-Type', row['mime'])
            disposition = 'attachment' if row['mime'] == 'application/pdf' or 'download' in parse_qs(path.query) else 'inline'
            handler.send_header('Content-Disposition', f"{disposition}; filename*=UTF-8''{quote(row['filename'], safe='')}")
            handler.send_header('Cache-Control', 'no-store')
            handler.send_header('X-Content-Type-Options', 'nosniff')
            handler.send_header('Content-Security-Policy', "sandbox; default-src 'none'")
            handler.send_header('Content-Length', str(row['size']))
            handler.end_headers()
            handler.wfile.write(row['attachment'])
    else:
        return False
    return True


def post(handler, db, user, data):
    uid = user['id']
    if handler.path == '/api/notifications/settings':
        enabled = data.get('enabled')
        if not isinstance(enabled, bool):
            raise ValueError()
        db.execute('INSERT INTO notification_settings(user_id,enabled) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET enabled=excluded.enabled', (uid, int(enabled)))
        db.commit()
        handler.reply(200, {'enabled': enabled})
    elif handler.path == '/api/notifications/read-requests':
        ids = data.get('ids')
        if not isinstance(ids, list) or len(ids)>1000:
            raise ValueError()
        for rid in ids:
            rid = positive(rid)
            db.execute("""INSERT OR IGNORE INTO request_reads(user_id,request_id)
                SELECT ?,id FROM friendships WHERE id=? AND (low_id=? OR high_id=?) AND sender_id<>? AND status='pending'""", (uid, rid, uid, uid, uid))
        db.commit()
        handler.reply(200, {'ok': True})
    elif handler.path == '/api/messages/read':
        peer, through = positive(data.get('peer')), positive(data.get('through'))
        if not friends(db, uid, peer):
            handler.reply(403, {'error': 'Conversation not available.'})
        elif not db.execute('SELECT 1 FROM messages WHERE id=? AND ((sender_id=? AND recipient_id=?) OR (sender_id=? AND recipient_id=?))', (through, uid, peer, peer, uid)).fetchone():
            handler.reply(400, {'error': 'Message not found in this conversation.'})
        else:
            db.execute("""INSERT INTO message_reads(user_id,peer_id,through_id) VALUES(?,?,?)
                ON CONFLICT(user_id,peer_id) DO UPDATE SET through_id=MAX(message_reads.through_id,excluded.through_id)""", (uid, peer, through))
            db.commit()
            handler.reply(200, {'ok': True})
    elif handler.path == '/api/friends/request':
        name = data.get('username')
        if not isinstance(name, str):
            raise ValueError()
        peer = db.execute('SELECT id FROM users WHERE username=?', (name.strip().lower(),)).fetchone()
        if not peer:
            handler.reply(404, {'error': 'No account has that username on this Stillroom server.'})
        elif peer['id'] == uid:
            handler.reply(400, {'error': 'You cannot add yourself.'})
        else:
            low, high = sorted((uid, peer['id']))
            try:
                db.execute("INSERT INTO friendships(low_id,high_id,sender_id,status,created) VALUES(?,?,?,'pending',?)", (low, high, uid, time.time()))
                db.commit()
                handler.reply(200, {'ok': True})
            except sqlite3.IntegrityError:
                handler.reply(409, {'error': 'You are already friends or have a pending request. Check your requests.'})
    elif handler.path == '/api/friends/respond':
        request_id, action = positive(data.get('request_id')), data.get('action')
        row = db.execute('SELECT * FROM friendships WHERE id=? AND (low_id=? OR high_id=?)', (request_id, uid, uid)).fetchone()
        if not row or row['status'] != 'pending':
            handler.reply(404, {'error': 'Pending request not found.'})
        elif action not in ('accept', 'decline', 'cancel') or (action == 'cancel') != (row['sender_id'] == uid):
            handler.reply(403, {'error': 'Only the recipient can accept or decline; only the sender can cancel.'})
        else:
            if action == 'accept':
                db.execute("UPDATE friendships SET status='accepted' WHERE id=?", (request_id,))
            else:
                db.execute('DELETE FROM friendships WHERE id=?', (request_id,))
            db.commit()
            handler.reply(200, {'ok': True})
    elif handler.path == '/api/messages/send':
        peer = positive(data.get('peer'))
        if not friends(db, uid, peer):
            handler.reply(403, {'error': 'Accept a friend request before chatting.'})
            return True
        text, client_id = data.get('text', ''), data.get('client_id')
        if not isinstance(text, str) or len(text) > 10000 or not isinstance(client_id, str) or not re.fullmatch(r'[a-zA-Z0-9-]{16,80}', client_id):
            raise ValueError()
        # A retry of the same send returns the existing message instead of duplicating it.
        existing = db.execute(f'SELECT {COLUMNS} FROM messages WHERE sender_id=? AND client_id=?', (uid, client_id)).fetchone()
        if existing:
            if existing['recipient_id'] != peer:
                raise ValueError()
            handler.reply(200, dict(existing))
            return True
        name, mime, content = attachment(data.get('attachment'))
        if not text.strip() and content is None:
            handler.reply(400, {'error': 'Write a message or attach a file.'})
            return True
        mid = db.execute('''INSERT INTO messages(sender_id,recipient_id,text,created,client_id,filename,mime,size,attachment)
            VALUES(?,?,?,?,?,?,?,?,?)''', (uid, peer, text, time.time(), client_id, name, mime, len(content) if content else None, content)).lastrowid
        db.commit()
        handler.reply(200, dict(db.execute(f'SELECT {COLUMNS} FROM messages WHERE id=?', (mid,)).fetchone()))
    else:
        return False
    return True
