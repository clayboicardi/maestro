"""Hand-overlay validators for AIOStreams schemas.

The auto-generated `schemas_generated.py` covers the structural shape but
strips Zod's runtime refinements (length checks that look up
`config.userLimits.*` at validate time). This module overlays those.

When AIOStreams bumps its `userLimits` defaults, update the constants
below. Read upstream:
https://github.com/Viren070/AIOStreams/blob/main/packages/core/src/config/index.ts
"""

from __future__ import annotations

from maestro.aiostreams import schemas_generated as _gen

UserData = _gen.UserDataSchema

MAX_SEL_EXPRESSION_LENGTH = 2000
MAX_FORMATTER_TEMPLATE_LENGTH = 4000


def validate_sel_expression(value: str) -> str:
    """Enforce upstream's `userLimits.sel.maxExpressionLength`.

    Raises ValueError when over limit so pydantic can surface the field
    in its standard validation error response.
    """
    if len(value) > MAX_SEL_EXPRESSION_LENGTH:
        raise ValueError(
            f"Stream expression exceeds maximum length of {MAX_SEL_EXPRESSION_LENGTH} characters."
        )
    return value


def validate_formatter_template(value: str) -> str:
    """Enforce upstream's `userLimits.maxFormatterTemplateLength`."""
    if len(value) > MAX_FORMATTER_TEMPLATE_LENGTH:
        raise ValueError(
            f"Formatter template exceeds maximum length of {MAX_FORMATTER_TEMPLATE_LENGTH} characters."
        )
    return value
