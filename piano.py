import os
import random
import librosa
import soundfile as sf
from pydub import AudioSegment, effects
from hashlib import sha1
import tempfile

# Configuration
NUM_SONGS = 100
SECTION_DURATION_SEC = 60
MIN_SONG_DURATION_SEC = 180  # 3 minutes
MAX_SONG_DURATION_SEC = 240  # 4 minutes
SAMPLES_DIR = "samples_piano_nature"
OUTPUT_DIR = "output_piano_nature"
os.makedirs(OUTPUT_DIR, exist_ok=True)

used_patterns = set()

def get_piano_samples():
    folder = os.path.join(SAMPLES_DIR, "piano")
    return [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".wav")]

def get_nature_loop():
    folder = os.path.join(SAMPLES_DIR, "nature")
    files = [f for f in os.listdir(folder) if f.endswith(".wav")]
    return AudioSegment.from_wav(os.path.join(folder, random.choice(files))) if files else None

def load_piano_slowed(file_path, slowdown_factor=1.0):
    y, sr = librosa.load(file_path, sr=None)
    y_stretched = librosa.effects.time_stretch(y=y, rate=slowdown_factor)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp:
        sf.write(temp.name, y_stretched, sr)
        stretched = AudioSegment.from_wav(temp.name)
    return effects.normalize(stretched)

def repeat_to_fill(audio: AudioSegment, target_ms: int) -> AudioSegment:
    result = AudioSegment.silent(duration=0)
    while len(result) < target_ms:
        result += audio
    return result[:target_ms]

def generate_song(index):
    piano_files = get_piano_samples()
    if len(piano_files) < 3:
        print("⚠️ Not enough piano samples")
        return False

    song = AudioSegment.silent(duration=0)
    structure = []
    nature = get_nature_loop()

    # Randomize section count between 3 and 4 minutes
    total_sections = random.randint(
        MIN_SONG_DURATION_SEC // SECTION_DURATION_SEC,
        MAX_SONG_DURATION_SEC // SECTION_DURATION_SEC
    )

    slowdown = 1.0  # initial tempo

    for _ in range(total_sections):
        piano_path = random.choice(piano_files)
        section = load_piano_slowed(piano_path, slowdown)
        section = repeat_to_fill(section, SECTION_DURATION_SEC * 1000)
        song += section
        structure.append(piano_path)
        slowdown *= 0.97  # gradually slow down

    # Apply nature overlay
    if nature:
        while len(nature) < len(song):
            nature += nature
        song = song.overlay(nature[:len(song)] - 6)

    # Prevent duplicate patterns
    song_hash = sha1(str(structure).encode()).hexdigest()
    if song_hash in used_patterns:
        return False
    used_patterns.add(song_hash)

    song = song.fade_in(3000).fade_out(5000)
    song = effects.normalize(song)

    filename = os.path.join(OUTPUT_DIR, f"piano_nature_{index:03d}.wav")
    song.export(filename, format="wav")
    print(f"✔️ Generated piano nature song {index}")
    return True

def main():
    count = 0
    attempts = 0
    while count < NUM_SONGS and attempts < NUM_SONGS * 5:
        if generate_song(count + 1):
            count += 1
        attempts += 1

if __name__ == "__main__":
    main()
