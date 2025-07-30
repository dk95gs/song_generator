import os
from pydub import AudioSegment, effects

SAMPLES_DIR = "samples"

def normalize_all_wav_files():
    for root, _, files in os.walk(SAMPLES_DIR):
        for file in files:
            if file.lower().endswith(".wav"):
                file_path = os.path.join(root, file)
                try:
                    print(f"Normalizing: {file_path}")
                    audio = AudioSegment.from_wav(file_path)
                    normalized_audio = effects.normalize(audio)
                    normalized_audio.export(file_path, format="wav")
                except Exception as e:
                    print(f"❌ Failed to normalize {file_path}: {e}")

if __name__ == "__main__":
    normalize_all_wav_files()
