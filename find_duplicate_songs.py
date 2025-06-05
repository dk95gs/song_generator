import os
import hashlib
from pydub import AudioSegment

OUTPUT_DIR = "output_songs"
HASHES = {}

def hash_audio(file_path):
    try:
        audio = AudioSegment.from_file(file_path)
        raw_data = audio.raw_data  # Uncompressed audio bytes
        return hashlib.sha1(raw_data).hexdigest()
    except Exception as e:
        print(f"⚠️ Error loading {file_path}: {e}")
        return None

def main():
    print(f"🔍 Scanning for duplicate songs in '{OUTPUT_DIR}'...\n")
    duplicates = []

    for filename in os.listdir(OUTPUT_DIR):
        if not filename.lower().endswith(".wav"):
            continue
        full_path = os.path.join(OUTPUT_DIR, filename)
        audio_hash = hash_audio(full_path)
        if not audio_hash:
            continue

        if audio_hash in HASHES:
            original = HASHES[audio_hash]
            duplicates.append((filename, original))
        else:
            HASHES[audio_hash] = filename

    if duplicates:
        print("🟡 Found duplicate songs:\n")
        for dup, original in duplicates:
            print(f"  🔁 {dup} is a duplicate of {original}")
    else:
        print("✅ No duplicate songs found.")

if __name__ == "__main__":
    main()
