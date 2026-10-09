import string
from uuid import uuid4

from text_unidecode import unidecode
from tortoise import fields, models

# Punctuation characters replaced with spaces during text normalization.
# Mirrors SearchFilter in query_search.py and SqlAlchemyBase:
# string.punctuation minus apostrophe and double-quote.
NORMALIZE_PUNCTUATION = string.punctuation.replace("'", "").replace('"', "")
_NORMALIZE_PUNCTUATION_TABLE = str.maketrans(NORMALIZE_PUNCTUATION, " " * len(NORMALIZE_PUNCTUATION))


class TortoiseBase(models.Model):
    created_at = fields.DatetimeField(auto_now_add=True, null=True, db_index=True)
    update_at = fields.DatetimeField(auto_now=True, null=True)

    class Meta:
        abstract = True

    @property
    def updated_at(self):
        return self.update_at

    @updated_at.setter
    def updated_at(self, value):
        self.update_at = value

    @classmethod
    def normalize(cls, val: str) -> str:
        # Cap the length to 255 to prevent indexes from being too long
        return unidecode(val).translate(_NORMALIZE_PUNCTUATION_TABLE).lower().strip()[:255]

    def update(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class IntIdModel(TortoiseBase):
    id = fields.IntField(pk=True)

    class Meta:
        abstract = True


class UUIDIdModel(TortoiseBase):
    id = fields.UUIDField(pk=True, default=uuid4)

    class Meta:
        abstract = True
