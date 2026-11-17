#multitest.py
import numpy as np
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import ttk, messagebox
import platform
import os
import json
import sys

# Debug log to verify sys.argv inside compiled exe
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "multitest_launch_debug.log"), "w") as f_dbg:
    f_dbg.write(f"sys.argv: {sys.argv}\n")

if "--socket-mode" in sys.argv:
    import socket
    import math
    import random
    import statistics
    
    def run_socket_mode_fusion():
        port = 45915
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect(('127.0.0.1', port))
        except Exception as e:
            print("Failed to connect to Process 1 server:", e)
            sys.exit(1)
            
        buffer = ""
        while True:
            try:
                data = s.recv(4096)
                if not data:
                    break
                buffer += data.decode('utf-8')
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if not line.strip():
                        continue
                    packet = json.loads(line)
                    algo = packet.get("algo", "aa1")
                    obs_list = packet.get("observations", [])
                    
                    fused_lat, fused_lon, fused_alt = 0.0, 0.0, 0.0
                    has_fused = False
                    
                    if len(obs_list) > 0:
                        has_fused = True
                        if algo == "aa4": # Single Best
                            best_obs = min(obs_list, key=lambda obs: obs[3])
                            fused_lat, fused_lon, fused_alt = best_obs[0], best_obs[1], best_obs[2]
                        else:
                            weights = []
                            for obs in obs_list:
                                noise = obs[3]
                                w = 1.0 / (noise**2 + 1e-4)
                                weights.append(w)
                                
                            if algo == "aa2" and len(obs_list) >= 2: # HKF
                                lats = [obs[0] for obs in obs_list]
                                lons = [obs[1] for obs in obs_list]
                                alts = [obs[2] for obs in obs_list]
                                med_lat = statistics.median(lats)
                                med_lon = statistics.median(lons)
                                med_alt = statistics.median(alts)
                                
                                for idx_obs, obs in enumerate(obs_list):
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
                                fused_lat = sum(obs[0] * w for obs, w in zip(obs_list, weights))
                                fused_lon = sum(obs[1] * w for obs, w in zip(obs_list, weights))
                                fused_alt = sum(obs[2] * w for obs, w in zip(obs_list, weights))
                                
                            fused_lat = max(-90.0, min(90.0, fused_lat))
                            fused_lon = (fused_lon + 180.0) % 360.0 - 180.0
                            fused_alt = max(0.0, fused_alt)
                            
                    reply = {
                        "fused_lat": fused_lat,
                        "fused_lon": fused_lon,
                        "fused_alt": fused_alt,
                        "has_fused": has_fused
                    }
                    s.sendall((json.dumps(reply) + "\n").encode('utf-8'))
            except Exception as e:
                print("Error in Process 2 client loop:", e)
                break
        s.close()
        sys.exit(0)
        
    run_socket_mode_fusion()

# Deterministic generator function to dynamically expand satellite positions in 3D space
def generate_satellites(num_sats):
    sats = {}
    np.random.seed(123)  # Fixed seed for consistent positions across regenerations
    for i in range(1, num_sats + 1):
        # Evenly and deterministically scatter coordinates in three dimensions around the missile flight path
        x = np.random.uniform(-50000.0, 450000.0)
        y = np.random.uniform(-100000.0, 400000.0)
        z = np.random.uniform(150000.0, 300000.0)
        sats[f"Sat {i}"] = np.array([x, y, z])
    return sats

# Global variables dynamically managed
available_sats = {}
sat_names = []
sat_vars = {}

# Load/Save Persistent Settings
script_dir = os.path.dirname(os.path.realpath(__file__))
settings_path = os.path.join(script_dir, "multitest_gui_settings.json")

def load_gui_settings():
    defaults = {
        "max_sats": 3,
        "checked_sats": ["Sat 1", "Sat 2", "Sat 3"],
        "tracking_algorithm": "EKF"
    }
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r") as f:
                loaded = json.load(f)
                defaults.update(loaded)
        except Exception as e:
            print(f"Warning: Could not load GUI settings ({e})")
    return defaults

