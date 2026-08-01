import typing as tp

import pydantic as pyd
from advanced_alchemy import filters
from sqlalchemy import ColumnElement, or_
from sqlalchemy.orm import DeclarativeBase

from . import exceptions
from .registry import LookupRegistry, default_registry
from .resolver import RelationshipResolver


class SQLAlchemyFilterSet(pyd.BaseModel):
    model_config = pyd.ConfigDict(
        extra="ignore",
        from_attributes=True,
        str_strip_whitespace=True,
        use_enum_values=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )

    model_cls: tp.ClassVar[type[DeclarativeBase]]
    registry: tp.ClassVar[LookupRegistry] = default_registry
    search_fields: tp.ClassVar[tp.Collection[str]] = ()

    enable_pagination: tp.ClassVar[bool] = True
    default_page_size: tp.ClassVar[int] = 30
    max_page_size: tp.ClassVar[int] = 100

    page: int | None = pyd.Field(default=None, ge=1)
    page_size: int | None = pyd.Field(default=None, ge=1)

    ordering: str | None = None
    search: str | None = None

    @pyd.model_validator(mode="after")
    def validate_pagination_params(self) -> tp.Self:
        if not self.enable_pagination:
            if self.page is not None:
                self.page = None
            if self.page_size is not None:
                self.page_size = None
        else:
            if self.page is None:
                self.page = 1
            if self.page_size is None:
                self.page_size = self.default_page_size
            if self.page_size > self.max_page_size:  # noqa: PLR1730
                self.page_size = self.max_page_size

        return self

    def to_statement_filters(self) -> tp.Sequence[filters.StatementFilter | ColumnElement[bool]]:
        if not hasattr(self, "model_cls"):
            raise ValueError(f"The {self.__class__.__name__} class must define the 'model_cls' attribute.")

        query_filters = []

        if self.enable_pagination and self.page and self.page_size:
            query_filters.append(filters.LimitOffset(limit=self.page_size, offset=(self.page - 1) * self.page_size))

        if ordering_expr := self._build_ordering_filters():
            query_filters.extend(ordering_expr)

        if (search_expr := self._build_search_filter()) is not None:
            query_filters.append(search_expr)

        query_filters.extend(self._build_field_filters())
        return query_filters

    def _build_ordering_filters(self) -> tp.Sequence[filters.OrderBy] | None:
        if self.ordering is None or not self.ordering.strip():
            return None

        ordering_filters = []
        fields = [field.strip() for field in self.ordering.split(",") if field.strip()]

        for field in fields:
            sort_order = "desc" if field.startswith("-") else "asc"
            clean_path = field.strip("+-")

            try:
                resolved = RelationshipResolver.resolve(self.model_cls, clean_path)
            except exceptions.RelationshipResolverError:
                continue

            field_to_order = tp.cast(tp.Any, resolved.target_attribute)
            ordering_filters.append(filters.OrderBy(field_name=field_to_order, sort_order=sort_order))

        return ordering_filters if ordering_filters else None

    def _build_search_filter(self) -> ColumnElement[bool] | None:
        if not self.search or not self.search_fields:
            return None

        conditions = []
        for path in self.search_fields:
            try:
                cond = self._build_single_condition(path, lookup="icontains", value=self.search)
                conditions.append(cond)
            except (
                exceptions.RelationshipResolverError,
                exceptions.LookupNotFoundError,
                exceptions.AttributeNotFoundError,
            ):
                continue

        return or_(*conditions) if conditions else None

    def _build_field_filters(self) -> tp.Sequence[ColumnElement[bool]]:
        conditions = []
        reserved_keys = {"page", "page_size", "ordering", "search"}

        query_params: tp.Mapping[str, tp.Any] = self.model_dump(
            exclude_unset=True, exclude_none=True, exclude=reserved_keys
        )

        for key, value in query_params.items():
            is_negated = False
            if key.startswith("not__"):
                is_negated = True
                key = key[len("not__") :]

            if custom_filter_method := getattr(self, f"filter_{key}", None):
                if (cond := custom_filter_method(value)) is not None:
                    conditions.append(~cond if is_negated else cond)
                continue

            parts = key.split("__")
            lookup = "eq"

            if len(parts) > 1 and self.registry.has_lookup(parts[-1]):
                lookup = parts.pop()

            clean_path = "__".join(parts)

            cond = self._build_single_condition(clean_path, lookup, value)
            conditions.append(~cond if is_negated else cond)

        return conditions

    def _build_single_condition(self, path: str, lookup: str, value: tp.Any) -> ColumnElement[bool]:
        resolved = RelationshipResolver.resolve(self.model_cls, path)
        builder_function = self.registry.get(lookup)
        condition = builder_function(resolved.target_attribute, value)

        for relation, uselist in reversed(resolved.relationship_chain):
            if uselist:
                condition = relation.any(condition)
            else:
                condition = relation.has(condition)

        return condition
