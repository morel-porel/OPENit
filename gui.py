import sys
import os
import ctypes
import platform
import launcher
import customtkinter as ctk
import threading
from tkinter import filedialog
import json
import socket
from tkinter import messagebox
import pwd
import pystray
from PIL import Image, ImageDraw

LOCK_PORT = 65432

def get_lock_socket():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(('127.0.0.1', LOCK_PORT))
        return s
    except socket.error:
        return None

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return os.getuid() == 0


def rerun_as_admin():
    if sys.platform == 'win32':
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1
        )
    else:
        args = [sys.executable] + sys.argv

        display = os.environ.get('DISPLAY', ':0')
        xauth = os.environ.get('XAUTHORITY', '')

        cmd = [
              'pkexec',
              'env',
              f'DISPLAY={display}',
              f'XAUTHORITY={xauth}'
          ] + args

        os.execvp('pkexec', cmd)

CONFIG_FILE = "config.json"

MODES_DB = {}

def get_config_file_path():
    home_dir = os.path.expanduser("~")

    if platform.system() == "Linux":
        sudo_user = os.environ.get('SUDO_USER')

        pkexec_uid = os.environ.get('PKEXEC_UID')

        real_user = None
        if sudo_user:
            real_user = sudo_user
        elif pkexec_uid:
            try:
                real_user = pwd.getpwuid(int(pkexec_uid)).pw_name
            except:
                pass

        if real_user:
            home_dir = f"/home/{real_user}"

    save_folder = os.path.join(home_dir, "Documents", "OPENitModes")

    if not os.path.exists(save_folder):
        try:
            os.makedirs(save_folder)
            if platform.system() == "Linux" and (sudo_user or pkexec_uid):
                u_info = pwd.getpwnam(real_user)
                os.chown(save_folder, u_info.pw_uid, u_info.pw_gid)
                print(f"Created config folder at: {save_folder}")
        except OSError as e:
            print(f"Error creating config folder: {e}")
            # Fallback to current directory if Documents is locked
            return "config.json"

    return os.path.join(save_folder, "modes.json")


class AddModeDialog(ctk.CTkToplevel):
    def __init__(self, parent, callback_function, full_db):
        super().__init__(parent)
        self.callback = callback_function
        self.full_db = full_db

        self.title("Create New Mode")
        self.geometry("300x280")
        self.attributes("-topmost", True)

        self.label_1 = ctk.CTkLabel(self, text="Mode Name:")
        self.label_1.pack(pady=(20, 5))
        self.name_entry = ctk.CTkEntry(self, placeholder_text="Enter name...")
        self.name_entry.pack(pady=5)

        self.label_2 = ctk.CTkLabel(self, text="Trigger Key:")
        self.label_2.pack(pady=(10, 5))
        self.key_entry = ctk.CTkEntry(self, placeholder_text="Single letter...")
        self.key_entry.pack(pady=5)

        self.error_label = ctk.CTkLabel(self, text="", text_color="#FF5555", font=("Arial", 12))
        self.error_label.pack(pady=5)

        self.save_btn = ctk.CTkButton(self, text="Save Mode", fg_color="green", command=self.save_data)
        self.save_btn.pack(pady=20)

    def save_data(self):
        name = self.name_entry.get().strip()
        key = self.key_entry.get().strip().lower()

        if not name or not key:
            self.error_label.configure(text="Please fill in all fields!")
            return

        if len(key) > 1:
            self.error_label.configure(text="Key must be a single letter!")
            return

        existing_names = [n.lower() for n in self.full_db.keys()]
        if name.lower() in existing_names:
            self.error_label.configure(text=f"Name '{name}' is taken!")
            return

        existing_keys = [data['key'] for data in self.full_db.values()]

        if key in existing_keys:
            owner = [n for n, d in self.full_db.items() if d['key'] == key][0]
            self.error_label.configure(text=f"Key '{key}' is used by '{owner}'!")
            return

        self.callback(name, key)
        self.destroy()


