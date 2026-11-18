#build_exe
import os
import subprocess
import sys
import shutil

print("==================================================================")
print("  MISSILE INTERCEPT SIMULATION COMPILER ENGINE  ")
print("==================================================================\n")

# 1. Install PyInstaller in the virtual environment
print("[Step 1/3] Installing PyInstaller compiler...")
try:
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    print("  -> PyInstaller installed successfully!\n")
except Exception as e:
    print("  -> Error installing PyInstaller:", e)
    sys.exit(1)

# 2. Build the compilation command
print("[Step 2/3] Packing and compiling assets...")

# Define paths
cwd = os.getcwd()
msl_warn_path = os.path.join("test_msl2", "mslwarntest.py")

cmd = [
    os.path.join(".venv", "Scripts", "pyinstaller"),
    "--noconfirm",
    "--onedir",
    "--windowed", # Hides standard terminal window on launch
    "--name=Missile_Intercept_Simulation",
    # Add local satellites database
    f"--add-data=test_msl2/satellites.json{os.pathsep}test_msl2",
    # Add Leaflet local offline files
    f"--add-data=test_msl2/leaflet_offline.js{os.pathsep}test_msl2",
    f"--add-data=test_msl2/leaflet_offline.css{os.pathsep}test_msl2",
    f"--add-data=test_msl2/offline_world_map.jpg{os.pathsep}test_msl2",
    # Add other python code files
    f"--add-data=test_msl2/updatemap.py{os.pathsep}test_msl2",
    f"--add-data=test_msl2/impact.py{os.pathsep}test_msl2",
    f"--add-data=test_msl2/mslsimwindow.py{os.pathsep}test_msl2",
    f"--add-data=test_msl2/msltest2.py{os.pathsep}test_msl2",
    # Target starting script
    msl_warn_path
]

try:
    subprocess.run(cmd, check=True)
    print("  -> Main executable compilation completed successfully!\n")
except Exception as e:
    print("  -> Error compiling main executable:", e)
    sys.exit(1)

# 2b. Compile updatemap.py as a secondary companion executable (using --onefile)
print("[Step 2b/3] Compiling updatemap.py companion server...")
cmd_update = [
    os.path.join(".venv", "Scripts", "pyinstaller"),
    "--noconfirm",
    "--onefile",
    "--console",
    "--name=updatemap",
    os.path.join("test_msl2", "updatemap.py")
]

try:
    subprocess.run(cmd_update, check=True)
    print("  -> Companion server compilation completed successfully!\n")
except Exception as e:
    print("  -> Error compiling companion server:", e)
    sys.exit(1)

# 3. Copy Coastline Shapefiles, Companion Server, & Custom Settings directly to the output folder
print("[Step 3/3] Copying geographic assets, companion server & custom configuration settings...")
dist_dir = os.path.join("dist", "Missile_Intercept_Simulation")

# Copy the compiled updatemap.exe into the main executable folder and its _internal folder
try:
    src_update = os.path.join("dist", "updatemap.exe")
    if os.path.exists(src_update):
        shutil.copy(src_update, os.path.join(dist_dir, "updatemap.exe"))
        shutil.copy(src_update, os.path.join(dist_dir, "_internal", "updatemap.exe"))
        print("  -> Companion server updatemap.exe copied successfully!")
except Exception as ue:
    print("  -> Error copying companion server updatemap.exe:", ue)

shape_files = [
    "ne_10m_coastline.shp",
    "ne_10m_coastline.shx",
    "ne_10m_coastline.dbf",
    "ne_110m_admin_0_boundary_lines_land.shp",
    "ne_110m_admin_0_boundary_lines_land.shx",
    "ne_110m_admin_0_boundary_lines_land.dbf",
    "leaflet_offline.js",
    "leaflet_offline.css",
    "offline_world_map.jpg"
]

copied_count = 0
for f_name in shape_files:
    if os.path.exists(f_name):
        shutil.copy(f_name, os.path.join(dist_dir, f_name))
        copied_count += 1

