"""Unbounded strings with native SQLite and PostgreSQL index support."""

from typing import TYPE_CHECKING, Self, overload

from tortoise import Model, fields


class StringField(fields.Field[str]):
    """Store text without adding a length limit to existing API input.

    Both supported databases can index TEXT columns. Tortoise's portable
    TextField prohibits indexes because other database engines restrict them.
    """

    field_type = str
    SQL_TYPE = "TEXT"

    if TYPE_CHECKING:

        @overload
        def __get__(self, instance: None, owner: type[Model]) -> Self: ...

        @overload
        def __get__(self, instance: Model, owner: type[Model]) -> str: ...

        def __get__(self, instance: Model | None, owner: type[Model]) -> Self | str: ...

        def __set__(self, instance: Model, value: str | None) -> None: ...
