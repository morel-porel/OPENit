import subprocess
import platform
import os
import threading
import time
import keyboard

def get_real_user():
    if platform.system() != "Linux": return None

    if os.environ.get('SUDO_USER'):
        return os.environ.get('SUDO_USER')

    if os.environ.get('PKEXEC_UID'):
        import pwd
        return pwd.getpwuid(int(os.environ.get('PKEXEC_UID'))).pw_name

    return None

def open_apps(mode_name, modes_db):
    print(f"\n[BACKEND] Triggered {mode_name}...")

    mode_data = modes_db.get(mode_name)
    if not mode_data:
        print(f" -> Error: Mode {mode_name} not found in DB.")
        return

    resources = mode_data.get("apps", [])
    real_user = get_real_user()

    for path in resources:
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Linux":
                if real_user:
                    cmd = ['sudo', '-u', real_user, 'xdg-open', path]
                else:
                    cmd = ['xdg-open', path]

                subprocess.Popen(
                    cmd,
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            print(f" -> Opened: {path}")
        except Exception as e:
            print(f" -> ERROR opening {path}: {e}")


def run_listener(modes_db, stop_event):
    print("--- LISTENER THREAD STARTED ---")

    while not stop_event.is_set():

        if keyboard.is_pressed('ctrl+space'):
            print("[BACKEND] Wake Key Detected! Waiting for command...")

            event = keyboard.read_event()
            if event.event_type == keyboard.KEY_DOWN:
                pressed_key = event.name.lower()

                found = False
                for name, data in modes_db.items():
                    if data['key'] == pressed_key:
                        t = threading.Thread(target=open_apps, args=(name, modes_db))
                        t.daemon = True
                        t.start()
                        found = True
                        break

                if not found:
                    print(f" -> No mode assigned to key: {pressed_key}")

            time.sleep(0.5)  # Anti-bounce sleep

        time.sleep(0.05)  # CPU Rest

    print("--- LISTENER THREAD STOPPED ---")