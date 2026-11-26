import subprocess

import pytest

import app


@pytest.mark.parametrize(('silences', 'padding', 'expected'), [
    pytest.param([], 0.25, [(0, 10)], id='no-silence'),
    pytest.param([(0, 2)], 0.25, [(1.75, 10)], id='leading-silence'),
    pytest.param([(8, 10)], 0.25, [(0, 8.25)], id='trailing-silence'),
    pytest.param([(0, 10)], 0.25, [], id='all-silent'),
    pytest.param([(2, 4), (6, 8)], 0.25, [(0, 2.25), (3.75, 6.25), (7.75, 10)],
                 id='separate-pauses'),
    pytest.param([(2, 4), (4, 6)], 0.25, [(0, 2.25), (5.75, 10)],
                 id='no-sound-between-touching-pauses'),
    pytest.param([(4, 5)], 2, [(0, 10)], id='large-padding-does-not-repeat-footage'),
    pytest.param([(0, 2), (2.1, 10)], -0.1, [], id='padding-leaves-no-interior-gap'),
])
def test_non_silent_intervals(silences, padding, expected):
    assert app.compute_non_silent_intervals(silences, 10, padding) == expected


FFMPEG_LOG = """frame=   12 time=00:00:01.00
[silencedetect @ 0x1] silence_start: 0
[silencedetect @ 0x1] silence_end: 1.25 | silence_duration: 1.25
[silencedetect @ 0x1] silence_start: 7.5
"""


def test_parse_silencedetect_output():
    assert app.parse_silencedetect_output(FFMPEG_LOG) == [(0, 1.25), (7.5, None)]
    assert app.parse_silencedetect_output('frame=50 time=00:00:02.00') == []


@pytest.mark.parametrize(('log', 'expected', 'probes'), [
    (FFMPEG_LOG, [(0, 1.25), (7.5, 10)], ['video.mp4']),
    (FFMPEG_LOG + 'silence_end: 9 | silence_duration: 1.5', [(0, 1.25), (7.5, 9)], []),
])
def test_detect_silences_probes_duration_only_for_an_open_end(monkeypatch, log, expected, probes):
    monkeypatch.setattr(app.subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess([], 0, stderr=log))
    paths = []

    def get_duration(path):
        paths.append(path)
        return 10

    monkeypatch.setattr(app, 'get_video_duration', get_duration)
    assert app.detect_silences('video.mp4') == expected
    assert paths == probes
