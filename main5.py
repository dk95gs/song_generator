import os
import subprocess
import random
import re
import tempfile
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
        f for f in os.listdir(SAMPLES_DIR)
        if os.path.isdir(os.path.join(SAMPLES_DIR, f)) and "_" in f and f != "drums"
    ]

def extract_bpm_from_filename(filename):
    # Match the first 2- or 3-digit number in the filename
    matches = re.findall(r'(\d{2,3})', filename)
    return int(matches[0]) if matches else None

def compute_musical_stretch_ratio(audio, original_bpm, target_bpm, desired_duration_ms=24000):
    original_duration_sec = len(audio) / 1000
    original_beats = original_bpm * (original_duration_sec / 60)
    target_beats = target_bpm * (desired_duration_ms / 1000 / 60)
    return original_beats / target_beats

def time_stretch_with_ffmpeg(input_path, stretch_ratio):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        output_path = tmp.name

    filters = []
    remaining = 1 / stretch_ratio
    while remaining < 0.5 or remaining > 2.0:
        step = 2.0 if remaining > 2.0 else 0.5
        filters.append(f"atempo={step}")
        remaining /= step
    filters.append(f"atempo={remaining:.6f}")
    atempo_filter = ",".join(filters)

    subprocess.run([
        "ffmpeg", "-y", "-i", input_path,
        "-filter:a", atempo_filter,
        output_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return output_path

def load_and_adjust_sample(path, target_bpm, num_bars=8):
    original_bpm = extract_bpm_from_filename(os.path.basename(path))
    if not original_bpm:
        print(f"[WARN] No BPM found in filename: {path}")
        return None

    original_audio = AudioSegment.from_wav(path)

    # Step 1: Stretch to match target BPM
    stretch_ratio = original_bpm / target_bpm
    stretched_path = time_stretch_with_ffmpeg(path, stretch_ratio)
    stretched_audio = AudioSegment.from_wav(stretched_path)

    # Step 2: Calculate how long N bars is at target BPM
    beats_per_second = target_bpm / 60
    target_beats = num_bars * 4  # assuming 4/4 time
    target_duration_ms = int((target_beats / beats_per_second) * 1000)

    # Step 3: Trim or pad to exact length
    if len(stretched_audio) > target_duration_ms:
        final = stretched_audio[:target_duration_ms]
    else:
        final = stretched_audio + AudioSegment.silent(duration=(target_duration_ms - len(stretched_audio)))

    print(f"[INFO] Loaded: {os.path.basename(path)} | BPM {original_bpm} → {target_bpm} | Bars: {num_bars} | Length: {len(final)/1000:.2f}s")
    return final


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
    duration_ms = SHORT_SECTION_DURATION_SEC * 1000 if section_name == "intro" else DEFAULT_SECTION_DURATION_SEC * 1000
    section = AudioSegment.silent(duration=duration_ms)
    used_files = []
    samples_by_layer = {}
    gain_per_layer = -3 if len(section_layers) >= 4 else -2

    for layer in section_layers:
        folder = GLOBAL_DRUMS_DIR if layer == "drums" else os.path.join(SAMPLES_DIR, key_bpm_dir, layer)
        candidates = [f for f in os.listdir(folder) if f.endswith(".wav")]

        if not candidates:
            print(f"[INFO] No samples in {folder}, skipping {layer}")
            continue

        sample = None
        chosen = None

        if layer == "drums":
            if cached_drum:
                sample = cached_drum
                chosen = "cached_drum.wav"
            else:
                chosen = random.choice(candidates)
                path = os.path.join(folder, chosen)
                sample = load_and_adjust_sample(path, target_bpm)
                cached_drum = sample
        elif layer == "chords" and cached_chords:
            sample = cached_chords
            chosen = "cached_chords.wav"
        else:
            chosen = random.choice(candidates)
            path = os.path.join(folder, chosen)
            sample = load_and_adjust_sample(path, target_bpm)

        if sample is None:
            continue

        sample = sample + gain_per_layer
        samples_by_layer[layer] = sample
        used_files.append(f"{layer}/{chosen}")

    if not samples_by_layer:
        print(f"[WARN] No valid samples found for section: {section_name}")
        return AudioSegment.silent(duration=duration_ms), [], cached_drum

    if "drums" in samples_by_layer:
        drum = samples_by_layer["drums"]
        others = [v for k, v in samples_by_layer.items() if k != "drums"]
        samples_by_layer["drums"] = adjust_drum_volume_if_needed(drum, others)

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
        "intro":  ["chords"],
        "loop_a": ["drums", "chords", "bass", "melody"],
        "loop_b": ["drums", "melody", "chords"],
        "bridge": ["drums", "chords", "melody"],
        "outro":  ["drums", "chords"]
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
            section_name,
            cached_chords=cached_chords_sample if section_name == "loop_a" else None
        )

        if section_name == "intro" and "chords" in section_presets[section_name]:
            folder = os.path.join(SAMPLES_DIR, key_bpm_dir, "chords")
            if used:
                chosen = used[0].split("/")[-1]
                cached_chords_sample = load_and_adjust_sample(os.path.join(folder, chosen), bpm)

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
