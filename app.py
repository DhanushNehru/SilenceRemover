import os
import re
import uuid
import subprocess
import shutil
import json
import math
from flask import Flask, request, render_template, send_file, jsonify

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
OUTPUT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'outputs')
TEMP_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp')

for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER, TEMP_FOLDER]:
    os.makedirs(folder, exist_ok=True)


@app.route('/')
def index():
    return render_template('index.html')


def get_video_duration(filepath):
    """Get the duration of a video file in seconds."""
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        filepath
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip())


def detect_silences(filepath, threshold=-30, min_duration=0.5):
    """
    Use ffmpeg's silencedetect filter to find silent segments.
    Returns a list of (start, end) tuples for each silent segment.
    """
    cmd = [
        'ffmpeg', '-i', filepath,
        '-af', f'silencedetect=noise={threshold}dB:d={min_duration}',
        '-f', 'null', '-'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stderr

    # Parse silence_start and silence_end from ffmpeg output
    silence_starts = re.findall(r'silence_start: ([\d.]+)', output)
    silence_ends = re.findall(r'silence_end: ([\d.]+)', output)

    silences = []
    for i in range(len(silence_ends)):
        start = float(silence_starts[i]) if i < len(silence_starts) else 0
        end = float(silence_ends[i])
        silences.append((start, end))

    # If there's an unmatched silence_start at the end (silence till end of video)
    if len(silence_starts) > len(silence_ends):
        duration = get_video_duration(filepath)
        silences.append((float(silence_starts[-1]), duration))

    return silences


def compute_non_silent_intervals(silences, total_duration, padding=0.1):
    """
    Given a list of silent intervals and total duration,
    compute the non-silent intervals with padding.
    """
    if not silences:
        return [(0, total_duration)]

    non_silent = []

    # Before first silence
    first_silence_start = silences[0][0]
    if first_silence_start > 0:
        end = min(first_silence_start + padding, silences[0][1])
        non_silent.append((0, end))

    # Between silences
    for i in range(len(silences) - 1):
        start = max(silences[i][1] - padding, silences[i][0])
        end = min(silences[i + 1][0] + padding, silences[i + 1][1])
        if start < end:
            non_silent.append((start, end))

    # After last silence
    last_silence_end = silences[-1][1]
    if last_silence_end < total_duration:
        start = max(last_silence_end - padding, silences[-1][0])
        non_silent.append((start, total_duration))

    return non_silent


def cut_and_concat(input_path, intervals, output_path, job_id):
    """
    Cut the non-silent intervals from the input video and concatenate them.
    Uses ffmpeg's concat demuxer for efficient concatenation.
    """
    temp_dir = os.path.join(TEMP_FOLDER, job_id)
    os.makedirs(temp_dir, exist_ok=True)

    segment_files = []

    for i, (start, end) in enumerate(intervals):
        duration = end - start
        if duration < 0.05:  # Skip very tiny segments
            continue

        segment_path = os.path.join(temp_dir, f'segment_{i:04d}.mp4')
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start),
            '-i', input_path,
            '-t', str(duration),
            '-c', 'copy',
            '-avoid_negative_ts', 'make_zero',
            segment_path
        ]
        subprocess.run(cmd, capture_output=True, text=True)

        if os.path.exists(segment_path) and os.path.getsize(segment_path) > 0:
            segment_files.append(segment_path)

    if not segment_files:
        # No segments to concatenate, return original
        shutil.copy2(input_path, output_path)
        return

    # Create concat file list
    concat_file = os.path.join(temp_dir, 'concat_list.txt')
    with open(concat_file, 'w') as f:
        for seg in segment_files:
            f.write(f"file '{seg}'\n")

    # Concatenate all segments
    cmd = [
        'ffmpeg', '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', concat_file,
        '-c', 'copy',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    # If copy mode fails (can happen with some codecs), try re-encoding
    if result.returncode != 0 or not os.path.exists(output_path):
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '192k',
            output_path
        ]
        subprocess.run(cmd, capture_output=True, text=True)

    # Clean up temp segments
    shutil.rmtree(temp_dir, ignore_errors=True)


@app.route('/upload', methods=['POST'])
def upload():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400

    file = request.files['video']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not file.filename.lower().endswith('.mp4'):
        return jsonify({'error': 'Only MP4 files are supported'}), 400

    # Get parameters from form
    try:
        threshold = float(request.form.get('threshold', -30))
        min_duration = float(request.form.get('min_duration', 0.5))
        padding = float(request.form.get('padding', 0.1))
    except ValueError:
        return jsonify({'error': 'Invalid numeric parameters'}), 400

    # Validate that all parameters are finite
    if not all(math.isfinite(v) for v in
               (threshold, min_duration, padding)):
        return jsonify({'error': 'Parameters must be finite numbers'}), 400

    # Validate parameter range
    if threshold < -90 or threshold > 0:
        return jsonify({
            'error': 'Threshold must be between -90 and 0 dB'
        }), 400
    if min_duration <= 0:
        return jsonify({
            'error': 'Minimum silence duration must be greater than 0'
        }), 400
    if padding < 0:
        return jsonify({
            'error': 'Padding must be non-negative'
        }), 400

    # Generate unique job ID
    job_id = str(uuid.uuid4())[:8]

    # Save uploaded file
    input_filename = f'{job_id}_input.mp4'
    input_path = os.path.join(UPLOAD_FOLDER, input_filename)
    file.save(input_path)

    try:
        # Get original duration
        original_duration = get_video_duration(input_path)

        # Detect silences
        silences = detect_silences(input_path, threshold=threshold, min_duration=min_duration)

        # Compute non-silent intervals
        intervals = compute_non_silent_intervals(silences, original_duration, padding=padding)

        # Cut and concatenate
        output_filename = f'{job_id}_output.mp4'
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)
        cut_and_concat(input_path, intervals, output_path, job_id)

        # Get output duration
        output_duration = get_video_duration(output_path)

        # Calculate stats
        time_saved = original_duration - output_duration
        reduction_pct = (time_saved / original_duration * 100) if original_duration > 0 else 0

        # Clean up input file
        os.remove(input_path)

        return jsonify({
            'success': True,
            'filename': output_filename,
            'original_duration': round(original_duration, 2),
            'output_duration': round(output_duration, 2),
            'time_saved': round(time_saved, 2),
            'reduction_pct': round(reduction_pct, 1),
            'silences_found': len(silences)
        })

    except Exception as e:
        # Clean up on error
        if os.path.exists(input_path):
            os.remove(input_path)
        return jsonify({'error': str(e)}), 500


@app.route('/download/<filename>')
def download(filename):
    filepath = os.path.join(OUTPUT_FOLDER, filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404

    return send_file(
        filepath,
        as_attachment=True,
        download_name='silence_removed.mp4',
        mimetype='video/mp4'
    )


@app.route('/cleanup/<filename>', methods=['POST'])
def cleanup(filename):
    """Clean up output file after download."""
    filepath = os.path.join(OUTPUT_FOLDER, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    return jsonify({'success': True})


if __name__ == '__main__':
    print("\n🎬 Video Silence Remover")
    print("=" * 40)
    print("Open http://localhost:5000 in your browser")
    print("=" * 40 + "\n")
    app.run(debug=True, port=5000)
