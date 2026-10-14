from tortoise import fields

from ._base import TortoiseBaseModel


class Household(TortoiseBaseModel):
    name = fields.CharField(max_length=255, db_index=True)
    slug = fields.CharField(max_length=255, null=True, db_index=True)
    group: fields.ForeignKeyRelation["Group"] = fields.ForeignKeyField(
        "models.Group", related_name="households", on_delete=fields.OnDelete.NO_ACTION, db_index=True
    )

    class Meta:
        table = "households"
        unique_together = (("group", "name"), ("group", "slug"))

