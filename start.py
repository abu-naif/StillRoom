"""Stillroom accounts and SQLite API, with optional Web Push delivery."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from contextlib import contextmanager
from pathlib import Path
import argparse
import ssl
from urllib.parse import urlsplit
import hashlib
import hmac
import json
import math
import re
import secrets
import sqlite3
import time
import webbrowser
import chat
import push_notify

ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / 'data' / 'stillroom.sqlite3'
PUBLIC_FILES = {'/', '/index.html', '/app.js', '/app.js.LEGAL.txt', '/styles.css', '/favicon.svg',
                '/manifest.webmanifest', '/sw.js', '/icons/icon-192.png', '/icons/icon-512.png', '/icons/apple-touch-icon.png'}


@contextmanager
def connect():
    db = sqlite3.connect(DATABASE, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize():
    DATABASE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE,
            salt TEXT NOT NULL, password TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS videos (
            user_id INTEGER NOT NULL REFERENCES users(id), provider TEXT NOT NULL, id TEXT NOT NULL,
            resourceKey TEXT, notes TEXT NOT NULL DEFAULT '', position REAL NOT NULL DEFAULT 0,
            title TEXT NOT NULL DEFAULT '', lastViewed REAL NOT NULL,
            PRIMARY KEY(user_id, provider, id));
        CREATE TABLE IF NOT EXISTS login_attempts (client TEXT PRIMARY KEY, count INTEGER NOT NULL, until REAL NOT NULL);
        ''')
        chat.initialize(db)
    DATABASE.chmod(0o600)


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        if self.path.split('?')[0] in PUBLIC_FILES:
            self.send_header('Cache-Control', 'no-cache, must-revalidate')
        super().end_headers()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def reply(self, status, value, cookie=None):
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if cookie:
            if getattr(self.server, 'public_origin', '').startswith('https://'):
                cookie += '; Secure'
            self.send_header('Set-Cookie', cookie)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def token(self):
        try:
            cookie = SimpleCookie(self.headers.get('Cookie', ''))
            return cookie['stillroom_session'].value if 'stillroom_session' in cookie else ''
        except Exception:
            return ''

    def user(self, db):
        return db.execute('SELECT users.id, username FROM sessions JOIN users ON users.id=sessions.user_id WHERE token=? AND expires>?',
                          (hashlib.sha256(self.token().encode()).hexdigest(), time.time())).fetchone()

    def do_GET(self):
        if self.path.startswith('/api/'):
            with connect() as db:
                user = self.user(db)
                if not user:
                    return self.reply(401, {'error': 'Please sign in.'})
                if push_notify.routes(self,db,user,database=DATABASE):
                    return
                if chat.get(self, db, user):
                    return
                if self.path == '/api/me':
                    return self.reply(200, dict(user))
                if self.path == '/api/history':
                    rows = db.execute('SELECT * FROM videos WHERE user_id=? ORDER BY lastViewed DESC', (user['id'],)).fetchall()
                    return self.reply(200, [dict(row) for row in rows])
            return self.reply(404, {'error': 'Not found.'})
        # Never expose the database, source, dotfiles, or directory listings.
        if self.path.split('?')[0] not in PUBLIC_FILES:
            return self.reply(404, {'error': 'Not found.'})
        return super().do_GET()

    def do_HEAD(self):
        if self.path.split('?')[0] not in PUBLIC_FILES:
            return self.reply(404, {'error': 'Not found.'})
        return super().do_HEAD()

    def do_POST(self):
        expected = getattr(self.server, 'public_origin', f'http://127.0.0.1:{self.server.server_port}')
        if self.headers.get('X-Stillroom') != '1' or self.headers.get('Origin', expected) != expected:
            return self.reply(403, {'error': 'Use the Stillroom page at its configured address.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            limit = 14 * 1024 * 1024 if self.path == '/api/messages/send' else 120000
            if not 0 < length <= limit:
                return self.reply(400, {'error': 'Request is too large or empty.'})
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError()
            with connect() as db:
                if self.path in ('/api/register', '/api/login'):
                    username = data.get('username', '').strip().lower()
                    password = data.get('password', '')
                    if not re.fullmatch(r'[a-z0-9_.-]{3,40}', username) or not isinstance(password, str) or not 10 <= len(password) <= 200:
                        return self.reply(400, {'error': 'Use a username of 3–40 letters, numbers, dots, underscores or dashes, and a password of 10–200 characters.'})
                    client = self.client_address[0]
                    attempt = db.execute('SELECT * FROM login_attempts WHERE client=? AND until>?', (client, time.time())).fetchone()
                    if attempt and attempt['count'] >= 10:
                        return self.reply(429, {'error': 'Too many attempts. Try again in 15 minutes.'})
                    row = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
                    if self.path == '/api/register':
                        if row:
                            return self.reply(409, {'error': 'This username is already taken.'})
                        salt = secrets.token_hex(16)
                        uid = db.execute('INSERT INTO users(username,salt,password) VALUES(?,?,?)', (username, salt, password_hash(password, salt))).lastrowid
                    else:
                        candidate = password_hash(password, row['salt'] if row else '00'*16)
                        if not row or not hmac.compare_digest(candidate, row['password']):
                            db.execute('INSERT INTO login_attempts VALUES(?,?,?) ON CONFLICT(client) DO UPDATE SET count=?, until=?',
                                       (client, 1, time.time()+900, (attempt['count'] if attempt else 0)+1, time.time()+900))
                            db.commit()
                            return self.reply(401, {'error': 'Incorrect username or password.'})
                        uid = row['id']
                    db.execute('DELETE FROM login_attempts WHERE client=?', (client,))
                    token = secrets.token_urlsafe(32)
                    db.execute('DELETE FROM sessions WHERE expires<?', (time.time(),))
                    db.execute('INSERT INTO sessions VALUES(?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), uid, time.time()+30*86400))
                    db.commit()
                    return self.reply(200, {'id': uid, 'username': username}, f'stillroom_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=2592000')
                user = self.user(db)
                if not user:
                    return self.reply(401, {'error': 'Please sign in.'})
                if push_notify.routes(self,db,user,data,database=DATABASE):
                    return
                if chat.post(self, db, user, data):
                    return
                if self.path == '/api/logout':
                    db.execute('DELETE FROM sessions WHERE token=?', (hashlib.sha256(self.token().encode()).hexdigest(),))
                    db.commit()
                    return self.reply(200, {'ok': True}, 'stillroom_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
                if self.path not in ('/api/watch', '/api/save'):
                    return self.reply(404, {'error': 'Not found.'})
                provider, vid = data.get('provider'), data.get('id')
                if provider not in ('youtube', 'drive') or not isinstance(vid, str) or not re.fullmatch(r'[\w-]{1,200}', vid, re.ASCII) or (provider == 'youtube' and len(vid) != 11):
                    raise ValueError()
                key = (user['id'], provider, vid)
                if self.path == '/api/watch':
                    resource = data.get('resourceKey')
                    if resource is not None and (not isinstance(resource, str) or len(resource) > 500):
                        raise ValueError()
                    db.execute('INSERT INTO videos(user_id,provider,id,resourceKey,lastViewed) VALUES(?,?,?,?,?) ON CONFLICT(user_id,provider,id) DO UPDATE SET lastViewed=excluded.lastViewed, resourceKey=COALESCE(excluded.resourceKey,videos.resourceKey)', (*key, resource, time.time()))
                else:
                    row = db.execute('SELECT * FROM videos WHERE user_id=? AND provider=? AND id=?', key).fetchone()
                    if not row:
                        return self.reply(404, {'error': 'Load the video first.'})
                    for field in ('notes', 'position', 'title'):
                        if field not in data:
                            continue
                        value = data[field]
                        if field == 'position':
                            if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 604800:
                                raise ValueError()
                        elif not isinstance(value, str) or len(value) > (100000 if field == 'notes' else 300):
                            raise ValueError()
                        db.execute(f'UPDATE videos SET {field}=? WHERE user_id=? AND provider=? AND id=?', (value, *key))
                row = db.execute('SELECT * FROM videos WHERE user_id=? AND provider=? AND id=?', key).fetchone()
                db.commit()
                return self.reply(200, dict(row))
        except (ValueError, TypeError, AttributeError):
            return self.reply(400, {'error': 'Invalid request.'})
        except sqlite3.Error:
            return self.reply(500, {'error': 'Could not save to the database. Please try again.'})


def main():
    parser = argparse.ArgumentParser(description='Run Stillroom locally, or at an explicitly configured HTTPS address.')
    parser.add_argument('--host', default='127.0.0.1', help='Bind address (default: this PC only)')
    parser.add_argument('--port', default=8765, type=int)
    parser.add_argument('--origin', help='Canonical HTTPS origin for phone access or a reverse proxy')
    parser.add_argument('--cert', help='TLS certificate PEM file trusted by client devices')
    parser.add_argument('--key', help='TLS private key PEM file')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    if bool(args.cert) != bool(args.key):
        parser.error('Supply both --cert and --key.')
    if args.host not in ('127.0.0.1', 'localhost') and not (args.cert and args.origin):
        parser.error('Phone/network access requires --cert, --key and an explicit HTTPS --origin.')
    url = (args.origin or f"{'https' if args.cert else 'http'}://127.0.0.1:{args.port}").rstrip('/')
    origin = urlsplit(url)
    if not origin.hostname or origin.username or origin.password or origin.path or origin.query or origin.fragment or origin.scheme not in ('http','https'):
        parser.error('--origin must be an origin such as https://stillroom.example.com, without a path.')
    if (args.origin or args.cert) and origin.scheme != 'https':
        parser.error('Configured network origins must use HTTPS.')
    if not 1 <= args.port <= 65535:
        parser.error('Port must be between 1 and 65535.')
    initialize()
    try:
        server = ThreadingHTTPServer((args.host, args.port), Handler)
        server.public_origin = url
        if args.cert:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(args.cert, args.key)
            server.socket = context.wrap_socket(server.socket, server_side=True)
    except (OSError, ssl.SSLError) as error:
        raise SystemExit(f'Could not start Stillroom: {error}\nClose any previous Stillroom server using Ctrl+C, then try again.')
    url += '/'
    if origin.scheme == 'https' and not (DATABASE.parent/'webpush.json').exists() and not (DATABASE.parent/'vapid-private.pem').exists():
        try:
            import pywebpush  # Check delivery support before creating persistent signing keys.
            from push_setup import setup
            setup(DATABASE.parent, url.rstrip('/'))
            print('Web Push signing keys created privately. Allow notifications on each device.')
        except (ImportError, OSError, ValueError):
            print('Web Push setup could not complete. See the server setup instructions in README.md.')
    push_stop=push_notify.start_worker(connect,DATABASE)
    print(f'Stillroom is ready: {url}\nKeep this terminal open. Press Ctrl+C to stop.')
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStillroom stopped.')
    finally:
        push_stop.set()
        server.server_close()


if __name__ == '__main__':
    main()
