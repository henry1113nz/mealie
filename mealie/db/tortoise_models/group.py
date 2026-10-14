from tortoise import fields

from ._base import TortoiseBaseModel


class Group(TortoiseBaseModel):
    name = fields.CharField(max_length=255, unique=True, db_index=True)
    slug = fields.CharField(max_length=255, null=True, unique=True, db_index=True)

    class Meta:
        table = "groups"

