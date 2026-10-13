"""Writes mealie/db/tortoise/models.py from the SQLAlchemy models (stage S1 of REWRITE_PLAN.md).

    uv run python dev/scripts/generate_tortoise_models.py

Keeps table and column names identical, and names relations the way the SQLAlchemy relationships
do, so the Pydantic schemas in mealie/schema read Tortoise objects the same way.
"""

import enum
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.orm import MANYTOONE, ONETOMANY

import mealie.db.models._all_models  # noqa: F401
from mealie.db.models._model_base import SqlAlchemyBase
from mealie.db.models._model_utils.guid import GUID

OUT = Path("mealie/db/tortoise/models.py")
ON_DELETE = {None: "fields.NO_ACTION", "CASCADE": "fields.CASCADE", "SET NULL": "fields.SET_NULL"}
DEFAULTS = {"generate": "uuid.uuid4", "get_utc_now": "utc_now", "get_utc_today": "utc_today"}
DEFAULT_BY_COLUMN = {"webhook_urls.scheduled_time": "utc_time"}


def relationship_names() -> tuple[dict, dict]:
    forward: dict[tuple[str, str], str] = {}
    reverse: dict[tuple[str, str], tuple[str, bool]] = {}
    for mapper in SqlAlchemyBase.registry.mappers:
        for rel in mapper.relationships:
            if rel.secondary is not None:
                continue
            if rel.direction is MANYTOONE and len(rel.local_columns) == 1:
                col = next(iter(rel.local_columns))
                forward.setdefault((col.table.name, col.name), rel.key)
            elif rel.direction is ONETOMANY and len(rel.remote_side) == 1:
                col = next(iter(rel.remote_side))
                reverse.setdefault((col.table.name, col.name), (rel.key, rel.uselist))
    return forward, reverse


def default_arg(col: sa.Column, where: str, notes: list[str]) -> str | None:
    if where in DEFAULT_BY_COLUMN:
        return f"default={DEFAULT_BY_COLUMN[where]}"
    if col.default is None:
        return None
    if col.default.is_callable:
        name = getattr(col.default.arg, "__name__", "")
        if name in DEFAULTS:
            return f"default={DEFAULTS[name]}"
        notes.append(f"{where}: unknown default {name!r}")
        return None
    value = col.default.arg
    return f"default={(value.value if isinstance(value, enum.Enum) else value)!r}"


def scalar(col: sa.Column, is_pk: bool, where: str, notes: list[str]) -> str:
    t = col.type
    args = ["primary_key=True"] if is_pk else []
    if isinstance(t, GUID):
        kind = "GUIDField"
    elif type(t).__name__ == "NaiveDateTime":
        kind = "UTCDatetimeField"
        if col.onupdate is not None:
            args.append("auto_now=True")
    elif isinstance(t, sa.Enum):
        kind, args = "fields.CharField", [*args, f"max_length={t.length or 32}"]
    elif isinstance(t, sa.String):
        if t.length:
            kind, args = "fields.CharField", [*args, f"max_length={t.length}"]
        elif col.index or col.unique:
            # Tortoise cannot index a TextField
            kind, args = "fields.CharField", [*args, "max_length=255"]
            notes.append(f"{where}: unbounded indexed string -> CharField(255)")
        else:
            kind = "fields.TextField"
    elif isinstance(t, sa.Boolean):
        kind = "fields.BooleanField"
    elif isinstance(t, sa.Integer):
        kind = "fields.IntField"
    elif isinstance(t, sa.Float):
        kind = "fields.FloatField"
    elif isinstance(t, sa.Date):
        kind = "fields.DateField"
    elif isinstance(t, sa.Time):
        kind = "fields.TimeField"
    else:
        notes.append(f"{where}: unmapped type {type(t).__name__}")
        kind = "fields.TextField"
    if not is_pk:
        if col.nullable:
            args.append("null=True")
        if col.unique:
            args.append("unique=True")
        if col.index:
            args.append("db_index=True")
        if (d := default_arg(col, where, notes)) and not any(a.startswith("auto_now") for a in args):
            args.append(d)
    return f"{kind}({', '.join(args)})"


