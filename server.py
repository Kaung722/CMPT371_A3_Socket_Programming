# CMPT 371 A3 - Connect-Four Server
# Handles all game logic server-side so neither client can manipulate the outcome.
# Architecture: one TCP server socket accepts connections into a lobby queue.
# Once two clients are queued, a new game thread is spawned for that pair,
# freeing the main thread to continue accepting new connections immediately.

import socket
import threading
import json
import datetime

# HOST is loopback only — both clients must run on the same machine.
# Change to the LAN IP of this machine if playing across a local network.
HOST = '127.0.0.1'
PORT = 5050

# Global lobby queue: holds (socket, address) tuples waiting to be paired.
# Access is safe here because the main accept loop is single-threaded.
lobby = []


def ts():
    # Returns current wall-clock time as HH:MM:SS for prefixing log lines.
    return datetime.datetime.now().strftime("%H:%M:%S")


def check_winner(board):
    # Checks the 6x7 board for a Connect-Four win or a draw.
    # Returns 'X' or 'O' if a player has four in a row,
    # 'Draw' if the board is full with no winner, or None if the game continues.
    # All four directions are checked independently (rows, columns, two diagonals).

    # --- Horizontal check ---
    # Scan each row left-to-right, tracking consecutive run lengths.
    # A gap (empty cell) resets both counters.
    for i in range(6):
        xcount = 0
        ocount = 0
        for j in range(7):
            if board[i][j] == ' ':
                xcount = 0
                ocount = 0
                continue
            if board[i][j] == 'X':
                xcount += 1
                ocount = 0
            else:
                ocount += 1
                xcount = 0
            if xcount >= 4: return 'X'
            elif ocount >= 4: return 'O'

    # --- Vertical check ---
    # Scan each column top-to-bottom with the same run-length logic.
    for j in range(7):
        xcount = 0
        ocount = 0
        for i in range(6):
            if board[i][j] == ' ':
                xcount = 0
                ocount = 0
                continue
            if board[i][j] == 'X':
                xcount += 1
                ocount = 0
            else:
                ocount += 1
                xcount = 0
            if xcount >= 4: return 'X'
            elif ocount >= 4: return 'O'

    # --- Diagonal check (top-left → bottom-right) ---
    # Only start positions where a run of 4 can fit within the 6x7 grid:
    # rows 0-2, cols 0-3 (so row+3 <= 5 and col+3 <= 6).
    DRstartPos = [(0,0),(0,1),(0,2),(0,3),
                  (1,0),(1,1),(1,2),(1,3),
                  (2,0),(2,1),(2,2),(2,3)]

    # --- Diagonal check (bottom-left → top-right) ---
    # Start positions where row-3 >= 0 and col+3 <= 6:
    # rows 3-5, cols 0-3.
    URstartPos = [(3,0),(3,1),(3,2),(3,3),
                  (4,0),(4,1),(4,2),(4,3),
                  (5,0),(5,1),(5,2),(5,3)]

    for pos in DRstartPos:
        i, j = pos
        if board[i][j] == board[i+1][j+1] == board[i+2][j+2] == board[i+3][j+3] != ' ':
            return board[i][j]

    for pos in URstartPos:
        i, j = pos
        if board[i][j] == board[i-1][j+1] == board[i-2][j+2] == board[i-3][j+3] != ' ':
            return board[i][j]

    # --- Draw check ---
    # If no empty cell remains and no winner was found, the board is full.
    if all(cell != ' ' for row in board for cell in row):
        return 'Draw'
    return None