# Copy custom settings so the executable inherits your exact window geometry, globe positions, and satellite configurations!
config_files = [
    ("test_msl2/mslwarntest_settings.json", "mslwarntest_settings.json"),
    ("test_msl2/mslwarntest_settings.json", "_internal/mslwarntest_settings.json"),
    ("test_msl2/mslwarntest_settings.json", "test_msl2/mslwarntest_settings.json"),
    ("test_msl2/map_window_settings.json", "test_msl2/map_window_settings.json"),
    ("impact_window_settings.json", "impact_window_settings.json"),
    ("test_msl2/satellites.json", "test_msl2/satellites.json")
]

for src, rel_dest in config_files:
    if os.path.exists(src):
        dest_path = os.path.join(dist_dir, rel_dest)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy(src, dest_path)
        copied_count += 1

print(f"  -> Copied {copied_count} geographic and settings assets into the executable folder!\n")

print("==================================================================")
print("  SUCCESS! MISSILE SIMULATION EXECUTABLE READY  ")
print("==================================================================")
print(f"Output folder: {os.path.abspath(dist_dir)}")
print("\nInstructions for your Presentation:")
print("1. Copy the entire 'Missile_Intercept_Simulation' folder from 'dist/' onto a USB flash drive.")
print("2. Paste the folder onto your laptop in the conference room.")
print("3. Double-click 'Missile_Intercept_Simulation.exe' to launch and run the presentation instantly!")
print("   (No Python installations or internet connections are required!)")
print("==================================================================\n")

##############################################################
#env_check.py
import sys
print(sys.executable)
print(sys.version)
try:
    import segment_anything
    print("segment_anything found")
except ImportError:
    print("segment_anything NOT found")

###############################################
# find_color_outliers.py
import cv2
import numpy as np

img = cv2.imread("testfiles/normal/n1.png")
h, w, _ = img.shape

max_ch = np.max(img, axis=2)
min_ch = np.min(img, axis=2)
color_mask = (max_ch - min_ch) > 40  # Colorful scatter points

y_indices, x_indices = np.where(color_mask)
points = np.vstack((x_indices, y_indices)).T

hull = cv2.convexHull(points)
peri = cv2.arcLength(hull, True)
polygon = cv2.approxPolyDP(hull, 0.01 * peri, True)

poly_mask = np.zeros((h, w), dtype=np.uint8)
cv2.fillPoly(poly_mask, [polygon], 255)
outside_mask = cv2.bitwise_not(poly_mask)

outside_color_mask = cv2.bitwise_and(outside_mask, outside_mask, mask=color_mask.astype(np.uint8) * 255)
y_coords, x_coords = np.where(outside_color_mask > 0)

if len(x_coords) > 0:
    print(f"Found {len(x_coords)} outside color pixels. Sample coords:")
    for idx in range(min(10, len(x_coords))):
        print(f"  - ({x_coords[idx]}, {y_coords[idx]}): BGR: {img[y_coords[idx], x_coords[idx]]}")
    
    # Save a patch around the first outside pixel
    cx, cy = x_coords[0], y_coords[0]
    patch = img[max(0, cy-100):min(h, cy+100), max(0, cx-100):min(w, cx+100)]
    cv2.imwrite("color_patch.png", patch)
    print("Saved patch of first outlier to color_patch.png")

#######################################################################
#sync_settings.py
#find_color_outliers
import os
import shutil

print("==================================================================")
print("  MISSILE SIMULATION SETTINGS & GEOGRAPHY SYNC ENGINE  ")
print("==================================================================\n")

dist_dir = os.path.join("dist", "Missile_Intercept_Simulation")

if not os.path.exists(dist_dir):
    print("❌ ERROR: Compiled folder 'dist/Missile_Intercept_Simulation' not found!")
    print("   Please compile your executable first by running: .venv/Scripts/python.exe build_exe.py")
    os._exit(1)

# List of all standard static assets and shapefiles
shape_files = [
    "ne_10m_coastline.shp",
    "ne_10m_coastline.shx",
    "ne_10m_coastline.dbf",
    "ne_110m_admin_0_boundary_lines_land.shp",
    "ne_110m_admin_0_boundary_lines_land.shx",
    "ne_110m_admin_0_boundary_lines_land.dbf",
    "leaflet_offline.js",
    "leaflet_offline.css",
    "offline_world_map.jpg"
]

