import os
import random
import subprocess
from pydub import AudioSegment, effects
from hashlib import sha1

# === CONFIGURATION ===
SONG_COUNT = 50
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

def load_sample(folder: str, layer: str, static_layers: dict) -> AudioSegment:
    if layer in static_layers:
        return static_layers[layer]

    path = os.path.join(folder, layer)
    if not os.path.isdir(path):
        return None

    files = [f for f in os.listdir(path) if f.endswith(".wav")]
    if not files:
        return None

    sample_path = os.path.join(path, random.choice(files))
    sample = AudioSegment.from_wav(sample_path)

    if layer in ["chords", "bass"]:
        static_layers[layer] = sample

    return sample

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

def create_section(folder: str, section_name: str, layers: list, static_layers: dict, add_riser_next=False) -> tuple:
    duration_sec = SECTION_LEN_SHORT_SEC if section_name in ["intro", "break"] else SECTION_LEN_DEFAULT_SEC
    duration_ms = duration_sec * 1000

    section = AudioSegment.silent(duration=duration_ms)
    used_layers = []

    gain_per_layer = -3 if len(layers) >= 4 else -2  # Dynamic gain control

    for layer in layers:
        sample = load_sample(folder, layer, static_layers)
        if not sample:
            continue

        if layer in ["builds", "risers"]:
            sample = sample[:duration_ms]
            if len(sample) < duration_ms:
                sample += AudioSegment.silent(duration=duration_ms - len(sample))
        else:
            sample = loop_to_duration(sample, duration_ms)

        sample = sample + gain_per_layer  # Apply gain based on number of layers
        section = section.overlay(sample)
        used_layers.append(layer)

    if add_riser_next:
        riser = add_riser(folder, duration_ms)
        section = section.overlay(riser, position=duration_ms - len(riser))
        used_layers.append("riser")

    return section, used_layers


def build_expanded_structure(base_structure, min_duration_sec=180):
    section_durations = {
        "intro": 8,
        "build1": 16,
        "drop1": 16,
        "drop1_repeat": 16,
        "break": 8,
        "drop2": 16,
        "drop2_repeat": 16,
        "outro": 16
    }

    expandable = ["drop1", "drop2", "drop1_repeat", "drop2_repeat", "build1", "break"]
    structure = base_structure[:]
    total_duration = sum(section_durations[name] for name, _ in structure)

    while total_duration < min_duration_sec:
        repeat_section = random.choice([s for s in structure if s[0] in expandable])
        insert_index = random.randint(2, len(structure) - 2)
        structure.insert(insert_index, repeat_section)
        total_duration += section_durations[repeat_section[0]]

    return structure

def generate_edm_song(index: int) -> bool:
    genre_dirs = get_genre_dirs()
    if not genre_dirs:
        print("❌ No genre folders found in edm_samples/")
        return False

    genre_dir = random.choice(genre_dirs)
    folder = os.path.join(SAMPLES_DIR, genre_dir)
    bpm = int(genre_dir.split("_")[0])

    static_layers = {}

    base_structure = [
        ("intro", ["fx", "chords"]),
        ("build1", ["drums", "chords", "fx", "builds"]),
        ("drop1", ["drums", "bass", "leads"]),
        ("drop1_repeat", ["drums", "bass", "leads"]),
        ("break", ["chords", "fx", "vocals", "builds"]),
        ("drop2", ["drums", "bass", "leads", "vocals"]),
        ("drop2_repeat", ["drums", "bass", "leads", "vocals"]),
        ("outro", ["chords", "fx"])
    ]

    # Extend structure to meet min duration
    structure = []
    total_duration = 0
    while total_duration < SONG_MIN_LENGTH_SEC:
        for s in base_structure:
            structure.append(s)
            section_len = SECTION_LEN_SHORT_SEC if s[0] in ["intro", "break"] else SECTION_LEN_DEFAULT_SEC
            total_duration += section_len
            if total_duration >= SONG_MIN_LENGTH_SEC:
                break

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

    # ✨ Mastering: fade, normalize, limiter
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
            print(f"\U0001F3B6 Generated EDM song {count + 1}")
            count += 1
        else:
            print("⚠️ Skipped duplicate or too short")
        attempts += 1

if __name__ == "__main__":
    main()
