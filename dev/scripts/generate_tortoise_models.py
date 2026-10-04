"""Generates mealie/db/tortoise/models.py from the SQLAlchemy model metadata.

Used once during the migration so that the Tortoise models describe exactly the same tables,
columns, keys and constraints as the existing schema. Run from the repository root:

    uv run python dev/scripts/generate_tortoise_models.py
"""

import enum
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.ext.associationproxy import AssociationProxy
from sqlalchemy.orm import MANYTOONE, ONETOMANY

import mealie.db.models._all_models  # noqa: F401  (registers every mapper)
from mealie.db.models._model_base import SqlAlchemyBase
from mealie.db.models._model_utils.guid import GUID

OUT = Path("mealie/db/tortoise/models.py")

ON_DELETE = {None: "fields.NO_ACTION", "CASCADE": "fields.CASCADE", "SET NULL": "fields.SET_NULL"}
DEFAULT_CALLABLES = {"generate": "uuid.uuid4", "get_utc_now": "get_utc_now", "get_utc_today": "get_utc_today"}
# lambdas have no useful name, so they are matched by column
DEFAULT_BY_COLUMN = {"webhook_urls.scheduled_time": "get_utc_time"}


def fk_field_name(column: str, taken: set[str]) -> str:
    name = column[:-3] if column.endswith("_id") else f"{column}_rel"
    while name in taken:
        name += "_rel"
    return name


def default_kwarg(col: sa.Column, warnings: list[str], where: str) -> str | None:
    if col.default is None:
        return None
    if where in DEFAULT_BY_COLUMN:
        return f"default={DEFAULT_BY_COLUMN[where]}"
    if col.default.is_callable:
        fn_name = getattr(col.default.arg, "__name__", "")
        if fn_name in DEFAULT_CALLABLES:
            return f"default={DEFAULT_CALLABLES[fn_name]}"
        warnings.append(f"{where}: unknown default callable {fn_name!r}")
        return None
    if col.default.is_scalar:
        arg = col.default.arg
        if isinstance(arg, enum.Enum):
            arg = arg.value
        return f"default={arg!r}"
    warnings.append(f"{where}: unsupported default {col.default!r}")
    return None


def scalar_field(col: sa.Column, is_pk: bool, warnings: list[str], where: str) -> str:
    t = col.type
    args: list[str] = []
    if is_pk:
        args.append("primary_key=True")
    if isinstance(t, GUID):
        kind = "GUIDField"
    elif type(t).__name__ == "NaiveDateTime":
        kind = "NaiveUTCDatetimeField"
        if col.onupdate is not None:
            args.append("auto_now=True")
    elif isinstance(t, sa.Enum):
        kind = "fields.CharField"
        args.append(f"max_length={t.length or 32}")
    elif isinstance(t, sa.String):
        if t.length:
            kind = "fields.CharField"
            args.append(f"max_length={t.length}")
        elif col.index or col.unique:
            # Tortoise cannot index a TextField; 255 matches the cap Mealie already puts on
            # normalized search text, but longer values are now rejected on save
            kind = "fields.CharField"
            args.append("max_length=255")
            warnings.append(f"{where}: unbounded indexed string mapped to CharField(255)")
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
        warnings.append(f"{where}: unmapped type {type(t).__name__}")
        kind = "fields.TextField"

    if not is_pk:
        if col.nullable:
            args.append("null=True")
        if col.unique:
            args.append("unique=True")
        if col.index:
            args.append("db_index=True")
        if (d := default_kwarg(col, warnings, where)) and not any(a.startswith("auto_now") for a in args):
            args.append(d)
    return f"{kind}({', '.join(args)})"


def relationship_names() -> tuple[dict[tuple[str, str], str], dict[tuple[str, str], tuple[str, bool]]]:
    """Names the SQLAlchemy models already use for each foreign key, in both directions.

    Reusing them keeps attribute names the same as in mealie/schema, so the Pydantic schemas
    can read nested data from Tortoise objects the way they did from SQLAlchemy ones.
    """
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