copied_count = 0
for f_name in shape_files:
    if os.path.exists(f_name):
        shutil.copy(f_name, os.path.join(dist_dir, f_name))
        copied_count += 1

# List of all custom settings and configuration files to sync
config_files = [
    ("test_msl2/mslwarntest_settings.json", "mslwarntest_settings.json"),
    ("test_msl2/mslwarntest_settings.json", "_internal/mslwarntest_settings.json"),
    ("test_msl2/mslwarntest_settings.json", "test_msl2/mslwarntest_settings.json"),
    ("test_msl2/map_window_settings.json", "test_msl2/map_window_settings.json"),
    ("impact_window_settings.json", "impact_window_settings.json"),
    ("test_msl2/satellites.json", "test_msl2/satellites.json")
]

for src, rel_dest in config_files:
    if os.path.exists(src):
        dest_path = os.path.join(dist_dir, rel_dest)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy(src, dest_path)
        copied_count += 1

print(f"  SUCCESS! Synchronized and updated {copied_count} assets & settings files!")
print(f"   Your compiled folder '{dist_dir}' now contains your absolute latest configurations!")
print("==================================================================\n")
#####################################################################################
# testmap.py
import webview
import sys

print("Python sys.executable:", sys.executable)
print("Opening a test webview window...")
try:
    win = webview.create_window("Missile Warning Map - Live Display", "https://pywebview.flowrl.com/hello.html")
    webview.start()
    print("Success!")
except Exception as e:
    print("Error launching webview:", e)

####################################################
#verifyinputfile.py
import os
import sys
import pandas as pd
from pathlib import Path
import datetime
import platform

