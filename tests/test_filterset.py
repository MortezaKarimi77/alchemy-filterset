import pytest
import sqlalchemy as sa
from advanced_alchemy import filters
from sqlalchemy.dialects import postgresql

from alchemy_filterset.filterset import SQLAlchemyFilterSet
from tests.conftest import City, Province


class CityFilterSet(SQLAlchemyFilterSet):
    model_cls = City
    search_fields = ("name", "province__name")

    name__icontains: str | None = None
    population__gt: int | None = None
    province__country__code: str | None = None
    tags__name__icontains: str | None = None

    not__population__gt: int | None = None
    not__province__country__code: str | None = None

    has_metro: bool | None = None
    not__has_metro: bool | None = None

    def filter_has_metro(self, value: bool):
        if value:
            return City.population > 1000000
        return City.population <= 1000000


class NoPaginationCityFilterSet(SQLAlchemyFilterSet):
    model_cls = City
    enable_pagination = False


class BadSearchFilterSet(SQLAlchemyFilterSet):
    model_cls = City
    search_fields = ("name", "does_not_exist")


class ConditionalCustomFilterSet(SQLAlchemyFilterSet):
    model_cls = City
    only_large: bool | None = None

    def filter_only_large(self, value: bool):
        if not value:
            return None
        return City.population > 1000000


class NullsLastCityFilterSet(SQLAlchemyFilterSet):
    model_cls = City
    default_nulls = "last"


