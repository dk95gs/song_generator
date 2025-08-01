import os
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, lfilter

# Paths
OUTPUT_DIR = "/Volumes/One Touch/output_songs"
WAHWAH_DIR = "wahwah_output"
os.makedirs(WAHWAH_DIR, exist_ok=True)

# Wahwah settings based on Audacity
LFO_FREQ = 0.7
DEPTH = 0.46
RESONANCE = 2.4
FREQ_OFFSET = 0.57
OUTPUT_GAIN_DB = 0.0

MIN_FREQ = 500
MAX_FREQ = 3000
CENTER_FREQ = MIN_FREQ + FREQ_OFFSET * (MAX_FREQ - MIN_FREQ)
OUT_SUFFIX = "_wah.wav"

def wahwah_effect(data, samplerate):
    t = np.arange(len(data)) / samplerate
    mod = (np.sin(2 * np.pi * LFO_FREQ * t) + 1) / 2
    depth_mod = 1 - DEPTH + DEPTH * mod
    freqs = CENTER_FREQ * depth_mod

    processed = np.zeros_like(data, dtype=np.float32)

    for i in range(0, len(data), 1024):
        fc = freqs[i]
        bw = fc / RESONANCE
        low = max(20, fc - bw / 2)
        high = min(samplerate / 2 - 1, fc + bw / 2)

        b, a = butter(2, [low, high], btype='band', fs=samplerate)
        chunk = data[i:i+1024]
        processed[i:i+1024] = lfilter(b, a, chunk)

    gain_factor = 10 ** (OUTPUT_GAIN_DB / 20)
    return (processed * gain_factor).astype(data.dtype)

# Process all WAV files in OUTPUT_DIR
for filename in os.listdir(OUTPUT_DIR):
    if filename.endswith(".wav"):
        input_path = os.path.join(OUTPUT_DIR, filename)
        output_path = os.path.join(WAHWAH_DIR, filename.replace(".wav", OUT_SUFFIX))

        print(f"Processing: {input_path}")
        samplerate, data = wavfile.read(input_path)

        if len(data.shape) == 2:
            data = data.mean(axis=1).astype(data.dtype)

        processed = wahwah_effect(data, samplerate)
        wavfile.write(output_path, samplerate, processed)

print("✅ Wahwah processing complete.")
