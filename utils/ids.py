"""ID helpers. All primary keys are 32-char uuid4 hex strings."""

from uuid import uuid4


def new_id() -> str:
    return uuid4().hex
