import typing as tp

import pytest
import sqlalchemy.orm as so

from alchemy_filterset.exceptions import AttributeNotFoundError, RelationshipResolverError
from alchemy_filterset.resolver import RelationshipResolver
from tests.conftest import City, CityTag, Country, Province, Tag


class TestRelationshipResolver:
    @pytest.mark.parametrize(
        argnames=("model", "target_attribute", "attribute_name"),
        argvalues=(
            (Country, Country.name, "name"),
            (Province, Province.country_id, "country_id"),
            (City, City.population, "population"),
        ),
    )
    def test_resolve_simple_attribute(
        self, model: type[so.DeclarativeBase], target_attribute: so.InstrumentedAttribute[tp.Any], attribute_name: str
    ) -> None:
        resolved = RelationshipResolver.resolve(model, attribute_name)
        assert resolved.is_nested is False
        assert resolved.target_attribute is target_attribute
        assert resolved.attribute_name == attribute_name

    @pytest.mark.parametrize(
        argnames=("model", "target_attribute", "path", "attribute_name", "relationship_length"),
        argvalues=(
            (Country, City.population, "provinces__cities__population", "population", 2),
            (Province, Country.code, "country__code", "code", 1),
            (Province, City.name, "cities__name", "name", 1),
            (City, Country.name, "province__country__name", "name", 2),
        ),
    )
    def test_resolve_nested_relationship(
        self,
        model: type[so.DeclarativeBase],
        target_attribute: so.InstrumentedAttribute[tp.Any],
        path: str,
        attribute_name: str,
        relationship_length: int,
    ) -> None:
        resolved = RelationshipResolver.resolve(model, path)
        assert resolved.is_nested is True
        assert resolved.target_attribute is target_attribute
        assert resolved.attribute_name == attribute_name
        assert len(resolved.relationship_chain) == relationship_length

    @pytest.mark.parametrize(
        argnames=("model", "association_proxy", "target_collection", "target_attribute"),
        argvalues=(
            (City, "tags", "city_tags", "tag"),
            (Tag, "cities", "city_tags", "city"),
        ),
    )
    def test_resolve_association_proxy_to_relationship(
        self, model: type[so.DeclarativeBase], association_proxy: str, target_collection: str, target_attribute: str
    ) -> None:
        resolved = RelationshipResolver.resolve(model, association_proxy)

        assert resolved.is_nested is True
        assert resolved.attribute_name == target_attribute
        assert len(resolved.relationship_chain) == 2

        # City -> CityTag
        assert resolved.relationship_chain[0][0].key == target_collection
        assert resolved.relationship_chain[0][1] is True  # uselist=True

        # CityTag -> Tag
        assert resolved.relationship_chain[1][0].key == target_attribute
        assert resolved.relationship_chain[1][1] is False  # uselist=False

    @pytest.mark.parametrize(
        argnames=("model", "target_attribute", "path", "attribute_name", "relationship_length"),
        argvalues=(
            (City, Tag.name, "tags__name", "name", 2),
            (Tag, City.name, "cities__name", "name", 2),
        ),
    )
    def test_resolve_association_proxy_with_field_continuation(
        self,
        model: type[so.DeclarativeBase],
        path: str,
        attribute_name: str,
        target_attribute: so.InstrumentedAttribute[tp.Any],
        relationship_length: int,
    ) -> None:
        resolved = RelationshipResolver.resolve(model, path)
        assert resolved.is_nested is True
        assert resolved.target_attribute is target_attribute
        assert resolved.attribute_name == attribute_name
        assert len(resolved.relationship_chain) == relationship_length

    @pytest.mark.parametrize(
        argnames=("model", "target_attribute", "path", "target_collection"),
        argvalues=(
            (City, CityTag.tag_id, "tag_ids", "city_tags"),
            (Tag, CityTag.city_id, "city_ids", "city_tags"),
        ),
    )
    def test_resolve_association_proxy_to_scalar_column(
        self,
        model: type[so.DeclarativeBase],
        target_attribute: so.InstrumentedAttribute[tp.Any],
        path: str,
        target_collection: str,
    ) -> None:
        resolved = RelationshipResolver.resolve(model, path)

        assert resolved.is_nested is True
        assert resolved.target_attribute is target_attribute
        assert len(resolved.relationship_chain) == 1
        assert resolved.relationship_chain[0][0].key == target_collection
        assert resolved.relationship_chain[0][1] is True  # uselist=True

    def test_resolve_invalid_field_after_association_proxy(self) -> None:
        with pytest.raises(AttributeNotFoundError):
            RelationshipResolver.resolve(City, "tags__non_existent_field")

    @pytest.mark.parametrize(
        argnames=("model", "target_attribute", "path", "attribute_name", "relationship_length"),
        argvalues=(
            (Country, City.population, ("provinces", "cities", "population"), "population", 2),
            (Province, Country.code, ("country", "code"), "code", 1),
            (Province, City.name, ("cities", "name"), "name", 1),
            (City, Country.name, ("province", "country", "name"), "name", 2),
        ),
    )
    def test_resolve_path_as_sequence(
        self,
        model: type[so.DeclarativeBase],
        target_attribute: so.InstrumentedAttribute[tp.Any],
        path: tp.Sequence[str],
        attribute_name: str,
        relationship_length: int,
    ) -> None:
        resolved = RelationshipResolver.resolve(model, path)
        assert resolved.is_nested is True
        assert resolved.target_attribute is target_attribute
        assert resolved.attribute_name == attribute_name
        assert len(resolved.relationship_chain) == relationship_length

    @pytest.mark.parametrize(
        argnames=("model", "target_attribute", "path", "attribute_name", "relationship_length", "expected_is_nested"),
        argvalues=(
            (Country, Province.cities, "provinces__cities", "cities", 1, True),
            (Province, Province.country, "country", "country", 0, False),
            (Province, Province.cities, "cities", "cities", 0, False),
            (City, Province.country, "province__country", "country", 1, True),
        ),
    )
    def test_resolve_path_ending_in_relationship(
        self,
        model: type[so.DeclarativeBase],
        target_attribute: so.InstrumentedAttribute[tp.Any],
        path: str,
        attribute_name: str,
        expected_is_nested: bool,
        relationship_length: int,
    ) -> None:
        resolved = RelationshipResolver.resolve(model, path)
        assert resolved.is_nested is expected_is_nested
        assert resolved.target_attribute is target_attribute
        assert resolved.attribute_name == attribute_name
        assert len(resolved.relationship_chain) == relationship_length
        assert len(resolved.remaining_parts) == 0

    def test_resolve_invalid_path(self) -> None:
        with pytest.raises(AttributeNotFoundError) as exc_info:
            RelationshipResolver.resolve(City, "invalid_column_name")

        assert "attribute was not found" in str(exc_info.value)

    def test_resolve_nested_invalid_path(self) -> None:
        with pytest.raises(AttributeNotFoundError) as exc_info:
            RelationshipResolver.resolve(City, "province__invalid_column")

        assert "The 'invalid_column' attribute was not found on the 'Province' model" in str(exc_info.value)

    def test_resolve_empty_path(self) -> None:
        with pytest.raises(RelationshipResolverError) as exc_info:
            RelationshipResolver.resolve(City, "  ")

        assert "navigation is empty" in str(exc_info.value)
