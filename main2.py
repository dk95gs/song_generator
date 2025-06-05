import os
import subprocess
import random
from pydub import AudioSegment, effects
from hashlib import sha1

# Configuration
NUM_SONGS = 1000
MIN_SONG_LENGTH_SEC = 150
MAX_SONG_LENGTH_SEC = 180
DEFAULT_SECTION_DURATION_SEC = 24  # seconds
SHORT_SECTION_DURATION_SEC = 12    # for intro and bridge

# Paths
SAMPLES_DIR = "samples"
GLOBAL_DRUMS_DIR = os.path.join(SAMPLES_DIR, "drums")
OUTPUT_DIR = "output_songs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

used_patterns = set()

def get_key_bpm_folders():
    return [
        f for f in os.listdir(SAMPLES_DIR)
        if os.path.isdir(os.path.join(SAMPLES_DIR, f)) and "_" in f and f != "drums"
    ]

def load_and_adjust_sample(path, target_bpm):
    return AudioSegment.from_wav(path)

def create_section(key_bpm_dir, section_layers, target_bpm, cached_drum=None, section_name=None):
    # Use 12s duration for intro and bridge, 24s for everything else
    section_duration = SHORT_SECTION_DURATION_SEC if section_name in ["intro", "bridge"] else DEFAULT_SECTION_DURATION_SEC
    duration_ms = section_duration * 1000
    section = AudioSegment.silent(duration=duration_ms)
    used_files = []

    gain_per_layer = -3 if len(section_layers) >= 4 else -2

    for layer in section_layers:
        folder = GLOBAL_DRUMS_DIR if layer == "drums" else os.path.join(SAMPLES_DIR, key_bpm_dir, layer)
        files = [f for f in os.listdir(folder) if f.endswith(".wav")]
        if not files:
            continue

        if layer == "drums":
            if cached_drum is not None:
                sample = cached_drum
                chosen = "cached_drum.wav"
            else:
                chosen = random.choice(files)
                sample = load_and_adjust_sample(os.path.join(folder, chosen), target_bpm)
                cached_drum = sample
        else:
            chosen = random.choice(files)
            sample = load_and_adjust_sample(os.path.join(folder, chosen), target_bpm)

        sample = sample + gain_per_layer
        section = section.overlay(sample[:duration_ms])
        used_files.append(f"{layer}/{chosen}")

    return section, used_files, cached_drum

def generate_lofi_song(index):
    key_bpm_dir = random.choice(get_key_bpm_folders())
    bpm_str, _ = key_bpm_dir.split("_", 1)
    bpm = int(bpm_str)
    cached_drum = None

    # Lo-fi hip hop structure
    structure = (
        ["intro"] +
        ["loop_a"] +
        ["loop_a"] * 2 +
        ["bridge"] +
        ["loop_a"] * 2 +
        ["loop_b"] +
        ["loop_a"] * 2 +
        ["outro"]
    )

    section_presets = {
        "intro":  ["chords"],
        "loop_a": ["drums", "chords", "bass", "melody"],
        "loop_b": ["drums", "melody", "chords"],
        "bridge": ["chords", "melody"],
        "outro":  ["chords"]
    }

    song = AudioSegment.silent(duration=0)
    pattern_id = []

    for section_name in structure:
        if song.duration_seconds >= MAX_SONG_LENGTH_SEC:
            break
        section, used, cached_drum = create_section(
            key_bpm_dir,
            section_presets[section_name],
            bpm,
            cached_drum,
            section_name=section_name
        )
        song += section
        pattern_id.append(tuple(sorted(used)))

    song_hash = sha1(str(pattern_id).encode()).hexdigest()
    if song_hash in used_patterns:
        return False
    used_patterns.add(song_hash)

    song = song.fade_in(3000).fade_out(5000)
    song = effects.normalize(song)

    filename = os.path.join(OUTPUT_DIR, f"song_{index:03d}.wav")
    song.export(filename, format="wav")

    limited_file = filename.replace(".wav", "_limited.wav")
    subprocess.run([
        "ffmpeg", "-y", "-i", filename,
        "-af", "alimiter=limit=0.8",
        limited_file
    ])
    os.remove(filename)
    os.rename(limited_file, filename)

    return True

def main():
    count = 0
    attempts = 0
    while count < NUM_SONGS and attempts < NUM_SONGS * 5:
        if generate_lofi_song(count + 1):
            print(f"✔️ Generated song {count + 1}")
            count += 1
        else:
            print("⚠️ Skipped duplicate pattern")
        attempts += 1

if __name__ == "__main__":
    main()
