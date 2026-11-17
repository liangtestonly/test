#mslwarntest.py
import json
import math
import os
import random
import threading
import time
import tkinter as tk
import sys
from tkinter import messagebox
from tkinter import simpledialog

import cartopy.io.shapereader as cartopy_shapereader
import numpy as np
import shapefile

from msltest2 import EARTH_RADIUS, EARTH_RADIUS_KM, TIME_STEP, Interceptor, SimulationConfig, TargetMissile


EARTH_RADIUS_MILES = 3958.8
GUI_BUILD_TAG = ""


def read_settings_data(settings_file):
    try:
        with open(settings_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def write_settings_data(settings_file, data):
    try:
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def read_saved_window_size(data, width_key, height_key):
    try:
        width = int(data.get(width_key, 0))
        height = int(data.get(height_key, 0))
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height


class ConfigGui:
    def __init__(self):
        self.root = tk.Tk()
#        self.root.title(f"Missile Intercept Setup [{`GUI_BUILD_TAG`}]")
        self.root.title(f"Missile Intercept Setup")
        self.root.geometry("640x980")
        self.root.configure(bg="#1e1e24")

        # Automatically load custom icon if 'app_icon.ico' or 'app_icon.png' is dropped in this folder!
        script_dir = os.path.dirname(os.path.abspath(__file__))
        ico_path = os.path.join(script_dir, "app_icon.ico")
        png_path = os.path.join(script_dir, "app_icon.png")
        
        if os.path.exists(ico_path):
            try:
                self.root.iconbitmap(ico_path)
            except Exception:
                pass
        elif os.path.exists(png_path):
            try:
                from PIL import ImageTk
                img_ico = ImageTk.PhotoImage(file=png_path)
                self.root.wm_iconphoto(True, img_ico)
            except Exception:
                pass
        self.body_frame = tk.Frame(self.root, bg="#1e1e24")
        self.body_frame.pack(side="top", fill="both", expand=True)
        self.scroll_canvas = tk.Canvas(self.body_frame, bg="#1e1e24", highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self.body_frame, orient="vertical", command=self.scroll_canvas.yview)
        self.content_frame = tk.Frame(self.scroll_canvas, bg="#1e1e24")
        self.content_window = self.scroll_canvas.create_window((0, 0), window=self.content_frame, anchor="nw")
        self.scroll_canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scroll_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.content_frame.bind("<Configure>", self.on_content_configure)
        self.scroll_canvas.bind("<Configure>", self.on_canvas_configure)
        self.simulation_thread = None
        self.simulation_window = None
        self.globe_picks_window = None
        self.missile_edit_window = None
        self.pick_mode = None
        self.missile_groups = {}
        self.interceptor_groups = {}
        self.temp_group_name = None
        self.temp_num_missiles = 0
        self.temp_missile_start = None
        self.default_view_yaw_deg = -28.0
        self.default_view_pitch_deg = 18.0
        self.view_yaw_deg = self.default_view_yaw_deg
        self.view_pitch_deg = self.default_view_pitch_deg
        self.drag_last = None
        self.drag_origin = None
        self.drag_button = None
        self.drag_moved = False
        self.suppress_left_release_action = False
        self.pending_pick_job = None
        self.last_left_click_time = 0.0
        self.last_left_click_pos = None
        self.drag_render_job = None
        self.updating_view_center_fields = False
        self.is_dragging_globe = False
        self.is_dragging_target = False
        self.grabbed_target = None
        self.globe_vector_cache = {}
        self.globe_canvas_width = 520
        self.globe_canvas_height = 520
        self.globe_zoom = 1.0
        self.globe_radius_px = 235
        self.default_settings = {
            "missile_speed": 5.0,
            "interceptor_speed": 7.0,
            "proportional_gain": 4.0,
            "auto_launch_interceptor": True,
            "show_wireframe_globe": True,
            "show_boundaries": False,
            "drag_refresh_ms": 80.0,
            "missile_start_lat": 39.0,
            "missile_start_lon": 125.0,
            "missile_start_altitude_km": 0.0,
            "missile_target_lat": 38.0,
            "missile_target_lon": -77.0,
            "missile_target_altitude_km": 0.0,
            "interceptor_start_lat": 64.0,
            "interceptor_start_lon": -147.0,
            "interceptor_start_altitude_km": 0.0,
            "interceptor_delay_sec": 3.0,
        }

        self.missile_speed_var = tk.DoubleVar(value=self.default_settings["missile_speed"])
        self.interceptor_speed_var = tk.DoubleVar(value=self.default_settings["interceptor_speed"])
        self.proportional_gain_var = tk.DoubleVar(value=self.default_settings["proportional_gain"])
        self.auto_launch_var = tk.BooleanVar(value=self.default_settings["auto_launch_interceptor"])
        self.show_wireframe_var = tk.BooleanVar(value=self.default_settings["show_wireframe_globe"])
        self.show_boundaries_var = tk.BooleanVar(value=self.default_settings["show_boundaries"])
        self.offline_mode_var = tk.BooleanVar(value=self.default_settings.get("offline_mode", False))
        self.drag_refresh_ms_var = tk.DoubleVar(value=self.default_settings["drag_refresh_ms"])
        self.missile_start_lat_var = tk.DoubleVar(value=self.default_settings["missile_start_lat"])
        self.missile_start_lon_var = tk.DoubleVar(value=self.default_settings["missile_start_lon"])
        self.missile_start_altitude_var = tk.DoubleVar(value=self.default_settings["missile_start_altitude_km"])
        self.missile_target_lat_var = tk.DoubleVar(value=self.default_settings["missile_target_lat"])
        self.missile_target_lon_var = tk.DoubleVar(value=self.default_settings["missile_target_lon"])
        self.missile_target_altitude_var = tk.DoubleVar(value=self.default_settings["missile_target_altitude_km"])
        self.interceptor_start_lat_var = tk.DoubleVar(value=self.default_settings["interceptor_start_lat"])
        self.interceptor_start_lon_var = tk.DoubleVar(value=self.default_settings["interceptor_start_lon"])
        self.interceptor_start_altitude_var = tk.DoubleVar(value=self.default_settings["interceptor_start_altitude_km"])
        self.interceptor_delay_var = tk.DoubleVar(value=self.default_settings["interceptor_delay_sec"])
        self.msl_grp_delay_var = tk.DoubleVar(value=5.0)
        self.msl_delay_var = tk.DoubleVar(value=2.0)
        self.msl_path_size_var = tk.DoubleVar(value=3.0)
        self.int_path_size_var = tk.DoubleVar(value=3.0)
        self.tracking_algo_var = tk.StringVar(value="EKF")
        self.mp_mode_var = tk.BooleanVar(value=False)
        self.view_center_lat_var = tk.StringVar(value="")
        self.view_center_lon_var = tk.StringVar(value="")
        self.view_altitude_km_var = tk.StringVar(value="1")
        self.view_yaw_var = tk.StringVar(value=f"{self.view_yaw_deg:.2f}")
        self.view_pitch_var = tk.StringVar(value=f"{self.view_pitch_deg:.2f}")
        self.mouse_geo_var = tk.StringVar(value="Mouse: move over globe")
        self.main_launch_lbl = None
        self.main_target_lbl = None
        self.main_interceptor_lbl = None
        self.popup_launch_lbl = None
        self.popup_target_lbl = None
        self.popup_interceptor_lbl = None
        # Locate settings_file next to the executable if compiled, otherwise next to this script file
        if getattr(sys, 'frozen', False):
            # Running as a compiled PyInstaller EXE
            # sys.executable is the path to Missile_Intercept_Simulation.exe, so we place settings next to it!
            self.settings_file = os.path.join(os.path.dirname(sys.executable), "mslwarntest_settings.json")
        else:
            # Running natively in Python development environment
            self.settings_file = os.path.join(os.path.dirname(__file__), "mslwarntest_settings.json")
        self.coastline_segments_drag = self.load_shapefile_segments(os.path.join(os.path.dirname(os.path.dirname(__file__)), "ne_10m_coastline.shp"), point_step=32)
        self.coastline_segments_full = self.load_shapefile_segments(os.path.join(os.path.dirname(os.path.dirname(__file__)), "ne_10m_coastline.shp"), point_step=3)
        
        # Safe offline shapefiles loader wrappers to prevent any internet download crashes!
        def safe_load_natural_earth(resolution, category, name, point_step):
            try:
                path = cartopy_shapereader.natural_earth(resolution=resolution, category=category, name=name)
                return self.load_shapefile_segments(path, point_step=point_step)
            except Exception as e:
                print(f"[Offline Mode] Skip loading remote shapefile '{name}' ({e})")
                return []
                
        def safe_load_country_labels(resolution, category, name):
            try:
                path = cartopy_shapereader.natural_earth(resolution=resolution, category=category, name=name)
                return self.load_country_labels(path)
            except Exception as e:
                print(f"[Offline Mode] Skip loading remote country labels '{name}' ({e})")
                return []

        def safe_load_city_labels(resolution, category, name):
            try:
                path = cartopy_shapereader.natural_earth(resolution=resolution, category=category, name=name)
                return self.load_city_labels(path)
            except Exception as e:
                print(f"[Offline Mode] Skip loading remote city labels '{name}' ({e})")
                return []

        self.land_segments_drag = []
        self.land_segments_full = safe_load_natural_earth(resolution="50m", category="physical", name="land", point_step=4)
        self.ocean_segments_drag = []
        self.ocean_segments_full = safe_load_natural_earth(resolution="50m", category="physical", name="ocean", point_step=4)
        self.boundary_segments_drag = []
        self.boundary_segments_full = safe_load_natural_earth(resolution="50m", category="cultural", name="admin_0_boundary_lines_land", point_step=4)
        self.country_labels = safe_load_country_labels(resolution="50m", category="cultural", name="admin_0_countries")
        self.city_labels = safe_load_city_labels(resolution="50m", category="cultural", name="populated_places")
        self.load_settings()
        self.update_globe_radius()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.build_ui()
        self.refresh_coordinate_labels()
        self.render_globe()

    def build_ui(self):
        tk.Label(
            self.content_frame,
            text="MISSILE INTERCEPT CONFIGURATION",
            font=("Segoe UI", 12, "bold"),
            fg="#ffffff",
            bg="#1e1e24",
        ).pack(pady=(14, 8))

        self.status_lbl = tk.Label(
            self.content_frame,
            text="Select a pick button, then left-click the wireframe globe. Drag rotates and double-click centers the globe.",
            font=("Segoe UI", 9),
            fg="#cfd8dc",
            bg="#1e1e24",
        )
        self.status_lbl.pack(pady=(0, 8))

        self.globe_canvas = tk.Canvas(
            self.content_frame,
            width=self.globe_canvas_width,
            height=self.globe_canvas_height,
            bg="#000000",
            highlightthickness=1,
            highlightbackground="#444444",
        )
        self.globe_canvas.pack(fill="both", expand=True, padx=20, pady=(0, 8), ipadx=20, ipady=20)
        self.globe_canvas.bind("<ButtonPress-1>", self.on_drag_start)
        self.globe_canvas.bind("<B1-Motion>", self.on_drag_move)
        self.globe_canvas.bind("<ButtonRelease-1>", self.on_drag_end)
        self.globe_canvas.bind("<ButtonPress-3>", self.on_drag_start)
        self.globe_canvas.bind("<B3-Motion>", self.on_drag_move)
        self.globe_canvas.bind("<ButtonRelease-3>", self.on_drag_end)
        self.globe_canvas.bind("<MouseWheel>", self.on_globe_mousewheel)
        self.globe_canvas.bind("<Button-4>", self.on_globe_mousewheel)
        self.globe_canvas.bind("<Button-5>", self.on_globe_mousewheel)
        self.globe_canvas.bind("<Motion>", self.on_globe_mouse_move)
        self.globe_canvas.bind("<Leave>", self.on_globe_mouse_leave)

        setup_frm = tk.Frame(self.content_frame, bg="#1e1e24")
        setup_frm.pack(fill="x", padx=20, pady=(0, 10))

        # Pick Coordinate Mode text title label placed cleanly at the top of the setup frame
        # tk.Label(setup_frm, text="Pick Coordinate Mode", font=("Segoe UI", 9, "bold"), fg="#ffffff", bg="#1e1e24").pack(anchor="w", padx=(10, 0), pady=(0, 6))

        # Single horizontal row container containing all buttons and the live coordinates label!
        control_row = tk.Frame(setup_frm, bg="#1e1e24")
        control_row.pack(fill="x", pady=(0, 8))

        # 1. Left Buttons: Add Missile, Add Intcp, and Msl Edit packed on the left
        self.launch_btn = tk.Button(control_row, text="Add Missile", command=self.on_add_missile_group, bg="#27ae60", fg="white", bd=0, width=11, pady=4, font=("Segoe UI", 9, "bold"))
        self.launch_btn.pack(side="left", padx=(10, 8))
        self.intcp_btn = tk.Button(control_row, text="Add Intcp", command=self.on_add_interceptor_group, bg="#2ecc71", fg="white", bd=0, width=11, pady=4, font=("Segoe UI", 9, "bold"))
        self.intcp_btn.pack(side="left", padx=(0, 8))
        self.msl_edit_btn = tk.Button(control_row, text="Msl Edit", command=self.open_missile_edit_window, bg="#34495e", fg="white", bd=0, width=11, pady=4, font=("Segoe UI", 9, "bold"))
        self.msl_edit_btn.pack(side="left")

        # 2. Centered Label: Dynamic Mouse Coordinate Display
        self.mouse_geo_lbl = tk.Label(control_row, textvariable=self.mouse_geo_var, fg="#9fb3bf", bg="#1e1e24", font=("Segoe UI", 9, "bold"))
        self.mouse_geo_lbl.pack(side="left", fill="x", expand=True)

        # 3. Right Buttons: Start and Reset packed on the right
        self.reset_btn = tk.Button(control_row, text="Reset", command=self.reset_globe, bg="#95a5a6", fg="white", bd=0, width=11, pady=4, font=("Segoe UI", 9, "bold"))
        self.reset_btn.pack(side="right", padx=(10, 8))
        self.start_btn = tk.Button(control_row, text="Start", command=self.start_simulation, bg="#2ecc71", activebackground="#2ecc71", fg="white", activeforeground="white", bd=0, width=11, pady=4, font=("Segoe UI", 9, "bold"))
        self.start_btn.pack(side="right", padx=(0, 8))

        # Horizontal row container for satellite operations
        control_row_sat = tk.Frame(setup_frm, bg="#1e1e24")
        control_row_sat.pack(fill="x", pady=(0, 8))

        self.add_sat_btn = tk.Button(control_row_sat, text="Add Sat", command=self.on_add_satellite, bg="#9b59b6", fg="white", bd=0, width=11, pady=4, font=("Segoe UI", 9, "bold"))
        self.add_sat_btn.pack(side="left", padx=(10, 8))
        self.sat_edit_btn = tk.Button(control_row_sat, text="Sat Edit", command=self.on_sat_edit, bg="#34495e", fg="white", bd=0, width=11, pady=4, font=("Segoe UI", 9, "bold"))
        self.sat_edit_btn.pack(side="left")

        self.main_launch_lbl = tk.Label(setup_frm, text="", anchor="w", fg="#ff6b6b", bg="#10151c", font=("Segoe UI", 9, "bold"), padx=10, pady=4)
        self.main_launch_lbl.pack(fill="x", pady=(0, 4))
        self.main_target_lbl = tk.Label(setup_frm, text="", anchor="w", fg="#ffd166", bg="#10151c", font=("Segoe UI", 9, "bold"), padx=10, pady=4)
        self.main_target_lbl.pack(fill="x", pady=(0, 4))
        self.main_interceptor_lbl = tk.Label(setup_frm, text="", anchor="w", fg="#22d3a6", bg="#10151c", font=("Segoe UI", 9, "bold"), padx=10, pady=4)
        self.main_interceptor_lbl.pack(fill="x", pady=(0, 8))

        params_frm = tk.Frame(self.content_frame, bg="#1e1e24")
        params_frm.pack(fill="x", padx=20, pady=(0, 10))

        tk.Label(params_frm, text="Simulation Setup:", font=("Segoe UI", 9, "bold"), fg="#ffffff", bg="#1e1e24").pack(anchor="w", pady=(0, 4))

        params_row1 = tk.Frame(params_frm, bg="#1e1e24")
        params_row1.pack(fill="x", pady=(0, 4))
        tk.Label(params_row1, text="Msl spd (M):", width=12, anchor="w", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9)).pack(side="left")
        self.missile_speed_entry = tk.Entry(params_row1, textvariable=self.missile_speed_var, width=12, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.missile_speed_entry.pack(side="left", padx=(0, 16))
        self.missile_speed_entry.bind("<FocusOut>", lambda e: self.save_settings())
        self.missile_speed_entry.bind("<Return>", lambda e: self.save_settings())

        tk.Label(params_row1, text="Intcp spd (M):", width=14, anchor="w", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9)).pack(side="left")
        self.interceptor_speed_entry = tk.Entry(params_row1, textvariable=self.interceptor_speed_var, width=12, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.interceptor_speed_entry.pack(side="left")
        self.interceptor_speed_entry.bind("<FocusOut>", lambda e: self.save_settings())
        self.interceptor_speed_entry.bind("<Return>", lambda e: self.save_settings())

        params_row2 = tk.Frame(params_frm, bg="#1e1e24")
        params_row2.pack(fill="x", pady=(0, 4))
        tk.Label(params_row2, text="PN gain:", width=12, anchor="w", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9)).pack(side="left")
        self.proportional_gain_entry = tk.Entry(params_row2, textvariable=self.proportional_gain_var, width=12, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.proportional_gain_entry.pack(side="left", padx=(0, 16))
        self.proportional_gain_entry.bind("<FocusOut>", lambda e: self.save_settings())
        self.proportional_gain_entry.bind("<Return>", lambda e: self.save_settings())

        tk.Label(params_row2, text="Launch dly (s):", width=14, anchor="w", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9)).pack(side="left")
        self.interceptor_delay_entry = tk.Entry(params_row2, textvariable=self.interceptor_delay_var, width=12, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.interceptor_delay_entry.pack(side="left")
        self.interceptor_delay_entry.bind("<FocusOut>", lambda e: self.save_settings())
        self.interceptor_delay_entry.bind("<Return>", lambda e: self.save_settings())

        params_row3 = tk.Frame(params_frm, bg="#1e1e24")
        params_row3.pack(fill="x", pady=(0, 4))
        tk.Label(params_row3, text="Msl grp dly (s):", width=16, anchor="w", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9)).pack(side="left")
        self.msl_grp_delay_entry = tk.Entry(params_row3, textvariable=self.msl_grp_delay_var, width=8, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.msl_grp_delay_entry.pack(side="left", padx=(0, 16))
        self.msl_grp_delay_entry.bind("<FocusOut>", lambda e: self.save_settings())
        self.msl_grp_delay_entry.bind("<Return>", lambda e: self.save_settings())

        tk.Label(params_row3, text="Msl dly (s):", width=14, anchor="w", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9)).pack(side="left")
        self.msl_delay_entry = tk.Entry(params_row3, textvariable=self.msl_delay_var, width=8, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.msl_delay_entry.pack(side="left")
        self.msl_delay_entry.bind("<FocusOut>", lambda e: self.save_settings())
        self.msl_delay_entry.bind("<Return>", lambda e: self.save_settings())

        params_row4 = tk.Frame(params_frm, bg="#1e1e24")
        params_row4.pack(fill="x", pady=(0, 4))
        tk.Label(params_row4, text="Msl path size:", width=16, anchor="w", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9)).pack(side="left")
        self.msl_path_size_entry = tk.Entry(params_row4, textvariable=self.msl_path_size_var, width=8, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.msl_path_size_entry.pack(side="left", padx=(0, 16))
        self.msl_path_size_entry.bind("<FocusOut>", lambda e: self.save_settings())
        self.msl_path_size_entry.bind("<Return>", lambda e: self.save_settings())

        tk.Label(params_row4, text="Int path size:", width=14, anchor="w", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9)).pack(side="left")
        self.int_path_size_entry = tk.Entry(params_row4, textvariable=self.int_path_size_var, width=8, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.int_path_size_entry.pack(side="left")
        self.int_path_size_entry.bind("<FocusOut>", lambda e: self.save_settings())
        self.int_path_size_entry.bind("<Return>", lambda e: self.save_settings())

        params_row5 = tk.Frame(params_frm, bg="#1e1e24")
        params_row5.pack(fill="x", pady=(0, 8))
        self.auto_cb = tk.Checkbutton(params_row5, text="Auto-launch interceptor", variable=self.auto_launch_var, command=self.save_settings, fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24")
        self.auto_cb.pack(side="left", padx=(0, 16))
        self.wire_cb = tk.Checkbutton(params_row5, text="Wireframe globe", variable=self.show_wireframe_var, command=self.render_globe, fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24")
        self.wire_cb.pack(side="left", padx=(0, 16))
        self.bound_cb = tk.Checkbutton(params_row5, text="Boundaries", variable=self.show_boundaries_var, command=self.render_globe, fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24")
        self.bound_cb.pack(side="left", padx=(0, 16))
        self.offline_cb = tk.Checkbutton(params_row5, text="Offline", variable=self.offline_mode_var, command=self.save_settings, fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24")
        self.offline_cb.pack(side="left")

        params_row6 = tk.Frame(params_frm, bg="#1e1e24")
        params_row6.pack(fill="x", pady=(4, 8))
        tk.Label(params_row6, text="Tracking Fusion:", font=("Segoe UI", 9, "bold"), fg="#ffffff", bg="#1e1e24").pack(side="left", padx=(0, 10))
        self.ekf_rb = tk.Radiobutton(params_row6, text="EKF (Extended)", variable=self.tracking_algo_var, value="EKF", command=self.save_settings, fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24")
        self.ekf_rb.pack(side="left", padx=(0, 12))
        self.hkf_rb = tk.Radiobutton(params_row6, text="HKF (Huber)", variable=self.tracking_algo_var, value="HKF", command=self.save_settings, fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24")
        self.hkf_rb.pack(side="left", padx=(0, 12))
        self.wavg_rb = tk.Radiobutton(params_row6, text="Weighted Avg", variable=self.tracking_algo_var, value="Weighted Avg", command=self.save_settings, fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24")
        self.wavg_rb.pack(side="left", padx=(0, 12))
        self.sbest_rb = tk.Radiobutton(params_row6, text="Single Best", variable=self.tracking_algo_var, value="Single Best", command=self.save_settings, fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24")
        self.sbest_rb.pack(side="left", padx=(0, 16))
        self.mp_cb = tk.Checkbutton(params_row6, text="MP", variable=self.mp_mode_var, command=self.save_settings, fg="#00ffd0", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#00ffd0", selectcolor="#1e1e24", font=("Segoe UI", 9, "bold"))
        self.mp_cb.pack(side="left")

        camera_frm = tk.Frame(self.content_frame, bg="#1e1e24")
        camera_frm.pack(fill="x", padx=20, pady=(0, 10))

        tk.Label(camera_frm, text="Camera Orbit:", font=("Segoe UI", 9, "bold"), fg="#ffffff", bg="#1e1e24").pack(anchor="w", pady=(0, 4))

        center_row = tk.Frame(camera_frm, bg="#1e1e24")
        center_row.pack(fill="x", pady=(0, 4))
        tk.Label(center_row, text="View center", width=16, anchor="w", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9)).pack(side="left")
        tk.Label(center_row, text="Lat", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 4))
        self.view_center_lat_entry = tk.Entry(center_row, textvariable=self.view_center_lat_var, width=10, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.view_center_lat_entry.pack(side="left", padx=(0, 8))
        tk.Label(center_row, text="Lon", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 4))
        self.view_center_lon_entry = tk.Entry(center_row, textvariable=self.view_center_lon_var, width=10, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.view_center_lon_entry.pack(side="left", padx=(0, 8))
        tk.Label(center_row, text="Alt km", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 4))
        self.view_altitude_entry = tk.Entry(center_row, textvariable=self.view_altitude_km_var, width=10, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.view_altitude_entry.pack(side="left", padx=(0, 8))
        tk.Button(center_row, text="Apply", width=8, command=self.apply_view_center_from_fields, bg="#3b6ea8", fg="white", bd=0).pack(side="left")
        self.view_center_lat_entry.bind("<Return>", self.apply_view_center_from_fields)
        self.view_center_lon_entry.bind("<Return>", self.apply_view_center_from_fields)
        self.view_altitude_entry.bind("<Return>", self.apply_view_center_from_fields)

        angle_row = tk.Frame(camera_frm, bg="#1e1e24")
        angle_row.pack(fill="x", pady=(0, 8))
        tk.Label(angle_row, text="View angle", width=16, anchor="w", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9)).pack(side="left")
        tk.Label(angle_row, text="Yaw", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 4))
        self.view_yaw_entry = tk.Entry(angle_row, textvariable=self.view_yaw_var, width=10, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.view_yaw_entry.pack(side="left", padx=(0, 8))
        tk.Label(angle_row, text="Pitch", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 4))
        self.view_pitch_entry = tk.Entry(angle_row, textvariable=self.view_pitch_var, width=10, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.view_pitch_entry.pack(side="left", padx=(0, 8))
        tk.Button(angle_row, text="Apply", width=8, command=self.apply_view_angle_from_fields, bg="#3b6ea8", fg="white", bd=0).pack(side="left")
        self.view_yaw_entry.bind("<Return>", self.apply_view_angle_from_fields)
        self.view_pitch_entry.bind("<Return>", self.apply_view_angle_from_fields)

    def open_missile_edit_window(self):
        if self.missile_edit_window is not None and self.missile_edit_window.winfo_exists():
            self.missile_edit_window.deiconify()
            self.missile_edit_window.lift()
            self.missile_edit_window.focus_force()
            return

        self.missile_edit_window = tk.Toplevel(self.root)
        self.missile_edit_window.title("Missile & Interceptor Properties Editor")
        self.missile_edit_window.geometry("1150x520")
        self.missile_edit_window.configure(bg="#1e1e24")
        self.missile_edit_window.protocol("WM_DELETE_WINDOW", self.close_individual_editor)

        # Scrolling framework for long list of threats
        frame = tk.Frame(self.missile_edit_window, bg="#1e1e24")
        frame.pack(fill="both", expand=True, padx=15, pady=15)

        canvas = tk.Canvas(frame, bg="#10151c", highlightthickness=0)
        scrollbar = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg="#10151c")

        scroll_window = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def on_scroll_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        scroll_frame.bind("<Configure>", on_scroll_configure)

        # Column Headers matching the picture
        headers = [
            "Missile Name", "Latitude", "Longitude", "Target", "Auto Launch",
            "Launch Delay (sec)", "Trail Path", "Speed", "PN Gain", "Height Line", "Project to Ground"
        ]
        for col_idx, h in enumerate(headers):
            lbl = tk.Label(scroll_frame, text=h, font=("Segoe UI", 9, "bold"), fg="#ffffff", bg="#2c3e50", padx=10, pady=8, bd=1, relief="solid")
            lbl.grid(row=0, column=col_idx, sticky="nsew")

        # Load active group threats
        raw_rows = []
        
        # 1. Gather Missiles
        if hasattr(self, "missile_groups") and self.missile_groups:
            for group_name, pairs in self.missile_groups.items():
                for pair in pairs:
                    i = pair["id"]
                    raw_rows.append({
                        "name": f"{group_name}-M{i}",
                        "is_interceptor": False,
                        "group_name": group_name,
                        "pair_index": pair,
                        "lat": pair.get("start_lat", 0.0),
                        "lon": pair.get("start_lon", 0.0),
                        "target": pair.get("target_name", f"{group_name}-T{i}"),
                        "auto_launch": pair.get("auto_launch", True),
                        "launch_delay": pair.get("launch_delay", 80.0),
                        "trail_path": pair.get("trail_path", True),
                        "speed": pair.get("speed", 5.0),
                        "pn_gain": "",
                        "height_line": pair.get("height_line", True),
                        "project_to_ground": pair.get("project_to_ground", False)
                    })

        # 2. Gather Interceptors
        if hasattr(self, "interceptor_groups") and self.interceptor_groups:
            for group_name, pairs in self.interceptor_groups.items():
                for pair in pairs:
                    i = pair["id"]
                    raw_rows.append({
                        "name": f"{group_name}-Int{i}",
                        "is_interceptor": True,
                        "group_name": group_name,
                        "pair_index": pair,
                        "lat": pair.get("start_lat", 0.0),
                        "lon": pair.get("start_lon", 0.0),
                        "target": pair.get("target_name", f"{group_name}-M{i}"),
                        "auto_launch": pair.get("auto_launch", True),
                        "launch_delay": pair.get("launch_delay", 5.0),
                        "trail_path": pair.get("trail_path", True),
                        "speed": pair.get("speed", 6.0),
                        "pn_gain": pair.get("pn_gain", 4.0),
                        "height_line": pair.get("height_line", True),
                        "project_to_ground": pair.get("project_to_ground", False)
                    })

        # Sort chronologically or by Alpha-Beta name order
        sorted_rows = sorted(raw_rows, key=lambda x: x["name"])

        # Track UI control variables to read on Save
        self.edit_vars = []

        for idx, r in enumerate(sorted_rows):
            row_idx = idx + 1
            bg_color = "#161b22" if idx % 2 == 0 else "#0d1117"

            # Create variables
            lat_var = tk.StringVar(value=f"{r['lat']:.4f}")
            lon_var = tk.StringVar(value=f"{r['lon']:.4f}")
            target_var = tk.StringVar(value=str(r['target']))
            auto_var = tk.BooleanVar(value=r['auto_launch'])
            delay_var = tk.StringVar(value=str(r['launch_delay']))
            trail_var = tk.BooleanVar(value=r['trail_path'])
            speed_var = tk.StringVar(value=str(r['speed']))
            pn_var = tk.StringVar(value=str(r['pn_gain']))
            height_var = tk.BooleanVar(value=r['height_line'])
            project_var = tk.BooleanVar(value=r['project_to_ground'])

            # Render controls in grid
            # Name
            tk.Label(scroll_frame, text=r["name"], bg=bg_color, fg="#58a6ff", font=("Segoe UI", 9, "bold"), bd=1, relief="solid", padx=8, pady=4).grid(row=row_idx, column=0, sticky="nsew")
            
            # Lat/Lon Entry
            e_lat = tk.Entry(scroll_frame, textvariable=lat_var, width=12, bg="#0d1117", fg="#ffffff", insertbackground="#ffffff", justify="center", bd=1, relief="solid")
            e_lat.grid(row=row_idx, column=1, sticky="nsew", padx=2, pady=2)
            e_lon = tk.Entry(scroll_frame, textvariable=lon_var, width=12, bg="#0d1117", fg="#ffffff", insertbackground="#ffffff", justify="center", bd=1, relief="solid")
            e_lon.grid(row=row_idx, column=2, sticky="nsew", padx=2, pady=2)
            
            # Target
            e_tgt = tk.Entry(scroll_frame, textvariable=target_var, width=12, bg="#0d1117", fg="#ffffff", insertbackground="#ffffff", justify="center", bd=1, relief="solid")
            e_tgt.grid(row=row_idx, column=3, sticky="nsew", padx=2, pady=2)

            # Checkbuttons/OptionMenus for Toggles
            auto_cb = tk.Checkbutton(scroll_frame, variable=auto_var, onvalue=True, offvalue=False, bg=bg_color, fg="#27ae60", activebackground=bg_color, selectcolor="#ffffff", bd=0, font=("Segoe UI", 12, "bold"))
            auto_cb.grid(row=row_idx, column=4, sticky="nsew")

            # Delay
            e_delay = tk.Entry(scroll_frame, textvariable=delay_var, width=12, bg="#0d1117", fg="#ffffff", insertbackground="#ffffff", justify="center", bd=1, relief="solid")
            e_delay.grid(row=row_idx, column=5, sticky="nsew", padx=2, pady=2)

            # Trail
            trail_cb = tk.Checkbutton(scroll_frame, variable=trail_var, onvalue=True, offvalue=False, bg=bg_color, fg="#27ae60", activebackground=bg_color, selectcolor="#ffffff", bd=0, font=("Segoe UI", 12, "bold"))
            trail_cb.grid(row=row_idx, column=6, sticky="nsew")

            # Speed
            e_spd = tk.Entry(scroll_frame, textvariable=speed_var, width=12, bg="#0d1117", fg="#ffffff", insertbackground="#ffffff", justify="center", bd=1, relief="solid")
            e_spd.grid(row=row_idx, column=7, sticky="nsew", padx=2, pady=2)

            # PN Gain (Blank and disabled for missiles!)
            if r["is_interceptor"]:
                e_pn = tk.Entry(scroll_frame, textvariable=pn_var, width=12, bg="#0d1117", fg="#ffffff", insertbackground="#ffffff", justify="center", bd=1, relief="solid")
                e_pn.grid(row=row_idx, column=8, sticky="nsew", padx=2, pady=2)
            else:
                lbl_pn = tk.Label(scroll_frame, text="", bg=bg_color, bd=1, relief="solid")
                lbl_pn.grid(row=row_idx, column=8, sticky="nsew")

            # Height Line
            height_cb = tk.Checkbutton(scroll_frame, variable=height_var, onvalue=True, offvalue=False, bg=bg_color, fg="#27ae60", activebackground=bg_color, selectcolor="#ffffff", bd=0, font=("Segoe UI", 12, "bold"))
            height_cb.grid(row=row_idx, column=9, sticky="nsew")

            # Project to Ground
            project_cb = tk.Checkbutton(scroll_frame, variable=project_var, onvalue=True, offvalue=False, bg=bg_color, fg="#27ae60", activebackground=bg_color, selectcolor="#ffffff", bd=0, font=("Segoe UI", 12, "bold"))
            project_cb.grid(row=row_idx, column=10, sticky="nsew")

            # Store tracking models
            self.edit_vars.append({
                "record": r,
                "lat": lat_var,
                "lon": lon_var,
                "target": target_var,
                "auto": auto_var,
                "delay": delay_var,
                "trail": trail_var,
                "speed": speed_var,
                "pn": pn_var,
                "height": height_var,
                "project": project_var
            })

        # Save/Cancel Buttons Row
        action_frm = tk.Frame(self.missile_edit_window, bg="#1e1e24")
        action_frm.pack(fill="x", side="bottom", padx=15, pady=10)

        cancel_btn = tk.Button(action_frm, text="Cancel", command=self.close_individual_editor, bg="#95a5a6", fg="white", bd=0, width=12, pady=6, font=("Segoe UI", 9, "bold"))
        cancel_btn.pack(side="right", padx=(12, 0))

        save_btn = tk.Button(action_frm, text="Save", command=self.save_individual_properties, bg="#2ecc71", fg="white", bd=0, width=12, pady=6, font=("Segoe UI", 9, "bold"))
        save_btn.pack(side="right")

    def save_individual_properties(self):
        try:
            # Parse all UI values and update the dictionaries
            for item in self.edit_vars:
                r = item["record"]
                pair = r["pair_index"]

                # Extract and validate numerical values
                lat_val = float(item["lat"].get())
                lon_val = float(item["lon"].get())
                tgt_val = item["target"].get().strip()
                auto_val = bool(item["auto"].get())
                delay_val = float(item["delay"].get())
                trail_val = bool(item["trail"].get())
                spd_val = float(item["speed"].get())
                height_val = bool(item["height"].get())
                proj_val = bool(item["project"].get())

                # Update target-level dictionary
                pair["start_lat"] = lat_val
                pair["start_lon"] = lon_val
                pair["target_name"] = tgt_val
                pair["auto_launch"] = auto_val
                pair["launch_delay"] = delay_val
                pair["trail_path"] = trail_val
                pair["speed"] = spd_val
                pair["height_line"] = height_val
                pair["project_to_ground"] = proj_val

                if r["is_interceptor"]:
                    pn_val = float(item["pn"].get())
                    pair["pn_gain"] = pn_val

            # Save to config file and re-render Setup globe map
            self.save_settings()
            self.render_globe()
            
            # Close the window
            self.close_individual_editor()
            messagebox.showinfo("Success", "Individual properties saved and applied to simulation successfully!", parent=self.root)
        except ValueError:
            messagebox.showerror("Validation Error", "Please verify that all coordinates, speeds, delays, and gains are valid numerical values.", parent=self.missile_edit_window)

    def on_add_satellite(self):
        sat_dialog = tk.Toplevel(self.root)
        sat_dialog.title("Add New Satellite")
        sat_dialog.geometry("380x350")
        sat_dialog.configure(bg="#1e1e24")
        sat_dialog.grab_set()  # Modal dialog
        
        # Centered Frame
        frm = tk.Frame(sat_dialog, bg="#1e1e24", padx=15, pady=15)
        frm.pack(fill="both", expand=True)
        
        # Grid fields
        tk.Label(frm, text="Satellite Name:", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", pady=6)
        name_entry = tk.Entry(frm, width=20, bg="#10151c", fg="#ffffff", insertbackground="#ffffff")
        name_entry.grid(row=0, column=1, sticky="w", pady=6)
        name_entry.insert(0, "Sat-New")
        
        tk.Label(frm, text="Inclines deg:", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky="w", pady=6)
        inc_entry = tk.Entry(frm, width=12, bg="#10151c", fg="#ffffff", insertbackground="#ffffff")
        inc_entry.grid(row=1, column=1, sticky="w", pady=6)
        inc_entry.insert(0, "45.0")
        
        tk.Label(frm, text="Phase deg:", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9, "bold")).grid(row=2, column=0, sticky="w", pady=6)
        phase_entry = tk.Entry(frm, width=12, bg="#10151c", fg="#ffffff", insertbackground="#ffffff")
        phase_entry.grid(row=2, column=1, sticky="w", pady=6)
        phase_entry.insert(0, "0.0")
        
        geosync_var = tk.BooleanVar(value=False)
        geosync_cb = tk.Checkbutton(frm, text="Geosync", variable=geosync_var, fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24", font=("Segoe UI", 9, "bold"))
        geosync_cb.grid(row=3, column=0, columnspan=2, sticky="w", pady=6)
        
        tk.Label(frm, text="Geo lat:", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9, "bold")).grid(row=4, column=0, sticky="w", pady=6)
        geolat_entry = tk.Entry(frm, width=12, bg="#10151c", fg="#ffffff", insertbackground="#ffffff")
        geolat_entry.grid(row=4, column=1, sticky="w", pady=6)
        geolat_entry.insert(0, "0.0")
        
        tk.Label(frm, text="Geo lon:", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9, "bold")).grid(row=5, column=0, sticky="w", pady=6)
        geolon_entry = tk.Entry(frm, width=12, bg="#10151c", fg="#ffffff", insertbackground="#ffffff")
        geolon_entry.grid(row=5, column=1, sticky="w", pady=6)
        geolon_entry.insert(0, "130.0")
        
        display_var = tk.BooleanVar(value=True)
        display_cb = tk.Checkbutton(frm, text="Display / Render", variable=display_var, fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24", font=("Segoe UI", 9, "bold"))
        display_cb.grid(row=6, column=0, columnspan=2, sticky="w", pady=6)
        
        # Submit Button
        def on_submit():
            try:
                name = name_entry.get().strip() or "Sat-B"
                inc = float(inc_entry.get() or 45.0)
                phase = float(phase_entry.get() or 0.0)
                geosync = bool(geosync_var.get())
                geolat = float(geolat_entry.get() or 0.0)
                geolon = float(geolon_entry.get() or 0.0)
                display = bool(display_var.get())
                
                # Load current satellites list
                sat_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "satellites.json")
                satellites = []
                if os.path.exists(sat_path):
                    try:
                        with open(sat_path, "r") as f:
                            satellites = json.load(f)
                    except Exception:
                        pass
                if not isinstance(satellites, list):
                    satellites = []
                    
                # Add new sat
                satellites.append({
                    "name": name,
                    "inclination": inc,
                    "phase": phase,
                    "geosync": geosync,
                    "geolat": geolat,
                    "geolon": geolon,
                    "display": display,
                    "altitude": 800.0,
                    "period": 120.0,
                    "noise": 0.0
                })
                
                # Save
                with open(sat_path, "w") as f:
                    json.dump(satellites, f, indent=2)
                    
                self.status_lbl.config(text=f"Status: Added satellite '{name}' successfully.", fg="#2ecc71")
                self.render_globe()
                sat_dialog.destroy()
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter valid numeric values for coordinates and angles.", parent=sat_dialog)
                
        submit_btn = tk.Button(frm, text="Add Satellite", command=on_submit, bg="#2ecc71", fg="white", bd=0, width=15, pady=4, font=("Segoe UI", 9, "bold"))
        submit_btn.grid(row=7, column=0, columnspan=2, pady=(15, 0))

    def on_sat_edit(self):
        if hasattr(self, "sat_edit_window") and self.sat_edit_window is not None and self.sat_edit_window.winfo_exists():
            self.sat_edit_window.deiconify()
            self.sat_edit_window.lift()
            self.sat_edit_window.focus_force()
            return

        self.sat_edit_window = tk.Toplevel(self.root)
        self.sat_edit_window.title("Satellite Properties Editor")
        self.sat_edit_window.geometry("980x520")
        self.sat_edit_window.configure(bg="#1e1e24")

        # Scrolling framework for satellites list
        frame = tk.Frame(self.sat_edit_window, bg="#1e1e24")
        frame.pack(fill="both", expand=True, padx=15, pady=15)

        canvas = tk.Canvas(frame, bg="#10151c", highlightthickness=0)
        scrollbar = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg="#10151c")

        scroll_window = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def on_scroll_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        scroll_frame.bind("<Configure>", on_scroll_configure)

        # Column Headers
        headers = [
            "Satellite Name", "Inclines deg", "Phase deg", "Geosync",
            "Geo Lat", "Geo Lon", "Display / Render", "Altitude km", "Period sec", "TLE", "Noise km"
        ]
        for col_idx, h in enumerate(headers):
            lbl = tk.Label(scroll_frame, text=h, font=("Segoe UI", 9, "bold"), fg="#ffffff", bg="#2c3e50", padx=10, pady=8, bd=1, relief="solid")
            lbl.grid(row=0, column=col_idx, sticky="nsew")

        # Load current satellites list
        sats_list = self.simulation_window.load_satellites_list() if (self.simulation_window is not None) else []
        if len(sats_list) == 0:
            # Try load directly from json file
            sat_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "satellites.json")
            if os.path.exists(sat_path):
                try:
                    with open(sat_path, "r") as f:
                        sats_list = json.load(f)
                except Exception:
                    pass
        if not isinstance(sats_list, list) or len(sats_list) == 0:
            sats_list = [
                {
                    "name": "Sat-A1",
                    "inclination": 45.0,
                    "phase": 0.0,
                    "geosync": True,
                    "geolat": -51.24,
                    "geolon": 82.03,
                    "display": True,
                    "altitude": 800.0,
                    "period": 120.0,
                    "tle": False,
                    "noise": 0.0
                }
            ]

        # Track UI control variables to read on Save
        self.sat_edit_vars = []

        for idx, sat_info in enumerate(sats_list):
            row_idx = idx + 1
            bg_color = "#161b22" if idx % 2 == 0 else "#0d1117"

            # Create variables
            name_var = tk.StringVar(value=str(sat_info.get("name", f"Sat-{row_idx}")))
            inc_var = tk.StringVar(value=f"{float(sat_info.get('inclination', 45.0)):.2f}")
            phase_var = tk.StringVar(value=f"{float(sat_info.get('phase', 0.0)):.2f}")
            geo_var = tk.BooleanVar(value=bool(sat_info.get("geosync", False)))
            geolat_var = tk.StringVar(value=f"{float(sat_info.get('geolat', 0.0)):.2f}")
            geolon_var = tk.StringVar(value=f"{float(sat_info.get('geolon', 130.0)):.2f}")
            disp_var = tk.BooleanVar(value=bool(sat_info.get("display", True)))
            alt_var = tk.StringVar(value=f"{float(sat_info.get('altitude', 800.0)):.1f}")
            per_var = tk.StringVar(value=f"{float(sat_info.get('period', 120.0)):.1f}")
            tle_var = tk.BooleanVar(value=bool(sat_info.get("tle", False)))
            noise_var = tk.StringVar(value=f"{float(sat_info.get('noise', 0.0)):.2f}")

            # Keep reference
            self.sat_edit_vars.append({
                "name": name_var,
                "inclination": inc_var,
                "phase": phase_var,
                "geosync": geo_var,
                "geolat": geolat_var,
                "geolon": geolon_var,
                "display": disp_var,
                "altitude": alt_var,
                "period": per_var,
                "tle": tle_var,
                "noise": noise_var
            })

            # Render controls in grid
            # Name
            e_name = tk.Entry(scroll_frame, textvariable=name_var, width=15, bg="#0d1117", fg="#58a6ff", font=("Segoe UI", 9, "bold"), justify="center", bd=1, relief="solid")
            e_name.grid(row=row_idx, column=0, sticky="nsew", padx=2, pady=2)
            
            # Inclines
            e_inc = tk.Entry(scroll_frame, textvariable=inc_var, width=10, bg="#0d1117", fg="#ffffff", insertbackground="#ffffff", justify="center", bd=1, relief="solid")
            e_inc.grid(row=row_idx, column=1, sticky="nsew", padx=2, pady=2)
            
            # Phase
            e_ph = tk.Entry(scroll_frame, textvariable=phase_var, width=10, bg="#0d1117", fg="#ffffff", insertbackground="#ffffff", justify="center", bd=1, relief="solid")
            e_ph.grid(row=row_idx, column=2, sticky="nsew", padx=2, pady=2)

            # Geosync Checkbutton (No interlock, allows concurrent TLE selection)
            geo_cb = tk.Checkbutton(scroll_frame, variable=geo_var, onvalue=True, offvalue=False, bg=bg_color, fg="#27ae60", activebackground=bg_color, selectcolor="#ffffff", bd=0, font=("Segoe UI", 12, "bold"))
            geo_cb.grid(row=row_idx, column=3, sticky="nsew")

            # Geo Lat
            e_geolat = tk.Entry(scroll_frame, textvariable=geolat_var, width=10, bg="#0d1117", fg="#ffffff", insertbackground="#ffffff", justify="center", bd=1, relief="solid")
            e_geolat.grid(row=row_idx, column=4, sticky="nsew", padx=2, pady=2)

            # Geo Lon
            e_geolon = tk.Entry(scroll_frame, textvariable=geolon_var, width=10, bg="#0d1117", fg="#ffffff", insertbackground="#ffffff", justify="center", bd=1, relief="solid")
            e_geolon.grid(row=row_idx, column=5, sticky="nsew", padx=2, pady=2)

            # Display Checkbutton
            disp_cb = tk.Checkbutton(scroll_frame, variable=disp_var, onvalue=True, offvalue=False, bg=bg_color, fg="#27ae60", activebackground=bg_color, selectcolor="#ffffff", bd=0, font=("Segoe UI", 12, "bold"))
            disp_cb.grid(row=row_idx, column=6, sticky="nsew")

            # Altitude
            e_alt = tk.Entry(scroll_frame, textvariable=alt_var, width=10, bg="#0d1117", fg="#ffffff", insertbackground="#ffffff", justify="center", bd=1, relief="solid")
            e_alt.grid(row=row_idx, column=7, sticky="nsew", padx=2, pady=2)

            # Period
            e_per = tk.Entry(scroll_frame, textvariable=per_var, width=10, bg="#0d1117", fg="#ffffff", insertbackground="#ffffff", justify="center", bd=1, relief="solid")
            e_per.grid(row=row_idx, column=8, sticky="nsew", padx=2, pady=2)

            # TLE Checkbutton (No interlock, allows concurrent Geosync selection)
            tle_cb = tk.Checkbutton(scroll_frame, variable=tle_var, onvalue=True, offvalue=False, bg=bg_color, fg="#27ae60", activebackground=bg_color, selectcolor="#ffffff", bd=0, font=("Segoe UI", 12, "bold"))
            tle_cb.grid(row=row_idx, column=9, sticky="nsew")

            # Noise entry
            e_noise = tk.Entry(scroll_frame, textvariable=noise_var, width=10, bg="#0d1117", fg="#ffffff", insertbackground="#ffffff", justify="center", bd=1, relief="solid")
            e_noise.grid(row=row_idx, column=10, sticky="nsew", padx=2, pady=2)

        # Action Buttons frame (Save / Cancel)
        action_frm = tk.Frame(self.sat_edit_window, bg="#1e1e24", pady=10)
        action_frm.pack(fill="x", side="bottom")

        def close_sat_editor():
            self.sat_edit_window.destroy()
            self.sat_edit_window = None

        def save_sat_properties():
            try:
                new_sats_list = []
                for idx, v in enumerate(self.sat_edit_vars):
                    is_geo = bool(v["geosync"].get())
                    is_tle = bool(v["tle"].get())
                        
                    t_line1 = ""
                    t_line2 = ""
                    
                    if is_tle:
                        # Force-overwrite TLE lines to match the selected orbit type on Save
                        if is_geo:
                            # GOES 16 (Geosync)
                            t_line1 = "1 41866U 16071A   26265.81250000  .00000100  00000-0  00000-0 0  9999"
                            t_line2 = "2 41866   0.0215  45.5200 0001250 180.2000 180.3000  1.00270000388219"
                        else:
                            # Standard Orbital
                            if idx == 0:
                                # Sat-A1: Hubble Space Telescope (HST)
                                t_line1 = "1 20580U 90037B   26265.81250000  .00000500  00000-0  11200-3 0  9999"
                                t_line2 = "2 20580  28.4700 120.5000 0003500 180.2000 180.3000 15.12500000288219"
                            elif idx == 2:
                                # Sat-B1: ISS (Zarya)
                                t_line1 = "1 25544U 98067A   26265.80775463  .00015505  00000-0  27869-3 0  9997"
                                t_line2 = "2 25544  51.6408 141.5209 0004546 221.7224 233.1550 15.49503461588219"
                            else:
                                # Sat-B2 / Sat-A2 Polar Standard: NOAA 19
                                t_line1 = "1 33591U 09005A   26265.81250000  .00000100  00000-0  77900-4 0  9998"
                                t_line2 = "2 33591  99.1200 135.5000 0013500 240.2000 120.3000 14.12500000288219"

                    new_sats_list.append({
                        "name": str(v["name"].get()).strip() or "Sat-B",
                        "inclination": float(v["inclination"].get() or 45.0),
                        "phase": float(v["phase"].get() or 0.0),
                        "geosync": is_geo,
                        "geolat": float(v["geolat"].get() or 0.0),
                        "geolon": float(v["geolon"].get() or 0.0),
                        "display": bool(v["display"].get()),
                        "altitude": float(v["altitude"].get() or 800.0),
                        "period": float(v["period"].get() or 120.0),
                        "tle": is_tle,
                        "tle_line1": t_line1,
                        "tle_line2": t_line2,
                        "noise": float(v["noise"].get() or 0.0)
                    })
                    
                # Save to file
                sat_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "satellites.json")
                with open(sat_path, "w") as f:
                    json.dump(new_sats_list, f, indent=2)
                
                # Apply in real-time if simulation is running
                if self.simulation_window is not None and not self.simulation_window.closed:
                    self.simulation_window.render_globe()
                    # Rebuild Sat Live View window if open (to refresh table columns/satellites list)
                    if hasattr(self.simulation_window, "sat_live_view_window") and self.simulation_window.sat_live_view_window is not None:
                        if self.simulation_window.sat_live_view_window.winfo_exists():
                            self.simulation_window.sat_live_view_window.destroy()
                            self.simulation_window.sat_live_view_window = None
                            self.simulation_window.open_sat_live_view_window()
                    
                self.status_lbl.config(text="Status: Satellite constellation properties saved successfully.", fg="#2ecc71")
                close_sat_editor()
                messagebox.showinfo("Success", "Satellite constellation properties saved and applied successfully!", parent=self.root)
            except ValueError:
                messagebox.showerror("Validation Error", "Please verify that all inclinations, phases, coordinates, and altitudes are valid numerical values.", parent=self.sat_edit_window)

        cancel_btn = tk.Button(action_frm, text="Cancel", command=close_sat_editor, bg="#95a5a6", fg="white", bd=0, width=12, pady=6, font=("Segoe UI", 9, "bold"))
        cancel_btn.pack(side="right", padx=(10, 20))
        save_btn = tk.Button(action_frm, text="Save", command=save_sat_properties, bg="#2ecc71", fg="white", bd=0, width=12, pady=6, font=("Segoe UI", 9, "bold"))
        save_btn.pack(side="right")

    def close_individual_editor(self):
        if self.missile_edit_window is not None and self.missile_edit_window.winfo_exists():
            self.missile_edit_window.destroy()
        self.missile_edit_window = None

    def on_content_configure(self, event):
        self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))

    def open_globe_picks_window(self):
        if self.globe_picks_window is not None and self.globe_picks_window.winfo_exists():
            self.globe_picks_window.deiconify()
            self.globe_picks_window.lift()
            self.globe_picks_window.focus_force()
            self.refresh_coordinate_labels()
            return
        self.globe_picks_window = tk.Toplevel(self.root)
        self.globe_picks_window.title("Status")
        self.globe_picks_window.geometry("500x250")
        self.globe_picks_window.minsize(460, 220)
        self.globe_picks_window.configure(bg="#1e1e24")
        self.globe_picks_window.protocol("WM_DELETE_WINDOW", self.close_globe_picks_window)
        picks = tk.LabelFrame(self.globe_picks_window, text="Globe Picks", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9, "bold"))
        picks.pack(fill="both", expand=True, padx=12, pady=12)

        launch_row = tk.Frame(picks, bg="#1e1e24")
        launch_row.pack(fill="x", padx=10, pady=(6, 2))
        self.popup_launch_lbl = tk.Label(launch_row, anchor="w", fg="#ff8080", bg="#1e1e24", font=("Segoe UI", 8))
        self.popup_launch_lbl.pack(side="left", fill="x", expand=True)
        tk.Button(launch_row, text="Pick M Launch", width=12, command=lambda: self.set_pick_mode("missile_start"), bg="#d35454", fg="white", bd=0).pack(side="right")

        target_row = tk.Frame(picks, bg="#1e1e24")
        target_row.pack(fill="x", padx=10, pady=2)
        self.popup_target_lbl = tk.Label(target_row, anchor="w", fg="#ffd166", bg="#1e1e24", font=("Segoe UI", 8))
        self.popup_target_lbl.pack(side="left", fill="x", expand=True)
        tk.Button(target_row, text="Pick M Target", width=12, command=lambda: self.set_pick_mode("missile_target"), bg="#d9a441", fg="white", bd=0).pack(side="right")

        interceptor_row = tk.Frame(picks, bg="#1e1e24")
        interceptor_row.pack(fill="x", padx=10, pady=(2, 6))
        self.popup_interceptor_lbl = tk.Label(interceptor_row, anchor="w", fg="#7be0d6", bg="#1e1e24", font=("Segoe UI", 8))
        self.popup_interceptor_lbl.pack(side="left", fill="x", expand=True)
        tk.Button(interceptor_row, text="Pick Intcp", width=12, command=lambda: self.set_pick_mode("interceptor_start"), bg="#1abc9c", fg="white", bd=0).pack(side="right")

        values = tk.LabelFrame(self.globe_picks_window, text="Selected Coordinates", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9, "bold"))
        values.pack(fill="x", padx=12, pady=(0, 12))
        for title, lat_var, lon_var, altitude_var in (
            ("Missile Launch", self.missile_start_lat_var, self.missile_start_lon_var, self.missile_start_altitude_var),
            ("Missile Target", self.missile_target_lat_var, self.missile_target_lon_var, self.missile_target_altitude_var),
            ("Interceptor Launch", self.interceptor_start_lat_var, self.interceptor_start_lon_var, self.interceptor_start_altitude_var),
        ):
            section = tk.Frame(values, bg="#1e1e24")
            section.pack(fill="x", padx=12, pady=4)
            tk.Label(section, text=title, width=18, anchor="w", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9, "bold")).pack(side="left")
            tk.Label(section, text="Lat", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 4))
            tk.Entry(section, textvariable=lat_var, width=8).pack(side="left", padx=(0, 6))
            tk.Label(section, text="Lon", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 4))
            tk.Entry(section, textvariable=lon_var, width=8).pack(side="left", padx=(0, 6))
            tk.Label(section, text="Alt km", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 4))
            tk.Entry(section, textvariable=altitude_var, width=8).pack(side="left")
        self.refresh_coordinate_labels()

    def close_globe_picks_window(self):
        if self.globe_picks_window is not None and self.globe_picks_window.winfo_exists():
            self.globe_picks_window.destroy()
        self.globe_picks_window = None
        self.popup_launch_lbl = None
        self.popup_target_lbl = None
        self.popup_interceptor_lbl = None

    def on_canvas_configure(self, event):
        self.scroll_canvas.itemconfigure(self.content_window, width=event.width)
        target_size = max(event.width - 40, 1)
        if target_size != self.globe_canvas_width or target_size != self.globe_canvas_height:
            self.globe_canvas_width = target_size
            self.globe_canvas_height = target_size
            self.update_globe_radius()
            self.globe_canvas.config(width=self.globe_canvas_width, height=self.globe_canvas_height)
            self.render_globe()

    def get_drag_sensitivity(self):
        zoom = float(self.globe_zoom)
        yaw_sens = 0.55 / max(zoom, 0.1)
        pitch_sens = 0.45 / max(zoom, 0.1)
        return yaw_sens, pitch_sens

    def on_globe_canvas_resize(self, event):
        pass

    def on_globe_mousewheel(self, event):
        delta = getattr(event, "delta", 0)
        if delta > 0 or getattr(event, "num", None) == 4:
            factor = 1.08
        elif delta < 0 or getattr(event, "num", None) == 5:
            factor = 1.0 / 1.08
        else:
            return
        self.globe_zoom = min(max(self.globe_zoom * factor, 0.65), 3.4)
        self.update_globe_radius()
        self.render_globe()

    def set_pick_mode(self, mode):
        if mode not in {"missile_start", "missile_target", "interceptor_start", "group_missile_start", "group_missile_target", "group_interceptor_start"}:
            self.pick_mode = None
            return
        self.pick_mode = mode
        labels = {
            "missile_start": "Pick mode: click the wireframe globe to set missile launch. Drag rotates. Wheel zooms.",
            "missile_target": "Pick mode: click the wireframe globe to set missile target. Drag rotates. Wheel zooms.",
            "interceptor_start": "Pick mode: click the wireframe globe to set interceptor launch. Drag rotates. Wheel zooms.",
            "group_missile_start": f"PICK MODE: CLICK THE GLOBE TO SET LAUNCH CENTER FOR GROUP {self.temp_group_name}!",
            "group_missile_target": f"PICK MODE: CLICK THE GLOBE TO SET TARGET CENTER FOR GROUP {self.temp_group_name}!",
            "group_interceptor_start": f"PICK MODE: CLICK THE GLOBE TO SET INTERCEPTOR BASE CENTER FOR GROUP {self.temp_group_name}!",
        }
        # Use bright warning gold/yellow color and bold text for group pick instructions to make them highly visible on the HUD
        lbl_color = "#ffd166" if "group" in mode else "#7bdff2"
        self.status_lbl.config(text=labels[mode], fg=lbl_color, font=("Segoe UI", 9, "bold") if "group" in mode else ("Segoe UI", 9))
        self.render_globe()

    def on_add_missile_group(self):
        group_name = simpledialog.askstring("Add Missile Group", "Enter Group Name (e.g. A, B, C):", parent=self.root, initialvalue="A")
        if not group_name:
            return
        group_name = group_name.strip().upper()
        num_missiles = simpledialog.askinteger("Add Missile Group", "Enter Number of Missiles (Enter 0 to delete group):", parent=self.root, minvalue=0, initialvalue=3)
        if num_missiles is None:
            return
        if num_missiles == 0:
            if group_name in self.missile_groups:
                del self.missile_groups[group_name]
                messagebox.showinfo("Group Deleted", f"Missile Group {group_name} has been successfully deleted.", parent=self.root)
                self.refresh_coordinate_labels()
                self.save_settings()
                self.render_globe()
            else:
                messagebox.showinfo("Group Not Found", f"Missile Group {group_name} does not exist.", parent=self.root)
            return

        self.temp_group_name = group_name
        self.temp_num_missiles = num_missiles
        # Show prompt first, then schedule set_pick_mode to avoid event leakage from clicking OK
        messagebox.showinfo("Pick Launch Center", f"Please left-click on the globe map to set the Launch Center for Group {group_name}.", parent=self.root)
        self.root.after(300, lambda: self.set_pick_mode("group_missile_start"))

    def on_add_interceptor_group(self):
        group_name = simpledialog.askstring("Add Interceptor Group", "Enter Group Name (e.g. A, B, C):", parent=self.root, initialvalue="A")
        if not group_name:
            return
        group_name = group_name.strip().upper()
        num_interceptors = simpledialog.askinteger("Add Interceptor Group", "Enter Number of Interceptors (Enter 0 to delete group):", parent=self.root, minvalue=0, initialvalue=3)
        if num_interceptors is None:
            return
        if num_interceptors == 0:
            if group_name in self.interceptor_groups:
                del self.interceptor_groups[group_name]
                messagebox.showinfo("Group Deleted", f"Interceptor Group {group_name} has been successfully deleted.", parent=self.root)
                self.refresh_coordinate_labels()
                self.save_settings()
                self.render_globe()
            else:
                messagebox.showinfo("Group Not Found", f"Interceptor Group {group_name} does not exist.", parent=self.root)
            return

        self.temp_group_name = group_name
        self.temp_num_missiles = num_interceptors
        messagebox.showinfo("Pick Base Center", f"Please left-click on the globe map to set the Interceptor Base Center for Group {group_name}.", parent=self.root)
        self.root.after(300, lambda: self.set_pick_mode("group_interceptor_start"))

    def update_globe_radius(self):
        self.globe_radius_px = int(min(self.globe_canvas_width, self.globe_canvas_height) * 0.45 * self.globe_zoom)

    def lat_lon_to_unit(self, lat_deg, lon_deg):
        lat = math.radians(lat_deg)
        lon = math.radians(lon_deg)
        x = math.cos(lat) * math.cos(lon)
        y = math.sin(lat)
        z = -math.cos(lat) * math.sin(lon)
        return np.array([x, y, z], dtype=float)

    def unit_to_lat_lon(self, point):
        point = np.asarray(point, dtype=float)
        norm = np.linalg.norm(point)
        if norm < 1e-9:
            return None
        point = point / norm
        lat = math.degrees(math.asin(point[1]))
        lon = math.degrees(math.atan2(-point[2], point[0]))
        return float(lat), float(lon)

    def get_center_geolocation(self):
        return self.unit_to_lat_lon(self.inverse_view_rotation(np.array([0.0, 0.0, 1.0], dtype=float)))

    def update_view_center_display(self):
        lat_lon = self.get_center_geolocation()
        if lat_lon is None:
            return
        lat, lon = lat_lon
        
        is_sim = (type(self).__name__ == "SimulationWindow")
        if is_sim and self.get_view_altitude_km() < 15.0:
            return
            
        self.updating_view_center_fields = True
        try:
            self.view_yaw_var.set(f"{self.view_yaw_deg:.2f}")
            self.view_pitch_var.set(f"{self.view_pitch_deg:.2f}")
            if self.pick_mode is not None:
                self.view_center_lat_var.set("")
                self.view_center_lon_var.set("")
            else:
                self.view_center_lat_var.set(f"{lat:.2f}")
                self.view_center_lon_var.set(f"{lon:.2f}")
        finally:
            self.updating_view_center_fields = False

    def canvas_to_geolocation(self, canvas_x, canvas_y):
        cx = self.globe_canvas_width / 2
        cy = self.globe_canvas_height / 2
        u = (canvas_x - cx) / self.globe_radius_px
        v = (cy - canvas_y) / self.globe_radius_px
        dist_sq = u*u + v*v
        if dist_sq > 1.0:
            return None
        view_point = np.array([u, v, math.sqrt(1.0 - dist_sq)], dtype=float)
        return self.unit_to_lat_lon(self.inverse_view_rotation(view_point))

    def event_to_geolocation(self, event):
        return self.canvas_to_geolocation(event.x, event.y)

    def on_globe_mouse_move(self, event):
        geo = self.canvas_to_geolocation(event.x, event.y)
        if geo is None:
            self.mouse_geo_var.set("Mouse: outside globe")
            return
        lat, lon = geo
        self.mouse_geo_var.set(f"Mouse: Lat {lat:.2f}, Lon {lon:.2f}")

    def on_globe_mouse_leave(self, event=None):
        self.mouse_geo_var.set("Mouse: move over globe")

    def center_view_on(self, lat, lon):
        lat = max(min(float(lat), 90.0), -90.0)
        lon = ((float(lon) + 180.0) % 360.0) - 180.0
        point = self.lat_lon_to_unit(lat, lon)
        horizontal = math.hypot(point[0], point[2])
        self.view_yaw_deg = math.degrees(math.atan2(-point[0], point[2]))
        self.view_pitch_deg = math.degrees(math.atan2(point[1], horizontal))
        self.update_view_center_display()

    def apply_view_center_from_fields(self, event=None):
        if self.updating_view_center_fields:
            return
        try:
            lat = float(self.view_center_lat_var.get())
            lon = float(self.view_center_lon_var.get())
            altitude_km = float(self.view_altitude_km_var.get())
        except ValueError:
            self.status_lbl.config(text="Status: Enter numeric camera latitude, longitude, and altitude.", fg="#ffcc80")
            return
        if not -90.0 <= lat <= 90.0:
            self.status_lbl.config(text="Status: Camera latitude must be between -90 and 90.", fg="#ffcc80")
            return
        altitude_km = max(altitude_km, 0.0001)
        self.view_altitude_km_var.set(f"{altitude_km:.4f}" if altitude_km < 1.0 else (f"{altitude_km:.0f}" if altitude_km.is_integer() else f"{altitude_km:.1f}"))
        self.center_view_on(lat, lon)
        self.save_settings()
        self.status_lbl.config(text=f"Status: Camera set to Lat {lat:.2f}, Lon {lon:.2f}, Alt {altitude_km:.0f} km", fg="#cfd8dc")
        self.render_globe()

    def apply_view_angle_from_fields(self, event=None):
        if self.updating_view_center_fields:
            return
        try:
            yaw = float(self.view_yaw_var.get())
            pitch = float(self.view_pitch_var.get())
        except ValueError:
            self.status_lbl.config(text="Status: Enter numeric view yaw and pitch.", fg="#ffcc80")
            return
        self.view_yaw_deg = ((yaw + 180.0) % 360.0) - 180.0
        self.view_pitch_deg = max(min(pitch, 85.0), -85.0)
        self.save_settings()
        self.status_lbl.config(text=f"Status: View angle set to Yaw {self.view_yaw_deg:.2f}, Pitch {self.view_pitch_deg:.2f}", fg="#cfd8dc")
        self.render_globe()

    def apply_view_rotation(self, point):
        yaw = math.radians(self.view_yaw_deg)
        pitch = math.radians(self.view_pitch_deg)
        x, y, z = point
        cos_yaw, sin_yaw = math.cos(yaw), math.sin(yaw)
        x1 = cos_yaw * x + sin_yaw * z
        y1 = y
        z1 = -sin_yaw * x + cos_yaw * z
        cos_pitch, sin_pitch = math.cos(pitch), math.sin(pitch)
        x2 = x1
        y2 = cos_pitch * y1 - sin_pitch * z1
        z2 = sin_pitch * y1 + cos_pitch * z1
        return np.array([x2, y2, z2], dtype=float)

    def inverse_view_rotation(self, point):
        pitch = math.radians(-self.view_pitch_deg)
        yaw = math.radians(-self.view_yaw_deg)
        x, y, z = point
        cos_pitch, sin_pitch = math.cos(pitch), math.sin(pitch)
        x1 = x
        y1 = cos_pitch * y - sin_pitch * z
        z1 = sin_pitch * y + cos_pitch * z
        cos_yaw, sin_yaw = math.cos(yaw), math.sin(yaw)
        x2 = cos_yaw * x1 + sin_yaw * z1
        y2 = y1
        z2 = -sin_yaw * x1 + cos_yaw * z1
        return np.array([x2, y2, z2], dtype=float)

    def get_view_altitude_km(self):
        try:
            return max(float(self.view_altitude_km_var.get()), 0.0001)
        except ValueError:
            return 0.0001

    def get_view_camera_distance(self):
        try:
            return max(float(self.view_altitude_km_var.get()), 0.0001) / EARTH_RADIUS_KM + 2.25
        except ValueError:
            return 2.25

    def project_to_canvas(self, point):
        # ConfigGui ALWAYS uses the orbit space view projection so the user can easily select coordinates
        view = self.apply_view_rotation(point)
        cx = self.globe_canvas_width / 2
        cy = self.globe_canvas_height / 2
        x = cx + view[0] * self.globe_radius_px
        y = cy - view[1] * self.globe_radius_px
        return view, x, y

    def clip_canvas_segment_to_globe(self, x1, y1, x2, y2):
        cx = self.globe_canvas_width / 2
        cy = self.globe_canvas_height / 2
        radius = max(self.globe_radius_px - 1.0, 1.0)
        dx = x2 - x1
        dy = y2 - y1
        fx = x1 - cx
        fy = y1 - cy
        a = dx * dx + dy * dy
        if a <= 1e-9:
            if fx * fx + fy * fy <= radius * radius:
                return x1, y1, x2, y2
            return None
        b = 2.0 * (fx * dx + fy * dy)
        c = fx * fx + fy * fy - radius * radius
        disc = b * b - 4.0 * a * c
        inside_1 = fx * fx + fy * fy <= radius * radius
        inside_2 = (x2 - cx) * (x2 - cx) + (y2 - cy) * (y2 - cy) <= radius * radius
        if inside_1 and inside_2:
            return x1, y1, x2, y2
        if disc < 0.0:
            return None
        sqrt_disc = math.sqrt(disc)
        roots = sorted(((-b - sqrt_disc) / (2.0 * a), (-b + sqrt_disc) / (2.0 * a)))
        hits = [t for t in roots if 0.0 <= t <= 1.0]
        if inside_1 and not inside_2:
            if not hits:
                return None
            t = hits[-1]
            return x1, y1, x1 + dx * t, y1 + dy * t
        if inside_2 and not inside_1:
            if not hits:
                return None
            t = hits[0]
            return x1 + dx * t, y1 + dy * t, x2, y2
        if len(hits) >= 2:
            t0, t1 = hits[0], hits[-1]
            return x1 + dx * t0, y1 + dy * t0, x1 + dx * t1, y1 + dy * t1
        return None

    def draw_polyline_segments(self, points, color, width=1, dash=None):
        visible_segment = []
        for point in points:
            view, x, y = self.project_to_canvas(point)
            if view[2] >= -0.02:
                visible_segment.extend([x, y])
            else:
                if len(visible_segment) >= 4:
                    self.globe_canvas.create_line(*visible_segment, fill=color, width=width, dash=dash)
                visible_segment = []
        if len(visible_segment) >= 4:
            self.globe_canvas.create_line(*visible_segment, fill=color, width=width, dash=dash)

    def draw_wireframe(self):
        is_sim = (type(self).__name__ == "SimulationWindow")
        if is_sim and self.get_view_altitude_km() < 15.0:
            return
        for lat in range(-75, 90, 15):
            if lat == 0:
                continue
            ring = [self.lat_lon_to_unit(lat, lon) for lon in np.linspace(-180, 180, 145)]
            self.draw_polyline_segments(ring, "#4c4f57")
        for lon in range(-165, 180, 15):
            meridian = [self.lat_lon_to_unit(lat, lon) for lat in np.linspace(-90, 90, 145)]
            self.draw_polyline_segments(meridian, "#4c4f57")

    def draw_globe_guides(self):
        is_sim = (type(self).__name__ == "SimulationWindow")
        if is_sim and self.get_view_altitude_km() < 15.0:
            return
        
        # Show equator only in global space View A (or in the Main Setup GUI); hide in close-up views B, C, D to prevent map clutter
        if is_sim and hasattr(self, "view_mode_var"):
            mode = self.view_mode_var.get()
            if mode != "A":
                return

        equator = [self.lat_lon_to_unit(0, lon) for lon in np.linspace(-180, 180, 181)]
        is_wireframe = self.show_wireframe_var.get()
        equator_dash = None if is_wireframe else (7, 5)
        equator_width = 2 if is_wireframe else 1
        self.draw_polyline_segments(equator, "#6fa8dc", width=equator_width, dash=equator_dash)
        north_point = self.lat_lon_to_unit(90.0, 0.0)
        south_point = self.lat_lon_to_unit(-90.0, 0.0)
        north_view, _, _ = self.project_to_canvas(north_point)
        south_view, _, _ = self.project_to_canvas(south_point)
        pole_choice = max(((north_view[2], 90.0, "N"), (south_view[2], -90.0, "S")), key=lambda item: item[0])
        if pole_choice[0] > -0.98:
            self.draw_pole_marker(pole_choice[1], "#8fd3ff", pole_choice[2])

    def load_shapefile_segments(self, shp_path, point_step=1):
        if not shp_path or not os.path.exists(shp_path):
            return []
        point_step = max(int(point_step), 1)
        try:
            reader = shapefile.Reader(shp_path)
        except Exception:
            return []
        segments = []
        for shape_record in reader.shapeRecords():
            points = shape_record.shape.points
            parts = list(shape_record.shape.parts) + [len(points)]
            for start, end in zip(parts, parts[1:]):
                sampled = []
                sub_points = points[start:end]
                for idx in range(0, len(sub_points), point_step):
                    lon, lat = sub_points[idx]
                    sampled.append(self.lat_lon_to_unit(lat, lon))
                if len(sub_points) % point_step != 1 and len(sub_points) > 1:
                    lon, lat = sub_points[-1]
                    sampled.append(self.lat_lon_to_unit(lat, lon))
                if len(sampled) >= 2:
                    segments.append(sampled)
        return segments

    def load_country_labels(self, shp_path):
        if not shp_path or not os.path.exists(shp_path):
            return []
        try:
            reader = shapefile.Reader(shp_path)
        except Exception:
            return []
        labels = []
        for record in reader.records():
            name = record[17] if len(record) > 17 else (record[4] if len(record) > 4 else None)
            lat = record[reader.fields.index(["LABEL_Y", "N", 16, 11]) - 1] if ["LABEL_Y", "N", 16, 11] in reader.fields else None
            lon = record[reader.fields.index(["LABEL_X", "N", 16, 11]) - 1] if ["LABEL_X", "N", 16, 11] in reader.fields else None
            if not name or lat is None or lon is None:
                continue
            labels.append({"name": str(name), "lat": float(lat), "lon": float(lon)})
        return labels

    def load_city_labels(self, shp_path):
        return []

    def draw_filled_band(self, segment, fill_color):
        pass

    def draw_map_globe(self):
        self.globe_canvas.configure(bg="#0b1e33")
        for segment in self.coastline_segments_drag:
            self.draw_polyline_segments(segment, "#cfd6d0", width=2)
        if self.show_boundaries_var.get():
            for segment in self.boundary_segments_drag:
                self.draw_polyline_segments(segment, "#8ab6a2", width=1)

    def draw_text_with_outline(self, x, y, text, anchor="center", fill="white", font=("Segoe UI", 9), outline="black", width=2, y_offset=0):
        for dx, dy in ((-1, -1), (-1, 1), (1, -1), (1, 1), (0, -1), (0, 1), (-1, 0), (1, 0)):
            self.globe_canvas.create_text(x + dx, y + dy + y_offset, text=text, anchor=anchor, fill=outline, font=font)
        self.globe_canvas.create_text(x, y + y_offset, text=text, anchor=anchor, fill=fill, font=font)

    def draw_marker_shape(self, x, y, radius, fill, outline, shape="circle", width=1):
        if shape == "diamond":
            self.globe_canvas.create_polygon(x, y - radius, x + radius, y, x, y + radius, x - radius, y, fill=fill, outline=outline, width=width)
        elif shape == "square":
            self.globe_canvas.create_rectangle(x - radius, y - radius, x + radius, y + radius, fill=fill, outline=outline, width=width)
        elif shape == "triangle":
            self.globe_canvas.create_polygon(x, y - radius, x + radius, y + radius, x - radius, y + radius, fill=fill, outline=outline, width=width)
        elif shape == "cross":
            cross_color = outline or fill
            self.globe_canvas.create_line(x - radius, y, x + radius, y, fill=cross_color, width=max(width, 2))
            self.globe_canvas.create_line(x, y - radius, x, y + radius, fill=cross_color, width=max(width, 2))
        else:
            self.globe_canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=fill, outline=outline, width=width)

    def draw_geographic_labels(self):
        is_sim = (type(self).__name__ == "SimulationWindow")
        if is_sim and self.get_view_altitude_km() < 15.0:
            return
        if self.show_wireframe_var.get() or self.is_dragging_globe:
            return
        zoom = float(self.globe_zoom)
        if zoom >= 1.05:
            country_count = min(32, 14 + int((zoom - 1.05) * 10))
            country_spacing = max(30, 54 - int((zoom - 1.05) * 8))
            self.draw_label_set(self.country_labels, max_items=country_count, min_depth=0.18, min_spacing=country_spacing, fill="#f2f4f8", font=("Segoe UI", 8, "bold"), y_offset=-6)
        if zoom >= 1.35:
            city_count = min(140, 18 + int((zoom - 1.35) * 55))
            city_spacing = max(14, 34 - int((zoom - 1.35) * 7))
            city_depth = 0.28 if zoom < 2.1 else 0.18
            self.draw_label_set(self.city_labels, max_items=city_count, min_depth=city_depth, min_spacing=city_spacing, fill="#ffd8a8", font=("Segoe UI", 7), y_offset=8)

    def draw_label_set(self, labels, max_items, min_depth, min_spacing, fill, font, y_offset=0):
        placed = []
        min_spacing_sq = float(min_spacing * min_spacing)
        count = 0
        for item in labels:
            point = self.lat_lon_to_unit(item["lat"], item["lon"])
            view, x, y = self.project_to_canvas(point)
            if view[2] < min_depth:
                continue
            cx = self.globe_canvas_width / 2
            cy = self.globe_canvas_height / 2
            if (x - cx) * (x - cx) + (y - cy) * (y - cy) > self.globe_radius_px * self.globe_radius_px * 0.99:
                continue
            overlap = False
            for px, py in placed:
                if (x - px) * (x - px) + (y - py) * (y - py) < min_spacing_sq:
                    overlap = True
                    break
            if not overlap:
                self.draw_text_with_outline(x, y, item["name"], fill=fill, font=font, y_offset=y_offset)
                placed.append((x, y))
                count += 1
                if count >= max_items:
                    break

    def draw_marker(self, lat, lon, altitude_km, color, label, always_show_label=False, label_anchor="w", label_offset=None, shape="circle", halo_color="#081018", halo_radius=2):
        point_surf = self.lat_lon_to_unit(lat, lon)
        altitude_units = altitude_km / EARTH_RADIUS_KM
        point_elev = point_surf * (1.0 + altitude_units)
        view_surf, x_surf, y_surf = self.project_to_canvas(point_surf)
        if altitude_km > 0.0:
            view_elev, x_elev, y_elev = self.project_to_canvas(point_elev)
        else:
            view_elev = view_surf
            x_elev, y_elev = x_surf, y_surf

        if view_surf[2] < -0.05:
            return

        cx = self.globe_canvas_width / 2
        cy = self.globe_canvas_height / 2
        if (x_surf - cx) * (x_surf - cx) + (y_surf - cy) * (y_surf - cy) > self.globe_radius_px * self.globe_radius_px * 0.995:
            return

        radius = 5
        if altitude_km > 0.0 and view_surf[2] > -0.05 and view_elev[2] > -0.05:
            self.globe_canvas.create_line(x_surf, y_surf, x_elev, y_elev, fill=color, width=1.5, dash=(2, 2))
            self.draw_marker_shape(x_surf, y_surf, 3, fill="", outline=color, shape="circle", width=1.5)

        self.draw_marker_shape(x_elev, y_elev, radius + halo_radius, fill=halo_color, outline=halo_color, shape=shape, width=1)
        self.draw_marker_shape(x_elev, y_elev, radius, fill=color, outline="white", shape=shape, width=1.5)

        show_lbl = always_show_label or (float(self.globe_zoom) >= 1.02)
        if show_lbl:
            offset = label_offset or (radius + 5)
            lx = x_elev + offset if label_anchor == "w" else (x_elev - offset if label_anchor == "e" else x_elev)
            ly = y_elev
            self.draw_text_with_outline(lx, ly, label, anchor=label_anchor, fill=color, font=("Segoe UI", 8, "bold"))

    def draw_pole_marker(self, lat, color, label):
        point = self.lat_lon_to_unit(lat, 0.0)
        view, x, y = self.project_to_canvas(point)
        if view[2] < -0.05:
            return
        cx = self.globe_canvas_width / 2
        cy = self.globe_canvas_height / 2
        if (x - cx) * (x - cx) + (y - cy) * (y - cy) > self.globe_radius_px * self.globe_radius_px * 0.99:
            return
        self.draw_marker_shape(x, y, 3, fill=color, outline="white", shape="circle", width=1)
        self.draw_text_with_outline(x + 7, y - 4, label, anchor="w", fill=color, font=("Segoe UI", 7, "bold"))

    def choose_scale_miles(self, target_miles):
        presets = [5000, 2000, 1000, 500, 200, 100, 50, 20, 10, 5, 2, 1]
        for p in presets:
            if target_miles >= p:
                return p
        return 1

    def draw_scale_bar(self):
        is_sim = (type(self).__name__ == "SimulationWindow")
        if is_sim and self.get_view_altitude_km() < 15.0:
            return
        EARTH_RADIUS_MILES = 3958.8
        miles_per_px = EARTH_RADIUS_MILES / max(self.globe_radius_px, 1.0)
        max_width_px = min(140.0, self.globe_radius_px * 0.42)
        target_miles = max_width_px * miles_per_px * 0.7
        scale_miles = self.choose_scale_miles(target_miles)
        scale_width_px = scale_miles / miles_per_px
        x0 = 26
        y0 = self.globe_canvas_height - 34
        x1 = x0 + scale_width_px
        self.globe_canvas.create_line(x0, y0, x1, y0, fill="#f2f4f8", width=3)
        self.globe_canvas.create_line(x0, y0 - 5, x0, y0 + 5, fill="#f2f4f8", width=2)
        self.globe_canvas.create_line(x1, y0 - 5, x1, y0 + 5, fill="#f2f4f8", width=2)
        self.draw_text_with_outline((x0 + x1) / 2, y0 - 10, f"{int(scale_miles):,} miles", fill="#f2f4f8", font=("Segoe UI", 8, "bold"), anchor="s")

    def draw_viewpoint_marker(self):
        if hasattr(self, "view_mode_var") and self.view_mode_var.get() == "D":
            return
            
        cam_alt = self.get_view_altitude_km()
        if cam_alt < 15.0:
            return

        if hasattr(self, "view_mode_var"):
            mode = self.view_mode_var.get()
            if mode == "A":
                label = "View A"
            elif mode == "B":
                label = "View B"
            elif mode == "D":
                label = "View D"
            else:
                label = "View C"
        else:
