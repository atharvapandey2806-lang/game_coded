# GameBot

GameBot is a Windows desktop multiplayer game app. Players should not need to read this file: publish `GameBot.exe` in GitHub Releases and tell them to download and run it.

## Player Download

1. Go to the latest GitHub Release.
2. Download `GameBot.exe`.
3. Run it.

On first launch the app installs its bundled server and web account files into the user's local app folder, creates shortcuts, starts the local server, and opens the desktop game UI.

## What The App Does

- Desktop-first gameplay with button controls.
- Multiple app themes: Nebula, Solar, and Cyber Mint.
- Account login/register inside the app, with web pages kept for account access only.
- Unique usernames.
- Passwords are salted and hashed.
- Email addresses are stored as a hash for lookup plus encrypted storage for account records.
- Server-resolved game outcomes so the client cannot invent wins.
- Anti-cheat event logging for invalid game actions.
- Friend requests and encrypted friend chat.

## Build The EXE

On Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\BUILD_EXE.ps1
```

The build output will be:

```text
dist\GameBot.exe
```

## Release On GitHub

1. Commit the project.
2. Build the EXE with `BUILD_EXE.ps1`.
3. Open your repo on GitHub.
4. Go to **Releases**.
5. Choose **Draft a new release**.
6. Create a tag like `v3.1.0`.
7. Upload `dist\GameBot.exe`.
8. Publish the release.

Use a short release title like:

```text
GameBot v3.1.0
```

Use this release note:

```text
Download GameBot.exe, run it, create an account, and play.
```

## Developer Run

```powershell
python launcher.py
```

The app starts the local Flask server automatically.

## Source Files

```text
launcher.py                    Desktop app and EXE installer behavior
gamebot_multiplayer_server.py  Local API, accounts, games, friends, chat
master.html                    Web account/dashboard fallback
login.html                     Web account login/register
dashboard.html                 Web account dashboard fallback
requirements.txt               Python runtime dependencies
BUILD_EXE.ps1                  Windows EXE build script
.env.example                   Optional local configuration
```
