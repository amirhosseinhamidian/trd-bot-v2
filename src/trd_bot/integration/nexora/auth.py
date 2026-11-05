from __future__ import annotations

import hmac
import os
import stat
from pathlib import Path
from typing import Final

MINIMUM_TOKEN_BYTES: Final = 32
MAXIMUM_TOKEN_BYTES: Final = 4096
BEARER_PREFIX: Final = "Bearer "


class ServiceTokenConfigurationError(RuntimeError):
    """Raised when the operator-owned service-token file is unsafe or unavailable."""


def load_service_token(path: Path | None) -> bytes:
    """Read a bounded service token from an absolute, private, regular file."""

    if path is None or not path.is_absolute():
        raise ServiceTokenConfigurationError("service token is unavailable")

    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as error:
        raise ServiceTokenConfigurationError("service token is unavailable") from error
    try:
        file_status = os.fstat(descriptor)
        if not stat.S_ISREG(file_status.st_mode):
            raise ServiceTokenConfigurationError("service token is unavailable")
        if file_status.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            raise ServiceTokenConfigurationError("service token is unavailable")
        if not file_status.st_mode & stat.S_IRUSR:
            raise ServiceTokenConfigurationError("service token is unavailable")
        if not MINIMUM_TOKEN_BYTES <= file_status.st_size <= MAXIMUM_TOKEN_BYTES:
            raise ServiceTokenConfigurationError("service token is unavailable")
        token = os.read(descriptor, MAXIMUM_TOKEN_BYTES + 1)
    except OSError as error:
        raise ServiceTokenConfigurationError("service token is unavailable") from error
    finally:
        os.close(descriptor)

    if len(token) != file_status.st_size:
        raise ServiceTokenConfigurationError("service token is unavailable")
    if any(value < 33 or value > 126 for value in token):
        raise ServiceTokenConfigurationError("service token is unavailable")
    return token


def bearer_token_matches(authorization: str | None, expected_token: bytes) -> bool:
    """Compare a presented bearer token without leaking prefix or token differences."""

    if authorization is None or not authorization.startswith(BEARER_PREFIX):
        return False
    presented = authorization.removeprefix(BEARER_PREFIX).encode("utf-8")
    return hmac.compare_digest(presented, expected_token)