settings = load_gui_settings()

def save_gui_settings():
    try:
        val_str = max_sat_entry.get().strip()
        max_sats = int(val_str) if val_str else 3
        if max_sats < 1: max_sats = 1
    except ValueError:
        max_sats = 3
        
    checked_sats = [sat for sat in sat_names if sat_vars[sat].get()]
    tracking_algo = algo_var.get()
    
    try:
        with open(settings_path, "w") as f:
            json.dump({
                "max_sats": max_sats, 
                "checked_sats": checked_sats,
                "tracking_algorithm": tracking_algo
            }, f, indent=4)
        print(f"Saved GUI settings to: {settings_path}")
    except Exception as e:
        print(f"Warning: Could not save GUI settings ({e})")

def run_simulation(selected_sats, algorithm):
    np.random.seed(42)  # For reproducible noise
    dt = 1.0            # Time step (seconds)
    total_time = 300    # Total simulation time (seconds)
    time_steps = int(total_time / dt)

    # True physical constants
    g = 9.81            # Gravity (m/s^2) downward along Z-axis

    # Initial State: [x, y, z, vx, vy, vz]
    true_state = np.array([0.0, 0.0, 0.0, 1500.0, 800.0, 3500.0])
    true_trajectory = np.zeros((time_steps, 3))

    for t in range(time_steps):
        true_trajectory[t] = true_state[:3]
        true_state[0] += true_state[3] * dt
        true_state[1] += true_state[4] * dt
        true_state[2] += true_state[5] * dt - 0.5 * g * (dt**2)
        true_state[5] -= g * dt
        
        if true_state[2] < 0 and t > 10:
            true_trajectory = true_trajectory[:t]
            time_steps = t
            break

    # Measurement noise characteristics (Standard deviation in meters)
    noise_std = 15000.0 
    R_matrix = np.eye(3) * (noise_std**2)  # Measurement noise covariance matrix

    # Generate noisy range measurements for each selected satellite
    measurements = {sat: np.zeros((time_steps, 3)) for sat in selected_sats}

    for t in range(time_steps):
        true_pos = true_trajectory[t]
        for sat_name in selected_sats:
            # 1. Base Gaussian measurement noise
            noise = np.random.normal(0, noise_std, size=3)
            
            # 2. Inject random massive Anomaly Spikes/Outliers (10% chance of a massive 60km-80km spike!)
            if np.random.random() < 0.10:
                anomaly_direction = np.random.choice([-1.0, 1.0], size=3)
                anomaly_spike = anomaly_direction * np.random.uniform(60000.0, 80000.0)
                noise += anomaly_spike
                
            measurements[sat_name][t] = true_pos + noise

    # State Vector: [x, y, z, vx, vy, vz]
    kf_state = np.array([1000.0, -1000.0, 500.0, 1400.0, 850.0, 3400.0])
    P = np.eye(6) * 10000.0
    Q = np.eye(6) * 1.0
    
    A = np.eye(6)
    A[0, 3] = dt
    A[1, 4] = dt
    A[2, 5] = dt
    B = np.array([0, 0, -0.5 * dt**2, 0, 0, -dt])

    estimated_trajectory = np.zeros((time_steps, 3))
    rejected_points_count = 0  # To log how many bad measurements we filter out in HKF!

    for t in range(time_steps):
        # --- STEP A: PREDICT ---
        kf_state = A @ kf_state + B * g
        P = A @ P @ A.T + Q
        
        # --- STEP B: UPDATE (Fuse measurements from all selected satellites) ---
        for sat_name in selected_sats:
            z_measured = measurements[sat_name][t]
            H = np.zeros((3, 6))
            H[0, 0] = 1.0; H[1, 1] = 1.0; H[2, 2] = 1.0
            
            z_predicted = H @ kf_state
            y = z_measured - z_predicted
            
            S = H @ P @ H.T + R_matrix
            S_inv = np.linalg.inv(S)
            
            # --- OUTLIER DETECTION (Chi-Square Anomaly Rejection & Huber Kalman) ---
            if algorithm == "HKF":
                # Compute Mahalanobis Distance squared of the measurement residual
                mahalanobis_dist_sq = y.T @ S_inv @ y
                
                # Gating outlier rejection: if Mahalanobis distance squared exceeds our threshold of 9.0 (Chi-square gate),
                # we flag this satellite's measurement as bad/anomalous and completely REMOVE/REJECT it from updating!
                if mahalanobis_dist_sq > 9.0:
                    rejected_points_count += 1
                    continue # Skip this anomalous update cleanly!
                    
                # Huber M-Estimation Downweighting for moderate boundary outliers:
                k_huber = 1.5
                d_mahalanobis = np.sqrt(mahalanobis_dist_sq)
                if d_mahalanobis > k_huber:
                    # Scale down the measurement influence by inflating its covariance
                    huber_weight = k_huber / d_mahalanobis
                    R_scaled = R_matrix / huber_weight
                    S = H @ P @ H.T + R_scaled
                    S_inv = np.linalg.inv(S)
            
            # Standard Kalman update
            K = P @ H.T @ S_inv
            kf_state = kf_state + K @ y
            P = (np.eye(6) - K @ H) @ P
            
        estimated_trajectory[t] = kf_state[:3]

    if algorithm == "HKF":
        print(f"[HKF INFO] Successfully detected and rejected {rejected_points_count} anomalous satellite measurements!")

    # Calculate simple average of raw measurements (Trajectory without EKF)
    raw_average_trajectory = np.zeros((time_steps, 3))
    for t in range(time_steps):
        sum_pos = np.zeros(3)
        for sat_name in selected_sats:
            sum_pos += measurements[sat_name][t]
        raw_average_trajectory[t] = sum_pos / len(selected_sats)

    # ---------------------------------------------------------
    # VISUALIZATION
    # ---------------------------------------------------------
    fig = plt.figure(figsize=(16, 8))

    # Subplot 1: 3D Trajectory Plot
    ax1 = fig.add_subplot(1, 2, 1, projection='3d')
    ax1.plot(true_trajectory[:, 0], true_trajectory[:, 1], true_trajectory[:, 2], 
            label='True Missile Trajectory', color='black', linewidth=3)
    ax1.plot(estimated_trajectory[:, 0], estimated_trajectory[:, 1], estimated_trajectory[:, 2], 
            label=f'{algorithm} Optimized Prediction', color='limegreen', linestyle='--', linewidth=2)
    ax1.plot(raw_average_trajectory[:, 0], raw_average_trajectory[:, 1], raw_average_trajectory[:, 2], 
            label='Trajectory without EKF (Raw Average)', color='orange', linestyle=':', linewidth=1.5)

    # Color mapping for raw trajectories
    colors = ['crimson', 'royalblue', 'darkorange', 'purple', 'teal', 'magenta', 'brown', 'forestgreen', 'darkblue', 'olive']
    for idx, sat_name in enumerate(selected_sats):
        c = colors[idx % len(colors)]
        ax1.plot(measurements[sat_name][:, 0], measurements[sat_name][:, 1], measurements[sat_name][:, 2], 
                label=f'{sat_name} Raw Trajectory', color=c, alpha=0.25, linewidth=1)

    # Plot Satellite Positions
    for sat_name in selected_sats:
        sat_pos = available_sats[sat_name]
        ax1.scatter(sat_pos[0], sat_pos[1], sat_pos[2], marker='^', s=100, label=f'{sat_name} Position')

    ax1.set_title(f"Multi-Satellite Missile Tracking & Data Fusion (3D - {len(selected_sats)} Sats)", fontsize=12, fontweight='bold')
    ax1.set_xlabel("X Distance (m)")
    ax1.set_ylabel("Y Distance (m)")
    ax1.set_zlabel("Altitude (m)")
    ax1.legend(loc='upper left', fontsize=8)

    # Subplot 2: 2D Position Error over Time
    ax2 = fig.add_subplot(1, 2, 2)
    raw_errors = np.linalg.norm(raw_average_trajectory - true_trajectory, axis=1)
    ekf_errors = np.linalg.norm(estimated_trajectory - true_trajectory, axis=1)
    time_axis = np.arange(time_steps) * dt

    ax2.plot(time_axis, raw_errors, label='Raw Average Position Error', color='orange', linestyle=':', linewidth=1.5)
    ax2.plot(time_axis, ekf_errors, label=f'{algorithm} Optimized Position Error', color='limegreen', linewidth=2)

    ax2.set_title(f"Tracking Accuracy Comparison ({algorithm} vs Raw)", fontsize=12, fontweight='bold')
    ax2.set_xlabel("Time (seconds)")
    ax2.set_ylabel("3D Position Error (meters)")
    ax2.grid(True, linestyle='--', alpha=0.6)
    ax2.legend()

    plt.suptitle(f"{algorithm} Performance Evaluation (Severe Outliers & Spikes Added)", fontsize=14, fontweight='bold', y=0.96)
    plt.show()

