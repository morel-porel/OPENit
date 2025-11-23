import customtkinter as ctk
import threading

MODES_DB = {
    "Study": {"key": "s", "apps": []},
    "Game": {"key": "g", "apps": []}
}


class AddModeDialog(ctk.CTkToplevel):
    def __init__(self, parent, callback_function):
        super().__init__(parent)
        self.callback = callback_function

        # Window Setup
        self.title("Create New Mode")
        self.geometry("300x250")
        self.attributes("-topmost", True)  # Keep it on top

        # Layout
        self.label_1 = ctk.CTkLabel(self, text="Mode Name (e.g. Coding):")
        self.label_1.pack(pady=(20, 5))
        self.name_entry = ctk.CTkEntry(self, placeholder_text="Enter name...")
        self.name_entry.pack(pady=5)

        self.label_2 = ctk.CTkLabel(self, text="Trigger Key (e.g. 'c'):")
        self.label_2.pack(pady=(10, 5))
        self.key_entry = ctk.CTkEntry(self, placeholder_text="Single letter...")
        self.key_entry.pack(pady=5)

        self.save_btn = ctk.CTkButton(self, text="Save Mode", fg_color="green", command=self.save_data)
        self.save_btn.pack(pady=20)

    def save_data(self):
        name = self.name_entry.get()
        key = self.key_entry.get()

        # Basic Validation
        if name and key:
            # Send data back to the main app
            self.callback(name, key)
            self.destroy()  # Close the popup
        else:
            # Shake or turn red (simple print for now)
            print("Please fill both fields")

def start_automation_service():
    print("Background Service Started...")
    # This is where we will eventually call the keyboard listener logic


class OPENitApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("OPENit")
        self.geometry("600x400")
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("green")

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

        self.service_running = False

        # Initial Load
        self.refresh_sidebar()

    def open_add_dialog(self):
        # Open the popup and pass the function to run when saved
        dialog = AddModeDialog(self, self.create_mode)

    def create_mode(self, name, key):
        print(f"Creating mode: {name} with key {key}")

        # 1. Save to our 'Database'
        MODES_DB[name] = {"key": key, "apps": []}

        # 2. Refresh the UI
        self.refresh_sidebar()

    def refresh_sidebar(self):
        # Clear existing buttons
        for widget in self.buttons_frame.winfo_children():
            widget.destroy()

        # Re-create buttons from Database
        for mode_name in MODES_DB:
            btn = ctk.CTkButton(
                self.buttons_frame,
                text=mode_name,
                command=lambda m=mode_name: self.show_mode_details(m)
            )
            btn.pack(pady=5, padx=10)

    def show_mode_details(self, mode_name):
        data = MODES_DB[mode_name]
        self.label_title.configure(text=f"Editing: {mode_name}")
        self.label_key_info.configure(text=f"Wake Key: [ {data['key'].upper()} ]")

        # Later: We will show the list of apps here

    def toggle_service(self):
        if not self.service_running:
            self.service_running = True
            self.start_button.configure(text="Stop Listener", fg_color="red")

            # Run the logic in a background thread so GUI doesn't freeze
            t = threading.Thread(target=start_automation_service)
            t.daemon = True
            t.start()
        else:
            self.service_running = False
            self.start_button.configure(text="Start Listener", fg_color="purple")
            print("Service Stopped (Logic to implement)")


if __name__ == "__main__":
    app = OPENitApp()
    app.mainloop()