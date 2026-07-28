import pytest
import sqlalchemy as sa

from alchemy_filterset.exceptions import LookupNotFoundError
from alchemy_filterset.registry import LookupRegistry, default_registry


class TestLookupRegistry:
    @pytest.mark.parametrize(
        argnames="lookup",
        argvalues=(
            "eq",
            "ne",
            "gt",
            "ge",
            "lt",
            "le",
            "between",
            "in",
            "notin",
            "contains",
            "icontains",
            "not_contains",
            "not_icontains",
            "startswith",
            "istartswith",
            "endswith",
            "iendswith",
            "is_null",
            "not_null",
        ),
    )
    def test_default_registry_has_standard_lookups(self, lookup: str) -> None:
        assert default_registry.has_lookup(lookup)

    def test_custom_lookup_registration_direct(self) -> None:
        registry = LookupRegistry()
        registry.register("custom_lookup", lambda col, val: col == val)

        assert registry.has_lookup("custom_lookup")
        assert registry.get("custom_lookup") is not None

    def test_custom_lookup_registration_decorator(self) -> None:
        registry = LookupRegistry()

        @registry.register("custom_lookup")
        def length_eq(col, val):
            return col == val

        assert registry.has_lookup("custom_lookup")
        assert registry.get("custom_lookup") is not None

    def test_register_multiple_lookups_direct(self) -> None:
        registry = LookupRegistry()
        registry.register(("is_equal", "equals"), lambda col, val: col == val)

        assert registry.has_lookup("is_equal")
        assert registry.has_lookup("equals")

    def test_register_multiple_lookups_decorator(self) -> None:
        registry = LookupRegistry()

        @registry.register(("is_equal", "equals"))
        def length_eq(col, val):
            return col == val

        assert registry.has_lookup("is_equal")
        assert registry.has_lookup("equals")

    @pytest.mark.parametrize(
        argnames="lookup",
        argvalues=(
            " EQ ",
            "iCoNtaIns",
            "  IN  ",
            "  BetWeen  ",
        ),
    )
    def test_registry_case_insensitivity(self, lookup: str) -> None:
        assert default_registry.has_lookup(lookup)
        assert default_registry.get(lookup) is not None

    def test_lookup_not_found_raises_exception(self) -> None:
        with pytest.raises(LookupNotFoundError) as exc_info:
            default_registry.get("invalid_lookup_name")

        assert "operator not found" in str(exc_info.value)

    def test_in_lookup_with_empty_list(self) -> None:
        builder = default_registry.get("in")
        col = sa.column("status")

        expr = builder(col, [])
        compiled = str(expr.compile(compile_kwargs={"literal_binds": True}))
        assert "false" in compiled.casefold() or "0 = 1" in compiled.casefold()

    def test_notin_lookup_with_empty_list(self) -> None:
        builder = default_registry.get("notin")
        col = sa.column("status")

        expr = builder(col, [])
        compiled = str(expr.compile(compile_kwargs={"literal_binds": True}))
        assert "true" in compiled.casefold() or "1 = 1" in compiled.casefold()

    def test_between_lookup_invalid_input(self) -> None:
        builder = default_registry.get("between")
        col = sa.column("price")

        expr = builder(col, 1000)
        compiled = str(expr.compile(compile_kwargs={"literal_binds": True}))
        assert "false" in compiled.casefold() or "0 = 1" in compiled.casefold()

    def test_registered_lookups_property(self) -> None:
        lookups = default_registry.registered_lookups
        assert isinstance(lookups, set)
        assert all(("eq" in lookups, "startswith" in lookups))