# ---------------------------------------------------------
# GUI DEVELOPMENT
# ---------------------------------------------------------
root = tk.Tk()
root.title("Missile Tracking Simulation Setup")
root.geometry("480x320")
root.resizable(False, False)

# Try to center on screen
root.update_idletasks()
width = root.winfo_width()
height = root.winfo_height()
x = (root.winfo_screenwidth() // 2) - (width // 2)
y = (root.winfo_screenheight() // 2) - (height // 2)
root.geometry(f'{width}x{height}+{x}+{y}')

style = ttk.Style(root)
available_themes = style.theme_names()
if 'vista' in available_themes:
    style.theme_use('vista')
elif 'clam' in available_themes:
    style.theme_use('clam')

main_frame = ttk.Frame(root, padding="15 15 15 15")
main_frame.pack(fill=tk.BOTH, expand=True)

# Title label
title_lbl = ttk.Label(
    main_frame, 
    text="Missile Tracking & Data Fusion", 
    font=("Segoe UI", 12, "bold")
)
title_lbl.pack(anchor=tk.W, pady=(0, 5))

desc_lbl = ttk.Label(
    main_frame,
    text="Configure the satellite constellation and algorithm parameters:",
    font=("Segoe UI", 9)
)
desc_lbl.pack(anchor=tk.W, pady=(0, 15))

# Controls Frame
ctrl_frame = ttk.LabelFrame(main_frame, text=" Constellation Settings ", padding="12")
ctrl_frame.pack(fill=tk.X, pady=(0, 15))

# Row 1 of Controls: Max Satellites Entry & Dropdown
row1_frame = ttk.Frame(ctrl_frame)
row1_frame.pack(fill=tk.X, pady=(0, 5))

max_sat_lbl = ttk.Label(row1_frame, text="Max of Satellite:", font=("Segoe UI", 9, "bold"))
max_sat_lbl.pack(side=tk.LEFT, padx=(0, 8))

max_sat_entry = ttk.Entry(row1_frame, width=8)
max_sat_entry.pack(side=tk.LEFT, padx=(0, 15))

# Row 2 of Controls: Algorithm Checkboxes
row2_frame = ttk.Frame(ctrl_frame)
row2_frame.pack(fill=tk.X, pady=(5, 0))

algo_lbl = ttk.Label(row2_frame, text="Tracking Algorithm:", font=("Segoe UI", 9, "bold"))
algo_lbl.pack(side=tk.LEFT, padx=(0, 8))

algo_var = tk.StringVar(value=settings["tracking_algorithm"])

rb_ekf = ttk.Radiobutton(row2_frame, text="EKF", variable=algo_var, value="EKF")
rb_ekf.pack(side=tk.LEFT, padx=(5, 10))

rb_hkf = ttk.Radiobutton(row2_frame, text="HKF (Huber Robust)", variable=algo_var, value="HKF")
rb_hkf.pack(side=tk.LEFT, padx=(5, 10))

# Pre-population variables dictionary for checkboxes
def rebuild_satellites_list():
    global available_sats, sat_names, sat_vars
    
    try:
        val_str = max_sat_entry.get().strip()
        max_sats = int(val_str) if val_str else 3
        if max_sats < 1: max_sats = 1
    except ValueError:
        max_sats = 3
        
    # Dynamically expand and generate 'max_sats' satellite nodes with deterministic 3D locations
    available_sats = generate_satellites(max_sats)
    sat_names = list(available_sats.keys())
    
    # Track which ones were already checked to keep them checked!
    old_checked = {name for name, var in sat_vars.items() if var.get()} if sat_vars else set()
    
    if not sat_vars:
        # First startup: restore from loaded settings, fallback to first 3 checked
        sat_vars = {sat: tk.BooleanVar(value=(sat in settings["checked_sats"] or (not settings["checked_sats"] and idx < 3))) for idx, sat in enumerate(sat_names)}
    else:
        # Rebuilding: preserve checked status for remaining indices, default new ones to False
        sat_vars = {sat: tk.BooleanVar(value=(sat in old_checked)) for sat in sat_names}

popup = None

def destroy_popup():
    global popup
    if popup and popup.winfo_exists():
        popup.grab_release()
        popup.destroy()
    popup = None
    try:
        root.unbind_all("<Button-1>")
        root.unbind_all("<MouseWheel>")
    except Exception:
        pass

def update_dropdown_button_text():
    checked_count = sum(1 for var in sat_vars.values() if var.get())
    try:
        val_str = max_sat_entry.get().strip()
        max_sats = int(val_str) if val_str else len(available_sats)
        if max_sats < 1: max_sats = 1
    except ValueError:
        max_sats = len(available_sats)
    menubutton.config(text=f"{checked_count} of {max_sats} Satellites Selected ▼")

def on_check_click(sat_name):
    try:
        val_str = max_sat_entry.get().strip()
        max_sats = int(val_str) if val_str else len(available_sats)
        if max_sats < 1: max_sats = 1
    except ValueError:
        max_sats = len(available_sats)
        
    checked_count = sum(1 for var in sat_vars.values() if var.get())
    
    if checked_count > max_sats:
        sat_vars[sat_name].set(False) # Revert checking this satellite
        messagebox.showwarning(
            "Selection Limit Reached",
            f"You can select at most {max_sats} satellites, as defined by the 'Max of Satellite' setting."
        )
    update_dropdown_button_text()

def toggle_popup():
    global popup
    if popup and popup.winfo_exists():
        destroy_popup()
        return
        
    # Rebuild checklist with latest max_sats value before rendering dropdown!
    rebuild_satellites_list()
    
    popup = tk.Toplevel(root)
    popup.overrideredirect(True)
    
    x = menubutton.winfo_rootx()
    y = menubutton.winfo_rooty() + menubutton.winfo_height()
    w = menubutton.winfo_width()
    h = 220 # dropdown list height
    
    popup.geometry(f"{w}x{h}+{x}+{y}")
    
    popup.focus_set()
    popup.grab_set()
    
    frame = tk.Frame(popup, bd=1, relief=tk.SOLID, background="white")
    frame.pack(fill=tk.BOTH, expand=True)
    
    # Scrollable list inside popup
    canvas = tk.Canvas(frame, background="white", highlightthickness=0)
    v_scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=canvas.yview)
    scroll_frame = tk.Frame(canvas, background="white")
    
    scroll_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    canvas_window = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    canvas.configure(yscrollcommand=v_scrollbar.set)
    
    # Pack scrollbar FIRST so it gets firmly docked on the right and never squeezed out of view!
    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    # Auto-stretch the checkbox container to match the exact width of the dropdown popup
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))
    
    for sat in sat_names:
        cb = tk.Checkbutton(
            scroll_frame,
            text=f"{sat} Tracking",
            variable=sat_vars[sat],
            command=lambda s=sat: on_check_click(s),
            background="white",
            activebackground="#e9ecef",
            anchor="w",
            padx=8,
            pady=3,
            font=("Segoe UI", 9)
        )
        cb.pack(fill=tk.X, expand=True, anchor="w")
        
    def on_mouse_wheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
    canvas.bind("<Enter>", lambda _: canvas.bind_all("<MouseWheel>", on_mouse_wheel))
    canvas.bind("<Leave>", lambda _: canvas.unbind_all("<MouseWheel>"))
    
    def on_click_outside(event):
        if popup and popup.winfo_exists():
            x_root = event.x_root
            y_root = event.y_root
            px1, py1 = popup.winfo_rootx(), popup.winfo_rooty()
            px2, py2 = px1 + popup.winfo_width(), py1 + popup.winfo_height()
            
            bx1, by1 = menubutton.winfo_rootx(), menubutton.winfo_rooty()
            bx2, by2 = bx1 + menubutton.winfo_width(), by1 + menubutton.winfo_height()
            
            if not (px1 <= x_root <= px2 and py1 <= y_root <= py2) and \
               not (bx1 <= x_root <= bx2 and by1 <= y_root <= by2):
                destroy_popup()
                
    popup.bind_all("<Button-1>", on_click_outside)

