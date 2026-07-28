import typing as tp


class LookupNotFoundError(KeyError):
    def __init__(self, lookup: str, available_lookups: tp.Collection[str]) -> None:
        sorted_lookups = ", ".join(sorted(available_lookups))
        super().__init__(
            f"'{lookup}' operator not found in lookup registry.",
            f"Allowed operators are: [{sorted_lookups}]",
        )


class RelationshipResolverError(Exception):
    pass


class AttributeNotFoundError(RelationshipResolverError):
    def __init__(self, model: type, attribute_name: str) -> None:
        super().__init__(f"The '{attribute_name}' attribute was not found on the '{model.__name__}' model.")
