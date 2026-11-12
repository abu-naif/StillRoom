# Stillroom — PC edition

A quiet YouTube and Google Drive video viewer with local accounts, private notes per video, viewing history, friend requests, private chats, cinema mode, and light/dark themes. Python 3 runs the server and SQLite database; local use needs no paid API keys or cloud hosting. Optional device notifications use the Web Push setup below.

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

Drive tries direct playback, automatically saving progress about every five seconds, on pause, and when leaving. Returning offers **Continue from where I left** or **Start from beginning**. Files that block direct playback fall back to Drive preview, which does not expose playback time or seeking to the app. For those files, use **Remember timestamp → Save bookmark** and seek manually.

Username entry suggests up to ten matching accounts on this server. On PC, the conversation header has a three-dot menu for mute and **Delete conversation**; touch users can hold a friend in the sidebar. Deleting a conversation clears its existing history from your account only, after confirmation. Your friend keeps their copy, and future messages still appear.

Drive files require viewing permission. Restricted files may need sign-in through **open in Google Drive**. Processing, cookie settings, or owner restrictions can affect embedded playback. YouTube may show ads, branding, and related videos, and owners can disable embedding. Internet access is required for either provider.

## Friends and messages

Use **Watch**, **Messages**, and **History** in the header to switch pages. The Messages page contains only messaging; the video link field, player, and notes stay on Watch. Switching pages saves progress and stops video playback.

Open **Messages** in the header. Enter an existing account's username to send a friend request. The recipient can accept or decline it; the sender can cancel a pending request. Texting and attachments are available only after acceptance.

Choose a friend to open a conversation. Text supports Unicode emoji. Desktop users have a smile button for the emoji picker; phones and touch devices use their keyboard’s emoji controls instead. New messages appear automatically (about every two seconds while the app is open). Older messages are available with **Load older messages**. Switching conversations or hiding Messages preserves unsent drafts while signed in; signing out or reloading clears drafts.

The paperclip sits to the left of the text field; on phones it hides while text is entered and returns when the field is cleared. It attaches one file per message, up to **10 MB**: PDF, PNG, JPEG, GIF, WebP, or audio (WebM, Ogg, MP4/M4A, WAV, MP3). Review the attachment before pressing **Send**. Pictures display inline, audio displays as a voice bubble with play/pause, a seek bar, duration, and 1×/1.5×/2× playback speed instead of a filename, and PDFs have a download link. File contents are checked against the selected media type; SVG and HTML are not supported.

The action button shows a microphone when the draft is empty, switches to Send when text or an attachment is present, and shows Stop during recording. Tap the microphone to record, then Stop to preview the voice message and Send to deliver it. New recordings include a saved duration so their timer is available before playback. Existing databases are extended automatically on server restart without replacing chats or files. Recordings stop automatically after two minutes; closing Messages stops recording and keeps its preview. Microphone access requires browser permission and a browser that supports recording. You can attach an existing audio file if recording is unavailable.

Messages and the actual PDF, image, and audio **bytes are stored in SQLite**, not an external file host. Only the sender and recipient can retrieve a message's attachment through the app. Chat messages are not end-to-end encrypted; someone with filesystem access to the database can read them. Attachments increase database size, so keep backups of the `data` folder.

This remains a **local PC app**. Both accounts must exist on the same Stillroom server. To try two accounts at once, use a regular browser window and a private window (or separate browser profiles). Separate PCs running their own copies do not share accounts or messages. Publishing the repository to GitHub does not create a shared messaging server.

## Edit and delete messages

Press and hold one of your own messages on a phone, or right-click it on PC, to open its menu. Keyboard users can focus an outgoing bubble and press Shift+F10. Choose **Edit text**, save the replacement, or choose **Delete message** and confirm. You can edit only your own nonempty text; only the sender can delete a message. A deleted message becomes a placeholder for both participants and its current text/attachment bytes are cleared from the message row. Backups may retain earlier content.

Edits show an “edited” label and sync to the other inbox through normal polling. Existing drafts are preserved while editing. Sending keeps the composer editable and preserves a new draft typed while a request is pending.

## Notifications and quiet mode

