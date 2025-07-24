import os
import subprocess
import random
from pydub import AudioSegment, effects
from hashlib import sha1

# Configuration
NUM_SONGS = 1000
MIN_SONG_LENGTH_SEC = 150
MAX_SONG_LENGTH_SEC = 180

# Paths
SAMPLES_DIR = "samples"
DRUMS_BASE_DIR = os.path.join(SAMPLES_DIR, "drums")
OUTPUT_DIR = "output_songs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

used_patterns = set()

HARMONIC_KEY_MAP = {
    "c": ["am", "em", "f", "g", "dm"],
    "g": ["em", "bm", "c", "d", "am"],
    "d": ["bm", "f#m", "g", "a", "em"],
    "a": ["f#m", "c#m", "d", "e", "bm"],
    "e": ["c#m", "g#m", "a", "b", "f#m"],
    "b": ["g#m", "d#m", "e", "f#", "c#m"],
    "f#": ["d#m", "a#m", "b", "c#", "g#m"],
    "f": ["dm", "am", "bb", "c", "gm"],
    "bb": ["gm", "cm", "eb", "f", "dm"],
    "eb": ["cm", "fm", "ab", "bb", "gm"],
    "ab": ["fm", "bbm", "db", "eb", "cm"],
    "am": ["c", "f", "g", "em", "dm"],
    "em": ["g", "c", "d", "bm", "am"],
    "bm": ["d", "g", "a", "f#m", "em"],
    "f#m": ["a", "d", "e", "c#m", "bm"],
    "c#m": ["e", "a", "b", "g#m", "f#m"],
    "g#m": ["b", "e", "f#", "d#m", "c#m"],
    "d#m": ["f#", "b", "c#", "a#m", "g#m"],
    "dm": ["f", "bb", "c", "am", "gm"],
    "gm": ["bb", "eb", "f", "dm", "cm"],
    "cm": ["eb", "ab", "bb", "gm", "fm"],
    "fm": ["ab", "db", "eb", "cm", "bbm"],
}

def get_key_bpm_folders():
    return [
        f for f in os.listdir(SAMPLES_DIR)
        if os.path.isdir(os.path.join(SAMPLES_DIR, f)) and "_" in f and f != "drums"
    ]

def parse_bpm_key(folder_name):
    bpm_str, key_str = folder_name.split("_", 1)
    return int(bpm_str), key_str.lower()

def get_section_durations(bpm):
    bar_duration = (60 / bpm) * 4
    return bar_duration * 8, bar_duration * 4

def load_and_adjust_sample(path):
    return AudioSegment.from_wav(path)

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

def create_section(compatible_folders, section_layers, target_bpm, default_sec, short_sec, cached_drum=None, section_name=None, cached_chords=None):
    section_duration = short_sec if section_name == "intro" else default_sec
    duration_ms = int(section_duration * 1000)
    section = AudioSegment.silent(duration=duration_ms)
    used_files = []
    samples_by_layer = {}
    gain_per_layer = -3 if len(section_layers) >= 4 else -2
    chords_sample_info = None

    for layer in section_layers:
        if layer == "drums":
            folder = os.path.join(DRUMS_BASE_DIR, str(target_bpm))
        else:
            chosen_folder = random.choice(compatible_folders)
            folder = os.path.join(SAMPLES_DIR, chosen_folder, layer)

        files = [f for f in os.listdir(folder) if f.endswith(".wav")]
        if not files:
            continue

        if layer == "drums":
            if cached_drum is not None:
                sample = cached_drum
                chosen = "cached_drum.wav"
            else:
                chosen = random.choice(files)
                sample = load_and_adjust_sample(os.path.join(folder, chosen))
                if len(sample) < duration_ms:
                    times = duration_ms // len(sample) + 1
                    sample = (sample * times)[:duration_ms]
                else:
                    sample = sample[:duration_ms]
                cached_drum = sample
        elif layer == "chords" and cached_chords is not None:
            sample = cached_chords
            chosen = "cached_chords.wav"
            if len(sample) < duration_ms:
                times = duration_ms // len(sample) + 1
                sample = (sample * times)[:duration_ms]
            else:
                sample = sample[:duration_ms]

        else:
            chosen = random.choice(files)
            sample = load_and_adjust_sample(os.path.join(folder, chosen))
            if len(sample) < duration_ms:
                times = duration_ms // len(sample) + 1
                sample = (sample * times)[:duration_ms]
            else:
                sample = sample[:duration_ms]

        sample = sample + gain_per_layer
        samples_by_layer[layer] = sample
        used_files.append(f"{layer}/{chosen}")

        if layer == "chords" and section_name == "intro":
            chords_sample_info = (chosen_folder, chosen)

    if "drums" in samples_by_layer:
        drum_sample = samples_by_layer["drums"]
        other_samples = [v for k, v in samples_by_layer.items() if k != "drums"]
        samples_by_layer["drums"] = adjust_drum_volume_if_needed(drum_sample, other_samples)

    for sample in samples_by_layer.values():
        section = section.overlay(sample)

    return section, used_files, cached_drum, chords_sample_info

def generate_structure(default_section_sec, short_section_sec):
    structure = ["intro"]
    current_duration = short_section_sec
    section_presets = ["loop_a", "loop_a", "loop_b", "bridge", "loop_a", "loop_a", "loop_b"]
    random.shuffle(section_presets)

    # Randomize a target song length between 2.5 and 4.0 minutes
    target_song_length = random.uniform(150, 240)

    while current_duration + default_section_sec < target_song_length:
        section = random.choice(section_presets)
        structure.append(section)
        current_duration += default_section_sec

    structure.append("outro")
    return structure

def generate_lofi_song(index):
    all_folders = get_key_bpm_folders()
    selected_folder = random.choice(all_folders)
    bpm, root_key = parse_bpm_key(selected_folder)
    default_sec, short_sec = get_section_durations(bpm)
    harmonizing_keys = HARMONIC_KEY_MAP.get(root_key, [])
    compatible_folders = [
        f for f in all_folders
        if parse_bpm_key(f)[0] == bpm and parse_bpm_key(f)[1] in harmonizing_keys + [root_key]
    ]

    structure = generate_structure(default_sec, short_sec)

    section_presets = {
        "intro":  ["chords"],
        "loop_a": ["drums", "chords", "bass", "melody"],
        "loop_b": ["drums", "melody", "bass", "chords"],
        "bridge": ["drums", "chords", "melody"],
        "outro":  ["drums", "chords"]
    }

    song = AudioSegment.silent(duration=0)
    pattern_id = []
    cached_drum = None
    cached_chords_sample = None

    for section_name in structure:
        # Disable this hard cutoff to allow full structure to render
        # if song.duration_seconds >= MAX_SONG_LENGTH_SEC:
        #     break

        section, used, cached_drum, chords_sample_info = create_section(
            compatible_folders,
            section_presets[section_name],
            bpm,
            default_sec,
            short_sec,
            cached_drum,
            section_name=section_name,
            cached_chords=cached_chords_sample
        )

        if chords_sample_info:
            chords_folder, chords_filename = chords_sample_info
            cached_chords_sample = load_and_adjust_sample(
                os.path.join(SAMPLES_DIR, chords_folder, "chords", chords_filename)
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
