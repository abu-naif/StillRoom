"""Start Stillroom locally. Python 3 standard library only."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import webbrowser

root = Path(__file__).resolve().parent
handler = partial(SimpleHTTPRequestHandler, directory=str(root))
# A stable origin keeps browser notes and theme available across launches.
try:
    server = ThreadingHTTPServer(('127.0.0.1', 8765), handler)
except OSError as error:
    raise SystemExit(f'Could not start Stillroom: {error}\nClose any previous Stillroom server using Ctrl+C, then try again.')
url = 'http://127.0.0.1:8765/'
print(f'Stillroom is ready: {url}\nKeep this terminal open. Press Ctrl+C to stop.')
webbrowser.open(url)
try:
    server.serve_forever()
except KeyboardInterrupt:
    print('\nStillroom stopped.')
finally:
    server.server_close()
