import os
import subprocess
import random
from pydub import AudioSegment, effects
from hashlib import sha1

# Configuration
NUM_SONGS = 1000
MIN_SONG_LENGTH_SEC = 150
MAX_SONG_LENGTH_SEC = 180

# Paths
SAMPLES_DIR = "samples"
DRUMS_BASE_DIR = os.path.join(SAMPLES_DIR, "drums")
#change to out_songs 
OUTPUT_DIR = "output_songs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

used_patterns = set()

HARMONIC_KEY_MAP = {
    "c": ["am", "em", "f", "g", "dm"],
    "g": ["em", "bm", "c", "d", "am"],
    "d": ["bm", "f#m", "g", "a", "em"],
    "a": ["f#m", "c#m", "d", "e", "bm"],
    "e": ["c#m", "g#m", "a", "b", "f#m"],
    "b": ["g#m", "d#m", "e", "f#", "c#m"],
    "f#": ["d#m", "a#m", "b", "c#", "g#m"],
    "f": ["dm", "am", "bb", "c", "gm"],
    "bb": ["gm", "cm", "eb", "f", "dm"],
    "eb": ["cm", "fm", "ab", "bb", "gm"],
    "ab": ["fm", "bbm", "db", "eb", "cm"],
    "am": ["c", "f", "g", "em", "dm"],
    "em": ["g", "c", "d", "bm", "am"],
    "bm": ["d", "g", "a", "f#m", "em"],
    "f#m": ["a", "d", "e", "c#m", "bm"],
    "c#m": ["e", "a", "b", "g#m", "f#m"],
    "g#m": ["b", "e", "f#", "d#m", "c#m"],
    "d#m": ["f#", "b", "c#", "a#m", "g#m"],
    "dm": ["f", "bb", "c", "am", "gm"],
    "gm": ["bb", "eb", "f", "dm", "cm"],
    "cm": ["eb", "ab", "bb", "gm", "fm"],
    "fm": ["ab", "db", "eb", "cm", "bbm"],
}

def get_key_bpm_folders():
    return [
        f for f in os.listdir(SAMPLES_DIR)
        if os.path.isdir(os.path.join(SAMPLES_DIR, f)) and "_" in f and f != "drums"
    ]

def parse_bpm_key(folder_name):
    bpm_str, key_str = folder_name.split("_", 1)
    return int(bpm_str), key_str.lower()

def get_section_durations(bpm):
    bar_duration = (60 / bpm) * 4
    return bar_duration * 8, bar_duration * 4

def calculate_loop_sections(section_duration, target_duration=60):
    """Calculate how many sections to chain for closest to target duration"""
    if section_duration <= 0:
        return 1
    
    sections_needed = round(target_duration / section_duration)
    return max(1, sections_needed)

def load_and_adjust_sample(path):
    return AudioSegment.from_wav(path)

def get_rms(audio):
    return audio.rms if len(audio) > 0 else 0

def match_rms_levels(loops_data, target_rms=None):
    """Match RMS levels across all loops for consistent loudness"""
    if not loops_data:
        return loops_data
    
    # Calculate RMS for each loop
    rms_values = []
    for loop_name, loop_audio in loops_data:
        rms = get_rms(loop_audio)
        rms_values.append(rms)
        print(f"📊 {loop_name} RMS: {rms:.2f}")
    
    # Use target RMS or average of all loops
    if target_rms is None:
        target_rms = sum(rms_values) / len(rms_values)
    
    print(f"🎯 Target RMS: {target_rms:.2f}")
    
    # Adjust each loop to match target RMS
    matched_loops = []
    for (loop_name, loop_audio), current_rms in zip(loops_data, rms_values):
        if current_rms > 0:
            # Calculate adjustment needed
            adjustment_ratio = target_rms / current_rms
            adjustment_db = 20 * (adjustment_ratio ** 0.5)  # Convert to dB
            
            # Apply adjustment (cap at ±6dB for safety)
            adjustment_db = max(-6, min(6, adjustment_db))
            adjusted_loop = loop_audio + adjustment_db
            
            print(f"🔧 {loop_name}: {adjustment_db:+.1f}dB adjustment")
            matched_loops.append((loop_name, adjusted_loop))
        else:
            matched_loops.append((loop_name, loop_audio))
    
    return matched_loops
    """Match RMS levels across all loops for consistent loudness"""
    if not loops_data:
        return loops_data
    
    # Calculate RMS for each loop
    rms_values = []
    for loop_name, loop_audio in loops_data:
        rms = get_rms(loop_audio)
        rms_values.append(rms)
        print(f"📊 {loop_name} RMS: {rms:.2f}")
    
    # Use target RMS or average of all loops
    if target_rms is None:
        target_rms = sum(rms_values) / len(rms_values)
    
    print(f"🎯 Target RMS: {target_rms:.2f}")
    
    # Adjust each loop to match target RMS
    matched_loops = []
    for (loop_name, loop_audio), current_rms in zip(loops_data, rms_values):
        if current_rms > 0:
            # Calculate adjustment needed
            adjustment_ratio = target_rms / current_rms
            adjustment_db = 20 * (adjustment_ratio ** 0.5)  # Convert to dB
            
            # Apply adjustment (cap at ±6dB for safety)
            adjustment_db = max(-6, min(6, adjustment_db))
            adjusted_loop = loop_audio + adjustment_db
            
            print(f"🔧 {loop_name}: {adjustment_db:+.1f}dB adjustment")
            matched_loops.append((loop_name, adjusted_loop))
        else:
            matched_loops.append((loop_name, loop_audio))
    
    return matched_loops

