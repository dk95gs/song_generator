import os
import subprocess
import random
from pydub import AudioSegment, effects
import librosa
import soundfile as sf
from hashlib import sha1
import numpy as np

# Config
song_signatures = []
MIN_SONG_LENGTH_SEC = 150  # 2 min 30 sec
MAX_SONG_LENGTH_SEC = 180  # 3 min
SECTION_DURATION_SEC = 24   # One 4-bar loop at 120 BPM
NUM_SONGS = 1000

SAMPLES_DIR = "samples"
GLOBAL_DRUMS_DIR = os.path.join(SAMPLES_DIR, "drums")
OUTPUT_DIR = "output_songs"
os.makedirs(OUTPUT_DIR, exist_ok=True)
used_patterns = set()


def get_mfcc_signature(file_path, n_mfcc=13):
    y, sr = librosa.load(file_path, sr=None)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc)
    return np.mean(mfcc, axis=1)  # summarize as 1D vector

def get_key_bpm_folders():
    return [
        f for f in os.listdir(SAMPLES_DIR)
        if os.path.isdir(os.path.join(SAMPLES_DIR, f)) and "_" in f and f != "drums"
    ]


def load_and_adjust_sample(path, target_bpm):
    return AudioSegment.from_wav(path)
   # y, sr = librosa.load(path)
  #  bpm, _ = librosa.beat.beat_track(y=y, sr=sr)
 #   stretch = float(bpm) / float(target_bpm) if bpm > 0 else 1.0

  # y_stretched = librosa.effects.time_stretch(y=y, rate=stretch)
  #  temp_path = "temp.wav"
 #   sf.write(temp_path, y_stretched, sr)
 #   return AudioSegment.from_wav(temp_path)

def create_section(key_bpm_dir, section_layers, target_bpm, cached_drum=None):
    section = AudioSegment.silent(duration=SECTION_DURATION_SEC * 1000)
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
        section = section.overlay(sample[:SECTION_DURATION_SEC * 1000])
        used_files.append(f"{layer}/{chosen}")

    return section, used_files, cached_drum




def generate_song(index):
    key_bpm_dir = random.choice(get_key_bpm_folders())
    bpm_str, _ = key_bpm_dir.split("_", 1)
    bpm = int(bpm_str)
    cached_drum = None

    structure_options = [
        ["intro", "verse", "chorus", "verse", "chorus", "outro"],
        ["intro", "verse", "verse", "chorus", "bridge", "chorus", "outro"],
        ["intro", "build", "verse", "chorus", "break", "chorus", "outro"],
    ]
    section_presets = {
    "intro":  ["drums", "chords"],
    "verse":  ["drums", "chords", "bass", "melody"],
    "chorus": ["drums", "melody", "chords", "bass"],
    "bridge": ["drums", "chords", "bass"],
    "build":  ["drums", "chords", "melody"],
    "break":  ["chords", "melody"],  # remove just-melody-only break
    "outro":  ["drums", "chords", "melody"]
}


    song = AudioSegment.silent(duration=0)
    pattern_id = []

    while song.duration_seconds < MIN_SONG_LENGTH_SEC:
        structure = random.choice(structure_options)
        for section_name in structure:
            if song.duration_seconds >= MAX_SONG_LENGTH_SEC:
                break
            section, used, cached_drum = create_section(key_bpm_dir, section_presets[section_name], bpm, cached_drum)

            song += section
            pattern_id.append(tuple(sorted(used)))

    song_hash = sha1(str(pattern_id).encode()).hexdigest()
    if song_hash in used_patterns:
        return False
    used_patterns.add(song_hash)
    song = song.fade_in(3000).fade_out(5000)
    song = effects.normalize(song)
    filename = os.path.join(OUTPUT_DIR, f"song_{index:03d}.wav")

    # Export raw song first
    song.export(filename, format="wav")

    # Compute MFCC signature and compare with previous
 #   new_sig = get_mfcc_signature(filename)
  #  for sig in song_signatures:
  #      similarity = np.linalg.norm(new_sig - sig)
 #       if similarity < 20:  # Adjust this threshold to tune similarity sensitivity
  #          print("❌ Song too similar to an existing one. Deleting.")
  #          os.remove(filename)
  #          return False
 #  song_signatures.append(new_sig)

    # Apply hard limiter using FFmpeg
    limited_file = filename.replace(".wav", "_limited.wav")

    subprocess.run([
        "ffmpeg", "-y", "-i", filename,
        "-af", "alimiter=limit=0.8",  # soft limiter at -1 dB
        limited_file
    ])

    # Replace original with limited version
    os.remove(filename)
    os.rename(limited_file, filename)

    return True

def main():
    count = 0
    attempts = 0
    while count < NUM_SONGS and attempts < NUM_SONGS * 5:
        if generate_song(count + 1):
            print(f"✔️ Generated song {count + 1}")
            count += 1
        else:
            print("⚠️ Skipped duplicate pattern")
        attempts += 1

if __name__ == "__main__":
    main()
