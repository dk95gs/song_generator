import os
import subprocess
import random
from pydub import AudioSegment, effects
from hashlib import sha1
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# === Google Drive Setup ===
SERVICE_ACCOUNT_FILE = 'songgenupload-cf8ed4438b4b.json'
SCOPES = ['https://www.googleapis.com/auth/drive.file']
DRIVE_FOLDER_ID = '1feczjlX5RKfsdwh4f6WR2V62Q2gLW40J'  # <- Replace with your real folder ID

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
drive_service = build('drive', 'v3', credentials=credentials)

def upload_to_drive(filepath, drive_folder_id=None):
    file_metadata = {'name': os.path.basename(filepath)}
    if drive_folder_id:
        file_metadata['parents'] = [drive_folder_id]

    media = MediaFileUpload(filepath, mimetype='audio/wav')

    uploaded_file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id',
        supportsAllDrives=True  # 👈 REQUIRED for Shared Drives
    ).execute()

    print(f"📤 Uploaded to Google Drive with ID: {uploaded_file.get('id')}")


# === Config ===
NUM_SONGS = 1000
MIN_SONG_LENGTH_SEC = 150
MAX_SONG_LENGTH_SEC = 180

SAMPLES_DIR = "samples"
DRUMS_BASE_DIR = os.path.join(SAMPLES_DIR, "drums")
OUTPUT_DIR = "output_songs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

used_patterns = set()

HARMONIC_KEY_MAP = {
    "c": ["am", "em", "f", "g", "dm"], "g": ["em", "bm", "c", "d", "am"], "d": ["bm", "f#m", "g", "a", "em"],
    "a": ["f#m", "c#m", "d", "e", "bm"], "e": ["c#m", "g#m", "a", "b", "f#m"], "b": ["g#m", "d#m", "e", "f#", "c#m"],
    "f#": ["d#m", "a#m", "b", "c#", "g#m"], "f": ["dm", "am", "bb", "c", "gm"], "bb": ["gm", "cm", "eb", "f", "dm"],
    "eb": ["cm", "fm", "ab", "bb", "gm"], "ab": ["fm", "bbm", "db", "eb", "cm"], "am": ["c", "f", "g", "em", "dm"],
    "em": ["g", "c", "d", "bm", "am"], "bm": ["d", "g", "a", "f#m", "em"], "f#m": ["a", "d", "e", "c#m", "bm"],
    "c#m": ["e", "a", "b", "g#m", "f#m"], "g#m": ["b", "e", "f#", "d#m", "c#m"], "d#m": ["f#", "b", "c#", "a#m", "g#m"],
    "dm": ["f", "bb", "c", "am", "gm"], "gm": ["bb", "eb", "f", "dm", "cm"], "cm": ["eb", "ab", "bb", "gm", "fm"],
    "fm": ["ab", "db", "eb", "cm", "bbm"],
}

def get_key_bpm_folders():
    return [f for f in os.listdir(SAMPLES_DIR) if os.path.isdir(os.path.join(SAMPLES_DIR, f)) and "_" in f and f != "drums"]

def parse_bpm_key(folder_name):
    bpm_str, key_str = folder_name.split("_", 1)
    return int(bpm_str), key_str.lower()

def get_section_durations(bpm):
    bar_duration = (60 / bpm) * 4
    return bar_duration * 8, bar_duration * 4

def calculate_loop_sections(section_duration, target_duration=60):
    return max(1, round(target_duration / section_duration)) if section_duration > 0 else 1

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
    elif drum_rms < average_rms * 0.7:
        boost_needed = 20 * ((average_rms * 0.8) / drum_rms) ** 0.5
        drum = drum + min(boost_needed, 4)
        print(f"🔊 Boosted drums by {min(boost_needed, 4):.1f}dB")
    return drum

