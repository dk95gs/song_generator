import os
import itertools
from pydub import AudioSegment
import librosa
import soundfile as sf

# Config
SECTION_DURATION_SEC = 24
MIN_SONG_LENGTH_SEC = 150  # 2 min 30 sec
MAX_SONG_LENGTH_SEC = 180  # 3 min
SAMPLES_DIR = "samples"
OUTPUT_DIR = "output_songs"
GLOBAL_DRUMS_DIR = os.path.join(SAMPLES_DIR, "drums")
KEY_BPM_FOLDER = "80_A_minor"  # choose 1 key folder for now
os.makedirs(OUTPUT_DIR, exist_ok=True)

MELODY_DIR = os.path.join(SAMPLES_DIR, KEY_BPM_FOLDER, "melody")
CHORDS_DIR = os.path.join(SAMPLES_DIR, KEY_BPM_FOLDER, "chords")
BASS_DIR = os.path.join(SAMPLES_DIR, KEY_BPM_FOLDER, "bass")
BPM = int(KEY_BPM_FOLDER.split("_")[0])


def load_and_adjust_sample(path, target_bpm):
    y, sr = librosa.load(path)
    bpm, _ = librosa.beat.beat_track(y=y, sr=sr)
    stretch = bpm / target_bpm if bpm > 0 else 1.0
    y_stretched = librosa.effects.time_stretch(y, stretch)
    temp_path = "temp.wav"
    sf.write(temp_path, y_stretched, sr)
    return AudioSegment.from_wav(temp_path)


def create_layered_section(drum_file, melody_file, chord_file, bass_file):
    section = AudioSegment.silent(duration=SECTION_DURATION_SEC * 1000)

    for category, file_path in zip([
        "drums", "melody", "chords", "bass"
    ], [
        drum_file, melody_file, chord_file, bass_file
    ]):
        sample = load_and_adjust_sample(file_path, BPM)
        if len(sample) < SECTION_DURATION_SEC * 1000:
            silence = AudioSegment.silent(duration=SECTION_DURATION_SEC * 1000 - len(sample))
            sample += silence
        sample = sample[:SECTION_DURATION_SEC * 1000]
        section = section.overlay(sample)

    return section


def main():
    drums = [os.path.join(GLOBAL_DRUMS_DIR, f) for f in os.listdir(GLOBAL_DRUMS_DIR) if f.endswith(".wav")]
    melodies = [os.path.join(MELODY_DIR, f) for f in os.listdir(MELODY_DIR) if f.endswith(".wav")]
    chords = [os.path.join(CHORDS_DIR, f) for f in os.listdir(CHORDS_DIR) if f.endswith(".wav")]
    basses = [os.path.join(BASS_DIR, f) for f in os.listdir(BASS_DIR) if f.endswith(".wav")]

    combinations = list(itertools.product(drums, melodies, chords, basses))
    print(f"Generating {len(combinations)} unique songs...")

    for i, (drum, melody, chord, bass) in enumerate(combinations):
        song = AudioSegment.silent(duration=0)
        while song.duration_seconds < MIN_SONG_LENGTH_SEC:
            section = create_layered_section(drum, melody, chord, bass)
            song += section
            if song.duration_seconds >= MAX_SONG_LENGTH_SEC:
                break

        name = f"{i+1:04d}_D-{os.path.basename(drum)}_M-{os.path.basename(melody)}_C-{os.path.basename(chord)}_B-{os.path.basename(bass)}.wav"
        filename = os.path.join(OUTPUT_DIR, name)
        song.export(filename, format="wav")
        print(f"✔️ Saved {filename}")


if __name__ == "__main__":
    main()
