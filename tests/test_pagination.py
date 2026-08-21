import pytest
from pydantic import ValidationError

from trd_bot.api.pagination import Page, PaginationParams, build_page


def test_pagination_params_use_safe_defaults() -> None:
    pagination = PaginationParams()

    assert pagination.limit == 20
    assert pagination.offset == 0


@pytest.mark.parametrize("limit", [0, 101])
def test_pagination_params_reject_invalid_limit(limit: int) -> None:
    with pytest.raises(ValidationError):
        PaginationParams(limit=limit)


def test_pagination_params_reject_negative_offset() -> None:
    with pytest.raises(ValidationError):
        PaginationParams(offset=-1)


def test_build_page_returns_first_page_metadata() -> None:
    pagination = PaginationParams(limit=2, offset=0)

    page = build_page(
        ["experiment-1", "experiment-2"],
        total=5,
        pagination=pagination,
    )

    assert page.items == ("experiment-1", "experiment-2")
    assert page.total == 5
    assert page.count == 2
    assert page.has_next is True
    assert page.has_previous is False


def test_build_page_returns_last_page_metadata() -> None:
    pagination = PaginationParams(limit=2, offset=4)

    page = build_page(
        ["experiment-5"],
        total=5,
        pagination=pagination,
    )

    assert page.count == 1
    assert page.has_next is False
    assert page.has_previous is True


def test_build_page_allows_offset_beyond_available_items() -> None:
    pagination = PaginationParams(limit=20, offset=100)

    page: Page[str] = build_page(
        [],
        total=5,
        pagination=pagination,
    )

    assert page.items == ()
    assert page.count == 0
    assert page.has_next is False
    assert page.has_previous is True


def test_page_rejects_incorrect_count() -> None:
    with pytest.raises(
        ValidationError,
        match="count must match the number of items",
    ):
        Page[str](
            items=("experiment-1",),
            total=1,
            limit=20,
            offset=0,
            count=0,
            has_next=False,
            has_previous=False,
        )


def test_page_rejects_more_items_than_limit() -> None:
    with pytest.raises(
        ValidationError,
        match="item count cannot be greater than limit",
    ):
        Page[str](
            items=("experiment-1", "experiment-2"),
            total=2,
            limit=1,
            offset=0,
            count=2,
            has_next=False,
            has_previous=False,
        )
