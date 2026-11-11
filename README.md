# Stillroom — PC edition

A quiet YouTube and Google Drive video viewer with cinema mode, light/dark themes, and notes saved per video on this browser and device. No ChatGPT account, login, API key, or hosting is needed.

## Run it (Linux or macOS)

1. Extract this ZIP.
2. Open a terminal inside the `stillroom-pc` folder.
3. Run:

   python3 start.py

Your browser opens http://127.0.0.1:8765/ automatically. If it doesn't, open that address yourself. Keep the terminal running; Ctrl+C stops the server.

## Windows

Extract the ZIP, open a terminal in its folder, and run:

   py start.py

Python 3 is required. If `py` isn't available but Python is installed, try `python start.py`.

## Use

Paste a regular YouTube URL, youtu.be link, Shorts link, live video link, or video ID. Google Drive video file links (`drive.google.com/file/d/…/view`, preview links, and `drive.google.com/open?id=…` links) are also supported, including links with resource keys. Folder links are not supported. Click Watch video. Timestamp links are supported. Cinema mode hides the surrounding workspace; Escape leaves cinema mode.

Notes save automatically for each video in this browser's local storage. Load the same video to retrieve them. Use the download icon to export notes as text. Clearing browser data removes saved notes. Private browsing may discard them. Always use the same localhost address and port to access the same stored notes.

For Drive videos, you must have permission to view the file. Sharing as “Anyone with the link” allows viewing without signing in; restricted files may need sign-in through the “open in Google Drive” link below the player. Drive processing, browser cookie settings, and owner restrictions can affect embedded playback.

An internet connection is needed to play videos. The interface and all its fonts and icons are bundled locally. YouTube's embedded player may show ads, branding, and related videos, and some videos disallow embedding. This does not bypass YouTube restrictions.

Use the local server, rather than double-clicking index.html: YouTube embeds need an HTTP origin/referrer and may reject file:// pages.

## Files and editing

- index.html — HTML entry point
- styles.css — all styling (edit directly and refresh)
- app.js — prebuilt application; no npm install needed to run
- app.js.LEGAL.txt — bundled third-party license notices
- src/App.tsx — readable React/TypeScript component, video parsing and UI logic
- src/main.tsx — React entry point
- build.mjs and package.json — optional developer build
- start.py — local server and browser launcher
- favicon.svg — icon

To rebuild after changing React source, install Node.js/npm, then run in this folder:

   npm install
   npm run build

Then refresh your local page. These commands are unnecessary for normal use. The provided app.js is already built.

The local server listens only on 127.0.0.1. The app has no analytics or backend database. Loading a video connects your browser to the selected provider (YouTube or Google Drive).