def adjust_drum_volume_if_needed(drum, other_layers):
    other_rms_values = [get_rms(layer) for layer in other_layers if layer is not None]
    if not other_rms_values:
        return drum
    average_rms = sum(other_rms_values) / len(other_rms_values)
    drum_rms = get_rms(drum)
    
    # If drums are too loud, reduce them (original logic)
    if drum_rms > average_rms:
        db_difference = 20 * ((drum_rms / average_rms) ** 0.5)
        drum = drum - min(db_difference, 6)
    
    # NEW: If drums are too quiet, boost them
    elif drum_rms < average_rms * 0.7:  # If drums are less than 70% of average
        boost_needed = 20 * ((average_rms * 0.8) / drum_rms) ** 0.5  # Boost to 80% of average
        drum = drum + min(boost_needed, 4)  # Cap boost at 4dB
        print(f"🔊 Boosted drums by {min(boost_needed, 4):.1f}dB")
    
    return drum

def create_single_section(compatible_folders, section_layers, target_bpm, default_sec, short_sec, section_name=None, cached_samples=None, intro_chords=None):
    """Create a single section with caching logic"""
    section_duration = short_sec if section_name == "intro" else default_sec
    duration_ms = int(section_duration * 1000)
    section = AudioSegment.silent(duration=duration_ms)
    used_files = []
    samples_by_layer = {}
    gain_per_layer = -3 if len(section_layers) >= 4 else -2
    chords_sample_info = None

    for layer in section_layers:
        chosen_folder = None  # Initialize chosen_folder
        
        if layer == "drums":
            folder = os.path.join(DRUMS_BASE_DIR, str(target_bpm))
            chosen_folder = f"drums/{target_bpm}"
        else:
            chosen_folder = random.choice(compatible_folders)
            folder = os.path.join(SAMPLES_DIR, chosen_folder, layer)

        files = [f for f in os.listdir(folder) if f.endswith(".wav")]
        if not files:
            continue

        # Check if we have cached sample for this layer
        if cached_samples and layer in cached_samples:
            sample = cached_samples[layer]['sample']
            chosen = cached_samples[layer]['file']
            chosen_folder = cached_samples[layer].get('folder', chosen_folder)
        elif layer == "chords" and intro_chords is not None:
            # Use intro chords for first loop after intro
            sample = intro_chords
            chosen = "intro_chords.wav"
        else:
            # Select new random sample
            chosen = random.choice(files)
            sample = load_and_adjust_sample(os.path.join(folder, chosen))

        # Adjust sample length to section duration
        if len(sample) < duration_ms:
            times = duration_ms // len(sample) + 1
            sample = (sample * times)[:duration_ms]
        else:
            sample = sample[:duration_ms]

        # Apply volume adjustments
        if layer == "chords" and (cached_samples or intro_chords):
            # Randomize volume of cached chords
            sample = sample - random.uniform(3.0, 6.0)

        sample = sample + gain_per_layer
        samples_by_layer[layer] = sample
        used_files.append(os.path.join(chosen_folder if layer != "drums" else f"drums/{target_bpm}", layer, chosen))

        # Store intro chords info for caching
        if layer == "chords" and section_name == "intro":
            chords_sample_info = (chosen_folder, chosen, sample)

    # Adjust drum volume if needed
    if "drums" in samples_by_layer:
        drum_sample = samples_by_layer["drums"]
        other_samples = [v for k, v in samples_by_layer.items() if k != "drums"]
        samples_by_layer["drums"] = adjust_drum_volume_if_needed(drum_sample, other_samples)

    # Mix all layers
    for sample in samples_by_layer.values():
        section = section.overlay(sample)

    return section, used_files, samples_by_layer, chords_sample_info