# Dropdown Button trigger
menubutton = ttk.Button(row1_frame, text="3 of 3 Satellites Selected ▼", command=toggle_popup)
menubutton.pack(fill=tk.X, side=tk.LEFT, expand=True)

# Pre-populate Max Satellites entry and build list on startup
max_sat_entry.insert(0, str(settings["max_sats"]))
rebuild_satellites_list()
update_dropdown_button_text()

def on_entry_change(event):
    # Rebuild available list to the new max constraint size, and refresh button text
    rebuild_satellites_list()
    update_dropdown_button_text()

max_sat_entry.bind("<KeyRelease>", on_entry_change)

# Alignment auto-adjust
def on_window_configure(event):
    if popup and popup.winfo_exists():
        x = menubutton.winfo_rootx()
        y = menubutton.winfo_rooty() + menubutton.winfo_height()
        w = menubutton.winfo_width()
        popup.geometry(f"{w}x220+{x}+{y}")
root.bind("<Configure>", on_window_configure)

# Action Buttons
btn_frame = ttk.Frame(main_frame)
btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

def on_exit():
    destroy_popup()
    save_gui_settings()
    root.destroy()

def on_run():
    destroy_popup()
    
    # 1. Read input
    try:
        val_str = max_sat_entry.get().strip()
        val = int(val_str)
        if val <= 0:
            raise ValueError()
    except ValueError:
        messagebox.showwarning(
            "Invalid Input",
            "Please enter a valid positive integer for Max of Satellite."
        )
        return
        
    selected_sats = [sat for sat in sat_names if sat_vars[sat].get()]
    if not selected_sats:
        messagebox.showwarning(
            "No Satellites Selected",
            "Please select at least one satellite from the dropdown to run the simulation."
        )
        return
        
    # Save settings on successful run
    save_gui_settings()
    
    # 2. Run simulation and plotting natively
    run_simulation(selected_sats, algo_var.get())

btn_exit = ttk.Button(btn_frame, text="Exit", command=on_exit)
btn_exit.pack(side=tk.RIGHT, padx=5)

btn_run = ttk.Button(btn_frame, text="Run", command=on_run)
btn_run.pack(side=tk.RIGHT, padx=5)

root.protocol("WM_DELETE_WINDOW", on_exit)
root.bind("<Return>", lambda event: on_run())

root.mainloop()
