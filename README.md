# SilenceCut

SilenceCut is a small Flask web app that removes silent pauses from MP4 videos. Choose a video in the browser, adjust the silence-detection settings, and download the edited result. Video processing runs on the machine hosting the app.

## Requirements

- Python 3
- [FFmpeg](https://ffmpeg.org/), including both `ffmpeg` and `ffprobe` on your `PATH`
- The Python package listed in `requirements.txt` (Flask)

For example, on macOS you can install FFmpeg with Homebrew:

```bash
brew install ffmpeg
```

## Setup and run

From the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser. The development server runs with Flask debug mode enabled; do not expose it to an untrusted network as-is.

## Using the app

1. Select or drag in an MP4 video.
2. Choose the processing settings:
   - **Silence threshold**: audio below this level is considered silent. A higher (less negative) threshold detects quieter audio as silence.
   - **Minimum silence duration**: pauses shorter than this are kept.
   - **Padding**: a small buffer retained around detected pauses to avoid abrupt cuts.
3. Click **Remove Silences**. The app detects quiet intervals, keeps the remaining video segments, and joins them into an MP4.
4. Review the duration statistics and download the result.

## Project layout

```text
.
├── app.py                 # Flask routes and FFmpeg processing
├── requirements.txt       # Python dependencies
├── templates/
│   └── index.html         # Browser UI, styles, and client-side behavior
├── uploads/               # Temporary uploaded videos (created at runtime)
├── temp/                  # Temporary video segments (created at runtime)
└── outputs/               # Processed videos (created at runtime)
```

The `uploads/`, `temp/`, and `outputs/` directories are created automatically when the app starts. Their contents are ignored by Git.

## HTTP routes

- `GET /` — serves the web interface.
- `POST /upload` — accepts an MP4 and the `threshold`, `min_duration`, and `padding` settings; returns processing statistics and the output filename as JSON.
- `GET /download/<filename>` — downloads a processed video.
- `POST /cleanup/<filename>` — deletes a processed video after it is no longer needed.

## Tests

From the project directory, with the virtual environment above active:

```bash
python -m pip install pytest
python -m pytest
```

The tests cover silence detection output and interval calculations without running FFmpeg.

## Notes

- Input is limited to MP4 files by the interface and upload route.
- FFmpeg stream copy is attempted for cutting and concatenation; if concatenation fails, the app attempts an H.264/AAC re-encode.
