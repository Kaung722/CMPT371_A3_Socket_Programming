"""
test_integration.py — Integration tests for the Connect-Four server protocol.

Spins up a real server subprocess and connects mock TCP clients to verify:
  - Handshake and role assignment
  - Board state after each move
  - Turn alternation
  - Gravity / stacking
  - Full-column rejection
  - Horizontal, vertical, and diagonal win detection
  - Both clients receiving identical final game state

Run with:
    python -m pytest test_integration.py -v
  or
    python test_integration.py
"""

import sys
import os
import socket
import json
import subprocess
import time
import unittest

HOST    = '127.0.0.1'
PORT    = 5050
TIMEOUT = 6.0   # per-recv timeout (seconds)


# ── Mock Client ───────────────────────────────────────────────────────────────

class MockClient:
    """Minimal TCP client that speaks the server's JSON-over-TCP protocol."""

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(TIMEOUT)
        self.sock.connect((HOST, PORT))
        self._buf = ""

    def connect_handshake(self):
        self._send({"type": "CONNECT"})

    def move(self, col):
        self._send({"type": "MOVE", "col": col})

    def _send(self, msg):
        self.sock.sendall((json.dumps(msg) + '\n').encode('utf-8'))

    def recv_msg(self):
        """Block until one complete newline-delimited JSON message arrives."""
        while '\n' not in self._buf:
            chunk = self.sock.recv(2048).decode('utf-8')
            if not chunk:
                raise ConnectionError("Server closed the connection")
            self._buf += chunk
        line, self._buf = self._buf.split('\n', 1)
        return json.loads(line.strip())

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


# ── Test Helpers ──────────────────────────────────────────────────────────────

def make_session():
    """
    Connect two clients, complete the handshake, and return both clients
    along with the WELCOME and initial UPDATE messages.
    Returns: (client_x, client_o, welcome_x, welcome_o, update_x, update_o)
    """
    cx = MockClient()
    co = MockClient()
    cx.connect_handshake()
    time.sleep(0.05)
    co.connect_handshake()

    welcome_x = cx.recv_msg()
    welcome_o = co.recv_msg()
    update_x  = cx.recv_msg()
    update_o  = co.recv_msg()

    return cx, co, welcome_x, welcome_o, update_x, update_o


def play_moves(cx, co, move_seq):
    """
    Execute a list of (client, col) moves, consuming both UPDATE messages
    after each move. Returns the last pair of UPDATE messages.
    """
    ux = uo = None
    clients = {'X': cx, 'O': co}
    for client, col in move_seq:
        client.move(col)
        ux = cx.recv_msg()
        uo = co.recv_msg()
    return ux, uo


# ── Test Suite ────────────────────────────────────────────────────────────────

