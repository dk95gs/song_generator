import os
import random
import subprocess
import librosa
import soundfile as sf
from pydub import AudioSegment, effects
from hashlib import sha1

# === Configuration ===
SAMPLES_DIR = "meditation_samples"
OUTPUT_DIR = "meditation_tracks"
PERC_DIR = os.path.join(SAMPLES_DIR, "percussion")
os.makedirs(OUTPUT_DIR, exist_ok=True)

NUM_SONGS = 1000
SECTION_DURATION_SEC = 32
MIN_SONG_LENGTH_SEC = 180
MAX_SONG_LENGTH_SEC = 240

used_patterns = set()


# === Utility ===

def get_bpm_dirs():
    return [
        d for d in os.listdir(SAMPLES_DIR)
        if os.path.isdir(os.path.join(SAMPLES_DIR, d)) and "_" in d and d != "percussion"
    ]


def detect_bpm(path):
    y, sr = librosa.load(path)
    bpm, _ = librosa.beat.beat_track(y=y, sr=sr)
    return bpm if bpm > 0 else 60


def stretch_and_pitch_shift(path, target_bpm, semitone_shift):
    y, sr = librosa.load(path)
    source_bpm = detect_bpm(path)

    # Safely cast to float for Python 3.13
    rate = float(target_bpm / source_bpm) * random.uniform(0.95, 1.05)
    y = librosa.effects.time_stretch(y.astype(float), rate=rate)
    y = librosa.effects.pitch_shift(y, sr=sr, n_steps=semitone_shift)

    temp_path = "temp_stretched.wav"
    sf.write(temp_path, y, sr)
    return AudioSegment.from_wav(temp_path)



def fit_to_section(sample, section_ms):
    if len(sample) > section_ms:
        return sample[:section_ms]
    loops = section_ms // len(sample) + 1
    return (sample * loops)[:section_ms]


# === Song Construction ===

def sprinkle_percussion(percussion_files, total_duration_ms):
    result = AudioSegment.silent(duration=total_duration_ms)
    one_shot_slots = sorted(random.sample(range(1000, total_duration_ms - 1000, 1000), k=min(30, total_duration_ms // 1000)))
    
    for i in one_shot_slots:
        file = random.choice(percussion_files)
        sound = AudioSegment.from_wav(os.path.join(PERC_DIR, file)) - random.randint(2, 6)
        result = result.overlay(sound, position=i)
    return result


def build_song(folder, bpm, chords_sample, melody_files, percussion_files):
    section_ms = SECTION_DURATION_SEC * 1000
    song = AudioSegment.silent(duration=0)
    used_melody_combos = set()

    structure = random.choice([
        ["intro", "ambient", "ambient", "ambient", "ambient", "outro"],
        ["intro", "ambient", "ambient", "ambient", "outro"]
    ])

    for section_type in structure:
        section = chords_sample
        if section_type in ["ambient", "outro"]:
            melody_file = random.choice(melody_files)
            while True:
                pitch = random.choice([-12, -9, -5, 5, 9, 12])
                combo_key = (section_type, melody_file, pitch)
                if combo_key not in used_melody_combos:
                    break
            used_melody_combos.add(combo_key)

            melody = stretch_and_pitch_shift(os.path.join(SAMPLES_DIR, folder, "melody", melody_file), bpm, pitch)
            melody = fit_to_section(melody, section_ms)
            section = section.overlay(melody - 3)

        song += section

    # Add percussion one-shots
    total_duration = len(song)
    sprinkled_perc = sprinkle_percussion(percussion_files, total_duration)
    full_song = song.overlay(sprinkled_perc)

    return full_song


def generate_song(index):
    folder = random.choice(get_bpm_dirs())
    bpm = int(folder.split("_")[0])

    chord_path = os.path.join(SAMPLES_DIR, folder, "chords")
    chord_files = [f for f in os.listdir(chord_path) if f.endswith(".wav")]
    if not chord_files:
        return False
    chosen_chord = os.path.join(chord_path, random.choice(chord_files))
    chords_sample = stretch_and_pitch_shift(chosen_chord, bpm, 0)
    chords_sample = fit_to_section(chords_sample - 3, SECTION_DURATION_SEC * 1000)

    melody_path = os.path.join(SAMPLES_DIR, folder, "melody")
    melody_files = [f for f in os.listdir(melody_path) if f.endswith(".wav")]
    if not melody_files:
        return False

    percussion_files = [f for f in os.listdir(PERC_DIR) if f.endswith(".wav")]
    if not percussion_files:
        return False

    song = build_song(folder, bpm, chords_sample, melody_files, percussion_files)

    if song.duration_seconds < MIN_SONG_LENGTH_SEC:
        return False

    song = song[:MAX_SONG_LENGTH_SEC * 1000]
    song = song.fade_in(3000).fade_out(5000)
    song = effects.normalize(song)

    filename = os.path.join(OUTPUT_DIR, f"meditation_{index:03d}.wav")
    song.export(filename, format="wav")

    limited = filename.replace(".wav", "_limited.wav")
    subprocess.run(["ffmpeg", "-y", "-i", filename, "-af", "alimiter=limit=0.8", limited])
    os.remove(filename)
    os.rename(limited, filename)
    return True


def main():
    count = 0
    attempts = 0
    while count < NUM_SONGS and attempts < NUM_SONGS * 5:
        if generate_song(count + 1):
            print(f"✔️ Track {count + 1} generated")
            count += 1
        else:
            print("⚠️ Skipped or failed")
        attempts += 1


if __name__ == "__main__":
    main()
