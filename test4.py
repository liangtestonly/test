#updatemap.py
import os
import sys
import threading
import time
import json
from livereload import Server
import webview

# Locate map window settings next to the executable if compiled, otherwise next to this script file
if getattr(sys, 'frozen', False):
    SETTINGS_FILE = os.path.join(os.path.dirname(sys.executable), "map_window_settings.json")
else:
    SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "map_window_settings.json")

def save_window_settings(x=None, y=None, width=None, height=None):
    try:
        # Ignore minimized/invalid/offscreen values from Windows sentinel coordinates (e.g. -32000)
        # We use -15000 to allow valid negative coordinates in multi-monitor setups (e.g. -1920)
        if x is not None and int(x) < -15000: return
        if y is not None and int(y) < -15000: return
        if width is not None and int(width) < 100: return
        if height is not None and int(height) < 100: return

        settings = {}
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    settings = json.load(f)
            except Exception:
                pass
        
        if x is not None: settings["x"] = int(x)
        if y is not None: settings["y"] = int(y)
        if width is not None: settings["width"] = int(width)
        if height is not None: settings["height"] = int(height)
        
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f)
    except Exception as e:
        print("Error saving map window settings:", e)

# Start livereload server in a background thread
def run_server():
    try:
        server = Server()
        server.watch("missile_warning_map.html")
        server.serve(root='.', default_filename="missile_warning_map.html", port=5500)
    except Exception as e:
        print("LiveReload server already running or port in use, using existing server.")

t = threading.Thread(target=run_server, daemon=True)
t.start()

# Wait a brief moment to let server bind (if it's starting)
time.sleep(0.5)

# Load saved settings
start_x, start_y = None, None
start_width, start_height = 800, 600

if os.path.exists(SETTINGS_FILE):
    try:
        with open(SETTINGS_FILE, "r") as f:
            settings = json.load(f)
            if "x" in settings and settings["x"] is not None and int(settings["x"]) >= -15000:
                start_x = int(settings["x"])
            if "y" in settings and settings["y"] is not None and int(settings["y"]) >= -15000:
                start_y = int(settings["y"])
            if "width" in settings and settings["width"] is not None and int(settings["width"]) >= 100:
                start_width = int(settings["width"])
            if "height" in settings and settings["height"] is not None and int(settings["height"]) >= 100:
                start_height = int(settings["height"])
    except Exception as e:
        print("Error loading map window settings:", e)

# Open modern native webview windows on the main thread
try:
    win = webview.create_window(
        "Missile Warning Map - Live Display",
        "http://127.0.0.1:5500/",
        x=start_x,
        y=start_y,
        width=start_width,
        height=start_height
    )
    
    win2 = webview.create_window(
        "Target Area Zoom Map",
        "http://127.0.0.1:5500/local_zoom_map.html",
        width=520,
        height=380
    )
    
    def on_moved(*args):
        x = args[0] if len(args) > 0 else win.x
        y = args[1] if len(args) > 1 else win.y
        save_window_settings(x=x, y=y)

    def on_resized(*args):
        width = args[0] if len(args) > 0 else win.width
        height = args[1] if len(args) > 1 else win.height
        save_window_settings(width=width, height=height)

    win.events.moved += on_moved
    win.events.resized += on_resized

    webview.start(private_mode=False)
except Exception as e:
    print("Error starting map browser window:", e)