def run_game(sock_red, addr_red, sock_yel, addr_yel):
    # Manages a single two-player game session in its own thread.
    # Responsible for:
    #   1. Sending each player their role (WELCOME message).
    #   2. Broadcasting the initial empty board (UPDATE message).
    #   3. Running the turn loop: receive MOVE → apply gravity → check winner
    #      → send personalized UPDATE to each player (different status strings).
    #   4. Closing both sockets when the game ends.

    red_str = f"{addr_red[0]}:{addr_red[1]}"
    yel_str = f"{addr_yel[0]}:{addr_yel[1]}"

    print(f"[{ts()}] new game: Red = {red_str}  | Yellow = {yel_str}", flush=True)

    # Tell each client which piece they are playing.
    # 'X' = Red (moves first), 'O' = Yellow.
    sock_red.sendall((json.dumps({"type": "WELCOME", "payload": "Player X"}) + '\n').encode('utf-8'))
    print(f"[{ts()}] WELCOME -> Player X ({red_str})", flush=True)
    sock_yel.sendall((json.dumps({"type": "WELCOME", "payload": "Player O"}) + '\n').encode('utf-8'))
    print(f"[{ts()}] WELCOME -> Player O ({yel_str})", flush=True)

    # Initialise the board as all empty spaces and send the starting state.
    board = [[' '] * 7 for _ in range(6)]
    turn = 'X'  # Red always goes first

    update_msg = json.dumps({"type": "UPDATE", "board": board, "turn": turn, "status": "ongoing"}) + '\n'
    sock_red.sendall(update_msg.encode('utf-8'))
    sock_yel.sendall(update_msg.encode('utf-8'))
    print(f"[{ts()}] initial UPDATE sent, turn=X", flush=True)

    # Map player symbols to their sockets and address strings for easy lookup.
    conns = {'X': sock_red, 'O': sock_yel}
    addr_map = {'X': red_str, 'O': yel_str}

    while True:
        # Only the player whose turn it is should be sending a MOVE.
        cur_sock = conns[turn]

        data = cur_sock.recv(1024).decode('utf-8')
        if not data:
            # Client closed the connection unexpectedly — end the session.
            break

        # TCP can coalesce multiple JSON messages into one recv() call.
        # We only process the first complete line here; extras are discarded below.
        first_line = data.strip().split('\n')[0]
        msg = json.loads(first_line)

        if msg["type"] == "MOVE":
            c = msg["col"]

            # Apply gravity: find the lowest unoccupied row in the chosen column.
            # Iterating from row 5 (bottom) upward ensures pieces stack naturally.
            r = None
            for i in range(5, -1, -1):
                if board[i][c] == ' ':
                    r = i
                    break

            if r is None:
                # The column is full — silently ignore the move and wait for another.
                print(f"[{ts()}] Column {c} is full, ignoring move from Player {turn} rejected", flush=True)
                continue

            print(f"[{ts()}] MOVE from Player {turn} ({addr_map[turn]}): col={c}", flush=True)

            board[r][c] = turn
            winner = check_winner(board)

            # Each player receives a personalised status string so the client
            # can display the correct message without any extra logic.
            status_x = "ongoing"
            status_o = "ongoing"

            if winner:
                if winner == 'Draw':
                    status_x = "It's a Draw!"
                    status_o = "It's a Draw!"
                else:
                    if winner == 'X':
                        status_x = "Congratulations, you won!"
                        status_o = "You lost! Better luck next time."
                        stat = "Player X won"
                    else:
                        status_o = "Congratulations, you won!"
                        status_x = "You lost! Better luck next time."
                        stat = "Player O won"
                    
                print(f"[{ts()}] Placed {turn} at ({r},{c}) result: {stat}", flush=True)
            else:
                print(f"[{ts()}] Placed {turn} at ({r},{c}) no winner yet", flush=True)
                turn = 'O' if turn == 'X' else 'X'  # Swap turns only when there's no winner

            # Broadcast the updated board with personalised status to each client.
            update_msg_x = json.dumps({"type": "UPDATE", "board": board, "turn": turn, "status": status_x}) + '\n'
            update_msg_o = json.dumps({"type": "UPDATE", "board": board, "turn": turn, "status": status_o}) + '\n'
            sock_red.sendall(update_msg_x.encode('utf-8'))
            sock_yel.sendall(update_msg_o.encode('utf-8'))

            if winner:
                print(f"[{ts()}] game over, sent final state: {stat}", flush=True)
            else:
                print(f"[{ts()}] sent UPDATE, turn={turn}", flush=True)

            # After a move, the player who just moved may have buffered extra data
            # in their send buffer. Drain it in non-blocking mode so it doesn't
            # interfere with the next expected MOVE from the other player.
            just_moved = conns['O' if turn == 'X' else 'X']
            just_moved.setblocking(False)
            try:
                while just_moved.recv(4096):
                    pass
            except:
                pass
            just_moved.setblocking(True)

            if winner:
                break  # Game is over; exit the loop and close sockets below.

    print(f"[{ts()}] game ended, closing sockets", flush=True)
    sock_red.close()
    sock_yel.close()


def start_server():
    # Creates the listening TCP socket and enters the accept loop.
    # SO_REUSEADDR lets the port be reused immediately after a restart,
    # avoiding "address already in use" errors during development.
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    print(f"[{ts()}] listening on {HOST}:{PORT}", flush=True)

    try:
        while True:
            conn, addr = server.accept()
            print(f"[{ts()}] Accepted connection from {addr[0]}:{addr[1]}", flush=True)
            data = conn.recv(1024).decode('utf-8')

            if "CONNECT" in data:
                # Add the new client to the lobby and check if we have a pair.
                lobby.append((conn, addr))
                print(f"[{ts()}] player connected, lobby size: {len(lobby)}", flush=True)

                if len(lobby) >= 2:
                    # Pop two clients and start their game in a dedicated thread.
                    # Using a thread per game allows multiple simultaneous sessions.
                    red_sock, addr_red = lobby.pop(0)
                    yel_sock, addr_yel = lobby.pop(0)
                    print(f"[{ts()}] matched 2 players, starting game thread", flush=True)
                    threading.Thread(target=run_game, args=(red_sock, addr_red, yel_sock, addr_yel)).start()

    except KeyboardInterrupt:
        print(f"[{ts()}] Server closing...", flush=True)
    finally:
        server.close()


if __name__ == "__main__":
    start_server()