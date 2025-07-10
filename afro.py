import os
import subprocess
import random
import re
from pydub import AudioSegment, effects
from hashlib import sha1

# Configuration
NUM_SONGS = 1000
MIN_SONG_LENGTH_SEC = 150
MAX_SONG_LENGTH_SEC = 180
DEFAULT_SECTION_DURATION_SEC = 24
SHORT_SECTION_DURATION_SEC = 12  # for intro

# Paths
SAMPLES_DIR = "samples"
GLOBAL_DRUMS_DIR = os.path.join(SAMPLES_DIR, "drums")
OUTPUT_DIR = "output_songs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

used_patterns = set()

def get_key_bpm_folders():
    return [
        f for f in os.listdir("samples")
        if os.path.isdir(os.path.join("samples", f)) and "afro" in f.lower()
    ]


def extract_bpm_from_filename(filename):
    match = re.search(r'(?<!\d)(\d{2,3})(?!\d)', filename)
    if match:
        return int(match.group(1))
    return None


def rubberband_stretch(input_path, output_path, original_bpm, target_bpm):
    ratio = target_bpm / original_bpm

    # Clamp ratio to avoid extremes
    if ratio < 0.5 or ratio > 2.0:
        print(f"⚠️ Skipping {input_path} — stretch ratio {ratio:.2f} out of bounds")
        raise ValueError("Stretch ratio too extreme")

    subprocess.run([
        "/Users/moody/bin/rubberband",
        "--time", str(ratio),
        "--fine",        # ✅ use R3 engine
        "--formant",     # ✅ preserve vocal timbre
        "-q",            # ✅ suppress terminal output
        input_path,
        output_path
    ], check=True)


def load_and_adjust_sample(path, target_bpm):
    original_bpm = extract_bpm_from_filename(os.path.basename(path))
    if not original_bpm:
        print(f"⚠️ No BPM found in: {path}, skipping.")
        return AudioSegment.silent(duration=1000)

    warped_path = path.replace(".wav", f"_warped_{target_bpm}.wav")

    try:
        rubberband_stretch(path, warped_path, original_bpm, target_bpm)
    except Exception as e:
        print(f"⚠️ Failed to warp {path}: {e}")
        return AudioSegment.silent(duration=1000)

    return AudioSegment.from_wav(warped_path)


def get_rms(audio):
    return audio.rms if len(audio) > 0 else 0

def adjust_drum_volume_if_needed(drum, other_layers):
    other_rms_values = [get_rms(layer) for layer in other_layers if layer is not None]
    if not other_rms_values:
        return drum
    average_rms = sum(other_rms_values) / len(other_rms_values)
    drum_rms = get_rms(drum)
    if drum_rms > average_rms:
        db_difference = 20 * ((drum_rms / average_rms) ** 0.5)
        drum = drum - min(db_difference, 6)
    return drum

def create_section(key_bpm_dir, section_layers, target_bpm, cached_drum=None, section_name=None, cached_chords=None):
    section_duration = SHORT_SECTION_DURATION_SEC if section_name == "intro" else DEFAULT_SECTION_DURATION_SEC
    duration_ms = section_duration * 1000
    section = AudioSegment.silent(duration=duration_ms)
    used_files = []
    samples_by_layer = {}

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
        elif layer == "chords" and cached_chords is not None:
            sample = cached_chords
            chosen = "cached_chords.wav"
        else:
            chosen = random.choice(files)
            sample = load_and_adjust_sample(os.path.join(folder, chosen), target_bpm)

        sample = sample + gain_per_layer
        samples_by_layer[layer] = sample[:duration_ms]
        used_files.append(os.path.join(folder, chosen))  # full correct path


    if "drums" in samples_by_layer:
        drum_sample = samples_by_layer["drums"]
        other_samples = [v for k, v in samples_by_layer.items() if k != "drums"]
        samples_by_layer["drums"] = adjust_drum_volume_if_needed(drum_sample, other_samples)

    for sample in samples_by_layer.values():
        section = section.overlay(sample)

    return section, used_files, cached_drum

def generate_lofi_song(index):
    key_bpm_dir = random.choice(get_key_bpm_folders())
    bpm_str, _ = key_bpm_dir.split("_", 1)
    bpm = int(bpm_str)
    cached_drum = None
    cached_chords_sample = None

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
        "intro":  ["pads", "chords"],
        "loop_a": ["drums", "chords", "bass", "melody", "pads", "vocals"],
        "loop_b": ["drums", "melody", "chords", "pads"],
        "bridge": ["drums", "chords", "melody", "pads", "fx"],
        "outro":  ["drums", "chords", "pads"]
    }

    song = AudioSegment.silent(duration=0)
    pattern_id = []

    for i, section_name in enumerate(structure):
        if song.duration_seconds >= MAX_SONG_LENGTH_SEC:
            break

        if section_name == "intro":
            section, used, cached_drum = create_section(
                key_bpm_dir,
                section_presets[section_name],
                bpm,
                cached_drum,
                section_name=section_name
            )

            # Grab the actual path of the "chords" sample
            chords_path = next((u for u in used if "/chords/" in u), None)
            if chords_path:
                cached_chords_sample = load_and_adjust_sample(chords_path, bpm)

        else:
            section, used, cached_drum = create_section(
                key_bpm_dir,
                section_presets[section_name],
                bpm,
                cached_drum,
                section_name=section_name,
                cached_chords=cached_chords_sample if section_name == "loop_a" else None
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
