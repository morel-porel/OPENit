import subprocess
import platform
import os
import threading
import time

import keyboard

# --- THE CONFIGURATION (The Brains) ---
# In the future, we will load this from a JSON file.
# For now, we hardcode it to test logic.
APP_MODES = {
    "study": [
        # Linux examples (for you)
        "gnome-calculator"
        # Windows examples (for her - comment these out when testing on Linux)
        # r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        # r"C:\Users\HerName\AppData\Local\Microsoft\Teams\current\Teams.exe"
    ],
    "game": [
        # "info",
        "/usr/bin/notesclonedym"
        # Windows examples
        # r"C:\Program Files (x86)\Steam\steam.exe"
    ]
}

last_trigger_time = 0
COOLDOWN = 1.0

is_listening = False


def activate_listening():
    global is_listening
    # Play sound here todo
    is_listening = True

    # Go back to sleep if no input after 3 secs
    threading.Timer(3.0, cancel_listening).start()

def cancel_listening():
    global is_listening
    if is_listening:
        is_listening = False

def get_real_user():

    if platform.system() == "Linux":
        return os.environ.get('SUDO_USER')
    return None

def launch_mode(mode_name):

    apps_to_open = APP_MODES.get(mode_name, [])
    real_user = get_real_user()

    for app in apps_to_open:
        try:
            if platform.system() == "Windows":
                subprocess.Popen(app, close_fds=True)
            else:
                if real_user:
                    cmd = ['sudo', '-u', real_user, app]
                else:
                    cmd = [app]

                subprocess.Popen(
                    cmd,
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

            print(f"Launched: {app}")
        except FileNotFoundError:
            print(f"ERROR: Could not find path: {app}")
        except Exception as e:
            print(f"ERROR launching {app}: {e}")


def safe_trigger(mode_name):
    global last_trigger_time
    current_time = time.time()

    if current_time - last_trigger_time > COOLDOWN:
        last_trigger_time = current_time
        t = threading.Thread(target=launch_mode, args=(mode_name,))
        t.daemon = True
        t.start()


def handle_command(key_event):
    global is_listening
    if not is_listening:
        return

    key = key_event.name

    if key == 's':
        print(" -> Command Received: STUDY")
        safe_trigger('study')
        is_listening = False

    elif key == 'g':
        print(" -> Command Received: GAME")
        safe_trigger('game')
        is_listening = False


if __name__ == "__main__":
    keyboard.add_hotkey('ctrl+space', activate_listening)

    keyboard.on_press(handle_command)

    keyboard.wait('Esc')