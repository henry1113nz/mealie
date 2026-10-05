"""Payload configuration shared by async nested model persistence."""

from pydantic import BaseModel, Field

from .._model_base import TortoiseModel


class AutoInitConfig(BaseModel):
    get_attr: str | None = None
    exclude: set = Field(default_factory=lambda: {"id"})


def _get_config(relation_cls: type[TortoiseModel], *, protect_primary_key: bool = True) -> AutoInitConfig:
    config = AutoInitConfig()
    for key, value in getattr(relation_cls, "model_config", {}).items():
        if key not in AutoInitConfig.model_fields:
            continue
        if key == "exclude" and protect_primary_key:
            config.exclude |= set(value)
        else:
            setattr(config, key, value)
    return config


def get_lookup_attr(relation_cls: type[TortoiseModel]) -> str:
    return _get_config(relation_cls).get_attr or relation_cls._meta.pk_attr