class TestFilterSet:
    def test_pagination_defaults(self) -> None:
        filterset = CityFilterSet()
        stmt_filters = filterset.to_statement_filters()
        pagination = next((filter for filter in stmt_filters if isinstance(filter, filters.LimitOffset)), None)

        assert pagination is not None
        assert all((pagination.limit == filterset.default_page_size, pagination.offset == 0))

    def test_pagination_disabled(self) -> None:
        filterset = NoPaginationCityFilterSet(page=2, page_size=50)
        stmt_filters = filterset.to_statement_filters()
        pagination = next((filter for filter in stmt_filters if isinstance(filter, filters.LimitOffset)), None)

        assert all((pagination is None, filterset.page is None, filterset.page_size is None))

    def test_pagination_max_size_clamping(self) -> None:
        filterset = CityFilterSet(page_size=500)
        assert filterset.page_size == filterset.max_page_size

    def test_global_search(self) -> None:
        filterset = CityFilterSet(search="Tehran")
        search_expr = filterset._build_search_filter()

        assert search_expr is not None
        compiled = str(search_expr.compile(compile_kwargs={"literal_binds": True}))

        assert all(
            (
                " OR " in compiled,
                "lower(CAST(city.name AS VARCHAR)) LIKE lower('%Tehran%')" in compiled,
                "lower(CAST(province.name AS VARCHAR)) LIKE lower('%Tehran%')" in compiled,
            )
        )

    def test_search_ignores_invalid_search_field(self) -> None:
        filterset = BadSearchFilterSet(search="Tehran")
        search_expr = filterset._build_search_filter()

        assert search_expr is not None
        compiled = str(search_expr.compile(compile_kwargs={"literal_binds": True}))
        assert "lower(CAST(city.name AS VARCHAR)) LIKE lower('%Tehran%')" in compiled
        assert " OR " not in compiled

    def test_nested_relationship_filtering(self) -> None:
        filterset = CityFilterSet(province__country__code="IR")
        exprs = filterset._build_field_filters()

        assert len(exprs) == 1
        compiled = str(exprs[0].compile(compile_kwargs={"literal_binds": True}))
        assert all(("EXISTS" in compiled, "IR" in compiled))

    def test_filtering_through_collection_relationship(self) -> None:
        filterset = CityFilterSet(tags__name__icontains="capital")
        exprs = filterset._build_field_filters()

        assert len(exprs) == 1
        compiled = str(exprs[0].compile(compile_kwargs={"literal_binds": True}))
        assert "EXISTS" in compiled
        assert "capital" in compiled

    def test_custom_filter_method(self) -> None:
        filterset = CityFilterSet(has_metro=True)
        exprs = filterset._build_field_filters()

        assert len(exprs) == 1
        compiled = str(exprs[0].compile(compile_kwargs={"literal_binds": True}))
        assert "population > 1000000" in compiled

    def test_custom_filter_method_returning_none_adds_no_condition(self) -> None:
        filterset = ConditionalCustomFilterSet(only_large=False)
        assert filterset._build_field_filters() == []

    def test_ordering_parsing(self) -> None:
        filterset = CityFilterSet(ordering="-population,province__name")
        ordering_filters = filterset._build_ordering_filters()

        assert ordering_filters is not None

        assert all(
            (
                len(ordering_filters) == 2,
                ordering_filters[0].field_name is City.population,
                ordering_filters[0].sort_order == "desc",
                ordering_filters[1].field_name is Province.name,
                ordering_filters[1].sort_order == "asc",
            )
        )

    def test_ordering_ignores_invalid_field(self) -> None:
        filterset = CityFilterSet(ordering="name,invalid_field,-population")
        stmt_filters = filterset.to_statement_filters()
        ordering_filters = [field for field in stmt_filters if isinstance(field, filters.OrderBy)]

        assert len(ordering_filters) == 2
        assert ordering_filters[0].field_name is City.name
        assert ordering_filters[1].field_name is City.population

    @pytest.mark.parametrize(
        argnames=("ordering", "sort_order", "nulls"),
        argvalues=(
            ("population", "asc", None),
            ("-population", "desc", None),
            ("population:nulls_first", "asc", "first"),
            ("population:nulls_last", "asc", "last"),
            ("-population:nulls_first", "desc", "first"),
            ("-population:nulls_last", "desc", "last"),
            ("-population:NULLS_LAST", "desc", "last"),
            (" -population : nulls_last ", "desc", "last"),
        ),
    )
    def test_ordering_nulls_modifier(self, ordering: str, sort_order: str, nulls: str | None) -> None:
        ordering_filters = CityFilterSet(ordering=ordering)._build_ordering_filters()

        assert ordering_filters is not None
        assert all(
            (
                len(ordering_filters) == 1,
                ordering_filters[0].field_name is City.population,
                ordering_filters[0].sort_order == sort_order,
                ordering_filters[0].nulls == nulls,
            )
        )

    @pytest.mark.parametrize(
        argnames="ordering",
        argvalues=(
            "population:nulls_lst",
            "population:",
            "population:last",
            "population:nulls_last:extra",
        ),
    )
    def test_ordering_ignores_invalid_nulls_modifier(self, ordering: str) -> None:
        assert CityFilterSet(ordering=ordering)._build_ordering_filters() is None

    def test_ordering_invalid_nulls_modifier_keeps_other_fields(self) -> None:
        filterset = CityFilterSet(ordering="name,population:bogus,-id:nulls_last")
        ordering_filters = filterset._build_ordering_filters()

        assert ordering_filters is not None
        assert all(
            (
                len(ordering_filters) == 2,
                ordering_filters[0].field_name is City.name,
                ordering_filters[0].nulls is None,
                ordering_filters[1].field_name is City.id,
                ordering_filters[1].sort_order == "desc",
                ordering_filters[1].nulls == "last",
            )
        )

    def test_default_nulls_applies_without_modifier(self) -> None:
        filterset = NullsLastCityFilterSet(ordering="-population,name")
        ordering_filters = filterset._build_ordering_filters()

        assert ordering_filters is not None
        assert all(
            (
                len(ordering_filters) == 2,
                ordering_filters[0].nulls == "last",
                ordering_filters[1].nulls == "last",
            )
        )

    def test_explicit_nulls_modifier_overrides_default_nulls(self) -> None:
        filterset = NullsLastCityFilterSet(ordering="-population:nulls_first,name")
        ordering_filters = filterset._build_ordering_filters()

        assert ordering_filters is not None
        assert all(
            (
                len(ordering_filters) == 2,
                ordering_filters[0].nulls == "first",
                ordering_filters[1].nulls == "last",
            )
        )

    def test_invalid_nulls_modifier_does_not_fall_back_to_default_nulls(self) -> None:
        filterset = NullsLastCityFilterSet(ordering="-population:bogus")
        assert filterset._build_ordering_filters() is None

    def test_nulls_placement_reaches_postgresql_sql(self) -> None:
        ordering_filters = CityFilterSet(ordering="-population:nulls_last")._build_ordering_filters()
        assert ordering_filters is not None

        statement = ordering_filters[0].append_to_statement(sa.select(City), City)
        compiled = str(statement.compile(dialect=postgresql.dialect()))

        assert "DESC NULLS LAST" in compiled

    def test_empty_search_and_ordering(self) -> None:
        filterset = CityFilterSet(search="   ", ordering="  ")
        assert all((filterset._build_search_filter() is None, filterset._build_ordering_filters() is None))

    def test_to_statement_filters_assembly(self) -> None:
        filterset = CityFilterSet(page=2, page_size=20, ordering="-population", search="Tehran", population__gt=1000)
        stmt_filters = filterset.to_statement_filters()

        assert len(stmt_filters) >= 3

        pagination = next((filter for filter in stmt_filters if isinstance(filter, filters.LimitOffset)), None)
        assert pagination is not None
        assert all((pagination.limit == 20, pagination.offset == 20))

        ordering = next((filter for filter in stmt_filters if isinstance(filter, filters.OrderBy)), None)
        assert ordering is not None
        assert ordering.field_name is City.population

        sql_exprs = [filter for filter in stmt_filters if hasattr(filter, "compile")]
        assert len(sql_exprs) > 0

    def test_to_statement_filters_without_model_cls_raises(self) -> None:
        class BrokenFilterSet(SQLAlchemyFilterSet):
            pass

        with pytest.raises(ValueError, match="model_cls"):
            BrokenFilterSet().to_statement_filters()

    def test_negation_simple_field(self) -> None:
        filterset = CityFilterSet(not__population__gt=1000000)
        exprs = filterset._build_field_filters()

        assert len(exprs) == 1
        compiled = str(exprs[0].compile(compile_kwargs={"literal_binds": True}))
        assert "population <= 1000000" in compiled or "NOT (city.population > 1000000)" in compiled

    def test_negation_nested_relationship(self) -> None:
        filterset = CityFilterSet(not__province__country__code="IR")
        exprs = filterset._build_field_filters()

        assert len(exprs) == 1
        compiled = str(exprs[0].compile(compile_kwargs={"literal_binds": True}))

        assert "NOT EXISTS" in compiled or "NOT (EXISTS" in compiled
        assert "IR" in compiled

    def test_negation_custom_method_true(self) -> None:
        filterset = CityFilterSet(not__has_metro=True)
        exprs = filterset._build_field_filters()
        compiled = str(exprs[0].compile(compile_kwargs={"literal_binds": True}))

        assert len(exprs) == 1
        assert "population <= 1000000" in compiled or "NOT (city.population > 1000000)" in compiled

    def test_negation_custom_method_false(self) -> None:
        filterset = CityFilterSet(not__has_metro=False)
        exprs = filterset._build_field_filters()
        compiled = str(exprs[0].compile(compile_kwargs={"literal_binds": True}))

        assert len(exprs) == 1
        assert "population > 1000000" in compiled or "NOT (city.population <= 1000000)" in compiled