def create_loop_section(compatible_folders, section_layers, target_bpm, default_sec, section_name, loop_caches, intro_chords):
    """Create a complete loop section (multiple sections chained for ~1 minute)"""
    # Calculate how many sections needed for ~1 minute
    sections_needed = calculate_loop_sections(default_sec, 60)
    
    complete_loop = AudioSegment.silent(duration=0)
    all_used_files = []
    
    # Check if this loop type already has cached samples
    if section_name in loop_caches:
        # Use cached samples for all sections in this loop
        cached_samples = loop_caches[section_name]
        for i in range(sections_needed):
            section, used_files, _, _ = create_single_section(
                compatible_folders, section_layers, target_bpm, default_sec, default_sec,
                section_name, cached_samples, None
            )
            complete_loop += section
            all_used_files.extend(used_files)
    else:
        # First time this loop appears - create and cache samples
        first_section, used_files, samples_by_layer, _ = create_single_section(
            compatible_folders, section_layers, target_bpm, default_sec, default_sec,
            section_name, None, intro_chords
        )
        complete_loop += first_section
        all_used_files.extend(used_files)
        
        # Cache the samples for this loop type
        loop_caches[section_name] = {}
        for layer, sample in samples_by_layer.items():
            # For intro chords, store the sample directly
            if layer == "chords" and intro_chords is not None:
                loop_caches[section_name][layer] = {
                    'sample': intro_chords,
                    'file': f"cached_{layer}.wav",
                    'folder': 'cached'
                }
            else:
                # For other layers, store the processed sample
                loop_caches[section_name][layer] = {
                    'sample': sample,
                    'file': f"cached_{layer}.wav",
                    'folder': 'cached'
                }
        
        # Create remaining sections using cached samples
        for i in range(1, sections_needed):
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
    
    # Randomize a target song length between 2.5 and 4.0 minutes
    target_song_length = random.uniform(150, 240)
    
    # Add first loop (will get intro chords)
    first_loop = random.choice(available_loops)
    structure.append(first_loop)
    current_duration += 60  # loops are ~1 minute now
    last_loop = first_loop
    
    # Add more loops, avoiding consecutive repeats
    while current_duration + 60 < target_song_length:
        # Get available loops excluding the last one used
        available_choices = [loop for loop in available_loops if loop != last_loop]
        
        # If no choices available (shouldn't happen with 3 loop types), allow any
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
    loop_caches = {}  # Cache samples for each loop type
    global_bass_cache = None  # Global bass cache for entire song
    used_drums = set()  # Track used drum files to avoid duplicates
    intro_chords = None
    first_loop_after_intro = True
    
    # Store all sections for RMS matching
    all_sections = []
    loops_for_rms_matching = []

    for section_name in structure:
        if section_name == "intro":
            # Create intro
            section, used_files, _, chords_info = create_single_section(
                compatible_folders, section_presets[section_name], bpm, 
                default_sec, short_sec, section_name
            )
            if chords_info:
                # Store intro chords for first loop
                intro_chords = chords_info[2]
            song += section
            pattern_id.append(tuple(sorted(used_files)))
            
        elif section_name == "outro":
            # Create outro using first loop's cached chords if available
            first_loop_name = structure[1]  # First loop after intro
            outro_chords = None
            if first_loop_name in loop_caches and "chords" in loop_caches[first_loop_name]:
                outro_chords = loop_caches[first_loop_name]["chords"]["sample"]
            
            section, used_files, _, _ = create_single_section(
                compatible_folders, section_presets[section_name], bpm,
                default_sec, short_sec, section_name, 
                {"chords": {"sample": outro_chords, "file": "cached_chords.wav"}} if outro_chords else None
            )
            song += section
            pattern_id.append(tuple(sorted(used_files)))
            
        else:
            # Create loop section
            intro_chords_for_loop = intro_chords if first_loop_after_intro else None
            section, used_files = create_loop_section(
                compatible_folders, section_presets[section_name], bpm,
                default_sec, section_name, loop_caches, intro_chords_for_loop
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