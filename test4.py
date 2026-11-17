#mslsimwindow.py
import math
import os
import time
import tkinter as tk
from tkinter import ttk, messagebox
import json
import re

import cartopy.io.shapereader as cartopy_shapereader
import numpy as np

from msltest2 import EARTH_RADIUS, EARTH_RADIUS_KM, TIME_STEP, Interceptor, SimulationConfig, TargetMissile
from mslwarntest import ConfigGui, EARTH_RADIUS_MILES, GUI_BUILD_TAG, read_settings_data, write_settings_data, read_saved_window_size


class SimulationWindow:
    on_content_configure = ConfigGui.on_content_configure
    update_globe_radius = ConfigGui.update_globe_radius
    get_drag_sensitivity = ConfigGui.get_drag_sensitivity
    on_globe_canvas_resize = ConfigGui.on_globe_canvas_resize
    on_globe_mousewheel = ConfigGui.on_globe_mousewheel
    lat_lon_to_unit = ConfigGui.lat_lon_to_unit
    unit_to_lat_lon = ConfigGui.unit_to_lat_lon
    get_center_geolocation = ConfigGui.get_center_geolocation
    update_view_center_display = ConfigGui.update_view_center_display
    canvas_to_geolocation = ConfigGui.canvas_to_geolocation
    event_to_geolocation = ConfigGui.event_to_geolocation
    center_view_on = ConfigGui.center_view_on
    set_pick_mode = ConfigGui.set_pick_mode
    apply_view_center_from_fields = ConfigGui.apply_view_center_from_fields
    apply_view_angle_from_fields = ConfigGui.apply_view_angle_from_fields
    apply_view_rotation = ConfigGui.apply_view_rotation
    inverse_view_rotation = ConfigGui.inverse_view_rotation
    project_to_canvas = ConfigGui.project_to_canvas
    draw_wireframe = ConfigGui.draw_wireframe
    draw_globe_guides = ConfigGui.draw_globe_guides
    load_shapefile_segments = ConfigGui.load_shapefile_segments
    load_country_labels = ConfigGui.load_country_labels
    load_city_labels = ConfigGui.load_city_labels
    draw_filled_band = ConfigGui.draw_filled_band
    draw_map_globe = ConfigGui.draw_map_globe
    draw_text_with_outline = ConfigGui.draw_text_with_outline
    draw_marker_shape = ConfigGui.draw_marker_shape
    draw_geographic_labels = ConfigGui.draw_geographic_labels
    draw_label_set = ConfigGui.draw_label_set
    draw_marker = ConfigGui.draw_marker
    draw_pole_marker = ConfigGui.draw_pole_marker
    choose_scale_miles = ConfigGui.choose_scale_miles
    draw_scale_bar = ConfigGui.draw_scale_bar
    draw_viewpoint_marker = ConfigGui.draw_viewpoint_marker
    on_drag_start = ConfigGui.on_drag_start
    schedule_drag_render = ConfigGui.schedule_drag_render
    perform_drag_render = ConfigGui.perform_drag_render
    on_drag_end = ConfigGui.on_drag_end
    recenter_globe_at = ConfigGui.recenter_globe_at
    on_globe_pick_at = ConfigGui.on_globe_pick_at
    on_globe_pick = ConfigGui.on_globe_pick

    def on_canvas_configure(self, event):
        self.scroll_canvas.itemconfigure(self.content_window, width=event.width)
        available_width = max(event.width - 40, 1)
        available_height = max(event.height - 180, 1)
        target_size = min(available_width, available_height)
        if target_size != self.globe_canvas_width or target_size != self.globe_canvas_height:
            self.globe_canvas_width = target_size
            self.globe_canvas_height = target_size
            self.update_globe_radius()
            self.globe_canvas.config(width=self.globe_canvas_width, height=self.globe_canvas_height)
            self.render_globe()

    def on_canavs_configure(self, event):
        self.on_canvas_configure(event)

    def __getattr__(self, name):
        if name in {"on_canavs_configure", "on_canavs_configiure", "on_canvas_configiure", "_on_canvas_configure", "_on_canavs_configiure", "_on_canvas_configiure"}:
            return self.on_canvas_configure
        config_gui_method = getattr(ConfigGui, name, None)
        if callable(config_gui_method):
            return config_gui_method.__get__(self, type(self))
        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

    def get_perspective_limb_radius(self):
        if hasattr(self, "render_limb_radius"):
            return self.render_limb_radius
        return self.globe_radius_px

    def clip_canvas_segment_to_globe(self, x1, y1, x2, y2):
        cx = self.globe_canvas_width / 2
        cy = self.globe_canvas_height / 2
        limb_radius = self.get_perspective_limb_radius()
        radius = max(limb_radius - 1.0, 1.0)
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
    def project_to_canvas(self, point):
        cx = self.globe_canvas_width / 2
        cy = self.globe_canvas_height / 2
        
        # If Ground View, use a genuine 3D perspective camera matrix projection (gluLookAt equivalent)
        if getattr(self, "render_is_ground", False):
            eye = getattr(self, "cam_eye", None)
            center = getattr(self, "cam_center", None)
            up = getattr(self, "cam_up", None)
            
            if eye is not None and center is not None and up is not None:
                # Construct standard OpenGL view coordinate system (basis vectors)
                z_axis = eye - center
                z_axis_norm = np.linalg.norm(z_axis)
                if z_axis_norm > 1e-9:
                    z_axis = z_axis / z_axis_norm
                else:
                    z_axis = np.array([0.0, 0.0, 1.0])
                    
                x_axis = np.cross(up, z_axis)
                x_axis_norm = np.linalg.norm(x_axis)
                if x_axis_norm > 1e-9:
                    x_axis = x_axis / x_axis_norm
                else:
                    x_axis = np.array([1.0, 0.0, 0.0])
                    
                y_axis = np.cross(z_axis, x_axis)
                y_axis_norm = np.linalg.norm(y_axis)
                if y_axis_norm > 1e-9:
                    y_axis = y_axis / y_axis_norm
                else:
                    y_axis = np.array([0.0, 1.0, 0.0])
                
                # Transform point into camera coordinates
                p_cam = np.asarray(point, dtype=float) - eye
                x_c = np.dot(p_cam, x_axis)
                y_c = np.dot(p_cam, y_axis)
                z_c = np.dot(p_cam, z_axis)
                
                dist = -z_c  # Distance along the look direction
                if dist <= 0.001:
                    # Point is behind the camera, return negative Z depth to clip/hide it
                    return np.array([0.0, 0.0, -1.0]), -9999.0, -9999.0
                    
                # Perspective projection division
                x_proj = x_c / dist
                y_proj = y_c / dist
                
                # Scale and center on canvas (adjust zoom factor dynamically)
                zoom_scale = max(self.globe_zoom, 0.5) * 1.5
                x = cx + x_proj * self.globe_radius_px * zoom_scale
                y = cy - y_proj * self.globe_radius_px * zoom_scale
                
                # Return depth (dist) as positive Z view coordinate
                return np.array([x_proj, y_proj, dist]), x, y

        # Otherwise, fall back to orbit space view orthographic projection
        view = self.apply_view_rotation(point)
        x = cx + view[0] * self.globe_radius_px
        y = cy - view[1] * self.globe_radius_px
        return view, x, y

    def on_drag_move(self, event):
        if self.drag_last is None:
            return
        dx = event.x - self.drag_last[0]
        dy = event.y - self.drag_last[1]
        if abs(dx) >= 1 or abs(dy) >= 1:
            self.drag_moved = True
            
        yaw_sensitivity, pitch_sensitivity = self.get_drag_sensitivity()
        
        mode = self.view_mode_var.get()
        if mode == "D":
            # For Mode D, drag adjusts the steerable camera offsets on the satellite!
            self.sat_view_yaw_offset += dx * yaw_sensitivity
            self.sat_view_pitch_offset = max(min(self.sat_view_pitch_offset + dy * pitch_sensitivity, 85.0), -85.0)
        else:
            self.view_yaw_deg += dx * yaw_sensitivity
            self.view_pitch_deg = max(min(self.view_pitch_deg + dy * pitch_sensitivity, 85.0), -85.0)
            
        self.drag_last = (event.x, event.y)
        self.schedule_drag_render()

    def draw_clipped_line(self, pt1, pt2, color, width=1, dash=None):
        camera_distance = self.get_view_camera_distance()
        is_ground = getattr(self, "render_is_ground", False)
        
        if not is_ground:
            view1, x1, y1 = self.project_to_canvas(pt1)
            view2, x2, y2 = self.project_to_canvas(pt2)
            if self.is_occluded_by_earth(view1, camera_distance) or self.is_occluded_by_earth(view2, camera_distance):
                return
            clipped = self.clip_canvas_segment_to_globe(x1, y1, x2, y2)
            if clipped is not None:
                self.globe_canvas.create_line(*clipped, fill=color, width=width, dash=dash)
            return

        # Ground View or Mode D perspective projection: 3D Homogeneous near-plane line clipping
        cx = self.globe_canvas_width / 2
        cy = self.globe_canvas_height / 2
        
        eye = getattr(self, "cam_eye", None)
        center = getattr(self, "cam_center", None)
        up = getattr(self, "cam_up", None)
        
        if eye is None or center is None or up is None:
            return
            
        z_axis = eye - center
        z_axis_norm = np.linalg.norm(z_axis)
        if z_axis_norm > 1e-9: z_axis /= z_axis_norm
        else: z_axis = np.array([0.0, 0.0, 1.0])
            
        x_axis = np.cross(up, z_axis)
        x_axis_norm = np.linalg.norm(x_axis)
        if x_axis_norm > 1e-9: x_axis /= x_axis_norm
        else: x_axis = np.array([1.0, 0.0, 0.0])
            
        y_axis = np.cross(z_axis, x_axis)
        y_axis_norm = np.linalg.norm(y_axis)
        if y_axis_norm > 1e-9: y_axis /= y_axis_norm
        else: y_axis = np.array([0.0, 1.0, 0.0])
            
        near = 0.01
        zoom_scale = max(self.globe_zoom, 0.5) * 1.5
        
        def project_cam_point(p_cam):
            x_c = np.dot(p_cam, x_axis)
            y_c = np.dot(p_cam, y_axis)
            z_c = np.dot(p_cam, z_axis)
            dist = -z_c
            x_proj = x_c / dist
            y_proj = y_c / dist
            x_screen = cx + x_proj * self.globe_radius_px * zoom_scale
            y_screen = cy - y_proj * self.globe_radius_px * zoom_scale
            return x_screen, y_screen

        p1_cam = np.asarray(pt1, dtype=float) - eye
        p2_cam = np.asarray(pt2, dtype=float) - eye
        
        d1 = -np.dot(p1_cam, z_axis)
        d2 = -np.dot(p2_cam, z_axis)
        
        if d1 >= near and d2 >= near:
            x1, y1 = project_cam_point(p1_cam)
            x2, y2 = project_cam_point(p2_cam)
            self.globe_canvas.create_line(x1, y1, x2, y2, fill=color, width=width, dash=dash)
        elif d1 < near and d2 < near:
            return
        else:
            t = (near - d1) / (d2 - d1)
            p_clip_cam = p1_cam + t * (p2_cam - p1_cam)
            if d1 >= near:
                x1, y1 = project_cam_point(p1_cam)
                x2, y2 = project_cam_point(p_clip_cam)
            else:
                x1, y1 = project_cam_point(p_clip_cam)
                x2, y2 = project_cam_point(p2_cam)
            self.globe_canvas.create_line(x1, y1, x2, y2, fill=color, width=width, dash=dash)

    def draw_polyline_segments(self, points, color, width=1, dash=None):
        for pt1, pt2 in zip(points, points[1:]):
            self.draw_clipped_line(pt1, pt2, color, width, dash)

    def draw_marker(self, lat, lon, altitude_km, color, label, always_show_label=False, label_anchor="w", label_offset=None, shape="circle", halo_color="#081018", halo_radius=2):
        point_surf = self.lat_lon_to_unit(lat, lon)
        view_surf, x_surf, y_surf = self.project_to_canvas(point_surf)
        min_depth = getattr(self, "render_min_depth", -0.05)
        if view_surf[2] < min_depth:
            return
        ConfigGui.draw_marker(self, lat, lon, altitude_km, color, label, always_show_label, label_anchor, label_offset, shape, halo_color, halo_radius)

    def draw_pole_marker(self, lat, color, label):
        point = self.lat_lon_to_unit(lat, 0.0)
        view, x, y = self.project_to_canvas(point)
        min_depth = getattr(self, "render_min_depth", -0.05)
        if view[2] < min_depth:
            return
        ConfigGui.draw_pole_marker(self, lat, color, label)

    def get_view_camera_distance(self):
        altitude_units = self.get_view_altitude_km() / EARTH_RADIUS_KM
        mode = self.view_mode_var.get()
        if mode == "B":
            try:
                base = float(self.view_b_dist_base_var.get())
            except ValueError:
                base = 1.01
            return base + altitude_units
        if mode == "C":
            try:
                base = float(self.view_c_dist_base_var.get())
                factor = float(self.view_c_alt_factor_var.get())
            except ValueError:
                base = 1.45
                factor = 0.9
            return base + altitude_units * factor
        return 2.25 + altitude_units

    def __init__(self, parent, config, view_state, on_close, gui_parent=None):
        self.root = tk.Toplevel(parent)
        self.gui_parent = gui_parent
        self.root.title(f"Simulation Viewer [{GUI_BUILD_TAG}]")
        self.root.geometry("980x860")
        self.root.configure(bg="#1e1e24")
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
        self.on_close_callback = on_close
        self.config = config
        self.pick_mode = None
        self.default_view_yaw_deg = float(view_state["yaw"])
        self.default_view_pitch_deg = float(view_state["pitch"])
        self.view_yaw_deg = float(view_state["yaw"])
        self.view_pitch_deg = float(view_state["pitch"])
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
        self.simulation_control_window = None
        self.globe_vector_cache = {}
        self.globe_canvas_width = 720
        self.globe_canvas_height = 720
        self.globe_zoom = float(view_state["zoom"])
        self.globe_radius_px = 320
        self.show_wireframe_var = tk.BooleanVar(value=bool(view_state["show_wireframe"]))
        self.show_boundaries_var = tk.BooleanVar(value=bool(view_state["show_boundaries"]))
        self.show_map_var = tk.BooleanVar(value=bool(view_state.get("show_map", True)))
        self.show_msl_lbl_var = tk.BooleanVar(value=bool(view_state.get("show_msl_lbl", True)))
        self.offline_mode_var = tk.BooleanVar(value=bool(view_state.get("offline_mode", False)))
        self.edit_sat_orbit_var = tk.BooleanVar(value=bool(view_state.get("edit_sat_orbit", False)))
        self.show_texture_var = tk.BooleanVar(value=bool(view_state.get("show_texture", False)))
        self.show_missile_path_var = tk.BooleanVar(value=bool(view_state.get("show_missile_path", True)))
        self.show_interceptor_path_var = tk.BooleanVar(value=bool(view_state.get("show_interceptor_path", True)))
        self.project_tracks_to_ground_var = tk.BooleanVar(value=bool(view_state.get("project_tracks_to_ground", False)))
        self.msl_tracking_var = tk.BooleanVar(value=bool(view_state.get("msl_tracking", True)))
        self.show_status_var = tk.BooleanVar(value=bool(view_state.get("show_status", True)))
        self.show_height_line_var = tk.BooleanVar(value=bool(view_state.get("show_height_line", True)))
        self.show_local_horizon_var = tk.BooleanVar(value=bool(view_state.get("show_local_horizon", False)))
        self.missile_loft_factor_var = tk.StringVar(value=f"{float(view_state.get('missile_loft_factor', 0.8)):.2f}")
        self.missile_hit_radius_var = tk.StringVar(value=f"{float(view_state.get('missile_hit_radius', 0.0015)):.4f}")
        self.interceptor_hit_radius_var = tk.StringVar(value=f"{float(view_state.get('interceptor_hit_radius', 0.003)):.4f}")
        self.loft_vis_ratio_var = tk.StringVar(value=f"{float(view_state.get('loft_vis_ratio', 1.0)):.1f}")
        self.spd_vis_ratio_var = tk.StringVar(value=f"{float(view_state.get('spd_vis_ratio', 1.0)):.1f}")
        self.view_mode_var = tk.StringVar(value=str(view_state.get("view_mode", "A")))
        self.view_b_dist_base_var = tk.StringVar(value=f"{float(view_state.get('view_b_dist_base', 1.01)):.3f}")
        self.view_b_focal_var = tk.StringVar(value=f"{float(view_state.get('view_b_focal', 1.0)):.2f}")
        self.view_b_floor_var = tk.StringVar(value=f"{float(view_state.get('view_b_floor', 0.08)):.3f}")
        self.view_c_dist_base_var = tk.StringVar(value=f"{float(view_state.get('view_c_dist_base', 1.45)):.3f}")
        self.view_c_alt_factor_var = tk.StringVar(value=f"{float(view_state.get('view_c_alt_factor', 0.9)):.2f}")
        self.view_c_floor_a_var = tk.StringVar(value=f"{float(view_state.get('view_c_floor_a', 0.15)):.3f}")
        self.view_c_floor_b_var = tk.StringVar(value=f"{float(view_state.get('view_c_floor_b', 0.08)):.3f}")
        self.view_d_alt_var = tk.StringVar(value=f"{float(view_state.get('view_d_alt', 800.0)):.1f}")
        self.view_d_period_var = tk.StringVar(value=f"{float(view_state.get('view_d_period', 120.0)):.1f}")
        self.view_d_focal_var = tk.StringVar(value=f"{float(view_state.get('view_d_focal', 2.5)):.2f}")
        self.sat_geosync_var = tk.BooleanVar(value=bool(view_state.get("sat_geosync", False)))
        self.view_d_inclination_var = tk.StringVar(value=f"{float(view_state.get('view_d_inclination', 45.0)):.1f}")
        self.view_d_phase_var = tk.StringVar(value=f"{float(view_state.get('view_d_phase', 0.0)):.1f}")
        self.view_d_geolat_var = tk.StringVar(value=f"{float(view_state.get('view_d_geolat', 0.0)):.2f}")
        self.view_d_geolon_var = tk.StringVar(value=f"{float(view_state.get('view_d_geolon', 130.0)):.2f}")
        self.drag_refresh_ms_var = tk.DoubleVar(value=float(view_state["drag_refresh_ms"]))
        self.view_center_lat_var = tk.StringVar(value=f"{float(view_state.get('camera_lat', 0.0)):.2f}")
        self.view_center_lon_var = tk.StringVar(value=f"{float(view_state.get('camera_lon', 0.0)):.2f}")
        self.view_yaw_var = tk.StringVar(value=f"{self.view_yaw_deg:.2f}")
        self.view_pitch_var = tk.StringVar(value=f"{self.view_pitch_deg:.2f}")
        self.view_altitude_km_var = tk.StringVar(value=str(float(view_state.get("altitude_km", 0.0))))
        self.camera_lat_var = tk.StringVar(value=f"{float(view_state.get('camera_lat', 0.0)):.2f}")
        self.camera_lon_var = tk.StringVar(value=f"{float(view_state.get('camera_lon', 0.0)):.2f}")
        self.camera_altitude_km_var = tk.StringVar(value=str(float(view_state.get("camera_altitude_km", 1.0))))
        # Locate settings_file next to the executable if compiled, otherwise next to this script file
        import sys
        if getattr(sys, 'frozen', False):
            self.settings_file = os.path.join(os.path.dirname(sys.executable), "mslwarntest_settings.json")
        else:
            self.settings_file = os.path.join(os.path.dirname(__file__), "mslwarntest_settings.json")
        self.coastline_segments_drag = self.load_shapefile_segments(os.path.join(os.path.dirname(os.path.dirname(__file__)), "ne_10m_coastline.shp"), point_step=32)
        self.coastline_segments_full = self.load_shapefile_segments(os.path.join(os.path.dirname(os.path.dirname(__file__)), "ne_10m_coastline.shp"), point_step=8)
        self.land_segments_drag = []
        self.land_segments_full = self.load_shapefile_segments(cartopy_shapereader.natural_earth(resolution="50m", category="physical", name="land"), point_step=6)
        self.ocean_segments_drag = []
        self.ocean_segments_full = self.load_shapefile_segments(cartopy_shapereader.natural_earth(resolution="50m", category="physical", name="ocean"), point_step=6)
        self.boundary_segments_drag = self.load_shapefile_segments(cartopy_shapereader.natural_earth(resolution="50m", category="cultural", name="admin_0_boundary_lines_land"), point_step=12)
        self.boundary_segments_full = self.load_shapefile_segments(cartopy_shapereader.natural_earth(resolution="50m", category="cultural", name="admin_0_boundary_lines_land"), point_step=8)
        self.country_labels = self.load_country_labels(cartopy_shapereader.natural_earth(resolution="50m", category="cultural", name="admin_0_countries"))
        self.city_labels = []
        self.after_job = None
        self.closed = False
        self.is_paused = False
        self.simulation_finished = False
        self.status_text = "Simulation paused. Press Play below the globe to start. Drag rotates, double-click centers, wheel zooms."
        self.status_color = "#80cbc4"
        self.ground_camera_fields_visible = False
        self.recording_state = "inactive" # "inactive", "armed", "recording"
        self.recording_area = "canvas"     # "canvas", "window", "screen"
        self.video_writer = None
        self.recording_filepath = None
        
        self.winrec_state = "inactive"     # "inactive", "recording"
        self.winrec_writer = None
        self.winrec_bbox = None
        self.winrec_width = 0
        self.winrec_height = 0
        self.winrec_filepath = None
        self.sat_view_yaw_offset = 0.0
        self.sat_view_pitch_offset = 0.0
        self.impact_window = None
        self.sat_live_view_window = None
        import queue
        self.sat_live_view_queue = queue.Queue(maxsize=1)
        self.updatemap_process = None
        self.plotter3d_process = None
        self.offscreen_plotter = None
        self.globe_bg_image = None
        self.restore_window_size()
        self.reset_simulation_state()
        self.update_globe_radius()
        self.build_ui()
        self.refresh_control_states()
        self.render_globe()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.bind("<space>", self.on_launch_key)
        self.is_paused = True
        self.refresh_control_states()

    def build_ui(self):
        tk.Label(self.content_frame, text="MISSILE INTERCEPT SIMULATION", font=("Segoe UI", 12, "bold"), fg="#ffffff", bg="#1e1e24").pack(pady=(14, 8))
        self.status_lbl = tk.Label(self.content_frame, text=self.status_text, font=("Segoe UI", 9), fg=self.status_color, bg="#1e1e24")
        self.status_lbl.pack(pady=(0, 8))
        self.globe_canvas = tk.Canvas(self.content_frame, width=self.globe_canvas_width, height=self.globe_canvas_height, bg="#000000", highlightthickness=1, highlightbackground="#444444")
        self.globe_canvas.pack(fill="both", expand=True, padx=20, pady=(0, 8), ipadx=20, ipady=20)
        self.globe_canvas.bind("<ButtonPress-1>", self.on_drag_start)
        self.globe_canvas.bind("<B1-Motion>", self.on_drag_move)
        self.globe_canvas.bind("<ButtonRelease-1>", self.on_drag_end)
        self.globe_canvas.bind("<Double-Button-1>", self.on_globe_double_click)
        self.globe_canvas.bind("<ButtonPress-3>", self.on_drag_start)
        self.globe_canvas.bind("<B3-Motion>", self.on_drag_move)
        self.globe_canvas.bind("<ButtonRelease-3>", self.on_drag_end)
        self.globe_canvas.bind("<MouseWheel>", self.on_globe_mousewheel)
        self.globe_canvas.bind("<Button-4>", self.on_globe_mousewheel)
        self.globe_canvas.bind("<Button-5>", self.on_globe_mousewheel)
        self.globe_canvas.bind("<Configure>", self.on_globe_canvas_resize)
        help_row = tk.Frame(self.content_frame, bg="#1e1e24")
        help_row.pack(fill="x", padx=20, pady=(0, 2))
        tk.Label(help_row, text="Simulation globe: drag rotates, double-click centers, wheel zooms.", font=("Segoe UI", 8), fg="#9fb3bf", bg="#1e1e24", anchor="w", justify="left").pack(side="left", fill="x", expand=True)
        toggle_row = tk.Frame(self.content_frame, bg="#1e1e24")
        toggle_row.pack(fill="x", padx=20, pady=(0, 6))
        tk.Checkbutton(toggle_row, text="Wireframe", variable=self.show_wireframe_var, command=self.render_globe, fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24").pack(side="left")
        tk.Checkbutton(toggle_row, text="Boundaries", variable=self.show_boundaries_var, command=self.render_globe, fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24").pack(side="left", padx=(16, 0))
        tk.Checkbutton(toggle_row, text="Globe map", variable=self.show_map_var, command=self.on_show_map_toggle, fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24").pack(side="left", padx=(16, 0))
        tk.Checkbutton(toggle_row, text="Msl tracking", variable=self.msl_tracking_var, command=self.render_globe, fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24").pack(side="left", padx=(16, 0))
        tk.Checkbutton(toggle_row, text="Show status", variable=self.show_status_var, command=self.render_globe, fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24").pack(side="left", padx=(16, 0))
        tk.Checkbutton(toggle_row, text="Tex", variable=self.show_texture_var, command=self.on_show_texture_toggle, fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24").pack(side="left", padx=(16, 0))
        tk.Button(toggle_row, text="Simcon", command=self.open_simulation_control_window, bg="#5e35b1", fg="white", bd=0, width=12).pack(side="right", padx=(8, 0))
        self.launch_btn = tk.Button(toggle_row, text="Launch-Int", command=self.launch_interceptor, bg="#ff8f1f", activebackground="#ff9f43", fg="white", activeforeground="white", bd=0, width=12)
        self.launch_btn.pack(side="right")
        playback_row = tk.Frame(self.content_frame, bg="#1e1e24")
        playback_row.pack(fill="x", padx=20, pady=(0, 6))
        self.pause_btn = tk.Button(playback_row, text="Pause", command=self.toggle_pause, bg="#607d8b", fg="white", bd=0, width=10)
        self.pause_btn.pack(side="left")
        self.replay_btn = tk.Button(playback_row, text="Replay", command=self.restart_simulation, bg="#8e44ad", fg="white", bd=0, width=10)
        self.replay_btn.pack(side="left", padx=(12, 0))
        self.record_btn = tk.Button(playback_row, text="Record", command=self.toggle_recording_ui, bg="#b0bec5", fg="black", bd=0, width=10)
        self.record_btn.pack(side="left", padx=(12, 0))
        self.winrec_btn = tk.Button(playback_row, text="WinRec", command=self.toggle_winrec_ui, bg="#90a4ae", fg="black", bd=0, width=10)
        self.winrec_btn.pack(side="left", padx=(12, 0))
        self.miw_btn = tk.Button(playback_row, text="MIW", command=self.open_miw_window, bg="#e74c3c", fg="white", bd=0, width=8)
        self.miw_btn.pack(side="left", padx=(12, 0))
        self.sat_live_btn = tk.Button(playback_row, text="Sat Live View", command=self.open_sat_live_view_window, bg="#ffd700", fg="black", bd=0, width=12, font=("Segoe UI", 9, "bold"))
        self.sat_live_btn.pack(side="left", padx=(12, 0))

    def open_simulation_control_window(self):
        if self.simulation_control_window is not None and self.simulation_control_window.winfo_exists():
            self.simulation_control_window.deiconify()
            self.simulation_control_window.lift()
            self.simulation_control_window.focus_force()
            self.refresh_control_states()
            return
        self.simulation_control_window = tk.Toplevel(self.root)
        self.simulation_control_window.title("Simulation Control")
        self.simulation_control_window.geometry("540x510")
        self.simulation_control_window.configure(bg="#1e1e24")
        self.simulation_control_window.protocol("WM_DELETE_WINDOW", self.close_simulation_control_window)

        path_row = tk.Frame(self.simulation_control_window, bg="#1e1e24")
        path_row.pack(fill="x", padx=20, pady=(16, 2))
        tk.Checkbutton(path_row, text="Msl path", variable=self.show_missile_path_var, command=lambda: (self.save_settings(), self.render_globe()), fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24").pack(side="left")
        tk.Checkbutton(path_row, text="Intcp path", variable=self.show_interceptor_path_var, command=lambda: (self.save_settings(), self.render_globe()), fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24").pack(side="left", padx=(16, 0))
        tk.Checkbutton(path_row, text="Project to ground", variable=self.project_tracks_to_ground_var, command=lambda: (self.save_settings(), self.render_globe()), fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24").pack(side="left", padx=(16, 0))
        tk.Checkbutton(path_row, text="Msl tracking", variable=self.msl_tracking_var, command=lambda: (self.save_settings(), self.render_globe()), fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24").pack(side="left", padx=(16, 0))

        path_row2 = tk.Frame(self.simulation_control_window, bg="#1e1e24")
        path_row2.pack(fill="x", padx=20, pady=(2, 6))
        tk.Checkbutton(path_row2, text="Ht line", variable=self.show_height_line_var, command=lambda: (self.save_settings(), self.render_globe()), fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24").pack(side="left")
        tk.Checkbutton(path_row2, text="Show status", variable=self.show_status_var, command=lambda: (self.save_settings(), self.render_globe()), fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24").pack(side="left", padx=(16, 0))
        tk.Checkbutton(path_row2, text="Local horizon", variable=self.show_local_horizon_var, command=lambda: (self.save_settings(), self.render_globe()), fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24").pack(side="left", padx=(16, 0))
        tk.Checkbutton(path_row2, text="Live map", variable=self.show_map_var, command=self.on_show_map_toggle, fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24").pack(side="left", padx=(16, 0))
        tk.Checkbutton(path_row2, text="Msl lbl", variable=self.show_msl_lbl_var, command=self.on_show_msl_lbl_toggle, fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24").pack(side="left", padx=(16, 0))

        mode_row = tk.Frame(self.simulation_control_window, bg="#1e1e24")
        mode_row.pack(fill="x", padx=20, pady=(0, 6))
        tk.Label(mode_row, text="View mode", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 10))
        tk.Radiobutton(mode_row, text="A", value="A", variable=self.view_mode_var, command=lambda: (self.save_settings(), self.render_globe()), fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24").pack(side="left")
        tk.Radiobutton(mode_row, text="B", value="B", variable=self.view_mode_var, command=lambda: (self.save_settings(), self.render_globe()), fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24").pack(side="left", padx=(10, 0))
        tk.Radiobutton(mode_row, text="C", value="C", variable=self.view_mode_var, command=lambda: (self.save_settings(), self.render_globe()), fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24").pack(side="left", padx=(10, 0))
        tk.Radiobutton(mode_row, text="D", value="D", variable=self.view_mode_var, command=lambda: (self.save_settings(), self.render_globe()), fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24").pack(side="left", padx=(10, 0))
        tk.Label(mode_row, text="A ext | B sat | C hybrid | D sat-mount", fg="#9fb3bf", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(14, 0))

        center_row = tk.Frame(self.simulation_control_window, bg="#1e1e24")
        center_row.pack(fill="x", padx=20, pady=(0, 10))
        tk.Label(center_row, text="Sim view center", width=16, anchor="w", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9)).pack(side="left")
        tk.Label(center_row, text="Lat", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 4))
        self.view_center_lat_entry = tk.Entry(center_row, textvariable=self.view_center_lat_var, width=9, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.view_center_lat_entry.pack(side="left", padx=(0, 8))
        tk.Label(center_row, text="Lon", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 4))
        self.view_center_lon_entry = tk.Entry(center_row, textvariable=self.view_center_lon_var, width=9, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.view_center_lon_entry.pack(side="left", padx=(0, 8))
        tk.Label(center_row, text="Alt km", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 4))
        self.view_altitude_entry = tk.Entry(center_row, textvariable=self.view_altitude_km_var, width=9, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.view_altitude_entry.pack(side="left", padx=(0, 8))
        tk.Button(center_row, text="Apply", command=self.apply_view_center_from_fields, bg="#3b6ea8", fg="white", bd=0, padx=10).pack(side="left")
        self.view_center_lat_entry.bind("<Return>", self.apply_view_center_from_fields)
        self.view_center_lon_entry.bind("<Return>", self.apply_view_center_from_fields)
        self.view_altitude_entry.bind("<Return>", self.apply_view_center_from_fields)

        angle_row = tk.Frame(self.simulation_control_window, bg="#1e1e24")
        angle_row.pack(fill="x", padx=20, pady=(0, 12))
        tk.Label(angle_row, text="Sim view angle", width=16, anchor="w", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9)).pack(side="left")
        tk.Label(angle_row, text="Yaw", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 4))
        self.view_yaw_entry = tk.Entry(angle_row, textvariable=self.view_yaw_var, width=9, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.view_yaw_entry.pack(side="left", padx=(0, 8))
        tk.Label(angle_row, text="Pitch", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 4))
        self.view_pitch_entry = tk.Entry(angle_row, textvariable=self.view_pitch_var, width=9, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.view_pitch_entry.pack(side="left", padx=(0, 8))
        tk.Button(angle_row, text="Apply", command=self.apply_view_angle_from_fields, bg="#3b6ea8", fg="white", bd=0, padx=10).pack(side="left")
        self.view_yaw_entry.bind("<Return>", self.apply_view_angle_from_fields)
        self.view_pitch_entry.bind("<Return>", self.apply_view_angle_from_fields)

        physics_row = tk.Frame(self.simulation_control_window, bg="#1e1e24")
        physics_row.pack(fill="x", padx=20, pady=(0, 12))
        tk.Label(physics_row, text="Physics params", width=16, anchor="w", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9)).pack(side="left")
        tk.Label(physics_row, text="Loft", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 2))
        self.loft_factor_entry = tk.Entry(physics_row, textvariable=self.missile_loft_factor_var, width=5, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.loft_factor_entry.pack(side="left", padx=(0, 6))
        tk.Label(physics_row, text="Msl rad", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 2))
        self.missile_hit_radius_entry = tk.Entry(physics_row, textvariable=self.missile_hit_radius_var, width=6, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.missile_hit_radius_entry.pack(side="left", padx=(0, 6))
        tk.Label(physics_row, text="Int rad", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 2))
        self.interceptor_hit_radius_entry = tk.Entry(physics_row, textvariable=self.interceptor_hit_radius_var, width=6, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.interceptor_hit_radius_entry.pack(side="left", padx=(0, 6))

        physics_row2 = tk.Frame(self.simulation_control_window, bg="#1e1e24")
        physics_row2.pack(fill="x", padx=20, pady=(0, 12))
        tk.Label(physics_row2, text="Visualization", width=16, anchor="w", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9)).pack(side="left")
        tk.Label(physics_row2, text="Loft vis", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 2))
        self.loft_vis_ratio_entry = tk.Entry(physics_row2, textvariable=self.loft_vis_ratio_var, width=5, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.loft_vis_ratio_entry.pack(side="left", padx=(0, 6))
        tk.Label(physics_row2, text="Spd vis", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 2))
        self.spd_vis_ratio_entry = tk.Entry(physics_row2, textvariable=self.spd_vis_ratio_var, width=5, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.spd_vis_ratio_entry.pack(side="left", padx=(0, 6))

        # Bind FocusOut and Return to auto-save and auto-render on manual entries
        for entry in [self.loft_factor_entry, self.missile_hit_radius_entry, self.interceptor_hit_radius_entry, self.loft_vis_ratio_entry, self.spd_vis_ratio_entry]:
            entry.bind("<Return>", lambda e: (self.save_settings(), self.render_globe()))
            entry.bind("<FocusOut>", lambda e: (self.save_settings(), self.render_globe()))

        view_b_row = tk.Frame(self.simulation_control_window, bg="#1e1e24")
        view_b_row.pack(fill="x", padx=20, pady=(0, 12))
        tk.Label(view_b_row, text="View B", width=16, anchor="w", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Label(view_b_row, text="Dist base", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 2))
        self.view_b_dist_base_entry = tk.Entry(view_b_row, textvariable=self.view_b_dist_base_var, width=6, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.view_b_dist_base_entry.pack(side="left", padx=(0, 6))
        tk.Label(view_b_row, text="Focal scale", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 2))
        self.view_b_focal_entry = tk.Entry(view_b_row, textvariable=self.view_b_focal_var, width=6, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.view_b_focal_entry.pack(side="left", padx=(0, 6))
        tk.Label(view_b_row, text="Floor", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 2))
        self.view_b_floor_entry = tk.Entry(view_b_row, textvariable=self.view_b_floor_var, width=6, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.view_b_floor_entry.pack(side="left", padx=(0, 6))

        view_c_row = tk.Frame(self.simulation_control_window, bg="#1e1e24")
        view_c_row.pack(fill="x", padx=20, pady=(0, 12))
        tk.Label(view_c_row, text="View C", width=16, anchor="w", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Label(view_c_row, text="Dist base", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 2))
        self.view_c_dist_base_entry = tk.Entry(view_c_row, textvariable=self.view_c_dist_base_var, width=6, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.view_c_dist_base_entry.pack(side="left", padx=(0, 6))
        tk.Label(view_c_row, text="Alt factor", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 2))
        self.view_c_alt_factor_entry = tk.Entry(view_c_row, textvariable=self.view_c_alt_factor_var, width=6, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.view_c_alt_factor_entry.pack(side="left", padx=(0, 6))
        tk.Label(view_c_row, text="Floor A", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 2))
        self.view_c_floor_a_entry = tk.Entry(view_c_row, textvariable=self.view_c_floor_a_var, width=6, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.view_c_floor_a_entry.pack(side="left", padx=(0, 6))
        tk.Label(view_c_row, text="Floor B", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 2))
        self.view_c_floor_b_entry = tk.Entry(view_c_row, textvariable=self.view_c_floor_b_var, width=6, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.view_c_floor_b_entry.pack(side="left", padx=(0, 6))

        view_d_row = tk.Frame(self.simulation_control_window, bg="#1e1e24")
        view_d_row.pack(fill="x", padx=20, pady=(0, 10))
        tk.Label(view_d_row, text="View D", width=16, anchor="w", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Label(view_d_row, text="Alt km", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 2))
        self.view_d_alt_entry = tk.Entry(view_d_row, textvariable=self.view_d_alt_var, width=6, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.view_d_alt_entry.pack(side="left", padx=(0, 6))
        tk.Label(view_d_row, text="s/rev", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 2))
        self.view_d_period_entry = tk.Entry(view_d_row, textvariable=self.view_d_period_var, width=6, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.view_d_period_entry.pack(side="left", padx=(0, 6))
        tk.Label(view_d_row, text="Cam focal", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 2))
        self.view_d_focal_entry = tk.Entry(view_d_row, textvariable=self.view_d_focal_var, width=6, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.view_d_focal_entry.pack(side="left", padx=(0, 6))

        orbit_row = tk.Frame(self.simulation_control_window, bg="#1e1e24")
        orbit_row.pack(fill="x", padx=20, pady=(0, 10))
        tk.Label(orbit_row, text="Orbit shape", width=16, anchor="w", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Label(orbit_row, text="Incline deg", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 2))
        self.view_d_inc_entry = tk.Entry(orbit_row, textvariable=self.view_d_inclination_var, width=6, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.view_d_inc_entry.pack(side="left", padx=(0, 6))
        tk.Label(orbit_row, text="Phase deg", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 2))
        self.view_d_phase_entry = tk.Entry(orbit_row, textvariable=self.view_d_phase_var, width=6, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.view_d_phase_entry.pack(side="left", padx=(0, 6))

        geosync_row = tk.Frame(self.simulation_control_window, bg="#1e1e24")
        geosync_row.pack(fill="x", padx=20, pady=(0, 12))
        tk.Label(geosync_row, text="", width=16, anchor="w", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9, "bold")).pack(side="left")
        self.sat_geosync_cb = tk.Checkbutton(geosync_row, text="Geosync", variable=self.sat_geosync_var, command=lambda: (self.save_settings(), self.render_globe()), fg="#ffffff", bg="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff", selectcolor="#1e1e24")
        self.sat_geosync_cb.pack(side="left", padx=(0, 6))
        tk.Label(geosync_row, text="Geo lat", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 2))
        self.view_d_geolat_entry = tk.Entry(geosync_row, textvariable=self.view_d_geolat_var, width=6, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.view_d_geolat_entry.pack(side="left", padx=(0, 6))
        tk.Label(geosync_row, text="Geo lon", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 8)).pack(side="left", padx=(0, 2))
        self.view_d_geolon_entry = tk.Entry(geosync_row, textvariable=self.view_d_geolon_var, width=6, bg="#10151c", fg="#d9e1e8", insertbackground="#d9e1e8")
        self.view_d_geolon_entry.pack(side="left", padx=(0, 6))

        self.view_b_dist_base_entry.bind("<Return>", lambda e: (self.save_settings(), self.render_globe()))
        self.view_b_focal_entry.bind("<Return>", lambda e: (self.save_settings(), self.render_globe()))
        self.view_b_floor_entry.bind("<Return>", lambda e: (self.save_settings(), self.render_globe()))
        self.view_c_dist_base_entry.bind("<Return>", lambda e: (self.save_settings(), self.render_globe()))
        self.view_c_alt_factor_entry.bind("<Return>", lambda e: (self.save_settings(), self.render_globe()))
        self.view_c_floor_a_entry.bind("<Return>", lambda e: (self.save_settings(), self.render_globe()))
        self.view_c_floor_b_entry.bind("<Return>", lambda e: (self.save_settings(), self.render_globe()))
        self.view_d_alt_entry.bind("<Return>", lambda e: (self.save_settings(), self.render_globe()))
        self.view_d_period_entry.bind("<Return>", lambda e: (self.save_settings(), self.render_globe()))
        self.view_d_focal_entry.bind("<Return>", lambda e: (self.save_settings(), self.render_globe()))
        self.view_d_inc_entry.bind("<Return>", lambda e: (self.save_settings(), self.render_globe()))
        self.view_d_phase_entry.bind("<Return>", lambda e: (self.save_settings(), self.render_globe()))
        self.view_d_geolat_entry.bind("<Return>", lambda e: (self.save_settings(), self.render_globe()))
        self.view_d_geolon_entry.bind("<Return>", lambda e: (self.save_settings(), self.render_globe()))

        preset_row = tk.Frame(self.simulation_control_window, bg="#1e1e24")
        preset_row.pack(fill="x", padx=20, pady=(4, 12))
        tk.Label(preset_row, text="View presets", width=16, anchor="w", fg="#ffffff", bg="#1e1e24", font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Button(preset_row, text="Ground View", command=self.apply_sample_ground_view, bg="#27ae60", fg="white", bd=0, width=14, pady=3).pack(side="left", padx=(0, 10))
        tk.Button(preset_row, text="Space View", command=self.apply_sample_space_view, bg="#2980b9", fg="white", bd=0, width=14, pady=3).pack(side="left")
        tk.Button(preset_row, text="View B/C Reset", command=self.reset_view_params, bg="#e74c3c", fg="white", bd=0, width=14, pady=3).pack(side="left", padx=(10, 0))

        self.refresh_control_states()

    def close_simulation_control_window(self):
        if self.simulation_control_window is not None and self.simulation_control_window.winfo_exists():
            self.simulation_control_window.destroy()
        self.simulation_control_window = None
        self.view_center_lat_entry = None
        self.view_center_lon_entry = None
        self.view_altitude_entry = None
        self.view_yaw_entry = None
        self.view_pitch_entry = None
        self.view_b_dist_base_entry = None
        self.view_b_focal_entry = None
        self.view_b_floor_entry = None
        self.view_c_dist_base_entry = None
        self.view_c_alt_factor_entry = None
        self.view_c_floor_a_entry = None
        self.view_c_floor_b_entry = None
        self.view_d_alt_entry = None
        self.view_d_period_entry = None
        self.view_d_focal_entry = None
        self.view_d_inc_entry = None
        self.view_d_phase_entry = None
        self.sat_geosync_cb = None
        self.view_d_geolat_entry = None
        self.view_d_geolon_entry = None

    def apply_sample_space_view(self):
        """Applies a sample preset space orbit view looking at the flight path from high altitude."""
        # Find the active missile or the first missile in the simulation to focus on
        focus_msl = None
        focus_intcp = None
        for idx, msl in enumerate(self.missiles):
            if msl.active:
                focus_msl = msl
                focus_intcp = self.interceptors[idx]
                break
        if focus_msl is None and len(self.missiles) > 0:
            focus_msl = self.missiles[0]
            focus_intcp = self.interceptors[0]

        # Extract positions of the focus missile and interceptor
        if focus_msl is not None:
            msl_start = self.simulation_vector_to_globe_point(focus_msl.path[0])
            msl_target = self.simulation_vector_to_globe_point(focus_msl.target)
            if focus_intcp is not None and len(focus_intcp.path) > 0:
                int_start = self.simulation_vector_to_globe_point(focus_intcp.path[0])
            else:
                int_start = self.lat_lon_to_unit(self.config.interceptor_start_lat, self.config.interceptor_start_lon)
        else:
            msl_start = self.lat_lon_to_unit(self.config.missile_start_lat, self.config.missile_start_lon)
            msl_target = self.lat_lon_to_unit(self.config.missile_target_lat, self.config.missile_target_lon)
            int_start = self.lat_lon_to_unit(self.config.interceptor_start_lat, self.config.interceptor_start_lon)

        # Centroid of the focus trajectory elements
        focus_pts = [msl_start, msl_target, int_start]
        avg_pos = np.mean(focus_pts, axis=0)
        avg_pos /= np.linalg.norm(avg_pos)
        
        # Convert centroid back to lat/lon
        center_geo = self.unit_to_lat_lon(avg_pos)
        if center_geo is not None:
            center_lat, center_lon = center_geo
        else:
            center_lat, center_lon = 39.73, 100.25

        # Calculate the maximum angular distance from the centroid to any of the key points
        max_theta = 0.0
        for pt in focus_pts:
            cos_theta = np.dot(avg_pos, pt)
            theta = math.acos(max(min(cos_theta, 1.0), -1.0))
            if theta > max_theta:
                max_theta = theta

        # Map the spread to a beautiful zoom level
        if max_theta > 0.01:
            computed_zoom = 1.35 / max_theta
        else:
            computed_zoom = 3.2
        
        # We also want to leave a nice margin (say 15%) so paths don't hit the screen borders
        computed_zoom *= 0.85
        self.globe_zoom = min(max(computed_zoom, 0.7), 3.2)
        self.update_globe_radius()

        # Set view center and altitude
        self.view_center_lat_var.set(f"{center_lat:.4f}")
        self.view_center_lon_var.set(f"{center_lon:.4f}")
        self.view_altitude_km_var.set("5000.0")  # Majestic space altitude
        self.view_mode_var.set("C")
        self.apply_view_center_from_fields()

        # Tilt/slant the view angles slightly to show gorgeous 3D depth and arc heights
        self.view_pitch_deg = max(min(self.view_pitch_deg + 15.0, 80.0), -80.0)
        self.view_yaw_deg = ((self.view_yaw_deg + 10.0 + 180.0) % 360.0) - 180.0
        
        self.view_yaw_var.set(f"{self.view_yaw_deg:.2f}")
        self.view_pitch_var.set(f"{self.view_pitch_deg:.2f}")
        self.apply_view_angle_from_fields()

        # For space view, turn off "msl tracking" by default so we can see the entire global theater and paths stably
        self.msl_tracking_var.set(False)
        self.render_globe()

    def apply_sample_ground_view(self):
        """Applies a sample preset ground viewpoint situated at the launch site looking skyward."""
        # Find the active missile or the first missile in the simulation to focus on
        focus_msl = None
        focus_intcp = None
        for idx, msl in enumerate(self.missiles):
            if msl.active:
                focus_msl = msl
                focus_intcp = self.interceptors[idx]
                break
        if focus_msl is None and len(self.missiles) > 0:
            focus_msl = self.missiles[0]
            focus_intcp = self.interceptors[0]

        # Extract positions of the focus missile and interceptor
        if focus_msl is not None:
            msl_start = self.simulation_vector_to_globe_point(focus_msl.path[0])
            msl_target = self.simulation_vector_to_globe_point(focus_msl.target)
            if focus_intcp is not None and len(focus_intcp.path) > 0:
                int_start = self.simulation_vector_to_globe_point(focus_intcp.path[0])
            else:
                int_start = self.lat_lon_to_unit(self.config.interceptor_start_lat, self.config.interceptor_start_lon)
        else:
            msl_start = self.lat_lon_to_unit(self.config.missile_start_lat, self.config.missile_start_lon)
            msl_target = self.lat_lon_to_unit(self.config.missile_target_lat, self.config.missile_target_lon)
            int_start = self.lat_lon_to_unit(self.config.interceptor_start_lat, self.config.interceptor_start_lon)

        # Centroid of the focus trajectory elements to center the theater map
        focus_pts = [msl_start, msl_target, int_start]
        avg_pos = np.mean(focus_pts, axis=0)
        avg_pos /= np.linalg.norm(avg_pos)
        
        # Convert centroid back to lat/lon
        center_geo = self.unit_to_lat_lon(avg_pos)
        if center_geo is not None:
            center_lat, center_lon = center_geo
        else:
            center_lat, center_lon = 39.73, 100.25

        # Calculate the maximum angular distance from the centroid to any of the key points
        max_theta = 0.0
        for pt in focus_pts:
            cos_theta = np.dot(avg_pos, pt)
            theta = math.acos(max(min(cos_theta, 1.0), -1.0))
            if theta > max_theta:
                max_theta = theta

        # Map the spread to a beautiful wide-angle zoom level
        # Uses a wider spread zoom with 30% extra margin for maximum situational awareness!
        if max_theta > 0.01:
            computed_zoom = 1.35 / max_theta
        else:
            computed_zoom = 3.2
            
        computed_zoom *= 0.70  # wide-angle factor for maximum situational awareness
        self.globe_zoom = min(max(computed_zoom, 0.65), 1.6)
        self.update_globe_radius()

        # Set view center and altitude
        self.view_center_lat_var.set(f"{center_lat:.4f}")
        self.view_center_lon_var.set(f"{center_lon:.4f}")
        self.view_altitude_km_var.set("1.0")  # Slightly elevated for a beautiful flat-map layout
        self.view_mode_var.set("C")
        self.apply_view_center_from_fields()

        # Tilt/slant the view angles slightly to show gorgeous 3D depth stably
        self.view_pitch_deg = 35.0  # Stable angle looking down onto the flat map
        self.view_yaw_deg = 169.26  # Standard beautiful yaw
        
        self.view_yaw_var.set(f"{self.view_yaw_deg:.2f}")
        self.view_pitch_var.set(f"{self.view_pitch_deg:.2f}")
        self.apply_view_angle_from_fields()

        # Disable "msl tracking" by default for Ground View so that the ground stays perfectly flat and stable
        # like a map under the trajectories, rather than spinning around!
        self.msl_tracking_var.set(False)
        self.render_globe()

    def reset_view_params(self):
        """Resets the View B, C, and D parameters to their original hardcoded defaults."""
        self.view_b_dist_base_var.set("1.010")
        self.view_b_focal_var.set("1.00")
        self.view_b_floor_var.set("0.080")
        self.view_c_dist_base_var.set("1.450")
        self.view_c_alt_factor_var.set("0.90")
        self.view_c_floor_a_var.set("0.150")
        self.view_c_floor_b_var.set("0.080")
        self.view_d_alt_var.set("800.0")
        self.view_d_period_var.set("120.0")
        self.view_d_focal_var.set("2.50")
        self.save_settings()
        self.render_globe()

    def set_status(self, text, color="#cfd8dc"):
        self.status_text = text
        self.status_color = color
        if hasattr(self, "status_lbl"):
            self.status_lbl.config(text=text, fg=color)

    def reset_simulation_state(self):
        try:
            loft_f = float(self.missile_loft_factor_var.get() or 0.8)
            msl_r = float(self.missile_hit_radius_var.get() or 0.0015)
            int_r = float(self.interceptor_hit_radius_var.get() or 0.003)
            vis_r = float(self.loft_vis_ratio_var.get() or 1.0)
            self.config.missile_loft_factor = loft_f
            self.config.missile_hit_radius = msl_r
            self.config.interceptor_hit_radius = int_r
            self.config.loft_vis_ratio = max(min(vis_r, 10.0), 1.0)
            spd_vis = float(self.spd_vis_ratio_var.get() or 1.0)
            self.config.spd_vis_ratio = max(spd_vis, 1.0)
        except ValueError:
            pass

        self.missiles = []
        self.interceptors = []
        self.explosions = []
        
        # Clear geodetic coordinates cache on the warning window to prevent ID-reuse trail ghosting!
        if hasattr(self, "impact_window") and self.impact_window is not None and self.impact_window.winfo_exists():
            try:
                self.impact_window.geo_path_cache = {}
            except Exception:
                pass
        
        data = read_settings_data(self.settings_file)
        self.missile_groups = data.get("missile_groups", {})
        
        try:
            msl_grp_delay = float(data.get("msl_grp_delay", 5.0))
            msl_delay = float(data.get("msl_delay", 2.0))
            self.msl_path_size = float(data.get("msl_path_size", 3.0))
            self.int_path_size = float(data.get("int_path_size", 3.0))
        except ValueError:
            msl_grp_delay, msl_delay = 5.0, 2.0
            self.msl_path_size = 3.0
            self.int_path_size = 3.0
            
        # Collect all configured interceptor launch sites from settings
        # Each site is represented as: { "group_name": group_name, "id": id, "lat": lat, "lon": lon, "assigned_count": 0 }
        all_launchers = []
        self.interceptor_groups = data.get("interceptor_groups", {})
        if hasattr(self, "interceptor_groups") and self.interceptor_groups:
            for g_name, pairs in self.interceptor_groups.items():
                for pair in pairs:
                    all_launchers.append({
                        "group_name": g_name,
                        "id": pair["id"],
                        "lat": pair["start_lat"],
                        "lon": pair["start_lon"],
                        "assigned_count": 0
                    })

        if hasattr(self, "missile_groups") and self.missile_groups:
            sorted_groups = sorted(self.missile_groups.keys())
            for g_idx, group_name in enumerate(sorted_groups):
                pairs = self.missile_groups[group_name]
                sorted_pairs = sorted(pairs, key=lambda x: x["id"])
                
                # Group start time based on alpha beta order
                g_start_time = g_idx * msl_grp_delay
                
                for idx, pair in enumerate(sorted_pairs):
                    i = pair["id"]
                    # Individual launch time
                    t_launch = g_start_time + idx * msl_delay
                    
                    m = TargetMissile(
                        start_lat=pair["start_lat"],
                        start_lon=pair["start_lon"],
                        start_altitude_km=0.0,
                        target_lat=pair["target_lat"],
                        target_lon=pair["target_lon"],
                        target_altitude_km=0.0,
                        speed=self.config.missile_speed,
                        loft_factor=self.config.missile_loft_factor * self.config.loft_vis_ratio,
                        hit_radius=self.config.missile_hit_radius
                    )
                    m.label = f"{group_name}-M{i}"
                    m.target_label = f"{group_name}-T{i}"
                    m.launch_time = t_launch
                    m.launched = False
                    m.active = False # initially inactive until launched
                    
                    # Battle Management System: Intelligently pair this missile with the best available interceptor launcher!
                    paired_lat = self.config.interceptor_start_lat
                    paired_lon = self.config.interceptor_start_lon
                    paired_alt = self.config.interceptor_start_altitude_km
                    int_label = f"{group_name}-Int{i}"
                    
                    # Filter launchers of the same group name if possible, otherwise look at any available launchers
                    same_group_launchers = [l for l in all_launchers if l["group_name"] == group_name]
                    candidates = same_group_launchers if same_group_launchers else all_launchers
                    
                    if candidates:
                        # Find candidate with the minimum assigned_count (to distribute loads evenly!)
                        min_assigned = min(l["assigned_count"] for l in candidates)
                        eligible_candidates = [l for l in candidates if l["assigned_count"] == min_assigned]
                        
                        # Among eligible candidates, pick the one closest to the missile's launch site!
                        msl_start_unit = self.lat_lon_to_unit(pair["start_lat"], pair["start_lon"])
                        
                        best_launcher = None
                        min_dist = float("inf")
                        for l in eligible_candidates:
                            l_unit = self.lat_lon_to_unit(l["lat"], l["lon"])
                            dist = np.linalg.norm(msl_start_unit - l_unit)
                            if dist < min_dist:
                                min_dist = dist
                                best_launcher = l
                                
                        if best_launcher:
                            paired_lat = best_launcher["lat"]
                            paired_lon = best_launcher["lon"]
                            paired_alt = 0.0
                            int_label = f"{best_launcher['group_name']}-Int{best_launcher['id']}"
                            best_launcher["assigned_count"] += 1

                    intcp = Interceptor(
                        start_lat=paired_lat,
                        start_lon=paired_lon,
                        start_altitude_km=paired_alt,
                        speed=self.config.interceptor_speed,
                        proportional_gain=self.config.proportional_gain,
                        hit_radius=self.config.interceptor_hit_radius
                    )
                    intcp.label = int_label
                    intcp.launched = False
                    intcp.launch_time = t_launch + self.config.interceptor_delay_sec
                    
                    self.missiles.append(m)
                    self.interceptors.append(intcp)
        else:
            m = TargetMissile(
                start_lat=self.config.missile_start_lat,
                start_lon=self.config.missile_start_lon,
                start_altitude_km=self.config.missile_start_altitude_km,
                target_lat=self.config.missile_target_lat,
                target_lon=self.config.missile_target_lon,
                target_altitude_km=self.config.missile_target_altitude_km,
                speed=self.config.missile_speed,
                loft_factor=self.config.missile_loft_factor * self.config.loft_vis_ratio,
                hit_radius=self.config.missile_hit_radius
            )
            m.label = "Missile"
            m.target_label = "M-Target"
            m.launch_time = 0.0
            m.launched = True
            m.active = True
            
            intcp = Interceptor(
                start_lat=self.config.interceptor_start_lat,
                start_lon=self.config.interceptor_start_lon,
                start_altitude_km=self.config.interceptor_start_altitude_km,
                speed=self.config.interceptor_speed,
                proportional_gain=self.config.proportional_gain,
                hit_radius=self.config.interceptor_hit_radius
            )
            intcp.label = "Interceptor"
            intcp.launched = False
            intcp.launch_time = self.config.interceptor_delay_sec
            
            self.missiles.append(m)
            self.interceptors.append(intcp)

        self.missile = self.missiles[0]
        self.interceptor = self.interceptors[0]
        self.interceptor_launched = False
        self.simulation_finished = False
        self.sim_elapsed_time = 0.0
        self.refresh_control_states()

    def refresh_control_states(self):
        if hasattr(self, "launch_btn"):
            can_launch = any(not intcp.launched and msl.active for idx, msl in enumerate(self.missiles) for intcp in [self.interceptors[idx]]) and not self.simulation_finished
            self.launch_btn.config(state="normal" if can_launch else "disabled", bg="#ff8f1f" if can_launch else "#78909c", activebackground="#ff9f43" if can_launch else "#78909c")
        if hasattr(self, "pause_btn"):
            self.pause_btn.config(text="Play" if self.is_paused else "Pause", state="normal" if not self.simulation_finished else "disabled", bg="#607d8b" if not self.simulation_finished else "#78909c")

    def save_settings(self):
        data = read_settings_data(self.settings_file)
        self.root.update_idletasks()
        data["simulation_window_width"] = int(self.root.winfo_width())
        data["simulation_window_height"] = int(self.root.winfo_height())
        data["simulation_window_x"] = int(self.root.winfo_x())
        data["simulation_window_y"] = int(self.root.winfo_y())
        data["simulation_view_yaw"] = float(self.view_yaw_deg)
        data["simulation_view_pitch"] = float(self.view_pitch_deg)
        data["simulation_globe_zoom"] = float(self.globe_zoom)
        data["simulation_show_wireframe"] = bool(self.show_wireframe_var.get())
        data["simulation_show_boundaries"] = bool(self.show_boundaries_var.get())
        data["simulation_show_map"] = bool(self.show_map_var.get())
        data["simulation_show_msl_lbl"] = bool(self.show_msl_lbl_var.get())
        data["offline_mode"] = bool(self.offline_mode_var.get())
        data["simulation_show_missile_path"] = bool(self.show_missile_path_var.get())
        data["simulation_show_interceptor_path"] = bool(self.show_interceptor_path_var.get())
        data["simulation_project_tracks_to_ground"] = bool(self.project_tracks_to_ground_var.get())
        data["simulation_msl_tracking"] = bool(self.msl_tracking_var.get())
        data["simulation_show_status"] = bool(self.show_status_var.get())
        data["simulation_show_height_line"] = bool(self.show_height_line_var.get())
        data["simulation_show_local_horizon"] = bool(self.show_local_horizon_var.get())
        data["simulation_missile_loft_factor"] = float(self.missile_loft_factor_var.get() or 0.8)
        data["simulation_missile_hit_radius"] = float(self.missile_hit_radius_var.get() or 0.0015)
        data["simulation_interceptor_hit_radius"] = float(self.interceptor_hit_radius_var.get() or 0.003)
        data["simulation_loft_vis_ratio"] = float(self.loft_vis_ratio_var.get() or 1.0)
        data["simulation_spd_vis_ratio"] = float(self.spd_vis_ratio_var.get() or 1.0)
        data["simulation_view_mode"] = str(self.view_mode_var.get())
        data["simulation_view_b_dist_base"] = float(self.view_b_dist_base_var.get() or 1.01)
        data["simulation_view_b_focal"] = float(self.view_b_focal_var.get() or 1.0)
        data["simulation_view_b_floor"] = float(self.view_b_floor_var.get() or 0.08)
        data["simulation_view_c_dist_base"] = float(self.view_c_dist_base_var.get() or 1.45)
        data["simulation_view_c_alt_factor"] = float(self.view_c_alt_factor_var.get() or 0.9)
        data["simulation_view_c_floor_a"] = float(self.view_c_floor_a_var.get() or 0.15)
        data["simulation_view_c_floor_b"] = float(self.view_c_floor_b_var.get() or 0.08)
        data["simulation_view_d_alt"] = float(self.view_d_alt_var.get() or 800.0)
        data["simulation_view_d_period"] = float(self.view_d_period_var.get() or 120.0)
        data["simulation_view_d_focal"] = float(self.view_d_focal_var.get() or 2.5)
        data["simulation_sat_geosync"] = bool(self.sat_geosync_var.get())
        data["simulation_view_d_inclination"] = float(self.view_d_inclination_var.get() or 45.0)
        data["simulation_view_d_phase"] = float(self.view_d_phase_var.get() or 0.0)
        data["simulation_view_d_geolat"] = float(self.view_d_geolat_var.get() or 0.0)
        data["simulation_view_d_geolon"] = float(self.view_d_geolon_var.get() or 130.0)
        data["simulation_view_altitude_km"] = float(self.get_view_altitude_km())
        data["simulation_view_yaw_deg"] = float(self.view_yaw_deg)
        data["simulation_view_pitch_deg"] = float(self.view_pitch_deg)
        data["simulation_globe_zoom"] = float(self.globe_zoom)
        write_settings_data(self.settings_file, data)

    def reload_parameters_from_gui(self):
        # Reload parameters from settings file
        data = read_settings_data(self.settings_file)
        if not data:
            return
            
        try:
            # 1. Update paths and sizes
            self.msl_path_size = float(data.get("msl_path_size", 3.0))
            self.int_path_size = float(data.get("int_path_size", 3.0))
            
            # 2. Rebuild simulation config speeds, PN gain, delays in real-time
            self.config.missile_speed = float(data.get("missile_speed", 5.0)) / 1000.0
            self.config.interceptor_speed = float(data.get("interceptor_speed", 7.0)) / 1000.0
            self.config.proportional_gain = float(data.get("proportional_gain", 4.0))
            self.config.interceptor_delay_sec = float(data.get("interceptor_delay_sec", 3.0))
            self.config.auto_launch_interceptor = bool(data.get("auto_launch_interceptor", True))
            self.config.tracking_algorithm = str(data.get("tracking_algorithm", "EKF"))
            self.config.mp_mode = bool(data.get("mp_mode", False))
            
            # 3. Apply to all active flying objects and update queues dynamically
            msl_grp_delay = float(data.get("msl_grp_delay", 5.0))
            msl_delay = float(data.get("msl_delay", 2.0))
            
            # Update missile speeds and recalculate launch timelines in real-time!
            if self.missile_groups:
                sorted_groups = sorted(self.missile_groups.keys())
                msl_index = 0
                for g_idx, group_name in enumerate(sorted_groups):
                    pairs = self.missile_groups[group_name]
                    sorted_pairs = sorted(pairs, key=lambda x: x["id"])
                    g_start_time = g_idx * msl_grp_delay
                    for idx, pair in enumerate(sorted_pairs):
                        if msl_index < len(self.missiles):
                            msl = self.missiles[msl_index]
                            intcp = self.interceptors[msl_index]
                            t_launch = g_start_time + idx * msl_delay
                            
                            msl.speed = self.config.missile_speed
                            msl.launch_time = t_launch
                            
                            intcp.speed = self.config.interceptor_speed
                            intcp.proportional_gain = self.config.proportional_gain
                            intcp.launch_time = t_launch + self.config.interceptor_delay_sec
                        msl_index += 1
            else:
                if len(self.missiles) > 0:
                    self.missiles[0].speed = self.config.missile_speed
                    self.interceptors[0].speed = self.config.interceptor_speed
                    self.interceptors[0].proportional_gain = self.config.proportional_gain
                    self.interceptors[0].launch_time = self.config.interceptor_delay_sec
        except Exception:
            pass
            
        # Re-render to show updated lines and icon sizes instantly!
        self.render_globe()

    def restore_window_size(self):
        data = read_settings_data(self.settings_file)
        sim_window_size = read_saved_window_size(
            data,
            "simulation_window_width",
            "simulation_window_height",
        )
        if sim_window_size is not None:
            geometry = f"{sim_window_size[0]}x{sim_window_size[1]}"
            try:
                sim_window_x = int(data.get("simulation_window_x"))
                sim_window_y = int(data.get("simulation_window_y"))
            except (TypeError, ValueError):
                sim_window_x = None
                sim_window_y = None
            if sim_window_x is not None and sim_window_y is not None:
                geometry = f"{geometry}+{sim_window_x}+{sim_window_y}"
            self.root.geometry(geometry)

    def on_launch_key(self, event=None):
        self.launch_interceptor()

    def launch_interceptor(self):
        launched_any = False
        for idx, msl in enumerate(self.missiles):
            intcp = self.interceptors[idx]
            if not intcp.launched and msl.active:
                intcp.launch()
                intcp.launched = True
                launched_any = True
        if launched_any:
            self.interceptor_launched = True
            self.refresh_control_states()
            self.set_status("Status: Interceptors launched.", "#80cbc4")
            self.render_globe()

    def toggle_pause(self):
        if self.simulation_finished:
            return
        self.is_paused = not self.is_paused
        self.refresh_control_states()
        if self.is_paused:
            if self.after_job is not None:
                self.root.after_cancel(self.after_job)
                self.after_job = None
            self.set_status("Status: Simulation paused.", "#ffd166")
            
            # If recording, stop and save it!
            if getattr(self, "recording_state", "inactive") == "recording":
                self.stop_recording()
        else:
            self.real_start_time = time.time()
            self.real_accumulated_time = self.sim_elapsed_time
            self.set_status("Status: Simulation resumed.", "#80cbc4")
            
            # Automatically launch the separate Missile Impact Warning window and live reload server!
            try:
                import sys
                import subprocess
                sys.path.append(os.path.dirname(__file__))
                import impact
                
                # Launch updatemap.py once in starting simulation if show map is enabled
                if self.show_map_var.get():
                    self._spawn_updatemap_process()
                
                if self.impact_window is None or not self.impact_window.winfo_exists():
                    target_lat = self.config.missile_target_lat
                    target_lon = self.config.missile_target_lon
                    self.impact_window = impact.MissileImpactWarningWindow(self.root, target_lat, target_lon, self)

            except Exception as e:
                print("Error opening impact window:", e)
            
            # If recording is armed, start recording now!
            if getattr(self, "recording_state", "inactive") == "armed":
                self.start_recording()
                
            self.schedule_step()
        self.render_globe()

    def toggle_recording_ui(self):
        import cv2
        from tkinter import messagebox
        
        if getattr(self, "recording_state", "inactive") == "recording":
            self.stop_recording()
            return
        elif getattr(self, "recording_state", "inactive") == "armed":
            self.recording_state = "inactive"
            self.record_btn.config(text="Record", bg="#b0bec5", fg="black")
            self.set_status("Status: Recording cancelled.", "#80cbc4")
            return
            
        # Select Area Selection popup dialog
        area_dialog = tk.Toplevel(self.root)
        area_dialog.title("Recording Selection")
        area_dialog.geometry("320x240")
        area_dialog.configure(bg="#1e1e24")
        area_dialog.grab_set()  # Make dialog modal
        area_dialog.focus_set()
        
        # Center the dialog on screen
        area_dialog.update_idletasks()
        rx = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - 160
        ry = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - 120
        area_dialog.geometry(f"+{rx}+{ry}")
        
        tk.Label(area_dialog, text="Select Recording Area", font=("Segoe UI", 11, "bold"), fg="#ffffff", bg="#1e1e24").pack(pady=(12, 10))
        
        area_var = tk.StringVar(value="canvas")
        
        tk.Radiobutton(area_dialog, text="Simulation Map Only (Globe Canvas)", variable=area_var, value="canvas", font=("Segoe UI", 9), fg="#ffffff", bg="#1e1e24", selectcolor="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff").pack(anchor="w", padx=30, pady=4)
        tk.Radiobutton(area_dialog, text="Full Simulator Window", variable=area_var, value="window", font=("Segoe UI", 9), fg="#ffffff", bg="#1e1e24", selectcolor="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff").pack(anchor="w", padx=30, pady=4)
        tk.Radiobutton(area_dialog, text="Entire Monitor Screen", variable=area_var, value="screen", font=("Segoe UI", 9), fg="#ffffff", bg="#1e1e24", selectcolor="#1e1e24", activebackground="#1e1e24", activeforeground="#ffffff").pack(anchor="w", padx=30, pady=4)
        
        def on_confirm():
            self.recording_area = area_var.get()
            self.recording_state = "armed"
            self.record_btn.config(text="Record [Armed]", bg="#ffd54f", fg="black")
            
            # If simulation is currently running (i.e., not paused), start recording immediately!
            if not self.is_paused and not self.simulation_finished:
                self.start_recording()
            else:
                self.set_status("Status: Recording armed. Press Play to start recording.", "#ffd166")
                
            area_dialog.destroy()
            
        tk.Button(area_dialog, text="Confirm Selection", command=on_confirm, font=("Segoe UI", 9, "bold"), bg="#3b6ea8", fg="white", bd=0, padx=16, pady=6).pack(pady=(18, 0))

    def start_recording(self):
        import cv2
        from PIL import ImageGrab
        import datetime
        
        # Calculate bounding box and resolution to initialize VideoWriter
        if self.recording_area == "canvas":
            x = self.globe_canvas.winfo_rootx()
            y = self.globe_canvas.winfo_rooty()
            w = self.globe_canvas.winfo_width()
            h = self.globe_canvas.winfo_height()
        elif self.recording_area == "window":
            x = self.root.winfo_rootx()
            y = self.root.winfo_rooty()
            w = self.root.winfo_width()
            h = self.root.winfo_height()
        else: # "screen"
            screen_img = ImageGrab.grab()
            w, h = screen_img.size
            x, y = 0, 0
            
        # Ensure dimensions are even
        if w % 2 != 0: w += 1
        if h % 2 != 0: h += 1
        
        self.recording_width = w
        self.recording_height = h
        
        # Create output filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.recording_filepath = os.path.join(os.getcwd(), f"simulation_record_{timestamp}.mp4")
        
        # Initialize VideoWriter (highly compatible 'mp4v' codec)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.video_writer = cv2.VideoWriter(self.recording_filepath, fourcc, 15.0, (w, h))
        
        self.recording_state = "recording"
        self.record_btn.config(text="• Recording", bg="#e53935", fg="white")
        self.set_status(f"Status: Recording started ({self.recording_area} area)...", "#e53935")
        
        # Capture first frame immediately
        self.capture_recording_frame()

    def stop_recording(self):
        from tkinter import messagebox
        if getattr(self, "video_writer", None) is not None:
            self.video_writer.release()
            self.video_writer = None
            
        if getattr(self, "recording_state", "inactive") == "recording":
            self.recording_state = "inactive"
            self.record_btn.config(text="Record", bg="#b0bec5", fg="black")
            
            # Show a beautiful notification to the user that it succeeded!
            filepath = getattr(self, "recording_filepath", "")
            self.set_status(f"Status: Recording saved.", "#80cbc4")
            
            # Show message box asynchronously so we don't freeze rendering thread
            def show_box():
                messagebox.showinfo("Recording Saved", f"The simulation video has been successfully recorded and saved to:\n\n{filepath}")
            self.root.after(100, show_box)

    def capture_recording_frame(self):
        import cv2
        from PIL import ImageGrab
        import numpy as np
        
        try:
            # Determine the bounding box
            if self.recording_area == "canvas":
                x = self.globe_canvas.winfo_rootx()
                y = self.globe_canvas.winfo_rooty()
                w = self.globe_canvas.winfo_width()
                h = self.globe_canvas.winfo_height()
                bbox = (x, y, x + w, y + h)
            elif self.recording_area == "window":
                x = self.root.winfo_rootx()
                y = self.root.winfo_rooty()
                w = self.root.winfo_width()
                h = self.root.winfo_height()
                bbox = (x, y, x + w, y + h)
            else: # "screen"
                bbox = None
                
            # Grab screenshot
            if bbox is not None:
                x1, y1, x2, y2 = bbox
                # Adjust if size changed or mismatch
                img = ImageGrab.grab(bbox=(x1, y1, x1 + self.recording_width, y1 + self.recording_height))
            else:
                img = ImageGrab.grab()
                
            frame = np.array(img)
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            # Make sure shape matches exactly (High-DPI screens correction)
            if frame_bgr.shape[1] != self.recording_width or frame_bgr.shape[0] != self.recording_height:
                frame_bgr = cv2.resize(frame_bgr, (self.recording_width, self.recording_height))
                
            self.video_writer.write(frame_bgr)
        except Exception as e:
            print("Error capturing recording frame:", e)

    def open_miw_window(self):
        try:
            import impact
            # 1. Open Missile Impact Warning Window
            if self.impact_window is None or not self.impact_window.winfo_exists():
                target_lat = self.config.missile_target_lat
                target_lon = self.config.missile_target_lon
                self.impact_window = impact.MissileImpactWarningWindow(self.root, target_lat, target_lon, self)
            else:
                self.impact_window.deiconify()
                self.impact_window.lift()
                self.impact_window.focus_force()
                
            # 2. Concurrently open the global floating Missile Warning Map
            self.open_mwm_window()
        except Exception as e:
            print("Error opening MIW and MWM windows:", e)

    def open_mwm_window(self):
        try:
            # Force show_map_var to True
            self.show_map_var.set(True)
            self.save_settings()
            
            # Start updatemap_process directly if not active, bypassing paused/finished simulation states!
            self._spawn_updatemap_process()
        except Exception as e:
            print("Error opening MWM window:", e)

    def open_sat_live_view_window(self):
        try:
            if hasattr(self, "sat_live_view_window") and self.sat_live_view_window is not None and self.sat_live_view_window.winfo_exists():
                self.sat_live_view_window.deiconify()
                self.sat_live_view_window.lift()
                self.sat_live_view_window.focus_force()
            else:
                self.sat_live_view_window = SatLiveViewWindow(self.root, self)
        except Exception as e:
            print("Error opening satellite live view window:", e)

    def get_satellite_orbit_normal(self, sat_info):
        inclination = float(sat_info.get("inclination", 45.0))
        u = self.lat_lon_to_unit(0.0, 0.0)
        e = np.array([u[2], 0.0, -u[0]], dtype=float)
        e_norm = np.linalg.norm(e)
        if e_norm > 1e-9:
            e /= e_norm
        else:
            e = np.array([0.0, 0.0, -1.0], dtype=float)
        n = np.array([0.0, 1.0, 0.0], dtype=float)

        inc_rad = math.radians(inclination)
        v = math.cos(inc_rad) * e + math.sin(inc_rad) * n
        
        n_plane = np.cross(u, v)
        n_plane_norm = np.linalg.norm(n_plane)
        if n_plane_norm > 1e-9:
            n_plane /= n_plane_norm
        return n_plane

    def on_globe_double_click(self, event):
        # Guard: Only allow double-left-click positioning if the "Sat orbit" checkbox is checked!
        if not self.edit_sat_orbit_var.get():
            self.set_status("Status: Check 'Sat orbit' in Simcon window to enable double-click positioning.", "#ff8a80")
            return
            
        geo = self.canvas_to_geolocation(event.x, event.y)
        if geo is None:
            return
        lat, lon = geo
        click_unit = self.lat_lon_to_unit(lat, lon)
        
        # Load current satellites list
        sats = self.load_satellites_list()
        
        # Find the NEAREST display-enabled satellite's 3D orbit plane (including both Geosync and Standard orbital!)
        best_sat = None
        min_dist = float("inf")
        
        for s in sats:
            if s.get("display", True):
                n_plane = self.get_satellite_orbit_normal(s)
                # Mathematical distance of click_unit to the orbit plane (abs of dot product)
                dist = abs(np.dot(click_unit, n_plane))
                if dist < min_dist:
                    min_dist = dist
                    best_sat = s
                    
        if best_sat is not None:
            if best_sat.get("geosync", False):
                # Geosynchronous: update its stationary geodetic coordinates directly!
                best_sat["geolat"] = round(lat, 2)
                best_sat["geolon"] = round(lon, 2)
                self.set_status(f"Status: Repositioned Geosync {best_sat.get('name')} to Lat {lat:.2f}°, Lon {lon:.2f}°", "#ffd700")
            else:
                # Standard orbital: project click_unit onto its orbit plane and find the phase angle!
                n_plane = self.get_satellite_orbit_normal(best_sat)
                proj = click_unit - np.dot(click_unit, n_plane) * n_plane
                proj_norm = np.linalg.norm(proj)
                u = self.lat_lon_to_unit(0.0, 0.0)
                if proj_norm > 1e-9:
                    proj /= proj_norm
                else:
                    proj = u
                    
                inclination = float(best_sat.get("inclination", 45.0))
                
                e = np.array([u[2], 0.0, -u[0]], dtype=float)
                e_norm = np.linalg.norm(e)
                if e_norm > 1e-9:
                    e /= e_norm
                else:
                    e = np.array([0.0, 0.0, -1.0], dtype=float)
                n = np.array([0.0, 1.0, 0.0], dtype=float)

                inc_rad = math.radians(inclination)
                v = math.cos(inc_rad) * e + math.sin(inc_rad) * n
                
                # Project onto the orbit basis u and v
                angle_rad = math.atan2(np.dot(proj, v), np.dot(proj, u))
                
                # Subtract simulation elapsed time orbital progress if currently running to keep starting phase correct!
                orbit_period = float(best_sat.get("period", 120.0))
                time_progress_rad = (self.sim_elapsed_time / orbit_period) * 2.0 * math.pi
                phase_rad = angle_rad - time_progress_rad
                
                phase_deg = math.degrees(phase_rad) % 360.0
                best_sat["phase"] = round(phase_deg, 2)
                
                self.set_status(f"Status: Repositioned Orbital {best_sat.get('name')} initial phase to {phase_deg:.2f}°", "#1e90ff")
            
            # Save back to satellites.json
            sat_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "satellites.json")
            with open(sat_path, "w") as f:
                json.dump(sats, f, indent=2)
                
            # Re-render immediately!
            self.render_globe()
            
            # If Sat Edit window is open, rebuild it to show the new coordinates in the grid!
            if self.gui_parent is not None:
                if hasattr(self.gui_parent, "sat_edit_window") and self.gui_parent.sat_edit_window is not None:
                    if self.gui_parent.sat_edit_window.winfo_exists():
                        self.gui_parent.sat_edit_window.destroy()
                        self.gui_parent.sat_edit_window = None
                        self.gui_parent.on_sat_edit()

    def toggle_winrec_ui(self):
        if getattr(self, "winrec_state", "inactive") == "recording":
            self.stop_winrec()
            return
            
        self.set_status("Status: Drag mouse to select screen area (Esc to cancel)...", "#ffd166")
        ScreenAreaSelector(self.root, self.start_winrec)

    def start_winrec(self, bbox):
        import cv2
        import datetime
        
        self.winrec_bbox = bbox
        x1, y1, x2, y2 = bbox
        w = x2 - x1
        h = y2 - y1
        
        # Ensure dimensions are even
        if w % 2 != 0: w += 1
        if h % 2 != 0: h += 1
        
        self.winrec_width = w
        self.winrec_height = h
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.winrec_filepath = os.path.join(os.getcwd(), f"winrec_manual_{timestamp}.mp4")
        
        # Initialize manual VideoWriter (highly compatible 'mp4v' codec)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.winrec_writer = cv2.VideoWriter(self.winrec_filepath, fourcc, 15.0, (w, h))
        
        self.winrec_state = "recording"
        self.winrec_btn.config(text="• WinRec", bg="#e53935", fg="white")
        self.set_status("Status: Manual recording started...", "#e53935")
        
        # Start independent capture loop
        self.capture_winrec_loop()

    def stop_winrec(self):
        from tkinter import messagebox
        if getattr(self, "winrec_writer", None) is not None:
            self.winrec_writer.release()
            self.winrec_writer = None
            
        if getattr(self, "winrec_state", "inactive") == "recording":
            self.winrec_state = "inactive"
            self.winrec_btn.config(text="WinRec", bg="#90a4ae", fg="black")
            
            filepath = getattr(self, "winrec_filepath", "")
            self.set_status("Status: Manual recording saved.", "#80cbc4")
            
            def show_box():
                messagebox.showinfo("Manual Recording Saved", f"The manual screen video has been successfully recorded and saved to:\n\n{filepath}")
            self.root.after(100, show_box)

    def capture_winrec_frame(self):
        import cv2
        from PIL import ImageGrab
        import numpy as np
        
        try:
            if self.winrec_bbox is not None:
                x1, y1, x2, y2 = self.winrec_bbox
                img = ImageGrab.grab(bbox=(x1, y1, x1 + self.winrec_width, y1 + self.winrec_height))
            else:
                img = ImageGrab.grab()
                
            frame = np.array(img)
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            # DPI scale correction
            if frame_bgr.shape[1] != self.winrec_width or frame_bgr.shape[0] != self.winrec_height:
                frame_bgr = cv2.resize(frame_bgr, (self.winrec_width, self.winrec_height))
                
            self.winrec_writer.write(frame_bgr)
        except Exception as e:
            print("Error capturing manual winrec frame:", e)

    def capture_winrec_loop(self):
        if getattr(self, "winrec_state", "inactive") != "recording" or getattr(self, "winrec_writer", None) is None:
            return
            
        self.capture_winrec_frame()
        self.root.after(66, self.capture_winrec_loop)  # ~15 FPS

    def restart_simulation(self):
        if self.after_job is not None:
            self.root.after_cancel(self.after_job)
            self.after_job = None
        if self.gui_parent is not None:
            new_config = self.gui_parent.build_config()
            if new_config is not None:
                self.config = new_config
        self.reset_simulation_state()
        self.is_paused = True
        self.set_status("Status: Simulation reset and paused. Press Play to start.", "#80cbc4")
        self.refresh_control_states()
        self.render_globe()

    def load_satellites_list(self):
        sat_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "satellites.json")
        if not os.path.exists(sat_path):
            default_sat = [
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
                    "tle_line1": "1 41866U 16071A   26265.81250000  .00000100  00000-0  00000-0 0  9999",
                    "tle_line2": "2 41866   0.0215  45.5200 0001250 180.2000 180.3000  1.00270000388219"
                },
                {
                    "name": "Sat-A2",
                    "inclination": 60.0,
                    "phase": 30.0,
                    "geosync": True,
                    "geolat": -4.43,
                    "geolon": 78.17,
                    "display": True,
                    "altitude": 800.0,
                    "period": 120.0,
                    "tle": False,
                    "tle_line1": "1 41866U 16071A   26265.81250000  .00000100  00000-0  00000-0 0  9999",
                    "tle_line2": "2 41866   0.0215  45.5200 0001250 180.2000 180.3000  1.00270000388219"
                },
                {
                    "name": "Sat-B1",
                    "inclination": 20.0,
                    "phase": 10.0,
                    "geosync": False,
                    "geolat": 20.0,
                    "geolon": 140.0,
                    "display": True,
                    "altitude": 800.0,
                    "period": 120.0,
                    "tle": False,
                    "tle_line1": "1 25544U 98067A   26265.80775463  .00015505  00000-0  27869-3 0  9997",
                    "tle_line2": "2 25544  51.6408 141.5209 0004546 221.7224 233.1550 15.49503461588219"
                },
                {
                    "name": "Sat-B2",
                    "inclination": 50.0,
                    "phase": 40.0,
                    "geosync": False,
                    "geolat": 30.0,
                    "geolon": 150.0,
                    "display": True,
                    "altitude": 800.0,
                    "period": 120.0,
                    "tle": False,
                    "tle_line1": "1 33591U 09005A   26265.81250000  .00000100  00000-0  77900-4 0  9998",
                    "tle_line2": "2 33591  99.1200 135.5000 0013500 240.2000 120.3000 14.12500000288219"
                }
            ]
            try:
                with open(sat_path, "w") as f:
                    json.dump(default_sat, f, indent=2)
            except Exception:
                pass
                
        satellites = []
        if os.path.exists(sat_path):
            try:
                with open(sat_path, "r") as f:
                    satellites = json.load(f)
            except Exception:
                pass
        if not isinstance(satellites, list):
            satellites = []
            
        if len(satellites) == 0:
            satellites = [
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
                    "tle": False
                }
            ]
        return satellites

    def get_satellite_ecef(self, sat_info):
        sat_alt_km = float(sat_info.get("altitude", 800.0))
        sat_r = 1.0 + sat_alt_km / EARTH_RADIUS_KM
        
        # Check if TLE option is checked for this satellite!
        if sat_info.get("tle", False):
            try:
                from sgp4.api import Satrec, jday
                import datetime
                line1 = sat_info.get("tle_line1")
                line2 = sat_info.get("tle_line2")
                
                # Default/fallback TLEs if not provided in JSON
                if not line1 or not line2:
                    if sat_info.get("geosync", False):
                        # GOES 16 Geosync TLE
                        line1 = "1 41866U 16071A   26265.81250000  .00000100  00000-0  00000-0 0  9999"
                        line2 = "2 41866   0.0215  45.5200 0001250 180.2000 180.3000  1.00270000388219"
                    else:
                        if sat_info.get("name") == "Sat-A1":
                            # HST (Hubble Space Telescope) TLE for Sat-A1
                            line1 = "1 20580U 90037B   26265.81250000  .00000500  00000-0  11200-3 0  9999"
                            line2 = "2 20580  28.4700 120.5000 0003500 180.2000 180.3000 15.12500000288219"
                        elif sat_info.get("name") == "Sat-B2":
                            # NOAA 19 TLE for Sat-B2
                            line1 = "1 33591U 09005A   26265.81250000  .00000100  00000-0  77900-4 0  9998"
                            line2 = "2 33591  99.1200 135.5000 0013500 240.2000 120.3000 14.12500000288219"
                        else:
                            # ISS Polar/Orbital TLE
                            line1 = "1 25544U 98067A   26265.80775463  .00015505  00000-0  27869-3 0  9997"
                            line2 = "2 25544  51.6408 141.5209 0004546 221.7224 233.1550 15.49503461588219"
                        
                sat = Satrec.twoline2rv(line1, line2)
                
                start_time = datetime.datetime(2026, 9, 21, 12, 0, 0, tzinfo=datetime.timezone.utc)
                # Fast-forward simulation: scale time by 30x so they move smoothly and visibly
                scaled_seconds = self.sim_elapsed_time * 30.0
                current_sim_time = start_time + datetime.timedelta(seconds=scaled_seconds)
                
                # Extract starting sub-satellite point of the TLE at epoch
                jd_epoch, fr_epoch = jday(start_time.year, start_time.month, start_time.day,
                                          start_time.hour, start_time.minute, start_time.second)
                err_epoch, pos_epoch, _ = sat.sgp4(jd_epoch, fr_epoch)
                lat_tle, lon_tle = 0.0, 0.0
                if err_epoch == 0:
                    p_surf_start = np.array([pos_epoch[0], pos_epoch[1], pos_epoch[2]], dtype=float)
                    p_surf_start /= np.linalg.norm(p_surf_start)
                    geo_start = self.unit_to_lat_lon(p_surf_start)
                    if geo_start is not None:
                        lat_tle, lon_tle = geo_start
                
                jd, fr = jday(current_sim_time.year, current_sim_time.month, current_sim_time.day,
                              current_sim_time.hour, current_sim_time.minute, current_sim_time.second)
                error, pos_teme, vel = sat.sgp4(jd, fr)
                if error == 0:
                    # SGP4 returns pos in TEME ECI frame (inertial).
                    # Convert to Earth-Fixed ECEF frame by rotating around Z polar axis westwards
                    angle_rad = -((2.0 * math.pi) / 86164.0) * scaled_seconds
                    cos_a = math.cos(angle_rad)
                    sin_a = math.sin(angle_rad)
                    
                    x_ecef = pos_teme[0] * cos_a - pos_teme[1] * sin_a
                    y_ecef = pos_teme[0] * sin_a + pos_teme[1] * cos_a
                    z_ecef = pos_teme[2]
                    
                    pos_ecef = np.array([x_ecef, y_ecef, z_ecef], dtype=float)
                    p_norm = np.linalg.norm(pos_ecef)
                    pos_ecef_unit = pos_ecef / p_norm
                    
                    if sat_info.get("geosync", False):
                        geo_prop = self.unit_to_lat_lon(pos_ecef_unit)
                        if geo_prop is not None:
                            lat_prop, lon_prop = geo_prop
                            lat_user = float(sat_info.get("geolat", 0.0))
                            lon_user = float(sat_info.get("geolon", 130.0))
                            lat_shifted = lat_user + (lat_prop - lat_tle)
                            lon_shifted = lon_user + (lon_prop - lon_tle)
                            pos_ecef_unit = self.lat_lon_to_unit(lat_shifted, lon_shifted)
                            
                    return pos_ecef_unit * sat_r
            except Exception as e:
                print("Error propagating TLE for satellite:", e)
                
        if sat_info.get("geosync", False):
            lat = float(sat_info.get("geolat", 0.0))
            lon = float(sat_info.get("geolon", 130.0))
            p_unit = self.lat_lon_to_unit(lat, lon)
            return p_unit * sat_r
            
        inclination = float(sat_info.get("inclination", 45.0))
        phase = float(sat_info.get("phase", 0.0))
        orbit_period = float(sat_info.get("period", 120.0))
        
        u = self.lat_lon_to_unit(0.0, 0.0)
        e = np.array([u[2], 0.0, -u[0]], dtype=float)
        e_norm = np.linalg.norm(e)
        if e_norm > 1e-9:
            e /= e_norm
        else:
            e = np.array([0.0, 0.0, -1.0], dtype=float)
        n = np.array([0.0, 1.0, 0.0], dtype=float)

        inc_rad = math.radians(inclination)
        v = math.cos(inc_rad) * e + math.sin(inc_rad) * n

        angle = math.radians(phase) + (self.sim_elapsed_time / orbit_period) * 2.0 * math.pi
        sat_dir = math.cos(angle) * u + math.sin(angle) * v
        sat_dir /= np.linalg.norm(sat_dir)
        return sat_dir * sat_r

    def get_satellite_pos(self):
        sats = self.load_satellites_list()
        for s in sats:
            if s.get("display", True):
                return self.get_satellite_ecef(s)
        return self.get_satellite_ecef(sats[0])

    def is_occluded_by_earth(self, point, camera_distance):
        # point is [x, y, z] in view space (after applying view rotation)
        # where the camera is located at [0, 0, camera_distance]
        # We check if the line segment from camera [0, 0, d] to the point intersects the unit sphere's interior
        d = camera_distance
        x, y, z = point
        dx = x
        dy = y
        dz = z - d
        a = dx*dx + dy*dy + dz*dz
        if a < 1e-9:
            return False
        b = 2.0 * d * dz
        c = d*d - 1.0
        t_min = -b / (2.0 * a)
        if 0.0 <= t_min <= 1.0:
            min_val = a * t_min * t_min + b * t_min + c
            if min_val < -0.002:  # strictly negative threshold to allow surface points to remain visible
                return True
        return False

    def simulation_vector_to_globe_point(self, vector, project_to_ground=None):
        point = np.asarray(vector, dtype=float) / EARTH_RADIUS
        project = self.project_tracks_to_ground_var.get()
        if project_to_ground is not None:
            project = project_to_ground
            
        if project:
            norm = np.linalg.norm(point)
            if norm > 1e-9:
                point = point / norm
        return np.array([point[0], point[1], -point[2]], dtype=float)

    def simulation_vector_to_geo_altitude(self, vector):
        vector = np.asarray(vector, dtype=float)
        point = self.simulation_vector_to_globe_point(vector)
        geo = self.unit_to_lat_lon(point)
        if geo is None:
            return None
        altitude_km = max((np.linalg.norm(vector) / EARTH_RADIUS - 1.0) * EARTH_RADIUS_KM, 0.0)
        return geo[0], geo[1], altitude_km

    def draw_simulation_path(self, path_points, color, width=3, project_to_ground=None, show_height_line=True):
        if len(path_points) < 2:
            return
        globe_points = [self.simulation_vector_to_globe_point(point, project_to_ground=project_to_ground) for point in path_points]
        sample_step = max(len(globe_points) // 180, 1)
        sampled_points = globe_points[::sample_step]
        if not np.array_equal(sampled_points[-1], globe_points[-1]):
            sampled_points.append(globe_points[-1])
            
        is_ground = getattr(self, "render_is_ground", False)
        if is_ground:
            # For ground view, draw the path using our perfect 3D homogeneous clipped polyline renderer!
            self.draw_polyline_segments(sampled_points, color, width=width)
            
            # Also draw the altitude dashed height lines in Ground View!
            if self.show_height_line_var.get() and show_height_line:
                for idx, pt in enumerate(sampled_points):
                    if idx % 8 == 0:
                        norm = np.linalg.norm(pt)
                        pt_surf = pt / norm if norm > 1e-9 else pt
                        # Draw vertical altitude dash line from the flight path down to the ground surface
                        self.draw_clipped_line(pt, pt_surf, color, width=1, dash=(2, 2))
            return
            
        # Space view: draw standard height lines and smooth paths
        min_depth = getattr(self, "render_min_depth", 0.02)
        projected_pairs = []
        for point in sampled_points:
            view, x, y = self.project_to_canvas(point)
            norm = np.linalg.norm(point)
            if norm > 1e-9:
                point_surf = point / norm
            else:
                point_surf = point
            view_surf, x_surf, y_surf = self.project_to_canvas(point_surf)
            projected_pairs.append((view, x, y, view_surf, x_surf, y_surf))
        visible_surf = []
        if self.show_height_line_var.get() and show_height_line:
            for view, x, y, view_surf, x_surf, y_surf in projected_pairs:
                if view_surf[2] < min_depth:
                    if len(visible_surf) >= 4:
                        self.globe_canvas.create_line(*visible_surf, fill=color, width=1, dash=(3, 3))
                    visible_surf = []
                    continue
                visible_surf.extend((x_surf, y_surf))
            if len(visible_surf) >= 4:
                self.globe_canvas.create_line(*visible_surf, fill=color, width=1, dash=(3, 3))
        if self.show_height_line_var.get() and show_height_line:
            for idx, (view, x, y, view_surf, x_surf, y_surf) in enumerate(projected_pairs):
                if idx % 8 == 0:
                    if view[2] >= min_depth and view_surf[2] >= min_depth:
                        self.globe_canvas.create_line(x, y, x_surf, y_surf, fill=color, width=1, dash=(2, 2))
        visible_coords = []
        visible_markers = []
        for view, x, y, view_surf, x_surf, y_surf in projected_pairs:
            if view[2] < min_depth:
                if len(visible_coords) >= 4:
                    self.globe_canvas.create_line(*visible_coords, fill="#f2f4f8", width=width + 3, smooth=True)
                    self.globe_canvas.create_line(*visible_coords, fill=color, width=width, smooth=True)
                visible_coords = []
                continue
            visible_coords.extend((x, y))
            visible_markers.append((x, y))
        if len(visible_coords) >= 4:
            self.globe_canvas.create_line(*visible_coords, fill="#f2f4f8", width=width + 3, smooth=True)
            self.globe_canvas.create_line(*visible_coords, fill=color, width=width, smooth=True)

    def draw_simulation_vector_marker(self, vector, color, label, shape, radius=7.0):
        point = self.simulation_vector_to_globe_point(vector)
        view, x, y = self.project_to_canvas(point)
        min_depth = getattr(self, "render_min_depth", 0.02)
        if view[2] < min_depth:
            return
        radius = int(radius)
        outline = "white" if view[2] >= 0.0 else "#666666"
        self.draw_marker_shape(x, y, radius + 3, fill="#ffffff", outline="#ffffff", shape=shape, width=1)
        self.draw_marker_shape(x, y, radius, fill=color, outline=outline, shape=shape, width=2)
        if not self.is_dragging_globe:
            self.draw_text_with_outline(x + radius + 7, y - radius - 5, text=label, anchor="w", fill=color, font=("Segoe UI", 8, "bold"))

    def draw_map_globe(self):
        self.globe_canvas.configure(bg="#0b1e33")
        # Hide original white coastlines in Tex mode to prevent visual clutter/redundancy!
        if not self.show_texture_var.get():
            for segment in self.coastline_segments_drag:
                self.draw_polyline_segments(segment, "#cfd6d0", width=2)
                
        if self.show_boundaries_var.get():
            for segment in self.boundary_segments_drag:
                self.draw_polyline_segments(segment, "#8ab6a2", width=1)

    def _spawn_updatemap_process(self):
        if not hasattr(self, "updatemap_process") or self.updatemap_process is None:
            try:
                import sys
                import subprocess
                import os
                if getattr(sys, "frozen", False):
                    # Running inside PyInstaller compiled executable!
                    # Spawn the bundled updatemap.exe directly from the same folder!
                    updatemap_exe = os.path.join(os.path.dirname(sys.executable), "updatemap.exe")
                    if not os.path.exists(updatemap_exe):
                        updatemap_exe = os.path.join(os.path.dirname(sys.executable), "_internal", "updatemap.exe")
                    self.updatemap_process = subprocess.Popen([updatemap_exe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    # Running in development mode!
                    python_exe = sys.executable
                    updatemap_path = os.path.join(os.path.dirname(__file__), "updatemap.py")
                    self.updatemap_process = subprocess.Popen([python_exe, updatemap_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as pe:
                print("Error spawning updatemap process:", pe)

    def on_show_map_toggle(self):
        self.save_settings()
        if self.show_map_var.get():
            if not self.is_paused and not self.simulation_finished:
                self._spawn_updatemap_process()
        else:
            if hasattr(self, "updatemap_process") and self.updatemap_process is not None:
                try:
                    self.updatemap_process.terminate()
                except Exception:
                    pass
                self.updatemap_process = None

    def init_offscreen_plotter(self):
        try:
            import pyvista as pl
            pl.set_plot_theme('dark')
            # Initialize off-screen plotter with same width and height
            self.offscreen_plotter = pl.Plotter(off_screen=True, window_size=(self.globe_canvas_width, self.globe_canvas_height))
            self.offscreen_plotter.background_color = 'black'
            self.offscreen_plotter.enable_parallel_projection()
            
            # Create sphere with texture coordinates
            earth_mesh = pl.Sphere(radius=1.0, theta_resolution=60, phi_resolution=60, texture_coordinates=True)
            
            # Mathematically align PyVista's sphere axes perfectly with our Tkinter 3D ECEF coordinate system:
            # 1. Align North Pole (PyVista positive Z axis) to our polar Y axis by rotating -90 degrees around X axis
            earth_mesh.rotate_x(-90, inplace=True)
            # 2. Align Prime Meridian (PyVista positive X axis) with our ECEF longitude system by rotating 180 degrees around Y axis
            earth_mesh.rotate_y(180, inplace=True)
            
            # Look for local high-resolution offline_world_map.jpg texture to avoid internet downloads!
            script_dir = os.path.dirname(os.path.abspath(__file__))
            local_tex_path = os.path.join(script_dir, "offline_world_map.jpg")
            if not os.path.exists(local_tex_path):
                local_tex_path = os.path.join(os.path.dirname(script_dir), "offline_world_map.jpg")
                
            if os.path.exists(local_tex_path):
                try:
                    earth_texture = pl.read_texture(local_tex_path)
                except Exception:
                    earth_texture = pl.examples.load_globe_texture()
            else:
                earth_texture = pl.examples.load_globe_texture()
                
            self.offscreen_plotter.add_mesh(earth_mesh, texture=earth_texture, smooth_shading=True, name="earth")
        except Exception as e:
            print("Error initializing offscreen plotter:", e)
            self.offscreen_plotter = None

    def on_show_texture_toggle(self):
        self.save_settings()
        self.render_globe()

    def on_show_msl_lbl_toggle(self):
        self.save_settings()
        if hasattr(self, "impact_window") and self.impact_window is not None and self.impact_window.winfo_exists():
            try:
                self.impact_window.synchronize_states()
            except Exception:
                pass

    def draw_first_person_ground_view(self):
        cx = self.globe_canvas_width / 2
        cy = self.globe_canvas_height / 2
        
        # Ground line vertical coordinate
        y_ground = int(cy + 200)
        
        # Draw a beautiful, star-filled night sky (random static stars for background depth)
        import random
        # We can seed with a fixed number so the stars are stable and don't flicker on every frame
        random.seed(42)
        for _ in range(35):
            sx = random.randint(15, int(self.globe_canvas_width) - 15)
            sy = random.randint(15, y_ground - 15)
            self.globe_canvas.create_oval(sx, sy, sx + 1.5, sy + 1.5, fill="#ffffff", outline="")
            
        # Draw the solid Ground Block at the bottom (Earth's surface from first-person view)
        self.globe_canvas.create_rectangle(0, y_ground, self.globe_canvas_width, self.globe_canvas_height, fill="#121820", outline="#2e7d32", width=1.5)
        
        # Ground/Horizon base labeling
        self.draw_text_with_outline(cx, y_ground + 20, "LOCAL HORIZON BASELINE (SEA LEVEL)", fill="#81c784", font=("Segoe UI", 8, "bold"))
        self.draw_text_with_outline(cx, y_ground + 38, "THEATER SKY-WATCH OBSERVATION RADAR: ON-LINE", fill="#cfd8dc", font=("Segoe UI", 9, "bold"))

    def draw_tactical_hud(self):
        cx = self.globe_canvas_width / 2
        cy = self.globe_canvas_height / 2
        r = self.globe_radius_px
        
        # Draw concentric tactical range rings (semi-transparent green/cyan)
        hud_color = "#00e676"  # bright tactical green
        hud_dim = "#00701a"   # dim green
        
        # Outer ring
        self.globe_canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline=hud_color, width=1.5, dash=(6, 6))
        # Inner ring
        self.globe_canvas.create_oval(cx - r * 0.5, cy - r * 0.5, cx + r * 0.5, cy + r * 0.5, outline=hud_dim, width=1, dash=(3, 3))
        
        # Crosshair segments
        gap = 25
        # Left line
        self.globe_canvas.create_line(cx - r, cy, cx - gap, cy, fill=hud_color, width=1.2)
        # Right line
        self.globe_canvas.create_line(cx + gap, cy, cx + r, cy, fill=hud_color, width=1.2)
        # Top line
        self.globe_canvas.create_line(cx, cy - r, cx, cy - gap, fill=hud_color, width=1.2)
        # Bottom line
        self.globe_canvas.create_line(cx, cy + gap, cx, cy + r, fill=hud_color, width=1.2)
        
        # Center target reticle (tiny circle)
        self.globe_canvas.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, outline=hud_color, width=1.5)
        
        # Cardinal direction labels (N, E, S, W)
        self.draw_text_with_outline(cx, cy - r + 14, "N", fill=hud_color, font=("Segoe UI", 8, "bold"))
        self.draw_text_with_outline(cx + r - 14, cy, "E", fill=hud_color, font=("Segoe UI", 8, "bold"))
        self.draw_text_with_outline(cx, cy + r - 14, "S", fill=hud_color, font=("Segoe UI", 8, "bold"))
        self.draw_text_with_outline(cx - r + 14, cy, "W", fill=hud_color, font=("Segoe UI", 8, "bold"))
        
        # Decorative corners/brackets
        bracket_len = 16
        # Top-Left bracket
        self.globe_canvas.create_line(cx - r - 8, cy - r, cx - r - 8, cy - r - 8, fill=hud_color, width=1.5)
        self.globe_canvas.create_line(cx - r - 8, cy - r - 8, cx - r, cy - r - 8, fill=hud_color, width=1.5)
        # Top-Right bracket
        self.globe_canvas.create_line(cx + r + 8, cy - r, cx + r + 8, cy - r - 8, fill=hud_color, width=1.5)
        self.globe_canvas.create_line(cx + r + 8, cy - r - 8, cx + r, cy - r - 8, fill=hud_color, width=1.5)
        # Bottom-Left bracket
        self.globe_canvas.create_line(cx - r - 8, cy + r, cx - r - 8, cy + r + 8, fill=hud_color, width=1.5)
        self.globe_canvas.create_line(cx - r - 8, cy + r + 8, cx - r, cy + r + 8, fill=hud_color, width=1.5)
        # Bottom-Right bracket
        self.globe_canvas.create_line(cx + r + 8, cy + r, cx + r + 8, cy + r + 8, fill=hud_color, width=1.5)
        self.globe_canvas.create_line(cx + r + 8, cy + r + 8, cx + r, cy + r + 8, fill=hud_color, width=1.5)



    def draw_geographic_labels(self):
        is_ground = getattr(self, "render_is_ground", False)
        if not is_ground:
            if self.show_wireframe_var.get() or self.is_dragging_globe or self.globe_zoom < 1.35:
                return
            country_count = min(16, 6 + int((self.globe_zoom - 1.35) * 6))
            country_spacing = max(44, 62 - int((self.globe_zoom - 1.35) * 8))
            min_depth_limit = getattr(self, "render_min_depth", 0.02)
            min_depth = max(0.28, min_depth_limit)
        else:
            if self.show_wireframe_var.get() or self.is_dragging_globe:
                return
            country_count = 12
            country_spacing = 35
            min_depth = -0.05
            
        self.draw_label_set(self.country_labels, max_items=country_count, min_depth=min_depth, min_spacing=country_spacing, fill="#f2f4f8", font=("Segoe UI", 7, "bold"), y_offset=-6)

    def render_globe(self):
        mode = self.view_mode_var.get()
        if mode == "D":
            sat_pos = self.get_satellite_pos()
            geo = self.unit_to_lat_lon(sat_pos)
            if geo is not None:
                sat_lat, sat_lon = geo
                try:
                    sat_alt_km = float(self.view_d_alt_var.get())
                except ValueError:
                    sat_alt_km = 800.0
                self.updating_view_center_fields = True
                self.view_center_lat_var.set(f"{sat_lat:.4f}")
                self.view_center_lon_var.set(f"{sat_lon:.4f}")
                self.view_altitude_km_var.set(f"{sat_alt_km:.1f}")
                self.updating_view_center_fields = False
                
                # Center the camera's gaze dynamically under the satellite nadir footprint
                self.center_view_on(sat_lat, sat_lon)
                
                # Apply steerable camera yaw/pitch offsets dragged by the user in Mode D!
                self.view_yaw_deg = ((self.view_yaw_deg + self.sat_view_yaw_offset + 180.0) % 360.0) - 180.0
                self.view_pitch_deg = max(min(self.view_pitch_deg + self.sat_view_pitch_offset, 85.0), -85.0)

        cam_alt = self.get_view_altitude_km()
        
        # Ground View Camera Director: dynamically scale camera altitude to stay above peak missile altitude
        is_ground = cam_alt < 2200.0
        if is_ground:
            peak_alt = 0.0
            for msl in self.missiles:
                if len(msl.path) > 0:
                    for pt in msl.path:
                        norm = np.linalg.norm(pt)
                        alt = max((norm / EARTH_RADIUS - 1.0) * EARTH_RADIUS_KM, 0.0)
                        if alt > peak_alt:
                            peak_alt = alt
            if peak_alt > 0.1:
                # Set camera altitude to be safely above the peak missile altitude (with 200km margin!)
                target_alt = max(peak_alt + 200.0, 500.0)
                cam_alt = min(target_alt, 2000.0)
                self.updating_view_center_fields = True
                self.view_altitude_km_var.set(f"{cam_alt:.1f}")
                self.updating_view_center_fields = False

        self.render_cam_alt = cam_alt
        self.render_is_ground = is_ground
        if not is_ground:
            d = self.get_view_camera_distance()
            self.render_camera_distance = d
            if d <= 1.0001:
                self.render_limb_radius = self.globe_radius_px
                self.render_min_depth = -0.02
            else:
                r_ecef = math.sqrt(max(0.0, 1.0 - 1.0 / (d * d)))
                mode = self.view_mode_var.get()
                if mode == "A":
                    scale = d * d / (d * d - 1.0)
                    self.render_limb_radius = self.globe_radius_px * r_ecef * scale
                    self.render_min_depth = max(1.0 / d - 0.005, -0.99)
                elif mode == "B":
                    scale = d / (d * d - 1.0)
                    self.render_limb_radius = self.globe_radius_px * r_ecef * scale
                    self.render_min_depth = max(1.0 / d - 0.005, -0.99)
                elif mode == "D":
                    R_val = 1.0 + cam_alt / EARTH_RADIUS_KM
                    self.render_limb_radius = (self.globe_radius_px * 2.5) / math.sqrt(max(0.0001, R_val * R_val - 1.0))
                    self.render_min_depth = 0.01
                else: # Mode C
                    scale = 0.5 * d / (d - 1.0)
                    self.render_limb_radius = self.globe_radius_px * r_ecef * scale
                    self.render_min_depth = max(1.0 / d - 0.005, -0.99)
        else:
            self.render_camera_distance = 1.0
            self.render_limb_radius = self.globe_radius_px
            self.render_min_depth = -0.02
            
            # Compute Ground View camera properties (Perspective Camera)
            try:
                cam_lat = float(self.view_center_lat_var.get() or 0.0)
                cam_lon = float(self.view_center_lon_var.get() or 0.0)
            except ValueError:
                cam_lat, cam_lon = 0.0, 0.0

            self.cam_eye = self.lat_lon_to_unit(cam_lat, cam_lon) * (1.0 + cam_alt / EARTH_RADIUS_KM)
            self.cam_up = self.lat_lon_to_unit(cam_lat, cam_lon)

            # Find the tracking target position
            target_pos = None
            if self.msl_tracking_var.get():
                for msl in self.missiles:
                    if msl.active:
                        target_pos = msl.pos
                        break
                if target_pos is None:
                    for intcp in self.interceptors:
                        if intcp.active and not intcp.hit:
                            target_pos = intcp.pos
                            break
                if target_pos is None and len(self.missiles) > 0:
                    target_pos = self.missiles[0].pos

            if target_pos is not None:
                self.cam_center = self.simulation_vector_to_globe_point(target_pos)
            else:
                focus_msl = self.missiles[0] if len(self.missiles) > 0 else None
                if focus_msl is not None:
                    msl_start = self.simulation_vector_to_globe_point(focus_msl.path[0])
                    msl_target = self.simulation_vector_to_globe_point(focus_msl.target)
                    look_target = (msl_start + msl_target) / 2.0
                    self.cam_center = look_target / np.linalg.norm(look_target)
                else:
                    self.cam_center = self.lat_lon_to_unit(self.config.missile_target_lat, self.config.missile_target_lon)

            # Also update display HUD readouts (Yaw & Pitch)
            if target_pos is not None:
                # Compute local tracking readouts relative to observer
                eye = self.cam_eye
                up = self.cam_up
                theta = math.radians(cam_lon)
                east = np.array([-math.sin(theta), 0.0, -math.cos(theta)], dtype=float)
                east_norm = np.linalg.norm(east)
                if east_norm > 1e-9: east /= east_norm
                north = np.cross(up, east)
                north_norm = np.linalg.norm(north)
                if north_norm > 1e-9: north /= north_norm
                
                target_ecef = self.cam_center
                d_look = target_ecef - eye
                if np.linalg.norm(d_look) > 0.001:
                    look = d_look / np.linalg.norm(d_look)
                    pitch_val = np.dot(look, up)
                    pitch_val = max(min(pitch_val, 1.0), -1.0)
                    pitch_rad = math.asin(pitch_val)
                    
                    horizontal = look - pitch_val * up
                    h_norm = np.linalg.norm(horizontal)
                    if h_norm > 1e-9:
                        look_h = horizontal / h_norm
                        yaw_rad = math.atan2(np.dot(look_h, east), np.dot(look_h, north))
                    else:
                        yaw_rad = 0.0
                    
                    self.view_yaw_deg = ((math.degrees(yaw_rad) + 180.0) % 360.0) - 180.0
                    self.view_pitch_deg = max(min(math.degrees(pitch_rad), 85.0), -85.0)
                    self.view_yaw_var.set(f"{self.view_yaw_deg:.2f}")
                    self.view_pitch_var.set(f"{self.view_pitch_deg:.2f}")

        self.update_view_center_display()
        self.globe_canvas.delete("all")
        cam_alt = self.get_view_altitude_km()
        is_ground = cam_alt < 2200.0
        self.globe_canvas.configure(bg="#081018" if is_ground else ("#000000" if self.show_wireframe_var.get() else "#0b1e33"))
        pad = 18
        cx = self.globe_canvas_width / 2
        cy = self.globe_canvas_height / 2
        limb_radius = self.get_perspective_limb_radius()
        
        show_local_baseline = self.show_local_horizon_var.get() and (is_ground or mode == "D")
        
        if not show_local_baseline:
            # Draw textured globe background if Tex is checked
            if self.show_texture_var.get() and not is_ground:
                if self.offscreen_plotter is None:
                    self.init_offscreen_plotter()
                    
                if self.offscreen_plotter is not None:
                    try:
                        from PIL import Image, ImageTk
                        # Align camera eye position based on current view center
                        try:
                            cam_lat = float(self.view_center_lat_var.get() or 0.0)
                            cam_lon = float(self.view_center_lon_var.get() or 0.0)
                        except ValueError:
                            cam_lat, cam_lon = 0.0, 0.0
                            
                        cam_ecef = self.lat_lon_to_unit(cam_lat, cam_lon)
                        eye = cam_ecef * self.get_view_camera_distance()
                        
                        self.offscreen_plotter.camera.position = (eye[0], eye[1], eye[2])
                        self.offscreen_plotter.camera.focal_point = (0.0, 0.0, 0.0)
                        self.offscreen_plotter.camera.up = (0.0, 1.0, 0.0)
                        
                        # Set parallel scale dynamically to match the current limb_radius zoom size
                        if limb_radius > 0:
                            self.offscreen_plotter.camera.parallel_scale = self.globe_canvas_height / (2.0 * limb_radius)
                        
                        self.offscreen_plotter.render()
                        img = self.offscreen_plotter.screenshot()
                        
                        pil_img = Image.fromarray(img)
                        self.globe_bg_image = ImageTk.PhotoImage(pil_img)
                        self.globe_canvas.create_image(cx, cy, image=self.globe_bg_image)
                    except Exception as e:
                        print("Error rendering offscreen textured globe:", e)

            if not is_ground:
                # Set background fill to empty if wireframe or texture is checked
                bg_fill = "" if (self.show_wireframe_var.get() or self.show_texture_var.get()) else "#163f63"
                self.globe_canvas.create_oval(cx - limb_radius, cy - limb_radius, cx + limb_radius, cy + limb_radius, fill=bg_fill, outline="#70757f", width=2)
            if self.show_wireframe_var.get():
                self.draw_wireframe()
            else:
                self.draw_map_globe()
            self.draw_globe_guides()
            self.draw_geographic_labels()
            self.draw_scale_bar()
        else:
            self.draw_first_person_ground_view()
            self.draw_tactical_hud()
            
        if not is_ground and not show_local_baseline:
            self.draw_viewpoint_marker()

        # Draw all display-enabled satellites and their orbit paths
        if not is_ground or mode == "D":
            sats = self.load_satellites_list()
            primary_sat_pos = self.get_satellite_pos() # for single-reference contexts
            
            for sat_info in sats:
                if not sat_info.get("display", True):
                    continue
                    
                sat_pos_ecef = self.get_satellite_ecef(sat_info)
                sat_name = sat_info.get("name", "Sat-B")
                sat_alt_km = float(sat_info.get("altitude", 800.0))
                sat_r = 1.0 + sat_alt_km / EARTH_RADIUS_KM
                is_geosync = sat_info.get("geosync", False)
                inclination = float(sat_info.get("inclination", 45.0))

                # Color-coding based on Geosync vs. Standard Orbit
                if is_geosync:
                    orbit_color = "#00ff66" # Glowing Neon Green for Geosync belt
                    core_color = "#ff9100"  # Vibrant Orange core
                    panel_color = "#ff3d00" # High-contrast Red/Orange solar panels
                    text_color = "#00ff66"  # Neon Green text label
                else:
                    orbit_color = "#1e90ff" # Bright Blue for standard orbits
                    core_color = "#ffd700"  # Gold core
                    panel_color = "#00e5ff" # Cyan solar panels
                    text_color = "#1e90ff"  # Bright Blue text label

                # 1. Draw Orbit Ring (only for standard moving orbital satellites; hidden for stationary geosync)
                camera_distance = self.get_view_camera_distance()
                show_orbit = not is_geosync and ((mode == "D") or (camera_distance > 1.3 * sat_r))
                
                if show_orbit:
                    if sat_info.get("tle", False):
                        try:
                            from sgp4.api import Satrec, jday
                            import datetime
                            line1 = sat_info.get("tle_line1")
                            line2 = sat_info.get("tle_line2")
                            if not line1 or not line2:
                                if sat_info.get("geosync", False):
                                    line1 = "1 41866U 16071A   26265.81250000  .00000100  00000-0  00000-0 0  9999"
                                    line2 = "2 41866   0.0215  45.5200 0001250 180.2000 180.3000  1.00270000388219"
                                else:
                                    if sat_info.get("name") == "Sat-A1":
                                        line1 = "1 20580U 90037B   26265.81250000  .00000500  00000-0  11200-3 0  9999"
                                        line2 = "2 20580  28.4700 120.5000 0003500 180.2000 180.3000 15.12500000288219"
                                    elif sat_info.get("name") == "Sat-B2":
                                        line1 = "1 33591U 09005A   26265.81250000  .00000100  00000-0  77900-4 0  9998"
                                        line2 = "2 33591  99.1200 135.5000 0013500 240.2000 120.3000 14.12500000288219"
                                    else:
                                        line1 = "1 25544U 98067A   26265.80775463  .00015505  00000-0  27869-3 0  9997"
                                        line2 = "2 25544  51.6408 141.5209 0004546 221.7224 233.1550 15.49503461588219"
                            sat = Satrec.twoline2rv(line1, line2)
                            
                            start_time = datetime.datetime(2026, 9, 21, 12, 0, 0, tzinfo=datetime.timezone.utc)
                            # Extract starting sub-satellite point of the TLE at epoch
                            jd_epoch, fr_epoch = jday(start_time.year, start_time.month, start_time.day,
                                                      start_time.hour, start_time.minute, start_time.second)
                            err_epoch, pos_epoch, _ = sat.sgp4(jd_epoch, fr_epoch)
                            lat_tle, lon_tle = 0.0, 0.0
                            if err_epoch == 0:
                                p_surf_start = np.array([pos_epoch[0], pos_epoch[1], pos_epoch[2]], dtype=float)
                                p_surf_start /= np.linalg.norm(p_surf_start)
                                geo_start = self.unit_to_lat_lon(p_surf_start)
                                if geo_start is not None:
                                    lat_tle, lon_tle = geo_start

                            # Extract true orbital period from TLE (Line 2, characters 52 to 63 represent Mean Motion in revs/day)
                            try:
                                mean_motion_str = line2[52:63].strip()
                                mean_motion = float(mean_motion_str)
                                if mean_motion > 0:
                                    period_min = 1440.0 / mean_motion
                                else:
                                    period_min = 105.0
                            except Exception:
                                period_min = 1440.0 if sat_info.get("geosync", False) else 105.0
                            ring_pts = 121
                            orbit_pts = []
                            for i in range(ring_pts):
                                t_offset_sec = self.sim_elapsed_time * 30.0 + (i * period_min * 60.0 / (ring_pts - 1))
                                current_sim_time = start_time + datetime.timedelta(seconds=t_offset_sec)
                                jd, fr = jday(current_sim_time.year, current_sim_time.month, current_sim_time.day,
                                              current_sim_time.hour, current_sim_time.minute, current_sim_time.second)
                                error, pos_teme, vel = sat.sgp4(jd, fr)
                                if error == 0:
                                    # Convert TEME to ECEF by rotating Z-axis
                                    angle_rad = -((2.0 * math.pi) / 86164.0) * t_offset_sec
                                    cos_a = math.cos(angle_rad)
                                    sin_a = math.sin(angle_rad)
                                    x_ecef = pos_teme[0] * cos_a - pos_teme[1] * sin_a
                                    y_ecef = pos_teme[0] * sin_a + pos_teme[1] * cos_a
                                    z_ecef = pos_teme[2]
                                    
                                    pt_ecef = np.array([x_ecef, y_ecef, z_ecef], dtype=float)
                                    pt_norm = np.linalg.norm(pt_ecef)
                                    pt_ecef_unit = pt_ecef / pt_norm
                                    
                                    if sat_info.get("geosync", False):
                                        geo_prop = self.unit_to_lat_lon(pt_ecef_unit)
                                        if geo_prop is not None:
                                            lat_prop, lon_prop = geo_prop
                                            lat_user = float(sat_info.get("geolat", 0.0))
                                            lon_user = float(sat_info.get("geolon", 130.0))
                                            lat_shifted = lat_user + (lat_prop - lat_tle)
                                            lon_shifted = lon_user + (lon_prop - lon_tle)
                                            pt_ecef_unit = self.lat_lon_to_unit(lat_shifted, lon_shifted)
                                            
                                    pt = pt_ecef_unit
                                    pt_scaled = pt * sat_r
                                    
                                    # Project to canvas
                                    v_proj, px, py = self.project_to_canvas(pt_scaled)
                                    if mode == "D":
                                        is_visible = not self.is_ecef_occluded_by_earth(primary_sat_pos, pt_scaled)
                                    else:
                                        is_visible = not self.is_occluded_by_earth(v_proj, camera_distance)
                                        
                                    if is_visible:
                                        orbit_pts.append((px, py))
                                        if i % 12 == 0:
                                            norm = np.linalg.norm(pt)
                                            pt_surf = pt / norm if norm > 1e-9 else pt
                                            self.draw_clipped_line(pt, pt_surf, color=orbit_color, width=1, dash=(1, 5))
                                    else:
                                        if len(orbit_pts) >= 2:
                                            flat_pts = [c for p in orbit_pts for c in p]
                                            self.globe_canvas.create_line(*flat_pts, fill=orbit_color, width=1.5, dash=(3, 5))
                                        orbit_pts = []
                            if len(orbit_pts) >= 2:
                                flat_pts = [c for p in orbit_pts for c in p]
                                self.globe_canvas.create_line(*flat_pts, fill=orbit_color, width=1.5, dash=(3, 5))
                        except Exception as e:
                            print("Error rendering TLE orbit ring:", e)
                    else:
                        u = self.lat_lon_to_unit(0.0, 0.0)
                        e = np.array([u[2], 0.0, -u[0]], dtype=float)
                        e_norm = np.linalg.norm(e)
                        if e_norm > 1e-9:
                            e /= e_norm
                        else:
                            e = np.array([0.0, 0.0, -1.0], dtype=float)
                        n = np.array([0.0, 1.0, 0.0], dtype=float)

                        inc_rad = math.radians(inclination)
                        v = math.cos(inc_rad) * e + math.sin(inc_rad) * n
                        
                        ring_pts = 181 if mode in {"B", "C"} else 73
                        orbit_pts = []
                        for i in range(ring_pts):
                            ang = (i / float(ring_pts - 1)) * 2.0 * math.pi
                            pt = (math.cos(ang) * u + math.sin(ang) * v) * sat_r
                            v_proj, px, py = self.project_to_canvas(pt)
                            
                            if mode == "D":
                                is_visible = not self.is_ecef_occluded_by_earth(primary_sat_pos, pt)
                            else:
                                is_visible = not self.is_occluded_by_earth(v_proj, camera_distance)
                                
                            if is_visible:
                                orbit_pts.append((px, py))
                                if i % 12 == 0:
                                    norm = np.linalg.norm(pt)
                                    pt_surf = pt / norm if norm > 1e-9 else pt
                                    self.draw_clipped_line(pt, pt_surf, color=orbit_color, width=1, dash=(1, 5))
                            else:
                                if len(orbit_pts) >= 2:
                                    flat_pts = [c for p in orbit_pts for c in p]
                                    self.globe_canvas.create_line(*flat_pts, fill=orbit_color, width=1.5, dash=(3, 5))
                                orbit_pts = []
                        if len(orbit_pts) >= 2:
                            flat_pts = [c for p in orbit_pts for c in p]
                            self.globe_canvas.create_line(*flat_pts, fill=orbit_color, width=1.5, dash=(3, 5))
                    
                # 2. Draw Satellite Dot
                if mode != "D" or sat_name != getattr(self, "current_tracking_sat_name", sats[0]["name"]):
                    try:
                        cam_lat = float(self.view_center_lat_var.get() or 0.0)
                        cam_lon = float(self.view_center_lon_var.get() or 0.0)
                    except ValueError:
                        cam_lat, cam_lon = 0.0, 0.0
                    cam_ecef = self.lat_lon_to_unit(cam_lat, cam_lon)
                    camera_pos = cam_ecef * self.get_view_camera_distance()
                    
                    is_occluded = self.is_ecef_occluded_by_earth(camera_pos, sat_pos_ecef)
                    view, sat_x, sat_y = self.project_to_canvas(sat_pos_ecef)
                    if not is_occluded:
                        self.globe_canvas.create_oval(sat_x - 4, sat_y - 4, sat_x + 4, sat_y + 4, fill=core_color, outline="#ffffff", width=1)
                        self.globe_canvas.create_rectangle(sat_x - 12, sat_y - 1.5, sat_x - 4, sat_y + 1.5, fill=panel_color, outline=orbit_color, width=1)
                        self.globe_canvas.create_rectangle(sat_x + 4, sat_y - 1.5, sat_x + 12, sat_y + 1.5, fill=panel_color, outline=orbit_color, width=1)
                        if not self.is_dragging_globe:
                            self.draw_text_with_outline(sat_x + 14, sat_y - 6, text=sat_name, anchor="w", fill=text_color, font=("Segoe UI", 8, "bold"))
                    else:
                        self.globe_canvas.create_oval(sat_x - 3, sat_y - 3, sat_x + 3, sat_y + 3, fill="#37474f", outline="#78909c", width=1)
                        self.globe_canvas.create_rectangle(sat_x - 9, sat_y - 1, sat_x - 3, sat_y + 1, fill="#455a64", outline="#78909c", width=1)
                        self.globe_canvas.create_rectangle(sat_x + 3, sat_y - 1, sat_x + 9, sat_y + 1, fill="#455a64", outline="#78909c", width=1)
                        if not self.is_dragging_globe:
                            self.draw_text_with_outline(sat_x + 11, sat_y - 5, text=f"{sat_name} (Back)", anchor="w", fill="#78909c", font=("Segoe UI", 7, "italic"))

                # 3. Draw Nadir Line & Still Ground Nadir Footprint Icon
                sat_pos_norm = np.linalg.norm(sat_pos_ecef)
                if sat_pos_norm > 1e-9:
                    sat_pos_surf = sat_pos_ecef / sat_pos_norm
                    self.draw_clipped_line(sat_pos_ecef, sat_pos_surf, color="#ff00ff", width=2.5)
                    
                    # Draw a gorgeous, stationary ground nadir footprint dot directly on the surface of the globe!
                    try:
                        cam_lat = float(self.view_center_lat_var.get() or 0.0)
                        cam_lon = float(self.view_center_lon_var.get() or 0.0)
                    except ValueError:
                        cam_lat, cam_lon = 0.0, 0.0
                    cam_ecef = self.lat_lon_to_unit(cam_lat, cam_lon)
                    camera_pos = cam_ecef * self.get_view_camera_distance()
                    
                    is_surf_occluded = self.is_ecef_occluded_by_earth(camera_pos, sat_pos_surf)
                    view_surf, surf_x, surf_y = self.project_to_canvas(sat_pos_surf)
                    if not is_surf_occluded:
                        # Stationary footprint marker matching the orbit's color
                        self.globe_canvas.create_oval(surf_x - 3, surf_y - 3, surf_x + 3, surf_y + 3, fill=orbit_color, outline="#ffffff", width=1)
                        if not self.is_dragging_globe:
                            self.draw_text_with_outline(surf_x + 8, surf_y - 5, text=f"{sat_name} Nadir", anchor="w", fill=orbit_color, font=("Segoe UI", 7, "bold"))


        # Draw all configured interceptor launch sites
        if hasattr(self, "interceptor_groups") and self.interceptor_groups:
            for group_name, pairs in self.interceptor_groups.items():
                for pair in pairs:
                    i = pair["id"]
                    has_launched = False
                    for intcp in self.interceptors:
                        if intcp.label == f"{group_name}-Int{i}" and len(intcp.path) > 1:
                            has_launched = True
                            break
                    if not has_launched:
                        self.draw_marker(pair["start_lat"], pair["start_lon"], 0.0, "#00ff00", f"{group_name}-Int{i}", shape="triangle", halo_color="#ffffff", halo_radius=3)
        else:
            if not self.interceptor_launched:
                self.draw_marker(self.config.interceptor_start_lat, self.config.interceptor_start_lon, self.config.interceptor_start_altitude_km, "#00ff00", "Int", shape="triangle", halo_color="#ffffff", halo_radius=3)

        # Draw all missiles, targets, and interceptors with labels
        for idx, msl in enumerate(self.missiles):
            intcp = self.interceptors[idx]
            
            # Start/launch marker (only show if not launched yet or at start of path)
            if len(msl.path) <= 1:
                start_pt = self.simulation_vector_to_globe_point(msl.path[0])
                start_geo = self.unit_to_lat_lon(start_pt)
                if start_geo:
                    self.draw_marker(start_geo[0], start_geo[1], 0.0, "#ff0000", f"{msl.label}-L", shape="circle", halo_color="#ffffff", halo_radius=3)
            
            # Target marker (hide if it has been hit and reached_target is True)
            if not getattr(msl, "reached_target", False):
                tgt_pt = self.simulation_vector_to_globe_point(msl.target)
                tgt_geo = self.unit_to_lat_lon(tgt_pt)
                if tgt_geo:
                    self.draw_marker(tgt_geo[0], tgt_geo[1], 0.0, "#ffd166", msl.target_label, shape="diamond", halo_color="#ffffff", halo_radius=3)
            
            # Flight paths
            msl_project = getattr(msl, "project_to_ground", False)
            msl_height = getattr(msl, "height_line", True)
            int_project = getattr(intcp, "project_to_ground", False)
            int_height = getattr(intcp, "height_line", True)
            
            if self.show_missile_path_var.get():
                msl_w = getattr(self, "msl_path_size", 3.0)
                self.draw_simulation_path(msl.path, "#ff0000", width=msl_w, project_to_ground=msl_project, show_height_line=msl_height)
            if self.show_interceptor_path_var.get() and len(intcp.path) > 1:
                int_w = getattr(self, "int_path_size", 3.0)
                self.draw_simulation_path(intcp.path, "#00ff00", width=int_w, project_to_ground=int_project, show_height_line=int_height)
            
            # Active in-flight vectors (hidden per user request)
            # if len(msl.path) > 1 and msl.active:
            #     msl_rad = max(4.0, getattr(self, "msl_path_size", 3.0) * 2.33)
            #     self.draw_simulation_vector_marker(msl.pos, "#ff0000", msl.label, "circle", radius=msl_rad)
            # if intcp.launched and intcp.active:
            #     int_rad = max(4.0, getattr(self, "int_path_size", 3.0) * 2.33)
            #     self.draw_simulation_vector_marker(intcp.pos, "#00ff00", intcp.label, "triangle", radius=int_rad)
                
        # Draw active and permanent static explosions
        for exp in self.explosions:
            elapsed = self.sim_elapsed_time - exp["start_time"]
            duration = exp["duration"]
            is_active = elapsed < duration
            
            point = self.simulation_vector_to_globe_point(exp["pos"])
            view, x, y = self.project_to_canvas(point)
            min_depth = getattr(self, "render_min_depth", 0.02)
            if view[2] >= min_depth:
                exp_type = exp.get("type", "intercept")
                
                if is_active:
                    ratio = elapsed / duration
                    rad_base = int(2.0 + ratio * 7.0) # slightly smaller explosion (max 9px)
                    rad = max(int(rad_base * getattr(self, "globe_zoom", 1.0)), 2) # scale proportionally to zoom ratio!
                    
                    if exp_type == "intercept":
                        # Cyan / Electric Blue explosion burst for interception success
                        self.draw_marker_shape(x, y, rad + 2, fill="", outline="#1e90ff", shape="cross", width=2)
                        self.draw_marker_shape(x, y, rad, fill="", outline="#00bfff", shape="diamond", width=1.5)
                        self.draw_marker_shape(x, y, int(rad * 0.6), fill="#7be0d6", outline="#7be0d6", shape="circle", width=1)
                        self.draw_marker_shape(x, y, int(rad * 0.3) + 1, fill="#ffffff", outline="#ffffff", shape="circle", width=1)
                        if not self.is_dragging_globe and ratio < 0.5:
                            self.draw_text_with_outline(x + rad + 4, y - 8, text="INTERCEPT!", anchor="w", fill="#00bfff", font=("Segoe UI", 10, "bold"))
                    else:
                        # Orange / Red explosion burst for ground strike
                        self.draw_marker_shape(x, y, rad + 2, fill="", outline="#ff4d4d", shape="cross", width=2)
                        self.draw_marker_shape(x, y, rad, fill="", outline="#ff4d4d", shape="diamond", width=1.5)
                        self.draw_marker_shape(x, y, int(rad * 0.6), fill="#ff9f43", outline="#ff9f43", shape="circle", width=1)
                        self.draw_marker_shape(x, y, int(rad * 0.3) + 1, fill="#ffd700", outline="#ffffff", shape="circle", width=1)
                        if not self.is_dragging_globe and ratio < 0.5:
                            self.draw_text_with_outline(x + rad + 4, y - 8, text="BOOM!", anchor="w", fill="#ff4d4d", font=("Segoe UI", 10, "bold"))
                else:
                    # Keep the simplified static explosion icon on the window
                    rad_base = 9
                    rad = max(int(rad_base * getattr(self, "globe_zoom", 1.0)), 2) # scale proportionally to zoom ratio!
                    if exp_type == "intercept":
                        # Cyan / Electric Blue explosion burst
                        self.draw_marker_shape(x, y, rad + 2, fill="", outline="#1e90ff", shape="cross", width=2)
                        self.draw_marker_shape(x, y, rad, fill="", outline="#00bfff", shape="diamond", width=1.5)
                        self.draw_marker_shape(x, y, int(rad * 0.6), fill="#7be0d6", outline="#7be0d6", shape="circle", width=1)
                        self.draw_marker_shape(x, y, int(rad * 0.3) + 1, fill="#ffffff", outline="#ffffff", shape="circle", width=1)
                    else:
                        # Orange / Red explosion burst for ground strike
                        self.draw_marker_shape(x, y, rad + 2, fill="", outline="#ff4d4d", shape="cross", width=2)
                        self.draw_marker_shape(x, y, rad, fill="", outline="#ff4d4d", shape="diamond", width=1.5)
                        self.draw_marker_shape(x, y, int(rad * 0.6), fill="#ff9f43", outline="#ff9f43", shape="circle", width=1)
                        self.draw_marker_shape(x, y, int(rad * 0.3) + 1, fill="#ffd700", outline="#ffffff", shape="circle", width=1)
        if self.show_status_var.get():
            active = "Auto Intcp" if self.config.auto_launch_interceptor else ("Launched" if self.interceptor_launched else "Manual")
            self.globe_canvas.create_text(pad, pad, text=f"Simulation mode: {active}", anchor="nw", fill="#d9e1e8", font=("Segoe UI", 9, "bold"))
            self.globe_canvas.create_text(pad, pad + 22, text="Drag rotates | Double-click centers | Wheel zooms | Space/button launches interceptor", anchor="nw", fill="#93a4b1", font=("Segoe UI", 8))
            self.globe_canvas.create_text(pad, pad + 40, text="Pause/Play and Replay controls are below the globe", anchor="nw", fill="#93a4b1", font=("Segoe UI", 8))
            self.globe_canvas.create_text(pad, pad + 58, text=f"Build: sim-{GUI_BUILD_TAG}", anchor="nw", fill="#6fb3ff", font=("Segoe UI", 8, "bold"))
            self.globe_canvas.create_text(pad, pad + 76, text=f"Time Elapsed: {self.sim_elapsed_time:.1f}s", anchor="nw", fill="#80cbc4", font=("Segoe UI", 9, "bold"))
            active_msls = [m for m in self.missiles if m.active]
            if active_msls:
                status_lines = []
                for msl in active_msls[:2]:
                    geo_alt = self.simulation_vector_to_geo_altitude(msl.pos)
                    if geo_alt is not None:
                        lat, lon, alt = geo_alt
                        status_lines.append(f"{msl.label}: Lat {lat:.1f}°, Lon {lon:.1f}°, Alt {alt:.1f} km")
                if len(active_msls) > 2:
                    status_lines.append(f"... and {len(active_msls) - 2} more")
                missile_status = " | ".join(status_lines)
            else:
                missile_status = "Missiles: All Offline/Terminated"
            self.globe_canvas.create_text(pad, pad + 96, text=missile_status, anchor="nw", fill="#ff0000", font=("Segoe UI", 9, "bold"))

            active_intcps = [i for i in self.interceptors if i.active and not i.hit]
            if active_intcps:
                status_lines = []
                for intcp in active_intcps[:2]:
                    geo_alt = self.simulation_vector_to_geo_altitude(intcp.pos)
                    if geo_alt is not None:
                        lat, lon, alt = geo_alt
                        status_lines.append(f"{intcp.label}: Lat {lat:.1f}°, Lon {lon:.1f}°, Alt {alt:.1f} km")
                if len(active_intcps) > 2:
                    status_lines.append(f"... and {len(active_intcps) - 2} more")
                interceptor_status = " | ".join(status_lines)
            else:
                interceptor_status = "Interceptor: All Offline/Not Launched"
            self.globe_canvas.create_text(pad, pad + 116, text=interceptor_status, anchor="nw", fill="#00ff00", font=("Segoe UI", 9, "bold"))
            
            # Satellite Status (Primary Active Satellite)
            sats = self.load_satellites_list()
            primary_sat = None
            for s in sats:
                if s.get("display", True):
                    primary_sat = s
                    break
            if primary_sat is None:
                primary_sat = sats[0]
                
            sat_name = primary_sat.get("name", "Sat-B")
            sat_alt_km = float(primary_sat.get("altitude", 800.0))
            is_geosync = primary_sat.get("geosync", False)
            
            sat_pos_ecef = self.get_satellite_ecef(primary_sat)
            geo = self.unit_to_lat_lon(sat_pos_ecef)
            sat_status = f"{sat_name}: Offline"
            if geo is not None:
                sat_lat, sat_lon = geo
                if is_geosync:
                    sat_status = f"{sat_name} (Geosync): Lat {sat_lat:.2f}°, Lon {sat_lon:.2f}°, Alt {sat_alt_km:.1f} km | V: [0.00, 0.00, 0.00] km/s"
                else:
                    orbit_period = float(primary_sat.get("period", 120.0))
                    inclination = float(primary_sat.get("inclination", 45.0))
                    phase = float(primary_sat.get("phase", 0.0))
                        
                    sat_r_km = EARTH_RADIUS_KM + sat_alt_km
                    v_mag = 2.0 * math.pi * sat_r_km / orbit_period  # km/s
                    
                    u = self.lat_lon_to_unit(0.0, 0.0)
                    e = np.array([u[2], 0.0, -u[0]], dtype=float)
                    e_norm = np.linalg.norm(e)
                    if e_norm > 1e-9:
                        e /= e_norm
                    else:
                        e = np.array([0.0, 0.0, -1.0], dtype=float)
                    n = np.array([0.0, 1.0, 0.0], dtype=float)
                    
                    inc_rad = math.radians(inclination)
                    v = math.cos(inc_rad) * e + math.sin(inc_rad) * n
                    
                    angle = math.radians(phase) + (self.sim_elapsed_time / orbit_period) * 2.0 * math.pi
                    tangent = -math.sin(angle) * u + math.cos(angle) * v
                    tangent_norm = np.linalg.norm(tangent)
                    if tangent_norm > 1e-9:
                        tangent /= tangent_norm
                    
                    vx, vy, vz = tangent * v_mag
                    sat_status = f"{sat_name} (Orbital): Lat {sat_lat:.2f}°, Lon {sat_lon:.2f}°, Alt {sat_alt_km:.1f} km | V: [{vx:.2f}, {vy:.2f}, {vz:.2f}] km/s"
            self.globe_canvas.create_text(pad, pad + 136, text=sat_status, anchor="nw", fill="#1e90ff", font=("Segoe UI", 9, "bold"))
            
        # Push the raw simulation state to the satellite live view queue if active
        if hasattr(self, "sat_live_view_window") and self.sat_live_view_window is not None and self.sat_live_view_window.winfo_exists():
            state = {
                "time": self.sim_elapsed_time,
                "tracking_algorithm": getattr(self.config, "tracking_algorithm", "EKF"),
                "mp_mode": getattr(self.config, "mp_mode", False),
                "sats": [
                    {
                        "name": s.get("name"),
                        "pos": self.get_satellite_ecef(s),
                        "geosync": s.get("geosync", False),
                        "altitude": float(s.get("altitude", 800.0)),
                        "period": float(s.get("period", 120.0)),
                        "inclination": float(s.get("inclination", 45.0)),
                        "phase": float(s.get("phase", 0.0)),
                        "noise": float(s.get("noise", 0.0))
                    }
                    for s in self.load_satellites_list() if s.get("display", True)
                ],
                "threats": [
                    {
                        "name": getattr(t, "label", ""),
                        "pos": np.copy(t.pos) if hasattr(t, "pos") else None,
                        "active": t.active,
                        "launched": getattr(t, "launched", True),
                        "hit": getattr(t, "hit", False)
                    }
                    for t in (self.missiles + self.interceptors)
                ]
            }
            try:
                # Keep only the latest frame in queue to save CPU/memory
                if self.sat_live_view_queue.full():
                    self.sat_live_view_queue.get_nowait()
                self.sat_live_view_queue.put_nowait(state)
            except Exception:
                pass
            
        # After drawing all elements, capture a frame if recording is active!
        if getattr(self, "recording_state", "inactive") == "recording" and getattr(self, "video_writer", None) is not None:
            self.capture_recording_frame()

    def get_simulation_step_multiplier(self):
        return min(max(int(math.ceil(self.globe_zoom * 2.0)), 1), 8)

    def step_simulation(self):
        self.after_job = None
        if self.closed or self.is_paused or self.simulation_finished:
            return
        try:
            spd_vis = float(self.spd_vis_ratio_var.get() or 1.0)
            self.config.spd_vis_ratio = max(spd_vis, 1.0)
        except ValueError:
            pass
        real_elapsed = time.time() - self.real_start_time
        target_sim_time = self.real_accumulated_time + real_elapsed * self.config.spd_vis_ratio
        needed_steps = int((target_sim_time - self.sim_elapsed_time) / TIME_STEP)
        if needed_steps <= 0:
            self.schedule_step()
            return
        
        required_steps = int(self.config.interceptor_delay_sec / TIME_STEP)
        for _ in range(needed_steps):
            # Activate queued missiles based on clock
            for msl in self.missiles:
                if not msl.launched and self.sim_elapsed_time >= getattr(msl, "launch_time", 0.0):
                    msl.launched = True
                    msl.active = True

            # Check auto launch for each individual missile
            for idx, msl in enumerate(self.missiles):
                intcp = self.interceptors[idx]
                if self.config.auto_launch_interceptor and msl.active and self.sim_elapsed_time >= getattr(intcp, "launch_time", required_steps * TIME_STEP) and not intcp.launched:
                    intcp.launch()
                    intcp.launched = True
                    self.interceptor_launched = True
            
            # Update all active missiles and interceptors
            for idx, msl in enumerate(self.missiles):
                intcp = self.interceptors[idx]
                if msl.active:
                    hit_tgt = msl.update()
                    if hit_tgt:
                        msl.pos = np.copy(msl.target)
                        intcp.active = False
                        intcp.vel[:] = 0.0
                        self.set_status(f"Status: {msl.label} hit the target. Intercept failed.", "#ff8a80")
                        
                        # Dynamically scale explosion duration to equal 2.5 real-world seconds
                        try:
                            spd_vis = float(self.spd_vis_ratio_var.get() or 1.0)
                        except ValueError:
                            spd_vis = 1.0
                        dur = 2.5 * max(spd_vis, 1.0)
                        
                        self.explosions.append({
                            "pos": np.copy(msl.target),
                            "start_time": self.sim_elapsed_time,
                            "duration": dur,
                            "type": "ground_strike"
                        })
                if intcp.launched and msl.active:
                    intcp.update(msl.pos)
                    if intcp.hit:
                        intcp.pos = np.copy(msl.pos)
                        msl.active = False
                        self.set_status(f"Status: {intcp.label} intercept successful!", "#80cbc4")
                        
                        # Dynamically scale explosion duration to equal 2.5 real-world seconds
                        try:
                            spd_vis = float(self.spd_vis_ratio_var.get() or 1.0)
                        except ValueError:
                            spd_vis = 1.0
                        dur = 2.5 * max(spd_vis, 1.0)
                        
                        self.explosions.append({
                            "pos": np.copy(msl.pos),
                            "start_time": self.sim_elapsed_time,
                            "duration": dur,
                            "type": "intercept"
                        })
            
            # Increment simulation elapsed time step-by-step
            self.sim_elapsed_time += TIME_STEP
        
        any_active_missile = any(msl.active for msl in self.missiles)
        any_unlaunched_intcp = any(not intcp.launched and msl.active for idx, msl in enumerate(self.missiles) for intcp in [self.interceptors[idx]])
        
        if not self.config.auto_launch_interceptor and any_unlaunched_intcp and any_active_missile:
            self.set_status("Status: Manual launch ready. Press the button or Space to launch interceptors.", "#ffd166")
            
        self.render_globe()
        any_playing_explosion = any(self.sim_elapsed_time - exp["start_time"] < exp["duration"] for exp in self.explosions)
        self.simulation_finished = (not any_active_missile) and (not any_playing_explosion)
        if self.simulation_finished:
            if getattr(self, "recording_state", "inactive") == "recording":
                self.stop_recording()
        self.refresh_control_states()
        self.schedule_step()

    def schedule_step(self):
        if self.closed or self.is_paused or self.simulation_finished or self.after_job is not None:
            return
        self.after_job = self.root.after(33, self.step_simulation)

    def is_ecef_occluded_by_earth(self, p1, p2):
        d_vec = p2 - p1
        a = np.dot(d_vec, d_vec)
        if a < 1e-9:
            return False
        b = 2.0 * np.dot(p1, d_vec)
        c = np.dot(p1, p1) - 1.0
        disc = b * b - 4.0 * a * c
        if disc >= 0.0:
            t = -b / (2.0 * a)
            if 0.0 <= t <= 1.0:
                val = a * t * t + b * t + c
                if val < -0.001:
                    return True
        return False

    def on_close(self):
        self.closed = True
        self.close_simulation_control_window()
        self.save_settings()
        
        # Stop separate sat live view window if active
        if hasattr(self, "sat_live_view_window") and self.sat_live_view_window is not None:
            try:
                if self.sat_live_view_window.winfo_exists():
                    self.sat_live_view_window.destroy()
            except Exception:
                pass
            self.sat_live_view_window = None
        
        # Stop separate impact window if active
        if hasattr(self, "impact_window") and self.impact_window is not None:
            try:
                if self.impact_window.winfo_exists():
                    if hasattr(self.impact_window, "on_close"):
                        self.impact_window.on_close()
                    else:
                        self.impact_window.destroy()
            except Exception:
                pass
            self.impact_window = None
            
        # Stop updatemap process if active
        if hasattr(self, "updatemap_process") and self.updatemap_process is not None:
            try:
                self.updatemap_process.terminate()
            except Exception:
                pass
            self.updatemap_process = None

        # Stop 3D plotter process if active
        if hasattr(self, "plotter3d_process") and self.plotter3d_process is not None:
            try:
                self.plotter3d_process.terminate()
            except Exception:
                pass
            self.plotter3d_process = None
            
        # Stop manual WinRec if active
        if getattr(self, "winrec_state", "inactive") == "recording":
            self.stop_winrec()
            
        if self.after_job is not None:
            self.root.after_cancel(self.after_job)
            self.after_job = None
        if self.drag_render_job is not None:
            self.root.after_cancel(self.drag_render_job)
            self.drag_render_job = None
        self.root.destroy()
        if self.on_close_callback is not None:
            self.on_close_callback()


class ScreenAreaSelector:
    def __init__(self, parent, callback):
        self.parent = parent
        self.callback = callback
        self.selector_win = tk.Toplevel(parent)
        self.selector_win.title("Select Recording Area")
        self.selector_win.attributes("-alpha", 0.3)  # semi-transparent overlay
        self.selector_win.attributes("-fullscreen", True)
        self.selector_win.attributes("-topmost", True)
        self.selector_win.overrideredirect(True)
        self.selector_win.configure(bg="#000000", cursor="cross")
        
        self.canvas = tk.Canvas(self.selector_win, cursor="cross", bg="#000000", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.selector_win.bind("<Escape>", lambda e: self.selector_win.destroy())
        
    def on_press(self, event):
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.rect_id = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="#00e676", width=2)
        
    def on_drag(self, event):
        if self.rect_id:
            cur_x = event.x_root
            cur_y = event.y_root
            self.canvas.coords(self.rect_id, self.start_x, self.start_y, cur_x, cur_y)
            
    def on_release(self, event):
        end_x = event.x_root
        end_y = event.y_root
        self.selector_win.destroy()
        
        # Calculate bounding box (handling negative drag direction)
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)
        
        w = x2 - x1
        h = y2 - y1
        if w > 10 and h > 10:
            self.callback((x1, y1, x2, y2))


class SatLiveViewWindow(tk.Toplevel):
    def __init__(self, parent, sim_window):
        super().__init__(parent)
        self.title("Satellite Live View Feed")
        self.configure(bg="#0c0f1d")
        self.sim_window = sim_window
        
        # Load last window size/position or default to 1180x480 next to executable if compiled
        import sys
        if getattr(sys, 'frozen', False):
            self.settings_file = os.path.join(os.path.dirname(sys.executable), "sat_live_view_settings.json")
        else:
            self.settings_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sat_live_view_settings.json")
        self.restore_window_size()
        
        # Force reload from settings file on startup to synchronize mp_mode instantly!
        self.sim_window.reload_parameters_from_gui()
        
        # Grid variables cache to update dynamically
        self.cell_labels = {} # key: (threat_name, sat_name, coord_type) -> label widget
        self.time_lbl = None
        self.build_ui()
        
        # Thread-safe data structures for background calculations
        import threading
        self.latest_ui_data = None
        self.data_lock = threading.Lock()
        
        # If MP (Multi-Process) mode is checked, start background Process 2 and TCP Server socket!
        self.mp_process = None
        self.server_socket = None
        self.client_socket = None
        
        if getattr(self.sim_window.config, "mp_mode", False):
            import subprocess
            import sys
            import socket
            try:
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.server_socket.bind(('127.0.0.1', 45915))
                self.server_socket.listen(1)
                
                # Launch Process 2 in background headless socket mode
                script_dir = os.path.dirname(os.path.abspath(__file__))
                multitest_path = os.path.join(script_dir, "multitest.py")
                
                # Resolve the correct execution path depending on whether we are compiled or in dev!
                if getattr(sys, "frozen", False):
                    # In compiled standalone EXE mode, we spawn multitest.exe directly!
                    multitest_exe = os.path.join(os.path.dirname(sys.executable), "multitest.exe")
                    if not os.path.exists(multitest_exe):
                        multitest_exe = os.path.join(os.path.dirname(sys.executable), "_internal", "multitest.exe")
                    self.mp_process = subprocess.Popen([multitest_exe, "--socket-mode"])
                else:
                    # Natively running in Python development environment
                    python_exe = sys.executable
                    self.mp_process = subprocess.Popen([python_exe, multitest_path, "--socket-mode"])
                
                # Accept connection with a timeout
                self.server_socket.settimeout(3.0)
                self.client_socket, addr = self.server_socket.accept()
                self.client_socket.setblocking(True)
                print("[MP INFO] Process 2 (multitest.py) connected successfully via Winsock.")
            except Exception as e:
                print("[MP ERROR] Failed to start Winsock multi-processing mode:", e)
                if self.client_socket: self.client_socket.close()
                if self.server_socket: self.server_socket.close()
                self.client_socket = None
                self.server_socket = None
        
        # Spawn high-performance background calculation thread!
        self.worker_thread = threading.Thread(target=self.bg_worker_loop, daemon=True)
        self.worker_thread.start()
        
        # Start high-performance, low-priority queue polling loop (250ms interval)
        self.poll_queue_loop()

    def restore_window_size(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r") as f:
                    data = json.load(f)
                w = int(data.get("width", 1180))
                h = int(data.get("height", 480))
                x = int(data.get("x", 100))
                y = int(data.get("y", 100))
                if x > -15000 and y > -15000:
                    self.geometry(f"{w}x{h}+{x}+{y}")
                else:
                    self.geometry(f"{w}x{h}")
            except Exception:
                self.geometry("1180x480")
        else:
            self.geometry("1180x480")

    def save_window_size(self):
        try:
            self.update_idletasks()
            geom = self.geometry()
            match = re.match(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", geom)
            if match:
                w, h, x, y = match.groups()
                if int(x) > -15000 and int(y) > -15000:
                    with open(self.settings_file, "w") as f:
                        json.dump({"width": int(w), "height": int(h), "x": int(x), "y": int(y)}, f, indent=4)
        except Exception as e:
            print("Error saving sat live view window size:", e)

    def destroy(self):
        # Save window bounds on exit
        self.save_window_size()
        
        # Clean up background Process 2 and close sockets cleanly
        if hasattr(self, "mp_process") and self.mp_process is not None:
            try:
                self.mp_process.terminate()
                self.mp_process.wait(timeout=1.0)
            except Exception:
                pass
        if hasattr(self, "client_socket") and self.client_socket is not None:
            try:
                self.client_socket.close()
            except Exception:
                pass
        if hasattr(self, "server_socket") and self.server_socket is not None:
            try:
                self.server_socket.close()
            except Exception:
                pass
        super().destroy()

    def build_ui(self):
        # 1. Header Banner
        header_frm = tk.Frame(self, bg="#ffd700", pady=6)
        header_frm.pack(fill="x")
        
        header_lbl = tk.Label(
            header_frm, 
            text="📡 SATELLITE MULTI-TARGET LIVE TRACKING FEED 📡", 
            font=("Segoe UI", 11, "bold"), 
            fg="#0c0f1d", 
            bg="#ffd700"
        )
        header_lbl.pack(anchor="center")

        # 2. Grid Table Area
        frame = tk.Frame(self, bg="#0c0f1d")
        frame.pack(fill="both", expand=True, padx=15, pady=15)

        # Configure row/col weights on the container frame for precise grid layout
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        canvas = tk.Canvas(frame, bg="#0c0f1d", highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")

        v_scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        v_scrollbar.grid(row=0, column=1, sticky="ns")

        h_scrollbar = ttk.Scrollbar(frame, orient="horizontal", command=canvas.xview)
        h_scrollbar.grid(row=1, column=0, sticky="ew")

        scroll_frame = tk.Frame(canvas, bg="#0c0f1d")
        scroll_window = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        def on_scroll_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        scroll_frame.bind("<Configure>", on_scroll_configure)

        # Get list of display-enabled satellites
        sats = [s for s in self.sim_window.load_satellites_list() if s.get("display", True)]
        
        # Header Row 1
        # Col 0: date and time stamp
        self.time_lbl = tk.Label(scroll_frame, text="date and time stamp\n0.0 s", font=("Segoe UI", 9, "bold"), fg="#ffffff", bg="#1a2238", padx=10, pady=8, bd=1, relief="solid", width=18)
        self.time_lbl.grid(row=0, column=0, sticky="nsew")

        for s_idx, sat in enumerate(sats):
            sat_name = sat.get("name", f"Sat-{s_idx+1}")
            noise_val = float(sat.get("noise", 0.0))
            header_text = f"{sat_name}\n(Noise: {noise_val:.1f} km)"
            lbl = tk.Label(scroll_frame, text=header_text, font=("Segoe UI", 9, "bold"), fg="#ffd700", bg="#2c3e50", padx=10, pady=8, bd=1, relief="solid")
            lbl.grid(row=0, column=1 + s_idx * 3, columnspan=3, sticky="nsew")

        # Add Fusing Prediction header
        fusion_header_lbl = tk.Label(scroll_frame, text="Fusing Prediction\n(Algorithm: EKF)", font=("Segoe UI", 9, "bold"), fg="#2ecc71", bg="#2c3e50", padx=10, pady=8, bd=1, relief="solid")
        fusion_header_lbl.grid(row=0, column=1 + len(sats) * 3, columnspan=3, sticky="nsew")
        self.fusion_header_lbl = fusion_header_lbl

        # Header Row 2
        # Col 0: Missile Name (blank or labeled)
        lbl_msl = tk.Label(scroll_frame, text="Missile Name", font=("Segoe UI", 9, "bold"), fg="#ffffff", bg="#1a2238", padx=10, pady=8, bd=1, relief="solid", width=18)
        lbl_msl.grid(row=1, column=0, sticky="nsew")

        for s_idx in range(len(sats)):
            for c_idx, h in enumerate(["Latitude", "Longitude", "Altitude"]):
                col_name_lbl = tk.Label(scroll_frame, text=h, font=("Segoe UI", 8, "bold"), fg="#9fb3bf", bg="#203040", padx=8, pady=4, bd=1, relief="solid")
                col_name_lbl.grid(row=1, column=1 + s_idx * 3 + c_idx, sticky="nsew")

        for c_idx, h in enumerate(["Latitude", "Longitude", "Altitude"]):
            col_name_lbl = tk.Label(scroll_frame, text=h, font=("Segoe UI", 8, "bold"), fg="#5cd65c", bg="#203040", padx=8, pady=4, bd=1, relief="solid")
            col_name_lbl.grid(row=1, column=1 + len(sats) * 3 + c_idx, sticky="nsew")

        # Threats list
        all_threats = self.sim_window.missiles + self.sim_window.interceptors
        
        for r_idx, threat in enumerate(all_threats):
            row_idx = r_idx + 2
            bg_color = "#111625" if r_idx % 2 == 0 else "#080b15"
            threat_name = getattr(threat, "label", f"Target-{r_idx+1}")
            
            # Threat Name
            tk.Label(scroll_frame, text=threat_name, bg=bg_color, fg="#58a6ff", font=("Segoe UI", 9, "bold"), bd=1, relief="solid", width=18, padx=8, pady=6).grid(row=row_idx, column=0, sticky="nsew")
            
            # Create cell Label widgets
            for s_idx, sat in enumerate(sats):
                sat_name = sat.get("name", f"Sat-{s_idx+1}")
                for c_idx, k in enumerate(["lat", "lon", "alt"]):
                    lbl = tk.Label(scroll_frame, text="", bg=bg_color, fg="#ffffff", font=("Segoe UI", 9), bd=1, relief="solid", width=10, padx=6, pady=6)
                    lbl.grid(row=row_idx, column=1 + s_idx * 3 + c_idx, sticky="nsew")
                    self.cell_labels[(threat_name, sat_name, k)] = lbl

            # Create cell Label widgets for Fusing Prediction column
            for c_idx, k in enumerate(["lat", "lon", "alt"]):
                lbl = tk.Label(scroll_frame, text="", bg=bg_color, fg="#2ecc71", font=("Segoe UI", 9, "bold"), bd=1, relief="solid", width=10, padx=6, pady=6)
                lbl.grid(row=row_idx, column=1 + len(sats) * 3 + c_idx, sticky="nsew")
                self.cell_labels[(threat_name, "Fusing_Prediction", k)] = lbl

        # Status Bar at bottom of window
        status_frm = tk.Frame(self, bg="#1a2238", pady=4)
        status_frm.pack(fill="x", side="bottom")
        
        self.winsock_lbl = tk.Label(
            status_frm, 
            text="Winsock Connection: INACTIVE (Local Mode)", 
            font=("Segoe UI", 9, "bold"), 
            fg="#e74c3c", 
            bg="#1a2238"
        )
        self.winsock_lbl.pack(side="left", padx=15)
        
        self.winsock_stats_lbl = tk.Label(
            status_frm, 
            text="Packets: N/A", 
            font=("Segoe UI", 9), 
            fg="#95a5a6", 
            bg="#1a2238"
        )
        self.winsock_stats_lbl.pack(side="right", padx=15)

    def poll_queue_loop(self):
        try:
            # Query the latest pre-computed results from background thread under lock
            results = None
            with self.data_lock:
                if self.latest_ui_data is not None:
                    results = self.latest_ui_data
                    self.latest_ui_data = None # Clear after reading to prevent redundant redraws
                    
            if results is not None:
                # 1. Update timestamp string
                if self.time_lbl:
                    self.time_lbl.config(text=results["time_text"])
                    
                # 2. Update algorithm label string
                if hasattr(self, "fusion_header_lbl") and self.fusion_header_lbl:
                    self.fusion_header_lbl.config(text=results["fusion_algo_text"])
                    
                # 3. Update Winsock labels directly
                if hasattr(self, "winsock_lbl") and self.winsock_lbl:
                    self.winsock_lbl.config(text=results.get("winsock_text", "Winsock Connection: INACTIVE"), fg=results.get("winsock_fg", "#e74c3c"))
                if hasattr(self, "winsock_stats_lbl") and self.winsock_stats_lbl:
                    self.winsock_stats_lbl.config(text=results.get("winsock_stats_text", "Packets: N/A"))
                    
                # 4. Update table labels directly (zero math!)
                for key, (val, is_visible) in results["cell_values"].items():
                    if key in self.cell_labels:
                        lbl = self.cell_labels[key]
                        if is_visible:
                            # Use bright green for fusion cells and gold for satellite cells
                            fg_color = "#2ecc71" if key[1] == "Fusing_Prediction" else "#ffd54f"
                            lbl.config(text=val, fg=fg_color)
                        else:
                            lbl.config(text="")
                            
        except Exception as e:
            print("Error polling pre-computed satellite tracking data:", e)
            
        # Poll again in 250ms (Low Priority, high performance!)
        if self.winfo_exists():
            self.after(250, self.poll_queue_loop)

    def local_fusions_math(self, threat_observations, tracking_algo):
        import math
        import statistics
        fused_lat, fused_lon, fused_alt = 0.0, 0.0, 0.0
        has_fused = False
        
        if len(threat_observations) > 0:
            has_fused = True
            
            if tracking_algo == "Single Best":
                best_obs = min(threat_observations, key=lambda obs: obs[3])
                fused_lat, fused_lon, fused_alt = best_obs[0], best_obs[1], best_obs[2]
            else:
                weights = []
                for obs in threat_observations:
                    noise = obs[3]
                    w = 1.0 / (noise**2 + 1e-4)
                    weights.append(w)
                
                if tracking_algo == "HKF" and len(threat_observations) >= 2:
                    lats = [obs[0] for obs in threat_observations]
                    lons = [obs[1] for obs in threat_observations]
                    alts = [obs[2] for obs in threat_observations]
                    med_lat = statistics.median(lats)
                    med_lon = statistics.median(lons)
                    med_alt = statistics.median(alts)
                    
                    for idx_obs, obs in enumerate(threat_observations):
                        lat_diff = (obs[0] - med_lat) * 111.32
                        lon_diff = (obs[1] - med_lon) * 111.32 * math.cos(math.radians(med_lat))
                        alt_diff = (obs[2] - med_alt)
                        dist_err = math.sqrt(lat_diff**2 + lon_diff**2 + alt_diff**2)
                        
                        sat_noise = obs[3]
                        k = 1.5 * max(sat_noise, 5.0)
                        if dist_err > k:
                            scale = k / dist_err
                            weights[idx_obs] *= scale
                
                sum_weights = sum(weights)
                if sum_weights > 0:
                    weights = [w / sum_weights for w in weights]
                    fused_lat = sum(obs[0] * w for obs, w in zip(threat_observations, weights))
                    fused_lon = sum(obs[1] * w for obs, w in zip(threat_observations, weights))
                    fused_alt = sum(obs[2] * w for obs, w in zip(threat_observations, weights))
                
                fused_lat = max(-90.0, min(90.0, fused_lat))
                fused_lon = (fused_lon + 180.0) % 360.0 - 180.0
                fused_alt = max(0.0, fused_alt)
        return fused_lat, fused_lon, fused_alt, has_fused

    def bg_worker_loop(self):
        import time
        import math
        import random
        import statistics
        
        sent_count = 0
        recv_count = 0
        
        while True:
            try:
                # Wait for a new state frame in the queue (blocking is fine, we are in a background thread!)
                state = self.sim_window.sat_live_view_queue.get()
                if state is None:
                    continue
                    
                t_elapsed = state["time"]
                sats = state["sats"]
                all_threats = state["threats"]
                tracking_algo = state.get("tracking_algorithm", "EKF")
                
                # Compute results dictionary
                results = {
                    "time_text": f"date and time stamp\n{t_elapsed:.1f} s",
                    "fusion_algo_text": f"Fusing Prediction\n(Algorithm: {tracking_algo})",
                    "cell_values": {} # key: (threat_name, sat_name, k) -> (val, is_visible)
                }
                
                for threat in all_threats:
                    threat_name = threat["name"]
                    threat_observations = []
                    
                    for sat_info in sats:
                        sat_name = sat_info["name"]
                        sat_pos_ecef = sat_info["pos"]
                        
                        is_tracking = threat["active"] and threat["launched"] and not threat["hit"]
                        is_visible = False
                        lat, lon, alt = 0.0, 0.0, 0.0
                        
                        if is_tracking and threat["pos"] is not None:
                            threat_pos_ecef = threat["pos"]
                            # Check occlusion (calling this here inside the background thread keeps the main thread 100% smooth!)
                            is_occluded = self.sim_window.is_ecef_occluded_by_earth(sat_pos_ecef, threat_pos_ecef)
                            if not is_occluded:
                                is_visible = True
                                geo_alt = self.sim_window.simulation_vector_to_geo_altitude(threat_pos_ecef)
                                if geo_alt is not None:
                                    lat, lon, alt = geo_alt
                                    
                                    # Add simulated noise
                                    sat_noise = float(sat_info.get("noise", 0.0))
                                    if sat_noise > 0.0:
                                        lat_noise_deg = random.gauss(0.0, sat_noise / 111.32)
                                        lat = lat + lat_noise_deg
                                        
                                        cos_lat = math.cos(math.radians(lat))
                                        if abs(cos_lat) > 0.01:
                                            lon_noise_deg = random.gauss(0.0, sat_noise / (111.32 * cos_lat))
                                        else:
                                            lon_noise_deg = 0.0
                                        lon = lon + lon_noise_deg
                                        
                                        alt_noise_km = random.gauss(0.0, sat_noise)
                                        alt = max(0.0, alt + alt_noise_km)
                                        
                                        lat = max(-90.0, min(90.0, lat))
                                        lon = (lon + 180.0) % 360.0 - 180.0
                                        
                                    threat_observations.append((lat, lon, alt, sat_noise))
                                    
                        # Store computed satellite cell values
                        for k, val in [("lat", f"{lat:.2f}°"), ("lon", f"{lon:.2f}°"), ("alt", f"{alt:.1f} km")]:
                            results["cell_values"][(threat_name, sat_name, k)] = (val, is_visible)
                            
                    # Perform EKF/HKF/Weighted Avg/Single Best data fusion over threat_observations
                    fused_lat, fused_lon, fused_alt = 0.0, 0.0, 0.0
                    has_fused = False
                    
                    is_mp = getattr(self.sim_window.config, "mp_mode", False) and (self.client_socket is not None)
                    if is_mp:
                        results["winsock_text"] = "Winsock Connection: ACTIVE (Process 2: multitest.py)"
                        results["winsock_fg"] = "#2ecc71"
                    else:
                        results["winsock_text"] = "Winsock Connection: INACTIVE (Local Mode)"
                        results["winsock_fg"] = "#e74c3c"
                        results["winsock_stats_text"] = "Packets: N/A"
                        
                    if len(threat_observations) > 0:
                        if is_mp:
                            # Winsock cyclic send/receive communication to Process 2 (multitest.py)!
                            # ex. "aa1" stands EKF, "aa2" stands HKF, "aa3" stands Weighted Avg, "aa4" stands Single Best
                            algo_protocol_map = {"EKF": "aa1", "HKF": "aa2", "Weighted Avg": "aa3", "Single Best": "aa4"}
                            algo_proto = algo_protocol_map.get(tracking_algo, "aa1")
                            
                            packet = {
                                "algo": algo_proto,
                                "observations": threat_observations # list of [lat, lon, alt, sat_noise]
                            }
                            
                            try:
                                import json
                                import time
                                t_start = time.perf_counter()
                                
                                # Send cyclic packet to Process 2 (mslrawpos queue equivalent)
                                self.client_socket.sendall((json.dumps(packet) + "\n").encode('utf-8'))
                                sent_count += 1
                                
                                # Receive cyclic response from Process 2 (OptFusing queue equivalent)
                                reply_buffer = ""
                                while "\n" not in reply_buffer:
                                    resp = self.client_socket.recv(4096)
                                    if not resp:
                                        raise ConnectionError()
                                    reply_buffer += resp.decode('utf-8')
                                    
                                recv_count += 1
                                t_end = time.perf_counter()
                                latency_ms = (t_end - t_start) * 1000.0
                                
                                results["winsock_stats_text"] = f"Packets: Sent {sent_count} / Recv {recv_count} (Latency: {latency_ms:.1f} ms)"
                                
                                line, _ = reply_buffer.split("\n", 1)
                                reply = json.loads(line)
                                fused_lat = reply.get("fused_lat", 0.0)
                                fused_lon = reply.get("fused_lon", 0.0)
                                fused_alt = reply.get("fused_alt", 0.0)
                                has_fused = reply.get("has_fused", False)
                            except Exception as e:
                                print("[MP ERROR] Winsock communication failed, falling back to local math:", e)
                                fused_lat, fused_lon, fused_alt, has_fused = self.local_fusions_math(threat_observations, tracking_algo)
                                results["winsock_text"] = "Winsock Connection: ERROR (Process 2 Disconnected)"
                                results["winsock_fg"] = "#e74c3c"
                                results["winsock_stats_text"] = "Packets: Connection Dropped"
                        else:
                            # Local computation mode
                            fused_lat, fused_lon, fused_alt, has_fused = self.local_fusions_math(threat_observations, tracking_algo)
                            
                    # Store computed fusion cell values
                    for k, val in [("lat", f"{fused_lat:.2f}°"), ("lon", f"{fused_lon:.2f}°"), ("alt", f"{fused_alt:.1f} km")]:
                        results["cell_values"][(threat_name, "Fusing_Prediction", k)] = (val, has_fused)
                        
                # Update latest computed data under lock
                with self.data_lock:
                    self.latest_ui_data = results
                    
            except Exception as e:
                print("Error in background worker thread:", e)
                time.sleep(0.1)