def main() -> None:
    metadata = SqlAlchemyBase.metadata
    forward_names, reverse_names = relationship_names()
    mappers = sorted(SqlAlchemyBase.registry.mappers, key=lambda m: m.class_.__tablename__)
    class_for_table = {m.class_.__tablename__: m.class_.__name__ for m in mappers}
    warnings: list[str] = []
    lines: list[str] = []
    cascade_delete: dict[str, list[str]] = {}
    nullify_on_delete: dict[str, list[str]] = {}
    filterable: dict[str, list[str]] = {}
    proxies: dict[str, dict[str, str]] = {}
    m2m_done: set[str] = set()

    for mapper in mappers:
        cls = mapper.class_
        table: sa.Table = metadata.tables[cls.__tablename__]
        pk_cols = [c.name for c in table.primary_key]
        if "id" not in pk_cols:
            warnings.append(f"{table.name}: primary key without id: {pk_cols}")
        if len(pk_cols) > 1:
            # Tortoise has no composite primary keys; id is a uuid4 and unique on its own
            warnings.append(f"{table.name}: composite primary key {pk_cols} reduced to id")

        body: list[str] = []
        taken = {c.name for c in table.columns}
        col_to_field: dict[str, str] = {}
        for col in table.columns:
            where = f"{table.name}.{col.name}"
            fks = list(col.foreign_keys)
            if fks and col.name != "id":
                target_table = fks[0].column.table.name
                name = forward_names.get((table.name, col.name)) or ""
                if not name or name in taken:
                    name = fk_field_name(col.name, taken)
                taken.add(name)
                col_to_field[col.name] = f"{name}_id"
                reverse_name, reverse_is_list = reverse_names.get(
                    (table.name, col.name), (f"{table.name}_{name}_rev", True)
                )
                field_kind = "ForeignKeyField" if reverse_is_list else "OneToOneField"
                relation_kind = "ForeignKeyRelation" if reverse_is_list else "OneToOneRelation"
                args = [
                    f'"models.{class_for_table[target_table]}"',
                    f'source_field="{col.name}"',
                    f'related_name="{reverse_name}"',
                    f"on_delete={ON_DELETE[fks[0].ondelete]}",
                ]
                if col.nullable:
                    args.append("null=True")
                if col.index:
                    args.append("db_index=True")
                body.append(
                    f"    {name}: fields.{relation_kind}[{class_for_table[target_table]}] = "
                    f"fields.{field_kind}({', '.join(args)})"
                )
            else:
                col_to_field[col.name] = col.name
                body.append(f"    {col.name} = {scalar_field(col, col.name == 'id', warnings, where)}")

        for rel in mapper.relationships:
            if rel.secondary is None and rel.direction is ONETOMANY and not rel.viewonly:
                # SQLAlchemy applies these in Python when the parent is deleted
                if "delete" in rel.cascade:
                    cascade_delete.setdefault(cls.__name__, []).append(rel.key)
                elif not rel.passive_deletes:
                    nullify_on_delete.setdefault(cls.__name__, []).append(rel.key)
            sec = rel.secondary
            if sec is None or sec.name in m2m_done:
                continue
            if sec.name in class_for_table:
                # the link table is a model with its own columns (e.g. rating, last_made); Tortoise
                # many-to-many tables can only hold the two keys, so use the model directly
                continue
            m2m_done.add(sec.name)
            target_cls = rel.mapper.class_
            back_key = next(c.name for c in sec.columns for fk in c.foreign_keys if fk.column.table is table)
            fwd_key = next(
                c.name
                for c in sec.columns
                for fk in c.foreign_keys
                if fk.column.table.name == target_cls.__tablename__ and c.name != back_key
            )
            related = rel.back_populates or f"{sec.name}_rev"
            body.append(
                f"    {rel.key}: fields.ManyToManyRelation[{target_cls.__name__}] = fields.ManyToManyField("
                f'"models.{target_cls.__name__}", through="{sec.name}", forward_key="{fwd_key}", '
                f'backward_key="{back_key}", related_name="{related}")'
            )

        meta = [f'        table = "{table.name}"']
        uniques = [c for c in table.constraints if isinstance(c, sa.UniqueConstraint) and len(c.columns) > 1]
        if uniques:
            groups = ", ".join("(" + ", ".join(f'"{col_to_field[c.name]}"' for c in u.columns) + ",)" for u in uniques)
            meta.append(f"        unique_together = ({groups},)")
        filterable[cls.__name__] = sorted(
            col_to_field[c.name] for c in table.columns if c.info.get("filterable") and c.name in col_to_field
        )
        for attr, value in vars(cls).items():
            if isinstance(value, AssociationProxy):
                # e.g. RecipeModel.household_id is really user.household_id
                proxies.setdefault(cls.__name__, {})[attr] = f"{value.target_collection}__{value.value_attr}"
        lines.append(f"class {cls.__name__}(Model):")
        lines.extend(body)
        lines.append("")
        lines.append("    class Meta:")
        lines.extend(meta)
        lines.append("\n")

    header = [
        '"""Tortoise ORM models for Mealie.',
        "",
        "Generated by dev/scripts/generate_tortoise_models.py from the SQLAlchemy models, then kept by hand.",
        '"""',
        "",
        "import uuid",
        "",
        "from tortoise import fields",
        "from tortoise.models import Model",
        "",
        "from .fields import GUIDField, NaiveUTCDatetimeField, get_utc_now, get_utc_time, get_utc_today",
        "",
        "",
    ]
    footer = [
        "# What SQLAlchemy did through relationship settings when a row was deleted: delete these",
        "# children, or clear their foreign key. Tortoise does neither, so the repositories apply it.",
        f"CASCADE_DELETE: dict[str, list[str]] = {dict(sorted(cascade_delete.items()))!r}",
        f"NULLIFY_ON_DELETE: dict[str, list[str]] = {dict(sorted(nullify_on_delete.items()))!r}",
        "# Columns that may be used in query filters (FilterableColumn in the SQLAlchemy models).",
        f"FILTERABLE: dict[str, list[str]] = {dict(sorted(filterable.items()))!r}",
        "# SQLAlchemy association proxies. Several group_id / household_id attributes are proxies, so",
        "# scoping a query by group or household has to follow these paths.",
        f"PROXIES: dict[str, dict[str, str]] = {dict(sorted(proxies.items()))!r}",
        "",
    ]
    OUT.write_text("\n".join(header + lines + footer))
    print(f"wrote {OUT}: {len(mappers)} models, {len(m2m_done)} many-to-many tables")  # noqa: T201
    for w in warnings:
        print("warning:", w)  # noqa: T201


if __name__ == "__main__":
    main()
