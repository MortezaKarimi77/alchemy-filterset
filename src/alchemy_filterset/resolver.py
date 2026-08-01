import typing as tp
from dataclasses import dataclass, field

from sqlalchemy import ColumnElement
from sqlalchemy.ext.associationproxy import AssociationProxyInstance
from sqlalchemy.orm import DeclarativeBase, InstrumentedAttribute

from . import exceptions

type QueryableAttribute = InstrumentedAttribute[tp.Any] | AssociationProxyInstance[tp.Any] | ColumnElement[tp.Any]


@dataclass(slots=True)
class ResolvedPath:
    root_model: type[DeclarativeBase]
    target_model: type[DeclarativeBase]
    target_attribute: QueryableAttribute | None
    attribute_name: str
    relationship_chain: list[tuple[InstrumentedAttribute[tp.Any], bool]] = field(default_factory=list)
    remaining_parts: list[str] = field(default_factory=list)

    @property
    def is_nested(self) -> bool:
        return len(self.relationship_chain) > 0


class RelationshipResolver:
    @classmethod
    def resolve(cls, root_model: type[DeclarativeBase], path: str | tp.Sequence[str], sep: str = "__") -> ResolvedPath:
        paths = (path,) if isinstance(path, str) else path
        parts = [part.strip() for path in paths for part in path.split(sep) if part.strip()]

        if not parts:
            raise exceptions.RelationshipResolverError("The entered path for navigation is empty.")

        current_model = root_model
        relationship_chain: list[tuple[InstrumentedAttribute[tp.Any], bool]] = []
        remaining_parts: list[str] = []

        for index, part in enumerate(parts):
            if (attribute := getattr(current_model, part, None)) is None:
                raise exceptions.AttributeNotFoundError(current_model, part)

            if cls._is_relationship(attribute):
                if index == len(parts) - 1:
                    return ResolvedPath(
                        root_model=root_model,
                        target_model=current_model,
                        target_attribute=attribute,
                        attribute_name=part,
                        relationship_chain=relationship_chain,
                    )

                uselist = attribute.property.uselist
                relationship_chain.append((attribute, uselist))
                current_model = attribute.property.mapper.class_

            elif isinstance(attribute, AssociationProxyInstance):
                local_attr = attribute.local_attr
                relationship_chain.append((local_attr, local_attr.property.uselist))

                remote_attr = attribute.remote_attr
                if cls._is_relationship(remote_attr):
                    relationship_chain.append((remote_attr, remote_attr.property.uselist))
                    current_model = remote_attr.property.mapper.class_
                else:
                    remaining_parts = parts[index + 1 :]
                    return ResolvedPath(
                        root_model=root_model,
                        target_model=local_attr.property.mapper.class_,
                        target_attribute=remote_attr,
                        attribute_name=part,
                        relationship_chain=relationship_chain,
                        remaining_parts=remaining_parts,
                    )

            else:
                remaining_parts = parts[index + 1 :]
                return ResolvedPath(
                    root_model=root_model,
                    target_model=current_model,
                    target_attribute=attribute,
                    attribute_name=part,
                    relationship_chain=relationship_chain,
                    remaining_parts=remaining_parts,
                )

        last_attribute = relationship_chain[-1][0] if relationship_chain else None
        return ResolvedPath(
            root_model=root_model,
            target_model=current_model,
            target_attribute=last_attribute,
            attribute_name=last_attribute.key if last_attribute else "",
            relationship_chain=relationship_chain,
            remaining_parts=remaining_parts,
        )

    @staticmethod
    def _is_relationship(attribute: tp.Any) -> bool:
        return hasattr(attribute, "property") and hasattr(attribute.property, "mapper")
