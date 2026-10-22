from trd_bot.market_data import redact_sensitive_text


def test_sensitive_provider_error_values_are_redacted() -> None:
    raw = (
        "request failed "
        "api_key=alpha-secret "
        'token: "beta-secret" '
        "Authorization: Bearer gamma-secret "
        "https://user:delta-secret@example.test/path"
    )

    redacted = redact_sensitive_text(
        raw,
        fallback="market-data request failed",
    )

    assert "alpha-secret" not in redacted
    assert "beta-secret" not in redacted
    assert "gamma-secret" not in redacted
    assert "delta-secret" not in redacted
    assert "[REDACTED]" in redacted


def test_empty_provider_error_uses_safe_fallback() -> None:
    assert (
        redact_sensitive_text("  ", fallback="market-data request failed")
        == "market-data request failed"
    )
