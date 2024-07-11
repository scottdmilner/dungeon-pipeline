from abc import ABCMeta, abstractmethod
from inspect import getmembers, isfunction
from typing import Iterable, Optional, Sequence

from pipe.struct.db import Asset


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

    @classmethod
    def __subclasshook__(cls, subclass: type) -> bool:
        return _check_methods(cls, subclass)

    @abstractmethod
    def __init__(self) -> None:
        """Initialize the DB"""
        raise NotImplementedError

    @abstractmethod
    def get_asset_by_name(self, name: str) -> Optional[Asset]:
        """Get an Asset object"""
        raise NotImplementedError

    @abstractmethod
    def get_assets_by_name(self, names: Iterable[str]) -> list[Asset]:
        """Get multiple Asset objects"""
        raise NotImplementedError

    @abstractmethod
    def get_asset_name_list(self) -> Sequence[str]:
        """Get a list of Asset ids"""
        raise NotImplementedError
