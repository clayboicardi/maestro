"""ToolAnnotations helper tests."""

from maestro.annotations import compute_annotation, destructive, pure_compute, read_only


def test_read_only_helper() -> None:
    a = read_only(title="Get Config")
    assert a.title == "Get Config"
    assert a.readOnlyHint is True
    assert a.destructiveHint is False


def test_destructive_helper() -> None:
    a = destructive(title="Set Languages")
    assert a.title == "Set Languages"
    assert a.readOnlyHint is False
    assert a.destructiveHint is True


def test_pure_compute_helper() -> None:
    a = pure_compute(title="Dedupe Streams")
    assert a.title == "Dedupe Streams"
    assert a.readOnlyHint is False
    assert a.destructiveHint is False


def test_compute_annotation_by_prefix() -> None:
    """Tool name -> annotation kind heuristic for CI lint."""
    assert compute_annotation("aiostreams_get_config") == "read"
    assert compute_annotation("aiostreams_set_preferred_languages") == "write"
    assert compute_annotation("aiostreams_save") == "write"
    assert compute_annotation("aiostreams_apply_template") == "write"
    assert compute_annotation("stremio_dedupe_streams") == "compute"
    assert compute_annotation("torrentio_build_url") == "compute"
    assert compute_annotation("realdebrid_filter_gate_check") == "compute"
    assert compute_annotation("realdebrid_check_cache") == "read"
    assert compute_annotation("realdebrid_unrestrict_link") == "write"
    assert compute_annotation("find_best_stream") == "write"
