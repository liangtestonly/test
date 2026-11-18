import json
import requests
import urllib3
import numpy as np
import datetime as dtt
import time
import shutil
import os

# ====================================================================
# CONFIGURABLE SCHEDULER & PATH SETTINGS
# ====================================================================
RUN_INTERVAL_HOURS = 12     # Set to 12 or 24 hours between TLE downloads
DOWNLOAD_ON_STARTUP = True  # Set to True to download fresh TLE data on startup

# Local and network destination paths matching your system
destdir = r"C:\tmp\demo_7_15"
destination_folder = r"\\159.4.50.205\m26814\home\rain\m26814\tools\task1\data"

# Auto-create local destdir if it doesn't exist to prevent crash!
os.makedirs(destdir, exist_ok=True)

# Suppress corporate proxy insecure SSL warnings to keep your terminal clean
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

tle_urls = ['https://celestrak.org/NORAD/elements/gp.php?GROUP=weather&FORMAT=tle']
f16 = "DMSP 5D-3 F16"
f17 = "DMSP 5D-3 F17"
f18 = "DMSP 5D-3 F18"

target_sats = {
    f16: "DMSP_5D-3_F16",
    f17: "DMSP_5D-3_F17",
    f18: "DMSP_5D-3_F18"
}

def download_and_extract_tle():
    # 1. Generate unique execution timestamp and script-relative paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    timestamp_suffix = time.strftime("%Y-%m-%d_%H%M%S")
    celes_json_file = os.path.join(script_dir, f"celes_tle_{timestamp_suffix}.json")
    
    print(f"\n[+] Starting execution cycle at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("[+] Downloading TLE data from CelesTrak...")
    
    tle_json = []
    for url in tle_urls:
        try:
            # Pass verify=False to bypass corporate SSL decryption firewalls cleanly
            request = requests.get(url, verify=False, timeout=15)
            raw_text = request.text
            
            # Split and clean lines
            lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
            
            # Robust 3-Line Block Parser: perfectly pairs Name, TLE 1, and TLE 2 with 0% scramble rate!
            i = 0
            while i < len(lines) - 2:
                line0 = lines[i]
                line1 = lines[i+1]
                line2 = lines[i+2]
                
                # Validate standard TLE format lines
                if line1.startswith('1 ') and line2.startswith('2 '):
                    tle_json.append({
                        "satellite_name": line0,
                        "tle_1": line1,
                        "tle_2": line2
                    })
                    i += 3
                else:
                    i += 1
        except Exception as e_dl:
            print(f"[-] Download failed for {url}: {e_dl}")
            
    if not tle_json:
        print("[-] No TLE data downloaded during this cycle.")
        return

    # Write full timestamped database
    with open(celes_json_file, 'w', encoding='utf-8') as f:
        json.dump(tle_json, f, indent=3)
    print(f"[+] Downloaded TLE data in: {celes_json_file}")
        
    # 2. Extract and split separate CSV files
    found_count = 0
    for item in tle_json:
        sat_name = item.get("satellite_name", "")
        for target, file_prefix in target_sats.items():
            if target in sat_name:
                tle_1 = item.get("tle_1", "")
                tle_2 = item.get("tle_2", "")
                tle_text = f"{sat_name}\n{tle_1}\n{tle_2}\n"
                
                # Format variables for local epoch file saving
                line2 = tle_2.strip()
                line1 = tle_1.strip()
                line0 = sat_name.strip()
                
                tle_string = line0 + '\n' + line1 + '\n' + line2
                epoch_year = line1[18:20]
                epoch_day = float(line1[20:32])
                epoch = np.datetime64(dtt.datetime.strptime(epoch_year, "%y") + dtt.timedelta(days=epoch_day - 1), "us")
                rep = str.maketrans({":": "_", ".": "_", " ": "_"})
                epoch = str(epoch).translate(rep)
                satstr = (line0).replace(" ", "_").replace("(", "_")\
                    .replace(")", "_").replace("/", "_")\
                    .replace("[", "_").replace("]", "_")                          

                dltime = time.strftime("%Y-%m-%d %H:%M:%S")
                dltime = str(dltime).translate(rep)
                tle_filename = "tle_" + line2[63:68].strip() + "_" + satstr + str(epoch) + ".csv"
                
                # Save locally to C:\tmp\demo_7_15\ folder
                local_out_path = os.path.join(destdir, tle_filename)
                print("[+] Saving Local TLE:", local_out_path)
                try:
                    with open(local_out_path, "w", encoding="utf-8") as tle_str:
                        tle_str.write(tle_string)
                except Exception as e_local:
                    print("[-] Failed to save locally:", e_local)
                    
                # Copy to network share dynamically (defensive wrap)
                net_out_path = os.path.join(destination_folder, tle_filename)
                print("[+] Copying to network:", net_out_path)
                try:
                    shutil.copy(local_out_path, net_out_path)
                except Exception as e_net:
                    print("[-] Network share copy skipped/offline:", e_net)

                # Save the requested individual timestamped .csv file
                out_filename = os.path.join(script_dir, f"{file_prefix}_{timestamp_suffix}.csv")
                try:
                    with open(out_filename, 'w', encoding='utf-8') as f_out:
                        f_out.write(tle_text)
                    print(f"[+] Extracted and saved: {out_filename}")
                    found_count += 1
                except Exception as e_csv:
                    print(f"[-] Failed to save CSV {out_filename}: {e_csv}")
                
    if found_count == 0:
        print("[-] No matching DMSP satellites found inside download")

if __name__ == '__main__':
    # Initial startup download check
    if DOWNLOAD_ON_STARTUP:
        download_and_extract_tle()
        
    while True:
        # Calculate next execution time
        next_run_sec = RUN_INTERVAL_HOURS * 3600
        next_run_time = dtt.datetime.now() + dtt.timedelta(hours=RUN_INTERVAL_HOURS)
        print(f"\n[+] Sleeping for {RUN_INTERVAL_HOURS} hours.")
        print(f"[+] Next scheduled TLE download cycle will start at: {next_run_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Sleep for the configured interval
        time.sleep(next_run_sec)
        
        # Run the TLE downloader & extractor
        download_and_extract_tle()
