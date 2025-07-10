import os
import subprocess
import random
import json
from pydub import AudioSegment, effects
from hashlib import sha1

# Configuration
NUM_SONGS = 1000
MIN_SONG_LENGTH_SEC = 150
MAX_SONG_LENGTH_SEC = 180
DEFAULT_SECTION_DURATION_SEC = 24
SHORT_SECTION_DURATION_SEC = 12

# Paths
SAMPLES_DIR = "samples"
GLOBAL_DRUMS_DIR = os.path.join(SAMPLES_DIR, "drums")
OUTPUT_DIR = "output_songs"
AMBIENT_LAYER = os.path.join(SAMPLES_DIR, "ambient", "vinyl_noise.wav")
os.makedirs(OUTPUT_DIR, exist_ok=True)

used_patterns = set()

def get_key_bpm_folders():
    return [
        f for f in os.listdir(SAMPLES_DIR)
        if os.path.isdir(os.path.join(SAMPLES_DIR, f)) and "_" in f and f != "drums"
    ]

def load_and_adjust_sample(path, target_bpm):
    sample = AudioSegment.from_wav(path)
    return sample.strip_silence(silence_len=50, silence_thresh=-40, padding=10)

def create_section(key_bpm_dir, section_layers, target_bpm, used_samples_per_layer, cached_drum=None, section_name=None, cached_chords=None):
    section_duration = SHORT_SECTION_DURATION_SEC if section_name == "intro" else DEFAULT_SECTION_DURATION_SEC
    duration_ms = section_duration * 1000
    section = AudioSegment.silent(duration=duration_ms)
    individual_layers = {}
    used_files = []
    gain_per_layer = -3 if len(section_layers) >= 4 else -2

    for layer in section_layers:
        folder = GLOBAL_DRUMS_DIR if layer == "drums" else os.path.join(SAMPLES_DIR, key_bpm_dir, layer)
        files = [f for f in os.listdir(folder) if f.endswith(".wav") and f not in used_samples_per_layer[layer]]
        if not files:
            continue

        if layer == "drums" and cached_drum:
            sample = cached_drum
            chosen = "cached_drum.wav"
        elif layer == "chords" and cached_chords:
            sample = cached_chords
            chosen = "cached_chords.wav"
        else:
            chosen = random.choice(files)
            sample = load_and_adjust_sample(os.path.join(folder, chosen), target_bpm)
            used_samples_per_layer[layer].add(chosen)

        sample = sample[:duration_ms]
        sample = sample + gain_per_layer

        if layer in ["melody", "chords"]:
            sample = sample.pan(random.uniform(-0.3, 0.3))

        section = section.overlay(sample[:duration_ms])
        if layer not in individual_layers:
            individual_layers[layer] = sample[:duration_ms]
        else:
            individual_layers[layer] = individual_layers[layer].overlay(sample[:duration_ms])

        used_files.append(f"{layer}/{chosen}")

    return section, used_files, cached_drum, individual_layers

