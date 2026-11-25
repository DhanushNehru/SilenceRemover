<div align="center">

# SilenceCut

**Remove silent pauses from MP4 videos in your browser.**

[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/flask-web%20app-000000?logo=flask)
![FFmpeg](https://img.shields.io/badge/powered%20by-FFmpeg-007808?logo=ffmpeg&logoColor=white)

[Quick start](#quick-start) · [How it works](#how-it-works) · [Settings](#settings) · [API](#http-api) · [Contributing](#contributing)

</div>

---

SilenceCut is a small Flask app for tightening up talking-head videos, lectures, screen recordings and tutorials. Pick an MP4, tune the silence settings, and download a version with the dead air cut out. Processing runs on the machine that hosts the app, so your video is never sent to a third party.

## Features

- Drag-and-drop upload from the browser
- Adjustable silence threshold, minimum pause length and padding
- Before and after duration stats, plus the number of silences found
- Fast cuts using FFmpeg stream copy, with an automatic H.264/AAC re-encode fallback
- One Python dependency (Flask)

## Quick start

### Requirements

- Python 3
- [FFmpeg](https://ffmpeg.org/) with both `ffmpeg` and `ffprobe` on your `PATH`

```bash
# macOS
brew install ffmpeg

# Debian / Ubuntu
sudo apt install ffmpeg
```

### Run it

```bash
git clone https://github.com/DhanushNehru/SilenceRemover.git
cd SilenceRemover

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python app.py
```

Open <http://localhost:5000>.

> **Note:** `app.py` starts Flask with `debug=True`. Run it on your own machine or a trusted network only, and do not expose it to the internet as-is.

## Settings

| Setting | Form field | Default | What it does |
| --- | --- | --- | --- |
| Silence threshold | `threshold` | `-30` dB | Audio below this level counts as silence. A higher (less negative) value treats quieter sound as silence. |
| Minimum silence duration | `min_duration` | `0.5` s | Pauses shorter than this are kept. |
| Padding | `padding` | `0.1` s | Buffer kept around each cut so speech does not clip. |

## How it works

1. The upload is saved to `uploads/` with a short random job ID.
2. `ffprobe` reads the duration and `ffmpeg -af silencedetect` finds the silent intervals.
3. The non-silent intervals are computed, with padding applied.
4. Each interval is cut into a segment with `-c copy`.
5. The segments are joined with the FFmpeg concat demuxer. If that fails, the app re-encodes to H.264/AAC.
6. The result is written to `outputs/` and offered for download. The uploaded input is deleted after processing.

## HTTP API

| Method | Route | Description |
| --- | --- | --- |
| `GET` | `/` | Web interface |
| `POST` | `/upload` | Multipart upload of `video` (MP4) plus `threshold`, `min_duration` and `padding`. Returns JSON with `filename`, `original_duration`, `output_duration`, `time_saved`, `reduction_pct` and `silences_found`. |
| `GET` | `/download/<filename>` | Download a processed video |
| `POST` | `/cleanup/<filename>` | Delete a processed video |

Example:

```bash
curl -F "video=@talk.mp4" -F "threshold=-30" -F "min_duration=0.5" -F "padding=0.1" \
  http://localhost:5000/upload
```

## Project structure

```text
.
├── app.py              # Flask routes and FFmpeg processing
├── requirements.txt    # Python dependencies
└── templates/
    └── index.html      # Browser UI, styles and client-side logic
```

`uploads/`, `temp/` and `outputs/` are created at startup and ignored by Git.

## Limitations

- MP4 input only.
- Stream-copy cuts land on keyframes, so cut points can be slightly off. The re-encode fallback is slower.
- No authentication, upload size limit or job queue, so this is built for personal or local use.
- No automated tests yet.

## Contributing

Contributions are welcome. Check the [open issues](https://github.com/DhanushNehru/SilenceRemover/issues), especially those labelled `good first issue`, then fork the repo, make your change on a branch and open a pull request.

## License

Released under the [Apache License 2.0](LICENSE).
