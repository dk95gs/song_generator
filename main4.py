import os
import subprocess
import random
from pydub import AudioSegment, effects
from hashlib import sha1

# Configuration
NUM_SONGS = 1000
SONG_LENGTH_SEC = 180
DEFAULT_SECTION_DURATION_SEC = 24
SHORT_SECTION_DURATION_SEC = 12

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

def create_section(key_bpm_dir, section_layers, target_bpm, cached_drum=None, section_name=None, static_layers={}):
    section_duration = SHORT_SECTION_DURATION_SEC if section_name in ["intro", "breakdown", "outro"] else DEFAULT_SECTION_DURATION_SEC
    duration_ms = section_duration * 1000
    section = AudioSegment.silent(duration=duration_ms)
    used_files = []

    gain_per_layer = -3 if len(section_layers) >= 4 else -2

    for layer in section_layers:
        folder = GLOBAL_DRUMS_DIR if layer == "drums" else os.path.join(SAMPLES_DIR, key_bpm_dir, layer)
        if not os.path.isdir(folder):
            continue

        if layer in static_layers:
            sample = static_layers[layer]
            chosen = f"cached_{layer}.wav"
        else:
            files = [f for f in os.listdir(folder) if f.endswith(".wav")]
            if not files:
                continue

            # === Special Ambient Handling for Intro ===
            if section_name == "intro" and layer == "ambient":
                num_layers = random.choice([2, 3])
                ambient_samples = random.sample(files, min(num_layers, len(files)))
                for amb_file in ambient_samples:
                    amb_sample = load_and_adjust_sample(os.path.join(folder, amb_file), target_bpm)

                    # Random trim offset (0–2s)
                    if len(amb_sample) > 3000:
                        offset = random.randint(0, min(2000, len(amb_sample) - 1000))
                        amb_sample = amb_sample[offset:]

                    # Random reverse
                    if random.random() < 0.3:
                        amb_sample = amb_sample.reverse()

                    # Random pitch shift (±2 semitones) — approximation by speed change
                    if random.random() < 0.4:
                        pitch_factor = 2 ** (random.uniform(-2, 2) / 12.0)
                        amb_sample = amb_sample._spawn(amb_sample.raw_data, overrides={
                            "frame_rate": int(amb_sample.frame_rate * pitch_factor)
                        }).set_frame_rate(amb_sample.frame_rate)

                    # Random gain
                    amb_sample = amb_sample + random.randint(-6, 3)

                    # Random pan (approximate by blending L/R)
                    pan = random.uniform(-0.8, 0.8)
                    amb_sample = amb_sample.pan(pan)

                    section = section.overlay(amb_sample[:duration_ms])
                    used_files.append(f"{layer}/{amb_file}")

                continue  # skip the normal layer handling for ambient in intro

            # === Normal Layer Handling ===
            chosen = random.choice(files)
            sample = load_and_adjust_sample(os.path.join(folder, chosen), target_bpm)

            if layer in ["chords", "bass", "ambient"]:
                static_layers[layer] = sample

        if layer == "drums" and cached_drum:
            sample = cached_drum
        elif layer == "drums":
            files = [f for f in os.listdir(folder) if f.endswith(".wav")]
            if files:
                chosen = random.choice(files)
                sample = load_and_adjust_sample(os.path.join(folder, chosen), target_bpm)
                cached_drum = sample

        sample = sample + gain_per_layer
        section = section.overlay(sample[:duration_ms])
        used_files.append(f"{layer}/{chosen}")

    return section, used_files, cached_drum, static_layers


def generate_lofi_song(index):
    key_bpm_dir = random.choice(get_key_bpm_folders())
    bpm_str, _ = key_bpm_dir.split("_", 1)
    bpm = int(bpm_str)
    cached_drum = None
    static_layers = {}

   # structure_templates = [
    #[
   #     "intro", "beat_drop", "main_loop", "main_loop", "breakdown",
    #    "return_loop", "main_loop", "return_loop", "outro"
   # ],
    #[
   #     "intro", "beat_drop", "main_loop", "breakdown", "main_loop",
   #     "return_loop", "main_loop", "main_loop", "outro"
   # ],
   # [
  #      "intro", "beat_drop", "main_loop", "main_loop", "main_loop",
   #     "return_loop", "breakdown", "return_loop", "outro"
  #  ],
   # [
   #     "intro", "beat_drop", "main_loop", "return_loop", "breakdown",
   #     "main_loop", "return_loop", "main_loop", "outro"
  #  ]
#]

    ##structure = random.choice(structure_templates)

    structure = [
        "intro",
        "beat_drop",
        "main_loop",
        "main_loop",
        "breakdown",
        "return_loop",
        "main_loop",
        "return_loop",
        "outro"
    ]

    section_presets = {
        "intro":        ["ambient", "fx"],
        "beat_drop":    ["drums", "chords", "bass"],
        "main_loop":    ["drums", "chords", "bass", "melody", "fx"],
        "breakdown":    ["ambient", "melody", "fx"],
        "return_loop":  ["drums", "chords", "melody", "fx"],
        "outro":        ["ambient", "chords"]
    }

    song = AudioSegment.silent(duration=0)
    pattern_id = []

    for i, section_name in enumerate(structure):
        # Generate section
        section, used, cached_drum, static_layers = create_section(
            key_bpm_dir,
            section_presets[section_name],
            bpm,
            cached_drum,
            section_name=section_name,
            static_layers=static_layers
        )

        # === Carry ambient from intro into beat_drop ===
        if section_name == "beat_drop" and "ambient" in static_layers:
            ambient_sample = static_layers["ambient"]
            ambient_fade = ambient_sample - 6
            ambient_fade = ambient_fade[:len(section)]
            section = section.overlay(ambient_fade)

        # === Overlay riser on end of previous section ===
        if section_name in ["beat_drop", "return_loop"] and i > 0:
            riser_path = os.path.join(SAMPLES_DIR, key_bpm_dir, "risers")
            if os.path.isdir(riser_path):
                riser_files = [f for f in os.listdir(riser_path) if f.endswith(".wav")]
                if riser_files:
                    riser_file = random.choice(riser_files)
                    riser_sample = load_and_adjust_sample(os.path.join(riser_path, riser_file), bpm)
                    riser_sample = riser_sample - 3
                    riser_duration = len(riser_sample)
                    song_duration = len(song)

                    if song_duration >= riser_duration:
                        tail = song[-riser_duration:]
                        blended = tail.overlay(riser_sample)
                        song = song[:-riser_duration] + blended
                    else:
                        blended = song.overlay(riser_sample[-song_duration:])
                        song = blended

        # Append section
        song += section
        pattern_id.append(tuple(sorted(used)))

        if song.duration_seconds >= 180:
            break

    # Enforce minimum duration
    if song.duration_seconds < 150:
        return False

    song = song.fade_in(3000).fade_out(4000)
    song = effects.normalize(song)

    # Deduplication
    song_hash = sha1(str(pattern_id).encode()).hexdigest()
    if song_hash in used_patterns:
        return False
    used_patterns.add(song_hash)

    # Export and apply limiter
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
