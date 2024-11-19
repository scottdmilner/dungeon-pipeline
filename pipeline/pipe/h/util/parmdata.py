from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import hou
    from typing import Any, Protocol

    class T_ParmData(Protocol):
        _node: hou.Node


def get_eval_fn(typ: str) -> str:
    if typ == "str":
        eval_fn = "evalAsString"
    elif typ == "float":
        eval_fn = "evalAsFloat"
    elif typ == "int":
        eval_fn = "evalAsInt"
    else:
        raise AttributeError(f"Unrecognized parm type: {typ}")
    return eval_fn


def get_cast(typ: str) -> type:
    t_cast: type
    if typ == "str":
        t_cast = str
    elif typ == "float":
        t_cast = float
    elif typ == "int":
        t_cast = int
    else:
        raise AttributeError(f"Unrecognized parm type: {typ}")
    return t_cast


def create_property(
    typ: str, parm: str, has_toggle: bool = False, writable: bool = False
) -> property:
    def getter(self: T_ParmData):
        return getattr(self._node.parm(parm), get_eval_fn(typ))()

    def getter_toggled(self: T_ParmData):
        if self._node.parm("toggle_" + parm).evalAsInt():  # type: ignore[union-attr]
            return getter(self)
        return None

    def setter(self: T_ParmData, value):
        self._node.parm(parm).set(get_cast(typ)(value))  # type: ignore[union-attr]

    return property(
        getter_toggled if has_toggle else getter, setter if writable else None
    )


@dataclass
class parmfield:
    has_toggle: bool = False
    writable: bool = False


class ParmData(type):
    def __new__(cls, name, bases, attrs: dict) -> ParmData:
        def __init__(self: T_ParmData, node: hou.Node) -> None:
            self._node = node
            for attr in self.__annotations__.keys():
                if not node.parm(attr):
                    raise AttributeError(f"Parm {attr} not found on node {node.name()}")

        new_attrs: dict[str, Any] = {
            cls.__init__.__name__: __init__,
        }

        annotations: dict[str, str] = attrs.get("__annotations__")  # type: ignore[assignment]
        if annotations:
            for attr, typ in annotations.items():
                has_toggle = False
                writable = False
                if isinstance(f := attrs.get(attr), parmfield):
                    has_toggle = f.has_toggle
                    writable = f.writable

                new_attrs[attr] = create_property(typ, attr, has_toggle, writable)

        return super().__new__(cls, name, bases, {**attrs, **new_attrs})
