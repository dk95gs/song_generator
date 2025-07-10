import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# === CONFIGURATION ===
INPUT_FOLDER = "input_wavs"
OUTPUT_FOLDER = "output_mp3s"
BITRATE = "192k"
MAX_WORKERS = os.cpu_count() or 4  # Use all CPU threads

# === SETUP ===
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
wav_files = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith(".wav")]
total_files = len(wav_files)

# === FUNCTION ===
def convert_file(filename):
    input_path = os.path.join(INPUT_FOLDER, filename)
    output_filename = os.path.splitext(filename)[0] + ".mp3"
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        start_time = time.time()
        subprocess.run([
            "ffmpeg", "-y", "-i", input_path,
            "-codec:a", "libmp3lame", "-b:a", BITRATE,
            output_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        elapsed = time.time() - start_time
        return True, filename, elapsed
    except subprocess.CalledProcessError:
        return False, filename, 0

# === EXECUTION WITH ETA ===
start_all = time.time()
converted = 0
failures = 0
times = []

print(f"🎧 Starting conversion of {total_files} WAV files using {MAX_WORKERS} threads...\n")

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    future_to_file = {executor.submit(convert_file, f): f for f in wav_files}

    for i, future in enumerate(as_completed(future_to_file), 1):
        success, filename, elapsed = future.result()
        times.append(elapsed)

        if success:
            converted += 1
            print(f"✔️ [{converted}/{total_files}] {filename} converted in {elapsed:.1f}s")
        else:
            failures += 1
            print(f"❌ [{converted + failures}/{total_files}] Failed to convert {filename}")

        # Estimate time remaining
        avg_time = sum(times) / len(times)
        remaining_files = total_files - (converted + failures)
        eta_sec = int(avg_time * remaining_files)
        eta_min, eta_rem_sec = divmod(eta_sec, 60)
        print(f"⏳ ETA: {eta_min} min {eta_rem_sec} sec remaining...\n")

# === SUMMARY ===
total_time = int(time.time() - start_all)
total_min, total_sec = divmod(total_time, 60)
print(f"✅ Done in {total_min} min {total_sec} sec — {converted} converted, {failures} failed.")
