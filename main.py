import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
from pynput import keyboard
import platform
import configparser
import os
import sys
import threading
import pystray
import ctypes
if platform.system() == "Windows":
    from ctypes import windll, wintypes

CONFIG_VERSION = "1.0"

class OverlayApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Map Overlay")
        
        # Determine Config Path
        self.set_config_path()
        
        # Load Config
        self.config = configparser.ConfigParser()
        self.load_config()

        # Window setup for transparency and fullscreen
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True) # Remove window borders
        
        # Set Window Icon (Taskbar)
        try:
            self.root.iconbitmap(self.resource_path("icon.ico"))
        except:
            pass
        
        # Windows Click-Through & Focus Settings
        if platform.system() == "Windows":
             self.set_click_through()
        
        # Mac-specific transparency
        if platform.system() == 'Darwin':
            self.root.wm_attributes("-transparent", True)
            self.root.config(bg='systemTransparent')
        else:
            # Windows fallback
            self.root.wm_attributes("-transparentcolor", "black")
            self.root.config(bg='black')

        # Get screen dimensions
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        self.root.geometry(f"{self.screen_width}x{self.screen_height}+0+0")

        # Load Overlay Image
        img_path = self.resource_path("assets/overlay_circle.png")
        try:
            self.original_image = Image.open(img_path)
        except FileNotFoundError:
            print(f"Error: {img_path} not found.")
            self.root.destroy()
            return
        
        # Settings
        self.is_visible = True
        self.mode = self.config.get("Settings", "mode", fallback="QHD")
        
        # Scaling factors
        # Scaling factors - Now handled dynamically in get_base_scale
        # self.scale_qhd = 1440 / 2475 * 0.9 
        # self.scale_fhd = 1080 / 2475 * 0.9 

        self.canvas = tk.Canvas(self.root, width=self.screen_width, height=self.screen_height, 
                                bg='systemTransparent' if platform.system() == 'Darwin' else 'black', 
                                highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.image_item = None
        self.update_image()

        # Initial hotkey setup
        self.listener = None
        self.setup_hotkeys()

        # System Tray (Windows Only)
        if platform.system() == "Windows":
            self.tray_thread = threading.Thread(target=self.setup_tray, daemon=True)
            self.tray_thread.start()

        print("Overlay Started.")
        print(f"Config loaded from: {self.config_file}")
        print("Press F12 to open Settings.")

    def set_config_path(self):
        app_name = "PUBG_Map_Overlay"
        system = platform.system()
        
        if system == "Windows":
            base_dir = os.getenv("LOCALAPPDATA")
            if not base_dir: # Fallback
                base_dir = os.path.expanduser("~\\AppData\\Local")
        elif system == "Darwin":
            base_dir = os.path.expanduser("~/Library/Application Support")
        else: # Linux/Other
            base_dir = os.path.expanduser("~/.config")
            
        self.config_dir = os.path.join(base_dir, app_name)
        
        # Create directory if it doesn't exist
        os.makedirs(self.config_dir, exist_ok=True)
        self.config_file = os.path.join(self.config_dir, "config.ini")

    def resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    def load_config(self):
        if not os.path.exists(self.config_file):
            self.create_default_config()
        else:
            self.config.read(self.config_file)
            # Check version
            if self.config.get("Settings", "version", fallback="0.0") != CONFIG_VERSION:
                print("Config version mismatch. Recreating config.")
                self.create_default_config()
            
        if not self.config.has_section("Settings") or not self.config.has_section("Hotkeys"):
            self.create_default_config()

    def create_default_config(self):
        self.config["Settings"] = {"mode": "QHD", "version": CONFIG_VERSION}
        self.config["Hotkeys"] = {
            "toggle_visibility": "<f8>",
            "open_settings": "<f12>"
        }
        with open(self.config_file, "w") as configfile:
            self.config.write(configfile)

    def setup_hotkeys(self):
        if self.listener:
            self.listener.stop()

        self.hotkey_visible = self.config.get("Hotkeys", "toggle_visibility", fallback="<f8>")
        self.hotkey_settings = self.config.get("Hotkeys", "open_settings", fallback="<f12>")

        try:
            self.listener = keyboard.GlobalHotKeys({
                self.hotkey_visible: self.toggle_visibility,
                self.hotkey_settings: self.open_settings_window
            })
            self.listener.start()
        except ValueError as e:
            print(f"Error setting up hotkeys: {e}")

    def set_click_through(self):
        try:
            # GWL_EXSTYLE = -20
            # WS_EX_LAYERED = 0x80000
            # WS_EX_TRANSPARENT = 0x20
            # WS_EX_NOACTIVATE = 0x08000000 (Prevents stealing focus)
            
            hwnd = windll.user32.GetParent(self.root.winfo_id())
            style = windll.user32.GetWindowLongW(hwnd, -20)
            style = style | 0x80000 | 0x20 | 0x08000000
            windll.user32.SetWindowLongW(hwnd, -20, style)
        except Exception as e:
            print(f"Failed to set click-through: {e}")

    def setup_tray(self):
        # Try to load custom icon, fallback to overlay circle if missing
        try:
            icon_path = self.resource_path("assets/icon.ico")
            image = Image.open(icon_path)
        except:
             image = Image.open(self.resource_path("assets/overlay_circle.png"))

        menu = pystray.Menu(
            pystray.MenuItem("Settings", self.open_settings_from_tray),
            pystray.MenuItem("Quit", self.quit_app_tray)
        )
        self.icon = pystray.Icon("PUBG Overlay", image, "PUBG Map Overlay", menu)
        self.icon.run()

    def open_settings_from_tray(self, icon, item):
        self.root.after(0, self.open_settings_window)

    def quit_app_tray(self, icon, item):
        self.root.after(0, self.quit_app)

    def get_base_scale(self):
        # Calculate base scale based on mode (Target Height / Image Height)
        # Image height is 2475
        target_height = 1440 if self.mode == "QHD" else 1080
        return target_height / 2475

    def update_image(self):
        # Get calibration values
        scale_factor = self.config.getfloat("Settings", "scale_factor", fallback=1.0)
        offset_x = self.config.getint("Settings", "offset_x", fallback=0)
        offset_y = self.config.getint("Settings", "offset_y", fallback=0)

        base_scale = self.get_base_scale()
        final_scale = base_scale * scale_factor
            
        new_width = int(self.original_image.width * final_scale)
        new_height = int(self.original_image.height * final_scale)
        
        # Optimization: Only resize if dimensions changed significantly
        if not hasattr(self, '_cached_image_dims') or self._cached_image_dims != (new_width, new_height):
             resized_img = self.original_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
             self.tk_image = ImageTk.PhotoImage(resized_img)
             self._cached_image_dims = (new_width, new_height)
        
        # Center of screen + Offset
        x = (self.screen_width // 2) + offset_x
        y = (self.screen_height // 2) + offset_y
        
        if self.image_item:
            self.canvas.delete(self.image_item)
            
        if self.is_visible:
            self.image_item = self.canvas.create_image(x, y, image=self.tk_image, anchor=tk.CENTER)

    def toggle_visibility(self):
        self.is_visible = not self.is_visible
        if self.is_visible:
            self.root.deiconify()
            if platform.system() == "Windows":
                # Re-apply properties if needed upon showing
                self.set_click_through()
            self.update_image()
        else:
            self.root.withdraw()


    def quit_app(self):
        print("Exiting...")
        try:
            if hasattr(self, 'icon'):
                self.icon.stop()
        except:
            pass
            
        try:
            if self.listener:
                self.listener.stop()
        except:
            pass

        self.root.quit()
        self.root.destroy()
        sys.exit(0)

    def open_settings_window(self):
        if hasattr(self, 'settings_window') and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return

        self.settings_window = tk.Toplevel(self.root)
        self.settings_window.title("Settings")
        self.settings_window.geometry("400x550")
        self.settings_window.attributes("-topmost", True)
        self.settings_window.configure(bg="#2b2b2b") # Dark Background

        # --- Style Configuration ---
        style = ttk.Style(self.settings_window)
        style.theme_use('clam') 

        # Colors
        BG_COLOR = "#2b2b2b"
        FG_COLOR = "#ffffff"
        ACCENT_COLOR = "#0078d4" 
        ENTRY_BG = "#3a3a3a"
        
        style.configure("TFrame", background=BG_COLOR)
        style.configure("TLabel", background=BG_COLOR, foreground=FG_COLOR, font=("Segoe UI", 10))
        style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("TLabelframe", background=BG_COLOR, bordercolor="#444444")
        style.configure("TLabelframe.Label", background=BG_COLOR, foreground=FG_COLOR, font=("Segoe UI", 10, "bold"))
        style.configure("TRadiobutton", background=BG_COLOR, foreground=FG_COLOR, indicatorcolor=BG_COLOR, selectcolor=ACCENT_COLOR, font=("Segoe UI", 10))
        style.map("TRadiobutton", indicatorcolor=[("selected", ACCENT_COLOR)])
        style.configure("TEntry", fieldbackground=ENTRY_BG, foreground=FG_COLOR, insertcolor=FG_COLOR, borderwidth=0)
        style.configure("TButton", background="#444444", foreground=FG_COLOR, borderwidth=0, focuscolor=BG_COLOR, font=("Segoe UI", 10))
        style.map("TButton", background=[("active", "#555555")])
        style.configure("Accent.TButton", background=ACCENT_COLOR, foreground=FG_COLOR)
        style.map("Accent.TButton", background=[("active", "#006cc1")])

        # --- Content (Simple Layout) ---
        
        # Main Container with Padding
        main_frame = ttk.Frame(self.settings_window, style="TFrame")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        ttk.Label(main_frame, text="Settings", style="Header.TLabel").pack(anchor="w", pady=(0, 20))

        # Mode
        mode_frame = ttk.LabelFrame(main_frame, text="Resolution Mode", padding=10)
        mode_frame.pack(fill="x", pady=10)
        
        if not hasattr(self, 'var_mode'):
            self.var_mode = tk.StringVar(value=self.mode)
        else:
            self.var_mode.set(self.mode)
            
        ttk.Radiobutton(mode_frame, text="QHD (1440p)", variable=self.var_mode, value="QHD").pack(side="left", padx=10)
        ttk.Radiobutton(mode_frame, text="FHD (1080p)", variable=self.var_mode, value="FHD").pack(side="left", padx=10)

        # Calibration
        calib_frame = ttk.LabelFrame(main_frame, text="Calibration", padding=10)
        calib_frame.pack(fill="x", pady=10)
        
        defaults = {"scale_factor": 1.0, "offset_x": 0, "offset_y": 0}
        for label, var_name, conf_key, is_float in [
            ("Scale Factor", "var_scale", "scale_factor", True),
            ("Offset X", "var_off_x", "offset_x", False),
            ("Offset Y", "var_off_y", "offset_y", False)
        ]:
            frame = ttk.Frame(calib_frame, style="TFrame")
            frame.pack(fill="x", pady=5)
            ttk.Label(frame, text=label).pack(side="left")
            
            fb = defaults[conf_key]
            if is_float:
                val = self.config.getfloat("Settings", conf_key, fallback=fb)
            else:
                val = self.config.getint("Settings", conf_key, fallback=fb)
                
            if not hasattr(self, var_name):
                 setattr(self, var_name, tk.DoubleVar(value=val) if is_float else tk.IntVar(value=val))
            
            ttk.Entry(frame, textvariable=getattr(self, var_name), width=10).pack(side="right")

        # Hotkeys
        hk_frame = ttk.LabelFrame(main_frame, text="Hotkeys", padding=10)
        hk_frame.pack(fill="x", pady=10)

        self.entries = {}
        for name, label in [("toggle_visibility", "Toggle On/Off"), 
                            ("open_settings", "Open Settings")]:
            
            f = ttk.Frame(hk_frame, style="TFrame")
            f.pack(fill="x", pady=5)
            ttk.Label(f, text=label).pack(side="left")
            
            current_key = self.config.get("Hotkeys", name)
            entry = ttk.Entry(f, width=15)
            entry.insert(0, current_key)
            entry.pack(side="right")
            
            entry.bind("<FocusIn>", lambda event, e=entry: e.selection_range(0, tk.END))
            entry.bind("<KeyPress>", lambda event, e=entry: self.capture_key(event, e))
            entry.bind("<KeyRelease>", lambda event: "break")
            
            self.entries[name] = entry

        # Buttons (Simple Pack at Bottom)
        btn_frame = ttk.Frame(main_frame, style="TFrame")
        btn_frame.pack(side="bottom", fill="x", pady=(20, 0))
        
        save_btn = ttk.Button(btn_frame, text="Save", command=self.save_settings, style="Accent.TButton")
        save_btn.pack(side="left", expand=True, fill="x", padx=(0, 5), ipady=5)
        
        close_btn = ttk.Button(btn_frame, text="Close", command=self.settings_window.destroy, style="TButton")
        close_btn.pack(side="left", expand=True, fill="x", padx=(5, 0), ipady=5)

    def capture_key(self, event, entry_widget):
        # Ignore modifier keys by themselves
        if event.keysym.lower() in ["control_l", "control_r", "alt_l", "alt_r", "shift_l", "shift_r", "caps_lock"]:
            return "break"
        
        parts = []
        
        # Check modifiers
        # State bitmasks can vary, but generally:
        # Shift: 0x0001
        # Control: 0x0004
        # Alt: 0x0008 or 0x20000 depending on OS/Key
        
        state = event.state
        
        # Helper to detect modifiers robustly
        # Windows: Alt=0x20000, Ctrl=0x0004, Shift=0x0001
        
        is_ctrl = (state & 0x0004) != 0
        is_shift = (state & 0x0001) != 0
        
        # Strict Alt check for Windows (0x20000)
        if platform.system() == "Windows":
            is_alt = (state & 0x20000) != 0
        else:
            # Fallback for Mac/Linux
            is_alt = (state & 0x0008) != 0 or (state & 0x0010) != 0 
        
        if is_ctrl: parts.append("<ctrl>")
        if is_alt: parts.append("<alt>")
        if is_shift: parts.append("<shift>")
        
        key = event.keysym.lower()
        
        # Format the main key
        if "f" in key and len(key) > 1 and key[1:].isdigit():
             formatted_key = f"<{key}>"
        elif key == "escape":
             formatted_key = "<esc>"
        else:
             formatted_key = key
             
        parts.append(formatted_key)
        
        final_hotkey = "+".join(parts)
            
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, final_hotkey)
        return "break"

    def apply_calibration(self):
        try:
            # Update config variables
            self.config.set("Settings", "scale_factor", str(self.var_scale.get()))
            self.config.set("Settings", "offset_x", str(self.var_off_x.get()))
            self.config.set("Settings", "offset_y", str(self.var_off_y.get()))
        except ValueError:
            messagebox.showerror("Error", "Invalid calibration values")

    def save_settings(self):
        new_mode = self.var_mode.get()
        if new_mode != self.mode:
            self.mode = new_mode
            self.config.set("Settings", "mode", self.mode)
            self.update_image()

        for name, entry in self.entries.items():
            self.config.set("Hotkeys", name, entry.get())
        
        # Calibration (Updates config object)
        self.apply_calibration()
        self.update_image()

        # Write everything to disk
        self.save_config_file()

        # Reload Hotkeys
        self.setup_hotkeys()
        
        print("Configuration Saved!")

    def save_config_file(self):
        with open(self.config_file, "w") as configfile:
            self.config.write(configfile)

if __name__ == "__main__":
    root = tk.Tk()
    app = OverlayApp(root)
    root.mainloop()