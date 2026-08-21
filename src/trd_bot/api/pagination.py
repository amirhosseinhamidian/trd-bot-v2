from collections.abc import Sequence
from typing import Generic, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

ItemT = TypeVar("ItemT")


class PaginationParams(BaseModel):
    """Validated pagination parameters received by API endpoints."""

    model_config = ConfigDict(frozen=True)

    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class Page(BaseModel, Generic[ItemT]):  # noqa: UP046
    """A paginated collection with navigation metadata."""

    model_config = ConfigDict(frozen=True)

    items: tuple[ItemT, ...]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    count: int = Field(ge=0)
    has_next: bool
    has_previous: bool

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        if self.count != len(self.items):
            raise ValueError("count must match the number of items")

        if self.count > self.limit:
            raise ValueError("item count cannot be greater than limit")

        if self.count > 0 and self.offset + self.count > self.total:
            raise ValueError("page items cannot exceed the total item count")

        expected_has_next = self.offset + self.count < self.total
        if self.has_next != expected_has_next:
            raise ValueError("has_next is inconsistent with the page values")

        expected_has_previous = self.offset > 0 and self.total > 0
        if self.has_previous != expected_has_previous:
            raise ValueError("has_previous is inconsistent with the page values")

        return self


def build_page(  # noqa: UP047
    items: Sequence[ItemT],
    *,
    total: int,
    pagination: PaginationParams,
) -> Page[ItemT]:
    """Build a validated page from an already sliced collection."""

    page_items = tuple(items)
    count = len(page_items)

    return Page[ItemT](
        items=page_items,
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
        count=count,
        has_next=pagination.offset + count < total,
        has_previous=pagination.offset > 0 and total > 0,
    )
