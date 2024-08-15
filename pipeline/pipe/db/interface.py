from __future__ import annotations

from abc import ABCMeta, abstractmethod
from enum import Enum
from inspect import getmembers, isfunction
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import typing

from pipe.struct.db import (
    Asset,
    AssetStub,
    SGEntity,
    SGEntityStub,
    Sequence,
    SequenceStub,
    Shot,
    ShotStub,
)


def _check_methods(cls: type, subclass: type) -> bool:
    """Check if a class implements another class's methods."""
    # Get the names of the class's methods
    methods: list = [member[0] for member in getmembers(cls, isfunction)]

    # Get the subclass's method resolution order (MRO)
    mro = subclass.__mro__

    # Check if the subclass's MRO contains every method
    for method in methods:
        for entry in mro:
            if method in entry.__dict__:
                if entry.__dict__[method] is None:
                    return NotImplemented
                break
        else:
            return NotImplemented
    return True


class DBInterface(metaclass=ABCMeta):
    """Interface for database interaction"""

    class ChildQueryMode(Enum):
        # children + assets w/ no children
        LEAVES = 0
        # all
        ALL = 1
        # only assets that have parents
        CHILDREN = 2
        # only assets that have children
        PARENTS = 3
        # top-level assets regardless of if they have children
        ROOTS = 4

    @classmethod
    def __subclasshook__(cls, subclass: type) -> bool:
        return _check_methods(cls, subclass)

    @abstractmethod
    def __init__(self) -> None:
        """Initialize the DB"""
        raise NotImplementedError

    @abstractmethod
    def get_entity_by_attr(
        self, entity_type: type[SGEntity], attr: str, attr_val: str | int
    ) -> SGEntity:
        """Get an entity by an attribute"""
        raise NotImplementedError

    @abstractmethod
    def get_entity_by_stub(
        self, entity_type: type[SGEntity], stub: SGEntityStub
    ) -> SGEntity:
        """Get an entity from a stub"""
        raise NotImplementedError

    @abstractmethod
    def get_entities_by_stub(
        self, entity_type: type[SGEntity], stubs: typing.Iterable[SGEntityStub]
    ) -> list[SGEntity]:
        """Get a list of entities from a list of stubs (all stubs must be of
        type `entity_type`)"""
        raise NotImplementedError

    @abstractmethod
    def get_entity_attr_list(
        self, entity_type: type[SGEntity], attr: str, *, sorted: bool
    ) -> list[str]:
        """Get a list of values of a specific attribute on the entities of a
        specified type"""
        raise NotImplementedError

    @abstractmethod
    def get_entity_code_list(
        self,
        entity_type: type[SGEntity],
        *,
        sorted: bool = False,
        child_mode: DBInterface.ChildQueryMode | None = None,
    ) -> list[str]:
        """Get a list of codes/names for the given entity type"""
        raise NotImplementedError

    @abstractmethod
    def get_entity_by_code(self, entity_type: type[SGEntity], code: str) -> SGEntity:
        """Get an entity by its code and type"""
        raise NotImplementedError

    @abstractmethod
    def get_asset_by_attr(self, attr: str, attr_val: str | int) -> Asset:
        """Get an asset that matches a specific attribute"""
        raise NotImplementedError

    @abstractmethod
    def get_asset_by_name(self, attr_val: str | int) -> Asset:
        """Get an asset by its name"""
        raise NotImplementedError

    @abstractmethod
    def get_asset_by_id(self, attr_val: str | int) -> Asset:
        """Get an asset by its id"""
        raise NotImplementedError

    @abstractmethod
    def get_asset_by_stub(self, stubs: AssetStub) -> Asset:
        """Get an asset from a stub"""
        raise NotImplementedError

    @abstractmethod
    def get_assets_by_stub(self, stubs: typing.Iterable[AssetStub]) -> list[Asset]:
        """Get a list of assets from a list of stubs"""
        raise NotImplementedError

    @abstractmethod
    def get_asset_attr_list(
        self,
        attr: str,
        *,
        child_mode: DBInterface.ChildQueryMode,
        sorted: bool = False,
    ) -> list[str]:
        """Get a list of a single attribute on the asset list"""
        raise NotImplementedError

    @abstractmethod
    def get_asset_name_list(
        self, child_mode: DBInterface.ChildQueryMode, sorted: bool
    ) -> list[str]:
        """Get a list of asset names"""
        raise NotImplementedError

    @abstractmethod
    def get_assets_by_name(self, names: typing.Iterable[str]) -> list[Asset]:
        """Get a list of assets from a list of names"""
        raise NotImplementedError

    @abstractmethod
    def update_asset(self, asset: Asset) -> bool:
        """Update an asset in the DB"""
        raise NotImplementedError

    @abstractmethod
    def get_sequence_by_attr(self, attr: str, attr_val: str | int) -> Sequence:
        """Get a sequence based off an attribute"""
        raise NotImplementedError

    @abstractmethod
    def get_sequence_by_code(self, code: str) -> Sequence:
        """Get a sequence based off the code"""
        raise NotImplementedError

    @abstractmethod
    def get_sequence_by_id(self, id: int) -> Sequence:
        """Get a sequence from the ID"""
        raise NotImplementedError

    @abstractmethod
    def get_sequence_by_stub(self, stub: SequenceStub) -> Sequence:
        """Get a sequence from a stub"""
        raise NotImplementedError

    @abstractmethod
    def get_sequences_by_stub(
        self, stubs: typing.Iterable[SequenceStub]
    ) -> list[Sequence]:
        """Get a list of sequences from a list of SequencStubs"""
        raise NotImplementedError

    @abstractmethod
    def get_sequence_attr_list(self, attr: str, *, sorted: bool) -> list[str]:
        """Get a list of sequence attributes"""
        raise NotImplementedError

    @abstractmethod
    def get_sequence_code_list(self, sorted: bool) -> list[str]:
        """Get a list of sequence codes"""
        raise NotImplementedError

    @abstractmethod
    def get_shot_by_attr(self, attr: str, attr_val: str | int) -> Shot:
        """Get a shot based off of an attribute"""
        raise NotImplementedError

    @abstractmethod
    def get_shot_by_code(self, code: str) -> Shot:
        """Get a shot based of its code"""
        raise NotImplementedError

    @abstractmethod
    def get_shot_by_id(self, id: int) -> Shot:
        """Get a shot based off its id"""
        raise NotImplementedError

    @abstractmethod
    def get_shot_by_stub(self, stub: ShotStub) -> Shot:
        """Get a shot from its stub"""
        raise NotImplementedError

    @abstractmethod
    def get_shots_by_stub(self, stubs: typing.Iterable[ShotStub]) -> list[Shot]:
        """Get a list of shots from a list of ShotStubs"""
        raise NotImplementedError

    @abstractmethod
    def get_shot_attr_list(self, attr: str, *, sorted: bool) -> list[str]:
        """Get a list of values of an attribute on the shots"""
        raise NotImplementedError

    @abstractmethod
    def get_shot_code_list(self, sorted: bool) -> list[str]:
        """Get a list of shot codes"""
        raise NotImplementedError
