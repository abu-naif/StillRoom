# Stillroom — PC edition

A quiet YouTube and Google Drive video viewer with local accounts, private notes per video, viewing history, cinema mode, and light/dark themes. Python 3 runs the server and SQLite database; no API keys or cloud hosting are required.

## Run

Open a terminal in this folder and run:

```sh
python3 start.py
```

On Windows, use `py start.py`. Open **http://127.0.0.1:8765/** if the browser doesn't open automatically. Keep the terminal running; Ctrl+C stops the server. After updating the app, stop any old server and run this command again, then refresh the browser.

## Accounts and notes

Choose **Create an account**, enter a username (3–40 letters, numbers, dots, underscores or dashes) and a password of at least 10 characters. Users must sign in before using the video workspace. Accounts belong to this local installation; there is no email verification, password recovery, or cross-device cloud sync.

Each account has separate notes, history, and playback positions. Notes save automatically to SQLite, with a save button for retrying and a download button for text exports. Save failures appear on screen; switching videos and signing out retry unsaved notes before continuing. Theme preferences remain in browser storage.

Notes from the earlier version remain in browser storage. While signed in, load the relevant video and choose **Import old browser notes** when the account's notes are empty. This copies those notes into the current account without automatically assigning shared browser data to anyone.

## Videos and history

Paste a YouTube URL, youtu.be link, Shorts/live link, video ID, or Google Drive video file sharing link. Drive `/file/d/…/view`, preview links, and `/open?id=…` or `/uc?id=…` links are supported, including resource keys. Folder links are not supported.

**History** lists videos opened by your account, most recent first. Choose a video to reopen its notes and saved progress. YouTube titles appear after playback starts; otherwise entries show the provider and file/video ID.

YouTube progress saves about every five seconds, on player state changes, and when leaving the page. Reopening a video resumes near the saved point; completed videos start again from the beginning. An abrupt browser shutdown or failed connection can lose the last few seconds. Timestamp links set the initial starting point when no saved progress exists.

**Google Drive's embedded preview does not expose a supported playback tracking/seeking API to this app.** Automatic resume is therefore available for YouTube only. For Drive, use **Remember timestamp → Save bookmark**. History retains that timestamp; seek to it manually in the Drive player after reopening.

Drive files require viewing permission. Restricted files may need sign-in through **open in Google Drive**. Processing, cookie settings, or owner restrictions can affect embedded playback. YouTube may show ads, branding, and related videos, and owners can disable embedding. Internet access is required for either provider.

## Database and privacy

The database is created automatically at `data/stillroom.sqlite3`. It stores account records, hashed passwords, sessions, notes, history, and progress. Passwords use salted scrypt hashing; session cookies are HttpOnly and SameSite=Strict. Account APIs require an active session, and the server does not serve the database or source files over HTTP.

Back up the `data` folder while the server is stopped to preserve accounts and notes. Clearing browser storage does not delete database notes. The server listens only on `127.0.0.1`; this is a local PC application, not a public hosting setup. Anyone with filesystem access to the database can read its notes and history. The app has no analytics. Loading videos connects your browser to the chosen provider.

## Development

- `start.py` — local server, accounts, sessions, SQLite API
- `src/App.tsx` — account UI, link parsing, notes and history
- `src/Player.tsx` — YouTube player integration and Drive preview
- `styles.css` — styling
- `app.js` — prebuilt application, ready to run
- `tests/` — parser and API integration tests

To rebuild after editing React source:

```sh
npm install
npm run build
npm test
python3 -m unittest discover -s tests -p 'test_*.py'
```

No npm installation is needed for normal use.