def generate_lofi_song(index):
    key_bpm_dir = random.choice(get_key_bpm_folders())
    bpm_str, _ = key_bpm_dir.split("_", 1)
    bpm = int(bpm_str)
    cached_drum = None
    cached_chords_sample = None
    used_samples_per_layer = {layer: set() for layer in ["drums", "chords", "bass", "melody"]}

    structure = ["intro", "loop_a", "loop_a", "loop_a", "bridge", "loop_a", "loop_a", "loop_b", "loop_a", "loop_a", "outro"]
    section_presets = {
        "intro":  ["chords"],
        "loop_a": ["drums", "chords", "bass", "melody"],
        "loop_b": ["drums", "melody", "chords"],
        "bridge": ["drums", "chords", "melody"],
        "outro":  ["drums", "chords"]
    }

    full_song = AudioSegment.silent(duration=0)
    stem_tracks = {}
    sample_names = {}
    pattern_id = []
    first_section = True
    section_details = []
    current_start_ms = 0

    for section_name in structure:
        if full_song.duration_seconds >= MAX_SONG_LENGTH_SEC:
            break

        section, used, cached_drum, individual_layers = create_section(
            key_bpm_dir,
            section_presets[section_name],
            bpm,
            used_samples_per_layer,
            cached_drum,
            section_name=section_name,
            cached_chords=cached_chords_sample if section_name == "loop_a" else None
        )

        if section_name == "intro":
            for layer in section_presets[section_name]:
                if layer == "chords":
                    folder = os.path.join(SAMPLES_DIR, key_bpm_dir, "chords")
                    chosen = used[0].split("/")[-1]
                    cached_chords_sample = load_and_adjust_sample(os.path.join(folder, chosen), bpm)

        if first_section:
            full_song = section
            for layer in individual_layers:
                stem_tracks[layer] = individual_layers[layer]
            first_section = False
        else:
            full_song = full_song.append(section, crossfade=500)
            for layer in individual_layers:
                if layer not in stem_tracks:
                    stem_tracks[layer] = individual_layers[layer]
                else:
                    stem_tracks[layer] = stem_tracks[layer].append(individual_layers[layer], crossfade=500)

        pattern_id.append(tuple(sorted(used)))

        section_info = {
            "section": section_name,
            "start_sec": round(current_start_ms / 1000, 2),
            "layers": {}
        }
        for u in used:
            layer, filename = u.split("/")
            section_info["layers"][layer] = filename
            sample_names[layer] = filename
        section_details.append(section_info)
        current_start_ms += len(section)

    song_hash = sha1(str(pattern_id).encode()).hexdigest()
    if song_hash in used_patterns:
        return False
    used_patterns.add(song_hash)

    if os.path.exists(AMBIENT_LAYER):
        ambient = AudioSegment.from_wav(AMBIENT_LAYER) - 20
        ambient = ambient[:len(full_song)]
        full_song = full_song.overlay(ambient)

    full_song = full_song.fade_in(3000).fade_out(5000)
    full_song = effects.normalize(full_song)

    song_folder = os.path.join(OUTPUT_DIR, f"{index:03d}_{key_bpm_dir}_lofi")
    stems_folder = os.path.join(song_folder, "stems")
    clips_folder = os.path.join(song_folder, "clips")
    os.makedirs(stems_folder, exist_ok=True)
    os.makedirs(clips_folder, exist_ok=True)

    full_song_path = os.path.join(song_folder, "full_song.wav")
    full_song.export(full_song_path, format="wav")

    clip_info = []

    for layer, audio in stem_tracks.items():
        original_name = sample_names.get(layer, layer)
        stem_path = os.path.join(stems_folder, original_name)
        clip_path = os.path.join(clips_folder, original_name)
        audio.export(stem_path, format="wav")
        audio.export(clip_path, format="wav")
        clip_info.append({"layer": layer, "filename": original_name, "bpm": bpm})

    project_info = {
        "bpm": bpm,
        "key": key_bpm_dir.split("_", 1)[1],
        "structure": section_details,
        "layers": list(stem_tracks.keys())
    }

    with open(os.path.join(song_folder, "project_info.json"), "w") as f:
        json.dump(project_info, f, indent=2)

    with open(os.path.join(clips_folder, "clip_info.json"), "w") as f:
        json.dump(clip_info, f, indent=2)

    limited_file = full_song_path.replace(".wav", "_limited.wav")
    subprocess.run([
        "ffmpeg", "-y", "-i", full_song_path,
        "-af", "alimiter=limit=0.85,acompressor=level_in=1:threshold=-10dB:ratio=4:attack=20:release=250,aecho=0.8:0.9:1000|1800:0.3|0.25,stereotools=mlev=0.1",
        limited_file
    ])
    os.remove(full_song_path)
    os.rename(limited_file, full_song_path)

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