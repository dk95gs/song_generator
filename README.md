# Song Generator - Setup Guide for macOS

This guide will help you set up and run the `song_generator` project on a **fresh macOS machine**.

---

## 🔧 Prerequisites

Make sure your system has:

* macOS 11 or later
* Administrator access
* Internet connection

---

## 🧱 Step 1: Install Python 3 (if not already installed)

1. Open Terminal.
2. Check version:

   ```bash
   python3 --version
   ```
3. If not installed, download and install from: [https://www.python.org/downloads/mac-osx/](https://www.python.org/downloads/mac-osx/)

Ensure that `pip3` is also installed:

```bash
pip3 --version
```

---

## 📦 Step 2: Download the Project

If you do not have Git installed, you can download the ZIP directly:

1. Go to [https://github.com/dk95gs/song\_generator](https://github.com/dk95gs/song_generator)
2. Click the green **Code** button → **Download ZIP**
3. Extract the ZIP file to your Desktop.

To open the folder in Terminal:

* Open the `song_generator` folder in Finder.
* Right-click anywhere inside the folder → Select **"New Terminal at Folder"** (if available), or:

  * Open Terminal manually and type:

    ```bash
    cd ~/Desktop/song_generator-main
    ```

---

## 🐍 Step 3: Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

Once inside the environment, your terminal prompt should change to something like:

```
(venv) your-macbook:~/Desktop/song_generator-main user$
```

---

## 📦 Step 4: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install pydub

```

---

## 🎛 Step 5: Install FFmpeg (manually)

1. Visit: [https://evermeet.cx/ffmpeg/](https://evermeet.cx/ffmpeg/)
2. Download the `ffmpeg` binary for macOS.
3. Move it to a directory (e.g. `/usr/local/bin`):

   ```bash
   sudo mv ~/Downloads/ffmpeg /usr/local/bin/
   sudo chmod +x /usr/local/bin/ffmpeg
   ```
4. Test:

   ```bash
   ffmpeg -version
   ```

---

## 🛡️ Troubleshooting: FFmpeg Blocked by macOS Gatekeeper

If macOS prevents ffmpeg from running and you see this message:

    “ffmpeg” cannot be opened because the developer cannot be verified.

Follow these steps to allow it:
1. Try Running ffmpeg Manually

Open Terminal and type:

ffmpeg -version

If a security popup appears, continue with the steps below.
2. Allow ffmpeg in System Settings

    Click the Apple  menu → System Settings (or System Preferences on older macOS).

    Go to Privacy & Security.

    Scroll to the bottom and look for this message:

        "ffmpeg" was blocked from use because it is not from an identified developer.

    Click Allow Anyway.

3. Re-run ffmpeg

Go back to Terminal and run:

ffmpeg -version

You might get one more popup. This time, click Open to allow ffmpeg to run permanently.

## 🎵 Step 6: Add Your Samples

Place your `.wav` sample folders inside the `samples/` directory. Organize them as:

```
samples/
├── 80_A_minor/
│   ├── bass/
│   ├── chords/
│   ├── melody/
├── drums/
```

---

## 🚀 Step 7: Run the Generator

```bash
python main.py
```

This will generate up to 100 unique songs in the `output_songs/` folder.

---
