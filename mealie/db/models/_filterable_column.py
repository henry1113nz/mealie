"""Filterability is recorded by each model's ``__filterable_fields__`` set."""

from typing import Annotated

type FilterableColumn[T] = Annotated[T, "filterable"]
