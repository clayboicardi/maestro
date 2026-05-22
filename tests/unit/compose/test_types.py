"""StreamResolution result type tests."""

from maestro.compose.types import Attempt, StreamMetadata, StreamResolution


def test_resolution_can_be_success() -> None:
    res = StreamResolution(
        url="https://rd.example/x.mkv",
        metadata=StreamMetadata(
            resolution="1080p",
            codec="x264",
            language="English",
            size_gb=8.2,
        ),
        source="aiostreams",
        attempts=[],
        elapsed_ms=2840,
    )
    assert res.ok is True
    assert res.url == "https://rd.example/x.mkv"


def test_resolution_can_be_failure() -> None:
    res = StreamResolution(
        url=None,
        metadata=None,
        source="aiostreams",
        attempts=[
            Attempt(hash="abc", status="filter_gate_block", filename="x.WEB-DL.mkv"),
            Attempt(hash="def", status="unrestrict_4xx", error="403"),
        ],
        elapsed_ms=5210,
    )
    assert res.ok is False
    assert len(res.attempts) == 2


def test_metadata_optional_fields() -> None:
    m = StreamMetadata(resolution="720p")
    assert m.resolution == "720p"
    assert m.codec is None
