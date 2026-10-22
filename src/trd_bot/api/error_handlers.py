from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.requests import Request

from trd_bot.market_data.security import redact_sensitive_text


def _sanitize_validation_value(value: object) -> object:
    if isinstance(value, str):
        return redact_sensitive_text(
            value,
            fallback="invalid request value",
            max_length=500,
        )
    if isinstance(value, list):
        return [_sanitize_validation_value(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _sanitize_validation_value(item)
            for key, item in value.items()
            if key != "input"
        }
    return value


async def sanitized_request_validation_error_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Return validation details without echoing rejected request values."""

    del request
    if not isinstance(exc, RequestValidationError):
        raise exc

    encoded = jsonable_encoder(exc.errors())
    sanitized = _sanitize_validation_value(encoded)
    return JSONResponse(
        status_code=422,
        content={"detail": sanitized},
    )