class ResourceTypeDialog(ctk.CTkToplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback = callback
        self.title("Select Type")
        self.geometry("300x150")
        self.attributes("-topmost", True)

        self.label = ctk.CTkLabel(self, text="What do you want to add?", font=("Arial", 14))
        self.label.pack(pady=20)

        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.pack(fill="x", padx=20)

        self.btn_file = ctk.CTkButton(self.btn_frame, text="File / App", width=120, command=lambda: self.select("file"))
        self.btn_file.pack(side="left", padx=10)

        self.btn_folder = ctk.CTkButton(self.btn_frame, text="Folder", width=120, fg_color="orange",
                                        hover_color="#D97706", command=lambda: self.select("folder"))
        self.btn_folder.pack(side="right", padx=10)

    def select(self, choice):
        self.withdraw()
        self.callback(choice)
        self.destroy()

class OPENitApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("OPENit")
        self.geometry("700x500")
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("green")

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.load_config()

        self.stop_event = threading.Event()
        self.service_running = False
        self.selected_mode = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar_frame = ctk.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(1, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Modes", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.buttons_frame = ctk.CTkScrollableFrame(self.sidebar_frame, fg_color="transparent")
        self.buttons_frame.grid(row=1, column=0, sticky="nsew")

        self.add_mode_btn = ctk.CTkButton(self.sidebar_frame, text="+ Add Mode",
                                fg_color="#8ba888", command=self.open_add_dialog)
        self.add_mode_btn.grid(row=3, column=0, padx=20, pady=10)

        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

        self.label_title = ctk.CTkLabel(self.main_frame, text="Select a mode to edit", font=ctk.CTkFont(size=16))
        self.label_title.pack(pady=20)
        self.label_key_info = ctk.CTkLabel(self.main_frame, text="", text_color="gray")
        self.label_key_info.pack(pady=5)

        self.start_button = ctk.CTkButton(self.sidebar_frame, text="Start Listener", fg_color="purple",
                                          command=self.toggle_service)
        self.start_button.grid(row=5, column=0, padx=20, pady=20)

        self.refresh_sidebar()

    def create_tray_image(self):
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), color=(30, 30, 30))
        d = ImageDraw.Draw(image)
        d.ellipse((10, 10, 54, 54), fill="#1F6AA5")
        return image

    def run_tray_icon(self):
        menu = (
            pystray.MenuItem("Open", self.show_window),
            pystray.MenuItem("Quit", self.quit_app)
        )

        self.tray_icon = pystray.Icon("name", self.create_tray_image(), "OpenIt", menu)

        self.tray_icon.run()

    def show_window(self, icon=None, item=None):
        self.tray_icon.stop()

        self.after(0, self.deiconify)

    def quit_app(self, icon=None, item=None):
        if hasattr(self, 'tray_icon'):
            self.tray_icon.stop()

        self.stop_event.set()

        self.destroy()
        import sys
        sys.exit(0)

    def on_closing(self):
        if not self.service_running:
            self.quit_app()
        else:
            if platform.system() == "Windows":
                self.withdraw()
                t = threading.Thread(target=self.run_tray_icon)
                t.daemon = True
                t.start()
            else:
                self.iconify()

    def load_config(self):
        file_path = get_config_file_path()

        if os.path.exists(file_path):
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                    MODES_DB.update(data)
                    print(f"Loaded config from: {file_path}")
            except Exception as e:
                print(f"Corrupt config file? Error: {e}")
        else:
            print("No config file found. Starting with empty database.")

    def save_config(self):
        file_path = get_config_file_path()

        try:
            with open(file_path, "w") as f:
                json.dump(MODES_DB, f, indent=4)
            print(f"Saved config to: {file_path}")
        except Exception as e:
            print(f"CRITICAL: Could not save config! {e}")

    def open_add_dialog(self):
        dialog = AddModeDialog(self, self.create_mode, MODES_DB)

    def create_mode(self, name, key):
        print(f"Creating mode: {name} with key {key}")

        MODES_DB[name] = {"key": key, "apps": []}

        self.refresh_sidebar()
        self.save_config()

    def delete_current_mode(self):
        if not self.selected_mode: return

        del MODES_DB[self.selected_mode]

        self.save_config()

        self.selected_mode = None

        for widget in self.main_frame.winfo_children():
            widget.destroy()

        self.label_title = ctk.CTkLabel(self.main_frame, text="Select a mode to edit", font=ctk.CTkFont(size=20))
        self.label_title.pack(pady=20)

        self.refresh_sidebar()

    def refresh_sidebar(self):
        for widget in self.buttons_frame.winfo_children():
            widget.destroy()

        for mode_name in MODES_DB:
            btn = ctk.CTkButton(
                self.buttons_frame,
                text=mode_name,
                command=lambda m=mode_name: self.show_mode_details(m)
            )
            btn.pack(pady=5, padx=10)

    def show_mode_details(self, mode_name):
        self.selected_mode = mode_name

        for widget in self.main_frame.winfo_children():
            widget.destroy()

        data = MODES_DB[mode_name]

        header = ctk.CTkLabel(self.main_frame, text=f"Mode: {mode_name}", font=ctk.CTkFont(size=24, weight="bold"))
        header.pack(pady=(20, 5))

        sub_header = ctk.CTkLabel(self.main_frame, text=f"Wake Key: [ {data['key'].upper()} ]", text_color="gray")
        sub_header.pack(pady=(0, 20))

        self.apps_scroll_frame = ctk.CTkScrollableFrame(self.main_frame, label_text="Applications")
        self.apps_scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.refresh_app_list_ui()

        actions_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        actions_frame.pack(pady=20, fill="x", side="bottom")

        btn_delete_mode = ctk.CTkButton(
            actions_frame,
            text="DELETE MODE",
            fg_color="transparent",
            border_width=1,
            border_color="#FF5555",
            text_color="#FF5555",
            hover_color="#550000",
            command=self.delete_current_mode
        )
        btn_delete_mode.pack(side="left", padx=20)

        btn_add = ctk.CTkButton(actions_frame, text="+ Add Application", command=self.add_app_dialog)
        btn_add.pack(side="right", padx=20, fill="x", expand=True)

    def refresh_app_list_ui(self):
        for widget in self.apps_scroll_frame.winfo_children():
            widget.destroy()

        current_apps = MODES_DB[self.selected_mode]["apps"]

        if not current_apps:
            label = ctk.CTkLabel(self.apps_scroll_frame, text="No apps added yet.", text_color="gray")
            label.pack(pady=20)
            return

        for index, app_path in enumerate(current_apps):
            row = ctk.CTkFrame(self.apps_scroll_frame)
            row.pack(fill="x", pady=2)

            app_name = os.path.basename(app_path)

            if os.path.isdir(app_path):
                display_text = f"📂 {app_name}"
            else:
                display_text = f"📄 {app_name}"

            label_name = ctk.CTkLabel(row, text=display_text, anchor="w")
            label_name.pack(side="left", padx=10)

            btn_delete = ctk.CTkButton(
                row,
                text="X",
                width=30,
                fg_color="#FF5555",
                hover_color="#990000",
                command=lambda i=index: self.remove_app(i)
            )
            btn_delete.pack(side="right", padx=5, pady=5)

    def add_app_dialog(self):
        if not self.selected_mode: return

        ResourceTypeDialog(self, self.handle_resource_selection)

    def handle_resource_selection(self, choice):
        path = ""

        if choice == "file":
            path = filedialog.askopenfilename(
                title="Select File",
                filetypes=[("All Files", "*.*")]
            )
        elif choice == "folder":
            path = filedialog.askdirectory(title="Select Folder")

        if path:
            path = os.path.normpath(path)

            MODES_DB[self.selected_mode]["apps"].append(path)
            self.refresh_app_list_ui()
            self.save_config()

    def remove_app(self, index):
        del MODES_DB[self.selected_mode]["apps"][index]
        self.refresh_app_list_ui()
        self.save_config()

    def toggle_service(self):

        if not self.service_running:
            self.service_running = True
            self.start_button.configure(text="Stop Listener", fg_color="red")

            self.stop_event.clear()

            t = threading.Thread(
                target=launcher.run_listener,
                args=(MODES_DB, self.stop_event)
            )
            t.daemon = True
            t.start()
        else:
            self.service_running = False
            self.start_button.configure(text="Start Listener", fg_color="purple")

            self.stop_event.set()


if __name__ == "__main__":
    if not is_admin():
        rerun_as_admin()
        sys.exit(0)

    lock_socket = get_lock_socket()
    if not lock_socket:
        import tkinter
        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror("Error", "OpenIt is already running!")
        sys.exit(0)

    app = OPENitApp()
    app.mainloop()