import re

_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)(\b(?:api[-_]?key|api[-_]?secret|access[-_]?key|private[-_]?key|"
    r"secret(?:[-_]?key)?|token|password|passphrase|signature|authorization|"
    r"credential)\b[\"']?\s*[:=]\s*[\"']?)([^\"'&,;\s}]+)"
)
_BEARER_CREDENTIAL = re.compile(r"(?i)(\bbearer\s+)([^\s,;]+)")
_URL_USER_INFO = re.compile(r"(?i)(https?://)([^/\s:@]+):([^@\s/]+)@")


def redact_sensitive_text(
    value: object,
    *,
    fallback: str,
    max_length: int = 500,
) -> str:
    """Return bounded user-visible text with common credential shapes removed."""

    normalized = str(value).strip()
    if not normalized:
        normalized = fallback

    redacted = _URL_USER_INFO.sub(r"\1[REDACTED]@", normalized)
    redacted = _BEARER_CREDENTIAL.sub(r"\1[REDACTED]", redacted)
    redacted = _SENSITIVE_ASSIGNMENT.sub(r"\1[REDACTED]", redacted)
    return redacted[:max_length]