def create_single_section(compatible_folders, section_layers, target_bpm, default_sec, short_sec, section_name=None, cached_samples=None, intro_chords=None):
    section_duration = short_sec if section_name == "intro" else default_sec
    duration_ms = int(section_duration * 1000)
    section = AudioSegment.silent(duration=duration_ms)
    used_files = []
    samples_by_layer = {}
    gain_per_layer = -3 if len(section_layers) >= 4 else -2
    chords_sample_info = None

    for layer in section_layers:
        chosen_folder = None
        if layer == "drums":
            folder = os.path.join(DRUMS_BASE_DIR, str(target_bpm))
            chosen_folder = f"drums/{target_bpm}"
        else:
            chosen_folder = random.choice(compatible_folders)
            folder = os.path.join(SAMPLES_DIR, chosen_folder, layer)

        files = [f for f in os.listdir(folder) if f.endswith(".wav")]
        if not files:
            continue

        if cached_samples and layer in cached_samples:
            sample = cached_samples[layer]['sample']
            chosen = cached_samples[layer]['file']
            chosen_folder = cached_samples[layer].get('folder', chosen_folder)
        elif layer == "chords" and intro_chords is not None:
            sample = intro_chords
            chosen = "intro_chords.wav"
        else:
            chosen = random.choice(files)
            sample = load_and_adjust_sample(os.path.join(folder, chosen))

        if len(sample) < duration_ms:
            times = duration_ms // len(sample) + 1
            sample = (sample * times)[:duration_ms]
        else:
            sample = sample[:duration_ms]

        if layer == "chords" and (cached_samples or intro_chords):
            sample = sample - random.uniform(3.0, 6.0)

        sample = sample + gain_per_layer
        samples_by_layer[layer] = sample
        used_files.append(os.path.join(chosen_folder if layer != "drums" else f"drums/{target_bpm}", layer, chosen))

        if layer == "chords" and section_name == "intro":
            chords_sample_info = (chosen_folder, chosen, sample)

    if "drums" in samples_by_layer:
        drum_sample = samples_by_layer["drums"]
        other_samples = [v for k, v in samples_by_layer.items() if k != "drums"]
        samples_by_layer["drums"] = adjust_drum_volume_if_needed(drum_sample, other_samples)

    for sample in samples_by_layer.values():
        section = section.overlay(sample)

    return section, used_files, samples_by_layer, chords_sample_info

def create_loop_section(compatible_folders, section_layers, target_bpm, default_sec, section_name, loop_caches, intro_chords):
    sections_needed = calculate_loop_sections(default_sec, 60)
    complete_loop = AudioSegment.silent(duration=0)
    all_used_files = []

    if section_name in loop_caches:
        cached_samples = loop_caches[section_name]
        for _ in range(sections_needed):
            section, used_files, _, _ = create_single_section(
                compatible_folders, section_layers, target_bpm, default_sec, default_sec,
                section_name, cached_samples, None
            )
            complete_loop += section
            all_used_files.extend(used_files)
    else:
        first_section, used_files, samples_by_layer, _ = create_single_section(
            compatible_folders, section_layers, target_bpm, default_sec, default_sec,
            section_name, None, intro_chords
        )
        complete_loop += first_section
        all_used_files.extend(used_files)

        loop_caches[section_name] = {}
        for layer, sample in samples_by_layer.items():
            loop_caches[section_name][layer] = {
                'sample': sample,
                'file': f"cached_{layer}.wav",
                'folder': 'cached'
            }

        for _ in range(1, sections_needed):
            section, used_files, _, _ = create_single_section(
                compatible_folders, section_layers, target_bpm, default_sec, default_sec,
                section_name, loop_caches[section_name], None
            )
            complete_loop += section
            all_used_files.extend(used_files)

    return complete_loop, all_used_files

def generate_structure(default_section_sec, short_section_sec):
    structure = ["intro"]
    current_duration = short_section_sec
    available_loops = ["loop_a", "loop_b", "bridge"]
    target_song_length = random.uniform(150, 240)
    first_loop = random.choice(available_loops)
    structure.append(first_loop)
    current_duration += 60
    last_loop = first_loop

    while current_duration + 60 < target_song_length:
        available_choices = [loop for loop in available_loops if loop != last_loop]
        if not available_choices:
            available_choices = available_loops
        loop_type = random.choice(available_choices)
        structure.append(loop_type)
        current_duration += 60
        last_loop = loop_type

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
        "loop_b": ["drums", "chords", "bass", "melody"],
        "bridge": ["drums", "chords", "bass", "melody"],
        "outro":  ["drums", "chords", "bass"]
    }

    song = AudioSegment.silent(duration=0)
    pattern_id = []
    loop_caches = {}
    intro_chords = None
    first_loop_after_intro = True

    for section_name in structure:
        if section_name == "intro":
            section, used_files, _, chords_info = create_single_section(
                compatible_folders, section_presets[section_name], bpm, default_sec, short_sec, section_name
            )
            if chords_info:
                intro_chords = chords_info[2]
            song += section
            pattern_id.append(tuple(sorted(used_files)))
        elif section_name == "outro":
            first_loop_name = structure[1]
            outro_chords = loop_caches.get(first_loop_name, {}).get("chords", {}).get("sample")
            section, used_files, _, _ = create_single_section(
                compatible_folders, section_presets[section_name], bpm, default_sec, short_sec, section_name,
                {"chords": {"sample": outro_chords, "file": "cached_chords.wav"}} if outro_chords else None
            )
            song += section
            pattern_id.append(tuple(sorted(used_files)))
        else:
            section, used_files = create_loop_section(
                compatible_folders, section_presets[section_name], bpm, default_sec,
                section_name, loop_caches, intro_chords if first_loop_after_intro else None
            )
            song += section
            pattern_id.append(tuple(sorted(used_files)))
            first_loop_after_intro = False

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
        "-af", "alimiter=limit=0.9",
        limited_file
    ])
    os.remove(filename)
    os.rename(limited_file, filename)

    # ✅ Upload to Google Drive folder
    upload_to_drive(filename, DRIVE_FOLDER_ID)

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