def main():
    print("==================================================================")
    print("  SATELLITE REVOLUTION ANOMALY VERIFIER (verifyinputfile.py)  ")
    print("==================================================================\n")
    test_flag = False
    test2_flag = True ##True: for test only
    test_folder = "/2026/testonly/"
    keys = ["*.xlsx"]

    # Cross-platform network path resolution
    if platform.system() == "Windows":
    #    network_path = r"\\159.4.50.205\m26814\home\rain\scratch\users\m26814\Plot_GeolocationOffset"
    ##    network_path = r"\\159.4.50.205\m26814\home\rain\scratch\dmsp\SSMIS_GeolocationTools\F18GeoOffset"
        if test2_flag:
    #        network_path = r"C:\tmp\pythontest\offset_merge\output2\21_12-26_10"
    #       network_path = r"C:\tmp\pythontest\offset_merge\output2\testonly"
            network_path = r"\\159.4.50.205\m26814\home\rain\scratch\dmsp\SSMIS_GeolocationTools\F18GeoOffset"
        else:
            network_path = r"\\159.4.50.205\m26814\home\rain\scratch\users\m26814\Plot_GeolocationOffset"
    else:
        network_path = "/scratch/users/m26814/Plot_GeolocationOffset/2025"
    # 1. Parse Command Line Arguments
    if len(sys.argv) < 3:
        # print("[ERROR] Missing required arguments!")
        # print("Usage: python verifyinputfile.py <path_of_folder> <file_type>")
        # print("Example: python verifyinputfile.py \"\\\\159.4.50.205\\m26814\\home\\rain\\scratch\\dmsp\\SSMIS_GeolocationTools\\F18GeoOffset\" \"*.xlsx\"")
        # sys.exit(1)
        folder_path_str = network_path
        file_pattern = keys[0]
    else:
        folder_path_str = sys.argv[1]
        file_pattern = sys.argv[2]
        
    
    folder_path = Path(folder_path_str)
    if not folder_path.exists() or not folder_path.is_dir():
        print(f"[ERROR] Folder path '{folder_path_str}' does not exist or is not a directory!")
        sys.exit(1)
        
    print(f"Scanning Folder: {folder_path.absolute()}")
    print(f"File Wildcard:   {file_pattern}\n")
    
    # 2. Gather All Matching Excel Files & Extract Initial Conditions
    print("Reading and parsing files recursively...")
    file_records = []
    excel_files = list(folder_path.rglob(file_pattern))
    
    total_scanned = 0
    epoch = datetime.datetime(2020, 1, 1)
    
    anomalies_internal = []  # List to hold internal file jumps (like row-to-row jumps in the same file)
    
    for p_file in excel_files:
        if p_file.name.startswith("~$"):
            continue
            
        try:
            # Read full file to inspect internal row-to-row jumps
            df = pd.read_excel(p_file, header=None)
            if df.shape[0] > 0 and df.shape[1] >= 17:
                total_scanned += 1
                
                # Extract initial conditions from the first row
                r_first = float(df.iloc[0, 0])
                sec_of_day = float(df.iloc[0, 13])
                yr = int(df.iloc[0, 14])
                doy = int(df.iloc[0, 15])
                date_val = int(df.iloc[0, 16])
                
                # Calculate fractional absolute day count since epoch
                dt = datetime.datetime(yr, 1, 1) + datetime.timedelta(days=doy - 1, seconds=sec_of_day)
                abs_days = (dt - epoch).total_seconds() / 86400.0
                
                # Check for internal revolution jumps inside the file itself!
                revs = df[0].values
                dates = df[16].values
                for j in range(1, len(revs)):
                    R_prev = revs[j - 1]
                    R_curr = revs[j]
                    
                    # Standard modulo 100,000 unwrap
                    R_curr_un = R_curr
                    if R_curr_un < R_prev:
                        while R_curr_un <= R_prev:
                            R_curr_un += 100000
                            
                    if (R_curr_un - R_prev) > 500:
                        # An internal anomaly is detected!
                        # Excel row index is 1-based, so row j (0-based) is Excel row j+1, row j-1 is Excel row j
                        anomalies_internal.append({
                            'file': p_file.name,
                            'path': p_file.absolute(),
                            'row_prev': j,      # Excel row number (1-based index)
                            'row_curr': j + 1,  # Excel row number (1-based index)
                            'rev_prev': R_prev,
                            'rev_curr': R_curr,
                            'date': dates[j],
                            'reason': f"Internal jump of {R_curr - R_prev:.1f} revolutions between Excel row {j} and {j+1} on date {dates[j]}!"
                        })
                        break  # Only need to flag each file once
                
                file_records.append({
                    'path': p_file,
                    'name': p_file.name,
                    'first_rev': r_first,
                    'sec_of_day': sec_of_day,
                    'year': yr,
                    'doy': doy,
                    'date': date_val,
                    'abs_days': abs_days
                })
        except Exception:
            pass
            
    print(f"  -> Successfully loaded {total_scanned} files.\n")
    
    # 3. Scan Chronologically for Strange File-to-File Revolution Jumps
    anomalies_chronological = []
    if len(file_records) >= 2:
        # Sort Chronologically by Absolute Day Time
        file_records.sort(key=lambda x: x['abs_days'])
        
        print("Verifying chronological file-to-file timeline...")
        for idx in range(1, len(file_records)):
            prev = file_records[idx - 1]
            curr = file_records[idx]
            
            # Calculate time difference in days
            delta_days = curr['abs_days'] - prev['abs_days']
            
            # Nominal expected revolution increase (14.17 revs/day)
            expected_rev_increase = delta_days * 14.17
            
            # Calculate actual revolution difference
            R_prev = prev['first_rev']
            R_curr = curr['first_rev']
            
            # Handle potential standard 100,000 modulo rollovers
            R_curr_unwrapped = R_curr
            if R_curr_unwrapped < R_prev:
                while R_curr_unwrapped <= R_prev:
                    R_curr_unwrapped += 100000
                    
            actual_rev_diff_unwrapped = R_curr_unwrapped - R_prev
            
            # Measure deviation from nominal orbital physics
            deviation = abs(actual_rev_diff_unwrapped - expected_rev_increase)
            
            is_anomaly = False
            reason = ""
            
            if deviation > 500:
                is_anomaly = True
                reason = f"Revolution jumped by {actual_rev_diff_unwrapped:.1f} over just {delta_days:.3f} days (Nominal expectation: {expected_rev_increase:.1f} revs)."
            elif curr['date'] == prev['date'] and abs(R_curr - R_prev) > 100:
                is_anomaly = True
                reason = f"Same date ({curr['date']}) but revolution jumped by {abs(R_curr - R_prev):.1f} passes (nominally can only be 14.17 per day)."
                
            if is_anomaly:
                # Make sure this isn't triggered by an internal mixed file itself (avoid double-reporting)
                is_duplicate = any(a['file'] == curr['name'] for a in anomalies_internal)
                if not is_duplicate:
                    anomalies_chronological.append({
                        'prev_file': prev['name'],
                        'prev_path': prev['path'].absolute(),
                        'prev_rev': R_prev,
                        'prev_date': prev['date'],
                        'curr_file': curr['name'],
                        'curr_path': curr['path'].absolute(),
                        'curr_rev': R_curr,
                        'curr_date': curr['date'],
                        'delta_days': delta_days,
                        'reason': reason
                    })
            
    # 4. Output Summary & Results
    total_anomalies = len(anomalies_internal) + len(anomalies_chronological)
    print("==================================================================")
    print("  VERIFICATION RESULTS SUMMARY")
    print("==================================================================")
    print(f"Total Files Scanned:             {total_scanned}")
    print(f"Internal File Row Jumps Found:   {len(anomalies_internal)}")
    print(f"Chronological File Jumps Found:  {len(anomalies_chronological)}")
    print(f"Total Unique Anomalies Found:    {total_anomalies}")
    print("==================================================================\n")
    
    if total_anomalies > 0:
        # Report internal row-to-row anomalies first
        if len(anomalies_internal) > 0:
            print("==================================================================")
            print("  INTERNAL FILE ROW JUMPS DETECTED (Mixed data inside same file!)")
            print("==================================================================")
            for i, anomaly in enumerate(anomalies_internal):
                print(f"  [INTERNAL ANOMALY #{i+1}]")
                print(f"   File Name: {anomaly['file']}")
                print(f"   Jump Details: Excel Row {anomaly['row_prev']} (Rev={int(anomaly['rev_prev'])}) -> Excel Row {anomaly['row_curr']} (Rev={int(anomaly['rev_curr'])})")
                print(f"   Date:      {anomaly['date']}")
                print(f"   Path:      {anomaly['path']}\n")
                
        # Report chronological file-to-file anomalies
        if len(anomalies_chronological) > 0:
            print("==================================================================")
            print("  CHRONOLOGICAL FILE JUMPS DETECTED (Mismatched file sequence!)")
            print("==================================================================")
            for i, anomaly in enumerate(anomalies_chronological):
                print(f"  [CHRONOLOGICAL ANOMALY #{i+1}]")
                print(f"   Previous File: {anomaly['prev_file']} (Rev={int(anomaly['prev_rev'])}, Date={anomaly['prev_date']})")
                print(f"   Current File:  {anomaly['curr_file']} (Rev={int(anomaly['curr_rev'])}, Date={anomaly['curr_date']})")
                print(f"   Time Elapsed:  {anomaly['delta_days']:.3f} days")
                print(f"   Mismatch Issue: {anomaly['reason']}")
                print(f"   Path:          {anomaly['curr_path']}\n")
            
        print("==================================================================")
        print("  RECOMMENDATION:")
        print("   The files flagged above likely contain mixed data from another satellite")
        print("   (for example, F17 or F16 files mixed into an F18 folder).")
        print("   Please inspect, edit, or move the flagged files to restore perfect folder hygiene!")
        print("==================================================================\n")
    else:
        print("  SUCCESS: Perfect folder hygiene! No strange revolution jumps or mixed-satellite files detected!")
        print("==================================================================\n")

