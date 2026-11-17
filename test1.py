#impact.py
import tkinter as tk
import os
import math
import numpy as np
import time

def snapshot_sim_data(sim_window, cache=None, selected_idx=0, go_trigger_time=0.0, selected_type="missile"):
    if sim_window is None:
        return None
    if cache is None:
        cache = {}
    
    missiles_snap = []
    try:
        for idx, msl in enumerate(sim_window.missiles):
            geo_msl = sim_window.simulation_vector_to_geo_altitude(msl.pos)
            geo_tgt = sim_window.simulation_vector_to_geo_altitude(msl.target)
            
            # Retrieve or initialize the cache for this missile
            msl_id = id(msl)
            if msl_id not in cache:
                cache[msl_id] = []
                
            msl_cache = cache[msl_id]
            # Convert only the NEW points
            if hasattr(msl, "path"):
                while len(msl_cache) < len(msl.path):
                    pt = msl.path[len(msl_cache)]
                    geo_pt = sim_window.simulation_vector_to_geo_altitude(pt)
                    if geo_pt is not None:
                        msl_cache.append([geo_pt[0], geo_pt[1]])
                    else:
                        msl_cache.append([0.0, 0.0]) # fallback
                        
            # Now downsample the pre-converted path
            trail_coords = []
            if len(msl_cache) > 1:
                sample_rate = max(1, len(msl_cache) // 150)
                sampled_path = msl_cache[::sample_rate]
                if len(msl_cache) - 1 not in range(0, len(msl_cache), sample_rate):
                    sampled_path.append(msl_cache[-1])
                trail_coords = sampled_path
            
            missiles_snap.append({
                "idx": idx,
                "label": getattr(msl, "label", f"M{idx+1}"),
                "geo_msl": geo_msl,
                "geo_tgt": geo_tgt,
                "trail_coords": trail_coords,
                "active": msl.active,
                "reached_target": getattr(msl, "reached_target", False)
            })
    except Exception as ex:
        print("Error snapshotting missiles:", ex)
        
    interceptors_snap = []
    try:
        for idx, intcp in enumerate(sim_window.interceptors):
            geo_intcp = sim_window.simulation_vector_to_geo_altitude(intcp.pos)
            
            # Retrieve or initialize the cache for this interceptor
            intcp_id = id(intcp)
            if intcp_id not in cache:
                cache[intcp_id] = []
                
            intcp_cache = cache[intcp_id]
            # Convert only the NEW points
            if hasattr(intcp, "path"):
                while len(intcp_cache) < len(intcp.path):
                    pt = intcp.path[len(intcp_cache)]
                    geo_pt = sim_window.simulation_vector_to_geo_altitude(pt)
                    if geo_pt is not None:
                        intcp_cache.append([geo_pt[0], geo_pt[1]])
                    else:
                        intcp_cache.append([0.0, 0.0]) # fallback
                        
            # Now downsample the pre-converted path
            trail_coords = []
            if len(intcp_cache) > 1:
                sample_rate = max(1, len(intcp_cache) // 150)
                sampled_path = intcp_cache[::sample_rate]
                if len(intcp_cache) - 1 not in range(0, len(intcp_cache), sample_rate):
                    sampled_path.append(intcp_cache[-1])
                trail_coords = sampled_path
                        
            interceptors_snap.append({
                "idx": idx,
                "label": getattr(intcp, "label", f"Int{idx+1}"),
                "geo_intcp": geo_intcp,
                "trail_coords": trail_coords,
                "active": intcp.active,
                "hit": intcp.hit
            })
    except Exception as ex:
        print("Error snapshotting interceptors:", ex)
        
    show_msl_lbl = getattr(sim_window, "show_msl_lbl_var", None).get() if hasattr(sim_window, "show_msl_lbl_var") else True
    return {
        "selected_idx": selected_idx,
        "selected_type": selected_type,
        "go_trigger_time": go_trigger_time,
        "show_msl_lbl": show_msl_lbl,
        "sim_elapsed_time": getattr(sim_window, "sim_elapsed_time", 0.0),
        "missiles": missiles_snap,
        "interceptors": interceptors_snap
    }

def save_json_atomic(data, filename):
    import json
    tmp_filename = filename + ".tmp"
    try:
        with open(tmp_filename, "w") as f:
            json.dump(data, f)
        if os.path.exists(tmp_filename):
            try:
                os.replace(tmp_filename, filename)
            except PermissionError:
                # On Windows, if WebView2 is fetching the file, ignore transient lock.
                pass
    except Exception:
        pass

def update_map_file(epicenter_lat, epicenter_lon, sim_window=None, msl_lat=None, msl_lon=None):
    try:
        import folium
        import os
        
        for filename, zoom_level, use_restore in [("missile_warning_map.html", 11, True), ("local_zoom_map.html", 14, True)]:
            m = folium.Map(location=[epicenter_lat, epicenter_lon], zoom_start=zoom_level, tiles="OpenStreetMap")
            
            # Ground zero marker (target) - drawn cleanly on its own without any impact circles
            folium.Marker(
                location=[epicenter_lat, epicenter_lon],
                popup="<b>Ground Zero (Target Epicenter)</b>",
                icon=folium.Icon(color="darkred", icon="warning", prefix="fa")
            ).add_to(m)
            
            # Inject Custom Leaflet Javascript to persist zoom/drag and fetch live_data.json every 250ms dynamically!
            js_persist_template = """
            <script>
            document.addEventListener("DOMContentLoaded", function() {
                setTimeout(function() {
                    var maps = Object.keys(window).filter(k => k.startsWith("map_") && window[k] instanceof L.Map);
                    if (maps.length > 0) {
                        var map = window[maps[0]];
                        
                        __RESTORE_LOGIC__
                        
                        // ------------------ REAL-TIME CLIENT-SIDE UPDATE LOOP ------------------
                        var dynamicLayers = [];
                        var epicenter_lat = __EPICENTER_LAT__;
                        var epicenter_lon = __EPICENTER_LON__;
                        
                        function updateLiveMap() {
                            fetch("./live_data.json?t=" + new Date().getTime())
                                .then(response => response.json())
                                .then(data => {
                                    __GO_TRIGGER_LOGIC__

                                    // 1. Clear old dynamic layers
                                    dynamicLayers.forEach(layer => map.removeLayer(layer));
                                    dynamicLayers = [];
                                    
                                    // 2. Render missiles and trails
                                    if (data.missiles) {
                                        data.missiles.forEach((msl) => {
                                            var idx = msl.idx;
                                            var geo_msl = msl.geo_msl;
                                            var geo_tgt = msl.geo_tgt;
                                            var trail_coords = msl.trail_coords;
                                            var active = msl.active;
                                            var reached_target = msl.reached_target;
                                            
                                            // Determine status
                                            var is_intercepted = data.interceptors && data.interceptors.some(i => i.idx === idx && i.hit);
                                            
                                            // Draw circles and missile marker if active or waiting on launch pad
                                            if (geo_msl && (active || (!active && !reached_target))) {
                                                var lat = geo_msl[0];
                                                var lon = geo_msl[1];
                                                var alt = geo_msl[2];
                                                
                                                // Only draw danger warning circles if the missile is active in flight
                                                if (active) {
                                                    // Circle 15km (Yellow)
                                                    var c1 = L.circle([lat, lon], {radius: 15000, color: "yellow", weight: 1.5, fill: true, fillColor: "yellow", fillOpacity: 0.12});
                                                    c1.bindTooltip("M" + (idx+1) + " Low Risk: Watch");
                                                    c1.addTo(map);
                                                    dynamicLayers.push(c1);
                                                    
                                                    // Circle 8km (Orange)
                                                    var c2 = L.circle([lat, lon], {radius: 8000, color: "orange", weight: 1.5, fill: true, fillColor: "orange", fillOpacity: 0.28});
                                                    c2.bindTooltip("M" + (idx+1) + " Med Risk: Fragment");
                                                    c2.addTo(map);
                                                    dynamicLayers.push(c2);
                                                    
                                                    // Circle 3km (Red)
                                                    var c3 = L.circle([lat, lon], {radius: 3000, color: "red", weight: 1.5, fill: true, fillColor: "red", fillOpacity: 0.45});
                                                    c3.bindTooltip("M" + (idx+1) + " High Risk: Blast");
                                                    c3.addTo(map);
                                                    dynamicLayers.push(c3);
                                                }
                                                
                                                // Missile Marker
                                                var mIcon = L.AwesomeMarkers.icon({icon: 'plane', markerColor: 'red', prefix: 'fa'});
                                                var marker = L.marker([lat, lon], {icon: mIcon});
                                                marker.bindPopup("<b>Incoming Missile " + (idx+1) + " (Alt: " + alt.toFixed(1) + "km)</b>");
                                                if (data.show_msl_lbl !== false) {
                                                    marker.bindTooltip(msl.label || "M" + (idx+1), {permanent: true, direction: "top", offset: [0, -5], className: "missile-tooltip"});
                                                }
                                                marker.addTo(map);
                                                dynamicLayers.push(marker);
                                            }
                                            
                                            // Draw trail
                                            if (trail_coords && trail_coords.length > 1) {
                                                var solid_segment = [];
                                                for (var i = 0; i < trail_coords.length; i++) {
                                                    var p = trail_coords[i];
                                                    if (solid_segment.length === 0) {
                                                        solid_segment.push(p);
                                                    } else {
                                                        var last_p = solid_segment[solid_segment.length - 1];
                                                        if (Math.abs(p[1] - last_p[1]) > 180) {
                                                            if (solid_segment.length > 1) {
                                                                var line = L.polyline(solid_segment, {color: "red", weight: 3, opacity: 0.8});
                                                                line.addTo(map);
                                                                dynamicLayers.push(line);
                                                            }
                                                            var dashLine = L.polyline([last_p, p], {color: "#ff6b6b", weight: 1.5, dashArray: "5, 5", opacity: 0.5});
                                                            dashLine.addTo(map);
                                                            dynamicLayers.push(dashLine);
                                                            solid_segment = [p];
                                                        } else {
                                                            solid_segment.push(p);
                                                        }
                                                    }
                                                }
                                                if (solid_segment.length > 1) {
                                                    var line = L.polyline(solid_segment, {color: "red", weight: 3, opacity: 0.8});
                                                    line.addTo(map);
                                                    dynamicLayers.push(line);
                                                }
                                            }
                                            
                                            // Draw status icons
                                            if (is_intercepted && trail_coords && trail_coords.length > 0) {
                                                var loc = trail_coords[trail_coords.length - 1];
                                                var fIcon = L.AwesomeMarkers.icon({icon: 'fire', markerColor: 'orange', prefix: 'fa'});
                                                var fMarker = L.marker(loc, {icon: fIcon});
                                                fMarker.bindPopup("<b>Missile " + (idx+1) + " INTERCEPTED (SUCCESS)</b>");
                                                if (data.show_msl_lbl !== false) {
                                                    fMarker.bindTooltip((msl.label || "M" + (idx+1)) + " (Intercepted)", {permanent: true, direction: "top", offset: [0, -5], className: "missile-tooltip"});
                                                }
                                                fMarker.addTo(map);
                                                dynamicLayers.push(fMarker);
                                            } else if (reached_target && geo_tgt) {
                                                var loc = [geo_tgt[0], geo_tgt[1]];
                                                var bIcon = L.AwesomeMarkers.icon({icon: 'bomb', markerColor: 'red', prefix: 'fa'});
                                                var bMarker = L.marker(loc, {icon: bIcon});
                                                bMarker.bindPopup("<b>Missile " + (idx+1) + " IMPACT (FAILURE)</b>");
                                                if (data.show_msl_lbl !== false) {
                                                    bMarker.bindTooltip((msl.label || "M" + (idx+1)) + " (Detonated)", {permanent: true, direction: "top", offset: [0, -5], className: "missile-tooltip"});
                                                }
                                                bMarker.addTo(map);
                                                dynamicLayers.push(bMarker);
                                            }
                                            
                                            // Draw Target (if not hit)
                                            if (!reached_target && geo_tgt) {
                                                var tgt_lat = geo_tgt[0];
                                                var tgt_lon = geo_tgt[1];
                                                if (Math.abs(tgt_lat - epicenter_lat) > 1e-4 || Math.abs(tgt_lon - epicenter_lon) > 1e-4) {
                                                    var tIcon = L.AwesomeMarkers.icon({icon: 'crosshairs', markerColor: 'green', prefix: 'fa'});
                                                    var tMarker = L.marker([tgt_lat, tgt_lon], {icon: tIcon});
                                                    tMarker.bindPopup("<b>Missile " + (idx+1) + " Target</b>");
                                                    if (data.show_msl_lbl !== false) {
                                                        tMarker.bindTooltip((msl.label || "M" + (idx+1)) + " Target", {permanent: true, direction: "top", offset: [0, -5], className: "target-tooltip"});
                                                    }
                                                    tMarker.addTo(map);
                                                    dynamicLayers.push(tMarker);
                                                }
                                            }
                                        });
                                    }
                                    
                                    // 3. Render interceptors and trails
                                    if (data.interceptors) {
                                        data.interceptors.forEach((intcp) => {
                                            var idx = intcp.idx;
                                            var geo_intcp = intcp.geo_intcp;
                                            var trail_coords = intcp.trail_coords;
                                            var active = intcp.active;
                                            var hit = intcp.hit;
                                            
                                            // Draw interceptor marker if active or waiting on launcher
                                            if (geo_intcp && (active || (!active && !hit))) {
                                                var lat = geo_intcp[0];
                                                var lon = geo_intcp[1];
                                                var alt = geo_intcp[2];
                                                
                                                var rIcon = L.AwesomeMarkers.icon({icon: 'rocket', markerColor: 'blue', prefix: 'fa'});
                                                var rMarker = L.marker([lat, lon], {icon: rIcon});
                                                rMarker.bindPopup("<b>Interceptor " + (idx+1) + " (Alt: " + alt.toFixed(1) + "km)</b>");
                                                if (data.show_msl_lbl !== false) {
                                                    rMarker.bindTooltip(intcp.label || "Int" + (idx+1), {permanent: true, direction: "top", offset: [0, -5], className: "interceptor-tooltip"});
                                                }
                                                rMarker.addTo(map);
                                                dynamicLayers.push(rMarker);
                                            }
                                            
                                            if (trail_coords && trail_coords.length > 1) {
                                                var solid_segment = [];
                                                for (var i = 0; i < trail_coords.length; i++) {
                                                    var p = trail_coords[i];
                                                    if (solid_segment.length === 0) {
                                                        solid_segment.push(p);
                                                    } else {
                                                        var last_p = solid_segment[solid_segment.length - 1];
                                                        if (Math.abs(p[1] - last_p[1]) > 180) {
                                                            if (solid_segment.length > 1) {
                                                                var line = L.polyline(solid_segment, {color: "blue", weight: 3, opacity: 0.8});
                                                                line.addTo(map);
                                                                dynamicLayers.push(line);
                                                            }
                                                            var dashLine = L.polyline([last_p, p], {color: "#819ff7", weight: 1.5, dashArray: "5, 5", opacity: 0.5});
                                                            dashLine.addTo(map);
                                                            dynamicLayers.push(dashLine);
                                                            solid_segment = [p];
                                                        } else {
                                                            solid_segment.push(p);
                                                        }
                                                    }
                                                }
                                                if (solid_segment.length > 1) {
                                                    var line = L.polyline(solid_segment, {color: "blue", weight: 3, opacity: 0.8});
                                                    line.addTo(map);
                                                    dynamicLayers.push(line);
                                                }
                                            }
                                        });
                                    }
                                })
                                .catch(err => console.log("Error loading live data:", err));
                        }
                        
                        setInterval(updateLiveMap, 250);
                    }
                }, 150);
            });
            </script>
            """
            
            # Determine unique localStorage keys based on map type (global vs local)
            lat_key = "global_map_lat" if zoom_level == 11 else "local_map_lat"
            lon_key = "global_map_lon" if zoom_level == 11 else "local_map_lon"
            zoom_key = "global_map_zoom" if zoom_level == 11 else "local_map_zoom"

            # Both maps now have their own independent, persistent saved coordinate/zoom settings!
            restore_logic = ""
            if use_restore:
                restore_logic = """
                var savedLat = localStorage.getItem("__LAT_KEY__");
                var savedLon = localStorage.getItem("__LON_KEY__");
                var savedZoom = localStorage.getItem("__ZOOM_KEY__");
                
                if (savedLat && savedLon && savedZoom) {
                    map.setView([parseFloat(savedLat), parseFloat(savedLon)], parseInt(savedZoom), {animate: false});
                }
                
                map.on("moveend", function() {
                    var center = map.getCenter();
                    localStorage.setItem("__LAT_KEY__", center.lat);
                    localStorage.setItem("__LON_KEY__", center.lng);
                });
                map.on("zoomend", function() {
                    localStorage.setItem("__ZOOM_KEY__", map.getZoom());
                });
                """.replace("__LAT_KEY__", lat_key) \
                   .replace("__LON_KEY__", lon_key) \
                   .replace("__ZOOM_KEY__", zoom_key)
                
            # Populate go-trigger logic (only for embedded local zoom map!)
            go_trigger_logic = ""
            if zoom_level == 14:
                go_trigger_logic = """
                                    // 0. Auto-center on selected index current position or target (Ground Zero local zoom map)
                                    var selectedIdx = data.selected_idx || 0;
                                    var lat, lon;
                                    if (data.selected_type === "interceptor") {
                                        var selectedIntcp = data.interceptors && data.interceptors.find(i => i.idx === selectedIdx);
                                        if (selectedIntcp && selectedIntcp.geo_intcp) {
                                            lat = selectedIntcp.geo_intcp[0];
                                            lon = selectedIntcp.geo_intcp[1];
                                        }
                                    } else if (data.selected_type === "target") {
                                        var selectedMsl = data.missiles && data.missiles.find(m => m.idx === selectedIdx);
                                        if (selectedMsl && selectedMsl.geo_tgt) {
                                            lat = selectedMsl.geo_tgt[0];
                                            lon = selectedMsl.geo_tgt[1];
                                        }
                                    } else { // missile
                                        var selectedMsl = data.missiles && data.missiles.find(m => m.idx === selectedIdx);
                                        if (selectedMsl && selectedMsl.geo_msl) {
                                            lat = selectedMsl.geo_msl[0];
                                            lon = selectedMsl.geo_msl[1];
                                        }
                                    }
                                    
                                    // Handle manual Go-trigger or selection change centering
                                    if (lat !== undefined && lon !== undefined && data.go_trigger_time && window.last_go_trigger !== data.go_trigger_time) {
                                        window.last_go_trigger = data.go_trigger_time;
                                        map.setView([lat, lon], map.getZoom(), {animate: true});
                                    }
                """
                
            js_persist = js_persist_template.replace("__RESTORE_LOGIC__", restore_logic) \
                                             .replace("__GO_TRIGGER_LOGIC__", go_trigger_logic) \
                                             .replace("__EPICENTER_LAT__", str(epicenter_lat)) \
                                             .replace("__EPICENTER_LON__", str(epicenter_lon)) \
                                             .replace("__ZOOM_LEVEL__", str(zoom_level))
                                             
            m.get_root().html.add_child(folium.Element(js_persist))
            
            css_style = """
            <style>
            .awesome-marker {
                transform: scale(0.5) !important;
                transform-origin: 50% 100% !important;
            }
            .awesome-marker-shadow {
                transform: scale(0.5) !important;
                transform-origin: 50% 100% !important;
            }
            .leaflet-tooltip {
                background-color: transparent !important;
                border: none !important;
                box-shadow: none !important;
                font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif !important;
                font-weight: 400 !important;
                font-size: 11px !important;
                white-space: nowrap !important;
                text-rendering: optimizeLegibility !important;
                -webkit-font-smoothing: antialiased !important;
                -moz-osx-font-smoothing: grayscale !important;
                text-shadow: 1px 1px 0px #000 !important;
            }
            .leaflet-tooltip:before {
                display: none !important;
            }
            .missile-tooltip {
                color: #ff3333 !important; /* Bright red matching missiles/trails */
            }
            .interceptor-tooltip {
                color: #3399ff !important; /* Bright blue matching interceptors/trails */
            }
            .target-tooltip {
                color: #2ecc71 !important; /* Bright green matching targets */
            }
            </style>
            """
            m.get_root().header.add_child(folium.Element(css_style))
            
            # Save file atomically
            tmp_name = filename + ".tmp"
            m.save(tmp_name)
            if os.path.exists(tmp_name):
                os.replace(tmp_name, filename)
    except Exception as e:
        print("Error regenerating maps:", e)

class MissileImpactWarningWindow(tk.Toplevel):
    def __init__(self, parent, impact_lat, impact_lon, sim_window):
        super().__init__(parent)
        self.title("Missile Impact Warning")
        self.load_window_settings()
        self.configure(bg="#0c0f1d")
        self.resizable(False, False)
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.impact_lat = impact_lat
        self.impact_lon = impact_lon
        self.sim_window = sim_window
        
        self.flash_state = True
        self.explosion_drawn = False
        self.last_map_update_time = 0.0
        self.map_update_in_progress = False
        self.geo_path_cache = {}
        self.go_trigger_time = 0.0
        
        # Determine initial selection (find first active missile if any, otherwise default to 0)
        self.selected_msl_idx = 0
        self.selected_type = "missile"
        if self.sim_window is not None and hasattr(self.sim_window, "missiles"):
            for idx, msl in enumerate(self.sim_window.missiles):
                if msl.active:
                    self.selected_msl_idx = idx
                    break
        
        # Generate static missile_warning_map.html once on startup
        update_map_file(self.impact_lat, self.impact_lon, self.sim_window)
        
        # Write initial real-time live_data.json snapshot
        snap = snapshot_sim_data(self.sim_window, self.geo_path_cache, self.selected_msl_idx, self.go_trigger_time, self.selected_type)
        save_json_atomic(snap or {}, "live_data.json")
        
        self.build_ui()
        self.update() # Force Tkinter geometry updates to set initial canvas width/height
        
        # Start reparenting function after 1 second
        self.after(1000, self.reparent_map)
        
        self.update_loop()
        
    def build_ui(self):
        # 1. Header Banner
        self.header_frm = tk.Frame(self, bg="#c0392b", pady=8)
        self.header_frm.pack(fill="x")
        
        self.header_lbl = tk.Label(
            self.header_frm, 
            text="🚨 TACTICAL IMPACT WARNING SYSTEM 🚨", 
            font=("Segoe UI", 12, "bold"), 
            fg="#ffffff", 
            bg="#c0392b"
        )
        self.header_lbl.pack(anchor="center")
        
        # 2. Hazard Map Canvas
        self.canvas_frm = tk.LabelFrame(
            self, 
            text=" Target Area Hazard Map (Ground Zero) ", 
            fg="#3498db", 
            bg="#0c0f1d", 
            font=("Segoe UI", 9, "bold"), 
            bd=1, 
            relief="solid"
        )
        self.canvas_frm.pack(fill="both", expand=True, padx=20, pady=15)
        
        self.canvas = tk.Canvas(self.canvas_frm, bg="#080b15", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Bind resize helper to draw concentric hazard rings
        self.canvas.bind("<Configure>", self.draw_hazard_map)
        
        # 3. Telemetry Status Dashboard Panel
        self.dash_frm = tk.LabelFrame(
            self, 
            text=" Dynamic Telemetry Feed ", 
            fg="#e74c3c", 
            bg="#0c0f1d", 
            font=("Segoe UI", 9, "bold"), 
            bd=1, 
            relief="solid",
            padx=15,
            pady=12
        )
        self.dash_frm.pack(fill="x", padx=20, pady=(0, 15))
        
        # Grid layout for telemetry values
        # Row 1: Threat Profile
        tk.Label(self.dash_frm, text="Threat Profile:", font=("Segoe UI", 9, "bold"), fg="#8892b0", bg="#0c0f1d").grid(row=0, column=0, sticky="w", pady=4)
        
        from tkinter import ttk
        self.msl_var = tk.StringVar()
        self.msl_combo = ttk.Combobox(self.dash_frm, textvariable=self.msl_var, state="readonly", width=35)
        self.msl_combo.grid(row=0, column=1, sticky="w", padx=10, pady=4)
        self.msl_combo.bind("<<ComboboxSelected>>", self.on_missile_selected)
        
        # Populate initial list of values statically once (include all missiles, interceptors, and targets!)
        self.combo_mapping = []
        display_values = []
        initial_combo_idx = 0
        
        if self.sim_window is not None:
            # Missiles
            if hasattr(self.sim_window, "missiles"):
                for idx, msl in enumerate(self.sim_window.missiles):
                    label = getattr(msl, "label", f"M{idx+1}")
                    display_values.append(f"Missile {idx+1}: {label}")
                    self.combo_mapping.append(("missile", idx))
                    if self.selected_type == "missile" and self.selected_msl_idx == idx:
                        initial_combo_idx = len(display_values) - 1
            # Interceptors
            if hasattr(self.sim_window, "interceptors"):
                for idx, intcp in enumerate(self.sim_window.interceptors):
                    label = getattr(intcp, "label", f"Int{idx+1}")
                    display_values.append(f"Interceptor {idx+1}: {label}")
                    self.combo_mapping.append(("interceptor", idx))
                    if self.selected_type == "interceptor" and self.selected_msl_idx == idx:
                        initial_combo_idx = len(display_values) - 1
            # Targets
            if hasattr(self.sim_window, "missiles"):
                for idx, msl in enumerate(self.sim_window.missiles):
                    label = getattr(msl, "target_label", f"T{idx+1}")
                    display_values.append(f"Target {idx+1}: {label}")
                    self.combo_mapping.append(("target", idx))
                    if self.selected_type == "target" and self.selected_msl_idx == idx:
                        initial_combo_idx = len(display_values) - 1
                        
        self.msl_combo["values"] = display_values
        if len(display_values) > 0:
            self.msl_combo.current(initial_combo_idx)
        
        # Row 2: Epicenter
        tk.Label(self.dash_frm, text="Impact Epicenter:", font=("Segoe UI", 9, "bold"), fg="#8892b0", bg="#0c0f1d").grid(row=1, column=0, sticky="w", pady=4)
        self.epicenter_lbl = tk.Label(self.dash_frm, text=f"Lat {self.impact_lat:.4f}°, Lon {self.impact_lon:.4f}°", font=("Segoe UI", 9, "bold"), fg="#ffffff", bg="#0c0f1d")
        self.epicenter_lbl.grid(row=1, column=1, sticky="w", padx=10, pady=4)
        
        # Row 3: Missile Position (Vibrant Real-Time tracking coordinates!)
        tk.Label(self.dash_frm, text="Missile Position:", font=("Segoe UI", 9, "bold"), fg="#8892b0", bg="#0c0f1d").grid(row=2, column=0, sticky="w", pady=4)
        self.msl_pos_lbl = tk.Label(self.dash_frm, text="Offline", font=("Segoe UI", 9, "bold"), fg="#ffd54f", bg="#0c0f1d")
        self.msl_pos_lbl.grid(row=2, column=1, sticky="w", padx=10, pady=4)
        
        self.go_btn = tk.Button(
            self.dash_frm, 
            text="Go", 
            command=self.on_go_clicked, 
            font=("Segoe UI", 8, "bold"), 
            fg="#ffffff", 
            bg="#3498db", 
            activebackground="#2980b9", 
            activeforeground="#ffffff", 
            bd=0, 
            padx=10, 
            pady=2
        )
        self.go_btn.grid(row=2, column=2, sticky="e", padx=(15, 0), pady=4)
        
        # Row 4: Range to Impact
        tk.Label(self.dash_frm, text="Range to Impact:", font=("Segoe UI", 9, "bold"), fg="#8892b0", bg="#0c0f1d").grid(row=3, column=0, sticky="w", pady=4)
        self.range_lbl = tk.Label(self.dash_frm, text="--- km", font=("Segoe UI", 10, "bold"), fg="#ffd54f", bg="#0c0f1d")
        self.range_lbl.grid(row=3, column=1, sticky="w", padx=10, pady=4)
        
        # Row 5: Countdown
        tk.Label(self.dash_frm, text="Time to Impact:", font=("Segoe UI", 9, "bold"), fg="#8892b0", bg="#0c0f1d").grid(row=4, column=0, sticky="w", pady=4)
        self.countdown_lbl = tk.Label(self.dash_frm, text="--- s", font=("Segoe UI", 12, "bold"), fg="#ff3333", bg="#0c0f1d")
        self.countdown_lbl.grid(row=4, column=1, sticky="w", padx=10, pady=4)
        
        # Row 6: Operational Status
        tk.Label(self.dash_frm, text="System Status:", font=("Segoe UI", 9, "bold"), fg="#8892b0", bg="#0c0f1d").grid(row=5, column=0, sticky="w", pady=4)
        self.status_lbl = tk.Label(self.dash_frm, text="TRACKING", font=("Segoe UI", 9, "bold"), fg="#ff9f43", bg="#0c0f1d")
        self.status_lbl.grid(row=5, column=1, sticky="w", padx=10, pady=4)

    def reparent_map(self):
        try:
            import ctypes
            user32 = ctypes.windll.user32
            
            # Find the pywebview window
            hwnd_child = user32.FindWindowW(None, "Target Area Zoom Map")
            if hwnd_child:
                hwnd_parent = self.canvas.winfo_id()
                
                # Get current style
                style = user32.GetWindowLongW(hwnd_child, -16) # GWL_STYLE
                # Remove caption (title bar) and thick frame/border, set WS_CHILD style
                new_style = (style & ~0x00C00000 & ~0x00040000) | 0x40000000 # WS_CHILD
                user32.SetWindowLongW(hwnd_child, -16, new_style)
                
                # Reparent
                user32.SetParent(hwnd_child, hwnd_parent)
                
                # Position it inside self.canvas
                w = self.canvas.winfo_width()
                h = self.canvas.winfo_height()
                if w <= 1: w = 520
                if h <= 1: h = 380
                user32.MoveWindow(hwnd_child, 0, 0, w, h, True)
                user32.ShowWindow(hwnd_child, 5) # SW_SHOW
                
                self.embedded_hwnd = hwnd_child
            else:
                # Retry in 500ms
                self.after(500, self.reparent_map)
        except Exception as e:
            print("Error reparenting map:", e)

    def draw_hazard_map(self, event=None):
        self.canvas.delete("all")
        w = event.width if event is not None else self.canvas.winfo_width()
        h = event.height if event is not None else self.canvas.winfo_height()
        
        if hasattr(self, "embedded_hwnd") and self.embedded_hwnd:
            try:
                import ctypes
                user32 = ctypes.windll.user32
                # Move and resize the embedded pywebview window to perfectly match the Canvas size
                user32.MoveWindow(self.embedded_hwnd, 0, 0, w, h, True)
            except Exception as e:
                print("Error resizing embedded map:", e)

    def update_loop(self):
        try:
            # Check if simulation window exists
            if self.sim_window is not None and self.sim_window.root.winfo_exists():
                self.synchronize_states()
        except Exception as e:
            print("Error synchronizing impact warning:", e)
            
        # Alarm flashing effect (toggled only for logical states, not header coloring)
        self.flash_state = not self.flash_state
        
        # Check every 100ms
        self.after(100, self.update_loop)

    def on_missile_selected(self, event=None):
        combo_sel = self.msl_combo.current()
        if combo_sel != -1 and combo_sel < len(self.combo_mapping):
            self.selected_type, self.selected_msl_idx = self.combo_mapping[combo_sel]
        self.canvas.delete("explosion")
        self.canvas.delete("threat_dot")
        self.canvas.delete("hazard_rings")
        self.explosion_drawn = False
        self.synchronize_states()

    def on_go_clicked(self):
        self.go_trigger_time = time.time()
        # Force an immediate update of live_data.json with the new trigger time
        snap = snapshot_sim_data(self.sim_window, self.geo_path_cache, self.selected_msl_idx, self.go_trigger_time, self.selected_type)
        save_json_atomic(snap or {}, "live_data.json")

    def synchronize_states(self):
        # Default initialization
        if self.sim_window is None or not hasattr(self.sim_window, "missiles") or len(self.sim_window.missiles) == 0:
            return

        if not hasattr(self, "selected_type"):
            self.selected_type = "missile"
        if not hasattr(self, "selected_msl_idx"):
            self.selected_msl_idx = 0

        # Retrieve entities
        active_msl = self.sim_window.missiles[self.selected_msl_idx]
        active_intcp = self.sim_window.interceptors[self.selected_msl_idx] if self.selected_msl_idx < len(self.sim_window.interceptors) else None

        # Dynamically update Ground Zero epicenter coordinates from the target of this missile index
        tgt_pt = self.sim_window.simulation_vector_to_globe_point(active_msl.target)
        tgt_geo = self.sim_window.unit_to_lat_lon(tgt_pt)
        if tgt_geo:
            self.impact_lat, self.impact_lon = tgt_geo
            self.epicenter_lbl.config(text=f"Lat {self.impact_lat:.4f}°, Lon {self.impact_lon:.4f}°")

        # ------------------ TELEMETRY SWITCHBOARD ------------------
        if self.selected_type == "interceptor" and active_intcp is not None:
            # 1. INTERCEPTOR TELEMETRY
            geo_alt = self.sim_window.simulation_vector_to_geo_altitude(active_intcp.pos)
            is_active = active_intcp.active and not active_intcp.hit
            is_launched = getattr(active_intcp, "launched", False) or is_active
            is_hit = active_intcp.hit

            if is_active:
                intcp_pos = np.asarray(active_intcp.pos, dtype=float)
                msl_pos = np.asarray(active_msl.pos, dtype=float)
                distance_km = np.linalg.norm(intcp_pos - msl_pos) * 1000.0 # ECEF distance to missile in km
                countdown_sec = np.linalg.norm(intcp_pos - msl_pos) / active_intcp.speed if active_intcp.speed > 1e-9 else 0.0

                if geo_alt is not None:
                    lat, lon, alt = geo_alt
                    self.msl_pos_lbl.config(text=f"Lat {lat:.2f}°, Lon {lon:.2f}°, Alt {alt:.1f} km", fg="#ffd54f")
                else:
                    self.msl_pos_lbl.config(text="Tracking...", fg="#ffd54f")

                self.range_lbl.config(text=f"{distance_km:.2f} km")
                self.countdown_lbl.config(text=f"{countdown_sec:.1f} s")
                self.status_lbl.config(text="INTERCEPTOR ACTIVE / TRACKING", fg="#3498db")
            elif is_hit:
                if geo_alt is not None:
                    lat, lon, alt = geo_alt
                    self.msl_pos_lbl.config(text=f"Lat {lat:.2f}°, Lon {lon:.2f}°, Alt {alt:.1f} km (Intercepted)", fg="#2ecc71")
                else:
                    self.msl_pos_lbl.config(text="Intercept Successful", fg="#2ecc71")
                self.range_lbl.config(text="0.00 km")
                self.countdown_lbl.config(text="0.0 s")
                self.status_lbl.config(text="INTERCEPT SUCCESSFUL", fg="#2ecc71")
            elif not is_launched:
                if geo_alt is not None:
                    lat, lon, alt = geo_alt
                    self.msl_pos_lbl.config(text=f"Lat {lat:.2f}°, Lon {lon:.2f}°, Alt {alt:.1f} km (Waiting)", fg="#ffd54f")
                else:
                    self.msl_pos_lbl.config(text="Offline (Waiting)", fg="#8892b0")
                self.range_lbl.config(text="--- km")
                self.countdown_lbl.config(text="--- s")
                self.status_lbl.config(text="WAITING FOR LAUNCH", fg="#ffd54f")
            else:
                self.msl_pos_lbl.config(text="Offline", fg="#8892b0")
                self.range_lbl.config(text="--- km")
                self.countdown_lbl.config(text="--- s")
                self.status_lbl.config(text="OFFLINE", fg="#8892b0")

        elif self.selected_type == "target":
            # 2. TARGET / GROUND ZERO TELEMETRY
            geo_alt = self.sim_window.simulation_vector_to_geo_altitude(active_msl.target)
            is_msl_active = active_msl.active
            is_reached = getattr(active_msl, "reached_target", False)
            is_intercepted = active_intcp is not None and getattr(active_intcp, "hit", False)

            if geo_alt is not None:
                lat, lon, alt = geo_alt
                # Target coordinates stay static, but reflect state in parenthetical label!
                if is_msl_active:
                    state_suffix = "Active Threat"
                elif is_reached:
                    state_suffix = "Impacted"
                elif is_intercepted:
                    state_suffix = "Secured"
                else:
                    state_suffix = "Safe"
                self.msl_pos_lbl.config(text=f"Lat {lat:.2f}°, Lon {lon:.2f}°, Alt {alt:.1f} km ({state_suffix})", fg="#2ecc71" if is_intercepted or (not is_msl_active and not is_reached) else "#e74c3c")
            else:
                self.msl_pos_lbl.config(text="Active Ground Zero", fg="#ffd54f")

            self.range_lbl.config(text="0.00 km")
            self.countdown_lbl.config(text="0.0 s")

            if is_msl_active:
                self.status_lbl.config(text="TARGET AREA UNDER ACTIVE THREAT", fg="#e74c3c")
            elif is_reached:
                self.status_lbl.config(text="GROUND ZERO IMPACT RESOLVED", fg="#c0392b")
            elif is_intercepted:
                self.status_lbl.config(text="TARGET AREA SECURED", fg="#2ecc71")
            else:
                self.status_lbl.config(text="TARGET AREA INACTIVE / SAFE", fg="#ffd54f")

        else:
            # 3. MISSILE TELEMETRY (Standard Behavior!)
            geo_alt = self.sim_window.simulation_vector_to_geo_altitude(active_msl.pos)
            is_active = active_msl.active
            is_launched = getattr(active_msl, "launched", True) or is_active
            is_neutralized = active_intcp is not None and getattr(active_intcp, "hit", False)
            is_reached = getattr(active_msl, "reached_target", False)

            if is_active:
                msl_pos = np.asarray(active_msl.pos, dtype=float)
                tgt_pos = np.asarray(active_msl.target, dtype=float)
                distance_km = np.linalg.norm(msl_pos - tgt_pos) * 1000.0 # ECEF distance to target Ground Zero in km
                countdown_sec = np.linalg.norm(msl_pos - tgt_pos) / active_msl.speed if active_msl.speed > 1e-9 else 0.0

                if geo_alt is not None:
                    lat, lon, alt = geo_alt
                    self.msl_pos_lbl.config(text=f"Lat {lat:.2f}°, Lon {lon:.2f}°, Alt {alt:.1f} km", fg="#ffd54f")
                else:
                    self.msl_pos_lbl.config(text="Calculating...", fg="#8892b0")

                self.range_lbl.config(text=f"{distance_km:.2f} km")
                self.countdown_lbl.config(text=f"{countdown_sec:.1f} s")
                self.status_lbl.config(text="TRACKING ACTIVE THREAT", fg="#e74c3c")
            elif is_neutralized:
                if geo_alt is not None:
                    lat, lon, alt = geo_alt
                    self.msl_pos_lbl.config(text=f"Lat {lat:.2f}°, Lon {lon:.2f}°, Alt {alt:.1f} km (Intercepted)", fg="#2ecc71")
                else:
                    self.msl_pos_lbl.config(text="Intercepted", fg="#2ecc71")
                self.range_lbl.config(text="0.00 km")
                self.countdown_lbl.config(text="0.0 s")
                self.status_lbl.config(text="THREAT NEUTRALIZED", fg="#2ecc71")
            elif is_reached:
                if geo_alt is not None:
                    lat, lon, alt = geo_alt
                    self.msl_pos_lbl.config(text=f"Lat {lat:.2f}°, Lon {lon:.2f}°, Alt {alt:.1f} km (Detonated)", fg="#c0392b")
                else:
                    self.msl_pos_lbl.config(text="Impacted", fg="#c0392b")
                self.range_lbl.config(text="0.00 km")
                self.countdown_lbl.config(text="0.0 s")
                self.status_lbl.config(text="IMPACT / DETONATION", fg="#c0392b")
            else:
                if geo_alt is not None:
                    lat, lon, alt = geo_alt
                    self.msl_pos_lbl.config(text=f"Lat {lat:.2f}°, Lon {lon:.2f}°, Alt {alt:.1f} km (Waiting)", fg="#ffd54f")
                else:
                    self.msl_pos_lbl.config(text="Offline (Waiting)", fg="#8892b0")
                self.range_lbl.config(text="--- km")
                self.countdown_lbl.config(text="--- s")
                self.status_lbl.config(text="WAITING FOR LAUNCH", fg="#ffd54f")

        # ------------------ DYNAMIC MAP UPDATE / RECORDINGS TRIGGER ------------------
        # Rate-limit and save live_data.json dynamically (every 250ms!)
        current_time = time.time()
        if current_time - self.last_map_update_time >= 0.25:
            self.last_map_update_time = current_time
            
            # Take snapshot on main thread
            snap = snapshot_sim_data(self.sim_window, self.geo_path_cache, self.selected_msl_idx, self.go_trigger_time, self.selected_type)
            
            # Save live_data.json atomically and instantaneously
            save_json_atomic(snap, "live_data.json")

    def save_window_settings(self):
        try:
            import json
            # Get geometry string, e.g. "560x650+100+100"
            geom = self.geometry()
            parts = geom.split("+")
            if len(parts) == 3:
                size_part = parts[0]
                x = int(parts[1])
                y = int(parts[2])
                
                size_parts = size_part.split("x")
                if len(size_parts) == 2:
                    width = int(size_parts[0])
                    height = int(size_parts[1])
                    
                    # Prevent saving minimized or sentinel coordinates (e.g. -32000)
                    # We use -15000 to allow valid negative coordinates in multi-monitor setups (e.g. -1920)
                    if x >= -15000 and y >= -15000 and width >= 100 and height >= 100:
                        settings = {
                            "width": width,
                            "height": height,
                            "x": x,
                            "y": y
                        }
                        with open("impact_window_settings.json", "w") as f:
                            json.dump(settings, f)
        except Exception as e:
            print("Error saving impact window settings:", e)

    def load_window_settings(self):
        try:
            import json
            import os
            if os.path.exists("impact_window_settings.json"):
                with open("impact_window_settings.json", "r") as f:
                    settings = json.load(f)
                    
                width = settings.get("width", 560)
                height = settings.get("height", 650)
                x = settings.get("x")
                y = settings.get("y")
                
                if x is not None and y is not None and int(x) >= -15000 and int(y) >= -15000:
                    self.geometry(f"{width}x{height}+{x}+{y}")
                else:
                    self.geometry(f"{width}x{height}")
            else:
                self.geometry("560x650")
        except Exception as e:
            print("Error loading impact window settings:", e)
            self.geometry("560x650")

    def on_close(self):
        self.save_window_settings()
        self.destroy()

if __name__ == "__main__":
    # Standard fallback test
    import sys
    if len(sys.argv) == 3:
        impact_lat, impact_lon = float(sys.argv[1]), float(sys.argv[2]) 
    else:   
        # Center map around the target
        impact_lat, impact_lon = 34.1425, -117.9048

    update_map_file(impact_lat, impact_lon)

