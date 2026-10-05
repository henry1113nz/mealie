"""Tortoise expressions for existential collection filters and correlated ordering."""

from __future__ import annotations

from copy import copy
from typing import Any

from pypika_tortoise import SqlContext, Table
from pypika_tortoise.functions import Lower, Max, Min
from pypika_tortoise.terms import Criterion
from tortoise.expressions import Expression, Q, ResolveContext, ResolveResult
from tortoise.fields.relational import BackwardFKRelation, ManyToManyFieldInstance
from tortoise.query_utils import QueryModifier


class Exists(Criterion):
    """Parameterized SQL EXISTS term supported by both database backends."""

    def __init__(self, query: Any) -> None:
        super().__init__()
        self.query = query

    def get_sql(self, ctx: SqlContext) -> str:
        inner = self.query.get_sql(ctx.copy(subquery=False, with_alias=False))
        sql = f"EXISTS ({inner})"
        return f"({sql})" if ctx.subcriterion else sql


def related_tables(model: Any, table: Any, name: str) -> tuple[Any, Any, Any, Any]:
    field = model._meta.fields_map[name]
    target = field.related_model
    target_table = target._meta.basetable
    if target_table == table:
        target_table = target_table.as_(f"{table.get_table_name()}__{name}")
    if isinstance(field, ManyToManyFieldInstance):
        through = Table(field.through)
        correlation = table[model._meta.db_pk_column] == through[field.backward_key]
        join = through[field.forward_key] == target_table[target._meta.db_pk_column]
        query = model._meta.db.query_class.from_(through).join(target_table).on(join)
    elif isinstance(field, BackwardFKRelation):
        source = field.to_field_instance.source_field or field.to_field_instance.model_field_name
        correlation = table[source] == target_table[field.relation_source_field]
        query = model._meta.db.query_class.from_(target_table)
    else:
        source = model._meta.fields_map[field.source_field]
        source_name = source.source_field or source.model_field_name
        target_name = field.to_field_instance.source_field or field.to_field_instance.model_field_name
        correlation = target_table[target_name] == table[source_name]
        query = model._meta.db.query_class.from_(target_table)
    return target, target_table, correlation, query


class AttributeFilter(Q):
    """Filter a field, wrapping each traversed relation in a correlated EXISTS."""

    def __init__(self, path: str, lookup: str, value: Any, *, string=False) -> None:
        super().__init__()
        self.path = path
        self.lookup = lookup
        self.value = value
        self.string = string

    def __invert__(self) -> AttributeFilter:
        result = copy(self)
        result.negate()
        return result

    def resolve(self, resolve_context: ResolveContext) -> QueryModifier:
        def resolve_path(model: Any, table: Any, parts: list[str]) -> Any:
            if len(parts) > 1:
                target, target_table, correlation, query = related_tables(model, table, parts[0])
                inner = resolve_path(target, target_table, parts[1:])
                return Exists(query.select(1).where(correlation & inner))
            name = parts[0]
            if name in resolve_context.annotations:
                annotation = resolve_context.annotations[name]
                term = annotation.resolve(resolve_context).term if isinstance(annotation, Expression) else annotation
                value = self.value
            else:
                field = model._meta.fields_map[name]
                term = table[field.source_field or name]
                if self.lookup in ("isnull", "like", "not_like"):
                    value = self.value
                elif isinstance(self.value, list):
                    value = [field.to_db_value(item, model) for item in self.value]
                else:
                    value = field.to_db_value(self.value, model)
            if self.string:
                term = Lower(term)
            if self.lookup == "isnull":
                return term.isnull() if value else term.notnull()
            if self.lookup == "in":
                return term.isin(value)
            if self.lookup == "like":
                return term.like(value)
            if self.lookup == "not_like":
                return term.not_like(value)
            if self.lookup == "gt":
                return term > value
            if self.lookup == "gte":
                return term >= value
            if self.lookup == "lt":
                return term < value
            if self.lookup == "lte":
                return term <= value
            if self.lookup == "not":
                return term != value
            return term == value

        criterion = resolve_path(resolve_context.model, resolve_context.table, self.path.split("__"))
        if self._is_negated:
            criterion = criterion.negate()
        return QueryModifier(where_criterion=criterion)


class RelatedOrder(Expression):
    """Reduce a relationship path to one value per root row before pagination."""

    def __init__(self, path: str, *, descending: bool, string: bool) -> None:
        self.path, self.descending, self.string = path, descending, string

    def resolve(self, resolve_context: ResolveContext) -> ResolveResult:
        parts = self.path.split("__")
        model, table = resolve_context.model, resolve_context.table
        joins = []
        conditions = []
        for name in parts[:-1]:
            target, target_table, correlation, query = related_tables(model, table, name)
            # Native relations may have an intermediate many-to-many table.
            for from_table in query._from:
                if from_table not in joins:
                    joins.append(from_table)
            for join in query._joins:
                if join.item not in joins:
                    joins.append(join.item)
                conditions.append(join.criterion)
            conditions.append(correlation)
            model, table = target, target_table
        field = model._meta.fields_map[parts[-1]]
        term: Any = table[field.source_field or parts[-1]]
        if self.string:
            term = Lower(term)
        aggregate = (Max if self.descending else Min)(term)
        query = model._meta.db.query_class.from_(joins[0]).select(aggregate)
        for join in joins[1:]:
            query = query.from_(join)
        for condition in conditions:
            query = query.where(condition)
        return ResolveResult(term=query, output_field=field)


class WordSimilarity(Expression):
    """PostgreSQL trigram similarity with the search supplied as a bound value."""

    def __init__(self, field: str, search: str) -> None:
        self.field = field
        self.search = search

    def resolve(self, resolve_context: ResolveContext) -> ResolveResult:
        from pypika_tortoise.terms import Function
        from tortoise.expressions import F

        resolved = F(self.field).resolve(resolve_context)
        return ResolveResult(term=Function("word_similarity", self.search, resolved.term), joins=resolved.joins)
