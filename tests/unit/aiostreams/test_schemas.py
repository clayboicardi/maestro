"""AIOStreams schema overlay tests."""

import pytest

from maestro.aiostreams import schemas


def test_user_data_re_exports_from_generated() -> None:
    """schemas.UserData re-exports from schemas_generated."""
    assert hasattr(schemas, "UserData")


def test_sel_expression_length_validator_rejects_oversize() -> None:
    """Runtime refinement: SEL expression > MAX_SEL_LENGTH chars is rejected."""
    too_long = "x" * (schemas.MAX_SEL_EXPRESSION_LENGTH + 1)
    with pytest.raises(ValueError, match="Stream expression exceeds maximum length"):
        schemas.validate_sel_expression(too_long)


def test_sel_expression_validator_accepts_normal_length() -> None:
    """Strings under the limit pass."""
    schemas.validate_sel_expression("typeof stream === 'movie'")


def test_formatter_template_validator_enforces_max_length() -> None:
    too_long = "x" * (schemas.MAX_FORMATTER_TEMPLATE_LENGTH + 1)
    with pytest.raises(ValueError, match="Formatter template exceeds maximum length"):
        schemas.validate_formatter_template(too_long)
