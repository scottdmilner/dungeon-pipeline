from __future__ import annotations

import logging
import platform
import subprocess
import sys

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Dict, Optional, Sequence, TypeVar
    from types import ModuleType

    KT = TypeVar("KT")
    VT = TypeVar("VT")


log = logging.getLogger(__name__)


class dotdict(dict):
    """dot notation access to dictionary attributes"""

    __getattr__ = dict.get
    __setattr__ = dict.__setitem__  # type: ignore[assignment]
    __delattr__ = dict.__delitem__  # type: ignore[assignment]


def dict_index(d: Dict[KT, VT], v: VT) -> KT:
    """List index function for dicts"""
    return list(d.keys())[list(d.values()).index(v)]


def reload_pipe(extra_modules: Optional[Sequence[ModuleType]] = None) -> None:
    """Reload all pipe python modules"""
    if extra_modules is None:
        extra_modules = []
    else:
        extra_modules = list(extra_modules)

    pipe_modules = [
        module
        for name, module in sys.modules.items()
        if (name.startswith("pipe")) and ("shotgun_api3" not in name) or (name == "env")
    ] + extra_modules

    for module in pipe_modules:
        if (name := module.__name__) in sys.modules:
            log.info(f"Unloading {name}")
            del sys.modules[name]


try:

    def silent_startupinfo() -> Optional[subprocess.STARTUPINFO]:  # type: ignore[name-defined]
        """Returns a Windows-only object to make sure tasks launched through
        subprocess don't open a cmd window.

        Returns:
            subprocess.STARTUPINFO -- the properly configured object if we are on
                                    Windows, otherwise None
        """
        startupinfo = None
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()  # type: ignore[attr-defined]
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore[attr-defined]
        return startupinfo
except Exception:

    def silent_startupinfo() -> Optional[Any]:
        pass
