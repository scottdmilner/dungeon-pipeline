import importlib
import importlib.util
import platform
import subprocess

from inspect import getmembers, isabstract, isclass, isfunction
from pathlib import Path
from typing import Optional, Union

from env import production_path as _prp


class dotdict(dict):
    """dot notation access to dictionary attributes"""

    __getattr__ = dict.get
    __setattr__ = dict.__setitem__  # type: ignore[assignment]
    __delattr__ = dict.__delitem__  # type: ignore[assignment]


def check_methods(cls: type, subclass: type) -> bool:
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


def find_implementation(cls: type, module: str, package: Optional[str] = None) -> type:
    """Find an implementation of the class in the specified module."""
    # Check if the specified module exists
    if importlib.util.find_spec(module, package):
        # Import the module
        imported_module = importlib.import_module(module, package)

        # Check if the submodule contains an implementation of the class
        classes = getmembers(
            imported_module,
            lambda obj: isclass(obj) and not isabstract(obj) and issubclass(obj, cls),
        )

        # Check if more or less than one implementation was found
        if len(classes) < 1:
            raise AssertionError(
                f"module '{module}' does not contain an "
                f"implementation of class '{cls.__name__}'"
            )
        elif len(classes) > 1:
            raise AssertionError(
                f"module '{module}' contains multiple "
                f"implementations of class '{cls.__name__}'"
            )

        # Return the implementing class
        return classes[0][1]

    else:
        raise ValueError(f"could not find module '{module}'")


def fix_launcher_metadata() -> None:
    if platform.system() != "Linux":
        return
    try:
        procs = [
            subprocess.Popen(
                [
                    "gio",
                    "set",
                    str(item),
                    "metadata::caja-trusted-launcher",
                    "true",
                ]
            )
            for item in get_pipe_path().parent.iterdir()
            if item.suffix == ".desktop"
        ]
        for p in procs:
            p.wait()

    except:
        pass


def get_pipe_path() -> Path:
    return Path(__file__).resolve().parents[1]


def get_character_path() -> Path:
    return get_production_path().parent / "character"


def get_rigging_path() -> Path:
    return get_character_path() / "Rigging"


def get_anim_path() -> Path:
    return get_production_path().parent / "anim"


def get_production_path() -> Path:
    return _prp


def get_asset_path() -> Path:
    return get_production_path() / "asset"


def resolve_mapped_path(path: Union[str, Path]) -> Path:
    """Windows mapped drive workaround. Adapated from: https://bugs.python.org/msg309160"""
    path = Path(path).resolve()

    if platform.system() != "Windows":
        return path

    mapped_paths = []
    for drive in "ZYXWVUTSRQPONMLKJIHGFEDCBA":
        root = Path("{}:/".format(drive))
        try:
            mapped_paths.append(root / path.relative_to(root.resolve()))
        except (ValueError, OSError):
            pass
    return min(mapped_paths, key=lambda x: len(str(x)), default=path)


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
except:

    def silent_startupinfo() -> None:
        pass