#            label = "View Center"
            label = ""
        cx = self.globe_canvas_width / 2
        cy = self.globe_canvas_height / 2
        self.draw_marker_shape(cx, cy, 3, fill="#ff66c4", outline="#ff66c4", shape="circle", width=1)
        self.draw_text_with_outline(cx + 10, cy - 10, text=label, anchor="w", fill="#ff66c4", font=("Segoe UI", 8, "bold"))

        # 3D projected vectors
        p_center = self.inverse_view_rotation(np.array([0.0, 0.0, 1.0], dtype=float))
        
        x, y, z = p_center
        horizontal_r = math.sqrt(max(1.0 - y * y, 1e-12))
        
        if horizontal_r < 1e-6:
            t_east = np.array([0.0, 0.0, -1.0], dtype=float)
            t_north = np.array([1.0, 0.0, 0.0], dtype=float) if y > 0 else np.array([-1.0, 0.0, 0.0], dtype=float)
        else:
            t_east = np.array([z / horizontal_r, 0.0, -x / horizontal_r], dtype=float)
            t_north = np.array([-y * x / horizontal_r, horizontal_r, -y * z / horizontal_r], dtype=float)

        yaw_rad = math.radians(self.view_yaw_deg)
        pitch_rad = math.radians(self.view_pitch_deg)

        # Look vector in local ECEF tangent frame
        l_horiz = math.cos(yaw_rad) * t_north + math.sin(yaw_rad) * t_east
        l_vec = math.cos(pitch_rad) * l_horiz + math.sin(pitch_rad) * p_center

        # 1. Project the 3D Horizon Disk
        # We sample 16 points along the disk of radius 0.06 (approx 19px).
        # We scale the t_north component by 0.5 to simulate a tilted horizontal perspective ellipse.
        disk_radius = 0.06
        disk_points = []
        for i in range(16):
            ang = (i / 16.0) * 2.0 * math.pi
            disk_pt = p_center + disk_radius * (math.cos(ang) * t_east + math.sin(ang) * 0.5 * t_north)
            _, dx, dy = self.project_to_canvas(disk_pt)
            disk_points.extend((dx, dy))
        # Draw dynamic horizon plane ellipse
        self.globe_canvas.create_polygon(*disk_points, fill="", outline="#80cbc4", width=1.5, dash=(2, 2))

        # 2. Project dynamic axes: North (green), East (red), Up (blue)
        axis_len = 0.05
        
        _, x_n, y_n = self.project_to_canvas(p_center + axis_len * t_north)
        _, x_e, y_e = self.project_to_canvas(p_center + axis_len * t_east)
        _, x_u, y_u = self.project_to_canvas(p_center + axis_len * p_center)

        # Draw local North axis
        self.globe_canvas.create_line(cx, cy, x_n, y_n, fill="#2ecc71", width=2, arrow="last", arrowshape=(5, 6, 2))
        self.draw_text_with_outline(x_n + (x_n - cx)*0.3, y_n + (y_n - cy)*0.3, text="N", anchor="center", fill="#2ecc71", font=("Segoe UI", 7, "bold"))

        # Draw local East axis
        self.globe_canvas.create_line(cx, cy, x_e, y_e, fill="#e74c3c", width=2, arrow="last", arrowshape=(5, 6, 2))
        self.draw_text_with_outline(x_e + (x_e - cx)*0.3, y_e + (y_e - cy)*0.3, text="E", anchor="center", fill="#e74c3c", font=("Segoe UI", 7, "bold"))

        # Draw local Zenith/Up axis
        self.globe_canvas.create_line(cx, cy, x_u, y_u, fill="#3498db", width=2, arrow="last", arrowshape=(5, 6, 2))
        self.draw_text_with_outline(x_u + (x_u - cx)*0.3, y_u + (y_u - cy)*0.3, text="UP", anchor="center", fill="#3498db", font=("Segoe UI", 7, "bold"))

        # 3. Project and draw the 3D View Angle Look Vector (pink arrow)
        _, x_l, y_l = self.project_to_canvas(p_center + 0.08 * l_vec)
        self.globe_canvas.create_line(cx, cy, x_l, y_l, fill="#ff66c4", width=3, arrow="last", arrowshape=(7, 9, 2.5))
