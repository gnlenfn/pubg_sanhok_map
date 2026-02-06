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

CONFIG_VERSION = "1.2"

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
            self.root.iconbitmap(self.resource_path("assets/icon.ico"))
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

        # Distance measurement state
        self.calibration_mode = False
        self.measurement_mode = False
        self.calibration_points = []
        self.measurement_points = []
        self.measurement_line = None
        self.measurement_text = None

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
            "open_settings": "<f12>",
            "measure_distance": "\\",
            "calibrate_mode": "<shift>+\\"
        }
        self.config["Calibration"] = {
            "pixels_per_km": "0.0"
        }
        with open(self.config_file, "w") as configfile:
            self.config.write(configfile)

    def setup_hotkeys(self):
        if self.listener:
            self.listener.stop()

        self.hotkey_visible = self.config.get("Hotkeys", "toggle_visibility", fallback="<f8>")
        self.hotkey_settings = self.config.get("Hotkeys", "open_settings", fallback="<f12>")
        self.hotkey_measure = self.config.get("Hotkeys", "measure_distance", fallback="\\")
        self.hotkey_calibrate = self.config.get("Hotkeys", "calibrate_mode", fallback="<shift>+\\")

        try:
            self.listener = keyboard.GlobalHotKeys({
                self.hotkey_visible: lambda: self.root.after(0, self.toggle_visibility),
                self.hotkey_settings: lambda: self.root.after(0, self.open_settings_window),
                self.hotkey_measure: lambda: self.root.after(0, self.toggle_measurement_mode),
                self.hotkey_calibrate: lambda: self.root.after(0, self.start_calibration_mode)
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
            self.settings_window.iconbitmap(icon_path)
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

    def start_calibration_mode(self):
        """Start calibration mode to set 1km baseline"""
        print("Calibration mode started. Click two points 1km apart.")
        self.calibration_mode = True
        self.calibration_points = []
        
        # Hide overlay during calibration
        if self.image_item:
            self.canvas.delete(self.image_item)
            self.image_item = None
        
        # Disable click-through temporarily
        if platform.system() == "Windows":
            try:
                hwnd = windll.user32.GetParent(self.root.winfo_id())
                style = windll.user32.GetWindowLongW(hwnd, -20)
                # Remove WS_EX_TRANSPARENT and WS_EX_NOACTIVATE
                style = style & ~0x20 & ~0x08000000
                windll.user32.SetWindowLongW(hwnd, -20, style)
                
                # Force window to be visible and receive clicks
                windll.user32.ShowWindow(hwnd, 5)  # SW_SHOW
                windll.user32.BringWindowToTop(hwnd)
                windll.user32.UpdateWindow(hwnd)
                self.root.focus_force()
            except Exception as e:
                print(f"Failed to disable click-through: {e}")
        
        # Unbind first to prevent duplicate bindings
        try:
            self.root.unbind("<Home>")
        except:
            pass
            
        # Bind keyboard for marking points (Home key)
        self.root.bind("<Home>", self.handle_mark_point)
        print(f"[DEBUG] Calibration mode: Home key bound, calibration_mode={self.calibration_mode}")
        print(f"[DEBUG] Current focus: {self.root.focus_get()}")
        
        # Create a semi-transparent overlay to capture clicks (black is transparent, so use gray)
        self.calibration_overlay = self.canvas.create_rectangle(
            0, 0, self.screen_width, self.screen_height,
            fill="gray", stipple="gray25", outline=""
        )
        

    def toggle_measurement_mode(self):
        """Toggle measurement mode on/off"""
        if self.measurement_mode:
            # Exit measurement mode
            self.exit_measurement_mode()
        else:
            # Enter measurement mode
            pixels_per_km = self.config.getfloat("Calibration", "pixels_per_km", fallback=0.0)
            if pixels_per_km <= 0:
                print("Please calibrate 1km baseline first!")
                return
            
            print("Measurement mode started. Click two points to measure distance.")
            self.measurement_mode = True
            self.measurement_points = []
            
            # Hide overlay during measurement
            if self.image_item:
                self.canvas.delete(self.image_item)
                self.image_item = None
            
            # Disable click-through temporarily
            if platform.system() == "Windows":
                try:
                    hwnd = windll.user32.GetParent(self.root.winfo_id())
                    style = windll.user32.GetWindowLongW(hwnd, -20)
                    # Remove WS_EX_TRANSPARENT and WS_EX_NOACTIVATE
                    style = style & ~0x20 & ~0x08000000
                    windll.user32.SetWindowLongW(hwnd, -20, style)
                    
                    # Force window to be visible and receive clicks
                    windll.user32.ShowWindow(hwnd, 5)  # SW_SHOW
                    windll.user32.BringWindowToTop(hwnd)
                    windll.user32.UpdateWindow(hwnd)
                    self.root.focus_force()
                except Exception as e:
                    print(f"Failed to disable click-through: {e}")
            
            
            # Unbind first to prevent duplicate bindings
            try:
                self.root.unbind("<Home>")
            except:
                pass
            
            # Bind keyboard for marking points (Home key)
            self.root.bind("<Home>", self.handle_mark_point)
            print(f"[DEBUG] Measurement mode: Home key bound, measurement_mode={self.measurement_mode}")
            print(f"[DEBUG] Current focus: {self.root.focus_get()}")
            
            # Create a semi-transparent overlay to capture clicks
            self.measurement_overlay = self.canvas.create_rectangle(
                0, 0, self.screen_width, self.screen_height,
                fill="gray", stipple="gray25", outline=""
            )


    def handle_mark_point(self, event):
        """Handle keyboard press to mark point at current cursor position"""
        print(f"[DEBUG] Mark point key pressed!")
        # Get current mouse position relative to screen
        x = self.root.winfo_pointerx() - self.root.winfo_rootx()
        y = self.root.winfo_pointery() - self.root.winfo_rooty()
        
        # Create a fake mouse event with cursor position
        class FakeEvent:
            pass
        
        fake_event = FakeEvent()
        fake_event.x = x
        fake_event.y = y
        
        # Call the existing click handler
        self.handle_canvas_click(fake_event)

    def handle_canvas_click(self, event):
        """Handle canvas clicks for calibration and measurement modes"""
        print(f"[DEBUG] handle_canvas_click called: calibration_mode={self.calibration_mode}, measurement_mode={self.measurement_mode}")
        if self.calibration_mode:
            print(f"[Calibration] Click registered at ({event.x}, {event.y}) - Point {len(self.calibration_points) + 1}/2")
            self.calibration_points.append((event.x, event.y))
            
            # Draw marker
            marker_size = 4
            self.canvas.create_oval(
                event.x - marker_size, event.y - marker_size,
                event.x + marker_size, event.y + marker_size,
                fill="red", outline="white", width=2
            )
            
            if len(self.calibration_points) == 2:
                # Calculate pixel distance
                x1, y1 = self.calibration_points[0]
                x2, y2 = self.calibration_points[1]
                pixel_distance = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                
                # Draw line
                self.canvas.create_line(x1, y1, x2, y2, fill="red", width=3)
                
                # Save to config
                self.config.set("Calibration", "pixels_per_km", str(pixel_distance))
                self.save_config_file()
                
                print(f"Calibration complete: 1km = {pixel_distance:.2f} pixels")
                
                # Exit calibration mode after 0.5 seconds
                self.root.after(500, self.exit_calibration_mode)
        
        elif self.measurement_mode:
            print(f"[Measurement] Click registered at ({event.x}, {event.y}) - Point {len(self.measurement_points) + 1}/2")
            self.measurement_points.append((event.x, event.y))
            
            # Draw marker
            marker_size = 4
            self.canvas.create_oval(
                event.x - marker_size, event.y - marker_size,
                event.x + marker_size, event.y + marker_size,
                fill="#FF3250", outline="white", width=2
            )
            
            if len(self.measurement_points) == 2:
                # Calculate and display distance
                distance_m = self.calculate_distance(
                    self.measurement_points[0],
                    self.measurement_points[1]
                )
                
                x1, y1 = self.measurement_points[0]
                x2, y2 = self.measurement_points[1]
                
                # Draw line
                self.measurement_line = self.canvas.create_line(
                    x1, y1, x2, y2, fill="#FF3250", width=3
                )
                
                # Display distance text next to line
                mid_x = (x1 + x2) / 2
                mid_y = (y1 + y2) / 2
                self.measurement_text = self.canvas.create_text(
                    mid_x + 20, mid_y - 20,
                    text=f"{distance_m:.0f}m",
                    fill="#FF3250", font=("Arial", 20, "bold"),
                    anchor="w"
                )
                
                print(f"Distance: {distance_m:.0f}m")
                
                # Exit measurement mode immediately and pass distance data to redraw
                line_id, text_id = self.exit_measurement_mode(keep_visuals=True, 
                    distance_data=(x1, y1, x2, y2, distance_m))
                
                # Clear distance visuals after 3 seconds
                self.root.after(3000, lambda: self.clear_distance_visuals(line_id, text_id))

    def calculate_distance(self, point1, point2):
        """Calculate real-world distance in meters between two points"""
        x1, y1 = point1
        x2, y2 = point2
        pixel_distance = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
        
        pixels_per_km = self.config.getfloat("Calibration", "pixels_per_km", fallback=1.0)
        distance_km = pixel_distance / pixels_per_km
        distance_m = distance_km * 1000
        
        return distance_m

    def exit_calibration_mode(self):
        """Exit calibration mode and restore overlay"""
        self.calibration_mode = False
        self.calibration_points = []
        self.root.unbind("<Home>")
        self.canvas.delete("all")
        
        # Restore click-through
        if platform.system() == "Windows":
            self.set_click_through()
        
        # Restore overlay
        self.update_image()
        print("Calibration mode exited.")

    def exit_measurement_mode(self, keep_visuals=False, distance_data=None):
        """Exit measurement mode and restore overlay"""
        self.measurement_mode = False
        self.measurement_points = []
        
        # Only unbind if not keeping visuals (fully exiting)
        if not keep_visuals:
            self.root.unbind("<Home>")
        
        # Always delete all canvas items (overlay, markers, old visuals)
        self.canvas.delete("all")
        
        # Restore click-through
        if platform.system() == "Windows":
            self.set_click_through()
        
        # Restore overlay
        self.update_image()
        
        # Redraw distance visuals if keeping them
        if keep_visuals and distance_data:
            x1, y1, x2, y2, distance_m = distance_data
            
            # Redraw line
            line_id = self.canvas.create_line(
                x1, y1, x2, y2, fill="#FF3250", width=3
            )
            
            # Redraw text
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            text_id = self.canvas.create_text(
                mid_x + 20, mid_y - 20,
                text=f"{distance_m:.0f}m",
                fill="#FF3250", font=("Arial", 20, "bold"),
                anchor="w"
            )
            
            print("Measurement mode exited.")
            return line_id, text_id
        else:
            self.measurement_line = None
            self.measurement_text = None
            print("Measurement mode exited.")
            return None, None
    
    def clear_distance_visuals(self, line_id, text_id):
        """Clear distance measurement visuals after delay"""
        try:
            if line_id:
                self.canvas.delete(line_id)
            if text_id:
                self.canvas.delete(text_id)
        except:
            pass  # Canvas item may already be deleted

    def open_settings_window(self):
        if hasattr(self, 'settings_window') and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return

        self.settings_window = tk.Toplevel(self.root)
        self.settings_window.title("Settings")
        self.settings_window.geometry("450x600")
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
        style.configure("TNotebook", background=BG_COLOR, borderwidth=0)
        style.configure("TNotebook.Tab", background="#444444", foreground=FG_COLOR, padding=[10, 5])
        style.map("TNotebook.Tab", background=[("selected", ACCENT_COLOR)])

        # --- Main Container ---
        main_frame = ttk.Frame(self.settings_window, style="TFrame")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        ttk.Label(main_frame, text="Settings", style="Header.TLabel").pack(anchor="w", pady=(0, 20))

        # Buttons (Bottom) - Pack *before* notebook to ensure visibility
        btn_frame = ttk.Frame(main_frame, style="TFrame")
        btn_frame.pack(side="bottom", fill="x", pady=(20, 0))
        
        save_btn = ttk.Button(btn_frame, text="Save", command=self.save_settings, style="Accent.TButton")
        save_btn.pack(side="left", expand=True, fill="x", padx=(0, 5), ipady=5)
        
        close_btn = ttk.Button(btn_frame, text="Close", command=self.settings_window.destroy, style="TButton")
        close_btn.pack(side="left", expand=True, fill="x", padx=(5, 0), ipady=5)

        # --- Tabbed Interface ---
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill="both", expand=True)

        # === Tab 1: 사녹 (Sanhok - Existing Settings) ===
        sanhok_tab = ttk.Frame(notebook, style="TFrame")
        notebook.add(sanhok_tab, text="사녹")

        # Mode
        mode_frame = ttk.LabelFrame(sanhok_tab, text="Resolution Mode", padding=10)
        mode_frame.pack(fill="x", pady=10, padx=10)
        
        if not hasattr(self, 'var_mode'):
            self.var_mode = tk.StringVar(value=self.mode)
        else:
            self.var_mode.set(self.mode)
            
        ttk.Radiobutton(mode_frame, text="QHD (1440p)", variable=self.var_mode, value="QHD").pack(side="left", padx=10)
        ttk.Radiobutton(mode_frame, text="FHD (1080p)", variable=self.var_mode, value="FHD").pack(side="left", padx=10)

        # Calibration
        calib_frame = ttk.LabelFrame(sanhok_tab, text="Calibration", padding=10)
        calib_frame.pack(fill="x", pady=10, padx=10)
        
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
        hk_frame = ttk.LabelFrame(sanhok_tab, text="Hotkeys", padding=10)
        hk_frame.pack(fill="x", pady=10, padx=10)

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

        # === Tab 2: 거리 측정 (Distance Measurement) ===
        distance_tab = ttk.Frame(notebook, style="TFrame")
        notebook.add(distance_tab, text="거리 측정")

        # Calibration Status
        calib_status_frame = ttk.LabelFrame(distance_tab, text="1km 기준선 설정", padding=10)
        calib_status_frame.pack(fill="x", pady=10, padx=10)

        pixels_per_km = self.config.getfloat("Calibration", "pixels_per_km", fallback=0.0)
        status_text = "설정됨" if pixels_per_km > 0 else "미설정"
        self.calib_status_label = ttk.Label(calib_status_frame, text=f"상태: {status_text}")
        self.calib_status_label.pack(anchor="w", pady=5)

        if pixels_per_km > 0:
            ttk.Label(calib_status_frame, text=f"1km = {pixels_per_km:.2f} pixels").pack(anchor="w", pady=5)

        ttk.Button(calib_status_frame, text="1km 기준선 설정", 
                   command=self.start_calibration_mode, style="Accent.TButton").pack(fill="x", pady=10)

        # Calibration Hotkey
        calib_hk_frame = ttk.LabelFrame(distance_tab, text="기준선 설정 단축키", padding=10)
        calib_hk_frame.pack(fill="x", pady=5, padx=10)
        
        f_calib = ttk.Frame(calib_hk_frame, style="TFrame")
        f_calib.pack(fill="x", pady=5)
        ttk.Label(f_calib, text="기준선 모드").pack(side="left")
        
        current_calib_key = self.config.get("Hotkeys", "calibrate_mode", fallback="<shift>+\\")
        calib_entry = ttk.Entry(f_calib, width=15)
        calib_entry.insert(0, current_calib_key)
        calib_entry.pack(side="right")
        
        calib_entry.bind("<FocusIn>", lambda event: calib_entry.selection_range(0, tk.END))
        calib_entry.bind("<KeyPress>", lambda event: self.capture_key(event, calib_entry))
        calib_entry.bind("<KeyRelease>", lambda event: "break")
        
        self.entries["calibrate_mode"] = calib_entry

        # Measurement Hotkey
        measure_hk_frame = ttk.LabelFrame(distance_tab, text="측정 모드 단축키", padding=10)
        measure_hk_frame.pack(fill="x", pady=5, padx=10)

        f = ttk.Frame(measure_hk_frame, style="TFrame")
        f.pack(fill="x", pady=5)
        ttk.Label(f, text="측정 모드").pack(side="left")

        current_measure_key = self.config.get("Hotkeys", "measure_distance", fallback="\\")
        measure_entry = ttk.Entry(f, width=15)
        measure_entry.insert(0, current_measure_key)
        measure_entry.pack(side="right")

        measure_entry.bind("<FocusIn>", lambda event: measure_entry.selection_range(0, tk.END))
        measure_entry.bind("<KeyPress>", lambda event: self.capture_key(event, measure_entry))
        measure_entry.bind("<KeyRelease>", lambda event: "break")

        self.entries["measure_distance"] = measure_entry

        # Instructions
        info_frame = ttk.LabelFrame(distance_tab, text="사용 방법", padding=10)
        info_frame.pack(fill="x", pady=10, padx=10)
        
        instructions = [
            "1. 먼저 '1km 기준선 설정' 버튼을 클릭",
            "2. 게임 내 1km 떨어진 두 지점을 클릭",
            "3. 측정 모드 단축키를 눌러 거리 측정 시작",
            "4. 측정하려는 두 지점을 클릭하면 거리 표시"
        ]
        for instruction in instructions:
            ttk.Label(info_frame, text=instruction, font=("Segoe UI", 9)).pack(anchor="w", pady=2)



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
        elif key == "backslash":
             formatted_key = "\\"
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