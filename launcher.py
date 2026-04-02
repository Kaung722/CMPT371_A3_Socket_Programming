# CMPT 371 A3 - Connect-Four Launcher
# opens a server terminal + two client windows when you click Launch

import subprocess
import sys
import os
import time
import pygame

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
pygame.init()

# colors
BG_COLOR      = (15, 15, 30)
TITLE_COLOR   = (230, 230, 255)
BTN_COLOR     = (50, 120, 255)
BTN_HOVER     = (90, 160, 255)
BTN_TEXT      = (255, 255, 255)
STATUS_COLOR  = (100, 255, 150)
ERROR_COLOR   = (255, 80, 80)

FONT_TITLE = pygame.font.SysFont("Helvetica", 28, bold=True)
FONT_BTN   = pygame.font.SysFont("Helvetica", 20, bold=True)
FONT_SUB   = pygame.font.SysFont("Helvetica", 15)

WIDTH, HEIGHT = 420, 280
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Connect-4 Launcher")

# use the same python that's running this script so the venv carries over
PYTHON = sys.executable
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

status_msg = "Click Launch to start the game!"
status_is_error = False
launched = False
processes = []

def launch():
    global status_msg, status_is_error, launched, processes

    # Kill any previously spawned processes first
    for p in processes:
        try: p.terminate()
        except: pass
    processes.clear()
    # Also kill any leftover server.py from a previous launch
    subprocess.Popen(['pkill', '-f', 'server.py'],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)

    try:
        # on mac, open a real terminal so we can see the server logs
        if sys.platform == 'darwin':
            script = (
                f'tell application "Terminal" to do script '
                f'"cd {BASE_DIR} && {PYTHON} server.py"'
            )
            subprocess.Popen(['osascript', '-e', script])
        else:
            # on other platforms just run it silently in the background
            server = subprocess.Popen(
                [PYTHON, os.path.join(BASE_DIR, 'server.py')],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            processes.append(server)

        time.sleep(1.5)  # let the server start up before clients try to connect

        # start 2 clients
        for _ in range(2):
            client = subprocess.Popen(
                [PYTHON, os.path.join(BASE_DIR, "gui_client.py")],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            processes.append(client)
            time.sleep(0.2)  # Slight stagger to allow clean matchmaking

        status_msg = "Server + 2 clients launched!"
        status_is_error = False
        launched = True
    except Exception as e:
        status_msg = f"Error: {e}"
        status_is_error = True

def stop():
    global status_msg, status_is_error, launched, processes
    for p in processes:
        try: p.terminate()
        except: pass
    processes.clear()
    launched = False
    status_msg = "Stopped all processes."
    status_is_error = False

clock = pygame.time.Clock()
running = True

while running:
    screen.fill(BG_COLOR)
    mouse_pos = pygame.mouse.get_pos()

    # title
    title = FONT_TITLE.render("Connect-4 Launcher", True, TITLE_COLOR)
    screen.blit(title, title.get_rect(center=(WIDTH // 2, 50)))

    sub = FONT_SUB.render("Spins up 1 server + 2 GUI clients instantly", True, (150, 150, 200))
    screen.blit(sub, sub.get_rect(center=(WIDTH // 2, 82)))

    # launch button
    launch_rect = pygame.Rect(WIDTH // 2 - 120, 120, 240, 50)
    hover = launch_rect.collidepoint(mouse_pos)
    pygame.draw.rect(screen, BTN_HOVER if hover else BTN_COLOR, launch_rect, border_radius=10)
    btn_label = "Re-Launch" if launched else "Launch Game"
    btn_text = FONT_BTN.render(btn_label, True, BTN_TEXT)
    screen.blit(btn_text, btn_text.get_rect(center=launch_rect.center))

    # stop button
    stop_rect = pygame.Rect(WIDTH // 2 - 120, 185, 240, 40)
    stop_hover = stop_rect.collidepoint(mouse_pos)
    stop_color = (200, 60, 60) if stop_hover else (160, 40, 40)
    pygame.draw.rect(screen, stop_color, stop_rect, border_radius=8)
    stop_text = FONT_BTN.render("Stop All", True, BTN_TEXT)
    screen.blit(stop_text, stop_text.get_rect(center=stop_rect.center))

    # status
    color = ERROR_COLOR if status_is_error else STATUS_COLOR
    status_surf = FONT_SUB.render(status_msg, True, color)
    screen.blit(status_surf, status_surf.get_rect(center=(WIDTH // 2, 246)))

    # events
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            stop()
            running = False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if launch_rect.collidepoint(mouse_pos):
                launch()
            elif stop_rect.collidepoint(mouse_pos):
                stop()

    pygame.display.update()
    clock.tick(60)

pygame.quit()
sys.exit()