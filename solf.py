import numpy as np
from pydub import AudioSegment
from scipy.io.wavfile import write
import random
import os
from io import BytesIO

# === CONFIGURATION ===
SAMPLE_RATE = 44100
OUTPUT_DIR = "meditation_tracks"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# === AUDIO LEVEL SETTINGS ===
TONE_VOLUME_DB = -18  # much softer to blend into background
PAD_VOLUME_DB = -3
BELLS_VOLUME_DB = -10
NUM_BELLS = 4

# === GENERATION SETTINGS ===
NUM_TRACKS = 5
MIN_DURATION = 180  # 3 minutes
MAX_DURATION = 240  # 4 minutes

# === FUNCTIONS ===
def generate_sine_audiosegment(freq, duration_sec, sample_rate=SAMPLE_RATE, amplitude=0.4):
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
    wave = amplitude * np.sin(2 * np.pi * freq * t)
    wave_int16 = np.int16(wave * 32767)
    
    buffer = BytesIO()
    write(buffer, sample_rate, wave_int16)
    buffer.seek(0)
    return AudioSegment.from_file(buffer, format="wav")

def generate_meditation_track(index, duration_sec, freq):
    # 1. Generate base sine tone
    base_tone = generate_sine_audiosegment(freq, duration_sec) + TONE_VOLUME_DB

    # 2. Load and process pad and bells
    pad = AudioSegment.from_wav("pad.wav") + PAD_VOLUME_DB
    bells = AudioSegment.from_wav("bells.wav") + BELLS_VOLUME_DB

    pad = pad.low_pass_filter(5000).pan(-0.2)  # soften and pan
    bells = bells.pan(0.2)  # place bells subtly right

    # 3. Ensure pad lasts full duration
    pad = pad * (duration_sec * 1000 // len(pad) + 1)
    pad = pad[:duration_sec * 1000]

    # 4. Add movement to pad
    segment_count = 4
    segment_duration = len(pad) // segment_count
    dynamic_pad = AudioSegment.silent(duration=0)

    for i in range(segment_count):
        segment = pad[i * segment_duration : (i + 1) * segment_duration]
        segment = segment.fade_in(3000).fade_out(3000)
        if i % 2 == 1:
            segment = segment - 3  # subtle dip
        dynamic_pad += segment

    # 5. Random bell placement
    bell_layer = AudioSegment.silent(duration=duration_sec * 1000)
    bell_points = sorted(random.sample(range(20, duration_sec - 20), NUM_BELLS))
    for t in bell_points:
        bell_layer = bell_layer.overlay(bells, position=t * 1000)

    # 6. Final blend
    final = base_tone.overlay(dynamic_pad).overlay(bell_layer)
    final = final.fade_in(4000).fade_out(8000)

    # 7. Export
    output_path = os.path.join(OUTPUT_DIR, f"meditation_track_{index:02d}.wav")
    final.export(output_path, format="wav")
    print(f"✅ Track {index} exported: {output_path}")

# === MAIN LOOP ===
for i in range(1, NUM_TRACKS + 1):
    duration = random.randint(MIN_DURATION, MAX_DURATION)
    freq = random.choice([396, 417, 528, 639, 741, 852])  # solfeggio tones
    generate_meditation_track(i, duration, freq)