def main() -> None:
    md = SqlAlchemyBase.metadata
    mappers = sorted(SqlAlchemyBase.registry.mappers, key=lambda m: m.class_.__tablename__)
    cls_of = {m.class_.__tablename__: m.class_.__name__ for m in mappers}
    forward, reverse = relationship_names()
    notes: list[str] = []
    out: list[str] = []
    done_m2m: set[str] = set()

    for mapper in mappers:
        cls = mapper.class_
        table = md.tables[cls.__tablename__]
        pk = [c.name for c in table.primary_key]
        if len(pk) > 1:
            notes.append(f"{table.name}: composite primary key {pk} -> id (Tortoise has none)")
        taken = {c.name for c in table.columns}
        col_field: dict[str, str] = {}
        body: list[str] = []
        for col in table.columns:
            where = f"{table.name}.{col.name}"
            fks = list(col.foreign_keys)
            if fks and col.name != "id":
                target = cls_of[fks[0].column.table.name]
                name = forward.get((table.name, col.name), "")
                if not name or name in taken:
                    name = col.name[:-3] if col.name.endswith("_id") else f"{col.name}_rel"
                    while name in taken:
                        name += "_rel"
                taken.add(name)
                col_field[col.name] = f"{name}_id"
                related, is_list = reverse.get((table.name, col.name), (f"{table.name}_{name}_set", True))
                kind = "ForeignKey" if is_list else "OneToOne"
                args = [
                    f'"models.{target}"',
                    f'source_field="{col.name}"',
                    f'related_name="{related}"',
                    f"on_delete={ON_DELETE[fks[0].ondelete]}",
                ]
                if col.nullable:
                    args.append("null=True")
                if col.index:
                    args.append("db_index=True")
                body.append(f"    {name}: fields.{kind}Relation[{target}] = fields.{kind}Field({', '.join(args)})")
            else:
                col_field[col.name] = col.name
                body.append(f"    {col.name} = {scalar(col, col.name == 'id', where, notes)}")

        for rel in mapper.relationships:
            sec = rel.secondary
            if sec is None or sec.name in done_m2m or sec.name in cls_of:
                continue
            done_m2m.add(sec.name)
            target = rel.mapper.class_
            back = next(c.name for c in sec.columns for fk in c.foreign_keys if fk.column.table is table)
            fwd = next(
                c.name
                for c in sec.columns
                for fk in c.foreign_keys
                if fk.column.table.name == target.__tablename__ and c.name != back
            )
            body.append(
                f"    {rel.key}: fields.ManyToManyRelation[{target.__name__}] = fields.ManyToManyField("
                f'"models.{target.__name__}", through="{sec.name}", forward_key="{fwd}", backward_key="{back}", '
                f'related_name="{rel.back_populates or sec.name + "_set"}")'
            )

        meta = [f'        table = "{table.name}"']
        uniques = [c for c in table.constraints if isinstance(c, sa.UniqueConstraint) and len(c.columns) > 1]
        if uniques:
            groups = ", ".join("(" + ", ".join(f'"{col_field[c.name]}"' for c in u.columns) + ",)" for u in uniques)
            meta.append(f"        unique_together = ({groups},)")
        out += [f"class {cls.__name__}(Model):", *body, "", "    class Meta:", *meta, "\n"]

    header = [
        '"""Tortoise ORM models, generated by dev/scripts/generate_tortoise_models.py."""',
        "",
        "import uuid",
        "",
        "from tortoise import fields",
        "from tortoise.models import Model",
        "",
        "from .fields import GUIDField, UTCDatetimeField, utc_now, utc_time, utc_today",
        "",
        "",
    ]
    OUT.write_text("\n".join(header + out))
    print(f"wrote {OUT}: {len(mappers)} models, {len(done_m2m)} many-to-many tables")  # noqa: T201
    for note in notes:
        print("note:", note)  # noqa: T201


if __name__ == "__main__":
    main()
