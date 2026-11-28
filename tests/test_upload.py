
import io
import pytest
from app import app
import app as app_module
from unittest.mock import Mock


@pytest.mark.parametrize("field, value", [
    (field, value)
    for field in ["threshold", "min_duration", "padding"]
    for value in ["abc", "", "NaN", "inf", "-inf"]
] + [
    ("threshold", "-91"),
    ("threshold", "1"),
    ("min_duration", "-1"),
    ("min_duration", "0"),
    ("padding", "-0.1"),
])

def test_upload_invalid_parameter(field, value, monkeypatch,tmp_path):

    
    monkeypatch.setitem(app.config, "TESTING", True)
    monkeypatch.setitem(app.config, "PROPAGATE_EXCEPTIONS", False)
    monkeypatch.setattr(app_module, "UPLOAD_FOLDER", str(tmp_path))

    mock_duration = Mock()
    monkeypatch.setattr(
        app_module, "get_video_duration", mock_duration
    )

    client = app.test_client()

    data = {
        "video": (io.BytesIO(b""), "test.mp4"),
        "threshold": "-30",
        "min_duration": "0.5",
        "padding": "0.1",
    }

    data[field] = value

   
    response = client.post(
        "/upload",
        data=data,
        content_type="multipart/form-data",
    )

    
    assert response.status_code == 400
    assert response.is_json
    assert "error" in response.get_json()
    mock_duration.assert_not_called()
    assert not list(tmp_path.iterdir())



@pytest.mark.parametrize(
    "threshold, min_duration, padding, use_defaults", [
        (-30, 0.5, 0.1, False),
        (-45, 1.5, 0.2, False),
        (-90, 0.5, 0.1, False),
        (0, 0.5, 0.1, False),
        (-30, 0.5, 0, False),
        (-30, 0.01, 0.1, False),
        (-30, 0.5, 0.1, True),
    ]
)
def test_upload_valid_parameters(
    monkeypatch, tmp_path,
    threshold, min_duration, padding, use_defaults
):
    monkeypatch.setitem(app.config, "TESTING", True)
    monkeypatch.setattr(app_module, "UPLOAD_FOLDER", str(tmp_path))
    monkeypatch.setattr(app_module, "OUTPUT_FOLDER", str(tmp_path))

    mock_duration = Mock(side_effect=[10.0, 8.0])
    mock_detect = Mock(return_value=[(4.0, 6.0)])
    mock_intervals = Mock(return_value=[(0.0, 4.0), (6.0, 10.0)])
    mock_cut = Mock(return_value=None)

    monkeypatch.setattr(app_module, "get_video_duration", mock_duration)
    monkeypatch.setattr(app_module, "detect_silences", mock_detect)
    monkeypatch.setattr(
        app_module, "compute_non_silent_intervals", mock_intervals
    )
    monkeypatch.setattr(app_module, "cut_and_concat", mock_cut)

    client = app.test_client()

    data = {
        "video": (io.BytesIO(b""), "test.mp4"),
    }

    if not use_defaults:
        data.update({
            "threshold": str(threshold),
            "min_duration": str(min_duration),
            "padding": str(padding),
        })

    response = client.post(
        "/upload",
        data=data,
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.is_json
    assert response.get_json()["success"] is True

    mock_detect.assert_called_once()
    mock_intervals.assert_called_once()
    mock_cut.assert_called_once()

    assert mock_detect.call_args.kwargs["threshold"] == threshold
    assert mock_detect.call_args.kwargs["min_duration"] == min_duration
    assert mock_intervals.call_args.kwargs["padding"] == padding
