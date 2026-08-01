from advanced_alchemy import filters

from alchemy_filterset.filterset import SQLAlchemyFilterSet
from tests.conftest import City, Province


class CityFilterSet(SQLAlchemyFilterSet):
    model_cls = City
    search_fields = ("name", "province__name")

    name__icontains: str | None = None
    population__gt: int | None = None
    province__country__code: str | None = None

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

        assert all((
            " OR " in compiled,
            "lower(CAST(city.name AS VARCHAR)) LIKE lower('%Tehran%')" in compiled,
            "lower(CAST(province.name AS VARCHAR)) LIKE lower('%Tehran%')" in compiled,
        ))

    def test_nested_relationship_filtering(self) -> None:
        filterset = CityFilterSet(province__country__code="IR")
        exprs = filterset._build_field_filters()

        assert len(exprs) == 1
        compiled = str(exprs[0].compile(compile_kwargs={"literal_binds": True}))
        assert all(("EXISTS" in compiled, "IR" in compiled))

    def test_custom_filter_method(self) -> None:
        filterset = CityFilterSet(has_metro=True)
        exprs = filterset._build_field_filters()

        assert len(exprs) == 1
        compiled = str(exprs[0].compile(compile_kwargs={"literal_binds": True}))
        assert "population > 1000000" in compiled

    def test_ordering_parsing(self) -> None:
        filterset = CityFilterSet(ordering="-population,province__name")
        ordering_filters = filterset._build_ordering_filters()

        assert ordering_filters is not None

        assert all((
            len(ordering_filters) == 2,
            ordering_filters[0].field_name is City.population,
            ordering_filters[0].sort_order == "desc",
            ordering_filters[1].field_name is Province.name,
            ordering_filters[1].sort_order == "asc",
        ))

    def test_ordering_ignores_invalid_field(self) -> None:
        filterset = CityFilterSet(ordering="name,invalid_field,-population")
        stmt_filters = filterset.to_statement_filters()
        ordering_filters = [field for field in stmt_filters if isinstance(field, filters.OrderBy)]

        assert len(ordering_filters) == 2
        assert ordering_filters[0].field_name is City.name
        assert ordering_filters[1].field_name is City.population

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
