# Connect-Four — Multiplayer Socket Application
> CMPT 371 – Assignment 3 | Simon Fraser University

A real-time, two-player **Connect-Four** game built entirely on Python's **TCP Socket API**. The application creates 1 server and 2 GUI clients. All game logic lives on the server so neither client can cheat.

---

## Team Members

| Name | Student ID | Email |
|------|-----------|-------|
| Ha Thuy Anh (Kelly) Khuc | 301416841 | htk@sfu.ca |
| Kaung Si Thu | 301554181 | kaungsit@sfu.ca |

---

## Video Demo

▶️ **[Watch the 2-minute demo here](https://youtu.be/HvSJlIYw7yE)**

---

## Architecture

```
┌──────────────┐    TCP / JSON    ┌──────────────────────────────────┐
│  GUI Client  │ ◄─────────────► │  Server  (authoritative engine)  │
│  Player Red  │                  │  • Matchmaking queue             │
└──────────────┘                  │  • Board state                   │
                                  │  • Win detection                 │
┌──────────────┐    TCP / JSON    │  • Turn enforcement              │
│  GUI Client  │ ◄─────────────► │                                  │
│ Player Yellow│                  └──────────────────────────────────┘
└──────────────┘
```

**Protocol messages (newline-delimited JSON):**

| Direction | Type | Payload |
|-----------|------|---------|
| Client → Server | `CONNECT` | Initial handshake |
| Client → Server | `MOVE` | `{ "col": <int> }` |
| Server → Client | `WELCOME` | `{ "payload": "Player X\|O" }` |
| Server → Client | `UPDATE` | `{ "board": [[...]], "turn": "X\|O", "status": "ongoing\|Congratulations, you won!\|You lost!\|It's a Draw!" }` — status is personalized per client |
| Server → Client | `ERROR` | `{ "message": "<reason>" }` — sent when a move is rejected (e.g. column full); client clears its move lock and shows the message |

---

## Project Files

| File | Role |
|---|---|
| `server.py` | Authoritative game server — matchmaking, board logic, win detection, timestamped protocol logging |
| `gui_client.py` | Pygame GUI client — drop animations, glow effects, sound effects (drop/win/lose), hover preview, and game-over overlay |
| `launcher.py` | One-click launcher — spawns server + 2 clients via **Launch Game** and **Stop All** buttons |
| `test_server.py` | Unit tests for `check_winner` (30 cases across all win directions and draw) |
| `test_integration.py` | Integration tests — connects real mock clients to a live server (18 protocol tests) |
| `requirements.txt` | Python runtime dependencies |
| `fonts/` | Bundled Montserrat font files used by the GUI client |
| `sounds/` | Sound effect files — `drop.mp3`, `win.mp3`, `lose.mp3` |

---

## Limitations

| # | Limitation | Notes |
|---|-----------|-------|
| 1 | **Two players per game** | The server matches exactly two clients per session. A third client connecting during a live game will not be paired until another client joins to form a new pair. |
| 2 | **Handling multiple clients concurrently** | The server utilizes `threading.Thread` to support multiple independent game pairs concurrently. However, scaling to thousands of games may be limited by the server's memory and OS thread limits. |
| 3 | **Client disconnecting** | If either client disconnects mid-game (network drop, window closed), the session ends immediately without state recovery. The remaining client must close and restart. |
| 4 | **Ensuring data integrity** | Data is transferred over reliable TCP sockets and JSON strings, ensuring complete in-order delivery. However, there is no TLS/SSL encryption or cryptographic hashing to prevent packet tampering on untrusted networks. |
| 5 | **High latency issues** | Actions are validated synchronously by the server. Under high network latency, players may experience a delay between clicking a column and seeing their move reflected, as the GUI awaits the server's `UPDATE`. |
| 6 | **No game persistence** | Game state exists only in memory. If the server process crashes, all active session data is lost. |
| 7 | **Port conflict on rapid re-launch** | The server uses `SO_REUSEADDR` to mitigate port reuse issues. If the port (`5050`) remains occupied after a crash, wait ~10 seconds before restarting. |
| 8 | **Local host limitation** | `HOST` is hardcoded to `127.0.0.1` in both files. To play over a LAN, both files must be edited to use the server machine's LAN IP. |
| 9 | **Launcher is macOS-only** | `launcher.py` opens a macOS Terminal window via AppleScript. On Windows, it runs silently in the background, so the manual three-terminal method is recommended on Windows. |

---

## Requirements

- **Python 3.9 or newer**
- **`pygame-ce`** (Pygame Community Edition — a maintained drop-in replacement for `pygame`)

All dependencies are listed in `requirements.txt`.

> ⚠️ Do **not** install both `pygame` and `pygame-ce` in the same environment — they conflict. If you have `pygame` installed, uninstall it first: `pip uninstall pygame`.

---

## Step-by-Step Run Guide

> This guide assumes a **completely fresh environment** with no existing Python packages.  
> All commands are run from inside the project folder after cloning.

### Step 1 — Clone the repository

```bash
git clone https://github.com/Kaung722/CMPT371_A3_Socket_Programming.git
cd CMPT371_A3_Socket_Programming
```

---

### 🍎 macOS Instructions

#### Step 2 — Verify Python 3.9+ is installed

```bash
python3 --version
```

If Python is not installed or is older than 3.9, download it from [python.org](https://www.python.org/downloads/) and re-run the command above to confirm.

#### Step 3 — Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

Your terminal prompt should now show `(venv)` at the start.

#### Step 4 — Install dependencies

```bash
pip install -r requirements.txt
```

This installs `pygame-ce`. Verify it succeeded:

```bash
python -c "import pygame; print(pygame.version.ver)"
```

You should see a version number printed (e.g. `2.5.x`).

#### Step 5 — Launch the game

**Option A — One-click launcher (recommended on macOS):**

```bash
python launcher.py
```

A small launcher window will appear. Click **Launch Game** — it automatically:
1. Opens a macOS Terminal window running `server.py` (so you can see server logs).
2. Launches two Pygame game windows (one per player).

Use **Re-Launch** to restart a finished game, and **Stop All** to shut everything down.

**Option B — Manual launch (three separate terminals):**

Open three separate Terminal tabs/windows, navigate into the project folder in each, activate the virtual environment (`source venv/bin/activate`), and run:

```bash
# Terminal 1 — start the server first
python server.py
```

Wait until you see:
```
[HH:MM:SS] listening on 127.0.0.1:5050
```

Then in the other two terminals:

```bash
# Terminal 2 — Player Red
python gui_client.py

# Terminal 3 — Player Yellow
python gui_client.py
```

---

### 🪟 Windows Instructions

> The one-click launcher does not show a visible server log on Windows. The **manual method** below is recommended.

#### Step 2 — Verify Python 3.9+ is installed

Open **Command Prompt** or **PowerShell** and run:

```cmd
python --version
```

If Python is not installed or is older than 3.9, download it from [python.org](https://www.python.org/downloads/).  
✅ During installation, check **"Add Python to PATH"**.

#### Step 3 — Install dependencies

```cmd
pip install -r requirements.txt
```

Verify:

```cmd
python -c "import pygame; print(pygame.version.ver)"
```

#### Step 4 — Manual launch (three separate terminals)

Open **three separate Command Prompt / PowerShell windows**, navigate into the project folder in each, and run:

```cmd
:: Window 1 — start the server first
python server.py
```

Wait for:
```
[HH:MM:SS] listening on 127.0.0.1:5050
```

Then:

```cmd
:: Window 2 — Player Red
python gui_client.py
```

```cmd
:: Window 3 — Player Yellow
python gui_client.py
```

---

## How to Play

1. Two clients connect to the server and are assigned **Player Red** (moves first, `X`) or **Player Yellow** (`O`).
2. Click any **column** on the board to drop your disc. If the chosen column is full, the server will reject the move and display an error message — simply click a different column.
3. First player to get **four discs in a row** (horizontal, vertical, or diagonal) wins.
4. If the board fills up completely with no winner, the game ends in a **Draw**.
5. A game-over overlay appears on both clients at the end of the game. Close the window to exit.

---

## Testing

Install `pytest` first (included automatically if you follow the run guide):

```bash
python -m pip install pytest
```

**Unit tests** — validates all `check_winner` logic without a running server:

```bash
python -m pytest test_server.py -v
```

**Integration tests** — spins up a real server and simulates two TCP clients end-to-end:

```bash
python -m pytest test_integration.py -v
```

Both suites also run automatically on every push and pull request to `main` via **GitHub Actions** (see `.github/workflows/tests.yml`).

---

## Credits & Acknowledgements

| Component | Attribution |
|-----------|-------------|
| **Test scripts** (`test_server.py`, `test_integration.py`) | Entirely generated by AI (Claude) |
| **GUI initial setup** (`gui_client.py`, `launcher.py`) | AI-assisted initial scaffolding; further developed and customized by the team |
| **Code comments** (`server.py`, `gui_client.py`) | AI-assisted comment improvements for clarity and readability |
| **README formatting** | AI-assisted formatting and structuring |
| **Gameplay logic inspiration** | Adapted from the Tic-Tac-Toe socket reference implementation by [@mariam-bebawy](https://github.com/mariam-bebawy/CMPT371_A3_Socket_Programming) |
| **Everything else** | Written by Ha Thuy Anh (Kelly) Khuc and Kaung Si Thu — including TCP socket setup and connection handling, the newline-delimited JSON protocol design, server-side matchmaking lobby, authoritative board state management, gravity-based piece placement, four-direction win detection (`check_winner`), per-client personalised status messages, turn enforcement, threaded game sessions, and the client-side networking layer (socket connect, background listener thread, message buffering and parsing) |

---

## References

- 📺 **[CMPT 371 — Assignment 3 Socket Programming in Python](https://www.youtube.com/playlist?list=PL-8C2cUhmkO1yWLTCiqf4mFXId73phvdx)** — TA-guided tutorial playlist for this assignment.
- 📺 **[Python Network Programming — TCP/IP Socket Programming](https://www.youtube.com/playlist?list=PLhTjy8cBISErYuLZUvVOYsR1giva2payF)** — YouTube tutorial series covering Python TCP socket fundamentals.
- 📄 **[Python `socket` module documentation](https://docs.python.org/3/library/socket.html)** — Official Python docs for the Socket API used throughout this project.
- 📄 **[Python `threading` module documentation](https://docs.python.org/3/library/threading.html)** — Used for per-game session threads on the server.
- 📄 **[Pygame CE documentation](https://pyga.me/docs/)** — API reference for the GUI client's rendering, animation, and sound.
- 📄 **[Python `json` module documentation](https://docs.python.org/3/library/json.html)** — Used for newline-delimited JSON protocol serialization/deserialization.

