import os
import matchering as mg

INPUT_DIR = "output_songs"
REFERENCE_TRACK = "reference.wav"
OUTPUT_DIR = "mastered_songs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Optional: log progress
mg.log(print)

for fname in os.listdir(INPUT_DIR):
    if not fname.lower().endswith(".wav"):
        continue

    target = os.path.join(INPUT_DIR, fname)
    output = os.path.join(OUTPUT_DIR, fname)

    print(f"🎧 Matching {fname} to reference...")

    mg.process(
        target=target,
        reference=REFERENCE_TRACK,
        results=[
            mg.pcm16(output.rsplit(".", 1)[0] + "_master16.wav"),
            mg.pcm24(output.rsplit(".", 1)[0] + "_master24.wav"),
        ],
    )
