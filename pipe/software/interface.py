"""Interfaces for interacting with DCCs"""

from abc import ABCMeta, abstractmethod


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