if __name__ == "__main__":
    main()
######################################################
# diagnose_pics.py
import cv2
import numpy as np
import glob
import os

normal_files = glob.glob("testfiles/normal/*.png")
anomaly_files = glob.glob("testfiles/anomalys/*.png")

print("=== DIAGNOSING NORMAL IMAGES ===")
for f in normal_files:
    img = cv2.imread(f)
    if img is not None:
        h, w, c = img.shape
        mean_bgr = np.mean(img, axis=(0,1))
        max_bgr = np.max(img, axis=(0,1))
        min_bgr = np.min(img, axis=(0,1))
        print(f"File: {os.path.basename(f)} | Shape: {h}x{w} | Mean BGR: {mean_bgr.round(1)} | Max BGR: {max_bgr} | Min BGR: {min_bgr}")

print("\n=== DIAGNOSING ANOMALY IMAGES ===")
for f in anomaly_files:
    img = cv2.imread(f)
    if img is not None:
        h, w, c = img.shape
        mean_bgr = np.mean(img, axis=(0,1))
        max_bgr = np.max(img, axis=(0,1))
        min_bgr = np.min(img, axis=(0,1))
        print(f"File: {os.path.basename(f)} | Shape: {h}x{w} | Mean BGR: {mean_bgr.round(1)} | Max BGR: {max_bgr} | Min BGR: {min_bgr}")
