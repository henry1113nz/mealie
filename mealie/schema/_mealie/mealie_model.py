from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, datetime
from enum import Enum
from typing import Any, ClassVar, Protocol, Self, cast

from humps.main import camelize
from pydantic import UUID4, AliasChoices, BaseModel, ConfigDict, Field, model_validator
from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.expressions import Case, Q, When
from tortoise.models import Model
from tortoise.queryset import QuerySet

HOUR_ONLY_TZ_PATTERN = re.compile(r"[+-]\d{2}$")


def UpdatedAtField(*args, **kwargs):
    """
    Wrapper for Pydantic's Field, which sets default values for our update_at aliases

    Since the database stores this value as update_at, we want to accept this as a possible value
    """

    kwargs.pop("alias", None)
    kwargs.pop("alias_generator", None)

    # ensure the alias is not overwritten by the generator, if there is one
    # https://docs.pydantic.dev/latest/concepts/alias/#alias-priority
    kwargs["alias_priority"] = 2

    kwargs["validation_alias"] = AliasChoices("update_at", "updateAt", "updated_at", "updatedAt")
    kwargs["serialization_alias"] = "updatedAt"

    return Field(*args, **kwargs)


class SearchType(Enum):
    fuzzy = "fuzzy"
    tokenized = "tokenized"


class MealieModel(BaseModel):
    _fuzzy_similarity_threshold: ClassVar[float] = 0.5
    _normalize_search: ClassVar[bool] = False
    _searchable_properties: ClassVar[list[str]] = []
    """
    Searchable properties for the search API.
    The first property will be used for sorting (order_by)
    """
    model_config = ConfigDict(alias_generator=camelize, populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def fix_hour_only_tz[T: BaseModel](cls, data: T) -> T:
        """
        Fixes datetimes with timezones that only have the hour portion.

        Pydantic assumes timezones are in the format +HH:MM, but postgres returns +HH.
        https://github.com/pydantic/pydantic/issues/8609
        """
        for field, field_info in cls.model_fields.items():
            if field_info.annotation != datetime:
                continue
            try:
                if not isinstance(val := getattr(data, field), str):
                    continue
            except AttributeError:
                continue
            if re.search(HOUR_ONLY_TZ_PATTERN, val):
                setattr(data, field, val + ":00")

        return data

    @model_validator(mode="after")
    def set_tz_info(self) -> Self:
        """
        Adds UTC timezone information to all datetimes in the model.
        The server stores everything in UTC without timezone info.
        """
        for field in self.__class__.model_fields:
            val = getattr(self, field)
            if not isinstance(val, datetime):
                continue
            if not val.tzinfo:
                setattr(self, field, val.replace(tzinfo=UTC))

        return self

    def cast[T: BaseModel](self, cls: type[T], **kwargs) -> T:
        """
        Cast the current model to another with additional arguments. Useful for
        transforming DTOs into models that are saved to a database
        """
        create_data = {
            field: getattr(self, field) for field in self.__class__.model_fields if field in cls.model_fields
        }
        create_data.update(kwargs or {})
        return cls(**create_data)

    def map_to[T: BaseModel](self, dest: T) -> T:
        """
        Map matching values from the current model to another model. Model returned
        for method chaining.
        """

        for field in self.__class__.model_fields:
            if field in dest.__class__.model_fields:
                setattr(dest, field, getattr(self, field))

        return dest

    def map_from(self, src: BaseModel):
        """
        Map matching values from another model to the current model.
        """

        for field in src.__class__.model_fields:
            if field in self.__class__.model_fields:
                setattr(self, field, getattr(src, field))

    def merge[T: BaseModel](self, src: T, replace_null=False):
        """
        Replace matching values from another instance to the current instance.
        """

        for field in src.__class__.model_fields:
            val = getattr(src, field)
            if field in self.__class__.model_fields and (val is not None or replace_null):
                setattr(self, field, val)

    @classmethod
    def loader_options(cls) -> list[str]:
        return []

    @classmethod
    def filter_search_query(
        cls,
        db_model: type[Model],
        query: QuerySet,
        session: BaseDBAsyncClient,
        search_type: SearchType,
        search: str,
        search_list: list[str],
    ) -> QuerySet:
        """
        Filters a search query based on model attributes

        Can be overridden to support a more advanced search
        """

        if not cls._searchable_properties:
            raise AttributeError("Not Implemented")

        properties = cls._searchable_properties
        if search_type is SearchType.fuzzy:
            from mealie.services.query_filter.expressions import WordSimilarity

            annotations = {
                f"_search_similarity_{index}": WordSimilarity(prop, search) for index, prop in enumerate(properties)
            }
            query = query.annotate(**annotations)
            matches = Q()
            for key in annotations:
                condition: dict[str, Any] = {key + "__gte": cls._fuzzy_similarity_threshold}
                matches |= Q(**condition)
            return query.filter(matches).order_by("-_search_similarity_0")
        matches = Q()
        for prop in properties:
            for token in search_list:
                matches |= Q(**{prop + "__icontains": token})
        return (
            query.filter(matches)
            .annotate(
                _search_rank=Case(
                    When(Q(**{properties[0] + "__icontains": search}), then=cast(Any, 1)), default=cast(Any, 0)
                )
            )
            .order_by("-_search_rank")
        )


class HasUUID(Protocol):
    id: UUID4


def extract_uuids(models: Sequence[HasUUID]) -> list[UUID4]:
    return [x.id for x in models]
