from __future__ import annotations
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import typing

"""Interfaces for interacting with DCCs"""


class DCCInterface(metaclass=ABCMeta):
    """interface for DCCs"""

    @abstractmethod
    def __init__(self):
        """Initialize the DCC"""
        raise NotImplementedError

    @abstractmethod
    def launch(self) -> None:
        """Launch the software"""
        raise NotImplementedError


class DCCLocalizerInterface(metaclass=ABCMeta):
    """interface for functions that need to be localized to the DCC"""

    @abstractmethod
    def __init__(self) -> None:
        """Initialize the pipe instance"""
        raise NotImplementedError

    @abstractmethod
    def get_main_qt_window(self) -> typing.Any:
        """Get the QT object representing the main application window.
        Use for the parent of other QT popups"""
        raise NotImplementedError

    @abstractmethod
    def is_headless(self) -> bool:
        """Check if this is a headless environment (no GUI)"""
        raise NotImplementedError
