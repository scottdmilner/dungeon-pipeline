from __future__ import annotations

import logging

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from typing import Any, ClassVar, Protocol, TypeVar

    KT = TypeVar("KT")
    VT = TypeVar("VT")

    class IsDataclass(Protocol):
        __dataclass_fields__: ClassVar[dict[str, Any]]
        __match_args__: ClassVar[tuple[str]]


log = logging.getLogger(__name__)


class dotdict(dict):
    """dot notation access to dictionary attributes"""

    __getattr__ = dict.get
    __setattr__ = dict.__setitem__  # type: ignore[assignment]
    __delattr__ = dict.__delitem__  # type: ignore[assignment]


def dataclass_as_tuple(dc: IsDataclass) -> tuple[Any]:
    return tuple((getattr(dc, a) for a in dc.__match_args__))


def dict_index(d: dict[KT, VT], v: VT) -> KT:
    """List index function for dicts"""
    return list(d.keys())[list(d.values()).index(v)]
