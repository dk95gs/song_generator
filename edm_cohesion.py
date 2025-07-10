import os
import random
import subprocess
from pydub import AudioSegment, effects
from hashlib import sha1

# === CONFIGURATION ===
SONG_COUNT = 1000
SONG_MIN_LENGTH_SEC = 150
SECTION_LEN_DEFAULT_SEC = 16
SECTION_LEN_SHORT_SEC = 8

SAMPLES_DIR = "edm_samples"
OUTPUT_DIR = "edm_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

used_hashes = set()

def get_genre_dirs():
    return [
        d for d in os.listdir(SAMPLES_DIR)
        if "_" in d and os.path.isdir(os.path.join(SAMPLES_DIR, d))
    ]

def loop_to_duration(sample: AudioSegment, target_duration_ms: int) -> AudioSegment:
    if len(sample) == 0:
        return AudioSegment.silent(duration=target_duration_ms)
    loops_needed = target_duration_ms // len(sample)
    remainder = target_duration_ms % len(sample)
    looped = sample * loops_needed
    if remainder > 0:
        looped += sample[:remainder]
    return looped

def load_sample(folder: str, layer: str) -> AudioSegment:
    path = os.path.join(folder, layer)
    if not os.path.isdir(path):
        return None
    files = [f for f in os.listdir(path) if f.endswith(".wav")]
    if not files:
        return None
    sample_path = os.path.join(path, random.choice(files))
    return AudioSegment.from_wav(sample_path)

def add_riser(folder: str, target_duration_ms: int) -> AudioSegment:
    riser_path = os.path.join(folder, "risers")
    if not os.path.isdir(riser_path):
        return AudioSegment.silent(duration=0)
    files = [f for f in os.listdir(riser_path) if f.endswith(".wav")]
    if not files:
        return AudioSegment.silent(duration=0)
    sample_path = os.path.join(riser_path, random.choice(files))
    riser = AudioSegment.from_wav(sample_path) - 3
    if len(riser) > target_duration_ms:
        riser = riser[-target_duration_ms:]
    elif len(riser) < target_duration_ms:
        riser += AudioSegment.silent(duration=target_duration_ms - len(riser))
    return riser

def calculate_structure_duration_sec(structure):
    return sum(
        SECTION_LEN_SHORT_SEC if name in ["intro", "break"] else SECTION_LEN_DEFAULT_SEC
        for name, _ in structure
    )

def build_expanded_structure(base_structure, min_duration_sec=180):
    expanded = base_structure[:]
    total_duration = calculate_structure_duration_sec(expanded)
    while total_duration < min_duration_sec:
        for section in ["drop1_repeat", "drop2_repeat", "drop2", "build1"]:
            matches = [s for s in base_structure if s[0] == section]
            if matches:
                expanded.append(matches[0])
                total_duration = calculate_structure_duration_sec(expanded)
                if total_duration >= min_duration_sec:
                    break
        else:
            break
    expanded.append(("outro", ["chords", "fx"]))
    return expanded

def create_section(folder: str, section_name: str, layers: list, static_layers: dict, add_riser_next=False) -> tuple:
    duration_sec = SECTION_LEN_SHORT_SEC if section_name in ["intro", "break"] else SECTION_LEN_DEFAULT_SEC
    duration_ms = duration_sec * 1000
    section = AudioSegment.silent(duration=duration_ms)
    used_layers = []
    base_gain = -2 - max(0, len(layers) - 2)

    for layer in layers:
        if layer in ["chords", "bass", "drums"] and layer in static_layers:
            sample = static_layers[layer]
        else:
            sample = load_sample(folder, layer)
            if layer in ["chords", "bass", "drums"] and sample:
                static_layers[layer] = sample

        if not sample:
            continue

        if layer in ["builds", "risers"]:
            sample = sample[:duration_ms]
            if len(sample) < duration_ms:
                sample += AudioSegment.silent(duration=duration_ms - len(sample))
        else:
            sample = loop_to_duration(sample, duration_ms)

        sample = sample + base_gain
        section = section.overlay(sample)
        used_layers.append(layer)

    if add_riser_next:
        riser = add_riser(folder, duration_ms)
        section = section.overlay(riser, position=duration_ms - len(riser))
        used_layers.append("riser")

    return section, used_layers

def generate_edm_song(index: int) -> bool:
    genre_dirs = get_genre_dirs()
    if not genre_dirs:
        print("❌ No genre folders found in edm_samples/")
        return False

    genre_dir = random.choice(genre_dirs)
    folder = os.path.join(SAMPLES_DIR, genre_dir)

    static_layers = {}

    base_structure = [
        ("intro", ["fx", "chords"]),
        ("build1", ["drums", "chords", "fx", "builds"]),
        ("drop1", ["drums", "bass", "leads"]),
        ("drop1_repeat", ["drums", "bass", "leads"]),
        ("break", ["chords", "fx", "vocals", "builds"]),
        ("drop2", ["drums", "bass", "leads", "vocals"]),
        ("drop2_repeat", ["drums", "bass", "leads", "vocals"])
    ]

    structure = build_expanded_structure(base_structure, min_duration_sec=180)

    song = AudioSegment.silent(duration=0)
    pattern_id = []

    for i, (section_name, layers) in enumerate(structure):
        add_riser = (i + 1 < len(structure)) and structure[i + 1][0].startswith("drop")
        section, used_layers = create_section(folder, section_name, layers, static_layers, add_riser_next=add_riser)
        song += section
        pattern_id.append(tuple(sorted(used_layers)))

    if song.duration_seconds < SONG_MIN_LENGTH_SEC:
        print(f"ℹ️ Song is {int(song.duration_seconds)}s — under minimum length but still saving.")

    song_hash = sha1(str(pattern_id).encode()).hexdigest()
    if song_hash in used_hashes:
        print("ℹ️ Duplicate pattern detected — saving anyway.")
    else:
        used_hashes.add(song_hash)

    song = song.fade_in(3000).fade_out(3000)
    song = effects.normalize(song)

    filename = os.path.join(OUTPUT_DIR, f"edm_song_{index:03d}.wav")
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
    while count < SONG_COUNT and attempts < SONG_COUNT * 5:
        if generate_edm_song(count + 1):
            print(f"🎶 Generated EDM song {count + 1}")
            count += 1
        else:
            print("⚠️ Skipped duplicate or too short")
        attempts += 1

if __name__ == "__main__":
    main()
