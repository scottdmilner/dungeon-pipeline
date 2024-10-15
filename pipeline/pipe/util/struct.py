from __future__ import annotations

import logging

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    import typing

    KT = typing.TypeVar("KT")
    VT = typing.TypeVar("VT")


log = logging.getLogger(__name__)


class dotdict(dict):
    """dot notation access to dictionary attributes"""

    __getattr__ = dict.get
    __setattr__ = dict.__setitem__  # type: ignore[assignment]
    __delattr__ = dict.__delitem__  # type: ignore[assignment]


def dict_index(d: dict[KT, VT], v: VT) -> KT:
    """List index function for dicts"""
    return list(d.keys())[list(d.values()).index(v)]
