import typing as tp
from dataclasses import dataclass, field

import sqlalchemy as sa

from .exceptions import LookupNotFoundError

type FilterBuilder = tp.Callable[[tp.Any, tp.Any], sa.ColumnElement[bool]]


@dataclass(slots=True)
class LookupRegistry:
    _builders: tp.MutableMapping[str, FilterBuilder] = field(default_factory=dict)

    @tp.overload
    def register(self, lookup: str | tp.Collection[str]) -> tp.Callable[[FilterBuilder], FilterBuilder]: ...

    @tp.overload
    def register(self, lookup: str | tp.Collection[str], builder: FilterBuilder) -> FilterBuilder: ...

    def register(
        self, lookup: str | tp.Collection[str], builder: FilterBuilder | None = None
    ) -> FilterBuilder | tp.Callable[[FilterBuilder], FilterBuilder]:
        def decorator(builder_function: FilterBuilder) -> FilterBuilder:
            lookups = (lookup,) if isinstance(lookup, str) else lookup

            for lookup_ in lookups:
                lookup_ = lookup_.strip().casefold()
                self._builders[lookup_] = builder_function

            return builder_function

        return decorator if builder is None else decorator(builder)

    def get(self, lookup: str) -> FilterBuilder:
        lookup = lookup.strip().casefold()
        if lookup not in self._builders:
            raise LookupNotFoundError(lookup, self._builders.keys())
        return self._builders[lookup]

    def has_lookup(self, lookup: str) -> bool:
        return lookup.strip().casefold() in self._builders

    @property
    def registered_lookups(self) -> set[str]:
        return set(self._builders.keys())


def register_default_lookups(registry: LookupRegistry) -> None:
    # Register comparison lookups
    registry.register(lookup="eq", builder=lambda col, val: col == val)
    registry.register(lookup="ne", builder=lambda col, val: col != val)
    registry.register(lookup="gt", builder=lambda col, val: col > val)
    registry.register(lookup="ge", builder=lambda col, val: col >= val)
    registry.register(lookup="lt", builder=lambda col, val: col < val)
    registry.register(lookup="le", builder=lambda col, val: col <= val)
    registry.register(
        lookup="between",
        builder=lambda col, val: (
            col.between(val[0], val[1]) if isinstance(val, (list, tuple)) and len(val) == 2 else sa.false()
        ),
    )

    # Register collection lookups
    registry.register(
        lookup="in",
        builder=lambda col, val: col.in_(val if isinstance(val, (list, tuple, set)) else [val]) if val else sa.false(),
    )
    registry.register(
        lookup="notin",
        builder=lambda col, val: (
            col.not_in(val if isinstance(val, (list, tuple, set)) else [val]) if val else sa.true()
        ),
    )

    # Register text search lookups
    registry.register(lookup="contains", builder=lambda col, val: sa.cast(col, sa.String).like(f"%{val}%"))
    registry.register(lookup="icontains", builder=lambda col, val: sa.cast(col, sa.String).ilike(f"%{val}%"))
    registry.register(lookup="not_contains", builder=lambda col, val: sa.cast(col, sa.String).not_like(f"%{val}%"))
    registry.register(lookup="not_icontains", builder=lambda col, val: sa.cast(col, sa.String).not_ilike(f"%{val}%"))
    registry.register(lookup="startswith", builder=lambda col, val: sa.cast(col, sa.String).like(f"{val}%"))
    registry.register(lookup="istartswith", builder=lambda col, val: sa.cast(col, sa.String).ilike(f"{val}%"))
    registry.register(lookup="endswith", builder=lambda col, val: sa.cast(col, sa.String).like(f"%{val}"))
    registry.register(lookup="iendswith", builder=lambda col, val: sa.cast(col, sa.String).ilike(f"%{val}"))

    # Register null lookups
    registry.register(lookup="is_null", builder=lambda col, val: col.is_(None) if val else col.is_not(None))
    registry.register(lookup="not_null", builder=lambda col, val: col.is_not(None) if val else col.is_(None))


default_registry = LookupRegistry()
register_default_lookups(default_registry)