#######################################################
# test_hull.py
import cv2
import numpy as np

img = cv2.imread("testfiles/normal/n1.png")
h, w, _ = img.shape

max_ch = np.max(img, axis=2)
min_ch = np.min(img, axis=2)
color_mask = (max_ch - min_ch) > 40  # Colorful scatter points

y_indices, x_indices = np.where(color_mask)
points = np.vstack((x_indices, y_indices)).T

if len(points) > 0:
    # Use the raw convex hull directly to guarantee 100% tight containment!
    polygon = cv2.convexHull(points)
    
    poly_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(poly_mask, [polygon], 255)
    outside_mask = cv2.bitwise_not(poly_mask)
    
    outside_color_mask = cv2.bitwise_and(outside_mask, outside_mask, mask=color_mask.astype(np.uint8) * 255)
    y_coords, x_coords = np.where(outside_color_mask > 0)
    print(f"File: n1.png | Outside Color Pixels with raw Convex Hull: {len(x_coords)}")

#################################################
# test_layout_ocr.py
import asyncio
import os
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.graphics.imaging import BitmapDecoder
from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream
from winrt.system import Array, UInt8

async def run_windows_ocr(path):
    with open(path, "rb") as f:
        file_bytes = f.read()
    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream.get_output_stream_at(0))
    writer.write_bytes(Array(UInt8, file_bytes))
    await writer.store_async()
    
    decoder = await BitmapDecoder.create_async(stream)
    software_bitmap = await decoder.get_software_bitmap_async()
    
    engine = OcrEngine.try_create_from_user_profile_languages()
    if not engine:
        return ""
    result = await engine.recognize_async(software_bitmap)
    
    # 1. Collect lines and their starting X coordinates
    lines_info = []
    min_x = float('inf')
    
    # We estimate average character width across all non-empty lines
    char_widths = []
    
    for line in result.lines:
        if not line.words:
            continue
        # Left-most coordinate is the x of the first word's bounding_rect
        line_x = line.words[0].bounding_rect.x
        # Right-most coordinate is the x + width of the last word's bounding_rect
        line_right = line.words[-1].bounding_rect.x + line.words[-1].bounding_rect.width
        line_width = line_right - line_x
        
        char_len = len(line.text)
        if char_len > 0:
            char_widths.append(line_width / char_len)
            min_x = min(min_x, line_x)
            lines_info.append((line_x, line.text.strip()))
            
    # Calculate global average character width
    avg_char_width = sum(char_widths) / len(char_widths) if char_widths else 10.0
    print(f"Estimated average character width: {avg_char_width:.1f} pixels")
    print(f"Minimum left margin (min_x): {min_x:.1f} pixels")
    
    # 2. Build final layout-preserved text by inserting leading spaces
    formatted_lines = []
    for line_x, text in lines_info:
        # Calculate indentation offset in pixels
        offset_px = line_x - min_x
        # Convert pixel offset to space count
        num_spaces = int(round(offset_px / avg_char_width))
        indent = " " * num_spaces
        formatted_lines.append(indent + text)
        
    return "\n".join(formatted_lines)

def main():
    path = r"C:\Users\M26814\OneDrive - NGC\Desktop\ref_g.png"
    if os.path.exists(path):
        print("Running Layout OCR on:", path)
        try:
            text = asyncio.run(run_windows_ocr(path))
            print("=== OCR LAYOUT SUCCESS ===")
            print(text)
            print("==========================")
        except Exception as e:
            print("OCR Failed:", e)
    else:
        print("File not found at:", path)

if __name__ == "__main__":
    main()
####################################################################
