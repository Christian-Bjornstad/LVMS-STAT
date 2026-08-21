from __future__ import annotations

import re
from dataclasses import dataclass

from lvms_stat.workflow import ControlIdentity


class BatchControlError(ValueError):
    """A batch document or control identity is unsafe."""


_FRAME_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,120}")


@dataclass(frozen=True)
class DocumentControlIdentity:
    frame: str
    control: ControlIdentity


def validate_document_control(
    identity: DocumentControlIdentity,
) -> DocumentControlIdentity:
    if (
        not isinstance(identity, DocumentControlIdentity)
        or not isinstance(identity.frame, str)
        or _FRAME_PATTERN.fullmatch(identity.frame) is None
        or not isinstance(identity.control, ControlIdentity)
    ):
        raise BatchControlError("batch control identity is invalid")
    return identity