The bell and Messages tab show a red count for new incoming friend requests and unread messages, with unread counts beside the relevant friends. Notifications update about every three seconds while Stillroom is open. Viewing requests marks them seen; viewing the latest messages in a visible conversation marks them read. Background polling and hidden conversations do not mark messages read.

Open the **bell → Notifications** switch to turn notifications on or off. Turning them off enables **Quiet mode**: no red dots, counts, sounds, device pop-ups, or notification items. You can still open chats and respond whenever you want. This preference is stored per account in SQLite and applies across browsers connected to that same server. Unread state is retained while muted, so unread items can appear again if notifications are reenabled.

### Device notifications (Android, iPhone and desktop)

After the server setup below, open the bell panel and choose **Allow on this device**. Browser permission is requested only when you tap that button. The main Notifications switch must be on. You can turn off a single device with **Turn off on this device** without changing your account-wide setting.

- **Android:** use an up-to-date browser with notifications allowed for the site. An installed Home Screen app is also supported.
- **iPhone/iPad:** iOS/iPadOS 16.4 or later is required. Add Stillroom to the Home Screen, open it from that icon, then tap Allow on this device. See [Apple/WebKit's Web Push requirements](https://webkit.org/blog/13878/).
- Serve the app over **HTTPS**. The server must stay online and be reachable by the phone. With private Tailscale hosting, the phone must remain connected to the Tailscale network so the background app can verify current notification preferences.
- Browser permissions, OS notification settings, Focus/Do Not Disturb, battery policies and network availability can delay or suppress delivery. This is Web Push, not a native WhatsApp/Messenger integration.

Notifications contain a sender name and a generic message/request alert; message contents and attachments are not included in the push payload. The server checks quiet mode and per-friend mute before enqueueing and delivery. The service worker checks them again before displaying an alert, and fails closed if it cannot verify the current account/settings. Read or deleted messages are not notified. Logging out disconnects subscriptions associated with that sign-in session. There is a maximum of 10 notification devices per account.

### One-time Ubuntu server setup for Web Push

Run in the deployed project directory:

```sh
sudo apt install python3-venv
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python push_setup.py --contact https://YOUR-STILLROOM-HTTPS-ADDRESS
```

Replace the contact with your real HTTPS address, or use `mailto:you@example.com`. This creates persistent VAPID signing keys in the ignored `data` folder; it never overwrites existing keys. Alternatively, after installing dependencies, starting `.venv/bin/python start.py --origin https://YOUR-STILLROOM-HTTPS-ADDRESS --no-browser` creates missing keys automatically using that HTTPS origin as the contact. Existing or incomplete key files are never replaced automatically. Keep these keys private and back them up with the database. They must remain the same across deployments for existing device subscriptions to work.

If using the systemd service from the hosting guide, change its `ExecStart` to the virtual environment's Python, keeping your actual username and origin:

```ini
ExecStart=/home/YOUR_USER/stillroom-pc/.venv/bin/python -u /home/YOUR_USER/stillroom-pc/start.py --origin https://YOUR-STILLROOM-HTTPS-ADDRESS --no-browser
```

Then apply the service change:

```sh
sudo systemctl daemon-reload
sudo systemctl restart stillroom
```

For a manual launch, use `.venv/bin/python start.py --origin https://YOUR-STILLROOM-HTTPS-ADDRESS --no-browser`.

The server starts a background worker automatically when the dependency and keys are available. Start it with the virtual environment's Python; installing dependencies there does not add them to the system Python. Message pushes use high urgency and a one-hour lifetime so the provider can attempt prompt delivery to idle devices and retain alerts through brief disconnections. Pending jobs are stored in SQLite and retried on temporary provider failures; expired subscriptions are removed. No paid notification service is needed. Tests validate encryption/signing and mock-provider delivery; actual phone delivery must be checked after deployment and device permission.

### Mute an individual friend

Press and hold a friend's row in the Messages friends list, or right-click it on PC. Choose **Mute notifications** or **Unmute notifications**. Muting is private to your account and suppresses that friend's message badges and device alerts; their messages still arrive in the inbox. Other friends remain unaffected.

## Mobile and installation

The interface adapts to small screens. On Messages, phones show the friends list first; selecting a friend opens a full-screen conversation with an initials avatar and username, and hides the main navigation. Use the **back arrow** to return to the list and restore navigation. Message bubbles use compact spacing, and the text field starts at one line and grows to a limited height. Send sits beside the text field. The inbox follows the visible viewport when the on-screen keyboard opens or pans the page, keeping Send above the keyboard, with safe-area space for phone notches and home indicators.

Use the **install/download icon** in the header for installation instructions or an **Install app** button when Chrome makes it available:

- **Android Chrome:** browser ⋮ menu → Install app or Add to Home screen.
- **iPhone Chrome:** Share beside the address bar → Add to Home Screen → Add. If the option is unavailable, open the same URL in Safari and use Share → Add to Home Screen.
- **Desktop Chrome/Edge:** the install icon in the address bar or the browser's Install app menu.

Browser menus and installation support vary. See [Chrome's iPhone instructions](https://support.google.com/chrome/answer/9658361?co=GENIE.Platform%3DiOS) and [PWA installation requirements](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable).

Stillroom includes an app manifest, standalone display mode, Android/iPhone icons, and a service worker. Only public interface files are cached for an offline shell. Accounts, notes, history, messages, and attachments are never cached by the service worker. Sign-in and other features still need a connection to the running server; installation does not copy the Python server or database onto a phone.

### Connecting a phone to your PC server

**127.0.0.1 on your phone means the phone itself, not your PC.** For phone installation, Stillroom needs an HTTPS URL reachable from the phone, using a certificate trusted by that device. The default command remains private to your PC and does not make it reachable from a phone automatically.

If you already have a trusted TLS certificate and a hostname that resolves to your PC, the server supports explicit HTTPS access:

```sh
python3 start.py --host 0.0.0.0 --port 8765 --origin https://YOUR_HOSTNAME:8765 --cert /path/to/fullchain.pem --key /path/to/private-key.pem --no-browser
```

Open that exact HTTPS address on the phone. Allow the port on your firewall as needed, and keep the PC/server running. The certificate must cover `YOUR_HOSTNAME` and be trusted by the phone; bypassing a certificate warning is not a reliable installation setup. Keep certificates and private keys outside the repository (common key files and `certs/` are ignored).

Alternatively, keep the Python server on loopback behind an HTTPS reverse proxy that forwards all paths to `127.0.0.1:8765`:

```sh
python3 start.py --origin https://YOUR_HOSTNAME --no-browser
```

Configure that proxy and its trusted certificate separately. `--origin` must match the exact address users open, including a nondefault port. HTTPS sessions use Secure cookies. This task prepares the app and server for phone installation; it does not provision a domain, certificate, proxy, or public deployment.

## Database and privacy

The database is created automatically at `data/stillroom.sqlite3`. It stores account records, hashed passwords, sessions, notes, history, progress, friendships, messages, attachment BLOBs, notification settings, and read markers. Passwords use salted scrypt hashing; session cookies are HttpOnly and SameSite=Strict. Account APIs require an active session, and the server does not serve the database or source files over HTTP.

Back up the `data` folder while the server is stopped to preserve accounts and notes. Clearing browser storage does not delete database notes. By default the server listens only on `127.0.0.1`. Network access requires explicit HTTPS configuration as described above. Anyone with filesystem access to the database can read its notes and history. The app has no analytics. Loading videos connects your browser to the chosen provider.

## Development

- `start.py` — local server, accounts, sessions, SQLite API and optional push worker
- `push_notify.py`, `push_setup.py`, `requirements.txt` — opt-in encrypted Web Push delivery and private signing-key setup
- `chat.py` — friend requests, chat permissions, message and attachment API
- `src/Chat.tsx` — messaging UI, read acknowledgements, file previews, emoji and voice recorder
- `src/VoiceMessage.tsx` — voice playback, seeking, duration and playback speed
- `src/Notifications.tsx` — unread counts, notification panel and quiet-mode settings
- `src/InstallApp.tsx` — install prompt and platform instructions
- `manifest.webmanifest`, `icons/`, `src/sw.js`, `sw.js` — install assets and public-shell offline support
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
