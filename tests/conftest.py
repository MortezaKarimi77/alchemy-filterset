from enum import StrEnum

import sqlalchemy as sa
import sqlalchemy.orm as so
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy


class OnDelete(StrEnum):
    CASCADE = "CASCADE"
    SET_NULL = "SET NULL"
    RESTRICT = "RESTRICT"
    NO_ACTION = "NO_ACTION"
    SET_DEFAULT = "SET DEFAULT"


class OrmCascade(StrEnum):
    SAVE_UPDATE = "save-update"
    MERGE = "merge"
    DEFAULT = "save-update, merge"
    DELETE = "delete"
    DELETE_ORPHAN = "delete-orphan"
    ALL = "all"
    ALL_DELETE_ORPHAN = "all, delete-orphan"


class Base(so.DeclarativeBase):
    @so.declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.casefold()


class Country(Base):
    # fields
    id: so.Mapped[int] = so.mapped_column(
        sa.BigInteger,
        primary_key=True,
    )
    code: so.Mapped[str] = so.mapped_column(
        sa.String(3),
        unique=True,
    )
    name: so.Mapped[str] = so.mapped_column(
        sa.String(50),
        unique=True,
    )

    # relations
    provinces: so.Mapped[list["Province"]] = so.relationship(
        back_populates="country",
    )


class Province(Base):
    # fields
    id: so.Mapped[int] = so.mapped_column(
        sa.BigInteger,
        primary_key=True,
    )
    country_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey(
            column="country.id",
            ondelete=OnDelete.RESTRICT.value,
        ),
        index=True,
    )
    name: so.Mapped[str] = so.mapped_column(
        sa.String(50),
        unique=True,
    )

    # relations
    country: so.Mapped["Country"] = so.relationship(
        back_populates="provinces",
    )
    cities: so.Mapped[list["City"]] = so.relationship(
        back_populates="province",
    )


class City(Base):
    # fields
    id: so.Mapped[int] = so.mapped_column(
        sa.BigInteger,
        primary_key=True,
    )
    province_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey(
            column="province.id",
            ondelete=OnDelete.RESTRICT.value,
        ),
        index=True,
    )
    name: so.Mapped[str] = so.mapped_column(
        sa.String(50),
        unique=True,
    )
    population: so.Mapped[int]

    # relations
    province: so.Mapped[Province] = so.relationship(
        back_populates="cities",
    )
    city_tags: so.Mapped[list["CityTag"]] = so.relationship(
        back_populates="city",
        cascade=OrmCascade.ALL_DELETE_ORPHAN,
    )

    # proxies
    tags: AssociationProxy[list["Tag"]] = association_proxy(
        target_collection="city_tags",
        attr="tag",
    )
    tag_ids: AssociationProxy[list[int]] = association_proxy(
        target_collection="city_tags",
        attr="tag_id",
    )


class Tag(Base):
    # fields
    id: so.Mapped[int] = so.mapped_column(
        sa.BigInteger,
        primary_key=True,
    )
    name: so.Mapped[str] = so.mapped_column(
        sa.String(50),
        unique=True,
    )

    # relations
    city_tags: so.Mapped[list["CityTag"]] = so.relationship(
        back_populates="tag",
        cascade=OrmCascade.ALL_DELETE_ORPHAN,
    )

    # proxies
    cities: AssociationProxy[list["City"]] = association_proxy(
        target_collection="city_tags",
        attr="city",
    )
    city_ids: AssociationProxy[list[int]] = association_proxy(
        target_collection="city_tags",
        attr="city_id",
    )


class CityTag(Base):
    __tablename__ = "city_tags"

    # fields
    city_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey(
            column="city.id",
            ondelete=OnDelete.CASCADE.value,
        ),
        primary_key=True,
    )
    tag_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey(
            column="tag.id",
            ondelete=OnDelete.CASCADE.value,
        ),
        primary_key=True,
    )

    # relations
    city: so.Mapped["City"] = so.relationship(
        back_populates="city_tags",
    )
    tag: so.Mapped["Tag"] = so.relationship(
        back_populates="city_tags",
    )