#        self.draw_text_with_outline(x_l + (x_l - cx)*0.3, y_l + (y_l - cy)*0.3, text="LOOK", anchor="center", fill="#ff66c4", font=("Segoe UI", 7, "bold"))
        self.draw_text_with_outline(x_l + (x_l - cx)*0.3, y_l + (y_l - cy)*0.3, text="", anchor="center", fill="#ff66c4", font=("Segoe UI", 7, "bold"))

    def render_globe(self):
        self.update_view_center_display()
        self.globe_canvas.delete("all")
        self.globe_canvas.configure(bg="#000000" if self.show_wireframe_var.get() else "#0b1e33")
        pad = 18
        cx = self.globe_canvas_width / 2
        cy = self.globe_canvas_height / 2
        self.globe_canvas.create_oval(
            cx - self.globe_radius_px,
            cy - self.globe_radius_px,
            cx + self.globe_radius_px,
            cy + self.globe_radius_px,
            fill="#163f63" if not self.show_wireframe_var.get() else "",
            outline="#70757f",
            width=2,
        )
        if self.show_wireframe_var.get():
            self.draw_wireframe()
        else:
            self.draw_map_globe()
        self.draw_globe_guides()
        self.draw_geographic_labels()
        self.draw_scale_bar()
        self.draw_viewpoint_marker()

        if hasattr(self, "missile_groups") and self.missile_groups:
            for group_name, pairs in self.missile_groups.items():
                for pair in pairs:
                    i = pair["id"]
                    self.draw_marker(pair["start_lat"], pair["start_lon"], 0.0, "#ff6b6b", f"{group_name}-M{i}", shape="circle", halo_color="#ffffff", halo_radius=3)
                    self.draw_marker(pair["target_lat"], pair["target_lon"], 0.0, "#ffd166", f"{group_name}-T{i}", shape="diamond", halo_color="#ffffff", halo_radius=3)
        else:
            self.draw_marker(self.missile_start_lat_var.get(), self.missile_start_lon_var.get(), self.missile_start_altitude_var.get(), "#ff6b6b", "M-L", shape="circle", halo_color="#ffffff", halo_radius=3)
            self.draw_marker(self.missile_target_lat_var.get(), self.missile_target_lon_var.get(), self.missile_target_altitude_var.get(), "#ffd166", "M-Tgt", shape="diamond", halo_color="#ffffff", halo_radius=3)
        
        if hasattr(self, "interceptor_groups") and self.interceptor_groups:
            for group_name, pairs in self.interceptor_groups.items():
                for pair in pairs:
                    i = pair["id"]
                    self.draw_marker(pair["start_lat"], pair["start_lon"], 0.0, "#22d3a6", f"{group_name}-Int{i}", shape="triangle", halo_color="#ffffff", halo_radius=3)
        else:
            self.draw_marker(self.interceptor_start_lat_var.get(), self.interceptor_start_lon_var.get(), self.interceptor_start_altitude_var.get(), "#22d3a6", "Int", shape="triangle", halo_color="#ffffff", halo_radius=3)
        active = self.pick_mode.replace("_", " ").title() if self.pick_mode else "None"
        self.globe_canvas.create_text(pad, pad, text=f"Pick mode: {active}", anchor="nw", fill="#d9e1e8", font=("Segoe UI", 9, "bold"))
        self.globe_canvas.create_text(pad, pad + 22, text="Drag rotates | Click picks | Double-click centers | Wheel zooms", anchor="nw", fill="#93a4b1", font=("Segoe UI", 8))
    #    self.globe_canvas.create_text(pad, pad + 40, text=f"Build: {GUI_BUILD_TAG}", anchor="nw", fill="#6fb3ff", font=("Segoe UI", 8, "bold"))

    def load_settings(self):
        data = read_settings_data(self.settings_file)
        if not data:
            return
        msl_spd = float(data.get("missile_speed", self.missile_speed_var.get()))
        if msl_spd < 0.15:
            msl_spd *= 100.0
        self.missile_speed_var.set(msl_spd)
        int_spd = float(data.get("interceptor_speed", self.interceptor_speed_var.get()))
        if int_spd < 0.15:
            int_spd *= 100.0
        self.interceptor_speed_var.set(int_spd)
        self.proportional_gain_var.set(float(data.get("proportional_gain", self.proportional_gain_var.get())))
        self.auto_launch_var.set(bool(data.get("auto_launch_interceptor", self.auto_launch_var.get())))
        self.show_wireframe_var.set(bool(data.get("show_wireframe_globe", self.show_wireframe_var.get())))
        self.show_boundaries_var.set(bool(data.get("show_boundaries", self.show_boundaries_var.get())))
        self.offline_mode_var.set(bool(data.get("offline_mode", self.offline_mode_var.get())))
        self.tracking_algo_var.set(str(data.get("tracking_algorithm", "EKF")))
        self.mp_mode_var.set(bool(data.get("mp_mode", self.mp_mode_var.get())))
        self.drag_refresh_ms_var.set(float(data.get("drag_refresh_ms", self.drag_refresh_ms_var.get())))
        self.globe_zoom = float(data.get("globe_zoom", self.globe_zoom))
        self.missile_start_lat_var.set(float(data.get("missile_start_lat", self.missile_start_lat_var.get())))
        self.missile_start_lon_var.set(float(data.get("missile_start_lon", self.missile_start_lon_var.get())))
        self.missile_start_altitude_var.set(float(data.get("missile_start_altitude_km", self.missile_start_altitude_var.get())))
        self.missile_target_lat_var.set(float(data.get("missile_target_lat", self.missile_target_lat_var.get())))
        self.missile_target_lon_var.set(float(data.get("missile_target_lon", self.missile_target_lon_var.get())))
        self.missile_target_altitude_var.set(float(data.get("missile_target_altitude_km", self.missile_target_altitude_var.get())))
        self.interceptor_start_lat_var.set(float(data.get("interceptor_start_lat", self.interceptor_start_lat_var.get())))
        self.interceptor_start_lon_var.set(float(data.get("interceptor_start_lon", self.interceptor_start_lon_var.get())))
        self.interceptor_start_altitude_var.set(float(data.get("interceptor_start_altitude_km", self.interceptor_start_altitude_var.get())))
        self.view_yaw_deg = float(data.get("view_yaw_deg", self.view_yaw_deg))
        self.view_pitch_deg = float(data.get("view_pitch_deg", self.view_pitch_deg))
        self.view_altitude_km_var.set(str(max(float(data.get("view_altitude_km", self.view_altitude_km_var.get())), 0.0001)))
        self.interceptor_delay_var.set(float(data.get("interceptor_delay_sec", self.interceptor_delay_var.get())))
        self.msl_grp_delay_var.set(float(data.get("msl_grp_delay", self.msl_grp_delay_var.get())))
        self.msl_delay_var.set(float(data.get("msl_delay", self.msl_delay_var.get())))
        self.msl_path_size_var.set(float(data.get("msl_path_size", self.msl_path_size_var.get() or 3.0)))
        self.int_path_size_var.set(float(data.get("int_path_size", self.int_path_size_var.get() or 3.0)))
        self.missile_groups = data.get("missile_groups", {})
        self.interceptor_groups = data.get("interceptor_groups", {})
        main_window_size = read_saved_window_size(
            data,
            "main_window_width",
            "main_window_height",
        )
        if main_window_size is not None:
            geometry = f"{main_window_size[0]}x{main_window_size[1]}"
            try:
                main_window_x = int(data.get("main_window_x"))
                main_window_y = int(data.get("main_window_y"))
            except (TypeError, ValueError):
                main_window_x = None
                main_window_y = None
            if main_window_x is not None and main_window_y is not None:
                geometry = f"{geometry}+{main_window_x}+{main_window_y}"
            self.root.geometry(geometry)

    def save_settings(self):
        data = read_settings_data(self.settings_file)
        self.root.update_idletasks()
        
        def safe_float(var, default=0.0):
            try:
                return float(var.get())
            except Exception:
                return default

        data.update({
            "missile_speed": safe_float(self.missile_speed_var, 0.05),
            "interceptor_speed": safe_float(self.interceptor_speed_var, 0.07),
            "proportional_gain": safe_float(self.proportional_gain_var, 4.0),
            "auto_launch_interceptor": bool(self.auto_launch_var.get()),
            "show_wireframe_globe": bool(self.show_wireframe_var.get()),
            "show_boundaries": bool(self.show_boundaries_var.get()),
            "offline_mode": bool(self.offline_mode_var.get()),
            "tracking_algorithm": self.tracking_algo_var.get(),
            "mp_mode": bool(self.mp_mode_var.get()),
            "drag_refresh_ms": safe_float(self.drag_refresh_ms_var, 200.0),
            "globe_zoom": float(self.globe_zoom),
            "missile_start_lat": safe_float(self.missile_start_lat_var, 39.0),
            "missile_start_lon": safe_float(self.missile_start_lon_var, 125.0),
            "missile_start_altitude_km": safe_float(self.missile_start_altitude_var, 0.0),
            "missile_target_lat": safe_float(self.missile_target_lat_var, 38.0),
            "missile_target_lon": safe_float(self.missile_target_lon_var, -77.0),
            "missile_target_altitude_km": safe_float(self.missile_target_altitude_var, 0.0),
            "interceptor_start_lat": safe_float(self.interceptor_start_lat_var, 64.0),
            "interceptor_start_lon": safe_float(self.interceptor_start_lon_var, -147.0),
            "interceptor_start_altitude_km": safe_float(self.interceptor_start_altitude_var, 0.0),
            "interceptor_delay_sec": safe_float(self.interceptor_delay_var, 3.0),
            "msl_grp_delay": safe_float(self.msl_grp_delay_var, 5.0),
            "msl_delay": safe_float(self.msl_delay_var, 2.0),
            "msl_path_size": safe_float(self.msl_path_size_var, 3.0),
            "int_path_size": safe_float(self.int_path_size_var, 3.0),
            "view_altitude_km": safe_float(self.view_altitude_km_var, 1.0),
            "view_yaw_deg": float(self.view_yaw_deg),
            "view_pitch_deg": float(self.view_pitch_deg),
            "main_window_width": int(self.root.winfo_width()),
            "main_window_height": int(self.root.winfo_height()),
            "main_window_x": int(self.root.winfo_x()),
            "main_window_y": int(self.root.winfo_y()),
            "missile_groups": self.missile_groups,
            "interceptor_groups": self.interceptor_groups,
        })
        write_settings_data(self.settings_file, data)
        if self.simulation_window is not None and not self.simulation_window.closed:
            self.simulation_window.reload_parameters_from_gui()

    def reset_globe(self):
        self.pick_mode = None
        self.missile_groups = {}
        self.interceptor_groups = {}
        self.view_yaw_deg = self.default_view_yaw_deg
        self.view_pitch_deg = self.default_view_pitch_deg
        self.view_altitude_km_var.set("1")
        self.globe_zoom = 1.0
        self.missile_speed_var.set(self.default_settings["missile_speed"])
        self.interceptor_speed_var.set(self.default_settings["interceptor_speed"])
        self.proportional_gain_var.set(self.default_settings["proportional_gain"])
        self.auto_launch_var.set(self.default_settings["auto_launch_interceptor"])
        self.show_wireframe_var.set(self.default_settings["show_wireframe_globe"])
        self.show_boundaries_var.set(self.default_settings["show_boundaries"])
        self.offline_mode_var.set(self.default_settings.get("offline_mode", False))
        self.drag_refresh_ms_var.set(self.default_settings["drag_refresh_ms"])
        self.missile_start_lat_var.set(self.default_settings["missile_start_lat"])
        self.missile_start_lon_var.set(self.default_settings["missile_start_lon"])
        self.missile_start_altitude_var.set(self.default_settings["missile_start_altitude_km"])
        self.missile_target_lat_var.set(self.default_settings["missile_target_lat"])
        self.missile_target_lon_var.set(self.default_settings["missile_target_lon"])
        self.missile_target_altitude_var.set(self.default_settings["missile_target_altitude_km"])
        self.interceptor_start_lat_var.set(self.default_settings["interceptor_start_lat"])
        self.interceptor_start_lon_var.set(self.default_settings["interceptor_start_lon"])
        self.interceptor_start_altitude_var.set(self.default_settings["interceptor_start_altitude_km"])
        self.interceptor_delay_var.set(self.default_settings["interceptor_delay_sec"])
        self.update_globe_radius()
        self.refresh_coordinate_labels()
        self.render_globe()
        self.status_lbl.config(text="Status: Globe and scenario reset to defaults.", fg="#cfd8dc")

    def refresh_coordinate_labels(self):
        # 1. Update Missile Launch Summary
        if hasattr(self, "missile_groups") and self.missile_groups:
            groups_summary = " | ".join(f"Group {name}: {len(pairs)} missiles" for name, pairs in self.missile_groups.items())
        else:
            groups_summary = f"M Launch  {self.missile_start_lat_var.get():.2f}, {self.missile_start_lon_var.get():.2f}, {self.missile_start_altitude_var.get():.2f} km"
            
        if self.main_launch_lbl is not None and self.main_launch_lbl.winfo_exists():
            self.main_launch_lbl.config(text=groups_summary)
        if self.popup_launch_lbl is not None and self.popup_launch_lbl.winfo_exists():
            self.popup_launch_lbl.config(text=groups_summary)

        # 2. Update Missile Target Summary
        if hasattr(self, "missile_groups") and self.missile_groups:
            target_summary = "Group target centers mapped and randomized."
        else:
            target_summary = f"M Target  {self.missile_target_lat_var.get():.2f}, {self.missile_target_lon_var.get():.2f}, {self.missile_target_altitude_var.get():.2f} km"
            
        if self.main_target_lbl is not None and self.main_target_lbl.winfo_exists():
            self.main_target_lbl.config(text=target_summary)
        if self.popup_target_lbl is not None and self.popup_target_lbl.winfo_exists():
            self.popup_target_lbl.config(text=target_summary)

        # 3. Update Interceptor Launch Summary
        if hasattr(self, "interceptor_groups") and self.interceptor_groups:
            intcp_summary = " | ".join(f"Group {name}: {len(pairs)} interceptors" for name, pairs in self.interceptor_groups.items())
        else:
            intcp_summary = f"Intcp  {self.interceptor_start_lat_var.get():.2f}, {self.interceptor_start_lon_var.get():.2f}, {self.interceptor_start_altitude_var.get():.2f} km"
            
        if self.main_interceptor_lbl is not None and self.main_interceptor_lbl.winfo_exists():
            self.main_interceptor_lbl.config(text=intcp_summary)
        if self.popup_interceptor_lbl is not None and self.popup_interceptor_lbl.winfo_exists():
            self.popup_interceptor_lbl.config(text=intcp_summary)

    def find_clicked_target(self, click_x, click_y):
        min_depth = getattr(self, "render_min_depth", -0.05)
        
        # 1. Check Group Targets
        if hasattr(self, "missile_groups") and self.missile_groups:
            for group_name, pairs in self.missile_groups.items():
                for idx, pair in enumerate(pairs):
                    lat = pair["target_lat"]
                    lon = pair["target_lon"]
                    point = self.lat_lon_to_unit(lat, lon)
                    view, x, y = self.project_to_canvas(point)
                    if view[2] >= min_depth:
                        dist = math.hypot(click_x - x, click_y - y)
                        if dist <= 12.0:  # within 12 pixels
                            return {"type": "group_target", "group_name": group_name, "pair_index": idx}

        # 2. Check Group Missiles (Starts)
        if hasattr(self, "missile_groups") and self.missile_groups:
            for group_name, pairs in self.missile_groups.items():
                for idx, pair in enumerate(pairs):
                    lat = pair["start_lat"]
                    lon = pair["start_lon"]
                    point = self.lat_lon_to_unit(lat, lon)
                    view, x, y = self.project_to_canvas(point)
                    if view[2] >= min_depth:
                        dist = math.hypot(click_x - x, click_y - y)
                        if dist <= 12.0:
                            return {"type": "group_missile", "group_name": group_name, "pair_index": idx}

        # 3. Check Group Interceptors (Starts)
        if hasattr(self, "interceptor_groups") and self.interceptor_groups:
            for group_name, pairs in self.interceptor_groups.items():
                for idx, pair in enumerate(pairs):
                    lat = pair["start_lat"]
                    lon = pair["start_lon"]
                    point = self.lat_lon_to_unit(lat, lon)
                    view, x, y = self.project_to_canvas(point)
                    if view[2] >= min_depth:
                        dist = math.hypot(click_x - x, click_y - y)
                        if dist <= 12.0:
                            return {"type": "group_interceptor", "group_name": group_name, "pair_index": idx}
                            
        # 4. Check Single Missile Start
        try:
            lat = float(self.missile_start_lat_var.get())
            lon = float(self.missile_start_lon_var.get())
            point = self.lat_lon_to_unit(lat, lon)
            view, x, y = self.project_to_canvas(point)
            if view[2] >= min_depth:
                dist = math.hypot(click_x - x, click_y - y)
                if dist <= 12.0:
                    return {"type": "single_missile_start"}
        except Exception:
            pass

        # 5. Check Single Interceptor Start
        try:
            lat = float(self.interceptor_start_lat_var.get())
            lon = float(self.interceptor_start_lon_var.get())
            point = self.lat_lon_to_unit(lat, lon)
            view, x, y = self.project_to_canvas(point)
            if view[2] >= min_depth:
                dist = math.hypot(click_x - x, click_y - y)
                if dist <= 12.0:
                    return {"type": "single_interceptor_start"}
        except Exception:
            pass

        # 6. Check Single Target
        try:
            lat = float(self.missile_target_lat_var.get())
            lon = float(self.missile_target_lon_var.get())
            point = self.lat_lon_to_unit(lat, lon)
            view, x, y = self.project_to_canvas(point)
            if view[2] >= min_depth:
                dist = math.hypot(click_x - x, click_y - y)
                if dist <= 12.0:
                    return {"type": "single_target"}
        except Exception:
            pass
            
        return None

    def on_drag_start(self, event):
        self.suppress_left_release_action = False
        self.drag_last = (event.x, event.y)
        self.drag_origin = (event.x, event.y)
        self.drag_button = getattr(event, "num", None) or (1 if event.state & 0x0100 else 3)
        self.drag_moved = False
        
        # Check if left-click is near a target on the globe!
        if self.drag_button == 1:
            clicked_target = self.find_clicked_target(event.x, event.y)
            if clicked_target is not None:
                self.is_dragging_target = True
                self.grabbed_target = clicked_target
                self.suppress_left_release_action = True
                self.is_dragging_globe = False
                return
                
        self.is_dragging_globe = True

    def schedule_drag_render(self):
        if self.drag_render_job is not None:
            return
        delay = max(int(float(self.drag_refresh_ms_var.get())), 16)
        self.drag_render_job = self.root.after(delay, self.perform_drag_render)

    def perform_drag_render(self):
        self.drag_render_job = None
        self.render_globe()

    def on_drag_move(self, event):
        if self.drag_last is None:
            return
        dx = event.x - self.drag_last[0]
        dy = event.y - self.drag_last[1]
        if abs(dx) >= 1 or abs(dy) >= 1:
            self.drag_moved = True
            
        if getattr(self, "is_dragging_target", False) and self.grabbed_target is not None:
            # Update the coordinates of the grabbed target to the mouse position on the globe!
            geo = self.canvas_to_geolocation(event.x, event.y)
            if geo is not None:
                lat, lon = geo
                target = self.grabbed_target
                if target["type"] == "single_target":
                    self.missile_target_lat_var.set(f"{lat:.4f}")
                    self.missile_target_lon_var.set(f"{lon:.4f}")
                    self.refresh_coordinate_labels()
                elif target["type"] == "single_missile_start":
                    self.missile_start_lat_var.set(f"{lat:.4f}")
                    self.missile_start_lon_var.set(f"{lon:.4f}")
                    self.refresh_coordinate_labels()
                elif target["type"] == "single_interceptor_start":
                    self.interceptor_start_lat_var.set(f"{lat:.4f}")
                    self.interceptor_start_lon_var.set(f"{lon:.4f}")
                    self.refresh_coordinate_labels()
                elif target["type"] == "group_target":
                    g_name = target["group_name"]
                    p_idx = target["pair_index"]
                    if g_name in self.missile_groups and p_idx < len(self.missile_groups[g_name]):
                        self.missile_groups[g_name][p_idx]["target_lat"] = float(f"{lat:.4f}")
                        self.missile_groups[g_name][p_idx]["target_lon"] = float(f"{lon:.4f}")
                elif target["type"] == "group_missile":
                    g_name = target["group_name"]
                    p_idx = target["pair_index"]
                    if g_name in self.missile_groups and p_idx < len(self.missile_groups[g_name]):
                        self.missile_groups[g_name][p_idx]["start_lat"] = float(f"{lat:.4f}")
                        self.missile_groups[g_name][p_idx]["start_lon"] = float(f"{lon:.4f}")
                elif target["type"] == "group_interceptor":
                    g_name = target["group_name"]
                    p_idx = target["pair_index"]
                    if g_name in self.interceptor_groups and p_idx < len(self.interceptor_groups[g_name]):
                        self.interceptor_groups[g_name][p_idx]["start_lat"] = float(f"{lat:.4f}")
                        self.interceptor_groups[g_name][p_idx]["start_lon"] = float(f"{lon:.4f}")
            self.drag_last = (event.x, event.y)
            self.schedule_drag_render()
            return
            
        if self.is_dragging_globe:
            yaw_sensitivity, pitch_sensitivity = self.get_drag_sensitivity()
            self.view_yaw_deg += dx * yaw_sensitivity
            self.view_pitch_deg = max(min(self.view_pitch_deg + dy * pitch_sensitivity, 85.0), -85.0)
            self.drag_last = (event.x, event.y)
            self.schedule_drag_render()

    def on_drag_end(self, event):
        if getattr(self, "is_dragging_target", False):
            self.is_dragging_target = False
            self.grabbed_target = None
            self.save_settings()
            self.render_globe()
            
            # Dynamically update the simulation window in real-time if it is open!
            if hasattr(self, "simulation_window") and self.simulation_window is not None:
                try:
                    if self.simulation_window.root.winfo_exists():
                        self.simulation_window.reset_simulation_state()
                except Exception as e:
                    print("Error updating simulation window:", e)
            return
            
        drag_button = self.drag_button
        drag_origin = self.drag_origin
        drag_moved = self.drag_moved
        suppress_left_release_action = self.suppress_left_release_action
        release_x = event.x
        release_y = event.y
        self.drag_last = None
        self.drag_origin = None
        self.drag_button = None
        self.drag_moved = False
        self.suppress_left_release_action = False
        self.is_dragging_globe = False
        if self.drag_render_job is not None:
            self.root.after_cancel(self.drag_render_job)
            self.drag_render_job = None
        if drag_moved:
            self.save_settings()
            self.render_globe()
        if drag_button != 1 or suppress_left_release_action:
            return
        if drag_moved or drag_origin is None or abs(release_x - drag_origin[0]) >= 4 or abs(release_y - drag_origin[1]) >= 4:
            return
        now = time.monotonic()
        last_pos = self.last_left_click_pos
        is_double_click = (
            last_pos is not None
            and now - self.last_left_click_time <= 0.45
            and abs(release_x - last_pos[0]) <= 12
            and abs(release_y - last_pos[1]) <= 12
        )
        if is_double_click:
            self.last_left_click_time = 0.0
            self.last_left_click_pos = None
            self.recenter_globe_at(release_x, release_y)
            return
        self.last_left_click_time = now
        self.last_left_click_pos = (release_x, release_y)
        if self.pick_mode is not None:
            if self.pending_pick_job is not None:
                self.root.after_cancel(self.pending_pick_job)
            self.pending_pick_job = self.root.after(260, lambda: self.on_globe_pick_at(release_x, release_y))

    def recenter_globe_at(self, canvas_x, canvas_y):
        if self.pending_pick_job is not None:
            self.root.after_cancel(self.pending_pick_job)
            self.pending_pick_job = None
        geo = self.canvas_to_geolocation(canvas_x, canvas_y)
        if geo is None:
            self.status_lbl.config(text="Status: Double-click inside the globe outline to recenter.", fg="#ffcc80")
            return
        lat, lon = geo
        self.center_view_on(lat, lon)
        self.save_settings()
        self.status_lbl.config(text=f"Status: Globe centered on Lat {lat:.2f}, Lon {lon:.2f}", fg="#cfd8dc")
        self.render_globe()

    def on_globe_pick_at(self, canvas_x, canvas_y):
        self.pending_pick_job = None
        if self.pick_mode is None:
            return
        geo = self.canvas_to_geolocation(canvas_x, canvas_y)
        if geo is None:
            self.status_lbl.config(text="Status: Click inside the globe outline.", fg="#ffcc80")
            return
        lat, lon = geo
        if self.pick_mode == "group_missile_start":
            self.temp_missile_start = (lat, lon)
            # Temporarily clear pick mode during dialogue popup to prevent click-release event leakage
            self.pick_mode = None
            messagebox.showinfo("Pick Target Center", f"Launch Center set. Now left-click on the globe map to set the Target Center for Group {self.temp_group_name}.", parent=self.root)
            self.root.after(300, lambda: self.set_pick_mode("group_missile_target"))
            return
        elif self.pick_mode == "group_missile_target":
            group_name = self.temp_group_name
            num_msl = self.temp_num_missiles
            start_center = self.temp_missile_start
            target_center = (lat, lon)
            
            pairs = []
            for i in range(1, num_msl + 1):
                if i == 1:
                    m_lat = start_center[0]
                    m_lon = start_center[1]
                    t_lat = target_center[0]
                    t_lon = target_center[1]
                else:
                    m_lat = start_center[0] + random.uniform(-0.15, 0.15)
                    m_lon = start_center[1] + random.uniform(-0.15, 0.15)
                    t_lat = target_center[0] + random.uniform(-0.15, 0.15)
                    t_lon = target_center[1] + random.uniform(-0.15, 0.15)
                pairs.append({
                    "id": i,
                    "start_lat": m_lat,
                    "start_lon": m_lon,
                    "target_lat": t_lat,
                    "target_lon": t_lon
                })
            self.missile_groups[group_name] = pairs
            label = f"Missile Group {group_name} ({num_msl} pairs)"
            self.missile_start_lat_var.set(pairs[0]["start_lat"])
            self.missile_start_lon_var.set(pairs[0]["start_lon"])
            self.missile_target_lat_var.set(pairs[0]["target_lat"])
            self.missile_target_lon_var.set(pairs[0]["target_lon"])
        elif self.pick_mode == "group_interceptor_start":
            group_name = self.temp_group_name
            num_intcp = self.temp_num_missiles  # we stored interceptor count here
            
            pairs = []
            for i in range(1, num_intcp + 1):
                if i == 1:
                    i_lat = lat
                    i_lon = lon
                else:
                    i_lat = lat + random.uniform(-0.15, 0.15)
                    i_lon = lon + random.uniform(-0.15, 0.15)
                pairs.append({
                    "id": i,
                    "start_lat": i_lat,
                    "start_lon": i_lon
                })
            self.interceptor_groups[group_name] = pairs
            label = f"Interceptor Group {group_name} ({num_intcp} launchers)"
            self.interceptor_start_lat_var.set(pairs[0]["start_lat"])
            self.interceptor_start_lon_var.set(pairs[0]["start_lon"])
        elif self.pick_mode == "missile_start":
            self.missile_start_lat_var.set(lat)
            self.missile_start_lon_var.set(lon)
            label = "Missile launch"
        elif self.pick_mode == "missile_target":
            self.missile_target_lat_var.set(lat)
            self.missile_target_lon_var.set(lon)
            label = "Missile target"
        elif self.pick_mode == "interceptor_start":
            self.interceptor_start_lat_var.set(lat)
            self.interceptor_start_lon_var.set(lon)
            label = "Interceptor launch"
        else:
            self.pick_mode = None
            self.status_lbl.config(text="Status: Pick mode cleared.", fg="#cfd8dc")
            self.render_globe()
            return
        self.pick_mode = None
        self.refresh_coordinate_labels()
        self.save_settings()
        self.status_lbl.config(text=f"Status: {label} set successfully.", fg="#cfd8dc")
        self.render_globe()

    def on_globe_pick(self, event):
        self.on_globe_pick_at(event.x, event.y)

    def build_config(self):
        try:
            return SimulationConfig(
                missile_speed=float(self.missile_speed_var.get()) / 1000.0,
                interceptor_speed=float(self.interceptor_speed_var.get()) / 1000.0,
                proportional_gain=float(self.proportional_gain_var.get()),
                auto_launch_interceptor=bool(self.auto_launch_var.get()),
                missile_start_lat=float(self.missile_start_lat_var.get()),
                missile_start_lon=float(self.missile_start_lon_var.get()),
                missile_start_altitude_km=float(self.missile_start_altitude_var.get()),
                missile_target_lat=float(self.missile_target_lat_var.get()),
                missile_target_lon=float(self.missile_target_lon_var.get()),
                missile_target_altitude_km=float(self.missile_target_altitude_var.get()),
                interceptor_start_lat=float(self.interceptor_start_lat_var.get()),
                interceptor_start_lon=float(self.interceptor_start_lon_var.get()),
                interceptor_start_altitude_km=float(self.interceptor_start_altitude_var.get()),
                interceptor_delay_sec=float(self.interceptor_delay_var.get()),
            )
        except (tk.TclError, ValueError):
            messagebox.showerror("Invalid input", "Please enter valid numeric values.")
            return None

    def start_simulation(self):
        if self.simulation_window is not None and not self.simulation_window.closed:
            self.status_lbl.config(text="Status: A simulation window is already open.", fg="#ffcc80")
            return
        config = self.build_config()
        if config is None:
            return
        self.save_settings()
        saved_data = read_settings_data(self.settings_file)
        self.start_btn.config(state="disabled", bg="#78909c")
        self.status_lbl.config(text="Status: Simulation window opened paused. Press Play in the viewer to start.", fg="#80cbc4")
        try:
            # Bind View Center coordinates and Alt/Yaw/Pitch directly from Main GUI setup values
            try:
                main_cam_lat = float(self.view_center_lat_var.get() or self.missile_target_lat_var.get())
                main_cam_lon = float(self.view_center_lon_var.get() or self.missile_target_lon_var.get())
                main_cam_alt = float(self.view_altitude_km_var.get() or 1.0)
            except ValueError:
                main_cam_lat = float(self.missile_target_lat_var.get())
                main_cam_lon = float(self.missile_target_lon_var.get())
                main_cam_alt = 1.0

            from mslsimwindow import SimulationWindow
            self.simulation_window = SimulationWindow(
                self.root,
                config,
                view_state={
                    "yaw": float(saved_data.get("simulation_view_yaw", self.view_yaw_deg)),
                    "pitch": float(saved_data.get("simulation_view_pitch", self.view_pitch_deg)),
                    "altitude_km": main_cam_alt,
                    "zoom": float(saved_data.get("simulation_globe_zoom", self.globe_zoom)),
                    "show_wireframe": bool(saved_data.get("simulation_show_wireframe", self.show_wireframe_var.get())),
                    "show_boundaries": bool(saved_data.get("simulation_show_boundaries", self.show_boundaries_var.get())),
                    "show_map": bool(saved_data.get("simulation_show_map", True)),
                    "show_msl_lbl": bool(saved_data.get("simulation_show_msl_lbl", True)),
                    "edit_sat_orbit": bool(saved_data.get("simulation_edit_sat_orbit", False)),
                    "drag_refresh_ms": self.drag_refresh_ms_var.get(),
                    "show_missile_path": bool(saved_data.get("simulation_show_missile_path", True)),
                    "show_interceptor_path": bool(saved_data.get("simulation_show_interceptor_path", True)),
                    "project_tracks_to_ground": bool(saved_data.get("simulation_project_tracks_to_ground", False)),
                    "msl_tracking": bool(saved_data.get("simulation_msl_tracking", True)),
                    "offline_mode": bool(saved_data.get("offline_mode", self.offline_mode_var.get())),
                    "show_status": bool(saved_data.get("simulation_show_status", True)),
                    "show_height_line": bool(saved_data.get("simulation_show_height_line", True)),
                    "missile_loft_factor": float(saved_data.get("simulation_missile_loft_factor", 0.8)),
                    "missile_hit_radius": float(saved_data.get("simulation_missile_hit_radius", 0.0015)),
                    "interceptor_hit_radius": float(saved_data.get("simulation_interceptor_hit_radius", 0.003)),
                    "loft_vis_ratio": float(saved_data.get("simulation_loft_vis_ratio", 1.0)),
                    "spd_vis_ratio": float(saved_data.get("simulation_spd_vis_ratio", 1.0)),
                    "view_mode": str(saved_data.get("simulation_view_mode", "C")),
                    "view_b_dist_base": float(saved_data.get("simulation_view_b_dist_base", 1.01)),
                    "view_b_focal": float(saved_data.get("simulation_view_b_focal", 1.0)),
                    "view_b_floor": float(saved_data.get("simulation_view_b_floor", 0.08)),
                    "view_c_dist_base": float(saved_data.get("simulation_view_c_dist_base", 1.45)),
                    "view_c_alt_factor": float(saved_data.get("simulation_view_c_alt_factor", 0.9)),
                    "view_c_floor_a": float(saved_data.get("simulation_view_c_floor_a", 0.15)),
                    "view_c_floor_b": float(saved_data.get("simulation_view_c_floor_b", 0.08)),
                    "view_d_alt": float(saved_data.get("simulation_view_d_alt", 800.0)),
                    "view_d_period": float(saved_data.get("simulation_view_d_period", 120.0)),
                    "view_d_focal": float(saved_data.get("simulation_view_d_focal", 2.5)),
                    "sat_geosync": bool(saved_data.get("simulation_sat_geosync", False)),
                    "view_d_inclination": float(saved_data.get("simulation_view_d_inclination", 45.0)),
                    "view_d_phase": float(saved_data.get("simulation_view_d_phase", 0.0)),
                    "view_d_geolat": float(saved_data.get("simulation_view_d_geolat", 0.0)),
                    "view_d_geolon": float(saved_data.get("simulation_view_d_geolon", 130.0)),
                    "camera_lat": main_cam_lat,
                    "camera_lon": main_cam_lon,
                    "camera_altitude_km": main_cam_alt,
                },
                on_close=self._simulation_finished,
                gui_parent=self,
            )
        except Exception as exc:
            self._simulation_failed(exc)

    def _simulation_finished(self):
        self.simulation_window = None
        self.start_btn.config(state="normal", bg="#2ecc71")
        self.status_lbl.config(text="Status: Simulation window closed. You can edit settings and start again.", fg="#cfd8dc")

    def _simulation_failed(self, exc):
        self.simulation_window = None
        self.start_btn.config(state="normal", bg="#2ecc71")
        self.status_lbl.config(text="Status: Simulation failed to start.", fg="#ff8a80")
        messagebox.showerror("Simulation error", str(exc))

    def on_close(self):
        if self.simulation_window is not None:
            try:
                self.simulation_window.on_close()
            except Exception:
                pass
        self.close_globe_picks_window()
        self.save_settings()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    ConfigGui().run()


if __name__ == "__main__":
    main()