class TestServerIntegration(unittest.TestCase):

    server_proc = None

    @classmethod
    def setUpClass(cls):
        """Start the game server once for the entire test class."""
        base   = os.path.dirname(os.path.abspath(__file__))
        python = sys.executable
        cls.server_proc = subprocess.Popen(
            [python, os.path.join(base, 'server.py')],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1.0)   # give server time to bind

    @classmethod
    def tearDownClass(cls):
        """Terminate the server after all tests complete."""
        if cls.server_proc:
            cls.server_proc.terminate()
            cls.server_proc.wait()

    # ── 1. Handshake & role assignment ────────────────────────────────────────

    def test_01_welcome_message_types(self):
        """Both clients must receive a WELCOME message."""
        cx, co, wx, wo, ux, uo = make_session()
        try:
            self.assertEqual(wx['type'], 'WELCOME')
            self.assertEqual(wo['type'], 'WELCOME')
        finally:
            cx.close(); co.close()

    def test_02_welcome_roles_are_x_and_o(self):
        """First connector is Player X, second is Player O."""
        cx, co, wx, wo, ux, uo = make_session()
        try:
            self.assertIn('X', wx['payload'])
            self.assertIn('O', wo['payload'])
        finally:
            cx.close(); co.close()

    # ── 2. Initial board state ────────────────────────────────────────────────

    def test_03_initial_update_type_and_status(self):
        """Initial UPDATE must have type UPDATE, status=ongoing, turn=X."""
        cx, co, wx, wo, ux, uo = make_session()
        try:
            self.assertEqual(ux['type'],   'UPDATE')
            self.assertEqual(ux['status'], 'ongoing')
            self.assertEqual(ux['turn'],   'X')
        finally:
            cx.close(); co.close()

    def test_04_initial_board_is_all_empty(self):
        """All 42 cells of the initial board must be empty spaces."""
        cx, co, wx, wo, ux, uo = make_session()
        try:
            for row in ux['board']:
                for cell in row:
                    self.assertEqual(cell, ' ')
        finally:
            cx.close(); co.close()

    def test_05_both_clients_receive_same_initial_board(self):
        """Both clients must see identical initial board state."""
        cx, co, wx, wo, ux, uo = make_session()
        try:
            self.assertEqual(ux['board'], uo['board'])
            self.assertEqual(ux['turn'],  uo['turn'])
        finally:
            cx.close(); co.close()

    # ── 3. Move mechanics ─────────────────────────────────────────────────────

    def test_06_first_move_places_piece_at_bottom(self):
        """X's first move in a column should land at the bottom row (row 5)."""
        cx, co, wx, wo, ux, uo = make_session()
        try:
            cx.move(3)
            update = cx.recv_msg(); co.recv_msg()
            self.assertEqual(update['board'][5][3], 'X')
        finally:
            cx.close(); co.close()

    def test_07_turn_passes_to_o_after_x_moves(self):
        """After X moves, the UPDATE must show turn=O."""
        cx, co, wx, wo, ux, uo = make_session()
        try:
            cx.move(0)
            update = cx.recv_msg(); co.recv_msg()
            self.assertEqual(update['turn'], 'O')
        finally:
            cx.close(); co.close()

    def test_08_turn_returns_to_x_after_o_moves(self):
        """After O moves, the UPDATE must show turn=X."""
        cx, co, wx, wo, ux, uo = make_session()
        try:
            cx.move(0); cx.recv_msg(); co.recv_msg()
            co.move(1)
            update = cx.recv_msg(); co.recv_msg()
            self.assertEqual(update['turn'], 'X')
        finally:
            cx.close(); co.close()

    def test_09_gravity_stacks_pieces_in_same_column(self):
        """Pieces in the same column should stack from the bottom up."""
        cx, co, wx, wo, ux, uo = make_session()
        try:
            cx.move(0); cx.recv_msg(); co.recv_msg()   # X → (5, 0)
            co.move(0); cx.recv_msg(); co.recv_msg()   # O → (4, 0)
            cx.move(0); u = cx.recv_msg(); co.recv_msg()  # X → (3, 0)

            self.assertEqual(u['board'][5][0], 'X')
            self.assertEqual(u['board'][4][0], 'O')
            self.assertEqual(u['board'][3][0], 'X')
        finally:
            cx.close(); co.close()

    def test_10_both_clients_see_same_board_after_each_move(self):
        """Both clients must receive identical board state in every UPDATE."""
        cx, co, wx, wo, ux, uo = make_session()
        try:
            moves = [(cx, 0), (co, 1), (cx, 2), (co, 3)]
            for client, col in moves:
                client.move(col)
                ux2 = cx.recv_msg()
                uo2 = co.recv_msg()
                self.assertEqual(ux2['board'], uo2['board'],
                                 f"Board mismatch after move to col {col}")
        finally:
            cx.close(); co.close()

    # ── 4. Full-column rejection ──────────────────────────────────────────────

    def test_11_full_column_move_is_rejected(self):
        """
        A move into a full column must be silently ignored. The next valid move
        from the same player should succeed and produce an UPDATE.
        """
        cx, co, wx, wo, ux, uo = make_session()
        try:
            # Fill column 0 with alternating X/O (3 pairs = 6 pieces)
            for _ in range(3):
                cx.move(0); cx.recv_msg(); co.recv_msg()
                co.move(0); cx.recv_msg(); co.recv_msg()

            # Column 0 is now completely full; it's X's turn.
            # Server reads both packets as a stream, so we add a small sleep
            # between the bad move and the valid move so TCP delivers them
            # as separate recv() calls on the server side.
            cx.move(0)   # rejected — server ignores
            time.sleep(0.15)
            cx.move(1)   # valid move — should produce UPDATE
            update = cx.recv_msg(); co.recv_msg()

            self.assertEqual(update['board'][5][1], 'X')
            self.assertEqual(update['status'], 'ongoing')
        finally:
            cx.close(); co.close()

    # ── 5. Win detection ──────────────────────────────────────────────────────

    def test_12_horizontal_win_player_red(self):
        """X wins with 4 in a horizontal row."""
        cx, co, wx, wo, ux, uo = make_session()
        try:
            # X plays cols 0,1,2 while O plays col 6 each time, then X plays 3
            moves = [(cx, 0), (co, 6), (cx, 1), (co, 6), (cx, 2), (co, 6)]
            play_moves(cx, co, moves)
            cx.move(3)
            ux_final = cx.recv_msg()
            uo_final = co.recv_msg()

            # Server sends personalized messages: winner gets 'won', loser gets 'lost'
            self.assertIn('won',  ux_final['status'])   # X sees win message
            self.assertIn('lost', uo_final['status'])   # O sees loss message
        finally:
            cx.close(); co.close()

    def test_13_vertical_win_player_red(self):
        """X wins with 4 pieces stacked in one column."""
        cx, co, wx, wo, ux, uo = make_session()
        try:
            # X and O alternate in cols 0 and 1; X stacks 4 in col 0
            moves = [(cx, 0), (co, 1), (cx, 0), (co, 1), (cx, 0), (co, 1)]
            play_moves(cx, co, moves)
            cx.move(0)
            ux_final = cx.recv_msg()
            uo_final = co.recv_msg()

            self.assertIn('won',  ux_final['status'])   # X sees win message
            self.assertIn('lost', uo_final['status'])   # O sees loss message
        finally:
            cx.close(); co.close()

    def test_14_diagonal_downright_win_player_red(self):
        """X wins with a down-right diagonal: (5,0),(4,1),(3,2),(2,3)."""
        cx, co, wx, wo, ux, uo = make_session()
        try:
            # Carefully construct the diagonal without triggering other wins
            setup = [
                (cx, 0), (co, 1),   # X(5,0), O(5,1)
                (cx, 1), (co, 2),   # X(4,1), O(5,2)
                (cx, 6), (co, 2),   # X(5,6), O(4,2)
                (cx, 2), (co, 3),   # X(3,2), O(5,3)
                (cx, 6), (co, 3),   # X(4,6), O(4,3)
                (cx, 6), (co, 3),   # X(3,6), O(3,3)
            ]
            play_moves(cx, co, setup)
            cx.move(3)              # X(2,3) → diagonal win ↘
            ux_final = cx.recv_msg()
            uo_final = co.recv_msg()

            self.assertIn('won',  ux_final['status'])   # X sees win message
            self.assertIn('lost', uo_final['status'])   # O sees loss message
        finally:
            cx.close(); co.close()

    def test_15_vertical_win_player_yellow(self):
        """O wins with 4 pieces stacked in one column."""
        cx, co, wx, wo, ux, uo = make_session()
        try:
            # X plays in col 6 as filler, O stacks in col 0
            moves = [(cx, 6), (co, 0), (cx, 6), (co, 0), (cx, 6), (co, 0)]
            play_moves(cx, co, moves)
            cx.move(5)    # X filler so it's O's turn
            cx.recv_msg(); co.recv_msg()
            co.move(0)    # O wins vertically in col 0
            ux_final = cx.recv_msg()
            uo_final = co.recv_msg()

            self.assertIn('lost', ux_final['status'])   # X sees loss message
            self.assertIn('won',  uo_final['status'])   # O sees win message
        finally:
            cx.close(); co.close()

    # ── 6. Game-over state ────────────────────────────────────────────────────

    def test_16_both_clients_see_same_final_board(self):
        """Both clients must receive identical board on game over (statuses differ by design)."""
        cx, co, wx, wo, ux, uo = make_session()
        try:
            moves = [(cx, 0), (co, 6), (cx, 1), (co, 6), (cx, 2), (co, 6)]
            play_moves(cx, co, moves)
            cx.move(3)
            ux_final = cx.recv_msg()
            uo_final = co.recv_msg()

            # Boards must be identical; statuses are intentionally personalized
            self.assertEqual(ux_final['board'], uo_final['board'])
            self.assertIn('won',  ux_final['status'])   # winner gets 'won'
            self.assertIn('lost', uo_final['status'])   # loser gets 'lost'
        finally:
            cx.close(); co.close()

    def test_17_status_is_ongoing_mid_game(self):
        """Status must remain 'ongoing' until someone wins or draws."""
        cx, co, wx, wo, ux, uo = make_session()
        try:
            moves = [(cx, 0), (co, 1), (cx, 2), (co, 3), (cx, 4)]
            ux_last, _ = play_moves(cx, co, moves)
            self.assertEqual(ux_last['status'], 'ongoing')
        finally:
            cx.close(); co.close()

    def test_18_board_dimensions_always_6x7(self):
        """Every UPDATE must carry a board with exactly 6 rows and 7 columns."""
        cx, co, wx, wo, ux, uo = make_session()
        try:
            moves = [(cx, 0), (co, 1), (cx, 2)]
            ux_last, _ = play_moves(cx, co, moves)
            self.assertEqual(len(ux_last['board']), 6)
            for row in ux_last['board']:
                self.assertEqual(len(row), 7)
        finally:
            cx.close(); co.close()


    # ── 7. Bug reproduction tests ─────────────────────────────────────────────
    # These tests are designed to EXPOSE the known bugs.
    # They are expected to FAIL before the bugs are fixed.

    def test_19_draw_game_does_not_crash_server(self):
        """
        BUG: UnboundLocalError — 'stat' is not assigned when winner == 'Draw'.
        Plays a complete 42-move game that ends in a draw and verifies the
        server sends 'Draw' status to both clients without crashing.

        Draw board pattern (X moves first, O moves second, columns 0-6):
        Round-robin across columns so no player gets 4 in a row.
        Column order each round: 0,1,2,3,4,5,6 -> fill bottom-up, alternating.
        We use a known non-winning fill: odd columns for X, even for O in each row.
        """
        cx, co, wx, wo, ux, uo = make_session()
        try:
            # This sequence fills the board in a zigzag pattern that produces
            # a draw (no 4-in-a-row for either player).
            # 6 rows × 7 cols = 42 moves total. X moves 21 times, O 21 times.
            # Column fill order chosen to avoid any win mid-game.
            # Verified draw sequence — all 42 moves, no 4-in-a-row for either player.
            # Found by simulating random column choices and keeping runs that end in 'Draw'.
            draw_cols = [
                5, 3, 4, 0, 3, 2, 4, 3, 1, 6,
                0, 5, 2, 3, 4, 4, 2, 1, 1, 6,
                6, 3, 6, 4, 2, 0, 6, 2, 2, 1,
                4, 6, 5, 0, 0, 0, 3, 5, 5, 5,
                1, 1,
            ]
            clients = [cx, co]
            turn_idx = 0
            last_ux = last_uo = None
            for col in draw_cols:
                client = clients[turn_idx % 2]
                client.move(col)
                last_ux = cx.recv_msg()
                last_uo = co.recv_msg()
                # If the game is over early (someone won), stop.
                if last_ux['status'] != 'ongoing':
                    break
                turn_idx += 1

            # The final status for both clients must contain 'Draw'.
            self.assertIn('Draw', last_ux['status'],
                          "Server crashed or sent wrong status on draw for X")
            self.assertIn('Draw', last_uo['status'],
                          "Server crashed or sent wrong status on draw for O")
        finally:
            cx.close(); co.close()

    def test_20_full_column_server_does_not_hang(self):
        """
        BUG: ConnectionResetError — When a full-column move is ignored by the
        server, _move_pending stays True on the client forever. The server then
        waits for the next recv from the same player but the client has given up
        and closed the connection, causing WinError 10054.

        This test fills a column, sends a bad move into it, then immediately
        sends a valid move. Both must produce a clean UPDATE with no crash.
        """
        cx, co, wx, wo, ux, uo = make_session()
        try:
            # Fill column 0 completely (6 pieces: X O X O X O)
            for _ in range(3):
                cx.move(0); cx.recv_msg(); co.recv_msg()  # X at col 0
                co.move(0); cx.recv_msg(); co.recv_msg()  # O at col 0
            # Col 0 is full. It's X's turn.

            # Send bad move into full column 0.
            cx.move(0)
            time.sleep(0.15)   # let server process the rejected move

            # Immediately send a valid move into col 1.
            # If the server is stuck waiting on the wrong client or crashed,
            # this recv_msg() call will time out and raise a socket.timeout.
            cx.move(1)
            update_x = cx.recv_msg()
            update_o = co.recv_msg()

            self.assertEqual(update_x['board'][5][1], 'X',
                             "Valid move after full-column rejection was not registered")
            self.assertEqual(update_x['status'], 'ongoing')
        finally:
            cx.close(); co.close()

    def test_21_abrupt_disconnect_does_not_crash_server(self):
        """
        BUG: ConnectionResetError — When a client forcefully closes its socket
        mid-game, the server's recv() raises ConnectionResetError/BrokenPipeError
        and the stack trace floods the console. The server thread should catch
        this and exit cleanly so the server process stays alive.

        After the disconnect, the server process must still accept new connections.
        """
        cx, co, wx, wo, ux, uo = make_session()

        # Make one move, then abruptly close both client sockets.
        cx.move(0); cx.recv_msg(); co.recv_msg()
        cx.close()   # disconnect mid-game — server will get ConnectionResetError on next recv
        co.close()

        # Give the server thread a moment to clean up.
        time.sleep(0.5)

        # The server must still be alive and accepting new games.
        try:
            cx2, co2, wx2, wo2, ux2, uo2 = make_session()
            self.assertEqual(wx2['type'], 'WELCOME',
                             "Server did not recover after abrupt client disconnect")
        finally:
            try: cx2.close()
            except: pass
            try: co2.close()
            except: pass


if __name__ == '__main__':
    unittest.main(verbosity=2)

